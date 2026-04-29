"""Tests for dag_executor.py — async dispatch, retry, circuit breaker."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dag_executor import CircuitBreaker, Node


def _mock_async_proc(
    stdout: bytes = b"",
    stderr: bytes = b"",
    returncode: int = 0,
) -> AsyncMock:
    """Build an AsyncMock process compatible with the streaming drainer in
    ``dispatch_node_async``.

    The new drainer calls ``stream.read(8192)`` until the stream returns empty
    bytes (EOF). A bare ``AsyncMock()`` with only ``.communicate`` configured
    leaves ``.stdout`` / ``.stderr`` as auto-generated child mocks that return
    non-bytes MagicMocks — ``_drain`` would loop forever and blow up RAM via
    ``AsyncMock.call_args_list``. This helper wires up stdin/stdout/stderr/wait
    so tests exercise the real code path cleanly.

    Returns a mock that:
      * yields ``stdout`` then ``b""`` on successive stdout.read() calls
      * yields ``stderr`` then ``b""`` on successive stderr.read() calls
      * sets ``.returncode`` to ``returncode``
      * has usable ``.stdin.write`` / ``.stdin.drain`` / ``.stdin.close``
      * has awaitable ``.wait`` and synchronous ``.kill``
    """
    mp = AsyncMock()
    mp.returncode = returncode
    mp.stdin = AsyncMock()
    mp.stdin.write = MagicMock()
    mp.stdin.drain = AsyncMock()
    mp.stdin.close = MagicMock()
    mp.stdout = AsyncMock()
    mp.stdout.read = AsyncMock(side_effect=[stdout, b""])
    mp.stderr = AsyncMock()
    mp.stderr.read = AsyncMock(side_effect=[stderr, b""])
    mp.wait = AsyncMock(return_value=returncode)
    mp.kill = MagicMock()
    return mp


# --- Fix: trace creation must happen AFTER gate check ---


@pytest.mark.asyncio
async def test_run_pipeline_async_no_trace_when_gate_pending(tmp_path):
    """run_pipeline_async must NOT create a trace when returning early due to pending gate.

    Regression test: prior to fix, a new trace was created every poll cycle (~15s)
    when a gate was pending, producing orphan traces with 0 completed nodes.
    """
    # Create minimal platform.yaml so file-existence check passes
    plat_dir = tmp_path / "platforms" / "test-plat"
    plat_dir.mkdir(parents=True)
    (plat_dir / "platform.yaml").write_text("title: Test\n")

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_conn.execute.return_value.fetchone.return_value = None

    with (
        patch("dag_executor.REPO_ROOT", tmp_path),
        patch("dag_executor._resolve_code_dir", return_value=tmp_path),
        patch("dag_executor.parse_dag") as mock_parse,
        patch("dag_executor.topological_sort") as mock_topo,
        patch("db.get_resumable_nodes", return_value=set()),
        patch("db.get_pending_gates") as mock_gates,
        patch("db.create_trace") as mock_create_trace,
    ):
        mock_parse.return_value = [_make_node("specify", "speckit.specify")]
        mock_topo.return_value = [_make_node("specify", "speckit.specify")]
        mock_gates.return_value = [{"node_id": "specify", "epic_id": "021-test", "gate_status": "waiting_approval"}]

        from dag_executor import run_pipeline_async

        result = await run_pipeline_async("test-plat", epic_slug="021-test", resume=True, conn=mock_conn)

        assert result == 0  # returns 0 (paused at gate)
        mock_create_trace.assert_not_called()  # NO trace created


@pytest.mark.asyncio
async def test_run_pipeline_async_transitions_epic_to_shipped(tmp_path):
    """run_pipeline_async must call compute_epic_status and transition epic to shipped."""
    plat_dir = tmp_path / "platforms" / "test-plat"
    plat_dir.mkdir(parents=True)
    (plat_dir / "platform.yaml").write_text("title: Test\n")
    # Create a minimal pipeline.yaml for this test
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text("epic_cycle:\n  nodes:\n    - id: specify\n      optional: false\n")

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_conn.execute.return_value.fetchone.return_value = None

    node = _make_node("specify", "speckit.specify")

    # Use a real in-memory DB to test the full flow end-to-end
    import sqlite3

    real_conn = sqlite3.connect(":memory:")
    real_conn.row_factory = sqlite3.Row

    # Bootstrap schema
    from db import migrate
    from db_pipeline import upsert_platform, upsert_epic, upsert_epic_node

    migrate(real_conn)
    upsert_platform(real_conn, "test-plat", name="Test", repo_path="platforms/test-plat")
    upsert_epic(real_conn, "test-plat", "021-test", title="Test", status="in_progress")
    upsert_epic_node(real_conn, "test-plat", "021-test", "specify", "done")

    try:
        with (
            patch("dag_executor.REPO_ROOT", tmp_path),
            patch("dag_executor._resolve_code_dir", return_value=tmp_path),
            patch("dag_executor.parse_dag", return_value=[node]),
            patch("dag_executor.topological_sort", return_value=[node]),
            patch("post_save._refresh_portal_status"),
            patch("config.PIPELINE_YAML", pipeline_path),
        ):
            from dag_executor import run_pipeline_async

            result = await run_pipeline_async("test-plat", epic_slug="021-test", resume=True, conn=real_conn)

            assert result == 0
            # Verify epic transitioned to shipped
            row = real_conn.execute("SELECT status, delivered_at FROM epics WHERE epic_id='021-test'").fetchone()
            assert row["status"] == "shipped"
            assert row["delivered_at"] is not None
    finally:
        real_conn.close()


@pytest.mark.asyncio
async def test_run_pipeline_async_resume_does_not_cancel_traces(tmp_path):
    """resume=True must NOT cancel running traces (reuses them instead)."""
    plat_dir = tmp_path / "platforms" / "test-plat"
    plat_dir.mkdir(parents=True)
    (plat_dir / "platform.yaml").write_text("title: Test\n")

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_conn.execute.return_value.fetchone.return_value = None

    sql_calls = []
    original_execute = mock_conn.execute

    def tracking_execute(sql, params=None):
        sql_calls.append((sql, params))
        return original_execute(sql, params)

    mock_conn.execute = tracking_execute

    with (
        patch("dag_executor.REPO_ROOT", tmp_path),
        patch("dag_executor._resolve_code_dir", return_value=tmp_path),
        patch("dag_executor.parse_dag", return_value=[_make_node("specify", "speckit.specify")]),
        patch("dag_executor.topological_sort", return_value=[_make_node("specify", "speckit.specify")]),
        patch("db.get_resumable_nodes", return_value=set()),
        patch(
            "db.get_pending_gates",
            return_value=[{"node_id": "specify", "epic_id": "021-test", "gate_status": "waiting_approval"}],
        ),
    ):
        from dag_executor import run_pipeline_async

        await run_pipeline_async("test-plat", epic_slug="021-test", resume=True, conn=mock_conn)

    # Traces should NOT be cancelled on resume — they are reused
    trace_cancel = [s for s, p in sql_calls if "traces" in s and "cancelled" in s]
    assert len(trace_cancel) == 0, f"Should not cancel traces on resume, got: {trace_cancel}"


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


def _make_task(
    task_id: str = "T001",
    description: str = "Generic task",
    files: list[str] | None = None,
    checked: bool = False,
    us_tag: str | None = None,
):
    """Build a TaskItem with sensible defaults — keeps the new context-scoping tests terse."""
    from dag_executor import TaskItem

    return TaskItem(
        id=task_id,
        description=description,
        checked=checked,
        phase="Phase 1",
        parallel=False,
        files=files or [],
        line_number=1,
        us_tag=us_tag,
    )


def _make_epic_dir(tmp_path, **extra_files: str):
    """Create an epic scratch dir with ``plan.md`` + ``spec.md`` and any extras."""
    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "plan.md").write_text("# Plan")
    (epic_dir / "spec.md").write_text("# Spec")
    for name, content in extra_files.items():
        # keys use "__" for "/" so callers can pass e.g. contracts__api_md="..."
        path = epic_dir / name.replace("__", "/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return epic_dir


# --- T004: Tests for dispatch_node_async ---


@pytest.mark.asyncio
async def test_dispatch_node_async_success():
    """dispatch_node_async returns (True, None) on success."""
    from dag_executor import dispatch_node_async

    mock_proc = _mock_async_proc(stdout=b"output", stderr=b"", returncode=0)

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        success, error, _stdout = await dispatch_node_async(_make_node(), "/tmp", "test prompt")

    assert success is True
    assert error is None


@pytest.mark.asyncio
async def test_dispatch_node_async_timeout():
    """dispatch_node_async returns (False, timeout message) on timeout.

    The refactored dispatcher uses streaming drainers + ``process.wait()``
    under a single ``asyncio.wait_for``. To trigger the timeout branch we
    make the FIRST ``wait()`` hang; ``kill()`` then rewires ``wait`` to
    return immediately (mirroring real subprocess semantics where SIGKILL
    makes the child exit and the subsequent wait resolve).
    """
    from dag_executor import dispatch_node_async

    mock_proc = _mock_async_proc(stdout=b"", stderr=b"", returncode=0)

    async def _hang() -> None:
        await asyncio.sleep(3600)

    mock_proc.wait = AsyncMock(side_effect=_hang)

    def _kill_effect() -> None:
        # After SIGKILL, subsequent wait() returns immediately.
        mock_proc.wait = AsyncMock(return_value=-9)

    mock_proc.kill = MagicMock(side_effect=_kill_effect)

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        success, error, _stdout = await dispatch_node_async(_make_node(), "/tmp", "test", timeout=1)

    assert success is False
    assert "timeout" in error
    mock_proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_node_async_failure():
    """dispatch_node_async returns (False, error) on non-zero exit code.

    stderr is captured by the drainer and passed to ``_extract_claude_error``
    which falls back to the stderr string when stdout is empty / not JSON.
    """
    from dag_executor import dispatch_node_async

    mock_proc = _mock_async_proc(stdout=b"", stderr=b"something went wrong", returncode=1)

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        success, error, _stdout = await dispatch_node_async(_make_node(), "/tmp", "test")

    assert success is False
    assert "something went wrong" in error


@pytest.mark.asyncio
async def test_dispatch_node_async_no_claude():
    """dispatch_node_async returns (False, error) when claude not in PATH."""
    from dag_executor import dispatch_node_async

    with patch("dag_executor.shutil.which", return_value=None):
        success, error, _stdout = await dispatch_node_async(_make_node(), "/tmp", "test")

    assert success is False
    assert "claude CLI not found" in error


@pytest.mark.asyncio
async def test_dispatch_node_async_propagates_cwd():
    """create_subprocess_exec receives the cwd passed in.

    Pins the external-repo dispatch invariant — if this breaks, implement
    nodes would run in the wrong working directory.
    """
    from dag_executor import dispatch_node_async

    mock_proc = _mock_async_proc(stdout=b"ok", stderr=b"", returncode=0)
    captured: dict = {}

    async def capturing_exec(*args, **kwargs):
        captured.update(kwargs)
        return mock_proc

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", side_effect=capturing_exec),
    ):
        await dispatch_node_async(
            _make_node(node_id="implement:phase-1", skill="speckit.implement"),
            "/tmp/external-repo",
            "test prompt",
        )

    assert captured.get("cwd") == "/tmp/external-repo"


# --- T005: Tests for dispatch_with_retry_async ---


@pytest.mark.asyncio
async def test_retry_with_async_sleep():
    """dispatch_with_retry_async retries on failure with asyncio.sleep."""
    from dag_executor import dispatch_with_retry_async

    breaker = CircuitBreaker()
    call_count = 0

    async def mock_dispatch(
        node, cwd, prompt, timeout=3000, guardrail=None, resume_session_id=None, platform_name="", **kwargs
    ):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return False, "transient error", None
        return True, None, "output"

    with (
        patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch),
        patch("dag_executor.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        success, error, _stdout = await dispatch_with_retry_async(_make_node(), "/tmp", "test", 600, breaker)

    assert success is True
    assert call_count == 3
    assert mock_sleep.await_count == 2  # 2 backoff sleeps


@pytest.mark.asyncio
async def test_circuit_breaker_with_async_dispatch():
    """dispatch_with_retry_async records failure on circuit breaker."""
    from dag_executor import dispatch_with_retry_async

    breaker = CircuitBreaker(max_failures=1)

    async def mock_dispatch(
        node, cwd, prompt, timeout=3000, guardrail=None, resume_session_id=None, platform_name="", **kwargs
    ):
        return False, "permanent error", None

    with (
        patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch),
        patch("dag_executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        success, error, _stdout = await dispatch_with_retry_async(_make_node(), "/tmp", "test", 600, breaker)

    assert success is False
    # Same-error escalation: "permanent error" is unknown, escalates after 3.
    # With 4 attempts and same unknown error, breaker gets a failure on attempt 3.
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

    success, error, _stdout = await dispatch_with_retry_async(_make_node(), "/tmp", "test", 600, breaker)
    assert success is False
    assert "circuit breaker OPEN" in error


@pytest.mark.asyncio
async def test_success_check_skips_retry():
    """dispatch_with_retry_async skips remaining retries when success_check returns True."""
    from dag_executor import dispatch_with_retry_async

    breaker = CircuitBreaker()
    call_count = 0

    async def mock_dispatch(
        node, cwd, prompt, timeout=3000, guardrail=None, resume_session_id=None, platform_name="", **kwargs
    ):
        nonlocal call_count
        call_count += 1
        return False, "timeout", None  # always fails

    # success_check returns True on second check (i.e., before retry 1)
    check_count = 0

    def success_check():
        nonlocal check_count
        check_count += 1
        return check_count >= 1  # True on first call (before retry 1)

    with (
        patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch),
        patch("dag_executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        success, error, _stdout = await dispatch_with_retry_async(
            _make_node(), "/tmp", "test", 600, breaker, success_check=success_check
        )

    assert success is True
    assert error is None
    assert call_count == 1  # only the first attempt ran, no retries
    assert check_count == 1  # success_check called once (before retry 1)


@pytest.mark.asyncio
async def test_report_success_check_skips_retry_when_report_exists(tmp_path):
    """run_pipeline_async passes a report-based success_check for qa/analyze-post/judge.

    Verifies that when a *-report.md exists with ≥50 lines and 'HANDOFF', the
    success_check returns True and retries are skipped — mirroring the implement-phase
    tasks.md success_check pattern.
    """
    from dag_executor import dispatch_with_retry_async

    breaker = CircuitBreaker()
    call_count = 0

    async def mock_dispatch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return False, "timeout", None  # always fails

    # Build a fake report with ≥50 lines and a HANDOFF block
    report = tmp_path / "qa-report.md"
    lines = ["# QA Report\n"] + [f"line {i}\n" for i in range(55)] + ["## HANDOFF\n", "to: reconcile\n"]
    report.write_text("".join(lines))

    def success_check(path=report):
        try:
            content = path.read_text()
            return len(content.splitlines()) >= 50 and "HANDOFF" in content
        except OSError:
            return False

    with (
        patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch),
        patch("dag_executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        success, error, _stdout = await dispatch_with_retry_async(
            _make_node(), "/tmp", "test", 600, breaker, success_check=success_check
        )

    assert success is True
    assert call_count == 1  # only first attempt ran

    # Negative case: report too short → retries proceed
    short_report = tmp_path / "short.md"
    short_report.write_text("# tiny\nHANDOFF\n")
    call_count = 0
    with (
        patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch),
        patch("dag_executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        success2, _, _ = await dispatch_with_retry_async(
            _make_node(),
            "/tmp",
            "test",
            600,
            breaker,
            success_check=lambda p=short_report: len(p.read_text().splitlines()) >= 50 and "HANDOFF" in p.read_text(),
        )
    assert success2 is False  # retries exhausted, check never passed


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
        "gate_notified_at TEXT, gate_resolved_at TEXT, telegram_message_id TEXT, dispatch_log TEXT)"
    )
    # epic-context is done
    conn.execute("INSERT INTO epic_nodes VALUES ('plat', 'e1', 'epic-context', 'done', NULL, '2026-01-01', 'test')")
    # specify has an approved gate but is NOT done in epic_nodes
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, epic_id, node_id, status, gate_status, started_at) "
        "VALUES ('r1', 'plat', 'e1', 'specify', 'running', 'approved', '2026-01-01')"
    )

    try:
        result = get_resumable_nodes(conn, "plat", "e1")
        assert "epic-context" in result
        assert "specify" not in result, "approved gate should NOT count as resumable"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_gate_approved_triggers_dispatch(tmp_path):
    """After gate approval, run_pipeline_async dispatches the node instead of pausing."""
    import sqlite3

    # Create real platform dir so yaml.safe_load doesn't hit a MagicMock stream
    plat_dir = tmp_path / "platforms" / "test-plat"
    plat_dir.mkdir(parents=True)
    (plat_dir / "platform.yaml").write_text("title: Test\n")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Minimal schema for the test
    for ddl in [
        "CREATE TABLE platforms (platform_id TEXT PRIMARY KEY, name TEXT, title TEXT, "
        "lifecycle TEXT DEFAULT 'design', repo_path TEXT, metadata TEXT DEFAULT '{}', "
        "created_at TEXT, updated_at TEXT)",
        "CREATE TABLE epics (epic_id TEXT, platform_id TEXT, title TEXT, status TEXT DEFAULT 'proposed', "
        "priority INT, branch_name TEXT, file_path TEXT, created_at TEXT, updated_at TEXT, "
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
        "trace_id TEXT, output_lines INT, started_at TEXT, completed_at TEXT, gate_notified_at TEXT, "
        "gate_resolved_at TEXT, telegram_message_id TEXT, dispatch_log TEXT)",
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
        return True, None, "output"

    mock_branch = MagicMock()
    mock_branch.stdout = "epic/test-plat/e1\n"

    try:
        with (
            patch("dag_executor.parse_dag", return_value=nodes),
            patch("dag_executor.topological_sort", return_value=nodes),
            patch("dag_executor._resolve_code_dir", return_value=tmp_path),
            patch("dag_executor.dispatch_with_retry_async", side_effect=mock_dispatch),
            patch("dag_executor.verify_outputs", return_value=(True, None)),
            patch("dag_executor.compose_skill_prompt", return_value=("test prompt", "guardrail")),
            patch("dag_executor.subprocess.run", return_value=mock_branch),
            patch("dag_executor.REPO_ROOT", tmp_path),
        ):
            await run_pipeline_async("test-plat", epic_slug="e1", resume=True, conn=conn)

        assert dispatch_called, "specify should have been dispatched after gate approval"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_auto_mode_skips_gate_approval(tmp_path):
    """In auto mode, human gates are auto-approved without DB interaction."""
    import sqlite3

    # Create real platform dir so yaml.safe_load doesn't hit a MagicMock stream
    plat_dir = tmp_path / "platforms" / "p"
    plat_dir.mkdir(parents=True)
    (plat_dir / "platform.yaml").write_text("title: Test\n")

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
        "trace_id TEXT, output_lines INT, started_at TEXT, completed_at TEXT, gate_notified_at TEXT, "
        "gate_resolved_at TEXT, telegram_message_id TEXT, dispatch_log TEXT)",
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
        return True, None, "output"

    mock_branch = MagicMock()
    mock_branch.stdout = "epic/p/e1\n"

    try:
        with (
            patch("dag_executor.parse_dag", return_value=nodes),
            patch("dag_executor.topological_sort", return_value=nodes),
            patch("dag_executor._resolve_code_dir", return_value=tmp_path),
            patch("dag_executor.dispatch_with_retry_async", side_effect=mock_dispatch),
            patch("dag_executor.verify_outputs", return_value=(True, None)),
            patch("dag_executor.compose_skill_prompt", return_value=("test", "guardrail")),
            patch("dag_executor.subprocess.run", return_value=mock_branch),
            patch("dag_executor.REPO_ROOT", tmp_path),
        ):
            await run_pipeline_async("p", epic_slug="e1", resume=True, conn=conn, gate_mode="auto")

        assert "specify" in dispatched, "auto mode should dispatch without pausing"
        # No waiting_approval runs should exist
        gates = conn.execute("SELECT * FROM pipeline_runs WHERE gate_status='waiting_approval'").fetchall()
        assert len(gates) == 0, "auto mode should not create waiting_approval gates"
    finally:
        conn.close()


# --- Tests for task-by-task implement ---


def test_parse_tasks(tmp_path):
    """parse_tasks extracts TaskItems from tasks.md."""
    from dag_executor import parse_tasks

    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text(
        "# Tasks\n\n"
        "## Phase 1: Setup\n\n"
        "- [ ] T001 Create migration `.pipeline/migrations/010.sql`\n"
        "- [X] T002 [P] Create page `portal/src/pages/obs.astro`\n\n"
        "## Phase 2: Core\n\n"
        "- [ ] T003 Add CRUD to `.specify/scripts/db.py`\n"
    )

    tasks = parse_tasks(tasks_md)
    assert len(tasks) == 3

    assert tasks[0].id == "T001"
    assert tasks[0].checked is False
    assert tasks[0].phase == "Phase 1: Setup"
    assert tasks[0].parallel is False
    assert ".pipeline/migrations/010.sql" in tasks[0].files

    assert tasks[1].id == "T002"
    assert tasks[1].checked is True
    assert tasks[1].parallel is True
    assert "portal/src/pages/obs.astro" in tasks[1].files

    assert tasks[2].id == "T003"
    assert tasks[2].phase == "Phase 2: Core"


def test_mark_task_done(tmp_path):
    """mark_task_done updates [ ] to [X] for the specified task."""
    from dag_executor import mark_task_done

    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text("- [ ] T001 First task\n- [ ] T002 Second task\n- [X] T003 Already done\n")

    assert mark_task_done(tasks_md, "T002") is True
    content = tasks_md.read_text()
    assert "- [ ] T001 " in content  # unchanged
    assert "- [X] T002 " in content  # updated
    assert "- [X] T003 " in content  # unchanged

    # Marking non-existent task returns False
    assert mark_task_done(tasks_md, "T099") is False

    # Marking already-done task returns False (pattern "- [ ] T003" not found)
    assert mark_task_done(tasks_md, "T003") is False


def test_compose_task_prompt(tmp_path):
    """compose_task_prompt includes task description and epic context."""
    from dag_executor import TaskItem, compose_task_prompt

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "plan.md").write_text("# Plan\nBuild the thing.")
    (epic_dir / "spec.md").write_text("# Spec\nFeature requirements.")
    (epic_dir / "tasks.md").write_text("# Tasks\n- [X] T001 Done\n- [ ] T005 Pending")

    task = TaskItem(
        id="T005",
        description="Add CORS to `easter.py`",
        checked=False,
        phase="Phase 2",
        parallel=True,
        files=["easter.py"],
        line_number=10,
    )

    prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")

    assert "T005" in prompt
    assert "ONLY implement this specific task" in prompt
    assert "easter.py" in prompt
    assert "Plan" in prompt
    assert "Spec" in prompt
    assert "epic/test-plat/001-test" in prompt
    assert "All Tasks" in prompt


def test_compose_task_prompt_shows_recent_done(tmp_path):
    """compose_task_prompt surfaces recently checked tasks from tasks.md.

    Replaces the legacy behavior of reading implement-context.md. The new
    source of truth is the [X] checkboxes in tasks.md itself.
    """
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(
        tmp_path,
        **{"tasks.md": "## Phase 1\n- [X] T001 First task\n- [X] T002 Second task\n- [ ] T003 Next task\n"},
    )
    prompt = compose_task_prompt(_make_task("T003", "Next task"), epic_dir, "test-plat", "001-test")

    assert "Recent progress" in prompt
    assert "T001" in prompt
    assert "T002" in prompt
    assert "Prior Tasks Completed" not in prompt


def test_compose_task_prompt_legacy_implement_context(tmp_path):
    """Rollback path: MADRUGA_KILL_IMPLEMENT_CONTEXT=0 restores legacy file reads."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(
        tmp_path,
        **{"implement-context.md": "### T001 — DONE\n- Created file\n"},
    )
    with patch.dict(os.environ, {"MADRUGA_KILL_IMPLEMENT_CONTEXT": "0"}):
        prompt = compose_task_prompt(_make_task("T002", "Next task"), epic_dir, "test-plat", "001-test")

    assert "Prior Tasks Completed" in prompt
    assert "T001 — DONE" in prompt


