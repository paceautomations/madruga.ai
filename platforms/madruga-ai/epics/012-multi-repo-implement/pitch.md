---
id: 012
title: "Multi-repo Implement"
status: shipped
appetite: 2w
priority: 1
delivered_at: 2026-03-31
---
# Multi-repo Implement

## Problem

O pipeline so opera no proprio repo (madruga.ai). Para gerar valor real, precisa executar ciclos L2 em repos externos (ex: Fulano). Hoje, `speckit.implement` assume que codigo e docs estao no mesmo repositorio — nao ha mecanismo de repo binding end-to-end.

## Appetite

**2w** — Menor e mais rapido. Value-first: desbloqueia Fulano imediatamente. Repo binding validado end-to-end antes do runtime.

## Dependencies

- Depends on: nenhum (primeiro epic do MVP)
- Blocks: 013 (DAG Executor precisa de multi-repo funcional)
