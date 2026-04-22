---
description: Detect drift from untracked commits (including direct pushes to bound repos) and propose doc updates
arguments:
  - name: platform
    description: "Platform/product name."
    required: false
argument-hint: "[platform]"
handoffs:
  - label: Check Pipeline Status
    agent: madruga/pipeline
    prompt: "Reverse-reconcile complete. Check pipeline status."
---

# Reverse-Reconcile — Drift Detection from Untracked Commits

> **Contract**: Follow steps 0 and 5 from `.claude/knowledge/pipeline-contract-base.md`.

Inverse of `madruga:reconcile`. Starts from **commits** (especially those made directly in the bound external repo) and asks: "does our documentation reflect these?" Ingests remote commits that never hit the local hook, triages them deterministically, and proposes concrete doc patches via JSON semantic patches.

## Cardinal Rule: ZERO Silent External Drift

Every commit in a bound repo must either (a) be reconciled into the docs, or (b) be explicitly marked as non-doc-affecting. No commit should sit forever with `reconciled_at IS NULL`.

**NEVER:**
- Call any reverse-reconcile script with `--commit` before the human gate approves the proposals.
- Edit an ADR that a commit appears to contradict — only **report** the contradiction (user decides whether to open a supersede ADR or a new epic).
- Skip triage — every commit must land in `none` (auto-reconciled) or a layer cluster before LLM analysis runs.
- Generate vague proposals — every patch must include `anchor_before`, optional `anchor_after`, and `new_content`.

## Persona

Drift Archaeologist. You assume the docs are stale until each commit proves otherwise. Deterministic triage first, LLM only on the residue. Write all generated artifact content in Brazilian Portuguese (PT-BR).

## Usage

- `/madruga:reverse-reconcile prosauai` — direct mode
- `/madruga:reverse-reconcile` — interactive (prompts for platform)

## Output Directory

Save the report to `platforms/<name>/reconcile-reports/reverse-YYYYMMDD-HHMMSS.md`.
Save the patch bundles (per layer) to `platforms/<name>/reconcile-reports/reverse-YYYYMMDD-HHMMSS-<layer>.patches.json`.

---

## Instructions

### Phase 1. Ingest missing commits from `base_branch`

**Always ingest first** — `reconciled_at IS NULL` only counts what the DB already knows about. Commits newly pushed to `origin/<base_branch>` must be ingested before any counting, or Phase 2 will falsely report "no drift".

```bash
python3 .specify/scripts/reverse_reconcile_ingest.py --platform <name> --json
```

**Branch scope**: the script reads `platform.yaml → repo.base_branch` (e.g., `develop` for prosauai, `main` for most) and walks **only `origin/<base_branch>`**. Feature branches, epic branches, and abandoned branches are excluded — only commits that shipped to the production branch count as drift. Idempotent.

Echo the result JSON to the user: `branch`, `remote_total`, `inserted`, `auto_marked_on_insert`, `retroactively_marked`. The `branch` field surfaces mismatches with expectations early.

**Backlog shortcut** — if this is the first run on a repo with hundreds of pre-existing commits, ask the user if they want to skip inspection of everything before a cutoff SHA:

```bash
python3 .specify/scripts/reverse_reconcile_ingest.py --platform <name> --assume-reconciled-before <sha>
```

### Phase 2. Count remaining unreconciled commits

After ingest, count the residue:

```bash
python3 .specify/scripts/reverse_reconcile_mark.py --platform <name> --count-unreconciled --json
```

If `unreconciled == 0`, STOP and report "no drift". Otherwise continue to triage.

### Phase 3. Deterministic triage

```bash
python3 .specify/scripts/reverse_reconcile_classify.py --platform <name> --out /tmp/triage.json
```

Output buckets:
- `none` — typos, lockfiles, trivial subjects → always auto-reconciled
- `doc_self_edits` — commits where 100% of files are platform doc edits; **already reflected at HEAD**, so they are auto-reconciled (not fed to LLM)
- `clusters.code` — all other commits (code changes + mixed code/doc commits)

Other cluster keys (`business`, `engineering`, `decisions`, `planning`) exist in the output for schema stability but should be empty after V2 — doc-only commits go to `doc_self_edits`, everything else goes to `code`.

