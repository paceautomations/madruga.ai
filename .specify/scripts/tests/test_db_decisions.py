"""Tests for decisions, memory, and FTS5 features in db.py.

ADR frontmatter variations documented from T001 survey (2026-03-29):
- All 19 Fulano ADRs use consistent frontmatter: title, status, decision, alternatives, rationale
- Section headers: ## Contexto (33), ## Decisao (32), ## Alternativas consideradas (32), ## Consequencias (32)
- Some ADRs have extra sections: ## Referencias, ## Regras obrigatorias, etc.
- Frontmatter values are quoted strings or plain text
- Status values: Accepted (18), Proposed (1)
"""

from pathlib import Path

import pytest


# ══════════════════════════════════════
# T004: migrate() trigger handling
# ══════════════════════════════════════


def test_migrate_handles_trigger_bodies(tmp_path):
    """migrate() should handle CREATE TRIGGER ... END; blocks without breaking."""
    from db import get_conn, migrate

    db_path = tmp_path / "test.db"
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()

    # Write a migration with a trigger
    (mig_dir / "001_test.sql").write_text(
        "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT, name_upper TEXT);\n"
        "CREATE TRIGGER items_upper AFTER INSERT ON items BEGIN\n"
        "    UPDATE items SET name_upper = UPPER(NEW.name) WHERE id = NEW.id;\n"
        "END;\n"
    )
    conn = get_conn(db_path)
    migrate(conn, mig_dir)

    # Verify trigger works
    conn.execute("INSERT INTO items (name) VALUES ('hello')")
    row = conn.execute("SELECT name_upper FROM items WHERE name='hello'").fetchone()
    assert row[0] == "HELLO"
    conn.close()


# ══════════════════════════════════════
# T005: New decision columns
# ══════════════════════════════════════


def test_insert_decision_new_columns(tmp_db):
    from db import insert_decision, upsert_platform

    upsert_platform(tmp_db, "test", name="Test", repo_path="platforms/test")
    did = insert_decision(
        tmp_db,
        "test",
        "adr",
        "Test ADR",
        number=1,
        decision_type="technology",
        context="We need a framework",
        consequences="Less flexibility",
        tags_json='["python", "framework"]',
        content_hash="sha256:abc123",
    )
    row = tmp_db.execute("SELECT * FROM decisions WHERE decision_id=?", (did,)).fetchone()
    d = dict(row)
    assert d["decision_type"] == "technology"
    assert d["context"] == "We need a framework"
    assert d["consequences"] == "Less flexibility"
    assert d["tags_json"] == '["python", "framework"]'
    assert d["content_hash"] == "sha256:abc123"


# ══════════════════════════════════════
# T006: Memory CRUD
# ══════════════════════════════════════


def test_insert_get_memory(tmp_db):
    from db import insert_memory, get_memories, upsert_platform

    upsert_platform(tmp_db, "test", name="Test", repo_path="platforms/test")
    mid = insert_memory(tmp_db, "feedback", "no-summaries", "Don't summarize", platform_id="test")
    assert mid
    memories = get_memories(tmp_db, type_="feedback")
    assert len(memories) == 1
    assert memories[0]["name"] == "no-summaries"
    assert memories[0]["content"] == "Don't summarize"


def test_update_memory(tmp_db):
    from db import insert_memory, update_memory, get_memories

    mid = insert_memory(tmp_db, "project", "sprint-goal", "Ship feature X")
    update_memory(tmp_db, mid, content="Ship feature Y")
    memories = get_memories(tmp_db)
    assert memories[0]["content"] == "Ship feature Y"


def test_delete_memory(tmp_db):
    from db import insert_memory, delete_memory, get_memories

    mid = insert_memory(tmp_db, "user", "role", "Data scientist")
    delete_memory(tmp_db, mid)
    assert len(get_memories(tmp_db)) == 0


# ══════════════════════════════════════
# T007: Decision links CRUD
# ══════════════════════════════════════


