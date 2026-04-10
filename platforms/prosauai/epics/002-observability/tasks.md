# Tasks: Observability — Tracing Total da Jornada de Mensagem

**Input**: Design documents from `platforms/prosauai/epics/002-observability/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/observability-api.md, quickstart.md

**Tests**: Included — Constitution Principle VII (TDD) requires tests. 8+ new tests covering E2E trace, structlog bridge, W3C round-trip, PII regression.

**Organization**: Tasks grouped by user story. D0 (doc sync) runs first as pre-implementation prerequisite. Foundational phase sets up SDK + infra before story-specific work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **prosauai repository**: `prosauai/` (source), `tests/` (tests), root config files
- **Platform docs**: `platforms/prosauai/` (architecture docs, engineering, business)
- **Epic docs**: `platforms/prosauai/epics/002-observability/` (this epic's artifacts)

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Dependencies, ADR, and architectural documentation updates that define the technical foundation.

- [X] T001 Add OTel dependencies to `pyproject.toml`: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-redis`, `arize-phoenix-otel`
- [X] T002 [P] Create ADR-020 (Phoenix substitui LangFuse v3, supersedes ADR-007) in `platforms/prosauai/decisions/ADR-020-phoenix-observability.md`
- [X] T003 [P] Mark ADR-007 as `Superseded by ADR-020` in `platforms/prosauai/decisions/ADR-007-*.md`
- [X] T004 [P] Create `prosauai/observability/__init__.py` package with module docstring
- [X] T005 [P] Update `.env.example` with new variables: `PHOENIX_GRPC_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_SAMPLER_ARG`, `TENANT_ID`, `DEPLOYMENT_ENV`, `OTEL_ENABLED`, `PHOENIX_SQL_DATABASE_URL`, `PHOENIX_PROJECT_NAME`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: OTel SDK setup, conventions, structlog bridge, Docker compose with Phoenix, and Settings extension. MUST be complete before ANY user story implementation.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Add OTel/Phoenix settings fields to `prosauai/config.py`: `phoenix_grpc_endpoint`, `otel_service_name`, `otel_sampler_arg`, `tenant_id`, `deployment_env`, `otel_enabled`
- [X] T007 [P] Create `prosauai/observability/conventions.py` with `SpanAttributes` constants: `TENANT_ID`, `PHONE_HASH`, `ROUTE`, `AGENT_ID`, `IS_GROUP`, `FROM_ME`, `GROUP_ID`, `MESSAGING_SYSTEM`, `MESSAGING_DESTINATION`, `MESSAGING_MESSAGE_ID`, `DEBOUNCE_BUFFER_SIZE`, `DEBOUNCE_WAIT_MS`, `PROVIDER_NAME`, `PROVIDER_HTTP_STATUS`, `GEN_AI_SYSTEM`, `GEN_AI_REQUEST_MODEL`
- [X] T008 [P] Create `prosauai/observability/structlog_bridge.py` with `add_otel_context` processor that injects `trace_id` (32 hex) and `span_id` (16 hex) from active OTel span
- [X] T009 [P] Create `prosauai/observability/tracing.py` with helpers: `get_tracer()`, `inject_trace_context()` (W3C carrier serialize), `extract_trace_context()` (W3C carrier deserialize)
- [X] T010 Create `prosauai/observability/setup.py` with `configure_observability(settings)`: TracerProvider with Resource (`service.name`, `service.version`, `deployment.environment`, `tenant_id`), ParentBased+TraceIdRatioBased sampler, BatchSpanProcessor, OTLPSpanExporter (gRPC), auto-instrument FastAPI/httpx/redis. No-op if `settings.otel_enabled == False`
- [X] T011 Wire `configure_observability(settings)` call in `prosauai/main.py` lifespan startup, add `add_otel_context` to structlog `shared_processors`
- [X] T012 Add `phoenix` service to `docker-compose.yml`: image `arizephoenix/phoenix:latest`, ports 6006 (UI) + 4317 (gRPC), env `PHOENIX_SQL_DATABASE_URL` + `PHOENIX_PROJECT_NAME`, volume `phoenix_data`, healthcheck on `/healthz`, `start_period: 30s`

