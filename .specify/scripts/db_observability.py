"""
db_observability.py — Traces, eval scores, stats, and cleanup.

Leaf-adjacent module: imports only stdlib + db_core.
No imports from db_pipeline, db_decisions at module level.

This module owns:
  - Trace lifecycle (create_trace, complete_trace, get_traces, get_trace_detail)
  - Eval score ingestion (insert_eval_score, get_eval_scores)
  - Aggregated stats (get_stats)
  - Data retention / cleanup (cleanup_old_data)
"""

from __future__ import annotations

import logging
import sqlite3
import uuid

from db_core import _now

logger = logging.getLogger(__name__)


# ══════════════════════════════════════
# Traces (Observability — Epic 017)
# ══════════════════════════════════════


def create_trace(
    conn: sqlite3.Connection,
    platform_id: str,
    epic_id: str | None = None,
    mode: str = "l1",
    total_nodes: int = 0,
) -> str:
    """Create a new trace for a pipeline run. Returns trace_id."""

    trace_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO traces (trace_id, platform_id, epic_id, mode, total_nodes, started_at) VALUES (?, ?, ?, ?, ?, ?)",
        (trace_id, platform_id, epic_id, mode, total_nodes, _now()),
    )
    conn.commit()
    logger.info("Created trace: %s (platform=%s, mode=%s)", trace_id, platform_id, mode)
    return trace_id


def complete_trace(conn: sqlite3.Connection, trace_id: str, status: str = "completed") -> None:
    """Complete a trace, aggregating metrics from its spans (pipeline_runs)."""
    row = conn.execute(
        "SELECT "
        "  COUNT(*) as span_count, "
        "  SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_count, "
        "  SUM(tokens_in) as total_tokens_in, "
        "  SUM(tokens_out) as total_tokens_out, "
        "  SUM(cost_usd) as total_cost_usd, "
        "  SUM(duration_ms) as total_duration_ms "
        "FROM pipeline_runs WHERE trace_id=?",
        (trace_id,),
    ).fetchone()
    conn.execute(
        "UPDATE traces SET status=?, completed_at=?, completed_nodes=?, "
        "total_tokens_in=?, total_tokens_out=?, total_cost_usd=?, total_duration_ms=? "
        "WHERE trace_id=?",
        (
            status,
            _now(),
            row["completed_count"] or 0,
            row["total_tokens_in"],
            row["total_tokens_out"],
            row["total_cost_usd"],
            row["total_duration_ms"],
            trace_id,
        ),
    )
    conn.commit()
    logger.info("Completed trace: %s (status=%s)", trace_id, status)


def get_traces(
    conn: sqlite3.Connection,
    platform_id: str,
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
) -> tuple[list[dict], int]:
    """List traces with pagination. Returns (traces, total_count)."""
    where = "WHERE t.platform_id = ?"
    params: list = [platform_id]
    if status_filter:
        where += " AND t.status = ?"
        params.append(status_filter)

    total = conn.execute(f"SELECT COUNT(*) FROM traces t {where}", params).fetchone()[0]

    sql = (
        f"SELECT t.*, "
        f"  COUNT(pr.run_id) as span_count, "
        f"  SUM(CASE WHEN pr.status='completed' THEN 1 ELSE 0 END) as completed_spans "
        f"FROM traces t "
        f"LEFT JOIN pipeline_runs pr ON pr.trace_id = t.trace_id "
        f"{where} "
        f"GROUP BY t.trace_id "
        f"ORDER BY t.started_at DESC "
        f"LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows], total


def get_trace_detail(conn: sqlite3.Connection, trace_id: str) -> dict | None:
    """Get a trace with its spans and eval scores. Returns None if not found."""
    trace_row = conn.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
    if not trace_row:
        return None

    spans = conn.execute(
        "SELECT run_id, node_id, status, tokens_in, tokens_out, cost_usd, "
        "duration_ms, error, started_at, completed_at "
        "FROM pipeline_runs WHERE trace_id=? ORDER BY started_at ASC",
        (trace_id,),
    ).fetchall()

    evals = conn.execute(
        "SELECT score_id, node_id, run_id, dimension, score, metadata, evaluated_at "
        "FROM eval_scores WHERE trace_id=? ORDER BY evaluated_at ASC",
        (trace_id,),
    ).fetchall()

    return {
        "trace": dict(trace_row),
        "spans": [dict(s) for s in spans],
        "eval_scores": [dict(e) for e in evals],
    }


# ══════════════════════════════════════
# Eval Scores (Observability — Epic 017)
# ══════════════════════════════════════


def insert_eval_score(
    conn: sqlite3.Connection,
    trace_id: str | None,
    platform_id: str,
    epic_id: str | None,
    node_id: str,
    run_id: str | None,
    dimension: str,
    score: float,
    metadata: str | None = None,
) -> str:
    """Insert an eval score. Skips if duplicate (run_id, dimension). Returns score_id."""

    if run_id:
        existing = conn.execute(
            "SELECT score_id FROM eval_scores WHERE run_id=? AND dimension=?",
            (run_id, dimension),
        ).fetchone()
        if existing:
            logger.debug("Skipping duplicate eval score: run_id=%s, dimension=%s", run_id, dimension)
            return existing[0]

    score_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO eval_scores "
        "(score_id, trace_id, platform_id, epic_id, node_id, run_id, dimension, score, metadata, evaluated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (score_id, trace_id, platform_id, epic_id, node_id, run_id, dimension, score, metadata, _now()),
    )
    conn.commit()
    return score_id


