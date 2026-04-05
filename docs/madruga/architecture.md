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
- LikeC4 DSL as single source of truth for architecture models
- `vision-build.py` generates markdown tables from exported JSON
- AUTO markers keep docs in sync with model changes
- Portal renders interactive diagrams from the same source

---

## 2. Architecture Documentation Structure

Based on C4 Model + Arc42 + IEEE 42010, each platform should maintain:

### 2.1 C4 Hierarchy (mandatory)

| Level | Artifact | LikeC4 File | Purpose |
|-------|----------|-------------|---------|
| L1 Context | System Landscape | `views.likec4` (index) | Who uses the system, what external systems exist |
| L2 Containers | Container Diagram | `platform.likec4` + `views.likec4` (containers) | Deployable units, tech choices, data stores |
| L3 Components | Context Map | `ddd-contexts.likec4` + `views.likec4` (contextMap) | Bounded contexts, modules, DDD patterns |
| L4 Code | (source code) | N/A | Classes, functions — live in the code repo |

### 2.2 Supplementary Views

| View | Artifact | Purpose |
|------|----------|---------|
| Dynamic / Business Flow | `views.likec4` (businessFlow) | Sequence of interactions for key scenarios |
| Scoped BC Details | `views.likec4` (*Detail) | Zoom into each bounded context |
| Relationships | `relationships.likec4` | All integrations (C4) + context map patterns (DDD) |
| Infrastructure | `infrastructure.likec4` | Shared infra elements (databases, caches, queues) |

### 2.3 Documentation Sections (Arc42-aligned)

| # | Section | Pipeline Artifact | Status |
|---|---------|------------------|--------|
| 1 | Introduction & Goals | `business/vision.md` | Covered |
| 2 | Constraints | `engineering/blueprint.md` | Covered |
| 3 | Context & Scope | `views.likec4` (index) | Covered |
| 4 | Solution Strategy | `business/solution-overview.md` | Covered |
| 5 | Building Block View | `ddd-contexts.likec4` + `platform.likec4` | Covered |
| 6 | Runtime View | `views.likec4` (businessFlow) | Partial |
| 7 | Deployment View | `infrastructure.likec4` | Gap |
| 8 | Cross-cutting Concepts | — | Gap |
| 9 | Architecture Decisions | `decisions/ADR-*.md` | Covered |
| 10 | Quality Scenarios | — | Gap |
| 11 | Risks & Technical Debt | — | Gap |
| 12 | Glossary | — | Gap |

---

## 3. LikeC4 Model Conventions

### 3.1 File Structure (per platform)

```
platforms/<name>/model/
  likec4.config.json    # {"name": "<platform>"} — required
  spec.likec4           # Element kinds + relationship kinds (Copier-synced)
  actors.likec4         # person elements (users, systems)
  platform.likec4       # platform + containers (C4 L2)
  ddd-contexts.likec4   # boundedContext + module elements (C4 L3)
  externals.likec4      # externalService elements
  infrastructure.likec4 # database, cache, proxy elements (shared infra)
  relationships.likec4  # ALL relationships (C4 + DDD context map)
  views.likec4          # ALL views (structural + scoped + dynamic)
```

### 3.2 Naming Conventions

| Element Kind | Naming Pattern | Example |
|-------------|---------------|---------|
| platform | camelCase | `fulano`, `madrugaAi` |
| boundedContext | camelCase (domain noun) | `channel`, `conversation`, `safety` |
| module | `m<N>` + descriptive suffix | `m1`, `m2`, `specifyPhase` |
| person | camelCase (role) | `agent`, `admin`, `architect` |
| externalService | camelCase (service name) | `evolutionApi`, `claudeApi` |
| database/cache | camelCase (tech + purpose) | `supabaseFulano`, `redis` |
| view (structural) | camelCase | `index`, `containers`, `contextMap` |
| view (scoped) | `<context>Detail` | `channelDetail`, `executionDetail` |
| view (dynamic) | camelCase (flow name) | `businessFlow`, `checkoutFlow` |

### 3.3 View Navigation (CRITICAL)

Views MUST include `navigateTo` declarations to enable drill-down navigation:

```likec4
// In structural views — use 'with { navigateTo ... }'
view index {
  include myPlatform with {
    navigateTo containers
  }
}

view containers of myPlatform {
  include *
  include myContext with {
    navigateTo myContextDetail
  }
}

// In dynamic views — use navigateTo on steps
dynamic view businessFlow {
  source -> target 'label' {
    navigateTo detailFlow
  }
}
```

### 3.4 Relationship Documentation

Every relationship should include:
- **technology** — protocol or transport (`HTTPS`, `asyncpg`, `Redis protocol`)
- **metadata** — endpoint, frequency, data, fallback (where applicable)
- **DDD pattern** — for context map relationships (ACL, Conformist, Customer-Supplier, Pub-Sub)
- **description** — for DDD relationships explaining the pattern rationale

### 3.5 Tag Usage

| Tag | Meaning | Applied to |
|-----|---------|-----------|
| `#critical` | Failure causes system-wide outage | Infrastructure elements |
| `#core` | Core domain — highest business value | Bounded contexts |
| `#supporting` | Supporting domain — necessary but not differentiating | Bounded contexts |
| `#generic` | Generic domain — commodity, could be outsourced | Bounded contexts |

---

## 4. DDD Context Map Patterns

### 4.1 Relationship Kinds (defined in spec.likec4)

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
| View navigation coverage | Every element in index has a navigateTo | `likec4 export json` + script |
| Orphan detection | No elements without relationships | JSON analysis |
| Relationship completeness | Every container has at least 1 inbound + 1 outbound | JSON analysis |
| Tag coverage | Every boundedContext has a domain classification tag | JSON analysis |
| Description coverage | Every element has a non-empty description | JSON analysis |

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
| 1 | **LikeC4 navigation broken** | HIGH | Add `navigateTo` to all views (see section 3.3) |
| 2 | **No deployment view** | MEDIUM | Add deployment diagrams to infrastructure.likec4 |
| 3 | **No cross-cutting concepts doc** | MEDIUM | Create shared patterns doc (logging, security, error handling) |
| 4 | **No quality scenarios** | LOW | Add Arc42 section 10 with measurable quality attributes |
| 5 | **No risk register** | LOW | Track risks as first-class artifacts alongside ADRs |
| 6 | **No glossary** | LOW | Enforce ubiquitous language per platform |
| 7 | **No automated model fitness** | MEDIUM | Script to validate LikeC4 JSON against conventions |
| 8 | **ADR review cadence missing** | LOW | Quarterly review of ADR relevance |

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
