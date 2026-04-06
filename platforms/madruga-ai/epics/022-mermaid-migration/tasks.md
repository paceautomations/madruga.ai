# Tasks: Mermaid Migration — LikeC4 to Mermaid Inline

**Input**: Design documents from `platforms/madruga-ai/epics/022-mermaid-migration/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), pitch.md

**Tests**: Not explicitly requested in the specification. Test tasks omitted — validation is done via `npm run build`, `make test`, `make lint`.

**Organization**: Tasks are organized by user story (6 stories) to enable independent implementation and verification. Stories P1 are co-dependent (portal cleanup + diagram conversion), so they share a single foundational phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Inventory & Backup)

**Purpose**: Understand current state, ensure no information is lost during migration.

- [X] T001 Read all LikeC4 source files for Fulano platform in `platforms/fulano/model/` (actors.likec4, externals.likec4, platform.likec4, infrastructure.likec4, ddd-contexts.likec4, relationships.likec4, views.likec4, spec.likec4) to extract architectural content for conversion
- [X] T002 [P] Read all LikeC4 source files for Madruga-AI platform in `platforms/madruga-ai/model/` (actors.likec4, externals.likec4, platform.likec4, infrastructure.likec4, ddd-contexts.likec4, relationships.likec4, views.likec4, spec.likec4) to extract architectural content for conversion
- [X] T003 [P] Read current state of target documents: `platforms/fulano/engineering/blueprint.md`, `platforms/fulano/engineering/domain-model.md`, `platforms/fulano/business/process.md`
- [X] T004 [P] Read current state of target documents: `platforms/madruga-ai/engineering/blueprint.md`, `platforms/madruga-ai/engineering/domain-model.md`

---

## Phase 2: Foundational (Portal LikeC4 Removal — BLOCKS all stories)

**Purpose**: Remove LikeC4 infrastructure from the portal so the build works without `likec4` CLI. This is the blocking prerequisite for all user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete and `npm run build` passes.

- [X] T005 Remove `LikeC4VitePlugin` import and plugin config from `portal/astro.config.mjs` — remove line 9 (`import { LikeC4VitePlugin }...`), remove the `LikeC4VitePlugin({ workspace: '../platforms' })` entry from `vite.plugins[]`, and remove the `esbuild` JSX config block (lines 110-114) that was only needed for likec4:react virtual modules
- [X] T006 [P] Delete `portal/src/components/viewers/LikeC4Diagram.tsx`
- [X] T007 [P] Delete `portal/src/likec4.d.ts`
- [X] T008 [P] Delete `portal/src/pages/[platform]/landscape.astro`
- [X] T009 [P] Delete `portal/src/pages/[platform]/containers.astro`
- [X] T010 [P] Delete `portal/src/pages/[platform]/context-map.astro`
- [X] T011 [P] Delete `portal/src/pages/[platform]/bc/[context].astro`
- [X] T012 [P] Delete `portal/src/pages/[platform]/business-flow.astro`
- [X] T013 Remove `buildViewPaths()` function (lines 223-246) from `portal/src/lib/platforms.mjs`
- [X] T014 Simplify `buildSidebar()` in `portal/src/lib/platforms.mjs` — remove "System Landscape" link (line 182), "Containers" link (line 184), "Context Map" group with BC detail links (lines 185-195), and remove dependency on `p.views.structural` (line 189-194)
- [X] T015 Update `portal/src/lib/constants.ts` — remove `.likec4` handling in `resolveNodeHref` (line 39) and any LikeC4-related refs
- [X] T016 Remove `likec4` dependency from `portal/package.json` and run `npm install` to update lockfile
- [X] T017 Remove `'model'` from the `portalSections` array in `portal/astro.config.mjs` (line 21) — the `model/` directory will no longer exist
- [X] T018 Verify portal builds cleanly: run `cd portal && npm run build` — must pass with zero errors and without `likec4` CLI installed

**Checkpoint**: Portal is LikeC4-free. Build passes. All diagram pages return 404.

---

## Phase 3: User Story 2 — Diagramas Mermaid Inline (Priority: P1) 🎯 MVP

**Goal**: Convert all LikeC4 diagram content to Mermaid inline in existing Markdown documents for both platforms, preserving all architectural information.

**Independent Test**: Open each document in the portal (Starlight) and verify Mermaid diagrams render correctly via `astro-mermaid`. Verify via `npm run build`.

### Fulano Platform Conversion

- [X] T019 [US2] Convert Fulano deploy topology (from `platform.likec4`, `infrastructure.likec4`, `actors.likec4`, `externals.likec4`) to `graph LR` Mermaid diagram in `platforms/fulano/engineering/blueprint.md` section "Deploy Topology"
- [X] T020 [US2] Convert Fulano containers (from `platform.likec4`, `views.likec4` containers view) to `graph LR` with subgraphs Mermaid diagram in `platforms/fulano/engineering/blueprint.md` section "Containers"
- [X] T021 [US2] Convert Fulano DDD context map (from `ddd-contexts.likec4`, `relationships.likec4`) to `flowchart LR` Mermaid diagram in `platforms/fulano/engineering/domain-model.md` section "Context Map"
- [X] T022 [US2] Convert Fulano bounded context detail views (from `views.likec4` *Detail views, `ddd-contexts.likec4`) to `classDiagram` Mermaid diagrams in `<details>` blocks per BC in `platforms/fulano/engineering/domain-model.md`
- [X] T023 [US2] Convert Fulano business flow (from `views.likec4` businessFlow — ~315 LOC) to overview `flowchart TD` + `sequenceDiagram` deep-dives per phase in `<details>` blocks in `platforms/fulano/business/process.md`
- [X] T024 [US2] Add cross-references between diagram levels in Fulano docs: blueprint.md L1↔L2, domain-model.md L3↔L4, process.md L5, and inter-document links

### Madruga-AI Platform Conversion

- [X] T025 [P] [US2] Convert Madruga-AI deploy topology (from `platform.likec4`, `infrastructure.likec4`, `actors.likec4`, `externals.likec4`) to `graph LR` Mermaid diagram in `platforms/madruga-ai/engineering/blueprint.md` section "Deploy Topology"
- [X] T026 [P] [US2] Convert Madruga-AI containers (from `platform.likec4`, `views.likec4`) to `graph LR` with subgraphs Mermaid diagram in `platforms/madruga-ai/engineering/blueprint.md` section "Containers"
- [X] T027 [P] [US2] Convert Madruga-AI DDD context map (from `ddd-contexts.likec4`, `relationships.likec4`) to `flowchart LR` Mermaid diagram in `platforms/madruga-ai/engineering/domain-model.md` section "Context Map"
- [X] T028 [P] [US2] Convert Madruga-AI bounded context detail views to `classDiagram` Mermaid diagrams in `<details>` blocks per BC in `platforms/madruga-ai/engineering/domain-model.md`
- [X] T029 [US2] Remove LikeC4-specific content from `platforms/madruga-ai/engineering/domain-model.md` — remove LikeC4Model, LikeC4Element, LikeC4Relation, LikeC4View, AutoMarker class references from the domain model classDiagram
- [X] T030 [US2] Add cross-references between diagram levels in Madruga-AI docs: blueprint.md L1↔L2, domain-model.md L3↔L4, and inter-document links

### Cleanup LikeC4 Source Files

- [X] T031 [US2] Delete entire `platforms/fulano/model/` directory (8 files: actors.likec4, externals.likec4, platform.likec4, infrastructure.likec4, ddd-contexts.likec4, relationships.likec4, views.likec4, spec.likec4, plus likec4.config.json and output/)
- [X] T032 [P] [US2] Delete entire `platforms/madruga-ai/model/` directory (8 files: actors.likec4, externals.likec4, platform.likec4, infrastructure.likec4, ddd-contexts.likec4, relationships.likec4, views.likec4, spec.likec4, plus likec4.config.json and output/)

**Checkpoint**: All LikeC4 diagrams converted to Mermaid inline. Zero `.likec4` files remain. Portal build passes with diagrams rendering.

---

## Phase 4: User Story 3 — Sidebar e Navegacao Simplificadas (Priority: P2)

**Goal**: Ensure sidebar has no links to removed diagram pages and navigation is clean.

**Independent Test**: Navigate the portal sidebar — no "System Landscape", "Containers", "Context Map", or "Business Flow" as separate pages. No 404 links.

- [X] T033 [US3] Verify sidebar simplification done in T014 is correct — Engineering section should show: ADRs, Blueprint, Domain Model, Integrations (no dedicated diagram pages). If any residual links remain in `portal/src/lib/platforms.mjs`, remove them
- [X] T034 [US3] Check for any hardcoded links to `/landscape/`, `/containers/`, `/context-map/`, `/bc/`, `/business-flow/` in portal components or pages (search `portal/src/`) and remove them

**Checkpoint**: Sidebar clean. No 404 links in navigation.

---

## Phase 5: User Story 4 — Template Copier e Manifestos (Priority: P2)

**Goal**: Update platform.yaml manifests and Copier template so new platforms use Mermaid inline by default.

**Independent Test**: Inspect platform.yaml files — no `views:`, `serve:`, `build:` blocks. Copier template generates no `model/` directory.

- [X] T035 [US4] Remove `model:`, `views:`, `serve:`, `build:` blocks from `platforms/madruga-ai/platform.yaml` and update `outputs` for `domain-model` node (remove `model/ddd-contexts.likec4`, keep `engineering/domain-model.md`) and `containers` node (change outputs from `model/platform.likec4`, `model/views.likec4` to Mermaid sections in `engineering/blueprint.md`)
- [X] T036 [P] [US4] Remove `model:`, `views:`, `serve:`, `build:` blocks from `platforms/fulano/platform.yaml` and update `outputs` for `domain-model` node and `containers` node (same changes as T035)
- [X] T037 [US4] Update Copier template: delete all `.likec4.jinja` files and `likec4.config.json.jinja` from `.specify/templates/platform/template/model/`, remove the `model/` directory from template, update `.specify/templates/platform/template/platform.yaml.jinja` to not generate `views:`, `serve:`, `build:`, `model:` blocks
- [X] T038 [US4] Delete `.specify/scripts/vision-build.py` (LikeC4 JSON → AUTO markers script — no longer needed)

**Checkpoint**: Manifests and template updated. New platforms will not have LikeC4 artifacts.

---

## Phase 6: User Story 5 — ADRs e Documentacao de Decisao (Priority: P3)

**Goal**: Create ADR-020, update ADR-001 and ADR-003 to reflect the migration decision.

**Independent Test**: Read ADRs — ADR-001 status "Superseded", ADR-020 exists with justification, ADR-003 has no LikeC4VitePlugin mentions.

- [X] T039 [US5] Create `platforms/madruga-ai/decisions/ADR-020-mermaid-inline-diagrams.md` in Nygard format — document the decision to replace LikeC4 with Mermaid inline, reference ADR-001 as superseded, list alternatives considered (LikeC4 keep, Structurizr, Mermaid), include context from pitch.md Captured Decisions
- [X] T040 [P] [US5] Update `platforms/madruga-ai/decisions/ADR-001-*.md` — change status to "Superseded" with reference "Superseded by ADR-020-mermaid-inline-diagrams"
- [X] T041 [P] [US5] Update `platforms/madruga-ai/decisions/ADR-003-*.md` — remove any mentions of `LikeC4VitePlugin` or LikeC4 Vite integration

**Checkpoint**: ADRs consistent and up-to-date.

---

## Phase 7: User Story 6 — Skills e Pipeline Knowledge (Priority: P3)

**Goal**: Update pipeline knowledge and documentation to reference Mermaid inline instead of LikeC4.

**Independent Test**: Grep for "likec4" or "LikeC4" in knowledge files and CLAUDE.md — zero references.

- [X] T042 [US6] Update `.claude/knowledge/pipeline-dag-knowledge.md` — change outputs for `domain-model` node from `model/ddd-contexts.likec4` to Mermaid sections in `engineering/domain-model.md`, and for `containers` node from `model/platform.likec4, model/views.likec4` to Mermaid sections in `engineering/blueprint.md`
- [X] T043 [P] [US6] Update `CLAUDE.md` (root) — remove `likec4` from Prerequisites section, remove LikeC4 mentions from Active Technologies or conventions, remove `likec4 CLI` reference
- [X] T044 [P] [US6] Update `platforms/madruga-ai/CLAUDE.md` — remove LikeC4 from tech stack, update any diagram references to Mermaid inline
- [X] T045 [P] [US6] Update `platforms/fulano/CLAUDE.md` — remove LikeC4 from tech stack if mentioned
- [X] T046 [US6] Delete `.claude/rules/likec4.md` (LikeC4 conventions file — no longer applicable)

**Checkpoint**: All documentation and knowledge files reference Mermaid inline. Zero LikeC4 mentions.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: CI cleanup, full verification, ensure zero LikeC4 remnants across the entire repository.

- [X] T047 Remove the entire `likec4` job (lines 23-43) from `.github/workflows/ci.yml`
- [X] T048 Update `.github/workflows/ci.yml` `smoke-test` job — remove `vision-build.py` from the entrypoints import check list (line 81)
- [X] T049 [P] Delete `.claude/rules/portal.md` or update it to remove all LikeC4 references (platformLoaders, LikeC4VitePlugin mentions)
- [X] T050 [P] Remove `portal/src/lib/platforms.mjs` export of `buildViewPaths` if it was only used by deleted pages — verify no remaining imports
- [X] T051 Verify zero `.likec4` files remain: `find . -name "*.likec4" -o -name "likec4.config.json"` must return empty
- [X] T052 Verify zero LikeC4 references in portal source: `grep -r "LikeC4\|likec4" portal/src/ --include="*.ts" --include="*.tsx" --include="*.mjs" --include="*.astro"` must return empty (excluding node_modules)
- [X] T053 Run `cd portal && npm run build` — must pass with zero errors
- [X] T054 Run `make test` — all pytest tests must pass
- [X] T055 Run `make lint` — all platform linting must pass
- [X] T056 Verify Mermaid nomenclature consistency across levels: same component names in L1 (blueprint deploy topology), L2 (blueprint containers), L3 (domain-model context map), L4 (domain-model BC details) for both platforms

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately. Read-only phase.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS** all user stories — portal must build without LikeC4 before adding Mermaid.
- **US2 — Diagrams (Phase 3)**: Depends on Phase 1 (content read) + Phase 2 (portal clean). Core conversion work.
- **US3 — Sidebar (Phase 4)**: Mostly done in Phase 2 (T014). Phase 4 is verification + cleanup.
- **US4 — Template/Manifests (Phase 5)**: Depends on Phase 3 (model/ dirs deleted first).
- **US5 — ADRs (Phase 6)**: Independent of other stories — can run in parallel with Phase 5+.
- **US6 — Knowledge/Docs (Phase 7)**: Independent — can run in parallel with Phase 5+.
- **Polish (Phase 8)**: Depends on ALL previous phases. Final verification.

### User Story Dependencies

- **US1 (Portal cleanup)**: Phase 2 — no dependencies on other stories
- **US2 (Diagrams)**: Depends on US1 (portal must build without LikeC4 pages first)
- **US3 (Sidebar)**: Depends on US1 (sidebar simplified during portal cleanup)
- **US4 (Template/Manifests)**: Depends on US2 (model/ dirs removed during diagram conversion)
- **US5 (ADRs)**: Independent — can start after Foundational
- **US6 (Knowledge/Docs)**: Independent — can start after Foundational

### Within Each Phase

- Tasks marked [P] can run in parallel
- Sequential tasks depend on prior tasks in the same phase
- Fulano and Madruga-AI conversions can run in parallel within Phase 3

### Parallel Opportunities

- Phase 1: All T001-T004 read tasks can run in parallel
- Phase 2: T006-T012 file deletions can all run in parallel, then T005/T013-T017 modifications
- Phase 3: Fulano conversion (T019-T024) and Madruga-AI conversion (T025-T030) can run in parallel
- Phase 5-7: US4, US5, US6 can all run in parallel after Phase 3 completes

---

## Parallel Example: Phase 2 (Portal Cleanup)

```bash
# Batch 1 — Delete all LikeC4-specific files in parallel:
Task: "Delete portal/src/components/viewers/LikeC4Diagram.tsx"
Task: "Delete portal/src/likec4.d.ts"
Task: "Delete portal/src/pages/[platform]/landscape.astro"
Task: "Delete portal/src/pages/[platform]/containers.astro"
Task: "Delete portal/src/pages/[platform]/context-map.astro"
Task: "Delete portal/src/pages/[platform]/bc/[context].astro"
Task: "Delete portal/src/pages/[platform]/business-flow.astro"

