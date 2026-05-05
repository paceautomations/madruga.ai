"""Tests for screen_flow_mark_pending.py — drift transition `captured → pending`.

Covers FR-037 (only modify `screens[id=X].status`, preserve order + comments) +
fallback behaviour when ruamel.yaml is unavailable (uses regex line-based path).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


# Sample YAML with comments + various screen states (3 captured, 1 pending, 1 failed).
# `additionalProperties: false` is enforced at schema level — fixture omits status-gated
# fields (image / capture / failure) on screens that should NOT be touched, to avoid
# leaking schema noise into the round-trip assertion.
SAMPLE_YAML = """\
# Top-level comment — must survive round-trip.
schema_version: 1

meta:
  device: mobile
  capture_profile: iphone-15

# Screens block — order matters (build order).
screens:
  # First screen: captured login.
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
        # Inline comment on a body item.
      - type: button
        id: submit
        testid: "auth.login.submit"

  # Second screen: still pending — should NOT be touched.
  - id: home
    title: "Home"
    status: pending
    body:
      - type: heading
        text: "Bem-vindo"

  # Third screen: failed.
  - id: profile
    title: "Profile"
    status: failed
    failure:
      reason: timeout
      occurred_at: "2026-05-05T10:05:00Z"
      retry_count: 3
    body:
      - type: heading
        text: "Perfil"

flows:
  - from: login
    to: home
    on: submit
    style: success
    label: "Entrar"
"""


@pytest.fixture
def sample_yaml_path(tmp_path):
    """Write SAMPLE_YAML to a temp file mimicking platforms/<p>/business/screen-flow.yaml."""
    p = tmp_path / "platforms" / "testplat" / "business" / "screen-flow.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    return p


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _find_screen(data: dict, screen_id: str) -> dict | None:
    for s in data.get("screens", []):
        if s.get("id") == screen_id:
            return s
    return None


# ── Core behaviour ───────────────────────────────────────────────────────────


def test_mark_pending_changes_only_target_screen_status(sample_yaml_path, monkeypatch, tmp_path):
    """Only `screens[id=login].status` flips captured → pending. Other screens untouched."""
    import screen_flow_mark_pending as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    rc = mod.mark_pending("testplat", "login")
    assert rc == 0

    data = _load(sample_yaml_path)
    assert _find_screen(data, "login")["status"] == "pending"
    # Untouched screens
    assert _find_screen(data, "home")["status"] == "pending"
    assert _find_screen(data, "profile")["status"] == "failed"


def test_mark_pending_preserves_comments_and_order(sample_yaml_path, monkeypatch, tmp_path):
    """Round-trip preserves top-level comments, screen comments, and inline comments.

    With ruamel.yaml installed: full round-trip preservation. With pyyaml fallback:
    line-based modification means ALL non-target lines are byte-identical.
    """
    import screen_flow_mark_pending as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    original = sample_yaml_path.read_text(encoding="utf-8")
    mod.mark_pending("testplat", "login")
    after = sample_yaml_path.read_text(encoding="utf-8")

    # Comments survive
    assert "# Top-level comment — must survive round-trip." in after
    assert "# Screens block — order matters (build order)." in after
    assert "# First screen: captured login." in after
    assert "# Second screen: still pending — should NOT be touched." in after
    assert "# Third screen: failed." in after
    assert "# Inline comment on a body item." in after

    # Screen order preserved (login → home → profile)
    login_idx = after.index("id: login")
    home_idx = after.index("id: home")
    profile_idx = after.index("id: profile")
    assert login_idx < home_idx < profile_idx

    # Diff is minimal: a single line changed (the captured → pending replacement).
    orig_lines = original.splitlines()
    new_lines = after.splitlines()
    assert len(orig_lines) == len(new_lines)
    diffs = [(i, o, n) for i, (o, n) in enumerate(zip(orig_lines, new_lines)) if o != n]
    assert len(diffs) == 1
    _, old_line, new_line = diffs[0]
    assert "status: captured" in old_line
    assert "status: pending" in new_line


def test_mark_pending_idempotent_when_already_pending(sample_yaml_path, monkeypatch, tmp_path):
    """If the target screen is already `pending`, nothing changes — script returns 0 silently."""
    import screen_flow_mark_pending as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    before = sample_yaml_path.read_text(encoding="utf-8")
    rc = mod.mark_pending("testplat", "home")  # home is already pending
    assert rc == 0

    after = sample_yaml_path.read_text(encoding="utf-8")
    assert before == after


def test_mark_pending_promotes_failed_to_pending(sample_yaml_path, monkeypatch, tmp_path):
    """status=failed is also a valid drift transition into pending (state machine E2)."""
    import screen_flow_mark_pending as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    rc = mod.mark_pending("testplat", "profile")
    assert rc == 0

    data = _load(sample_yaml_path)
    assert _find_screen(data, "profile")["status"] == "pending"


def test_mark_pending_unknown_screen_id_returns_nonzero(sample_yaml_path, monkeypatch, tmp_path):
    """Asking to mark a screen that doesn't exist is a hard error (exit 1)."""
    import screen_flow_mark_pending as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    rc = mod.mark_pending("testplat", "nonexistent_screen")
    assert rc == 1
    # File must not be modified
    data = _load(sample_yaml_path)
    assert _find_screen(data, "login")["status"] == "captured"


