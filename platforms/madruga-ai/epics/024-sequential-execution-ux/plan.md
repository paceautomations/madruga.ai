# Implementation Plan: Sequential Execution UX

**Branch**: `epic/madruga-ai/024-sequential-execution-ux` (to be created at implementation time — planning runs on `epic/prosauai/004-router-mece` per auto-sabotage guardrail Camada 0)
**Date**: 2026-04-11
**Spec**: [spec.md](spec.md)
**Input**: Feature specification from `platforms/madruga-ai/epics/024-sequential-execution-ux/spec.md`

## Summary

Epic 024 introduces two opt-in mechanisms that together remove the two biggest operational frictions in the external-platform L2 pipeline:

1. **New isolation mode** (`repo.isolation: branch`) — the pipeline checks out epic branches directly in the platform's main clone instead of in a disposable worktree, so developers see live progress in their editor without navigating to worktree paths.
2. **New epic status `queued` + auto-promotion hook** — developers mark drafted epics as "next in line" with one command; when a running epic ships, the easter daemon automatically promotes the next queued epic within 60 seconds, creating its branch with cascade semantics and a dirty-tree guard.

Both changes are **additive** to the existing pipeline and protected by feature flags, so the code can be merged and deployed without activating the new behavior. The entire feature set is gated by `MADRUGA_QUEUE_PROMOTION` (runtime kill-switch) and by per-platform opt-in in `platform.yaml`.

This plan applies a **strict additive task order** (migration → db_pipeline → platform_cli → ensure_repo → implement_remote → easter) so that each commit leaves the madruga-ai self-reference pipeline fully functional and no restart of the easter daemon is required until the final phase. This is driven by the auto-sabotage guardrails captured in [pitch.md](pitch.md) §Applicable Constraints.

## Technical Context

**Language/Version**: Python 3.12 (stdlib only — match/case, StrEnum, asyncio)
**Primary Dependencies**: Standard library only (sqlite3, subprocess, pathlib, os, asyncio, logging). Optional: pyyaml for platform.yaml reading (already in project dependencies per ADR-004). No new third-party packages.
**Storage**: SQLite WAL mode (`.pipeline/madruga.db`) — schema change via rec-table migration 017.
**Testing**: pytest (existing), unittest.mock for subprocess and DB, real SQLite temp files for migration tests (no mocks for DB schema). Test-first per Constitution Principle VII.
**Target Platform**: Linux (WSL2), Python 3.12+ runtime, systemd user services for the easter daemon.
**Project Type**: CLI + background daemon (madruga.ai pipeline — existing codebase).
**Performance Goals**: Auto-promotion latency ≤ 60 seconds wall-clock from running-slot free → next queued epic in_progress (SC-002). Retry budget ≤ 10 seconds total (FR-011).
**Constraints**: 
- ADR-004: stdlib only, no new deps
- ADR-006: asyncio single-process; git blocking I/O wrapped in `asyncio.to_thread()`
- ADR-010: raw `subprocess` for git operations
- Sequential invariant: at most one epic per platform in `in_progress` at any time
- `.pipeline/madruga.db` not tracked (A1) — test migrations on copies, never against live DB during dev
- Feature flag `MADRUGA_QUEUE_PROMOTION` default OFF — hook must be a no-op unless explicitly enabled
- Auto-sabotage guardrails (Camadas 0–5) from pitch.md

