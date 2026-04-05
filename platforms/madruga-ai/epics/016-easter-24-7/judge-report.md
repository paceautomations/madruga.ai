---
title: "Judge Report — Epic 016 Easter 24/7"
score: 59
verdict: fail
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
updated: 2026-04-01
---
# Judge Report — Epic 016 Easter 24/7

## Score: 59%

**Verdict:** FAIL
**Team:** Tech Reviewers (4 personas)

## Findings

### BLOCKERs (1)

| # | Persona | Finding | Localização | Sugestão |
|---|---------|---------|-------------|----------|
| B1 | arch-reviewer + stress-tester | **Watchdog interval mismatch**: `WatchdogSec=30` no systemd mas `health_checker` envia `WATCHDOG=1` a cada 60s. systemd vai matar o easter ~30s apos startup por timeout. | `etc/systemd/madruga-easter.service:11` + `easter.py:128` (interval=60) | Aumentar `WatchdogSec=120` no service file (recomendado), OU reduzir health_checker interval para 10-15s, OU separar watchdog em coroutine dedicado. |

### WARNINGs (3)

| # | Persona | Finding | Localização | Sugestão |
|---|---------|---------|-------------|----------|
| W1 | simplifier | **`pending_gates_count` morto**: declarado em EasterState e lido em `/status` mas nunca atualizado. Sempre retorna 0. | `easter.py:56, easter.py:349` | Remover campo, ou alimentar a partir do gate_reminder que ja consulta gates pendentes. |
| W2 | simplifier + stress-tester | **CircuitBreaker orfao + sem persistencia**: `EasterState.circuit_breaker` nunca e usado pelo pipeline. O CircuitBreaker real e criado por `run_pipeline_async` a cada execucao — failure state nao persiste entre iteracoes do scheduler. `/status` sempre mostra defaults. | `easter.py:54` + `dag_executor.py:386` | Manter CircuitBreaker por epic_id no easter (dict[str, CircuitBreaker]) e passar como parametro. Remover o campo morto de EasterState. |
| W3 | simplifier | **State passing inconsistente**: health_checker recebe `state` como parametro, mas dag_scheduler e gate_reminder usam `_easter_state` global direto. Mix confuso. | `easter.py` (funcoes diversas) | Escolher um padrao: parametro explicito (testavel) ou global (simples). Nao misturar. |

### NITs (6)

| # | Persona | Finding | Localização | Sugestão |
|---|---------|---------|-------------|----------|
| N1 | bug-hunter + stress-tester | **Conexao SQLite unica compartilhada** entre coroutines. Risco baixo em asyncio single-threaded com fetchall(), mas fragil se refatorado. | `easter.py` lifespan | Documentar invariante single-threaded. Considerar conn-per-operation futuro. |
| N2 | stress-tester | **ntfy_alert bloqueia event loop** com urllib sincrono (ate 5s timeout). | `ntfy.py:8`, chamado de `dag_scheduler` e `health_checker` | Usar `asyncio.to_thread(ntfy_alert, ...)` nos call sites. |
| N3 | stress-tester | **Retry backoff sem jitter** em dispatch_with_retry_async. `RETRY_BACKOFFS = [5, 10, 20]` deterministicos. | `dag_executor.py:313-315` | Adicionar jitter. Risco baixo (single operator, sequencial). |
| N4 | simplifier | **health_checker com 6 parametros**, 3 opcionais (conn, adapter, chat_id). Triple-None check interno. | `easter.py:128` | Simplificar signature. |
| N5 | simplifier | **dag_scheduler faz poll DB mesmo quando epic ja rodando**, so para skipar. | `easter.py:88-101` | Mover check `if _running_epics` para antes do poll. |
| N6 | bug-hunter | **dag_scheduler error loop sem backoff**. Se DB corrupto, spin a cada 15s logando mesmo erro. | `easter.py:122-123` | Adicionar backoff incremental em erros consecutivos. |

### Findings Descartados pelo Judge (4)

| Persona | Finding | Motivo do Descarte |
|---------|---------|-------------------|
| bug-hunter | `_running_epics` race condition | Falso positivo: asyncio single-threaded, set ops sao atomicas no CPython. |
| bug-hunter | `run_pipeline_async` skip silencioso de nodes | Comportamento intencional: scheduler re-polla na proxima iteracao. |
| simplifier | Duplicacao async ~200 LOC no dag_executor | Serve proposito real: CLI sync vs easter async. `asyncio.to_thread` nao permitiria subprocess interleaving. |
| arch-reviewer | Config via env vars vs config.yaml blueprint | MVP: env vars sao padrao 12-factor. config.yaml e melhoria futura, nao violacao. |

## Safety Net — Decisoes 1-Way-Door

Nenhuma decisao 1-way-door escapou. Todas as decisoes do epic 016 foram capturadas em context.md durante `/madruga:epic-context` (10 perguntas estruturadas + respostas). Nenhum evento `decision` nao-aprovado encontrado na tabela events para este epic.

## Personas que Falharam

Nenhuma — 4/4 completaram com sucesso.

## Recomendacoes

### Fixes obrigatorios (resolver antes de merge)

1. **B1 — Watchdog mismatch** (1 linha): Mudar `WatchdogSec=120` em `etc/systemd/madruga-easter.service`.

### Fixes recomendados (resolver antes de merge)

2. **W1 — pending_gates_count morto**: Remover campo de EasterState e de `/status`, ou conectar.
3. **W2 — CircuitBreaker orfao**: Remover de EasterState. Manter breaker per-epic no easter se persistencia necessaria.
4. **W3 — State passing**: Padronizar (global ou parametro explicito).

### Fixes opcionais (podem ir no proximo epic)

5. **N2 — ntfy blocking**: `asyncio.to_thread()` wrapper.
6. **N3 — Jitter no backoff**: Adicionar randomizacao.
7. **N5 — Poll otimizado**: Skip DB query quando epic ja rodando.
8. **N6 — Error backoff no scheduler**: Backoff incremental.
