"""Tests for post-save.py CLI wrapper."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_conn, get_epic_nodes, get_pipeline_nodes, migrate


@pytest.fixture
def setup_platform(tmp_path):
    """Create a minimal platform structure for testing."""
    db_path = tmp_path / ".pipeline" / "madruga.db"
    db_path.parent.mkdir(parents=True)

    # Create platform dir with platform.yaml (metadata only)
    pdir = tmp_path / "platforms" / "test-plat"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text("name: test-plat\ntitle: Test\nlifecycle: design\n")

    # Create pipeline.yaml and patch config.PIPELINE_YAML
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(
        "nodes:\n"
        "  - id: vision\n"
        "    outputs: ['business/vision.md']\n"
        "    depends: []\n"
        "    gate: human\n"
        "epic_cycle:\n"
        "  nodes:\n"
        "    - id: specify\n"
        "      skill: speckit.specify\n"
        "      outputs: ['{epic}/spec.md']\n"
        "      depends: []\n"
        "      gate: human\n"
        "    - id: plan\n"
        "      skill: speckit.plan\n"
        "      outputs: ['{epic}/plan.md']\n"
        "      depends: [specify]\n"
        "      gate: human\n"
        "    - id: implement\n"
        "      skill: speckit.implement\n"
        "      outputs: ['{epic}/code']\n"
        "      depends: [plan]\n"
        "      gate: auto\n"
        "    - id: clarify\n"
        "      skill: speckit.clarify\n"
        "      outputs: ['{epic}/spec.md']\n"
        "      depends: [specify]\n"
        "      gate: human\n"
        "      optional: true\n"
    )

    # Create an artifact
    (pdir / "business").mkdir()
    (pdir / "business" / "vision.md").write_text(
        "# Vision\n\nTest content here. This is the vision document for the test platform.\n"
    )

    # Create epic structure
    epic_dir = pdir / "epics" / "001-test-epic"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text("---\ntitle: Test Epic\n---\n# Test Epic\n")
    (epic_dir / "spec.md").write_text(
        "# Spec\n\nTest spec content for the epic. This file has enough content to pass validation.\n"
    )

    # Create migrations dir
    migrations_dir = tmp_path / ".pipeline" / "migrations"
    migrations_dir.mkdir()

    # Copy real migration files
    real_migrations = Path(__file__).parent.parent.parent.parent / ".pipeline" / "migrations"
    for f in sorted(real_migrations.glob("*.sql")):
        (migrations_dir / f.name).write_text(f.read_text())

    conn = get_conn(db_path)
    migrate(conn, migrations_dir)
    conn.close()

    # Patch is active for the entire test — caller uses `with` or fixture scope
    with patch("config.PIPELINE_YAML", pipeline_path):
        yield tmp_path, db_path


def test_record_save_l1(setup_platform):
    """Test L1 save recording."""
    tmp_path, db_path = setup_platform
    sys.path.insert(0, str(Path(__file__).parent.parent))

    # Import and patch REPO_ROOT + DB_PATH
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        result = post_save.record_save(
            platform="test-plat",
            node="vision",
            skill="madruga:vision",
            artifact="business/vision.md",
        )
        assert result["status"] == "ok"
        assert result["node"] == "vision"
        assert result["hash"].startswith("sha256:")

        # Verify DB state
        conn = get_conn(db_path)
        nodes = get_pipeline_nodes(conn, "test-plat")
        vision = [n for n in nodes if n["node_id"] == "vision"]
        assert len(vision) == 1
        assert vision[0]["status"] == "done"
        assert vision[0]["output_hash"] is not None
        assert vision[0]["completed_at"] is not None

        # Verify provenance
        prov = conn.execute(
            "SELECT * FROM artifact_provenance WHERE platform_id='test-plat' AND file_path='business/vision.md'"
        ).fetchone()
        assert prov is not None
        assert dict(prov)["generated_by"] == "madruga:vision"

        # Verify event
        events = conn.execute(
            "SELECT * FROM events WHERE platform_id='test-plat' AND entity_id='vision' AND action='completed'"
        ).fetchall()
        assert len(events) >= 1

        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_record_save_l2_epic(setup_platform):
    """Test L2 epic node save recording."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        # First seed to create the platform and epic
        from db import get_conn as gc, upsert_epic, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        upsert_epic(conn, "test-plat", "001-test-epic", title="Test Epic")
        conn.close()

        result = post_save.record_save(
            platform="test-plat",
            node="specify",
            skill="speckit.specify",
            artifact="epics/001-test-epic/spec.md",
            epic="001-test-epic",
        )
        assert result["status"] == "ok"
        assert result["epic"] == "001-test-epic"

        # Verify epic node
        conn = gc(db_path)
        enodes = get_epic_nodes(conn, "test-plat", "001-test-epic")
        specify = [n for n in enodes if n["node_id"] == "specify"]
        assert len(specify) == 1
        assert specify[0]["status"] == "done"
        assert specify[0]["completed_at"] is not None
        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_reseed(setup_platform):
    """Test reseed functionality."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        result = post_save.reseed("test-plat")
        assert result["status"] == "ok"
        assert result["nodes"] >= 1

        # Verify platform was created
        conn = get_conn(db_path)
        plat = conn.execute("SELECT * FROM platforms WHERE platform_id='test-plat'").fetchone()
        assert plat is not None
        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_inject_ship_fields_delivered_at_idempotent(setup_platform):
    """_inject_ship_fields is idempotent for delivered_at."""
    tmp_path, db_path = setup_platform
    import post_save

    original_repo = post_save.REPO_ROOT
    post_save.REPO_ROOT = tmp_path

    try:
        post_save._inject_ship_fields("test-plat", "001-test-epic", "2026-03-30")
        pitch = tmp_path / "platforms" / "test-plat" / "epics" / "001-test-epic" / "pitch.md"
        content = pitch.read_text()
        assert "delivered_at: 2026-03-30" in content
        assert "status: shipped" in content
        # Verify idempotent — second call doesn't duplicate
        post_save._inject_ship_fields("test-plat", "001-test-epic", "2026-03-31")
        content2 = pitch.read_text()
        assert content2.count("delivered_at:") == 1
        assert "2026-03-30" in content2  # original date preserved
        assert content2.count("status:") == 1
    finally:
        post_save.REPO_ROOT = original_repo


def test_ship_transition_sets_delivered_at(setup_platform):
    """When all required epic nodes complete, delivered_at is set in DB and pitch.md."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        from db import get_conn as gc, get_epics, upsert_epic, upsert_epic_node, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        upsert_epic(conn, "test-plat", "001-test-epic", title="Test Epic")
        # Pre-complete 2 of 3 required nodes (specify, plan); implement is pending
        upsert_epic_node(conn, "test-plat", "001-test-epic", "specify", "done")
        upsert_epic_node(conn, "test-plat", "001-test-epic", "plan", "done")
        upsert_epic_node(conn, "test-plat", "001-test-epic", "implement", "pending")
        conn.close()

        # Create the plan.md artifact (implement needs it)
        plan_path = tmp_path / "platforms" / "test-plat" / "epics" / "001-test-epic" / "plan.md"
        plan_path.write_text("# Plan\nTest plan.")

        # Complete last required node — should trigger ship
        result = post_save.record_save(
            platform="test-plat",
            node="implement",
            skill="speckit.implement",
            artifact="epics/001-test-epic/spec.md",
            epic="001-test-epic",
        )
        assert result["status"] == "ok"

        conn = gc(db_path)
        epics = get_epics(conn, "test-plat")
        epic = [e for e in epics if e["epic_id"] == "001-test-epic"][0]
        assert epic["status"] == "shipped"
        assert epic["delivered_at"] is not None

        # Verify pitch.md was updated
        pitch = tmp_path / "platforms" / "test-plat" / "epics" / "001-test-epic" / "pitch.md"
        content = pitch.read_text()
        assert "status: shipped" in content
        assert "delivered_at:" in content
        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_partial_nodes_do_not_ship(setup_platform):
    """Epic with only some required nodes done stays in_progress, not shipped."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        from db import get_conn as gc, get_epics, upsert_epic, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        upsert_epic(conn, "test-plat", "001-test-epic", title="Test Epic")
        conn.close()

        # Complete only specify — plan and implement still missing
        result = post_save.record_save(
            platform="test-plat",
            node="specify",
            skill="speckit.specify",
            artifact="epics/001-test-epic/spec.md",
            epic="001-test-epic",
        )
        assert result["status"] == "ok"

        conn = gc(db_path)
        epics = get_epics(conn, "test-plat")
        epic = [e for e in epics if e["epic_id"] == "001-test-epic"][0]
        # Must NOT be shipped — only 1 of 3 required nodes done
        assert epic["status"] == "in_progress"
        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_reseed_missing_platform(setup_platform):
    """Test reseed with non-existent platform."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        result = post_save.reseed("nonexistent")
        assert result["status"] == "error"
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_epic_shipped_with_skipped_nodes(setup_platform):
    """Epic with required nodes done + optional skipped transitions to shipped."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        from db import get_conn as gc, get_epics, upsert_epic, upsert_epic_node, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        upsert_epic(conn, "test-plat", "001-test-epic", title="Test Epic")
        # Required nodes: specify (done), plan (done), implement (pending)
        # Optional node: clarify (skipped)
        upsert_epic_node(conn, "test-plat", "001-test-epic", "specify", "done")
        upsert_epic_node(conn, "test-plat", "001-test-epic", "plan", "done")
        upsert_epic_node(conn, "test-plat", "001-test-epic", "clarify", "skipped")
        upsert_epic_node(conn, "test-plat", "001-test-epic", "implement", "pending")
        conn.close()

        # Complete last required node — should trigger ship
        result = post_save.record_save(
            platform="test-plat",
            node="implement",
            skill="speckit.implement",
            artifact="epics/001-test-epic/spec.md",
            epic="001-test-epic",
        )
        assert result["status"] == "ok"

        conn = gc(db_path)
        epics = get_epics(conn, "test-plat")
        epic = [e for e in epics if e["epic_id"] == "001-test-epic"][0]
        assert epic["status"] == "shipped"
        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_inject_ship_fields_updates_status(setup_platform):
    """_inject_ship_fields writes both status: shipped and delivered_at."""
    tmp_path, db_path = setup_platform
    import post_save

    original_repo = post_save.REPO_ROOT
    post_save.REPO_ROOT = tmp_path

    try:
        post_save._inject_ship_fields("test-plat", "001-test-epic", "2026-04-01")
        pitch = tmp_path / "platforms" / "test-plat" / "epics" / "001-test-epic" / "pitch.md"
        content = pitch.read_text()
        assert "status: shipped" in content
        assert "delivered_at: 2026-04-01" in content
        # Verify original "title: Test Epic" is preserved
        assert "title: Test Epic" in content
    finally:
        post_save.REPO_ROOT = original_repo


def test_record_save_bumps_timestamp_when_hash_unchanged(setup_platform):
    """record_save bumps completed_at even when hash is unchanged (DAG ordering)."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        # First save — records the node as done
        result1 = post_save.record_save(
            platform="test-plat",
            node="vision",
            skill="madruga:vision",
            artifact="business/vision.md",
        )
        assert result1["status"] == "ok"

        # Get the original completed_at
        conn = get_conn(db_path)
        nodes = get_pipeline_nodes(conn, "test-plat")
        original_ts = next(n for n in nodes if n["node_id"] == "vision")["completed_at"]
        conn.close()

        # Second save — same file, same hash, mocked future timestamp
        from unittest.mock import patch
        from datetime import datetime as _dt, timezone as _tz

        future = _dt(2099, 1, 1, tzinfo=_tz.utc)
        with patch("post_save.datetime") as mock_dt:
            mock_dt.now.return_value = future
            mock_dt.side_effect = lambda *a, **kw: _dt(*a, **kw)
            post_save.record_save(
                platform="test-plat",
                node="vision",
                skill="madruga:vision",
                artifact="business/vision.md",
            )

        # completed_at SHOULD have been bumped (prevents stale after dep re-registration)
        conn = get_conn(db_path)
        nodes = get_pipeline_nodes(conn, "test-plat")
        new_ts = next(n for n in nodes if n["node_id"] == "vision")["completed_at"]
        conn.close()

        assert new_ts > original_ts, f"completed_at not bumped: {original_ts} → {new_ts}"
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_register_only_skips_already_done_node(setup_platform):
    """register_only=True does NOT bump completed_at on already-done L1 nodes."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        # First save — skill execution, records the node as done
        result1 = post_save.record_save(
            platform="test-plat",
            node="vision",
            skill="madruga:vision",
            artifact="business/vision.md",
        )
        assert result1["status"] == "ok"

        conn = get_conn(db_path)
        nodes = get_pipeline_nodes(conn, "test-plat")
        original_ts = next(n for n in nodes if n["node_id"] == "vision")["completed_at"]
        conn.close()

        # Second save — register_only=True, mocked future timestamp
        from datetime import datetime as _dt
        from datetime import timezone as _tz
        from unittest.mock import patch

        future = _dt(2099, 1, 1, tzinfo=_tz.utc)
        with patch("post_save.datetime") as mock_dt:
            mock_dt.now.return_value = future
            mock_dt.side_effect = lambda *a, **kw: _dt(*a, **kw)
            result2 = post_save.record_save(
                platform="test-plat",
                node="vision",
                skill="madruga:vision",
                artifact="business/vision.md",
                register_only=True,
            )

        assert result2["action"] == "skipped_register_only"

        # completed_at must NOT have been bumped
        conn = get_conn(db_path)
        nodes = get_pipeline_nodes(conn, "test-plat")
        new_ts = next(n for n in nodes if n["node_id"] == "vision")["completed_at"]
        conn.close()

        assert new_ts == original_ts, f"completed_at wrongly bumped: {original_ts} → {new_ts}"
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_register_only_allows_first_completion(setup_platform):
    """register_only=True still records a node that was never done."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        result = post_save.record_save(
            platform="test-plat",
            node="vision",
            skill="madruga:vision",
            artifact="business/vision.md",
            register_only=True,
        )
        assert result["status"] == "ok"
        assert result.get("action") != "skipped_register_only"

        conn = get_conn(db_path)
        nodes = get_pipeline_nodes(conn, "test-plat")
        node = next(n for n in nodes if n["node_id"] == "vision")
        assert node["status"] == "done"
        assert node["completed_at"] is not None
        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_backfill_epic_predecessors(setup_platform):
    """Backfill fills missing nodes whose artifacts exist on disk."""
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        from db import get_conn as gc, get_epic_nodes, upsert_epic, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        upsert_epic(conn, "test-plat", "001-test-epic", title="Test Epic")
        conn.close()

        # Create plan.md on disk (specify's spec.md already exists from fixture)
        plan_path = tmp_path / "platforms" / "test-plat" / "epics" / "001-test-epic" / "plan.md"
        plan_path.write_text("# Plan\n\nTest plan content for the epic. This file validates backfill.\n")

        # Record only implement — backfill should fill specify + plan from disk
        code_path = tmp_path / "platforms" / "test-plat" / "epics" / "001-test-epic" / "code"
        code_path.write_text(
            "# Code\n\nImplementation of the feature. Contains enough content to pass validation check.\n"
        )
        result = post_save.record_save(
            platform="test-plat",
            node="implement",
            skill="speckit.implement",
            artifact="epics/001-test-epic/code",
            epic="001-test-epic",
        )
        assert result["status"] == "ok"

        conn = gc(db_path)
        nodes = get_epic_nodes(conn, "test-plat", "001-test-epic")
        node_map = {n["node_id"]: n for n in nodes}
        conn.close()

        # specify and plan should have been backfilled from disk
        assert "specify" in node_map
        assert node_map["specify"]["status"] == "done"
        assert node_map["specify"]["completed_by"].startswith("seed:")
        assert "plan" in node_map
        assert node_map["plan"]["status"] == "done"
        assert node_map["plan"]["completed_by"].startswith("seed:")
        # implement was recorded directly
        assert node_map["implement"]["completed_by"] == "speckit.implement"
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_compute_epic_status_never_regresses_shipped(setup_platform):
    """compute_epic_status never downgrades shipped to a lesser status."""
    tmp_path, db_path = setup_platform
    import db_core as db_mod

    original_db = db_mod.DB_PATH
    db_mod.DB_PATH = db_path

    try:
        from db import compute_epic_status, get_conn as gc, upsert_epic, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        upsert_epic(conn, "test-plat", "001-test-epic", title="Test", status="shipped")

        # No nodes at all — but epic is already shipped
        new_status, delivered = compute_epic_status(conn, "test-plat", "001-test-epic", {"specify", "plan"}, "shipped")
        assert new_status == "shipped"
        assert delivered is None  # no new delivered_at needed
        conn.close()
    finally:
        db_mod.DB_PATH = original_db


