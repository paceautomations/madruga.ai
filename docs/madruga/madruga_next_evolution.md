# Madruga Next Evolution — Strategic Improvement Roadmap

> **Purpose**: Single source of truth for prioritized improvements. Consolidates findings from 9 reference documents, benchmarks against Claude Code CLI, RTK, GSD, BMAD, Gas Town, and OpenClaw. Reviewed by 6-persona team.
>
> **Generated**: 2026-04-04 | **Branch**: epic/madruga-ai/017-observability-tracing-evals
>
> **Principle**: Value, performance, quality, security >>> effort. Simple performs well.

---

## Part 1 — What Works Well (Protect and Reinforce)

These are proven strengths. Do not refactor, do not over-engineer. Reinforce by adding tests and documentation where missing.

| # | Strength | Evidence | Benchmark |
|---|----------|----------|-----------|
| 1 | **Pipeline DAG with topological sort** | `dag_executor.py` — Kahn's algorithm, circuit breaker, retry, watchdog | Matches Claude Code QueryEngine budget enforcement |
| 2 | **SQLite as state store (WAL mode)** | `db.py` — migrations, FTS5, `_ClosingConnection`, `_BatchConnection` | More sophisticated than Claude Code's JSONL sessions |
| 3 | **Skill contract (6 steps)** | `pipeline-contract-base.md` — Prerequisites→Context→Generate→Review→Gate→Save | Equivalent to Claude Code tool contract |
| 4 | **Knowledge files on-demand** | 7+ files in `.claude/knowledge/`, loaded per-skill | Same pattern as Claude Code system prompt separation |
| 5 | **Structured questions with pushback** | 4 categories (Assumptions, Trade-offs, Gaps, Challenge) + uncertainty markers | Innovation — no Claude Code equivalent |
| 6 | **Human gates with pause/resume** | `human`, `1-way-door`, `auto`, `auto-escalate` | Simpler and more appropriate than Claude Code's 6 permission modes |
| 7 | **Copier template system** | `.specify/templates/platform/` with `copier update` sync | No Claude Code equivalent — unique advantage |
| 8 | **Config as leaf-of-DAG** | `config.py` — 14 lines, zero imports | Identical to Claude Code `src/constants/` pattern |
| 9 | **Circuit breaker** | Closed/open/half-open with max failures + recovery timeout | Classic pattern, well implemented |
| 10 | **LikeC4 as architecture source of truth** | `.likec4` files → JSON export → markdown tables via AUTO markers | Strongest choice per landscape analysis (vs Structurizr, PlantUML, Mermaid) |
| 11 | **MECE artifact model** | Each artifact has 1 owner (skill), 1 purpose, linear progression | Clean separation — pitch→spec→plan→tasks→implement |
| 12 | **Shape Up epics** | Problem, Appetite, Solution, Rabbit Holes, Acceptance Criteria | Battle-tested format for scope control |
| 13 | **Rules with path-scoping** | `.claude/rules/*.md` with `paths:` frontmatter | Context-efficient — loads only when relevant files touched |
| 14 | **PostToolUse hooks** | Auto-register artifacts in DB, auto-lint skills | Deterministic enforcement without LLM compliance dependency |
| 15 | **Observability pipeline (epic 017)** | `traces`, `eval_scores` tables, structlog, `observability_export.py` | Active development — closes the telemetry gap |

---

## Part 2 — Prioritized Improvements

### Tier S — Immediate (next 1-2 sessions, <4h total, highest ROI)

These are low-effort, high-impact items that directly prevent bugs, security issues, or token waste.

#### S1. Context managers everywhere
| Aspect | Detail |
|--------|--------|
| **Problem** | `dag_executor.py` uses `conn = get_conn()` + manual `conn.close()` in 5+ places. A `return` or exception before `close()` = connection leak. |
| **Fix** | Replace all `conn = get_conn(); ... conn.close()` with `with get_conn() as conn:`. The `_ClosingConnection` already supports this. |
| **Impact** | Eliminates entire class of resource leak bugs. |
| **Effort** | 1h | **Source** | M3 (madruga_vs_claude) |

#### S2. Fail-closed gate defaults
| Aspect | Detail |
|--------|--------|
| **Problem** | A typo `gate: "humam"` in platform.yaml passes silently as auto. No validation of gate types. |
| **Fix** | Validate gate against `{"auto", "human", "1-way-door", "auto-escalate"}` in `parse_dag()`. Unknown gate → treat as `human` (fail-closed). |
| **Impact** | Prevents accidental execution of nodes without human approval. |
| **Effort** | 30min | **Source** | M4 (madruga_vs_claude), Claude Code fail-closed pattern |

