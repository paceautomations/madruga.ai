"""
db.py — SQLite thin wrapper for madruga.ai pipeline state.

Zero external dependencies. Uses only Python stdlib:
sqlite3, hashlib, json, pathlib, os, logging.

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


def migrate(
    conn: sqlite3.Connection | None = None, migrations_dir: Path | None = None
) -> None:
    """Run pending migrations from .pipeline/migrations/ in order."""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    mdir = migrations_dir or MIGRATIONS_DIR
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations "
        "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    conn.commit()
    applied = {r[0] for r in conn.execute("SELECT name FROM _migrations").fetchall()}
    for sql_file in sorted(mdir.glob("*.sql")):
        if sql_file.name not in applied:
            logger.info("Applying migration: %s", sql_file.name)
            try:
                conn.executescript(sql_file.read_text())
                conn.execute(
                    "INSERT INTO _migrations (name, applied_at) VALUES (?, ?)",
                    (sql_file.name, _now()),
                )
                conn.commit()
            except Exception:
                logger.error("Migration failed: %s", sql_file.name)
                raise
    if own_conn:
        conn.close()


def compute_file_hash(path: str | Path) -> str:
    """Return 'sha256:<12-char hex>' hash of file contents."""
    data = Path(path).read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()[:12]


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
        "INSERT OR REPLACE INTO platforms "
        "(platform_id, name, title, lifecycle, repo_path, metadata, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, "
        "COALESCE((SELECT created_at FROM platforms WHERE platform_id=?), ?), ?)",
        (
            platform_id,
            name or platform_id,
            title,
            lifecycle,
            repo_path,
            metadata,
            platform_id,
            _now(),
            _now(),
        ),
    )
    conn.commit()
    logger.info("Upserted platform: %s", platform_id)


def get_platform(conn: sqlite3.Connection, platform_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM platforms WHERE platform_id=?", (platform_id,)
    ).fetchone()
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
    fields = {
        "platform_id": platform_id,
        "node_id": node_id,
        "status": status,
        "output_hash": kwargs.get("output_hash"),
        "input_hashes": kwargs.get("input_hashes", "{}"),
        "output_files": kwargs.get("output_files", "[]"),
        "completed_at": kwargs.get("completed_at"),
        "completed_by": kwargs.get("completed_by"),
        "line_count": kwargs.get("line_count"),
    }
    cols = ", ".join(fields.keys())
    placeholders = ", ".join(["?"] * len(fields))
    conn.execute(
        f"INSERT OR REPLACE INTO pipeline_nodes ({cols}) VALUES ({placeholders})",
        tuple(fields.values()),
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


def upsert_epic(
    conn: sqlite3.Connection, platform_id: str, epic_id: str, title: str = "", **kwargs
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO epics "
        "(platform_id, epic_id, title, status, appetite, priority, branch_name, file_path, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, "
        "COALESCE((SELECT created_at FROM epics WHERE platform_id=? AND epic_id=?), ?), ?)",
        (
            platform_id,
            epic_id,
            title,
            kwargs.get("status", "proposed"),
            kwargs.get("appetite"),
            kwargs.get("priority"),
            kwargs.get("branch_name"),
            kwargs.get("file_path"),
            platform_id,
            epic_id,
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
        "INSERT OR REPLACE INTO epic_nodes "
        "(platform_id, epic_id, node_id, status, output_hash, completed_at, completed_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
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


def get_epic_nodes(
    conn: sqlite3.Connection, platform_id: str, epic_id: str
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM epic_nodes WHERE platform_id=? AND epic_id=? ORDER BY node_id",
        (platform_id, epic_id),
    ).fetchall()
    return [dict(r) for r in rows]


# ══════════════════════════════════════
# Decisions
# ══════════════════════════════════════


def insert_decision(
    conn: sqlite3.Connection, platform_id: str, skill: str, title: str, **kwargs
) -> str:
    decision_id = kwargs.get("decision_id") or os.urandom(4).hex()
    decisions_json = json.dumps(kwargs.get("decisions", []))
    assumptions_json = json.dumps(kwargs.get("assumptions", []))
    open_questions_json = json.dumps(kwargs.get("open_questions", []))
    conn.execute(
        "INSERT OR REPLACE INTO decisions "
        "(decision_id, platform_id, epic_id, skill, slug, title, number, status, "
        "superseded_by, source_decision_key, file_path, "
        "decisions_json, assumptions_json, open_questions_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "COALESCE((SELECT created_at FROM decisions WHERE decision_id=?), ?), ?)",
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
            decision_id,
            _now(),
            _now(),
        ),
    )
    conn.commit()
    logger.info("Inserted decision: %s — %s", decision_id, title)
    return decision_id


def get_decisions(
    conn: sqlite3.Connection, platform_id: str, epic_id: str | None = None
) -> list[dict]:
    if epic_id:
        rows = conn.execute(
            "SELECT * FROM decisions WHERE platform_id=? AND epic_id=? ORDER BY created_at",
            (platform_id, epic_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM decisions WHERE platform_id=? ORDER BY created_at",
            (platform_id,),
        ).fetchall()
    return [dict(r) for r in rows]


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


def insert_run(
    conn: sqlite3.Connection, platform_id: str, node_id: str, **kwargs
) -> str:
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


def complete_run(
    conn: sqlite3.Connection, run_id: str, status: str = "completed", **kwargs
) -> None:
    sets = ["status=?", "completed_at=?"]
    vals: list = [status, _now()]
    for field in ("tokens_in", "tokens_out", "cost_usd", "duration_ms", "error"):
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


def get_stale_nodes(
    conn: sqlite3.Connection, platform_id: str, dag_edges: dict[str, list[str]]
) -> list[dict]:
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
            if (
                dep
                and dep["completed_at"]
                and dep["completed_at"] > node["completed_at"]
            ):
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
    counts = {"done": 0, "pending": 0, "stale": 0, "blocked": 0, "skipped": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {
        "platform_id": platform_id,
        "total_nodes": total,
        **counts,
        "progress_pct": round(counts["done"] / total * 100, 1) if total else 0,
    }


def get_epic_status(conn: sqlite3.Connection, platform_id: str, epic_id: str) -> dict:
    rows = get_epic_nodes(conn, platform_id, epic_id)
    total = len(rows)
    counts = {"done": 0, "pending": 0, "stale": 0, "blocked": 0, "skipped": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
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


def seed_from_filesystem(
    conn: sqlite3.Connection, platform_id: str, platform_dir: str | Path
) -> dict:
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
        metadata=json.dumps(
            {k: manifest[k] for k in ("views", "serve", "build") if k in manifest}
        ),
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

    logger.info(
        "Seeded %s: %d nodes, %d epics", platform_id, nodes_seeded, epics_seeded
    )
    return {"status": "ok", "nodes": nodes_seeded, "epics": epics_seeded}
