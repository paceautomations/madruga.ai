"""Tests for telegram_bot — gate polling, notification, callbacks."""

from __future__ import annotations

import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock


# --- Helpers ---


def _make_conn():
    """Create in-memory DB with pipeline_runs schema + gate fields."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE pipeline_runs (
            run_id TEXT PRIMARY KEY,
            platform_id TEXT NOT NULL,
            epic_id TEXT,
            node_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            gate_status TEXT CHECK (gate_status IN ('waiting_approval','approved','rejected')),
            gate_notified_at TEXT,
            gate_resolved_at TEXT,
            telegram_message_id INTEGER,
            started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        )"""
    )
    conn.execute(
        """CREATE TABLE local_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        )"""
    )
    return conn


def _insert_gate(conn, run_id="run-1", platform_id="madruga-ai", node_id="vision", notified=False):
    conn.execute(
        "INSERT INTO pipeline_runs (run_id, platform_id, node_id, status, gate_status, gate_notified_at) "
        "VALUES (?, ?, ?, 'running', 'waiting_approval', ?)",
        (run_id, platform_id, node_id, "2026-04-01T10:00:00Z" if notified else None),
    )
    conn.commit()


# --- T008: Tests for poll_pending_gates ---


class TestPollPendingGates:
    def test_returns_unnotified_gates(self):
        from telegram_bot import poll_pending_gates

        conn = _make_conn()
        _insert_gate(conn, "run-1", notified=False)
        _insert_gate(conn, "run-2", notified=True)
        gates = poll_pending_gates(conn)
        assert len(gates) == 1
        assert gates[0]["run_id"] == "run-1"

    def test_returns_empty_when_all_notified(self):
        from telegram_bot import poll_pending_gates

        conn = _make_conn()
        _insert_gate(conn, "run-1", notified=True)
        gates = poll_pending_gates(conn)
        assert len(gates) == 0

    def test_filters_by_platform(self):
        from telegram_bot import poll_pending_gates

        conn = _make_conn()
        _insert_gate(conn, "run-1", platform_id="madruga-ai", notified=False)
        _insert_gate(conn, "run-2", platform_id="other", notified=False)
        gates = poll_pending_gates(conn, platform_id="madruga-ai")
        assert len(gates) == 1
        assert gates[0]["platform_id"] == "madruga-ai"

    def test_returns_all_platforms_when_no_filter(self):
        from telegram_bot import poll_pending_gates

        conn = _make_conn()
        _insert_gate(conn, "run-1", platform_id="madruga-ai", notified=False)
        _insert_gate(conn, "run-2", platform_id="other", notified=False)
        gates = poll_pending_gates(conn)
        assert len(gates) == 2


# --- T009: Tests for notify_gate ---


class TestNotifyGate:
    def test_notify_gate_calls_ask_choice(self):
        from telegram_bot import notify_gate

        conn = _make_conn()
        _insert_gate(conn, "run-1")
        gate = dict(conn.execute("SELECT * FROM pipeline_runs WHERE run_id='run-1'").fetchone())

        adapter = AsyncMock()
        adapter.ask_choice.return_value = 99

        asyncio.get_event_loop().run_until_complete(notify_gate(adapter, 123, gate, conn))

        adapter.ask_choice.assert_called_once()
        call_args = adapter.ask_choice.call_args
        assert call_args[0][0] == 123  # chat_id
        # Verify choices contain approve and reject
        choices = call_args[0][2]
        callback_datas = [c[1] for c in choices]
        assert "gate:run-1:a" in callback_datas
        assert "gate:run-1:r" in callback_datas

    def test_notify_gate_saves_message_id_and_notified_at(self):
        from telegram_bot import notify_gate

        conn = _make_conn()
        _insert_gate(conn, "run-1")
        gate = dict(conn.execute("SELECT * FROM pipeline_runs WHERE run_id='run-1'").fetchone())

        adapter = AsyncMock()
        adapter.ask_choice.return_value = 99

        asyncio.get_event_loop().run_until_complete(notify_gate(adapter, 123, gate, conn))

        row = conn.execute(
            "SELECT telegram_message_id, gate_notified_at FROM pipeline_runs WHERE run_id='run-1'"
        ).fetchone()
        assert row[0] == 99
        assert row[1] is not None


# --- T015: Tests for handle_gate_callback (approve) ---