def test_detect_from_path_disambiguates_shared_output(setup_platform):
    """detect_from_path picks first unfinished node when multiple match same file.

    The fixture has both 'specify' and 'clarify' outputting {epic}/spec.md.
    When specify is already done, detect_from_path should return 'clarify'.
    When neither is done, it should return 'specify' (first in DAG order).
    """
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        spec_path = str(tmp_path / "platforms" / "test-plat" / "epics" / "001-test-epic" / "spec.md")

        # Case 1: neither done — should return 'specify' (first in DAG order)
        result = post_save.detect_from_path(spec_path)
        assert result is not None
        assert result["node"] == "specify", f"Expected 'specify' but got '{result['node']}'"

        # Case 2: mark specify as done — should return 'clarify'
        from db import get_conn as gc, upsert_epic, upsert_epic_node, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        upsert_epic(conn, "test-plat", "001-test-epic", title="Test Epic")
        upsert_epic_node(conn, "test-plat", "001-test-epic", "specify", "done")
        conn.close()

        result2 = post_save.detect_from_path(spec_path)
        assert result2 is not None
        assert result2["node"] == "clarify", f"Expected 'clarify' but got '{result2['node']}'"
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_is_valid_output_rejects_raw_claude_json(tmp_path):
    """_is_valid_output rejects raw claude -p --output-format json output."""
    from db import _is_valid_output

    # Raw claude JSON metadata — not real content
    raw_json = tmp_path / "implement-report.md"
    raw_json.write_text(
        '{"type":"result","subtype":"success","is_error":false,"duration_ms":442636,'
        '"result":"","stop_reason":"end_turn","session_id":"abc123"}'
    )
    assert _is_valid_output(raw_json) is False


