#!/usr/bin/env python3
"""
platform.py — Unified CLI for managing madruga.ai platforms.

Usage:
    python3 .specify/scripts/platform.py new <name>        # scaffold via copier
    python3 .specify/scripts/platform.py lint <name>        # validate structure
    python3 .specify/scripts/platform.py lint --all         # validate all platforms
    python3 .specify/scripts/platform.py sync [name]        # copier update (one or all)
    python3 .specify/scripts/platform.py register <name>    # re-run setup.sh + validate model
    python3 .specify/scripts/platform.py list               # list all platforms
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLATFORMS_DIR = REPO_ROOT / "platforms"
TEMPLATE_DIR = REPO_ROOT / ".specify" / "templates" / "platform"
PORTAL_DIR = REPO_ROOT / "portal"
CANONICAL_SPEC = TEMPLATE_DIR / "template" / "model" / "spec.likec4"
LIKEC4_DIAGRAM_TSX = PORTAL_DIR / "src" / "components" / "viewers" / "LikeC4Diagram.tsx"

REQUIRED_DIRS = ["business", "engineering", "decisions", "epics", "model"]
REQUIRED_FILES = [
    "platform.yaml",
    "business/vision.md",
    "business/solution-overview.md",
    "engineering/domain-model.md",
    "engineering/containers.md",
    "engineering/context-map.md",
    "engineering/integrations.md",
    "engineering/blueprint.md",
    "model/spec.likec4",
    "model/likec4.config.json",
]
AUTO_MARKERS = {
    "engineering/containers.md": ["containers"],
    "engineering/context-map.md": ["domains", "relations"],
    "engineering/integrations.md": ["integrations"],
}
ADR_REQUIRED_FIELDS = ["title", "status"]
EPIC_REQUIRED_FIELDS = ["title", "status"]


def _ok(msg: str) -> None:
    print(f"  [ok] {msg}")


def _warn(msg: str) -> None:
    print(f"  [warn] {msg}")


def _error(msg: str) -> None:
    print(f"  [error] {msg}")


def _discover_platforms() -> list[str]:
    """Return sorted list of platform names that have platform.yaml."""
    return sorted(
        d.name
        for d in PLATFORMS_DIR.iterdir()
        if d.is_dir() and (d / "platform.yaml").exists()
    )


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
    updated = (
        content[: match.start()]
        + before
        + "\n"
        + new_entry
        + "\n"
        + match.group(2)
        + content[match.end() :]
    )
    LIKEC4_DIAGRAM_TSX.write_text(updated)
    _ok(f"Injected '{name}' into LikeC4Diagram.tsx platformLoaders")
    return True


# -- Commands --


def cmd_list() -> None:
    """List all discovered platforms."""
    platforms = _discover_platforms()
    if not platforms:
        print("No platforms found.")
        return

    print(f"{'Name':<25} {'Lifecycle':<15} {'Version':<10} {'Copier'}")
    print("-" * 65)
    for name in platforms:
        pdir = PLATFORMS_DIR / name
        manifest = yaml.safe_load((pdir / "platform.yaml").read_text())
        lifecycle = manifest.get("lifecycle", "?")
        version = manifest.get("version", "?")
        has_copier = "yes" if (pdir / ".copier-answers.yml").exists() else "no"
        print(f"  {name:<23} {lifecycle:<15} {version:<10} {has_copier}")


def cmd_new(name: str) -> None:
    """Scaffold a new platform via copier copy, register in portal, inject LikeC4 loader."""
    import re

    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        _error(
            f"Invalid platform name '{name}'. Must be kebab-case: lowercase letters, digits, hyphens. Start with a letter."
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
    print(f"Scaffolding platform '{name}'...")
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

    # 3. Register in portal (symlinks)
    setup_sh = PORTAL_DIR / "setup.sh"
    if setup_sh.exists():
        subprocess.run(["bash", str(setup_sh)], check=True, capture_output=True)
        _ok("Portal symlinks updated")

    # 4. Validate
    print(f"\n{'=' * 50}")
    print(f"Platform '{name}' created successfully!")
    print(f"{'=' * 50}")
    print("\nNext steps:")
    print("  cd portal && npm run dev              # see it in the portal")
    print(
        f"  /pipeline {name}                      # see pipeline status and next step"
    )
    print(f"  python3 .specify/scripts/platform.py lint {name}  # validate")


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
            _warn(
                f"platform.yaml name '{manifest.get('name')}' != directory name '{name}'"
            )
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
                if (
                    f"<!-- AUTO:{marker} -->" in content
                    and f"<!-- /AUTO:{marker} -->" in content
                ):
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

        print(f"Syncing {p}...")
        result = subprocess.run(
            ["copier", "update", str(pdir), "--trust", "--defaults"],
            check=False,
        )
        if result.returncode == 0:
            _ok(f"{p} synced")
        else:
            _error(f"{p} sync failed (exit {result.returncode})")


def cmd_register(name: str) -> None:
    """Inject LikeC4 loader, re-run portal setup.sh, and validate model."""
    pdir = PLATFORMS_DIR / name
    if not pdir.exists():
        _error(f"Platform '{name}' not found")
        sys.exit(1)

    # Inject LikeC4 loader import (idempotent — skips if already present)
    _inject_platform_loader(name)

    # Re-run setup.sh
    setup_sh = PORTAL_DIR / "setup.sh"
    if setup_sh.exists():
        print("Running portal/setup.sh...")
        subprocess.run(["bash", str(setup_sh)], check=True)
        _ok("Portal symlinks updated")

    # Validate LikeC4 model
    model_dir = pdir / "model"
    if model_dir.exists():
        print(f"Validating LikeC4 model at {model_dir}...")
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

    print(f"\nPlatform '{name}' registered. Run: cd portal && npm run dev")


# -- Main --


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        cmd_list()
    elif cmd == "new":
        if len(sys.argv) < 3:
            _error("Usage: platform.py new <name>")
            sys.exit(1)
        cmd_new(sys.argv[2])
    elif cmd == "lint":
        if "--all" in sys.argv:
            cmd_lint(None, lint_all=True)
        elif len(sys.argv) >= 3:
            cmd_lint(sys.argv[2])
        else:
            _error("Usage: platform.py lint <name> | --all")
            sys.exit(1)
    elif cmd == "sync":
        cmd_sync(sys.argv[2] if len(sys.argv) >= 3 else None)
    elif cmd == "register":
        if len(sys.argv) < 3:
            _error("Usage: platform.py register <name>")
            sys.exit(1)
        cmd_register(sys.argv[2])
    else:
        _error(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
