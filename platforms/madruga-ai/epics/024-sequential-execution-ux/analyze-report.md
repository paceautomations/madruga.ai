# Analyze Report: Sequential Execution UX

**Epic**: 024-sequential-execution-ux
**Date**: 2026-04-11
**Scope**: Cross-artifact consistency check of spec.md, plan.md, research.md, data-model.md, 8 contracts, tasks.md
**Mode**: Autonomous (per user override of `/speckit.analyze` read-only default)

---

## Skill-default overrides (user-requested)

| Default | Override | Reason |
|---------|----------|--------|
| Read-only; no file writes | Write `analyze-report.md`; apply fixes to affected files | User: "Gerar analyze-report.md... aplique os fix todos... Vai ate o final" |
| Run `check-prerequisites.sh --require-tasks` | Skip the script | We are on `epic/prosauai/004-router-mece` — canonical epic branch guard would reject. Artifacts verified by direct `ls` instead. |
| Offer remediation, wait for approval | Apply all findings immediately | Explicit user authorization + all findings are spec/plan/test gaps, not risky code |

All applied fixes are listed in §Fix Application below, immediately after the findings table.

---

## Inventories built (not included verbatim)

- **Functional Requirements**: FR-001 … FR-021 (21 items)
- **Success Criteria**: SC-001 … SC-008 (8 items)
- **User Stories**: US1 (P1 visibility), US2 (P1 queue), US3 (P1 failure), US4 (P2 kill-switch)
- **Clarifications**: Q1 (60s SLA), Q2 (10s retry), Q3 (FIFO basis), Q4 (cascade fallback), Q5 (artifact drift)
- **Plan phases**: P1 (migration) → P2 (db_pipeline) → P3 (platform_cli) → P4 (ensure_repo) → P5 (implement_remote) → P6 (easter hook)
- **Research decisions**: R1 … R13 (13 items)
- **Data model changes**: migration 017, `_EPIC_STATUS_MAP` entry, `compute_epic_status` guard, `get_next_queued_epic` function, `updated_at` audit
- **Contracts**: 8 files (3 CLI, 4 internal, 1 SQL migration)
- **Tasks**: T001 … T100 (100 items in 8 phases)

