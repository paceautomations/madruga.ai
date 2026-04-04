# Tasks: Observability, Tracing & Evals

**Input**: Design documents from `platforms/madruga-ai/epics/017-observability-tracing-evals/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/daemon-api.md, research.md, quickstart.md
**Branch**: `epic/madruga-ai/017-observability-tracing-evals`

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Migration SQL e shell do portal para a pagina de observabilidade.

- [X] T001 Create migration file `.pipeline/migrations/010_observability.sql` with CREATE TABLE traces, ALTER TABLE pipeline_runs ADD COLUMN trace_id, CREATE TABLE eval_scores, and 7 indices per data-model.md
- [X] T002 [P] Create observability page shell `portal/src/pages/[platform]/observability.astro` importing ObservabilityDashboard as React island with `client:load`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend core — db.py trace/span CRUD, dag_executor tracing integration, CORS middleware. MUST complete before any user story.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add trace/span CRUD functions to `.specify/scripts/db.py`: `create_trace(conn, platform_id, epic_id, mode, total_nodes) -> trace_id`, `complete_trace(conn, trace_id, status)` (calcula agregados dos spans), `get_traces(conn, platform_id, limit, offset, status_filter) -> list[dict]`, `get_trace_detail(conn, trace_id) -> dict` (trace + spans). Use uuid4().hex for trace_id. Aggregate total_tokens_in/out/cost_usd/duration_ms from pipeline_runs in complete_trace.
- [X] T004 Add `parse_claude_output(stdout: str) -> dict` to `.specify/scripts/dag_executor.py` — extract `usage.input_tokens`, `usage.output_tokens`, `cost_usd`, `duration_ms` from JSON with defensive `.get()` and try/except (R1). Integrate trace lifecycle: create trace at pipeline run start, pass trace_id to each insert_run call, call parse_claude_output in dispatch_node_async to populate tokens_in/out/cost_usd/duration_ms in complete_run, call complete_trace at pipeline end. All parsing best-effort with silent failure (FR-011).
- [X] T005 [P] Add CORSMiddleware to `.specify/scripts/daemon.py` with `allow_origins=["http://localhost:4321", "http://localhost:3000"]`, `allow_methods=["GET"]`, `allow_headers=["*"]` per R8.
- [X] T006 Write trace/span DB function tests in `.specify/scripts/tests/test_db_observability.py`: test create_trace returns valid trace_id, test complete_trace aggregates span metrics, test get_traces with pagination and status filter, test get_trace_detail returns trace + ordered spans, test trace_id FK on pipeline_runs. Use in-memory SQLite with migrate().

**Checkpoint**: Foundation ready — trace lifecycle integrated in executor, CORS configured, DB functions tested.

---

## Phase 3: User Story 1 — Monitorar execucao de pipeline em tempo real (Priority: P1) MVP

**Goal**: O operador visualiza o progresso de um pipeline run com status de cada node atualizado automaticamente a cada 10s.

**Independent Test**: Iniciar um pipeline run e verificar no portal que cada node aparece com status atualizado. Um node em execucao aparece como "executando" em ate 10s.

### Implementation for User Story 1

- [X] T007 [US1] Add GET `/api/traces` and GET `/api/traces/{trace_id}` endpoints to `.specify/scripts/daemon.py` per contracts/daemon-api.md. `/api/traces` requires `platform_id`, supports `limit`, `offset`, `status` query params, returns `{traces, total, limit, offset}`. `/api/traces/{trace_id}` returns `{trace, spans, eval_scores}` or 404. Call db.get_traces and db.get_trace_detail respectively.
- [X] T008 [P] [US1] Create `portal/src/components/observability/ObservabilityDashboard.tsx` — main React component with 4 tab buttons (Runs, Traces, Evals, Cost). State: activeTab, data per tab. Polling via useEffect + setInterval(10000) + fetch() against daemon `localhost:8040`. Accepts `platform` prop from Astro page. Renders the active tab's child component.
- [X] T009 [US1] Create `portal/src/components/observability/RunsTab.tsx` — table of recent traces showing status, duration, total cost, nodes completed/total. Status badges: running=blue, completed=green, failed=red, cancelled=gray. Click row to expand inline showing span details (node_id, status, duration, cost). Receives traces data as prop from ObservabilityDashboard.
- [X] T010 [US1] Add endpoint tests for `/api/traces` and `/api/traces/{trace_id}` in `.specify/scripts/tests/test_daemon_observability.py` using httpx AsyncClient + TestClient. Test: list traces with platform_id filter, pagination, status filter, 400 on missing platform_id, trace detail with spans, 404 on unknown trace_id. Seed test DB with sample traces and pipeline_runs.

**Checkpoint**: Operador ve lista de pipeline runs com status e detalhes de cada node no portal. Polling 10s ativo.

---

## Phase 4: User Story 2 — Rastrear consumo de tokens e custo por run (Priority: P1)

**Goal**: O operador ve tokens consumidos e custo estimado por node e por run, com tendencia de custo acumulado por periodo.

**Independent Test**: Executar pipeline run completo, verificar que cada node exibe tokens/custo. Tab Cost mostra custo acumulado por dia.

### Implementation for User Story 2

- [X] T011 [US2] Add `get_stats(conn, platform_id, days) -> dict` to `.specify/scripts/db.py` — query agregado por dia (COUNT runs, SUM cost, SUM tokens_in/out, AVG duration) from traces table per data-model.md queries. Return `{stats: list[dict], summary: dict}` with period totals.
- [X] T012 [US2] Add GET `/api/stats` endpoint to `.specify/scripts/daemon.py` per contracts/daemon-api.md. Requires `platform_id`, optional `days` (default 30, max 90). Returns `{stats, period_days, summary}`. Call db.get_stats.
- [X] T013 [P] [US2] Create `portal/src/components/observability/CostTab.tsx` — SVG bar chart showing cost per day/week. Display total tokens (in/out) as summary cards. Show top 5 nodes by cost. Receives stats data as prop. Use SVG `<rect>` for bars, proportional heights.
- [X] T014 [US2] Add endpoint tests for `/api/stats` in `.specify/scripts/tests/test_daemon_observability.py` — test stats aggregation by day, summary totals, days parameter clamped to 90, 400 on missing platform_id. Add test for get_stats db function in `test_db_observability.py`.

**Checkpoint**: Operador ve custo por node em cada run (via RunsTab detail) e custo acumulado por periodo na tab Cost.

---

## Phase 5: User Story 3 — Avaliar qualidade dos artefatos gerados (Priority: P2)

**Goal**: Cada node completado recebe scores 0-10 em 4 dimensoes heuristicas, visiveis no portal com tendencias.

**Independent Test**: Executar pipeline run, verificar que cada node recebe 4 eval scores persistidos e visiveis na tab Evals.

### Implementation for User Story 3

- [X] T015 [US3] Add eval score CRUD functions to `.specify/scripts/db.py`: `insert_eval_score(conn, trace_id, platform_id, epic_id, node_id, run_id, dimension, score, metadata)` with duplicate check on (run_id, dimension), `get_eval_scores(conn, platform_id, node_id, dimension, limit) -> list[dict]` with optional filters. Use uuid4().hex for score_id.
- [X] T016 [P] [US3] Create `.specify/scripts/eval_scorer.py` (~150 LOC) — `score_node(conn, platform_id, node_id, run_id, output_path, metrics) -> list[dict]`. 4 heuristic dimensions per R4: `quality` (output non-empty + no error markers -> 7.0 default, normalize Judge score if exists), `adherence_to_spec` (regex match expected sections vs output), `completeness` (min(10, actual_lines / expected_lines * 10)), `cost_efficiency` (10 - min(10, cost / avg_budget * 10), neutral 5.0 if no history). Return list of score dicts ready for insert_eval_score.
- [X] T017 [US3] Integrate eval scoring in `.specify/scripts/dag_executor.py` — after each node completes successfully, call `eval_scorer.score_node()` and persist via `db.insert_eval_score()`. Wrap in try/except for best-effort (FR-011). Pass output_path and metrics dict (tokens, cost, duration, output_size).
- [X] T018 [US3] Add GET `/api/evals` endpoint to `.specify/scripts/daemon.py` per contracts/daemon-api.md. Requires `platform_id`, optional `node_id`, `dimension`, `limit` (default 100). Returns `{scores, total}`. Call db.get_eval_scores.
- [X] T019 [P] [US3] Create `portal/src/components/observability/EvalsTab.tsx` — scoreboard table (node x dimension) with color-coded scores (green >= 7, yellow >= 5, red < 5). Sparkline trends (last 5-10 runs) as SVG `<path>`. Visual highlight for scores < 5 ("atencao necessaria"). Receives eval scores data as prop.
- [X] T020 [P] [US3] Write tests for eval scorer in `.specify/scripts/tests/test_eval_scorer.py` — test each dimension scoring: quality with/without Judge score, adherence with matching/missing sections, completeness proportional to line count, cost_efficiency with/without history. Test edge cases: empty output (low completeness), zero cost (max efficiency), missing metrics (neutral defaults).
- [X] T021 [US3] Add eval score DB tests to `.specify/scripts/tests/test_db_observability.py` — test insert_eval_score, duplicate check (run_id + dimension), get_eval_scores with filters (platform, node, dimension), ordering by evaluated_at DESC.

**Checkpoint**: Nodes completados recebem 4 eval scores automaticos. Portal exibe scoreboard com tendencias e destaques visuais.

---

## Phase 6: User Story 4 — Visualizar trace hierarquico de um run (Priority: P2)

**Goal**: Diagrama waterfall SVG mostrando sequencia de nodes com duracao proporcional, permitindo identificar gargalos.

**Independent Test**: Executar pipeline run, abrir tab Traces, verificar waterfall com barras proporcionais a duracao de cada node.

### Implementation for User Story 4

- [X] T022 [US4] Create `portal/src/components/observability/TracesTab.tsx` — dropdown to select trace from recentes. SVG waterfall: each span as `<rect>` with width proportional to duration_ms, positioned by started_at relative to trace start. Color-coded by status (completed=green, failed=red, running=blue, cancelled=gray). Native `<title>` tooltip showing node_id, duration, tokens, cost. Vertical stacking in execution order. Receives traces list + selected trace detail as props.

**Checkpoint**: Operador identifica visualmente o node mais lento de cada run via waterfall.

---

## Phase 7: User Story 5 — Limpeza automatica de dados antigos (Priority: P3)

**Goal**: Registros > 90 dias removidos automaticamente. Export CSV sob demanda antes da remocao.

**Independent Test**: Inserir registros com timestamps > 90 dias, executar cleanup, verificar remocao. Exportar CSV e validar conteudo.

### Implementation for User Story 5

- [X] T023 [US5] Add `cleanup_old_data(conn, days=90) -> dict` to `.specify/scripts/db.py` — 3 sequential DELETEs in single transaction per R6: eval_scores, pipeline_runs (WHERE trace_id IN stale traces), traces. Return `{eval_scores: N, pipeline_runs: N, traces: N}` deleted counts. Log with structlog.
- [X] T024 [P] [US5] Create `.specify/scripts/observability_export.py` (~80 LOC) — `export_csv(conn, platform_id, entity, days) -> str` where entity is 'traces', 'spans', or 'evals'. Query appropriate table, write CSV string with headers via csv.writer + io.StringIO. Include all columns per contracts/daemon-api.md example.
- [X] T025 [US5] Add GET `/api/export/csv` endpoint to `.specify/scripts/daemon.py` per contracts/daemon-api.md. Requires `platform_id` and `entity` (traces|spans|evals), optional `days` (default 90). Returns text/csv with Content-Disposition header. Call observability_export.export_csv. Return 400 on invalid entity.
- [X] T026 [US5] Add retention cleanup periodic task to `.specify/scripts/daemon.py` — `retention_cleanup(conn, shutdown_event, interval=86400)` in daemon TaskGroup. Calls db.cleanup_old_data(conn, days=90). Log deleted counts with structlog. Run once daily.
- [X] T027 [P] [US5] Write tests for CSV export in `.specify/scripts/tests/test_observability_export.py` — test export_csv for each entity type (traces, spans, evals): verify CSV headers match schema, rows match inserted data, UTF-8 encoding, empty result returns headers only. Test days parameter filtering.
- [X] T028 [US5] Add cleanup DB tests to `.specify/scripts/tests/test_db_observability.py` — test cleanup_old_data removes records older than 90 days, preserves recent records, returns correct deleted counts per table, handles empty tables gracefully.

**Checkpoint**: Retention automatica ativa no daemon. Export CSV funcional via endpoint.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validacao end-to-end e edge cases.

- [X] T029 Verify all edge cases from spec in relevant test files: interrupted pipeline run registers partial trace with status "cancelled", node without JSON output registers tokens/cost as NULL without impacting others, concurrent pipeline runs have isolated traces, DB write failure does not block pipeline execution, eval on empty/minimal artifacts scores low on completeness
- [X] T030 Run quickstart.md end-to-end validation: apply migration, start daemon, start portal, execute pipeline run, verify trace/spans/evals in DB and portal, export CSV, verify CORS

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on T001 (migration) — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational completion
- **US2 (Phase 4)**: Depends on Foundational completion — can run in parallel with US1
- **US3 (Phase 5)**: Depends on Foundational completion — can run in parallel with US1/US2
- **US4 (Phase 6)**: Depends on US1 (needs ObservabilityDashboard.tsx and /api/traces/{id})
- **US5 (Phase 7)**: Depends on Foundational completion — can run in parallel with US1-US4
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: After Foundational — no dependencies on other stories. Creates ObservabilityDashboard.tsx (shared shell).
- **US2 (P1)**: After Foundational — independent of US1. CostTab is standalone component.
- **US3 (P2)**: After Foundational — independent. Adds eval_scorer.py + EvalsTab.
- **US4 (P2)**: After US1 — needs ObservabilityDashboard tabs + trace detail endpoint from US1.
- **US5 (P3)**: After Foundational — independent. Adds cleanup + export.

### Within Each User Story

- DB functions before daemon endpoints
- Daemon endpoints before portal components
- Tests can be written in parallel with implementation (same story, different files)

### File Modification Map

Files modified by multiple tasks (execute these tasks sequentially):

| File | Tasks |
|------|-------|
| `.specify/scripts/db.py` | T003, T011, T015, T023 |
| `.specify/scripts/dag_executor.py` | T004, T017 |
| `.specify/scripts/daemon.py` | T005, T007, T012, T018, T025, T026 |
| `.specify/scripts/tests/test_db_observability.py` | T006, T014, T021, T028 |
| `.specify/scripts/tests/test_daemon_observability.py` | T010, T014 |

### Parallel Opportunities

```text
# Phase 1: Setup (parallel)
T001 (migration) || T002 (astro page)

