# everything-claude-code -- Architecture Analysis

> **Repository**: [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code)
> **Stars**: 155k+ | **Forks**: 24k+ | **Contributors**: 170+
> **Origin**: Anthropic Hackathon winner, now the de facto Claude Code plugin ecosystem
> **License**: MIT | **Last push**: 2026-04-13
> **Date**: 2026-04-14

---

## 1. Overview

everything-claude-code (ECC) is a **distributable harness performance optimization system** for Claude Code. It is not a single project configuration -- it's a plugin ecosystem providing 181 skills, 47 agents, 79 commands, language-partitioned rules, profile-gated hooks, and a self-improving instinct system. It also supports 7+ AI agent platforms (Claude Code, Codex, Cursor, OpenCode, Gemini, Kiro, Trae).

### Scale

| Component | Count |
|-----------|-------|
| Skills | 181 |
| Agents | 47 |
| Commands | 79 |
| Hook event types | 17 supported, 7 actively used |
| Language rule sets | 14 |
| MCP server configs | 24 |
| Example CLAUDE.md templates | 6+ |
| Total files | 2,642 |

---

## 2. Architecture and Configuration

### 2.1 Project Structure

```
everything-claude-code/
  agents/          # 47 specialized subagent definitions (.md + YAML frontmatter)
  skills/          # 181 skills, each in skills/<name>/SKILL.md
  commands/        # 79 legacy slash-command shims (migrating to skills)
  hooks/           # hooks.json (31KB) + Node.js hook scripts
  rules/           # Language-partitioned: common/, typescript/, python/, go/, etc.
  examples/        # Template CLAUDE.md files for different project types
  mcp-configs/     # 24 MCP server configurations
  manifests/       # Install profiles (full/minimal/standard/strict)
  schemas/         # JSON schemas for validation
  scripts/         # CI validators, hook runtime, install scripts
  contexts/        # Contextual instruction sets (review, planning)
  plugins/         # Plugin system infrastructure
  ecc2/            # Rust-based control-plane prototype (alpha)
  .claude/         # Identity, team, enterprise, homunculus (instincts)
```

### 2.2 Configuration System

- **Install profiles**: `full`, `minimal`, `standard`, `strict` via `./install.sh --profile <name>` or per-language `./install.sh typescript`
- **Identity.json**: Auto-generated user profile (`technicalLevel`, `preferredStyle`, `domains`) that personalizes agent behavior per developer
- **Hook profiles**: `ECC_HOOK_PROFILE=minimal|standard|strict` controls which hooks fire. Individual hooks disabled via `ECC_DISABLED_HOOKS=id1,id2`
- **Manifest-driven**: `install-profiles.json` + `install-components.json` + `install-modules.json` enable incremental updates and per-team customization
- **Cross-harness portability**: Same repo installs into Claude Code, Codex (`.codex/`), Cursor (`.cursor/`), OpenCode (`.opencode/`), Gemini (`.gemini/`), Kiro (`.kiro/`), Trae (`.trae/`)

### 2.3 CLAUDE.md Organization

Three-tier pattern:
- **User-level** (`~/.claude/CLAUDE.md`): Personal preferences, agent roster, modular rule references
- **Project-level** (repo root): Project overview, architecture, test commands, file structure
- **Stack-specific templates**: SaaS Next.js, Django API, Go microservice, Rust API, Laravel, GAN harness

Key insight: CLAUDE.md chain should stay under ~300 lines. Use modular `~/.claude/rules/*.md` files instead of inlining.

---

## 3. Hook System

### 3.1 Event Types

17 supported event types (validated by CI):

| Event | Hooks | Purpose |
|-------|-------|---------|
| **PreToolUse** | 12 | Gate/block/warn before tool execution |
| **PostToolUse** | 8 | Audit, quality checks, tracking after execution |
| **PostToolUseFailure** | 1 | MCP health tracking on failed tool calls |
| **Stop** | 5 | Format, cleanup, session state, cost tracking, desktop notify |
| **PreCompact** | 1 | Save state before context compaction |
| **SessionStart** | 1 | Load previous context, detect package manager |
| **SessionEnd** | 1 | Lifecycle marker and cleanup |