class TestHandleGateCallback:
    def test_approve_updates_db_and_edits_message(self):
        from telegram_bot import handle_gate_callback

        conn = _make_conn()
        _insert_gate(conn, "run-1", notified=True)
        conn.execute("UPDATE pipeline_runs SET telegram_message_id=99 WHERE run_id='run-1'")
        conn.commit()

        callback = AsyncMock()
        callback.data = "gate:run-1:a"
        callback.message = MagicMock()
        callback.message.chat = MagicMock()
        callback.message.chat.id = 123
        callback.message.message_id = 99

        adapter = AsyncMock()

        asyncio.get_event_loop().run_until_complete(handle_gate_callback(callback, adapter, conn))

        # DB updated
        row = conn.execute("SELECT gate_status FROM pipeline_runs WHERE run_id='run-1'").fetchone()
        assert row[0] == "approved"

        # Message edited
        adapter.edit_message.assert_called_once()
        callback.answer.assert_called_once()

    def test_already_resolved_gate(self):
        from telegram_bot import handle_gate_callback

        conn = _make_conn()
        _insert_gate(conn, "run-1", notified=True)
        conn.execute(
            "UPDATE pipeline_runs SET gate_status='approved', gate_resolved_at='2026-04-01' WHERE run_id='run-1'"
        )
        conn.commit()

        callback = AsyncMock()
        callback.data = "gate:run-1:a"
        callback.message = MagicMock()
        callback.message.chat = MagicMock()
        callback.message.chat.id = 123
        callback.message.message_id = 99

        adapter = AsyncMock()

        asyncio.get_event_loop().run_until_complete(handle_gate_callback(callback, adapter, conn))

        # Should not edit message
        adapter.edit_message.assert_not_called()
        callback.answer.assert_called_once()
        assert "resolvido" in callback.answer.call_args[0][0].lower()


# --- T019: Tests for reject path ---


class TestRejectGate:
    def test_reject_updates_db(self):
        from telegram_bot import handle_gate_callback

        conn = _make_conn()
        _insert_gate(conn, "run-1", notified=True)
        conn.execute("UPDATE pipeline_runs SET telegram_message_id=99 WHERE run_id='run-1'")
        conn.commit()

        callback = AsyncMock()
        callback.data = "gate:run-1:r"
        callback.message = MagicMock()
        callback.message.chat = MagicMock()
        callback.message.chat.id = 123
        callback.message.message_id = 99

        adapter = AsyncMock()

        asyncio.get_event_loop().run_until_complete(handle_gate_callback(callback, adapter, conn))

        row = conn.execute("SELECT gate_status FROM pipeline_runs WHERE run_id='run-1'").fetchone()
        assert row[0] == "rejected"
        adapter.edit_message.assert_called_once()


# --- T024: Tests for backoff ---


class TestExponentialBackoff:
    def test_backoff_sequence(self):
        from telegram_bot import calculate_backoff

        # initial=2, factor=1.8, max=30, jitter=25%
        b0 = calculate_backoff(0)
        assert 1.5 <= b0 <= 2.5  # 2.0 +/- 25% jitter
        b1 = calculate_backoff(1)
        assert 2.7 <= b1 <= 4.5  # 3.6 +/- jitter 25%
        b2 = calculate_backoff(2)
        assert 4.8 <= b2 <= 8.1  # 6.48 +/- jitter
        # After many retries, should cap at max
        b10 = calculate_backoff(10)
        assert b10 <= 30.0


# --- T025: Tests for offset persistence ---


class TestOffsetPersistence:
    def test_save_and_load_offset(self):
        from telegram_bot import load_offset, save_offset

        conn = _make_conn()
        assert load_offset(conn) is None
        save_offset(conn, 12345)
        assert load_offset(conn) == 12345
        save_offset(conn, 67890)
        assert load_offset(conn) == 67890


# --- Decision notification tests (Epic 015) ---


