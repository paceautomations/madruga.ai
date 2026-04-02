#!/usr/bin/env python3
"""
dag_executor.py — Custom DAG executor for the Madruga AI pipeline.

Reads platform.yaml, performs topological sort, dispatches skills via
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
import logging
import os
import random
import shutil
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from typing import NamedTuple

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from config import REPO_ROOT  # noqa: E402

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = int(os.environ.get("MADRUGA_EXECUTOR_TIMEOUT", "600"))
RETRY_BACKOFFS = [5, 10, 20]
CB_MAX_FAILURES = 5
CB_RECOVERY_SECONDS = 300
HUMAN_GATES = frozenset({"human", "1-way-door"})


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


def parse_dag(platform_yaml: Path, mode: str = "l1", epic: str | None = None) -> list[Node]:
    """Parse pipeline nodes from platform.yaml.

    Args:
        platform_yaml: Path to platform.yaml
        mode: 'l1' for platform pipeline, 'l2' for epic cycle
        epic: Epic slug (required for l2 mode, used to resolve {epic} templates)

    Returns:
        List of Node namedtuples.
    """
    data = yaml.safe_load(platform_yaml.read_text())
    pipeline = data.get("pipeline", {})

    if mode == "l2":
        cycle = pipeline.get("epic_cycle", {})
        raw_nodes = cycle.get("nodes", [])
        if not raw_nodes:
            raise SystemExit("ERROR: No epic_cycle.nodes section in platform.yaml")
    else:
        raw_nodes = pipeline.get("nodes", [])
        if not raw_nodes:
            raise SystemExit("ERROR: No pipeline.nodes section in platform.yaml")

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


# ── Circuit Breaker ──────────────────────────────────────────────────


class CircuitBreaker:
    """Simple circuit breaker: closed → open (after max_failures) → half-open (after recovery)."""

    def __init__(self, max_failures: int = CB_MAX_FAILURES, recovery_seconds: int = CB_RECOVERY_SECONDS):
        self.max_failures = max_failures
        self.recovery_seconds = recovery_seconds
        self.failure_count = 0
        self.last_failure_at: float = 0
        self.state = "closed"  # closed, open, half-open

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


# ── Dispatch ─────────────────────────────────────────────────────────


def dispatch_node(
    node: Node,
    cwd: Path,
    prompt: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[bool, str | None]:
    """Dispatch a skill via claude -p subprocess.

    Returns (success, error_message).
    """
    if not shutil.which("claude"):
        return False, "claude CLI not found in PATH"

    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    log.info("Dispatching node '%s' (skill: %s, timeout: %ds)", node.id, node.skill, timeout)
    log.debug("Command: %s", " ".join(cmd[:4]) + " ...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(cwd))
        if result.returncode != 0:
            error = result.stderr.strip()[:500] if result.stderr else f"exitcode {result.returncode}"
            log.error("Node '%s' failed: %s", node.id, error)
            return False, error
        return True, None
    except subprocess.TimeoutExpired:
        error = f"timeout after {timeout}s"
        log.error("Node '%s': %s", node.id, error)
        return False, error


def verify_outputs(node: Node, platform_dir: Path) -> tuple[bool, str | None]:
    """Check that all expected output files exist."""
    for output in node.outputs:
        # Skip glob patterns (e.g., "epics/*/pitch.md")
        if "*" in output:
            continue
        path = platform_dir / output
        if not path.exists():
            error = f"output not found: {output}"
            log.error("Node '%s': %s", node.id, error)
            return False, error
    return True, None


def dispatch_with_retry(
    node: Node,
    cwd: Path,
    prompt: str,
    timeout: int,
    breaker: CircuitBreaker,
) -> tuple[bool, str | None]:
    """Dispatch with retry (3x exponential backoff) and circuit breaker."""
    if not breaker.check():
        return False, "circuit breaker OPEN"

    last_error = None
    for attempt, backoff in enumerate([0] + RETRY_BACKOFFS, 1):
        if backoff > 0:
            log.info("Retry %d/%d for node '%s' after %ds", attempt - 1, len(RETRY_BACKOFFS), node.id, backoff)
            time.sleep(backoff)

        success, error = dispatch_node(node, cwd, prompt, timeout)
        if success:
            breaker.record_success()
            return True, None
        last_error = error

    breaker.record_failure()
    return False, last_error


# ── Async Dispatch (for daemon integration) ─────────────────────────


async def dispatch_node_async(
    node: Node,
    cwd: str | Path,
    prompt: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[bool, str | None]:
    """Async version of dispatch_node using asyncio.create_subprocess_exec."""
    if not shutil.which("claude"):
        return False, "claude CLI not found in PATH"

    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    log.info("Dispatching node '%s' async (skill: %s, timeout: %ds)", node.id, node.skill, timeout)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        if process.returncode != 0:
            error = stderr.decode()[:500] if stderr else f"exitcode {process.returncode}"
            log.error("Node '%s' failed: %s", node.id, error)
            return False, error
        return True, None
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        error = f"timeout after {timeout}s"
        log.error("Node '%s': %s", node.id, error)
        return False, error


async def dispatch_with_retry_async(
    node: Node,
    cwd: str | Path,
    prompt: str,
    timeout: int,
    breaker: CircuitBreaker,
) -> tuple[bool, str | None]:
    """Async version of dispatch_with_retry using asyncio.sleep."""
    if not breaker.check():
        return False, "circuit breaker OPEN"

    last_error = None
    for attempt, backoff in enumerate([0] + RETRY_BACKOFFS, 1):
        if backoff > 0:
            jittered = backoff + random.uniform(0, backoff * 0.3)
            log.info("Retry %d/%d for node '%s' after %.1fs", attempt - 1, len(RETRY_BACKOFFS), node.id, jittered)
            await asyncio.sleep(jittered)

        success, error = await dispatch_node_async(node, cwd, prompt, timeout)
        if success:
            breaker.record_success()
            return True, None
        last_error = error

    breaker.record_failure()
    return False, last_error


# ── Async Pipeline (for daemon) ─────────────────────────────────────


async def run_pipeline_async(
    platform_name: str,
    epic_slug: str | None = None,
    resume: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    semaphore: "asyncio.Semaphore | None" = None,
    conn: object | None = None,
) -> int:
    """Async version of run_pipeline for daemon integration.

    Returns exit code: 0=success or paused at gate, 1=failure.
    Human gates are written to DB and the function returns (daemon continues).
    If conn is provided, it is reused (not closed). Otherwise a new one is created.
    """
    platform_dir = REPO_ROOT / "platforms" / platform_name
    yaml_path = platform_dir / "platform.yaml"

    if not yaml_path.exists():
        log.error("platform.yaml not found: %s", yaml_path)
        return 1

    mode = "l2" if epic_slug else "l1"
    nodes = parse_dag(yaml_path, mode=mode, epic=epic_slug)
    ordered = topological_sort(nodes)

    log.info("Pipeline async %s — %d nodes in %s mode", platform_name, len(ordered), mode.upper())

    from db import (
        complete_run,
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
        completed_nodes = get_resumable_nodes(conn, platform_name, epic_slug)
        pending = get_pending_gates(conn, platform_name)
        if epic_slug:
            pending = [g for g in pending if g.get("epic_id") == epic_slug]
        for gate in pending:
            if gate["node_id"] not in completed_nodes:
                log.info("Gate pendente para '%s' — daemon aguardara aprovacao", gate["node_id"])
                if owns_conn:
                    conn.close()
                return 0
        log.info("Resume async: %d nodes already completed", len(completed_nodes))

    breaker = CircuitBreaker()
    cwd = REPO_ROOT

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
            continue

        node_deps = set(node.depends)
        if not node_deps.issubset(completed_nodes):
            missing = node_deps - completed_nodes
            log.warning("Node '%s' blocked — missing deps: %s", node.id, missing)
            continue

        # Human gate: write to DB and return (daemon will poll for approval)
        if node.gate in HUMAN_GATES:
            run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug)
            conn.execute(
                "UPDATE pipeline_runs SET gate_status='waiting_approval', gate_notified_at=datetime('now') "
                "WHERE run_id=?",
                (run_id,),
            )
            conn.commit()
            log.info("Gate '%s' aguardando aprovacao (run_id=%s)", node.id, run_id)
            if owns_conn:
                conn.close()
            return 0

        prompt = compose_skill_prompt(platform_name, node, platform_dir, epic_slug)

        if semaphore:
            async with semaphore:
                success, error = await dispatch_with_retry_async(node, cwd, prompt, timeout, breaker)
        else:
            success, error = await dispatch_with_retry_async(node, cwd, prompt, timeout, breaker)

        if not success:
            run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug, error=error)
            complete_run(conn, run_id, status="failed", error=error)
            log.error("Node '%s' failed after retries: %s", node.id, error)
            if owns_conn:
                conn.close()
            return 1

        ok, verify_error = verify_outputs(node, platform_dir)
        if not ok:
            run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug, error=verify_error)
            complete_run(conn, run_id, status="failed", error=verify_error)
            log.error("Node '%s': %s", node.id, verify_error)
            if owns_conn:
                conn.close()
            return 1

        run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug)
        complete_run(conn, run_id, status="completed")
        if epic_slug:
            upsert_epic_node(conn, platform_name, epic_slug, node.id, status="done")
        else:
            upsert_pipeline_node(conn, platform_name, node.id, status="done")
        completed_nodes.add(node.id)
        log.info("Node '%s' completed successfully (async)", node.id)

    log.info("Pipeline async %s complete — %d nodes executed", mode.upper(), len(completed_nodes))
    if owns_conn:
        conn.close()
    return 0


# ── Prompt Composition ───────────────────────────────────────────────


def compose_skill_prompt(
    platform_name: str,
    node: Node,
    platform_dir: Path,
    epic_slug: str | None = None,
) -> str:
    """Compose a prompt for dispatching a skill via claude -p.

    For L1 madruga:* skills: instruction + dependency artifact contents.
    For L2 speckit.implement: delegates to implement_remote.compose_prompt().
    For other L2 speckit.*: instruction + epic artifacts.
    """
    skill = node.skill

    # L2 speckit.implement — use existing compose_prompt
    if skill == "speckit.implement" and epic_slug:
        from implement_remote import compose_prompt

        return compose_prompt(platform_name, epic_slug)

    # L2 speckit.* — instruction + epic context
    if skill.startswith("speckit.") and epic_slug:
        skill_name = skill.split(".", 1)[1]
        epic_dir = platform_dir / "epics" / epic_slug
        parts = [f"Execute /speckit.{skill_name} for platform '{platform_name}', epic '{epic_slug}'."]

        # Include relevant epic artifacts as context
        context_files = ["pitch.md", "spec.md", "plan.md", "tasks.md"]
        for fname in context_files:
            fpath = epic_dir / fname
            if fpath.exists():
                content = fpath.read_text()
                if len(content) > 50000:
                    content = content[:50000] + "\n\n[... truncated ...]"
                parts.append(f"## {fname}\n\n{content}")
        return "\n\n---\n\n".join(parts)

    # L1 madruga:* — instruction + dependency outputs as context
    parts = [f"Execute /{skill} {platform_name}"]

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

    return "\n\n---\n\n".join(parts)


# ── Pipeline Orchestrator ────────────────────────────────────────────


def run_pipeline(
    platform_name: str,
    epic_slug: str | None = None,
    resume: bool = False,
    dry_run: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
) -> int:
    """Execute the pipeline DAG.

    Returns exit code: 0=success or paused at gate, 1=failure.

    ARCHITECTURAL INVARIANT: This function processes epics sequentially.
    Parallel epic execution is ONLY safe for external repos (via worktree
    isolation). Self-ref platforms share working dir, DB, and skills —
    see pipeline-dag-knowledge.md "Parallel Epics Constraint".
    """
    platform_dir = REPO_ROOT / "platforms" / platform_name
    yaml_path = platform_dir / "platform.yaml"

    if not yaml_path.exists():
        log.error("platform.yaml not found: %s", yaml_path)
        return 1

    mode = "l2" if epic_slug else "l1"
    nodes = parse_dag(yaml_path, mode=mode, epic=epic_slug)
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
        get_conn,
        get_pending_gates,
        get_resumable_nodes,
        insert_run,
        complete_run,
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
                print(f"Gate pendente para '{gate['node_id']}'. Execute:")
                print(f"  python3 .specify/scripts/platform_cli.py gate approve {gate['run_id']}")
                conn.close()
                return 0
        log.info("Resume: %d nodes already completed", len(completed_nodes))

    breaker = CircuitBreaker()
    cwd = REPO_ROOT

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
            continue

        # Check dependencies satisfied
        node_deps = set(node.depends)
        if not node_deps.issubset(completed_nodes):
            missing = node_deps - completed_nodes
            log.warning("Node '%s' blocked — missing deps: %s", node.id, missing)
            continue

        # Human gate: pause and exit
        if node.gate in HUMAN_GATES:
            run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug)
            conn.execute(
                "UPDATE pipeline_runs SET gate_status='waiting_approval', gate_notified_at=datetime('now') "
                "WHERE run_id=?",
                (run_id,),
            )
            conn.commit()
            print(f"\nAguardando aprovacao para '{node.id}' (gate: {node.gate}).")
            print(f"Execute: python3 .specify/scripts/platform_cli.py gate approve {run_id}")
            print("Apos aprovar, re-execute com --resume.\n")
            conn.close()
            return 0

        # Compose prompt
        prompt = compose_skill_prompt(platform_name, node, platform_dir, epic_slug)

        # Dispatch with retry + circuit breaker
        success, error = dispatch_with_retry(node, cwd, prompt, timeout, breaker)

        if not success:
            run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug, error=error)
            complete_run(conn, run_id, status="failed", error=error)
            log.error("Node '%s' failed after retries: %s", node.id, error)
            conn.close()
            return 1

        # Verify outputs
        ok, verify_error = verify_outputs(node, platform_dir)
        if not ok:
            run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug, error=verify_error)
            complete_run(conn, run_id, status="failed", error=verify_error)
            log.error("Node '%s': %s", node.id, verify_error)
            conn.close()
            return 1

        # Record success
        run_id = insert_run(conn, platform_name, node.id, epic_id=epic_slug)
        complete_run(conn, run_id, status="completed")
        if epic_slug:
            upsert_epic_node(conn, platform_name, epic_slug, node.id, status="done")
        else:
            upsert_pipeline_node(conn, platform_name, node.id, status="done")
        completed_nodes.add(node.id)
        log.info("Node '%s' completed successfully", node.id)

    print(f"\nPipeline {mode.upper()} complete — {len(completed_nodes)} nodes executed.")
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
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    sys.exit(
        run_pipeline(
            platform_name=args.platform,
            epic_slug=args.epic,
            resume=args.resume,
            dry_run=args.dry_run,
            timeout=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
