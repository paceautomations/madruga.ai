# Implementation Plan: Production Readiness

**Branch**: `epic/prosauai/006-production-readiness` | **Date**: 2026-04-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `epics/006-production-readiness/spec.md`

## Summary

Preparar infraestrutura ProsauAI para deploy em VPS de produção, resolvendo 7 gaps: schema isolation (Supabase-safe), Phoenix Postgres backend, log persistence com rotation, data retention cron (LGPD compliance), particionamento de messages, host monitoring e migration runner automatizado. Zero mudança em lógica de negócio — escopo puramente infraestrutural.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: asyncpg >=0.30 (já existente), structlog (já existente), FastAPI >=0.115 (já existente)
**Storage**: PostgreSQL 15 (Supabase para dados de negócio, Postgres local VPS para traces Phoenix)
**Testing**: pytest + asyncpg (testes contra Postgres real via testcontainers ou fixture)
**Target Platform**: VPS Linux (Docker Compose) — mínimo 2 vCPU, 4GB RAM, 40GB SSD
**Project Type**: Infraestrutura / DevOps (migrations, Docker config, scripts operacionais)
**Performance Goals**: Migration runner < 30s total. Partition DROP < 100ms. Batch DELETE < 5s por iteração.
**Constraints**: Zero downtime de lógica de negócio. Zero dependências novas (usar apenas asyncpg + structlog + stdlib).
**Scale/Scope**: 2-10 tenants Fase 1, ~1000 msgs/dia, ~365K msgs/ano.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Status | Evid��ncia |
|---|---|---|
| **I. Pragmatismo** | ✅ PASS | Soluções mais simples escolhidas: script custom vs Alembic, Netdata vs Prometheus, sleep loop vs crontab |
| **II. Automatizar tarefas repetitivas** | ✅ PASS | Migration runner automatizado, cron de retention automatizado, partições criadas automaticamente |
| **III. Conhecimento estruturado** | ✅ PASS | research.md, data-model.md, contracts/ documentam todas as decisões |
| **IV. Ação rápida** | ✅ PASS | Forward-only migrations (sem rollback), TDD para scripts novos |
| **V. Alternativas e trade-offs** | ✅ PASS | Cada decisão tem ≥2 alternativas documentadas em research.md |
| **VI. Honestidade brutal** | ✅ PASS | Correção da spec: PG 15 NÃO suporta UNIQUE global em partitioned tables. FK eval_scores removida. |
| **VII. TDD** | ✅ PASS | Testes para migration runner, retention cron, partitions manager |
| **VIII. Decisão colaborativa** | ✅ PASS | Decisões documentadas com racional em research.md |
| **IX. Observabilidade e logging** | ✅ PASS | Log rotation configurado, retention cron com structured logging, Netdata para host monitoring |

### Correções Identificadas na Pesquisa

1. **UNIQUE index global em tabela particionada**: A spec (FR-010) e o pitch (S5, Opção A) assumiam que PG 15 suporta `UNIQUE(id)` em tabela particionada por `created_at`. Isso é **INCORRETO** — PG exige partition key em todas as unique constraints. **Solução**: FK `eval_scores.message_id` removida; integridade via UUID v4 + validação na app.
2. **Phoenix schema via search_path**: A spec (FR-020) e clarifications propunham `options=-c search_path=observability` na URL. Phoenix suporta env var dedicada `PHOENIX_SQL_DATABASE_SCHEMA=observability` desde v4.33.0 — mecanismo mais confiável.

## Project Structure

### Documentation (this feature)

```text
epics/006-production-readiness/
├── plan.md              # Este arquivo
├── research.md          # Phase 0 — pesquisa técnica
├── data-model.md        # Phase 1 — schema layout + entidades
├── quickstart.md        # Phase 1 — guia de setup dev/prod
├── contracts/
│   ���── retention-cli.md # Contract do CLI de retention
│   └── migration-runner.md # Contract do migration runner
└── tasks.md             # Phase 2 — gerado por /speckit.tasks
```

### Source Code (prosauai repository)