**Checkpoint**: `docker compose up` sobe 3 containers. OTel SDK configurado. Logs contêm `trace_id`/`span_id` para requests FastAPI.

---

## Phase 3: User Story 7 — D0: Sync Documental (Priority: P1)

**Goal**: Aplicar 12 propostas de atualização pendentes do reconcile do epic 001 nos 4 documentos afetados, zerando o drift documental antes de implementar.

**Independent Test**: Verificar que os 4 docs refletem as entregas do epic 001 e que os itens D0 estão resolvidos.

### Implementation for User Story 7

- [X] T013 [P] [US7] Atualizar `platforms/prosauai/business/solution-overview.md` com features entregues no epic 001 (propostas D1.1, D1.2, D1.3)
- [X] T014 [P] [US7] Atualizar folder structure em `platforms/prosauai/engineering/blueprint.md` §3 para refletir estrutura real do codigo (proposta D2.1)
- [X] T015 [P] [US7] Adicionar secao "Implementation Status" em `platforms/prosauai/engineering/containers.md` com status real dos containers (proposta D3.1)
- [X] T016 [P] [US7] Verificar e atualizar lifecycle em `platforms/prosauai/platform.yaml` (proposta D6.4)
- [X] T017 [US7] Validar que `platforms/prosauai/planning/roadmap.md` ja reflete epic 002 inserido (proposta D6.1-D6.3 — verificacao apenas)
- [X] T018 [US7] Atualizar `platforms/prosauai/engineering/blueprint.md` §4.4 Observabilidade: Phoenix em vez de LangFuse
- [X] T019 [US7] Atualizar `platforms/prosauai/engineering/containers.md` com container `phoenix` no diagrama Mermaid e novo entry na Container Matrix

**Checkpoint**: 4+ docs atualizados. Drift score do epic 001 = 0%. ADR-020 publicado.

---

## Phase 4: User Story 1 — Debug de Mensagem por ID (Priority: P1)

**Goal**: Cada mensagem processada gera um trace completo com 7+ spans visivel no Phoenix — do webhook ao echo — permitindo debug em menos de 30s.

**Independent Test**: Enviar 1 mensagem via webhook e verificar no Phoenix (ou InMemorySpanExporter) que o trace contem spans: webhook_whatsapp → route_message → debounce.append → debounce.flush → send_echo.

### Tests for User Story 1

- [X] T020 [P] [US1] Write integration test in `tests/integration/test_trace_e2e.py`: mock OTel exporter (InMemorySpanExporter), send webhook request, assert trace has 5+ spans with correct hierarchy (webhook → route → append → flush → echo) and correct attributes
- [X] T021 [P] [US1] Write unit test in `tests/unit/test_pii_regression.py`: assert no span attribute in conventions.py or webhook code contains raw `phone`, raw `text`, or raw Evolution payload

### Implementation for User Story 1

- [X] T022 [US1] Add manual span `webhook_whatsapp` in `prosauai/api/webhooks.py` with attributes: `MESSAGING_SYSTEM="whatsapp"`, `MESSAGING_DESTINATION`, `MESSAGING_MESSAGE_ID`, `PHONE_HASH`, `IS_GROUP`, `FROM_ME`, `GROUP_ID`, `TENANT_ID`
- [X] T023 [US1] Add manual span `route_message` in `prosauai/core/router.py` (or where route_message is called) with attributes: `ROUTE`, `IS_GROUP`, `FROM_ME`
- [X] T024 [US1] Add manual span `send_echo` in echo send path (`prosauai/main.py` or `prosauai/api/webhooks.py`) with attributes: `PROVIDER_NAME="evolution"`, `GEN_AI_SYSTEM="echo"` (placeholder)

