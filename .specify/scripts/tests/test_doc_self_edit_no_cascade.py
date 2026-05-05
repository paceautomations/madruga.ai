"""Integration tests for FR-038 — doc-self-edit commits never cascade into screen-flow patches.

Epic 027 (Screen Flow Canvas), User Story 7. The reverse-reconcile pipeline must not
generate screen_flow_pending_patches for commits that ONLY edit platform documentation
(everything under `platforms/<p>/(business|engineering|decisions|planning)/`).

Two scenarios are covered:

1. Pure doc commit — touching ONLY platform docs (including `business/screen-flow.yaml`
   itself) must be classified as `doc-self-edit` by ``reverse_reconcile_classify`` and,
   crucially, must NOT trigger any patch from
   ``reverse_reconcile_aggregate._collect_screen_flow_patches``.
2. Mixed commit (doc + app) — must be classified as ``code`` (code is the drift
   signal), AND the screen-flow patch path must fire for the matching app file
   (and only for that file, not for the doc file in the same commit).

This guarantees the loop "edit screen-flow.yaml → reverse-reconcile re-flips it to
pending" never closes.

Path conventions:
- `tests/integration/test_doc_self_edit_no_cascade.py` is the spec path. The test
  lives under `.specify/scripts/tests/` (`make test` target) so CI exercises it.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# Path rules mirror the ones declared by `platforms/resenhai-expo/platform.yaml`.
# Kept inline so this test file does not depend on any specific manifest existing.
RESENHAI_PATH_RULES = [
    {"pattern": r"app/\(auth\)/(\w+)\.tsx", "screen_id_template": "{1}"},
    {"pattern": r"app/\(app\)/(\w+)\.tsx", "screen_id_template": "{1}"},
    {"pattern": r"app/\(app\)/(\w+)/(\w+)\.tsx", "screen_id_template": "{1}_{2}"},
]


# ── Helpers ────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_db(tmp_path):
    import db_core

    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    migrations_dir = Path(__file__).resolve().parents[3] / ".pipeline" / "migrations"
    db_core.migrate(conn, migrations_dir)
    conn.close()
    return db_file


def _seed_commit(db_file: Path, sha: str, message: str, files: list[str], platform: str = "resenhai"):
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO commits (sha, message, author, platform_id, source, committed_at, files_json) "
        "VALUES (?, ?, 'a', ?, 'external-fetch', '2026-01-01T00:00:00Z', ?)",
        (sha, message, platform, json.dumps(files)),
    )
    conn.commit()
    conn.close()


def _init_repo(tmp_path: Path, commits: list[tuple[str, dict[str, str]]]) -> Path:
    """Create a tiny git repo + bare origin so aggregate can resolve `origin/develop`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "develop", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    for msg, files in commits:
        for path, content in files.items():
            full = repo / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg, "--allow-empty"], cwd=repo, check=True)
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)
    return repo


# ── 1. Classify-level guarantees ───────────────────────────────────────────


def test_pure_screen_flow_yaml_edit_is_doc_self_edit():
    """Editing ONLY screen-flow.yaml is doc-self-edit (lives under business/)."""
    from reverse_reconcile_classify import _classify_commit

    layer, reason = _classify_commit(
        {
            "message": "docs(screen-flow): adjust hotspot coords",
            "files": ["platforms/resenhai/business/screen-flow.yaml"],
        }
    )
    assert layer == "doc-self-edit"
    assert "1 files" in reason or "platform doc" in reason


def test_multi_doc_layers_only_is_doc_self_edit():
    """A commit touching business + engineering + decisions + planning is still
    doc-self-edit — it never spawns code_items nor screen-flow patches."""
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit(
        {
            "message": "docs: refactor across layers",
            "files": [
                "platforms/resenhai/business/screen-flow.yaml",
                "platforms/resenhai/engineering/blueprint.md",
                "platforms/resenhai/decisions/ADR-027-screen-flow.md",
                "platforms/resenhai/planning/roadmap.md",
            ],
        }
    )
    assert layer == "doc-self-edit"


def test_mixed_doc_and_app_screen_is_code():
    """Doc + app screen mixed → classifier returns 'code' (code is the drift signal).

    The doc file lives at HEAD by definition, so it is excluded from code_items by
    the aggregate; ONLY the app file feeds path_rules → screen_flow patches.
    """
    from reverse_reconcile_classify import _classify_commit

    layer, _ = _classify_commit(
        {
            "message": "feat: rework login screen + docs",
            "files": [
                "platforms/resenhai/business/screen-flow.yaml",
                "app/(auth)/login.tsx",
            ],
        }
    )
    assert layer == "code"


# ── 2. End-to-end: classify → aggregate → no screen-flow patches ───────────


