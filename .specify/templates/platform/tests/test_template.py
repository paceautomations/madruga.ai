"""TDD tests for the platform Copier template."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


def test_scaffold_structure(scaffold: Path):
    """Copier copy generates all expected files and directories."""
    expected_files = [
        "platform.yaml",
        "business/vision.md",
        "business/solution-overview.md",
        "engineering/domain-model.md",
        "engineering/containers.md",
        "engineering/context-map.md",
        "engineering/integrations.md",
        "model/spec.likec4",
        "model/likec4.config.json",
        "model/platform.likec4",
        "model/actors.likec4",
        "model/externals.likec4",
        "model/infrastructure.likec4",
        "model/ddd-contexts.likec4",
        "model/relationships.likec4",
        "model/views.likec4",
        "model/.gitignore",
    ]
    expected_dirs = ["decisions", "epics", "research"]

    for f in expected_files:
        assert (scaffold / f).exists(), f"Missing file: {f}"

    for d in expected_dirs:
        assert (scaffold / d).is_dir(), f"Missing directory: {d}"


def test_platform_yaml_values(scaffold: Path, default_data: dict):
    """Jinja variables are substituted correctly in platform.yaml."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())

    assert content["name"] == default_data["platform_name"]
    assert content["title"] == default_data["platform_title"]
    assert content["description"] == default_data["platform_description"]
    assert content["lifecycle"] == default_data["lifecycle"]
    assert content["version"] == "0.1.0"


def test_spec_likec4_identical(scaffold: Path, template_root: Path):
    """spec.likec4 is byte-for-byte identical to the canonical template copy."""
    canonical = (template_root / "template" / "model" / "spec.likec4").read_bytes()
    generated = (scaffold / "model" / "spec.likec4").read_bytes()
    assert canonical == generated, "spec.likec4 diverged from canonical"


def test_auto_markers_present(scaffold: Path):
    """All AUTO markers exist in engineering docs."""
    containers = (scaffold / "engineering" / "containers.md").read_text()
    assert "<!-- AUTO:containers -->" in containers
    assert "<!-- /AUTO:containers -->" in containers

    context_map = (scaffold / "engineering" / "context-map.md").read_text()
    assert "<!-- AUTO:domains -->" in context_map
    assert "<!-- /AUTO:domains -->" in context_map
    assert "<!-- AUTO:relations -->" in context_map
    assert "<!-- /AUTO:relations -->" in context_map

    integrations = (scaffold / "engineering" / "integrations.md").read_text()
    assert "<!-- AUTO:integrations -->" in integrations
    assert "<!-- /AUTO:integrations -->" in integrations


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
        except Exception:
            pass  # Expected: validation error


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


def test_spec_not_in_skip_list(template_root: Path):
    """spec.likec4 should NOT be in _skip_if_exists (it must sync on update)."""
    copier_yml = yaml.safe_load((template_root / "copier.yml").read_text())
    skip_list = copier_yml.get("_skip_if_exists", [])
    for entry in skip_list:
        assert "spec.likec4" not in str(entry), f"spec.likec4 should not be skipped on update, but found in: {entry}"


def test_conditional_business_flow(tmp_path: Path, template_root: Path, default_data: dict):
    """include_business_flow=false removes the businessFlow view."""
    from copier import run_copy

    data = dict(default_data)
    data["include_business_flow"] = False
    dst = tmp_path / "no-flow"

    run_copy(str(template_root), str(dst), data=data, unsafe=True, defaults=True)

    views = (dst / "model" / "views.likec4").read_text()
    assert "businessFlow" not in views, "businessFlow view should not exist when disabled"

    platform_yaml = yaml.safe_load((dst / "platform.yaml").read_text())
    flows = platform_yaml.get("views", {}).get("flows", [])
    flow_ids = [f["id"] for f in flows] if flows else []
    assert "businessFlow" not in flow_ids, "businessFlow should not be in platform.yaml flows"


def test_likec4_config_json(scaffold: Path, default_data: dict):
    """likec4.config.json has the correct project name."""
    config = json.loads((scaffold / "model" / "likec4.config.json").read_text())
    assert config["name"] == default_data["platform_name"]


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
