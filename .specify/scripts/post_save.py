#!/usr/bin/env python3
"""
post_save.py — CLI wrapper for recording pipeline state after a skill saves an artifact.

Called by skills at Step 5 of the pipeline contract. Wraps db.py functions
into a single command that the AI can call after saving any artifact.

Usage:
    # L1 (platform DAG):
    python3 .specify/scripts/post_save.py \
        --platform fulano --node vision --skill madruga:vision \
        --artifact business/vision.md

    # L2 (epic cycle):
    python3 .specify/scripts/post_save.py \
        --platform fulano --epic 001-channel-pipeline \
        --node specify --skill speckit.specify \
        --artifact epics/001-channel-pipeline/spec.md

    # Re-seed from filesystem:
    python3 .specify/scripts/post_save.py --reseed --platform fulano

    # Re-seed all platforms:
    python3 .specify/scripts/post_save.py --reseed-all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path for db/config import
sys.path.insert(0, str(Path(__file__).parent))


import yaml

from config import REPO_ROOT  # noqa: F401
from db import (  # noqa: F401 — compute_epic_status used in record_save
    compute_epic_status,
    compute_file_hash,
    get_conn,
    get_epic_nodes,
    get_epics,
    get_pipeline_nodes,
    get_platform,
    insert_event,
    insert_provenance,
    migrate,
    seed_epic_nodes_from_disk,
    seed_from_filesystem,
    transaction,
    upsert_epic,
    upsert_epic_node,
    upsert_platform,
    upsert_pipeline_node,
)


def _refresh_portal_status() -> None:
    """Regenerate portal/src/data/pipeline-status.json (best-effort)."""
    portal_json = REPO_ROOT / "portal" / "src" / "data" / "pipeline-status.json"
    if not portal_json.parent.exists():
        return
    try:
        import subprocess

        subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / ".specify" / "scripts" / "platform.py"),
                "status",
                "--all",
                "--json",
                "--output",
                str(portal_json),
            ],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass  # best-effort — never block the save


def _validate_artifact_path(platform: str, artifact: str) -> Path:
    """Validate artifact path is within the platform directory (prevent path traversal)."""
    platform_dir = (REPO_ROOT / "platforms" / platform).resolve()
    artifact_path = (platform_dir / artifact).resolve()
    if not str(artifact_path).startswith(str(platform_dir) + "/"):
        raise ValueError(f"Path traversal detected: '{artifact}' resolves outside platform dir")
    return artifact_path


def _inject_ship_fields(platform: str, epic: str, delivered_at: str) -> None:
    """Update pitch.md frontmatter with status: shipped and delivered_at."""
    pitch = REPO_ROOT / "platforms" / platform / "epics" / epic / "pitch.md"
    if not pitch.exists():
        return
    content = pitch.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return
    # Find closing --- of frontmatter
    end = content.find("---", 3)
    if end == -1:
        return
    fm_block = content[3:end]
    body = content[end:]

    # Update status within frontmatter block
    if re.search(r"^status:", fm_block, re.MULTILINE):
        fm_block = re.sub(r"^status:.*$", "status: shipped", fm_block, flags=re.MULTILINE)
    else:
        fm_block += "status: shipped\n"

    # Add delivered_at if not present
    if not re.search(r"^delivered_at:", fm_block, re.MULTILINE):
        fm_block += f"delivered_at: {delivered_at}\n"

    updated = "---" + fm_block + body
    pitch.write_text(updated, encoding="utf-8")


def _get_required_epic_nodes(platform: str, pipeline_data: dict | None = None) -> set[str]:
    """Read required (non-optional) epic cycle node IDs from platform.yaml."""
    if pipeline_data is None:
        yaml_path = REPO_ROOT / "platforms" / platform / "platform.yaml"
        if not yaml_path.exists():
            return set()
        pipeline_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")).get("pipeline", {})
    cycle_nodes = pipeline_data.get("epic_cycle", {}).get("nodes", [])
    return {n["id"] for n in cycle_nodes if not n.get("optional", False)}


def _backfill_epic_predecessors(txn, platform: str, epic: str, pipeline_data: dict) -> set[str]:
    """Backfill missing epic_nodes whose output files exist on disk.

    Returns set of all completed node IDs (existing + newly backfilled).
    """

    epic_cycle = pipeline_data.get("epic_cycle", {}).get("nodes", [])
    pdir = REPO_ROOT / "platforms" / platform
    return seed_epic_nodes_from_disk(txn, platform, epic, pdir, epic_cycle)


def record_save(
    platform: str,
    node: str,
    skill: str,
    artifact: str,
    epic: str | None = None,
    epic_status: str | None = None,
) -> dict:
    """Record a skill's artifact save in the DB."""
    artifact_path = _validate_artifact_path(platform, artifact)

    with get_conn() as conn:
        migrate(conn)

        # Auto-create platform if missing
        if not get_platform(conn, platform):
            yaml_path = REPO_ROOT / "platforms" / platform / "platform.yaml"
            if yaml_path.exists():
                seed_from_filesystem(conn, platform, REPO_ROOT / "platforms" / platform)
            else:
                upsert_platform(conn, platform, name=platform, repo_path=f"platforms/{platform}")

        # Compute hash of the artifact
        output_hash = None
        if artifact_path.exists():
            output_hash = compute_file_hash(artifact_path)

        # Batch all writes into a single transaction for atomicity
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        shipped_delivered_at = None  # track ship transition for post-txn filesystem write
        with transaction(conn) as txn:
            if epic:
                # Skip update if epic node was already completed by a real skill with same hash
                existing_epic_node = next(
                    (n for n in get_epic_nodes(txn, platform, epic) if n["node_id"] == node),
                    None,
                )
                epic_was_completed_by_skill = (
                    existing_epic_node
                    and existing_epic_node.get("completed_by")
                    and not existing_epic_node["completed_by"].startswith("seed")
                )
                skip_epic_update = (
                    existing_epic_node
                    and existing_epic_node["status"] == "done"
                    and epic_was_completed_by_skill
                    and existing_epic_node.get("output_hash")
                    and output_hash == existing_epic_node["output_hash"]
                )
                if not skip_epic_update:
                    upsert_epic_node(
                        txn,
                        platform,
                        epic,
                        node,
                        "done",
                        output_hash=output_hash,
                        completed_by=skill,
                        completed_at=now,
                    )
                    insert_event(
                        txn,
                        platform,
                        "epic_node",
                        f"{epic}/{node}",
                        "completed",
                        actor="claude",
                        payload={"skill": skill, "artifact": artifact},
                    )

                # Backfill missing predecessor nodes whose artifacts exist on disk
                yaml_path = REPO_ROOT / "platforms" / platform / "platform.yaml"
                pipeline_data = (
                    yaml.safe_load(yaml_path.read_text(encoding="utf-8")).get("pipeline", {})
                    if yaml_path.exists()
                    else {}
                )
                completed_ids = _backfill_epic_predecessors(txn, platform, epic, pipeline_data)

                # Auto-transition epic status using centralized logic
                existing_epics = [e for e in get_epics(txn, platform) if e["epic_id"] == epic]
                if existing_epics:
                    current = existing_epics[0]
                    if epic_status:
                        # Explicit override (e.g., --epic-status drafted)
                        new_status, delivered_at = epic_status, None
                    else:
                        required_nodes = _get_required_epic_nodes(platform, pipeline_data)
                        new_status, delivered_at = compute_epic_status(
                            txn,
                            platform,
                            epic,
                            required_nodes,
                            current["status"],
                            completed_ids=completed_ids,
                        )
                    if new_status != current["status"]:
                        upsert_epic(
                            txn,
                            platform,
                            epic,
                            title=current["title"],
                            status=new_status,
                            delivered_at=delivered_at,
                        )
                        if delivered_at:
                            shipped_delivered_at = delivered_at
            else:
                # Skip update if node was already completed by a real skill with the same hash
                # (prevents side-effect edits from other skills overwriting completed_at)
                # Allow update if completed_by is from seed (not a real skill execution)
                existing_node = next(
                    (n for n in get_pipeline_nodes(txn, platform) if n["node_id"] == node),
                    None,
                )
                was_completed_by_skill = (
                    existing_node
                    and existing_node.get("completed_by")
                    and not existing_node["completed_by"].startswith("seed")
                )
                skip_update = (
                    existing_node
                    and existing_node["status"] == "done"
                    and was_completed_by_skill
                    and existing_node.get("output_hash")
                    and output_hash == existing_node["output_hash"]
                )
                if not skip_update:
                    upsert_pipeline_node(
                        txn,
                        platform,
                        node,
                        "done",
                        output_hash=output_hash,
                        output_files=json.dumps([artifact]),
                        completed_by=skill,
                        completed_at=now,
                    )
                    insert_event(
                        txn,
                        platform,
                        "node",
                        node,
                        "completed",
                        actor="claude",
                        payload={"skill": skill, "artifact": artifact},
                    )

            # Record provenance
            insert_provenance(
                txn,
                platform,
                artifact,
                generated_by=skill,
                epic_id=epic,
                output_hash=output_hash,
            )

    # Sync ship fields to pitch.md frontmatter (outside transaction — filesystem only)
    if epic and shipped_delivered_at:
        _inject_ship_fields(platform, epic, shipped_delivered_at)

    # Refresh portal dashboard JSON (best-effort, non-blocking)
    _refresh_portal_status()

    result = {
        "status": "ok",
        "platform": platform,
        "node": node,
        "artifact": artifact,
        "hash": output_hash,
    }
    if epic:
        result["epic"] = epic
    return result