#### S3. Circuit breaker on skill dispatch
| Aspect | Detail |
|--------|--------|
| **Problem** | If a skill fails repeatedly via `claude -p`, the retry loop burns tokens indefinitely. Anthropic lost ~250K API calls/day from a similar bug in compaction. |
| **Fix** | After 3 consecutive failures of the SAME skill in `dispatch_with_retry()`, disable retries and return failure. |
| **Impact** | Prevents catastrophic token waste on persistent failures. |
| **Effort** | 15min | **Source** | I2 (madruga_vs_claude), Akita article |

#### S4. CODEOWNERS for AI instruction infrastructure
| Aspect | Detail |
|--------|--------|
| **Problem** | Any commit to `.claude/` merges without review. A broken knowledge file silently breaks 5+ skills. |
| **Fix** | Create `.github/CODEOWNERS`: `/.claude/ @gabrielhamu`, `/CLAUDE.md @gabrielhamu`. Enable "Require review from Code Owners" on main. |
| **Impact** | All AI instruction changes require review before merge. |
| **Effort** | 5min | **Source** | D1 (ai-instructions-as-infrastructure) |

#### S5. Security scan in CI
| Aspect | Detail |
|--------|--------|
| **Problem** | No automated check for secrets, dangerous patterns, or hardcoded credentials. |
| **Fix** | Add CI job that greps for `eval()`, `exec()`, `subprocess.call(shell=True)`, API keys, `.env` files in staged changes. |
| **Impact** | Low-cost safety net. RTK does this for every PR. |
| **Effort** | 30min | **Source** | RTK security scan, M16/I6 (madruga_vs_claude), Ref_tech_Guide layer 6 |

#### S6. Path security basics
| Aspect | Detail |
|--------|--------|
| **Problem** | Platform names not validated. `ensure_repo.py` runs `git clone` with unsanitized URLs. Path traversal via `../` possible. |
| **Fix** | Validate platform names against `^[a-z0-9-]+$`. Validate URLs against known patterns. Check for `..` in all user-provided paths. |
| **Impact** | Prevents injection via platform name or repo URL. |
| **Effort** | 1h | **Source** | M9 (madruga_vs_claude) |

---

### Tier A — Short Term (next 2-3 epics, 6-8h total, foundation hardening)

#### A1. Input validation with schemas (dataclasses)
| Aspect | Detail |
|--------|--------|
| **Problem** | Validation is ad-hoc: `if not yaml_path.exists()`, `if not raw_nodes`. A missing field in `platform.yaml` causes `KeyError` 3 nodes downstream. |
| **Fix** | Create dataclasses for `Node`, `PlatformConfig`, skill frontmatter. Validate at entry, fail early with clear messages. |
| **Impact** | Errors detected 10x earlier. Clear error messages instead of `KeyError: 'id'`. |
| **Effort** | 3h | **Source** | M1 (madruga_vs_claude), Claude Code uses Zod schemas for 100% of tools |

#### A2. Error hierarchy
| Aspect | Detail |
|--------|--------|
| **Problem** | Mix of `SystemExit(...)`, `log.error() + return 1`, `print("[error]")`. No structured error types. |
| **Fix** | Create `MadrugaError` → `PipelineError`, `ValidationError`, `DispatchError`. Use instead of SystemExit. |
| **Impact** | Tests can catch specific errors. `dag_executor.py` can decide retry vs abort by type. |
| **Effort** | 2h | **Source** | M2 (madruga_vs_claude), Claude Code error hierarchy (ClaudeError → 6 subtypes) |

#### A3. Graceful shutdown
| Aspect | Detail |
|--------|--------|
| **Problem** | Ctrl+C during `dag_executor.py` dispatch → orphan subprocess, no checkpoint saved, no resume hint. |
| **Fix** | Signal handler: terminate active subprocess → save checkpoint → print `--resume` command. |
| **Impact** | Clean interrupt handling. User knows how to resume. |
| **Effort** | 1h | **Source** | M8 (madruga_vs_claude), Claude Code 6-stage shutdown |

