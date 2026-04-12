#!/usr/bin/env python3
"""
dag_executor.py — Custom DAG executor for the Madruga AI pipeline.

Reads .specify/pipeline.yaml, performs topological sort, dispatches skills via
claude -p subprocess. Supports human gates (pause/resume), retry with
exponential backoff, circuit breaker, watchdog timeout, and resume
from checkpoint.

Usage:
    python .specify/scripts/dag_executor.py --platform madruga-ai
    python .specify/scripts/dag_executor.py --platform madruga-ai --dry-run
    python .specify/scripts/dag_executor.py --platform madruga-ai --resume
    python .specify/scripts/dag_executor.py --platform madruga-ai --epic 013-dag-executor-bridge
"""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple


import yaml

sys.path.insert(0, str(Path(__file__).parent))

from config import REPO_ROOT, UNFILLED_TEMPLATE_MARKERS  # noqa: E402

# A2-long: keep stdlib logging here — easter._configure_logging installs a
# structlog ProcessorFormatter with foreign_pre_chain, so every record from
# this file flows through the structlog pipeline (contextvars + JSON render)
# without changing call sites. Printf-style calls (``log.info("Foo %s", x)``)
# continue to work because stdlib handles the interpolation before the
# formatter sees the record.
log = logging.getLogger(__name__)


from log_utils import setup_logging as _setup_logging  # noqa: E402


DEFAULT_TIMEOUT = int(os.environ.get("MADRUGA_EXECUTOR_TIMEOUT", "3000"))
RETRY_BACKOFFS = [10, 30, 90]
CB_MAX_FAILURES = 5
CB_RECOVERY_SECONDS = 300
HUMAN_GATES = frozenset({"human", "1-way-door"})
VALID_GATE_MODES = frozenset({"manual", "interactive", "auto"})
DEFAULT_GATE_MODE = os.environ.get("MADRUGA_MODE", "manual")
DISALLOWED_TOOLS = "Bash(git checkout:*) Bash(git branch -:*) Bash(git switch:*)"
# Nodes that need to run in the external code repo (not in REPO_ROOT).
CODE_CWD_NODES = frozenset({"implement", "judge", "qa"})
# Quick mode flag — set by run_pipeline/run_pipeline_async when --quick is active.
# Checked by build_dispatch_cmd to inject quick-fix context into system prompt.
# Uses contextvars for async safety (avoids shared mutable state between coroutines).

_quick_mode_ctx: contextvars.ContextVar[bool] = contextvars.ContextVar("_quick_mode", default=False)
# Upstream reports injected into downstream node prompts (context threading)
REPORT_CONTEXT: dict[str, list[str]] = {
    "judge": ["analyze-post-report.md"],
    "qa": ["analyze-post-report.md", "judge-report.md"],
    "reconcile": ["judge-report.md", "qa-report.md"],
}

# ── Bare-mode dispatch configuration ──────────────────────────────
# Maps node.skill → skill .md file path (relative to REPO_ROOT)
SKILL_FILE_MAP: dict[str, str] = {
    # L1 — platform foundation
    "madruga:platform-new": ".claude/commands/madruga/platform-new.md",
    "madruga:vision": ".claude/commands/madruga/vision.md",
    "madruga:solution-overview": ".claude/commands/madruga/solution-overview.md",
    "madruga:business-process": ".claude/commands/madruga/business-process.md",
    "madruga:tech-research": ".claude/commands/madruga/tech-research.md",
    "madruga:codebase-map": ".claude/commands/madruga/codebase-map.md",
    "madruga:adr": ".claude/commands/madruga/adr.md",
    "madruga:blueprint": ".claude/commands/madruga/blueprint.md",
    "madruga:domain-model": ".claude/commands/madruga/domain-model.md",
    "madruga:containers": ".claude/commands/madruga/containers.md",
    "madruga:context-map": ".claude/commands/madruga/context-map.md",
    "madruga:epic-breakdown": ".claude/commands/madruga/epic-breakdown.md",
    "madruga:roadmap": ".claude/commands/madruga/roadmap.md",
    # L2 — epic cycle
    "madruga:epic-context": ".claude/commands/madruga/epic-context.md",
    "speckit.specify": ".claude/commands/speckit.specify.md",
    "speckit.clarify": ".claude/commands/speckit.clarify.md",
    "speckit.plan": ".claude/commands/speckit.plan.md",
    "speckit.tasks": ".claude/commands/speckit.tasks.md",
    "speckit.analyze": ".claude/commands/speckit.analyze.md",
    "speckit.implement": ".claude/commands/speckit.implement.md",
    "madruga:judge": ".claude/commands/madruga/judge.md",
    "madruga:qa": ".claude/commands/madruga/qa.md",
    "madruga:reconcile": ".claude/commands/madruga/reconcile.md",
}

# Maps node.layer → layer-specific contract file (relative to REPO_ROOT)
LAYER_CONTRACT_MAP: dict[str, str] = {
    "engineering": ".claude/knowledge/pipeline-contract-engineering.md",
    "planning": ".claude/knowledge/pipeline-contract-planning.md",
    "business": ".claude/knowledge/pipeline-contract-business.md",
}

# Allowed tools per node ID. Nodes not in map use DEFAULT_TOOLS.
NODE_TOOLS: dict[str, str] = {
    # L1 — business layer (read + write artifacts)
    "platform-new": "Bash,Read,Write,Glob,Grep",
    "vision": "Bash,Read,Write,Glob,Grep",
    "solution-overview": "Bash,Read,Write,Glob,Grep",
    "business-process": "Bash,Read,Write,Glob,Grep",
    # L1 — research layer
    "tech-research": "Bash,Read,Write,Glob,Grep,WebFetch,WebSearch",
    "codebase-map": "Bash,Read,Write,Glob,Grep",
    # L1 — engineering layer
    "adr": "Bash,Read,Write,Glob,Grep",
    "blueprint": "Bash,Read,Write,Glob,Grep",
    "domain-model": "Bash,Read,Write,Glob,Grep",
    "containers": "Bash,Read,Write,Glob,Grep",
    "context-map": "Bash,Read,Write,Glob,Grep",
    # L1 — planning layer
    "epic-breakdown": "Bash,Read,Write,Glob,Grep",
    "roadmap": "Bash,Read,Write,Glob,Grep",
    # L2 — epic cycle
    "epic-context": "Bash,Read,Write,Glob,Grep",
    "specify": "Bash,Read,Write,Glob,Grep",
    "clarify": "Read,Write,Glob,Grep",
    "plan": "Bash,Read,Write,Glob,Grep",
    "tasks": "Read,Write,Glob,Grep",
    "analyze": "Bash,Read,Glob,Grep",
    "implement": "Bash,Read,Write,Edit,Glob,Grep",
    "analyze-post": "Bash,Read,Glob,Grep",
    "judge": "Bash,Read,Write,Edit,Glob,Grep,Agent",
    "qa": "Bash,Read,Write,Edit,Glob,Grep,Agent",
    "reconcile": "Bash,Read,Write,Edit,Glob,Grep",
}
DEFAULT_TOOLS = "Bash,Read,Write,Edit,Glob,Grep"
IMPLEMENT_TASK_TOOLS = "Bash,Read,Write,Edit,Glob,Grep"

# Effort level per node ID. Nodes not in map use default (high).
NODE_EFFORT: dict[str, str] = {
    "analyze": "medium",
    "analyze-post": "medium",
    "reconcile": "medium",
}

# Minimal CLAUDE.md essentials for --bare mode system prompt
_CONVENTIONS_HEADER = (
    "# Conventions\n"
    "Docs, comments and code in English.\n"
    "Commits with prefixes: feat:, fix:, chore:, merge:.\n"
    "Python: stdlib + pyyaml. SQLite WAL mode. Ruff for lint/format.\n"
    "Platforms at platforms/<name>/. Skills at .claude/commands/.\n"
    "Scripts at .specify/scripts/. Portal at portal/.\n"
)

_AUTONOMOUS_DISPATCH = (
    "# Autonomous Dispatch Mode\n\n"
    "You are running as an autonomous pipeline agent (claude -p). "
    "There is NO human in the loop — stdin is closed.\n\n"
    "CRITICAL OVERRIDES:\n"
    "- Do NOT ask questions or wait for approval. Make reasonable decisions autonomously.\n"
    "- Do NOT pause at gates (human, 1-way-door). Treat ALL gates as auto.\n"
    "- Do NOT present structured questions and wait for answers. Skip Step 1 questions.\n"
    "- Go straight to generating and SAVING the output file.\n"
    "- Use your best judgment for any decision that would normally require human input.\n"
    "- The output file MUST be written to disk before you finish.\n"
)


# ── Claude Output Parsing (Observability) ──────────────────────────


def parse_claude_output(stdout: str) -> dict:
    """Extract tokens/cost from claude -p --output-format json stdout.

    Returns dict with keys: tokens_in, tokens_out, cost_usd, duration_ms,
    cache_read, cache_create. All values default to None on parse failure
    (best-effort, FR-011).

    `tokens_in` is the TOTAL input sent to the model — sum of raw input_tokens
    plus cache reads and cache writes. When prompt caching is active (default),
    `usage.input_tokens` alone is only the uncached delta (often < 100 tokens)
    and severely undercounts the real input. The portal displays this value, so
    we aggregate all three fields here to reflect the actual prompt size.

    `cache_read` and `cache_create` are ALSO exposed separately so Phase 5
    (cache-optimal reorder) can empirically verify prefix cache hit rate.

    If total_cost_usd is missing but token counts are available, estimates
    cost using Sonnet pricing as fallback (see _estimate_cost_usd). Note that
    the estimate will overcount cost in cache-heavy runs (cache reads cost less
    than fresh input), but total_cost_usd from the CLI is preferred and correct.
    """
    result: dict = {
        "tokens_in": None,
        "tokens_out": None,
        "cost_usd": None,
        "duration_ms": None,
        "cache_read": None,
        "cache_create": None,
    }
    if not stdout:
        return result
    try:
        data = json.loads(stdout)
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens")
        cache_read = usage.get("cache_read_input_tokens")
        cache_create = usage.get("cache_creation_input_tokens")
        # Sum all three. Only return None when ALL three are absent, so a run
        # without cache fields (cache_read=None) still reports raw input_tokens.
        if input_tokens is None and cache_read is None and cache_create is None:
            result["tokens_in"] = None
        else:
            result["tokens_in"] = (input_tokens or 0) + (cache_read or 0) + (cache_create or 0)
        result["cache_read"] = cache_read
        result["cache_create"] = cache_create
        result["tokens_out"] = usage.get("output_tokens")
        result["cost_usd"] = data.get("total_cost_usd")
        result["duration_ms"] = data.get("duration_ms")
        # Fallback: estimate cost from token counts if claude didn't provide it
        if result["cost_usd"] is None:
            result["cost_usd"] = _estimate_cost_usd(result["tokens_in"], result["tokens_out"])
    except (ValueError, TypeError, AttributeError):
        log.debug("Failed to parse claude output as JSON")
    return result


def _estimate_cost_usd(tokens_in: int | None, tokens_out: int | None) -> float | None:
    """Estimate cost from token counts using Sonnet pricing (from config).

    Returns None if both token counts are missing (cannot estimate).
    Pricing is configurable via MADRUGA_INPUT_PRICE_PER_TOKEN / MADRUGA_OUTPUT_PRICE_PER_TOKEN env vars.
    """
    from config import SONNET_INPUT_PRICE, SONNET_OUTPUT_PRICE

    if tokens_in is None and tokens_out is None:
        return None
    cost = (tokens_in or 0) * SONNET_INPUT_PRICE + (tokens_out or 0) * SONNET_OUTPUT_PRICE
    return round(cost, 8)


def _check_hallucination(stdout: str) -> bool:
    """Detect likely hallucinated output (zero tool calls heuristic).

    Returns True if the dispatch likely fabricated output without using tools.
    Heuristic: num_turns <= 2 means no tool was invoked (1 user + 1 assistant).
    Error runs (is_error=True) are excluded — they fail for other reasons.

    Fails safe: returns False on malformed JSON, missing fields, or empty input.
    """
    if not stdout:
        return False
    try:
        data = json.loads(stdout)
        if not isinstance(data, dict):
            return False
        num_turns = data.get("num_turns")
        if num_turns is None or not isinstance(num_turns, (int, float)):
            return False
        return num_turns <= 2 and not data.get("is_error", False)
    except (ValueError, TypeError):
        return False


def parse_session_id(stdout: str) -> str | None:
    """Extract session_id from claude -p --output-format json stdout."""
    if not stdout:
        return None
    try:
        return json.loads(stdout).get("session_id")
    except (ValueError, TypeError):
        return None


