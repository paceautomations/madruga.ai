# Implementation Plan: Observability — Tracing Total da Jornada de Mensagem

**Branch**: `epic/prosauai/002-observability` | **Date**: 2026-04-10 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `platforms/prosauai/epics/002-observability/spec.md`

## Summary

Instrumentar o pipeline de mensagens do ProsauAI com OpenTelemetry + Phoenix (Arize) self-hosted para rastreamento fim-a-fim de cada mensagem — do webhook ao echo. A implementação adiciona: (1) container Phoenix no docker-compose apontando para Supabase Postgres, (2) OTel SDK com auto-instrumentation FastAPI/httpx/redis, (3) spans manuais nos pontos de domínio, (4) propagação W3C Trace Context pelo Redis no debounce, (5) correlação structlog↔trace, (6) 5 dashboards curados no Phoenix. Adicionalmente, como D0, aplica 12 propostas de atualização documental pendentes do reconcile do epic 001.

## Technical Context

**Language/Version**: Python 3.12, FastAPI >=0.115  
**Primary Dependencies**: `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-redis`, `arize-phoenix-otel`  
**Storage**: Supabase Postgres (schema `observability`, gerenciado pelo Phoenix); Redis 7 (buffers de debounce)  
**Testing**: pytest + InMemorySpanExporter (SimpleSpanProcessor) + OTEL_SDK_DISABLED=true para testes regulares  
**Target Platform**: Linux server (Docker Compose: prosauai-api + redis + phoenix)  
**Project Type**: Web service (FastAPI) — instrumentação cross-cutting  
**Performance Goals**: Overhead < 5ms p95 no webhook, exporter fire-and-forget  
**Constraints**: Zero PII em spans (phone_hash, nunca text raw), Supabase como BD único  
**Scale/Scope**: ~10 arquivos modificados, ~600-800 LOC novos, 8+ testes novos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Status | Justificativa |
|-----------|--------|---------------|
| I. Pragmatism Above All | ✅ PASS | Phoenix single container é a solução mais simples compatível com constraints. Sem over-engineering (sem OTel Collector standalone, sem tail-based sampling, sem alerting) |
| II. Automate Repetitive Tasks | ✅ PASS | Auto-instrumentation cobre 80% dos spans. structlog processor automático para correlação |
| IV. Fast Action Over Excessive Planning | ✅ PASS | Implementação direta — stack único, config via env, TDD para novos testes |
| V. Alternatives and Trade-offs | ✅ PASS | 5 alternativas documentadas para Phoenix, 3 para propagação, 3 para sampling (research.md) |
| VI. Brutal Honesty | ✅ PASS | Phoenix UI de logs é fraca (documentado). Hot reload warnings em dev (documentado). Auth ausente em dev (documentado) |
| VII. TDD | ✅ PASS | 8+ testes novos: E2E trace, structlog bridge, W3C round-trip, PII regression. InMemorySpanExporter para asserts |
| IX. Observability and Logging | ✅ PASS | Este epic É o princípio IX implementado — trace_id/span_id em todo log, correlação bidirecional |

**Re-check pós-design**: ✅ PASS. Nenhuma violação introduzida nas fases de design.

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/002-observability/
├── plan.md              # This file
├── research.md          # Phase 0 output — 7 research topics
├── data-model.md        # Phase 1 output — entities, attributes, Redis payload
├── quickstart.md        # Phase 1 output — setup and debug guide
├── contracts/           # Phase 1 output
│   └── observability-api.md  # Module interface, health contract, span hierarchy
├── spec.md              # Feature specification (20 FRs, 12 SCs)
├── pitch.md             # Epic context and decisions
├── decisions.md         # Decision log
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (prosauai repository)

