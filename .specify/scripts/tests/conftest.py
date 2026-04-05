"""Shared fixtures for db.py tests."""

import gc
from pathlib import Path

import pytest
import sys

# Add scripts dir to path so we can import db
sys.path.insert(0, str(Path(__file__).parent.parent))

# Eagerly import modules that use `from db import get_conn` at module level.
# Without this, test_hallucination_guard patches db.get_conn then triggers
# `from post_save import _get_required_epic_nodes` inside run_pipeline(),
# causing post_save.get_conn to be bound to the mock permanently.
import post_save  # noqa: F401, E402


@pytest.fixture(autouse=True)
def _gc_collect_after_test():
    """Force garbage collection after every test.

    MagicMock objects create reference cycles (parent ↔ child) that bypass
    Python's refcount collector. Without explicit gc.collect(), cycles from
    73+ tests accumulate faster than the generational GC can reclaim them,
    leading to 18-23 GB RSS and OOM kills on WSL.
    """
    yield
    gc.collect()


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temp DB with migrations applied."""
    from db import get_conn, migrate

    db_path = tmp_path / "test.db"
    migrations_dir = Path(__file__).parent.parent.parent.parent / ".pipeline" / "migrations"
    conn = get_conn(db_path)
    migrate(conn, migrations_dir)
    yield conn
    conn.close()


@pytest.fixture
def sample_platform_dir(tmp_path):
    """Create a mock platform directory with platform.yaml and sample files."""
    pdir = tmp_path / "platforms" / "test-plat"
    pdir.mkdir(parents=True)

    # platform.yaml with pipeline section
    (pdir / "platform.yaml").write_text("""
name: test-plat
title: "Test Platform"
lifecycle: design
version: "0.1.0"
repo:
  org: testorg
  name: test-repo
  base_branch: main
  epic_branch_prefix: "epic/test-plat/"
tags: [test, sample]
model: model/
pipeline:
  nodes:
    - id: platform-new
      skill: "madruga:platform-new"
      outputs: ["platform.yaml"]
      depends: []
      layer: business
      gate: human
    - id: vision
      skill: "madruga:vision"
      outputs: ["business/vision.md"]
      depends: ["platform-new"]
      layer: business
      gate: human
    - id: solution-overview
      skill: "madruga:solution-overview"
      outputs: ["business/solution-overview.md"]
      depends: ["vision"]
      layer: business
      gate: human
""")

    # Create some "done" artifacts
    (pdir / "business").mkdir()
    (pdir / "business" / "vision.md").write_text("---\ntitle: Vision\n---\n# Vision\nContent here.\n")

    # Create epics
    epic_dir = pdir / "epics" / "001-test-epic"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text(
        '---\ntitle: "Test Epic"\nstatus: in_progress\nappetite: "1w"\npriority: 1\n---\n# Test Epic\n'
    )

    return pdir
