"""Tests for easter.py observability endpoints (Epic 017, T010/T012)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


# ── helpers ──────────────────────────────────────────────────────────────


def _get_app():
    from easter import app

    return app


def _make_test_db(tmp_path: Path) -> sqlite3.Connection:
    """Create an in-memory DB with full migrations and seed observability data."""
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))

    from db import get_conn, migrate

    db_path = tmp_path / "test_easter_obs.db"
    migrations_dir = Path(__file__).parent.parent.parent.parent / ".pipeline" / "migrations"
    conn = get_conn(db_path)
    migrate(conn, migrations_dir)
    return conn


def _seed_platform(conn, platform_id="test-plat"):
    from db import upsert_platform

    upsert_platform(conn, platform_id, name=platform_id)


def _seed_data(conn, platform_id="test-plat"):
    """Seed traces, pipeline_runs (spans), and eval_scores for endpoint tests."""
    from db import complete_trace, create_trace, insert_eval_score, insert_run

    _seed_platform(conn, platform_id)

    # Trace 1: completed with 2 spans
    t1 = create_trace(conn, platform_id, epic_id="017-obs", mode="l2", total_nodes=2)
    r1 = insert_run(
        conn, platform_id, "specify", trace_id=t1, tokens_in=100, tokens_out=50, cost_usd=0.01, duration_ms=1000
    )
    r2 = insert_run(
        conn, platform_id, "plan", trace_id=t1, tokens_in=200, tokens_out=100, cost_usd=0.02, duration_ms=2000
    )
    from db import complete_run

    complete_run(conn, r1, "completed")
    complete_run(conn, r2, "completed")
    complete_trace(conn, t1, "completed")

    # Eval scores for trace 1
    insert_eval_score(conn, t1, platform_id, "017-obs", "specify", r1, "quality", 8.5)
    insert_eval_score(conn, t1, platform_id, "017-obs", "specify", r1, "completeness", 7.0)

    # Trace 2: running (no spans completed)
    t2 = create_trace(conn, platform_id, mode="l1", total_nodes=3)
    insert_run(conn, platform_id, "vision", trace_id=t2)

    # Trace 3: failed
    t3 = create_trace(conn, platform_id, epic_id="016-test", mode="l2", total_nodes=5)
    complete_trace(conn, t3, "failed")

    return {"t1": t1, "t2": t2, "t3": t3, "r1": r1, "r2": r2}


@pytest.fixture
def seeded_app(tmp_path):
    """Yield (app, conn, seed_ids) with a seeded DB wired into app.state."""
    app = _get_app()
    conn = _make_test_db(tmp_path)
    ids = _seed_data(conn)
    app.state.db_conn = conn
    yield app, conn, ids
    conn.close()


# ── GET /api/traces — list with platform_id filter ──────────────────────


@pytest.mark.asyncio
async def test_list_traces_returns_traces_for_platform(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/traces", params={"platform_id": "test-plat"})
    assert resp.status_code == 200
    data = resp.json()
    assert "traces" in data
    assert data["total"] == 3
    assert len(data["traces"]) == 3


@pytest.mark.asyncio
async def test_list_traces_empty_for_unknown_platform(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/traces", params={"platform_id": "nonexistent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["traces"] == []


# ── GET /api/traces — pagination ────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_traces_pagination(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/traces", params={"platform_id": "test-plat", "limit": 2, "offset": 0})
    data = resp.json()
    assert data["total"] == 3
    assert len(data["traces"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_traces_pagination_offset(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        page1 = await client.get("/api/traces", params={"platform_id": "test-plat", "limit": 2, "offset": 0})
        page2 = await client.get("/api/traces", params={"platform_id": "test-plat", "limit": 2, "offset": 2})

    ids_p1 = {t["trace_id"] for t in page1.json()["traces"]}
    ids_p2 = {t["trace_id"] for t in page2.json()["traces"]}
    assert ids_p1.isdisjoint(ids_p2)
    assert len(page2.json()["traces"]) == 1  # 3 total, offset 2 → 1 left


# ── GET /api/traces — status filter ────────────────────────────────────


@pytest.mark.asyncio
async def test_list_traces_status_filter_completed(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/traces", params={"platform_id": "test-plat", "status": "completed"})
    data = resp.json()
    assert data["total"] == 1
    assert data["traces"][0]["trace_id"] == ids["t1"]


@pytest.mark.asyncio
async def test_list_traces_status_filter_running(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/traces", params={"platform_id": "test-plat", "status": "running"})
    data = resp.json()
    assert data["total"] == 1
    assert data["traces"][0]["trace_id"] == ids["t2"]


@pytest.mark.asyncio
async def test_list_traces_status_filter_failed(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/traces", params={"platform_id": "test-plat", "status": "failed"})
    data = resp.json()
    assert data["total"] == 1
    assert data["traces"][0]["trace_id"] == ids["t3"]


# ── GET /api/traces — 400 on missing platform_id ───────────────────────


@pytest.mark.asyncio
async def test_list_traces_400_missing_platform_id(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/traces")
    assert resp.status_code == 400
    assert resp.json()["error"] == "platform_id is required"


# ── GET /api/traces/{trace_id} — detail with spans ─────────────────────


@pytest.mark.asyncio
async def test_trace_detail_returns_trace_and_spans(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/traces/{ids['t1']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace"]["trace_id"] == ids["t1"]
    assert data["trace"]["status"] == "completed"
    assert len(data["spans"]) == 2
    node_ids = [s["node_id"] for s in data["spans"]]
    assert node_ids == ["specify", "plan"]


@pytest.mark.asyncio
async def test_trace_detail_includes_eval_scores(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/traces/{ids['t1']}")
    data = resp.json()
    assert len(data["eval_scores"]) == 2
    dims = {e["dimension"] for e in data["eval_scores"]}
    assert dims == {"quality", "completeness"}


@pytest.mark.asyncio
async def test_trace_detail_running_trace_has_spans(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/traces/{ids['t2']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace"]["status"] == "running"
    assert len(data["spans"]) == 1
    assert data["spans"][0]["node_id"] == "vision"


# ── GET /api/traces/{trace_id} — 404 on unknown trace_id ───────────────


@pytest.mark.asyncio
async def test_trace_detail_404_unknown_trace_id(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/traces/nonexistent-trace-id")
    assert resp.status_code == 404
    assert resp.json()["error"] == "trace not found"


# ── GET /api/stats — aggregated stats ────────────────────────────────────


@pytest.mark.asyncio
async def test_stats_returns_aggregated_data(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats", params={"platform_id": "test-plat"})
    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data
    assert "summary" in data
    assert data["period_days"] == 30
    assert isinstance(data["stats"], list)
    assert data["summary"]["total_runs"] >= 1


@pytest.mark.asyncio
async def test_stats_custom_days(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats", params={"platform_id": "test-plat", "days": 7})
    assert resp.status_code == 200
    data = resp.json()
    assert data["period_days"] == 7


@pytest.mark.asyncio
async def test_stats_global_without_platform_id(seeded_app):
    """When platform_id is omitted, /api/stats returns global aggregated data."""
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "stats" in data


@pytest.mark.asyncio
async def test_stats_empty_for_unknown_platform(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats", params={"platform_id": "nonexistent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"] == []
    assert data["summary"]["total_runs"] == 0


# ── GET /api/evals — eval scores with filters ──────────────────────────


@pytest.mark.asyncio
async def test_evals_returns_scores_for_platform(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/evals", params={"platform_id": "test-plat"})
    assert resp.status_code == 200
    data = resp.json()
    assert "scores" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["scores"]) == 2


@pytest.mark.asyncio
async def test_evals_filter_by_node_id(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/evals", params={"platform_id": "test-plat", "node_id": "specify"})
    data = resp.json()
    assert data["total"] == 2
    for s in data["scores"]:
        assert s["node_id"] == "specify"


@pytest.mark.asyncio
async def test_evals_filter_by_dimension(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/evals", params={"platform_id": "test-plat", "dimension": "quality"})
    data = resp.json()
    assert data["total"] == 1
    assert data["scores"][0]["dimension"] == "quality"
    assert data["scores"][0]["score"] == 8.5


@pytest.mark.asyncio
async def test_evals_filter_by_node_and_dimension(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/evals", params={"platform_id": "test-plat", "node_id": "specify", "dimension": "completeness"}
        )
    data = resp.json()
    assert data["total"] == 1
    assert data["scores"][0]["score"] == 7.0


@pytest.mark.asyncio
async def test_evals_limit(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/evals", params={"platform_id": "test-plat", "limit": 1})
    data = resp.json()
    assert data["total"] == 2  # total count unaffected by limit
    assert len(data["scores"]) == 1


@pytest.mark.asyncio
async def test_evals_400_missing_platform_id(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/evals")
    assert resp.status_code == 400
    assert resp.json()["error"] == "platform_id is required"


@pytest.mark.asyncio
async def test_evals_empty_for_unknown_platform(seeded_app):
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/evals", params={"platform_id": "nonexistent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["scores"] == []


@pytest.mark.asyncio
async def test_stats_days_clamped_to_90(seeded_app):
    """FastAPI validates days <= 90 via Query(le=90), returning 422."""
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats", params={"platform_id": "test-plat", "days": 120})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_stats_includes_top_nodes(seeded_app):
    """Stats response should include top_nodes from pipeline_runs costs."""
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats", params={"platform_id": "test-plat"})
    assert resp.status_code == 200
    data = resp.json()
    assert "top_nodes" in data
    assert isinstance(data["top_nodes"], list)


@pytest.mark.asyncio
async def test_stats_includes_failed_runs(seeded_app):
    """Stats summary should include failed_runs count (U3 fix)."""
    app, conn, ids = seeded_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats", params={"platform_id": "test-plat"})
    assert resp.status_code == 200
    data = resp.json()
    assert "failed_runs" in data["summary"]
    assert isinstance(data["summary"]["failed_runs"], int)