**Auto-reconcile noise immediately** (no LLM):

```bash
python3 .specify/scripts/reverse_reconcile_mark.py --platform <name> \
  --shas "$(jq -r '.triage.none[].sha' /tmp/triage.json | paste -sd,)"
```

### Phase 4a. Aggregate per-file (chronological collapse)

```bash
python3 .specify/scripts/reverse_reconcile_aggregate.py --platform <name> \
  --triage /tmp/triage.json --out /tmp/work.json
```

**This is the chronological-priority step.** Aggregate collapses all commits touching the same file into a SINGLE `code_item` with `touched_by_shas: [all SHAs]` and `head_content_snippet` from `origin/<base_branch>:<file>`. LLM downstream never sees per-commit diffs — only HEAD state + the audit trail.

Output has three sections:
- `doc_self_edits.shas_to_auto_reconcile` — mark these now, no LLM
- `code_items` — per-file work items with HEAD snippet + candidate docs
- `deleted_files` — paths that existed in some commit but not at HEAD

**Auto-reconcile doc-self-edits immediately:**

```bash
python3 .specify/scripts/reverse_reconcile_mark.py --platform <name> \
  --shas "$(jq -r '.doc_self_edits.shas_to_auto_reconcile[]' /tmp/work.json | paste -sd,)"
```

### Phase 4b. Human gate — aggregate review

Present to the user, numbered (1, 2, 3…):
- Branch walked + HEAD SHA (sanity-check echo from work.json)
- Counts: noise auto-marked, doc-self-edits auto-marked, code_items, deleted_files
- Top 5 code_items by `len(touched_by_shas)` (most-churned files)
- Any deleted files (docs may still reference them)

Wait for explicit approval to proceed with LLM analysis.

### Phase 5. Per-file LLM analysis (HEAD-grounded)

**Cardinal chronological rule**: HEAD é a fonte de verdade. `touched_by_shas` é APENAS audit trail. Nunca descreva estado intermediário.

**Order**: process `code_items` first by "most-churned files" (longest `touched_by_shas`), then `deleted_files`.

For each `code_item`:

1. Read `head_content_snippet` — **this is what you document, not per-commit diffs**.
2. If snippet is truncated and you need full content, use:
   ```bash
   git -C <repo_path> show origin/<base_branch>:<target_file>
   ```
3. Read the `candidate_docs` (first entry is the top pick).
4. Emit ONE patch per target doc section, with:
   - `sha_refs`: **ALL** `touched_by_shas` (audit trail)
   - `new_content`: describes HEAD reality (PT-BR)
5. Chronological edge cases:
   - **Revert sequences** (HEAD = state before any of these SHAs, or same as a mid-commit): emit EMPTY patch list for this item + still put all SHAs in a "Reversões detectadas" section of the report. They will be marked reconciled with no doc change.
   - **Deletions in `deleted_files`**: search the candidate_docs for references to the deleted path → emit `operation: delete` patches to remove those references. If no references found, mark SHAs reconciled with no patch.

**ADR contradiction detection**: for any code_item whose HEAD state contradicts an existing ADR (e.g., ADR-019 says "Postgres", HEAD code uses SQLite), flag it in the "ADR Contradictions" section. Do NOT generate supersede patches. User decides.

**Sentinel handling — ADR Candidates and Research Gaps**:

The aggregator (`reverse_reconcile_aggregate.py`) injects two kinds of signals into `candidate_docs` that are NOT valid patch targets:

- Any path ending in `__ADR_CANDIDATE__` (e.g., `platforms/<name>/decisions/__ADR_CANDIDATE__`) means the file's change pattern suggests a new architectural decision is implicit in the code. Manifest changes (`pyproject.toml`, `package.json`) and new infra layouts trigger this.
- Any candidate whose path resolves under `platforms/<name>/research/tech-alternatives.md` represents a tech-stack drift signal — new dependency, new runtime, new service.

For these two cases:
- **NEVER emit a patch** with `file` pointing to `__ADR_CANDIDATE__` — apply script will FileNotFound.
- **DO NOT auto-patch** `research/tech-alternatives.md` even though it is a real file — manifest edits rarely yield anchorable diffs, and proposing content requires human context.
- Instead, route these code_items to the **"ADR Candidates"** and **"Research Gaps"** sections of the Phase 9 report with a one-line summary (HEAD file, commits, suggested action).
- Still mark the SHAs reconciled in Phase 8 — they are documented as deferred decisions, not as drift awaiting patches.

