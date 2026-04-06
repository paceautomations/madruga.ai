# Implementation Plan: Mermaid Migration — LikeC4 to Mermaid Inline

**Branch**: `epic/madruga-ai/022-mermaid-migration` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Migrate all architecture diagrams from LikeC4 to Mermaid inline in existing Markdown documents, eliminating all LikeC4 tooling.

## Summary

Remove LikeC4 dependency (16 `.likec4` files, Vite plugin, React component, 5 dedicated `.astro` pages, CI job, vision-build.py) and replace with Mermaid diagrams inline in existing `.md` documents (`blueprint.md`, `domain-model.md`, `process.md`). Zero new functionality — pure simplification. The portal already has `astro-mermaid` v2.0.1 installed and functional. L4 classDiagrams already exist in both platforms' `domain-model.md`. L1 deploy topology already exists in madruga-ai's `blueprint.md`.

## Technical Context

**Language/Version**: TypeScript (Astro 5.x, React), Python 3.11+ (scripts), Bash (CI)
**Primary Dependencies**: Astro + Starlight, astro-mermaid v2.0.1, js-yaml (portal build-time)
**Storage**: Filesystem (Markdown + YAML), SQLite WAL mode (pipeline state)
**Testing**: pytest (scripts), portal build validation (Mermaid syntax), `platform_cli.py lint --all`
**Target Platform**: WSL2 Linux (local dev), GitHub Actions (CI)
**Project Type**: Documentation system (portal + CLI tools)
**Performance Goals**: Portal build < 30s (NFR Q1 from blueprint)
**Constraints**: No new dependencies. `astro-mermaid` already installed. Python: stdlib + pyyaml only.
**Scale/Scope**: 2 platforms (fulano, madruga-ai), ~28 files removed, ~20 files modified, 1 file created

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I. Pragmatism | Simplification reduces tooling — fully aligned | PASS |
| II. Automate Repetitive | Removing vision-build.py (automated but unnecessary) | PASS |
| III. Structured Knowledge | All arch info preserved in .md — more accessible | PASS |
| IV. Fast Action | 1-week appetite, well-scoped removal | PASS |
| V. Alternatives | ADR-020 documents alternatives (LikeC4, Structurizr, PlantUML) | PASS |
| VI. Brutal Honesty | Trade-off explicit: losing interactivity (pan/zoom) | PASS |
| VII. TDD | Tests validate: portal build, make test, make lint | PASS |
| VIII. Collaborative Decision | Pitch reviewed and approved, decisions captured | PASS |
| IX. Observability | N/A — no runtime components changed | PASS |

**All gates pass. No violations.**

## Project Structure

### Documentation (this epic)

```text
platforms/madruga-ai/epics/022-mermaid-migration/
├── pitch.md              # Epic pitch (Shape Up)
├── spec.md               # Feature specification
├── plan.md               # This file
├── research.md           # Phase 0 output — content inventory + decisions
├── data-model.md         # Phase 1 output — artifact inventory + naming contract
└── tasks.md              # Phase 2 output (by /speckit.tasks)
```

### Source Code Impact

