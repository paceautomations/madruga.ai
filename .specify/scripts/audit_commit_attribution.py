"""Audit + cleanup mis-attributed commits in the pipeline DB.

A commit is considered mis-attributed when ``commits.epic_id`` belongs to a
platform whose ``platforms/<X>/epics/<epic_id>/`` directory exists, but
``commits.platform_id`` points to a different platform. This happens when:

  - The local hook tagged a commit by file path (fallback to madruga-ai)
    while the user was actually working on another platform's epic.
  - ``backfill_commits.py`` parsed an epic slug that later moved to a
    different platform (e.g. ``fulano`` was renamed to ``madruga-ai``).

The script does NOT touch ``host_repo`` — that column records the physical
repo where the SHA lives and is unrelated to who owns the work.

Usage:
    python3 .specify/scripts/audit_commit_attribution.py --report
    python3 .specify/scripts/audit_commit_attribution.py --apply [--backup PATH]

``--apply`` requires a backup path; the script copies the DB before mutating.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".specify" / "scripts"))

import db_core  # noqa: E402

log = logging.getLogger("audit_commit_attribution")


def _epic_owner_map() -> dict[str, list[str]]:
    """Return ``{epic_slug: [platform_id, ...]}`` from disk.

    A slug owned by exactly one platform is unambiguous. Multiple owners
    (rare — would mean two platforms have the same slug) is reported but
    not auto-fixed.
    """
    owners: dict[str, list[str]] = {}
    platforms_dir = REPO_ROOT / "platforms"
    if not platforms_dir.is_dir():
        return owners
    for plat_dir in platforms_dir.iterdir():
        epics_dir = plat_dir / "epics"
        if not epics_dir.is_dir():
            continue
        for epic_dir in epics_dir.iterdir():
            if epic_dir.is_dir():
                owners.setdefault(epic_dir.name, []).append(plat_dir.name)
    return owners


def audit(db_path: Path | None = None) -> dict:
    """Scan ``commits`` for mis-attributions. Returns structured report."""
    owners = _epic_owner_map()
    mismatches: list[dict] = []
    ambiguous: list[dict] = []
    with db_core.get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT platform_id, epic_id, source, COUNT(*) "
            "FROM commits WHERE epic_id IS NOT NULL "
            "GROUP BY platform_id, epic_id, source"
        ).fetchall()
    for plat, epic, source, count in rows:
        true_owners = owners.get(epic, [])
        if not true_owners:
            continue
        if plat in true_owners:
            continue
        if len(true_owners) == 1:
            mismatches.append(
                {
                    "platform_id": plat,
                    "epic_id": epic,
                    "source": source,
                    "count": count,
                    "should_be": true_owners[0],
                }
            )
        else:
            ambiguous.append(
                {
                    "platform_id": plat,
                    "epic_id": epic,
                    "source": source,
                    "count": count,
                    "candidates": true_owners,
                }
            )
    return {
        "total_mismatches": sum(m["count"] for m in mismatches),
        "total_ambiguous": sum(a["count"] for a in ambiguous),
        "mismatches": mismatches,
        "ambiguous": ambiguous,
    }


def apply_fixes(db_path: Path | None, report: dict) -> dict:
    """Re-attribute commits per the audit report's ``mismatches`` list.

    Uses the composite SHA pattern (``<sha>:<platform>``) to bypass the
    ``commits.sha UNIQUE`` constraint when a commit ends up tagged for
    multiple platforms. If the target SHA is already taken under the new
    platform, the row is skipped (logged) — caller can run audit again.
    """
    fixed = 0
    skipped = 0
    with db_core.get_conn(db_path) as conn:
        # Prefetch SHAs already tracked under each target platform (avoids N+1).
        target_plats = {m["should_be"] for m in report["mismatches"]}
        taken: dict[str, set[str]] = {}
        for plat in target_plats:
            taken[plat] = {
                row[0] for row in conn.execute("SELECT sha FROM commits WHERE platform_id = ?", (plat,)).fetchall()
            }

        for m in report["mismatches"]:
            rows = conn.execute(
                "SELECT id, sha FROM commits WHERE platform_id = ? AND epic_id = ?",
                (m["platform_id"], m["epic_id"]),
            ).fetchall()
            new_plat = m["should_be"]
            plat_taken = taken[new_plat]
            for row_id, sha in rows:
                raw_sha = sha.split(":", 1)[0]
                target_sha = f"{raw_sha}:{new_plat}" if raw_sha in plat_taken else raw_sha
                if target_sha in plat_taken:
                    log.warning("skip id=%s: %s already tracked under %s", row_id, target_sha, new_plat)
                    skipped += 1
                    continue
                conn.execute(
                    "UPDATE commits SET platform_id = ?, sha = ? WHERE id = ?",
                    (new_plat, target_sha, row_id),
                )
                plat_taken.add(target_sha)
                fixed += 1
        conn.commit()
    return {"fixed": fixed, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--report", action="store_true", help="Print audit report (no writes)")
    grp.add_argument("--apply", action="store_true", help="Apply re-attributions")
    p.add_argument("--backup", type=Path, help="Backup DB to this path before --apply (required)")
    p.add_argument("--db", type=Path, help="Path to madruga.db (default: .pipeline/madruga.db)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    db_path = args.db or REPO_ROOT / ".pipeline" / "madruga.db"
    report = audit(db_path)

    if args.report:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"Mismatches: {report['total_mismatches']} commits across {len(report['mismatches'])} groups")
            for m in report["mismatches"]:
                print(f"  {m['platform_id']}/{m['epic_id']} (source={m['source']}, n={m['count']}) → {m['should_be']}")
            if report["ambiguous"]:
                print(f"\nAmbiguous (manual fix): {report['total_ambiguous']} commits")
                for a in report["ambiguous"]:
                    print(
                        f"  {a['platform_id']}/{a['epic_id']} "
                        f"(source={a['source']}, n={a['count']}) → candidates: {a['candidates']}"
                    )
        return 0

    if not args.backup:
        print("ERROR: --apply requires --backup PATH for safety", file=sys.stderr)
        return 2
    if not db_path.is_file():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2
    backup_path = args.backup
    if backup_path.is_dir():
        backup_path = backup_path / f"madruga.db.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    log.info("Backup written: %s", backup_path)
    result = apply_fixes(db_path, report)
    log.info("Fixed: %d, Skipped: %d", result["fixed"], result["skipped"])
    if args.json:
        print(json.dumps({"backup": str(backup_path), **result}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
