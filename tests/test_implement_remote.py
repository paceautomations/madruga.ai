"""Tests for implement_remote.py — orchestrator + prompt composition + PR."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".specify" / "scripts"))

from implement_remote import compose_prompt, create_pr, run_implement


# ── Prompt Composition Tests ─────────────────────────────────────────


class TestComposePrompt:
    def test_compose_prompt_all_artifacts(self, tmp_path):
        """US3: All 4 artifacts included with headers in correct order."""
        epic_dir = tmp_path / "platforms" / "test" / "epics" / "001"
        epic_dir.mkdir(parents=True)
        (epic_dir / "context.md").write_text("Context content")
        (epic_dir / "spec.md").write_text("Spec content")
        (epic_dir / "plan.md").write_text("Plan content")
        (epic_dir / "tasks.md").write_text("Tasks content")

        with patch("implement_remote.REPO_ROOT", tmp_path):
            prompt = compose_prompt("test", "001")

        assert "## Epic Context" in prompt
        assert "## Feature Specification" in prompt
        assert "## Implementation Plan" in prompt
        assert "## Tasks" in prompt
        # Order: context before spec before plan before tasks
        assert prompt.index("Context") < prompt.index("Spec")
        assert prompt.index("Spec") < prompt.index("Plan")
        assert prompt.index("Plan") < prompt.index("Tasks content")

    def test_compose_prompt_missing_optional(self, tmp_path):
        """US3: Works without context.md (optional)."""
        epic_dir = tmp_path / "platforms" / "test" / "epics" / "001"
        epic_dir.mkdir(parents=True)
        (epic_dir / "spec.md").write_text("Spec content")
        (epic_dir / "plan.md").write_text("Plan content")
        (epic_dir / "tasks.md").write_text("Tasks content")

        with patch("implement_remote.REPO_ROOT", tmp_path):
            prompt = compose_prompt("test", "001")

        assert "## Epic Context" not in prompt
        assert "## Feature Specification" in prompt

    def test_compose_prompt_truncates_large_context(self, tmp_path):
        """US3: context.md truncated when total > 100KB."""
        epic_dir = tmp_path / "platforms" / "test" / "epics" / "001"
        epic_dir.mkdir(parents=True)
        (epic_dir / "context.md").write_text("X" * 120_000)  # 120KB
        (epic_dir / "spec.md").write_text("Spec")
        (epic_dir / "plan.md").write_text("Plan")
        (epic_dir / "tasks.md").write_text("Tasks")

        with patch("implement_remote.REPO_ROOT", tmp_path):
            prompt = compose_prompt("test", "001")

        # Spec, plan, tasks should be intact
        assert "Spec" in prompt
        assert "Plan" in prompt
        assert "Tasks" in prompt
        # Context should be truncated
        assert "[... truncated for size ...]" in prompt or "[context.md truncated" in prompt

    def test_missing_required_exits(self, tmp_path):
        """US3: Missing required artifact raises SystemExit."""
        epic_dir = tmp_path / "platforms" / "test" / "epics" / "001"
        epic_dir.mkdir(parents=True)
        (epic_dir / "spec.md").write_text("Spec")
        # plan.md missing

        with patch("implement_remote.REPO_ROOT", tmp_path):
            with pytest.raises(SystemExit, match="Required artifact missing"):
                compose_prompt("test", "001")


# ── run_implement Tests ──────────────────────────────────────────────


class TestRunImplement:
    @patch("implement_remote.compose_prompt", return_value="test prompt")
    def test_invoke_claude_correct_args(self, mock_compose):
        """US3: claude -p called with --cwd pointing to worktree."""
        with (
            patch("ensure_repo._load_repo_binding") as mock_bind,
            patch("ensure_repo._is_self_ref", return_value=False),
            patch("worktree.create_worktree", return_value=Path("/tmp/wt")),
            patch("subprocess.run") as mock_run,
        ):
            mock_bind.return_value = {
                "org": "o",
                "name": "r",
                "base_branch": "main",
                "epic_branch_prefix": "e/",
            }
            mock_run.return_value = MagicMock(returncode=0)

            result = run_implement("test", "001", timeout=60)

        assert result == 0
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "claude"
        assert cmd[1] == "-p"
        assert "--cwd" in cmd
        assert "/tmp/wt" in cmd

    @patch("implement_remote.compose_prompt", return_value="test prompt")
    def test_timeout_returns_exit_3(self, mock_compose):
        """US3: Timeout returns exit code 3."""
        with (
            patch("ensure_repo._load_repo_binding") as mock_bind,
            patch("ensure_repo._is_self_ref", return_value=False),
            patch("worktree.create_worktree", return_value=Path("/tmp/wt")),
            patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=60),
            ),
        ):
            mock_bind.return_value = {
                "org": "o",
                "name": "r",
                "base_branch": "main",
                "epic_branch_prefix": "e/",
            }

            result = run_implement("test", "001", timeout=60)

        assert result == 3

    @patch("implement_remote.compose_prompt", return_value="test prompt")
    def test_self_ref_skips_clone_worktree(self, mock_compose):
        """US3: Self-ref platform uses REPO_ROOT directly."""
        with (
            patch("ensure_repo._load_repo_binding") as mock_bind,
            patch("ensure_repo._is_self_ref", return_value=True),
            patch("worktree.create_worktree") as mock_wt,
            patch("subprocess.run") as mock_run,
            patch("implement_remote.REPO_ROOT", Path("/repo")),
        ):
            mock_bind.return_value = {
                "org": "p",
                "name": "madruga.ai",
                "base_branch": "main",
                "epic_branch_prefix": "e/",
            }
            mock_run.return_value = MagicMock(returncode=0)

            result = run_implement("madruga-ai", "012")

        assert result == 0
        mock_wt.assert_not_called()
        # claude -p should use REPO_ROOT as cwd
        cmd = mock_run.call_args[0][0]
        assert "/repo" in cmd


# ── PR Tests ─────────────────────────────────────────────────────────


class TestCreatePR:
    @patch("shutil.which", return_value="/usr/bin/gh")
    def test_push_and_create_pr(self, mock_which, tmp_path):
        """US4: Push + gh pr create called with correct args."""
        push_ok = MagicMock(returncode=0, stderr="")
        pr_ok = MagicMock(returncode=0, stdout="https://github.com/org/repo/pull/1\n")

        with patch("subprocess.run", side_effect=[push_ok, pr_ok]) as mock_run:
            url = create_pr(tmp_path, "epic/test/001", "main", "Epic 001")

        assert url == "https://github.com/org/repo/pull/1"
        calls = mock_run.call_args_list
        # Push
        push_cmd = calls[0][0][0]
        assert "push" in push_cmd
        assert "epic/test/001" in push_cmd
        # PR
        pr_cmd = calls[1][0][0]
        assert "pr" in pr_cmd
        assert "create" in pr_cmd
        assert "--base" in pr_cmd

    @patch("shutil.which", return_value="/usr/bin/gh")
    def test_pr_already_exists(self, mock_which, tmp_path):
        """US4: Existing PR detected → returns URL via gh pr view."""
        push_ok = MagicMock(returncode=0, stderr="")
        pr_fail = MagicMock(returncode=1, stderr="already exists", stdout="")
        pr_view = MagicMock(returncode=0, stdout="https://github.com/org/repo/pull/1\n")

        with patch("subprocess.run", side_effect=[push_ok, pr_fail, pr_view]):
            url = create_pr(tmp_path, "epic/test/001", "main", "Epic 001")

        assert url == "https://github.com/org/repo/pull/1"

    @patch("shutil.which", return_value="/usr/bin/gh")
    def test_push_permission_error(self, mock_which, tmp_path):
        """US4: Push failure raises SystemExit with clear message."""
        push_fail = MagicMock(returncode=128, stderr="Permission denied (publickey)")

        with patch("subprocess.run", return_value=push_fail):
            with pytest.raises(SystemExit, match="git push failed"):
                create_pr(tmp_path, "epic/test/001", "main", "Epic 001")

    def test_gh_not_installed(self, tmp_path):
        """US4: Missing gh CLI raises clear error."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(SystemExit, match="gh CLI not found"):
                create_pr(tmp_path, "epic/test/001", "main", "Epic 001")
