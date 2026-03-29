# Feature Specification: Atomic Skills DAG Pipeline

**Feature Branch**: `001-atomic-skills-dag-pipeline`
**Created**: 2026-03-29
**Status**: Draft
**Input**: Platform documentation pipeline — atomic skills with DAG orchestration for madruga.ai

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Document a Platform from Scratch (Priority: P1)

As an architect, I invoke atomic skills one by one to document a new platform incrementally. Each skill runs with fresh context, reads only its dependency artifacts, questions my assumptions with structured prompts, and produces a single validated artifact. I approve each artifact before the next skill runs.

**Why this priority**: This is the core value — replacing the big-bang `/architecture-portal` with incremental, validated, context-fresh documentation. Without this, nothing else works.

**Independent Test**: Can be fully tested by creating a test platform and invoking `/business-process test-plat` — it should check prerequisites, read vision + solution-overview, ask structured questions, generate `business/process.md`, run auto-review, present gate approval, and suggest the next skill via handoff.

**Acceptance Scenarios**:

1. **Given** a platform with `business/vision.md` and `business/solution-overview.md` validated, **When** I invoke `/business-process test-plat`, **Then** the skill checks prerequisites (both files exist), reads them as context, presents structured questions (premissas, trade-offs, gaps, provocação), waits for my answers, generates `business/process.md`, runs auto-review, presents gate approval, and suggests `/tech-research test-plat` as next step.
2. **Given** a platform with NO `business/vision.md`, **When** I invoke `/solution-overview test-plat`, **Then** the skill aborts with a clear error listing the missing dependency and which skill generates it (`/vision-one-pager`).
3. **Given** a platform with all business + research + engineering artifacts done, **When** I invoke `/epic-breakdown test-plat`, **Then** the skill presents a 1-way-door gate listing each epic scope decision with ≥3 alternatives, requires explicit confirmation before saving.

---

### User Story 2 - See Pipeline Status and Next Step (Priority: P1)

As an architect, I invoke `/pipeline-status <platform>` to see exactly where I am in the documentation pipeline — which artifacts are done, which are ready to generate, and which are blocked. I then invoke `/pipeline-next <platform>` to get a recommendation of what to run next.

**Why this priority**: Without visibility into pipeline state, the architect doesn't know what to do next. This is the orchestration awareness that makes atomic skills usable.

**Independent Test**: Can be tested by running `/pipeline-status madruga-ai` on a platform that has some artifacts (vision, solution-overview) and lacks others — it should show a table with done/ready/blocked status and a Mermaid DAG with color coding.

**Acceptance Scenarios**:

1. **Given** a platform with `business/vision.md` and `business/solution-overview.md` existing, **When** I run `/pipeline-status test-plat`, **Then** I see a table showing vision=done, solution-overview=done, business-process=ready, tech-research=blocked, and a progress count (2/14 done), plus a Mermaid DAG.
2. **Given** the same state, **When** I run `/pipeline-next test-plat`, **Then** it recommends `/business-process test-plat` as the next skill to run (does NOT auto-execute).
3. **Given** a platform with ALL 14 artifacts done, **When** I run `/pipeline-status test-plat`, **Then** it shows "Pipeline complete! 14/14 nodes done." and suggests starting the per-epic implementation cycle.

---

### User Story 3 - Skills Validate Prerequisites and Abort Early (Priority: P2)

As an architect, every skill I invoke first checks that its dependency artifacts exist. If something is missing, the skill fails fast with a clear error message that tells me exactly what's missing and which skill to run to generate it. No tokens are wasted on generation when prerequisites aren't met.

**Why this priority**: Fail-fast prevents wasted work and frustration. It's the safety net that makes the DAG reliable.

**Independent Test**: Can be tested by invoking any skill whose dependencies are missing — it should error immediately with actionable guidance.

**Acceptance Scenarios**:

1. **Given** a platform with only `platform.yaml`, **When** I invoke `/blueprint test-plat`, **Then** the script `check-platform-prerequisites.sh` returns `ready: false` with `missing` listing the dependency artifacts, and the skill aborts with: "Missing prerequisites: run `/tech-research test-plat` then `/adr-gen test-plat` first."
2. **Given** a brownfield platform where `codebase-map` is optional, **When** I invoke `/adr-gen test-plat` without `research/codebase-context.md`, **Then** adr-gen proceeds because codebase-map is marked `optional: true` in the DAG.

