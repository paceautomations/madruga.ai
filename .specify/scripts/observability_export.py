"""
observability_export.py — CSV export for observability data (traces, spans, evals).

Usage:
    from observability_export import export_csv
    csv_str = export_csv(conn, "madruga-ai", "traces", days=90)
"""

from __future__ import annotations

import csv
import io
import logging
import sqlite3

logger = logging.getLogger(__name__)

VALID_ENTITIES = ("traces", "spans", "evals")

_HEADERS = {
    "traces": [
        "trace_id",
        "platform_id",
        "epic_id",
        "mode",
        "status",
        "total_nodes",
        "completed_nodes",
        "total_tokens_in",
        "total_tokens_out",
        "total_cost_usd",
        "total_duration_ms",
        "started_at",
        "completed_at",
    ],
    "spans": [
        "run_id",
        "platform_id",
        "epic_id",
        "node_id",
        "trace_id",
        "status",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "duration_ms",
        "error",
        "started_at",
        "completed_at",
    ],
    "evals": [
        "score_id",
        "trace_id",
        "platform_id",
        "epic_id",
        "node_id",
        "run_id",
        "dimension",
        "score",
        "metadata",
        "evaluated_at",
    ],
}

_QUERIES = {
    "traces": (
        "SELECT {cols} FROM traces WHERE platform_id = ? AND started_at >= date('now', ?) ORDER BY started_at DESC"
    ),
    "spans": (
        "SELECT {cols} FROM pipeline_runs "
        "WHERE platform_id = ? AND started_at >= date('now', ?) "
        "ORDER BY started_at DESC"
    ),
    "evals": (
        "SELECT {cols} FROM eval_scores "
        "WHERE platform_id = ? AND evaluated_at >= date('now', ?) "
        "ORDER BY evaluated_at DESC"
    ),
}


def export_csv(conn: sqlite3.Connection, platform_id: str, entity: str, days: int = 90) -> str:
    """Export observability data as a CSV string.

    Args:
        conn: SQLite connection with row_factory=sqlite3.Row.
        platform_id: Platform to export.
        entity: One of 'traces', 'spans', or 'evals'.
        days: How many days back to include (default 90).

    Returns:
        CSV string with headers on the first line.

    Raises:
        ValueError: If entity is not one of the valid options.
    """
    if entity not in VALID_ENTITIES:
        raise ValueError(f"entity must be one of: {', '.join(VALID_ENTITIES)}")

    headers = _HEADERS[entity]
    cols = ", ".join(headers)
    sql = _QUERIES[entity].format(cols=cols)
    cutoff = f"-{days} days"

    rows = conn.execute(sql, (platform_id, cutoff)).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row[h] for h in headers])

    logger.info("Exported %d %s rows for platform %s", len(rows), entity, platform_id)
    return buf.getvalue()