def _count_output_lines(path: str | None) -> int | None:
    """Count lines in an output artifact file. Returns None if unreadable."""
    if not path:
        return None
    try:
        from pathlib import Path

        p = Path(path)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8", errors="replace").count("\n") + 1
    except OSError:
        pass
    return None


def _run_eval_scoring(
    conn,
    platform_id: str,
    node_id: str,
    run_id: str | None,
    trace_id: str | None,
    epic_id: str | None,
    output_path: str | None,
    metrics: dict,
) -> None:
    """Best-effort eval scoring after a node completes (FR-011).

    Calls eval_scorer.score_node() and persists each score via db.insert_eval_score().
    Never raises — all exceptions are caught and logged.
    """
    try:
        from eval_scorer import score_node
        from db import insert_eval_score

        scores = score_node(conn, platform_id, node_id, run_id, output_path, metrics)
        for s in scores:
            insert_eval_score(
                conn,
                trace_id=trace_id,
                platform_id=s["platform_id"],
                epic_id=epic_id,
                node_id=s["node_id"],
                run_id=s["run_id"],
                dimension=s["dimension"],
                score=s["score"],
                metadata=s.get("metadata"),
            )
        log.debug("Eval scoring completed for node '%s': %d scores", node_id, len(scores))
    except Exception:
        log.debug("Eval scoring failed for node '%s' (best-effort)", node_id, exc_info=True)


# ── Task-by-Task Implement ────────────────────────────────────────


TASK_RE = re.compile(r"^- \[([ Xx])\] (T\d{3})\s+(.+)$")
PHASE_RE = re.compile(r"^## Phase \d+")
FILE_PATH_RE = re.compile(r"`([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)`")
US_TAG_RE = re.compile(r"\[US(\d+)\]")

# Task-scoping heuristics: decide which static docs are relevant to a given
# task by matching its files + description against path/keyword regexes.
# Anchored so ``models/user.py`` matches but ``fetch_models_xyz.py`` does not.
# Word boundaries on description keywords to avoid false positives.
MODEL_PATH_RE = re.compile(r"(^|/)(models|schemas|migrations|db)/", re.IGNORECASE)
API_PATH_RE = re.compile(r"(^|/)(api|routes|handlers|endpoints|webhooks)/", re.IGNORECASE)
MODEL_DESC_RE = re.compile(
    r"\b(model|entity|schema|migration|dataclass|pydantic|table)\b",
    re.IGNORECASE,
)
API_DESC_RE = re.compile(
    r"\b(api|endpoint|webhook|contract|validation|serializer|dto|route)\b",
    re.IGNORECASE,
)
TASK_TIMEOUT = int(os.environ.get("MADRUGA_TASK_TIMEOUT", "600"))
MAX_FILE_CONTEXT_BYTES = 50_000  # 50KB — no doc in our repo exceeds this
MAX_PROMPT_BYTES = 200_000  # 200KB — safety net, not a bottleneck

# Rollback kill-switches for the bare-lite + scoped-context optimizations (ADR-021).
# Default all on; set any to "0" via systemd drop-in to restore legacy behavior
# without a redeploy. See CLAUDE.md "Gotchas" for the rollback procedure.
ENV_BARE_LITE = "MADRUGA_BARE_LITE"
ENV_KILL_IMPLEMENT_CONTEXT = "MADRUGA_KILL_IMPLEMENT_CONTEXT"
ENV_SCOPED_CONTEXT = "MADRUGA_SCOPED_CONTEXT"
ENV_STRICT_SETTINGS = "MADRUGA_STRICT_SETTINGS"  # opt-in (default off)
ENV_CACHE_ORDERED = "MADRUGA_CACHE_ORDERED"  # Phase 5: cache-optimal prefix order

# Byte-identical cue at position 0 of the user prompt under CACHE_ORDERED.
# Must never vary per task — any task-specific bytes here would invalidate
# Claude's prefix cache across the whole epic. Signals to Claude that the
# task card is at the END of the prompt (leverages recency bias).
_CACHE_PREFIX_CUE = "(Implementing one SpecKit task — task card at end of prompt.)\n"

# Slack reserved in the MAX_PROMPT_BYTES budget for the deferred header
# section under CACHE_ORDERED (header is added AFTER the file-inlining loop).
_HEADER_BUDGET_PADDING = 200


def _flag(name: str, default: str = "1") -> bool:
    """Read a MADRUGA_* boolean env var. Default enabled — set to 0 to roll back."""
    return os.environ.get(name, default) == "1"


# Session-resume bounds (postmortem: prosauai/003 T031 — --resume accumulated
# tool outputs across 12 US3 tasks, hit Anthropic 1M context window, crashed).
# Force a fresh session when either threshold trips:
SESSION_RESUME_MAX_TASKS = int(os.environ.get("MADRUGA_RESUME_MAX_TASKS", "8"))
SESSION_RESUME_MAX_TOKENS = int(os.environ.get("MADRUGA_RESUME_MAX_TOKENS", "700000"))

# Stop plowing through tasks after this many consecutive failures in one batch.
# Prevents wasted cycles when the root cause (usually context overflow or API
# outage) affects all remaining tasks identically.
IMPLEMENT_MAX_CONSECUTIVE_FAILURES = int(os.environ.get("MADRUGA_IMPLEMENT_MAX_FAILS", "3"))


@dataclass
class TaskItem:
    id: str
    description: str
    checked: bool
    phase: str
    parallel: bool
    files: list[str] = field(default_factory=list)
    line_number: int = 0
    us_tag: str | None = None


def _parse_tasks_from_text(content: str) -> list[TaskItem]:
    """Parse pre-loaded tasks.md content. Use when the file is already in memory."""
    tasks: list[TaskItem] = []
    current_phase = ""

    for i, line in enumerate(content.splitlines(), start=1):
        if PHASE_RE.match(line):
            current_phase = line.lstrip("#").strip()
            continue

        task_match = TASK_RE.match(line)
        if not task_match:
            continue
        check, task_id, desc = task_match.groups()
        us_match = US_TAG_RE.search(desc)
        tasks.append(
            TaskItem(
                id=task_id,
                description=desc,
                checked=check.lower() == "x",
                phase=current_phase,
                parallel="[P]" in desc,
                files=FILE_PATH_RE.findall(desc),
                line_number=i,
                us_tag=f"US{us_match.group(1)}" if us_match else None,
            )
        )

    return tasks


def parse_tasks(tasks_md_path: Path) -> list[TaskItem]:
    """Parse tasks.md into structured TaskItem list."""
    return _parse_tasks_from_text(tasks_md_path.read_text(encoding="utf-8"))


def mark_task_done(tasks_md_path: Path, task_id: str) -> bool:
    """Mark a task as [X] in tasks.md. Returns True if found and updated."""
    content = tasks_md_path.read_text(encoding="utf-8")
    pattern = f"- [ ] {task_id} "
    replacement = f"- [X] {task_id} "
    if pattern not in content:
        return False
    content = content.replace(pattern, replacement, 1)
    tasks_md_path.write_text(content, encoding="utf-8")
    return True


def append_implement_context(epic_dir: Path, task: TaskItem, metrics: dict | None = None) -> None:
    """Append completed task summary to implement-context.md for next tasks.

    NO-OP by default (MADRUGA_KILL_IMPLEMENT_CONTEXT=1) — ``compose_task_prompt``
    now derives "recent progress" from the authoritative tasks.md checkboxes
    instead, eliminating a redundant 4-12KB per dispatch. Set the env var to 0
    to restore the legacy file-based history for rollback.
    """
    if _flag(ENV_KILL_IMPLEMENT_CONTEXT):
        return
    ctx_path = epic_dir / "implement-context.md"
    entry = f"### {task.id} — DONE\n- {task.description[:200]}\n"
    if task.files:
        entry += f"- Files: {', '.join(task.files)}\n"
    if metrics:
        tokens = f"{metrics.get('tokens_in', '?')}/{metrics.get('tokens_out', '?')}"
        entry += f"- Tokens in/out: {tokens}\n"
    entry += "\n"
    with open(ctx_path, "a", encoding="utf-8") as f:
        f.write(entry)


def _task_needs_data_model(task: TaskItem) -> bool:
    """True if the task touches model-ish files or mentions data model keywords."""
    if any(MODEL_PATH_RE.search(f) for f in task.files):
        return True
    return MODEL_DESC_RE.search(task.description) is not None


def _task_needs_contracts(task: TaskItem) -> bool:
    """True if the task touches API-ish files or mentions contract/endpoint keywords."""
    if any(API_PATH_RE.search(f) for f in task.files):
        return True
    return API_DESC_RE.search(task.description) is not None


def _analyze_report_slice(path: Path, task_id: str) -> str | None:
    """Return only paragraphs of analyze-report.md that mention ``task_id``.

    Empty → returns None (no section added). Whole-file fallback is intentional:
    if analyze-report.md doesn't reference the task, the task is unaffected by
    the pre-implementation consistency check and doesn't need the report at all.
    """
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    paras = content.split("\n\n")
    relevant = [p for p in paras if task_id in p]
    if not relevant:
        return None
    body = "\n\n".join(relevant)
    return f"\n---\n\n## Pre-Implementation Analysis (filtered to {task_id})\n\n{body}"


def _format_context(content: str, header: str) -> str:
    """Format pre-loaded content as a prompt section (truncated at MAX_FILE_CONTEXT_BYTES)."""
    return f"\n---\n\n## {header}\n\n{content[:MAX_FILE_CONTEXT_BYTES]}"


def _read_context(path: Path, header: str) -> str | None:
    """Read a file and format it as a prompt section, or None if missing."""
    if not path.exists():
        return None
    return _format_context(path.read_text(encoding="utf-8"), header)


