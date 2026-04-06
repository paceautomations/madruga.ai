"""Tests for db.py observability functions: traces, spans, evals (Epic 017)."""

import pytest


# ── helpers ──────────────────────────────────────────────────────────────


def _seed_platform(conn, platform_id="test-plat"):
    """Insert a minimal platform row for FK satisfaction."""
    from db import upsert_platform

    upsert_platform(conn, platform_id, name=platform_id)
    return platform_id


def _seed_trace(conn, platform_id="test-plat", **kwargs):
    """Create a trace and return its trace_id."""
    from db import create_trace

    return create_trace(conn, platform_id, **kwargs)


def _seed_run(conn, platform_id="test-plat", node_id="vision", **kwargs):
    """Insert a pipeline run (span) and return its run_id."""
    from db import insert_run

    return insert_run(conn, platform_id, node_id, **kwargs)


# ── create_trace ─────────────────────────────────────────────────────────


def test_create_trace_returns_valid_id(tmp_db):
    _seed_platform(tmp_db)
    from db import create_trace

    trace_id = create_trace(tmp_db, "test-plat")
    assert isinstance(trace_id, str)
    assert len(trace_id) == 32  # uuid4().hex


def test_create_trace_defaults(tmp_db):
    _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    row = tmp_db.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
    assert row["status"] == "running"
    assert row["mode"] == "l1"
    assert row["total_nodes"] == 0
    assert row["epic_id"] is None
    assert row["started_at"] is not None


def test_create_trace_with_epic(tmp_db):
    _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db, epic_id="017-obs", mode="l2", total_nodes=5)

    row = tmp_db.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
    assert row["epic_id"] == "017-obs"
    assert row["mode"] == "l2"
    assert row["total_nodes"] == 5


def test_create_trace_unique_ids(tmp_db):
    _seed_platform(tmp_db)
    ids = {_seed_trace(tmp_db) for _ in range(10)}
    assert len(ids) == 10


# ── complete_trace ───────────────────────────────────────────────────────


def test_complete_trace_aggregates_span_metrics(tmp_db):
    """complete_trace should sum tokens/cost/duration from linked pipeline_runs."""
    from db import complete_trace

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    # Create two spans linked to the trace
    _seed_run(tmp_db, pid, "specify", trace_id=trace_id, tokens_in=100, tokens_out=50, cost_usd=0.01, duration_ms=1000)
    from db import complete_run

    r2 = _seed_run(
        tmp_db, pid, "plan", trace_id=trace_id, tokens_in=200, tokens_out=100, cost_usd=0.02, duration_ms=2000
    )
    complete_run(tmp_db, r2, "completed")

    complete_trace(tmp_db, trace_id, "completed")

    row = tmp_db.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
    assert row["status"] == "completed"
    assert row["completed_at"] is not None
    assert row["total_tokens_in"] == 300
    assert row["total_tokens_out"] == 150
    assert pytest.approx(row["total_cost_usd"], abs=1e-6) == 0.03
    assert row["total_duration_ms"] == 3000
    assert row["completed_nodes"] == 1  # only r2 was completed


def test_complete_trace_no_spans(tmp_db):
    """complete_trace with no spans should set zeroes/nulls gracefully."""
    from db import complete_trace

    _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    complete_trace(tmp_db, trace_id, "failed")

    row = tmp_db.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
    assert row["status"] == "failed"
    assert row["completed_nodes"] == 0
    assert row["total_tokens_in"] is None
    assert row["total_cost_usd"] is None


# ── get_traces ───────────────────────────────────────────────────────────


def test_get_traces_pagination(tmp_db):
    from db import get_traces

    _seed_platform(tmp_db)
    for _ in range(5):
        _seed_trace(tmp_db)

    traces, total = get_traces(tmp_db, "test-plat", limit=2, offset=0)
    assert total == 5
    assert len(traces) == 2

    traces2, total2 = get_traces(tmp_db, "test-plat", limit=2, offset=2)
    assert total2 == 5
    assert len(traces2) == 2

    # no overlap
    ids_page1 = {t["trace_id"] for t in traces}
    ids_page2 = {t["trace_id"] for t in traces2}
    assert ids_page1.isdisjoint(ids_page2)


def test_get_traces_status_filter(tmp_db):
    from db import get_traces, complete_trace

    _seed_platform(tmp_db)
    t1 = _seed_trace(tmp_db)
    _seed_trace(tmp_db)  # stays running
    complete_trace(tmp_db, t1, "completed")

    completed, total_c = get_traces(tmp_db, "test-plat", status_filter="completed")
    assert total_c == 1
    assert completed[0]["trace_id"] == t1

    running, total_r = get_traces(tmp_db, "test-plat", status_filter="running")
    assert total_r == 1