def test_is_valid_output_accepts_valid_markdown(tmp_path):
    """_is_valid_output accepts a valid markdown file with heading."""
    from db import _is_valid_output

    valid_md = tmp_path / "spec.md"
    valid_md.write_text("# Feature Specification\n\nThis is a valid spec file with content.\n")
    assert _is_valid_output(valid_md) is True


def test_is_valid_output_rejects_tiny_file(tmp_path):
    """_is_valid_output rejects files under 50 bytes."""
    from db import _is_valid_output

    tiny = tmp_path / "tiny.md"
    tiny.write_text("# Hi\n")
    assert _is_valid_output(tiny) is False


def test_is_valid_output_rejects_md_without_heading(tmp_path):
    """_is_valid_output rejects .md files without any markdown heading."""
    from db import _is_valid_output

    no_heading = tmp_path / "bad.md"
    no_heading.write_text("This is just plain text without any heading markers at all, long enough to pass size check.")
    assert _is_valid_output(no_heading) is False


# ══════════════════════════════════════
# get_commits_paginated (T027)
# ══════════════════════════════════════


def _seed_commits(db_path):
    """Insert 5 test commits (3 epic, 2 ad-hoc) across 2 platforms. Returns the connection."""
    from db_pipeline import insert_commit

    conn = get_conn(db_path)
    migrate(conn)
    insert_commit(
        conn,
        "aaa1111",
        "feat: add login",
        "Alice",
        "plat-a",
        "012-auth",
        "hook",
        "2026-04-01T10:00:00Z",
        '["src/login.py"]',
    )
    insert_commit(
        conn,
        "bbb2222",
        "fix: password hash",
        "Bob",
        "plat-a",
        "012-auth",
        "hook",
        "2026-04-02T11:00:00Z",
        '["src/auth.py"]',
    )
    insert_commit(
        conn,
        "ccc3333",
        "feat: signup flow",
        "Alice",
        "plat-b",
        "015-signup",
        "backfill",
        "2026-04-03T09:00:00Z",
        '["src/signup.py", "tests/test_signup.py"]',
    )
    insert_commit(
        conn, "ddd4444", "chore: update deps", "Charlie", "plat-a", None, "hook", "2026-04-04T08:00:00Z", "[]"
    )
    insert_commit(
        conn, "eee5555", "fix: typo in readme", "Bob", "plat-b", None, "hook", "2026-04-05T07:00:00Z", '["README.md"]'
    )
    conn.commit()
    return conn