def compose_task_prompt(
    task: TaskItem,
    epic_dir: Path,
    platform_name: str,
    epic_slug: str,
    resume: bool = False,
) -> str:
    """Compose a focused prompt for a single task.

    If resume=True, skips static docs (plan, spec, etc.) since the resumed
    session already has them — only includes task description, updated
    tasks.md progress, and implement-context.md.

    Emits a structured `prompt_composed` log line with per-section byte counts
    so we can measure context bloat without relying on noisy API metrics.
    """
    output_dir = f"platforms/{platform_name}/epics/{epic_slug}"

    header = "\n".join(
        [
            f"You are implementing task {task.id} for platform '{platform_name}', epic '{epic_slug}'.",
            "",
            "## Task",
            f"- {task.description}",
            "",
            "CRITICAL CONSTRAINTS:",
            f"- ONLY implement this specific task ({task.id}). Do NOT implement other tasks.",
            f"- export SPECIFY_BASE_DIR={output_dir}/",
            f"- You are on branch: epic/{platform_name}/{epic_slug}",
            "- Do NOT create, switch, or checkout any branch.",
            f"- Save ALL output to: {output_dir}/ or project root (for scripts/portal).",
        ]
    )

    # Carry byte_count with each section so the final log line can report
    # per-section sizes without re-encoding. ``total_size`` enforces
    # MAX_PROMPT_BYTES in the file-inlining loop below.
    sections: list[tuple[str, str, int]] = []
    total_size = 0

    def add(name: str, content: str | None) -> None:
        nonlocal total_size
        if content is None:
            return
        size = len(content.encode())
        sections.append((name, content, size))
        total_size += size

    # Read tasks.md exactly once — both the "recent_done" derivation and the
    # "All Tasks" section share this single in-memory copy.
    tasks_md_path = epic_dir / "tasks.md"
    try:
        tasks_text: str | None = tasks_md_path.read_text(encoding="utf-8")
    except OSError:
        tasks_text = None

    def _recent_done_section() -> str | None:
        if tasks_text is None:
            return None
        done_ids = [t.id for t in _parse_tasks_from_text(tasks_text) if t.checked][-5:]
        if not done_ids:
            return None
        return f"\n---\n\n## Recent progress\nLast tasks completed in this cycle: {', '.join(done_ids)}"

    cache_ordered = _flag(ENV_CACHE_ORDERED)
    header_deferred = False

    if cache_ordered:
        # ─── STABLE PREFIX (cacheable across tasks in the same epic) ───
        add("cue", _CACHE_PREFIX_CUE)
        if not resume:
            add("plan", _read_context(epic_dir / "plan.md", "Implementation Plan"))
            add("spec", _read_context(epic_dir / "spec.md", "Specification"))
            # Force-include data_model + contracts under CACHE_ORDERED: the
            # ~20KB "waste" per non-touching task buys a uniform prefix across
            # ALL tasks in the epic, unlocking 1h-TTL cache on tasks 2..N.
            # Math: uniform 64KB prefix × 0.9 (cache_read cost) = 58KB saved
            # vs fragmented 44KB prefix × 0.9 = 40KB. Net +18KB saved per
            # cached task. See ADR-021 Phase 5 addendum for full derivation.
            add("data_model", _read_context(epic_dir / "data-model.md", "Data Model"))
            contracts_dir = epic_dir / "contracts"
            if contracts_dir.is_dir():
                for contract_file in sorted(contracts_dir.glob("*.md")):
                    add(
                        f"contract:{contract_file.name}",
                        _read_context(contract_file, f"Contract: {contract_file.name}"),
                    )

        # ─── VARIABLE SUFFIX (task-specific, not cached) ───
        # tasks.md goes in the suffix because mark_task_done flips [ ]→[X]
        # between dispatches, changing bytes and invalidating cache.
        if tasks_text is not None:
            add("tasks", _format_context(tasks_text, "All Tasks (current progress)"))
        if _flag(ENV_KILL_IMPLEMENT_CONTEXT):
            add("recent_done", _recent_done_section())
        else:
            add("implement_context", _read_context(epic_dir / "implement-context.md", "Prior Tasks Completed"))
        if not resume:
            add("analyze_report", _analyze_report_slice(epic_dir / "analyze-report.md", task.id))
        # Header (task card) added LAST, after the file-inlining loop below.
        header_deferred = True
    else:
        # LEGACY path — byte-identical to pre-Phase-5 output. Any edit here
        # invalidates the rollback guarantee (MADRUGA_CACHE_ORDERED=0).
        add("header", header)
        if _flag(ENV_KILL_IMPLEMENT_CONTEXT):
            add("recent_done", _recent_done_section())
        else:
            add("implement_context", _read_context(epic_dir / "implement-context.md", "Prior Tasks Completed"))
        if tasks_text is not None:
            add("tasks", _format_context(tasks_text, "All Tasks (current progress)"))

        if not resume:
            add("plan", _read_context(epic_dir / "plan.md", "Implementation Plan"))
            add("spec", _read_context(epic_dir / "spec.md", "Specification"))
            scoped = _flag(ENV_SCOPED_CONTEXT)
            if (not scoped) or _task_needs_data_model(task):
                add("data_model", _read_context(epic_dir / "data-model.md", "Data Model"))
            contracts_dir = epic_dir / "contracts"
            if contracts_dir.is_dir() and ((not scoped) or _task_needs_contracts(task)):
                for contract_file in sorted(contracts_dir.glob("*.md")):
                    add(
                        f"contract:{contract_file.name}",
                        _read_context(contract_file, f"Contract: {contract_file.name}"),
                    )
            analyze_path = epic_dir / "analyze-report.md"
            if scoped:
                add("analyze_report", _analyze_report_slice(analyze_path, task.id))
            else:
                add("analyze_report", _read_context(analyze_path, "Pre-Implementation Analysis"))

    # Include referenced files that already exist (so task can build on prior work).
    # Under CACHE_ORDERED the header has not been added yet; reserve its byte
    # count in the budget so we never drop the task card to fit a file.
    header_reserve = len(header.encode()) + _HEADER_BUDGET_PADDING if header_deferred else 0
    dropped_files: list[str] = []
    for file_path in task.files:
        if total_size + header_reserve >= MAX_PROMPT_BYTES:
            dropped_files.append(file_path)
            continue
        full_path = Path(file_path)
        if not full_path.is_absolute():
            full_path = REPO_ROOT / file_path
        if not (full_path.exists() and full_path.is_file()):
            continue
        try:
            content = full_path.read_text(encoding="utf-8")[:MAX_FILE_CONTEXT_BYTES]
        except (OSError, UnicodeDecodeError):
            continue
        add(f"file:{file_path}", f"\n---\n\n## Existing file: {file_path}\n\n```\n{content}\n```")

    if header_deferred:
        add("header", header)

    if dropped_files:
        log.warning(
            "prompt_budget_exceeded task=%s total_bytes=%d limit=%d dropped_files=%s",
            task.id,
            total_size,
            MAX_PROMPT_BYTES,
            dropped_files,
        )

    log.info(
        "prompt_composed task=%s resume=%s cache_ordered=%s total_bytes=%d sections=%s",
        task.id,
        resume,
        cache_ordered,
        total_size,
        {name: size for name, _, size in sections},
    )

    return "\n".join(content for _, content, _ in sections)


async def run_implement_tasks(
    platform_name: str,
    epic_slug: str,
    platform_dir: Path,
    conn,
    cwd: Path,
    trace_id: str | None = None,
    guardrail: str | None = None,
    timeout_per_task: int = TASK_TIMEOUT,
) -> tuple[bool, str | None, str | None]:
    """Dispatch implement as individual tasks instead of one monolithic dispatch.

    Returns (all_succeeded, error_summary_or_None, progress_summary).
    """
    from db import complete_run, insert_run

    tasks_path = platform_dir / "epics" / epic_slug / "tasks.md"
    if not tasks_path.exists():
        return False, f"tasks.md not found at {tasks_path}", None

    tasks = parse_tasks(tasks_path)
    pending = [t for t in tasks if not t.checked]

    if not pending:
        log.info("All %d tasks already checked — nothing to implement", len(tasks))
        return True, None, "all tasks already done"

    log.info("Task-by-task implement: %d pending of %d total", len(pending), len(tasks))
    epic_dir = platform_dir / "epics" / epic_slug

    # Delete stale implement-context.md from previous run (legacy mode only).
    # Under MADRUGA_KILL_IMPLEMENT_CONTEXT=1 (default) the file isn't written,
    # but legacy leftovers may still exist — sweep them opportunistically.
    ctx_path = epic_dir / "implement-context.md"
    if ctx_path.exists():
        ctx_path.unlink()

    breaker = CircuitBreaker(conn=conn, platform_id=platform_name, epic_id=epic_slug)
    completed = 0
    failed: list[tuple[str, str]] = []
    consecutive_failures = 0

    # Track session_id per User Story for --resume between consecutive tasks
    last_us_tag: str | None = None
    last_session_id: str | None = None
    resume_chain_length = 0  # how many tasks reused the current session
    last_task_tokens_in: int | None = None

    for task in pending:
        # Resume session if same US tag as previous successful task AND we're
        # still within the session-resume bounds. These bounds cap how much
        # prior tool-output context a single claude session can accumulate.
        resume_id = None
        resume_blocker: str | None = None
        if task.us_tag and task.us_tag == last_us_tag and last_session_id:
            if resume_chain_length >= SESSION_RESUME_MAX_TASKS:
                resume_blocker = f"chain_len={resume_chain_length}>={SESSION_RESUME_MAX_TASKS}"
            elif last_task_tokens_in and last_task_tokens_in >= SESSION_RESUME_MAX_TOKENS:
                resume_blocker = f"prev_tokens_in={last_task_tokens_in}>={SESSION_RESUME_MAX_TOKENS}"
            else:
                resume_id = last_session_id
                log.info(
                    "Resuming session %s for %s (same %s, chain=%d)",
                    last_session_id[:12],
                    task.id,
                    task.us_tag,
                    resume_chain_length + 1,
                )
        if resume_blocker:
            log.info(
                "Session-resume bound tripped for %s (%s) — forcing fresh session",
                task.id,
                resume_blocker,
            )
            last_session_id = None
            resume_chain_length = 0

        prompt = compose_task_prompt(
            task,
            epic_dir,
            platform_name,
            epic_slug,
            resume=bool(resume_id),
        )
        task_node = Node(
            id=f"implement:{task.id}",
            skill="speckit.implement",
            outputs=[],
            depends=[],
            gate="auto",
            layer="implementation",
            optional=False,
            skip_condition=None,
        )

        log.info("Dispatching task %s (%d/%d): %.80s", task.id, completed + 1, len(pending), task.description)

        # A9: create a `running` row BEFORE dispatch so the portal can show
        # the live sub-task. Previously the row was only inserted after the
        # subprocess returned, causing a multi-minute gap where the portal
        # saw `current_node=null` while claude was actively running. On
        # dispatch completion (success OR failure) we `complete_run` the
        # existing row instead of inserting a second one.
        run_id = insert_run(
            conn,
            platform_name,
            f"implement:{task.id}",
            epic_id=epic_slug,
            trace_id=trace_id,
        )

        success, error, stdout = await dispatch_with_retry_async(
            task_node,
            cwd,
            prompt,
            timeout_per_task,
            breaker,
            guardrail,
            resume_session_id=resume_id,
            platform_name=platform_name,
            abort_check=_make_abort_check(conn, epic_slug),
        )

        if success:
            mark_task_done(tasks_path, task.id)
            completed += 1
            consecutive_failures = 0
            log.info("Task %s completed (%d/%d)", task.id, completed, len(pending))

            # Track session for potential resume on next task
            new_session_id = parse_session_id(stdout) if stdout else None
            if resume_id and new_session_id == last_session_id:
                resume_chain_length += 1
            else:
                resume_chain_length = 1
            last_us_tag = task.us_tag
            last_session_id = new_session_id

            metrics = parse_claude_output(stdout) if stdout else {}
            last_task_tokens_in = metrics.get("tokens_in")
            complete_run(
                conn,
                run_id,
                status="completed",
                tokens_in=metrics.get("tokens_in"),
                tokens_out=metrics.get("tokens_out"),
                cost_usd=metrics.get("cost_usd"),
                duration_ms=metrics.get("duration_ms"),
            )
            append_implement_context(epic_dir, task, metrics)
            _run_eval_scoring(
                conn,
                platform_name,
                f"implement:{task.id}",
                run_id,
                trace_id,
                epic_slug,
                None,
                metrics,
            )
        else:
            # Reset session tracking on failure — next task starts fresh
            last_us_tag = None
            last_session_id = None
            resume_chain_length = 0
            last_task_tokens_in = None
            consecutive_failures += 1
            failed.append((task.id, error or "unknown error"))
            log.error("Task %s failed: %s", task.id, error)
            complete_run(conn, run_id, status="failed", error=error)

            # Early abort: if the same error keeps killing tasks in a row, stop
            # the whole batch. Continuing burns time + cost without fixing the
            # root cause (typically context overflow or API outage).
            if consecutive_failures >= IMPLEMENT_MAX_CONSECUTIVE_FAILURES:
                log.error(
                    "Aborting implement batch: %d consecutive task failures (>=%d). "
                    "Remaining %d tasks skipped. Fix root cause before re-dispatching.",
                    consecutive_failures,
                    IMPLEMENT_MAX_CONSECUTIVE_FAILURES,
                    len(pending) - completed - len(failed),
                )
                break

    summary = f"{completed}/{len(pending)} tasks completed"
    if failed:
        summary += f", {len(failed)} failed: {[f[0] for f in failed]}"

    all_done = len(failed) == 0
    log.info("Implement tasks done: %s", summary)
    return all_done, None if all_done else summary, summary


_SENSITIVE_PATTERNS = frozenset({".env", "credentials", ".key", ".pem", "id_rsa", ".secret", ".password"})


def _is_sensitive_path(filepath: str) -> bool:
    """Return True if filepath matches a sensitive pattern (case-insensitive)."""
    lower = filepath.lower()
    return any(pat in lower for pat in _SENSITIVE_PATTERNS)


def _resolve_code_dir(platform_name: str, epic_slug: str | None) -> Path:
    """Resolve working directory for nodes that read/write source code.

    For self-ref platforms: returns REPO_ROOT.
    For external platforms with an epic: creates/reuses a worktree.
    For L1 (no epic): returns REPO_ROOT (L1 nodes don't touch code).
    """
    if not epic_slug:
        return REPO_ROOT
    from ensure_repo import _is_self_ref, _load_repo_binding
    from worktree import create_worktree

    binding = _load_repo_binding(platform_name)
    if _is_self_ref(binding["name"]):
        return REPO_ROOT
    return create_worktree(platform_name, epic_slug)


def _needs_code_cwd(node: Node) -> bool:
    """Return True if this node should run in the external code repo."""
    return node.id in CODE_CWD_NODES or node.id.startswith("implement:")