def test_get_traces_includes_span_counts(tmp_db):
    from db import get_traces

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    _seed_run(tmp_db, pid, "specify", trace_id=trace_id)
    from db import complete_run

    r2 = _seed_run(tmp_db, pid, "plan", trace_id=trace_id)
    complete_run(tmp_db, r2, "completed")

    traces, _ = get_traces(tmp_db, "test-plat")
    t = traces[0]
    assert t["span_count"] == 2
    assert t["completed_spans"] == 1


def test_get_traces_empty(tmp_db):
    _seed_platform(tmp_db)
    from db import get_traces

    traces, total = get_traces(tmp_db, "test-plat")
    assert traces == []
    assert total == 0


# ── get_trace_detail ─────────────────────────────────────────────────────


def test_get_trace_detail_returns_trace_and_ordered_spans(tmp_db):
    from db import get_trace_detail

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    # Insert spans — order matters
    _seed_run(tmp_db, pid, "specify", trace_id=trace_id, run_id="run-001")
    _seed_run(tmp_db, pid, "plan", trace_id=trace_id, run_id="run-002")
    _seed_run(tmp_db, pid, "tasks", trace_id=trace_id, run_id="run-003")

    detail = get_trace_detail(tmp_db, trace_id)
    assert detail is not None
    assert detail["trace"]["trace_id"] == trace_id
    assert len(detail["spans"]) == 3
    # Ordered by started_at ASC
    node_ids = [s["node_id"] for s in detail["spans"]]
    assert node_ids == ["specify", "plan", "tasks"]


def test_get_trace_detail_includes_eval_scores(tmp_db):
    from db import get_trace_detail, insert_eval_score

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, pid, "specify", trace_id=trace_id)

    insert_eval_score(tmp_db, trace_id, pid, None, "specify", run_id, "quality", 8.5)
    insert_eval_score(tmp_db, trace_id, pid, None, "specify", run_id, "completeness", 7.0)

    detail = get_trace_detail(tmp_db, trace_id)
    assert len(detail["eval_scores"]) == 2
    dims = {e["dimension"] for e in detail["eval_scores"]}
    assert dims == {"quality", "completeness"}


def test_get_trace_detail_not_found(tmp_db):
    from db import get_trace_detail

    assert get_trace_detail(tmp_db, "nonexistent") is None


# ── trace_id FK on pipeline_runs ─────────────────────────────────────────


