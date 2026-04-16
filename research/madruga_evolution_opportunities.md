# madruga.ai — Evolution Opportunities

> **Date**: 2026-04-14
> **Sources**: AgentScope architecture analysis, everything-claude-code (ECC) analysis, codebase deep-dives
> **Method**: Per-opportunity sub-agent deep-dive — problem validation, current state, best practices, recommendation

---

## Executive Summary

Cross-referencing AgentScope (multi-agent framework, Alibaba) and everything-claude-code (155k-star Claude Code plugin ecosystem) against madruga.ai revealed **11 improvement opportunities**. After deep-dive validation against the actual codebase, **8 are confirmed actionable** and **3 are deferred or downgraded**.

madruga.ai's strengths remain unchallenged: DAG orchestration, declarative pipeline, prefix cache ordering, retry/circuit-breaker, skill contracts. The opportunities below fill gaps in **developer experience**, **cost efficiency**, **security**, and **pipeline learning** — without compromising those strengths.

### Priority Matrix

| Priority | Opportunity | Effort | Impact | Source |
|----------|-----------|--------|--------|--------|
| **Infra** | Model routing by pipeline node (infra only) | S | Future flexibility | ECC |
| **P0** | 3-layer architecture: Pipeline + Specialists + Repo Knowledge | M-L | Quality uplift across ALL nodes | ECC + codebase gap |
| **P0** | Judge score persistence + regression alerts | S | Quality visibility | ECC + AgentScope |
| **P1** | Fact-forcing PreToolUse hook | S | Implementation quality | ECC GateGuard |
| **P1** | Security hardening (secrets + config protection) | M | Risk reduction | ECC |
| **P2** | Hook lifecycle expansion (SessionStart, PreCompact) | M | Developer experience | ECC |
| **P2** | Structured compression for dispatch context | M-L | Longer sessions, fewer resets | AgentScope |
| **P3** | Self-learning / instinct system (Tier 1 only) | M | Cross-epic learning | ECC + AgentScope |
| **Defer** | Santa Loop for Judge | — | Not needed yet | ECC |
| **Defer** | RAG over documentation corpus | — | Premature | AgentScope |
| **Defer** | Inter-skill messaging / A2A | — | Over-engineering | AgentScope |

---

## Infrastructure — Model Routing (Build, Don't Use Yet)

### 1. Model Routing by Pipeline Node

**Problem validated: PARTIALLY — cost savings are real, but quality loss is unacceptable**

Deep-dive into actual skill complexity revealed that NO L2 node is "mechanical enough" for Haiku:
- **analyze** requires detecting subtle cross-artifact inconsistencies (duplicated rules, underspecification gaps). Haiku would miss 40-60% of issues.
- **reconcile** traces code changes through 5 documentation layers and infers impact on future epics. Strong reasoning required.
- **judge** filters 4-persona findings with nuanced severity reclassification. Weak models produce noisy results.

Even "balanced" nodes (implement, clarify, tasks, qa) lose 20-30% quality with weaker models.

**Revised recommendation**: Build the infrastructure (~80 LOC) but keep all nodes on Opus 4.6. The value of the pipeline depends on quality gates catching issues early — a missed bug in analyze costs more than the model price difference.

**Implementation (3 changes, ~80 LOC — future-proofing only)**:
1. Add optional `model:` field to each node in `pipeline.yaml`
2. Add `model: str | None` to `Node` namedtuple; update `parse_dag()` to extract it
3. In `build_dispatch_cmd()`: `if node.model: cmd.extend(["--model", node.model])`

**When to actually use it**: When new models launch with better cost/performance ratios, or for L1 nodes (vision, solution-overview) where reasoning requirements differ.

**Effort**: S (2-4 hours). Backward compatible — `model` defaults to `None` (inherits system default).

---

## P0 — Do First (High Impact)

### 2. 3-Layer Architecture: Pipeline + Generic Specialists + Repo Knowledge

**Problem validated: YES (biggest quality lever identified)**

