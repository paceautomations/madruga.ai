# Tasks: Sequential Execution UX

**Input**: Design documents from `platforms/madruga-ai/epics/024-sequential-execution-ux/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: REQUIRED (TDD per Constitution Principle VII). Every implementation task is preceded by a failing-test task.

**Organization**: Tasks are grouped by the 6 additive implementation phases (P1–P6) defined in plan.md §Phase Layering, NOT by user story. Rationale: the feature is infrastructure that modifies files the pipeline itself executes; additive phase ordering matters MORE than per-story independence. User stories (US1–US4) map across phases because P1–P4 build the foundations and P5–P6 activate them. Each task is annotated with the user story(ies) it ultimately enables.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on in-flight tasks)
- **[Story]**: User story enabled by this task (US1, US2, US3, US4)
- Every task includes exact file paths
- Phase boundary = `make test` green gate. No task in phase N+1 starts before all tasks in phase N are committed and tests pass.

## Path Conventions

Single-project layout (madruga.ai monorepo):

- **Migrations**: `.specify/migrations/`
- **Scripts**: `.specify/scripts/`
- **Tests**: `.specify/scripts/tests/`
- **Platform configs**: `platforms/<name>/platform.yaml`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preconditions and safety rails BEFORE touching any production code.

**Gate**: All items complete. No test gate — these are environmental.

- [ ] T001 Backup `.pipeline/madruga.db` to `.pipeline/madruga.db.bak-pre-024` (Camada 1 — recovery if migration brickar). Command: `cp .pipeline/madruga.db .pipeline/madruga.db.bak-pre-024 && cp .pipeline/madruga.db-wal .pipeline/madruga.db-wal.bak-pre-024 2>/dev/null || true && cp .pipeline/madruga.db-shm .pipeline/madruga.db-shm.bak-pre-024 2>/dev/null || true`
- [ ] T002 Stop the easter daemon explicitly: `systemctl --user stop madruga-easter && systemctl --user status madruga-easter` (Camada 0 — must remain stopped until `/madruga:qa` green). Confirm output shows `inactive`.
- [ ] T003 Create safety branch `epic/madruga-ai/024-sequential-execution-ux` off `main` (after 004-router-mece is merged): `git checkout main && git pull && git checkout -b epic/madruga-ai/024-sequential-execution-ux`.
- [ ] T004 Create snapshot branch `epic/madruga-ai/024-sequential-execution-ux-backup` pointing at the same commit: `git branch epic/madruga-ai/024-sequential-execution-ux-backup` (rollback insurance).
- [ ] T005 [P] Verify `make test` is green on the fresh branch before any changes: `make test`. Must pass.
- [ ] T006 [P] Verify `make lint` is green on the fresh branch: `make lint`. Must pass.

---

## Phase 2: Foundational (Schema Change — P1)

**Purpose**: Extend the `epics.status` CHECK constraint to include `queued`. Purely additive; existing rows unchanged. Nothing in this phase writes `queued` yet.

**Enables**: US2, US3, US4 (all queue-related stories depend on the new status existing in the schema).

**Gate**: `make test` green after commit. Contract SQL applied cleanly to a temp DB.

### Tests (TDD — write first, verify red)

- [ ] T007 [P] [US2] Create `.specify/scripts/tests/test_migration_017.py` with failing test `test_migration_017_adds_queued_to_check_constraint`. Test creates a temp DB at pre-017 schema (copying the `epics` CREATE from `data-model.md` §1), applies `017_add_queued_status.sql`, asserts that `INSERT INTO epics ... VALUES (..., 'queued', ...)` succeeds (RED state: fails because migration doesn't exist yet).
- [ ] T008 [P] [US2] Add failing test `test_migration_017_preserves_existing_rows` in the same file: insert one epic per pre-existing status (6 statuses), run migration, assert all 6 rows still present and queryable.
- [ ] T009 [P] [US2] Add failing test `test_migration_017_rejects_invalid_status`: after migration, `INSERT INTO epics ... VALUES (..., 'gibberish', ...)` must raise `sqlite3.IntegrityError` (CHECK still enforced).
- [ ] T010 [P] [US2] Add failing test `test_migration_017_idempotent_user_version`: after first apply, `PRAGMA user_version` returns 17; simulated re-apply via `user_version` guard is a no-op.
- [ ] T011 [P] [US2] Add failing test `test_migration_017_preserves_indexes`: after migration, both `idx_epics_platform` and `idx_epics_status` exist (query `sqlite_master` WHERE type='index').

### Implementation

- [ ] T012 [US2] Create `.specify/migrations/017_add_queued_status.sql` with the exact content from [`contracts/db_migration_017.sql`](contracts/db_migration_017.sql). Includes BEGIN/COMMIT bracket, `PRAGMA foreign_keys = OFF/ON`, rec-table pattern, `PRAGMA user_version = 17`.
- [ ] T013 [US2] Locate the migration runner in `.specify/scripts/` (search for `user_version`, `apply_migration`, or similar). Add dispatch for migration 017. If runner auto-discovers files in `.specify/migrations/`, no code change needed beyond file placement.
- [ ] T014 [US2] Run `pytest .specify/scripts/tests/test_migration_017.py` — all 5 tests go from RED → GREEN.
- [ ] T015 Run `make test` — full suite must stay green (no regressions in other tests). Run `make lint`. Commit: `feat(024): migration 017 adds queued status to epics CHECK constraint`.

---

## Phase 3: db_pipeline.py — Additive (P2)

**Purpose**: Teach `db_pipeline.py` about the new `queued` status. All changes are additive to existing data structures (list entry, dict entry) plus one new function.

**Enables**: US2, US3 (queue lookup and status guard).

**Gate**: `make test` green. No existing tests should break — this phase only adds.

### Tests (TDD)

- [ ] T016 [P] [US2] In `.specify/scripts/tests/test_db_pipeline.py`, add failing test `test_epic_status_map_contains_queued`: import `_EPIC_STATUS_MAP` and assert `_EPIC_STATUS_MAP["queued"] == "queued"` (RED — key missing).
- [ ] T017 [P] [US2] Add failing test `test_compute_epic_status_queued_guard`: simulate a row with `current_status='queued'` and node completion metadata. Assert `compute_epic_status()` returns `("queued", None)` (guard prevents auto-promotion).
- [ ] T018 [P] [US2] Add failing test `test_get_next_queued_epic_returns_none_when_empty`: empty DB. Assert `get_next_queued_epic(conn, 'prosauai')` returns `None` (RED — function doesn't exist).
- [ ] T019 [P] [US2] Add failing test `test_get_next_queued_epic_returns_single_queued`: insert one queued epic. Assert the function returns the row as a dict with keys `epic_id, platform_id, title, branch_name, updated_at`.
- [ ] T020 [P] [US2] Add failing test `test_get_next_queued_epic_fifo_order`: insert 3 epics with staggered `updated_at` timestamps (oldest first). Assert the function returns the oldest one regardless of insertion order in the DB.
- [ ] T021 [P] [US2] Add failing test `test_get_next_queued_epic_scoped_by_platform`: insert queued epics in platforms A and B. Assert calling with `platform_id='A'` returns only A's epic, never B's.
- [ ] T022 [P] [US2] Add failing test `test_get_next_queued_epic_tiebreaker_epic_id`: two queued epics with identical `updated_at`. Assert the one with alphabetically smaller `epic_id` is returned.

### Implementation

- [ ] T023 [US2] In `.specify/scripts/db_pipeline.py`, add `"queued": "queued"` to `_EPIC_STATUS_MAP` dict (~line 30). Additive — no existing key modified.
- [ ] T024 [US2] In `.specify/scripts/db_pipeline.py`, update the `compute_epic_status()` guard at line 917 from `("blocked", "cancelled", "shipped", "drafted")` to `("blocked", "cancelled", "shipped", "drafted", "queued")`. One string added to a tuple.
- [ ] T025 [US2] In `.specify/scripts/db_pipeline.py`, add new function `get_next_queued_epic(conn: sqlite3.Connection, platform_id: str) -> Optional[dict]` per [`data-model.md`](data-model.md) §5 query. Returns `None` if no rows; returns a dict with `epic_id, platform_id, title, branch_name, updated_at` otherwise.
- [ ] T026 [US2] Audit every `UPDATE epics SET status = ...` statement in `db_pipeline.py`. Ensure each one also writes `updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')`. If any are missing, add the assignment. (data-model.md §2 flags this as a dependency.)
- [ ] T027 [US2] Run `pytest .specify/scripts/tests/test_db_pipeline.py` — all 7 new tests go GREEN.
- [ ] T028 Run `make test` (full suite must stay green). Run `make lint`. Commit: `feat(024): db_pipeline additive support for queued status (map + guard + get_next_queued_epic)`.

