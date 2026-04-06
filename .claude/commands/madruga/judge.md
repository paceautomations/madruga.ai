---
description: Run tech-reviewers Judge (4 personas + judge pass) against implemented code
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
  - name: epic
    description: "Epic number (e.g., 001)."
    required: false
argument-hint: "[platform] [epic-number]"
handoffs:
  - label: QA Testing
    agent: madruga/qa
    prompt: "Judge complete. Run comprehensive QA testing."
---

# Judge — Tech Reviewers + Quality Assessment

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

Run 4 specialized reviewers in parallel against implemented code, filter findings through a Judge pass, produce a consolidated quality report with score.

**Replaces**: `/madruga:verify` (deprecated). Judge = **engineering quality** (will it work well?). Analyze = **adherence** (does it match spec/tasks?).

## Cardinal Rule: ZERO Invented Findings

The Judge does NOT create new findings. It only filters and reclassifies findings from the 4 personas. Every finding MUST have evidence in the actual code.

## Persona

Staff Engineer + QA Lead. Skeptical, evidence-based. Write generated artifacts in Brazilian Portuguese (PT-BR).

## Usage

- `/judge fulano 001` — Judge epic 001 of platform "fulano"
- `/judge` — Prompt for the platform and epic

## Output

Save to `platforms/<name>/epics/<NNN>/judge-report.md`.

---

## Instructions

### 0. Prerequisites

Follow Step 0 from `pipeline-contract-base.md` (branch guard + dependency check). Confirm spec.md and tasks.md exist.

### 1. Collect Context + Validate Config

- Read spec.md, tasks.md, plan.md for the epic
- Scan implemented code via git diff or filesystem
- Read `.specify/memory/constitution.md` — project constitution

**Validate judge-config.yaml**:
1. Read `.claude/knowledge/judge-config.yaml`.
2. Verify structure: `review_teams` must exist with at least one team.
3. Each team must have: `name` (string), `personas` (non-empty list), `runs_at` (list).
4. Each persona must have: `id` (string), `role` (string), `prompt` (string path).
5. For each persona, verify the prompt file exists at the configured path.
6. If any validation fails → **FAIL** with clear error listing what's missing.

Select the team to run (default: `engineering`).

### 2. Launch Personas in Parallel

Launch **4 Agent tool calls in a single message** (subagent_type="general-purpose"). Each receives:

```
"You are reviewing the following artifact/code as a {persona.role}.

=== ARTIFACT ===
{full artifact or code text}
=== END ARTIFACT ===

=== CONSTITUTION ===
{contents of .specify/memory/constitution.md}
=== END CONSTITUTION ===

=== CONTEXT ===
{spec.md summary, tasks.md summary, architecture references}
=== END CONTEXT ===

=== PERSONA INSTRUCTIONS ===
{contents of persona prompt file}
=== END PERSONA INSTRUCTIONS ===

Follow the output format in the persona instructions EXACTLY. Do not deviate."
```

### 3. Aggregate Findings

For each persona result:
1. Check for `PERSONA:` header and `FINDINGS:` section.
2. If format invalid → mark persona as **failed** (see §6).
3. Parse each `- [SEVERITY] description | LOCATION: ... | SUGGESTION: ...` line.
4. Build aggregated findings list.

### 4. Judge Pass — Filter and Reclassify

For each finding, evaluate:

| Criterion | Question | Action if fails |
|-----------|----------|-----------------|
| **Accuracy** | Cites real evidence? Problem actually exists? | **Discard** (hallucination) |
| **Actionability** | Concrete fix suggestion? | **Discard** (noise) |
| **Severity** | Impact justifies classification? | **Reclassify** (e.g., NIT→BLOCKER gets rebaixado) |

**Consensus rules:**
- All personas agree on BLOCKER → confirmed.
- Only 1 persona raises BLOCKER, others don't mention → evaluate evidence. Weak → rebaixa para WARNING.
- Duplicate findings across personas → keep best-described, discard rest.

### 5. Generate Score and Report

**Score**: `100 - (blockers×20 + warnings×5 + nits×1)`, min 0.
**Verdict**: score ≥80 = PASS, <80 = FAIL.

Generate `judge-report.md`:

```markdown
---
title: "Judge Report — {context}"
score: {N}
initial_score: {N_before_fixes}
verdict: pass|fail
team: {team-name}
personas_run: [{ids}]
personas_failed: [{ids}]
findings_total: {N}
findings_fixed: {N}
findings_open: {N}
updated: {YYYY-MM-DD}
---
# Judge Report — {context}

## Score: {N}%

**Verdict:** {PASS|FAIL}
**Team:** {team-name} ({N} personas)

## Findings

### BLOCKERs ({count} — {fixed}/{count} fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|

### WARNINGs ({count} — {fixed}/{count} fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|

### NITs ({count} — {fixed}/{count} fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|

## Personas que Falharam

[List if any, otherwise "Nenhuma"]

## Files Changed (by fix phase)

| File | Findings Fixed | Summary |
|------|---------------|---------|

## Recomendações

[Actionable recommendations for any OPEN findings]
```

### 6. Degradation Rules

| Personas OK | Behavior |
|-------------|----------|
| 4/4 | Normal — score on all findings |
| 3/4 | Partial — score on available. Report `personas_failed` + WARNING |
| 2/4 | Partial — escalated WARNING: "review significativamente incompleto" |
| ≤1/4 | **FAIL** — escalate to human regardless of score |

**Failure detection**: Agent error, missing `PERSONA:` header, missing `FINDINGS:` section.

### 7. Fix Phase — Resolve ALL Findings

After the Judge Pass (section 4), fix **every** finding from both sources:
- Findings from `analyze-post-report.md` (received as upstream context)
- Findings from the 4 personas (filtered by the judge pass)

**The judge MUST resolve 100% of issues. No finding should be left OPEN if a fix is possible.**

#### 7a. Ingest Analyze-Post Findings

1. Parse `analyze-post-report.md` from the upstream context injection.
2. Extract each finding (adherence gaps, spec mismatches, missing implementations).
3. Add them to the consolidated findings list alongside persona findings.
4. Deduplicate: if a persona already flagged the same issue, keep the best-described version.

#### 7b. Fix Priority Order

Fix in this order: BLOCKERs first, then WARNINGs, then NITs.

**For each BLOCKER and WARNING:**

| Source | Finding Type | Action |
|--------|-------------|--------|
| Analyze-post | Missing implementation | Implement the missing code per spec |
| Analyze-post | Spec mismatch | Fix code to match spec |
| Analyze-post | Task not completed | Complete the task |
| Persona | Security issue | Fix with proper validation/escaping |
| Persona | Bug / logic error | Fix the code |
| Persona | Missing error handling | Add error handling at boundaries |
| Persona | Wrong API usage | Fix to correct usage |

**For each NIT:**
- If trivial (< 5 lines changed): apply fix
- If non-trivial: keep as suggestion in report, mark `[SKIPPED — NIT]`

#### 7c. Re-Verify After Fixes

1. Run lint on changed files: `ruff check` (Python), `npx tsc --noEmit` (TypeScript), or equivalent.
2. Run tests if they exist: `make test` or project-specific test command.
3. If a fix introduces a new failure → revert that fix, mark finding as `[OPEN — fix caused regression]`.

#### 7d. Re-Score

Recalculate score AFTER fixes:
- `[FIXED]` findings do NOT count against score.
- `[OPEN]` findings count normally (blockers×20, warnings×5, nits×1).
- `[SKIPPED — NIT]` findings count as nits (×1).

The report verdict reflects the **post-fix state**, not the initial state.

### 8. Safety Net — Escaped 1-Way-Door Decisions (L2 only)

After running the personas review, scan for decisions made during the epic cycle that may have escaped the inline Decision Classifier:

1. Read `git diff main...HEAD` to identify all changes in the epic branch.
2. Query the `events` table for decision entries in the current epic.
3. For each decision found in the diff or events:
   a. Run the description through the Decision Classifier patterns (from `decision-classifier-knowledge.md`).
   b. If score ≥ 15 AND the decision was NOT previously approved (no `decision_resolved` event with `verdict: approved`):
      - Add as **BLOCKER** in the judge-report.md under "Safety Net — Decisões 1-Way-Door".
      - Include: which decision, why it's 1-way-door, recommendation to revert or get approval.
4. If no escaped decisions found, the safety net section shows "Nenhuma decisão 1-way-door escapou."

This catches decisions that the inline classifier missed or that were made without going through the classification flow.

### 9. Gate: Auto-Escalate

- Score ≥80 AND 0 blockers → **AUTO** — save report, proceed.
- Score <80 OR blockers → **ESCALATE** — present report to user.
- ≤1/4 personas → **FAIL** — always escalate.

## Error Handling

| Problem | Action |
|---------|--------|
| No spec.md | Suggest `/speckit.specify` |
| No tasks.md | Suggest `/speckit.tasks` |
| No code implemented | Score 0%, escalate |
| Persona prompt file missing | FAIL with clear error |
| ≤1/4 personas completed | FAIL + escalate to human |
