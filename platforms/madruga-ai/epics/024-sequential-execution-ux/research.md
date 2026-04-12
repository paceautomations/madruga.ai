# Research: Sequential Execution UX

**Epic**: 024-sequential-execution-ux
**Date**: 2026-04-11
**Status**: Phase 0 complete — all technical unknowns resolved

This document records every non-trivial technical decision taken during planning, with rationale and at least 2 alternatives considered. Each decision is traceable to a row in `decisions.md` or to a constraint in `pitch.md` / `spec.md`.

---

## R1. Isolation mode opt-in: where to put the flag?

**Decision**: Add an optional field `repo.isolation: worktree | branch` to `platform.yaml`. Default is `worktree` (preserves existing behavior). Per-platform, declarative, versioned in git.

**Rationale**:
- Platform-scoped config (not global) — each platform migrates on its own timeline
- Declarative in `platform.yaml` means the choice is visible at the platform manifest level, next to `repo.name`, `repo.base_branch`, etc. No hidden state in DB or env vars
- Default `worktree` preserves backwards compatibility — unconfigured platforms behave exactly as before
- Matches existing pattern: `platform.yaml` already has `repo.epic_branch_prefix`, `repo.base_branch`, etc.

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Global env var `MADRUGA_ISOLATION_MODE` | Simple, one toggle for rollout | All platforms migrate at once — too risky. No per-platform audit trail. | REJECTED |
| Separate file `isolation.yaml` | Decouples config from platform manifest | One more file to read, diverges from current conventions | REJECTED |
| CLI flag on `dag_executor` | Runtime override | Not persistent; operator burden every invocation | REJECTED |
| **Opt-in field in platform.yaml (CHOSEN)** | Per-platform, declarative, versioned, matches existing pattern | Requires `platform.yaml` parse logic in `ensure_repo.py` | ACCEPTED |

**Reference**: decisions.md #1, pitch.md §Suggested Approach 1a.

---

## R2. Queue representation: new status enum vs separate table?

**Decision**: Add `queued` as a new value in the existing `epics.status` CHECK constraint. No new table.

**Rationale**:
- Queue depth is small (2–3 per platform per pitch §Apetite)
- All other epic statuses live in the same column (`proposed`, `drafted`, `in_progress`, `shipped`, `blocked`, `cancelled`) — orthogonal addition
- FIFO lookup is a single query (`WHERE status='queued' ORDER BY status_transitioned_at LIMIT 1`), no join needed
- Matches migration 009 precedent (`drafted` was added the same way)

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Separate `epic_queue` table with FK to epics | Scales to millions of queued entries; supports priorities | Over-engineered for 2–3 depth; two sources of truth (table + epic status); extra FK complexity | REJECTED |
| Priority column on epics | Supports non-FIFO ordering | Nobody asked for priority ordering; violates YAGNI | REJECTED |
| **New enum value (CHOSEN)** | Minimal change; one query; matches migration 009 | No built-in priority (acceptable — FIFO is sufficient) | ACCEPTED |

**Reference**: decisions.md #2, #4, pitch.md §Captured Decisions row 2.

---

## R3. "Oldest" in FIFO — which timestamp?

**Decision**: Order by the time the epic most recently transitioned INTO `queued` status (tracked via a `status_transitioned_at` column if not already present, or by inserting a row in a `status_transitions` audit log).

**Rationale**:
- Matches operator intuition: "I queued A then B" → A runs first
- Re-queuing (drafted → queued → drafted → queued) resets ordering — this is intentional, re-queuing is an explicit act
- Avoids using `epics.created_at` (epic creation time is a stale signal — it could be months before queuing)

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| `epics.created_at` | Simple, always available | Stale; re-queuing doesn't reset | REJECTED |
| Dedicated `queued_at` column | Clear semantic | One more migration, requires backfill | REJECTED (overkill) |
| **Last status transition time (CHOSEN)** | Works with existing `updated_at` or a lightweight `status_transitions` log if present | Requires either an `updated_at` update on every status write, or a transitions table | ACCEPTED |

