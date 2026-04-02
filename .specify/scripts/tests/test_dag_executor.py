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

    with patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc):
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

    with patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc):
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

    with patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc):
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

    async def mock_dispatch(node, cwd, prompt, timeout=600):
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

    async def mock_dispatch(node, cwd, prompt, timeout=600):
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
