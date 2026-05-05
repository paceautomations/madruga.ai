"""Tests for `platform.yaml.screen_flow:` block lint integration.

Source task: T050 (epic 027-screen-flow-canvas Phase 5 / US3).

Covers FR-005..010 and FR-047:
- (a) `enabled: false` without `skip_reason` → BLOCKER (FR-006)
- (b) `enabled: false` with `capture` populated → BLOCKER (FR-006 — forbidden)
- (c) `enabled: true` without `capture.base_url` → BLOCKER (FR-007)
- (d) `enabled: true` without `capture.test_user_marker` → BLOCKER (FR-047)
- (e) `enabled: false` with `skip_reason` → passes
- (f) `enabled: true` with full capture config → passes

Also asserts that `platform_cli.py _lint_platform` rejects a platform.yaml with
invalid `screen_flow:` block (T051 integration).

Note on path: project convention puts pytest tests under .specify/scripts/tests/
(see pyproject.toml + Makefile `make test`). The plan/tasks reference
"tests/unit/" but the canonical pytest tree wins so `make test` picks them up.
"""

from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / ".specify" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import screen_flow_validator as sfv  # noqa: E402

# platform_cli.py shadows stdlib `platform` — load via importlib like other tests do.
_spec = importlib.util.spec_from_file_location("plat", SCRIPTS_DIR / "platform_cli.py")
plat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plat)


# ───────────────────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────────────────


def _valid_disabled_block() -> dict:
    return {
        "enabled": False,
        "skip_reason": (
            "Plataforma de tooling/orquestração — não tem app de usuário no sentido tradicional."
        ),
    }


def _valid_enabled_block() -> dict:
    return {
        "enabled": True,
        "capture": {
            "base_url": "https://dev.example.com",
            "device_profile": "iphone-15",
            "auth": {
                "type": "storage_state",
                "setup_command": "npx playwright test --project=auth-setup",
                "storage_state_path": "e2e/.auth/user.json",
                "test_user_env_prefix": "EXAMPLE",
            },
            "determinism": {
                "freeze_time": "2026-01-01T12:00:00Z",
                "random_seed": 42,
                "disable_animations": True,
                "clear_service_workers": True,
                "clear_cookies_between_screens": True,
                "mock_routes": [
                    {"match": "**/api/notifications/unread", "body": {"count": 0}}
                ],
            },
            "path_rules": [
                {"pattern": r"app/\(auth\)/(\w+)\.tsx", "screen_id_template": "{1}"},
            ],
            "test_user_marker": "demo+playwright@example.com",
        },
    }


def _blockers(findings: list[dict]) -> list[dict]:
    return [f for f in findings if f.get("severity") == "BLOCKER"]


# ───────────────────────────────────────────────────────────────────────────────
# (a) enabled: false without skip_reason → BLOCKER
# ───────────────────────────────────────────────────────────────────────────────


def test_disabled_without_skip_reason_is_blocker():
    block = {"enabled": False}
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "Expected BLOCKER when enabled=false has no skip_reason"
    assert any("skip_reason" in f.get("message", "") for f in _blockers(findings))


# ───────────────────────────────────────────────────────────────────────────────
# (b) enabled: false with capture populated → BLOCKER (forbidden)
# ───────────────────────────────────────────────────────────────────────────────


def test_disabled_with_capture_populated_is_blocker():
    block = _valid_disabled_block()
    block["capture"] = _valid_enabled_block()["capture"]
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "Expected BLOCKER when enabled=false has capture populated"


# ───────────────────────────────────────────────────────────────────────────────
# (c) enabled: true without capture.base_url → BLOCKER
# ───────────────────────────────────────────────────────────────────────────────


def test_enabled_missing_base_url_is_blocker():
    block = _valid_enabled_block()
    del block["capture"]["base_url"]
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "Expected BLOCKER when capture.base_url is missing"
    assert any("base_url" in f.get("message", "") for f in _blockers(findings))


