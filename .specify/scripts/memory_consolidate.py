#!/usr/bin/env python3
"""
memory_consolidate.py — Report stale memory entries, possible duplicates, and index health.

Dry-run by default. No files modified without --apply.

Usage:
    python3 .specify/scripts/memory_consolidate.py --dry-run
    python3 .specify/scripts/memory_consolidate.py --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _find_memory_dir() -> Path | None:
    """Discover the memory directory for this repo under ~/.claude/projects/."""
    # The Claude project dir encodes the repo path as a slug
    home_claude = Path.home() / ".claude" / "projects"
    if home_claude.exists():
        for candidate in home_claude.iterdir():
            mem = candidate / "memory"
            if mem.is_dir():
                return mem
    # Fallback: look under repo root (for tests or non-standard setups)
    repo_claude = REPO_ROOT / ".claude" / "projects"
    if repo_claude.exists():
        for candidate in repo_claude.rglob("memory"):
            if candidate.is_dir():
                return candidate
    return None


# Files in memory dir that are not memory entries
INDEX_FILENAME = "MEMORY.md"


def scan_memory_files(memory_dir: Path) -> tuple[list[dict], list[Path]]:
    """Read all *.md in memory_dir, parse frontmatter, return (entries, unparseable)."""
    entries: list[dict] = []
    unparseable: list[Path] = []

    for md_file in sorted(memory_dir.glob("*.md")):
        if md_file.name == INDEX_FILENAME:
            continue
        content = md_file.read_text(encoding="utf-8")
        if not content.startswith("---"):
            unparseable.append(md_file)
            continue
        end = content.find("---", 3)
        if end == -1:
            unparseable.append(md_file)
            continue
        try:
            fm = yaml.safe_load(content[3:end])
            if not isinstance(fm, dict):
                unparseable.append(md_file)
                continue
        except yaml.YAMLError:
            unparseable.append(md_file)
            continue

        entries.append(
            {
                "path": md_file,
                "name": fm.get("name", md_file.stem),
                "type": fm.get("type", "unknown"),
                "description": fm.get("description", ""),
                "mtime": md_file.stat().st_mtime,
            }
        )

    return entries, unparseable


def find_stale(entries: list[dict], threshold_days: int = 90) -> list[dict]:
    """Return entries older than threshold_days based on file mtime."""
    now = datetime.now(timezone.utc)
    stale = []
    for entry in entries:
        mtime_dt = datetime.fromtimestamp(entry["mtime"], tz=timezone.utc)
        age_days = (now - mtime_dt).days
        if age_days > threshold_days:
            stale.append({**entry, "age_days": age_days, "last_modified": mtime_dt.strftime("%Y-%m-%d")})
    return stale


def find_possible_duplicates(entries: list[dict], similarity_threshold: float = 0.4) -> list[tuple]:
    """Find pairs of same-type entries with high Jaccard similarity on description tokens."""
    duplicates = []
    for i, a in enumerate(entries):
        tokens_a = set(a["description"].lower().split())
        if not tokens_a:
            continue
        for b in entries[i + 1 :]:
            if a["type"] != b["type"]:
                continue
            tokens_b = set(b["description"].lower().split())
            if not tokens_b:
                continue
            intersection = len(tokens_a & tokens_b)
            union = len(tokens_a | tokens_b)
            jaccard = intersection / union if union else 0
            if jaccard > similarity_threshold:
                duplicates.append((a, b, round(jaccard, 2)))
    return duplicates


def check_index_health(memory_dir: Path) -> dict:
    """Check MEMORY.md line count and return health status."""
    index_path = memory_dir / INDEX_FILENAME
    if not index_path.exists():
        return {"lines": 0, "status": "OK"}
    lines = index_path.read_text(encoding="utf-8").count("\n") + 1
    if lines >= 200:
        status = "CRITICAL"
    elif lines >= 180:
        status = "WARNING"
    else:
        status = "OK"
    return {"lines": lines, "status": status}


def print_report(
    entries: list[dict],
    stale: list[dict],
    duplicates: list[tuple],
    health: dict,
    unparseable: list[Path],
) -> None:
    """Print the consolidation report to stdout."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("Memory Consolidation Report")
    print("============================")
    print(f"Scanned: {len(entries)} files")
    print(f"Date: {now_str}")

    print("\nSTALE (>90 days without update):")
    if stale:
        for s in stale:
            print(f"  - {s['path'].name} (last modified: {s['last_modified']}, {s['age_days']} days ago)")
    else:
        print("  (none)")

    print("\nPOSSIBLE DUPLICATES (same type + overlapping description):")
    if duplicates:
        for a, b, sim in duplicates:
            print(f"  - {a['path'].name} <-> {b['path'].name} (type: {a['type']}, similarity: {sim})")
    else:
        print("  (none)")

    print("\nINDEX HEALTH:")
    status_msg = f"  - MEMORY.md: {health['lines']} lines"
    if health["status"] == "WARNING":
        status_msg += " (WARNING: approaching 200-line limit)"
    elif health["status"] == "CRITICAL":
        status_msg += " (CRITICAL: at or exceeding 200-line limit)"
    else:
        status_msg += " (OK)"
    print(status_msg)

    if unparseable:
        print("\nUNPARSEABLE FILES:")
        for p in unparseable:
            print(f"  - {p.name}")

    if stale or duplicates:
        print("\nACTIONS SUGGESTED:")
        n = 1
        for s in stale:
            print(f"  {n}. Review or delete: {s['path'].name} (stale)")
            n += 1
        for a, b, _ in duplicates:
            print(f"  {n}. Consider merging: {a['path'].name} + {b['path'].name}")
            n += 1
        if health["status"] != "OK":
            print(f"  {n}. Prune MEMORY.md to free up index capacity")

    print("\nRun with --apply to mark stale entries for review (adds [STALE] prefix to body).")


