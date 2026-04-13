"""Data retention logic for ProsauAI — LGPD compliance.

Purges expired data per ADR-018 retention rules:
- messages: DROP PARTITION (90d, monthly granularity → effective 90-120d)
- conversations (closed): batch DELETE (90d)
- eval_scores: batch DELETE (90d)
- Phoenix traces: batch DELETE on observability.spans (90d)
- admin.audit_log: NEVER purged automatically

Usage (library):
    from prosauai.ops.retention import run_retention
    result = await run_retention(conn, dry_run=True)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from time import monotonic

from prosauai.ops.partitions import (
    drop_expired_partitions,
    ensure_future_partitions,
    list_partitions,
)

try:
    import structlog

    log = structlog.get_logger("prosauai.ops.retention")
except ImportError:  # pragma: no cover
    log = logging.getLogger("prosauai.ops.retention")

# Retention defaults (days)
RETENTION_MESSAGES = 90
RETENTION_CONVERSATIONS = 90
RETENTION_EVAL_SCORES = 90
RETENTION_TRACES = 90
BATCH_SIZE = 1000


@dataclass
class RetentionResult:
    """Outcome of a retention run."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rows_purged: dict[str, int] = field(default_factory=dict)
    partitions_dropped: list[str] = field(default_factory=list)
    partitions_created: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    dry_run: bool = True


async def purge_expired_messages(
    conn,
    retention_days: int = RETENTION_MESSAGES,
    dry_run: bool = True,
    *,
    today=None,
) -> tuple[list[str], list[str]]:
    """Purge expired message partitions and ensure future ones exist.

    Returns:
        Tuple of (dropped_partitions, created_partitions).
    """
    if dry_run:
        # List what would be dropped
        parts = await list_partitions(conn, "prosauai.messages")
        from datetime import date, timedelta

        today_val = today or date.today()
        threshold = today_val - timedelta(days=retention_days)
        eligible = []
        estimated_rows = 0
        for p in parts:
            suffix = p.name.rsplit("_", 2)
            if len(suffix) < 3:
                continue
            try:
                year, month = int(suffix[-2]), int(suffix[-1])
            except ValueError:
                continue
            end_year = year + month // 12
            end_month = month % 12 + 1
            partition_end = date(end_year, end_month, 1)
            if partition_end <= threshold:
                eligible.append(p.name)
                estimated_rows += p.row_count

        log.info(
            "retention_check",
            table="messages",
            partitions_eligible=len(eligible),
            estimated_rows=estimated_rows,
            dry_run=True,
        )
        return eligible, []

    dropped = await drop_expired_partitions(conn, "prosauai.messages", retention_days, today=today)
    created = await ensure_future_partitions(conn, "prosauai.messages", months_ahead=3, today=today)
    return dropped, created


async def purge_expired_conversations(
    conn,
    retention_days: int = RETENTION_CONVERSATIONS,
    dry_run: bool = True,
) -> int:
    """Purge closed conversations older than retention period.

    Uses batch DELETE with LIMIT to bound lock duration.

    Returns:
        Total rows deleted.
    """
    if dry_run:
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM prosauai.conversations "
            "WHERE status = 'closed' "
            "AND closed_at < (now() AT TIME ZONE 'UTC') - $1 * INTERVAL '1 day'",
            retention_days,
        )
        eligible = row["cnt"] if row else 0
        log.info(
            "retention_check",
            table="conversations",
            rows_eligible=eligible,
            dry_run=True,
        )
        return 0

    total = 0
    while True:
        result = await conn.execute(
            "DELETE FROM prosauai.conversations "
            "WHERE id IN ("
            "  SELECT id FROM prosauai.conversations "
            "  WHERE status = 'closed' "
            "  AND closed_at < (now() AT TIME ZONE 'UTC') - $1 * INTERVAL '1 day' "
            "  LIMIT $2"
            ")",
            retention_days,
            BATCH_SIZE,
        )
        # asyncpg returns "DELETE N"
        deleted = int(result.split()[-1])
        total += deleted
        if deleted < BATCH_SIZE:
            break

    if total > 0:
        log.info(
            "rows_purged",
            table="conversations",
            rows_removed=total,
            batch_size=BATCH_SIZE,
        )
    return total