---

## Phase 4: platform_cli.py — New Subcommands + Promotion Helper (P3)

**Purpose**: Add CLI surface (`queue`, `dequeue`, `queue-list`) and the `promote_queued_epic()` helper function. No runtime hook consumes these yet.

**Enables**: US2 (queue surface), US3 (failure handling logic lives here), SC-008 (self-service queue command).

**Gate**: `make test` green. Manual smoke test of CLI subcommands.

### Tests (TDD)

- [ ] T029 [P] [US2] In `.specify/scripts/tests/test_platform_cli.py`, add failing test `test_queue_subcommand_drafted_to_queued`: mock DB fixture with a drafted epic. Invoke `queue prosauai 004-foo`. Assert status = `queued`, exit 0, FIFO position = 1.
- [ ] T030 [P] [US2] Add failing test `test_queue_subcommand_rejects_non_drafted`: epic in `in_progress`. Invoke `queue`. Assert exit 3, status unchanged.
- [ ] T031 [P] [US2] Add failing test `test_queue_subcommand_rejects_unknown_epic`: no such epic. Invoke `queue`. Assert exit 2.
- [ ] T032 [P] [US2] Add failing test `test_queue_subcommand_rejects_unknown_platform`. Assert exit 2.
- [ ] T033 [P] [US2] Add failing test `test_dequeue_subcommand_queued_to_drafted`: queued epic. Invoke `dequeue`. Assert status=`drafted`, exit 0.
- [ ] T034 [P] [US2] Add failing test `test_dequeue_preserves_artifact_files_on_disk`: create a fake pitch.md file. Invoke `dequeue`. Assert pitch.md still exists byte-for-byte.
- [ ] T035 [P] [US2] Add failing test `test_queue_list_empty_platform`: no queued epics. Invoke `queue-list`. Assert output contains "No epics queued", exit 0.
- [ ] T036 [P] [US2] Add failing test `test_queue_list_fifo_order`: 3 queued epics with staggered timestamps. Invoke `queue-list`. Assert output rows appear in FIFO order (oldest first, position 1, 2, 3).
- [ ] T037 [P] [US2] Add failing test `test_queue_list_json_output`: Invoke `queue-list --json`. Assert JSON valid, `count` matches, `queue` array in FIFO order.
- [ ] T038 [P] [US3] In a new file `.specify/scripts/tests/test_promote_queued_epic.py`, add failing test `test_promote_no_queue_returns_no_queue`: empty DB. Assert `PromotionResult(status='no_queue')`.
- [ ] T039 [P] [US3] Add failing test `test_promote_happy_path_first_attempt`: mock subprocess to succeed all git calls. Clean temp DB with one queued epic. Assert `PromotionResult(status='promoted', attempts=1)`, DB status now `in_progress`, `branch_name` set. **Additionally assert the exact subprocess call order** (M3): (1) git status --porcelain, (2) git branch --list, (3) git fetch origin, (4) git for-each-ref, (5) git rev-list --count (ancestry check), (6) git checkout -b <new> <base>, (7) git checkout <base_branch> -- platforms/<platform>/epics/<epic>/, (8) git add <epic_dir>, (9) git commit -m. **Also assert the commit message matches the regex** `^feat: promote queued epic [0-9]{3}-[a-z0-9-]+ \(cascade from .+\)$` (M2 — enforces FR-016).
- [ ] T040 [P] [US3] Add failing test `test_promote_retry_on_transient_failure`: mock subprocess to fail attempt 1 with `CalledProcessError`, succeed attempt 2. Assert `PromotionResult(status='promoted', attempts=2)`.
- [ ] T041 [P] [US3] Add failing test `test_promote_retry_exhaustion_marks_blocked`: mock subprocess to fail all 3 attempts. Assert `PromotionResult(status='blocked_retry_exhausted', attempts=3)`, DB status `blocked`, notification stub was called. **Additionally assert (M1 — enforces FR-013) that `branch_name IS NULL` in the `epics` row after failure** — proves no half-written branch metadata. Also assert `file_path` is NULL or unchanged.
- [ ] T042 [P] [US3] Add failing test `test_promote_dirty_tree_blocks_immediately_no_retry`: mock `_checkout_epic_branch` to raise `DirtyTreeError`. Assert `PromotionResult(status='blocked_dirty_tree', attempts=1)`, DB `blocked`, notification sent, **and no retry attempted** (DirtyTreeError is not in the retryable set).
- [ ] T043 [P] [US3] Add failing test `test_promote_idempotent_race`: two concurrent calls to `promote_queued_epic` for the same platform. Second call should observe `conn.total_changes == 0` (row already promoted) and return `PromotionResult(status='promoted')` with `attempts=1` (or `race_detected`). Neither call should raise.
- [ ] T044 [P] [US3] Add failing test `test_promote_retry_budget_within_10s`: use `time.monotonic()` before/after. Force 3 retries with zero-delay mock sleep. Assert total wall time ≤ 10s (SLA per FR-011).
- [ ] T044a [P] [US3] Add failing test `test_promote_logs_success_event` (M4 — enforces Constitution Principle IX + research.md §R13): happy-path promotion. Capture structlog output. Assert `promotion_success` event was emitted with keys `platform, epic_id, branch_name, duration_ms` at INFO level.
- [ ] T044b [P] [US3] Add failing test `test_promote_logs_failure_events` (M4): force dirty-tree AND retry-exhaustion scenarios separately. Assert `promotion_dirty_tree_blocked` (ERROR, keys `platform, epic_id, porcelain`) and `promotion_permanent_failure` (ERROR, keys `platform, epic_id, reason, total_attempts`) events are emitted in the respective scenarios.

