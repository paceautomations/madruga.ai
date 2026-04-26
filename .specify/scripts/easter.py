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
import sqlite3
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import structlog
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

sys.path.insert(0, os.path.dirname(__file__))

from dag_executor import run_pipeline_async  # noqa: E402
from ensure_repo import DirtyTreeError  # noqa: E402
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

# Per-epic consecutive pipeline failure counter (in-memory; resets on daemon
# restart). After MAX_EPIC_DISPATCH_FAILURES consecutive non-zero exits, the
# epic is auto-transitioned to status='blocked' to stop the retry storm.
# Postmortem: prosauai/003 T031-T046 cascade retried ~22× before user noticed.
_epic_fail_counts: dict[str, int] = {}
# One-shot notification tracker for DirtyTreeError. Dirty tree is a transient
# user-state condition (dev is mid-work on another epic in the same repo), not
# a pipeline failure — easter skips dispatch and self-heals when the tree goes
# clean. We notify once per streak to avoid spamming every poll_interval.
_dirty_notified: set[str] = set()
MAX_EPIC_DISPATCH_FAILURES = int(os.environ.get("MADRUGA_MAX_EPIC_FAILS", "3"))
RATE_LIMIT_COOLDOWN_SECONDS = int(os.environ.get("MADRUGA_RATE_LIMIT_COOLDOWN", "600"))
_platform_filter: str | None = None

_RATE_LIMIT_PATTERNS = ("hit your limit", "rate limit exceeded", "resets")


def _is_rate_limit_error_str(error: str | None) -> bool:
    if not error:
        return False
    lower = error.lower()
    return any(p in lower for p in _RATE_LIMIT_PATTERNS)


def _get_last_failed_run(conn, platform_id: str, epic_id: str) -> dict | None:
    """Return the most recent failed pipeline_run for this epic, or None."""
    row = conn.execute(
        """
        SELECT error, completed_at
        FROM pipeline_runs
        WHERE platform_id=? AND epic_id=? AND status='failed'
        ORDER BY completed_at DESC
        LIMIT 1
        """,
        (platform_id, epic_id),
    ).fetchone()
    return dict(row) if row else None


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


# --- Zombie Sweep ---------------------------------------------------

# A3: Mark stale 'running' rows as 'failed' when they exceed this age without
# a completion timestamp. Rationale: whenever the daemon is killed with SIGKILL
# (shutdown timeout, crash, OOM), active runs are left "running" forever. The
# sweep runs once at startup (catches restart crashes) and periodically while
# alive (catches runaway tasks). 1 hour is the conservative threshold — real
# implement tasks can legitimately run for 20-30 minutes.
ZOMBIE_THRESHOLD = "-1 hour"


def _sweep_zombies_sync(conn) -> tuple[int, int]:
    """Synchronous core for zombie sweep (easier to test). Returns (runs, traces) swept.

    Uses julianday() for comparison because our timestamps are stored as ISO
    strings with 'T' separator and 'Z' suffix, while ``datetime('now', ...)``
    produces ``'YYYY-MM-DD HH:MM:SS'`` without them. Lexicographic comparison
    between the two formats is always wrong (``'T' > ' '``). julianday converts
    both to numeric days and compares correctly across formats.
    """
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    runs_swept = conn.execute(
        "UPDATE pipeline_runs SET status='failed', "
        "error=COALESCE(error, 'zombie — daemon restart or crash'), "
        "completed_at=? "
        "WHERE status='running' "
        "AND julianday(started_at) < julianday('now', ?) "
        "AND (gate_status IS NULL OR gate_status != 'waiting_approval')",
        (now, ZOMBIE_THRESHOLD),
    ).rowcount

    traces_swept = conn.execute(
        "UPDATE traces SET status='failed', completed_at=? "
        "WHERE status='running' "
        "AND julianday(started_at) < julianday('now', ?)",
        (now, ZOMBIE_THRESHOLD),
    ).rowcount

    conn.commit()
    return runs_swept, traces_swept