def _auto_commit_epic(cwd: str | Path, platform_name: str, epic_slug: str) -> bool:
    """Commit working tree changes to the epic branch after implement.

    Filters out files matching sensitive patterns (e.g. .env, .key, .pem)
    to prevent accidental credential exposure in easter auto-commits.
    """
    try:
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(cwd))
        if not status.stdout.strip():
            log.info("No changes to commit for %s/%s", platform_name, epic_slug)
            return True

        safe_files = []
        for line in status.stdout.splitlines():
            if not line or len(line) < 4:
                continue
            # git status --porcelain format: XY <path> or XY <orig> -> <path>
            filepath = line[3:].strip().strip('"')
            if " -> " in filepath:
                filepath = filepath.split(" -> ", 1)[1].strip('"')
            if _is_sensitive_path(filepath):
                log.warning("Skipping sensitive file from auto-commit: %s", filepath)
                continue
            safe_files.append(filepath)

        if not safe_files:
            log.info("No safe files to commit for %s/%s (all filtered)", platform_name, epic_slug)
            return True

        subprocess.run(["git", "add", "--"] + safe_files, cwd=str(cwd), check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                f"feat: epic {epic_slug} — implement tasks\n\nAuto-committed by easter after implement phase.",
            ],
            cwd=str(cwd),
            check=True,
            capture_output=True,
        )
        log.info("Auto-committed implement changes for %s/%s", platform_name, epic_slug)
        return True
    except subprocess.CalledProcessError as exc:
        log.warning("Auto-commit failed for %s/%s: %s", platform_name, epic_slug, exc.stderr)
        return False


def _transition_epic_status(conn, platform_name: str, epic_slug: str) -> None:
    """Transition epic status (in_progress → shipped) if all required nodes done. Best-effort."""
    try:
        from db import compute_epic_status, get_epics, upsert_epic
        from post_save import _get_required_epic_nodes
        from config import load_pipeline

        required_nodes = _get_required_epic_nodes(platform_name, load_pipeline())
        existing = [e for e in get_epics(conn, platform_name) if e["epic_id"] == epic_slug]
        if existing:
            new_status, delivered_at = compute_epic_status(
                conn, platform_name, epic_slug, required_nodes, existing[0]["status"]
            )
            if new_status != existing[0]["status"]:
                upsert_epic(
                    conn,
                    platform_name,
                    epic_slug,
                    title=existing[0]["title"],
                    status=new_status,
                    delivered_at=delivered_at,
                )
                log.info("Epic '%s' transitioned: %s → %s", epic_slug, existing[0]["status"], new_status)
    except Exception:
        log.debug("Failed to compute epic status — non-blocking")


# ── Data Structures ─────────────────────────────────────────────────


class Node(NamedTuple):
    id: str
    skill: str
    outputs: list[str]
    depends: list[str]
    gate: str
    layer: str
    optional: bool
    skip_condition: str | None


def parse_dag(mode: str = "l1", epic: str | None = None) -> list[Node]:
    """Parse pipeline nodes from .specify/pipeline.yaml.

    Args:
        mode: 'l1' for platform pipeline, 'l2' for epic cycle,
              'quick' for fast lane (specify → implement → judge)
        epic: Epic slug (required for l2/quick mode, used to resolve {epic} templates)

    Returns:
        List of Node namedtuples.
    """
    from config import load_pipeline

    pipeline = load_pipeline()

    if mode == "quick":
        cycle = pipeline.get("quick_cycle", {})
        raw_nodes = cycle.get("nodes", [])
        if not raw_nodes:
            raise SystemExit("ERROR: No quick_cycle.nodes section in pipeline.yaml")
    elif mode == "l2":
        cycle = pipeline.get("epic_cycle", {})
        raw_nodes = cycle.get("nodes", [])
        if not raw_nodes:
            raise SystemExit("ERROR: No epic_cycle.nodes section in pipeline.yaml")
    else:
        raw_nodes = pipeline.get("nodes", [])
        if not raw_nodes:
            raise SystemExit("ERROR: No nodes section in pipeline.yaml")

    nodes = []
    for n in raw_nodes:
        outputs = n.get("outputs", [])
        if n.get("output_pattern"):
            outputs = [n["output_pattern"]]
        # Resolve {epic} template in outputs
        if epic:
            outputs = [o.replace("{epic}", f"epics/{epic}") for o in outputs]
        nodes.append(
            Node(
                id=n["id"],
                skill=n["skill"],
                outputs=outputs,
                depends=n.get("depends", []),
                gate=n.get("gate", "auto"),
                layer=n.get("layer", ""),
                optional=n.get("optional", False),
                skip_condition=n.get("skip_condition"),
            )
        )
    return nodes


def topological_sort(nodes: list[Node]) -> list[Node]:
    """Kahn's algorithm with cycle detection.

    Returns nodes in execution order. Raises SystemExit on cycles or
    unknown dependencies.
    """
    node_map = {n.id: n for n in nodes}
    in_degree: dict[str, int] = {n.id: 0 for n in nodes}
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}

    for n in nodes:
        for dep in n.depends:
            if dep not in node_map:
                raise SystemExit(f"ERROR: Unknown dependency '{dep}' for node '{n.id}'")
            adj[dep].append(n.id)
            in_degree[n.id] += 1

    queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    result: list[Node] = []

    while queue:
        nid = queue.popleft()
        result.append(node_map[nid])
        for child in adj[nid]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(result) != len(nodes):
        remaining = {n.id for n in nodes} - {n.id for n in result}
        raise SystemExit(f"ERROR: Cycle detected in DAG involving: {remaining}")

    return result


# ── Auto-Escalate Gate ──────────────────────────────────────────────


def check_auto_escalate(node: Node, platform_dir: Path, epic_slug: str | None) -> bool | None:
    """Parse node output report frontmatter to decide auto-escalate gate.

    Returns True=pass (auto-proceed), False=fail (escalate), None=can't determine.
    Only applies to nodes with gate='auto-escalate' in an epic context.
    """
    if node.gate != "auto-escalate" or not epic_slug:
        return None
    for output in node.outputs:
        resolved = output.replace("{epic}", f"epics/{epic_slug}")
        report_path = platform_dir / resolved
        if not report_path.exists():
            continue
        content = report_path.read_text(encoding="utf-8")[:2000]
        if not content.startswith("---"):
            continue
        end = content.find("---", 3)
        if end < 0:
            continue
        try:
            fm = yaml.safe_load(content[3:end])
            score = fm.get("score", 0)
            verdict = str(fm.get("verdict", "")).lower()
            if verdict == "pass" and isinstance(score, (int, float)) and score >= 80:
                return True
            return False
        except (yaml.YAMLError, AttributeError, TypeError):
            continue
    return None


def _handle_auto_escalate(
    node: Node,
    platform_dir: Path,
    epic_slug: str | None,
    gmode: str,
    conn,
    platform_name: str,
    trace_id: str | None,
) -> bool:
    """Handle auto-escalate gate after node dispatch. Returns True if pipeline should stop."""
    from db import insert_run

    escalate = check_auto_escalate(node, platform_dir, epic_slug)
    if escalate is False:
        if gmode == "auto":
            log.warning("Auto-escalate: '%s' FAILED (score < 80 after fix) — mode=auto, proceeding to qa", node.id)
        elif gmode == "interactive":
            print(f"\n>>> Auto-escalate: '{node.id}' FAILED quality gate (score < 80)")
            report_hint = node.outputs[0] if node.outputs else "report.md"
            print(f"    Review: platforms/{platform_name}/epics/{epic_slug}/{report_hint}")
            try:
                answer = input("    Continue to QA for healing? [y/N] ").strip().lower()
            except EOFError:
                answer = "n"
            if answer != "y":
                return True
        else:
            # manual: pause for external approval
            esc_run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug, trace_id=trace_id)
            conn.execute(
                "UPDATE pipeline_runs SET gate_status='waiting_approval' WHERE run_id=?",
                (esc_run_id,),
            )
            conn.commit()
            log.warning("Auto-escalate: '%s' FAILED, awaiting human approval", node.id)
            return True
    elif escalate is True:
        log.info("Auto-escalate: '%s' PASSED (score >= 80)", node.id)
    return False


# ── Circuit Breaker ──────────────────────────────────────────────────


class CircuitBreaker:
    """Simple circuit breaker: closed → open (after max_failures) → half-open (after recovery).

    Optionally seeds from DB on init: counts recent consecutive failures
    to avoid retry storms after process restart.
    """

    def __init__(
        self,
        max_failures: int = CB_MAX_FAILURES,
        recovery_seconds: int = CB_RECOVERY_SECONDS,
        conn=None,
        platform_id: str | None = None,
        epic_id: str | None = None,
    ):
        self.max_failures = max_failures
        self.recovery_seconds = recovery_seconds
        self.failure_count = 0
        self.last_failure_at: float = 0
        self.state = "closed"  # closed, open, half-open
        if conn and platform_id:
            self._seed_from_db(conn, platform_id, epic_id)

    def check(self) -> bool:
        """Return True if dispatch is allowed."""
        if self.state == "closed":
            return True
        if self.state == "open":
            elapsed = time.time() - self.last_failure_at
            if elapsed >= self.recovery_seconds:
                self.state = "half-open"
                log.info("Circuit breaker HALF-OPEN — attempting recovery")
                return True
            log.warning("Circuit breaker OPEN — %ds remaining", int(self.recovery_seconds - elapsed))
            return False
        # half-open: allow one attempt
        return True

    def record_success(self) -> None:
        if self.state == "half-open":
            log.info("Circuit breaker CLOSED — recovery successful")
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_at = time.time()
        if self.state == "half-open":
            self.state = "open"
            log.warning("Circuit breaker re-OPENED after half-open failure")
        elif self.failure_count >= self.max_failures:
            self.state = "open"
            log.warning(
                "Circuit breaker OPEN — %d consecutive failures, suspending for %ds",
                self.failure_count,
                self.recovery_seconds,
            )

    def _seed_from_db(self, conn, platform_id: str, epic_id: str | None) -> None:
        """Count recent consecutive failures from DB to persist state across restarts.

        Excludes rows whose error is itself ``circuit breaker OPEN`` — those are
        not new failures, they're the breaker echoing its own state. Counting them
        causes the CB to stay permanently OPEN across epic re-dispatches (see
        easter-tracking postmortem on T031-T046 cascade).
        """
        import sqlite3

        try:
            epic_filter = "AND epic_id=?" if epic_id else "AND epic_id IS NULL"
            params = (platform_id, epic_id) if epic_id else (platform_id,)
            rows = conn.execute(
                "SELECT status, error FROM pipeline_runs "
                f"WHERE platform_id=? {epic_filter} "
                "  AND (error IS NULL OR error NOT LIKE '%circuit breaker%') "
                "ORDER BY started_at DESC LIMIT ?",
                (*params, self.max_failures),
            ).fetchall()
            consecutive = 0
            for status, _error in rows:
                if status == "failed":
                    consecutive += 1
                else:
                    break
            if consecutive >= self.max_failures:
                self.failure_count = consecutive
                self.state = "open"
                self.last_failure_at = time.time()
                log.warning("Circuit breaker seeded OPEN from DB — %d consecutive failures", consecutive)
            elif consecutive > 0:
                self.failure_count = consecutive
                log.info("Circuit breaker seeded with %d prior failures", consecutive)
        except (sqlite3.Error, TypeError):
            log.debug("Circuit breaker DB seed failed — starting fresh")


# ── Dispatch ─────────────────────────────────────────────────────────


def _dispatch_env() -> dict[str, str]:
    """Return environ with MADRUGA_DISPATCH=1 so user hooks skip in subprocesses."""
    env = os.environ.copy()
    env["MADRUGA_DISPATCH"] = "1"
    return env


def dispatch_node(
    node: Node,
    cwd: Path,
    prompt: str,
    timeout: int = DEFAULT_TIMEOUT,
    guardrail: str | None = None,
    platform_name: str = "",
) -> tuple[bool, str | None, str | None]:
    """Dispatch a skill via claude -p subprocess.

    Returns (success, error_message, stdout_content).
    """
    if not shutil.which("claude"):
        return False, "claude CLI not found in PATH", None

    cmd = build_dispatch_cmd(node, prompt, platform_name, guardrail)
    log.info("Dispatching node '%s' (skill: %s, timeout: %ds)", node.id, node.skill, timeout)
    log.debug("Command: %s", " ".join(cmd[:4]) + " ...")

    try:
        # Pipe prompt via stdin — see dispatch_node_async for the rationale
        # (Linux MAX_ARG_STRLEN=128KB per-arg limit on execve).
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
            env=_dispatch_env(),
        )
        if result.returncode != 0:
            error = _extract_claude_error(
                result.stdout or "",
                result.stderr.encode() if result.stderr else None,
                result.returncode,
            )
            log.error("Node '%s' failed: %s", node.id, error)
            return False, error, result.stdout
        return True, None, result.stdout
    except subprocess.TimeoutExpired as exc:
        # ``subprocess.run(capture_output=True)`` attaches the partial stdout
        # to the ``TimeoutExpired`` exception — persist it alongside the async
        # variant for symmetric diagnostics.
        partial_bytes = exc.stdout or b""
        partial = partial_bytes.decode(errors="replace") if isinstance(partial_bytes, bytes) else str(partial_bytes)
        try:
            diag_dir = REPO_ROOT / ".pipeline" / "timeout-diagnostics"
            diag_dir.mkdir(parents=True, exist_ok=True)
            fname = f"{node.id.replace(':', '_')}_{int(time.time())}.stdout"
            (diag_dir / fname).write_text(partial[:200_000], encoding="utf-8")
            log.error(
                "Node '%s': timeout after %ds — partial stdout (%d bytes) saved to %s",
                node.id,
                timeout,
                len(partial),
                diag_dir / fname,
            )
        except Exception as diag_exc:  # noqa: BLE001 — diagnostic best-effort
            log.warning("Could not persist timeout diagnostic: %s", diag_exc)
            log.error("Node '%s': timeout after %ds", node.id, timeout)
        return False, f"timeout after {timeout}s", partial or None