---

### User Story 4 - Skills Chain via Handoffs (Priority: P2)

As an architect, after each skill completes and I approve the artifact, the skill suggests the next logical step via a handoff. I can follow the suggestion or choose a different path. The chain of handoffs forms a natural walkthrough of the entire pipeline.

**Why this priority**: Handoffs eliminate the need to remember the DAG order. Each skill tells you what comes next.

**Independent Test**: Can be tested by invoking `/vision-one-pager test-plat`, approving the output, and verifying it suggests `/solution-overview test-plat` as the handoff.

**Acceptance Scenarios**:

1. **Given** I just completed `/vision-one-pager test-plat` and approved it, **When** the skill finishes, **Then** it presents a handoff: "Next: `/solution-overview test-plat` — Generate solution overview based on validated vision."
2. **Given** I just completed `/context-map test-plat`, **When** the skill finishes, **Then** it presents a handoff to `/epic-breakdown test-plat` with a note: "This is a 1-way-door gate — epic scope decisions are hard to reverse."

---

### User Story 5 - Skills Question Assumptions and Research Best Practices (Priority: P2)

As an architect, every business and engineering skill acts as a senior consultant — it reads my dependency artifacts, identifies implicit assumptions, researches current best practices, presents alternatives with pros/cons, and asks me structured questions before generating. It doesn't just fill a template; it challenges my thinking.

**Why this priority**: The questioning behavior is what makes the pipeline produce high-quality artifacts instead of boilerplate.

**Independent Test**: Can be tested by invoking `/tech-research test-plat` — it should spawn parallel research agents, present ≥3 alternatives per technology decision with pros/cons/recommendation, and ask structured questions before generating.

**Acceptance Scenarios**:

1. **Given** I invoke `/tech-research test-plat` with business layer complete, **When** the skill analyzes the context, **Then** it identifies key technology decisions, spawns parallel research agents (stack, patterns, pitfalls), and presents a decision matrix with ≥3 alternatives per decision including: cost, performance, complexity, community health, and fit.
2. **Given** I invoke `/blueprint test-plat`, **When** the skill reads ADRs and business layer, **Then** it presents structured questions in 4 categories: Premissas ("I assume X — correct?"), Trade-offs ("A simpler vs B more robust?"), Gaps ("No info about X — you define or I research?"), Provocação ("Y is standard but Z may be better because...").
3. **Given** any skill with `gate: human` completes generation, **When** it presents the auto-review, **Then** the review includes checks for: alternatives documented, assumptions marked, best practices researched, trade-offs explicit.

---

### User Story 6 - Daemon Can Execute Pipeline Autonomously (Priority: P3)

As a future daemon (autonomous agent), I read the DAG from `platform.yaml`, execute skills in topological order, stop at human gates for approval, skip optional nodes, and continue automatically through auto gates. The skills don't know they're being called by a daemon — they work the same way as when invoked manually.

**Why this priority**: This is the future evolution (mode C). It's P3 because it requires all skills (P1) and orchestration (P1-P2) to work first. The design should support it but implementation is deferred.

**Independent Test**: Can be verified structurally — every skill has the same contract (prerequisites → context → generation → auto-review → gate → save → handoff), and the DAG schema includes `gate` types that the daemon can interpret.

**Acceptance Scenarios**:

1. **Given** a pipeline node with `gate: auto`, **When** the daemon invokes the skill and it completes successfully, **Then** the daemon detects the output file exists and proceeds to the next node without pausing.
2. **Given** a pipeline node with `gate: 1-way-door`, **When** the daemon reaches it, **Then** it ALWAYS pauses, notifies the human, and waits for explicit approval before proceeding.
3. **Given** a pipeline node with `gate: auto-escalate`, **When** the skill (verify) finds blockers, **Then** the daemon pauses and escalates; when no blockers found, it continues automatically.

---

### Edge Cases

