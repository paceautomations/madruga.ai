#!/usr/bin/env python3
"""
platform_cli.py — Unified CLI for managing madruga.ai platforms.

Renamed from platform.py to avoid shadowing Python stdlib 'platform' module.

Usage:
    python3 .specify/scripts/platform_cli.py new <name>        # scaffold via copier
    python3 .specify/scripts/platform_cli.py lint <name>        # validate structure
    python3 .specify/scripts/platform_cli.py lint --all         # validate all platforms
    python3 .specify/scripts/platform_cli.py sync [name]        # copier update (one or all)
    python3 .specify/scripts/platform_cli.py register <name>    # inject LikeC4 loader + validate model
    python3 .specify/scripts/platform_cli.py list               # list all platforms
    python3 .specify/scripts/platform_cli.py check-stale <name>  # detect stale pipeline nodes
    python3 .specify/scripts/platform_cli.py import-adrs <name> # import ADRs into DB
    python3 .specify/scripts/platform_cli.py export-adrs <name> # export decisions to markdown
    python3 .specify/scripts/platform_cli.py import-memory      # import .claude/memory into DB
    python3 .specify/scripts/platform_cli.py export-memory      # export memory entries to markdown
    python3 .specify/scripts/platform_cli.py status <name>      # pipeline status (human table)
    python3 .specify/scripts/platform_cli.py status --all       # all platforms (human table)
    python3 .specify/scripts/platform_cli.py status --all --json # all platforms (JSON for dashboards)
    python3 .specify/scripts/platform_cli.py use <name>         # set active platform
    python3 .specify/scripts/platform_cli.py current             # show active platform
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import yaml

from config import PLATFORMS_DIR, PORTAL_DIR, REPO_ROOT, TEMPLATE_DIR  # noqa: F401

log = logging.getLogger("platform_cli")


# -- Structured logging (NDJSON) -- Duplicated by design — no shared util module in this scripts dir


class _NDJSONFormatter(logging.Formatter):
    """Emit one JSON object per line for CI consumption."""

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
            }
        )


def _setup_logging(json_mode: bool) -> None:
    """Configure root logger for human or NDJSON output."""
    handler = logging.StreamHandler()
    if json_mode:
        handler.setFormatter(_NDJSONFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)


CANONICAL_SPEC = TEMPLATE_DIR / "template" / "model" / "spec.likec4"
LIKEC4_DIAGRAM_TSX = PORTAL_DIR / "src" / "components" / "viewers" / "LikeC4Diagram.tsx"

REQUIRED_DIRS = ["business", "engineering", "decisions", "epics", "model"]
REQUIRED_FILES = [
    "platform.yaml",
    "business/vision.md",
    "business/solution-overview.md",
    "engineering/domain-model.md",
    "engineering/context-map.md",
    "engineering/integrations.md",
    "engineering/blueprint.md",
    "model/spec.likec4",
    "model/likec4.config.json",
]
AUTO_MARKERS = {
    "engineering/context-map.md": ["domains", "relations"],
    "engineering/integrations.md": ["integrations"],
}
ADR_REQUIRED_FIELDS = ["title", "status", "decision", "alternatives", "rationale"]
EPIC_REQUIRED_FIELDS = ["title", "status"]


def _ok(msg: str) -> None:
    log.info(msg)


def _warn(msg: str) -> None:
    log.warning(msg)


def _error(msg: str) -> None:
    log.error(msg)


@lru_cache(maxsize=None)
def _discover_platforms() -> list[str]:
    """Return sorted list of platform names that have platform.yaml."""
    return sorted(d.name for d in PLATFORMS_DIR.iterdir() if d.is_dir() and (d / "platform.yaml").exists())


def _inject_platform_loader(name: str) -> bool:
    """Add a platform import to LikeC4Diagram.tsx platformLoaders map.

    Returns True if injected, False if already present.
    """
    if not LIKEC4_DIAGRAM_TSX.exists():
        _warn(f"LikeC4Diagram.tsx not found at {LIKEC4_DIAGRAM_TSX}")
        return False

    content = LIKEC4_DIAGRAM_TSX.read_text()

    # Check if already registered
    if f"'likec4:react/{name}'" in content:
        _ok(f"Platform '{name}' already in LikeC4Diagram.tsx")
        return False

    # Find the closing brace of platformLoaders and insert before it
    # Pattern: line with just `};` after the loader entries
    new_entry = f"  '{name}': () => import('likec4:react/{name}'),"
    pattern = r"(const platformLoaders:[^{]*\{[^}]*)(})"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        _error("Could not find platformLoaders in LikeC4Diagram.tsx")
        return False

    # Insert the new entry before the closing brace
    before = match.group(1).rstrip()
    updated = content[: match.start()] + before + "\n" + new_entry + "\n" + match.group(2) + content[match.end() :]
    LIKEC4_DIAGRAM_TSX.write_text(updated)
    _ok(f"Injected '{name}' into LikeC4Diagram.tsx platformLoaders")
    return True


# -- Commands --


def cmd_list() -> None:
    """List all discovered platforms with repo info and tags."""
    from db import get_active_platform, get_conn, get_platform, migrate

    platforms = _discover_platforms()
    if not platforms:
        print("No platforms found.")
        return

    with get_conn() as conn:
        migrate(conn)
        active = get_active_platform(conn)

        print(f"  {'Name':<20} {'Lifecycle':<13} {'Repo':<30} {'Tags'}")
        print(f"  {'-' * 80}")
        for name in platforms:
            pdir = PLATFORMS_DIR / name
            manifest = yaml.safe_load((pdir / "platform.yaml").read_text())
            lifecycle = manifest.get("lifecycle", "?")

            # Try DB first for repo info, fallback to YAML
            db_plat = get_platform(conn, name)
            repo = manifest.get("repo", {})
            repo_org = (db_plat or {}).get("repo_org") or repo.get("org", "")
            repo_name = (db_plat or {}).get("repo_name") or repo.get("name", "")
            repo_str = f"{repo_org}/{repo_name}" if repo_org and repo_name else "-"

            tags = manifest.get("tags", [])
            tags_str = ", ".join(tags) if tags else "-"

            marker = " *" if name == active else "  "
            print(f"{marker}{name:<20} {lifecycle:<13} {repo_str:<30} {tags_str}")

        if active:
            print(f"\n  * = active platform ({active})")


def cmd_new(name: str) -> None:
    """Scaffold a new platform via copier copy, register in portal, inject LikeC4 loader."""
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        _error(
            f"Invalid platform name '{name}'. "
            "Must be kebab-case: lowercase letters, digits, hyphens. Start with a letter."
        )
        sys.exit(1)

    dst = PLATFORMS_DIR / name
    if dst.exists():
        _error(f"Platform '{name}' already exists at {dst}")
        sys.exit(1)

    if not TEMPLATE_DIR.exists():
        _error(f"Template directory not found: {TEMPLATE_DIR}")
        sys.exit(1)

    # 1. Scaffold via copier
    log.info("Scaffolding platform '%s'...", name)
    result = subprocess.run(
        ["copier", "copy", str(TEMPLATE_DIR), str(dst), "--trust"],
        check=False,
    )
    if result.returncode != 0:
        _error("copier copy failed")
        sys.exit(1)
    _ok(f"Platform scaffolded at {dst}")

    # 2. Inject LikeC4 loader import
    _inject_platform_loader(name)

    # 3. Portal symlinks are auto-managed by Vite plugin in astro.config.mjs
    _ok("Portal symlinks auto-managed by Vite plugin (no manual step needed)")

    # 4. Validate
    print(f"\n{'=' * 50}")
    print(f"Platform '{name}' created successfully!")
    print(f"{'=' * 50}")
    print("\nNext steps:")
    print("  cd portal && npm run dev              # see it in the portal")
    print(f"  /pipeline {name}                      # see pipeline status and next step")
    print(f"  python3 .specify/scripts/platform_cli.py lint {name}  # validate")


def cmd_lint(name: str | None, lint_all: bool = False) -> None:
    """Validate platform structure and consistency."""
    if lint_all:
        platforms = _discover_platforms()
        if not platforms:
            print("No platforms found.")
            return
        all_ok = True
        for p in platforms:
            print(f"\n=== {p} ===")
            if not _lint_platform(p):
                all_ok = False
        sys.exit(0 if all_ok else 1)
    elif name:
        print(f"=== {name} ===")
        ok = _lint_platform(name)
        sys.exit(0 if ok else 1)
    else:
        _error("Provide a platform name or --all")
        sys.exit(1)


def _lint_platform(name: str) -> bool:
    """Run all lint checks for a platform. Returns True if all pass."""
    pdir = PLATFORMS_DIR / name
    ok = True

    if not pdir.exists():
        _error(f"Platform directory not found: {pdir}")
        return False

    # Check platform.yaml
    manifest_path = pdir / "platform.yaml"
    if manifest_path.exists():
        manifest = yaml.safe_load(manifest_path.read_text())
        for field in ["name", "title", "lifecycle"]:
            if field not in manifest:
                _error(f"platform.yaml missing required field: {field}")
                ok = False
        if manifest.get("name") != name:
            _warn(f"platform.yaml name '{manifest.get('name')}' != directory name '{name}'")
        _ok("platform.yaml valid")
    else:
        _error("platform.yaml not found")
        ok = False

    # Check required directories
    for d in REQUIRED_DIRS:
        if (pdir / d).is_dir():
            _ok(f"{d}/ exists")
        else:
            _error(f"{d}/ missing")
            ok = False

    # Check required files
    for f in REQUIRED_FILES:
        if (pdir / f).exists():
            _ok(f"{f} exists")
        else:
            _warn(f"{f} missing")

    # Check AUTO markers
    for filepath, markers in AUTO_MARKERS.items():
        fpath = pdir / filepath
        if fpath.exists():
            content = fpath.read_text()
            for marker in markers:
                if f"<!-- AUTO:{marker} -->" in content and f"<!-- /AUTO:{marker} -->" in content:
                    _ok(f"AUTO:{marker} markers in {filepath}")
                else:
                    _warn(f"AUTO:{marker} markers missing in {filepath}")

    # Check spec.likec4 matches canonical
    spec_path = pdir / "model" / "spec.likec4"
    if spec_path.exists() and CANONICAL_SPEC.exists():
        if spec_path.read_bytes() == CANONICAL_SPEC.read_bytes():
            _ok("model/spec.likec4 matches canonical")
        else:
            _warn("model/spec.likec4 differs from canonical template")

    # Check likec4.config.json
    config_path = pdir / "model" / "likec4.config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        if config.get("name") == name:
            _ok("likec4.config.json name matches")
        else:
            _warn(f"likec4.config.json name '{config.get('name')}' != '{name}'")

    # Check ADR frontmatter
    adr_dir = pdir / "decisions"
    if adr_dir.is_dir():
        adrs = list(adr_dir.glob("ADR-*.md"))
        for adr in adrs:
            _check_frontmatter(adr, ADR_REQUIRED_FIELDS, "ADR")

    # Check epic frontmatter
    epic_dir = pdir / "epics"
    if epic_dir.is_dir():
        pitches = list(epic_dir.glob("*/pitch.md"))
        for pitch in pitches:
            _check_frontmatter(pitch, EPIC_REQUIRED_FIELDS, "Epic")

    return ok


def _check_frontmatter(filepath: Path, required_fields: list[str], label: str) -> None:
    """Check that a markdown file has required frontmatter fields."""
    content = filepath.read_text()
    if not content.startswith("---"):
        _warn(f"{label} {filepath.name}: no frontmatter")
        return

    end = content.find("---", 3)
    if end == -1:
        _warn(f"{label} {filepath.name}: malformed frontmatter")
        return

    fm = yaml.safe_load(content[3:end])
    if not fm:
        _warn(f"{label} {filepath.name}: empty frontmatter")
        return

    missing = [f for f in required_fields if f not in fm]
    if missing:
        _warn(f"{label} {filepath.name}: missing fields: {', '.join(missing)}")
    else:
        _ok(f"{label} {filepath.name} frontmatter valid")


def cmd_sync(name: str | None) -> None:
    """Run copier update on one or all platforms."""
    if name:
        platforms = [name]
    else:
        platforms = _discover_platforms()

    for p in platforms:
        pdir = PLATFORMS_DIR / p
        answers = pdir / ".copier-answers.yml"
        if not answers.exists():
            _warn(f"{p}: no .copier-answers.yml, skipping")
            continue

        log.info("Syncing %s...", p)
        result = subprocess.run(
            ["copier", "update", str(pdir), "--trust", "--defaults"],
            check=False,
        )
        if result.returncode == 0:
            _ok(f"{p} synced")
        else:
            _error(f"{p} sync failed (exit {result.returncode})")


def cmd_register(name: str) -> None:
    """Inject LikeC4 loader and validate model. Symlinks are auto-managed by Vite plugin."""
    pdir = PLATFORMS_DIR / name
    if not pdir.exists():
        _error(f"Platform '{name}' not found")
        sys.exit(1)

    # Inject LikeC4 loader import (idempotent — skips if already present)
    _inject_platform_loader(name)

    # Portal symlinks are auto-managed by Vite plugin in astro.config.mjs
    _ok("Portal symlinks auto-managed by Vite plugin")

    # Validate LikeC4 model
    model_dir = pdir / "model"
    if model_dir.exists():
        log.info("Validating LikeC4 model at %s...", model_dir)
        result = subprocess.run(
            ["npx", "likec4", "build", str(model_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            _ok("LikeC4 model validates")
        else:
            _warn(f"LikeC4 model has warnings: {result.stderr[:200]}")

    log.info("Platform '%s' registered. Run: cd portal && npm run dev", name)


# -- Main --


# ══════════════════════════════════════
# Decision/Memory Import/Export Commands
# ══════════════════════════════════════


def cmd_repair_timestamps(name: str) -> None:
    """Repair completed_at timestamps from events table."""
    from db import get_conn, migrate, repair_timestamps

    with get_conn() as conn:
        migrate(conn)
        repaired = repair_timestamps(conn, name)

    if repaired:
        log.info("%s: repaired %d node(s)", name, len(repaired))
        for r in repaired:
            log.info("%s: %s → %s", r["node_id"], r["old"], r["new"])
    else:
        log.info("%s: all timestamps OK", name)


def cmd_check_stale(name: str) -> None:
    """Check for stale pipeline nodes (dependencies completed after them)."""
    from db import get_conn, get_stale_nodes, migrate

    pdir = PLATFORMS_DIR / name
    yaml_path = pdir / "platform.yaml"
    if not yaml_path.exists():
        _error(f"platform.yaml not found: {yaml_path}")
        sys.exit(1)

    with open(yaml_path) as f:
        manifest = yaml.safe_load(f)

    # Build DAG edges from platform.yaml
    dag_edges: dict[str, list[str]] = {}
    for node in manifest.get("pipeline", {}).get("nodes", []):
        dag_edges[node["id"]] = node.get("depends", [])

    with get_conn() as conn:
        migrate(conn)
        stale = get_stale_nodes(conn, name, dag_edges)

    if stale:
        log.warning("%s: %d stale node(s)", name, len(stale))
        for s in stale:
            log.warning("stale: %s — %s", s["node_id"], s["stale_reason"])
        sys.exit(1)
    else:
        log.info("%s: no stale nodes", name)


def cmd_import_adrs(name: str) -> None:
    """Import all ADR-*.md from a platform's decisions/ dir into the DB."""
    from db import get_conn, migrate, import_all_adrs, upsert_platform

    decisions_dir = PLATFORMS_DIR / name / "decisions"
    if not decisions_dir.exists():
        _error(f"Decisions dir not found: {decisions_dir}")
        sys.exit(1)
    with get_conn() as conn:
        migrate(conn)
        upsert_platform(conn, name, name=name, repo_path=f"platforms/{name}")
        count = import_all_adrs(conn, name, decisions_dir)
    log.info("Imported %d ADRs for platform '%s'", count, name)