def test_pipeline_run_trace_id_fk(tmp_db):
    """pipeline_runs.trace_id should accept valid trace references."""
    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, pid, "specify", trace_id=trace_id)

    row = tmp_db.execute("SELECT trace_id FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["trace_id"] == trace_id


def test_pipeline_run_trace_id_nullable(tmp_db):
    """pipeline_runs.trace_id should allow NULL (pre-017 runs)."""
    pid = _seed_platform(tmp_db)
    run_id = _seed_run(tmp_db, pid, "vision")

    row = tmp_db.execute("SELECT trace_id FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["trace_id"] is None


def test_pipeline_run_trace_id_column_exists(tmp_db):
    """The trace_id column should exist on pipeline_runs after migration."""
    cols = [row[1] for row in tmp_db.execute("PRAGMA table_info(pipeline_runs)").fetchall()]
    assert "trace_id" in cols


# ── get_stats ───────────────────────────────────────────────────────────


def _complete_trace_with_metrics(conn, trace_id, started_at, **metrics):
    """Set trace metrics and started_at directly for deterministic tests.

    Also creates a pipeline_run with matching metrics so get_stats (which
    queries pipeline_runs) sees the data.
    """
    conn.execute(
        "UPDATE traces SET status='completed', completed_at=?, started_at=?, "
        "total_cost_usd=?, total_tokens_in=?, total_tokens_out=?, total_duration_ms=? "
        "WHERE trace_id=?",
        (
            started_at,
            started_at,
            metrics.get("cost", 0),
            metrics.get("tokens_in", 0),
            metrics.get("tokens_out", 0),
            metrics.get("duration_ms", 0),
            trace_id,
        ),
    )
    # Get platform_id from the trace to create a matching pipeline_run
    row = conn.execute("SELECT platform_id FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
    platform_id = row["platform_id"] if row else "test-plat"
    import uuid

    run_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, node_id, status, "
        "cost_usd, tokens_in, tokens_out, duration_ms, started_at, completed_at, trace_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            platform_id,
            "stats-node",
            metrics.get("status", "completed"),
            metrics.get("cost", 0),
            metrics.get("tokens_in", 0),
            metrics.get("tokens_out", 0),
            metrics.get("duration_ms", 0),
            started_at,
            started_at,
            trace_id,
        ),
    )
    conn.commit()


def test_get_stats_empty(tmp_db):
    """get_stats with no traces returns empty stats and zeroed summary."""
    from db import get_stats

    _seed_platform(tmp_db)
    result = get_stats(tmp_db, "test-plat", days=30)
    assert result["stats"] == []
    assert result["summary"]["total_runs"] == 0
    assert result["summary"]["total_cost"] is None


def test_get_stats_aggregates_by_day(tmp_db):
    """get_stats groups traces by day and sums metrics correctly."""
    from db import get_stats

    _seed_platform(tmp_db)

    # Two traces on same day, one on another
    t1 = _seed_trace(tmp_db)
    t2 = _seed_trace(tmp_db)
    t3 = _seed_trace(tmp_db)
    _complete_trace_with_metrics(
        tmp_db, t1, "2026-04-01T10:00:00Z", cost=1.0, tokens_in=100, tokens_out=50, duration_ms=1000
    )
    _complete_trace_with_metrics(
        tmp_db, t2, "2026-04-01T14:00:00Z", cost=2.0, tokens_in=200, tokens_out=100, duration_ms=3000
    )
    _complete_trace_with_metrics(
        tmp_db, t3, "2026-04-02T08:00:00Z", cost=0.5, tokens_in=50, tokens_out=25, duration_ms=500
    )

    result = get_stats(tmp_db, "test-plat", days=90)

    assert len(result["stats"]) == 2

    day1 = result["stats"][0]
    assert day1["day"] == "2026-04-01"
    assert day1["runs"] == 2
    assert pytest.approx(day1["total_cost"], abs=1e-6) == 3.0
    assert day1["total_tokens_in"] == 300
    assert day1["total_tokens_out"] == 150
    assert pytest.approx(day1["avg_duration_ms"], abs=1e-6) == 2000.0

    day2 = result["stats"][1]
    assert day2["day"] == "2026-04-02"
    assert day2["runs"] == 1
    assert pytest.approx(day2["total_cost"], abs=1e-6) == 0.5


def test_get_stats_summary_totals(tmp_db):
    """get_stats summary should aggregate across all days in the period."""
    from db import get_stats

    _seed_platform(tmp_db)

    t1 = _seed_trace(tmp_db)
    t2 = _seed_trace(tmp_db)
    _complete_trace_with_metrics(
        tmp_db, t1, "2026-04-01T10:00:00Z", cost=1.0, tokens_in=100, tokens_out=50, duration_ms=1000
    )
    _complete_trace_with_metrics(
        tmp_db, t2, "2026-04-02T10:00:00Z", cost=3.0, tokens_in=300, tokens_out=150, duration_ms=2000
    )

    result = get_stats(tmp_db, "test-plat", days=90)

    s = result["summary"]
    assert s["total_runs"] == 2
    assert pytest.approx(s["total_cost"], abs=1e-6) == 4.0
    assert s["total_tokens_in"] == 400
    assert s["total_tokens_out"] == 200
    assert pytest.approx(s["avg_cost_per_run"], abs=1e-6) == 2.0


def test_get_stats_caps_days_at_90(tmp_db):
    """get_stats should cap the days parameter at 90."""
    from db import get_stats

    _seed_platform(tmp_db)

    # Trace 200 days ago — should be excluded even if days=200
    t1 = _seed_trace(tmp_db)
    _complete_trace_with_metrics(
        tmp_db, t1, "2025-09-15T10:00:00Z", cost=1.0, tokens_in=100, tokens_out=50, duration_ms=1000
    )

    result = get_stats(tmp_db, "test-plat", days=200)
    # Should be capped to 90 days, so old trace excluded
    assert result["summary"]["total_runs"] == 0


def test_get_stats_filters_by_platform(tmp_db):
    """get_stats should only return data for the specified platform."""
    from db import get_stats, upsert_platform

    _seed_platform(tmp_db, "plat-a")
    upsert_platform(tmp_db, "plat-b", name="plat-b")

    t1 = _seed_trace(tmp_db, platform_id="plat-a")
    t2 = _seed_trace(tmp_db, platform_id="plat-b")
    _complete_trace_with_metrics(
        tmp_db, t1, "2026-04-01T10:00:00Z", cost=1.0, tokens_in=100, tokens_out=50, duration_ms=1000
    )
    _complete_trace_with_metrics(
        tmp_db, t2, "2026-04-01T10:00:00Z", cost=5.0, tokens_in=500, tokens_out=250, duration_ms=5000
    )

    result = get_stats(tmp_db, "plat-a", days=90)
    assert result["summary"]["total_runs"] == 1
    assert pytest.approx(result["summary"]["total_cost"], abs=1e-6) == 1.0


def test_get_stats_null_metrics(tmp_db):
    """get_stats handles runs with NULL metrics gracefully."""
    from db import get_stats

    _seed_platform(tmp_db)

    # Pipeline run with no cost/token metrics
    t1 = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, node_id="null-node", trace_id=t1)
    tmp_db.execute(
        "UPDATE pipeline_runs SET started_at='2026-04-01T10:00:00Z' WHERE run_id=?",
        (run_id,),
    )
    tmp_db.commit()

    result = get_stats(tmp_db, "test-plat", days=90)
    assert len(result["stats"]) == 1
    assert result["stats"][0]["runs"] == 1
    assert result["stats"][0]["total_cost"] is None