**Checkpoint**: 1 mensagem → trace com 5+ spans visivel via InMemorySpanExporter em testes. PII zero verificada.

---

## Phase 5: User Story 3 — Trace Continuo no Debounce (Priority: P1)

**Goal**: Multiplas mensagens rapidas do mesmo remetente geram 1 trace continuo — appends individuais + flush final como spans de uma mesma arvore via W3C Trace Context propagado pelo Redis.

**Independent Test**: Enviar 3 mensagens rapidas para o mesmo numero e verificar que existe 1 trace com 3 sub-spans `debounce.append` e 1 span `debounce.flush` conectados.

### Tests for User Story 3

- [X] T025 [P] [US3] Write integration test in `tests/integration/test_debounce_context.py`: serialize W3C trace context into Redis payload (RPUSH), read back (LRANGE+DEL), extract context, assert trace_id survives round-trip and parent relationship is correct
- [X] T026 [P] [US3] Write integration test for legacy payload retrocompat in `tests/integration/test_debounce_context.py`: flush handler receives text-only payload (no trace_context), creates new trace gracefully without error

### Implementation for User Story 3

- [X] T027 [US3] Rewrite Lua script in `prosauai/core/debounce.py`: change APPEND (string concat) to RPUSH (list). New append Lua: `RPUSH buf_key item` + `PEXPIRE` + `SET tmr_key`. Each item is JSON `{"text": "...", "trace_context": {...}}`
- [X] T028 [US3] Rewrite flush Lua script in `prosauai/core/debounce.py`: `LRANGE buf_key 0 -1` + `DEL buf_key` (atomic in Lua). Returns list of JSON items
- [X] T029 [US3] Update `DebounceManager.append` in `prosauai/core/debounce.py`: inject W3C trace context (`propagate.inject(carrier)`) into payload JSON before RPUSH. Add manual span `debounce.append` with `DEBOUNCE_BUFFER_SIZE` attribute
- [X] T030 [US3] Update `DebounceManager` flush handler in `prosauai/core/debounce.py`: parse JSON items from LRANGE, extract first item's trace_context as parent (`propagate.extract`), add remaining items as OTel Links. Open span `debounce.flush` as child of restored context with `DEBOUNCE_WAIT_MS` attribute. Concatenate texts with `\n` for echo
- [X] T031 [US3] Add retrocompat in flush handler in `prosauai/core/debounce.py`: if JSON parse fails (legacy text-only payload), treat as text without trace_context — degradation graciosa, new trace instead of continued

**Checkpoint**: 3 msgs rapidas → 1 trace continuo com 3 spans append + 1 span flush. Legacy payloads degradam graciosamente.

---

## Phase 6: User Story 2 — Correlacao Log-Trace (Priority: P1)

**Goal**: Todo log estruturado emitido pelo structlog contem `trace_id` e `span_id` do contexto OTel ativo, permitindo navegacao bidirecional entre logs e traces.

**Independent Test**: Verificar que qualquer request ao API gera logs JSON com campos `trace_id` e `span_id` preenchidos, e que fora de contexto OTel esses campos estao ausentes.

### Tests for User Story 2

- [X] T032 [P] [US2] Write unit test in `tests/unit/test_structlog_bridge.py`: assert `add_otel_context` injects `trace_id` (32 hex) and `span_id` (16 hex) when active span exists
- [X] T033 [P] [US2] Write unit test in `tests/unit/test_structlog_bridge.py`: assert `add_otel_context` does NOT add trace_id/span_id when no active span (no false values)

### Implementation for User Story 2

- [X] T034 [US2] Validate structlog bridge wiring in `prosauai/main.py`: confirm `add_otel_context` is in `shared_processors` after `merge_contextvars` and before renderer. Verify log output contains `trace_id` and `span_id` for requests

**Checkpoint**: Logs contêm `trace_id`/`span_id` para todas as requests. Sem campos falsos fora de contexto OTel.

