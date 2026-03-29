---
description: Generate a business vision one-pager using the Playing to Win framework for any platform
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt the user."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Generate Solution Overview
    agent: madruga/solution-overview
    prompt: Generate solution overview based on the validated vision
---

# Vision One-Pager — Playing to Win

Generate a 1-page business vision document (markdown, ~150 lines) using the Playing to Win framework (Lafley & Martin). The output is purely business-oriented — zero technical jargon.

## Cardinal Rule: ZERO Technical Content

This document is **exclusively about the business**. Technical decisions, architecture, and implementation belong in other artifacts (ADRs, technical roadmap, C4 diagrams).

**NEVER include in the output:**
- Names of technologies, frameworks, languages, databases, or libraries (e.g., Python, FastAPI, Redis, Supabase, pgvector, React, Docker)
- Architecture terms (e.g., RLS, API, SDK, middleware, cache, queue, webhook, endpoint, microservice, monolith)
- References to ADRs, technical specs, or C4 diagrams
- Infrastructure details (e.g., deploy, CI/CD, server, container, cloud provider)
- Names of internal development tools (e.g., LangFuse, Bifrost, Evolution API)

**Permitted exceptions:** proper names of competitor products/companies (Botpress, Blip) and business terms that overlap with technical terms (e.g., "platform", "channel", "automation").

**When in doubt:** if a sentence only makes sense to an engineer, it does not belong in this document. Rewrite it in language that an investor or business executive would understand.

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-business.md`.

## Usage

- `/vision fulano` — Generate one-pager for platform "fulano"
- `/vision` — Prompt for the platform name and collect context

## Output Directory

Save to `platforms/<name>/business/vision.md`. Create the directory if it does not exist.

## Instructions

### 1. Collect Context + Ask Questions

**If `$ARGUMENTS.platform` is provided:** use it as the platform name.
**If empty:** ask the user for the name.

In both cases, check whether `platforms/<name>/business/vision.md` already exists. If it does, read it as a baseline.

If the user has research docs in the platform directory (`research/`), read them to extract data before asking questions.

Collect the following from the user (ask everything at once, not one at a time):

| # | Question | Example |
|---|----------|---------|
| 1 | **Thesis** — What it does, for whom, how? (1-2 sentences) | "Config-driven AI WhatsApp agent platform for Brazilian SMBs" |
| 2 | **Target customer** — Persona, pain, current alternative | "SMB owner, manual service doesn't scale, uses rigid chatbot" |
| 3 | **Market** — TAM, SAM, SOM (or estimates) | "6M Brazilian SMBs on WhatsApp, SOM 500 in 18m" |
| 4 | **Moat** — What is hard to copy? (1-2 real differentiators) | "Only one that does AI in WhatsApp groups" |
| 5 | **Competitors** — 3-5 relevant players | "Blip, Botpress, Respond.io, Octadesk" |
| 6 | **Success metrics** — North Star + targets at 6m and 18m | "Conversations resolved/month. 50->500 clients, R$25K->250K MRR" |
| 7 | **Pricing** — Model and tiers (if defined) | "Free R$0, Starter R$197, Growth R$497, Business R$997" |
| 8 | **Risks** — Top 3-5 business risks | "Meta changes pricing, LLM cost explodes, single channel" |

After receiving answers, identify implicit assumptions and present structured questions:

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume [X extracted from answers]. Correct?" |
| **Trade-offs** | "[Moat A] more defensible or [Moat B] more scalable?" |
| **Gaps** | "I have no data about [market/pricing]. Do you define it or should I estimate with [VALIDAR]?" |
| **Provocation** | "[Obvious positioning], but [alternative] may be better because [reason]." |

Wait for answers BEFORE generating.

### 2. Generate One-Pager

Write the document with exactly **7 sections**, following this template. All generated content MUST be in PT-BR:

```markdown
---
title: "Business Vision"
updated: YYYY-MM-DD
---
# <Name> — Business Vision

> Framework: Playing to Win (Lafley & Martin). Ultima atualizacao: YYYY-MM-DD.

---

## 1. Tese & Aspiracao

[Thesis paragraph: what it does, for whom, how. 3-4 lines max.]

[Structural differentiator in bold — the real moat. 2 lines.]

**North Star Metric:** [metric]

