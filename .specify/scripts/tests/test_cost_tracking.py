"""Tests for cost tracking: parse_claude_output() and complete_run() metrics.

Tasks T003+T004 — Epic 021: Pipeline Intelligence (US1: Cost Tracking).
Real JSON fixtures from research.md (claude -p --output-format json, v2.1.90).
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from dag_executor import _estimate_cost_usd, parse_claude_output
from db_pipeline import complete_run, insert_run, upsert_platform

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
        "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
        "service_tier": "standard",
        "cache_creation": {
            "ephemeral_1h_input_tokens": 16210,
            "ephemeral_5m_input_tokens": 0,
        },
        "inference_geo": "",
        "iterations": [],
        "speed": "standard",
    },
    "modelUsage": {
        "claude-opus-4-6[1m]": {
            "inputTokens": 6,
            "outputTokens": 41,
            "cacheReadInputTokens": 38899,
            "cacheCreationInputTokens": 16210,
            "webSearchRequests": 0,
            "costUSD": 0.12181700000000001,
            "contextWindow": 1000000,
            "maxOutputTokens": 64000,
        }
    },
    "permission_denials": [],
    "fast_mode_state": "off",
    "uuid": "2f6e492c-1eed-4da1-bf09-1a6e23bec33a",
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
        "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
        "service_tier": "standard",
        "cache_creation": {
            "ephemeral_1h_input_tokens": 18379,
            "ephemeral_5m_input_tokens": 0,
        },
        "inference_geo": "",
        "iterations": [],
        "speed": "standard",
    },
    "modelUsage": {
        "claude-opus-4-6[1m]": {
            "inputTokens": 7,
            "outputTokens": 353,
            "cacheReadInputTokens": 70145,
            "cacheCreationInputTokens": 18379,
            "webSearchRequests": 0,
            "costUSD": 0.15880125,
            "contextWindow": 1000000,
            "maxOutputTokens": 64000,
        }
    },
    "permission_denials": [],
    "fast_mode_state": "off",
    "uuid": "2c14996f-b117-4ec6-8ef9-c9593437c463",
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
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 25,
        "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
        "service_tier": "standard",
    },
    "modelUsage": {},
    "permission_denials": [],
    "fast_mode_state": "off",
    "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
}


# ---------------------------------------------------------------------------
# Tests: correct field extraction from real JSON
# ---------------------------------------------------------------------------


class TestParseClaudeOutputCorrectExtraction:
    """Verify parse_claude_output() extracts the right fields from real JSON."""

    def test_tokens_in_from_real_json_no_tools(self):
        result = parse_claude_output(json.dumps(REAL_JSON_NO_TOOLS))
        assert result["tokens_in"] == 6

    def test_tokens_out_from_real_json_no_tools(self):
        result = parse_claude_output(json.dumps(REAL_JSON_NO_TOOLS))
        assert result["tokens_out"] == 41

    def test_duration_ms_from_real_json_no_tools(self):
        result = parse_claude_output(json.dumps(REAL_JSON_NO_TOOLS))
        assert result["duration_ms"] == 12112

    def test_cost_usd_from_real_json_no_tools(self):
        """Cost field uses total_cost_usd from claude output.

        NOTE: current code reads data["cost_usd"] which is wrong —
        actual field is data["total_cost_usd"]. T005 will fix this.
        This test defines DESIRED behavior (will fail until T005).
        """
        result = parse_claude_output(json.dumps(REAL_JSON_NO_TOOLS))
        assert result["cost_usd"] == pytest.approx(0.12181700000000001)

    def test_tokens_in_from_real_json_with_tools(self):
        result = parse_claude_output(json.dumps(REAL_JSON_WITH_TOOLS))
        assert result["tokens_in"] == 7

    def test_tokens_out_from_real_json_with_tools(self):
        result = parse_claude_output(json.dumps(REAL_JSON_WITH_TOOLS))
        assert result["tokens_out"] == 353

    def test_duration_ms_from_real_json_with_tools(self):
        result = parse_claude_output(json.dumps(REAL_JSON_WITH_TOOLS))
        assert result["duration_ms"] == 41736

    def test_cost_usd_from_real_json_with_tools(self):
        """Same as no-tools case — total_cost_usd should be extracted."""
        result = parse_claude_output(json.dumps(REAL_JSON_WITH_TOOLS))
        assert result["cost_usd"] == pytest.approx(0.15880125)

    def test_extracts_metrics_from_error_run(self):
        """Even errored runs should have metrics extracted (cost tracking)."""
        result = parse_claude_output(json.dumps(REAL_JSON_ERROR))
        assert result["tokens_in"] == 10
        assert result["tokens_out"] == 25
        assert result["duration_ms"] == 8500
        assert result["cost_usd"] == pytest.approx(0.045)

    def test_return_dict_has_exactly_four_keys(self):
        result = parse_claude_output(json.dumps(REAL_JSON_NO_TOOLS))
        assert set(result.keys()) == {"tokens_in", "tokens_out", "cost_usd", "duration_ms"}


# ---------------------------------------------------------------------------
# Tests: missing fields
# ---------------------------------------------------------------------------


class TestParseClaudeOutputMissingFields:
    """Verify graceful handling when expected fields are absent."""

    def test_missing_usage_block(self):
        """JSON without 'usage' key — tokens should be None."""
        data = {"total_cost_usd": 0.05, "duration_ms": 1000}
        result = parse_claude_output(json.dumps(data))
        assert result["tokens_in"] is None
        assert result["tokens_out"] is None
        assert result["cost_usd"] == pytest.approx(0.05)
        assert result["duration_ms"] == 1000

    def test_empty_usage_block(self):
        """usage exists but is empty dict."""
        data = {"usage": {}, "total_cost_usd": 0.01, "duration_ms": 500}
        result = parse_claude_output(json.dumps(data))
        assert result["tokens_in"] is None
        assert result["tokens_out"] is None
        assert result["cost_usd"] == pytest.approx(0.01)
        assert result["duration_ms"] == 500

    def test_missing_cost_and_duration(self):
        """JSON with usage but no cost or duration — fallback estimates cost."""
        data = {"usage": {"input_tokens": 100, "output_tokens": 50}}
        result = parse_claude_output(json.dumps(data))
        assert result["tokens_in"] == 100
        assert result["tokens_out"] == 50
        # Fallback: 100 * 0.003/1000 + 50 * 0.015/1000 = 0.0003 + 0.00075 = 0.00105
        assert result["cost_usd"] == pytest.approx(0.00105)
        assert result["duration_ms"] is None

    def test_missing_input_tokens_only(self):
        data = {"usage": {"output_tokens": 50}, "total_cost_usd": 0.01, "duration_ms": 100}
        result = parse_claude_output(json.dumps(data))
        assert result["tokens_in"] is None
        assert result["tokens_out"] == 50

    def test_missing_output_tokens_only(self):
        data = {"usage": {"input_tokens": 100}, "total_cost_usd": 0.01, "duration_ms": 100}
        result = parse_claude_output(json.dumps(data))
        assert result["tokens_in"] == 100
        assert result["tokens_out"] is None

    def test_completely_empty_json_object(self):
        """Empty JSON object — all fields None."""
        result = parse_claude_output("{}")
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    def test_usage_is_none(self):
        """usage key present but value is None (not dict)."""
        data = {"usage": None, "total_cost_usd": 0.01}
        result = parse_claude_output(json.dumps(data))
        # usage.get() will fail on None — should be handled gracefully
        assert result["tokens_in"] is None
        assert result["tokens_out"] is None


# ---------------------------------------------------------------------------
# Tests: malformed JSON
# ---------------------------------------------------------------------------


class TestParseClaudeOutputMalformedJson:
    """Verify graceful handling of invalid JSON input."""

    def test_invalid_json_string(self):
        result = parse_claude_output("{not valid json}")
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    def test_truncated_json(self):
        """JSON cut off mid-stream (e.g., process killed)."""
        truncated = json.dumps(REAL_JSON_NO_TOOLS)[:50]
        result = parse_claude_output(truncated)
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    def test_json_array_instead_of_object(self):
        """JSON is a valid array, not an object."""
        result = parse_claude_output("[1, 2, 3]")
        # list has no .get() — should be caught by AttributeError
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    def test_json_string_literal(self):
        """JSON is a plain string, not an object."""
        result = parse_claude_output('"just a string"')
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    def test_json_number_literal(self):
        result = parse_claude_output("42")
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    def test_plain_text_output(self):
        """Non-JSON text (e.g., raw assistant response without --output-format json)."""
        result = parse_claude_output("Hello! I'm Claude, ready to help.")
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    def test_json_with_extra_text_before(self):
        """Stray text before JSON (e.g., logging prefix)."""
        result = parse_claude_output("INFO: " + json.dumps(REAL_JSON_NO_TOOLS))
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}


# ---------------------------------------------------------------------------
# Tests: empty / None input
# ---------------------------------------------------------------------------


class TestParseClaudeOutputEmptyInput:
    """Verify handling of empty and None inputs."""

    def test_empty_string(self):
        result = parse_claude_output("")
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    def test_whitespace_only(self):
        result = parse_claude_output("   \n\t  ")
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    def test_none_input(self):
        """None should not crash — return defaults."""
        result = parse_claude_output(None)
        assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}


# ---------------------------------------------------------------------------
# Tests: complete_run() persists metric columns (T004)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_with_platform(tmp_db):
    """tmp_db with a platform row so insert_run FK is satisfied."""
    upsert_platform(tmp_db, "test-plat", name="test-plat", repo_path="platforms/test-plat")
    return tmp_db


class TestCompleteRunMetrics:
    """Verify complete_run() UPDATE includes metric columns in pipeline_runs."""

    def test_all_metrics_persisted(self, db_with_platform):
        """All 4 metric fields written by complete_run() are readable back."""
        run_id = insert_run(db_with_platform, "test-plat", "vision")
        complete_run(
            db_with_platform,
            run_id,
            "completed",
            tokens_in=600,
            tokens_out=150,
            cost_usd=0.042,
            duration_ms=8500,
        )
        row = db_with_platform.execute(
            "SELECT tokens_in, tokens_out, cost_usd, duration_ms, status FROM pipeline_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        assert row["tokens_in"] == 600
        assert row["tokens_out"] == 150
        assert row["cost_usd"] == pytest.approx(0.042)
        assert row["duration_ms"] == 8500
        assert row["status"] == "completed"

    def test_partial_metrics_leaves_others_null(self, db_with_platform):
        """Passing only tokens_in leaves tokens_out/cost_usd/duration_ms NULL."""
        run_id = insert_run(db_with_platform, "test-plat", "vision")
        complete_run(db_with_platform, run_id, "completed", tokens_in=100)
        row = db_with_platform.execute(
            "SELECT tokens_in, tokens_out, cost_usd, duration_ms FROM pipeline_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        assert row["tokens_in"] == 100
        assert row["tokens_out"] is None
        assert row["cost_usd"] is None
        assert row["duration_ms"] is None

    def test_no_metrics_only_updates_status(self, db_with_platform):
        """complete_run() with no metric kwargs still updates status + completed_at."""
        run_id = insert_run(db_with_platform, "test-plat", "vision")
        complete_run(db_with_platform, run_id, "completed")
        row = db_with_platform.execute(
            "SELECT status, completed_at, tokens_in, tokens_out, cost_usd, duration_ms "
            "FROM pipeline_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        assert row["status"] == "completed"
        assert row["completed_at"] is not None
        assert row["tokens_in"] is None
        assert row["tokens_out"] is None
        assert row["cost_usd"] is None
        assert row["duration_ms"] is None

    def test_error_status_with_metrics(self, db_with_platform):
        """Failed runs still persist metrics (we want cost tracking even on errors)."""
        run_id = insert_run(db_with_platform, "test-plat", "vision")
        complete_run(
            db_with_platform,
            run_id,
            "failed",
            tokens_in=10,
            tokens_out=25,
            cost_usd=0.045,
            duration_ms=8500,
            error="Reached maximum number of turns (1)",
        )
        row = db_with_platform.execute(
            "SELECT status, tokens_in, tokens_out, cost_usd, duration_ms, error FROM pipeline_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        assert row["status"] == "failed"
        assert row["tokens_in"] == 10
        assert row["cost_usd"] == pytest.approx(0.045)
        assert row["error"] == "Reached maximum number of turns (1)"

    def test_ignores_unknown_kwargs(self, db_with_platform):
        """Fields not in _COMPLETE_RUN_FIELDS are silently ignored."""
        run_id = insert_run(db_with_platform, "test-plat", "vision")
        complete_run(
            db_with_platform,
            run_id,
            "completed",
            tokens_in=50,
            bogus_field="should be ignored",
            another_unknown=999,
        )
        row = db_with_platform.execute(
            "SELECT tokens_in FROM pipeline_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        assert row["tokens_in"] == 50

    def test_metrics_overwrite_on_second_complete(self, db_with_platform):
        """Calling complete_run() twice overwrites metric values."""
        run_id = insert_run(db_with_platform, "test-plat", "vision")
        complete_run(db_with_platform, run_id, "completed", tokens_in=100, cost_usd=0.01)
        complete_run(db_with_platform, run_id, "completed", tokens_in=200, cost_usd=0.02)
        row = db_with_platform.execute(
            "SELECT tokens_in, cost_usd FROM pipeline_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        assert row["tokens_in"] == 200
        assert row["cost_usd"] == pytest.approx(0.02)

    def test_output_lines_persisted(self, db_with_platform):
        """output_lines is also in _COMPLETE_RUN_FIELDS and should persist."""
        run_id = insert_run(db_with_platform, "test-plat", "vision")
        complete_run(db_with_platform, run_id, "completed", output_lines=42)
        row = db_with_platform.execute(
            "SELECT output_lines FROM pipeline_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        assert row["output_lines"] == 42


# ---------------------------------------------------------------------------
# Tests: cost fallback estimation (T006)
# ---------------------------------------------------------------------------


class TestEstimateCostUsd:
    """Verify _estimate_cost_usd() fallback when total_cost_usd is absent."""

    def test_both_tokens_present(self):
        # 1000 in * 0.003/1000 + 500 out * 0.015/1000 = 0.003 + 0.0075 = 0.0105
        assert _estimate_cost_usd(1000, 500) == pytest.approx(0.0105)

    def test_only_input_tokens(self):
        assert _estimate_cost_usd(1000, None) == pytest.approx(0.003)

    def test_only_output_tokens(self):
        assert _estimate_cost_usd(None, 500) == pytest.approx(0.0075)

    def test_zero_tokens(self):
        assert _estimate_cost_usd(0, 0) == pytest.approx(0.0)

    def test_both_none_returns_none(self):
        assert _estimate_cost_usd(None, None) is None


class TestParseClaudeOutputCostFallback:
    """Verify parse_claude_output() uses fallback when total_cost_usd is missing."""

    def test_fallback_when_cost_missing_but_tokens_present(self):
        data = {"usage": {"input_tokens": 1000, "output_tokens": 500}, "duration_ms": 100}
        result = parse_claude_output(json.dumps(data))
        assert result["cost_usd"] == pytest.approx(0.0105)

    def test_no_fallback_when_cost_present(self):
        """total_cost_usd takes precedence — no fallback."""
        data = {
            "usage": {"input_tokens": 1000, "output_tokens": 500},
            "total_cost_usd": 0.99,
            "duration_ms": 100,
        }
        result = parse_claude_output(json.dumps(data))
        assert result["cost_usd"] == pytest.approx(0.99)

    def test_no_fallback_when_no_tokens_and_no_cost(self):
        """No tokens, no cost — cost_usd stays None."""
        data = {"duration_ms": 100}
        result = parse_claude_output(json.dumps(data))
        assert result["cost_usd"] is None
