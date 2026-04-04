"""Tests for observability_export.py CSV export (Epic 017, T027)."""

import csv
import io

import pytest

from observability_export import _HEADERS, export_csv


# ── helpers ──────────────────────────────────────────────────────────────


def _seed_platform(conn, platform_id="test-plat"):
    from db import upsert_platform

    upsert_platform(conn, platform_id, name=platform_id)
    return platform_id


def _seed_trace(conn, platform_id="test-plat", **kwargs):
    from db import create_trace

    return create_trace(conn, platform_id, **kwargs)


def _seed_run(conn, platform_id="test-plat", node_id="vision", **kwargs):
    from db import insert_run

    return insert_run(conn, platform_id, node_id, **kwargs)


def _seed_eval(conn, trace_id, platform_id, node_id, run_id, dimension="quality", score=7.0):
    from db import insert_eval_score

    return insert_eval_score(conn, trace_id, platform_id, None, node_id, run_id, dimension, score)


def _parse_csv(csv_str):
    reader = csv.reader(io.StringIO(csv_str))
    rows = list(reader)
    return rows[0], rows[1:]  # headers, data_rows


# ── traces export ────────────────────────────────────────────────────────


def test_export_traces_headers(tmp_db):
    _seed_platform(tmp_db)
    result = export_csv(tmp_db, "test-plat", "traces")
    headers, _ = _parse_csv(result)
    assert headers == _HEADERS["traces"]


def test_export_traces_with_data(tmp_db):
    _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db, mode="l2", total_nodes=5)
    result = export_csv(tmp_db, "test-plat", "traces")
    headers, rows = _parse_csv(result)
    assert len(rows) == 1
    row_dict = dict(zip(headers, rows[0]))
    assert row_dict["trace_id"] == trace_id
    assert row_dict["mode"] == "l2"
    assert row_dict["total_nodes"] == "5"


def test_export_traces_empty(tmp_db):
    _seed_platform(tmp_db)
    result = export_csv(tmp_db, "test-plat", "traces")
    headers, rows = _parse_csv(result)
    assert headers == _HEADERS["traces"]
    assert rows == []


# ── spans export ─────────────────────────────────────────────────────────


def test_export_spans_headers(tmp_db):
    _seed_platform(tmp_db)
    result = export_csv(tmp_db, "test-plat", "spans")
    headers, _ = _parse_csv(result)
    assert headers == _HEADERS["spans"]


def test_export_spans_with_data(tmp_db):
    _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, node_id="blueprint", trace_id=trace_id, tokens_in=100, cost_usd=0.5)
    result = export_csv(tmp_db, "test-plat", "spans")
    headers, rows = _parse_csv(result)
    assert len(rows) == 1
    row_dict = dict(zip(headers, rows[0]))
    assert row_dict["run_id"] == run_id
    assert row_dict["node_id"] == "blueprint"
    assert row_dict["trace_id"] == trace_id


# ── evals export ─────────────────────────────────────────────────────────


def test_export_evals_headers(tmp_db):
    _seed_platform(tmp_db)
    result = export_csv(tmp_db, "test-plat", "evals")
    headers, _ = _parse_csv(result)
    assert headers == _HEADERS["evals"]


def test_export_evals_with_data(tmp_db):
    _seed_platform(tmp_db)
    trace_id = _seed_trace(tmp_db)
    run_id = _seed_run(tmp_db, trace_id=trace_id)
    _seed_eval(tmp_db, trace_id, "test-plat", "vision", run_id, "quality", 8.5)
    result = export_csv(tmp_db, "test-plat", "evals")
    headers, rows = _parse_csv(result)
    assert len(rows) == 1
    row_dict = dict(zip(headers, rows[0]))
    assert row_dict["dimension"] == "quality"
    assert row_dict["score"] == "8.5"


# ── days filtering ───────────────────────────────────────────────────────


def test_export_traces_days_filter(tmp_db):
    _seed_platform(tmp_db)
    _seed_trace(tmp_db)
    # Insert an old trace manually
    tmp_db.execute(
        "INSERT INTO traces (trace_id, platform_id, mode, status, started_at) "
        "VALUES ('old1', 'test-plat', 'l1', 'completed', datetime('now', '-100 days'))"
    )
    tmp_db.commit()

    # days=90 should exclude the old trace
    result = export_csv(tmp_db, "test-plat", "traces", days=90)
    _, rows = _parse_csv(result)
    assert len(rows) == 1

    # days=200 should include both
    result = export_csv(tmp_db, "test-plat", "traces", days=200)
    _, rows = _parse_csv(result)
    assert len(rows) == 2


def test_export_spans_days_filter(tmp_db):
    _seed_platform(tmp_db)
    _seed_run(tmp_db)
    tmp_db.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, node_id, status, started_at) "
        "VALUES ('old_run', 'test-plat', 'x', 'completed', datetime('now', '-100 days'))"
    )
    tmp_db.commit()

    result = export_csv(tmp_db, "test-plat", "spans", days=90)
    _, rows = _parse_csv(result)
    assert len(rows) == 1


# ── invalid entity ───────────────────────────────────────────────────────


def test_export_invalid_entity(tmp_db):
    _seed_platform(tmp_db)
    with pytest.raises(ValueError, match="entity must be one of"):
        export_csv(tmp_db, "test-plat", "invalid")


# ── UTF-8 encoding ──────────────────────────────────────────────────────


def test_export_utf8(tmp_db):
    _seed_platform(tmp_db)
    result = export_csv(tmp_db, "test-plat", "traces")
    assert isinstance(result, str)
    result.encode("utf-8")  # should not raise


# ── platform isolation ───────────────────────────────────────────────────


def test_export_filters_by_platform(tmp_db):
    _seed_platform(tmp_db, "plat-a")
    _seed_platform(tmp_db, "plat-b")
    _seed_trace(tmp_db, "plat-a")
    _seed_trace(tmp_db, "plat-b")

    result_a = export_csv(tmp_db, "plat-a", "traces")
    _, rows_a = _parse_csv(result_a)
    assert len(rows_a) == 1
