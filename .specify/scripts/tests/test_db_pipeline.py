"""Tests for db_pipeline.py CRUD functions."""


def test_upsert_get_platform(tmp_db):
    from db_pipeline import upsert_platform, get_platform

    upsert_platform(tmp_db, "test", name="Test", repo_path="platforms/test")
    p = get_platform(tmp_db, "test")
    assert p is not None
    assert p["platform_id"] == "test"
    assert p["name"] == "Test"
    assert p["lifecycle"] == "design"


def test_upsert_platform_idempotent(tmp_db):
    from db_pipeline import upsert_platform, get_platform

    upsert_platform(tmp_db, "test", name="Test", repo_path="platforms/test")
    upsert_platform(tmp_db, "test", name="Test Updated", repo_path="platforms/test")
    p = get_platform(tmp_db, "test")
    assert p["name"] == "Test Updated"
    count = tmp_db.execute("SELECT COUNT(*) FROM platforms WHERE platform_id='test'").fetchone()[0]
    assert count == 1


def test_upsert_get_pipeline_node(tmp_db):
    from db_pipeline import upsert_platform, upsert_pipeline_node, get_pipeline_nodes

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_pipeline_node(tmp_db, "p1", "vision", "done", output_hash="sha256:abc123")
    nodes = get_pipeline_nodes(tmp_db, "p1")
    assert len(nodes) == 1
    assert nodes[0]["status"] == "done"
    assert nodes[0]["output_hash"] == "sha256:abc123"


def test_upsert_get_epic(tmp_db):
    from db_pipeline import upsert_platform, upsert_epic, get_epics

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "001-test", title="Test Epic", status="proposed")
    epics = get_epics(tmp_db, "p1")
    assert len(epics) == 1
    assert epics[0]["title"] == "Test Epic"


def test_upsert_get_epic_node(tmp_db):
    from db_pipeline import upsert_platform, upsert_epic, upsert_epic_node, get_epic_nodes

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "001-test", title="Test")
    upsert_epic_node(tmp_db, "p1", "001-test", "specify", "done")
    nodes = get_epic_nodes(tmp_db, "p1", "001-test")
    assert len(nodes) == 1
    assert nodes[0]["status"] == "done"


def test_insert_decision_auto_id(tmp_db):
    from db_decisions import insert_decision, get_decisions
    from db_pipeline import upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    did = insert_decision(tmp_db, "p1", "vision", "Test Decision", decisions=["chose A over B"])
    assert len(did) == 16  # hex of 8 bytes
    decs = get_decisions(tmp_db, "p1")
    assert len(decs) == 1
    assert decs[0]["title"] == "Test Decision"


def test_insert_provenance(tmp_db):
    from db_pipeline import upsert_platform, insert_provenance, get_provenance

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    insert_provenance(tmp_db, "p1", "business/vision.md", "vision", output_hash="sha256:abc")
    provs = get_provenance(tmp_db, "p1")
    assert len(provs) == 1
    assert provs[0]["generated_by"] == "vision"


def test_insert_complete_run(tmp_db):
    from db_pipeline import upsert_platform, insert_run, complete_run, get_runs

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    rid = insert_run(tmp_db, "p1", "vision", agent="claude-opus-4-6")
    runs = get_runs(tmp_db, "p1")
    assert len(runs) == 1
    assert runs[0]["status"] == "running"
    complete_run(tmp_db, rid, "completed", tokens_in=1000, tokens_out=500, cost_usd=0.05)
    runs = get_runs(tmp_db, "p1")
    assert runs[0]["status"] == "completed"
    assert runs[0]["tokens_in"] == 1000


def test_insert_get_events(tmp_db):
    from db_pipeline import upsert_platform, insert_event, get_events

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    eid = insert_event(tmp_db, "p1", "platform", "p1", "created", actor="human")
    assert eid is not None
    events = get_events(tmp_db, "p1")
    assert len(events) == 1
    assert events[0]["action"] == "created"
    assert events[0]["actor"] == "human"


