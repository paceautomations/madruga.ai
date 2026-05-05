#!/usr/bin/env python3
"""pre_commit_png_size.py — reject committed PNGs > 500KB (FR-034).

Wired in `.pre-commit-config.yaml` against ``platforms/*/business/shots/*.png``.
Exit code 0 when every passed file fits the budget (or is skipped); exit 1 if
any PNG exceeds the limit, listing the offenders.

Files that don't exist (e.g. deletions staged by pre-commit) are skipped.
Non-PNG paths are skipped — the hook scope is enforced by the pre-commit
``files:`` regex but we double-check defensively.
"""

from __future__ import annotations

import sys
from pathlib import Path

MAX_BYTES = 500_000  # FR-034 — hard limit


def _is_png(path: Path) -> bool:
    return path.suffix.lower() == ".png"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    offenders: list[tuple[Path, int]] = []
    for raw in args:
        p = Path(raw)
        if not p.exists() or not _is_png(p):
            continue
        size = p.stat().st_size
        if size > MAX_BYTES:
            offenders.append((p, size))
    if not offenders:
        return 0
    print(
        "Refusing to commit: PNG(s) exceed 500KB budget (FR-034).",
        file=sys.stderr,
    )
    for path, size in offenders:
        print(
            f"  {path}  {size:,} bytes  (limit 500_000) — recompress, "
            f"reduce viewport, or strip decorative imagery via mock_routes.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
