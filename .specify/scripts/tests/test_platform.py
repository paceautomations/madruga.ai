"""Tests for platform_cli.py functions."""

import importlib
import logging
import re
import sys
from pathlib import Path

# Add scripts dir to path so we can import platform_cli.py as a module
_scripts_dir = str(Path(__file__).parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# Import as 'plat' to avoid collision with stdlib 'platform'
import importlib.util

_spec = importlib.util.spec_from_file_location("plat", Path(__file__).parent.parent / "platform_cli.py")
plat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plat)


def _create_platform(base_dir: Path, name: str, yaml_content: str = "") -> Path:
    """Helper to create a minimal platform directory."""
    pdir = base_dir / name
    pdir.mkdir(parents=True)
    content = yaml_content or f"name: {name}\ntitle: Test\nlifecycle: design\n"
    (pdir / "platform.yaml").write_text(content)
    return pdir


def test_discover_platforms_empty(tmp_path):
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path
    try:
        assert plat._discover_platforms() == []
    finally:
        plat.PLATFORMS_DIR = old


def test_discover_platforms_finds(tmp_path):
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path
    plat._discover_platforms.cache_clear()

    _create_platform(tmp_path, "alpha")
    _create_platform(tmp_path, "beta")
    (tmp_path / "not-a-platform").mkdir()  # no platform.yaml

    try:
        result = plat._discover_platforms()
        assert result == ["alpha", "beta"]
    finally:
        plat.PLATFORMS_DIR = old
        plat._discover_platforms.cache_clear()


def test_lint_platform_valid(tmp_path, capsys):
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    pdir = _create_platform(tmp_path, "test-plat")
    for d in ["business", "engineering", "decisions", "epics"]:
        (pdir / d).mkdir()
    for f in [
        "business/vision.md",
        "business/solution-overview.md",
        "engineering/domain-model.md",
        "engineering/integrations.md",
        "engineering/blueprint.md",
    ]:
        (pdir / f).write_text("placeholder")

    try:
        result = plat._lint_platform("test-plat")
        assert result is True
    finally:
        plat.PLATFORMS_DIR = old


def test_lint_platform_missing_yaml(tmp_path, capsys):
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    (tmp_path / "bad-plat").mkdir()

    try:
        result = plat._lint_platform("bad-plat")
        assert result is False
    finally:
        plat.PLATFORMS_DIR = old


def test_name_validation_regex():
    """Kebab-case validation regex from cmd_new."""
    pattern = r"^[a-z][a-z0-9-]*$"
    assert re.match(pattern, "my-saas")
    assert re.match(pattern, "prosauai")
    assert re.match(pattern, "a123-test")
    assert not re.match(pattern, "My SaaS")
    assert not re.match(pattern, "123abc")
    assert not re.match(pattern, "UPPER")
    assert not re.match(pattern, "-starts-dash")
    assert not re.match(pattern, "has_underscore")


# ══════════════════════════════════════
# Active platform (use/current) tests
# ══════════════════════════════════════


def test_cmd_use_sets_active(tmp_path, caplog):
    """cmd_use sets active_platform in DB."""
    old_platforms = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path
    plat._discover_platforms.cache_clear()

    _create_platform(tmp_path, "alpha")

    # Patch DB to use temp — patch db_core where DB_PATH is defined
    from db import get_conn, migrate, get_active_platform
    import db_core

    db_path = tmp_path / "test.db"
    old_db = db_core.DB_PATH
    db_core.DB_PATH = db_path

    try:
        with get_conn(db_path) as conn:
            migrate(conn)

        with caplog.at_level(logging.INFO, logger="platform_cli"):
            plat.cmd_use("alpha")
        assert "Active platform set to: alpha" in caplog.text

        with get_conn(db_path) as conn:
            assert get_active_platform(conn) == "alpha"
    finally:
        plat.PLATFORMS_DIR = old_platforms
        db_core.DB_PATH = old_db
        plat._discover_platforms.cache_clear()