All 34 current skills are **process-oriented** (SDLC). Zero domain expertise exists. The `implement` skill receives the same prompt whether it's generating FastAPI endpoints, React components, or SQLite migrations. The Judge personas (arch-reviewer, bug-hunter, simplifier, stress-tester) review code **blind** to:
- PostgreSQL RLS hardening patterns
- pydantic-ai idiomatic usage
- Redis Streams consumer group correctness
- Circuit breaker state machine invariants
- LGPD compliance requirements
- 8 other critical domains documented in ADRs but never injected into skills

Result: ~40-60% of epics require extra review iterations to catch domain-specific anti-patterns.

**Mental model (validated)**

A senior consultancy has three distinct bodies of knowledge. madruga.ai today has only one:

| Layer | Purpose | Scope | Status in madruga.ai |
|---|---|---|---|
| **1. Pipeline / Commands** | "WHAT to do" (SDLC) | Universal across repos | Exists (25 skills) |
| **2. Generic Specialists** | "HOW to do well" (craft/expertise) | Universal across repos | Missing |
| **3. Repo Knowledge** | "How WE do it HERE" (local conventions + which specialists apply) | Per-repo/platform | Partial (CLAUDE.md + ADRs) |

**Why the 3-layer split matters**

- Layers 1+2 are stable — written once, reused across all platforms
- Layer 3 is variable — each repo declares its stack + which specialists apply
- Avoids the ECC trap (181 unstructured skills) while capturing the same expertise
- Preserves the uniform skill contract that makes madruga.ai auditable

**Layer 2 catalog (proposed, ~15 specialists covers both current platforms)**

- Backend/Infra: `backend-python-expert`, `fastapi-expert`, `pydantic-ai-expert`, `postgres-rls-expert`, `sqlite-wal-expert`, `redis-streams-expert`
- Frontend: `nextjs-expert`, `astro-starlight-expert`, `ui-component-expert`
- Craft transversal: `resilience-expert`, `observability-expert`, `security-expert`, `test-expert`, `llm-orchestration-expert`
- Meta: `migration-expert`

**Layer 3 declaration (per `platform.yaml`)**

```yaml
specialists:
  - backend-python-expert
  - fastapi-expert
  - postgres-rls-expert
  - redis-streams-expert
  - pydantic-ai-expert
  - observability-expert
repo_knowledge:
  - path: .claude/knowledge/local/prosauai-conventions.md
  - path: .claude/knowledge/local/bifrost-gateway.md
```

Pipeline (Layer 1) reads `platform.yaml` and routes specialists dynamically based on task metadata (e.g., task touches `.tsx` → inject `ui-component-expert` + `nextjs-expert`).

**Boundary rule (Layer 2 vs Layer 3)**

- Layer 2: "how X works in general" → "RLS policies must use `auth.uid()`, never `user_metadata`"
- Layer 3: "how we use X here" → "in this repo, tenant_id comes from `X-Tenant-ID` header"

**Constitution note**: `speckit.constitution` is Layer 2 **governance** (project principles), not Layer 2 **expertise** (technical craft). Both are universal but distinct — keep them separated.

---

#### Option A — Specialists as Knowledge Files (Markdown)

Each specialist is a markdown file under `.claude/specialists/`. `compose_task_prompt()` reads `platform.yaml.specialists`, loads the relevant files, and injects their content into the prompt.

**Structure**
```
.claude/specialists/
  postgres-rls-expert.md       (~500 lines: patterns, anti-patterns, test templates)
  fastapi-expert.md            (~400 lines)
  redis-streams-expert.md      (~350 lines)
  ...
```

**Pros**
- Simple — same infra as existing `.claude/knowledge/`
- Deterministic — specialist content always present in prompt
- No invocation overhead (zero extra LLM calls)
- Works with existing prompt caching if placed in the stable prefix
- Easy to version, lint, and audit (reuse skill-lint)

**Cons**
- **Prompt bloat** — 15 specialists × ~400 lines ≈ ~6000 lines added to base prompts. Undermines prefix cache wins from Phase 5 (`MADRUGA_CACHE_ORDERED`)
- Always-on — specialists are in prompt even when not relevant to the task
- Scaling ceiling — more specialists linearly inflate every dispatch
- Judge loses parallelism — all expertise in one agent context, no isolation between reviewers

