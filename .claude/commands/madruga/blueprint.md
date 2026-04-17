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

- `/blueprint prosauai` — Generate blueprint for the "prosauai" platform
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

### Testing Scaffold

Ao gerar os artefatos da plataforma (Step 2), incluir automaticamente a infraestrutura de testes:

#### 1. Bloco `testing:` em platform.yaml

Inferir `startup.type` a partir da stack declarada nas ADRs ou perguntas estruturais:

| Stack detectada | startup.type |
|-----------------|-------------|
| Docker / docker-compose | `docker` |
| Node.js / npm / Next.js | `npm` |
| Python / venv / FastAPI | `script` |
| Makefile como entrypoint | `make` |
| Indefinido / sem servidor | `none` |

Gerar o bloco `testing:` com skeleton preenchível:

```yaml
testing:
  startup:
    type: <inferido da stack>   # docker | npm | make | script | none
    command: null               # override; obrigatório se type=script ou venv
    ready_timeout: 60           # segundos
  health_checks: []             # preencher com URLs de health check do serviço
  urls: []                      # preencher com URLs a validar (type: api|frontend)
  required_env: []              # listar env vars obrigatórias para o serviço subir
  env_file: null                # ex: .env.example (relativo ao repo da plataforma)
  journeys_file: testing/journeys.md
```

#### 2. Arquivo `testing/journeys.md`

Criar `platforms/<name>/testing/journeys.md` com J-001 placeholder estruturado baseado na US principal declarada na visão/spec da plataforma:

````markdown
# Jornadas de Teste — <Platform Name>

> Jornadas de usuário para validação end-to-end. Atualizado por `speckit.tasks` e `reconcile`.

## J-001 — Happy Path Principal

Descrever brevemente o fluxo principal do usuário.

```yaml
id: J-001
title: "Happy Path Principal"
required: true
steps:
  # Exemplo de step de API:
  # - type: api
  #   action: "GET http://localhost:PORT/health"
  #   assert_status: 200
  # Exemplo de step de browser:
  # - type: browser
  #   action: "navigate http://localhost:PORT"
  #   screenshot: true
  # - type: browser
  #   action: "assert_contains <texto esperado>"
```
````

#### 3. CI Workflow (plataformas com `repo:` binding)

Para plataformas com `repo:` binding declarado em `platform.yaml`, gerar `.github/workflows/ci.yml` com os jobs:

- **lint**: análise estática + linting
- **test**: suite de testes automatizados
- **build**: build de produção (se `startup.type=docker`, incluir `docker build` com flag opcional `--no-cache`)

Exemplo mínimo para startup.type=docker:

```yaml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # [lint steps da stack]
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # [test steps da stack]
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t <platform>:ci .
        # Flag opcional para CI lento: adicionar --build-arg SKIP_TESTS=1
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