---

## Phase 7: User Story 5 — Stack Unico com Docker Compose (Priority: P2)

**Goal**: `docker compose up` sobe Phoenix junto com prosauai-api e redis automaticamente — observabilidade sempre disponivel sem configuracao extra.

**Independent Test**: Executar `docker compose up` em ambiente limpo e verificar que 3 containers sobem healthy em <60s, Phoenix UI acessivel em `:6006`.

### Implementation for User Story 5

- [X] T035 [US5] Extend `HealthResponse` in `prosauai/api/health.py`: add `ObservabilityHealth` model with `status: Literal["ok", "degraded"]` and `last_export_success: bool`. Wire into health endpoint to report OTel exporter status (never 503 for OTel failure)
- [X] T036 [US5] Update `tests/integration/test_health.py` (or equivalent): assert `/health` response contains `observability` field with correct structure
- [X] T037 [US5] Validate Docker Compose stack: verify `docker-compose.yml` has correct depends_on (api depends on redis healthy, NOT on phoenix), phoenix volumes persisted, ports 6006+4317 exposed

**Checkpoint**: `docker compose up` → 3 containers healthy. `/health` retorna campo `observability`. Phoenix UI em `:6006`.

---

## Phase 8: User Story 4 — Dashboards Operacionais (Priority: P2)

**Goal**: 5 dashboards curados no Phoenix documentados como SpanQL queries versionadas — jornada, funil, latencia, failure modes, saude debounce.

**Independent Test**: Verificar que as 5 queries SpanQL estao documentadas e executam sem erro no Phoenix (apos traces existirem).

### Implementation for User Story 4

- [X] T038 [P] [US4] Create `phoenix-dashboards/README.md` with SpanQL query for dashboard (a): Jornada por trace_id — filter spans by trace_id, show waterfall
- [X] T039 [P] [US4] Add SpanQL query for dashboard (b) in `phoenix-dashboards/README.md`: Funil por rota — aggregate spans by `prosauai.route` attribute, show distribution by MessageRoute
- [X] T040 [P] [US4] Add SpanQL query for dashboard (c) in `phoenix-dashboards/README.md`: Latencia por span — p50/p95/p99 por tipo de span (webhook, route, debounce, echo)
- [X] T041 [P] [US4] Add SpanQL query for dashboard (d) in `phoenix-dashboards/README.md`: Failure modes — aggregate ERROR spans by type (HMAC invalido, malformed payload, Redis indisponivel, Evolution 5xx) with count + last_seen
- [X] T042 [P] [US4] Add SpanQL query for dashboard (e) in `phoenix-dashboards/README.md`: Saude debounce — buffer_size distribution, wait_ms p50/p95, flush rate

**Checkpoint**: 5 SpanQL queries documentadas e versionadas em `phoenix-dashboards/README.md`.

---

## Phase 9: User Story 6 — Forward-Compat para LLM Tracing (Priority: P3)

**Goal**: Spans ja incluem atributos placeholder `gen_ai.*` (OTel GenAI Semantic Conventions) para que epic 003 aceite novos atributos sem refactor.

**Independent Test**: Verificar que spans de echo possuem `gen_ai.system="echo"` e que conventions.py tem constantes `GEN_AI_*`.

### Implementation for User Story 6

- [X] T043 [US6] Validate `gen_ai.system="echo"` is set on send_echo span in `prosauai/api/webhooks.py` or echo send path (should be done in T024). Verify `gen_ai.request.model` is NOT set (null until epic 003)
- [X] T044 [US6] Write unit test in `tests/unit/test_conventions.py`: assert `SpanAttributes` class has `GEN_AI_SYSTEM`, `GEN_AI_REQUEST_MODEL` constants defined with correct OTel semantic convention values

**Checkpoint**: Spans de echo contêm `gen_ai.system="echo"`. Conventions prontas para epic 003.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: E2E validation, benchmark, operational documentation, code cleanup.