# ───────────────────────────────────────────────────────────────────────────────
# (d) enabled: true without test_user_marker → BLOCKER (FR-047)
# ───────────────────────────────────────────────────────────────────────────────


def test_enabled_missing_test_user_marker_is_blocker():
    block = _valid_enabled_block()
    del block["capture"]["test_user_marker"]
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "Expected BLOCKER when capture.test_user_marker is missing"
    assert any("test_user_marker" in f.get("message", "") for f in _blockers(findings))


def test_enabled_missing_path_rules_is_blocker():
    block = _valid_enabled_block()
    del block["capture"]["path_rules"]
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "Expected BLOCKER when capture.path_rules is missing"


def test_enabled_missing_auth_is_blocker():
    block = _valid_enabled_block()
    del block["capture"]["auth"]
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "Expected BLOCKER when capture.auth is missing"


# ───────────────────────────────────────────────────────────────────────────────
# (e) enabled: false with skip_reason → passes
# ───────────────────────────────────────────────────────────────────────────────


def test_disabled_with_skip_reason_passes():
    block = _valid_disabled_block()
    findings = sfv.validate_platform_screen_flow_block(block)
    assert not _blockers(findings), f"Unexpected BLOCKERs for valid disabled block: {findings}"


# ───────────────────────────────────────────────────────────────────────────────
# (f) enabled: true with full capture config → passes
# ───────────────────────────────────────────────────────────────────────────────


def test_enabled_full_config_passes():
    block = _valid_enabled_block()
    findings = sfv.validate_platform_screen_flow_block(block)
    assert not _blockers(findings), f"Unexpected BLOCKERs for valid enabled block: {findings}"


# ───────────────────────────────────────────────────────────────────────────────
# Extra rejection paths covered by the schema
# ───────────────────────────────────────────────────────────────────────────────


def test_disabled_with_skip_reason_too_short_is_blocker():
    block = {"enabled": False, "skip_reason": "short"}  # < 10 chars
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "skip_reason shorter than 10 chars must be rejected"


def test_enabled_with_skip_reason_is_blocker():
    block = _valid_enabled_block()
    block["skip_reason"] = "Cannot have skip_reason when enabled is true."
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "skip_reason MUST be forbidden when enabled=true"


def test_invalid_path_rules_regex_is_blocker():
    """FR-010 — path_rules.pattern must compile as a Python regex."""
    block = _valid_enabled_block()
    block["capture"]["path_rules"] = [
        {"pattern": "app/[unclosed", "screen_id_template": "{1}"}
    ]
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "Invalid regex in path_rules.pattern must be rejected"
    assert any(
        "regex" in f.get("message", "").lower() or "pattern" in f.get("path", "")
        for f in _blockers(findings)
    )


def test_absent_block_returns_no_findings():
    """The screen_flow: block is opt-in — its absence MUST NOT produce findings."""
    findings = sfv.validate_platform_screen_flow_block(None)
    assert findings == []


def test_invalid_auth_type_is_blocker():
    block = _valid_enabled_block()
    block["capture"]["auth"]["type"] = "oauth"  # only `storage_state` is allowed
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "Unknown auth.type MUST be rejected"


def test_invalid_device_profile_is_blocker():
    block = _valid_enabled_block()
    block["capture"]["device_profile"] = "android-pixel-7"
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "Unknown device_profile MUST be rejected"


def test_test_user_env_prefix_must_be_uppercase():
    block = _valid_enabled_block()
    block["capture"]["auth"]["test_user_env_prefix"] = "lowercase"
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _blockers(findings), "test_user_env_prefix must match uppercase regex"


# ───────────────────────────────────────────────────────────────────────────────
# Integration with platform_cli.py _lint_platform (T051)
# ───────────────────────────────────────────────────────────────────────────────


