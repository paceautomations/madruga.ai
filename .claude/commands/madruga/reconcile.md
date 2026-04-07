---
description: Detect drift between implementation and documentation, update roadmap, manage ADRs, and flag future epic impact
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
  - name: epic
    description: "Epic number (e.g., 001)."
    required: false
argument-hint: "[platform] [epic-number]"
handoffs:
  - label: Check Pipeline Status
    agent: madruga/pipeline
    prompt: "Reconcile complete. Check pipeline status — epic cycle may be done."
---

# Reconcile — Documentation Guardian

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

Compare implementation (git diff / PR) against ALL platform documentation. Detect drift across 10 categories (D1-D10), compute a drift score, propose concrete updates, review the roadmap, manage ADR contradictions, flag impact on future epics, and update the README if needed.

## Cardinal Rule: ZERO Silent Drift

Every deviation between implementation and documentation must be made explicit. No architecture change can exist without a corresponding doc update.

**NEVER:**
- Propose changes without showing current state vs expected state side-by-side
- Apply any changes before the human gate approval — this skill PROPOSES, the user APPLIES
- Skip the roadmap review — it is mandatory after every epic
- Mark an ADR as superseded without explicit user confirmation
- Generate vague proposals like "update this doc" — always provide concrete diffs

## Persona

