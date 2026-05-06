"""Tests for screen_flow_validator.py — covers ≥30 rejection paths.

Source tasks: T040 (epic 027-screen-flow-canvas Phase 4 / US2).

Note on path: project convention puts pytest tests under .specify/scripts/tests/
(see pyproject.toml + Makefile `make test`). The plan/tasks reference
"tests/unit/" but the canonical pytest tree wins so `make test` picks them up.
"""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import screen_flow_validator as sfv  # noqa: E402


# ───────────────────────────────────────────────────────────────────────────────
# Fixtures: a minimal valid document we mutate per-test
# ───────────────────────────────────────────────────────────────────────────────


def _valid_doc() -> dict:
    return {
        "schema_version": 1,
        "meta": {"device": "mobile", "capture_profile": "iphone-15"},
        "screens": [
            {
                "id": "welcome",
                "title": "Welcome",
                "status": "pending",
                "body": [
                    {"type": "heading", "id": "title", "text": "Welcome"},
                    {"type": "button", "id": "go", "text": "Start", "testid": "btn-go"},
                ],
            },
            {
                "id": "home",
                "title": "Home",
                "status": "pending",
                "body": [{"type": "heading", "text": "Home"}],
            },
        ],
        "flows": [{"from": "welcome", "to": "home", "on": "go", "style": "success"}],
    }


def _normalize_path(p: str) -> str:
    """Normalize JSON-pointer path to canonical form for matching.

    The validator uses two path conventions:
    - JSON Schema (Draft202012Validator) emits dot-separated parts, e.g. ``flows.0.from``
    - Custom cross-field checks use Python indexing, e.g. ``flows[0].from``
    Tests compare via this normalizer so either notation matches.
    """
    return p.replace("[", ".").replace("]", "").replace("..", ".")


def _has_blocker_at(findings: list[dict], path_substring: str) -> bool:
    needle = _normalize_path(path_substring)
    return any(f["severity"] == "BLOCKER" and needle in _normalize_path(f["path"]) for f in findings)


def _no_blockers(findings: list[dict]) -> bool:
    return not any(f["severity"] == "BLOCKER" for f in findings)


# ───────────────────────────────────────────────────────────────────────────────
# Happy path
# ───────────────────────────────────────────────────────────────────────────────


def test_minimal_valid_document_has_no_blockers():
    findings = sfv.validate_screen_flow_dict(_valid_doc())
    assert _no_blockers(findings), findings


def test_validate_yaml_string_round_trip():
    import yaml

    text = yaml.safe_dump(_valid_doc())
    findings = sfv.validate_yaml_string(text)
    assert _no_blockers(findings), findings


# ───────────────────────────────────────────────────────────────────────────────
# FR-002 — schema_version
# ───────────────────────────────────────────────────────────────────────────────


def test_missing_schema_version_rejected():
    doc = _valid_doc()
    del doc["schema_version"]
    findings = sfv.validate_screen_flow_dict(doc)
    assert _has_blocker_at(findings, "schema_version")


def test_unknown_schema_version_rejected():
    doc = _valid_doc()
    doc["schema_version"] = 99
    findings = sfv.validate_screen_flow_dict(doc)
    assert _has_blocker_at(findings, "schema_version")
    assert any("Supported" in f["message"] for f in findings if f["severity"] == "BLOCKER")


def test_schema_version_string_rejected():
    doc = _valid_doc()
    doc["schema_version"] = "1"  # not int
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" for f in findings)


# ───────────────────────────────────────────────────────────────────────────────
# FR-003 — body.type vocabulary (closed enum of 10)
# ───────────────────────────────────────────────────────────────────────────────


def test_body_type_outside_vocabulary_rejected():
    doc = _valid_doc()
    doc["screens"][0]["body"][0]["type"] = "video"  # not in 10
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" and "screens.0.body.0" in f["path"] for f in findings)


