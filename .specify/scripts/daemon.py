#!/usr/bin/env python3
"""
daemon.py — Madruga AI Daemon: 24/7 pipeline orchestrator.

FastAPI app with lifespan context manager composing:
  - dag_scheduler: polls active epics, dispatches pipeline
  - telegram: inline gate approvals via aiogram
  - health_checker: Telegram API connectivity + systemd watchdog
  - gate_poller: polls DB for pending unnotified gates

Endpoints:
  GET /health — liveness (always 200)
  GET /status — full daemon state JSON

Usage:
    python3 .specify/scripts/daemon.py
    # Or via systemd: systemctl --user start madruga-daemon
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import structlog
from fastapi import FastAPI

sys.path.insert(0, os.path.dirname(__file__))

from dag_executor import run_pipeline_async  # noqa: E402
from ntfy import ntfy_alert  # noqa: E402
from sd_notify import sd_notify  # noqa: E402

logger = structlog.get_logger(__name__)

# --- Daemon State ---

DEGRADATION_THRESHOLD = 3


@dataclass
class DaemonState:
    """Mutable daemon state shared across coroutines."""

    daemon_state: str = "starting"  # starting, running, degraded, shutting_down
    telegram_status: str = "disconnected"  # connected, degraded, disconnected
    telegram_fail_count: int = 0
    start_time: float = field(default_factory=time.time)


# Module-level state
_daemon_state = DaemonState()
_shutdown_event = asyncio.Event()
_running_epics: set[str] = set()


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


async def dag_scheduler(conn, semaphore, shutdown_event, poll_interval=15):
    """Poll active epics and dispatch pipeline runs.

    INVARIANT: self-ref platforms execute epics sequentially.
    """
    consecutive_errors = 0
    while not shutdown_event.is_set():
        try:
            # N5: skip DB poll when an epic is already running (sequential constraint)
            if _running_epics:
                await asyncio.sleep(poll_interval)
                continue

            epics = poll_active_epics(conn)
            consecutive_errors = 0  # reset on successful poll
            for epic in epics:
                epic_id = epic["epic_id"]
                platform_id = epic["platform_id"]

                # Skip already-running epics
                if epic_id in _running_epics:
                    continue

                # Sequential constraint: only one epic at a time for self-ref
                if _running_epics:
                    logger.debug("sequential_constraint", running=list(_running_epics), skipped=epic_id)
                    break

                _running_epics.add(epic_id)
                logger.info("dispatching_epic", epic_id=epic_id, platform=platform_id)

                try:
                    result = await run_pipeline_async(
                        platform_name=platform_id,
                        epic_slug=epic_id,
                        resume=True,
                        semaphore=semaphore,
                    )
                    # C2: notify via ntfy when pipeline fails (circuit breaker likely involved)
                    if result != 0:
                        topic = os.environ.get("MADRUGA_NTFY_TOPIC")
                        if topic:
                            await asyncio.to_thread(
                                ntfy_alert, topic, f"Pipeline failed for epic {epic_id} (exit={result})"
                            )
                finally:
                    _running_epics.discard(epic_id)

        except Exception:
            consecutive_errors += 1
            backoff = min(poll_interval * (2**consecutive_errors), 300)
            logger.exception("dag_scheduler_error", consecutive_errors=consecutive_errors, backoff_s=backoff)
            await asyncio.sleep(backoff)
            continue

        await asyncio.sleep(poll_interval)


async def health_checker(bot, shutdown_event, interval=60, conn=None, adapter=None, chat_id=None):
    """Check Telegram API connectivity and send systemd watchdog pings."""
    from telegram_bot import poll_pending_gates

    while not shutdown_event.is_set():
        await asyncio.sleep(interval)

        # Systemd watchdog
        sd_notify("WATCHDOG=1")

        if bot is None:
            continue

        try:
            me = await bot.get_me()
            if _daemon_state.telegram_fail_count > 0:
                logger.info(
                    "telegram_recovered", username=me.username, after_failures=_daemon_state.telegram_fail_count
                )
                if _daemon_state.daemon_state == "degraded":
                    _daemon_state.daemon_state = "running"
                    _daemon_state.telegram_status = "connected"
                    # C4: send summary of accumulated pending gates on recovery
                    if conn and adapter and chat_id:
                        pending = poll_pending_gates(conn)
                        if pending:
                            await adapter.send(
                                chat_id,
                                f"<b>Telegram recovered</b> — {len(pending)} gate(s) pendente(s) acumulados.",
                            )
            _daemon_state.telegram_fail_count = 0
            _daemon_state.telegram_status = "connected"
        except Exception:
            _daemon_state.telegram_fail_count += 1
            logger.warning("health_check_failed", fail_count=_daemon_state.telegram_fail_count)

            if _daemon_state.telegram_fail_count >= DEGRADATION_THRESHOLD and _daemon_state.daemon_state != "degraded":
                _daemon_state.daemon_state = "degraded"
                _daemon_state.telegram_status = "degraded"
                logger.warning("entering_degraded_mode", fail_count=_daemon_state.telegram_fail_count)

                topic = os.environ.get("MADRUGA_NTFY_TOPIC")
                if topic:
                    await asyncio.to_thread(
                        ntfy_alert,
                        topic,
                        f"Daemon degraded: Telegram unreachable after {_daemon_state.telegram_fail_count} failures",
                    )


GATE_REMINDER_HOURS = 24


async def gate_reminder(conn, adapter, chat_id, shutdown_event, interval=3600):
    """C1: Remind operator about gates pending for more than 24 hours."""
    while not shutdown_event.is_set():
        await asyncio.sleep(interval)
        if _daemon_state.telegram_status != "connected" or adapter is None:
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


# --- Lifespan ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start background tasks, handle shutdown."""
    _daemon_state.daemon_state = "running"
    _daemon_state.start_time = time.time()

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
            from telegram_bot import handle_decision_callback, handle_gate_callback, load_offset, save_offset

            bot = Bot(token=telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            dp = Dispatcher()
            adapter = TelegramAdapter(bot)
            chat_id = int(chat_id_str)
            _daemon_state.telegram_status = "connected"
            logger.info("telegram_configured", chat_id=chat_id)
        except Exception:
            logger.exception("telegram_init_failed")
            _daemon_state.telegram_status = "disconnected"
            bot = None
    else:
        logger.warning("telegram_not_configured", reason="missing env vars")

    # DB connection
    from db import get_conn, migrate

    conn = get_conn()
    migrate(conn)

    semaphore = asyncio.Semaphore(int(os.environ.get("MADRUGA_MAX_CONCURRENT", "3")))

    # Signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: _shutdown_event.set())

    sd_notify("READY=1")
    logger.info("daemon_started", pid=os.getpid())

    try:
        async with asyncio.TaskGroup() as tg:
            # Core: DAG scheduler
            tg.create_task(dag_scheduler(conn, semaphore, _shutdown_event))

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

                tg.create_task(dp.start_polling(bot, offset=offset))
                tg.create_task(tg_gate_poller(adapter, chat_id, conn))
                tg.create_task(gate_reminder(conn, adapter, chat_id, _shutdown_event))

            yield  # FastAPI serves requests here

            # Shutdown
            _daemon_state.daemon_state = "shutting_down"
            _shutdown_event.set()
            sd_notify("STOPPING=1")
    except* Exception as eg:
        for exc in eg.exceptions:
            logger.exception("taskgroup_error", error=str(exc))
    finally:
        conn.close()
        logger.info("daemon_stopped", uptime_s=int(time.time() - _daemon_state.start_time))


# --- FastAPI App ---

app = FastAPI(lifespan=lifespan, title="Madruga AI Daemon", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    return {"status": "ok", "daemon_state": _daemon_state.daemon_state}


@app.get("/status")
async def status():
    return {
        "daemon_state": _daemon_state.daemon_state,
        "telegram_status": _daemon_state.telegram_status,
        "running_epics": list(_running_epics),
        "uptime_seconds": int(time.time() - _daemon_state.start_time),
        "pid": os.getpid(),
    }


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

    parser = argparse.ArgumentParser(description="Madruga AI Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8040, help="Bind port (default: 8040)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    args = parser.parse_args()

    _configure_logging(args.verbose)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
