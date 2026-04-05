---
id: 016
title: "Easter 24/7"
status: shipped
delivered_at: 2026-04-01
appetite: 2w
priority: 3
updated: 2026-04-01
---
# Easter 24/7

## Problem

O pipeline so executa quando um humano invoca skills manualmente no terminal. Nao existe processo persistente que monitore o estado do DAG, dispare skills quando prerequisites sao atendidos, e opere continuamente. Sem easter, a promessa de autonomia do pipeline e impossivel.

## Appetite

**2w** — Ultimo epic do MVP. Monta em cima de tudo. Mecanico: asyncio event loop + health checks + systemd.

## Dependencies

- Depends on: 014 (notificacoes para gates), 013 (DAG executor)
- Blocks: nenhum (ultimo epic do MVP)

## Implementation Notes

- **Polling loop do Telegram**: epic 014 entrega `telegram_bot.py` como script standalone. O easter 016 deve refatorar para integrar o polling como coroutine asyncio composavel dentro do event loop principal.
- **Fallback ntfy.sh**: ADR-018 define ntfy.sh como fallback quando Telegram API esta unreachable. Implementar neste epic (~15-20 LOC, HTTP POST simples).



## Captured Decisions

| # | Area | Decisao | Referencia Arquitetural |
|---|------|---------|------------------------|
| 1 | Runtime | FastAPI minimo em 127.0.0.1:8040 com lifespan context manager para background tasks. Endpoints: GET /health (systemd watchdog), GET /status (pipeline state JSON). | ADR-006 (asyncio easter), ADR-016 (Sentry auto-instrumentacao FastAPI), blueprint §3.1 |
| 2 | DAG Executor | Refatorar `dag_executor.py` de sincrono para async: `subprocess.run()` → `asyncio.create_subprocess_exec()`, `time.sleep()` → `asyncio.sleep()`, `sys.exit()` em gates → sinalizacao via `asyncio.Event`. Mudanca cirurgica, sem reescrita completa. | ADR-017 (custom DAG executor), blueprint §Q9 |
| 3 | Telegram Bot | Absorver `telegram_bot.py` como coroutine composavel no TaskGroup do easter. aiogram Dispatcher + gate poller + health check rodam como tasks concorrentes. Script standalone deixa de existir como entry point separado. | ADR-018 (Telegram Bot), blueprint §3.1 |
| 4 | Concorrencia | Epics sequenciais para self-ref (madruga-ai). `asyncio.Semaphore(max_slots=3)` para sessoes `claude -p` concorrentes. | pipeline-dag-knowledge.md §8 "Parallel Epics Constraint", blueprint §Q9 |
| 5 | Epic Trigger | DB polling na tabela `epics`: easter monitora epics com status `in_progress` a cada N segundos. Trigger (mudanca de status) pode vir de CLI, Telegram, ou qualquer interface futura. ~20 LOC. | ADR-006 (polling pattern), telegram_bot.py (mesmo pattern de gate polling) |
| 6 | Estrutura | Modular: `easter.py` (entry point + FastAPI lifespan + signal handling, ~150-200 LOC) compoe modulos existentes. dag_executor refatorado para async. telegram_bot absorvido como coroutine. | ADR-006, blueprint §3.1 |
| 7 | Fallback ntfy.sh | Funcao standalone `ntfy_alert(topic, msg)` (~15 LOC, HTTP POST). Sem polimorfismo — ntfy e unidirecional, nao suporta ask_choice. Ativa quando Telegram unreachable por 3+ health checks. | ADR-018 §fallback |
| 8 | Configuracao | Env vars (MADRUGA_*) para todas as settings do easter. Sem config.yaml neste epic. ~8 settings: bot token, chat ID, poll interval, max slots, executor timeout, health interval, ntfy topic, sentry DSN. | blueprint §1.5, convencao existente |
| 9 | Observabilidade | Sentry incluido neste epic (~10 LOC). `sentry_sdk.init(dsn=..., integrations=[FastApiIntegration()])`. Auto-captura de exceptions, breadcrumbs, performance traces. | ADR-016 (Sentry free tier) |
| 10 | systemd | Unit file com Type=notify, WatchdogSec=30, Restart=on-failure, RestartSec=5. Health check loop envia sd_notify("WATCHDOG=1") periodicamente. | ADR-006 (always-on, systemd/supervisord) |

## Resolved Gray Areas

### 1. FastAPI vs pure asyncio

**Pergunta:** O easter precisa de HTTP server ou basta asyncio puro?

**Resposta:** FastAPI minimo. O ganho de Sentry auto-instrumentacao (ADR-016), health check HTTP para systemd, e status endpoint para portal justificam os ~10MB RAM extras. Bind exclusivo em 127.0.0.1 elimina risco de seguranca.

**Alternativa rejeitada:** Pure asyncio — economiza ~5MB RAM mas perde Sentry auto-instrumentation e requer health check customizado para systemd (PID check, menos confiavel).

### 2. Estrutura monolitica vs modular

**Pergunta:** Um arquivo easter.py grande ou composicao de modulos?

**Resposta:** Modular. dag_executor (507 LOC) e telegram_bot (536 LOC) ja existem e sao testados. O easter e um orquestrador fino (~150-200 LOC) que compoe esses modulos via asyncio.TaskGroup. Testabilidade: scheduler isolado permite testar logica de slots e backoff sem levantar FastAPI/Telegram.

