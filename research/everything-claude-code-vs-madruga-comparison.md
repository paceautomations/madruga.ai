# everything-claude-code vs madruga.ai -- Comparative Analysis

> **Date**: 2026-04-14
> **Purpose**: Identify improvement opportunities by comparing two Claude Code harness systems

---

## 1. Executive Summary

Both ECC and madruga.ai optimize Claude Code usage, but at different levels of the stack:

- **ECC**: **Breadth-first plugin ecosystem** -- 181 skills, 47 agents, 14 language rule sets. Optimizes the individual developer experience with self-learning instincts, fact-forcing gates, model routing, and cross-harness portability. Think "vim plugins for Claude Code."
- **madruga.ai**: **Depth-first orchestration system** -- 25-skill DAG pipeline with gates, retry, cost tracking, and a 24/7 daemon. Optimizes multi-step architectural documentation workflows end-to-end. Think "CI/CD for software architecture."

ECC has more components; madruga.ai has deeper orchestration. The comparison reveals concrete opportunities for both sides.

---

## 2. Comparison Matrix

| Dimension | ECC | madruga.ai | Winner |
|-----------|-----|------------|--------|
| **Pipeline orchestration** | Informal (tmux, bash, sequential) | 25-node DAG, topological sort, 4 gate types, checkpoint/resume | **madruga.ai** (by far) |
| **Skill/agent catalog** | 181 skills + 47 agents + 79 commands | 25 skills + 4 layer personas | **ECC** (7x more) |
| **Hook system** | 17 event types, profile-gated, Node.js scripts | 4 PostToolUse shell hooks | **ECC** (richer) |
| **Memory persistence** | Session files + instincts + context keeper | Markdown files + SQLite bidirectional sync | **Tie** (different strengths) |
| **Self-learning** | Instinct system with confidence scoring, decay, evolution to skills | None | **ECC** |
| **Prompt caching** | Not addressed | Prefix cache ordering (Phase 5), context scoping, session resume caps | **madruga.ai** |
| **Cost tracking** | Per-session hook, no aggregation | Per-dispatch USD estimation, trend analysis in DB, cache metrics | **madruga.ai** |
| **Retry/resilience** | None | Exponential backoff, 3-class circuit breaker, zombie sweep | **madruga.ai** |
| **Quality gates** | GateGuard (+2.25 A/B tested), verification loop, TDD workflow | Judge (4 personas), QA (4 layers), auto-review checklist | **Tie** (ECC measured; madruga deeper) |
| **Security** | Supply chain awareness, CVE citations, secrets scanning, enterprise governance | Tool restrictions per node, placement validation, skill-lint | **ECC** |
| **Multi-agent patterns** | dmux, Santa Loop, GAN triad, multi-plan, devfleet | Isolated subprocess dispatch, no inter-agent messaging | **ECC** |
| **Configuration** | Install profiles + identity.json + hook profiles | pipeline.yaml + platform.yaml + env kill-switches | **Tie** (different philosophies) |
| **Cross-platform** | 7+ AI agent platforms (Codex, Cursor, Gemini, Kiro, etc.) | Claude Code only | **ECC** |
| **Context optimization** | Lazy loading, MCP audit, strategic compaction, token budget advisor | Scoped context, prefix ordering, context windowing | **Tie** (complementary) |
| **Observability** | Eval harness, session tracking, monthly metrics | Trace/span model, structlog, portal API, Telegram alerts, 90-day retention | **madruga.ai** |
| **Skill contract** | No uniform structure. Quality varies. | Uniform 6-section contract, frontmatter handoffs, skill-lint CI | **madruga.ai** |
| **Declarative config** | Code-first (bash, Node.js) | YAML pipeline.yaml, platform.yaml | **madruga.ai** |
| **Community** | 155k stars, 170+ contributors | Private/internal | **ECC** |
| **Daemon/24x7** | ecc2/ (alpha, Rust) | easter.py (production, Python + systemd) | **madruga.ai** |
| **Model routing** | Haiku/Sonnet/Opus by task complexity | Single model per dispatch (configurable) | **ECC** |

---

## 3. What ECC Does Better

### 3.1 Instinct System / Self-Learning (HIGH PRIORITY)

**Gap in madruga.ai**: No mechanism to learn from past sessions. Memory is explicit (user writes it) or hook-synced (file changes), but there's no pattern extraction from behavior.

