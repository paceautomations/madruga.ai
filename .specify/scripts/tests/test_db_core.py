"""Tests for db_core.py: connection, migration, hashing, FTS5, transaction."""

import sqlite3
from pathlib import Path

import pytest


def test_get_conn_creates_db(tmp_path):
    from db_core import get_conn

    db_path = tmp_path / "sub" / "test.db"
    conn = get_conn(db_path)
    assert db_path.exists()
    conn.close()


def test_get_conn_wal_mode(tmp_path):
    from db_core import get_conn

    conn = get_conn(tmp_path / "test.db")
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    conn.close()


def test_get_conn_foreign_keys(tmp_path):
    from db_core import get_conn

    conn = get_conn(tmp_path / "test.db")
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1
    conn.close()


def test_migrate_creates_tables(tmp_db):
    tables = [
        r[0] for r in tmp_db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    ]
    expected = [
        "_migrations",
        "artifact_provenance",
        "decisions",
        "epic_nodes",
        "epics",
        "events",
        "pipeline_nodes",
        "pipeline_runs",
        "platforms",
    ]
    for t in expected:
        assert t in tables, f"Missing table: {t}"


def test_migrate_idempotent(tmp_db):
    from db_core import migrate

    migrations_dir = Path(__file__).parent.parent.parent.parent / ".pipeline" / "migrations"
    migrate(tmp_db, migrations_dir)  # second run
    tables = [r[0] for r in tmp_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert len(tables) >= 9


def test_migrate_tracks_applied(tmp_db):
    applied = tmp_db.execute("SELECT name FROM _migrations").fetchall()
    assert len(applied) >= 1
    assert applied[0][0] == "001_initial.sql"


def test_compute_file_hash_consistent(tmp_path):
    from db_core import compute_file_hash

    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h1 = compute_file_hash(f)
    h2 = compute_file_hash(f)
    assert h1 == h2


def test_compute_file_hash_format(tmp_path):
    from db_core import compute_file_hash

    f = tmp_path / "test.txt"
    f.write_text("hello")
    h = compute_file_hash(f)
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_compute_file_hash_differs(tmp_path):
    from db_core import compute_file_hash

    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("aaa")
    f2.write_text("bbb")
    assert compute_file_hash(f1) != compute_file_hash(f2)


MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / ".pipeline" / "migrations"


def test_closing_connection_closes_on_exit(tmp_path):
    """_ClosingConnection must close the underlying connection on __exit__."""
    from db_core import _ClosingConnection

    raw = sqlite3.connect(str(tmp_path / "test.db"))
    with _ClosingConnection(raw) as conn:
        conn.execute("SELECT 1")

    with pytest.raises(sqlite3.ProgrammingError):
        raw.execute("SELECT 1")


def test_migrate_idempotent_from_db_core(tmp_path):
    """Running migrate() twice must produce the same schema with no errors."""
    from db_core import get_conn, migrate

    conn = get_conn(tmp_path / "test.db")
    migrate(conn, MIGRATIONS_DIR)
    tables_first = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    migrate(conn, MIGRATIONS_DIR)
    tables_second = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    assert tables_first == tables_second
    conn.close()


def test_transaction_rollback_on_exception(tmp_path):
    """transaction() must rollback all writes when an exception is raised."""
    from db_core import get_conn, migrate, transaction

    conn = get_conn(tmp_path / "test.db")
    migrate(conn, MIGRATIONS_DIR)

    with pytest.raises(ValueError):
        with transaction(conn) as txn:
            txn.execute(
                "INSERT INTO platforms (platform_id, name, title, lifecycle, repo_path) VALUES (?, ?, ?, ?, ?)",
                ("rollback-test-id", "rollback-test", "Test", "design", "/tmp/rollback"),
            )
            raise ValueError("forced rollback")

    count = conn.execute("SELECT COUNT(*) FROM platforms WHERE name='rollback-test'").fetchone()[0]
    assert count == 0
    conn.close()


def test_check_fts5_returns_bool_and_is_idempotent(monkeypatch):
    """_check_fts5() must return a bool and produce the same result on repeated calls."""
    import db_core
    from db_core import _check_fts5

    # Reset singleton so the probe runs fresh
    monkeypatch.setattr(db_core, "_FTS5_AVAILABLE", None)

    result = _check_fts5()
    assert isinstance(result, bool)

    result2 = _check_fts5()
    assert result == result2
    assert db_core._FTS5_AVAILABLE is not None


def test_fts5_search_like_fallback(monkeypatch):
    """_fts5_search() must fall back to LIKE search when FTS5 is unavailable."""
    import db_core
    from db_core import _fts5_search

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, body TEXT)")
    conn.execute("INSERT INTO items (name, body) VALUES ('hello world', 'alpha')")
    conn.execute("INSERT INTO items (name, body) VALUES ('unrelated', 'beta')")
    conn.commit()

    monkeypatch.setattr(db_core, "_FTS5_AVAILABLE", False)

    results = _fts5_search(
        conn,
        "hello",
        table="items",
        fts_table="items_fts",  # does not exist — only used when FTS5 is available
        like_columns=["name", "body"],
        filters={},
    )

    assert len(results) == 1
    assert results[0]["name"] == "hello world"
    conn.close()


class TestValidateIdentifiers:
    """Tests for _validate_identifiers SQL injection guard."""

    def test_accepts_valid_identifiers(self):
        from db_core import _validate_identifiers

        _validate_identifiers("tokens_in", "cost_usd", "platform_id", "name")

    def test_rejects_sql_injection_attempt(self):
        from db_core import _validate_identifiers

        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_identifiers("name; DROP TABLE users")

    def test_rejects_uppercase(self):
        from db_core import _validate_identifiers

        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_identifiers("Name")

    def test_rejects_leading_digit(self):
        from db_core import _validate_identifiers

        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_identifiers("1column")

    def test_rejects_empty_string(self):
        from db_core import _validate_identifiers

        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_identifiers("")

    def test_rejects_hyphenated(self):
        from db_core import _validate_identifiers

        with pytest.raises(ValueError, match="Unsafe SQL identifier"):
            _validate_identifiers("some-column")
