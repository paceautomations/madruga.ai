# Tasks: Atomic Skills DAG Pipeline

**Input**: Design documents from `/specs/001-atomic-skills-dag-pipeline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Validation via bash syntax check, YAML parsing, grep for required sections, and manual skill invocation. No unit test framework — skills are markdown prompts.

**Organization**: Tasks are grouped in 9 waves by dependency. Each wave can be committed independently. Skills within a wave that touch different files can run in parallel [P].

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[US#]**: Maps to user story from spec.md

## Path Conventions

- Skills: `.claude/commands/madruga/<name>.md`
- Templates: `.specify/templates/platform/template/<path>.jinja`
- Scripts: `.specify/scripts/bash/<name>.sh`
- Knowledge: `.claude/knowledge/<name>.md`
- Config: `.specify/templates/platform/copier.yml`

---

## Phase 1: Setup — Infrastructure

**Purpose**: Create the foundation that all skills depend on — prerequisites script, knowledge file, pipeline schema, and Copier template updates.

**Checkpoint**: After this phase, `check-platform-prerequisites.sh --status --platform madruga-ai` returns valid JSON.

- [X] T001 Create `check-platform-prerequisites.sh` in `.specify/scripts/bash/check-platform-prerequisites.sh` — implement `--json`, `--platform`, `--skill`, `--status`, `--help` modes per CLI contract in `contracts/check-platform-prerequisites-cli.md`. Reuse `common.sh` functions (get_repo_root, json_escape, has_jq). Parse `platform.yaml` via `python3 -c yaml.safe_load`. Handle `optional: true` nodes and `output_pattern` globs.
- [X] T002 [P] Create `pipeline-dag-knowledge.md` in `.claude/knowledge/pipeline-dag-knowledge.md` — document: canonical DAG (14 nodes with all fields), skill uniform contract (6 sections with examples), 4 gate types with behavior descriptions, persona definitions per layer, structured questions framework (Premissas/Trade-offs/Gaps/Provocação), auto-review checklist template, handoff declaration examples.
- [X] T003 [P] Modify `platform.yaml.jinja` in `.specify/templates/platform/template/platform.yaml.jinja` — add `pipeline:` section with 14 nodes: platform-new, vision, solution-overview, business-process, tech-research, codebase-map (optional), adr-gen (1-way-door), blueprint, folder-arch, domain-model, containers, context-map, epic-breakdown (1-way-door), roadmap. Each node with: id, skill, outputs, depends, layer, gate.
- [X] T004 [P] Modify `copier.yml` in `.specify/templates/platform/copier.yml` — add `_skip_if_exists` entries for: `business/process.md`, `engineering/folder-structure.md`, `planning/*`, `research/codebase-context.md`, `research/tech-alternatives.md`. Create stub templates: `business/process.md.jinja`, `engineering/folder-structure.md.jinja`, `planning/roadmap.md.jinja`, `planning/.gitkeep`, `research/codebase-context.md.jinja`, `research/tech-alternatives.md.jinja`. Each with `<!-- ACTION REQUIRED -->` placeholders and Jinja header.

**Validation Wave 1**:
- `bash -n .specify/scripts/bash/check-platform-prerequisites.sh`
- `check-platform-prerequisites.sh --help` shows usage
- `copier copy .specify/templates/platform/ /tmp/test-plat-001/ --defaults -d platform_name=test` → platform.yaml has pipeline section with 14 nodes

---

## Phase 2: Foundational — Adapt Existing Skills

**Purpose**: Update 3 existing skills to integrate with the pipeline (prerequisites check + handoffs). Must NOT break existing functionality.

**Checkpoint**: Existing skills work on both fulano and madruga-ai platforms. Handoff chain starts.

- [X] T005 [US4] Modify `platform-new.md` in `.claude/commands/madruga/platform-new.md` — add handoff in frontmatter pointing to `madruga/vision-one-pager` with prompt "Generate vision for the new platform". Keep all existing functionality intact.
- [X] T006 [P] [US4] Modify `vision-one-pager.md` in `.claude/commands/madruga/vision-one-pager.md` — add section 0 (Pré-requisitos) calling `check-platform-prerequisites.sh --json --platform <nome> --skill vision`. Add handoff to `madruga/solution-overview`. Preserve all existing sections (Regra Cardinal, Persona, template, auto-review).
- [X] T007 [P] [US4] Modify `solution-overview.md` in `.claude/commands/madruga/solution-overview.md` — add section 0 (Pré-requisitos) calling `check-platform-prerequisites.sh --json --platform <nome> --skill solution-overview`. Add handoff to `madruga/business-process`. Preserve all existing sections.

**Validation Wave 2**:
- Grep handoffs in all 3 modified skills: `grep -c "handoffs" .claude/commands/madruga/{platform-new,vision-one-pager,solution-overview}.md` → ≥1 each
- Handoff chain: platform-new → vision → solution-overview → (business-process)

---

## Phase 3: User Story 1 — Document a Platform (Business Skills)

**Goal**: Enable the core flow: platform-new → vision → solution-overview → business-process

**Independent Test**: Invoke `/business-process` on a platform with vision + solution-overview. It should check prereqs, ask structured questions, generate process.md, auto-review, present gate, suggest next step.

- [ ] T008 [US1] Create skill `business-process.md` in `.claude/commands/madruga/business-process.md` — follow uniform contract from `pipeline-dag-knowledge.md`. Persona: Estrategista Bain/McKinsey. Regra Cardinal: ZERO conteúdo técnico. Reads: vision.md + solution-overview.md. Generates: business/process.md with 3-5 core business flows as Mermaid sequence diagrams. Structured questions: identify implicit business assumptions, ask about flow priorities, challenge obvious processes. Auto-review: zero tech terms, every flow has happy path + exception, max 120 lines. Gate: human. Handoff: tech-research.

**Validation Wave 3**:
- Grep required sections in business-process.md: Pré-requisitos, Auto-Review, Gate, handoffs → all present
- `check-platform-prerequisites.sh --json --platform madruga-ai --skill business-process` → returns JSON with depends=[solution-overview]

---

## Phase 4: User Story 1 — Document a Platform (Research Skills)

**Goal**: Enable tech-research and codebase-map for technology decision-making.

**Independent Test**: Invoke `/tech-research` with business layer complete. It should spawn research agents, present decision matrix with ≥3 alternatives, require 1-way-door confirmation.

- [ ] T009 [US1] [US5] Create skill `tech-research.md` in `.claude/commands/madruga/tech-research.md` — Persona: Analista de Pesquisa Tech Senior. Reads: business/* (all business layer artifacts). Spawns parallel Agent subagents for each technology decision (stack, patterns, pitfalls, libs). Uses Context7 and web search. Generates: research/tech-alternatives.md with decision matrix (≥3 alternatives per decision with: cost, performance, complexity, community, fit). Gate: **1-way-door** — lists every tech decision, requires per-decision confirmation. Handoff: adr-gen.
- [ ] T010 [P] [US1] Create skill `codebase-map.md` in `.claude/commands/madruga/codebase-map.md` — Persona: Staff Engineer. Detects brownfield vs greenfield (checks for source repo in platform.yaml or src/ directory). If greenfield: generates minimal codebase-context.md ("Greenfield project"). If brownfield: spawns parallel agents (file structure, dependencies, patterns, integrations). Generates: research/codebase-context.md. Gate: auto. Handoff: none (optional node).

**Validation Wave 4**:
- tech-research has 1-way-door gate instruction and spawns Agent subagents
- codebase-map detects brownfield/greenfield and is marked optional
- `check-platform-prerequisites.sh --json --platform madruga-ai --skill tech-research` → depends=[business-process]

---

## Phase 5: User Story 1 — Document a Platform (Engineering Core Skills)

**Goal**: Enable ADR generation, blueprint, and folder architecture.

- [ ] T011 [US1] [US5] Create skill `adr-gen.md` in `.claude/commands/madruga/adr-gen.md` — Persona: Staff Engineer. Reads: research/tech-alternatives.md (decision matrix) + codebase-context.md (if exists). For each technology decision: generates `decisions/ADR-NNN-kebab-case.md` in Nygard format (Context, Decision, Alternatives, Consequences). Uses Context7 to research best practices for each chosen technology. Gate: **1-way-door** — lists each ADR being created, requires confirmation. Handoff: blueprint. output_pattern: `decisions/ADR-*.md`.
- [ ] T012 [P] [US1] [US5] Create skill `blueprint.md` in `.claude/commands/madruga/blueprint.md` — Persona: Staff Engineer. Reads: ADRs + business/* + codebase-context.md (if exists). Generates: engineering/blueprint.md using existing blueprint.md.jinja template structure. Fills: concerns transversais, NFRs, deploy topology, data map, glossary. Questions: "Is this the simplest thing that works?", references Netflix/Shopify/Stripe patterns. Research via Context7 for each concern. Gate: human. Handoff: folder-arch AND domain-model.
- [ ] T013 [P] [US1] Create skill `folder-arch.md` in `.claude/commands/madruga/folder-arch.md` — Persona: Staff Engineer. Reads: blueprint.md + ADRs. Generates: engineering/folder-structure.md with annotated folder tree (purpose of each directory) + naming conventions + module boundaries. Gate: human. Handoff: none (terminal node in this branch).

**Validation Wave 5**:
- adr-gen has 1-way-door gate, Nygard format, output_pattern instruction
- blueprint references existing template, fills all sections
- folder-arch generates annotated tree
- Handoff chain: tech-research → adr-gen → blueprint → folder-arch

---

## Phase 6: User Story 1 — Document a Platform (Engineering DDD Skills)

**Goal**: Enable DDD domain model, containers, and context map.

- [ ] T014 [US1] [US5] Create skill `domain-model.md` in `.claude/commands/madruga/domain-model.md` — Persona: Staff Engineer / DDD Expert. Reads: blueprint.md + business/process.md. Generates: engineering/domain-model.md (bounded contexts, aggregates, entities, value objects, invariants, Mermaid class diagrams, SQL schemas) + model/ddd-contexts.likec4 (LikeC4 DSL for interactive portal diagrams). Questions about domain boundaries, aggregate sizing, context splitting. Gate: human. Handoff: containers.
- [ ] T015 [P] [US1] [US5] Create skill `containers.md` in `.claude/commands/madruga/containers.md` — Persona: Staff Engineer. Reads: domain-model.md + blueprint.md. Generates: engineering/containers.md (C4 L2 diagram, container table, protocols, NFRs per container) + model/platform.likec4 + model/views.likec4 (LikeC4 DSL). Gate: human. Handoff: context-map.
- [ ] T016 [P] [US1] [US5] Create skill `context-map.md` in `.claude/commands/madruga/context-map.md` — Persona: Staff Engineer / DDD Expert. Reads: domain-model.md + containers.md. Generates: engineering/context-map.md (relationships between bounded contexts: upstream/downstream, conformist, ACL, shared kernel, customer/supplier). Uses existing context-map.md.jinja template with AUTO markers. Gate: human. Handoff: epic-breakdown.

**Validation Wave 6**:
- domain-model generates both .md and .likec4 files
- containers generates both .md and LikeC4 model files
- context-map references DDD patterns (upstream/downstream, ACL, etc.)
- Handoff chain: blueprint → domain-model → containers → context-map

---

## Phase 7: User Story 1 — Document a Platform (Planning Skills)

**Goal**: Enable epic breakdown (Shape Up) and roadmap generation.

- [ ] T017 [US1] Create skill `epic-breakdown.md` in `.claude/commands/madruga/epic-breakdown.md` — Persona: Product Manager / Architect. Reads: domain-model.md + containers.md + context-map.md + business/* (full context). Breaks the project into épicos using Shape Up format: Problem, Appetite (2w or 6w cycle), Solution, Rabbit Holes, No-gos, Acceptance Criteria. Creates: `epics/NNN-slug/pitch.md` for each epic. Gate: **1-way-door** — lists each epic scope, requires confirmation of scope/priority. Handoff: roadmap.
- [ ] T018 [P] [US1] Create skill `roadmap.md` in `.claude/commands/madruga/roadmap.md` — Persona: Product Manager. Reads: all epics/*/pitch.md. Generates: planning/roadmap.md with: epic sequence, dependencies between epics, timeline estimates, milestones, MVP definition. Gate: human. Handoff: "Pipeline complete! Start per-epic implementation with `/discuss <platform>`".

