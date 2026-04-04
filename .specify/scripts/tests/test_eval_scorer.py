"""Tests for eval_scorer.py — heuristic eval scoring across 4 dimensions."""

import json

import pytest

from eval_scorer import score_node


# ── helpers ──────────────────────────────────────────────────────────────


def _seed_platform(conn, platform_id="test-plat"):
    from db import upsert_platform

    upsert_platform(conn, platform_id, name=platform_id)
    return platform_id


def _seed_runs_with_cost(conn, platform_id, node_id, costs):
    """Insert completed runs with cost_usd for historical avg lookup."""
    from db import insert_run

    for cost in costs:
        run_id = insert_run(conn, platform_id, node_id)
        conn.execute(
            "UPDATE pipeline_runs SET status='completed', cost_usd=? WHERE run_id=?",
            (cost, run_id),
        )
    conn.commit()


def _write_artifact(tmp_path, content, name="output.md"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _find(scores, dimension):
    return next(s for s in scores if s["dimension"] == dimension)


# ── score_node integration ──────────────────────────────────────────────


def test_score_node_returns_four_dimensions(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Vision\nSome content\n")
    scores = score_node(tmp_db, "test-plat", "vision", "run-1", path)

    assert len(scores) == 4
    dims = {s["dimension"] for s in scores}
    assert dims == {"quality", "adherence_to_spec", "completeness", "cost_efficiency"}

    for s in scores:
        assert s["platform_id"] == "test-plat"
        assert s["node_id"] == "vision"
        assert s["run_id"] == "run-1"
        assert 0.0 <= s["score"] <= 10.0


def test_score_node_none_metrics_uses_defaults(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Content\n")
    scores = score_node(tmp_db, "test-plat", "vision", None, path, metrics=None)
    assert len(scores) == 4


# ── quality dimension ───────────────────────────────────────────────────


def test_quality_heuristic_normal_content(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Good output\nSome valid content.\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    q = _find(scores, "quality")

    assert q["score"] == 7.0
    meta = json.loads(q["metadata"])
    assert meta["method"] == "heuristic"


def test_quality_with_judge_score(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Output\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"judge_score": 80})
    q = _find(scores, "quality")

    assert q["score"] == 8.0
    meta = json.loads(q["metadata"])
    assert meta["method"] == "judge"
    assert meta["raw_judge_score"] == 80


def test_quality_judge_score_zero(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Output\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"judge_score": 0})
    q = _find(scores, "quality")
    assert q["score"] == 0.0


def test_quality_judge_score_100(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Output\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"judge_score": 100})
    q = _find(scores, "quality")
    assert q["score"] == 10.0


def test_quality_judge_score_invalid_falls_back_to_heuristic(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Output\nContent\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"judge_score": "invalid"})
    q = _find(scores, "quality")
    meta = json.loads(q["metadata"])
    assert meta["method"] == "heuristic"
    assert q["score"] == 7.0