def test_insert_get_decision_link(tmp_db):
    from db import insert_decision, insert_decision_link, get_decision_links, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    a = insert_decision(tmp_db, "p", "adr", "Decision A")
    b = insert_decision(tmp_db, "p", "adr", "Decision B")
    insert_decision_link(tmp_db, a, b, "supersedes")
    links = get_decision_links(tmp_db, a)
    assert len(links) == 1
    assert links[0]["to_decision_id"] == b
    assert links[0]["link_type"] == "supersedes"


# ══════════════════════════════════════
# T008: get_decisions with filters
# ══════════════════════════════════════


def test_get_decisions_filter_status(tmp_db):
    from db import insert_decision, get_decisions, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    insert_decision(tmp_db, "p", "adr", "Accepted one", status="accepted")
    insert_decision(tmp_db, "p", "adr", "Proposed one", status="proposed")
    accepted = get_decisions(tmp_db, "p", status="accepted")
    assert len(accepted) == 1
    assert accepted[0]["title"] == "Accepted one"


def test_get_decisions_filter_type(tmp_db):
    from db import insert_decision, get_decisions, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    insert_decision(tmp_db, "p", "adr", "Tech choice", decision_type="technology")
    insert_decision(tmp_db, "p", "blueprint", "Arch choice", decision_type="architecture")
    tech = get_decisions(tmp_db, "p", decision_type="technology")
    assert len(tech) == 1
    assert tech[0]["title"] == "Tech choice"


# ══════════════════════════════════════
# T015: Export decision to markdown
# ══════════════════════════════════════


def test_export_decision_to_markdown(tmp_db, tmp_path):
    from db import insert_decision, export_decision_to_markdown, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    out_dir = tmp_path / "decisions"
    out_dir.mkdir()
    did = insert_decision(
        tmp_db,
        "p",
        "adr",
        "ADR-001: Test decision",
        number=1,
        slug="test-decision",
        status="accepted",
        decision_type="technology",
        context="We need to choose a framework.",
        consequences="- [+] Fast\n- [-] Less flexible",
    )
    path = export_decision_to_markdown(tmp_db, did, out_dir)
    assert path.exists()
    assert path.name == "ADR-001-test-decision.md"
    content = path.read_text()
    assert "## Contexto" in content
    assert "## Decisao" in content
    assert "## Consequencias" in content
    assert "We need to choose a framework." in content
    # Check frontmatter
    assert "title:" in content
    assert "status: Accepted" in content


# ══════════════════════════════════════
# T016: Batch export
# ══════════════════════════════════════


def test_sync_decisions_to_markdown(tmp_db, tmp_path):
    from db import insert_decision, sync_decisions_to_markdown, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    out_dir = tmp_path / "decisions"
    out_dir.mkdir()
    for i in range(1, 4):
        insert_decision(
            tmp_db,
            "p",
            "adr",
            f"ADR-{i:03d}: Decision {i}",
            number=i,
            slug=f"decision-{i}",
            status="accepted",
            context=f"Context {i}",
            consequences=f"Consequence {i}",
        )
    count = sync_decisions_to_markdown(tmp_db, "p", out_dir)
    assert count == 3
    assert len(list(out_dir.glob("ADR-*.md"))) == 3


# ══════════════════════════════════════
# T017: Supersede chain
# ══════════════════════════════════════


def test_supersede_chain(tmp_db):
    from db import insert_decision, get_decisions, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    a = insert_decision(tmp_db, "p", "adr", "Old choice", status="accepted")
    b = insert_decision(tmp_db, "p", "adr", "New choice", status="accepted")
    # Supersede A with B
    tmp_db.execute(
        "UPDATE decisions SET status='superseded', superseded_by=? WHERE decision_id=?",
        (b, a),
    )
    tmp_db.commit()
    decisions = get_decisions(tmp_db, "p")
    old = [d for d in decisions if d["decision_id"] == a][0]
    assert old["status"] == "superseded"
    assert old["superseded_by"] == b


# ══════════════════════════════════════
# T022-T025: Import ADR from markdown
# ══════════════════════════════════════