Additionally supported but not all actively used: `UserPromptSubmit`, `PermissionRequest`, `Notification`, `SubagentStart`, `SubagentStop`, `InstructionsLoaded`, `TeammateIdle`, `TaskCompleted`, `ConfigChange`, `WorktreeCreate`, `WorktreeRemove`.

### 3.2 Profile-Gated Execution

Central dispatcher `run-with-flags.js` gates every hook through the profile system. Hooks self-declare which profiles they run under. Optimizes by `require()`-ing hooks that export `run()` directly (saving ~50-100ms per hook vs spawning a child process).

### 3.3 Notable Hook Implementations

| Hook | Type | What it does |
|------|------|-------------|
| **quality-gate.js** | PostToolUse | Polyglot formatter: Biome/Prettier for JS/TS, gofmt, ruff |
| **pre-bash-commit-quality.js** | PreToolUse | Scans for console.log, debugger, secrets, validates conventional commits |
| **config-protection.js** | PreToolUse | Blocks edits to ~30 linter/formatter config files |
| **gateguard-fact-force.js** | PreToolUse | Forces investigation before first edit per file |
| **block-no-verify.js** | PreToolUse | Prevents `--no-verify` on git commands |
| **governance-capture.js** | PostToolUse | Detects secrets, policy violations, elevated privileges |
| **mcp-health-check.js** | PreToolUse | Monitors MCP server health, blocks unhealthy calls |
| **session-start-bootstrap.js** | SessionStart | Loads previous session context + instincts |
| **cost-tracker.js** | Stop | Tracks token/cost metrics per session |
| **suggest-compact.js** | Stop | Suggests `/compact` after configurable tool-call threshold |

### 3.4 CI Validation

7 validators in `scripts/ci/`:
- `validate-hooks.js` -- JSON schema validation against `schemas/hooks.schema.json`
- `validate-agents.js`, `validate-commands.js`, `validate-rules.js`, `validate-skills.js`
- `check-unicode-safety.js` -- Detects Unicode bidirectional override attacks
- `validate-workflow-security.js` -- Validates GitHub Actions workflow security

---

## 4. Memory and Context Management

### 4.1 Session Persistence (3-Hook Lifecycle)

1. **SessionStart**: Load most recent session summary from `~/.claude/sessions/`. Matches by worktree path > project name > recency. Also injects learned "instincts"
2. **PreCompact**: Logs compaction event, annotates session file with compaction marker
3. **Stop/SessionEnd**: Parses JSONL transcript, extracts user messages/tools/files, writes structured `.tmp` session file

Session files have 7-day active window, 30-day retention (configurable via `ECC_SESSION_RETENTION_DAYS`). Auto-pruning of expired sessions on start.

### 4.2 Instinct System (Continuous Learning v2)

The most novel memory pattern in the repo. Located in `.claude/homunculus/instincts/`:

- **Format**: YAML with `id`, `trigger`, `confidence` (0.0-1.0), `domain`, `source`
- **Learning**: PreToolUse/PostToolUse observation hooks capture every tool use event. At session end, patterns are extracted with confidence scores
- **Threshold**: Only instincts at >= 0.7 confidence are injected into new sessions
- **Evolution**: When instinct clusters reach >= 80% confidence, they "evolve" via `/evolve` into reusable skills, commands, or agents
- **Decay**: Unused instincts lose confidence over time

This is a **self-improving system** -- the harness learns from developer behavior and promotes patterns to first-class skills.

### 4.3 Context Keeper (ck)

Community-contributed per-project memory:
- `context.json` per project in `~/.claude/ck/contexts/<name>/`
- Commands: `/ck:save` (LLM-analyzed session state), `/ck:resume` (full briefing), `/ck:init`
- SessionStart hook injects ~100 tokens of compact context

### 4.4 Context Window Optimization

Key strategies documented:
- **Replace MCPs with CLI-backed skills**: MCPs eat context (~500 tokens per tool schema). A 30-tool MCP server costs more than all skills combined
- **Trigger-table lazy loading**: Map keywords to skill paths. Skills load only when triggered, reducing baseline context by 50%+
- **Strategic compaction**: Manual `/compact` at logical boundaries (after exploration before execution, after milestones, before context shifts). Never mid-implementation
- **Token budget advisor**: Choose response depth (25%/50%/75%/100%). Heuristic: `words x 1.3` for prose, `chars / 4` for code
- **Dynamic system prompt injection**: `claude --system-prompt "$(cat memory.md)"` with context-specific aliases
- **CLAUDE.md under 300 lines**: Everything counts when it's always loaded