def test_cmd_use_invalid_platform(tmp_path):
    """cmd_use exits with error for non-existent platform."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    import pytest

    try:
        with pytest.raises(SystemExit) as exc_info:
            plat.cmd_use("nonexistent")
        assert exc_info.value.code == 1
    finally:
        plat.PLATFORMS_DIR = old


def test_cmd_current_when_set(tmp_path, capsys):
    """cmd_current shows the active platform."""
    from db import get_conn, migrate, set_local_config
    import db_core

    db_path = tmp_path / "test.db"
    old_db = db_core.DB_PATH
    db_core.DB_PATH = db_path

    try:
        with get_conn(db_path) as conn:
            migrate(conn)
            set_local_config(conn, "active_platform", "prosauai")

        plat.cmd_current()
        captured = capsys.readouterr()
        assert "Active platform: prosauai" in captured.out
    finally:
        db_core.DB_PATH = old_db


def test_cmd_current_when_unset(tmp_path, capsys):
    """cmd_current shows message when no active platform."""
    from db import get_conn, migrate
    import db_core

    db_path = tmp_path / "test.db"
    old_db = db_core.DB_PATH
    db_core.DB_PATH = db_path

    try:
        with get_conn(db_path) as conn:
            migrate(conn)

        plat.cmd_current()
        captured = capsys.readouterr()
        assert "No active platform set" in captured.out
    finally:
        db_core.DB_PATH = old_db


# ══════════════════════════════════════
# _check_frontmatter tests
# ══════════════════════════════════════


def test_check_frontmatter_valid(tmp_path, caplog):
    """Valid frontmatter with all required fields."""
    f = tmp_path / "ADR-001.md"
    f.write_text(
        "---\ntitle: Test\nstatus: accepted\ndecision: Use X\nalternatives: [A, B]\nrationale: Because\n---\n\nBody"
    )
    with caplog.at_level(logging.INFO):
        plat._check_frontmatter(f, plat.ADR_REQUIRED_FIELDS, "ADR")
    assert "frontmatter valid" in caplog.text


def test_check_frontmatter_missing_fields(tmp_path, caplog):
    """Frontmatter missing required fields logs warning."""
    f = tmp_path / "ADR-002.md"
    f.write_text("---\ntitle: Test\n---\n\nBody")
    with caplog.at_level(logging.WARNING):
        plat._check_frontmatter(f, plat.ADR_REQUIRED_FIELDS, "ADR")
    assert "missing fields" in caplog.text


def test_check_frontmatter_no_frontmatter(tmp_path, caplog):
    """File without frontmatter logs warning."""
    f = tmp_path / "ADR-003.md"
    f.write_text("# No frontmatter here")
    with caplog.at_level(logging.WARNING):
        plat._check_frontmatter(f, plat.ADR_REQUIRED_FIELDS, "ADR")
    assert "no frontmatter" in caplog.text


def test_check_frontmatter_malformed(tmp_path, caplog):
    """Malformed frontmatter (no closing ---) logs warning."""
    f = tmp_path / "ADR-004.md"
    f.write_text("---\ntitle: Test\nno closing delimiter")
    with caplog.at_level(logging.WARNING):
        plat._check_frontmatter(f, plat.ADR_REQUIRED_FIELDS, "ADR")
    assert "malformed" in caplog.text


def test_check_frontmatter_empty(tmp_path, caplog):
    """Empty frontmatter logs warning."""
    f = tmp_path / "ADR-005.md"
    f.write_text("---\n\n---\n\nBody")
    with caplog.at_level(logging.WARNING):
        plat._check_frontmatter(f, plat.ADR_REQUIRED_FIELDS, "ADR")
    assert "empty frontmatter" in caplog.text


# ══════════════════════════════════════
# cmd_new tests
# ══════════════════════════════════════


def test_cmd_new_invalid_name():
    """cmd_new rejects invalid platform names."""
    import pytest

    with pytest.raises(SystemExit):
        plat.cmd_new("Invalid Name")


def test_cmd_new_existing_platform(tmp_path):
    """cmd_new rejects existing platform."""
    import pytest

    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path
    (tmp_path / "my-plat").mkdir()

    try:
        with pytest.raises(SystemExit):
            plat.cmd_new("my-plat")
    finally:
        plat.PLATFORMS_DIR = old


# ══════════════════════════════════════
# cmd_lint tests
# ══════════════════════════════════════


def test_cmd_lint_no_name_or_all():
    """cmd_lint exits when neither name nor --all provided."""
    import pytest

    with pytest.raises(SystemExit):
        plat.cmd_lint(None, lint_all=False)


def test_cmd_lint_single_platform(tmp_path):
    """cmd_lint for a single valid platform."""
    import pytest

    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    pdir = _create_platform(tmp_path, "test-plat")
    for d in ["business", "engineering", "decisions", "epics"]:
        (pdir / d).mkdir()

    try:
        # Should exit 0 (success)
        with pytest.raises(SystemExit) as exc_info:
            plat.cmd_lint("test-plat")
        assert exc_info.value.code == 0
    finally:
        plat.PLATFORMS_DIR = old


# ══════════════════════════════════════
# cmd_sync tests
# ══════════════════════════════════════


def test_cmd_sync_skips_without_copier_answers(tmp_path, caplog):
    """cmd_sync skips platforms without .copier-answers.yml."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path
    plat._discover_platforms.cache_clear()

    _create_platform(tmp_path, "my-plat")

    try:
        with caplog.at_level(logging.WARNING):
            plat.cmd_sync("my-plat")
        assert "skipping" in caplog.text
    finally:
        plat.PLATFORMS_DIR = old
        plat._discover_platforms.cache_clear()


