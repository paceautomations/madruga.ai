"""Tests for db.py gate management functions (epic 013)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".specify" / "scripts"))

import pytest

from db import (
    approve_gate,
    get_conn,
    get_pending_gates,
    get_resumable_nodes,
    insert_run,
    migrate,
    reject_gate,
    upsert_pipeline_node,
    upsert_platform,
)


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    """Create an in-memory DB with migrations applied."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("db.DB_PATH", db_path)
    monkeypatch.setattr("db.MIGRATIONS_DIR", Path(__file__).resolve().parents[1] / ".pipeline" / "migrations")
    c = get_conn(str(db_path))
    migrate(c)
    upsert_platform(c, "test-plat", name="Test", repo_path="platforms/test")
    return c


def _insert_gated_run(conn, node_id, gate_status="waiting_approval"):
    run_id = insert_run(conn, "test-plat", node_id)
    if gate_status:
        conn.execute(
            "UPDATE pipeline_runs SET gate_status=?, gate_notified_at=datetime('now') WHERE run_id=?",
            (gate_status, run_id),
        )
        conn.commit()
    return run_id


class TestApproveGate:
    def test_approve_pending(self, conn):
        run_id = _insert_gated_run(conn, "vision")
        assert approve_gate(conn, run_id) is True
        row = dict(
            conn.execute("SELECT gate_status, gate_resolved_at FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
        )
        assert row["gate_status"] == "approved"
        assert row["gate_resolved_at"] is not None

    def test_approve_already_approved(self, conn):
        run_id = _insert_gated_run(conn, "vision", gate_status="approved")
        assert approve_gate(conn, run_id) is False

    def test_approve_nonexistent(self, conn):
        assert approve_gate(conn, "nonexistent") is False


class TestRejectGate:
    def test_reject_pending(self, conn):
        run_id = _insert_gated_run(conn, "vision")
        assert reject_gate(conn, run_id) is True
        row = dict(conn.execute("SELECT gate_status FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone())
        assert row["gate_status"] == "rejected"

    def test_reject_already_rejected(self, conn):
        run_id = _insert_gated_run(conn, "vision", gate_status="rejected")
        assert reject_gate(conn, run_id) is False


class TestGetPendingGates:
    def test_lists_pending_only(self, conn):
        _insert_gated_run(conn, "vision")
        _insert_gated_run(conn, "blueprint")
        _insert_gated_run(conn, "adr", gate_status="approved")
        pending = get_pending_gates(conn, "test-plat")
        assert len(pending) == 2
        assert {g["node_id"] for g in pending} == {"vision", "blueprint"}

    def test_empty_when_none(self, conn):
        assert get_pending_gates(conn, "test-plat") == []


class TestGetResumableNodes:
    def test_returns_done_nodes(self, conn):
        upsert_pipeline_node(conn, "test-plat", "vision", status="done")
        upsert_pipeline_node(conn, "test-plat", "blueprint", status="pending")
        nodes = get_resumable_nodes(conn, "test-plat")
        assert "vision" in nodes
        assert "blueprint" not in nodes

    def test_includes_approved_gates(self, conn):
        _insert_gated_run(conn, "vision", gate_status="approved")
        nodes = get_resumable_nodes(conn, "test-plat")
        assert "vision" in nodes

    def test_epic_mode(self, conn):
        from db import upsert_epic, upsert_epic_node

        upsert_epic(conn, "test-plat", "013", title="Test Epic")
        upsert_epic_node(conn, "test-plat", "013", "specify", status="done")
        upsert_epic_node(conn, "test-plat", "013", "plan", status="pending")
        nodes = get_resumable_nodes(conn, "test-plat", epic_id="013")
        assert "specify" in nodes
        assert "plan" not in nodes