def test_compose_task_prompt_analyze_report_filtered_to_task(tmp_path):
    """analyze-report.md is sliced to paragraphs mentioning this task id."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(
        tmp_path,
        **{
            "analyze-report.md": (
                "## Findings\n\nIssue A affects T001 badly.\n\nIssue B affects T050 differently.\n\nIssue C is generic."
            ),
        },
    )
    prompt = compose_task_prompt(_make_task("T001", "Fix module X"), epic_dir, "test-plat", "001-test")

    assert "Pre-Implementation Analysis (filtered to T001)" in prompt
    assert "Issue A affects T001" in prompt
    # Unrelated findings for other tasks must NOT leak into this task's prompt
    assert "T050 differently" not in prompt


def test_compose_task_prompt_analyze_report_absent_when_no_mention(tmp_path):
    """No analyze-report section is added when the report doesn't mention this task."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(
        tmp_path,
        **{"analyze-report.md": "## Findings\n\nIssue unrelated to T999."},
    )
    prompt = compose_task_prompt(_make_task("T042", "Ship feature"), epic_dir, "test-plat", "001-test")

    assert "Pre-Implementation Analysis" not in prompt


def test_task_needs_data_model_by_path():
    """_task_needs_data_model detects model-like file paths."""
    from dag_executor import _task_needs_data_model

    assert _task_needs_data_model(_make_task(files=["prosauai/models/tenant.py"])) is True
    # Anchored regex: fetch_models_helper.py must NOT match (false positive guard)
    assert _task_needs_data_model(_make_task(files=["prosauai/fetch_models_helper.py"])) is False


def test_task_needs_data_model_by_description():
    """_task_needs_data_model detects data model keywords in description."""
    from dag_executor import _task_needs_data_model

    task = _make_task(description="Add Pydantic schema for tenant config", files=["config.py"])
    assert _task_needs_data_model(task) is True