**Scale/Scope**: 
- ~5–10 platforms in production
- 2–3 queued epics per platform at most
- 1 promotion event per epic ship (low frequency: hours to days)
- ~8 files modified, ~2 files created, 1 SQL migration, ~15–25 unit/integration tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Compliance | Notes |
|---|-----------|-----------|-------|
| I | Pragmatism / Simplicity | ✓ | Additive changes only; reuses existing SQLite + subprocess + asyncio patterns; no new abstractions. Simpler than a dedicated queue table or dedicated queue service. |
| II | Automate repetitive tasks | ✓ | This epic IS automation — it eliminates the manual `/madruga:epic-context` between epics. |
| III | Structured knowledge | ✓ | pitch.md + decisions.md (13 entries) + spec.md + this plan + research.md + data-model.md + contracts/ keep context explicit. |
| IV | Fast action > planning | ⚠ | Planning phase is deliberately longer than usual because the epic modifies files the pipeline itself executes — the auto-sabotage risk justifies extra design time up front. Accepted trade-off. |
| V | Alternatives & trade-offs | ✓ | research.md documents alternatives for each major decision (isolation mode location, queue representation, hook placement, etc.). |
| VI | Brutal honesty | ✓ | Plan explicitly calls out that `madruga-ai` self-ref is NOT a target of the new isolation mode; worktree.py stays as default; `easter.py` hook is the single most dangerous modification and goes last. |
| VII | TDD | ✓ | Every phase has a test written before the production code change. See Phase breakdown — each phase's first task is "write failing test, then implementation". Existing `tests/test_dag_executor.py`, `tests/test_platform_cli.py`, `tests/test_easter.py` are the insertion points. |
| VIII | Collaborative decision making | ⚠ OVERRIDE | User explicitly requested autonomous execution of the planning phase ("aplique os fix todos"). All 5 clarifications in spec.md were self-answered with rationale; all design decisions in research.md are picked by the best-fit heuristic. Override logged here for traceability. |
| IX | Observability & logging | ✓ | New functions in `promote_queued_epic`, `get_repo_work_dir`, and the easter hook all emit `structlog`-style structured logs at INFO for state transitions and ERROR for failures (matches existing easter.py conventions). |

**Gate status**: PASS (no unjustified violations). Principle VIII override is explicit and time-boxed to this epic planning phase.

## Project Structure

### Documentation (this feature)

```text
platforms/madruga-ai/epics/024-sequential-execution-ux/
├── pitch.md                    # Shape Up pitch (updated with 6 guardrails + decision #10)
├── decisions.md                # 13 captured decisions (updated 2026-04-11)
├── spec.md                     # Feature specification + clarifications
├── plan.md                     # This file
├── research.md                 # Phase 0 — technical decisions with rationale + alternatives
├── data-model.md               # Phase 1 — DB schema + state machine
├── quickstart.md               # Phase 1 — end-to-end smoke test walkthrough
├── contracts/                  # Phase 1 — CLI + internal function contracts
│   ├── cli_platform_queue.md
│   ├── cli_platform_dequeue.md
│   ├── cli_platform_queue_list.md
│   ├── internal_get_repo_work_dir.md
│   ├── internal_promote_queued_epic.md
│   ├── internal_checkout_epic_branch.md
│   ├── internal_easter_promotion_hook.md
│   └── db_migration_017.sql
├── checklists/
│   └── requirements.md         # Spec quality checklist (filled)
└── tasks.md                    # Phase 2 output (/speckit.tasks — next step, NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
.specify/
├── migrations/
│   └── 017_add_queued_status.sql   # NEW — rec-table pattern, adds 'queued' to CHECK constraint
├── scripts/
│   ├── db_pipeline.py              # MODIFIED — additive: _EPIC_STATUS_MAP["queued"], compute_epic_status guard, get_next_queued_epic()
│   ├── ensure_repo.py              # MODIFIED — NEW FUNCTION get_repo_work_dir() (not yet called)
│   ├── platform_cli.py             # MODIFIED — NEW subcommands queue / dequeue / queue-list; NEW function promote_queued_epic()
│   ├── implement_remote.py         # MODIFIED — swap create_worktree() call-site to get_repo_work_dir()
│   ├── easter.py                   # MODIFIED (LAST) — add promotion hook after _running_epics.discard, gated by MADRUGA_QUEUE_PROMOTION
│   └── tests/
│       ├── test_db_pipeline.py         # MODIFIED — add tests for queued status map, guard, get_next_queued_epic
│       ├── test_migration_017.py       # NEW — idempotent rec-table migration test
│       ├── test_ensure_repo.py         # MODIFIED — add tests for get_repo_work_dir (both isolation modes)
│       ├── test_platform_cli.py        # MODIFIED — add tests for queue / dequeue / promote_queued_epic
│       ├── test_implement_remote.py    # MODIFIED — verify work_dir dispatch to get_repo_work_dir
│       └── test_easter.py              # MODIFIED (LAST) — verify hook fires with flag on, no-op with flag off
platforms/
└── prosauai/
    └── platform.yaml              # MODIFIED (at rollout time, not part of epic code changes) — add repo.isolation: branch
```

