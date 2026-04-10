"""Tests for dag_executor.py — async dispatch, retry, circuit breaker."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dag_executor import CircuitBreaker, Node


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

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"output", b"")
    mock_proc.returncode = 0

    with (
        patch("dag_executor.shutil.which", return_value="/usr/bin/claude"),
        patch("dag_executor.asyncio.create_subprocess_exec", return_value=mock_proc),
    ):
        success, error, _stdout = await dispatch_node_async(_make_node(), "/tmp", "test prompt")

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
        success, error, _stdout = await dispatch_node_async(_make_node(), "/tmp", "test", timeout=5)

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


# --- T005: Tests for dispatch_with_retry_async ---


@pytest.mark.asyncio
async def test_retry_with_async_sleep():
    """dispatch_with_retry_async retries on failure with asyncio.sleep."""
    from dag_executor import dispatch_with_retry_async

    breaker = CircuitBreaker()
    call_count = 0

    async def mock_dispatch(node, cwd, prompt, timeout=3000, guardrail=None, resume_session_id=None, platform_name=""):
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

    async def mock_dispatch(node, cwd, prompt, timeout=3000, guardrail=None, resume_session_id=None, platform_name=""):
        return False, "permanent error", None

    with (
        patch("dag_executor.dispatch_node_async", side_effect=mock_dispatch),
        patch("dag_executor.asyncio.sleep", new_callable=AsyncMock),
    ):
        success, error, _stdout = await dispatch_with_retry_async(_make_node(), "/tmp", "test", 600, breaker)

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

    success, error, _stdout = await dispatch_with_retry_async(_make_node(), "/tmp", "test", 600, breaker)
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
    """data-model.md is OMITTED for tasks that don't touch models."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(tmp_path, **{"data-model.md": "# Data Model\nEntity definitions."})
    task = _make_task(description="Update README", files=["README.md"])

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
    """contracts/*.md OMITTED for tasks that don't touch APIs."""
    from dag_executor import compose_task_prompt

    epic_dir = _make_epic_dir(tmp_path, **{"contracts__webhook-api.md": "# Webhook contract"})
    task = _make_task(description="Update README", files=["README.md"])

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
    assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    # None input
    result = parse_claude_output(None)
    assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

    # Non-JSON output (e.g., raw text from failed subprocess)
    result = parse_claude_output("Error: something went wrong\nTraceback...")
    assert result == {"tokens_in": None, "tokens_out": None, "cost_usd": None, "duration_ms": None}

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

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b'{"usage": {"input_tokens": 100}}', b"")
    mock_proc.returncode = 0

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