### Implementation

- [ ] T045 [US2] In `.specify/scripts/platform_cli.py`, add the argparse subcommand `queue` per [`contracts/cli_platform_queue.md`](contracts/cli_platform_queue.md). Implementation: validate platform, validate epic in drafted, UPDATE with db_write_lock, log event, print confirmation.
- [ ] T046 [US2] Add subcommand `dequeue` per [`contracts/cli_platform_dequeue.md`](contracts/cli_platform_dequeue.md).
- [ ] T047 [US2] Add subcommand `queue-list` per [`contracts/cli_platform_queue_list.md`](contracts/cli_platform_queue_list.md). Supports `--json` flag.
- [ ] T048 [US3] In `.specify/scripts/platform_cli.py` (or new module `.specify/scripts/queue_promotion.py` if it grows big), implement `promote_queued_epic(platform_id: str) -> PromotionResult` exactly per [`contracts/internal_promote_queued_epic.md`](contracts/internal_promote_queued_epic.md). Includes `@dataclass PromotionResult`, retry loop with backoff 1/2/4s, dirty-tree fast-fail, idempotency via `AND status='queued'` in UPDATE, and structured logging.
- [ ] T049 [US3] Add helper `_mark_epic_blocked(platform_id, epic_id, reason)` — writes `UPDATE epics SET status='blocked', updated_at=..., file_path=<reason?>` (or use existing helper if one already exists in db_pipeline.py — grep first).
- [ ] T050 [US3] Add helper `_notify(message)` wrapper around the existing notification channel. Must not raise on delivery failure — catch and log.
- [ ] T051 Run `pytest .specify/scripts/tests/test_platform_cli.py .specify/scripts/tests/test_promote_queued_epic.py` — all 16 new tests go GREEN.
- [ ] T052 Manual smoke test of the CLI: `python3 .specify/scripts/platform_cli.py queue prosauai <some-drafted-epic>`; verify success. Then `dequeue` and verify. Then `queue-list` and verify empty. (DB writes will be cleaned up before commit.)
- [ ] T053 Run `make test`. Run `make lint`. Commit: `feat(024): platform_cli queue/dequeue/queue-list subcommands + promote_queued_epic helper`.