def test_all_ten_body_types_accepted():
    doc = _valid_doc()
    doc["screens"][0]["body"] = [{"type": t, "id": f"id_{i}"} for i, t in enumerate(sorted(sfv.BODY_TYPES))]
    findings = sfv.validate_screen_flow_dict(doc)
    # Body types should not produce blockers; flow.on now points to a valid id_X
    doc["flows"][0]["on"] = "id_0"
    findings = sfv.validate_screen_flow_dict(doc)
    blockers = [f for f in findings if f["severity"] == "BLOCKER"]
    # Only allowed remaining blocker would be unrelated; with id_0 on flow it's clean.
    assert not blockers, blockers


def test_edge_style_outside_vocabulary_rejected():
    doc = _valid_doc()
    doc["flows"][0]["style"] = "warning"  # not in 4
    findings = sfv.validate_screen_flow_dict(doc)
    assert _has_blocker_at(findings, "flows.0.style")


def test_capture_state_outside_vocabulary_rejected():
    doc = _valid_doc()
    doc["screens"][0]["status"] = "in_progress"  # not in 3
    findings = sfv.validate_screen_flow_dict(doc)
    assert _has_blocker_at(findings, "screens.0.status")


# ───────────────────────────────────────────────────────────────────────────────
# FR-048 — id charset rules
# ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad_id",
    [
        "Login",  # uppercase
        "welcome-screen",  # hyphen
        "tela_início",  # unicode
        "1home",  # leading digit
        "WELCOME",  # all caps
        "home v2",  # space
        "home/v2",  # slash
        "x" * 65,  # too long
        "",  # empty
    ],
)
def test_screen_id_charset_rejects_invalid(bad_id):
    doc = _valid_doc()
    doc["screens"][0]["id"] = bad_id
    # Adjust flow.from to reference the bad id so jsonschema doesn't strip it earlier
    doc["flows"][0]["from"] = bad_id
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" for f in findings)


@pytest.mark.parametrize(
    "good_id",
    [
        "welcome",
        "login",
        "home",
        "auth_login",
        "screen_a",
        "a",  # single char
        "x_1_2_3",
        "x" * 64,  # max length
    ],
)
def test_screen_id_charset_accepts_valid(good_id):
    doc = _valid_doc()
    doc["screens"][0]["id"] = good_id
    doc["flows"][0]["from"] = good_id
    findings = sfv.validate_screen_flow_dict(doc)
    # No blocker pointing at screens.0.id
    assert not _has_blocker_at(findings, "screens.0.id")


def test_body_id_invalid_charset_rejected():
    doc = _valid_doc()
    doc["screens"][0]["body"][0]["id"] = "Bad-Id"
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" and "body" in f["path"] for f in findings)


def test_flow_on_invalid_charset_rejected():
    doc = _valid_doc()
    doc["flows"][0]["on"] = "Bad-Id"
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" for f in findings)


# ───────────────────────────────────────────────────────────────────────────────
# Cross-references: flow.from/to → screen.id; flow.on → body.id
# ───────────────────────────────────────────────────────────────────────────────


def test_flow_from_unknown_screen_rejected():
    doc = _valid_doc()
    doc["flows"][0]["from"] = "ghost"
    findings = sfv.validate_screen_flow_dict(doc)
    assert _has_blocker_at(findings, "flows.0.from")


def test_flow_to_unknown_screen_rejected():
    doc = _valid_doc()
    doc["flows"][0]["to"] = "ghost"
    findings = sfv.validate_screen_flow_dict(doc)
    assert _has_blocker_at(findings, "flows.0.to")


def test_flow_on_missing_body_rejected():
    doc = _valid_doc()
    doc["flows"][0]["on"] = "nonexistent"
    findings = sfv.validate_screen_flow_dict(doc)
    assert _has_blocker_at(findings, "flows.0.on")


# ───────────────────────────────────────────────────────────────────────────────
# Uniqueness
# ───────────────────────────────────────────────────────────────────────────────


def test_duplicate_screen_id_rejected():
    doc = _valid_doc()
    doc["screens"].append(deepcopy(doc["screens"][0]))  # duplicate "welcome"
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" and "Duplicate screen id" in f["message"] for f in findings)


