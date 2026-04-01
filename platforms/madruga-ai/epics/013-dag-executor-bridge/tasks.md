---
title: "Tasks: DAG Executor + SpeckitBridge"
updated: 2026-03-31
---
# Tasks: DAG Executor + SpeckitBridge

## Dependencies

```
Phase 1 (Setup) → Phase 2 (DB) → Phase 3 (DAG Parser) → Phase 4 (SpeckitBridge)
                                                       → Phase 5 (Dispatch)
Phase 4 + Phase 5 → Phase 6 (Gates) → Phase 7 (Resilience) → Phase 8 (Integration)
```

## LOC Budget

| Arquivo | Estimado | Real |
|---------|----------|------|
| dag_executor.py | ~420 | 494 |
| db.py | +40 | +55 |
| platform.py | +30 | +45 |
| implement_remote.py | +50 | 0 (compose_skill_prompt in dag_executor.py) |
| 007_gate_fields.sql | ~10 | 11 |
| test_dag_executor.py | ~300 | 420 |
| test_db_gates.py | — | 110 |
| **Total producao** | **~550** | **~605** |
| **Total com testes** | **~850** | **~1135** |

---

## Phase 1: Setup

- [x] T001 Create migration `.pipeline/migrations/007_gate_fields.sql` — ALTER TABLE pipeline_runs ADD COLUMN gate_status, gate_notified_at, gate_resolved_at. Run migration via `python3 -c "from db import get_conn, migrate; migrate(get_conn())"` to verify.

---

## Phase 2: DB Extensions

- [x] T002 [P] Extend `.specify/scripts/db.py` with gate functions: `approve_gate(conn, run_id)`, `reject_gate(conn, run_id)`, `get_pending_gates(conn, platform_id)`, `get_resumable_nodes(conn, platform_id, epic_id=None)` (~40 LOC). Add tests in `tests/test_db_gates.py` (~60 LOC).

---

## Phase 3: DAG Parser [US1]

- [x] T003 [US1] Create `.specify/scripts/dag_executor.py` — initial structure with Node namedtuple, `parse_dag(platform_yaml_path, mode, epic=None)` that reads YAML and returns list of Nodes, and `topological_sort(nodes)` using Kahn's algorithm with cycle detection (~70 LOC). Add tests for parser + sort in `tests/test_dag_executor.py` (~80 LOC): valid DAG order, cycle detection error, unknown dependency error.

---

## Phase 4: SpeckitBridge [US4]

- [x] T004 [P] [US4] Extend `.specify/scripts/implement_remote.py` with `compose_skill_prompt(platform_name, node_id, skill, outputs, depends_artifacts, epic_slug=None)` (~50 LOC). For L1 madruga:* skills: "Execute /<skill> <platform>" + dependency artifacts content. For L2 speckit.implement: delegate to existing compose_prompt(). For other L2 speckit.*: adapted prompt with epic artifacts. Add tests in `tests/test_implement_remote.py` (~40 LOC): L1 prompt, L2 implement prompt, L2 specify prompt, missing artifact warning.

---

## Phase 5: Dispatch Loop [US1]

- [x] T005 [US1] Add to `dag_executor.py`: `dispatch_node(node, cwd, timeout, compose_fn)` — subprocess.run with claude -p, --output-format json, timeout. Returns (success: bool, error: str|None). Add `verify_outputs(node, platform_dir)` — check all output files exist. (~80 LOC). Tests: mock subprocess success, mock subprocess failure, output verification pass/fail (~60 LOC).

---

## Phase 6: Gate State Machine [US2]

- [x] T006 [US2] Add to `dag_executor.py`: gate detection in run_pipeline() — check node.gate, if human/1-way-door: insert_run with gate_status=waiting_approval, print instructions, return. Resume logic: read DB for completed/approved nodes, skip them. (~50 LOC). Tests: gate pause behavior, resume skips done nodes, resume with approved gate (~60 LOC).

- [x] T007 [US2] Extend `.specify/scripts/platform.py` with `cmd_gate_approve(args)`, `cmd_gate_reject(args)`, `cmd_gate_list(args)` subcommands + argparse setup (~30 LOC).

---

## Phase 7: Resilience [US3]

- [x] T008 [US3] Add to `dag_executor.py`: `CircuitBreaker` class (closed/open/half-open, max_failures=5, recovery_seconds=300) with `check()`, `record_failure()`, `record_success()` methods. Integrate retry loop in dispatch_node(): 3 attempts with backoff [5, 10, 20]s. (~80 LOC). Tests: retry 3x then fail, circuit breaker opens at 5, half-open after recovery, watchdog timeout (~80 LOC).

---

## Phase 8: Integration & Polish [US5] [US6]

- [x] T009 [US5] Add to `dag_executor.py`: L2 mode — `--epic` flag, parse epic_cycle.nodes, use epic_nodes table for state, resolve {epic} template in outputs (~40 LOC). Tests: L2 dry-run order, L2 state in epic_nodes (~40 LOC).

- [x] T010 [US6] [US1] Add to `dag_executor.py`: `run_pipeline()` orchestrator + `main()` with argparse (--platform, --epic, --resume, --dry-run, -v, --timeout). Wire all components together (~60 LOC). Integration test: dry-run L1 full pipeline prints correct order.

- [x] T011 Run `ruff check` + `ruff format` on all modified files. Verify LOC budget: `wc -l dag_executor.py` within 400-550. Run full test suite: `pytest tests/test_dag_executor.py tests/test_db_gates.py -v`. Update LOC budget table with real values.

---

## Parallel Execution Opportunities

Tasks T002 and T004 can run in parallel (different files, no dependencies).
Tasks T003 and T004 can run in parallel after T001.

## Implementation Strategy

**MVP (US1 + US2 + US3)**: Phases 1-7 — executor funcional com dispatch, gates, retry.
**Complete (+ US4 + US5 + US6)**: Phase 8 — L2 mode, full integration.

---
handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "11 tasks em 8 fases. ~550 LOC producao + ~300 LOC testes. Pronto para analyze."
  blockers: []
  confidence: Alta