---

## Phase 5: ensure_repo.py — New Functions (P4)

**Purpose**: Add `get_repo_work_dir()` and its helper `_checkout_epic_branch()` + `_get_cascade_base()` to `ensure_repo.py`. These functions are NOT called by anything yet — pure dead code until P5.

**Enables**: US1 (branch visibility in main clone).

**Gate**: `make test` green. Dead-code is acceptable at this gate.

### Tests (TDD)

- [ ] T054 [P] [US1] In `.specify/scripts/tests/test_ensure_repo.py`, add failing test `test_get_repo_work_dir_selfref_short_circuits_to_repo_root`: mock `_is_self_ref` to return True. Assert function returns `REPO_ROOT`, no git ops invoked.
- [ ] T055 [P] [US1] Add failing test `test_get_repo_work_dir_worktree_mode_default`: platform.yaml without `isolation` key. Assert function delegates to `create_worktree()`.
- [ ] T056 [P] [US1] Add failing test `test_get_repo_work_dir_worktree_mode_explicit`: platform.yaml with `isolation: worktree`. Same delegation.
- [ ] T057 [P] [US1] Add failing test `test_get_repo_work_dir_branch_mode_delegates_to_checkout`: platform.yaml with `isolation: branch`. Mock `ensure_repo()` to return a temp path. Mock `_checkout_epic_branch` to record its call. Assert function calls `_checkout_epic_branch` with the right args and returns the repo path.
- [ ] T058 [P] [US1] Add failing test `test_get_repo_work_dir_unknown_isolation_raises_valueerror`: `isolation: foo`. Assert `ValueError`.
- [ ] T059 [P] [US1] Add failing test `test_checkout_epic_branch_dirty_tree_raises`: mock `git status --porcelain` to return non-empty output. Assert `DirtyTreeError` raised before any `git checkout` call.
- [ ] T060 [P] [US1] Add failing test `test_checkout_epic_branch_existing_local_branch`: mock `git branch --list` to return the branch name. Assert function calls `git checkout <branch>` and NOT `git checkout -b`.
- [ ] T061 [P] [US1] Add failing test `test_checkout_epic_branch_new_branch_cascade_from_prior`: mock `git branch --list` to return empty, mock `git for-each-ref` to return a prior epic branch with commits ahead of base. Assert `git checkout -b <new-branch> <prior-branch>` is called.
- [ ] T062 [P] [US1] Add failing test `test_checkout_epic_branch_new_branch_fallback_to_base`: mock `git branch --list` empty, mock `git for-each-ref` to return empty. Assert `git checkout -b <new-branch> origin/develop` (or configured base).
- [ ] T063 [P] [US1] Add failing test `test_checkout_epic_branch_fallback_when_prior_branch_merged`: mock prior branch exists BUT `git rev-list --count base..prior` returns 0 (all ancestors already in base). Assert fallback to base.