- What happens when a skill's output already exists? The skill reads it as a base and offers to update (idempotent), not overwrite blindly.
- What happens when a platform has no `platform.yaml` pipeline section? The `check-platform-prerequisites.sh` script errors with "No pipeline section found — run `copier update` or add pipeline manually."
- What happens when an optional node (codebase-map) is skipped? Downstream nodes that depend on it are NOT blocked; they proceed without the optional context.
- What happens when `output_pattern` (e.g., `decisions/ADR-*.md`) has no matches? The node is considered NOT done; the script uses glob matching to detect at least one file matching the pattern.
- What happens when the user runs skills out of DAG order? The prerequisites check blocks them with a clear error and the correct order.
- What happens when a 1-way-door gate is rejected? The skill loops back to generation (step 2) with the user's feedback, regenerates, and re-presents the gate.

## Requirements *(mandatory)*

### Functional Requirements

**Infrastructure:**
- **FR-001**: The system MUST provide a `check-platform-prerequisites.sh` script that validates skill dependencies by reading `platform.yaml` pipeline nodes, checking file existence, and returning JSON with `ready`, `missing`, `available`, `depends_on`, and `outputs` fields.
- **FR-002**: The script MUST support `--status` mode that returns all pipeline nodes with status (done/ready/blocked), next available nodes, and progress count.
- **FR-003**: The script MUST handle `optional: true` nodes by excluding them from dependency blocking — downstream nodes proceed even if optional node output is missing.
- **FR-004**: The script MUST handle `output_pattern` (glob) by using file system matching to determine if variable-name outputs (e.g., `decisions/ADR-*.md`) exist.
- **FR-005**: The `platform.yaml` template MUST include a `pipeline` section with 14 nodes declaring `id`, `skill`, `outputs`, `depends`, `layer`, `gate`, and optional `optional`/`output_pattern` fields.

**Skill Contract:**
- **FR-006**: Every skill MUST follow the uniform contract: frontmatter (description, arguments, handoffs) → regra cardinal → persona → uso → diretório → instruções (0. prerequisites, 1. context+question, 2. generate, 3. auto-review, 4. gate approval, 5. save+report).
- **FR-007**: Every skill MUST call `check-platform-prerequisites.sh` as step 0 and abort with actionable error if `ready: false`.
- **FR-008**: Every skill MUST read `.specify/memory/constitution.md` as part of step 0 and validate generated content against core principles.
- **FR-009**: Every skill with `gate: human` or `gate: 1-way-door` MUST present a gate approval section with: summary, decisions taken, alternatives considered, and validation questions before saving.
- **FR-010**: Every skill MUST present a standardized final report with: file path, line count, auto-review checks, and next step handoff.
- **FR-011**: Every skill MUST declare handoffs in frontmatter pointing to the next skill(s) in the DAG.

**Questioning Behavior:**
- **FR-012**: Skills in business and engineering layers MUST identify implicit assumptions from dependency artifacts and present them as structured questions in 4 categories: Premissas, Trade-offs, Gaps, Provocação.
- **FR-013**: Skills MUST research best practices (via subagents, Context7, or web search) before generating artifacts, and reference findings in the output.
- **FR-014**: Skills MUST present ≥2 alternatives with pros/cons for every significant decision in the generated artifact.
- **FR-015**: Skills MUST mark unvalidated assumptions with `[VALIDAR]` in the generated artifact.

**Gate Types:**
- **FR-016**: The system MUST support 4 gate types: `human` (always pause for approval), `auto` (proceed without pausing), `1-way-door` (always pause, even in autonomous mode, list decisions with ≥3 alternatives), `auto-escalate` (auto if no blockers, escalate to human if blockers found).
- **FR-017**: Skills with `gate: 1-way-door` MUST list every irreversible decision with ≥3 alternatives, pros/cons, and recommendation, and require explicit per-decision confirmation.

**Auto-Review:**
- **FR-018**: Every skill MUST include an auto-review checklist that validates: decisions have alternatives, assumptions are marked, best practices researched, trade-offs explicit, plus artifact-specific checks.

