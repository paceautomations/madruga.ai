# Implementation Plan: Telegram Notifications

**Branch**: `epic/madruga-ai/014-telegram-notifications` | **Date**: 2026-04-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `platforms/madruga-ai/epics/014-telegram-notifications/spec.md`

## Summary

Implementar notificacoes Telegram para human gates do pipeline usando aiogram 3.x com long-polling. O sistema desacoplado consiste de: (1) interface abstrata `MessagingProvider`, (2) `TelegramAdapter` com inline keyboards para approve/reject, (3) script standalone `telegram_bot.py` que poll DB para gates pendentes e recebe callbacks.

## Technical Context

**Language/Version**: Python 3.12 (compativel com 3.11+)
**Primary Dependencies**: aiogram >= 3.15, pyyaml (existente)
**Storage**: SQLite WAL mode (existente — `.pipeline/madruga.db`)
**Testing**: pytest (existente) + bot real de staging
**Target Platform**: Linux (WSL2), single-machine
**Project Type**: CLI script + library module
**Performance Goals**: Notificacao em < 30s apos gate criado, callback processado em < 2s
**Constraints**: Outbound HTTPS only, single-writer SQLite, < 20 msgs/dia
**Scale/Scope**: Single operator, single chat_id, ~5-10 gates/dia

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Status | Evidencia |
|-----------|--------|-----------|
| I. Pragmatism | PASS | Script standalone simples (~300 LOC), sem over-engineering |
| II. Automate | PASS | Automatiza notificacao manual de gates |
| III. Structured Knowledge | PASS | Padroes documentados em context.md, ADR-018 |
| IV. Fast Action | PASS | Scope minimo: adapter + bot + testes |
| V. Alternatives | PASS | 4 alternativas avaliadas em ADR-018 |
| VI. Brutal Honesty | PASS | Limitacoes documentadas (single operator, sem fallback) |
| VII. TDD | PASS | Testes com bot real + unit tests com mocks |
| VIII. Collaborative Decision | PASS | 10 decisoes capturadas em context.md |
| IX. Observability | PASS | structlog em todos os modulos, health check periodico |

## Project Structure

### Documentation (this feature)

```text
platforms/madruga-ai/epics/014-telegram-notifications/
├── context.md           # Epic context (done)
├── spec.md              # Feature spec (done)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
.specify/scripts/
├── telegram_adapter.py      # MessagingProvider + TelegramAdapter
├── telegram_bot.py          # Standalone bot: polling + gate notify + callbacks
└── tests/
    ├── test_telegram_adapter.py  # Unit tests (mocked Bot)
    └── test_telegram_bot.py      # Integration tests (real bot)

pyproject.toml               # NEW: dependency declaration
.env.example                 # NEW: MADRUGA_TELEGRAM_BOT_TOKEN, MADRUGA_TELEGRAM_CHAT_ID
```

**Structure Decision**: Modulos em `.specify/scripts/` seguem padrao existente (ensure_repo.py, worktree.py, dag_executor.py). Nenhum diretorio novo necessario.

---

## Phase 0: Research

### R-001: aiogram 3.x — Inline Keyboards + Callbacks

**Decision**: Usar `InlineKeyboardBuilder` do aiogram com `callback_data` no formato `gate:{run_id}:{a|r}`.

**Rationale**: aiogram 3.x tem builder pattern nativo para inline keyboards. `CallbackQuery` handler usa `F.data.startswith("gate:")` para filtrar. `callback.message.edit_text()` e `callback.message.edit_reply_markup()` para editar apos decisao.

**Codigo de referencia (aiogram 3.x)**:
```python
from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Enviar com inline keyboard
builder = InlineKeyboardBuilder()
builder.button(text="Aprovar", callback_data=f"gate:{run_id}:a")
builder.button(text="Rejeitar", callback_data=f"gate:{run_id}:r")
await bot.send_message(chat_id, text, reply_markup=builder.as_markup())

# Handler de callback
@dp.callback_query(F.data.startswith("gate:"))
async def handle_gate(callback: CallbackQuery):
    _, run_id, action = callback.data.split(":")
    # ... approve/reject ...
    await callback.message.edit_text("Aprovado", reply_markup=None)
    await callback.answer("Gate aprovado")
```

