---
description: Research technology alternatives with deep research and decision matrices for any platform
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt the user."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Generate ADRs
    agent: madruga/adr
    prompt: "Generate Architecture Decision Records from the validated technology decisions. WARNING: 1-way-door gate — ADRs define the project's technical foundation."
---

# Tech Research — Technology Alternatives Research

Research technology alternatives using parallel deep research for each decision. Generate a decision matrix with a minimum of 3 alternatives per decision, covering cost, performance, complexity, community, and fit.

## Cardinal Rule: ZERO Opinion Without Research

Every technology recommendation MUST be backed by research evidence. No suggestions based on personal preference or "everyone uses it". Every claim must have a source.

**NEVER:**
- Recommend a technology without researching real alternatives
- Base a decision on popularity without evaluating fit for the project
- Omit viable alternatives to force a particular choice
- Present benchmarks or data without a verifiable source
- Ignore the project's specific context (size, team, budget)
- Fabricate data or sources. If research (Context7, web search) returns no data for an alternative, mark the entire row as `[DADOS INSUFICIENTES]` and recommend deferring the decision

**Every factual claim MUST have a verifiable URL or reference.** No URL → mark as `[FONTE NÃO VERIFICADA]`.

## Persona

Senior Tech Research Analyst. Objective, data-driven, skeptical. Research before opining. When data is unavailable, mark [INCONCLUSIVE RESEARCH]. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/tech-research fulano` — Research alternatives for platform "fulano"
- `/tech-research` — Prompt for the platform name

## Output Directory

Save to `platforms/<name>/research/tech-alternatives.md`.

## Instructions

### 0. Prerequisites

Run `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill tech-research` and parse the JSON output.
- If `ready: false`: ERROR — list missing dependencies and which skill generates each one.
- If `ready: true`: read artifacts listed in `available` as context.
- Read `.specify/memory/constitution.md` to validate the output against project principles.

### 1. Collect Context + Identify Decisions

**Required reading:**
- `business/vision.md` — business context, metrics, expected scale
- `business/solution-overview.md` — features and priorities
- `business/process.md` — business flows and implicit requirements
- `research/codebase-context.md` — (if it exists) existing stack and detected patterns (brownfield)

**Identify required technology decisions:**

From the business artifacts, list all technology decisions that need to be made. Typical categories:

| Category | Example Decision |
|----------|-----------------|
| Language/Runtime | Python vs Node.js vs Go |
| Web Framework | FastAPI vs Express vs Gin |
| Database | PostgreSQL vs SQLite vs MongoDB |
| Cache/Messaging | Redis vs Memcached vs RabbitMQ |
| Infrastructure | Docker + K8s vs Serverless vs VPS |
| Authentication | JWT vs Session vs OAuth provider |
| Monitoring | Datadog vs Grafana vs CloudWatch |

**Structured Questions (present BEFORE researching):**

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume the team has experience with [X]. Correct?" / "Are there budget, cloud provider, or pre-defined technology constraints?" |
| **Trade-offs** | "Prioritize [simplicity] or [scalability] at this point?" |
| **Gaps** | "I found no requirements about [observability/security/compliance]. Define now?" |
| **Provocation** | "The market standard is [X], but given the size of this project, [Y] may be more suitable." |

Wait for answers BEFORE starting research.

### 2. Generate Artifact — Research + Matrix

#### 2a. Deep Research with Parallel Subagents

**Spawn Agent subagents in parallel** — 1 per technology decision:

For each decision:
1. **Context7**: Use `mcp__context7__resolve-library-id` + `mcp__context7__query-docs` for up-to-date documentation on each alternative
2. **Web Search**: Search for benchmarks, recent comparisons (2025-2026), use cases
3. **Evaluate**: cost, performance, complexity, community size, fit for the project

**Each subagent must return:**
- Minimum 3 real alternatives (not fabricated)
- For each: pros, cons, metrics when available
- Source for each claim
- Recommendation with justification

#### 2b. Consolidate Decision Matrix

Consolidate results into `research/tech-alternatives.md`. All generated content MUST be in PT-BR:

```markdown
---
title: "Tech Alternatives"
updated: YYYY-MM-DD
---
# <Name> — Alternativas Tecnologicas

> Pesquisa de alternativas para decisoes tecnologicas. Ultima atualizacao: YYYY-MM-DD.

---

## Resumo Executivo

[2-3 paragraphs: project context, key decisions, recommended overall approach]

---

## Decisao 1: [Decision Title]

### Contexto
[Why this decision is necessary. What problem it solves.]

### Matriz de Alternativas

