"""Tests for reverse_reconcile_mark.py — atomic, idempotent, composite SHA handling."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def fresh_db(tmp_path):
    import db_core

    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    migrations_dir = Path(__file__).resolve().parents[3] / ".pipeline" / "migrations"
    db_core.migrate(conn, migrations_dir)
    conn.close()
    return db_file


def _seed(db_file: Path, rows: list[tuple]):
    """rows: (sha, platform, epic_id, reconciled)."""
    conn = sqlite3.connect(str(db_file))
    for sha, plat, epic, rec in rows:
        conn.execute(
            "INSERT INTO commits (sha, message, author, platform_id, epic_id, source, committed_at, reconciled_at) "
            "VALUES (?, 'm', 'a', ?, ?, 'hook', '2026-01-01T00:00:00Z', ?)",
            (sha, plat, epic, rec),
        )
    conn.commit()
    conn.close()


def test_mark_shas_updates_only_listed(fresh_db):
    from reverse_reconcile_mark import mark_shas

    _seed(
        fresh_db,
        [
            ("sha1", "plat", None, None),
            ("sha2", "plat", None, None),
            ("sha3", "plat", None, None),
        ],
    )
    n = mark_shas("plat", ["sha1", "sha3"], db_path=fresh_db)
    assert n == 2
    conn = sqlite3.connect(str(fresh_db))
    unreconciled = {r[0] for r in conn.execute("SELECT sha FROM commits WHERE reconciled_at IS NULL").fetchall()}
    conn.close()
    assert unreconciled == {"sha2"}


def test_mark_shas_handles_composite(fresh_db):
    from reverse_reconcile_mark import mark_shas

    _seed(fresh_db, [("abc:plat", "plat", None, None)])
    n = mark_shas("plat", ["abc"], db_path=fresh_db)
    assert n == 1


def test_mark_shas_idempotent(fresh_db):
    from reverse_reconcile_mark import mark_shas

    _seed(fresh_db, [("sha1", "plat", None, None)])
    assert mark_shas("plat", ["sha1"], db_path=fresh_db) == 1
    # Second run → no rows updated (already reconciled)
    assert mark_shas("plat", ["sha1"], db_path=fresh_db) == 0


def test_mark_shas_respects_platform_boundary(fresh_db):
    from reverse_reconcile_mark import mark_shas

    _seed(
        fresh_db,
        [("sha1", "plat_a", None, None), ("sha1b", "plat_b", None, None)],
    )
    # Only plat_a should be touched even if sha1 uniqueness is global
    n = mark_shas("plat_a", ["sha1"], db_path=fresh_db)
    assert n == 1
    conn = sqlite3.connect(str(fresh_db))
    b_rec = conn.execute("SELECT reconciled_at FROM commits WHERE sha='sha1b'").fetchone()[0]
    conn.close()
    assert b_rec is None


def test_mark_epic_updates_all_epic_commits(fresh_db):
    from reverse_reconcile_mark import mark_epic

    _seed(
        fresh_db,
        [
            ("e1", "plat", "001-foo", None),
            ("e2", "plat", "001-foo", None),
            ("e3", "plat", "002-bar", None),
        ],
    )
    n = mark_epic("plat", "001-foo", db_path=fresh_db)
    assert n == 2


def test_count_unreconciled(fresh_db):
    from reverse_reconcile_mark import count_unreconciled

    _seed(
        fresh_db,
        [
            ("a", "plat", None, None),
            ("b", "plat", None, "2026-01-01T00:00:00Z"),
            ("c", "plat", None, None),
        ],
    )
    assert count_unreconciled("plat", db_path=fresh_db) == 2


def test_empty_shas_returns_zero(fresh_db):
    from reverse_reconcile_mark import mark_shas

    assert mark_shas("plat", [], db_path=fresh_db) == 0
