# Pipeline DAG Knowledge

Reference knowledge file for the madruga.ai pipeline DAG system.
Skills reference this file to understand node dependencies, gate types, personas, and the uniform contract.

---

## 1. Canonical DAG (14 nodes)

| ID | Skill | Outputs | Depends | Layer | Gate | Optional |
|----|-------|---------|---------|-------|------|----------|
| platform-new | madruga:platform-new | platform.yaml | — | business | human | no |
| vision | madruga:vision-one-pager | business/vision.md | platform-new | business | human | no |
| solution-overview | madruga:solution-overview | business/solution-overview.md | vision | business | human | no |
| business-process | madruga:business-process | business/process.md | solution-overview | business | human | no |
| tech-research | madruga:tech-research | research/tech-alternatives.md | business-process | research | 1-way-door | no |
| codebase-map | madruga:codebase-map | research/codebase-context.md | vision | research | auto | YES |
| adr-gen | madruga:adr-gen | decisions/ADR-*.md (output_pattern) | tech-research | engineering | 1-way-door | no |
| blueprint | madruga:blueprint | engineering/blueprint.md | adr-gen | engineering | human | no |
| folder-arch | madruga:folder-arch | engineering/folder-structure.md | blueprint | engineering | human | no |
| domain-model | madruga:domain-model | engineering/domain-model.md, model/ddd-contexts.likec4 | blueprint, business-process | engineering | human | no |
| containers | madruga:containers | engineering/containers.md, model/platform.likec4 | domain-model, blueprint | engineering | human | no |
| context-map | madruga:context-map | engineering/context-map.md | domain-model, containers | engineering | human | no |
| epic-breakdown | madruga:epic-breakdown | epics/*/pitch.md (output_pattern) | domain-model, containers, context-map | planning | 1-way-door | no |
| roadmap | madruga:roadmap | planning/roadmap.md | epic-breakdown | planning | human | no |

---

## 2. Skill Uniform Contract

Every skill MUST follow this 6-section structure:

```markdown
---
description: <1-line English description>
arguments:
  - name: platform
    description: "Platform name"
    required: false
argument-hint: "[platform-name]"
handoffs:
  - label: <next skill label>
    agent: madruga/<next>
    prompt: <context for handoff>
---

# <Name> — <Subtitle>

## Cardinal Rule
<What this skill NEVER does. Negative constraint.>

## Persona
<Who the AI simulates. Specific expertise.>

## Usage
- `/<skill-name> <platform>` — Direct mode
- `/<skill-name>` — Interactive mode

## Output Directory
Save to `platforms/<name>/<path>`.

## Instructions

### 0. Prerequisites
Run: `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill <id>`
If NOT ready: ERROR with missing deps and which skill generates each one.
If ready: read all artifacts listed in `available`.
Read `.specify/memory/constitution.md`.

### 1. Collect Context + Ask Questions
- Read dependency artifacts
- Identify implicit assumptions
- Deep research (subagents, Context7, web)
- Structured Questions:
  - **Assumptions**: "I assume X. Correct?"
  - **Trade-offs**: "A (simple) or B (robust)?"
  - **Gaps**: "Missing info about X. Do you define or should I research?"
  - **Challenge**: "Y is standard, but Z may be better because..."
- Present alternatives (>=2 options with pros/cons)
- Wait for answers BEFORE generating

### 2. Generate <Artifact>
- Follow template if one exists
- Include alternatives considered
- Mark [VALIDATE] where there is no supporting data
- PT-BR for prose, EN for code

### 3. Auto-Review
| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every decision have >=2 alternatives? | Add them |
| 2 | Is every assumption marked [VALIDATE] or backed by data? | Mark it |
| 3 | Were recent best practices researched? | Research |
| 4 | Are trade-offs explicit? | Add pros/cons |
| 5 | [Artifact-specific checks] | ... |

### 4. Approval Gate
If gate=human: Present summary + decisions + validation questions.
If gate=1-way-door: List EACH decision with >=3 alternatives, request EXPLICIT confirmation.
Wait for approval before saving.

### 5. Save + Report
File: platforms/<name>/<path>
Lines: <N>
Checks: [x] ...
Next step: /<next-skill> <name>
```

---

## 3. Gate Types

| Type | Behavior | When Pauses | Examples |
|------|----------|-------------|----------|
| human | Always pause for approval | Always | vision, blueprint, DDD |
| auto | Never pause, proceed automatically | Never | codebase-map, checkpoint |
| 1-way-door | Always pause, even in autonomous mode | Always, with per-decision confirmation | tech-research, adr-gen, epic-breakdown |
| auto-escalate | Auto if OK, escalate if blockers | Only when problems detected | verify |

### 1-way-door details

- List every irreversible decision
- For each: >=3 alternatives with pros/cons/recommendation
- Require explicit confirmation per decision
- "Confirm [decision X]? This defines [Y] for the rest of the project."

---

## 4. Personas by Layer

| Layer | Persona | Focus |
|-------|---------|-------|
| Business | Bain/McKinsey Strategist | Challenge assumptions, quantify, mark [VALIDATE] |
| Research | Senior Tech Research Analyst | Parallel deep research, >=3 alternatives per decision |
| Engineering | Staff Engineer 15+ years | Simplicity, "is this the simplest thing that works?" |
| Planning | Product Manager / Architect | Shape Up, scope definition, roadmap sequencing |

---

## 5. Structured Questions Framework

Every skill with gate: human presents questions in 4 categories:

1. **Assumptions** (what I'm assuming): "I assume [X]. Correct?"
2. **Trade-offs** (decisions with impact): "[A] simpler or [B] more robust?"
3. **Gaps** (missing info): "I didn't find [X]. Do you define or should I research?"
4. **Challenge** (challenge the obvious): "[Y] is standard, but [Z] may be better because [reason]."

---

## 6. Auto-Review Checklist Template

Every skill's auto-review MUST include these universal checks plus artifact-specific ones:

| # | Check | Applies to |
|---|-------|-----------|
| 1 | Every decision has >=2 alternatives documented | All |
| 2 | Every assumption marked [VALIDATE] or backed by data | All |
| 3 | Best practices researched (2025-2026) | Business + Engineering |
| 4 | Trade-offs explicit (pros/cons) | All |
| 5 | Zero technical terms in business artifacts | Business only |
| 6 | Mermaid/LikeC4 diagrams included where applicable | Engineering |
| 7 | Max line count respected | All |

---

## 7. Handoff Examples

```yaml
# vision -> solution-overview
handoffs:
  - label: Generate Solution Overview
    agent: madruga/solution-overview
    prompt: Generate solution overview based on validated vision

# solution-overview -> business-process
handoffs:
  - label: Map Business Process
    agent: madruga/business-process
    prompt: Map core business processes from validated solution overview

# business-process -> tech-research (with 1-way-door warning)
handoffs:
  - label: Research Tech Alternatives
    agent: madruga/tech-research
    prompt: "Research technology alternatives. WARNING: This is a 1-way-door gate — technology choices constrain all downstream architecture."

# tech-research -> adr-gen (with 1-way-door warning)
handoffs:
  - label: Generate ADRs
    agent: madruga/adr-gen
    prompt: "Generate Architecture Decision Records from validated tech research. WARNING: 1-way-door — ADRs define the technical foundation."

# adr-gen -> blueprint
handoffs:
  - label: Generate Blueprint
    agent: madruga/blueprint
    prompt: Generate engineering blueprint based on approved ADRs

# blueprint -> folder-arch
handoffs:
  - label: Define Folder Architecture
    agent: madruga/folder-arch
    prompt: Define folder structure based on approved blueprint

# domain-model -> containers
handoffs:
  - label: Define Containers
    agent: madruga/containers
    prompt: Define container architecture from domain model and blueprint

# context-map -> epic-breakdown (with 1-way-door warning)
handoffs:
  - label: Break into Epics (Shape Up)
    agent: madruga/epic-breakdown
    prompt: "Break project into epics. WARNING: This is a 1-way-door gate — epic scope decisions define everything downstream."

# epic-breakdown -> roadmap
handoffs:
  - label: Build Roadmap
    agent: madruga/roadmap
    prompt: Sequence epics into delivery roadmap based on dependencies and risk
```

---

## 8. Per-Epic Implementation Cycle

After the pipeline completes (roadmap done), each epic follows this cycle:

| Step | Skill | Gate | Purpose |
|------|-------|------|---------|
| 1 | discuss | human | Capture implementation context and decisions |
| 2 | speckit.specify | human | Feature specification |
| 3 | speckit.clarify | human | Reduce ambiguity in spec before planning |
| 4 | speckit.plan | human | Design artifacts |
| 5 | speckit.tasks | human | Task breakdown |
| 6 | speckit.analyze | auto | Pre-implementation consistency check (spec/plan/tasks) |
| 7 | speckit.implement | auto | Execute tasks |
| 8 | speckit.analyze | auto | Post-implementation consistency check |
| 9 | verify | auto-escalate | Check spec adherence |
| 10 | test-ai | human (optional) | QA test running app via Playwright |
| 11 | reconcile | human | Detect and fix documentation drift |

**test-ai is optional** — skip when:
- Epic has no web-facing features
- App is not running / Playwright MCP not available
- Epic is infrastructure or data-only

**test-ai heal loop** may modify code, which is why reconcile runs AFTER test-ai.