```text
# REMOVE (28 files)
portal/src/components/viewers/LikeC4Diagram.tsx
portal/src/likec4.d.ts
portal/src/pages/[platform]/landscape.astro
portal/src/pages/[platform]/containers.astro
portal/src/pages/[platform]/context-map.astro
portal/src/pages/[platform]/bc/[context].astro
portal/src/pages/[platform]/business-flow.astro
platforms/fulano/model/          (10 files: 8 .likec4 + config + output/)
platforms/madruga-ai/model/      (10 files: 8 .likec4 + config + output/)
.specify/scripts/vision-build.py
.specify/scripts/tests/test_vision_build.py
.claude/rules/likec4.md

# MODIFY (20+ files)
portal/astro.config.mjs
portal/src/lib/platforms.mjs
portal/src/lib/constants.ts
portal/src/components/dashboard/PipelineDAG.tsx
portal/package.json
platforms/fulano/platform.yaml
platforms/madruga-ai/platform.yaml
platforms/fulano/engineering/blueprint.md        # Add L1 + L2 Mermaid
platforms/fulano/engineering/domain-model.md     # Add L3 context map section
platforms/fulano/engineering/context-map.md      # Populate with Mermaid (was empty)
platforms/madruga-ai/engineering/blueprint.md    # Add L2, update stack table
platforms/madruga-ai/decisions/ADR-001-*.md      # Status: Superseded
platforms/madruga-ai/decisions/ADR-003-*.md      # Remove LikeC4VitePlugin refs
.specify/scripts/platform_cli.py                # Remove model/ from REQUIRED_DIRS/FILES
.specify/templates/platform/template/           # Remove model/, update platform.yaml.jinja
.github/workflows/ci.yml                        # Remove likec4 job + vision-build.py ref
.claude/knowledge/pipeline-dag-knowledge.md     # Update node outputs
CLAUDE.md                                       # Remove LikeC4 prereqs
platforms/madruga-ai/CLAUDE.md                  # Remove LikeC4 from stack

# CREATE (1 file)
platforms/madruga-ai/decisions/ADR-020-mermaid-inline-diagrams.md
```

---

## Phase 0: Research (Complete)

See [research.md](research.md) for full findings. Key results:

1. **astro-mermaid v2.0.1** supports all required diagram types (graph, flowchart, classDiagram, sequenceDiagram).
2. **L4 already exists**: Both platforms' `domain-model.md` already have Mermaid classDiagrams for BCs.
3. **L1 partially exists**: madruga-ai's `blueprint.md` already has a deploy topology Mermaid diagram.
4. **Business flow decomposition**: Fulano's 315 LOC dynamic view → overview flowchart + 8 phase deep-dives (~125 LOC total).
5. **platform_cli.py** requires `model/` in `REQUIRED_DIRS` and `model/spec.likec4` in `REQUIRED_FILES` — must be updated.
6. **CI smoke test** references `vision-build.py` — must be removed from entrypoint list.
7. **Fulano has no `business/process.md`** — must be created for L5 business flow diagrams.

---

## Phase 1: Design & Contracts

### 1.1 Mermaid Diagram Specifications

#### L1 — Deploy Topology (Fulano `blueprint.md`)

New section "Deploy Topology" with `graph LR` showing:
- Actors: agent (WhatsApp user), admin (operator)
- Platform containers: fulano-api, fulano-worker, fulano-admin
- Infrastructure: Redis, Supabase Fulano, Bifrost
- External: Evolution API, Supabase ResenhAI, Claude Sonnet/Haiku, LangFuse, Infisical
- Connections: key protocol/technology on edges

Source: `actors.likec4` + `externals.likec4` + `infrastructure.likec4` + `platform.likec4` + `relationships.likec4` (container-level only)

#### L2 — Containers (Fulano `blueprint.md`)

New section "Containers" with `graph LR` + subgraphs showing:
- Subgraph "Fulano Platform": fulano-api, fulano-worker, fulano-admin (with technology labels)
- Subgraph "Storage": Redis, Supabase Fulano
- Subgraph "External": Evolution API, Bifrost, Claude Sonnet/Haiku, LangFuse, Infisical
- Connections with protocol labels (HTTPS, Redis Streams, asyncpg, Socket.io)

Source: `relationships.likec4` (container-level relationships, lines 1-156)

#### L2 — Containers (Madruga-AI `blueprint.md`)

Enhance existing deploy topology diagram OR add separate "Containers" section with subgraphs:
- Subgraph "Local": Portal, Easter, DAG Executor, Telegram Bot, Platform CLI
- Subgraph "Storage": SQLite, Filesystem
- Subgraph "External": Claude Code, GitHub, Telegram API, Sentry