**Alternatives considered**: python-telegram-bot (sincrono, nao asyncio-native), grammY (TypeScript — openclaw usa, mas nos somos Python).

### R-002: Long-Polling + DB Polling — Arquitetura Dual-Loop

**Decision**: Dois loops asyncio concorrentes: (1) aiogram Dispatcher.start_polling() para receber callbacks, (2) asyncio.task periodico que poll `pipeline_runs` para gates pendentes.

**Rationale**: aiogram gerencia o long-polling do Telegram nativamente. O DB polling e uma task asyncio separada com `asyncio.sleep(interval)` entre iteracoes. Ambos rodam no mesmo event loop.

**Pattern**:
```python
async def poll_gates(bot, chat_id, interval=15):
    while True:
        # Query DB for pending unnotified gates
        # Send notification for each
        await asyncio.sleep(interval)

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    # Register handlers...
    
    # Run both concurrently
    async with asyncio.TaskGroup() as tg:
        tg.create_task(dp.start_polling(bot))
        tg.create_task(poll_gates(bot, CHAT_ID))
```

### R-003: Deduplicacao de Notificacoes

**Decision**: Usar coluna `gate_notified_at` ja existente em `pipeline_runs` (migration 007). Ao enviar notificacao, atualizar `gate_notified_at` e armazenar `message_id` do Telegram para editar depois.

**Rationale**: Coluna ja existe. Precisamos adicionar campo para `telegram_message_id` — opcoes: (a) nova coluna em pipeline_runs, (b) tabela separada, (c) campo em JSON no `gate_status`. Escolha: **(a)** — uma migration simples, acesso direto.

### R-004: pyproject.toml — Dependency Management

**Decision**: Criar `pyproject.toml` na raiz do repo com `[project]` section declarativa.

**Rationale**: Padrao moderno Python 3.11+, suporta `pip install -e .`, extensivel. Nao precisa setuptools. Pinagem minima (aiogram >= 3.15) para flexibilidade.

```toml
[project]
name = "madruga-ai"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "aiogram>=3.15",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "ruff>=0.4",
]
```

### R-005: Offset Persistence

**Decision**: Salvar ultimo `update_id` processado na tabela `local_config` (existente) com key `telegram_last_update_id`. Ao iniciar, ler e passar como offset ao polling.

**Rationale**: Reusa infraestrutura existente (set_local_config/get_local_config). Evita reprocessamento de callbacks antigos apos restart.

### R-006: Migration 008 — telegram_message_id

**Decision**: Nova migration `008_telegram_message_id.sql` adicionando coluna `telegram_message_id INTEGER` a `pipeline_runs`.

**Rationale**: Necessario para editar mensagem apos approve/reject. Sem essa coluna, nao sabemos qual mensagem Telegram corresponde a qual gate.

---

## Phase 1: Design

### Data Model

#### Entidades Modificadas

**pipeline_runs** (existente — nova coluna):
| Campo | Tipo | Descricao |
|-------|------|-----------|
| telegram_message_id | INTEGER NULL | ID da mensagem Telegram enviada para este gate |

**local_config** (existente — novas keys):
| Key | Valor | Descricao |
|-----|-------|-----------|
| telegram_last_update_id | INTEGER | Ultimo update_id processado pelo bot |

#### Entidades Novas

**MessagingProvider** (interface abstrata):
```
class MessagingProvider(ABC):
    async send(chat_id, text, parse_mode="HTML") → message_id
    async ask_choice(chat_id, text, choices: list[tuple[str, str]]) → message_id
    async alert(chat_id, text, level: "info"|"warn"|"error") → message_id
```

