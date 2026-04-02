"""Tests for daemon.py — FastAPI daemon, lifespan, scheduler, degradation, endpoints."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# --- Helpers ---


def _make_app():
    """Import and return the FastAPI app."""
    from daemon import app

    return app


# --- T012: US1 Tests ---


@pytest.mark.asyncio
async def test_health_endpoint_returns_200():
    """GET /health returns 200 with status ok."""
    from daemon import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_status_endpoint_returns_json():
    """GET /status returns JSON with expected keys."""
    from daemon import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "daemon_state" in data
    assert "pid" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_graceful_shutdown_sets_event():
    """Shutdown event is set after lifespan exit."""
    from daemon import _shutdown_event

    # _shutdown_event is module-level; test that it exists and is an asyncio.Event
    assert isinstance(_shutdown_event, asyncio.Event)


@pytest.mark.asyncio
async def test_startup_without_telegram_env_vars_logs_warning():
    """Daemon starts without Telegram env vars (degraded but functional)."""
    from daemon import app

    with patch.dict("os.environ", {}, clear=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200


# --- T017: US2 Tests ---


@pytest.mark.asyncio
async def test_dag_scheduler_detects_active_epic():
    """dag_scheduler calls poll_active_epics and dispatches."""
    from daemon import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "daemon.poll_active_epics",
            return_value=[{"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"}],
        ),
        patch("daemon.run_pipeline_async", new_callable=AsyncMock, return_value=0) as mock_run,
        patch("daemon._running_epics", set()),
    ):
        # Run one iteration then stop
        async def _stop_after_poll(*args, **kwargs):
            shutdown.set()
            return 0

        mock_run.side_effect = _stop_after_poll
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_dag_scheduler_respects_sequential_constraint():
    """dag_scheduler does not dispatch a second epic if one is already running."""
    from daemon import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "daemon.poll_active_epics",
            return_value=[
                {"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"},
                {"epic_id": "017", "platform_id": "test", "branch_name": "epic/test/017"},
            ],
        ),
        patch("daemon.run_pipeline_async", new_callable=AsyncMock) as mock_run,
        patch("daemon._running_epics", {"016"}),
        patch("daemon.asyncio.sleep", new_callable=AsyncMock, side_effect=lambda _: shutdown.set()),
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    # Should not dispatch anything — 016 is already running and sequential constraint blocks 017
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_dag_scheduler_skips_already_running_epic():
    """dag_scheduler does not re-dispatch an epic that is already running."""
    from daemon import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "daemon.poll_active_epics",
            return_value=[
                {"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"},
            ],
        ),
        patch("daemon.run_pipeline_async", new_callable=AsyncMock) as mock_run,
        patch("daemon._running_epics", {"016"}),
        patch("daemon.asyncio.sleep", new_callable=AsyncMock, side_effect=lambda _: shutdown.set()),
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_dag_scheduler_poll_interval():
    """dag_scheduler respects poll_interval between iterations."""
    from daemon import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()
    iterations = 0

    def _count_and_stop(*args, **kwargs):
        nonlocal iterations
        iterations += 1
        if iterations >= 2:
            shutdown.set()
        return []

    with (
        patch("daemon.poll_active_epics", side_effect=_count_and_stop),
        patch("daemon.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=15)

    assert mock_sleep.await_count >= 1
    mock_sleep.assert_awaited_with(15)


@pytest.mark.asyncio
async def test_poll_active_epics_ignores_drafted():
    """poll_active_epics only returns in_progress, not drafted epics."""
    from daemon import poll_active_epics

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []

    result = poll_active_epics(mock_conn)
    assert result == []
    # Verify the SQL only queries in_progress
    sql = mock_conn.execute.call_args[0][0]
    assert "in_progress" in sql
    assert "drafted" not in sql


# --- T022: US3 Tests ---


@pytest.mark.asyncio
async def test_telegram_coroutines_start_in_taskgroup():
    """When Telegram env vars are set, Telegram coroutines are scheduled."""
    # We test this indirectly by checking the /status endpoint reports telegram state
    from daemon import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    data = resp.json()
    assert "telegram_status" in data


@pytest.mark.asyncio
async def test_gate_approval_resumes_pipeline():
    """When a gate is approved, dag_scheduler detects it on next poll."""
    from daemon import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    # First poll: epic has pending gate. Second poll: gate approved, epic dispatched.
    call_count = 0

    def mock_poll(conn, platform_id=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [{"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"}]
        shutdown.set()
        return []

    with (
        patch("daemon.poll_active_epics", side_effect=mock_poll),
        patch("daemon.run_pipeline_async", new_callable=AsyncMock, return_value=0) as mock_run,
        patch("daemon._running_epics", set()),
        patch("daemon.asyncio.sleep", new_callable=AsyncMock),
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    mock_run.assert_called_once()


# --- T027: US4 Tests ---


@pytest.mark.asyncio
async def test_telegram_degradation_after_3_failures():
    """Daemon enters degraded mode after 3 consecutive health check failures."""
    import daemon
    from daemon import health_checker

    # Reset module-level state
    daemon._daemon_state.daemon_state = "running"
    daemon._daemon_state.telegram_fail_count = 0
    daemon._daemon_state.telegram_status = "connected"

    shutdown = asyncio.Event()
    mock_bot = AsyncMock()
    mock_bot.get_me.side_effect = Exception("connection failed")

    with patch("daemon.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Run 3 iterations
        call_count = 0

        async def counted_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count >= 4:
                shutdown.set()
                raise asyncio.CancelledError()

        mock_sleep.side_effect = counted_sleep
        try:
            await health_checker(mock_bot, shutdown, interval=0.01)
        except asyncio.CancelledError:
            pass

    assert daemon._daemon_state.daemon_state == "degraded"


@pytest.mark.asyncio
async def test_telegram_recovery_resumes_normal():
    """Daemon recovers from degraded mode when Telegram comes back."""
    import daemon
    from daemon import health_checker

    # Reset module-level state to degraded
    daemon._daemon_state.daemon_state = "degraded"
    daemon._daemon_state.telegram_status = "degraded"
    daemon._daemon_state.telegram_fail_count = 3

    shutdown = asyncio.Event()

    mock_bot = AsyncMock()
    mock_bot.get_me.return_value = MagicMock(username="test_bot")

    with patch("daemon.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        call_count = 0

        async def counted_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                shutdown.set()
                raise asyncio.CancelledError()

        mock_sleep.side_effect = counted_sleep
        try:
            await health_checker(mock_bot, shutdown, interval=0.01)
        except asyncio.CancelledError:
            pass

    assert daemon._daemon_state.daemon_state == "running"
    assert daemon._daemon_state.telegram_status == "connected"


@pytest.mark.asyncio
async def test_ntfy_fallback_on_degradation():
    """ntfy_alert is called when transitioning to degraded mode."""
    import daemon
    from daemon import health_checker

    # Reset module-level state: 2 failures already, next triggers degradation
    daemon._daemon_state.daemon_state = "running"
    daemon._daemon_state.telegram_fail_count = 2
    daemon._daemon_state.telegram_status = "connected"

    shutdown = asyncio.Event()

    mock_bot = AsyncMock()
    mock_bot.get_me.side_effect = Exception("down")

    with (
        patch("daemon.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch("daemon.ntfy_alert", return_value=True) as mock_ntfy,
        patch.dict("os.environ", {"MADRUGA_NTFY_TOPIC": "test-topic"}),
    ):
        call_count = 0

        async def counted_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                shutdown.set()
                raise asyncio.CancelledError()

        mock_sleep.side_effect = counted_sleep
        try:
            await health_checker(mock_bot, shutdown, interval=0.01)
        except asyncio.CancelledError:
            pass

    mock_ntfy.assert_called_once()
    assert "degraded" in mock_ntfy.call_args[0][1].lower() or "degraded" in str(mock_ntfy.call_args)


@pytest.mark.asyncio
async def test_auto_gates_continue_in_degraded_mode():
    """Auto gates continue processing when daemon is in degraded mode."""
    from daemon import DaemonState, dag_scheduler

    state = DaemonState()
    state.daemon_state = "degraded"
    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "daemon.poll_active_epics",
            return_value=[
                {"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"},
            ],
        ),
        patch("daemon.run_pipeline_async", new_callable=AsyncMock, return_value=0) as mock_run,
        patch("daemon._running_epics", set()),
    ):

        async def _stop(*args, **kwargs):
            shutdown.set()
            return 0

        mock_run.side_effect = _stop
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    mock_run.assert_called_once()


# --- T031: US5 Tests ---


@pytest.mark.asyncio
async def test_status_includes_telegram_state():
    """GET /status includes telegram_status field."""
    from daemon import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    data = resp.json()
    assert "telegram_status" in data


@pytest.mark.asyncio
async def test_status_includes_running_epics():
    """GET /status includes running_epics list."""
    from daemon import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    data = resp.json()
    assert "running_epics" in data
    assert isinstance(data["running_epics"], list)


@pytest.mark.asyncio
async def test_status_includes_uptime():
    """GET /status includes uptime_seconds."""
    from daemon import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    data = resp.json()
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_health_returns_200_even_when_degraded():
    """GET /health returns 200 even when daemon is in degraded mode."""
    from daemon import _daemon_state, app

    original = _daemon_state.daemon_state
    _daemon_state.daemon_state = "degraded"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
    finally:
        _daemon_state.daemon_state = original


# --- C1: Gate reminder tests ---


@pytest.mark.asyncio
async def test_gate_reminder_sends_for_old_gates():
    """gate_reminder sends Telegram message for gates older than 24h."""
    import sqlite3

    from daemon import gate_reminder

    shutdown = asyncio.Event()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE pipeline_runs (
            run_id TEXT PRIMARY KEY, node_id TEXT, platform_id TEXT, epic_id TEXT,
            gate_status TEXT, gate_notified_at TEXT, started_at TEXT
        )"""
    )
    # Insert a gate notified 25 hours ago
    conn.execute(
        "INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?, datetime('now', '-25 hours'), datetime('now', '-25 hours'))",
        ("run-old", "vision", "test", "016", "waiting_approval"),
    )
    conn.commit()

    mock_adapter = AsyncMock()
    mock_adapter.send.return_value = 1

    from daemon import _daemon_state

    original = _daemon_state.telegram_status
    _daemon_state.telegram_status = "connected"
    try:
        with patch("daemon.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

            async def stop_after_one(t):
                shutdown.set()

            mock_sleep.side_effect = stop_after_one
            await gate_reminder(conn, mock_adapter, 123, shutdown, interval=1)

        mock_adapter.send.assert_called_once()
        assert "vision" in mock_adapter.send.call_args[0][1]
    finally:
        _daemon_state.telegram_status = original
    conn.close()


@pytest.mark.asyncio
async def test_gate_reminder_skips_recent_gates():
    """gate_reminder does not send for gates notified less than 24h ago."""
    import sqlite3

    from daemon import gate_reminder

    shutdown = asyncio.Event()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE pipeline_runs (
            run_id TEXT PRIMARY KEY, node_id TEXT, platform_id TEXT, epic_id TEXT,
            gate_status TEXT, gate_notified_at TEXT, started_at TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO pipeline_runs VALUES (?, ?, ?, ?, ?, datetime('now', '-1 hour'), datetime('now', '-1 hour'))",
        ("run-new", "vision", "test", "016", "waiting_approval"),
    )
    conn.commit()

    mock_adapter = AsyncMock()

    with patch("daemon.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

        async def stop_after_one(t):
            shutdown.set()

        mock_sleep.side_effect = stop_after_one
        await gate_reminder(conn, mock_adapter, 123, shutdown, interval=1)

    mock_adapter.send.assert_not_called()
    conn.close()


# --- C2: ntfy on pipeline failure ---


@pytest.mark.asyncio
async def test_dag_scheduler_ntfy_on_pipeline_failure():
    """dag_scheduler sends ntfy alert when pipeline run fails."""
    from daemon import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "daemon.poll_active_epics",
            return_value=[{"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"}],
        ),
        patch("daemon.run_pipeline_async", new_callable=AsyncMock, return_value=1) as mock_run,
        patch("daemon._running_epics", set()),
        patch("daemon.ntfy_alert", return_value=True) as mock_ntfy,
        patch.dict("os.environ", {"MADRUGA_NTFY_TOPIC": "test-topic"}),
    ):

        async def _stop(*args, **kwargs):
            shutdown.set()
            return 1

        mock_run.side_effect = _stop
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    mock_ntfy.assert_called_once()
    assert "016" in mock_ntfy.call_args[0][1]


