"""Tests for qa_startup.py — Runtime QA & Testing Pyramid.

Coverage:
  - load_manifest: valid block, absent block, incomplete block, missing file
  - parse_journeys: valid YAML blocks, malformed blocks, non-journey blocks
  - _read_env_keys: present/absent files, comments, complex values
  - validate_env: required present/absent, optional absent
  - quick_check: mock urlopen → 200/timeout/error
  - wait_for_health: successful polling, timeout with docker logs
  - execute_startup: mock subprocess.run per type including none
  - validate_urls + _is_placeholder: all 4 FR-023 criteria, redirect, connection refused
  - main(): CLI argparse dispatch and exit codes

All tests use unittest.mock — no real services required.
"""

from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qa_startup import (
    Finding,
    HealthCheck,
    HealthCheckResult,
    StartupConfig,
    StartupResult,
    TestingManifest,
    URLEntry,
    URLResult,
    _is_placeholder,
    _read_env_keys,
    execute_startup,
    load_manifest,
    main,
    parse_journeys,
    quick_check,
    run_full,
    start_services,
    validate_env,
    validate_urls,
    wait_for_health,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_platform_yaml(testing_block: dict | None = None) -> str:
    data: dict = {
        "platform": "test-platform",
        "version": "1.0",
    }
    if testing_block is not None:
        data["testing"] = testing_block
    return yaml.dump(data)


def write_platform_yaml(tmp_path: Path, platform: str, content: str) -> Path:
    platform_dir = tmp_path / "platforms" / platform
    platform_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = platform_dir / "platform.yaml"
    yaml_path.write_text(content)
    return yaml_path


def minimal_manifest(startup_type: str = "none") -> TestingManifest:
    return TestingManifest(
        startup=StartupConfig(type=startup_type),
        health_checks=[],
        urls=[],
        required_env=[],
        env_file=None,
        journeys_file=None,
    )


# ---------------------------------------------------------------------------
# load_manifest
# ---------------------------------------------------------------------------


class TestLoadManifest:
    def test_valid_testing_block(self, tmp_path):
        testing = {
            "startup": {"type": "docker", "command": None, "ready_timeout": 120},
            "health_checks": [{"url": "http://localhost:8050/health", "label": "API", "method": "GET", "expect_status": 200}],
            "urls": [{"url": "http://localhost:3000", "type": "frontend", "label": "Frontend"}],
            "required_env": ["JWT_SECRET", "DB_URL"],
            "env_file": ".env.example",
            "journeys_file": "testing/journeys.md",
        }
        write_platform_yaml(tmp_path, "my-platform", make_platform_yaml(testing))
        manifest = load_manifest("my-platform", tmp_path)
        assert manifest is not None
        assert manifest.startup.type == "docker"
        assert manifest.startup.ready_timeout == 120
        assert len(manifest.health_checks) == 1
        assert manifest.health_checks[0].url == "http://localhost:8050/health"
        assert len(manifest.urls) == 1
        assert manifest.urls[0].type == "frontend"
        assert manifest.required_env == ["JWT_SECRET", "DB_URL"]
        assert manifest.env_file == ".env.example"
        assert manifest.journeys_file == "testing/journeys.md"

    def test_absent_testing_block_returns_none(self, tmp_path):
        write_platform_yaml(tmp_path, "my-platform", make_platform_yaml(None))
        assert load_manifest("my-platform", tmp_path) is None

    def test_missing_platform_file_returns_none(self, tmp_path):
        assert load_manifest("nonexistent", tmp_path) is None

    def test_minimal_testing_block_uses_defaults(self, tmp_path):
        testing = {"startup": {"type": "npm"}}
        write_platform_yaml(tmp_path, "my-platform", make_platform_yaml(testing))
        manifest = load_manifest("my-platform", tmp_path)
        assert manifest is not None
        assert manifest.startup.type == "npm"
        assert manifest.startup.ready_timeout == 60
        assert manifest.health_checks == []
        assert manifest.urls == []
        assert manifest.required_env == []
        assert manifest.env_file is None

    def test_testing_block_with_list_expect_status(self, tmp_path):
        testing = {
            "startup": {"type": "none"},
            "urls": [
                {
                    "url": "http://localhost:8050/api/login",
                    "type": "api",
                    "label": "Login",
                    "expect_status": [200, 401],
                }
            ],
        }
        write_platform_yaml(tmp_path, "my-platform", make_platform_yaml(testing))
        manifest = load_manifest("my-platform", tmp_path)
        assert manifest is not None
        assert manifest.urls[0].expect_status == [200, 401]

    def test_invalid_yaml_raises_value_error(self, tmp_path):
        """Invalid YAML raises ValueError (not None) so callers can produce useful diagnostics."""
        platform_dir = tmp_path / "platforms" / "bad-platform"
        platform_dir.mkdir(parents=True)
        (platform_dir / "platform.yaml").write_text("key: [unclosed")
        import pytest as _pytest
        with _pytest.raises(ValueError, match="not valid YAML"):
            load_manifest("bad-platform", tmp_path)

    def test_health_check_with_expect_body_contains(self, tmp_path):
        testing = {
            "startup": {"type": "docker"},
            "health_checks": [
                {
                    "url": "http://localhost:8050/health",
                    "label": "API",
                    "expect_body_contains": '"status"',
                }
            ],
        }
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        manifest = load_manifest("p", tmp_path)
        assert manifest.health_checks[0].expect_body_contains == '"status"'


# ---------------------------------------------------------------------------
# parse_journeys
# ---------------------------------------------------------------------------


class TestParseJourneys:
    def test_valid_journey_block(self):
        content = textwrap.dedent(
            """\
            ## J-001 — Happy Path

            ```yaml
            id: J-001
            title: "Happy Path"
            required: true
            steps:
              - type: api
                action: "GET http://localhost:8050/health"
                assert_status: 200
            ```
            """
        )
        journeys = parse_journeys(content)
        assert len(journeys) == 1
        assert journeys[0]["id"] == "J-001"
        assert journeys[0]["required"] is True
        assert journeys[0]["steps"][0]["type"] == "api"

    def test_multiple_journey_blocks(self):
        content = textwrap.dedent(
            """\
            ```yaml
            id: J-001
            title: "First"
            required: true
            steps: []
            ```

            ```yaml
            id: J-002
            title: "Second"
            required: false
            steps: []
            ```
            """
        )
        journeys = parse_journeys(content)
        assert len(journeys) == 2
        assert journeys[0]["id"] == "J-001"
        assert journeys[1]["id"] == "J-002"

    def test_malformed_yaml_block_skipped(self):
        content = textwrap.dedent(
            """\
            ```yaml
            id: J-001
            bad: [unclosed
            ```
            """
        )
        journeys = parse_journeys(content)
        assert journeys == []

    def test_non_journey_yaml_block_skipped(self):
        """YAML blocks without 'id' starting with 'J-' are ignored."""
        content = textwrap.dedent(
            """\
            ```yaml
            name: some-config
            value: 42
            ```
            """
        )
        journeys = parse_journeys(content)
        assert journeys == []

    def test_mixed_blocks_filters_correctly(self):
        content = textwrap.dedent(
            """\
            ```yaml
            id: J-001
            title: "Journey"
            required: true
            steps: []
            ```

            ```yaml
            name: not-a-journey
            ```

            ```yaml
            id: "J-002"
            title: "Another"
            required: false
            steps: []
            ```
            """
        )
        journeys = parse_journeys(content)
        assert len(journeys) == 2

    def test_empty_content_returns_empty_list(self):
        assert parse_journeys("") == []

    def test_journey_id_not_starting_with_J_dash_skipped(self):
        content = textwrap.dedent(
            """\
            ```yaml
            id: JOURNEY-001
            title: "Wrong format"
            required: true
            steps: []
            ```
            """
        )
        assert parse_journeys(content) == []


# ---------------------------------------------------------------------------
# _read_env_keys
# ---------------------------------------------------------------------------


class TestReadEnvKeys:
    def test_reads_keys_not_values(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("MY_SECRET=super_secret_value\nOTHER_KEY=123\n")
        keys = _read_env_keys(env_file)
        assert "MY_SECRET" in keys
        assert "OTHER_KEY" in keys
        # Ensure values are not included
        assert "super_secret_value" not in keys
        assert "123" not in keys

    def test_skips_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nKEY=value\n# Another comment\n")
        keys = _read_env_keys(env_file)
        assert keys == {"KEY"}

    def test_skips_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("\n\nKEY=value\n\n\n")
        keys = _read_env_keys(env_file)
        assert keys == {"KEY"}

    def test_absent_file_returns_empty_set(self, tmp_path):
        keys = _read_env_keys(tmp_path / ".env.nonexistent")
        assert keys == set()

    def test_complex_values_with_equals_in_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("DB_URL=postgresql://user:pass@host:5432/db?sslmode=require\n")
        keys = _read_env_keys(env_file)
        assert keys == {"DB_URL"}

    def test_key_without_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("EMPTY_KEY=\n")
        keys = _read_env_keys(env_file)
        assert "EMPTY_KEY" in keys

    def test_export_prefix_stripped(self, tmp_path):
        """Shell-compatible .env files may use 'export KEY=value' format."""
        env_file = tmp_path / ".env"
        env_file.write_text("export JWT_SECRET=abc\nexport DB_URL=postgresql://...\n")
        keys = _read_env_keys(env_file)
        assert keys == {"JWT_SECRET", "DB_URL"}, f"Got: {keys}"


# ---------------------------------------------------------------------------
# validate_env
# ---------------------------------------------------------------------------


class TestValidateEnv:
    def test_env_file_none_returns_ok(self, tmp_path):
        manifest = minimal_manifest()
        manifest.env_file = None
        result = validate_env(manifest, tmp_path)
        assert result.status == "ok"
        assert result.findings == []
        assert result.env_missing == []

    def test_all_required_present(self, tmp_path):
        (tmp_path / ".env").write_text("JWT_SECRET=abc\nDB_URL=postgresql://...\n")
        manifest = minimal_manifest()
        manifest.env_file = ".env.example"
        manifest.required_env = ["JWT_SECRET", "DB_URL"]
        result = validate_env(manifest, tmp_path)
        assert result.status == "ok"
        assert result.env_missing == []
        assert set(result.env_present) == {"JWT_SECRET", "DB_URL"}
        assert not any(f.level == "BLOCKER" for f in result.findings)

    def test_required_var_absent_triggers_blocker(self, tmp_path):
        (tmp_path / ".env").write_text("DB_URL=postgresql://...\n")
        manifest = minimal_manifest()
        manifest.env_file = ".env.example"
        manifest.required_env = ["JWT_SECRET", "DB_URL"]
        result = validate_env(manifest, tmp_path)
        assert result.status == "blocker"
        assert "JWT_SECRET" in result.env_missing
        assert any(f.level == "BLOCKER" and "JWT_SECRET" in f.message for f in result.findings)

    def test_optional_var_absent_triggers_warn(self, tmp_path):
        # env_file (.env.example) has SENTRY_DSN, but it's not in required_env
        # and not in .env → WARN
        (tmp_path / ".env.example").write_text("JWT_SECRET=\nSENTRY_DSN=\n")
        (tmp_path / ".env").write_text("JWT_SECRET=abc\n")
        manifest = minimal_manifest()
        manifest.env_file = ".env.example"
        manifest.required_env = ["JWT_SECRET"]
        result = validate_env(manifest, tmp_path)
        # JWT_SECRET is present — no BLOCKER
        assert "JWT_SECRET" not in result.env_missing
        # SENTRY_DSN is in example but not in .env and not required — WARN
        assert any(f.level == "WARN" and "SENTRY_DSN" in f.message for f in result.findings)

    def test_no_env_file_in_cwd_returns_blockers(self, tmp_path):
        # .env doesn't exist, required vars → all missing
        manifest = minimal_manifest()
        manifest.env_file = ".env.example"
        manifest.required_env = ["JWT_SECRET"]
        result = validate_env(manifest, tmp_path)
        assert "JWT_SECRET" in result.env_missing
        assert result.status == "blocker"

    def test_env_values_never_in_output(self, tmp_path):
        """FR-022: values must never appear in findings or result fields."""
        (tmp_path / ".env").write_text("MY_SECRET=super_sensitive_value_12345\n")
        manifest = minimal_manifest()
        manifest.env_file = ".env.example"
        manifest.required_env = ["MY_SECRET"]
        result = validate_env(manifest, tmp_path)
        result_json = json.dumps(
            {
                "findings": [{"message": f.message, "detail": f.detail} for f in result.findings],
                "env_missing": result.env_missing,
                "env_present": result.env_present,
            }
        )
        assert "super_sensitive_value_12345" not in result_json


# ---------------------------------------------------------------------------
# quick_check
# ---------------------------------------------------------------------------


class TestQuickCheck:
    def test_all_checks_pass(self):
        hc = HealthCheck(url="http://localhost:8050/health", expect_status=200, label="API")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "ok"}'
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert quick_check([hc]) is True

    def test_check_wrong_status_returns_false(self):
        hc = HealthCheck(url="http://localhost:8050/health", expect_status=200, label="API")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 503
        mock_resp.read.return_value = b""
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert quick_check([hc]) is False

    def test_connection_error_returns_false(self):
        hc = HealthCheck(url="http://localhost:9999/nope", expect_status=200, label="X")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            assert quick_check([hc]) is False

    def test_timeout_returns_false(self):
        hc = HealthCheck(url="http://localhost:9999/timeout", expect_status=200, label="X")
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
            assert quick_check([hc]) is False

    def test_empty_health_checks_returns_true(self):
        assert quick_check([]) is True

    def test_body_contains_check_passes(self):
        hc = HealthCheck(
            url="http://localhost:8050/health",
            expect_status=200,
            label="API",
            expect_body_contains='"status"',
        )
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "ok"}'
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert quick_check([hc]) is True

    def test_body_contains_check_fails(self):
        hc = HealthCheck(
            url="http://localhost:8050/health",
            expect_status=200,
            label="API",
            expect_body_contains='"status"',
        )
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        mock_resp.read.return_value = b"pong"
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert quick_check([hc]) is False


