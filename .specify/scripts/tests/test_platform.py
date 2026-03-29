"""Tests for platform.py functions."""

import importlib
import re
import sys
from pathlib import Path

# Add scripts dir to path so we can import platform.py as a module
_scripts_dir = str(Path(__file__).parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# Import as 'plat' to avoid collision with stdlib 'platform'
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "plat", Path(__file__).parent.parent / "platform.py"
)
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

    _create_platform(tmp_path, "alpha")
    _create_platform(tmp_path, "beta")
    (tmp_path / "not-a-platform").mkdir()  # no platform.yaml

    try:
        result = plat._discover_platforms()
        assert result == ["alpha", "beta"]
    finally:
        plat.PLATFORMS_DIR = old


def test_lint_platform_valid(tmp_path, capsys):
    old = plat.PLATFORMS_DIR
    plat.PLATFORMS_DIR = tmp_path

    pdir = _create_platform(tmp_path, "test-plat")
    for d in ["business", "engineering", "decisions", "epics", "model"]:
        (pdir / d).mkdir()
    for f in [
        "business/vision.md",
        "business/solution-overview.md",
        "engineering/domain-model.md",
        "engineering/integrations.md",
        "engineering/blueprint.md",
        "model/spec.likec4",
    ]:
        (pdir / f).write_text("placeholder")
    (pdir / "model" / "likec4.config.json").write_text('{"name": "test-plat"}')

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