### 3. ntfy.sh como MessagingProvider vs funcao standalone

**Pergunta:** ntfy.sh deve implementar a ABC MessagingProvider?

**Resposta:** Nao. ntfy.sh e unidirecional — implementar MessagingProvider geraria 3 metodos com `raise NotImplementedError` (ask_choice, edit_message, alert com level). Funcao standalone `ntfy_alert()` e honesta sobre a capacidade real. Menos codigo no path de degradacao = menos superficie de bug.

### 4. config.yaml vs env vars

**Pergunta:** Criar config.yaml para settings do easter?

**Resposta:** Env vars. Ja e a convencao (MADRUGA_TELEGRAM_BOT_TOKEN, etc.), sao ~8 settings, e secrets (bot token, Sentry DSN) devem ficar em env vars (nao em arquivo commitado). Se crescer para 15+ settings, migrar para pydantic-settings (le env vars E yaml). YAGNI.

### 5. Sentry agora ou depois

**Pergunta:** Incluir sentry-sdk neste epic ou deferrir?

**Resposta:** Agora. Sao ~10 LOC, o easter e o processo primario que precisa de error tracking, e as primeiras semanas de operacao sao quando bugs sao mais provaveis. Deferrir = rodar cego.

## Applicable Constraints

### Do Blueprint

- **Single instance**: easter, DAG executor, Telegram bot — todos single instance (blueprint §3.1)
- **Max 3 claude -p concorrentes**: semaforo asyncio (blueprint §Q9)
- **SQLite WAL mode**: busy_timeout=5000ms, single writer, N readers (blueprint §Q6)
- **structlog**: logging estruturado JSON em todos os modulos (ADR-016)
- **Error handling**: watchdog timer com SIGKILL, retry 3x backoff exponencial, circuit breaker 5 falhas/300s recovery (blueprint §1.4)

### Dos ADRs

- **ADR-006**: asyncio easter, slot-based orchestrator, estado em memoria + SQLite
- **ADR-010**: claude -p subprocess, --output-format json, --allowedTools whitelist
- **ADR-011**: circuit breaker separado para epics/actions, 5 falhas, 5min recovery
- **ADR-013**: decision gates 1-way/2-way, classificacao automatica, ADR auto-gerado para 1-way
- **ADR-017**: YAML como source of truth, DAG executor 500-800 LOC, human gates via SQLite + Telegram + resume
- **ADR-018**: Telegram outbound HTTPS only, long-polling, inline keyboard, fallback ntfy.sh

### Do Pipeline DAG Knowledge

- **Epics sequenciais para self-ref**: NEVER parallel para madruga-ai (§8)
- **Branch guard**: todo skill L2 verifica `git branch --show-current` (§8)

## Suggested Approach

### Fase 1: Refatorar dag_executor para async (~200 LOC de delta)

1. `subprocess.run()` → `asyncio.create_subprocess_exec()` em `dispatch_node()`
2. `time.sleep()` → `asyncio.sleep()` em `dispatch_with_retry()`
3. Human gates: em vez de `sys.exit(0)`, gravar no SQLite e retornar (o easter continua rodando)
4. `run_pipeline()` → `async def run_pipeline()` com `asyncio.Semaphore(max_slots)`
5. Manter backward compatibility: CLI sincrono wrappeia com `asyncio.run()`

### Fase 2: Easter entry point (~150-200 LOC)

1. `easter.py` com FastAPI app + lifespan context manager
2. Lifespan: inicia TaskGroup com 4 tasks:
   - DAG scheduler (poll epics, dispatch pipelines)
   - Telegram Dispatcher (aiogram polling)
   - Gate poller (poll DB, notify via Telegram)
   - Health checker (Telegram API + systemd watchdog)
3. Endpoints: GET /health, GET /status
4. Signal handling: SIGTERM/SIGINT → graceful shutdown via asyncio.Event
5. Sentry init no startup

### Fase 3: ntfy.sh fallback + systemd (~50 LOC)

1. `ntfy_alert(topic, msg)` — HTTP POST fire-and-forget
2. Health checker: apos 3 falhas Telegram → modo log-only + ntfy alerts
3. systemd unit file: Type=notify, WatchdogSec=30, Restart=on-failure
4. sd_notify("WATCHDOG=1") no health check loop

### Estimativa LOC (com multiplicador 1.5x)

| Componente | Base | Realista (1.5x) |
|------------|------|-----------------|
| dag_executor async refactor | ~130 LOC delta | ~200 LOC |
| easter.py (entry point) | ~150 LOC | ~225 LOC |
| ntfy fallback | ~15 LOC | ~25 LOC |
| systemd unit | ~20 linhas | ~20 linhas |
| Testes | ~200 LOC | ~300 LOC |
| **Total** | **~515 LOC** | **~770 LOC** |

handoff:
  from: madruga:epic-context
  to: speckit.specify
  context: "Gerar spec detalhada do easter 24/7: FastAPI minimo, dag_executor async, telegram_bot composavel, ntfy fallback, systemd. Decisoes capturadas em context.md."
  blockers: []
  confidence: Alta
  kill_criteria: "Se dag_executor async se provar inviavel (ex: claude -p nao funciona com create_subprocess_exec), repensar arquitetura."
