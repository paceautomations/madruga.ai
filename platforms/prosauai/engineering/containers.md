---
title: "Containers"
updated: 2026-04-13
sidebar:
  order: 4
---
# ProsaUAI — Container Architecture (C4 Level 2)

> C4 Level 2: containers, responsabilidades e comunicacao entre componentes.
>
> BCs e aggregates → ver [domain-model.md](../domain-model/) · Integracoes externas → ver [integrations.md](../integrations/)

---

## Container Diagram

```mermaid
graph LR
    %% Actors
    agent(("Agente WhatsApp"))
    admin_user(("Admin / Operador"))

    subgraph prosauai ["ProsaUAI Platform"]
        subgraph prosauai_api ["prosauai-api :8050"]
            api_webhook["Webhook receiver<br/><small>X-Webhook-Secret per-tenant</small>"]
            api_rest["REST endpoints<br/><small>/api/v1/*</small>"]
            api_socketio["Socket.io gateway<br/><small>realtime push</small>"]
        end

        subgraph prosauai_worker ["prosauai-worker"]
            wk_debounce["Debounce flush<br/><small>Redis Lua 3s + jitter</small>"]
            wk_llm["LLM orchestration<br/><small>via Bifrost proxy</small>"]
            wk_delivery["Delivery + retry<br/><small>3x backoff</small>"]
            wk_eval["Eval batch jobs<br/><small>DeepEval offline</small>"]
            wk_trigger["Trigger evaluator<br/><small>PG LISTEN/NOTIFY</small>"]
        end

        subgraph prosauai_admin ["prosauai-admin :3000"]
            adm_dash["Dashboard<br/><small>metricas por tenant</small>"]
            adm_conv["Conversation viewer<br/><small>realtime via Socket.io</small>"]
            adm_prompt["Prompt manager<br/><small>versionamento</small>"]
            adm_handoff["Handoff queue<br/><small>fila de atendimento</small>"]
        end
    end

    subgraph storage ["Storage"]
        redis["Redis 7<br/><small>arq: buf: cache: ps:</small>"]
        supabase-prosauai[("Supabase ProsaUAI<br/><small>PG 15 + pgvector + RLS</small>")]
    end

    subgraph llm_proxy ["LLM Proxy"]
        bifrost["Bifrost :8080<br/><small>Go — rate limit + fallback</small>"]
    end

    subgraph observability ["Observability"]
        phoenix["Phoenix (Arize) :6006<br/><small>OTel traces + UI</small>"]
    end

    subgraph external ["External Services"]
        evolution-api["Evolution API<br/><small>WhatsApp gateway</small>"]
        supabase-resenhai[("Supabase ResenhAI<br/><small>PG 15 read-only</small>")]
        openai-gpt-mini["OpenAI GPT mini<br/><small>classification + generation</small>"]
        infisical["Infisical<br/><small>secrets vault</small>"]
    end

    %% Actor → Platform
    agent -- "HTTPS" --> api_webhook
    evolution-api -- "webhook POST<br/>X-Webhook-Secret" --> api_webhook
    admin_user -- "HTTPS + JWT" --> prosauai_admin

    %% API internal
    api_webhook -- "XADD stream:messages" --> redis
    api_webhook -- "SET dedup message_id<br/>TTL 24h" --> redis
    api_rest -- "asyncpg SQL" --> supabase-prosauai
    api_socketio -- "WebSocket" --> adm_conv

    %% Admin → API
    prosauai_admin -- "REST /api/v1/*" --> api_rest
    prosauai_admin -- "Supabase JS client<br/>Auth + queries" --> supabase-prosauai

    %% Redis → Worker
    redis -- "XREADGROUP<br/>BLOCK 5000ms" --> wk_debounce

    %% Worker processing
    wk_debounce -- "BufferedBatch" --> wk_llm
    wk_llm -- "POST /v1/chat/completions" --> bifrost
    wk_llm -- "asyncpg SQL" --> supabase-prosauai
    wk_llm -- "asyncpg read-only" --> supabase-resenhai
    wk_delivery -- "POST sendText" --> evolution-api
    wk_delivery -- "PUBLISH ps:events" --> redis
    wk_eval -. "HTTPS SDK<br/>fire-and-forget" .-> phoenix

    %% OTel traces → Phoenix
    prosauai_api -. "OTLP gRPC :4317<br/>fire-and-forget" .-> phoenix
    phoenix -- "asyncpg SQL" --> supabase-prosauai
    wk_trigger -- "SDK secret read<br/>cached 5min" --> infisical

    %% PG events → Worker
    supabase-prosauai -. "PG LISTEN/NOTIFY<br/>games, group_members" .-> wk_trigger

    %% Bifrost → LLMs
    bifrost -- "OpenAI API" --> openai-gpt-mini
```

