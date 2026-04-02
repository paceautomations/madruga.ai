"""Tests for hook_skill_lint.py — PostToolUse skill-lint hook."""

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent

sys.path.insert(0, str(SCRIPTS_DIR))
import hook_skill_lint


# ── Helpers ──────────────────────────────────────────────────────────


def _run_main(payload: dict | str, mock_run_return=None):
    """Run hook_skill_lint.main() with mocked stdin and subprocess."""
    raw = json.dumps(payload) if isinstance(payload, dict) else payload
    with (
        patch("sys.stdin", io.StringIO(raw)),
        patch("subprocess.run", return_value=mock_run_return) as mock_run,
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        hook_skill_lint.main()
        return mock_run, mock_out.getvalue()


def _make_run_result(findings: list) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[],
        returncode=0 if not findings else 1,
        stdout=json.dumps(findings),
        stderr="",
    )


# ── Tests ────────────────────────────────────────────────────────────


def test_non_claude_file_exits_silently():
    """Files outside .claude/ should not trigger lint."""
    payload = {"tool_input": {"file_path": "platforms/fulano/business/vision.md"}}
    mock_run, output = _run_main(payload)
    mock_run.assert_not_called()
    assert output == ""


def test_command_file_lints_single_skill():
    """Editing a command file should lint that specific skill."""
    path = f"{REPO_ROOT}/.claude/commands/madruga/vision.md"
    payload = {"tool_input": {"file_path": path}}
    mock_run, _ = _run_main(payload, _make_run_result([]))
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "--skill" in args
    assert "vision" in args
    assert "--json" in args


def test_knowledge_file_lints_full():
    """Editing a knowledge file should run full lint."""
    path = f"{REPO_ROOT}/.claude/knowledge/pipeline-dag-knowledge.md"
    payload = {"tool_input": {"file_path": path}}
    mock_run, _ = _run_main(payload, _make_run_result([]))
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "--skill" not in args
    assert "--json" in args


def test_invalid_json_exits_silently():
    """Invalid JSON on stdin should not crash."""
    with patch("sys.stdin", io.StringIO("not json")):
        hook_skill_lint.main()  # should not raise


def test_missing_file_path_exits_silently():
    """Missing file_path in payload should exit silently."""
    mock_run, output = _run_main({"tool_input": {}})
    mock_run.assert_not_called()
    assert output == ""


def test_blocker_findings_printed():
    """BLOCKER findings should appear in stdout."""
    path = f"{REPO_ROOT}/.claude/commands/madruga/vision.md"
    findings = [
        {"skill": "vision", "severity": "BLOCKER", "message": "Missing description"},
        {"skill": "vision", "severity": "NIT", "message": "PT-BR missing"},
    ]
    _, output = _run_main(
        {"tool_input": {"file_path": path}},
        _make_run_result(findings),
    )
    assert "[skill-lint]" in output
    assert "BLOCKER" in output
    assert "Missing description" in output
    # NITs should NOT appear
    assert "PT-BR missing" not in output


def test_no_findings_no_output():
    """No findings should produce no output."""
    path = f"{REPO_ROOT}/.claude/commands/madruga/vision.md"
    _, output = _run_main(
        {"tool_input": {"file_path": path}},
        _make_run_result([]),
    )
    assert output == ""


def test_only_nits_no_output():
    """Only NIT findings should produce no output."""
    path = f"{REPO_ROOT}/.claude/commands/madruga/vision.md"
    findings = [{"skill": "vision", "severity": "NIT", "message": "minor"}]
    _, output = _run_main(
        {"tool_input": {"file_path": path}},
        _make_run_result(findings),
    )
    assert output == ""


def test_subprocess_timeout_exits_silently():
    """Subprocess timeout should not crash the hook."""
    path = f"{REPO_ROOT}/.claude/commands/madruga/vision.md"
    payload = {"tool_input": {"file_path": path}}
    raw = json.dumps(payload)
    with (
        patch("sys.stdin", io.StringIO(raw)),
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="lint", timeout=15)),
        patch("sys.stdout", new_callable=io.StringIO) as mock_out,
    ):
        hook_skill_lint.main()
        assert mock_out.getvalue() == ""


def test_relative_path_works():
    """Relative paths (without repo root prefix) should also work."""
    payload = {"tool_input": {"file_path": ".claude/commands/madruga/adr.md"}}
    mock_run, _ = _run_main(payload, _make_run_result([]))
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "adr" in args
