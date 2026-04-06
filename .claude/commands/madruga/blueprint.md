---
description: Generate an engineering blueprint with cross-cutting concerns, NFRs, and deploy topology for any platform
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt the user."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Generate Domain Model (DDD)
    agent: madruga/domain-model
    prompt: Generate DDD domain model based on the blueprint and business flows
---

# Blueprint — Platform Engineering

Generate an engineering blueprint (~200 lines) covering cross-cutting concerns, NFRs, deploy topology, data map, and technical glossary. Reference ADRs and the business layer.

## Cardinal Rule: ZERO Over-Engineering

If you cannot explain a decision in 1 paragraph, it is too complex. Every architectural choice must be **the simplest thing that works** for the current context.

**NEVER:**
- Add an abstraction layer "for the future"
- Choose a complex technology when a simple one suffices
- Copy FAANG architecture without justifying it for the project's scale
- Include a cross-cutting concern without a real problem it solves

**ALWAYS ask:** "Is this the simplest thing that works?"

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md` + `.claude/knowledge/pipeline-contract-engineering.md`.

## Persona

Pragmatic architect — simplicity first, justifies every component. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/blueprint fulano` — Generate blueprint for the "fulano" platform
- `/blueprint` — Prompt for the platform name

## Output Directory

Save to `platforms/<name>/engineering/blueprint.md`.

## Instructions

### 1. Collect Context + Ask Questions

**Required reading:**
- `decisions/ADR-*.md` — all approved technology decisions
- `business/*` — vision, solution-overview, process
- `research/codebase-context.md` — if present (brownfield project)

**For each cross-cutting concern:**
- Use Context7 to research best practices for the stack chosen in the ADRs
- Web search: "[technology] [concern] best practices 2026"

**Structured Questions:**

Every question MUST present **>=2 options with pros/cons/risks and a recommendation**, regardless of category. Format:

> **A)** Option — Pros: ... Cons: ... Risks: ...
> **B)** Option — Pros: ... Cons: ... Risks: ...
> **Recommendation:** [A or B] because [reason].

| Category | Pattern | Example |
|----------|---------|---------|
| **Assumptions** | "I assume [X] because [ref]. Alternatives:" + options | "Observability: **A)** structlog + SQLite custom — Pros: ~100 LOC, zero deps. Cons: no standard export. Risks: low. **B)** OpenTelemetry — Pros: industry standard. Cons: heavy for 1 operator. Risks: overengineering. **Rec:** A." |
| **Trade-offs** | "For [concern]: [A] or [B]?" + options | "Error handling: **A)** Exception hierarchy — Pros: Python idiomatic, granular catch. Cons: none for this scale. **B)** Result types — Pros: explicit, no hidden throws. Cons: boilerplate. **Rec:** A." |
| **Gaps** | "ADRs do not cover [X]. Options:" + options | "Secrets management: **A)** Env vars (current) — Pros: simple. Cons: no rotation. **B)** Vault/SOPS — Pros: rotation, audit. Cons: infra overhead. **Rec:** A for single-machine." |
| **Challenge** | "Do you really need [concern]? Alternatives:" + options | "Auth: **A)** Skip (single operator, CLI only) — Pros: zero complexity. Cons: no multi-user. **B)** Basic token auth — Pros: future-proof. Cons: premature. **Rec:** A." |

Wait for answers BEFORE generating.

### 2. Generate Blueprint

Check if the template exists at `.specify/templates/platform/template/engineering/blueprint.md.jinja` and follow its structure.

```markdown
---
title: "Engineering Blueprint"
updated: YYYY-MM-DD
sidebar:
  order: 1
---
# <Name> — Engineering Blueprint

> Engineering decisions, cross-cutting concerns, and topology. Last updated: YYYY-MM-DD.

---

## Technology Stack

[Summary table derived from ADRs — include alternatives considered and why they were rejected]

| Category | Choice | ADR | Alternatives Considered |
|----------|--------|-----|------------------------|
| ... | ... | ADR-NNN | [Alt A] (rejected: reason), [Alt B] (rejected: reason) |

---

## Deploy Topology

[Mermaid diagram — infrastructure-level: where things run, how they connect. NOT C4 L2 detail.]

```mermaid
graph LR
  ...
```

> Detalhamento C4 L2 dos containers → ver [containers.md](../containers/)

---

## Folder Structure

[Annotated directory tree + conventions]

```text
project-root/
├── src/           # [purpose]
├── tests/         # [purpose]
└── ...
```

| Convention | Rule |
|------------|------|
| ... | ... |

---

## Cross-Cutting Concerns

### Authentication & Authorization
[Approach, pattern, reference to ADR if applicable]

### Logging & Observability
[Structured logging, metrics, tracing — the minimum necessary]

### Error Handling
[Error handling pattern, error codes, retry policy]

### Configuration
[How configs are managed — env vars, config files, feature flags]

### Security
[Relevant OWASP top 10, input validation, secrets management]

[Add only concerns the project ACTUALLY needs]

---

## NFRs (Non-Functional Requirements)

| NFR | Target | Metric | How to Measure |
|-----|--------|--------|----------------|
| P95 Latency | < Xms | response time | [tool] |
| Availability | X% | uptime | [tool] |
| Throughput | X req/s | requests/sec | [tool] |
| Recovery | RTO Xmin | time to recover | [process] |

---

## Data Map

| Store | Type | Data | Estimated Size |
|-------|------|------|----------------|
| ... | ... | ... | ... |

---

## Technical Glossary

| Term | Definition |
|------|-----------|
| ... | ... |
```

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every NFR have a measurable target? | Add a number |
| 2 | Does every concern have a justification ("why we need it")? | Justify or remove |
| 3 | No over-engineering ("for the future")? | Simplify |
| 4 | References ADRs for stack decisions? | Add references |
| 5 | Max 200 lines? | Condense |
| 6 | References real-world patterns (companies/projects)? | Add |
| 7 | Does the topology include a Mermaid diagram? | Add |
| 8 | Does each decision answer "is this the simplest thing that works?"? | Revalidate |
| 9 | Does every tech stack choice list alternatives considered? | Add alternatives + why rejected |
| 10 | Does every cross-cutting concern show >=2 options with pros/cons? | Add options |
| 11 | Does Deploy Topology stay infra-level (no C4 L2 container detail)? | Move container detail to containers.md |
| 12 | Does Folder Structure include annotated directory tree? | Add it |

## Error Handling

| Problem | Action |
|---------|--------|
| ADRs incomplete or conflicting | List conflicts; request resolution before generating |
| Very simple project (1 service) | Generate a minimal blueprint — do not force complexity |
| Too many concerns (>7) | Ask: "What are the 5 most critical ones right now?" |
| NFRs without baseline | Mark [TO DEFINE] and suggest defaults by app type |
| No codebase-context | OK — treat as greenfield |

