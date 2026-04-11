"""Tests for worktree.py — _get_cascade_base, _branch_exists_on_remote,
create_worktree, and cleanup_worktree."""

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


# ──────────────────────────────────────────────────────────────────────────────
# _branch_exists_on_remote
# ──────────────────────────────────────────────────────────────────────────────


class TestBranchExistsOnRemote:
    def test_returns_true_when_branch_found(self, tmp_path):
        from worktree import _branch_exists_on_remote

        mock_result = MagicMock()
        mock_result.stdout = "  origin/main\n"

        with patch("worktree.subprocess.run", return_value=mock_result):
            assert _branch_exists_on_remote(tmp_path, "main") is True

    def test_returns_false_when_empty(self, tmp_path):
        from worktree import _branch_exists_on_remote

        mock_result = MagicMock()
        mock_result.stdout = ""

        with patch("worktree.subprocess.run", return_value=mock_result):
            assert _branch_exists_on_remote(tmp_path, "nonexistent") is False


# ──────────────────────────────────────────────────────────────────────────────
# _branch_exists_locally
# ──────────────────────────────────────────────────────────────────────────────


class TestBranchExistsLocally:
    def test_returns_true_when_branch_found(self, tmp_path):
        from worktree import _branch_exists_locally

        mock_result = MagicMock()
        mock_result.stdout = "  epic/myplat/001-feat\n"

        with patch("worktree.subprocess.run", return_value=mock_result):
            assert _branch_exists_locally(tmp_path, "epic/myplat/001-feat") is True

    def test_returns_false_when_empty(self, tmp_path):
        from worktree import _branch_exists_locally

        mock_result = MagicMock()
        mock_result.stdout = ""

        with patch("worktree.subprocess.run", return_value=mock_result):
            assert _branch_exists_locally(tmp_path, "nonexistent") is False


# ──────────────────────────────────────────────────────────────────────────────
# create_worktree
# ──────────────────────────────────────────────────────────────────────────────


def _make_binding(name="other-repo"):
    return {
        "org": "myorg",
        "name": name,
        "base_branch": "main",
        "epic_branch_prefix": "epic/myplat/",
    }