Source: existing diagram at line 102-135 + `platform.likec4` + `relationships.likec4`

#### L3 — Context Map (Fulano `domain-model.md`)

New "Context Map" section at the top of domain-model.md with `flowchart LR` showing:
- 5 bounded contexts as subgraphs: Channel, Conversation (Core), Safety, Operations, Observability
- DDD relationships: ACL, Customer-Supplier, Pub-Sub, Conformist
- External integrations connected to BCs

Source: `relationships.likec4` (DDD-level relationships, lines 157-232)

Note: Fulano's `engineering/context-map.md` currently has only empty AUTO markers. The content will be absorbed into domain-model.md. The context-map.md file can be either:
- **Option A**: Populated with a redirect/link to domain-model.md (keeps URL working)
- **Option B**: Left with a simplified version (just the flowchart, no details)

Decision: **Option A** — minimal content with cross-reference to avoid 404s for anyone who bookmarked the URL.

#### L5 — Business Flow (Fulano — new `business/process.md`)

Fulano does not have `business/process.md`. Create it with:
- Title and overview text
- Overview `flowchart TD` (~25 lines): high-level pipeline phases
- 8 `<details>` sections, each with phase-specific diagram:
  - Fase 1: Entrada (sequenceDiagram)
  - Fase 2: Decision Point #1 — Router (flowchart LR)
  - Fase 3: Pipeline Core (sequenceDiagram)
  - Fase 4: Decision Point #3 — Quality (flowchart LR)
  - Fase 5: Saida (sequenceDiagram)
  - Fase 6: Handoff Humano (sequenceDiagram + state diagram)
  - Fase 7: Triggers Proativos (sequenceDiagram)
  - Fase 8: Observabilidade (flowchart LR)

Source: `views.likec4` businessFlow dynamic view (315 LOC)

#### L5 — Business Flow (Madruga-AI)

Check if `platforms/madruga-ai/business/process.md` exists and has content. If it has a Mermaid business flow already, no action needed. If not, convert from `views.likec4` businessFlow.

### 1.2 Platform YAML Schema Changes

Remove from both `platform.yaml` files and the Copier template:
```yaml
# REMOVE these top-level keys:
model: model/
views:
  structural: [...]
  flows: [...]
serve:
  command: "likec4 serve"
  port: 5173
build:
  command: "likec4 build"
  export_json: "..."
  cwd: "model/"
```

Update pipeline node outputs:
```yaml
# BEFORE:
- id: domain-model
  outputs: ["engineering/domain-model.md", "model/ddd-contexts.likec4"]
- id: containers
  outputs: ["model/platform.likec4", "model/views.likec4"]

# AFTER:
- id: domain-model
  outputs: ["engineering/domain-model.md"]
- id: containers
  outputs: ["engineering/blueprint.md"]
```

### 1.3 Portal Architecture Changes

#### astro.config.mjs
```diff
- import { LikeC4VitePlugin } from 'likec4/vite-plugin';
  
- const portalSections = ['business', 'engineering', 'decisions', 'research', 'planning', 'model'];
+ const portalSections = ['business', 'engineering', 'decisions', 'research', 'planning'];

  vite: {
-   esbuild: {
-     jsx: 'automatic',
-     jsxImportSource: 'react',
-   },
    ...
    plugins: [
      platformSymlinksPlugin(),
-     LikeC4VitePlugin({ workspace: '../platforms' }),
    ],
  },
  
  head: [
    { tag: 'script', attrs: { src: '/sidebar-toggle.js', defer: true } },
-   { tag: 'script', attrs: { src: '/svg-pan-zoom.min.js' } },
-   { tag: 'script', attrs: { src: '/mermaid-interactive.js', defer: true } },
  ],
```

#### platforms.mjs — buildSidebar()
Remove:
- `{ label: 'System Landscape', link: ... }` item
- `{ label: 'Containers', link: ... }` item
- Entire `Context Map` group (which uses `p.views.structural`)
- `buildViewPaths()` function (export removed)

