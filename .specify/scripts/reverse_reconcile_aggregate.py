"""Collapse per-commit triage into per-file work list grounded in HEAD state.

Input: triage JSON produced by `reverse_reconcile_classify.py` (commits sorted
ASC by committed_at).

Output: work list that groups all SHAs touching the same file into ONE entry,
plus the HEAD content of the file (truncated). This gives LLM a HEAD-first
view of drift — not a per-commit view — so chronological sequences (A modifies,
B reverts, C modifies again) collapse to one decision: "what is HEAD and what
doc reflects it?".

Deterministic. No LLM.

Usage:
    python3 reverse_reconcile_aggregate.py --platform <name> \
        --triage /tmp/triage.json --out /tmp/work.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / ".specify" / "scripts"))

import db_core  # noqa: E402,F401  (used inside _assert_no_reconciled_leak)
import ensure_repo as ensure_repo_mod  # noqa: E402

log = logging.getLogger("reverse_reconcile_aggregate")

# ── Screen-flow drift detection (epic 027 — FR-036/039) ─────────────────────
# Charset enforced on screen.id (FR-048). resolve_screen_id_from_rules refuses
# to emit a patch if the resolved id would not be valid in screen-flow.yaml.
_SCREEN_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
# `{1}`, `{2}`, … placeholders in screen_id_template (referenced groups of the
# matched regex). Captured here so resolve_screen_id_from_rules can detect a
# template that requests a group the regex does NOT have, instead of silently
# emitting the literal placeholder.
_TEMPLATE_GROUP_RE = re.compile(r"\{(\d+)\}")

# First N lines + last M lines kept in the HEAD snippet (avoids token blowup on large files).
_HEAD_SNIPPET_HEAD = 50
_HEAD_SNIPPET_TAIL = 20

# Files considered "platform-owned content" — NOT patch targets, they ARE the docs.
# A mixed commit drops these files before building code_items; a commit where ALL
# files are platform-owned becomes an auto-reconcile.
_PLATFORM_OWNED_RE = re.compile(r"^platforms/[^/]+/")


def _is_platform_owned(path: str) -> bool:
    return bool(_PLATFORM_OWNED_RE.match(path))


# Sentinel: candidate is NOT a real file — flags an "ADR Candidate" note for the skill to
# surface in its report (Phase 5 / Phase 9 of reverse-reconcile.md). Never patched, never
# filtered out by the existence check.
ADR_CANDIDATE_SENTINEL = "__ADR_CANDIDATE__"

# Path → doc candidates heuristic. Ordered by precedence (first match wins).
# Each rule: (regex, [(layer, basename), ...]). `basename` may be the sentinel
# `__ADR_CANDIDATE__` to flag a pending architectural decision. Layers map to the
# `platforms/<name>/<layer>/` subtree.
_DOC_CANDIDATE_RULES: list[tuple[re.Pattern, list[tuple[str, str]]]] = [
    # Dependency manifests — strongest tech-stack signal + candidate ADR.
    # Matched before feature/domain rules because manifests are file-root literals.
    (
        re.compile(
            r"^(pyproject\.toml|package\.json|package-lock\.json|requirements.*\.txt|Cargo\.toml|go\.(mod|sum))$"
        ),
        [
            ("research", "tech-alternatives.md"),
            ("decisions", ADR_CANDIDATE_SENTINEL),
            ("engineering", "blueprint.md"),
        ],
    ),
    # Feature/use-case paths: strong scope signal → business docs first, then domain.
    (
        re.compile(r"(^|/)(features?|use[-_]?cases?)/"),
        [
            ("business", "solution-overview.md"),
            ("business", "process.md"),
            ("engineering", "domain-model.md"),
        ],
    ),
    # Domain / entities — match at any depth
    (
        re.compile(r"(^|/)(models|entities|domain|schemas?)/"),
        [("engineering", "domain-model.md"), ("engineering", "blueprint.md")],
    ),
    # Migrations / schema DDL
    (
        re.compile(r"^(migrations|alembic)/|(^|/)schema/"),
        [("engineering", "data-model.md"), ("engineering", "domain-model.md")],
    ),
    # Database modules (sqlite/postgres helpers in any script dir)
    (
        re.compile(r"(^|/)db[_/]|(^|/)database[_/]"),
        [("engineering", "data-model.md"), ("engineering", "domain-model.md")],
    ),
    # API / routing / controllers / webhooks / handlers
    (
        re.compile(r"(^|/)(api|routers?|controllers?|endpoints?|webhooks?|handlers?)(/|\.[a-z]+$)"),
        [("engineering", "context-map.md"), ("engineering", "containers.md")],
    ),
    # Orchestrators / daemons / background workers (key container concern)
    (
        re.compile(r"(easter|daemon|scheduler|worker|executor|orchestrator|dispatcher)\.(py|ts|js)$"),
        [("engineering", "containers.md"), ("engineering", "blueprint.md")],
    ),
    # Container / infra files — also trigger ADR candidate (infra is decision-heavy).
    (
        re.compile(r"(^|/)(docker|k8s|kubernetes|deploy|infra)/|^(Dockerfile|docker-compose)|^\.github/workflows/"),
        [
            ("engineering", "containers.md"),
            ("engineering", "blueprint.md"),
            ("decisions", ADR_CANDIDATE_SENTINEL),
        ],
    ),
    # Build tooling (less decision-laden than manifests)
    (
        re.compile(r"^(Makefile|tsconfig\.json)"),
        [("engineering", "containers.md"), ("engineering", "blueprint.md")],
    ),
    # Portal / frontend layout
    (re.compile(r"^portal/src/components/"), [("engineering", "containers.md"), ("engineering", "context-map.md")]),
    (re.compile(r"^portal/src/pages/"), [("engineering", "context-map.md"), ("engineering", "containers.md")]),
    (re.compile(r"^portal/src/"), [("engineering", "containers.md"), ("engineering", "blueprint.md")]),
    # Generic script/tooling dirs (madruga-ai style)
    (
        re.compile(r"^\.specify/scripts/|^scripts/"),
        [("engineering", "blueprint.md"), ("engineering", "containers.md")],
    ),
    # Generic app code fallback
    (
        re.compile(r"^(src|app|apps|services|lib)/"),
        [("engineering", "blueprint.md"), ("engineering", "containers.md")],
    ),
]

# Repo-level authored docs (for self-ref platforms these are the docs themselves, not targets)
_SELF_REF_DOC_RE = re.compile(
    r"^(CLAUDE\.md|README\.md|\.claude/commands/.+\.md|\.claude/knowledge/.+\.md|\.claude/rules/.+\.md)$"
)


def _is_self_ref_doc(path: str) -> bool:
    """True if path is authored documentation at the repo root or under .claude/."""
    return bool(_SELF_REF_DOC_RE.match(path))


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _resolve_ref(repo_path: Path, branch: str) -> str:
    """Prefer origin/<branch>, fallback to local <branch>. Empty string if neither."""
    for ref in (f"origin/{branch}", branch):
        check = _run_git(["rev-parse", "--verify", "--quiet", ref], repo_path)
        if check.returncode == 0:
            return ref
    return ""


def _list_head_files(repo_path: Path, ref: str) -> set[str]:
    """Return set of all paths present at `<ref>`. Single git call."""
    result = _run_git(["ls-tree", "-r", "--name-only", ref], repo_path)
    if result.returncode != 0:
        return set()
    return {line for line in result.stdout.splitlines() if line}


def _head_tip_sha(repo_path: Path, ref: str) -> str:
    result = _run_git(["rev-parse", ref], repo_path)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _head_content_snippet(repo_path: Path, ref: str, path: str) -> str:
    """Return truncated content of <ref>:<path>. Binary-safe."""
    # Run with bytes to avoid UnicodeDecodeError on binary blobs (PNGs, etc.)
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=str(repo_path),
        capture_output=True,
    )
    if result.returncode != 0:
        return "<not present>"
    try:
        content = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return "<binary>"
    if "\x00" in content:
        return "<binary>"
    lines = content.splitlines()
    total = len(lines)
    if total <= _HEAD_SNIPPET_HEAD + _HEAD_SNIPPET_TAIL:
        return content
    head = "\n".join(lines[:_HEAD_SNIPPET_HEAD])
    tail = "\n".join(lines[-_HEAD_SNIPPET_TAIL:])
    return f"{head}\n\n... [{total - _HEAD_SNIPPET_HEAD - _HEAD_SNIPPET_TAIL} lines truncated] ...\n\n{tail}"


def _candidate_docs(file_path: str, platform_id: str) -> list[str]:
    """Return ordered list of platform doc candidates across all L1 layers.

    Rules map file paths to `(layer, basename)` tuples so candidates can span
    business/, engineering/, research/, planning/, decisions/. Non-existent
    files are dropped — LLM downstream never receives paths that would make
    `reverse_reconcile_apply.py` fail with FileNotFound. The ADR sentinel is
    preserved verbatim (it's a flag for the skill, not a patch target).

    If all concrete candidates are missing, fall back to blueprint.md — the
    skill instructs the LLM to `operation: append` a new section there.
    """
    for regex, candidates in _DOC_CANDIDATE_RULES:
        if regex.search(file_path):
            raw = [f"platforms/{platform_id}/{layer}/{basename}" for (layer, basename) in candidates]
            break
    else:
        raw = [
            f"platforms/{platform_id}/engineering/blueprint.md",
            f"platforms/{platform_id}/engineering/containers.md",
        ]
    existing = [p for p in raw if p.endswith(ADR_CANDIDATE_SENTINEL) or (REPO_ROOT / p).exists()]
    if existing:
        return existing
    return [f"platforms/{platform_id}/engineering/blueprint.md"]


# ── Screen-flow drift mapping (epic 027 — FR-036/037/039) ──────────────────


def _load_platform_screen_flow(platform_id: str) -> dict | None:
    """Read `screen_flow:` block from `platforms/<platform>/platform.yaml`.

    Returns the block dict (or None when the file or the block is absent). Errors
    parsing the YAML are swallowed and logged — drift detection should be a
    silent enrichment, never a blocker for the rest of the aggregate output.
    """
    manifest = REPO_ROOT / "platforms" / platform_id / "platform.yaml"
    if not manifest.exists():
        return None
    try:
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        log.warning("could not parse platform.yaml for %s: %s", platform_id, exc)
        return None
    block = data.get("screen_flow")
    return block if isinstance(block, dict) else None


def resolve_screen_id_from_rules(file_path: str, rules: list[dict]) -> str | None:
    """Apply path_rules in order; return the resolved screen_id of the first match.

    Skips:
    - rules with invalid regex (cannot compile)
    - templates referencing groups absent in the regex (bad config — emit nothing)
    - resolved ids that violate the FR-048 charset (defensive — never write
      malformed ids into screen-flow.yaml)
    """
    if not rules:
        return None
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        pattern = rule.get("pattern")
        template = rule.get("screen_id_template")
        if not isinstance(pattern, str) or not isinstance(template, str):
            continue
        try:
            compiled = re.compile(pattern)
        except re.error:
            continue
        m = compiled.search(file_path)
        if not m:
            continue
        groups = m.groups()
        # Validate that the template only references existing groups before substituting.
        ok = True
        for ref in _TEMPLATE_GROUP_RE.findall(template):
            idx = int(ref)
            if idx < 1 or idx > len(groups) or groups[idx - 1] is None:
                ok = False
                break
        if not ok:
            continue
        resolved = _TEMPLATE_GROUP_RE.sub(lambda mo: groups[int(mo.group(1)) - 1] or "", template)
        # File paths often contain hyphens (`verify-otp.tsx`, `set-password.tsx`)
        # but screen IDs must match `^[a-z][a-z0-9_]{0,63}$` (no hyphens). Slug-
        # convert hyphens so authors can use `[\w-]+` in path_rules without
        # manually mapping each hyphenated file. Casing is left as-is so
        # PascalCase filenames (convention violation) still fail validation.
        resolved = resolved.replace("-", "_")
        if not _SCREEN_ID_RE.match(resolved):
            log.debug(
                "screen-flow path_rule pattern %r resolved %r → invalid id %r — skipped",
                pattern,
                file_path,
                resolved,
            )
            continue
        return resolved
    return None


def _collect_screen_flow_patches(triage: dict, platform_id: str, screen_flow: dict | None) -> list[dict]:
    """Build deduplicated screen_flow_pending_patches from a triage payload.

    Returns one patch per distinct screen_id, with merged sha_refs + source_files
    across every commit that touched any matching file. Silently returns [] when
    the platform has `screen_flow.enabled: false` or no `path_rules` (FR-039).

    Defense-in-depth (FR-038, US-07): only iterates the ``clusters`` bucket of
    the triage, never ``doc_self_edits``. Plus, any platform-owned file that
    leaks into a cluster (regression in classify) is filtered here — the closed
    loop "edit screen-flow.yaml → reverse-reconcile re-flips it to pending"
    cannot close even if classify regresses. See
    test_doc_self_edit_no_cascade.py for the locked invariants.
    """
    if not screen_flow or not screen_flow.get("enabled"):
        return []
    capture = screen_flow.get("capture") or {}
    rules = capture.get("path_rules") or []
    if not rules:
        return []

    grouped: dict[str, dict] = {}
    clusters = triage.get("triage", {}).get("clusters", {})
    for commits in clusters.values():
        for commit in commits:
            sha = commit.get("sha")
            # Defensive guard (T102): even if a doc-self-edit commit somehow lands
            # in a cluster (classify regression), platform-owned files cannot drive
            # screen-flow patches. path_rules are scoped to app source paths and
            # platform-owned paths are explicitly skipped here as belt-and-braces.
            for f in commit.get("files", []):
                if _is_platform_owned(f):
                    continue
                sid = resolve_screen_id_from_rules(f, rules)
                if not sid:
                    continue
                bucket = grouped.setdefault(
                    sid,
                    {
                        "platform": platform_id,
                        "screen_id": sid,
                        "sha_refs": [],
                        "source_files": [],
                    },
                )
                if sha and sha not in bucket["sha_refs"]:
                    bucket["sha_refs"].append(sha)
                if f not in bucket["source_files"]:
                    bucket["source_files"].append(f)
    # Stable order across runs: sort by screen_id
    return [grouped[k] for k in sorted(grouped)]


def _collect_file_work(
    triage: dict,
) -> tuple[dict[str, list[dict]], list[str]]:
    """Split triage into (file → commits-touching-it, extra-self-edit-shas).

    Commits where every file is platform-owned get promoted to extra-self-edit:
    those are platform docs, not patch targets.
    """
    clusters = triage.get("triage", {}).get("clusters", {})
    relevant: list[dict] = []
    for commits in clusters.values():
        relevant.extend(commits)

    file_to_commits: dict[str, list[dict]] = {}
    extra_self_edits: list[str] = []
    for commit in relevant:
        # Exclude both platform-owned files and repo-level authored docs (for self-ref)
        code_files = [f for f in commit.get("files", []) if not _is_platform_owned(f) and not _is_self_ref_doc(f)]
        if not code_files:
            extra_self_edits.append(commit["sha"])
            continue
        for f in code_files:
            file_to_commits.setdefault(f, []).append(commit)
    return file_to_commits, extra_self_edits


def _build_entry(
    path: str,
    commits: list[dict],
    platform_id: str,
    *,
    exists: bool,
    head_sha: str,
    repo_path: Path,
    ref: str,
) -> dict:
    """Build one code_item (exists) or deleted_files entry."""
    shas = [c["sha"] for c in commits]
    subjects = [c["message"] for c in commits]
    cand = _candidate_docs(path, platform_id)
    if not exists:
        return {
            "path": path,
            "touched_by_shas": shas,
            "commit_subjects": subjects,
            "note": "No longer exists at HEAD — check candidate_docs for dangling references",
            "candidate_docs": cand,
        }
    return {
        "target_file": path,
        "file_exists_at_head": True,
        "head_content_snippet": _head_content_snippet(repo_path, ref, path),
        "head_sha": head_sha,
        "touched_by_shas": shas,
        "commit_subjects": subjects,
        "candidate_docs": cand,
    }


def _assert_no_reconciled_leak(platform_id: str, triage: dict, db_path: Path | None = None) -> None:
    """Invariant 6: aggregate MUST NOT see any commit whose ``reconciled_at IS NOT NULL``.

    A leak means ingest/classify skipped the ``WHERE reconciled_at IS NULL`` filter
    (regression). Failing loud here prevents silently re-proposing patches for
    already-reconciled work. Cost: one indexed SELECT, <1ms.
    """
    all_shas: set[str] = set()
    for e in triage.get("triage", {}).get("none", []):
        all_shas.add(e.get("sha", ""))
    for e in triage.get("triage", {}).get("doc_self_edits", []):
        all_shas.add(e.get("sha", ""))
    for commits in triage.get("triage", {}).get("clusters", {}).values():
        for c in commits:
            all_shas.add(c.get("sha", ""))
    all_shas.discard("")
    if not all_shas:
        return
    try:
        with db_core.get_conn(db_path) as conn:
            all_forms = list(all_shas) + [f"{s}:{platform_id}" for s in all_shas]
            placeholders = ",".join("?" for _ in all_forms)
            row = conn.execute(
                f"SELECT COUNT(*) FROM commits "
                f"WHERE platform_id = ? AND reconciled_at IS NOT NULL "
                f"AND sha IN ({placeholders})",
                [platform_id, *all_forms],
            ).fetchone()
        leaked = row[0] if row else 0
    except Exception as exc:
        log.warning("aggregate invariant check skipped: %s", exc)
        return
    if leaked > 0:
        raise AssertionError(
            f"Aggregate invariant violated: {leaked} reconciled commits in input "
            f"for platform={platform_id}. Triage/classify must filter reconciled_at IS NULL."
        )


def aggregate(platform_id: str, triage: dict, branch: str | None = None, db_path: Path | None = None) -> dict:
    """Collapse triage clusters into per-file work items. Returns JSON-ready dict."""
    _assert_no_reconciled_leak(platform_id, triage, db_path=db_path)
    repo_path = ensure_repo_mod.ensure_repo(platform_id)
    if branch is None:
        branch = ensure_repo_mod.load_repo_binding(platform_id)["base_branch"]
    ref = _resolve_ref(repo_path, branch)
    if not ref:
        raise SystemExit(f"ERROR: branch '{branch}' not found in {repo_path}")
    head_sha = _head_tip_sha(repo_path, ref)

    doc_self_edit_shas = [e["sha"] for e in triage.get("triage", {}).get("doc_self_edits", [])]
    file_to_commits, extra_self_edits = _collect_file_work(triage)
    doc_self_edit_shas.extend(extra_self_edits)

    head_files = _list_head_files(repo_path, ref)

    code_items: list[dict] = []
    deleted_files: list[dict] = []
    for path, commits in sorted(file_to_commits.items()):
        entry = _build_entry(
            path,
            commits,
            platform_id,
            exists=path in head_files,
            head_sha=head_sha,
            repo_path=repo_path,
            ref=ref,
        )
        (code_items if path in head_files else deleted_files).append(entry)

    # Screen-flow drift: enrich the work list with patches for `screen_flow_mark_pending.py`.
    # Skipped silently when the platform has `screen_flow.enabled: false` (FR-039).
    screen_flow_patches = _collect_screen_flow_patches(triage, platform_id, _load_platform_screen_flow(platform_id))

    return {
        "platform": platform_id,
        "branch": branch,
        "head_sha": head_sha,
        "doc_self_edits": {
            "shas_to_auto_reconcile": doc_self_edit_shas,
            "count": len(doc_self_edit_shas),
            "reason": "100% files under platforms/*/(business|engineering|decisions|planning)/ — already at HEAD",
        },
        "code_items": code_items,
        "deleted_files": deleted_files,
        "screen_flow_pending_patches": screen_flow_patches,
        "summary": {
            "doc_self_edits": len(doc_self_edit_shas),
            "code_items": len(code_items),
            "deleted_files": len(deleted_files),
            "screen_flow_pending_patches": len(screen_flow_patches),
        },
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--platform", required=True)
    p.add_argument("--triage", type=Path, required=True, help="JSON file produced by reverse_reconcile_classify.py")
    p.add_argument("--branch", help="Override base branch from platform.yaml")
    p.add_argument("--out", type=Path, help="Write JSON here instead of stdout")
    args = p.parse_args(argv)

    triage = json.loads(args.triage.read_text(encoding="utf-8"))
    result = aggregate(args.platform, triage, branch=args.branch)
    payload = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
