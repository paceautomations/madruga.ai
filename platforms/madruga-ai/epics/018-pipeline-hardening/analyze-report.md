# Specification Analysis Report

**Epic**: 018-pipeline-hardening | **Date**: 2026-04-04  
**Artifacts**: spec.md, plan.md, tasks.md, research.md, data-model.md  
**Phase**: Pre-implementation analysis

---

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | HIGH | spec.md:FR-010, tasks.md | **FR-010 (validate platform config at load time) has no task.** Pitch and research R5 mention a `PlatformConfig` dataclass but no task creates it. T002 creates validation functions, T009-T010 handle Node dataclass — neither covers PlatformConfig. | Add a task in Phase 4 to create `PlatformConfig` dataclass (name, repo_org, repo_name validated at load) or downscope FR-010 to match what T009-T010 actually deliver. |
| C2 | Inconsistency | HIGH | spec.md:US3 vs research.md:R3, tasks.md:T012 | **Per-skill vs global circuit breaker mismatch.** Spec US3 says "3 consecutive failures of the same skill." Research R3 reveals the existing breaker is **global** (all skills), not per-skill. Tasks T012-T013 just change the constant — delivering global behavior, not the per-skill behavior the spec promises. | Align spec US3 wording to say "3 consecutive dispatch failures" (global). The current plan is correct engineering but the spec overpromises. |
| C3 | Inconsistency | MEDIUM | spec.md:SC-006, tasks.md:T018-T022 | **SC-006 overpromises scope.** SC-006 says "zero `SystemExit` calls remain in the 4 main scripts." But tasks only replace: dag_executor (4x `raise SystemExit` → typed errors), ensure_repo (3x `raise SystemExit`). platform_cli has 19 `sys.exit()` calls and only "validation paths" are replaced (T020). post_save gets only an import (T021). | Narrow SC-006 to: "Zero `raise SystemExit(...)` in library functions (parse_dag, topological_sort, _load_repo_binding). CLI `main()` and `sys.exit()` for argparse/flow control are kept." |
| C4 | Inconsistency | MEDIUM | pitch T4, research.md:R4, data-model.md | **Platform name regex inconsistency.** Pitch says `^[a-z0-9][a-z0-9-]*$` (digit start allowed). Research R4 and data-model say `^[a-z][a-z0-9-]*$` (letter start only, matching existing `cmd_new` at platform_cli.py:153). Tasks don't specify which regex to use. | Use `^[a-z][a-z0-9-]*$` per research decision. Already aligned with `cmd_new`. Pitch has a stale value — no action needed since research supersedes. |
| C5 | Underspecification | MEDIUM | tasks.md:T004 | **T004 claims 9 `conn.close()` occurrences but lists 8 line numbers.** Actual grep confirms 8 occurrences in `run_pipeline_async()` (lines 958, 999, 1020, 1051, 1082, 1126, 1169, 1198). | Fix T004 description: 8 occurrences, not 9. |
| C6 | Underspecification | MEDIUM | tasks.md:T005 | **T005 claims 8 `conn.close()` occurrences but lists 7 line numbers.** Actual grep confirms 7 occurrences in `run_pipeline()` (lines 1395, 1438, 1453, 1477, 1521, 1563, 1591). | Fix T005 description: 7 occurrences, not 8. |
| C7 | Inconsistency | MEDIUM | tasks.md:T004-T005 vs source | **Line number drift in tasks.** Tasks reference `run_pipeline_async()` at "line ~924" but it starts at line 872. `run_pipeline()` referenced at "line ~1375" but starts at line 1312. `parse_dag()` at "line ~497" but at 465. These are ~50 lines off. | Not blocking — tasks use `~` prefix. But implementer should use grep, not line numbers. |
| C8 | Coverage | MEDIUM | spec.md:FR-011, tasks.md:T021 | **T021 is a no-op.** "Add `import errors` to post_save.py for forward compatibility" adds an unused import. Research R6 confirms post_save.py is already clean with 0 `raise SystemExit`. Ruff will flag unused imports. | Remove T021 entirely. post_save.py needs no changes for this epic. |
| C9 | Constitution | LOW | constitution:VII (TDD), tasks.md | **TDD ordering not strictly followed.** Constitution Principle VII says "Write tests before implementation." Tasks are organized implement-first, test-second within each phase (e.g., T009 modifies source, T011 adds tests). | Acceptable deviation — the tasks note "modify source code first, then update/add tests" explicitly. For mechanical refactoring (context managers, constant changes), strict red-green-refactor adds overhead without value. Constitution allows pragmatic judgment per Principle I. |
| C10 | Underspecification | LOW | spec.md:Edge Cases, tasks.md | **3 edge cases from spec have no task coverage.** (1) DB locked by another process during cleanup, (2) Ctrl+C during DB writes, (3) circuit breaker with multiple different failing skills. | These are acknowledged edge cases, not requirements. The global circuit breaker actually handles (3) correctly. (1) and (2) are SQLite WAL mode behaviors — out of scope per spec assumptions. No action needed. |
| C11 | Coverage | LOW | tasks.md:T014 | **T014 doesn't cover `cmd_new()`.** It adds `validate_platform_name()` to cmd_use, cmd_lint, cmd_status, cmd_gate_list but cmd_new already has its own regex (line 153). After T014, there will be two validation patterns: cmd_new's inline regex + errors.py's function. | Add a note in T020 (US6 error migration) to replace cmd_new's inline regex with `validate_platform_name()` for consistency. |

