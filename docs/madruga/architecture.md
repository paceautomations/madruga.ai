# Architecture Best Practices — madruga.ai

Reference document consolidating architecture frameworks and best practices
applicable to the madruga.ai platform ecosystem. Derived from industry-standard
references and adapted for a multi-platform architecture documentation system.

---

## 1. Foundational Principles

### 1.1 Boundaries Are Everything

> "A bounded context delimits the applicability of a particular model."
> — Vaughn Vernon, Implementing DDD

Every framework converges on this: DDD bounded contexts, microservice boundaries,
C4 container boundaries, cell-based architecture walls, Team Topologies team APIs.

**How we apply it:**
- Each platform is a bounded context with its own ubiquitous language
- `platform.yaml` is the aggregate root — enforces invariants (fields, lifecycle)
- Inter-platform dependencies go through explicit interfaces, never direct file access
- Skill contracts define clear input/output boundaries per pipeline node

### 1.2 Decisions Are First-Class Citizens

> "The goal of ADRs is to capture the motivation behind a decision, not just the decision itself."
> — Michael Nygard

**How we apply it:**
- ADRs in Nygard format with status lifecycle (proposed → accepted → superseded)
- 1-way-door gates require explicit per-decision confirmation with >=3 alternatives
- Decision classification: 1-way-door (irreversible, needs ADR) vs 2-way-door (reversible, inline doc)
- ADR cross-references via `supersedes` / `depends-on` chains

### 1.3 Fitness Over Perfection

> "Build evolutionary architectures — architectures that support guided, incremental change."
> — Neal Ford & Rebecca Parsons

**How we apply it:**
- Auto-review checklists in every skill (triggered fitness functions)
- Judge skill applies 4-persona fitness assessment (Architecture, Bugs, Simplicity, Stress)
- Prerequisite checks enforce pipeline ordering
- Reconcile detects drift between docs and implementation

### 1.4 Cognitive Load as a Design Constraint

> "The purpose of the platform is to reduce cognitive load on stream-aligned teams."
> — Matthew Skelton & Manuel Pais, Team Topologies

**How we apply it:**
- Golden paths via Copier templates (opinionated, easy defaults)
- CLI abstracts complexity (`platform_cli.py use/status/lint`)
- Structured questions reduce ambiguity (Assumptions, Trade-offs, Gaps, Challenge)
- Gate types adapt to context (auto for safe ops, human for key decisions)

### 1.5 Diagrams as Code, Docs as Code

> "Keep architecture descriptions close to code, version-controlled, and generated from models."
> — Simon Brown, C4 Model

**How we apply it:**
- Mermaid inline diagrams as source of truth for architecture models (ADR-020)
- Diagrams live alongside prose in the same `.md` files — context never drifts
- Portal renders diagrams via `astro-mermaid` — zero custom tooling
- GitHub/Starlight/any Markdown viewer renders natively

---

## 2. Architecture Documentation Structure

Based on C4 Model + Arc42 + IEEE 42010, each platform should maintain:

### 2.1 C4 Hierarchy (mandatory) — Mermaid Inline (ADR-020)

| Level | Artifact | Mermaid Type | Document | Purpose |
|-------|----------|-------------|----------|---------|
| L1 Context | System Landscape | `graph LR` | `blueprint.md` "Deploy Topology" | Who uses the system, what external systems exist |
| L2 Containers | Container Diagram | `graph LR` + subgraphs | `blueprint.md` "Containers" | Deployable units, tech choices, data stores |
| L3 Components | Context Map | `flowchart LR` | `domain-model.md` "Context Map" | Bounded contexts, modules, DDD patterns |
| L4 Code | Class diagrams | `classDiagram` | `domain-model.md` `<details>` per BC | Aggregates, entities, invariants |

### 2.2 Supplementary Views

| View | Mermaid Type | Document | Purpose |
|------|-------------|----------|---------|
| Business Flow | `flowchart TD` + `sequenceDiagram` | `process.md` | Sequence of interactions for key scenarios |
| Deploy Topology | `graph LR` | `blueprint.md` | Infrastructure + connectivity |
| Pipeline DAG | `graph LR` | `roadmap.md` | Epic dependencies and sequencing |

### 2.3 Documentation Sections (Arc42-aligned)

