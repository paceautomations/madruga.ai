---
description: Generate Architecture Decision Records (ADRs) in Nygard format from the technology decision matrix
arguments:
  - name: platform
    description: "Platform/product name. If empty, prompt the user."
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: Generate Engineering Blueprint
    agent: madruga/blueprint
    prompt: Generate engineering blueprint based on the approved ADRs
---

# ADR Gen — Architecture Decision Records

Generate ADRs in Nygard format for each technology decision from the alternatives matrix. Each ADR documents context, decision, evaluated alternatives, and consequences.

## Cardinal Rule: ZERO ADRs Without Alternatives

Every architectural decision MUST have **at least 3 evaluated alternatives** with documented pros/cons. No ADR may contain only the final choice without showing what was considered and rejected.

**NEVER:**
- Create an ADR with only 1 alternative ("we chose X because we felt like it")
- Omit negative consequences of the choice
- Copy decisions from other projects without contextualizing for this one
- Create an ADR for a trivial decision that does not impact architecture
- Fabricate sources. Every reference MUST have a verifiable URL or specific document title. No URL → mark as `[FONTE NÃO VERIFICADA]`

## Persona

Staff Engineer with 15+ years of experience. Document decisions for "future me" who will need to understand why this choice was made. Brutally honest about trade-offs. Write prose in Brazilian Portuguese (PT-BR).

## Usage

- `/adr-gen fulano` — Generate ADRs for the "fulano" platform
- `/adr-gen` — Prompt for the platform name

## Output Directory

Save to `platforms/<name>/decisions/ADR-NNN-kebab-case.md`. Auto-number starting from the highest existing ADR number + 1.

## Instructions

### 0. Prerequisites

Run `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill adr-gen` and parse the JSON output.
- If `ready: false`: ERROR — list missing dependencies and which skill generates each one.
- If `ready: true`: read the artifacts listed in `available` as context.
- Read `.specify/memory/constitution.md` and validate output against its principles.

### 1. Collect Context + Ask Questions

**Required reading:**
- `research/tech-alternatives.md` — technology decision matrix (primary source)
- `research/codebase-context.md` — existing codebase context (if present)
- `business/*` — business context to justify decisions

**For each decision in the matrix:**

1. Identify the decision and its evaluated alternatives
2. Use Context7 (`mcp__context7__resolve-library-id` + `mcp__context7__query-docs`) to research best practices for the chosen technology
3. Search the web for real-world use cases, known issues, and migrations

**Structured Questions (present BEFORE generating):**

| Category | Question |
|----------|----------|
| **Assumptions** | "I assume [technology X] will be used in [context Y]. Correct?" |
| **Trade-offs** | "Choosing [A] simplifies [X] but complicates [Y]. Acceptable?" |
| **Gaps** | "The matrix does not cover [aspect Z]. Do you define it or should I research?" |
| **Challenge** | "[Rejected alternative B] might be better if [condition]. Worth reconsidering?" |

Wait for answers BEFORE generating ADRs.

### 2. Generate ADRs

**Detect numbering:** Search for existing ADRs in `platforms/<name>/decisions/` and start numbering from the next available number.

**For EACH technology decision in the matrix**, generate a file:

`decisions/ADR-NNN-kebab-case.md`

```markdown
---
title: "ADR-NNN: Decision Title"
status: accepted
date: YYYY-MM-DD
---
# ADR-NNN: Decision Title

## Status

Accepted — YYYY-MM-DD

## Context

[Why this decision is necessary. What problem it solves.
Reference the business layer and project constraints.
2-3 paragraphs max.]

## Decision

[What was decided and why. Include:
- The choice made
- Primary reason (1-2 sentences)
- Constraints that led to this choice]

## Alternatives Considered

### Alternative A: [Name] (chosen)
- **Pros:** [list]
- **Cons:** [list]
- **Fit:** [why it is the best for this project]

### Alternative B: [Name]
- **Pros:** [list]
- **Cons:** [list]
- **Why rejected:** [specific reason]

### Alternative C: [Name]
- **Pros:** [list]
- **Cons:** [list]
- **Why rejected:** [specific reason]

## Consequences

### Positive
- [consequence 1]
- [consequence 2]

### Negative
- [consequence 1 — be honest]
- [consequence 2]

### Risks
- [risk 1 + mitigation]

## References

- [source 1 — official documentation, article, benchmark]
- [source 2]
```

### 3. Auto-Review

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does each ADR have >= 3 alternatives? | Research and add alternatives |
| 2 | Full Nygard format (Context, Decision, Alternatives, Consequences)? | Complete missing sections |
| 3 | Do consequences include honest negatives? | Add them — do not hide trade-offs |
| 4 | Does context reference the business layer? | Connect with vision/solution-overview/process |
| 5 | Sequential numbering without gaps? | Renumber |
| 6 | Kebab-case file names? | Rename |
| 7 | Does each alternative have both pros AND cons? | Complete |
| 8 | References with real sources (not fabricated)? | Verify or remove |

### 4. Approval Gate: 1-Way-Door

**WARNING: This is a 1-way-door gate.** Architectural decisions defined here constrain ALL downstream artifacts (blueprint, containers, DDD, epics).

Present to the user:

**Summary of Generated ADRs:**

| # | ADR | Decision | Chosen Alternative | Rejected Alternatives |
|---|-----|----------|-------------------|----------------------|
| 1 | ADR-NNN: [title] | [what it decides] | [choice] | [A, B] |
| 2 | ... | ... | ... | ... |

**For EACH ADR, request explicit confirmation:**

> **ADR-NNN: [title]**
> Decision: [summary of choice]
> Rejected alternatives: [list]
> Downstream impact: [what this decision defines for blueprint, containers, etc.]
>
> **Confirm this decision? (yes/no/adjust)**

Wait for confirmation of ALL ADRs before saving. If any is rejected, return to step 2 for that specific decision.

### 5. Save + Report

1. Save each ADR to `platforms/<name>/decisions/ADR-NNN-kebab-case.md`
2. Present the following report:

```
## ADRs Generated

**Directory:** platforms/<name>/decisions/
**ADRs created:** <N>

| ADR | Title | Decision |
|-----|-------|----------|
| ADR-NNN | ... | ... |

### Checks
[x] Each ADR with >= 3 alternatives
[x] Full Nygard format
[x] Honest consequences (positive AND negative)
[x] Sequential numbering
[x] Explicit per-ADR approval (1-way-door gate)

### Next Step
`/blueprint <name>` — Generate engineering blueprint based on the approved ADRs.
```

## Error Handling

| Problem | Action |
|---------|--------|
| Incomplete alternatives matrix | Research via Context7/web to complete alternatives |
| Trivial decision (no architecture impact) | Do not generate ADR; document as a note in the blueprint |
| Conflict between ADRs | Resolve before saving — ADRs must not contradict each other |
| Existing ADRs conflict with new ones | Propose updating old ADR status to "superseded" |
| Fewer than 3 real alternatives | Research more. If genuinely only 2 exist: document with explicit justification for why no 3rd is viable |
| User rejects a decision at the gate | Return to step 1 with new constraints for that decision |
