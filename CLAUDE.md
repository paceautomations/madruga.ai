# Madruga Development Guidelines

## Stack
- Python 3.11
- asyncio (daemon loop)
- pydantic 2.10+ / pydantic-settings 2.1+
- structlog 24.1+
- SQLite (aiosqlite)
- Claude Code headless (`claude -p`) + Claude Agent SDK

## Commands
```bash
pip install -e ".[dev]"    # Install with dev deps
pytest                     # Run tests
ruff check .               # Lint
ruff format .              # Format
```

## Code Style
- Python 3.11, ruff for lint+format
- structlog for all logging (never print/logging)
- httpx async for HTTP calls
- pydantic-settings for config (config.yaml + .env)
- Type hints everywhere
- Docstrings only where logic isn't self-evident

## Architecture
- `src/madruga/` — main package
- `prompts/` — system prompts for agents (.md files)
- `epics/` — persistent artifacts per epic (spec, plan, tasks)
- `config.yaml` — repo registry, models, throttle settings
- SQLite is single source of truth for state
- Obsidian Kanban is view-only (daemon writes, human interacts)

## Key Patterns
- All LLM calls via `api/client.py` (claude -p wrapper) or Agent SDK
- Debate loop is reusable (`debate/runner.py`) — same pattern every phase
- 1-Way/2-Way Door classification before every decision
- Max 3 parallel `claude -p` processes (throttle.py)
- Each task ~200 LOC max (Task Agent decomposes if larger)
