"""Tests for prosauai.ops.partitions — partition lifecycle manager.

Tests use mocked asyncpg connections to verify logic without a real Postgres.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from prosauai.ops.partitions import (
    PartitionInfo,
    _month_range,
    _partition_name,
    drop_expired_partitions,
    ensure_future_partitions,
    list_partitions,
)


# ────────────────────── _month_range ──────────────────────


class TestMonthRange:
    def test_current_month(self):
        start, end = _month_range(date(2026, 4, 15), 0)
        assert start == date(2026, 4, 1)
        assert end == date(2026, 5, 1)

    def test_next_month(self):
        start, end = _month_range(date(2026, 4, 15), 1)
        assert start == date(2026, 5, 1)
        assert end == date(2026, 6, 1)

    def test_year_boundary(self):
        start, end = _month_range(date(2026, 11, 1), 2)
        assert start == date(2027, 1, 1)
        assert end == date(2027, 2, 1)

    def test_december_to_january(self):
        start, end = _month_range(date(2026, 12, 1), 0)
        assert start == date(2026, 12, 1)
        assert end == date(2027, 1, 1)


# ────────────────────── _partition_name ──────────────────────


class TestPartitionName:
    def test_format(self):
        assert _partition_name("prosauai.messages", date(2026, 4, 1)) == "prosauai.messages_2026_04"

    def test_single_digit_month(self):
        assert _partition_name("prosauai.messages", date(2026, 1, 1)) == "prosauai.messages_2026_01"


# ────────────────────── ensure_future_partitions ──────────────────────


class TestEnsureFuturePartitions:
    @pytest.mark.asyncio
    async def test_creates_3_months_by_default(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()

        result = await ensure_future_partitions(conn, "prosauai.messages", months_ahead=3, today=date(2026, 4, 15))

        assert len(result) == 3
        assert result[0] == "prosauai.messages_2026_04"
        assert result[1] == "prosauai.messages_2026_05"
        assert result[2] == "prosauai.messages_2026_06"
        assert conn.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_ddl_uses_if_not_exists(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()

        await ensure_future_partitions(conn, "prosauai.messages", months_ahead=1, today=date(2026, 4, 1))

        ddl = conn.execute.call_args_list[0][0][0]
        assert "IF NOT EXISTS" in ddl
        assert "prosauai.messages_2026_04" in ddl
        assert "PARTITION OF prosauai.messages" in ddl
        assert "'2026-04-01'" in ddl
        assert "'2026-05-01'" in ddl

    @pytest.mark.asyncio
    async def test_idempotent_reruns(self):
        """Running twice with same params produces same DDL — IF NOT EXISTS handles it."""
        conn = AsyncMock()
        conn.execute = AsyncMock()

        r1 = await ensure_future_partitions(conn, "prosauai.messages", months_ahead=2, today=date(2026, 4, 1))
        r2 = await ensure_future_partitions(conn, "prosauai.messages", months_ahead=2, today=date(2026, 4, 1))

        assert r1 == r2
        assert conn.execute.call_count == 4  # 2 + 2

    @pytest.mark.asyncio
    async def test_year_boundary_partitions(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()

        result = await ensure_future_partitions(conn, "prosauai.messages", months_ahead=3, today=date(2026, 11, 1))

        assert result[0] == "prosauai.messages_2026_11"
        assert result[1] == "prosauai.messages_2026_12"
        assert result[2] == "prosauai.messages_2027_01"


# ────────────────────── drop_expired_partitions ──────────────────────


class TestDropExpiredPartitions:
    @pytest.fixture
    def mock_conn_with_partitions(self):
        """Connection that returns a set of partitions via list_partitions query."""
        conn = AsyncMock()
        # list_partitions query returns these rows
        conn.fetch = AsyncMock(
            return_value=[
                {"partition_name": "prosauai.messages_2026_01", "row_count": 500},
                {"partition_name": "prosauai.messages_2026_02", "row_count": 300},
                {"partition_name": "prosauai.messages_2026_03", "row_count": 200},
                {"partition_name": "prosauai.messages_2026_04", "row_count": 100},
            ]
        )
        conn.execute = AsyncMock()
        return conn

    @pytest.mark.asyncio
    async def test_drops_only_fully_expired(self, mock_conn_with_partitions):
        """Only partitions where upper bound <= threshold are dropped."""
        conn = mock_conn_with_partitions

        # today=2026-07-01, retention=90d → threshold=2026-04-02
        # Partitions: 2026_01 (end=2026-02-01 ✓), 2026_02 (end=2026-03-01 ✓),
        #             2026_03 (end=2026-04-01 ✓), 2026_04 (end=2026-05-01 ✗)
        dropped = await drop_expired_partitions(
            conn,
            "prosauai.messages",
            retention_days=90,
            today=date(2026, 7, 1),
        )

        assert "prosauai.messages_2026_01" in dropped
        assert "prosauai.messages_2026_02" in dropped
        assert "prosauai.messages_2026_03" in dropped
        assert "prosauai.messages_2026_04" not in dropped
        # 3 DROP TABLE calls
        drop_calls = [c for c in conn.execute.call_args_list if "DROP TABLE" in str(c)]
        assert len(drop_calls) == 3

    @pytest.mark.asyncio
    async def test_keeps_partition_at_boundary(self, mock_conn_with_partitions):
        """Partition at exact boundary is NOT dropped (conservative)."""
        conn = mock_conn_with_partitions

        # today=2026-05-01, retention=90d → threshold=2026-01-31
        # 2026_01: end=2026-02-01 > threshold → NOT dropped
        dropped = await drop_expired_partitions(
            conn,
            "prosauai.messages",
            retention_days=90,
            today=date(2026, 5, 1),
        )

        assert "prosauai.messages_2026_01" not in dropped

    @pytest.mark.asyncio
    async def test_no_partitions_returns_empty(self):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])

        dropped = await drop_expired_partitions(conn, "prosauai.messages", retention_days=90, today=date(2026, 7, 1))

        assert dropped == []
        # No DROP TABLE calls
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_drop_if_exists(self, mock_conn_with_partitions):
        """DDL uses IF EXISTS for safety."""
        conn = mock_conn_with_partitions

        await drop_expired_partitions(conn, "prosauai.messages", retention_days=90, today=date(2026, 7, 1))

        for c in conn.execute.call_args_list:
            ddl = c[0][0]
            assert "DROP TABLE IF EXISTS" in ddl


# ────────────────────── list_partitions ──────────────────────


class TestListPartitions:
    @pytest.mark.asyncio
    async def test_returns_partition_info(self):
        conn = AsyncMock()
        conn.fetch = AsyncMock(
            return_value=[
                {"partition_name": "prosauai.messages_2026_04", "row_count": 100},
                {"partition_name": "prosauai.messages_2026_05", "row_count": 50},
            ]
        )

        result = await list_partitions(conn, "prosauai.messages")

        assert len(result) == 2
        assert result[0] == PartitionInfo(name="prosauai.messages_2026_04", row_count=100)
        assert result[1] == PartitionInfo(name="prosauai.messages_2026_05", row_count=50)

    @pytest.mark.asyncio
    async def test_passes_correct_schema_and_table(self):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])

        await list_partitions(conn, "prosauai.messages")

        # Verify the query received correct params
        call_args = conn.fetch.call_args
        assert call_args[0][1] == "messages"  # table name
        assert call_args[0][2] == "prosauai"  # schema name

    @pytest.mark.asyncio
    async def test_empty_partitions(self):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])

        result = await list_partitions(conn, "prosauai.messages")

        assert result == []

    @pytest.mark.asyncio
    async def test_unqualified_table_defaults_to_public(self):
        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])

        await list_partitions(conn, "messages")

        call_args = conn.fetch.call_args
        assert call_args[0][1] == "messages"
        assert call_args[0][2] == "public"
