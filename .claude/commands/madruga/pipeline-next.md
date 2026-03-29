---
description: Recommend the next pipeline DAG step based on status and layer priority
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt for it."
    required: false
argument-hint: "[platform-name]"
---

# Pipeline Next — Next Step Recommendation

Read-only skill. Analyze the pipeline status and recommend the next node to execute. Does NOT auto-execute — only suggests.

## Rule: NEVER Auto-Execute

This skill RECOMMENDS only. The user decides when and whether to execute. Zero automatic execution.

## Persona

Pipeline Advisor. Concise, direct. Write output in Brazilian Portuguese (PT-BR).

## Usage

- `/pipeline-next fulano` — Next step for "fulano"
- `/pipeline-next` — Prompt for platform

## Instructions

### 1. Collect Status

Run: `.specify/scripts/bash/check-platform-prerequisites.sh --json --status --platform <name>`

### 2. Analyze and Recommend

**Filter nodes with status=ready.**

**If 1 ready:**
```
## Recommended Next Step

**`/<skill> <platform>`**
- What it does: [1-line description]
- Dependencies: [already met]
- Gate: [human/auto/1-way-door]

To execute: `/<skill> <platform>`
```

**If multiple ready:**
List all and recommend using this priority logic:
1. **Non-optional before optional** (critical path first)
2. **Most downstream dependents first** (unblocks more work)
3. **Layer as tiebreaker:** business > research > engineering > planning

Within the same layer: fewer pending dependencies = first.

**If none ready AND all done:**
```
## Pipeline Complete!

All 14 stages are done.
Next: start implementation with the first epic from the roadmap using `/discuss <platform> <NNN>` (where NNN is the epic number).
```

**If none ready AND some blocked:**
```
## No Stage Available

Blockers:
| Skill | Blocked by |
|-------|-----------|
| ... | ... |

Resolve the blockers first.
```

### 3. Present

Show the recommendation. Do NOT execute. Wait for the user.

## Error Handling

| Issue | Action |
|-------|--------|
| Script fails | ERROR: python3 prerequisite not installed |
| platform.yaml missing pipeline section | ERROR: run `copier update` on the platform |
| Invalid platform name | Prompt for correct name |
