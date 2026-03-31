---
description: Interactive onboarding — detect platforms, explain pipeline, recommend next step
arguments: []
argument-hint: ""
---

# Getting Started — Onboarding

Lightweight interactive skill. Detects the current state of the repository and guides the user through the development process.

## Persona

Onboarding guide — immediate action, zero unnecessary theory. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Instructions

### 1. Detect Current State

Run `python3 .specify/scripts/platform.py list` to detect existing platforms.

### 2. If No Platforms Exist

```
Nenhuma plataforma encontrada.

Para comecar, crie sua primeira plataforma:
  /madruga:platform-new <nome-em-kebab-case>

Exemplo: /madruga:platform-new meu-saas
```

### 3. If Platforms Exist

For each platform, run:
```
bash .specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --status
```

Present a summary table:

```
## Plataformas Detectadas

| Plataforma | Lifecycle | Pipeline | Proximo Passo |
|-----------|-----------|----------|--------------|
| fulano | design | 7/13 (54%) | /madruga:business-process fulano |
| madruga-ai | development | 11/13 (85%) | /madruga:business-process madruga-ai |
```

### 4. Explain the Pipeline

```
## Como Funciona o Pipeline

O pipeline documenta plataformas em 4 fases sequenciais:

### Fase 1: Negocio (~2h)
platform-new → vision → solution-overview → business-process
- Define O QUE o produto faz e PARA QUEM

### Fase 2: Pesquisa (~1h)
tech-research + codebase-map (opcional)
- Pesquisa alternativas tecnologicas

### Fase 3: Engenharia (~3h)
adr → blueprint → domain-model → containers → context-map
- Define COMO o sistema funciona (DDD, C4, ADRs)

### Fase 4: Planejamento (~1h)
epic-breakdown → roadmap
- Define QUANDO entregar (epics Shape Up)

### Ciclo por Epic (~2-4h cada)
epic-context (cria branch) → specify → plan → tasks → implement → verify → reconcile → PR/merge
IMPORTANTE: cada epic roda em branch dedicada `epic/<platform>/<NNN-slug>`

Tempo total estimado: ~7h para pipeline completo + 2-4h por epic.
```

### 5. Namespaces

```
## Comandos Disponiveis

**Pipeline (madruga:)** — documentacao da plataforma:
  /madruga:pipeline, /madruga:vision, /madruga:solution-overview, /madruga:business-process,
  /madruga:tech-research, /madruga:adr, /madruga:blueprint, /madruga:domain-model,
  /madruga:containers, /madruga:context-map, /madruga:epic-breakdown, /madruga:roadmap

**Epic Cycle (speckit.)** — implementacao por epic:
  /speckit.specify, /speckit.plan, /speckit.tasks,
  /speckit.implement, /speckit.analyze

**Utilitarios:**
  /madruga:pipeline <nome> — ver status a qualquer momento
  /madruga:checkpoint — salvar progresso da sessao
  /madruga:verify — verificar aderencia
  /madruga:qa — testar via Playwright
  /madruga:reconcile — detectar drift
```

### 6. Recommend Next Step

Based on the pipeline status, recommend the single most impactful next action.

