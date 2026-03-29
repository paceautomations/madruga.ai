---
description: Generate C4 Level 2 container architecture with LikeC4 diagrams for any platform
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt for it."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Generate Context Map (DDD)
    agent: madruga/context-map
    prompt: Generate context map with relationships between bounded contexts based on domain model and containers
---

# Containers — C4 Level 2 Architecture

Generate container architecture (~200 lines) with C4 L2 diagram, container table, communication protocols, and per-container NFRs. Include LikeC4 DSL for interactive portal diagrams.

## Cardinal Rule: ZERO Containers Without Clear Responsibility

One container = one reason to exist. If two containers do the same thing, merge them. If one container does everything, split it.

**NEVER:**
- Create a "utils" or "shared" container as a separate runtime
- Split into microservices without scale/team justification
- Omit communication protocols between containers
- Create a container without a clear owner (which bounded context it belongs to)

## Persona

Staff Engineer with 15+ years of experience. Focus on operational simplicity. "Can this be done with fewer containers?" Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/containers fulano` — Generate containers for "fulano"
- `/containers` — Prompt for name

## Output Directory

Save to:
- `platforms/<name>/engineering/containers.md`
- `platforms/<name>/model/platform.likec4`
- `platforms/<name>/model/views.likec4`

## Instructions

### 0. Prerequisites

Run `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill containers` and parse the JSON output.
- If `ready: false`: ERROR listing missing dependencies.
- If `ready: true`: read artifacts listed in `available`.
- Read `.specify/memory/constitution.md`.

### 1. Collect Context + Ask Questions

**Required reading:**
- `engineering/domain-model.md` — bounded contexts and aggregates
- `engineering/blueprint.md` — stack, NFRs, topology
- `decisions/ADR-*.md` — stack decisions that impact containers
- `model/spec.likec4` — existing element types (NEVER redefine)
- `model/ddd-contexts.likec4` — bounded context naming

**Structured Questions:**

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume [N] containers based on the bounded contexts. Correct?" |
| **Trade-offs** | "Modular monolith (simple, 1 deploy) or microservices (complex, independent deploy)?" |
| **Gaps** | "Blueprint does not specify [messaging pattern]. Define it?" |
| **Challenge** | "Do you really need [N] containers? Start with a modular monolith and split later." |

Wait for answers BEFORE generating.

### 2. Generate Artifacts

**File 1: engineering/containers.md**

```markdown
---
title: "Container Architecture"
updated: YYYY-MM-DD
---
# <Name> — Container Architecture (C4 Level 2)

> Containers, responsibilities, protocols, and NFRs. Last updated: YYYY-MM-DD.

---

## Container Diagram

```mermaid
graph TD
  ...
```

---

## Container Table

| Container | Technology | Responsibility | Bounded Contexts | Protocol In | Protocol Out |
|-----------|-----------|---------------|-----------------|-------------|--------------|
| ... | ... | ... | ... | ... | ... |

---

## Inter-Container Communication

| From | To | Protocol | Data | Synchronous? |
|------|-----|----------|------|-------------|
| ... | ... | ... | ... | ... |

---

## Per-Container NFRs

| Container | Latency P95 | Throughput | Availability | Notes |
|-----------|-------------|-----------|-------------|-------|
| ... | ... | ... | ... | ... |

---

## Data Ownership

| Container | Store | Data | Pattern |
|-----------|-------|------|---------|
| ... | ... | ... | Database per service / Shared DB |
```

**File 2: model/platform.likec4**
- Define LikeC4 elements for each container
- Relationships between containers

**File 3: model/views.likec4**
- Views for the interactive portal
- Main container view

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every container have a single responsibility? | Merge or justify |
| 2 | Are there any orphan containers (disconnected)? | Connect or remove |
| 3 | Are protocols defined for every communication? | Add them |
| 4 | Are NFRs measurable per container? | Add targets |
| 5 | Is LikeC4 syntax valid? | Fix |
| 6 | Max 200 lines (.md)? | Condense |
| 7 | Is data ownership clear? | Define it |
| 8 | Does every decision have >=2 documented alternatives? | Add |
| 9 | Are trade-offs explicit (pros/cons)? | Add pros/cons |
| 10 | Are assumptions marked [VALIDATE] or backed by data? | Mark [VALIDATE] |
| 11 | Is .md consistent with .likec4? | Align |

### 4. Approval Gate: Human

Present to user:

**Container Architecture Summary:**
- Containers: [N]
- Communications: [N]
- Pattern: [modular monolith / microservices / hybrid]

**Key Decisions:**
| # | Decision | Simple Alternative | Robust Alternative | Choice |
|---|---------|-------------------|-------------------|--------|
| 1 | ... | ... | ... | ... |

**Validation Questions:**
1. Can this be done with fewer containers?
2. Do the communication protocols make sense?
3. Is data ownership correct?
4. Are per-container NFRs realistic?

Wait for approval before saving.

### 5. Save + Report

```
## Containers generated

**Files:**
- platforms/<name>/engineering/containers.md (<N> lines)
- platforms/<name>/model/platform.likec4
- platforms/<name>/model/views.likec4

**Containers:** <N>
**Communications:** <N>

### Checks
[x] Single responsibility per container
[x] Zero orphan containers
[x] Protocols defined
[x] NFRs with targets
[x] LikeC4 syntax valid

### Next Step
`/context-map <name>`
```

## Error Handling

| Issue | Action |
|-------|--------|
| Domain model with 1 bounded context | Generate 1 container (monolith) — do not force a split |
| Too many containers (>8) | Challenge: "Do you have a team to maintain 8 services?" |
| LikeC4 syntax error | Validate against spec before saving |
| Conflict with blueprint topology | Align with blueprint, propose update if needed |

---
handoff:
  from: containers
  to: context-map
  context: "Containers definidos. Context map deve mapear relações entre bounded contexts."
  blockers: []
