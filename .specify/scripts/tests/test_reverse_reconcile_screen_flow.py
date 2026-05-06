"""Tests for the screen-flow extension of reverse_reconcile_aggregate.py.

Covers FR-036 (path_rules → screen.id) + FR-039 (silent skip for opt-out platforms,
and unmatched files continue through the normal aggregate flow).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _init_repo(tmp_path: Path, commits: list[tuple[str, dict[str, str]]]) -> Path:
    """Create a git repo, apply commits sequentially, push to bare `origin`.

    Mirrors the helper in test_reverse_reconcile_aggregate.py — duplicated here to
    avoid cross-test imports (no `__init__.py` in the tests dir).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "develop", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    for msg, files in commits:
        for path, content in files.items():
            full = repo / path
            if content is None:
                full.unlink(missing_ok=True)
            else:
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(content)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg, "--allow-empty"], cwd=repo, check=True)
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)
    return repo


def _list_shas(repo: Path, ref: str) -> list[str]:
    out = subprocess.run(["git", "log", ref, "--format=%H", "--reverse"], cwd=repo, capture_output=True, text=True)
    return [s for s in out.stdout.splitlines() if s]


# Mirrors `platforms/resenhai/platform.yaml` screen_flow.capture.path_rules — kept
# inline so the tests are independent of the real platform manifest. The aggregate
# code is what consumes the rules at runtime.
RESENHAI_PATH_RULES = [
    {"pattern": r"app/\(auth\)/(\w+)\.tsx", "screen_id_template": "{1}"},
    {"pattern": r"app/\(app\)/(\w+)\.tsx", "screen_id_template": "{1}"},
    {"pattern": r"app/\(app\)/(\w+)/(\w+)\.tsx", "screen_id_template": "{1}_{2}"},
]


# ── Pure regex helpers (unit-level) ─────────────────────────────────────────


def test_resolve_screen_id_simple_capture():
    import reverse_reconcile_aggregate as mod

    sid = mod.resolve_screen_id_from_rules("app/(auth)/login.tsx", RESENHAI_PATH_RULES)
    assert sid == "login"


def test_resolve_screen_id_two_groups():
    import reverse_reconcile_aggregate as mod

    sid = mod.resolve_screen_id_from_rules("app/(app)/profile/settings.tsx", RESENHAI_PATH_RULES)
    assert sid == "profile_settings"


def test_resolve_screen_id_first_match_wins():
    """Rule order matters — single-segment app/(app)/X.tsx must match before the
    two-segment regex would, even if both technically COULD match."""
    import reverse_reconcile_aggregate as mod

    sid = mod.resolve_screen_id_from_rules("app/(app)/feed.tsx", RESENHAI_PATH_RULES)
    assert sid == "feed"


def test_resolve_screen_id_unmatched_returns_none():
    import reverse_reconcile_aggregate as mod

    sid = mod.resolve_screen_id_from_rules("src/lib/utils.ts", RESENHAI_PATH_RULES)
    assert sid is None


def test_resolve_screen_id_invalid_template_returns_none():
    """A template referencing a group that doesn't exist (`{2}` for a 1-group regex)
    is dropped silently — drift detection prefers a missed mapping over a corrupt id."""
    import reverse_reconcile_aggregate as mod

    bad_rules = [{"pattern": r"app/(\w+)\.tsx", "screen_id_template": "{1}_{2}"}]
    sid = mod.resolve_screen_id_from_rules("app/login.tsx", bad_rules)
    assert sid is None


def test_resolve_screen_id_template_must_yield_valid_id():
    """Templates that resolve to something that doesn't match the screen.id charset
    (FR-048) are rejected — better to emit no patch than a malformed YAML write."""
    import reverse_reconcile_aggregate as mod

    bad_rules = [{"pattern": r"app/([A-Z][a-zA-Z]+)\.tsx", "screen_id_template": "{1}"}]
    sid = mod.resolve_screen_id_from_rules("app/Login.tsx", bad_rules)
    assert sid is None


