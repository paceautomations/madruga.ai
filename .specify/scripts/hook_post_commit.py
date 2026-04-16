"""Post-commit hook: register commits in the pipeline SQLite DB.

Best-effort — errors are logged to stderr but never block the commit (FR-007).
Identifies platform from branch name or file paths, epic from branch or message tag.

Usage (as git hook):
    python3 .specify/scripts/hook_post_commit.py

Usage (programmatic):
    from hook_post_commit import parse_branch, detect_platforms_from_files
    platform, epic = parse_branch("epic/madruga-ai/023-commit-traceability")
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

# DB path — overridden in tests via patch
DB_PATH = Path(__file__).parent.parent.parent / ".pipeline" / "madruga.db"

# Default platform when no platforms/<X>/ match is found in file paths
_FALLBACK_PLATFORM = "madruga-ai"

# Branch pattern: epic/<platform>/<NNN-slug>
_BRANCH_RE = re.compile(r"^epic/([^/]+)/(\d{3}-.+)$")

# File path pattern: platforms/<platform_id>/...
_PLATFORM_FILE_RE = re.compile(r"^platforms/([^/]+)/")

# Commit message tag: [epic:NNN] where NNN is one or more digits
_EPIC_TAG_RE = re.compile(r"\[epic:(\d+)\]")

# Epic tag accepting either NNN or NNN-slug. Used by reverse_reconcile_ingest
# to attribute external commits to epics. Kept separate from _EPIC_TAG_RE to
# avoid changing the local hook contract (which expects digits-only).
_EPIC_TAG_SLUG_RE = re.compile(r"\[epic:(\d{3}(?:-[a-z0-9][a-z0-9-]*)?)\]")

# Body trailer: line of the form "Epic: NNN-slug" or "Epic: NNN".
_EPIC_TRAILER_RE = re.compile(r"^Epic:\s+(\d{3}(?:-[a-z0-9][a-z0-9-]*)?)\s*$", re.MULTILINE)


def parse_branch(branch_name: str) -> tuple[str | None, str | None]:
    """Extract (platform_id, epic_id) from branch name.

    Pattern: ``epic/<platform>/<NNN-slug>``

    Returns:
        Tuple of (platform_id, epic_id). Both None if branch doesn't match.

    Examples:
        >>> parse_branch("epic/prosauai/007-foo")
        ('prosauai', '007-foo')
        >>> parse_branch("main")
        (None, None)
        >>> parse_branch("epic/prosauai")
        (None, None)
    """
    m = _BRANCH_RE.match(branch_name)
    if m:
        return m.group(1), m.group(2)
    return None, None


def detect_platforms_from_files(file_list: list[str]) -> set[str]:
    """Detect platform IDs from file paths.

    Scans each path for the ``platforms/<name>/`` prefix and collects
    unique platform identifiers.  Falls back to ``madruga-ai`` when no
    platform directory is matched (e.g. repo-wide files like Makefile).

    Args:
        file_list: Paths relative to repo root (as returned by git diff-tree).

    Returns:
        Non-empty set of platform IDs.

    Examples:
        >>> detect_platforms_from_files(["platforms/prosauai/x.md"])
        {'prosauai'}
        >>> detect_platforms_from_files(["Makefile"])
        {'madruga-ai'}
    """
    platforms: set[str] = set()
    for path in file_list:
        m = _PLATFORM_FILE_RE.match(path)
        if m:
            platforms.add(m.group(1))
    return platforms if platforms else {_FALLBACK_PLATFORM}


def parse_epic_tag(message: str) -> str | None:
    """Extract epic number from ``[epic:NNN]`` tag in commit message.

    When present, the tag overrides the branch-based epic detection (FR-005).
    Returns the raw number string (e.g. ``"015"``), not the full slug.

    Args:
        message: Git commit message (first line or full).

    Returns:
        Epic number string if tag found, None otherwise.

    Examples:
        >>> parse_epic_tag("fix: endpoint [epic:015]")
        '015'
        >>> parse_epic_tag("feat: normal commit")
        None
    """
    m = _EPIC_TAG_RE.search(message)
    return m.group(1) if m else None


def parse_epic_tag_slug(message: str) -> str | None:
    """Extract epic slug from ``[epic:NNN-slug]`` tag or ``Epic: NNN-slug`` trailer.

    Used by reverse_reconcile_ingest to attribute external commits. Accepts
    both full slug (``042-bar``) and digits-only (``042``); caller must
    normalize digits-only against the platform's epic directory listing.

    Resolution order: subject/body tag first, then trailer in body.

    Examples:
        >>> parse_epic_tag_slug("feat: x [epic:042-bar]")
        '042-bar'
        >>> parse_epic_tag_slug("feat: x [epic:042]")
        '042'
        >>> parse_epic_tag_slug("feat: x\\n\\nEpic: 042-bar\\n")
        '042-bar'
        >>> parse_epic_tag_slug("feat: nothing here")
    """
    m = _EPIC_TAG_SLUG_RE.search(message)
    if m:
        return m.group(1)
    m = _EPIC_TRAILER_RE.search(message)
    return m.group(1) if m else None


def _get_current_branch() -> str:
    """Return the current git branch name.

    Returns:
        Branch name string (e.g. ``"main"`` or ``"epic/madruga-ai/023-commit-traceability"``).

    Raises:
        subprocess.CalledProcessError: If git command fails.
    """
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


_GITHUB_URL_RE = re.compile(r"github\.com[:/]([^/]+)/([^/.\s]+)")


def get_host_repo() -> str | None:
    """Return ``<org>/<name>`` of the local checkout's origin remote.

    Parsed from ``git config remote.origin.url`` — handles both SSH
    (``git@github.com:org/name.git``) and HTTPS (``https://github.com/org/name``)
    forms. Returns None if no GitHub remote is configured (best-effort).
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    m = _GITHUB_URL_RE.search(result.stdout.strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None


def get_head_info() -> dict:
    """Retrieve info about the HEAD commit via git subprocess calls.

    Runs two git commands:
    1. ``git log -1 --format=%H%n%s%n%an%n%aI`` for sha, message, author, date
    2. ``git diff-tree --no-commit-id --name-only -r HEAD`` for changed files

    Returns:
        Dict with keys: sha, message, author, date, files (list of paths).

    Raises:
        subprocess.CalledProcessError: If git commands fail.
        ValueError: If git log output is malformed.
    """
    # Get commit metadata
    log_result = subprocess.run(
        ["git", "log", "-1", "--format=%H%n%s%n%an%n%aI"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = log_result.stdout.strip().split("\n")
    if len(lines) < 4:
        msg = f"Expected 4 lines from git log, got {len(lines)}"
        raise ValueError(msg)

    # Get changed files
    tree_result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    files = [f for f in tree_result.stdout.strip().split("\n") if f]

    return {
        "sha": lines[0],
        "message": lines[1],
        "author": lines[2],
        "date": lines[3],
        "files": files,
    }


def main() -> None:
    """Orchestrate commit registration — best-effort, never raises (FR-007).

    Flow: get_head_info → _get_current_branch → parse_branch →
    detect_platforms_from_files → parse_epic_tag → insert_commit per platform.

    All exceptions are caught and logged to stderr. The hook always exits
    cleanly so ``git commit`` is never blocked.
    """
    try:
        from db_core import get_conn
        from db_pipeline import insert_commit

        info = get_head_info()
        branch = _get_current_branch()

        # Detect platform and epic from branch
        branch_platform, branch_epic = parse_branch(branch)

        # Branch is authoritative on epic branches: a commit on
        # `epic/<X>/<NNN-slug>` belongs to platform X regardless of which
        # files it touches. File-path detection is the fallback for non-epic
        # branches (e.g., main/hotfix). Prevents prosauai work committed in
        # the madruga.ai checkout from being mis-tagged as madruga-ai.
        if branch_platform:
            platforms = {branch_platform}
        else:
            platforms = detect_platforms_from_files(info["files"])

        # Epic tag in message overrides branch epic (FR-005)
        tag_epic = parse_epic_tag(info["message"])
        epic_id = tag_epic if tag_epic is not None else branch_epic

        # Serialize file list
        files_json = json.dumps(info["files"])
        host_repo = get_host_repo()

        # Connect to DB (WAL mode, busy_timeout per ADR-012) and insert one row per platform
        conn = get_conn(DB_PATH)
        try:
            for platform in platforms:
                # Multi-platform commits use composite SHA for uniqueness (pitch.md #7)
                sha = f"{info['sha']}:{platform}" if len(platforms) > 1 else info["sha"]
                insert_commit(
                    conn,
                    sha=sha,
                    message=info["message"],
                    author=info["author"],
                    platform_id=platform,
                    epic_id=epic_id,
                    source="hook",
                    committed_at=info["date"],
                    files_json=files_json,
                    host_repo=host_repo,
                )
            conn.commit()
        finally:
            conn.close()

    except Exception as exc:
        # Best-effort: log to stderr, never block the commit
        print(f"post-commit hook error: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
