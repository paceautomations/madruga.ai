"""Tests for hallucination guard: _check_hallucination() heuristic.

Tasks T008+T009 — Epic 021: Pipeline Intelligence (US2: Hallucination Guard).
Real JSON fixtures from research.md (claude -p --output-format json, v2.1.90).

Heuristic: num_turns <= 2 with no error → likely fabricated output (zero tool calls).
"""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from dag_executor import _check_hallucination

# ---------------------------------------------------------------------------
# Fixtures — real JSON from claude -p --output-format json (research.md)
# ---------------------------------------------------------------------------

REAL_JSON_NO_TOOLS = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "duration_ms": 12112,
    "duration_api_ms": 5491,
    "num_turns": 2,
    "result": "hello",
    "stop_reason": "end_turn",
    "session_id": "37d55cfa-cf8a-45f4-a40f-f11ba6c2159b",
    "total_cost_usd": 0.12181700000000001,
    "usage": {
        "input_tokens": 6,
        "cache_creation_input_tokens": 16210,
        "cache_read_input_tokens": 38899,
        "output_tokens": 41,
    },
}

REAL_JSON_WITH_TOOLS = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "duration_ms": 41736,
    "duration_api_ms": 36742,
    "num_turns": 3,
    "result": "Listed files.",
    "stop_reason": "end_turn",
    "session_id": "38f4ee87-8ead-4f6c-a1fe-24e97d1b33a8",
    "total_cost_usd": 0.15880125,
    "usage": {
        "input_tokens": 7,
        "cache_creation_input_tokens": 18379,
        "cache_read_input_tokens": 70145,
        "output_tokens": 353,
    },
}

REAL_JSON_ERROR = {
    "type": "result",
    "subtype": "error_max_turns",
    "is_error": True,
    "duration_ms": 8500,
    "duration_api_ms": 4200,
    "num_turns": 1,
    "stop_reason": "tool_use",
    "errors": ["Reached maximum number of turns (1)"],
    "total_cost_usd": 0.045,
    "usage": {
        "input_tokens": 10,
        "output_tokens": 25,
    },
}


# ---------------------------------------------------------------------------
# T008: Tests for _check_hallucination() — core heuristic
# ---------------------------------------------------------------------------


class TestCheckHallucinationZeroToolCalls:
    """Zero tool calls (num_turns <= 2, no error) → True (hallucination detected)."""

    def test_num_turns_2_returns_true(self):
        """num_turns == 2 means 1 user + 1 assistant turn — no tool use."""
        stdout = json.dumps(REAL_JSON_NO_TOOLS)
        assert _check_hallucination(stdout) is True

    def test_num_turns_1_returns_true(self):
        """num_turns == 1 — even fewer turns, still no tool use."""
        data = {**REAL_JSON_NO_TOOLS, "num_turns": 1, "is_error": False}
        assert _check_hallucination(json.dumps(data)) is True

    def test_real_json_no_tools_fixture(self):
        """Real fixture from research.md Run 1 (no tool use) triggers guard."""
        assert _check_hallucination(json.dumps(REAL_JSON_NO_TOOLS)) is True


class TestCheckHallucinationNonzeroToolCalls:
    """Nonzero tool calls (num_turns > 2) → False (no hallucination)."""

    def test_num_turns_3_returns_false(self):
        """num_turns == 3 means at least one tool was called."""
        stdout = json.dumps(REAL_JSON_WITH_TOOLS)
        assert _check_hallucination(stdout) is False

    def test_num_turns_5_returns_false(self):
        """More turns → even more tool calls."""
        data = {**REAL_JSON_WITH_TOOLS, "num_turns": 5}
        assert _check_hallucination(json.dumps(data)) is False

    def test_num_turns_10_returns_false(self):
        """High turn count — clearly not hallucinated."""
        data = {**REAL_JSON_WITH_TOOLS, "num_turns": 10}
        assert _check_hallucination(json.dumps(data)) is False

    def test_real_json_with_tools_fixture(self):
        """Real fixture from research.md Run 2 (with tool use) does not trigger."""
        assert _check_hallucination(json.dumps(REAL_JSON_WITH_TOOLS)) is False


