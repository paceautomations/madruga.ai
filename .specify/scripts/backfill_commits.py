"""Backfill historical commits into the pipeline SQLite DB.

Populates the ``commits`` table with the full git history since epic 001,
classifying each commit by platform and epic.  Uses a hybrid strategy:

- **Merge history**: ``git log main --merges`` identifies epic branch merges,
  then ``git log <merge>^..<merge>`` lists individual commits per epic.
- **First-parent**: ``git log --no-merges --first-parent main`` captures
  commits made directly on main (classified as ad-hoc).
- **Pre-006 cutoff**: Commits before SHA ``d6befe0`` are assigned to epic
  ``001-inicio-de-tudo``.

Idempotent: uses INSERT OR IGNORE on the SHA UNIQUE constraint (FR-009).

Usage:
    python3 .specify/scripts/backfill_commits.py [--db PATH]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Ensure .specify/scripts is on sys.path for imports (when called directly)
_SCRIPTS_DIR = str(Path(__file__).parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# Regex to extract epic/<platform>/<NNN-slug> from merge commit messages.
# Handles:
#   - git merge:  Merge branch 'epic/madruga-ai/012-foo' into main
#   - git merge:  Merge branch "epic/madruga-ai/012-foo" into main
#   - GitHub PR:  Merge pull request #N from org/epic/madruga-ai/012-foo
_EPIC_MERGE_RE = re.compile(r"epic/([^/]+)/(\d{3}-.+?)(?:['\"\s]|$)")


def parse_merge_message(message: str) -> tuple[str | None, str | None]:
    """Extract (platform_id, epic_id) from a merge commit message.

    Looks for the ``epic/<platform>/<NNN-slug>`` pattern in the message,
    regardless of quoting style or merge format.

    Args:
        message: Merge commit subject line.

    Returns:
        Tuple of (platform_id, epic_id).  Both None if no epic pattern found.

    Examples:
        >>> parse_merge_message("Merge branch 'epic/madruga-ai/012-foo' into main")
        ('madruga-ai', '012-foo')
        >>> parse_merge_message("Merge branch 'feature/bar' into main")
        (None, None)
    """
    m = _EPIC_MERGE_RE.search(message)
    if m:
        return m.group(1), m.group(2)
    return None, None


def get_merge_commits() -> list[dict]:
    """List merge commits on main that came from epic branches.

    Runs ``git log main --merges --format=%H%n%s%n%P`` and parses the output
    into a list of dicts.  Only merges whose message references an
    ``epic/<platform>/<NNN-slug>`` branch are included.

    Returns:
        List of dicts with keys: sha, message, epic_id, platform_id, parents.
        Empty list if no epic merges found or git output is empty.
    """
    result = subprocess.run(
        ["git", "log", "main", "--merges", "--format=%H%n%s%n%P"],
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout.strip()
    if not output:
        return []

    lines = output.split("\n")
    merges: list[dict] = []

    # Process in groups of 3 lines: sha, subject, parents
    for i in range(0, len(lines) - 2, 3):
        sha = lines[i]
        subject = lines[i + 1]
        parents_str = lines[i + 2]

        platform_id, epic_id = parse_merge_message(subject)
        if platform_id is None:
            continue  # Not an epic merge — skip

        merges.append(
            {
                "sha": sha,
                "message": subject,
                "epic_id": epic_id,
                "platform_id": platform_id,
                "parents": parents_str.split(),
            }
        )

    return merges


def get_epic_commits_from_merge(merge_sha: str) -> list[dict]:
    """List individual commits that were part of a merge.

    Runs ``git log <merge>^..<merge> --format=%H%n%s%n%an%n%aI`` to get the
    commits introduced by the merge (i.e. the epic branch commits).  For each
    commit, also retrieves changed files via ``git diff-tree``.

    Args:
        merge_sha: SHA of the merge commit.

    Returns:
        List of dicts with keys: sha, message, author, date, files.
        Empty list if the range contains no commits or git fails.
    """
    # Get commit metadata for the range introduced by the merge
    log_result = subprocess.run(
        [
            "git",
            "log",
            f"{merge_sha}^..{merge_sha}",
            "--format=%H%n%s%n%an%n%aI",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    output = log_result.stdout.strip()
    if not output:
        return []

    lines = output.split("\n")
    commits: list[dict] = []

    # Process in groups of 4 lines: sha, subject, author, date
    for i in range(0, len(lines) - 3, 4):
        sha = lines[i]
        message = lines[i + 1]
        author = lines[i + 2]
        date = lines[i + 3]

        # Get changed files for this commit
        tree_result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f for f in tree_result.stdout.strip().split("\n") if f]

        commits.append(
            {
                "sha": sha,
                "message": message,
                "author": author,
                "date": date,
                "files": files,
            }
        )

    return commits


def get_direct_main_commits() -> list[dict]:
    """List non-merge commits made directly on main (first-parent only).

    Runs ``git log --no-merges --first-parent main --format=%H%n%s%n%an%n%aI``
    to capture commits that were pushed directly to main without going through
    an epic branch.  These are classified as ad-hoc (epic_id=NULL).

    For each commit, also retrieves changed files via ``git diff-tree``.

    Returns:
        List of dicts with keys: sha, message, author, date, files.
        Empty list if no direct commits found or git output is empty.
    """
    log_result = subprocess.run(
        [
            "git",
            "log",
            "--no-merges",
            "--first-parent",
            "main",
            "--format=%H%n%s%n%an%n%aI",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    output = log_result.stdout.strip()
    if not output:
        return []

    lines = output.split("\n")
    commits: list[dict] = []

    # Process in groups of 4 lines: sha, subject, author, date
    for i in range(0, len(lines) - 3, 4):
        sha = lines[i]
        message = lines[i + 1]
        author = lines[i + 2]
        date = lines[i + 3]

        # Get changed files for this commit
        tree_result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f for f in tree_result.stdout.strip().split("\n") if f]

        commits.append(
            {
                "sha": sha,
                "message": message,
                "author": author,
                "date": date,
                "files": files,
            }
        )

    return commits


# File path pattern: platforms/<platform_id>/...
_PLATFORM_FILE_RE = re.compile(r"^platforms/([^/]+)/")

# Default fallback platform
_FALLBACK_PLATFORM = "madruga-ai"

# Default cutoff SHA for pre-006 commits (epic 001-inicio-de-tudo)
_DEFAULT_CUTOFF_SHA = "d6befe0"


def _detect_platform_from_files(files: list[str]) -> str:
    """Detect platform from file paths. Returns first match or fallback."""
    for fpath in files:
        m = _PLATFORM_FILE_RE.match(fpath)
        if m:
            return m.group(1)
    return _FALLBACK_PLATFORM


def classify_pre006(
    sha: str,
    cutoff_sha: str = _DEFAULT_CUTOFF_SHA,
    ordered_shas: list[str] | None = None,
) -> str | None:
    """Classify whether a commit belongs to epic 001-inicio-de-tudo.

    Commits at or before the cutoff SHA (d6befe0) are linked to the first epic.

    Args:
        sha: The commit SHA to classify.
        cutoff_sha: The last SHA belonging to epic 001 (default: d6befe0).
        ordered_shas: Optional list of SHAs in chronological order (oldest first).
            When provided, uses positional comparison instead of prefix matching.

    Returns:
        ``'001-inicio-de-tudo'`` if the commit is at or before the cutoff,
        ``None`` otherwise.
    """
    epic_001 = "001-inicio-de-tudo"

    def _prefix_match(a: str, b: str) -> bool:
        """Check if a and b match via prefix (either direction)."""
        return a == b or a.startswith(b) or b.startswith(a)

    if ordered_shas is not None:
        if not ordered_shas:
            return None

        # Find positions using prefix matching
        sha_pos = None
        cutoff_pos = None
        for idx, s in enumerate(ordered_shas):
            if sha_pos is None and _prefix_match(s, sha):
                sha_pos = idx
            if cutoff_pos is None and _prefix_match(s, cutoff_sha):
                cutoff_pos = idx

        if sha_pos is None or cutoff_pos is None:
            return None
        return epic_001 if sha_pos <= cutoff_pos else None

    # Simple mode: direct prefix comparison
    if _prefix_match(sha, cutoff_sha):
        return epic_001
    return None


def run_backfill(conn) -> dict:
    """Run the full backfill: merge commits + direct main commits + pre-006 classification.

    Orchestrates the hybrid backfill strategy (FR-010):
    1. Merge commits → epic commits (linked to their epic)
    2. Direct main commits → classify_pre006 (pre-006 → epic 001, rest → ad-hoc)

    Inserts all commits with ``source='backfill'``.  Uses INSERT OR IGNORE
    for idempotency (FR-009).

    Args:
        conn: SQLite connection with commits table already created.

    Returns:
        Dict with summary: total, epic_commits, adhoc_commits, by_epic.
    """
    by_epic: dict[str, int] = {}

    def _insert(commit: dict, platform: str, epic_id: str | None) -> None:
        """Insert a single commit row. Tracks per-epic counts."""
        conn.execute(
            """INSERT OR IGNORE INTO commits
               (sha, message, author, platform_id, epic_id, source, committed_at, files_json)
               VALUES (?, ?, ?, ?, ?, 'backfill', ?, ?)""",
            (
                commit["sha"],
                commit["message"],
                commit["author"],
                platform,
                epic_id,
                commit["date"],
                json.dumps(commit["files"]),
            ),
        )
        if epic_id:
            by_epic[epic_id] = by_epic.get(epic_id, 0) + 1

    # 1. Process merge commits (epic branches)
    merges = get_merge_commits()
    for merge in merges:
        epic_commits = get_epic_commits_from_merge(merge["sha"])
        for commit in epic_commits:
            platform = _detect_platform_from_files(commit["files"])
            _insert(commit, platform, merge["epic_id"])

    # 2. Process direct main commits — apply classify_pre006 (FR-011)
    direct_commits = get_direct_main_commits()
    # Build ordered SHA list for positional pre-006 classification
    ordered_shas = [c["sha"] for c in reversed(direct_commits)]  # oldest first
    for commit in direct_commits:
        platform = _detect_platform_from_files(commit["files"])
        epic_id = classify_pre006(
            commit["sha"],
            ordered_shas=ordered_shas if ordered_shas else None,
        )
        _insert(commit, platform, epic_id)

    conn.commit()

    # Summary
    total = conn.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    epic_count = conn.execute("SELECT COUNT(*) FROM commits WHERE epic_id IS NOT NULL").fetchone()[0]
    adhoc_count = conn.execute("SELECT COUNT(*) FROM commits WHERE epic_id IS NULL").fetchone()[0]

    return {
        "total": total,
        "epic_commits": epic_count,
        "adhoc_commits": adhoc_count,
        "by_epic": by_epic,
    }


def main() -> None:
    """CLI entrypoint for backfill.

    Parses ``--db`` argument, connects to DB, runs migrations, executes
    the full backfill, and prints a summary.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill git commits into pipeline SQLite DB",
    )
    parser.add_argument(
        "--db",
        type=Path,
        help="Path to SQLite DB (default: .pipeline/madruga.db)",
    )
    args = parser.parse_args()

    db_path = args.db or Path(__file__).parent.parent.parent / ".pipeline" / "madruga.db"

    from db_core import get_conn, migrate

    conn = get_conn(db_path)
    migrate(conn)

    print(f"Running backfill against {db_path}...")
    result = run_backfill(conn)
    conn.close()

    print(f"Backfill complete: {result['total']} total commits")
    print(f"  Epic commits: {result['epic_commits']}")
    print(f"  Ad-hoc commits: {result['adhoc_commits']}")
    if result.get("by_epic"):
        print("  By epic:")
        for epic, count in sorted(result["by_epic"].items()):
            print(f"    {epic}: {count}")


if __name__ == "__main__":
    main()