def _make_platform_dir(base: Path, name: str, *, screen_flow_block: dict | None = None) -> Path:
    pdir = base / name
    pdir.mkdir(parents=True)
    manifest_lines = [
        f"name: {name}",
        "title: Test",
        "lifecycle: design",
    ]
    if screen_flow_block is not None:
        import yaml

        sf_yaml = yaml.safe_dump({"screen_flow": screen_flow_block}, sort_keys=False).rstrip()
        manifest_lines.append(sf_yaml)
    (pdir / "platform.yaml").write_text("\n".join(manifest_lines) + "\n")
    for d in ("business", "engineering", "decisions", "epics"):
        (pdir / d).mkdir()
    return pdir


def test_lint_platform_passes_with_valid_disabled_block(tmp_path, monkeypatch):
    monkeypatch.setattr(plat, "PLATFORMS_DIR", tmp_path)
    _make_platform_dir(tmp_path, "alpha", screen_flow_block=_valid_disabled_block())
    assert plat._lint_platform("alpha") is True


def test_lint_platform_passes_with_valid_enabled_block(tmp_path, monkeypatch):
    monkeypatch.setattr(plat, "PLATFORMS_DIR", tmp_path)
    _make_platform_dir(tmp_path, "beta", screen_flow_block=_valid_enabled_block())
    assert plat._lint_platform("beta") is True


def test_lint_platform_fails_with_disabled_no_skip_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(plat, "PLATFORMS_DIR", tmp_path)
    _make_platform_dir(tmp_path, "gamma", screen_flow_block={"enabled": False})
    assert plat._lint_platform("gamma") is False


def test_lint_platform_fails_with_enabled_no_test_user_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(plat, "PLATFORMS_DIR", tmp_path)
    block = _valid_enabled_block()
    del block["capture"]["test_user_marker"]
    _make_platform_dir(tmp_path, "delta", screen_flow_block=block)
    assert plat._lint_platform("delta") is False


def test_lint_platform_fails_with_disabled_capture_populated(tmp_path, monkeypatch):
    monkeypatch.setattr(plat, "PLATFORMS_DIR", tmp_path)
    block = _valid_disabled_block()
    block["capture"] = _valid_enabled_block()["capture"]
    _make_platform_dir(tmp_path, "epsilon", screen_flow_block=block)
    assert plat._lint_platform("epsilon") is False


def test_lint_platform_passes_when_block_absent(tmp_path, monkeypatch):
    """Absence of screen_flow: block MUST NOT cause lint to fail (FR-016 invariance)."""
    monkeypatch.setattr(plat, "PLATFORMS_DIR", tmp_path)
    _make_platform_dir(tmp_path, "zeta", screen_flow_block=None)
    assert plat._lint_platform("zeta") is True


# ───────────────────────────────────────────────────────────────────────────────
# Live platform.yaml files (T052/T053 integration)
# ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("platform_name", ["madruga-ai", "prosauai"])
def test_live_optout_platforms_pass_lint(platform_name):
    """Real platform.yaml files for opt-out platforms must pass lint with the
    screen_flow: block populated by T052 / T053."""
    import yaml

    p = REPO_ROOT / "platforms" / platform_name / "platform.yaml"
    if not p.exists():
        pytest.skip(f"{p} not present in this checkout")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    block = data.get("screen_flow")
    if block is None:
        pytest.skip(f"{platform_name} has not yet declared screen_flow:")
    findings = sfv.validate_platform_screen_flow_block(block)
    blockers = _blockers(findings)
    assert not blockers, f"{platform_name}: BLOCKERs in screen_flow block: {blockers}"
    assert block.get("enabled") is False, f"{platform_name}: expected enabled=false (opt-out)"
    assert block.get("skip_reason"), f"{platform_name}: skip_reason must be populated"


# ───────────────────────────────────────────────────────────────────────────────
# Sanity: deepcopy contract
# ───────────────────────────────────────────────────────────────────────────────


def test_validator_does_not_mutate_input_block():
    block = _valid_enabled_block()
    snapshot = deepcopy(block)
    sfv.validate_platform_screen_flow_block(block)
    assert block == snapshot, "validate_platform_screen_flow_block must not mutate input"