# Batch 2 — Modify config files (sequentially, same files):
Task: "Remove LikeC4VitePlugin from astro.config.mjs"
Task: "Simplify buildSidebar() in platforms.mjs"
Task: "Update constants.ts"
Task: "Remove likec4 from package.json"

# Batch 3 — Verify:
Task: "cd portal && npm run build"
```

## Parallel Example: Phase 3 (Diagram Conversion)

```bash
# Fulano and Madruga-AI can run in parallel:
# Worker A: Fulano
Task: "Convert Fulano deploy topology to blueprint.md"
Task: "Convert Fulano containers to blueprint.md"
Task: "Convert Fulano context map to domain-model.md"
Task: "Convert Fulano BC details to domain-model.md"
Task: "Convert Fulano business flow to process.md"

# Worker B: Madruga-AI (all [P] marked)
Task: "Convert Madruga-AI deploy topology to blueprint.md"
Task: "Convert Madruga-AI containers to blueprint.md"
Task: "Convert Madruga-AI context map to domain-model.md"
Task: "Convert Madruga-AI BC details to domain-model.md"
```

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3)

1. Complete Phase 1: Read all LikeC4 content
2. Complete Phase 2: Remove LikeC4 from portal — **verify build passes**
3. Complete Phase 3: Convert diagrams to Mermaid inline — **verify build passes with diagrams**
4. **STOP and VALIDATE**: Portal works, diagrams render, zero LikeC4 remnants in portal
5. This is the MVP — portal fully functional with Mermaid inline

### Incremental Delivery

1. Phase 1+2 → Portal builds without LikeC4 ✓
2. Phase 3 → Diagrams converted, model/ dirs removed ✓
3. Phase 4 → Sidebar verified clean ✓
4. Phase 5 → Manifests + template updated ✓
5. Phase 6 → ADRs documented ✓
6. Phase 7 → Knowledge files updated ✓
7. Phase 8 → CI clean, full verification ✓

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US1 (Portal cleanup) is fully covered by Phase 2 — no separate phase needed since it's the foundational prerequisite
- Diagrams should follow the Pyramid of Detail convention from pitch.md (L1-L5)
- Use `<details>` blocks for complex diagrams (BC deep-dives, business flow phases)
- Mermaid syntax: `graph LR`, `flowchart LR`, `flowchart TD`, `classDiagram`, `sequenceDiagram` — do NOT use experimental C4Context/C4Container syntax
- Verify nomenclature consistency across diagram levels (same component IDs)

---
handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "56 tasks gerados para migracao LikeC4 → Mermaid inline. 8 fases: setup, portal cleanup (foundational), diagrama conversion (P1), sidebar (P2), template/manifests (P2), ADRs (P3), knowledge (P3), polish. MVP = phases 1-3. Zero funcionalidade nova — pura simplificacao."
  blockers: []
  confidence: Alta
  kill_criteria: "Se astro-mermaid nao renderizar os tipos de diagrama necessarios (classDiagram, sequenceDiagram, flowchart) no portal build."