**NEVER**:
- Use `git show <sha>` per commit to decide patch content (only for intent clarification).
- Emit separate patches per SHA on the same doc section — use 1 patch with N sha_refs.
- Document features absent from HEAD (don't mention section X if HEAD doesn't have X).
- Emit patches against sentinel paths (`__ADR_CANDIDATE__`) or auto-patch `research/tech-alternatives.md` from manifest diffs.

Emit JSON matching the [apply script format](/home/gabrielhamu/repos/paceautomations/madruga.ai/.specify/scripts/reverse_reconcile_apply.py):

```json
{
  "patches": [
    {
      "file": "platforms/<name>/engineering/containers.md",
      "operation": "replace" | "insert_after" | "delete" | "append",
      "anchor_before": "EXACT text that exists in the doc (>=2 lines is best)",
      "anchor_after": "EXACT text after the region to replace (omit for insert_after)",
      "new_content": "markdown to write (PT-BR)",
      "reason": "Commit abc123 adicionou X; doc só mencionava Y",
      "sha_refs": ["abc123", "def456"],
      "layer": "engineering"
    }
  ]
}
```

6. Save to `platforms/<name>/reconcile-reports/reverse-{ts}-<layer>.patches.json`.

**Patch quality rules:**
- `anchor_before` must be unique in the target file. If you can't find unique text, expand context.
- Never invent docs that don't exist. If no doc covers the commit's topic, use `operation="append"` on the most likely doc and mention "seção nova criada" in `reason`.
- Group commits that touch the same doc section into ONE patch with multiple `sha_refs`.
- Keep `new_content` in PT-BR. Keep code/YAML snippets in English.

### Phase 6. Dry-run apply

```bash
python3 .specify/scripts/reverse_reconcile_apply.py \
  --patches platforms/<name>/reconcile-reports/reverse-{ts}-<layer>.patches.json \
  --repo-root $PWD --json
```

This writes `.proposed` files next to each target. Summarize results: how many applied, how many errors (ambiguous anchor, file not found, etc). If errors, **go back to Phase 5** and regenerate the failing patches with more anchor context — do NOT ask the user to resolve patch conflicts.

### Phase 7. Human gate — review proposals

Present:
- Diff between each original file and its `.proposed` counterpart (use `diff -u`)
- Grouped by layer in order: decisions → engineering → business → planning
- Numbered (1, 2, 3…)
- ADR contradiction flags (copy verbatim from Phase 5)

Ask (numbered):
1. Apply ALL proposed patches?
2. Apply only layers X, Y?
3. Skip specific patches by number?

### Phase 8. Commit approved patches

For each layer/patch the user approved:

```bash
python3 .specify/scripts/reverse_reconcile_apply.py \
  --patches <file>.patches.json \
  --repo-root $PWD --commit --json
```

Then **mark the commits as reconciled** (only the SHAs referenced by applied patches):

```bash
python3 .specify/scripts/reverse_reconcile_mark.py --platform <name> --shas <sha1,sha2,...>
```

Append each applied decision to `platforms/<name>/decisions.md`:
```markdown
- [YYYY-MM-DD reverse-reconcile] {reason} (refs: {sha_refs})
```

Commit the doc changes (branch must be `epic/<platform>/<epic>` or an explicit `docs/<platform>/reverse-reconcile-{ts}` branch):
```bash
git add platforms/<name>/
git commit -m "docs(<name>): reverse-reconcile drift from external commits"
```

### Phase 9. Write the report

`platforms/<name>/reconcile-reports/reverse-{ts}.md`:

