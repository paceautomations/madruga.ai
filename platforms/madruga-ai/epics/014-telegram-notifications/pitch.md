---
id: 014
title: "Telegram Notifications"
status: shipped
appetite: 2w
priority: 2
delivered_at: 2026-04-01
updated: 2026-04-01
---
# Telegram Notifications

## Problem

Human gates no pipeline requerem aprovacao humana, mas nao ha mecanismo de notificacao. O operador precisa ficar monitorando manualmente se algum gate precisa de atencao. Isso inviabiliza operacao 24/7 e aumenta o tempo de resposta a gates para horas/dias.

## Appetite

**2w** — Depende da gate state machine de 013. aiogram e framework maduro — baixo risco tecnico.

## Dependencies

- Depends on: 013 (gate state machine)
- Blocks: 016 (daemon precisa de notificacoes para operar autonomamente)



## Captured Decisions

| # | Area | Decisao | Referencia Arquitetural |
|---|------|---------|------------------------|
| 1 | Stack | aiogram 3.x + long-polling (nao webhook) | ADR-018 |
| 2 | Interface | `MessagingProvider` abstrato com 3 metodos (`send`, `ask_choice`, `alert`) + `TelegramAdapter` como implementacao | ADR-018, Blueprint 0.0 |
| 3 | Deploy model | Script standalone (`telegram_bot.py`) com polling loop proprio. Daemon 016 refatora para asyncio composavel | ADR-006, pitch 016 |
| 4 | Integracao | Desacoplado via DB — dag_executor grava evento, telegram_bot poll tabela `pipeline_runs` e notifica | ADR-017 (YAML-driven, desacoplado) |
| 5 | Config | `.env` com `MADRUGA_TELEGRAM_BOT_TOKEN` e `MADRUGA_TELEGRAM_CHAT_ID`. `.env.example` com placeholders | Blueprint 1.5 (config), seguranca |
| 6 | Formatacao | HTML mode (nao MarkdownV2) — mais confiavel, sem escaping excessivo | Padrao openclaw/openclaw |
| 7 | Inline keyboards | Callback data: `gate:{run_id}:{action}` (respeitar limite 64 bytes). Editar mensagem apos decisao (remove botoes) | Padrao openclaw/openclaw |
| 8 | Dependency mgmt | `pyproject.toml` com `[project.dependencies]` — aiogram pinado com versao minima | Melhores praticas Python 3.11+ |
| 9 | Fallback ntfy.sh | Adiado para epic 016 — nao infla scope do 014 | ADR-018, pitch 016 |
| 10 | Testes | Bot real de staging (nao mocks) para e2e. Unit tests com mocks para logica de negocio | Principio: zero untested assumptions |

## Resolved Gray Areas

### 1. Scope do epic vs daemon (016)
**Pergunta:** O 014 implementa o polling loop completo ou apenas o adapter?
**Resposta:** Implementa script standalone completo (`telegram_bot.py`) que: faz long-polling, recebe callbacks de approve/reject, atualiza `pipeline_runs` via `approve_gate()`/`reject_gate()`, poll tabela para novos gates pendentes e envia notificacao. **Nao** implementa integracao com daemon asyncio (016).

### 2. Modelo de notificacao (push vs pull)
**Pergunta:** dag_executor chama send() diretamente ou desacoplado via DB?
**Resposta:** Desacoplado (opcao B). O dag_executor grava gate no DB (`gate_status='waiting_approval'`). O `telegram_bot.py` poll a tabela `pipeline_runs` periodicamente e envia notificacao quando detecta gates pendentes nao-notificados (`gate_notified_at IS NULL` ou flag de controle). Isso evita acoplamento executor↔telegram.

### 3. Callback data e limite de 64 bytes do Telegram
**Pergunta:** Como encodar dados no callback sem estourar 64 bytes?
**Resposta:** Formato: `gate:{run_id}:{action}` onde run_id e hex de 4 bytes (8 chars) e action e `a` (approve) ou `r` (reject). Exemplo: `gate:1a2b3c4d:a` = 18 bytes. Margem ampla. Replicar padrao openclaw de validar `fitsCallbackData()` antes de enviar.