# Phase 2: Foundational
T003 (db.py) → T004 (dag_executor) → T006 (db tests)
T005 (CORS) can run in parallel with T003/T004

# Phase 3-7: User Stories (after Foundational)
US1, US2, US3, US5 can start in parallel (different primary files)
US4 waits for US1 (depends on ObservabilityDashboard + trace detail)

# Within US3 (example):
T015 (db) → T016 (scorer, parallel) + T018 (daemon endpoint)
T019 (EvalsTab, parallel with backend) || T020 (scorer tests, parallel)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T006)
3. Complete Phase 3: User Story 1 (T007-T010)
4. **STOP and VALIDATE**: Pipeline runs visibles no portal com status real-time
5. Deploy/demo if ready — operador ja consegue monitorar execucao

### Incremental Delivery

1. Setup + Foundational -> Trace lifecycle integrado no executor
2. Add US1 -> Portal exibe runs com status real-time (MVP!)
3. Add US2 -> Custo e tokens vissiveis por run e por periodo
4. Add US3 -> Evals automaticos com scoreboard
5. Add US4 -> Waterfall visual para identificar gargalos
6. Add US5 -> Retention + export CSV
7. Each story adds value without breaking previous stories

### Single Developer Strategy (Recommended)

Sequencia otima para um desenvolvedor:

1. T001 + T002 (Setup, parallelizable)
2. T003 → T004 → T005 + T006 (Foundational)
3. T007 → T008 → T009 → T010 (US1 — MVP)
4. T011 → T012 → T013 → T014 (US2)
5. T015 → T016 + T017 → T018 → T019 + T020 → T021 (US3)
6. T022 (US4 — depends on US1)
7. T023 → T024 + T025 → T026 → T027 + T028 (US5)
8. T029 → T030 (Polish)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in same phase
- [Story] label maps task to specific user story for traceability
- All backend parsing is best-effort with try/except — observability never blocks pipeline (FR-011)
- Scripts must stay < 300 LOC each (CLAUDE.md constraint) — eval_scorer.py and observability_export.py are standalone
- db.py already exceeds 300 LOC (core module); additions are simple CRUD
- Portal components use SVG puro (zero deps) per R7 decision
- Daemon URL: localhost:8040 | Portal URL: localhost:4321
