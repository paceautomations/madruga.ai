"""TDD tests for the platform Copier template."""

from __future__ import annotations

import subprocess
from pathlib import Path

import copier.errors
import yaml


def test_scaffold_structure(scaffold: Path):
    """Copier copy generates all expected files and directories."""
    expected_files = [
        "platform.yaml",
        "business/vision.md",
        "business/solution-overview.md",
        "engineering/domain-model.md",
        "engineering/context-map.md",
        "engineering/blueprint.md",
        "engineering/containers.md",
        "decisions.md",
    ]
    expected_dirs = ["decisions", "epics", "research"]

    for f in expected_files:
        assert (scaffold / f).exists(), f"Missing file: {f}"

    for d in expected_dirs:
        assert (scaffold / d).is_dir(), f"Missing directory: {d}"


def test_orphan_files_removed(scaffold: Path):
    """Regression: integrations.md was removed (orphan, no skill produces it)."""
    assert not (scaffold / "engineering" / "integrations.md").exists(), (
        "integrations.md should not be in template (orphan removed in template realignment)"
    )


def test_platform_yaml_values(scaffold: Path, default_data: dict):
    """Jinja variables are substituted correctly in platform.yaml."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())

    assert content["name"] == default_data["platform_name"]
    assert content["title"] == default_data["platform_title"]
    assert content["description"] == default_data["platform_description"]
    assert content["lifecycle"] == default_data["lifecycle"]
    assert content["version"] == "0.1.0"


def test_auto_markers_present(scaffold: Path):
    """AUTO markers exist in engineering docs (used by reconcile/reverse-reconcile)."""
    context_map = (scaffold / "engineering" / "context-map.md").read_text()
    assert "<!-- AUTO:domains -->" in context_map
    assert "<!-- /AUTO:domains -->" in context_map
    assert "<!-- AUTO:relations -->" in context_map
    assert "<!-- /AUTO:relations -->" in context_map


def test_kebab_case_validation(tmp_path: Path, template_root: Path):
    """Copier rejects invalid platform names."""
    from copier import run_copy

    invalid_names = ["MeuProjeto", "meu projeto", "123-abc", "Abc"]
    for name in invalid_names:
        dst = tmp_path / f"invalid-{name}"
        try:
            run_copy(
                str(template_root),
                str(dst),
                data={
                    "platform_name": name,
                    "platform_title": "Test",
                    "platform_description": "Test",
                    "lifecycle": "design",
                    "include_business_flow": True,
                    "register_portal": False,
                },
                unsafe=True,
                defaults=True,
            )
            # If it didn't raise, check if the directory is empty (validation failed silently)
            # or contains files (validation was bypassed)
            if (dst / "platform.yaml").exists():
                raise AssertionError(f"Copier accepted invalid name: {name}")
        except (subprocess.CalledProcessError, OSError, copier.errors.CopierError, ValueError):
            pass  # Expected: copier validation rejects invalid names


def test_skip_if_exists_config(template_root: Path):
    """copier.yml declares _skip_if_exists for user-modified files.

    Full copier update E2E testing requires a git-tagged remote template
    (copier needs _commit refs for three-way merge). This test validates
    that the _skip_if_exists config is correctly defined.
    """
    copier_yml = yaml.safe_load((template_root / "copier.yml").read_text())
    skip_list = copier_yml.get("_skip_if_exists", [])
    assert isinstance(skip_list, list), "_skip_if_exists should be a list"
    assert len(skip_list) > 0, "_skip_if_exists should not be empty"
    # Key user-editable files should be protected
    skip_str = " ".join(str(s) for s in skip_list)
    assert "vision.md" in skip_str or "business/" in skip_str or "*" in skip_str, (
        "Business docs should be in _skip_if_exists"
    )


def _scaffold_yaml(tmp_path: Path, template_root: Path, default_data: dict, name: str, **overrides) -> dict:
    """Scaffold the template with overrides into tmp_path/<name> and return parsed platform.yaml."""
    from copier import run_copy

    data = {**default_data, "platform_name": name, **overrides}
    dst = tmp_path / name
    run_copy(str(template_root), str(dst), data=data, unsafe=True, defaults=True)
    return yaml.safe_load((dst / "platform.yaml").read_text())


def test_conditional_tags_block(tmp_path: Path, template_root: Path, default_data: dict):
    """tags='' omits tags block; tags='a,b,c' renders as YAML list."""
    yaml_empty = _scaffold_yaml(tmp_path, template_root, default_data, "no-tags", tags="")
    assert "tags" not in yaml_empty, "Empty tags should omit the field"

    yaml_full = _scaffold_yaml(tmp_path, template_root, default_data, "with-tags", tags="alpha,beta,gamma")
    assert yaml_full.get("tags") == ["alpha", "beta", "gamma"]


def test_conditional_testing_block(tmp_path: Path, template_root: Path, default_data: dict):
    """testing_startup_type=none omits testing block; non-none renders skeleton."""
    yaml_none = _scaffold_yaml(tmp_path, template_root, default_data, "no-testing", testing_startup_type="none")
    assert "testing" not in yaml_none, "testing_startup_type=none should omit testing block"

    yaml_docker = _scaffold_yaml(tmp_path, template_root, default_data, "with-docker", testing_startup_type="docker")
    testing = yaml_docker.get("testing", {})
    assert testing.get("startup", {}).get("type") == "docker"
    assert testing.get("startup", {}).get("ready_timeout") == 120
    assert testing.get("journeys_file") == "testing/journeys.md"


def test_no_jinja_artifacts(scaffold: Path):
    """No residual {{ or {% in generated files."""
    for f in scaffold.rglob("*"):
        if not f.is_file():
            continue
        if f.name == ".copier-answers.yml":
            continue
        try:
            content = f.read_text()
        except UnicodeDecodeError:
            continue
        assert "{{" not in content, f"Jinja artifact '{{{{' found in {f.relative_to(scaffold)}"
        assert "{%" not in content, f"Jinja artifact '{{% %}}' found in {f.relative_to(scaffold)}"
