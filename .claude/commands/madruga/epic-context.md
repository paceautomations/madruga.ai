---
description: Capture implementation context and decisions before the SpecKit cycle for an epic
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
  - name: epic
    description: "Epic number (e.g., 001)."
    required: false
argument-hint: "[platform] [epic-number]"
handoffs:
  - label: Start SpecKit Cycle
    agent: speckit.specify
    prompt: "Context captured. Start implementation cycle with /speckit.specify."
---

# Epic Context — Implementation Context

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

Capture implementation decisions and preferences before starting the SpecKit cycle for an epic. Identify gray areas and resolve ambiguities.

## Cardinal Rule: ZERO Decisions Without Architectural Context

Every implementation decision MUST reference the blueprint, ADRs, or domain model. No choices made in a vacuum.

## Persona

Staff Engineer. Bridge architecture and implementation. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/epic-context fulano 001` — Capture context for epic 001 of "fulano"
- `/epic-context` — Prompt for platform and epic

## Output Directory

Save to `platforms/<name>/epics/<N>/context.md`.

## Instructions

Additional required reading:
- `epics/<NNN>/pitch.md` — epic scope
- `engineering/blueprint.md` — stack and concerns
- `engineering/domain-model.md` — DDD
- `engineering/containers.md` — architecture
- `decisions/ADR-*.md` — relevant decisions

### 1. Collect Context + Ask Questions

By feature type in the epic:

| Type | Typical Gray Areas |
|------|--------------------|
| Visual/UI | Layout, responsive, design system, accessibility |
| API | Error codes, pagination, rate limiting, versioning |
| Data | Schema design, migration strategy, indexing, retention |
| Integration | Failure modes, retries, circuit breaker, timeouts |
| Infra | Deploy strategy, scaling, monitoring thresholds |

**Structured Questions:**

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume [ADR-NNN decision] applies here. Correct?" |
| **Trade-offs** | "For [gray area]: [simple approach A] or [robust approach B]?" |
| **Gaps** | "Blueprint does not specify [detail X] for this epic. Define it?" |
| **Challenge** | "[Obvious approach] may not be the best because [reason]." |

Wait for answers BEFORE generating.

### 2. Generate Context

```markdown
---
title: "Implementation Context — Epic <N>"
updated: YYYY-MM-DD
---
# Epic <N> — Implementation Context

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|---------|----------------------|
| 1 | [area] | [decision] | ADR-NNN / blueprint / domain-model |

## Resolved Gray Areas

[For each gray area: question, answer, rationale]

## Applicable Constraints

[From blueprint/ADRs that impact this epic]

## Suggested Approach

[Summary of the implementation approach]
```

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every decision reference architecture? | Connect it |
| 2 | Are gray areas resolved? | Resolve or mark as pending |
| 3 | Are blueprint constraints present? | Add them |
| 4 | Does every decision have >=2 documented alternatives? | Add |
| 5 | Are trade-offs explicit (pros/cons)? | Add pros/cons |
| 6 | Are assumptions marked [VALIDATE] or backed by data? | Mark [VALIDATE] |

### 4. Gate: Human

Present captured decisions and resolved gray areas for validation.

## Error Handling

| Issue | Action |
|-------|--------|
| Epic does not exist | Suggest running `/epic-breakdown` first |
| Architecture docs incomplete | List gaps, suggest completing the pipeline |
| Too many gray areas (>10) | Prioritize the 5 most critical |

---
handoff:
  from: epic-context
  to: specify
  context: "Contexto de implementação capturado. Spec deve endereçar decisões e constraints documentadas."
  blockers: []