def test_get_commits_paginated_no_filters(setup_platform):
    """get_commits_paginated returns all commits ordered by committed_at DESC."""
    from db_pipeline import get_commits_paginated

    _tmp_path, db_path = setup_platform
    conn = _seed_commits(db_path)

    commits, total = get_commits_paginated(conn)
    assert total == 5
    assert len(commits) == 5
    # Ordered DESC by committed_at
    dates = [c["committed_at"] for c in commits]
    assert dates == sorted(dates, reverse=True)
    # files_json parsed into files list
    signup = next(c for c in commits if c["sha"] == "ccc3333")
    assert signup["files"] == ["src/signup.py", "tests/test_signup.py"]
    conn.close()


def test_get_commits_paginated_platform_filter(setup_platform):
    """get_commits_paginated filters by platform_id."""
    from db_pipeline import get_commits_paginated

    _tmp_path, db_path = setup_platform
    conn = _seed_commits(db_path)

    commits, total = get_commits_paginated(conn, platform_id="plat-a")
    assert total == 3
    assert all(c["platform_id"] == "plat-a" for c in commits)
    conn.close()


def test_get_commits_paginated_commit_type(setup_platform):
    """get_commits_paginated filters by commit_type (epic vs adhoc)."""
    from db_pipeline import get_commits_paginated

    _tmp_path, db_path = setup_platform
    conn = _seed_commits(db_path)

    epic_commits, epic_total = get_commits_paginated(conn, commit_type="epic")
    assert epic_total == 3
    assert all(c["epic_id"] is not None for c in epic_commits)

    adhoc_commits, adhoc_total = get_commits_paginated(conn, commit_type="adhoc")
    assert adhoc_total == 2
    assert all(c["epic_id"] is None for c in adhoc_commits)
    conn.close()