def reseed(platform: str) -> dict:
    """Re-seed a platform from filesystem."""
    pdir = REPO_ROOT / "platforms" / platform
    if not pdir.exists():
        return {"status": "error", "reason": f"Platform dir not found: {pdir}"}
    with get_conn() as conn:
        migrate(conn)
        result = seed_from_filesystem(conn, platform, pdir)
    return result


def reseed_all() -> list[dict]:
    """Re-seed all platforms from filesystem.

    Opens a single connection and migrates once, then seeds all platforms
    (instead of N connections + N migration scans).
    """
    platforms_dir = REPO_ROOT / "platforms"
    results = []
    with get_conn() as conn:
        migrate(conn)
        for pdir in sorted(platforms_dir.iterdir()):
            yaml_path = pdir / "platform.yaml"
            if pdir.is_dir() and yaml_path.exists():
                r = seed_from_filesystem(conn, pdir.name, pdir)
                results.append({"platform": pdir.name, **r})
    return results


def detect_from_path(file_path: str) -> dict | None:
    """Infer platform, epic, node, skill, and artifact from a file path.

    Matches the path against output patterns in platform.yaml (L1 nodes and
    epic_cycle nodes) to auto-detect which node produced the artifact.
    Returns a dict ready for record_save(), or None if no match.
    """

    path = Path(file_path).resolve()
    platforms_dir = REPO_ROOT / "platforms"

    # Extract platform name from path: platforms/<name>/...
    try:
        rel = path.relative_to(platforms_dir)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2:
        return None
    platform = parts[0]
    artifact = str(Path(*parts[1:]))  # relative to platform dir

    yaml_path = platforms_dir / platform / "platform.yaml"
    if not yaml_path.exists():
        return None
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    pipeline = data.get("pipeline", {})

    # Check if this is an epic artifact: epics/<epic-id>/...
    epic = None
    if len(parts) >= 3 and parts[1] == "epics":
        epic = parts[2]

    # Try L2 epic cycle nodes first (if epic is set)
    if epic:
        for node_cfg in pipeline.get("epic_cycle", {}).get("nodes", []):
            for output_pattern in node_cfg.get("outputs", []):
                expected = output_pattern.replace("{epic}", f"epics/{epic}")
                if artifact == expected:
                    return {
                        "platform": platform,
                        "epic": epic,
                        "node": node_cfg["id"],
                        "skill": node_cfg["skill"],
                        "artifact": artifact,
                    }

    # Try L1 pipeline nodes
    for node_cfg in pipeline.get("nodes", []):
        for output in node_cfg.get("outputs", []):
            if artifact == output:
                return {
                    "platform": platform,
                    "node": node_cfg["id"],
                    "skill": node_cfg.get("skill", node_cfg["id"]),
                    "artifact": artifact,
                }

    return None