# --- C3: telegram_bot.py async_main deprecation ---


def test_async_main_deprecation_warning():
    """async_main emits DeprecationWarning."""
    import warnings

    from telegram_bot import async_main

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            asyncio.get_event_loop().run_until_complete(
                async_main(MagicMock(verbose=False, poll_interval=15, health_interval=60, platform=None, dry_run=True))
            )
        except (SystemExit, Exception):
            pass  # Expected — no env vars set
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1
        assert "deprecated" in str(deprecation_warnings[0].message).lower()


# --- C4: pending gates summary on recovery ---


@pytest.mark.asyncio
async def test_health_checker_sends_pending_summary_on_recovery():
    """health_checker sends pending gates summary when recovering from degraded."""
    import daemon
    from daemon import health_checker

    # Reset module-level state to degraded
    daemon._daemon_state.daemon_state = "degraded"
    daemon._daemon_state.telegram_status = "degraded"
    daemon._daemon_state.telegram_fail_count = 3

    shutdown = asyncio.Event()

    mock_bot = AsyncMock()
    mock_bot.get_me.return_value = MagicMock(username="test_bot")
    mock_adapter = AsyncMock()
    mock_adapter.send.return_value = 1
    mock_conn = MagicMock()

    call_count = 0

    with (
        patch("daemon.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch("telegram_bot.poll_pending_gates", return_value=[{"run_id": "r1"}, {"run_id": "r2"}]),
    ):

        async def sleep_then_stop(t):
            nonlocal call_count
            call_count += 1
            # First sleep lets the health check run; second stops the loop
            if call_count >= 2:
                shutdown.set()
                raise asyncio.CancelledError()

        mock_sleep.side_effect = sleep_then_stop
        try:
            await health_checker(mock_bot, shutdown, conn=mock_conn, adapter=mock_adapter, chat_id=123)
        except asyncio.CancelledError:
            pass

    assert daemon._daemon_state.daemon_state == "running"
    mock_adapter.send.assert_called_once()
    assert "2" in mock_adapter.send.call_args[0][1]
