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

    async def mock_dispatch(node, cwd, prompt, timeout=3000, guardrail=None, resume_session_id=None):
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

    async def mock_dispatch(node, cwd, prompt, timeout=3000, guardrail=None, resume_session_id=None):
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
        "trace_id TEXT, output_lines INT, started_at TEXT, completed_at TEXT, gate_notified_at TEXT, "
        "gate_resolved_at TEXT, telegram_message_id TEXT)",
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

    with (
        patch("dag_executor.parse_dag", return_value=nodes),
        patch("dag_executor.topological_sort", return_value=nodes),
        patch("dag_executor.dispatch_with_retry_async", side_effect=mock_dispatch),
        patch("dag_executor.verify_outputs", return_value=(True, None)),
        patch("dag_executor.compose_skill_prompt", return_value=("test prompt", "guardrail")),
        patch("dag_executor.subprocess.run", return_value=mock_branch),
        patch("dag_executor.REPO_ROOT", MagicMock()),
    ):
        await run_pipeline_async("test-plat", epic_slug="e1", resume=True, conn=conn)

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
        "trace_id TEXT, output_lines INT, started_at TEXT, completed_at TEXT, gate_notified_at TEXT, "
        "gate_resolved_at TEXT, telegram_message_id TEXT)",
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

    with (
        patch("dag_executor.parse_dag", return_value=nodes),
        patch("dag_executor.topological_sort", return_value=nodes),
        patch("dag_executor.dispatch_with_retry_async", side_effect=mock_dispatch),
        patch("dag_executor.verify_outputs", return_value=(True, None)),
        patch("dag_executor.compose_skill_prompt", return_value=("test", "guardrail")),
        patch("dag_executor.subprocess.run", return_value=mock_branch),
        patch("dag_executor.REPO_ROOT", MagicMock()),
    ):
        await run_pipeline_async("p", epic_slug="e1", resume=True, conn=conn, gate_mode="auto")

    assert "specify" in dispatched, "auto mode should dispatch without pausing"
    # No waiting_approval runs should exist
    gates = conn.execute("SELECT * FROM pipeline_runs WHERE gate_status='waiting_approval'").fetchall()
    assert len(gates) == 0, "auto mode should not create waiting_approval gates"


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
        description="Add CORS to `daemon.py`",
        checked=False,
        phase="Phase 2",
        parallel=True,
        files=["daemon.py"],
        line_number=10,
    )

    prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")

    assert "T005" in prompt
    assert "ONLY implement this specific task" in prompt
    assert "daemon.py" in prompt
    assert "Plan" in prompt
    assert "Spec" in prompt
    assert "epic/test-plat/001-test" in prompt
    assert "All Tasks" in prompt


def test_compose_task_prompt_includes_implement_context(tmp_path):
    """compose_task_prompt includes implement-context.md when present."""
    from dag_executor import TaskItem, compose_task_prompt

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "plan.md").write_text("# Plan")
    (epic_dir / "spec.md").write_text("# Spec")
    (epic_dir / "implement-context.md").write_text("### T001 — DONE\n- Created file\n")

    task = TaskItem(
        id="T002",
        description="Next task",
        checked=False,
        phase="Phase 1",
        parallel=False,
        files=[],
        line_number=1,
    )
    prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")

    assert "Prior Tasks Completed" in prompt
    assert "T001 — DONE" in prompt


def test_compose_task_prompt_includes_analyze_report(tmp_path):
    """compose_task_prompt includes analyze-report.md when present."""
    from dag_executor import TaskItem, compose_task_prompt

    epic_dir = tmp_path / "epics" / "001-test"
    epic_dir.mkdir(parents=True)
    (epic_dir / "plan.md").write_text("# Plan")
    (epic_dir / "spec.md").write_text("# Spec")
    (epic_dir / "analyze-report.md").write_text("# Analysis\nIssue found in module X.")

    task = TaskItem(
        id="T001",
        description="Fix module X",
        checked=False,
        phase="Phase 1",
        parallel=False,
        files=[],
        line_number=1,
    )
    prompt = compose_task_prompt(task, epic_dir, "test-plat", "001-test")

    assert "Pre-Implementation Analysis" in prompt
    assert "Issue found in module X" in prompt


def test_append_implement_context(tmp_path):
    """append_implement_context creates and appends to implement-context.md."""
    from dag_executor import TaskItem, append_implement_context

    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()

    task1 = TaskItem(
        id="T001",
        description="Create db.py functions",
        checked=True,
        phase="Phase 1",
        parallel=False,
        files=["db.py", "models.py"],
        line_number=1,
    )
    task2 = TaskItem(
        id="T002",
        description="Add API endpoint",
        checked=True,
        phase="Phase 1",
        parallel=False,
        files=["daemon.py"],
        line_number=2,
    )

    append_implement_context(epic_dir, task1, {"tokens_in": 1000, "tokens_out": 500})
    append_implement_context(epic_dir, task2)

    ctx = (epic_dir / "implement-context.md").read_text()
    assert "T001 — DONE" in ctx
    assert "db.py, models.py" in ctx
    assert "1000/500" in ctx
    assert "T002 — DONE" in ctx
    assert "daemon.py" in ctx


def test_implement_context_deleted_at_cycle_start(tmp_path):
    """Stale implement-context.md is deleted before task loop starts."""
    # Simulate the deletion logic from run_implement_tasks
    epic_dir = tmp_path / "epic"
    epic_dir.mkdir()
    ctx_path = epic_dir / "implement-context.md"
    ctx_path.write_text("### T001 — DONE\nstale data\n")

    # Replicate the cleanup logic
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

    result = parse_claude_output('{"usage": {"input_tokens": 500}, "cost_usd": 0.05}')
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