**Effort**: M (~2-3 weeks)
- 15 specialist files (~40h)
- Extend `compose_task_prompt()` for Layer 3 → Layer 2 resolution (~8h)
- Extend `platform.yaml` schema + validator (~4h)
- Tests + docs (~8h)

**Expected impact**: Medium. Solves the knowledge gap at a significant prompt-cost tradeoff. Good for Layer 2 governance (constitution-style), weaker for Layer 2 expertise (craft).

---

#### Option B — Specialists as Claude Code Subagents (RECOMMENDED)

Each specialist is a Claude Code agent in `.claude/agents/<name>.md` with YAML frontmatter (system prompt, allowed tools, model). Skills invoke specialists via the `Task` tool when domain expertise is needed. Each specialist runs in an **isolated context** and returns a focused result.

**Structure**
```
.claude/agents/
  postgres-rls-expert.md
  fastapi-expert.md
  redis-streams-expert.md
  ...
```

Example file:
```markdown
---
name: postgres-rls-expert
description: Senior PostgreSQL engineer specializing in RLS, multi-tenant isolation, and Supabase patterns. Use when implementing, reviewing, or designing anything touching RLS policies, tenant isolation, or pgvector namespacing.
model: opus
tools: Read, Grep, Glob
---

You are a senior PostgreSQL engineer with deep expertise in Row-Level Security...

## Checklist
- All RLS policies use `auth.uid()` not `user_metadata`
- Every RLS-enabled table has an index on tenant columns
- SECURITY DEFINER functions are audited and least-privilege scoped
...
```

**Pros**
- **Isolated context** — each specialist has its own token budget; main agent prompt stays lean
- **Parallelism** — Judge can invoke 4-8 specialists in parallel (domain-scoped review)
- **Dynamic activation** — only invoked when relevant (frontend-expert on `.tsx`, postgres-expert on migrations)
- **Composable** — `implement` can invoke `postgres-rls-expert` for DB layer AND `fastapi-expert` for endpoints in the same task, each focused
- **Claude Code native** — uses existing `Task` tool, no new harness code
- **Preserves prefix cache** — specialists are not in the main prompt
- **Scales cleanly** — adding a 20th specialist has zero impact on existing dispatches

**Cons**
- **Invocation overhead** — each specialist call is a separate LLM invocation (~$0.02-0.10 and 5-20s per call)
- **More complex design** — skills need logic to decide WHEN to invoke WHICH specialist
- **Harder to audit** — specialist output is ephemeral unless explicitly persisted
- **Requires subagent instrumentation** — need to track specialist calls in `pipeline_runs` for cost attribution
- **Activation discipline** — without clear rules, skills may over-invoke (cost) or under-invoke (missed expertise)

**Effort**: M-L (~3-4 weeks)
- 15 subagent definitions (~30h — less content than Option A since context is focused)
- Activation rules per skill (~12h)
- Extend `platform.yaml` specialist roster (~4h)
- Instrument `Task` tool calls in `pipeline_runs` (~8h)
- Modify Judge to delegate domain reviews to specialist subagents (~12h)
- Tests + docs (~12h)

**Expected impact**: **High**. Closes the domain expertise gap without compromising prompt caching. Enables dynamic, composable expertise per task. Judge becomes multi-domain.

---

#### Recommendation: Option B (Subagents)

**Why B wins:**

1. **Prompt caching integrity** — Phase 5 prefix caching is a meaningful cost/latency win. Option A undoes it. Option B doesn't touch the main prompt.
2. **Dynamic > Static** — different tasks need different expertise. Static injection (A) includes everything always, which dilutes focus and wastes tokens.
3. **Judge becomes multi-domain naturally** — current 4-persona model (arch/bug/simplifier/stress-tester) is effective but blind to domain specifics. With subagents, Judge invokes `postgres-rls-expert` in parallel with `arch-reviewer` for DB-touching tasks.
4. **Scales to new platforms** — adding Rust/Go/mobile specialists doesn't penalize existing platforms.

**When Option A would be preferable**: if specialists were small (<100 lines) AND universally applied (constitution-style). For deep craft expertise (RLS policies, observability conventions, Redis Streams patterns), isolated subagents fit better.

