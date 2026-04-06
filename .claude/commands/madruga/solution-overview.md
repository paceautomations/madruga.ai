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

# Solution Overview — Feature Map + Principles + Boundaries

Generate a solution overview (~120 lines) containing a product narrative, a feature map split by maturity (Implementado/Next/Later), product principles, and explicit boundaries (what the product does NOT do). The output is purely business/product-oriented. Personas belong in `vision.md`, NOT here.

## Cardinal Rule: ZERO Technical Content

This document describes **what the product does from the user's perspective**. Technical decisions, architecture, and implementation belong in other artifacts.

**NEVER include in the output:**
- Names of technologies, frameworks, languages, databases, or libraries (e.g., Python, FastAPI, Redis, Supabase, pgvector, React, Docker, Copier, Jinja2, Astro, Starlight, Mermaid, SQLite, Vite, Tailwind)
- Architecture terms (e.g., RLS, API, SDK, middleware, cache, queue, webhook, endpoint, microservice, pipeline, module, WAL, FTS5, systemd, asyncio, daemon, ruff)
- References to ADRs, technical specs, C4 diagrams, or numbered epics (e.g., 006, 007, 008)
- Infrastructure details (e.g., deploy, CI/CD, server, container, cloud provider)
- Names of internal development tools or automated agents
- Automated systems as personas — only humans who interact with the product are personas (and personas belong in vision.md)

**Permitted exceptions:** proper names of products/companies and common business terms (e.g., "platform", "channel", "automation", "dashboard").

**When in doubt:** if a sentence only makes sense to an engineer, rewrite it in language that an SMB owner would understand.

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-business.md`.

## Persona

Product Designer — user-focused, simple language, prioritizes clarity. Write generated artifacts in Brazilian Portuguese (PT-BR).

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

Check whether `business/vision.md` exists — if so, read it to extract business context and personas (personas live there, not here).
Check whether `research/` exists — if so, read it to extract use cases.
If `platforms/fulano/business/solution-overview.md` exists, read it as a **tone reference** for business-oriented writing.

Collect the following from the user (ask everything at once):

| # | Question | Example |
|---|----------|---------|
| 1 | **What does the user do in the product?** (1-2 sentences, user's perspective) | "Connects WhatsApp, configures agent, monitors metrics" |
| 2 | **Known features** — free-form list, any level of detail. Include what already works AND what is planned. | "Reply to messages, transfer to human, admin dashboard" |
| 3 | **Priorities** — what is already implemented vs. coming next vs. future? | "Reply is live, dashboard is next, billing is later" |
| 4 | **Boundaries** — what does the product explicitly NOT do? | "Not an IDE, not a CI/CD tool, not a project manager" |

If context was already gathered from existing docs (vision), present a summary and ask if adjustments are needed.

After receiving answers, identify implicit assumptions and present structured questions:

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume [Feature X] is already implemented. Correct?" |
| **Trade-offs** | "Broad feature map (more features, less depth) or focused (fewer features, more detail)?" |
| **Gaps** | "I found no information about [feature Y]. Implemented, Next, or Later?" |
| **Provocation** | "[Feature Z] seems obvious, but is it really implemented or still Next?" |

Wait for answers BEFORE generating.

### 2. Generate Solution Overview

Write the document with exactly **6 sections**. All generated content MUST be in PT-BR:

```markdown
---
title: "Solution Overview"
updated: YYYY-MM-DD
sidebar:
  order: 2
---
# <Name> — Solution Overview

## Visao de Solucao

[Product narrative from the user's perspective. What they see, do, and gain.
2-3 short paragraphs. Simple language — a bakery owner could understand it.]

---

## Implementado — Funcional hoje

| Feature | Descricao | Por que é importante |
|---------|-----------|---------------------|
| **[Feature 1]** | [1-2 lines, user language — what the user sees/does] | [why this matters for the business] |
| **[Feature 2]** | ... | ... |

---

## Next — Candidatos para proximos ciclos

| Feature | Descricao | Por que é importante |
|---------|-----------|---------------------|
| **[Feature N]** | ... | ... |

---

## Later — Visao de longo prazo

| Feature | Descricao | Por que é importante |
|---------|-----------|---------------------|
| **[Feature L]** | ... | ... |

---

## Principios de Produto

1. **[Principle]** — [1-line explanation]
2. ...

---

## O que NAO fazemos

| NAO e... | Porque |
|----------|--------|
| **[Boundary 1]** | [Why we chose not to do this] |
| **[Boundary 2]** | ... |
```

### Generation Rules:

1. **Feature tables:** 3 separate sections (Implementado, Next, Later). Max 15 features total across all three.
2. **Description:** always from the user's perspective, never the engineer's. "Agent replies to messages" not "webhook receives payload and sends to pipeline".
3. **"Por que é importante":** 1 short sentence about why this feature matters for the business.
4. **Principles:** max 5. Derive from the vision if it exists. These are macro product principles (e.g., "one true source of truth for all data"), not technical implementation choices.
5. **Boundaries:** min 2, max 5. Clear statements of what the product explicitly does NOT do, with business reasoning.
6. **No technical actors:** automated systems, background processes, or runtime engines are NOT personas and must not appear. Personas belong in vision.md.

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Zero technical terms (scan for: API, SDK, framework, database, backend, frontend, deploy, server, endpoint, middleware, cache, queue, Python, Redis, Docker, Supabase, pgvector, webhook, microservice, CI/CD, ADR, pipeline, module, Copier, Jinja2, Astro, Starlight, Mermaid, WAL, FTS5, SQLite, systemd, asyncio, daemon, ruff, Vite, React, Tailwind, copier) | Rewrite in product language |
| 2 | Every feature has both description AND "por que é importante" | Complete the missing fields |
| 3 | No section exceeds 30 lines | Trim |
| 4 | Total under 120 lines | Condense |
| 5 | Max 15 features across all three tables | Group similar features |
| 6 | Max 5 principles | Prioritize |
| 7 | "O que NAO fazemos" section present with min 2 entries | Add boundaries |
| 8 | No "Personas" section exists (personas belong in vision.md) | Remove and reference vision.md |

## Error Handling

| Problem | Action |
|---------|--------|
| User does not know the features | Ask: "What does your user do in the product today? What would you like them to do?" and derive features |
| Too many features (>15) | Group similar ones. E.g., "Offline evals" + "Online evals" = "Quality measurement" |
| No clear priorities | Ask: "What already works today?" (Implementado) / "What improves it significantly?" (Next) / "What would be nice to have?" (Later) |
| Vision exists but solution-overview does not | Read vision and derive features from segments and critical battles |
| Platform already has a solution-overview | Read as baseline, ask whether to rewrite or iterate |
| User lists technical features | Translate to user language. "SQLite state store" → "Progress tracking" |

---
handoff:
  from: solution-overview
  to: business-process
  context: "Feature map priorizado. Business process deve mapear fluxos core."
  blockers: []
