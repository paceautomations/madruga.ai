---
description: Generate a DDD context map with relationships between bounded contexts for any platform
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt for it."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Break Down into Epics (Shape Up)
    agent: madruga/epic-breakdown
    prompt: "Break project into Shape Up epics. WARNING: 1-way-door gate — epic scope defines the entire implementation."
---

# Context Map — DDD Context Map

Generate a context map (~150 lines) with relationships between bounded contexts using DDD patterns (upstream/downstream, ACL, shared kernel, conformist, customer/supplier).

## Cardinal Rule: ZERO Relationships Without a DDD Pattern

Every integration between bounded contexts MUST have an explicitly named DDD pattern. No vague relationships like "they communicate."

**NEVER:**
- Define a relationship without naming the DDD pattern
- Use "shared kernel" as the default pattern for everything (it creates the strongest coupling)
- Ignore upstream/downstream direction
- Create a relationship without business justification

## Persona

Staff Engineer / DDD Expert. Focus on decoupling and clear boundaries. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/context-map fulano` — Generate context map for "fulano"
- `/context-map` — Prompt for name

## Output Directory

Save to `platforms/<name>/engineering/context-map.md`.

## Instructions

### 0. Prerequisites

Run `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill context-map` and parse the JSON output.
- If `ready: false`: ERROR listing missing dependencies.
- If `ready: true`: read artifacts listed in `available`.
- Read `.specify/memory/constitution.md`.

### 1. Collect Context + Ask Questions

**Required reading:**
- `engineering/domain-model.md` — bounded contexts, aggregates
- `engineering/containers.md` — how contexts map to containers
- `model/ddd-contexts.likec4` — context naming for consistency

**Structured Questions:**

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume [context A] is upstream of [context B]. Correct?" |
| **Trade-offs** | "ACL (decoupled, more code) or Conformist (coupled, less code) for [relationship]?" |
| **Gaps** | "The relationship between [X] and [Y] is unclear. How do they communicate?" |
| **Challenge** | "Shared Kernel between [A] and [B] creates strong coupling. Is the trade-off worth it?" |

Wait for answers BEFORE generating.

### 2. Generate Context Map

Check whether a template exists at `.specify/templates/platform/template/engineering/context-map.md.jinja`.

```markdown
---
title: "Context Map"
updated: YYYY-MM-DD
---
# <Name> — Context Map

> Relationships between bounded contexts. Explicit DDD patterns.

---

## Context Diagram

```mermaid
graph TD
  subgraph Upstream
    A[Context A]
  end
  subgraph Downstream
    B[Context B]
  end
  A -->|"ACL"| B
  ...
```

---

## Relationship Table

| Upstream | Downstream | Pattern | Direction | Justification |
|----------|-----------|---------|-----------|--------------|
| [Context A] | [Context B] | ACL | A -> B | [why ACL and not conformist] |
| [Context C] | [Context D] | Customer/Supplier | C -> D | [justification] |
| ... | ... | ... | ... | ... |

---

## Patterns Used

| Pattern | Description | When to Use | Used In |
|---------|------------|------------|---------|
| **Shared Kernel** | Shared code between contexts | When 2 contexts evolve together | [if applicable] |
| **ACL (Anti-Corruption Layer)** | Translates external model to internal | When upstream has a different model | [relationships] |
| **Conformist** | Downstream adopts upstream's model | When upstream is stable and reliable | [relationships] |
| **Customer/Supplier** | Upstream adapts to downstream | When downstream has negotiation power | [relationships] |
| **Open Host Service** | Standardized public API | When there are many consumers | [relationships] |
| **Published Language** | Standard integration language | When a neutral format is needed | [relationships] |

---

## Anti-Patterns to Avoid

| Anti-Pattern | Risk | How to Detect |
|-------------|------|--------------|
| Big Ball of Mud | No clear boundaries | All contexts communicate with all |
| Excessive Shared Kernel | Strong coupling | >2 contexts sharing a kernel |
| God Context | 1 context does everything | Context with >5 aggregates |
```

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every relationship have a named DDD pattern? | Name it |
| 2 | Is the upstream/downstream direction clear? | Define it |
| 3 | Does every relationship have a justification? | Justify |
| 4 | Are patterns appropriate (not "shared kernel for everything")? | Re-evaluate |
| 5 | Does the Mermaid diagram render? | Fix |
| 6 | Max 150 lines? | Condense |
| 7 | Are all contexts from the domain model present? | Add missing ones |
| 8 | Does every decision have >=2 documented alternatives? | Add |
| 9 | Are trade-offs explicit? | Add pros/cons |
| 10 | Are assumptions marked [VALIDATE] or backed by data? | Mark [VALIDATE] |

### 4. Approval Gate: Human

Present to user:

**Context Map Summary:**
- Bounded Contexts: [N]
- Relationships: [N]
- Patterns used: [list]

**Validation Questions:**
1. Do the upstream/downstream directions make sense?
2. Are the chosen patterns the most appropriate?
3. Is any relationship missing?
4. Is shared kernel (if used) truly necessary?

Wait for approval before saving.

### 5. Save + Report

```
## Context Map generated

**File:** platforms/<name>/engineering/context-map.md
**Lines:** <N>
**Relationships:** <N>
**Patterns used:** [list]

### Checks
[x] Every relationship has a DDD pattern
[x] Upstream/downstream directions clear
[x] Justifications present
[x] All contexts covered

### Next Step
`/epic-breakdown <name>` — Break into Shape Up epics.
WARNING: 1-way-door gate — epic scope defines the entire implementation.
```

## Error Handling

| Issue | Action |
|-------|--------|
| Only 1 bounded context | Trivial context map — 0 relationships. Suggest whether more contexts are needed |
| Circular relationships | Identify and resolve — indicates wrong boundary |
| Isolated context (no relationships) | Question: is it truly independent? |
| Conflict between domain-model and containers | Align — contexts should map to containers |
