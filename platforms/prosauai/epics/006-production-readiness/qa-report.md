---
type: qa-report
date: 2026-04-12
feature: "Epic 006 — Production Readiness"
branch: "epic/prosauai/006-production-readiness"
layers_executed: ["L1", "L2", "L3", "L4"]
layers_skipped: ["L5", "L6"]
findings_total: 10
pass_rate: "100%"
healed: 4
unresolved: 0
---

## QA Report — Epic 006 Production Readiness

**Data:** 12/04/2026 | **Branch:** epic/prosauai/006-production-readiness | **Arquivos alterados:** 29
**Layers executados:** L1, L2, L3, L4 | **Layers ignorados:** L5 (sem servidor rodando), L6 (Playwright indisponivel)

---

### Summary

| Status | Contagem |
|--------|----------|
| ✅ PASS | 6 |
| 🔧 HEALED | 4 |
| ⚠️ WARN | 3 |
| ❌ UNRESOLVED | 0 |
| ⏭️ SKIP | 2 |

---

### L1: Static Analysis

| Ferramenta | Resultado | Findings |
|------------|-----------|----------|
| ruff check | 🔧 2 erros → corrigidos | F841 variavel nao usada `original_execute` em test_retention.py:310; F401 import nao usado `os` em test_schema_isolation.py:15 |
| ruff format | 🔧 7 arquivos → reformatados | prosauai/main.py, prosauai/ops/migrate.py, prosauai/ops/retention.py, prosauai/ops/retention_cli.py, tests/ops/test_migrate.py, tests/ops/test_retention.py, tests/ops/test_schema_isolation.py |
| mypy/pyright | ⏭️ Skip | Nenhum type checker configurado no projeto |

---

### L2: Automated Tests

| Suite | Passed | Failed | Skipped |
|-------|--------|--------|---------|
| pytest (tests/ops/) | 67 | 0 | 0 |

**Detalhamento por modulo:**

| Arquivo | Testes | Status |
|---------|--------|--------|
| test_migrate.py | 12 | ✅ PASS |
| test_partitions.py | 13 | ✅ PASS |
| test_retention.py | 17 | ✅ PASS |
| test_schema_isolation.py | 25 | ✅ PASS (integracao com Postgres real via Docker) |

---

### L3: Code Review

| Arquivo | Finding | Severidade | Status |
|---------|---------|------------|--------|
| docker-compose.prod.yml:24 | `volumes: []` nao remove volumes da base em Docker Compose v5. Sequences sao merged (appendados), nao substituidos. Phoenix mantinha volume SQLite `phoenix_data` em prod, contrariando a intencao do override. | S2 | 🔧 HEALED |
| tests/ops/test_retention.py:310 | Variavel `original_execute` atribuida mas nunca usada | S4 | 🔧 HEALED |
| tests/ops/test_schema_isolation.py:15 | Import `os` nao utilizado | S4 | 🔧 HEALED |
| docker-compose.prod.yml:62 | retention-cron usa env var `DATABASE_URL` com credenciais default (prosauai:prosauai). Para deploy em Supabase, operador precisa usar service_role com BYPASSRLS. `.env.example` documenta `RETENTION_DATABASE_URL` mas o container le `DATABASE_URL` — naming mismatch entre documentacao e config. Funciona em Docker local (owner bypassa RLS), requer atencao manual em Supabase prod. | S3 | ⚠️ WARN |
| prosauai/ops/retention.py:70 | `from datetime import date, timedelta` importado dentro do corpo da funcao `purge_expired_messages` (lazy import). Funciona mas e nao-convencional — preferivel import no topo do modulo. | S4 | ⚠️ WARN |
| prosauai/db/pool.py:38 | `create_pool()` nao protege contra chamada dupla — pool anterior pode leakar. Lifespan garante chamada unica, mas guard defensivo (`if _pool is not None: return _pool`) seria mais seguro. | S4 | ⚠️ WARN |

**Analise cross-file:**