# ---------------------------------------------------------------------------
# wait_for_health
# ---------------------------------------------------------------------------


class TestWaitForHealth:
    def test_immediate_success(self):
        hcs = [HealthCheck(url="http://localhost:8050/health", expect_status=200, label="API")]
        with patch("qa_startup.quick_check", return_value=True):
            result = wait_for_health(hcs, "docker", timeout=10, cwd=Path("/tmp"))
        assert result.status == "ok"
        assert result.health_checks[0].status == "ok"

    def test_success_after_retry(self):
        hcs = [HealthCheck(url="http://localhost:8050/health", expect_status=200, label="API")]
        # First call fails, second succeeds
        with patch("qa_startup.quick_check", side_effect=[False, True]), \
             patch("time.sleep"):
            result = wait_for_health(hcs, "npm", timeout=10, cwd=Path("/tmp"))
        assert result.status == "ok"

    def test_timeout_triggers_blocker(self):
        hcs = [HealthCheck(url="http://localhost:8050/health", expect_status=200, label="API")]
        # Simulate time running out
        with patch("qa_startup.quick_check", return_value=False), \
             patch("time.monotonic", side_effect=[0, 0, 100, 100, 100, 100]), \
             patch("time.sleep"), \
             patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")), \
             patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(stdout="log line", stderr="", returncode=0)
            result = wait_for_health(hcs, "docker", timeout=5, cwd=Path("/tmp"))
        assert result.status == "blocker"
        assert any(f.level == "BLOCKER" for f in result.findings)

    def test_timeout_non_docker_no_logs(self):
        hcs = [HealthCheck(url="http://localhost:3000", expect_status=200, label="Frontend")]
        with patch("qa_startup.quick_check", return_value=False), \
             patch("time.monotonic", side_effect=[0, 0, 100, 100, 100, 100]), \
             patch("time.sleep"), \
             patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            result = wait_for_health(hcs, "npm", timeout=5, cwd=Path("/tmp"))
        assert result.status == "blocker"


