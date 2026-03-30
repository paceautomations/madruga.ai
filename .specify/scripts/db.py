"""
db.py — SQLite thin wrapper for madruga.ai pipeline state.

Uses Python stdlib: sqlite3, hashlib, json, pathlib, os, logging.
seed_from_filesystem() additionally requires pyyaml.

Usage:
    from db import get_conn, migrate, upsert_platform, ...
    migrate()  # run once, idempotent
    conn = get_conn()
    upsert_platform(conn, 'fulano', name='Fulano', repo_path='platforms/fulano')
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = REPO_ROOT / ".pipeline" / "madruga.db"
MIGRATIONS_DIR = REPO_ROOT / ".pipeline" / "migrations"
_FTS5_AVAILABLE: bool | None = None


def _check_fts5() -> bool:
    """Check if FTS5 is available in this Python's sqlite3."""
    global _FTS5_AVAILABLE
    if _FTS5_AVAILABLE is None:
        try:
            c = sqlite3.connect(":memory:")
            c.execute("CREATE VIRTUAL TABLE _fts5_test USING fts5(content)")
            c.execute("DROP TABLE _fts5_test")
            c.close()
            _FTS5_AVAILABLE = True
        except Exception:
            _FTS5_AVAILABLE = False
            logger.warning("FTS5 not available — full-text search features will be disabled")
    return _FTS5_AVAILABLE


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_conn(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create connection with WAL, FK, busy_timeout. Auto-creates directory."""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


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
    for sql_file in sorted(mdir.glob("*.sql")):
        if sql_file.name not in applied:
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
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)",
                    (sql_file.name, _now()),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                logger.error("Migration failed: %s", sql_file.name)
                raise
    if own_conn:
        conn.close()


def compute_file_hash(path: str | Path) -> str:
    """Return 'sha256:<full hex>' hash of file contents."""
    data = Path(path).read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()


# ══════════════════════════════════════
# Platforms
# ══════════════════════════════════════


def upsert_platform(
    conn: sqlite3.Connection,
    platform_id: str,
    *,
    name: str = "",
    repo_path: str = "",
    title: str = "",
    lifecycle: str = "design",
    metadata: str = "{}",
) -> None:
    conn.execute(
        """INSERT INTO platforms
           (platform_id, name, title, lifecycle, repo_path, metadata, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(platform_id) DO UPDATE SET
             name = excluded.name,
             title = excluded.title,
             lifecycle = excluded.lifecycle,
             repo_path = excluded.repo_path,
             metadata = excluded.metadata,
             updated_at = excluded.updated_at
        """,
        (
            platform_id,
            name or platform_id,
            title,
            lifecycle,
            repo_path,
            metadata,
            _now(),
            _now(),
        ),
    )
    conn.commit()
    logger.info("Upserted platform: %s", platform_id)


def get_platform(conn: sqlite3.Connection, platform_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM platforms WHERE platform_id=?", (platform_id,)).fetchone()
    return dict(row) if row else None


# ══════════════════════════════════════
# Pipeline Nodes (DAG Level 1)
# ══════════════════════════════════════


def upsert_pipeline_node(
    conn: sqlite3.Connection,
    platform_id: str,
    node_id: str,
    status: str = "pending",
    **kwargs,
) -> None:
    conn.execute(
        """INSERT INTO pipeline_nodes
           (platform_id, node_id, status, output_hash, input_hashes,
            output_files, completed_at, completed_by, line_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(platform_id, node_id) DO UPDATE SET
             status = excluded.status,
             output_hash = COALESCE(excluded.output_hash, pipeline_nodes.output_hash),
             input_hashes = COALESCE(excluded.input_hashes, pipeline_nodes.input_hashes),
             output_files = COALESCE(excluded.output_files, pipeline_nodes.output_files),
             completed_at = COALESCE(excluded.completed_at, pipeline_nodes.completed_at),
             completed_by = COALESCE(excluded.completed_by, pipeline_nodes.completed_by),
             line_count = COALESCE(excluded.line_count, pipeline_nodes.line_count)
        """,
        (
            platform_id,
            node_id,
            status,
            kwargs.get("output_hash"),
            kwargs.get("input_hashes"),
            kwargs.get("output_files"),
            kwargs.get("completed_at"),
            kwargs.get("completed_by"),
            kwargs.get("line_count"),
        ),
    )
    conn.commit()


def get_pipeline_nodes(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM pipeline_nodes WHERE platform_id=? ORDER BY node_id",
        (platform_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Epics
# ══════════════════════════════════════


def upsert_epic(conn: sqlite3.Connection, platform_id: str, epic_id: str, title: str = "", **kwargs) -> None:
    conn.execute(
        """INSERT INTO epics
           (platform_id, epic_id, title, status, appetite, priority, branch_name, file_path,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(platform_id, epic_id) DO UPDATE SET
             title = excluded.title,
             status = excluded.status,
             appetite = COALESCE(excluded.appetite, epics.appetite),
             priority = COALESCE(excluded.priority, epics.priority),
             branch_name = COALESCE(excluded.branch_name, epics.branch_name),
             file_path = COALESCE(excluded.file_path, epics.file_path),
             updated_at = excluded.updated_at
        """,
        (
            platform_id,
            epic_id,
            title,
            kwargs.get("status", "proposed"),
            kwargs.get("appetite"),
            kwargs.get("priority"),
            kwargs.get("branch_name"),
            kwargs.get("file_path"),
            _now(),
            _now(),
        ),
    )
    conn.commit()


def get_epics(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM epics WHERE platform_id=? ORDER BY epic_id",
        (platform_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Epic Nodes (DAG Level 2)
# ══════════════════════════════════════


def upsert_epic_node(
    conn: sqlite3.Connection,
    platform_id: str,
    epic_id: str,
    node_id: str,
    status: str = "pending",
    **kwargs,
) -> None:
    conn.execute(
        """INSERT INTO epic_nodes
           (platform_id, epic_id, node_id, status, output_hash, completed_at, completed_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(platform_id, epic_id, node_id) DO UPDATE SET
             status = excluded.status,
             output_hash = COALESCE(excluded.output_hash, epic_nodes.output_hash),
             completed_at = COALESCE(excluded.completed_at, epic_nodes.completed_at),
             completed_by = COALESCE(excluded.completed_by, epic_nodes.completed_by)
        """,
        (
            platform_id,
            epic_id,
            node_id,
            status,
            kwargs.get("output_hash"),
            kwargs.get("completed_at"),
            kwargs.get("completed_by"),
        ),
    )
    conn.commit()


def get_epic_nodes(conn: sqlite3.Connection, platform_id: str, epic_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM epic_nodes WHERE platform_id=? AND epic_id=? ORDER BY node_id",
        (platform_id, epic_id),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Decisions
# ══════════════════════════════════════


def insert_decision(conn: sqlite3.Connection, platform_id: str, skill: str, title: str, **kwargs) -> str:
    decision_id = kwargs.get("decision_id") or os.urandom(8).hex()
    decisions_json = json.dumps(kwargs.get("decisions", []))
    assumptions_json = json.dumps(kwargs.get("assumptions", []))
    open_questions_json = json.dumps(kwargs.get("open_questions", []))
    conn.execute(
        """INSERT INTO decisions
           (decision_id, platform_id, epic_id, skill, slug, title, number, status,
            superseded_by, source_decision_key, file_path,
            decisions_json, assumptions_json, open_questions_json,
            content_hash, decision_type, context, consequences, tags_json,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(decision_id) DO UPDATE SET
             platform_id = excluded.platform_id,
             epic_id = excluded.epic_id,
             skill = excluded.skill,
             slug = excluded.slug,
             title = excluded.title,
             number = excluded.number,
             status = excluded.status,
             superseded_by = excluded.superseded_by,
             source_decision_key = excluded.source_decision_key,
             file_path = excluded.file_path,
             decisions_json = excluded.decisions_json,
             assumptions_json = excluded.assumptions_json,
             open_questions_json = excluded.open_questions_json,
             content_hash = excluded.content_hash,
             decision_type = excluded.decision_type,
             context = excluded.context,
             consequences = excluded.consequences,
             tags_json = excluded.tags_json,
             updated_at = excluded.updated_at
        """,
        (
            decision_id,
            platform_id,
            kwargs.get("epic_id"),
            skill,
            kwargs.get("slug"),
            title,
            kwargs.get("number"),
            kwargs.get("status", "accepted"),
            kwargs.get("superseded_by"),
            kwargs.get("source_decision_key"),
            kwargs.get("file_path"),
            decisions_json,
            assumptions_json,
            open_questions_json,
            kwargs.get("content_hash"),
            kwargs.get("decision_type"),
            kwargs.get("context"),
            kwargs.get("consequences"),
            kwargs.get("tags_json", "[]"),
            _now(),
            _now(),
        ),
    )
    conn.commit()
    logger.info("Inserted decision: %s — %s", decision_id, title)
    return decision_id


def get_decisions(
    conn: sqlite3.Connection,
    platform_id: str,
    epic_id: str | None = None,
    status: str | None = None,
    decision_type: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM decisions WHERE platform_id=?"
    params: list = [platform_id]
    if epic_id:
        sql += " AND epic_id=?"
        params.append(epic_id)
    if status:
        sql += " AND status=?"
        params.append(status)
    if decision_type:
        sql += " AND decision_type=?"
        params.append(decision_type)
    sql += " ORDER BY created_at"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ══════════════════════════════════════
# Decision Links
# ══════════════════════════════════════


def insert_decision_link(conn: sqlite3.Connection, from_id: str, to_id: str, link_type: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO decision_links (from_decision_id, to_decision_id, link_type) VALUES (?, ?, ?)",
        (from_id, to_id, link_type),
    )
    conn.commit()
    logger.info("Linked decision %s -[%s]-> %s", from_id, link_type, to_id)


def get_decision_links(
    conn: sqlite3.Connection,
    decision_id: str,
    direction: str = "both",
    link_type: str | None = None,
) -> list[dict]:
    parts: list[str] = []
    params: list = []
    if direction in ("from", "both"):
        q = "SELECT *, 'from' as direction FROM decision_links WHERE from_decision_id=?"
        p: list = [decision_id]
        if link_type:
            q += " AND link_type=?"
            p.append(link_type)
        parts.append(q)
        params.extend(p)
    if direction in ("to", "both"):
        q = "SELECT *, 'to' as direction FROM decision_links WHERE to_decision_id=?"
        p = [decision_id]
        if link_type:
            q += " AND link_type=?"
            p.append(link_type)
        parts.append(q)
        params.extend(p)
    sql = " UNION ALL ".join(parts)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ══════════════════════════════════════
# Decision Import/Export (Markdown <-> BD)
# ══════════════════════════════════════


def _parse_adr_markdown(file_path: Path) -> dict | None:
    """Parse an ADR markdown file into a dict. Returns None on parse failure."""
    import re
    import yaml

    text = file_path.read_text(encoding="utf-8")
    # Split frontmatter
    parts = text.split("---", 2)
    if len(parts) < 3:
        logger.warning("No frontmatter found in %s", file_path)
        return None
    try:
        fm = yaml.safe_load(parts[1])
    except Exception:
        logger.warning("Failed to parse YAML frontmatter in %s", file_path)
        return None
    if not isinstance(fm, dict):
        logger.warning("Frontmatter is not a dict in %s", file_path)
        return None

    body = parts[2].strip()
    # Extract sections by ## headers
    sections: dict[str, str] = {}
    current_header = ""
    current_lines: list[str] = []
    for line in body.split("\n"):
        if line.startswith("## "):
            if current_header:
                sections[current_header] = "\n".join(current_lines).strip()
            current_header = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_header:
        sections[current_header] = "\n".join(current_lines).strip()

    # Extract number from title
    number = None
    title = fm.get("title", "")
    m = re.match(r"ADR-(\d+)", title)
    if m:
        number = int(m.group(1))

    # Extract slug from filename
    slug = file_path.stem
    if slug.startswith("ADR-"):
        slug = re.sub(r"^ADR-\d+-?", "", slug)

    return {
        "title": title,
        "status": fm.get("status", "Accepted"),
        "decision": fm.get("decision", ""),
        "alternatives": fm.get("alternatives", ""),
        "rationale": fm.get("rationale", ""),
        "number": number,
        "slug": slug,
        "context": sections.get("Contexto", ""),
        "consequences": sections.get("Consequencias", ""),
        "body": body,
        "file_path": str(file_path),
    }


def import_adr_from_markdown(conn: sqlite3.Connection, file_path: Path, platform_id: str) -> str | None:
    """Import a single ADR markdown file into the BD. Returns decision_id or None on failure."""
    parsed = _parse_adr_markdown(Path(file_path))
    if parsed is None:
        return None
    content_hash = compute_file_hash(file_path)
    # Check if already imported with same hash
    existing = conn.execute(
        "SELECT decision_id, content_hash FROM decisions WHERE platform_id=? AND file_path=?",
        (platform_id, str(file_path)),
    ).fetchone()
    if existing and existing["content_hash"] == content_hash:
        logger.debug("Skipping unchanged ADR: %s", file_path)
        return existing["decision_id"]

    decision_id = existing["decision_id"] if existing else os.urandom(8).hex()
    return insert_decision(
        conn,
        platform_id,
        "adr",
        parsed["title"],
        decision_id=decision_id,
        number=parsed["number"],
        slug=parsed["slug"],
        status=parsed["status"].lower(),
        file_path=str(file_path),
        content_hash=content_hash,
        context=parsed["context"],
        consequences=parsed["consequences"],
        decisions=[parsed["decision"]],
        assumptions=[],
        open_questions=[],
    )


def import_all_adrs(conn: sqlite3.Connection, platform_id: str, decisions_dir: Path) -> int:
    """Import all ADR-*.md files from a directory. Returns count of imported files."""
    count = 0
    for adr_file in sorted(decisions_dir.glob("ADR-*.md")):
        result = import_adr_from_markdown(conn, adr_file, platform_id)
        if result:
            count += 1
        else:
            logger.warning("Failed to import: %s", adr_file)
    logger.info("Imported %d ADRs for platform %s", count, platform_id)
    return count


def export_decision_to_markdown(conn: sqlite3.Connection, decision_id: str, output_dir: Path) -> Path:
    """Export a single decision from BD to Nygard-format markdown."""
    row = conn.execute("SELECT * FROM decisions WHERE decision_id=?", (decision_id,)).fetchone()
    if not row:
        raise ValueError(f"Decision not found: {decision_id}")
    d = dict(row)
    number = d.get("number")
    slug = d.get("slug", "")
    title = d["title"]
    status = (d.get("status") or "accepted").capitalize()
    decision_text = ""
    decisions_list = json.loads(d.get("decisions_json") or "[]")
    if decisions_list:
        decision_text = decisions_list[0] if isinstance(decisions_list[0], str) else str(decisions_list[0])

    # Build filename
    if number:
        fname = f"ADR-{number:03d}-{slug}.md" if slug else f"ADR-{number:03d}.md"
    else:
        fname = f"decision-{decision_id[:8]}.md"

    # Build Nygard format
    context = d.get("context") or ""
    consequences = d.get("consequences") or ""
    now_str = _now()[:10]
    created = (d.get("created_at") or now_str)[:10]
    updated = (d.get("updated_at") or now_str)[:10]

    content = (
        f'---\ntitle: "{title}"\nstatus: {status}\n'
        f'decision: "{decision_text}"\nalternatives: ""\n'
        f'rationale: ""\n---\n'
        f"# {title}\n"
        f"**Status:** {status} | **Data:** {created} | **Atualizado:** {updated}\n\n"
        f"## Contexto\n{context}\n\n"
        f"## Decisao\n{decision_text}\n\n"
        f"## Alternativas consideradas\n\n\n"
        f"## Consequencias\n{consequences}\n"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / fname
    out_path.write_text(content, encoding="utf-8")
    # Update file_path and content_hash in BD
    file_hash = compute_file_hash(out_path)
    conn.execute(
        "UPDATE decisions SET file_path=?, content_hash=? WHERE decision_id=?",
        (str(out_path), file_hash, decision_id),
    )
    conn.commit()
    logger.info("Exported decision to %s", out_path)
    return out_path


def sync_decisions_to_markdown(conn: sqlite3.Connection, platform_id: str, output_dir: Path) -> int:
    """Export all decisions for a platform to markdown. Returns count."""
    rows = conn.execute(
        "SELECT decision_id FROM decisions WHERE platform_id=? AND number IS NOT NULL ORDER BY number",
        (platform_id,),
    ).fetchall()
    count = 0
    for row in rows:
        export_decision_to_markdown(conn, row["decision_id"], output_dir)
        count += 1
    logger.info("Synced %d decisions to %s", count, output_dir)
    return count


# ══════════════════════════════════════
# Decision Search (FTS5)
# ══════════════════════════════════════


def search_decisions(conn: sqlite3.Connection, query: str, platform_id: str | None = None) -> list[dict]:
    """Full-text search across decisions using FTS5."""
    if not _check_fts5():
        logger.warning("FTS5 not available — falling back to LIKE search")
        sql = "SELECT * FROM decisions WHERE title LIKE ? OR context LIKE ?"
        params: list = [f"%{query}%", f"%{query}%"]
        if platform_id:
            sql += " AND platform_id=?"
            params.append(platform_id)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    sql = "SELECT d.* FROM decisions d JOIN decisions_fts f ON d.rowid = f.rowid WHERE decisions_fts MATCH ? "
    params = [query]
    if platform_id:
        sql += "AND d.platform_id=? "
        params.append(platform_id)
    sql += "ORDER BY rank"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ══════════════════════════════════════
# Memory Entries
# ══════════════════════════════════════


def insert_memory(
    conn: sqlite3.Connection,
    type_: str,
    name: str,
    content: str,
    **kwargs,
) -> str:
    memory_id = kwargs.get("memory_id") or os.urandom(8).hex()
    conn.execute(
        """INSERT INTO memory_entries
           (memory_id, platform_id, type, name, description, content,
            source, file_path, content_hash, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(memory_id) DO UPDATE SET
             platform_id = excluded.platform_id,
             type = excluded.type,
             name = excluded.name,
             description = excluded.description,
             content = excluded.content,
             source = excluded.source,
             file_path = excluded.file_path,
             content_hash = excluded.content_hash,
             updated_at = excluded.updated_at
        """,
        (
            memory_id,
            kwargs.get("platform_id"),
            type_,
            name,
            kwargs.get("description"),
            content,
            kwargs.get("source"),
            kwargs.get("file_path"),
            kwargs.get("content_hash"),
            _now(),
            _now(),
        ),
    )
    conn.commit()
    logger.info("Inserted memory: %s — %s", memory_id, name)
    return memory_id


def get_memories(
    conn: sqlite3.Connection,
    type_: str | None = None,
    platform_id: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM memory_entries WHERE 1=1"
    params: list = []
    if type_:
        sql += " AND type=?"
        params.append(type_)
    if platform_id:
        sql += " AND platform_id=?"
        params.append(platform_id)
    sql += " ORDER BY created_at"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def update_memory(conn: sqlite3.Connection, memory_id: str, **kwargs) -> None:
    allowed = {"name", "description", "content", "type", "platform_id", "source", "file_path", "content_hash"}
    sets = ["updated_at=?"]
    vals: list = [_now()]
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(v)
    vals.append(memory_id)
    conn.execute(f"UPDATE memory_entries SET {', '.join(sets)} WHERE memory_id=?", vals)
    conn.commit()


def delete_memory(conn: sqlite3.Connection, memory_id: str) -> None:
    conn.execute("DELETE FROM memory_entries WHERE memory_id=?", (memory_id,))
    conn.commit()
    logger.info("Deleted memory: %s", memory_id)


# ══════════════════════════════════════
# Memory Import/Export (Markdown <-> BD)
# ══════════════════════════════════════


def _parse_memory_markdown(file_path: Path) -> dict | None:
    """Parse a memory markdown file into a dict."""
    import yaml

    text = file_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        logger.warning("No frontmatter in memory file %s", file_path)
        return None
    try:
        fm = yaml.safe_load(parts[1])
    except Exception:
        logger.warning("Failed to parse frontmatter in %s", file_path)
        return None
    if not isinstance(fm, dict):
        return None
    return {
        "name": fm.get("name", file_path.stem),
        "description": fm.get("description", ""),
        "type": fm.get("type", "project"),
        "content": parts[2].strip(),
        "file_path": str(file_path),
    }


def import_memory_from_markdown(conn: sqlite3.Connection, file_path: Path) -> str | None:
    """Import a single memory markdown file. Returns memory_id or None."""
    parsed = _parse_memory_markdown(Path(file_path))
    if parsed is None:
        return None
    content_hash = compute_file_hash(file_path)
    existing = conn.execute(
        "SELECT memory_id, content_hash FROM memory_entries WHERE file_path=?",
        (str(file_path),),
    ).fetchone()
    if existing and existing["content_hash"] == content_hash:
        return existing["memory_id"]
    memory_id = existing["memory_id"] if existing else os.urandom(8).hex()
    return insert_memory(
        conn,
        parsed["type"],
        parsed["name"],
        parsed["content"],
        memory_id=memory_id,
        description=parsed["description"],
        file_path=str(file_path),
        content_hash=content_hash,
        source="import",
    )


def import_all_memories(conn: sqlite3.Connection, memory_dir: Path) -> int:
    """Import all *.md files from a memory directory. Returns count."""
    count = 0
    for md_file in sorted(memory_dir.glob("*.md")):
        if md_file.name == "MEMORY.md":
            continue  # Skip index file
        result = import_memory_from_markdown(conn, md_file)
        if result:
            count += 1
    logger.info("Imported %d memory files from %s", count, memory_dir)
    return count


def export_memory_to_markdown(conn: sqlite3.Connection, memory_id: str, output_dir: Path) -> Path:
    """Export a memory entry to markdown file."""
    row = conn.execute("SELECT * FROM memory_entries WHERE memory_id=?", (memory_id,)).fetchone()
    if not row:
        raise ValueError(f"Memory not found: {memory_id}")
    d = dict(row)
    slug = d["name"].replace(" ", "_").lower()
    fname = f"{d['type']}_{slug}.md"
    content = (
        f"---\nname: {d['name']}\ndescription: {d.get('description') or ''}\ntype: {d['type']}\n---\n\n{d['content']}\n"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / fname
    out_path.write_text(content, encoding="utf-8")
    file_hash = compute_file_hash(out_path)
    conn.execute(
        "UPDATE memory_entries SET file_path=?, content_hash=? WHERE memory_id=?",
        (str(out_path), file_hash, memory_id),
    )
    conn.commit()
    logger.info("Exported memory to %s", out_path)
    return out_path


def sync_memories_to_markdown(conn: sqlite3.Connection, output_dir: Path) -> int:
    """Export all memory entries to markdown. Returns count."""
    rows = conn.execute("SELECT memory_id FROM memory_entries ORDER BY type, name").fetchall()
    count = 0
    for row in rows:
        export_memory_to_markdown(conn, row["memory_id"], output_dir)
        count += 1
    return count


# ══════════════════════════════════════
# Memory Search (FTS5)
# ══════════════════════════════════════


def search_memories(conn: sqlite3.Connection, query: str, type_: str | None = None) -> list[dict]:
    """Full-text search across memory entries using FTS5."""
    if not _check_fts5():
        sql = "SELECT * FROM memory_entries WHERE name LIKE ? OR content LIKE ?"
        params: list = [f"%{query}%", f"%{query}%"]
        if type_:
            sql += " AND type=?"
            params.append(type_)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    sql = "SELECT m.* FROM memory_entries m JOIN memory_fts f ON m.rowid = f.rowid WHERE memory_fts MATCH ? "
    params = [query]
    if type_:
        sql += "AND m.type=? "
        params.append(type_)
    sql += "ORDER BY rank"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ══════════════════════════════════════
# Artifact Provenance
# ══════════════════════════════════════


def insert_provenance(
    conn: sqlite3.Connection,
    platform_id: str,
    file_path: str,
    generated_by: str,
    **kwargs,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO artifact_provenance "
        "(platform_id, file_path, generated_by, epic_id, output_hash, generated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            platform_id,
            file_path,
            generated_by,
            kwargs.get("epic_id"),
            kwargs.get("output_hash"),
            _now(),
        ),
    )
    conn.commit()


def get_provenance(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM artifact_provenance WHERE platform_id=? ORDER BY file_path",
        (platform_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Pipeline Runs
# ══════════════════════════════════════


def insert_run(conn: sqlite3.Connection, platform_id: str, node_id: str, **kwargs) -> str:
    run_id = kwargs.get("run_id") or os.urandom(4).hex()
    conn.execute(
        "INSERT INTO pipeline_runs "
        "(run_id, platform_id, epic_id, node_id, status, agent, "
        "tokens_in, tokens_out, cost_usd, duration_ms, error, started_at) "
        "VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            platform_id,
            kwargs.get("epic_id"),
            node_id,
            kwargs.get("agent"),
            kwargs.get("tokens_in"),
            kwargs.get("tokens_out"),
            kwargs.get("cost_usd"),
            kwargs.get("duration_ms"),
            kwargs.get("error"),
            _now(),
        ),
    )
    conn.commit()
    return run_id


_COMPLETE_RUN_FIELDS = frozenset({"tokens_in", "tokens_out", "cost_usd", "duration_ms", "error"})


def complete_run(conn: sqlite3.Connection, run_id: str, status: str = "completed", **kwargs) -> None:
    sets = ["status=?", "completed_at=?"]
    vals: list = [status, _now()]
    for field in _COMPLETE_RUN_FIELDS:
        if field in kwargs:
            sets.append(f"{field}=?")
            vals.append(kwargs[field])
    vals.append(run_id)
    conn.execute(f"UPDATE pipeline_runs SET {', '.join(sets)} WHERE run_id=?", vals)
    conn.commit()


def get_runs(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM pipeline_runs WHERE platform_id=? ORDER BY started_at",
        (platform_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Events
# ══════════════════════════════════════


def insert_event(
    conn: sqlite3.Connection,
    platform_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    **kwargs,
) -> int:
    cur = conn.execute(
        "INSERT INTO events "
        "(platform_id, entity_type, entity_id, action, actor, payload, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            platform_id,
            entity_type,
            entity_id,
            action,
            kwargs.get("actor", "system"),
            json.dumps(kwargs.get("payload", {})),
            _now(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_events(
    conn: sqlite3.Connection,
    platform_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM events WHERE platform_id=?"
    params: list = [platform_id]
    if entity_type:
        sql += " AND entity_type=?"
        params.append(entity_type)
    if entity_id:
        sql += " AND entity_id=?"
        params.append(entity_id)
    sql += " ORDER BY created_at"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ══════════════════════════════════════
# Staleness & Status
# ══════════════════════════════════════


def get_stale_nodes(conn: sqlite3.Connection, platform_id: str, dag_edges: dict[str, list[str]]) -> list[dict]:
    """Return nodes whose dependencies completed after them.

    dag_edges: {node_id: [dep_node_id, ...]} parsed from platform.yaml.
    """
    nodes = {n["node_id"]: n for n in get_pipeline_nodes(conn, platform_id)}
    stale = []
    for node_id, deps in dag_edges.items():
        node = nodes.get(node_id)
        if not node or node["status"] != "done" or not node["completed_at"]:
            continue
        for dep_id in deps:
            dep = nodes.get(dep_id)
            if dep and dep["completed_at"] and dep["completed_at"] > node["completed_at"]:
                stale.append(
                    {
                        "node_id": node_id,
                        "stale_reason": f"{dep_id} completed at {dep['completed_at']} > {node['completed_at']}",
                        "dep_node_id": dep_id,
                    }
                )
                break
    return stale


def get_platform_status(conn: sqlite3.Connection, platform_id: str) -> dict:
    rows = get_pipeline_nodes(conn, platform_id)
    total = len(rows)
    counts: dict[str, int] = {
        "done": 0,
        "pending": 0,
        "stale": 0,
        "blocked": 0,
        "skipped": 0,
    }
    for r in rows:
        s = r["status"]
        counts[s] = counts.get(s, 0) + 1
    return {
        "platform_id": platform_id,
        "total_nodes": total,
        **counts,
        "progress_pct": round(counts["done"] / total * 100, 1) if total else 0,
    }


def get_epic_status(conn: sqlite3.Connection, platform_id: str, epic_id: str) -> dict:
    rows = get_epic_nodes(conn, platform_id, epic_id)
    total = len(rows)
    counts: dict[str, int] = {
        "done": 0,
        "pending": 0,
        "stale": 0,
        "blocked": 0,
        "skipped": 0,
    }
    for r in rows:
        s = r["status"]
        counts[s] = counts.get(s, 0) + 1
    return {
        "platform_id": platform_id,
        "epic_id": epic_id,
        "total_nodes": total,
        **counts,
        "progress_pct": round(counts["done"] / total * 100, 1) if total else 0,
    }


# ══════════════════════════════════════
# Seed from filesystem
# ══════════════════════════════════════


def seed_from_filesystem(conn: sqlite3.Connection, platform_id: str, platform_dir: str | Path) -> dict:
    """Import existing state from filesystem into DB. Idempotent."""
    import yaml

    pdir = Path(platform_dir)
    yaml_path = pdir / "platform.yaml"
    if not yaml_path.exists():
        logger.warning("platform.yaml not found at %s — skipping seed", yaml_path)
        return {"status": "skipped", "reason": "no platform.yaml"}

    with open(yaml_path) as f:
        manifest = yaml.safe_load(f)

    upsert_platform(
        conn,
        platform_id,
        name=manifest.get("name", platform_id),
        title=manifest.get("title", ""),
        lifecycle=manifest.get("lifecycle", "design"),
        repo_path=f"platforms/{platform_id}",
        metadata=json.dumps({k: manifest[k] for k in ("views", "serve", "build") if k in manifest}),
    )

    nodes_seeded = 0
    pipeline = manifest.get("pipeline", {})
    for node in pipeline.get("nodes", []):
        nid = node["id"]
        outputs = node.get("outputs", [])
        pattern = node.get("output_pattern")
        if pattern:
            import glob as glob_mod

            found = glob_mod.glob(str(pdir / pattern))
            exists = len(found) > 0
            output_files = [str(Path(f).relative_to(pdir)) for f in found]
        else:
            exists = all((pdir / o).exists() for o in outputs)
            output_files = outputs

        status = "done" if exists else "pending"
        output_hash = None
        if exists and outputs and not pattern:
            first_output = pdir / outputs[0]
            if first_output.exists():
                output_hash = compute_file_hash(first_output)

        upsert_pipeline_node(
            conn,
            platform_id,
            nid,
            status,
            output_hash=output_hash,
            output_files=json.dumps(output_files),
            completed_by=node.get("skill"),
        )
        # Populate artifact_provenance for done nodes
        if status == "done":
            for ofile in output_files:
                full_path = pdir / ofile
                if full_path.exists() and full_path.is_file():
                    insert_provenance(
                        conn,
                        platform_id,
                        ofile,
                        generated_by=node.get("skill", f"madruga:{nid}"),
                        output_hash=compute_file_hash(full_path),
                    )
        insert_event(
            conn,
            platform_id,
            "node",
            nid,
            "seeded",
            actor="seed",
            payload={"status": status},
        )
        nodes_seeded += 1

    epics_seeded = 0
    epics_dir = pdir / "epics"
    if epics_dir.exists():
        for epic_dir in sorted(epics_dir.iterdir()):
            pitch = epic_dir / "pitch.md"
            if epic_dir.is_dir() and pitch.exists():
                epic_id = epic_dir.name
                with open(pitch) as f:
                    first_lines = f.read(500)
                title_line = ""
                for line in first_lines.split("\n"):
                    if line.startswith("title:"):
                        title_line = line.split(":", 1)[1].strip().strip('"').strip("'")
                        break
                    if line.startswith("# "):
                        title_line = line[2:].strip()
                        break
                upsert_epic(
                    conn,
                    platform_id,
                    epic_id,
                    title=title_line or epic_id,
                    file_path=f"epics/{epic_id}/pitch.md",
                )
                epics_seeded += 1

    logger.info("Seeded %s: %d nodes, %d epics", platform_id, nodes_seeded, epics_seeded)
    return {"status": "ok", "nodes": nodes_seeded, "epics": epics_seeded}
