# Implementation Plan: Easter 24/7

**Branch**: `epic/madruga-ai/016-easter-24-7` | **Date**: 2026-04-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `platforms/madruga-ai/epics/016-easter-24-7/spec.md`

## Summary

Processo persistente 24/7 que orquestra o pipeline Madruga AI automaticamente. Compoe tres modulos existentes (dag_executor, telegram_bot, telegram_adapter) num unico event loop asyncio com FastAPI minimo. Refatora dag_executor para async (create_subprocess_exec), integra Telegram bot como coroutine, adiciona ntfy.sh fallback, Sentry error tracking, e systemd unit file.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, uvicorn, aiogram, structlog, sentry-sdk[fastapi], pyyaml
**Storage**: SQLite WAL mode (.pipeline/madruga.db) — state store, checkpoints, gate status
**Testing**: pytest (make test)
**Target Platform**: WSL2 Ubuntu, systemd service
**Project Type**: easter/service (long-running process)
**Performance Goals**: <10s startup, <5s shutdown, <30s epic detection, <5s gate notification
**Constraints**: single instance, max 3 claude -p concorrentes, localhost only (127.0.0.1:8040), <200MB RAM
**Scale/Scope**: 1 operador, 24 nodes no DAG (13 L1 + 11 L2), ~5-10 epics ativos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Status | Notas |
|-----------|--------|-------|
| I. Pragmatism | PASS | Compoe modulos existentes em vez de reescrever. Refatora cirurgicamente (subprocess.run → create_subprocess_exec). |
| II. Automate | PASS | Este epic E a automacao — easter automatiza o pipeline inteiro. |
| III. Structured Knowledge | PASS | context.md captura decisoes. Plan documenta approach. |
| IV. Fast Action + TDD | PASS | Testes escritos junto com implementacao. Batch para modulos < 300 LOC. |
| V. Alternatives + Trade-offs | PASS | 10 decisoes capturadas em context.md, todas com alternativas e pros/cons. |
| VI. Brutal Honesty | PASS | Riscos documentados (kill criteria: async subprocess pode nao funcionar com claude CLI). |
| VII. TDD | PASS | Testes para: async dispatch, circuit breaker, graceful shutdown, DB polling, ntfy fallback. |
| VIII. Collaborative Decision | PASS | 10 perguntas estruturadas respondidas antes de iniciar. |
| IX. Observability | PASS | structlog JSON em todos os modulos + Sentry auto-instrumentation + /health + /status endpoints. |

**Gate result: PASS** — sem violacoes.

## Project Structure

### Documentation (this feature)

```text
platforms/madruga-ai/epics/016-easter-24-7/
├── pitch.md             # Shape Up pitch (existente)
├── context.md           # Implementation context (gerado)
├── spec.md              # Feature spec (gerado)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
.specify/scripts/
├── easter.py              # NEW — FastAPI entry point + lifespan + signal handling (~200 LOC)
├── dag_executor.py        # MODIFY — refatorar para async (subprocess.run → create_subprocess_exec)
├── telegram_bot.py        # MODIFY — extrair coroutines composáveis, remover entry point standalone
├── telegram_adapter.py    # KEEP — MessagingProvider ABC + TelegramAdapter (sem mudanças)
├── ntfy.py                # NEW — ntfy_alert() standalone (~25 LOC)
├── db.py                  # KEEP — reusa funcoes existentes (get_conn, migrate, approve_gate, etc.)
├── config.py              # KEEP — REPO_ROOT e paths
├── post_save.py           # KEEP — registro de artefatos no SQLite
└── tests/
    ├── test_easter.py          # NEW — testes do easter (startup, shutdown, lifespan)
    ├── test_dag_executor.py    # MODIFY — adicionar testes async
    ├── test_ntfy.py            # NEW — testes do ntfy fallback
    ├── test_sd_notify.py       # NEW — testes do sd_notify
    └── test_telegram_bot.py    # KEEP — testes existentes continuam validos

etc/
└── systemd/
    └── madruga-easter.service  # NEW — systemd unit file
```

**Structure Decision**: Modular — easter.py como orquestrador fino que compoe modulos existentes. Sem novo diretorio — tudo em `.specify/scripts/` (convencao do projeto). Unit file em `etc/systemd/` (convencao Unix).