# ---------------------------------------------------------------------------
# execute_startup
# ---------------------------------------------------------------------------


class TestExecuteStartup:
    def test_docker_type(self, tmp_path):
        manifest = minimal_manifest("docker")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            code, stderr = execute_startup(manifest, tmp_path)
        assert code == 0
        mock_run.assert_called_once()
        cmd_arg = mock_run.call_args[0][0]
        # Default commands use list form (shell=False) for security
        assert cmd_arg == ["docker", "compose", "up", "-d"]

    def test_npm_type(self, tmp_path):
        manifest = minimal_manifest("npm")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            code, _ = execute_startup(manifest, tmp_path)
        assert code == 0
        cmd_arg = mock_run.call_args[0][0]
        assert cmd_arg == ["npm", "run", "dev"]

    def test_make_type(self, tmp_path):
        manifest = minimal_manifest("make")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            code, _ = execute_startup(manifest, tmp_path)
        assert code == 0
        cmd_arg = mock_run.call_args[0][0]
        assert cmd_arg == ["make", "run"]

    def test_none_type_noop(self, tmp_path):
        manifest = minimal_manifest("none")
        with patch("subprocess.run") as mock_run:
            code, stderr = execute_startup(manifest, tmp_path)
        mock_run.assert_not_called()
        assert code == 0
        assert stderr == ""

    def test_script_type_uses_custom_command(self, tmp_path):
        manifest = minimal_manifest("script")
        manifest.startup.command = "./start.sh"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            code, _ = execute_startup(manifest, tmp_path)
        assert code == 0
        cmd_arg = mock_run.call_args[0][0]
        assert "./start.sh" in cmd_arg

    def test_command_override(self, tmp_path):
        manifest = minimal_manifest("docker")
        manifest.startup.command = "docker compose -f docker-compose.test.yml up -d"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            code, _ = execute_startup(manifest, tmp_path)
        cmd_arg = mock_run.call_args[0][0]
        assert "docker-compose.test.yml" in cmd_arg

    def test_command_failure(self, tmp_path):
        manifest = minimal_manifest("docker")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error: no such service")
            code, stderr = execute_startup(manifest, tmp_path)
        assert code == 1
        assert "no such service" in stderr

    def test_shell_metachar_command_uses_shell_true(self, tmp_path):
        """Commands with && must use shell=True to work correctly."""
        manifest = minimal_manifest("npm")
        manifest.startup.command = "cd portal && npm run dev"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            execute_startup(manifest, tmp_path)
        _, kwargs = mock_run.call_args
        assert kwargs.get("shell") is True

    def test_simple_custom_command_uses_shell_false(self, tmp_path):
        """Simple commands without metacharacters use shell=False (more secure)."""
        manifest = minimal_manifest("docker")
        manifest.startup.command = "docker compose -f docker-compose.test.yml up -d"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            execute_startup(manifest, tmp_path)
        _, kwargs = mock_run.call_args
        assert kwargs.get("shell") is False

    def test_venv_without_command_returns_error(self, tmp_path):
        manifest = minimal_manifest("venv")
        manifest.startup.command = None
        code, stderr = execute_startup(manifest, tmp_path)
        assert code == 2
        assert "No command configured" in stderr

    def test_timeout_expired(self, tmp_path):
        manifest = minimal_manifest("npm")
        with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("cmd", 30)):
            code, stderr = execute_startup(manifest, tmp_path)
        assert code == 1
        assert "timed out" in stderr.lower()

    def test_never_uses_docker_compose_down(self, tmp_path):
        """Invariant: docker compose down must never be called."""
        manifest = minimal_manifest("docker")
        calls_made = []

        def capture_run(cmd, **kwargs):
            calls_made.append(cmd)
            return MagicMock(returncode=0, stderr="")

        with patch("subprocess.run", side_effect=capture_run):
            execute_startup(manifest, tmp_path)

        for cmd in calls_made:
            assert "down" not in str(cmd), f"Destructive command found: {cmd}"


