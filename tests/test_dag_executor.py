"""Tests for dag_executor.py (epic 013)."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".specify" / "scripts"))

import pytest

from dag_executor import (
    CircuitBreaker,
    Node,
    compose_skill_prompt,
    dispatch_node,
    dispatch_with_retry,
    parse_dag,
    topological_sort,
    verify_outputs,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def platform_yaml(tmp_path):
    """Create a minimal pipeline.yaml and patch config.PIPELINE_YAML."""
    content = textwrap.dedent("""\
        nodes:
          - id: alpha
            skill: "madruga:alpha"
            outputs: ["business/alpha.md"]
            depends: []
            gate: auto
            layer: business

          - id: beta
            skill: "madruga:beta"
            outputs: ["engineering/beta.md"]
            depends: ["alpha"]
            gate: human
            layer: engineering

          - id: gamma
            skill: "madruga:gamma"
            outputs: ["planning/gamma.md"]
            depends: ["alpha", "beta"]
            gate: auto
            layer: planning

        epic_cycle:
          nodes:
            - id: epic-context
              skill: "madruga:epic-context"
              outputs: ["{epic}/context.md"]
              depends: []
              gate: human

            - id: specify
              skill: "speckit.specify"
              outputs: ["{epic}/spec.md"]
              depends: ["epic-context"]
              gate: human

            - id: implement
              skill: "speckit.implement"
              outputs: ["{epic}/tasks.md"]
              depends: ["specify"]
              gate: auto
    """)
    yaml_file = tmp_path / "pipeline.yaml"
    yaml_file.write_text(content)
    with patch("config.PIPELINE_YAML", yaml_file):
        yield yaml_file


@pytest.fixture()
def cyclic_yaml(tmp_path):
    content = textwrap.dedent("""\
        nodes:
          - id: a
            skill: "s:a"
            outputs: []
            depends: ["c"]
            gate: auto
          - id: b
            skill: "s:b"
            outputs: []
            depends: ["a"]
            gate: auto
          - id: c
            skill: "s:c"
            outputs: []
            depends: ["b"]
            gate: auto
    """)
    f = tmp_path / "pipeline.yaml"
    f.write_text(content)
    with patch("config.PIPELINE_YAML", f):
        yield f


# ── Parse DAG Tests ──────────────────────────────────────────────────


class TestParseDag:
    def test_parse_l1_nodes(self, platform_yaml):
        nodes = parse_dag(mode="l1")
        assert len(nodes) == 3
        assert nodes[0].id == "alpha"
        assert nodes[1].depends == ["alpha"]
        assert nodes[2].depends == ["alpha", "beta"]

    def test_parse_l2_nodes(self, platform_yaml):
        nodes = parse_dag(mode="l2", epic="013-test")
        assert len(nodes) == 3
        assert nodes[0].id == "epic-context"
        assert nodes[2].outputs == ["epics/013-test/tasks.md"]

    def test_epic_template_resolution(self, platform_yaml):
        nodes = parse_dag(mode="l2", epic="my-epic")
        assert nodes[0].outputs == ["epics/my-epic/context.md"]

    def test_missing_pipeline_section(self, tmp_path):
        f = tmp_path / "pipeline.yaml"
        f.write_text("epic_cycle: {}\n")
        with patch("config.PIPELINE_YAML", f):
            with pytest.raises(SystemExit, match="No nodes"):
                parse_dag(mode="l1")

    def test_missing_epic_cycle(self, tmp_path):
        f = tmp_path / "pipeline.yaml"
        f.write_text("nodes:\n  - id: a\n    skill: s\n    depends: []\n    gate: auto\n")
        with patch("config.PIPELINE_YAML", f):
            with pytest.raises(SystemExit, match="No epic_cycle"):
                parse_dag(mode="l2")


# ── Topological Sort Tests ───────────────────────────────────────────


class TestTopologicalSort:
    def test_correct_order(self, platform_yaml):
        nodes = parse_dag(mode="l1")
        ordered = topological_sort(nodes)
        ids = [n.id for n in ordered]
        assert ids.index("alpha") < ids.index("beta")
        assert ids.index("beta") < ids.index("gamma")

    def test_cycle_detection(self, cyclic_yaml):
        nodes = parse_dag(mode="l1")
        with pytest.raises(SystemExit, match="Cycle detected"):
            topological_sort(nodes)

    def test_unknown_dependency(self):
        nodes = [Node("a", "s", [], ["nonexistent"], "auto", "", False, None)]
        with pytest.raises(SystemExit, match="Unknown dependency"):
            topological_sort(nodes)

    def test_single_node(self):
        nodes = [Node("only", "s", [], [], "auto", "", False, None)]
        ordered = topological_sort(nodes)
        assert len(ordered) == 1
        assert ordered[0].id == "only"

    def test_independent_nodes(self):
        nodes = [
            Node("a", "s", [], [], "auto", "", False, None),
            Node("b", "s", [], [], "auto", "", False, None),
            Node("c", "s", [], [], "auto", "", False, None),
        ]
        ordered = topological_sort(nodes)
        assert len(ordered) == 3


# ── Circuit Breaker Tests ────────────────────────────────────────────


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(max_failures=3, recovery_seconds=10)
        assert cb.state == "closed"
        assert cb.check() is True

    def test_opens_after_max_failures(self):
        cb = CircuitBreaker(max_failures=3, recovery_seconds=10)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.check() is False

    def test_half_open_after_recovery(self):
        cb = CircuitBreaker(max_failures=2, recovery_seconds=0)  # instant recovery
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"
        # With recovery=0, should immediately transition to half-open
        assert cb.check() is True
        assert cb.state == "half-open"

    def test_closes_after_success_in_half_open(self):
        cb = CircuitBreaker(max_failures=1, recovery_seconds=0)
        cb.record_failure()
        assert cb.state == "open"
        cb.check()  # transitions to half-open
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_reopens_on_half_open_failure(self):
        cb = CircuitBreaker(max_failures=1, recovery_seconds=0)
        cb.record_failure()
        cb.check()  # half-open
        cb.record_failure()
        assert cb.state == "open"

    def test_success_resets_count(self):
        cb = CircuitBreaker(max_failures=5)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == "closed"


# ── Dispatch Tests ───────────────────────────────────────────────────


class TestDispatchNode:
    def _make_node(self, node_id="test"):
        return Node(node_id, "madruga:test", ["out.md"], [], "auto", "", False, None)

    @patch("dag_executor.shutil.which", return_value="/usr/bin/claude")
    @patch("dag_executor.subprocess.run")
    def test_success(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0)
        ok, err, _stdout = dispatch_node(self._make_node(), Path("/tmp"), "prompt")
        assert ok is True
        assert err is None
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "--output-format" in cmd
        assert "json" in cmd

    @patch("dag_executor.shutil.which", return_value="/usr/bin/claude")
    @patch("dag_executor.subprocess.run")
    def test_failure(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=1, stderr="error msg")
        ok, err, _stdout = dispatch_node(self._make_node(), Path("/tmp"), "prompt")
        assert ok is False
        assert "error msg" in err

    @patch("dag_executor.shutil.which", return_value="/usr/bin/claude")
    @patch("dag_executor.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 60))
    def test_timeout(self, mock_run, mock_which):

        ok, err, _stdout = dispatch_node(self._make_node(), Path("/tmp"), "prompt", timeout=60)
        assert ok is False
        assert "timeout" in err

    @patch("dag_executor.shutil.which", return_value=None)
    def test_claude_not_found(self, mock_which):
        ok, err, _stdout = dispatch_node(self._make_node(), Path("/tmp"), "prompt")
        assert ok is False
        assert "claude CLI not found" in err


# ── Verify Outputs Tests ─────────────────────────────────────────────


class TestVerifyOutputs:
    def test_outputs_exist(self, tmp_path):
        (tmp_path / "out.md").write_text("content")
        node = Node("n", "s", ["out.md"], [], "auto", "", False, None)
        ok, err = verify_outputs(node, tmp_path)
        assert ok is True

    def test_output_missing(self, tmp_path):
        node = Node("n", "s", ["missing.md"], [], "auto", "", False, None)
        ok, err = verify_outputs(node, tmp_path)
        assert ok is False
        assert "output not found" in err

    def test_glob_pattern_skipped(self, tmp_path):
        node = Node("n", "s", ["epics/*/pitch.md"], [], "auto", "", False, None)
        ok, err = verify_outputs(node, tmp_path)
        assert ok is True  # globs are skipped


# ── Dispatch With Retry Tests ────────────────────────────────────────


class TestDispatchWithRetry:
    def _make_node(self):
        return Node("retry-test", "s", [], [], "auto", "", False, None)

    @patch("dag_executor.time.sleep")
    @patch("dag_executor.dispatch_node")
    def test_succeeds_first_try(self, mock_dispatch, mock_sleep):
        mock_dispatch.return_value = (True, None, "stdout")
        cb = CircuitBreaker()
        ok, err, _stdout = dispatch_with_retry(self._make_node(), Path("/tmp"), "p", 60, cb)
        assert ok is True
        assert mock_dispatch.call_count == 1
        mock_sleep.assert_not_called()

    @patch("dag_executor.time.sleep")
    @patch("dag_executor.dispatch_node")
    def test_succeeds_on_retry(self, mock_dispatch, mock_sleep):
        mock_dispatch.side_effect = [(False, "err1", None), (False, "err2", None), (True, None, "stdout")]
        cb = CircuitBreaker()
        ok, err, _stdout = dispatch_with_retry(self._make_node(), Path("/tmp"), "p", 60, cb)
        assert ok is True
        assert mock_dispatch.call_count == 3

    @patch("dag_executor.time.sleep")
    @patch("dag_executor.dispatch_node")
    def test_fails_after_all_retries(self, mock_dispatch, mock_sleep):
        mock_dispatch.return_value = (False, "persistent error", None)
        cb = CircuitBreaker()
        ok, err, _stdout = dispatch_with_retry(self._make_node(), Path("/tmp"), "p", 60, cb)
        assert ok is False
        assert err == "persistent error"
        assert mock_dispatch.call_count == 4  # 1 initial + 3 retries

    def test_circuit_breaker_blocks(self):
        cb = CircuitBreaker(max_failures=1, recovery_seconds=9999)
        cb.record_failure()
        assert cb.state == "open"
        ok, err, _stdout = dispatch_with_retry(self._make_node(), Path("/tmp"), "p", 60, cb)
        assert ok is False
        assert "circuit breaker" in err


# ── Compose Skill Prompt Tests ───────────────────────────────────────


class TestComposeSkillPrompt:
    def _make_node(self, skill="madruga:vision", depends=None):
        return Node("test", skill, [], depends or [], "auto", "", False, None)

    def test_l1_prompt(self, tmp_path):
        node = self._make_node(skill="madruga:vision")
        prompt, _guardrail = compose_skill_prompt("test-plat", node, tmp_path)
        assert "test-plat" in prompt
        assert "skill instructions" in prompt.lower() or "platform" in prompt.lower()

    def test_l2_speckit_specify(self, tmp_path):
        epic_dir = tmp_path / "epics" / "013-test"
        epic_dir.mkdir(parents=True)
        (epic_dir / "context.md").write_text("# Context")
        (epic_dir / "pitch.md").write_text("# Pitch")
        node = self._make_node(skill="speckit.specify")
        prompt, _guardrail = compose_skill_prompt("test-plat", node, tmp_path, epic_slug="013-test")
        assert "013-test" in prompt
        assert "# Pitch" in prompt

    @patch("implement_remote.compose_prompt", return_value="mock prompt")
    def test_l2_speckit_implement_delegates(self, mock_compose, tmp_path):
        node = self._make_node(skill="speckit.implement")
        prompt, _guardrail = compose_skill_prompt("test-plat", node, tmp_path, epic_slug="013")
        assert prompt is not None
        mock_compose.assert_called_once_with("test-plat", "013")

    def test_l1_with_dependency_context(self, tmp_path):
        (tmp_path / "business").mkdir()
        (tmp_path / "business" / "alpha.md").write_text("# Alpha content")
        node = self._make_node(skill="madruga:beta", depends=["alpha"])
        prompt, _guardrail = compose_skill_prompt("test-plat", node, tmp_path)
        assert "test-plat" in prompt


# ── Dry Run Integration Test ─────────────────────────────────────────


class TestDryRun:
    def test_l1_dry_run(self, platform_yaml, capsys):
        from dag_executor import run_pipeline

        repo_root = platform_yaml.parent
        with patch("dag_executor.REPO_ROOT", repo_root):
            # Create platforms/test-plat/platform.yaml (metadata only)
            plat_dir = repo_root / "platforms" / "test-plat"
            plat_dir.mkdir(parents=True)
            (plat_dir / "platform.yaml").write_text("name: test-plat\ntitle: Test\nlifecycle: design\n")

            result = run_pipeline("test-plat", dry_run=True)

        assert result == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "alpha" in captured.out
        assert "beta" in captured.out
        assert "gamma" in captured.out

    def test_l2_dry_run(self, platform_yaml, capsys):
        from dag_executor import run_pipeline

        repo_root = platform_yaml.parent
        with patch("dag_executor.REPO_ROOT", repo_root):
            plat_dir = repo_root / "platforms" / "test-plat"
            plat_dir.mkdir(parents=True, exist_ok=True)
            (plat_dir / "platform.yaml").write_text("name: test-plat\ntitle: Test\nlifecycle: design\n")

            result = run_pipeline("test-plat", epic_slug="013-test", dry_run=True)

        assert result == 0
        captured = capsys.readouterr()
        assert "L2" in captured.out
        assert "epic-context" in captured.out
        assert "specify" in captured.out
        assert "implement" in captured.out
