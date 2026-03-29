"""Shared fixtures for db.py tests."""

from pathlib import Path

import pytest
import sys

# Add scripts dir to path so we can import db
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temp DB with migrations applied."""
    from db import get_conn, migrate

    db_path = tmp_path / "test.db"
    migrations_dir = (
        Path(__file__).parent.parent.parent.parent / ".pipeline" / "migrations"
    )
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
      skill: "madruga:vision-one-pager"
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
    (pdir / "business" / "vision.md").write_text(
        "---\ntitle: Vision\n---\n# Vision\nContent here.\n"
    )

    # Create epics
    epic_dir = pdir / "epics" / "001-test-epic"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text('---\ntitle: "Test Epic"\n---\n# Test Epic\n')

    return pdir
