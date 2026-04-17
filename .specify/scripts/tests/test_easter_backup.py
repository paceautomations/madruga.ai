"""Tests for periodic_backup helper in easter.py.

Regression for sqlite3.ProgrammingError when a connection created in one
thread is used from another (asyncio.to_thread runs in a worker thread).
See easter-tracking.md (epic 008-admin-evolution) for the original incident.
"""

from __future__ import annotations

import asyncio
import sqlite3

import pytest

from easter import _backup_db


def test_backup_db_creates_target_file(tmp_path):
    src = tmp_path / "src.db"
    target = tmp_path / "backup.db"

    conn = sqlite3.connect(str(src))
    conn.execute("CREATE TABLE t(x INTEGER)")
    conn.execute("INSERT INTO t VALUES (1), (2), (3)")
    conn.commit()
    conn.close()

    _backup_db(str(src), str(target))

    assert target.exists()
    out = sqlite3.connect(str(target)).execute("SELECT count(*) FROM t").fetchone()
    assert out[0] == 3


def test_backup_db_works_when_invoked_from_worker_thread(tmp_path):
    """The bug we're fixing: VACUUM INTO via asyncio.to_thread used to fail with
    sqlite3.ProgrammingError because conn was created in the event loop thread.

    By opening the connection INSIDE _backup_db (which runs in the worker
    thread), this test path now succeeds.
    """
    src = tmp_path / "src.db"
    target = tmp_path / "backup.db"

    sqlite3.connect(str(src)).execute("CREATE TABLE t(x)").connection.commit()

    async def _run():
        await asyncio.to_thread(_backup_db, str(src), str(target))

    asyncio.run(_run())
    assert target.exists()


def test_backup_db_propagates_sqlite_errors(tmp_path):
    """If the target path is invalid, the worker should surface sqlite3 errors
    rather than silently swallowing them — periodic_backup wraps the call in
    its own try/except and logs.
    """
    src = tmp_path / "src.db"
    sqlite3.connect(str(src)).close()
    bad_target = tmp_path / "nonexistent_dir" / "backup.db"

    with pytest.raises(sqlite3.OperationalError):
        _backup_db(str(src), str(bad_target))
