"""Partition manager for ProsauAI — monthly RANGE partitions on messages.

Handles creation of future partitions, dropping expired ones, and listing
existing partitions with row counts.

Usage (library):
    from prosauai.ops.partitions import ensure_future_partitions, drop_expired_partitions
    await ensure_future_partitions(conn, "prosauai.messages", months_ahead=3)
    dropped = await drop_expired_partitions(conn, "prosauai.messages", retention_days=90)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta

try:
    import structlog

    log = structlog.get_logger("prosauai.ops.partitions")
except ImportError:  # pragma: no cover
    log = logging.getLogger("prosauai.ops.partitions")


_VALID_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_.]*$")


def _validate_table(table: str) -> None:
    """Validate table name to prevent SQL injection in DDL statements."""
    if not _VALID_IDENTIFIER.match(table):
        raise ValueError(f"Invalid table identifier: {table!r}")


@dataclass
class PartitionInfo:
    """Metadata about a single partition."""

    name: str
    row_count: int


def _month_range(base: date, offset_months: int) -> tuple[date, date]:
    """Return (start, end) dates for the month at base + offset_months."""
    # Advance month by offset
    year = base.year + (base.month - 1 + offset_months) // 12
    month = (base.month - 1 + offset_months) % 12 + 1
    start = date(year, month, 1)
    # end = first day of next month
    end_year = year + (month) // 12
    end_month = (month) % 12 + 1
    end = date(end_year, end_month, 1)
    return start, end


def _partition_name(table: str, start: date) -> str:
    """Generate partition table name: schema.table_YYYY_MM."""
    # table is like "prosauai.messages"
    return f"{table}_{start.strftime('%Y_%m')}"


async def ensure_future_partitions(
    conn,
    table: str = "prosauai.messages",
    months_ahead: int = 3,
    *,
    today: date | None = None,
) -> list[str]:
    """Create monthly partitions for the next N months (IF NOT EXISTS).

    Args:
        conn: asyncpg connection.
        table: Fully qualified partitioned table name.
        months_ahead: How many future months to create (from current month).
        today: Override for testing; defaults to date.today().

    Returns:
        List of partition names that were created (or already existed).
    """
    _validate_table(table)
    today = today or date.today()
    created: list[str] = []

    for offset in range(months_ahead):
        start, end = _month_range(today, offset)
        part_name = _partition_name(table, start)
        ddl = (
            f"CREATE TABLE IF NOT EXISTS {part_name} "
            f"PARTITION OF {table} "
            f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
        )
        await conn.execute(ddl)
        created.append(part_name)
        log.info(
            "partition.ensured",
            partition=part_name,
            range_start=start.isoformat(),
            range_end=end.isoformat(),
        )

    return created


async def drop_expired_partitions(
    conn,
    table: str = "prosauai.messages",
    retention_days: int = 90,
    *,
    today: date | None = None,
) -> list[str]:
    """Drop partitions where ALL data exceeds retention period.

    A partition is dropped only if its upper bound (end date) is before
    the retention threshold — meaning every row in the partition is older
    than retention_days.

    Args:
        conn: asyncpg connection.
        table: Fully qualified partitioned table name.
        retention_days: Days to retain data.
        today: Override for testing; defaults to date.today().

    Returns:
        List of dropped partition names.
    """
    _validate_table(table)
    today = today or date.today()
    threshold = today - timedelta(days=retention_days)
    partitions = await list_partitions(conn, table)
    dropped: list[str] = []

    for part in partitions:
        # Extract YYYY_MM from partition name suffix
        # e.g. "prosauai.messages_2026_01" → "2026_01"
        suffix = part.name.rsplit("_", 2)
        if len(suffix) < 3:
            log.warning("partition.unparseable_name", partition=part.name, reason="insufficient segments")
            continue
        try:
            year = int(suffix[-2])
            month = int(suffix[-1])
        except ValueError:
            log.warning("partition.unparseable_name", partition=part.name, reason="non-numeric year/month")
            continue

        # Upper bound of partition = first day of next month
        end_year = year + (month) // 12
        end_month = (month) % 12 + 1
        partition_end = date(end_year, end_month, 1)

        if partition_end <= threshold:
            await conn.execute(f"DROP TABLE IF EXISTS {part.name}")
            dropped.append(part.name)
            log.info(
                "partition.dropped",
                partition=part.name,
                rows_removed=part.row_count,
                threshold=threshold.isoformat(),
            )

    return dropped


async def list_partitions(
    conn,
    table: str = "prosauai.messages",
) -> list[PartitionInfo]:
    """List existing partitions with row counts.

    Args:
        conn: asyncpg connection.
        table: Fully qualified partitioned table name (schema.table).

    Returns:
        List of PartitionInfo sorted by partition name.
    """
    _validate_table(table)
    # Parse schema and table name
    parts = table.split(".", 1)
    if len(parts) == 2:
        schema, tbl = parts
    else:
        schema, tbl = "public", parts[0]

    rows = await conn.fetch(
        """
        SELECT
            c.relnamespace::regnamespace || '.' || c.relname AS partition_name,
            COALESCE(s.n_live_tup, 0) AS row_count
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class parent ON parent.oid = i.inhparent
        JOIN pg_namespace ns ON ns.oid = parent.relnamespace
        LEFT JOIN pg_stat_user_tables s
            ON s.relid = c.oid
        WHERE parent.relname = $1
          AND ns.nspname = $2
        ORDER BY c.relname
        """,
        tbl,
        schema,
    )

    return [PartitionInfo(name=r["partition_name"], row_count=r["row_count"]) for r in rows]