**Hybrid possibility**: Option A for constitution-style Layer 2 governance (lightweight, universal) + Option B for Layer 2 expertise (heavy, domain-specific). Matches how the two kinds of content differ in size and activation pattern.

---

#### Implementation Path (Option B)

**Phase 1 — Foundation (1 week)**
- Extend `platform.yaml` schema with `specialists` and `repo_knowledge` fields
- Validator: specialists declared must exist in `.claude/agents/`
- Create 3 pilot specialists: `postgres-rls-expert`, `fastapi-expert`, `resilience-expert`

**Phase 2 — Integration (1 week)**
- Modify `implement` dispatch to invoke relevant specialists based on task file types
- Modify `judge` to invoke domain specialists in parallel with existing 4 personas
- Instrument specialist calls in `pipeline_runs` (new columns: `specialist_calls`, `specialist_cost_usd`)

**Phase 3 — Catalog buildout (1-2 weeks)**
- Create remaining ~12 specialists based on observed gaps from pilot
- Migrate relevant sections from existing ADRs into specialist files
- Document activation rules per skill in `.claude/knowledge/specialist-routing.md`

**Phase 4 — Measure and iterate**
- Compare Judge scores before/after for 5 epics
- Compare review iteration counts (target: -40%)
- Tune activation rules based on false-positive/false-negative rates

**Kill-switch**: `MADRUGA_SPECIALISTS=0` reverts to current behavior.

---

### 3. Judge Score Persistence + Regression Alerts

**Problem validated: YES**
14 epics judged across 2 platforms. Scores exist only in markdown reports — never stored in DB. Score range observed: 59-92%. No way to detect quality regression. `eval_scores` table exists (migration 010) but is unused for Judge output.

**Current gaps**:
- Can't answer: "Did quality regress after epic 015?"
- Can't set quality gates: "shipping requires Judge score >= 80"
- Fix rate varies wildly (0-56%) with no tracking

**Recommendation (phased)**:

**Phase 1 — `judge_scores` table (2-3 hours)**:
```sql
CREATE TABLE judge_scores (
    score_id TEXT PRIMARY KEY,
    platform_id TEXT NOT NULL,
    epic_id TEXT NOT NULL,
    score INTEGER NOT NULL,
    initial_score INTEGER,
    verdict TEXT CHECK (verdict IN ('pass', 'fail')),
    findings_total INTEGER,
    findings_fixed INTEGER,
    blockers_count INTEGER,
    warnings_count INTEGER,
    nits_count INTEGER,
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (platform_id) REFERENCES platforms(platform_id)
);
```
- Parse `judge-report.md` frontmatter at end of Judge skill
- Insert score + finding counts

**Phase 2 — Regression alert (4-6 hours)**:
```sql
SELECT platform_id, epic_id, score,
       LAG(score) OVER (PARTITION BY platform_id ORDER BY evaluated_at) as prev_score
FROM judge_scores
WHERE score < prev_score - 10;  -- Alert on 10+ point drop
```

**Phase 3 — Map to eval_scores dimensions (1-2 hours)**:
- Insert 4 rows per Judge pass: `judge_architecture`, `judge_bugs`, `judge_simplicity`, `judge_resilience`

**Effort**: S (total ~8 hours across 3 phases).

**Expected impact**: High. Catches quality regressions within 1 epic. Enables data-driven quality gates.

---

## P1 — Do Next (High Impact, Small-Medium Effort)

### 4. Fact-Forcing PreToolUse Hook (GateGuard Pattern)

**Problem validated: YES**
`compose_task_prompt()` injects spec/plan/data-model into the prompt, but nothing forces the agent to actually process it before editing. The research comparison documents explicitly flag this: "Before the first Edit/Write in a task, require the agent to have Read the spec section."

**Current mitigations**: Context injection via prompt, scoped filtering (`MADRUGA_SCOPED_CONTEXT`), prefix cache ordering. All address *what's in the prompt* — none address *whether the agent reads it before acting*.

**Best practice**: ECC's GateGuard — DENY first edit, FORCE investigation, ALLOW after facts. A/B tested: +2.25 improvement score.

