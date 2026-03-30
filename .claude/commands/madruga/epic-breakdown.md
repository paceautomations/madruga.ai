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

## Usage

- `/epic-breakdown fulano` — Break platform "fulano" into epics
- `/epic-breakdown` — Prompt for name

## Output Modes

**Mode 1 — Roadmap-only (default):** Add epic entries to `platforms/<name>/planning/roadmap.md` in the "Proximos Epics" table. **Do NOT create** `epics/NNN-slug/` directories or `pitch.md` files. This keeps the roadmap as the single source of planned work without file proliferation.

**Mode 2 — Full pitch (on request):** When the user explicitly requests detailed epic files (e.g., "create pitch for epic 011"), create `epics/NNN-slug/pitch.md`. Only use this mode when the epic is about to enter the L2 cycle (implementation).

Default is Mode 1. Auto-number epics sequentially from the highest existing epic number.

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

**Mode 1 (Roadmap-only, default):** Add a row to the "Proximos Epics" table in `planning/roadmap.md` for each epic. Format:

```markdown
| NNN | Epic Title | Descricao resumida | Complexidade (Pequena/Media/Grande) | Prioridade sugerida |
```

Do NOT create directories or files. The epic will be detailed later when prioritized for implementation.

**Mode 2 (Full pitch, only when explicitly requested):** Create a directory and pitch:

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

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every epic have a defined problem (not a feature)? | Rewrite as a problem |
| 2 | Is appetite realistic (2w or 6w)? | Adjust or split |
| 3 | Are no-gos explicit? | Add them |
| 4 | Are acceptance criteria testable? | Make them measurable |
| 5 | Is there no scope overlap between epics? | Resolve |
| 6 | Are bounded contexts mapped to epics? | Map them |
| 7 | Are inter-epic dependencies acyclic? | Resolve cycles |

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