# ---------------------------------------------------------------------------
# _is_placeholder
# ---------------------------------------------------------------------------


class TestIsPlaceholder:
    def test_criterion_1_short_body(self):
        body = b"<html><body>Hi</body></html>"
        assert _is_placeholder(body, "text/html", "frontend") is True

    def test_criterion_1_long_body_not_placeholder(self):
        body = b"x" * 600
        # Not a placeholder by size, assume no other criteria
        result = _is_placeholder(body, "text/html", "frontend")
        assert result is False

    def test_criterion_2_react_app_literal(self):
        body = b"x" * 600 + b"React App" + b"x" * 600
        assert _is_placeholder(body, "text/html", "frontend") is True

    def test_criterion_2_vite_react(self):
        body = b"x" * 600 + b"Vite + React" + b"x" * 600
        assert _is_placeholder(body, "text/html", "frontend") is True

    def test_criterion_2_nginx_welcome(self):
        body = b"x" * 600 + b"Welcome to nginx" + b"x" * 600
        assert _is_placeholder(body, "text/html", "frontend") is True

    def test_criterion_2_it_works(self):
        body = b"x" * 600 + b"It works!" + b"x" * 600
        assert _is_placeholder(body, "text/html", "frontend") is True

    def test_criterion_2_js_needed(self):
        body = b"x" * 600 + b"You need to enable JavaScript" + b"x" * 600
        assert _is_placeholder(body, "text/html", "frontend") is True

    def test_criterion_3_empty_body_tag(self):
        body = b"x" * 600 + b"<body>   \n  </body>" + b"x" * 600
        assert _is_placeholder(body, "text/html", "frontend") is True

    def test_criterion_3_body_tag_with_content_not_placeholder(self):
        body = b"x" * 600 + b"<body><div>Real content here</div></body>" + b"x" * 600
        assert _is_placeholder(body, "text/html", "frontend") is False

    def test_criterion_4_non_html_content_type_frontend(self):
        body = b"x" * 600
        assert _is_placeholder(body, "application/json", "frontend") is True

    def test_criterion_4_non_html_api_type_not_placeholder(self):
        body = b"x" * 600
        # api type with JSON is fine
        assert _is_placeholder(body, "application/json", "api") is False

    def test_not_placeholder_real_content(self):
        body = b"<html><head><title>App</title></head><body><div id='root'><main>Real App Content goes here</main></div></body></html>" * 5
        assert _is_placeholder(body, "text/html; charset=utf-8", "frontend") is False


