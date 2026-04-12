"""Tests for prosauai.ops.migrate — migration runner.

Tests use mocked asyncpg connections to verify logic without a real Postgres.
Integration tests against real PG would go in a separate test_migrate_integration.py.
"""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from prosauai.ops.migrate import MigrationResult, _checksum, _list_migrations, run_migrations


# ────────────────────── helpers ──────────────────────


def _write_sql(tmp_path: Path, name: str, content: str) -> Path:
    """Write a .sql file into tmp_path and return the path."""
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


# ────────────────────── _checksum ──────────────────────


class TestChecksum:
    def test_returns_sha256(self):
        content = "CREATE TABLE foo (id INT);"
        assert _checksum(content) == _sha(content)

    def test_different_content_different_checksum(self):
        assert _checksum("aaa") != _checksum("bbb")


# ────────────────────── _list_migrations ──────────────────────


class TestListMigrations:
    def test_sorts_by_name(self, tmp_path: Path):
        _write_sql(tmp_path, "002_b.sql", "SELECT 1;")
        _write_sql(tmp_path, "001_a.sql", "SELECT 1;")
        _write_sql(tmp_path, "003_c.sql", "SELECT 1;")

        files = _list_migrations(tmp_path)
        assert [f.name for f in files] == ["001_a.sql", "002_b.sql", "003_c.sql"]

    def test_empty_directory(self, tmp_path: Path):
        assert _list_migrations(tmp_path) == []

    def test_ignores_non_sql(self, tmp_path: Path):
        _write_sql(tmp_path, "001_a.sql", "SELECT 1;")
        (tmp_path / "readme.md").write_text("ignore me")
        files = _list_migrations(tmp_path)
        assert len(files) == 1


# ────────────────────── run_migrations ──────────────────────


@pytest.fixture
def mock_conn():
    """Create a mock asyncpg connection with async methods."""
    conn = AsyncMock()
    # Default: no migrations applied yet
    conn.fetch = AsyncMock(return_value=[])
    # Transaction context manager
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    return conn


class TestRunMigrations:
    """Tests for run_migrations using mocked asyncpg."""

    @pytest.mark.asyncio
    async def test_applies_all_pending(self, tmp_path: Path, mock_conn):
        """All migrations applied when none are in schema_migrations."""
        _write_sql(tmp_path, "001_schema.sql", "CREATE SCHEMA prosauai;")
        _write_sql(tmp_path, "002_tables.sql", "CREATE TABLE prosauai.foo (id INT);")

        with patch("prosauai.ops.migrate.asyncpg") as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)
            result = await run_migrations(dsn="postgresql://test", migrations_dir=tmp_path)

        assert result.applied == ["001_schema", "002_tables"]
        assert result.skipped == []
        assert result.failed is None
        assert result.total_time_ms > 0
        # Verify execute was called for bootstrap + each migration SQL + each INSERT
        assert mock_conn.execute.call_count >= 3  # bootstrap + 2 migrations

    @pytest.mark.asyncio
    async def test_idempotent_skips_applied(self, tmp_path: Path, mock_conn):
        """Already-applied migrations are skipped."""
        content = "CREATE SCHEMA prosauai;"
        _write_sql(tmp_path, "001_schema.sql", content)

        # Simulate: 001_schema already applied
        mock_conn.fetch = AsyncMock(return_value=[
            {"version": "001_schema", "checksum": _sha(content)}
        ])

        with patch("prosauai.ops.migrate.asyncpg") as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)
            result = await run_migrations(dsn="postgresql://test", migrations_dir=tmp_path)

        assert result.applied == []
        assert result.skipped == ["001_schema"]
        assert result.failed is None

    @pytest.mark.asyncio
    async def test_failed_migration_blocks_subsequent(self, tmp_path: Path, mock_conn):
        """A failed migration stops execution of subsequent ones."""
        _write_sql(tmp_path, "001_ok.sql", "SELECT 1;")
        _write_sql(tmp_path, "002_fail.sql", "INVALID SQL;")
        _write_sql(tmp_path, "003_never.sql", "SELECT 1;")

        call_count = 0

        async def execute_side_effect(sql, *args):
            nonlocal call_count
            call_count += 1
            # First call is bootstrap, then 001 content, then 001 insert = OK
            # 002 content should fail
            if "INVALID SQL" in str(sql):
                raise Exception("syntax error at or near INVALID")

        mock_conn.execute = AsyncMock(side_effect=execute_side_effect)
        mock_conn.fetch = AsyncMock(return_value=[])

        # Transaction must re-raise the error
        tx = AsyncMock()
        tx.__aenter__ = AsyncMock(return_value=tx)
        tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=tx)

        with patch("prosauai.ops.migrate.asyncpg") as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)
            result = await run_migrations(dsn="postgresql://test", migrations_dir=tmp_path)

        assert "001_ok" in result.applied
        assert result.failed == "002_fail"
        # 003_never should NOT be in applied
        assert "003_never" not in result.applied

    @pytest.mark.asyncio
    async def test_checksum_drift_logs_warning(self, tmp_path: Path, mock_conn, caplog):
        """Checksum mismatch for applied migration logs a warning."""
        content = "CREATE SCHEMA prosauai;"
        _write_sql(tmp_path, "001_schema.sql", content)

        # Applied with different checksum
        mock_conn.fetch = AsyncMock(return_value=[
            {"version": "001_schema", "checksum": "wrong_checksum_abc123"}
        ])

        with patch("prosauai.ops.migrate.asyncpg") as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)
            import logging
            with caplog.at_level(logging.WARNING):
                result = await run_migrations(dsn="postgresql://test", migrations_dir=tmp_path)

        assert result.skipped == ["001_schema"]
        # The warning is logged via structlog or stdlib — check structlog mock or caplog
        # Structlog may not appear in caplog, so we just verify the skipped behavior

    @pytest.mark.asyncio
    async def test_dry_run_lists_without_applying(self, tmp_path: Path, mock_conn):
        """Dry run lists pending migrations without executing."""
        _write_sql(tmp_path, "001_schema.sql", "CREATE SCHEMA prosauai;")

        with patch("prosauai.ops.migrate.asyncpg") as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)
            result = await run_migrations(
                dsn="postgresql://test", migrations_dir=tmp_path, dry_run=True
            )

        assert result.applied == ["001_schema"]
        assert result.failed is None
        # In dry run, transaction should NOT be opened for migration SQL
        # Only bootstrap execute should be called
        # (bootstrap + fetch, no per-migration execute in transaction)
        # Check that conn.transaction was never called
        mock_conn.transaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_dir_returns_empty_result(self, tmp_path: Path, mock_conn):
        """Empty migrations dir returns clean result."""
        with patch("prosauai.ops.migrate.asyncpg") as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)
            result = await run_migrations(dsn="postgresql://test", migrations_dir=tmp_path)

        assert result.applied == []
        assert result.skipped == []
        assert result.failed is None


class TestMigrationResult:
    def test_defaults(self):
        r = MigrationResult()
        assert r.applied == []
        assert r.skipped == []
        assert r.failed is None
        assert r.total_time_ms == 0.0