```text
prosauai/
├── prosauai/
│   ├── __init__.py              # (existing) add __version__
│   ├── main.py                  # (modify) call configure_observability, add otel processor to structlog
│   ├── config.py                # (modify) add OTel/Phoenix settings fields
│   ├── observability/           # (NEW) observability package
│   │   ├── __init__.py
│   │   ├── setup.py             # configure_observability() — SDK + exporter + auto-instrument
│   │   ├── conventions.py       # SpanAttributes constants (prosauai.* + gen_ai.*)
│   │   ├── structlog_bridge.py  # add_otel_context processor
│   │   └── tracing.py           # helper: get_tracer(), span context inject/extract utils
│   ├── api/
│   │   ├── health.py            # (modify) extend HealthResponse with observability field
│   │   └── webhooks.py          # (modify) add manual spans + inject trace context
│   ├── core/
│   │   ├── debounce.py          # (modify) RPUSH Lua, trace context propagation
│   │   ├── router.py            # (modify) HealthResponse model extension
│   │   └── formatter.py         # (existing, no changes)
│   └── channels/
│       └── evolution.py         # (existing, auto-instrumented via httpx)
├── tests/
│   ├── unit/
│   │   ├── test_otel_setup.py       # (NEW) OTel SDK configuration tests
│   │   ├── test_structlog_bridge.py  # (NEW) trace_id/span_id injection
│   │   ├── test_conventions.py       # (NEW) SpanAttributes validation
│   │   └── test_pii_regression.py    # (NEW) no raw phone/text in span attributes
│   └── integration/
│       ├── test_trace_e2e.py         # (NEW) full trace reconstruction
│       ├── test_debounce_context.py  # (NEW) W3C context round-trip Redis
│       └── test_health.py            # (modify) assert observability field
├── docker-compose.yml   # (modify) add phoenix service
├── .env.example         # (modify) add OTel/Phoenix vars
└── pyproject.toml       # (modify) add OTel dependencies
```

**Structure Decision**: Observability é um pacote cross-cutting (`prosauai/observability/`) com 4 módulos. Não é um bounded context de domínio — é infraestrutura que instrumenta os contextos existentes (channel, debounce, echo).

## Complexity Tracking

| Aspecto | Complexidade | Justificativa |
|---------|-------------|---------------|
| Lua script rewrite (APPEND→RPUSH) | Média | Muda o mecanismo de buffer. Lua atômico garante consistência. Testes existentes cobrem |
| W3C context propagation | Média | Pattern OTel documentado mas requer serialização/deserialização cuidadosa no Redis |
| Auto-instrumentation setup | Baixa | Padrão OTel — 5 linhas por instrumentor |
| Spans manuais | Baixa | 3-5 linhas por span com `tracer.start_as_current_span()` |
| Phoenix compose setup | Baixa | Single container com env vars |
| D0 doc sync | Baixa | Edições manuais em 4 docs |

---

## Implementation Phases

### Fase 0 — D0: Documentation Sync (Pré-Implementação)

**Objetivo**: Aplicar 12 propostas pendentes do reconcile do epic 001 para zerar drift documental.

| Task | Arquivo | Mudança | LOC Estimado |
|------|---------|---------|-------------|
| D0.1 | `business/solution-overview.md` | Propostas D1.1, D1.2, D1.3 — features entregues epic 001 | ~30 |
| D0.2 | `engineering/blueprint.md` §3 | Proposta D2.1 — folder structure real | ~20 |
| D0.3 | `engineering/containers.md` | Proposta D3.1 — seção "Implementation Status" | ~30 |
| D0.4 | `platform.yaml` | Proposta D6.4 — lifecycle check | ~5 |
| D0.5 | `planning/roadmap.md` | Verificar se já atualizado (epic 002 inserido) | ~0 |

**Critério de saída**: 4 docs atualizados, drift score epic 001 = 0%.

---

### Fase 1 — ADR + Architectural Docs

**Objetivo**: Documentar decisão Phoenix e atualizar arquitetura antes de implementar.

| Task | Arquivo | Mudança | LOC Estimado |
|------|---------|---------|-------------|
| A1 | `decisions/ADR-020-phoenix-observability.md` | Novo ADR: Phoenix substitui LangFuse v3 (supersedes ADR-007) | ~80 |
| A2 | `engineering/blueprint.md` §4.4 | Atualizar Observabilidade: Phoenix em vez de LangFuse | ~20 |
| A3 | `engineering/containers.md` | Container `phoenix` no diagrama + Container Matrix entry | ~30 |

**Critério de saída**: ADR-020 publicado, ADR-007 marcado como superseded.