async def sweep_zombies(conn) -> None:
    """Log-wrapping async facade for the zombie sweep.

    Runs inline on the event loop — sqlite3.Connection objects are bound to
    their creating thread (``check_same_thread=True`` default), so dispatching
    the sweep via ``asyncio.to_thread`` triggers a ProgrammingError. The two
    UPDATE statements complete in <1 ms, so the event loop yield is negligible.
    """
    try:
        runs_swept, traces_swept = _sweep_zombies_sync(conn)
    except Exception:
        logger.exception("zombie_sweep_failed")
        return

    if runs_swept or traces_swept:
        logger.warning("zombie_sweep_done", runs_swept=runs_swept, traces_swept=traces_swept)
    else:
        logger.debug("zombie_sweep_clean")


async def dag_scheduler(conn, semaphore, shutdown_event, poll_interval=15, platform_id=None):
    """Poll active epics and dispatch pipeline runs.

    INVARIANT: self-ref platforms execute epics sequentially.

    Note on connections: the ``conn`` argument is the connection opened in
    ``lifespan()`` (kept for signature/test compatibility) but it is NOT used
    inside the poll loop. Instead, every iteration opens a fresh connection
    via ``get_conn()``. This protects against stale file descriptors when the
    SQLite file is deleted and recreated underneath the daemon (e.g. by the
    post-merge auto-reseed hook or a manual ``make seed``). Without this, the
    daemon polls a phantom inode forever and never sees newly inserted epics.
    The cost is one ``open()`` + WAL pragmas per poll interval (~1 ms) which
    is negligible against the 15 s default cadence.
    """
    from db import get_conn, get_pending_gates

    # A3: Periodic zombie sweep state — runs every ZOMBIE_SWEEP_INTERVAL seconds
    # regardless of how many polls happen between them. Belt-and-suspenders with
    # the startup sweep in lifespan(): startup catches restart-after-crash zombies,
    # periodic catches tasks that zombify while the daemon is alive.
    zombie_sweep_interval = float(os.environ.get("MADRUGA_ZOMBIE_SWEEP_INTERVAL", "300"))  # 5 min
    last_sweep_monotonic = time.monotonic()

    consecutive_errors = 0
    while not shutdown_event.is_set():
        try:
            # N5: skip DB poll when an epic is already running (sequential constraint)
            if _running_epics:
                await _interruptible_sleep(shutdown_event, poll_interval)
                continue

            # Reopen the DB connection on every poll so that DB recreation events
            # (post-merge reseed, manual `make seed`, copy-restore from backup)
            # do not leave us bound to a deleted inode. See module docstring above.
            try:
                poll_conn = get_conn()
            except Exception:
                logger.exception("dag_scheduler_get_conn_failed")
                await _interruptible_sleep(shutdown_event, poll_interval)
                continue

            try:
                # A3: periodic zombie sweep (belt-and-suspenders)
                if time.monotonic() - last_sweep_monotonic >= zombie_sweep_interval:
                    await sweep_zombies(poll_conn)
                    last_sweep_monotonic = time.monotonic()

                epics = poll_active_epics(poll_conn, platform_id=platform_id)
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
                    pending = get_pending_gates(poll_conn, epic_platform_id)
                    epic_pending = [
                        g for g in pending if g.get("epic_id") == epic_id and g.get("gate_status") == "waiting_approval"
                    ]
                    if epic_pending:
                        logger.debug("gate_pending_skip", epic_id=epic_id, gate=epic_pending[0]["node_id"])
                        continue

                    # Rate limit cooldown: if the last run failed with a token
                    # limit error recently, hold off dispatching until cooldown
                    # expires. This prevents rapid-fire retries that waste turns
                    # against a limit that may take minutes/hours to reset.
                    last_failed = _get_last_failed_run(poll_conn, epic_platform_id, epic_id)
                    if last_failed and _is_rate_limit_error_str(last_failed["error"]):
                        completed_at = last_failed["completed_at"]
                        if completed_at:
                            try:
                                import datetime as _dt

                                fail_ts = _dt.datetime.fromisoformat(completed_at).timestamp()
                            except Exception:
                                fail_ts = time.time() - RATE_LIMIT_COOLDOWN_SECONDS
                            elapsed = time.time() - fail_ts
                            if elapsed < RATE_LIMIT_COOLDOWN_SECONDS:
                                remaining = int(RATE_LIMIT_COOLDOWN_SECONDS - elapsed)
                                logger.info(
                                    "rate_limit_cooldown_active",
                                    epic_id=epic_id,
                                    platform=epic_platform_id,
                                    remaining_s=remaining,
                                )
                                continue

                    _running_epics.add(epic_id)

                    # A11: bind structlog contextvars so every log line emitted
                    # inside run_pipeline_async (including dag_executor logs once
                    # they're routed through LoggingHandler in A2-long) carries
                    # epic_id, platform, and trace_id (resolved later). We unbind
                    # in finally to avoid leaking context to other epics.
                    from structlog.contextvars import bind_contextvars, unbind_contextvars

                    bind_contextvars(epic_id=epic_id, platform=epic_platform_id)
                    logger.info("dispatching_epic", epic_id=epic_id, platform=epic_platform_id)

                    # F3: Proactive branch checkout before dispatch
                    # For external repos, get_repo_work_dir handles branch checkout.
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
                        if result == 0:
                            # success → clear the fail streak + dirty-tree streak
                            _epic_fail_counts.pop(epic_id, None)
                            _dirty_notified.discard(epic_id)
                        else:
                            _epic_fail_counts[epic_id] = _epic_fail_counts.get(epic_id, 0) + 1
                            fail_count = _epic_fail_counts[epic_id]
                            logger.warning(
                                "epic_dispatch_failed",
                                epic_id=epic_id,
                                exit_code=result,
                                consecutive_failures=fail_count,
                                max=MAX_EPIC_DISPATCH_FAILURES,
                            )
                            # C2: notify via ntfy when pipeline fails
                            topic = os.environ.get("MADRUGA_NTFY_TOPIC")
                            if topic:
                                await asyncio.to_thread(
                                    ntfy_alert,
                                    topic,
                                    f"Pipeline failed for epic {epic_id} "
                                    f"(exit={result}, streak={fail_count}/{MAX_EPIC_DISPATCH_FAILURES})",
                                )
                            # Auto-block after max consecutive failures. User
                            # must re-enable via portal Start after fixing root cause.
                            if fail_count >= MAX_EPIC_DISPATCH_FAILURES:
                                try:
                                    _mark_epic_blocked(epic_platform_id, epic_id)
                                    logger.error(
                                        "epic_auto_blocked",
                                        epic_id=epic_id,
                                        platform=epic_platform_id,
                                        after_failures=fail_count,
                                    )
                                    if topic:
                                        await asyncio.to_thread(
                                            ntfy_alert,
                                            topic,
                                            f"Epic {epic_id} AUTO-BLOCKED after "
                                            f"{fail_count} consecutive failures. "
                                            f"Investigate and run: UPDATE epics "
                                            f"SET status='in_progress' WHERE epic_id='{epic_id}'",
                                        )
                                    _epic_fail_counts.pop(epic_id, None)
                                except Exception:
                                    logger.exception("epic_auto_block_failed", epic_id=epic_id)
                            # Cooldown after failure to avoid rapid retry busy-loop
                            await _interruptible_sleep(shutdown_event, poll_interval * 2)
                    except DirtyTreeError as dirty:
                        # Transient user-state — dev is working in the bound repo.
                        # Skip dispatch safely; self-heals when the tree is clean.
                        # Notify once per streak to avoid spamming the poll loop.
                        if epic_id not in _dirty_notified:
                            logger.warning(
                                "epic_skipped_dirty_tree",
                                epic_id=epic_id,
                                platform=epic_platform_id,
                                dirty_tree_message=str(dirty),
                            )
                            topic = os.environ.get("MADRUGA_NTFY_TOPIC")
                            if topic:
                                await asyncio.to_thread(
                                    ntfy_alert,
                                    topic,
                                    f"Epic {epic_id} SKIPPED: dirty working tree in {epic_platform_id} repo. "
                                    f"Will auto-resume when tree is clean. Commit or stash to unblock.",
                                )
                            _dirty_notified.add(epic_id)
                        else:
                            logger.debug(
                                "epic_skipped_dirty_tree_repeat",
                                epic_id=epic_id,
                                platform=epic_platform_id,
                            )
                        # Longer cooldown than a normal poll — the dev is editing,
                        # no need to retry every poll_interval.
                        await _interruptible_sleep(shutdown_event, poll_interval * 4)
                    finally:
                        _running_epics.discard(epic_id)
                        unbind_contextvars("epic_id", "platform")
            finally:
                try:
                    poll_conn.close()
                except Exception:
                    pass

        except Exception:
            consecutive_errors += 1
            backoff = min(poll_interval * (2**consecutive_errors), 300)
            logger.exception("dag_scheduler_error", consecutive_errors=consecutive_errors, backoff_s=backoff)
            await _interruptible_sleep(shutdown_event, backoff)
            continue

        await _interruptible_sleep(shutdown_event, poll_interval)