**Validation Wave 7**:
- epic-breakdown uses Shape Up format (Problem, Appetite, Solution, Rabbit Holes, No-gos, AC)
- epic-breakdown has 1-way-door gate
- roadmap reads all epics and sequences them
- Handoff chain: context-map → epic-breakdown → roadmap

---

## Phase 8: User Story 1 + US3 + US5 — Implementation Support Skills

**Goal**: Enable the per-epic implementation cycle skills (discuss, verify, checkpoint, reconcile).

- [ ] T019 [US1] Create skill `discuss.md` in `.claude/commands/madruga/discuss.md` — Persona: Staff Engineer. Reads: epic pitch.md + all architecture docs (blueprint, DDD, containers). Identifies "gray areas" by feature type (visual→layout, API→error handling, data→schema). Asks structured questions about implementation preferences. Generates: epics/<N>/context.md (decisions captured before SpecKit cycle). Gate: human. Handoff: "Run `/speckit.specify` to start the implementation cycle for this epic."
- [ ] T020 [P] [US1] Create skill `verify.md` in `.claude/commands/madruga/verify.md` — Persona: QA Lead. Reads: spec.md + tasks.md + codebase (git diff or file scan). Compares implementation vs spec (functional requirements covered?), vs tasks (phantom completions?), vs architecture (drift?). Generates: verify-report.md with adherence score. Gate: **auto-escalate** — auto if all OK, escalate if blockers found.
- [ ] T021 [P] [US1] Create skill `checkpoint.md` in `.claude/commands/madruga/checkpoint.md` — Lightweight skill. Reads: current STATE.md (if exists) + tasks.md + git log. Generates/updates: STATE.md with: tasks completed this session, decisions taken (and why), problems encountered and solutions, next steps, files touched. Gate: auto. No handoff (called between waves).
- [ ] T022 [P] [US1] Create skill `reconcile.md` in `.claude/commands/madruga/reconcile.md` — Persona: Architect. Reads: git diff of merged PR + all business/engineering docs. Compares implementation with architecture, identifies drift. Proposes updates to: business layer (if scope changed), engineering layer (if architecture diverged), LikeC4 model (if containers/contexts changed). Gate: human. Handoff: "Documentation updated. Run `/pipeline-status <platform>` to verify."