# ── get_stats top_nodes ────────────────────────────────────────────────


def test_get_stats_returns_top_nodes(tmp_db):
    """get_stats should return top 5 nodes by cost from pipeline_runs."""
    from db import get_stats

    pid = _seed_platform(tmp_db)

    t1 = _seed_trace(tmp_db)
    tmp_db.execute("UPDATE traces SET started_at='2026-04-01T10:00:00Z' WHERE trace_id=?", (t1,))

    # Insert pipeline_runs with costs linked to trace
    for node_id, cost in [("specify", 1.0), ("plan", 3.0), ("tasks", 0.5), ("specify", 2.0)]:
        run_id = _seed_run(tmp_db, pid, node_id, trace_id=t1)
        tmp_db.execute(
            "UPDATE pipeline_runs SET cost_usd=?, status='completed' WHERE run_id=?",
            (cost, run_id),
        )
    tmp_db.commit()

    result = get_stats(tmp_db, pid, days=90)
    top = result["top_nodes"]

    assert len(top) >= 2
    # plan=3.0 should be first, specify=3.0 (1.0+2.0) tied
    node_ids = [n["node_id"] for n in top]
    assert "plan" in node_ids
    assert "specify" in node_ids
    assert top[0]["total_cost"] >= top[1]["total_cost"]


def test_get_stats_top_nodes_empty(tmp_db):
    """get_stats top_nodes empty when no pipeline_runs with cost."""
    from db import get_stats

    _seed_platform(tmp_db)
    _seed_trace(tmp_db)

    result = get_stats(tmp_db, "test-plat", days=90)
    assert result["top_nodes"] == []


# ── get_stats failed_runs (U3 fix) ────────────────────────────────────────


def test_get_stats_summary_includes_failed_runs(tmp_db):
    """get_stats summary should include failed_runs count from pipeline_runs."""
    from db import get_stats

    _seed_platform(tmp_db)

    t1 = _seed_trace(tmp_db)
    t2 = _seed_trace(tmp_db)
    t3 = _seed_trace(tmp_db)
    _complete_trace_with_metrics(
        tmp_db, t1, "2026-04-01T10:00:00Z", cost=1.0, tokens_in=100, tokens_out=50, duration_ms=1000
    )
    # t2 = failed — create a failed pipeline_run
    run_id = _seed_run(tmp_db, node_id="failed-node", trace_id=t2)
    tmp_db.execute(
        "UPDATE pipeline_runs SET status='failed', started_at='2026-04-01T12:00:00Z' WHERE run_id=?",
        (run_id,),
    )
    tmp_db.commit()
    _complete_trace_with_metrics(
        tmp_db, t3, "2026-04-02T08:00:00Z", cost=0.5, tokens_in=50, tokens_out=25, duration_ms=500
    )

    result = get_stats(tmp_db, "test-plat", days=90)
    assert result["summary"]["failed_runs"] == 1
    assert result["summary"]["total_runs"] == 3


def test_get_stats_summary_failed_runs_zero_when_none_failed(tmp_db):
    """failed_runs should be 0 when no pipeline_runs have failed status."""
    from db import get_stats

    _seed_platform(tmp_db)

    t1 = _seed_trace(tmp_db)
    _complete_trace_with_metrics(
        tmp_db, t1, "2026-04-01T10:00:00Z", cost=1.0, tokens_in=100, tokens_out=50, duration_ms=1000
    )

    result = get_stats(tmp_db, "test-plat", days=90)
    assert result["summary"]["failed_runs"] == 0


# ── insert_run output_lines (U2 fix) ──────────────────────────────────────


