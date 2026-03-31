# Pipeline DAG Knowledge

Reference knowledge file for the madruga.ai pipeline — a **single continuous flow of 24 skills** (L1: 13 platform nodes + L2: 11 per-epic nodes) that takes a platform from conception to implemented, tested code.

Skills reference this file to understand node dependencies, gate types, personas, and the uniform contract.

---

## 1. L1 — Platform Foundation (13 nodes, runs once per platform)

| ID | Skill | Outputs | Depends | Layer | Gate | Optional |
|----|-------|---------|---------|-------|------|----------|
| platform-new | madruga:platform-new | platform.yaml | — | business | human | no |
| vision | madruga:vision | business/vision.md | platform-new | business | human | no |
| solution-overview | madruga:solution-overview | business/solution-overview.md | vision | business | human | no |
| business-process | madruga:business-process | business/process.md | solution-overview | business | human | no |
| tech-research | madruga:tech-research | research/tech-alternatives.md | business-process | research | 1-way-door | no |
| codebase-map | madruga:codebase-map | research/codebase-context.md | vision | research | auto | YES |
| adr | madruga:adr | decisions/ADR-*.md (output_pattern) | tech-research | engineering | 1-way-door | no |
| blueprint | madruga:blueprint | engineering/blueprint.md | adr | engineering | human | no |
| domain-model | madruga:domain-model | engineering/domain-model.md, model/ddd-contexts.likec4 | blueprint, business-process | engineering | human | no |
| containers | madruga:containers | model/platform.likec4, model/views.likec4 | domain-model, blueprint | engineering | human | no |
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
- `/madruga:<skill-name> <platform>` (or `/speckit.<skill-name>` for SpecKit nodes) — Direct mode
- `/madruga:<skill-name>` (or `/speckit.<skill-name>`) — Interactive mode

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
- Mark [VALIDAR] where there is no supporting data
- PT-BR for prose, EN for code

### 3. Auto-Review
| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every decision have >=2 alternatives? | Add them |
| 2 | Is every assumption marked [VALIDAR] or backed by data? | Mark it |
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
Next step: /madruga:<next-skill> <name> (or /speckit.<next-skill> <name> for SpecKit nodes)

#### SQLite Integration
After saving, run:
```bash
python3 .specify/scripts/post_save.py --platform <name> --node <node-id> --skill <skill-id> --artifact <relative-path>
# For epic cycle, add: --epic <epic-id>
```
If the script fails, proceed normally (DB is additive, not blocking).
```

---

## 3. Gate Types

| Type | Behavior | When Pauses | Examples |
|------|----------|-------------|----------|
| human | Always pause for approval | Always | vision, blueprint, DDD |
| auto | Never pause, proceed automatically | Never | codebase-map, checkpoint |
| 1-way-door | Always pause, even in autonomous mode | Always, with per-decision confirmation | tech-research, adr, epic-breakdown |
| auto-escalate | Auto if OK, escalate if blockers | Only when problems detected | verify |

### 1-way-door details

- List every irreversible decision
- For each: >=3 alternatives with pros/cons/recommendation
- Require explicit confirmation per decision
- "Confirm [decision X]? This defines [Y] for the rest of the project."

---

## 4. Personas by Layer

| Layer | Behavioral Directive | Contract File |
|-------|---------------------|---------------|
| Business | "Your instinct is to REDUCE scope. Ask 'is this essential for v1?' before adding. Quantify everything — no vague adjectives without numbers. Mark `[VALIDAR]` when no evidence exists." | `pipeline-contract-business.md` |
| Research | "Your default is `[DADOS INSUFICIENTES]`. Only assert with a verifiable source. Every factual claim must have a URL or reference. No URL → `[FONTE?]`." | (base only) |
| Engineering | "Your first question is always: 'Is this the simplest thing that works?' Default to fewer components, fewer abstractions, fewer moving parts. Prefer stdlib over library, single process over distributed." | `pipeline-contract-engineering.md` |
| Planning | "Your instinct is to CUT scope. Default appetite is 2 weeks. If an epic needs more, it should be split. Sequence by risk: uncertain epics first, mechanical epics later." | `pipeline-contract-planning.md` |

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
| 2 | Every assumption marked [VALIDAR] or backed by data | All |
| 3 | Best practices researched (2025-2026) | Business + Engineering |
| 4 | Trade-offs explicit (pros/cons) | All |
| 5 | Zero technical terms in business artifacts | Business only |
| 6 | Mermaid/LikeC4 diagrams included where applicable | Engineering |
| 7 | Max line count respected | All |
| 8 | Verifiable sources? Every factual claim has URL or reference. No URL → [FONTE?] | Research + Engineering |

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

# tech-research -> adr (with 1-way-door warning)
handoffs:
  - label: Generate ADRs
    agent: madruga/adr
    prompt: "Generate Architecture Decision Records from validated tech research. WARNING: 1-way-door — ADRs define the technical foundation."

# adr -> blueprint
handoffs:
  - label: Generate Blueprint
    agent: madruga/blueprint
    prompt: Generate engineering blueprint based on approved ADRs (includes folder structure)

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

## 8. L2 — Epic Implementation Cycle (11 nodes per epic)

After L1 completes (roadmap done), the pipeline continues into L2. Each epic from the roadmap follows this cycle on a dedicated branch:

### Branch Requirement (MANDATORY)

**Every epic MUST run on a dedicated branch.** NEVER commit epic work directly to main.

- **Branch naming**: `epic/<platform>/<NNN-slug>` (e.g., `epic/fulano/001-channel-pipeline`)
- **Created by**: `epic-context` (Step 1) — the first skill in the cycle creates the branch
- **Merged by**: User after reconcile completes — via PR or manual merge
- **Guard**: All epic cycle skills check `git branch --show-current` and STOP if on main (see pipeline-contract-base.md Step 0)

### Cycle Steps

| Step | Skill | Gate | Purpose |
|------|-------|------|---------|
| 1 | madruga:epic-context | human | **Create branch** + capture implementation context |
| 2 | speckit.specify | human | Feature specification |
| 3 | speckit.clarify | human | Reduce ambiguity in spec before planning |
| 4 | speckit.plan | human | Design artifacts |
| 5 | speckit.tasks | human | Task breakdown |
| 6 | speckit.analyze | auto | Pre-implementation consistency check (spec/plan/tasks) |
| 7 | speckit.implement | auto | Execute tasks |
| 8 | speckit.analyze | auto | Post-implementation consistency check |
| 9 | madruga:verify | auto-escalate | Check spec adherence |
| 10 | madruga:qa | human | Comprehensive testing — static analysis, tests, code review, browser QA |
| 11 | madruga:reconcile | human | Detect and fix documentation drift |

**Note:** `clarify` is optional — `plan` depends on `specify`, not `clarify`. Skip clarify when spec has 0 `[NEEDS CLARIFICATION]` markers.

**qa is mandatory** — always runs. Testing layers auto-adapt:
- Static analysis + code review + build verification: always available
- Automated test suites: when test files exist
- API testing: when server is running + API endpoints detected
- Browser testing: when Playwright MCP available + web features + app running

**qa heal loop** may modify code, which is why reconcile runs AFTER qa.
