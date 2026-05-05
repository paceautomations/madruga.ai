"""Integration test for retry policy + failed-status materialisation.

Source task: T062 (epic 027-screen-flow-canvas Phase 6 / US4).

Covers FR-045 + FR-046:
- 3 retries with exponential backoff 1s/2s/4s on transient failure
- After exhaustion → status: failed + failure block (reason, occurred_at,
  retry_count, last_error_message)
- Workflow exits 1 when ANY screen failed; YAML is committed regardless
- Auth-expired is treated as fatal at the orchestrator boundary (validate_env)
- Backoff sequence walks the documented values exactly (no jitter, no rounding)
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "capture"))

import screen_capture as sc  # noqa: E402


def _failing_runner(reason: str = "timeout", error: str = "Timeout 30000ms exceeded"):
    def runner() -> dict[str, Any]:
        return {"success": False, "reason": reason, "error": error}

    return runner


def _flaky_runner(success_after: int, reason: str = "network_error"):
    """Fail ``success_after`` times then succeed."""
    state = {"calls": 0}

    def runner() -> dict[str, Any]:
        state["calls"] += 1
        if state["calls"] <= success_after:
            return {"success": False, "reason": reason, "error": "transient"}
        return {
            "success": True,
            "image_path": Path("/tmp/img.png"),
            "image_md5": "0" * 32,
            "viewport": {"w": 393, "h": 852},
        }

    return runner, state


# ───────────────────────────────────────────────────────────────────────────────
# Backoff sequence
# ───────────────────────────────────────────────────────────────────────────────


def test_backoff_walks_exactly_1_2_4_seconds_on_full_failure():
    sleeps: list[float] = []
    result = sc.capture_with_retries(
        "screen_a",
        _failing_runner(),
        sleep=sleeps.append,
    )
    # 4 attempts (1 initial + 3 retries) → 3 sleeps between retries
    assert sleeps == [1.0, 2.0, 4.0]
    assert result.status == "failed"
    assert result.retry_count == 3


def test_succeeds_on_second_attempt_only_one_sleep():
    runner, state = _flaky_runner(success_after=1)
    sleeps: list[float] = []
    result = sc.capture_with_retries(
        "x", runner, sleep=sleeps.append,
    )
    assert state["calls"] == 2
    assert sleeps == [1.0]
    assert result.status == "captured"
    assert result.retry_count == 1


def test_succeeds_on_third_attempt_two_sleeps():
    runner, state = _flaky_runner(success_after=2)
    sleeps: list[float] = []
    result = sc.capture_with_retries(
        "x", runner, sleep=sleeps.append,
    )
    assert state["calls"] == 3
    assert sleeps == [1.0, 2.0]
    assert result.status == "captured"


def test_succeeds_on_fourth_attempt_uses_full_backoff():
    runner, state = _flaky_runner(success_after=3)
    sleeps: list[float] = []
    result = sc.capture_with_retries(
        "x", runner, sleep=sleeps.append,
    )
    assert state["calls"] == 4
    assert sleeps == [1.0, 2.0, 4.0]
    assert result.status == "captured"
    assert result.retry_count == 3


# ───────────────────────────────────────────────────────────────────────────────
# Failure record materialisation
# ───────────────────────────────────────────────────────────────────────────────


def test_failure_record_has_required_fields(tmp_path: Path):
    """FR-046 — the YAML failure block carries reason, retry_count, error msg."""
    doc = {
        "schema_version": 1,
        "meta": {"device": "mobile", "capture_profile": "iphone-15"},
        "screens": [
            {
                "id": "broken",
                "title": "Broken",
                "status": "pending",
                "body": [{"type": "heading", "text": "x"}],
            }
        ],
        "flows": [],
    }
    result = sc.capture_with_retries(
        "broken", _failing_runner(reason="timeout", error="Timeout 30s exceeded"),
        sleep=lambda _s: None,
    )

    sc.apply_capture_result(doc, result, app_version="abc1234")

    screen = doc["screens"][0]
    assert screen["status"] == "failed"
    failure = screen["failure"]
    assert failure["reason"] == "timeout"
    assert failure["retry_count"] == 3
    assert "Timeout 30s exceeded" in failure["last_error_message"]
    # ISO 8601 occurrred_at
    datetime.fromisoformat(failure["occurred_at"].rstrip("Z"))


def test_unknown_reason_is_normalised():
    """Reasons outside the closed enum collapse to 'unknown' (data-model E11)."""
    result = sc.capture_with_retries(
        "x",
        lambda: {"success": False, "reason": "make_coffee", "error": ""},
        sleep=lambda _s: None,
    )
    assert result.status == "failed"
    assert result.reason == "unknown"


def test_runner_raising_exception_is_caught_and_retried():
    """Any exception is treated as a transient runner crash."""
    state = {"calls": 0}

    def runner():
        state["calls"] += 1
        if state["calls"] < 4:
            raise RuntimeError("kaboom")
        return {
            "success": True,
            "image_path": Path("/tmp/x.png"),
            "image_md5": "0" * 32,
            "viewport": {"w": 1, "h": 1},
        }

    result = sc.capture_with_retries("x", runner, sleep=lambda _s: None)
    assert state["calls"] == 4
    assert result.status == "captured"


def test_workflow_exits_one_when_any_screen_failed():
    a = sc.capture_with_retries(
        "a", _failing_runner(), sleep=lambda _s: None,
    )
    b = sc.capture_with_retries(
        "b",
        lambda: {
            "success": True, "image_path": Path("/tmp/b.png"),
            "image_md5": "0" * 32, "viewport": {"w": 1, "h": 1},
        },
        sleep=lambda _s: None,
    )
    assert sc.compute_workflow_exit_code([a, b]) == 1


def test_workflow_exits_zero_when_all_screens_captured():
    runs = [
        sc.capture_with_retries(
            f"s{i}",
            lambda i=i: {
                "success": True, "image_path": Path(f"/tmp/{i}.png"),
                "image_md5": "0" * 32, "viewport": {"w": 1, "h": 1},
            },
            sleep=lambda _s: None,
        )
        for i in range(3)
    ]
    assert sc.compute_workflow_exit_code(runs) == 0


# ───────────────────────────────────────────────────────────────────────────────
# Last error message truncation (data-model E11 — max 500 chars)
# ───────────────────────────────────────────────────────────────────────────────


def test_last_error_message_truncated_to_500_chars(tmp_path: Path):
    huge = "x" * 5000
    result = sc.capture_with_retries(
        "x", _failing_runner(error=huge), sleep=lambda _s: None,
    )
    doc = {
        "schema_version": 1,
        "meta": {"device": "mobile", "capture_profile": "iphone-15"},
        "screens": [
            {"id": "x", "title": "x", "status": "pending",
             "body": [{"type": "heading", "text": "h"}]},
        ],
        "flows": [],
    }
    sc.apply_capture_result(doc, result, app_version="abc1234")
    msg = doc["screens"][0]["failure"]["last_error_message"]
    assert len(msg) == 500


# ───────────────────────────────────────────────────────────────────────────────
# Total YAML still gets written (FR-046)
# ───────────────────────────────────────────────────────────────────────────────


def test_yaml_persisted_with_mixed_results(tmp_path: Path):
    yaml_path = tmp_path / "screen-flow.yaml"
    doc = {
        "schema_version": 1,
        "meta": {"device": "mobile", "capture_profile": "iphone-15"},
        "screens": [
            {"id": "ok", "title": "OK", "status": "pending",
             "body": [{"type": "heading", "text": "h"}]},
            {"id": "ko", "title": "KO", "status": "pending",
             "body": [{"type": "heading", "text": "h"}]},
        ],
        "flows": [],
    }
    sc.save_screen_flow(yaml_path, doc)

    ok = sc.capture_with_retries(
        "ok",
        lambda: {
            "success": True, "image_path": tmp_path / "ok.png",
            "image_md5": "f" * 32, "viewport": {"w": 393, "h": 852},
        },
        sleep=lambda _s: None,
    )
    (tmp_path / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\nokok")
    ko = sc.capture_with_retries(
        "ko", _failing_runner(reason="auth_expired"),
        sleep=lambda _s: None,
    )
    sc.apply_capture_result(doc, ok, app_version="abc1234")
    sc.apply_capture_result(doc, ko, app_version="abc1234")
    sc.save_screen_flow(yaml_path, doc)

    reloaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in reloaded["screens"]}
    assert by_id["ok"]["status"] == "captured"
    assert by_id["ko"]["status"] == "failed"
    assert by_id["ko"]["failure"]["reason"] == "auth_expired"