def _current_rss_mb() -> float | None:
    """Resident memory in MB for the current process. ``None`` on non-Linux.

    Reads /proc/self/status (stdlib, zero deps). health_checker publishes
    this periodically so memory regressions in long-running dispatch loops
    are observable via log/metrics pipeline.
    """
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # Format: "VmRSS:\t  123456 kB"
                    return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


async def health_checker(bot, shutdown_event, interval=60, conn=None, adapter=None, chat_id=None):
    """Check Telegram API connectivity and send systemd watchdog pings."""
    from telegram_bot import poll_pending_gates

    while not shutdown_event.is_set():
        if await _interruptible_sleep(shutdown_event, interval):
            break

        # Systemd watchdog
        sd_notify("WATCHDOG=1")

        # A1 validation metric: current resident memory. Published every
        # `interval` seconds so Grafana/journalctl can confirm the
        # stream-to-file refactor actually dropped the peak sustained RSS.
        rss_mb = _current_rss_mb()
        if rss_mb is not None:
            logger.info("easter_rss", rss_mb=round(rss_mb, 1))

        if bot is None:
            continue

        try:
            # Bound the Telegram check so a stuck network call cannot stall
            # this loop past WatchdogSec (120s) — without the timeout, a
            # blocked aiogram await skips sd_notify("WATCHDOG=1") and
            # systemd kills the service.
            me = await asyncio.wait_for(bot.get_me(), timeout=10)
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
        except Exception as e:
            _easter_state.telegram_fail_count += 1
            logger.warning(
                "health_check_failed",
                fail_count=_easter_state.telegram_fail_count,
                err_type=type(e).__name__,
            )

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


