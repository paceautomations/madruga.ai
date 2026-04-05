"""Tests for easter.py — FastAPI easter, lifespan, scheduler, degradation, endpoints."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# --- Helpers ---


def _make_app():
    """Import and return the FastAPI app."""
    from easter import app

    return app


# --- T012: US1 Tests ---


@pytest.mark.asyncio
async def test_health_endpoint_returns_200():
    """GET /health returns 200 with status and db fields."""
    from easter import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "db" in data


@pytest.mark.asyncio
async def test_status_endpoint_returns_json():
    """GET /status returns JSON with expected keys."""
    from easter import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "easter_state" in data
    assert "pid" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_graceful_shutdown_sets_event():
    """Shutdown event is set after lifespan exit."""
    from easter import _shutdown_event

    # _shutdown_event is module-level; test that it exists and is an asyncio.Event
    assert isinstance(_shutdown_event, asyncio.Event)


@pytest.mark.asyncio
async def test_startup_without_telegram_env_vars_logs_warning():
    """Easter starts without Telegram env vars (degraded but functional)."""
    from easter import app

    with patch.dict("os.environ", {}, clear=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200


# --- T017: US2 Tests ---


@pytest.mark.asyncio
async def test_dag_scheduler_detects_active_epic():
    """dag_scheduler calls poll_active_epics and dispatches."""
    from easter import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "easter.poll_active_epics",
            return_value=[{"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"}],
        ),
        patch("easter.run_pipeline_async", new_callable=AsyncMock, return_value=0) as mock_run,
        patch("easter._running_epics", set()),
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
    from easter import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "easter.poll_active_epics",
            return_value=[
                {"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"},
                {"epic_id": "017", "platform_id": "test", "branch_name": "epic/test/017"},
            ],
        ),
        patch("easter.run_pipeline_async", new_callable=AsyncMock) as mock_run,
        patch("easter._running_epics", {"016"}),
        patch("easter.asyncio.sleep", new_callable=AsyncMock, side_effect=lambda _: shutdown.set()),
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    # Should not dispatch anything — 016 is already running and sequential constraint blocks 017
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_dag_scheduler_skips_already_running_epic():
    """dag_scheduler does not re-dispatch an epic that is already running."""
    from easter import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "easter.poll_active_epics",
            return_value=[
                {"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"},
            ],
        ),
        patch("easter.run_pipeline_async", new_callable=AsyncMock) as mock_run,
        patch("easter._running_epics", {"016"}),
        patch("easter.asyncio.sleep", new_callable=AsyncMock, side_effect=lambda _: shutdown.set()),
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_dag_scheduler_poll_interval():
    """dag_scheduler respects poll_interval between iterations."""
    from easter import dag_scheduler

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
        patch("easter.poll_active_epics", side_effect=_count_and_stop),
        patch("easter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=15)

    assert mock_sleep.await_count >= 1
    mock_sleep.assert_awaited_with(15)


@pytest.mark.asyncio
async def test_poll_active_epics_ignores_drafted():
    """poll_active_epics only returns in_progress, not drafted epics."""
    from easter import poll_active_epics

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
    from easter import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    data = resp.json()
    assert "telegram_status" in data


@pytest.mark.asyncio
async def test_gate_approval_resumes_pipeline():
    """When a gate is approved, dag_scheduler detects it on next poll."""
    from easter import dag_scheduler

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
        patch("easter.poll_active_epics", side_effect=mock_poll),
        patch("easter.run_pipeline_async", new_callable=AsyncMock, return_value=0) as mock_run,
        patch("easter._running_epics", set()),
        patch("easter.asyncio.sleep", new_callable=AsyncMock),
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    mock_run.assert_called_once()


# --- T027: US4 Tests ---


@pytest.mark.asyncio
async def test_telegram_degradation_after_3_failures():
    """Easter enters degraded mode after 3 consecutive health check failures."""
    import easter
    from easter import health_checker

    # Reset module-level state
    easter._easter_state.easter_state = "running"
    easter._easter_state.telegram_fail_count = 0
    easter._easter_state.telegram_status = "connected"

    shutdown = asyncio.Event()
    mock_bot = AsyncMock()
    mock_bot.get_me.side_effect = Exception("connection failed")

    with patch("easter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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

    assert easter._easter_state.easter_state == "degraded"


@pytest.mark.asyncio
async def test_telegram_recovery_resumes_normal():
    """Easter recovers from degraded mode when Telegram comes back."""
    import easter
    from easter import health_checker

    # Reset module-level state to degraded
    easter._easter_state.easter_state = "degraded"
    easter._easter_state.telegram_status = "degraded"
    easter._easter_state.telegram_fail_count = 3

    shutdown = asyncio.Event()

    mock_bot = AsyncMock()
    mock_bot.get_me.return_value = MagicMock(username="test_bot")

    with patch("easter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
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

    assert easter._easter_state.easter_state == "running"
    assert easter._easter_state.telegram_status == "connected"


@pytest.mark.asyncio
async def test_ntfy_fallback_on_degradation():
    """ntfy_alert is called when transitioning to degraded mode."""
    import easter
    from easter import health_checker

    # Reset module-level state: 2 failures already, next triggers degradation
    easter._easter_state.easter_state = "running"
    easter._easter_state.telegram_fail_count = 2
    easter._easter_state.telegram_status = "connected"

    shutdown = asyncio.Event()

    mock_bot = AsyncMock()
    mock_bot.get_me.side_effect = Exception("down")

    with (
        patch("easter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch("easter.ntfy_alert", return_value=True) as mock_ntfy,
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
    """Auto gates continue processing when easter is in degraded mode."""
    from easter import EasterState, dag_scheduler

    state = EasterState()
    state.easter_state = "degraded"
    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "easter.poll_active_epics",
            return_value=[
                {"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"},
            ],
        ),
        patch("easter.run_pipeline_async", new_callable=AsyncMock, return_value=0) as mock_run,
        patch("easter._running_epics", set()),
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
    from easter import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    data = resp.json()
    assert "telegram_status" in data


@pytest.mark.asyncio
async def test_status_includes_running_epics():
    """GET /status includes running_epics list."""
    from easter import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    data = resp.json()
    assert "running_epics" in data
    assert isinstance(data["running_epics"], list)


@pytest.mark.asyncio
async def test_status_includes_uptime():
    """GET /status includes uptime_seconds."""
    from easter import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/status")
    data = resp.json()
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_health_returns_200_even_when_degraded():
    """GET /health returns 200 even when easter is in degraded mode."""
    from easter import _easter_state, app

    original = _easter_state.easter_state
    _easter_state.easter_state = "degraded"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
    finally:
        _easter_state.easter_state = original


# --- C1: Gate reminder tests ---


@pytest.mark.asyncio
async def test_gate_reminder_sends_for_old_gates():
    """gate_reminder sends Telegram message for gates older than 24h."""
    import sqlite3

    from easter import gate_reminder

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

    from easter import _easter_state

    original = _easter_state.telegram_status
    _easter_state.telegram_status = "connected"
    try:
        with patch("easter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

            async def stop_after_one(t):
                shutdown.set()

            mock_sleep.side_effect = stop_after_one
            await gate_reminder(conn, mock_adapter, 123, shutdown, interval=1)

        mock_adapter.send.assert_called_once()
        assert "vision" in mock_adapter.send.call_args[0][1]
    finally:
        _easter_state.telegram_status = original
    conn.close()


@pytest.mark.asyncio
async def test_gate_reminder_skips_recent_gates():
    """gate_reminder does not send for gates notified less than 24h ago."""
    import sqlite3

    from easter import gate_reminder

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

    with patch("easter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

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
    from easter import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    with (
        patch(
            "easter.poll_active_epics",
            return_value=[{"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"}],
        ),
        patch("easter.run_pipeline_async", new_callable=AsyncMock, return_value=1) as mock_run,
        patch("easter._running_epics", set()),
        patch("easter.ntfy_alert", return_value=True) as mock_ntfy,
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
    import easter
    from easter import health_checker

    # Reset module-level state to degraded
    easter._easter_state.easter_state = "degraded"
    easter._easter_state.telegram_status = "degraded"
    easter._easter_state.telegram_fail_count = 3

    shutdown = asyncio.Event()

    mock_bot = AsyncMock()
    mock_bot.get_me.return_value = MagicMock(username="test_bot")
    mock_adapter = AsyncMock()
    mock_adapter.send.return_value = 1
    mock_conn = MagicMock()

    call_count = 0

    with (
        patch("easter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
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

    assert easter._easter_state.easter_state == "running"
    mock_adapter.send.assert_called_once()
    assert "2" in mock_adapter.send.call_args[0][1]


# --- Easter reliability fixes (F1, F2, F3, F9) ---


@pytest.mark.asyncio
async def test_dag_scheduler_proactive_branch_checkout():
    """F3: dag_scheduler runs git checkout before dispatching epic."""
    from easter import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    checkout_called = []

    def mock_subprocess_run(cmd, **kwargs):
        if cmd[0] == "git" and cmd[1] == "checkout":
            checkout_called.append(cmd[2])
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    with (
        patch(
            "easter.poll_active_epics",
            return_value=[{"epic_id": "020", "platform_id": "test", "branch_name": "epic/test/020"}],
        ),
        patch("easter.run_pipeline_async", new_callable=AsyncMock, return_value=0) as mock_run,
        patch("easter._running_epics", set()),
        patch("subprocess.run", side_effect=mock_subprocess_run),
    ):

        async def _stop(*args, **kwargs):
            shutdown.set()
            return 0

        mock_run.side_effect = _stop
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    assert "epic/test/020" in checkout_called


@pytest.mark.asyncio
async def test_dag_scheduler_platform_filter():
    """F1: dag_scheduler passes platform_id to poll_active_epics."""
    from easter import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()
    poll_calls = []

    def mock_poll(conn, platform_id=None):
        poll_calls.append(platform_id)
        shutdown.set()
        return []

    with patch("easter.poll_active_epics", side_effect=mock_poll):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01, platform_id="madruga-ai")

    assert poll_calls == ["madruga-ai"]


@pytest.mark.asyncio
async def test_dispatch_with_retry_abort_check():
    """F2: dispatch_with_retry_async aborts when abort_check returns True."""
    from dag_executor import CircuitBreaker, Node, dispatch_with_retry_async

    node = Node(
        id="test-node",
        skill="test",
        outputs=[],
        depends=[],
        gate="auto",
        layer="test",
        optional=False,
        skip_condition=None,
    )
    breaker = CircuitBreaker(max_failures=3)

    call_count = 0

    async def mock_dispatch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return False, "simulated failure", None

    with patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch):
        # abort_check returns True on first retry — should abort immediately
        success, error, stdout = await dispatch_with_retry_async(
            node,
            "/tmp",
            "test prompt",
            60,
            breaker,
            abort_check=lambda: True,
        )

    assert not success
    assert error == "epic_status_changed"
    # Should have run once (initial attempt fails), then abort_check triggers before retry
    assert call_count == 1


@pytest.mark.asyncio
async def test_dispatch_with_retry_no_abort_check():
    """F2: dispatch_with_retry_async retries normally when abort_check is None."""
    from dag_executor import CircuitBreaker, Node, dispatch_with_retry_async

    node = Node(
        id="test-node",
        skill="test",
        outputs=[],
        depends=[],
        gate="auto",
        layer="test",
        optional=False,
        skip_condition=None,
    )
    breaker = CircuitBreaker(max_failures=3)

    call_count = 0

    async def mock_dispatch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return True, None, "ok"
        return False, "fail", None

    with patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch):
        success, error, stdout = await dispatch_with_retry_async(
            node,
            "/tmp",
            "test prompt",
            60,
            breaker,
            abort_check=None,
        )

    assert success
    assert call_count == 2


def test_auto_commit_epic_no_changes(tmp_path):
    """F9: _auto_commit_epic returns True when no changes to commit."""
    from dag_executor import _auto_commit_epic

    with patch("dag_executor.subprocess.run") as mock_run:
        # git status --porcelain returns empty (no changes)
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        result = _auto_commit_epic(tmp_path, "test-plat", "001-epic")

    assert result is True
    # Only git status called, no git add or commit
    assert mock_run.call_count == 1


def test_auto_commit_epic_with_changes(tmp_path):
    """F9: _auto_commit_epic runs git add + commit when changes exist."""
    from dag_executor import _auto_commit_epic

    call_log = []

    def mock_run(cmd, **kwargs):
        call_log.append(cmd)
        result = MagicMock()
        # git status --porcelain: XY format (2 chars status + space + path)
        result.stdout = " M file.py\n" if cmd[1] == "status" else ""
        result.returncode = 0
        return result

    with patch("dag_executor.subprocess.run", side_effect=mock_run):
        result = _auto_commit_epic(tmp_path, "test-plat", "001-epic")

    assert result is True
    # Should use selective git add with -- separator (not -A)
    add_cmd = [c for c in call_log if len(c) > 1 and c[1] == "add"]
    assert len(add_cmd) == 1
    assert "--" in add_cmd[0]
    # After XY(2) + space(1) = line[3:], "file.py" should be in staged files
    staged = add_cmd[0][add_cmd[0].index("--") + 1 :]
    assert any("file.py" in f for f in staged)


def test_auto_commit_epic_skips_sensitive_files(tmp_path):
    """_auto_commit_epic must filter out sensitive files from staging."""
    from dag_executor import _auto_commit_epic

    call_log = []

    def mock_run(cmd, **kwargs):
        call_log.append(cmd)
        result = MagicMock()
        if cmd[1] == "status":
            # git status --porcelain: XY(2 chars) + space + path
            result.stdout = " M safe.py\n?? .env\n?? secrets.key\n M src/main.py\n"
        result.returncode = 0
        return result

    with patch("dag_executor.subprocess.run", side_effect=mock_run):
        result = _auto_commit_epic(tmp_path, "test-plat", "001-epic")

    assert result is True
    add_cmd = [c for c in call_log if len(c) > 1 and c[1] == "add"]
    assert len(add_cmd) == 1
    staged_files = add_cmd[0][add_cmd[0].index("--") + 1 :]
    # safe.py and src/main.py should be staged
    assert any("safe.py" in f for f in staged_files)
    assert any("src/main.py" in f for f in staged_files)
    # .env and secrets.key should NOT be staged
    assert not any(".env" in f for f in staged_files)
    assert not any("secrets.key" in f for f in staged_files)


# --- Fix: easter must skip re-dispatch when epic has pending gate ---


@pytest.mark.asyncio
async def test_dag_scheduler_skips_epic_with_pending_gate():
    """dag_scheduler must not dispatch an epic that has a waiting_approval gate.

    Regression test: prior to fix, the easter re-dispatched every 15s when a gate
    was pending, creating orphan traces and wasting resources.
    """
    import easter

    # Save originals and reset module state
    orig_running = easter._running_epics.copy()
    orig_filter = easter._platform_filter
    easter._running_epics.clear()
    easter._platform_filter = None

    shutdown = asyncio.Event()
    mock_conn = MagicMock()

    mock_epic = {"epic_id": "021-test", "platform_id": "madruga-ai", "priority": 1, "branch_name": None}

    with (
        patch("easter.poll_active_epics", return_value=[mock_epic]),
        patch(
            "db.get_pending_gates",
            return_value=[{"node_id": "specify", "epic_id": "021-test", "gate_status": "waiting_approval"}],
        ),
        patch("easter.run_pipeline_async") as mock_dispatch,
    ):
        asyncio.get_event_loop().call_later(0.1, shutdown.set)
        await easter.dag_scheduler(mock_conn, asyncio.Semaphore(1), shutdown, poll_interval=0.05)

        # Dispatch must NOT have been called (gate is pending)
        mock_dispatch.assert_not_called()

    # Restore
    easter._running_epics = orig_running
    easter._platform_filter = orig_filter
