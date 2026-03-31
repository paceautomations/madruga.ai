"""Tests for ensure_repo.py — clone/fetch with SSH/HTTPS fallback and locking."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".specify" / "scripts"))

from ensure_repo import (
    REPO_ROOT,
    _is_self_ref,
    _load_repo_binding,
    _resolve_repos_base,
    ensure_repo,
)


# ── Helper Tests ─────────────────────────────────────────────────────


class TestLoadRepoBinding:
    def test_loads_fulano_binding(self):
        binding = _load_repo_binding("fulano")
        assert binding["org"] == "paceautomations"
        assert binding["name"] == "fulano-api"
        assert binding["base_branch"] == "main"
        assert binding["epic_branch_prefix"] == "epic/fulano/"

    def test_missing_platform_exits(self):
        with pytest.raises(SystemExit, match="not found"):
            _load_repo_binding("nonexistent-platform-xyz")


class TestIsSelfRef:
    def test_madruga_ai_is_self_ref(self):
        assert _is_self_ref("madruga.ai") is True

    def test_external_repo_is_not_self_ref(self):
        assert _is_self_ref("fulano-api") is False


class TestResolveReposBase:
    @patch("db.get_local_config", return_value="/custom/repos")
    @patch("db.get_conn")
    def test_uses_db_value(self, mock_conn, mock_config):
        result = _resolve_repos_base()
        assert result == Path("/custom/repos")

    @patch("db.get_conn", side_effect=Exception("no db"))
    def test_defaults_to_home_repos(self, mock_conn):
        result = _resolve_repos_base()
        assert result == Path.home() / "repos"


# ── ensure_repo Tests ────────────────────────────────────────────────


class TestEnsureRepo:
    def test_self_ref_returns_repo_root(self):
        """US1: Self-ref detection returns REPO_ROOT without calling git."""
        with patch("ensure_repo._load_repo_binding") as mock_bind:
            mock_bind.return_value = {
                "org": "paceautomations",
                "name": "madruga.ai",
                "base_branch": "main",
                "epic_branch_prefix": "epic/madruga-ai/",
            }
            with patch("subprocess.run") as mock_run:
                result = ensure_repo("madruga-ai")
                assert result == REPO_ROOT
                mock_run.assert_not_called()

    @patch("ensure_repo._resolve_repos_base")
    @patch("ensure_repo._load_repo_binding")
    def test_clone_ssh_success(self, mock_bind, mock_base, tmp_path):
        """US1: SSH clone succeeds on first try."""
        mock_bind.return_value = {
            "org": "testorg",
            "name": "testrepo",
            "base_branch": "main",
            "epic_branch_prefix": "epic/test/",
        }
        mock_base.return_value = tmp_path

        ssh_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=ssh_result) as mock_run:
            with patch("fcntl.flock"):
                with patch("builtins.open", mock_open()):
                    result = ensure_repo("test")

        assert result == tmp_path / "testorg" / "testrepo"
        # Should have called git clone with SSH URL
        clone_call = mock_run.call_args_list[0]
        assert "git@github.com:testorg/testrepo.git" in clone_call[0][0]

    @patch("ensure_repo._resolve_repos_base")
    @patch("ensure_repo._load_repo_binding")
    def test_clone_ssh_fail_https_fallback(self, mock_bind, mock_base, tmp_path):
        """US1: SSH fails, HTTPS fallback succeeds."""
        mock_bind.return_value = {
            "org": "testorg",
            "name": "testrepo",
            "base_branch": "main",
            "epic_branch_prefix": "epic/test/",
        }
        mock_base.return_value = tmp_path

        ssh_fail = MagicMock(returncode=128)
        https_ok = MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=[ssh_fail, https_ok]) as mock_run:
            with patch("fcntl.flock"):
                with patch("builtins.open", mock_open()):
                    result = ensure_repo("test")

        assert result == tmp_path / "testorg" / "testrepo"
        # Second call should be HTTPS
        https_call = mock_run.call_args_list[1]
        assert "https://github.com/testorg/testrepo.git" in https_call[0][0]

    @patch("ensure_repo._resolve_repos_base")
    @patch("ensure_repo._load_repo_binding")
    def test_existing_repo_fetches(self, mock_bind, mock_base, tmp_path):
        """US1: Existing repo with .git runs fetch instead of clone."""
        mock_bind.return_value = {
            "org": "testorg",
            "name": "testrepo",
            "base_branch": "main",
            "epic_branch_prefix": "epic/test/",
        }
        mock_base.return_value = tmp_path

        # Create a dir with .git
        repo_dir = tmp_path / "testorg" / "testrepo"
        (repo_dir / ".git").mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            result = ensure_repo("test")

        assert result == repo_dir
        mock_run.assert_called_once()
        assert "fetch" in mock_run.call_args[0][0]

    @patch("ensure_repo._resolve_repos_base")
    @patch("ensure_repo._load_repo_binding")
    def test_partial_clone_reclones(self, mock_bind, mock_base, tmp_path):
        """US1: Dir without .git is removed and re-cloned."""
        mock_bind.return_value = {
            "org": "testorg",
            "name": "testrepo",
            "base_branch": "main",
            "epic_branch_prefix": "epic/test/",
        }
        mock_base.return_value = tmp_path

        # Create dir WITHOUT .git
        repo_dir = tmp_path / "testorg" / "testrepo"
        repo_dir.mkdir(parents=True)
        (repo_dir / "some_file.txt").touch()

        ssh_ok = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=ssh_ok) as mock_run:
            with patch("fcntl.flock"):
                with patch("builtins.open", mock_open()):
                    result = ensure_repo("test")

        assert result == repo_dir
        # Should have called clone (not fetch)
        assert "clone" in mock_run.call_args_list[0][0][0][1] or "clone" in str(mock_run.call_args_list[0])

    @patch("ensure_repo._resolve_repos_base")
    @patch("ensure_repo._load_repo_binding")
    def test_locking_creates_lockfile(self, mock_bind, mock_base, tmp_path):
        """US1: fcntl.flock is called for clone operations."""
        mock_bind.return_value = {
            "org": "testorg",
            "name": "testrepo",
            "base_branch": "main",
            "epic_branch_prefix": "epic/test/",
        }
        mock_base.return_value = tmp_path

        ssh_ok = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=ssh_ok):
            with patch("fcntl.flock") as mock_flock:
                with patch("builtins.open", mock_open()) as mock_file:
                    ensure_repo("test")

        # flock should have been called (LOCK_EX and LOCK_UN)
        assert mock_flock.call_count >= 2