| # | Section | Pipeline Artifact | Status |
|---|---------|------------------|--------|
| 1 | Introduction & Goals | `business/vision.md` | Covered |
| 2 | Constraints | `engineering/blueprint.md` | Covered |
| 3 | Context & Scope | `blueprint.md` (Deploy Topology) | Covered |
| 4 | Solution Strategy | `business/solution-overview.md` | Covered |
| 5 | Building Block View | `domain-model.md` + `blueprint.md` | Covered |
| 6 | Runtime View | `process.md` (sequence diagrams) | Covered |
| 7 | Deployment View | `blueprint.md` (Deploy Topology) | Covered |
| 8 | Cross-cutting Concepts | `blueprint.md` (Cross-Cutting Concerns) | Covered |
| 9 | Architecture Decisions | `decisions/ADR-*.md` | Covered |
| 10 | Quality Scenarios | — | Gap |
| 11 | Risks & Technical Debt | — | Gap |
| 12 | Glossary | `blueprint.md` (Glossario Tecnico) | Covered |

---

## 3. Mermaid Diagram Conventions (ADR-020)

### 3.1 File Structure (per platform)

Diagrams live **inline** in the `.md` files that provide their context — no separate diagram files:

```
platforms/<name>/
  engineering/blueprint.md       # Deploy Topology (L1) + Containers (L2)
  engineering/domain-model.md    # Context Map (L3) + Class diagrams (L4)
  engineering/context-map.md     # DDD relationships between bounded contexts
  business/process.md            # Business flows (flowchart + sequence)
```

### 3.2 Pyramid of Detail

| Level | Mermaid Type | Document | What it shows |
|-------|-------------|----------|---------------|
| L1 | `graph LR` | blueprint.md "Deploy Topology" | System + externals + connectivity |
| L2 | `graph LR` + subgraphs | blueprint.md "Containers" | Internal containers + integrations |
| L3 | `flowchart LR` | domain-model.md "Context Map" | Bounded contexts + DDD relations |
| L4 | `classDiagram` | domain-model.md `<details>` per BC | Aggregates, entities, invariants |
| L5 | `flowchart TD` + `sequenceDiagram` | process.md | End-to-end business flow |

### 3.3 Diagram Size Guideline

- Keep each Mermaid block under ~50 lines — split into multiple diagrams if larger
- Use `<details>` blocks for drill-down into bounded contexts or subsystems
- Cross-reference between levels using markdown links (`[→ See containers](../engineering/blueprint/#containers-l2)`)

### 3.4 Naming Conventions in Diagrams

| Element | Convention | Example |
|---------|-----------|---------|
| Subgraph labels | Title Case with purpose | `subgraph server["VPS (Production)"]` |
| Node IDs | camelCase | `Easter`, `DB`, `CLI` |
| Edge labels | quoted strings | `-->\|"subprocess"\|` |
| Domain classification | Style classes | `:::core`, `:::supporting`, `:::generic` |

---

## 4. DDD Context Map Patterns

### 4.1 Relationship Kinds

| Kind | When to Use | Visual |
|------|------------|--------|
| `acl` (Anti-Corruption Layer) | Isolating internal model from external format | Green solid |
| `conformist` | Accepting external API format as-is | Amber dashed |
| `customerSupplier` | One context serves another; supplier defines contract | Blue solid |
| `pubSub` | Async, decoupled event-based integration | Gray dotted |
| `sync` | Synchronous call | Secondary solid |
| `async` | Asynchronous call | Indigo dashed |

### 4.2 When to Use Each Pattern

- **ACL**: When integrating with external systems whose schema you don't control (APIs, legacy)
- **Conformist**: When the cost of translation exceeds the benefit (e.g., observability SDKs)
- **Customer-Supplier**: When one team/context explicitly serves another's needs
- **Pub-Sub**: When contexts need decoupling and eventual consistency is acceptable
- **Shared Kernel**: Avoid unless contexts are very tightly coupled (not in current spec)

---

## 5. Architecture Fitness Functions

### 5.1 Pipeline-Level (automated)

