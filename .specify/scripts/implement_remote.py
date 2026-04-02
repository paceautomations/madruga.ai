"""Orchestrate implementation in external repositories via claude -p."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_PROMPT_BYTES = 100_000  # 100KB


# ── Prompt Composition ───────────────────────────────────────────────


def compose_prompt(platform_name: str, epic_slug: str) -> str:
    """Read epic artifacts and compose a prompt for claude -p."""
    epic_dir = REPO_ROOT / "platforms" / platform_name / "epics" / epic_slug

    artifacts = [
        ("pitch.md", "## Epic Pitch", False),
        ("spec.md", "## Feature Specification", True),
        ("plan.md", "## Implementation Plan", True),
        ("tasks.md", "## Tasks", True),
    ]

    parts: list[str] = []
    total_size = 0

    # First pass: read required artifacts and measure size
    for filename, header, required in artifacts:
        filepath = epic_dir / filename
        if not filepath.exists():
            if required:
                raise SystemExit(f"ERROR: Required artifact missing: {filepath}")
            continue

        content = filepath.read_text()
        total_size += len(content.encode())
        parts.append((filename, header, content))

    # Truncate pitch.md if total > MAX_PROMPT_BYTES
    if total_size > MAX_PROMPT_BYTES:
        new_parts = []
        for filename, header, content in parts:
            if filename == "pitch.md":
                # Calculate how much to keep
                excess = total_size - MAX_PROMPT_BYTES
                keep = max(0, len(content.encode()) - excess)
                if keep > 0:
                    content = content[:keep] + "\n\n[... truncated for size ...]"
                else:
                    content = "[pitch.md truncated — too large]"
                log.warning("Truncated pitch.md to fit within %d bytes", MAX_PROMPT_BYTES)
            new_parts.append((filename, header, content))
        parts = new_parts

    # Compose final prompt
    sections = []
    for filename, header, content in parts:
        sections.append(f"{header}\n\n{content}")

    prompt = (
        "You are implementing code for a platform epic. "
        "Follow the tasks in order, marking each as [X] when complete. "
        "The spec, plan, and tasks below describe what to build.\n\n" + "\n\n---\n\n".join(sections)
    )

    return prompt


# ── PR Creation ──────────────────────────────────────────────────────


def create_pr(worktree_path: Path, branch: str, base_branch: str, title: str) -> str:
    """Push branch and create PR in the correct repo. Returns PR URL."""
    if not shutil.which("gh"):
        raise SystemExit("ERROR: gh CLI not found — install via https://cli.github.com/")

    cwd = str(worktree_path)

    # Push branch
    log.info("Pushing branch: %s", branch)
    result = subprocess.run(
        ["git", "push", "-u", "origin", branch],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"ERROR: git push failed:\n{result.stderr}")

    # Create PR
    log.info("Creating PR: %s → %s", branch, base_branch)
    result = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            base_branch,
            "--title",
            title,
            "--body",
            f"Epic implementation via madruga.ai multi-repo pipeline.\n\nBranch: `{branch}`",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Check if PR already exists
        if "already exists" in result.stderr.lower():
            log.info("PR already exists, fetching URL")
            view = subprocess.run(
                ["gh", "pr", "view", "--json", "url", "-q", ".url"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            return view.stdout.strip()
        raise SystemExit(f"ERROR: gh pr create failed:\n{result.stderr}")

    pr_url = result.stdout.strip()
    log.info("PR created: %s", pr_url)
    return pr_url


# ── Orchestrator ─────────────────────────────────────────────────────


def run_implement(
    platform_name: str,
    epic_slug: str,
    timeout: int = 1800,
    dry_run: bool = False,
    create_pr_flag: bool = False,
) -> int:
    """Orchestrate: ensure_repo → worktree → prompt → claude -p."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ensure_repo import _is_self_ref, _load_repo_binding
    from worktree import create_worktree

    binding = _load_repo_binding(platform_name)

    # Resolve working directory
    if _is_self_ref(binding["name"]):
        work_dir = REPO_ROOT
    else:
        work_dir = create_worktree(platform_name, epic_slug)

    # Compose prompt
    prompt = compose_prompt(platform_name, epic_slug)

    if dry_run:
        print(prompt)
        return 0

    # Invoke claude -p
    log.info("Invoking claude -p in %s (timeout: %ds)", work_dir, timeout)
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--cwd", str(work_dir)],
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log.error("claude -p timed out after %ds", timeout)
        return 3

    if result.returncode != 0:
        log.error("claude -p failed with exit code %d", result.returncode)
        return 2

    # Optional PR creation
    if create_pr_flag and not _is_self_ref(binding["name"]):
        branch = f"{binding['epic_branch_prefix']}{epic_slug}"
        pr_url = create_pr(work_dir, branch, binding["base_branch"], f"Epic {epic_slug}")
        print(f"PR: {pr_url}")

    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Implement epic in external repository via claude -p")
    parser.add_argument("--platform", required=True, help="Platform name")
    parser.add_argument("--epic", required=True, help="Epic slug")
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("MADRUGA_IMPLEMENT_TIMEOUT", "1800")),
        help="Timeout in seconds (default: 1800)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print composed prompt without executing",
    )
    parser.add_argument(
        "--create-pr",
        action="store_true",
        help="Push branch and create PR after implementation",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    exit(run_implement(args.platform, args.epic, args.timeout, args.dry_run, args.create_pr))
