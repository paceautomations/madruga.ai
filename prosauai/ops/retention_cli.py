"""CLI entry point for ProsauAI data retention cron.

Usage:
    python -m prosauai.ops.retention_cli --dry-run=false --database-url postgresql://...

Exit codes:
    0 — Success (purge complete or dry-run listed)
    1 — Connection error
    2 — Error during purge
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

try:
    import structlog

    log = structlog.get_logger("prosauai.ops.retention_cli")
except ImportError:  # pragma: no cover
    log = logging.getLogger("prosauai.ops.retention_cli")

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]


async def _run(dsn: str, dry_run: bool) -> int:
    """Connect and execute retention, returning exit code."""
    from prosauai.ops.retention import run_retention

    if asyncpg is None:
        log.error("asyncpg_missing", msg="asyncpg is required")
        return 1

    try:
        conn = await asyncpg.connect(dsn)
    except Exception:
        log.exception("connection_failed", dsn=dsn.split("@")[-1])
        return 1

    try:
        result = await run_retention(conn, dry_run=dry_run)
        if not dry_run:
            total = sum(result.rows_purged.values())
            log.info(
                "retention_summary",
                run_id=result.run_id,
                total_rows_purged=total,
                partitions_dropped=len(result.partitions_dropped),
                partitions_created=len(result.partitions_created),
                duration_ms=round(result.duration_ms, 1),
            )
        return 0
    except Exception:
        log.exception("retention_failed")
        return 2
    finally:
        await conn.close()


def _parse_dry_run(value: str) -> bool:
    """Parse --dry-run value accepting bool-like strings."""
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ProsauAI data retention cron — LGPD compliance"
    )
    parser.add_argument(
        "--dry-run",
        type=_parse_dry_run,
        default=True,
        help="List what would be purged without executing (default: true)",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Postgres connection string with BYPASSRLS (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    if not args.database_url:
        print("ERROR: --database-url or $DATABASE_URL required", file=sys.stderr)
        sys.exit(1)

    exit_code = asyncio.run(_run(dsn=args.database_url, dry_run=args.dry_run))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