def verify_outputs(node: Node, platform_dir: Path) -> tuple[bool, str | None]:
    """Check that all expected output files exist and are not unfilled templates."""
    for output in node.outputs:
        # Skip glob patterns (e.g., "epics/*/pitch.md")
        if "*" in output:
            continue
        path = platform_dir / output
        if not path.exists():
            error = f"output not found: {output}"
            log.error("Node '%s': %s", node.id, error)
            return False, error
        # Detect unfilled template placeholders
        try:
            with path.open(encoding="utf-8", errors="replace") as f:
                head = f.read(2000)
            if any(m in head for m in UNFILLED_TEMPLATE_MARKERS):
                error = f"output is unfilled template: {output}"
                log.error("Node '%s': %s", node.id, error)
                return False, error
        except OSError:
            pass
    return True, None


def dispatch_with_retry(
    node: Node,
    cwd: Path,
    prompt: str,
    timeout: int,
    breaker: CircuitBreaker,
    guardrail: str | None = None,
    platform_name: str = "",
) -> tuple[bool, str | None, str | None]:
    """Dispatch with retry (3x exponential backoff) and circuit breaker.

    Returns (success, error_message, stdout_content).
    """
    if not breaker.check():
        return False, "circuit breaker OPEN", None

    last_error = None
    last_stdout = None
    for attempt, backoff in enumerate([0] + RETRY_BACKOFFS, 1):
        if backoff > 0:
            jittered = backoff + random.uniform(0, backoff * 0.3)
            log.info("Retry %d/%d for node '%s' after %.1fs", attempt - 1, len(RETRY_BACKOFFS), node.id, jittered)
            time.sleep(jittered)

        success, error, stdout = dispatch_node(node, cwd, prompt, timeout, guardrail, platform_name)
        if success:
            breaker.record_success()
            return True, None, stdout
        last_error = error
        last_stdout = stdout

    breaker.record_failure()
    return False, last_error, last_stdout


# ── Async Dispatch (for easter integration) ─────────────────────────


# A8: track all live claude subprocesses so lifespan shutdown can propagate
# SIGTERM down the tree. Without this, systemd SIGTERM only reaches the uvicorn
# parent; the claude subprocesses keep running until TimeoutStopSec expires
# and systemd SIGKILLs the whole control group (with orphaned shell/node
# children). Registered on dispatch, discarded on completion.
_active_subprocesses: "set[asyncio.subprocess.Process]" = set()


async def terminate_active_subprocesses(graceful_timeout: float = 5.0) -> int:
    """Signal every live dispatch subprocess to exit cleanly.

    Called by easter.lifespan during shutdown. Sends SIGTERM first, waits up
    to ``graceful_timeout`` seconds for the children to exit, then escalates
    to SIGKILL on survivors. Returns the number of subprocesses that received
    a signal (for logging).
    """
    import signal as _signal

    if not _active_subprocesses:
        return 0

    snapshot = list(_active_subprocesses)
    signalled = 0
    for proc in snapshot:
        try:
            # send_signal vs terminate: on Unix they're equivalent for
            # SIGTERM, but send_signal is explicit about the signal number.
            proc.send_signal(_signal.SIGTERM)
            signalled += 1
        except (ProcessLookupError, AttributeError):
            # Process already exited between snapshot and signal — fine.
            _active_subprocesses.discard(proc)

    if signalled == 0:
        return 0

    # Wait for graceful exit, bounded by `graceful_timeout`.
    deadline = asyncio.get_event_loop().time() + graceful_timeout
    while _active_subprocesses:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        done_snapshot = [p for p in list(_active_subprocesses) if p.returncode is not None]
        for proc in done_snapshot:
            _active_subprocesses.discard(proc)
        if not _active_subprocesses:
            break
        await asyncio.sleep(min(0.2, remaining))

    # Escalate to SIGKILL on any survivors.
    for proc in list(_active_subprocesses):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        finally:
            _active_subprocesses.discard(proc)

    return signalled


def _extract_claude_error(stdout_text: str, stderr: bytes | None, returncode: int) -> str:
    """Extract the real error from a failed claude -p --output-format json invocation.

    Claude CLI's JSON output format emits errors to stdout (not stderr):
      {"is_error": true, "subtype": "error_during_execution", "result": "<msg>", ...}

    On non-zero exit with empty stderr (the common failure mode for context-window
    overflows and API errors), we parse stdout for the structured error. Falls back
    to stderr when stdout isn't JSON.
    """
    # First try: parse stdout as JSON and extract structured error fields.
    if stdout_text:
        # Claude CLI may emit multiple JSON objects (one per turn); the last one
        # carries the final result. Scan from the end for a {"is_error": true, ...}.
        for line in reversed(stdout_text.strip().splitlines()):
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("is_error") or obj.get("type") == "error":
                subtype = obj.get("subtype") or obj.get("error_type") or "unknown"
                result = obj.get("result") or obj.get("error") or obj.get("message") or ""
                detail = f"{subtype}: {result}" if result else subtype
                return f"claude_error[{detail}][:500]"[:500]
        # Whole-stdout fallback (non-jsonl formats)
        try:
            obj = json.loads(stdout_text)
            if obj.get("is_error"):
                subtype = obj.get("subtype", "unknown")
                result = obj.get("result", "")
                return f"claude_error[{subtype}: {result}]"[:500]
        except (json.JSONDecodeError, AttributeError):
            pass
    # Second try: stderr
    if stderr:
        decoded = stderr.decode(errors="replace").strip()
        if decoded:
            return decoded[:500]
    # Last resort: exit code + hint that stdout was empty/opaque
    stdout_hint = f" stdout_len={len(stdout_text)}" if stdout_text else " stdout_empty"
    return f"exitcode {returncode}{stdout_hint}"


