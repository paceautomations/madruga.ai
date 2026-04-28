# Tasks: Agent Pipeline Steps — sub-routing configurável por agente

**Input**: Design documents from `platforms/prosauai/epics/015-agent-pipeline-steps/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/openapi.yaml, research.md, quickstart.md
**Branch**: `epic/prosauai/015-agent-pipeline-steps`
**Repo**: `paceautomations/prosauai` (external — checkout in main clone, ADR-024)

**Tests**: TDD enforced for the executor core (PR-2) and condition evaluator (PR-2). Test tasks are written FIRST per phase per the spec's hard-gate compatibility invariant (FR-070, SC-008).

**Organization**: Tasks are grouped by user story so each P1 story can be merged independently. P2 stories (US3, US4, US5 frontend) are cut-line sensitive — see Phase 8 cut-line decision.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1, US2, US3, US4, US5, US6) — phases without a story tag are shared
- File paths are absolute relative to repo root (`paceautomations/prosauai`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm working environment, dependencies, and pre-existing scaffolding.

- [x] T001 Verify branch `epic/prosauai/015-agent-pipeline-steps` is checked out and current (`git branch --show-current`); confirm `paceautomations/prosauai` repo at the path resolved by `python3 .specify/scripts/ensure_repo.py prosauai`
- [x] T002 [P] Confirm Python deps in `apps/api/pyproject.toml` are at minimum versions stated in plan.md (FastAPI ≥0.135, asyncpg ≥0.31, pydantic ≥2.12, pydantic-ai ≥1.80, structlog ≥25.0, opentelemetry-sdk 1.39.x); zero new deps to add
- [x] T003 [P] Confirm dbmate migration scaffold exists at `apps/api/db/migrations/` and `dbmate up` runs cleanly against a fresh testcontainers Postgres
- [x] T004 [P] Read `apps/api/prosauai/conversation/pipeline.py` and `apps/api/prosauai/conversation/agent.py` end-to-end and document in `decisions.md` (under `## Implementation Decisions`) the exact insertion point for the executor branch — line numbers + helper signature

**Checkpoint**: Environment verified, no surprises in upstream code.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, shared modules, and protocol-level types that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until Phase 2 is complete (gates PR-1 + scaffolds PR-2).

### PR-1 — Schema base

- [x] T010 Create migration `apps/api/db/migrations/20260601000010_create_agent_pipeline_steps.sql` matching `data-model.md` § Migration 1 (table + RLS policy + 2 indexes + `set_updated_at` trigger + comments) — idempotent via `IF NOT EXISTS` (FR-072)
- [x] T011 Create migration `apps/api/db/migrations/20260601000011_alter_trace_steps_sub_steps.sql` adding `sub_steps JSONB NULL` to `public.trace_steps` with comment from `data-model.md` § Migration 2 — `ADD COLUMN IF NOT EXISTS` (FR-072)
- [x] T012 [P] Create constant module `apps/api/prosauai/conversation/pipeline_constants.py` with `MAX_PIPELINE_STEPS_PER_AGENT = 5`, `MAX_CONFIG_BYTES = 16_384`, `MAX_SUB_STEP_BYTES = 4_096`, `MAX_SUB_STEPS_TOTAL_BYTES = 32_768`, `DEFAULT_STEP_TIMEOUT_SECONDS = 30`, `MAX_STEP_TIMEOUT_SECONDS = 60` (avoids import cycles)
- [x] T013 Create repository `apps/api/prosauai/db/queries/pipeline_steps.py` with `PipelineStepRow` dataclass + `list_active_steps(conn, agent_id)` (returns `list[PipelineStepRow]`, ordered by `step_order`) + `replace_steps(conn, agent_id, steps_json)` (atomic transaction `BEGIN; DELETE; INSERT…; COMMIT`) + `validate_steps_payload(steps_json)` (returns `list[ValidationError]` per `data-model.md` § Validation rules 1–7)
- [x] T014 [P] Write integration test `apps/api/tests/integration/test_pipeline_steps_repository_pg.py` covering: (a) list returns `[]` for agent with no rows; (b) UNIQUE(agent_id, step_order) enforced; (c) RLS isolates tenant A from tenant B; (d) `step_order` CHECK rejects 0 and 6; (e) `octet_length(config) > 16384` rejected; (f) `replace_steps` is atomic (rollback on failure leaves prior state); (g) `validate_steps_payload` returns specific errors for each violation in § Validation rules — uses testcontainers-postgres + dbmate

### Cross-cutting types and protocol

