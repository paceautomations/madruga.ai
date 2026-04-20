---
description: Generate a solution overview with a value-stream feature map for any platform
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

# Solution Overview — Value-Stream Feature Map + Principles + Boundaries

Generate a solution overview containing a product narrative, a **feature map organized by value stream** (not by delivery horizon), product principles, and explicit boundaries (what the product does NOT do). The output is purely business/product-oriented. Personas belong in `vision.md`, NOT here.

## Cardinal Rule: ZERO Technical Content in Prose

This document describes **what the product does from the user's perspective**. Technical decisions, architecture, and implementation belong in other artifacts.

**NEVER include in descriptive prose (Valor column, narrative, principles, boundaries):**
- Names of technologies, frameworks, languages, databases, or libraries (e.g., Python, FastAPI, Redis, Supabase, pgvector, React, Docker, Copier, Jinja2, Astro, Starlight, Mermaid, SQLite, Vite, Tailwind)
- Architecture terms (e.g., RLS, API, SDK, middleware, cache, queue, webhook, endpoint, microservice, pipeline, module, WAL, FTS5, systemd, asyncio, daemon, ruff)
- References to ADRs, technical specs, or C4 diagrams
- Infrastructure details (e.g., deploy, CI/CD, server, container, cloud provider)
- Names of internal development tools or automated agents
- Automated systems as personas — only humans who interact with the product are personas (and personas belong in vision.md)

**Numbered epic references are permitted ONLY in metadata columns** (`Status` and `Horizonte`), never in the `Valor` column or in narrative prose. The `Valor` column answers "what does the user get"; epic number is shipping metadata, not product content.

**Permitted exceptions:** proper names of products/companies and common business terms (e.g., "platform", "channel", "automation", "dashboard").

**When in doubt:** if a sentence only makes sense to an engineer, rewrite it in language that an SMB owner would understand.

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-business.md`.

## Persona

Product Designer — user-focused, simple language, prioritizes clarity. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/solution-overview prosauai` — Generate solution overview for platform "prosauai"
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
Check whether `planning/roadmap.md` and `epics/*/reconcile-report.md` exist — if so, derive **value streams** and delivery status from them. Reconcile reports carry the authoritative "what shipped where" record.
If `platforms/prosauai/business/solution-overview.md` exists, read it as a **tone reference** for business-oriented writing.

Collect the following from the user (ask everything at once):