## Design Decisions

### D1: Async refactor do dag_executor

**Approach**: Mudanca cirurgica — nao reescrever, apenas converter para async.

| Funcao | Antes | Depois |
|--------|-------|--------|
| `dispatch_node()` | `subprocess.run()` bloqueante | `asyncio.create_subprocess_exec()` non-blocking |
| `dispatch_with_retry()` | `time.sleep(backoff)` | `asyncio.sleep(backoff)` |
| `run_pipeline()` | `sys.exit(0)` em human gates | Gravar no SQLite + retornar (easter continua) |
| CLI entry point | `asyncio.run(run_pipeline(...))` | Mantém backward compat sincrono |

**Semaforo**: `asyncio.Semaphore(max_slots)` wrappeia dispatch para limitar concorrencia.

### D2: Composicao do easter via lifespan

```
easter.py
  └── FastAPI app
       └── lifespan context manager
            └── asyncio.TaskGroup
                 ├── dag_scheduler()     — poll epics, dispatch pipelines
                 ├── dp.start_polling()  — aiogram Telegram callbacks
                 ├── gate_poller()       — poll DB, notify via Telegram
                 └── health_checker()    — Telegram API + systemd watchdog
```

**Shutdown flow**: SIGTERM → asyncio.Event set → TaskGroup cancela tasks → subprocesses recebem SIGTERM → await cleanup (max 10s) → exit.

### D3: DAG Scheduler (nova coroutine)

```python
async def dag_scheduler(conn, semaphore, shutdown_event, poll_interval=15):
    while not shutdown_event.is_set():
        epics = poll_active_epics(conn)  # SELECT status='in_progress'
        for epic in epics:
            if not is_running(epic):
                asyncio.create_task(run_pipeline_async(epic, semaphore))
        await asyncio.sleep(poll_interval)
```

**Invariante**: para self-ref, so um epic executa por vez (verificacao antes de create_task).

### D4: Telegram degradation

```
Estado normal → health_check falha 3x → modo degradado
  - auto gates: continuam
  - human gates: pausam (ficam no DB)
  - alertas: ntfy.sh (se configurado) + structlog WARNING
  - health_check continua tentando → Telegram volta → retoma normal
```

### D5: Sentry integration

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.environ.get("MADRUGA_SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.5,
)
```

~10 LOC no startup do easter. Auto-captura exceptions de rotas FastAPI e tasks asyncio.

## Risk Analysis

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| `create_subprocess_exec` nao funciona com claude CLI | Alto | Baixa | Testar primeiro. Se falhar, usar `asyncio.to_thread(subprocess.run, ...)` como fallback. |
| SQLite lock contention com escritas concorrentes | Medio | Baixa | WAL mode + busy_timeout=5000ms. Easter e unico writer na maioria dos cenarios. |
| Memory leak em processo 24/7 | Medio | Media | SC-006 exige 72h sem leak. Monitorar com /status endpoint (RSS). |
| Telegram long-polling interfere com graceful shutdown | Baixo | Media | aiogram Dispatcher.stop() cancela polling. Timeout de 5s no shutdown. |

## LOC Estimates (com multiplicador 1.5x)

| Componente | Base | Realista (1.5x) | Tipo |
|------------|------|-----------------|------|
| easter.py | ~150 | ~225 | NEW |
| dag_executor.py async refactor | ~130 delta | ~200 | MODIFY |
| telegram_bot.py refactor | ~50 delta | ~75 | MODIFY |
| ntfy.py | ~15 | ~25 | NEW |
| madruga-easter.service | ~20 | ~20 | NEW |
| test_easter.py | ~150 | ~225 | NEW |
| test_dag_executor.py delta | ~80 | ~120 | MODIFY |
| test_ntfy.py | ~40 | ~60 | NEW |
| **Total** | **~635** | **~950** | — |

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan completo com 5 design decisions, risk analysis, LOC estimates. Pronto para task breakdown."
  blockers: []
  confidence: Alta
  kill_criteria: "Se create_subprocess_exec nao funcionar com claude CLI, usar asyncio.to_thread como fallback."
