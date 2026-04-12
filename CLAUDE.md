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
- Platforms: `platforms/<name>/` (business/, engineering/, decisions/, epics/)
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
- ADRs: Nygard format. Epics: Shape Up pitch. Planned epics live only in roadmap.md
- Repo binding: `platform.yaml` → `repo:` block. External repos at `{repos_base_dir}/{repo_org}/{repo_name}`
- Python: stdlib + pyyaml. SQLite WAL mode. Ruff for lint/format.
- Tech stack: Markdown skills + YAML frontmatter, Bash 5.x, Python 3.11+, Mermaid (inline), Astro + Starlight

## Prerequisites

Node.js 20+ | Python 3.11+ | `copier` >= 9.4.0

## Gotchas

- Architecture diagrams use Mermaid inline in `.md` files (rendered by `astro-mermaid` in portal).
- Scripts < 300 LOC: write complete + tests in one batch, no empty incrementalism.
- LOC estimates: multiply by 1.5-2x (docstrings, argparse, logging are not in the base).
- **Easter naming** (A12): the 24/7 orchestrator daemon has two aliases — `easter` is the Python module (`.specify/scripts/easter.py`), `madruga-easter` is the systemd user service (`etc/systemd/madruga-easter.service`). Same process, different views: logs via `journalctl --user -u madruga-easter`, code lives in `easter:app`.
- **`.pipeline/madruga.db` is NOT tracked** (A1): fresh clones run `make seed` to reproduce it from `platforms/*/platform.yaml` + pitches + ADRs. Tracking a live WAL DB caused `row missing from index` corruption on `git checkout`/`stash`.
- **Bare-lite dispatch env vars** (ADR-021): `dag_executor.build_dispatch_cmd` adds `--strict-mcp-config`, `--disable-slash-commands`, `--tools`, `--no-session-persistence` to every `claude -p` invocation under OAuth. `compose_task_prompt` gates `data-model.md`/`contracts/`/`analyze-report.md` on task metadata (legacy mode) and reorders sections for cache-optimal prefix (Phase 5). Rollback kill-switches (default all on):
  - `MADRUGA_BARE_LITE=0` → restore legacy dispatch flags
  - `MADRUGA_KILL_IMPLEMENT_CONTEXT=0` → restore `implement-context.md` append/read
  - `MADRUGA_SCOPED_CONTEXT=0` → re-include all static docs unconditionally (legacy path only)
  - `MADRUGA_CACHE_ORDERED=0` → restore legacy section order (task card at top, scoped gating active). Under the default `=1`, stable sections (plan/spec/data_model/contracts) are force-included at the START of the user prompt so Claude's 1h-TTL prefix cache hits on tasks 2..N within the same epic
  - `MADRUGA_STRICT_SETTINGS=1` (opt-in) → add `--setting-sources project` (requires audit of `settings.local.json` first)
- **`sync_memory.py` hook respects `MADRUGA_DISPATCH=1`** — the flag set by `dag_executor._dispatch_env()` now short-circuits the script to avoid PostToolUse subprocess storms + WAL contention inside dispatched sessions.

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
- Python 3.11+ (backend), TypeScript/React (portal) + sqlite3 (stdlib), structlog, FastAPI (easter), React + @xyflow/react (portal existente), Astro Starlight (epic/madruga-ai/017-observability-tracing-evals)
- SQLite WAL mode (`.pipeline/madruga.db`) — novas tabelas `traces` e `eval_scores`, coluna `trace_id` em `pipeline_runs` (epic/madruga-ai/017-observability-tracing-evals)
- TypeScript (Astro 5.x, React), Python 3.11+ (scripts), Bash (CI) + Astro + Starlight, astro-mermaid v2.0.1, js-yaml (portal build-time) (epic/madruga-ai/022-mermaid-migration)
- Filesystem (Markdown + YAML), SQLite WAL mode (pipeline state) (epic/madruga-ai/022-mermaid-migration)
- Python 3.12 + FastAPI >=0.115 + FastAPI, uvicorn, pydantic 2.x, pydantic-settings, redis[hiredis] >=5.0, httpx, structlog (epic/prosauai/001-channel-pipeline)
- Redis 7 (debounce buffers apenas — sem persistência de dados) (epic/prosauai/001-channel-pipeline)
- Python 3.12, FastAPI >=0.115 + `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-redis`, `arize-phoenix-otel` (epic/prosauai/002-observability)
- Supabase Postgres (schema `observability`, gerenciado pelo Phoenix); Redis 7 (buffers de debounce) (epic/prosauai/002-observability)
- Python 3.12 + FastAPI >=0.115, pydantic 2.x, pydantic-settings, redis[hiredis] >=5.0, httpx, structlog, pyyaml, opentelemetry-sdk (epic/prosauai/003-multi-tenant-foundation)
- Redis 7 (idempotência + debounce buffers), YAML file (tenant config) (epic/prosauai/003-multi-tenant-foundation)
- Python 3.12 (match/case, StrEnum nativo) + FastAPI >=0.115, pydantic 2.x, redis[hiredis] >=5.0, httpx, structlog, opentelemetry-sdk, hypothesis (dev) (epic/prosauai/004-router-mece)
- Redis 7 (state lookup: seen + handoff keys), YAML em disco (routing config) (epic/prosauai/004-router-mece)

## Recent Changes
- epic/madruga-ai/017-observability-tracing-evals: Added Python 3.11+ (backend), TypeScript/React (portal) + sqlite3 (stdlib), structlog, FastAPI (easter), React + @xyflow/react (portal existente), Astro Starlight
