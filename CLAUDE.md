# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

**madruga.ai** is an architecture documentation system for digital platforms. It documents what a system does, why decisions were made, and how pieces connect — all versioned in git, consumable by humans and LLMs.

The system supports **N platforms** from a shared Copier template. Each platform gets the same documentation structure, portal integration, and LikeC4 model pipeline. The first platform is **Fulano** — a multi-tenant WhatsApp conversational agent platform for Brazilian SMBs.

Language: documentation and comments are in **Brazilian Portuguese**. Code is in English.

## Repository Structure

```
├── .specify/                  # SpecKit + platform tooling
│   ├── scripts/
│   │   ├── bash/              # SpecKit shell scripts
│   │   ├── vision-build.py    # Exports LikeC4 JSON → populates markdown tables
│   │   └── platform.py        # Platform CLI (new, lint, sync, register, list)
│   ├── templates/
│   │   ├── platform/          # Copier template for scaffolding new platforms
│   │   │   ├── copier.yml     # Template config + questions
│   │   │   ├── template/      # Template files (Jinja2)
│   │   │   └── tests/         # Template validation tests (pytest)
│   │   └── *.md               # SpecKit templates (spec, plan, tasks, etc.)
│   └── memory/                # Constitution and project memory
├── platforms/
│   ├── fulano/                # First platform (Fulano)
│   └── <new-platform>/       # Additional platforms (scaffolded via copier)
│       ├── platform.yaml      # Platform manifest (name, lifecycle, views, commands)
│       ├── .copier-answers.yml # Copier state (enables copier update)
│       ├── business/          # Vision brief, solution overview
│       ├── engineering/       # Domain model, containers, context map, integrations
│       ├── decisions/         # ADRs (Nygard format)
│       ├── epics/             # Shape Up pitch documents
│       ├── research/          # Market research, technical benchmarks
│       └── model/             # LikeC4 architecture model (.likec4 files)
│           └── likec4.config.json  # Multi-project name (required)
├── portal/                    # Astro + Starlight site (auto-discovers all platforms)
│   ├── src/lib/platforms.mjs  # Platform discovery + dynamic sidebar builder
│   └── src/pages/[platform]/  # Dynamic routes for all platforms
├── .claude/
│   ├── commands/madruga/      # 21 skills: 13 L1 nodes + 3 L2 nodes + 5 utilities
│   ├── knowledge/             # Knowledge files loaded on-demand by skills
│   └── settings.local.json    # Permissions and MCP server config
└── docs/                      # Legacy docs
```

## Common Commands

