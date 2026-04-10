"""
db_core.py — Connection lifecycle, migration engine, FTS5 utilities.

Leaf module: imports only stdlib + config + errors.
No imports from db_pipeline, db_decisions, or db_observability.

This module owns:
  - _FTS5_AVAILABLE singleton + FTS5 helpers (_check_fts5, _sanitize_fts5_query,
    _escape_like, _fts5_search)
  - Time utilities (_now, _file_mtime_iso)
  - Connection wrappers (_ClosingConnection, get_conn, _BatchConnection, transaction)
  - Migration engine (_split_sql_statements, migrate)
  - Path/hash utilities (to_relative_path, compute_file_hash)
"""

from __future__ import annotations

import fcntl
import hashlib
import logging
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH, MIGRATIONS_DIR

logger = logging.getLogger(__name__)
_FTS5_AVAILABLE: bool | None = None

# SQL identifier safety: only allow lowercase letters, digits, underscores (start with letter)
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_identifiers(*names: str) -> None:
    """Raise ValueError if any name is not a safe SQL identifier.

    Prevents SQL injection via dynamic column/table names.
    All callers pass hardcoded whitelists, but this guard ensures
    future changes don't accidentally introduce injection vectors.
    """
    for name in names:
        if not _IDENTIFIER_RE.match(name):
            raise ValueError(f"Unsafe SQL identifier: {name!r}")


def _check_fts5() -> bool:
    """Check if FTS5 is available in this Python's sqlite3."""
    global _FTS5_AVAILABLE
    if _FTS5_AVAILABLE is None:
        c = sqlite3.connect(":memory:")
        try:
            c.execute("CREATE VIRTUAL TABLE _fts5_test USING fts5(content)")
            c.execute("DROP TABLE _fts5_test")
            _FTS5_AVAILABLE = True
        except Exception:
            _FTS5_AVAILABLE = False
            logger.warning("FTS5 not available — full-text search features will be disabled")
        finally:
            c.close()
    return _FTS5_AVAILABLE


def _sanitize_fts5_query(query: str) -> str:
    """Sanitize a user query for FTS5 MATCH by escaping double quotes."""
    return '"' + query.replace('"', '""') + '"'


def _escape_like(query: str) -> str:
    """Escape LIKE wildcards in user input."""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _fts5_search(
    conn: sqlite3.Connection,
    query: str,
    *,
    table: str,
    fts_table: str,
    like_columns: list[str],
    filters: dict[str, str | None],
) -> list[dict]:
    """Shared FTS5 search with automatic LIKE fallback.

    Args:
        table: Main table name (e.g., 'decisions').
        fts_table: FTS5 virtual table name (e.g., 'decisions_fts').
        like_columns: Columns to search with LIKE when FTS5 is unavailable.
        filters: Column→value filters. None values are skipped.
    """
    # Validate all identifiers that will be interpolated into SQL
    _validate_identifiers(table, fts_table, *like_columns, *filters.keys())

    active_filters = {k: v for k, v in filters.items() if v is not None}

    def _like_fallback() -> list[dict]:
        escaped = _escape_like(query)
        like_clauses = " OR ".join(f"{col} LIKE ? ESCAPE '\\'" for col in like_columns)
        sql = f"SELECT * FROM {table} WHERE ({like_clauses})"
        params: list = [f"%{escaped}%" for _ in like_columns]
        for col, val in active_filters.items():
            sql += f" AND {col}=?"
            params.append(val)
        sql += " ORDER BY rowid DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    if not _check_fts5():
        logger.warning("FTS5 not available — falling back to LIKE search")
        return _like_fallback()

    alias = f"t_{table}"
    sanitized = _sanitize_fts5_query(query)
    sql = (
        f"SELECT {alias}.* FROM {table} {alias} "
        f"JOIN {fts_table} f ON {alias}.rowid = f.rowid "
        f"WHERE {fts_table} MATCH ? "
    )
    params: list = [sanitized]
    for col, val in active_filters.items():
        sql += f"AND {alias}.{col}=? "
        params.append(val)
    sql += "ORDER BY rank"
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except sqlite3.OperationalError:
        logger.warning("FTS5 query failed, falling back to LIKE: %s", query)
        return _like_fallback()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _file_mtime_iso(path: Path) -> str:
    """Return ISO 8601 UTC timestamp of a file's last modification time."""
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _ClosingConnection:
    """sqlite3.Connection wrapper that auto-closes on context exit.

    sqlite3's native `with` only commits/rollbacks — it does NOT close.
    This wrapper adds auto-close while proxying all connection methods.
    """

    __slots__ = ("_conn",)

    def __init__(self, conn: sqlite3.Connection):
        object.__setattr__(self, "_conn", conn)

    def __enter__(self) -> sqlite3.Connection:
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._conn.close()
        return False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __repr__(self):
        return f"<_ClosingConnection wrapping {self._conn!r}>"


def get_conn(db_path: Path | str | None = None) -> _ClosingConnection:
    """Create connection with WAL, FK, busy_timeout. Auto-creates directory.

    Supports both manual and context manager usage:
        conn = get_conn()          # manual close required
        with get_conn() as conn:   # auto-closes on exit
    """
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.row_factory = sqlite3.Row
    return _ClosingConnection(conn)


_DB_WRITE_LOCK_PATH = DB_PATH.parent / "madruga-db.lock"


@contextmanager
def db_write_lock():
    """Acquire exclusive flock before writing to the DB.

    Uses a separate lock file from easter's singleton guard (madruga.lock).
    Prevents concurrent writes from easter, post_save, seed, and hooks.
    """
    fh = open(_DB_WRITE_LOCK_PATH, "w")  # noqa: SIM115
    try:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.write(str(os.getpid()))
        fh.flush()
        yield
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()