def test_mark_pending_missing_yaml_returns_nonzero(tmp_path, monkeypatch):
    """If `business/screen-flow.yaml` is absent, exit 1 with a clear message."""
    import screen_flow_mark_pending as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    (tmp_path / "platforms" / "testplat" / "business").mkdir(parents=True)

    rc = mod.mark_pending("testplat", "login")
    assert rc == 1


# ── CLI entry point ──────────────────────────────────────────────────────────


def test_cli_invocation_round_trip(sample_yaml_path, monkeypatch, tmp_path):
    """Running the script via main(['--platform', ..., '--screen-id', ...]) flips status."""
    import screen_flow_mark_pending as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)

    rc = mod.main(["--platform", "testplat", "--screen-id", "login"])
    assert rc == 0

    data = _load(sample_yaml_path)
    assert _find_screen(data, "login")["status"] == "pending"


# ── Regex-fallback regressions (no ruamel.yaml) ─────────────────────────────


def test_handles_quoted_status_value(tmp_path, monkeypatch):
    """`status: "captured"` (double-quoted) is still flipped — line-based fallback handles it."""
    import screen_flow_mark_pending as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    p = tmp_path / "platforms" / "testplat" / "business" / "screen-flow.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(
        """\
schema_version: 1
meta:
  device: mobile
  capture_profile: iphone-15
screens:
  - id: login
    title: "Login"
    status: "captured"
    image: business/shots/login.png
    capture:
      captured_at: "2026-05-05T10:00:00Z"
      app_version: "abc"
    body:
      - type: heading
        text: "Login"
flows: []
""",
        encoding="utf-8",
    )

    rc = mod.mark_pending("testplat", "login")
    assert rc == 0
    data = _load(p)
    assert _find_screen(data, "login")["status"] == "pending"


def test_does_not_touch_status_inside_capture_block(tmp_path, monkeypatch):
    """A `status:` key nested inside `capture:` (or other sub-blocks) MUST NOT be modified.

    Regression guard for the line-based fallback: it must scope its search to the screen
    record's top-level `status:` key, not any nested key with the same name.
    """
    import screen_flow_mark_pending as mod

    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path)
    p = tmp_path / "platforms" / "testplat" / "business" / "screen-flow.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(
        """\
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
      app_version: "abc"
      # A sentinel comment that should NOT migrate.
      meta_status: noise_should_stay
    body:
      - type: heading
        text: "Login"
        # body-level field that shouldn't be touched
        nested:
          status: keep_me
flows: []
""",
        encoding="utf-8",
    )

    rc = mod.mark_pending("testplat", "login")
    assert rc == 0
    text = p.read_text(encoding="utf-8")
    assert "meta_status: noise_should_stay" in text
    assert "status: keep_me" in text
    data = _load(p)
    assert _find_screen(data, "login")["status"] == "pending"