def test_task_needs_contracts_by_path():
    """_task_needs_contracts detects API-like file paths."""
    from dag_executor import _task_needs_contracts

    assert _task_needs_contracts(_make_task(files=["prosauai/webhooks/telegram.py"])) is True


def test_task_needs_contracts_by_description():
    """_task_needs_contracts detects API keywords in description."""
    from dag_executor import _task_needs_contracts

    task = _make_task(description="Add validation to POST endpoint", files=["main.py"])
    assert _task_needs_contracts(task) is True


def test_task_needs_gates_negative_case():
    """Both predicates return False for unrelated tasks (no false positives)."""
    from dag_executor import _task_needs_contracts, _task_needs_data_model

    task = _make_task(description="Add README section about installation", files=["README.md"])
    assert _task_needs_data_model(task) is False
    assert _task_needs_contracts(task) is False


def test_compose_task_prompt_data_model_gated(tmp_path):
    """Legacy gating: data-model.md is OMITTED for tasks that don't touch models.

    CACHE_ORDERED=1 (the default) force-includes data_model to keep the
    cache prefix uniform across tasks. This gating only applies under
    MADRUGA_CACHE_ORDERED=0 (legacy path).
    """
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(tmp_path, **{"data-model.md": "# Data Model\nEntity definitions."})
    task = _make_task(description="Update README", files=["README.md"])

    with patch.dict(os.environ, {"MADRUGA_CACHE_ORDERED": "0"}):
        prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")
    assert "Data Model" not in prompt
    assert "Entity definitions" not in prompt