def test_pure_doc_commit_emits_no_screen_flow_patches(monkeypatch, tmp_path, fresh_db):
    """E2E: a commit touching only `business/screen-flow.yaml` is auto-reconciled
    via doc_self_edits AND emits ZERO entries in screen_flow_pending_patches."""
    from reverse_reconcile_classify import triage
    import reverse_reconcile_aggregate as agg

    _seed_commit(
        fresh_db,
        "deadbeef",
        "docs(screen-flow): tweak coords",
        ["platforms/resenhai/business/screen-flow.yaml"],
        platform="resenhai",
    )

    repo = _init_repo(tmp_path, [("seed", {"app/(auth)/login.tsx": "x\n"})])
    monkeypatch.setattr(agg.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(agg.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})
    monkeypatch.setattr(
        agg,
        "_load_platform_screen_flow",
        lambda _p: {"enabled": True, "capture": {"path_rules": RESENHAI_PATH_RULES}},
    )

    triage_payload = triage("resenhai", db_path=fresh_db)
    assert len(triage_payload["triage"]["doc_self_edits"]) == 1
    assert triage_payload["triage"]["doc_self_edits"][0]["sha"] == "deadbeef"
    # Code cluster is empty → no commit reaches _collect_screen_flow_patches
    assert triage_payload["triage"]["clusters"]["code"] == []

    result = agg.aggregate("resenhai", triage_payload)

    assert "deadbeef" in result["doc_self_edits"]["shas_to_auto_reconcile"]
    assert result["screen_flow_pending_patches"] == []
    assert result["code_items"] == []


def test_mixed_doc_and_app_commit_emits_patch_only_for_app_file(monkeypatch, tmp_path, fresh_db):
    """E2E: a single commit touching both `business/screen-flow.yaml` and
    `app/(auth)/login.tsx` produces ONE screen_flow patch (for `login`) and the
    code_item flows from the app file. The doc file does not generate a patch."""
    from reverse_reconcile_classify import triage
    import reverse_reconcile_aggregate as agg

    _seed_commit(
        fresh_db,
        "f00dbabe",
        "feat: rework login screen + docs",
        [
            "platforms/resenhai/business/screen-flow.yaml",
            "app/(auth)/login.tsx",
        ],
        platform="resenhai",
    )

    repo = _init_repo(tmp_path, [("seed", {"app/(auth)/login.tsx": "x\n"})])
    monkeypatch.setattr(agg.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(agg.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})
    monkeypatch.setattr(
        agg,
        "_load_platform_screen_flow",
        lambda _p: {"enabled": True, "capture": {"path_rules": RESENHAI_PATH_RULES}},
    )

    triage_payload = triage("resenhai", db_path=fresh_db)
    # Mixed commit goes to clusters['code'] and is NOT in doc_self_edits
    assert triage_payload["triage"]["clusters"]["code"] != []
    assert all(e["sha"] != "f00dbabe" for e in triage_payload["triage"]["doc_self_edits"])

    result = agg.aggregate("resenhai", triage_payload)

    # Exactly one patch, for the `login` screen
    assert len(result["screen_flow_pending_patches"]) == 1
    patch = result["screen_flow_pending_patches"][0]
    assert patch["screen_id"] == "login"
    assert patch["source_files"] == ["app/(auth)/login.tsx"]
    # The doc file did NOT pollute the source_files
    assert "platforms/resenhai/business/screen-flow.yaml" not in patch["source_files"]
    # And the doc file did NOT promote the commit into doc_self_edits
    assert "f00dbabe" not in result["doc_self_edits"]["shas_to_auto_reconcile"]
    # code_items contains the app file only — the doc file is excluded by _is_platform_owned
    assert len(result["code_items"]) == 1
    assert result["code_items"][0]["target_file"] == "app/(auth)/login.tsx"


def test_doc_self_edit_invariant_screen_flow_patches_only_drawn_from_clusters(monkeypatch, tmp_path, fresh_db):
    """Defensive: even if a doc commit is somehow injected directly into the
    triage clusters (regression scenario), the screen-flow path_rules will not
    match files under `platforms/<p>/.../*.md|.yaml` because the rules are
    scoped to app source paths. This locks the invariant from the OTHER side
    too — ensuring path_rule sets stay code-only."""
    import reverse_reconcile_aggregate as agg

    repo = _init_repo(tmp_path, [("seed", {"app/(auth)/login.tsx": "x\n"})])
    monkeypatch.setattr(agg.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(agg.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})
    monkeypatch.setattr(
        agg,
        "_load_platform_screen_flow",
        lambda _p: {"enabled": True, "capture": {"path_rules": RESENHAI_PATH_RULES}},
    )

    # Force a doc file into the code cluster (simulates a regression in classify).
    forced_triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {
                "business": [],
                "engineering": [],
                "decisions": [],
                "planning": [],
                "code": [
                    {
                        "sha": "abcd1234",
                        "message": "should not trigger",
                        "files": ["platforms/resenhai/business/screen-flow.yaml"],
                    }
                ],
            },
        }
    }
    result = agg.aggregate("resenhai", forced_triage)
    # Even with the regression, no screen-flow patch is emitted for the doc file
    # (path_rules are scoped to `app/...` and don't match `platforms/.../*.yaml`).
    assert result["screen_flow_pending_patches"] == []
