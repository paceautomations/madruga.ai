"""Tests for db.py seed_from_filesystem function."""


def test_seed_from_filesystem(tmp_db, sample_platform_dir):
    from db import seed_from_filesystem, get_platform, get_pipeline_nodes, get_epics

    result = seed_from_filesystem(tmp_db, "test-plat", sample_platform_dir)
    assert result["status"] == "ok"
    assert result["nodes"] == 3  # 3 nodes in sample platform.yaml

    p = get_platform(tmp_db, "test-plat")
    assert p is not None
    assert p["name"] == "test-plat"

    nodes = get_pipeline_nodes(tmp_db, "test-plat")
    assert len(nodes) == 3

    # platform.yaml exists so platform-new is done
    done_nodes = [n for n in nodes if n["status"] == "done"]
    pending_nodes = [n for n in nodes if n["status"] == "pending"]
    assert len(done_nodes) >= 1  # at least platform-new + vision
    assert len(pending_nodes) >= 1  # solution-overview has no file

    epics = get_epics(tmp_db, "test-plat")
    assert len(epics) == 1
    assert epics[0]["epic_id"] == "001-test-epic"


def test_seed_idempotent(tmp_db, sample_platform_dir):
    from db import seed_from_filesystem, get_pipeline_nodes

    seed_from_filesystem(tmp_db, "test-plat", sample_platform_dir)
    seed_from_filesystem(tmp_db, "test-plat", sample_platform_dir)

    nodes = get_pipeline_nodes(tmp_db, "test-plat")
    assert len(nodes) == 3  # still 3, not 6

    count = tmp_db.execute(
        "SELECT COUNT(*) FROM platforms WHERE platform_id='test-plat'"
    ).fetchone()[0]
    assert count == 1


def test_seed_missing_platform_yaml(tmp_db, tmp_path):
    from db import seed_from_filesystem

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = seed_from_filesystem(tmp_db, "missing", empty_dir)
    assert result["status"] == "skipped"
