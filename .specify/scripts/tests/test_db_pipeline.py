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


def test_complete_run_fills_wall_clock_when_duration_missing(tmp_db):
    """success_check rescue path completes runs WITHOUT duration_ms (Claude
    output was lost to timeout). Wall-clock must still be filled from started_at.

    Regression for easter-tracking.md (epic 008-admin-evolution, run 8718bb50).
    Mocks _now() because db_core._now has 1-second resolution — a real sleep
    would slow the test to >1s.
    """
    from unittest.mock import patch

    from db_pipeline import complete_run, get_runs, insert_run, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")

    with patch("db_pipeline._now", return_value="2026-04-17T12:00:00Z"):
        rid = insert_run(tmp_db, "p1", "implement:phase-1")
    with patch("db_pipeline._now", return_value="2026-04-17T12:55:22Z"):
        complete_run(tmp_db, rid, status="completed")  # no duration_ms passed

    runs = get_runs(tmp_db, "p1")
    expected_ms = (55 * 60 + 22) * 1000  # 3322000 ms
    assert runs[0]["duration_ms"] == expected_ms


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


def test_compute_epic_status_drafted_stays_when_only_epic_context_done(tmp_db):
    """drafted stays when only epic-context is done (--draft mode footprint)."""
    from db_pipeline import compute_epic_status, upsert_epic, upsert_epic_node, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "017-test", title="Test", status="drafted")
    upsert_epic_node(tmp_db, "p1", "017-test", "epic-context", "done")

    new_status, _ = compute_epic_status(
        tmp_db,
        "p1",
        "017-test",
        required_node_ids={"epic-context", "specify", "plan"},
        current_status="drafted",
    )
    assert new_status == "drafted"


def test_compute_epic_status_drafted_stays_with_no_nodes_done(tmp_db):
    """drafted stays when no nodes are done (pristine draft)."""
    from db_pipeline import compute_epic_status, upsert_epic, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "017-test", title="Test", status="drafted")

    new_status, delivered_at = compute_epic_status(
        tmp_db,
        "p1",
        "017-test",
        required_node_ids={"specify", "plan", "implement"},
        current_status="drafted",
    )
    assert new_status == "drafted"
    assert delivered_at is None


def test_compute_epic_status_drafted_promotes_when_beyond_epic_context(tmp_db):
    """drafted → in_progress when any node beyond epic-context completes."""
    from db_pipeline import compute_epic_status, upsert_epic, upsert_epic_node, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "017-test", title="Test", status="drafted")
    upsert_epic_node(tmp_db, "p1", "017-test", "epic-context", "done")
    upsert_epic_node(tmp_db, "p1", "017-test", "specify", "done")

    new_status, delivered_at = compute_epic_status(
        tmp_db,
        "p1",
        "017-test",
        required_node_ids={"specify", "plan", "implement"},
        current_status="drafted",
    )
    assert new_status == "in_progress"
    assert delivered_at is None


def test_compute_epic_status_drafted_ships_when_all_required_done(tmp_db):
    """drafted → shipped when all required nodes complete (reseed of fully-run stuck epic)."""
    from db_pipeline import compute_epic_status, upsert_epic, upsert_epic_node, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "017-test", title="Test", status="drafted")
    for node in ("epic-context", "specify", "plan", "implement"):
        upsert_epic_node(tmp_db, "p1", "017-test", node, "done")

    new_status, delivered_at = compute_epic_status(
        tmp_db,
        "p1",
        "017-test",
        required_node_ids={"epic-context", "specify", "plan", "implement"},
        current_status="drafted",
    )
    assert new_status == "shipped"
    assert delivered_at is not None


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


# ══════════════════════════════════════
# Commit traceability tests (Epic 023)
# ══════════════════════════════════════


