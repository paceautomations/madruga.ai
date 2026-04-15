"""Ingest commits from a platform's bound external repo into the `commits` table.

Walks `git log` from the remote, INSERTs any SHAs not already tracked with
`source='external-fetch'`. Idempotent: re-runs skip commits already present.

Usage:
    python3 reverse_reconcile_ingest.py --platform <name> [--dry-run] [--since <iso>]
    python3 reverse_reconcile_ingest.py --platform <name> --assume-reconciled-before <sha>

The `--assume-reconciled-before` flag is a one-shot backlog cutter: marks all
commits reachable from `<sha>` as already reconciled without inspection. Use
when onboarding a repo with hundreds of historical commits.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".specify" / "scripts"))

import db_core  # noqa: E402
import ensure_repo as ensure_repo_mod  # noqa: E402

log = logging.getLogger("reverse_reconcile_ingest")


def _run_git(args: list[str], cwd: Path) -> str:
    """Run git with the given args in `cwd`. Returns stdout stripped."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _resolve_ref(repo_path: Path, branch: str) -> str:
    """Return 'origin/<branch>' if it exists, else plain '<branch>'. Raise if neither."""
    for ref in (f"origin/{branch}", branch):
        check = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )
        if check.returncode == 0:
            return ref
    raise SystemExit(
        f"ERROR: branch '{branch}' not found locally or on origin in {repo_path}. "
        f"Run `git -C {repo_path} fetch origin {branch}` or check platform.yaml:repo.base_branch."
    )


def _list_remote_shas(repo_path: Path, branch: str, since: str | None = None) -> list[dict]:
    """Return commits reachable from `<branch>` (prefers origin/<branch>), newest first.

    Each dict: {sha, message, author, committed_at, files}.
    `files` is a list of paths from the commit's diff-tree.
    """
    ref = _resolve_ref(repo_path, branch)
    # Single `git log --name-only` call: metadata line + blank + file list + record separator.
    # %x1e (RS) between commits; %x1f (US) between metadata fields.
    fmt = "%x1e%H%x1f%s%x1f%an%x1f%aI"
    args = [
        "log",
        ref,
        "--no-merges",
        f"--format={fmt}",
        "--name-only",
    ]
    if since:
        args.append(f"--since={since}")
    raw = _run_git(args, repo_path)
    commits: list[dict] = []
    for record in raw.split("\x1e"):
        record = record.strip()
        if not record:
            continue
        lines = record.split("\n", 1)
        meta = lines[0]
        parts = meta.split("\x1f")
        if len(parts) != 4:
            continue
        sha, message, author, committed_at = parts
        files = [f for f in lines[1].splitlines() if f.strip()] if len(lines) > 1 else []
        commits.append(
            {
                "sha": sha,
                "message": message,
                "author": author,
                "committed_at": committed_at,
                "files": files,
            }
        )
    return commits


def _existing_shas(conn, platform_id: str) -> set[str]:
    """Return SHAs already recorded for this platform (including composite form)."""
    rows = conn.execute(
        "SELECT sha FROM commits WHERE platform_id = ?",
        (platform_id,),
    ).fetchall()
    out: set[str] = set()
    for (sha,) in rows:
        out.add(sha)
        # Composite form `<sha>:<platform>` → also index the raw sha prefix
        if ":" in sha:
            out.add(sha.split(":", 1)[0])
    return out


def ingest(
    platform_id: str,
    *,
    dry_run: bool = False,
    since: str | None = None,
    branch: str | None = None,
    db_path: Path | None = None,
) -> dict:
    """Fetch remote + insert new commits from `branch` (defaults to platform's base_branch).

    Returns summary dict including the resolved branch name.
    """
    repo_path = ensure_repo_mod.ensure_repo(platform_id)
    if branch is None:
        branch = ensure_repo_mod.load_repo_binding(platform_id)["base_branch"]

    with db_core.get_conn(db_path) as conn:
        existing = _existing_shas(conn, platform_id)
        remote_commits = _list_remote_shas(repo_path, branch, since=since)

        to_insert: list[dict] = []
        for c in remote_commits:
            if c["sha"] in existing:
                continue
            to_insert.append(c)

        if dry_run:
            return {
                "platform": platform_id,
                "branch": branch,
                "remote_total": len(remote_commits),
                "already_tracked": len(remote_commits) - len(to_insert),
                "would_insert": len(to_insert),
                "sample_shas": [c["sha"][:8] for c in to_insert[:5]],
                "dry_run": True,
            }

        for c in to_insert:
            conn.execute(
                "INSERT INTO commits "
                "(sha, message, author, platform_id, epic_id, source, committed_at, files_json, reconciled_at) "
                "VALUES (?, ?, ?, ?, NULL, 'external-fetch', ?, ?, NULL)",
                (
                    c["sha"],
                    c["message"],
                    c["author"],
                    platform_id,
                    c["committed_at"],
                    json.dumps(c["files"]),
                ),
            )
        conn.commit()

        return {
            "platform": platform_id,
            "branch": branch,
            "remote_total": len(remote_commits),
            "already_tracked": len(remote_commits) - len(to_insert),
            "inserted": len(to_insert),
            "dry_run": False,
        }


def assume_reconciled_before(platform_id: str, sha: str, db_path: Path | None = None) -> int:
    """Mark all commits reachable from <sha> (inclusive) as reconciled."""
    repo_path = ensure_repo_mod.ensure_repo(platform_id)
    raw = _run_git(["rev-list", sha], repo_path)
    shas = [s.strip() for s in raw.splitlines() if s.strip()]
    if not shas:
        return 0

    with db_core.get_conn(db_path) as conn:
        placeholders = ",".join("?" for _ in shas)
        cur = conn.execute(
            f"UPDATE commits SET reconciled_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
            f"WHERE platform_id = ? AND reconciled_at IS NULL AND sha IN ({placeholders})",
            [platform_id, *shas],
        )
        conn.commit()
        return cur.rowcount


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--platform", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--since", help="ISO date, passed to `git log --since`")
    p.add_argument(
        "--branch",
        help="Override base branch from platform.yaml (debug only; default reads repo.base_branch)",
    )
    p.add_argument(
        "--assume-reconciled-before", metavar="SHA", help="Mark all commits reachable from SHA as reconciled"
    )
    p.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    args = p.parse_args(argv)

    if args.assume_reconciled_before:
        n = assume_reconciled_before(args.platform, args.assume_reconciled_before)
        result = {"platform": args.platform, "marked_reconciled": n}
    else:
        result = ingest(args.platform, dry_run=args.dry_run, since=args.since, branch=args.branch)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for k, v in result.items():
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
