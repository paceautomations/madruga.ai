"""
db_pipeline.py — Platform registry, pipeline/epic CRUD, run tracking, gate management.

Imports from db_core only. No imports from db_decisions or db_observability.
"""

from __future__ import annotations

import glob as glob_mod
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

from config import REPO_ROOT
from db_core import _file_mtime_iso, _now, _validate_identifiers, compute_file_hash, transaction

logger = logging.getLogger(__name__)

# Mapping from freeform pitch.md status values to DB CHECK constraint values.
# "planned" maps to "proposed" intentionally — the DB uses a smaller set of
# canonical statuses (proposed/in_progress/shipped/blocked/cancelled) while
# roadmap docs may use friendlier terms like "planned" or "done".
_EPIC_STATUS_MAP = {
    "proposed": "proposed",
    "planned": "proposed",
    "drafted": "drafted",
    "draft": "drafted",
    "in_progress": "in_progress",
    "in progress": "in_progress",
    "shipped": "shipped",
    "done": "shipped",
    "blocked": "blocked",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}

# Claude's duration_ms is inference-only and can be wildly low (4s reported vs
# 16min real). When below this threshold, complete_run() substitutes wall-clock.
_WALL_CLOCK_THRESHOLD_MS = 10_000

# Fields allowed in complete_run() updates — validated at import time to prevent SQL injection
_COMPLETE_RUN_FIELDS = frozenset(
    {"tokens_in", "tokens_out", "cost_usd", "duration_ms", "error", "output_lines", "dispatch_log"}
)
_validate_identifiers(*_COMPLETE_RUN_FIELDS)


# ══════════════════════════════════════
# Platforms
# ══════════════════════════════════════


