# Implementation Plan: Multi-repo Implement

**Branch**: `epic/madruga-ai/012-multi-repo-implement` | **Date**: 2026-03-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `platforms/madruga-ai/epics/012-multi-repo-implement/spec.md`

## Summary

Habilitar o pipeline SpecKit para operar em repositorios externos via git worktree. O sistema clona repos automaticamente (SSH/HTTPS), cria worktrees isolados por epic, injeta contexto (spec/plan/tasks) no prompt, e invoca `claude -p --cwd=worktree`. PR e criado no repo correto via `gh`. Tres scripts Python novos (~300 LOC total) + 3 subcomandos em platform.py.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib + pyyaml)
**Primary Dependencies**: subprocess (git, gh, claude CLIs), pathlib, fcntl, logging, yaml
**Storage**: Filesystem (repos, worktrees) + SQLite existente (resolve_repo_path, local_config)
**Testing**: pytest com mock de subprocess (unit) + temp dir (integration)
**Target Platform**: Linux/macOS (WSL2 = Linux)
**Project Type**: CLI scripts (extensao do tooling existente)
**Performance Goals**: ensure_repo < 2min (network-bound), worktree < 5s, prompt composition < 1s
**Constraints**: < 500 LOC novo, zero deps novas, stdlib-only + pyyaml
**Scale/Scope**: Single operator, ~5 plataformas, ~10 epics ativos simultaneamente max

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Status | Justificativa |
|-----------|--------|---------------|
| I. Pragmatism | PASS | Scripts diretos, subprocess simples, reutiliza db.py existente |
| II. Automate | PASS | Automatiza clone/worktree/implement que hoje e manual |
| III. Structured Knowledge | PASS | Reutiliza platform.yaml como fonte unica de repo binding |
| IV. Fast Action | PASS | ~300 LOC, 3 scripts, implementacao direta |
| V. Alternatives | PASS | Pesquisa em research.md documenta alternativas para cada decisao |
| VI. Brutal Honesty | PASS | fcntl nao funciona em Windows — aceitavel (target Linux/macOS) |
| VII. TDD | PASS | Testes antes de implementacao: unit (mock subprocess) + integration |
| VIII. Collaborative Decision | PASS | Decisoes capturadas em context.md com participacao do operador |
| IX. Observability | PASS | logging.getLogger(__name__) em todos os scripts, INFO default |

**Re-check pos-design**: PASS — nenhuma violacao introduzida.

## Project Structure

### Documentation (this feature)

```text
platforms/madruga-ai/epics/012-multi-repo-implement/
├── pitch.md             # Shape Up pitch
├── context.md           # Implementation context
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart
├── contracts/
│   └── cli-commands.md  # CLI contracts
└── tasks.md             # (Phase 2, gerado por /speckit.tasks)
```

### Source Code (repository root)

```text
.specify/scripts/
├── ensure_repo.py       # NOVO — Clone/fetch repos (SSH/HTTPS, locking)
├── worktree.py          # NOVO — Create/cleanup git worktrees
├── implement_remote.py  # NOVO — Orquestrador: ensure → worktree → prompt → claude -p
└── platform.py          # EDIT — +3 subcomandos (ensure-repo, worktree, worktree-cleanup)

tests/
├── test_ensure_repo.py  # Unit: mock subprocess git
├── test_worktree.py     # Unit: mock subprocess git
└── test_implement_remote.py  # Integration: temp dir + mock claude
```

**Structure Decision**: Scripts individuais em `.specify/scripts/` (padrao do repo). Cada script e importavel como modulo e tem `if __name__ == "__main__"` para uso direto. `platform.py` importa funcoes dos scripts para expor como subcomandos.

## Complexity Tracking

Nenhuma violacao de constitution a justificar.

---
handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan completo com research, data-model, contracts e quickstart. 3 scripts novos (~300 LOC), 3 subcomandos em platform.py. Pronto para task breakdown."
  blockers: []
  confidence: Alta
  kill_criteria: "Se claude -p nao suportar --cwd, abordagem precisa revisao."