| # | Question | Example |
|---|----------|---------|
| 1 | **What does the user do in the product?** (1-2 sentences, user's perspective) | "Connects WhatsApp, configures agent, monitors metrics" |
| 2 | **Value streams** — what are the 3-6 user-facing capability groups the platform ships? | "Message delivery / Media handling / Admin operations / Compliance" |
| 3 | **Known features per stream** — free-form list, any level of detail. Include what already works AND what is planned. | "Delivery: WhatsApp intake, debounce, multi-tenant. Media: audio transcription, image description." |
| 4 | **Boundaries** — what does the product explicitly NOT do? | "Not a CRM, not a call center, not a marketplace" |

If context was already gathered from existing docs (vision + roadmap + reconcile reports), present a summary and ask if adjustments are needed.

After receiving answers, identify implicit assumptions and present structured questions:

| Category | Question |
|----------|----------|
| **Assumptions** | "I grouped [features X, Y] under value stream [Z]. Correct?" |
| **Trade-offs** | "Broad value streams (fewer, higher-level) or focused (more streams, narrower)?" |
| **Gaps** | "I found no shipping evidence for [feature Y] in reconcile reports. Status is 🔄 in-progress or 📋 planned?" |
| **Provocation** | "[Feature Z] looks like a delivery mechanism (Evolution API, Meta Cloud), not a user value. Should it be a Status attribute of another feature instead of its own row?" |

Wait for answers BEFORE generating.

### 2. Generate Solution Overview

Write the document with exactly **6 top-level sections**. All generated content MUST be in PT-BR:

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

> Personas e jornadas detalhadas → ver [Vision](./vision/).

---

## Mapa de Features

> Catalogo de funcionalidades user-facing. Linguagem de negocio — o "o que" e o "por que", nao o "como". Cada feature carrega **Status** (✅ live · 🔄 em progresso · 📋 planejado · 🧪 beta), **Para quem** (end-user / tenant / admin / ops) e, quando aplicavel, **Limites** observaveis pelo usuario.

### <Value Stream 1 Name>

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **<Feature A>** | ✅ epic NNN | end-user | <1-2 lines: what the user sees/does AND why it matters. No tech.> |
| **<Feature B>** | 🔄 epic NNN · previsao YYYY-MM-DD | tenant | ... |

### <Value Stream 2 — e.g., has observable limits>

| Feature | Status | Para | Valor | Limites |
|---------|--------|------|-------|---------|
| **<Feature C>** | 🔄 epic NNN · previsao YYYY-MM-DD | end-user + tenant | ... | ate 10 min por audio; pt-BR prioritario |

### <Value Stream 3...>
...

---

## Proximos ciclos e visao de longo prazo

| Feature | Horizonte | Valor |
|---------|-----------|-------|
| **<Feature X>** | Proximo — epic NNN | ... |
| **<Feature Y>** | Longo prazo | ... |

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

---

> **Proximo passo:** `/madruga:business-process <name>` — mapear fluxos core a partir do feature map priorizado.
```

### Generation Rules

1. **Value streams, not horizons.** Organize shipped + in-progress features by user capability group (e.g., "Entrega de conversas", "Conteudo de midia", "Controle operacional", "Compliance"). 3-6 streams typical. Rationale: stream-based organization matches how PMs/marketers/users think; adding a new epic just flips a Status badge rather than shuffling features across tables.

2. **Features per stream: 3-8.** If a stream has <3, merge it; if >8, split it. There is no global cap — a mature platform legitimately carries 20-30 features.

3. **Status vocabulary is FIXED** (reject free text):
   - `✅ <epic-ref>` — live/shipped (epic ref mandatory: `epic NNN` or epic slug)
   - `🔄 <epic-ref> · previsao YYYY-MM-DD` — in progress (epic ref + date mandatory)
   - `📋 <epic-ref>` — planned with committed epic (epic ref mandatory)
   - `🧪 <epic-ref>` — beta/experimental (epic ref mandatory)

4. **Para quem vocabulary is FIXED** (reject free text): `end-user | tenant | admin | ops` (or combinations joined by `+`, e.g., `end-user + tenant`). `ops` = internal operations (e.g., Pace ops team).

5. **Valor column** merges description + why-it-matters into a single sentence or two. ALWAYS user-language. "Agent replies to messages" not "webhook receives payload and sends to pipeline". Include the why inline ("reduces handoff in 30-50% of cases").

6. **Limites column is optional** — include only when the feature has observable constraints the user will hit (size, duration, quantity, format). Omit the column entirely for streams where no feature has limits.

7. **Next + Later combined** into a single "Proximos ciclos e visao de longo prazo" table with a `Horizonte` column: `Proximo — epic NNN` for committed-planned, `Longo prazo` for unscheduled. Avoids a three-table maze.

8. **Numbered epic references are metadata-only.** Epics appear in `Status` and `Horizonte` columns. They must NOT appear in the `Valor` column, narrative, principles, or boundaries. If a feature's description is "we added X in epic NNN", rewrite to "<agent/tenant/user> can now <X>" — the epic lives in Status.

9. **Principles:** max 5. Derive from the vision if it exists. Macro product principles (e.g., "one true source of truth for all data"), not technical implementation choices.

10. **Boundaries:** min 2, max 5. Clear statements of what the product explicitly does NOT do, with business reasoning.

11. **No technical actors:** automated systems, background processes, or runtime engines are NOT personas and must not appear. Personas belong in vision.md.

### Maintenance (post-reconcile ownership)

After every `/madruga:reconcile` that ships features:

1. Flip `🔄 → ✅` for every feature the epic delivered.
2. Remove corresponding rows from "Proximos ciclos" (they graduated into a value stream).
3. Add new rows if the epic introduced capabilities not previously listed.
4. Update `Limites` if the epic tightened or relaxed a user-observable constraint.

**If solution-overview drifts (e.g., a new user-facing capability is missing):** update solution-overview in place — DO NOT create a parallel `features.md`. There is exactly one feature catalog per platform, and it lives here.

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Zero technical terms in prose columns (scan Valor column + narrative + principles + boundaries for: API, SDK, framework, database, backend, frontend, deploy, server, endpoint, middleware, cache, queue, Python, Redis, Docker, Supabase, pgvector, webhook, microservice, CI/CD, ADR, pipeline, module, Copier, Jinja2, Astro, Starlight, Mermaid, WAL, FTS5, SQLite, systemd, asyncio, daemon, ruff, Vite, React, Tailwind, copier) | Rewrite in product language |
| 2 | Every feature has Status from fixed enum (`✅` / `🔄` / `📋` / `🧪`) with epic ref | Coerce to enum; add missing epic ref |
| 3 | Every feature has Para from fixed enum (`end-user` / `tenant` / `admin` / `ops` or `+`-joined combinations) | Coerce to enum |
| 4 | Every feature row has both Status AND Valor filled | Complete missing cells |
| 5 | No `epic NNN` references in Valor column or narrative prose (regex scan scoped to prose) | Move epic ref to Status column |
| 6 | 3-6 value streams (section `###` count under `## Mapa de Features`) | Merge or split streams |
| 7 | 3-8 features per value stream | Merge or split |
| 8 | Max 5 principles | Prioritize |
| 9 | `O que NAO fazemos` present with 2-5 entries | Add/trim boundaries |
| 10 | No "Personas" section exists (personas belong in vision.md) | Remove and reference vision.md |
| 11 | No parallel `business/features.md` exists in the platform directory | Delete it; merge content into solution-overview |

## Error Handling

| Problem | Action |
|---------|--------|
| User does not know the features | Ask: "What does your user do in the product today? What would you like them to do?" and derive features |
| Features do not fit a single stream cleanly | Keep feature in primary stream; mention cross-cutting dimension in Valor (e.g., "shared with Admin via Trace Explorer") |
| No clear value streams | Start from vision's "Critical Battles" or roadmap epic groupings |
| Vision exists but solution-overview does not | Read vision and derive features from segments and critical battles, then group into streams |
| Platform already has a solution-overview in old 3-table format (Implementado/Next/Later) | Migrate: group Implementado features into value streams using reconcile reports as ground truth; combine Next+Later into "Proximos ciclos". Offer diff for user approval. |
| Platform has a parallel `business/features.md` | Merge its content into solution-overview (value streams already organized there) and delete features.md. Flag to user. |
| User lists technical features | Translate to user language. "SQLite state store" → "Progress tracking" |

---
handoff:
  from: solution-overview
  to: business-process
  context: "Feature map agrupado por value stream. Business process deve mapear fluxos core a partir dos streams."
  blockers: []