def _make_adr_file(path: Path, number: int = 1, title: str = "Test", status: str = "Accepted"):
    path.write_text(
        f'---\ntitle: "ADR-{number:03d}: {title}"\nstatus: {status}\n'
        f'decision: "Use {title}"\nalternatives: "Alt1, Alt2"\n'
        f'rationale: "Because reasons"\n---\n'
        f"# ADR-{number:03d}: {title}\n"
        f"**Status:** {status} | **Data:** 2026-03-29\n\n"
        f"## Contexto\nWe need {title}.\n\n"
        f"## Decisao\nWe chose {title}.\n\n"
        f"## Alternativas consideradas\n### Alt1\n- Pros: Good\n- Cons: Bad\n\n"
        f"## Consequencias\n- [+] Fast\n- [-] Complex\n"
    )


def test_parse_adr_markdown(tmp_path):
    from db import _parse_adr_markdown

    adr_path = tmp_path / "ADR-001-test.md"
    _make_adr_file(adr_path, 1, "Framework")
    result = _parse_adr_markdown(adr_path)
    assert result["title"] == "ADR-001: Framework"
    assert result["status"] == "Accepted"
    assert result["decision"] == "Use Framework"
    assert "We need Framework." in result["context"]
    assert "Fast" in result["consequences"]


def test_import_adr_from_markdown(tmp_db, tmp_path):
    from db import import_adr_from_markdown, get_decisions, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    adr_path = tmp_path / "ADR-001-test.md"
    _make_adr_file(adr_path)
    did = import_adr_from_markdown(tmp_db, adr_path, "p")
    decisions = get_decisions(tmp_db, "p")
    assert len(decisions) == 1
    assert decisions[0]["decision_id"] == did


def test_import_adr_idempotent(tmp_db, tmp_path):
    from db import import_adr_from_markdown, get_decisions, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    adr_path = tmp_path / "ADR-001-test.md"
    _make_adr_file(adr_path)
    import_adr_from_markdown(tmp_db, adr_path, "p")
    import_adr_from_markdown(tmp_db, adr_path, "p")
    decisions = get_decisions(tmp_db, "p")
    assert len(decisions) == 1


def test_import_all_adrs(tmp_db, tmp_path):
    from db import import_all_adrs, get_decisions, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    decisions_dir = tmp_path / "decisions"
    decisions_dir.mkdir()
    for i in range(1, 4):
        _make_adr_file(decisions_dir / f"ADR-{i:03d}-test-{i}.md", i, f"Tech{i}")
    count = import_all_adrs(tmp_db, "p", decisions_dir)
    assert count == 3
    assert len(get_decisions(tmp_db, "p")) == 3


def test_import_malformed_frontmatter(tmp_db, tmp_path):
    from db import import_adr_from_markdown, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    bad_path = tmp_path / "ADR-999-bad.md"
    bad_path.write_text("---\ntitle: [broken yaml\n---\n# Bad\n")
    result = import_adr_from_markdown(tmp_db, bad_path, "p")
    assert result is None  # Should skip, not crash


# ══════════════════════════════════════
# T031-T032: FTS5 search
# ══════════════════════════════════════


def test_search_decisions_fts5(tmp_db):
    from db import insert_decision, search_decisions, upsert_platform, _check_fts5

    if not _check_fts5():
        pytest.skip("FTS5 not available")
    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    insert_decision(
        tmp_db,
        "p",
        "adr",
        "Redis choice",
        context="We need a message queue for async processing",
        consequences="Redis streams selected",
    )
    insert_decision(
        tmp_db,
        "p",
        "adr",
        "Database choice",
        context="We need a relational database for persistence",
        consequences="PostgreSQL selected",
    )
    results = search_decisions(tmp_db, "message queue")
    assert len(results) >= 1
    assert "Redis" in results[0]["title"]


def test_fts5_trigger_sync(tmp_db):
    from db import insert_decision, upsert_platform, _check_fts5

    if not _check_fts5():
        pytest.skip("FTS5 not available")
    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    insert_decision(
        tmp_db,
        "p",
        "adr",
        "Unique findable title xyz123",
        context="Very specific context abc789",
    )
    # Verify FTS has the data
    row = tmp_db.execute("SELECT * FROM decisions_fts WHERE decisions_fts MATCH 'abc789'").fetchone()
    assert row is not None


