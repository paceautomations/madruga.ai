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
import sys
from pathlib import Path

# Add scripts dir to path for db import
sys.path.insert(0, str(Path(__file__).parent))

from db import (
    compute_file_hash,
    get_conn,
    get_platform,
    insert_event,
    insert_provenance,
    migrate,
    seed_from_filesystem,
    upsert_epic_node,
    upsert_platform,
    upsert_pipeline_node,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _validate_artifact_path(platform: str, artifact: str) -> Path:
    """Validate artifact path is within the platform directory (prevent path traversal)."""
    platform_dir = (REPO_ROOT / "platforms" / platform).resolve()
    artifact_path = (platform_dir / artifact).resolve()
    if not str(artifact_path).startswith(str(platform_dir) + "/"):
        raise ValueError(
            f"Path traversal detected: '{artifact}' resolves outside platform dir"
        )
    return artifact_path


def record_save(
    platform: str,
    node: str,
    skill: str,
    artifact: str,
    epic: str | None = None,
) -> dict:
    """Record a skill's artifact save in the DB."""
    artifact_path = _validate_artifact_path(platform, artifact)

    conn = get_conn()
    migrate(conn)

    # Auto-create platform if missing
    if not get_platform(conn, platform):
        yaml_path = REPO_ROOT / "platforms" / platform / "platform.yaml"
        if yaml_path.exists():
            seed_from_filesystem(conn, platform, REPO_ROOT / "platforms" / platform)
        else:
            upsert_platform(
                conn, platform, name=platform, repo_path=f"platforms/{platform}"
            )

    # Compute hash of the artifact
    output_hash = None
    if artifact_path.exists():
        output_hash = compute_file_hash(artifact_path)

    # Update pipeline node or epic node
    if epic:
        upsert_epic_node(
            conn,
            platform,
            epic,
            node,
            "done",
            output_hash=output_hash,
            completed_by=skill,
        )
        insert_event(
            conn,
            platform,
            "epic_node",
            f"{epic}/{node}",
            "completed",
            actor="claude",
            payload={"skill": skill, "artifact": artifact},
        )
    else:
        upsert_pipeline_node(
            conn,
            platform,
            node,
            "done",
            output_hash=output_hash,
            output_files=json.dumps([artifact]),
            completed_by=skill,
        )
        insert_event(
            conn,
            platform,
            "node",
            node,
            "completed",
            actor="claude",
            payload={"skill": skill, "artifact": artifact},
        )

    # Record provenance
    insert_provenance(
        conn,
        platform,
        artifact,
        generated_by=skill,
        epic_id=epic,
        output_hash=output_hash,
    )

    conn.close()

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
    conn = get_conn()
    migrate(conn)
    pdir = REPO_ROOT / "platforms" / platform
    if not pdir.exists():
        conn.close()
        return {"status": "error", "reason": f"Platform dir not found: {pdir}"}
    result = seed_from_filesystem(conn, platform, pdir)
    conn.close()
    return result


def reseed_all() -> list[dict]:
    """Re-seed all platforms from filesystem."""
    platforms_dir = REPO_ROOT / "platforms"
    results = []
    for pdir in sorted(platforms_dir.iterdir()):
        yaml_path = pdir / "platform.yaml"
        if pdir.is_dir() and yaml_path.exists():
            r = reseed(pdir.name)
            results.append({"platform": pdir.name, **r})
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Record pipeline state after artifact save"
    )
    parser.add_argument("--platform", help="Platform name (e.g., fulano)")
    parser.add_argument("--node", help="DAG node ID (e.g., vision, specify)")
    parser.add_argument(
        "--skill", help="Skill that generated the artifact (e.g., madruga:vision)"
    )
    parser.add_argument(
        "--artifact",
        help="Relative path to artifact within platform dir (e.g., business/vision.md)",
    )
    parser.add_argument(
        "--epic", help="Epic ID for L2 nodes (e.g., 001-channel-pipeline)"
    )
    parser.add_argument(
        "--reseed", action="store_true", help="Re-seed platform from filesystem"
    )
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
