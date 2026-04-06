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
    assert re.match(pattern, "fulano")
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
            set_local_config(conn, "active_platform", "fulano")

        plat.cmd_current()
        captured = capsys.readouterr()
        assert "Active platform: fulano" in captured.out
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