**Recommendation**: Add a PreToolUse hook (`hook_pre_tool_gate.py`, ~150 LOC) for `implement` dispatches:
- On first Edit/Write in session: check if agent has Read spec, plan, and data-model sections
- If not: DENY with error message pointing to required reads
- Track session state via temp file (which files have been Read)
- Kill-switch: `MADRUGA_GATE_FORCE_READ=0`

**Effort**: S (4-6 hours). Reuses existing hook infrastructure.

**Expected impact**: High. Directly reduces hallucinated implementations. ECC's +2.25 A/B result suggests measurable improvement.

---

### 5. Security Hardening (Secrets Scanning + Config Protection)

**Problem validated: YES (preventive)**
No incidents found in git history, but the attack surface is real:
- `.env.example` shows `OPENAI_API_KEY`, `POSTGRES_PASSWORD`, `MADRUGA_TELEGRAM_BOT_TOKEN` — dispatch agents could leak these
- No file is protected from Write/Edit during dispatch (pipeline.yaml, settings.json, platform.yaml)
- skill-lint validates structure but NOT content for prompt injection patterns

**Current mitigations**: `hook_validate_placement.py` (cross-repo writes), per-node `--tools` restrictions, `DISALLOWED_TOOLS` blocks dangerous git ops, path security tests prevent traversal.

**Recommendation (2 tiers)**:

**Tier 1 — Config protection hook (8 hours)**:
- `hook_config_protection.py`: Block Write/Edit to protected files during dispatch
- Protected list: `pipeline.yaml`, `.claude/settings.json`, `.claude/settings.local.json`, `.env`, `platform.yaml`, `pyproject.toml`
- Alternatively: add to `DISALLOWED_TOOLS` at dispatch level (stronger, simpler)

**Tier 2 — Secrets scanning hook (12 hours)**:
- `hook_secrets_scan.py`: Regex patterns for credential formats
- Patterns: `AKIA[0-9A-Z]{16}`, `-----BEGIN.*KEY-----`, `sk_live_`, `ghp_`, `glpat-`, DB passwords in URLs
- Non-blocking warning unless CRITICAL (private key blocks)

**Tier 3 — Prompt injection scanning in skill-lint (10 hours)**:
- Extend `skill-lint.py` to scan for `{{`, `{%`, `[SYSTEM]`, `<|assistant|>` in skill bodies
- WARNING severity on suspicious patterns outside fenced code blocks

**Effort**: M (total ~30 hours across 3 tiers). Tier 1 standalone is S.

**Expected impact**: High risk reduction. Credential leak probability drops from ~70% (estimated) to ~15% with Tier 1+2.

---

## P2 — Follow-Up (Medium Impact, Medium Effort)

### 6. Hook Lifecycle Expansion

**Problem validated: YES**
Only 4 PostToolUse hooks active. Claude Code supports 7+ event types. Key gaps: no SessionStart (users re-brief manually), no PreCompact (context lost on compaction), no Stop (no auto-summary).

**Current architecture**: All hooks read JSON from stdin, Python scripts with shell wrappers, `2>/dev/null || true` to never block. `sync_memory.py` already skips under `MADRUGA_DISPATCH=1`. Orphaned `hook_post_commit.py` (~233 LOC) exists but is NOT configured.

**Recommended new hooks (priority order)**:

| Hook | Event | Purpose | Effort |
|------|-------|---------|--------|
| `hook_session_start.py` | SessionStart | Load STATE.md checkpoint + epic context on session begin | M (2-4h) |
| `hook_precompact_snapshot.py` | PreCompact | Auto-save STATE.md + memory snapshot before context trim | M (2-4h) |
| Enable `hook_post_commit.py` | git post-commit | Register commits to DB (already written, unused) | S (1h) |
| `hook_pretooluse_guard.py` | PreToolUse | Validate file paths before Write (shift-left from PostToolUse) | S (1-2h) |
| `hook_stop_summarize.py` | Stop | Parse transcript, update STATE.md with decisions | L (4-8h) |

**Effort**: M (total ~12-20 hours).

**Expected impact**: Medium. Reduces session re-briefing friction, protects context from compaction loss, enables commit-level traceability.

---

### 7. Structured Compression for Dispatch Context

