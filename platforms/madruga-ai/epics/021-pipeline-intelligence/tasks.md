# Tasks: Pipeline Intelligence (Epic 021)

**Input**: `platforms/madruga-ai/epics/021-pipeline-intelligence/pitch.md`
**Prerequisites**: pitch.md (primary design doc — spec.md and plan.md are stubs from Q&A sessions)

**Tests**: Included — constitution mandates TDD for all code.

**Organization**: Tasks grouped by feature (T1–T4 from pitch) since each is independent.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which feature this task belongs to (US1=Cost Tracking, US2=Hallucination Guard, US3=Quick-Fix, US4=Roadmap-Reassess)

---

## Phase 1: Setup

**Purpose**: Understand current state and prepare shared infrastructure

- [X] T001 Verify `claude -p --output-format json` actual output fields by running a test dispatch and inspecting stdout JSON structure (document in `platforms/madruga-ai/epics/021-pipeline-intelligence/research.md`)
- [X] T002 Review existing test coverage in `.specify/scripts/tests/test_dag_executor.py` to understand test patterns and fixtures already available

**Checkpoint**: Output JSON field names confirmed, test patterns understood

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational tasks needed — each feature modifies independent files/functions. All user stories can start after Phase 1.

**Checkpoint**: Proceed directly to user stories.

---

## Phase 3: User Story 1 — Cost Tracking (Priority: P1) 🎯 MVP

**Goal**: Ensure `pipeline_runs` rows have `tokens_in`, `tokens_out`, `cost_usd`, `duration_ms` populated after every dispatch — both normal L1/L2 nodes and implement tasks.

**Independent Test**: Query `SELECT tokens_in, tokens_out, cost_usd FROM pipeline_runs WHERE tokens_in IS NOT NULL` returns rows after a dispatch. Portal "Cost" tab shows real data.

**Context from code analysis**:
- `parse_claude_output()` exists at `dag_executor.py:183` and parses `usage.input_tokens`, `usage.output_tokens`, `cost_usd`, `duration_ms`
- Both sync loop (line 1302–1326) and async loop (line 1812–1837) already call `parse_claude_output()` and pass metrics to `complete_run()`
- `_run_implement_tasks()` (line 524–536) also passes metrics to `insert_run()` directly
- `complete_run()` in `db_pipeline.py:373` uses `_COMPLETE_RUN_FIELDS` which includes all metric fields
- **Gap**: The field names in `parse_claude_output()` may not match actual `claude -p` JSON output. Need T001 to verify.

### Tests for User Story 1

- [X] T003 [P] [US1] Write test for `parse_claude_output()` with real claude JSON output in `.specify/scripts/tests/test_cost_tracking.py` — test correct field extraction, missing fields, malformed JSON, empty string
- [X] T004 [P] [US1] Write test verifying `complete_run()` updates metric columns in `.specify/scripts/tests/test_cost_tracking.py` — mock DB, assert UPDATE includes tokens_in/out/cost_usd/duration_ms

### Implementation for User Story 1

- [X] T005 [US1] Update `parse_claude_output()` in `.specify/scripts/dag_executor.py` to match actual `claude -p --output-format json` field names (based on T001 findings) — adjust `usage.input_tokens` → correct path if different
- [X] T006 [US1] Add `cost_usd` calculation if not provided by claude output — compute from token counts using model pricing in `.specify/scripts/dag_executor.py` (fallback: `tokens_in * 0.003/1000 + tokens_out * 0.015/1000` for Sonnet)
- [X] T007 [US1] Verify portal "Cost" tab in `portal/` renders data from populated `pipeline_runs` rows — confirm React components from epic 017 read `cost_usd` column correctly (read-only check, no code change expected)

**Checkpoint**: After a dispatch, `pipeline_runs` has non-null metric values. `make test` passes.

---

## Phase 4: User Story 2 — Hallucination Guard (Priority: P1) 🎯 MVP

**Goal**: Detect and warn when a skill dispatch completes with zero tool calls — likely fabricated output.

**Independent Test**: A mock dispatch with zero tool calls in output JSON triggers a WARNING log.

### Tests for User Story 2

- [X] T008 [P] [US2] Write test for `_check_hallucination()` function in `.specify/scripts/tests/test_hallucination_guard.py` — test zero tool calls → True, nonzero → False, malformed JSON → False, missing field → False
- [X] T009 [P] [US2] Write test verifying hallucination check is called after dispatch in `.specify/scripts/tests/test_hallucination_guard.py` — mock dispatch returning zero-tool-call JSON, assert warning logged

