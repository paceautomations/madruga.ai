"""
telegram_adapter.py — MessagingProvider ABC + TelegramAdapter.

Desacoplado: interface abstrata permite trocar canal de notificacao
sem alterar logica de negocio (bot, poller, handlers).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

MAX_MESSAGE_LENGTH = 4096


class MessagingProvider(ABC):
    """Interface abstrata para canal de notificacao."""

    @abstractmethod
    async def send(self, chat_id: int, text: str, **kwargs) -> int:
        """Envia mensagem simples. Retorna message_id."""

    @abstractmethod
    async def ask_choice(self, chat_id: int, text: str, choices: list[tuple[str, str]]) -> int:
        """Envia mensagem com opcoes inline. choices: [(label, callback_data), ...]. Retorna message_id."""

    @abstractmethod
    async def alert(self, chat_id: int, text: str, level: str = "info") -> int:
        """Envia alerta com indicador visual de severidade. Retorna message_id."""

    @abstractmethod
    async def edit_message(self, chat_id: int, message_id: int, text: str, reply_markup: object | None = None) -> None:
        """Edita mensagem existente. Usado para remover botoes apos resolucao."""


ALERT_PREFIXES = {
    "info": "<b>Pipeline</b>",
    "warn": "<b>Pipeline \u2014 ATENCAO</b>",
    "error": "<b>Pipeline Alert \u2014 ERRO</b>",
}


class TelegramAdapter(MessagingProvider):
    """Implementacao via aiogram Bot."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send(self, chat_id: int, text: str, **kwargs) -> int:
        text = _truncate(text)
        msg = await self.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, **kwargs)
        return msg.message_id

    async def ask_choice(self, chat_id: int, text: str, choices: list[tuple[str, str]]) -> int:
        builder = InlineKeyboardBuilder()
        for label, callback_data in choices:
            builder.button(text=label, callback_data=callback_data)
        text = _truncate(text)
        msg = await self.bot.send_message(
            chat_id,
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=builder.as_markup(),
        )
        return msg.message_id

    async def alert(self, chat_id: int, text: str, level: str = "info") -> int:
        prefix = ALERT_PREFIXES.get(level, ALERT_PREFIXES["info"])
        full_text = f"{prefix}\n\n{text}"
        return await self.send(chat_id, full_text)

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        text = _truncate(text)
        await self.bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )


def _truncate(text: str) -> str:
    """Trunca mensagem para caber no limite do Telegram (4096 chars)."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        return text
    suffix = "\n\n<i>[mensagem truncada]</i>"
    return text[: MAX_MESSAGE_LENGTH - len(suffix)] + suffix
