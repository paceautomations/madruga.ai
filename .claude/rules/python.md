---
paths:
  - "**/*.py"
---
# Python Conventions

- Usar **ruff** para formatting e linting: `make ruff` (check) / `make ruff-fix` (auto-fix)
- Dependências: stdlib + pyyaml. Adicionar deps externas só com justificativa explícita.
- SQLite em WAL mode (`.pipeline/madruga.db`)
- Testes: pytest (`make test` ou `python3 -m pytest .specify/scripts/tests/ -v`)

## Mock patches
Sempre patchar no módulo que **define** o símbolo, não onde é consumido.
Imports locais dentro de `def` → patch na origem.

Correto: `@patch("ensure_repo._is_self_ref")`
Errado: `@patch("worktree._is_self_ref")`

## Scripts < 300 LOC
Escrever script completo + testes de uma vez (batch). Criar arquivos vazios incrementalmente gera round-trips sem valor. Reservar task breakdown granular para módulos > 500 LOC.

## LOC estimates
Multiplicar estimativas por 1.5-2x. Docstrings, argparse, logging e boilerplate não entram na estimativa base.
