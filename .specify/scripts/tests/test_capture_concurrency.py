"""Concurrency safety integration test (FR-035, SC-012).

Source task: T063 (epic 027-screen-flow-canvas Phase 6 / US4).

Two simultaneous capture writers MUST serialize writes to screen-flow.yaml
without corruption. The CI side relies on a GitHub Actions ``concurrency``
block; this test exercises the in-process safety net (``acquire_yaml_lock``)
that protects local dev concurrent dispatches.

Invariant tested:
    Given N parallel writers each appending an opaque marker to the YAML
    document, the final document
    (a) parses cleanly as YAML,
    (b) contains markers from every writer,
    (c) preserves the schema_version + meta keys.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "capture"))

import screen_capture as sc  # noqa: E402


def _seed_doc(yaml_path: Path) -> None:
    sc.save_screen_flow(
        yaml_path,
        {
            "schema_version": 1,
            "meta": {"device": "mobile", "capture_profile": "iphone-15"},
            "screens": [],
            "flows": [],
        },
    )


def _writer_under_lock(yaml_path: Path, screen_id: str, *, hold_for: float = 0.05) -> None:
    """Acquire the lock, append a screen, sleep, write back, release."""
    with sc.acquire_yaml_lock(yaml_path):
        doc = sc.load_screen_flow(yaml_path)
        screens = doc.setdefault("screens", [])
        screens.append(
            {
                "id": screen_id,
                "title": screen_id,
                "status": "pending",
                "body": [{"type": "heading", "text": screen_id}],
            }
        )
        # Simulate slow I/O while holding the lock to maximize contention.
        time.sleep(hold_for)
        sc.save_screen_flow(yaml_path, doc)


# ───────────────────────────────────────────────────────────────────────────────
# Tests
# ───────────────────────────────────────────────────────────────────────────────


def test_two_writers_under_lock_do_not_corrupt_yaml(tmp_path: Path):
    yaml_path = tmp_path / "screen-flow.yaml"
    _seed_doc(yaml_path)

    threads = [
        threading.Thread(target=_writer_under_lock, args=(yaml_path, f"writer_{i}"))
        for i in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
        assert not t.is_alive(), "writer hung — lock deadlocked"

    final = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert final["schema_version"] == 1
    ids = {s["id"] for s in final["screens"]}
    assert ids == {"writer_0", "writer_1"}, ids


def test_many_writers_serialize_cleanly(tmp_path: Path):
    """Stress test — 8 writers should all land their screen, none lost."""
    yaml_path = tmp_path / "screen-flow.yaml"
    _seed_doc(yaml_path)

    n = 8
    threads = [
        threading.Thread(
            target=_writer_under_lock,
            args=(yaml_path, f"w_{i}"),
            kwargs={"hold_for": 0.02},
        )
        for i in range(n)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive()

    final = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    ids = {s["id"] for s in final["screens"]}
    assert ids == {f"w_{i}" for i in range(n)}


def test_lock_actually_serializes_critical_section(tmp_path: Path):
    """If two threads enter the lock window at overlapping wall-clock instants,
    they must NOT both be inside the critical section at the same time."""
    yaml_path = tmp_path / "screen-flow.yaml"
    _seed_doc(yaml_path)

    inside = {"count": 0, "max": 0}
    inside_lock = threading.Lock()

    def race():
        with sc.acquire_yaml_lock(yaml_path):
            with inside_lock:
                inside["count"] += 1
                inside["max"] = max(inside["max"], inside["count"])
            time.sleep(0.05)
            with inside_lock:
                inside["count"] -= 1

    threads = [threading.Thread(target=race) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    # If the lock works, only ONE thread is ever inside at a time.
    assert inside["max"] == 1, (
        f"lock failed: {inside['max']} writers entered the critical section"
    )


def test_concurrent_capture_apply_keeps_each_screen_record(tmp_path: Path):
    """Higher-level scenario: parallel apply_capture_result calls preserve every
    screen's outcome, regardless of which thread won the race."""
    yaml_path = tmp_path / "screen-flow.yaml"
    sc.save_screen_flow(
        yaml_path,
        {
            "schema_version": 1,
            "meta": {"device": "mobile", "capture_profile": "iphone-15"},
            "screens": [
                {"id": f"s_{i}", "title": f"S{i}", "status": "pending",
                 "body": [{"type": "heading", "text": "h"}]}
                for i in range(4)
            ],
            "flows": [],
        },
    )

    def write_for(screen_id: str, status: str):
        with sc.acquire_yaml_lock(yaml_path):
            doc = sc.load_screen_flow(yaml_path)
            if status == "captured":
                result = sc.CaptureResult(
                    screen_id=screen_id,
                    status="captured",
                    image_path=Path(f"shots/{screen_id}.png"),
                    image_md5="a" * 32,
                    viewport={"w": 393, "h": 852},
                    retry_count=0,
                )
            else:
                result = sc.CaptureResult(
                    screen_id=screen_id,
                    status="failed",
                    reason="timeout",
                    last_error_message="timed out",
                    retry_count=3,
                )
            sc.apply_capture_result(doc, result, app_version="abc1234")
            sc.save_screen_flow(yaml_path, doc)

    plan = [("s_0", "captured"), ("s_1", "failed"),
            ("s_2", "captured"), ("s_3", "failed")]
    threads = [threading.Thread(target=write_for, args=p) for p in plan]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    final = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in final["screens"]}
    assert by_id["s_0"]["status"] == "captured"
    assert by_id["s_1"]["status"] == "failed"
    assert by_id["s_2"]["status"] == "captured"
    assert by_id["s_3"]["status"] == "failed"
    assert by_id["s_1"]["failure"]["reason"] == "timeout"
    assert by_id["s_3"]["failure"]["reason"] == "timeout"
