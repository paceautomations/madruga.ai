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


def test_cmd_register_valid(tmp_path, caplog):
    """cmd_register succeeds for existing platform."""
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path
    _create_platform(tmp_path, "my-plat")

    try:
        with caplog.at_level(logging.INFO, logger="platform_cli"):
            plat.cmd_register("my-plat")
        assert "registered" in caplog.text
    finally:
        plat.PLATFORMS_DIR = old


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