---

## Container Matrix

<!-- Tech choices justified in Blueprint — list technology here without justification -->

| # | Container | Bounded Context | Tecnologia | Responsabilidade | Protocol In | Protocol Out |
|---|-----------|----------------|------------|------------------|-------------|-------------|
| 1 | prosauai-api :8050 | Channel | Python 3.12 + FastAPI | Webhook receiver, REST endpoints, Socket.io gateway | HTTPS (webhook, REST) | Redis keys, Socket.io, asyncpg |
| 2 | prosauai-worker | Conversation, Safety, Operations | Python 3.12 + ARQ | Debounce (Lua 3s + jitter), LLM orchestration (semaphore cap), delivery, eval, triggers. Concurrency: `max_jobs=20`, `llm_semaphore=10`, backpressure at queue depth > 100 | Redis Streams (XREADGROUP) | asyncpg, HTTP (Bifrost, Evolution), OTLP gRPC (Phoenix) |
| 3 | prosauai-admin | — (apresentacao) | Next.js 15 + shadcn/ui | Dashboard, conversation viewer, prompt manager, handoff queue | HTTPS + JWT | REST API, Supabase JS |
| 4 | Redis 7 | — (infra) | Redis | Message streams, cache, PubSub, debounce state | Redis protocol | Redis protocol |
| 5 | Supabase ProsaUAI | — (infra) | PG 15 + pgvector + RLS | Persistent state multi-tenant | asyncpg SQL, Supabase JS | PG LISTEN/NOTIFY |
| 6 | Bifrost :8080 | — (proxy) | Go binary | LLM proxy: rate limit, cost tracking | HTTP POST | OpenAI API |
| 7 | Phoenix (Arize) | Observability | Docker (self-hosted) | Tracing fim-a-fim (OTel spans), waterfall UI, SpanQL queries. Postgres backend (Supabase) | OTLP gRPC :4317 | asyncpg SQL (Supabase) |
| 8 | Infisical | — (infra) | Docker (self-hosted) | Secrets vault: envelope encryption, rotation | HTTPS REST SDK | — |
| 9 | Evolution API | Channel | Cloud mode (managed) | WhatsApp gateway: send/receive messages | HTTP POST (sendText) | Webhook POST |
| 10 | Netdata :19999 | — (infra) | Docker (self-hosted) | Host monitoring: CPU, RAM, disco, containers Docker. Dashboard web. Bind `127.0.0.1` only (acesso via SSH tunnel) | — | HTTP :19999 (dashboard) |
| 11 | retention-cron | Operations | Python 3.12 (same image as API) | Purge diario de dados expirados: DROP PARTITION (messages), batch DELETE (conversations, eval_scores, traces). LGPD compliance | asyncpg SQL | Logs (structlog JSON) |

---

## Communication Protocols