**Structure Decision**: The feature is implemented entirely inside the existing `.specify/scripts/` module tree. No new packages, no new directories outside the epic's own artifacts. Tests live adjacent to the scripts in `.specify/scripts/tests/`, following the existing convention.

## Architecture Overview

### Component interactions (happy path)

```
Developer                      Pipeline CLI                SQLite DB              Easter Daemon
   │                                │                          │                         │
   │ /madruga:epic-context --queue  │                          │                         │
   ├──────────────────────────────>│                          │                         │
   │                                │ UPDATE epics SET status='queued'                   │
   │                                ├─────────────────────────>│                         │
   │                                │                          │                         │
   │                                │  (earlier: running epic N ships)                   │
   │                                │                          │                         │
   │                                │                          │ poll (5s interval)      │
   │                                │                          │<────────────────────────┤
   │                                │                          │                         │
   │                                │                          │ _running_epics empty     │
   │                                │                          │ AND queued epic exists   │
   │                                │                          │ AND MADRUGA_QUEUE_PROMOTION=1 │
   │                                │                          │                         │
   │                                │                          │<───promote_queued_epic──┤
   │                                │                          │     (git + DB via asyncio.to_thread) │
   │                                │                          │                         │
   │                                │                          │ UPDATE status='in_progress' │
   │                                │                          │<────────────────────────┤
   │                                │                          │                         │
   │                                │                          │ dispatch via dag_executor │
   │                                │                          │<────────────────────────┤
```

### Phase layering (STRICT additive order, per auto-sabotage guardrail Camada 2)

Each phase is its own commit, with `make test` green before the next phase begins. Each phase leaves the pipeline fully functional on its own.

| Phase | File(s) | Nature | Reversible? | Risk if broken | Pipeline impact if deployed alone |
|-------|---------|--------|-------------|----------------|-----------------------------------|
| P1 | `017_add_queued_status.sql` | Schema change (additive — adds value to CHECK) | YES (reverse rec-table migration) | Low — existing rows stay valid | None; DB accepts new `queued` but nothing writes it |
| P2 | `db_pipeline.py` | Additive: status map entry + guard list entry + new `get_next_queued_epic()` | YES (revert file) | Low — no existing call sites changed | None; new functions unused |
| P3 | `platform_cli.py` (queue/dequeue/queue-list subcommands + `promote_queued_epic` helper) | Additive: new subcommands, new helper | YES (revert file) | Low — existing commands unchanged | Developers can manually set queued/dequeue, but no auto-promotion yet |
| P4 | `ensure_repo.py::get_repo_work_dir` (new function, not yet called) | Additive: new function | YES (revert file) | Low — function is dead code until P5 | None |
| P5 | `implement_remote.py` (call-site swap) | **Call-site swap** — replaces `create_worktree()` with `get_repo_work_dir()` | YES (revert call) | **Medium** — this is the first phase that changes runtime behavior for external platforms if they are opted in. Platforms NOT opted in still use worktree (backwards compatible). | Platforms with `repo.isolation: branch` start using main clone for work_dir. Others unchanged. |
| P6 | `easter.py` (promotion hook, gated by flag) | Additive: new code path, gated by `MADRUGA_QUEUE_PROMOTION` env var | YES (revert file OR set flag to 0 without revert) | **High** — `easter.py` is the daemon. But gated by default-off flag, so runtime behavior unchanged unless explicitly enabled. | None until flag enabled. |

After P6, the feature is code-complete but runtime-inactive. Activation happens in a separate step (flip the feature flag) and is NOT part of this epic's implementation phase.

### Why this order