#### A4. CI gate for AI infrastructure changes
| Aspect | Detail |
|--------|--------|
| **Problem** | CODEOWNERS says WHO reviews. But nothing tells WHAT broke. Broken knowledge file references pass CI green. |
| **Fix** | New CI job `ai-infra`: detect changes to `.claude/`, run `skill-lint.py`, show impact analysis per changed knowledge file. Add `ai-infra` label. |
| **Impact** | CI fails on broken references. Reviewer sees exactly which skills are affected. |
| **Effort** | 1h | **Source** | D2+D3 (ai-instructions-as-infrastructure) |

#### A5. `skill-lint.py --impact-of`
| Aspect | Detail |
|--------|--------|
| **Problem** | "I changed `pipeline-contract-engineering.md`, what breaks?" requires manual grep. |
| **Fix** | New flag that builds knowledge→skill graph and prints affected skills + archetypes. ~40-50 lines. |
| **Impact** | CI can auto-show blast radius. Review becomes focused. |
| **Effort** | 1h | **Source** | D3 (ai-instructions-as-infrastructure) |

#### A6. Documentation-change matrix in CLAUDE.md
| Aspect | Detail |
|--------|--------|
| **Problem** | No documented mapping of "what changed → what docs to update". |
| **Fix** | Add matrix: new skill → update pipeline-dag-knowledge + CLAUDE.md; new script → update commands.md; new migration → update Active Technologies; new platform → update portal LikeC4Diagram.tsx. |
| **Impact** | Prevents drift. RTK does this rigorously. |
| **Effort** | 30min | **Source** | RTK documentation-change matrix |

---

### Tier B — Medium Term (3-5 epics, 12-16h total, consistency and DX)

#### B1. Split db.py (2,268 lines)
| Aspect | Detail |
|--------|--------|
| **Problem** | Largest file in codebase. Single responsibility violation — handles connections, migrations, pipeline CRUD, decisions, memory, FTS5, and observability. |
| **Fix** | Split: `db_core.py` (connection, migration, transaction) + `db_pipeline.py` (runs, nodes) + `db_decisions.py` (ADR, memory, FTS5) + `db_observability.py` (traces, evals). |
| **Impact** | Easier to test, review, and maintain. Prevents the "3,167-line function" problem that gave Claude Code 6.5/10. |
| **Effort** | 4h | **Source** | I3 (madruga_vs_claude), Akita article |

#### B2. Structured logging (JSON for CI, human for CLI)
| Aspect | Detail |
|--------|--------|
| **Problem** | Mix of `print("[ok]")`, `log.info()`, and raw `print()`. CI can't parse output without regex. |
| **Fix** | Standardize: `log.*()` for operations, `print()` only for final user output. Add `--json` flag for structured output. |
| **Impact** | CI gets machine-readable output. Errors have structured context. |
| **Effort** | 3h | **Source** | M6 (madruga_vs_claude), Claude Code dual output pattern |

#### B3. Memory consolidation (Dream-like)
| Aspect | Detail |
|--------|--------|
| **Problem** | Memories accumulate without pruning. No staleness detection. No contradiction detection. MEMORY.md grows unbounded. |
| **Fix** | Script that: detects contradictions, converts relative→absolute dates, prunes >90 day memories, keeps MEMORY.md <200 lines. Run as cron or post-session hook. |
| **Impact** | Memory stays useful over time. Same principle as Claude Code's Dream system. |
| **Effort** | 4h | **Source** | I1 (madruga_vs_claude), Claude Code Dream system (Orient→Gather→Consolidate→Prune) |

#### B4. Skill contract validation in linter
| Aspect | Detail |
|--------|--------|
| **Problem** | `skill-lint.py` validates frontmatter but not contract compliance (6 steps, output directory, gate declaration). |
| **Fix** | Add checks: references `pipeline-contract-base.md`? Has Step 0 Prerequisites? Has Output Directory? Gate type valid? |
| **Impact** | Prevents silent drift when someone edits a skill and removes a contract section. |
| **Effort** | 2h | **Source** | M7 (madruga_vs_claude) |

#### B5. Memoization for repeated operations
| Aspect | Detail |
|--------|--------|
| **Problem** | `_discover_platforms()` reads filesystem every call. `_check_fts5()` already uses memoization — pattern exists but isn't generalized. |
| **Fix** | Apply `functools.lru_cache` to `_discover_platforms()` and `platform.yaml` readers. Invalidate on `sync`/`new`. |
| **Impact** | `platform_cli.py status --all` reads filesystem once instead of N times. |
| **Effort** | 1h | **Source** | M5 (madruga_vs_claude), Claude Code 3 memoization strategies |