# ---------------------------------------------------------------------------
# validate_urls
# ---------------------------------------------------------------------------


class TestValidateUrls:
    def _make_manifest(self, urls: list[URLEntry]) -> TestingManifest:
        manifest = minimal_manifest("docker")
        manifest.urls = urls
        return manifest

    def _mock_response(self, status: int, body: bytes = b"x" * 600, content_type: str = "text/html"):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = status
        mock_resp.read.return_value = body
        # Use a MagicMock for headers so .get can be overridden
        headers_mock = MagicMock()
        headers_mock.get = lambda k, d="": content_type if k == "Content-Type" else d
        mock_resp.headers = headers_mock
        return mock_resp

    def test_successful_url(self):
        entry = URLEntry(url="http://localhost:8050/health", type="api", label="Health", expect_status=200)
        manifest = self._make_manifest([entry])
        with patch("urllib.request.build_opener") as mock_builder:
            opener = MagicMock()
            mock_builder.return_value = opener
            opener.open.return_value = self._mock_response(200)
            result = validate_urls(manifest)
        assert result.status == "ok"
        assert result.urls[0].ok is True

    def test_404_triggers_blocker(self):
        entry = URLEntry(url="http://localhost:3000/login", type="frontend", label="Login", expect_status=200)
        manifest = self._make_manifest([entry])
        with patch("urllib.request.build_opener") as mock_builder:
            opener = MagicMock()
            mock_builder.return_value = opener
            opener.open.return_value = self._mock_response(404)
            result = validate_urls(manifest)
        assert result.status == "blocker"
        assert any("404" in f.message for f in result.findings)
        assert result.urls[0].ok is False

    def test_connection_refused_triggers_blocker(self):
        entry = URLEntry(url="http://localhost:9999/nowhere", type="api", label="X", expect_status=200)
        manifest = self._make_manifest([entry])
        with patch("urllib.request.build_opener") as mock_builder:
            opener = MagicMock()
            mock_builder.return_value = opener
            opener.open.side_effect = urllib.error.URLError("connection refused")
            result = validate_urls(manifest)
        assert result.status == "blocker"
        assert result.urls[0].ok is False
        assert result.urls[0].status_code is None

    def test_list_expect_status_accepted(self):
        entry = URLEntry(
            url="http://localhost:8050/api/login",
            type="api",
            label="Login",
            expect_status=[200, 401],
        )
        manifest = self._make_manifest([entry])
        with patch("urllib.request.build_opener") as mock_builder:
            opener = MagicMock()
            mock_builder.return_value = opener
            opener.open.return_value = self._mock_response(401)
            result = validate_urls(manifest)
        assert result.urls[0].ok is True

    def test_placeholder_html_triggers_warn(self):
        entry = URLEntry(url="http://localhost:3000", type="frontend", label="Root", expect_status=200)
        manifest = self._make_manifest([entry])
        # Short body → placeholder
        with patch("urllib.request.build_opener") as mock_builder:
            opener = MagicMock()
            mock_builder.return_value = opener
            opener.open.return_value = self._mock_response(200, body=b"<html></html>")
            result = validate_urls(manifest)
        assert result.status == "warn"
        assert any(f.level == "WARN" for f in result.findings)

    def test_redirect_check_correct_location(self):
        entry = URLEntry(
            url="http://localhost:3000",
            type="frontend",
            label="Root",
            expect_redirect="/login",
        )
        manifest = self._make_manifest([entry])
        headers_mock = MagicMock()
        headers_mock.get = lambda k, d="": "/login" if k == "Location" else d
        http_err = urllib.error.HTTPError(
            "http://localhost:3000", 302, "Found", headers_mock, None
        )
        with patch("urllib.request.build_opener") as mock_builder:
            opener = MagicMock()
            mock_builder.return_value = opener
            opener.open.side_effect = http_err
            result = validate_urls(manifest)
        assert result.urls[0].ok is True

    def test_redirect_check_wrong_location(self):
        entry = URLEntry(
            url="http://localhost:3000",
            type="frontend",
            label="Root",
            expect_redirect="/login",
        )
        manifest = self._make_manifest([entry])
        headers_mock = MagicMock()
        headers_mock.get = lambda k, d="": "/dashboard" if k == "Location" else d
        http_err = urllib.error.HTTPError(
            "http://localhost:3000", 302, "Found", headers_mock, None
        )
        with patch("urllib.request.build_opener") as mock_builder:
            opener = MagicMock()
            mock_builder.return_value = opener
            opener.open.side_effect = http_err
            result = validate_urls(manifest)
        assert result.urls[0].ok is False
        assert any("BLOCKER" == f.level for f in result.findings)

    def test_expect_contains_missing_triggers_blocker(self):
        entry = URLEntry(
            url="http://localhost:3000/login",
            type="frontend",
            label="Login",
            expect_contains=["email", "password"],
        )
        manifest = self._make_manifest([entry])
        big_body = b"<html><body>" + b"x" * 600 + b"email field here but no pass</body></html>"
        with patch("urllib.request.build_opener") as mock_builder:
            opener = MagicMock()
            mock_builder.return_value = opener
            opener.open.return_value = self._mock_response(200, body=big_body)
            result = validate_urls(manifest)
        assert result.urls[0].ok is False


