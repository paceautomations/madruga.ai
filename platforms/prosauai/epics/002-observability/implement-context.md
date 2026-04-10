### T001 — DONE
- Add OTel dependencies to `pyproject.toml`: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-h
- Files: pyproject.toml
- Tokens in/out: 12/2221

### T002 — DONE
- [P] Create ADR-020 (Phoenix substitui LangFuse v3, supersedes ADR-007) in `platforms/prosauai/decisions/ADR-020-phoenix-observability.md`
- Files: platforms/prosauai/decisions/ADR-020-phoenix-observability.md
- Tokens in/out: 22/6378

### T003 — DONE
- [P] Mark ADR-007 as `Superseded by ADR-020` in `platforms/prosauai/decisions/ADR-007-*.md`
- Tokens in/out: 17/4110

### T004 — DONE
- [P] Create `prosauai/observability/__init__.py` package with module docstring
- Files: prosauai/observability/__init__.py
- Tokens in/out: 11/1853

### T005 — DONE
- [P] Update `.env.example` with new variables: `PHOENIX_GRPC_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_SAMPLER_ARG`, `TENANT_ID`, `DEPLOYMENT_ENV`, `OTEL_ENABLED`, `PHOENIX_SQL_DATABASE_URL`, `PHOENIX_PROJ
- Files: .env.example
- Tokens in/out: 18/2559

### T006 — DONE
- Add OTel/Phoenix settings fields to `prosauai/config.py`: `phoenix_grpc_endpoint`, `otel_service_name`, `otel_sampler_arg`, `tenant_id`, `deployment_env`, `otel_enabled`
- Files: prosauai/config.py
- Tokens in/out: 49/1842

### T007 — DONE
- [P] Create `prosauai/observability/conventions.py` with `SpanAttributes` constants: `TENANT_ID`, `PHONE_HASH`, `ROUTE`, `AGENT_ID`, `IS_GROUP`, `FROM_ME`, `GROUP_ID`, `MESSAGING_SYSTEM`, `MESSAGING_DE
- Files: prosauai/observability/conventions.py
- Tokens in/out: 15/2600

### T008 — DONE
- [P] Create `prosauai/observability/structlog_bridge.py` with `add_otel_context` processor that injects `trace_id` (32 hex) and `span_id` (16 hex) from active OTel span
- Files: prosauai/observability/structlog_bridge.py
- Tokens in/out: 15/3268

### T009 — DONE
- [P] Create `prosauai/observability/tracing.py` with helpers: `get_tracer()`, `inject_trace_context()` (W3C carrier serialize), `extract_trace_context()` (W3C carrier deserialize)
- Files: prosauai/observability/tracing.py
- Tokens in/out: 15/3263

### T010 — DONE
- Create `prosauai/observability/setup.py` with `configure_observability(settings)`: TracerProvider with Resource (`service.name`, `service.version`, `deployment.environment`, `tenant_id`), ParentBased+
- Files: prosauai/observability/setup.py, service.name, service.version, deployment.environment
- Tokens in/out: 18/4599

### T011 — DONE
- Wire `configure_observability(settings)` call in `prosauai/main.py` lifespan startup, add `add_otel_context` to structlog `shared_processors`
- Files: prosauai/main.py
- Tokens in/out: 14/3080

### T012 — DONE
- Add `phoenix` service to `docker-compose.yml`: image `arizephoenix/phoenix:latest`, ports 6006 (UI) + 4317 (gRPC), env `PHOENIX_SQL_DATABASE_URL` + `PHOENIX_PROJECT_NAME`, volume `phoenix_data`, healt
- Files: docker-compose.yml
- Tokens in/out: 15/3075

### T013 — DONE
- [P] [US7] Atualizar `platforms/prosauai/business/solution-overview.md` com features entregues no epic 001 (propostas D1.1, D1.2, D1.3)
- Files: platforms/prosauai/business/solution-overview.md
- Tokens in/out: 14/3909

### T014 — DONE
- [P] [US7] Atualizar folder structure em `platforms/prosauai/engineering/blueprint.md` §3 para refletir estrutura real do codigo (proposta D2.1)
- Files: platforms/prosauai/engineering/blueprint.md
- Tokens in/out: 16/3829

### T015 — DONE
- [P] [US7] Adicionar secao "Implementation Status" em `platforms/prosauai/engineering/containers.md` com status real dos containers (proposta D3.1)
- Files: platforms/prosauai/engineering/containers.md
- Tokens in/out: 11/2222

### T016 — DONE
- [P] [US7] Verificar e atualizar lifecycle em `platforms/prosauai/platform.yaml` (proposta D6.4)
- Files: platforms/prosauai/platform.yaml
- Tokens in/out: 10/1287

### T017 — DONE
- [US7] Validar que `platforms/prosauai/planning/roadmap.md` ja reflete epic 002 inserido (proposta D6.1-D6.3 — verificacao apenas)
- Files: platforms/prosauai/planning/roadmap.md
- Tokens in/out: 13/2788

