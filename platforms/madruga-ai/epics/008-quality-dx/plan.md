---
title: "Plan — Epic 008: Quality & DX"
updated: 2026-03-29
---
# Plan — Quality & Developer Experience

## Technical Context

- **Stack**: Markdown (knowledge files, skill files). Zero código novo.
- **Linguagem dos knowledge files**: Inglês (instruções para LLM, não artefatos de documentação)
- **Arquivos afetados**: 4 knowledge files novos, 1 knowledge file editado (pipeline-dag-knowledge.md), 1 novo (likec4-syntax.md), 13+ skills editadas
- **Dependências**: Epic 006 (db.py existe), Epic 007 (skills renomeadas, HANDOFF blocks existem)

## Constitution Check

| Princípio | Status | Impacto |
|-----------|--------|---------|
| I. Pragmatismo | OK | Knowledge files são a solução mais simples para deduplicação |
| II. Automatizar | OK | Nenhum script novo necessário |
| IV. Ação rápida | OK | Markdown puro, sem build step |
| VII. TDD | N/A | Sem código, sem testes |
| VIII. Decisão colaborativa | OK | Decisões já capturadas em context.md |

## Architecture

### Knowledge File Structure

```
.claude/knowledge/
  pipeline-dag-knowledge.md          (EXISTENTE — editar §4 personas)
  pipeline-contract-base.md          (NOVO — steps 0,1,3,4,5 genéricos)
  pipeline-contract-business.md      (NOVO — persona + regras business layer)
  pipeline-contract-engineering.md   (NOVO — persona + regras engineering layer)
  pipeline-contract-planning.md      (NOVO — persona + regras planning layer)
  likec4-syntax.md                   (NOVO — referência de syntax LikeC4)
```

### Contract-Base Structure

```markdown
# Pipeline Contract — Base

## Step 0: Prerequisites
[check-platform-prerequisites.sh pattern]
[constitution.md read]

## Step 1: Collect Context + Ask Questions
[Structured Questions framework — 4 categories]
[Read dependency artifacts]
[Wait for answers BEFORE generating]

## Step 3: Auto-Review
### Tier 1 — Auto Gates
[Checks executáveis: grep, wc, file existence]

### Tier 2 — Human Gates
[Tier 1 + scorecard for human review]

### Tier 3 — 1-Way-Door Gates
[Tier 1 + Tier 2 + subagent adversarial review]

## Step 4: Approval Gate
[Gate behavior by type]

## Step 5: Save + Report
[Save artifact]
[SQLite integration — if DB exists]
[Report format]
[HANDOFF block]
```

### Skill Refactor Pattern

**Before (inline):**
```markdown
## Instructions
### 0. Prerequisites
Run `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill <id>`
[...20 linhas...]

### 3. Auto-Review
| # | Check | Action on Failure |
[...10 linhas...]

### 4. Gate: Human
Present summary + decisions...
[...5 linhas...]

### 5. Save + Report
[...15 linhas...]
```

**After (reference):**
```markdown
> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-engineering.md`. Overrides below.

## Instructions
### 1. Collect Context
[Artifact-specific context collection]

### 2. Generate <Artifact>
[Artifact-specific generation]

### Auto-Review Additions
[Only artifact-specific checks beyond contract-base]
```

### Layer-to-Skills Mapping

| Layer | Contract File | Skills |
|-------|--------------|--------|
| business | pipeline-contract-business.md | vision, solution-overview, business-process, platform-new |
| research | (uses base only) | tech-research, codebase-map |
| engineering | pipeline-contract-engineering.md | adr, blueprint, domain-model, containers, context-map |
| planning | pipeline-contract-planning.md | epic-breakdown, roadmap |
| utility | (uses base partially) | pipeline, checkpoint, epic-context, verify, reconcile, qa |

## Phases

### Phase 1: Create Knowledge Files (4 new + 1 edit)
- Create pipeline-contract-base.md
- Create pipeline-contract-business.md
- Create pipeline-contract-engineering.md
- Create pipeline-contract-planning.md
- Create likec4-syntax.md
- Edit pipeline-dag-knowledge.md §4 (personas)

### Phase 2: Refactor Skills
- Update 13 DAG skills to reference contract files
- Remove inline boilerplate (steps 0,3,4,5)
- Keep artifact-specific content
- Update utility skills partially

### Phase 3: Validate
- Count lines per skill — verify ≥30% reduction
- Grep validation — contract references present
- Grep validation — zero orphaned inline boilerplate

---
handoff:
  from: plan
  to: tasks
  context: "Plan completo. 6 novos/editados knowledge files + 13+ skills refatoradas. Zero código, apenas markdown."
  blockers: []