async def dispatch_node_async(
    node: Node,
    cwd: str | Path,
    prompt: str,
    timeout: int = DEFAULT_TIMEOUT,
    guardrail: str | None = None,
    resume_session_id: str | None = None,
    platform_name: str = "",
) -> tuple[bool, str | None, str | None]:
    """Async version of dispatch_node using asyncio.create_subprocess_exec.

    If resume_session_id is provided, resumes that session instead of starting fresh.
    Returns (success, error_message, stdout_content).
    """
    if not shutil.which("claude"):
        return False, "claude CLI not found in PATH", None

    cmd = build_dispatch_cmd(node, prompt, platform_name, guardrail, resume_session_id)
    log.info(
        "Dispatching node '%s' async (skill: %s, timeout: %ds%s)",
        node.id,
        node.skill,
        timeout,
        f", resume={resume_session_id[:12]}" if resume_session_id else "",
    )

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
        env=_dispatch_env(),
    )
    # A8: register so shutdown can terminate us
    _active_subprocesses.add(process)
    # Streaming buffers so we can inspect partial output on timeout. Replaces
    # the prior ``process.communicate()`` call — communicate() only yields
    # stdout/stderr AFTER the child closes its pipes, which means on timeout
    # asyncio.wait_for cancels the task and the partial output is lost. With
    # manual drainers we keep a live copy in-process.
    # See easter-tracking.md (epic prosauai/004-router-mece) for the "silent
    # hang in claude -p stream" pattern that motivated this.
    stdout_buf = bytearray()
    stderr_buf = bytearray()

    async def _drain(stream: asyncio.StreamReader | None, buf: bytearray) -> None:
        if stream is None:
            return
        while True:
            chunk = await stream.read(8192)
            # Guard: EOF (empty) OR non-bytes (broken mock that would otherwise
            # infinite-loop and blow up RAM via AsyncMock.call_args_list). Real
            # asyncio.StreamReader always returns bytes, so this is a pure
            # test-safety net with zero cost in production.
            if not chunk or not isinstance(chunk, (bytes, bytearray)):
                return
            buf.extend(chunk)

    try:
        # Pipe the (potentially very large) prompt via stdin to avoid the Linux
        # ``MAX_ARG_STRLEN=128KB`` per-argument limit on execve. Postmortem:
        # T042's prompt was ~155KB (accumulated implement-context.md + plan +
        # spec + data-model + contracts) and crashed with ``OSError [Errno 7]
        # Argument list too long`` before claude even started.
        if prompt and process.stdin is not None:
            process.stdin.write(prompt.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _drain(process.stdout, stdout_buf),
                    _drain(process.stderr, stderr_buf),
                    process.wait(),
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            partial = stdout_buf.decode(errors="replace")
            # Persist partial stdout to disk so we can diagnose silent hangs
            # without capturing it from journalctl (claude -p JSON mode writes
            # the whole response at the end — partial output is the only clue
            # about whether the agent was mid-tool-use or mid-auto-review).
            try:
                diag_dir = REPO_ROOT / ".pipeline" / "timeout-diagnostics"
                diag_dir.mkdir(parents=True, exist_ok=True)
                fname = f"{node.id.replace(':', '_')}_{int(time.time())}.stdout"
                (diag_dir / fname).write_text(partial[:200_000], encoding="utf-8")
                log.error(
                    "Node '%s': timeout after %ds — partial stdout (%d bytes) saved to %s",
                    node.id,
                    timeout,
                    len(partial),
                    diag_dir / fname,
                )
            except Exception as exc:  # noqa: BLE001 — diagnostic best-effort
                log.warning("Could not persist timeout diagnostic: %s", exc)
                log.error("Node '%s': timeout after %ds", node.id, timeout)
            return False, f"timeout after {timeout}s", partial or None

        stdout_text = stdout_buf.decode(errors="replace")
        if process.returncode != 0:
            # Claude CLI with --output-format json often fails silently (empty stderr,
            # error details embedded in stdout JSON). Parse stdout to surface the real
            # cause (e.g. context_length_exceeded, rate_limit, max_turns).
            error = _extract_claude_error(stdout_text, bytes(stderr_buf), process.returncode)
            log.error("Node '%s' failed: %s", node.id, error)
            return False, error, stdout_text
        return True, None, stdout_text
    finally:
        _active_subprocesses.discard(process)


def _make_abort_check(conn, epic_slug: str | None):
    """Create a callable that returns True if the epic is no longer in_progress."""
    import sqlite3

    if not conn or not epic_slug:
        return None

    def check() -> bool:
        try:
            row = conn.execute("SELECT status FROM epics WHERE epic_id=?", (epic_slug,)).fetchone()
            # Only abort on explicit cancellation/block — NOT on natural completion
            # (shipped/completed are valid transitions from the pipeline itself)
            return row is not None and row[0] in ("cancelled", "blocked")
        except sqlite3.Error:
            return False

    return check


async def dispatch_with_retry_async(
    node: Node,
    cwd: str | Path,
    prompt: str,
    timeout: int,
    breaker: CircuitBreaker,
    guardrail: str | None = None,
    resume_session_id: str | None = None,
    platform_name: str = "",
    abort_check: "object | None" = None,
) -> tuple[bool, str | None, str | None]:
    """Async version of dispatch_with_retry using asyncio.sleep.

    Returns (success, error_message, stdout_content).
    """
    if not breaker.check():
        return False, "circuit breaker OPEN", None

    last_error = None
    last_stdout = None
    for attempt, backoff in enumerate([0] + RETRY_BACKOFFS, 1):
        if backoff > 0:
            # F2: Check if epic was cancelled/blocked before retrying
            if abort_check and abort_check():
                log.info("Aborting retries for '%s' — epic status changed", node.id)
                return False, "epic_status_changed", None
            jittered = backoff + random.uniform(0, backoff * 0.3)
            log.info("Retry %d/%d for node '%s' after %.1fs", attempt - 1, len(RETRY_BACKOFFS), node.id, jittered)
            await asyncio.sleep(jittered)
            # Don't resume on retries — start fresh to avoid corrupted state
            resume_session_id = None

        success, error, stdout = await dispatch_node_async(
            node,
            cwd,
            prompt,
            timeout,
            guardrail,
            resume_session_id,
            platform_name,
        )
        if success:
            breaker.record_success()
            return True, None, stdout
        last_error = error
        last_stdout = stdout

    breaker.record_failure()
    return False, last_error, last_stdout


def _resolve_trace_id(
    conn, platform_name: str, epic_slug: str | None, resume: bool, mode: str, total_nodes: int
) -> str | None:
    """Find an existing running trace on resume, or create a new one. Best-effort."""
    from db import create_trace

    try:
        if resume:
            if epic_slug:
                row = conn.execute(
                    "SELECT trace_id FROM traces WHERE platform_id=? AND epic_id=? AND status='running' "
                    "ORDER BY started_at DESC LIMIT 1",
                    (platform_name, epic_slug),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT trace_id FROM traces WHERE platform_id=? AND epic_id IS NULL AND status='running' "
                    "ORDER BY started_at DESC LIMIT 1",
                    (platform_name,),
                ).fetchone()
            if row:
                log.info("Reusing existing trace: %s", row[0])
                return row[0]
        return create_trace(conn, platform_name, epic_id=epic_slug, mode=mode, total_nodes=total_nodes)
    except Exception:
        log.debug("Failed to create/reuse trace — continuing without tracing")
        return None


# ── Async Pipeline (for easter) ─────────────────────────────────────


async def run_pipeline_async(
    platform_name: str,
    epic_slug: str | None = None,
    resume: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    semaphore: "asyncio.Semaphore | None" = None,
    conn: object | None = None,
    gate_mode: str | None = None,
    quick: bool = False,
) -> int:
    """Async version of run_pipeline for easter integration.

    gate_mode: 'manual' (default) — pause at human gates, wait for CLI/Telegram approval.
               'interactive' — print summary, wait for y/n on stdin.
               'auto' — auto-approve all human gates, run pipeline end-to-end.

    Returns exit code: 0=success or paused at gate, 1=failure.
    Human gates are written to DB and the function returns (easter continues).
    If conn is provided, it is reused (not closed). Otherwise a new one is created.
    """
    _quick_mode_ctx.set(quick)

    gmode = gate_mode or DEFAULT_GATE_MODE
    if gmode not in VALID_GATE_MODES:
        log.error("Invalid gate_mode '%s'. Valid: %s", gmode, VALID_GATE_MODES)
        return 1
    log.info("Gate mode: %s", gmode)

    platform_dir = REPO_ROOT / "platforms" / platform_name

    mode = "quick" if quick else ("l2" if epic_slug else "l1")
    nodes = parse_dag(mode=mode, epic=epic_slug)
    ordered = topological_sort(nodes)

    log.info("Pipeline async %s — %d nodes in %s mode", platform_name, len(ordered), mode.upper())

    from db import (
        complete_run,
        complete_trace,
        get_conn,
        get_pending_gates,
        get_resumable_nodes,
        insert_run,
        upsert_epic_node,
        upsert_pipeline_node,
    )

    owns_conn = conn is None
    if owns_conn:
        conn = get_conn()
    completed_nodes: set[str] = set()

    if resume:
        # Cleanup stale 'running' runs from previous crashes/failures.
        # Preserve only runs with gate_status='waiting_approval' — these are
        # real gate checkpoints awaiting human response.
        # If the node's artifact was already saved (epic_nodes.status='done'),
        # mark the run as 'completed' instead of 'cancelled'.
        epic_filter = "AND epic_id=?" if epic_slug else "AND epic_id IS NULL"
        params_base = (platform_name, epic_slug) if epic_slug else (platform_name,)
        stale_runs = conn.execute(
            "SELECT run_id, node_id FROM pipeline_runs "
            f"WHERE platform_id=? {epic_filter} AND status='running' "
            "AND (gate_status IS NULL OR gate_status != 'waiting_approval')",
            params_base,
        ).fetchall()
        if stale_runs:
            status_table = "epic_nodes" if epic_slug else "pipeline_nodes"
            done_nodes = {
                r[0]
                for r in conn.execute(
                    f"SELECT node_id FROM {status_table} WHERE platform_id=? {epic_filter} AND status='done'",
                    params_base,
                ).fetchall()
            }
            for run_id, node_id in stale_runs:
                final = "completed" if node_id in done_nodes else "cancelled"
                conn.execute(
                    "UPDATE pipeline_runs SET status=?, completed_at=datetime('now') WHERE run_id=?",
                    (final, run_id),
                )
        conn.commit()

        completed_nodes = get_resumable_nodes(conn, platform_name, epic_slug)
        pending = get_pending_gates(conn, platform_name)
        if epic_slug:
            pending = [g for g in pending if g.get("epic_id") == epic_slug]
        for gate in pending:
            if gate["node_id"] not in completed_nodes:
                log.info("Gate pendente para '%s' — easter aguardara aprovacao", gate["node_id"])
                if owns_conn:
                    conn.close()
                return 0
        log.info("Resume async: %d nodes already completed", len(completed_nodes))

    trace_id = _resolve_trace_id(conn, platform_name, epic_slug, resume, mode, len(ordered))

    breaker = CircuitBreaker(conn=conn, platform_id=platform_name, epic_id=epic_slug)
    cwd = REPO_ROOT
    code_dir = _resolve_code_dir(platform_name, epic_slug)
    if code_dir != REPO_ROOT:
        log.info("External repo code_dir: %s", code_dir)

    for node in ordered:
        if node.id in completed_nodes:
            log.info("Skipping completed node: %s", node.id)
            continue

        if node.optional and node.skip_condition:
            log.info("Skipping optional node: %s (%s)", node.id, node.skip_condition)
            if epic_slug:
                upsert_epic_node(conn, platform_name, epic_slug, node.id, status="skipped")
            else:
                upsert_pipeline_node(conn, platform_name, node.id, status="skipped")
            completed_nodes.add(node.id)
            continue

        node_deps = set(node.depends)
        if not node_deps.issubset(completed_nodes):
            missing = node_deps - completed_nodes
            log.warning("Node '%s' blocked — missing deps: %s", node.id, missing)
            continue

        # Human gate handling based on gmode
        if node.gate in HUMAN_GATES:
            if gmode == "auto":
                log.info("Auto-approving gate '%s' (mode=auto)", node.id)
            elif gmode == "interactive":
                print(f"\n>>> Gate '{node.id}' (type: {node.gate}, skill: {node.skill})")
                print(f"    Next: dispatch '{node.skill}' for epic '{epic_slug or 'L1'}'")
                try:
                    answer = input("    Approve? [y/N] ").strip().lower()
                except EOFError:
                    answer = "n"
                if answer != "y":
                    log.info("Gate '%s' rejected by user (interactive mode)", node.id)
                    if owns_conn:
                        conn.close()
                    return 0
                log.info("Gate '%s' approved by user (interactive mode)", node.id)
            else:
                # gmode == "manual": check DB for prior approval, or pause
                approved_run = conn.execute(
                    "SELECT run_id FROM pipeline_runs "
                    "WHERE platform_id=? AND node_id=? AND gate_status='approved' "
                    "AND (epic_id=? OR (epic_id IS NULL AND ? IS NULL))",
                    (platform_name, node.id, epic_slug, epic_slug),
                ).fetchone()
                if not approved_run:
                    run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug)
                    conn.execute(
                        "UPDATE pipeline_runs SET gate_status='waiting_approval' WHERE run_id=?",
                        (run_id,),
                    )
                    conn.commit()
                    log.info("Gate '%s' aguardando aprovacao (run_id=%s)", node.id, run_id)
                    if owns_conn:
                        conn.close()
                    return 0
                log.info("Gate '%s' approved — dispatching", node.id)

        # Task-by-task dispatch for speckit.implement — handles its own
        # run recording, verify, and checkpoint. Skip normal post-dispatch.
        if node.skill == "speckit.implement" and epic_slug:
            output_dir = f"platforms/{platform_name}/epics/{epic_slug}"
            guardrail = (
                f"MANDATORY: You are on branch epic/{platform_name}/{epic_slug}. "
                f"Do NOT create or switch branches. "
                f"Set SPECIFY_BASE_DIR={output_dir}/ for any SpecKit scripts."
            )
            success, error, stdout = await run_implement_tasks(
                platform_name,
                epic_slug,
                platform_dir,
                conn,
                code_dir,
                trace_id=trace_id,
                guardrail=guardrail,
                timeout_per_task=TASK_TIMEOUT,
            )
            if not success:
                log.error("Implement tasks failed: %s", error)
                try:
                    if trace_id:
                        complete_trace(conn, trace_id, status="failed")
                except Exception:
                    log.debug("Failed to complete trace on implement failure")
                if owns_conn:
                    conn.close()
                return 1
            # Create marker file for verify_outputs
            marker = platform_dir / "epics" / epic_slug / "implement-report.md"
            if not marker.exists():
                marker.write_text(f"# Implementation Report\n\n{stdout or 'Tasks completed.'}\n")
            upsert_epic_node(conn, platform_name, epic_slug, node.id, status="done")
            completed_nodes.add(node.id)
            log.info("Node '%s' completed successfully (task-by-task)", node.id)
            # F9: Auto-commit implement changes to epic branch
            _auto_commit_epic(code_dir, platform_name, epic_slug)
            continue

        else:
            prompt, guardrail = compose_skill_prompt(platform_name, node, platform_dir, epic_slug)
            abort_fn = _make_abort_check(conn, epic_slug)
            # Insert "running" record before dispatch so it appears in real-time
            run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug, trace_id=trace_id)
            node_cwd = code_dir if _needs_code_cwd(node) else cwd
            if semaphore:
                async with semaphore:
                    success, error, stdout = await dispatch_with_retry_async(
                        node,
                        node_cwd,
                        prompt,
                        timeout,
                        breaker,
                        guardrail,
                        platform_name=platform_name,
                        abort_check=abort_fn,
                    )
            else:
                success, error, stdout = await dispatch_with_retry_async(
                    node,
                    node_cwd,
                    prompt,
                    timeout,
                    breaker,
                    guardrail,
                    platform_name=platform_name,
                    abort_check=abort_fn,
                )

        # Truncate stdout for dispatch_log (debug aid, max 4KB)
        _dispatch_log = stdout[:4096] if stdout else None

        if not success:
            complete_run(conn, run_id, status="failed", error=error, dispatch_log=_dispatch_log)
            log.error("Node '%s' failed after retries: %s", node.id, error)
            try:
                if trace_id:
                    complete_trace(conn, trace_id, status="failed")
            except Exception:
                log.debug("Failed to complete trace on failure")
            if owns_conn:
                conn.close()
            return 1

        # Layer 4: verify branch didn't change
        if epic_slug:
            branch_check = subprocess.run(
                ["git", "branch", "--show-current"], capture_output=True, text=True, cwd=str(node_cwd)
            )
            expected_branch = f"epic/{platform_name}/{epic_slug}"
            actual_branch = branch_check.stdout.strip()
            if actual_branch != expected_branch:
                subprocess.run(["git", "checkout", expected_branch], cwd=str(node_cwd), capture_output=True)
                log.error("claude -p changed branch to '%s', reverted to '%s'", actual_branch, expected_branch)

        # Layer 5: save stdout as missing output for read-only skills
        # Extract actual content from claude JSON (not raw metadata)
        if stdout:
            save_content = stdout
            try:
                data = json.loads(stdout)
                if isinstance(data, dict) and data.get("type") == "result":
                    save_content = data.get("result", "")
            except (ValueError, TypeError):
                pass
            if save_content:
                for output_path in node.outputs:
                    resolved = output_path.replace("{epic}", f"epics/{epic_slug}") if epic_slug else output_path
                    full_path = platform_dir / resolved
                    if not full_path.exists():
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        full_path.write_text(save_content)
                        log.info("Saved stdout as missing output: %s", resolved)

        ok, verify_error = verify_outputs(node, platform_dir)
        if not ok:
            complete_run(conn, run_id, status="failed", error=verify_error, dispatch_log=_dispatch_log)
            log.error("Node '%s': %s", node.id, verify_error)
            try:
                if trace_id:
                    complete_trace(conn, trace_id, status="failed")
            except Exception:
                log.debug("Failed to complete trace on verify failure")
            if owns_conn:
                conn.close()
            return 1

        # Parse metrics from claude JSON output (best-effort)
        metrics = parse_claude_output(stdout) if stdout else {}

        # Hallucination guard: warn if dispatch used zero tool calls (US2)
        if stdout and _check_hallucination(stdout):
            log.warning(
                "Hallucination guard: node '%s' completed with zero tool calls — output may be fabricated", node.id
            )

        # Resolve output artifact for eval scoring and output_lines (FR-012/U2)
        eval_output = None
        if node.outputs:
            resolved = node.outputs[0].replace("{epic}", f"epics/{epic_slug}") if epic_slug else node.outputs[0]
            eval_path = platform_dir / resolved
            if eval_path.exists():
                eval_output = str(eval_path)
        complete_run(
            conn,
            run_id,
            status="completed",
            tokens_in=metrics.get("tokens_in"),
            tokens_out=metrics.get("tokens_out"),
            cost_usd=metrics.get("cost_usd"),
            duration_ms=metrics.get("duration_ms"),
            output_lines=_count_output_lines(eval_output),
            dispatch_log=_dispatch_log,
        )
        _run_eval_scoring(
            conn,
            platform_name,
            node.id,
            run_id,
            trace_id,
            epic_slug,
            eval_output,
            metrics,
        )

        # Auto-escalate: post-dispatch gate — decision depends on node output
        if _handle_auto_escalate(node, platform_dir, epic_slug, gmode, conn, platform_name, trace_id):
            if owns_conn:
                conn.close()
            return 0

        if epic_slug:
            upsert_epic_node(conn, platform_name, epic_slug, node.id, status="done")
        else:
            upsert_pipeline_node(conn, platform_name, node.id, status="done")
        completed_nodes.add(node.id)
        log.info("Node '%s' completed successfully (async)", node.id)

    # Complete trace with aggregated metrics
    try:
        if trace_id:
            final_status = "completed" if completed_nodes else "cancelled"
            complete_trace(conn, trace_id, status=final_status)
    except Exception:
        log.debug("Failed to complete trace at pipeline end")

    log.info("Pipeline async %s complete — %d nodes executed", mode.upper(), len(completed_nodes))

    if epic_slug:
        _transition_epic_status(conn, platform_name, epic_slug)

    # Refresh portal dashboard JSON (best-effort)
    try:
        from post_save import _refresh_portal_status

        _refresh_portal_status()
    except Exception:
        log.debug("Failed to refresh portal status")

    if owns_conn:
        conn.close()
    return 0


