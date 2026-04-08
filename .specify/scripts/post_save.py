#!/usr/bin/env python3
"""
post_save.py — CLI wrapper for recording pipeline state after a skill saves an artifact.

Called by skills at Step 5 of the pipeline contract. Wraps db.py functions
into a single command that the AI can call after saving any artifact.

Usage:
    # L1 (platform DAG):
    python3 .specify/scripts/post_save.py \
        --platform prosauai --node vision --skill madruga:vision \
        --artifact business/vision.md

    # L2 (epic cycle):
    python3 .specify/scripts/post_save.py \
        --platform prosauai --epic 001-channel-pipeline \
        --node specify --skill speckit.specify \
        --artifact epics/001-channel-pipeline/spec.md

    # Re-seed from filesystem:
    python3 .specify/scripts/post_save.py --reseed --platform prosauai

    # Re-seed all platforms:
    python3 .specify/scripts/post_save.py --reseed-all
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add scripts dir to path for db/config import
sys.path.insert(0, str(Path(__file__).parent))


from config import REPO_ROOT, UNFILLED_TEMPLATE_MARKERS  # noqa: F401

log = logging.getLogger("post_save")


from log_utils import setup_logging as _setup_logging  # noqa: E402


from db_pipeline import get_commit_stats  # noqa: E402

from db import (  # noqa: E402, F401 — compute_epic_status used in record_save
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
                str(REPO_ROOT / ".specify" / "scripts" / "platform_cli.py"),
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

    # Also regenerate commits-status.json (best-effort)
    try:
        export_commits_json()
    except Exception:
        pass


def export_commits_json(output_path: str | Path | None = None) -> Path:
    """Export all commits from DB to a JSON file for portal consumption.

    Queries all commits and computes aggregate stats (by_epic, by_platform,
    adhoc_pct). Writes to ``portal/src/data/commits-status.json`` by default.

    Args:
        output_path: Destination file path. Defaults to
            ``REPO_ROOT / portal/src/data/commits-status.json``.

    Returns:
        The resolved output Path that was written.
    """
    if output_path is None:
        output_path = REPO_ROOT / "portal" / "src" / "data" / "commits-status.json"
    output_path = Path(output_path)

    with get_conn() as conn:
        migrate(conn)

        # Fetch all commits ordered by committed_at DESC
        rows = conn.execute(
            "SELECT sha, message, author, platform_id, epic_id, source, committed_at, files_json "
            "FROM commits ORDER BY committed_at DESC"
        ).fetchall()

        commits = []
        by_platform: dict[str, int] = {}
        for row in rows:
            r = dict(row)
            # Parse files_json back to list for cleaner JSON output
            try:
                r["files"] = json.loads(r.pop("files_json"))
            except (json.JSONDecodeError, TypeError):
                r["files"] = []
                r.pop("files_json", None)
            commits.append(r)
            # Accumulate by_platform counts
            pid = r["platform_id"]
            by_platform[pid] = by_platform.get(pid, 0) + 1

        # Use existing stats function for by_epic and adhoc_pct
        stats = get_commit_stats(conn)

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commits": commits,
        "stats": {
            "by_epic": stats["commits_per_epic"],
            "by_platform": by_platform,
            "adhoc_pct": stats["adhoc_percentage"],
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Exported %d commits to %s", len(commits), output_path)
    return output_path


def sync_commits(conn, platform_id: str) -> int:
    """Synchronize commits from git history into the DB for a platform.

    Reads the full git log and inserts each commit via INSERT OR IGNORE,
    so existing records are untouched and only missing ones are added.
    Reuses epic detection logic from hook_post_commit (branch pattern and
    message tag).

    For reseed, all commits are attributed to the given ``platform_id``
    (the caller already scoped the reseed to a specific platform). File-based
    platform detection is not used here — that's the hook's job at capture
    time. Reseed is a recovery mechanism, not a classification mechanism.

    Args:
        conn: SQLite connection (caller owns transaction boundary).
        platform_id: Platform to attribute commits to.

    Returns:
        Number of commits processed (not necessarily inserted — INSERT OR
        IGNORE skips existing).
    """
    from hook_post_commit import parse_branch, parse_epic_tag

    from db_pipeline import insert_commit

    # Get current branch for epic detection
    try:
        br = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        branch = br.stdout.strip() if br.returncode == 0 else ""
    except OSError:
        branch = ""

    _branch_platform, branch_epic = parse_branch(branch)

    # Fetch full git log: SHA, message, author, date — separated by blank lines
    try:
        result = subprocess.run(
            ["git", "log", "--format=%H%n%s%n%an%n%aI", "--all"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            log.warning("git log failed (rc=%d), skipping commit sync", result.returncode)
            return 0
    except OSError as exc:
        log.warning("git not available, skipping commit sync: %s", exc)
        return 0

    # Parse log output into commit records (4 lines per commit, blank-line separated)
    raw = result.stdout.strip()
    if not raw:
        return 0

    blocks = raw.split("\n\n")
    count = 0

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 4:
            continue

        sha, message, author, committed_at = lines[0], lines[1], lines[2], lines[3]

        # Get changed files for this commit
        try:
            tree_result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            files = [f for f in tree_result.stdout.strip().split("\n") if f]
        except OSError:
            files = []

        # Epic detection: branch first, then message tag override
        tag_epic = parse_epic_tag(message)
        epic_id = tag_epic if tag_epic is not None else branch_epic

        files_json = json.dumps(files)

        insert_commit(
            conn,
            sha=sha,
            message=message,
            author=author,
            platform_id=platform_id,
            epic_id=epic_id,
            source="reseed",
            committed_at=committed_at,
            files_json=files_json,
        )
        count += 1

    conn.commit()
    log.info("sync_commits: processed %d commits for platform '%s'", count, platform_id)
    return count


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
    """Read required (non-optional) epic cycle node IDs from pipeline.yaml."""
    if pipeline_data is None:
        from config import load_pipeline

        pipeline_data = load_pipeline()
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

        # Detect current git branch before entering transaction (avoid subprocess inside txn)
        _current_branch = None
        if epic:
            try:
                br = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    cwd=str(REPO_ROOT),
                )
                _current_branch = br.stdout.strip() if br.returncode == 0 else None
            except OSError:
                pass

        # Pre-read pipeline data outside transaction to avoid I/O inside txn
        pipeline_data = {}
        if epic:
            from config import load_pipeline

            pipeline_data = load_pipeline()

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
                # Reject unfilled templates — don't mark node as done
                is_template = False
                if artifact_path.exists():
                    try:
                        with artifact_path.open(encoding="utf-8", errors="replace") as _f:
                            head = _f.read(2000)
                        is_template = any(m in head for m in UNFILLED_TEMPLATE_MARKERS)
                    except OSError:
                        pass
                if is_template:
                    log.warning("Skipping node done — unfilled template: %s", artifact)
                    skip_epic_update = True
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

                    # Auto-set branch_name from pre-fetched git branch
                    if not current.get("branch_name") and _current_branch and _current_branch.startswith("epic/"):
                        upsert_epic(txn, platform, epic, title=current["title"], branch_name=_current_branch)
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
                hash_unchanged = (
                    existing_node
                    and existing_node["status"] == "done"
                    and was_completed_by_skill
                    and existing_node.get("output_hash")
                    and output_hash == existing_node["output_hash"]
                )
                # Always bump completed_at (even on identical hash) so DAG
                # ordering stays correct after review passes.
                upsert_kwargs: dict = dict(completed_at=now)
                if not hash_unchanged:
                    upsert_kwargs.update(
                        output_hash=output_hash,
                        output_files=json.dumps([artifact]),
                        completed_by=skill,
                    )
                upsert_pipeline_node(txn, platform, node, "done", **upsert_kwargs)
                if not hash_unchanged:
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
    """Re-seed a platform from filesystem.

    After seeding pipeline nodes and epics, also synchronizes commits from
    git history (best-effort). This fills gaps when the post-commit hook
    missed commits (e.g. hook not installed, DB unavailable at commit time).
    """
    pdir = REPO_ROOT / "platforms" / platform
    if not pdir.exists():
        return {"status": "error", "reason": f"Platform dir not found: {pdir}"}
    with get_conn() as conn:
        migrate(conn)
        result = seed_from_filesystem(conn, platform, pdir)
        # Sync commits from git history (best-effort — never fail the reseed)
        try:
            commits_synced = sync_commits(conn, platform)
            result["commits_synced"] = commits_synced
        except Exception as exc:
            log.warning("sync_commits failed for '%s': %s", platform, exc)
            result["commits_synced"] = 0
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

    # Verify platform directory exists
    if not (platforms_dir / platform / "platform.yaml").exists():
        return None
    from config import load_pipeline

    pipeline = load_pipeline()

    # Check if this is an epic artifact: epics/<epic-id>/...
    epic = None
    if len(parts) >= 3 and parts[1] == "epics":
        epic = parts[2]

    # Try L2 epic cycle nodes first (if epic is set)
    # When multiple nodes declare the same output file (e.g. tasks.md used by
    # both 'tasks' and 'implement'), pick the first NOT-YET-DONE node in
    # topological order to avoid marking downstream nodes as done prematurely.
    if epic:
        matches = []
        for node_cfg in pipeline.get("epic_cycle", {}).get("nodes", []):
            for output_pattern in node_cfg.get("outputs", []):
                expected = output_pattern.replace("{epic}", f"epics/{epic}")
                if artifact == expected:
                    matches.append(node_cfg)

        if matches:
            if len(matches) > 1:
                # Disambiguate: pick first unfinished node in DAG order
                try:
                    with get_conn() as conn:
                        done_nodes = {
                            n["node_id"]
                            for n in get_epic_nodes(conn, platform, epic)
                            if n["status"] in ("done", "skipped")
                        }
                    for m in matches:
                        if m["id"] not in done_nodes:
                            matches = [m]
                            break
                    else:
                        # All matching nodes already done — use last (most downstream)
                        matches = [matches[-1]]
                except Exception:
                    # DB unavailable — fall back to first match
                    matches = [matches[0]]

            node_cfg = matches[0]
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
    parser.add_argument("--platform", help="Platform name (e.g., prosauai)")
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
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_mode",
        help="Emit structured NDJSON log output (for CI consumption)",
    )

    args = parser.parse_args()

    _setup_logging(args.json_mode)

    if args.detect_path:
        detected = detect_from_path(args.detect_path)
        if not detected:
            # Not a recognized pipeline artifact — silently exit
            return
        log.info("Auto-detected: %s/%s → %s", detected["platform"], detected["node"], detected["artifact"])
        result = record_save(**detected)
        print(json.dumps(result))
        return

    if args.reseed_all:
        log.info("Re-seeding all platforms from filesystem")
        results = reseed_all()
        for r in results:
            log.info("Reseeded: %s", r.get("platform", "?"))
            print(json.dumps(r))
        return

    if args.reseed:
        if not args.platform:
            parser.error("--reseed requires --platform")
        log.info("Re-seeding platform '%s' from filesystem", args.platform)
        result = reseed(args.platform)
        print(json.dumps(result))
        return

    # Normal save recording
    if not all([args.platform, args.node, args.skill, args.artifact]):
        parser.error("--platform, --node, --skill, and --artifact are required")

    log.info("Recording save: %s/%s → %s", args.platform, args.node, args.artifact)
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
