---
description: "[DEPRECATED] Use /madruga:judge instead. Redirects to Judge skill."
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
  - name: epic
    description: "Epic number (e.g., 001)."
    required: false
argument-hint: "[platform] [epic-number]"
handoffs:
  - label: Judge (replacement)
    agent: madruga/judge
    prompt: "Verify is deprecated. Use /madruga:judge for tech-reviewers quality review."
---

# Verify — DEPRECATED

> **This skill has been replaced by `/madruga:judge`** (Epic 015).
>
> The Judge provides multi-persona review (4 specialized reviewers + Judge pass) instead of the old single-perspective verify.

## Migration

- **Old**: `/madruga:verify <platform> <epic>` → `verify-report.md`
- **New**: `/madruga:judge <platform> <epic>` → `judge-report.md`

## What Changed

| Aspect | Verify (old) | Judge (new) |
|--------|-------------|-------------|
| Reviewers | Single generic check | 4 specialized personas in parallel |
| Focus | Adherence (spec vs code) | Engineering quality (bugs, architecture, simplicity, stress) |
| Output | verify-report.md | judge-report.md |
| Scoring | Coverage % | Quality score (100 - blockers×20 - warnings×5 - nits×1) |
| Gate | auto-escalate | auto-escalate (same) |

**Note**: Adherence checking (spec vs code) is now handled by `speckit.analyze` (pre and post implementation). The Judge focuses on engineering quality.

## Redirect

When invoked, this skill redirects to `/madruga:judge` with the same arguments.

Execute `/madruga:judge` with the provided platform and epic arguments.
