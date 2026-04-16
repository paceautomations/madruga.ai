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
from backfill_commits import parse_merge_message  # noqa: E402
from hook_post_commit import parse_epic_tag_slug  # noqa: E402

log = logging.getLogger("reverse_reconcile_ingest")

REPO_PLATFORMS_DIR = REPO_ROOT / "platforms"


def _load_approved_epics(platform_id: str) -> set[str]:
    """Return slugs of epics whose ``reconcile-report.md`` exists on disk.

    Presence of the report is the authoritative marker that a forward reconcile
    was approved (Invariant 1). Ingest uses this to set ``reconciled_at`` at
    INSERT time for commits belonging to already-reconciled epics.

    Cost: 1 listdir + N stats where N = epic count per platform (typically <20).
    """
    epics_dir = REPO_PLATFORMS_DIR / platform_id / "epics"
    if not epics_dir.is_dir():
        return set()
    approved: set[str] = set()
    for entry in epics_dir.iterdir():
        if not entry.is_dir():
            continue
        if (entry / "reconcile-report.md").is_file():
            approved.add(entry.name)
    return approved


def _epic_dir_exists(platform_id: str, slug: str) -> bool:
    """Return True if ``platforms/<platform>/epics/<slug>/`` exists on disk."""
    return (REPO_PLATFORMS_DIR / platform_id / "epics" / slug).is_dir()


def _normalize_epic_slug(tag: str, approved: set[str], platform_id: str) -> str | None:
    """Normalize a tag value against known epic directories.

    If ``tag`` is already a full slug (``042-bar``) and the directory exists
    (or is in ``approved``), return it unchanged. If ``tag`` is digits-only
    (``042``), try to match a unique epic whose slug starts with ``<tag>-``.
    Ambiguous or missing → log warning and return None (Invariant 5).
    """
    if "-" in tag:
        if tag in approved or _epic_dir_exists(platform_id, tag):
            return tag
        log.warning(
            "commit tags [epic:%s] but no such epic dir for platform %s — ignoring",
            tag,
            platform_id,
        )
        return None
    prefix = f"{tag}-"
    candidates = [s for s in approved if s.startswith(prefix)]
    if len(candidates) == 1:
        return candidates[0]
    epics_dir = REPO_PLATFORMS_DIR / platform_id / "epics"
    if epics_dir.is_dir():
        disk_candidates = [e.name for e in epics_dir.iterdir() if e.is_dir() and e.name.startswith(prefix)]
        if len(disk_candidates) == 1:
            return disk_candidates[0]
        if len(disk_candidates) > 1:
            log.warning(
                "commit tags [epic:%s] ambiguous: multiple dirs match %s* — ignoring",
                tag,
                prefix,
            )
            return None
    log.warning(
        "commit tags [epic:%s] but no epic dir starts with %s for %s — ignoring",
        tag,
        prefix,
        platform_id,
    )
    return None


def _build_merge_map(repo_path: Path, branch: str, platform_id: str) -> dict[str, tuple[str, str]]:
    """Return ``{child_sha: (platform, epic)}`` for commits brought in by merge commits.

    Uses a single ``git log --format=%H %P %s`` call (via US/RS delimiters) to get
    the full ancestry graph + merge subjects. For each merge whose subject encodes
    an ``epic/<platform>/<slug>`` reference (via ``parse_merge_message``), walk the
    commit DAG from ``parent[1]`` (the merged branch tip) stopping at any ancestor
    of ``parent[0]`` (the base). Every SHA visited inherits that (platform, epic).

    Performance: 1 subprocess call regardless of merge count. Walk is O(N) in
    commits reachable from ``branch``, entirely in-memory.
    """
    ref = _resolve_ref(repo_path, branch)
    raw = _run_git(
        ["log", ref, "--format=%H%x1f%P%x1f%s"],
        repo_path,
    )
    graph: dict[str, list[str]] = {}
    subjects: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        sha, parents, subject = parts
        graph[sha] = parents.split() if parents else []
        subjects[sha] = subject

    merge_map: dict[str, tuple[str, str]] = {}
    for merge_sha, parents in graph.items():
        if len(parents) < 2:
            continue
        if len(parents) > 2:
            # Octopus merges: too ambiguous to attribute deterministically.
            continue
        mp, me = parse_merge_message(subjects.get(merge_sha, ""))
        if not me or (mp and mp != platform_id):
            continue
        epic = me
        base_parent, branch_parent = parents[0], parents[1]

        base_ancestors: set[str] = set()
        stack = [base_parent]
        while stack:
            cur = stack.pop()
            if cur in base_ancestors or cur not in graph:
                continue
            base_ancestors.add(cur)
            stack.extend(graph[cur])

        stack = [branch_parent]
        seen: set[str] = set()
        while stack:
            cur = stack.pop()
            if cur in seen or cur in base_ancestors or cur not in graph:
                continue
            seen.add(cur)
            merge_map.setdefault(cur, (platform_id, epic))
            stack.extend(graph[cur])
    return merge_map