def test_get_stale_nodes(tmp_db):
    from db_pipeline import upsert_platform, upsert_pipeline_node, get_stale_nodes

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_pipeline_node(tmp_db, "p1", "vision", "done", completed_at="2026-03-01T00:00:00Z")
    upsert_pipeline_node(tmp_db, "p1", "solution-overview", "done", completed_at="2026-03-02T00:00:00Z")
    # vision was regenerated AFTER solution-overview
    upsert_pipeline_node(tmp_db, "p1", "vision", "done", completed_at="2026-03-10T00:00:00Z")
    dag_edges = {"solution-overview": ["vision"]}
    stale = get_stale_nodes(tmp_db, "p1", dag_edges)
    assert len(stale) == 1
    assert stale[0]["node_id"] == "solution-overview"


def test_repair_timestamps(tmp_db):
    """repair_timestamps restores completed_at from events table."""
    from db_pipeline import upsert_platform, upsert_pipeline_node, insert_event, repair_timestamps

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    # Node was originally completed at a specific time
    upsert_pipeline_node(tmp_db, "p1", "vision", "done", completed_at="2026-03-15T10:00:00Z")
    insert_event(tmp_db, "p1", "node", "vision", "completed", actor="claude", payload={"skill": "madruga:vision"})

    # Simulate a reseed overwriting completed_at with a bad timestamp
    upsert_pipeline_node(tmp_db, "p1", "vision", "done", completed_at="2026-04-01T13:14:37Z")

    # Get the event timestamp for comparison
    event_ts = tmp_db.execute(
        "SELECT created_at FROM events WHERE entity_id='vision' AND action='completed'"
    ).fetchone()["created_at"]

    repaired = repair_timestamps(tmp_db, "p1")
    assert len(repaired) == 1
    assert repaired[0]["node_id"] == "vision"
    assert repaired[0]["new"] == event_ts


def test_get_platform_status(tmp_db):
    from db_pipeline import upsert_platform, upsert_pipeline_node, get_platform_status

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_pipeline_node(tmp_db, "p1", "vision", "done")
    upsert_pipeline_node(tmp_db, "p1", "blueprint", "pending")
    upsert_pipeline_node(tmp_db, "p1", "roadmap", "pending")
    status = get_platform_status(tmp_db, "p1")
    assert status["total_nodes"] == 3
    assert status["done"] == 1
    assert status["pending"] == 2
    assert status["progress_pct"] == 33.3


def test_get_epic_status(tmp_db):
    from db_pipeline import upsert_platform, upsert_epic, upsert_epic_node, get_epic_status

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "001-test", title="Test")
    upsert_epic_node(tmp_db, "p1", "001-test", "specify", "done")
    upsert_epic_node(tmp_db, "p1", "001-test", "plan", "pending")
    status = get_epic_status(tmp_db, "p1", "001-test")
    assert status["total_nodes"] == 2
    assert status["done"] == 1
    assert status["progress_pct"] == 50.0


def test_upsert_pipeline_node_preserves_existing(tmp_db):
    """ON CONFLICT DO UPDATE must preserve existing values when new kwargs are None."""
    from db_pipeline import upsert_platform, upsert_pipeline_node, get_pipeline_nodes

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    # First upsert: set all fields
    upsert_pipeline_node(
        tmp_db,
        "p1",
        "vision",
        "done",
        output_hash="sha256:original",
        completed_at="2026-03-01T00:00:00Z",
        completed_by="vision",
        line_count=150,
    )
    # Second upsert: only update status, other kwargs absent
    upsert_pipeline_node(tmp_db, "p1", "vision", "stale")
    nodes = get_pipeline_nodes(tmp_db, "p1")
    assert len(nodes) == 1
    n = nodes[0]
    assert n["status"] == "stale"
    assert n["output_hash"] == "sha256:original"  # preserved
    assert n["completed_at"] == "2026-03-01T00:00:00Z"  # preserved
    assert n["completed_by"] == "vision"  # preserved
    assert n["line_count"] == 150  # preserved


def test_upsert_epic_node_preserves_existing(tmp_db):
    """ON CONFLICT DO UPDATE must preserve existing values for epic nodes."""
    from db_pipeline import upsert_platform, upsert_epic, upsert_epic_node, get_epic_nodes

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "001-test", title="Test")
    upsert_epic_node(
        tmp_db,
        "p1",
        "001-test",
        "specify",
        "done",
        output_hash="sha256:abc",
        completed_at="2026-03-01T00:00:00Z",
    )
    # Re-upsert with just status change
    upsert_epic_node(tmp_db, "p1", "001-test", "specify", "stale")
    nodes = get_epic_nodes(tmp_db, "p1", "001-test")
    assert len(nodes) == 1
    assert nodes[0]["status"] == "stale"
    assert nodes[0]["output_hash"] == "sha256:abc"  # preserved
    assert nodes[0]["completed_at"] == "2026-03-01T00:00:00Z"  # preserved


