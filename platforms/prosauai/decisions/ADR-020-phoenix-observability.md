---
title: 'ADR-020: Phoenix (Arize) substitui LangFuse para observabilidade'
status: Accepted
decision: Phoenix (Arize) self-hosted
alternatives: LangFuse v3 (ADR-007), LangSmith, Helicone
rationale: Single container, Postgres backend, OTLP gRPC nativo, ops drasticamente mais simples
supersedes: ADR-007-langfuse-observability
---
# ADR-020: Phoenix (Arize) substitui LangFuse para observabilidade
**Status:** Accepted | **Data:** 2026-04-09 (epic 002) | **Supersedes:** [ADR-007](ADR-007-langfuse-observability.md)

## Contexto

Durante a implementacao do epic 002 (Observability), ao validar LangFuse v3 self-hosted em ambiente real, encontramos problemas operacionais significativos:
- ClickHouse consome CPU idle de forma desproporcional
- Tabela `events` ausente na v3.152.0 (bug)
- Timezone UTC obrigatorio com migracoes manuais em modo clustered
- Stack de 3 containers (app + Postgres + ClickHouse) vs. necessidade de single-container simples

## Decisao

Substituir LangFuse por **Phoenix (Arize) self-hosted** como plataforma de observabilidade LLM.

### Stack implementada (epic 002)

| Componente | Tecnologia | Porta |
|------------|-----------|-------|
| Phoenix UI | Docker `arizephoenix/phoenix:8.22.1` | :6006 (HTTP) |
| OTLP ingestao | gRPC nativo do Phoenix | :4317 |
| Backend | Postgres (Supabase) | — |
| SDK | `opentelemetry-sdk` + `arize-phoenix-otel` | — |
| Auto-instrumentation | `opentelemetry-instrumentation-fastapi`, `-httpx`, `-redis` | — |
| Log bridge | `structlog_bridge.py` — injeta `trace_id`/`span_id` em logs estruturados | — |

### Vantagens sobre LangFuse

1. **Single container** — Phoenix = 1 container Docker. LangFuse = app + Postgres + ClickHouse
2. **Postgres backend** — reutiliza Supabase existente. Sem ClickHouse
3. **OTLP gRPC nativo** — fire-and-forget via `BatchSpanProcessor`. Sem SDK proprietario
4. **OpenTelemetry first** — auto-instrumentation para FastAPI, httpx, redis out-of-the-box
5. **SpanQL queries** — linguagem de query para spans no waterfall UI
6. **Operacionalmente simples** — healthcheck via `/healthz`, zero migracoes manuais

### Trade-offs

| Aspecto | Phoenix | LangFuse |
|---------|---------|----------|
| Prompt management | Nao tem (usa versionamento no codigo) | Integrado (versiona + deploya prompts) |
| Evals integrados | Basico (traces view) | DeepEval + custom evals |
| Community size | Menor | 26M+ SDK installs/mes |
| Auto-instrumentation | OpenTelemetry nativo | SDK proprietario |

### Mitigacao de trade-offs

- **Prompt management**: versionamento via `agent_config_versions` table (ADR-019) em vez de ferramenta externa
- **Evals**: DeepEval + Promptfoo continuam como stack de eval separada (ADR-008), nao dependem do LangFuse

## Alternativas rejeitadas

### Manter LangFuse v3
- Rejeitado: problemas operacionais reais encontrados durante epic 002. ClickHouse overhead inaceitavel para 2 tenants

### LangSmith
- Rejeitado: SaaS-only (mesma razao do ADR-007). Dados nao saem do ambiente

### Helicone
- Rejeitado: proxy-based (nao self-hosted). Lock-in com API Gateway pattern

## Consequencias

- `prosauai/observability/` reescrito com OTel SDK + Phoenix exporter
- `structlog_bridge.py` criado para correlacao log↔trace
- `ExporterHealthTracker` criado para monitorar status de exportacao
- Health endpoint (`/health`) reflete estado do OTel exporter (ok/degraded)
- docker-compose.yml inclui Phoenix container
- Todos os ADRs e docs que referenciavam LangFuse atualizados para Phoenix