#### B6. Knowledge declarations in platform.yaml
| Aspect | Detail |
|--------|--------|
| **Problem** | Knowledge→skill dependencies inferred by grep (fragile). A refactored reference breaks silently. |
| **Fix** | Add `knowledge:` section to `platform.yaml` declaring which knowledge files each skill consumes. Cross-check in lint. |
| **Impact** | Dependencies become versionable, reviewable, lintable as first-class citizens. |
| **Effort** | 2h | **Source** | D4 (ai-instructions-as-infrastructure) |

#### B7. Governance files
| Aspect | Detail |
|--------|--------|
| **Problem** | No SECURITY.md (trust model, vulnerability policy), no CONTRIBUTING.md (PR rules, AI code policy), no PR template. |
| **Fix** | Create SECURITY.md (trust model, secret management, AI-specific rules), CONTRIBUTING.md (PR rules, commit conventions), `.github/pull_request_template.md`. |
| **Impact** | Defense-in-depth. 6-layer governance per Ref_tech_Guide (currently missing layers 2 and 5). |
| **Effort** | 3h | **Source** | Ref_tech_Guide layers 2+5, Claude Code security model |

---

### Tier C — Backlog (evaluate per-epic, long-term value)

| # | Improvement | Value | Effort | Source |
|---|-------------|-------|--------|--------|
| C1 | **Hallucination guard** — reject artifacts from zero-tool-call generations | High | 1h | GSD (IMPROVEMENTS I15) |
| C2 | **Pre-inline dependency artifacts** in skill prompts (save tool-call tokens) | High | 4h | GSD (IMPROVEMENTS I16) |
| C3 | **Cost tracking per skill/epic** — `pipeline_runs` already has columns, just need to populate | High | 2h | GSD (IMPROVEMENTS I17), M13 |
| C4 | **Wave-based parallel task execution** in speckit.implement | High | 1-2d | GSD (IMPROVEMENTS I20) |
| C5 | **Atomic git commits per task** (enables `git bisect`, individual revert) | High | 2h | GSD+Ralph Wiggum (IMPROVEMENTS I21) |
| C6 | **Fast lane** — `/quick-fix` for bugs (skip L1, compressed L2) | Medium | 4h | GSD (IMPROVEMENTS I22) |
| C7 | **Portal pipeline dashboard** — visual DAG with color-coded status | Medium | 8-12h | IMPROVEMENTS I1 |
| C8 | **Portal command palette** (Cmd+K) for quick navigation | Medium | 4h | IMPROVEMENTS I4c |
| C9 | **Race-to-resolve gates** — approve via Telegram + CLI | Medium | 4h | M11 (madruga_vs_claude) |
| C10 | **Multi-writer DB safety** — file-based lock for concurrent writes | Low | 4h | M14 (madruga_vs_claude) |
| C11 | **Session cache between pipeline nodes** — `--resume` + session ID | Medium | 6h | I4/M15 (madruga_vs_claude) |
| C12 | **Adaptive replanning** after each L2 epic | Medium | 4h | GSD (IMPROVEMENTS I18) |
| C13 | **Structured escalation** — P0/P1/P2 severity routing for auto-escalate | Low | 4h | Gas Town (IMPROVEMENTS I19) |
| C14 | **Developer onboarding script** — `make setup` validates all prereqs | Low | 2h | IMPROVEMENTS I23 |
| C15 | **DB migration testing** — fresh + upgrade path in CI | Medium | 3h | IMPROVEMENTS I11b |
| C16 | **Deferred knowledge loading** — reduce re-reading same files across skills | Medium | 4h | M10 (madruga_vs_claude) |

---

## Part 3 — Architecture Gaps (Vision vs Reality)

Comparing `madruga-ai-vision.md` (the target) with current implementation state.