def upsert_platform(
    conn: sqlite3.Connection,
    platform_id: str,
    *,
    name: str = "",
    repo_path: str = "",
    title: str = "",
    lifecycle: str = "design",
    metadata: str = "{}",
    repo_org: str | None = None,
    repo_name: str | None = None,
    base_branch: str | None = None,
    epic_branch_prefix: str | None = None,
    tags_json: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO platforms
           (platform_id, name, title, lifecycle, repo_path, metadata,
            repo_org, repo_name, base_branch, epic_branch_prefix, tags_json,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(platform_id) DO UPDATE SET
             name = excluded.name,
             title = excluded.title,
             lifecycle = excluded.lifecycle,
             repo_path = excluded.repo_path,
             metadata = excluded.metadata,
             repo_org = COALESCE(excluded.repo_org, platforms.repo_org),
             repo_name = COALESCE(excluded.repo_name, platforms.repo_name),
             base_branch = COALESCE(excluded.base_branch, platforms.base_branch),
             epic_branch_prefix = COALESCE(excluded.epic_branch_prefix, platforms.epic_branch_prefix),
             tags_json = COALESCE(excluded.tags_json, platforms.tags_json),
             updated_at = excluded.updated_at
        """,
        (
            platform_id,
            name or platform_id,
            title,
            lifecycle,
            repo_path,
            metadata,
            repo_org,
            repo_name,
            base_branch,
            epic_branch_prefix,
            tags_json,
            _now(),
            _now(),
        ),
    )
    conn.commit()
    logger.info("Upserted platform: %s", platform_id)


def get_platform(conn: sqlite3.Connection, platform_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM platforms WHERE platform_id=?", (platform_id,)).fetchone()
    return dict(row) if row else None


# ══════════════════════════════════════
# Local Config (machine-specific settings)
# ══════════════════════════════════════


def set_local_config(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Set a machine-local config value (e.g., active_platform, repos_base_dir)."""
    conn.execute(
        """INSERT INTO local_config (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET
             value = excluded.value,
             updated_at = excluded.updated_at
        """,
        (key, value, _now()),
    )
    conn.commit()


def get_local_config(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    """Get a machine-local config value."""
    row = conn.execute("SELECT value FROM local_config WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def get_active_platform(conn: sqlite3.Connection) -> str | None:
    """Shorthand for getting the active platform from local_config."""
    return get_local_config(conn, "active_platform")


def resolve_repo_path(conn: sqlite3.Connection, platform_id: str) -> str:
    """Resolve the local filesystem path for a platform's code repository.

    Resolution order:
    1. If platform has repo_org + repo_name → {repos_base_dir}/{repo_org}/{repo_name}
    2. If platform's repo_name matches its own id (self-ref) → REPO_ROOT
    3. Fallback → REPO_ROOT / "platforms" / platform_id
    """
    platform = get_platform(conn, platform_id)
    if not platform:
        return str(REPO_ROOT / "platforms" / platform_id)

    repo_org = platform.get("repo_org")
    repo_name = platform.get("repo_name")

    if repo_org and repo_name:
        # Check self-referencing (code lives in this repo)
        if repo_name == "madruga.ai" or platform.get("repo_path") == ".":
            return str(REPO_ROOT)
        # Convention: {repos_base_dir}/{org}/{repo_name}
        base = get_local_config(conn, "repos_base_dir", str(REPO_ROOT.parent.parent))
        return str(Path(base).expanduser() / repo_org / repo_name)

    # Legacy fallback: platform dir inside this repo
    return str(REPO_ROOT / "platforms" / platform_id)


# ══════════════════════════════════════
# Pipeline Nodes (DAG Level 1)
# ══════════════════════════════════════


def upsert_pipeline_node(
    conn: sqlite3.Connection,
    platform_id: str,
    node_id: str,
    status: str = "pending",
    **kwargs,
) -> None:
    conn.execute(
        """INSERT INTO pipeline_nodes
           (platform_id, node_id, status, output_hash, input_hashes,
            output_files, completed_at, completed_by, line_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(platform_id, node_id) DO UPDATE SET
             status = excluded.status,
             output_hash = COALESCE(excluded.output_hash, pipeline_nodes.output_hash),
             input_hashes = COALESCE(excluded.input_hashes, pipeline_nodes.input_hashes),
             output_files = COALESCE(excluded.output_files, pipeline_nodes.output_files),
             completed_at = COALESCE(excluded.completed_at, pipeline_nodes.completed_at),
             completed_by = COALESCE(excluded.completed_by, pipeline_nodes.completed_by),
             line_count = COALESCE(excluded.line_count, pipeline_nodes.line_count)
        """,
        (
            platform_id,
            node_id,
            status,
            kwargs.get("output_hash"),
            kwargs.get("input_hashes"),
            kwargs.get("output_files"),
            kwargs.get("completed_at"),
            kwargs.get("completed_by"),
            kwargs.get("line_count"),
        ),
    )
    conn.commit()


def get_pipeline_nodes(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM pipeline_nodes WHERE platform_id=? ORDER BY node_id",
        (platform_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Epics
# ══════════════════════════════════════


_UPSERT_EPIC_STATUS_UNSET = object()


def upsert_epic(conn: sqlite3.Connection, platform_id: str, epic_id: str, title: str = "", **kwargs) -> None:
    """Upsert an epic row.

    IMPORTANT: When ``status`` is not explicitly provided, this function
    PRESERVES the existing DB status instead of overwriting it with the
    previous default ``"proposed"``. Background: the old behavior silently
    regressed in_progress/drafted epics whenever callers did a partial
    upsert (e.g. post_save.py auto-setting branch_name). Postmortem:
    ``madruga-ai/024-sequential-execution-ux`` was auto-dispatched by easter
    because its ``drafted`` status got clobbered to ``proposed`` via this
    foot-gun, then compute_epic_status auto-promoted ``proposed`` →
    ``in_progress`` once an epic_node was backfilled.

    On INSERT of a brand-new row with no status provided, falls back to
    the schema default ``'proposed'``.
    """
    status = kwargs.get("status", _UPSERT_EPIC_STATUS_UNSET)
    now = _now()

    if status is _UPSERT_EPIC_STATUS_UNSET:
        # Status not provided — do a two-branch update that never touches status.
        existing = conn.execute(
            "SELECT 1 FROM epics WHERE platform_id=? AND epic_id=?",
            (platform_id, epic_id),
        ).fetchone()
        if existing is None:
            # Brand-new row — must provide status (schema is NOT NULL).
            conn.execute(
                """INSERT INTO epics
                   (platform_id, epic_id, title, status, priority, branch_name,
                    file_path, delivered_at, created_at, updated_at)
                   VALUES (?, ?, ?, 'proposed', ?, ?, ?, ?, ?, ?)
                """,
                (
                    platform_id,
                    epic_id,
                    title,
                    kwargs.get("priority"),
                    kwargs.get("branch_name"),
                    kwargs.get("file_path"),
                    kwargs.get("delivered_at"),
                    now,
                    now,
                ),
            )
        else:
            # Existing row — update title/priority/branch_name/file_path/delivered_at
            # but NEVER touch status.
            conn.execute(
                """UPDATE epics SET
                     title = ?,
                     priority = COALESCE(?, priority),
                     branch_name = COALESCE(?, branch_name),
                     file_path = COALESCE(?, file_path),
                     delivered_at = COALESCE(?, delivered_at),
                     updated_at = ?
                   WHERE platform_id=? AND epic_id=?
                """,
                (
                    title,
                    kwargs.get("priority"),
                    kwargs.get("branch_name"),
                    kwargs.get("file_path"),
                    kwargs.get("delivered_at"),
                    now,
                    platform_id,
                    epic_id,
                ),
            )
        conn.commit()
        return

    # Explicit status provided — original upsert behavior.
    conn.execute(
        """INSERT INTO epics
           (platform_id, epic_id, title, status, priority, branch_name, file_path,
            delivered_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(platform_id, epic_id) DO UPDATE SET
             title = excluded.title,
             status = excluded.status,
             priority = COALESCE(excluded.priority, epics.priority),
             branch_name = COALESCE(excluded.branch_name, epics.branch_name),
             file_path = COALESCE(excluded.file_path, epics.file_path),
             delivered_at = COALESCE(excluded.delivered_at, epics.delivered_at),
             updated_at = excluded.updated_at
        """,
        (
            platform_id,
            epic_id,
            title,
            status,
            kwargs.get("priority"),
            kwargs.get("branch_name"),
            kwargs.get("file_path"),
            kwargs.get("delivered_at"),
            now,
            now,
        ),
    )
    conn.commit()


def get_epics(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM epics WHERE platform_id=? ORDER BY epic_id",
        (platform_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Epic Nodes (DAG Level 2)
# ══════════════════════════════════════


def upsert_epic_node(
    conn: sqlite3.Connection,
    platform_id: str,
    epic_id: str,
    node_id: str,
    status: str = "pending",
    **kwargs,
) -> None:
    conn.execute(
        """INSERT INTO epic_nodes
           (platform_id, epic_id, node_id, status, output_hash, completed_at, completed_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(platform_id, epic_id, node_id) DO UPDATE SET
             status = excluded.status,
             output_hash = COALESCE(excluded.output_hash, epic_nodes.output_hash),
             completed_at = COALESCE(excluded.completed_at, epic_nodes.completed_at),
             completed_by = COALESCE(excluded.completed_by, epic_nodes.completed_by)
        """,
        (
            platform_id,
            epic_id,
            node_id,
            status,
            kwargs.get("output_hash"),
            kwargs.get("completed_at"),
            kwargs.get("completed_by"),
        ),
    )
    conn.commit()


def get_epic_nodes(conn: sqlite3.Connection, platform_id: str, epic_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM epic_nodes WHERE platform_id=? AND epic_id=? ORDER BY node_id",
        (platform_id, epic_id),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Artifact Provenance
# ══════════════════════════════════════


def insert_provenance(
    conn: sqlite3.Connection,
    platform_id: str,
    file_path: str,
    generated_by: str,
    **kwargs,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO artifact_provenance "
        "(platform_id, file_path, generated_by, epic_id, output_hash, generated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            platform_id,
            file_path,
            generated_by,
            kwargs.get("epic_id"),
            kwargs.get("output_hash"),
            _now(),
        ),
    )
    conn.commit()


def get_provenance(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM artifact_provenance WHERE platform_id=? ORDER BY file_path",
        (platform_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Pipeline Runs
# ══════════════════════════════════════


def insert_run(conn: sqlite3.Connection, platform_id: str, node_id: str, **kwargs) -> str:
    run_id = kwargs.get("run_id") or os.urandom(4).hex()
    conn.execute(
        "INSERT INTO pipeline_runs "
        "(run_id, platform_id, epic_id, node_id, status, agent, "
        "tokens_in, tokens_out, cost_usd, duration_ms, error, trace_id, output_lines, started_at) "
        "VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            platform_id,
            kwargs.get("epic_id"),
            node_id,
            kwargs.get("agent"),
            kwargs.get("tokens_in"),
            kwargs.get("tokens_out"),
            kwargs.get("cost_usd"),
            kwargs.get("duration_ms"),
            kwargs.get("error"),
            kwargs.get("trace_id"),
            kwargs.get("output_lines"),
            _now(),
        ),
    )
    conn.commit()
    return run_id


def complete_run(conn: sqlite3.Connection, run_id: str, status: str = "completed", **kwargs) -> None:
    completed_at = _now()
    # Wall-clock fallback: Claude's duration_ms is inference-only and can be
    # wildly low (4s reported vs 16min real). Substitute wall-clock when the
    # reported value is suspiciously short.
    reported = kwargs.get("duration_ms")
    if reported is not None and reported < _WALL_CLOCK_THRESHOLD_MS:
        row = conn.execute("SELECT started_at FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
        if row and row[0]:
            wall_ms = int(
                (datetime.fromisoformat(completed_at) - datetime.fromisoformat(row[0])).total_seconds() * 1000
            )
            if wall_ms > reported:
                kwargs["duration_ms"] = wall_ms
    sets = ["status=?", "completed_at=?"]
    vals: list = [status, completed_at]
    for field in _COMPLETE_RUN_FIELDS:
        if field in kwargs:
            sets.append(f"{field}=?")
            vals.append(kwargs[field])
    vals.append(run_id)
    conn.execute(f"UPDATE pipeline_runs SET {', '.join(sets)} WHERE run_id=?", vals)
    conn.commit()


def get_runs(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM pipeline_runs WHERE platform_id=? ORDER BY started_at",
        (platform_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Gate Management
# ══════════════════════════════════════


def approve_gate(conn: sqlite3.Connection, run_id: str) -> bool:
    """Approve a pending human gate. Returns True if a row was updated."""
    cur = conn.execute(
        "UPDATE pipeline_runs SET gate_status='approved', gate_resolved_at=? "
        "WHERE run_id=? AND gate_status='waiting_approval'",
        (_now(), run_id),
    )
    conn.commit()
    return cur.rowcount > 0


def reject_gate(conn: sqlite3.Connection, run_id: str) -> bool:
    """Reject a pending human gate. Returns True if a row was updated."""
    cur = conn.execute(
        "UPDATE pipeline_runs SET gate_status='rejected', gate_resolved_at=? "
        "WHERE run_id=? AND gate_status='waiting_approval'",
        (_now(), run_id),
    )
    conn.commit()
    return cur.rowcount > 0


def get_pending_gates(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    """List all runs with gate_status='waiting_approval' for a platform.

    Excludes cancelled/failed runs — stale gates must not block the scheduler.
    """
    rows = conn.execute(
        "SELECT run_id, platform_id, epic_id, node_id, gate_status, "
        "gate_notified_at, started_at FROM pipeline_runs "
        "WHERE platform_id=? AND gate_status='waiting_approval' "
        "AND status NOT IN ('cancelled', 'failed') ORDER BY started_at",
        (platform_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_resumable_nodes(conn: sqlite3.Connection, platform_id: str, epic_id: str | None = None) -> set[str]:
    """Return set of node_ids that are done or skipped (for resume).

    Note: approved gates are NOT included — 'approved' means 'ready to execute',
    not 'executed successfully'. The node must be dispatched, verified, and marked
    done in epic_nodes/pipeline_nodes before it counts as resumable.
    """
    if epic_id:
        rows = conn.execute(
            "SELECT node_id FROM epic_nodes WHERE platform_id=? AND epic_id=? AND status IN ('done', 'skipped')",
            (platform_id, epic_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT node_id FROM pipeline_nodes WHERE platform_id=? AND status IN ('done', 'skipped')",
            (platform_id,),
        ).fetchall()
    return {r[0] for r in rows}


# ══════════════════════════════════════
# Events
# ══════════════════════════════════════


def insert_event(
    conn: sqlite3.Connection,
    platform_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    **kwargs,
) -> int:
    cur = conn.execute(
        "INSERT INTO events "
        "(platform_id, entity_type, entity_id, action, actor, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            platform_id,
            entity_type,
            entity_id,
            action,
            kwargs.get("actor", "system"),
            json.dumps(kwargs.get("payload", {})),
            _now(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_events(
    conn: sqlite3.Connection,
    platform_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM events WHERE platform_id=?"
    params: list = [platform_id]
    if entity_type:
        sql += " AND entity_type=?"
        params.append(entity_type)
    if entity_id:
        sql += " AND entity_id=?"
        params.append(entity_id)
    sql += " ORDER BY created_at"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ══════════════════════════════════════
# Commits (Epic 023 — Commit Traceability)
# ══════════════════════════════════════


def insert_commit(
    conn: sqlite3.Connection,
    sha: str,
    message: str,
    author: str,
    platform_id: str,
    epic_id: str | None,
    source: str,
    committed_at: str,
    files_json: str,
) -> None:
    """Insert a commit record. Uses INSERT OR IGNORE for idempotency on SHA.

    Args:
        conn: SQLite connection.
        sha: Git commit SHA (or sha:platform_id composite for multi-platform).
        message: Commit message.
        author: Commit author name.
        platform_id: Platform this commit belongs to.
        epic_id: Epic slug (e.g. '023-commit-traceability') or None for ad-hoc.
        source: How the commit was captured ('hook', 'backfill', 'manual', 'reseed').
        committed_at: ISO 8601 timestamp of the commit.
        files_json: JSON string of affected file paths (e.g. '["src/main.py"]').
    """
    conn.execute(
        """INSERT OR IGNORE INTO commits
           (sha, message, author, platform_id, epic_id, source, committed_at, files_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sha, message, author, platform_id, epic_id, source, committed_at, files_json),
    )
    # NOTE: caller owns transaction boundary — call conn.commit() after batch inserts


def get_commits_by_epic(
    conn: sqlite3.Connection,
    epic_id: str,
    platform_id: str | None = None,
) -> list[dict]:
    """Return commits for a given epic, ordered by committed_at DESC.

    Args:
        conn: SQLite connection.
        epic_id: Epic slug (e.g. '023-commit-traceability').
        platform_id: Optional platform filter. If None, returns commits across all platforms.

    Returns:
        List of dicts with commit data. Empty list if no commits found.
    """
    sql = "SELECT * FROM commits WHERE epic_id=?"
    params: list = [epic_id]
    if platform_id is not None:
        sql += " AND platform_id=?"
        params.append(platform_id)
    sql += " ORDER BY committed_at DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_commits_by_platform(
    conn: sqlite3.Connection,
    platform_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Return commits for a given platform, paginated, ordered by committed_at DESC.

    Args:
        conn: SQLite connection.
        platform_id: Platform identifier (e.g. 'madruga-ai').
        limit: Maximum number of rows to return (default 100).
        offset: Number of rows to skip (default 0).

    Returns:
        List of dicts with commit data. Empty list if no commits found.
    """
    rows = conn.execute(
        "SELECT * FROM commits WHERE platform_id=? ORDER BY committed_at DESC LIMIT ? OFFSET ?",
        (platform_id, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def get_adhoc_commits(
    conn: sqlite3.Connection,
    platform_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return commits with no epic association (epic_id IS NULL), ordered by committed_at DESC.

    Args:
        conn: SQLite connection.
        platform_id: Optional platform filter. If None, returns ad-hoc commits across all platforms.
        limit: Maximum number of rows to return (default 100).

    Returns:
        List of dicts with commit data. Empty list if no ad-hoc commits found.
    """
    sql = "SELECT * FROM commits WHERE epic_id IS NULL"
    params: list = []
    if platform_id is not None:
        sql += " AND platform_id=?"
        params.append(platform_id)
    sql += " ORDER BY committed_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_commit_stats(
    conn: sqlite3.Connection,
    platform_id: str | None = None,
) -> dict:
    """Return aggregate commit statistics for the portal.

    Args:
        conn: SQLite connection.
        platform_id: Optional platform filter. If None, stats span all platforms.

    Returns:
        Dict with keys: total_commits, commits_per_epic (dict of epic_id→count),
        commits_per_platform (dict of platform_id→count),
        adhoc_count, adhoc_percentage (float 0-100, rounded to 1 decimal).
    """
    where = ""
    params: list = []
    if platform_id is not None:
        where = " WHERE platform_id=?"
        params = [platform_id]

    total = conn.execute(f"SELECT COUNT(*) FROM commits{where}", params).fetchone()[0]

    adhoc_sql = f"SELECT COUNT(*) FROM commits{where}{' AND' if where else ' WHERE'} epic_id IS NULL"
    adhoc_count = conn.execute(adhoc_sql, params).fetchone()[0]

    epic_rows = conn.execute(
        f"SELECT epic_id, COUNT(*) AS cnt FROM commits{where}"
        f"{' AND' if where else ' WHERE'} epic_id IS NOT NULL"
        " GROUP BY epic_id ORDER BY epic_id",
        params,
    ).fetchall()
    commits_per_epic = {row["epic_id"]: row["cnt"] for row in epic_rows}

    platform_rows = conn.execute(
        f"SELECT platform_id, COUNT(*) AS cnt FROM commits{where} GROUP BY platform_id",
        params,
    ).fetchall()
    commits_per_platform = {row["platform_id"]: row["cnt"] for row in platform_rows}

    return {
        "total_commits": total,
        "commits_per_epic": commits_per_epic,
        "commits_per_platform": commits_per_platform,
        "adhoc_count": adhoc_count,
        "adhoc_percentage": round(adhoc_count / total * 100, 1) if total > 0 else 0.0,
    }


def get_commits_paginated(
    conn: sqlite3.Connection,
    limit: int = 50,
    offset: int = 0,
    platform_id: str | None = None,
    epic_id: str | None = None,
    commit_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[dict], int]:
    """List commits with pagination and filters. Returns (commits, total_count).

    Args:
        conn: SQLite connection.
        limit: Max rows per page.
        offset: Rows to skip.
        platform_id: Filter by platform.
        epic_id: Filter by specific epic.
        commit_type: 'epic' (has epic_id) or 'adhoc' (epic_id IS NULL).
        date_from: Inclusive lower bound (ISO date or datetime).
        date_to: Inclusive upper bound (ISO date or datetime).

    Returns:
        Tuple of (list of commit dicts with files parsed, total matching count).
    """
    where_parts: list[str] = []
    params: list = []

    if platform_id is not None:
        where_parts.append("platform_id = ?")
        params.append(platform_id)
    if epic_id is not None:
        where_parts.append("epic_id = ?")
        params.append(epic_id)
    if commit_type == "epic":
        where_parts.append("epic_id IS NOT NULL")
    elif commit_type == "adhoc":
        where_parts.append("epic_id IS NULL")
    if date_from is not None:
        where_parts.append("committed_at >= ?")
        params.append(date_from)
    if date_to is not None:
        # If only a date (no time), include the full day
        val = date_to if "T" in date_to else date_to + "T23:59:59Z"
        where_parts.append("committed_at <= ?")
        params.append(val)

    where = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    total = conn.execute(f"SELECT COUNT(*) FROM commits{where}", params).fetchone()[0]

    sql = f"SELECT * FROM commits{where} ORDER BY committed_at DESC LIMIT ? OFFSET ?"
    rows = conn.execute(sql, [*params, limit, offset]).fetchall()

    commits = []
    for row in rows:
        d = dict(row)
        try:
            d["files"] = json.loads(d.pop("files_json"))
        except (json.JSONDecodeError, TypeError):
            d["files"] = []
            d.pop("files_json", None)
        commits.append(d)

    return commits, total


# ══════════════════════════════════════
# Staleness & Status
# ══════════════════════════════════════


def get_stale_nodes(conn: sqlite3.Connection, platform_id: str, dag_edges: dict[str, list[str]]) -> list[dict]:
    """Return nodes whose dependencies completed after them.

    dag_edges: {node_id: [dep_node_id, ...]} parsed from pipeline.yaml.
    """
    nodes = {n["node_id"]: n for n in get_pipeline_nodes(conn, platform_id)}
    stale = []
    for node_id, deps in dag_edges.items():
        node = nodes.get(node_id)
        if not node or node["status"] != "done" or not node["completed_at"]:
            continue
        for dep_id in deps:
            dep = nodes.get(dep_id)
            if dep and dep["completed_at"] and dep["completed_at"] > node["completed_at"]:
                stale.append(
                    {
                        "node_id": node_id,
                        "stale_reason": f"{dep_id} completed at {dep['completed_at']} > {node['completed_at']}",
                        "dep_node_id": dep_id,
                    }
                )
                break
    return stale


def repair_timestamps(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    """Reset completed_at from events table where a more accurate timestamp exists.

    Returns list of repaired nodes with old and new timestamps.
    """
    nodes = get_pipeline_nodes(conn, platform_id)
    repaired = []
    for node in nodes:
        if node["status"] != "done" or not node["completed_at"]:
            continue
        # Find the latest 'completed' event for this node (set by actual skill execution)
        row = conn.execute(
            """SELECT created_at FROM events
               WHERE platform_id=? AND entity_type='node' AND entity_id=? AND action='completed'
               ORDER BY created_at DESC LIMIT 1""",
            (platform_id, node["node_id"]),
        ).fetchone()
        if row and row["created_at"] != node["completed_at"]:
            conn.execute(
                "UPDATE pipeline_nodes SET completed_at=? WHERE platform_id=? AND node_id=?",
                (row["created_at"], platform_id, node["node_id"]),
            )
            repaired.append(
                {
                    "node_id": node["node_id"],
                    "old": node["completed_at"],
                    "new": row["created_at"],
                }
            )
    conn.commit()
    return repaired


def _count_node_statuses(rows: list[dict]) -> tuple[int, dict[str, int]]:
    """Count rows by status field. Returns (total, counts_by_status)."""
    counts: dict[str, int] = {"done": 0, "pending": 0, "stale": 0, "blocked": 0, "skipped": 0}
    for r in rows:
        s = r["status"]
        counts[s] = counts.get(s, 0) + 1
    return len(rows), counts


def get_platform_status(conn: sqlite3.Connection, platform_id: str) -> dict:
    total, counts = _count_node_statuses(get_pipeline_nodes(conn, platform_id))
    return {
        "platform_id": platform_id,
        "total_nodes": total,
        **counts,
        "progress_pct": round((counts["done"] + counts["skipped"]) / total * 100, 1) if total else 0,
    }


def get_epic_status(conn: sqlite3.Connection, platform_id: str, epic_id: str) -> dict:
    total, counts = _count_node_statuses(get_epic_nodes(conn, platform_id, epic_id))
    return {
        "platform_id": platform_id,
        "epic_id": epic_id,
        "total_nodes": total,
        **counts,
        "progress_pct": round((counts["done"] + counts["skipped"]) / total * 100, 1) if total else 0,
    }


def compute_epic_status(
    conn: sqlite3.Connection,
    platform_id: str,
    epic_id: str,
    required_node_ids: set[str],
    current_status: str,
    completed_ids: set[str] | None = None,
) -> tuple[str, str | None]:
    """Derive epic status from epic_nodes completion.

    Returns (new_status, delivered_at_or_None).
    Pass completed_ids to avoid a redundant DB query when caller already has the data.
    Safety: never regresses shipped to a lesser status.
    """
    if current_status in ("blocked", "cancelled", "shipped", "drafted"):
        return current_status, None

    if completed_ids is None:
        nodes = get_epic_nodes(conn, platform_id, epic_id)
        completed_ids = {n["node_id"] for n in nodes if n["status"] in ("done", "skipped")}

    if required_node_ids and required_node_ids.issubset(completed_ids):
        delivered_at = _now()[:10]
        return "shipped", delivered_at
    elif len(completed_ids) > 0 and current_status == "proposed":
        return "in_progress", None
    return current_status, None


def _resolve_epic_outputs(outputs: list[str], epic_id: str) -> list[str]:
    """Resolve {epic} placeholder in output patterns."""
    return [o.replace("{epic}", f"epics/{epic_id}") for o in outputs]


def _is_valid_output(file_path: Path) -> bool:
    """Check if output file has valid content (not raw claude JSON or empty).

    Prevents seed from marking nodes as done when output files contain
    garbage data (e.g., raw claude -p --output-format json metadata).
    """
    try:
        content = file_path.read_text(encoding="utf-8")[:500]
    except (OSError, UnicodeDecodeError):
        return False
    if len(content) < 50:
        return False
    # Raw claude -p --output-format json output — not real content
    if content.lstrip().startswith('{"type":"result"'):
        return False
    # Markdown files should have at least one heading
    if file_path.suffix == ".md" and "#" not in content:
        return False
    return True


def seed_epic_nodes_from_disk(
    txn: sqlite3.Connection,
    platform_id: str,
    epic_id: str,
    pdir: Path,
    epic_cycle: list[dict],
    existing_epic_nodes: dict[str, dict] | None = None,
) -> set[str]:
    """Seed epic_nodes from output files on disk. Returns set of completed node IDs."""
    if existing_epic_nodes is None:
        existing_epic_nodes = {n["node_id"]: n for n in get_epic_nodes(txn, platform_id, epic_id)}

    completed = {nid for nid, n in existing_epic_nodes.items() if n["status"] in ("done", "skipped")}

    for node_cfg in epic_cycle:
        nid = node_cfg["id"]
        outputs = node_cfg.get("outputs", [])
        resolved = _resolve_epic_outputs(outputs, epic_id)
        exists = all((pdir / r).exists() for r in resolved) if resolved else False
        if not exists:
            continue
        first_file = pdir / resolved[0]
        if not _is_valid_output(first_file):
            logger.debug("Skipping invalid output for %s: %s", nid, first_file)
            continue
        en_existing = existing_epic_nodes.get(nid)
        en_completed_at = None
        if not (en_existing and en_existing.get("completed_at")):
            en_completed_at = _file_mtime_iso(first_file)
        upsert_epic_node(
            txn,
            platform_id,
            epic_id,
            nid,
            "done",
            output_hash=compute_file_hash(first_file),
            completed_by=en_existing["completed_by"] if en_existing else f"seed:{node_cfg['skill']}",
            completed_at=en_completed_at,
        )
        completed.add(nid)

    # Backfill missing nodes so total always reflects the full cycle.
    # For shipped epics, mark missing nodes as "skipped" to keep 100% progress.
    epic_row = txn.execute(
        "SELECT status FROM epics WHERE platform_id=? AND epic_id=?",
        (platform_id, epic_id),
    ).fetchone()
    backfill_status = "skipped" if epic_row and epic_row["status"] == "shipped" else "pending"
    for node_cfg in epic_cycle:
        nid = node_cfg["id"]
        if nid not in existing_epic_nodes and nid not in completed:
            upsert_epic_node(txn, platform_id, epic_id, nid, backfill_status)

    return completed


# ══════════════════════════════════════
# Seed from filesystem
# ══════════════════════════════════════


def seed_from_filesystem(conn: sqlite3.Connection, platform_id: str, platform_dir: str | Path) -> dict:
    """Import existing state from filesystem into DB. Idempotent.

    Uses transaction() to batch all writes into a single commit instead of
    committing after each upsert/insert (~80 individual commits for 1 platform).
    """
    pdir = Path(platform_dir)
    yaml_path = pdir / "platform.yaml"
    if not yaml_path.exists():
        logger.warning("platform.yaml not found at %s — skipping seed", yaml_path)
        return {"status": "skipped", "reason": "no platform.yaml"}

    with open(yaml_path) as f:
        manifest = yaml.safe_load(f)

    repo = manifest.get("repo", {})
    tags = manifest.get("tags", [])

    with transaction(conn) as txn:
        upsert_platform(
            txn,
            platform_id,
            name=manifest.get("name", platform_id),
            title=manifest.get("title", ""),
            lifecycle=manifest.get("lifecycle", "design"),
            repo_path=f"platforms/{platform_id}",
            metadata=json.dumps({k: manifest[k] for k in ("views", "serve", "build") if k in manifest}),
            repo_org=repo.get("org"),
            repo_name=repo.get("name"),
            base_branch=repo.get("base_branch"),
            epic_branch_prefix=repo.get("epic_branch_prefix"),
            tags_json=json.dumps(tags) if tags else None,
        )

        nodes_seeded = 0
        from config import load_pipeline

        pipeline = load_pipeline()

        # Load existing node timestamps so reseed never overwrites them
        existing_nodes = {n["node_id"]: n for n in get_pipeline_nodes(txn, platform_id)}

        for node in pipeline.get("nodes", []):
            nid = node["id"]
            outputs = node.get("outputs", [])
            pattern = node.get("output_pattern")
            if pattern:
                found = glob_mod.glob(str(pdir / pattern))
                exists = len(found) > 0
                output_files = [str(Path(f).relative_to(pdir)) for f in found]
            else:
                exists = all((pdir / o).exists() for o in outputs)
                output_files = outputs

            status = "done" if exists else "pending"
            output_hash = None
            if exists and outputs and not pattern:
                first_output = pdir / outputs[0]
                if first_output.exists():
                    output_hash = compute_file_hash(first_output)

            completed_at = None
            if status == "done" and output_files:
                existing = existing_nodes.get(nid)
                # Only use file mtime if the node has no existing completed_at
                if not (existing and existing.get("completed_at")):
                    first_file = pdir / output_files[0]
                    if first_file.exists():
                        completed_at = _file_mtime_iso(first_file)

            upsert_pipeline_node(
                txn,
                platform_id,
                nid,
                status,
                output_hash=output_hash,
                output_files=json.dumps(output_files),
                completed_by=node.get("skill"),
                completed_at=completed_at,
            )
            # Populate artifact_provenance for done nodes
            if status == "done":
                for ofile in output_files:
                    full_path = pdir / ofile
                    if full_path.exists() and full_path.is_file():
                        insert_provenance(
                            txn,
                            platform_id,
                            ofile,
                            generated_by=node.get("skill", f"madruga:{nid}"),
                            output_hash=compute_file_hash(full_path),
                        )
            insert_event(
                txn,
                platform_id,
                "node",
                nid,
                "seeded",
                actor="seed",
                payload={"status": status},
            )
            nodes_seeded += 1

        # DAG integrity: if a node is done, backfill its dependencies as done too.
        # This handles pre-existing artifacts created before the DAG was introduced.
        node_statuses = {
            n["id"]: "done"
            if all((pdir / o).exists() for o in n.get("outputs", []))
            or (n.get("output_pattern") and len(glob_mod.glob(str(pdir / n["output_pattern"]))) > 0)
            else "pending"
            for n in pipeline.get("nodes", [])
        }
        changed = True
        while changed:
            changed = False
            for node in pipeline.get("nodes", []):
                nid = node["id"]
                if node_statuses.get(nid) != "done":
                    continue
                for dep_id in node.get("depends", []):
                    if node_statuses.get(dep_id) == "pending":
                        node_statuses[dep_id] = "done"
                        dep_existing = existing_nodes.get(dep_id)
                        backfill_at = None if (dep_existing and dep_existing.get("completed_at")) else _now()
                        upsert_pipeline_node(
                            txn, platform_id, dep_id, "done", completed_by="seed-backfill", completed_at=backfill_at
                        )
                        changed = True

        epics_seeded = 0
        epics_dir = pdir / "epics"
        if epics_dir.exists():
            for epic_dir in sorted(epics_dir.iterdir()):
                pitch = epic_dir / "pitch.md"
                if epic_dir.is_dir() and pitch.exists():
                    epic_id = epic_dir.name
                    content = pitch.read_text(encoding="utf-8")

                    # Parse YAML frontmatter
                    frontmatter: dict = {}
                    if content.startswith("---"):
                        parts = content.split("---", 2)
                        if len(parts) >= 3:
                            try:
                                frontmatter = yaml.safe_load(parts[1]) or {}
                            except yaml.YAMLError:
                                pass

                    # Title: prefer frontmatter, fall back to first heading
                    title_line = str(frontmatter.get("title", "")).strip()
                    if not title_line:
                        for line in content.split("\n"):
                            if line.startswith("# "):
                                title_line = line[2:].strip()
                                break

                    # Status: map frontmatter value to DB constraint
                    raw_status = str(frontmatter.get("status", "")).lower().strip()
                    fs_status = _EPIC_STATUS_MAP.get(raw_status) or "proposed"

                    # Guard: never regress shipped→proposed via reseed.
                    # blocked/cancelled from filesystem are legitimate overrides.
                    existing_row = txn.execute(
                        "SELECT status FROM epics WHERE platform_id=? AND epic_id=?",
                        (platform_id, epic_id),
                    ).fetchone()
                    if existing_row and existing_row[0] == "shipped" and fs_status == "proposed":
                        fs_status = "shipped"

                    # Priority and delivery from frontmatter
                    priority = frontmatter.get("priority")
                    delivered_at = frontmatter.get("delivered_at")
                    if delivered_at is not None:
                        delivered_at = str(delivered_at).strip('"').strip("'")

                    upsert_epic(
                        txn,
                        platform_id,
                        epic_id,
                        title=title_line or epic_id,
                        file_path=f"epics/{epic_id}/pitch.md",
                        status=fs_status,
                        priority=priority,
                        delivered_at=delivered_at,
                    )

                    # Seed epic_nodes from output files on disk
                    epic_cycle = pipeline.get("epic_cycle", {}).get("nodes", [])
                    completed_ids = seed_epic_nodes_from_disk(txn, platform_id, epic_id, pdir, epic_cycle)

                    # Recalculate epic status from completed nodes
                    required_ids = {n["id"] for n in epic_cycle if not n.get("optional", False)}
                    new_status, new_delivered = compute_epic_status(
                        txn,
                        platform_id,
                        epic_id,
                        required_ids,
                        fs_status,
                        completed_ids=completed_ids,
                    )
                    if new_status != fs_status:
                        upsert_epic(
                            txn,
                            platform_id,
                            epic_id,
                            title=title_line or epic_id,
                            status=new_status,
                            delivered_at=new_delivered,
                        )

                    epics_seeded += 1

    logger.info("Seeded %s: %d nodes, %d epics", platform_id, nodes_seeded, epics_seeded)
    return {"status": "ok", "nodes": nodes_seeded, "epics": epics_seeded}
