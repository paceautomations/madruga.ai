"""Tests for worktree.py — create/cleanup git worktrees."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".specify" / "scripts"))

from worktree import cleanup_worktree, create_worktree


BINDING = {
    "org": "testorg",
    "name": "testrepo",
    "base_branch": "main",
    "epic_branch_prefix": "epic/test/",
}

SELF_REF_BINDING = {
    "org": "paceautomations",
    "name": "madruga.ai",
    "base_branch": "main",
    "epic_branch_prefix": "epic/madruga-ai/",
}


class TestCreateWorktree:
    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._resolve_repos_base")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_create_worktree_new_branch(self, mock_self_ref, mock_bind, mock_base, mock_ensure, tmp_path):
        """US2: Creates worktree with new branch from origin/base."""
        mock_bind.return_value = BINDING
        mock_base.return_value = tmp_path
        repo_path = tmp_path / "testorg" / "testrepo"
        repo_path.mkdir(parents=True)
        mock_ensure.return_value = repo_path

        # branch does not exist on remote
        branch_check = MagicMock(stdout="", returncode=0)
        fetch_ok = MagicMock(returncode=0)
        wt_ok = MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=[fetch_ok, branch_check, wt_ok]) as mock_run:
            result = create_worktree("test", "001-feature")

        expected_wt = tmp_path / "testrepo-worktrees" / "001-feature"
        assert result == expected_wt

        # Should call git worktree add with -b flag
        wt_call = mock_run.call_args_list[-1]
        cmd = wt_call[0][0]
        assert "worktree" in cmd
        assert "add" in cmd
        assert "-b" in cmd

    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._resolve_repos_base")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_reuse_existing_worktree(self, mock_self_ref, mock_bind, mock_base, mock_ensure, tmp_path):
        """US2: Existing worktree is reused (crash recovery)."""
        mock_bind.return_value = BINDING
        mock_base.return_value = tmp_path
        mock_ensure.return_value = tmp_path / "testorg" / "testrepo"

        # Create existing worktree dir with .git
        wt_path = tmp_path / "testrepo-worktrees" / "001-feature"
        wt_path.mkdir(parents=True)
        (wt_path / ".git").touch()

        with patch("subprocess.run") as mock_run:
            result = create_worktree("test", "001-feature")

        assert result == wt_path
        # Should NOT call git worktree add
        mock_run.assert_not_called()

    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=True)
    def test_self_ref_skips_worktree(self, mock_self_ref, mock_bind):
        """US2: Self-ref platform returns REPO_ROOT without creating worktree."""
        mock_bind.return_value = SELF_REF_BINDING

        with patch("subprocess.run") as mock_run:
            result = create_worktree("madruga-ai", "012-multi-repo")

        from ensure_repo import REPO_ROOT

        assert result == REPO_ROOT
        mock_run.assert_not_called()

    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._resolve_repos_base")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_branch_already_on_remote(self, mock_self_ref, mock_bind, mock_base, mock_ensure, tmp_path):
        """US2: Remote branch exists → checkout without -b."""
        mock_bind.return_value = BINDING
        mock_base.return_value = tmp_path
        repo_path = tmp_path / "testorg" / "testrepo"
        repo_path.mkdir(parents=True)
        mock_ensure.return_value = repo_path

        # branch exists on remote
        branch_check = MagicMock(stdout="  origin/epic/test/001-feature\n", returncode=0)
        fetch_ok = MagicMock(returncode=0)
        wt_ok = MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=[fetch_ok, branch_check, wt_ok]) as mock_run:
            create_worktree("test", "001-feature")

        # Should call git worktree add WITHOUT -b flag
        wt_call = mock_run.call_args_list[-1]
        cmd = wt_call[0][0]
        assert "worktree" in cmd
        assert "add" in cmd
        assert "-b" not in cmd


class TestCleanupWorktree:
    @patch("ensure_repo.ensure_repo")
    @patch("ensure_repo._resolve_repos_base")
    @patch("ensure_repo._load_repo_binding")
    @patch("ensure_repo._is_self_ref", return_value=False)
    def test_cleanup_worktree(self, mock_self_ref, mock_bind, mock_base, mock_ensure, tmp_path):
        """US2: Cleanup removes worktree and deletes branch."""
        mock_bind.return_value = BINDING
        mock_base.return_value = tmp_path
        repo_path = tmp_path / "testorg" / "testrepo"
        repo_path.mkdir(parents=True)
        mock_ensure.return_value = repo_path

        # Create worktree dir
        wt_path = tmp_path / "testrepo-worktrees" / "001-feature"
        wt_path.mkdir(parents=True)

        remove_ok = MagicMock(returncode=0, stderr="")
        branch_ok = MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=[remove_ok, branch_ok]) as mock_run:
            cleanup_worktree("test", "001-feature")

        calls = mock_run.call_args_list
        # First: git worktree remove
        assert "worktree" in calls[0][0][0]
        assert "remove" in calls[0][0][0]
        # Second: git branch -d
        assert "branch" in calls[1][0][0]
        assert "-d" in calls[1][0][0]
