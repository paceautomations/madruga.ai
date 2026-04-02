"""Tests for dag_executor.py — async dispatch, retry, circuit breaker."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dag_executor import CircuitBreaker, Node

# --- Helpers ---


def _make_node(node_id: str = "test-node", skill: str = "test:skill") -> Node:
    return Node(
        id=node_id,
        skill=skill,
        outputs=[],
        depends=[],
        gate="auto",
        layer="test",
        optional=False,
        skip_condition=None,
    )


# --- T004: Tests for dispatch_node_async ---


@pytest.mark.asyncio
async def test_dispatch_node_async_success():
    """dispatch_node_async returns (True, None) on success."""
    from dag_executor import dispatch_node_async

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"output", b"")
    mock_proc.returncode = 0

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        success, error = await dispatch_node_async(_make_node(), "/tmp", "test prompt")

    assert success is True
    assert error is None


@pytest.mark.asyncio
async def test_dispatch_node_async_timeout():
    """dispatch_node_async returns (False, timeout message) on timeout."""
    from dag_executor import dispatch_node_async

    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = asyncio.TimeoutError()
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock()

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        success, error = await dispatch_node_async(_make_node(), "/tmp", "test", timeout=5)

    assert success is False
    assert "timeout" in error
    mock_proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_node_async_failure():
    """dispatch_node_async returns (False, error) on non-zero exit code."""
    from dag_executor import dispatch_node_async

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"something went wrong")
    mock_proc.returncode = 1

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        success, error = await dispatch_node_async(_make_node(), "/tmp", "test")

    assert success is False
    assert "something went wrong" in error


@pytest.mark.asyncio
async def test_dispatch_node_async_no_claude():
    """dispatch_node_async returns (False, error) when claude not in PATH."""
    from dag_executor import dispatch_node_async

    with patch("dag_executor.shutil.which", return_value=None):
        success, error = await dispatch_node_async(_make_node(), "/tmp", "test")

    assert success is False
    assert "claude CLI not found" in error


# --- T005: Tests for dispatch_with_retry_async ---


@pytest.mark.asyncio
async def test_retry_with_async_sleep():
    """dispatch_with_retry_async retries on failure with asyncio.sleep."""
    from dag_executor import dispatch_with_retry_async

    breaker = CircuitBreaker()
    call_count = 0

    async def mock_dispatch(node, cwd, prompt, timeout=3000):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return False, "transient error"
        return True, None

    with (
        patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch),
        patch("dag_executor.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        success, error = await dispatch_with_retry_async(_make_node(), "/tmp", "test", 600, breaker)

    assert success is True
    assert call_count == 3
    assert mock_sleep.await_count == 2  # 2 backoff sleeps


@pytest.mark.asyncio
async def test_circuit_breaker_with_async_dispatch():
    """dispatch_with_retry_async records failure on circuit breaker."""
    from dag_executor import dispatch_with_retry_async

    breaker = CircuitBreaker(max_failures=1)

    async def mock_dispatch(node, cwd, prompt, timeout=3000):
        return False, "permanent error"

    with (
        patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch),
        patch("dag_executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        success, error = await dispatch_with_retry_async(_make_node(), "/tmp", "test", 600, breaker)

    assert success is False
    assert breaker.state == "open"


@pytest.mark.asyncio
async def test_circuit_breaker_open_blocks_dispatch():
    """dispatch_with_retry_async returns immediately when breaker is open."""
    import time

    from dag_executor import dispatch_with_retry_async

    breaker = CircuitBreaker()
    breaker.state = "open"
    breaker.failure_count = 10
    breaker.last_failure_at = time.time()  # recent failure — stays open

    success, error = await dispatch_with_retry_async(_make_node(), "/tmp", "test", 600, breaker)
    assert success is False
    assert "circuit breaker OPEN" in error


# --- Tests for gate dispatch and resume fixes ---


def test_resumable_nodes_excludes_approved_gates():
    """get_resumable_nodes must NOT include nodes with gate_status='approved'."""
    import sqlite3

    from db import get_resumable_nodes

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE epic_nodes (platform_id TEXT, epic_id TEXT, node_id TEXT, "
        "status TEXT, output_hash TEXT, completed_at TEXT, completed_by TEXT, "
        "PRIMARY KEY (platform_id, epic_id, node_id))"
    )
    conn.execute(
        "CREATE TABLE pipeline_runs (run_id TEXT PRIMARY KEY, platform_id TEXT, "
        "epic_id TEXT, node_id TEXT, status TEXT, gate_status TEXT, "
        "agent TEXT, tokens_in INT, tokens_out INT, cost_usd REAL, "
        "duration_ms INT, error TEXT, started_at TEXT, completed_at TEXT, "
        "gate_notified_at TEXT, gate_resolved_at TEXT, telegram_message_id TEXT)"
    )
    # epic-context is done
    conn.execute("INSERT INTO epic_nodes VALUES ('plat', 'e1', 'epic-context', 'done', NULL, '2026-01-01', 'test')")
    # specify has an approved gate but is NOT done in epic_nodes
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, epic_id, node_id, status, gate_status, started_at) "
        "VALUES ('r1', 'plat', 'e1', 'specify', 'running', 'approved', '2026-01-01')"
    )

    result = get_resumable_nodes(conn, "plat", "e1")
    assert "epic-context" in result
    assert "specify" not in result, "approved gate should NOT count as resumable"


@pytest.mark.asyncio
async def test_gate_approved_triggers_dispatch():
    """After gate approval, run_pipeline_async dispatches the node instead of pausing."""
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Minimal schema for the test
    for ddl in [
        "CREATE TABLE platforms (platform_id TEXT PRIMARY KEY, name TEXT, title TEXT, "
        "lifecycle TEXT DEFAULT 'design', repo_path TEXT, metadata TEXT DEFAULT '{}', "
        "created_at TEXT, updated_at TEXT)",
        "CREATE TABLE epics (epic_id TEXT, platform_id TEXT, title TEXT, status TEXT DEFAULT 'proposed', "
        "appetite TEXT, priority INT, branch_name TEXT, file_path TEXT, created_at TEXT, updated_at TEXT, "
        "delivered_at TEXT, PRIMARY KEY (platform_id, epic_id))",
        "CREATE TABLE epic_nodes (platform_id TEXT, epic_id TEXT, node_id TEXT, status TEXT, "
        "output_hash TEXT, completed_at TEXT, completed_by TEXT, "
        "PRIMARY KEY (platform_id, epic_id, node_id))",
        "CREATE TABLE pipeline_nodes (platform_id TEXT, node_id TEXT, status TEXT, "
        "output_hash TEXT, input_hashes TEXT, output_files TEXT, completed_at TEXT, "
        "completed_by TEXT, line_count INT, PRIMARY KEY (platform_id, node_id))",
        "CREATE TABLE pipeline_runs (run_id TEXT PRIMARY KEY, platform_id TEXT, epic_id TEXT, "
        "node_id TEXT, status TEXT DEFAULT 'running', gate_status TEXT, agent TEXT, "
        "tokens_in INT, tokens_out INT, cost_usd REAL, duration_ms INT, error TEXT, "
        "started_at TEXT, completed_at TEXT, gate_notified_at TEXT, gate_resolved_at TEXT, "
        "telegram_message_id TEXT)",
        "CREATE TABLE events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, platform_id TEXT, "
        "entity_type TEXT, entity_id TEXT, action TEXT, actor TEXT, payload TEXT, created_at TEXT)",
    ]:
        conn.execute(ddl)

    # epic-context done, specify has approved gate
    conn.execute(
        "INSERT INTO epic_nodes VALUES ('test-plat', 'e1', 'epic-context', 'done', NULL, '2026-01-01', 'test')"
    )
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, epic_id, node_id, status, gate_status, started_at) "
        "VALUES ('r1', 'test-plat', 'e1', 'specify', 'running', 'approved', '2026-01-01')"
    )

    from dag_executor import run_pipeline_async

    nodes = [
        Node("epic-context", "madruga:epic-context", ["{epic}/pitch.md"], [], "human", "business", False, None),
        Node("specify", "speckit.specify", ["{epic}/spec.md"], ["epic-context"], "human", "business", False, None),
    ]

    dispatch_called = False

    async def mock_dispatch(*args, **kwargs):
        nonlocal dispatch_called
        dispatch_called = True
        return True, None

    with (
        patch("dag_executor.parse_dag", return_value=nodes),
        patch("dag_executor.topological_sort", return_value=nodes),
        patch("dag_executor.dispatch_with_retry_async", side_effect=mock_dispatch),
        patch("dag_executor.verify_outputs", return_value=(True, None)),
        patch("dag_executor.compose_skill_prompt", return_value="test prompt"),
        patch("dag_executor.REPO_ROOT", MagicMock()),
    ):
        result = await run_pipeline_async("test-plat", epic_slug="e1", resume=True, conn=conn)

    assert dispatch_called, "specify should have been dispatched after gate approval"


@pytest.mark.asyncio
async def test_auto_mode_skips_gate_approval():
    """In auto mode, human gates are auto-approved without DB interaction."""
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    for ddl in [
        "CREATE TABLE epic_nodes (platform_id TEXT, epic_id TEXT, node_id TEXT, status TEXT, "
        "output_hash TEXT, completed_at TEXT, completed_by TEXT, PRIMARY KEY (platform_id, epic_id, node_id))",
        "CREATE TABLE pipeline_nodes (platform_id TEXT, node_id TEXT, status TEXT, "
        "output_hash TEXT, input_hashes TEXT, output_files TEXT, completed_at TEXT, "
        "completed_by TEXT, line_count INT, PRIMARY KEY (platform_id, node_id))",
        "CREATE TABLE pipeline_runs (run_id TEXT PRIMARY KEY, platform_id TEXT, epic_id TEXT, "
        "node_id TEXT, status TEXT DEFAULT 'running', gate_status TEXT, agent TEXT, "
        "tokens_in INT, tokens_out INT, cost_usd REAL, duration_ms INT, error TEXT, "
        "started_at TEXT, completed_at TEXT, gate_notified_at TEXT, gate_resolved_at TEXT, "
        "telegram_message_id TEXT)",
        "CREATE TABLE events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, platform_id TEXT, "
        "entity_type TEXT, entity_id TEXT, action TEXT, actor TEXT, payload TEXT, created_at TEXT)",
    ]:
        conn.execute(ddl)

    conn.execute("INSERT INTO epic_nodes VALUES ('p', 'e1', 'epic-context', 'done', NULL, '2026-01-01', 'test')")

    from dag_executor import run_pipeline_async

    nodes = [
        Node("epic-context", "madruga:epic-context", [], [], "human", "business", False, None),
        Node("specify", "speckit.specify", [], ["epic-context"], "human", "business", False, None),
    ]

    dispatched = []

    async def mock_dispatch(node, *args, **kwargs):
        dispatched.append(node.id)
        return True, None

    with (
        patch("dag_executor.parse_dag", return_value=nodes),
        patch("dag_executor.topological_sort", return_value=nodes),
        patch("dag_executor.dispatch_with_retry_async", side_effect=mock_dispatch),
        patch("dag_executor.verify_outputs", return_value=(True, None)),
        patch("dag_executor.compose_skill_prompt", return_value="test"),
        patch("dag_executor.REPO_ROOT", MagicMock()),
    ):
        result = await run_pipeline_async("p", epic_slug="e1", resume=True, conn=conn, gate_mode="auto")

    assert "specify" in dispatched, "auto mode should dispatch without pausing"
    # No waiting_approval runs should exist
    gates = conn.execute("SELECT * FROM pipeline_runs WHERE gate_status='waiting_approval'").fetchall()
    assert len(gates) == 0, "auto mode should not create waiting_approval gates"
