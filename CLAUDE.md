# CLAUDE.md — madruga.ai

Docs, comments and code in English.
Commits with prefixes: feat:, fix:, chore:, merge:.
Number structured questions (1, 2, 3…) for reply by number.

## What it is

Architectural documentation system for N digital platforms.
Shared Copier template.
24-skill pipeline (L1 platform + L2 per epic): @.claude/knowledge/pipeline-dag-knowledge.md

## Where to find things

- Skills: `.claude/commands/` | Knowledge: `.claude/knowledge/`
- Platforms: `platforms/<name>/` (business/, engineering/, decisions/, epics/, model/)
- Scripts: `.specify/scripts/` | Portal: `portal/`

## Essential commands

`make test` | `make lint` | `make ruff` | `make seed`
`python3 .specify/scripts/platform_cli.py list|status|use|lint <name>`
`/madruga:getting-started` (onboarding) | `/madruga:pipeline` (status)
Full reference: @.claude/knowledge/commands.md

## Namespaces

- `madruga:*` — full pipeline (L1 + L2 + utilities)
- `speckit.*` — L2 cycle: specify → clarify → plan → tasks → analyze → implement

## Conventions

- platform.yaml: manifest with repo binding, views, lifecycle stage
- `platform_cli.py use <name>` sets active platform — skills check when no argument given
- Each `platforms/<name>/` has its own CLAUDE.md with platform-specific context (on-demand)
- ADRs: Nygard format. Epics: Shape Up pitch. Planned epics live only in roadmap.md
- Repo binding: `platform.yaml` → `repo:` block. External repos at `{repos_base_dir}/{repo_org}/{repo_name}`
- Python: stdlib + pyyaml. SQLite WAL mode. Ruff for lint/format.
- Tech stack: Markdown skills + YAML frontmatter, Bash 5.x, Python 3.11+, LikeC4, Astro + Starlight

## Prerequisites

Node.js 20+ | Python 3.11+ | `likec4` CLI (`npm i -g likec4`) | `copier` >= 9.4.0

## Gotchas

- Edit `.likec4` sources, run `vision-build.py` to regenerate AUTO markers.
- Add platformLoaders in `LikeC4Diagram.tsx` when creating a new platform.
- Scripts < 300 LOC: write complete + tests in one batch, no empty incrementalism.
- LOC estimates: multiply by 1.5-2x (docstrings, argparse, logging are not in the base).

## Active hooks

- PostToolUse on `platforms/**` → auto-registers in SQLite (hook_post_save.py)
- PostToolUse on `.claude/commands/**` and `.claude/knowledge/**` → auto skill-lint (hook_skill_lint.py)
- PostToolUse on `.claude/**/memory/**` → auto-sync memory (sync_memory.py)
- Git post-merge → auto-reseed DB if migrations changed
- Auto-simplify: after implementation touching 3+ files → run /simplify (skip one-liners/docs)

## Compact instructions

Preserve on compact: modified files, test state, active epic/task,
architectural decisions from the session, in-progress debug hypotheses.

## Principles

Pragmatism > elegance. Automate on 3rd repetition. Bias for action.
Use Context7 for up-to-date docs. Always present trade-offs with pros/cons.

## Workflow enforcement

Plan mode → auto-review with subagent before presenting.
Subagent prompt: @.claude/rules/plan-review-prompt.md

## Epic workflow

- **Planned epics** live only in `planning/roadmap.md` — no files created
- **Active epics** (entering L2) get `epics/NNN-slug/` with pitch.md, spec, plan, tasks
- Epic branches mandatory: `epic/<platform>/<NNN-slug>` — merge to main via PR only
- `/madruga:epic-breakdown` for roadmap candidates; `/madruga:epic-context` to start

## Skill & knowledge editing policy

Edits to `.claude/commands/` and `.claude/knowledge/` MUST go through `/madruga:skills-mgmt`.
Never edit these files directly — always use `/madruga:skills-mgmt edit <name>` (or create/lint/audit).
Direct edits bypass validation (frontmatter, handoff chains, archetype compliance, dedup).

## Active Technologies
- Python 3.11+ (backend), TypeScript/React (portal) + sqlite3 (stdlib), structlog, FastAPI (daemon), React + @xyflow/react (portal existente), Astro Starlight (epic/madruga-ai/017-observability-tracing-evals)
- SQLite WAL mode (`.pipeline/madruga.db`) — novas tabelas `traces` e `eval_scores`, coluna `trace_id` em `pipeline_runs` (epic/madruga-ai/017-observability-tracing-evals)

## Recent Changes
- epic/madruga-ai/017-observability-tracing-evals: Added Python 3.11+ (backend), TypeScript/React (portal) + sqlite3 (stdlib), structlog, FastAPI (daemon), React + @xyflow/react (portal existente), Astro Starlight