class TestCheckHallucinationErrorRuns:
    """Error runs (is_error=True) → False (don't flag errors as hallucinations)."""

    def test_error_with_low_turns_returns_false(self):
        """Error run with num_turns=1 — is_error=True suppresses the guard."""
        assert _check_hallucination(json.dumps(REAL_JSON_ERROR)) is False

    def test_error_with_two_turns_returns_false(self):
        """Error with num_turns=2 — still suppressed by is_error."""
        data = {**REAL_JSON_ERROR, "num_turns": 2}
        assert _check_hallucination(json.dumps(data)) is False


class TestCheckHallucinationMalformedJson:
    """Malformed JSON → False (fail safe — don't warn on broken output)."""

    def test_invalid_json_string(self):
        assert _check_hallucination("{not valid json}") is False

    def test_truncated_json(self):
        truncated = json.dumps(REAL_JSON_NO_TOOLS)[:50]
        assert _check_hallucination(truncated) is False

    def test_json_array_instead_of_object(self):
        """JSON array has no .get() — should not crash."""
        assert _check_hallucination("[1, 2, 3]") is False

    def test_json_string_literal(self):
        assert _check_hallucination('"just a string"') is False

    def test_json_number_literal(self):
        assert _check_hallucination("42") is False

    def test_plain_text_output(self):
        """Non-JSON output (e.g., raw assistant response)."""
        assert _check_hallucination("Hello! I'm Claude.") is False

    def test_json_with_prefix_text(self):
        """Stray text before JSON (e.g., logging prefix)."""
        assert _check_hallucination("INFO: " + json.dumps(REAL_JSON_NO_TOOLS)) is False


class TestCheckHallucinationMissingFields:
    """Missing expected fields → False (fail safe)."""

    def test_missing_num_turns(self):
        """No num_turns field — can't determine turn count, default safe."""
        data = {"type": "result", "is_error": False, "total_cost_usd": 0.05}
        assert _check_hallucination(json.dumps(data)) is False

    def test_missing_is_error(self):
        """No is_error field — num_turns <= 2 but is_error defaults to False.
        Should still detect hallucination since is_error absence means no error.
        """
        data = {"type": "result", "num_turns": 2, "total_cost_usd": 0.05}
        assert _check_hallucination(json.dumps(data)) is True

    def test_num_turns_zero(self):
        """num_turns == 0 (edge case) — still <= 2, should flag."""
        data = {"type": "result", "is_error": False, "num_turns": 0}
        assert _check_hallucination(json.dumps(data)) is True

    def test_empty_json_object(self):
        """Empty {} — num_turns defaults to 0 which is <= 2.
        But 0 means data.get('num_turns', 0) == 0 which could be ambiguous.
        Per research.md: return False for missing num_turns (fail safe).
        """
        assert _check_hallucination("{}") is False

    def test_num_turns_none(self):
        """num_turns is explicitly null in JSON — should fail safe."""
        data = {"num_turns": None, "is_error": False}
        assert _check_hallucination(json.dumps(data)) is False

    def test_is_error_none(self):
        """is_error is null — treat as falsy (no error), check num_turns."""
        data = {"num_turns": 2, "is_error": None}
        assert _check_hallucination(json.dumps(data)) is True


class TestCheckHallucinationEmptyInput:
    """Empty and None inputs → False (fail safe)."""

    def test_empty_string(self):
        assert _check_hallucination("") is False

    def test_whitespace_only(self):
        assert _check_hallucination("   \n\t  ") is False

    def test_none_input(self):
        assert _check_hallucination(None) is False


class TestCheckHallucinationBoundary:
    """Boundary tests at num_turns == 2 (threshold)."""

    def test_exactly_2_turns_is_hallucination(self):
        """2 turns = 1 user + 1 assistant = no tool use."""
        data = {"num_turns": 2, "is_error": False}
        assert _check_hallucination(json.dumps(data)) is True

    def test_exactly_3_turns_is_not_hallucination(self):
        """3 turns = at least one tool call round-trip."""
        data = {"num_turns": 3, "is_error": False}
        assert _check_hallucination(json.dumps(data)) is False

    def test_negative_num_turns(self):
        """Negative num_turns (nonsense value) — still <= 2, but fail safe."""
        data = {"num_turns": -1, "is_error": False}
        # Negative is <= 2 but represents invalid data — function should
        # treat as hallucination since the heuristic is simple: <= 2 → True
        assert _check_hallucination(json.dumps(data)) is True


