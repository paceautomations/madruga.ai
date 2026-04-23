---
title: "Engineering Blueprint"
updated: 2026-04-13
sidebar:
  order: 1
---
# Blueprint de Engenharia

Referencia tecnica consolidada da plataforma **ProsaUAI — Agentes WhatsApp**: stack, topologia, concerns transversais, NFRs, mapa de dados e glossario.

> **Convencao**: esta pagina consolida o **O QUE** e **COMO**. Para o **POR QUE** de cada decisao, consulte os [ADRs](../decisions/).
>
> Artefatos relacionados: [Domain Model](../domain-model/) · [Context Map](../context-map/) · [Containers](../containers/) · [Integrations](../integrations/) · [ADRs](../decisions/)

---

## 1. Technology Stack

| Componente | Runtime | Porta/Protocolo | Scaling |
|------------|---------|-----------------|---------|
| prosauai-api | Python 3.12, FastAPI + uvicorn | 8050/HTTP | Horizontal (stateless) |
| prosauai-worker | Python 3.12, ARQ (async task queue) | — (consumer) | Horizontal (Redis consumer groups) |
| prosauai-admin | Next.js 15, shadcn/ui | 3000/HTTP | Horizontal (stateless) |
| Redis 7 | Managed ou self-hosted | 6379/TCP | Single instance + Sentinel (HA) |
| Supabase (PG 15 + pgvector + RLS) | Managed (Supabase Cloud) | 5432/TCP | Vertical (managed) |
| Bifrost | Go binary (LLM proxy) | 8080/HTTP | Horizontal (stateless) |
| Phoenix (Arize) | Docker Compose (self-hosted) | 6006/HTTP (UI) + 4317/gRPC (OTLP) | Single instance |
| Infisical | Docker Compose (self-hosted) | 8080/HTTP | Single instance |
| Evolution API | Cloud mode (managed) | — (webhook) | Managed pelo provider |

---

## 2. Deploy Topology

> Visao geral de todos os componentes, atores e conexoes da plataforma.
> Detalhamento C4 L2 dos containers → ver [containers.md](../containers/)
> Integracoes externas detalhadas → ver [integrations.md](../integrations/)

```mermaid
graph LR
    %% Actors
    agent(("Agente WhatsApp"))
    admin_user(("Admin / Operador"))

    %% Platform
    subgraph prosauai ["ProsaUAI Platform"]
        prosauai-api["prosauai-api<br/><small>Python 3.12 + FastAPI</small>"]
        prosauai-worker["prosauai-worker<br/><small>Python 3.12 + ARQ</small>"]
        prosauai-admin["prosauai-admin<br/><small>Next.js 15 + shadcn/ui</small>"]
    end

    %% Infrastructure
    subgraph infra ["Infrastructure"]
        redis["Redis 7"]
        supabase-prosauai[("Supabase ProsaUAI<br/><small>PG 15 + pgvector</small>")]
        bifrost["Bifrost<br/><small>Go LLM Proxy</small>"]
    end

    %% External Services
    subgraph external ["External"]
        evolution-api["Evolution API<br/><small>WhatsApp Gateway</small>"]
        supabase-resenhai[("Supabase ResenhAI<br/><small>PG 15 read-only</small>")]
        openai-gpt-mini["OpenAI gpt-5.4-mini<br/><small>default model (ADR-025)</small>"]
        phoenix-ext["Phoenix (Arize)<br/><small>OTel traces</small>"]
        infisical["Infisical"]
    end

    %% Actor connections
    agent -- "HTTPS webhook" --> prosauai-api
    admin_user -- "HTTPS + JWT" --> prosauai-admin
    evolution-api -- "webhook POST<br/>X-Webhook-Secret" --> prosauai-api

    %% Internal platform flows
    prosauai-api -- "XADD Redis Streams" --> redis
    prosauai-api -- "GET/SET cache" --> redis
    prosauai-api -- "Socket.io WebSocket" --> prosauai-admin
    prosauai-admin -- "REST API /api/v1/*" --> prosauai-api
    prosauai-admin -- "Supabase JS client" --> supabase-prosauai
    redis -- "XREADGROUP" --> prosauai-worker
    prosauai-worker -- "PUBLISH events" --> redis

    %% Worker → Infrastructure
    prosauai-worker -- "asyncpg SQL" --> supabase-prosauai
    supabase-prosauai -. "PG LISTEN/NOTIFY" .-> prosauai-worker
    prosauai-worker -- "POST /v1/chat/completions" --> bifrost

    %% Worker → External
    prosauai-worker -- "POST sendText" --> evolution-api
    prosauai-worker -- "asyncpg read-only" --> supabase-resenhai
    prosauai-worker -. "OTLP gRPC traces" .-> phoenix-ext
    prosauai-worker -- "SDK secret read" --> infisical

    %% Bifrost → LLMs
    bifrost -- "OpenAI API" --> openai-gpt-mini
```

### 2.1 Ambientes