---

## 5. Agents and Skills

### 5.1 Agent Archetypes (47 agents)

| Archetype | Examples | Pattern |
|-----------|----------|---------|
| **Planner** | `planner.md` | 4-phase: requirements, architecture review, step breakdown, implementation order. Never writes code. |
| **Language Reviewers** | `python-reviewer`, `go-reviewer`, `rust-reviewer`, etc. | Severity-tiered (CRITICAL/HIGH/MEDIUM/LOW), >80% confidence threshold |
| **Build Resolvers** | `build-error-resolver`, `go-build-resolver`, `java-build-resolver` | Minimal-diff-only philosophy. Fix errors without architecture changes. |
| **GAN Triad** | `gan-planner`, `gan-generator`, `gan-evaluator` | Generate-then-evaluate loop. "The reviewer should never be the author." |
| **Security** | `security-reviewer.md` | Pre-deployment 17-item checklist. Cites real CVEs. |
| **Performance** | `performance-optimizer.md` | Web Vitals targets, algorithmic complexity lookup table |

### 5.2 Skill Catalog Highlights (181 skills)

| Domain | Notable Skills |
|--------|---------------|
| **Orchestration** | `autonomous-loops`, `autonomous-agent-harness`, `devfleet` |
| **Quality** | `tdd-workflow`, `verification-loop`, `gateguard`, `safety-guard` |
| **Context** | `strategic-compact`, `context-budget`, `token-budget-advisor`, `ck` |
| **Learning** | `continuous-learning`, `continuous-learning-v2`, `eval-harness` |
| **Security** | `security-review`, `security-guard` |
| **Frameworks** | Django, Laravel, Spring Boot, NestJS, SwiftUI, etc. |
| **Research** | `deep-research`, `tech-radar` |

### 5.3 Skill Structure