def test_insert_run_persists_output_lines(tmp_db):
    """insert_run should store output_lines when provided."""
    from db import insert_run

    _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    run_id = insert_run(tmp_db, "test-plat", "vision", trace_id=trace_id, output_lines=42)
    row = tmp_db.execute("SELECT output_lines FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["output_lines"] == 42


def test_insert_run_output_lines_null_by_default(tmp_db):
    """output_lines should be NULL when not provided."""
    from db import insert_run

    _seed_platform(tmp_db)

    run_id = insert_run(tmp_db, "test-plat", "vision")
    row = tmp_db.execute("SELECT output_lines FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["output_lines"] is None


def test_complete_run_updates_output_lines(tmp_db):
    """complete_run should update output_lines when provided."""
    from db import complete_run, insert_run

    _seed_platform(tmp_db)

    run_id = insert_run(tmp_db, "test-plat", "vision")
    complete_run(tmp_db, run_id, status="completed", output_lines=100)
    row = tmp_db.execute("SELECT output_lines FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
    assert row["output_lines"] == 100


# ── insert_eval_score ────────────────────────────────────────────────────


def test_insert_eval_score_returns_id(tmp_db):
    from db import insert_eval_score

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, pid, "specify", trace_id=trace_id)

    score_id = insert_eval_score(tmp_db, trace_id, pid, None, "specify", run_id, "quality", 8.5)
    assert isinstance(score_id, str)
    assert len(score_id) == 32


def test_insert_eval_score_persists(tmp_db):
    from db import insert_eval_score

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, pid, "specify", trace_id=trace_id)

    score_id = insert_eval_score(
        tmp_db, trace_id, pid, "017-obs", "specify", run_id, "completeness", 7.0, '{"method": "heuristic"}'
    )

    row = tmp_db.execute("SELECT * FROM eval_scores WHERE score_id=?", (score_id,)).fetchone()
    assert row["trace_id"] == trace_id
    assert row["platform_id"] == pid
    assert row["epic_id"] == "017-obs"
    assert row["node_id"] == "specify"
    assert row["run_id"] == run_id
    assert row["dimension"] == "completeness"
    assert row["score"] == 7.0
    assert row["metadata"] == '{"method": "heuristic"}'
    assert row["evaluated_at"] is not None


def test_insert_eval_score_duplicate_skips(tmp_db):
    """Duplicate (run_id, dimension) should return existing score_id, not insert."""
    from db import insert_eval_score

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, pid, "specify", trace_id=trace_id)

    id1 = insert_eval_score(tmp_db, trace_id, pid, None, "specify", run_id, "quality", 8.0)
    id2 = insert_eval_score(tmp_db, trace_id, pid, None, "specify", run_id, "quality", 9.0)

    assert id1 == id2
    # Only one row in DB
    count = tmp_db.execute(
        "SELECT COUNT(*) FROM eval_scores WHERE run_id=? AND dimension=?", (run_id, "quality")
    ).fetchone()[0]
    assert count == 1
    # Original score preserved
    row = tmp_db.execute("SELECT score FROM eval_scores WHERE score_id=?", (id1,)).fetchone()
    assert row["score"] == 8.0


def test_insert_eval_score_different_dimensions_allowed(tmp_db):
    """Same run_id but different dimensions should both insert."""
    from db import insert_eval_score

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, pid, "specify", trace_id=trace_id)

    id1 = insert_eval_score(tmp_db, trace_id, pid, None, "specify", run_id, "quality", 8.0)
    id2 = insert_eval_score(tmp_db, trace_id, pid, None, "specify", run_id, "completeness", 6.0)

    assert id1 != id2
    count = tmp_db.execute("SELECT COUNT(*) FROM eval_scores WHERE run_id=?", (run_id,)).fetchone()[0]
    assert count == 2


def test_insert_eval_score_null_run_id_no_dedup(tmp_db):
    """When run_id is None, dedup is skipped — both inserts should succeed."""
    from db import insert_eval_score

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    id1 = insert_eval_score(tmp_db, trace_id, pid, None, "specify", None, "quality", 7.0)
    id2 = insert_eval_score(tmp_db, trace_id, pid, None, "specify", None, "quality", 8.0)

    assert id1 != id2


# ── get_eval_scores ──────────────────────────────────────────────────────


def test_get_eval_scores_basic(tmp_db):
    from db import insert_eval_score, get_eval_scores

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, pid, "specify", trace_id=trace_id)

    insert_eval_score(tmp_db, trace_id, pid, None, "specify", run_id, "quality", 8.0)
    insert_eval_score(tmp_db, trace_id, pid, None, "specify", run_id, "completeness", 6.0)

    scores, total = get_eval_scores(tmp_db, pid)
    assert total == 2
    assert len(scores) == 2


def test_get_eval_scores_filter_by_platform(tmp_db):
    from db import insert_eval_score, get_eval_scores, upsert_platform

    pid_a = _seed_platform(tmp_db, "plat-a")
    upsert_platform(tmp_db, "plat-b", name="plat-b")
    t_a = _seed_trace(tmp_db, platform_id="plat-a")
    t_b = _seed_trace(tmp_db, platform_id="plat-b")

    insert_eval_score(tmp_db, t_a, pid_a, None, "specify", None, "quality", 8.0)
    insert_eval_score(tmp_db, t_b, "plat-b", None, "specify", None, "quality", 5.0)

    scores, total = get_eval_scores(tmp_db, "plat-a")
    assert total == 1
    assert scores[0]["platform_id"] == "plat-a"


def test_get_eval_scores_filter_by_node(tmp_db):
    from db import insert_eval_score, get_eval_scores

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    insert_eval_score(tmp_db, trace_id, pid, None, "specify", None, "quality", 8.0)
    insert_eval_score(tmp_db, trace_id, pid, None, "plan", None, "quality", 6.0)

    scores, total = get_eval_scores(tmp_db, pid, node_id="specify")
    assert total == 1
    assert scores[0]["node_id"] == "specify"


