---
id: 015
title: "Subagent Judge + Decision Classifier"
status: planned
appetite: 2w
priority: 2
---
# Subagent Judge + Decision Classifier

## Problem

Specs e artefatos gerados pelo pipeline nao passam por review multi-perspectiva antes de serem aprovados. Nao ha mecanismo automatico para classificar decisoes como 1-way-door vs 2-way-door, nem para detectar problemas antes que cheguem ao human gate.

## Appetite

**2w** — Paralelo com 014. Agent tool ja provado no pipeline. Risco em calibracao de personas/judge.

## Dependencies

- Depends on: 013 (dispatch de subagents via executor)
- Blocks: nenhum