- [x] T015 [P] Create `apps/api/prosauai/conversation/pipeline_state.py` with `@dataclass PipelineState` carrying `classifier|clarifier|resolver|specialist|summarizer: dict | None`, `summarized_context: str | None`, `context: dict`, and `to_scope() -> dict` shaping the dict consumed by `condition.evaluate` (FR-022, FR-024)
- [x] T016 [P] Create `apps/api/prosauai/conversation/condition.py` with `evaluate(condition: dict | None, scope: dict) -> bool` per FR-024 — supports operators `<,>,<=,>=,==,!=,in`, AND-implicit across keys, dotted-path resolver with `_MISSING` sentinel; chave inexistente OR parse error returns `False` and emits structlog `condition_eval_skipped` with dedup-once-per-(agent_id, step_index) via `functools.lru_cache` of warning fingerprint
- [x] T017 [P] Write unit test `apps/api/tests/conversation/test_condition.py` with ≥30 cases covering: each operator with int/float/string literals, `in [a,b,c]` literal-list parser, AND-implicit (2 keys, both true → true; one false → false), dotted-path miss → false (no exception), syntactically broken predicate (e.g. `>>>0.5`) → false + warning, `condition is None` → true, `condition == {}` → true, dedup of warnings (single warning across 100 evaluations of the same broken condition)
- [x] T018 [P] Create `apps/api/prosauai/conversation/steps/__init__.py` with module-level registry `STEP_TYPE_REGISTRY: dict[str, type[PipelineStep]]` (initially empty, populated by step type tasks)
- [x] T019 [P] Create `apps/api/prosauai/conversation/steps/base.py` with `Protocol PipelineStep` (signature per plan.md PR-2 § "steps/base.py") + `@dataclass StepResult` (`output: dict`, `text_for_customer: str | None`, `model_used: str | None`, `tokens_in: int`, `tokens_out: int`, `cost_usd: Decimal`, `tool_calls: list | None`, `latency_ms: int`)

**Checkpoint**: Foundation ready — schema + indexes + RLS + cross-cutting modules + Protocol committed. Repository tests green. User story implementation can now begin in parallel where files allow.

---

## Phase 3: User Story 1 — Reduzir custo do agente generalista (Priority: P1) 🎯 MVP

**Goal**: configurar 2 pipeline steps (classifier + specialist) reduz custo médio ≥30% e latência p95 ≤1 s para casos triviais (SC-001, SC-002), sem regressão de QS (SC-003).

**Independent Test**: ver `quickstart.md` — configurar via SQL um agente `ariel-test` com classifier `gpt-5-nano` + specialist `routing_map` em `pace-internal`, processar 20 mensagens reais (greetings + billing) e verificar via SQL/trace que `messages.metadata.model_used` reflete o routing, custo médio das `greeting` cai ≥50% vs. baseline.

### Tests for User Story 1 (write FIRST — TDD per Constitution Check VII) ⚠️

- [x] T020 [P] [US1] Write unit test `apps/api/tests/conversation/test_steps_classifier.py` covering: output schema `{intent, confidence, explanation}` validates; intent outside `intent_labels` → step still emits StepResult (validator does NOT raise — caller decides); pydantic-ai Agent invoked with prompt referenced by `prompt_slug`; mock LLM returns malformed JSON → step raises ValidationError (caught upstream as step error)
- [x] T021 [P] [US1] Write unit test `apps/api/tests/conversation/test_steps_specialist.py` covering: `routing_map.get(state.classifier.intent, default_model)` selects correct model; `state.classifier is None` (no preceding classifier) → uses `default_model`; intent not in `routing_map` → falls back to `default_model`; tool calls flow through (mock tool registry); `text_for_customer` populated from agent output
- [x] T022 [P] [US1] Write unit test `apps/api/tests/conversation/test_pipeline_executor.py` covering executor flows with mock `PipelineStep`s: (a) two-step linear success (classifier → specialist), state correctly chained; (b) terminating step short-circuits subsequent (specialist not called when prior step set `text_for_customer`); (c) timeout on a step → step.status=error, subsequent skipped, fallback canned returned; (d) `routing_map` cost aggregate = sum of step costs; (e) snapshot atomicity — modifying `steps` list after execute starts has zero effect
- [x] T023 [P] [US1] Write integration test `apps/api/tests/integration/test_pipeline_executor_pg.py` end-to-end: insert 2 steps via repository, build full `ConversationDeps` against testcontainers Postgres, drive executor with stubbed pydantic-ai Agents (deterministic outputs), assert: row written to `trace_steps` for `generate_response` includes `sub_steps` JSONB array of length 2, `messages.metadata.terminating_step` populated, custo agregado correto

### Implementation for User Story 1