# ══════════════════════════════════════
# cmd_register tests
# ══════════════════════════════════════


def test_cmd_register_nonexistent_exits(tmp_path):
    """cmd_register exits for non-existent platform."""
    import pytest

    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    try:
        with pytest.raises(SystemExit):
            plat.cmd_register("nonexistent")
    finally:
        plat.PLATFORMS_DIR = old


def test_cmd_register_valid(tmp_path, caplog, monkeypatch):
    """cmd_register succeeds for existing platform."""
    monkeypatch.setattr(plat, "PLATFORMS_DIR", tmp_path)
    monkeypatch.setattr(plat, "PORTAL_DOCS_DIR", tmp_path / "portal-docs")
    monkeypatch.setattr(plat, "_seed_platform_db", lambda name: None)
    monkeypatch.setattr(plat, "_refresh_status_json", lambda: None)
    _create_platform(tmp_path, "my-plat")

    with caplog.at_level(logging.INFO, logger="platform_cli"):
        plat.cmd_register("my-plat")
    assert "registered" in caplog.text


# ══════════════════════════════════════
# _lint_platform edge cases
# ══════════════════════════════════════


def test_lint_platform_missing_dir(tmp_path):
    """_lint_platform returns False for nonexistent platform dir."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    try:
        result = plat._lint_platform("nonexistent")
        assert result is False
    finally:
        plat.PLATFORMS_DIR = old


def test_lint_platform_yaml_missing_fields(tmp_path):
    """_lint_platform detects missing required fields in platform.yaml."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    pdir = tmp_path / "bad-plat"
    pdir.mkdir()
    (pdir / "platform.yaml").write_text("lifecycle: design\n")
    for d in ["business", "engineering", "decisions", "epics"]:
        (pdir / d).mkdir()

    try:
        result = plat._lint_platform("bad-plat")
        assert result is False
    finally:
        plat.PLATFORMS_DIR = old


def test_lint_platform_name_mismatch(tmp_path, caplog):
    """_lint_platform warns when yaml name != dir name."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    pdir = tmp_path / "my-plat"
    pdir.mkdir()
    (pdir / "platform.yaml").write_text("name: wrong-name\ntitle: Test\nlifecycle: design\n")
    for d in ["business", "engineering", "decisions", "epics"]:
        (pdir / d).mkdir()

    try:
        with caplog.at_level(logging.WARNING, logger="platform_cli"):
            plat._lint_platform("my-plat")
        assert "wrong-name" in caplog.text
    finally:
        plat.PLATFORMS_DIR = old


def test_lint_platform_with_auto_markers(tmp_path, caplog):
    """_lint_platform checks AUTO markers in engineering files."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    pdir = _create_platform(tmp_path, "test-plat")
    for d in ["business", "engineering", "decisions", "epics"]:
        (pdir / d).mkdir()

    # Add AUTO markers
    (pdir / "engineering" / "context-map.md").write_text(
        "# Context Map\n<!-- AUTO:domains -->\ncontent\n<!-- /AUTO:domains -->\n"
        "<!-- AUTO:relations -->\nrels\n<!-- /AUTO:relations -->\n"
    )

    try:
        with caplog.at_level(logging.INFO, logger="platform_cli"):
            plat._lint_platform("test-plat")
        assert "AUTO:domains" in caplog.text
    finally:
        plat.PLATFORMS_DIR = old