```bash
# ── Platform Management ──
python3 .specify/scripts/platform.py list                    # list all platforms
python3 .specify/scripts/platform.py new <name>              # scaffold new platform (copier)
python3 .specify/scripts/platform.py lint <name>             # validate structure
python3 .specify/scripts/platform.py lint --all              # validate all platforms
python3 .specify/scripts/platform.py sync                    # copier update all platforms
python3 .specify/scripts/platform.py register <name>         # inject LikeC4 loader + validate model
python3 .specify/scripts/platform.py import-adrs <name>      # import ADR markdown files into DB
python3 .specify/scripts/platform.py export-adrs <name>      # export decisions from DB to markdown
python3 .specify/scripts/platform.py import-memory           # import .claude/memory/*.md into DB
python3 .specify/scripts/platform.py export-memory           # export memory entries to markdown
python3 .specify/scripts/platform.py use <name>               # set active platform
python3 .specify/scripts/platform.py current                   # show active platform
python3 .specify/scripts/platform.py status <name>           # pipeline status (human table)
python3 .specify/scripts/platform.py status --all --json     # all platforms (JSON for dashboard)

# ── Portal ──
cd portal
npm install          # install dependencies (symlinks auto-managed by Vite plugin)
npm run dev          # http://localhost:4321 (auto-discovers all platforms)
npm run build        # production build

# ── LikeC4 ──
cd platforms/<name>/model
likec4 serve         # http://localhost:5173 (standalone hot reload)

# ── Build Pipeline ──
python3 .specify/scripts/vision-build.py <name>              # populate AUTO tables from model
python3 .specify/scripts/vision-build.py <name> --validate-only
python3 .specify/scripts/vision-build.py <name> --export-png

# ── DAG Executor ──
python3 .specify/scripts/dag_executor.py --platform <name> --dry-run     # print execution order
python3 .specify/scripts/dag_executor.py --platform <name>                # execute L1 pipeline
python3 .specify/scripts/dag_executor.py --platform <name> --epic <slug>  # execute L2 epic cycle
python3 .specify/scripts/dag_executor.py --platform <name> --resume       # resume from checkpoint
python3 .specify/scripts/platform.py gate list <name>                     # list pending gates
python3 .specify/scripts/platform.py gate approve <run-id>                # approve a gate

# ── DB State (post-save) ──
python3 .specify/scripts/post_save.py --platform <name> --node <id> --skill <skill> --artifact <path>  # record skill completion
python3 .specify/scripts/post_save.py --reseed --platform <name>   # re-seed platform from filesystem
python3 .specify/scripts/post_save.py --reseed-all                 # re-seed all platforms

# ── Skill Management ──
python3 .specify/scripts/skill-lint.py                 # lint all skills
python3 .specify/scripts/skill-lint.py --skill <name>  # lint one skill
python3 .specify/scripts/skill-lint.py --json           # JSON output
```

## Command Namespaces

- **`madruga:*`** (e.g., `/madruga:vision`, `/madruga:adr`, `/madruga:pipeline`, `/madruga:getting-started`) — Full pipeline: L1 platform documentation (13 nodes) + L2 epic cycle (epic-context, verify, qa, reconcile) + utilities (pipeline, checkpoint, getting-started, skills-mgmt).
- **`speckit.*`** (e.g., `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`) — Part of L2 epic cycle: specify → clarify → plan → tasks → analyze → implement.

Both namespaces form a single continuous pipeline invoked via `/madruga:<skill>` or `/speckit.<skill>` in Claude Code. Start with `/madruga:getting-started` for guided onboarding.

## Prerequisites

- Node.js 20+
- Python 3.11+
- `likec4` CLI: `npm i -g likec4`
- `copier` >= 9.4.0: `pip install copier`

## Architecture: How the Pieces Connect

### Multi-Platform Template System (Copier)

- `.specify/templates/platform/` contains a Copier template for scaffolding new platforms
- `copier copy .specify/templates/platform/ platforms/<name>/` creates a new platform with the standard structure
- `copier update` syncs structural changes across platforms (protected by `_skip_if_exists`)
- `model/spec.likec4` is the only model file that syncs — all other model files are platform-specific
- Each platform has `model/likec4.config.json` with `{"name": "<platform>"}` for LikeC4 multi-project

### Three-Layer Documentation Framework

Each platform is documented in 3 layers: **Business** (why/for whom), **Engineering** (how it works technically), **Planning** (what to build and when). This maps to the directory structure under `platforms/<name>/`.

### LikeC4 Model → Markdown Pipeline

The LikeC4 model files (`platforms/<name>/model/*.likec4`) are the **source of truth** for architecture diagrams. The pipeline is:

1. `.likec4` files define elements, relationships, and views
2. `likec4 export json` produces `model/output/likec4.json`
3. `.specify/scripts/vision-build.py` reads that JSON and populates markdown tables via `<!-- AUTO:name -->` markers in engineering docs

### Portal (Astro + Starlight + LikeC4 React)

