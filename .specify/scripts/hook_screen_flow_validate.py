#!/usr/bin/env python3
"""PostToolUse hook: validate platforms/<name>/business/screen-flow.yaml on save.

Reads the Claude Code PostToolUse JSON payload from stdin, extracts the file
path, and — if the path matches `platforms/**/business/screen-flow.yaml` —
runs `screen_flow_validator.py` against it.

If the validator reports BLOCKERs, this hook prints the structured findings to
stderr and exits 1 so the user can see why the file was rejected. If
validation passes (or the file is not a screen-flow YAML) the hook exits 0.

Implements FR-004 of epic 027-screen-flow-canvas.

Fallback: if the hook framework is unavailable (e.g. running outside Claude
Code), `make lint` re-runs the same validator across every platform directory
via `platform_cli.py lint`, so drift is caught at CI time even without the
hook.
"""

from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
VALIDATOR = SCRIPTS_DIR / "screen_flow_validator.py"

# Match both relative ("platforms/x/business/screen-flow.yaml") and absolute paths.
PATTERNS = (
    "platforms/*/business/screen-flow.yaml",
    "*/platforms/*/business/screen-flow.yaml",
)


def _matches(path: str) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in PATTERNS)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # malformed payload — never block the user

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path or not _matches(file_path):
        return 0

    if not VALIDATOR.exists():
        print(f"[screen-flow] validator not found at {VALIDATOR}", file=sys.stderr)
        return 0  # don't block when the validator was uninstalled

    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), file_path, "--json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return 0

    # Pretty-print findings for the user.
    try:
        payload = json.loads(proc.stdout)
        findings = payload.get("findings", [])
    except (json.JSONDecodeError, ValueError):
        findings = []

    print(f"[screen-flow] validation failed for {file_path}", file=sys.stderr)
    for f in findings:
        print(
            f"  {f.get('severity', 'BLOCKER'):7s}  "
            f"{f.get('path', '$')}  "
            f"{f.get('message', '')}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