def test_get_eval_scores_filter_by_dimension(tmp_db):
    from db import insert_eval_score, get_eval_scores

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    insert_eval_score(tmp_db, trace_id, pid, None, "specify", None, "quality", 8.0)
    insert_eval_score(tmp_db, trace_id, pid, None, "specify", None, "completeness", 6.0)
    insert_eval_score(tmp_db, trace_id, pid, None, "specify", None, "adherence_to_spec", 7.0)

    scores, total = get_eval_scores(tmp_db, pid, dimension="completeness")
    assert total == 1
    assert scores[0]["dimension"] == "completeness"


def test_get_eval_scores_combined_filters(tmp_db):
    from db import insert_eval_score, get_eval_scores

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    insert_eval_score(tmp_db, trace_id, pid, None, "specify", None, "quality", 8.0)
    insert_eval_score(tmp_db, trace_id, pid, None, "specify", None, "completeness", 6.0)
    insert_eval_score(tmp_db, trace_id, pid, None, "plan", None, "quality", 7.0)

    scores, total = get_eval_scores(tmp_db, pid, node_id="specify", dimension="quality")
    assert total == 1
    assert scores[0]["node_id"] == "specify"
    assert scores[0]["dimension"] == "quality"


def test_get_eval_scores_ordered_by_evaluated_at_desc(tmp_db):
    """Scores should be returned most-recent first."""
    from db import get_eval_scores

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    # Insert with explicit timestamps via direct SQL to control order
    for i, ts in enumerate(["2026-04-01T10:00:00Z", "2026-04-02T10:00:00Z", "2026-04-03T10:00:00Z"]):
        import uuid

        sid = uuid.uuid4().hex
        tmp_db.execute(
            "INSERT INTO eval_scores "
            "(score_id, trace_id, platform_id, node_id, dimension, score, evaluated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, trace_id, pid, "specify", "quality", float(i + 5), ts),
        )
    tmp_db.commit()

    scores, total = get_eval_scores(tmp_db, pid)
    assert total == 3
    timestamps = [s["evaluated_at"] for s in scores]
    assert timestamps == sorted(timestamps, reverse=True)


def test_get_eval_scores_limit(tmp_db):
    from db import insert_eval_score, get_eval_scores

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)

    for i in range(5):
        insert_eval_score(tmp_db, trace_id, pid, None, f"node-{i}", None, "quality", float(i))

    scores, total = get_eval_scores(tmp_db, pid, limit=3)
    assert total == 5
    assert len(scores) == 3


def test_get_eval_scores_empty(tmp_db):
    from db import get_eval_scores

    _seed_platform(tmp_db)
    scores, total = get_eval_scores(tmp_db, "test-plat")
    assert scores == []
    assert total == 0


# ── cleanup_old_data ─────────────────────────────────────────────────────


def _insert_old_trace(conn, trace_id, platform_id, days_ago):
    """Insert a trace with started_at set to `days_ago` days in the past."""
    conn.execute(
        "INSERT INTO traces (trace_id, platform_id, mode, status, started_at) "
        "VALUES (?, ?, 'l1', 'completed', datetime('now', ?))",
        (trace_id, platform_id, f"-{days_ago} days"),
    )
    conn.commit()


def _insert_old_eval(conn, score_id, trace_id, platform_id, node_id, days_ago):
    """Insert an eval score with evaluated_at set to `days_ago` days in the past."""
    conn.execute(
        "INSERT INTO eval_scores (score_id, trace_id, platform_id, node_id, dimension, score, evaluated_at) "
        "VALUES (?, ?, ?, ?, 'quality', 7.0, datetime('now', ?))",
        (score_id, trace_id, platform_id, node_id, f"-{days_ago} days"),
    )
    conn.commit()


def _insert_old_run(conn, run_id, platform_id, node_id, trace_id, days_ago):
    """Insert a pipeline run with started_at set to `days_ago` days in the past."""
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, node_id, status, trace_id, started_at) "
        "VALUES (?, ?, ?, 'completed', ?, datetime('now', ?))",
        (run_id, platform_id, node_id, trace_id, f"-{days_ago} days"),
    )
    conn.commit()


def test_cleanup_removes_old_records(tmp_db):
    """cleanup_old_data should remove traces, runs, and evals older than 90 days."""
    from db import cleanup_old_data

    pid = _seed_platform(tmp_db)

    # Old data (100 days ago)
    _insert_old_trace(tmp_db, "old-trace", pid, 100)
    _insert_old_run(tmp_db, "old-run", pid, "vision", "old-trace", 100)
    _insert_old_eval(tmp_db, "old-eval", "old-trace", pid, "vision", 100)

    result = cleanup_old_data(tmp_db, days=90)

    assert result["traces"] == 1
    assert result["pipeline_runs"] == 1
    assert result["eval_scores"] == 1

    # Verify actually deleted
    assert tmp_db.execute("SELECT COUNT(*) FROM traces").fetchone()[0] == 0
    assert tmp_db.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0] == 0
    assert tmp_db.execute("SELECT COUNT(*) FROM eval_scores").fetchone()[0] == 0