| Verificacao | Status | Detalhe |
|-------------|--------|---------|
| Migrations criam tabelas em schema `prosauai` | ✅ | Todas 7 tabelas de negocio em `prosauai.`, zero objetos em `auth`/`public` |
| Enums prefixados com `prosauai.` | ✅ | `prosauai.conversation_status`, `prosauai.close_reason`, `prosauai.message_direction` |
| SET search_path nas migrations com enums | ✅ | 003_conversations.sql e 004_messages.sql usam `SET search_path TO prosauai, prosauai_ops, public;` |
| `prosauai_ops.tenant_id()` com SECURITY DEFINER | ✅ | Migration 001, SET search_path = '' (hardened) |
| RLS policies referenciam `prosauai_ops.tenant_id()` | ✅ | Todas migrations 002-006 |
| FK eval_scores.message_id removida (PG partition limitation) | ✅ | Comentario explicativo presente em 006_eval_scores.sql |
| Messages particionada por RANGE(created_at) | ✅ | PK composta (id, created_at), 3 particoes iniciais via DO block |
| Seed data idempotente (ON CONFLICT DO UPDATE) | ✅ | 007_seed_data.sql usa pure SQL sem psql-specifics |
| pool.py search_path configurado | ✅ | `server_settings={"search_path": "prosauai,prosauai_ops,public"}` |
| migrate.py search_path configurado | ✅ | Mesmo search_path no asyncpg.connect() |
| migrate.py advisory lock | ✅ | `pg_advisory_lock(hashtext('prosauai_migrations'))` previne corrida |
| migrate.py command_timeout | ✅ | 300s timeout previne migration presa |
| retention.py error isolation | ✅ | Cada purge function em try/except individual, RuntimeError no final |
| retention.py ctid subquery pattern | ✅ | `purge_expired_traces` usa `WHERE ctid IN (SELECT ctid ... LIMIT $2)` |
| partitions.py input validation | ✅ | `_validate_table()` com regex previne SQL injection em DDL |
| partitions.py unparseable name logging | ✅ | Warnings para nomes de particao nao-parseaveis |
| retention_cli.py statement_timeout | ✅ | 300s timeout por statement |
| Docker log rotation em todos services | ✅ | YAML anchor `x-logging` aplicado a postgres, redis, phoenix, api |
| Phoenix Postgres backend em prod | ✅ | `PHOENIX_SQL_DATABASE_SCHEMA=observability` (env var oficial) |
| Netdata bind localhost only | ✅ | `127.0.0.1:19999:19999` |
| Resource limits em containers auxiliares | ✅ | Netdata 256M, retention-cron 128M |
| initdb.d mount removido | ✅ | Migrations via runner no startup da API |
| main.py fail-fast | ✅ | RuntimeError se migration falha, API nao inicia |
| audit_log nunca purgado | ✅ | Teste dedicado confirma que nenhum SQL referencia `audit_log` |

---

### L4: Build Verification

