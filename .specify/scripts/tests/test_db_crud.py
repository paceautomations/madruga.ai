"""Tests for db.py CRUD functions."""


def test_upsert_get_platform(tmp_db):
    from db import upsert_platform, get_platform

    upsert_platform(tmp_db, "test", name="Test", repo_path="platforms/test")
    p = get_platform(tmp_db, "test")
    assert p is not None
    assert p["platform_id"] == "test"
    assert p["name"] == "Test"
    assert p["lifecycle"] == "design"


def test_upsert_platform_idempotent(tmp_db):
    from db import upsert_platform, get_platform

    upsert_platform(tmp_db, "test", name="Test", repo_path="platforms/test")
    upsert_platform(tmp_db, "test", name="Test Updated", repo_path="platforms/test")
    p = get_platform(tmp_db, "test")
    assert p["name"] == "Test Updated"
    count = tmp_db.execute(
        "SELECT COUNT(*) FROM platforms WHERE platform_id='test'"
    ).fetchone()[0]
    assert count == 1


def test_upsert_get_pipeline_node(tmp_db):
    from db import upsert_platform, upsert_pipeline_node, get_pipeline_nodes

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_pipeline_node(tmp_db, "p1", "vision", "done", output_hash="sha256:abc123")
    nodes = get_pipeline_nodes(tmp_db, "p1")
    assert len(nodes) == 1
    assert nodes[0]["status"] == "done"
    assert nodes[0]["output_hash"] == "sha256:abc123"


def test_upsert_get_epic(tmp_db):
    from db import upsert_platform, upsert_epic, get_epics

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "001-test", title="Test Epic", status="proposed")
    epics = get_epics(tmp_db, "p1")
    assert len(epics) == 1
    assert epics[0]["title"] == "Test Epic"


def test_upsert_get_epic_node(tmp_db):
    from db import upsert_platform, upsert_epic, upsert_epic_node, get_epic_nodes

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "001-test", title="Test")
    upsert_epic_node(tmp_db, "p1", "001-test", "specify", "done")
    nodes = get_epic_nodes(tmp_db, "p1", "001-test")
    assert len(nodes) == 1
    assert nodes[0]["status"] == "done"


def test_insert_decision_auto_id(tmp_db):
    from db import upsert_platform, insert_decision, get_decisions

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    did = insert_decision(
        tmp_db, "p1", "vision", "Test Decision", decisions=["chose A over B"]
    )
    assert len(did) == 8  # hex of 4 bytes
    decs = get_decisions(tmp_db, "p1")
    assert len(decs) == 1
    assert decs[0]["title"] == "Test Decision"


def test_insert_provenance(tmp_db):
    from db import upsert_platform, insert_provenance, get_provenance

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    insert_provenance(
        tmp_db, "p1", "business/vision.md", "vision", output_hash="sha256:abc"
    )
    provs = get_provenance(tmp_db, "p1")
    assert len(provs) == 1
    assert provs[0]["generated_by"] == "vision"


def test_insert_complete_run(tmp_db):
    from db import upsert_platform, insert_run, complete_run, get_runs

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    rid = insert_run(tmp_db, "p1", "vision", agent="claude-opus-4-6")
    runs = get_runs(tmp_db, "p1")
    assert len(runs) == 1
    assert runs[0]["status"] == "running"
    complete_run(
        tmp_db, rid, "completed", tokens_in=1000, tokens_out=500, cost_usd=0.05
    )
    runs = get_runs(tmp_db, "p1")
    assert runs[0]["status"] == "completed"
    assert runs[0]["tokens_in"] == 1000


def test_insert_get_events(tmp_db):
    from db import upsert_platform, insert_event, get_events

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    eid = insert_event(tmp_db, "p1", "platform", "p1", "created", actor="human")
    assert eid is not None
    events = get_events(tmp_db, "p1")
    assert len(events) == 1
    assert events[0]["action"] == "created"
    assert events[0]["actor"] == "human"


def test_get_stale_nodes(tmp_db):
    from db import upsert_platform, upsert_pipeline_node, get_stale_nodes

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_pipeline_node(
        tmp_db, "p1", "vision", "done", completed_at="2026-03-01T00:00:00Z"
    )
    upsert_pipeline_node(
        tmp_db, "p1", "solution-overview", "done", completed_at="2026-03-02T00:00:00Z"
    )
    # vision was regenerated AFTER solution-overview
    upsert_pipeline_node(
        tmp_db, "p1", "vision", "done", completed_at="2026-03-10T00:00:00Z"
    )
    dag_edges = {"solution-overview": ["vision"]}
    stale = get_stale_nodes(tmp_db, "p1", dag_edges)
    assert len(stale) == 1
    assert stale[0]["node_id"] == "solution-overview"


def test_get_platform_status(tmp_db):
    from db import upsert_platform, upsert_pipeline_node, get_platform_status

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
    from db import upsert_platform, upsert_epic, upsert_epic_node, get_epic_status

    upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
    upsert_epic(tmp_db, "p1", "001-test", title="Test")
    upsert_epic_node(tmp_db, "p1", "001-test", "specify", "done")
    upsert_epic_node(tmp_db, "p1", "001-test", "plan", "pending")
    status = get_epic_status(tmp_db, "p1", "001-test")
    assert status["total_nodes"] == 2
    assert status["done"] == 1
    assert status["progress_pct"] == 50.0
