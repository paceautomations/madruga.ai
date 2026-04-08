"""Tests for pipeline.yaml shared pipeline definition."""

from __future__ import annotations

from pathlib import Path

import yaml


PIPELINE_YAML = Path(__file__).resolve().parent.parent.parent.parent.parent / ".specify" / "pipeline.yaml"


def test_pipeline_yaml_exists():
    """Shared pipeline.yaml exists at .specify/pipeline.yaml."""
    assert PIPELINE_YAML.exists(), f"Missing {PIPELINE_YAML}"


def test_platform_yaml_has_no_pipeline(scaffold: Path):
    """Copier-generated platform.yaml does NOT contain a pipeline section."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())
    assert "pipeline" not in content, "platform.yaml should not have a pipeline section after refactor"


def test_pipeline_has_13_l1_nodes():
    """Pipeline DAG (L1) has exactly 13 nodes."""
    pipeline = yaml.safe_load(PIPELINE_YAML.read_text())
    nodes = pipeline["nodes"]
    assert len(nodes) == 13, f"Expected 13 pipeline nodes, got {len(nodes)}"
    node_ids = [n["id"] for n in nodes]
    assert "folder-arch" not in node_ids, "folder-arch should be removed from pipeline"


def test_epic_cycle_has_12_nodes():
    """epic_cycle contains exactly 12 nodes."""
    pipeline = yaml.safe_load(PIPELINE_YAML.read_text())
    nodes = pipeline["epic_cycle"]["nodes"]
    assert len(nodes) == 12, f"Expected 12 epic_cycle nodes, got {len(nodes)}"


def test_epic_cycle_node_ids():
    """epic_cycle nodes have correct IDs in expected order."""
    pipeline = yaml.safe_load(PIPELINE_YAML.read_text())
    nodes = pipeline["epic_cycle"]["nodes"]
    expected_ids = [
        "epic-context",
        "specify",
        "clarify",
        "plan",
        "tasks",
        "analyze",
        "implement",
        "analyze-post",
        "judge",
        "qa",
        "reconcile",
        "roadmap-reassess",
    ]
    actual_ids = [n["id"] for n in nodes]
    assert actual_ids == expected_ids, f"Expected {expected_ids}, got {actual_ids}"


def test_epic_cycle_nodes_have_required_fields():
    """Each epic_cycle node has required fields: id, skill, outputs, depends, gate."""
    pipeline = yaml.safe_load(PIPELINE_YAML.read_text())
    nodes = pipeline["epic_cycle"]["nodes"]
    required_fields = {"id", "skill", "outputs", "depends", "gate"}
    for node in nodes:
        missing = required_fields - set(node.keys())
        assert not missing, f"Node {node['id']} missing fields: {missing}"


def test_epic_cycle_all_nodes_mandatory():
    """All 12 epic_cycle nodes are mandatory (no optional flag)."""
    pipeline = yaml.safe_load(PIPELINE_YAML.read_text())
    nodes = pipeline["epic_cycle"]["nodes"]
    for node in nodes:
        assert not node.get("optional"), f"Node {node['id']} should not be optional — all L2 nodes are mandatory"


def test_epic_cycle_outputs_use_epic_placeholder():
    """All epic_cycle outputs use {epic} placeholder."""
    pipeline = yaml.safe_load(PIPELINE_YAML.read_text())
    nodes = pipeline["epic_cycle"]["nodes"]
    for node in nodes:
        for output in node["outputs"]:
            assert "{epic}" in output, f"Node {node['id']} output '{output}' missing {{epic}} placeholder"
