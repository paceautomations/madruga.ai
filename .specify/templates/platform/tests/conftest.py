"""Shared fixtures for template tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = {
    "platform_name": "acme-platform",
    "platform_title": "Acme Platform",
    "platform_description": "Plataforma de teste automatizado",
    "lifecycle": "design",
    "include_business_flow": True,
    "register_portal": False,
}


def _git_init(path: Path) -> None:
    """Initialize a git repo and make an initial commit."""
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


@pytest.fixture
def template_root() -> Path:
    return TEMPLATE_ROOT


@pytest.fixture
def default_data() -> dict:
    return dict(DEFAULT_DATA)


@pytest.fixture
def scaffold(tmp_path: Path, template_root: Path, default_data: dict):
    """Scaffold a platform into tmp_path and return the output directory."""
    from copier import run_copy

    dst = tmp_path / "output"
    run_copy(
        str(template_root),
        str(dst),
        data=default_data,
        unsafe=True,
        defaults=True,
    )
    return dst


@pytest.fixture
def scaffold_git(tmp_path: Path, template_root: Path, default_data: dict):
    """Scaffold a platform into a git repo (required for copier update)."""
    from copier import run_copy

    dst = tmp_path / "output"
    run_copy(
        str(template_root),
        str(dst),
        data=default_data,
        unsafe=True,
        defaults=True,
    )
    _git_init(dst)
    return dst