### Implementation for User Story 2

- [X] T010 [US2] Add `_check_hallucination(stdout: str) -> bool` function to `.specify/scripts/dag_executor.py` — parse JSON, check `tool_use_count` or equivalent field from claude output, return True if zero tool calls
- [X] T011 [US2] Integrate hallucination check in sync execution loop at `.specify/scripts/dag_executor.py` (after line ~1302 where `metrics = parse_claude_output(stdout)`) — call `_check_hallucination(stdout)`, log WARNING if True, still accept output (warning-only mode per pitch decision)
- [X] T012 [US2] Integrate hallucination check in async execution loop at `.specify/scripts/dag_executor.py` (after line ~1812) — same pattern as T011
- [X] T013 [US2] Add hallucination guard to Tier 1 auto-review table in `.claude/knowledge/pipeline-contract-base.md` — add row 0: "Agent made at least 1 tool call during generation?" with action "WARNING — output may be fabricated"

**Checkpoint**: Zero-tool-call output triggers WARNING in logs. `make test` passes. Contract doc updated.

---

## Phase 5: User Story 3 — Fast Lane `/quick-fix` (Priority: P2)

**Goal**: New skill + DAG mode for compressed L2 cycle: specify → implement → judge (skipping plan, tasks, analyze, qa, reconcile).

**Independent Test**: `python3 .specify/scripts/dag_executor.py --platform madruga-ai --epic test --quick --dry-run` prints the 3-node fast lane DAG.

### Tests for User Story 3

- [X] T014 [P] [US3] Write test for `--quick` DAG parsing in `.specify/scripts/tests/test_dag_executor.py` — verify `parse_dag()` or equivalent returns only 3 nodes (specify, implement, judge) when `mode="quick"`
- [X] T015 [P] [US3] Write test for quick-fix node dependencies in `.specify/scripts/tests/test_dag_executor.py` — verify implement depends on specify, judge depends on implement

### Implementation for User Story 3

- [X] T016 [US3] Create `/quick-fix` skill markdown at `.claude/commands/madruga/quick-fix.md` (~80–120 LOC) — frontmatter with `gate: human`, persona as pragmatic engineer, instructions to collect bug description + affected files + generate minimal spec.md + delegate to implement + run judge
- [X] T017 [US3] Add `quick_cycle` node list to `platforms/madruga-ai/platform.yaml` under `pipeline.epic_cycle` — 3 nodes: specify (gate: human), implement (gate: auto), judge (gate: auto-escalate) with correct depends chains
- [X] T018 [US3] Add `--quick` CLI flag to argparse in `.specify/scripts/dag_executor.py` — new argument `--quick` (boolean flag), passed through to DAG loading
- [X] T019 [US3] Implement quick mode DAG loading in `.specify/scripts/dag_executor.py` — when `--quick` is set, read `quick_cycle` nodes from platform.yaml instead of `epic_cycle`, build reduced DAG with only specify → implement → judge
- [X] T020 [US3] Update `build_dispatch_cmd()` in `.specify/scripts/dag_executor.py` to pass quick-fix context in system prompt when `--quick` mode is active — inform the skill it's in fast-lane mode, scope restricted

**Checkpoint**: `--quick --dry-run` shows 3-node DAG. Skill markdown passes lint. `make test` passes.

---

## Phase 6: User Story 4 — Adaptive Replanning Hint (Priority: P3)

**Goal**: After `reconcile` completes an epic, optionally trigger roadmap reassessment for large epics (appetite > 2w).

**Independent Test**: `platform.yaml` has `roadmap-reassess` node. Dry-run with a >2w epic shows the node; dry-run with ≤2w epic skips it.

### Implementation for User Story 4

- [X] T021 [US4] Add `roadmap-reassess` optional node to `platforms/madruga-ai/platform.yaml` under `pipeline.epic_cycle.nodes` — id: roadmap-reassess, skill: madruga:roadmap, depends: [reconcile], gate: auto, optional: true, skip_condition: "epic.appetite <= '2w'"
- [X] T022 [US4] Document `roadmap-reassess` node in `.claude/knowledge/pipeline-dag-knowledge.md` — add row to L2 table (step 12), explain optional behavior and skip condition
- [X] T023 [US4] Verify `dag_executor.py` handles `skip_condition` and `optional: true` correctly for the new node — trace existing skip_condition logic to confirm "epic.appetite <= '2w'" pattern is supported (may need to add appetite-based skip evaluation)

