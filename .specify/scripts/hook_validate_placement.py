#!/usr/bin/env python3
"""PostToolUse hook: warns when files are written to locations that look like
external platform code accidentally placed in the madruga.ai repo.

Non-blocking (always exits 0). Warnings go to stderr so Claude Code
displays them inline without stopping the session.
"""

import functools
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
_SELF_REF_REPO_NAME = "madruga.ai"

# Prefixes that are always valid madruga.ai paths — skip check entirely.
_SAFE_PREFIXES = (
    ".claude/",
    ".specify/",
    ".pipeline/",
    ".git/",
    "platforms/",
    "portal/",
    "docs/",
    "etc/",
    "tests/",
    ".github/",
)

# Root-level patterns that should never exist in a documentation repo.
_FORBIDDEN_ROOT = {
    "migrations": "Pipeline migrations live at .pipeline/migrations/, not /migrations/",
}

_FORBIDDEN_ROOT_GLOBS = (
    ("docker-compose", "madruga.ai is a documentation system, not a Docker app"),
    ("Dockerfile", "madruga.ai is a documentation system, not a Docker app"),
)


@functools.lru_cache(maxsize=16)
def _load_platform_repo_name(platform_dir: str) -> str | None:
    """Read repo.name from a platform's platform.yaml. Returns None on error."""
    manifest = REPO_ROOT / "platforms" / platform_dir / "platform.yaml"
    if not manifest.exists():
        return None
    try:
        with open(manifest) as f:
            data = yaml.safe_load(f)
        return (data.get("repo") or {}).get("name")
    except Exception:
        return None


@functools.lru_cache(maxsize=1)
def _list_platform_dirs() -> frozenset[str]:
    """List directory names under platforms/ (cached, returns frozenset for O(1) lookup)."""
    platforms_dir = REPO_ROOT / "platforms"
    if not platforms_dir.is_dir():
        return frozenset()
    return frozenset(d.name for d in platforms_dir.iterdir() if d.is_dir() and (d / "platform.yaml").exists())


def _warn(msg: str) -> None:
    print(f"WARNING: {msg}", file=sys.stderr)


def _check_placement(file_path: str) -> None:
    """Check if file_path looks misplaced. Prints warnings to stderr."""
    try:
        rel = str(Path(file_path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return  # File is outside the repo — not our concern.

    # Fast path: known-good prefixes.
    if any(rel.startswith(p) for p in _SAFE_PREFIXES):
        return

    parts = rel.split("/")
    top = parts[0]

    # Check forbidden root-level directories.
    if top in _FORBIDDEN_ROOT:
        _warn(f"'{rel}' — {_FORBIDDEN_ROOT[top]}.")
        return

    # Check forbidden root-level file patterns.
    if len(parts) == 1:
        for pattern, reason in _FORBIDDEN_ROOT_GLOBS:
            if top.startswith(pattern):
                _warn(f"'{rel}' — {reason}.")
                return

    # Check if top-level dir matches an external platform name.
    if top in _list_platform_dirs():
        repo_name = _load_platform_repo_name(top)
        if repo_name and repo_name != _SELF_REF_REPO_NAME:
            _warn(
                f"'{rel}' looks like code for external platform '{top}' "
                f"(repo: {repo_name}). This file should be in the external repo, "
                f"not in madruga.ai."
            )


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return

    _check_placement(file_path)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # Never crash — FR-007 compliance.