#: Retention horizon for subprocess diagnostic artifacts (stream + timeout).
#: 7 days balances "enough to postmortem a weekend failure on Monday" with
#: bounded disk usage (typical artifact = 10-50 MB).
DISPATCH_ARTIFACT_RETENTION_DAYS = 7


def _cleanup_dispatch_artifacts(days: int) -> dict[str, int]:
    """Delete .pipeline/stream/*.stdout and .pipeline/timeout-diagnostics/*.stdout
    older than ``days``. Synchronous — call via asyncio.to_thread.

    Returns a dict with per-directory deletion counts.
    """
    from config import REPO_ROOT

    cutoff = time.time() - days * 86400
    result = {"stream_deleted": 0, "timeout_deleted": 0, "errors": 0}
    for dir_name, key in (("stream", "stream_deleted"), ("timeout-diagnostics", "timeout_deleted")):
        d = REPO_ROOT / ".pipeline" / dir_name
        if not d.is_dir():
            continue
        for p in d.glob("*.stdout"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
                    result[key] += 1
            except OSError:
                result["errors"] += 1
    return result


async def dispatch_artifact_cleanup(shutdown_event, interval=86400, days=DISPATCH_ARTIFACT_RETENTION_DAYS):
    """Remove old subprocess stdout diagnostics. Runs once daily.

    Targets ``.pipeline/stream/*.stdout`` (live dispatch buffer preserved on
    error/timeout by ``dispatch_node_async``) and ``.pipeline/timeout-
    diagnostics/*.stdout`` (legacy pre-unified path). Without this cron,
    artifacts accumulate indefinitely across weeks of error runs.
    """
    while not shutdown_event.is_set():
        if await _interruptible_sleep(shutdown_event, interval):
            break
        try:
            result = await asyncio.to_thread(_cleanup_dispatch_artifacts, days)
            logger.info("dispatch_artifact_cleanup", **result)
        except Exception:
            logger.exception("dispatch_artifact_cleanup_error")


def _backup_db(src_db_path: str, target_path: str) -> None:
    """VACUUM INTO using a fresh sqlite connection opened in the caller thread.

    sqlite3 connections default to check_same_thread=True; periodic_backup
    runs via asyncio.to_thread so the lifespan conn cannot be reused.
    """
    local_conn = sqlite3.connect(src_db_path)
    try:
        local_conn.execute("VACUUM INTO ?", (target_path,))
    finally:
        local_conn.close()


def _mark_epic_blocked(platform_id: str, epic_id: str) -> None:
    """Set epics.status='blocked' via a short-lived connection."""
    from db import get_conn

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE epics SET status='blocked' WHERE platform_id=? AND epic_id=?",
            (platform_id, epic_id),
        )
        conn.commit()
    finally:
        conn.close()


