---
description: Capture implementation context and decisions before the SpecKit cycle for an epic (supports --draft mode for planning ahead)
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
  - name: epic
    description: "Epic number (e.g., 001)."
    required: false
argument-hint: "[--draft] [platform] [epic-number]"
handoffs:
  - label: Start SpecKit Cycle
    agent: speckit.specify
    prompt: "Context captured. Start implementation cycle with /speckit.specify."
---

# Epic Context — Implementation Context

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

Capture implementation decisions and preferences before starting the SpecKit cycle for an epic. Identify gray areas and resolve ambiguities.

**Draft mode** (`--draft`): Plan ahead on main without creating a branch. Allows drafting multiple epics while another executes. When activated later (normal mode), performs a delta review of what changed since the draft.

## Cardinal Rule: ZERO Decisions Without Architectural Context

Every implementation decision MUST reference the blueprint, ADRs, or domain model. No choices made in a vacuum.

## Persona

Staff Engineer. Bridge architecture and implementation. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/epic-context --draft fulano 002` — Draft context on main (no branch, planning ahead)
- `/epic-context fulano 001` — Activate epic (if draft exists: delta review + branch; if not: full context + branch)
- `/epic-context` — Prompt for platform and epic

## Output Directory

Save to `platforms/<name>/epics/<NNN>/context.md`.

## Instructions

### 0. Mode Detection + Branch Setup

Parse arguments for `--draft` flag presence.

**Path A: `--draft` mode**

```bash
current_branch=$(git branch --show-current)
if [ "$current_branch" != "main" ]; then
    echo "WARNING: Draft mode should run on main. Currently on $current_branch."
fi
```

- Do NOT create a branch — stay on main.
- Create the epic directory `platforms/<name>/epics/<NNN>/` if needed.
- Set `$DRAFT_MODE=true` for downstream steps.

**Path B: Normal mode, draft exists**

Check if a draft exists:
1. Query DB: `SELECT status FROM epics WHERE platform_id=? AND epic_id=? AND status='drafted'`
2. Check filesystem: `platforms/<name>/epics/<NNN>/context.md` exists

If both conditions met:
- Read existing context.md
- Proceed to **Step 0b (Delta Review)**
- After delta review, create branch `epic/<platform>/<NNN-slug>` (or checkout if exists)

**Path C: Normal mode, no draft** (current behavior)

```bash
current_branch=$(git branch --show-current)
if [ "$current_branch" = "main" ]; then
    git checkout -b epic/<platform>/<NNN-slug>
fi
```

Branch naming: `epic/<platform>/<NNN-slug>` (e.g., `epic/fulano/001-channel-pipeline`).
If the branch already exists (resuming work), just checkout.

**Do NOT proceed with Path B or C if on main without creating/checking out a branch.**

### 0b. Delta Review (draft promotion only — Path B)

Read the existing `context.md` frontmatter `updated` date as `$DRAFT_DATE`.

Collect changes since draft:

```bash
# 1. Git changes in platform dir
git log --oneline --after=$DRAFT_DATE -- platforms/<platform>/

# 2. New/updated ADRs
git log --oneline --after=$DRAFT_DATE -- platforms/<platform>/decisions/ADR-*.md

# 3. Blueprint/domain changes
git log --oneline --after=$DRAFT_DATE -- platforms/<platform>/engineering/
```

```python
# 4. Epics shipped since draft
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
- For each original decision in context.md, flag if related changes exist
- Ask: "Quais decisoes precisam revisao dado essas mudancas?"

Wait for user response. Revise affected decisions in context.md during Step 2.