def test_insert_commit_single(tmp_db):
    """insert_commit stores a single commit with all fields."""
    from db_pipeline import insert_commit, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    insert_commit(
        tmp_db,
        sha="abc123def456",
        message="feat: add feature X",
        author="Dev User",
        platform_id="p1",
        epic_id="023-commit-traceability",
        source="hook",
        committed_at="2026-04-08T10:00:00Z",
        files_json='["src/main.py", "tests/test_main.py"]',
    )

    row = tmp_db.execute("SELECT * FROM commits WHERE sha = 'abc123def456'").fetchone()
    assert row is not None
    assert row["sha"] == "abc123def456"
    assert row["message"] == "feat: add feature X"
    assert row["author"] == "Dev User"
    assert row["platform_id"] == "p1"
    assert row["epic_id"] == "023-commit-traceability"
    assert row["source"] == "hook"
    assert row["committed_at"] == "2026-04-08T10:00:00Z"
    assert row["files_json"] == '["src/main.py", "tests/test_main.py"]'
    assert row["created_at"] is not None  # auto-populated by DEFAULT


def test_insert_commit_duplicate_sha_ignored(tmp_db):
    """Duplicate SHA is silently ignored (INSERT OR IGNORE for idempotency)."""
    from db_pipeline import insert_commit, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    insert_commit(
        tmp_db,
        sha="deadbeef1234",
        message="first insert",
        author="Dev",
        platform_id="p1",
        epic_id=None,
        source="hook",
        committed_at="2026-04-08T10:00:00Z",
        files_json="[]",
    )
    # Second insert with same SHA — should be silently ignored
    insert_commit(
        tmp_db,
        sha="deadbeef1234",
        message="second insert attempt",
        author="Other Dev",
        platform_id="p1",
        epic_id="099-other",
        source="backfill",
        committed_at="2026-04-08T11:00:00Z",
        files_json='["new_file.py"]',
    )

    count = tmp_db.execute("SELECT COUNT(*) FROM commits WHERE sha = 'deadbeef1234'").fetchone()[0]
    assert count == 1
    # Original values preserved (first insert wins)
    row = tmp_db.execute("SELECT * FROM commits WHERE sha = 'deadbeef1234'").fetchone()
    assert row["message"] == "first insert"
    assert row["author"] == "Dev"


def test_insert_commit_multi_platform_same_sha(tmp_db):
    """A commit touching multiple platforms creates one row per platform.

    The SHA UNIQUE constraint is per-row, so multi-platform commits use
    a composite key pattern: sha + platform_id must be unique together,
    OR the caller appends a platform suffix to make the SHA unique per row.
    Based on the migration (sha UNIQUE globally), multi-platform commits
    need distinct SHA values (e.g. sha:platform_id convention).
    """
    from db_pipeline import insert_commit, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_platform(tmp_db, "p2", name="P2", repo_path="platforms/p2")

    # Multi-platform commit: same logical commit, one row per platform
    # SHA must differ per row since commits.sha is UNIQUE
    insert_commit(
        tmp_db,
        sha="aaa111:p1",
        message="chore: update cross-platform config",
        author="Dev",
        platform_id="p1",
        epic_id=None,
        source="hook",
        committed_at="2026-04-08T12:00:00Z",
        files_json='["platforms/p1/config.yaml"]',
    )
    insert_commit(
        tmp_db,
        sha="aaa111:p2",
        message="chore: update cross-platform config",
        author="Dev",
        platform_id="p2",
        epic_id=None,
        source="hook",
        committed_at="2026-04-08T12:00:00Z",
        files_json='["platforms/p2/config.yaml"]',
    )

    total = tmp_db.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    assert total == 2
    p1_row = tmp_db.execute("SELECT * FROM commits WHERE platform_id = 'p1'").fetchone()
    p2_row = tmp_db.execute("SELECT * FROM commits WHERE platform_id = 'p2'").fetchone()
    assert p1_row is not None
    assert p2_row is not None
    assert p1_row["message"] == p2_row["message"]  # same commit message
    assert p1_row["platform_id"] != p2_row["platform_id"]


