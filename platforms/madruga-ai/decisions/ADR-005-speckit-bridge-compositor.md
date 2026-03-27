---
title: "ADR-005: SpeckitBridge Compositor"
---
# ADR-005: SpeckitBridge como Compositor de Skills e Templates
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O pipeline spec-to-code usa 13 skills (`.claude/commands/`) e templates (`.specify/templates/`) que precisam ser compostos dinamicamente. O compositor precisa: (1) ler skills e templates do filesystem, (2) montar prompts contextuais com constitution + memory, (3) executar via `claude -p` (subprocess), e (4) manter MECE — cada artefato tem 1 owner, 1 purpose. Precisamos de uma camada que orquestre essa composicao sem hardcodar prompts.

## Decisao

We will use SpeckitBridge as a Python compositor that reads `.claude/commands/` and `.specify/templates/` at runtime, assembling contextual prompts for the Claude API subprocess.

## Alternativas consideradas

### Hardcoded prompts (Python strings)
- Pros: simples, sem indirection, facil de debugar
- Cons: nao escala — cada skill nova requer codigo Python, prompts ficam enterrados em codigo, sem reuso, viola DRY

### Separate agents (multi-agent framework)
- Pros: cada skill e um agent independente, paralelismo nativo, frameworks maduros (LangGraph, CrewAI)
- Cons: complexidade excessiva para nosso caso, overhead de coordenacao inter-agent, context window desperdicado em handoffs, dependencia de framework externo

## Consequencias

- [+] Skills e templates vivem como arquivos editaveis — nao requerem deploy
- [+] Constitution e memory sao injetados automaticamente em cada execucao
- [+] MECE enforced — SpeckitBridge garante que cada artefato tem ownership claro
- [+] Testavel — compositor pode ser unit-tested sem chamar Claude API
- [-] Layer adicional de indirection — debugging requer entender o fluxo SpeckitBridge -> claude -p
- [-] Dependencia de convencao de filesystem (paths especificos para commands/ e templates/)