---

### Fase 2 — Infrastructure (Docker + Dependencies)

**Objetivo**: Phoenix rodando no compose, deps OTel instaladas.

| Task | Arquivo Alvo | Mudança | LOC Estimado |
|------|-------------|---------|-------------|
| F1 | `docker-compose.yml` | Container `phoenix` com volume, healthcheck, env vars + portas 6006/4317 | ~25 |
| F2 | `docker-compose.yml` + `.env.example` | Variáveis Phoenix (`PHOENIX_SQL_DATABASE_URL`, `PHOENIX_PROJECT_NAME`) | ~10 |
| F4 | `.env.example` | Vars OTel + Phoenix + tenant_id + deployment_env | ~15 |
| B1 | `pyproject.toml` | Deps OTel (6 packages) + `arize-phoenix-otel` | ~10 |
| B2 | `prosauai/config.py` | Settings: phoenix_grpc_endpoint, otel_service_name, otel_sampler_arg, tenant_id, deployment_env, otel_enabled | ~15 |

**Critério de saída**: `docker compose up` sobe 3 containers (api, redis, phoenix). Phoenix UI em `:6006`.

---

### Fase 3 — OTel SDK Setup + Auto-Instrumentation

**Objetivo**: SDK configurado, auto-instrumentation ativa, structlog bridge funcional.

| Task | Arquivo Alvo | Mudança | LOC Estimado |
|------|-------------|---------|-------------|
| B3 | `prosauai/observability/setup.py` | `configure_observability(settings)`: TracerProvider, Resource, Sampler, BatchSpanProcessor, OTLPSpanExporter, auto-instrument FastAPI/httpx/redis | ~80 |
| B4 | `prosauai/observability/conventions.py` | `SpanAttributes` constants (prosauai.*, gen_ai.*, messaging.*) | ~40 |
| B5 | `prosauai/observability/structlog_bridge.py` | `add_otel_context` processor | ~25 |
| B6 | `prosauai/observability/tracing.py` | Helper: `get_tracer()`, inject/extract utils para W3C context | ~30 |
| B7 | `prosauai/main.py` | Chamar `configure_observability(settings)` no lifespan, adicionar `add_otel_context` aos shared_processors | ~15 |
| C1-C3 | (within setup.py) | Auto-instrument FastAPI, httpx, redis (chamadas no configure_observability) | ~10 |

**Critério de saída**: Request ao `/health` cria trace no Phoenix. Logs contêm `trace_id`/`span_id`.

---

### Fase 4 — Manual Spans + W3C Propagation

**Objetivo**: Spans manuais nos pontos de domínio. Trace contínuo webhook→flush→echo.

| Task | Arquivo Alvo | Mudança | LOC Estimado |
|------|-------------|---------|-------------|
| D2 | `prosauai/api/webhooks.py` | Span manual `webhook_whatsapp` com atributos: MESSAGING_SYSTEM, MESSAGING_DESTINATION, MESSAGING_MESSAGE_ID, PHONE_HASH, IS_GROUP, FROM_ME, GROUP_ID, TENANT_ID | ~30 |
| D1 | `prosauai/core/router.py` (chamada em webhooks.py) | Span manual `route_message` com atributos: ROUTE, IS_GROUP, FROM_ME | ~15 |
| D3 | `prosauai/main.py` (`_flush_echo`) + `prosauai/api/webhooks.py` (`_send_echo`) | Span manual `send_echo` com: PROVIDER_NAME, GEN_AI_SYSTEM="echo" | ~20 |
| E1 | `prosauai/core/debounce.py` (append) | Injetar `traceparent`/`tracestate` no payload. Serializar como JSON `{"text": ..., "trace_context": {...}}` | ~25 |
| E2 | `prosauai/core/debounce.py` (start_listener/flush) | Extrair context do primeiro item. Links dos demais. Abrir span filho com parent restaurado | ~40 |
| E3 | `prosauai/core/debounce.py` (LUA_SCRIPT) | Novo Lua: `RPUSH` (append) + `LRANGE+DEL` (flush). Retrocompat com payloads texto puro | ~35 |

