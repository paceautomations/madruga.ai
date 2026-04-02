#!/usr/bin/env python3
"""PostToolUse hook: lint skill/knowledge files after edit.

Reads Claude Code PostToolUse JSON from stdin, extracts file_path.
If the file is under .claude/commands/ or .claude/knowledge/,
runs skill-lint.py on the affected skill and reports issues.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).parent
COMMANDS_PREFIX = ".claude/commands/madruga/"
KNOWLEDGE_PREFIX = ".claude/knowledge/"


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return

    # Normalize to relative path
    rel = file_path
    repo_str = str(REPO_ROOT)
    if rel.startswith(repo_str):
        rel = rel[len(repo_str) :].lstrip("/")

    is_command = rel.startswith(COMMANDS_PREFIX)
    is_knowledge = rel.startswith(KNOWLEDGE_PREFIX)
    if not is_command and not is_knowledge:
        return

    # Build lint command
    lint_script = str(SCRIPTS_DIR / "skill-lint.py")
    if is_command and rel.endswith(".md"):
        skill_name = Path(rel).stem
        cmd = [sys.executable, lint_script, "--skill", skill_name, "--json"]
    else:
        cmd = [sys.executable, lint_script, "--json"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        return

    try:
        findings = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        return

    if not findings:
        return

    important = [f for f in findings if f["severity"] in ("BLOCKER", "WARNING")]
    if not important:
        return

    blockers = [f for f in important if f["severity"] == "BLOCKER"]
    warnings = [f for f in important if f["severity"] == "WARNING"]
    parts = []
    if blockers:
        parts.append(f"{len(blockers)} BLOCKER(s)")
    if warnings:
        parts.append(f"{len(warnings)} WARNING(s)")

    print(f"[skill-lint] {rel} — {', '.join(parts)}:")
    for f in important:
        print(f"  [{f['severity']}] {f['skill']}: {f['message']}")
    print("Fix via /madruga:skills-mgmt or: python3 .specify/scripts/skill-lint.py --skill <name>")


if __name__ == "__main__":
    main()