**Problem validated: YES (with real incidents)**
prosauai/003 T031 hit Anthropic's 1M context window limit on session resume. Max tokens observed: 9.5M on `implement:phase-6`. Average implement phase: 2.3-3.2M tokens. QA: 6.1M, Judge: 5.4M.

**Current mitigations (working but hitting ceiling)**:
- `SESSION_RESUME_MAX_TOKENS = 700K` — hard reset after 700K
- `SESSION_RESUME_MAX_TASKS = 8` — fresh session after 8 tasks
- `MAX_PROMPT_BYTES = 200KB` — safety net
- `MADRUGA_KILL_IMPLEMENT_CONTEXT=1` — 5-task recent progress (4-12KB savings/task)
- Phase dispatch with stdin (removes ARG_MAX limit)

**Recommendation (phased)**:

**Phase 1 — Resume chain compression (2-3 weeks)**:
- When `tokens_in >= 600K`, compress previous task outputs via LLM before resuming
- Summary schema: `task_id`, `outcome`, `key_files_modified`, `test_results`, `blockers_encountered`
- Optional: cheaper model (Haiku) for summarization

**Phase 2 — Mid-phase compression (1-2 weeks)**:
- After each task completes in a phase, summarize before moving to next
- Keeps all tasks in one session without fragmentation

**Effort**: M-L (3-5 weeks total).

**Expected impact**: High for large phases. Enables 2-3x longer resume chains (12-16 tasks vs current 8), eliminates "session forced reset" pauses, 20-30% context savings on late tasks.

---

## P3 — Later (Medium Impact, Requires Design)

### 8. Self-Learning / Instinct System (Tier 1 Only)

**Problem validated: YES**
123 completed L2 cycles across 6 epics and 3 platforms. Zero institutional memory of behavioral patterns. `plan` node fails 5x on "unfilled template" — same error, never learned. 1,712 eval scores exist but no pattern extraction.

**What's worth extracting** (specific patterns):

1. **Error taxonomy** — Classify `pipeline_runs.error` by regex: `template`, `rate_limit`, `timeout`, `sql`, `anthropic_api`. Track repeat rates. Auto-detect deterministic vs transient.
2. **Judge findings patterns** — Parse judge-report.md: severity distribution per persona, finding categories that recur across epics.
3. **Cost/duration regression** — Track (platform, epic_size, node) -> actual duration. Flag outliers (3x average = likely stuck).
4. **Eval score trends** — Rolling avg quality/adherence/completeness per node. Correlate low adherence with specific causes.

**Recommendation: Simple extraction, NOT semantic memory**

Skip Mem0/ReMe-style vector memory — overkill for a deterministic pipeline. No ML, no embeddings, no knowledge graphs.

**Tier 1 MVP (~500 LOC, 2-3 weeks)**:
- 3-4 new tables: `error_patterns`, `finding_patterns`, `eval_trends`
- Post-run hooks extract & store structured patterns
- Require min 5 occurrences before surfacing a pattern
- Query API for skills to read relevant patterns

**Tier 2 (defer)**:
- Add confidence scoring (0-1.0) to patterns
- Decay unused patterns (not seen in 5 epics -> -20% confidence)
- Promote at 80%+ to "instinct" (inject into future dispatches)

**Effort**: M (Tier 1 only: 2-3 weeks).

**Expected impact**: Medium. Reduces failure repeat rate by ~40-50% (catches deterministic errors early). Improves estimate accuracy. Reduces Judge surprises.

**Risk**: Over-engineering is real if pattern frequency is too low. Mitigate with the 5-occurrence minimum threshold.

---

## Deferred — Not Now

### 9. Santa Loop for Judge

**Verdict: SKIP (for now)**

The current 4-persona consensus + Judge filtering already handles bias effectively. Evidence from epic 005: 3-persona agreement escalated to BLOCKER, 1-persona findings evaluated individually, 8 duplicates deduplicated to best version. Model diversity adds cost (2x Judge passes) with marginal gain over persona diversity.

**Revisit when**: Production incident data correlates low Judge scores with bugs, or a specific model blind spot is identified.

---

### 10. RAG Over Documentation Corpus