| Comando | Resultado | Duracao |
|---------|-----------|---------|
| `docker compose config` | ✅ Valido | <1s |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` | ✅ Valido — 6 services | <1s |
| `python3 -m ruff check` | ✅ Limpo (pos-fix) | <1s |
| `python3 -m ruff format --check` | ✅ Limpo (pos-fix) | <1s |
| `python3 -m pytest tests/ops/ -v` | ✅ 67 passed | 3.8s |

**Smoke tests de entrypoints Python:**

| Entrypoint | Teste | Resultado |
|------------|-------|-----------|
| `prosauai.ops.migrate` | CLI com argparse | ✅ Importavel, --help disponivel |
| `prosauai.ops.retention_cli` | CLI com argparse | ✅ Importavel, --help disponivel |
| `prosauai.main` | FastAPI app com lifespan | ✅ Importavel (FastAPI opcional, graceful) |

---

### L5: API Testing

⏭️ **Skip** — Nenhum servidor rodando. API endpoints nao testados em runtime.

---

### L6: Browser Testing

⏭️ **Skip** — Playwright MCP indisponivel. Epic e infraestrutural, sem UI web.

---

### Heal Loop

| # | Layer | Finding | Iteracoes | Fix | Status |
|---|-------|---------|-----------|-----|--------|
| 1 | L1 | F841 variavel nao usada `original_execute` em test_retention.py | 1 | Removida atribuicao (Edit) | 🔧 HEALED |
| 2 | L1 | F401 import nao usado `os` em test_schema_isolation.py | 1 | Removido import (Edit) | 🔧 HEALED |
| 3 | L1 | 7 arquivos com formato incorreto | 1 | `ruff format` aplicado | 🔧 HEALED |
| 4 | L3 | `volumes: []` nao efetivo em Docker Compose v5 | 1 | Alterado para `volumes: !reset []` (Edit) | 🔧 HEALED |

---

### Arquivos Alterados (pelo heal loop)

| Arquivo | Linha | Mudanca |
|---------|-------|---------|
| tests/ops/test_retention.py | 310 | Removida atribuicao `original_execute = conn.execute` |
| tests/ops/test_schema_isolation.py | 15 | Removido `import os` |
| prosauai/main.py | — | Reformatado (ruff format) |
| prosauai/ops/migrate.py | — | Reformatado (ruff format) |
| prosauai/ops/retention.py | — | Reformatado (ruff format) |
| prosauai/ops/retention_cli.py | — | Reformatado (ruff format) |
| tests/ops/test_migrate.py | — | Reformatado (ruff format) |
| tests/ops/test_retention.py | — | Reformatado (ruff format) |
| tests/ops/test_schema_isolation.py | — | Reformatado (ruff format) |
| docker-compose.prod.yml | 24 | `volumes: []` → `volumes: !reset []` |

---

### Findings dos Relatorios Upstream — Status de Resolucao

| Relatorio | ID | Severidade | Status QA | Detalhe |
|-----------|-----|------------|-----------|---------|
| analyze-post | P1 | CRITICAL | N/A | Codigo no repo errado — fora do escopo do QA (decisao organizacional) |
| analyze-post | P2 | HIGH | ✅ Verificado | DELETE...LIMIT corrigido → subquery ctid pattern em retention.py:261-266 |
| analyze-post | P3 | HIGH | ✅ Verificado | spec.md FR-010 e US6-AC4 atualizados (vide judge report) |
| analyze-post | P4 | MEDIUM | ✅ Verificado | spec.md FR-015 e FR-020 usam PHOENIX_SQL_DATABASE_SCHEMA |
| analyze-post | P5 | MEDIUM | ⚠️ Aceito | Validacao pos-startup do Phoenix como divida tecnica. Cron faz check indireto |
| analyze-post | P6 | MEDIUM | ✅ Verificado | ER diagram corrigido (vide judge report) |
| analyze-post | P7 | LOW | ✅ Verificado | plan.md atualizado: 34 tasks |
| analyze-post | P8 | LOW | ⚠️ Aceito | Nome `observability.spans` hardcoded — `IF EXISTS` previne erros |
| analyze-post | P9 | LOW | ✅ Verificado | docker-compose.prod.yml ja tem comentario VPS na linha 5 |
| judge | #1 BLOCKER | CRITICAL | ✅ Verificado | DELETE...LIMIT → subquery ctid (retention.py:261-266) |
| judge | #2 | WARNING | ✅ Verificado | Enums prefixados com `prosauai.` + SET search_path |
| judge | #3 | WARNING | ✅ Verificado | migrate.py search_path no asyncpg.connect() |
| judge | #4 | WARNING | ✅ Verificado | retention_cli.py search_path + statement_timeout |
| judge | #5 | WARNING | ✅ Verificado | Advisory lock no migration runner |
| judge | #6 | WARNING | ✅ Verificado | _validate_table() regex em partitions.py |
| judge | #7 | WARNING | ✅ Verificado | log.warning para unparseable partition names |
| judge | #8 | WARNING | ✅ Verificado | Error isolation em run_retention() |
| judge | #9 | WARNING | ✅ Verificado | command_timeout=300.0 no migrate.py |
| judge | #10 | WARNING | ⚠️ Aceito | sleep 86400 loop — tech debt documentado |

---

### Licoes Aprendidas

1. **Docker Compose `volumes: []` nao limpa volumes em override files.** Sequences em Docker Compose sao merged (appendadas), nao substituidas. Para limpar, usar `!reset []` (Compose v2.24+/v5+). Este e um gotcha comum que causa volumes orfaos em prod.

2. **Testes com mock mascaram bugs reais de SQL.** O bug original DELETE...LIMIT (P2 do analyze-post) nunca foi detectado pelos testes unitarios porque `conn.execute` e mockado. Os testes de schema_isolation (integracao com Postgres real via Docker) sao muito mais valiosos para detectar problemas reais.

3. **ruff format deve ser executado como pre-commit hook.** 7 arquivos estavam fora do formato — automatizar via hook previne drift.

4. **Code review cross-file e essencial em epics infraestruturais.** Verificar que migrations, pool.py, migrate.py e retention.py usam o mesmo search_path exigiu leitura de 4+ arquivos em conjunto. Um review file-by-file perderia a inconsistencia.

5. **Naming convention entre .env.example e docker-compose deve ser identica.** `RETENTION_DATABASE_URL` documentado vs `DATABASE_URL` usado no container cria confusao para o operador. Padronizar nomes de env vars entre docs e configs.

---

handoff:
  from: qa
  to: madruga:reconcile
  context: "QA completo para epic 006 production readiness. 67 testes passam, 4 findings corrigidos no heal loop (2 lint, 1 format, 1 Docker Compose volumes bug). 3 WARNs abertos (naming mismatch DATABASE_URL, lazy import, pool guard). Todos findings do analyze-post e judge verificados — fixes confirmados. Pronto para reconciliacao de documentacao."
  blockers: []
  confidence: Alta
  kill_criteria: "Se os testes de integracao (test_schema_isolation.py) comecarem a falhar em CI por falta de Docker, o coverage real de schema isolation cai drasticamente — testes unitarios com mock nao sao suficientes."