### Implementation

- [ ] T064 [US1] In `.specify/scripts/ensure_repo.py`, add new exception class `class DirtyTreeError(Exception): pass` at the top of the file.
- [ ] T065 [US1] Add helper `_get_cascade_base(repo_path, binding)` per [`contracts/internal_checkout_epic_branch.md`](contracts/internal_checkout_epic_branch.md) §Algorithm. Uses `git for-each-ref --sort=-committerdate` + `git rev-list --count` for ancestry check.
- [ ] T066 [US1] Add helper `_checkout_epic_branch(repo_path, platform_name, epic_slug, binding)` per the contract: dirty-tree guard first, then local branch detection, then new-branch cascade.
- [ ] T067 [US1] Add public function `get_repo_work_dir(platform_name, epic_slug) -> Path` per [`contracts/internal_get_repo_work_dir.md`](contracts/internal_get_repo_work_dir.md). Self-ref short-circuit first; isolation dispatch second.
- [ ] T068 [US1] Run `pytest .specify/scripts/tests/test_ensure_repo.py` — all 10 new tests GREEN.
- [ ] T069 Run `make test`. Run `make lint`. Commit: `feat(024): ensure_repo.get_repo_work_dir + _checkout_epic_branch helpers (dead code until P5)`.

---

## Phase 6: implement_remote.py — Call-Site Swap (P5)

**Purpose**: Replace the single call to `create_worktree()` in `implement_remote.py` with `get_repo_work_dir()`. **This is the first phase that changes runtime behavior** — but only for platforms explicitly opted into `isolation: branch`. Default (`worktree`) behavior preserved exactly.

**Enables**: US1 becomes live for opted-in platforms.

**Gate**: `make test` green + manual verification that self-ref + default-worktree platforms still work.

### Tests (TDD)

- [ ] T070 [P] [US1] In `.specify/scripts/tests/test_implement_remote.py`, add failing test `test_implement_remote_uses_get_repo_work_dir`: mock `get_repo_work_dir` with a known return value. Invoke whatever top-level function in `implement_remote.py` orchestrates work_dir resolution. Assert `cwd` passed to subprocess matches the mocked path.
- [ ] T071 [P] [US1] Add regression test `test_implement_remote_default_worktree_mode_preserved`: use a platform.yaml without `isolation` key. Invoke orchestration. Assert the resulting path matches the pre-epic behavior (worktree path). This is the backwards-compat safety net.
- [ ] T072 [P] [US1] Add test `test_implement_remote_selfref_still_uses_repo_root`: madruga-ai-like fixture. Assert path = REPO_ROOT (no worktree, no branch checkout).

### Implementation