- **P1 first**: Schema must exist before any code writes to `queued`. The migration is additive to the CHECK constraint — existing rows (proposed, drafted, in_progress, shipped, blocked, cancelled) remain valid. Zero risk to pre-P1 code.
- **P2 second**: The status map + guard entries are additive dict/list modifications — existing code paths for other statuses unchanged.
- **P3 third**: CLI commands can exist and be called manually without any runtime hook consuming them. Manual `platform_cli.py queue prosauai 001-foo` works after P3 but nothing promotes yet.
- **P4 fourth**: New function in `ensure_repo.py` but nothing calls it. Pure dead code until P5.
- **P5 fifth**: First behavior change. Only affects platforms explicitly opted in (`repo.isolation: branch` in platform.yaml). Default behavior preserved.
- **P6 last**: The daemon touch. Gated by feature flag. Even after P6 is merged, runtime remains unchanged unless the operator exports `MADRUGA_QUEUE_PROMOTION=1`.

### Rollback strategy

Each phase is independently revertible. If a regression is detected after deployment:

| Regression in | Rollback action |
|---------------|-----------------|
| P6 (easter hook) | Unset env var `MADRUGA_QUEUE_PROMOTION` OR revert commit (no daemon restart needed to unset env var — daemon reads env on startup; restart with flag unset) |
| P5 (call-site swap) | Revert commit OR set `repo.isolation: worktree` in platform.yaml |
| P4 | Revert commit (dead code — zero runtime impact either way) |
| P3 | Revert commit — only affects CLI surface |
| P2 | Revert commit — only affects new DB functions |
| P1 | Run reverse rec-table migration (SQL file to be created alongside, but not required for forward migration) |

## Non-Functional Requirements Satisfaction

| SC | Requirement | How Plan Satisfies It |
|----|-------------|----------------------|
| SC-001 | Developer sees active epic branch in editor with zero navigation | Phase 5 swaps work_dir to main clone path for opted-in platforms |
| SC-002 | ≤60s latency for auto-promotion | Phase 6 hook runs inside existing easter poll loop. Assumption (see research.md §R14): the current easter poll cycle is short enough that a 60s SLA is easily achievable. The 60s number is the outer SLA budget — the actual delay is bounded by the poll interval + the retry budget (≤10s) + DB write time. |
| SC-003 | End-to-end queue-two-walk-away completes in one attempt | Phases 1–6 combined, with feature flag enabled |
| SC-004 | 100% dirty-tree failures → blocked with notification | Phase 3 `promote_queued_epic` uses `git status --porcelain` guard; Phase 6 hook propagates failure to `blocked` status |
| SC-005 | Rollout reversible <30s | Feature flag env var can be unset and easter restarted in seconds |
| SC-006 | Backwards compatibility | Phase 4 creates function that defaults to `worktree` path; Phase 5 preserves worktree behavior for non-opted-in platforms |
| SC-007 | 100% failure observability | `promote_queued_epic` writes to `structlog` + transitions DB status atomically within retry budget |
| SC-008 | Self-service queue command | Phase 3 `platform_cli.py queue <platform> <epic>` subcommand |

## Open Questions / NEEDS CLARIFICATION

**None.** All 5 clarifications were resolved in spec.md (see `## Clarifications` section). All technical decisions deferred to research.md with rationale and alternatives.

## Complexity Tracking

No violations. Feature stays within stdlib, reuses existing patterns (subprocess git, asyncio.to_thread, rec-table migration), introduces no new abstractions, no new services, no new processes.

## Exit Criteria for Planning Phase

- [x] `spec.md` + `## Clarifications` section complete
- [x] `plan.md` (this file) — architecture + phase ordering + constitution check
- [x] `research.md` — all technical decisions with rationale + alternatives
- [x] `data-model.md` — DB schema + state machine
- [x] `quickstart.md` — end-to-end test walkthrough
- [x] `contracts/` — CLI + internal function contracts (8 files)
- [ ] `tasks.md` — generated by `/speckit.tasks` in the next step (NOT this skill)
- [ ] `analyze-report.md` — generated by `/speckit.analyze` after tasks.md (NOT this skill)

Planning phase terminates here. Implementation deferred to a future session where:
1. Epic 004-router-mece is merged to main
2. Easter daemon is explicitly stopped (Camada 0)
3. `.pipeline/madruga.db` is backed up (Camada 1)
4. A dedicated branch `epic/madruga-ai/024-sequential-execution-ux` is created
5. Phases P1–P6 are executed in strict order, with `make test` green between each