```markdown
---
title: Reverse Reconcile Report
platform: <name>
date: <YYYY-MM-DD HH:MM>
commits_reviewed: N
auto_noise: M
patches_proposed: P
patches_applied: A
adr_contradictions: C
adr_candidates: AC
research_gaps: RG
---

## Summary

- Ingested X new external commits (source=external-fetch)
- Auto-marked Y commits as noise (trivial / lockfiles / empty)
- Z commits clustered across layers: {business: ..., engineering: ..., decisions: ..., planning: ..., code: ...}
- Applied N patches across M docs
- Flagged AC ADR candidates and RG research gaps for human review

## Applied Patches

### Layer: engineering
1. `platforms/<name>/engineering/containers.md` — added Redis idempotency section (refs: abc123)
2. ...

## ADR Contradictions (NOT auto-resolved)

- Commit `abc123` appears to contradict **ADR-019** (agent-config-versioning) — author shipped in-memory cache that bypasses the versioned config. User action required: open supersede ADR or revert.

## ADR Candidates (implicit architectural decisions without an ADR)

Routed here by the `__ADR_CANDIDATE__` sentinel in `candidate_docs`. Not auto-patched.

- Commit `abc123` introduced `apps/<name>/workers/stream_processor.py` — event-driven pattern not covered by any existing ADR. Suggested action: `/madruga:adr <name>` with input "stream processing backbone".
- Commit `def456` (pyproject.toml) added `redis[hiredis]>=5.0` — new runtime dependency, no ADR for caching/queue strategy. Suggested action: `/madruga:adr <name>` or amend ADR-003.

## Research Gaps (tech stack drift)

Detected from dependency manifests and new service layouts. `research/tech-alternatives.md` is NOT auto-patched — a proper entry requires comparative analysis.

- `pyproject.toml` (commits def456, ghi789) adopted `redis[hiredis]>=5.0`. `research/tech-alternatives.md` does not list Redis as an evaluated alternative. Suggested action: update tech-alternatives.md with pros/cons of Redis vs in-memory + pub-sub, or open a small research epic.
- `package.json` (commit jkl012) replaced `tanstack-query` with a custom hook. `research/tech-alternatives.md` still lists TanStack as the chosen state lib. Suggested action: decide whether to amend ADR-010 or revert.

## Skipped / Deferred

- Commit `def456` (code cluster) — no clear doc impact, no layer proposed. Marked as reconciled=false for next run review.

## Next Steps

- Consider opening epic `reconcile-drift-<date>` for ADR contradictions (if any).
- Address ADR Candidates via `/madruga:adr <name>` before the next reverse-reconcile cycle.
- Revisit Research Gaps during the next planning slice — treat as debt, not blockers.
- Rerun after N commits accumulate (trigger via portal "drift" badge).
```

### Phase 10. Post-save DB update

```bash
python3 .specify/scripts/post_save.py --platform <name> --node reverse-reconcile --skill madruga/reverse-reconcile --artifact platforms/<name>/reconcile-reports/reverse-{ts}.md
```

---

## Auto-Review Checklist

| # | Check | Action on Failure |
|---|-------|-------------------|
| 1 | Every non-`none` cluster commit has at least one patch OR an explicit deferral reason | Add patch or move to deferred list |
| 2 | All `anchor_before` strings exist (verified by apply script dry-run) | Regenerate patch with wider context |
| 3 | ADR contradictions are reported but NEVER auto-patched | Remove any such patch and convert to report line |
| 4 | Every applied patch's SHAs are passed to mark script | Compute union of `sha_refs` across applied patches |
| 5 | Report saved in `platforms/<name>/reconcile-reports/` with timestamp | Rename if wrong path |
| 6 | `source='external-fetch'` commits appear in the Changes tab filter | Verify by hitting `/api/commits?platform_id=<name>&reconciled=false` |
| 7 | Zero patches target `__ADR_CANDIDATE__` sentinel paths | Move those items to "ADR Candidates" report section |
| 8 | Zero patches target `research/tech-alternatives.md` from manifest diffs | Move those items to "Research Gaps" report section |

## Error Handling

| Error | Response |
|-------|----------|
| `ensure_repo` fails (no SSH, clone refused) | Report to user with exact `git` error; do not continue |
| Apply script: `AnchorNotFound` | Regenerate that single patch with wider anchor; do not ask user |
| Apply script: `AmbiguousAnchor` | Same as above |
| Mark script: 0 rows updated | Warn: the SHA may have been already reconciled by a parallel run; continue |
| Triage cluster empty for all layers | Exit cleanly: only `none` commits existed, already auto-reconciled |