**Validation Wave 8**:
- discuss generates context.md per epic with implementation preferences
- verify has auto-escalate gate
- checkpoint generates STATE.md with session state
- reconcile reads git diff and proposes doc updates

---

## Phase 9: User Story 2 — Pipeline Status and Orchestration

**Goal**: Enable pipeline visibility and next-step recommendation.

- [ ] T023 [US2] Create skill `pipeline-status.md` in `.claude/commands/madruga/pipeline-status.md` — Reads: `check-platform-prerequisites.sh --json --status --platform <nome>` output. Renders: table of all nodes (status emoji, layer, gate, missing deps), Mermaid DAG with color coding (green=done, yellow=ready, red=blocked, gray=skipped), progress count (N/14 done), next available node(s). Gate: N/A (read-only skill). No handoff — suggests running the next ready skill.
- [ ] T024 [P] [US2] Create skill `pipeline-next.md` in `.claude/commands/madruga/pipeline-next.md` — Reads: `check-platform-prerequisites.sh --json --status --platform <nome>` output. Filters nodes with status=ready. If one ready: suggests it. If multiple ready: lists all, recommends by layer priority (business > research > engineering > planning). If none ready: reports blocked/complete. Does NOT auto-execute — recommends and waits. Gate: N/A (read-only).

**Validation Wave 9**:
- pipeline-status renders table + Mermaid DAG
- pipeline-next recommends but does NOT auto-execute
- Both call check-platform-prerequisites.sh --status