**Follow-up in data-model.md**: Verify whether `epics.updated_at` or a `status_transitions` table already exists; if not, use `epics.updated_at` updated atomically with each status write.

**Reference**: spec.md Clarifications Q3.

---

## R4. Promotion hook placement: sync in poll loop vs async worker?

**Decision**: Insert promotion logic synchronously inside the existing `easter.py::dag_scheduler` poll loop, immediately after `_running_epics.discard(epic_id)`. Git operations wrapped in `asyncio.to_thread()` to avoid blocking the event loop.

**Rationale**:
- easter is a single-process asyncio daemon (ADR-006); adding a separate worker violates the single-process invariant
- `_running_epics` is the authoritative "slot is free" signal — hooking the promotion right where the slot becomes free is the simplest possible placement
- Git operations (clone status, checkout, commit) are blocking I/O; `asyncio.to_thread` offloads to a thread pool without changing the daemon architecture. This pattern is already used in `dag_executor.py` (per CLAUDE.md Gotchas reference and ADR-006)

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Separate promotion worker (new thread or process) | Isolates failures | Violates single-process invariant; adds lock coordination complexity; harder to debug | REJECTED |
| Periodic cron-style scan | Simple | Adds latency (up to cron interval); still needs the running-slot check | REJECTED |
| `asyncio.create_task(promote...)` inside poll | Non-blocking | Unordered with respect to next poll; harder reasoning about concurrency | REJECTED |
| **Synchronous in poll loop, `asyncio.to_thread` for git (CHOSEN)** | Minimal change, maintains invariants, straightforward reasoning | Slightly slower poll tick when promoting (bounded by retry budget ≤10s) | ACCEPTED |

**Reference**: decisions.md #3, pitch.md §Captured Decisions row 3, ADR-006.

---

## R5. Git library: subprocess vs gitpython/pygit2?

**Decision**: Keep raw `subprocess` for all git operations.

**Rationale**:
- ADR-004 mandates stdlib only (+ pyyaml); gitpython/pygit2 would be new dependencies
- Operations needed are simple (`status --porcelain`, `fetch`, `checkout`, `checkout -b`, `commit`, `branch --list`)
- Existing codebase already uses `subprocess` for git (worktree.py, implement_remote.py, easter.py)
- No performance concern — operations are millisecond-scale, and the overall flow is bounded by the retry budget (≤10s)

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| gitpython | Pythonic API, typed returns | New dependency; heavy import time; violates ADR-004 | REJECTED |
| pygit2 | Fast, C-based | New dependency with C extension; build complexity; violates ADR-004 | REJECTED |
| **Raw subprocess (CHOSEN)** | Zero new deps, consistent with existing code | Manual parsing of `git status --porcelain` output | ACCEPTED |

**Reference**: decisions.md #8, pitch.md §Applicable Constraints, ADR-004, ADR-010.

---

## R6. Feature flag mechanism: env var vs config file vs DB?

**Decision**: Runtime env var `MADRUGA_QUEUE_PROMOTION` (default unset / "0" → disabled; "1" → enabled).

**Rationale**:
- Matches established precedent in CLAUDE.md: `MADRUGA_BARE_LITE`, `MADRUGA_KILL_IMPLEMENT_CONTEXT`, `MADRUGA_SCOPED_CONTEXT`, `MADRUGA_CACHE_ORDERED`
- Env var is process-local — no disk state to clean up, no DB write to roll back
- Operator can toggle with `systemctl --user set-environment` or by editing the systemd unit file and restarting
- Zero risk of the flag being mis-read at runtime: `os.environ.get("MADRUGA_QUEUE_PROMOTION", "0") == "1"` is atomic

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| DB flag row | Live-toggleable without daemon restart | Adds DB dependency on an operational control; harder to version | REJECTED |
| Config file in `.pipeline/` | Versionable | Changes require file write + daemon re-read | REJECTED |
| **Env var (CHOSEN)** | Matches precedent; process-local; atomic read | Requires daemon restart for toggle (acceptable: same as other flags) | ACCEPTED |

**Reference**: decisions.md #10, pitch.md §Captured Decisions row 10, CLAUDE.md §Gotchas.

