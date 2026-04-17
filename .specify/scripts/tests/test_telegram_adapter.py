"""Tests for MessagingProvider and TelegramAdapter."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from telegram_adapter import (
    ALERT_PREFIXES,
    MAX_MESSAGE_LENGTH,
    MessagingProvider,
    TelegramAdapter,
    _truncate,
)


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    msg = MagicMock()
    msg.message_id = 42
    bot.send_message.return_value = msg
    bot.edit_message_text.return_value = None
    return bot


@pytest.fixture
def adapter(mock_bot):
    return TelegramAdapter(mock_bot)


class TestMessagingProviderABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            MessagingProvider()


class TestTelegramAdapterSend:
    def test_send_returns_message_id(self, adapter, mock_bot):
        result = asyncio.run(adapter.send(123, "hello"))
        assert result == 42
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args
        assert call_kwargs[0][0] == 123
        assert call_kwargs[0][1] == "hello"

    def test_send_uses_html_parse_mode(self, adapter, mock_bot):
        asyncio.run(adapter.send(123, "<b>bold</b>"))
        call_kwargs = mock_bot.send_message.call_args
        assert call_kwargs[1]["parse_mode"].value == "HTML"


class TestTelegramAdapterAskChoice:
    def test_ask_choice_returns_message_id(self, adapter, mock_bot):
        choices = [("Aprovar", "gate:1:a"), ("Rejeitar", "gate:1:r")]
        result = asyncio.run(adapter.ask_choice(123, "Approve?", choices))
        assert result == 42

    def test_ask_choice_sends_inline_keyboard(self, adapter, mock_bot):
        choices = [("Aprovar", "gate:1:a"), ("Rejeitar", "gate:1:r")]
        asyncio.run(adapter.ask_choice(123, "Approve?", choices))
        call_kwargs = mock_bot.send_message.call_args
        reply_markup = call_kwargs[1]["reply_markup"]
        buttons = reply_markup.inline_keyboard
        assert len(buttons) > 0


class TestTelegramAdapterAlert:
    def test_alert_info_prefix(self, adapter, mock_bot):
        asyncio.run(adapter.alert(123, "Node completo", "info"))
        call_args = mock_bot.send_message.call_args
        sent_text = call_args[0][1]
        assert ALERT_PREFIXES["info"] in sent_text

    def test_alert_warn_prefix(self, adapter, mock_bot):
        asyncio.run(adapter.alert(123, "Timeout", "warn"))
        sent_text = mock_bot.send_message.call_args[0][1]
        assert "ATENCAO" in sent_text

    def test_alert_error_prefix(self, adapter, mock_bot):
        asyncio.run(adapter.alert(123, "Falha", "error"))
        sent_text = mock_bot.send_message.call_args[0][1]
        assert "ERRO" in sent_text

    def test_alert_unknown_level_defaults_to_info(self, adapter, mock_bot):
        asyncio.run(adapter.alert(123, "test", "unknown"))
        sent_text = mock_bot.send_message.call_args[0][1]
        assert ALERT_PREFIXES["info"] in sent_text


class TestTelegramAdapterEditMessage:
    def test_edit_message_calls_bot(self, adapter, mock_bot):
        asyncio.run(adapter.edit_message(123, 42, "Aprovado"))
        mock_bot.edit_message_text.assert_called_once()
        call_args = mock_bot.edit_message_text.call_args
        assert call_args[0][0] == "Aprovado"
        assert call_args[1]["chat_id"] == 123
        assert call_args[1]["message_id"] == 42

    def test_edit_message_removes_reply_markup(self, adapter, mock_bot):
        asyncio.run(adapter.edit_message(123, 42, "Done", reply_markup=None))
        assert mock_bot.edit_message_text.call_args[1]["reply_markup"] is None


class TestTruncate:
    def test_short_message_unchanged(self):
        assert _truncate("hello") == "hello"

    def test_long_message_truncated(self):
        long_text = "x" * (MAX_MESSAGE_LENGTH + 100)
        result = _truncate(long_text)
        assert len(result) <= MAX_MESSAGE_LENGTH
        assert "[mensagem truncada]" in result

    def test_exact_limit_unchanged(self):
        text = "x" * MAX_MESSAGE_LENGTH
        assert _truncate(text) == text


class TestFormatAlertMessage:
    def test_info_prefix(self):
        assert ALERT_PREFIXES["info"] == "<b>Pipeline</b>"

    def test_warn_prefix(self):
        assert "ATENCAO" in ALERT_PREFIXES["warn"]

    def test_error_prefix(self):
        assert "ERRO" in ALERT_PREFIXES["error"]