```text
prosauai/
├── db/
│   └── pool.py              # MODIFICADO: adicionar search_path
├── ops/
│   ├── __init__.py           # NOVO: package ops
│   ├── migrate.py            # NOVO: migration runner (~80 LOC)
│   ├─�� partitions.py         # NOVO: gerenciamento de partições (~60 LOC)
│   ├── retention.py          # NOVO: lógica de purge (~120 LOC)
│   └── retention_cli.py      # NOVO: CLI entry point (~40 LOC)
├── config.py                # MODIFICADO: adicionar settings de retention (opcional)
└── main.py                  # MODIFICADO: chamar migrate no lifespan

migrations/
├── 001_create_schema.sql    # REESCRITA: prosauai + prosauai_ops schemas
├── 002_customers.sql        # REESCRITA: prosauai.customers + RLS prosauai_ops
├─�� 003_conversations.sql    # REESCRITA: prosauai.conversations + RLS prosauai_ops
├── 003b_conversation_states.sql # REESCRITA: prosauai.conversation_states
├── 004_messages.sql         # REESCRITA: particionada + prosauai schema
├── 005_agents_prompts.sql   # REESCRITA: prosauai schema + RLS prosauai_ops
├── 006_eval_scores.sql      # REESCRITA: prosauai schema, FK message_id removida
└── 007_seed_data.sql        # REESCRITA: SQL puro (sem \set psql), schema prefix

docker-compose.yml           # MODIFICADO: log rotation em todos services
docker-compose.prod.yml      # NOVO: overrides de produção

tests/
└── ops/
    ├── __init__.py
    ├── test_migrate.py       # NOVO: testes migration runner
    ├── test_partitions.py    # NOVO: testes partition management
    └── test_retention.py     # NOVO: testes retention cron
```

**Structure Decision**: Módulo `prosauai/ops/` agrupa todos os scripts operacionais (migrations, retention, partitions). Separado de `prosauai/db/` (connection pool, repositories) para distinção clara entre operação e runtime. Testes em `tests/ops/`.

## Complexity Tracking

| Aspecto | Justificativa | Alternativa Simples Rejeitada |
|---|---|---|
| Particionamento de messages | Purge via DROP PARTITION é instantâneo vs DELETE lento em tabela monolítica. Fazer agora = trocar CREATE TABLE; depois = downtime + pg_rewrite | Sem particionamento: purge requer DELETE massivo com write amplification |
| Migration runner custom | ~80 LOC vs Yoyo/Alembic (nova dependência + config). Forward-only, sem rollback | `docker-entrypoint-initdb.d` (status quo): só executa na primeira init do volume |

---

## Phase 0: Research (Completo)

Todas as incógnitas técnicas foram resolvidas. Ver [research.md](research.md).

### Decisões-Chave

| # | Decisão | Racional | Alternativas Rejeitadas |
|---|---|---|---|
| 1 | Schemas `prosauai` + `prosauai_ops` | Supabase-safe, isolamento claro | `public` (conflito), schema único (mistura dados + ops) |
| 2 | Migration runner com asyncpg | Zero deps novas, alinhado com stack | Yoyo (psycopg2), Alembic (SQLAlchemy), dbmate (Go) |
| 3 | Particionamento RANGE(created_at) mensal | Purge instantâneo via DDL | Sem partição (DELETE lento), partição por tenant (sem benefício de purge) |
| 4 | FK eval_scores.message_id removida | PG não suporta UNIQUE(id) em partitioned table | FK composta (coluna extra), trigger (frágil) |
| 5 | Phoenix via PHOENIX_SQL_DATABASE_SCHEMA | Env var oficial desde v4.33.0 | search_path na URL (não oficial), DB separado (overengineering) |
| 6 | Docker json-file rotation via YAML anchor | Custo zero, previne disk-full | Log aggregation externo (custo, complexidade) |
| 7 | Netdata para host monitoring | Setup 5min, UI built-in, temporário até epic 013 | Prometheus+Grafana (overengineering), script bash (insuficiente) |
| 8 | Retention cron via container sleep loop | Portável, idempotente, sem dependência de host crontab | Host crontab (não portável), systemd timer (não Docker) |

---

## Phase 1: Design (Completo)

### Data Model

Ver [data-model.md](data-model.md) para schema layout completo, incluindo:
- Schema `prosauai`: 7 tabelas de negócio (messages particionada)
- Schema `prosauai_ops`: `tenant_id()` function + `schema_migrations` table
- Schema `observability`: reservado para Phoenix (gerenciado pelo Phoenix)
- Schema `admin`: reservado para epic 013 (criado vazio)

### Contracts

Ver [contracts/](contracts/) para interfaces dos componentes novos:
- [retention-cli.md](contracts/retention-cli.md): CLI de purge com --dry-run, regras de retention por tabela
- [migration-runner.md](contracts/migration-runner.md): Runner com tracking, idempotência, fail-fast

### Quickstart

Ver [quickstart.md](quickstart.md) para guia de setup dev e prod.