def cmd_export_adrs(name: str) -> None:
    """Export all decisions for a platform from DB to markdown."""
    from db import get_conn, migrate, sync_decisions_to_markdown

    decisions_dir = PLATFORMS_DIR / name / "decisions"
    with get_conn() as conn:
        migrate(conn)
        count = sync_decisions_to_markdown(conn, name, decisions_dir)
    log.info("Exported %d decisions to %s", count, decisions_dir)


def cmd_import_memory() -> None:
    """Import all .claude/memory/*.md files into the DB."""
    from db import get_conn, migrate, import_all_memories

    memory_dir = REPO_ROOT / ".claude" / "projects"
    # Find the memory dir for this repo
    candidates = list(memory_dir.rglob("memory"))
    if not candidates:
        _error("No .claude/projects/*/memory/ directory found")
        sys.exit(1)
    with get_conn() as conn:
        migrate(conn)
        total = 0
        for mem_dir in candidates:
            if mem_dir.is_dir():
                total += import_all_memories(conn, mem_dir)
    log.info("Imported %d memory entries", total)


def cmd_export_memory() -> None:
    """Export all memory entries from DB to markdown."""
    from db import get_conn, migrate, sync_memories_to_markdown

    memory_dir = REPO_ROOT / ".claude" / "projects"
    candidates = list(memory_dir.rglob("memory"))
    if not candidates:
        _error("No .claude/projects/*/memory/ directory found")
        sys.exit(1)
    with get_conn() as conn:
        migrate(conn)
        count = sync_memories_to_markdown(conn, candidates[0])
    log.info("Exported %d memory entries to %s", count, candidates[0])


