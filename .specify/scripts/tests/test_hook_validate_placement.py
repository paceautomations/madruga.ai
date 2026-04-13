"""Tests for hook_validate_placement.py — PostToolUse placement guard."""

import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import hook_validate_placement


def _run_hook(payload: dict | str, tmp_path: Path | None = None) -> str:
    """Run hook main() with given stdin payload. Returns captured stderr."""
    if isinstance(payload, dict):
        stdin = io.StringIO(json.dumps(payload))
    else:
        stdin = io.StringIO(payload)

    stderr = io.StringIO()
    patches = [
        patch.object(sys, "stdin", stdin),
        patch.object(sys, "stderr", stderr),
    ]
    if tmp_path is not None:
        patches.append(patch.object(hook_validate_placement, "REPO_ROOT", tmp_path))
        # Clear caches that depend on REPO_ROOT.
        hook_validate_placement._load_platform_repo_name.cache_clear()
        hook_validate_placement._list_platform_dirs.cache_clear()

    for p in patches:
        p.start()
    try:
        hook_validate_placement.main()
    finally:
        for p in patches:
            p.stop()
        hook_validate_placement._load_platform_repo_name.cache_clear()
        hook_validate_placement._list_platform_dirs.cache_clear()

    return stderr.getvalue()


def _make_platform(tmp_path: Path, name: str, repo_name: str) -> None:
    """Create a minimal platform.yaml under tmp_path/platforms/<name>/."""
    d = tmp_path / "platforms" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "platform.yaml").write_text(f"name: {name}\nrepo:\n  org: paceautomations\n  name: {repo_name}\n")


class TestInvalidInput:
    def test_invalid_json_exits_silently(self):
        stderr = _run_hook("not json {{{{")
        assert stderr == ""

    def test_missing_file_path_exits_silently(self):
        stderr = _run_hook({"other_key": "value"})
        assert stderr == ""

    def test_empty_file_path_exits_silently(self):
        stderr = _run_hook({"tool_input": {"file_path": ""}})
        assert stderr == ""


class TestSafePrefixes:
    def test_claude_dir_no_warning(self, tmp_path):
        _make_platform(tmp_path, "prosauai", "prosauai")
        payload = {"tool_input": {"file_path": str(tmp_path / ".claude/commands/foo.md")}}
        stderr = _run_hook(payload, tmp_path)
        assert stderr == ""

    def test_platforms_dir_no_warning(self, tmp_path):
        _make_platform(tmp_path, "prosauai", "prosauai")
        payload = {"tool_input": {"file_path": str(tmp_path / "platforms/prosauai/pitch.md")}}
        stderr = _run_hook(payload, tmp_path)
        assert stderr == ""

    def test_specify_dir_no_warning(self, tmp_path):
        payload = {"tool_input": {"file_path": str(tmp_path / ".specify/scripts/foo.py")}}
        stderr = _run_hook(payload, tmp_path)
        assert stderr == ""

    def test_pipeline_migrations_no_warning(self, tmp_path):
        payload = {"tool_input": {"file_path": str(tmp_path / ".pipeline/migrations/001.sql")}}
        stderr = _run_hook(payload, tmp_path)
        assert stderr == ""


class TestForbiddenRootPatterns:
    def test_root_migrations_warns(self, tmp_path):
        payload = {"tool_input": {"file_path": str(tmp_path / "migrations/001.sql")}}
        stderr = _run_hook(payload, tmp_path)
        assert "WARNING" in stderr
        assert ".pipeline/migrations/" in stderr

    def test_root_docker_compose_warns(self, tmp_path):
        payload = {"tool_input": {"file_path": str(tmp_path / "docker-compose.yml")}}
        stderr = _run_hook(payload, tmp_path)
        assert "WARNING" in stderr
        assert "not a Docker app" in stderr

    def test_root_docker_compose_prod_warns(self, tmp_path):
        payload = {"tool_input": {"file_path": str(tmp_path / "docker-compose.prod.yml")}}
        stderr = _run_hook(payload, tmp_path)
        assert "WARNING" in stderr

    def test_root_dockerfile_warns(self, tmp_path):
        payload = {"tool_input": {"file_path": str(tmp_path / "Dockerfile")}}
        stderr = _run_hook(payload, tmp_path)
        assert "WARNING" in stderr


class TestExternalPlatformDetection:
    def test_external_platform_dir_warns(self, tmp_path):
        _make_platform(tmp_path, "prosauai", "prosauai")
        payload = {"tool_input": {"file_path": str(tmp_path / "prosauai/main.py")}}
        stderr = _run_hook(payload, tmp_path)
        assert "WARNING" in stderr
        assert "prosauai" in stderr
        assert "external" in stderr.lower()

    def test_self_ref_platform_no_warning(self, tmp_path):
        _make_platform(tmp_path, "madruga-ai", "madruga.ai")
        payload = {"tool_input": {"file_path": str(tmp_path / "madruga-ai/foo.py")}}
        stderr = _run_hook(payload, tmp_path)
        assert stderr == ""

    def test_nonexistent_platform_no_warning(self, tmp_path):
        # Top-level dir that doesn't match any platform.
        payload = {"tool_input": {"file_path": str(tmp_path / "randomdir/foo.py")}}
        stderr = _run_hook(payload, tmp_path)
        assert stderr == ""


class TestRobustness:
    def test_bad_yaml_no_crash(self, tmp_path):
        d = tmp_path / "platforms" / "badplatform"
        d.mkdir(parents=True)
        (d / "platform.yaml").write_text("{{{{invalid yaml")
        payload = {"tool_input": {"file_path": str(tmp_path / "badplatform/foo.py")}}
        # Should not raise — hook catches all exceptions.
        _run_hook(payload, tmp_path)  # Should not raise.

    def test_file_outside_repo_no_warning(self):
        payload = {"tool_input": {"file_path": "/tmp/random/file.py"}}
        stderr = _run_hook(payload)
        assert stderr == ""