- `portal/src/lib/platforms.mjs` auto-discovers all platforms by scanning `platforms/*/platform.yaml`
- `portal/astro.config.mjs` builds sidebar dynamically from platform manifests and uses `LikeC4VitePlugin({ workspace: '../platforms' })` for multi-project support
- `platformSymlinksPlugin()` in `astro.config.mjs` auto-creates per-section symlinks at build/dev time (no manual setup needed)
- Dynamic routes in `src/pages/[platform]/` generate pages for every platform at build time
- `LikeC4Diagram.tsx` uses `React.lazy` with per-project imports (`likec4:react/<name>`)
- **IMPORTANT**: When adding a new platform, also add its import to `platformLoaders` in `portal/src/components/viewers/LikeC4Diagram.tsx`

### ADRs Follow Nygard Format

All ADRs in `platforms/<name>/decisions/` follow the Nygard template: Context, Decision, Alternatives, Consequences.

### Epics Follow Shape Up

All epics in `platforms/<name>/epics/NNN-slug/pitch.md` follow Shape Up format: Problem, Appetite, Solution, Rabbit Holes, Acceptance Criteria.

## Pipeline — Full Flow (L1 + L2)

The pipeline is a **single continuous flow of 24 skills** that takes a platform from conception to implemented, tested code. Orchestrated by a **two-level DAG** (defined in `.claude/knowledge/pipeline-dag-knowledge.md`). Each skill is self-contained (fresh context), produces one artifact, and gets validated before proceeding.

### Pipeline Flow

```
L1 (platform, runs once):
  platform-new → vision → solution-overview → business-process
  → tech-research → adr → blueprint → domain-model → containers → context-map
  → epic-breakdown → roadmap

L2 (per epic, repeats on dedicated branch):
  → epic-context → specify → clarify → plan → tasks → analyze
  → implement → analyze → verify → qa? → reconcile → PR/merge → next epic
```

### Gate Types

| Gate | Behavior |
|------|----------|
| `human` | Always pauses for approval |
| `auto` | Proceeds automatically |
| `1-way-door` | Always pauses — irreversible decisions (tech-research, adr, epic-breakdown) |
| `auto-escalate` | Auto if OK, escalates if blockers (verify) |

### Key Commands

```bash
# Pipeline status and navigation (shows L1 + L2 unified)
/pipeline <platform>           # Table + Mermaid DAG + progress + next step

# Prerequisite check
.specify/scripts/bash/check-platform-prerequisites.sh --json --status --platform <name>
```

### L1 — Platform Foundation (13 nodes, runs once)

