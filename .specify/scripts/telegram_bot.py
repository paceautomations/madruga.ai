"""
telegram_bot.py — Standalone Telegram bot for pipeline gate notifications.

Dual-loop asyncio architecture:
  1. aiogram Dispatcher.start_polling() — receives Telegram callbacks
  2. asyncio task — polls DB for pending unnotified gates

Desacoplado: dag_executor writes gates to pipeline_runs,
this bot polls the table and sends notifications via TelegramAdapter.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sqlite3
import sys
from datetime import datetime, timezone

import structlog
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery

sys.path.insert(0, os.path.dirname(__file__))


from db import approve_gate, reject_gate  # noqa: E402
from telegram_adapter import TelegramAdapter  # noqa: E402

logger = structlog.get_logger(__name__)

# --- Backoff constants ---
BACKOFF_INITIAL = 2.0
BACKOFF_FACTOR = 1.8
BACKOFF_MAX = 30.0
BACKOFF_JITTER = 0.25


def calculate_backoff(attempt: int) -> float:
    """Exponential backoff: initial * factor^attempt, capped at max, with jitter."""
    delay = BACKOFF_INITIAL * (BACKOFF_FACTOR**attempt)
    delay = min(delay, BACKOFF_MAX)
    jitter = delay * BACKOFF_JITTER * (2 * random.random() - 1)
    return max(0.1, min(delay + jitter, BACKOFF_MAX))


# --- Offset persistence ---


def save_offset(conn: sqlite3.Connection, update_id: int) -> None:
    """Persist last processed Telegram update_id in local_config."""
    conn.execute(
        "INSERT OR REPLACE INTO local_config (key, value, updated_at) "
        "VALUES ('telegram_last_update_id', ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
        (str(update_id),),
    )
    conn.commit()


def load_offset(conn: sqlite3.Connection) -> int | None:
    """Load last processed Telegram update_id from local_config."""
    row = conn.execute("SELECT value FROM local_config WHERE key='telegram_last_update_id'").fetchone()
    return int(row[0]) if row else None


# --- Gate polling ---


def poll_pending_gates(conn: sqlite3.Connection, platform_id: str | None = None) -> list[dict]:
    """Query pipeline_runs for gates that are waiting_approval and not yet notified."""
    sql = (
        "SELECT run_id, platform_id, epic_id, node_id, gate_status, "
        "gate_notified_at, started_at FROM pipeline_runs "
        "WHERE gate_status='waiting_approval' AND gate_notified_at IS NULL"
    )
    params: list = []
    if platform_id:
        sql += " AND platform_id=?"
        params.append(platform_id)
    sql += " ORDER BY started_at"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# --- Message formatting ---


def format_gate_message(gate: dict) -> str:
    """Format HTML message for a pending gate notification."""
    node = gate.get("node_id", "?")
    platform = gate.get("platform_id", "?")
    epic = gate.get("epic_id")
    started = gate.get("started_at", "?")
    lines = [
        "<b>Pipeline Gate \u2014 Aguardando Aprovacao</b>",
        "",
        f"<b>Node:</b> <code>{node}</code>",
        f"<b>Plataforma:</b> {platform}",
    ]
    if epic:
        lines.append(f"<b>Epic:</b> {epic}")
    lines.append(f"<b>Criado:</b> {started}")
    return "\n".join(lines)


def format_resolved_message(gate: dict, action: str) -> str:
    """Format HTML message after gate is approved/rejected."""
    node = gate.get("node_id", "?")
    platform = gate.get("platform_id", "?")
    decision = "Aprovado" if action == "a" else "Rejeitado"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"<b>Pipeline Gate \u2014 {decision}</b>",
        "",
        f"<b>Node:</b> <code>{node}</code>",
        f"<b>Plataforma:</b> {platform}",
        f"<b>Resolvido:</b> {now}",
        f"<b>Decisao:</b> {decision} via Telegram",
    ]
    return "\n".join(lines)


def format_decision_message(decision: dict) -> str:
    """Format HTML message for a 1-way-door decision notification.

    Args:
        decision: dict with keys: description, context, alternatives (list of str),
                  risk_score (dict with risk, reversibility, score),
                  skill (str), platform (str), epic (str, optional).
    """
    risk = decision.get("risk_score", {})
    lines = [
        "<b>Pipeline \u2014 Decisao 1-Way-Door</b>",
        "",
        f"<b>Skill:</b> <code>{decision.get('skill', '?')}</code>",
        f"<b>Plataforma:</b> {decision.get('platform', '?')}",
    ]
    epic = decision.get("epic")
    if epic:
        lines.append(f"<b>Epic:</b> {epic}")
    lines.extend(
        [
            "",
            f"<b>Decisao:</b> {decision.get('description', '?')}",
            f"<b>Score de Risco:</b> {risk.get('score', '?')} "
            f"(Risco={risk.get('risk', '?')} \u00d7 Reversibilidade={risk.get('reversibility', '?')})",
            f"<b>Contexto:</b> {decision.get('context', 'N/A')}",
        ]
    )
    alternatives = decision.get("alternatives", [])
    if alternatives:
        lines.append("")
        lines.append("<b>Alternativas:</b>")
        for i, alt in enumerate(alternatives, 1):
            lines.append(f"{i}. {alt}")
    return "\n".join(lines)


def format_decision_resolved_message(decision: dict, action: str) -> str:
    """Format HTML message after a decision is approved/rejected."""
    verdict = "Aprovada" if action == "a" else "Rejeitada"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"<b>Pipeline \u2014 Decisao {verdict}</b>",
        "",
        f"<b>Decisao:</b> {decision.get('description', '?')}",
        f"<b>Resolvido:</b> {now}",
        f"<b>Veredicto:</b> {verdict} via Telegram",
    ]
    return "\n".join(lines)


# --- Gate notification ---


async def notify_gate(
    adapter: TelegramAdapter,
    chat_id: int,
    gate: dict,
    conn: sqlite3.Connection,
) -> None:
    """Send gate notification via Telegram and record in DB."""
    text = format_gate_message(gate)
    run_id = gate["run_id"]
    choices = [
        ("\u2705 Aprovar", f"gate:{run_id}:a"),
        ("\u274c Rejeitar", f"gate:{run_id}:r"),
    ]
    message_id = await adapter.ask_choice(chat_id, text, choices)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "UPDATE pipeline_runs SET telegram_message_id=?, gate_notified_at=? WHERE run_id=?",
        (message_id, now, run_id),
    )
    conn.commit()
    logger.info("gate_notified", run_id=run_id, message_id=message_id)


# --- Decision notification (1-way-door) ---


async def notify_oneway_decision(
    adapter: TelegramAdapter,
    chat_id: int,
    decision: dict,
    conn: sqlite3.Connection,
) -> None:
    """Send 1-way-door decision notification via Telegram and record in DB.

    Args:
        decision: dict with keys: id, description, context, alternatives,
                  risk_score (dict), skill, platform, epic (optional).
    """
    text = format_decision_message(decision)
    decision_id = decision["id"]
    choices = [
        ("\u2705 Aprovar", f"decision:{decision_id}:a"),
        ("\u274c Rejeitar", f"decision:{decision_id}:r"),
    ]
    message_id = await adapter.ask_choice(chat_id, text, choices)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO events (platform_id, entity_type, entity_id, action, payload, created_at) "
        "VALUES (?, 'decision', ?, 'decision_notified', ?, ?)",
        (
            decision.get("platform", "unknown"),
            decision_id,
            json.dumps({"message_id": message_id}),
            now,
        ),
    )
    conn.commit()
    logger.info("decision_notified", decision_id=decision_id, message_id=message_id)


# --- Callback handling ---


def parse_decision_callback_data(data: str) -> tuple[str, str] | None:
    """Parse 'decision:{id}:{action}'. Returns (decision_id, action) or None."""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "decision" or parts[2] not in ("a", "r"):
        return None
    return parts[1], parts[2]


async def handle_decision_callback(
    callback: CallbackQuery,
    adapter: TelegramAdapter,
    conn: sqlite3.Connection,
) -> None:
    """Process approve/reject callback for a 1-way-door decision."""
    parsed = parse_decision_callback_data(callback.data)
    if not parsed:
        await callback.answer("Dados invalidos")
        return

    decision_id, action = parsed
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id

    verdict = "approved" if action == "a" else "rejected"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Lookup platform_id from the original decision_notified event
    row = conn.execute(
        "SELECT platform_id FROM events WHERE entity_type='decision' AND entity_id=? AND action='decision_notified'",
        (decision_id,),
    ).fetchone()
    platform_id = row[0] if row else "unknown"

    # Record decision result in events
    conn.execute(
        "INSERT INTO events (platform_id, entity_type, entity_id, action, payload, created_at) "
        "VALUES (?, 'decision', ?, 'decision_resolved', ?, ?)",
        (
            platform_id,
            decision_id,
            json.dumps({"verdict": verdict}),
            now,
        ),
    )
    conn.commit()

    # Edit message to remove buttons
    decision_info = {"description": decision_id}
    resolved_text = format_decision_resolved_message(decision_info, action)
    await adapter.edit_message(chat_id, message_id, resolved_text, reply_markup=None)

    label = "Aprovada" if action == "a" else "Rejeitada"
    await callback.answer(f"Decisao {label}")
    logger.info("decision_resolved", decision_id=decision_id, verdict=verdict)


def parse_callback_data(data: str) -> tuple[str, str] | None:
    """Parse 'gate:{run_id}:{action}'. Returns (run_id, action) or None."""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "gate" or parts[2] not in ("a", "r"):
        return None
    return parts[1], parts[2]


async def handle_gate_callback(
    callback: CallbackQuery,
    adapter: TelegramAdapter,
    conn: sqlite3.Connection,
) -> None:
    """Process approve/reject callback from Telegram inline keyboard."""
    parsed = parse_callback_data(callback.data)
    if not parsed:
        await callback.answer("Dados invalidos")
        return

    run_id, action = parsed
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id

    # Fetch gate info for message formatting
    row = conn.execute("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
    if not row:
        await callback.answer("Gate nao encontrado")
        return

    gate = dict(row)

    # Check if already resolved
    if gate["gate_status"] != "waiting_approval":
        await callback.answer("Gate ja resolvido")
        return

    # Update DB via db.py functions (single source of truth)
    if action == "a":
        updated = approve_gate(conn, run_id)
    else:
        updated = reject_gate(conn, run_id)
    if not updated:
        await callback.answer("Gate ja resolvido")
        return

    # Edit message to remove buttons and show result
    resolved_text = format_resolved_message(gate, action)
    await adapter.edit_message(chat_id, message_id, resolved_text, reply_markup=None)

    decision = "Aprovado" if action == "a" else "Rejeitado"
    await callback.answer(f"Gate {decision}")
    logger.info("gate_resolved", run_id=run_id, decision=decision.lower())


# --- Polling loop ---


async def gate_poller(
    adapter: TelegramAdapter,
    chat_id: int,
    conn: sqlite3.Connection,
    interval: float = 15.0,
    platform_id: str | None = None,
    dry_run: bool = False,
) -> None:
    """Asyncio task: poll DB for pending gates and send notifications."""
    attempt = 0
    while True:
        try:
            gates = poll_pending_gates(conn, platform_id=platform_id)
            if gates:
                logger.info("pending_gates_found", count=len(gates))
                for gate in gates:
                    if dry_run:
                        logger.info("dry_run_skip", run_id=gate["run_id"])
                    else:
                        await notify_gate(adapter, chat_id, gate, conn)
            attempt = 0  # reset on success
        except Exception:
            attempt += 1
            delay = calculate_backoff(attempt)
            logger.exception("gate_poller_error", attempt=attempt, retry_in_s=round(delay, 1))
            await asyncio.sleep(delay)
            continue
        await asyncio.sleep(interval)


# --- Health check ---


async def health_check(bot: Bot, interval: float = 60.0) -> None:
    """Periodically verify Telegram API connectivity."""
    attempt = 0
    while True:
        await asyncio.sleep(interval)
        try:
            me = await bot.get_me()
            if attempt > 0:
                logger.info(
                    "health_check_recovered",
                    username=me.username,
                    after_attempts=attempt,
                )
            else:
                logger.debug("health_check_ok", username=me.username)
            attempt = 0
        except Exception:
            attempt += 1
            delay = calculate_backoff(attempt)
            logger.warning("health_check_failed", attempt=attempt, next_retry_s=round(delay, 1))
            await asyncio.sleep(delay)


# --- Main entry point ---


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram bot for pipeline gate notifications")
    parser.add_argument("--poll-interval", type=float, default=15.0, help="DB poll interval in seconds")
    parser.add_argument("--health-interval", type=float, default=60.0, help="Health check interval in seconds")
    parser.add_argument("--platform", type=str, default=None, help="Filter gates by platform_id")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--dry-run", action="store_true", help="Show pending gates without sending")
    return parser.parse_args(argv)


async def async_main(args: argparse.Namespace) -> None:
    """Standalone entry point. Deprecated — use easter.py lifespan instead."""
    import warnings

    warnings.warn("async_main is deprecated, use easter.py", DeprecationWarning, stacklevel=2)
    token = os.environ.get("MADRUGA_TELEGRAM_BOT_TOKEN")
    chat_id_str = os.environ.get("MADRUGA_TELEGRAM_CHAT_ID")

    if not token:
        logger.error("missing_env_var", var="MADRUGA_TELEGRAM_BOT_TOKEN")
        sys.exit(1)
    if not chat_id_str:
        logger.error("missing_env_var", var="MADRUGA_TELEGRAM_CHAT_ID")
        sys.exit(1)

    try:
        chat_id = int(chat_id_str)
    except ValueError:
        logger.error("invalid_chat_id", value=chat_id_str)
        sys.exit(1)

    # Import DB connection (path resolution via config.py)
    from db import get_conn, migrate

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    adapter = TelegramAdapter(bot)

    with get_conn() as conn:
        migrate(conn)

        # Load offset for polling resume
        offset = load_offset(conn)
        if offset:
            logger.info("resuming_from_offset", offset=offset)

        # Persist offset after each update for crash recovery
        @dp.update.outer_middleware()
        async def _persist_offset(handler, event, data):
            result = await handler(event, data)
            if event.update_id:
                save_offset(conn, event.update_id)
            return result

        # Register callback handlers
        @dp.callback_query(F.data.startswith("gate:"))
        async def _handle_gate(callback: CallbackQuery):
            await handle_gate_callback(callback, adapter, conn)

        @dp.callback_query(F.data.startswith("decision:"))
        async def _handle_decision(callback: CallbackQuery):
            await handle_decision_callback(callback, adapter, conn)

        logger.info(
            "bot_starting",
            poll_interval=args.poll_interval,
            health_interval=args.health_interval,
            platform=args.platform or "all",
            dry_run=args.dry_run,
        )

        # Run all tasks concurrently
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                dp.start_polling(bot, offset=offset),
            )
            tg.create_task(
                gate_poller(
                    adapter,
                    chat_id,
                    conn,
                    interval=args.poll_interval,
                    platform_id=args.platform,
                    dry_run=args.dry_run,
                ),
            )
            tg.create_task(
                health_check(bot, interval=args.health_interval),
            )


def _configure_logging(verbose: bool = False) -> None:
    """Configure structlog with JSON output for production, console for dev."""
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
    args = parse_args()
    _configure_logging(args.verbose)

    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        logger.info("bot_stopped", reason="keyboard_interrupt")


if __name__ == "__main__":
    main()
