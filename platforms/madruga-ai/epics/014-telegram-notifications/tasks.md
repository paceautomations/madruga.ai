# Tasks: Telegram Notifications

**Input**: Design documents from `platforms/madruga-ai/epics/014-telegram-notifications/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: TDD — testes sao incluidos (constitution VII).

**Organization**: Tasks agrupadas por user story para implementacao e teste independentes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependencias)
- **[Story]**: User story correspondente (US1, US2, US3, US4, US5)
- File paths relativos a raiz do repo

---

## Phase 1: Setup

**Purpose**: Inicializacao do projeto e dependencias

- [x] T001 Criar `pyproject.toml` na raiz do repo com dependencies (aiogram>=3.15, pyyaml>=6.0) e optional dev deps (pytest, ruff)
- [x] T002 Criar `.env.example` na raiz do repo com `MADRUGA_TELEGRAM_BOT_TOKEN=` e `MADRUGA_TELEGRAM_CHAT_ID=`
- [x] T003 Criar migration `.pipeline/migrations/008_telegram_message_id.sql` com `ALTER TABLE pipeline_runs ADD COLUMN telegram_message_id INTEGER`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Interface abstrata e adapter Telegram — base para todas as user stories

**CRITICAL**: Nenhuma user story pode comecar sem esta fase completa.

- [x] T004 [P] Escrever testes para MessagingProvider e TelegramAdapter em `.specify/scripts/tests/test_telegram_adapter.py` — testar send(), ask_choice(), alert(), edit_message() com Bot mockado
- [x] T005 Criar interface abstrata `MessagingProvider` (ABC) com metodos send, ask_choice, alert em `.specify/scripts/telegram_adapter.py`
- [x] T006 Implementar `TelegramAdapter` (herda MessagingProvider) em `.specify/scripts/telegram_adapter.py` — Bot instance, HTML parse mode, InlineKeyboardBuilder, edit_message()
- [x] T007 Verificar que migration 008 roda corretamente — executar `python3 -c "from db import get_conn, migrate; conn=get_conn(); migrate(conn)"` e validar coluna `telegram_message_id` existe

**Checkpoint**: Adapter funcional, migration aplicada, testes passando.

---

## Phase 3: User Story 1 — Receber notificacao de gate pendente (Priority: P1) MVP

**Goal**: Operador recebe mensagem no Telegram quando gate fica pendente.

**Independent Test**: Criar gate pendente no DB, iniciar bot, verificar mensagem recebida no Telegram com formato correto dentro de 30s.

### Tests for User Story 1

- [x] T008 [P] [US1] Escrever teste para `poll_pending_gates()` em `.specify/scripts/tests/test_telegram_bot.py` — mock DB com gates pendentes, verificar que retorna gates com gate_notified_at IS NULL
- [x] T009 [P] [US1] Escrever teste para `notify_gate()` em `.specify/scripts/tests/test_telegram_bot.py` — mock TelegramAdapter, verificar que ask_choice() e chamado com texto e botoes corretos, e que telegram_message_id e salvo no DB

### Implementation for User Story 1

- [x] T010 [US1] Implementar `poll_pending_gates(conn, platform_id=None)` em `.specify/scripts/telegram_bot.py` — query `pipeline_runs WHERE gate_status='waiting_approval' AND gate_notified_at IS NULL`
- [x] T011 [US1] Implementar `format_gate_message(gate)` em `.specify/scripts/telegram_bot.py` — formatar mensagem HTML com node, plataforma, gate type, timestamp
- [x] T012 [US1] Implementar `notify_gate(adapter, chat_id, gate, conn)` em `.specify/scripts/telegram_bot.py` — enviar via ask_choice(), salvar telegram_message_id e gate_notified_at no DB
- [x] T013 [US1] Implementar loop `gate_poller(bot, chat_id, interval)` em `.specify/scripts/telegram_bot.py` — asyncio task que chama poll_pending_gates + notify_gate a cada N segundos
- [x] T014 [US1] Implementar `main()` com `asyncio.run()`, leitura de .env, inicializacao de Bot e Dispatcher, e TaskGroup com gate_poller em `.specify/scripts/telegram_bot.py`

**Checkpoint**: Bot roda, detecta gates pendentes, envia notificacao formatada no Telegram.

---

## Phase 4: User Story 2 — Aprovar gate via Telegram (Priority: P1)

**Goal**: Operador toca "Aprovar" no inline keyboard, gate e atualizado no DB, mensagem editada.

**Independent Test**: Com gate notificado, tocar "Aprovar" no Telegram, verificar gate_status=approved no DB e mensagem editada.

### Tests for User Story 2

- [x] T015 [P] [US2] Escrever teste para `handle_gate_callback()` em `.specify/scripts/tests/test_telegram_bot.py` — mock CallbackQuery com data "gate:{run_id}:a", verificar approve_gate() chamado, mensagem editada

### Implementation for User Story 2

- [x] T016 [US2] Implementar `parse_callback_data(data)` em `.specify/scripts/telegram_bot.py` — parsear "gate:{run_id}:{action}", validar formato, retornar (run_id, action)
- [x] T017 [US2] Implementar handler `handle_gate_callback(callback: CallbackQuery)` em `.specify/scripts/telegram_bot.py` — registrar com `dp.callback_query(F.data.startswith("gate:"))`, chamar approve_gate(), editar mensagem removendo botoes e atualizando texto para "Aprovado"
- [x] T018 [US2] Tratar caso de gate ja resolvido — se approve_gate() retorna False, responder com callback.answer("Gate ja resolvido")

**Checkpoint**: Approve funcional end-to-end. Bot + inline keyboard + DB + message edit.

---

## Phase 5: User Story 3 — Rejeitar gate via Telegram (Priority: P2)

**Goal**: Operador toca "Rejeitar", gate atualizado como rejected no DB.

**Independent Test**: Com gate notificado, tocar "Rejeitar", verificar gate_status=rejected no DB.

### Tests for User Story 3

- [x] T019 [P] [US3] Escrever teste para reject path em `handle_gate_callback()` em `.specify/scripts/tests/test_telegram_bot.py` — mock com data "gate:{run_id}:r", verificar reject_gate() chamado

### Implementation for User Story 3

- [x] T020 [US3] Estender `handle_gate_callback()` em `.specify/scripts/telegram_bot.py` para tratar action "r" — chamar reject_gate(), editar mensagem para "Rejeitado"

**Checkpoint**: Approve + reject ambos funcionais.

---

## Phase 6: User Story 4 — Enviar alertas e mensagens de status (Priority: P2)

**Goal**: Sistema envia mensagens informativas (node completo, erro, pipeline completo) sem inline keyboard.

**Independent Test**: Chamar send() e alert() programaticamente, verificar mensagens recebidas formatadas.

### Tests for User Story 4

- [x] T021 [P] [US4] Escrever teste para `format_alert_message()` em `.specify/scripts/tests/test_telegram_adapter.py` — verificar prefixos por nivel (info/warn/error)

### Implementation for User Story 4

- [x] T022 [US4] Implementar logica de prefixo por nivel em `TelegramAdapter.alert()` em `.specify/scripts/telegram_adapter.py` — info: "Pipeline", warn: "Pipeline — ATENCAO", error: "Pipeline Alert — ERRO"
- [x] T023 [US4] Adicionar truncamento de mensagens longas (>4096 chars) em `TelegramAdapter.send()` em `.specify/scripts/telegram_adapter.py`

**Checkpoint**: send(), ask_choice(), alert() todos funcionais com formatacao correta.

---

## Phase 7: User Story 5 — Health check e resiliencia (Priority: P3)

**Goal**: Bot monitora conectividade, retry com backoff, offset persistence.

**Independent Test**: Simular falha de API, verificar retry com backoff. Reiniciar bot, verificar sem reprocessamento.

### Tests for User Story 5

- [x] T024 [P] [US5] Escrever teste para backoff exponencial em `.specify/scripts/tests/test_telegram_bot.py` — verificar delays 2s, 3.6s, 6.5s... ate 30s max
- [x] T025 [P] [US5] Escrever teste para offset persistence em `.specify/scripts/tests/test_telegram_bot.py` — verificar save/load de telegram_last_update_id em local_config

### Implementation for User Story 5

- [x] T026 [US5] Implementar `save_offset(conn, update_id)` e `load_offset(conn)` em `.specify/scripts/telegram_bot.py` — usar set_local_config/get_local_config com key "telegram_last_update_id"
- [x] T027 [US5] Implementar health check periodico em `.specify/scripts/telegram_bot.py` — asyncio task que chama `bot.get_me()` a cada 60s, loga warning em falha
- [x] T028 [US5] Implementar backoff exponencial no polling loop e no health check em `.specify/scripts/telegram_bot.py` — initial 2s, factor 1.8x, jitter 25%, max 30s
- [x] T029 [US5] Integrar offset no startup do Dispatcher em `.specify/scripts/telegram_bot.py` — carregar offset no boot, passar como parametro ao start_polling(), salvar apos cada batch de updates

**Checkpoint**: Bot resiliente — retry, health check, crash recovery.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Qualidade, logging, CLI args

- [x] T030 [P] Adicionar argparse ao `telegram_bot.py` com --poll-interval, --health-interval, --verbose, --dry-run
- [x] T031 [P] Adicionar structlog em todos os modulos (telegram_adapter.py, telegram_bot.py) — log de cada notificacao enviada, callback recebido, health check, erro
- [x] T032 Rodar ruff check + ruff format em todos os arquivos novos
- [x] T033 Teste de integracao end-to-end com bot real — criar gate, verificar notificacao, aprovar via Telegram, verificar DB atualizado
- [x] T034 Atualizar `.github/workflows/` se necessario para instalar aiogram nos testes CI

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependencias — comecar imediatamente
- **Foundational (Phase 2)**: Depende de Setup — BLOQUEIA todas as user stories
- **US1 (Phase 3)**: Depende de Foundational — MVP
- **US2 (Phase 4)**: Depende de US1 (precisa de notify para ter botao)
- **US3 (Phase 5)**: Depende de US2 (estende handle_gate_callback)
- **US4 (Phase 6)**: Depende apenas de Foundational (independente de US1-3)
- **US5 (Phase 7)**: Depende apenas de Foundational (independente de US1-4)
- **Polish (Phase 8)**: Depende de todas as stories desejadas

### User Story Dependencies

- **US1 (P1)**: Foundational → pode iniciar. MVP standalone.
- **US2 (P1)**: US1 → precisa de notify_gate para ter mensagens com botoes
- **US3 (P2)**: US2 → estende o mesmo handler
- **US4 (P2)**: Foundational → independente. Pode rodar em paralelo com US1.
- **US5 (P3)**: Foundational → independente. Pode rodar em paralelo com US1.

### Parallel Opportunities

```
Phase 2: T004 || T007 (testes e migration em paralelo)
Phase 3: T008 || T009 (testes US1 em paralelo)
Phase 4+6: US4 pode rodar em paralelo com US2/US3
Phase 5+7: US5 pode rodar em paralelo com US2/US3
Phase 7: T024 || T025 (testes US5 em paralelo)
Phase 8: T030 || T031 || T034 (polish em paralelo)
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Setup (T001-T003) — ~10 min
2. Foundational (T004-T007) — ~30 min
3. US1 (T008-T014) — ~45 min
4. **STOP e VALIDAR**: Bot detecta gates e envia notificacao no Telegram
5. US2 (T015-T018) — ~30 min
6. **VALIDAR**: Approve funcional end-to-end

### Incremental Delivery

1. Setup + Foundational → Adapter pronto
2. US1 → Bot notifica gates (MVP!)
3. US2 + US3 → Approve/reject bidirecional
4. US4 → Alertas informativos
5. US5 → Resiliencia e crash recovery
6. Polish → Logging, CLI, CI

---

## Notes

- Estimativa total: ~300 LOC de producao + ~150 LOC de testes
- 34 tasks, 8 fases
- TDD: testes escritos antes da implementacao em cada fase
- Commit apos cada checkpoint de fase
