#!/usr/bin/env python3
"""
seed.py — Idempotent DB bootstrap for madruga.ai.

A1: The runtime SQLite DB at ``.pipeline/madruga.db`` is NOT tracked in git
(tracking a live WAL DB caused corruption on ``git checkout``/``stash``). This
script recreates it from the canonical filesystem sources — platform.yaml,
epic pitches, and ADR markdown — so a fresh clone can reach a working state
with one command.

Usage:
    make seed
    # or
    python3 .specify/scripts/seed.py
    python3 .specify/scripts/seed.py --platform prosauai        # single platform
    python3 .specify/scripts/seed.py --force                    # drop + recreate

Idempotent: running twice on the same filesystem produces the same DB state.
Preserves live pipeline run/trace history (only re-seeds deterministic data
from platform.yaml + pitches + ADRs).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import REPO_ROOT  # noqa: E402


def _discover_platforms() -> list[str]:
    """Return platform slugs for every ``platforms/*/platform.yaml`` in the repo."""
    platforms_dir = REPO_ROOT / "platforms"
    if not platforms_dir.exists():
        return []
    return sorted(p.name for p in platforms_dir.iterdir() if p.is_dir() and (p / "platform.yaml").exists())


def seed(platform: str | None = None, force: bool = False) -> int:
    """Seed the DB from filesystem sources.

    Returns the number of platforms seeded.
    """
    from db import get_conn, migrate, seed_from_filesystem

    db_path = REPO_ROOT / ".pipeline" / "madruga.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if force and db_path.exists():
        # Also remove WAL/SHM siblings — otherwise SQLite reopens the stale state.
        for suffix in ("", "-wal", "-shm"):
            candidate = db_path.with_name(db_path.name + suffix)
            if candidate.exists():
                candidate.unlink()
        print(f"seed: removed existing DB at {db_path}", file=sys.stderr)

    conn = get_conn()
    try:
        migrate(conn)

        targets = [platform] if platform else _discover_platforms()
        if not targets:
            print("seed: no platforms found under platforms/", file=sys.stderr)
            return 0

        total = 0
        for slug in targets:
            pdir = REPO_ROOT / "platforms" / slug
            if not (pdir / "platform.yaml").exists():
                print(f"seed: skipping {slug} (no platform.yaml)", file=sys.stderr)
                continue
            summary = seed_from_filesystem(conn, slug, pdir)
            print(
                f"seed: {slug} — "
                f"status={summary.get('status', '?')} "
                f"nodes={summary.get('nodes', 0)} "
                f"epics={summary.get('epics', 0)}",
                file=sys.stderr,
            )
            total += 1

        conn.commit()
        return total
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed madruga.ai DB from filesystem (idempotent)",
    )
    parser.add_argument("--platform", default=None, help="Seed only this platform slug")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing madruga.db (+wal/-shm) before seeding",
    )
    args = parser.parse_args()

    try:
        count = seed(platform=args.platform, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"seed: FAILED — {exc}", file=sys.stderr)
        sys.exit(1)

    if count == 0:
        print("seed: nothing seeded", file=sys.stderr)
        sys.exit(1)

    print(f"seed: done — {count} platform(s) seeded", file=sys.stderr)


if __name__ == "__main__":
    main()