# ══════════════════════════════════════
# _lint_testing_block tests
# ══════════════════════════════════════


def _make_valid_testing_block() -> dict:
    """Build a minimal valid testing: block for reuse in tests."""
    return {
        "startup": {"type": "docker", "command": None, "ready_timeout": 60},
        "health_checks": [{"url": "http://localhost:8050/health", "label": "API"}],
        "urls": [{"url": "http://localhost:3000", "type": "frontend", "label": "Home"}],
        "required_env": ["JWT_SECRET"],
        "env_file": ".env.example",
        "journeys_file": "testing/journeys.md",
    }


def test_lint_testing_block_valid():
    """A fully valid testing: block returns no errors."""
    data = _make_valid_testing_block()
    errors = plat._lint_testing_block(data, "my-plat")
    assert errors == []


def test_lint_testing_block_startup_type_absent():
    """Missing startup.type produces an error."""
    data = _make_valid_testing_block()
    del data["startup"]["type"]
    errors = plat._lint_testing_block(data, "my-plat")
    assert any("startup.type" in e and "required" in e for e in errors)


def test_lint_testing_block_startup_type_invalid():
    """An unrecognised startup.type produces an error."""
    data = _make_valid_testing_block()
    data["startup"]["type"] = "kubernetes"
    errors = plat._lint_testing_block(data, "my-plat")
    assert any("kubernetes" in e and "invalid" in e for e in errors)


def test_lint_testing_block_script_type_requires_command():
    """type=script without command is an error."""
    data = _make_valid_testing_block()
    data["startup"]["type"] = "script"
    data["startup"]["command"] = None  # missing
    errors = plat._lint_testing_block(data, "my-plat")
    assert any("command" in e and "script" in e for e in errors)


def test_lint_testing_block_venv_type_requires_command():
    """type=venv without command is an error."""
    data = _make_valid_testing_block()
    data["startup"]["type"] = "venv"
    data["startup"]["command"] = ""  # empty → falsy
    errors = plat._lint_testing_block(data, "my-plat")
    assert any("command" in e and "venv" in e for e in errors)


def test_lint_testing_block_script_type_with_command_ok():
    """type=script with a command set produces no error."""
    data = _make_valid_testing_block()
    data["startup"]["type"] = "script"
    data["startup"]["command"] = "./run.sh"
    errors = plat._lint_testing_block(data, "my-plat")
    assert errors == []


def test_lint_testing_block_empty_health_checks_ok():
    """health_checks: [] is valid (may be empty)."""
    data = _make_valid_testing_block()
    data["health_checks"] = []
    errors = plat._lint_testing_block(data, "my-plat")
    assert errors == []


def test_lint_testing_block_health_check_missing_url():
    """A health_check without 'url' produces an error."""
    data = _make_valid_testing_block()
    data["health_checks"] = [{"label": "API"}]  # no url
    errors = plat._lint_testing_block(data, "my-plat")
    assert any("health_checks[0]" in e and "'url'" in e for e in errors)


def test_lint_testing_block_health_check_missing_label():
    """A health_check without 'label' produces an error."""
    data = _make_valid_testing_block()
    data["health_checks"] = [{"url": "http://localhost:8050/health"}]  # no label
    errors = plat._lint_testing_block(data, "my-plat")
    assert any("health_checks[0]" in e and "'label'" in e for e in errors)


def test_lint_testing_block_empty_urls_ok():
    """urls: [] is valid (may be empty)."""
    data = _make_valid_testing_block()
    data["urls"] = []
    errors = plat._lint_testing_block(data, "my-plat")
    assert errors == []


def test_lint_testing_block_url_invalid_type():
    """A url with an invalid 'type' produces an error."""
    data = _make_valid_testing_block()
    data["urls"] = [{"url": "http://localhost:3000", "type": "websocket", "label": "WS"}]
    errors = plat._lint_testing_block(data, "my-plat")
    assert any("urls[0]" in e and "websocket" in e and "invalid" in e for e in errors)


