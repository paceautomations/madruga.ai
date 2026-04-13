"""ProsauAI API entrypoint — FastAPI with lifespan-managed resources.

On startup:
  1. Run pending database migrations (fail-fast if any error)
  2. Create asyncpg connection pool with schema-isolated search_path

On shutdown:
  1. Close connection pool
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment,misc]

from prosauai.db.pool import close_pool, create_pool
from prosauai.ops.migrate import run_migrations

logger = logging.getLogger("prosauai.main")

# Default migrations directory (relative to project root)
_MIGRATIONS_DIR = Path(os.environ.get("MIGRATIONS_DIR", "./migrations"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # type: ignore[type-arg]
    """Manage startup/shutdown lifecycle."""
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("DATABASE_URL environment variable is required")

    # Step 1: Run migrations — fail-fast if any migration fails
    logger.info("Running database migrations...")
    result = await run_migrations(dsn=dsn, migrations_dir=_MIGRATIONS_DIR)
    if result.failed:
        raise RuntimeError(f"Migration failed: {result.failed}. API cannot start.")
    logger.info(
        "Migrations complete: %d applied, %d skipped",
        len(result.applied),
        len(result.skipped),
    )

    # Step 2: Create connection pool
    await create_pool(dsn=dsn)
    logger.info("Connection pool created")

    yield

    # Shutdown: close pool
    await close_pool()
    logger.info("Connection pool closed")


def create_app() -> FastAPI:  # type: ignore[type-arg]
    """Create the FastAPI application."""
    if FastAPI is None:
        raise RuntimeError("FastAPI is required to create the app")

    app = FastAPI(
        title="ProsauAI",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