**What ECC offers**:
- YAML-based behavioral triggers with confidence scores (0.0-1.0)
- PreToolUse/PostToolUse observation hooks capture every tool event
- Patterns extracted at session end with confidence scoring
- Threshold (0.7) gates injection into new sessions
- Confidence decay for unused instincts
- Evolution: instinct clusters at >= 80% become skills/commands/agents

**Opportunity**: Implement a lightweight instinct system for the madruga.ai pipeline. After each epic cycle, extract patterns like "specs for API epics always need X clarification" or "judge always flags Y in Python code" and inject these as pre-context for future epics. The infrastructure already exists (memory sync hooks + SQLite), just needs the extraction + confidence logic.

### 3.2 Hook Diversity (HIGH PRIORITY)

**Gap in madruga.ai**: Only 4 PostToolUse hooks. No PreToolUse gates, no SessionStart/End lifecycle, no Stop hooks, no SubagentStart/Stop events.

**What ECC offers**:
- **PreToolUse** gates: block destructive operations, force investigation before edits, secrets scanning
- **SessionStart**: Load previous context, environment detection
- **Stop**: Format/lint edited files, session persistence, cost tracking
- **PreCompact**: Save state before context loss
- **Profile gating**: Same hooks.json at different strictness levels

**Opportunity for madruga.ai**:
1. **PreToolUse gate for dispatched skills**: Before implement writes code, force it to read the spec section relevant to the task (GateGuard-like fact-forcing)
2. **SessionStart hook**: Auto-detect active platform and epic, inject relevant context
3. **Stop hook**: Auto-format/lint after each response, track per-response cost
4. **PreCompact**: Persist critical state (decisions.md, current task progress) before compaction

### 3.3 GateGuard / Fact-Forcing (HIGH PRIORITY)

**Gap in madruga.ai**: Skills have auto-review checklists but no mechanism to force the agent to investigate before acting. The implement skill can start writing code without verifying it read the relevant spec.

**What ECC offers**:
- DENY first edit, FORCE investigation (grep importers, read schemas, quote instruction), then ALLOW
- A/B tested: +2.25 improvement score
- Applies to Edit/Write/destructive Bash

**Opportunity**: Implement a fact-forcing PreToolUse hook for the implement dispatch. Before the first Edit/Write in a task, require the agent to have Read the spec section, plan section, and data-model section relevant to the current task. This could reduce "hallucinated implementations" significantly.

### 3.4 Multi-Agent Patterns (MEDIUM PRIORITY)

**Gap in madruga.ai**: Skills run as isolated subprocesses. No inter-skill communication, no parallel review patterns, no model diversity for quality.

**What ECC offers**:
- **Santa Loop**: Two different models must both approve (model diversity as quality gate)
- **GAN Triad**: Separate planner/generator/evaluator personas
- **dmux**: tmux-based parallel dispatch with worktree isolation
- **De-Sloppify**: Separate cleanup pass after generation

**Opportunity**:
1. **Santa Loop for Judge**: Run Judge with two different model configs (Opus + Sonnet, or same model with different temperatures). Both must pass.
2. **De-Sloppify as explicit post-implement step**: Instead of relying on `/simplify` hook, make it a pipeline node.

### 3.5 Model Routing (MEDIUM PRIORITY)

**Gap in madruga.ai**: Single model per dispatch. `dag_executor.py` doesn't route by task complexity.

**What ECC offers**:
- Haiku for mechanical/frequent tasks (3x savings)
- Sonnet for main implementation
- Opus for architecture, security, ambiguity
- Budget parameter (low/med/high)

**Opportunity**: Route by pipeline node:
- `specify`, `plan`, `judge`: Opus (high reasoning)
- `implement`: Sonnet (balanced cost/quality)
- `analyze`, `reconcile`: Haiku (mechanical checks)

Estimated savings: 30-50% on total pipeline cost per epic.

### 3.6 Security Hardening (MEDIUM PRIORITY)

**Gap in madruga.ai**: Tool restrictions per node but no secrets scanning, no config protection, no supply chain awareness for skills.