def test_cleanup_preserves_recent_records(tmp_db):
    """cleanup_old_data should NOT remove records within the retention window."""
    from db import cleanup_old_data

    pid = _seed_platform(tmp_db)

    # Recent data (10 days ago)
    _insert_old_trace(tmp_db, "recent-trace", pid, 10)
    _insert_old_run(tmp_db, "recent-run", pid, "vision", "recent-trace", 10)
    _insert_old_eval(tmp_db, "recent-eval", "recent-trace", pid, "vision", 10)

    result = cleanup_old_data(tmp_db, days=90)

    assert result["traces"] == 0
    assert result["pipeline_runs"] == 0
    assert result["eval_scores"] == 0

    # Verify still present
    assert tmp_db.execute("SELECT COUNT(*) FROM traces").fetchone()[0] == 1
    assert tmp_db.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0] == 1
    assert tmp_db.execute("SELECT COUNT(*) FROM eval_scores").fetchone()[0] == 1


def test_cleanup_mixed_old_and_recent(tmp_db):
    """cleanup_old_data should only remove old records, keeping recent ones."""
    from db import cleanup_old_data

    pid = _seed_platform(tmp_db)

    # Old
    _insert_old_trace(tmp_db, "old-t", pid, 100)
    _insert_old_run(tmp_db, "old-r", pid, "vision", "old-t", 100)
    _insert_old_eval(tmp_db, "old-e", "old-t", pid, "vision", 100)

    # Recent
    _insert_old_trace(tmp_db, "new-t", pid, 10)
    _insert_old_run(tmp_db, "new-r", pid, "plan", "new-t", 10)
    _insert_old_eval(tmp_db, "new-e", "new-t", pid, "plan", 10)

    result = cleanup_old_data(tmp_db, days=90)

    assert result["traces"] == 1
    assert result["pipeline_runs"] == 1
    assert result["eval_scores"] == 1

    # Only recent remain
    assert tmp_db.execute("SELECT trace_id FROM traces").fetchone()[0] == "new-t"
    assert tmp_db.execute("SELECT run_id FROM pipeline_runs").fetchone()[0] == "new-r"
    assert tmp_db.execute("SELECT score_id FROM eval_scores").fetchone()[0] == "new-e"


def test_cleanup_empty_tables(tmp_db):
    """cleanup_old_data should handle empty tables gracefully."""
    from db import cleanup_old_data

    _seed_platform(tmp_db)
    result = cleanup_old_data(tmp_db, days=90)

    assert result == {"eval_scores": 0, "pipeline_runs": 0, "traces": 0}


def test_cleanup_untraced_pipeline_runs(tmp_db):
    """cleanup_old_data should also remove old pipeline_runs with trace_id IS NULL."""
    from db import cleanup_old_data

    pid = _seed_platform(tmp_db)

    # Old run without trace (pre-017)
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, node_id, status, trace_id, started_at) "
        "VALUES ('orphan-run', ?, 'vision', 'completed', NULL, datetime('now', '-100 days'))",
        (pid,),
    )
    tmp_db.commit()

    result = cleanup_old_data(tmp_db, days=90)

    assert result["pipeline_runs"] == 1
    assert tmp_db.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0] == 0


def test_cleanup_custom_days(tmp_db):
    """cleanup_old_data should respect the days parameter."""
    from db import cleanup_old_data

    pid = _seed_platform(tmp_db)

    # 50 days old — within 90 but outside 30
    _insert_old_trace(tmp_db, "mid-t", pid, 50)

    result_90 = cleanup_old_data(tmp_db, days=90)
    assert result_90["traces"] == 0  # 50 < 90, preserved

    result_30 = cleanup_old_data(tmp_db, days=30)
    assert result_30["traces"] == 1  # 50 > 30, deleted


# ── T029 edge cases ─────────────────────────────────────────────────────


def test_interrupted_pipeline_registers_partial_trace_cancelled(tmp_db):
    """Edge case: interrupted pipeline run registers partial trace with status 'cancelled'.

    Simulates a pipeline that started 3 nodes but was interrupted mid-run.
    complete_trace with status='cancelled' should aggregate only completed spans.
    """
    from db import complete_run, complete_trace

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db, total_nodes=5)

    # 2 completed spans
    r1 = _seed_run(
        tmp_db, pid, "specify", trace_id=trace_id, tokens_in=100, tokens_out=50, cost_usd=0.01, duration_ms=1000
    )
    complete_run(tmp_db, r1, "completed")
    r2 = _seed_run(
        tmp_db, pid, "plan", trace_id=trace_id, tokens_in=200, tokens_out=100, cost_usd=0.02, duration_ms=2000
    )
    complete_run(tmp_db, r2, "completed")
    # 1 running span (interrupted, never completed)
    _seed_run(tmp_db, pid, "tasks", trace_id=trace_id, tokens_in=50, tokens_out=25, cost_usd=0.005, duration_ms=500)

    # Pipeline interrupted — mark trace as cancelled
    complete_trace(tmp_db, trace_id, status="cancelled")

    row = tmp_db.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
    assert row["status"] == "cancelled"
    assert row["completed_at"] is not None
    assert row["completed_nodes"] == 2  # only 2 completed, 1 still running
    assert row["total_nodes"] == 5  # original total preserved
    # Aggregated metrics include ALL linked spans (completed + running)
    assert row["total_tokens_in"] == 350  # 100 + 200 + 50
    assert row["total_tokens_out"] == 175  # 50 + 100 + 25


