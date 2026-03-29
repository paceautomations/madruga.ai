---
title: "Implementation Context — Epic 006"
updated: 2026-03-29
---
# Epic 006 — Implementation Context

## Captured Decisions

| # | Area | Decision | Alternativas Consideradas | Referência Arquitetural |
|---|------|---------|--------------------------|------------------------|
| 1 | BD | SQLite local em `.pipeline/madruga.db` (raiz do repo). Um BD central para todas plataformas | Supabase (over-engineering para CLI single-user), BD por plataforma (complica queries cross-platform) | Blueprint §1.4 (já menciona SQLite + WAL), process_improvement.md §BD |
| 2 | BD Config | WAL mode + `foreign_keys=ON` + `busy_timeout=5000` | journal_mode=DELETE (mais lento), sem FK (menos seguro) | Blueprint §1.6 (SQLite write lock: busy_timeout=5000ms WAL mode) |
| 3 | Schema | 8 tabelas: platforms, pipeline_nodes, epics, epic_nodes, decisions, artifact_provenance, pipeline_runs, events. SEM tags, elements, relationships (fases futuras) | Schema completo com 11 tabelas (over-engineering para fase 1) | process_improvement.md §Schema SQLite |
| 4 | Módulo | `db.py` em `.specify/scripts/db.py` — thin wrapper stdlib, ~200-300 linhas, zero deps externas. Context manager para connections | ORM (SQLAlchemy — dep externa), raw SQL everywhere (boilerplate) | Constitution §I (simplicidade), Blueprint §3.1 (Python 3.11+) |
| 5 | Migrations | SQL files numerados em `.pipeline/migrations/`. Runner em `db.py migrate()`. Tabela `_migrations` para tracking | Alembic (dep externa), manual DDL (sem versionamento) | process_improvement.md §db.py |
| 6 | .gitignore | `.pipeline/madruga.db` no .gitignore. Migrations (.sql) versionadas no git. BD é estado local, reproduzível via seed | BD versionado no git (merge conflicts, binary) | Blueprint §1.3 (nenhum state no repo) |
| 7 | Prerequisites | `check-platform-prerequisites.sh` ganha flag `--use-db` já neste epic. Quando flag presente, consulta SQLite em vez de file existence. Flag é opt-in (backward compatible) | Adiar para epic 007 (perde oportunidade de testar integração end-to-end) | process_improvement.md §A3 |
| 8 | Guardrails | Adicionar `[DADOS INSUFICIENTES]` como escape hatch + URL obrigatório para sources em tech-research.md e adr-gen.md | Manter sem guardrails (hallucination risk), two-pass research (dobra latência) | process_improvement.md §A11 |
| 9 | CI/CD | GitHub Actions workflow completo: `platform.py lint --all` + `likec4 build` por plataforma + copier template tests. Simples e eficiente | Só lint (incompleto), lint + testes + deploy (over-engineering) | process_improvement.md §CI/CD |
| 10 | Seed | `db.py seed_from_filesystem(platform_id)` importa estado atual: scan platform.yaml, check file existence para pipeline_nodes, scan epics/ para epics table | Manual INSERT (tedioso), sem seed (BD vazio) | process_improvement.md §F1 |

## Resolved Gray Areas

### 1. API Surface do db.py
**Pergunta:** Quantas e quais funções?
**Resposta:** 2 por tabela (upsert + query) + utilities = ~20 funções:
- `get_conn()`, `migrate()`, `compute_file_hash(path)`
- `upsert_platform()`, `get_platform()`
- `upsert_pipeline_node()`, `get_pipeline_nodes()`, `get_stale_nodes()`
- `upsert_epic()`, `get_epics()`
- `upsert_epic_node()`, `get_epic_nodes()`
- `insert_decision()`, `get_decisions()`
- `insert_provenance()`, `get_provenance()`
- `insert_run()`, `complete_run()`, `get_runs()`
- `insert_event()`, `get_events()`
- `seed_from_filesystem(platform_id)`

### 2. Como skills chamam db.py
**Pergunta:** Subprocess ou import direto?
**Resposta:** Import direto. Skills rodam em Claude Code que executa Python. No step 5, a skill instrui: "Run `python3 -c 'from db import ...; ...'`" ou o script de prerequisites faz `import db`. Sem subprocess intermediário.

### 3. Scope do GitHub Actions
**Pergunta:** O que o CI roda?
**Resposta:** Um workflow `.github/workflows/ci.yml` com 3 jobs paralelos:
1. **lint**: `platform.py lint --all`
2. **likec4**: `likec4 build` para cada `platforms/*/model/`
3. **templates**: `copier copy .specify/templates/platform/ /tmp/test --defaults` + validar output
Trigger: push to main + PRs.

### 4. BD path relativo vs absoluto
**Pergunta:** Como db.py encontra o BD?
**Resposta:** Path relativo à raiz do repo: `.pipeline/madruga.db`. `db.py` resolve via `Path(__file__).parent.parent.parent / '.pipeline' / 'madruga.db'`. Funciona de qualquer working directory.

## Applicable Constraints

- **Zero dependências externas** — só stdlib Python (sqlite3, hashlib, json, pathlib, uuid)
- **Backward compatible** — `--use-db` é opt-in. Scripts sem a flag continuam funcionando com file existence
- **Offline-first** — SQLite funciona sem rede. Zero dependência de serviços externos
- **PostgreSQL-forward** — Schema desenhado para migração mecânica para PG (~1 dia quando necessário)
- **Constitution §VII** — TDD: testes para CRUD e migration runner

## Suggested Approach

1. **Wave 1 — CI**: GitHub Actions workflow com 3 jobs
2. **Wave 2 — Schema**: `.pipeline/` dir + .gitignore + `001_initial.sql` + `db.py` base (conn, migrate, hash)
3. **Wave 3 — CRUD**: Funções upsert/insert/get para cada tabela
4. **Wave 4 — Integration**: `--use-db` no prerequisites checker + seed + `pipeline-dag-knowledge.md` com instruções step 5
5. **Wave 5 — Guardrails**: Directives em tech-research.md e adr-gen.md
6. **Wave 6 — Tests**: pytest para CRUD, migration, seed, hash