def test_get_commits_paginated_date_range(setup_platform):
    """get_commits_paginated filters by date_from and date_to."""
    from db_pipeline import get_commits_paginated

    _tmp_path, db_path = setup_platform
    conn = _seed_commits(db_path)

    commits, total = get_commits_paginated(conn, date_from="2026-04-03", date_to="2026-04-04")
    assert total == 2
    conn.close()


def test_get_commits_paginated_pagination(setup_platform):
    """get_commits_paginated respects limit and offset."""
    from db_pipeline import get_commits_paginated

    _tmp_path, db_path = setup_platform
    conn = _seed_commits(db_path)

    page1, total = get_commits_paginated(conn, limit=2, offset=0)
    assert total == 5
    assert len(page1) == 2

    page2, _ = get_commits_paginated(conn, limit=2, offset=2)
    assert len(page2) == 2
    # No overlap
    assert {c["sha"] for c in page1}.isdisjoint({c["sha"] for c in page2})
    conn.close()


# ══════════════════════════════════════
# reseed commit sync (T041)
# ══════════════════════════════════════


def test_reseed_commit_sync_restores_deleted(setup_platform):
    """Reseed restores a deleted commit from git history.

    Scenario: 3 commits exist in both git and DB. One is deleted from DB.
    After reseed, all 3 must be present again (sync_commits fills gaps).
    """
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        from db_pipeline import insert_commit

        conn = get_conn(db_path)
        migrate(conn)

        # Step 1: Insert 3 commits (simulating hook captures)
        commits_data = [
            (
                "aaa1111",
                "feat: add widget",
                "Alice",
                "test-plat",
                "001-test-epic",
                "hook",
                "2026-04-01T10:00:00Z",
                '["src/widget.py"]',
            ),
            (
                "bbb2222",
                "fix: widget border",
                "Bob",
                "test-plat",
                "001-test-epic",
                "hook",
                "2026-04-02T11:00:00Z",
                '["src/widget.py"]',
            ),
            (
                "ccc3333",
                "chore: update config",
                "Alice",
                "test-plat",
                None,
                "hook",
                "2026-04-03T09:00:00Z",
                '["config.yaml"]',
            ),
        ]
        for c in commits_data:
            insert_commit(conn, *c)
        conn.commit()

        # Verify all 3 present
        count_before = conn.execute("SELECT COUNT(*) FROM commits WHERE platform_id='test-plat'").fetchone()[0]
        assert count_before == 3

        # Step 2: Delete one commit (simulate gap — hook missed it or DB corruption)
        conn.execute("DELETE FROM commits WHERE sha='bbb2222'")
        conn.commit()
        count_after_delete = conn.execute("SELECT COUNT(*) FROM commits WHERE platform_id='test-plat'").fetchone()[0]
        assert count_after_delete == 2
        conn.close()

        # Step 3: Mock git log to return all 3 commits (simulating real git history)
        # sync_commits calls git log to discover commits, then INSERT OR IGNORE each
        git_log_output = (
            "aaa1111\n"
            "feat: add widget\n"
            "Alice\n"
            "2026-04-01T10:00:00+00:00\n"
            "\n"
            "bbb2222\n"
            "fix: widget border\n"
            "Bob\n"
            "2026-04-02T11:00:00+00:00\n"
            "\n"
            "ccc3333\n"
            "chore: update config\n"
            "Alice\n"
            "2026-04-03T09:00:00+00:00\n"
        )

        # git diff-tree returns file paths per commit
        def mock_subprocess_run(cmd, **kwargs):
            """Mock subprocess.run for git commands used by sync_commits."""
            from unittest.mock import MagicMock

            result = MagicMock()
            result.returncode = 0
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd

            if "git log" in cmd_str and "--format=" in cmd_str:
                result.stdout = git_log_output
            elif "git diff-tree" in cmd_str:
                # Return file list for each SHA
                sha = cmd[-1] if isinstance(cmd, list) else cmd.split()[-1]
                file_map = {
                    "aaa1111": "src/widget.py\n",
                    "bbb2222": "src/widget.py\n",
                    "ccc3333": "config.yaml\n",
                }
                result.stdout = file_map.get(sha, "")
            elif "git branch" in cmd_str:
                result.stdout = "main\n"
            else:
                result.stdout = ""
            return result

        with patch("post_save.subprocess.run", side_effect=mock_subprocess_run):
            result = post_save.reseed("test-plat")
            assert result["status"] == "ok"

        # Step 4: Verify all 3 commits are present again
        conn = get_conn(db_path)
        count_after_reseed = conn.execute("SELECT COUNT(*) FROM commits WHERE platform_id='test-plat'").fetchone()[0]
        assert count_after_reseed == 3, f"Expected 3 commits after reseed, got {count_after_reseed}"

        # Verify the deleted commit was restored
        restored = conn.execute("SELECT * FROM commits WHERE sha='bbb2222'").fetchone()
        assert restored is not None, "Commit bbb2222 was not restored by reseed"
        assert dict(restored)["message"] == "fix: widget border"
        assert dict(restored)["author"] == "Bob"
        assert dict(restored)["platform_id"] == "test-plat"
        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