async def periodic_backup(_unused_conn, shutdown_event, interval_hours=6):
    """Create periodic DB backups via VACUUM INTO. Rotate to keep last 5."""
    from config import DB_PATH as _db_path

    backup_dir = _db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    while not shutdown_event.is_set():
        if await _interruptible_sleep(shutdown_event, interval_hours * 3600):
            break
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
            path = backup_dir / f"madruga_{timestamp}.db"
            await asyncio.to_thread(_backup_db, str(_db_path), str(path))
            logger.info("backup_created", path=str(path))
            # Rotate: keep last 5
            backups = sorted(backup_dir.glob("madruga_*.db"))
            for old in backups[:-5]:
                old.unlink()
                logger.info("backup_rotated", path=str(old))
        except Exception:
            logger.exception("backup_failed")


# --- Lifespan ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start background tasks, handle shutdown."""
    # A2: Logging config MUST run before any logger.info() call.
    # When easter is started via `uvicorn easter:app` (systemd path), easter.main()
    # never runs, so _configure_logging() would never be invoked. Result: zero
    # dag_executor output in journald. Invoking it here guarantees the structlog
    # pipeline is set up regardless of entry point (main() vs uvicorn).
    _configure_logging(os.environ.get("MADRUGA_VERBOSE", "").lower() in ("1", "true", "yes"))

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

    # Integrity check — fail fast if DB is corrupt
    integrity = conn.execute("PRAGMA integrity_check").fetchone()
    if integrity[0] != "ok":
        logger.error("db_integrity_check_failed", result=integrity[0])
        conn.close()
        sys.exit(78)  # EX_CONFIG — operator runs: make seed
    logger.info("db_integrity_ok")

    app.state.db_conn = conn

    # A3: startup zombie sweep — mark orphaned 'running' runs/traces from a
    # previous crashed or SIGKILL'd daemon as 'failed'. Must happen after
    # migrate() (schema ready) and before dag_scheduler starts polling, so the
    # first poll sees a clean state.
    await sweep_zombies(conn)

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

            # Dispatch artifact cleanup (daily) — A1 stream files + timeout diagnostics
            tg.create_task(dispatch_artifact_cleanup(_shutdown_event))

            # DB backup (every 6 hours)
            tg.create_task(periodic_backup(conn, _shutdown_event))

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

                # Clear stale webhook + pending updates before polling to avoid
                # TelegramConflictError from a previous instance's lingering
                # getUpdates session on Telegram's side (ADR-018).
                try:
                    await bot.delete_webhook(drop_pending_updates=True)
                    logger.info("telegram_webhook_reset")
                except Exception:
                    logger.exception("delete_webhook_failed")

                tg.create_task(dp.start_polling(bot, offset=offset))
                tg.create_task(tg_gate_poller(adapter, chat_id, conn))
                tg.create_task(gate_reminder(conn, adapter, chat_id, _shutdown_event))

            yield  # FastAPI serves requests here

            # Shutdown
            _easter_state.easter_state = "shutting_down"
            _shutdown_event.set()
            sd_notify("STOPPING=1")

            # A8: propagate SIGTERM down the claude subprocess tree so they
            # can flush/exit cleanly instead of being SIGKILL'd when systemd's
            # TimeoutStopSec expires (60s). 45s for subprocesses + 15s for
            # easter shutdown (WAL checkpoint, lock file). Previously 10s
            # caused premature SIGKILL on long nodes (judge ~12min).
            try:
                from dag_executor import terminate_active_subprocesses

                signalled = await terminate_active_subprocesses(graceful_timeout=45.0)
                if signalled:
                    logger.info("shutdown_terminated_children", count=signalled)
            except Exception:
                logger.exception("shutdown_terminate_failed")
    except* Exception as eg:
        for exc in eg.exceptions:
            logger.exception("taskgroup_error", error=str(exc))
    finally:
        # Close aiogram HTTP session so Telegram releases the long-poll
        # connection server-side. Avoids TelegramConflictError on the next
        # easter restart.
        if bot is not None:
            try:
                await bot.session.close()
                logger.info("telegram_session_closed")
            except Exception:
                logger.exception("telegram_session_close_failed")
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            logger.info("wal_checkpoint_done")
        except Exception:
            logger.exception("wal_checkpoint_failed")
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


