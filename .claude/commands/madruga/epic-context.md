---
description: Materialize an epic's pitch.md from its roadmap entry and capture implementation context (supports --draft mode)
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
  - name: epic
    description: "Epic number or full slug (e.g., 010 or 010-handoff-engine-inbox)."
    required: false
argument-hint: "[--draft] [platform] [epic-number]"
handoffs:
  - label: Start SpecKit Cycle
    agent: speckit.specify
    prompt: "Context captured and pitch.md materialized. Start implementation cycle with /speckit.specify."
---

# Epic Context — Create Pitch + Capture Implementation Context

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

First L2 node. Reads the epic's entry from `planning/roadmap.md`, materializes the full `pitch.md` (Layer 1: Problem/Appetite/Dependencies; Layer 2: Captured Decisions, Resolved Gray Areas, Applicable Constraints, Suggested Approach), registers the epic stub in the DB with the canonical title, and creates the epic branch.

**Draft mode** (`--draft`): Plan ahead on main without creating a branch — allows drafting multiple epics while another executes. When promoted later (normal mode), performs a delta review of what changed since the draft.

## Cardinal Rule: ZERO Decisions Without Architectural Context

Every implementation decision MUST reference the blueprint, ADRs, or domain model. No choices made in a vacuum. Every pitch MUST start from a roadmap entry — this skill does not invent epics.

## Persona

Staff Engineer. Bridge architecture and implementation. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/madruga:epic-context --draft prosauai 011` — Draft context on main (no branch, planning ahead)
- `/madruga:epic-context prosauai 010` — Activate epic (creates pitch.md from the roadmap entry + branch; if draft exists, delta review)
- `/madruga:epic-context` — Prompt for platform and epic

Epic argument accepts both the number (`010`) and the full slug (`010-handoff-engine-inbox`). The slug comes from the roadmap entry.

## Output Directory

Save to `platforms/<name>/epics/<NNN-slug>/pitch.md`.

## Instructions

### 0. Mode Detection + Branch Setup

Parse arguments for `--draft` flag.

**Path A: `--draft` mode**

```bash
current_branch=$(git branch --show-current)
if [ "$current_branch" != "main" ]; then
    echo "WARNING: Draft mode should run on main. Currently on $current_branch."
fi
```

- Do NOT create a branch — stay on main.
- Create the epic directory `platforms/<name>/epics/<NNN-slug>/` if needed.
- Set `$DRAFT_MODE=true` for downstream steps.

**Path B: Normal mode, draft exists**

Check if a draft exists:
1. Query DB: `SELECT status FROM epics WHERE platform_id=? AND epic_id=? AND status='drafted'`
2. Filesystem: `platforms/<name>/epics/<NNN-slug>/pitch.md` exists with Layer 2 sections (`## Captured Decisions`)

If both conditions met:
- Read existing pitch.md
- Proceed to **Step 0b (Delta Review)**
- After delta review, apply the same cascade checkout logic as Path C.

**Path C: Normal mode, no draft** (primary flow)

Resolve the epic from roadmap:

1. Read `platforms/<name>/planning/roadmap.md`.
2. Find the row in the Epic Table whose ID matches the argument (number or slug).
3. If no matching row → **ERROR**: `Epic '<NNN>' not found in planning/roadmap.md. Run /madruga:roadmap first to add the entry.`
4. Extract from the roadmap row: full slug (NNN-slug), title, problem (2 frases), appetite, deps, priority, milestone.

Branch setup:

**Important:** NEVER manually create the epic branch in the external repo. The `epic-context` skill handles this automatically via the cascade below. Manual creation causes a collision with the worktree that `easter` spawns. See `easter-tracking.md` for epic 004, incident at 2026-04-10 20:06.

```bash
BRANCH="epic/<platform>/<NNN-slug>"
BASE_BRANCH="<base_branch from platform.yaml>"

# Resume: branch already exists locally → just check it out
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git checkout "$BRANCH"
# Cascade: currently on another epic branch → new branch starts from its HEAD
elif git branch --show-current | grep -qE "^epic/"; then
    git checkout -b "$BRANCH"
# First epic or on base branch → branch from origin/base_branch
else
    git fetch origin "$BASE_BRANCH"
    git checkout -b "$BRANCH" "origin/$BASE_BRANCH"
fi
```

Branch naming: `epic/<platform>/<NNN-slug>`. Cascade is intentional — epics run sequentially; the previous epic's reconcile (Phase 11) will have already pushed before this runs.

**Always** create or checkout an epic branch before proceeding in normal mode.

### 0b. Delta Review (draft promotion only — Path B)

Read the existing `pitch.md` frontmatter `updated` date as `$DRAFT_DATE`.

Collect changes since draft:

```bash
# 1. Git changes in platform dir
git log --oneline --after=$DRAFT_DATE -- platforms/<platform>/

# 2. New/updated ADRs
git log --oneline --after=$DRAFT_DATE -- platforms/<platform>/decisions/ADR-*.md

# 3. Blueprint/domain changes
git log --oneline --after=$DRAFT_DATE -- platforms/<platform>/engineering/

# 4. Roadmap changes (problem, appetite, deps may have shifted)
git log --oneline --after=$DRAFT_DATE -- platforms/<platform>/planning/roadmap.md
```

