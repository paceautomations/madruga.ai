#!/usr/bin/env python3
"""
easter.py — Madruga AI Easter: 24/7 pipeline orchestrator.

FastAPI app with lifespan context manager composing:
  - dag_scheduler: polls active epics, dispatches pipeline
  - telegram: inline gate approvals via aiogram
  - health_checker: Telegram API connectivity + systemd watchdog
  - gate_poller: polls DB for pending unnotified gates

Endpoints:
  GET /health — liveness (always 200)
  GET /status — full easter state JSON
  GET /api/traces — list traces with pagination
  GET /api/traces/{trace_id} — trace detail with spans and evals
  GET /api/evals — eval scores with filters
  GET /api/stats — aggregated stats by day
  GET /api/export/csv — export traces/spans/evals as CSV

Usage:
    python3 .specify/scripts/easter.py
    # Or via systemd: systemctl --user start madruga-easter
"""

from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import structlog
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

sys.path.insert(0, os.path.dirname(__file__))

from dag_executor import run_pipeline_async  # noqa: E402
from ntfy import ntfy_alert  # noqa: E402
from sd_notify import sd_notify  # noqa: E402

logger = structlog.get_logger(__name__)

# --- Easter State ---

DEGRADATION_THRESHOLD = 3


@dataclass
class EasterState:
    """Mutable easter state shared across coroutines."""

    easter_state: str = "starting"  # starting, running, degraded, shutting_down
    telegram_status: str = "disconnected"  # connected, degraded, disconnected
    telegram_fail_count: int = 0
    start_time: float = field(default_factory=time.time)


# Module-level state
_easter_state = EasterState()
_shutdown_event = asyncio.Event()
_running_epics: set[str] = set()
_platform_filter: str | None = None


# --- Epic Polling ---


def poll_active_epics(conn, platform_id=None) -> list[dict]:
    """Query epics with status='in_progress'."""
    sql = "SELECT epic_id, platform_id, priority, branch_name FROM epics WHERE status='in_progress'"
    params: list = []
    if platform_id:
        sql += " AND platform_id=?"
        params.append(platform_id)
    sql += " ORDER BY priority ASC, rowid ASC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# --- Coroutines ---


async def _interruptible_sleep(shutdown_event: asyncio.Event, seconds: float) -> bool:
    """Sleep for up to `seconds`, returning immediately if shutdown_event fires.

    Returns True if shutdown was requested, False if timeout elapsed normally.
    """
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=seconds)
        return True  # shutdown requested
    except TimeoutError:
        return False  # timeout elapsed, keep running


