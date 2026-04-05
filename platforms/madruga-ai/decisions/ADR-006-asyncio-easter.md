---
title: 'ADR-006: asyncio Easter 24/7'
status: Accepted
decision: We will use a Python asyncio easter running 24/7 with a slot-based orchestrator,
  polling the Obsidian kanban at regular intervals and executing pipeline phases as
  async tasks.
alternatives: Cron jobs, Serverless (Lambda / Cloud Functions), Celery + Redis
rationale: Processo unico — sem overhead de coordenacao distribuida
---
# ADR-006: asyncio Easter 24/7 para Execucao Autonoma
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O sistema precisa executar pipelines spec-to-code de forma autonoma: monitorar kanban (Obsidian), detectar epics prontos, executar pipeline (specify -> plan -> tasks -> implement), e notificar resultados via Telegram. A execucao precisa ser continua (nao batch), com slot-based scheduling para controlar paralelismo e evitar context rot.

## Decisao

We will use a Python asyncio easter running 24/7 with a slot-based orchestrator, polling the Obsidian kanban at regular intervals and executing pipeline phases as async tasks.

## Alternativas consideradas

### Cron jobs
- Pros: simples, sem estado persistente, padrao Unix, facil de monitorar
- Cons: sem estado entre execucoes (cada run e cold start), nao suporta slot-based scheduling facilmente, granularidade minima de 1 min, nao mantem contexto de pipeline em andamento

### Serverless (Lambda / Cloud Functions)
- Pros: zero ops, auto-scaling, pay-per-use
- Cons: cold start de 5-15s, timeout de 15min (pipeline pode demorar 30min+), sem estado entre invocacoes, custo de egress para claude -p subprocess, vendor lock-in

### Celery + Redis
- Pros: task queue madura, retry nativo, result backend, monitoramento (Flower)
- Cons: overhead significativo (broker + worker + beat), complexidade desnecessaria para single-machine, nao precisamos de distributed tasks

## Consequencias

- [+] Processo unico — sem overhead de coordenacao distribuida
- [+] Slot-based orchestrator controla paralelismo (max N pipelines simultaneos)
- [+] asyncio permite I/O concorrente sem threads (claude -p, Obsidian polling, Telegram)
- [+] Estado em memoria + SQLite — sem dependencia de broker externo
- [-] Single point of failure — se o easter cair, tudo para (mitigado com systemd/supervisord)
- [-] Requer maquina always-on (nao serverless)
- [-] Context rot em pipelines longos — mitigado com waves de subagents frescos (Epic 003)

## Amendment (2026-04-01, Epic 016)

A decisao original referenciava "polling the Obsidian kanban". Com a implementacao do SQLite como state store (Epic 006) e do DAG Executor (Epic 013), o easter agora faz polling na tabela `epics` do SQLite em vez de Obsidian. A arquitetura core (asyncio single-process, slot-based scheduling) permanece inalterada. Implementado como FastAPI app com lifespan + TaskGroup compondo dag_scheduler, Telegram polling (aiogram), health_checker, e gate_poller.
