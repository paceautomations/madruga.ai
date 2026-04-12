"""Migration runner for ProsauAI — forward-only, asyncpg-based.

Applies SQL migrations from a directory in numeric order, tracks them
in prosauai_ops.schema_migrations with SHA-256 checksums.

Usage (CLI):
    python -m prosauai.ops.migrate --database-url postgresql://... --migrations-dir ./migrations

Usage (library):
    from prosauai.ops.migrate import run_migrations
    result = await run_migrations(dsn, migrations_dir)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic

try:
    import structlog

    log = structlog.get_logger("prosauai.ops.migrate")
except ImportError:  # pragma: no cover — structlog optional for standalone use
    log = logging.getLogger("prosauai.ops.migrate")

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]

BOOTSTRAP_SQL = """\
CREATE SCHEMA IF NOT EXISTS prosauai_ops;
CREATE TABLE IF NOT EXISTS prosauai_ops.schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum   TEXT
);
"""


@dataclass
class MigrationResult:
    """Outcome of a migration run."""

    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: str | None = None
    total_time_ms: float = 0.0


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _list_migrations(migrations_dir: Path) -> list[Path]:
    """List .sql files sorted by filename (numeric order)."""
    files = sorted(migrations_dir.glob("*.sql"), key=lambda p: p.name)
    return files


async def run_migrations(
    dsn: str,
    migrations_dir: Path | str = Path("./migrations"),
    dry_run: bool = False,
) -> MigrationResult:
    """Apply pending SQL migrations.

    Args:
        dsn: Postgres connection string.
        migrations_dir: Directory containing .sql files.
        dry_run: If True, list pending migrations without applying.

    Returns:
        MigrationResult with applied/skipped/failed info.
    """
    if asyncpg is None:
        raise RuntimeError("asyncpg is required for migrations")

    migrations_dir = Path(migrations_dir)
    result = MigrationResult()
    t0 = monotonic()

    conn = await asyncpg.connect(dsn)
    try:
        # Bootstrap: ensure schema_migrations exists
        await conn.execute(BOOTSTRAP_SQL)

        # Fetch already-applied migrations
        rows = await conn.fetch(
            "SELECT version, checksum FROM prosauai_ops.schema_migrations"
        )
        applied_map = {r["version"]: r["checksum"] for r in rows}

        # List migration files
        files = _list_migrations(migrations_dir)
        if not files:
            log.info("migrate.no_files", dir=str(migrations_dir))
            result.total_time_ms = (monotonic() - t0) * 1000
            return result

        for fpath in files:
            version = fpath.stem  # e.g. "001_create_schema"
            content = fpath.read_text(encoding="utf-8")
            cs = _checksum(content)

            if version in applied_map:
                # Checksum drift detection
                if applied_map[version] and applied_map[version] != cs:
                    log.warning(
                        "migrate.checksum_drift",
                        version=version,
                        expected=applied_map[version],
                        actual=cs,
                    )
                result.skipped.append(version)
                continue

            if dry_run:
                log.info("migrate.pending", version=version)
                result.applied.append(version)
                continue

            # Apply migration in a transaction
            log.info("migrate.applying", version=version)
            try:
                async with conn.transaction():
                    await conn.execute(content)
                    await conn.execute(
                        "INSERT INTO prosauai_ops.schema_migrations (version, checksum) "
                        "VALUES ($1, $2)",
                        version,
                        cs,
                    )
                log.info("migrate.applied", version=version)
                result.applied.append(version)
            except Exception:
                log.exception("migrate.failed", version=version)
                result.failed = version
                break
    finally:
        await conn.close()

    result.total_time_ms = (monotonic() - t0) * 1000
    log.info(
        "migrate.complete",
        applied=len(result.applied),
        skipped=len(result.skipped),
        failed=result.failed,
        total_time_ms=round(result.total_time_ms, 1),
    )
    return result


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="ProsauAI migration runner")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Postgres connection string (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--migrations-dir",
        default="./migrations",
        help="Directory with .sql files (default: ./migrations)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="List pending migrations without applying",
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

    result = asyncio.run(
        run_migrations(
            dsn=args.database_url,
            migrations_dir=Path(args.migrations_dir),
            dry_run=args.dry_run,
        )
    )

    if result.failed:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