# A4: Fresh connection per request. Prevents the same stale-inode bug fixed for
# dag_scheduler (commit a879b46): after `make seed` or a post-merge reseed, the
# connection cached on app.state points to a deleted inode and silently serves
# phantom data. Opening per request costs ~1 ms against admin-only endpoints —
# negligible — and guarantees the portal always reads the live DB.
async def get_fresh_conn():
    from db import get_conn as _gc

    conn = _gc()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


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


def _aggregate_completed_nodes(rows: list[dict]) -> tuple[int, dict | None]:
    """Count DAG nodes fully complete from a list of pipeline_runs rows.

    A5: Sub-tasks of ``speckit.implement`` (one row per ``implement:T00N``) must
    NOT inflate the completed-node count. The rule per user feedback: a node
    only counts as completed when every sub-task has terminated successfully.
    39/51 sub-tasks still means *zero* implement nodes completed.

    Returns ``(completed_count, implement_progress)`` where implement_progress is
    ``{"done", "total"}`` or ``None`` when implement never started. The portal
    uses it to render "5/12 (implement: 32/51)".
    """
    completed: set[str] = set()
    implement_total = 0
    implement_done = 0

    for r in rows:
        nid = r["node_id"] or ""
        status = r["status"]
        if nid.startswith("implement:"):
            implement_total += 1
            if status == "completed":
                implement_done += 1
        else:
            if status == "completed":
                completed.add(nid)

    if implement_total > 0 and implement_done == implement_total:
        completed.add("implement")

    progress = {"done": implement_done, "total": implement_total} if implement_total else None
    return len(completed), progress