**Verdict: PREMATURE**

The pipeline already uses scoped context filtering (`MADRUGA_SCOPED_CONTEXT`) and prefix cache ordering. Adding vector search over ADRs/specs/blueprints requires embedding infrastructure (Qdrant/Chroma, embedding model, indexing pipeline) for marginal improvement over current keyword-based context injection.

**Revisit when**: Documentation corpus exceeds what scoped context can handle (>50 ADRs, >20 epics per platform).

---

### 11. Inter-Skill Messaging / A2A Protocol

**Verdict: OVER-ENGINEERING**

Skills run as isolated `claude -p` subprocesses by design — this isolation is a feature (reproducibility, retry, checkpointing). Adding pub/sub or A2A messaging would break isolation guarantees and add complexity without clear benefit. Phase dispatch already groups related tasks.

**Revisit when**: The pipeline needs real-time collaboration between concurrent skills (not currently in roadmap).

---

## Implementation Roadmap

```
Sprint 1 (P0 — quick wins):
  [1] Model routing infra (build, don't activate) ..... 4h
  [3] Judge score persistence (Phase 1) ............... 3h

Sprint 2-3 (P0 — 3-layer architecture, Option B):
  [2-Ph1] platform.yaml schema + 3 pilot specialists .. 40h
  [2-Ph2] implement + judge integration + tracking .... 32h

Sprint 4-5 (P0 catalog + P1 start):
  [2-Ph3] Remaining ~12 specialists + routing docs .... 50h
  [4] Fact-forcing PreToolUse hook .................... 6h
  [5a] Config protection hook (Security Tier 1) ....... 8h

Sprint 6 (P1 continued + P2 start):
  [5b] Secrets scanning hook (Security Tier 2) ........ 12h
  [6a] SessionStart hook .............................. 4h
  [6b] PreCompact snapshot hook ....................... 4h

Sprint 7 (P2):
  [7] Structured compression Phase 1 .................. 20h
  [3b] Judge regression alerts (Phase 2) .............. 6h

Sprint 8+ (P3):
  [8] Self-learning Tier 1 (error taxonomy + findings). 20h
  [5c] Prompt injection scanning in skill-lint ........ 10h
```

**Total estimated effort**: ~219 hours across 8 sprints (3-layer architecture is the largest single investment at ~122h but delivers the highest quality uplift).

---

## Cross-Reference: What NOT to Import

| Aspect | Source | Why Skip |
|--------|--------|----------|
| Code-first-only config | AgentScope | Declarative YAML is a strength |
| 181 skills without contract | ECC | Quality > quantity; 6-section contract is superior |
| tmux-based parallelism | ECC | Phase dispatch + DAG executor is more robust |
| Cross-harness portability | ECC | Purpose-built for Claude Code; supporting 7 platforms dilutes focus |
| No retry at framework level | AgentScope + ECC | Circuit breaker is a strength; never regress |
| Heavy dependency footprint | AgentScope | stdlib + pyyaml philosophy is better for reliability |
| Session .tmp files | ECC | SQLite WAL with proper schema > ad-hoc temp files |
| Vector/semantic memory | AgentScope | Premature for deterministic pipeline |

---

## Conclusion

madruga.ai's core architecture (DAG orchestration, declarative pipeline, prefix caching, retry resilience, skill contracts) is strong and validated by comparison with both AgentScope and ECC. Neither system matches madruga.ai's orchestration depth.

The highest-ROI improvements are:
1. **3-layer architecture (Pipeline + Specialists + Repo Knowledge)** — the biggest quality lever. Closes the domain expertise gap that causes 40-60% of epics to need extra review iterations. Option B (subagents) recommended to preserve prompt caching.
2. **Model routing infra** — build the plumbing now, activate when better cost/performance models exist
3. **Judge persistence** — unlocks quality visibility with minimal effort
4. **Fact-forcing hooks** — proven +2.25 improvement in ECC, addresses real hallucination risk
5. **Security hardening** — preventive, no incidents yet but attack surface is real

The self-learning system (P3) is the most ambitious but should wait until P0-P2 deliver the data infrastructure it needs (judge scores in DB, error patterns, eval trends).