# ══════════════════════════════════════
# reseed commit sync idempotency (T042)
# ══════════════════════════════════════


def test_reseed_commit_sync_idempotent(setup_platform):
    """Reseed with all commits already present creates no duplicates and no errors.

    Scenario: 3 commits exist in both git and DB. Reseed runs twice.
    After each run, the count remains exactly 3 — INSERT OR IGNORE prevents dupes.
    """
    tmp_path, db_path = setup_platform
    import post_save
    import db_core as db_mod

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        from db_pipeline import insert_commit

        conn = get_conn(db_path)
        migrate(conn)

        # Pre-populate DB with 3 commits (all already present before reseed)
        commits_data = [
            (
                "aaa1111",
                "feat: add widget",
                "Alice",
                "test-plat",
                "001-test-epic",
                "hook",
                "2026-04-01T10:00:00Z",
                '["src/widget.py"]',
            ),
            (
                "bbb2222",
                "fix: widget border",
                "Bob",
                "test-plat",
                "001-test-epic",
                "hook",
                "2026-04-02T11:00:00Z",
                '["src/widget.py"]',
            ),
            (
                "ccc3333",
                "chore: update config",
                "Alice",
                "test-plat",
                None,
                "hook",
                "2026-04-03T09:00:00Z",
                '["config.yaml"]',
            ),
        ]
        for c in commits_data:
            insert_commit(conn, *c)
        conn.commit()

        count_before = conn.execute("SELECT COUNT(*) FROM commits WHERE platform_id='test-plat'").fetchone()[0]
        assert count_before == 3
        conn.close()

        # Mock git log returning the same 3 commits that are already in the DB
        git_log_output = (
            "aaa1111\n"
            "feat: add widget\n"
            "Alice\n"
            "2026-04-01T10:00:00+00:00\n"
            "\n"
            "bbb2222\n"
            "fix: widget border\n"
            "Bob\n"
            "2026-04-02T11:00:00+00:00\n"
            "\n"
            "ccc3333\n"
            "chore: update config\n"
            "Alice\n"
            "2026-04-03T09:00:00+00:00\n"
        )

        def mock_subprocess_run(cmd, **kwargs):
            """Mock subprocess.run for git commands used by sync_commits."""
            from unittest.mock import MagicMock

            result = MagicMock()
            result.returncode = 0
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd

            if "git log" in cmd_str and "--format=" in cmd_str:
                result.stdout = git_log_output
            elif "git diff-tree" in cmd_str:
                sha = cmd[-1] if isinstance(cmd, list) else cmd.split()[-1]
                file_map = {
                    "aaa1111": "src/widget.py\n",
                    "bbb2222": "src/widget.py\n",
                    "ccc3333": "config.yaml\n",
                }
                result.stdout = file_map.get(sha, "")
            elif "git branch" in cmd_str:
                result.stdout = "main\n"
            else:
                result.stdout = ""
            return result

        # First reseed — all commits already present, should be a no-op for commits
        with patch("post_save.subprocess.run", side_effect=mock_subprocess_run):
            result1 = post_save.reseed("test-plat")
            assert result1["status"] == "ok"

        conn = get_conn(db_path)
        count_after_first = conn.execute("SELECT COUNT(*) FROM commits WHERE platform_id='test-plat'").fetchone()[0]
        assert count_after_first == 3, f"Expected 3 after first reseed, got {count_after_first}"
        conn.close()

        # Second reseed — verify idempotency holds on repeated runs
        with patch("post_save.subprocess.run", side_effect=mock_subprocess_run):
            result2 = post_save.reseed("test-plat")
            assert result2["status"] == "ok"

        conn = get_conn(db_path)
        count_after_second = conn.execute("SELECT COUNT(*) FROM commits WHERE platform_id='test-plat'").fetchone()[0]
        assert count_after_second == 3, f"Expected 3 after second reseed, got {count_after_second}"

        # Verify original data integrity is preserved (no field corruption)
        row = conn.execute("SELECT * FROM commits WHERE sha='aaa1111'").fetchone()
        assert row is not None
        d = dict(row)
        assert d["message"] == "feat: add widget"
        assert d["author"] == "Alice"
        assert d["source"] == "hook"  # original source preserved, not overwritten to 'reseed'
        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


