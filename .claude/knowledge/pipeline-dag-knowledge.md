# Pipeline DAG Knowledge

Reference knowledge file for the madruga.ai pipeline DAG system.
Skills reference this file to understand node dependencies, gate types, personas, and the uniform contract.

---

## 1. Canonical DAG (14 nodes)

| ID | Skill | Outputs | Depends | Layer | Gate | Optional |
|----|-------|---------|---------|-------|------|----------|
| platform-new | madruga:platform-new | platform.yaml | — | business | human | no |
| vision | madruga:vision-one-pager | business/vision.md | platform-new | business | human | no |
| solution-overview | madruga:solution-overview | business/solution-overview.md | vision | business | human | no |
| business-process | madruga:business-process | business/process.md | solution-overview | business | human | no |
| tech-research | madruga:tech-research | research/tech-alternatives.md | business-process | research | 1-way-door | no |
| codebase-map | madruga:codebase-map | research/codebase-context.md | vision | research | auto | YES |
| adr-gen | madruga:adr-gen | decisions/ADR-*.md (output_pattern) | tech-research | engineering | 1-way-door | no |
| blueprint | madruga:blueprint | engineering/blueprint.md | adr-gen | engineering | human | no |
| folder-arch | madruga:folder-arch | engineering/folder-structure.md | blueprint | engineering | human | no |
| domain-model | madruga:domain-model | engineering/domain-model.md, model/ddd-contexts.likec4 | blueprint, business-process | engineering | human | no |
| containers | madruga:containers | engineering/containers.md, model/platform.likec4 | domain-model, blueprint | engineering | human | no |
| context-map | madruga:context-map | engineering/context-map.md | domain-model, containers | engineering | human | no |
| epic-breakdown | madruga:epic-breakdown | epics/*/pitch.md (output_pattern) | domain-model, containers, context-map | planning | 1-way-door | no |
| roadmap | madruga:roadmap | planning/roadmap.md | epic-breakdown | planning | human | no |

---

## 2. Skill Uniform Contract

Every skill MUST follow this 6-section structure:

```markdown
---
description: <1 linha PT-BR>
arguments:
  - name: platform
    description: "Nome da plataforma"
    required: false
argument-hint: "[nome-da-plataforma]"
handoffs:
  - label: <next skill label>
    agent: madruga/<next>
    prompt: <context for handoff>
---

# <Nome> — <Subtitulo>

## Regra Cardinal
<What this skill NEVER does. Negative constraint.>

## Persona
<Who the AI simulates. Specific expertise.>

## Uso
- `/<skill-name> <platform>` — Direct mode
- `/<skill-name>` — Interactive mode

## Diretorio
Salvar em `platforms/<nome>/<path>`.

## Instrucoes

### 0. Pre-requisitos
Rodar: `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill <id>`
Se NOT ready: ERROR com deps faltantes e qual skill gera cada um.
Se ready: ler todos artefatos em `available`.
Ler `.specify/memory/constitution.md`.

### 1. Coletar Contexto + Questionar
- Ler artefatos de dependencia
- Identificar premissas implicitas
- Deep research (subagents, Context7, web)
- Perguntas Estruturadas:
  - **Premissas**: "Assumo que X. Correto?"
  - **Trade-offs**: "A (simples) ou B (robusto)?"
  - **Gaps**: "Falta info sobre X. Voce define ou eu pesquiso?"
  - **Provocacao**: "Y e padrao, mas Z pode ser melhor porque..."
- Apresentar alternativas (>=2 opcoes com pros/cons)
- Aguardar respostas ANTES de gerar

### 2. Gerar <Artefato>
- Seguir template se existir
- Incluir alternativas consideradas
- Marcar [VALIDAR] onde nao tem dado
- PT-BR para prosa, EN para codigo

### 3. Auto-Review
| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Toda decisao tem >=2 alternativas? | Adicionar |
| 2 | Toda premissa tem [VALIDAR] ou dado? | Marcar |
| 3 | Pesquisou best practices recentes? | Research |
| 4 | Trade-offs explicitos? | Adicionar pros/cons |
| 5 | [Checks especificos do artefato] | ... |

### 4. Gate de Aprovacao
Se gate=human: Apresentar resumo + decisoes + perguntas de validacao.
Se gate=1-way-door: Listar CADA decisao com >=3 alternativas, pedir confirmacao EXPLICITA.
Aguardar aprovacao antes de salvar.

### 5. Salvar + Relatorio
Arquivo: platforms/<nome>/<path>
Linhas: <N>
Checks: [x] ...
Proximo passo: /<next-skill> <nome>
```

---

## 3. Gate Types

| Type | Behavior | When Pauses | Examples |
|------|----------|-------------|----------|
| human | Always pause for approval | Always | vision, blueprint, DDD |
| auto | Never pause, proceed automatically | Never | codebase-map, checkpoint |
| 1-way-door | Always pause, even in autonomous mode | Always, with per-decision confirmation | tech-research, adr-gen, epic-breakdown |
| auto-escalate | Auto if OK, escalate if blockers | Only when problems detected | verify |

### 1-way-door details

- List every irreversible decision
- For each: >=3 alternatives with pros/cons/recommendation
- Require explicit confirmation per decision
- "Confirma [decisao X]? Isso define [Y] para o resto do projeto."

---

## 4. Personas por Layer

| Layer | Persona | Focus |
|-------|---------|-------|
| Business | Estrategista Bain/McKinsey | Desafiar premissas, quantificar, marcar [VALIDAR] |
| Research | Analista de Pesquisa Tech Senior | Deep research paralelo, >=3 alternativas por decisao |
| Engineering | Staff Engineer 15+ anos | Simplicidade, "e a coisa mais simples que funciona?" |
| Planning | Product Manager / Architect | Shape Up, scope definition, roadmap sequencing |

---

## 5. Structured Questions Framework

Every skill with gate: human presents questions in 4 categories:

1. **Premissas** (what I'm assuming): "Assumo que [X]. Correto?"
2. **Trade-offs** (decisions with impact): "[A] mais simples ou [B] mais robusto?"
3. **Gaps** (missing info): "Nao encontrei [X]. Voce define ou eu pesquiso?"
4. **Provocacao** (challenge the obvious): "[Y] e padrao, mas [Z] pode ser melhor porque [razao]."

---

## 6. Auto-Review Checklist Template

Every skill's auto-review MUST include these universal checks plus artifact-specific ones:

| # | Check | Applies to |
|---|-------|-----------|
| 1 | Every decision has >=2 alternatives documented | All |
| 2 | Every assumption marked [VALIDAR] or backed by data | All |
| 3 | Best practices researched (2025-2026) | Business + Engineering |
| 4 | Trade-offs explicit (pros/cons) | All |
| 5 | Zero technical terms in business artifacts | Business only |
| 6 | Mermaid/LikeC4 diagrams included where applicable | Engineering |
| 7 | Max line count respected | All |

---

## 7. Handoff Examples

```yaml
# vision -> solution-overview
handoffs:
  - label: Generate Solution Overview
    agent: madruga/solution-overview
    prompt: Generate solution overview based on validated vision

# solution-overview -> business-process
handoffs:
  - label: Map Business Process
    agent: madruga/business-process
    prompt: Map core business processes from validated solution overview

# business-process -> tech-research (with 1-way-door warning)
handoffs:
  - label: Research Tech Alternatives
    agent: madruga/tech-research
    prompt: "Research technology alternatives. WARNING: This is a 1-way-door gate — technology choices constrain all downstream architecture."

# tech-research -> adr-gen (with 1-way-door warning)
handoffs:
  - label: Generate ADRs
    agent: madruga/adr-gen
    prompt: "Generate Architecture Decision Records from validated tech research. WARNING: 1-way-door — ADRs define the technical foundation."

# adr-gen -> blueprint
handoffs:
  - label: Generate Blueprint
    agent: madruga/blueprint
    prompt: Generate engineering blueprint based on approved ADRs

# blueprint -> folder-arch
handoffs:
  - label: Define Folder Architecture
    agent: madruga/folder-arch
    prompt: Define folder structure based on approved blueprint

# domain-model -> containers
handoffs:
  - label: Define Containers
    agent: madruga/containers
    prompt: Define container architecture from domain model and blueprint

# context-map -> epic-breakdown (with 1-way-door warning)
handoffs:
  - label: Break into Epics (Shape Up)
    agent: madruga/epic-breakdown
    prompt: "Break project into epics. WARNING: This is a 1-way-door gate — epic scope decisions define everything downstream."

# epic-breakdown -> roadmap
handoffs:
  - label: Build Roadmap
    agent: madruga/roadmap
    prompt: Sequence epics into delivery roadmap based on dependencies and risk
```