- [x] T024 [P] [US1] Implement `apps/api/prosauai/conversation/steps/classifier.py` — pydantic-ai `Agent[ClassifierDeps, ClassifierOutput]` with `output_type=ClassifierOutput` (Pydantic model `intent: str`, `confidence: float >= 0 and <= 1`, `explanation: str | None`). Loads `prompt_slug` via existing `prompts.version` lookup (D-PLAN-09). Registers in `STEP_TYPE_REGISTRY["classifier"]`
- [x] T025 [P] [US1] Implement `apps/api/prosauai/conversation/steps/specialist.py` — thin wrapper that selects `model = config.routing_map.get(state.classifier.intent if state.classifier else None, config.default_model)` and delegates to existing `agent.py:generate_response()` with `model_override`. Reuses sandwich prompt + tools + `ModelSettings`. `text_for_customer = result.response_text` (always terminating). Registers in `STEP_TYPE_REGISTRY["specialist"]`
- [x] T026 [US1] Implement `apps/api/prosauai/conversation/pipeline_executor.py` per plan.md PR-2 § "pipeline_executor.py" algorithm — `execute_agent_pipeline(...)` returns `PipelineExecutionResult` (final response, sub_steps list, aggregated cost/tokens/model). Uses `asyncio.wait_for(step_impl.execute(...), timeout=step_timeout)` per step. Catches `(asyncio.TimeoutError, ConnectionError, RuntimeError, ValidationError)` → fallback canned (depends on T024–T025)
- [x] T027 [US1] Modify `apps/api/prosauai/conversation/pipeline.py:_generate_with_retry()` to: (a) call `pipeline_steps_repo.list_active_steps(conn, agent_id)` once at entry under existing OTel span `conversation.generate`; (b) if list is empty → call existing `generate_response()` exactly as today (zero behavioral change); (c) else → delegate to `pipeline_executor.execute_agent_pipeline(...)`. Lookup uses per-tenant `pool` so RLS is enforced (depends on T013, T026)
- [x] T028 [US1] Add structured logging in executor at each step: `pipeline_step_start`, `pipeline_step_end`, `pipeline_step_skipped_condition`, `pipeline_step_failed` — each with `correlation_id` (trace_id), `agent_id`, `step_order`, `step_type`, `model`, `tokens`, `cost`, `latency_ms` (Constitution Principle IX)
- [x] T029 [US1] Add OTel sub-span `conversation.pipeline.step` per step with attributes `step.type`, `step.order`, `step.model`, `step.condition_evaluated`, `step.terminating`, `step.skipped_reason` (Constitution Principle IX)
- [x] T030 [US1] [P] Quickstart validation per `quickstart.md` § "Validar US1": INSERT `agent_pipeline_steps` rows for `ariel-test`, send 5 greetings + 5 billing requests, query `traces` and `messages.metadata`, document outcomes in `decisions.md` under `## US1 staging validation`

**Checkpoint**: US1 fully functional and testable independently. PRs 1–2 mergeable. Backward-compat hard gate (T050) MUST also be green before merge.

---

## Phase 4: User Story 2 — Desambiguar pedidos vagos antes de gerar resposta cara (Priority: P1)

**Goal**: clarifier step ativado por `condition: {"classifier.confidence": "<0.6"}` reduz taxa de retomadas em ≥30% (SC-004).

**Independent Test**: configurar 3 steps (classifier + clarifier com condition + specialist), enviar mensagem ambígua, verificar trace mostra clarifier executou e specialist foi `skipped`; com `confidence ≥ 0.6` clarifier vira `skipped`.

### Tests for User Story 2 (write FIRST) ⚠️

- [x] T040 [P] [US2] Write unit test `apps/api/tests/conversation/test_steps_clarifier.py` covering: output is short text question (length ≤ `max_question_length`, default 140); `text_for_customer` populated → terminates pipeline; pydantic-ai Agent receives prior classifier output as context; modelo cheap (`gpt-5-nano`) honored
- [x] T041 [P] [US2] Write unit test in `apps/api/tests/conversation/test_pipeline_executor.py` (extending T022) covering: (a) clarifier with `condition: {"classifier.confidence": "<0.6"}` skipped when classifier returns confidence=0.92; (b) clarifier executes when confidence=0.4 and terminates pipeline (specialist marked `skipped` with `reason: prior_step_terminated`); (c) malformed condition (`{"classifier.foo": "<0.6"}` — key inexistent) → step is `skipped` with `reason: condition_eval_skipped` (no crash)
- [x] T042 [P] [US2] Write integration test in `apps/api/tests/integration/test_pipeline_executor_pg.py` (extending T023) — 3-step pipeline classifier+clarifier+specialist, verify full row sequence in `trace_steps.sub_steps` array, `messages.metadata.terminating_step == "clarifier"` when clarifier fired

### Implementation for User Story 2

- [x] T043 [P] [US2] Implement `apps/api/prosauai/conversation/steps/clarifier.py` — pydantic-ai Agent text output with length validation in pydantic model (`max_question_length`). Sets `text_for_customer = output.question_text` (always terminating when it executes). Registers in `STEP_TYPE_REGISTRY["clarifier"]`
- [x] T044 [US2] Wire condition evaluation in `pipeline_executor.py` (already started in T026): before each step, call `condition.evaluate(step.condition, state.to_scope())`; on False → emit `StepRecord(status="skipped", output={"condition_evaluated": <repr>})` and `continue` (depends on T016, T026)
- [x] T045 [US2] When `result.text_for_customer is not None`, set `terminating_step = step.step_type` and break loop; mark all subsequent steps as `StepRecord(status="skipped", output={"reason": "prior_step_terminated"})` (depends on T026)
- [x] T046 [US2] [P] Quickstart validation per `quickstart.md` § "Validar US2": configure 3-step pipeline, send `"oi"` and `"qual o saldo da fatura de abril?"`, verify clarifier branch fires only on the ambiguous one, document results in `decisions.md`

**Checkpoint**: US1 + US2 deliver the MVP feature surface. Both use the same executor — clarifier is just another step type with a condition that gates it.

---

## Phase 5: User Story 6 — Operação default unchanged (Priority: P1) 🛡️ Hard regression gate

**Goal**: agentes sem pipeline_steps continuam executando exatamente como hoje. Hard gate de merge (SC-008, SC-010, FR-070, FR-071, FR-072).

