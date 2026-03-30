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

    count = tmp_db.execute("SELECT COUNT(*) FROM platforms WHERE platform_id='test-plat'").fetchone()[0]
    assert count == 1


def test_seed_missing_platform_yaml(tmp_db, tmp_path):
    from db import seed_from_filesystem

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = seed_from_filesystem(tmp_db, "missing", empty_dir)
    assert result["status"] == "skipped"


def test_seed_reads_repo_fields(tmp_db, sample_platform_dir):
    """Seed populates repo fields from platform.yaml."""
    from db import seed_from_filesystem, get_platform

    seed_from_filesystem(tmp_db, "test-plat", sample_platform_dir)
    p = get_platform(tmp_db, "test-plat")
    assert p["repo_org"] == "testorg"
    assert p["repo_name"] == "test-repo"
    assert p["base_branch"] == "main"
    assert p["epic_branch_prefix"] == "epic/test-plat/"
    assert '"test"' in p["tags_json"]
    assert '"sample"' in p["tags_json"]


def test_seed_without_repo_fields(tmp_db, tmp_path):
    """Seed works for platform.yaml without repo block (backward compat)."""
    from db import seed_from_filesystem, get_platform

    pdir = tmp_path / "legacy-plat"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text(
        "name: legacy-plat\ntitle: Legacy\nlifecycle: design\n"
        "pipeline:\n  nodes:\n    - id: platform-new\n"
        "      outputs: ['platform.yaml']\n      depends: []\n"
        "      gate: human\n"
    )
    seed_from_filesystem(tmp_db, "legacy-plat", pdir)
    p = get_platform(tmp_db, "legacy-plat")
    assert p is not None
    assert p["repo_org"] is None
    assert p["repo_name"] is None


def test_seed_sets_completed_at_for_done_nodes(tmp_db, sample_platform_dir):
    """Done pipeline nodes get completed_at from file mtime."""
    from db import seed_from_filesystem, get_pipeline_nodes

    seed_from_filesystem(tmp_db, "test-plat", sample_platform_dir)
    nodes = get_pipeline_nodes(tmp_db, "test-plat")
    for n in nodes:
        if n["status"] == "done":
            assert n["completed_at"] is not None, f"done node {n['node_id']} missing completed_at"
        else:
            assert n["completed_at"] is None, f"pending node {n['node_id']} should not have completed_at"


def test_seed_reads_epic_frontmatter(tmp_db, sample_platform_dir):
    """Seed reads status, appetite, priority from pitch.md YAML frontmatter."""
    from db import seed_from_filesystem, get_epics

    seed_from_filesystem(tmp_db, "test-plat", sample_platform_dir)
    epics = get_epics(tmp_db, "test-plat")
    assert len(epics) == 1
    assert epics[0]["status"] == "in_progress"
    assert epics[0]["appetite"] == "1w"
    assert epics[0]["priority"] == 1


def test_seed_epic_status_defaults_to_proposed(tmp_db, tmp_path):
    """Epic without status in frontmatter defaults to proposed."""
    from db import seed_from_filesystem, get_epics

    pdir = tmp_path / "plat-no-status"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text(
        "name: plat-no-status\ntitle: Test\nlifecycle: design\npipeline:\n  nodes: []\n"
    )
    epic_dir = pdir / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text('---\ntitle: "No Status Epic"\n---\n# No Status Epic\n')

    seed_from_filesystem(tmp_db, "plat-no-status", pdir)
    epics = get_epics(tmp_db, "plat-no-status")
    assert len(epics) == 1
    assert epics[0]["status"] == "proposed"


def test_seed_epic_shipped_status(tmp_db, tmp_path):
    """Epic with status: Shipped maps to 'shipped' in DB."""
    from db import seed_from_filesystem, get_epics

    pdir = tmp_path / "plat-shipped"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text("name: plat-shipped\ntitle: Test\nlifecycle: design\npipeline:\n  nodes: []\n")
    epic_dir = pdir / "epics" / "006-sqlite"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text(
        '---\ntitle: "SQLite Foundation"\nstatus: Shipped\nappetite: "2w"\n---\n# SQLite Foundation\n'
    )

    seed_from_filesystem(tmp_db, "plat-shipped", pdir)
    epics = get_epics(tmp_db, "plat-shipped")
    assert len(epics) == 1
    assert epics[0]["status"] == "shipped"
    assert epics[0]["appetite"] == "2w"