def apply_stale_markers(stale_entries: list[dict]) -> int:
    """Prepend [STALE - review by YYYY-MM-DD] header to stale files. Returns count applied."""
    from datetime import timedelta

    review_by = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    marker = f"[STALE - review by {review_by}]"
    applied = 0

    for entry in stale_entries:
        path: Path = entry["path"]
        content = path.read_text(encoding="utf-8")
        if marker in content or "[STALE -" in content:
            continue
        # Insert marker after frontmatter closing ---
        end = content.find("---", 3)
        if end == -1:
            continue
        # Find end of the closing --- line
        newline_after = content.find("\n", end)
        if newline_after == -1:
            insert_pos = len(content)
        else:
            insert_pos = newline_after + 1
        updated = content[:insert_pos] + f"\n{marker}\n" + content[insert_pos:]
        path.write_text(updated, encoding="utf-8")
        applied += 1

    return applied


def main() -> None:
    parser = argparse.ArgumentParser(description="Memory health monitoring and consolidation")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Report only, no changes (default)")
    parser.add_argument("--apply", action="store_true", help="Mark stale entries for review")
    parser.add_argument("--memory-dir", type=Path, default=None, help="Override memory directory path")
    args = parser.parse_args()

    memory_dir = args.memory_dir or _find_memory_dir()
    if not memory_dir or not memory_dir.exists():
        print(f"Memory directory not found: {memory_dir}", file=sys.stderr)
        sys.exit(1)

    entries, unparseable = scan_memory_files(memory_dir)
    stale = find_stale(entries)
    duplicates = find_possible_duplicates(entries)
    health = check_index_health(memory_dir)

    print_report(entries, stale, duplicates, health, unparseable)

    if args.apply:
        applied = apply_stale_markers(stale)
        print(f"\nApplied stale markers to {applied} file(s).")


if __name__ == "__main__":
    main()
