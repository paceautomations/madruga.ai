"""Tests for ensure_repo.py — clone/fetch with locking and fallback."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

import ensure_repo


class TestLoadRepoBinding:
    def test_happy_path(self, tmp_path):
        platform_dir = tmp_path / "platforms" / "myplat"
        platform_dir.mkdir(parents=True)
        manifest = {
            "repo": {
                "org": "myorg",
                "name": "myrepo",
                "base_branch": "develop",
            }
        }
        (platform_dir / "platform.yaml").write_text(yaml.dump(manifest))

        with patch.object(ensure_repo, "REPO_ROOT", tmp_path):
            result = ensure_repo._load_repo_binding("myplat")

        assert result["org"] == "myorg"
        assert result["name"] == "myrepo"
        assert result["base_branch"] == "develop"

    def test_defaults_base_branch_and_prefix(self, tmp_path):
        platform_dir = tmp_path / "platforms" / "myplat"
        platform_dir.mkdir(parents=True)
        manifest = {"repo": {"org": "myorg", "name": "myrepo"}}
        (platform_dir / "platform.yaml").write_text(yaml.dump(manifest))

        with patch.object(ensure_repo, "REPO_ROOT", tmp_path):
            result = ensure_repo._load_repo_binding("myplat")

        assert result["base_branch"] == "main"
        assert result["epic_branch_prefix"] == "epic/myplat/"

    def test_missing_manifest_exits(self, tmp_path):
        with patch.object(ensure_repo, "REPO_ROOT", tmp_path):
            with pytest.raises(SystemExit, match="not found"):
                ensure_repo._load_repo_binding("nonexistent")

    def test_missing_repo_block_exits(self, tmp_path):
        platform_dir = tmp_path / "platforms" / "myplat"
        platform_dir.mkdir(parents=True)
        (platform_dir / "platform.yaml").write_text(yaml.dump({"name": "myplat"}))

        with patch.object(ensure_repo, "REPO_ROOT", tmp_path):
            with pytest.raises(SystemExit, match="no repo"):
                ensure_repo._load_repo_binding("myplat")

    def test_missing_org_exits(self, tmp_path):
        platform_dir = tmp_path / "platforms" / "myplat"
        platform_dir.mkdir(parents=True)
        manifest = {"repo": {"name": "myrepo"}}
        (platform_dir / "platform.yaml").write_text(yaml.dump(manifest))

        with patch.object(ensure_repo, "REPO_ROOT", tmp_path):
            with pytest.raises(SystemExit, match="missing org or name"):
                ensure_repo._load_repo_binding("myplat")


class TestIsSelfRef:
    def test_self_ref_true(self):
        assert ensure_repo._is_self_ref("madruga.ai") is True

    def test_self_ref_false(self):
        assert ensure_repo._is_self_ref("other-repo") is False


class TestResolveReposBase:
    def test_db_available_returns_config(self):
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        with (
            patch("db.get_conn", return_value=mock_conn),
            patch("db.get_local_config", return_value="/custom/repos"),
        ):
            result = ensure_repo._resolve_repos_base()

        assert result == Path("/custom/repos")

    def test_db_unavailable_returns_default(self):
        with patch("db.get_conn", side_effect=Exception("no db")):
            result = ensure_repo._resolve_repos_base()

        assert result == Path.home() / "repos"


class TestEnsureRepo:
    def test_self_ref_returns_repo_root(self, tmp_path):
        platform_dir = tmp_path / "platforms" / "myplat"
        platform_dir.mkdir(parents=True)
        manifest = {"repo": {"org": "paceautomations", "name": "madruga.ai"}}
        (platform_dir / "platform.yaml").write_text(yaml.dump(manifest))

        with patch.object(ensure_repo, "REPO_ROOT", tmp_path):
            result = ensure_repo.ensure_repo("myplat")

        assert result == tmp_path

    def test_existing_repo_fetches(self, tmp_path):
        platform_dir = tmp_path / "platforms" / "myplat"
        platform_dir.mkdir(parents=True)
        manifest = {"repo": {"org": "myorg", "name": "myrepo"}}
        (platform_dir / "platform.yaml").write_text(yaml.dump(manifest))

        # Create fake existing repo
        repos_base = tmp_path / "repos"
        repo_path = repos_base / "myorg" / "myrepo"
        (repo_path / ".git").mkdir(parents=True)

        with (
            patch.object(ensure_repo, "REPO_ROOT", tmp_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
            patch("ensure_repo.subprocess.run") as mock_run,
        ):
            result = ensure_repo.ensure_repo("myplat")

        assert result == repo_path
        mock_run.assert_called_once()
        assert "fetch" in mock_run.call_args[0][0]

    def test_fresh_clone_ssh_success(self, tmp_path):
        platform_dir = tmp_path / "platforms" / "myplat"
        platform_dir.mkdir(parents=True)
        manifest = {"repo": {"org": "myorg", "name": "myrepo"}}
        (platform_dir / "platform.yaml").write_text(yaml.dump(manifest))

        repos_base = tmp_path / "repos"

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch.object(ensure_repo, "REPO_ROOT", tmp_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
            patch("ensure_repo.subprocess.run", return_value=mock_result) as mock_run,
            patch("ensure_repo.fcntl.flock"),
        ):
            result = ensure_repo.ensure_repo("myplat")

        assert result == repos_base / "myorg" / "myrepo"
        # Should have called clone (SSH)
        clone_call = mock_run.call_args_list[0]
        assert "clone" in clone_call[0][0]
        assert "git@github.com:" in clone_call[0][0][2]

    def test_ssh_fail_falls_back_to_https(self, tmp_path):
        platform_dir = tmp_path / "platforms" / "myplat"
        platform_dir.mkdir(parents=True)
        manifest = {"repo": {"org": "myorg", "name": "myrepo"}}
        (platform_dir / "platform.yaml").write_text(yaml.dump(manifest))

        repos_base = tmp_path / "repos"

        ssh_fail = MagicMock()
        ssh_fail.returncode = 1

        with (
            patch.object(ensure_repo, "REPO_ROOT", tmp_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
            patch("ensure_repo.subprocess.run", side_effect=[ssh_fail, MagicMock()]) as mock_run,
            patch("ensure_repo.fcntl.flock"),
        ):
            ensure_repo.ensure_repo("myplat")

        # Two calls: SSH clone (fail) + HTTPS clone (success)
        assert mock_run.call_count == 2
        https_call = mock_run.call_args_list[1]
        assert "https://github.com/" in https_call[0][0][2]

    def test_partial_clone_removed_and_recloned(self, tmp_path):
        platform_dir = tmp_path / "platforms" / "myplat"
        platform_dir.mkdir(parents=True)
        manifest = {"repo": {"org": "myorg", "name": "myrepo"}}
        (platform_dir / "platform.yaml").write_text(yaml.dump(manifest))

        repos_base = tmp_path / "repos"
        repo_path = repos_base / "myorg" / "myrepo"
        repo_path.mkdir(parents=True)  # exists but no .git

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch.object(ensure_repo, "REPO_ROOT", tmp_path),
            patch("ensure_repo._resolve_repos_base", return_value=repos_base),
            patch("ensure_repo.subprocess.run", return_value=mock_result),
            patch("ensure_repo.fcntl.flock"),
            patch("ensure_repo.shutil.rmtree") as mock_rmtree,
        ):
            ensure_repo.ensure_repo("myplat")

        mock_rmtree.assert_called_once_with(repo_path)


# ══════════════════════════════════════
# Epic 024: get_repo_work_dir tests (T054–T063)
# ══════════════════════════════════════


class TestGetRepoWorkDir:
    """T054–T058: get_repo_work_dir dispatch logic."""

    def test_selfref_short_circuits(self, tmp_path):
        """T054: Self-ref platform → returns REPO_ROOT, no git ops."""
        (tmp_path / "platforms" / "madruga-ai").mkdir(parents=True)
        (tmp_path / "platforms" / "madruga-ai" / "platform.yaml").write_text(
            "name: madruga-ai\nrepo:\n  org: paceautomations\n  name: madruga.ai\n"
        )

        with patch.object(ensure_repo, "REPO_ROOT", tmp_path):
            result = ensure_repo.get_repo_work_dir("madruga-ai", "001-test")

        assert result == tmp_path

    def test_worktree_mode_default(self, tmp_path):
        """T055: No isolation key → delegates to create_worktree."""
        (tmp_path / "platforms" / "ext").mkdir(parents=True)
        (tmp_path / "platforms" / "ext" / "platform.yaml").write_text(
            "name: ext\nrepo:\n  org: testorg\n  name: ext-repo\n  base_branch: main\n"
        )

        with (
            patch.object(ensure_repo, "REPO_ROOT", tmp_path),
            patch("worktree.create_worktree", return_value=Path("/tmp/wt")) as mock_wt,
        ):
            result = ensure_repo.get_repo_work_dir("ext", "001-test")

        assert result == Path("/tmp/wt")
        mock_wt.assert_called_once_with("ext", "001-test")

    def test_worktree_mode_explicit(self, tmp_path):
        """T056: isolation: worktree → delegates to create_worktree."""
        (tmp_path / "platforms" / "ext").mkdir(parents=True)
        (tmp_path / "platforms" / "ext" / "platform.yaml").write_text(
            "name: ext\nrepo:\n  org: testorg\n  name: ext-repo\n  isolation: worktree\n"
        )

        with (
            patch.object(ensure_repo, "REPO_ROOT", tmp_path),
            patch("worktree.create_worktree", return_value=Path("/tmp/wt")) as mock_wt,
        ):
            result = ensure_repo.get_repo_work_dir("ext", "001-test")

        assert result == Path("/tmp/wt")
        mock_wt.assert_called_once()

    def test_branch_mode_calls_checkout(self, tmp_path):
        """T057: isolation: branch → calls ensure_repo + _checkout_epic_branch."""
        (tmp_path / "platforms" / "ext").mkdir(parents=True)
        (tmp_path / "platforms" / "ext" / "platform.yaml").write_text(
            "name: ext\nrepo:\n  org: testorg\n  name: ext-repo\n"
            "  base_branch: develop\n  epic_branch_prefix: 'epic/ext/'\n"
            "  isolation: branch\n"
        )
        clone_path = tmp_path / "repos" / "ext-repo"
        clone_path.mkdir(parents=True)

        with (
            patch.object(ensure_repo, "REPO_ROOT", tmp_path),
            patch("ensure_repo.ensure_repo", return_value=clone_path) as mock_ensure,
            patch("queue_promotion._checkout_epic_branch") as mock_checkout,
        ):
            result = ensure_repo.get_repo_work_dir("ext", "001-test")

        assert result == clone_path
        mock_ensure.assert_called_once_with("ext")
        mock_checkout.assert_called_once()

    def test_unknown_isolation_raises(self, tmp_path):
        """T058: isolation: foo → ValueError."""
        (tmp_path / "platforms" / "ext").mkdir(parents=True)
        (tmp_path / "platforms" / "ext" / "platform.yaml").write_text(
            "name: ext\nrepo:\n  org: testorg\n  name: ext-repo\n  isolation: foo\n"
        )

        with (
            patch.object(ensure_repo, "REPO_ROOT", tmp_path),
            pytest.raises(ValueError, match="Unknown isolation mode"),
        ):
            ensure_repo.get_repo_work_dir("ext", "001-test")