#### constants.ts & PipelineDAG.tsx
Remove `.replace(/\.likec4$/, '')` from URL generation.

### 1.4 CI Changes

```yaml
# REMOVE entire job:
  likec4:
    runs-on: ubuntu-latest
    steps: [...]

# UPDATE smoke-test entrypoints list:
# Remove vision-build.py from the list
```

### 1.5 Script Changes

#### platform_cli.py
```python
# BEFORE:
REQUIRED_DIRS = ["business", "engineering", "decisions", "epics", "model"]
REQUIRED_FILES = [
    ...
    "model/spec.likec4",
    "model/likec4.config.json",
]

# AFTER:
REQUIRED_DIRS = ["business", "engineering", "decisions", "epics"]
# Remove model/spec.likec4 and model/likec4.config.json from REQUIRED_FILES
```

Also remove the `register` subcommand logic that validates LikeC4 models (or make it no-op).

### 1.6 ADR Changes

#### ADR-001 (Supersede)
```markdown
---
title: 'ADR-001: LikeC4 como Source of Truth'
status: Superseded
superseded_by: ADR-020
---
# ADR-001: LikeC4 como Source of Truth para Modelos Arquiteturais
**Status:** Superseded by [ADR-020](ADR-020-mermaid-inline-diagrams/) | **Data:** 2026-03-27
```

#### ADR-003 (Update)
Remove mentions of `LikeC4VitePlugin` from decision statement and consequences. Update to reflect that diagrams are now rendered via `astro-mermaid`.

#### ADR-020 (Create)
New ADR documenting the decision to migrate to Mermaid inline, with alternatives considered (keep LikeC4, Structurizr, PlantUML, Mermaid files .mmd).

### 1.7 Knowledge & Skills Updates

#### pipeline-dag-knowledge.md
Update L1 table:
```markdown
| domain-model | madruga:domain-model | engineering/domain-model.md | blueprint, business-process | engineering | human | no |
| containers | madruga:containers | engineering/blueprint.md (Mermaid sections) | domain-model, blueprint | engineering | human | no |
```

Note: Skills themselves (`.claude/commands/`) must be updated via `/madruga:skills-mgmt` per repo policy. This plan documents WHAT needs to change; the actual skill edits happen during implementation via the proper channel.

---

## Execution Order (5 Phases)

### Fase 1: Portal Cleanup (Remove LikeC4) — P1
**Why first**: Removes the dependency that blocks everything else. Portal must build without LikeC4.

1. Remove `LikeC4VitePlugin` from `astro.config.mjs`
2. Remove esbuild jsx config (only needed for likec4:react virtual modules)
3. Remove `likec4` head scripts (svg-pan-zoom.min.js, mermaid-interactive.js)
4. Remove 'model' from `portalSections` array
5. Remove `LikeC4Diagram.tsx` and `likec4.d.ts`
6. Remove 5 dedicated `.astro` pages (landscape, containers, context-map, bc/[context], business-flow)
7. Simplify `buildSidebar()` — remove diagram links and `p.views.structural` refs
8. Remove `buildViewPaths()` function
9. Remove `.likec4` extension handling from `constants.ts` and `PipelineDAG.tsx`
10. Remove `likec4` from `package.json` and regenerate `package-lock.json`
11. Verify: `cd portal && npm install && npm run build` passes

### Fase 2: Convert Diagrams — P1
**Why second**: Adds Mermaid content to existing docs. Required before model/ can be removed.

