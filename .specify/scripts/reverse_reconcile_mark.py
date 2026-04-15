"""Mark commits as reconciled. Used by forward reconcile (end of epic) and reverse reconcile.

Handles composite SHAs (`<sha>:<platform>`) transparently. Atomic (single transaction).

Usage:
    python3 reverse_reconcile_mark.py --platform <name> --shas sha1,sha2,sha3
    python3 reverse_reconcile_mark.py --platform <name> --epic <epic-id>
    python3 reverse_reconcile_mark.py --platform <name> --shas-file /path/to/shas.txt
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".specify" / "scripts"))

import db_core  # noqa: E402

log = logging.getLogger("reverse_reconcile_mark")


def mark_shas(platform_id: str, shas: list[str], db_path: Path | None = None) -> int:
    """Mark SHAs as reconciled_at=now(). Handles composite form `<sha>:<platform>`.

    Returns number of rows updated.
    """
    if not shas:
        return 0
    # Two IN clauses (raw + composite) keeps expression depth bounded under SQLITE_MAX_EXPR_DEPTH
    composite = [f"{s}:{platform_id}" for s in shas]
    raw_placeholders = ",".join("?" for _ in shas)
    comp_placeholders = ",".join("?" for _ in composite)
    with db_core.get_conn(db_path) as conn:
        cur = conn.execute(
            f"UPDATE commits SET reconciled_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
            f"WHERE platform_id = ? AND reconciled_at IS NULL "
            f"AND (sha IN ({raw_placeholders}) OR sha IN ({comp_placeholders}))",
            [platform_id, *shas, *composite],
        )
        conn.commit()
        return cur.rowcount


def mark_epic(platform_id: str, epic_id: str, db_path: Path | None = None) -> int:
    """Mark all commits of a given epic as reconciled."""
    with db_core.get_conn(db_path) as conn:
        cur = conn.execute(
            "UPDATE commits SET reconciled_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
            "WHERE platform_id = ? AND epic_id = ? AND reconciled_at IS NULL",
            (platform_id, epic_id),
        )
        conn.commit()
        return cur.rowcount


def count_unreconciled(platform_id: str, db_path: Path | None = None) -> int:
    with db_core.get_conn(db_path) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM commits WHERE platform_id = ? AND reconciled_at IS NULL",
            (platform_id,),
        ).fetchone()[0]


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--platform", required=True)
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--shas", help="Comma-separated SHAs")
    grp.add_argument("--shas-file", type=Path, help="File with one SHA per line")
    grp.add_argument("--epic", help="Mark all commits of epic <epic-id>")
    grp.add_argument("--count-unreconciled", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.count_unreconciled:
        n = count_unreconciled(args.platform)
        out = {"platform": args.platform, "unreconciled": n}
    elif args.epic:
        n = mark_epic(args.platform, args.epic)
        out = {"platform": args.platform, "epic": args.epic, "marked": n}
    else:
        if args.shas:
            shas = [s.strip() for s in args.shas.split(",") if s.strip()]
        else:
            shas = [line.strip() for line in args.shas_file.read_text().splitlines() if line.strip()]
        n = mark_shas(args.platform, shas)
        out = {"platform": args.platform, "input_shas": len(shas), "marked": n}

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for k, v in out.items():
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
