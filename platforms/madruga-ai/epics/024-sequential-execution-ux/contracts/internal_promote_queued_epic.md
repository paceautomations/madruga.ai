# Internal Contract: `promote_queued_epic()`

**Phase**: P3 (function definition) + P6 (called from easter hook)
**File**: `.specify/scripts/platform_cli.py` (or a new module `.specify/scripts/queue_promotion.py`)
**Type**: New public function
**Spec reference**: FR-009, FR-010, FR-011, FR-012, FR-013, FR-015, FR-016

## Purpose

Atomically promote the oldest queued epic for a platform from `queued` to `in_progress`:

1. Create the epic's branch in the platform's main clone (via `get_repo_work_dir`).
2. Copy the drafted artifacts from the base branch onto the new epic branch.
3. Commit the artifacts with a cascade message.
4. Update the DB: `epics.status='in_progress'`, `epics.branch_name=<new_branch>`, `epics.updated_at=now()`.

Called by:
- `easter.py::dag_scheduler` (P6, via `asyncio.to_thread`) when the running slot becomes free.
- Possibly by `platform_cli.py promote-now <platform>` as a manual escape hatch (optional, deferred to implementation phase if time permits).

## Preconditions

**Sync-context-only**: this function MUST be called from a synchronous Python context. The retry loop uses `time.sleep()` for backoff, which blocks the current thread. When invoked from the easter daemon (an asyncio process), the caller MUST wrap the call in `asyncio.to_thread(promote_queued_epic, platform_id)` so the blocking operations execute on a thread pool worker without blocking the event loop. Calling this function directly from an `async def` context without `to_thread` would stall the daemon during retries. (A2 from analyze-report.md.)

## Signature

```python
def promote_queued_epic(platform_id: str) -> PromotionResult:
    """
    Promote the oldest queued epic for a platform to in_progress.

    Args:
        platform_id: Platform name.

    Returns:
        PromotionResult dataclass:
          - status: Literal["promoted", "no_queue", "blocked_dirty_tree", "blocked_retry_exhausted"]
          - epic_id: Optional[str]  -- the epic that was promoted, if any
          - branch_name: Optional[str]
          - attempts: int           -- total attempts before success / failure
          - duration_ms: int
          - error_message: Optional[str]

    Does NOT raise. All failure modes are encoded in PromotionResult.status.
    """
```

## Algorithm

```python
@dataclass
class PromotionResult:
    status: str
    epic_id: Optional[str] = None
    branch_name: Optional[str] = None
    attempts: int = 0
    duration_ms: int = 0
    error_message: Optional[str] = None


def promote_queued_epic(platform_id: str) -> PromotionResult:
    t0 = time.monotonic()
    logger = structlog.get_logger(__name__).bind(platform=platform_id)

    # 1. Lookup next queued epic (read-only, no lock).
    with db_read_connection() as conn:
        next_epic = get_next_queued_epic(conn, platform_id)
    if next_epic is None:
        logger.debug("promotion_skipped_no_queue")
        return PromotionResult(status="no_queue")

    epic_id = next_epic["epic_id"]
    logger = logger.bind(epic_id=epic_id)
    logger.info("promotion_hook_triggered")

    # 2. Load binding for cascade / artifact migration.
    binding = _load_repo_binding(platform_id)
    base_branch = binding["base_branch"]
    branch_name = f"{binding['epic_branch_prefix']}{epic_id}"

    # 3. Retry loop: 3 attempts, 1/2/4s backoff, ≤10s total budget.
    delays = [0.0, 1.0, 2.0, 4.0]  # pre-first-attempt 0s; post-fail backoff 1/2/4s
    last_error = None
    for attempt in range(1, 4):
        if delays[attempt - 1] > 0:
            time.sleep(delays[attempt - 1])
        logger_a = logger.bind(attempt=attempt)
        logger_a.info("promotion_attempt_started")
        try:
            # 3a. Dirty-tree guard + branch creation + checkout.
            repo_path = get_repo_work_dir(platform_id, epic_id)

            # 3b. Bring draft artifacts from base branch into epic branch.
            epic_dir_rel = f"platforms/{platform_id}/epics/{epic_id}/"
            subprocess.run(
                ["git", "checkout", base_branch, "--", epic_dir_rel],
                cwd=str(repo_path), check=True
            )
            # 3c. Commit the artifact migration.
            commit_msg = f"feat: promote queued epic {epic_id} (cascade from {base_branch})"
            subprocess.run(
                ["git", "add", epic_dir_rel],
                cwd=str(repo_path), check=True
            )
            subprocess.run(
                ["git", "commit", "-m", commit_msg, "--allow-empty"],
                cwd=str(repo_path), check=True
            )

            # 3d. DB update: status → in_progress, branch_name set, updated_at bumped.
            with db_write_lock():
                with sqlite3.connect(DB_PATH, isolation_level=None) as conn:
                    conn.execute(
                        "UPDATE epics SET status='in_progress', branch_name=?, "
                        "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
                        "WHERE platform_id=? AND epic_id=? AND status='queued'",
                        (branch_name, platform_id, epic_id),
                    )
                    if conn.total_changes == 0:
                        # Someone else already transitioned this epic (idempotency).
                        logger_a.warn("promotion_race_detected_noop")
                        duration = int((time.monotonic() - t0) * 1000)
                        return PromotionResult(
                            status="promoted", epic_id=epic_id,
                            branch_name=branch_name, attempts=attempt,
                            duration_ms=duration,
                        )

            # Success.
            duration = int((time.monotonic() - t0) * 1000)
            logger_a.info("promotion_success", branch_name=branch_name, duration_ms=duration)
            return PromotionResult(
                status="promoted", epic_id=epic_id,
                branch_name=branch_name, attempts=attempt, duration_ms=duration,
            )

        except DirtyTreeError as e:
            logger_a.error("promotion_dirty_tree_blocked", porcelain=str(e))
            _mark_epic_blocked(platform_id, epic_id, f"Dirty tree: {e}")
            _notify(f"Epic {epic_id} promotion blocked: dirty tree in clone")
            duration = int((time.monotonic() - t0) * 1000)
            return PromotionResult(
                status="blocked_dirty_tree", epic_id=epic_id,
                attempts=attempt, duration_ms=duration, error_message=str(e),
            )

        except subprocess.CalledProcessError as e:
            last_error = e
            logger_a.warn(
                "promotion_attempt_git_failure",
                returncode=e.returncode,
                stderr_preview=(e.stderr or "")[:200],
            )
            # Loop continues to next attempt.

    # All attempts exhausted.
    logger.error("promotion_permanent_failure",
                 total_attempts=3, reason=str(last_error))
    _mark_epic_blocked(platform_id, epic_id, f"Retry exhausted: {last_error}")
    _notify(f"Epic {epic_id} promotion failed after 3 attempts")
    duration = int((time.monotonic() - t0) * 1000)
    return PromotionResult(
        status="blocked_retry_exhausted", epic_id=epic_id,
        attempts=3, duration_ms=duration, error_message=str(last_error),
    )
```