def test_duplicate_body_id_rejected():
    doc = _valid_doc()
    doc["screens"][0]["body"].append({"type": "text", "id": "title", "text": "dup"})
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" and "Duplicate body.id" in f["message"] for f in findings)


# ───────────────────────────────────────────────────────────────────────────────
# FR-049 — scale limits
# ───────────────────────────────────────────────────────────────────────────────


def test_more_than_100_screens_hard_rejected():
    doc = _valid_doc()
    doc["screens"] = [
        {"id": f"s{i:03d}", "title": f"S{i}", "status": "pending", "body": [{"type": "heading"}]} for i in range(101)
    ]
    doc["flows"] = []
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" and "screens" == f["path"] for f in findings)


def test_warns_above_50_screens_but_passes():
    doc = _valid_doc()
    doc["screens"] = [
        {"id": f"s{i:03d}", "title": f"S{i}", "status": "pending", "body": [{"type": "heading"}]} for i in range(60)
    ]
    doc["flows"] = []
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "WARNING" and "soft limit" in f["message"] for f in findings)
    assert _no_blockers(findings)


def test_under_50_screens_no_warn_no_blocker():
    doc = _valid_doc()
    findings = sfv.validate_screen_flow_dict(doc)
    assert not any("soft limit" in f["message"] for f in findings)
    assert _no_blockers(findings)


def test_zero_screens_rejected():
    doc = _valid_doc()
    doc["screens"] = []
    doc["flows"] = []
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" for f in findings)


# ───────────────────────────────────────────────────────────────────────────────
# capture/failure consistency
# ───────────────────────────────────────────────────────────────────────────────


def test_status_captured_requires_image_and_capture():
    doc = _valid_doc()
    doc["screens"][0]["status"] = "captured"
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(f["severity"] == "BLOCKER" for f in findings)


def test_status_failed_requires_failure_block():
    doc = _valid_doc()
    doc["screens"][0]["status"] = "failed"
    findings = sfv.validate_screen_flow_dict(doc)
    assert _has_blocker_at(findings, "failure")


def test_status_failed_with_failure_passes():
    doc = _valid_doc()
    doc["screens"][0]["status"] = "failed"
    doc["screens"][0]["failure"] = {
        "reason": "timeout",
        "occurred_at": "2026-05-05T12:00:00Z",
        "retry_count": 3,
    }
    findings = sfv.validate_screen_flow_dict(doc)
    assert _no_blockers(findings)


# ───────────────────────────────────────────────────────────────────────────────
# capture_profile match between meta and screen.meta
# ───────────────────────────────────────────────────────────────────────────────


def test_screen_capture_profile_mismatch_rejected():
    doc = _valid_doc()
    doc["screens"][0]["meta"] = {"capture_profile": "desktop"}
    findings = sfv.validate_screen_flow_dict(doc)
    assert any(
        f["severity"] == "BLOCKER" and _normalize_path(f["path"]) == "screens.0.meta.capture_profile" for f in findings
    )


def test_screen_capture_profile_match_ok():
    doc = _valid_doc()
    doc["screens"][0]["meta"] = {"capture_profile": "iphone-15"}
    findings = sfv.validate_screen_flow_dict(doc)
    assert _no_blockers(findings)


# ───────────────────────────────────────────────────────────────────────────────
# Top-level YAML / parse errors
# ───────────────────────────────────────────────────────────────────────────────


def test_top_level_list_rejected():
    findings = sfv.validate_screen_flow_dict([1, 2, 3])
    assert any(f["severity"] == "BLOCKER" and f["path"] == "$" for f in findings)


def test_yaml_parse_error_returns_blocker():
    findings = sfv.validate_yaml_string("foo: bar:\n  - [unclosed")
    assert any(f["severity"] == "BLOCKER" for f in findings)


# ───────────────────────────────────────────────────────────────────────────────
# path_rules helper (validate_path_rules)
# ───────────────────────────────────────────────────────────────────────────────


