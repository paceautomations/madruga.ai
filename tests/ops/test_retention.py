"""Tests for prosauai.ops.retention — data retention logic (LGPD compliance).

Tests use mocked asyncpg connections to verify logic without a real Postgres.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from prosauai.ops.retention import (
    BATCH_SIZE,
    RetentionResult,
    purge_expired_conversations,
    purge_expired_eval_scores,
    purge_expired_messages,
    purge_expired_traces,
    run_retention,
)


# ────────────────────── helpers ──────────────────────


def _make_conn(**kwargs) -> AsyncMock:
    """Create a mock asyncpg connection with sensible defaults."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 0")
    conn.fetchrow = AsyncMock(return_value={"cnt": 0})
    conn.fetchval = AsyncMock(return_value=False)
    conn.fetch = AsyncMock(return_value=[])
    for k, v in kwargs.items():
        setattr(conn, k, v)
    return conn


# ────────────────────── purge_expired_messages ──────────────────────


class TestPurgeExpiredMessages:
    @pytest.mark.asyncio
    async def test_dry_run_lists_without_deleting(self):
        """Dry run checks eligible partitions but does not drop."""
        conn = _make_conn()
        # list_partitions returns via conn.fetch
        conn.fetch = AsyncMock(
            return_value=[
                {"partition_name": "prosauai.messages_2025_12", "row_count": 500},
                {"partition_name": "prosauai.messages_2026_01", "row_count": 300},
                {"partition_name": "prosauai.messages_2026_04", "row_count": 100},
            ]
        )

        dropped, created = await purge_expired_messages(
            conn, retention_days=90, dry_run=True, today=date(2026, 7, 1)
        )

        # 2025_12 (end=2026-01-01) and 2026_01 (end=2026-02-01) are eligible
        # threshold = 2026-07-01 - 90d = 2026-04-02
        assert "prosauai.messages_2025_12" in dropped
        assert "prosauai.messages_2026_01" in dropped
        assert "prosauai.messages_2026_04" not in dropped
        assert created == []  # dry-run doesn't create
        # No DROP TABLE executed
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_run_drops_and_creates(self):
        """Real run delegates to partitions module."""
        conn = _make_conn()
        # Mock the partition functions at module level
        with (
            patch(
                "prosauai.ops.retention.drop_expired_partitions",
                new_callable=AsyncMock,
                return_value=["prosauai.messages_2025_12"],
            ) as mock_drop,
            patch(
                "prosauai.ops.retention.ensure_future_partitions",
                new_callable=AsyncMock,
                return_value=["prosauai.messages_2026_07", "prosauai.messages_2026_08"],
            ) as mock_ensure,
        ):
            dropped, created = await purge_expired_messages(
                conn, retention_days=90, dry_run=False, today=date(2026, 5, 1)
            )

        assert dropped == ["prosauai.messages_2025_12"]
        assert len(created) == 2
        mock_drop.assert_awaited_once()
        mock_ensure.assert_awaited_once()


# ────────────────────── purge_expired_conversations ──────────────────────


class TestPurgeExpiredConversations:
    @pytest.mark.asyncio
    async def test_dry_run_counts_without_deleting(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"cnt": 42})

        result = await purge_expired_conversations(conn, retention_days=90, dry_run=True)

        assert result == 0  # dry-run returns 0 deleted
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_run_deletes_in_batches(self):
        """Batch DELETE stops when fewer than BATCH_SIZE rows deleted."""
        conn = _make_conn()
        # First batch: 1000 deleted, second: 200 deleted (< BATCH_SIZE → stop)
        conn.execute = AsyncMock(
            side_effect=[f"DELETE {BATCH_SIZE}", "DELETE 200"]
        )

        result = await purge_expired_conversations(conn, retention_days=90, dry_run=False)

        assert result == BATCH_SIZE + 200
        assert conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_no_expired_data(self):
        conn = _make_conn()
        conn.execute = AsyncMock(return_value="DELETE 0")

        result = await purge_expired_conversations(conn, retention_days=90, dry_run=False)

        assert result == 0


# ────────────────────── purge_expired_eval_scores ──────────────────────


class TestPurgeExpiredEvalScores:
    @pytest.mark.asyncio
    async def test_dry_run_counts_without_deleting(self):
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"cnt": 1203})

        result = await purge_expired_eval_scores(conn, retention_days=90, dry_run=True)

        assert result == 0
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_run_deletes_in_batches(self):
        conn = _make_conn()
        conn.execute = AsyncMock(side_effect=["DELETE 500"])

        result = await purge_expired_eval_scores(conn, retention_days=90, dry_run=False)

        assert result == 500
        assert conn.execute.call_count == 1  # 500 < BATCH_SIZE → single batch

    @pytest.mark.asyncio
    async def test_multiple_batches(self):
        conn = _make_conn()
        conn.execute = AsyncMock(
            side_effect=[f"DELETE {BATCH_SIZE}", f"DELETE {BATCH_SIZE}", "DELETE 50"]
        )

        result = await purge_expired_eval_scores(conn, retention_days=90, dry_run=False)

        assert result == 2 * BATCH_SIZE + 50
        assert conn.execute.call_count == 3