---

## R7. Retry strategy: budget and backoff

**Decision**: 3 attempts total, exponential backoff 1s / 2s / 4s (≈7s cumulative, ≤10s including operation time). Backoff uses `asyncio.sleep` inside the `asyncio.to_thread` worker since git ops are already on a thread.

**Rationale**:
- Pitch decision #7 already specified this sequence (1s, 2s, 4s)
- 10s is the upper-bound SLA in spec (FR-011), giving operations ~2s headroom
- 3 attempts is the minimum that can distinguish "transient" from "permanent" (1 retry = coincidence; 2 retries = pattern; 3 retries = permanent)
- Operator feedback is fast (ntfy notification within 10s of failure)

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| 5 retries with longer backoff | More resilient to flakiness | Longer operator-facing delay for permanent failures | REJECTED (10s SLA) |
| No retry — fail fast | Simplest | Misses transient git lock / network blips | REJECTED |
| **3 retries, 1/2/4s backoff (CHOSEN)** | Matches pitch decision, fits SLA | None material | ACCEPTED |

**Reference**: decisions.md #7, spec.md FR-011, pitch.md §Captured Decisions row 7.

---

## R8. Dirty-tree guard: where to check?

**Decision**: Inside the new `_checkout_epic_branch()` helper in `ensure_repo.py`, check `git status --porcelain` on the clone path BEFORE any `git checkout` or `git checkout -b`. If output is non-empty, raise `DirtyTreeError` with the full porcelain output included in the message.

**Rationale**:
- Check must happen BEFORE any git state change — anything else risks partial state
- `git status --porcelain` is stable, machine-readable, byte-exact
- Error includes porcelain output so operator can see exactly which files are dirty
- Caller (`promote_queued_epic`) catches `DirtyTreeError` and transitions the epic to `blocked` with a notification

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Check in `promote_queued_epic` before calling helper | Separation of concerns | Duplicated check (helper already needs it for direct calls) | REJECTED |
| Check after `git fetch` | Ensures fetched state is clean | Still before checkout, but harder to reason about | REJECTED |
| **Check at top of `_checkout_epic_branch` (CHOSEN)** | Single source of truth; atomic with the rest of checkout logic | None material | ACCEPTED |

**Reference**: decisions.md #6, pitch.md §Captured Decisions row 6.

---

## R9. Cascade base resolution

**Decision**: `_get_cascade_base()` helper with the following logic:

```
def _get_cascade_base(repo_path, platform_name, base_branch):
    # 1. Find the most recently active epic branch in the clone
    #    (branches matching repo.epic_branch_prefix, sorted by committer date)
    # 2. If one exists AND is locally present AND has commits not yet on origin/base_branch:
    #    return that branch name (cascade from tip of prior epic)
    # 3. Else: return f"origin/{base_branch}" (fetch first, then branch from base)
```

**Rationale**:
- Covers both cases from pitch Resolved Gray Area #2 and clarification Q4: prior epic branch exists locally → cascade; prior branch cleaned up after merge → fallback to base
- Uses `git for-each-ref --sort=-committerdate refs/heads/<prefix>/*` to find the most recent epic branch
- Only cascades if the prior branch has diverged from base — if it's already merged and its commits are ancestors of base, use base directly

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Always cascade from base branch | Simple | Breaks pitch intent — queue N+1 should inherit N's changes | REJECTED |
| Track prior epic in DB (last promoted per platform) | Explicit | Extra state to maintain; git already knows | REJECTED |
| **Git for-each-ref + ancestry check (CHOSEN)** | Uses git as source of truth; handles both cascade and cleanup cases | Slightly complex logic | ACCEPTED |

**Reference**: decisions.md #5, pitch.md §Resolved Gray Areas #2, spec.md FR-005.

---

## R10. Artifact migration: `git checkout` from base vs cp?

**Decision**: Use `git checkout <base_branch> -- platforms/<platform>/epics/<NNN>/` to bring draft artifacts onto the new epic branch, followed by `git add` and `git commit` with a descriptive message.