class TestCreateWorktree:
    def test_self_ref_returns_repo_root(self, tmp_path):
        from worktree import create_worktree

        with (
            patch("ensure_repo._load_repo_binding", return_value=_make_binding("madruga.ai")),
            patch("ensure_repo._is_self_ref", return_value=True),
            patch("ensure_repo.REPO_ROOT", tmp_path),
        ):
            result = create_worktree("myplat", "001-feat")

        assert result == tmp_path

    def test_existing_worktree_reused(self, tmp_path):
        from worktree import create_worktree

        repos_base = tmp_path / "repos"
        repo_path = repos_base / "myorg" / "other-repo"
        repo_path.mkdir(parents=True)
        wt_path = repos_base / "other-repo-worktrees" / "001-feat"
        (wt_path / ".git").mkdir(parents=True)

        with (
            patch("ensure_repo._load_repo_binding", return_value=_make_binding()),
            patch("ensure_repo._is_self_ref", return_value=False),
            patch("ensure_repo.ensure_repo", return_value=repo_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
        ):
            result = create_worktree("myplat", "001-feat")

        assert result == wt_path

    def test_creates_worktree_existing_branch(self, tmp_path):
        """Case (a): branch on remote — checkout without -b."""
        from worktree import create_worktree

        repos_base = tmp_path / "repos"
        repo_path = repos_base / "myorg" / "other-repo"
        repo_path.mkdir(parents=True)

        with (
            patch("ensure_repo._load_repo_binding", return_value=_make_binding()),
            patch("ensure_repo._is_self_ref", return_value=False),
            patch("ensure_repo.ensure_repo", return_value=repo_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
            patch("worktree.subprocess.run") as mock_run,
            patch("worktree._branch_exists_on_remote", return_value=True),
            # Remote exists → local_exists is not consulted, but patch to keep
            # the test hermetic (real call would shell out to git).
            patch("worktree._branch_exists_locally", return_value=False),
        ):
            create_worktree("myplat", "001-feat")

        # Should have called fetch + worktree add (checkout existing branch)
        assert mock_run.call_count == 2
        wt_add_call = mock_run.call_args_list[1][0][0]
        assert "worktree" in wt_add_call
        assert "add" in wt_add_call
        assert "-b" not in wt_add_call

    def test_creates_worktree_local_only_branch(self, tmp_path):
        """Case (b): branch exists locally but not on remote — push + checkout without -b."""
        from worktree import create_worktree

        repos_base = tmp_path / "repos"
        repo_path = repos_base / "myorg" / "other-repo"
        repo_path.mkdir(parents=True)

        with (
            patch("ensure_repo._load_repo_binding", return_value=_make_binding()),
            patch("ensure_repo._is_self_ref", return_value=False),
            patch("ensure_repo.ensure_repo", return_value=repo_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
            patch("worktree.subprocess.run") as mock_run,
            patch("worktree._branch_exists_on_remote", return_value=False),
            patch("worktree._branch_exists_locally", return_value=True),
        ):
            create_worktree("myplat", "001-feat")

        # Should have called fetch + push -u origin + worktree add (no -b)
        assert mock_run.call_count == 3
        push_call = mock_run.call_args_list[1][0][0]
        assert push_call[:2] == ["git", "push"]
        assert "-u" in push_call and "origin" in push_call
        wt_add_call = mock_run.call_args_list[2][0][0]
        assert "worktree" in wt_add_call
        assert "add" in wt_add_call
        assert "-b" not in wt_add_call

    def test_creates_worktree_new_branch(self, tmp_path):
        """Case (c): branch absent everywhere — create with -b from cascade base."""
        from worktree import create_worktree

        repos_base = tmp_path / "repos"
        repo_path = repos_base / "myorg" / "other-repo"
        repo_path.mkdir(parents=True)

        with (
            patch("ensure_repo._load_repo_binding", return_value=_make_binding()),
            patch("ensure_repo._is_self_ref", return_value=False),
            patch("ensure_repo.ensure_repo", return_value=repo_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
            patch("worktree.subprocess.run") as mock_run,
            patch("worktree._branch_exists_on_remote", return_value=False),
            patch("worktree._branch_exists_locally", return_value=False),
            patch("worktree._get_cascade_base", return_value="origin/main"),
        ):
            create_worktree("myplat", "001-feat")

        assert mock_run.call_count == 2
        wt_add_call = mock_run.call_args_list[1][0][0]
        assert "-b" in wt_add_call


# ──────────────────────────────────────────────────────────────────────────────
# cleanup_worktree
# ──────────────────────────────────────────────────────────────────────────────


class TestCleanupWorktree:
    def test_self_ref_noop(self):
        from worktree import cleanup_worktree

        with (
            patch("ensure_repo._load_repo_binding", return_value=_make_binding("madruga.ai")),
            patch("ensure_repo._is_self_ref", return_value=True),
            patch("worktree.subprocess.run") as mock_run,
        ):
            cleanup_worktree("myplat", "001-feat")

        mock_run.assert_not_called()

    def test_removes_worktree_and_branch(self, tmp_path):
        from worktree import cleanup_worktree

        repos_base = tmp_path / "repos"
        repo_path = repos_base / "myorg" / "other-repo"
        repo_path.mkdir(parents=True)
        wt_path = repos_base / "other-repo-worktrees" / "001-feat"
        wt_path.mkdir(parents=True)

        mock_wt_remove = MagicMock(returncode=0)
        mock_branch_del = MagicMock(returncode=0)

        with (
            patch("ensure_repo._load_repo_binding", return_value=_make_binding()),
            patch("ensure_repo._is_self_ref", return_value=False),
            patch("ensure_repo.ensure_repo", return_value=repo_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
            patch("worktree.subprocess.run", side_effect=[mock_wt_remove, mock_branch_del]),
        ):
            cleanup_worktree("myplat", "001-feat")

    def test_falls_back_to_rmtree_on_failure(self, tmp_path):
        from worktree import cleanup_worktree

        repos_base = tmp_path / "repos"
        repo_path = repos_base / "myorg" / "other-repo"
        repo_path.mkdir(parents=True)
        wt_path = repos_base / "other-repo-worktrees" / "001-feat"
        wt_path.mkdir(parents=True)

        mock_wt_fail = MagicMock(returncode=1)
        mock_branch_del = MagicMock(returncode=0)

        with (
            patch("ensure_repo._load_repo_binding", return_value=_make_binding()),
            patch("ensure_repo._is_self_ref", return_value=False),
            patch("ensure_repo.ensure_repo", return_value=repo_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
            patch("worktree.subprocess.run", side_effect=[mock_wt_fail, mock_branch_del]),
            patch("worktree.shutil.rmtree") as mock_rmtree,
        ):
            cleanup_worktree("myplat", "001-feat")

        assert mock_rmtree.call_count >= 1