def _fetch_bodies(repo_path: Path, branch: str, since: str | None = None) -> dict[str, str]:
    """Return ``{sha: body}`` for all non-merge commits reachable from ``branch``.

    Body is needed to support the ``Epic: <slug>`` trailer convention. Single
    git call; output split on ``\\x1e`` record separator between commits.
    """
    ref = _resolve_ref(repo_path, branch)
    args = ["log", ref, "--no-merges", "--format=%H%x1f%B%x1e"]
    if since:
        args.append(f"--since={since}")
    raw = _run_git(args, repo_path)
    bodies: dict[str, str] = {}
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if not record or "\x1f" not in record:
            continue
        sha, body = record.split("\x1f", 1)
        sha = sha.strip()
        if sha:
            bodies[sha] = body
    return bodies


def _resolve_epic(
    commit: dict,
    body: str,
    merge_map: dict[str, tuple[str, str]],
    approved: set[str],
    platform_id: str,
) -> str | None:
    """Resolve ``epic_id`` for an external commit.

    Order (Invariant 2): subject/body tag → merge map → None.
    """
    tag = parse_epic_tag_slug(commit["message"]) or parse_epic_tag_slug(body or "")
    if tag:
        slug = _normalize_epic_slug(tag, approved, platform_id)
        if slug is not None:
            return slug
    hit = merge_map.get(commit["sha"])
    if hit and hit[0] == platform_id:
        return hit[1]
    return None


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
    """Return raw SHAs already tracked for THIS platform (raw or composite form).

    Used for dedup: if a commit is already recorded for this platform, skip it.
    """
    rows = conn.execute(
        "SELECT sha FROM commits WHERE platform_id = ?",
        (platform_id,),
    ).fetchall()
    out: set[str] = set()
    for (sha,) in rows:
        out.add(sha)
        if ":" in sha:
            out.add(sha.split(":", 1)[0])
    return out


def _globally_tracked_shas(conn) -> set[str]:
    """Return raw SHAs tracked under ANY platform. Used to decide composite-form storage.

    The `commits.sha` column has a UNIQUE constraint (global). If we try to INSERT
    a raw SHA that already exists for another platform, SQLite raises IntegrityError.
    Mirrors `hook_post_commit.py` behavior: store as `<sha>:<platform>` in that case.
    """
    rows = conn.execute("SELECT sha FROM commits").fetchall()
    out: set[str] = set()
    for (sha,) in rows:
        out.add(sha.split(":", 1)[0] if ":" in sha else sha)
    return out