def get_eval_scores(
    conn: sqlite3.Connection,
    platform_id: str,
    node_id: str | None = None,
    dimension: str | None = None,
    limit: int = 100,
) -> tuple[list[dict], int]:
    """Get eval scores with optional filters. Returns (scores, total_count)."""
    where = "WHERE platform_id = ?"
    params: list = [platform_id]
    if node_id:
        where += " AND node_id = ?"
        params.append(node_id)
    if dimension:
        where += " AND dimension = ?"
        params.append(dimension)

    total = conn.execute(f"SELECT COUNT(*) FROM eval_scores {where}", params).fetchone()[0]

    sql = f"SELECT * FROM eval_scores {where} ORDER BY evaluated_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows], total


# ══════════════════════════════════════
# Runs with Evals (flat node view)
# ══════════════════════════════════════


def get_runs_with_evals(
    conn: sqlite3.Connection,
    platform_id: str,
    limit: int = 100,
    offset: int = 0,
    status_filter: str | None = None,
    epic_filter: str | None = None,
) -> tuple[list[dict], int]:
    """List pipeline_runs with eval scores pivoted into an evals dict.

    Returns (runs, total_count). Each run has an 'evals' dict mapping
    dimension → score (latest score per dimension for that run).
    """
    where = "WHERE pr.platform_id = ?"
    params: list = [platform_id]
    if status_filter:
        where += " AND pr.status = ?"
        params.append(status_filter)
    if epic_filter:
        where += " AND pr.epic_id = ?"
        params.append(epic_filter)

    total = conn.execute(f"SELECT COUNT(*) FROM pipeline_runs pr {where}", params).fetchone()[0]

    rows = conn.execute(
        f"SELECT pr.run_id, pr.epic_id, pr.node_id, pr.status, pr.tokens_in, "
        f"pr.tokens_out, pr.cost_usd, pr.duration_ms, pr.error, "
        f"pr.started_at, pr.completed_at "
        f"FROM pipeline_runs pr {where} "
        f"ORDER BY pr.started_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    # Batch-fetch eval scores for these runs
    run_ids = [r["run_id"] for r in rows]
    eval_map: dict[str, dict[str, float]] = {}
    if run_ids:
        placeholders = ",".join("?" * len(run_ids))
        evals = conn.execute(
            f"SELECT run_id, dimension, score FROM eval_scores "
            f"WHERE run_id IN ({placeholders}) ORDER BY evaluated_at DESC",
            run_ids,
        ).fetchall()
        for e in evals:
            rid = e["run_id"]
            dim = e["dimension"]
            if rid not in eval_map:
                eval_map[rid] = {}
            # Keep first (latest due to ORDER BY DESC)
            if dim not in eval_map[rid]:
                eval_map[rid][dim] = e["score"]

    result = []
    for r in rows:
        d = dict(r)
        d["evals"] = eval_map.get(r["run_id"], {})
        result.append(d)

    return result, total


# ══════════════════════════════════════
# Stats & Cleanup (Observability — Epic 017)
# ══════════════════════════════════════


def get_stats(conn: sqlite3.Connection, platform_id: str, days: int = 30) -> dict:
    """Aggregate stats by day for a platform. Returns {stats, summary, top_nodes}.

    Aggregates from pipeline_runs (source of truth) instead of traces,
    because traces often have NULL metrics (cancelled/running traces
    never called complete_trace).
    """
    days = min(days, 90)
    day_offset = f"-{days} days"

    stats_rows = conn.execute(
        "SELECT "
        "  date(pr.started_at) as day, "
        "  COUNT(*) as runs, "
        "  SUM(pr.cost_usd) as total_cost, "
        "  SUM(pr.tokens_in) as total_tokens_in, "
        "  SUM(pr.tokens_out) as total_tokens_out, "
        "  AVG(pr.duration_ms) as avg_duration_ms "
        "FROM pipeline_runs pr "
        "WHERE pr.platform_id = ? AND pr.started_at >= date('now', ?) "
        "GROUP BY date(pr.started_at) "
        "ORDER BY day",
        (platform_id, day_offset),
    ).fetchall()

    summary_row = conn.execute(
        "SELECT "
        "  COUNT(*) as total_runs, "
        "  SUM(cost_usd) as total_cost, "
        "  SUM(tokens_in) as total_tokens_in, "
        "  SUM(tokens_out) as total_tokens_out, "
        "  AVG(cost_usd) as avg_cost_per_run, "
        "  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_runs "
        "FROM pipeline_runs "
        "WHERE platform_id = ? AND started_at >= date('now', ?)",
        (platform_id, day_offset),
    ).fetchone()

    top_nodes = conn.execute(
        "SELECT pr.node_id, "
        "  SUM(pr.cost_usd) as total_cost, "
        "  COUNT(*) as run_count "
        "FROM pipeline_runs pr "
        "WHERE pr.platform_id = ? AND pr.started_at >= date('now', ?) "
        "  AND pr.cost_usd > 0 "
        "GROUP BY pr.node_id "
        "ORDER BY total_cost DESC "
        "LIMIT 5",
        (platform_id, day_offset),
    ).fetchall()

    # Avg eval across all runs in the period (not limited by page size)
    avg_eval_row = conn.execute(
        "SELECT AVG(es.score) as avg_eval "
        "FROM eval_scores es "
        "JOIN pipeline_runs pr ON pr.run_id = es.run_id "
        "WHERE pr.platform_id = ? AND pr.started_at >= date('now', ?)",
        (platform_id, day_offset),
    ).fetchone()

    summary = dict(summary_row) if summary_row else {}
    summary["avg_eval"] = avg_eval_row["avg_eval"] if avg_eval_row else None

    return {
        "stats": [dict(r) for r in stats_rows],
        "summary": summary,
        "top_nodes": [dict(r) for r in top_nodes],
    }


def cleanup_old_data(conn: sqlite3.Connection, days: int = 90) -> dict:
    """Remove observability data older than `days`. Returns deleted counts."""
    cutoff = f"-{days} days"

    # Delete in dependency order: eval_scores, pipeline_runs (traced), traces
    # Also clean pre-017 pipeline_runs with trace_id IS NULL (analysis finding I3)
    r1 = conn.execute("DELETE FROM eval_scores WHERE evaluated_at < datetime('now', ?)", (cutoff,))
    eval_count = r1.rowcount

    r2 = conn.execute(
        "DELETE FROM pipeline_runs WHERE trace_id IN "
        "(SELECT trace_id FROM traces WHERE started_at < datetime('now', ?))",
        (cutoff,),
    )
    runs_traced = r2.rowcount

    r3 = conn.execute(
        "DELETE FROM pipeline_runs WHERE trace_id IS NULL AND started_at < datetime('now', ?)",
        (cutoff,),
    )
    runs_untraced = r3.rowcount

    r4 = conn.execute("DELETE FROM traces WHERE started_at < datetime('now', ?)", (cutoff,))
    trace_count = r4.rowcount

    conn.commit()
    result = {
        "eval_scores": eval_count,
        "pipeline_runs": runs_traced + runs_untraced,
        "traces": trace_count,
    }
    logger.info("Cleanup: deleted %s", result)
    return result