### 4. O que acontece apos approve/reject via Telegram
**Resposta:** (a) Chama `approve_gate()` ou `reject_gate()` no DB. (b) Edita mensagem original removendo botoes inline. (c) Atualiza texto com status (ex: "Aprovado por operador via Telegram"). (d) Operador pode retomar pipeline via `dag_executor --resume`.

### 5. Dependency management
**Pergunta:** Criar requirements.txt ou pyproject.toml?
**Resposta:** `pyproject.toml` com `[project]` section. E o padrao moderno Python 3.11+, suporta `pip install .`, e extensivel para futuras deps (structlog, sentry-sdk no 016). Nao precisa de setuptools — e declarativo. Incluir `[project.optional-dependencies]` para dev deps (pytest, ruff).

## Applicable Constraints

| Constraint | Fonte | Impacto no 014 |
|-----------|-------|-----------------|
| Outbound HTTPS only | ADR-018 | Long-polling, sem porta inbound, sem webhook |
| Bot token em .env | Blueprint 1.2, 1.5 | Nenhum secret no repo |
| SQLite WAL single-writer | ADR-012 | telegram_bot.py e dag_executor nao devem escrever simultaneamente sem busy_timeout |
| Circuit breaker | ADR-011 | Aplicar ao polling do Telegram (retry com backoff se getMe falha) |
| gate_status state machine | Epic 013, migration 007 | Respeitar estados: waiting_approval → approved/rejected |

## Padroes do OpenClaw a Replicar

Analise de `github.com/openclaw/openclaw/extensions/telegram/`:

| Padrao | Implementacao no 014 |
|--------|---------------------|
| HTML mode (nao MarkdownV2) | Usar `parse_mode="HTML"` em todas as mensagens |
| Callback data validation (64 bytes) | Validar antes de construir InlineKeyboardButton |
| Editar mensagem apos decisao | `edit_message_reply_markup` para remover botoes + `edit_message_text` para atualizar status |
| Polling com watchdog | Timer que detecta stall no polling loop (>90s sem update) e forca restart |
| Offset persistence | Salvar ultimo update_id no SQLite para evitar duplicatas apos restart |
| Backoff exponencial em errors | Initial 2s, max 30s, fator 1.8x com jitter |

## Suggested Approach

### Arquitetura de arquivos

```
.specify/scripts/
  telegram_bot.py          # Script standalone: polling + handlers + gate integration
  telegram_adapter.py      # MessagingProvider abstrato + TelegramAdapter
  tests/
    test_telegram_adapter.py  # Unit tests com mocks
    test_telegram_bot.py      # Integration tests com bot real

pyproject.toml             # Nova: declaracao de deps (aiogram >= 3.x)
.env.example               # Nova: MADRUGA_TELEGRAM_BOT_TOKEN, MADRUGA_TELEGRAM_CHAT_ID
```

### Fluxo principal

1. **`telegram_adapter.py`** — Interface abstrata `MessagingProvider` com:
   - `send(text, parse_mode)` — envia mensagem simples
   - `ask_choice(text, choices)` — envia com inline keyboard, retorna escolha
   - `alert(text, level)` — envia com formatacao de severidade (info/warn/error)
   - `TelegramAdapter` implementa via aiogram Bot instance

2. **`telegram_bot.py`** — Script standalone:
   - Poll `pipeline_runs` a cada N segundos para gates `waiting_approval` nao-notificados
   - Envia notificacao via `TelegramAdapter.ask_choice()`
   - Recebe callbacks via aiogram Dispatcher (long-polling)
   - Callback handler: `approve_gate()`/`reject_gate()` + edita mensagem
   - Health check: `getMe` a cada 60s. Backoff exponencial em falhas.
   - Offset persistence no SQLite

3. **`pyproject.toml`** — Deps: aiogram >= 3.15, pyyaml. Dev: pytest, ruff.

4. **Testes**: bot real de staging no Telegram, unit tests com mocks para adapter.
