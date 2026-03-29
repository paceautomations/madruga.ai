---
description: Generate or update STATE.md with current session progress — tasks, decisions, issues, next steps
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
  - name: context
    description: "Brief session context (e.g., 'wave 3 implementation')."
    required: false
argument-hint: "[platform] [session-context]"
---

# Checkpoint — Session State

> **Contract**: Follow step 0 from `.claude/knowledge/pipeline-contract-base.md`.

Lightweight skill. Generate or update STATE.md with session progress: completed tasks, decisions, issues, and next steps. Based on real data (git log, tasks.md, filesystem).

## Cardinal Rule: ZERO Invented Information

Base everything on git log, tasks.md, and the real filesystem. No assumptions.

## Persona

Session Recorder. Factual, concise. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/checkpoint wave 3` — Session checkpoint with context
- `/checkpoint` — Generic checkpoint

## Instructions

### 1. Collect Data

- Existing STATE.md (if present — for appending)
- tasks.md — tasks marked [X]
- `git log --oneline -20` — recent commits
- `git diff --stat` — changed files

### 2. Generate/Update STATE.md

If STATE.md exists, append a new session section. If not, create it.

```markdown
# STATE — [Feature/Context]

**Session**: YYYY-MM-DD
**Branch**: `branch-name`

## Completed

[Tasks marked [X] in this session]

## Decisions Made

[Decisions taken and why — extract from commits/context]

## Issues and Solutions

[Issues encountered and how they were resolved]

## Next Steps

[Derived from pending tasks]

## Changed Files

[List of created/modified files]
```

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Do all [X] tasks have corresponding commits? | Verify via git log |
| 2 | Is there any invented information? | Cross-check with git log/filesystem |
| 3 | Are next steps derived from real pending tasks? | Verify against tasks.md |

### 4. Gate: Auto

No human approval required. Save immediately.

### 5. Save + Report

```
## Checkpoint saved

**File:** [path/STATE.md]
**Tasks done this session:** <N>
**Next steps:** <N>
```

## Error Handling

| Issue | Action |
|-------|--------|
| No tasks.md found | Create minimal STATE.md based on git log |
| No git repo | Create STATE.md based on filesystem only |

---
handoff:
  from: checkpoint
  to: null
  context: "Utilitario. STATE.md salvo."
  blockers: []