# ---------------------------------------------------------------------------
# MADRUGA_PHASE_CTX guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "node",
    ["implement", "analyze-post", "judge", "reconcile", "qa", "roadmap-reassess"],
)
def test_post_save_blocks_protected_node_in_phase_ctx(monkeypatch, node):
    """Each L2 protected node exits with code 1 when MADRUGA_PHASE_CTX=1.

    Prevents phase subprocesses from corrupting epic_nodes resume state via
    direct post_save.py calls for nodes owned by dag_executor.
    """
    import post_save

    monkeypatch.setenv("MADRUGA_PHASE_CTX", "1")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "post_save.py",
            "--platform",
            "test-plat",
            "--node",
            node,
            "--skill",
            "speckit.implement",
            "--artifact",
            "epics/001/spec.md",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        post_save.main()
    assert exc_info.value.code == 1


def test_post_save_allows_protected_node_without_phase_ctx(monkeypatch, setup_platform):
    """post_save.py --node implement proceeds normally when MADRUGA_PHASE_CTX is absent."""
    import post_save
    import db_core as db_mod

    tmp_path, db_path = setup_platform
    monkeypatch.delenv("MADRUGA_PHASE_CTX", raising=False)
    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    # Create a minimal artifact so record_save doesn't fail on hash
    epic_dir = tmp_path / "platforms" / "test-plat" / "epics" / "001-feat"
    epic_dir.mkdir(parents=True)
    (epic_dir / "spec.md").write_text("# Spec\n\nContent.\n")

    try:
        from db import get_conn as gc, upsert_epic, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        upsert_epic(conn, "test-plat", "001-feat", title="Test Feature")
        conn.close()

        result = post_save.record_save(
            platform="test-plat",
            node="implement",
            skill="speckit.implement",
            artifact="epics/001-feat/spec.md",
            epic="001-feat",
        )
        assert result["status"] == "ok"
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_record_save_autoseeds_epic_from_pitch_when_missing(setup_platform):
    """FK check failure + pitch.md on disk → auto-seed stub instead of SystemExit.

    Regression: epic 010 landed in the portal Kanban without title because
    the operator had to run ``upsert_epic`` manually and forgot ``title=``.
    post_save.py now reads the frontmatter and seeds the stub itself.
    """
    tmp_path, db_path = setup_platform
    import db_core as db_mod
    import post_save

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        from db import get_conn as gc, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        conn.close()

        epic_dir = tmp_path / "platforms" / "test-plat" / "epics" / "042-auto-seed"
        epic_dir.mkdir(parents=True)
        (epic_dir / "pitch.md").write_text(
            '---\ntitle: "Handoff Engine + Multi-Helpdesk"\nstatus: drafted\npriority: 2\n---\n'
            "# Handoff Engine + Multi-Helpdesk\n\nBody.\n"
        )
        (epic_dir / "spec.md").write_text("# Spec\n\nContent.\n")

        result = post_save.record_save(
            platform="test-plat",
            node="specify",
            skill="speckit.specify",
            artifact="epics/042-auto-seed/spec.md",
            epic="042-auto-seed",
        )
        assert result["status"] == "ok"

        conn = gc(db_path)
        row = conn.execute(
            "SELECT title, status, priority FROM epics WHERE platform_id='test-plat' AND epic_id='042-auto-seed'"
        ).fetchone()
        conn.close()
        assert row is not None, "auto-seed should have created the epic row"
        assert row["title"] == "Handoff Engine + Multi-Helpdesk"
        assert row["priority"] == 2
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_record_save_systemexits_when_no_pitch(setup_platform):
    """FK check failure + no pitch.md → SystemExit with actionable message."""
    tmp_path, db_path = setup_platform
    import db_core as db_mod
    import post_save

    original_repo = post_save.REPO_ROOT
    original_db = db_mod.DB_PATH
    post_save.REPO_ROOT = tmp_path
    db_mod.DB_PATH = db_path

    try:
        from db import get_conn as gc, upsert_platform

        conn = gc(db_path)
        upsert_platform(conn, "test-plat", name="test-plat", repo_path="platforms/test-plat")
        conn.close()

        epic_dir = tmp_path / "platforms" / "test-plat" / "epics" / "099-no-pitch"
        epic_dir.mkdir(parents=True)
        (epic_dir / "spec.md").write_text("# Spec\n\nContent.\n")

        with pytest.raises(SystemExit) as exc_info:
            post_save.record_save(
                platform="test-plat",
                node="specify",
                skill="speckit.specify",
                artifact="epics/099-no-pitch/spec.md",
                epic="099-no-pitch",
            )
        assert "pitch.md" in str(exc_info.value)
        assert "/madruga:epic-context" in str(exc_info.value)
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db
