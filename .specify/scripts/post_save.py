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


from config import REPO_ROOT  # noqa: F401
from db import (
    compute_file_hash,
    get_conn,
    get_epic_nodes,
    get_epics,
    get_platform,
    insert_event,
    insert_provenance,
    migrate,
    seed_from_filesystem,
    transaction,
    upsert_epic,
    upsert_epic_node,
    upsert_platform,
    upsert_pipeline_node,
)


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
    if "delivered_at:" not in fm_block:
        fm_block += f"delivered_at: {delivered_at}\n"

    updated = "---" + fm_block + body
    pitch.write_text(updated, encoding="utf-8")


def _get_required_epic_nodes(platform: str) -> set[str]:
    """Read required (non-optional) epic cycle node IDs from platform.yaml."""
    import yaml

    yaml_path = REPO_ROOT / "platforms" / platform / "platform.yaml"
    if not yaml_path.exists():
        return set()
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    cycle_nodes = data.get("pipeline", {}).get("epic_cycle", {}).get("nodes", [])
    return {n["id"] for n in cycle_nodes if not n.get("optional", False)}


def record_save(
    platform: str,
    node: str,
    skill: str,
    artifact: str,
    epic: str | None = None,
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

                # Auto-transition epic status based on node completion
                # Skip if epic is blocked or cancelled (manual override only)
                nodes = get_epic_nodes(txn, platform, epic)
                if nodes:
                    completed_count = sum(1 for n in nodes if n["status"] in ("done", "skipped"))
                    completed_ids = {n["node_id"] for n in nodes if n["status"] in ("done", "skipped")}
                    required_nodes = _get_required_epic_nodes(platform)
                    existing = [e for e in get_epics(txn, platform) if e["epic_id"] == epic]
                    if existing:
                        current = existing[0]
                        if current["status"] not in ("blocked", "cancelled"):
                            new_status = current["status"]
                            delivered_at = None
                            # Ship only when ALL required (non-optional) nodes are done
                            all_required_done = required_nodes and required_nodes.issubset(completed_ids)
                            if all_required_done:
                                new_status = "shipped"
                                delivered_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                            elif completed_count > 0 and current["status"] == "proposed":
                                new_status = "in_progress"
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
    parser.add_argument("--reseed", action="store_true", help="Re-seed platform from filesystem")
    parser.add_argument(
        "--reseed-all",
        action="store_true",
        help="Re-seed all platforms from filesystem",
    )

    args = parser.parse_args()

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
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