def main():
    parser = argparse.ArgumentParser(description="Record pipeline state after artifact save")
    parser.add_argument("--platform", help="Platform name (e.g., fulano)")
    parser.add_argument("--node", help="DAG node ID (e.g., vision, specify)")
    parser.add_argument("--skill", help="Skill that generated the artifact (e.g., madruga:vision)")
    parser.add_argument(
        "--artifact",
        help="Relative path to artifact within platform dir (e.g., business/vision.md)",
    )
    parser.add_argument("--epic", help="Epic ID for L2 nodes (e.g., 001-channel-pipeline)")
    parser.add_argument("--epic-status", dest="epic_status", help="Override epic status (e.g., drafted)")
    parser.add_argument("--reseed", action="store_true", help="Re-seed platform from filesystem")
    parser.add_argument(
        "--reseed-all",
        action="store_true",
        help="Re-seed all platforms from filesystem",
    )
    parser.add_argument(
        "--detect-from-path",
        dest="detect_path",
        help="Auto-detect platform/node/skill from file path (used by hooks)",
    )

    args = parser.parse_args()

    if args.detect_path:
        detected = detect_from_path(args.detect_path)
        if not detected:
            # Not a recognized pipeline artifact — silently exit
            return
        result = record_save(**detected)
        print(json.dumps(result))
        return

    if args.reseed_all:
        results = reseed_all()
        for r in results:
            print(json.dumps(r))
        return

    if args.reseed:
        if not args.platform:
            parser.error("--reseed requires --platform")
        result = reseed(args.platform)
        print(json.dumps(result))
        return

    # Normal save recording
    if not all([args.platform, args.node, args.skill, args.artifact]):
        parser.error("--platform, --node, --skill, and --artifact are required")

    result = record_save(
        platform=args.platform,
        node=args.node,
        skill=args.skill,
        artifact=args.artifact,
        epic=args.epic,
        epic_status=args.epic_status,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
