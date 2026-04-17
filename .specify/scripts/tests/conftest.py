"""Shared fixtures for db.py tests."""

import gc
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import sys

# Add scripts dir to path so we can import db
sys.path.insert(0, str(Path(__file__).parent.parent))

# Eagerly import modules that use `from db import get_conn` at module level.
# Without this, test_hallucination_guard patches db.get_conn then triggers
# `from post_save import _get_required_epic_nodes` inside run_pipeline(),
# causing post_save.get_conn to be bound to the mock permanently.
import post_save  # noqa: F401, E402


# Snapshot the test runner's process group at collection time so the safety
# fixture below can detect calls that would signal the runner's own group.
_TEST_RUNNER_PGID = os.getpgid(0)


@pytest.fixture(autouse=True)
def _prevent_killpg_suicide(monkeypatch):
    """Safety net: block os.killpg() calls during tests that would kill the runner.

    Production code in dag_executor (dispatch_node_async timeout, shutdown
    cascade) calls os.killpg() on the subprocess's process group. If a test
    mock leaks a non-int pid, or if production logic drifts and stops creating
    new sessions (start_new_session=True), the target pgid can equal the
    runner's pgid — SIGKILL to that group kills pytest, make, the shell, and
    in WSL can crash the terminal/session.

    This fixture wraps os.killpg to raise PermissionError instead of actually
    signalling when the target equals the runner's pgid (or is 0, meaning
    "current group"). dag_executor._kill_process_group_safely catches
    PermissionError and falls back to process.kill(), which is safe.
    """
    real_killpg = os.killpg

    def safe_killpg(pgid, sig):
        if pgid in (0, _TEST_RUNNER_PGID):
            raise PermissionError(
                f"Test safety: refused killpg(pgid={pgid}, sig={sig}) — would signal test runner's process group"
            )
        return real_killpg(pgid, sig)

    monkeypatch.setattr(os, "killpg", safe_killpg)


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


@pytest.fixture(autouse=True)
def _clear_repo_binding_cache():
    """Clear _load_repo_binding lru_cache between tests."""
    from ensure_repo import _load_repo_binding

    _load_repo_binding.cache_clear()
    yield
    _load_repo_binding.cache_clear()


@pytest.fixture(autouse=True)
def _mock_epic_output_dir_self_ref(request):
    """Default _epic_output_dir to self-ref (relative) for all tests.

    Tests that need the real _epic_output_dir should use the marker:
        @pytest.mark.real_epic_output_dir
    """
    if request.node.get_closest_marker("real_epic_output_dir"):
        yield
        return

    def _self_ref_output_dir(platform_name, epic_slug):
        return f"platforms/{platform_name}/epics/{epic_slug}"

    with patch("dag_executor._epic_output_dir", side_effect=_self_ref_output_dir):
        yield


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
def mock_pipeline(tmp_path):
    """Write a minimal pipeline.yaml and patch config.PIPELINE_YAML.

    Returns the path.  Use as a context-manager fixture — the patch is active
    for the duration of the test that requests this fixture.
    """
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(
        "nodes:\n"
        "  - id: platform-new\n"
        "    skill: 'madruga:platform-new'\n"
        "    outputs: ['platform.yaml']\n"
        "    depends: []\n"
        "    layer: business\n"
        "    gate: human\n"
        "  - id: vision\n"
        "    skill: 'madruga:vision'\n"
        "    outputs: ['business/vision.md']\n"
        "    depends: ['platform-new']\n"
        "    layer: business\n"
        "    gate: human\n"
        "  - id: solution-overview\n"
        "    skill: 'madruga:solution-overview'\n"
        "    outputs: ['business/solution-overview.md']\n"
        "    depends: ['vision']\n"
        "    layer: business\n"
        "    gate: human\n"
    )
    with patch("config.PIPELINE_YAML", pipeline_path):
        yield pipeline_path


@pytest.fixture
def sample_platform_dir(tmp_path):
    """Create a mock platform directory with platform.yaml and sample files."""
    pdir = tmp_path / "platforms" / "test-plat"
    pdir.mkdir(parents=True)

    # platform.yaml — metadata only (pipeline lives in pipeline.yaml)
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
""")

    # Create some "done" artifacts
    (pdir / "business").mkdir()
    (pdir / "business" / "vision.md").write_text("---\ntitle: Vision\n---\n# Vision\nContent here.\n")

    # Create epics
    epic_dir = pdir / "epics" / "001-test-epic"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text('---\ntitle: "Test Epic"\nstatus: in_progress\npriority: 1\n---\n# Test Epic\n')

    return pdir