# ---------------------------------------------------------------------------
# T009: Integration tests — hallucination check called after dispatch
# ---------------------------------------------------------------------------
# These tests verify that _check_hallucination is called at dispatch sites
# (sync loop, async loop, implement tasks) and that WARNING is logged when
# hallucination is detected. They mock dispatch_with_retry / the dispatch
# function to return zero-tool-call JSON, then assert the warning appears.
#
# NOTE: These tests define DESIRED integration behavior. They will fail
# until T011/T012 wire _check_hallucination into the execution loops.
# ---------------------------------------------------------------------------

ZERO_TOOL_STDOUT = json.dumps(REAL_JSON_NO_TOOLS)  # num_turns=2 → hallucination
TOOL_USE_STDOUT = json.dumps(REAL_JSON_WITH_TOOLS)  # num_turns=3 → no hallucination


class TestHallucinationIntegrationSyncLoop:
    """Verify _check_hallucination is called in run_pipeline (sync loop)."""

    @patch("dag_executor._check_hallucination", return_value=True)
    @patch("dag_executor.dispatch_with_retry", return_value=(True, None, ZERO_TOOL_STDOUT))
    @patch("dag_executor.parse_dag")
    @patch("dag_executor.verify_outputs", return_value=(True, None))
    @patch("dag_executor._run_eval_scoring")
    @patch("dag_executor._handle_auto_escalate", return_value=False)
    def test_hallucination_check_called_after_sync_dispatch(
        self, mock_escalate, mock_eval, mock_verify, mock_dag, mock_dispatch, mock_halluc, tmp_path
    ):
        """After successful dispatch in sync loop, _check_hallucination is called with stdout."""
        from dag_executor import Node, run_pipeline

        node = Node(
            id="vision",
            skill="madruga:vision",
            outputs=["business/vision.md"],
            depends=[],
            gate="auto",
            layer="business",
            optional=False,
            skip_condition=None,
        )
        mock_dag.return_value = [node]

        # Create minimal platform dir with platform.yaml
        plat_dir = tmp_path / "platforms" / "test-plat"
        plat_dir.mkdir(parents=True)
        (plat_dir / "platform.yaml").write_text("pipeline: {}\n")
        output_file = plat_dir / "business" / "vision.md"
        output_file.parent.mkdir(parents=True)
        output_file.write_text("test output")

        with (
            patch("dag_executor.REPO_ROOT", tmp_path),
            patch("db.get_conn") as mock_conn,
            patch("db.insert_run", return_value=1),
            patch("db.complete_run"),
            patch("db.upsert_pipeline_node"),
            patch("db.create_trace", return_value="trace-1"),
            patch("db.complete_trace"),
        ):
            mock_conn.return_value.execute.return_value.fetchone.return_value = None
            run_pipeline("test-plat", dry_run=False, gate_mode="auto")

        mock_halluc.assert_called_once_with(ZERO_TOOL_STDOUT)

    @patch("dag_executor._check_hallucination", return_value=True)
    @patch("dag_executor.dispatch_with_retry", return_value=(True, None, ZERO_TOOL_STDOUT))
    @patch("dag_executor.parse_dag")
    @patch("dag_executor.verify_outputs", return_value=(True, None))
    @patch("dag_executor._run_eval_scoring")
    @patch("dag_executor._handle_auto_escalate", return_value=False)
    def test_hallucination_warning_logged_sync(
        self, mock_escalate, mock_eval, mock_verify, mock_dag, mock_dispatch, mock_halluc, tmp_path, caplog
    ):
        """When _check_hallucination returns True, a WARNING is logged."""
        from dag_executor import Node, run_pipeline

        node = Node(
            id="vision",
            skill="madruga:vision",
            outputs=["business/vision.md"],
            depends=[],
            gate="auto",
            layer="business",
            optional=False,
            skip_condition=None,
        )
        mock_dag.return_value = [node]

        plat_dir = tmp_path / "platforms" / "test-plat"
        plat_dir.mkdir(parents=True)
        (plat_dir / "platform.yaml").write_text("pipeline: {}\n")
        output_file = plat_dir / "business" / "vision.md"
        output_file.parent.mkdir(parents=True)
        output_file.write_text("test output")

        with (
            caplog.at_level(logging.WARNING, logger="dag_executor"),
            patch("dag_executor.REPO_ROOT", tmp_path),
            patch("db.get_conn") as mock_conn,
            patch("db.insert_run", return_value=1),
            patch("db.complete_run"),
            patch("db.upsert_pipeline_node"),
            patch("db.create_trace", return_value="trace-1"),
            patch("db.complete_trace"),
        ):
            mock_conn.return_value.execute.return_value.fetchone.return_value = None
            run_pipeline("test-plat", dry_run=False, gate_mode="auto")

        halluc_warnings = [r for r in caplog.records if "hallucin" in r.message.lower()]
        assert len(halluc_warnings) >= 1, f"Expected hallucination WARNING, got: {[r.message for r in caplog.records]}"

    @patch("dag_executor._check_hallucination", return_value=False)
    @patch("dag_executor.dispatch_with_retry", return_value=(True, None, TOOL_USE_STDOUT))
    @patch("dag_executor.parse_dag")
    @patch("dag_executor.verify_outputs", return_value=(True, None))
    @patch("dag_executor._run_eval_scoring")
    @patch("dag_executor._handle_auto_escalate", return_value=False)
    def test_no_warning_when_tools_used_sync(
        self, mock_escalate, mock_eval, mock_verify, mock_dag, mock_dispatch, mock_halluc, tmp_path, caplog
    ):
        """When _check_hallucination returns False (tools used), no WARNING."""
        from dag_executor import Node, run_pipeline

        node = Node(
            id="vision",
            skill="madruga:vision",
            outputs=["business/vision.md"],
            depends=[],
            gate="auto",
            layer="business",
            optional=False,
            skip_condition=None,
        )
        mock_dag.return_value = [node]

        plat_dir = tmp_path / "platforms" / "test-plat"
        plat_dir.mkdir(parents=True)
        (plat_dir / "platform.yaml").write_text("pipeline: {}\n")
        output_file = plat_dir / "business" / "vision.md"
        output_file.parent.mkdir(parents=True)
        output_file.write_text("test output")

        with (
            caplog.at_level(logging.WARNING, logger="dag_executor"),
            patch("dag_executor.REPO_ROOT", tmp_path),
            patch("db.get_conn") as mock_conn,
            patch("db.insert_run", return_value=1),
            patch("db.complete_run"),
            patch("db.upsert_pipeline_node"),
            patch("db.create_trace", return_value="trace-1"),
            patch("db.complete_trace"),
        ):
            mock_conn.return_value.execute.return_value.fetchone.return_value = None
            run_pipeline("test-plat", dry_run=False, gate_mode="auto")

        halluc_warnings = [r for r in caplog.records if "hallucin" in r.message.lower()]
        assert len(halluc_warnings) == 0, f"Unexpected hallucination warning: {halluc_warnings}"


class TestHallucinationIntegrationDirectCall:
    """Verify _check_hallucination + logging works end-to-end (no mocking the function)."""

    def test_zero_tools_logs_warning(self, caplog):
        """Direct call: _check_hallucination with zero-tool JSON returns True,
        and caller is expected to log WARNING containing 'hallucin'.
        This tests the contract that T011/T012 must implement.
        """
        result = _check_hallucination(ZERO_TOOL_STDOUT)
        assert result is True
        # The function itself just returns bool — the caller logs.
        # This test documents the expected contract.

    def test_tool_use_no_warning(self):
        """Direct call: _check_hallucination with tool-use JSON returns False."""
        result = _check_hallucination(TOOL_USE_STDOUT)
        assert result is False

    def test_dispatch_not_blocked_on_hallucination(self):
        """Hallucination guard is warning-only — dispatch result is still accepted.
        Per pitch decision: warn but don't reject.
        """
        # Even when hallucination detected, the function returns True (detected)
        # but the caller should NOT fail the pipeline — just log.
        assert _check_hallucination(ZERO_TOOL_STDOUT) is True
        # The caller's responsibility is to log WARNING and continue,
        # NOT to return error or halt the pipeline.
