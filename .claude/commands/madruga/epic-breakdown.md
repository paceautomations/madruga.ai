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

## Persona

Product Manager / Architect. Dual hat: understands business AND technology. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/epic-breakdown fulano` — Break platform "fulano" into epics
- `/epic-breakdown` — Prompt for name

## Output Directory

Save to `platforms/<name>/epics/NNN-slug/pitch.md`. Auto-number.

## Instructions

### 0. Prerequisites

Run `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill epic-breakdown` and parse the JSON output.
- If `ready: false`: ERROR listing missing dependencies.
- If `ready: true`: read artifacts listed in `available`.
- Read `.specify/memory/constitution.md`.

### 1. Collect Context + Ask Questions

**Required reading (full context):**
- `engineering/domain-model.md` — bounded contexts
- `engineering/containers.md` — architecture
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

For each epic, create a directory and pitch:

`epics/NNN-slug/pitch.md`

```markdown
---
title: "Epic NNN: Title"
appetite: 2w | 6w
priority: P1 | P2 | P3
---
# Epic NNN: Title

## Problem

[2-3 sentences: what problem this epic solves. From user/business perspective.]

## Appetite

**[2w | 6w]** — [size justification]

## Solution

[High-level approach. What will be built, not how. 1-2 paragraphs.]

### Bounded Contexts Involved
- [Context A] — [what changes in this context]
- [Context B] — [what changes]

### Containers Impacted
- [Container X] — [what changes]

## Rabbit Holes

[Things that can consume unnecessary time. Where NOT to go deep.]

1. [Rabbit hole 1] — [why to avoid]
2. [Rabbit hole 2] — [why to avoid]

## No-gos

[Explicitly out of scope for this epic.]

1. [No-go 1] — [will be addressed in which epic, or never]
2. [No-go 2]

## Acceptance Criteria

[Testable checklist. When all items are checked, the epic is done.]

- [ ] [Criterion 1 — measurable]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

## Dependencies

- Depends on: [epic NNN] (if applicable)
- Blocks: [epic NNN] (if applicable)
```

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every epic have a defined problem (not a feature)? | Rewrite as a problem |
| 2 | Is appetite realistic (2w or 6w)? | Adjust or split |
| 3 | Are no-gos explicit? | Add them |
| 4 | Are acceptance criteria testable? | Make them measurable |
| 5 | Is there no scope overlap between epics? | Resolve |
| 6 | Are bounded contexts mapped to epics? | Map them |
| 7 | Are inter-epic dependencies acyclic? | Resolve cycles |
| 8 | Does every decision have >=2 documented alternatives? | Add |
| 9 | Are trade-offs explicit? | Add pros/cons |
| 10 | Are assumptions marked [VALIDATE] or backed by data? | Mark [VALIDATE] |

### 4. Approval Gate: 1-Way-Door

**WARNING: 1-way-door gate.** Epic scope defines ALL downstream implementation (roadmap, specs, tasks, code).

Present:

| # | Epic | Problem | Appetite | Contexts | Deps |
|---|------|---------|----------|----------|------|
| 1 | NNN: [title] | [summary] | 2w/6w | [contexts] | [deps] |

**For EACH epic, request confirmation:**

> **Epic NNN: [title]**
> Problem: [summary]
> Appetite: [Xw]
> Includes: [scope list]
> Excludes (no-gos): [list]
> Depends on: [epics]
>
> **Confirm scope? This defines the implementation. (yes/no/adjust)**

### 5. Save + Report

```
## Epics generated

**Directory:** platforms/<name>/epics/
**Epics:** <N>
**Total appetite:** <N> weeks

| Epic | Appetite | Priority |
|------|----------|----------|
| NNN: [title] | Xw | P1/P2/P3 |

### Checks
[x] Problems defined (not features)
[x] Appetites realistic
[x] No-gos explicit
[x] Acceptance criteria testable
[x] Zero scope overlap
[x] Per-epic approval (1-way-door gate)

### Next Step
`/roadmap <name>` — Sequence epics into a delivery roadmap.
```

## Error Handling

| Issue | Action |
|-------|--------|
| Very small project (1 epic) | OK — 1 epic is valid |
| Too many epics (>8) | Group related ones or question granularity |
| Total appetite > 6 months | Alert about scope risk |
| Circular dependency between epics | Resolve via split or merge |
| Context without an associated epic | Check whether the context is needed now |

---
handoff:
  from: epic-breakdown
  to: roadmap
  context: "Epics definidos com pitch, appetite, e acceptance criteria. Roadmap deve sequenciar entrega."
  blockers: []