```python
# 5. Epics shipped since draft
python3 -c "
import sys; sys.path.insert(0, '.specify/scripts')
from db import get_conn, get_epics
conn = get_conn()
epics = [e for e in get_epics(conn, '<platform>') if e['status'] == 'shipped' and (e.get('delivered_at') or '') > '$DRAFT_DATE']
for e in epics: print(f\"  - {e['epic_id']}: {e['title']}\")
conn.close()
"
```

Present **Delta Summary**:
- List each change category with items found
- For each original decision in pitch.md, flag if related changes exist
- Ask: "Quais decisões precisam revisão dado essas mudanças?"

Wait for user response. Revise affected decisions in pitch.md during Step 2.

### Additional required reading

- `planning/roadmap.md` — **canonical definition of the epic** (problem, appetite, deps, priority, milestone)
- `engineering/blueprint.md` — stack and cross-cutting concerns
- `engineering/domain-model.md` — bounded contexts, aggregates, invariants
- `engineering/containers.md` + `engineering/context-map.md` — topology and relationships
- `decisions/ADR-*.md` — relevant decisions
- If Path B: existing `epics/<NNN-slug>/pitch.md` (the draft with Layer 2 sections)

### 1. Collect Context + Ask Questions

By feature type in the epic:

| Type | Typical Gray Areas |
|------|--------------------|
| Visual/UI | Layout, responsive, design system, accessibility |
| API | Error codes, pagination, rate limiting, versioning |
| Data | Schema design, migration strategy, indexing, retention |
| Integration | Failure modes, retries, circuit breaker, timeouts |
| Infra | Deploy strategy, scaling, monitoring thresholds |

**Structured Questions** (categorias conforme `pipeline-contract-base.md` Step 1):

Toda pergunta DEVE apresentar **≥2 opções com prós/contras/riscos e recomendação**, independente da categoria.

**Micro-template** (aplicar em cada pergunta):

> **A)** [opção] — Prós: [benefício]. Contras: [custo]. Riscos: [risco].
> **B)** [opção] — Prós: [benefício]. Contras: [custo]. Riscos: [risco].
> **Recomendação:** [A ou B] porque [razão].

| Categoria | Padrão | Exemplo |
|-----------|--------|---------|
| **Premissas** | "Assumo [X] por causa de [ref]. Alternativas:" + opções | "Assumo ADR-003 (PostgreSQL). **A)** PostgreSQL — Prós: stack. Contras: nenhum. Riscos: baixo. **B)** SQLite dev + PG prod — divergência. **Rec:** A." |
| **Trade-offs** | "Para [área cinza]: [A] ou [B]?" + opções | "Paginação API: **A)** Offset — simples mas lento >10k. **B)** Cursor — performático. **Rec:** B." |
| **Gaps** | "Blueprint não especifica [X]. Opções:" + opções | "Sem retry definida. **A)** Backoff 3x. **B)** Fail-fast + DLQ. **Rec:** A + circuit breaker." |
| **Provocação** | "[Óbvio] pode não ser ideal porque [razão]. Alternativas:" + opções | "REST padrão, mas gRPC inter-container. **Rec:** B inter-serviço, A APIs públicas." |

Wait for answers BEFORE generating.

### 2. Generate / Enrich `pitch.md`

**pitch.md is the single canonical file per epic.** The output MUST be a cohesive document.

Three variants:

**(a) No pitch.md exists (primary flow — Path A/C first run)**

Generate the complete file from the roadmap entry + architectural context.

```markdown
---
id: NNN
title: "<Title from roadmap>"
slug: NNN-slug
appetite: "<X semanas>"
status: <drafted|in_progress>
priority: <P1|P2|P3>
depends_on: [NNN, NNN]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
# Epic NNN: <Title>

## Problem

<Expand the 2 sentences from roadmap into 1-2 paragraphs. Include user/business framing + current gap + why now.>

## Appetite

<X semanas — Shape Up cap, not estimate. Rationale from the roadmap + any architectural constraint discovered here.>

## Dependencies

- Depends on: NNN (if applicable)
- Blocks: NNN (if applicable)
- Assumes: <blueprint/ADR references>

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|----------|------------------------|
| 1 | [area] | [decision] | ADR-NNN / blueprint / domain-model |

## Resolved Gray Areas

[For each gray area: question, answer, rationale]

## Applicable Constraints

[From blueprint/ADRs that impact this epic]

## Suggested Approach

[Summary of the implementation approach — ordered steps or PRs]
```

Status: `in_progress` in Path C (normal — branch created), `drafted` in Path A.

**(b) pitch.md exists without Layer 2** (migration from older pitches or half-filled drafts)

1. READ the existing content completely.
2. **REVISE Layer 1 sections** (Problem, Appetite, Dependencies) — expand/correct using roadmap + architectural context learned during questioning.
3. **ADD Layer 2 sections** (Captured Decisions, Resolved Gray Areas, Applicable Constraints, Suggested Approach).
4. **Keep a single H1 heading** — do NOT add a second H1.
5. Do NOT use `---` horizontal rules as separators (breaks Starlight rendering).
6. Update `updated:` in frontmatter.
7. The result must read as ONE coherent document.