**Critério de saída**: 1 mensagem → trace completo no Phoenix com 7+ spans. 3 msgs rápidas → 1 trace contínuo com sub-spans append + 1 flush.

---

### Fase 5 — Health Extension + Dashboards + PII Lint

**Objetivo**: Health reporta status OTel. Dashboards curados. PII validada.

| Task | Arquivo Alvo | Mudança | LOC Estimado |
|------|-------------|---------|-------------|
| G1 | `prosauai/api/health.py` + `prosauai/core/router.py` | Estender HealthResponse com `ObservabilityHealth`. Checar último export success via span processor status | ~30 |
| I1 | `phoenix-dashboards/README.md` | 5 SpanQL queries documentadas: (a) jornada por trace_id, (b) funil por rota, (c) latência p50/p95/p99, (d) failure modes, (e) saúde debounce | ~60 |
| PII | (CI/teste) | Grep validation: nenhum atributo contém `phone` cru, `text` raw, ou payload raw | ~10 |

**Critério de saída**: `/health` retorna campo `observability`. 5 dashboards documentados. Zero PII em spans.

---

### Fase 6 — Tests + Documentation

**Objetivo**: Testes novos passando. Documentação operacional completa.

| Task | Arquivo Alvo | Mudança | LOC Estimado |
|------|-------------|---------|-------------|
| H1 | `tests/integration/test_trace_e2e.py` | 1 trace E2E reconstruído: mock OTel exporter, asserta spans esperados (webhook→route→append→flush→echo) | ~80 |
| H2 | `tests/unit/test_structlog_bridge.py` | structlog injeta trace_id/span_id quando span ativo; não injeta quando inativo | ~40 |
| H3 | `tests/integration/test_debounce_context.py` | W3C context sobrevive round-trip Redis no debounce (serialize → RPUSH → LRANGE → extract) | ~60 |
| H4 | `tests/unit/test_pii_regression.py` | Nenhum atributo de span contém phone cru ou text raw (grep em conventions.py + webhook code) | ~30 |
| H5 | (benchmark) | Latência p95 webhook antes/depois — overhead < 5ms | ~20 |
| G2 | `engineering/observability.md` (plataforma) | Guia "como debugar uma mensagem ponta-a-ponta" — runbook completo | ~50 |
| J1 | `README.md` (repo prosauai) | "Como abrir Phoenix UI" + "Como debugar uma msg" | ~20 |

**Critério de saída**: 130+ testes passando (122 + 8+). `ruff check .` = 0. Overhead < 5ms.

---

## Design Decisions (Phase 1)

### DD-001: Lua Script — APPEND → RPUSH

**Decisão**: Mudar de `APPEND` (string concatenation) para `RPUSH` (lista) no buffer Redis.

**Alternativas**:
1. **RPUSH lista** — cada item é JSON com text + trace_context → ✅ Escolhido
   - Prós: Trace context por mensagem, reconstituição limpa, sem parsing de separator
   - Contras: Muda Lua script e flush logic
2. **APPEND com delimiter JSON** — serializar tudo em 1 string → ❌
   - Prós: Não muda tipo de key
   - Contras: Parse complexo no flush, não consegue distinguir boundaries de mensagem se texto contém delimiter
3. **Hash com field per message** — HSET por index → ❌
   - Prós: Acesso individual por index
   - Contras: Over-engineering, HGETALL + HDEL não é atômico sem Lua extra

**Impacto**: Flush muda de `GETDEL` para `LRANGE 0 -1 + DEL` (ambos atômicos em Lua). Testes existentes de debounce precisam ser atualizados para o novo formato.

### DD-002: Auto-Instrumentation Global vs Per-Instance

**Decisão**: Auto-instrumentation global no `configure_observability()`.

**Alternativas**:
1. **Global** (`FastAPIInstrumentor.instrument_app(app)`, `HttpxInstrumentor().instrument()`, `RedisInstrumentor().instrument()`) → ✅ Escolhido
   - Prós: Setup único, todas as instâncias instrumentadas automaticamente
   - Contras: Menos controle granular
