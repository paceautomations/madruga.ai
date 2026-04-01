# Data Model — Epic 014 Telegram Notifications

## Entidades Modificadas

### pipeline_runs (existente)
Nova coluna via migration 008:

| Campo | Tipo | Nullable | Descricao |
|-------|------|----------|-----------|
| telegram_message_id | INTEGER | SIM | ID da mensagem Telegram enviada para este gate |

### local_config (existente)
Novas keys:

| Key | Tipo Valor | Descricao |
|-----|------------|-----------|
| telegram_last_update_id | str(int) | Ultimo update_id processado pelo bot |

## Entidades Novas (codigo, nao BD)

### MessagingProvider (ABC)
Interface abstrata para canal de notificacao.

| Metodo | Params | Retorno | Descricao |
|--------|--------|---------|-----------|
| send | chat_id, text, **kwargs | int (message_id) | Mensagem simples |
| ask_choice | chat_id, text, choices | int (message_id) | Mensagem com inline keyboard |
| alert | chat_id, text, level | int (message_id) | Alerta com severidade visual |

### TelegramAdapter (impl)
Implementa MessagingProvider via aiogram Bot.

| Metodo Adicional | Params | Retorno | Descricao |
|-----------------|--------|---------|-----------|
| edit_message | chat_id, message_id, text, reply_markup | None | Edita mensagem existente |

### GateNotification (dataclass)
Representacao de gate pendente.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| run_id | str | ID do pipeline_run |
| node_id | str | ID do node (ex: vision) |
| platform_id | str | Plataforma |
| epic_id | str | None | Epic (L2) ou None (L1) |
| gate | str | Tipo de gate (human, 1-way-door) |
| started_at | str | Timestamp de criacao |

### CallbackAction (parsed)
| Campo | Tipo | Descricao |
|-------|------|-----------|
| run_id | str | Extraido de callback_data |
| action | "a" or "r" | approve ou reject |

## State Transitions

```
waiting_approval → [telegram notifica] → waiting_approval (gate_notified_at set)
                                              │
                                    ┌─────────┴─────────┐
                                    ▼                     ▼
                               approved              rejected
                          (gate_resolved_at)     (gate_resolved_at)
```

## Migration 008

```sql
ALTER TABLE pipeline_runs ADD COLUMN telegram_message_id INTEGER;
```