12. Add L1 deploy topology Mermaid to `platforms/fulano/engineering/blueprint.md`
13. Add L2 containers Mermaid to `platforms/fulano/engineering/blueprint.md`
14. Add L3 context map Mermaid to `platforms/fulano/engineering/domain-model.md`
15. Update `platforms/fulano/engineering/context-map.md` with cross-reference to domain-model.md
16. Create `platforms/fulano/business/process.md` with L5 business flow Mermaid (overview + 8 deep-dives)
17. Add L2 containers detail to `platforms/madruga-ai/engineering/blueprint.md`
18. Update madruga-ai `blueprint.md` stack table: LikeC4 → Mermaid, remove LikeC4 error handling row
19. Check if madruga-ai needs business flow conversion (process.md)
20. Remove `model/` directory from both platforms (16 .likec4 files + configs + output/)
21. Remove `vision-build.py` and its test file
22. Remove `.claude/rules/likec4.md`
23. Verify: `cd portal && npm run build` still passes with new Mermaid content

### Fase 3: Manifests & Template — P2
**Why third**: Updates configs after content is migrated.

24. Update `platforms/fulano/platform.yaml`: remove `model:`, `views:`, `serve:`, `build:` blocks; update outputs
25. Update `platforms/madruga-ai/platform.yaml`: same changes
26. Update `platform_cli.py`: remove `model` from `REQUIRED_DIRS`, remove `.likec4` files from `REQUIRED_FILES`, update `register` command
27. Update Copier template `platform.yaml.jinja`: remove LikeC4 blocks, update outputs
28. Remove `model/` directory from Copier template (9 .jinja/.likec4 files)
29. Update `pipeline-dag-knowledge.md`: domain-model and containers outputs
30. Verify: `make lint` passes, `make test` passes

### Fase 4: ADRs & Docs — P3
**Why fourth**: Documentation updates after all functional changes.

31. Create `ADR-020-mermaid-inline-diagrams.md`
32. Update `ADR-001-likec4-source-of-truth.md`: status Superseded
33. Update `ADR-003-astro-starlight-portal.md`: remove LikeC4VitePlugin mentions
34. Update `CLAUDE.md`: remove LikeC4 prereqs, update conventions
35. Update `platforms/madruga-ai/CLAUDE.md`: remove LikeC4 from stack

### Fase 5: CI & Final Validation — P3
**Why last**: Final cleanup and full validation.

36. Remove `likec4` job from `.github/workflows/ci.yml`
37. Remove `vision-build.py` from smoke-test entrypoints list
38. Run full validation: `make test && make lint && cd portal && npm run build`
39. Verify zero `.likec4` files remain: `find . -name "*.likec4" | wc -l` = 0
40. Verify zero LikeC4 refs in portal: `grep -rn "LikeC4\|likec4" portal/src/ --include="*.ts" --include="*.tsx" --include="*.mjs" --include="*.astro"` = 0 (except possibly comments in ADR links)

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Portal build breaks during LikeC4 removal | Medium | Medium | Incremental removal: plugin first, then pages, then deps. Build check after each step. |
| Information loss during diagram conversion | Low | High | Systematic line-by-line audit of each .likec4 file. Research.md has full inventory. |
| Platform lint fails on missing model/ | High | Low | Update REQUIRED_DIRS/FILES in platform_cli.py before running lint. |
| Copier template tests fail | Medium | Low | Update template and tests together. |
| Fulano process.md creation adds unexpected sidebar entry | Low | Low | buildSidebar() already handles optional process.md via `platformFileExists()`. |
| astro-mermaid renders poorly on complex diagrams | Low | Medium | Decompose complex diagrams. Max ~50 lines per diagram block. |

---

## Complexity Tracking

No constitution violations. This is a simplification epic — reduces complexity rather than adding it.

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan complete for 022-mermaid-migration. 5 phases, 40 steps. Key artifacts: research.md (content inventory), data-model.md (artifact mapping). Portal cleanup first (P1), then diagram conversion (P1), then manifests+template (P2), then ADRs (P3), then CI (P3). Break into dependency-ordered tasks."
  blockers: []
  confidence: Alta
  kill_criteria: "If astro-mermaid cannot render the diagram types needed (verified: it can), or if removing LikeC4 breaks portal in an unrecoverable way."