**Rationale**:
- `git checkout <branch> -- <path>` is atomic and tracks the source branch's version precisely (resolved clarification Q5: base branch at moment of promotion is authoritative)
- No three-way merge, no conflict resolution
- Files land in the working tree AND the index; a single `git commit` captures them
- Commit message per decisions.md #5 / pitch §Resolved Gray Area #3: `feat: promote queued epic NNN (cascade from <prev_branch>)`

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| `cp` from worktree to new branch | Simple | Doesn't use git's index; breaks if files have uncommitted edits | REJECTED |
| `git merge <base_branch> -- path` | Explicit merge | Three-way merge semantics; possible conflicts; violates spec FR-015 "no three-way merge" | REJECTED |
| **`git checkout <base> -- path` + commit (CHOSEN)** | Atomic, clean, uses git's native mechanism | None material | ACCEPTED |

**Reference**: decisions.md #5, spec.md FR-015/FR-016, pitch.md §Resolved Gray Areas #3.

---

## R11. SQLite migration: rec-table vs ALTER?

**Decision**: Rec-table pattern (create new table, copy data, drop old, rename new), following migration `009_add_drafted_status.sql` exactly.

**Rationale**:
- SQLite does NOT support `ALTER TABLE ... ALTER COLUMN ... CHECK (...)` — rec-table is the only way to modify a CHECK constraint
- Migration 009 is the working precedent in this codebase — same pattern, same `PRAGMA foreign_keys = OFF` bracket, same index recreation
- Atomic per SQLite transaction semantics; WAL mode handles concurrent readers

**Alternatives considered**:

| Alternative | Pros | Cons | Verdict |
|-------------|------|------|---------|
| Drop CHECK, use app-level validation only | Simple SQL | Violates defense-in-depth; future contributors can insert invalid statuses | REJECTED |
| Separate status-validation table | Schema-independent | Over-engineered for a single enum value | REJECTED |
| **Rec-table (CHOSEN)** | Proven precedent, keeps DB integrity | Verbose SQL (~30 lines) | ACCEPTED |

**Reference**: decisions.md #2, pitch.md §Applicable Constraints.

---

## R12. Test strategy

**Decision**: Unit tests for every new function using `unittest.mock` for subprocess isolation, plus one integration test per phase using a real temp SQLite file (no DB mock for schema/CRUD).

**Rationale**:
- Constitution Principle VII (TDD): tests before implementation, Red-Green-Refactor cycle
- Mocking subprocess for unit tests keeps them fast and deterministic
- Real SQLite for schema tests because mocking SQLite behavior is a known anti-pattern (see epic 012 learnings in memory: "mock patches target source module")
- Integration test runs the full promotion flow against a real DB copy

**Test inventory** (to be expanded in `/speckit.tasks`):

| Test | Type | Phase |
|------|------|-------|
| `test_migration_017_idempotent` | Integration (temp DB) | P1 |
| `test_migration_017_preserves_existing_rows` | Integration | P1 |
| `test_epic_status_map_has_queued` | Unit | P2 |
| `test_compute_epic_status_queued_guard` | Unit | P2 |
| `test_get_next_queued_epic_fifo` | Integration | P2 |
| `test_platform_cli_queue_subcommand` | Unit (mock DB) | P3 |
| `test_platform_cli_dequeue_subcommand` | Unit | P3 |
| `test_promote_queued_epic_happy_path` | Integration (mock subprocess, real DB) | P3 |
| `test_promote_queued_epic_dirty_tree_blocked` | Integration | P3 |
| `test_promote_queued_epic_retry_exhaustion` | Integration | P3 |
| `test_promote_queued_epic_idempotent` | Integration | P3 |
| `test_get_repo_work_dir_branch_mode` | Unit (mock platform.yaml) | P4 |
| `test_get_repo_work_dir_worktree_mode_default` | Unit | P4 |
| `test_get_repo_work_dir_selfref_short_circuit` | Unit | P4 |
| `test_checkout_epic_branch_existing` | Integration (mock subprocess) | P4 |
| `test_checkout_epic_branch_cascade` | Integration | P4 |
| `test_checkout_epic_branch_dirty_guard` | Integration | P4 |
| `test_implement_remote_uses_get_repo_work_dir` | Unit | P5 |
| `test_easter_hook_noop_when_flag_off` | Unit (env var=0) | P6 |
| `test_easter_hook_fires_when_flag_on` | Integration | P6 |
| `test_easter_hook_failure_does_not_crash_poll_loop` | Integration | P6 |

