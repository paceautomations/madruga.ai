"""Create and cleanup git worktrees for epic implementation."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def _branch_exists_on_remote(repo_path: Path, branch: str) -> bool:
    """Check if a branch exists on remote."""
    result = subprocess.run(
        ["git", "branch", "-r", "--list", f"origin/{branch}"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _get_cascade_base(repo_path: Path, platform_name: str, fallback: str) -> str:
    """Return the best base ref for a new epic worktree.

    Queries the DB for the last shipped epic's branch; if it exists on remote,
    returns ``origin/<branch>`` (cascade). Falls back to ``origin/<fallback>``
    on any error or if the branch is gone from remote.
    """
    try:
        from config import DB_PATH
        from db import get_conn

        with get_conn(DB_PATH) as conn:
            row = conn.execute(
                """SELECT branch_name FROM epics
                   WHERE platform_id = ? AND status = 'shipped' AND branch_name IS NOT NULL
                   ORDER BY delivered_at DESC, rowid DESC
                   LIMIT 1""",
                (platform_name,),
            ).fetchone()

        if row and row["branch_name"]:
            candidate = row["branch_name"]
            if _branch_exists_on_remote(repo_path, candidate):
                log.info(
                    "Cascade base: '%s' → last shipped branch '%s'",
                    platform_name,
                    candidate,
                )
                return f"origin/{candidate}"
            log.info(
                "Cascade base: '%s' not on remote — fallback to origin/%s",
                candidate,
                fallback,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("Cascade base lookup failed (%s) — using origin/%s", exc, fallback)

    return f"origin/{fallback}"


def create_worktree(platform_name: str, epic_slug: str) -> Path:
    """Create an isolated git worktree for an epic. Returns worktree path."""
    from ensure_repo import (
        REPO_ROOT,
        _is_self_ref,
        _load_repo_binding,
        _resolve_repos_base,
        ensure_repo,
    )

    binding = _load_repo_binding(platform_name)
    repo_name = binding["name"]

    # Self-ref → operate in current repo (no worktree).
    # ARCHITECTURAL INVARIANT: self-ref platforms MUST run epics sequentially.
    # Worktree isolation only works for external repos. Self-ref shares the
    # working directory, .pipeline/madruga.db, and .claude/ skills — parallel
    # epics here would cause checkout conflicts, DB desync, and stale skills.
    # See pipeline-dag-knowledge.md "Parallel Epics Constraint".
    if _is_self_ref(repo_name):
        log.info("Self-ref platform '%s' → %s (no worktree)", platform_name, REPO_ROOT)
        return REPO_ROOT

    # Ensure repo exists
    repo_path = ensure_repo(platform_name)

    # Resolve worktree path
    base = _resolve_repos_base()
    wt_path = base / f"{repo_name}-worktrees" / epic_slug
    branch = f"{binding['epic_branch_prefix']}{epic_slug}"
    base_branch = binding["base_branch"]

    # Crash recovery — reuse existing worktree
    if wt_path.exists() and (wt_path / ".git").exists():
        log.info("Worktree exists (crash recovery): %s", wt_path)
        return wt_path

    # Fetch latest
    log.info("Fetching origin in %s", repo_path)
    subprocess.run(
        ["git", "fetch", "origin"],
        cwd=str(repo_path),
        check=True,
    )

    # Create worktree
    wt_path.parent.mkdir(parents=True, exist_ok=True)

    if _branch_exists_on_remote(repo_path, branch):
        log.info("Branch '%s' exists on remote — checking out", branch)
        subprocess.run(
            ["git", "worktree", "add", str(wt_path), branch],
            cwd=str(repo_path),
            check=True,
        )
    else:
        cascade_base = _get_cascade_base(repo_path, platform_name, base_branch)
        log.info("Creating worktree: %s (branch: %s from %s)", wt_path, branch, cascade_base)
        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "-b", branch, cascade_base],
            cwd=str(repo_path),
            check=True,
        )

    log.info("Worktree ready: %s", wt_path)
    return wt_path


def cleanup_worktree(platform_name: str, epic_slug: str) -> None:
    """Remove a worktree and its local branch."""
    from ensure_repo import (
        _is_self_ref,
        _load_repo_binding,
        _resolve_repos_base,
        ensure_repo,
    )

    binding = _load_repo_binding(platform_name)
    repo_name = binding["name"]

    if _is_self_ref(repo_name):
        log.info("Self-ref platform — nothing to clean up")
        return

    repo_path = ensure_repo(platform_name)
    base = _resolve_repos_base()
    wt_path = base / f"{repo_name}-worktrees" / epic_slug
    branch = f"{binding['epic_branch_prefix']}{epic_slug}"

    # Remove worktree
    if wt_path.exists():
        log.info("Removing worktree: %s", wt_path)
        result = subprocess.run(
            ["git", "worktree", "remove", str(wt_path)],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log.warning("git worktree remove failed, removing dir manually")
            shutil.rmtree(wt_path, ignore_errors=True)

    # Delete local branch
    log.info("Deleting local branch: %s", branch)
    subprocess.run(
        ["git", "branch", "-d", branch],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )

    # Final cleanup
    if wt_path.exists():
        shutil.rmtree(wt_path, ignore_errors=True)

    log.info("Cleanup complete for %s/%s", platform_name, epic_slug)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage git worktrees for epics")
    sub = parser.add_subparsers(dest="action")

    p_create = sub.add_parser("create", help="Create worktree")
    p_create.add_argument("platform", help="Platform name")
    p_create.add_argument("epic_slug", help="Epic slug (e.g., 001-channel-pipeline)")
    p_create.add_argument("-v", "--verbose", action="store_true")

    p_cleanup = sub.add_parser("cleanup", help="Remove worktree")
    p_cleanup.add_argument("platform", help="Platform name")
    p_cleanup.add_argument("epic_slug", help="Epic slug")
    p_cleanup.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if args.action == "create":
        path = create_worktree(args.platform, args.epic_slug)
        print(path)
    elif args.action == "cleanup":
        cleanup_worktree(args.platform, args.epic_slug)
    else:
        parser.print_help()