### T018 — DONE
- [US7] Atualizar `platforms/prosauai/engineering/blueprint.md` §4.4 Observabilidade: Phoenix em vez de LangFuse
- Files: platforms/prosauai/engineering/blueprint.md
- Tokens in/out: 12/3098

### T019 — DONE
- [US7] Atualizar `platforms/prosauai/engineering/containers.md` com container `phoenix` no diagrama Mermaid e novo entry na Container Matrix
- Files: platforms/prosauai/engineering/containers.md
- Tokens in/out: 13/3165

### T020 — DONE
- [P] [US1] Write integration test in `tests/integration/test_trace_e2e.py`: mock OTel exporter (InMemorySpanExporter), send webhook request, assert trace has 5+ spans with correct hierarchy (webhook → 
- Files: tests/integration/test_trace_e2e.py
- Tokens in/out: 35/16859

### T021 — DONE
- [P] [US1] Write unit test in `tests/unit/test_pii_regression.py`: assert no span attribute in conventions.py or webhook code contains raw `phone`, raw `text`, or raw Evolution payload
- Files: tests/unit/test_pii_regression.py
- Tokens in/out: 11/6185

### T022 — DONE
- [US1] Add manual span `webhook_whatsapp` in `prosauai/api/webhooks.py` with attributes: `MESSAGING_SYSTEM="whatsapp"`, `MESSAGING_DESTINATION`, `MESSAGING_MESSAGE_ID`, `PHONE_HASH`, `IS_GROUP`, `FROM_
- Files: prosauai/api/webhooks.py
- Tokens in/out: 11/3494

### T023 — DONE
- [US1] Add manual span `route_message` in `prosauai/core/router.py` (or where route_message is called) with attributes: `ROUTE`, `IS_GROUP`, `FROM_ME`
- Files: prosauai/core/router.py
- Tokens in/out: 9/2485

### T024 — DONE
- [US1] Add manual span `send_echo` in echo send path (`prosauai/main.py` or `prosauai/api/webhooks.py`) with attributes: `PROVIDER_NAME="evolution"`, `GEN_AI_SYSTEM="echo"` (placeholder)
- Files: prosauai/main.py, prosauai/api/webhooks.py
- Tokens in/out: 14/3433

### T025 — DONE
- [P] [US3] Write integration test in `tests/integration/test_debounce_context.py`: serialize W3C trace context into Redis payload (RPUSH), read back (LRANGE+DEL), extract context, assert trace_id survi
- Files: tests/integration/test_debounce_context.py
- Tokens in/out: 38/12619

### T026 — DONE
- [P] [US3] Write integration test for legacy payload retrocompat in `tests/integration/test_debounce_context.py`: flush handler receives text-only payload (no trace_context), creates new trace graceful
- Files: tests/integration/test_debounce_context.py
- Tokens in/out: 9/4099

### T027 — DONE
- [US3] Rewrite Lua script in `prosauai/core/debounce.py`: change APPEND (string concat) to RPUSH (list). New append Lua: `RPUSH buf_key item` + `PEXPIRE` + `SET tmr_key`. Each item is JSON `{"text": ".
- Files: prosauai/core/debounce.py
- Tokens in/out: 12/4212

### T028 — DONE
- [US3] Rewrite flush Lua script in `prosauai/core/debounce.py`: `LRANGE buf_key 0 -1` + `DEL buf_key` (atomic in Lua). Returns list of JSON items
- Files: prosauai/core/debounce.py
- Tokens in/out: 21/7760

### T029 — DONE
- [US3] Update `DebounceManager.append` in `prosauai/core/debounce.py`: inject W3C trace context (`propagate.inject(carrier)`) into payload JSON before RPUSH. Add manual span `debounce.append` with `DEB
- Files: DebounceManager.append, prosauai/core/debounce.py, debounce.append
- Tokens in/out: 12/3677

### T030 — DONE
- [US3] Update `DebounceManager` flush handler in `prosauai/core/debounce.py`: parse JSON items from LRANGE, extract first item's trace_context as parent (`propagate.extract`), add remaining items as OT
- Files: prosauai/core/debounce.py, propagate.extract, debounce.flush
- Tokens in/out: 12/3208

### T031 — DONE
- [US3] Add retrocompat in flush handler in `prosauai/core/debounce.py`: if JSON parse fails (legacy text-only payload), treat as text without trace_context — degradation graciosa, new trace instead of 
- Files: prosauai/core/debounce.py
- Tokens in/out: 17/4390

### T032 — DONE
- [P] [US2] Write unit test in `tests/unit/test_structlog_bridge.py`: assert `add_otel_context` injects `trace_id` (32 hex) and `span_id` (16 hex) when active span exists
- Files: tests/unit/test_structlog_bridge.py
- Tokens in/out: 17/4324

### T033 — DONE
- [P] [US2] Write unit test in `tests/unit/test_structlog_bridge.py`: assert `add_otel_context` does NOT add trace_id/span_id when no active span (no false values)
- Files: tests/unit/test_structlog_bridge.py
- Tokens in/out: 10/2931

### T034 — DONE
- [US2] Validate structlog bridge wiring in `prosauai/main.py`: confirm `add_otel_context` is in `shared_processors` after `merge_contextvars` and before renderer. Verify log output contains `trace_id` 
- Files: prosauai/main.py
- Tokens in/out: 21/10542

### T035 — DONE
- [US5] Extend `HealthResponse` in `prosauai/api/health.py`: add `ObservabilityHealth` model with `status: Literal["ok", "degraded"]` and `last_export_success: bool`. Wire into health endpoint to report
- Files: prosauai/api/health.py
- Tokens in/out: 26/7080

### T036 — DONE
- [US5] Update `tests/integration/test_health.py` (or equivalent): assert `/health` response contains `observability` field with correct structure
- Files: tests/integration/test_health.py
- Tokens in/out: 15/4525

### T037 — DONE
- [US5] Validate Docker Compose stack: verify `docker-compose.yml` has correct depends_on (api depends on redis healthy, NOT on phoenix), phoenix volumes persisted, ports 6006+4317 exposed
- Files: docker-compose.yml
- Tokens in/out: 9/3502

### T038 — DONE
- [P] [US4] Create `phoenix-dashboards/README.md` with SpanQL query for dashboard (a): Jornada por trace_id — filter spans by trace_id, show waterfall
- Files: phoenix-dashboards/README.md
- Tokens in/out: 13/3396

### T039 — DONE
- [P] [US4] Add SpanQL query for dashboard (b) in `phoenix-dashboards/README.md`: Funil por rota — aggregate spans by `prosauai.route` attribute, show distribution by MessageRoute
- Files: phoenix-dashboards/README.md, prosauai.route
- Tokens in/out: 7/2253

### T040 — DONE
- [P] [US4] Add SpanQL query for dashboard (c) in `phoenix-dashboards/README.md`: Latencia por span — p50/p95/p99 por tipo de span (webhook, route, debounce, echo)
- Files: phoenix-dashboards/README.md
- Tokens in/out: 5/2459

### T041 — DONE
- [P] [US4] Add SpanQL query for dashboard (d) in `phoenix-dashboards/README.md`: Failure modes — aggregate ERROR spans by type (HMAC invalido, malformed payload, Redis indisponivel, Evolution 5xx) with
- Files: phoenix-dashboards/README.md
- Tokens in/out: 5/2462

### T042 — DONE
- [P] [US4] Add SpanQL query for dashboard (e) in `phoenix-dashboards/README.md`: Saude debounce — buffer_size distribution, wait_ms p50/p95, flush rate
- Files: phoenix-dashboards/README.md
- Tokens in/out: 5/2951

### T043 — DONE
- [US6] Validate `gen_ai.system="echo"` is set on send_echo span in `prosauai/api/webhooks.py` or echo send path (should be done in T024). Verify `gen_ai.request.model` is NOT set (null until epic 003)
- Files: prosauai/api/webhooks.py, gen_ai.request.model
- Tokens in/out: 11/2638

### T044 — DONE
- [US6] Write unit test in `tests/unit/test_conventions.py`: assert `SpanAttributes` class has `GEN_AI_SYSTEM`, `GEN_AI_REQUEST_MODEL` constants defined with correct OTel semantic convention values
- Files: tests/unit/test_conventions.py
- Tokens in/out: 10/2489

### T045 — DONE
- [P] Write unit test in `tests/unit/test_otel_setup.py`: assert `configure_observability` creates TracerProvider with correct Resource attributes, sampler config, and exporter. Assert no-op when `otel_
- Files: tests/unit/test_otel_setup.py
- Tokens in/out: 1320/12026

### T046 — DONE
- Run benchmark: measure webhook latency p95 before/after instrumentation — verify overhead < 5ms. Document results in `platforms/prosauai/epics/002-observability/decisions.md`
- Files: platforms/prosauai/epics/002-observability/decisions.md
- Tokens in/out: 46/13343

### T047 — DONE
- [P] Create `platforms/prosauai/engineering/observability.md`: guia operacional "como debugar uma mensagem ponta-a-ponta" — runbook com exemplos reais (por message_id, por trace_id, correlacao log-trac
- Files: platforms/prosauai/engineering/observability.md
- Tokens in/out: 16/9582

### T048 — DONE
- [P] Update README do repo prosauai: adicionar secao "Observability" com "como abrir Phoenix UI" + "como debugar uma msg" + link para `engineering/observability.md`
- Files: engineering/observability.md
- Tokens in/out: 13/2574

### T049 — DONE
- Validate all existing tests still pass (122+ tests from epic 001) with OTel instrumentation active via `OTEL_SDK_DISABLED=true` — zero regressions
- Tokens in/out: 75/19992

### T050 — DONE
- Run `ruff check .` — zero errors. Run `ruff format --check .` — zero formatting issues
- Tokens in/out: 16/2477

### T051 — DONE
- Run quickstart.md validation: follow steps from `platforms/prosauai/epics/002-observability/quickstart.md` end-to-end and verify all commands work
- Files: platforms/prosauai/epics/002-observability/quickstart.md
- Tokens in/out: 43/7595