| Horizonte | [KPI 1] | [KPI 2] | [KPI 3] | [KPI 4] |
|-----------|---------|---------|---------|---------|
| **6 meses** | ... | ... | ... | ... |
| **18 meses** | ... | ... | ... | ... |

---

## 2. Where to Play

### Mercado
- **TAM:** [number + source]
- **SAM:** [segment + number]
- **SOM:** [achievable in 18m]

### Cliente-alvo
| Dimensao | Detalhe |
|----------|---------|
| **Persona** | ... |
| **Dor principal** | ... |
| **Alternativa atual** | ... |
| **Job-to-be-Done** | ... |

### Segmentos prioritarios
1. **[P1]** — ...
2. **[P2]** — ...
3. **[P3]** — ...

### Onde NAO jogamos
| NAO e... | Porque |
|----------|--------|
| ... | ... |

---

## 3. How to Win

### Moat estrutural: [moat name]
[2 paragraphs: what it is + why it is hard to copy]

### Posicionamento
[1 paragraph: who it does NOT compete against + on which axis it competes]

### Batalhas criticas
| # | Batalha | Metrica de sucesso | Por que importa |
|---|---------|-------------------|-----------------|
| 1 | ... | ... | ... |
| 2 | ... | ... | ... |
| 3 | ... | ... | ... |
| 4 | ... | ... | ... |
| 5 | ... | ... | ... |

---

## 4. Landscape

| Player | Foco | Preco entry | [Differentiator column] |
|--------|------|-------------|------------------------|
| ... | ... | ... | ... |
| **[Platform]** | ... | ... | **Sim** |

**Tese competitiva:** [1 paragraph: why the space is empty and how it expands]

---

## 5. Riscos & Premissas

### Riscos
| # | Risco | Prob. | Impacto | Mitigacao |
|---|-------|-------|---------|-----------|
| 1 | ... | ... | ... | ... |

### Premissas criticas
Se qualquer uma for falsa, a tese precisa ser revisada:
1. ...
2. ...

---

## 6. Modelo de Negocio

### Pricing
| Tier | Preco/mes | [Unit] | [Resource 1] | [Resource 2] |
|------|-----------|--------|--------------|--------------|
| ... | ... | ... | ... | ... |

### [Tailwind or structural cost advantage]
[2-3 lines]

### Unit economics
- **Custo variavel:** ...
- **Margem bruta target:** ...
- **Break-even por [unit]:** ...

---

## 7. Linguagem Ubiqua

| Termo | Definicao | Exemplo |
|-------|-----------|---------|
| **[Term 1]** | [short definition — what it means in this business context] | [usage in a sentence] |
| **[Term 2]** | ... | ... |
| **[Term N]** | ... | ... |

> Padronizar estes termos em todos os documentos, codigo, e comunicacao do projeto.
```

### Auto-Review Additions

Beyond contract-base checks, verify:

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Zero technical terms (scan for: API, SDK, framework, database, backend, frontend, deploy, server, endpoint, middleware, cache, queue, Python, Redis, Docker, webhook, microservice, CI/CD, ADR) | Rewrite in business language. See Cardinal Rule. Exception: proper names of competitor products. |
| 2 | Every metric has a number | Add number or mark `[VALIDAR]` |
| 3 | No section exceeds 30 lines | Trim — a one-pager has no long sections |
| 4 | Total under 200 lines | Condense the largest sections |
| 5 | Landscape has max 5 players | Remove the least relevant |
| 6 | Moat is truly defensible (not easily copied feature) | Reframe or be honest |
| 7 | Ubiquitous Language section present with min 5 terms | Add domain terms |

## Error Handling

| Problem | Action |
|---------|--------|
| User does not know the moat | Ask: "What do you do that a competitor would take >6 months to copy?" If there is none, be honest: mark as `[DEFINIR]` |
| No market data | Use estimates with `[ESTIMAR]` and recommend sources (SEBRAE, IBGE, Statista) |
| Platform already has a vision | Read as baseline, ask whether to rewrite from scratch or iterate |
| More than 5 relevant competitors | Force prioritization: "Which 4 define the competitive space?" |

---
handoff:
  from: vision
  to: solution-overview
  context: "Vision validada. Solution overview deve detalhar feature map e priorização."
  blockers: []