def test_resolve_screen_id_hyphen_slug_converted():
    """Hyphenated filenames are slug-converted to underscores so `[\\w-]+` rules
    can match Expo conventions (verify-otp.tsx, set-password.tsx) without each
    platform needing an explicit alias mapping. Process improvement #3 from the
    epic 027 retrospective.
    """
    import reverse_reconcile_aggregate as mod

    rules = [{"pattern": r"app/\(auth\)/([\w-]+)\.tsx", "screen_id_template": "{1}"}]

    assert mod.resolve_screen_id_from_rules("app/(auth)/welcome.tsx", rules) == "welcome"
    assert mod.resolve_screen_id_from_rules("app/(auth)/verify-otp.tsx", rules) == "verify_otp"
    assert mod.resolve_screen_id_from_rules("app/(auth)/set-password.tsx", rules) == "set_password"
    # Casing is preserved — uppercase remains a charset violation (returns None)
    assert mod.resolve_screen_id_from_rules("app/(auth)/Login.tsx", rules) is None


# ── Aggregate-level integration ─────────────────────────────────────────────


def _make_triage(shas: list[str], files: list[str]) -> dict:
    return {
        "triage": {
            "doc_self_edits": [],
            "clusters": {
                "code": [{"sha": sha, "message": f"feat: change {i}", "files": files} for i, sha in enumerate(shas)]
            },
        }
    }


def test_aggregate_reads_path_rules_and_emits_screen_flow_patches(monkeypatch, tmp_path):
    """When `screen_flow.enabled: true` and the platform has path_rules, an aggregate
    of a commit touching `app/(auth)/login.tsx` produces a screen_flow_pending entry."""
    import reverse_reconcile_aggregate as mod

    # Stub repo + binding

    repo = _init_repo(tmp_path, [("feat: edit login", {"app/(auth)/login.tsx": "x\n"})])
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})

    # Stub platform config loader
    monkeypatch.setattr(
        mod,
        "_load_platform_screen_flow",
        lambda _p: {"enabled": True, "capture": {"path_rules": RESENHAI_PATH_RULES}},
    )

    shas = _list_shas(repo, "develop")
    triage = _make_triage(shas, ["app/(auth)/login.tsx"])
    result = mod.aggregate("resenhai", triage)

    assert "screen_flow_pending_patches" in result
    patches = result["screen_flow_pending_patches"]
    assert len(patches) == 1
    p = patches[0]
    assert p["platform"] == "resenhai"
    assert p["screen_id"] == "login"
    assert p["source_files"] == ["app/(auth)/login.tsx"]
    assert p["sha_refs"] == shas


def test_aggregate_skips_silently_when_screen_flow_disabled(monkeypatch, tmp_path):
    """FR-039 — `screen_flow.enabled: false` ⇒ no patches emitted, nothing logged at error level."""
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("feat: edit login", {"app/(auth)/login.tsx": "x\n"})])
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})
    monkeypatch.setattr(
        mod,
        "_load_platform_screen_flow",
        lambda _p: {"enabled": False, "skip_reason": "headless platform"},
    )

    shas = _list_shas(repo, "develop")
    triage = _make_triage(shas, ["app/(auth)/login.tsx"])
    result = mod.aggregate("madruga-ai", triage)

    # No patches emitted — but key may still be present as []. Either is acceptable.
    patches = result.get("screen_flow_pending_patches", [])
    assert patches == []


def test_aggregate_skips_when_no_screen_flow_block(monkeypatch, tmp_path):
    """No `screen_flow:` key at all in platform.yaml ⇒ same behaviour as enabled=false."""
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("feat: edit auth", {"app/(auth)/welcome.tsx": "x\n"})])
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})
    monkeypatch.setattr(mod, "_load_platform_screen_flow", lambda _p: None)

    shas = _list_shas(repo, "develop")
    triage = _make_triage(shas, ["app/(auth)/welcome.tsx"])
    result = mod.aggregate("prosauai", triage)

    assert result.get("screen_flow_pending_patches", []) == []


def test_unmatched_file_follows_normal_flow(monkeypatch, tmp_path):
    """A file that doesn't match any path_rule does NOT emit a screen_flow patch
    AND continues to be aggregated as a normal code_item (FR-039 right-hand clause)."""
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(tmp_path, [("feat: shared util", {"src/lib/utils.ts": "x\n"})])
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})
    monkeypatch.setattr(
        mod,
        "_load_platform_screen_flow",
        lambda _p: {"enabled": True, "capture": {"path_rules": RESENHAI_PATH_RULES}},
    )

    shas = _list_shas(repo, "develop")
    triage = _make_triage(shas, ["src/lib/utils.ts"])
    result = mod.aggregate("resenhai", triage)

    # No screen_flow patch
    assert result.get("screen_flow_pending_patches", []) == []
    # And the file IS still in code_items, processed by the regular doc-mapping rules
    assert len(result["code_items"]) == 1
    assert result["code_items"][0]["target_file"] == "src/lib/utils.ts"


