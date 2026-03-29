---
description: Verify implementation adherence against spec, tasks, and architecture with a coverage score
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
  - name: epic
    description: "Epic number (e.g., 001)."
    required: false
argument-hint: "[platform] [epic-number]"
handoffs:
  - label: QA Test (optional)
    agent: madruga/test-ai
    prompt: "Verify complete. If app is running, run QA tests with /test-ai."
  - label: Reconcile Documentation
    agent: madruga/reconcile
    prompt: "Skip QA tests. Reconcile documentation with implementation."
---

# Verify — Adherence Verification

Compare implementation against spec (FRs covered?), tasks (phantom completions?), and architecture (drift?). Generate a report with an adherence score.

## Cardinal Rule: ZERO Phantom Completion

If a task is marked [X] but the code does not exist, it is a **BLOCKER**. No task is considered done without filesystem evidence.

## Persona

QA Lead / Auditor. Skeptical, factual. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/verify fulano 001` — Verify epic 001 of platform "fulano"
- `/verify` — Prompt for the platform and epic

## Output Directory

Save to `platforms/<name>/epics/<NNN>/verify-report.md`.

## Instructions

### 0. Prerequisites

Run `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill verify` and parse the JSON output.
- If `ready: false`: ERROR — list missing dependencies.
- If `ready: true`: read artifacts listed in `available`.
- Read `.specify/memory/constitution.md`.

Confirm that spec.md and tasks.md exist for the epic (in the corresponding spec directory).

### 1. Collect Context + Verify

- Read spec.md — extract functional requirements (FR-NNN)
- Read tasks.md — extract tasks and their status ([X] vs [ ])
- Scan the filesystem or git diff — verify implemented code
- Read architecture docs — verify alignment

### 2. Generate Verify Report

All generated content MUST be in PT-BR:

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
| FR-001 | ... | Sim/Nao/Parcial | [file:line] |

## Phantom Completion Check

| Task | Status | Codigo Existe? | Veredicto |
|------|--------|---------------|-----------|
| T001 | [X] | Sim/Nao | OK/PHANTOM |

## Architecture Drift

| Area | Esperado (ADR/Blueprint) | Encontrado | Drift? |
|------|-------------------------|-----------|--------|
| ... | ... | ... | Sim/Nao |

## Blockers
[List of critical problems]

## Warnings
[List of non-critical problems]

## Recomendacoes
[What to do to reach 100%]
```

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Every FR verified? | Verify it |
| 2 | Every task marked [X] has evidence? | Verify it |
| 3 | Drift identified? | Report it |
| 4 | Every decision has >=2 documented alternatives? | Add them |
| 5 | Explicit trade-offs? | Add them |
| 6 | Assumptions marked [VALIDAR] or backed by data? | Mark them |

### 4. Gate: Auto-Escalate

- If score >= 80% AND 0 blockers: **AUTO** — save the report, report success
- If score < 80% OR blockers found: **ESCALATE** — present the report to the user with details

### 5. Save + Report

```
## Verification Complete

**File:** platforms/<name>/epics/<NNN>/verify-report.md
**Lines:** <N>
**Score:** [N]%
**Blockers:** <N>
**Warnings:** <N>
**Phantom completions:** <N>
```

## Error Handling

| Problem | Action |
|---------|--------|
| No spec.md | Suggest `/speckit.specify` |
| No tasks.md | Suggest `/speckit.tasks` |
| No code implemented | Score 0%, list everything as pending |