@app.get("/api/sessions")
async def sessions(platform_id: str | None = Query(default=None), conn=Depends(get_fresh_conn)):
    """Active sessions with per-session detail.

    Opens a fresh DB connection per request (via ``get_fresh_conn``) so we never
    serve from a stale inode after a ``make seed`` / post-merge reseed — same
    rationale as the comment in ``dag_scheduler``. Negligible cost for an
    admin-only endpoint.
    """
    result = {
        "easter_state": _easter_state.easter_state,
        "telegram_status": _easter_state.telegram_status,
        "uptime_seconds": int(time.time() - _easter_state.start_time),
        "pid": os.getpid(),
        "poll_interval_seconds": 15,
        "running_epics": [],
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
                    "MAX(COALESCE(completed_at, started_at)) AS last_activity "
                    "FROM pipeline_runs WHERE trace_id=?",
                    (tid,),
                ).fetchone()
                nodes = conn.execute(
                    "SELECT node_id, status FROM pipeline_runs WHERE trace_id=? ORDER BY started_at",
                    (tid,),
                ).fetchall()
                rows = [{"node_id": n["node_id"], "status": n["status"]} for n in nodes]
                completed_nodes, implement_progress = _aggregate_completed_nodes(rows)
                # Pretty current_node: hide implement sub-task id for the generic
                # header but keep it in node_statuses so the frontend can show
                # the precise task in a sub-indicator.
                current_node_label = None
                current_node_started_at = None
                if running_node:
                    current_node_label = running_node["node_id"]
                    current_node_started_at = running_node["started_at"]
                session.update(
                    {
                        "trace_id": tid,
                        "started_at": trace_row["started_at"],
                        "current_node": current_node_label,
                        "current_node_started_at": current_node_started_at,
                        "session_cost_usd": agg["cost"] or 0,
                        "tokens_in": agg["tin"] or 0,
                        "tokens_out": agg["tout"] or 0,
                        "completed_nodes": completed_nodes,
                        "total_nodes": trace_row["total_nodes"] or 12,
                        "implement_progress": implement_progress,
                        "last_activity": agg["last_activity"],
                        "node_statuses": rows,
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
                        "implement_progress": None,
                        "last_activity": None,
                        "node_statuses": [],
                    }
                )
            result["running_epics"].append(session)

    return result


# --- Observability Endpoints ---


@app.get("/api/traces")
async def list_traces(
    platform_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    conn=Depends(get_fresh_conn),
):
    if not platform_id:
        return JSONResponse(status_code=400, content={"error": "platform_id is required"})

    from db import get_traces

    traces, total = get_traces(conn, platform_id, limit, offset, status)
    return {"traces": traces, "total": total, "limit": limit, "offset": offset}


@app.get("/api/traces/{trace_id}")
async def trace_detail(trace_id: str, conn=Depends(get_fresh_conn)):
    from db import get_trace_detail

    result = get_trace_detail(conn, trace_id)
    if result is None:
        return JSONResponse(status_code=404, content={"error": "trace not found"})
    return result


@app.get("/api/runs")
async def list_runs(
    platform_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    epic_id: str | None = Query(default=None),
    conn=Depends(get_fresh_conn),
):
    from db import get_runs_with_evals

    runs, total = get_runs_with_evals(
        conn,
        platform_id,
        limit,
        offset,
        status,
        epic_id,
    )
    return {"runs": runs, "total": total, "limit": limit, "offset": offset}


@app.get("/api/evals")
async def list_evals(
    platform_id: str | None = Query(default=None),
    node_id: str | None = Query(default=None),
    dimension: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    conn=Depends(get_fresh_conn),
):
    if not platform_id:
        return JSONResponse(status_code=400, content={"error": "platform_id is required"})

    from db import get_eval_scores

    scores, total = get_eval_scores(conn, platform_id, node_id, dimension, limit)
    return {"scores": scores, "total": total}