def test_compute_file_hash_full_length(tmp_path):
    """Hash should be full SHA-256 (64 hex chars after prefix)."""
    from db_core import compute_file_hash

    f = tmp_path / "test.txt"
    f.write_text("hello")
    h = compute_file_hash(f)
    assert h.startswith("sha256:")
    hex_part = h[len("sha256:") :]
    assert len(hex_part) == 64  # full SHA-256


# ══════════════════════════════════════
# Platform repo binding tests
# ══════════════════════════════════════


def test_upsert_platform_with_repo_fields(tmp_db):
    """Repo fields are stored and retrieved correctly."""
    from db_pipeline import upsert_platform, get_platform

    upsert_platform(
        tmp_db,
        "p1",
        name="P1",
        repo_path="platforms/p1",
        repo_org="myorg",
        repo_name="my-repo",
        base_branch="develop",
        epic_branch_prefix="epic/p1/",
        tags_json='["tag1", "tag2"]',
    )
    p = get_platform(tmp_db, "p1")
    assert p["repo_org"] == "myorg"
    assert p["repo_name"] == "my-repo"
    assert p["base_branch"] == "develop"
    assert p["epic_branch_prefix"] == "epic/p1/"
    assert p["tags_json"] == '["tag1", "tag2"]'


def test_upsert_platform_preserves_repo_fields(tmp_db):
    """COALESCE preserves existing repo fields when new params are None."""
    from db_pipeline import upsert_platform, get_platform

    upsert_platform(
        tmp_db,
        "p1",
        name="P1",
        repo_path="platforms/p1",
        repo_org="org1",
        repo_name="repo1",
        base_branch="main",
    )
    # Second upsert without repo fields
    upsert_platform(tmp_db, "p1", name="P1 Updated", repo_path="platforms/p1")
    p = get_platform(tmp_db, "p1")
    assert p["name"] == "P1 Updated"
    assert p["repo_org"] == "org1"  # preserved
    assert p["repo_name"] == "repo1"  # preserved
    assert p["base_branch"] == "main"  # preserved


def test_upsert_platform_without_repo_fields(tmp_db):
    """Platforms without repo fields have None values (backward compat)."""
    from db_pipeline import upsert_platform, get_platform

    upsert_platform(tmp_db, "legacy", name="Legacy", repo_path="platforms/legacy")
    p = get_platform(tmp_db, "legacy")
    assert p["repo_org"] is None
    assert p["repo_name"] is None
    # base_branch and tags_json are None when explicitly passed as None via upsert
    # (SQLite DEFAULT only applies to INSERT without the column)
    assert p["base_branch"] is None
    assert p["tags_json"] is None


# ══════════════════════════════════════
# Local config tests
# ══════════════════════════════════════


def test_set_get_local_config(tmp_db):
    """Round-trip set/get for local_config."""
    from db_pipeline import set_local_config, get_local_config

    set_local_config(tmp_db, "repos_base_dir", "~/repos")
    assert get_local_config(tmp_db, "repos_base_dir") == "~/repos"

    # Overwrite
    set_local_config(tmp_db, "repos_base_dir", "/opt/repos")
    assert get_local_config(tmp_db, "repos_base_dir") == "/opt/repos"


def test_get_local_config_default(tmp_db):
    """Missing key returns default."""
    from db_pipeline import get_local_config

    assert get_local_config(tmp_db, "nonexistent") is None
    assert get_local_config(tmp_db, "nonexistent", "fallback") == "fallback"


def test_get_active_platform(tmp_db):
    """Active platform shorthand works."""
    from db_pipeline import set_local_config, get_active_platform

    assert get_active_platform(tmp_db) is None
    set_local_config(tmp_db, "active_platform", "prosauai")
    assert get_active_platform(tmp_db) == "prosauai"


def test_resolve_repo_path_external(tmp_db):
    """Platform with repo_org/repo_name resolves via convention."""
    from db_pipeline import upsert_platform, set_local_config, resolve_repo_path

    upsert_platform(
        tmp_db,
        "ext",
        name="Ext",
        repo_path="platforms/ext",
        repo_org="myorg",
        repo_name="ext-api",
    )
    set_local_config(tmp_db, "repos_base_dir", "/home/user/repos")
    path = resolve_repo_path(tmp_db, "ext")
    assert path == "/home/user/repos/myorg/ext-api"


