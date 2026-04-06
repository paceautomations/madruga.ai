# Research: Mermaid Migration — LikeC4 to Mermaid Inline

**Epic**: 022-mermaid-migration | **Date**: 2026-04-05

---

## 1. astro-mermaid Compatibility

### Decision
`astro-mermaid` (v2.0.1, already installed) supports all required diagram types natively.

### Rationale
Verified in portal `package.json`: `"astro-mermaid": "^2.0.1"`. The integration is already active in `astro.config.mjs` as `mermaid()`. It renders server-side during Astro build — no client-side JS needed.

### Supported Types (confirmed)
| Type | Used in This Epic | Status |
|------|------------------|--------|
| `graph LR` / `graph TD` | Deploy Topology (L1), Containers (L2) | Supported |
| `flowchart LR` / `flowchart TD` | Context Map (L3), Business Flow overview (L5) | Supported |
| `classDiagram` | Bounded Context details (L4) | Supported |
| `sequenceDiagram` | Business Flow deep-dives (L5) | Supported |

### Alternatives Considered
- **mermaid-cli (`mmdc`)**: CLI tool for pre-rendering Mermaid to SVG/PNG. Rejected — adds CI dependency, `astro-mermaid` already validates syntax at build time.
- **Custom React component**: Rejected — unnecessary complexity, `astro-mermaid` handles server-side rendering.

---

## 2. LikeC4 Content Inventory

### Fulano Platform (8 .likec4 files, 877 LOC total)

| File | LOC | Content | Migration Target |
|------|-----|---------|-----------------|
| `actors.likec4` | 10 | 2 personas (agent, admin) | Absorbed into blueprint.md deploy topology |
| `externals.likec4` | 29 | 4 external services (Evolution API, Supabase ResenhAI, Claude Sonnet, Claude Haiku) | Absorbed into blueprint.md deploy topology |
| `infrastructure.likec4` | 50 | 6 infra components (Redis, Supabase Fulano, Bifrost, LangFuse, Infisical) | Absorbed into blueprint.md deploy topology + containers |
| `platform.likec4` | 34 | 3 platform containers (fulano-api, fulano-worker, fulano-admin) | Absorbed into blueprint.md containers |
| `ddd-contexts.likec4` | 149 | 5 BCs with 14 modules (M1-M14) | Already in domain-model.md as classDiagram (5 existing) |
| `relationships.likec4` | 232 | Container relationships + DDD relationships + pipeline flow | Split: container rels → blueprint.md, DDD rels → domain-model.md context map |
| `views.likec4` | 315 | 7 structural views + 1 businessFlow dynamic view | Structural: absorbed into inline sections. businessFlow: overview flowchart + phase deep-dives |
| `spec.likec4` | 58 | LikeC4 spec definitions (element kinds, tags, styles) | Discarded — boilerplate, no informational content |

### Madruga-AI Platform (8 .likec4 files, 817 LOC total)

| File | LOC | Content | Migration Target |
|------|-----|---------|-----------------|
| `actors.likec4` | 10 | 2 personas (operator, stakeholder) | Absorbed into blueprint.md deploy topology |
| `externals.likec4` | 27 | External services (Claude Code, GitHub, Telegram, Sentry) | Absorbed into blueprint.md deploy topology |
| `infrastructure.likec4` | 12 | SQLite, Filesystem | Absorbed into blueprint.md deploy topology |
| `platform.likec4` | 56 | 5 platform containers (Portal, Easter, DAG Executor, etc.) | Absorbed into blueprint.md containers |
| `ddd-contexts.likec4` | 128 | 6 BCs (Documentation, Specification, Execution, Intelligence, Integration, Observability) | Already in domain-model.md as classDiagram (6 existing) |
| `relationships.likec4` | 174 | Container + DDD relationships | Split: container rels → blueprint.md, DDD rels → context-map.md |
| `views.likec4` | 272 | Structural views + businessFlow | Same pattern as Fulano |
| `spec.likec4` | 138 | LikeC4 spec definitions | Discarded — boilerplate |

### Key Finding
Both platforms' `domain-model.md` files **already have Mermaid classDiagrams** for bounded contexts (L4). The migration for L4 is already done. What's missing:
- L1 (Deploy Topology) — new section in blueprint.md
- L2 (Containers) — new section in blueprint.md
- L3 (Context Map) — madruga-ai already has it in context-map.md; fulano needs creation
- L5 (Business Flow) — fulano needs conversion from 315 LOC dynamic view; madruga-ai needs conversion

---

## 3. Portal Component Inventory

### Files to Remove (12 files)