def test_node_without_json_output_null_tokens_no_impact(tmp_db):
    """Edge case: node without JSON output registers tokens/cost as NULL
    without impacting other nodes in the same trace."""
    from db import complete_run, complete_trace

    pid = _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db, total_nodes=3)

    # Node 1: valid metrics
    r1 = _seed_run(
        tmp_db, pid, "specify", trace_id=trace_id, tokens_in=100, tokens_out=50, cost_usd=0.01, duration_ms=1000
    )
    complete_run(tmp_db, r1, "completed")

    # Node 2: no JSON output — tokens/cost NULL
    r2 = _seed_run(tmp_db, pid, "plan", trace_id=trace_id)
    complete_run(tmp_db, r2, "completed")

    # Node 3: valid metrics
    r3 = _seed_run(
        tmp_db, pid, "tasks", trace_id=trace_id, tokens_in=200, tokens_out=100, cost_usd=0.02, duration_ms=2000
    )
    complete_run(tmp_db, r3, "completed")

    complete_trace(tmp_db, trace_id, "completed")

    row = tmp_db.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
    assert row["status"] == "completed"
    assert row["completed_nodes"] == 3
    # SUM with NULLs: SQLite SUM ignores NULLs, so only non-null values sum
    assert row["total_tokens_in"] == 300  # 100 + NULL + 200 = 300
    assert row["total_tokens_out"] == 150
    assert pytest.approx(row["total_cost_usd"], abs=1e-6) == 0.03

    # Verify individual spans are intact
    r2_row = tmp_db.execute("SELECT * FROM pipeline_runs WHERE run_id=?", (r2,)).fetchone()
    assert r2_row["tokens_in"] is None
    assert r2_row["cost_usd"] is None


def test_concurrent_pipeline_runs_isolated_traces(tmp_db):
    """Edge case: concurrent pipeline runs have isolated traces.

    Two traces running simultaneously should not share spans or metrics.
    """
    from db import complete_run, complete_trace, get_trace_detail

    pid = _seed_platform(tmp_db)
    trace_a = _seed_trace(tmp_db, total_nodes=2)
    trace_b = _seed_trace(tmp_db, total_nodes=2)

    # Trace A spans
    ra1 = _seed_run(tmp_db, pid, "specify", trace_id=trace_a, tokens_in=100, tokens_out=50, cost_usd=0.10)
    complete_run(tmp_db, ra1, "completed")
    ra2 = _seed_run(tmp_db, pid, "plan", trace_id=trace_a, tokens_in=200, tokens_out=100, cost_usd=0.20)
    complete_run(tmp_db, ra2, "completed")

    # Trace B spans
    rb1 = _seed_run(tmp_db, pid, "specify", trace_id=trace_b, tokens_in=500, tokens_out=250, cost_usd=0.50)
    complete_run(tmp_db, rb1, "completed")
    rb2 = _seed_run(tmp_db, pid, "plan", trace_id=trace_b, tokens_in=600, tokens_out=300, cost_usd=0.60)
    complete_run(tmp_db, rb2, "completed")

    complete_trace(tmp_db, trace_a, "completed")
    complete_trace(tmp_db, trace_b, "completed")

    # Verify trace A metrics are isolated
    detail_a = get_trace_detail(tmp_db, trace_a)
    assert len(detail_a["spans"]) == 2
    assert detail_a["trace"]["total_tokens_in"] == 300
    assert pytest.approx(detail_a["trace"]["total_cost_usd"], abs=1e-6) == 0.30

    # Verify trace B metrics are isolated
    detail_b = get_trace_detail(tmp_db, trace_b)
    assert len(detail_b["spans"]) == 2
    assert detail_b["trace"]["total_tokens_in"] == 1100
    assert pytest.approx(detail_b["trace"]["total_cost_usd"], abs=1e-6) == 1.10

    # No span leaks between traces
    a_run_ids = {s["run_id"] for s in detail_a["spans"]}
    b_run_ids = {s["run_id"] for s in detail_b["spans"]}
    assert a_run_ids.isdisjoint(b_run_ids)
