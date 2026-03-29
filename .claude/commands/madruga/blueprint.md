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

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume [concern X] is needed because [reason]. Correct?" |
| **Trade-offs** | "For logging: [structured JSON] (simple, easy search) or [ELK stack] (powerful, complex). Which?" |
| **Gaps** | "ADRs do not cover [observability/security]. Define now?" |
| **Challenge** | "Do you really need [concern]? Netflix has it, but at 100x your scale." |

Wait for answers BEFORE generating.

### 2. Generate Blueprint

Check if the template exists at `.specify/templates/platform/template/engineering/blueprint.md.jinja` and follow its structure.

```markdown
---
title: "Engineering Blueprint"
updated: YYYY-MM-DD
---
# <Name> — Engineering Blueprint

> Engineering decisions, cross-cutting concerns, and topology. Last updated: YYYY-MM-DD.

---

## Technology Stack

[Summary table derived from ADRs — do not repeat details, reference ADR-NNN]

| Category | Choice | ADR |
|----------|--------|-----|
| ... | ... | ADR-NNN |

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

## Deploy Topology

[Mermaid diagram with containers/services and how they connect]

```mermaid
graph LR
  ...
```

| Container | Technology | Responsibility |
|-----------|-----------|----------------|
| ... | ... | ... |

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

## Error Handling

| Problem | Action |
|---------|--------|
| ADRs incomplete or conflicting | List conflicts; request resolution before generating |
| Very simple project (1 service) | Generate a minimal blueprint — do not force complexity |
| Too many concerns (>7) | Ask: "What are the 5 most critical ones right now?" |
| NFRs without baseline | Mark [TO DEFINE] and suggest defaults by app type |
| No codebase-context | OK — treat as greenfield |

---
handoff:
  from: blueprint
  to: domain-model
  context: "Blueprint aprovado com concerns, NFRs, e folder structure. Domain model deve modelar bounded contexts."
  blockers: []