# ── Prompt Composition ───────────────────────────────────────────────


def compose_skill_prompt(
    platform_name: str,
    node: Node,
    platform_dir: Path,
    epic_slug: str | None = None,
) -> tuple[str, str | None]:
    """Compose a prompt + optional system guardrail for dispatching a skill via claude -p.

    Returns (prompt, system_guardrail_or_None).
    For L1 madruga:* skills: instruction + dependency artifact contents.
    For L2 speckit.implement: delegates to implement_remote.compose_prompt().
    For other L2 speckit.*: instruction + epic artifacts + guardrail.
    """
    skill = node.skill

    # L2 speckit.implement — use existing compose_prompt + analyze-report context
    if skill == "speckit.implement" and epic_slug:
        from implement_remote import compose_prompt

        output_dir = f"platforms/{platform_name}/epics/{epic_slug}"
        guardrail = (
            f"MANDATORY: You are on branch epic/{platform_name}/{epic_slug}. "
            f"Do NOT create or switch branches. "
            f"Set SPECIFY_BASE_DIR={output_dir}/ for any SpecKit scripts."
        )
        prompt = compose_prompt(platform_name, epic_slug)

        # Feed analyze findings into implement so it addresses them
        analyze_report = platform_dir / "epics" / epic_slug / "analyze-report.md"
        if analyze_report.exists():
            report_content = analyze_report.read_text(encoding="utf-8")[:10000]
            prompt += (
                "\n\n---\n\n## Pre-Implementation Analysis Report\n\n"
                "Address these findings during implementation:\n\n"
                f"{report_content}"
            )

        return prompt, guardrail

    # L2 speckit.* or madruga:* epic skills — instruction + epic context + guardrail
    if epic_slug:
        epic_dir = platform_dir / "epics" / epic_slug
        output_dir = f"platforms/{platform_name}/epics/{epic_slug}"

        parts = [
            f"Follow the skill instructions in the system prompt for platform '{platform_name}', epic '{epic_slug}'.",
            "",
            "CRITICAL CONSTRAINTS:",
            f"- export SPECIFY_BASE_DIR={output_dir}/",
            f"- Save ALL output to: {output_dir}/",
            f"- You are on branch: epic/{platform_name}/{epic_slug}",
            "- Do NOT create, switch, or checkout any branch. The branch already exists.",
            "- Do NOT run create-new-feature.sh. The epic directory already exists.",
            "- Do NOT write files outside the epic directory.",
            f"- Expected output file: {', '.join(node.outputs)}",
        ]

        # Include relevant epic artifacts as context
        context_files = ["pitch.md", "spec.md", "plan.md", "tasks.md"]
        for fname in context_files:
            fpath = epic_dir / fname
            if fpath.exists():
                content = fpath.read_text()
                if len(content) > 50000:
                    content = content[:50000] + "\n\n[... truncated ...]"
                parts.append(f"\n---\n\n## {fname}\n\n{content}")

        # Inject upstream reports for context threading (analyze-post → judge → qa → reconcile)
        for rname in REPORT_CONTEXT.get(node.id, []):
            rpath = epic_dir / rname
            if rpath.exists():
                rcontent = rpath.read_text(encoding="utf-8")[:10_000]
                parts.append(f"\n---\n\n## Upstream Report: {rname}\n\nAddress these findings:\n\n{rcontent}")

        guardrail = (
            f"MANDATORY: Save all files to {output_dir}/. "
            f"Current branch: epic/{platform_name}/{epic_slug}. "
            f"Do NOT create branches, switch branches, or write outside the epic directory. "
            f"Set SPECIFY_BASE_DIR={output_dir}/ if using SpecKit scripts. "
            f"Do NOT run create-new-feature.sh."
        )
        return "\n".join(parts), guardrail

    # L1 madruga:* — instruction + dependency outputs as context
    parts = [f"Follow the skill instructions in the system prompt for platform '{platform_name}'."]

    # Read dependency outputs as context
    for dep_id in node.depends:
        # Try to find output files from the dependency node
        dep_outputs_dir = platform_dir
        for candidate in [f"{dep_id}.md", f"business/{dep_id}.md", f"engineering/{dep_id}.md"]:
            candidate_path = dep_outputs_dir / candidate
            if candidate_path.exists():
                content = candidate_path.read_text()
                if len(content) > 30000:
                    content = content[:30000] + "\n\n[... truncated ...]"
                parts.append(f"## Context from {dep_id}\n\n{content}")
                break

    return "\n\n---\n\n".join(parts), None


# ── Bare-mode System Prompt & Command Builder ─────────────────────


_QUICK_FIX_CONTEXT = (
    "# Quick-Fix Mode (Fast Lane)\n\n"
    "You are running in QUICK-FIX mode — a compressed L2 cycle: specify → implement → judge.\n"
    "This mode skips plan, tasks, analyze, clarify, qa, and reconcile.\n\n"
    "CONSTRAINTS:\n"
    "- Scope is restricted to bug fixes and small changes (max 3 files, ~100 LOC)\n"
    "- Do NOT create plan.md or tasks.md — they are not part of the quick cycle\n"
    "- Generate a minimal spec.md (problem + fix + acceptance criteria)\n"
    "- Focus on shipping the fix fast with quality (judge review follows)\n"
)


def build_system_prompt(node: Node, platform_name: str, quick_mode: bool = False) -> str:
    """Build a focused system prompt for --bare dispatch.

    Assembles:
    1. Trimmed CLAUDE.md essentials (conventions, not discovery)
    2. pipeline-contract-base.md (full)
    3. Layer-specific contract (engineering/planning/business)
    4. Python rules (only for implement nodes)
    5. Full skill .md body
    6. Quick-fix context (only when quick_mode=True)

    Returns the concatenated system prompt string.
    """
    parts: list[str] = [_CONVENTIONS_HEADER, _AUTONOMOUS_DISPATCH]

    # Base contract (always)
    base_contract = REPO_ROOT / ".claude" / "knowledge" / "pipeline-contract-base.md"
    if base_contract.exists():
        parts.append(base_contract.read_text(encoding="utf-8"))

    # Layer contract
    layer_file = LAYER_CONTRACT_MAP.get(node.layer)
    if layer_file:
        layer_path = REPO_ROOT / layer_file
        if layer_path.exists():
            parts.append(layer_path.read_text(encoding="utf-8"))

    # Python rules (implement nodes only — they write code)
    if node.id == "implement" or node.id.startswith("implement:"):
        python_rules = REPO_ROOT / ".claude" / "rules" / "python.md"
        if python_rules.exists():
            parts.append(python_rules.read_text(encoding="utf-8"))

    # Skill body
    skill_file = SKILL_FILE_MAP.get(node.skill)
    if not skill_file:
        # Derive from convention
        if node.skill.startswith("speckit."):
            skill_file = f".claude/commands/{node.skill}.md"
        elif ":" in node.skill:
            name = node.skill.split(":", 1)[1]
            skill_file = f".claude/commands/madruga/{name}.md"
    if skill_file:
        skill_path = REPO_ROOT / skill_file
        if skill_path.exists():
            parts.append(f"# Skill Instructions\n\n{skill_path.read_text(encoding='utf-8')}")
        else:
            log.warning("Skill file not found: %s", skill_path)

    # Quick-fix mode context
    if quick_mode:
        parts.append(_QUICK_FIX_CONTEXT)

    return "\n\n---\n\n".join(parts)


def build_dispatch_cmd(
    node: Node,
    prompt: str,
    platform_name: str,
    guardrail: str | None = None,
    resume_session_id: str | None = None,
    quick_mode: bool = False,
) -> list[str]:
    """Build the claude -p command array with --system-prompt, --allowedTools, --effort.

    Uses --bare only when ANTHROPIC_API_KEY is set (API key auth).
    With OAuth (claude.ai), --bare is skipped because it disables OAuth/keychain reads.

    The ``prompt`` argument is kept in the signature for test compatibility,
    but it is NOT placed on the command line — it is piped via stdin by
    ``dispatch_node_async``. Passing large prompts as argv blows up against
    the Linux per-arg limit ``MAX_ARG_STRLEN=128KB`` with ``OSError:
    [Errno 7] Argument list too long`` (postmortem: prosauai/003 T042 cascade).

    Centralizes command construction for both dispatch_node() and dispatch_node_async().
    """
    system_prompt = build_system_prompt(node, platform_name, quick_mode=quick_mode or _quick_mode_ctx.get())

    # NB: ``prompt`` is intentionally NOT passed on argv; it's piped via stdin.
    # See note in the docstring.
    _ = prompt
    cmd = [
        "claude",
        "-p",
    ]

    # --bare isolates the agent: no CLAUDE.md, no hooks, no user settings.
    # Needs ANTHROPIC_API_KEY (--bare disables OAuth).
    if os.environ.get("ANTHROPIC_API_KEY"):
        cmd.append("--bare")

    cmd.extend(
        [
            "--output-format",
            "json",
            "--system-prompt",
            system_prompt,
        ]
    )

    # --bare-lite: approximate --bare isolation under OAuth (no ANTHROPIC_API_KEY).
    # Drops user/local MCP servers, skill resolver, and (for implement) tool defs
    # that aren't needed. Rollback: MADRUGA_BARE_LITE=0 (systemd drop-in).
    if _flag(ENV_BARE_LITE):
        cmd.extend(
            [
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--disable-slash-commands",
            ]
        )
        # --tools prunes tool DEFINITIONS (not just runtime gating like --allowedTools).
        # Safe only for implement:* — judge/qa need Agent, tech-research needs Web*.
        if node.id.startswith("implement:") or node.id == "implement":
            cmd.extend(["--tools", IMPLEMENT_TASK_TOOLS])
        if not resume_session_id:
            cmd.append("--no-session-persistence")
        # Opt-in (off by default until settings.local.json audit completes).
        if _flag(ENV_STRICT_SETTINGS, default="0"):
            cmd.extend(["--setting-sources", "project"])

    # Tool restriction (runtime permission gate — composes with --tools above)
    tools = NODE_TOOLS.get(node.id, DEFAULT_TOOLS)
    if node.id.startswith("implement:"):
        tools = IMPLEMENT_TASK_TOOLS
    cmd.extend(["--allowedTools", tools])

    # Effort tuning
    effort = NODE_EFFORT.get(node.id)
    if effort:
        cmd.extend(["--effort", effort])

    # Resume session
    if resume_session_id:
        cmd.extend(["--resume", resume_session_id])

    # Guardrail (append-system-prompt for hard constraints)
    if guardrail:
        cmd.extend(["--append-system-prompt", guardrail])

    # Defense-in-depth: block dangerous git operations
    cmd.extend(["--disallowedTools", DISALLOWED_TOOLS])

    # Safety net against silent hangs in ``claude -p`` auto-review loops —
    # tasks typically need 20–40 turns, so a ceiling of 100 is 2.5–5× the
    # normal and only fires on pathological loops. Set
    # ``MADRUGA_MAX_TURNS=0`` / ``unlimited`` to disable. See
    # easter-tracking.md (prosauai/004-router-mece) for the motivating
    # incidents (T004, T006 silent-hang pattern).
    max_turns = os.environ.get("MADRUGA_MAX_TURNS", "100")
    if max_turns and max_turns not in ("0", "unlimited"):
        cmd.extend(["--max-turns", max_turns])

    log.info(
        "dispatch_cmd node=%s system_prompt_bytes=%d flags=%s",
        node.id,
        len(system_prompt.encode()),
        [f for f in cmd if f.startswith("--")],
    )

    return cmd