def test_quality_empty_output(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    q = _find(scores, "quality")

    assert q["score"] == 1.0
    meta = json.loads(q["metadata"])
    assert meta["reason"] == "empty_output"


def test_quality_whitespace_only_is_empty(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "   \n  \n  ")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    q = _find(scores, "quality")
    assert q["score"] == 1.0


def test_quality_error_markers_reduce_score(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    content = "# Output\n[ERROR] something\nTraceback (most recent call last)\nFAILED\n"
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    q = _find(scores, "quality")

    assert q["score"] < 7.0
    meta = json.loads(q["metadata"])
    assert meta["error_markers_found"] == 3


def test_quality_many_errors_cap_penalty(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    content = "# Output\n" + "[ERROR] fail\n" * 10
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    q = _find(scores, "quality")

    # 7.0 - min(4.0, 10*1.0) = 3.0
    assert q["score"] == 3.0


def test_quality_no_output_path(tmp_db):
    _seed_platform(tmp_db)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", None)
    q = _find(scores, "quality")
    assert q["score"] == 1.0


# ── adherence_to_spec dimension ─────────────────────────────────────────


def test_adherence_all_sections_matched(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    content = "# Playing to Win\nSome text\n## Winning Aspiration\nMore text\n### Where to Play\nEven more\n"
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    a = _find(scores, "adherence_to_spec")

    assert a["score"] == 10.0
    meta = json.loads(a["metadata"])
    assert meta["matched"] == 3
    assert meta["expected"] == 3


def test_adherence_partial_match(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    content = "# Playing to Win\nOnly this section\n"
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    a = _find(scores, "adherence_to_spec")

    # 1 of 3 matched → 3.3
    assert a["score"] == pytest.approx(3.3, abs=0.1)
    meta = json.loads(a["metadata"])
    assert meta["matched"] == 1
    assert meta["expected"] == 3


def test_adherence_no_sections_matched(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    content = "# Random Heading\nNothing expected here.\n"
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    a = _find(scores, "adherence_to_spec")

    assert a["score"] == 0.0


def test_adherence_empty_output(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    a = _find(scores, "adherence_to_spec")

    assert a["score"] == 0.0
    meta = json.loads(a["metadata"])
    assert meta["reason"] == "empty_output"


def test_adherence_unknown_node_neutral_score(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Some content\n")
    scores = score_node(tmp_db, "test-plat", "unknown-node", "r1", path)
    a = _find(scores, "adherence_to_spec")

    assert a["score"] == 5.0
    meta = json.loads(a["metadata"])
    assert meta["reason"] == "no_expectations_defined"


def test_adherence_analyze_post_strips_suffix(tmp_db, tmp_path):
    """analyze-post should match as 'analyze' for section lookup."""
    _seed_platform(tmp_db)
    content = "# Consistency Check\n## Findings\nSome result\n"
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "analyze-post", "r1", path)
    a = _find(scores, "adherence_to_spec")

    # analyze has patterns with pipe alternation — each list entry is one pattern
    assert a["score"] > 0.0
    meta = json.loads(a["metadata"])
    assert meta["expected"] >= 1


# ── completeness dimension ──────────────────────────────────────────────


def test_completeness_proportional_to_lines(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    # vision expects 80 lines; 40 lines → 50% → score 5.0
    content = "\n".join(f"line {i}" for i in range(40))
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    c = _find(scores, "completeness")

    assert c["score"] == pytest.approx(5.0, abs=0.2)


def test_completeness_exceeding_expected_caps_at_10(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    # vision expects 80 lines; 200 lines → capped at 10.0
    content = "\n".join(f"line {i}" for i in range(200))
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    c = _find(scores, "completeness")

    assert c["score"] == 10.0


def test_completeness_empty_output(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    c = _find(scores, "completeness")

    # Empty file: 0 lines after content.count("\n")+1 logic, but content is ""
    # so actual_lines = 0 → score 0.0
    assert c["score"] == 0.0
    meta = json.loads(c["metadata"])
    assert meta["reason"] == "no_output"


def test_completeness_uses_metrics_output_lines(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    # File has 5 lines but metrics says 160 (2x vision expected)
    path = _write_artifact(tmp_path, "short\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"output_lines": 160})
    c = _find(scores, "completeness")
    # 160/80*10 = 20 → capped at 10.0
    assert c["score"] == 10.0


def test_completeness_unknown_node_uses_default(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    # Default expected is 80 lines; 40 lines → score ~5.0
    content = "\n".join(f"line {i}" for i in range(40))
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "custom-node", "r1", path)
    c = _find(scores, "completeness")

    assert c["score"] == pytest.approx(5.0, abs=0.2)


def test_completeness_no_output_path(tmp_db):
    _seed_platform(tmp_db)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", None)
    c = _find(scores, "completeness")
    assert c["score"] == 0.0


# ── cost_efficiency dimension ───────────────────────────────────────────


def test_cost_efficiency_no_cost_data_neutral(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Content\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)
    ce = _find(scores, "cost_efficiency")

    assert ce["score"] == 5.0
    meta = json.loads(ce["metadata"])
    assert meta["reason"] == "no_cost_data"


def test_cost_efficiency_zero_cost_neutral(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Content\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"cost_usd": 0})
    ce = _find(scores, "cost_efficiency")

    assert ce["score"] == 5.0
    meta = json.loads(ce["metadata"])
    assert meta["reason"] == "no_cost_data"


def test_cost_efficiency_no_history_neutral(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Content\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"cost_usd": 0.50})
    ce = _find(scores, "cost_efficiency")

    assert ce["score"] == 5.0
    meta = json.loads(ce["metadata"])
    assert meta["reason"] == "no_history"


def test_cost_efficiency_below_budget_high_score(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    # Seed historical runs with avg cost $1.00 → budget = $1.50
    _seed_runs_with_cost(tmp_db, "test-plat", "vision", [1.00, 1.00, 1.00])

    path = _write_artifact(tmp_path, "# Content\n")
    # Current cost $0.30 → ratio = 0.30/1.50 = 0.2 → score = 10 - 2 = 8.0
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"cost_usd": 0.30})
    ce = _find(scores, "cost_efficiency")

    assert ce["score"] == pytest.approx(8.0, abs=0.1)


def test_cost_efficiency_at_budget_low_score(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    _seed_runs_with_cost(tmp_db, "test-plat", "vision", [1.00, 1.00])

    path = _write_artifact(tmp_path, "# Content\n")
    # Current cost $1.50 = budget → ratio = 1.0 → score = 10 - 10 = 0.0
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"cost_usd": 1.50})
    ce = _find(scores, "cost_efficiency")

    assert ce["score"] == 0.0


def test_cost_efficiency_over_budget_capped_at_zero(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    _seed_runs_with_cost(tmp_db, "test-plat", "vision", [1.00])

    path = _write_artifact(tmp_path, "# Content\n")
    # Cost $5.00 way over budget $1.50 → capped at 0.0
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"cost_usd": 5.00})
    ce = _find(scores, "cost_efficiency")

    assert ce["score"] == 0.0


def test_cost_efficiency_negative_cost_neutral(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Content\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={"cost_usd": -1.0})
    ce = _find(scores, "cost_efficiency")
    assert ce["score"] == 5.0


# ── edge cases ──────────────────────────────────────────────────────────


def test_missing_output_file_scores_low(tmp_db):
    _seed_platform(tmp_db)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", "/nonexistent/file.md")

    q = _find(scores, "quality")
    a = _find(scores, "adherence_to_spec")
    c = _find(scores, "completeness")

    assert q["score"] == 1.0  # empty → 1.0
    assert a["score"] == 0.0  # empty → 0.0
    assert c["score"] == 0.0  # no lines → 0.0


def test_scores_clamped_to_0_10_range(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Content\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)

    for s in scores:
        assert 0.0 <= s["score"] <= 10.0


def test_metadata_is_valid_json_or_none(tmp_db, tmp_path):
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "# Content\n")
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)

    for s in scores:
        if s["metadata"] is not None:
            parsed = json.loads(s["metadata"])
            assert isinstance(parsed, dict)


def test_missing_metrics_neutral_defaults(tmp_db, tmp_path):
    """All dimensions produce reasonable scores with empty metrics dict."""
    _seed_platform(tmp_db)
    content = "\n".join(f"line {i}" for i in range(80))
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path, metrics={})

    q = _find(scores, "quality")
    ce = _find(scores, "cost_efficiency")

    assert q["score"] == 7.0  # heuristic default, no errors
    assert ce["score"] == 5.0  # no cost → neutral


# ── T029 edge cases: eval on empty/minimal artifacts ──────────────────


def test_empty_artifact_scores_low_completeness(tmp_db, tmp_path):
    """Edge case: eval on empty artifact scores low on completeness.

    Spec: 'evals de nodes que produziram artefatos vazios ou minimos
    devem registrar score baixo em completude e sinalizar no dashboard.'
    """
    _seed_platform(tmp_db)
    path = _write_artifact(tmp_path, "")  # empty file
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)

    c = _find(scores, "completeness")
    q = _find(scores, "quality")
    a = _find(scores, "adherence_to_spec")

    # All dimensions should signal poor output
    assert c["score"] == 0.0  # empty → 0 lines / expected = 0
    assert q["score"] == 1.0  # empty → quality 1.0
    assert a["score"] == 0.0  # empty → no sections matched


def test_minimal_artifact_scores_low_completeness(tmp_db, tmp_path):
    """Edge case: minimal artifact (few lines) scores proportionally low.

    A 5-line output for a node expecting 80 lines should score ~0.6.
    """
    _seed_platform(tmp_db)
    content = "# Vision\nShort.\nVery short.\nMinimal.\nDone.\n"
    path = _write_artifact(tmp_path, content)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", path)

    c = _find(scores, "completeness")
    meta = json.loads(c["metadata"])

    # 6 lines (5 newlines + 1) / 80 expected = 0.075 * 10 = 0.75
    assert c["score"] < 2.0  # significantly below threshold
    assert meta["actual_lines"] < 10
    assert meta["expected_lines"] == 80


def test_no_output_path_all_dimensions_score_low(tmp_db):
    """Edge case: no output path at all — all content-based dimensions score low."""
    _seed_platform(tmp_db)
    scores = score_node(tmp_db, "test-plat", "vision", "r1", None)

    c = _find(scores, "completeness")
    q = _find(scores, "quality")
    a = _find(scores, "adherence_to_spec")

    assert c["score"] == 0.0
    assert q["score"] == 1.0
    assert a["score"] == 0.0
    # cost_efficiency is independent of output content
    ce = _find(scores, "cost_efficiency")
    assert ce["score"] == 5.0  # neutral (no cost data)