def test_path_rules_invalid_regex_rejected():
    findings = sfv.validate_path_rules([{"pattern": "[unclosed", "screen_id_template": "x"}])
    assert any(f["severity"] == "BLOCKER" and "path_rules[0]" in f["path"] for f in findings)


def test_path_rules_valid_regex_passes():
    findings = sfv.validate_path_rules([{"pattern": r"app/\(auth\)/(\w+)\.tsx", "screen_id_template": "{1}"}])
    assert not findings


def test_path_rules_empty_list_ok():
    assert sfv.validate_path_rules([]) == []


# ───────────────────────────────────────────────────────────────────────────────
# platform.yaml.screen_flow block (helper for platform_cli.py lint)
# ───────────────────────────────────────────────────────────────────────────────


def test_platform_block_disabled_without_skip_reason_rejected():
    findings = sfv.validate_platform_screen_flow_block({"enabled": False})
    assert any(f["severity"] == "BLOCKER" for f in findings)


def test_platform_block_disabled_with_skip_reason_ok():
    findings = sfv.validate_platform_screen_flow_block(
        {"enabled": False, "skip_reason": "Tooling platform — no UI exposed to end-users."}
    )
    assert _no_blockers(findings)


def test_platform_block_enabled_without_capture_rejected():
    findings = sfv.validate_platform_screen_flow_block({"enabled": True})
    assert any(f["severity"] == "BLOCKER" for f in findings)


def test_platform_block_enabled_full_capture_ok():
    block = {
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
            "determinism": {"disable_animations": True},
            "path_rules": [{"pattern": r"app/(\w+)\.tsx", "screen_id_template": "{1}"}],
            "test_user_marker": "demo+playwright@example.com",
        },
    }
    findings = sfv.validate_platform_screen_flow_block(block)
    assert _no_blockers(findings), findings


def test_platform_block_path_rules_invalid_regex_rejected():
    block = {
        "enabled": True,
        "capture": {
            "base_url": "https://dev.example.com",
            "device_profile": "iphone-15",
            "auth": {
                "type": "storage_state",
                "setup_command": "x",
                "storage_state_path": "x",
                "test_user_env_prefix": "X",
            },
            "determinism": {},
            "path_rules": [{"pattern": "[unclosed", "screen_id_template": "x"}],
            "test_user_marker": "x@example.com",
        },
    }
    findings = sfv.validate_platform_screen_flow_block(block)
    assert any(f["severity"] == "BLOCKER" and "path_rules" in f["path"] for f in findings)


def test_platform_block_none_returns_no_findings():
    # screen_flow block absent — feature is opt-in
    assert sfv.validate_platform_screen_flow_block(None) == []


# ───────────────────────────────────────────────────────────────────────────────
# CLI / file-based entry points
# ───────────────────────────────────────────────────────────────────────────────


def test_validate_file_returns_zero_for_valid(tmp_path):
    import yaml

    p = tmp_path / "ok.yaml"
    p.write_text(yaml.safe_dump(_valid_doc()), encoding="utf-8")
    code, findings = sfv.validate_file(p)
    assert code == 0
    assert _no_blockers(findings)


