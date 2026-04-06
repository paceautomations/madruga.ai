---
title: "Codebase Context"
updated: 2026-04-06
---
# Madruga AI — Codebase Context

> Brownfield analysis of the madruga.ai repository. Self-referencing platform (repo.name == own repo). Last updated: 2026-04-06.

---

## Summary

Python 3.11+ orchestration layer (~8,500 LOC across 27 modules) + Astro/React portal (~3,500 LOC). SQLite WAL mode for state (14 tables + 2 FTS5). 472 files total, 2 platforms, 30+ skills, 20 ADRs, 12 migrations.

---

## File Structure

```
madruga.ai/
├── .specify/scripts/          # Python backend — 27 modules, ~8,500 LOC
│   ├── db_core.py (354)       # Connection, migrations, FTS5, transactions
│   ├── db_pipeline.py (925)   # Platforms, epics, nodes, runs, gates, events
│   ├── db_decisions.py (729)  # ADRs, memory entries, FTS5 search
│   ├── db_observability.py (375) # Traces, eval scores, stats
│   ├── db.py (23)             # Facade re-exports
│   ├── dag_executor.py (2,117) # DAG scheduler, circuit breaker, skill dispatch
│   ├── platform_cli.py (833)  # CLI: list, lint, status, seed, register
│   ├── post_save.py (558)     # Artifact recording → DB
│   ├── easter.py (609)        # Easter 24/7, /api endpoints
│   ├── telegram_bot.py (539)  # Gate approvals via Telegram inline buttons
│   ├── eval_scorer.py (294)   # 4-dimension heuristic scoring (Q/A/C/E)
│   ├── worktree.py (210)      # Git worktree lifecycle for external epics
│   ├── ensure_repo.py (160)   # Clone/fetch platform repos via SSH/HTTPS
│   ├── implement_remote.py (232) # Compose prompts + create PRs for external repos
│   ├── config.py (23)         # Paths, pricing constants
│   ├── errors.py (68)         # MadrugaError hierarchy + validators
│   └── tests/ (20 files)      # pytest + pytest-asyncio
├── portal/src/                # Astro + React — ~3,500 LOC
│   ├── components/dashboard/PipelineDAG.tsx (334) # @xyflow/react DAG
│   ├── components/observability/ (6 tabs)  # Traces, runs, evals, costs
│   ├── pages/[platform]/      # Dynamic: dashboard, roadmap, decisions, observability
│   └── lib/                   # platforms.mjs (auto-discovery), constants.ts
├── .claude/commands/madruga/  # 30+ skill definitions (markdown)
├── .claude/knowledge/         # Pipeline contracts, personas, DAG knowledge
├── .pipeline/migrations/      # 12 SQL migration files
├── platforms/                 # Multi-platform workspace
│   ├── madruga-ai/            # Self-ref platform (this repo)
│   └── fulano/                # External platform (template example)
└── .specify/templates/        # Copier template for new platforms
```

---

## Technology Stack

| Category | Technology | Version | Evidence |
|----------|-----------|---------|---------|
| Language | Python | >=3.11 | pyproject.toml |
| Language | TypeScript/React | 19.2.x | portal/package.json |
| Framework | Astro + Starlight | 6.0.1 / 0.38.2 | portal/package.json |
| Runtime | FastAPI + uvicorn | (easter.py) | easter.py |
| Database | SQLite WAL | 3.35+ | db_core.py PRAGMA journal_mode=WAL |
| Messaging | Telegram Bot API | aiogram >=3.15 | pyproject.toml |
| Visualization | @xyflow/react | 12.10.2 | portal/package.json |
| Diagrams | astro-mermaid | 2.0.1 | portal/package.json |
| AI | Claude CLI (claude -p) | subprocess | dag_executor.py |
| Logging | structlog | >=24.0 | pyproject.toml |
| Template | Copier | >=9.4 | .specify/templates/ |

---

## Detected Patterns

| Pattern | Evidence | File(s) |
|---------|----------|---------|
| Circuit Breaker (3-state) | 5 failures → 300s recovery, half-open test | dag_executor.py:833-876 |
| Topological Sort (Kahn) | In-degree map + queue BFS, cycle detection | dag_executor.py:719-750 |
| Transaction Proxy | _BatchConnection suppresses individual commits | db_core.py:183-219 |
| Event Sourcing | Append-only events table for audit trail | db_pipeline.py:457-495 |
| Gate/Approval | Telegram inline keyboards → DB gate_status | telegram_bot.py:182-357 |
| Observer/Hook | PostToolUse stdin hooks for auto-lint and DB | hook_skill_lint.py, hook_post_save.py |
| Facade | db.py re-exports 4 domain modules | db.py |
| Modular DB Split | 4 isolated modules (zero cross-imports) | db_core/pipeline/decisions/observability |
| FTS5 Fallback | Full-text search with LIKE degradation | db_core.py:_check_fts5 |
| Self-ref Constraint | Sequential epics only for self-ref platforms | pipeline-dag-knowledge.md |

---

## Integrations

| Service | Type | Protocol | File(s) |
|---------|------|----------|---------|
| Claude CLI | AI orchestration | subprocess (claude -p --json) | dag_executor.py |
| Telegram Bot API | Gate approvals + alerts | HTTPS via aiogram | telegram_bot.py |
| ntfy.sh | Emergency alerts | HTTPS POST (stdlib) | ntfy.py |
| Sentry | Error tracking | SDK DSN (optional) | easter.py |
| GitHub | VCS operations | SSH/HTTPS git | ensure_repo.py |
| systemd | Easter watchdog | Unix socket | sd_notify.py |

---

## Observations

- **dag_executor.py (2,117 LOC)** is the largest module — handles DAG parsing, sort, dispatch, circuit breaker, retry, gates, auto-commit. Candidate for decomposition.
- **DB module isolation**: db_core, db_pipeline, db_decisions, db_observability have zero cross-imports.
- **Claude CLI coupling**: All skill dispatch via `claude -p` subprocess — no SDK.
- **Easter as runtime**: runs DAG scheduler, gate poller, and observability API.
- **Self-ref constraint**: madruga-ai epics must run sequentially (shared DB + skills).