def test_resolve_repo_path_self_ref(tmp_db):
    """Self-referencing platform (madruga.ai) resolves to REPO_ROOT."""
    from config import REPO_ROOT
    from db_pipeline import upsert_platform, resolve_repo_path

    upsert_platform(
        tmp_db,
        "madruga-ai",
        name="Madruga AI",
        repo_path="platforms/madruga-ai",
        repo_org="paceautomations",
        repo_name="madruga.ai",
    )
    path = resolve_repo_path(tmp_db, "madruga-ai")
    assert path == str(REPO_ROOT)


def test_resolve_repo_path_legacy(tmp_db):
    """Platform without repo fields falls back to platforms/{id}."""
    from config import REPO_ROOT
    from db_pipeline import upsert_platform, resolve_repo_path

    upsert_platform(tmp_db, "old", name="Old", repo_path="platforms/old")
    path = resolve_repo_path(tmp_db, "old")
    assert path == str(REPO_ROOT / "platforms" / "old")


# --- Draft status tests ---


def test_epic_drafted_status(tmp_db):
    """Epic can be created with drafted status."""
    from db_pipeline import get_epics, upsert_epic, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "017-test", title="Test Draft", status="drafted")
    epics = get_epics(tmp_db, "p1")
    drafted = [e for e in epics if e["epic_id"] == "017-test"]
    assert len(drafted) == 1
    assert drafted[0]["status"] == "drafted"


def test_epic_status_map_drafted():
    """_EPIC_STATUS_MAP includes drafted."""
    from db_pipeline import _EPIC_STATUS_MAP

    assert _EPIC_STATUS_MAP["drafted"] == "drafted"
    assert _EPIC_STATUS_MAP["draft"] == "drafted"


def test_compute_epic_status_does_not_promote_drafted(tmp_db):
    """compute_epic_status does not auto-promote drafted epics."""
    from db_pipeline import compute_epic_status, upsert_epic, upsert_epic_node, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "017-test", title="Test", status="drafted")
    upsert_epic_node(tmp_db, "p1", "017-test", "epic-context", "done")

    new_status, _ = compute_epic_status(
        tmp_db, "p1", "017-test", required_node_ids={"epic-context"}, current_status="drafted"
    )
    assert new_status == "drafted"


# --- Fix: progress_pct must include skipped nodes ---


def test_get_epic_status_progress_includes_skipped(tmp_db):
    """progress_pct counts done+skipped as completed (fix: trace spam operation)."""
    from db_pipeline import get_epic_status, upsert_epic, upsert_epic_node, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "020-test", title="Test", status="in_progress")
    upsert_epic_node(tmp_db, "p1", "020-test", "specify", "done")
    upsert_epic_node(tmp_db, "p1", "020-test", "plan", "done")
    upsert_epic_node(tmp_db, "p1", "020-test", "qa", "skipped")

    status = get_epic_status(tmp_db, "p1", "020-test")
    assert status["done"] == 2
    assert status["skipped"] == 1
    assert status["total_nodes"] == 3
    # progress must be 100% (2 done + 1 skipped = 3/3)
    assert status["progress_pct"] == 100.0


def test_get_platform_status_progress_includes_skipped(tmp_db):
    """L1 progress_pct also counts skipped nodes as completed."""
    from db_pipeline import get_platform_status, upsert_pipeline_node, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_pipeline_node(tmp_db, "p1", "vision", "done")
    upsert_pipeline_node(tmp_db, "p1", "codebase-map", "skipped")

    status = get_platform_status(tmp_db, "p1")
    assert status["done"] == 1
    assert status["skipped"] == 1
    assert status["total_nodes"] == 2
    assert status["progress_pct"] == 100.0


def test_progress_pct_zero_skipped_unchanged(tmp_db):
    """When no skipped nodes, progress_pct works as before."""
    from db_pipeline import get_epic_status, upsert_epic, upsert_epic_node, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "021-test", title="Test", status="in_progress")
    upsert_epic_node(tmp_db, "p1", "021-test", "specify", "done")
    upsert_epic_node(tmp_db, "p1", "021-test", "plan", "pending")

    status = get_epic_status(tmp_db, "p1", "021-test")
    assert status["progress_pct"] == 50.0