def test_aggregate_dedupes_repeated_screen_id_with_merged_sha_refs(monkeypatch, tmp_path):
    """Two commits both touching `app/(auth)/login.tsx` collapse to ONE patch with both SHAs."""
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(
        tmp_path,
        [
            ("feat: tweak login 1", {"app/(auth)/login.tsx": "v1\n"}),
            ("feat: tweak login 2", {"app/(auth)/login.tsx": "v2\n"}),
        ],
    )
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})
    monkeypatch.setattr(
        mod,
        "_load_platform_screen_flow",
        lambda _p: {"enabled": True, "capture": {"path_rules": RESENHAI_PATH_RULES}},
    )

    shas = _list_shas(repo, "develop")
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {
                "code": [
                    {"sha": shas[0], "message": "v1", "files": ["app/(auth)/login.tsx"]},
                    {"sha": shas[1], "message": "v2", "files": ["app/(auth)/login.tsx"]},
                ]
            },
        }
    }
    result = mod.aggregate("resenhai", triage)
    patches = result["screen_flow_pending_patches"]
    assert len(patches) == 1
    assert patches[0]["screen_id"] == "login"
    assert sorted(patches[0]["sha_refs"]) == sorted(shas)


def test_aggregate_emits_patch_per_distinct_screen(monkeypatch, tmp_path):
    """One commit touching two different screens → two distinct patches."""
    import reverse_reconcile_aggregate as mod

    repo = _init_repo(
        tmp_path,
        [
            (
                "feat: refactor auth",
                {
                    "app/(auth)/login.tsx": "x\n",
                    "app/(auth)/signup.tsx": "y\n",
                },
            )
        ],
    )
    monkeypatch.setattr(mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"})
    monkeypatch.setattr(
        mod,
        "_load_platform_screen_flow",
        lambda _p: {"enabled": True, "capture": {"path_rules": RESENHAI_PATH_RULES}},
    )

    shas = _list_shas(repo, "develop")
    triage = _make_triage(shas, ["app/(auth)/login.tsx", "app/(auth)/signup.tsx"])
    result = mod.aggregate("resenhai", triage)

    patches = result["screen_flow_pending_patches"]
    sids = sorted(p["screen_id"] for p in patches)
    assert sids == ["login", "signup"]


# ── End-to-end with the real `_load_platform_screen_flow` reading platform.yaml ─


def test_load_platform_screen_flow_real_yaml(tmp_path, monkeypatch):
    """`_load_platform_screen_flow` reads platforms/<p>/platform.yaml.screen_flow."""
    import reverse_reconcile_aggregate as mod

    fake_platforms = tmp_path / "platforms" / "fakeplat"
    fake_platforms.mkdir(parents=True)
    (fake_platforms / "platform.yaml").write_text(
        """\
name: fakeplat
screen_flow:
  enabled: true
  capture:
    path_rules:
      - pattern: 'src/(\\w+)\\.tsx'
        screen_id_template: '{1}'
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    block = mod._load_platform_screen_flow("fakeplat")
    assert block is not None
    assert block["enabled"] is True
    assert block["capture"]["path_rules"][0]["pattern"] == r"src/(\w+)\.tsx"


def test_load_platform_screen_flow_missing_returns_none(tmp_path, monkeypatch):
    import reverse_reconcile_aggregate as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    assert mod._load_platform_screen_flow("does-not-exist") is None


def test_load_platform_screen_flow_no_block_returns_none(tmp_path, monkeypatch):
    import reverse_reconcile_aggregate as mod

    fake_platforms = tmp_path / "platforms" / "noscreen"
    fake_platforms.mkdir(parents=True)
    (fake_platforms / "platform.yaml").write_text("name: noscreen\n", encoding="utf-8")
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    assert mod._load_platform_screen_flow("noscreen") is None