Architect / Documentation Guardian. Skeptical, systematic. You do not trust that docs are current — you verify every claim against the code. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/reconcile prosauai 001` — Reconcile after epic 001 of platform "prosauai"
- `/reconcile prosauai` — Prompt for epic number
- `/reconcile` — Prompt for platform and epic

## Output Directory

Save to `platforms/<name>/epics/<NNN>/reconcile-report.md`.

---

## Instructions

### Phase 1. Collect Context (Progressive Disclosure)

**Step 1 — Read the diff first** to understand what changed:
```bash
git diff main...HEAD --stat
git log main..HEAD --oneline
git diff main...HEAD --name-only
```

**Step 2 — Read only docs relevant to the changed areas.** Use this mapping:

| If diff touches... | Read these docs |
|---------------------|----------------|
| Business logic, features, scope | `business/solution-overview.md`, `business/process.md` |
| Architecture, infra, deploy, new services | `engineering/blueprint.md`, `engineering/containers.md` |
| Domain entities, aggregates, events | `engineering/domain-model.md` |
| APIs, contracts, integrations | `engineering/context-map.md` |
| Technology choices, patterns | `decisions/ADR-*.md` |
| Always (mandatory) | `planning/roadmap.md`, `epics/<NNN>/verify-report.md`, `epics/<NNN>/qa-report.md`, `epics/<NNN>/decisions.md` |

**Step 3 — Read future epic pitches** only if the diff changed APIs, schemas, or bounded context boundaries:
- `epics/*/pitch.md` (up to 15 future epics, prioritize by roadmap proximity)

**Step 4 — Check for README:** If `platforms/<name>/README.md` exists, include it in drift detection scope.

**Deduplication with verify:** Read `verify-report.md` to identify findings already reported. Do NOT re-report architecture drift items that verify already flagged — cross-reference them instead.

**Structured Questions:**

| Category | Question |
|----------|----------|
| **Premissas** | "Assumo que a mudanca em [X] foi intencional e reflete o design correto. Confirma?" |
| **Trade-offs** | "Atualizar todos os docs agora (completo) ou marcar para proximo sprint (rapido)?" |
| **Gaps** | "Nao tenho certeza se a mudanca em [X] afeta [doc Y]. Verificar?" |
| **Provocacao** | "O drift em [area] pode indicar que o ADR-NNN original precisa revisao." |

Wait for answers BEFORE generating the report or proposing updates.

---

### Phase 2. Detect Drift (10 Categories)

Scan each category systematically. For each drift item found, record: ID, category, affected doc, current state in doc, actual state in code, severity (high/medium/low).

| ID | Category | Source of Truth | Compare Against | How to Detect | Example |
|----|----------|----------------|-----------------|---------------|---------|
| D1 | Scope | `business/solution-overview.md` features | Implemented code | Feature in code but not in doc, or listed but not implemented | New `/v2/orders` endpoint not in solution-overview |
| D2 | Architecture | `engineering/blueprint.md` topology + NFRs | Code structure, dependencies | New service not in blueprint; different tech used | Blueprint says SQLite but code added Redis |
| D3 | Model | `engineering/containers.md` diagrams | Actual containers/relationships | Mermaid diagrams missing new containers or stale relationships | New `worker` container not in containers.md |
| D4 | Domain | `engineering/domain-model.md` | Code entities, aggregates, events | New entity/aggregate not in domain model | New `OrderItem` entity undocumented |
| D5 | Decision | `decisions/ADR-*.md` (Accepted) | Implementation patterns | Code contradicts an accepted ADR | ADR chose REST but code uses GraphQL |
| D6 | Roadmap | `planning/roadmap.md` | Actual epic outcome | Appetite over/under; milestone status; risk materialized | 2w appetite took 4w |
| D7 | Epic (future) | `epics/*/pitch.md` (unimplemented) | Changes from current epic | Current epic changed APIs/schema/boundaries assumed by future pitches | Future epic assumes `/v1/channels` but it was renamed |
| D8 | Integration | `engineering/context-map.md` | Actual API contracts, events | Published API changed; new integration not in context map | New webhook not documented |
| D9 | README | `platforms/<name>/README.md` | Current implementation state | Setup instructions outdated; new dependencies not listed; architecture section stale | README lists old env vars; missing new service |
| D10 | Epic Decisions | `epics/<NNN>/decisions.md` | `decisions/ADR-*.md` + code | Decision in log contradicts ADR; significant decision not promoted to ADR; decision no longer reflected in code | decisions.md says "used polling" but ADR-005 mandates websockets |

#### D5 — Decision Drift: Action on Detection

Propose one of:
- **Amend**: ADR decision is still valid but needs an exception clause
- **Supersede**: ADR decision is no longer valid — draft header for new ADR (title, status: Proposed, supersedes: ADR-NNN). Do NOT generate the full ADR — that is the `adr` skill's job.

#### D10 — Epic Decision Drift: Action on Detection

If `decisions.md` does not exist for this epic, skip D10 silently.

For each entry in `decisions.md`, run 3 checks:

1. **Contradiction**: Does this decision contradict any accepted ADR? If yes, flag with severity HIGH and propose amend/supersede (same flow as D5).
2. **Promotion**: Is this decision significant enough to become a platform-level ADR? Heuristic: the decision (a) affects more than one epic, (b) constrains future architectural choices, or (c) is a 1-way-door pattern. If yes, flag and propose running `/madruga:adr` with the decision as input. Do NOT generate the ADR — that is the `adr` skill's job.
3. **Staleness**: Does the code still reflect this decision? If not (decision was superseded during implementation but not updated), flag for removal or amendment in `decisions.md`.

#### D6 — Roadmap Drift: Mandatory Checks

| Field | Planned (from roadmap) | Actual (from epic) | Drift? |
|-------|----------------------|-------------------|--------|
| Appetite | Xw | Yw | Yes if X != Y |
| Status | In Progress | Complete/Partial | Update |
| Milestone | MVP / v1.0 | Reached? | Update |
| Dependencies | [list] | New ones discovered? | Add |
| Risks | [list] | Materialized? Mitigated? New? | Update |

#### D7 — Epic Drift: Scan Procedure

1. List future epics from `epics/*/pitch.md` (up to 15, prioritize by roadmap order)
2. For each, check if the current epic changed: APIs, schemas, bounded context boundaries, or technology choices assumed in the pitch
3. Report top 5 most impacted. If >5, summarize overflow.

---

### Phase 3. Compute Drift Score + Impact Radius

#### Drift Score

`Score = (docs_current / docs_checked) * 100` — a doc is "current" if zero drift items found.

Generate a **Documentation Health Table** listing each checked doc, which categories (D1-D10) apply, status (CURRENT/OUTDATED), and drift item count.

#### Impact Radius Matrix

Before proposing changes, show the scope of work:

| Changed Area | Directly Affected Docs | Transitively Affected | Effort |
|-------------|----------------------|----------------------|--------|
| [area from git diff] | [docs] | [downstream docs] | S/M/L |

Effort levels: **S** (single section edit), **M** (multiple sections or cross-doc), **L** (structural rewrite).

---

### Phase 4. Propose Updates with Concrete Diffs

For each detected drift item, generate a structured proposal:

| # | ID | Category | Affected Doc | Current State | Expected State | Severity |
|---|-----|----------|-------------|---------------|----------------|----------|
| 1 | D1.1 | Scope | solution-overview.md | Missing feature X | Feature X implemented | medium |
| 2 | D5.1 | Decision | ADR-003 | status: Accepted | Code contradicts decision | high |

**For each proposal, provide the concrete diff:**

- **Markdown docs**: Show the specific section with before/after (3 lines of context)
- **Roadmap**: Show the updated epic table row and milestone status
- **ADRs**: Draft the supersede/amend header only (full ADR is the `adr` skill's job)

Limit to 20 proposals. If >20, show top 15 by severity and summarize the rest as titles.

---

### Phase 5. Roadmap Review (Mandatory)

**Always runs after every epic.** Compare `planning/roadmap.md` against actual epic outcome and generate:

1. **Epic Status Table**: appetite planned vs actual, status update, milestone reached?
2. **Dependencies Discovered**: new inter-epic dependencies found during implementation
3. **Risk Status**: for each risk in roadmap — materialized, mitigated, or did not occur. Add new risks discovered.
4. **Concrete diffs** for `planning/roadmap.md` — updated epic table row, milestone status, risk table

---

### Phase 6. Future Epic Impact

Generate a table of future epics affected by the current implementation. Columns: Epic, Pitch Assumption, How Affected, Impact, Action Needed.

If zero future epics are affected: report "Nenhum impacto em epics futuros detectado."

---

### Phase 7. Auto-Review

**Tier 1 — Deterministic checks:**

| # | Check | How | Action on Failure |
|---|-------|-----|-------------------|
| 1 | Report file exists and is non-empty | `test -s <file>` | Save it |
| 2 | All 10 drift categories scanned | grep for D1-D10 in report | Scan missing categories |
| 3 | Drift score computed | grep for "Drift Score:" | Compute it |
| 4 | No placeholder markers remain | `grep -c 'TODO\|TKTK\|???\|PLACEHOLDER'` = 0 | Remove or resolve |
| 5 | HANDOFF block present at footer | grep `handoff:` at end | Add it |
| 6 | Impact radius matrix present | grep "Impact Radius" or "Raio de Impacto" | Generate it |
| 7 | Roadmap review section present | grep "Revisao do Roadmap" | Generate it |

**Tier 2 — Scorecard for human reviewer:**

| # | Scorecard Item | Self-Assessment |
|---|---------------|-----------------|
| 1 | Every drift item has current vs expected state | Yes/No |
| 2 | Roadmap review completed with actual vs planned | Yes/No |
| 4 | ADR contradictions flagged with recommendation (amend/supersede) | Yes/No |
| 5 | Future epic impact assessed (top 5) | Yes/No |
| 6 | Concrete diffs provided (not vague descriptions) | Yes/No |
| 7 | Trade-offs explicit for each proposed change | Yes/No |

---

### Phase 8. Gate: Human

Present the full reconcile report (drift score, health table, impact radius, proposals, roadmap review, future epic impact, scorecard). Request approval before applying any changes. If the user approves partially, apply only approved items.

---

### Phase 9. Auto-Commit (Cascade Branch Seal)

After user approval, stage, commit, and push all epic work so the next epic's worktree can cascade from a clean remote base:

```bash
git add -A
git commit -m "feat: epic <NNN> <title> — full L2 cycle"
git push -u origin HEAD
```

Report:
- Commit hash and branch name
- Files committed (count + summary by category)
- Push result: `origin/<branch>` updated (or error details if push failed)
- Confirmation: `epic/<platform>/<NNN-slug>` is ready to be the base for the next epic

If nothing to commit: report "Working tree clean — nothing to commit. Branch already sealed."
If `git commit` fails: report the error clearly, do NOT block handoff (commit is advisory, not a gate).
If `git push` fails: report the error clearly, do NOT block handoff (push is advisory — cascade falls back to main if branch is not on remote).

---

## Error Handling

| Problem | Action |
|---------|--------|
| No git diff (nothing changed) | Report "zero drift", score 100% |
| Architecture docs incomplete | List gaps, suggest completing the pipeline |
| Drift too large (>20 items) | Show top 15 by severity, summarize the rest as titles |
| No `planning/roadmap.md` | Skip roadmap review, report as WARNING |
| No `decisions/ADR-*.md` | Skip decision drift (D5), report as WARNING |
| No future epics exist | Skip epic drift (D7), report "Nenhum epic futuro encontrado" |
| No `verify-report.md` for this epic | WARN: "Verify deveria rodar antes de reconcile" |
| No `qa-report.md` for this epic | WARN: "QA deveria rodar antes de reconcile" |
| No `README.md` for this platform | Skip README drift (D9), not all platforms have one |