@app.get("/api/stats")
async def stats(
    platform_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=90),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn=Depends(get_fresh_conn),
):
    from db import get_stats

    result = get_stats(
        conn,
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
    platform_id: str | None = Query(default=None),
    entity: str | None = Query(default=None),
    days: int = Query(default=90, ge=1, le=365),
    conn=Depends(get_fresh_conn),
):
    if not platform_id:
        return JSONResponse(status_code=400, content={"error": "platform_id is required"})
    if not entity:
        return JSONResponse(status_code=400, content={"error": "entity is required"})

    from observability_export import VALID_ENTITIES, export_csv

    if entity not in VALID_ENTITIES:
        return JSONResponse(status_code=400, content={"error": f"entity must be one of: {', '.join(VALID_ENTITIES)}"})

    from datetime import date

    csv_str = export_csv(conn, platform_id, entity, days)
    filename = f"{entity}_{platform_id}_{date.today().isoformat()}.csv"
    return Response(
        content=csv_str,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/commits")
async def list_commits(
    platform_id: str | None = Query(default=None),
    epic_id: str | None = Query(default=None),
    commit_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    reconciled: str | None = Query(default=None, pattern="^(true|false)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn=Depends(get_fresh_conn),
):
    from db_pipeline import get_commits_paginated

    commits, total = get_commits_paginated(
        conn,
        limit=limit,
        offset=offset,
        platform_id=platform_id,
        epic_id=epic_id,
        commit_type=commit_type,
        date_from=date_from,
        date_to=date_to,
        reconciled=reconciled,
    )
    return {"commits": commits, "total": total, "limit": limit, "offset": offset}


@app.get("/api/commits/stats")
async def commits_stats(
    platform_id: str | None = Query(default=None),
    conn=Depends(get_fresh_conn),
):
    from db_pipeline import get_commit_stats

    stats = get_commit_stats(conn, platform_id)
    return {
        "total_commits": stats["total_commits"],
        "by_epic": stats["commits_per_epic"],
        "by_platform": stats["commits_per_platform"],
        "adhoc_count": stats["adhoc_count"],
        "adhoc_pct": stats["adhoc_percentage"],
    }


# --- Epic Lifecycle ---


@app.post("/api/epics/{platform_id}/{epic_id}/start")
async def start_epic(platform_id: str, epic_id: str, conn=Depends(get_fresh_conn)):
    """Transition a drafted epic directly to in_progress."""
    from db_core import _now

    row = conn.execute(
        "SELECT status FROM epics WHERE platform_id=? AND epic_id=?",
        (platform_id, epic_id),
    ).fetchone()
    if row is None:
        return JSONResponse(status_code=404, content={"error": f"Epic {epic_id} not found"})
    if row["status"] != "drafted":
        return JSONResponse(
            status_code=409,
            content={"error": f"Cannot start: status is '{row['status']}', expected 'drafted'"},
        )
    # Atomic: set in_progress only if no other epic is already running for this platform
    cur = conn.execute(
        "UPDATE epics SET status='in_progress', updated_at=?"
        " WHERE platform_id=? AND epic_id=? AND status='drafted'"
        " AND NOT EXISTS (SELECT 1 FROM epics WHERE platform_id=? AND status='in_progress')",
        (_now(), platform_id, epic_id, platform_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        running = conn.execute(
            "SELECT epic_id FROM epics WHERE platform_id=? AND status='in_progress' LIMIT 1",
            (platform_id,),
        ).fetchone()
        return JSONResponse(
            status_code=409,
            content={"error": f"Platform '{platform_id}' already has epic '{running['epic_id']}' in progress"},
        )
    return {"status": "in_progress", "epic_id": epic_id, "platform_id": platform_id}


# --- CLI Entry Point ---


def _configure_logging(verbose: bool = False) -> None:
    """Configure stdlib logging + structlog unified pipeline.

    A2-long: logs emitted via ``logging.getLogger(__name__)`` (the stdlib API
    used by ``dag_executor``) flow through the SAME structlog pipeline as
    ``structlog.get_logger(__name__)`` calls. This means every ``log.info`` in
    dag_executor inherits ``epic_id``/``platform``/``trace_id`` from the
    contextvars bound by ``dag_scheduler`` and emits JSON on stdout — visible
    in ``journalctl --user -u madruga-easter``.

    Safe to call multiple times: idempotent handler attach, clears existing
    handlers to avoid duplicate lines when uvicorn + this both configure.
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Shared processor chain used by both stdlib and native structlog loggers.
    # Runs before the final renderer, so the JSON payload carries contextvars
    # and timestamps regardless of which API emitted the record.
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer = structlog.dev.ConsoleRenderer() if verbose else structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors
        + [
            # When used via stdlib LoggingHandler, this hands the event_dict to
            # ProcessorFormatter. When used natively, it renders directly.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Root handler — clear any pre-existing to prevent duplicate lines when
    # uvicorn or something else already installed one.
    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            # foreign_pre_chain runs on records that came from plain ``logging``
            # (the dag_executor case). For records from native structlog, those
            # processors already ran, so we skip them here.
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level)

    # Silence noisy third-party loggers one notch to reduce cost during dispatch.
    for noisy in ("httpx", "httpcore", "asyncio", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


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
