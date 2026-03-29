---
description: Detect drift between implementation and documentation and propose updates
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Check Pipeline Status
    agent: madruga/pipeline
    prompt: "Documentation updated. Check pipeline status."
---

# Reconcile — Drift Detection and Correction

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

Compare implementation (git diff / PR) with architecture documentation. Identify drift and propose updates to affected docs.

## Cardinal Rule: ZERO Silent Drift

Every deviation between implementation and documentation must be made explicit. No architecture change can exist without a corresponding doc update.

## Persona

Architect / Documentation Guardian. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/reconcile fulano` — Reconcile "fulano" post-implementation
- `/reconcile` — Prompt for platform

## Output Directory

Update existing docs in `platforms/<name>/`. Report saved to `reconcile-report.md`.

## Instructions

### 1. Collect Context + Detect Drift

Read:
- `git diff` or recent `git log`
- `business/*` — vision, solution-overview, process
- `engineering/*` — blueprint, domain-model, containers, context-map
- `model/*.likec4` — LikeC4 models

**Drift categories:**

| Category | How to Detect |
|----------|--------------|
| Scope drift | Implemented features not in solution-overview |
| Architecture drift | Implementation diverges from blueprint/ADRs |
| Model drift | Containers/contexts changed but LikeC4 not updated |
| Domain drift | New entities/aggregates not in domain-model |

**Structured Questions:**

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume the change in [X] was intentional. Correct?" |
| **Trade-offs** | "Update docs now (complete) or mark for next sprint (fast)?" |
| **Gaps** | "I am not sure if the change in [X] affects [doc Y]. Verify?" |
| **Challenge** | "Drift in [area] may indicate the original ADR needs revision." |

Wait for answers BEFORE proposing updates.

### 2. Propose Updates

For each detected drift, generate a structured proposal:

| # | Drift | Affected Doc | Proposed Change | Severity |
|---|-------|-------------|----------------|----------|
| 1 | [description] | [file] | [what to change] | high/medium/low |

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Is all drift identified? | Re-scan |
| 2 | Are updates consistent across docs? | Verify cross-references |
| 3 | Is LikeC4 syntax valid? | Fix |
| 4 | Does every proposal have >=2 alternatives? | Add alternative |
| 5 | Are trade-offs explicit? | Add pros/cons |
| 6 | Are assumptions marked [VALIDATE] or backed by data? | Mark [VALIDATE] |

### 4. Gate: Human

Present the drift report and proposed updates. Request approval before applying.

## Error Handling

| Issue | Action |
|-------|--------|
| No git diff (nothing changed) | Report "zero drift" |
| Architecture docs incomplete | List gaps, suggest completing the pipeline |
| Drift too large | Suggest re-running affected skills |

---
handoff:
  from: reconcile
  to: null
  context: "Reconciliação concluída. Epic cycle completo."
  blockers: []