**Independent Test**: rodar suite completa `pytest apps/api/tests/` antes do merge; comparar A/B em staging 1000 mensagens reais (com agente baseline vs. agente com `pipeline_steps=[]`); outputs estatisticamente equivalentes (≤1% margem em QS, custo, latência).

### Tests for User Story 6 (write FIRST — these gate the merge) ⚠️

- [x] T050 [P] [US6] Write `apps/api/tests/conversation/test_pipeline_backwards_compat.py`: fixture with agent that has zero rows in `agent_pipeline_steps`. Drive `_generate_with_retry` with deterministic mock LLM. Assert: `pipeline_executor.execute_agent_pipeline` is **never called** (mock with `assert_not_called`); `agent.py:generate_response` IS called exactly once; output is byte-equivalent to a baseline run on `develop` HEAD (snapshot test using stable seed)
- [x] T051 [P] [US6] Write benchmark `apps/api/tests/benchmarks/test_overhead_no_pipeline.py`: 100 iterations of `_generate_with_retry` with `pipeline_steps_repo.list_active_steps` returning `[]`; measure delta vs. a control run that bypasses the lookup; assert p95 delta ≤ **5 ms** (hard SC-010 gate). Fails the suite on regression
- [x] T052 [P] [US6] Confirm full existing test suite runs green: `cd apps/api && pytest tests/ -x --tb=short` produces zero failures, zero new warnings (FR-070). Document command + result in `decisions.md` under `## Backwards-compat verification`

### Implementation safeguards for User Story 6

- [x] T053 [US6] Inspect `step_record.py` modification (from T070 below) and verify `sub_steps: list[StepRecord] | None = None` default keeps existing constructor calls source-compatible (no fixture mass-update)
- [x] T054 [US6] Verify migration idempotency: run `dbmate up` twice on the same DB; second run is no-op (FR-072)
- [x] T055 [US6] Verify `messages.metadata` write path: when `pipeline_steps == []`, neither `terminating_step` nor `pipeline_step_count` nor `pipeline_version` is written (FR-064 negative case) — assert via direct SQL probe in T050

**Checkpoint**: 🛡️ HARD GATE. SC-008 + SC-010 verified. PR-2 mergeable. NO subsequent work proceeds if this phase fails.

---

## Phase 6: User Story 5 — Auditar execução de pipeline step por step (Priority: P2)

**Goal**: cada execução de pipeline step persiste como sub-row no trace, visível no Trace Explorer; engenheiro identifica step responsável por latência/erro em <1 minuto (SC-007, SC-012).

**Independent Test**: a partir de um `trace_id` de uma mensagem real processada com pipeline, expandir o step `generate_response` na UI do Trace Explorer e ver N sub-rows com mesmo formato visual dos top-level (waterfall, accordion).

### Backend — sub_steps persist (PR-3)

- [ ] T070 [US5] Modify `apps/api/prosauai/conversation/step_record.py` — add field `sub_steps: list[StepRecord] | None = None` to `StepRecord` dataclass; modify `_record_step` helper to accept and pass through `sub_steps` kwarg (depends on T010 schema migration applied)
- [ ] T071 [US5] Modify `apps/api/prosauai/conversation/trace_persist.py:persist_trace` — when `step.name == "generate_response"` and `step.sub_steps is not None`, serialize sub_steps to JSONB and INSERT into `trace_steps.sub_steps`. Apply truncation rules per `data-model.md` § "Truncation rules": each sub-step capped at 4 KB (input/output replaced with `{"truncated": true, "preview": "<1.5KB>"}`); after per-element truncate, if total array >32 KB, keep first N + sentinel `{"truncated_omitted_count": K}`
- [ ] T072 [US5] Modify `apps/api/prosauai/conversation/pipeline_executor.py` to emit `StepRecord` per sub-step (with `name="{step_type}"`, `status`, `duration_ms`, `model`, `tokens_in`, `tokens_out`, `cost_usd`, `input`, `output`, `tool_calls`, `condition_evaluated`, `error_type`, `error_message`, `terminating`) and pass list to top-level `generate_response` `StepRecord.sub_steps` (depends on T070)
- [ ] T073 [US5] Modify `apps/api/prosauai/conversation/pipeline.py` to write `messages.metadata` JSONB merge with `{"terminating_step": <str>, "pipeline_step_count": <int>, "pipeline_version": "unversioned-v1"}` for outbound messages produced by the pipeline executor; do NOT write these keys for single-call agents (FR-064, depends on T026)
- [ ] T074 [US5] [P] Add Prometheus metric `trace_steps_substeps_bytes_p95` (histogram) — observed at the truncation step in `trace_persist.py`. Metric description per `data-model.md` § Volume estimates
- [ ] T075 [US5] [P] Write integration test `apps/api/tests/integration/test_trace_persist_sub_steps_pg.py`: drive a 3-step pipeline through testcontainers, SELECT row from `trace_steps WHERE name='generate_response'`, assert `sub_steps` JSONB is a 3-element array with correct shape; force a sub-step >4 KB and assert `truncated: true` flag set; force total >32 KB and assert sentinel element appended

### Frontend — Trace Explorer rendering (PR-6, P2 cut-line sensitive)

