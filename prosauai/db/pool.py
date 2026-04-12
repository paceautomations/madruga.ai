"""Asyncpg connection pool for ProsauAI.

Configures search_path = prosauai,prosauai_ops,public so that existing
queries work without schema prefix after the epic 006 schema isolation.
"""

from __future__ import annotations

import os

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]

# Default pool settings — can be overridden via environment or config
_DEFAULT_MIN_SIZE = 2
_DEFAULT_MAX_SIZE = 10
_DEFAULT_COMMAND_TIMEOUT = 60.0

# Schema search path for prosauai tables (epic 006 isolation)
SEARCH_PATH = "prosauai,prosauai_ops,public"

_pool: asyncpg.Pool | None = None  # type: ignore[type-arg]


async def create_pool(
    dsn: str | None = None,
    min_size: int = _DEFAULT_MIN_SIZE,
    max_size: int = _DEFAULT_MAX_SIZE,
    command_timeout: float = _DEFAULT_COMMAND_TIMEOUT,
) -> asyncpg.Pool:  # type: ignore[type-arg]
    """Create and return an asyncpg connection pool.

    Sets search_path = prosauai,prosauai_ops,public via server_settings
    so that unqualified table names resolve correctly.
    """
    global _pool  # noqa: PLW0603

    if asyncpg is None:
        raise RuntimeError("asyncpg is required")

    if dsn is None:
        dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise ValueError("DATABASE_URL is required")

    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
        server_settings={"search_path": SEARCH_PATH},
    )
    return _pool


async def get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    """Return the current pool, raising if not initialized."""
    if _pool is None:
        raise RuntimeError("Connection pool not initialized. Call create_pool() first.")
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        await _pool.close()
        _pool = None
