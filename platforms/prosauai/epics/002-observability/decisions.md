---
epic: 002-observability
created: 2026-04-10
updated: 2026-04-10
---
# Registro de Decisoes — Epic 002

1. `[2026-04-10 epic-context]` Phoenix (Arize) self-hosted substitui LangFuse v3 como plataforma de observabilidade (ref: ADR-020 supersedes ADR-007)
2. `[2026-04-10 epic-context]` OpenTelemetry Python SDK + auto-instrumentation FastAPI/httpx/redis como camada de instrumentação (ref: OTel spec, blueprint §4.4)
3. `[2026-04-10 epic-context]` Storage no Supabase Postgres mesmo projeto, schema dedicado `observability` (ref: ADR-011 RLS, constraint usuário 2026-04-10)
4. `[2026-04-10 epic-context]` Trace lifetime via W3C Trace Context propagado pelo Redis — 1 trace contínuo webhook → flush → echo (ref: OTel messaging spec, blueprint §4.6)
5. `[2026-04-10 epic-context]` `tenant_id` via `settings.tenant_id` no `.env`, swap futuro pra lookup real em UMA linha (ref: ADR-017)
6. `[2026-04-10 epic-context]` Stack único `docker compose up` — Phoenix sobe sempre junto com api+redis (ref: containers.md)
7. `[2026-04-10 epic-context]` Sampling head-based 100% dev / 10% prod via `OTEL_TRACES_SAMPLER_ARG` env (ref: NFR Q2 blueprint)
8. `[2026-04-10 epic-context]` OTel GenAI Semantic Conventions + namespace `prosauai.*` para metadata local (ref: OTel spec, ADR-007 mantém este princípio)
9. `[2026-04-10 epic-context]` structlog processor injeta `trace_id`/`span_id` automaticamente em todos os events (ref: ADR-018 PII zero)
10. `[2026-04-10 epic-context]` Zero PII em spans — `phone_hash` sempre, nunca `text` raw, nunca `payload` Evolution raw, lint check no CI (ref: ADR-018)
11. `[2026-04-10 epic-context]` D0 = 12 propostas reconcile do epic 001 como primeira tarefa do epic 002 (ref: reconcile-report.md do epic 001)
12. `[2026-04-10 epic-context]` Sem alerting, sem metrics, sem distributed tracing api↔worker neste epic — scope discipline (ref: pitch.md §scope.fora)
13. `[2026-04-10 epic-context]` Critério objetivo de migração para projeto Supabase separado: spans > 5M/dia OU storage_obs > 50% OU latência app > +20% (ref: pitch.md §rabbit-holes)
