# Pipeline Contract — Base

Universal contract for all pipeline skills. Every DAG skill follows this structure.
Skills reference this file and add artifact-specific steps 1 (context) and 2 (generate).

---

## Step 0: Prerequisites

### Branch Guard (epic cycle skills ONLY)

For any epic cycle skill (epic-context, specify, clarify, plan, tasks, analyze, implement, analyze-post, verify, qa, reconcile):

```bash
current_branch=$(git branch --show-current)
```

- If `current_branch` is `main` → **ERROR**: "Epic work MUST happen on a feature branch. Run `/epic-context <platform> <epic>` first to create branch `epic/<platform>/<NNN-slug>`."
- If `current_branch` starts with `epic/` → OK, proceed.
- Exception: `epic-context` itself creates the branch (see epic-context.md Step 0).

**This is a hard stop. Do NOT proceed with any epic cycle work on main.**

### Dependency Check

Run the prerequisites check from the repo root:

```
.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <name> --skill <skill-id>
```

Parse the JSON output:
- If `ready: false` → ERROR. List missing dependencies and which skill generates each one.
- If `ready: true` → read all artifacts listed in `available`.

Then read `.specify/memory/constitution.md`.

For epic cycle skills, add `--epic <NNN>` to check epic-level prerequisites.

---

## Step 1: Collect Context + Ask Questions

Read dependency artifacts. Identify implicit assumptions. Use deep research (subagents, Context7, web) where needed.

Present **Structured Questions** in 4 categories before generating:

| Category | Pattern |
|----------|---------|
| **Premissas** | "Assumo que [X]. Correto?" |
| **Trade-offs** | "[A] mais simples ou [B] mais robusto?" |
| **Gaps** | "Não encontrei info sobre [X]. Você define ou devo pesquisar?" |
| **Provocação** | "[Y] é o padrão, mas [Z] pode ser melhor porque [motivo]." |

Present alternatives (≥2 options with pros/cons for every decision).

**Wait for answers BEFORE generating.** Never generate based on assumptions alone.

---

## Step 3: Auto-Review

Auto-review is **tiered by gate type**. The skill's gate determines which tier applies.

### Tier 1 — Auto Gates

Deterministic, executable checks only. No LLM judgment.

| # | Check | How |
|---|-------|-----|
| 1 | Output file exists and is non-empty | `test -s <file>` |
| 2 | Line count within bounds | `wc -l` against expected range |
| 3 | Required sections present | `grep` for mandatory headings |
| 4 | No placeholder markers remain | `grep -c 'TODO\|TKTK\|???\|PLACEHOLDER'` = 0 |
| 5 | HANDOFF block present at footer | `grep 'handoff:'` at end of file |

### Tier 2 — Human Gates

Tier 1 checks + **scorecard** presented to the human reviewer.

| # | Scorecard Item | Self-Assessment |
|---|---------------|-----------------|
| 1 | Every decision has ≥2 documented alternatives | Yes/No |
| 2 | Every assumption marked [VALIDAR] or backed by data | Yes/No |
| 3 | Trade-offs explicit (pros/cons) | Yes/No |
| 4 | Best practices researched (current year) | Yes/No |
| 5 | [Artifact-specific checks] | Yes/No |

Present scorecard to user with honest self-assessment. Flag weak spots.

### Tier 3 — 1-Way-Door Gates

Tier 1 + Tier 2 + **subagent adversarial review**.

After completing Tier 2, launch a subagent (Agent tool, subagent_type="general-purpose") with:
- The complete artifact text
- Prompt: "You are a staff engineer reviewing this artifact for a 1-way-door decision. Be harsh and direct. Check for: missed alternatives, unsupported claims, hidden assumptions, scope creep, simpler approaches. Output a bullet list of issues (BLOCKER/WARNING/NIT) and an overall verdict."

Incorporate feedback: fix blockers, note warnings in the scorecard.

---

## Step 4: Approval Gate

| Gate Type | Behavior |
|-----------|----------|
| auto | Save immediately. No pause. |
| human | Present summary + decisions + scorecard. Wait for approval. |
| 1-way-door | List EACH irreversible decision. ≥3 alternatives per decision. Request EXPLICIT confirmation per decision. |
| auto-escalate | Auto if OK (no blockers). Escalate to human if blockers found. |

---

## Step 5: Save + Report

### Save the artifact

Write to `platforms/<name>/<path>` (or `platforms/<name>/epics/<NNN>/<path>` for epic cycle).

### SQLite Integration

After saving the artifact, run the post-save script to record state in the DB.

**For L1 (platform DAG) skills:**
```bash
python3 .specify/scripts/post_save.py --platform <name> --node <node-id> --skill <skill-id> --artifact <relative-path>
```

**For L2 (epic cycle) skills:**
```bash
python3 .specify/scripts/post_save.py --platform <name> --epic <epic-id> --node <node-id> --skill <skill-id> --artifact <relative-path>
```

Example:
```bash
# After /vision saves business/vision.md:
python3 .specify/scripts/post_save.py --platform fulano --node vision --skill madruga:vision --artifact business/vision.md

# After /speckit.specify saves spec.md in an epic:
python3 .specify/scripts/post_save.py --platform fulano --epic 001-channel-pipeline --node specify --skill speckit.specify --artifact epics/001-channel-pipeline/spec.md
```

If the script fails or the DB does not exist, proceed normally — the DB is additive, not blocking.

### Report Format

```
## <Skill Name> complete

**File:** platforms/<name>/<path>
**Lines:** <N>

### Auto-Review
[Tier results — PASS/FAIL per check]

### Next step
`/<next-skill> <name>` — <brief context from HANDOFF>
```

### HANDOFF Block

Append at the end of the artifact:

```yaml
---
handoff:
  from: <this-skill>
  to: <next-skill>
  context: "<1-2 sentences of context for the next skill>"
  blockers: []
```

---

## Language

- Artifact prose: **PT-BR** (Brazilian Portuguese)
- Code, YAML, config: **EN** (English)
- Knowledge files (this file): **EN**