**TelegramAdapter** (implementacao):
```
class TelegramAdapter(MessagingProvider):
    __init__(bot: aiogram.Bot)
    async send(chat_id, text, parse_mode) → message_id
    async ask_choice(chat_id, text, choices) → message_id  # inline keyboard
    async alert(chat_id, text, level) → message_id  # prefixo visual por nivel
    async edit_message(chat_id, message_id, text, reply_markup=None)
```

#### State Machine — Gate Notification Flow

```
pipeline_runs criado (gate_status=waiting_approval)
    │
    ▼
telegram_bot detecta (gate_notified_at IS NULL)
    │
    ├─ Envia mensagem com inline keyboard
    ├─ Salva telegram_message_id na row
    ├─ Atualiza gate_notified_at
    │
    ▼
Operador toca botao
    │
    ├─ Callback: gate:{run_id}:a → approve_gate()
    │   ├─ Edita mensagem: remove botoes + "Aprovado"
    │   └─ gate_status = approved
    │
    └─ Callback: gate:{run_id}:r → reject_gate()
        ├─ Edita mensagem: remove botoes + "Rejeitado"
        └─ gate_status = rejected
```

### Contracts

#### CLI Interface — telegram_bot.py

```
python3 .specify/scripts/telegram_bot.py [OPTIONS]

Opcoes:
  --poll-interval SECONDS   Intervalo de polling do DB (default: 15)
  --health-interval SECONDS Intervalo de health check (default: 60)
  -v, --verbose             Debug logging
  --dry-run                 Mostra gates pendentes sem enviar

Variaveis de ambiente:
  MADRUGA_TELEGRAM_BOT_TOKEN  Token do bot (@BotFather)
  MADRUGA_TELEGRAM_CHAT_ID    Chat ID do operador
```

#### MessagingProvider Interface

```python
from abc import ABC, abstractmethod

class MessagingProvider(ABC):
    @abstractmethod
    async def send(self, chat_id: int, text: str, **kwargs) -> int:
        """Envia mensagem simples. Retorna message_id."""
        
    @abstractmethod
    async def ask_choice(self, chat_id: int, text: str, choices: list[tuple[str, str]]) -> int:
        """Envia mensagem com opcoes inline. choices: [(label, callback_data), ...]. Retorna message_id."""
        
    @abstractmethod
    async def alert(self, chat_id: int, text: str, level: str = "info") -> int:
        """Envia alerta com indicador visual de severidade. Retorna message_id."""
```

### Message Format (HTML)

```html
<!-- Gate notification -->
<b>Pipeline Gate — Aguardando Aprovacao</b>

<b>Node:</b> <code>vision</code>
<b>Plataforma:</b> madruga-ai
<b>Gate:</b> human
<b>Criado:</b> 2026-04-01 10:30:00

[Aprovar] [Rejeitar]

<!-- After approve -->
<b>Pipeline Gate — Aprovado</b>

<b>Node:</b> <code>vision</code>
<b>Plataforma:</b> madruga-ai
<b>Resolvido:</b> 2026-04-01 10:35:22
<b>Decisao:</b> Aprovado via Telegram

<!-- Alert (error) -->
<b>Pipeline Alert — ERRO</b>

Node <code>implement</code> falhou apos 3 retries.
Erro: timeout after 600s
```

### Alert Level Indicators

| Level | Prefixo |
|-------|---------|
| info | `Pipeline` |
| warn | `Pipeline — ATENCAO` |
| error | `Pipeline Alert — ERRO` |

---

## Constitution Re-Check (Post-Design)

| Principio | Status | Notas |
|-----------|--------|-------|
| VII. TDD | PASS | test_telegram_adapter.py (mocked) + test_telegram_bot.py (real bot) |
| IX. Observability | PASS | structlog em todos os modulos, health check, logging de callbacks |
| I. Pragmatism | PASS | ~300 LOC total, 1 migration, reusa DB existente |

Todos os gates passam. Pronto para `/speckit.tasks`.