def _make_conn_with_events():
    """Create in-memory DB with pipeline_runs + events schema."""
    conn = _make_conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_id TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            action TEXT NOT NULL,
            actor TEXT,
            payload TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        )"""
    )
    return conn


def _sample_decision(decision_id="dec-1"):
    return {
        "id": decision_id,
        "description": "drop column legacy_id from users table",
        "context": "Column has been unused for 6 months",
        "alternatives": ["Add deprecation warning first", "Keep column but stop writing"],
        "risk_score": {"risk": 5, "reversibility": 5, "score": 25},
        "skill": "speckit.implement",
        "platform": "madruga-ai",
        "epic": "015-subagent-judge",
    }


class TestFormatDecisionMessage:
    def test_contains_key_fields(self):
        from telegram_bot import format_decision_message

        msg = format_decision_message(_sample_decision())
        assert "1-Way-Door" in msg
        assert "drop column legacy_id" in msg
        assert "Score de Risco" in msg
        assert "25" in msg
        assert "Alternativas" in msg
        assert "deprecation" in msg.lower()

    def test_without_epic(self):
        from telegram_bot import format_decision_message

        d = _sample_decision()
        del d["epic"]
        msg = format_decision_message(d)
        assert "Epic" not in msg

    def test_without_alternatives(self):
        from telegram_bot import format_decision_message

        d = _sample_decision()
        d["alternatives"] = []
        msg = format_decision_message(d)
        assert "Alternativas" not in msg


class TestNotifyOnewayDecision:
    def test_sends_message_and_records_event(self):
        from telegram_bot import notify_oneway_decision

        conn = _make_conn_with_events()
        adapter = AsyncMock()
        adapter.ask_choice.return_value = 42

        decision = _sample_decision()
        asyncio.get_event_loop().run_until_complete(notify_oneway_decision(adapter, 123, decision, conn))

        adapter.ask_choice.assert_called_once()
        call_args = adapter.ask_choice.call_args
        assert call_args[0][0] == 123  # chat_id
        choices = call_args[0][2]
        callback_datas = [c[1] for c in choices]
        assert "decision:dec-1:a" in callback_datas
        assert "decision:dec-1:r" in callback_datas

        # Verify event recorded
        row = conn.execute("SELECT * FROM events WHERE action='decision_notified'").fetchone()
        assert row is not None


class TestParseDecisionCallbackData:
    def test_valid_approve(self):
        from telegram_bot import parse_decision_callback_data

        result = parse_decision_callback_data("decision:dec-1:a")
        assert result == ("dec-1", "a")

    def test_valid_reject(self):
        from telegram_bot import parse_decision_callback_data

        result = parse_decision_callback_data("decision:dec-1:r")
        assert result == ("dec-1", "r")

    def test_invalid_prefix(self):
        from telegram_bot import parse_decision_callback_data

        assert parse_decision_callback_data("gate:run-1:a") is None

    def test_invalid_action(self):
        from telegram_bot import parse_decision_callback_data

        assert parse_decision_callback_data("decision:dec-1:x") is None


class TestHandleDecisionCallback:
    def test_approve_records_event_and_edits_message(self):
        from telegram_bot import handle_decision_callback

        conn = _make_conn_with_events()
        # Pre-insert a decision_notified event so platform_id lookup works
        conn.execute(
            "INSERT INTO events (platform_id, entity_type, entity_id, action, payload, created_at) "
            "VALUES ('madruga-ai', 'decision', 'dec-1', 'decision_notified', '{\"message_id\": 42}', '2026-04-01')"
        )
        conn.commit()

        callback = AsyncMock()
        callback.data = "decision:dec-1:a"
        callback.message = MagicMock()
        callback.message.chat = MagicMock()
        callback.message.chat.id = 123
        callback.message.message_id = 42

        adapter = AsyncMock()

        asyncio.get_event_loop().run_until_complete(handle_decision_callback(callback, adapter, conn))

        # Event recorded
        row = conn.execute("SELECT payload FROM events WHERE action='decision_resolved'").fetchone()
        assert row is not None
        assert "approved" in row[0]

        # Message edited
        adapter.edit_message.assert_called_once()
        callback.answer.assert_called_once()
        assert "aprovada" in callback.answer.call_args[0][0].lower()

    def test_reject_records_event(self):
        from telegram_bot import handle_decision_callback

        conn = _make_conn_with_events()

        callback = AsyncMock()
        callback.data = "decision:dec-1:r"
        callback.message = MagicMock()
        callback.message.chat = MagicMock()
        callback.message.chat.id = 123
        callback.message.message_id = 42

        adapter = AsyncMock()

        asyncio.get_event_loop().run_until_complete(handle_decision_callback(callback, adapter, conn))

        row = conn.execute("SELECT payload FROM events WHERE action='decision_resolved'").fetchone()
        assert "rejected" in row[0]
        assert "rejeitada" in callback.answer.call_args[0][0].lower()
