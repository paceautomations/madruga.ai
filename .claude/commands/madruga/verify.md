---
description: Verifica aderencia da implementacao vs spec, tasks e arquitetura com score de cobertura
arguments:
  - name: platform
    description: "Nome da plataforma/produto."
    required: false
  - name: epic
    description: "Numero do epico (ex: 001)."
    required: false
argument-hint: "[plataforma] [numero-epico]"
---

# Verify — Verificacao de Aderencia

Compara implementacao vs spec (FRs cobertos?), vs tasks (phantom completions?), vs arquitetura (drift?). Gera report com score de aderencia.

## Regra Cardinal: ZERO Phantom Completion

Se uma task esta marcada [X] mas o codigo nao existe, e um **BLOCKER**. Nenhuma task considerada done sem evidencia no filesystem.

## Persona

QA Lead / Auditor. Cético, factual. Portugues BR.

## Uso

- `/verify fulano 001` — Verifica epico 001 de "fulano"
- `/verify` — Pergunta plataforma e epico

## Diretorio

Salvar em `platforms/<nome>/epics/<N>/verify-report.md` ou no spec dir do epico.

## Instrucoes

### 0. Pre-requisitos

Verificar que spec.md e tasks.md existem para o epico (no spec dir correspondente).

### 1. Coletar Dados

- Ler spec.md — extrair functional requirements (FR-NNN)
- Ler tasks.md — extrair tasks e status ([X] vs [ ])
- Scan filesystem ou git diff — verificar codigo implementado
- Ler architecture docs — verificar alinhamento

### 2. Gerar Verify Report

```markdown
---
title: "Verify Report — Epic <N>"
updated: YYYY-MM-DD
---
# Verify Report

## Score: [N]%

## Coverage Matrix

| FR | Descricao | Implementado? | Evidencia |
|----|-----------|--------------|-----------|
| FR-001 | ... | Sim/Nao/Parcial | [arquivo:linha] |

## Phantom Completion Check

| Task | Status | Codigo Existe? | Veredicto |
|------|--------|---------------|-----------|
| T001 | [X] | Sim/Nao | OK/PHANTOM |

## Architecture Drift

| Area | Esperado (ADR/Blueprint) | Encontrado | Drift? |
|------|-------------------------|-----------|--------|
| ... | ... | ... | Sim/Nao |

## Blockers
[Lista de problemas criticos]

## Warnings
[Lista de problemas nao-criticos]

## Recomendacoes
[O que fazer para atingir 100%]
```

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Todo FR verificado? | Verificar |
| 2 | Toda task [X] tem evidencia? | Verificar |
| 3 | Drift identificado? | Reportar |

### 4. Gate: Auto-Escalate

- Se score >= 80% E 0 blockers → **AUTO**: salvar report, reportar sucesso
- Se score < 80% OU blockers encontrados → **ESCALATE**: apresentar report ao usuario com detalhes

### 5. Salvar + Relatorio

```
## Verificacao completa

**Score:** [N]%
**Blockers:** <N>
**Warnings:** <N>
**Phantom completions:** <N>
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Sem spec.md | Sugerir `/speckit.specify` |
| Sem tasks.md | Sugerir `/speckit.tasks` |
| Sem codigo implementado | Score 0%, listar tudo como pendente |