- [ ] T076 [US5] Modify `apps/api/prosauai/admin/traces.py` admin endpoint (épico 008) — include `sub_steps` array in the trace detail payload when present on the `generate_response` row (no schema change to top-level response shape)
- [ ] T077 [US5] Modify `apps/admin/components/trace-detail.tsx` (épico 008) — when `step.sub_steps` is non-null on the `generate_response` row, render a nested accordion list using the same visual primitive as top-level steps (waterfall bar, status badge, expandable input/output/model/tokens/error). Skipped sub-steps render with muted styling and short reason text
- [ ] T078 [US5] [P] Add filters to `apps/api/prosauai/admin/traces.py` list endpoint: `?terminating_step=<str>` (queries `WHERE output_jsonb->>'terminating_step' = $1` against the `generate_response` row); `?pipeline_version=<uuid|str>` (queries `WHERE agent_version_id = $1` on the trace step). Document FR-062 mapping (zero new columns) in route docstring
- [ ] T079 [US5] [P] Update `apps/admin/app/admin/traces/page.tsx` UI — add filter inputs for `terminating_step` (dropdown of distinct values from response) and `pipeline_version` (text input) consistent with épico 008 filter pattern

**Checkpoint**: US5 backend (T070–T075) is hard-required for production debug. Frontend (T076–T079) is part of PR-6 cut-line — backend ships first.

---

## Phase 7: User Story 1 enrichment — Resolver + Summarizer (PR-4)

**Goal**: completar os 5 step types da v1. Resolver extrai entidades; summarizer reduz token count em conversas longas.

**Independent Test**: configure pipeline com summarizer + classifier + specialist; processar mensagem em conversa com >20 mensagens prévias; assert specialist recebe `summarized_context` (não histórico bruto) — verificável via mock LLM capturando `messages` arg.

### Tests for resolver/summarizer (write FIRST) ⚠️

- [ ] T080 [P] [US1] Write `apps/api/tests/conversation/test_steps_resolver.py` covering: pydantic-ai Agent with `output_type=ResolverOutput` (`entities: dict[str, Any]`); tools enabled flow through (mock tool registry, asserts tools were resolved per `tools_enabled` config); failure of any tool call → step error (no retry, FR-026)
- [ ] T081 [P] [US1] Write `apps/api/tests/conversation/test_steps_summarizer.py` covering: input truncated to last `max_input_messages` (default 20); output `{summary_text, message_count}`; **substitui** (não prepende) histórico — `state.summarized_context` populated, raw `messages` table untouched (FR-015); cheap model honored

### Implementation

- [ ] T082 [P] [US1] Implement `apps/api/prosauai/conversation/steps/resolver.py` — pydantic-ai Agent with `output_type=ResolverOutput`. Honors `config.tools_enabled` via existing `agent.py:get_enabled_tools` pattern. Registers in `STEP_TYPE_REGISTRY["resolver"]`
- [ ] T083 [P] [US1] Implement `apps/api/prosauai/conversation/steps/summarizer.py` — pydantic-ai Agent text output with structured output `{summary_text: str, message_count: int}`. After execute, sets `state.summarized_context = output.summary_text` (FR-015 substitution semantic). Registers in `STEP_TYPE_REGISTRY["summarizer"]`
- [ ] T084 [US1] Modify `pipeline_executor.py` to compute `effective_context = state.summarized_context or original_context_messages` and pass `effective_context` to subsequent steps (instead of the raw `context_messages`) when summarizer has executed. The raw `messages` table is never altered (FR-015, depends on T026, T083)
- [ ] T085 [US1] [P] Quickstart validation per `quickstart.md` § "Validar Resolver+Summarizer": insert 4-step pipeline (summarizer + classifier + resolver + specialist) for a tenant, send a long-history message, verify trace shows summarizer ran first and downstream steps received the compressed context

**Checkpoint**: All 5 step types implemented. PR-4 mergeable.

---

## Phase 8: User Story 3 — Configurar pipeline pelo admin sem SQL (Priority: P2) ✂️ Cut-line

**Goal**: engenheiro de prompt configura pipeline em <3 min via admin UI sem SQL (SC-005, SC-006).

**Independent Test**: operador (sem acesso ao banco) adiciona step `summarizer` ao final do pipeline do agente Ariel via UI, ativa, próxima mensagem dispara nova config (hot reload), `audit_log` registra a ação.

**⚠️ Cut-line**: se PR-1..PR-4 não estiverem em produção em pelo menos 1 tenant ao final da semana 3, abortar PR-5 e PR-6 (extrair para épico 015b). Phase 8 + Phase 9 são sacrificáveis.

### Backend — admin endpoints