def _reconcile_orphans(conn, platform_id: str, remote_shas: set[str], dry_run: bool) -> int:
    """Auto-reconcile SHAs tagged for this platform but absent from external repo's base_branch.

    These are cross-repo attribution artifacts: `hook_post_commit.py` tags a commit
    to platform X when any file matches `platforms/X/`, so madruga-ai commits
    editing `platforms/prosauai/*` get tagged for prosauai but never appear in
    prosauai's develop. Leaving them unreconciled creates phantom drift forever.
    """
    rows = conn.execute(
        "SELECT sha FROM commits WHERE platform_id = ? AND reconciled_at IS NULL",
        (platform_id,),
    ).fetchall()
    orphans = [sha for (sha,) in rows if sha.split(":", 1)[0] not in remote_shas]
    if not orphans or dry_run:
        return len(orphans)
    placeholders = ",".join("?" for _ in orphans)
    conn.execute(
        f"UPDATE commits SET reconciled_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
        f"WHERE platform_id = ? AND reconciled_at IS NULL AND sha IN ({placeholders})",
        [platform_id, *orphans],
    )
    return len(orphans)


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
    binding = ensure_repo_mod.load_repo_binding(platform_id)
    if branch is None:
        branch = binding["base_branch"]
    # host_repo: SHAs ingested by this script live in the bound repo of platform_id.
    host_repo = f"{binding['org']}/{binding['name']}" if binding.get("org") and binding.get("name") else None

    approved_epics = _load_approved_epics(platform_id)

    with db_core.get_conn(db_path) as conn:
        existing = _existing_shas(conn, platform_id)
        globally_tracked = _globally_tracked_shas(conn)
        remote_commits = _list_remote_shas(repo_path, branch, since=since)
        remote_shas = {c["sha"] for c in remote_commits}

        merge_map = _build_merge_map(repo_path, branch, platform_id)
        bodies = _fetch_bodies(repo_path, branch, since=since)

        to_insert: list[dict] = []
        for c in remote_commits:
            if c["sha"] in existing:
                continue
            # If SHA exists under another platform, use composite form to bypass UNIQUE
            stored_sha = f"{c['sha']}:{platform_id}" if c["sha"] in globally_tracked else c["sha"]
            epic_id = _resolve_epic(c, bodies.get(c["sha"], ""), merge_map, approved_epics, platform_id)
            to_insert.append({**c, "stored_sha": stored_sha, "epic_id": epic_id})

        orphans_reconciled = _reconcile_orphans(conn, platform_id, remote_shas, dry_run)

        if dry_run:
            return {
                "platform": platform_id,
                "branch": branch,
                "remote_total": len(remote_commits),
                "already_tracked": len(remote_commits) - len(to_insert),
                "would_insert": len(to_insert),
                "would_reconcile_orphans": orphans_reconciled,
                "with_epic": sum(1 for c in to_insert if c["epic_id"]),
                "approved_epics": sorted(approved_epics),
                "sample_shas": [c["sha"][:8] for c in to_insert[:5]],
                "dry_run": True,
            }

        auto_marked = 0
        for c in to_insert:
            is_approved = bool(c["epic_id"]) and c["epic_id"] in approved_epics
            reconciled_expr = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')" if is_approved else "NULL"
            if is_approved:
                auto_marked += 1
            conn.execute(
                "INSERT INTO commits "
                "(sha, message, author, platform_id, epic_id, source, committed_at, "
                "files_json, reconciled_at, host_repo) "
                f"VALUES (?, ?, ?, ?, ?, 'external-fetch', ?, ?, {reconciled_expr}, ?)",
                (
                    c["stored_sha"],
                    c["message"],
                    c["author"],
                    platform_id,
                    c["epic_id"],
                    c["committed_at"],
                    json.dumps(c["files"]),
                    host_repo,
                ),
            )

        retroactively_marked = _upgrade_pending_reconciled(conn, platform_id, approved_epics)
        conn.commit()

        return {
            "platform": platform_id,
            "branch": branch,
            "remote_total": len(remote_commits),
            "already_tracked": len(remote_commits) - len(to_insert),
            "inserted": len(to_insert),
            "with_epic": sum(1 for c in to_insert if c["epic_id"]),
            "auto_marked_on_insert": auto_marked,
            "retroactively_marked": retroactively_marked,
            "orphans_reconciled": orphans_reconciled,
            "dry_run": False,
        }


def _upgrade_pending_reconciled(conn, platform_id: str, approved_epics: set[str]) -> int:
    """Mark still-pending commits whose epic has an approved reconcile-report.

    Covers commits that were ingested BEFORE the report existed (Invariant 3,
    retroactive pass). Idempotent: the ``WHERE reconciled_at IS NULL`` clause
    prevents touching already-marked rows. Uses the partial index
    ``idx_commits_reconciled_pending`` (migration 018).
    """
    if not approved_epics:
        return 0
    epic_list = sorted(approved_epics)
    placeholders = ",".join("?" for _ in epic_list)
    cur = conn.execute(
        f"UPDATE commits SET reconciled_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
        f"WHERE platform_id = ? AND reconciled_at IS NULL AND epic_id IN ({placeholders})",
        [platform_id, *epic_list],
    )
    return cur.rowcount


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