2. **Per-instance** (instrumentar cada `httpx.AsyncClient` e `Redis` individualmente) → ❌
   - Prós: Controle total de quais clients são trackeados
   - Contras: Mais LOC, fácil esquecer um client, precisa mudar construtores

### DD-003: OTLP gRPC vs HTTP

**Decisão**: OTLP gRPC (porta 4317) para comunicação com Phoenix.

**Alternativas**:
1. **gRPC** → ✅ Escolhido
   - Prós: Mais eficiente (binary protocol, streaming), padrão OTel preferido
   - Contras: Requer porta adicional, grpc dependency
2. **HTTP** (porta 4318) → ❌
   - Prós: Mais simples (sem grpc dep), funciona em ambientes que bloqueiam gRPC
   - Contras: Menos eficiente, mais overhead por request

### DD-004: Exporter Health Tracking

**Decisão**: Monitorar `last_export_success` via custom SpanProcessor wrapper que intercepta `on_end()` e tracked success/failure do `BatchSpanProcessor`.

**Alternativas**:
1. **Custom wrapper SpanProcessor** → ✅ Escolhido
   - Prós: Sem dependência externa, integrado no health endpoint
   - Contras: Mais LOC (~20 linhas)
2. **Prometheus metrics do OTel SDK** → ❌
   - Prós: Métricas nativas
   - Contras: Requer Prometheus (fora do escopo), over-engineering para um bool

---

## Risk Assessment

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Phoenix >=8.0 não suporta Postgres | Baixa | Alto | Pinada versão verificada. Fallback: SQLite local Phoenix |
| OTel auto-instrumentation incompatível com FastAPI lifespan tasks | Média | Médio | Spans manuais no listener. Não confiar em context propagation automática para lifespan tasks |
| Lua script RPUSH quebra testes existentes | Alta | Baixo | Atualizar testes junto com a mudança. Comportamento externo (append → flush → callback) idêntico |
| Hot reload uvicorn reinicializa OTel SDK | Alta | Baixo | Documentar como warning aceito em dev. Guard `if not already_configured` |
| Volume de spans excede storage Supabase | Baixa | Médio | Sampling 10% em prod. Critério de migração documentado (5M spans/dia) |
| Phoenix sem auth exposta na internet | Média | Alto | Localhost only em dev. Staging/prod: reverse proxy com basic auth (doc no quickstart) |

---

## Estimated Effort

| Fase | LOC Estimado | Dias Estimados |
|------|-------------|----------------|
| Fase 0 — D0 Doc Sync | ~85 (docs) | 0.5 |
| Fase 1 — ADR + Arch Docs | ~130 (docs) | 0.5 |
| Fase 2 — Infrastructure | ~75 (config) | 0.5 |
| Fase 3 — SDK Setup | ~200 (code) | 1 |
| Fase 4 — Spans + Propagation | ~165 (code) | 1.5 |
| Fase 5 — Health + Dashboards | ~100 (code+docs) | 0.5 |
| Fase 6 — Tests + Docs | ~300 (tests+docs) | 1.5 |
| **Total** | **~1055** | **~6 dias** |

---

## Agent Context

### Tecnologias Adicionadas (Epic 002)
- OpenTelemetry Python SDK (api, sdk, exporter-otlp-proto-grpc)
- OpenTelemetry Instrumentation (FastAPI, httpx, redis)
- arize-phoenix-otel (Phoenix helper)
- Phoenix (Arize) self-hosted via Docker

### Padrões Chave
- `configure_observability(settings)` chamado no lifespan startup
- `add_otel_context` structlog processor para correlação log↔trace
- W3C Trace Context propagado via payload Redis JSON no debounce
- SpanAttributes constants em `prosauai.observability.conventions`
- InMemorySpanExporter para testes; OTEL_SDK_DISABLED para testes regulares

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan completo com 6 fases, 7 research topics, data model (spans, Redis payload, settings), contracts (observability API, health extension, span hierarchy). ~1055 LOC, ~6 dias. Pronto para breakdown em tasks com dependências e TDD."
  blockers: []
  confidence: Alta
  kill_criteria: "Se Phoenix >=8.0 não suportar Postgres backend, ou se OTel auto-instrumentation for incompatível com FastAPI lifespan tasks do prosauai."