- [ ] T073 [US1] In `.specify/scripts/implement_remote.py`, locate the current line that calls `create_worktree(platform_name, epic_slug)` (pitch.md mentions line ~158). Replace the call with `from ensure_repo import get_repo_work_dir; work_dir = get_repo_work_dir(platform_name, epic_slug)`.
- [ ] T074 [US1] Verify `create_worktree` is no longer imported directly in `implement_remote.py` (it is still imported by `ensure_repo.py` for the worktree isolation path). Keep the `worktree.py` module intact — it is NOT dead code, it is the default.
- [ ] T075 [US1] Run `pytest .specify/scripts/tests/test_implement_remote.py` — 3 new tests GREEN.
- [ ] T076 [US1] Run the full test suite `make test`. Pay special attention to any existing integration test that exercises the implement flow for external platforms — it should continue to pass with the default worktree path.
- [ ] T077 Run `make lint`. Commit: `feat(024): implement_remote uses get_repo_work_dir (call-site swap, worktree default preserved)`.

---

## Phase 7: easter.py — Promotion Hook (P6 — LAST)

**Purpose**: Insert the auto-promotion hook in the easter daemon's `dag_scheduler` loop. Gated by `MADRUGA_QUEUE_PROMOTION` env var (default OFF). Even after commit, runtime behavior is unchanged unless the operator explicitly enables the flag.

**Enables**: US2 fully activated (auto-promotion happens), US3 (failure handling fires through the hook), US4 (kill-switch mechanism).

**Gate**: `make test` green. **Daemon import check**: `python3 -c "import sys; sys.path.insert(0, '.specify/scripts'); import easter"` must succeed cleanly BEFORE any systemd restart. Per Camada 2, this is the highest-risk phase.

### Tests (TDD)

- [ ] T078 [P] [US4] In `.specify/scripts/tests/test_easter.py`, add failing test `test_promotion_hook_noop_when_flag_unset`: `os.environ.pop('MADRUGA_QUEUE_PROMOTION', None)`. Simulate `dag_scheduler` iteration where an epic just shipped. Assert `promote_queued_epic` was NOT called.
- [ ] T079 [P] [US4] Add failing test `test_promotion_hook_noop_when_flag_zero`: `os.environ['MADRUGA_QUEUE_PROMOTION'] = '0'`. Same assertion.
- [ ] T080 [P] [US2] Add failing test `test_promotion_hook_fires_when_flag_one`: `os.environ['MADRUGA_QUEUE_PROMOTION'] = '1'`. Mock `promote_queued_epic` to return `PromotionResult(status='promoted', epic_id='005-next', ...)`. Simulate `dag_scheduler` iteration. Assert `promote_queued_epic('prosauai')` was called exactly once.
- [ ] T081 [P] [US3] Add failing test `test_promotion_hook_swallows_exceptions_and_continues_poll_loop`: mock `promote_queued_epic` to raise `KeyError`. Assert the `dag_scheduler` iteration completes without raising, logs the exception at ERROR level, and continues processing other platforms.
- [ ] T082 [P] [US2] Add failing test `test_promotion_hook_skipped_when_platform_has_other_running_epic`: mock `_platform_has_running_epic` to return True. Assert `promote_queued_epic` is NOT called (sequential invariant preserved).
- [ ] T083 [P] [US4] Add failing test `test_promotion_hook_uses_asyncio_to_thread`: verify via a call recorder that the hook wraps `promote_queued_epic` in `asyncio.to_thread` (does not block the event loop).
- [ ] T084 [P] [US4] Add failing test `test_promotion_hook_env_var_frozen_in_process`: set env var to '1', run hook, then set to '0' from within same process without restart. Assert the hook STILL reads '1' on subsequent calls if os.environ dict is updated (or assert the expected caching behavior — matches quickstart.md §Step 7 documentation).

### Implementation