async def dag_scheduler(conn, semaphore, shutdown_event, poll_interval=15, platform_id=None):
    """Poll active epics and dispatch pipeline runs.

    INVARIANT: self-ref platforms execute epics sequentially.
    """
    consecutive_errors = 0
    while not shutdown_event.is_set():
        try:
            # N5: skip DB poll when an epic is already running (sequential constraint)
            if _running_epics:
                await _interruptible_sleep(shutdown_event, poll_interval)
                continue

            epics = poll_active_epics(conn, platform_id=platform_id)
            consecutive_errors = 0  # reset on successful poll
            for epic in epics:
                epic_id = epic["epic_id"]
                epic_platform_id = epic["platform_id"]

                # Skip already-running epics
                if epic_id in _running_epics:
                    continue

                # Sequential constraint: only one epic at a time (global — all platforms)
                if _running_epics:
                    logger.debug("sequential_constraint", running=list(_running_epics), skipped=epic_id)
                    break

                # Check if epic has a pending gate — skip dispatch to avoid busy-loop
                from db import get_pending_gates

                pending = get_pending_gates(conn, epic_platform_id)
                epic_pending = [
                    g for g in pending if g.get("epic_id") == epic_id and g.get("gate_status") == "waiting_approval"
                ]
                if epic_pending:
                    logger.debug("gate_pending_skip", epic_id=epic_id, gate=epic_pending[0]["node_id"])
                    continue

                _running_epics.add(epic_id)
                logger.info("dispatching_epic", epic_id=epic_id, platform=epic_platform_id)

                # F3: Proactive branch checkout before dispatch
                # For external repos, worktree handles branching — skip checkout.
                branch = epic.get("branch_name")
                if branch:
                    import subprocess as _sp

                    from config import REPO_ROOT as _repo_root
                    from ensure_repo import _is_self_ref, _load_repo_binding

                    binding = _load_repo_binding(epic_platform_id)
                    if _is_self_ref(binding["name"]):
                        checkout = await asyncio.to_thread(
                            _sp.run,
                            ["git", "checkout", branch],
                            cwd=str(_repo_root),
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if checkout.returncode != 0:
                            logger.warning("branch_checkout_failed", branch=branch, stderr=checkout.stderr.strip())
                    else:
                        logger.info("external_repo_skip_checkout", branch=branch, platform=epic_platform_id)

                try:
                    result = await run_pipeline_async(
                        platform_name=epic_platform_id,
                        epic_slug=epic_id,
                        resume=True,
                        semaphore=semaphore,
                        gate_mode=os.environ.get("MADRUGA_MODE", "auto"),
                    )
                    # C2: notify via ntfy when pipeline fails (circuit breaker likely involved)
                    if result != 0:
                        topic = os.environ.get("MADRUGA_NTFY_TOPIC")
                        if topic:
                            await asyncio.to_thread(
                                ntfy_alert, topic, f"Pipeline failed for epic {epic_id} (exit={result})"
                            )
                        # Cooldown after failure to avoid rapid retry busy-loop
                        await _interruptible_sleep(shutdown_event, poll_interval * 2)
                finally:
                    _running_epics.discard(epic_id)

        except Exception:
            consecutive_errors += 1
            backoff = min(poll_interval * (2**consecutive_errors), 300)
            logger.exception("dag_scheduler_error", consecutive_errors=consecutive_errors, backoff_s=backoff)
            await _interruptible_sleep(shutdown_event, backoff)
            continue

        await _interruptible_sleep(shutdown_event, poll_interval)


async def health_checker(bot, shutdown_event, interval=60, conn=None, adapter=None, chat_id=None):
    """Check Telegram API connectivity and send systemd watchdog pings."""
    from telegram_bot import poll_pending_gates

    while not shutdown_event.is_set():
        if await _interruptible_sleep(shutdown_event, interval):
            break

        # Systemd watchdog
        sd_notify("WATCHDOG=1")

        if bot is None:
            continue

        try:
            me = await bot.get_me()
            if _easter_state.telegram_fail_count > 0:
                logger.info(
                    "telegram_recovered", username=me.username, after_failures=_easter_state.telegram_fail_count
                )
                if _easter_state.easter_state == "degraded":
                    _easter_state.easter_state = "running"
                    _easter_state.telegram_status = "connected"
                    # C4: send summary of accumulated pending gates on recovery
                    if conn and adapter and chat_id:
                        pending = poll_pending_gates(conn)
                        if pending:
                            await adapter.send(
                                chat_id,
                                f"<b>Telegram recovered</b> — {len(pending)} gate(s) pendente(s) acumulados.",
                            )
            _easter_state.telegram_fail_count = 0
            _easter_state.telegram_status = "connected"
        except Exception:
            _easter_state.telegram_fail_count += 1
            logger.warning("health_check_failed", fail_count=_easter_state.telegram_fail_count)

            if _easter_state.telegram_fail_count >= DEGRADATION_THRESHOLD and _easter_state.easter_state != "degraded":
                _easter_state.easter_state = "degraded"
                _easter_state.telegram_status = "degraded"
                logger.warning("entering_degraded_mode", fail_count=_easter_state.telegram_fail_count)

                topic = os.environ.get("MADRUGA_NTFY_TOPIC")
                if topic:
                    await asyncio.to_thread(
                        ntfy_alert,
                        topic,
                        f"Easter degraded: Telegram unreachable after {_easter_state.telegram_fail_count} failures",
                    )


GATE_REMINDER_HOURS = 24


async def gate_reminder(conn, adapter, chat_id, shutdown_event, interval=3600):
    """C1: Remind operator about gates pending for more than 24 hours."""
    while not shutdown_event.is_set():
        if await _interruptible_sleep(shutdown_event, interval):
            break
        if _easter_state.telegram_status != "connected" or adapter is None:
            continue
        try:
            rows = conn.execute(
                "SELECT run_id, node_id, platform_id, epic_id, gate_notified_at "
                "FROM pipeline_runs "
                "WHERE gate_status='waiting_approval' "
                "AND gate_notified_at IS NOT NULL "
                "AND julianday('now') - julianday(gate_notified_at) >= ?",
                (GATE_REMINDER_HOURS / 24,),
            ).fetchall()
            for row in rows:
                gate = dict(row)
                node = gate.get("node_id", "?")
                hours = GATE_REMINDER_HOURS
                await adapter.send(
                    chat_id,
                    f"<b>Lembrete</b>: gate <code>{node}</code> aguardando aprovacao ha mais de {hours}h.",
                )
                logger.info("gate_reminder_sent", node_id=node, run_id=gate["run_id"])
        except Exception:
            logger.exception("gate_reminder_error")


async def retention_cleanup(conn, shutdown_event, interval=86400):
    """Remove observability data older than 90 days. Runs once daily."""
    from db import cleanup_old_data

    while not shutdown_event.is_set():
        if await _interruptible_sleep(shutdown_event, interval):
            break
        try:
            result = await asyncio.to_thread(cleanup_old_data, conn, days=90)
            logger.info("retention_cleanup", **result)
        except Exception:
            logger.exception("retention_cleanup_error")


# --- Lifespan ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start background tasks, handle shutdown."""
    _easter_state.easter_state = "running"
    _easter_state.start_time = time.time()

    # Single-instance lock — prevent multiple easters from running concurrently
    from config import REPO_ROOT as _lock_repo_root

    lock_path = _lock_repo_root / ".pipeline" / "madruga.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    def _acquire_lock(fh):
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fh.write(str(os.getpid()))
        fh.flush()

    lock_file = open(lock_path, "w")  # noqa: SIM115
    try:
        _acquire_lock(lock_file)
        logger.info("instance_lock_acquired", lock=str(lock_path), pid=os.getpid())
    except OSError:
        # Check if the PID holding the lock is still alive
        lock_file.close()
        stale = False
        old_pid = None
        try:
            with open(lock_path) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)  # signal 0 = check if alive
        except (ValueError, ProcessLookupError, PermissionError):
            stale = True
        if stale:
            logger.warning("stale_lock_reclaimed", lock=str(lock_path), old_pid=old_pid)
            lock_path.unlink(missing_ok=True)
            lock_file = open(lock_path, "w")  # noqa: SIM115
            _acquire_lock(lock_file)
        else:
            logger.error("another_easter_running", lock=str(lock_path), pid=old_pid)
            sys.exit(1)

    # Sentry (optional)
    dsn = os.environ.get("MADRUGA_SENTRY_DSN")
    if dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_sdk.init(dsn=dsn, integrations=[FastApiIntegration()], traces_sample_rate=0.5)
            logger.info("sentry_initialized")
        except ImportError:
            logger.warning("sentry_sdk_not_installed")

    # Telegram setup (optional)
    bot = None
    dp = None
    adapter = None
    telegram_token = os.environ.get("MADRUGA_TELEGRAM_BOT_TOKEN")
    chat_id_str = os.environ.get("MADRUGA_TELEGRAM_CHAT_ID")

    if telegram_token and chat_id_str:
        try:
            from aiogram import Bot, Dispatcher
            from aiogram.client.default import DefaultBotProperties
            from aiogram.enums import ParseMode

            from telegram_adapter import TelegramAdapter
            from telegram_bot import gate_poller as tg_gate_poller
            from telegram_bot import (
                handle_decision_callback,
                handle_freetext,
                handle_gate_callback,
                handle_gates,
                handle_help,
                handle_status,
                load_offset,
                save_offset,
            )

            bot = Bot(token=telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher()
            adapter = TelegramAdapter(bot)
            chat_id = int(chat_id_str)
            _easter_state.telegram_status = "connected"
            logger.info("telegram_configured", chat_id=chat_id)
        except Exception:
            logger.exception("telegram_init_failed")
            _easter_state.telegram_status = "disconnected"
            bot = None
    else:
        logger.warning("telegram_not_configured", reason="missing env vars")

    # DB connection
    from db import get_conn, migrate

    conn = get_conn()
    migrate(conn)
    app.state.db_conn = conn

    semaphore = asyncio.Semaphore(int(os.environ.get("MADRUGA_MAX_CONCURRENT", "3")))

    # Signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: _shutdown_event.set())

    sd_notify("READY=1")
    logger.info("easter_started", pid=os.getpid())

    try:
        async with asyncio.TaskGroup() as tg:
            # Core: DAG scheduler
            tg.create_task(dag_scheduler(conn, semaphore, _shutdown_event, platform_id=_platform_filter))

            # Health checker (with or without Telegram)
            tg.create_task(
                health_checker(
                    bot,
                    _shutdown_event,
                    conn=conn,
                    adapter=adapter,
                    chat_id=int(chat_id_str) if chat_id_str else None,
                )
            )

            # Retention cleanup (daily)
            tg.create_task(retention_cleanup(conn, _shutdown_event))

            # Telegram tasks (if configured)
            if bot and dp and adapter:
                from aiogram import F
                from aiogram.types import CallbackQuery

                offset = load_offset(conn)

                @dp.update.outer_middleware()
                async def _persist_offset(handler, event, data):
                    result = await handler(event, data)
                    if event.update_id:
                        save_offset(conn, event.update_id)
                    return result

                @dp.callback_query(F.data.startswith("gate:"))
                async def _handle_gate(callback: CallbackQuery):
                    await handle_gate_callback(callback, adapter, conn)

                @dp.callback_query(F.data.startswith("decision:"))
                async def _handle_decision(callback: CallbackQuery):
                    await handle_decision_callback(callback, adapter, conn)

                # Command handlers (must be registered before catch-all)
                from aiogram.filters import Command
                from aiogram.types import Message

                @dp.message(Command("start", "help"))
                async def _handle_help(message: Message):
                    if message.chat.id != chat_id:
                        return
                    await handle_help(message, adapter, chat_id)

                @dp.message(Command("status"))
                async def _handle_status(message: Message):
                    if message.chat.id != chat_id:
                        return
                    await handle_status(message, adapter, chat_id, conn)

                @dp.message(Command("gates"))
                async def _handle_gates(message: Message):
                    if message.chat.id != chat_id:
                        return
                    await handle_gates(message, adapter, chat_id, conn)

                # Catch-all: free text → claude -p (MUST be last)
                @dp.message()
                async def _handle_freetext(message: Message):
                    if message.chat.id != chat_id:
                        return
                    await handle_freetext(message, adapter, chat_id, conn)

                tg.create_task(dp.start_polling(bot, offset=offset))
                tg.create_task(tg_gate_poller(adapter, chat_id, conn))
                tg.create_task(gate_reminder(conn, adapter, chat_id, _shutdown_event))

            yield  # FastAPI serves requests here

            # Shutdown
            _easter_state.easter_state = "shutting_down"
            _shutdown_event.set()
            sd_notify("STOPPING=1")
    except* Exception as eg:
        for exc in eg.exceptions:
            logger.exception("taskgroup_error", error=str(exc))
    finally:
        conn.close()
        lock_file.close()
        lock_path.unlink(missing_ok=True)
        logger.info("easter_stopped", uptime_s=int(time.time() - _easter_state.start_time))


# --- FastAPI App ---

app = FastAPI(lifespan=lifespan, title="Madruga AI Easter", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    db_ok = True
    try:
        from db import get_conn

        with get_conn() as conn:
            conn.execute("SELECT 1")
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {"status": status, "easter_state": _easter_state.easter_state, "db": db_ok}


@app.get("/status")
async def status():
    return {
        "easter_state": _easter_state.easter_state,
        "telegram_status": _easter_state.telegram_status,
        "running_epics": list(_running_epics),
        "uptime_seconds": int(time.time() - _easter_state.start_time),
        "pid": os.getpid(),
    }


# --- Session Monitoring ---


@app.get("/api/sessions")
async def sessions(request: Request, platform_id: str | None = Query(default=None)):
    """Active and queued sessions with per-session detail."""
    conn = request.app.state.db_conn

    result = {
        "easter_state": _easter_state.easter_state,
        "telegram_status": _easter_state.telegram_status,
        "uptime_seconds": int(time.time() - _easter_state.start_time),
        "pid": os.getpid(),
        "poll_interval_seconds": 15,
        "running_epics": [],
        "queued_epics": [],
    }

    all_active = poll_active_epics(conn, platform_id=platform_id)
    running_ids = set(_running_epics)

    for epic in all_active:
        eid = epic["epic_id"]
        pid = epic["platform_id"]
        if eid in running_ids:
            session: dict = {"epic_id": eid, "platform_id": pid}
            trace_row = conn.execute(
                "SELECT trace_id, started_at, total_nodes FROM traces "
                "WHERE epic_id=? AND status='running' ORDER BY started_at DESC LIMIT 1",
                (eid,),
            ).fetchone()
            if trace_row:
                tid = trace_row["trace_id"]
                running_node = conn.execute(
                    "SELECT node_id, started_at FROM pipeline_runs "
                    "WHERE trace_id=? AND status='running' ORDER BY started_at DESC LIMIT 1",
                    (tid,),
                ).fetchone()
                agg = conn.execute(
                    "SELECT SUM(cost_usd) AS cost, SUM(tokens_in) AS tin, SUM(tokens_out) AS tout, "
                    "COUNT(CASE WHEN status='completed' THEN 1 END) AS completed, "
                    "MAX(COALESCE(completed_at, started_at)) AS last_activity "
                    "FROM pipeline_runs WHERE trace_id=?",
                    (tid,),
                ).fetchone()
                nodes = conn.execute(
                    "SELECT node_id, status FROM pipeline_runs WHERE trace_id=? ORDER BY started_at",
                    (tid,),
                ).fetchall()
                session.update(
                    {
                        "trace_id": tid,
                        "started_at": trace_row["started_at"],
                        "current_node": running_node["node_id"] if running_node else None,
                        "current_node_started_at": running_node["started_at"] if running_node else None,
                        "session_cost_usd": agg["cost"] or 0,
                        "tokens_in": agg["tin"] or 0,
                        "tokens_out": agg["tout"] or 0,
                        "completed_nodes": agg["completed"] or 0,
                        "total_nodes": trace_row["total_nodes"] or 12,
                        "last_activity": agg["last_activity"],
                        "node_statuses": [{"node_id": n["node_id"], "status": n["status"]} for n in nodes],
                    }
                )
            else:
                session.update(
                    {
                        "trace_id": None,
                        "started_at": None,
                        "current_node": None,
                        "current_node_started_at": None,
                        "session_cost_usd": 0,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "completed_nodes": 0,
                        "total_nodes": 12,
                        "last_activity": None,
                        "node_statuses": [],
                    }
                )
            result["running_epics"].append(session)
        else:
            result["queued_epics"].append({"epic_id": eid, "platform_id": pid})

    return result


# --- Observability Endpoints ---


@app.get("/api/traces")
async def list_traces(
    request: Request,
    platform_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
):
    if not platform_id:
        return JSONResponse(status_code=400, content={"error": "platform_id is required"})

    from db import get_traces

    traces, total = get_traces(request.app.state.db_conn, platform_id, limit, offset, status)
    return {"traces": traces, "total": total, "limit": limit, "offset": offset}


@app.get("/api/traces/{trace_id}")
async def trace_detail(request: Request, trace_id: str):
    from db import get_trace_detail

    result = get_trace_detail(request.app.state.db_conn, trace_id)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "trace not found"})
    return result


