'---
description: Perform a non-destructive cross-artifact consistency and quality analysis across spec.md, plan.md, and tasks.md after task generation.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

---

## Goal

**Epic Dir Support**: When this skill is invoked in the context of a platform epic (e.g., via `/epic-context` → handoff), set `export SPECIFY_BASE_DIR=platforms/<name>/epics/<NNN-slug>/` before invoking any SpecKit bash scripts. This ensures all artifacts (spec.md, plan.md, tasks.md, etc.) are created within the epic directory instead of `specs/`.

Identify inconsistencies, duplications, ambiguities, and underspecified items across the three core artifacts (`spec.md`, `plan.md`, `tasks.md`) before implementation. This command MUST run only after `/speckit.tasks` has successfully produced a complete `tasks.md`.

---

## Operating Constraints

1. **STRICTLY READ-ONLY**: Do NOT modify any files. Output a structured analysis report only. Offer an optional remediation plan -- the user must explicitly approve before any follow-up edits.
2. **Constitution Authority**: The project constitution (`.specify/memory/constitution.md`) is non-negotiable. Constitution conflicts are automatically CRITICAL and require adjustment of the spec, plan, or tasks -- never dilution, reinterpretation, or silent ignoring. If a principle itself needs to change, that must occur in a separate constitution update outside `/speckit.analyze`.

---

## Execution Steps

### Step 1: Initialize Analysis Context

Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` once from repo root. Parse JSON for `FEATURE_DIR` and `AVAILABLE_DOCS`. Derive absolute paths:

- `SPEC` = `FEATURE_DIR/spec.md`
- `PLAN` = `FEATURE_DIR/plan.md`
- `TASKS` = `FEATURE_DIR/tasks.md`

Abort with an error message if any required file is missing. Instruct the user to run the missing prerequisite command.

For single quotes in args (e.g., "I'm Groot"), use escape syntax: `'I'\''m Groot'` or double-quote: `"I'm Groot"`.

### Step 2: Load Artifacts (Progressive Disclosure)

Load only the minimal necessary context from each artifact:

**From spec.md:**
- Overview/Context
- Functional Requirements
- Success Criteria (measurable outcomes: performance, security, availability, user success, business impact)
- User Stories
- Edge Cases (if present)

**From plan.md:**
- Architecture/stack choices
- Data Model references
- Phases
- Technical constraints

**From tasks.md:**
- Task IDs
- Descriptions
- Phase grouping
- Parallel markers `[P]`
- Referenced file paths

**From constitution:**
- Load `.specify/memory/constitution.md` for principle validation

### Step 3: Build Semantic Models

Create internal representations (do not include raw artifacts in output):

- **Requirements inventory**: For each Functional Requirement (FR-###) and Success Criterion (SC-###), record a stable key. Use the explicit FR-/SC- identifier as the primary key. Optionally derive an imperative-phrase slug for readability (e.g., "User can upload file" -> `user-can-upload-file`). Include only Success Criteria items that require buildable work (e.g., load-testing infrastructure, security audit tooling). Exclude post-launch outcome metrics and business KPIs (e.g., "Reduce support tickets by 50%").
- **User story/action inventory**: Discrete user actions with acceptance criteria.
- **Task coverage mapping**: Map each task to one or more requirements or stories (inference by keyword / explicit reference patterns like IDs or key phrases).
- **Constitution rule set**: Extract principle names and MUST/SHOULD normative statements.

### Step 4: Detection Passes (Token-Efficient Analysis)

Focus on high-signal findings. Limit to 50 findings total; aggregate the remainder in an overflow summary.

#### A. Duplication Detection
- Identify near-duplicate requirements.
- Mark lower-quality phrasing for consolidation.

#### B. Ambiguity Detection
- Flag vague adjectives (fast, scalable, secure, intuitive, robust) lacking measurable criteria.
- Flag unresolved placeholders (TODO, TKTK, ???, `<placeholder>`, etc.).

#### C. Underspecification
- Requirements with verbs but missing object or measurable outcome.
- User stories missing acceptance criteria alignment.
- Tasks referencing files or components not defined in spec/plan.

#### D. Constitution Alignment
- Any requirement or plan element conflicting with a MUST principle.
- Missing mandated sections or quality gates from constitution.

#### E. Coverage Gaps
- Requirements with zero associated tasks.
- Tasks with no mapped requirement/story.
- Success Criteria requiring buildable work (performance, security, availability) not reflected in tasks.

#### F. Inconsistency
- Terminology drift (same concept named differently across files).
- Data entities referenced in plan but absent in spec (or vice versa).
- Task ordering contradictions (e.g., integration tasks before foundational setup tasks without dependency note).
- Conflicting requirements (e.g., one requires Next.js while another specifies Vue).

### Step 5: Severity Assignment

Apply this heuristic:

| Severity | Criteria |
|----------|----------|
| CRITICAL | Violates constitution MUST, missing core spec artifact, or requirement with zero coverage that blocks baseline functionality |
| HIGH | Duplicate or conflicting requirement, ambiguous security/performance attribute, untestable acceptance criterion |
| MEDIUM | Terminology drift, missing non-functional task coverage, underspecified edge case |
| LOW | Style/wording improvements, minor redundancy not affecting execution order |

### Step 6: Produce Compact Analysis Report

Output a Markdown report (no file writes) with this structure:

```markdown
## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Duplication | HIGH | spec.md:L120-134 | Two similar requirements ... | Merge phrasing; keep clearer version |
```

Add one row per finding. Generate stable IDs prefixed by category initial.

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|

**Constitution Alignment Issues:** (if any)

**Unmapped Tasks:** (if any)

**Metrics:**
- Total Requirements
- Total Tasks
- Coverage % (requirements with >=1 task)
- Ambiguity Count
- Duplication Count
- Critical Issues Count

### Step 7: Provide Next Actions

At the end of the report, output a concise Next Actions block:

- If CRITICAL issues exist: Recommend resolving before `/speckit.implement`.
- If only LOW/MEDIUM: User may proceed; provide improvement suggestions.
- Provide explicit command suggestions, e.g.: "Run /speckit.specify with refinement", "Run /speckit.plan to adjust architecture", "Manually edit tasks.md to add coverage for 'performance-metrics'".

### Step 8: Offer Remediation

Ask the user: "Would you like me to suggest concrete remediation edits for the top N issues?" Do NOT apply edits automatically.

---

## Operating Principles

### Context Efficiency
- **Minimal high-signal tokens**: Focus on actionable findings, not exhaustive documentation.
- **Progressive disclosure**: Load artifacts incrementally; do not dump all content into analysis.
- **Token-efficient output**: Limit findings table to 50 rows; summarize overflow.
- **Deterministic results**: Rerunning without changes should produce consistent IDs and counts.

### Analysis Guidelines
- NEVER modify files (this is read-only analysis).
- NEVER hallucinate missing sections (if absent, report them accurately).
- Prioritize constitution violations (these are always CRITICAL).
- Use examples over exhaustive rules (cite specific instances, not generic patterns).
- Report zero issues gracefully (emit success report with coverage statistics).

---

## Context

$ARGUMENTS
