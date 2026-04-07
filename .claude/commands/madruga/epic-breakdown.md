---
description: Break a project into Shape Up epics with Problem, Appetite, Solution, Rabbit Holes, and Acceptance Criteria
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt for it."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Generate Roadmap
    agent: madruga/roadmap
    prompt: Sequence epics into a delivery roadmap based on dependencies and risks
---

# Epic Breakdown — Shape Up Epic Decomposition

Break the project into epics using Shape Up format: Problem, Appetite, Solution, Rabbit Holes, No-gos, Acceptance Criteria. Each epic becomes `epics/NNN-slug/pitch.md`.

## Cardinal Rule: ZERO Epics Without a Defined Problem

If the problem cannot be explained in 2 sentences, the epic is poorly defined. Every epic starts from a real problem, not from a feature list.

**NEVER:**
- Create an epic from a feature ("build login") without a problem ("users cannot access their accounts")
- Leave scope ambiguous between epics
- Create an epic with appetite > 6w without splitting
- Omit no-gos (what is NOT in scope)

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-planning.md`.

## Persona

Product Manager (Shape Up) — problem before solution, appetite as constraint. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/epic-breakdown prosauai` — Break platform "prosauai" into epics
- `/epic-breakdown` — Prompt for name

## Output

Always create `epics/NNN-slug/pitch.md` with minimal content. Auto-number epics sequentially from the highest existing epic number. The detailed implementation context (branch creation, architectural decisions) is enriched into the same `pitch.md` later by `epic-context`.

## Instructions

### 1. Collect Context + Ask Questions

**Required reading (full context):**
- `engineering/domain-model.md` — bounded contexts
- `engineering/blueprint.md` — architecture, NFRs, deploy topology
- `engineering/context-map.md` — DDD relationships
- `business/*` — vision, solution-overview, process
- `engineering/blueprint.md` — NFRs and cross-cutting concerns
- `decisions/ADR-*.md` — technology constraints

**Identify natural epic boundaries:**
- 1 bounded context = candidate for 1 epic
- 1 critical business flow = candidate for 1 epic
- Cross-cutting concerns = possible infra epic

**Structured Questions:**

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume [N] epics based on the bounded contexts. Correct?" |
| **Trade-offs** | "MVP with [2 epics] or full delivery with [5]? What appetite?" |
| **Gaps** | "What is the MVP success criterion?" |
| **Challenge** | "Epic [X] seems too large (6w). Worth splitting into 2 of 2w?" |

Wait for answers BEFORE generating epics.

### 2. Generate Epics

For each epic, create `epics/NNN-slug/pitch.md` with **minimal content**. The full pitch (Solution, Rabbit Holes, No-gos, Acceptance Criteria) is generated later by `epic-context` when the epic enters L2.

```markdown
---
id: NNN
title: "Epic NNN: Title"
status: planned
appetite: 2w | 6w
priority: P1 | P2 | P3
---
# Epic NNN: Title

## Problem

[2-3 sentences: what problem this epic solves. From user/business perspective.]

## Appetite

**[2w | 6w]** — [size justification]

## Dependencies

- Depends on: [epic NNN] (if applicable)
- Blocks: [epic NNN] (if applicable)
```

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every epic have a defined problem (not a feature)? | Rewrite as a problem |
| 2 | Is appetite realistic (2w or 6w)? | Adjust or split |
| 3 | Is there no scope overlap between epics? | Resolve |
| 4 | Are inter-epic dependencies acyclic? | Resolve cycles |

### Tier 3 — Adversarial Review (1-way-door)

Per pipeline-contract-base.md Tier 3: before presenting to user, launch a subagent (Agent tool, subagent_type="general-purpose") with the complete artifact text. Prompt: "You are a staff engineer reviewing this epic breakdown for a 1-way-door decision. Be harsh and direct. Check for: scope creep, missing epics, overlapping epics, unrealistic appetites, hidden assumptions. Output a bullet list of issues (BLOCKER/WARNING/NIT) and an overall verdict."

Incorporate feedback: fix blockers, note warnings in the scorecard.

## Error Handling

| Issue | Action |
|-------|--------|
| Very small project (1 epic) | OK — 1 epic is valid |
| Too many epics (>8) | Group related ones or question granularity |
| Total appetite > 6 months | Alert about scope risk |
| Circular dependency between epics | Resolve via split or merge |
| Context without an associated epic | Check whether the context is needed now |