def test_lint_testing_block_url_valid_types():
    """Both 'api' and 'frontend' url types are valid."""
    data = _make_valid_testing_block()
    data["urls"] = [
        {"url": "http://localhost:8050/health", "type": "api", "label": "API"},
        {"url": "http://localhost:3000", "type": "frontend", "label": "FE"},
    ]
    errors = plat._lint_testing_block(data, "my-plat")
    assert errors == []


def test_lint_testing_block_url_missing_label():
    """A url without 'label' produces an error."""
    data = _make_valid_testing_block()
    data["urls"] = [{"url": "http://localhost:3000", "type": "frontend"}]
    errors = plat._lint_testing_block(data, "my-plat")
    assert any("urls[0]" in e and "'label'" in e for e in errors)


def test_lint_testing_block_required_env_non_string():
    """required_env with a non-string entry produces an error."""
    data = _make_valid_testing_block()
    data["required_env"] = ["JWT_SECRET", 42]  # 42 is not a string
    errors = plat._lint_testing_block(data, "my-plat")
    assert any("required_env[1]" in e and "string" in e for e in errors)


def test_lint_testing_block_required_env_empty_ok():
    """required_env: [] is valid."""
    data = _make_valid_testing_block()
    data["required_env"] = []
    errors = plat._lint_testing_block(data, "my-plat")
    assert errors == []


def test_lint_testing_block_not_a_dict():
    """testing: block that is not a dict produces an error immediately."""
    errors = plat._lint_testing_block("not-a-dict", "my-plat")
    assert len(errors) == 1
    assert "mapping" in errors[0]


def test_lint_platform_testing_block_absent_not_called(tmp_path):
    """_lint_platform does NOT error when testing: block is absent (retrocompat)."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    pdir = _create_platform(tmp_path, "no-testing")
    for d in ["business", "engineering", "decisions", "epics"]:
        (pdir / d).mkdir()

    try:
        result = plat._lint_platform("no-testing")
        assert result is True  # no testing: → should not fail
    finally:
        plat.PLATFORMS_DIR = old


def test_lint_platform_testing_block_valid_passes(tmp_path):
    """_lint_platform passes when testing: block is present and valid."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    yaml_content = (
        "name: plat-with-testing\n"
        "title: Test\n"
        "lifecycle: design\n"
        "testing:\n"
        "  startup:\n"
        "    type: npm\n"
        "    command: null\n"
        "    ready_timeout: 30\n"
        "  health_checks: []\n"
        "  urls: []\n"
        "  required_env: []\n"
        "  env_file: null\n"
        "  journeys_file: testing/journeys.md\n"
    )
    pdir = _create_platform(tmp_path, "plat-with-testing", yaml_content)
    for d in ["business", "engineering", "decisions", "epics"]:
        (pdir / d).mkdir()

    try:
        result = plat._lint_platform("plat-with-testing")
        assert result is True
    finally:
        plat.PLATFORMS_DIR = old