# ────────────────────── purge_expired_traces ──────────────────────


class TestPurgeExpiredTraces:
    @pytest.mark.asyncio
    async def test_skips_if_spans_table_missing(self):
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=False)

        result = await purge_expired_traces(conn, retention_days=90, dry_run=False)

        assert result == 0
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_counts_eligible(self):
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=True)  # spans table exists
        conn.fetchrow = AsyncMock(return_value={"cnt": 5000})

        result = await purge_expired_traces(conn, retention_days=90, dry_run=True)

        assert result == 0
        conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_run_deletes(self):
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=True)
        conn.execute = AsyncMock(return_value="DELETE 300")

        result = await purge_expired_traces(conn, retention_days=90, dry_run=False)

        assert result == 300


# ────────────────────── run_retention (orchestrator) ──────────────────────


class TestRunRetention:
    @pytest.mark.asyncio
    async def test_dry_run_orchestrates_all(self):
        """Dry run calls all purge functions in dry-run mode."""
        conn = _make_conn()
        # messages: list_partitions mock
        conn.fetch = AsyncMock(return_value=[])
        # conversations + eval_scores: count queries
        conn.fetchrow = AsyncMock(return_value={"cnt": 0})
        # traces: spans table doesn't exist
        conn.fetchval = AsyncMock(return_value=False)

        result = await run_retention(conn, dry_run=True, today=date(2026, 7, 1))

        assert result.dry_run is True
        assert isinstance(result.run_id, str)
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_real_run_aggregates_results(self):
        """Real run collects results from all purge functions."""
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=False)  # no spans table

        with (
            patch(
                "prosauai.ops.retention.drop_expired_partitions",
                new_callable=AsyncMock,
                return_value=["prosauai.messages_2025_12"],
            ),
            patch(
                "prosauai.ops.retention.ensure_future_partitions",
                new_callable=AsyncMock,
                return_value=["prosauai.messages_2026_07"],
            ),
        ):
            # conversations: 0 deleted, eval_scores: 0 deleted
            conn.execute = AsyncMock(return_value="DELETE 0")

            result = await run_retention(conn, dry_run=False, today=date(2026, 5, 1))

        assert result.dry_run is False
        assert result.partitions_dropped == ["prosauai.messages_2025_12"]
        assert result.partitions_created == ["prosauai.messages_2026_07"]

    @pytest.mark.asyncio
    async def test_idempotent_rerun(self):
        """Running retention twice produces no errors — idempotent by nature."""
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=False)

        with (
            patch(
                "prosauai.ops.retention.drop_expired_partitions",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "prosauai.ops.retention.ensure_future_partitions",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            conn.execute = AsyncMock(return_value="DELETE 0")

            r1 = await run_retention(conn, dry_run=False, today=date(2026, 5, 1))
            r2 = await run_retention(conn, dry_run=False, today=date(2026, 5, 1))

        # Both succeed with no errors
        assert r1.partitions_dropped == []
        assert r2.partitions_dropped == []
        assert sum(r1.rows_purged.values()) == 0
        assert sum(r2.rows_purged.values()) == 0


# ────────────────────── RetentionResult ──────────────────────


class TestRetentionResult:
    def test_defaults(self):
        r = RetentionResult()
        assert r.rows_purged == {}
        assert r.partitions_dropped == []
        assert r.partitions_created == []
        assert r.duration_ms == 0.0
        assert r.dry_run is True
        assert len(r.run_id) > 0  # UUID generated


# ────────────────────── audit_log never touched ──────────────────────


class TestAuditLogProtection:
    @pytest.mark.asyncio
    async def test_run_retention_never_touches_audit_log(self):
        """Verify no SQL referencing admin.audit_log is ever executed."""
        conn = _make_conn()
        conn.fetchval = AsyncMock(return_value=False)

        executed_sql: list[str] = []
        original_execute = conn.execute

        async def capture_execute(sql, *args, **kwargs):
            executed_sql.append(str(sql))
            return "DELETE 0"

        conn.execute = AsyncMock(side_effect=capture_execute)

        with (
            patch(
                "prosauai.ops.retention.drop_expired_partitions",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "prosauai.ops.retention.ensure_future_partitions",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await run_retention(conn, dry_run=False, today=date(2026, 5, 1))

        # No SQL should reference audit_log
        for sql in executed_sql:
            assert "audit_log" not in sql.lower(), f"audit_log referenced in: {sql}"