Each skill lives in `skills/<name>/SKILL.md`. Format is Markdown with instructions, examples, and constraints. No standardized frontmatter contract (unlike madruga.ai's uniform 6-section structure).

---

## 6. Multi-Agent Orchestration

### 6.1 Patterns

| Pattern | Mechanism | Description |
|---------|-----------|-------------|
| **Sequential Pipeline** | `claude -p` chained steps | Output of one feeds next |
| **dmux Parallel Dispatch** | tmux panes + worktrees | Independent sessions per pane, cap 5-6 |
| **Infinite Agentic Loop** | Two-prompt system | Deploying parallel sub-agents continuously |
| **Continuous PR Loop** | Create PR, wait CI, auto-merge | Autonomous shipping |
| **Santa Loop** | Dual-independent-reviewer | Two different models must both approve. No shared context prevents anchoring. |
| **multi-plan** | External model dispatch | Codex backend + Gemini frontend, zero write access for externals |
| **RFC-Driven DAG** | Spec decomposition | Dependency graph, parallel implementation, merge coordination |
| **GAN Triad** | Planner/Generator/Evaluator | Generate-then-evaluate with separate personas |
| **De-Sloppify** | Separate cleanup pass | Post-generation cleanup instead of negative instructions |

### 6.2 Key Principles

- "The reviewer should never be the author" -- eliminates author bias
- External models get **zero filesystem write access** -- only Claude modifies code
- Fresh reviewer instances each round to prevent anchoring bias
- Model diversity (different training data, different biases) as a quality gate

---

## 7. Quality Assurance

### 7.1 GateGuard (Fact-Forcing Pre-Action Gate)

Three-stage gate:
1. **DENY** the first edit attempt
2. **FORCE** investigation: grep importers, read schemas, quote user instruction
3. **ALLOW** only after facts presented

Measurably improves output by **+2.25 points** vs ungated agents (A/B tested).

### 7.2 Verification Loop

6-phase sequential chain before PR:
1. Build
2. Type check
3. Lint
4. Test suite (80% coverage minimum)
5. Security scan (secrets, console.log)
6. Diff review

### 7.3 TDD Workflow

Strict RED-GREEN-REFACTOR with git checkpoints:
- Tests BEFORE code (RED gate requires verified failing test)
- Git checkpoint commits at each TDD stage
- 80% coverage minimum (branches, functions, lines, statements)
- Three layers: unit, integration, E2E (Playwright)
- Eval-driven TDD addendum: capability + regression evals before implementation

### 7.4 Safety Guard

Three modes:
- **Careful**: Intercept destructive commands
- **Freeze**: Lock edits to a directory
- **Guard**: Both

Blocks: `rm -rf`, `git push --force`, `git reset --hard`, `DROP TABLE`, `chmod 777`, `--no-verify`

---

## 8. Security

### 8.1 Supply Chain Awareness

Cites Snyk study: **36% of 3,984 public skills contain prompt injection**. Treats skills as supply chain artifacts requiring audit.

### 8.2 Practices

- Real CVE references (CVE-2025-59536, CVE-2026-21852)
- Sandboxing: containers with `--network=none`, `internal: true` Docker networks
- Identity separation: dedicated bot accounts, never personal credentials
- Tool/path restrictions: deny `~/.ssh/**`, `~/.aws/**`, `**/.env*`
- Pre-commit secrets scanning via regex (OpenAI keys, GitHub PATs, AWS keys, private key blocks)
- Enterprise governance controls with audit suppressions requiring narrowest-viable-matcher

---

## 9. Cost Management

| Strategy | Mechanism |
|----------|-----------|
| **Model routing** | Haiku for mechanical tasks, Sonnet for coding, Opus for architecture. Budget parameter: low/med/high |
| **Context budget** | Audit token overhead. MCPs are the biggest lever (~500 tokens/tool) |
| **Pane limits** | Cap dmux parallel agents at 5-6 |
| **Strategic compaction** | Manual `/compact` at logical boundaries |
| **Lazy skill loading** | Trigger-table reduces baseline context by 50%+ |
| **Token budget advisor** | Choose response depth (25%/50%/75%/100%) |
| **cost-tracker.js** | Stop hook tracking per-session metrics |

---

## 10. Observability

### 10.1 Eval Harness

Eval-driven development (EDD):
- Three grader types: code-based (deterministic), model-based (rubric scoring), human
- Metrics: `pass@k` (>90% target within k attempts), `pass^k` (all k succeed)
- Evals stored in `.claude/evals/` with baselines and run history

### 10.2 Session Tracking

- Bash command audit logging to `~/.claude/bash-commands.log`
- Session activity tracking (tool calls, files modified)
- Orchestration status snapshots (JSON exports of session activity, pane metadata, worker states)
- Monthly GitHub metrics workflow (downloads, stars, contributors)

### 10.3 ECC 2.0 Control Plane (Alpha)

Rust-based daemon prototype in `ecc2/`:
- Session management, dashboard, status monitoring
- Conceptually similar to madruga.ai's easter daemon but in Rust
- Early alpha -- not yet production-ready

---

## 11. Strengths and Weaknesses

### Strengths

1. **Massive ecosystem**: 181 skills, 47 agents, 79 commands -- the largest Claude Code plugin collection
2. **Instinct system**: Self-improving learned behaviors with confidence scoring and evolution to skills
3. **Profile-gated hooks**: Same hooks.json at different strictness levels without editing
4. **Cross-harness portability**: Single repo targets 7+ AI agent platforms
5. **GateGuard with A/B data**: Fact-forcing gate with measured +2.25 improvement
6. **Security depth**: Supply chain awareness, real CVEs, enterprise governance
7. **Santa Loop**: Model diversity as quality gate (genuinely novel)
8. **Community scale**: 155k stars, 170+ contributors, active maintenance

### Weaknesses

1. **No DAG orchestration**: No dependency graph, no topological sort, no gate types. Pipeline patterns are informal.
2. **No declarative pipeline**: Orchestration is code-first (tmux commands, bash scripts), not YAML-defined
3. **No unified state management**: Session files are `.tmp`, no database, no trace/span model
4. **Skill quality varies**: 181 skills with no uniform contract -- some are 10 lines, others are 500+
5. **No cost aggregation**: Per-session tracking only. No cross-session trend analysis or USD estimation
6. **Documentation is external**: Guides are Twitter threads, not in-repo markdown
7. **No retry/resilience**: No circuit breaker, no error classification, no exponential backoff
8. **No checkpoint/resume at pipeline level**: Session resume exists but not workflow-level checkpointing