def test_insert_commit_null_epic_id_adhoc(tmp_db):
    """Ad-hoc commits (not tied to any epic) have NULL epic_id."""
    from db_pipeline import insert_commit, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    insert_commit(
        tmp_db,
        sha="adhoc999",
        message="fix: quick typo fix on main",
        author="Dev",
        platform_id="p1",
        epic_id=None,
        source="hook",
        committed_at="2026-04-08T09:00:00Z",
        files_json='["README.md"]',
    )

    row = tmp_db.execute("SELECT * FROM commits WHERE sha = 'adhoc999'").fetchone()
    assert row is not None
    assert row["epic_id"] is None
    # Verify it's distinguishable from epic-linked commits
    insert_commit(
        tmp_db,
        sha="epic777",
        message="feat: epic work",
        author="Dev",
        platform_id="p1",
        epic_id="023-commit-traceability",
        source="hook",
        committed_at="2026-04-08T09:30:00Z",
        files_json="[]",
    )
    adhoc_rows = tmp_db.execute("SELECT * FROM commits WHERE epic_id IS NULL").fetchall()
    epic_rows = tmp_db.execute("SELECT * FROM commits WHERE epic_id IS NOT NULL").fetchall()
    assert len(adhoc_rows) == 1
    assert len(epic_rows) == 1
    assert adhoc_rows[0]["sha"] == "adhoc999"
    assert epic_rows[0]["sha"] == "epic777"


# --- T004: Query function tests ---


def _seed_commits(tmp_db):
    """Helper: seed a mix of epic and ad-hoc commits across two platforms."""
    from db_pipeline import insert_commit, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_platform(tmp_db, "p2", name="P2", repo_path="platforms/p2")

    # 3 commits for epic 012 on p1
    for i in range(3):
        insert_commit(
            tmp_db,
            sha=f"epic012-p1-{i}",
            message=f"feat: epic 012 work #{i}",
            author="Dev A",
            platform_id="p1",
            epic_id="012-whatsapp-daemon",
            source="hook",
            committed_at=f"2026-04-0{i + 1}T10:00:00Z",
            files_json=f'["platforms/p1/file{i}.py"]',
        )

    # 2 commits for epic 023 on p1
    for i in range(2):
        insert_commit(
            tmp_db,
            sha=f"epic023-p1-{i}",
            message=f"feat: epic 023 work #{i}",
            author="Dev B",
            platform_id="p1",
            epic_id="023-commit-traceability",
            source="hook",
            committed_at=f"2026-04-0{i + 5}T10:00:00Z",
            files_json="[]",
        )

    # 2 ad-hoc commits on p1 (NULL epic_id)
    for i in range(2):
        insert_commit(
            tmp_db,
            sha=f"adhoc-p1-{i}",
            message=f"fix: ad-hoc fix #{i}",
            author="Dev C",
            platform_id="p1",
            epic_id=None,
            source="hook",
            committed_at=f"2026-04-0{i + 7}T10:00:00Z",
            files_json="[]",
        )

    # 1 commit for epic 012 on p2 (different platform)
    insert_commit(
        tmp_db,
        sha="epic012-p2-0",
        message="feat: epic 012 cross-platform",
        author="Dev A",
        platform_id="p2",
        epic_id="012-whatsapp-daemon",
        source="hook",
        committed_at="2026-04-01T11:00:00Z",
        files_json='["platforms/p2/config.yaml"]',
    )

    # 1 ad-hoc commit on p2
    insert_commit(
        tmp_db,
        sha="adhoc-p2-0",
        message="fix: p2 ad-hoc",
        author="Dev C",
        platform_id="p2",
        epic_id=None,
        source="hook",
        committed_at="2026-04-09T10:00:00Z",
        files_json="[]",
    )


def test_get_commits_by_epic_returns_correct_commits(tmp_db):
    """get_commits_by_epic returns only commits for the specified epic."""
    from db_pipeline import get_commits_by_epic

    _seed_commits(tmp_db)

    results = get_commits_by_epic(tmp_db, "012-whatsapp-daemon")
    # 3 on p1 + 1 on p2 = 4 total for epic 012
    assert len(results) == 4
    assert all(r["epic_id"] == "012-whatsapp-daemon" for r in results)
    # Ordered by committed_at DESC
    dates = [r["committed_at"] for r in results]
    assert dates == sorted(dates, reverse=True)