| Ambiente | Finalidade | Infra |
|----------|------------|-------|
| local | Desenvolvimento e testes | `docker-compose.yml` — todos servicos (Phoenix SQLite, sem Netdata/retention) |
| staging | QA, red-teaming, testes de integracao | Subset producao; tenants de teste |
| production | Tenants reais | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up` — Phoenix Postgres, Netdata, retention-cron. VPS minimo: 2 vCPU, 4GB RAM, 40GB SSD |

### 2.2 CI/CD

> **Nota**: pipeline em definicao. Estrutura planejada abaixo.

| Etapa | Ferramenta | Gate |
|-------|------------|------|
| Lint + type check | ruff, mypy | Blocking |
| Unit tests | pytest | Blocking |
| RLS isolation tests | pytest + Supabase test DB | Blocking |
| Prompt regression | Promptfoo | Warning |
| Security scan | — (a definir no epic 001) | Blocking |
| Deploy staging | — (a definir no epic 001) | Automatico |
| Deploy production | — (a definir no epic 001) | Manual approval |

---

## 3. Folder Structure

```text
prosauai/
├── prosauai/
│   ├── __init__.py
│   ├── main.py               # FastAPI app, lifespan (tenants + routing engines + Redis + debounce)
│   ├── config.py              # pydantic-settings + .env
│   ├── core/                  # Core domain logic
│   │   ├── tenant.py          # Tenant frozen dataclass (10 fields, incl default_agent_id)
│   │   ├── tenant_store.py    # YAML loader + ${VAR} interpolation
│   │   ├── formatter.py       # Evolution v2.3.0 payload → ParsedMessage (13 tipos)
│   │   ├── idempotency.py     # Redis SETNX deduplication (24h TTL per-tenant)
│   │   ├── debounce.py        # DebounceManager (Redis Lua + keyspace notifications, tenant-prefixed)
│   │   └── router/            # Epic 004: Router MECE
│   │       ├── __init__.py    # Public API: route() + models
│   │       ├── facts.py       # MessageFacts + classify() pure function
│   │       ├── engine.py      # RoutingEngine + Rule evaluation (priority-based)
│   │       ├── loader.py      # YAML routing config loader + MECE verification
│   │       ├── matchers.py    # MentionMatchers (3-strategy: @lid, phone, keywords)
│   │       ├── errors.py      # Custom exceptions
│   │       └── verify.py      # MECE overlap verification CLI
│   ├── conversation/          # Epic 005: Conversation Core (LLM pipeline) + Epic 009 (content_process)
│   │   ├── pipeline.py        # 13-step orchestrated conversation flow (step 6 content_process — ADR-032)
│   │   ├── agent.py           # pydantic-ai agent generation + response
│   │   ├── classifier.py      # Intent classification (LLM structured output, 0.7 threshold)
│   │   ├── context.py         # Sliding context window (N=10 msgs, 8K token budget)
│   │   ├── customer.py        # Customer lookup/create (phone → SHA-256 hash)
│   │   ├── evaluator.py       # Response evaluation (heuristic 0-1, APPROVE/RETRY/ESCALATE)
│   │   └── state.py           # Conversation state management (active → closed lifecycle)
│   ├── safety/                # Epic 005: Safety guards (3-layer)
│   │   ├── input_guard.py     # PII detection (7 regex), length check, injection patterns
│   │   ├── output_guard.py    # PII masking before delivery
│   │   └── patterns.py        # Shared PII + injection regex patterns
│   ├── tools/                 # Epic 005: Tool registry
│   │   ├── registry.py        # @register_tool decorator + TOOL_REGISTRY + whitelist
│   │   └── resenhai.py        # ResenhAI rankings tool (HTTP stub)
│   ├── channels/              # Channel adapters (ACL boundary)
│   │   ├── base.py            # MessagingProvider ABC
│   │   └── evolution.py       # EvolutionProvider (httpx async)
│   ├── api/                   # FastAPI endpoints
│   │   ├── webhooks.py        # POST /webhook/whatsapp/{instance_name}
│   │   ├── webhooks/
│   │   │   └── helpdesk/
│   │   │       └── chatwoot.py # POST /webhook/helpdesk/chatwoot/{tenant_slug} (epic 010)
│   │   ├── health.py          # GET /health (status + Redis + OTel)
│   │   └── dependencies.py    # resolve_tenant_and_authenticate() (X-Webhook-Secret)
│   ├── handoff/               # Epic 010: Handoff Engine + Multi-Helpdesk
│   │   ├── base.py            # HelpdeskAdapter Protocol + error hierarchy (ADR-037)
│   │   ├── registry.py        # register/get adapters by helpdesk_type
│   │   ├── state.py           # mute_conversation / resume_conversation (advisory lock, ADR-036)
│   │   ├── events.py          # HandoffEvent dataclass + persist_event fire-and-forget
│   │   ├── breaker.py         # CircuitBreaker per (tenant, helpdesk)
│   │   ├── chatwoot.py        # ChatwootAdapter (HMAC + API v1 + private notes + operator reply)
│   │   ├── none.py            # NoneAdapter (fromMe hook + bot_sent_messages echo check, ADR-038)
│   │   └── scheduler.py       # Periodic tasks: auto_resume + bot_sent_messages_cleanup + handoff_events_cleanup
│   ├── db/                    # Epic 005: Database layer
│   │   └── pool.py            # asyncpg pool (min=2, max=10, JSONB codec, search_path)
│   ├── ops/                   # Epic 006: Operations tooling
│   │   ├── migrate.py         # Migration runner (asyncpg, advisory lock, checksum)
│   │   ├── retention.py       # LGPD retention logic (partition drop + batch delete)
│   │   ├── retention_cli.py   # CLI: --dry-run, --database-url, --log-level
│   │   └── partitions.py      # Partition manager (ensure future + drop expired)
│   └── observability/         # OTel SDK + Phoenix integration (epic 002)
│       ├── __init__.py
│       ├── setup.py           # configure_observability() — SDK + exporter
│       ├── conventions.py     # SpanAttributes constants (prosauai.*, gen_ai.*)
│       ├── structlog_bridge.py # add_otel_context processor (log↔trace)
│       ├── tracing.py         # get_tracer(), W3C context inject/extract
│       └── health.py          # ExporterHealthTracker (thread-safe export status)
├── config/                    # Tenant & routing configuration
│   ├── tenants.yaml           # Active tenants (gitignored, ${VAR} interpolated)
│   ├── tenants.example.yaml   # Template with instructions
│   └── routing/               # Per-tenant routing rules (YAML)
│       ├── ariel.yaml         # Pace-internal tenant rules
│       └── resenhai.yaml      # ResenhAI tenant rules
├── tests/                     # pytest (unit + integration)
│   ├── conftest.py            # Fixtures + parametrized discovery
│   ├── fixtures/captured/     # 26 real-payload fixture pairs (*.input.json + *.expected.yaml)
│   ├── unit/                  # 24 unit test modules
│   └── integration/           # 5 integration test modules
├── tools/                     # Payload capture & anonymization
├── scripts/                   # Automation (e2e-validate, verify-routing-configs)
├── pyproject.toml             # Deps, ruff, pytest config
├── Dockerfile                 # Multi-stage build (port 8050)
├── docker-compose.yml         # api + redis + phoenix
└── .env.example               # Environment template (40+ vars)
```

> **Nota**: A estrutura atual (packages por concern) evoluiu organicamente com os epics 001-006. Packages de dominio (`conversation/`, `safety/`, `tools/`) ja refletem bounded contexts do domain model. Evolucao para `src/domain/` com BCs explicitamente separados e `src/infra/` pode ser considerada quando ARQ worker for introduzido e a separacao API/worker exigir shared domain layer.

| Convencao | Regra |
|-----------|-------|
| Packages por concern | `core/` (dominio base), `conversation/` (LLM pipeline), `safety/` (guardrails), `tools/` (registry), `api/` (endpoints), `channels/` (adapters), `handoff/` (helpdesk integration — epic 010), `db/` (pool), `ops/` (migrations, retention), `observability/` (cross-cutting), `core/router/` (routing engine) |
| Config per-tenant | `config/tenants.yaml` (identidade) + `config/routing/*.yaml` (regras de roteamento) |
| RLS tests | Obrigatorios para toda nova tabela com tenant_id |
| Secrets | Nunca em codigo; sempre via env vars (.env) — Infisical SDK em fase futura |

---

## 3b. Database Schema Layout (epic 006)

> Detalhes completos em [ADR-024](../decisions/ADR-024-schema-isolation.md) e [data-model.md](../epics/006-production-readiness/data-model.md).

| Schema | Conteudo | Gerenciado por |
|--------|----------|----------------|
| `prosauai` | 7 tabelas de negocio: customers, conversations, conversation_states, messages (particionada), agents, prompts, eval_scores | Migrations da app (`migrations/*.sql`) |
| `prosauai_ops` | `schema_migrations` (tracking de migrations aplicadas) | Migrations da app |
| `public` | `tenant_id()` SECURITY DEFINER STABLE (funcao RLS helper). Usa `gen_random_uuid()` built-in — **sem extensoes adicionais**. **Epic 008**: tabelas admin-only sem RLS: `traces` (pipeline execution — 12 steps cada), `trace_steps` (FK CASCADE; JSONB input/output truncados 8 KB), `routing_decisions` (append-only, incluindo DROPs invisiveis no epic 004). **Epic 010**: mais duas tabelas admin-only sob o mesmo carve-out: `handoff_events` (append-only, audit trail dos mutes/resumes/breakers, retention 90d via cron FR-047a) + `bot_sent_messages` (tracking 48h usado pelo NoneAdapter para evitar bot echo, retention 48h). Acessiveis exclusivamente via `pool_admin` (BYPASSRLS) — carve-out documentado em ADR-027 | Migrations da app (funcao) + Supabase (schema) |
| `observability` | Tabelas Phoenix (traces, spans) | Phoenix auto-managed (`PHOENIX_SQL_DATABASE_SCHEMA`) |
| `admin` | Reservado — tenants, audit_log (epic 013) | Futuro |
| `auth` | Supabase-managed (GoTrue) — **NAO TOCAR** | Supabase |

**Particionamento**: Tabela `messages` usa `PARTITION BY RANGE (created_at)` com particoes mensais. Purge via `DROP TABLE partition` (<100ms). Particoes futuras criadas 3 meses a frente pelo cron de retention.

**search_path**: Connection pool configura `search_path = prosauai,prosauai_ops,public` — queries existentes funcionam sem schema prefix.

## 3c. Migration Runner (epic 006)

Migrations aplicadas automaticamente no startup da API (fail-fast):

```python
# prosauai/main.py (lifespan)
await run_migrations(dsn=settings.database_url, migrations_dir=Path("./migrations"))
```

- **Forward-only**: Sem rollback. Correcoes via nova migration
- **Idempotente**: Re-execucao nao aplica migrations ja registradas
- **Checksum**: SHA-256 do conteudo detecta drift
- **Tracking**: `prosauai_ops.schema_migrations` (version, applied_at, checksum)

CLI: `python -m prosauai.ops.migrate --database-url $DATABASE_URL`

## 3d. Log Persistence (epic 006)

Todos os containers Docker com log rotation configurado:

```yaml
# docker-compose.yml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"
```

- **Max total por service**: 250MB (50m x 5 files)
- **Max total stack** (5 services): 1.25GB
- **Aplicado a**: api, redis, postgres, phoenix + netdata, retention-cron (prod)
- **Logs sobrevivem restarts** e sao acessiveis via `docker compose logs`

---

## 3e. Admin (epic 008)

O epic 008 evoluiu o admin (fundacao do epic 007: sidebar minima + login +
dashboard com 1 KPI) para plataforma operacional com **8 abas funcionais**,
cada uma cobrindo um vertice do ciclo de vida da conversa:

| # | Aba | Finalidade principal | User Story |
|---|-----|----------------------|------------|
| 1 | **Overview** | "Esta tudo bem?" em <10 s: 6 KPIs (conversas, mensagens, containment, latencia, QS, erros) + sparklines 24 h + activity feed + system health + saude por tenant | US4 |
| 2 | **Conversas** | Inbox com thread + perfil do contato, busca ILIKE em `customers.display_name` + `messages.content`; read-only (envio via WhatsApp externo) | US1 |
| 3 | **Trace Explorer** | Waterfall das 12 etapas do pipeline com input/output por step (truncados 8 KB), tokens/modelo/custo, erro auto-expandido | US2 |
| 4 | **Performance AI** | Agregacoes qualidade/custo com 5 graficos (intent distribution, quality trend, latency waterfall, error heatmap 24×7, cost by model); cache Redis 5 min | US3 |
| 5 | **Agentes** | Config + diff de prompts (safety_prefix / system_prompt / safety_suffix com fundo distinto), metricas vs. media da plataforma | US6 |
| 6 | **Roteamento** | Decisoes MECE persistidas INCLUINDO `DROP`/`LOG_ONLY`/`BYPASS_AI` (antes invisiveis em logs) com `matched_rule` + `MessageFacts` em JSON | US5 |
| 7 | **Tenants** | Admin CRUD + toggle `enabled`, metricas 7 d por tenant | US7 |
| 8 | **Auditoria** | Timeline paginada com anomaly detection (3+ `login_failed` mesmo IP em 24 h destacados) | US8 |

Persistencia (3 tabelas admin-only em `public.*`, sem RLS — ADR-027):

| Tabela | Finalidade | Retencao default |
|--------|-----------|------------------|
| `public.traces` | 1 row por execucao completa do pipeline (parent) | 30 d |
| `public.trace_steps` | 12 rows por trace (FK CASCADE); JSONB input/output truncados 8 KB | 30 d (cascade) |
| `public.routing_decisions` | Append-only; toda decisao do router MECE com `decision_type` + `matched_rule` + `facts` + `trace_id` | 90 d |

Denormalizacao: `public.conversations` ganha `last_message_id` + `last_message_at` + `last_message_preview` (200 chars) para inbox <100 ms em 10k conversas (SC-005).

Caracteristicas-chave:

- **Fire-and-forget**: persistencia de trace/steps e routing_decisions via `asyncio.create_task` — zero impacto no caminho critico da resposta ao cliente (padrao herdado do Phoenix exporter; ADR-028).
- **Filtro global de tenant**: URL param `?tenant=<slug>` (ou `all`) como unica fonte de verdade. Server Components leem via `searchParams` — sem context/cookie.
- **Tudo acessado via `pool_admin`**: queries admin fazem bypass de RLS (cross-tenant por design). Apps que escrevem (pipeline/router) tambem usam `pool_admin` para popular as 3 tabelas novas.
- **Stack reaproveitada** do epic 007: Next.js 15 App Router + shadcn/ui + Tailwind v4 + Recharts + TanStack Query v5 + lucide-react. Dark mode unico na v1 (tokens OKLCH).
- **Tipos gerados**: backend expoe OpenAPI 3.1 em `contracts/openapi.yaml`; frontend consome via `pnpm gen:api` (openapi-typescript) — evita drift.
- **Retention cron** do epic 006 estendido com 3 DELETEs novos (ver `3d`).

Detalhes de arquitetura: [epics/008-admin-evolution/](../epics/008-admin-evolution/) (spec + plan + research + data-model + contracts).

---

## 3f. Handoff Engine + Multi-Helpdesk (epic 010)

O epic 010 materializa o bit `conversations.ai_active` (antes declarado
mas inexistente, cf. comentario historico em
`db/queries/conversations.py:16` "not yet materialised") e introduz um
**Protocol `HelpdeskAdapter`** espelhando o padrao de `ChannelAdapter`
do epic 009. Resultado pratico: quando um atendente humano assume a
conversa no Chatwoot (ou digita direto do WhatsApp Business em tenants
sem helpdesk), o bot ProsaUAI silencia na mesma conversa — e retoma
automaticamente quando a conversa e resolvida ou apos timeout configuravel.

Arquitetura consolidada:

| Camada | Componente | Responsabilidade |
|--------|-----------|------------------|
| Schema | 6 colunas novas em `conversations` | `ai_active`, `ai_muted_reason`, `ai_muted_at`, `ai_muted_by_user_id`, `ai_auto_resume_at`, `external_refs JSONB` — tenant-scoped, herdam RLS |
| Schema | `public.handoff_events` (admin-only, ADR-027) | Append-only audit: `muted`/`resumed`/`admin_reply_sent`/`breaker_open`/`breaker_closed`; retention 90d |
| Schema | `public.bot_sent_messages` (admin-only, ADR-027) | Tracking 48h — NoneAdapter usa para evitar bot echo ao detectar `fromMe=true` |
| Code | `prosauai/handoff/` | Novo modulo: Protocol + registry + state + events + breaker + ChatwootAdapter + NoneAdapter + scheduler |
| Code | `api/webhooks/helpdesk/chatwoot.py` | Webhook inbound com HMAC + idempotency Redis + 2 event types (`conversation_updated` + `conversation_status_changed`) |
| Config | `tenants.yaml` — blocos `helpdesk.*` + `handoff.*` | Per-tenant: tipo de helpdesk, credenciais, mode (`off`/`shadow`/`on`), `auto_resume_after_hours`, `human_pause_minutes` |
| Admin UI | 3 endpoints + badges + composer | `POST /admin/conversations/{id}/{mute,unmute,reply}` — reply delega ao adapter para enviar mensagem via Chatwoot |
| Admin UI | Performance AI: 4 cards novos | Taxa de handoff, duracao media, breakdown por source, SLA breaches |
| Scheduler | 3 periodic tasks no lifespan | `handoff_auto_resume_cron` (60s) + `bot_sent_messages_cleanup_cron` (12h) + `handoff_events_cleanup_cron` (24h) — singleton via `pg_try_advisory_lock` |

Invariantes obrigatorios:

- **Advisory lock per-conversation** em toda transicao (`pg_advisory_xact_lock(hashtext(conversation_id))`) — serializa os 4 gatilhos possiveis (webhook, fromMe, manual, cron). Lock do cron (`handoff_resume_cron`) e **disjunto** do per-conversation — sem deadlock path.
- **Fire-and-forget** para `handoff_events` insert, push de private note e sync de assignee — NUNCA antes do commit do bit (ADR-028).
- **Ordenacao estrita**: commit DB → emissao evento → side effects.
- **Single source of truth**: Postgres `ai_active`. Router le direto do PG (amortizado no `customer_lookup`). Redis legacy key `handoff:{tenant}:{sender_key}` deprecated em PR-A, removida em PR-B apos 7d zero leituras.
- **Feature flag reload em <60s**: `config_poller` re-le `tenants.yaml` a cada 60s. Mudanca de `handoff.mode: on → off` reverte a feature em ate 1 minuto sem deploy.

ADRs novos:

- **ADR-036** — `ai_active` unified mute state (boolean single-bit, nao enum multi-step)
- **ADR-037** — HelpdeskAdapter pattern (Protocol + registry, espelha ADR-031 ChannelAdapter)
- **ADR-038** — fromMe auto-detection semantics (NoneAdapter `bot_sent_messages` + 10s tolerance + group skip)

Observabilidade (FR-051/052/053):

- Metricas Prometheus: `handoff_events_total{tenant, event_type, source, shadow}`, `handoff_shadow_events_total`, `handoff_duration_seconds{tenant, source}` (histogram), `helpdesk_webhook_latency_seconds{tenant, helpdesk}`, `helpdesk_breaker_open{tenant, helpdesk, reason}`. Emitidas via structlog facade (sem `prometheus_client` como dependencia nova).
- OTel baggage propaga de ponta-a-ponta: webhook inbound attacha `tenant_id`, `chatwoot_conversation_id`, `chatwoot_event_id`, `helpdesk_type`; `add_otel_context` processor le baggage e insere como top-level fields em todos os logs downstream (state.mute, adapter, persist_event).
- Logs structlog canonicos em todos os paths — `tenant_id`, `conversation_id`, `event_type`, `source`, `helpdesk_type`, `admin_user_id`.

Rollout gradual (FR-012):

1. Ariel: `off → shadow` (7d observacao) → `on` (48h validacao)
2. ResenhAI replica mesmo trajeto 7d depois

Shadow mode emite `handoff_events.shadow=true` mas NAO muta `ai_active` — permite medir "quantos mutes a pipeline teria feito" antes de confiar o real na producao (SC-012 ≤10% drift).

Detalhes de arquitetura: [epics/010-handoff-engine-inbox/](../epics/010-handoff-engine-inbox/) (spec + plan + research + data-model + contracts + decisions).

---

## 4. Concerns Transversais

### 4.1 Autenticacao & Autorizacao

| Aspecto | Mecanismo | ADR |
|---------|-----------|-----|
| Autenticacao tenant admin | Supabase Auth (JWT) — login email/password | — |
| Isolamento de dados | Pool + RLS com `SET LOCAL` por transacao | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |
| Wrapper RLS | `public.tenant_id()` STABLE SECURITY DEFINER — todas as policies usam. Em `public` para compatibilidade Supabase (schema `auth` e gerenciado pelo provider) | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/), [ADR-024](../decisions/ADR-024-schema-isolation/) |
| Indexes obrigatorios | `tenant_id` em toda tabela de dados, sem excecao | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |
| Service role key | Nunca exposta no frontend; apenas server-side | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |
| Tenant context | Sempre `SET LOCAL` (transaction-scoped), nunca `SET` global | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |

### 4.2 Seguranca & Safety

| Camada | Mecanismo | Latencia | ADR |
|--------|-----------|----------|-----|
| Hard limits | 20 tool calls/conversa, 60s timeout, 8K context tokens, 3 max retries | — | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Layer A — Regex | Blocklist, PII patterns (CPF, telefone, email), length checks | <5ms | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Layer B — ML classifier | DistilBERT injection detection + toxicity | ~50ms | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Layer C — LLM-as-judge | Semantic check em acoes destrutivas (tools high-risk only) | ~200ms | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Loop detection | Similaridade de pattern + semantic entre ultimas N respostas | — | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Prompt injection defense | Sandwich pattern (system → user → system), input sanitization, output scan | — | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Tool safety | Pydantic strict schema, whitelist enforcement, server-side tenant_id injection | — | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) |
| Webhook validation | X-Webhook-Secret per-tenant (constant-time compare) | — | — |

### 4.3 Secrets & Encryption

| Aspecto | Mecanismo | ADR |
|---------|-----------|-----|
| Vault | Infisical self-hosted (MIT license) | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Modelo de encryption | Envelope — KEK master + DEK por tenant | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao Evolution API keys | A cada 30 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao LLM keys | A cada 30 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao webhook secrets | A cada 90 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao DEK | A cada 180 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Rotacao JWT | A cada 90 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Runtime injection | Via pydantic-ai dependency injection — worker nunca ve raw keys | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Audit trail | Toda operacao (read/rotate/create/delete) com tenant_id, agent_id, IP, timestamp | [ADR-017](../decisions/ADR-017-secrets-management/) |
| Retencao audit | 365 dias | [ADR-017](../decisions/ADR-017-secrets-management/) |

### 4.4 Observabilidade

| Ferramenta | Papel | Integracao |
|------------|-------|------------|
| Phoenix (Arize) self-hosted | Tracing fim-a-fim da jornada de mensagens, waterfall UI, SpanQL queries | OTel SDK Python → OTLP gRPC :4317; Postgres backend (Supabase) |
| OpenTelemetry SDK | Auto-instrumentation (FastAPI, httpx, redis) + spans manuais de dominio | `configure_observability()` no lifespan; `prosauai.observability.*` |
| structlog + OTel bridge | Correlacao log↔trace: `trace_id`/`span_id` em todo log estruturado | Processor `add_otel_context` em shared_processors |
| DeepEval | Eval offline: faithfulness, relevance, toxicity, coherence | Batch jobs no worker; resultados em `eval_results` |
| Promptfoo | Regressao de prompts, red-teaming automatizado | CI/CD pipeline; roda contra prompt snapshots |
| `usage_events` | Metricas de consumo, latencia, custo por tenant | Supabase; particao mensal por `event_month` |
| Phoenix traces | Latencia p50/p95/p99 por span (webhook, route, debounce, echo) | Fire-and-forget via BatchSpanProcessor; API continua se Phoenix indisponivel |

> Detalhes: [ADR-020](../decisions/ADR-020-phoenix-observability.md) (supersedes [ADR-007](../decisions/ADR-007-langfuse-observability/)) | [ADR-008](../decisions/ADR-008-eval-stack/)

### 4.5 Multi-Tenancy

| Mecanismo | Descricao | ADR |
|-----------|-----------|-----|
| Rate limiting | Sliding window Redis por tenant por tier (Free=20, Starter=100, Growth=200, Business=500 RPM) | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| LLM spend caps | Bifrost daily cap por tier; throttle ao atingir cap | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| Queue priority | 3 niveis Redis Streams (high/normal/low) por tier; ratio 1:10 anti-starvation | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| Circuit breaker | Por tenant; threshold 50 erros/5min abre por 5min; half-open testing; DLQ para falhas | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| Concurrency limits | Free=5, Starter=20, Growth=50, Business=100 requests simultaneos | [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation/) |
| Data isolation | RLS policies + `SET LOCAL` em toda query | [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/) |
| Billing metering | `usage_events` com particao mensal; Stripe Metered Billing sync | [ADR-012](../decisions/ADR-012-consumption-billing/) |

### 4.6 Error Handling

| Cenario | Estrategia | Fallback |
|---------|------------|----------|
| LLM timeout/falha | 3 retries com backoff exponencial via Bifrost | Se falham: mensagem amigavel + handoff |
| Evolution API fora | 3 retries exponential backoff (1s → 4s → 16s) | Mensagem reenfileirada no Redis Stream; alerta admin |
| Redis desconectado | Reconnect automatico com exponential backoff | — |
| PG LISTEN/NOTIFY drop | Polling fallback a cada 5s | ARQ cron a cada 30min catch-up de eventos perdidos |
| Rate limit excedido | HTTP 429 + mensagem amigavel ao usuario WhatsApp | Fila de espera; mensagem processada quando slot disponivel |
| Circuit breaker aberto | Requests do tenant vao para DLQ | Half-open apos 5min; 1 request teste; sucesso = fecha |
| Tool execution falha | Retry 1x; se falha novamente, resposta sem tool + log | Alerta no Phoenix trace |
| Webhook HMAC invalido | Request rejeitado com 401 | Log de tentativa + alerta seguranca |
| Debounce flush avalanche | Jitter aleatorio 0-1s no TTL do Lua script (espalha flushes no tempo) | — |
| Worker overload (pico) | ARQ `max_jobs=20` limita batches concorrentes; `asyncio.Semaphore(10)` limita chamadas LLM | Batches excedentes ficam na fila Redis (sem perda); backpressure se fila > 100 jobs |

---

## 5. Qualidade & NFRs

| # | Cenario | Metrica | Target | Mecanismo | Prioridade |
|---|---------|---------|--------|-----------|------------|
| Q1 | Latencia resposta bot | p95 end-to-end (msg recebida → resposta enviada) | <3s | Debounce 3s + LLM streaming + Redis pipeline | Must |
| Q2 | Disponibilidade pipeline | Uptime mensal | 99.5% | Health checks, auto-restart, fallback LLM, DLQ | Must |
| Q3 | Isolamento tenant | Cross-tenant data leak | Zero | RLS + SET LOCAL + integration tests automatizados | Must |
| Q4 | Safety — injection bypass | Taxa de bypass das guardrails | <1% | 3-layer guardrails (regex + ML + LLM-as-judge) | Must |
| Q5 | Throughput Starter | Mensagens/min por tenant | 100 RPM | Redis sliding window rate limiting | Must |
| Q6 | Throughput Business | Mensagens/min por tenant | 500 RPM | Redis sliding window rate limiting | Must |
| Q7 | Custo LLM Starter | Cap diario por tenant | $5/dia | Bifrost spend tracking + throttle | Should |
| Q8 | Retencao automatica | Purge de dados expirados | <=90d default (config 30-365d) | Cron diario com cascade delete | Must |
| Q9 | SAR response (LGPD) | Tempo de resposta a requisicao do titular | <=15 dias | Endpoint dedicado `/api/v1/sar/{customer_id}` | Must |
| Q10 | Eval quality | Faithfulness score medio | >0.8 | DeepEval batch offline + alerta se cai abaixo | Should |
| Q11 | Guardrail latencia | Overhead de seguranca no pipeline | <260ms total (3 layers) | Layer A <5ms, B ~50ms, C ~200ms (so high-risk) | Should |
| Q12 | Secret rotation | Compliance de rotacao | 100% no prazo | Infisical rotation schedules automatizados | Must |
| Q13 | Routing rule evaluation | Latencia da resolucao de agente (M3 Fase B) | <10ms p99 | DB query + in-memory cache (TTL 30s) | Should |
| Q14 | Handoff webhook latency | p95 webhook Chatwoot → mute efetivo (epic 010) | <500ms | HMAC + idempotency Redis + advisory lock | Must |
| Q15 | Handoff rollback RTO | Tempo para desligar feature via tenants.yaml | <=60s | config_poller polling interval + hot reload | Must |

---

## 6. Mapa de Dados & Privacidade

### 6.1 Fluxo de Dados Pessoais

| Dado | Origem | Storage | Retention | PII? | Base Legal LGPD |
|------|--------|---------|-----------|------|-----------------|
| Mensagens (texto, audio, imagem) | Usuario WhatsApp | Supabase `messages` | 90d (config 30-365d) | Sim | Consentimento no 1o contato |
| Numero WhatsApp | Usuario WhatsApp | Supabase `customers.phone` | Vida do registro | Sim | Execucao de contrato |
| Phone hash | Pipeline | Supabase `customers.phone_hash` (SHA-256) | Vida do registro | Pseudonimizado | Legitimo interesse |
| Sessoes ativas | Pipeline processing | Redis (TTL 24h) | 24h auto-expire | Sim | Legitimo interesse |
| Embeddings knowledge base | Admin upload | Supabase pgvector `knowledge_chunks` | Permanente (ate delete manual) | Possivel | Consentimento do tenant |
| Phoenix traces | Pipeline observability | Supabase PG (schema `observability`) | 90d | Sim (referencia) | Legitimo interesse |
| Application logs | Todos os servicos | Log rotation local | 30d | Hash only | Legitimo interesse |
| Audit trail (seguranca) | Auth, admin actions, secret ops | Supabase `audit_log` | 365d | Sim | Obrigacao legal |
| Consent records | 1o contato WhatsApp | Supabase `user_consents` | Permanente | Sim | Obrigacao legal |

> PII em logs e traces: sempre SHA-256 hash do phone. Nunca plain text fora do BD principal. ([ADR-018](../decisions/ADR-018-data-retention-lgpd/))

### 6.2 Direitos do Titular (LGPD)

| Direito | Mecanismo | SLA | ADR |
|---------|-----------|-----|-----|
| Acesso (SAR) | Endpoint `/api/v1/sar/{customer_id}` — retorna metadata, conversas, knowledge_mentions, consents, metricas | 15 dias | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Exclusao | Cascade delete por `phone_hash`: mensagens → embeddings → traces (redact, nao delete) → cache Redis | 15 dias | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Consentimento | Mensagem de disclosure no 1o contato WhatsApp; opt-in explicito; re-consent se politica muda | Imediato | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Portabilidade | JSON export via mesmo SAR endpoint | 15 dias | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Revogacao | Sem consentimento = apenas respostas genericas, sem armazenamento | Imediato | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |

### 6.3 Compliance Checklist

| Item | Status | Nota |
|------|--------|------|
| Consent flow no 1o contato | Desenhado | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Retention cron automatico (diario) | ✅ Implementado | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) — `prosauai/ops/retention.py` + container `retention-cron` (epic 006) |
| SAR endpoint | Desenhado | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) — 15 dias SLA |
| PII detection pre-LLM | Desenhado | [ADR-016](../decisions/ADR-016-agent-runtime-safety/) — Layer A regex |
| Encryption at rest | Supabase managed | Transparente via provider |
| Encryption in transit (TLS) | Todas conexoes HTTPS/TLS | Inclui Redis TLS em producao |
| HMAC webhook validation | Desenhado | [ADR-017](../decisions/ADR-017-secrets-management/) — SHA-256 por tenant |
| Envelope encryption secrets | Desenhado | [ADR-017](../decisions/ADR-017-secrets-management/) — KEK + DEK |
| Proibicao fine-tuning sem consent | Politica | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |
| Proibicao cross-tenant embedding | Politica | [ADR-018](../decisions/ADR-018-data-retention-lgpd/) |

---

## 7. Glossario

| Termo | Definicao | Dominio |
|-------|-----------|---------|
| **Tenant** | Empresa/negocio que usa ProsaUAI. Isolamento completo de dados, config e billing | Plataforma |
| **Pipeline** | Sequencia de 14 modulos (M1-M14) que processa cada mensagem recebida | Core |
| **Handoff** | Transferencia de conversa do agente IA para atendente humano, com maquina de estados | Atendimento |
| **Guardrails** | Filtros de seguranca pre/pos-LLM que bloqueiam conteudo indesejado (3 layers) | Seguranca |
| **Debounce** | Agrupamento de mensagens rapidas (janela 3s + jitter 0-1s via Redis Lua) numa unica request. Jitter previne avalanche de flushes simultaneos sob pico | Core |
| **Cooldown** | Tempo minimo entre mensagens proativas para o mesmo cliente (evitar spam) | Triggers |
| **Bounded Context** | Area logica do sistema com fronteiras definidas (DDD). 5 contextos no ProsaUAI | Arquitetura |
| **ACL** | Anti-Corruption Layer — isola integracao com sistemas externos, traduzindo formatos | Arquitetura |
| **Bifrost** | Proxy LLM em Go — centraliza rate limiting, cost tracking | Infra |
| **Evolution API** | Gateway WhatsApp self-hosted (cloud mode) — conecta ProsaUAI ao WhatsApp sem BSP | Integracao |
| **Phoenix (Arize)** | Observabilidade: tracing fim-a-fim, waterfall UI, SpanQL queries. Self-hosted, Postgres backend. Substitui LangFuse ([ADR-020](../decisions/ADR-020-phoenix-observability.md)) | Observabilidade |
| **CSAT** | Customer Satisfaction Score (1-5) coletado apos atendimento humano | Metricas |
| **Channel Adapter** | Interface padrao que abstrai canal de mensageria. Novo canal = novo adapter, zero mudanca no core | Arquitetura |
| **Tool Registry** | Catalogo central de tools com metadata (nome, params, categoria). Alimenta admin e valida configs | Arquitetura |
| **Routing Rule** | Mapeamento configuravel de (phone_number, match_conditions) → agent_id. Avaliado pelo Smart Router (M3) em priority order. Sem regra = tenant default | Routing |
| **Pipeline Step** | Etapa configuravel de processamento dentro de um agente (classifier, clarifier, resolver, specialist). Zero steps = single LLM call (backward compatible) | Orquestracao |
| **Context Window** | Sliding window das ultimas N mensagens (default 10) mantidas verbatim no conversation state. Apos threshold (default 20 exchanges), async summarization comprime mensagens mais antigas | Memoria |
| **Infisical** | Secret manager open-source (MIT). Envelope encryption (KEK + DEK por tenant) | Seguranca |
| **DLQ** | Dead Letter Queue — fila de mensagens que falharam apos max retries, para reprocessamento manual | Infra |
| **Circuit Breaker** | Padrao que isola tenant com alta taxa de erro, evitando cascata para outros tenants | Resiliencia |
| **Sandwich Pattern** | Defesa contra prompt injection: system prompt antes e depois do input do usuario | Seguranca |
| **SAR** | Subject Access Request — requisicao do titular de dados (LGPD Art. 18) | Compliance |
| **RPM** | Requests Per Minute — metrica primaria de rate limiting por tenant | Metricas |

---

## 8. Multi-Tenant Topology — Faseamento

A arquitetura multi-tenant nao e binaria. Tres fases progressivas, cada uma com escopo bem definido e trigger explicito de entrada.

### Fase 1 — Fundacao Estrutural (epic 003)

**Topologia:**

```mermaid
graph LR
    Tailscale[/"Tailscale<br/>(dev)"/] -->|"100.x.x.x:8050<br/>(dev only)"| API
    DockerNet[/"Docker network<br/>pace-net (prod)"/] -->|"http://api:8050<br/>(internal DNS)"| API
    Evolution_Ariel[/"Evolution Ariel<br/>(Pace internal)"/] -->|"webhook + X-Webhook-Secret"| Tailscale
    Evolution_Resenha[/"Evolution ResenhAI<br/>(Pace internal)"/] -->|"webhook + X-Webhook-Secret"| Tailscale

    subgraph ProsauAI_API ["prosauai-api :8050"]
        TR[TenantResolver]
        Auth[Auth dep<br/>X-Webhook-Secret]
        Idem[Idempotency<br/>Redis SETNX]
        Parser[Parser v2.3.0]
        Router[Router 6 paths]
        Debounce[Debounce<br/>buf:tenant_id:*]
        EvoP[EvolutionProvider<br/>per-tenant credentials]
    end

    API[ProsauAI API] --> TR
    TR --> Auth
    Auth --> Idem
    Idem --> Parser
    Parser --> Router
    Router --> Debounce
    Debounce --> EvoP
    EvoP -.->|"echo back<br/>tenant.evolution_api_url"| Evolution_Ariel
    EvoP -.->|"echo back<br/>tenant.evolution_api_url"| Evolution_Resenha
```

**Caracteristicas:**
- TenantStore file-backed YAML, lifespan carrega no startup
- 2 tenants reais (Ariel + ResenhAI) operando em paralelo
- Idempotencia per-tenant (`seen:{tenant_id}:{message_id}` Redis SETNX 24h TTL)
- Debounce keys per-tenant (`buf:/tmr:{tenant_id}:{sender_key}:{ctx}`)
- Auth via `X-Webhook-Secret` constant-time compare
- Deploy isolado por rede: Tailscale (dev) + Docker network privada (prod)
- **Zero porta exposta na internet publica.**

**O que NAO existe:** Caddy publico, admin API, rate limit per-tenant, billing.

**ADRs novas envolvidas:** nenhuma (refactor estrutural, sem decisao 1-way-door).

### Fase 2 — Public API (epic 012)

**Topologia (delta vs Fase 1):**

```mermaid
graph LR
    Internet((Internet)) -->|"HTTPS :443<br/>api.prosauai.com"| Caddy
    Caddy -->|"TLS terminated<br/>+ rate limit per IP"| API
    AdminAPI[Admin API<br/>POST /admin/tenants] --> TS_File[TenantStore<br/>tenants.yaml hot-reload]

    Caddy[/"Caddy 2<br/>:80, :443"/]
    API[ProsauAI API :8050]

    AdminClient[/"Admin Client<br/>(master token)"/] --> Caddy
    Caddy --> AdminAPI

    Evolution_Cliente[/"Evolution<br/>(cliente externo)"/] -->|"webhook + secret"| Caddy
```

**Mudancas vs Fase 1:**
- Caddy 2 alpine container na frente, expondo `:80` + `:443` (Let's Encrypt automatico)
- ProsauAI API continua sem `ports:` no docker-compose — **so Caddy fala com a internet**
- Admin API: novo modulo `prosauai/api/admin.py` com endpoints `POST/GET/PATCH/DELETE /admin/tenants`
- Auth admin via master token estatico no header `X-Admin-Token` (futuro: JWT scoped per-org)
- Hot reload do TenantStore: file watcher (inotify) ou endpoint `POST /admin/tenants/reload` — sem restart
- Rate limiting per-tenant em duas camadas: (a) Caddy `rate_limit` por IP global; (b) Redis sliding window per-tenant integrado com Bifrost spend caps (ja documentado em [ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation.md))
- Metricas basicas per-tenant expostas via `/admin/metrics` (requests/s, errors, debounces flushed)

**ADRs novas envolvidas:** [ADR-021](../decisions/ADR-021-caddy-edge-proxy.md) (Caddy), [ADR-022](../decisions/ADR-022-admin-api.md) (Admin API).

**Storage:** ainda YAML — Postgres so na Fase 3.

### Fase 3 — Operacao (epic 013)

**Topologia (delta vs Fase 2):**

```mermaid
graph LR
    AdminAPI[Admin API] --> Postgres[(TenantStore<br/>Postgres + RLS)]
    Postgres -->|"audit_log"| AuditTable[(audit_log)]
    API[ProsauAI API] --> CB[Circuit Breaker<br/>per-tenant]
    CB -->|"open: DLQ"| DLQ[(DLQ Redis Stream)]
    API --> Bifrost[Bifrost LLM proxy<br/>spend cap per-tenant]
    Bifrost --> Stripe[Stripe billing]
    API --> Prometheus[Prometheus]
    Prometheus --> Grafana[Grafana dashboards]
    Grafana -->|"alerts"| PagerDuty[PagerDuty]

    Postgres -.->|"migrated from<br/>tenants.yaml"| YAMLLegacy[/"tenants.yaml<br/>(deprecated)"/]
```

**Mudancas vs Fase 2:**
- TenantStore migrado de YAML para Postgres (schema gerenciado em Supabase, RLS herdada do [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant.md))
- `audit_log` table: append-only, registra todas operacoes administrativas (quem criou/editou/disabilitou cada tenant)
- Circuit breaker per-tenant ([ADR-015](../decisions/ADR-015-noisy-neighbor-mitigation.md)): tenant doente vai pra DLQ, half-open apos 5min
- Billing/usage tracking automatizado via Bifrost spend metrics + Stripe ([ADR-012](../decisions/ADR-012-consumption-billing.md))
- Alertas Prometheus per-tenant (requests/s, error rate, queue depth, spend approaching cap)
- Backup/restore: pg_dump scheduled + secrets via [Infisical](../decisions/ADR-017-secrets-management.md)
- Migracao YAML → Postgres feita uma unica vez, com cutover ([ADR-023](../decisions/ADR-023-tenant-store-postgres-migration.md))

**ADR nova envolvida:** [ADR-023](../decisions/ADR-023-tenant-store-postgres-migration.md) (trigger e migration plan).

**Trigger de entrada:** dor operacional real, nao antes. Threshold objetivo: >=5 tenants em producao OU primeiro incidente de noisy neighbor mensuravel.

### Sintese — comparativo das fases

| Aspecto | Fase 1 (epic 003) | Fase 2 (epic 012) | Fase 3 (epic 013) |
|---------|------------------|------------------|------------------|
| **Tenant storage** | YAML file | YAML file (hot reload) | Postgres + RLS |
| **Edge proxy** | Nao | Caddy 2 + Let's Encrypt | Caddy 2 + Let's Encrypt |
| **Porta publica** | Nenhuma (Tailscale dev / Docker network prod) | 80 + 443 (Caddy) | 80 + 443 (Caddy) |
| **Admin API** | Nao | `POST/GET/PATCH/DELETE /admin/tenants` (master token) | + JWT scoped per-org + audit log |
| **Rate limit per-tenant** | Nao | Redis sliding window + Bifrost spend cap | + Circuit breaker + DLQ per-tenant |
| **Billing** | Nao | Manual (planilha) | Stripe automatizado |
| **Alertas** | Nao | Manual (sem Prometheus) | Prometheus + Grafana + PagerDuty |
| **Onboarding** | Manual interno | Vendas + Admin API + onboarding doc | Self-service via Stripe checkout |
| **Estimativa** | ~1 semana (epic 003) | ~2 semanas (epic 012) | ~3 semanas (epic 013) |
| **Trigger entrada** | Bloqueio do servico em prod real | Primeiro cliente externo pagante | >=5 tenants OU dor operacional mensuravel |

---

> **Proximo passo:** `/madruga:domain-model prosauai` — modelar bounded contexts, aggregates e invariantes.
