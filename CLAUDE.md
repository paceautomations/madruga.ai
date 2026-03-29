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
│   ├── commands/madruga/      # 20 atomic skills for platform documentation pipeline
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
python3 .specify/scripts/platform.py register <name>         # update portal symlinks

# ── Portal ──
cd portal
npm install          # runs setup.sh (creates symlinks for ALL platforms)
npm run dev          # http://localhost:4321 (auto-discovers all platforms)
npm run build        # production build

# ── LikeC4 ──
cd platforms/<name>/model
likec4 serve         # http://localhost:5173 (standalone hot reload)

# ── Build Pipeline ──
python3 .specify/scripts/vision-build.py <name>              # populate AUTO tables from model
python3 .specify/scripts/vision-build.py <name> --validate-only
python3 .specify/scripts/vision-build.py <name> --export-png
```

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
- `portal/setup.sh` creates symlinks for ALL discovered platforms: `src/content/docs/<name> → platforms/<name>`
- Dynamic routes in `src/pages/[platform]/` generate pages for every platform at build time
- `LikeC4Diagram.tsx` uses `React.lazy` with per-project imports (`likec4:react/<name>`)
- **IMPORTANT**: When adding a new platform, also add its import to `platformLoaders` in `portal/src/components/viewers/LikeC4Diagram.tsx`

### ADRs Follow Nygard Format

All ADRs in `platforms/<name>/decisions/` follow the Nygard template: Context, Decision, Alternatives, Consequences.

### Epics Follow Shape Up

All epics in `platforms/<name>/epics/NNN-slug/pitch.md` follow Shape Up format: Problem, Appetite, Solution, Rabbit Holes, Acceptance Criteria.

## Platform Documentation Pipeline (DAG)

Each platform is documented incrementally via **atomic skills** orchestrated by a **DAG declared in `platform.yaml`**. Each skill is self-contained (fresh context), produces one artifact, and gets validated before proceeding.

### Pipeline Flow

```
platform-new → vision → solution-overview → business-process
→ tech-research → adr-gen → blueprint → folder-arch
                                      → domain-model → containers → context-map
→ epic-breakdown → roadmap → [per-epic: discuss → SpecKit → verify → reconcile]
```

### Gate Types

| Gate | Behavior |
|------|----------|
| `human` | Always pauses for approval |
| `auto` | Proceeds automatically |
| `1-way-door` | Always pauses — irreversible decisions (tech-research, adr-gen, epic-breakdown) |
| `auto-escalate` | Auto if OK, escalates if blockers (verify) |

### Key Commands

```bash
# Pipeline status and navigation
/pipeline-status <platform>    # Table + Mermaid DAG + progress
/pipeline-next <platform>      # Recommend next step (NO auto-execute)

# Prerequisite check
.specify/scripts/bash/check-platform-prerequisites.sh --json --status --platform <name>
```

### Skill Contract

Every pipeline skill follows a uniform 6-step contract (see `.claude/knowledge/pipeline-dag-knowledge.md`):
0. Prerequisites check + constitution validation
1. Context collection + structured questions (Premissas, Trade-offs, Gaps, Provocação)
2. Artifact generation
3. Auto-review
4. Gate approval
5. Save + report + handoff

## SpecKit Workflow

The `.claude/commands/speckit.*.md` skills form a feature specification pipeline:
`specify → clarify → plan → tasks → implement`, with `analyze` for consistency checks and `taskstoissues` for GitHub integration.

## Key Conventions

- **AUTO markers**: Never manually edit content between `<!-- AUTO:name -->` and `<!-- /AUTO:name -->` markers in engineering docs — these are regenerated by `vision-build.py`
- **platform.yaml**: Declarative manifest defining available views, lifecycle stage, build commands, and **pipeline DAG** (14 nodes with dependencies, gates, layers) for each platform
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

## Active Technologies
- Bash 5.x (script), Markdown (skills), YAML (schema), Python 3.11+ (YAML parsing in script) + Claude Code custom commands system, `python3` with `pyyaml`, existing `.specify/scripts/bash/common.sh` (001-atomic-skills-dag-pipeline)
- Filesystem only — artifacts are markdown/LikeC4 files, status derived from file existence (001-atomic-skills-dag-pipeline)

## Recent Changes
- 001-atomic-skills-dag-pipeline: Added Bash 5.x (script), Markdown (skills), YAML (schema), Python 3.11+ (YAML parsing in script) + Claude Code custom commands system, `python3` with `pyyaml`, existing `.specify/scripts/bash/common.sh`