- [ ] T090 [US3] Create Pydantic schemas in `apps/api/prosauai/admin/schemas/pipeline_steps.py` — `PipelineStepWrite` discriminated union per `contracts/openapi.yaml` (one variant per step_type with type-specific fields per `data-model.md` § Validation rules 5); `PipelineStepResponse`; `PipelineStepsListResponse`; `PipelineStepsReplaceRequest`
- [ ] T091 [US3] Create `apps/api/prosauai/admin/pipeline_steps.py` with `GET /admin/agents/{agent_id}/pipeline-steps` (uses `pool_admin` BYPASSRLS, ADR-027) → `PipelineStepsListResponse` ordered by `step_order` (depends on T013, T090)
- [ ] T092 [US3] Add `PUT /admin/agents/{agent_id}/pipeline-steps` (atomic replace via repository's `replace_steps`); 422 with `field_errors` from `validate_steps_payload` on validation failure; depends on T013 + T090. Register router in `apps/api/prosauai/main.py`
- [ ] T093 [US3] Emit `audit_log` entry on each successful PUT with operator email (from `get_current_admin`), agent_id, diff (added/removed/modified steps by `step_order`), timestamp (FR-045)
- [ ] T094 [P] [US3] Modify `apps/api/prosauai/admin/agents.py` (épico 008) — add `pipeline_steps_count` to agent listing and detail responses (single LEFT JOIN aggregate)
- [ ] T095 [P] [US3] Write integration test `apps/api/tests/integration/test_admin_pipeline_steps.py` covering: GET returns ordered list; PUT replaces atomically; PUT with 6 steps → 422; PUT with duplicate `step_order` → 422; PUT with unknown model in `routing_map` → 422; PUT with unknown `prompt_slug` → 422; audit_log row inserted with correct diff

### Frontend — admin UI (Next.js 15 + shadcn)

- [ ] T096 [US3] Create `apps/admin/lib/api/pipeline-steps.ts` — TanStack Query v5 hooks: `usePipelineSteps(agentId)`, `useReplacePipelineSteps()` mutation with optimistic update + rollback on error
- [ ] T097 [US3] Create `apps/admin/components/pipeline-step-form.tsx` — controlled form with discriminated rendering by `step_type`: classifier shows `model + intent_labels + prompt_slug + timeout_seconds`; clarifier shows `model + prompt_slug + max_question_length`; resolver shows `model + prompt_slug + tools_enabled`; specialist shows `default_model + routing_map (key/value pairs UI) + prompt_slug + tools_enabled`; summarizer shows `model + max_input_messages + prompt_slug` (FR-043). Optional `condition` text input with inline syntax help
- [ ] T098 [US3] Create `apps/admin/components/pipeline-step-list.tsx` — vertical card list ordered by step_order, each card with edit/up/down/remove buttons; "Add step" button opens dialog with step_type selector then `pipeline-step-form.tsx`
- [ ] T099 [US3] Create `apps/admin/app/admin/agents/[id]/pipeline-steps/page.tsx` — orchestrates list + add/edit dialog + save (calls `useReplacePipelineSteps` with full list per D-PLAN-10); shows server-side validation errors inline; success toast on save
- [ ] T100 [P] [US3] Add Playwright test `apps/admin/tests/pipeline-steps.spec.ts` exercising the SC-006 happy path: login as admin, navigate to agent detail, open pipeline steps tab, add classifier + specialist, save, refresh, verify steps persist; total elapsed time logged for SC-006 verification
- [ ] T101 [P] [US3] Add rollback button to agent detail UI — calls existing `agent_config_versions` rollback endpoint OR (per D-PLAN-02 fallback) calls a new `POST /admin/agents/{id}/pipeline-steps/rollback` that uses `audit_log` to reconstruct the previous state and PUTs it. Document approach in `decisions.md` based on T093 outcome

**Checkpoint**: US3 fully usable. Engineering team migrates from SQL workflow to UI workflow.

---

## Phase 9: User Story 4 — Comparar versões lado-a-lado (Priority: P2) ✂️ Cut-line

**Goal**: canary rollout per agent_version exibe métricas lado-a-lado (QS, custo, latência, fallback rate); operador decide promote/rollback baseado em números (SC-013).

**Independent Test**: agente em canary v4 (sem pipeline) 90% / v5 (com pipeline) 10% por 48 h; aba Performance AI mostra colunas separadas com KPIs e contagem de mensagens; insuficiência marcada quando N<50.

**⚠️ Cut-line**: Phase 9 depends on Phase 8 (P2 frontend infra) AND on `agent_config_versions` actually existing. Per D-PLAN-02 the table doesn't exist in production — Phase 9 is **fully optional in this epic**. If `agent_config_versions` is not shipped before week 3, Phase 9 is deferred to a future epic. Document the branching decision in `decisions.md`.

- [ ] T110 [US4] Confirm `agent_config_versions` table exists in production. If NOT, mark Phase 9 as DEFERRED in `decisions.md` and SKIP T111–T115
- [ ] T111 [US4] Modify `apps/api/prosauai/admin/performance.py` (épico 008) — accept `?group_by=agent_version` query param; when set, GROUP BY `agent_version_id` and return parallel KPI series (QS, latency_p95, cost_avg, fallback_rate, message_count) per version
- [ ] T112 [US4] Apply minimum-sample-size rule: any version with `message_count < 50` returns `kpis: null, sample_label: "amostra insuficiente — N=42"` instead of numbers (FR-052, ADR-019 item 16)
- [ ] T113 [US4] [P] Modify `apps/admin/components/perf-ai-card.tsx` (épico 008) — add toggle "Group by version" (visible only when ≥2 active versions detected); when toggled, render side-by-side columns with version label + KPIs (or insufficient-sample placeholder)
- [ ] T114 [US4] [P] Update trend charts (`apps/admin/components/perf-ai-charts.tsx` épico 008) — when `group_by=agent_version`, render distinct lines per version with legend
- [ ] T115 [US4] [P] Write Playwright test `apps/admin/tests/perf-ai-canary.spec.ts` exercising the SC-013 flow: seed 2 versions of fake data with different distributions, navigate to perf-ai page, toggle group-by, verify both columns render with correct labels and small-sample handling

**Checkpoint**: US4 enables data-driven canary promotion decisions.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: final cleanup, docs, observability hardening, decisions ledger update.

- [ ] T120 [P] Run `ruff check --fix apps/api/prosauai/conversation/` and `ruff format apps/api/prosauai/conversation/` — clean (Constitution Principle II)
- [ ] T121 [P] Run `make ruff` and `make test` from repo root (`paceautomations/prosauai`) — green
- [ ] T122 [P] Update `apps/api/README.md` with a "Pipeline Steps (epic 015)" section referencing `docs/pipeline-steps-runbook.md`
- [ ] T123 [P] Create `apps/api/docs/pipeline-steps-runbook.md` runbook for ops/eng covering: how to insert steps via SQL during phase 1; how to read sub_steps in Trace Explorer; how to roll back via `UPDATE agent_pipeline_steps SET is_active=FALSE` (per `data-model.md` § Rollback path); diagnostic queries for `messages.metadata.terminating_step`
- [ ] T124 Append accumulated `D-PLAN-XX` decisions to `platforms/prosauai/epics/015-agent-pipeline-steps/decisions.md` under `## Implementation Decisions` — full audit trail for ADR-019 follow-up scoping
- [ ] T125 [P] Validate Prometheus metrics scraping: `agent_pipeline_steps_count`, `trace_steps_substeps_count`, `trace_steps_substeps_bytes_p95` are exposed at `/metrics` and scrape successfully (depends on T074)
- [ ] T126 Re-run benchmark T051 against the merged code in staging — confirm SC-010 (≤5 ms p95 overhead) holds end-to-end with realistic load (10 agents × 100k requests). Document staging numbers in `decisions.md`
- [ ] T127 Update `platforms/prosauai/engineering/domain-model.md` line 244 cross-reference — replace "schema-draft" with "implemented in epic 015 — see migration 20260601000010"
- [ ] T128 [P] Run final regression sweep: `pytest apps/api/tests/ -x` zero failures; manual smoke of 3 baseline tenants (no pipeline configured) confirming zero behavior change

---

## Phase 11: Deployment Smoke

**Purpose**: validate the full epic against staging environment per `platforms/prosauai/platform.yaml:testing` block (docker startup type detected).

- [ ] T130 Execute `docker compose build` no diretório da plataforma — build sem erros
- [ ] T131 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --start --platform prosauai` — todos os health_checks respondem dentro do ready_timeout (120s)
- [ ] T132 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-env --platform prosauai` — zero required_env vars ausentes no .env (JWT_SECRET, ADMIN_BOOTSTRAP_EMAIL, ADMIN_BOOTSTRAP_PASSWORD, DATABASE_URL)
- [ ] T133 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-urls --platform prosauai` — todas as URLs acessíveis com status esperado
- [ ] T134 Capturar screenshot de cada URL `type: frontend` declarada em `testing.urls` (http://localhost:3000 e http://localhost:3000/admin/login) — conteúdo não é placeholder
- [ ] T135 Executar Journey J-001 (happy path) declarado em `platforms/prosauai/testing/journeys.md` — todos os steps com assertions OK; adicionalmente validar que mensagens processadas via pipeline (com tenant em adoção) populam `trace_steps.sub_steps` corretamente

---

## Dependencies & Execution Order

```text
Phase 1 (Setup)
   └─→ Phase 2 (Foundational, schema + protocol) ⚠️ BLOCKING
        ├─→ Phase 3 (US1 — classifier+specialist) ─┐
        ├─→ Phase 4 (US2 — clarifier + condition) ─┤
        └─→ Phase 5 (US6 — backwards compat) ──────┴─→ 🛡️ HARD GATE (SC-008, SC-010)
                                                         │
                                                         ├─→ Phase 6 (US5 — sub_steps tracing) ─┐
                                                         ├─→ Phase 7 (resolver + summarizer) ───┤
                                                         │                                       │
                                                         │       ✂️ Cut-line decision @ week 3 ──┤
                                                         │                                       │
                                                         ├─→ Phase 8 (US3 — admin UI) ──────────┤
                                                         └─→ Phase 9 (US4 — group-by-version) ──┤
                                                                                                 │
                                                                                  Phase 10 (Polish) ◀┘
                                                                                                 │
                                                                                  Phase 11 (Smoke) ◀┘
```

**Within each phase**:
- Tests marked `[P]` can run in parallel (different files, no inter-dependencies)
- Implementation tasks within a story may serialize on shared files (e.g., `pipeline_executor.py` is touched by T026, T044, T045, T072, T084 — these MUST serialize in that order)

**MVP scope (PRs 1–4)**: Phase 1 + Phase 2 + Phase 3 + Phase 4 + Phase 5 + Phase 7 + Phase 6 backend (T070–T075). Operators configure pipelines via SQL during phase 1 of adoption. Estimated 3 weeks (per appetite).

**Cut-line scope (drops PRs 5–6)**: skip Phase 8 + Phase 9 + Phase 6 frontend (T076–T079). Decide by end of week 3 — see plan.md § "Cut-line decision".

---

## Parallel Execution Opportunities

### Phase 2 — after T010+T011+T013 are sequential, the rest are [P]

```text
T012 (constants) ║ T014 (repo tests) ║ T015 (pipeline_state) ║ T016 (condition) ║ T017 (condition tests) ║ T018 (registry) ║ T019 (Protocol)
```

### Phase 3 — Tests parallel, then implementation parallel where files differ

```text
Tests:           T020 ║ T021 ║ T022 ║ T023
Implementation:  T024 ║ T025  →  T026 (executor)  →  T027 (pipeline.py branch)  →  T028 (logs) + T029 (otel) [P]
```

### Phase 5 — All tests are independent

```text
T050 ║ T051 ║ T052
```

### Phase 8 — Backend serializes; frontend parallelizes

```text
Backend:  T090  →  T091 ║ T092  →  T093  →  T094 ║ T095
Frontend: T096  →  (T097 ║ T098)  →  T099  →  (T100 ║ T101)
```

---

## Implementation Strategy

### MVP first

1. **Phase 1 + Phase 2** (~1.5 days): foundations.
2. **Phase 3 (US1) + Phase 4 (US2)** (~7 days): the executor + 3 step types + condition. This is the *coração*. Demonstrate value via SQL-only configuration in staging by end of week 2.
3. **Phase 5 (US6)** (~1 day): hard gate before merge.
4. **Phase 6 backend (T070–T075)** (~2 days): persistence of sub_steps + metadata.
5. **Phase 7** (~2 days): resolver + summarizer.

End of week 3: PR-1..PR-4 merged, US1+US2+US5(backend)+US6 in production. Operators configure via SQL.

### Cut-line evaluation @ end of week 3

If PR-1..PR-4 are merged AND at least 1 tenant is running with pipeline configured:
→ proceed to Phase 8 (US3) + Phase 6 frontend (T076–T079) + Phase 9 (US4) (~5 days for PR-5+PR-6).

If NOT (delay, regression, etc.):
→ defer Phase 8 + Phase 9 + frontend tasks to a follow-up epic 015b. Document decision in `decisions.md`. The MVP is shippable as-is.

### Risk-based ordering within each story

- US1: tests for classifier and specialist FIRST (T020–T023), then the executor (T026) where most of the architectural risk lives.
- US6: write `test_pipeline_backwards_compat.py` (T050) BEFORE the executor branch (T027) — once T027 is touched, T050 must be green continuously.

---

## Format Validation

Sample task line conforms to `- [ ] [TaskID] [P?] [Story?] Description with file path`:

- ✅ `- [X] T020 [P] [US1] Write unit test apps/api/tests/conversation/test_steps_classifier.py covering...`
- ✅ `- [x] T010 Create migration apps/api/db/migrations/20260601000010_create_agent_pipeline_steps.sql ...`
- ✅ `- [X] T044 [US2] Wire condition evaluation in pipeline_executor.py ...`

All tasks include: checkbox, sequential ID, optional [P], optional [Story] (for Phase 3+ except Polish/Smoke), and a concrete file path or runnable command.

---

handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "Tasks for epic 015 organized by user story across 11 phases — PR-1 (Foundational, T010-T019), PR-2 + PR-4 spread across US1 (T020-T030, T080-T085) and US2 (T040-T046), PR-3/PR-6 backend in US5 (T070-T079), PR-5 in US3 (T090-T101), PR-6 perf-ai in US4 (T110-T115). Hard regression gate is US6 (T050-T055) — SC-008 (existing suite passes) + SC-010 (≤5 ms p95 overhead). Cut-line at end of week 3: if PR-1..PR-4 not in production with at least 1 tenant configured, drop Phase 8 + Phase 9 + frontend tasks (T076-T079) into epic 015b. Deployment smoke (T130-T135) follows platform.yaml:testing block (docker startup type, build → start → validate envs/URLs → screenshots → journey J-001). 7 unique stories tagged: US1 (P1), US2 (P1), US6 (P1), US3 (P2), US4 (P2), US5 (P2). 5 step types implemented (classifier, clarifier, resolver, specialist, summarizer). Total ~85 tasks."
  blockers: []
  confidence: Alta
  kill_criteria: "Tasks invalidated if: (a) PR-1 schema migration fails apply on staging — surface earlier mismatch with `domain-model.md` line 244; (b) Phase 5 regression gate (T050/T051/T052) cannot be made green within 2 days of work — escalates need for refactor of `pipeline.py` injection point identified in T004; (c) `agent_config_versions` (ADR-019) ships before this epic merges, invalidating D-PLAN-02 — Phase 9 becomes mandatory and Phase 8 may need pipeline_version-aware UI; (d) testing block in platform.yaml changes (e.g., switch from docker to npm or removal of testing block) — Phase 11 must be regenerated; (e) discovery during T026/T027 that the executor cannot be inserted as a 5-line branch due to coupling in `_generate_with_retry` — invalidates D-PLAN-03 and forces refactor PR ahead of PR-2."