def test_get_commits_by_epic_with_platform_filter(tmp_db):
    """get_commits_by_epic with platform_id filters to that platform only."""
    from db_pipeline import get_commits_by_epic

    _seed_commits(tmp_db)

    results = get_commits_by_epic(tmp_db, "012-whatsapp-daemon", platform_id="p1")
    assert len(results) == 3
    assert all(r["platform_id"] == "p1" for r in results)
    assert all(r["epic_id"] == "012-whatsapp-daemon" for r in results)


def test_get_commits_by_epic_returns_dicts(tmp_db):
    """get_commits_by_epic returns list of dicts with expected keys."""
    from db_pipeline import get_commits_by_epic

    _seed_commits(tmp_db)

    results = get_commits_by_epic(tmp_db, "023-commit-traceability")
    assert len(results) == 2
    # Verify dict-like access works (Row or dict)
    first = results[0]
    for key in ("sha", "message", "author", "platform_id", "epic_id", "committed_at", "files_json"):
        assert key in first.keys(), f"Missing key: {key}"


def test_get_commits_by_epic_empty_result(tmp_db):
    """Querying a non-existent epic returns an empty list, no error."""
    from db_pipeline import get_commits_by_epic, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")

    results = get_commits_by_epic(tmp_db, "999-nonexistent")
    assert results == []


def test_get_commits_by_platform_filters_correctly(tmp_db):
    """get_commits_by_platform returns only commits for the specified platform."""
    from db_pipeline import get_commits_by_platform

    _seed_commits(tmp_db)

    results = get_commits_by_platform(tmp_db, "p1")
    # p1 has: 3 (epic 012) + 2 (epic 023) + 2 (ad-hoc) = 7
    assert len(results) == 7
    assert all(r["platform_id"] == "p1" for r in results)
    # Ordered by committed_at DESC
    dates = [r["committed_at"] for r in results]
    assert dates == sorted(dates, reverse=True)


def test_get_commits_by_platform_pagination(tmp_db):
    """get_commits_by_platform respects limit and offset for pagination."""
    from db_pipeline import get_commits_by_platform

    _seed_commits(tmp_db)

    # p1 has 7 commits total
    page1 = get_commits_by_platform(tmp_db, "p1", limit=3, offset=0)
    assert len(page1) == 3

    page2 = get_commits_by_platform(tmp_db, "p1", limit=3, offset=3)
    assert len(page2) == 3

    page3 = get_commits_by_platform(tmp_db, "p1", limit=3, offset=6)
    assert len(page3) == 1

    # No overlap between pages
    shas_p1 = {r["sha"] for r in page1}
    shas_p2 = {r["sha"] for r in page2}
    shas_p3 = {r["sha"] for r in page3}
    assert shas_p1.isdisjoint(shas_p2)
    assert shas_p1.isdisjoint(shas_p3)
    assert shas_p2.isdisjoint(shas_p3)


def test_get_commits_by_platform_empty_result(tmp_db):
    """Querying a platform with no commits returns an empty list."""
    from db_pipeline import get_commits_by_platform, upsert_platform

    upsert_platform(tmp_db, "empty", name="Empty", repo_path="platforms/empty")

    results = get_commits_by_platform(tmp_db, "empty")
    assert results == []


def test_get_adhoc_commits_returns_only_null_epic(tmp_db):
    """get_adhoc_commits returns only commits with NULL epic_id."""
    from db_pipeline import get_adhoc_commits

    _seed_commits(tmp_db)

    results = get_adhoc_commits(tmp_db)
    # 2 ad-hoc on p1 + 1 ad-hoc on p2 = 3
    assert len(results) == 3
    assert all(r["epic_id"] is None for r in results)


def test_get_adhoc_commits_with_platform_filter(tmp_db):
    """get_adhoc_commits with platform_id filters to that platform only."""
    from db_pipeline import get_adhoc_commits

    _seed_commits(tmp_db)

    results = get_adhoc_commits(tmp_db, platform_id="p1")
    assert len(results) == 2
    assert all(r["platform_id"] == "p1" for r in results)
    assert all(r["epic_id"] is None for r in results)