- [X] T045 [P] Write unit test in `tests/unit/test_otel_setup.py`: assert `configure_observability` creates TracerProvider with correct Resource attributes, sampler config, and exporter. Assert no-op when `otel_enabled=False`
- [X] T046 Run benchmark: measure webhook latency p95 before/after instrumentation — verify overhead < 5ms. Document results in `platforms/prosauai/epics/002-observability/decisions.md`
- [X] T047 [P] Create `platforms/prosauai/engineering/observability.md`: guia operacional "como debugar uma mensagem ponta-a-ponta" — runbook com exemplos reais (por message_id, por trace_id, correlacao log-trace, debounce debugging)
- [X] T048 [P] Update README do repo prosauai: adicionar secao "Observability" com "como abrir Phoenix UI" + "como debugar uma msg" + link para `engineering/observability.md`
- [X] T049 Validate all existing tests still pass (122+ tests from epic 001) with OTel instrumentation active via `OTEL_SDK_DISABLED=true` — zero regressions
- [X] T050 Run `ruff check .` — zero errors. Run `ruff format --check .` — zero formatting issues
- [X] T051 Run quickstart.md validation: follow steps from `platforms/prosauai/epics/002-observability/quickstart.md` end-to-end and verify all commands work

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on T001 (deps) and T006 (settings) — BLOCKS all user stories
- **US7 D0 Doc Sync (Phase 3)**: Can start in PARALLEL with Phase 2 — doc edits have no code dependency
- **US1 Debug (Phase 4)**: Depends on Phase 2 completion (SDK + auto-instrumentation must be wired)
- **US3 Trace Continuo (Phase 5)**: Depends on Phase 2 (SDK) — can run in parallel with Phase 4
- **US2 Correlacao (Phase 6)**: Depends on Phase 2 (structlog bridge already wired in T011) — mostly validation
- **US5 Docker Compose (Phase 7)**: Depends on T012 (phoenix container) from Phase 2 — health extension is independent
- **US4 Dashboards (Phase 8)**: Can start after Phase 2 — independent of code implementation
- **US6 Forward-Compat (Phase 9)**: Depends on T024 (send_echo span) from Phase 4
- **Polish (Phase 10)**: Depends on all user story phases complete

### User Story Dependencies

- **US7 (P1)**: Independent — doc edits only, can start Day 1
- **US1 (P1)**: Depends on Foundational (Phase 2) — needs OTel SDK wired
- **US3 (P1)**: Depends on Foundational (Phase 2) — needs OTel SDK + tracing helpers
- **US2 (P1)**: Depends on Foundational (Phase 2) — structlog bridge wired in T011
- **US5 (P2)**: Depends on T012 (compose) from Foundational
- **US4 (P2)**: No code dependencies — SpanQL queries are documentation
- **US6 (P3)**: Depends on T024 (send_echo span) from US1

### Within Each User Story

- Tests written FIRST (TDD — Constitution Principle VII)
- Core infrastructure before domain-specific spans
- Manual spans before W3C propagation
- Lua script rewrite before context injection
- Validation after each checkpoint

### Parallel Opportunities

- T002, T003, T004, T005 can all run in parallel (Setup phase — different files)
- T007, T008, T009 can run in parallel (Foundational — different new files)
- T013, T014, T015, T016 can run in parallel (D0 — different platform docs)
- T020, T021 can run in parallel (US1 tests — different test files)
- T025, T026 can run in parallel (US3 tests — same file but independent tests)
- T032, T033 can run in parallel (US2 tests — same file but independent tests)
- T038-T042 can all run in parallel (dashboards — same file but independent queries)
- T045, T047, T048 can run in parallel (Polish — different files)
- Phase 3 (US7) runs entirely in parallel with Phase 2 (Foundational)

---

## Parallel Example: Foundational Phase

