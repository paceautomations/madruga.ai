---
id: 013
title: "DAG Executor + SpeckitBridge"
status: shipped
appetite: 6w
priority: 1
delivered_at: 2026-03-31
---
# DAG Executor + SpeckitBridge

## Problem

O pipeline hoje e invocado manualmente skill por skill. Nao existe runtime que execute o DAG automaticamente, respeite gates, gerencie estado de execucao, ou faca dispatch de skills via `claude -p`. Sem isso, o pipeline nao pode operar autonomamente.

## Appetite

**6w** — Core do runtime. Maior incerteza tecnica (DAG executor, gate state machine, claude -p dispatch). Absorver risco cedo.

## Dependencies

- Depends on: 012 (multi-repo precisa estar funcional)
- Blocks: 014 (gate state machine necessaria para notificacoes), 015 (dispatch necessario para subagent judge)
