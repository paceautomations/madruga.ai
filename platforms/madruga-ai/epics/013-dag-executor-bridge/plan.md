---
title: "Implementation Plan: DAG Executor + SpeckitBridge"
updated: 2026-03-31
---
# Implementation Plan: DAG Executor + SpeckitBridge

**Branch**: `epic/madruga-ai/013-dag-executor-bridge` | **Date**: 2026-03-31 | **Spec**: spec.md

## Summary

Construir custom DAG executor (ADR-017) que le platform.yaml, faz topological sort, e despacha skills via `claude -p` subprocess. Inclui gate state machine (pause/resume via SQLite + CLI), retry com backoff exponencial, circuit breaker, watchdog, e SpeckitBridge para composicao generalizada de prompts.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib + pyyaml)
**Primary Dependencies**: pyyaml (existente), sqlite3 (stdlib)
**Storage**: SQLite WAL mode (.pipeline/madruga.db)
**Testing**: pytest
**Target Platform**: Linux (WSL2)
**Project Type**: CLI tool
**Performance Goals**: Resume < 5s, dispatch overhead < 1s por node
**Constraints**: Zero deps novas, 500-800 LOC producao, single executor (sem asyncio)
**Scale/Scope**: 24 nodes (13 L1 + 11 L2), single-operator
**Estimated LOC**: ~500 functional + ~150 boilerplate (argparse, imports, docstrings) = ~650 total

## Project Structure

### Source Code

```
.specify/scripts/
├── dag_executor.py          # NEW (~420 LOC) — core executor
├── implement_remote.py      # EXTEND (+50 LOC) — compose_skill_prompt()
├── platform.py              # EXTEND (+30 LOC) — gate subcommands
├── db.py                    # EXTEND (+40 LOC) — gate functions
└── config.py                # READ ONLY — DB_PATH, REPO_ROOT

.pipeline/migrations/
└── 007_gate_fields.sql      # NEW — gate columns em pipeline_runs

tests/
└── test_dag_executor.py     # NEW (~300 LOC)
```

**Structure Decision**: Modulo unico `dag_executor.py` contem toda a logica do executor (DAG parser, dispatch, gates, retry, circuit breaker). Extensoes em arquivos existentes mantem coesao.

## LOC Budget

| Arquivo | LOC Estimado | Tipo |
|---------|-------------|------|
| dag_executor.py | ~420 | novo |
| db.py | +40 | extensao |
| platform.py | +30 | extensao |
| implement_remote.py | +50 | extensao |
| 007_gate_fields.sql | ~10 | novo |
| **Total producao** | **~550** | |
| test_dag_executor.py | ~300 | novo |
| **Total com testes** | **~850** | |

## Arquitetura do dag_executor.py

```
┌─────────────────────────────────────────────────┐
│                  main() / argparse               │
│  --platform, --epic, --resume, --dry-run, -v    │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              run_pipeline()                       │
│  1. parse_dag() → nodes                          │
│  2. topological_sort() → ordered nodes           │
│  3. if resume: filter completed from DB          │
│  4. for node in ordered:                         │
│     a. check deps satisfied                      │
│     b. check gate (human → pause & exit)         │
│     c. check circuit breaker                     │
│     d. compose_skill_prompt()                    │
│     e. dispatch_node() with retry + watchdog     │
│     f. verify_outputs()                          │
│     g. record in DB                              │
└─────────────────────────────────────────────────┘
```

### Componentes Internos

| Componente | LOC Est. | Responsabilidade |
|-----------|----------|-----------------|
| `parse_dag()` | ~40 | Le YAML, retorna lista de Node namedtuples |
| `topological_sort()` | ~30 | Kahn's algorithm com deteccao de ciclos |
| `CircuitBreaker` | ~40 | Classe com closed/open/half-open, check()/record_failure()/record_success() |
| `dispatch_node()` | ~60 | subprocess.run + timeout + retry loop |
| `verify_outputs()` | ~20 | Checa existencia de arquivos |
| `run_pipeline()` | ~80 | Orquestrador principal |
| `main()` | ~40 | Argparse + setup logging |
| Gate logic | ~50 | Deteccao, persist DB, mensagem, resume check |
| Helpers | ~60 | _resolve_cwd(), _skip_optional(), logging |

## Decisoes Tecnicas

### 1. Kahn's Algorithm para Topological Sort

Kahn's e O(V+E), determinístico, ~30 LOC. Detecta ciclos naturalmente (se restam nodes apos o sort, ha ciclo). Alternativa BFS/DFS recursivo — rejeitado por nao detectar ciclos tao elegantemente.

### 2. Exit-and-Resume para Human Gates

Executor faz exit 0 ao atingir gate (nao fica bloqueado). Operador aprova via CLI e re-invoca com --resume. Alternativa: polling loop — rejeitado porque desperdicaria recursos e complicaria o codigo.

### 3. Circuit Breaker como Classe Simples

3 estados, 2 transicoes, ~40 LOC. Sem persistencia (state in-memory, reseta entre runs). Se persistencia necessaria no futuro, gravar em local_config.

### 4. compose_skill_prompt() Reutiliza compose_prompt()

Para skill "speckit.implement", reutiliza compose_prompt() existente. Para outros skills, monta prompt minimalista: instrucao + artefatos de dependencia. Nao precisa de templates por skill — claude -p resolve internamente.

## Nao Implementar

- Easter/event loop (epic 016)
- Telegram notifications (epic 014)
- Subagent Judge (epic 015)
- Concorrencia claude -p (epic 016)
- Web UI para gates (portal dashboard ja existe)
- Persistencia do circuit breaker (in-memory suficiente)

---
handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan completo. dag_executor.py como modulo unico (~420 LOC). Extensoes em db.py, platform.py, implement_remote.py. Migration 007. Pronto para tasks."
  blockers: []
  confidence: Alta
