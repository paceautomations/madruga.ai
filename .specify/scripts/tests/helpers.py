"""Shared test helpers — importable by any test module."""

import sqlite3
from pathlib import Path


def init_mem_db() -> sqlite3.Connection:
    """Create an in-memory SQLite DB with all migrations applied."""
    from db_core import migrate

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn


def write_memory_md(path: Path, name: str, type_: str, desc: str, body: str = "content") -> Path:
    """Write a memory markdown file with valid frontmatter."""
    content = f"---\nname: {name}\ntype: {type_}\ndescription: {desc}\n---\n\n{body}\n"
    path.write_text(content, encoding="utf-8")
    return path
