"""queue_promotion.py — Epic queue auto-promotion logic (epic 024).

Handles the transition of a queued epic to in_progress:
branch creation, artifact migration, DB status update, retry with backoff.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from config import REPO_ROOT
from db_core import _now, get_conn

log = logging.getLogger(__name__)


@dataclass
class PromotionResult:
    """Outcome of a promote_queued_epic() call."""

    status: str  # promoted | no_queue | blocked_dirty_tree | blocked_retry_exhausted
    epic_id: str | None = None
    branch_name: str | None = None
    attempts: int = 0
    duration_ms: int = 0
    error_message: str | None = None


class DirtyTreeError(Exception):
    """Raised when a repo working tree has uncommitted changes."""


def _checkout_epic_branch(
    repo_path: Path,
    epic_slug: str,
    binding: dict,
) -> str:
    """Check out the epic branch in the clone. Returns the branch name.

    Raises DirtyTreeError if working tree has uncommitted changes.
    Raises subprocess.CalledProcessError on git failure.
    """
    branch_name = f"{binding['epic_branch_prefix']}{epic_slug}"

    # 1. Dirty-tree guard
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=True,
    )
    if status.stdout.strip():
        raise DirtyTreeError(
            f"{repo_path} has uncommitted changes. "
            f"Commit or stash before running epic {epic_slug}.\n"
            f"Dirty files:\n{status.stdout}"
        )

    # 2. Branch already exists locally → just checkout
    local = subprocess.run(
        ["git", "branch", "--list", branch_name],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if local:
        subprocess.run(["git", "checkout", branch_name], cwd=str(repo_path), check=True)
        return branch_name

    # 3. New branch — fetch first
    subprocess.run(
        ["git", "fetch", "origin", binding["base_branch"]],
        cwd=str(repo_path),
        check=True,
    )

    # 4. Determine cascade base
    cascade_base = _get_cascade_base(repo_path, binding)

    # 5. Create new branch from cascade base
    subprocess.run(
        ["git", "checkout", "-b", branch_name, cascade_base],
        cwd=str(repo_path),
        check=True,
    )
    return branch_name


def _get_cascade_base(repo_path: Path, binding: dict) -> str:
    """Return the ref to branch from: prior epic tip or origin/base_branch."""
    base_ref = f"origin/{binding['base_branch']}"
    prefix = binding["epic_branch_prefix"].rstrip("/")

    result = subprocess.run(
        [
            "git",
            "for-each-ref",
            "--sort=-committerdate",
            f"refs/heads/{prefix}/*",
            "--format=%(refname:short)",
        ],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=True,
    )
    for candidate in result.stdout.splitlines():
        candidate = candidate.strip()
        if not candidate:
            continue
        ahead = subprocess.run(
            ["git", "rev-list", "--count", f"{base_ref}..{candidate}"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
        )
        if int(ahead.stdout.strip()) > 0:
            return candidate
    return base_ref


def _notify(message: str) -> None:
    """Best-effort notification via existing ntfy channel."""
    try:
        from ntfy import ntfy_alert, get_ntfy_topic

        topic = get_ntfy_topic()
        if topic:
            ntfy_alert(topic, message)
    except Exception:
        log.debug("notify_delivery_failed", exc_info=True)


def promote_queued_epic(platform_id: str) -> PromotionResult:
    """Promote the oldest queued epic for a platform to in_progress.

    MUST be called from a sync context. Easter hook uses asyncio.to_thread().
    """
    t0 = time.monotonic()

    # 1. Lookup next queued epic
    with get_conn() as conn:
        from db_pipeline import get_next_queued_epic

        next_epic = get_next_queued_epic(conn, platform_id)

    if next_epic is None:
        log.debug("promotion_skipped_no_queue", extra={"platform": platform_id})
        return PromotionResult(status="no_queue")

    epic_id = next_epic["epic_id"]
    log.info(
        "promotion_hook_triggered",
        extra={"platform": platform_id, "epic_id": epic_id},
    )

    # 2. Load repo binding
    from ensure_repo import _load_repo_binding, ensure_repo

    binding = _load_repo_binding(platform_id)
    base_branch = binding["base_branch"]

    # 3. Resolve repo path
    from ensure_repo import _is_self_ref

    if _is_self_ref(binding["name"]):
        repo_path = REPO_ROOT
    else:
        repo_path = ensure_repo(platform_id)

    # 4. Retry loop: 3 attempts, 1/2/4s backoff
    delays = [0.0, 1.0, 2.0, 4.0]
    last_error: Exception | None = None

    for attempt in range(1, 4):
        if delays[attempt] > 0:
            time.sleep(delays[attempt])

        log.info(
            "promotion_attempt_started",
            extra={"platform": platform_id, "epic_id": epic_id, "attempt": attempt},
        )

        try:
            # 4a. Branch creation + dirty-tree guard
            branch_name = _checkout_epic_branch(repo_path, epic_id, binding)

            # 4b. Bring draft artifacts from base branch
            epic_dir_rel = f"platforms/{platform_id}/epics/{epic_id}/"
            subprocess.run(
                ["git", "checkout", base_branch, "--", epic_dir_rel],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
            )
            # 4c. Commit artifact migration
            subprocess.run(["git", "add", epic_dir_rel], cwd=str(repo_path), check=True)
            commit_msg = f"feat: promote queued epic {epic_id} (cascade from {base_branch})"
            subprocess.run(
                ["git", "commit", "-m", commit_msg, "--allow-empty"],
                cwd=str(repo_path),
                check=True,
            )

            # 4d. DB: queued → in_progress
            with get_conn() as conn:
                now = _now()
                changed = conn.execute(
                    "UPDATE epics SET status='in_progress', branch_name=?, "
                    "updated_at=? "
                    "WHERE platform_id=? AND epic_id=? AND status='queued'",
                    (branch_name, now, platform_id, epic_id),
                ).rowcount
                conn.commit()

                if changed == 0:
                    log.warning(
                        "promotion_race_detected_noop",
                        extra={"platform": platform_id, "epic_id": epic_id},
                    )

            duration = int((time.monotonic() - t0) * 1000)
            log.info(
                "promotion_success",
                extra={
                    "platform": platform_id,
                    "epic_id": epic_id,
                    "branch_name": branch_name,
                    "duration_ms": duration,
                },
            )
            return PromotionResult(
                status="promoted",
                epic_id=epic_id,
                branch_name=branch_name,
                attempts=attempt,
                duration_ms=duration,
            )

        except DirtyTreeError as e:
            log.error(
                "promotion_dirty_tree_blocked",
                extra={"platform": platform_id, "epic_id": epic_id, "porcelain": str(e)},
            )
            _mark_blocked(platform_id, epic_id, f"Dirty tree: {e}")
            _notify(f"Epic {epic_id} promotion blocked: dirty tree in clone")
            duration = int((time.monotonic() - t0) * 1000)
            return PromotionResult(
                status="blocked_dirty_tree",
                epic_id=epic_id,
                attempts=attempt,
                duration_ms=duration,
                error_message=str(e),
            )

        except subprocess.CalledProcessError as e:
            last_error = e
            log.warning(
                "promotion_attempt_git_failure",
                extra={
                    "platform": platform_id,
                    "epic_id": epic_id,
                    "attempt": attempt,
                    "returncode": e.returncode,
                    "stderr_preview": (e.stderr or "")[:200],
                },
            )

    # All attempts exhausted
    log.error(
        "promotion_permanent_failure",
        extra={
            "platform": platform_id,
            "epic_id": epic_id,
            "total_attempts": 3,
            "reason": str(last_error),
        },
    )
    _mark_blocked(platform_id, epic_id, f"Retry exhausted: {last_error}")
    _notify(f"Epic {epic_id} promotion failed after 3 attempts")
    duration = int((time.monotonic() - t0) * 1000)
    return PromotionResult(
        status="blocked_retry_exhausted",
        epic_id=epic_id,
        attempts=3,
        duration_ms=duration,
        error_message=str(last_error),
    )


def _mark_blocked(platform_id: str, epic_id: str, reason: str) -> None:
    """Transition epic to blocked. Best-effort — doesn't raise."""
    try:
        with get_conn() as conn:
            conn.execute(
                "UPDATE epics SET status='blocked', updated_at=? WHERE platform_id=? AND epic_id=?",
                (_now(), platform_id, epic_id),
            )
            conn.commit()
    except Exception:
        log.exception("mark_blocked_failed", extra={"platform_id": platform_id, "epic_id": epic_id})