# ---------------------------------------------------------------------------
# start_services
# ---------------------------------------------------------------------------


class TestStartServices:
    def test_already_healthy_skips_startup(self):
        manifest = minimal_manifest("docker")
        manifest.health_checks = [
            HealthCheck(url="http://localhost:8050/health", expect_status=200, label="API")
        ]
        with patch("qa_startup.quick_check", return_value=True):
            result = start_services(manifest, Path("/tmp"))
        assert result.status == "ok"
        assert result.skipped_startup is True

    def test_none_type_returns_ok(self):
        manifest = minimal_manifest("none")
        result = start_services(manifest, Path("/tmp"))
        assert result.status == "ok"
        assert result.skipped_startup is True

    def test_startup_failure_returns_blocker(self):
        manifest = minimal_manifest("docker")
        with patch("qa_startup.quick_check", return_value=False), \
             patch("qa_startup.execute_startup", return_value=(1, "fatal error")):
            result = start_services(manifest, Path("/tmp"))
        assert result.status == "blocker"
        assert any("fatal error" in f.detail for f in result.findings)

    def test_startup_success_waits_for_health(self):
        manifest = minimal_manifest("npm")
        manifest.health_checks = [HealthCheck(url="http://localhost:3000", expect_status=200, label="FE")]
        health_result = StartupResult(status="ok", health_checks=[
            HealthCheckResult(label="FE", url="http://localhost:3000", status="ok")
        ])
        with patch("qa_startup.quick_check", return_value=False), \
             patch("qa_startup.execute_startup", return_value=(0, "")), \
             patch("qa_startup.wait_for_health", return_value=health_result):
            result = start_services(manifest, Path("/tmp"))
        assert result.status == "ok"


