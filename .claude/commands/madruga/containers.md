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

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-engineering.md`.

## Persona

Platform engineer — one responsibility per container, explicit protocols. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/containers fulano` — Generate containers for "fulano"
- `/containers` — Prompt for name

## Output Directory

Save to:
- `platforms/<name>/model/platform.likec4`
- `platforms/<name>/model/views.likec4`

> **Note:** This skill generates LikeC4 files only. Container NFRs and deploy topology live in `engineering/blueprint.md`. No separate `engineering/containers.md` is generated — the LikeC4 model is the source of truth for containers.

## Instructions

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

**File 1: model/platform.likec4**
- Define LikeC4 elements for each container
- Relationships between containers
- Use existing element types from `model/spec.likec4` (NEVER redefine)

**File 2: model/views.likec4**
- Views for the interactive portal
- Main container view + zoom views per bounded context

**MANDATORY: For EVERY `boundedContext` in `ddd-contexts.likec4`, generate:**

1. A scoped view in `views.likec4`:
```likec4
view <name>Detail of <name> {
  title '<DisplayName> — <DDD Classification (Core/Supporting/Generic) Domain>'
  description '<What this bounded context does>'
  include *
  include <relevant externals from externals.likec4 and infrastructure.likec4>
}
```

2. An entry in `platform.yaml` under `views.structural`:
```yaml
- id: <name>Detail
  label: "<DisplayName> (zoom)"
```

**Why**: LikeC4 auto-generates `navigateTo` for bounded contexts when a scoped `view X of Y` exists. The portal generates navigation URLs only from `platform.yaml` `views.structural`. Missing either one breaks portal navigation.

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every container have a single responsibility? | Merge or justify |
| 2 | Are there any orphan containers (disconnected)? | Connect or remove |
| 3 | Are protocols defined for every communication? | Add them |
| 4 | Are NFRs measurable per container? | Add targets |
| 5 | Is LikeC4 syntax valid? | Fix |
| 6 | Are views defined for all bounded contexts? | Add zoom views |
| 7 | Every BC from ddd-contexts.likec4 has `view <name>Detail of <name>` in views.likec4? | Add missing views |
| 8 | Every `<name>Detail` view registered in `platform.yaml` `views.structural`? | Add entry |
| 9 | `autoLayout` ONLY in `dynamic view`, not in structural views? | Remove |
| 10 | `likec4 build` passes without errors? | Fix syntax errors |

### LikeC4 Validation

After saving `.likec4` files, validate by running `likec4 build` in the model directory. Reference `.claude/knowledge/likec4-syntax.md` for syntax. Fix all errors before proceeding to the gate.

## Error Handling

| Issue | Action |
|-------|--------|
| Domain model with 1 bounded context | Generate 1 container (monolith) — do not force a split |
| Too many containers (>8) | Challenge: "Do you have a team to maintain 8 services?" |
| LikeC4 syntax error | Validate against spec before saving |
| Conflict with blueprint topology | Align with blueprint, propose update if needed |

---
