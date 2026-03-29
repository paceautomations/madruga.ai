---
description: Generate an annotated folder structure with naming conventions and module boundaries
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt for it."
    required: false
argument-hint: "[platform-name]"
handoffs: []
---

# Folder Architecture — Folder Structure

Generate an annotated folder structure (~150 lines) with the purpose of each directory, naming conventions, and module boundaries.

## Cardinal Rule: ZERO Directories Without a Purpose

Every directory MUST have a clear reason to exist. If its purpose cannot be explained in 1 sentence, it should not exist.

**NEVER:**
- Create empty directories "for the future"
- Copy structure from another project without adapting
- Create a directory that duplicates another's responsibility
- Nest more than 4 levels without justification

## Persona

Staff Engineer with 15+ years of experience. Structure must be navigable by someone new to the project in 5 minutes. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/folder-arch fulano` — Generate folder architecture for "fulano"
- `/folder-arch` — Prompt for name

## Output Directory

Save to `platforms/<name>/engineering/folder-structure.md`.

## Instructions

### 0. Prerequisites

Run `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill folder-arch` and parse the JSON output.
- If `ready: false`: ERROR listing missing dependencies.
- If `ready: true`: read artifacts listed in `available`.
- Read `.specify/memory/constitution.md`.

### 1. Collect Context + Ask Questions

**Required reading:**
- `engineering/blueprint.md` — stack, concerns, topology
- `decisions/ADR-*.md` — decisions that impact structure

**Identify stack conventions:**
- From the ADRs, identify the primary framework/language
- Research via Context7 the recommended framework structure
- Web search: "[framework] project structure best practices 2026"
- Adapt to project size (do not use enterprise structure for an MVP)

**Structured Questions:**

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume monorepo/polyrepo. Correct?" |
| **Trade-offs** | "Feature-based (src/features/X) or layer-based (src/models, src/services)?" |
| **Gaps** | "Blueprint does not specify where [tests/configs/scripts] go. Define?" |
| **Challenge** | "A flat structure (few levels) may be better than deep nesting for this project." |

Wait for answers BEFORE generating.

### 2. Generate Folder Structure

```markdown
---
title: "Folder Structure"
updated: YYYY-MM-DD
---
# <Name> — Folder Structure

> Annotated folder structure. Every directory has a documented purpose.

---

## Annotated Tree

[Tree with max 3-4 levels, each directory annotated]

```
<name>/
├── src/                     # Main source code
│   ├── domain/              # Bounded contexts and aggregates (DDD)
│   │   ├── [context-a]/     # [Purpose of context A]
│   │   └── [context-b]/     # [Purpose of context B]
│   ├── infra/               # Infrastructure adapters
│   │   ├── db/              # Repositories and migrations
│   │   ├── http/            # Controllers and middleware
│   │   └── messaging/       # Event handlers and publishers
│   ├── shared/              # Cross-cutting utilities
│   │   ├── errors/          # Standardized error types
│   │   └── config/          # Configuration loading
│   └── main.[ext]           # Entry point
├── tests/                   # Tests (mirrors src/)
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── e2e/                 # End-to-end tests
├── scripts/                 # Automation scripts
├── docs/                    # Technical documentation
├── config/                  # Configuration files (env, deploy)
└── [others per stack]
```

---

## Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Directories | kebab-case | `user-auth/` |
| Files [language] | [language convention] | `user_service.py` / `UserService.ts` |
| Tests | [convention] | `test_user_service.py` / `UserService.test.ts` |
| Configs | kebab-case | `docker-compose.yml` |

---

## Module Boundaries

| Module | Can Import From | CANNOT Import From |
|--------|----------------|-------------------|
| domain/ | shared/ | infra/ |
| infra/ | domain/, shared/ | — |
| shared/ | — (no internal deps) | domain/, infra/ |

---

## Structure Decisions

| Decision | Choice | Alternative | Reason |
|----------|--------|------------|--------|
| Organization | [feature/layer] | [other] | [reason] |
| Max nesting | [N levels] | [more/fewer] | [reason] |
| Tests | [colocated/separate] | [other] | [reason] |
```

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every directory have a purpose annotation? | Add it |
| 2 | Are there any empty/purposeless directories? | Remove or justify |
| 3 | Is the structure compatible with the stack from ADRs? | Adjust |
| 4 | Max 4 nesting levels? | Flatten |
| 5 | Are module boundaries clear? | Define them |
| 6 | Are naming conventions documented? | Add them |
| 7 | Max 150 lines? | Condense |
| 8 | Does every decision have >=2 documented alternatives? | Add alternative |
| 9 | Are trade-offs explicit (pros/cons)? | Add pros/cons |
| 10 | Are assumptions marked [VALIDATE] or backed by data? | Mark [VALIDATE] |

### 4. Approval Gate: Human

Present:
- Summarized tree (1 level)
- Key decisions (feature vs layer, nesting, tests)
- Questions: "Does this make sense for your team?", "Any missing directories?"

### 5. Save + Report

```
## Folder Architecture generated

**File:** platforms/<name>/engineering/folder-structure.md
**Lines:** <N>
**Top-level directories:** <N>
**Max levels:** <N>

### Checks
[x] Every directory has a purpose
[x] Zero orphan directories
[x] Boundaries documented
[x] Conventions defined

### Next Step
folder-arch is terminal in the DAG. Check `/pipeline-status <name>` for other pending skills (domain-model, containers, etc.).
```

## Error Handling

| Issue | Action |
|-------|--------|
| Framework has no standard structure | Propose based on language best practices |
| Very small project | Flat structure (2 levels max) — do not force complexity |
| Conflict with existing codebase (brownfield) | Read codebase-context.md and propose gradual migration |
| Team has not defined monorepo/polyrepo | Ask — it impacts the entire structure |