class _BatchConnection:
    """Proxy that suppresses individual commit()/rollback() for batched operations.

    Usage:
        with transaction(conn) as txn:
            upsert_platform(txn, ...)  # commit() inside is a no-op
            upsert_pipeline_node(txn, ...)
        # single commit happens here on success, rollback on exception
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def commit(self):
        pass  # suppressed — will commit on context exit

    def rollback(self):
        pass  # suppressed — outer transaction() handles rollback on exception

    def __getattr__(self, name):
        return getattr(self._conn, name)


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Batch multiple writes into a single transaction.

    Suppresses individual conn.commit() calls inside the block,
    issuing one commit on successful exit or rollback on exception.
    """
    batch = _BatchConnection(conn)
    try:
        yield batch
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL text on ';' but preserve CREATE TRIGGER ... END; blocks."""
    statements: list[str] = []
    current: list[str] = []
    in_trigger = False
    for line in sql.split("\n"):
        stripped = line.strip().upper()
        if stripped.startswith("CREATE TRIGGER") or stripped.startswith("CREATE TEMP TRIGGER"):
            in_trigger = True
        current.append(line)
        if in_trigger:
            if stripped == "END;" or stripped.endswith(" END;"):
                statements.append("\n".join(current).strip())
                current = []
                in_trigger = False
        else:
            # Split on semicolons outside trigger blocks
            joined = "\n".join(current)
            if ";" in joined:
                parts = joined.split(";")
                for part in parts[:-1]:
                    s = part.strip()
                    if s:
                        statements.append(s)
                remainder = parts[-1].strip()
                current = [remainder] if remainder else []
    # Flush remaining
    leftover = "\n".join(current).strip()
    if leftover:
        statements.append(leftover)
    return [s for s in statements if s and not s.isspace()]


def migrate(conn: sqlite3.Connection | None = None, migrations_dir: Path | None = None) -> None:
    """Run pending migrations from .pipeline/migrations/ in order."""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    mdir = migrations_dir or MIGRATIONS_DIR
    conn.execute("CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    conn.commit()
    applied = {r[0] for r in conn.execute("SELECT name FROM _migrations").fetchall()}
    # Handle split of 003_decisions_memory.sql → 003a + 003b
    if "003_decisions_memory.sql" in applied:
        for split_name in ("003a_decisions_memory.sql", "003b_fts5.sql"):
            if split_name not in applied:
                conn.execute(
                    "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)",
                    (split_name, _now()),
                )
        conn.commit()
        applied = {r[0] for r in conn.execute("SELECT name FROM _migrations").fetchall()}
    # Repair: re-run ALTER TABLE ADD COLUMN from already-applied migrations.
    # SQLite DDL is not transactional, so a partially-applied migration can
    # leave the schema incomplete while _migrations marks it as done.
    # The "duplicate column" handler below makes this safe and idempotent.
    for sql_file in sorted(mdir.glob("*.sql")):
        if sql_file.name in applied:
            sql_text = sql_file.read_text()
            if "ADD COLUMN" in sql_text.upper():
                lines = [ln for ln in sql_text.split("\n") if not ln.strip().startswith("--")]
                for stmt in _split_sql_statements("\n".join(lines)):
                    if "ADD COLUMN" in stmt.upper():
                        try:
                            conn.execute(stmt)
                        except sqlite3.OperationalError as e:
                            if "duplicate column" in str(e):
                                continue
                            logger.warning("Repair failed for %s: %s", sql_file.name, e)
                conn.commit()

    for sql_file in sorted(mdir.glob("*.sql")):
        if sql_file.name not in applied:
            # Skip FTS5 migrations when FTS5 is not available
            if "fts5" in sql_file.name.lower() and not _check_fts5():
                logger.warning("Skipping %s — FTS5 not available", sql_file.name)
                conn.execute(
                    "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)",
                    (sql_file.name, _now()),
                )
                conn.commit()
                continue
            logger.info("Applying migration: %s", sql_file.name)
            try:
                # Strip SQL comments, then split on ';' and execute each
                # statement within the current transaction (unlike executescript()
                # which auto-commits and breaks rollback safety).
                # Handles CREATE TRIGGER ... END; blocks by not splitting inside them.
                sql_text = sql_file.read_text()
                # Remove single-line comments
                lines = [ln for ln in sql_text.split("\n") if not ln.strip().startswith("--")]
                cleaned = "\n".join(lines)
                for stmt in _split_sql_statements(cleaned):
                    try:
                        conn.execute(stmt)
                    except sqlite3.OperationalError as e:
                        # SQLite DDL is not transactional — ALTER TABLE ADD COLUMN
                        # can't be rolled back. Treat "duplicate column" as idempotent
                        # no-op so partially-applied migrations can be re-run safely.
                        if "duplicate column" in str(e):
                            logger.debug("Skipping (column already exists): %s", stmt[:80])
                            continue
                        raise
                conn.execute(
                    "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)",
                    (sql_file.name, _now()),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                logger.error("Migration failed: %s", sql_file.name)
                raise
    # DDL operations can reset PRAGMA foreign_keys — re-enable after migrate
    conn.execute("PRAGMA foreign_keys=ON")
    if own_conn:
        conn.close()


def to_relative_path(path: str | Path) -> str:
    """Convert absolute path to relative (to REPO_ROOT) if inside the repo."""
    import config as _cfg  # read at call time so test patches work

    p = Path(path).resolve()
    try:
        return str(p.relative_to(_cfg.REPO_ROOT))
    except ValueError:
        return str(p)  # outside repo, keep absolute


def compute_file_hash(path: str | Path) -> str:
    """Return 'sha256:<full hex>' hash of file contents."""
    data = Path(path).read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()