async def purge_expired_eval_scores(
    conn,
    retention_days: int = RETENTION_EVAL_SCORES,
    dry_run: bool = True,
) -> int:
    """Purge eval_scores older than retention period.

    Uses batch DELETE with LIMIT to bound lock duration.

    Returns:
        Total rows deleted.
    """
    if dry_run:
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM prosauai.eval_scores "
            "WHERE created_at < (now() AT TIME ZONE 'UTC') - $1 * INTERVAL '1 day'",
            retention_days,
        )
        eligible = row["cnt"] if row else 0
        log.info(
            "retention_check",
            table="eval_scores",
            rows_eligible=eligible,
            dry_run=True,
        )
        return 0

    total = 0
    while True:
        result = await conn.execute(
            "DELETE FROM prosauai.eval_scores "
            "WHERE id IN ("
            "  SELECT id FROM prosauai.eval_scores "
            "  WHERE created_at < (now() AT TIME ZONE 'UTC') - $1 * INTERVAL '1 day' "
            "  LIMIT $2"
            ")",
            retention_days,
            BATCH_SIZE,
        )
        deleted = int(result.split()[-1])
        total += deleted
        if deleted < BATCH_SIZE:
            break

    if total > 0:
        log.info(
            "rows_purged",
            table="eval_scores",
            rows_removed=total,
            batch_size=BATCH_SIZE,
        )
    return total


async def purge_expired_traces(
    conn,
    retention_days: int = RETENTION_TRACES,
    dry_run: bool = True,
) -> int:
    """Purge Phoenix traces from observability schema.

    Skips silently if the observability.spans table does not exist
    (Phoenix may not have been initialized yet).

    Returns:
        Total rows deleted.
    """
    # Check if observability.spans exists
    exists = await conn.fetchval(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.tables "
        "  WHERE table_schema = 'observability' AND table_name = 'spans'"
        ")"
    )
    if not exists:
        log.info("retention_check", table="traces", status="skipped", reason="observability.spans not found")
        return 0

    if dry_run:
        row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM observability.spans "
            "WHERE start_time < (now() AT TIME ZONE 'UTC') - $1 * INTERVAL '1 day'",
            retention_days,
        )
        eligible = row["cnt"] if row else 0
        log.info(
            "retention_check",
            table="traces",
            rows_eligible=eligible,
            dry_run=True,
        )
        return 0

    total = 0
    while True:
        result = await conn.execute(
            "DELETE FROM observability.spans "
            "WHERE ctid IN ("
            "  SELECT ctid FROM observability.spans "
            "  WHERE start_time < (now() AT TIME ZONE 'UTC') - $1 * INTERVAL '1 day' "
            "  LIMIT $2"
            ")",
            retention_days,
            BATCH_SIZE,
        )
        deleted = int(result.split()[-1])
        total += deleted
        if deleted < BATCH_SIZE:
            break

    if total > 0:
        log.info(
            "rows_purged",
            table="traces",
            rows_removed=total,
            batch_size=BATCH_SIZE,
        )
    return total


async def run_retention(
    conn,
    dry_run: bool = True,
    *,
    today=None,
) -> RetentionResult:
    """Orchestrate all retention purge functions.

    Args:
        conn: asyncpg connection (should have BYPASSRLS for real purge).
        dry_run: If True, list what would be purged without executing.
        today: Override date for testing (messages partition logic).

    Returns:
        RetentionResult with totals.
    """
    result = RetentionResult(dry_run=dry_run)
    t0 = monotonic()

    log.info("retention_run_start", run_id=result.run_id, dry_run=dry_run)

    errors: list[str] = []

    # 1. Messages (partitions)
    try:
        dropped, created = await purge_expired_messages(conn, dry_run=dry_run, today=today)
        result.partitions_dropped = dropped
        result.partitions_created = created
    except Exception:
        log.exception("retention_error", table="messages")
        errors.append("messages")

    # 2. Conversations (batch DELETE)
    try:
        conv_purged = await purge_expired_conversations(conn, dry_run=dry_run)
        if conv_purged > 0:
            result.rows_purged["conversations"] = conv_purged
    except Exception:
        log.exception("retention_error", table="conversations")
        errors.append("conversations")

    # 3. Eval scores (batch DELETE)
    try:
        eval_purged = await purge_expired_eval_scores(conn, dry_run=dry_run)
        if eval_purged > 0:
            result.rows_purged["eval_scores"] = eval_purged
    except Exception:
        log.exception("retention_error", table="eval_scores")
        errors.append("eval_scores")

    # 4. Phoenix traces (batch DELETE)
    try:
        traces_purged = await purge_expired_traces(conn, dry_run=dry_run)
        if traces_purged > 0:
            result.rows_purged["traces"] = traces_purged
    except Exception:
        log.exception("retention_error", table="traces")
        errors.append("traces")

    result.duration_ms = (monotonic() - t0) * 1000

    total_rows = sum(result.rows_purged.values())
    log_fn = log.warning if errors else log.info
    log_fn(
        "retention_run_complete",
        run_id=result.run_id,
        duration_ms=round(result.duration_ms, 1),
        total_rows_purged=total_rows,
        partitions_dropped=len(result.partitions_dropped),
        partitions_created=len(result.partitions_created),
        dry_run=dry_run,
        errors=errors or None,
    )

    if errors and not dry_run:
        raise RuntimeError(f"Retention errors in: {', '.join(errors)}")

    return result