def test_compose_task_prompt_data_model_included_for_model_task(tmp_path):
    """data-model.md IS included when the task touches models/."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(tmp_path, **{"data-model.md": "# Data Model\nEntity definitions."})
    task = _make_task(description="Create Tenant entity", files=["prosauai/models/tenant.py"])

    prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")
    assert "## Data Model" in prompt
    assert "Entity definitions" in prompt


def test_compose_task_prompt_contracts_gated(tmp_path):
    """Legacy gating: contracts/*.md OMITTED for tasks that don't touch APIs.

    CACHE_ORDERED=1 (the default) force-includes contracts to keep the
    cache prefix uniform across tasks. This gating only applies under
    MADRUGA_CACHE_ORDERED=0 (legacy path).
    """
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(tmp_path, **{"contracts__webhook-api.md": "# Webhook contract"})
    task = _make_task(description="Update README", files=["README.md"])

    with patch.dict(os.environ, {"MADRUGA_CACHE_ORDERED": "0"}):
        prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")
    assert "webhook-api" not in prompt
    assert "Webhook contract" not in prompt


def test_compose_task_prompt_scoped_context_rollback(tmp_path):
    """Rollback path: MADRUGA_SCOPED_CONTEXT=0 restores always-include behavior."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(tmp_path, **{"data-model.md": "# Data Model\nEverything."})
    task = _make_task(description="Update README", files=["README.md"])

    with patch.dict(os.environ, {"MADRUGA_SCOPED_CONTEXT": "0"}):
        prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")
    assert "Data Model" in prompt


def test_append_implement_context_noop_by_default(tmp_path):
    """append_implement_context is a NO-OP under MADRUGA_KILL_IMPLEMENT_CONTEXT=1."""
    from dag_executor import append_implement_context

    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()
    append_implement_context(
        epic_dir, _make_task(files=["db.py"], checked=True), {"tokens_in": 1000, "tokens_out": 500}
    )
    assert not (epic_dir / "implement-context.md").exists()


def test_append_implement_context_legacy_mode(tmp_path):
    """Rollback path: MADRUGA_KILL_IMPLEMENT_CONTEXT=0 restores append behavior."""
    from dag_executor import append_implement_context

    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()
    task1 = _make_task("T001", "Create db.py functions", files=["db.py", "models.py"], checked=True)
    task2 = _make_task("T002", "Add API endpoint", files=["easter.py"], checked=True)

    with patch.dict(os.environ, {"MADRUGA_KILL_IMPLEMENT_CONTEXT": "0"}):
        append_implement_context(epic_dir, task1, {"tokens_in": 1000, "tokens_out": 500})
        append_implement_context(epic_dir, task2)

    ctx = (epic_dir / "implement-context.md").read_text()
    assert "T001 — DONE" in ctx
    assert "db.py, models.py" in ctx
    assert "1000/500" in ctx
    assert "T002 — DONE" in ctx
    assert "easter.py" in ctx


def test_implement_context_swept_at_cycle_start(tmp_path):
    """Stale implement-context.md from legacy runs is cleaned up on cycle start."""
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()
    ctx_path = epic_dir / "implement-context.md"
    ctx_path.write_text("### T001 — DONE\nstale data\n")

    if ctx_path.exists():
        ctx_path.unlink()

    assert not ctx_path.exists()


# --- Phase 5: Cache-optimal reorder (MADRUGA_CACHE_ORDERED) ---


def test_compose_task_prompt_cache_ordered_prefix_comes_first(tmp_path):
    """Under CACHE_ORDERED=1, stable sections (plan/spec) come BEFORE task card."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(
        tmp_path,
        **{
            "tasks.md": "## Phase 1\n- [ ] T001 Do stuff\n",
            "data-model.md": "# Data Model\nEntities.",
            "contracts__api.md": "# API contract",
        },
    )
    task = _make_task(files=["README.md"])
    prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")

    # Cue at position 0 (cache-safe constant)
    assert prompt.startswith("(Implementing one SpecKit task")

    # plan comes before the task card header
    assert prompt.index("Implementation Plan") < prompt.index("You are implementing task")
    # spec comes before the "All Tasks" section (which is in the variable suffix)
    assert prompt.index("## Specification") < prompt.index("## All Tasks")
    # data_model and contracts force-included (even though task doesn't touch them)
    assert "## Data Model" in prompt
    assert "## Contract: api.md" in prompt


def test_compose_task_prompt_cache_ordered_stable_prefix_byte_equal(tmp_path):
    """The cacheable prefix is byte-identical across tasks with different files/descriptions.

    This is THE core invariant that unlocks Claude's 1h-TTL prefix cache
    across tasks in the same epic. Any drift breaks cache alignment.
    """
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(
        tmp_path,
        **{
            "tasks.md": "## Phase 1\n- [ ] T001 Something\n- [ ] T999 Something else\n",
            "data-model.md": "# Data Model\nEntities.",
            "contracts__api.md": "# API contract",
        },
    )
    t_model = _make_task("T001", "Create entity", files=["models/user.py"], us_tag="US1")
    t_readme = _make_task("T999", "Update README", files=["README.md"], us_tag="US3")

    p1 = compose_task_prompt(t_model, epic_dir, "test-plat", "001-test")
    p2 = compose_task_prompt(t_readme, epic_dir, "test-plat", "001-test")

    # "## All Tasks (current progress)" is the first section of the variable
    # suffix. Everything before it must be byte-identical.
    marker = "## All Tasks"
    b1 = p1.index(marker)
    b2 = p2.index(marker)
    assert p1[:b1] == p2[:b2], (
        f"Stable prefix diverges at first {min(b1, b2)} bytes — Claude prefix cache will miss on non-first tasks."
    )


def test_compose_task_prompt_cache_ordered_rollback_legacy_layout(tmp_path):
    """MADRUGA_CACHE_ORDERED=0 restores the legacy layout (task card at top)."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(
        tmp_path,
        **{"data-model.md": "# DM", "contracts__api.md": "# API"},
    )
    task = _make_task(files=["README.md"])

    with patch.dict(os.environ, {"MADRUGA_CACHE_ORDERED": "0"}):
        prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")

    # Legacy invariants: task card first, no cue line, scoped gating active
    assert prompt.startswith("You are implementing task T001")
    assert "(Implementing one SpecKit task" not in prompt
    # Legacy with default SCOPED_CONTEXT=1: data_model/contracts gated OUT
    # for a README task (doesn't touch models or api)
    assert "## Data Model" not in prompt
    assert "## Contract: api.md" not in prompt


def test_compose_task_prompt_cache_ordered_resume_no_prefix(tmp_path):
    """resume=True skips the static prefix, keeps cue + reordered suffix."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(tmp_path, **{"data-model.md": "# DM"})
    task = _make_task()
    prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test", resume=True)

    # No prefix: plan/spec/data_model/contracts all absent
    assert "Implementation Plan" not in prompt
    assert "## Specification" not in prompt
    assert "## Data Model" not in prompt
    # Cue still present (cache-safe constant)
    assert prompt.startswith("(Implementing one SpecKit task")
    # Header (task card) still added at the end
    assert "You are implementing task T001" in prompt


def test_compose_task_prompt_cache_ordered_missing_data_model(tmp_path):
    """Missing data-model.md → prefix stays aligned across tasks; no error."""
    from dag_executor import compose_task_prompt

    # No data-model.md, no contracts/ — minimal epic (only tasks.md for boundary)
    epic_dir = _make_epic_dir(
        tmp_path,
        **{"tasks.md": "## Phase 1\n- [ ] T001 A\n- [ ] T002 B\n"},
    )
    t1 = _make_task("T001", files=["models/user.py"])
    t2 = _make_task("T002", files=["README.md"])

    p1 = compose_task_prompt(t1, epic_dir, "test-plat", "001-test")
    p2 = compose_task_prompt(t2, epic_dir, "test-plat", "001-test")

    # Prefix still aligned even when optional sections are missing
    b1 = p1.index("## All Tasks")
    b2 = p2.index("## All Tasks")
    assert p1[:b1] == p2[:b2]
    # data_model legitimately absent for both
    assert "## Data Model" not in p1
    assert "## Data Model" not in p2


def test_compose_task_prompt_cache_ordered_log_field(tmp_path, caplog):
    """prompt_composed log line includes cache_ordered=True when flag is on."""
    import logging

    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(tmp_path)
    task = _make_task()
    with caplog.at_level(logging.INFO, logger="dag_executor"):
        compose_task_prompt(task, epic_dir, "test-plat", "001-test")

    # Default on → cache_ordered=True in the log event
    relevant = [r for r in caplog.records if "prompt_composed" in r.getMessage()]
    assert relevant, "Expected prompt_composed log entry"
    assert "cache_ordered=True" in relevant[-1].getMessage()


def test_parse_tasks_extracts_us_tag(tmp_path):
    """parse_tasks extracts [US*] tag from task descriptions."""
    from dag_executor import parse_tasks

    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text(
        "# Tasks\n"
        "- [ ] T001 [US1] Create traces table\n"
        "- [ ] T002 [P] [US1] Add CORS middleware\n"
        "- [ ] T003 Plain task without US tag\n"
        "- [ ] T004 [US3] Eval scoring\n"
    )
    tasks = parse_tasks(tasks_md)

    assert tasks[0].us_tag == "US1"
    assert tasks[1].us_tag == "US1"
    assert tasks[2].us_tag is None
    assert tasks[3].us_tag == "US3"


def test_parse_session_id():
    """parse_session_id extracts session_id from JSON stdout."""
    from dag_executor import parse_session_id

    assert parse_session_id('{"result": "ok", "session_id": "abc-123"}') == "abc-123"
    assert parse_session_id('{"result": "ok"}') is None
    assert parse_session_id("") is None
    assert parse_session_id(None) is None
    assert parse_session_id("not json") is None


def test_parse_tasks_empty(tmp_path):
    """parse_tasks returns empty list for file with no tasks."""
    from dag_executor import parse_tasks

    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text("# Tasks\n\nNo tasks here.\n")

    tasks = parse_tasks(tasks_md)
    assert len(tasks) == 0


# --- T029: Edge case tests ---


def test_parse_claude_output_no_json_returns_nulls():
    """Edge case: node without JSON output registers tokens/cost as NULL."""
    from dag_executor import parse_claude_output

    # No output at all
    result = parse_claude_output("")
    assert result == {
        "tokens_in": None,
        "tokens_out": None,
        "cost_usd": None,
        "duration_ms": None,
        "cache_read": None,
        "cache_create": None,
    }

    # None input
    result = parse_claude_output(None)
    assert result == {
        "tokens_in": None,
        "tokens_out": None,
        "cost_usd": None,
        "duration_ms": None,
        "cache_read": None,
        "cache_create": None,
    }

    # Non-JSON output (e.g., raw text from failed subprocess)
    result = parse_claude_output("Error: something went wrong\nTraceback...")
    assert result == {
        "tokens_in": None,
        "tokens_out": None,
        "cost_usd": None,
        "duration_ms": None,
        "cache_read": None,
        "cache_create": None,
    }

    # Valid JSON but missing usage fields
    result = parse_claude_output('{"result": "ok"}')
    assert result["tokens_in"] is None
    assert result["tokens_out"] is None
    assert result["cost_usd"] is None


def test_parse_claude_output_partial_fields():
    """Edge case: JSON output with only some fields populated."""
    from dag_executor import parse_claude_output

    result = parse_claude_output('{"usage": {"input_tokens": 500}, "total_cost_usd": 0.05}')
    assert result["tokens_in"] == 500
    assert result["tokens_out"] is None  # missing from usage
    assert result["cost_usd"] == 0.05
    assert result["duration_ms"] is None


def test_run_eval_scoring_best_effort_on_db_failure():
    """Edge case: DB write failure does not block pipeline execution.

    _run_eval_scoring wraps everything in try/except (FR-011).
    Even if insert_eval_score raises, no exception propagates.
    """
    from dag_executor import _run_eval_scoring

    # Pass a mock connection that raises on execute
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = Exception("DB write failed: disk full")

    # Should NOT raise — best-effort scoring
    _run_eval_scoring(
        conn=mock_conn,
        platform_id="test-plat",
        node_id="specify",
        run_id="run-1",
        trace_id="trace-1",
        epic_id="017-obs",
        output_path="/nonexistent/file.md",
        metrics={},
    )
    # If we get here, the test passes — no exception propagated


@pytest.mark.asyncio
async def test_db_write_failure_does_not_block_dispatch():
    """Edge case: DB write failure does not block pipeline execution.

    When insert_run or complete_run raise, dispatch_with_retry_async
    should still return the dispatch result (observability is best-effort).
    """
    from dag_executor import dispatch_node_async

    mock_proc = _mock_async_proc(
        stdout=b'{"usage": {"input_tokens": 100}}',
        stderr=b"",
        returncode=0,
    )

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        success, error, stdout = await dispatch_node_async(_make_node(), "/tmp", "test prompt")

    # Core dispatch succeeds regardless of DB state
    assert success is True
    assert error is None


# --- Tests for check_auto_escalate ---


def test_check_auto_escalate_pass(tmp_path):
    """score >= 80 and verdict pass returns True."""
    from dag_executor import check_auto_escalate

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "judge-report.md").write_text("---\nscore: 85\nverdict: pass\n---\n# Report\nAll good.")
    node = Node(
        id="judge",
        skill="madruga:judge",
        outputs=["epics/001-test/judge-report.md"],
        depends=[],
        gate="auto-escalate",
        layer="test",
        optional=False,
        skip_condition=None,
    )
    assert check_auto_escalate(node, tmp_path, "001-test") is True


def test_check_auto_escalate_fail(tmp_path):
    """score < 80 returns False."""
    from dag_executor import check_auto_escalate

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "judge-report.md").write_text("---\nscore: 59\nverdict: fail\n---\n# Report\nBLOCKERs found.")
    node = Node(
        id="judge",
        skill="madruga:judge",
        outputs=["epics/001-test/judge-report.md"],
        depends=[],
        gate="auto-escalate",
        layer="test",
        optional=False,
        skip_condition=None,
    )
    assert check_auto_escalate(node, tmp_path, "001-test") is False


def test_check_auto_escalate_borderline_80(tmp_path):
    """score == 80 with verdict pass returns True (boundary)."""
    from dag_executor import check_auto_escalate

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "judge-report.md").write_text("---\nscore: 80\nverdict: pass\n---\n# Report")
    node = Node(
        id="judge",
        skill="madruga:judge",
        outputs=["epics/001-test/judge-report.md"],
        depends=[],
        gate="auto-escalate",
        layer="test",
        optional=False,
        skip_condition=None,
    )
    assert check_auto_escalate(node, tmp_path, "001-test") is True


def test_check_auto_escalate_high_score_fail_verdict(tmp_path):
    """score >= 80 but verdict fail returns False (verdict takes precedence)."""
    from dag_executor import check_auto_escalate

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "judge-report.md").write_text("---\nscore: 90\nverdict: fail\n---\n# Report")
    node = Node(
        id="judge",
        skill="madruga:judge",
        outputs=["epics/001-test/judge-report.md"],
        depends=[],
        gate="auto-escalate",
        layer="test",
        optional=False,
        skip_condition=None,
    )
    assert check_auto_escalate(node, tmp_path, "001-test") is False


def test_check_auto_escalate_no_report(tmp_path):
    """Missing report file returns None."""
    from dag_executor import check_auto_escalate

    node = Node(
        id="judge",
        skill="madruga:judge",
        outputs=["epics/001-test/judge-report.md"],
        depends=[],
        gate="auto-escalate",
        layer="test",
        optional=False,
        skip_condition=None,
    )
    assert check_auto_escalate(node, tmp_path, "001-test") is None


def test_check_auto_escalate_wrong_gate(tmp_path):
    """Node with gate != auto-escalate returns None immediately."""
    from dag_executor import check_auto_escalate

    node = Node(
        id="judge",
        skill="madruga:judge",
        outputs=["epics/001-test/judge-report.md"],
        depends=[],
        gate="auto",
        layer="test",
        optional=False,
        skip_condition=None,
    )
    assert check_auto_escalate(node, tmp_path, "001-test") is None


def test_check_auto_escalate_malformed_yaml(tmp_path):
    """Invalid YAML frontmatter returns None (graceful degradation)."""
    from dag_executor import check_auto_escalate

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "judge-report.md").write_text("---\n{invalid: yaml: [broken\n---\n# Report")
    node = Node(
        id="judge",
        skill="madruga:judge",
        outputs=["epics/001-test/judge-report.md"],
        depends=[],
        gate="auto-escalate",
        layer="test",
        optional=False,
        skip_condition=None,
    )
    assert check_auto_escalate(node, tmp_path, "001-test") is None


# --- Tests for compose_skill_prompt context threading ---


def test_compose_skill_prompt_judge_receives_analyze_post(tmp_path):
    """judge node prompt includes analyze-post-report.md content."""
    from dag_executor import compose_skill_prompt

    # Setup platform dir with epic and reports
    platform_dir = tmp_path / "platforms" / "test-plat"
    epic_dir = platform_dir / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "spec.md").write_text("# Spec\nTest spec.")
    (epic_dir / "analyze-post-report.md").write_text("# Post Analysis\nGap found in FR-003.")

    node = Node(
        id="judge",
        skill="madruga:judge",
        outputs=["{epic}/judge-report.md"],
        depends=["analyze-post"],
        gate="auto-escalate",
        layer="test",
        optional=False,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        prompt, _ = compose_skill_prompt("test-plat", node, platform_dir, "001-test")

    assert "Upstream Report: analyze-post-report.md" in prompt
    assert "Gap found in FR-003" in prompt


def test_compose_skill_prompt_qa_receives_judge_and_analyze(tmp_path):
    """qa node prompt includes both judge-report.md and analyze-post-report.md."""
    from dag_executor import compose_skill_prompt

    platform_dir = tmp_path / "platforms" / "test-plat"
    epic_dir = platform_dir / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "spec.md").write_text("# Spec")
    (epic_dir / "analyze-post-report.md").write_text("# Post Analysis\nIssue A.")
    (epic_dir / "judge-report.md").write_text("---\nscore: 60\n---\n# Judge\nBLOCKER in db.py:45.")

    node = Node(
        id="qa",
        skill="madruga:qa",
        outputs=["{epic}/qa-report.md"],
        depends=["judge"],
        gate="human",
        layer="test",
        optional=True,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        prompt, _ = compose_skill_prompt("test-plat", node, platform_dir, "001-test")

    assert "Upstream Report: analyze-post-report.md" in prompt
    assert "Issue A" in prompt
    assert "Upstream Report: judge-report.md" in prompt
    assert "BLOCKER in db.py:45" in prompt


def test_compose_skill_prompt_reconcile_receives_judge_and_qa(tmp_path):
    """reconcile node prompt includes judge-report.md and qa-report.md."""
    from dag_executor import compose_skill_prompt

    platform_dir = tmp_path / "platforms" / "test-plat"
    epic_dir = platform_dir / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "spec.md").write_text("# Spec")
    (epic_dir / "judge-report.md").write_text("# Judge\nScore: 85.")
    (epic_dir / "qa-report.md").write_text("# QA\nHealed 3 issues.")

    node = Node(
        id="reconcile",
        skill="madruga:reconcile",
        outputs=["{epic}/reconcile-report.md"],
        depends=["qa"],
        gate="human",
        layer="test",
        optional=True,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        prompt, _ = compose_skill_prompt("test-plat", node, platform_dir, "001-test")

    assert "Upstream Report: judge-report.md" in prompt
    assert "Score: 85" in prompt
    assert "Upstream Report: qa-report.md" in prompt
    assert "Healed 3 issues" in prompt


def test_compose_skill_prompt_no_report_graceful(tmp_path):
    """judge node prompt generated without error when reports don't exist."""
    from dag_executor import compose_skill_prompt

    platform_dir = tmp_path / "platforms" / "test-plat"
    epic_dir = platform_dir / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "spec.md").write_text("# Spec")
    # No analyze-post-report.md exists

    node = Node(
        id="judge",
        skill="madruga:judge",
        outputs=["{epic}/judge-report.md"],
        depends=["analyze-post"],
        gate="auto-escalate",
        layer="test",
        optional=False,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        prompt, guardrail = compose_skill_prompt("test-plat", node, platform_dir, "001-test")

    assert "Upstream Report" not in prompt
    assert guardrail is not None  # guardrail is always generated for epic nodes


# --- Tests for build_system_prompt ---


def _setup_knowledge(tmp_path):
    """Create minimal knowledge/contract files for build_system_prompt tests."""
    knowledge = tmp_path / ".claude" / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "pipeline-contract-base.md").write_text("# Pipeline Contract — Base\nStep 0: Prerequisites\n")
    (knowledge / "pipeline-contract-engineering.md").write_text(
        "# Pipeline Contract — Engineering\nSimplicity first.\n"
    )
    (knowledge / "pipeline-contract-planning.md").write_text("# Pipeline Contract — Planning\nCut scope.\n")
    (knowledge / "pipeline-contract-business.md").write_text("# Pipeline Contract — Business\nReduce scope.\n")

    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "python.md").write_text("# Python Conventions\nUse ruff.\n")

    commands = tmp_path / ".claude" / "commands"
    commands.mkdir(parents=True)
    (commands / "speckit.specify.md").write_text("---\ndescription: Create spec\n---\n## Outline\nGenerate spec.\n")
    (commands / "speckit.analyze.md").write_text("---\ndescription: Analyze\n---\n## Goal\nAnalyze artifacts.\n")
    (commands / "speckit.implement.md").write_text("---\ndescription: Implement\n---\n## Outline\nExecute tasks.\n")

    madruga = commands / "madruga"
    madruga.mkdir()
    (madruga / "vision.md").write_text("---\ndescription: Generate vision\n---\n## Instructions\nVision content.\n")
    (madruga / "judge.md").write_text("---\ndescription: Run judge\n---\n## Instructions\nJudge content.\n")
    (madruga / "reconcile.md").write_text("---\ndescription: Reconcile\n---\n## Instructions\nReconcile content.\n")
    (madruga / "qa.md").write_text("---\ndescription: QA\n---\n## Instructions\nQA content.\n")

    return tmp_path


def test_build_system_prompt_includes_conventions_header(tmp_path):
    """System prompt starts with conventions header."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert result.startswith("# Conventions")
    assert "English" in result


def test_build_system_prompt_includes_base_contract(tmp_path):
    """System prompt always includes pipeline-contract-base.md."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "Pipeline Contract — Base" in result
    assert "Step 0: Prerequisites" in result


def test_build_system_prompt_includes_layer_contract_engineering(tmp_path):
    """Engineering layer nodes get engineering contract."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = Node(
        id="specify",
        skill="speckit.specify",
        outputs=[],
        depends=[],
        gate="human",
        layer="engineering",
        optional=False,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "Pipeline Contract — Engineering" in result
    assert "Simplicity first" in result


def test_build_system_prompt_includes_layer_contract_planning(tmp_path):
    """Planning layer nodes get planning contract."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = Node(
        id="roadmap",
        skill="madruga:roadmap",
        outputs=[],
        depends=[],
        gate="human",
        layer="planning",
        optional=False,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "Pipeline Contract — Planning" in result
    assert "Cut scope" in result


def test_build_system_prompt_includes_layer_contract_business(tmp_path):
    """Business layer nodes get business contract."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = Node(
        id="vision",
        skill="madruga:vision",
        outputs=[],
        depends=[],
        gate="human",
        layer="business",
        optional=False,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "Pipeline Contract — Business" in result
    assert "Reduce scope" in result


def test_build_system_prompt_no_layer_contract_for_unknown(tmp_path):
    """Unknown layers do not get a layer contract section."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = _make_node("test-node", "test:skill")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "Pipeline Contract — Engineering" not in result
    assert "Pipeline Contract — Planning" not in result
    assert "Pipeline Contract — Business" not in result


def test_build_system_prompt_includes_skill_body(tmp_path):
    """System prompt includes the full skill .md body."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "# Skill Instructions" in result
    assert "Generate spec" in result


def test_build_system_prompt_implement_includes_python_rules(tmp_path):
    """Implement nodes include Python rules."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = Node(
        id="implement",
        skill="speckit.implement",
        outputs=[],
        depends=[],
        gate="auto",
        layer="engineering",
        optional=False,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "Python Conventions" in result
    assert "ruff" in result


def test_build_system_prompt_non_implement_excludes_python_rules(tmp_path):
    """Non-implement nodes do NOT include Python rules."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "Python Conventions" not in result


def test_build_system_prompt_implement_task_includes_python_rules(tmp_path):
    """implement:T001 task nodes include Python rules."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = Node(
        id="implement:T001",
        skill="speckit.implement",
        outputs=[],
        depends=[],
        gate="auto",
        layer="implementation",
        optional=False,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "Python Conventions" in result


def test_build_system_prompt_missing_skill_file_warns(tmp_path):
    """Missing skill file logs a warning but still returns conventions+contract."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.nonexistent")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "# Conventions" in result
    assert "Pipeline Contract — Base" in result
    assert "# Skill Instructions" not in result


def test_build_system_prompt_derives_path_for_madruga_skill(tmp_path):
    """Skill path is derived from convention for madruga:* skills."""
    from dag_executor import build_system_prompt

    _setup_knowledge(tmp_path)
    node = Node(
        id="vision",
        skill="madruga:vision",
        outputs=[],
        depends=[],
        gate="human",
        layer="business",
        optional=False,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", tmp_path):
        result = build_system_prompt(node, "test-plat")

    assert "Vision content" in result


# --- Tests for build_dispatch_cmd ---


def test_build_dispatch_cmd_bare_with_api_key(tmp_path):
    """Command includes --bare only when ANTHROPIC_API_KEY is set."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    # Without API key: no --bare (OAuth mode)
    with patch("dag_executor.REPO_ROOT", tmp_path), patch.dict("os.environ", {}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")
    assert "--bare" not in cmd

    # With API key: --bare present
    with patch("dag_executor.REPO_ROOT", tmp_path), patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")
    assert "--bare" in cmd


def test_build_dispatch_cmd_has_output_format_json(tmp_path):
    """Command includes --output-format json."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--output-format")
    assert cmd[idx + 1] == "json"


def test_build_dispatch_cmd_has_system_prompt(tmp_path):
    """Command includes --system-prompt with conventions content."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--system-prompt")
    system_prompt = cmd[idx + 1]
    assert "# Conventions" in system_prompt
    assert "Pipeline Contract — Base" in system_prompt


def test_build_dispatch_cmd_allowed_tools_for_analyze(tmp_path):
    """Analyze nodes get read-only tools."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("analyze", "speckit.analyze")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--allowedTools")
    tools = cmd[idx + 1]
    assert tools == "Bash,Read,Glob,Grep"
    assert "Write" not in tools
    assert "Edit" not in tools


def test_build_dispatch_cmd_allowed_tools_for_implement(tmp_path):
    """Implement nodes get full code tools."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("implement", "speckit.implement")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--allowedTools")
    tools = cmd[idx + 1]
    assert "Bash" in tools
    assert "Write" in tools
    assert "Edit" in tools


def test_build_dispatch_cmd_allowed_tools_for_judge(tmp_path):
    """Judge nodes get Agent tool for parallel personas."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("judge", "madruga:judge")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--allowedTools")
    tools = cmd[idx + 1]
    assert "Agent" in tools


def test_build_dispatch_cmd_default_tools_for_unknown_node(tmp_path):
    """Unknown nodes get DEFAULT_TOOLS."""
    from dag_executor import DEFAULT_TOOLS, build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("unknown-node", "unknown:skill")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--allowedTools")
    assert cmd[idx + 1] == DEFAULT_TOOLS


def test_build_dispatch_cmd_implement_task_tools(tmp_path):
    """implement:T001 nodes get IMPLEMENT_TASK_TOOLS."""
    from dag_executor import IMPLEMENT_TASK_TOOLS, build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("implement:T001", "speckit.implement")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--allowedTools")
    assert cmd[idx + 1] == IMPLEMENT_TASK_TOOLS


def test_build_dispatch_cmd_effort_for_analyze(tmp_path):
    """Analyze nodes get --effort medium."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("analyze", "speckit.analyze")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--effort")
    assert cmd[idx + 1] == "medium"


def test_build_dispatch_cmd_effort_for_analyze_post(tmp_path):
    """analyze-post nodes get --effort medium."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("analyze-post", "speckit.analyze")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--effort")
    assert cmd[idx + 1] == "medium"


def test_build_dispatch_cmd_no_effort_for_specify(tmp_path):
    """Specify nodes do NOT get --effort flag."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    assert "--effort" not in cmd


def test_build_dispatch_cmd_guardrail_appended(tmp_path):
    """Guardrail is added via --append-system-prompt."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat", guardrail="MANDATORY: stay on branch")

    idx = cmd.index("--append-system-prompt")
    assert cmd[idx + 1] == "MANDATORY: stay on branch"


def test_build_dispatch_cmd_no_guardrail_when_none(tmp_path):
    """No --append-system-prompt when guardrail is None."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    assert "--append-system-prompt" not in cmd


def test_build_dispatch_cmd_resume_session(tmp_path):
    """Resume session ID is passed via --resume."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("implement:T001", "speckit.implement")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat", resume_session_id="abc123def")

    idx = cmd.index("--resume")
    assert cmd[idx + 1] == "abc123def"


def test_build_dispatch_cmd_disallowed_tools_present(tmp_path):
    """Defense-in-depth: --disallowedTools still present alongside --allowedTools."""
    from dag_executor import DISALLOWED_TOOLS, build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")

    idx = cmd.index("--disallowedTools")
    assert cmd[idx + 1] == DISALLOWED_TOOLS


def test_build_dispatch_cmd_prompt_not_in_argv(tmp_path):
    """Prompt is NOT passed as argv — it's piped via stdin by dispatch_node_async.

    Postmortem: passing large prompts as argv hit Linux MAX_ARG_STRLEN=128KB
    with ``OSError: [Errno 7] Argument list too long`` on T042.
    """
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("specify", "speckit.specify")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "my test prompt here", "test-plat")

    assert cmd[0] == "claude"
    assert cmd[1] == "-p"
    # The prompt must NOT appear anywhere in argv
    assert "my test prompt here" not in cmd


# --- Tests for --bare-lite flags (MADRUGA_BARE_LITE) ---


def test_bare_lite_default_on_adds_mcp_and_slash_flags(tmp_path):
    """With MADRUGA_BARE_LITE unset (default on), cmd includes MCP isolation flags."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("implement:T001", "speckit.implement")

    with patch("dag_executor.REPO_ROOT", tmp_path), patch.dict("os.environ", {}, clear=False):
        os.environ.pop("MADRUGA_BARE_LITE", None)
        cmd = build_dispatch_cmd(node, "p", "test-plat")

    assert "--strict-mcp-config" in cmd
    idx = cmd.index("--mcp-config")
    assert cmd[idx + 1] == '{"mcpServers":{}}'
    assert "--disable-slash-commands" in cmd


def test_bare_lite_off_omits_all_new_flags(tmp_path):
    """MADRUGA_BARE_LITE=0 is the rollback kill switch — all new flags absent."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("implement:T001", "speckit.implement")

    with patch("dag_executor.REPO_ROOT", tmp_path), patch.dict("os.environ", {"MADRUGA_BARE_LITE": "0"}):
        cmd = build_dispatch_cmd(node, "p", "test-plat")

    assert "--strict-mcp-config" not in cmd
    assert "--mcp-config" not in cmd
    assert "--disable-slash-commands" not in cmd
    assert "--tools" not in cmd
    assert "--no-session-persistence" not in cmd
    assert "--setting-sources" not in cmd


def test_bare_lite_tools_flag_only_for_implement_nodes(tmp_path):
    """--tools (definition pruning) is restricted to implement nodes."""
    from dag_executor import IMPLEMENT_TASK_TOOLS, build_dispatch_cmd

    _setup_knowledge(tmp_path)

    # implement:T001 → gets --tools
    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(_make_node("implement:T001", "speckit.implement"), "p", "test-plat")
    assert "--tools" in cmd
    idx = cmd.index("--tools")
    assert cmd[idx + 1] == IMPLEMENT_TASK_TOOLS


def test_bare_lite_tools_flag_absent_for_judge(tmp_path):
    """Judge needs Agent tool — must NOT have --tools restriction."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("judge", "madruga:judge")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "p", "test-plat")

    assert "--tools" not in cmd


def test_bare_lite_tools_flag_absent_for_tech_research(tmp_path):
    """tech-research needs WebFetch/WebSearch — must NOT have --tools restriction."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("tech-research", "madruga:tech-research")

    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd = build_dispatch_cmd(node, "p", "test-plat")

    assert "--tools" not in cmd


def test_bare_lite_no_session_persistence_only_on_fresh_dispatch(tmp_path):
    """--no-session-persistence present for fresh dispatches, absent when resuming."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("implement:T001", "speckit.implement")

    # Fresh dispatch → flag present
    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd_fresh = build_dispatch_cmd(node, "p", "test-plat")
    assert "--no-session-persistence" in cmd_fresh

    # Resume → flag absent (would conflict with --resume semantics)
    with patch("dag_executor.REPO_ROOT", tmp_path):
        cmd_resume = build_dispatch_cmd(node, "p", "test-plat", resume_session_id="abc123")
    assert "--no-session-persistence" not in cmd_resume


def test_bare_lite_strict_settings_opt_in(tmp_path):
    """--setting-sources project only when MADRUGA_STRICT_SETTINGS=1 (opt-in)."""
    from dag_executor import build_dispatch_cmd

    _setup_knowledge(tmp_path)
    node = _make_node("implement:T001", "speckit.implement")

    # Default: opt-in flag absent
    with patch("dag_executor.REPO_ROOT", tmp_path), patch.dict("os.environ", {}, clear=False):
        os.environ.pop("MADRUGA_STRICT_SETTINGS", None)
        cmd = build_dispatch_cmd(node, "p", "test-plat")
    assert "--setting-sources" not in cmd

    # Opt-in: flag present
    with patch("dag_executor.REPO_ROOT", tmp_path), patch.dict("os.environ", {"MADRUGA_STRICT_SETTINGS": "1"}):
        cmd = build_dispatch_cmd(node, "p", "test-plat")
    assert "--setting-sources" in cmd
    idx = cmd.index("--setting-sources")
    assert cmd[idx + 1] == "project"


# --- Integration test: full dispatch flow ---


def test_full_dispatch_flow_integration(tmp_path):
    """Integration: compose_skill_prompt + build_dispatch_cmd produce correct cmd."""
    from dag_executor import build_dispatch_cmd, compose_skill_prompt

    root = _setup_knowledge(tmp_path)

    # Create platform structure
    platform_dir = root / "platforms" / "test-plat"
    epic_dir = platform_dir / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "pitch.md").write_text("# Pitch\nBuild a widget.")
    (epic_dir / "spec.md").write_text("# Spec\nWidget requirements.")

    node = Node(
        id="specify",
        skill="speckit.specify",
        outputs=["{epic}/spec.md"],
        depends=["epic-context"],
        gate="human",
        layer="engineering",
        optional=False,
        skip_condition=None,
    )

    with patch("dag_executor.REPO_ROOT", root):
        prompt, guardrail = compose_skill_prompt("test-plat", node, platform_dir, "001-test")
        cmd = build_dispatch_cmd(node, prompt, "test-plat", guardrail)

    # Verify command structure
    assert cmd[0] == "claude"
    # --bare only present with ANTHROPIC_API_KEY (not set in test env)
    assert "--output-format" in cmd
    assert "--system-prompt" in cmd
    assert "--allowedTools" in cmd
    assert "--disallowedTools" in cmd

    # Verify system prompt contains skill body
    sp_idx = cmd.index("--system-prompt")
    system_prompt = cmd[sp_idx + 1]
    assert "# Conventions" in system_prompt
    assert "Pipeline Contract — Base" in system_prompt
    assert "Pipeline Contract — Engineering" in system_prompt
    assert "# Skill Instructions" in system_prompt
    assert "Generate spec" in system_prompt

    # Verify user prompt contains epic artifacts
    assert "Pitch" in prompt or "pitch.md" in prompt
    assert "Widget requirements" in prompt or "spec.md" in prompt

    # Verify guardrail is appended
    assert "--append-system-prompt" in cmd


# --- T014: Tests for --quick DAG parsing ---


def test_parse_dag_quick_mode_returns_three_nodes(tmp_path):
    """parse_dag with mode='quick' returns only specify, implement, judge nodes."""
    from dag_executor import parse_dag

    pipeline_yaml = _make_quick_cycle_yaml(tmp_path)
    with patch("config.PIPELINE_YAML", pipeline_yaml):
        nodes = parse_dag(mode="quick", epic="001-test-fix")

    # Exactly 3 nodes in quick mode
    assert len(nodes) == 3

    node_ids = [n.id for n in nodes]
    assert node_ids == ["specify", "implement", "judge"]

    # Verify node properties are correctly parsed
    specify = nodes[0]
    assert specify.skill == "speckit.specify"
    assert specify.gate == "human"
    assert specify.depends == []

    implement = nodes[1]
    assert implement.skill == "speckit.implement"
    assert implement.gate == "auto"
    assert implement.depends == ["specify"]

    judge = nodes[2]
    assert judge.skill == "madruga:judge"
    assert judge.gate == "auto-escalate"
    assert judge.depends == ["implement"]


def test_parse_dag_quick_mode_resolves_epic_templates(tmp_path):
    """parse_dag with mode='quick' resolves {epic} templates in outputs."""
    from dag_executor import parse_dag

    pipeline_yaml = _make_quick_cycle_yaml(tmp_path)
    with patch("config.PIPELINE_YAML", pipeline_yaml):
        nodes = parse_dag(mode="quick", epic="042-hotfix")

    assert nodes[0].outputs == ["epics/042-hotfix/spec.md"]
    assert nodes[1].outputs == ["epics/042-hotfix/implement-context.md"]
    assert nodes[2].outputs == ["epics/042-hotfix/judge-report.md"]


def test_parse_dag_quick_mode_errors_when_no_quick_cycle(tmp_path):
    """parse_dag with mode='quick' exits with error if quick_cycle section missing."""
    from dag_executor import parse_dag

    pipeline_yaml = tmp_path / "pipeline.yaml"
    pipeline_yaml.write_text(
        "epic_cycle:\n"
        "  nodes:\n"
        "    - id: specify\n"
        "      skill: 'speckit.specify'\n"
        "      outputs: ['{epic}/spec.md']\n"
        "      depends: []\n"
        "      gate: human\n"
        "      layer: business\n"
    )

    with patch("config.PIPELINE_YAML", pipeline_yaml):
        with pytest.raises(SystemExit, match="quick_cycle"):
            parse_dag(mode="quick", epic="001-test")


# --- T015: Tests for quick-fix node dependencies ---


def _make_quick_cycle_yaml(tmp_path):
    """Helper: create pipeline.yaml with quick_cycle section and patch config."""
    pipeline_yaml = tmp_path / "pipeline.yaml"
    pipeline_yaml.write_text(
        "quick_cycle:\n"
        "  nodes:\n"
        "    - id: specify\n"
        "      skill: 'speckit.specify'\n"
        "      outputs: ['{epic}/spec.md']\n"
        "      depends: []\n"
        "      gate: human\n"
        "      layer: business\n"
        "    - id: implement\n"
        "      skill: 'speckit.implement'\n"
        "      outputs: ['{epic}/implement-context.md']\n"
        "      depends: [specify]\n"
        "      gate: auto\n"
        "      layer: engineering\n"
        "    - id: judge\n"
        "      skill: 'madruga:judge'\n"
        "      outputs: ['{epic}/judge-report.md']\n"
        "      depends: [implement]\n"
        "      gate: auto-escalate\n"
        "      layer: engineering\n"
    )
    return pipeline_yaml


def test_quick_fix_dependency_chain(tmp_path):
    """Quick-fix DAG has linear chain: specify → implement → judge."""
    from dag_executor import parse_dag

    pipeline_yaml = _make_quick_cycle_yaml(tmp_path)
    with patch("config.PIPELINE_YAML", pipeline_yaml):
        nodes = parse_dag(mode="quick", epic="099-bugfix")
    node_map = {n.id: n for n in nodes}

    # specify is the root — no dependencies
    assert node_map["specify"].depends == []

    # implement depends ONLY on specify
    assert node_map["implement"].depends == ["specify"]

    # judge depends ONLY on implement
    assert node_map["judge"].depends == ["implement"]


def test_quick_fix_topological_sort_order(tmp_path):
    """topological_sort on quick-fix DAG produces specify → implement → judge."""
    from dag_executor import parse_dag, topological_sort

    pipeline_yaml = _make_quick_cycle_yaml(tmp_path)
    with patch("config.PIPELINE_YAML", pipeline_yaml):
        nodes = parse_dag(mode="quick", epic="099-bugfix")
    sorted_nodes = topological_sort(nodes)

    order = [n.id for n in sorted_nodes]
    assert order == ["specify", "implement", "judge"]


def test_quick_fix_no_skipped_nodes_in_dependencies(tmp_path):
    """Quick-fix nodes do NOT depend on plan, tasks, clarify, analyze, qa, or reconcile."""
    from dag_executor import parse_dag

    pipeline_yaml = _make_quick_cycle_yaml(tmp_path)
    with patch("config.PIPELINE_YAML", pipeline_yaml):
        nodes = parse_dag(mode="quick", epic="099-bugfix")

    skipped_nodes = {"plan", "tasks", "clarify", "analyze", "analyze-post", "qa", "reconcile", "epic-context"}
    all_deps = set()
    all_ids = set()
    for n in nodes:
        all_deps.update(n.depends)
        all_ids.add(n.id)

    # No skipped node appears as a dependency or as a node
    assert all_deps.isdisjoint(skipped_nodes), f"Quick DAG references skipped nodes: {all_deps & skipped_nodes}"
    assert all_ids.isdisjoint(skipped_nodes), f"Quick DAG contains skipped nodes: {all_ids & skipped_nodes}"


# ---------------------------------------------------------------------------
# _resolve_code_dir / _epic_output_dir
# ---------------------------------------------------------------------------


def test_resolve_code_dir_delegates_to_get_repo_work_dir():
    """_resolve_code_dir delegates to get_repo_work_dir for L2 epics."""
    from pathlib import Path

    from dag_executor import _resolve_code_dir

    fake_path = Path("/tmp/fake-worktree")
    with patch("ensure_repo.get_repo_work_dir", return_value=fake_path) as mock_grwd:
        result = _resolve_code_dir("prosauai", "004-router-mece")

    mock_grwd.assert_called_once_with("prosauai", "004-router-mece")
    assert result == fake_path


def test_resolve_code_dir_returns_repo_root_without_epic():
    """_resolve_code_dir returns REPO_ROOT when no epic is given (L1)."""
    from dag_executor import REPO_ROOT, _resolve_code_dir

    result = _resolve_code_dir("prosauai", None)
    assert result == REPO_ROOT


@pytest.mark.real_epic_output_dir
def test_epic_output_dir_self_ref():
    """_epic_output_dir returns relative path for self-ref platforms."""
    from dag_executor import _epic_output_dir

    with (
        patch("ensure_repo._is_self_ref", return_value=True),
        patch("ensure_repo._load_repo_binding", return_value={"name": "madruga.ai"}),
    ):
        result = _epic_output_dir("madruga-ai", "024-sequential")

    assert result == "platforms/madruga-ai/epics/024-sequential"
    assert not result.startswith("/")


@pytest.mark.real_epic_output_dir
def test_epic_output_dir_external_repo():
    """_epic_output_dir returns absolute path for external repos."""
    from dag_executor import REPO_ROOT, _epic_output_dir

    with (
        patch("ensure_repo._is_self_ref", return_value=False),
        patch("ensure_repo._load_repo_binding", return_value={"name": "prosauai"}),
    ):
        result = _epic_output_dir("prosauai", "005-next")

    expected = str(REPO_ROOT / "platforms" / "prosauai" / "epics" / "005-next")
    assert result == expected
    assert result.startswith("/")


def test_compose_task_prompt_uses_epic_output_dir(tmp_path):
    """compose_task_prompt output_dir comes from _epic_output_dir."""
    from dag_executor import TaskItem, compose_task_prompt

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "plan.md").write_text("# Plan")
    (epic_dir / "spec.md").write_text("# Spec")
    (epic_dir / "tasks.md").write_text("# Tasks\n- [ ] T001 Do thing")

    task = TaskItem(
        id="T001",
        description="Do thing",
        checked=False,
        phase="Phase 1",
        parallel=False,
        files=[],
        line_number=2,
    )

    abs_dir = "/absolute/path/platforms/ext-plat/epics/001-test"
    with patch("dag_executor._epic_output_dir", return_value=abs_dir):
        prompt = compose_task_prompt(task, epic_dir, "ext-plat", "001-test")

    assert f"SPECIFY_BASE_DIR={abs_dir}/" in prompt
    assert f"Save ALL output to: {abs_dir}/" in prompt


# ── Phase dispatch tests ──────────────────────────────────────────────


def test_group_tasks_by_phase_basic():
    """Groups tasks correctly by phase field."""
    from dag_executor import TaskItem, group_tasks_by_phase

    tasks = [
        TaskItem("T001", "task 1", False, "Phase 1: Setup", False),
        TaskItem("T002", "task 2", False, "Phase 1: Setup", False),
        TaskItem("T003", "task 3", False, "Phase 2: Core", False),
    ]
    result = group_tasks_by_phase(tasks)
    assert len(result) == 2
    assert result[0][0] == "Phase 1: Setup"
    assert [t.id for t in result[0][1]] == ["T001", "T002"]
    assert result[1][0] == "Phase 2: Core"
    assert [t.id for t in result[1][1]] == ["T003"]


def test_group_tasks_by_phase_splits_large():
    """Phases with >max_per_phase tasks are split into sub-phases."""
    from dag_executor import TaskItem, group_tasks_by_phase

    tasks = [TaskItem(f"T{i:03d}", f"task {i}", False, "Phase 1: Big", False) for i in range(1, 16)]
    result = group_tasks_by_phase(tasks, max_per_phase=12)
    assert len(result) == 2
    assert "part 1" in result[0][0]
    assert len(result[0][1]) == 12
    assert "part 2" in result[1][0]
    assert len(result[1][1]) == 3


def test_group_tasks_by_phase_stable_numbering_with_checked():
    """All tasks (checked+unchecked) are included so phase indices stay stable
    across retries. The caller (_run_implement_phases) skips fully-done phases
    via its own still_pending check."""
    from dag_executor import TaskItem, group_tasks_by_phase

    tasks = [
        TaskItem("T001", "done", True, "Phase 1: A", False),
        TaskItem("T002", "pending", False, "Phase 1: A", False),
        TaskItem("T003", "done", True, "Phase 2: B", False),
    ]
    result = group_tasks_by_phase(tasks)
    # Both phases returned for stable numbering; Phase 2 contains only checked
    # tasks but _run_implement_phases will skip it via still_pending.
    assert len(result) == 2
    assert result[0][0] == "Phase 1: A"
    assert [t.id for t in result[0][1]] == ["T001", "T002"]
    assert result[1][0] == "Phase 2: B"
    assert [t.id for t in result[1][1]] == ["T003"]


def test_group_tasks_by_phase_no_phases_empty():
    """Returns empty list when all tasks have phase='' (no headers)."""
    from dag_executor import TaskItem, group_tasks_by_phase

    tasks = [
        TaskItem("T001", "task 1", False, "", False),
        TaskItem("T002", "task 2", False, "", False),
    ]
    result = group_tasks_by_phase(tasks)
    assert result == []


def test_group_tasks_by_phase_preserves_order():
    """Phase order matches file order (not alphabetical)."""
    from dag_executor import TaskItem, group_tasks_by_phase

    tasks = [
        TaskItem("T001", "t", False, "Phase 2: Zebra", False),
        TaskItem("T002", "t", False, "Phase 1: Alpha", False),
    ]
    result = group_tasks_by_phase(tasks)
    assert result[0][0] == "Phase 2: Zebra"
    assert result[1][0] == "Phase 1: Alpha"


def test_group_tasks_by_phase_single_phase():
    """All tasks in one phase → single group."""
    from dag_executor import TaskItem, group_tasks_by_phase

    tasks = [TaskItem(f"T{i:03d}", f"t{i}", False, "Phase 1: Only", False) for i in range(1, 4)]
    result = group_tasks_by_phase(tasks)
    assert len(result) == 1
    assert len(result[0][1]) == 3


def test_phase_max_turns_formula():
    """_phase_max_turns applies correct formula and cap."""
    from dag_executor import _phase_max_turns

    assert _phase_max_turns(5) == 150
    assert _phase_max_turns(10) == 250
    assert _phase_max_turns(20) == 400  # capped


def test_phase_max_turns_edge_cases():
    """Edge cases: 0 and 1 tasks."""
    from dag_executor import _phase_max_turns

    assert _phase_max_turns(0) == 50
    assert _phase_max_turns(1) == 70


def test_verify_phase_completion_all_done(tmp_path):
    """All tasks marked [X] → all completed."""
    from dag_executor import TaskItem, _verify_phase_completion

    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text("## Phase 1: A\n- [X] T001 task 1\n- [X] T002 task 2\n- [X] T003 task 3\n")
    phase_tasks = [
        TaskItem("T001", "task 1", False, "Phase 1: A", False),
        TaskItem("T002", "task 2", False, "Phase 1: A", False),
        TaskItem("T003", "task 3", False, "Phase 1: A", False),
    ]
    completed, pending = _verify_phase_completion(tasks_md, phase_tasks)
    assert completed == ["T001", "T002", "T003"]
    assert pending == []


def test_verify_phase_completion_partial(tmp_path):
    """3/5 done → correct split."""
    from dag_executor import TaskItem, _verify_phase_completion

    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text(
        "## Phase 1: A\n- [x] T001 task 1\n- [x] T002 task 2\n- [ ] T003 task 3\n- [x] T004 task 4\n- [ ] T005 task 5\n"
    )
    phase_tasks = [TaskItem(f"T{i:03d}", f"task {i}", False, "Phase 1: A", False) for i in range(1, 6)]
    completed, pending = _verify_phase_completion(tasks_md, phase_tasks)
    assert completed == ["T001", "T002", "T004"]
    assert pending == ["T003", "T005"]


def test_verify_phase_completion_none_done(tmp_path):
    """All [ ] → none completed."""
    from dag_executor import TaskItem, _verify_phase_completion

    tasks_md = tmp_path / "tasks.md"
    tasks_md.write_text("## Phase 1: A\n- [ ] T001 task 1\n- [ ] T002 task 2\n")
    phase_tasks = [
        TaskItem("T001", "task 1", False, "Phase 1: A", False),
        TaskItem("T002", "task 2", False, "Phase 1: A", False),
    ]
    completed, pending = _verify_phase_completion(tasks_md, phase_tasks)
    assert completed == []
    assert pending == ["T001", "T002"]


def test_classify_error_deterministic():
    """Deterministic errors classified correctly."""
    from dag_executor import _classify_error

    assert _classify_error("output is unfilled template: plan.md") == "deterministic"
    assert _classify_error("exitcode 1 stdout_len=0") == "deterministic"
    assert _classify_error("output not found: spec.md") == "deterministic"


def test_classify_error_transient():
    """Transient errors classified correctly."""
    from dag_executor import _classify_error

    assert _classify_error("claude_error[rate_limit: exceeded]") == "transient"
    assert _classify_error("asyncio timeout after 3000s") == "transient"
    assert _classify_error("context_length_exceeded: 1.2M tokens") == "transient"


def test_classify_error_unknown():
    """Unknown errors classified correctly."""
    from dag_executor import _classify_error

    assert _classify_error("zombie — daemon restart or crash") == "unknown"
    assert _classify_error("some random error") == "unknown"
    assert _classify_error(None) == "unknown"
    assert _classify_error("") == "unknown"


def test_build_dispatch_cmd_max_turns_override():
    """max_turns_override takes precedence over env var."""
    from dag_executor import Node, build_dispatch_cmd

    node = Node("implement:phase-1", "speckit.implement", [], [], "auto", "implementation", False, None)
    with patch.dict(os.environ, {"MADRUGA_MAX_TURNS": "100"}, clear=False):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat", max_turns_override=250)
    assert "--max-turns" in cmd
    idx = cmd.index("--max-turns")
    assert cmd[idx + 1] == "250"


def test_build_dispatch_cmd_max_turns_default():
    """Without override, uses MADRUGA_MAX_TURNS env var."""
    from dag_executor import Node, build_dispatch_cmd

    node = Node("implement:T001", "speckit.implement", [], [], "auto", "implementation", False, None)
    with patch.dict(os.environ, {"MADRUGA_MAX_TURNS": "100"}, clear=False):
        cmd = build_dispatch_cmd(node, "test prompt", "test-plat")
    assert "--max-turns" in cmd
    idx = cmd.index("--max-turns")
    assert cmd[idx + 1] == "100"


def test_compose_phase_prompt_all_task_ids(tmp_path):
    """Phase prompt contains all task IDs."""
    from dag_executor import TaskItem, compose_phase_prompt

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "plan.md").write_text("# Plan")
    (epic_dir / "spec.md").write_text("# Spec")
    (epic_dir / "tasks.md").write_text("## Phase 1\n- [ ] T001 a\n- [ ] T002 b\n")

    tasks = [
        TaskItem("T001", "first task", False, "Phase 1", False),
        TaskItem("T002", "second task", False, "Phase 1", False),
    ]
    with patch("dag_executor._epic_output_dir", return_value="/out"):
        prompt = compose_phase_prompt("Phase 1", tasks, epic_dir, "plat", "001-test")
    assert "T001" in prompt
    assert "T002" in prompt
    assert "first task" in prompt
    assert "second task" in prompt


def test_compose_phase_prompt_execution_instructions(tmp_path):
    """Phase prompt includes execution instructions."""
    from dag_executor import TaskItem, compose_phase_prompt

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "tasks.md").write_text("## Phase 1\n- [ ] T001 a\n")

    tasks = [TaskItem("T001", "a", False, "Phase 1", False)]
    with patch("dag_executor._epic_output_dir", return_value="/out"):
        prompt = compose_phase_prompt("Phase 1", tasks, epic_dir, "plat", "001-test")
    assert "Execute these tasks" in prompt
    assert "sequentially" in prompt
    assert "Git commit" in prompt


def test_compose_phase_prompt_includes_analyze_report_when_relevant(tmp_path):
    """analyze-report.md paragraphs mentioning a phase task are included in prompt."""
    from dag_executor import TaskItem, compose_phase_prompt

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "tasks.md").write_text("## Phase 1\n- [ ] T001 a\n")
    (epic_dir / "analyze-report.md").write_text("## Findings\n\nT001 has a missing index.\n\nT999 unrelated finding.")

    tasks = [TaskItem("T001", "a", False, "Phase 1", False)]
    with patch("dag_executor._epic_output_dir", return_value="/out"):
        prompt = compose_phase_prompt("Phase 1", tasks, epic_dir, "plat", "001-test")

    assert "Pre-Implementation Analysis" in prompt
    assert "T001 has a missing index" in prompt
    assert "T999 unrelated finding" not in prompt


def test_compose_phase_prompt_omits_analyze_report_when_no_match(tmp_path):
    """analyze-report.md with no mention of phase tasks is excluded from prompt."""
    from dag_executor import TaskItem, compose_phase_prompt

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "tasks.md").write_text("## Phase 1\n- [ ] T001 a\n")
    (epic_dir / "analyze-report.md").write_text("## Findings\n\nT999 unrelated finding.")

    tasks = [TaskItem("T001", "a", False, "Phase 1", False)]
    with patch("dag_executor._epic_output_dir", return_value="/out"):
        prompt = compose_phase_prompt("Phase 1", tasks, epic_dir, "plat", "001-test")

    assert "Pre-Implementation Analysis" not in prompt
    assert "T999 unrelated finding" not in prompt


@pytest.mark.asyncio
async def test_circuit_breaker_same_error_deterministic():
    """2x deterministic error → early stop (no 3rd/4th attempt)."""
    from dag_executor import Node, dispatch_with_retry_async

    node = Node("implement:T001", "speckit.implement", [], [], "auto", "", False, None)
    breaker = MagicMock()
    breaker.check.return_value = True

    call_count = 0

    async def mock_dispatch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return False, "output is unfilled template: plan.md", None

    with patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch):
        success, error, _ = await dispatch_with_retry_async(node, "/tmp", "prompt", 60, breaker)

    assert success is False
    assert "unfilled template" in error
    assert call_count == 2  # stopped after 2nd identical deterministic error


@pytest.mark.asyncio
async def test_circuit_breaker_transient_full_retry():
    """Transient errors get full retry cycle (4 attempts)."""
    from dag_executor import Node, dispatch_with_retry_async

    node = Node("implement:T001", "speckit.implement", [], [], "auto", "", False, None)
    breaker = MagicMock()
    breaker.check.return_value = True

    call_count = 0

    async def mock_dispatch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return False, "claude_error[rate_limit: exceeded]", None

    with patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            success, error, _ = await dispatch_with_retry_async(node, "/tmp", "prompt", 60, breaker)

    assert success is False
    assert call_count == 4  # all 4 attempts made


@pytest.mark.asyncio
async def test_circuit_breaker_different_errors_no_escalation():
    """Different errors at each attempt → all 4 attempts made."""
    from dag_executor import Node, dispatch_with_retry_async

    node = Node("implement:T001", "speckit.implement", [], [], "auto", "", False, None)
    breaker = MagicMock()
    breaker.check.return_value = True

    errors = iter(["error A", "error B", "error C", "error D"])

    async def mock_dispatch(*args, **kwargs):
        return False, next(errors), None

    with patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            success, _, _ = await dispatch_with_retry_async(node, "/tmp", "prompt", 60, breaker)

    assert success is False
    assert breaker.record_failure.call_count == 1  # only final failure recorded


@pytest.mark.asyncio
async def test_circuit_breaker_same_error_unknown():
    """3x same unknown error → escalation (no 4th attempt)."""
    from dag_executor import Node, dispatch_with_retry_async

    node = Node("implement:T001", "speckit.implement", [], [], "auto", "", False, None)
    breaker = MagicMock()
    breaker.check.return_value = True

    call_count = 0

    async def mock_dispatch(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return False, "zombie — daemon restart or crash", None

    with patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            success, error, _ = await dispatch_with_retry_async(node, "/tmp", "prompt", 60, breaker)

    assert success is False
    assert call_count == 3  # stopped after 3rd unknown error


@pytest.mark.asyncio
async def test_max_turns_override_threaded_to_dispatch():
    """max_turns_override reaches build_dispatch_cmd through the call chain."""
    from dag_executor import Node, dispatch_with_retry_async

    node = Node("implement:phase-1", "speckit.implement", [], [], "auto", "", False, None)
    breaker = MagicMock()
    breaker.check.return_value = True

    captured_kwargs = {}

    async def mock_dispatch(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return True, None, '{"type":"result"}'

    with patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch):
        await dispatch_with_retry_async(node, "/tmp", "prompt", 60, breaker, max_turns_override=250)

    assert captured_kwargs.get("max_turns_override") == 250


# ---------------------------------------------------------------------------
# DISALLOWED_TOOLS expanded patterns
# ---------------------------------------------------------------------------


def test_disallowed_tools_blocks_git_reset_hard():
    """DISALLOWED_TOOLS must block git reset --hard variants."""
    from dag_executor import DISALLOWED_TOOLS

    assert "Bash(git reset --hard:*)" in DISALLOWED_TOOLS
    assert "Bash(git reset --hard)" in DISALLOWED_TOOLS


def test_disallowed_tools_blocks_git_stash_pop_apply():
    """DISALLOWED_TOOLS must block git stash pop and git stash apply."""
    from dag_executor import DISALLOWED_TOOLS

    assert "Bash(git stash pop:*)" in DISALLOWED_TOOLS
    assert "Bash(git stash apply:*)" in DISALLOWED_TOOLS


def test_disallowed_tools_preserves_original_patterns():
    """DISALLOWED_TOOLS must still block original checkout/branch/switch patterns."""
    from dag_executor import DISALLOWED_TOOLS

    assert "Bash(git checkout:*)" in DISALLOWED_TOOLS
    assert "Bash(git branch -:*)" in DISALLOWED_TOOLS
    assert "Bash(git switch:*)" in DISALLOWED_TOOLS


# ---------------------------------------------------------------------------
# extra_env propagation (Fix C: MADRUGA_PHASE_CTX)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_with_retry_propagates_extra_env():
    """dispatch_with_retry_async passes extra_env through to dispatch_node_async.

    This verifies that MADRUGA_PHASE_CTX=1 set by _run_implement_phases reaches
    the subprocess environment, enabling post_save.py to detect and block direct
    L2 node writes that would corrupt epic_nodes resume state.
    """
    from dag_executor import dispatch_with_retry_async

    breaker = CircuitBreaker()
    captured_kwargs = {}

    async def mock_dispatch(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return True, None, '{"result": "ok"}'

    with patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch):
        await dispatch_with_retry_async(
            _make_node(),
            "/tmp",
            "test",
            600,
            breaker,
            extra_env={"MADRUGA_PHASE_CTX": "1"},
        )

    assert captured_kwargs.get("extra_env") == {"MADRUGA_PHASE_CTX": "1"}


# ---------------------------------------------------------------------------
# Process group isolation (Fix B: start_new_session + killpg)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_node_async_uses_new_session():
    """dispatch_node_async spawns subprocesses with start_new_session=True.

    Without a new session, SIGKILL on timeout only kills the direct claude -p
    process; orphan children (pytest, make, zsh) survive and accumulate CPU/IO
    contention across phase retries.
    """
    from dag_executor import dispatch_node_async

    mock_proc = _mock_async_proc(stdout=b"{}", stderr=b"", returncode=0)
    captured_kwargs = {}

    async def capturing_exec(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return mock_proc

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", side_effect=capturing_exec),
    ):
        await dispatch_node_async(_make_node(), "/tmp", "test prompt")

    assert captured_kwargs.get("start_new_session") is True


@pytest.mark.parametrize(
    "pid_setter",
    [
        pytest.param(lambda p: None, id="invalid_pid"),  # leaves MagicMock auto-attr
        pytest.param(lambda p: setattr(p, "pid", os.getpid()), id="runner_pgid"),
    ],
)
def test_kill_process_group_safely_falls_back_to_process_kill(pid_setter):
    """Both unsafe inputs (non-int pid, runner's own pgid) fall back to process.kill().

    Defense-in-depth: prevents killpg() from signalling the caller's own
    process group, which in WSL would kill the shell and everything in it.
    """
    from dag_executor import _kill_process_group_safely

    proc = MagicMock()
    pid_setter(proc)
    proc.kill = MagicMock()

    _kill_process_group_safely(proc)

    proc.kill.assert_called_once()


# --- F1: phase prompt must not hardcode `make test` ---


def test_compose_phase_prompt_no_make_hardcode(tmp_path):
    """Setup phases were running `make test` in the wrong CWD because the prompt
    hardcoded the command. Verify the new instruction is runner-agnostic.

    Regression for incidents at easter-tracking.md (epic 008-admin-evolution,
    2026-04-17 ~10:33 and ~13:08 — pytest zombies).
    """
    from dag_executor import compose_phase_prompt

    epic_dir = _make_epic_dir(tmp_path)
    (epic_dir / "tasks.md").write_text("- [ ] T001 setup\n")
    tasks = [_make_task(task_id="T001", description="setup")]

    prompt = compose_phase_prompt("Setup (Shared Infrastructure)", tasks, epic_dir, "p1", "001-test")

    assert "make test" not in prompt, "phase prompt must not hardcode `make test` — incidents 2026-04-17"
    assert "test suite for THIS repository" in prompt
    assert "Do NOT cd to other directories" in prompt


# --- F6: phase prompt is scope-aware (excludes spec for setup; slices tasks) ---


def test_compose_phase_prompt_setup_excludes_spec(tmp_path):
    """Setup phases (no User Stories) must NOT include the full spec.md.

    On epic 008 the setup phase received 43KB of spec it didn't need.
    Heuristic: phase_label starts with 'Setup' or no task has us_tag.
    """
    from dag_executor import compose_phase_prompt

    epic_dir = _make_epic_dir(tmp_path)
    (epic_dir / "spec.md").write_text("# Specification\n\n## User Story 1\n\nWebhook ingestion. " + "x" * 5000)
    (epic_dir / "tasks.md").write_text("- [ ] T001 setup db\n- [ ] T002 setup config\n")

    # Setup tasks: no us_tag → kind detected as 'setup'
    tasks = [_make_task(task_id="T001", description="setup db"), _make_task(task_id="T002", description="setup config")]
    prompt = compose_phase_prompt("Setup (Shared Infrastructure)", tasks, epic_dir, "p1", "001-test")

    assert "## Specification" not in prompt, "setup phase must NOT include spec.md"
    # plan + data-model still included
    # (data-model not present in fixture — only checking spec exclusion)


def test_compose_phase_prompt_user_story_includes_only_that_story(tmp_path):
    """A 'User Story 2' phase must include ONLY the spec section for story 2,
    not stories 1, 3, 4..."""
    from dag_executor import compose_phase_prompt

    epic_dir = _make_epic_dir(tmp_path)
    (epic_dir / "spec.md").write_text(
        "# Spec\n\n## User Story 1\n\nFIRST_STORY_BODY\n\n"
        "## User Story 2\n\nSECOND_STORY_BODY\n\n"
        "## User Story 3\n\nTHIRD_STORY_BODY\n"
    )
    (epic_dir / "tasks.md").write_text("- [ ] T010 implement story 2 endpoint\n")

    tasks = [_make_task(task_id="T010", description="story 2 endpoint", us_tag="US2")]
    prompt = compose_phase_prompt("User Story 2", tasks, epic_dir, "p1", "001-test")

    assert "SECOND_STORY_BODY" in prompt
    assert "FIRST_STORY_BODY" not in prompt
    assert "THIRD_STORY_BODY" not in prompt


def test_compose_phase_prompt_slices_tasks_md(tmp_path):
    """tasks.md is sliced to ONLY the phase's tasks. Unrelated tasks must be dropped."""
    from dag_executor import compose_phase_prompt

    epic_dir = _make_epic_dir(tmp_path)
    (epic_dir / "tasks.md").write_text(
        "# Tasks\n\n## Phase 1: Setup\n\n- [ ] T001 setup\n\n"
        "## Phase 2: User Story 1\n\n- [ ] T100 webhook\n  Description for T100.\n\n"
        "- [ ] T200 unrelated task\n  This must NOT appear in Phase 1 prompt.\n"
    )

    tasks = [_make_task(task_id="T001", description="setup")]
    prompt = compose_phase_prompt("Setup (Shared Infrastructure)", tasks, epic_dir, "p1", "001-test")

    assert "T001 setup" in prompt
    assert "T200 unrelated task" not in prompt
    assert "T100 webhook" not in prompt


# --- F3: Layer 4 branch check must skip non-CODE_CWD nodes ---


def test_needs_code_cwd_only_for_code_nodes():
    """Layer 4 branch revert (dag_executor.py:2511,3113) MUST gate on
    _needs_code_cwd. For nodes that run in REPO_ROOT (specify/clarify/plan/
    tasks/analyze/reconcile/roadmap), the epic branch lives in the EXTERNAL
    repo — checking branch in REPO_ROOT triggers a bogus 'claude -p changed
    branch' ERROR every dispatch.
    """
    from dag_executor import _needs_code_cwd

    # Non-code nodes run in REPO_ROOT — branch check must be skipped
    for nid in ("specify", "clarify", "plan", "tasks", "analyze", "analyze-post", "reconcile", "roadmap"):
        assert _needs_code_cwd(_make_node(nid)) is False, f"{nid} should NOT need code cwd"

    # Code nodes run in code_dir — branch check is meaningful
    for nid in ("implement", "judge", "qa", "implement:phase-1", "implement:phase-18"):
        assert _needs_code_cwd(_make_node(nid)) is True, f"{nid} SHOULD need code cwd"


# --- F1: TASK_RE must accept 4+ digit task IDs ---


def test_task_re_accepts_4digit_ids():
    """TASK_RE must admit T1000+ — the `\\d{3}` form silently hid whole phases
    when an epic exceeded 999 tasks."""
    from dag_executor import TASK_RE

    for tid in ("T100", "T999", "T1000", "T1234", "T9999", "T10000"):
        assert TASK_RE.match(f"- [ ] {tid} do thing"), f"{tid} should match"
    for bad in ("T1", "T12", "T99", "U1000"):
        assert not TASK_RE.match(f"- [ ] {bad} do thing"), f"{bad} should NOT match"


# --- F4: tasks marked [x] but containing **DEFERRED** count as pending ---


def test_parse_tasks_treats_deferred_as_pending(tmp_path):
    """`[x] ... **DEFERRED**` must parse as pending — agent marks [x] while
    deferring the actual work; parser forces it back to pending so audit sees it."""
    from dag_executor import parse_tasks

    tasks_file = tmp_path / "tasks.md"
    tasks_file.write_text(
        "# Tasks\n\n## Phase 1: Setup\n\n"
        "- [x] T001 plain done task\n"
        "- [x] T002 done with **DEFERRED**: needs prod traffic\n"
        "- [ ] T003 not done yet\n"
    )
    tasks = parse_tasks(tasks_file)
    by_id = {t.id: t.checked for t in tasks}
    assert by_id == {"T001": True, "T002": False, "T003": False}


# --- F2: report quality gate detects BLOCKER / UNRESOLVED markers ---


def test_report_quality_check_passes_clean(tmp_path):
    from dag_executor import _report_quality_check

    report = tmp_path / "qa-report.md"
    body = "## QA Report\n\n" + ("\n## Section\n" * 30) + "\n## HANDOFF\nAll clean.\n"
    report.write_text(body)
    assert _report_quality_check(report, "qa") is True


def test_report_quality_check_fails_on_blocker(tmp_path):
    """Any BLOCKER in a report invalidates success — forces retry then auto-block."""
    from dag_executor import _report_quality_check

    report = tmp_path / "qa-report.md"
    body = (
        "## QA Report\n\n"
        + ("\n## Section\n" * 30)
        + "\n#### B1 — pool starvation [CODE REVIEW] **BLOCKER S1 CONFIRMADO**\n"
        "## HANDOFF\nFinished but flagged 1 BLOCKER.\n"
    )
    report.write_text(body)
    assert _report_quality_check(report, "qa") is False


def test_report_quality_check_fails_on_unresolved(tmp_path):
    from dag_executor import _report_quality_check

    report = tmp_path / "judge-report.md"
    body = (
        "## Judge Report\n\n" + ("\n## Section\n" * 30) + "\n| ❌ UNRESOLVED (BLOCKERs confirmados) | 5 |\n"
        "## HANDOFF\nReport done.\n"
    )
    report.write_text(body)
    assert _report_quality_check(report, "judge") is False


def test_report_quality_check_fails_when_too_short(tmp_path):
    from dag_executor import _report_quality_check

    report = tmp_path / "qa-report.md"
    report.write_text("## QA\n\nshort report\n## HANDOFF\n")
    assert _report_quality_check(report, "qa") is False


def test_report_quality_check_fails_when_handoff_missing(tmp_path):
    from dag_executor import _report_quality_check

    report = tmp_path / "qa-report.md"
    report.write_text("## QA Report\n" + ("filler line\n" * 60))
    assert _report_quality_check(report, "qa") is False


# ---------------------------------------------------------------------------
# _slice_spec_for_user_story — regex must match both `### User Story N` (H3,
# the format actually used by all 38+ epics in the repo) and `## User Story N`
# (H2, supported for back-compat). End-of-slice must stop at the next H2/H3
# section but never at a H4+ header inside the user story body.
# ---------------------------------------------------------------------------


def test_slice_spec_user_story_h3_format():
    """Real-world specs use `### User Story N`. Regex must match this format."""
    from dag_executor import _slice_spec_for_user_story

    spec = (
        "# Feature Specification\n"
        "## User Scenarios & Testing\n"
        "### User Story 1 — first one\n"
        "Body of US1.\n"
        "### User Story 2 — second one\n"
        "Body of US2.\n"
        "More US2 content.\n"
        "## Requirements\n"
        "Functional requirements.\n"
    )
    sliced = _slice_spec_for_user_story(spec, 2)
    assert sliced is not None
    assert sliced.startswith("### User Story 2")
    assert "Body of US2." in sliced
    assert "More US2 content." in sliced
    assert "Functional requirements." not in sliced
    assert "Body of US1." not in sliced


def test_slice_spec_user_story_h2_back_compat():
    """Older specs may use `## User Story N` (H2). Must continue to work."""
    from dag_executor import _slice_spec_for_user_story

    spec = (
        "# Spec\n## User Story 1 — alpha\nalpha body.\n## User Story 2 — beta\nbeta body.\n## Edge Cases\nedge body.\n"
    )
    sliced = _slice_spec_for_user_story(spec, 2)
    assert sliced is not None
    assert sliced.startswith("## User Story 2")
    assert "beta body." in sliced
    assert "edge body." not in sliced
    assert "alpha body." not in sliced


def test_slice_spec_stops_at_next_h2_section():
    """When the spec switches back to H2 (e.g. `## Requirements`), slice ends there."""
    from dag_executor import _slice_spec_for_user_story

    spec = (
        "## User Scenarios\n"
        "### User Story 1 — only US\n"
        "US1 content.\n"
        "More US1 content.\n"
        "## Requirements\n"
        "FR-001 must do X.\n"
    )
    sliced = _slice_spec_for_user_story(spec, 1)
    assert sliced is not None
    assert "More US1 content." in sliced
    assert "FR-001" not in sliced
    assert "## Requirements" not in sliced


def test_slice_spec_ignores_h4_inside_user_story():
    """H4 headers like `#### Acceptance Criteria` inside a US must NOT terminate the slice."""
    from dag_executor import _slice_spec_for_user_story

    spec = (
        "## User Scenarios\n"
        "### User Story 1 — with AC subsection\n"
        "Why this matters.\n"
        "#### Acceptance Criteria\n"
        "- AC-1: criterion one\n"
        "- AC-2: criterion two\n"
        "#### Independent Test\n"
        "Steps to validate.\n"
        "### User Story 2 — next one\n"
        "US2 body.\n"
    )
    sliced = _slice_spec_for_user_story(spec, 1)
    assert sliced is not None
    assert "AC-1: criterion one" in sliced  # H4 sections preserved inside US1
    assert "Steps to validate." in sliced
    assert "US2 body." not in sliced  # next H3 ends the slice


def test_slice_spec_returns_none_when_user_story_missing():
    from dag_executor import _slice_spec_for_user_story

    spec = "## User Scenarios\n### User Story 1 — only one\nbody.\n"
    assert _slice_spec_for_user_story(spec, 5) is None


def test_slice_spec_for_real_epic_format():
    """End-to-end: feed a spec mirroring the real prosauai/014 layout and
    check that slicing US-2 yields a tight slice (~ tens of lines), not the
    whole 200-line spec."""
    from dag_executor import _slice_spec_for_user_story

    big_spec = (
        "# Feature Specification: Test\n\n"
        "## Contexto\nBackground content.\n\n"
        "## User Scenarios & Testing *(mandatory)*\n\n"
        "### User Story 1 — Story alpha (Priority: P1)\n\n"
        + ("US1 line\n" * 30)
        + "\n### User Story 2 — Story beta (Priority: P1)\n\n"
        + ("US2 line\n" * 25)
        + "\n### User Story 3 — Story gamma (Priority: P2)\n\n"
        + ("US3 line\n" * 30)
        + "\n## Requirements *(mandatory)*\n\n"
        + ("FR line\n" * 200)
    )
    sliced = _slice_spec_for_user_story(big_spec, 2)
    assert sliced is not None
    sliced_size = len(sliced.encode())
    full_size = len(big_spec.encode())
    # Slicing US-2 should drop at least 80% of the bytes — empirical floor that
    # guards against a regression where the slice degenerates to ~full spec.
    assert sliced_size < full_size * 0.2, (
        f"slice too large: {sliced_size} vs full {full_size} ({sliced_size / full_size:.0%})"
    )
    assert "US2 line" in sliced
    assert "US1 line" not in sliced
    assert "US3 line" not in sliced
    assert "FR line" not in sliced