class TestRunFull:
    def test_short_circuits_validate_urls_on_startup_blocker(self):
        """When start_services returns BLOCKER, validate_urls must not be called."""
        manifest = minimal_manifest("docker")
        startup_blocker = StartupResult(
            status="blocker",
            findings=[Finding(level="BLOCKER", message="health check failed", detail="")],
        )
        env_ok = StartupResult(status="ok")
        with patch("qa_startup.start_services", return_value=startup_blocker), \
             patch("qa_startup.validate_env", return_value=env_ok), \
             patch("qa_startup.validate_urls") as mock_validate_urls:
            result = run_full(manifest, Path("/tmp"))
        mock_validate_urls.assert_not_called()
        assert result.status == "blocker"
        assert any(f.level == "INFO" and "skipped" in f.message for f in result.findings)

    def test_runs_validate_urls_when_startup_ok(self):
        manifest = minimal_manifest("docker")
        startup_ok = StartupResult(status="ok")
        env_ok = StartupResult(status="ok")
        urls_ok = StartupResult(status="ok")
        with patch("qa_startup.start_services", return_value=startup_ok), \
             patch("qa_startup.validate_env", return_value=env_ok), \
             patch("qa_startup.validate_urls", return_value=urls_ok) as mock_validate_urls:
            result = run_full(manifest, Path("/tmp"))
        mock_validate_urls.assert_called_once()
        assert result.status == "ok"