### Additional required reading:
- `epics/<NNN>/pitch.md` — epic scope
- `engineering/blueprint.md` — stack and concerns
- `engineering/domain-model.md` — DDD
- `decisions/ADR-*.md` — relevant decisions
- If Path B: existing `epics/<NNN>/context.md` (the draft)

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
| **Premissas** | "Assumo [X] por causa de [ref]. Alternativas:" + opções | "Assumo ADR-003 (PostgreSQL) para este epic. **A)** PostgreSQL — Prós: consistência com stack. Contras: nenhum. Riscos: baixo. **B)** SQLite local + PG prod — Prós: velocidade dev. Contras: divergência ambientes. Riscos: bugs só em prod. **Rec:** A." |
| **Trade-offs** | "Para [área cinza]: [A] ou [B]?" + opções | "Paginação da API: **A)** Offset — Prós: simples. Contras: lento >10k rows. Riscos: inconsistência com inserts. **B)** Cursor — Prós: performático. Contras: complexo no front. Riscos: baixo. **Rec:** B para >1k registros." |
| **Gaps** | "Blueprint não especifica [X]. Opções:" + opções | "Sem estratégia de retry definida. **A)** Backoff exponencial 3x — Prós: resiliente. Contras: latência. Riscos: sobrecarga downstream. **B)** Fail-fast + DLQ — Prós: resposta rápida. Contras: reprocessamento manual. Riscos: perda sem monitoramento. **Rec:** A + circuit breaker." |
| **Provocação** | "[Óbvio] pode não ser ideal porque [razão]. Alternativas:" + opções | "REST é padrão, mas gRPC pode ser melhor inter-container. **A)** REST — Prós: ecossistema maduro. Contras: overhead serialização. Riscos: baixo. **B)** gRPC — Prós: tipagem forte, streaming. Contras: tooling limitado. Riscos: curva aprendizado. **Rec:** B inter-serviço, A APIs públicas." |

Wait for answers BEFORE generating.

### 2. Generate Context

```markdown
---
title: "Implementation Context — Epic <N>"
updated: YYYY-MM-DD
---
# Epic <N> — Implementation Context

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|---------|----------------------|
| 1 | [area] | [decision] | ADR-NNN / blueprint / domain-model |

## Resolved Gray Areas

[For each gray area: question, answer, rationale]

## Applicable Constraints

[From blueprint/ADRs that impact this epic]

## Suggested Approach

[Summary of the implementation approach]
```

If Path B (draft promotion): merge delta review findings into the existing context, marking revised decisions with `[REVISADO]`.

### Auto-Review Additions

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Does every decision reference architecture? | Connect it |
| 2 | Are gray areas resolved? | Resolve or mark as pending |
| 3 | Are blueprint constraints present? | Add them |
| 4 | Does every decision have >=2 documented alternatives? | Add |
| 5 | Are trade-offs explicit (pros/cons)? | Add pros/cons |
| 6 | Are assumptions marked [VALIDAR] or backed by data? | Mark [VALIDAR] |

### 4. Gate

- **Draft mode (Path A)**: Auto gate — save immediately. Present summary but do not wait for approval. The user will review at promotion time.
- **Normal mode (Path B/C)**: Human gate — present captured decisions and resolved gray areas for validation.

### 5. Save + Report

**Draft mode**: Register with `drafted` status:
```bash
python3 .specify/scripts/post_save.py --platform <name> --epic <epic-id> --node epic-context --skill madruga:epic-context --artifact epics/<NNN>/context.md --epic-status drafted
```

**Normal mode**: Register normally (status computed automatically):
```bash
python3 .specify/scripts/post_save.py --platform <name> --epic <epic-id> --node epic-context --skill madruga:epic-context --artifact epics/<NNN>/context.md
```

## Error Handling

| Issue | Action |
|-------|--------|
| Epic does not exist (no pitch.md) | Suggest running `/epic-breakdown` first |
| Architecture docs incomplete | List gaps, suggest completing the pipeline |
| Too many gray areas (>10) | Prioritize the 5 most critical |
| Draft mode on non-main branch | Warn but allow (user may have reasons) |
| Delta review finds zero changes | Skip revision, proceed with existing draft as-is |
| Draft exists but DB status is not `drafted` | Re-read context.md, treat as Path C (fresh) |