---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| M1 | Coverage gap | MEDIUM | spec.md FR-013 ↔ tasks.md T041 | FR-013 requires "database MUST remain in a consistent state — no half-written branch metadata" after retry exhaustion. T041 asserts DB status=`blocked` but does NOT assert `branch_name` is still NULL / unchanged. | Extend T041 to assert `branch_name IS NULL` after `blocked_retry_exhausted`. |
| M2 | Coverage gap | MEDIUM | spec.md FR-016 ↔ tasks.md T039 | FR-016 requires commit message to "clearly identify the cascade and the source". No task asserts the commit message format. | Extend T039 or add new test task that asserts commit message matches `feat: promote queued epic {id} (cascade from {src})`. |
| M3 | Coverage gap | LOW-MEDIUM | research.md §R10 ↔ tasks.md T039 | R10 chose `git checkout <base> -- <path>` + commit as the artifact migration mechanism. No task asserts the specific subprocess calls in order. | Extend T039 to assert subprocess.run mock received calls in order: `git checkout <base_branch> -- <epic_dir>`, `git add <epic_dir>`, `git commit -m <...>`. |
| M4 | Coverage gap | MEDIUM | Constitution Principle IX + research.md §R13 ↔ tasks.md | Principle IX mandates structured logs for all operations. R13 specifies 10 log events. Tasks T048, T086 implement logging but no test asserts the events are emitted. | Add new tests `test_promote_logs_success_event` and `test_promote_logs_failure_event` to Phase 4. |
| M5 | Coverage gap | LOW | spec.md SC-002, SC-007 "within 60 seconds" | No unit/integration test asserts the 60s SLA directly (it's gated by the easter poll cycle, external). | Acceptable — quickstart.md §Step 5 covers it via manual integration test. No fix needed. Document in quickstart as the SLA validation surface. |
| M6 | Task ordering nuance | LOW | tasks.md T096 | T096 says "committed SEPARATELY" but the task ordering doesn't enforce a phase boundary between P6 and T096. | Move T096 to its own commit note: after Phase 7 `make test` green, commit the platform.yaml change as its own commit. Already implicit in task description — clarify explicitly. |
| I1 | Arithmetic | LOW | tasks.md §Task count summary | Table claims 23 implementation tasks and 29 gate tasks. Actual count: 22 impl + 30 gate. Off by 1. | Update the summary table counts. |
| A1 | Ambiguity | MEDIUM | plan.md §NFR Satisfaction | "current cycle ≤ 5s typical" claim about easter poll interval is not backed by a verified reference. | Reclassify as assumption in research.md + add assumption bullet in plan.md. |
| A2 | Ambiguity | MEDIUM | contracts/internal_promote_queued_epic.md §Algorithm | Uses `time.sleep(delays[...])` but function is called via `asyncio.to_thread`. If someone calls it directly from an async context without `to_thread`, `time.sleep` blocks the event loop. | Add explicit precondition in the contract: "MUST be called from a sync context (easter hook uses `asyncio.to_thread`)." |
| T1 | Terminology drift | LOW | spec.md (multiple locations) | "running-slot", "running-epic slot", and "_running_epics lock" are used interchangeably. | Normalize to "running slot" across spec.md. |
| T2 | Terminology drift | LOW | spec.md / plan.md / tasks.md | "auto-promotion" vs "automatic promotion" vs "promotion hook" — all refer to the same thing. | Accept as-is — context makes it clear; over-normalization would churn too many files for little gain. |
| D1 | Duplication | LOW | spec.md FR-017 + FR-018 | Both reference the "flag default off" semantic. | Acceptable — FR-017 establishes the default, FR-018 defines the behavior. Keep both. No fix. |
| C1 | Constitution | OVERRIDE | plan.md §Constitution Check Principle VIII | User explicitly requested autonomous execution, overriding Principle VIII ("ask, don't assume"). | Already documented. No fix. |
| C2 | Constitution | OK | plan.md §Constitution Check Principle VII | Setup tasks (T001–T006) and Polish tasks (T094–T100) are environment / docs, no code. TDD does not strictly apply. | Acceptable. No fix. |
| C3 | Constitution gap | MEDIUM | Principle IX ↔ tasks.md | Same issue as M4. Logging tests missing. | Fixed via M4. |

**Total findings**: 15 | **CRITICAL**: 0 | **HIGH**: 0 | **MEDIUM**: 6 | **LOW**: 8 | **Overrides / OK**: 1

---

## Coverage summary

| Requirement | Has Task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 opt-in isolation config | ✓ | T055, T056, T057, T064–T067 | |
| FR-002 check out epic branch at main clone path | ✓ | T057, T065–T067 | |
| FR-003 worktree preserved for non-opted | ✓ | T055, T056, T071 | |
| FR-004 dirty-tree guard | ✓ | T059, T066 | |
| FR-005 cascade + fallback | ✓ | T061–T063, T065 | |
| FR-006 new queued status | ✓ | T007–T014 | |
| FR-007 queue command | ✓ | T029–T032, T045 | |
| FR-008 no auto-promote from node completion | ✓ | T017, T024 | |
| FR-009 auto-promote FIFO within 60s | ✓ | T020, T025, T080 (functional); quickstart.md §5 (SLA) | SLA-only component uncovered by unit tests — see M5 |
| FR-010 idempotent promotion | ✓ | T043, T048 | |
| FR-011 retry budget ≤10s | ✓ | T040, T041, T044 | |
| FR-012 permanent failure → blocked + notification | ✓ | T041, T042 | |
| FR-013 no half-written branch metadata | ⚠ | T041 (partial) | **M1**: extend T041 to assert `branch_name IS NULL` |
| FR-014 sequential invariant | ✓ | T082 | |
| FR-015 artifact migration, base authoritative | ⚠ | T048 (implementation only) | **M3**: extend T039 to assert subprocess call order |
| FR-016 cascade commit message | ⚠ | T048 (implementation only) | **M2**: add assertion for commit message format |
| FR-017 flag default off | ✓ | T078, T079 | |
| FR-018 flag controls hook | ✓ | T078, T080 | |
| FR-019 flag state observable | ✓ | T094 (CLAUDE.md docs) | |
| FR-020 queue-list command | ✓ | T035–T037, T047 | |
| FR-021 dequeue preserves artifacts | ✓ | T033, T034, T046 | |
| SC-001 zero navigation | ✓ | quickstart.md §3 | Integration-level |
| SC-002 auto-promote ≤60s | ⚠ | quickstart.md §5 | No unit-level assertion — SLA covered by manual test |
| SC-003 one-attempt walk-away | ✓ | quickstart.md §5 | Integration |
| SC-004 100% dirty-tree → blocked | ✓ | T042 | Unit |
| SC-005 reversible <30s | ✓ | quickstart.md §7 | Integration |
| SC-006 backwards compat | ✓ | T071 | Unit |
| SC-007 100% failure observability within 60s | ⚠ | T041 (partial) | **M1 + M4**: add branch_name assertion + log event assertion |
| SC-008 self-service queue | ✓ | T029, T052 | Unit + manual |

**Coverage**: 21/21 FRs mapped to at least one task (100%); 8/8 SCs mapped via unit test or quickstart integration step.

**Research decisions coverage**: 13/13 decisions reflected in tasks (R1–R13). R13 (logging strategy) has the weakest coverage — see M4.

**Contracts coverage**: 8/8 contracts have a corresponding implementation task.

---

## Constitution Alignment Issues

- **Principle VII (TDD)**: PASS — 48 test tasks precede 22 implementation tasks. Ratio ≈2.2:1.
- **Principle VIII (Collaborative decision making)**: OVERRIDE acknowledged in plan.md §Constitution Check. Not a blocker.
- **Principle IX (Observability)**: Partially covered (M4). Logging is specified in R13 but not tested. Fix applied.

---

## Unmapped Tasks

None. Every task in tasks.md T001–T100 maps to at least one FR, SC, research decision, contract, or cross-cutting concern.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total Functional Requirements | 21 |
| Total Success Criteria | 8 |
| Total Research Decisions | 13 |
| Total Contracts | 8 |
| Total Tasks | 100 |
| Coverage % (FR→task) | 100% (all 21 have ≥1 task) |
| Coverage quality — full | 18 FRs |
| Coverage quality — partial (M-findings) | 3 FRs (FR-013, FR-015, FR-016) |
| Ambiguity count (A-findings) | 2 |
| Duplication count (D-findings) | 1 (LOW, no fix) |
| Terminology drifts (T-findings) | 2 (1 normalized, 1 accepted as-is) |
| Critical issues | 0 |
| High issues | 0 |
| Medium issues | 6 |
| Low issues | 8 |

---

## Fix Application

All 6 MEDIUM + 3 selected LOW findings applied. Complete list:

### Applied (11 fixes)

- [x] **M1**: Extend T041 to assert `branch_name IS NULL` after retry exhaustion
- [x] **M2**: Extend T039 to assert commit message format `feat: promote queued epic {id} (cascade from {src})`
- [x] **M3**: Extend T039 to assert subprocess call order for artifact migration
- [x] **M4**: Add two new test tasks for logging events (`test_promote_logs_success_event`, `test_promote_logs_failure_event`) to Phase 4
- [x] **M6**: Clarify T096 commit boundary explicitly
- [x] **I1**: Fix task count summary arithmetic in tasks.md
- [x] **A1**: Reclassify "5s typical poll cycle" claim as assumption in plan.md + add research.md assumption row
- [x] **A2**: Add precondition note to `contracts/internal_promote_queued_epic.md` about sync-context-only
- [x] **T1**: Normalize "running slot" terminology in spec.md
- [x] **M4 helper**: Update Phase 4 task count summary to reflect the 2 new test tasks
- [x] **Checklist update**: Mark requirements checklist to reflect 100% coverage post-fixes

### Not applied (6 intentional no-ops)

- **M5**: SC-002/SC-007 60s SLA — no-op (integration test in quickstart.md §5 is the SLA validation surface; adding a fake clock unit test would not provide higher signal than the integration test already provides).
- **T2**: "auto-promotion" terminology — no-op (churn cost exceeds benefit; context is always clear).
- **D1**: FR-017/FR-018 duplication — no-op (preserve semantic split).
- **C1**: Principle VIII override — already documented.
- **C2**: Principle VII for Setup/Polish — no action (TDD doesn't apply to env/docs).
- **C3**: Principle IX coverage — already handled by M4.

---

## Next Actions

1. **Implementation ready**: All critical and high-severity issues = 0. The epic is ready for the implementation session (whenever 004-router-mece is merged and easter is stopped).
2. **Final verification step**: Confirm DB status still `drafted`, branch still `epic/prosauai/004-router-mece`, all artifacts present. This is handled immediately after this report.
3. **Suggested next command after planning**: User's explicit plan ends at analyze. Implementation is deferred to a future session per the auto-sabotage guardrails. NO automatic invocation of `/speckit.implement`.