## Helper functions

- `get_next_queued_epic(conn, platform_id)` — new function in `db_pipeline.py` (P2). Signature: `(conn, platform_id: str) -> Optional[dict]`. Returns row dict or None.
- `_mark_epic_blocked(platform_id, epic_id, reason)` — writes `UPDATE epics SET status='blocked', updated_at=... WHERE ...`. Existing DB helpers.
- `_notify(message)` — calls the existing notification channel (ntfy or equivalent). Best-effort (doesn't raise on delivery failure).

## Idempotency

- The DB UPDATE includes `AND status='queued'` — if a concurrent caller already promoted the epic, `conn.total_changes == 0` and the function returns success (race detected, no-op). This preserves the sequential invariant.
- Artifact commit uses `--allow-empty` because if the draft directory is already present on the branch (e.g., rerun after a partial git failure), `git add` produces no staged changes and the commit would otherwise fail.

## Retry budget accounting

| Phase | Time budget |
|-------|-------------|
| First attempt (no pre-delay) | operation time |
| Backoff 1 | 1.0 s |
| Second attempt | operation time |
| Backoff 2 | 2.0 s |
| Third attempt | operation time |
| **Total budget** | **≤ 10 s** (1 + 2 + 4 = 7s sleep + ~3s operation headroom) |

Matches spec FR-011 ("≤10s total retry budget") and decisions.md #7.

## Non-goals

- Does NOT delete worktrees for platforms that previously used isolation=worktree. That cleanup is out of scope.
- Does NOT notify on every successful promotion — only on failures. Successful promotion is visible via `queue-list` and easter logs.
- Does NOT merge PRs — per decisions.md #9, merge stays human-gated.

## Test cases (P3)

| Test | Given | When | Then |
|------|-------|------|------|
| no queue | platform has 0 queued | promote | status=no_queue |
| happy path first attempt | clean tree, queued epic | promote | status=promoted, attempts=1, DB in_progress |
| happy path after retry | transient git failure on attempt 1, success on attempt 2 | promote | status=promoted, attempts=2 |
| retry exhaustion | all 3 attempts fail | promote | status=blocked_retry_exhausted, DB blocked, notification sent |
| dirty tree | uncommitted changes in clone | promote | status=blocked_dirty_tree, NO retry, DB blocked, notification |
| idempotent race | concurrent call already promoted | promote | status=promoted, total_changes=0 detected |
| budget respected | force 3 retries | promote | total duration ≤ 10s |