**What ECC offers**:
- Pre-commit secrets scanning (OpenAI keys, GitHub PATs, AWS keys, private key blocks)
- Config protection: blocks edits to linter/formatter configs
- `block-no-verify`: prevents bypassing git hooks
- Governance capture: audit trail for elevated privilege usage
- Supply chain: 36% of public skills contain prompt injection (Snyk study)

**Opportunity**:
1. **Secrets scanning hook**: Add PreToolUse hook on Bash/Write that scans for credential patterns
2. **Config protection**: Block implement from editing `.claude/settings.json`, `pyproject.toml`, `ruff.toml`
3. **Skill supply chain**: skill-lint should scan for prompt injection patterns in contributed skills

### 3.7 Strategic Compaction (LOW PRIORITY)

**Gap in madruga.ai**: No explicit compaction strategy. Dispatched sessions rely on `MADRUGA_RESUME_MAX_TOKENS` cap but no guidance on when to compact.

**What ECC offers**:
- Manual `/compact` at logical boundaries
- `suggest-compact.js` hook at configurable tool-call thresholds
- Clear rules: after exploration before execution, after milestones, never mid-implementation

**Opportunity**: Add a `suggest-compact` Stop hook for interactive sessions (not dispatched ones). Particularly useful during manual epic-context and specify sessions.

---

## 4. What madruga.ai Does Better

### 4.1 DAG Orchestration (ECC's biggest gap)

**madruga.ai advantage**: Full 25-node DAG with:
- Topological sort and dependency tracking
- 4 gate types (human / auto / 1-way-door / auto-escalate)
- Checkpoint/resume from any node
- Phase dispatch (grouping tasks by `## Phase N:` headers)
- Retry with exponential backoff and circuit breaker
- Zombie sweep for orphaned dispatches

**ECC limitation**: No pipeline abstraction. Orchestration is informal (tmux commands, bash scripts, manual chaining). `devfleet` has a task DAG concept but it's a single command, not a framework.

**Impact**: ECC cannot express "run 12 skills in dependency order, pause at 3 for human approval, retry on failure, and resume from checkpoint." This is madruga.ai's defining capability.

### 4.2 Declarative Pipeline Definition

**madruga.ai advantage**: `pipeline.yaml` (193 lines) defines the entire 25-node DAG declaratively -- nodes, dependencies, gates, layers, optionality. Any change to the pipeline is a YAML edit, version-controlled and auditable.

**ECC limitation**: Pipeline behavior is scattered across bash scripts, command files, and hook configurations. No single source of truth for workflow ordering.

### 4.3 Prompt Caching / Prefix Ordering (Phase 5)

**madruga.ai advantage**: `MADRUGA_CACHE_ORDERED=1` reorders prompt sections to maximize Claude API's 1-hour TTL prefix cache. Stable context (spec, plan, data model, contracts) is force-included at the START. Variable context (task card, progress) goes at the END. Empirically tracks `cache_read_input_tokens` vs. `cache_creation_input_tokens`.

**ECC limitation**: No prompt caching awareness. The `context-budget` skill audits token overhead but doesn't optimize prompt structure for cache hits.

**Impact**: For multi-task epics, madruga.ai gets significant cache hits on tasks 2..N. ECC pays full price every time.

### 4.4 Cost Aggregation and Trend Analysis

**madruga.ai advantage**: Full cost pipeline:
- Per-dispatch token metrics (input, output, cache_read, cache_creation)
- USD estimation via configurable pricing tiers
- Stored in `pipeline_runs` table for historical analysis
- Portal API for visualization
- Cross-epic trend comparison

**ECC limitation**: `cost-tracker.js` Stop hook tracks per-session metrics but no aggregation, no USD estimation, no trend analysis.

### 4.5 Retry and Resilience

**madruga.ai advantage**: `dispatch_with_retry_async` with:
- Exponential backoff (10s, 30s, 90s)
- 3-class error classification (deterministic, transient, unknown)
- Different retry limits per class (deterministic: 2, transient: full cycle, unknown: 3)
- Zombie sweep for orphaned dispatches
- Escalation to human on circuit break

**ECC limitation**: Zero retry at any level. If a dispatch fails, manual intervention is required.

### 4.6 Skill Contract and Validation

**madruga.ai advantage**: Every skill follows a uniform 6-section contract:
1. Cardinal Rule (negative constraint)
2. Persona (expertise)
3. Usage
4. Output Directory
5. Instructions (6 sub-steps: prerequisites, collect context, generate, auto-review, approval gate, save)
6. Handoffs (machine-readable frontmatter)

