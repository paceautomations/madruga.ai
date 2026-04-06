"""Tests for epic_cycle section in platform.yaml template."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_epic_cycle_exists(scaffold: Path):
    """Copier-generated platform.yaml contains epic_cycle section."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())
    pipeline = content.get("pipeline", {})
    assert "epic_cycle" in pipeline, "Missing epic_cycle section in platform.yaml"


def test_epic_cycle_has_12_nodes(scaffold: Path):
    """epic_cycle contains exactly 12 nodes."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())
    nodes = content["pipeline"]["epic_cycle"]["nodes"]
    assert len(nodes) == 12, f"Expected 12 epic_cycle nodes, got {len(nodes)}"


def test_epic_cycle_node_ids(scaffold: Path):
    """epic_cycle nodes have correct IDs in expected order."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())
    nodes = content["pipeline"]["epic_cycle"]["nodes"]
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


def test_epic_cycle_nodes_have_required_fields(scaffold: Path):
    """Each epic_cycle node has required fields: id, skill, outputs, depends, gate."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())
    nodes = content["pipeline"]["epic_cycle"]["nodes"]
    required_fields = {"id", "skill", "outputs", "depends", "gate"}
    for node in nodes:
        missing = required_fields - set(node.keys())
        assert not missing, f"Node {node['id']} missing fields: {missing}"


def test_epic_cycle_all_nodes_mandatory(scaffold: Path):
    """All 12 epic_cycle nodes are mandatory (no optional flag)."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())
    nodes = content["pipeline"]["epic_cycle"]["nodes"]
    for node in nodes:
        assert not node.get("optional"), f"Node {node['id']} should not be optional — all L2 nodes are mandatory"


def test_epic_cycle_outputs_use_epic_placeholder(scaffold: Path):
    """All epic_cycle outputs use {epic} placeholder."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())
    nodes = content["pipeline"]["epic_cycle"]["nodes"]
    for node in nodes:
        for output in node["outputs"]:
            assert "{epic}" in output, f"Node {node['id']} output '{output}' missing {{epic}} placeholder"


def test_pipeline_nodes_count_13(scaffold: Path):
    """Platform DAG (L1) has exactly 13 nodes (folder-arch removed)."""
    content = yaml.safe_load((scaffold / "platform.yaml").read_text())
    nodes = content["pipeline"]["nodes"]
    assert len(nodes) == 13, f"Expected 13 pipeline nodes, got {len(nodes)}"
    node_ids = [n["id"] for n in nodes]
    assert "folder-arch" not in node_ids, "folder-arch should be removed from pipeline"
