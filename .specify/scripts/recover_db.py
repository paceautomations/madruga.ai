#!/usr/bin/env python3
"""
recover_db.py — Merge historical telemetry from a git-archived DB snapshot.

Context: On 2026-04-10 the live DB corrupted and was rebuilt from scratch,
losing all pipeline_runs / traces / eval_scores / commits. The last valid
version was tracked in git at commit f2f55ec.

Usage:
    python3 .specify/scripts/recover_db.py                        # default commit
    python3 .specify/scripts/recover_db.py --commit <sha>         # custom commit
    python3 .specify/scripts/recover_db.py --from-file /path.db   # local file

Idempotent: INSERT OR IGNORE on PKs — safe to run twice.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import REPO_ROOT  # noqa: E402

DEFAULT_COMMIT = "f2f55ec"
DB_PATH = REPO_ROOT / ".pipeline" / "madruga.db"

# Tables to merge, in FK-safe order.
# Each entry: (table, pk_cols, data_cols | None).
# If data_cols is None, SELECT * is used with INSERT OR IGNORE on PK.
MERGE_TABLES = [
    # PK-based tables: INSERT OR IGNORE keyed on primary key
    ("traces", ["trace_id"]),
    ("pipeline_runs", ["run_id"]),
    ("eval_scores", ["score_id"]),
    # commits: autoincrement PK, but UNIQUE on sha
    ("commits", ["sha"]),
    # events: autoincrement PK, deduplicate by natural key
    ("events", None),
    # memory_entries: text PK
    ("memory_entries", ["memory_id"]),
    # artifact_provenance: composite PK
    ("artifact_provenance", ["platform_id", "file_path"]),
]


def extract_from_git(commit: str, dest: Path) -> None:
    """Extract the DB blob from a git commit into dest."""
    result = subprocess.run(
        ["git", "show", f"{commit}:.pipeline/madruga.db"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"ERROR: git show failed: {result.stderr.decode()}", file=sys.stderr)
        sys.exit(1)
    dest.write_bytes(result.stdout)
    print(f"Extracted {len(result.stdout):,} bytes from commit {commit}")


def count_rows(conn, tables: list[str]) -> dict[str, int]:
    """Count rows in each table."""
    counts = {}
    for t in tables:
        try:
            counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
        except Exception:
            counts[t] = -1
    return counts


def merge(live_db: Path, recovered_db: Path) -> dict:
    """ATTACH recovered DB and merge historical data into live DB."""
    import sqlite3

    # Validate recovered DB
    r_conn = sqlite3.connect(str(recovered_db))
    integrity = r_conn.execute("PRAGMA integrity_check").fetchone()
    if integrity[0] != "ok":
        print(f"ERROR: Recovered DB failed integrity check: {integrity[0]}", file=sys.stderr)
        sys.exit(1)
    print("Recovered DB integrity: ok")
    r_conn.close()

    # Open live DB
    conn = sqlite3.connect(str(live_db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")  # Disable FK during merge
    conn.execute("PRAGMA busy_timeout=5000")

    table_names = [t[0] for t in MERGE_TABLES]

    # Count before
    before = count_rows(conn, table_names)
    r_conn2 = sqlite3.connect(str(recovered_db))
    recovered_counts = count_rows(r_conn2, table_names)
    r_conn2.close()

    print("\n--- Before merge ---")
    print(f"{'Table':<25} {'Live':>8} {'Recovered':>10}")
    for t in table_names:
        print(f"{t:<25} {before[t]:>8} {recovered_counts[t]:>10}")

    # ATTACH
    conn.execute("ATTACH DATABASE ? AS recovered", (str(recovered_db),))

    total_inserted = {}

    for entry in MERGE_TABLES:
        table = entry[0]
        pk_cols = entry[1] if len(entry) > 1 else None

        if recovered_counts.get(table, 0) <= 0:
            total_inserted[table] = 0
            continue

        if table == "events":
            # Deduplicate by natural key (no reliable PK across DBs)
            sql = """
                INSERT INTO events (platform_id, entity_type, entity_id, action, actor, payload, created_at)
                SELECT r.platform_id, r.entity_type, r.entity_id, r.action, r.actor, r.payload, r.created_at
                FROM recovered.events r
                WHERE NOT EXISTS (
                    SELECT 1 FROM events e
                    WHERE e.platform_id IS r.platform_id
                      AND e.entity_type = r.entity_type
                      AND e.entity_id = r.entity_id
                      AND e.action = r.action
                      AND e.created_at = r.created_at
                )
            """
            cursor = conn.execute(sql)
            total_inserted[table] = cursor.rowcount
        elif table == "commits":
            # Autoincrement PK but UNIQUE on sha
            cols = [
                "sha",
                "message",
                "author",
                "platform_id",
                "epic_id",
                "source",
                "committed_at",
                "files_json",
            ]
            cols_str = ", ".join(cols)
            sql = f"INSERT OR IGNORE INTO commits ({cols_str}) SELECT {cols_str} FROM recovered.commits"
            cursor = conn.execute(sql)
            total_inserted[table] = cursor.rowcount
        elif pk_cols:
            # Get column names from live DB schema
            cols_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
            cols = [c[1] for c in cols_info]
            # Get columns that exist in recovered DB too
            r_cols_info = conn.execute(f"PRAGMA recovered.table_info({table})").fetchall()
            r_cols = {c[1] for c in r_cols_info}
            # Use intersection (recovered may lack newer columns)
            shared_cols = [c for c in cols if c in r_cols]
            cols_str = ", ".join(shared_cols)
            sql = f"INSERT OR IGNORE INTO {table} ({cols_str}) SELECT {cols_str} FROM recovered.{table}"
            cursor = conn.execute(sql)
            total_inserted[table] = cursor.rowcount

    conn.commit()
    conn.execute("DETACH DATABASE recovered")
    conn.execute("PRAGMA foreign_keys=ON")  # restore after merge

    # Count after
    after = count_rows(conn, table_names)

    print("\n--- After merge ---")
    print(f"{'Table':<25} {'Before':>8} {'After':>8} {'Inserted':>10}")
    for t in table_names:
        inserted = total_inserted.get(t, 0)
        print(f"{t:<25} {before[t]:>8} {after[t]:>8} {inserted:>10}")

    # Final integrity check
    integrity = conn.execute("PRAGMA integrity_check").fetchone()
    print(f"\nFinal integrity check: {integrity[0]}")

    conn.close()

    return {"before": before, "after": after, "inserted": total_inserted}


def main():
    parser = argparse.ArgumentParser(description="Recover historical DB data")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--commit", default=DEFAULT_COMMIT, help="Git commit with DB snapshot")
    source.add_argument("--from-file", type=Path, help="Use a local DB file instead of git")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"ERROR: Live DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    if args.from_file:
        if not args.from_file.exists():
            print(f"ERROR: File not found: {args.from_file}", file=sys.stderr)
            sys.exit(1)
        recovered_path = args.from_file
        print(f"Using local file: {recovered_path}")
        result = merge(DB_PATH, recovered_path)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            recovered_path = Path(tmpdir) / "madruga_recovered.db"
            extract_from_git(args.commit, recovered_path)
            result = merge(DB_PATH, recovered_path)

    total = sum(result["inserted"].values())
    print(f"\nRecovery complete: {total} rows merged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
