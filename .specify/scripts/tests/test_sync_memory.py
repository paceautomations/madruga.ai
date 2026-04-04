"""Tests for sync_memory.py — memory import/export round-trips via db_decisions."""

import sqlite3
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from db_core import migrate
from db_decisions import (
    export_memory_to_markdown,
    get_memories,
    import_memory_from_markdown,
    sync_memories_to_markdown,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_db() -> sqlite3.Connection:
    """Create an in-memory SQLite DB with all migrations applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn


def _write_memory_md(path: Path, name: str, type_: str, description: str, body: str) -> Path:
    """Write a memory markdown file with valid frontmatter."""
    content = f"---\nname: {name}\ntype: {type_}\ndescription: {description}\n---\n\n{body}\n"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestImportMemory:
    """Test import_memory_from_markdown()."""

    def test_import_basic_frontmatter(self, tmp_path):
        conn = _init_db()
        md_file = _write_memory_md(
            tmp_path / "user_role.md",
            name="User Role",
            type_="user",
            description="Role info",
            body="The user is a senior engineer.",
        )

        result = import_memory_from_markdown(conn, md_file)
        assert result is not None  # returns memory_id

        rows = get_memories(conn)
        assert len(rows) == 1
        assert rows[0]["name"] == "User Role"
        assert rows[0]["type"] == "user"
        assert rows[0]["content"] == "The user is a senior engineer."

    def test_malformed_frontmatter_skipped(self, tmp_path):
        md_file = tmp_path / "broken.md"
        md_file.write_text("---\nkey: [unclosed\n---\n\nBody text.\n", encoding="utf-8")

        conn = _init_db()
        result = import_memory_from_markdown(conn, md_file)

        # Should return None (graceful skip), not crash
        assert result is None
        assert get_memories(conn) == []


class TestAllTypesRoundTrip:
    """Test that all four memory types survive import → DB → export."""

    def test_all_four_types_round_trip(self, tmp_path):
        conn = _init_db()
        types = ["user", "feedback", "project", "reference"]

        for t in types:
            md_file = _write_memory_md(
                tmp_path / f"{t}_test.md",
                name=f"Test {t}",
                type_=t,
                description=f"A {t} memory",
                body=f"Content for {t} type.",
            )
            mid = import_memory_from_markdown(conn, md_file)
            assert mid is not None, f"Failed to import type={t}"

        # Verify all 4 in DB
        rows = get_memories(conn)
        assert len(rows) == 4
        db_types = {r["type"] for r in rows}
        assert db_types == set(types)

        # Export each and verify type preserved
        export_dir = tmp_path / "exported"
        for row in rows:
            out_path = export_memory_to_markdown(conn, row["memory_id"], export_dir)
            text = out_path.read_text(encoding="utf-8")
            parts = text.split("---", 2)
            fm = yaml.safe_load(parts[1])
            assert fm["type"] == row["type"]


class TestExportProducesValidFrontmatter:
    """Test export_memory_to_markdown() output structure."""

    def test_export_produces_valid_frontmatter(self, tmp_path):
        conn = _init_db()
        md_file = _write_memory_md(
            tmp_path / "feedback_testing.md",
            name="Testing Feedback",
            type_="feedback",
            description="How to test",
            body="Always write tests first.",
        )
        mid = import_memory_from_markdown(conn, md_file)

        export_dir = tmp_path / "out"
        out_path = export_memory_to_markdown(conn, mid, export_dir)

        text = out_path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        parts = text.split("---", 2)
        fm = yaml.safe_load(parts[1])

        assert "name" in fm
        assert "type" in fm
        assert "description" in fm
        assert fm["name"] == "Testing Feedback"
        assert fm["type"] == "feedback"


class TestFullRoundTrip:
    """Test import → export → re-import preserves data."""

    def test_full_round_trip_no_data_loss(self, tmp_path):
        conn = _init_db()
        original_name = "Project Context"
        original_type = "project"
        original_desc = "Current project state"
        original_body = "Epic 020 is in progress.\n\nMultiple phases planned."

        md_file = _write_memory_md(
            tmp_path / "project_context.md",
            name=original_name,
            type_=original_type,
            description=original_desc,
            body=original_body,
        )
        mid = import_memory_from_markdown(conn, md_file)

        # Export
        export_dir = tmp_path / "round_trip"
        out_path = export_memory_to_markdown(conn, mid, export_dir)

        # Re-import from exported file into a fresh DB
        conn2 = _init_db()
        mid2 = import_memory_from_markdown(conn2, out_path)
        assert mid2 is not None

        rows = get_memories(conn2)
        assert len(rows) == 1
        row = rows[0]
        assert row["name"] == original_name
        assert row["type"] == original_type
        assert row["description"] == original_desc
        assert row["content"] == original_body


class TestMemoryIndexUpdate:
    """Test sync_memories_to_markdown exports all entries."""

    def test_memory_index_update(self, tmp_path):
        conn = _init_db()

        # Import two memory files
        for i, t in enumerate(["user", "reference"]):
            _write_memory_md(
                tmp_path / f"{t}_{i}.md",
                name=f"Entry {i}",
                type_=t,
                description=f"Description {i}",
                body=f"Body {i}.",
            )
            import_memory_from_markdown(conn, tmp_path / f"{t}_{i}.md")

        # Export all to a directory
        export_dir = tmp_path / "sync_out"
        count = sync_memories_to_markdown(conn, export_dir)

        assert count == 2
        exported_files = list(export_dir.glob("*.md"))
        assert len(exported_files) == 2