| Criterio | [Alt. A] | [Alt. B] | [Alt. C] |
|----------|----------|----------|----------|
| **Custo** | [$/month or free] | ... | ... |
| **Performance** | [relevant metric] | ... | ... |
| **Complexidade** | [low/medium/high] | ... | ... |
| **Comunidade** | [GitHub stars, downloads/month] | ... | ... |
| **Fit para projeto** | [high/medium/low + reason] | ... | ... |
| **Maturidade** | [years, stable version] | ... | ... |

### Analise Detalhada

**[Alternative A]:**
- Pros: [list]
- Cons: [list]
- Use cases: [companies/projects using it]
- Source: [link or reference]

**[Alternative B]:**
- Pros: [list]
- Cons: [list]
- Use cases: [companies/projects using it]
- Source: [link or reference]

**[Alternative C]:**
- Pros: [list]
- Cons: [list]
- Use cases: [companies/projects using it]
- Source: [link or reference]

### Recomendacao
**[Chosen alternative]** — [2-3 line justification referencing matrix criteria]

[If research is inconclusive: "[PESQUISA INCONCLUSIVA] — [Alt A] and [Alt B] are tied on [criterion]. Decision depends on [factor X]."]

---

## Decisao 2: [Title]
[Same format...]

---

## Tabela Consolidada

| # | Decisao | Recomendacao | Confianca | Gate |
|---|---------|-------------|-----------|------|
| 1 | [title] | [choice] | Alta/Media/Baixa | 1-way-door |
| 2 | ... | ... | ... | ... |

---

## Premissas e Riscos

### Premissas
1. [assumption 1 — mark [VALIDAR] if unconfirmed]
2. ...

### Riscos Tecnologicos
| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| ... | ... | ... | ... |

---

## Fontes
1. [source 1]
2. [source 2]
```

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Each decision has >= 3 real alternatives? | Research more |
| 2 | Each claim has a source? | Add source or mark [SEM FONTE] |
| 3 | No opinion without evidence? | Convert to sourced claim or remove |
| 4 | Matrix has measurable criteria? | Add metrics |
| 5 | Recommendation references the matrix in its justification? | Connect to criteria |
| 6 | Assumptions marked with [VALIDAR]? | Mark them |
| 7 | Max 350 lines total? | Condense |
| 8 | Research is recent (2025-2026)? | Verify dates |

### 4. Approval Gate: 1-Way-Door

**WARNING: This is a 1-way-door gate.** Technology decisions defined here constrain ALL downstream architecture (ADRs, blueprint, containers, DDD, epics).

Present to the user:

**Technology decisions summary:**

| # | Decision | Recommendation | Alternatives | Confidence |
|---|----------|---------------|-------------|-----------|
| 1 | ... | ... | [A, B, C] | High/Medium |

**For EACH decision, request explicit confirmation:**

> **Decision N: [title]**
> Recommendation: [chosen alternative]
> Rejected alternatives: [list with brief reason]
> Impact: [what this decision locks in for ADRs, blueprint, etc.]
>
> **Confirm [choice]? This defines [Y] for the rest of the project. (yes/no/adjust)**

Wait for confirmation on ALL decisions before saving.

### 5. Save + Report

1. Save to `platforms/<name>/research/tech-alternatives.md`
2. Report to the user:

```
## Tech Research Complete

**File:** platforms/<name>/research/tech-alternatives.md
**Decisions:** <N>
**Alternatives researched:** <total>
**Lines:** <N>

### Checks
[x] Each decision with >= 3 alternatives
[x] Claims with sources
[x] Matrix with measurable criteria
[x] Assumptions marked
[x] Explicit per-decision approval (1-way-door gate)

### Next Step
`/adr <name>` — Generate formal ADRs for each approved decision.
WARNING: ADR is also a 1-way-door gate.
```

## Error Handling

| Problem | Action |
|---------|--------|
| Context7 returns no docs for a technology | Use web search as fallback |
| Fewer than 3 real alternatives for a decision | Be honest: "only 2 viable alternatives" with justification |
| Inconclusive research (tie) | Mark [PESQUISA INCONCLUSIVA] and present both for human decision |
| Very new technology (insufficient data) | Mark [EMERGENTE — dados limitados] and recommend with caution |
| Incomplete business layer | List gaps and ask the user before researching |
| User rejects a decision at the gate | Ask for new constraints and re-research only that decision |

---
handoff:
  from: tech-research
  to: adr
  context: "Pesquisa tecnológica concluída. ADRs devem formalizar decisões. WARNING: 1-way-door."
  blockers: []