| # | Skill | Output | Depends on | Layer | Gate |
|---|-------|--------|------------|-------|------|
| 1 | `platform-new` | platform.yaml | — | business | human |
| 2 | `vision` | business/vision.md | platform-new | business | human |
| 3 | `solution-overview` | business/solution-overview.md | vision | business | human |
| 4 | `business-process` | business/process.md | solution-overview | business | human |
| 5 | `tech-research` | research/tech-alternatives.md | business-process | research | 1-way-door |
| 6 | `codebase-map` | research/codebase-context.md | vision | research | auto (optional) |
| 7 | `adr` | decisions/ADR-*.md | tech-research | engineering | 1-way-door |
| 8 | `blueprint` | engineering/blueprint.md | adr | engineering | human |
| 9 | `domain-model` | engineering/domain-model.md + model/ddd-contexts.likec4 | blueprint, business-process | engineering | human |
| 10 | `containers` | model/platform.likec4 + model/views.likec4 | domain-model, blueprint | engineering | human |
| 11 | `context-map` | engineering/context-map.md | domain-model, containers | engineering | human |
| 12 | `epic-breakdown` | epics/*/pitch.md | domain-model, containers, context-map | planning | 1-way-door |
| 13 | `roadmap` | planning/roadmap.md | epic-breakdown | planning | human |

### L2 — Epic Implementation Cycle (11 nodes per epic)

Each epic from the roadmap continues the pipeline on a dedicated branch `epic/<platform>/<NNN-slug>`. This is where code is actually written, tested, and validated.

**MANDATORY: Every epic runs on a dedicated branch.** `epic-context` creates it. All L2 skills verify they are NOT on main (branch guard in pipeline-contract-base.md Step 0). Merge to main via PR after reconcile.

| # | Skill | Gate | Purpose |
|---|-------|------|---------|
| 14 | `epic-context` | human | **Create branch** + capture implementation context |
| 15 | `speckit.specify` | human | Feature specification |
| 16 | `speckit.clarify` | human | Reduce ambiguity in spec before planning |
| 17 | `speckit.plan` | human | Design artifacts |
| 18 | `speckit.tasks` | human | Task breakdown |
| 19 | `speckit.analyze` | auto | Pre-implementation consistency check (spec/plan/tasks) |
| 20 | `speckit.implement` | auto | **Execute tasks — writes actual code** |
| 21 | `speckit.analyze` | auto | Post-implementation consistency check |
| 22 | `verify` | auto-escalate | Check implementation vs spec/tasks/architecture |
| 23 | `qa` | human | Comprehensive testing — static analysis, tests, code review, browser QA |
| 24 | `reconcile` | human | Detect and fix drift between implementation and docs |

After reconcile: **PR → merge to main → next epic**.

**qa is mandatory** — always runs with auto-adaptive layers (static analysis, tests, code review, build, API, browser). Runs before reconcile because its heal loop may modify code, creating new drift.

### Utility Skills

| Skill | Purpose |
|-------|---------|
| `pipeline` | Table + Mermaid DAG (L1 + L2) + progress + next step |
| `checkpoint` | Save STATE.md with session progress |
| `getting-started` | Interactive onboarding |
| `skills-mgmt` | Create, edit, lint, audit skills and knowledge files |
| `speckit.checklist` | Custom checklist for a feature |
| `speckit.constitution` | Create/update project constitution |
| `speckit.taskstoissues` | Convert tasks to GitHub Issues |

### Skill Contract

Every pipeline skill (L1 and L2) follows a uniform 6-step contract (see `.claude/knowledge/pipeline-dag-knowledge.md`):
0. Prerequisites check + constitution validation (+ branch guard for L2)
1. Context collection + structured questions (Premissas, Trade-offs, Gaps, Provocação)
2. Artifact generation (or code for `speckit.implement`)
3. Auto-review (Tier 1/2/3 based on gate type)
4. Gate approval
5. Save + SQLite recording (post_save.py) + report + handoff

## Key Conventions

- **AUTO markers**: Never manually edit content between `<!-- AUTO:name -->` and `<!-- /AUTO:name -->` markers in engineering docs — these are regenerated by `vision-build.py`
- **platform.yaml**: Declarative manifest defining available views, lifecycle stage, build commands, and repo binding for each platform. Full pipeline (L1: 13 nodes + L2: 11 nodes per epic) is defined in `.claude/knowledge/pipeline-dag-knowledge.md`
- **Repo binding**: Each platform's `platform.yaml` has a `repo:` block mapping to its code repository (org, name, base_branch). Convention: external repo lives at `{repos_base_dir}/{repo_org}/{repo_name}`. Self-referencing platforms (madruga-ai) have `repo.name: madruga.ai`.
- **Active platform**: `platform.py use <name>` sets the active platform in local DB. Skills should check active platform when no explicit platform argument is given. Each `platforms/<name>/` has its own `CLAUDE.md` with platform-specific context loaded on-demand by Claude Code.
- Python code in this repo uses **ruff** for formatting and linting

## Principles

- **Pragmatism**: "Works and delivers value" > "elegant but slow". Throwaway code is fine. Don't over-engineer one-off scripts.
- **Automate**: If you do something 3x, write a script. Look for APIs/MCPs before building from scratch. Use Context7 for up-to-date docs.
- **Structured knowledge**: Keep contexts current, access fast, templates reusable, decision history tracked.
- **Bias for action**: Prototype first, refine later. No tests for one-off scripts. Ship imperfect today > perfect never.
- **Trade-offs**: Always present alternatives with pros/cons. Recommend one, but explain why.
- **Brutal honesty**: No empty praise. Flag problems early. Say "this doesn't make sense" when it doesn't.

## Plan Mode Auto-Review

When finishing any implementation plan (plan mode), BEFORE presenting it to the user:
1. Run a subagent (Agent tool, subagent_type="general-purpose") with the full plan text
2. Subagent prompt: "You are a staff engineer reviewing an implementation plan. Be harsh and direct. Check for: missed edge cases, over-engineering, simpler alternatives, security risks, missing error handling at boundaries, unrealistic assumptions. Output a bullet list of issues found (BLOCKER/WARNING/NIT) and an overall verdict."
3. Incorporate the subagent's feedback into the plan — fix blockers, note warnings
4. Present the improved plan to the user with a brief "Review notes" section at the end

## Auto-Simplify

After completing any implementation task (new code or refactor touching 3+ files):
1. Before presenting to the user, run `/simplify` on the changed files
2. If BLOCKER issues are found, fix them before presenting
3. If WARNING/NIT issues are found, mention them briefly in the output
4. **Skip for**: one-liners, config changes, docs, one-off scripts, typo fixes

## Tech Stack

- **Skills**: Markdown (Claude Code custom commands) + YAML frontmatter
- **Scripts**: Bash 5.x + Python 3.11+ (`pyyaml`)
- **Architecture models**: LikeC4 (.likec4 files)
- **Portal**: Astro + Starlight + LikeC4 React
- **Storage**: Filesystem (source of truth) + SQLite (state store, cache)

## Active Technologies
- Python 3.11+ (stdlib only: sqlite3, hashlib, json, pathlib, uuid, logging, fcntl, subprocess) + pyyaml
- SQLite 3 WAL mode (`.pipeline/madruga.db`) — 13 tables, 5 migrations, FTS5
- Bash 5.x
- Astro + Starlight (portal)
- LikeC4 (architecture models)
- Python 3.12 (compativel com 3.11+) + aiogram >= 3.15, pyyaml (existente) (010-telegram-notifications)
- SQLite WAL mode (existente — `.pipeline/madruga.db`) (010-telegram-notifications)

## Epic Workflow
- **Planned epics** live only in `planning/roadmap.md` as table entries — no files created
- **Active epics** (entering L2) get full `epics/NNN-slug/` directory with pitch.md, spec, plan, tasks
- Use `/madruga:epic-breakdown` to add candidates to roadmap; `/madruga:epic-context` to start implementation

## Shipped Epics (madruga-ai)
| # | Epic | Summary |
|---|------|---------|
| 006 | SQLite Foundation | BD SQLite como state store. db.py, migrations, seed, provenance. |
| 007 | Directory Unification | SpecKit em epics/. DAG L1+L2. platform.yaml. Copier template. |
| 008 | Quality & DX | Knowledge files. Skills enxutas. Verify + QA + Reconcile. |
| 009 | Decision Log BD | BD source of truth para decisions + memory. FTS5. Import/export CLI. |
| 010 | Pipeline Dashboard | Dashboard visual no portal. CLI status. Mermaid DAG. |
| 011 | CI/CD Pipeline | GitHub Actions: lint, LikeC4 build, db-tests, templates, bash-tests, portal-build. |
| 012 | Multi-repo Implement | ensure_repo (SSH/HTTPS), worktree, implement_remote (claude -p --cwd), PR via gh. 3 scripts, 28 testes. |
| 013 | DAG Executor + SpeckitBridge | dag_executor.py: Kahn's topological sort, claude -p dispatch, human gates (CLI pause/resume), retry/circuit breaker/watchdog. Migration 007. 43 testes. |
| 014 | Telegram Notifications | Bot Telegram standalone (aiogram 3.x): notifica human gates, inline keyboard approve/reject, health check, backoff, offset persistence. Migration 008. 28 testes. |

## Recent Changes
- 014-telegram-notifications: telegram_bot.py + telegram_adapter.py. structlog>=24.0. 135 testes totais.
