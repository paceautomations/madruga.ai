# Implementation Plan: SQLite Foundation

**Branch**: `002-sqlite-foundation` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-sqlite-foundation/spec.md`

## Summary

Implementar SQLite como banco de dados para todo estado do pipeline madruga.ai. Inclui: schema com 8 tabelas, módulo `db.py` (thin wrapper stdlib), migration runner, seed do filesystem, flag `--use-db` no prerequisites checker, GitHub Actions CI (lint + likec4 + copier), e guardrails de hallucination em skills de research.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib only: sqlite3, hashlib, json, pathlib, uuid)
**Primary Dependencies**: Zero — apenas stdlib Python
**Storage**: SQLite 3 (WAL mode, foreign_keys=ON, busy_timeout=5000)
**Testing**: pytest (já disponível no ambiente)
**Target Platform**: Linux (WSL2), macOS — CLI single-user
**Project Type**: CLI tool / pipeline infrastructure
**Performance Goals**: Migration <1s, CRUD <50ms, seed <5s
**Constraints**: Zero dependências externas, offline-capable, PostgreSQL-forward-compatible
**Scale/Scope**: 2 plataformas, ~30 epics, ~28 pipeline nodes, ~30 ADRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pragmatism | ✅ PASS | SQLite é a solução mais simples que funciona. Zero infra, built-in Python |
| II. Automate | ✅ PASS | seed_from_filesystem automatiza importação. CI automatiza validação |
| III. Structured Knowledge | ✅ PASS | BD estrutura estado que hoje é disperso em files |
| IV. Fast Action | ✅ PASS | Schema pronto no process_improvement.md. Implementação direta |
| V. Alternatives | ✅ PASS | Supabase vs SQLite avaliado no context.md. Trade-offs documentados |
| VI. Brutal Honesty | ✅ PASS | N/A |
| VII. TDD | ✅ PASS | pytest para CRUD, migration, seed, hash |
| VIII. Collaborative | ✅ PASS | Decisões validadas no discuss (context.md) |
| IX. Observability | ✅ PASS | Events table é o audit log. Pipeline runs trackeia custo/tokens |

## Project Structure

### Documentation (this feature)

```text
specs/002-sqlite-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
.pipeline/
├── migrations/
│   └── 001_initial.sql      # Schema DDL (8 tabelas + indexes)
└── madruga.db                # SQLite database (gitignored)

.specify/scripts/
├── db.py                     # Thin wrapper module (~250 linhas)
└── bash/
    └── check-platform-prerequisites.sh  # +flag --use-db

.specify/scripts/tests/
├── test_db.py                # pytest: CRUD, migration, seed, hash
└── conftest.py               # Fixtures: temp DB, sample platforms

.github/workflows/
└── ci.yml                    # Lint + LikeC4 build + Copier test

.claude/commands/madruga/
├── tech-research.md          # +guardrail [DADOS INSUFICIENTES]
└── adr-gen.md                # +guardrail URL obrigatório

.claude/knowledge/
└── pipeline-dag-knowledge.md # +step 5 SQLite instructions
```

**Structure Decision**: Módulo Python flat (`db.py` standalone) em vez de package. Razão: é um thin wrapper de ~250 linhas, não justifica `__init__.py` + múltiplos módulos. Quando crescer além de 400 linhas, refatorar para package.

## Complexity Tracking

Nenhuma violação de constitution detectada. Schema tem 8 tabelas — complexidade justificada:

| Tabela | Justificativa |
|--------|---------------|
| platforms | Core entity. FK target de tudo |
| pipeline_nodes | DAG nível 1 (13 nós). Staleness detection |
| epics | Shape Up lifecycle tracking |
| epic_nodes | DAG nível 2 (10 nós/epic). Observabilidade per-epic |
| decisions | ADR registry + decision log unificados. Idempotência |
| artifact_provenance | Quem gerou cada artefato. Validação de prerequisites |
| pipeline_runs | Tracking tokens/custo. Otimização |
| events | Audit log append-only. Timeline |

## Architecture Decisions

### 1. db.py API Design

**Pattern**: Funções standalone com connection como context manager. Sem classes, sem ORM.

```python
def get_conn() -> sqlite3.Connection:
    """Create connection with WAL, FK, busy_timeout. Auto-creates .pipeline/ dir."""

def migrate() -> None:
    """Run pending migrations from .pipeline/migrations/ in order."""

def upsert_platform(conn, platform_id, **kwargs) -> None:
    """INSERT OR REPLACE into platforms."""

def get_pipeline_nodes(conn, platform_id) -> list[dict]:
    """SELECT * FROM pipeline_nodes WHERE platform_id = ?"""
```

Todas funções recebem `conn` como primeiro argumento — caller controla lifecycle da connection.

### 2. Migration Runner

```python
def migrate():
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS _migrations (name TEXT PK, applied_at TEXT)")
    applied = {r['name'] for r in conn.execute("SELECT name FROM _migrations")}
    for sql_file in sorted(Path(MIGRATIONS_DIR).glob('*.sql')):
        if sql_file.name not in applied:
            conn.executescript(sql_file.read_text())  # executescript auto-commits
            conn.execute("INSERT INTO _migrations VALUES (?,?)", (sql_file.name, now()))
            conn.commit()
```

### 3. Seed Strategy

`seed_from_filesystem(conn, platform_id)`:
1. Ler `platforms/<name>/platform.yaml` → `upsert_platform()`
2. Para cada nó do pipeline (do YAML): checar se output files existem → `upsert_pipeline_node(status='done'|'pending', output_hash=compute_hash())`
3. Scan `epics/*/pitch.md` → `upsert_epic()` para cada
4. Não seed epic_nodes (ainda não rastreados), decisions (sem dados), runs (sem dados), events (sem dados)

### 4. Prerequisites --use-db Integration

No `check-platform-prerequisites.sh`, quando `--use-db` flag presente:

```bash
if [ "$USE_DB" = true ]; then
    # Query SQLite via Python one-liner
    STATUS_JSON=$(python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT/.specify/scripts')
from db import get_conn, get_pipeline_nodes
import json
conn = get_conn()
nodes = get_pipeline_nodes(conn, '$PLATFORM')
print(json.dumps({'platform': '$PLATFORM', 'nodes': nodes, 'source': 'db'}))
")
else
    # Existing file-existence logic
fi
```

### 5. GitHub Actions CI

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install pyyaml copier
      - run: python3 .specify/scripts/platform.py lint --all

  likec4:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npx likec4 build platforms/fulano/model/
      - run: npx likec4 build platforms/madruga-ai/model/

  templates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install copier pyyaml
      - run: copier copy .specify/templates/platform/ /tmp/test-plat --defaults -d platform_name=ci-test -d platform_title="CI Test" -d platform_description="test" -d lifecycle=design
      - run: python3 .specify/scripts/platform.py lint ci-test --platforms-dir /tmp
```

### 6. Guardrails

Adicionar às Cardinal Rules:

**tech-research.md:**
```markdown
- Se research (Context7, web search) não retornar dados para uma alternativa, marcar toda a linha como `[DADOS INSUFICIENTES]` e recomendar adiar a decisão. NUNCA fabricar dados.
- Toda afirmação factual DEVE ter URL ou referência verificável. Sem URL → marcar `[FONTE NÃO VERIFICADA]`.
```

**adr-gen.md:**
```markdown
- Toda referência DEVE ter URL ou título específico de documento verificável. Sem URL → `[FONTE NÃO VERIFICADA]`. NUNCA fabricar sources.
```