def cmd_use(name: str) -> None:
    """Set the active platform."""
    from db import get_conn, migrate, set_local_config

    platforms = _discover_platforms()
    if name not in platforms:
        _error(f"Platform '{name}' not found. Available: {', '.join(platforms)}")
        sys.exit(1)
    with get_conn() as conn:
        migrate(conn)
        set_local_config(conn, "active_platform", name)
    _ok(f"Active platform set to: {name}")


def cmd_current() -> None:
    """Show the active platform."""
    from db import get_active_platform, get_conn, migrate

    with get_conn() as conn:
        migrate(conn)
        active = get_active_platform(conn)
    if active:
        print(f"Active platform: {active}")
    else:
        print("No active platform set. Use: platform_cli.py use <name>")


def cmd_status(name: str | None, show_all: bool, as_json: bool, output_file: str | None = None) -> None:
    """Show pipeline status for one or all platforms."""
    from datetime import datetime, timezone

    from db import (
        get_conn,
        get_decisions_summary,
        get_epic_nodes,
        get_epic_status,
        get_epics,
        get_pipeline_nodes,
        get_platform_status,
        get_stale_nodes,
        migrate,
    )

    with get_conn() as conn:
        migrate(conn)
        platforms = _discover_platforms()
        if not platforms:
            if as_json:
                print(json.dumps({"generated_at": "", "platforms": []}, indent=2))
            else:
                print("No platforms found.")
            return

        if name and name not in platforms:
            _error(f"Platform '{name}' not found. Available: {', '.join(platforms)}")
            sys.exit(1)

        targets = platforms if show_all else ([name] if name else platforms)

        result = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "platforms": [],
        }

        for pname in targets:
            pdir = PLATFORMS_DIR / pname
            manifest = yaml.safe_load((pdir / "platform.yaml").read_text())

            # Build DAG edges and node metadata from platform.yaml
            pipeline_cfg = manifest.get("pipeline", {})
            dag_edges = {n["id"]: n.get("depends", []) for n in pipeline_cfg.get("nodes", [])}

            # Query DB
            db_nodes = {n["node_id"]: n for n in get_pipeline_nodes(conn, pname)}
            status = get_platform_status(conn, pname)
            stale_ids = {s["node_id"] for s in get_stale_nodes(conn, pname, dag_edges)}

            # Merge DB + YAML into enriched nodes
            merged_nodes = []
            for node_cfg in pipeline_cfg.get("nodes", []):
                nid = node_cfg["id"]
                db_node = db_nodes.get(nid, {})
                node_status = db_node.get("status", "pending")
                if nid in stale_ids:
                    node_status = "stale"
                merged_nodes.append(
                    {
                        "id": nid,
                        "status": node_status,
                        "layer": node_cfg.get("layer", ""),
                        "gate": node_cfg.get("gate", ""),
                        "depends": node_cfg.get("depends", []),
                        "optional": node_cfg.get("optional", False),
                        "outputs": node_cfg.get("outputs", []),
                        "completed_at": db_node.get("completed_at"),
                    }
                )

            # L2 epics
            epics_data = []
            for epic in get_epics(conn, pname):
                epic_db_nodes = get_epic_nodes(conn, pname, epic["epic_id"])
                epic_status = get_epic_status(conn, pname, epic["epic_id"])
                enodes = []
                for en in epic_db_nodes:
                    enodes.append(
                        {
                            "id": en["node_id"],
                            "status": en["status"],
                            "completed_at": en.get("completed_at"),
                        }
                    )
                epics_data.append(
                    {
                        "id": epic["epic_id"],
                        "title": epic.get("title", ""),
                        "status": epic.get("status", "proposed"),
                        "total": epic_status.get("total_nodes", 0),
                        "done": epic_status.get("done", 0),
                        "skipped": epic_status.get("skipped", 0),
                        "pending": epic_status.get("pending", 0),
                        "progress_pct": epic_status.get("progress_pct", 0),
                        "nodes": enodes,
                    }
                )

            platform_data = {
                "id": pname,
                "title": manifest.get("title", pname),
                "lifecycle": manifest.get("lifecycle", "unknown"),
                "l1": {
                    "total": status.get("total_nodes", 0),
                    "done": status.get("done", 0),
                    "pending": status.get("pending", 0),
                    "stale": len(stale_ids),
                    "blocked": status.get("blocked", 0),
                    "skipped": status.get("skipped", 0),
                    "progress_pct": status.get("progress_pct", 0),
                    "nodes": merged_nodes,
                },
                "l2": {"epics": epics_data},
                "decisions": get_decisions_summary(conn, pname),
            }
            result["platforms"].append(platform_data)

        if as_json:
            json_str = json.dumps(result, ensure_ascii=False, indent=2)
            if output_file:
                out_path = Path(output_file)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json_str, encoding="utf-8")
            else:
                print(json_str)
        else:
            for p in result["platforms"]:
                print(f"\n{'=' * 60}")
                print(f"  {p['title']}  ({p['lifecycle']})")
                completed = p["l1"]["done"] + p["l1"].get("skipped", 0)
                print(f"  L1 Progress: {completed}/{p['l1']['total']} ({p['l1']['progress_pct']}%)")
                print(f"{'=' * 60}")
                print(f"  {'Node':<25} {'Status':<10} {'Layer':<15} {'Gate'}")
                print(f"  {'-' * 55}")
                for n in p["l1"]["nodes"]:
                    opt = " (opt)" if n["optional"] else ""
                    print(f"  {n['id']:<25} {n['status']:<10} {n['layer']:<15} {n['gate']}{opt}")
                if p["l2"]["epics"]:
                    print("\n  L2 Epics:")
                    for e in p["l2"]["epics"]:
                        epic_completed = e["done"] + e.get("skipped", 0)
                        print(f"    {e['id']}: {e['title']} — {epic_completed}/{e['total']} ({e['progress_pct']}%)")