`skill-lint.py` validates: frontmatter, handoff chains, archetype compliance, dedup. CI validates on every edit.

**ECC limitation**: 181 skills with no enforced structure. Some are 10 lines, others 500+. No uniform contract, no machine-readable handoffs, no CI validation of skill quality (only structural validation).

### 4.7 Operational Maturity (24/7 Daemon)

**madruga.ai advantage**:
- `easter.py`: Production daemon with systemd integration, health checks, degradation modes
- Telegram alerting for gates, errors, epic status
- 90-day data retention with backup rotation
- Portal with trace/span visualization
- Sequential invariant enforcement (1 epic per platform)

**ECC limitation**: `ecc2/` (Rust control plane) is alpha. No production daemon, no alerting, no retention policy.

### 4.8 Scoped Context Filtering

**madruga.ai advantage**: `MADRUGA_SCOPED_CONTEXT=1` filters spec/plan to only the sections relevant to the current task. If implementing "user authentication," the prompt includes only the auth sections of the spec, not the entire document.

**ECC limitation**: No content-aware context filtering. The `context-budget` skill audits overhead but doesn't selectively include/exclude content.

---

## 5. What's Similar

| Aspect | ECC | madruga.ai |
|--------|-----|------------|
| **Personas** | 47 agent definitions with role constraints | 4 layer personas (Business, Research, Engineering, Planning) |
| **Tool restrictions** | Hook-based blocking + agent frontmatter `tools` | Per-node `--tools` in dispatch command |
| **Quality gates** | GateGuard, verification loop, TDD | Judge (4 personas), QA (4 layers), auto-review |
| **De-sloppify / simplify** | Separate cleanup pass after generation | `/simplify` hook on 3+ file implementations |
| **Env var kill-switches** | `ECC_HOOK_PROFILE`, `ECC_DISABLED_HOOKS`, `ECC_GOVERNANCE_CAPTURE` | `MADRUGA_BARE_LITE`, `MADRUGA_CACHE_ORDERED`, `MADRUGA_SCOPED_CONTEXT`, etc. |
| **Session state** | `.tmp` session files with metadata | SQLite `pipeline_runs` + checkpoint/resume |
| **Config protection** | Blocks edits to linter/formatter configs | `hook_validate_placement.py` prevents cross-repo writes |
| **Conventional commits** | Instinct-enforced at 0.9 confidence | CLAUDE.md mandates prefixes (feat:, fix:, chore:) |
| **CLAUDE.md as index** | Modular `~/.claude/rules/*.md` | Modular `.claude/knowledge/*.md` |

---

## 6. Prioritized Improvement Opportunities for madruga.ai

### TIER 1 -- High Impact, Actionable Now

| # | Opportunity | Source | Effort | Expected Impact |
|---|-----------|--------|--------|----------------|
| 1 | **Fact-forcing PreToolUse hook for implement** | GateGuard pattern | Small | Reduce hallucinated implementations. Force agent to read spec/plan/data-model before first Edit. |
| 2 | **Model routing by pipeline node** | ECC model-route | Small | 30-50% cost reduction. Opus for plan/judge, Sonnet for implement, Haiku for analyze/reconcile. |
| 3 | **SessionStart hook with context injection** | ECC session bootstrap | Small | Auto-detect active platform/epic, inject relevant context on session start. Reduce manual orientation. |
| 4 | **Secrets scanning PreToolUse hook** | ECC pre-commit quality | Small | Prevent accidental credential commits during implement dispatch. |

### TIER 2 -- High Impact, Requires Design

| # | Opportunity | Source | Effort | Expected Impact |
|---|-----------|--------|--------|----------------|
| 5 | **Instinct system for pipeline learning** | ECC instincts v2 | Medium | Extract patterns from epic cycles. "Specs for API epics need X." Confidence-scored, decaying, evolvable. |
| 6 | **Hook profile system** | ECC hook profiles | Medium | `MADRUGA_HOOK_PROFILE=minimal|standard|strict`. Same hooks config at different strictness for dev vs dispatch vs CI. |
| 7 | **Stop hook for auto-format/lint** | ECC quality-gate.js | Small | Auto-run ruff after every response touching Python files. Currently requires manual `/simplify`. |
| 8 | **PreCompact state preservation** | ECC pre-compact.js | Small | Before compaction, persist decisions.md, current task progress, and test state to files. |

