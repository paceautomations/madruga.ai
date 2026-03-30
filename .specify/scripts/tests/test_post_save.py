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
        "pipeline:\n  nodes:\n    - id: vision\n      outputs: ['business/vision.md']\n"
        "      depends: []\n      gate: human\n"
    )

    # Create an artifact
    (pdir / "business").mkdir()
    (pdir / "business" / "vision.md").write_text("# Vision\nTest content here.")

    # Create epic structure
    epic_dir = pdir / "epics" / "001-test-epic"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text("---\ntitle: Test Epic\n---\n# Test Epic\n")
    (epic_dir / "spec.md").write_text("# Spec\nTest spec content.")

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
    import db as db_mod

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
    import db as db_mod

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
        conn.close()
    finally:
        post_save.REPO_ROOT = original_repo
        db_mod.DB_PATH = original_db


def test_reseed(setup_platform):
    """Test reseed functionality."""
    tmp_path, db_path = setup_platform
    import post_save
    import db as db_mod

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


def test_reseed_missing_platform(setup_platform):
    """Test reseed with non-existent platform."""
    tmp_path, db_path = setup_platform
    import post_save
    import db as db_mod

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
