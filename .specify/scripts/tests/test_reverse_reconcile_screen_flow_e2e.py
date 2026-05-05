"""End-to-end validation of the screen-flow drift loop (T094).

Wires together what T090–T093 built:

    fake repo with commit on `app/(auth)/login.tsx`
        → reverse_reconcile_aggregate (CLI)
        → screen_flow_pending_patches in JSON output
        → screen_flow_mark_pending (CLI per patch)
        → screen-flow.yaml on disk has `status: pending` for screen `login`

This is the live invariant guarding the SC-011 success criterion: "commit em
app/(auth)/login.tsx faz screens[id=login].status virar pending no próximo
reverse-reconcile". If this test breaks, the drift loop is broken.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


SAMPLE_SCREEN_FLOW_YAML = """\
# E2E fixture for T094 — drift loop validation.
schema_version: 1
meta:
  device: mobile
  capture_profile: iphone-15
screens:
  - id: login
    title: "Login"
    status: captured
    image: business/shots/login.png
    capture:
      captured_at: "2026-05-05T10:00:00Z"
      app_version: "abc123"
    body:
      - type: heading
        text: "Entrar"
      - type: input
        id: email
        text: "E-mail"
      - type: button
        id: submit
        testid: "auth.login.submit"

  - id: home
    title: "Home"
    status: captured
    image: business/shots/home.png
    capture:
      captured_at: "2026-05-05T10:01:00Z"
      app_version: "abc123"
    body:
      - type: heading
        text: "Bem-vindo"

flows:
  - from: login
    to: home
    on: submit
    style: success
"""


PATH_RULES = [
    {"pattern": r"app/\(auth\)/(\w+)\.tsx", "screen_id_template": "{1}"},
]


def _init_repo_with_commit(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "develop", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "app" / "(auth)").mkdir(parents=True)
    (repo / "app" / "(auth)" / "login.tsx").write_text("export default function Login() {}\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "feat: edit login screen"], cwd=repo, check=True)
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(repo), str(bare)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=repo, check=True)
    subprocess.run(["git", "fetch", "-q", "origin"], cwd=repo, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "develop"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    return repo, sha


@pytest.mark.slow
def test_e2e_drift_loop_login_screen_flips_to_pending(tmp_path, monkeypatch):
    """Full drift loop: commit on app/(auth)/login.tsx → mark_pending writes status=pending."""
    import reverse_reconcile_aggregate as agg_mod
    import screen_flow_mark_pending as mark_mod

    # 1. Build a fake repo with the trigger commit
    repo, sha = _init_repo_with_commit(tmp_path)

    # 2. Stage a fake REPO_ROOT that contains:
    #    - platforms/testplat/platform.yaml with screen_flow.enabled=true + path_rules
    #    - platforms/testplat/business/screen-flow.yaml with screen 'login' captured
    fake_root = tmp_path / "fake_repo_root"
    plat_dir = fake_root / "platforms" / "testplat"
    biz_dir = plat_dir / "business"
    biz_dir.mkdir(parents=True)

    (plat_dir / "platform.yaml").write_text(
        f"""\
name: testplat
screen_flow:
  enabled: true
  capture:
    path_rules:
{chr(10).join(f"      - pattern: '{r['pattern']}'\n        screen_id_template: '{r['screen_id_template']}'" for r in PATH_RULES)}
""",
        encoding="utf-8",
    )
    yaml_path = biz_dir / "screen-flow.yaml"
    yaml_path.write_text(SAMPLE_SCREEN_FLOW_YAML, encoding="utf-8")

    # 3. Patch REPO_ROOT in both modules + the binding/repo lookup in aggregate
    monkeypatch.setattr(agg_mod, "REPO_ROOT", fake_root)
    monkeypatch.setattr(mark_mod, "REPO_ROOT", fake_root)
    monkeypatch.setattr(agg_mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(
        agg_mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"}
    )

    # 4. Build the triage that classify would emit (we feed the aggregate CLI directly).
    triage = {
        "triage": {
            "doc_self_edits": [],
            "clusters": {
                "code": [
                    {
                        "sha": sha,
                        "message": "feat: edit login screen",
                        "files": ["app/(auth)/login.tsx"],
                    }
                ]
            },
        }
    }

    # 5. Run aggregate → assert screen_flow patches present
    result = agg_mod.aggregate("testplat", triage)
    patches = result["screen_flow_pending_patches"]
    assert len(patches) == 1
    patch = patches[0]
    assert patch["screen_id"] == "login"
    assert patch["platform"] == "testplat"
    assert sha in patch["sha_refs"]
    assert "app/(auth)/login.tsx" in patch["source_files"]

    # 6. Pre-condition: login is `captured`, home is `captured` too
    pre = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    statuses_pre = {s["id"]: s["status"] for s in pre["screens"]}
    assert statuses_pre == {"login": "captured", "home": "captured"}

    # 7. Apply the mark_pending patch
    rc = mark_mod.mark_pending(patch["platform"], patch["screen_id"])
    assert rc == 0

    # 8. Post-condition: login is now `pending`, home untouched
    post = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    statuses_post = {s["id"]: s["status"] for s in post["screens"]}
    assert statuses_post == {"login": "pending", "home": "captured"}, (
        "drift loop did not flip login to pending"
    )

    # 9. Comments preserved across the round-trip
    final_text = yaml_path.read_text(encoding="utf-8")
    assert "# E2E fixture for T094 — drift loop validation." in final_text


@pytest.mark.slow
def test_e2e_aggregate_cli_emits_screen_flow_patches_in_json(tmp_path, monkeypatch):
    """The aggregate CLI (--out file.json) MUST include screen_flow_pending_patches."""
    import reverse_reconcile_aggregate as agg_mod

    repo, sha = _init_repo_with_commit(tmp_path)

    fake_root = tmp_path / "fake_repo_root"
    (fake_root / "platforms" / "testplat").mkdir(parents=True)
    (fake_root / "platforms" / "testplat" / "platform.yaml").write_text(
        f"""\
name: testplat
screen_flow:
  enabled: true
  capture:
    path_rules:
      - pattern: '{PATH_RULES[0]['pattern']}'
        screen_id_template: '{PATH_RULES[0]['screen_id_template']}'
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(agg_mod, "REPO_ROOT", fake_root)
    monkeypatch.setattr(agg_mod.ensure_repo_mod, "ensure_repo", lambda _p: repo)
    monkeypatch.setattr(
        agg_mod.ensure_repo_mod, "load_repo_binding", lambda _p: {"base_branch": "develop"}
    )

    triage_path = tmp_path / "triage.json"
    triage_path.write_text(
        json.dumps(
            {
                "triage": {
                    "doc_self_edits": [],
                    "clusters": {
                        "code": [
                            {
                                "sha": sha,
                                "message": "feat: edit login",
                                "files": ["app/(auth)/login.tsx"],
                            }
                        ]
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    out_path = tmp_path / "work.json"
    rc = agg_mod.main(
        ["--platform", "testplat", "--triage", str(triage_path), "--out", str(out_path)]
    )
    assert rc == 0

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "screen_flow_pending_patches" in payload
    assert payload["summary"]["screen_flow_pending_patches"] == 1
    assert payload["screen_flow_pending_patches"][0]["screen_id"] == "login"
