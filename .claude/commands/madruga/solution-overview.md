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

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-business.md`.

## Usage

- `/solution-overview fulano` — Generate solution overview for platform "fulano"
- `/solution-overview` — Prompt for the platform name and collect context

## Output Directory

Save to `platforms/<name>/business/solution-overview.md`. Create the directory if it does not exist.

## Instructions

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

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Zero technical terms (scan for: API, SDK, framework, database, backend, frontend, deploy, server, endpoint, middleware, cache, queue, Python, Redis, Docker, Supabase, pgvector, webhook, microservice, CI/CD, ADR, pipeline, module) | Rewrite in product language |
| 2 | Every feature has both description AND value | Complete the missing fields |
| 3 | No section exceeds 30 lines | Trim |
| 4 | Total under 120 lines | Condense |
| 5 | Max 15 features in the map | Group similar features |
| 6 | Max 5 principles | Prioritize |

## Error Handling

| Problem | Action |
|---------|--------|
| User does not know the features | Ask: "What does your user do in the product today? What would you like them to do?" and derive features |
| Too many features (>15) | Group similar ones. E.g., "Offline evals" + "Online evals" = "Quality measurement" |
| No clear priorities | Ask: "Without what does the product not work?" (Now) / "What improves it significantly?" (Next) / "What would be nice to have?" (Later) |
| Vision exists but solution-overview does not | Read vision and derive features from segments and critical battles |
| Platform already has a solution-overview | Read as baseline, ask whether to rewrite or iterate |

---
handoff:
  from: solution-overview
  to: business-process
  context: "Feature map priorizado. Business process deve mapear fluxos core."
  blockers: []