**(c) pitch.md exists with Layer 2** (re-run / delta promotion from draft)

Update in place. If Path B (draft promotion), merge delta review findings, marking revised decisions with `[REVISADO]`.

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Frontmatter has `title`, `appetite`, `status`, `priority`, `depends_on`? | Fill from roadmap |
| 2 | Problem expanded from 2 frases do roadmap para 1-2 parágrafos? | Expand |
| 3 | Every decision references architecture? | Connect it |
| 4 | Are gray areas resolved? | Resolve or mark as pending |
| 5 | Are blueprint constraints present? | Add them |
| 6 | Every decision has ≥2 documented alternatives? | Add |
| 7 | Trade-offs explicit (pros/cons)? | Add |
| 8 | Assumptions marked `[VALIDAR]` or backed by data? | Mark |

### 4. Gate

- **Draft mode (Path A)**: Auto gate — save immediately. Present summary but do not wait for approval. User reviews at promotion time.
- **Normal mode (Path B/C)**: Human gate — present captured decisions and resolved gray areas for validation.

### 5. Save + Report

**Step 5.1 — Seed the epic stub in the DB from the frontmatter** (before recording node completion):

```bash
python3 -c "
import sys, sqlite3
sys.path.insert(0, '.specify/scripts')
from db_pipeline import seed_epic_from_pitch

conn = sqlite3.connect('.pipeline/madruga.db')
conn.execute('PRAGMA foreign_keys = ON')
try:
    status = seed_epic_from_pitch(
        conn,
        '<platform>',
        '<NNN-slug>',
        'platforms/<platform>',
    )
    if status is None:
        raise SystemExit('pitch.md não encontrado — verifique o slug.')
    conn.commit()
    print(f'Seeded epic <NNN-slug> with status={status}')
finally:
    conn.close()
"
```

This guarantees the `epics` row has `title` populated from the frontmatter before any `post_save.py` call. The portal Kanban renders `title` from the snapshot — a missing title was the root cause of the epic 010 incident.

**Step 5.2 — Set branch_name** (normal mode only):

```bash
python3 -c "
import sys, sqlite3
sys.path.insert(0, '.specify/scripts')
from db_pipeline import upsert_epic

conn = sqlite3.connect('.pipeline/madruga.db')
upsert_epic(conn, '<platform>', '<NNN-slug>', branch_name='epic/<platform>/<NNN-slug>')
conn.commit()
conn.close()
"
```

Skip this step in Draft mode — drafted epics stay with `branch_name=NULL` until activation.

**Step 5.3 — Record node completion** via post_save:

```bash
# Draft mode: override status to drafted
python3 .specify/scripts/post_save.py --platform <name> --epic <NNN-slug> --node epic-context --skill madruga:epic-context --artifact epics/<NNN-slug>/pitch.md --epic-status drafted

# Normal mode: status computed automatically
python3 .specify/scripts/post_save.py --platform <name> --epic <NNN-slug> --node epic-context --skill madruga:epic-context --artifact epics/<NNN-slug>/pitch.md
```

**Step 5.4 — Decision Log**: create `platforms/<name>/epics/<NNN-slug>/decisions.md`:

1. Parse the "Captured Decisions" table from the just-generated pitch.md.
2. Create `decisions.md`:

```markdown
---
epic: <NNN-slug>
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
# Registro de Decisões — Epic <NNN>

1. `[YYYY-MM-DD epic-context]` <Decision text> (ref: <Architectural Reference>)
2. `[YYYY-MM-DD epic-context]` <Decision text> (ref: <Architectural Reference>)
```

3. One numbered entry per row from the Captured Decisions table.
4. If `decisions.md` already exists (re-run or delta review): append only NEW decisions not already present, incrementing numbering. Update `updated:` frontmatter.
5. Register the artifact:

```bash
python3 .specify/scripts/post_save.py --platform <name> --epic <NNN-slug> --node epic-context --skill madruga:epic-context --artifact epics/<NNN-slug>/decisions.md
```

## Error Handling

| Issue | Action |
|-------|--------|
| Epic not in `planning/roadmap.md` | ERROR — sugerir `/madruga:roadmap` para adicionar a entrada antes |
| Epic in roadmap, no pitch.md yet | **Fluxo normal** — variant (a): gerar pitch.md do zero com Layer 1 + Layer 2 |
| Epic has pitch.md without Layer 2 | Variant (b) — enriquecer preservando Layer 1 |
| Epic has pitch.md with Layer 2 | Variant (c) — delta review ou re-run in place |
| Architecture docs incomplete | Listar gaps, sugerir completar pipeline L1 antes |
| Too many gray areas (>10) | Priorizar as 5 mais críticas |
| Draft mode em branch não-main | Warn mas permitir (user pode ter razões) |
| Delta review sem changes | Skip revision, proceed com draft existente |
| Draft existe mas DB status não é `drafted` | Re-read pitch.md, tratar como Path C (fresh) |