---

## Dependencies & Execution Order

```
Wave 1 (Infra):       T001, T002, T003, T004 — all parallel
Wave 2 (Adapt):       T005, T006, T007 — parallel (after Wave 1)
Wave 3 (Business):    T008 — sequential (after Wave 2)
Wave 4 (Research):    T009, T010 — parallel (after Wave 3)
Wave 5 (Eng Core):    T011, T012, T013 — T011 first, then T012+T013 parallel
Wave 6 (Eng DDD):     T014, T015, T016 — T014 first, then T015+T016 parallel
Wave 7 (Planning):    T017, T018 — sequential
Wave 8 (Impl Support):T019, T020, T021, T022 — all parallel
Wave 9 (Orchestration):T023, T024 — parallel
```

## Implementation Strategy

**MVP (Waves 1-3)**: Infrastructure + adapted skills + business-process = architect can start documenting with prerequisites validation and handoffs.

**Full Pipeline (Waves 4-7)**: All 14 DAG nodes have skills = complete documentation journey from vision to roadmap.

**Implementation Cycle (Wave 8)**: Per-epic tools = discuss, verify, checkpoint, reconcile.

**Orchestration (Wave 9)**: Visibility layer = pipeline-status + pipeline-next.

**Total**: 24 tasks, 9 waves, ~25 files created/modified.