**Reference**: Constitution Principle VII, feedback memory `feedback_epic012_flow_learnings.md`.

---

## R13. Logging strategy (Constitution Principle IX)

**Decision**: Use `structlog`-style structured logs in all new code, matching existing easter.py conventions. Key events and their levels:

| Event | Level | Fields |
|-------|-------|--------|
| `queue_command_invoked` | INFO | platform, epic_id, operator |
| `dequeue_command_invoked` | INFO | platform, epic_id, operator |
| `promotion_hook_triggered` | INFO | platform, freed_epic_id |
| `promotion_skipped_flag_off` | DEBUG | platform, queued_count |
| `promotion_skipped_no_queue` | DEBUG | platform |
| `promotion_attempt_started` | INFO | platform, queued_epic_id, attempt_number |
| `promotion_attempt_git_failure` | WARN | platform, queued_epic_id, attempt_number, stderr_preview |
| `promotion_dirty_tree_blocked` | ERROR | platform, queued_epic_id, porcelain_output |
| `promotion_permanent_failure` | ERROR | platform, queued_epic_id, reason, total_attempts |
| `promotion_success` | INFO | platform, queued_epic_id, branch_name, duration_ms |

**Rationale**: Matches existing easter.py / dag_executor.py logging style. Keys are machine-parseable. No unstructured text fields. Errors include enough context for post-mortem without needing git history.

**Reference**: Constitution Principle IX, existing easter.py conventions.

---

## R14. Assumption: easter poll cycle is short enough for 60s SLA

**Assumption** (not a decision — inherited from existing daemon behavior): the current easter poll loop cycle is short (typically well under 10 seconds). This is NOT verified in code during planning — it is an observable runtime property. The 60s SC-002/SC-007 SLA assumes this continues to hold.

**Verification plan**: During `/madruga:qa` (after implementation phases P1–P6 complete), measure actual poll cycle by reading `journalctl --user -u madruga-easter` timestamps and confirming consecutive `dag_scheduler` iterations are ≤ 10s apart. If the poll interval ever changes to be longer than 50s, the 60s SLA becomes marginal and the spec's SC-002 may need to be revised.

**Why this is deferred**: Changing the poll interval would be its own decision (out of scope for epic 024). This assumption exists to document the dependency without forcing a measurement task during planning.

**Reference**: spec.md SC-002, SC-007, clarification Q1.

---

## Summary of unknowns resolved

| Unknown (from Technical Context) | Resolution | Reference |
|----------------------------------|-----------|-----------|
| Which file format stores the isolation flag? | `platform.yaml` opt-in field | R1 |
| How is the queue persisted? | `epics.status='queued'` enum value | R2 |
| How is FIFO ordering determined? | Last transition-into-queued time | R3 |
| Where does the promotion hook live? | Synchronous in easter.py poll loop with `asyncio.to_thread` | R4 |
| Which git library? | subprocess (ADR-004) | R5 |
| How is the feature flag configured? | `MADRUGA_QUEUE_PROMOTION` env var | R6 |
| Retry strategy specifics? | 3 attempts, 1/2/4s backoff, ≤10s total | R7 |
| Dirty-tree guard location? | `_checkout_epic_branch()` helper, before any git state change | R8 |
| Cascade base resolution? | `git for-each-ref` + ancestry check, fallback to origin base branch | R9 |
| Artifact migration mechanism? | `git checkout <base> -- <path>` + commit | R10 |
| Migration pattern for CHECK constraint change? | Rec-table (matches 009) | R11 |
| Test strategy? | Unit + integration, real SQLite for schema, mock subprocess for git | R12 |
| Logging taxonomy? | Structured events, INFO for state changes, ERROR for failures | R13 |

**All NEEDS CLARIFICATION resolved. Phase 0 complete.**
