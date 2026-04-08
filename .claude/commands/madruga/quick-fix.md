---
description: Fast lane L2 cycle for bug fixes and small changes — specify → implement → judge (skips plan, tasks, analyze, qa, reconcile)
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
  - name: epic
    description: "Epic slug (e.g., 042-hotfix-auth)."
    required: false
argument-hint: "[platform] [epic-slug]"
handoffs:
  - label: Run full L2 cycle instead
    agent: madruga/epic-context
    prompt: "Quick-fix scope too large. Start full L2 cycle."
---

# Quick-Fix — Fast Lane L2 Cycle

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

Compressed L2 cycle for bug fixes and small changes: **specify → implement → judge**. Skips plan, tasks, analyze, clarify, qa, reconcile.

## Cardinal Rule: NEVER Exceed Small Scope

If the fix touches more than 3 files or exceeds ~100 LOC of changes, **STOP** and recommend the full L2 cycle via `/madruga:epic-context` instead.

## Persona

Pragmatic senior engineer. Bias for shipping fast with minimal ceremony. Still demands quality — judge review is mandatory. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/madruga:quick-fix prosauai 042-hotfix-auth` — Direct mode with platform and epic
- `/madruga:quick-fix` — Interactive mode (prompts for platform, bug description, affected files)

## When to Use

- Bug fix with clear scope (1–3 files)
- Typo, config change, or copy fix
- Change under ~100 LOC
- The problem and fix are well-understood

## When NOT to Use

- New features or significant refactors → full L2 cycle
- Changes requiring data model updates → full L2 cycle
- Scope is unclear or needs discovery → `/speckit.clarify` first

## Output Directory

Save spec to `platforms/<name>/epics/<NNN>/spec.md`. Implementation and judge artifacts follow standard paths.

---

## Instructions

### 0. Prerequisites

Follow Step 0 from `pipeline-contract-base.md` (branch guard + dependency check).

Verify the epic branch exists: `epic/<platform>/<NNN-slug>`. If not, create it via `/madruga:epic-context` first.

### 1. Collect Bug Context

Ask the user (numbered questions for reply by number):

1. **Bug description**: What is broken? What is the expected behavior?
2. **Affected files**: Which file(s) need changes? (max 3)
3. **Reproduction**: How do you reproduce the issue? (or "obvious from code")
4. **Acceptance criteria**: How will you verify the fix works?

If the user already provided this information in $ARGUMENTS, skip redundant questions.

### 2. Scope Guard

Evaluate the collected context:

- **Files affected** > 3 → STOP: "This exceeds quick-fix scope. Recommend `/madruga:epic-context`."
- **Estimated LOC** > 100 → STOP: same recommendation.
- **Requires new dependencies or schema changes** → STOP: same recommendation.

If scope is acceptable, proceed.

### 3. Generate Minimal spec.md

Create a lightweight spec at `platforms/<name>/epics/<NNN>/spec.md` with:

```markdown
# Quick-Fix: <short title>

**Type**: Bug fix / Config change / Copy fix
**Scope**: <N> file(s), ~<N> LOC estimated

## Problem
<1-2 sentences describing the bug>

## Expected Fix
<1-2 sentences describing what the fix should do>

## Affected Files
- `path/to/file1.py` — <what changes>
- `path/to/file2.py` — <what changes>

## Acceptance Criteria
- [ ] <criterion 1>
- [ ] <criterion 2>

## Out of Scope
Everything not listed above.
```

### 4. Approval Gate

Present the spec summary to the user. This is a **human gate** — wait for explicit approval before proceeding.

Show:
- Bug description (1 sentence)
- Files to change
- Estimated LOC
- Acceptance criteria

Ask: "Proceed with implementation? (yes/no)"

### 5. Delegate to Implementation

After approval, the DAG executor handles the rest automatically:
- **implement**: Executes the fix based on the spec
- **judge**: Reviews the implementation with 4 tech-reviewer personas

The quick-fix cycle is driven by `dag_executor.py --quick`, which loads the `quick_cycle` nodes from `.specify/pipeline.yaml`.

### 6. Save + Report

Follow Step 5 from `pipeline-contract-base.md` (save artifact + SQLite integration + report format).

```
## Quick-Fix complete

**File:** platforms/<name>/epics/<NNN>/spec.md
**Lines:** <N>
**Cycle:** specify → implement → judge (fast lane)

### Next step
Implementation and judge review are handled automatically by the DAG executor.
```

---
handoff:
  from: madruga:quick-fix
  to: speckit.implement
  context: "Quick-fix spec generated with minimal ceremony. Scope verified as small (<3 files, <100 LOC). Proceed to implement, then judge."
  blockers: []
  confidence: Alta
  kill_criteria: "If scope exceeds 3 files or 100 LOC during implementation, abort and escalate to full L2 cycle."
