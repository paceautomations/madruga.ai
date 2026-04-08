"""
eval_scorer.py — Heuristic eval scoring for pipeline node outputs.

Scores each completed node across 4 dimensions (0-10 scale):
  - quality:           Output non-empty + no error markers → 7.0 default;
                       normalizes Judge score if a judge-report exists.
  - adherence_to_spec: Regex-matches expected markdown sections vs actual output.
  - completeness:      min(10, actual_lines / expected_lines * 10).
  - cost_efficiency:   10 - min(10, cost / avg_budget * 10); neutral 5.0 if no history.

Usage:
    from eval_scorer import score_node
    scores = score_node(conn, platform_id, node_id, run_id, output_path, metrics)
    for s in scores:
        insert_eval_score(conn, **s)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Expected markdown sections per node type (L1 + L2).
# Keys are node_id patterns; values are lists of heading regexes.
_NODE_EXPECTED_SECTIONS: dict[str, list[str]] = {
    # L1 nodes
    "vision": [r"#+\s*Playing to Win", r"#+\s*Winning Aspiration", r"#+\s*Where to Play"],
    "solution-overview": [r"#+\s*Feature", r"#+\s*Summary"],
    "business-process": [r"#+\s*Processo", r"#+\s*Mermaid|```mermaid"],
    "tech-research": [r"#+\s*Decision Matrix|#+\s*Alternatives"],
    "blueprint": [r"#+\s*Cross-Cutting|#+\s*NFR", r"#+\s*Deploy"],
    "domain-model": [r"#+\s*Bounded Context", r"#+\s*Aggregate"],
    "containers": [r"#+\s*Container|specification\s*\{"],
    "context-map": [r"#+\s*Context Map|#+\s*Relationship"],
    "epic-breakdown": [r"#+\s*Problem|#+\s*Solution"],
    "roadmap": [r"#+\s*Roadmap|#+\s*Epic.*Sequenc"],
    # L2 nodes
    "epic-context": [r"#+\s*Problem|#+\s*Solution"],
    "specify": [r"#+\s*User Stor|#+\s*Acceptance"],
    "plan": [r"#+\s*Summary|#+\s*Technical Context|#+\s*Project Structure"],
    "tasks": [r"#+\s*Phase|#+\s*Task|\- \[.\] T\d+"],
    "analyze": [r"#+\s*Consistency|#+\s*Finding|#+\s*Result"],
    "implement": [r"#+\s*Implementation|#+\s*Result"],
    "judge": [r"#+\s*Verdict|#+\s*Score|#+\s*Review"],
    "reconcile": [r"#+\s*Drift|#+\s*Reconcil"],
}

# Reasonable expected line counts per node type.
_NODE_EXPECTED_LINES: dict[str, int] = {
    "vision": 80,
    "solution-overview": 100,
    "business-process": 80,
    "tech-research": 150,
    "blueprint": 120,
    "domain-model": 120,
    "containers": 80,
    "context-map": 80,
    "epic-breakdown": 100,
    "roadmap": 80,
    "epic-context": 80,
    "specify": 120,
    "plan": 150,
    "tasks": 100,
    "analyze": 80,
    "implement": 60,
    "judge": 100,
    "qa": 80,
    "reconcile": 60,
}

_DEFAULT_EXPECTED_LINES = 80

# Error markers that indicate a problematic output.
_ERROR_MARKERS = [
    r"\[ERROR\]",
    r"\[FATAL\]",
    r"Traceback \(most recent call last\)",
    r"^FAILED\b",  # anchored to line start — avoids false positives in prose
    r"Exception:",
]


def score_node(
    conn: sqlite3.Connection,
    platform_id: str,
    node_id: str,
    run_id: str | None,
    output_path: str | None,
    metrics: dict | None = None,
) -> list[dict]:
    """Score a completed node across 4 heuristic dimensions.

    Args:
        conn: DB connection (for historical cost lookups).
        platform_id: Platform identifier.
        node_id: Pipeline node identifier.
        run_id: Pipeline run ID (nullable for manual scores).
        output_path: Absolute path to the primary output artifact.
        metrics: Dict with optional keys: cost_usd, tokens_in, tokens_out,
                 duration_ms, output_lines, judge_score (0-100).

    Returns:
        List of score dicts ready for insert_eval_score (without score_id/evaluated_at).
    """
    metrics = metrics or {}
    content = _read_output(output_path)
    actual_lines = content.count("\n") + 1 if content else 0

    scores = [
        _score_quality(content, metrics, node_id),
        _score_adherence(content, node_id),
        _score_completeness(actual_lines, node_id, metrics),
        _score_cost_efficiency(conn, platform_id, node_id, metrics),
    ]

    result = []
    for dimension, score, meta in scores:
        result.append(
            {
                "platform_id": platform_id,
                "node_id": node_id,
                "run_id": run_id,
                "dimension": dimension,
                "score": round(max(0.0, min(10.0, score)), 1),
                "metadata": json.dumps(meta) if meta else None,
            }
        )
    return result


def _read_output(output_path: str | None) -> str:
    """Read output file content. Returns empty string on failure."""
    if not output_path:
        return ""
    try:
        p = Path(output_path)
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.debug("Could not read output at %s", output_path)
    return ""


def _score_quality(content: str, metrics: dict, node_id: str = "") -> tuple[str, float, dict]:
    """Quality: Judge score if available, else heuristic (non-empty + no errors)."""
    meta: dict = {"method": "heuristic"}

    # If Judge score is provided (0-100 scale), normalize to 0-10.
    judge_score = metrics.get("judge_score")
    if judge_score is not None:
        try:
            normalized = float(judge_score) / 100.0 * 10.0
            meta = {"method": "judge", "raw_judge_score": judge_score}
            return ("quality", normalized, meta)
        except (TypeError, ValueError):
            pass

    # Implement tasks don't produce output files — score by completion + tokens.
    if not content.strip() and node_id.startswith("implement:"):
        tokens_out = metrics.get("tokens_out") or 0
        meta = {"method": "implement_heuristic"}
        if tokens_out > 500:
            meta["reason"] = "substantial_output_tokens"
            return ("quality", 8.0, meta)
        elif tokens_out > 0:
            meta["reason"] = "completed_with_output"
            return ("quality", 7.0, meta)
        else:
            meta["reason"] = "completed_no_token_data"
            return ("quality", 6.0, meta)

    # Heuristic: start at 7.0, penalize for issues.
    score = 7.0
    if not content.strip():
        score = 1.0
        meta["reason"] = "empty_output"
        return ("quality", score, meta)

    # Check for error markers.
    error_count = 0
    for pattern in _ERROR_MARKERS:
        error_count += len(re.findall(pattern, content, re.MULTILINE))
    if error_count > 0:
        penalty = min(4.0, error_count * 1.0)
        score -= penalty
        meta["error_markers_found"] = error_count

    return ("quality", score, meta)


def _score_adherence(content: str, node_id: str) -> tuple[str, float, dict]:
    """Adherence to spec: proportion of expected sections found in output."""
    # Normalize node_id for lookup (strip -post suffix from analyze-post).
    # Strip implement:TXXX to just "implement" for lookup.
    lookup_id = node_id.replace("-post", "")
    if lookup_id.startswith("implement:"):
        lookup_id = "implement"
    expected = _NODE_EXPECTED_SECTIONS.get(lookup_id, [])
    meta: dict = {"method": "section_match"}

    # Implement tasks don't produce output files — score by completion.
    if node_id.startswith("implement:") and not content.strip():
        return ("adherence_to_spec", 7.0, {"method": "implement_completed", "reason": "no_artifact_expectations"})

    if not expected:
        meta["reason"] = "no_expectations_defined"
        return ("adherence_to_spec", 5.0, meta)

    if not content.strip():
        meta["reason"] = "empty_output"
        return ("adherence_to_spec", 0.0, meta)

    matched = 0
    for pattern in expected:
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            matched += 1

    score = (matched / len(expected)) * 10.0
    meta["matched"] = matched
    meta["expected"] = len(expected)
    return ("adherence_to_spec", score, meta)


def _score_completeness(actual_lines: int, node_id: str, metrics: dict) -> tuple[str, float, dict]:
    """Completeness: actual lines vs expected lines."""
    meta: dict = {"method": "line_ratio"}

    # Use metrics.output_lines if provided, else actual_lines from file read.
    lines = metrics.get("output_lines", actual_lines)
    if lines is None or lines <= 0:
        # Implement tasks: completion = 10.0 (only called on success).
        if node_id.startswith("implement:"):
            return ("completeness", 10.0, {"method": "implement_completion", "reason": "task_completed_successfully"})
        meta["reason"] = "no_output"
        return ("completeness", 0.0, meta)

    lookup_id = node_id.replace("-post", "")
    expected = _NODE_EXPECTED_LINES.get(lookup_id, _DEFAULT_EXPECTED_LINES)
    score = min(10.0, (lines / expected) * 10.0)
    meta["actual_lines"] = lines
    meta["expected_lines"] = expected
    return ("completeness", score, meta)


def _score_cost_efficiency(
    conn: sqlite3.Connection,
    platform_id: str,
    node_id: str,
    metrics: dict,
) -> tuple[str, float, dict]:
    """Cost efficiency: 10 - min(10, cost / avg_budget * 10). Neutral 5.0 if no history."""
    meta: dict = {"method": "cost_ratio"}
    cost = metrics.get("cost_usd")

    if cost is None or cost <= 0:
        meta["reason"] = "no_cost_data"
        return ("cost_efficiency", 5.0, meta)

    # Look up historical average cost for this node.
    avg_cost = _get_avg_cost(conn, platform_id, node_id)
    if avg_cost is None or avg_cost <= 0:
        meta["reason"] = "no_history"
        return ("cost_efficiency", 5.0, meta)

    # Budget = avg * 1.5 (generous margin).
    budget = avg_cost * 1.5
    score = 10.0 - min(10.0, (cost / budget) * 10.0)
    meta["cost_usd"] = cost
    meta["avg_cost"] = round(avg_cost, 4)
    meta["budget"] = round(budget, 4)
    return ("cost_efficiency", score, meta)


def _get_avg_cost(conn: sqlite3.Connection, platform_id: str, node_id: str) -> float | None:
    """Get average cost_usd for a node from pipeline_runs history.

    Returns None if fewer than 3 completed runs exist (not enough data for meaningful average).
    """
    try:
        row = conn.execute(
            "SELECT AVG(cost_usd) as avg_cost, COUNT(*) as cnt FROM pipeline_runs "
            "WHERE platform_id=? AND node_id=? AND cost_usd > 0 AND status='completed'",
            (platform_id, node_id),
        ).fetchone()
        if row and row[0] is not None and (row[1] or 0) >= 3:
            return float(row[0])
    except Exception:
        logger.debug("Could not query avg cost for %s/%s", platform_id, node_id)
    return None
