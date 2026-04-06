"""Tests for implement_remote.py — prompt composition and PR creation."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import implement_remote


class TestComposePrompt:
    def _setup_epic(self, tmp_path, platform="myplat", epic="001-feature"):
        epic_dir = tmp_path / "platforms" / platform / "epics" / epic
        epic_dir.mkdir(parents=True)
        return epic_dir

    def test_all_artifacts_present(self, tmp_path):
        epic_dir = self._setup_epic(tmp_path)
        (epic_dir / "pitch.md").write_text("# Pitch\nSome pitch content")
        (epic_dir / "spec.md").write_text("# Spec\nSpecification")
        (epic_dir / "plan.md").write_text("# Plan\nPlan content")
        (epic_dir / "tasks.md").write_text("# Tasks\n- [ ] Task 1")

        with patch.object(implement_remote, "REPO_ROOT", tmp_path):
            prompt = implement_remote.compose_prompt("myplat", "001-feature")

        assert "Epic Pitch" in prompt
        assert "Feature Specification" in prompt
        assert "Implementation Plan" in prompt
        assert "Tasks" in prompt
        assert "Some pitch content" in prompt

    def test_missing_required_artifact_raises(self, tmp_path):
        epic_dir = self._setup_epic(tmp_path)
        (epic_dir / "pitch.md").write_text("# Pitch")
        # spec.md is required but missing

        with patch.object(implement_remote, "REPO_ROOT", tmp_path):
            with pytest.raises(SystemExit, match="Required artifact missing"):
                implement_remote.compose_prompt("myplat", "001-feature")

    def test_optional_pitch_missing_ok(self, tmp_path):
        epic_dir = self._setup_epic(tmp_path)
        # pitch.md is optional (required=False)
        (epic_dir / "spec.md").write_text("# Spec")
        (epic_dir / "plan.md").write_text("# Plan")
        (epic_dir / "tasks.md").write_text("# Tasks")

        with patch.object(implement_remote, "REPO_ROOT", tmp_path):
            prompt = implement_remote.compose_prompt("myplat", "001-feature")

        assert "Feature Specification" in prompt
        assert "Epic Pitch" not in prompt

    def test_truncation_when_too_large(self, tmp_path):
        epic_dir = self._setup_epic(tmp_path)
        # Make pitch.md very large
        large_content = "X" * 200_000
        (epic_dir / "pitch.md").write_text(large_content)
        (epic_dir / "spec.md").write_text("spec")
        (epic_dir / "plan.md").write_text("plan")
        (epic_dir / "tasks.md").write_text("tasks")

        with patch.object(implement_remote, "REPO_ROOT", tmp_path):
            prompt = implement_remote.compose_prompt("myplat", "001-feature")

        assert "truncated" in prompt.lower()


class TestCreatePr:
    def test_gh_missing_exits(self, tmp_path):
        with patch("implement_remote.shutil.which", return_value=None):
            with pytest.raises(SystemExit, match="gh CLI not found"):
                implement_remote.create_pr(tmp_path, "feature-branch", "main", "My PR")

    def test_push_fail_exits(self, tmp_path):
        push_fail = MagicMock()
        push_fail.returncode = 1
        push_fail.stderr = "push rejected"

        with (
            patch("implement_remote.shutil.which", return_value="/usr/bin/gh"),
            patch("implement_remote.subprocess.run", return_value=push_fail),
        ):
            with pytest.raises(SystemExit, match="git push failed"):
                implement_remote.create_pr(tmp_path, "feature-branch", "main", "My PR")

    def test_pr_created_returns_url(self, tmp_path):
        push_ok = MagicMock(returncode=0)
        pr_ok = MagicMock(returncode=0, stdout="https://github.com/org/repo/pull/42\n")

        with (
            patch("implement_remote.shutil.which", return_value="/usr/bin/gh"),
            patch("implement_remote.subprocess.run", side_effect=[push_ok, pr_ok]),
        ):
            url = implement_remote.create_pr(tmp_path, "feature-branch", "main", "My PR")

        assert url == "https://github.com/org/repo/pull/42"

    def test_pr_already_exists_fetches_url(self, tmp_path):
        push_ok = MagicMock(returncode=0)
        pr_exists = MagicMock(returncode=1, stderr="A pull request already exists")
        pr_view = MagicMock(returncode=0, stdout="https://github.com/org/repo/pull/99\n")

        with (
            patch("implement_remote.shutil.which", return_value="/usr/bin/gh"),
            patch("implement_remote.subprocess.run", side_effect=[push_ok, pr_exists, pr_view]),
        ):
            url = implement_remote.create_pr(tmp_path, "feature-branch", "main", "My PR")

        assert url == "https://github.com/org/repo/pull/99"


class TestRunImplement:
    """run_implement() does local imports from ensure_repo and dag_executor.
    Patch at the source module so the local `from X import Y` picks up mocks."""

    def test_dry_run_prints_prompt(self, tmp_path, capsys):
        epic_dir = tmp_path / "platforms" / "myplat" / "epics" / "001-feat"
        epic_dir.mkdir(parents=True)
        (epic_dir / "pitch.md").write_text("pitch")
        (epic_dir / "spec.md").write_text("spec")
        (epic_dir / "plan.md").write_text("plan")
        (epic_dir / "tasks.md").write_text("tasks")

        binding = {
            "org": "paceautomations",
            "name": "madruga.ai",
            "base_branch": "main",
            "epic_branch_prefix": "epic/myplat/",
        }

        with (
            patch.object(implement_remote, "REPO_ROOT", tmp_path),
            patch("ensure_repo._load_repo_binding", return_value=binding),
            patch("ensure_repo._is_self_ref", return_value=True),
        ):
            result = implement_remote.run_implement("myplat", "001-feat", dry_run=True)

        assert result == 0
        output = capsys.readouterr().out
        assert "spec" in output

    def test_timeout_returns_3(self, tmp_path):
        epic_dir = tmp_path / "platforms" / "myplat" / "epics" / "001-feat"
        epic_dir.mkdir(parents=True)
        (epic_dir / "pitch.md").write_text("pitch")
        (epic_dir / "spec.md").write_text("spec")
        (epic_dir / "plan.md").write_text("plan")
        (epic_dir / "tasks.md").write_text("tasks")

        binding = {
            "org": "paceautomations",
            "name": "madruga.ai",
            "base_branch": "main",
            "epic_branch_prefix": "epic/myplat/",
        }

        with (
            patch.object(implement_remote, "REPO_ROOT", tmp_path),
            patch("ensure_repo._load_repo_binding", return_value=binding),
            patch("ensure_repo._is_self_ref", return_value=True),
            patch("dag_executor.build_dispatch_cmd", return_value=["echo", "test"]),
            patch("implement_remote.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 10)),
        ):
            result = implement_remote.run_implement("myplat", "001-feat", timeout=10)

        assert result == 3

    def test_failure_returns_2(self, tmp_path):
        epic_dir = tmp_path / "platforms" / "myplat" / "epics" / "001-feat"
        epic_dir.mkdir(parents=True)
        (epic_dir / "pitch.md").write_text("pitch")
        (epic_dir / "spec.md").write_text("spec")
        (epic_dir / "plan.md").write_text("plan")
        (epic_dir / "tasks.md").write_text("tasks")

        binding = {
            "org": "paceautomations",
            "name": "madruga.ai",
            "base_branch": "main",
            "epic_branch_prefix": "epic/myplat/",
        }
        fail_result = MagicMock(returncode=1)

        with (
            patch.object(implement_remote, "REPO_ROOT", tmp_path),
            patch("ensure_repo._load_repo_binding", return_value=binding),
            patch("ensure_repo._is_self_ref", return_value=True),
            patch("dag_executor.build_dispatch_cmd", return_value=["echo", "test"]),
            patch("implement_remote.subprocess.run", return_value=fail_result),
        ):
            result = implement_remote.run_implement("myplat", "001-feat")

        assert result == 2
