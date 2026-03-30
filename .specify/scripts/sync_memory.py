#!/usr/bin/env python3
"""
sync_memory.py — Sync .claude/memory/*.md files to/from the SQLite BD.

Resolves the dual-write problem: Claude Code auto-memory writes to .claude/memory/,
but BD is the canonical source (Alternativa B). This script detects changes on both
sides and reconciles:

  - New/changed .claude/memory/ files → import to BD (filesystem wins for auto-memory)
  - New/changed BD entries → export to .claude/memory/ (BD wins for manual inserts)
  - Unchanged on both sides → skip

Usage:
    python3 .specify/scripts/sync_memory.py                # bidirectional sync
    python3 .specify/scripts/sync_memory.py --import-only  # filesystem → BD only
    python3 .specify/scripts/sync_memory.py --export-only  # BD → filesystem only
    python3 .specify/scripts/sync_memory.py --dry-run      # show what would change
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import (
    compute_file_hash,
    export_memory_to_markdown,
    get_conn,
    get_memories,
    import_memory_from_markdown,
    migrate,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def find_memory_dirs() -> list[Path]:
    """Find memory directories for this repo.

    Searches both:
    1. ~/.claude/projects/<project-slug>/memory/ (Claude Code auto-memory)
    2. <repo>/.claude/projects/*/memory/ (if exists)
    """
    dirs: list[Path] = []

    # Claude Code stores auto-memory at ~/.claude/projects/<slug>/memory/
    home_claude = Path.home() / ".claude" / "projects"
    if home_claude.exists():
        # The slug is derived from the repo path: / and . replaced by -
        repo_slug = str(REPO_ROOT).replace("/", "-").replace(".", "-")
        project_dir = home_claude / repo_slug / "memory"
        if project_dir.is_dir():
            dirs.append(project_dir)

    # Also check inside repo (legacy or custom setups)
    repo_claude = REPO_ROOT / ".claude" / "projects"
    if repo_claude.exists():
        for d in repo_claude.rglob("memory"):
            if d.is_dir() and d not in dirs:
                dirs.append(d)

    return dirs


def sync(
    import_only: bool = False,
    export_only: bool = False,
    dry_run: bool = False,
) -> dict:
    """Bidirectional sync between .claude/memory/ and BD."""
    conn = get_conn()
    migrate(conn)

    memory_dirs = find_memory_dirs()
    if not memory_dirs:
        logger.warning("No .claude/projects/*/memory/ directories found")
        conn.close()
        return {"imported": 0, "exported": 0, "skipped": 0}

    stats = {"imported": 0, "exported": 0, "skipped": 0}

    # Phase 1: Import filesystem → BD (new/changed files)
    if not export_only:
        for memory_dir in memory_dirs:
            for md_file in sorted(memory_dir.glob("*.md")):
                if md_file.name == "MEMORY.md":
                    continue
                file_hash = compute_file_hash(md_file)
                existing = conn.execute(
                    "SELECT memory_id, content_hash FROM memory_entries WHERE file_path=?",
                    (str(md_file),),
                ).fetchone()
                if existing and existing["content_hash"] == file_hash:
                    stats["skipped"] += 1
                    continue
                if dry_run:
                    action = "update" if existing else "import"
                    logger.info("[DRY RUN] Would %s: %s", action, md_file.name)
                    stats["imported"] += 1
                    continue
                result = import_memory_from_markdown(conn, md_file)
                if result:
                    stats["imported"] += 1
                    logger.info("Imported: %s", md_file.name)

    # Phase 2: Export BD → filesystem (entries without matching file or with stale file)
    if not import_only:
        primary_dir = memory_dirs[0]
        all_memories = get_memories(conn)
        existing_files = set()
        for memory_dir in memory_dirs:
            for md_file in memory_dir.glob("*.md"):
                if md_file.name != "MEMORY.md":
                    existing_files.add(str(md_file))

        for mem in all_memories:
            file_path = mem.get("file_path")
            if file_path and file_path in existing_files:
                # File exists — check if BD is newer
                if mem.get("content_hash"):
                    try:
                        current_hash = compute_file_hash(file_path)
                        if current_hash == mem["content_hash"]:
                            continue  # In sync
                    except FileNotFoundError:
                        pass  # File was deleted, re-export
                else:
                    continue  # No hash to compare, skip
            if dry_run:
                logger.info("[DRY RUN] Would export: %s", mem["name"])
                stats["exported"] += 1
                continue
            export_memory_to_markdown(conn, mem["memory_id"], primary_dir)
            stats["exported"] += 1
            logger.info("Exported: %s", mem["name"])

    conn.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync memory between filesystem and BD")
    parser.add_argument("--import-only", action="store_true", help="Only import filesystem → BD")
    parser.add_argument("--export-only", action="store_true", help="Only export BD → filesystem")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change")
    args = parser.parse_args()

    stats = sync(
        import_only=args.import_only,
        export_only=args.export_only,
        dry_run=args.dry_run,
    )
    prefix = "[DRY RUN] " if args.dry_run else ""
    imp, exp, skp = stats["imported"], stats["exported"], stats["skipped"]
    print(f"{prefix}Sync complete: {imp} imported, {exp} exported, {skp} unchanged")


if __name__ == "__main__":
    main()