| Function | What it Checks | Trigger |
|----------|---------------|---------|
| Prerequisite check | Dependencies satisfied before skill runs | Pre-skill |
| Auto-review checklist | 5-8 quality checks per artifact | Post-skill |
| Judge (4 personas) | Architecture, bugs, simplicity, stress | Post-implement |
| Reconcile | Docs match implementation | Post-epic |
| Skill-lint | Skill contracts valid (frontmatter, handoffs) | Post-edit |

### 5.2 Model-Level (recommended additions)

| Function | What it Checks | How to Implement |
|----------|---------------|-----------------|
| Cross-reference coverage | Every diagram level links to adjacent levels | Grep for markdown links |
| Orphan detection | No elements without relationships in context map | Manual review |
| Diagram size | Each Mermaid block under ~50 lines | Lint script |
| Label coverage | Every node in Mermaid has a descriptive label | Manual review |
| Consistency | Same names across L1-L5 diagrams | Grep + review |

---

## 6. Key Patterns from Reference Library

### From Building Microservices (Sam Newman)
- **Independent deployability** — model services around business domains
- **Consumer-driven contracts** — interfaces defined by provider, tested by consumer
- **Strangler Fig** — migrate incrementally, not big-bang

### From Clean Code (Robert Martin)
- **Single Responsibility** — one reason to change per module
- **Command-Query Separation** — functions do or return, never both
- **Newspaper Metaphor** — organize top-down: summary first, details later

### From The Pragmatic Programmer (Hunt/Thomas)
- **DRY** — single authoritative representation of every piece of knowledge
- **Orthogonality** — independent components; changes don't ripple
- **Tracer Bullets** — build end-to-end skeleton first, flesh out later
- **Design by Contract** — explicit preconditions, postconditions, invariants

### From Designing Data-Intensive Applications (Kleppmann)
- **Reliability > Scalability > Maintainability** — in that order
- **Schema evolution is inevitable** — design for compatibility
- **Event logs as source of truth** — derive state from events

### From Domain-Driven Design (Vernon)
- **Ubiquitous Language** — same terms in code, docs, and conversation
- **Aggregates** — cluster with root that enforces invariants
- **Domain Events** — capture what happened as first-class objects

### From Thinking in Systems (Meadows)
- **Feedback loops drive behavior** — auto-review = balancing loop
- **Leverage points** — small changes in right place create large shifts
- **Resilience over optimization** — keep slack, don't over-optimize

### From Team Topologies (Skelton/Pais)
- **Platform as a Product** — treat pipeline users as customers
- **Cognitive Load** — if the pipeline feels bureaucratic, simplify
- **Fast Flow** — optimize for speed of delivery, not utilization

---

## 7. Identified Gaps & Recommendations

| # | Gap | Priority | Recommendation |
|---|-----|----------|---------------|
| 1 | **No quality scenarios** | LOW | Add Arc42 section 10 with measurable quality attributes |
| 2 | **No risk register** | LOW | Track risks as first-class artifacts alongside ADRs |
| 3 | **No automated diagram lint** | MEDIUM | Script to validate Mermaid block size and cross-references |
| 4 | **ADR review cadence missing** | LOW | Quarterly review of ADR relevance |

---

## 8. References

### Books
- Sam Newman — *Building Microservices* (2nd ed.)
- Robert C. Martin — *Clean Code*
- Andrew Hunt & David Thomas — *The Pragmatic Programmer* (20th Anniversary)
- Martin Kleppmann — *Designing Data-Intensive Applications*
- Vaughn Vernon — *Implementing Domain-Driven Design*
- Will Larson — *Staff Engineer: Leadership Beyond the Management Track*
- Tanya Reilly — *The Staff Engineer's Path*
- Donella Meadows — *Thinking in Systems*

### Frameworks & Standards
- Simon Brown — C4 Model (https://c4model.com)
- Arc42 — Architecture Documentation Template (https://arc42.org)
- IEEE 42010 — Systems and Software Engineering Architecture Description
- TOGAF — The Open Group Architecture Framework
- 4+1 View Model — Philippe Kruchten

### Modern Practices
- Cell-Based Architecture — WSO2
- Platform Engineering — Team Topologies / CNCF
- Architecture Decision Records — Michael Nygard
- Evolutionary Architecture — Neal Ford & Rebecca Parsons
- Team Topologies — Matthew Skelton & Manuel Pais
