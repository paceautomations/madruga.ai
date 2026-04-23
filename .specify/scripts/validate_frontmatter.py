#!/usr/bin/env python3
"""Validate YAML frontmatter in all platform Markdown files.

Scans platforms/<name>/**/*.md for files with --- frontmatter blocks and
attempts to parse them with yaml.safe_load. Reports files with invalid
YAML so they can be fixed before the Astro portal crashes on startup.

Exit code 0 = all valid. Exit code 1 = one or more files broken.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def validate_file(path: Path) -> str | None:
    """Return error string if frontmatter is invalid, else None."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return str(e)
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return None
    try:
        yaml.safe_load(m.group(1))
        return None
    except yaml.YAMLError as e:
        return str(e).splitlines()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="*",
        default=["platforms"],
        help="Directories to scan (default: platforms/)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    errors: list[dict] = []
    repo_root = Path(__file__).parent.parent.parent

    for root in args.roots:
        base = repo_root / root
        if not base.exists():
            continue
        for md in sorted(base.rglob("*.md")):
            err = validate_file(md)
            if err:
                errors.append({"file": str(md.relative_to(repo_root)), "error": err})

    if args.json:
        import json

        print(json.dumps({"ok": len(errors) == 0, "errors": errors}, indent=2))
    else:
        if errors:
            print(f"frontmatter errors found: {len(errors)}", file=sys.stderr)
            for e in errors:
                print(f"  BROKEN  {e['file']}", file=sys.stderr)
                print(f"          {e['error']}", file=sys.stderr)
        else:
            print("frontmatter ok")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
