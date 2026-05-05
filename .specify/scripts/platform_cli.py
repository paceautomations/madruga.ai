#!/usr/bin/env python3
"""
platform_cli.py — Unified CLI for managing madruga.ai platforms.

Renamed from platform.py to avoid shadowing Python stdlib 'platform' module.

Usage:
    python3 .specify/scripts/platform_cli.py new <name>        # scaffold via copier
    python3 .specify/scripts/platform_cli.py lint <name>        # validate structure
    python3 .specify/scripts/platform_cli.py lint --all         # validate all platforms
    python3 .specify/scripts/platform_cli.py sync [name]        # copier update (one or all)
    python3 .specify/scripts/platform_cli.py register <name>    # register platform in portal
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

import json
import logging
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import yaml

from config import PLATFORMS_DIR, PORTAL_DIR, REPO_ROOT, TEMPLATE_DIR  # noqa: F401
from log_utils import setup_logging as _setup_logging

log = logging.getLogger("platform_cli")


REQUIRED_DIRS = ["business", "engineering", "decisions", "epics"]
PORTAL_SECTIONS = ["business", "engineering", "decisions", "research", "planning"]
PORTAL_DOCS_DIR = PORTAL_DIR / "src" / "content" / "docs"
LIFECYCLES = ["design", "development", "production"]
TESTING_STARTUP_TYPES = ["none", "docker", "npm", "python"]

REQUIRED_FILES = [
    "platform.yaml",
    "business/vision.md",
    "business/solution-overview.md",
    "engineering/domain-model.md",
    "engineering/context-map.md",
    "engineering/blueprint.md",
]
AUTO_MARKERS = {
    "engineering/context-map.md": ["domains", "relations"],
}
ADR_REQUIRED_FIELDS = ["title", "status", "decision", "alternatives", "rationale"]
EPIC_REQUIRED_FIELDS = ["title", "status"]


def _ok(msg: str) -> None:
    log.info(msg)


def _warn(msg: str) -> None:
    log.warning(msg)


def _error(msg: str) -> None:
    log.error(msg)


def _create_portal_symlinks(name: str) -> None:
    """Create portal symlinks for a platform — mirrors astro.config.mjs:syncPlatformSymlinks()."""
    docs_dir = PORTAL_DOCS_DIR / name
    docs_dir.mkdir(parents=True, exist_ok=True)
    platform_dir = PLATFORMS_DIR / name
    targets = {section: platform_dir / section for section in PORTAL_SECTIONS}
    targets["platform.yaml"] = platform_dir / "platform.yaml"
    for link_name, target in targets.items():
        link = docs_dir / link_name
        if link.is_symlink() and not link.exists():
            link.unlink()
        if target.exists() and not link.exists():
            link.symlink_to(target)
    (docs_dir / "epics").mkdir(exist_ok=True)
    _ok(f"Portal symlinks created at {docs_dir}")


def _seed_platform_db(name: str) -> None:
    """Seed SQLite DB for a platform via post_save.reseed (in-process)."""
    from post_save import reseed

    result = reseed(name)
    if result.get("status") == "error":
        _warn(f"DB seed failed for '{name}': {result.get('reason')} (non-blocking)")
    else:
        _ok(f"DB seeded for '{name}'")


def _refresh_status_json() -> None:
    """Regenerate portal/src/data/pipeline-status.json with all platforms."""
    # Drop the lru_cache so a freshly-scaffolded platform appears in the JSON.
    _discover_platforms.cache_clear()
    output_file = str(PORTAL_DIR / "src" / "data" / "pipeline-status.json")
    cmd_status(name=None, show_all=True, as_json=True, output_file=output_file)
    _ok("pipeline-status.json refreshed")


def _notify_dev_server(_verify_attempts: int = 15, _verify_interval: float = 1.0) -> None:
    """If Astro dev server is running on :4321, touch astro.config.mjs to trigger soft restart
    and verify it recovers. Astro's content layer doesn't auto-detect newly-symlinked dirs;
    a config touch forces a full restart that re-indexes content collections.

    Verifies the server returns 200 within ~15 attempts. If recovery fails, prints an actionable
    message instead of leaving the user with a silently-broken dev server.

    Test hooks: `_verify_attempts` and `_verify_interval` keep the verify loop bounded.
    """
    import socket
    import time
    import urllib.error
    import urllib.request

    def _port_open() -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        try:
            return sock.connect_ex(("127.0.0.1", 4321)) == 0
        finally:
            sock.close()

    if not _port_open():
        return

    config = PORTAL_DIR / "astro.config.mjs"
    if not config.exists():
        return

    config.touch()
    for _ in range(_verify_attempts):
        time.sleep(_verify_interval)
        try:
            with urllib.request.urlopen("http://127.0.0.1:4321/", timeout=2) as resp:
                if resp.status == 200:
                    _ok("Dev server on :4321 — soft restart succeeded (refresh browser)")
                    return
        except (urllib.error.URLError, OSError):
            continue

    _warn(
        "Dev server on :4321 was touched but did not recover within ~15s. "
        "Restart manually: Ctrl+C in the dev terminal, then `cd portal && npm run dev`."
    )


@lru_cache(maxsize=None)
def _discover_platforms() -> list[str]:
    """Return sorted list of platform names that have platform.yaml."""
    return sorted(d.name for d in PLATFORMS_DIR.iterdir() if d.is_dir() and (d / "platform.yaml").exists())


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


def cmd_new(
    name: str,
    title: str | None = None,
    description: str | None = None,
    lifecycle: str | None = None,
    repo_org: str | None = None,
    repo_name: str | None = None,
    repo_branch: str | None = None,
    tags: str | None = None,
    testing_startup: str | None = None,
) -> None:
    """Scaffold a new platform via copier copy, create portal symlinks, and seed DB."""
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

    log.info("Scaffolding platform '%s'...", name)
    copier_cmd = ["copier", "copy", str(TEMPLATE_DIR), str(dst), "--trust"]
    cli_fields = {
        "platform_title": title,
        "platform_description": description,
        "lifecycle": lifecycle,
        "repo_org": repo_org,
        "repo_name": repo_name,
        "repo_base_branch": repo_branch,
        "tags": tags,
        "testing_startup_type": testing_startup,
    }
    if any(v is not None for v in cli_fields.values()):
        copier_cmd += ["--defaults", "-d", f"platform_name={name}", "-d", "register_portal=false"]
        for key, value in cli_fields.items():
            if value is not None:
                copier_cmd += ["-d", f"{key}={value}"]
    result = subprocess.run(copier_cmd, check=False)
    if result.returncode != 0:
        _error("copier copy failed")
        sys.exit(1)
    _ok(f"Platform scaffolded at {dst}")

    # Vite plugin only runs at dev-server startup; create symlinks eagerly so
    # already-running portals see the new platform immediately.
    _create_portal_symlinks(name)
    _seed_platform_db(name)
    _refresh_status_json()
    _notify_dev_server()

    print(f"\n{'=' * 50}")
    print(f"Platform '{name}' created successfully!")
    print(f"{'=' * 50}")
    print("\nNext steps:")
    print(f"  /vision {name}                        # start documentation pipeline")
    print(f"  /pipeline {name}                      # see pipeline DAG status")


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

        # Validate testing: block if present
        if "testing" in manifest:
            testing_errors = _lint_testing_block(manifest["testing"], name)
            if testing_errors:
                for err in testing_errors:
                    _error(err)
                ok = False
            else:
                _ok("testing: block valid")

        # Validate screen_flow: block if present (epic 027 — FR-005..010, FR-047)
        if "screen_flow" in manifest:
            sf_errors = _lint_screen_flow_block(manifest["screen_flow"], name)
            if sf_errors:
                for err in sf_errors:
                    _error(err)
                ok = False
            else:
                _ok("screen_flow: block valid")
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


_VALID_STARTUP_TYPES = {"docker", "npm", "make", "venv", "script", "none"}
_STARTUP_COMMAND_REQUIRED = {"venv", "script"}
_VALID_URL_TYPES = {"api", "frontend"}


def _lint_testing_block(testing_data: dict, platform_name: str) -> list[str]:
    """Validate the optional testing: block in platform.yaml.

    Returns a list of error strings. Empty list means no errors.
    """
    errors: list[str] = []

    if not isinstance(testing_data, dict):
        errors.append(f"{platform_name}: testing: must be a mapping, got {type(testing_data).__name__}")
        return errors

    # --- startup ---
    startup = testing_data.get("startup")
    if not isinstance(startup, dict):
        errors.append(f"{platform_name}: testing.startup must be a mapping")
    else:
        startup_type = startup.get("type")
        if not startup_type:
            errors.append(f"{platform_name}: testing.startup.type is required")
        elif startup_type not in _VALID_STARTUP_TYPES:
            errors.append(
                f"{platform_name}: testing.startup.type '{startup_type}' is invalid "
                f"(valid: {', '.join(sorted(_VALID_STARTUP_TYPES))})"
            )
        elif startup_type in _STARTUP_COMMAND_REQUIRED:
            if not startup.get("command"):
                errors.append(
                    f"{platform_name}: testing.startup.command is required when startup.type is '{startup_type}'"
                )

    # --- health_checks ---
    health_checks = testing_data.get("health_checks", [])
    if not isinstance(health_checks, list):
        errors.append(f"{platform_name}: testing.health_checks must be a list")
    else:
        for i, hc in enumerate(health_checks):
            if not isinstance(hc, dict):
                errors.append(f"{platform_name}: testing.health_checks[{i}] must be a mapping")
                continue
            if not hc.get("url"):
                errors.append(f"{platform_name}: testing.health_checks[{i}] missing required field 'url'")
            if not hc.get("label"):
                errors.append(f"{platform_name}: testing.health_checks[{i}] missing required field 'label'")

    # --- urls ---
    urls = testing_data.get("urls", [])
    if not isinstance(urls, list):
        errors.append(f"{platform_name}: testing.urls must be a list")
    else:
        for i, u in enumerate(urls):
            if not isinstance(u, dict):
                errors.append(f"{platform_name}: testing.urls[{i}] must be a mapping")
                continue
            if not u.get("url"):
                errors.append(f"{platform_name}: testing.urls[{i}] missing required field 'url'")
            url_type = u.get("type")
            if not url_type:
                errors.append(f"{platform_name}: testing.urls[{i}] missing required field 'type'")
            elif url_type not in _VALID_URL_TYPES:
                errors.append(
                    f"{platform_name}: testing.urls[{i}] type '{url_type}' is invalid "
                    f"(valid: {', '.join(sorted(_VALID_URL_TYPES))})"
                )
            if not u.get("label"):
                errors.append(f"{platform_name}: testing.urls[{i}] missing required field 'label'")

    # --- required_env ---
    required_env = testing_data.get("required_env", [])
    if not isinstance(required_env, list):
        errors.append(f"{platform_name}: testing.required_env must be a list")
    else:
        for i, var in enumerate(required_env):
            if not isinstance(var, str):
                errors.append(f"{platform_name}: testing.required_env[{i}] must be a string, got {type(var).__name__}")

    return errors


def _lint_screen_flow_block(block: object, platform_name: str) -> list[str]:
    """Validate the optional `screen_flow:` block in platform.yaml.

    Delegates to `screen_flow_validator.validate_platform_screen_flow_block` (epic 027:
    FR-005..010, FR-047). Returns a list of error strings shaped like the testing-block
    output for consistent CLI rendering. Each string carries the offending JSON pointer
    so authors can locate the field.
    """
    errors: list[str] = []
    try:
        import screen_flow_validator as sfv  # local import — script lives next to us
    except ImportError as exc:  # pragma: no cover — repo invariant
        errors.append(
            f"{platform_name}: screen_flow validator unavailable ({exc}); install jsonschema and pyyaml"
        )
        return errors

    findings = sfv.validate_platform_screen_flow_block(block)
    for f in findings:
        if f.get("severity") != "BLOCKER":
            continue
        path = f.get("path") or "screen_flow"
        message = f.get("message") or "invalid screen_flow block"
        errors.append(f"{platform_name}: screen_flow.{path}: {message}")
    return errors


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
    """Register platform: create portal symlinks, seed DB, refresh status JSON."""
    pdir = PLATFORMS_DIR / name
    if not pdir.exists():
        _error(f"Platform '{name}' not found")
        sys.exit(1)

    _create_portal_symlinks(name)
    _seed_platform_db(name)
    _refresh_status_json()
    _notify_dev_server()
    log.info("Platform '%s' registered.", name)


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

    from config import load_pipeline

    pdir = PLATFORMS_DIR / name
    if not (pdir / "platform.yaml").exists():
        _error(f"platform.yaml not found: {pdir / 'platform.yaml'}")
        sys.exit(1)

    dag_edges: dict[str, list[str]] = {}
    for node in load_pipeline().get("nodes", []):
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

        from config import load_pipeline

        pipeline_cfg = load_pipeline()
        for pname in targets:
            pdir = PLATFORMS_DIR / pname
            manifest = yaml.safe_load((pdir / "platform.yaml").read_text())

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
                        "updated_at": epic.get("updated_at", ""),
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
    p.add_argument("--title", default=None, help="Platform title (any flag triggers non-interactive mode)")
    p.add_argument("--description", default=None, help="Platform description")
    p.add_argument("--lifecycle", default=None, choices=LIFECYCLES)
    p.add_argument("--repo-org", default=None, help="GitHub org")
    p.add_argument("--repo-name", default=None, help="GitHub repo name")
    p.add_argument("--repo-branch", default=None, help="Base branch (main/develop)")
    p.add_argument("--tags", default=None, help="Tags as CSV (e.g., 'whatsapp,multi-tenant'). Empty = no tags.")
    p.add_argument(
        "--testing-startup",
        default=None,
        choices=TESTING_STARTUP_TYPES,
        help="App startup type for E2E tests (renders testing block in platform.yaml).",
    )

    # lint
    p = sub.add_parser("lint", help="Validate platform structure")
    p.add_argument("name", nargs="?", help="Platform name")
    p.add_argument("--all", action="store_true", dest="lint_all", help="Lint all platforms")

    # sync
    p = sub.add_parser("sync", help="Run copier update on platforms")
    p.add_argument("name", nargs="?", help="Platform name (omit for all)")

    # register
    p = sub.add_parser("register", help="Register platform in portal")
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
        cmd_new(
            args.name,
            title=args.title,
            description=args.description,
            lifecycle=args.lifecycle,
            repo_org=args.repo_org,
            repo_name=args.repo_name,
            repo_branch=args.repo_branch,
            tags=args.tags,
            testing_startup=args.testing_startup,
        )
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


def cmd_gate_approve(run_id: str) -> None:
    """Approve a pending human gate."""
    from db import approve_gate, get_conn

    with get_conn() as conn:
        if approve_gate(conn, run_id):
            _ok(f"Gate approved: {run_id}")
        else:
            _error(f"No pending gate found for run_id: {run_id}")
            sys.exit(1)


def cmd_gate_reject(run_id: str) -> None:
    """Reject a pending human gate."""
    from db import get_conn, reject_gate

    with get_conn() as conn:
        if reject_gate(conn, run_id):
            _ok(f"Gate rejected: {run_id}")
        else:
            _error(f"No pending gate found for run_id: {run_id}")
            sys.exit(1)


def cmd_gate_list(name: str) -> None:
    """List pending gates for a platform."""
    from db import get_conn, get_pending_gates

    with get_conn() as conn:
        gates = get_pending_gates(conn, name)
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