# ---------------------------------------------------------------------------
# main() — CLI dispatch and exit codes
# ---------------------------------------------------------------------------


class TestMain:
    def test_help_exits_zero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_parse_config_ok(self, tmp_path):
        testing = {"startup": {"type": "none"}}
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        with patch("qa_startup._detect_repo_root", return_value=tmp_path):
            code = main(["--platform", "p", "--parse-config", "--json"])
        assert code == 0

    def test_parse_config_missing_block_exits_2(self, tmp_path):
        write_platform_yaml(tmp_path, "p", make_platform_yaml(None))
        with patch("qa_startup._detect_repo_root", return_value=tmp_path):
            code = main(["--platform", "p", "--parse-config"])
        assert code == 2

    def test_validate_env_no_blockers_exits_0(self, tmp_path):
        testing = {"startup": {"type": "none"}, "required_env": [], "env_file": None}
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        with patch("qa_startup._detect_repo_root", return_value=tmp_path):
            code = main(["--platform", "p", "--validate-env", "--json"])
        assert code == 0

    def test_validate_env_blocker_exits_1(self, tmp_path):
        testing = {
            "startup": {"type": "none"},
            "required_env": ["MISSING_VAR"],
            "env_file": ".env.example",
        }
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        # No .env file → MISSING_VAR is absent
        with patch("qa_startup._detect_repo_root", return_value=tmp_path):
            code = main(["--platform", "p", "--validate-env"])
        assert code == 1

    def test_start_services_dispatched(self, tmp_path):
        testing = {"startup": {"type": "none"}}
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        with patch("qa_startup._detect_repo_root", return_value=tmp_path), \
             patch("qa_startup.start_services", return_value=StartupResult(status="ok")) as mock_start:
            code = main(["--platform", "p", "--start", "--json"])
        assert code == 0
        mock_start.assert_called_once()

    def test_validate_urls_dispatched(self, tmp_path):
        testing = {"startup": {"type": "none"}}
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        with patch("qa_startup._detect_repo_root", return_value=tmp_path), \
             patch("qa_startup.validate_urls", return_value=StartupResult(status="ok")) as mock_urls:
            code = main(["--platform", "p", "--validate-urls", "--json"])
        assert code == 0
        mock_urls.assert_called_once()

    def test_full_dispatched(self, tmp_path):
        testing = {"startup": {"type": "none"}}
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        with patch("qa_startup._detect_repo_root", return_value=tmp_path), \
             patch("qa_startup.run_full", return_value=StartupResult(status="ok")) as mock_full:
            code = main(["--platform", "p", "--full", "--json"])
        assert code == 0
        mock_full.assert_called_once()

    def test_blocker_result_exits_1(self, tmp_path):
        testing = {"startup": {"type": "none"}}
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        blocker_result = StartupResult(
            status="blocker",
            findings=[Finding(level="BLOCKER", message="something failed")],
        )
        with patch("qa_startup._detect_repo_root", return_value=tmp_path), \
             patch("qa_startup.validate_urls", return_value=blocker_result):
            code = main(["--platform", "p", "--validate-urls"])
        assert code == 1

    def test_json_output_is_valid_json(self, tmp_path, capsys):
        testing = {"startup": {"type": "none"}, "required_env": [], "env_file": None}
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        with patch("qa_startup._detect_repo_root", return_value=tmp_path):
            code = main(["--platform", "p", "--validate-env", "--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "status" in data
        assert "findings" in data
        assert "env_missing" in data

    def test_repo_root_from_env_var(self, tmp_path, monkeypatch):
        testing = {"startup": {"type": "none"}}
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        monkeypatch.setenv("REPO_ROOT", str(tmp_path))
        code = main(["--platform", "p", "--parse-config", "--json"])
        assert code == 0

    def test_cwd_argument_used(self, tmp_path):
        testing = {"startup": {"type": "none"}, "required_env": ["X"], "env_file": ".env"}
        write_platform_yaml(tmp_path, "p", make_platform_yaml(testing))
        # Create .env in a subdirectory
        subdir = tmp_path / "myapp"
        subdir.mkdir()
        (subdir / ".env").write_text("X=value\n")
        with patch("qa_startup._detect_repo_root", return_value=tmp_path):
            code = main(["--platform", "p", "--validate-env", "--cwd", str(subdir), "--json"])
        assert code == 0