def _build_parser():  # -> argparse.ArgumentParser
    import argparse

    parser = argparse.ArgumentParser(
        prog="platform_cli.py",
        description="Unified CLI for managing madruga.ai platforms.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_mode",
        help="Emit structured NDJSON log output (for CI consumption)",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # list
    sub.add_parser("list", help="List all discovered platforms")

    # new
    p = sub.add_parser("new", help="Scaffold a new platform via copier")
    p.add_argument("name", help="Platform name (kebab-case)")

    # lint
    p = sub.add_parser("lint", help="Validate platform structure")
    p.add_argument("name", nargs="?", help="Platform name")
    p.add_argument("--all", action="store_true", dest="lint_all", help="Lint all platforms")

    # sync
    p = sub.add_parser("sync", help="Run copier update on platforms")
    p.add_argument("name", nargs="?", help="Platform name (omit for all)")

    # register
    p = sub.add_parser("register", help="Inject LikeC4 loader and validate model")
    p.add_argument("name", help="Platform name")

    # check-stale
    p = sub.add_parser("check-stale", help="Detect stale pipeline nodes")
    p.add_argument("name", help="Platform name")

    # repair-timestamps
    p = sub.add_parser("repair-timestamps", help="Repair completed_at from events table")
    p.add_argument("name", help="Platform name")

    # import-adrs
    p = sub.add_parser("import-adrs", help="Import ADR markdown files into DB")
    p.add_argument("name", help="Platform name")

    # export-adrs
    p = sub.add_parser("export-adrs", help="Export decisions from DB to markdown")
    p.add_argument("name", help="Platform name")

    # import-memory
    sub.add_parser("import-memory", help="Import .claude/memory into DB")

    # export-memory
    sub.add_parser("export-memory", help="Export memory entries to markdown")

    # status
    p = sub.add_parser("status", help="Show pipeline status")
    p.add_argument("name", nargs="?", help="Platform name")
    p.add_argument("--all", action="store_true", dest="show_all", help="Show all platforms")
    p.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    p.add_argument("--output", dest="output_file", help="Write JSON to file instead of stdout")

    # use
    p = sub.add_parser("use", help="Set the active platform")
    p.add_argument("name", help="Platform name")

    # current
    sub.add_parser("current", help="Show the active platform")

    # ensure-repo
    p = sub.add_parser("ensure-repo", help="Clone or fetch a platform's code repo")
    p.add_argument("name", help="Platform name")

    # worktree
    p = sub.add_parser("worktree", help="Create a git worktree for an epic")
    p.add_argument("name", help="Platform name")
    p.add_argument("epic_slug", help="Epic slug (e.g., 001-channel-pipeline)")

    # worktree-cleanup
    p = sub.add_parser("worktree-cleanup", help="Remove a git worktree and its branch")
    p.add_argument("name", help="Platform name")
    p.add_argument("epic_slug", help="Epic slug")

    # Gate management (epic 013)
    gate_p = sub.add_parser("gate", help="Manage human gates (approve/reject/list)")
    gate_sub = gate_p.add_subparsers(dest="gate_action", help="Gate action")
    ga = gate_sub.add_parser("approve", help="Approve a pending gate")
    ga.add_argument("run_id", help="Run ID to approve")
    gr = gate_sub.add_parser("reject", help="Reject a pending gate")
    gr.add_argument("run_id", help="Run ID to reject")
    gl = gate_sub.add_parser("list", help="List pending gates")
    gl.add_argument("name", help="Platform name")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    _setup_logging(args.json_mode)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "list":
        cmd_list()
    elif args.command == "new":
        cmd_new(args.name)
        _discover_platforms.cache_clear()
    elif args.command == "lint":
        if not args.name and not args.lint_all:
            _error("Provide a platform name or --all")
            sys.exit(1)
        cmd_lint(args.name, lint_all=args.lint_all)
    elif args.command == "sync":
        cmd_sync(args.name)
        _discover_platforms.cache_clear()
    elif args.command == "register":
        cmd_register(args.name)
    elif args.command == "check-stale":
        cmd_check_stale(args.name)
    elif args.command == "repair-timestamps":
        cmd_repair_timestamps(args.name)
    elif args.command == "import-adrs":
        cmd_import_adrs(args.name)
    elif args.command == "export-adrs":
        cmd_export_adrs(args.name)
    elif args.command == "import-memory":
        cmd_import_memory()
    elif args.command == "export-memory":
        cmd_export_memory()
    elif args.command == "status":
        show_all = args.show_all
        if not args.name and not show_all:
            show_all = True
        cmd_status(args.name, show_all, args.as_json, output_file=args.output_file)
    elif args.command == "use":
        cmd_use(args.name)
    elif args.command == "current":
        cmd_current()
    elif args.command == "ensure-repo":
        cmd_ensure_repo(args.name)
    elif args.command == "worktree":
        cmd_worktree(args.name, args.epic_slug)
    elif args.command == "worktree-cleanup":
        cmd_worktree_cleanup(args.name, args.epic_slug)
    elif args.command == "gate":
        if not args.gate_action:
            print("Usage: platform_cli.py gate {approve|reject|list}")
            sys.exit(1)
        if args.gate_action == "approve":
            cmd_gate_approve(args.run_id)
        elif args.gate_action == "reject":
            cmd_gate_reject(args.run_id)
        elif args.gate_action == "list":
            cmd_gate_list(args.name)


def cmd_ensure_repo(name: str) -> None:
    """Clone or fetch a platform's code repository."""
    from ensure_repo import ensure_repo

    path = ensure_repo(name)
    _ok(f"Repo ready: {path}")
    print(path)


def cmd_worktree(name: str, epic_slug: str) -> None:
    """Create a git worktree for an epic."""
    from worktree import create_worktree

    path = create_worktree(name, epic_slug)
    _ok(f"Worktree ready: {path}")
    print(path)


def cmd_worktree_cleanup(name: str, epic_slug: str) -> None:
    """Remove a git worktree and its local branch."""
    from worktree import cleanup_worktree

    cleanup_worktree(name, epic_slug)
    _ok(f"Worktree cleaned up: {name}/{epic_slug}")


def cmd_gate_approve(run_id: str) -> None:
    """Approve a pending human gate."""
    from db import approve_gate, get_conn

    conn = get_conn()
    if approve_gate(conn, run_id):
        _ok(f"Gate approved: {run_id}")
    else:
        _error(f"No pending gate found for run_id: {run_id}")
        sys.exit(1)
    conn.close()


def cmd_gate_reject(run_id: str) -> None:
    """Reject a pending human gate."""
    from db import get_conn, reject_gate

    conn = get_conn()
    if reject_gate(conn, run_id):
        _ok(f"Gate rejected: {run_id}")
    else:
        _error(f"No pending gate found for run_id: {run_id}")
        sys.exit(1)
    conn.close()


def cmd_gate_list(name: str) -> None:
    """List pending gates for a platform."""
    from db import get_conn, get_pending_gates

    conn = get_conn()
    gates = get_pending_gates(conn, name)
    conn.close()
    if not gates:
        print("No pending gates.")
        return
    print(f"{'Run ID':<12s} {'Node':<25s} {'Epic':<30s} {'Waiting Since'}")
    print("-" * 80)
    for g in gates:
        epic = g.get("epic_id") or "-"
        since = g.get("started_at") or "-"
        print(f"{g['run_id']:<12s} {g['node_id']:<25s} {epic:<30s} {since}")


if __name__ == "__main__":
    main()