# ══════════════════════════════════════
# T036-T039: Memory import/export/search
# ══════════════════════════════════════


def _make_memory_file(path: Path, name: str = "test", type_: str = "feedback"):
    path.write_text(f"---\nname: {name}\ndescription: A test memory\ntype: {type_}\n---\n\nContent of {name} memory.\n")


def test_parse_memory_markdown(tmp_path):
    from db import _parse_memory_markdown

    mem_path = tmp_path / "test.md"
    _make_memory_file(mem_path, "my-rule", "feedback")
    result = _parse_memory_markdown(mem_path)
    assert result["name"] == "my-rule"
    assert result["type"] == "feedback"
    assert "Content of my-rule" in result["content"]


def test_import_memory_from_markdown(tmp_db, tmp_path):
    from db import import_memory_from_markdown, get_memories

    mem_path = tmp_path / "test.md"
    _make_memory_file(mem_path)
    mid = import_memory_from_markdown(tmp_db, mem_path)
    assert mid is not None
    memories = get_memories(tmp_db)
    assert len(memories) == 1


def test_import_memory_idempotent(tmp_db, tmp_path):
    from db import import_memory_from_markdown, get_memories

    mem_path = tmp_path / "test.md"
    _make_memory_file(mem_path)
    import_memory_from_markdown(tmp_db, mem_path)
    import_memory_from_markdown(tmp_db, mem_path)
    assert len(get_memories(tmp_db)) == 1


def test_export_memory_to_markdown(tmp_db, tmp_path):
    from db import insert_memory, export_memory_to_markdown

    mid = insert_memory(tmp_db, "feedback", "no-summaries", "Don't summarize responses")
    out_dir = tmp_path / "memory"
    out_dir.mkdir()
    path = export_memory_to_markdown(tmp_db, mid, out_dir)
    assert path.exists()
    content = path.read_text()
    assert "name: no-summaries" in content
    assert "type: feedback" in content
    assert "Don't summarize responses" in content


def test_search_memories_fts5(tmp_db):
    from db import insert_memory, search_memories, _check_fts5

    if not _check_fts5():
        pytest.skip("FTS5 not available")
    insert_memory(tmp_db, "feedback", "terse-responses", "User wants short replies without summaries")
    insert_memory(tmp_db, "project", "sprint-goal", "Ship the billing feature by Friday")
    results = search_memories(tmp_db, "summaries")
    assert len(results) >= 1
    assert results[0]["name"] == "terse-responses"


# ══════════════════════════════════════
# T046-T047: Decision links bidirectional + type filtering
# ══════════════════════════════════════


def test_decision_link_bidirectional(tmp_db):
    from db import insert_decision, insert_decision_link, get_decision_links, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    a = insert_decision(tmp_db, "p", "adr", "A")
    b = insert_decision(tmp_db, "p", "adr", "B")
    insert_decision_link(tmp_db, a, b, "supersedes")
    from_a = get_decision_links(tmp_db, a, direction="from")
    from_b = get_decision_links(tmp_db, b, direction="to")
    assert len(from_a) == 1
    assert len(from_b) == 1
    both = get_decision_links(tmp_db, a, direction="both")
    assert len(both) == 1


def test_decision_link_type_filter(tmp_db):
    from db import insert_decision, insert_decision_link, get_decision_links, upsert_platform

    upsert_platform(tmp_db, "p", name="P", repo_path="platforms/p")
    a = insert_decision(tmp_db, "p", "adr", "A")
    b = insert_decision(tmp_db, "p", "adr", "B")
    c = insert_decision(tmp_db, "p", "adr", "C")
    insert_decision_link(tmp_db, a, b, "supersedes")
    insert_decision_link(tmp_db, a, c, "depends_on")
    supersedes = get_decision_links(tmp_db, a, link_type="supersedes")
    assert len(supersedes) == 1
    assert supersedes[0]["link_type"] == "supersedes"