| De | Para | Protocolo | Padrao | Justificativa |
|----|------|-----------|--------|---------------|
| Evolution API | prosauai-api | HTTPS webhook (X-Webhook-Secret) | async | WhatsApp messages inbound |
| prosauai-api | Redis | XADD stream:messages | async | Desacoplamento intake → processing |
| prosauai-api | prosauai-admin | Socket.io WebSocket | async (push) | Realtime updates (new messages, handoff alerts) |
| Redis | prosauai-worker | XREADGROUP (BLOCK 5000ms) | async (pull) | Consumer group permite horizontal scaling |
| prosauai-worker | Bifrost | POST /v1/chat/completions | sync | LLM request-response |
| prosauai-worker | Supabase ProsaUAI | asyncpg SQL | sync | CRUD + RLS per transaction |
| prosauai-worker | Evolution API | POST sendText/{instance} | sync | Envio de resposta ao WhatsApp |
| prosauai-api | Phoenix (Arize) | OTLP gRPC :4317 | async (fire-and-forget) | Tracing OTel spans via BatchSpanProcessor — API continua se Phoenix indisponivel |
| prosauai-worker | Infisical | HTTPS REST SDK (cached 5min) | sync | Secret retrieval |
| Supabase ProsaUAI | prosauai-worker | PG LISTEN/NOTIFY | async (event-driven) | Triggers proativos (games, group_members) |
| prosauai-admin | prosauai-api | REST /api/v1/* | sync | CRUD operations |
| Bifrost | OpenAI GPT mini | OpenAI API | sync | LLM inference |

---

## Scaling Strategy

| Container | Estrategia | Trigger | Notas |
|-----------|-----------|---------|-------|
| prosauai-api | Horizontal | CPU > 70% ou latencia p95 > 500ms | Stateless — qualquer instancia serve |
| prosauai-worker | Horizontal | Queue depth > 100 msgs | Redis consumer groups distribui carga. Cada instancia: `max_jobs=20` (ARQ), `llm_semaphore=10` (asyncio), backpressure se fila > 100. Jitter 0-1s no Lua TTL previne avalanche de flushes |
| prosauai-admin | Horizontal | Usuarios concorrentes > 100 | Stateless Next.js |
| Redis | Single + Sentinel | — | HA via Sentinel; vertical para throughput |
| Supabase | Vertical (managed) | Conexoes > 80% pool | Managed pelo provider. Tabela `messages` particionada mensalmente — purge via DROP PARTITION (<100ms). Partition pruning em queries com filtro `created_at`. Crescimento sustentavel ~365K msgs/ano |
| Bifrost | Horizontal | RPM > 1000 | Stateless Go proxy |
| Phoenix (Arize) | Single instance | — | Tracing nao e critico para pipeline. Postgres backend (Supabase) |
| Infisical | Single instance | — | Cache 5min no client reduz load |
| Netdata | Single instance | — | Temporario (epic 013 substitui por Prometheus+Grafana). mem_limit 256m |
| retention-cron | Single instance | — | Execucao diaria (sleep 86400). mem_limit 128m. Idempotente |

> NFRs globais e targets mensuraveis → ver [blueprint.md](../blueprint/)

---

## Implementation Status

> O diagrama e a Container Matrix acima representam a **arquitetura target**. A tabela abaixo reflete o estado real de cada container apos os epics implementados.

| Container | Status | Epic | Notas |
|-----------|--------|------|-------|
| prosauai-api | ✅ Operacional | 001-006 | Webhook + health + debounce + multi-tenant auth (X-Webhook-Secret) + MECE router + idempotency + **conversation pipeline 12-step** (customer lifecycle, context window, intent classifier, LLM agent pydantic-ai, safety guards 3-layer, tool registry, evaluator) + **DB migrations** (7 files, asyncpg pool, RLS on all tables) + **schema isolation** (`prosauai` + `prosauai_ops`). OTel SDK + structlog bridge. Port 8050. **Nota:** LLM orchestration atualmente roda inline na API (sem worker separado) |
| prosauai-worker | ⏳ Planejado (arquitetura target) | — | Arquitetura target: LLM orchestration, delivery, eval batch e triggers migram para ARQ worker com Redis Streams consumer groups. **Atualmente:** toda logica de conversacao roda inline no prosauai-api. Migracao para worker planejada quando throughput exigir scaling independente |
| prosauai-admin | ⏳ Planejado | — | — |
| Redis 7 | ✅ Operacional | 001-004 | Debounce keys (buf:/tmr:) + keyspace notifications + idempotency (seen:tenant_id:msg_id SETNX 24h) |
| Supabase ProsaUAI | ✅ Schema isolation | 005-006 | Schema `prosauai` (7 tabelas de negocio) + `prosauai_ops` (schema_migrations). `public.tenant_id()` SECURITY DEFINER (Supabase compat — movido de `prosauai_ops`). `gen_random_uuid()` built-in (sem `uuid-ossp`). Messages particionada por mes. Migrations idempotentes com `DROP POLICY IF EXISTS`. Migration runner asyncpg automatizado no startup (advisory lock + checksum). Pool: `statement_cache_size=0` (Supavisor compat), JSONB codec auto. [ADR-024](../decisions/ADR-024-schema-isolation.md) |
| Bifrost | ⏳ Planejado | — | — |
| Phoenix (Arize) | ✅ Operacional | 002, 006 | Substitui LangFuse ([ADR-020](../decisions/ADR-020-phoenix-observability.md)). UI :6006 + gRPC :4317. SQLite em dev, Postgres backend em prod (`PHOENIX_SQL_DATABASE_SCHEMA=observability`) |
| Infisical | ⏳ Planejado | — | Config via .env nesta fase |
| Evolution API | ✅ Integrado | 001 | Cloud mode, mock em testes |
| TenantStore (file) | ✅ Operacional | 003 | YAML file-backed, lifespan loader, ${VAR} interpolation, 2 tenants reais (Ariel + ResenhAI). Migracao para Postgres em [ADR-023](../decisions/ADR-023-tenant-store-postgres-migration.md) |
| Router MECE | ✅ Operacional | 004 | classify() pure + RoutingEngine declarativa + config YAML per-tenant (config/routing/*.yaml) + MECE verification (4 camadas) + MentionMatchers (3 estrategias) |
| Netdata | ✅ Operacional (prod) | 006 | Host monitoring temporario (substitui por Prometheus+Grafana no epic 013). Bind `127.0.0.1:19999`, mem_limit 256m. Acesso via SSH tunnel |
| retention-cron | ✅ Operacional (prod) | 006 | Purge diario LGPD: DROP PARTITION messages, batch DELETE conversations/eval_scores/traces. mem_limit 128m. `--dry-run` default |
| Caddy 2 (edge proxy) | 📋 Planejado | 012 (Fase 2) | TLS automatico via Let's Encrypt; reverse proxy para prosauai-api; rate limit por IP. Ver [ADR-021](../decisions/ADR-021-caddy-edge-proxy.md) |
| Admin API | 📋 Planejado | 012 (Fase 2) | Endpoints `POST/GET/PATCH/DELETE /admin/tenants`; auth via master token. Ver [ADR-022](../decisions/ADR-022-admin-api.md) |
| TenantStore (Postgres) | 📋 Planejado | 013 (Fase 3) | Migracao YAML → Postgres; schema gerenciado em Supabase com RLS herdada de [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant.md). Trigger: >=5 tenants reais |

---

## Multi-Tenant Topology — Faseamento

A arquitetura multi-tenant evolui em 3 fases. Cada fase tem trigger de entrada explicito; nenhuma e antecipada sem dor real para evita-la.

### Fase 1 — Multi-tenant estrutural (epic 003, shipped)

**Topologia:** prosauai-api isolado por rede (Tailscale dev / Docker network privada prod), TenantStore file-backed YAML, 2 tenants reais (Ariel + ResenhAI), per-tenant credentials/keys/idempotency. **Zero porta exposta na internet.**

```mermaid
graph LR
    subgraph dev ["Dev (Tailscale)"]
        Tail[/"Tailscale<br/>100.x.x.x:8050"/]
    end
    subgraph prod_p1 ["Prod Fase 1 (Docker network)"]
        DockerNet[/"pace-net<br/>internal DNS<br/>http://api:8050"/]
    end

    EvoAriel[/"Evolution Ariel"/] -->|"webhook + X-Webhook-Secret"| Tail
    EvoResenha[/"Evolution ResenhAI"/] -->|"webhook + X-Webhook-Secret"| Tail
    Tail --> API_F1[ProsauAI API :8050]
    DockerNet --> API_F1
    API_F1 --> Redis_F1[Redis<br/>buf:tenant_id:*<br/>seen:tenant_id:*]
    API_F1 --> TenantYAML[/"config/tenants.yaml<br/>(file-backed)"/]
    API_F1 -.->|"echo per-tenant"| EvoAriel
    API_F1 -.->|"echo per-tenant"| EvoResenha
```

**Containers novos:** nenhum — refactor estrutural do `prosauai-api` existente.

**Containers que mudam:**
- `prosauai-api`: lifespan carrega `TenantStore.load_from_file()`; novo modulo `core/tenant.py`, `core/tenant_store.py`, `core/idempotency.py`; `api/dependencies.py` reescrito (sem HMAC); `formatter.py` reescrito (12 correcoes).
- `Redis 7`: chaves prefixadas com `tenant_id` (debounce + idempotency); zero impacto operacional.

### Fase 2 — Public API (epic 012)

**Topologia (delta):** Caddy 2 como edge proxy + Admin API. ProsauAI API continua sem `ports:` — so Caddy fala com a internet.

```mermaid
graph LR
    Internet((Internet)) -->|"HTTPS :443<br/>api.prosauai.com"| Caddy_F2[/"Caddy 2<br/>:80, :443"/]
    Caddy_F2 -->|"reverse_proxy<br/>internal Docker network"| API_F2[ProsauAI API :8050]
    API_F2 --> AdminAPI[/"Admin API<br/>POST /admin/tenants"/]
    AdminClient[/"Admin Client<br/>(master token)"/] -->|"X-Admin-Token"| Caddy_F2
    EvoCliente[/"Evolution<br/>(cliente externo)"/] -->|"webhook + X-Webhook-Secret"| Caddy_F2
    AdminAPI --> TenantYAML_F2[/"tenants.yaml<br/>(hot reload via watcher)"/]
    API_F2 --> RedisRL[Redis<br/>rate:tenant_id:*<br/>per-tenant sliding window]
```

**Containers novos:**
- `caddy` (Caddy 2 alpine) — edge proxy + TLS automatico Let's Encrypt + rate limit por IP.

**Containers que mudam:**
- `prosauai-api`: novo modulo `prosauai/api/admin.py` com endpoints CRUD de tenants; auth via master token; hot reload do TenantStore via inotify ou endpoint dedicado.
- `Redis 7`: novas chaves para rate limiting (`rate:{tenant_id}:msgs`).
- `docker-compose.prod.yml`: adiciona Caddy + volumes `caddy-data` (certs).

**ADRs novos:** [ADR-021](../decisions/ADR-021-caddy-edge-proxy.md), [ADR-022](../decisions/ADR-022-admin-api.md).

### Fase 3 — Operacao em Producao (epic 013)

**Topologia (delta):** TenantStore migrado para Postgres (Supabase + RLS); circuit breaker per-tenant; billing automatizado; alertas Prometheus.

```mermaid
graph LR
    AdminAPI[Admin API] --> Postgres_F3[("TenantStore Postgres<br/>schema observability +<br/>schema admin")]
    Postgres_F3 -->|"audit_log"| Audit[(audit_log)]
    Postgres_F3 -->|"RLS policies"| RLS[Row-Level Security]
    API_F3[ProsauAI API] --> CB[Circuit Breaker<br/>per-tenant state]
    CB -->|"open: route to DLQ"| DLQ[(DLQ Redis Stream)]
    API_F3 --> Bifrost[Bifrost LLM proxy<br/>spend cap per-tenant]
    Bifrost --> Stripe[Stripe billing]
    API_F3 --> Prom[Prometheus]
    Prom --> Grafana[Grafana dashboards]
    Grafana -->|"alerts"| Pager[PagerDuty]

    Postgres_F3 -.->|"migrated from"| YAMLLegacy[/"tenants.yaml<br/>(deprecated)"/]
```

**Containers novos:**
- `prometheus` + `grafana` (single instance cada, observabilidade operacional).
- `bifrost` finalmente promovido de "planejado" para "operacional" (ja documentado em [ADR-002](../decisions/ADR-002-bifrost-llm-proxy.md)).

**Containers que mudam:**
- `prosauai-api`: TenantStore agora usa `TenantStore.load_from_db()` (mesmo interface, loader diferente); circuit breaker module novo; integracao Stripe webhook handler.
- `Supabase ProsaUAI`: novas tables `tenants`, `audit_log`; RLS policies herdam padrao do [ADR-011](../decisions/ADR-011-pool-rls-multi-tenant.md).

**ADR novo:** [ADR-023](../decisions/ADR-023-tenant-store-postgres-migration.md) (trigger e migration plan one-shot).

### Sintese — comparativo das fases

| Container | Fase 1 (epic 003) | Fase 2 (epic 012) | Fase 3 (epic 013) |
|-----------|------------------|------------------|------------------|
| **prosauai-api** | TenantStore file + per-tenant keys + parser corrigido | + Admin API + hot reload + rate limit | + circuit breaker + Stripe handler |
| **Redis 7** | `buf:/tmr:/seen:` prefixados por tenant_id | + `rate:` per-tenant | + DLQ stream per-tenant |
| **TenantStore** | YAML file (gitignored) | YAML file (hot reload) | Postgres + RLS + audit |
| **Caddy 2** | — | Edge proxy + Let's Encrypt | Edge proxy + Let's Encrypt |
| **Admin API** | — | `POST/GET/PATCH/DELETE /admin/tenants` (master token) | + JWT scoped + audit log |
| **Bifrost** | ⏳ Planejado | ⏳ Planejado | ✅ Operacional + spend cap per-tenant |
| **Prometheus + Grafana** | — | — | Operacional + alertas PagerDuty |
| **Stripe** | — | — | Operacional + webhook handler |
| **Porta publica** | 0 | 80 + 443 (so Caddy) | 80 + 443 (so Caddy) |

---

## Premissas e Decisoes

| # | Decisao | Alternativas Consideradas | Justificativa |
|---|---------|---------------------------|---------------|
| 1 | Separar API e Worker em containers distintos | Monolito com threads — rejeitado: scaling independente necessario | Worker processa LLM (lento), API precisa ser rapida para webhooks |
| 2 | Redis como message broker (nao RabbitMQ/Kafka) | RabbitMQ — rejeitado: overhead operacional. Kafka — overkill para ~500 RPM | Redis Streams cobre consumer groups + DLQ + backpressure |
| 3 | Bifrost como proxy LLM separado | SDK direto no worker — rejeitado: rate limiting centralizado + fallback chain | Go binary leve, stateless, horizontal |
| 4 | Next.js para admin (nao React SPA) | SPA puro — rejeitado: SSR melhora SEO/perf para dashboards | Next.js 15 + shadcn/ui — produtividade alta |

---

> **Proximo passo:** `/madruga:context-map prosauai` — mapear relacionamentos DDD entre bounded contexts.