- [ ] T085 [US4] In `.specify/scripts/easter.py`, locate `dag_scheduler()` and the line `_running_epics.discard(epic_id)`. **Read the surrounding code carefully** — understand the async context and variable names before editing.
- [ ] T086 [US4] Immediately after `_running_epics.discard(epic_id)`, add the hook block per [`contracts/internal_easter_promotion_hook.md`](contracts/internal_easter_promotion_hook.md) §Insertion point. Includes env var check, `_platform_has_running_epic` defensive call, `asyncio.to_thread(promote_queued_epic, epic_platform_id)`, structured logging, and bare-`except Exception` safety net.
- [ ] T087 [US4] Add helper async function `_platform_has_running_epic(platform_id: str) -> bool` per the contract — DB query wrapped in `asyncio.to_thread`.
- [ ] T088 [US4] Add `from platform_cli import promote_queued_epic` as a LAZY import inside the hook (not at module top) — avoids import-order issues and keeps the existing `easter.py` import graph untouched for the no-op path.
- [ ] T089 [US4] Python-syntax check: `python3 -c "import ast; ast.parse(open('.specify/scripts/easter.py').read())"`. Must return 0.
- [ ] T090 [US4] Import check: `python3 -c "import sys; sys.path.insert(0, '.specify/scripts'); import easter; print('easter imports clean')"`. Must print the success line.
- [ ] T091 [US4] Run `pytest .specify/scripts/tests/test_easter.py` — 7 new tests GREEN.
- [ ] T092 [US4] Run `make test` full suite. Run `make lint`.
- [ ] T093 **DO NOT RESTART easter.** Commit: `feat(024): easter auto-promotion hook gated by MADRUGA_QUEUE_PROMOTION flag (default off)`. Flag remains off — daemon will remain stopped until `/madruga:qa` verifies the full integration path in a later step.

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Documentation, observability polish, minor cleanups. Runs after all 6 functional phases.

- [ ] T094 [P] Update `CLAUDE.md` §Gotchas to document `MADRUGA_QUEUE_PROMOTION` env var alongside the existing bare-lite kill-switches. Add one bullet:  
  `- MADRUGA_QUEUE_PROMOTION=1` → enables auto-promotion of queued epics in easter.py hook. Default **off**. Must restart daemon to toggle.
- [ ] T095 [P] Update `.claude/knowledge/pipeline-dag-knowledge.md` §8 to mention the new `queued` status alongside `drafted`, and note that auto-promotion is gated by the flag.
- [ ] T096 [P] [US1] Update the target platform's `platform.yaml` (e.g., `platforms/prosauai/platform.yaml`) to add `isolation: branch` under the `repo:` block, enabling US1 for that platform. **This is a CONFIG change that MUST be committed AS ITS OWN STANDALONE COMMIT**, separate from P1–P6 code commits AND separate from other Polish tasks. Rationale (M6): the rollout cutover must be atomic and obvious in `git log` so a rollback can revert just the opt-in without touching code. Sequence: (1) ensure Phase 7 `make test` is green and committed, (2) edit `platforms/prosauai/platform.yaml` adding `isolation: branch`, (3) run `make test` to verify nothing broke, (4) commit ONLY this file with message `chore(024): opt prosauai into branch isolation mode`.
- [ ] T097 [P] Run the end-to-end smoke walkthrough from [`quickstart.md`](quickstart.md) — Steps 0 through 7. This is the full integration test; some of these steps require easter to be running, so this task is marked [P] with its own prerequisite: must run AFTER `/madruga:qa` reviews the full branch.
- [ ] T098 [P] [US3] Verify observability: tail `journalctl --user -u madruga-easter -f` during the smoke test and confirm all expected `structlog` events are emitted (event names per research.md §R13).
- [ ] T099 Grep for stale TODO / FIXME markers introduced during the epic: `grep -rn 'TODO\|FIXME' .specify/scripts/db_pipeline.py .specify/scripts/ensure_repo.py .specify/scripts/platform_cli.py .specify/scripts/easter.py .specify/scripts/implement_remote.py .specify/migrations/017_*.sql`. Address or explicitly justify each one.
- [ ] T100 Final `make test && make lint` on the epic branch before handing off to `/madruga:judge`.

---

## Dependencies

### Phase-level dependencies (STRICT — no parallelism across phases)

```text
Phase 1 (Setup)
   ↓
Phase 2 (Migration 017 — P1)
   ↓
Phase 3 (db_pipeline additive — P2)
   ↓
Phase 4 (platform_cli + promote_queued_epic — P3)
   ↓
Phase 5 (ensure_repo new functions — P4)
   ↓
Phase 6 (implement_remote call-site swap — P5)
   ↓
Phase 7 (easter.py hook — P6 — LAST)
   ↓
Phase 8 (Polish)
```

**Hard rule per Camada 2**: No task in Phase N+1 may start until all tasks in Phase N are committed and `make test` is green on the head commit.

### Intra-phase parallelism

Within a single phase, test tasks [P] can run in parallel (different test functions in the same file, or different test files). Implementation tasks mostly cannot — they edit the same file.

