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


def test_seed_reads_delivered_at(tmp_db, tmp_path):
    """Seed reads delivered_at from shipped epic frontmatter."""
    from db import seed_from_filesystem, get_epics

    pdir = tmp_path / "plat-delivered"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text(
        "name: plat-delivered\ntitle: Test\nlifecycle: design\npipeline:\n  nodes: []\n"
    )
    epic_dir = pdir / "epics" / "010-dashboard"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text(
        '---\ntitle: "Dashboard"\nstatus: shipped\ndelivered_at: 2026-03-30\n---\n# Dashboard\n'
    )

    seed_from_filesystem(tmp_db, "plat-delivered", pdir)
    epics = get_epics(tmp_db, "plat-delivered")
    assert len(epics) == 1
    assert epics[0]["delivered_at"] == "2026-03-30"


def test_seed_delivered_at_null_for_non_shipped(tmp_db, tmp_path):
    """Non-shipped epic has no delivered_at."""
    from db import seed_from_filesystem, get_epics

    pdir = tmp_path / "plat-planned"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text("name: plat-planned\ntitle: Test\nlifecycle: design\npipeline:\n  nodes: []\n")
    epic_dir = pdir / "epics" / "012-feature"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text('---\ntitle: "Feature"\nstatus: planned\n---\n# Feature\n')

    seed_from_filesystem(tmp_db, "plat-planned", pdir)
    epics = get_epics(tmp_db, "plat-planned")
    assert len(epics) == 1
    assert epics[0]["delivered_at"] is None


def test_reseed_preserves_shipped_status(tmp_db, tmp_path):
    """Reseed does not regress shipped→proposed when pitch.md says planned."""
    from db import seed_from_filesystem, get_epics, upsert_epic

    pdir = tmp_path / "plat-guard"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text("name: plat-guard\ntitle: Test\nlifecycle: design\npipeline:\n  nodes: []\n")
    epic_dir = pdir / "epics" / "012-shipped"
    epic_dir.mkdir(parents=True)
    # pitch.md says "planned" (stale)
    (epic_dir / "pitch.md").write_text('---\ntitle: "Shipped Epic"\nstatus: planned\n---\n# Shipped Epic\n')

    # First seed to create the epic
    seed_from_filesystem(tmp_db, "plat-guard", pdir)
    # Manually set to shipped in DB (simulating post_save transition)
    upsert_epic(tmp_db, "plat-guard", "012-shipped", title="Shipped Epic", status="shipped")
    epics = get_epics(tmp_db, "plat-guard")
    assert epics[0]["status"] == "shipped"

    # Reseed again — pitch.md still says "planned"
    seed_from_filesystem(tmp_db, "plat-guard", pdir)
    epics = get_epics(tmp_db, "plat-guard")
    assert epics[0]["status"] == "shipped"  # must NOT regress to proposed


def test_reseed_accepts_blocked_override(tmp_db, tmp_path):
    """Reseed accepts blocked status from filesystem even if DB says shipped."""
    from db import seed_from_filesystem, get_epics, upsert_epic

    pdir = tmp_path / "plat-block"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text("name: plat-block\ntitle: Test\nlifecycle: design\npipeline:\n  nodes: []\n")
    epic_dir = pdir / "epics" / "013-blocked"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text('---\ntitle: "Blocked Epic"\nstatus: blocked\n---\n# Blocked Epic\n')

    # First seed
    seed_from_filesystem(tmp_db, "plat-block", pdir)
    # Set to shipped in DB
    upsert_epic(tmp_db, "plat-block", "013-blocked", title="Blocked Epic", status="shipped")

    # Reseed — pitch.md says "blocked" (legitimate override)
    seed_from_filesystem(tmp_db, "plat-block", pdir)
    epics = get_epics(tmp_db, "plat-block")
    assert epics[0]["status"] == "blocked"  # must accept the override


def test_reseed_preserves_completed_at(tmp_db, sample_platform_dir):
    """Reseed must NOT overwrite completed_at when node already has one in DB."""
    from db import seed_from_filesystem, get_pipeline_nodes, upsert_pipeline_node

    # First seed — sets completed_at from file mtime
    seed_from_filesystem(tmp_db, "test-plat", sample_platform_dir)
    _ = {n["node_id"]: n for n in get_pipeline_nodes(tmp_db, "test-plat")}

    # Manually set a specific completed_at (simulating record_save from skill execution)
    original_ts = "2026-03-15T10:00:00Z"
    upsert_pipeline_node(tmp_db, "test-plat", "vision", "done", completed_at=original_ts)

    # Modify the file to change its mtime (simulating a reconcile edit)
    vision_file = sample_platform_dir / "business" / "vision.md"
    vision_file.write_text("---\ntitle: Vision\n---\n# Vision\nUpdated content.\n")

    # Reseed — should preserve the original completed_at, not use new file mtime
    seed_from_filesystem(tmp_db, "test-plat", sample_platform_dir)
    nodes_after = {n["node_id"]: n for n in get_pipeline_nodes(tmp_db, "test-plat")}

    assert nodes_after["vision"]["completed_at"] == original_ts


def test_seed_backfill_sets_completed_at(tmp_db, tmp_path):
    """Backfilled dependency nodes get a completed_at timestamp."""
    from db import seed_from_filesystem, get_pipeline_nodes

    pdir = tmp_path / "plat-backfill"
    pdir.mkdir(parents=True)
    (pdir / "platform.yaml").write_text("""
name: plat-backfill
title: Test
lifecycle: design
pipeline:
  nodes:
    - id: A
      outputs: ["a.md"]
      depends: []
      gate: human
    - id: B
      outputs: ["b.md"]
      depends: ["A"]
      gate: human
""")
    # Only B exists — A should be backfilled as done
    (pdir / "b.md").write_text("# B\n")

    seed_from_filesystem(tmp_db, "plat-backfill", pdir)
    nodes = {n["node_id"]: n for n in get_pipeline_nodes(tmp_db, "plat-backfill")}

    assert nodes["A"]["status"] == "done"  # backfilled
    assert nodes["A"]["completed_at"] is not None  # must have a timestamp
    assert nodes["B"]["status"] == "done"
    assert nodes["B"]["completed_at"] is not None
