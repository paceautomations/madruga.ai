#!/usr/bin/env python3
"""Hook wrapper: reads Claude Code PostToolUse JSON from stdin,
extracts file_path, and calls post_save.py --detect-from-path."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return

    # Only trigger for files under platforms/
    if "platforms/" not in file_path:
        return

    subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "post_save.py"), "--detect-from-path", file_path, "--register-only"],
        capture_output=True,
    )


if __name__ == "__main__":
    main()
