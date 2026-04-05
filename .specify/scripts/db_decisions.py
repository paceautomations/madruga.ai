"""
db_decisions.py — Decisions (ADRs) and memory entries: CRUD, import/export, FTS5 search.

Imports from db_core only. No imports from db_pipeline or db_observability.

Note: import_adr_from_markdown emits an audit event via insert_event (db_pipeline).
That call is deferred to a local import inside a try/except so the module boundary
is preserved — the failure path is already silent (logs a warning and continues).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path

import yaml

from db_core import _fts5_search, _now, compute_file_hash, to_relative_path

logger = logging.getLogger(__name__)


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
            body, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
             body = excluded.body,
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
            kwargs.get("body"),
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


def get_decisions_summary(conn: sqlite3.Connection, platform_id: str) -> list[dict]:
    """Return lightweight decision summaries for portal display."""
    rows = conn.execute(
        """SELECT number, slug, title, status, decisions_json,
                  consequences, body
           FROM decisions
           WHERE platform_id=? AND number IS NOT NULL
           ORDER BY number""",
        (platform_id,),
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        decisions_list = json.loads(d.get("decisions_json") or "[]")
        decision_text = decisions_list[0] if decisions_list and isinstance(decisions_list[0], str) else ""

        rationale = ""
        cons = d.get("consequences") or ""
        for line in cons.split("\n"):
            ls = line.strip()
            if ls.startswith("- [+]"):
                rationale = ls[5:].strip()
                break

        alternatives = ""
        body = d.get("body") or ""
        in_alt_section = False
        alt_names = []
        for line in body.split("\n"):
            if line.startswith("## ") and "lternativ" in line:
                in_alt_section = True
                continue
            if in_alt_section and line.startswith("## "):
                break
            if in_alt_section and line.startswith("### "):
                alt_names.append(line[4:].strip())
        if alt_names:
            alternatives = ", ".join(alt_names)

        result.append(
            {
                "num": f"{d['number']:03d}" if d["number"] else "000",
                "slug": d.get("slug") or "",
                "title": d.get("title") or "",
                "status": d.get("status") or "",
                "decision": decision_text,
                "alternatives": alternatives,
                "rationale": rationale,
            }
        )
    return result


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
# Decision Import/Export (Markdown <-> DB)
# ══════════════════════════════════════


def _parse_body_sections(body: str) -> dict[str, str]:
    """Split markdown body on level-2 headings into {header: content} dict."""
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
    return sections


def _parse_adr_markdown(file_path: Path) -> dict | None:
    """Parse an ADR markdown file into a dict. Returns None on parse failure."""
    import re

    text = file_path.read_text(encoding="utf-8")
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
    sections = _parse_body_sections(body)

    number = None
    title = fm.get("title", "")
    m = re.match(r"ADR-(\d+)", title)
    if m:
        number = int(m.group(1))

    slug = file_path.stem
    if slug.startswith("ADR-"):
        slug = re.sub(r"^ADR-\d+-?", "", slug)

    decision_text = fm.get("decision", "")
    if not decision_text:
        raw = sections.get("Decisao", sections.get("Decisão", ""))
        for para in raw.split("\n\n"):
            stripped = para.strip()
            if stripped and not stripped.startswith("**Status:"):
                decision_text = stripped
                break

    alternatives_text = fm.get("alternatives", "")
    if not alternatives_text:
        raw = sections.get("Alternativas consideradas", sections.get("Alternativas Consideradas", ""))
        if raw:
            alt_names = [line[4:].strip() for line in raw.split("\n") if line.startswith("### ")]
            if alt_names:
                alternatives_text = ", ".join(alt_names)

    rationale_text = fm.get("rationale", "")
    if not rationale_text:
        raw = sections.get("Consequencias", sections.get("Consequências", ""))
        if raw:
            for line in raw.split("\n"):
                line_s = line.strip()
                if line_s.startswith("- [+]"):
                    rationale_text = line_s[5:].strip()
                    break

    return {
        "title": title,
        "status": fm.get("status", "Accepted"),
        "decision": decision_text,
        "alternatives": alternatives_text,
        "rationale": rationale_text,
        "number": number,
        "slug": slug,
        "context": sections.get("Contexto", ""),
        "consequences": sections.get("Consequencias", sections.get("Consequências", "")),
        "body": body,
        "file_path": to_relative_path(file_path),
    }


def import_adr_from_markdown(conn: sqlite3.Connection, file_path: Path, platform_id: str) -> str | None:
    """Import a single ADR markdown file into the DB. Returns decision_id or None on failure."""
    parsed = _parse_adr_markdown(Path(file_path))
    if parsed is None:
        return None
    content_hash = compute_file_hash(file_path)
    rel_path = to_relative_path(file_path)
    existing = conn.execute(
        "SELECT decision_id, content_hash FROM decisions WHERE platform_id=? AND (file_path=? OR file_path=?)",
        (platform_id, rel_path, str(file_path)),
    ).fetchone()
    if existing and existing["content_hash"] == content_hash:
        logger.debug("Skipping unchanged ADR: %s", file_path)
        return existing["decision_id"]

    # Record audit event when an existing decision changes.
    # Local import avoids a module-level dependency on db_pipeline; the call is
    # non-critical and already wrapped in try/except.
    if existing and existing["content_hash"] != content_hash:
        try:
            from db_pipeline import insert_event

            insert_event(
                conn,
                platform_id,
                "decision",
                existing["decision_id"],
                "updated",
                payload={"old_hash": existing["content_hash"], "new_hash": content_hash},
            )
        except Exception:
            logger.warning("Failed to record decision change event for %s", file_path)

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
        file_path=rel_path,
        content_hash=content_hash,
        context=parsed["context"],
        consequences=parsed["consequences"],
        decisions=[parsed["decision"]],
        assumptions=[],
        open_questions=[],
        body=parsed.get("body"),
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
    """Export a single decision from DB to Nygard-format markdown."""
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

    if number:
        fname = f"ADR-{number:03d}-{slug}.md" if slug else f"ADR-{number:03d}.md"
    else:
        fname = f"decision-{decision_id[:8]}.md"

    alternatives_text = ""
    rationale_text = ""
    stored_body = d.get("body")
    if stored_body:
        body_sections = _parse_body_sections(stored_body)

        alt_raw = body_sections.get("Alternativas consideradas", body_sections.get("Alternativas Consideradas", ""))
        if alt_raw:
            alt_names = [al[4:].strip() for al in alt_raw.split("\n") if al.startswith("### ")]
            if alt_names:
                alternatives_text = ", ".join(alt_names)

        cons_raw = body_sections.get("Consequencias", body_sections.get("Consequências", ""))
        if cons_raw:
            for cline in cons_raw.split("\n"):
                cline_s = cline.strip()
                if cline_s.startswith("- [+]"):
                    rationale_text = cline_s[5:].strip()
                    break

    frontmatter = yaml.dump(
        {
            "title": title,
            "status": status,
            "decision": decision_text,
            "alternatives": alternatives_text,
            "rationale": rationale_text,
        },
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).strip()

    if stored_body:
        content = f"---\n{frontmatter}\n---\n{stored_body}\n"
    else:
        context = d.get("context") or ""
        consequences = d.get("consequences") or ""
        now_str = _now()[:10]
        created = (d.get("created_at") or now_str)[:10]
        updated = (d.get("updated_at") or now_str)[:10]
        content = (
            f"---\n{frontmatter}\n---\n"
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
    file_hash = compute_file_hash(out_path)
    conn.execute(
        "UPDATE decisions SET file_path=?, content_hash=? WHERE decision_id=?",
        (to_relative_path(out_path), file_hash, decision_id),
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
    return _fts5_search(
        conn,
        query,
        table="decisions",
        fts_table="decisions_fts",
        like_columns=["title", "context"],
        filters={"platform_id": platform_id},
    )


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
    from db_core import _validate_identifiers

    _validate_identifiers(*allowed)  # guard against future changes adding unsafe column names
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
# Memory Import/Export (Markdown <-> DB)
# ══════════════════════════════════════


def _parse_memory_markdown(file_path: Path) -> dict | None:
    """Parse a memory markdown file into a dict."""
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
        "platform_id": fm.get("platform"),
        "content": parts[2].strip(),
        "file_path": to_relative_path(file_path),
    }


def import_memory_from_markdown(conn: sqlite3.Connection, file_path: Path) -> str | None:
    """Import a single memory markdown file. Returns memory_id or None."""
    parsed = _parse_memory_markdown(Path(file_path))
    if parsed is None:
        return None
    content_hash = compute_file_hash(file_path)
    rel_path = to_relative_path(file_path)
    existing = conn.execute(
        "SELECT memory_id, content_hash FROM memory_entries WHERE file_path=? OR file_path=?",
        (rel_path, str(file_path)),
    ).fetchone()
    if existing and existing["content_hash"] == content_hash:
        return existing["memory_id"]
    memory_id = existing["memory_id"] if existing else os.urandom(8).hex()
    platform_id = parsed.get("platform_id")
    try:
        return insert_memory(
            conn,
            parsed["type"],
            parsed["name"],
            parsed["content"],
            memory_id=memory_id,
            platform_id=platform_id,
            description=parsed["description"],
            file_path=rel_path,
            content_hash=content_hash,
            source="import",
        )
    except sqlite3.IntegrityError:
        logger.warning("Invalid platform_id '%s' in %s — importing without platform", platform_id, file_path)
        return insert_memory(
            conn,
            parsed["type"],
            parsed["name"],
            parsed["content"],
            memory_id=memory_id,
            description=parsed["description"],
            file_path=rel_path,
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
    fm_dict = {"name": d["name"], "description": d.get("description") or "", "type": d["type"]}
    if d.get("platform_id"):
        fm_dict["platform"] = d["platform_id"]
    frontmatter = yaml.dump(
        fm_dict,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).strip()
    content = f"---\n{frontmatter}\n---\n\n{d['content']}\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / fname
    out_path.write_text(content, encoding="utf-8")
    file_hash = compute_file_hash(out_path)
    conn.execute(
        "UPDATE memory_entries SET file_path=?, content_hash=? WHERE memory_id=?",
        (to_relative_path(out_path), file_hash, memory_id),
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


def search_memories(
    conn: sqlite3.Connection,
    query: str,
    type_: str | None = None,
    platform_id: str | None = None,
) -> list[dict]:
    """Full-text search across memory entries using FTS5.

    Args:
        query: Search query string.
        type_: Optional memory type filter.
        platform_id: Optional platform filter. None means search all platforms.
    """
    return _fts5_search(
        conn,
        query,
        table="memory_entries",
        fts_table="memory_fts",
        like_columns=["name", "content"],
        filters={"type": type_, "platform_id": platform_id},
    )
