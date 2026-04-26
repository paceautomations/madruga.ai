"""Tests for config.load_pipeline() shared pipeline definition."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_pipeline


def test_load_pipeline_keys():
    """load_pipeline() returns a dict with nodes, epic_cycle, quick_cycle keys."""
    p = load_pipeline()
    assert isinstance(p, dict)
    assert "nodes" in p
    assert "epic_cycle" in p
    assert "quick_cycle" in p


def test_l1_has_12_nodes():
    """L1 pipeline has exactly 12 nodes (epic-breakdown removed in favour of roadmap)."""
    assert len(load_pipeline()["nodes"]) == 12


def test_l2_has_12_nodes():
    """L2 epic cycle has exactly 12 nodes."""
    assert len(load_pipeline()["epic_cycle"]["nodes"]) == 12


def test_quick_has_3_nodes():
    """Quick cycle has exactly 3 nodes."""
    assert len(load_pipeline()["quick_cycle"]["nodes"]) == 3


def test_all_nodes_have_required_fields():
    """All nodes have required fields: id, skill, gate."""
    p = load_pipeline()
    all_nodes = p["nodes"] + p["epic_cycle"]["nodes"] + p["quick_cycle"]["nodes"]
    for node in all_nodes:
        assert "id" in node, f"Node missing id: {node}"
        assert "skill" in node, f"Node {node['id']} missing skill"
        assert "gate" in node, f"Node {node['id']} missing gate"


def test_all_nodes_have_outputs():
    """All nodes have outputs or output_pattern."""
    p = load_pipeline()
    all_nodes = p["nodes"] + p["epic_cycle"]["nodes"] + p["quick_cycle"]["nodes"]
    for node in all_nodes:
        has_outputs = "outputs" in node or "output_pattern" in node
        assert has_outputs, f"Node {node['id']} missing outputs or output_pattern"
