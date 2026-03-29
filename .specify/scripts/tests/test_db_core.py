"""Tests for db.py core functions: connection, migration, hashing."""

from pathlib import Path


def test_get_conn_creates_db(tmp_path):
    from db import get_conn

    db_path = tmp_path / "sub" / "test.db"
    conn = get_conn(db_path)
    assert db_path.exists()
    conn.close()


def test_get_conn_wal_mode(tmp_path):
    from db import get_conn

    conn = get_conn(tmp_path / "test.db")
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    conn.close()


def test_get_conn_foreign_keys(tmp_path):
    from db import get_conn

    conn = get_conn(tmp_path / "test.db")
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1
    conn.close()


def test_migrate_creates_tables(tmp_db):
    tables = [
        r[0]
        for r in tmp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
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
    from db import migrate

    migrations_dir = (
        Path(__file__).parent.parent.parent.parent / ".pipeline" / "migrations"
    )
    migrate(tmp_db, migrations_dir)  # second run
    tables = [
        r[0]
        for r in tmp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    assert len(tables) >= 9


def test_migrate_tracks_applied(tmp_db):
    applied = tmp_db.execute("SELECT name FROM _migrations").fetchall()
    assert len(applied) >= 1
    assert applied[0][0] == "001_initial.sql"


def test_compute_file_hash_consistent(tmp_path):
    from db import compute_file_hash

    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h1 = compute_file_hash(f)
    h2 = compute_file_hash(f)
    assert h1 == h2


def test_compute_file_hash_format(tmp_path):
    from db import compute_file_hash

    f = tmp_path / "test.txt"
    f.write_text("hello")
    h = compute_file_hash(f)
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 12


def test_compute_file_hash_differs(tmp_path):
    from db import compute_file_hash

    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("aaa")
    f2.write_text("bbb")
    assert compute_file_hash(f1) != compute_file_hash(f2)