def test_lint_platform_testing_block_invalid_fails(tmp_path):
    """_lint_platform returns False when testing: block has errors."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    yaml_content = (
        "name: plat-bad-testing\n"
        "title: Test\n"
        "lifecycle: design\n"
        "testing:\n"
        "  startup:\n"
        "    type: invalid-type\n"
        "  health_checks: []\n"
        "  urls: []\n"
        "  required_env: []\n"
    )
    pdir = _create_platform(tmp_path, "plat-bad-testing", yaml_content)
    for d in ["business", "engineering", "decisions", "epics"]:
        (pdir / d).mkdir()

    try:
        result = plat._lint_platform("plat-bad-testing")
        assert result is False
    finally:
        plat.PLATFORMS_DIR = old


# ══════════════════════════════════════
# Template realignment regression tests
# ══════════════════════════════════════


def test_template_no_orphan_integrations_jinja():
    """Regression: integrations.md.jinja was removed (orphan, no skill produces it)."""
    template_dir = plat.TEMPLATE_DIR / "template"
    assert not (template_dir / "engineering" / "integrations.md.jinja").exists(), (
        "engineering/integrations.md.jinja should be removed (orphan template)"
    )


def test_copier_yml_has_new_questions():
    """Regression: copier.yml must define tags + testing_startup_type questions."""
    copier_yml = (plat.TEMPLATE_DIR / "copier.yml").read_text()
    assert "tags:" in copier_yml, "copier.yml must define tags question"
    assert "testing_startup_type:" in copier_yml, (
        "copier.yml must define testing_startup_type question (else testing block is unreachable)"
    )


def test_required_files_excludes_integrations():
    """Regression: REQUIRED_FILES no longer references engineering/integrations.md."""
    assert "engineering/integrations.md" not in plat.REQUIRED_FILES
    assert "engineering/integrations.md" not in plat.AUTO_MARKERS


# ══════════════════════════════════════
# _notify_dev_server (Astro soft-restart trigger)
# ══════════════════════════════════════


def _patch_socket(monkeypatch, connect_ex_returns: int) -> None:
    """Stub socket.socket() so connect_ex returns a fixed value (0=open, !=0=closed)."""
    import socket as real_socket

    class _FakeSocket:
        def settimeout(self, _):
            pass

        def connect_ex(self, _addr):
            return connect_ex_returns

        def close(self):
            pass

    monkeypatch.setattr(real_socket, "socket", lambda *_a, **_k: _FakeSocket())


def test_notify_dev_server_no_op_when_port_closed(tmp_path, monkeypatch):
    """No dev server on :4321 → no touch, no error."""
    _patch_socket(monkeypatch, connect_ex_returns=1)
    fake_config = tmp_path / "astro.config.mjs"
    fake_config.write_text("// dummy")
    original_mtime = fake_config.stat().st_mtime
    monkeypatch.setattr(plat, "PORTAL_DIR", tmp_path)

    plat._notify_dev_server()

    assert fake_config.stat().st_mtime == original_mtime, "config should NOT be touched when port is closed"


def _patch_urlopen(monkeypatch, status_code: int) -> None:
    """Stub urllib.request.urlopen to return a fake response with given status."""
    import urllib.request as real_urlreq

    class _FakeResp:
        status = status_code

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    monkeypatch.setattr(real_urlreq, "urlopen", lambda *_a, **_k: _FakeResp())


def _patch_urlopen_failing(monkeypatch) -> None:
    """Stub urllib.request.urlopen to always raise URLError (simulates server still down)."""
    import urllib.error as real_urlerr
    import urllib.request as real_urlreq

    def _raise(*_a, **_k):
        raise real_urlerr.URLError("simulated: server not ready")

    monkeypatch.setattr(real_urlreq, "urlopen", _raise)


def test_notify_dev_server_touches_and_verifies_recovery(tmp_path, monkeypatch):
    """Dev server on :4321 + recovery → touch happens + verify loop exits cleanly."""
    import time

    _patch_socket(monkeypatch, connect_ex_returns=0)
    _patch_urlopen(monkeypatch, status_code=200)
    fake_config = tmp_path / "astro.config.mjs"
    fake_config.write_text("// dummy")
    original_mtime = fake_config.stat().st_mtime
    monkeypatch.setattr(plat, "PORTAL_DIR", tmp_path)

    time.sleep(0.01)
    plat._notify_dev_server()

    assert fake_config.stat().st_mtime > original_mtime, "config SHOULD be touched when dev server is running"


def test_notify_dev_server_warns_when_recovery_fails(tmp_path, monkeypatch, caplog):
    """Touch happens but server stays down → warns instead of staying silent."""
    import logging

    _patch_socket(monkeypatch, connect_ex_returns=0)
    _patch_urlopen_failing(monkeypatch)
    fake_config = tmp_path / "astro.config.mjs"
    fake_config.write_text("// dummy")
    monkeypatch.setattr(plat, "PORTAL_DIR", tmp_path)

    with caplog.at_level(logging.WARNING, logger="platform_cli"):
        plat._notify_dev_server(_verify_attempts=2, _verify_interval=0)

    assert "did not recover" in caplog.text, "should warn when server stays down"
    assert "Restart manually" in caplog.text, "warning should be actionable"


def test_notify_dev_server_silent_when_portal_missing(tmp_path, monkeypatch):
    """Portal dir without astro.config.mjs → silent no-op (no exception)."""
    _patch_socket(monkeypatch, connect_ex_returns=0)
    monkeypatch.setattr(plat, "PORTAL_DIR", tmp_path)  # tmp_path has no astro.config.mjs

    plat._notify_dev_server()  # Must not raise