**Example parallelism in Phase 3** (db_pipeline):

```bash
# All 7 test-writing tasks can be done in one sitting (same file, but independent functions):
# T016 T017 T018 T019 T020 T021 T022 — write failing tests
# Then implementation:
# T023 T024 T025 T026 — all edit db_pipeline.py, SEQUENTIAL
# Then:
# T027 T028 — verify GREEN + lint + commit
```

### User story dependencies

- **US1** (isolation visibility): depends on P4 + P5 (Phases 5 + 6).
- **US2** (queue + auto-promotion): depends on P1 + P2 + P3 + P6 (Phases 2, 3, 4, 7).
- **US3** (failure handling): depends on P3 + P6 (Phases 4, 7) — the handling code is in `promote_queued_epic`, invoked by the hook.
- **US4** (kill-switch): depends on P6 (Phase 7) — the flag is read in the hook.

Stories are NOT independently shippable in this epic because P6 is load-bearing for US2/US3/US4 and must be last. This is accepted per plan.md §Constitution Check Principle IV override.

---

## Implementation Strategy

### Option A — Single sitting (recommended for low-distraction day)

Run Phase 1 → Phase 7 → Phase 8 in one continuous session with `make test` between each phase. Total estimated effort: 1–2 days of focused work.

### Option B — Phase-by-phase over a week

Each phase is its own commit + PR-ready state. If interruptions are likely, stop at any phase boundary and the pipeline remains fully functional (subject to the additive guarantee).

### MVP scope (first shipped increment)

Technically, P1 alone is a shippable increment (migration applied, nothing else changes). But it delivers no user value without P6. The minimum user-visible MVP is **P1 + P2 + P3 + P6** (US2 queue mechanic) — skip P4/P5 (isolation mode) for later. However the plan does NOT recommend this shortcut because:

1. P4/P5 are dead code / call-site swaps, essentially free
2. Shipping all 6 phases in one epic gives atomic rollback via single PR revert
3. US1 (isolation visibility) is half the point of the epic per the pitch

**Recommendation**: Ship all 6 phases together.

---

## Independent test criteria by user story

- **US1**: Open `~/repos/paceautomations/prosauai` in an editor; current branch is `epic/prosauai/<whatever-is-running>`. Pass iff it is NOT a worktree path and NOT `develop`.
- **US2**: `platform_cli.py queue prosauai 004-foo` succeeds; after the currently-running epic finishes, `004-foo` transitions to `in_progress` within 60s without manual intervention (requires `MADRUGA_QUEUE_PROMOTION=1`).
- **US3**: With a dirty tree intentionally created, trigger a promotion; epic transitions to `blocked` with a visible notification and no files modified.
- **US4**: `systemctl --user unset-environment MADRUGA_QUEUE_PROMOTION && systemctl --user restart madruga-easter` completes in < 30s; subsequent epic completions do NOT trigger promotion.

---

## Task count summary

| Phase | Tasks | Of which tests | Of which implementation | Of which gates |
|-------|-------|----------------|-------------------------|----------------|
| 1. Setup | 6 | 0 | 0 | 6 (env prep) |
| 2. Migration 017 | 9 | 5 | 2 | 2 (gate) |
| 3. db_pipeline | 13 | 7 | 4 | 2 (gate) |
| 4. platform_cli | 27 | 18 | 6 | 3 (gate) |
| 5. ensure_repo | 16 | 10 | 4 | 2 (gate) |
| 6. implement_remote | 8 | 3 | 2 | 3 (gate) |
| 7. easter.py | 16 | 7 | 4 | 5 (gate) |
| 8. Polish | 7 | 0 | 0 | 7 |
| **TOTAL** | **102** | **50** | **22** | **30** |

**Tests-to-implementation ratio**: ≈2.3 : 1 — consistent with TDD Principle VII and the high risk of this epic. (Count includes T044a, T044b added during `/speckit.analyze` fix pass.)

---

## Format validation

All 102 tasks follow the format `- [ ] T### [P?] [US?] Description with file path`. Checkbox ✓, sequential IDs T001–T100 + T044a + T044b ✓, parallel markers where applicable ✓, story labels in implementation phases ✓, exact file paths in every actionable task ✓. (T044a and T044b inserted during `/speckit.analyze` fix pass to close M4 logging coverage gap — IDs chosen to avoid renumbering existing tasks.)

**Ready for**: `/speckit.analyze` (consistency check across spec/plan/tasks).
