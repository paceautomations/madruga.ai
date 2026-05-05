"""Integration test for capture determinism (FR-033, SC-003).

Source task: T061 (epic 027-screen-flow-canvas Phase 6 / US4).

Strategy:
2 back-to-back runs against an injectable runner that mimics a stable HTTP
fixture must produce md5-identical PNGs in ≥80% of the screens. The runner is
deterministic by design (writes a content-hashed PNG payload); a small
configurable noise rate emulates the tail of non-deterministic screens caused
by uncovered animations or third-party widgets — at most 20% noise is allowed
(SC-003 threshold).

This is a pure-Python integration test: it does NOT spin up Playwright. The
contract for the runner used by the orchestrator is documented in
``screen_capture.capture_with_retries`` and the same shape is exercised here.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "capture"))

import screen_capture as sc  # noqa: E402


def _png_bytes(seed: bytes) -> bytes:
    """Build a deterministic PNG payload keyed by ``seed``.

    For the determinism test the actual pixels don't matter — only that the
    bytes (and therefore md5) collapse to a stable value across runs.
    """
    return b"\x89PNG\r\n\x1a\n" + seed + hashlib.sha256(seed).digest()


def _fake_runner_factory(
    screen_id: str,
    out_dir: Path,
    *,
    noise_per_run: dict[str, bytes] | None = None,
    run_idx: int = 0,
) -> Any:
    """Return a runner that writes a stable PNG for ``screen_id``.

    ``noise_per_run`` can inject a per-run salt for screens that should differ
    between runs — emulating non-deterministic widgets the determinism layer
    failed to neutralize.
    """

    def runner() -> dict[str, Any]:
        salt = b""
        if noise_per_run and screen_id in noise_per_run:
            salt = noise_per_run[screen_id] + str(run_idx).encode()
        payload = _png_bytes(screen_id.encode() + salt)
        out_dir.mkdir(parents=True, exist_ok=True)
        png_path = out_dir / f"{screen_id}.png"
        png_path.write_bytes(payload)
        return {
            "success": True,
            "image_path": png_path,
            "image_md5": sc.md5_of(png_path),
            "viewport": {"w": 393, "h": 852},
        }

    return runner


def _capture_all(
    screens: list[str],
    out_dir: Path,
    *,
    noise: dict[str, bytes] | None = None,
    run_idx: int = 0,
) -> dict[str, sc.CaptureResult]:
    out: dict[str, sc.CaptureResult] = {}
    for sid in screens:
        runner = _fake_runner_factory(sid, out_dir, noise_per_run=noise, run_idx=run_idx)
        out[sid] = sc.capture_with_retries(sid, runner, sleep=lambda _s: None)
    return out


# ───────────────────────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────────────────────


def test_two_runs_back_to_back_produce_identical_md5_for_all_clean_screens(tmp_path: Path):
    """Without noise, 100% of the screens must collapse to identical md5."""
    screens = ["welcome", "login", "home", "profile"]
    a_dir = tmp_path / "run_a"
    b_dir = tmp_path / "run_b"

    a = _capture_all(screens, a_dir, run_idx=0)
    b = _capture_all(screens, b_dir, run_idx=1)

    matches = sum(1 for sid in screens if a[sid].image_md5 == b[sid].image_md5)
    assert matches == len(screens), f"All {len(screens)} should match, got {matches}"


def test_two_runs_match_at_least_80_percent_with_tail_of_noise(tmp_path: Path):
    """Up to 20% of screens may legitimately differ between runs (SC-003)."""
    # 10 screens; inject noise into 2 (20%) — boundary case.
    screens = [f"screen_{i}" for i in range(10)]
    noise = {sid: b"unstable" for sid in screens[:2]}
    a_dir = tmp_path / "run_a"
    b_dir = tmp_path / "run_b"

    a = _capture_all(screens, a_dir, noise=noise, run_idx=0)
    b = _capture_all(screens, b_dir, noise=noise, run_idx=1)

    matches = sum(1 for sid in screens if a[sid].image_md5 == b[sid].image_md5)
    determinism_ratio = matches / len(screens)
    assert determinism_ratio >= 0.8, (
        f"determinism dropped below 80%: {matches}/{len(screens)}"
    )


def test_three_noisy_screens_out_of_ten_breaks_threshold(tmp_path: Path):
    """If >20% of screens churn between runs, the test must flag a regression."""
    screens = [f"s_{i}" for i in range(10)]
    noise = {sid: b"jitter" for sid in screens[:3]}  # 30% noise
    a = _capture_all(screens, tmp_path / "a", noise=noise, run_idx=0)
    b = _capture_all(screens, tmp_path / "b", noise=noise, run_idx=1)
    matches = sum(1 for sid in screens if a[sid].image_md5 == b[sid].image_md5)
    assert matches / len(screens) < 0.8


def test_apply_capture_result_sets_status_captured_and_capture_record(tmp_path: Path):
    """The orchestrator must persist captured_at + image_md5 + viewport on success."""
    yaml_path = tmp_path / "screen-flow.yaml"
    doc = {
        "schema_version": 1,
        "meta": {"device": "mobile", "capture_profile": "iphone-15"},
        "screens": [
            {
                "id": "welcome",
                "title": "Welcome",
                "status": "pending",
                "body": [{"type": "heading", "text": "Hi"}],
            }
        ],
        "flows": [],
    }
    sc.save_screen_flow(yaml_path, doc)

    runner = _fake_runner_factory("welcome", tmp_path / "shots")
    result = sc.capture_with_retries("welcome", runner, sleep=lambda _s: None)
    assert result.status == "captured"

    sc.apply_capture_result(doc, result, app_version="abcdef0")
    sc.save_screen_flow(yaml_path, doc)

    reloaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    screen = reloaded["screens"][0]
    assert screen["status"] == "captured"
    assert screen["capture"]["app_version"] == "abcdef0"
    assert len(screen["capture"]["image_md5"]) == 32
    assert screen["capture"]["viewport"] == {"w": 393, "h": 852}
    assert "failure" not in screen


def test_yaml_is_committed_with_mixed_captured_and_failed_status(tmp_path: Path):
    """FR-046 — when at least one screen fails, the YAML still includes the
    captured ones; only the workflow exit code becomes 1."""
    yaml_path = tmp_path / "screen-flow.yaml"
    doc = {
        "schema_version": 1,
        "meta": {"device": "mobile", "capture_profile": "iphone-15"},
        "screens": [
            {"id": "ok", "title": "OK", "status": "pending",
             "body": [{"type": "heading", "text": "ok"}]},
            {"id": "broken", "title": "Broken", "status": "pending",
             "body": [{"type": "heading", "text": "broken"}]},
        ],
        "flows": [],
    }
    sc.save_screen_flow(yaml_path, doc)

    ok_result = sc.capture_with_retries(
        "ok",
        _fake_runner_factory("ok", tmp_path / "shots"),
        sleep=lambda _s: None,
    )

    def fail_runner() -> dict[str, Any]:
        return {"success": False, "reason": "timeout", "error": "Timeout 30000ms exceeded"}

    fail_result = sc.capture_with_retries(
        "broken", fail_runner, sleep=lambda _s: None,
    )

    sc.apply_capture_result(doc, ok_result, app_version="abc1234")
    sc.apply_capture_result(doc, fail_result, app_version="abc1234")
    sc.save_screen_flow(yaml_path, doc)

    reloaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in reloaded["screens"]}
    assert by_id["ok"]["status"] == "captured"
    assert by_id["broken"]["status"] == "failed"
    assert by_id["broken"]["failure"]["reason"] == "timeout"
    assert sc.compute_workflow_exit_code([ok_result, fail_result]) == 1


def test_load_capture_config_rejects_opted_out_platforms(tmp_path: Path):
    """When enabled=false the orchestrator must raise so the workflow skips."""
    p = tmp_path / "platforms" / "demo"
    p.mkdir(parents=True)
    (p / "platform.yaml").write_text(
        "name: demo\n"
        "screen_flow:\n"
        "  enabled: false\n"
        "  skip_reason: 'not yet'\n",
        encoding="utf-8",
    )
    with pytest.raises(KeyError):
        sc.load_capture_config(p)


def test_load_capture_config_rejects_missing_test_user_marker(tmp_path: Path):
    """FR-047 — capture must abort if test_user_marker is missing."""
    p = tmp_path / "platforms" / "demo"
    p.mkdir(parents=True)
    (p / "platform.yaml").write_text(
        "name: demo\n"
        "screen_flow:\n"
        "  enabled: true\n"
        "  capture:\n"
        "    base_url: https://example.com\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="test_user_marker"):
        sc.load_capture_config(p)