def test_validate_file_returns_one_for_invalid(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("schema_version: 1\nmeta:\n  device: mobile\n", encoding="utf-8")
    code, findings = sfv.validate_file(p)
    assert code == 1
    assert any(f["severity"] == "BLOCKER" for f in findings)


def test_main_emits_json(tmp_path, capsys):
    import yaml

    p = tmp_path / "ok.yaml"
    p.write_text(yaml.safe_dump(_valid_doc()), encoding="utf-8")
    code = sfv.main([str(p), "--json"])
    out = capsys.readouterr().out
    import json

    payload = json.loads(out)
    assert payload["ok"] is True
    assert code == 0


def test_main_returns_one_on_blocker(tmp_path, capsys):
    p = tmp_path / "bad.yaml"
    p.write_text("schema_version: 99\nmeta: {}\nscreens: []\nflows: []\n", encoding="utf-8")
    code = sfv.main([str(p), "--json"])
    assert code == 1


def test_main_platform_block_mode(tmp_path, capsys):
    p = tmp_path / "platform.yaml"
    p.write_text(
        "name: x\nscreen_flow:\n  enabled: false\n  skip_reason: 'Tooling platform without end-user UI.'\n",
        encoding="utf-8",
    )
    code = sfv.main([str(p), "--platform-block", "--json"])
    assert code == 0


# ── Process improvement #1 — YAML 1.1 boolean collision detection ──────────


def test_yaml11_boolean_collision_detected():
    """Unquoted `on:` parses as Python `True` in YAML 1.1; validator emits an
    actionable hint pointing to the quoting fix (process improvement #1).
    """
    text = (
        "schema_version: 1\n"
        "meta: { device: mobile, capture_profile: iphone-15 }\n"
        "screens:\n"
        "  - id: a\n    title: A\n    status: pending\n"
        "    body: [{ type: button, id: x, text: X }]\n"
        "  - id: b\n    title: B\n    status: pending\n"
        "    body: [{ type: button, id: y, text: Y }]\n"
        "flows:\n"
        "  - { from: a, to: b, on: x, style: neutral }\n"
    )
    findings = sfv.validate_yaml_string(text)
    boolean_collision = [f for f in findings if "boolean" in f["message"].lower() or "True" in f["message"]]
    assert boolean_collision, "expected YAML 1.1 boolean collision finding"
    assert "flows.0" in boolean_collision[0]["path"]
    assert '"on":' in boolean_collision[0]["message"]


def test_yaml11_boolean_quoted_passes():
    """When `"on":` is quoted, the validator does not emit the boolean collision finding."""
    text = (
        "schema_version: 1\n"
        "meta: { device: mobile, capture_profile: iphone-15 }\n"
        "screens:\n"
        "  - id: a\n    title: A\n    status: pending\n"
        "    body: [{ type: button, id: x, text: X }]\n"
        "  - id: b\n    title: B\n    status: pending\n"
        "    body: [{ type: button, id: y, text: Y }]\n"
        "flows:\n"
        '  - { from: a, to: b, "on": x, style: neutral }\n'
    )
    findings = sfv.validate_yaml_string(text)
    boolean_collision = [f for f in findings if "boolean" in f["message"].lower()]
    assert not boolean_collision


# ── Process improvement #2 — testID source-of-truth validation ─────────────


def test_check_testids_against_source_warns_on_missing(tmp_path):
    """Body components referencing testIDs that do not exist in the bound repo
    source emit a WARNING (capture pipeline FR-028).
    """
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "Button.tsx").write_text('<Pressable testID="real-button" />')

    data = {
        "screens": [
            {
                "id": "a",
                "body": [
                    {"type": "button", "id": "x", "testid": "real-button"},
                    {"type": "button", "id": "y", "testid": "fictional-button"},
                ],
            },
        ],
    }
    findings = sfv.check_testids_against_source(data, source_root)
    assert len(findings) == 1
    assert findings[0]["severity"] == "WARNING"
    assert "fictional-button" in findings[0]["message"]
    assert findings[0]["path"] == "screens.0.body.1.testid"


def test_check_testids_returns_empty_when_source_missing(tmp_path):
    """Best-effort: missing source dir returns no findings (does not block)."""
    data = {"screens": [{"id": "a", "body": [{"type": "button", "testid": "x"}]}]}
    findings = sfv.check_testids_against_source(data, tmp_path / "does_not_exist")
    assert findings == []


def test_scan_source_testids_collects_unique(tmp_path):
    """scan_source_testids deduplicates and walks .tsx/.ts/.jsx/.js files."""
    (tmp_path / "a.tsx").write_text('testID="alpha" something testID="beta"')
    (tmp_path / "b.ts").write_text('testID="gamma"')
    (tmp_path / "c.txt").write_text('testID="ignored"')
    found = sfv.scan_source_testids(tmp_path)
    assert found == {"alpha", "beta", "gamma"}
