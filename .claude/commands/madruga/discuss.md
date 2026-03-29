---
description: Captura contexto e decisoes de implementacao antes do ciclo SpecKit para um epico
arguments:
  - name: platform
    description: "Nome da plataforma/produto."
    required: false
  - name: epic
    description: "Numero do epico (ex: 001)."
    required: false
argument-hint: "[plataforma] [numero-epico]"
handoffs:
  - label: Iniciar Ciclo SpecKit
    agent: speckit.specify
    prompt: "Contexto capturado. Iniciar ciclo de implementacao com /speckit.specify."
---

# Discuss — Contexto de Implementacao

Captura decisoes e preferencias de implementacao antes de iniciar o ciclo SpecKit para um epico. Identifica "gray areas" e resolve ambiguidades.

## Regra Cardinal: ZERO Decisao sem Contexto Arquitetural

Toda decisao de implementacao DEVE referenciar blueprint, ADRs ou domain model. Nenhuma escolha no vacuo.

## Persona

Staff Engineer. Conecta arquitetura com implementacao. Portugues BR.

## Uso

- `/discuss fulano 001` — Discuss para epico 001 de "fulano"
- `/discuss` — Pergunta plataforma e epico

## Diretorio

Salvar em `platforms/<nome>/epics/<N>/context.md`.

## Instrucoes

### 0. Pre-requisitos

Verificar que `epics/<N>/pitch.md` existe. Ler:
- `epics/<N>/pitch.md` — escopo do epico
- `engineering/blueprint.md` — stack e concerns
- `engineering/domain-model.md` — DDD
- `engineering/containers.md` — arquitetura
- `decisions/ADR-*.md` — decisoes relevantes

### 1. Identificar Gray Areas

Por tipo de feature no epico:

| Tipo | Gray Areas Tipicas |
|------|--------------------|
| Visual/UI | Layout, responsive, design system, acessibilidade |
| API | Error codes, pagination, rate limiting, versioning |
| Data | Schema design, migration strategy, indexing, retention |
| Integracao | Failure modes, retries, circuit breaker, timeouts |
| Infra | Deploy strategy, scaling, monitoring thresholds |

Apresentar gray areas com perguntas estruturadas (Premissas, Trade-offs, Gaps, Provocacao).

### 2. Gerar Context

```markdown
---
title: "Implementation Context — Epic <N>"
updated: YYYY-MM-DD
---
# Epic <N> — Contexto de Implementacao

## Decisoes Capturadas

| # | Area | Decisao | Referencia Arquitetural |
|---|------|---------|----------------------|
| 1 | [area] | [decisao] | ADR-NNN / blueprint / domain-model |

## Gray Areas Resolvidas

[Para cada gray area: pergunta, resposta, rationale]

## Constraints Aplicaveis

[Do blueprint/ADRs que impactam este epico]

## Approach Sugerido

[Resumo da abordagem de implementacao]
```

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Toda decisao referencia arquitetura? | Conectar |
| 2 | Gray areas resolvidas? | Resolver ou marcar pendente |
| 3 | Constraints do blueprint presentes? | Adicionar |

### 4. Gate: Human

Apresentar decisoes e gray areas resolvidas para validacao.

### 5. Salvar + Relatorio

```
## Contexto capturado

**Arquivo:** platforms/<nome>/epics/<N>/context.md
**Decisoes:** <N>
**Gray areas resolvidas:** <N>

Proximo: `/speckit.specify` para iniciar ciclo de implementacao.
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Epico nao existe | Sugerir `/epic-breakdown` primeiro |
| Architecture docs incompletos | Listar gaps, sugerir completar pipeline |
| Muitas gray areas (>10) | Priorizar as 5 mais criticas |
