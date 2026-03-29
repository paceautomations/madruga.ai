---
description: Generate a solution overview with a prioritized feature map for any platform
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt the user."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Generate Business Process
    agent: madruga/business-process
    prompt: Generate business flows based on the validated vision and solution overview
---

# Solution Overview — Prioritized Feature Map

Generate a solution overview (~100 lines) containing a product vision, personas, a prioritized feature map (Now/Next/Later), and product principles. The output is purely business/product-oriented.

## Cardinal Rule: ZERO Technical Content

This document describes **what the product does from the user's perspective**. Technical decisions, architecture, and implementation belong in other artifacts.

**NEVER include in the output:**
- Names of technologies, frameworks, languages, databases, or libraries (e.g., Python, FastAPI, Redis, Supabase, pgvector, React, Docker)
- Architecture terms (e.g., RLS, API, SDK, middleware, cache, queue, webhook, endpoint, microservice, pipeline, module)
- References to ADRs, technical specs, C4 diagrams, or numbered epics
- Infrastructure details (e.g., deploy, CI/CD, server, container, cloud provider)
- Names of internal development tools

**Permitted exceptions:** proper names of products/companies and common business terms (e.g., "platform", "channel", "automation", "dashboard").

**When in doubt:** if a sentence only makes sense to an engineer, rewrite it in language that an SMB owner would understand.

## Persona

Senior Bain/McKinsey product strategist. Focus on user value, not how to build it. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/solution-overview fulano` — Generate solution overview for platform "fulano"
- `/solution-overview` — Prompt for the platform name and collect context

## Output Directory

Save to `platforms/<name>/business/solution-overview.md`. Create the directory if it does not exist.

## Instructions

### 0. Prerequisites

Run `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill solution-overview` and parse the JSON output.
- If `ready: false`: ERROR — list missing dependencies and which skill generates each one.
- If `ready: true`: read artifacts listed in `available` as additional context.
- Read `.specify/memory/constitution.md` to validate the output against project principles.

### 1. Collect Context + Ask Questions

**If `$ARGUMENTS.platform` is provided:** use it as the platform name.
**If empty:** ask the user for the name.

Check whether `platforms/<name>/business/solution-overview.md` already exists. If it does, read it as a baseline.

Check whether `business/vision.md` exists — if so, read it to extract business context.
Check whether `research/` exists — if so, read it to extract use cases.

Collect the following from the user (ask everything at once):

| # | Question | Example |
|---|----------|---------|
| 1 | **What does the user do in the product?** (1-2 sentences, user's perspective) | "Connects WhatsApp, configures agent, monitors metrics" |
| 2 | **Who uses it?** (2-3 personas) | "SMB owner, end customer, operator" |
| 3 | **Known features** — free-form list, any level of detail | "Reply to messages, transfer to human, admin dashboard" |
| 4 | **Priorities** — what comes first vs. later vs. future? | "First reply, then dashboard, then billing" |

If context was already gathered from existing docs (vision), present a summary and ask if adjustments are needed.

After receiving answers, identify implicit assumptions and present structured questions:

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume [Persona X] is the primary user. Correct?" |
| **Trade-offs** | "Broad feature map (more features, less depth) or focused (fewer features, more detail)?" |
| **Gaps** | "I found no information about [journey Y]. Do you define it or should I propose?" |
| **Provocation** | "[Feature Z] seems obvious, but is it really Now or could it be Later?" |

Wait for answers BEFORE generating.

### 2. Generate Solution Overview

Write the document with exactly **4 sections**. All generated content MUST be in PT-BR:

```markdown
---
title: "Solution Overview"
updated: YYYY-MM-DD
---
# <Name> — Solution Overview

> O que vamos construir, para quem, e em que ordem. Ultima atualizacao: YYYY-MM-DD.

---

## Visao de Solucao

[Product narrative from the user's perspective. What they see, do, and gain.
2-3 short paragraphs. Simple language — a bakery owner could understand it.]

---

## Personas x Jornadas

| Persona | O que faz | O que ganha | Jornada principal |
|---------|-----------|-------------|-------------------|
| **[Persona 1]** | ... | ... | ... |
| **[Persona 2]** | ... | ... | ... |
| **[Persona 3]** | ... | ... | ... |

---

## Feature Map

| Prioridade | Feature | Descricao | Valor |
|------------|---------|-----------|-------|
| **Now** | ... | [1-2 lines, user language] | [why it matters] |
| **Next** | ... | ... | ... |
| **Later** | ... | ... | ... |

---

## Principios de Produto

1. **[Principle]** — [1-line explanation]
2. ...
```

### Generation Rules:

1. **Feature Map:** group by priority (Now first, Later last). Max 15 features.
2. **Description:** always from the user's perspective, never the engineer's. "Agent replies to messages" not "webhook receives payload and sends to pipeline".
3. **Value:** 1 short sentence about why this feature matters for the business.
4. **Principles:** max 5. Derive from the vision if it exists.
5. **Personas:** max 4. Always include the end user (the one receiving the service), not just the person who configures it.

### 3. Auto-Review

Before saving, verify:

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Zero technical terms (scan for: API, SDK, framework, database, backend, frontend, deploy, server, endpoint, middleware, cache, queue, Python, Redis, Docker, Supabase, pgvector, webhook, microservice, CI/CD, ADR, pipeline, module) | Rewrite in product language |
| 2 | Every feature has both description AND value | Complete the missing fields |
| 3 | Every decision has >=2 documented alternatives | Add an alternative |
| 4 | Explicit trade-offs (pros/cons) | Add pros/cons |
| 5 | Assumptions marked [VALIDAR] or backed by data | Mark [VALIDAR] |
| 6 | No section exceeds 30 lines | Trim |
| 7 | Total under 120 lines | Condense |
| 8 | Max 15 features in the map | Group similar features |
| 9 | Max 5 principles | Prioritize |

### 4. Approval Gate (human)

Present to the user:

```
## Solution Overview Summary

**Personas:** [list]
**Features:** <N> (Now: <n>, Next: <n>, Later: <n>)
**Principles:** [list]

### Decisions Made
1. [Decision]: [rationale]
2. ...

### Validation Questions
1. Do the personas cover all user types?
2. Does the Now/Next/Later prioritization reflect reality?
3. Is any important feature missing?
4. Do the product principles guide future decisions?
```

Wait for approval before saving.

### 5. Save + Report

1. Save to `platforms/<name>/business/solution-overview.md`
2. Report to the user:

```
## Solution Overview Generated

**File:** platforms/<name>/business/solution-overview.md
**Lines:** <N>
**Features:** <N> (Now: <n>, Next: <n>, Later: <n>)

### Checks
[x] Zero technical jargon
[x] Features with description and value
[x] Decisions with alternatives
[x] Explicit trade-offs
[x] Assumptions marked
[x] Sections <= 30 lines
[x] Total < 120 lines
[x] Max 15 features
[x] Max 5 principles

### Next Step
`/business-process <name>`
```

## Error Handling

| Problem | Action |
|---------|--------|
| User does not know the features | Ask: "What does your user do in the product today? What would you like them to do?" and derive features |
| Too many features (>15) | Group similar ones. E.g., "Offline evals" + "Online evals" = "Quality measurement" |
| No clear priorities | Ask: "Without what does the product not work?" (Now) / "What improves it significantly?" (Next) / "What would be nice to have?" (Later) |
| Vision exists but solution-overview does not | Read vision and derive features from segments and critical battles |
| Platform already has a solution-overview | Read as baseline, ask whether to rewrite or iterate |