| File | LOC | Purpose |
|------|-----|---------|
| `portal/src/components/viewers/LikeC4Diagram.tsx` | 104 | React component with platformLoaders |
| `portal/src/likec4.d.ts` | ~5 | TypeScript declarations for likec4 virtual modules |
| `portal/src/pages/[platform]/landscape.astro` | 21 | System Landscape page |
| `portal/src/pages/[platform]/containers.astro` | ~21 | Containers page |
| `portal/src/pages/[platform]/context-map.astro` | ~21 | Context Map page |
| `portal/src/pages/[platform]/bc/[context].astro` | ~40 | Bounded Context detail pages |
| `portal/src/pages/[platform]/business-flow.astro` | ~21 | Business Flow page |

### Files to Modify (6 files)

| File | Change |
|------|--------|
| `portal/astro.config.mjs` | Remove `LikeC4VitePlugin` import and vite plugins config, remove esbuild jsx config, remove `portalSections` 'model' entry, remove likec4 head scripts |
| `portal/src/lib/platforms.mjs` | Remove `buildViewPaths()` function, remove `p.views.structural` reference in `buildSidebar()`, simplify sidebar |
| `portal/src/lib/constants.ts` | Remove `.likec4` extension handling in URL generation |
| `portal/src/components/dashboard/PipelineDAG.tsx` | Remove `.likec4` extension handling |
| `portal/package.json` | Remove `likec4` dependency |
| `portal/package-lock.json` | Regenerated after removing `likec4` |

---

## 4. CI Impact Analysis

### Decision
Remove the `likec4` job entirely from `.github/workflows/ci.yml`.

### Rationale
The `likec4` CI job (lines 23-43) builds LikeC4 models for all platforms. After migration, there are no `.likec4` files to build. Mermaid syntax is validated by the `portal-build` job (astro-mermaid fails on invalid Mermaid during `npm run build`).

### Alternatives Considered
- **Replace with `mmdc` validation job**: Rejected — redundant with portal-build job.
- **Keep job but make it no-op**: Rejected — dead code in CI.

---

## 5. Sidebar Simplification Strategy

### Decision
Remove dedicated diagram links from sidebar. Diagram content lives inline in existing docs.

### Current Sidebar Structure (Engineering section)
```
Engineering/
  ADRs/
  Blueprint
  System Landscape    ← REMOVE (page deleted)
  Domain Model
  Containers          ← REMOVE (page deleted)
  Context Map/        ← REMOVE entire group (pages deleted)
    Context Map
    Channel (zoom)
    Conversation (zoom)
    Safety (zoom)
    Operations (zoom)
  Integrations
```

### New Sidebar Structure
```
Engineering/
  ADRs/
  Blueprint           ← contains deploy topology + containers (Mermaid inline)
  Domain Model        ← contains context map + BC deep-dives (Mermaid inline)
  Integrations
```

### Impact on `buildSidebar()` in `platforms.mjs`
- Remove `{ label: 'System Landscape', link: ... }` entry
- Remove `{ label: 'Containers', link: ... }` entry
- Remove entire `Context Map` group (which references `p.views.structural`)
- This eliminates the dependency on `platform.yaml > views` block

---

## 6. Fulano Business Flow Decomposition

### Decision
Convert 315-line `businessFlow` dynamic view into overview flowchart + 8 phase deep-dives using `<details>` collapsible sections.

### Decomposition Plan

| Phase | Mermaid Type | ~LOC | Content |
|-------|-------------|------|---------|
| Overview | `flowchart TD` | ~25 | High-level pipeline: Entrada → Router → Pipeline Core → Saida → Handoff → Triggers → Observabilidade |
| Fase 1: Entrada | `sequenceDiagram` | ~15 | agent → M1 (Recepcao) → M2 (Debounce) → M3 (Router) |
| Fase 2: Decision Point #1 | `flowchart LR` | ~10 | Router 5 paths: SUPPORT, GROUP_RESPOND, GROUP_SAVE_ONLY, HANDOFF, IGNORE |
| Fase 3: Pipeline Core | `sequenceDiagram` | ~20 | M4 (Customer) → M5 (Contexto) → M6 (Guardrail) → M7 (Classificador) → M8 (Agente) → M9 (Avaliador) |
| Fase 4: Decision Point #3 | `flowchart LR` | ~10 | Avaliador: APPROVE → M10, RETRY → M8, ESCALATE → M12 |
| Fase 5: Saida | `sequenceDiagram` | ~10 | M10 (Guardrails) → M11 (Entrega) → Evolution API |
| Fase 6: Handoff | `sequenceDiagram` | ~15 | State machine: AGENT_ACTIVE → PENDING → ASSIGNED → HUMAN_ACTIVE → COMPLETED |
| Fase 7: Triggers | `sequenceDiagram` | ~10 | Supabase LISTEN/NOTIFY → M13 → M11 → Evolution API |
| Fase 8: Observabilidade | `flowchart LR` | ~10 | All modules → M14 → LangFuse (fire-and-forget) |