---

## Coverage Summary

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 (context managers) | YES | T004, T005, T006, T007, T008 | Full coverage across 4 scripts |
| FR-002 (gate fail-closed) | YES | T009, T010 | Via Node `__post_init__` |
| FR-003 (gate warning log) | YES | T009 | `log.warning` in `__post_init__` |
| FR-004 (3 consecutive failures) | YES | T012 | Constant change |
| FR-005 (reset counter on success) | YES | T013 | Existing behavior, tested |
| FR-006 (platform name validation) | YES | T002, T014, T016 | Centralized + entry points |
| FR-007 (repo component validation) | YES | T002, T015 | Centralized + entry point |
| FR-008 (path traversal `..`) | YES | T002, T017 | `validate_path_safe()` + tests |
| FR-009 (DAG node parse-time validation) | YES | T009, T010 | Via Node `__post_init__` |
| FR-010 (platform config validation) | **NO** | — | **No `PlatformConfig` dataclass task. See finding C1.** |
| FR-011 (typed error hierarchy) | YES | T002, T018, T019, T020 | errors.py + migration |
| FR-012 (SIGINT graceful shutdown) | YES | T023, T024, T025 | Signal handler + KeyboardInterrupt |
| FR-013 (make test passes) | YES | T001, T027 | Baseline + final |
| FR-014 (make ruff passes) | YES | T028, T029 | Final polish |

| Success Criterion | Buildable? | Covered? | Notes |
|-------------------|-----------|----------|-------|
| SC-001 (zero conn leaks) | YES | YES | Phase 3 |
| SC-002 (fail-closed gates) | YES | YES | Phase 4 |
| SC-003 (retry containment) | YES | YES | Phase 5 |
| SC-004 (path/injection rejection) | YES | YES | Phase 6 |
| SC-005 (parse-time validation) | YES | PARTIAL | Node covered; PlatformConfig missing (C1) |
| SC-006 (typed exceptions) | YES | PARTIAL | Scope narrower than stated (C3) |
| SC-007 (SIGINT cleanup) | YES | YES | Phase 8 |
| SC-008 (tests pass + new tests) | YES | YES | Phase 9 |

---

## Unmapped Tasks

| Task | Mapped To | Notes |
|------|-----------|-------|
| T001 | FR-013 | Baseline verification |
| T021 | FR-011 | **No-op — unused import. See C8.** |
| T027-T030 | FR-013, FR-014 | Polish phase |

All other tasks map to at least one FR or SC.

---

## Constitution Alignment Issues

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pragmatism | PASS | Proven patterns, no over-engineering |
| II. Automate | PASS | Automating safety checks |
| III. Structured Knowledge | PASS | Error hierarchy is self-documenting |
| IV. Fast Action | PASS | Incremental delivery, each phase testable |
| V. Alternatives | PASS | Research documents alternatives for all decisions |
| VI. Brutal Honesty | PASS | Pitch honestly identifies real bugs |
| VII. TDD | MINOR DEVIATION | Implement-then-test order (see C9). Pragmatically acceptable. |
| VIII. Collaborative Decision | PASS | Decisions documented in research.md |
| IX. Observability | PASS (deferred) | Structured logging explicitly deferred to epic 020 |

No CRITICAL constitution violations.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Functional Requirements | 14 |
| Total Success Criteria | 8 |
| Total Tasks | 30 |
| FR Coverage (FR with ≥1 task) | 13/14 = **92.9%** |
| SC Coverage (buildable SC with tasks) | 6/8 full + 2/8 partial = **87.5%** |
| Ambiguity Count | 0 (no vague adjectives or placeholders) |
| Duplication Count | 0 |
| Critical Issues | 0 |
| High Issues | 2 (C1, C2) |
| Medium Issues | 6 |
| Low Issues | 3 |

---

## Next Actions

No CRITICAL issues found. Two HIGH issues should be resolved before `/speckit.implement`:

1. **C1 (FR-010 gap)**: Either add a `PlatformConfig` dataclass task or explicitly downscope FR-010 in spec.md to "DAG node validation only." Recommendation: downscope — PlatformConfig can be added in epic 020 alongside db.py refactoring.

2. **C2 (per-skill vs global breaker)**: Update spec US3 acceptance scenarios to say "3 consecutive dispatch failures" instead of "3 consecutive failures of the same skill." The implementation (global breaker) is correct — the spec just needs to match.

3. **C8 (T021 no-op)**: Remove T021 to avoid an unused-import lint violation.

The remaining MEDIUM/LOW findings are informational and do not block implementation. You may proceed with `/speckit.implement` after resolving C1 and C2.

---

Would you like me to suggest concrete remediation edits for the top 3 issues (C1, C2, C8)?
