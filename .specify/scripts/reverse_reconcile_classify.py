"""Deterministic triage for unreconciled commits. No LLM.

Produces a JSON bundle the skill (LLM) consumes to generate doc patches.

Rules:
  - layer=none   → typos/formatting/lockfiles/ignore-only changes → auto-mark reconciled
  - layer=docs/business|engineering|decisions|planning → file path points to platforms/<p>/<layer>/
  - layer=code   → everything else (default). Skill/LLM decides which doc layer is impacted.

Output (JSON to stdout or --out):
    {
      "platform": "<name>",
      "generated_at": "<iso>",
      "triage": {
          "none": [{sha, message, reason}, ...],
          "clusters": {
              "business": [commit_dict, ...],
              "engineering": [...],
              "decisions": [...],
              "planning": [...],
              "code": [...],
          }
      },
      "total": N
    }

The skill then:
  1. Calls reverse_reconcile_mark.py with layer=none SHAs → auto-reconciled
  2. For each non-empty cluster, prompts LLM with the cluster's commits to emit patches
  3. Feeds patches to reverse_reconcile_apply.py
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".specify" / "scripts"))

import db_core  # noqa: E402

log = logging.getLogger("reverse_reconcile_classify")

# Files that are pure noise
_NOISE_EXTS = {".lock", ".log"}
_NOISE_BASENAMES = {
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    "poetry.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "Cargo.lock",
    "go.sum",
}
# Cache/build dirs: any file under these is noise (tool caches, build output).
_NOISE_DIR_RE = re.compile(
    r"^(\.hypothesis|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|"
    r"node_modules|dist|build|coverage|\.coverage|\.next|\.turbo|\.nuxt|\.svelte-kit|"
    r"target|\.tox|\.venv|venv)/"
)
# Keywords that flag trivial commits in the subject line
_TRIVIAL_SUBJECT = re.compile(
    r"^(chore|style|docs|fix)\s*(\([^)]+\))?\s*:\s*("
    r"typo|formatting|format|lint|whitespace|reformat|prettier|bump|"
    r"version bump|dependency update|deps:|update dep"
    r")",
    re.IGNORECASE,
)

# Layer routing from file paths inside platforms/<p>/
#
# Anything under business|engineering|decisions|planning is "platform-owned content"
# (the docs themselves, not patch targets). For epic 027 this implicitly covers
# `business/screen-flow.yaml` and `business/shots/*.png` — capture/auto-commit and
# manual edits to the screen-flow document never trigger reverse-reconcile cascade
# (FR-038 / US-07). See test_doc_self_edit_no_cascade.py for the locked invariants.
_LAYER_RE = re.compile(r"^platforms/[^/]+/(business|engineering|decisions|planning)/")


def _is_noise_file(path: str) -> bool:
    if _NOISE_DIR_RE.match(path):
        return True
    name = Path(path).name
    if name in _NOISE_BASENAMES:
        return True
    if Path(path).suffix in _NOISE_EXTS:
        return True
    return False


def _is_platform_doc_file(path: str) -> bool:
    """True if file lives under platforms/<p>/(business|engineering|decisions|planning)/."""
    return bool(_LAYER_RE.match(path))


def _classify_commit(commit: dict) -> tuple[str, str]:
    """Return (layer, reason).

    Layer in {none, doc-self-edit, business, engineering, decisions, planning, code}.

    doc-self-edit: 100% of files are platform doc edits. Already reflects HEAD →
    auto-reconcile without LLM analysis (avoids the circular "patch X based on
    commit that edited X" loop).
    """
    files = commit.get("files") or []
    message = commit.get("message", "")

    # All files are noise → none
    if files and all(_is_noise_file(f) for f in files):
        return "none", "only noise files (locks/ignore/etc)"
    # Empty commit (no files) → none (probably merge metadata)
    if not files:
        return "none", "no files touched"
    # Trivial commit subject
    if _TRIVIAL_SUBJECT.match(message):
        return "none", f"trivial subject: {message[:60]}"

    # Non-noise files: classify doc-self-edit vs mixed vs code
    non_noise = [f for f in files if not _is_noise_file(f)]
    doc_files = [f for f in non_noise if _is_platform_doc_file(f)]
    code_files = [f for f in non_noise if not _is_platform_doc_file(f)]

    # 100% platform docs, no code → doc-self-edit (already at HEAD)
    if doc_files and not code_files:
        return "doc-self-edit", f"100% platform doc edits — already at HEAD ({len(doc_files)} files)"

    # Mixed doc + code → code wins (code is the drift signal)
    # Pure code → code cluster
    return "code", f"code change ({len(code_files)} code files, {len(doc_files)} doc files)"


def triage(platform_id: str, db_path: Path | None = None) -> dict:
    """Fetch unreconciled commits for platform and triage them."""
    with db_core.get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT sha, message, author, committed_at, files_json FROM commits "
            "WHERE platform_id = ? AND reconciled_at IS NULL "
            "ORDER BY committed_at ASC",
            (platform_id,),
        ).fetchall()

    clusters: dict[str, list[dict]] = {
        "business": [],
        "engineering": [],
        "decisions": [],
        "planning": [],
        "code": [],
    }
    noise: list[dict] = []
    doc_self_edits: list[dict] = []
    for row in rows:
        sha, message, author, committed_at, files_json = row
        try:
            files = json.loads(files_json) if files_json else []
        except json.JSONDecodeError:
            files = []
        commit = {
            "sha": sha,
            "message": message,
            "author": author,
            "committed_at": committed_at,
            "files": files,
        }
        layer, reason = _classify_commit(commit)
        if layer == "none":
            noise.append({"sha": sha, "message": message, "reason": reason})
        elif layer == "doc-self-edit":
            doc_self_edits.append({"sha": sha, "message": message, "reason": reason, "files": files})
        else:
            commit["reason"] = reason
            clusters[layer].append(commit)

    return {
        "platform": platform_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(rows),
        "triage": {
            "none": noise,
            "doc_self_edits": doc_self_edits,
            "clusters": clusters,
        },
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--platform", required=True)
    p.add_argument("--out", type=Path, help="Write JSON here instead of stdout")
    args = p.parse_args(argv)

    result = triage(args.platform)
    payload = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
