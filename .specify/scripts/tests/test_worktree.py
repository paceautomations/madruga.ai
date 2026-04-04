"""Tests for worktree._get_cascade_base."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).parent.parent))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_row(branch_name: str | None) -> MagicMock:
    """Build a Row-like mock where row["branch_name"] returns branch_name."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: branch_name if key == "branch_name" else None
    row.__bool__ = lambda self: True
    return row


def _mock_conn_ctx(fetchone_return):
    """Return a context-manager mock whose execute().fetchone() returns fetchone_return."""
    conn = MagicMock()
    conn.__enter__ = lambda s: conn
    conn.__exit__ = MagicMock(return_value=False)
    conn.execute.return_value.fetchone.return_value = fetchone_return
    return conn


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — _get_cascade_base
# ──────────────────────────────────────────────────────────────────────────────


class TestGetCascadeBase:
    def _call(self, repo_path, platform_name, fallback):
        from worktree import _get_cascade_base

        return _get_cascade_base(repo_path, platform_name, fallback)

    def test_returns_shipped_branch_when_on_remote(self, tmp_path):
        """DB has shipped epic + branch exists on remote → return origin/<branch>."""
        row = _make_row("epic/myplatform/001-first")
        conn = _mock_conn_ctx(row)

        with (
            patch("db.get_conn", return_value=conn),
            patch("worktree._branch_exists_on_remote", return_value=True) as mock_exists,
        ):
            result = self._call(tmp_path, "myplatform", "main")

        assert result == "origin/epic/myplatform/001-first"
        mock_exists.assert_called_once_with(tmp_path, "epic/myplatform/001-first")

    def test_falls_back_when_branch_not_on_remote(self, tmp_path):
        """Branch in DB but not on remote → origin/<fallback>."""
        row = _make_row("epic/myplatform/001-first")
        conn = _mock_conn_ctx(row)

        with (
            patch("db.get_conn", return_value=conn),
            patch("worktree._branch_exists_on_remote", return_value=False),
        ):
            result = self._call(tmp_path, "myplatform", "main")

        assert result == "origin/main"

    def test_falls_back_when_no_shipped_epic(self, tmp_path):
        """DB returns None (no shipped epics) → origin/<fallback>."""
        conn = _mock_conn_ctx(None)

        with (
            patch("db.get_conn", return_value=conn),
            patch("worktree._branch_exists_on_remote") as mock_exists,
        ):
            result = self._call(tmp_path, "myplatform", "main")

        assert result == "origin/main"
        mock_exists.assert_not_called()

    def test_falls_back_when_branch_name_is_null(self, tmp_path):
        """Shipped epic exists but branch_name is NULL → origin/<fallback>."""
        row = _make_row(None)
        conn = _mock_conn_ctx(row)

        with (
            patch("db.get_conn", return_value=conn),
            patch("worktree._branch_exists_on_remote") as mock_exists,
        ):
            result = self._call(tmp_path, "myplatform", "main")

        assert result == "origin/main"
        mock_exists.assert_not_called()

    def test_degrades_on_db_exception(self, tmp_path):
        """get_conn raises → return origin/<fallback>, no propagation."""
        with (
            patch("db.get_conn", side_effect=Exception("DB unavailable")),
            patch("worktree._branch_exists_on_remote") as mock_exists,
        ):
            result = self._call(tmp_path, "myplatform", "main")

        assert result == "origin/main"
        mock_exists.assert_not_called()

    def test_degrades_on_execute_exception(self, tmp_path):
        """conn.execute raises → return origin/<fallback>, no propagation."""
        conn = MagicMock()
        conn.__enter__ = lambda s: conn
        conn.__exit__ = MagicMock(return_value=False)
        conn.execute.side_effect = Exception("no such table: epics")

        with (
            patch("db.get_conn", return_value=conn),
            patch("worktree._branch_exists_on_remote") as mock_exists,
        ):
            result = self._call(tmp_path, "myplatform", "main")

        assert result == "origin/main"
        mock_exists.assert_not_called()

    def test_non_main_fallback(self, tmp_path):
        """Fallback arg is honoured verbatim when no cascade base is found."""
        conn = _mock_conn_ctx(None)

        with patch("db.get_conn", return_value=conn):
            result = self._call(tmp_path, "myplatform", "release/v2")

        assert result == "origin/release/v2"


# ──────────────────────────────────────────────────────────────────────────────
# Integration test — real migrated DB via tmp_db fixture
# ──────────────────────────────────────────────────────────────────────────────


class TestGetCascadeBaseIntegration:
    def test_returns_latest_by_delivered_at(self, tmp_db, tmp_path):
        """Two shipped epics: picks the one with the most recent delivered_at."""
        from db_pipeline import upsert_epic, upsert_platform

        upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
        upsert_epic(
            tmp_db,
            "p1",
            "001-alpha",
            title="Alpha",
            status="shipped",
            branch_name="epic/p1/001-alpha",
            delivered_at="2026-01-01",
        )
        upsert_epic(
            tmp_db,
            "p1",
            "002-beta",
            title="Beta",
            status="shipped",
            branch_name="epic/p1/002-beta",
            delivered_at="2026-02-01",
        )

        ctx = MagicMock()
        ctx.__enter__ = lambda s: tmp_db
        ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("db.get_conn", return_value=ctx),
            patch("worktree._branch_exists_on_remote", return_value=True),
        ):
            from worktree import _get_cascade_base

            result = _get_cascade_base(tmp_path, "p1", "main")

        assert result == "origin/epic/p1/002-beta"

    def test_no_shipped_epics_falls_back(self, tmp_db, tmp_path):
        """Platform with only in_progress epics → origin/<fallback>."""
        from db_pipeline import upsert_epic, upsert_platform

        upsert_platform(tmp_db, "p2", name="P2", repo_path="platforms/p2")
        upsert_epic(tmp_db, "p2", "001-wip", title="WIP", status="in_progress")

        ctx = MagicMock()
        ctx.__enter__ = lambda s: tmp_db
        ctx.__exit__ = MagicMock(return_value=False)

        with (
            patch("db.get_conn", return_value=ctx),
            patch("worktree._branch_exists_on_remote") as mock_exists,
        ):
            from worktree import _get_cascade_base

            result = _get_cascade_base(tmp_path, "p2", "main")

        assert result == "origin/main"
        mock_exists.assert_not_called()