**Orchestration:**
- **FR-019**: `/pipeline-status` MUST display: table of all nodes (status, layer, gate, approval state), Mermaid DAG with color coding, progress count, and next available nodes.
- **FR-020**: `/pipeline-next` MUST identify the next ready node(s), recommend one, and present it as a handoff suggestion (NOT auto-execute).

**Existing Skill Adaptation:**
- **FR-021**: `/vision-one-pager`, `/solution-overview`, and `/platform-new` MUST be adapted to include prerequisites check (step 0) and updated handoffs, without breaking their existing functionality.

**Templates and Knowledge:**
- **FR-022**: New Copier templates MUST be created for new artifacts (`business/process.md`, `engineering/folder-structure.md`, `planning/roadmap.md`, `research/codebase-context.md`, `research/tech-alternatives.md`) with `[ALL_CAPS]` placeholders and `<!-- ACTION REQUIRED -->` comments.
- **FR-023**: A `pipeline-dag-knowledge.md` file MUST be created in `.claude/knowledge/` documenting the canonical DAG, skill contracts, gate types, and examples.

### Key Entities

- **Skill**: A self-contained Claude Code command that reads dependency artifacts, questions assumptions, generates a single output artifact, and suggests the next step. Has: id, description, persona, gate type, dependencies, outputs, handoffs.
- **Pipeline Node**: A declaration in `platform.yaml` mapping a skill to its outputs, dependencies, layer, and gate type. Has: id, skill reference, outputs (file paths), depends (node ids), layer, gate, optional flag, output_pattern.
- **Platform**: A documented system living under `platforms/<name>/` with `platform.yaml` manifest, artifacts in business/engineering/decisions/epics/research/planning/model directories, and a pipeline DAG.
- **Artifact**: A markdown or LikeC4 file produced by a skill. Exists on filesystem = skill is "done". Has: path, template, generating skill.
- **Gate**: An approval checkpoint in the pipeline. Types: human (always pause), auto (never pause), 1-way-door (always pause with decision confirmation), auto-escalate (auto unless blockers).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of new skills (17) follow the uniform contract — verified by grep of required sections (Pré-requisitos, Auto-Review, Gate, handoffs).
- **SC-002**: `check-platform-prerequisites.sh` correctly identifies done/ready/blocked status for all 14 pipeline nodes — verified by running `--status` on a platform with partial artifacts.
- **SC-003**: Every skill with `gate: human` or `1-way-door` presents structured questions before generating — verified by manual invocation of 3+ skills.
- **SC-004**: Handoff chain is complete with zero broken links — every skill's handoff target references an existing skill.
- **SC-005**: DAG integrity: every `depends` reference resolves to an existing node `id` — verified by a validation script.
- **SC-006**: Existing skills (`/vision-one-pager`, `/solution-overview`) continue to work correctly after adaptation — verified by invoking on existing platform.
- **SC-007**: Copier template produces a valid `platform.yaml` with pipeline section — verified by `copier copy` to temp directory.
- **SC-008**: An architect can document a new platform from scratch by following handoffs skill-by-skill, with clear next steps at every point — verified by walkthrough on a test platform.

## Clarifications

### Session 2026-03-29

- No critical ambiguities detected. All categories (Functional Scope, Domain Model, Interaction Flow, Non-Functional, Integration, Edge Cases, Constraints, Terminology, Completion Signals) assessed as Clear. Spec ready for planning.

## Assumptions

- The madruga.ai repo is the sole target — no changes to `general/services/madruga-ai`.
- Skills are Claude Code custom commands (`.claude/commands/madruga/*.md`) — no Python service code.
- The daemon (autonomous mode) is a future evolution — this spec designs for it but does not implement it.
- All skills operate on a single platform at a time (no cross-platform orchestration).
- The `check-platform-prerequisites.sh` script uses `python3 -c` with `yaml.safe_load` for YAML parsing (Python 3.11+ is a prerequisite per CLAUDE.md).
- Gate approval is conversational (the skill asks, the user responds in chat) — no external approval system.
- Per-epic implementation cycle (discuss → SpecKit → verify → reconcile) is NOT part of the platform DAG — it's managed by existing SpecKit workflow per epic.
- Existing platforms (fulano, madruga-ai) will need `copier update` to get the pipeline section in their `platform.yaml`.