```bash
# Launch all new observability module files in parallel:
Task: T007 "Create conventions.py in prosauai/observability/conventions.py"
Task: T008 "Create structlog_bridge.py in prosauai/observability/structlog_bridge.py"
Task: T009 "Create tracing.py in prosauai/observability/tracing.py"

# Then sequentially (depends on above):
Task: T010 "Create setup.py in prosauai/observability/setup.py"
Task: T011 "Wire configure_observability in prosauai/main.py"
```

## Parallel Example: D0 Doc Sync (runs alongside Foundational)

```bash
# All doc updates in parallel:
Task: T013 "Update solution-overview.md"
Task: T014 "Update blueprint.md §3"
Task: T015 "Update containers.md"
Task: T016 "Update platform.yaml"
```

---

## Implementation Strategy

### MVP First (US7 + US1 + US3 + US2)

1. Complete Phase 1: Setup (deps + ADR)
2. Complete Phase 2: Foundational (SDK + compose) IN PARALLEL with Phase 3: US7 (D0)
3. Complete Phase 4: US1 (manual spans)
4. Complete Phase 5: US3 (W3C propagation + Lua rewrite)
5. Complete Phase 6: US2 (validate correlacao)
6. **STOP and VALIDATE**: 1 mensagem → trace completo. 3 msgs → trace continuo. Logs correlacionados.
7. Deploy/demo if ready — core tracing is the MVP

### Incremental Delivery

1. Setup + Foundational + D0 → Infrastructure ready, docs aligned
2. Add US1 → Manual spans, basic tracing → Validate single message trace
3. Add US3 → W3C propagation → Validate debounce trace continuity (FULL MVP)
4. Add US2 → Validate log↔trace correlation
5. Add US5 → Health extension, compose polish
6. Add US4 → Dashboards for operational visibility
7. Add US6 → Forward-compat placeholder attributes
8. Polish → Tests, benchmark, operational docs

### Critical Path

```
T001 (deps) → T006 (settings) → T010 (setup.py) → T011 (wire main.py)
  → T022-T024 (manual spans) → T027-T031 (W3C propagation + Lua)
  → T049 (validate no regressions) → T050 (lint clean)
```

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 51 |
| Phase 1 (Setup) | 5 tasks |
| Phase 2 (Foundational) | 7 tasks |
| Phase 3 — US7 D0 Doc Sync (P1) | 7 tasks |
| Phase 4 — US1 Debug (P1) | 5 tasks |
| Phase 5 — US3 Trace Continuo (P1) | 7 tasks |
| Phase 6 — US2 Correlacao (P1) | 3 tasks |
| Phase 7 — US5 Docker Compose (P2) | 3 tasks |
| Phase 8 — US4 Dashboards (P2) | 5 tasks |
| Phase 9 — US6 Forward-Compat (P3) | 2 tasks |
| Phase 10 (Polish) | 7 tasks |
| Parallel opportunities | 22 tasks marked [P] |
| Tests included | 10 test tasks (TDD) |
| Estimated LOC | ~1055 (per plan.md) |
| Estimated effort | ~6 dias uteis |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Constitution Principle VII (TDD): tests written first, verify they fail, then implement
- Commit after each phase or logical group
- Stop at any checkpoint to validate independently
- PII zero: never raw phone, never raw text, never raw Evolution payload in any span attribute
- OTel SDK disabled in regular tests (`OTEL_SDK_DISABLED=true`), InMemorySpanExporter for observability tests

---

handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "51 tasks organizadas em 10 fases (setup + foundational + 7 user stories + polish). 22 tasks parallelizaveis. 10 test tasks (TDD). MVP = US7+US1+US3+US2 (P1). Critical path: deps → settings → setup.py → wire main.py → manual spans → W3C propagation. ~1055 LOC, ~6 dias."
  blockers: []
  confidence: Alta
  kill_criteria: "Se Phoenix >=8.0 nao suportar Postgres backend, ou se OTel auto-instrumentation for incompativel com FastAPI lifespan tasks, a abordagem precisa ser revisada."
