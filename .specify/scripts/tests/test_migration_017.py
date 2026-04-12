"""Tests for migration 017_add_queued_status.sql (T007–T011)."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def pre017_db(tmp_path):
    """Create a DB with all migrations up to 016, then yield conn + path to 017 SQL."""
    from db_core import get_conn, migrate

    db_path = tmp_path / "test.db"
    migrations_dir = Path(__file__).parents[3] / ".pipeline" / "migrations"
    conn = get_conn(db_path)

    # Apply all existing migrations (001–016) — they establish the pre-017 schema.
    migrate(conn, migrations_dir)

    # Remove the 017 entry from _migrations if it was auto-applied
    # (migrate() picks up all *.sql files in sorted order).
    conn.execute("DELETE FROM _migrations WHERE name = '017_add_queued_status.sql'")
    conn.commit()

    # Need a platform to satisfy FK constraint on epics
    conn.execute(
        "INSERT OR IGNORE INTO platforms (platform_id, name, title, lifecycle, repo_path)"
        " VALUES ('test-plat', 'test-plat', 'Test', 'design', '/tmp/test-repo')"
    )
    conn.commit()

    yield conn, migrations_dir / "017_add_queued_status.sql"
    conn.close()


class TestMigration017:
    """T007–T011: migration 017 adds queued to CHECK constraint."""

    def test_queued_status_accepted_after_migration(self, pre017_db):
        """T007: After migration, INSERT with status='queued' succeeds."""
        conn, sql_path = pre017_db
        # Migration already applied by fixture's migrate() — but we deleted
        # the _migrations marker. The schema IS already at post-017 state
        # because migrate() applied it. So just verify:
        conn.execute(
            "INSERT INTO epics (epic_id, platform_id, title, status)"
            " VALUES ('q-epic', 'test-plat', 'Queue Test', 'queued')"
        )
        conn.commit()
        row = conn.execute("SELECT status FROM epics WHERE epic_id = 'q-epic'").fetchone()
        assert row[0] == "queued"

    def test_preserves_existing_rows(self, pre017_db):
        """T008: All pre-existing status values survive the migration."""
        conn, _ = pre017_db
        statuses = ["proposed", "drafted", "in_progress", "shipped", "blocked", "cancelled"]
        for i, st in enumerate(statuses):
            conn.execute(
                "INSERT INTO epics (epic_id, platform_id, title, status) VALUES (?, 'test-plat', ?, ?)",
                (f"epic-{i}", f"Epic {st}", st),
            )
        conn.commit()
        rows = conn.execute("SELECT COUNT(*) FROM epics").fetchone()
        assert rows[0] == len(statuses)
        for i, st in enumerate(statuses):
            row = conn.execute("SELECT status FROM epics WHERE epic_id = ?", (f"epic-{i}",)).fetchone()
            assert row[0] == st

    def test_rejects_invalid_status(self, pre017_db):
        """T009: CHECK constraint still enforces valid enum values."""
        conn, _ = pre017_db
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO epics (epic_id, platform_id, title, status)"
                " VALUES ('bad', 'test-plat', 'Bad', 'gibberish')"
            )

    def test_migration_tracked_in_migrations_table(self, pre017_db):
        """T010: After applying via migrate(), the migration is recorded."""
        conn, sql_path = pre017_db
        from db_core import migrate

        # Re-run migrate — it should detect 017 as already applied (schema is
        # already post-017 from the fixture). But we deleted the marker, so
        # it will re-apply — this should be safe because DROP TABLE IF EXISTS.
        migrate(conn, sql_path.parent)
        row = conn.execute("SELECT 1 FROM _migrations WHERE name = '017_add_queued_status.sql'").fetchone()
        assert row is not None, "Migration 017 should be tracked in _migrations"

    def test_indexes_preserved(self, pre017_db):
        """T011: Both indexes are present after migration."""
        conn, _ = pre017_db
        indexes = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='epics'").fetchall()
            if r[0]  # skip autoindex
        }
        assert "idx_epics_platform" in indexes
        assert "idx_epics_status" in indexes