# ── Pipeline Orchestrator ────────────────────────────────────────────


def run_pipeline(
    platform_name: str,
    epic_slug: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    gate_mode: str | None = None,
    quick: bool = False,
) -> int:
    """Execute the pipeline DAG.

    gate_mode: 'manual' | 'interactive' | 'auto' (see run_pipeline_async).

    Returns exit code: 0=success or paused at gate, 1=failure.

    ARCHITECTURAL INVARIANT: This function processes epics sequentially.
    Parallel epic execution is ONLY safe for external repos (via worktree
    isolation). Self-ref platforms share working dir, DB, and skills —
    see pipeline-dag-knowledge.md "Parallel Epics Constraint".
    """
    _quick_mode_ctx.set(quick)

    gmode = gate_mode or DEFAULT_GATE_MODE
    if gmode not in VALID_GATE_MODES:
        log.error("Invalid gate_mode '%s'. Valid: %s", gmode, VALID_GATE_MODES)
        return 1

    platform_dir = REPO_ROOT / "platforms" / platform_name

    mode = "quick" if quick else ("l2" if epic_slug else "l1")
    nodes = parse_dag(mode=mode, epic=epic_slug)
    ordered = topological_sort(nodes)

    log.info("Pipeline %s — %d nodes in %s mode", platform_name, len(ordered), mode.upper())

    if dry_run:
        print(f"\n{'=' * 60}")
        print(f"DRY RUN — {mode.upper()} Pipeline: {platform_name}")
        if epic_slug:
            print(f"Epic: {epic_slug}")
        print(f"{'=' * 60}\n")
        for i, node in enumerate(ordered, 1):
            gate_label = f" [{node.gate}]" if node.gate in HUMAN_GATES else ""
            opt = " (optional)" if node.optional else ""
            print(f"  {i:2d}. {node.id:<25s} skill={node.skill}{gate_label}{opt}")
        print(f"\nTotal: {len(ordered)} nodes")
        return 0

    # Get DB connection for state management
    from db import (
        complete_run,
        complete_trace,
        get_conn,
        get_pending_gates,
        get_resumable_nodes,
        insert_run,
        upsert_epic_node,
        upsert_pipeline_node,
    )

    conn = get_conn()
    completed_nodes: set[str] = set()

    if resume:
        completed_nodes = get_resumable_nodes(conn, platform_name, epic_slug)
        # Check for pending (unapproved) gates
        pending = get_pending_gates(conn, platform_name)
        if epic_slug:
            pending = [g for g in pending if g.get("epic_id") == epic_slug]
        for gate in pending:
            if gate["node_id"] not in completed_nodes:
                log.info("Gate pendente para '%s'. Execute:", gate["node_id"])
                log.info("  python3 .specify/scripts/platform_cli.py gate approve %s", gate["run_id"])
                conn.close()
                return 0

    trace_id = _resolve_trace_id(conn, platform_name, epic_slug, resume, mode, len(ordered))
    if resume:
        log.info("Resume: %d nodes already completed", len(completed_nodes))

    breaker = CircuitBreaker(conn=conn, platform_id=platform_name, epic_id=epic_slug)
    cwd = REPO_ROOT
    code_dir = _resolve_code_dir(platform_name, epic_slug)
    if code_dir != REPO_ROOT:
        log.info("External repo code_dir: %s", code_dir)

    for node in ordered:
        # Skip completed nodes
        if node.id in completed_nodes:
            log.info("Skipping completed node: %s", node.id)
            continue

        # Skip optional nodes with skip_condition
        if node.optional and node.skip_condition:
            log.info("Skipping optional node: %s (%s)", node.id, node.skip_condition)
            if epic_slug:
                upsert_epic_node(conn, platform_name, epic_slug, node.id, status="skipped")
            else:
                upsert_pipeline_node(conn, platform_name, node.id, status="skipped")
            completed_nodes.add(node.id)
            continue

        # Check dependencies satisfied
        node_deps = set(node.depends)
        if not node_deps.issubset(completed_nodes):
            missing = node_deps - completed_nodes
            log.warning("Node '%s' blocked — missing deps: %s", node.id, missing)
            continue

        # Human gate handling based on gmode
        if node.gate in HUMAN_GATES:
            if gmode == "auto":
                log.info("Auto-approving gate '%s' (mode=auto)", node.id)
            elif gmode == "interactive":
                print(f"\n>>> Gate '{node.id}' (type: {node.gate}, skill: {node.skill})")
                print(f"    Next: dispatch '{node.skill}' for epic '{epic_slug or 'L1'}'")
                try:
                    answer = input("    Approve? [y/N] ").strip().lower()
                except EOFError:
                    answer = "n"
                if answer != "y":
                    log.info("Gate '%s' rejected by user (interactive mode)", node.id)
                    conn.close()
                    return 0
                log.info("Gate '%s' approved by user (interactive mode)", node.id)
            else:
                # gmode == "manual": pause and wait for external approval
                run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug)
                conn.execute(
                    "UPDATE pipeline_runs SET gate_status='waiting_approval' WHERE run_id=?",
                    (run_id,),
                )
                conn.commit()
                log.info("Aguardando aprovacao para '%s' (gate: %s)", node.id, node.gate)
                log.info("Execute: python3 .specify/scripts/platform_cli.py gate approve %s", run_id)
                log.info("Apos aprovar, re-execute com --resume.")
                conn.close()
                return 0

        # Task-by-task dispatch for speckit.implement (sync falls back to monolithic)
        if node.skill == "speckit.implement" and epic_slug:
            log.warning(
                "Sync run_pipeline does not support task-by-task dispatch. Use async (easter/--mode interactive)."
            )

        # Compose prompt
        prompt, guardrail = compose_skill_prompt(platform_name, node, platform_dir, epic_slug)

        # Dispatch with retry + circuit breaker
        node_cwd = code_dir if _needs_code_cwd(node) else cwd
        success, error, stdout = dispatch_with_retry(
            node, node_cwd, prompt, timeout, breaker, guardrail, platform_name=platform_name
        )

        if not success:
            run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug, error=error, trace_id=trace_id)
            complete_run(conn, run_id, status="failed", error=error)
            log.error("Node '%s' failed after retries: %s", node.id, error)
            try:
                if trace_id:
                    complete_trace(conn, trace_id, status="failed")
            except Exception:
                log.debug("Failed to complete trace on failure")
            conn.close()
            return 1

        # Layer 4: verify branch didn't change
        if epic_slug:
            branch_check = subprocess.run(
                ["git", "branch", "--show-current"], capture_output=True, text=True, cwd=str(node_cwd)
            )
            expected_branch = f"epic/{platform_name}/{epic_slug}"
            actual_branch = branch_check.stdout.strip()
            if actual_branch != expected_branch:
                subprocess.run(["git", "checkout", expected_branch], cwd=str(node_cwd), capture_output=True)
                log.error("claude -p changed branch to '%s', reverted to '%s'", actual_branch, expected_branch)

        # Layer 5: save stdout as missing output for read-only skills
        # Extract actual content from claude JSON (not raw metadata)
        if stdout:
            save_content = stdout
            try:
                data = json.loads(stdout)
                if isinstance(data, dict) and data.get("type") == "result":
                    save_content = data.get("result", "")
            except (ValueError, TypeError):
                pass
            if save_content:
                for output_path in node.outputs:
                    resolved = output_path.replace("{epic}", f"epics/{epic_slug}") if epic_slug else output_path
                    full_path = platform_dir / resolved
                    if not full_path.exists():
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        full_path.write_text(save_content)
                        log.info("Saved stdout as missing output: %s", resolved)

        # Verify outputs
        ok, verify_error = verify_outputs(node, platform_dir)
        if not ok:
            run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug, error=verify_error, trace_id=trace_id)
            complete_run(conn, run_id, status="failed", error=verify_error)
            log.error("Node '%s': %s", node.id, verify_error)
            try:
                if trace_id:
                    complete_trace(conn, trace_id, status="failed")
            except Exception:
                log.debug("Failed to complete trace on verify failure")
            conn.close()
            return 1

        # Parse metrics from claude JSON output (best-effort)
        metrics = parse_claude_output(stdout) if stdout else {}

        # Hallucination guard: warn if dispatch used zero tool calls (US2)
        if stdout and _check_hallucination(stdout):
            log.warning(
                "Hallucination guard: node '%s' completed with zero tool calls — output may be fabricated", node.id
            )

        # Resolve output artifact for eval scoring and output_lines (FR-012/U2)
        eval_output = None
        if node.outputs:
            resolved = node.outputs[0].replace("{epic}", f"epics/{epic_slug}") if epic_slug else node.outputs[0]
            eval_path = platform_dir / resolved
            if eval_path.exists():
                eval_output = str(eval_path)
        run_id = insert_run(
            conn,
            platform_name,
            node.id,
            epic_id=epic_slug,
            trace_id=trace_id,
            output_lines=_count_output_lines(eval_output),
        )
        complete_run(
            conn,
            run_id,
            status="completed",
            tokens_in=metrics.get("tokens_in"),
            tokens_out=metrics.get("tokens_out"),
            cost_usd=metrics.get("cost_usd"),
            duration_ms=metrics.get("duration_ms"),
        )
        _run_eval_scoring(
            conn,
            platform_name,
            node.id,
            run_id,
            trace_id,
            epic_slug,
            eval_output,
            metrics,
        )

        # Auto-escalate: post-dispatch gate — decision depends on node output
        if _handle_auto_escalate(node, platform_dir, epic_slug, gmode, conn, platform_name, trace_id):
            conn.close()
            return 0

        if epic_slug:
            upsert_epic_node(conn, platform_name, epic_slug, node.id, status="done")
        else:
            upsert_pipeline_node(conn, platform_name, node.id, status="done")
        completed_nodes.add(node.id)
        log.info("Node '%s' completed successfully", node.id)

    # Complete trace with aggregated metrics
    try:
        if trace_id:
            final_status = "completed" if completed_nodes else "cancelled"
            complete_trace(conn, trace_id, status=final_status)
    except Exception:
        log.debug("Failed to complete trace at pipeline end")

    print(f"\nPipeline {mode.upper()} complete — {len(completed_nodes)} nodes executed.")

    if epic_slug:
        _transition_epic_status(conn, platform_name, epic_slug)

    # Refresh portal dashboard JSON (best-effort)
    try:
        from post_save import _refresh_portal_status

        _refresh_portal_status()
    except Exception:
        log.debug("Failed to refresh portal status")

    conn.close()
    return 0


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DAG executor for the Madruga AI pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--platform", required=True, help="Platform name (e.g., madruga-ai)")
    parser.add_argument("--epic", default=None, help="Epic slug for L2 mode (e.g., 013-dag-executor-bridge)")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Print execution order without dispatching")
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Watchdog timeout in seconds (default: {DEFAULT_TIMEOUT})"
    )
    parser.add_argument(
        "--mode",
        choices=["manual", "interactive", "auto"],
        default=None,
        help="Gate mode: manual (default, pause at gates), interactive (y/n prompt), auto (no pauses)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Fast lane: use quick_cycle (specify → implement → judge) instead of full epic_cycle",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--json", action="store_true", dest="json_mode", help="Emit structured NDJSON log output")
    args = parser.parse_args()

    if args.quick and not args.epic:
        parser.error("--quick requires --epic")

    _setup_logging(args.json_mode, verbose=args.verbose)

    # Use async path (supports task-by-task implement); sync only for dry-run
    if args.dry_run:
        sys.exit(
            run_pipeline(
                platform_name=args.platform,
                epic_slug=args.epic,
                resume=args.resume,
                dry_run=True,
                timeout=args.timeout,
                gate_mode=args.mode,
                quick=args.quick,
            )
        )
    else:
        sys.exit(
            asyncio.run(
                run_pipeline_async(
                    platform_name=args.platform,
                    epic_slug=args.epic,
                    resume=args.resume,
                    timeout=args.timeout,
                    gate_mode=args.mode,
                    quick=args.quick,
                )
            )
        )


if __name__ == "__main__":
    main()
