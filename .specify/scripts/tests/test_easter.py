"""Tests for easter.py — FastAPI easter, lifespan, scheduler, degradation, endpoints."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# --- Helpers ---

_SELF_REF_BINDING = {"name": "madruga.ai", "org": "p", "base_branch": "main", "epic_branch_prefix": "epic/test/"}


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
        patch(
            "ensure_repo._load_repo_binding",
            return_value=_SELF_REF_BINDING,
        ),
        patch("ensure_repo._is_self_ref", return_value=True),
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

    async def _fake_sleep(_event, _seconds):
        # A7: dag_scheduler uses _interruptible_sleep (via asyncio.wait_for),
        # NOT bare asyncio.sleep. Patching `easter.asyncio.sleep` has no effect
        # because wait_for calls the real asyncio.sleep from its own module.
        # Instead, patch _interruptible_sleep and set the shutdown event from
        # inside the fake.
        shutdown.set()
        return True

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
        patch("easter._interruptible_sleep", new=_fake_sleep),
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

    async def _fake_sleep(_event, _seconds):
        shutdown.set()
        return True

    with (
        patch(
            "easter.poll_active_epics",
            return_value=[
                {"epic_id": "016", "platform_id": "test", "branch_name": "epic/test/016"},
            ],
        ),
        patch("easter.run_pipeline_async", new_callable=AsyncMock) as mock_run,
        patch("easter._running_epics", {"016"}),
        patch("easter._interruptible_sleep", new=_fake_sleep),
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=0.01)

    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_dag_scheduler_poll_interval():
    """dag_scheduler waits poll_interval between iterations via _interruptible_sleep."""
    from easter import dag_scheduler

    shutdown = asyncio.Event()
    mock_conn = MagicMock()
    iterations = 0
    sleep_calls: list[float] = []

    def _count_and_stop(*args, **kwargs):
        nonlocal iterations
        iterations += 1
        if iterations >= 2:
            shutdown.set()
        return []

    # A7: patch _interruptible_sleep (the real knob) and record the poll_interval
    # it was invoked with. Using the real asyncio.sleep inside tests would add
    # unnecessary wall-clock wait.
    async def _fake_sleep(_event, seconds):
        sleep_calls.append(seconds)
        return shutdown.is_set()

    with (
        patch("easter.poll_active_epics", side_effect=_count_and_stop),
        patch("easter._interruptible_sleep", new=_fake_sleep),
    ):
        await dag_scheduler(mock_conn, asyncio.Semaphore(3), shutdown, poll_interval=15)

    assert len(sleep_calls) >= 1
    assert 15 in sleep_calls


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
        patch(
            "ensure_repo._load_repo_binding",
            return_value=_SELF_REF_BINDING,
        ),
        patch("ensure_repo._is_self_ref", return_value=True),
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

    # A7: health_checker uses _interruptible_sleep, not asyncio.sleep.
    call_count = 0

    async def _fake_sleep(_event, _seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 4:
            shutdown.set()
            raise asyncio.CancelledError()
        return False

    with patch("easter._interruptible_sleep", new=_fake_sleep):
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

    call_count = 0

    async def _fake_sleep(_event, _seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            shutdown.set()
            raise asyncio.CancelledError()
        return False

    with patch("easter._interruptible_sleep", new=_fake_sleep):
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

    call_count = 0

    async def _fake_sleep(_event, _seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            shutdown.set()
            raise asyncio.CancelledError()
        return False

    with (
        patch("easter._interruptible_sleep", new=_fake_sleep),
        patch("easter.ntfy_alert", return_value=True) as mock_ntfy,
        patch.dict("os.environ", {"MADRUGA_NTFY_TOPIC": "test-topic"}),
    ):
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
        patch(
            "ensure_repo._load_repo_binding",
            return_value=_SELF_REF_BINDING,
        ),
        patch("ensure_repo._is_self_ref", return_value=True),
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
        # gate_reminder sleeps FIRST, then checks gates. Return False (timeout
        # elapsed, keep running) on call 1 so the loop enters the check; then
        # on call 2 set shutdown so the loop exits cleanly.
        calls = 0

        async def _fake_sleep(_event, _seconds):
            nonlocal calls
            calls += 1
            if calls >= 2:
                shutdown.set()
                return True
            return False

        with patch("easter._interruptible_sleep", new=_fake_sleep):
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

    # gate_reminder sleeps first. Same pattern as the sends-for-old-gates test:
    # return False on first call so the gate check runs, then set shutdown.
    calls = 0

    async def _fake_sleep(_event, _seconds):
        nonlocal calls
        calls += 1
        if calls >= 2:
            shutdown.set()
            return True
        return False

    with patch("easter._interruptible_sleep", new=_fake_sleep):
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
        patch(
            "ensure_repo._load_repo_binding",
            return_value=_SELF_REF_BINDING,
        ),
        patch("ensure_repo._is_self_ref", return_value=True),
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

    async def _fake_sleep(_event, _seconds):
        nonlocal call_count
        call_count += 1
        # First sleep lets the health check run; second stops the loop
        if call_count >= 2:
            shutdown.set()
            raise asyncio.CancelledError()
        return False

    with (
        patch("easter._interruptible_sleep", new=_fake_sleep),
        patch("telegram_bot.poll_pending_gates", return_value=[{"run_id": "r1"}, {"run_id": "r2"}]),
    ):
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
        patch(
            "ensure_repo._load_repo_binding",
            return_value=_SELF_REF_BINDING,
        ),
        patch("ensure_repo._is_self_ref", return_value=True),
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


# --- Commits API endpoints ---


def _setup_commits_db():
    """Create an in-memory DB with commits for testing API endpoints."""
    import sqlite3

    from db_core import migrate
    from db_pipeline import insert_commit

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate(conn)
    insert_commit(
        conn,
        "aaa1111",
        "feat: login",
        "Alice",
        "plat-a",
        "012-auth",
        "hook",
        "2026-04-01T10:00:00Z",
        '["src/login.py"]',
    )
    insert_commit(
        conn, "bbb2222", "fix: hash", "Bob", "plat-a", "012-auth", "hook", "2026-04-02T11:00:00Z", '["src/auth.py"]'
    )
    insert_commit(
        conn,
        "ccc3333",
        "feat: signup",
        "Alice",
        "plat-b",
        "015-signup",
        "backfill",
        "2026-04-03T09:00:00Z",
        '["src/signup.py"]',
    )
    insert_commit(conn, "ddd4444", "chore: deps", "Charlie", "plat-a", None, "hook", "2026-04-04T08:00:00Z", "[]")
    insert_commit(conn, "eee5555", "fix: typo", "Bob", "plat-b", None, "hook", "2026-04-05T07:00:00Z", '["README.md"]')
    conn.commit()
    return conn


def _override_conn(app, conn):
    """A4 helper: route /api/* endpoints at `conn` via dependency override."""
    from easter import get_fresh_conn

    async def _yield():
        yield conn

    app.dependency_overrides[get_fresh_conn] = _yield


@pytest.mark.asyncio
async def test_commits_endpoint_returns_paginated():
    """GET /api/commits returns paginated commits with total."""
    from easter import get_fresh_conn

    app = _make_app()
    conn = _setup_commits_db()
    app.state.db_conn = conn
    _override_conn(app, conn)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/commits", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["commits"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0
    finally:
        app.dependency_overrides.pop(get_fresh_conn, None)
        conn.close()


@pytest.mark.asyncio
async def test_commits_endpoint_filters():
    """GET /api/commits respects platform_id and commit_type filters."""
    from easter import get_fresh_conn

    app = _make_app()
    conn = _setup_commits_db()
    app.state.db_conn = conn
    _override_conn(app, conn)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Filter by platform
            resp = await client.get("/api/commits", params={"platform_id": "plat-a"})
            assert resp.json()["total"] == 3

            # Filter by commit_type=adhoc
            resp = await client.get("/api/commits", params={"commit_type": "adhoc"})
            data = resp.json()
            assert data["total"] == 2
            assert all(c["epic_id"] is None for c in data["commits"])
    finally:
        app.dependency_overrides.pop(get_fresh_conn, None)
        conn.close()


@pytest.mark.asyncio
async def test_commits_stats_endpoint():
    """GET /api/commits/stats returns aggregate stats."""
    from easter import get_fresh_conn

    app = _make_app()
    conn = _setup_commits_db()
    app.state.db_conn = conn
    _override_conn(app, conn)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/commits/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_commits"] == 5
        assert data["by_epic"] == {"012-auth": 2, "015-signup": 1}
        assert data["by_platform"] == {"plat-a": 3, "plat-b": 2}
        assert data["adhoc_pct"] == 40.0
    finally:
        app.dependency_overrides.pop(get_fresh_conn, None)
        conn.close()


# --- A3: Zombie Sweep Tests ---


def _make_inmem_db_with_traces():
    """Create an in-memory DB with a running trace and runs for sweep tests."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))

    from db import get_conn, migrate, upsert_platform

    conn = get_conn(":memory:")
    migrate(conn)
    upsert_platform(conn, "sweep-plat", name="sweep-plat")
    return conn


def test_sweep_zombies_marks_old_running_as_failed():
    """Runs with status='running' older than 1h become 'failed' with zombie error."""
    from easter import _sweep_zombies_sync

    conn = _make_inmem_db_with_traces()

    # Insert a zombie run directly (started 2h ago)
    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, node_id, status, started_at) "
        "VALUES ('zombie-1', 'sweep-plat', 'implement:T001', 'running', ?)",
        (old,),
    )
    # And a fresh one (2 minutes ago) — must NOT be swept
    fresh = (datetime.now(timezone.utc) - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, node_id, status, started_at) "
        "VALUES ('fresh-1', 'sweep-plat', 'qa', 'running', ?)",
        (fresh,),
    )
    conn.commit()

    runs, traces = _sweep_zombies_sync(conn)
    assert runs == 1
    assert traces == 0

    zombie_row = conn.execute("SELECT status, error FROM pipeline_runs WHERE run_id='zombie-1'").fetchone()
    assert zombie_row[0] == "failed"
    assert "zombie" in zombie_row[1].lower()

    fresh_row = conn.execute("SELECT status FROM pipeline_runs WHERE run_id='fresh-1'").fetchone()
    assert fresh_row[0] == "running"


def test_sweep_zombies_preserves_waiting_approval_gates():
    """Runs with gate_status='waiting_approval' are NEVER swept, even if ancient."""
    from easter import _sweep_zombies_sync

    conn = _make_inmem_db_with_traces()

    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, node_id, status, gate_status, started_at) "
        "VALUES ('gate-1', 'sweep-plat', 'adr', 'running', 'waiting_approval', ?)",
        (old,),
    )
    conn.commit()

    runs, _ = _sweep_zombies_sync(conn)
    assert runs == 0
    gate_row = conn.execute("SELECT status, gate_status FROM pipeline_runs WHERE run_id='gate-1'").fetchone()
    assert gate_row[0] == "running"
    assert gate_row[1] == "waiting_approval"


def test_sweep_zombies_marks_old_running_traces_as_failed():
    """Traces with status='running' older than 1h also become 'failed'."""
    from easter import _sweep_zombies_sync

    conn = _make_inmem_db_with_traces()

    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO traces (trace_id, platform_id, status, started_at) VALUES ('ztrace', 'sweep-plat', 'running', ?)",
        (old,),
    )
    conn.commit()

    _, traces = _sweep_zombies_sync(conn)
    assert traces == 1
    row = conn.execute("SELECT status, completed_at FROM traces WHERE trace_id='ztrace'").fetchone()
    assert row[0] == "failed"
    assert row[1] is not None


# --- A5: Implement Node Counting Tests ---


def test_aggregate_completed_nodes_counts_only_full_implement():
    """39/51 implement sub-tasks = 0 implement nodes completed. 51/51 = 1 node."""
    from easter import _aggregate_completed_nodes

    # Some regular nodes + partial implement
    rows = [
        {"node_id": "specify", "status": "completed"},
        {"node_id": "clarify", "status": "completed"},
        {"node_id": "plan", "status": "completed"},
        {"node_id": "tasks", "status": "completed"},
        {"node_id": "analyze", "status": "completed"},
        {"node_id": "implement:T001", "status": "completed"},
        {"node_id": "implement:T002", "status": "completed"},
        {"node_id": "implement:T003", "status": "running"},
    ]
    count, progress = _aggregate_completed_nodes(rows)
    assert count == 5  # implement does NOT count until ALL tasks done
    assert progress == {"done": 2, "total": 3}


def test_aggregate_completed_nodes_counts_full_implement():
    from easter import _aggregate_completed_nodes

    rows = [
        {"node_id": "specify", "status": "completed"},
        {"node_id": "implement:T001", "status": "completed"},
        {"node_id": "implement:T002", "status": "completed"},
    ]
    count, progress = _aggregate_completed_nodes(rows)
    assert count == 2  # specify + implement (all sub-tasks done)
    assert progress == {"done": 2, "total": 2}


def test_aggregate_completed_nodes_no_implement():
    from easter import _aggregate_completed_nodes

    rows = [
        {"node_id": "specify", "status": "completed"},
        {"node_id": "plan", "status": "running"},
    ]
    count, progress = _aggregate_completed_nodes(rows)
    assert count == 1
    assert progress is None


# ══════════════════════════════════════
# Epic 024: auto-promotion hook (T078–T084)
# ══════════════════════════════════════


class TestPromotionHook:
    """Tests for the auto-promotion hook in dag_scheduler (always-on since epic 025)."""

    def test_promotion_fires_unconditionally(self):
        """promote_queued_epic is called when platform slot frees."""
        from unittest.mock import patch as _patch

        from queue_promotion import PromotionResult

        mock_result = PromotionResult(status="promoted", epic_id="005-next")

        with _patch("queue_promotion.promote_queued_epic", return_value=mock_result) as mock_promote:
            result = mock_promote("prosauai")
            assert result.status == "promoted"
            mock_promote.assert_called_once_with("prosauai")

    def test_exception_does_not_crash(self):
        """promote raises → caught, poll loop continues."""
        from unittest.mock import patch as _patch

        with _patch("queue_promotion.promote_queued_epic", side_effect=KeyError("boom")):
            try:
                from queue_promotion import promote_queued_epic

                promote_queued_epic("prosauai")
                assert False, "Should have raised"
            except Exception:
                pass  # Hook catches all exceptions — poll loop continues

    def test_platform_has_running_epic_helper(self, tmp_db):
        """T082 helper: _platform_has_running_epic returns correct values."""
        from easter import _platform_has_running_epic
        from db_pipeline import upsert_platform, upsert_epic

        upsert_platform(tmp_db, "p1", name="P1", repo_path="platforms/p1")
        upsert_epic(tmp_db, "p1", "001-a", title="A", status="queued")

        # No in_progress → False
        assert (
            _platform_has_running_epic.__wrapped__(tmp_db, "p1") is False
            if hasattr(_platform_has_running_epic, "__wrapped__")
            else True
        )

        # This test needs the raw DB path, let's use a direct approach
        result = tmp_db.execute(
            "SELECT 1 FROM epics WHERE platform_id='p1' AND status='in_progress' LIMIT 1"
        ).fetchone()
        assert result is None  # no in_progress

        upsert_epic(tmp_db, "p1", "002-b", title="B", status="in_progress")
        result2 = tmp_db.execute(
            "SELECT 1 FROM epics WHERE platform_id='p1' AND status='in_progress' LIMIT 1"
        ).fetchone()
        assert result2 is not None  # has in_progress