@app.get("/api/runs")
async def list_runs(
    request: Request,
    platform_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    epic_id: str | None = Query(default=None),
):
    from db import get_runs_with_evals

    runs, total = get_runs_with_evals(
        request.app.state.db_conn,
        platform_id,
        limit,
        offset,
        status,
        epic_id,
    )
    return {"runs": runs, "total": total, "limit": limit, "offset": offset}


@app.get("/api/evals")
async def list_evals(
    request: Request,
    platform_id: str | None = Query(default=None),
    node_id: str | None = Query(default=None),
    dimension: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    if not platform_id:
        return JSONResponse(status_code=400, content={"error": "platform_id is required"})

    from db import get_eval_scores

    scores, total = get_eval_scores(request.app.state.db_conn, platform_id, node_id, dimension, limit)
    return {"scores": scores, "total": total}


@app.get("/api/stats")
async def stats(
    request: Request,
    platform_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=90),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
):
    from db import get_stats

    result = get_stats(
        request.app.state.db_conn,
        platform_id,
        days,
        start_date=start_date,
        end_date=end_date,
    )
    return {
        "stats": result["stats"],
        "period_days": days,
        "summary": result["summary"],
        "top_nodes": result["top_nodes"],
        "stats_by_status": result["stats_by_status"],
        "avg_scores_by_day": result["avg_scores_by_day"],
        "avg_duration_by_node": result["avg_duration_by_node"],
        "score_distribution": result["score_distribution"],
    }


@app.get("/api/export/csv")
async def export_csv_endpoint(
    request: Request,
    platform_id: str | None = Query(default=None),
    entity: str | None = Query(default=None),
    days: int = Query(default=90, ge=1, le=365),
):
    if not platform_id:
        return JSONResponse(status_code=400, content={"error": "platform_id is required"})
    if not entity:
        return JSONResponse(status_code=400, content={"error": "entity is required"})

    from observability_export import VALID_ENTITIES, export_csv

    if entity not in VALID_ENTITIES:
        return JSONResponse(status_code=400, content={"error": f"entity must be one of: {', '.join(VALID_ENTITIES)}"})

    from datetime import date

    csv_str = export_csv(request.app.state.db_conn, platform_id, entity, days)
    filename = f"{entity}_{platform_id}_{date.today().isoformat()}.csv"
    return Response(
        content=csv_str,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- CLI Entry Point ---


def _configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if verbose else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def main():
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Madruga AI Easter")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8040, help="Bind port (default: 8040)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--platform", default=None, help="Only process epics for this platform")
    args = parser.parse_args()

    global _platform_filter
    _platform_filter = args.platform

    _configure_logging(args.verbose)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
