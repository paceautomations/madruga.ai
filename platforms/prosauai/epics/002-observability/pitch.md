---
id: "002"
title: "Observability — Tracing total da jornada de mensagem"
status: shipped
phase: now
features:
  - "Trace fim-a-fim por mensagem (webhook → router → debounce → echo)"
  - "Dashboards de funil por rota, latência p50/p95/p99, failure modes"
  - "Correlação log↔trace (trace_id em todo log estruturado)"
  - "Forward-compat para LLM tracing no epic 003 (pydantic-ai + Bifrost)"
  - "Sync documental (D0): aplicar 12 propostas pendentes do reconcile do epic 001"
owner: ""
created: 2026-04-10
updated: 2026-04-10
target: ""
outcome: ""
arch:
  modules: [M14]
  contexts: [observability, channel, conversation]
  containers: [prosauai-api, redis, phoenix, supabase-prosauai]
delivered_at: 2026-04-10
---

# 002 — Observability — Tracing total da jornada de mensagem

## Escopo Arquitetural

| Camada | Blocos | Viewer |
|--------|--------|--------|
| Modulos | M14 (Observabilidade), M1-M3 + M11 (instrumentação cross-cutting) | [Containers](../../engineering/containers/) |
| Contextos | Observability (#generic), Channel (instrumentação) | [Context Map](../../engineering/context-map/) |
| Containers | prosauai-api, redis, **phoenix (NOVO)**, supabase-prosauai | [Containers](../../engineering/containers/) |

## Problema

Hoje (epic 001 entregue), o pipeline de mensagens funciona — webhook recebe, router classifica, debounce agrupa, echo responde — mas a observabilidade é apenas `structlog` em stdout. Para responder perguntas básicas como **"o que aconteceu com a mensagem X?"**, **"por que essa msg não foi respondida?"** ou **"qual é a latência média do echo?"**, é preciso fazer arqueologia em logs distribuídos sem correlação. Isso é insustentável agora (debug manual demorado) e fatal quando o epic 003 (Conversation Core) adicionar LLMs, agentes, retries e timeouts: sem traces correlacionados, será impossível diagnosticar regressões de qualidade ou custos de tokens fora de controle.

Adicionalmente, o reconcile do epic 001 deixou **12 propostas de atualização documental pendentes** (drift score 60%) que precisam ser aplicadas para que `solution-overview.md`, `blueprint.md` (folder structure), `containers.md` (Implementation Status) e `roadmap.md` reflitam a realidade entregue.

## Valor de Negocio

- [ ] **Debug acelerado**: dado um `message_id`, ver waterfall completo (webhook → parse → route → debounce_wait → flush → provider.send → echo.completed) com timing por etapa em <30s
- [ ] **Visibilidade operacional**: dashboards de taxa de mensagens/min, distribuição por `MessageRoute`, error rate por etapa, latência p50/p95/p99
- [ ] **Failure mode detection**: agregação de falhas (HMAC inválido, malformed payload, Redis indisponível, Evolution API 5xx) com count + last_seen + sample trace
- [ ] **Forward-compat para epic 003**: spans namespace `gen_ai.*` prontos para receber traces de pydantic-ai + Bifrost sem refactor
- [ ] **Forward-compat para epics 010/011 (Evals)**: Phoenix tem datasets, experiments e LLM-as-Judge nativos — base de avaliação já no lugar
- [ ] **Cultura "observability is part of the product"**: Phoenix sobe junto com `docker compose up`, time não tem como debugar às cegas
- [ ] **Documentação alinhada com código**: 12 docs sincronizados com a entrega do epic 001 (D0)

## Solucao

**Stack.** Adotar **Phoenix (Arize) self-hosted** como plataforma de observabilidade unificada — supersede ADR-007 (LangFuse v3). Phoenix é OpenTelemetry-native, single container, aceita backend Postgres (compatível com Supabase como BD), e inclui nativamente as primitivas de eval/datasets/prompt management que os epics 010/011 vão exigir — sem paywall.

**Instrumentação.** OpenTelemetry Python SDK com auto-instrumentation para FastAPI, httpx (Evolution API client), redis-py (debounce). Spans manuais cirúrgicos nos pontos de domínio que não têm auto-instrumentation: `route_message`, `debounce.append`, `debounce.flush_handler`, `format_for_whatsapp`. Atributos de cada span seguem **OpenTelemetry GenAI Semantic Conventions** estendidas com namespace `prosauai.*` para metadata local (route, phone_hash, tenant_id, etc).

**Trace lifetime.** Cada mensagem entra com um `trace_id` aberto no webhook. Quando o `DebounceManager.append` salva texto no buffer Redis, propaga o **W3C Trace Context** (`traceparent` + `tracestate`) junto do payload. O listener de keyspace notifications, ao disparar o flush, **restaura o context** via `propagate.extract()` antes de abrir o span do flush + echo. Resultado: **um único trace contínuo** webhook → flush → echo, mesmo que segundos/minutos passem entre webhook e flush. Esse é o pattern OTel oficial para messaging async.

**Correlação log↔trace.** `structlog` ganha um processor que injeta `trace_id` e `span_id` (do contexto OTel atual) em todos os events. Resultado: dado um `message_id` no log, você obtém o `trace_id` e abre o waterfall completo no Phoenix. Dado um trace no Phoenix, você grep o `trace_id` no log JSON e vê o detalhamento.

**Sampling.** Head-based sampling configurável via `OTEL_TRACES_SAMPLER_ARG` no `.env`. Default: 100% em dev, 10% em prod. Permite escalar custo de armazenamento sem cegar diagnóstico.

**Storage.** Phoenix aponta para Supabase Postgres usando schema dedicado `observability` (tabelas `observability.spans`, `observability.traces`). Roda no MESMO projeto Supabase da app por enquanto (decisão pragmática para o MVP), com critério objetivo documentado para migração futura para projeto separado se houver sinais de contention.

**Compose.** Stack único: `docker compose up` sobe `prosauai-api` + `redis` + `phoenix` (3 containers). Phoenix expõe UI em `:6006`. Docker healthcheck garante ordem de startup. Volumes nomeados para persistência local em dev.

**Tenant_id.** `settings.tenant_id` via `.env` (prosauai-default por enquanto). Atributo obrigatório em todo span. Quando epic 013 (multi-tenant self-service) chegar, swap por `lookup_tenant(instance_name)` em UM lugar.

**D0 — Documentation Sync.** Como primeira tarefa do epic 002, aplicar as 12 propostas do reconcile do epic 001:
- D1.1, D1.2, D1.3 → atualizar `business/solution-overview.md` com features entregues
- D2.1 → atualizar folder structure no `engineering/blueprint.md` §3
- D3.1 → adicionar seção "Implementation Status" em `engineering/containers.md`
- D6.1, D6.2, D6.3, D6.4 → atualizar status, lifecycle, riscos no `planning/roadmap.md` e `platform.yaml` (parcialmente já feito ao inserir o próprio epic 002 no roadmap)
- D2.2, D2.3, D3.2 → sem ação (referem-se a arquitetura target — worker, security scan, Redis Streams — fora do escopo dos epics 001/002)

### Interfaces / Contratos

```python
# prosauai/observability/__init__.py
"""Observability module — OpenTelemetry SDK setup, Phoenix exporter,
structlog correlation, custom semantic conventions."""

# prosauai/observability/setup.py
def configure_observability(settings: Settings) -> None:
    """Wires up OTel SDK + Phoenix exporter + structlog bridge.

    Called once from main.py lifespan startup.

    1. TracerProvider with Resource(service.name="prosauai-api",
       service.version=__version__, deployment.environment=settings.env)
    2. OTLPSpanExporter (HTTP) pointing to settings.phoenix_endpoint
    3. BatchSpanProcessor with reasonable defaults
    4. Configure sampler from settings.otel_sampler_arg
    5. Auto-instrument FastAPI, httpx, redis
    6. Wire structlog processor to inject trace_id/span_id
    """
    ...

# prosauai/observability/conventions.py
class SpanAttributes:
    """Constants for our custom span attributes (prosauai.* namespace)."""

    # Tenant + identity
    TENANT_ID = "tenant_id"  # OTel-standard
    PHONE_HASH = "prosauai.phone_hash"  # SHA-256 trunc 12 chars

    # Routing
    ROUTE = "prosauai.route"  # MessageRoute.value
    AGENT_ID = "prosauai.agent_id"  # None until epic 004
    IS_GROUP = "prosauai.is_group"
    FROM_ME = "prosauai.from_me"
    GROUP_ID = "prosauai.group_id"

    # Messaging — OTel semantic conventions
    MESSAGING_SYSTEM = "messaging.system"  # "whatsapp"
    MESSAGING_DESTINATION = "messaging.destination.name"  # instance_name
    MESSAGING_MESSAGE_ID = "messaging.message.id"

    # Debounce
    DEBOUNCE_BUFFER_SIZE = "prosauai.debounce.buffer_size"
    DEBOUNCE_WAIT_MS = "prosauai.debounce.wait_ms"

    # Provider
    PROVIDER_NAME = "prosauai.provider"  # "evolution"
    PROVIDER_HTTP_STATUS = "http.response.status_code"

    # GenAI (reserved for epic 003 — empty stubs today)
    GEN_AI_SYSTEM = "gen_ai.system"  # "echo" until epic 003
    GEN_AI_REQUEST_MODEL = "gen_ai.request.model"  # null until epic 003

# prosauai/observability/structlog_bridge.py
def add_otel_context(logger, method_name, event_dict):
    """Structlog processor — injects current OTel trace_id/span_id."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict

# prosauai/core/debounce.py — updated to propagate W3C context
async def append(self, phone: str, group_id: str | None, text: str) -> None:
    """Buffer text for later flush, propagating OTel trace context."""
    from opentelemetry import propagate
    carrier: dict[str, str] = {}
    propagate.inject(carrier)  # injects traceparent + tracestate
    payload = {
        "text": text,
        "trace_context": carrier,
    }
    # ... existing Lua append using payload
```

### Scope

**Dentro:**
- D0: aplicar 12 propostas do reconcile do epic 001 (atualizar 4 docs)
- ADR-020: Phoenix substitui LangFuse v3 (supersedes ADR-007)
- Container Phoenix no `docker-compose.yml` com volume persistente
- Schema `observability` no Supabase via migration (criado/aplicado pelo Phoenix init container ou migration manual no startup)
- `prosauai/observability/` package: setup.py, conventions.py, structlog_bridge.py, sampler.py
- Auto-instrumentation: FastAPI, httpx (Evolution API), redis-py (debounce)
- Manual spans em `route_message`, `debounce.append`, `debounce.flush_handler`, `_send_echo`
- W3C Trace Context propagation no DebounceManager (carrier no payload Redis)
- Structlog processor que injeta `trace_id`/`span_id`
- Settings novas: `phoenix_endpoint`, `otel_service_name`, `otel_sampler_arg`, `tenant_id`, `deployment_env`
- Sampling head-based configurável via env
- 5 dashboards Phoenix curados: (a) jornada por trace_id, (b) funil por rota, (c) latência por span, (d) failure modes, (e) saúde do debounce
- Healthcheck `/health` retornando status do exporter OTel (último export ok? buffer cheio?)
- Documentação: `engineering/observability.md` (novo) explicando como debugar uma mensagem ponta-a-ponta
- Testes: instrumentação não quebra testes existentes (overhead < 5ms p95 verificado em benchmark)
- Test fixtures: 1 trace E2E reconstrutível em testes de integração

**Fora:**
- LLM tracing real (epic 003 — pydantic-ai + Bifrost spans com `gen_ai.*` reais)
- Eval scores online/offline (epics 010/011 — Phoenix datasets ficam vazios neste epic)
- Multi-tenant real (epic 013 — `tenant_id` é placeholder hoje)
- Alerting (PagerDuty/Slack/Telegram) — dashboards apenas
- Metrics (Prometheus/OTLP metrics) — só traces+logs neste epic; metrics deferred
- Logs no Phoenix UI — logs continuam em stdout/structlog JSON (Phoenix é traces-first)
- Tail-based sampling — head-based é suficiente para o volume atual
- Phoenix em projeto Supabase separado — schema dedicado é o caminho do MVP
- Service mesh / OpenTelemetry Collector standalone — exporter direto é suficiente para 1 serviço
- Synthetic monitoring / uptime checks — out of scope
- Distributed tracing entre prosauai-api e prosauai-worker (worker não existe ainda — chega no epic 003)

## Rabbit Holes

- **W3C context propagation no Redis** → Lua atual do DebounceManager append precisa aceitar payload JSON com `text` + `trace_context` (atualmente só `text`). Migração: payload retro-compatível (`text` standalone OU `{text, trace_context}`). Listener de keyspace tenta `propagate.extract` e cai em "no parent" se ausente
- **Auto-instrumentation FastAPI x lifespan tasks** → Background task do debounce flush listener (criada no lifespan) NÃO herda automaticamente o context OTel. Solução: usar `with tracer.start_as_current_span(...)` explicitamente dentro do listener handler, com context restaurado a partir do `traceparent` lido do Redis. NÃO confiar em context propagation automática para tasks de lifespan
- **Phoenix bootstrap no Supabase** → Phoenix cria suas tabelas no schema configurado via `PHOENIX_SQL_DATABASE_URL`. Decidir se migration roda no startup do Phoenix ou via init container. Postgres user precisa de permissão `CREATE SCHEMA observability`
- **Span attribute bombing** → cuidado para não vazar PII em atributos. Regra: nunca `phone` cru, sempre `phone_hash`. Nunca `text` da mensagem (pode vir CPF/cartão). Nunca `payload` raw da Evolution API. Lint check: ruff custom rule grep `attribute.*phone[^_]` em testes
- **Volume de spans no Postgres** → 10M spans/dia ≈ 116 spans/s. Postgres aguenta confortavelmente até ~50M spans armazenados (com indexes corretos). Acima disso, latência de query degrada. Critério de migração para projeto Supabase separado: spans > 5M/dia OU storage_obs > 50% total OU latência queries app > +20%
- **Phoenix UI sem auth** → Phoenix OSS não tem auth nativo robusto. Em dev: localhost only. Em staging/prod: VPN ou reverse proxy com basic auth. NÃO expor `:6006` na internet
- **Hot reload em dev quebra OTel** → uvicorn `--reload` recria SDK múltiplas vezes, span buffer pode vazar. Solução documentada: configurar SDK condicional `if not settings.dev_reload` ou aceitar warnings em dev
- **Sampling em dev x prod** → Em dev queremos 100% pra debug; em prod 10% pra custo. Mas: amostra de 10% pode esconder bugs raros. Solução: sampling adaptativo no futuro (epic posterior) com tail-based para "errored traces always sampled"
- **Forward-compat do worker (epic 003)** → Quando epic 003 introduzir ARQ worker, distributed trace entre api e worker exige propagation via Redis Streams (outro carrier). Mesmo padrão W3C — código de propagação é reutilizável

## Tasks

- [ ] **D0.1** — Atualizar `business/solution-overview.md` (3 propostas D1.1, D1.2, D1.3)
- [ ] **D0.2** — Atualizar folder structure em `engineering/blueprint.md` §3 (proposta D2.1)
- [ ] **D0.3** — Adicionar "Implementation Status" em `engineering/containers.md` (proposta D3.1)
- [ ] **D0.4** — Atualizar `platform.yaml` lifecycle (proposta D6.4 — verificar se já feito)
- [ ] **D0.5** — Validar reconcile do roadmap.md (já feito ao inserir epic 002)
- [ ] **A1** — ADR-020: Phoenix substitui LangFuse v3 (supersedes ADR-007)
- [ ] **A2** — Atualizar `engineering/blueprint.md` §4.4 Observabilidade: Phoenix em vez de LangFuse
- [ ] **A3** — Atualizar `engineering/containers.md`: container `phoenix` no diagrama, novo Container Matrix entry
- [ ] **B1** — Adicionar deps: `opentelemetry-distro`, `opentelemetry-exporter-otlp-proto-http`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-redis`, `arize-phoenix-otel`
- [ ] **B2** — Settings: `phoenix_endpoint`, `otel_service_name`, `otel_sampler_arg`, `tenant_id`, `deployment_env` no `prosauai/config.py`
- [ ] **B3** — `prosauai/observability/setup.py` — função `configure_observability(settings)`
- [ ] **B4** — `prosauai/observability/conventions.py` — `SpanAttributes` constants
- [ ] **B5** — `prosauai/observability/structlog_bridge.py` — processor que injeta trace_id/span_id
- [ ] **B6** — `prosauai/observability/sampler.py` — head-based sampler com env config
- [ ] **B7** — `prosauai/main.py` — chamar `configure_observability(settings)` no lifespan startup
- [ ] **C1** — Auto-instrument FastAPI no startup
- [ ] **C2** — Auto-instrument httpx no `EvolutionProvider.__init__` (ou global)
- [ ] **C3** — Auto-instrument redis no `DebounceManager.__init__`
- [ ] **D1** — Spans manuais em `route_message` com `SpanAttributes.ROUTE`, `IS_GROUP`, `FROM_ME`
- [ ] **D2** — Spans manuais em `webhook_whatsapp` (entrypoint do trace) com `MESSAGING_SYSTEM`, `MESSAGING_DESTINATION`, `MESSAGING_MESSAGE_ID`, `TENANT_ID`, `PHONE_HASH`
- [ ] **D3** — Spans manuais em `_send_echo` com `PROVIDER_NAME`, `PROVIDER_HTTP_STATUS`
- [ ] **E1** — `DebounceManager.append` injeta `traceparent` + `tracestate` no payload Redis
- [ ] **E2** — `DebounceManager.flush_handler` extrai context e abre span filho
- [ ] **E3** — Migration: Lua script suporta payload JSON `{text, trace_context}` retro-compat
- [ ] **F1** — Container `phoenix` no `docker-compose.yml` com volume + healthcheck
- [ ] **F2** — Variáveis Phoenix: `PHOENIX_SQL_DATABASE_URL` apontando pra Supabase + schema `observability`
- [ ] **F3** — Migration SQL: `CREATE SCHEMA IF NOT EXISTS observability` (init container ou doc manual)
- [ ] **F4** — `.env.example` atualizado com vars Phoenix + OTel + tenant_id
- [ ] **G1** — Healthcheck `/health` reportando status do exporter
- [ ] **G2** — Documentação `engineering/observability.md` — guia "como debugar uma mensagem ponta-a-ponta"
- [ ] **H1** — Test: 1 trace E2E reconstruído em integration test (mock OTel exporter, asserta spans esperados)
- [ ] **H2** — Test: structlog injeta trace_id/span_id quando span ativo
- [ ] **H3** — Test: W3C context sobrevive ao round-trip Redis no debounce
- [ ] **H4** — Test: PII regression — nenhum atributo de span contém `phone` cru ou `text`
- [ ] **H5** — Benchmark: latência p95 do webhook antes/depois (overhead < 5ms)
- [ ] **I1** — 5 dashboards Phoenix curados (export como JSON no repo: `phoenix-dashboards/`)
- [ ] **J1** — README do repo prosauai atualizado: "como abrir Phoenix UI" + "como debugar uma msg"

## Criterios de Sucesso

- [ ] **D0**: 4 docs atualizados (`solution-overview.md`, `blueprint.md`, `containers.md`, `platform.yaml`) — drift score do epic 001 cai para 0%
- [ ] **ADR-020 publicado** marcando ADR-007 como `Superseded by ADR-020`
- [ ] `docker compose up` sobe `prosauai-api` + `redis` + `phoenix` em <60s
- [ ] Phoenix UI acessível em `http://localhost:6006`
- [ ] Schema `observability.spans` criado no Supabase com pelo menos 1 trace registrado
- [ ] **Jornada completa rastreável**: enviar 1 mensagem WhatsApp via webhook → abrir Phoenix → ver waterfall com 7+ spans (webhook → parse → route → debounce.append → debounce.flush → provider.send_text → echo.completed) com trace_id único
- [ ] **Correlação log↔trace**: grep `trace_id=<X>` no `docker logs prosauai-api` retorna todas as linhas estruturadas daquela jornada
- [ ] **3 mensagens rápidas no debounce → 1 trace contínuo** com 3 sub-spans de `debounce.append` e 1 `debounce.flush` em árvore conectada
- [ ] **5 dashboards funcionais** no Phoenix: jornada por trace_id, funil por rota, latência p50/p95/p99, failure modes, saúde do debounce
- [ ] **PII zero**: ruff lint check + grep validation: nenhum atributo de span contém `phone` cru, `text` cru ou payload Evolution raw
- [ ] **Overhead aceitável**: latência p95 do webhook < 5ms maior vs baseline epic 001
- [ ] `pytest` → 130+ testes passando (122 existentes + 8 novos de observability)
- [ ] `ruff check .` → zero errors
- [ ] **Forward-compat verificada**: span tem `gen_ai.system="echo"` placeholder pronto para epic 003 trocar por valor real

## Decisoes

| Data | Decisao | Rationale |
|------|---------|-----------|
| 2026-04-10 | Phoenix substitui LangFuse v3 (supersedes ADR-007) | Stack LangFuse v3 (PG+CH+Redis+MinIO) é incompatível com constraint Supabase-as-DB. Phoenix Postgres-backed cabe direto. ADR-007 já listava Phoenix como fallback documentado |
| 2026-04-10 | OpenTelemetry Python SDK + auto-instrumentation | Vendor-agnóstico. Permite swap futuro pra LangFuse/SigNoz se necessário sem reescrever instrumentação |
| 2026-04-10 | Trace lifetime via W3C Trace Context propagado pelo Redis | Padrão OTel oficial para messaging async. 1 trace contínuo webhook → flush → echo. Suporta retries futuros |
| 2026-04-10 | tenant_id via env `settings.tenant_id` (placeholder "prosauai-default") | Alinhado com ADR-017 (config via Settings + .env). Swap futuro pra lookup real em UMA linha |
| 2026-04-10 | Schema `observability` no MESMO projeto Supabase | Pragmatismo MVP — 1 projeto, 2 schemas. Critério objetivo de migração: spans > 5M/dia OU storage_obs > 50% OU latência app > +20% |
| 2026-04-10 | Stack único docker compose (Phoenix sobe sempre) | Phoenix é leve (~512MB-1GB). Cultura "obs faz parte do produto" desde dia 1. Onboarding 1 comando |
| 2026-04-10 | Sampling head-based 100% dev / 10% prod via env | Custo controlado em scale. Tail-based fica para epic posterior se necessário |
| 2026-04-10 | OTel GenAI Semantic Conventions + namespace `prosauai.*` para metadata local | Padrão da indústria. Forward-compat com epic 003 (LLM real) sem refactor |
| 2026-04-10 | structlog processor injeta trace_id/span_id automaticamente | Correlação log↔trace zero-friction. Debug cruzado é trivial |
| 2026-04-10 | PII zero em spans: phone_hash sempre, nunca text raw | Compliance LGPD (ADR-018). Lint check no CI |
| 2026-04-10 | D0 = 12 propostas reconcile do epic 001 como primeira tarefa | Decisão do usuário. Mantém epic 002 dono da dívida documental herdada |
| 2026-04-10 | Sem alerting/metrics neste epic — só traces+logs | Scope discipline. Alerting é epic posterior; metrics OTLP idem |
| 2026-04-10 | Sem distributed tracing api↔worker | Worker não existe ainda (chega no epic 003). Padrão de propagação fica documentado para reuso |

## Notas

(Append-only — adicionar descobertas durante implementacao)

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|---------|----------------------|
| 1 | Tooling | Phoenix (Arize) self-hosted substitui LangFuse v3 | ADR-020 (novo) supersedes ADR-007 |
| 2 | SDK | OpenTelemetry Python SDK + auto-instrumentation FastAPI/httpx/redis | OTel spec, blueprint §4.4 |
| 3 | Backend | Supabase Postgres mesmo projeto, schema dedicado `observability` | ADR-011 (RLS), constraint usuário |
| 4 | Trace lifetime | W3C Trace Context propagado via Redis (1 trace contínuo) | OTel messaging spec, blueprint §4.6 |
| 5 | tenant_id | `settings.tenant_id` via .env, swap futuro pra lookup real | ADR-017 |
| 6 | Compose | Stack único — Phoenix sobe sempre com `docker compose up` | Containers.md |
| 7 | Sampling | Head-based 100% dev / 10% prod via env var | NFR Q2 |
| 8 | Conventions | OTel GenAI Semantic Conventions + namespace `prosauai.*` | OTel spec, ADR-007 (mantém este princípio) |
| 9 | Logs | structlog processor injeta trace_id/span_id automaticamente | ADR-018 (PII zero) |
| 10 | PII | Zero PII em spans — phone_hash sempre, nunca text raw | ADR-018 |
| 11 | D0 | 12 propostas reconcile do epic 001 como primeira tarefa | reconcile-report.md do epic 001 |
| 12 | Scope | Sem alerting, metrics, distributed tracing api↔worker | Scope discipline MVP |
| 13 | Migration trigger | Spans > 5M/dia OU storage_obs > 50% OU latência app > +20% → projeto Supabase separado | Critério objetivo |

## Resolved Gray Areas

**Por que Phoenix e não LangFuse v3?** O constraint "Supabase como BD" elimina LangFuse v3 (que exige ClickHouse). Phoenix é a única ferramenta OTel-native, LLM-ready, com Postgres backend, single container, que cabe no constraint. ADR-007 já documentava Phoenix como fallback aceito — agora é o caminho principal. ADR-020 substitui ADR-007.

**Por que NÃO SigNoz?** SigNoz exige ClickHouse (mesmo problema do LangFuse). Além disso, é APM-first, não LLM-first — quando epic 003 chegar, vai precisar de tooling adicional (Phoenix ou LangFuse) ao lado. Dois sistemas = mais ops.

**Por que NÃO Grafana LGTM?** Tempo (storage de traces) usa S3/object storage, não Postgres. Não cabe no constraint. Além disso, configuração pesada e nada LLM-native.

**Trace lifetime: 1 trace ou N traces?** UM trace contínuo via W3C Trace Context propagado pelo Redis. Permite ver "3 mensagens rápidas → 1 echo" como árvore única no Phoenix. Custo: ~30 LOC no DebounceManager para serializar/desserializar carrier. Padrão OTel oficial para messaging-async.

**tenant_id agora ou depois?** Agora, mas como placeholder (`settings.tenant_id` via .env). O atributo é OBRIGATÓRIO em todo span desde dia 1 — quando epic 013 chegar, swap em UM lugar. Sem isso, dashboards históricos perdem dimensão crítica.

**Compose com profile ou stack único?** Stack único. Phoenix é leve (~512MB-1GB), cabe no `docker compose up` padrão. Cria a cultura "observabilidade não é opcional" — devs nunca debugam às cegas. Se um dia trocarmos pra LGTM/LangFuse, reabrimos a decisão.

**Como evitar PII em spans?** Reusar o padrão do epic 001: `phone_hash = sha256(phone)[:12]`. Nunca atributo `text`. Nunca `payload` raw. Lint check no CI: grep `attribute.*phone[^_]` em código de spans. Documentado em ADR-018.

**Migrar pra projeto Supabase separado quando?** Critério objetivo (não "quando incomodar"): (a) spans > 5M/dia, OU (b) storage_obs > 50% do total Supabase, OU (c) latência queries app > +20% baseline. Qualquer um dispara epic futuro `obs-storage-isolation`.

**Sampling 100% ou amostragem?** Head-based, configurável via env. Default 100% dev / 10% prod. Permite ajuste por deploy sem mudar código. Tail-based (errored traces always 100%) fica para epic posterior se houver evidência de bugs raros sendo perdidos pela amostragem.

**Logs no Phoenix UI ou fora?** Logs continuam em `structlog` JSON via stdout. Phoenix é traces-first — UI de logs é fraca. Correlação é via `trace_id` injetado no log: dado um trace, grep o ID no log; dado um log, abre o trace. Loki opcional em epic posterior.

**Alerting neste epic?** NÃO. Scope discipline. Dashboards primeiro; alerting depois com base em SLOs descobertos. Telegram (ADR-018 superseder) é o canal definido para quando alerting chegar.

## Applicable Constraints

| Constraint | Source | Impact |
|-----------|--------|--------|
| Supabase como BD único | Decisão usuário 2026-04-10 | Phoenix é única opção OTel + LLM-ready compatível |
| Zero PII em logs/traces | ADR-018 | phone_hash sempre, nunca text raw, lint check no CI |
| HMAC-SHA256 webhook validation | ADR-017 | Span do webhook captura `hmac_valid: bool` como atributo |
| OTel GenAI Semantic Conventions obrigatório | ADR-007 (mantido na supersession) | Atributos `gen_ai.*` reservados para epic 003 |
| `tenant_id` em todo span | ADR-007 (mantido) | Atributo obrigatório desde dia 1 |
| Config nunca em código | ADR-017 | Vars Phoenix/OTel via Settings + .env |
| Forward-compat com epic 003 (LLM) | Pitch epic 003 (Conversation Core) | Spans `gen_ai.*` placeholder, namespace `prosauai.*` reservado para metadata local |
| Forward-compat com epics 010/011 (Evals) | Roadmap | Phoenix datasets/experiments ficam vazios mas a estrutura está pronta |
| Pipeline L2 obrigatório (12 nodes) | pipeline-dag-knowledge.md | Epic 002 segue ciclo completo: specify → clarify → plan → tasks → analyze → implement → judge → qa → reconcile → roadmap-reassess |
| Repo binding | platform.yaml | Código vai em `paceautomations/prosauai`, branch `epic/prosauai/002-observability` |

## Suggested Approach

**Fase 0 — D0 Doc Sync (1 dia)**
1. Aplicar 12 propostas do reconcile do epic 001 (4 docs)
2. Verificar drift score = 0% antes de prosseguir
3. Commit: `chore(prosauai): D0 — sync docs after epic 001`

**Fase 1 — ADR + Docs Pré-Implementação (1 dia)**
4. ADR-020: Phoenix substitui LangFuse (supersedes ADR-007)
5. Atualizar `blueprint.md` §4.4 Observabilidade
6. Atualizar `containers.md` com container Phoenix + Container Matrix entry
7. Criar `engineering/observability.md` (guia de debug ponta-a-ponta — pode ser placeholder e preencher depois)
8. Commit: `docs(prosauai): ADR-020 + Phoenix observability architecture`

**Fase 2 — Infra (1 dia)**
9. Adicionar `phoenix` ao `docker-compose.yml` com volume + healthcheck + env vars
10. Criar migration manual `CREATE SCHEMA IF NOT EXISTS observability` no Supabase
11. Atualizar `.env.example`
12. Validar: `docker compose up` sobe Phoenix, UI em `:6006`, schema criado

**Fase 3 — SDK Setup + Auto-Instrumentation (1 dia)**
13. Adicionar deps OTel + Phoenix no `pyproject.toml`
14. `prosauai/observability/setup.py` — configure_observability()
15. `prosauai/observability/conventions.py` — SpanAttributes constants
16. `prosauai/observability/structlog_bridge.py` — processor
17. `prosauai/main.py` lifespan — chamar `configure_observability(settings)`
18. Validar: requisição no `/health` cria 1 trace no Phoenix
19. Test: structlog processor injeta trace_id

**Fase 4 — Spans Manuais + W3C Propagation (2 dias)**
20. Span manual no `webhook_whatsapp` com atributos OTel + prosauai
21. Span manual em `route_message`
22. Span manual em `_send_echo`
23. `DebounceManager.append` injeta `traceparent`/`tracestate` no payload Redis
24. `DebounceManager.flush_handler` extrai context e abre span filho
25. Lua script suporta payload JSON `{text, trace_context}` retro-compat
26. Validar: 1 mensagem real → trace completo no Phoenix com 7+ spans
27. Validar: 3 msgs rápidas → 1 trace contínuo com sub-spans append + 1 flush

**Fase 5 — Dashboards + PII Lint (1 dia)**
28. 5 dashboards Phoenix curados (export JSON)
29. PII lint check no CI (ruff custom rule ou grep test)
30. Benchmark p95 antes/depois (overhead < 5ms)

**Fase 6 — Tests + QA (1 dia)**
31. 8+ testes novos (E2E trace, structlog bridge, W3C round-trip Redis, PII regression)
32. Documentação final `engineering/observability.md` com runbook real
33. README do repo prosauai atualizado

**Total: ~7 dias úteis** (dentro de "1 semana" do roadmap revisado, mas confortavelmente — não é projeto trivial)

> **Proximo passo:** `/speckit.specify prosauai 002` — especificar feature detalhada a partir deste contexto.