def test_get_adhoc_commits_respects_limit(tmp_db):
    """get_adhoc_commits respects the limit parameter."""
    from db_pipeline import get_adhoc_commits

    _seed_commits(tmp_db)

    results = get_adhoc_commits(tmp_db, limit=1)
    assert len(results) == 1
    assert results[0]["epic_id"] is None


def test_get_adhoc_commits_empty_result(tmp_db):
    """When no ad-hoc commits exist, returns an empty list."""
    from db_pipeline import get_adhoc_commits, insert_commit, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    # Only epic commits, no ad-hoc
    insert_commit(
        tmp_db,
        sha="epic-only-1",
        message="feat: epic work",
        author="Dev",
        platform_id="p1",
        epic_id="023-commit-traceability",
        source="hook",
        committed_at="2026-04-08T10:00:00Z",
        files_json="[]",
    )

    results = get_adhoc_commits(tmp_db)
    assert results == []


# --- T010: Integration test — epic vs ad-hoc commit partitioning ---


def test_integration_epic_vs_adhoc_partitioning(tmp_db):
    """Insert 5 commits (3 epic-012, 2 ad-hoc) and verify query partitioning.

    Integration test: exercises insert_commit + get_commits_by_epic +
    get_adhoc_commits together on a single platform to confirm the
    epic/ad-hoc split is exact with no leaks between partitions.
    """
    from db_pipeline import get_adhoc_commits, get_commits_by_epic, insert_commit, upsert_platform

    upsert_platform(tmp_db, "madruga-ai", name="Madruga AI", repo_path="platforms/madruga-ai")

    # 3 commits linked to epic 012
    epic_shas = []
    for i in range(3):
        sha = f"integ-epic012-{i}"
        epic_shas.append(sha)
        insert_commit(
            tmp_db,
            sha=sha,
            message=f"feat: epic 012 integration #{i}",
            author="Dev Integration",
            platform_id="madruga-ai",
            epic_id="012-whatsapp-daemon",
            source="hook",
            committed_at=f"2026-04-0{i + 1}T08:00:00Z",
            files_json=f'["platforms/madruga-ai/file{i}.py"]',
        )

    # 2 ad-hoc commits (no epic)
    adhoc_shas = []
    for i in range(2):
        sha = f"integ-adhoc-{i}"
        adhoc_shas.append(sha)
        insert_commit(
            tmp_db,
            sha=sha,
            message=f"fix: ad-hoc integration #{i}",
            author="Dev Integration",
            platform_id="madruga-ai",
            epic_id=None,
            source="hook",
            committed_at=f"2026-04-0{i + 4}T08:00:00Z",
            files_json="[]",
        )

    # Verify total is 5
    total = tmp_db.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    assert total == 5

    # get_commits_by_epic returns exactly the 3 epic commits
    epic_results = get_commits_by_epic(tmp_db, "012-whatsapp-daemon")
    assert len(epic_results) == 3
    assert {r["sha"] for r in epic_results} == set(epic_shas)
    assert all(r["epic_id"] == "012-whatsapp-daemon" for r in epic_results)

    # get_adhoc_commits returns exactly the 2 ad-hoc commits
    adhoc_results = get_adhoc_commits(tmp_db)
    assert len(adhoc_results) == 2
    assert {r["sha"] for r in adhoc_results} == set(adhoc_shas)
    assert all(r["epic_id"] is None for r in adhoc_results)

    # No overlap between the two result sets
    epic_sha_set = {r["sha"] for r in epic_results}
    adhoc_sha_set = {r["sha"] for r in adhoc_results}
    assert epic_sha_set.isdisjoint(adhoc_sha_set)
    # Together they account for all 5 commits
    assert len(epic_sha_set | adhoc_sha_set) == 5


# --- T011: Integration test — empty epic query with populated DB ---