**Checkpoint**: Node exists in YAML. Knowledge doc updated. `make lint` passes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation, integration, and documentation

- [X] T024 [P] Run `make test` — all existing + new tests pass
- [X] T025 [P] Run `make ruff` — no lint errors in modified files
- [X] T026 [P] Run `python3 .specify/scripts/skill-lint.py --skill madruga:quick-fix` — validate new skill frontmatter and structure
- [X] T027 Verify `python3 .specify/scripts/platform_cli.py lint madruga-ai` passes — platform YAML valid with new nodes
- [X] T028 Update `platforms/madruga-ai/epics/021-pipeline-intelligence/pitch.md` acceptance criteria checkboxes based on implementation status

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **US1 Cost Tracking (Phase 3)**: Depends on T001 (JSON field verification)
- **US2 Hallucination Guard (Phase 4)**: No dependencies on other stories — can start after Setup
- **US3 Quick-Fix (Phase 5)**: No dependencies on other stories — can start after Setup
- **US4 Roadmap-Reassess (Phase 6)**: No dependencies on other stories — can start after Setup
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (Cost Tracking)**: Independent. T001 → T003/T004 → T005 → T006 → T007
- **US2 (Hallucination Guard)**: Independent. T008/T009 → T010 → T011/T012 → T013
- **US3 (Quick-Fix)**: Independent. T014/T015 → T016 → T017 → T018 → T019 → T020
- **US4 (Roadmap-Reassess)**: Independent. T021 → T022 → T023

### Within Each User Story

- Tests written FIRST (Red phase of TDD)
- Implementation to make tests pass (Green phase)
- Documentation/integration last

### Parallel Opportunities

- **All 4 user stories can run in parallel** (different files, no shared dependencies)
- Within US1: T003 ∥ T004
- Within US2: T008 ∥ T009; T011 ∥ T012
- Within US3: T014 ∥ T015
- Polish tasks T024 ∥ T025 ∥ T026

---

## Parallel Example: User Story 2 (Hallucination Guard)

```bash
# Launch tests in parallel:
Task T008: "Write test for _check_hallucination() in tests/test_hallucination_guard.py"
Task T009: "Write test verifying hallucination check called after dispatch in tests/test_hallucination_guard.py"

# Then implement (sequential):
Task T010: "Add _check_hallucination() to dag_executor.py"
Task T011: "Integrate in sync loop"
Task T012: "Integrate in async loop" (parallel with T011 - different code sections)
Task T013: "Update pipeline-contract-base.md"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup (verify JSON fields)
2. Complete US1: Cost Tracking (highest value — enables visibility)
3. Complete US2: Hallucination Guard (safety net — cheap, high-value)
4. **STOP and VALIDATE**: Metrics appear in DB, warnings trigger correctly
5. Deploy — portal "Cost" tab shows real data

### Incremental Delivery

1. US1 (Cost Tracking) → Immediate visibility into pipeline costs
2. US2 (Hallucination Guard) → Safety against fabricated outputs
3. US3 (Quick-Fix) → Developer productivity for small changes
4. US4 (Roadmap-Reassess) → Long-term pipeline intelligence
5. Each increment delivers standalone value

### Key Risks

- **T001 is critical**: If `claude -p --output-format json` doesn't return expected fields, T005/T006 scope changes significantly
- **T010 depends on claude output format**: Need to verify what field tracks tool call count
- **T16 skill creation**: Must go through `/madruga:skills-mgmt create` per repo conventions — do NOT edit `.claude/commands/` directly

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 28 |
| US1 (Cost Tracking) | 5 tasks (T003–T007) |
| US2 (Hallucination Guard) | 6 tasks (T008–T013) |
| US3 (Quick-Fix) | 7 tasks (T014–T020) |
| US4 (Roadmap-Reassess) | 3 tasks (T021–T023) |
| Setup | 2 tasks (T001–T002) |
| Polish | 5 tasks (T024–T028) |
| Parallel opportunities | 8 parallel groups identified |
| MVP scope | US1 + US2 (11 tasks) |

---
handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "28 tasks generated for 4 features (cost tracking, hallucination guard, quick-fix, roadmap-reassess). MVP is US1+US2 (11 tasks). Key risk: T001 must verify claude JSON output format before US1/US2 implementation."
  blockers: []
  confidence: Media
  kill_criteria: "If claude -p --output-format json does not expose token usage or tool call counts, US1 and US2 need significant redesign."
