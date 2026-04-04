"""Tests for post-save.py CLI wrapper."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_conn, get_epic_nodes, get_pipeline_nodes, migrate


@pytest.fixture
def setup_platform(tmp_path):
    """Create a minimal platform structure for testing."""
    db_path = tmp_path / ".pipeline" / "madruga.db"
    db_path.parent.mkdir(parents=True)

    # Create platform dir with platform.yaml
    pdir = tmp_path / "platforms" / "test-plat"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text(
        "name: test-plat\ntitle: Test\nlifecycle: design\n"
        "pipeline:\n"
        "  nodes:\n"
        "    - id: vision\n      outputs: ['business/vision.md']\n"
        "      depends: []\n      gate: human\n"
        "  epic_cycle:\n"
        "    nodes:\n"
        "      - id: specify\n        skill: speckit.specify\n"
        "        outputs: ['{epic}/spec.md']\n"
        "        depends: []\n        gate: human\n"
        "      - id: plan\n        skill: speckit.plan\n"
        "        outputs: ['{epic}/plan.md']\n"
        "        depends: [specify]\n        gate: human\n"
        "      - id: implement\n        skill: speckit.implement\n"
        "        outputs: ['{epic}/code']\n"
        "        depends: [plan]\n        gate: auto\n"
        "      - id: clarify\n        skill: speckit.clarify\n"
        "        outputs: ['{epic}/spec.md']\n"
        "        depends: [specify]\n        gate: human\n"
        "        optional: true\n"
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

    return tmp_path, db_path


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


def test_record_save_skips_when_hash_unchanged(setup_platform):
    """record_save should NOT overwrite completed_at when hash is unchanged."""
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

        # Second save — same file, same hash (simulates hook from side-effect edit)
        import time

        time.sleep(0.1)  # ensure datetime.now() would differ
        post_save.record_save(
            platform="test-plat",
            node="vision",
            skill="madruga:vision",
            artifact="business/vision.md",
        )

        # completed_at should NOT have changed
        conn = get_conn(db_path)
        nodes = get_pipeline_nodes(conn, "test-plat")
        new_ts = next(n for n in nodes if n["node_id"] == "vision")["completed_at"]
        conn.close()

        assert new_ts == original_ts, f"completed_at changed from {original_ts} to {new_ts}"
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
