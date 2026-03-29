---
description: Map an existing codebase (brownfield) or declare greenfield for any platform
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt for it."
    required: false
argument-hint: "[platform-name]"
---

# Codebase Map — Codebase Analysis

Detect whether the project is brownfield (existing codebase) or greenfield (from scratch). If brownfield, analyze structure, dependencies, patterns, and integrations. If greenfield, generate a minimal artifact.

**Optional DAG node** — if not executed, no downstream node is blocked.

## Cardinal Rule: ZERO Guesswork About Codebase

Every statement about the codebase MUST be based on **actual code reading**. No assumptions about structure, patterns, or dependencies without filesystem evidence.

**NEVER:**
- Assume a pattern exists without finding it in code
- Infer dependencies without reading package.json/requirements.txt/go.mod or equivalent
- Assert integrations without finding actual calls
- Invent metrics (lines of code, coverage) without measuring

> **Contract**: Follow `.claude/knowledge/pipeline-contract-base.md`.

## Usage

- `/codebase-map fulano` — Map the codebase for platform "fulano"
- `/codebase-map` — Prompt for platform name

## Output Directory

Save to `platforms/<name>/research/codebase-context.md`.

## Instructions

### 1. Detect Brownfield vs Greenfield

**Detection criteria:**

| Criterion | Where to Check | Result |
|-----------|---------------|--------|
| `source_repo` field in platform.yaml | `platforms/<name>/platform.yaml` | If exists → brownfield |
| `src/` directory in referenced repo | Repo or local directory | If exists → brownfield |
| Dependency files (package.json, requirements.txt, go.mod, Cargo.toml, pom.xml) | Root of referenced repo | If exists → brownfield |

**If NONE of the criteria are met → GREENFIELD.**

### 2A. Greenfield Flow

If greenfield, generate a minimal artifact:

```markdown
---
title: "Codebase Context"
updated: YYYY-MM-DD
---
# <Name> — Codebase Context

> Greenfield project — no existing codebase.

## Status

Greenfield. No codebase analysis required.

## Implications

- No pre-existing technical debt
- Full freedom for stack and pattern choices
- No legacy integrations to consider
```

Skip to section 5 (Save).

### 2B. Brownfield Flow

If brownfield, **spawn Agent subagents in parallel** for analysis:

**Agent 1 — File Structure:**
- Map directory tree (max 3 levels)
- Identify main directories and their purpose
- Count files by type/extension

**Agent 2 — Dependencies:**
- Read dependency files (package.json, requirements.txt, etc.)
- List direct dependencies with versions
- Identify main frameworks and libraries

**Agent 3 — Detected Patterns:**
- Search for architectural patterns (MVC, hexagonal, DDD, monolith, microservices)
- Identify code patterns (recurring design patterns)
- Detect naming conventions

**Agent 4 — Integrations:**
- Search for HTTP/gRPC/messaging calls
- Identify referenced external services
- Map integration points (APIs, webhooks, queues)

Consolidate results into `research/codebase-context.md`:

```markdown
---
title: "Codebase Context"
updated: YYYY-MM-DD
---
# <Name> — Codebase Context

> Existing codebase analysis. Last updated: YYYY-MM-DD.

---

## Summary

[2-3 lines: primary language, framework, approximate size]

---

## File Structure

[Annotated tree — max 3 levels with purpose for each directory]

---

## Technology Stack

| Category | Technology | Version | Notes |
|----------|-----------|---------|-------|
| Language | ... | ... | ... |
| Framework | ... | ... | ... |
| Database | ... | ... | ... |
| Infra | ... | ... | ... |

---

## Key Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| ... | ... | ... |

---

## Detected Patterns

| Pattern | Evidence | File(s) |
|---------|----------|---------|
| ... | ... | ... |

---

## Integrations

| Service | Type | Endpoint/Topic | File(s) |
|---------|------|----------------|---------|
| ... | ... | ... | ... |

---

## Observations

[Risks, evident technical debt, areas requiring attention]
```

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every statement have a source file as evidence? | Add reference or remove |
| 2 | Are there any assumptions without actual file reads? | Verify or mark [NOT VERIFIED] |
| 3 | Is brownfield/greenfield correctly detected? | Re-check criteria |
| 4 | Do dependencies include versions? | Read dependency file |
| 5 | Within line limits: max 150 lines (brownfield) / 15 lines (greenfield)? | Condense |

## Error Handling

| Issue | Action |
|-------|--------|
| source_repo in platform.yaml points to inaccessible repo | Treat as greenfield, warn user |
| Codebase too large (>10k files) | Limit analysis to top 3 levels, sample patterns |
| Multiple languages | List all, focus on primary (most files) |
| No dependency files found | Infer stack from files, mark [INFERRED] |
| platform.yaml missing source_repo field | Check for local src/, otherwise greenfield |

---
handoff:
  from: codebase-map
  to: null
  context: "No opcional. Sem handoff obrigatorio."
  blockers: []