def test_integration_empty_epic_query_with_populated_db(tmp_db):
    """Querying a non-existent epic returns empty list even when DB has commits.

    Integration test: unlike the unit-level test_get_commits_by_epic_empty_result
    (which tests against an empty DB), this verifies that querying a non-existent
    epic returns [] when the DB is populated with commits for OTHER epics — ensuring
    no false positives leak from unrelated epic_id values or NULL epic_id rows.
    """
    from db_pipeline import get_commits_by_epic, insert_commit, upsert_platform

    upsert_platform(tmp_db, "madruga-ai", name="Madruga AI", repo_path="platforms/madruga-ai")

    # Populate DB with commits for real epics + ad-hoc
    insert_commit(
        tmp_db,
        sha="existing-epic-1",
        message="feat: epic 012 work",
        author="Dev",
        platform_id="madruga-ai",
        epic_id="012-whatsapp-daemon",
        source="hook",
        committed_at="2026-04-01T10:00:00Z",
        files_json="[]",
    )
    insert_commit(
        tmp_db,
        sha="existing-epic-2",
        message="feat: epic 023 work",
        author="Dev",
        platform_id="madruga-ai",
        epic_id="023-commit-traceability",
        source="hook",
        committed_at="2026-04-02T10:00:00Z",
        files_json="[]",
    )
    insert_commit(
        tmp_db,
        sha="existing-adhoc-1",
        message="fix: quick fix",
        author="Dev",
        platform_id="madruga-ai",
        epic_id=None,
        source="hook",
        committed_at="2026-04-03T10:00:00Z",
        files_json="[]",
    )

    # Verify DB is populated
    total = tmp_db.execute("SELECT COUNT(*) FROM commits").fetchone()[0]
    assert total == 3

    # Query for a non-existent epic — must return empty list, no error
    results = get_commits_by_epic(tmp_db, "999-nonexistent-epic")
    assert results == []
    assert isinstance(results, list)

    # Also verify with platform filter — still empty, no error
    results_filtered = get_commits_by_epic(tmp_db, "999-nonexistent-epic", platform_id="madruga-ai")
    assert results_filtered == []

    # Sanity: real epics still return their commits (no side effects)
    assert len(get_commits_by_epic(tmp_db, "012-whatsapp-daemon")) == 1
    assert len(get_commits_by_epic(tmp_db, "023-commit-traceability")) == 1


# ══════════════════════════════════════
# get_commit_stats tests (T1 — missing tests found by judge)
# ══════════════════════════════════════


def test_get_commit_stats_with_data(tmp_db):
    """get_commit_stats returns correct totals, per-epic breakdown, and adhoc percentage."""
    from db_pipeline import get_commit_stats

    _seed_commits(tmp_db)
    tmp_db.commit()

    stats = get_commit_stats(tmp_db)
    # _seed_commits creates: 3 (epic 012 p1) + 2 (epic 023 p1) + 2 (adhoc p1)
    #   + 1 (epic 012 p2) + 1 (adhoc p2) = 9 total
    assert stats["total_commits"] == 9
    assert stats["commits_per_epic"]["012-whatsapp-daemon"] == 4  # 3 p1 + 1 p2
    assert stats["commits_per_epic"]["023-commit-traceability"] == 2
    assert stats["adhoc_count"] == 3  # 2 p1 + 1 p2
    assert stats["adhoc_percentage"] == round(3 / 9 * 100, 1)


def test_get_commit_stats_with_platform_filter(tmp_db):
    """get_commit_stats filters correctly by platform_id."""
    from db_pipeline import get_commit_stats

    _seed_commits(tmp_db)
    tmp_db.commit()

    stats = get_commit_stats(tmp_db, platform_id="p1")
    # p1 has: 3 (epic 012) + 2 (epic 023) + 2 (adhoc) = 7
    assert stats["total_commits"] == 7
    assert stats["commits_per_epic"]["012-whatsapp-daemon"] == 3
    assert stats["commits_per_epic"]["023-commit-traceability"] == 2
    assert stats["adhoc_count"] == 2
    assert stats["adhoc_percentage"] == round(2 / 7 * 100, 1)


def test_get_commit_stats_empty_db(tmp_db):
    """get_commit_stats on empty DB returns zeroes without error."""
    from db_pipeline import get_commit_stats, upsert_platform

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")

    stats = get_commit_stats(tmp_db)
    assert stats["total_commits"] == 0
    assert stats["commits_per_epic"] == {}
    assert stats["adhoc_count"] == 0
    assert stats["adhoc_percentage"] == 0.0