---

## Phase 2: Implementation Plan

### Fase 1 — Schema Isolation + Migration Runner (estimativa: 2 dias)

#### Task 1.1 — Reescrever migration 001_create_schema.sql

**O que muda**: Trocar `CREATE SCHEMA IF NOT EXISTS auth` por criação de `prosauai`, `prosauai_ops`, `observability`, `admin`. Mover `tenant_id()` para `prosauai_ops`.

**Arquivo**: `migrations/001_create_schema.sql`

**De** (atual):
```sql
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.tenant_id() ...
```

**Para** (novo):
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Business data schema
CREATE SCHEMA IF NOT EXISTS prosauai;
-- Operational helpers (RLS functions, migration tracking)
CREATE SCHEMA IF NOT EXISTS prosauai_ops;
-- Phoenix observability (managed by Phoenix)
CREATE SCHEMA IF NOT EXISTS observability;
-- Admin (reserved for epic 013 — TenantStore Postgres)
CREATE SCHEMA IF NOT EXISTS admin;

-- RLS helper function (ADR-011 hardening)
CREATE OR REPLACE FUNCTION prosauai_ops.tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT current_setting('app.current_tenant_id', true)::uuid
$$;

-- Migration tracking table
CREATE TABLE IF NOT EXISTS prosauai_ops.schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum   TEXT
);
```

#### Task 1.2 — Reescrever migrations 002-003b com schema prefix

**Arquivos**: `002_customers.sql`, `003_conversations.sql`, `003b_conversation_states.sql`

**Mudanças por arquivo**:
- Prefixar `CREATE TABLE` com `prosauai.` (ex: `prosauai.customers`)
- Trocar `auth.tenant_id()` por `prosauai_ops.tenant_id()` em policies
- Prefixar indexes com `prosauai.` (ex: `ON prosauai.customers(tenant_id)`)
- FKs cross-table: `REFERENCES prosauai.conversations(id)` etc.

#### Task 1.3 — Reescrever migration 004_messages.sql com particionamento

**Arquivo**: `migrations/004_messages.sql`

**Mudanças**:
- Schema prefix `prosauai.messages`
- `PARTITION BY RANGE (created_at)`
- PK composta `PRIMARY KEY (id, created_at)`
- Remover PK simples `id UUID PRIMARY KEY`
- Manter indexes (tenant, conversation) — herdados pelas partições
- Criar 3 partições iniciais (mês atual + 2 futuros)

#### Task 1.4 — Reescrever migrations 005-007 com schema prefix

**Arquivos**: `005_agents_prompts.sql`, `006_eval_scores.sql`, `007_seed_data.sql`

**Mudanças em 005**: Prefixar `prosauai.agents`, `prosauai.prompts`, RLS com `prosauai_ops.tenant_id()`
**Mudanças em 006**: Prefixar `prosauai.eval_scores`, **remover FK** `REFERENCES messages(id)` (substituir por comentário explicativo), RLS com `prosauai_ops.tenant_id()`
**Mudanças em 007**: Reescrever sem `\set` psql. Usar UUIDs hardcoded. Prefixar tabelas com `prosauai.`.

#### Task 1.5 — Implementar migration runner (prosauai/ops/migrate.py)

**Arquivo novo**: `prosauai/ops/migrate.py` (~80 LOC)

**Comportamento**:
1. Conecta via asyncpg (mesma DSN da app)
2. Bootstrap: cria `prosauai_ops` schema + `schema_migrations` table se não existirem
3. Lista `migrations/*.sql` em ordem numérica
4. Para cada não-registrada: execute SQL em transaction, registra em schema_migrations
5. Log structured (structlog) de cada migration aplicada

**Ref**: [contracts/migration-runner.md](contracts/migration-runner.md)

#### Task 1.6 — Implementar partition manager (prosauai/ops/partitions.py)

**Arquivo novo**: `prosauai/ops/partitions.py` (~60 LOC)

**Funções**:
- `ensure_future_partitions(conn, months_ahead=3)`: Cria partições para os próximos N meses (IF NOT EXISTS)
- `drop_expired_partitions(conn, retention_days=90)`: Remove partições onde max(created_at) < threshold
- `list_partitions(conn)`: Lista partições existentes com contagem de rows

#### Task 1.7 — Atualizar pool.py com search_path

**Arquivo**: `prosauai/db/pool.py`

**Mudança única** no `create_pool()`:
```python
pool = await asyncpg.create_pool(
    dsn=settings.database_url,
    min_size=settings.pool_min_size,
    max_size=settings.pool_max_size,
    command_timeout=60.0,
    server_settings={'search_path': 'prosauai,prosauai_ops,public'},
)
```

Zero mudança em queries existentes — `search_path` resolve tabelas transparentemente.

#### Task 1.8 — Integrar migration runner no startup da API

**Arquivo**: `prosauai/main.py` (lifespan)

**Mudança**: Antes de `create_pool()`, chamar `await run_migrations(settings.database_url, migrations_dir)`. Se falhar, app não inicia (fail-fast).

#### Task 1.9 — Testes: migration runner + schema isolation

**Arquivo novo**: `tests/ops/test_migrate.py`

**Testes**:
- Migration aplica DDL corretamente (schema criado, tabelas existem)
- Re-execução é idempotente (nenhuma migration re-aplicada)
- Migration com erro faz rollback e não aplica seguintes
- Checksum detecta drift (warning no log)

### Fase 2 — Docker Compose Production + Log Rotation (estimativa: 1 dia)

#### Task 2.1 — Adicionar log rotation ao docker-compose.yml

**Arquivo**: `docker-compose.yml`

**Mudança**: Adicionar YAML anchor e aplicar a todos os services:
```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"

services:
  api:
    logging: *default-logging
    ...
  redis:
    logging: *default-logging
    ...
  postgres:
    logging: *default-logging
    ...
  phoenix:
    logging: *default-logging
    ...
```

#### Task 2.2 — Remover initdb.d mount do Postgres

**Arquivo**: `docker-compose.yml`

**Mudança**: Remover `./migrations:/docker-entrypoint-initdb.d:ro` do volume do Postgres. Migrations agora são gerenciadas pelo runner no startup da API.

#### Task 2.3 — Adicionar migration runner ao startup da API no docker-compose

**Arquivo**: `docker-compose.yml`

**Mudança**: Ajustar command da API para executar migrations antes do uvicorn (se necessário — se feito via lifespan no main.py, nenhuma mudança no compose é necessária).

#### Task 2.4 — Criar docker-compose.prod.yml

**Arquivo novo**: `docker-compose.prod.yml`

**Conteúdo**:
```yaml
# Production overrides — use with: docker compose -f docker-compose.yml -f docker-compose.prod.yml up
# Minimum VPS requirements: 2 vCPU, 4GB RAM, 40GB SSD

x-logging: &prod-logging
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"

services:
  phoenix:
    environment:
      PHOENIX_SQL_DATABASE_URL: postgresql://${POSTGRES_USER:-prosauai}:${POSTGRES_PASSWORD:-prosauai}@postgres:5432/${POSTGRES_DB:-prosauai}
      PHOENIX_SQL_DATABASE_SCHEMA: observability
    volumes: []  # Remove phoenix_data SQLite volume

  netdata:
    image: netdata/netdata:stable
    ports:
      - "127.0.0.1:19999:19999"
    cap_add:
      - SYS_PTRACE
    security_opt:
      - apparmor:unconfined
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - netdataconfig:/etc/netdata
      - netdatalib:/var/lib/netdata
      - netdatacache:/var/cache/netdata
    logging: *prod-logging
    deploy:
      resources:
        limits:
          memory: 256M
    restart: unless-stopped

  retention-cron:
    build:
      context: .
      dockerfile: Dockerfile
    command: >
      sh -c "while true; do
        python -m prosauai.ops.retention_cli --dry-run=false;
        sleep 86400;
      done"
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-prosauai}:${POSTGRES_PASSWORD:-prosauai}@postgres:5432/${POSTGRES_DB:-prosauai}
    logging: *prod-logging
    deploy:
      resources:
        limits:
          memory: 128M
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

volumes:
  netdataconfig:
  netdatalib:
  netdatacache:
```

### Fase 3 — Retention Cron + Partitions (estimativa: 1.5 dias)

#### Task 3.1 — Implementar retention.py (lógica de purge)

**Arquivo novo**: `prosauai/ops/retention.py` (~120 LOC)

**Funções**:
- `purge_expired_messages(conn, retention_days=90, dry_run=True)`: Drop partições expiradas via `partitions.drop_expired_partitions()`
- `purge_expired_conversations(conn, retention_days=90, dry_run=True)`: DELETE batch em conversations fechadas
- `purge_expired_eval_scores(conn, retention_days=90, dry_run=True)`: DELETE batch em eval_scores
- `purge_expired_traces(conn, retention_days=90, dry_run=True)`: DELETE em tabelas Phoenix no schema `observability`
- `run_retention(conn, dry_run=True)`: Orquestra todas as funções acima + cria partições futuras

**Ref**: [contracts/retention-cli.md](contracts/retention-cli.md)

#### Task 3.2 — Implementar retention_cli.py (CLI entry point)

**Arquivo novo**: `prosauai/ops/retention_cli.py` (~40 LOC)

**Comportamento**: Argparse com `--dry-run` (default True), `--database-url`. Chama `asyncio.run(run_retention(...))`. Structured logging via structlog.

#### Task 3.3 �� Testes: retention + partitions

**Arquivos novos**: `tests/ops/test_retention.py`, `tests/ops/test_partitions.py`

**Testes retention**:
- Dry-run lista dados sem deletar
- Purge real remove apenas dados expirados
- Partições são criadas para 3 meses futuros
- Partições expiradas são removidas
- Batch DELETE respeita LIMIT
- Re-execução é idempotente

**Testes partitions**:
- `ensure_future_partitions` cria partições corretamente (idempotente)
- `drop_expired_partitions` remove apenas expiradas
- `list_partitions` retorna contagem correta

### Fase 4 — Documentação + Finalização (estimativa: 0.5 dia)

#### Task 4.1 — Atualizar ADR-011 (pool + RLS)

Trocar `auth.tenant_id()` por `prosauai_ops.tenant_id()`. Adicionar seção sobre schema isolation com `search_path` no pool.

#### Task 4.2 — Atualizar ADR-018 (data retention)

Adicionar seção "Implementation" referenciando `prosauai/ops/retention.py`. Documentar particionamento como estratégia de purge.

#### Task 4.3 — Atualizar ADR-020 (Phoenix)

Documentar `PHOENIX_SQL_DATABASE_SCHEMA=observability` como configuração de produção. Adicionar nota sobre SQLite dev vs Postgres prod.

#### Task 4.4 — Criar ADR-024 (schema isolation)

Novo ADR documentando decisão de schemas `prosauai` + `prosauai_ops`. Motivação: compatibilidade Supabase, isolamento de namespaces.

---

## Resumo de Estimativas

| Fase | Escopo | Estimativa | LOC Estimado |
|---|---|---|---|
| 1 — Schema + Migrations | 9 tasks: reescrita de 7 migrations, migration runner, partition manager, pool.py, testes | 2 dias | ~500 LOC (migrations SQL) + ~200 LOC (Python) + ~150 LOC (testes) |
| 2 — Docker Compose | 4 tasks: log rotation, remover initdb, prod profile | 1 dia | ~100 LOC (YAML) |
| 3 — Retention Cron | 3 tasks: retention.py, CLI, testes | 1.5 dias | ~200 LOC (Python) + ~150 LOC (testes) |
| 4 — Documentação | 4 tasks: ADRs, containers.md, blueprint.md | 0.5 dia | ~200 LOC (Markdown) |
| **Total** | **34 tasks** | **5 dias** | **~1500 LOC** |

## Riscos Residuais

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| asyncpg não suporta sintaxe específica de migration SQL (DO $$ blocks, ENUMs) | Baixa | Médio | Testar cada migration reescrita contra PG 15 real. asyncpg suporta DDL e PL/pgSQL blocks. |
| Phoenix ignora PHOENIX_SQL_DATABASE_SCHEMA | Muito baixa | Médio | Versão 8.22.1 é muito posterior a v4.33.0 quando a feature foi adicionada. Fallback: DB separado. |
| Remoção da FK eval_scores.message_id causa inconsistência | Muito baixa | Baixo | UUID v4 collision é negligível. App já valida existência. eval_scores é auditoria, não crítica. |
| Docker log rotation não cobre 30 dias para alto volume | Média | Baixo | 250MB por service cobre >30d para 2-10 tenants. Monitorar e ajustar max-size após deploy. |
| sleep 86400 drift acumulado no cron | Muito baixa | Nenhum | Drift de ~1-2s/dia é irrelevante para purge diário. |

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plano completo com 4 fases, 34 tasks, 5 dias estimados. Correções na spec aplicadas: FK eval_scores removida (PG partition limitation), Phoenix via PHOENIX_SQL_DATABASE_SCHEMA (não search_path). Pesquisa, data model, contracts e quickstart prontos. Próximo passo: quebrar em tasks detalhadas com dependências."
  blockers: []
  confidence: Alta
  kill_criteria: "Se migrations do epic 005 já foram aplicadas em produção antes deste epic, a estratégia de reescrita de migrations se torna inválida."
