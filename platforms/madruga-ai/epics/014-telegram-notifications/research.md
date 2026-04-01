# Research — Epic 014 Telegram Notifications

## R-001: aiogram 3.x Inline Keyboards + Callbacks
- **Decision**: aiogram 3.x com `InlineKeyboardBuilder`, `CallbackQuery` handler, `edit_text()`/`edit_reply_markup()`
- **Rationale**: Framework asyncio-native, builder pattern intuitivo, HTML parse mode nativo
- **Alternatives**: python-telegram-bot (sincrono), grammY (TypeScript)

## R-002: Dual-Loop Architecture
- **Decision**: `dp.start_polling()` + `asyncio.create_task(poll_gates())` no mesmo event loop
- **Rationale**: aiogram gerencia long-polling, DB polling e task asyncio separada
- **Alternatives**: Thread separado (desnecessario com asyncio), webhook (requer porta inbound)

## R-003: Deduplicacao via gate_notified_at + telegram_message_id
- **Decision**: Nova coluna `telegram_message_id` em `pipeline_runs` (migration 008)
- **Rationale**: Permite editar mensagem apos approve/reject. `gate_notified_at` ja existe para dedup.
- **Alternatives**: Tabela separada (overhead), JSON em gate_status (fragil)

## R-004: pyproject.toml
- **Decision**: `pyproject.toml` declarativo com aiogram >= 3.15 + pyyaml >= 6.0
- **Rationale**: Padrao moderno Python 3.11+, extensivel, suporta pip install -e .
- **Alternatives**: requirements.txt (sem metadata), pip-tools (overhead para projeto simples)

## R-005: Offset Persistence
- **Decision**: Salvar `telegram_last_update_id` em `local_config` (existente)
- **Rationale**: Reusa infraestrutura, evita reprocessamento de callbacks apos restart
- **Alternatives**: Arquivo separado (fragmenta estado), sqlite3 table dedicada (overkill)

## R-006: Migration 008
- **Decision**: `ALTER TABLE pipeline_runs ADD COLUMN telegram_message_id INTEGER`
- **Rationale**: Necessario para `edit_message_text()` apos approve/reject
- **Alternatives**: Nao salvar message_id (impossibilita edicao)