### TIER 3 -- Medium Impact, Future Consideration

| # | Opportunity | Source | Effort | Expected Impact |
|---|-----------|--------|--------|----------------|
| 9 | **Santa Loop for Judge** | ECC Santa Loop | Medium | Two model configs must both approve. Model diversity as quality gate for irreversible architecture decisions. |
| 10 | **Eval harness with regression tracking** | ECC eval-harness | Medium | Track Judge scores over time. Alert on regression. `pass@k` and `pass^k` metrics. |
| 11 | **Config protection hook** | ECC config-protection | Small | Block implement from editing pipeline.yaml, settings.json, pyproject.toml during dispatch. |
| 12 | **Cross-session context keeper** | ECC ck skill | Medium | Structured JSON per epic with `/ck:save` and `/ck:resume` for complex epics spanning multiple sessions. |

---

## 7. What madruga.ai Should NOT Copy from ECC

| Aspect | Why not |
|--------|---------|
| **181 skills without uniform contract** | madruga.ai's 6-section contract with skill-lint validation is superior. Quality > quantity. |
| **Code-first orchestration** | madruga.ai's declarative pipeline.yaml is more auditable and version-controllable. |
| **tmux-based parallelism** | madruga.ai's phase dispatch with DAG executor is more robust than manual tmux panes. |
| **Cross-harness portability** | madruga.ai is purpose-built for Claude Code. Supporting 7 platforms dilutes focus. |
| **Commands as legacy shims** | madruga.ai should keep skills as the primary abstraction, not accumulate legacy layers. |
| **No retry/resilience** | madruga.ai's circuit breaker is a strength. Never regress. |
| **Session .tmp files** | madruga.ai's SQLite WAL mode with proper schema is more reliable than ad-hoc tmp files. |

---

## 8. Conclusion

**ECC excels at the developer experience layer** -- making each individual Claude Code session smarter through instincts, fact-forcing, model routing, and a massive skill library. It's a "developer toolkit."

**madruga.ai excels at the orchestration layer** -- making multi-step workflows reliable through DAG pipelines, gates, retry, cost tracking, and a production daemon. It's a "workflow engine."

The highest-value improvements for madruga.ai from ECC are:

1. **Fact-forcing hooks** (GateGuard pattern) -- small effort, immediately measurable impact on implementation quality
2. **Model routing by node** -- small effort, 30-50% cost reduction
3. **Instinct system** -- medium effort, enables pipeline learning across epic cycles
4. **Hook lifecycle expansion** -- PreToolUse, SessionStart, Stop, PreCompact events

These improvements strengthen madruga.ai's developer experience without compromising its orchestration strengths. The pipeline DAG, prompt caching, retry resilience, and skill contracts remain clear advantages that ECC lacks.

### Cross-Reference with AgentScope Findings

Comparing all three systems:

| Capability | AgentScope | ECC | madruga.ai |
|-----------|-----------|-----|------------|
| Memory (semantic) | Best (Mem0/ReMe) | Good (instincts) | Basic (file sync) |
| Orchestration | Worst (seq/fanout only) | Medium (informal) | Best (DAG + gates) |
| Hooks | Good (metaclass AOP) | Best (17 events, profiles) | Basic (4 PostToolUse) |
| Cost optimization | Basic (compression only) | Good (model routing) | Best (prefix cache + scoping) |
| Resilience | None | None | Best (circuit breaker) |
| Multi-agent | Best (MsgHub, A2A) | Good (dmux, Santa Loop) | Basic (isolated dispatch) |
| Skill quality | N/A (code classes) | Low (no contract) | Best (uniform contract + lint) |
| Self-learning | None | Best (instincts) | None |
| Security | Basic | Best (CVEs, governance) | Good (restrictions) |
| Observability | Good (OTel) | Basic (session tracking) | Best (trace/span + daemon) |

The three-way comparison reinforces that madruga.ai's highest-value imports are:
- **From AgentScope**: Semantic memory for cross-epic learning
- **From ECC**: Fact-forcing hooks, model routing, instinct-based self-learning
