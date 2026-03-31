#!/usr/bin/env python3
"""
vision-build.py — Generates markdown tables and static exports from LikeC4 model.

Usage:
    python .specify/scripts/vision-build.py fulano                  # build all
    python .specify/scripts/vision-build.py fulano --validate-only  # validate only
    python .specify/scripts/vision-build.py fulano --export-png     # also export PNGs
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import PLATFORMS_DIR, REPO_ROOT  # noqa: F401

CONTAINER_KINDS = {"api", "worker", "frontend", "cache", "database", "proxy"}
BC_KIND = "boundedContext"
MODULE_KIND = "module"
MAX_INTEGRATION_ROWS = 30


def _esc(text: str) -> str:
    """Escape pipe characters for markdown tables."""
    return text.replace("|", "\\|")


def _desc_text(el: dict) -> str:
    """Extract plain-text description from a LikeC4 element."""
    d = el.get("description")
    if d is None:
        return ""
    return d.get("txt", "") if isinstance(d, dict) else str(d)


def _bc_ids(data: dict) -> list[str]:
    """Collect all bounded context element IDs."""
    return [eid for eid, el in data.get("elements", {}).items() if el.get("kind") == BC_KIND]


def validate_model(model_dir: Path) -> None:
    """Validate the LikeC4 model by running likec4 build."""
    subprocess.run(["likec4", "build", str(model_dir)], check=True, timeout=60)
    print(f"[ok] Model validated: {model_dir}")


def export_json(model_dir: Path) -> dict:
    """Export LikeC4 model to JSON and return parsed data."""
    out_file = model_dir / "output" / "likec4.json"
    out_file.parent.mkdir(exist_ok=True)
    subprocess.run(
        [
            "likec4",
            "export",
            "json",
            "--pretty",
            "--skip-layout",
            "-o",
            str(out_file),
            str(model_dir),
        ],
        check=True,
        timeout=60,
    )
    data = json.loads(out_file.read_text())
    print(f"[ok] JSON exported to: {out_file}")
    return data


def export_png(model_dir: Path) -> None:
    """Export all views as PNG images."""
    output_dir = model_dir / "output"
    output_dir.mkdir(exist_ok=True)
    subprocess.run(
        ["likec4", "export", "png", "-o", str(output_dir)],
        check=True,
        timeout=120,
        cwd=str(model_dir),
    )
    print(f"[ok] PNGs exported to: {output_dir}")


def _containers_table(data: dict) -> str:
    """Build markdown table of platform containers."""
    rows = []
    bc_prefixes = tuple(f"{bc_id}." for bc_id in _bc_ids(data))

    for eid, el in sorted(data.get("elements", {}).items()):
        if el.get("kind") not in CONTAINER_KINDS:
            continue
        if eid.startswith(bc_prefixes):
            continue

        title = _esc(el.get("title", eid.split(".")[-1]))
        tech = _esc(el.get("technology", "-"))
        port = _esc(el.get("metadata", {}).get("port", "-"))
        desc = _esc(_desc_text(el))
        rows.append(f"| **{title}** | {tech} | {port} | {desc} |")

    header = "| Container | Tech | Port | Responsibility |\n|-----------|------|------|----------------|\n"
    return header + "\n".join(rows)


def _domains_table(data: dict) -> str:
    """Build markdown table of bounded contexts (domains)."""
    elements = data.get("elements", {})
    rows = []
    for i, bc_id in enumerate(_bc_ids(data), 1):
        bc = elements.get(bc_id, {})
        title = _esc(bc.get("title", bc_id))
        desc = _esc(_desc_text(bc))

        modules = [
            _esc(el.get("title", eid.split(".")[-1]).split(" ")[0])
            for eid, el in elements.items()
            if eid.startswith(bc_id + ".") and el.get("kind") == MODULE_KIND
        ]

        tags = bc.get("tags", [])
        pattern = (
            "Core"
            if "core" in tags
            else "Supporting"
            if "supporting" in tags
            else "Generic"
            if "generic" in tags
            else "-"
        )

        # Avoid duplication if title already contains the pattern (e.g. "Conversation (Core)")
        if pattern != "-" and pattern.lower() in title.lower():
            label = title
        else:
            label = f"{title} ({pattern})"

        rows.append(f"| {i} | **{label}** | {', '.join(modules)} | {desc} |")

    header = "| # | Domain | Modules | Responsibility |\n|---|--------|---------|----------------|\n"
    return header + "\n".join(rows)


def _integrations_table(data: dict) -> str:
    """Build markdown table of external integrations."""
    elements = data.get("elements", {})
    rows = []
    count = 0

    for rel in data.get("relations", {}).values():
        tech = rel.get("technology")
        if not tech:
            continue

        count += 1
        source_id = rel.get("source", {}).get("model", "?")
        target_id = rel.get("target", {}).get("model", "?")

        source_name = _esc(elements.get(source_id, {}).get("title", source_id.split(".")[-1]))
        target_name = _esc(elements.get(target_id, {}).get("title", target_id.split(".")[-1]))

        title = _esc(rel.get("title", "-"))
        meta = rel.get("metadata", {})
        freq = _esc(meta.get("frequency", "-"))
        payload_desc = _esc(meta.get("data", "-"))
        fallback = _esc(meta.get("fallback", "-"))

        direction = f"{source_name} -> {target_name}"
        rows.append(f"| {count} | **{title}** | {_esc(tech)} | {direction} | {freq} | {payload_desc} | {fallback} |")

        if count >= MAX_INTEGRATION_ROWS:
            break

    header = (
        "| # | System | Protocol | Direction | Frequency | Data | Fallback |\n"
        "|---|--------|----------|-----------|-----------|------|----------|\n"
    )
    return header + "\n".join(rows)


DDD_REL_KINDS = {"acl", "conformist", "customerSupplier", "pubSub"}


def _rel_kind_label(kind: str) -> str:
    """Map LikeC4 relationship kind to human-readable DDD label."""
    return {
        "acl": "ACL",
        "conformist": "Conformist",
        "customerSupplier": "Customer-Supplier",
        "pubSub": "Publish-Subscribe",
    }.get(kind, kind)


def _ddd_relations_table(data: dict) -> str:
    """Build markdown table of DDD inter-domain relationships."""
    elements = data.get("elements", {})
    rows = []
    bc_ids = set(_bc_ids(data))

    def _bc_name(eid: str) -> str:
        """Get the bounded context name for an element (module -> parent BC)."""
        el = elements.get(eid, {})
        if el.get("kind") == BC_KIND or eid in bc_ids:
            return _esc(el.get("title", eid.split(".")[-1]))
        # module — find parent BC
        for bc_id in bc_ids:
            if eid.startswith(bc_id + "."):
                return _esc(elements.get(bc_id, {}).get("title", bc_id.split(".")[-1]))
        return _esc(el.get("title", eid.split(".")[-1]))

    for rel in data.get("relations", {}).values():
        kind = rel.get("kind", "")
        if kind not in DDD_REL_KINDS:
            continue

        source_id = rel.get("source", {}).get("model", "?")
        target_id = rel.get("target", {}).get("model", "?")

        source_name = _bc_name(source_id)
        target_name = _bc_name(target_id)
        desc = _esc(_desc_text(rel))
        label = _rel_kind_label(kind)

        rows.append(f"| {source_name} | {target_name} | {label} | {desc} |")

    header = "| Upstream | Downstream | Type | Description |\n|----------|-----------|------|-------------|\n"
    return header + "\n".join(rows)


def update_markdown(md_path: Path, marker: str, content: str) -> bool:
    """Replace content between <!-- AUTO:marker --> and <!-- /AUTO:marker -->."""
    if not md_path.exists():
        return False

    text = md_path.read_text()
    start_tag = f"<!-- AUTO:{marker} -->"
    end_tag = f"<!-- /AUTO:{marker} -->"

    start_idx = text.find(start_tag)
    end_idx = text.find(end_tag)

    if start_idx == -1 or end_idx == -1:
        print(f"[warn] Markers not found in {md_path.name} ({marker})")
        return False

    new_text = text[: start_idx + len(start_tag)] + "\n" + content + "\n" + text[end_idx:]
    md_path.write_text(new_text)
    print(f"[ok] Updated {md_path.name} ({marker})")
    return True


def build(platform: str, validate_only: bool = False, do_export_png: bool = False) -> None:
    """Main build pipeline: validate, export JSON, populate markdown tables."""
    import shutil

    if not shutil.which("likec4"):
        sys.exit("Error: likec4 CLI not found. Install with: npm i -g likec4")

    model_dir = PLATFORMS_DIR / platform / "model"
    if not model_dir.exists():
        print(f"[error] Model directory not found: {model_dir}")
        sys.exit(1)

    if validate_only:
        validate_model(model_dir)
        return

    # export_json already validates the model (check=True fails on invalid input)
    data = export_json(model_dir)
    n_elem = len(data.get("elements", {}))
    n_rel = len(data.get("relations", {}))
    n_view = len(data.get("views", {}))
    print(f"[ok] {n_elem} elements, {n_rel} relations, {n_view} views")

    eng_dir = PLATFORMS_DIR / platform / "engineering"

    update_markdown(eng_dir / "containers.md", "containers", _containers_table(data))
    update_markdown(eng_dir / "context-map.md", "domains", _domains_table(data))
    update_markdown(eng_dir / "context-map.md", "relations", _ddd_relations_table(data))
    update_markdown(eng_dir / "integrations.md", "integrations", _integrations_table(data))

    if do_export_png:
        export_png(model_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python .specify/scripts/vision-build.py <platform> [--validate-only] [--export-png]")
        sys.exit(1)

    platform_name = sys.argv[1]
    only_validate = "--validate-only" in sys.argv
    png = "--export-png" in sys.argv

    build(platform_name, validate_only=only_validate, do_export_png=png)