Total: ~125 LOC Mermaid (vs 315 LOC LikeC4) — 60% reduction, zero information loss.

### Alternatives Considered
- **Single large flowchart**: Rejected — ilegible at 315+ nodes.
- **1:1 conversion of dynamic view syntax**: Rejected — LikeC4 `parallel{}` and `notes` have no Mermaid equivalent; simplification needed.
- **Separate .mmd files**: Rejected — pitch explicitly says inline in .md.

---

## 7. Template Copier Changes

### Decision
Remove `model/` directory and LikeC4 config from template. Keep pipeline node outputs pointing to `.md` files.

### Files to Remove from Template
- `model/actors.likec4.jinja`
- `model/ddd-contexts.likec4.jinja`
- `model/externals.likec4.jinja`
- `model/infrastructure.likec4.jinja`
- `model/likec4.config.json.jinja`
- `model/platform.likec4.jinja`
- `model/relationships.likec4.jinja`
- `model/spec.likec4`
- `model/views.likec4.jinja`

### `platform.yaml.jinja` Changes
- Remove `model:` key
- Remove `views:` block (structural + flows)
- Remove `serve:` block
- Remove `build:` block
- Update pipeline node outputs:
  - `domain-model`: `["engineering/domain-model.md"]` (remove `model/ddd-contexts.likec4`)
  - `containers`: `["engineering/blueprint.md"]` (was `model/platform.likec4`, `model/views.likec4`)

---

## 8. vision-build.py Analysis

### Decision
Remove entirely. AUTO markers become manual content.

### Rationale
`vision-build.py` reads `model/output/likec4.json` (exported by `likec4 export json`) and populates `<!-- AUTO:name -->` markers in markdown files. With no LikeC4 export, the pipeline is broken. The AUTO markers in fulano's `context-map.md` are already empty (never populated). Madruga-ai's context-map.md already has hand-written Mermaid.

### Impact
- `platforms/fulano/engineering/context-map.md`: AUTO markers → replace with hand-written Mermaid context map
- Smoke test in CI references `vision-build.py` — must be removed from the import check list

---

## 9. Existing Mermaid Diagrams Audit

### Already Have Mermaid (no conversion needed for L4)
- `platforms/fulano/engineering/domain-model.md`: 5 classDiagrams (Channel, Conversation, Safety, Operations, Observability)
- `platforms/madruga-ai/engineering/domain-model.md`: 7 Mermaid blocks (classDiagrams for BCs)
- `platforms/madruga-ai/engineering/context-map.md`: 1 Mermaid graph (Context Map L3)
- `platforms/madruga-ai/engineering/blueprint.md`: 1 Mermaid graph (Deploy Topology L1) — already has it!

### Need New Mermaid Diagrams
| Platform | Document | Diagram Type | Source |
|----------|----------|-------------|--------|
| fulano | blueprint.md | Deploy Topology (L1) | actors + externals + infrastructure + platform.likec4 |
| fulano | blueprint.md | Containers (L2) | relationships.likec4 (container-level) |
| fulano | domain-model.md | Context Map (L3) | relationships.likec4 (DDD-level) + context-map.md AUTO markers |
| fulano | process.md | Business Flow (L5) | views.likec4 businessFlow (315 LOC) |
| madruga-ai | blueprint.md | Containers (L2) | Add subgraph detail to existing topology |
| madruga-ai | process.md or business/process.md | Business Flow (L5) | views.likec4 businessFlow (if applicable) |

### Key Finding: madruga-ai blueprint.md already has L1!
The deploy topology Mermaid diagram already exists at line 102-135. Only L2 (containers subgraphs) needs to be added.

---

## 10. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Mermaid syntax errors break portal build | Medium | Low | Build catches errors; fix before merge |
| Information loss during conversion | Low | High | Systematic audit of each .likec4 file against output .md |
| `astro-mermaid` rendering issues with complex diagrams | Low | Medium | Split complex diagrams into smaller pieces |
| Copier template breaks existing tests | Medium | Low | Run template tests after changes |
| Platform lint fails after removing `model:` and `views:` | High | Medium | Update lint script to not require these fields |
| Smoke test references vision-build.py | High | Low | Remove from entrypoint list |

---

handoff:
  from: research
  to: design
  context: "All NEEDS CLARIFICATION resolved. Key findings: L4 Mermaid already exists in domain-model.md for both platforms. L1 exists for madruga-ai. Main work: L1+L2 for fulano, L5 conversion for both, portal cleanup, CI update, template update."
  blockers: []
  confidence: Alta
  kill_criteria: "astro-mermaid does not support required diagram types (verified: it does)"