| Vision Component | Status | Gap |
|-----------------|--------|-----|
| 24-skill pipeline (L1 13 + L2 11) | **Implemented** | All 31 skill files exist (22 madruga + 9 speckit) |
| SQLite state store | **Implemented** | 13+ tables, WAL, migrations, FTS5 |
| Easter (24/7 autonomous) | **Partial** | `easter.py` exists (528 LOC) but lives in madruga.ai, not consolidated from `general/services/madruga-ai/`. Engine (10K LOC + 10K tests) not yet migrated |
| LikeC4 architecture-as-code | **Implemented** | Model files, vision-build.py, AUTO markers |
| Portal Starlight | **Implemented** | Astro + Starlight + LikeC4 React, auto-discovery |
| Copier template | **Implemented** | Full scaffolding + `copier update` sync |
| Debate engine (multi-persona) | **Not migrated** | Exists in `general/services/madruga-ai/src/debate/` |
| Decision gates (1-way/2-way door) | **Implemented** | `decision_classifier.py` (136 LOC) |
| Telegram notifications | **Implemented** | `telegram_bot.py` (539 LOC), `telegram_adapter.py` (98 LOC) |
| Observability (traces, evals) | **In progress** | Epic 017 — migration 010, `eval_scorer.py`, `observability_export.py` |
| SpeckitBridge consolidation | **Not started** | Vision describes plug-and-play migration from general repo |
| Supabase/DB-first evolution | **Not started** | Vision proposes Supabase for cross-platform queries, real-time dashboard |
| RECONCILE feedback loop | **Implemented** | `reconcile.md` skill exists |

### Priority Assessment

1. **Engine consolidation** — Highest strategic value. Unlocks autonomous 24/7 operation. But large scope (10K LOC + 10K tests). Best treated as a dedicated epic.
2. **Observability** — Already in progress (epic 017). Complete it.
3. **Supabase migration** — Deferred. SQLite works well at current scale. Re-evaluate when >5 platforms or when portal needs real-time.

---

## Part 4 — Governance Maturity Assessment

Per the 6-layer model from `Ref_tech_Guide.md`:

| Layer | Description | Status | Gap |
|-------|-------------|--------|-----|
| 6 | **Automation** (scripts, CI, AST) | **Strong** | PostToolUse hooks, ruff, CI tests. Missing: security scan, detect-secrets. |
| 5 | **.github/** (CODEOWNERS, PR template, CI) | **Weak** | Only ci.yml exists. No CODEOWNERS, no PR template, no CodeQL. |
| 4 | **docs/** (architecture, security, threats) | **Partial** | Architecture docs exist in platforms/. No threat model, no testing strategy doc. |
| 3 | **.claude/rules/** (boundary contracts) | **Good** | 4 rules files with path-scoping. Could expand with API rules, test rules. |
| 2 | **Governance files** (SECURITY, CONTRIBUTING) | **Missing** | No SECURITY.md, no CONTRIBUTING.md. |
| 1 | **CLAUDE.md** (agent instructions) | **Excellent** | 93 lines, well-structured, includes gotchas, conventions, hooks. |

**Action**: Focus on layers 5 (CODEOWNERS + PR template) and 2 (SECURITY.md + CONTRIBUTING.md) — cheapest to add, biggest governance gap.

---

## Part 5 — Benchmark Synthesis

### What to adopt from each benchmark

| Benchmark | Key Takeaway | How to Adopt | Tier |
|-----------|-------------|--------------|------|
| **Claude Code CLI** | Fail-closed defaults, error hierarchy, Zod schemas, graceful shutdown | S2+A1+A2+A3 | S/A |
| **RTK** | TOML declarative filters, security scan CI, doc-change matrix, fail-safe fallback | S5+A6 | S/A |
| **GSD** | Hallucination guard, cost tracking, wave execution, adaptive replanning | C1+C3+C4+C12 | C |
| **BMAD** | 9 specialized agent roles, implementation tracks, MCP integration | Already have personas in contracts. Tracks → fast lane (C6). MCP → not needed yet. | C |
| **Gas Town** | Three-tier watchdog, structured escalation, refinery merge queue | C13 (escalation). Watchdog → already have circuit breaker. Refinery → overkill for solo dev. | C |
| **OpenClaw** | Dual memory model (audit log + curated), semantic snapshots | B3 (memory consolidation). Audit log → events table already exists. | B |

### What NOT to adopt

| Pattern | Why Skip |
|---------|----------|
| Gas Town's 20-30 parallel agents | Solo developer. Sequential epics are correct constraint. |
| BMAD's 9 formalized agent roles | Our persona-per-skill approach is simpler and works. |
| Claude Code's plugin marketplace | Overkill for internal tool. Skills are our plugins. |
| Supabase migration (now) | SQLite works. Re-evaluate at 5+ platforms. |
| MCP server integration | No external tools need real-time integration yet. |
| Feature flags (GrowthBook-style) | No need. Direct code changes are fine at our scale. |

---

## Part 6 — Team Review

### PM (Product Manager)
> **Verdict**: The roadmap correctly prioritizes infrastructure hardening over new features. The fast-lane idea (C6) should move up — it directly reduces time-to-fix for bugs, which is the most common workflow. The portal dashboard (C7) is nice but not critical until there are 3+ platforms.

### Business Owner
> **Verdict**: The engine consolidation from `general/services/madruga-ai/` is the single highest-value initiative. It turns madruga.ai from a documentation tool into an autonomous platform factory. Everything else is polish by comparison. However, don't block current epics waiting for consolidation — continue shipping on the current architecture.

### Software Engineer
> **Verdict**: Tier S items are all obvious fixes — any one of them could have caused a production issue. The db.py split (B1) is overdue but not urgent. The error hierarchy (A2) will pay dividends in every future debug session. Skip Supabase until SQLite becomes a bottleneck — WAL mode handles concurrent reads fine and we're nowhere near write contention limits.

### Data Engineer
> **Verdict**: Cost tracking (C3) is the sleeper hit. The `pipeline_runs` table already has `tokens_in`, `tokens_out`, `cost_usd` columns. Populating them is trivial but the insight is invaluable — which skills are expensive? Which need optimization? This should be Tier A, not C. Also, the observability work in epic 017 should export traces in OpenTelemetry format for future integration with external tools.

### QA Specialist
> **Verdict**: Hallucination guard (C1) is cheap and high-value — move to Tier A. Zero tool calls = fabricated output. Also missing: no test coverage for `vision-build.py` or `sync_memory.py` (from IMPROVEMENTS W8). The 23 test files are good but there are gaps in the build pipeline scripts. Pre-commit hooks with detect-secrets should be added to layer 6 governance.

### Security Expert
> **Verdict**: S5 (security scan) and S6 (path security) are non-negotiable minimums. Also critical: B7 (SECURITY.md) — without a documented trust model, security decisions are implicit and inconsistent. The `ensure_repo.py` git clone with unsanitized URLs is the most concerning finding. Add `.pre-commit-config.yaml` with detect-secrets, check-yaml, and shellcheck as layer 6 enforcement. CODEOWNERS (S4) is trivial and should be done today.

### Founder Leader
> **Verdict**: This document maps well to our principle: "Pragmatism > elegance. Automate on 3rd repetition. Bias for action." Execute Tier S in the next session — it's 4 hours for massive risk reduction. Tier A across the next 2-3 epics. Don't get trapped building infrastructure for hypothetical scale. The engine consolidation is the most important strategic move, but it's also the most complex — scope it as a proper epic with appetite, not a side project. The simple things that perform well: fail-closed defaults, context managers, circuit breakers. Ship those first.

---

## Part 7 — Execution Summary

### Do Now (Tier S — next session, 4h)
1. Context managers in dag_executor.py (S1)
2. Fail-closed gate validation (S2)
3. Circuit breaker on skill dispatch (S3)
4. Create CODEOWNERS (S4)
5. Security scan CI job (S5)
6. Path security validation (S6)

### Do Next (Tier A — next 2-3 epics, 8h)
1. Dataclass schemas for platform.yaml/Node (A1)
2. Error hierarchy (A2)
3. Graceful shutdown handler (A3)
4. AI infrastructure CI gate (A4)
5. `skill-lint.py --impact-of` (A5)
6. Documentation-change matrix (A6)

### Do Later (Tier B — 3-5 epics, 16h)
1. Split db.py (B1)
2. Structured logging (B2)
3. Memory consolidation (B3)
4. Skill contract validation in linter (B4)
5. Memoization (B5)
6. Knowledge declarations in platform.yaml (B6)
7. Governance files — SECURITY.md, CONTRIBUTING.md (B7)

### Evaluate Per-Epic (Tier C — backlog)
Cost tracking (C3), hallucination guard (C1), wave execution (C4), atomic commits (C5), fast lane (C6) — pick based on epic needs.

### Strategic Initiative (separate epic)
Engine consolidation from `general/services/madruga-ai/` — the multiplier that enables autonomous 24/7 operation.

---

> **Guiding principle from Claude Code**: *"Fail-closed defaults. Deny always wins. Defense in depth."*
>
> **From RTK**: *"Every filter has a fallback to raw output — never block the user."*
>
> **From GSD**: *"A task must fit in one context window. If it cannot, it is two tasks."*
>
> **Translated for madruga.ai**: Validate inputs at entry, close resources in finally, treat unknown gates as human, never trust string concatenation for paths, treat memory as hint not truth, and keep it simple — simple performs well.
