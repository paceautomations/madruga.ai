# Tasks: Production Readiness — Schema Isolation, Log Persistence, Data Retention, VPS Deploy

**Input**: Design documents from `epics/006-production-readiness/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included — constitution (Principle VII) mandates TDD for all code.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source code**: `prosauai/` (Python package in external repo)
- **Migrations**: `migrations/` (SQL files in external repo)
- **Docker**: `docker-compose.yml`, `docker-compose.prod.yml` (external repo root)
- **Tests**: `tests/ops/` (external repo)
- **Docs**: `platforms/prosauai/` (this repo — ADRs, containers, blueprint)

---

## Phase 1: Setup

**Purpose**: Create package structure for new operational modules

- [x] T001 Create ops package directory with prosauai/ops/__init__.py
- [x] T002 Create tests directory with tests/ops/__init__.py

---

## Phase 2: Foundational — Schema Isolation + Migration Runner

**Purpose**: Rewrite all migrations with schema prefix and implement automated migration runner. This phase BLOCKS all user stories — without correct schemas and a runner, nothing else works.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Rewrite migration 001_create_schema.sql — create schemas prosauai, prosauai_ops, observability, admin; move tenant_id() to prosauai_ops; create schema_migrations table in prosauai_ops; keep uuid-ossp extension in public (file: migrations/001_create_schema.sql)
- [x] T004 [P] Rewrite migration 002_customers.sql — prefix all tables with prosauai., update RLS policies to use prosauai_ops.tenant_id(), prefix indexes with prosauai. (file: migrations/002_customers.sql)
- [x] T005 [P] Rewrite migration 003_conversations.sql — prefix tables with prosauai., update RLS to prosauai_ops.tenant_id(), update FK to prosauai.customers(id) (file: migrations/003_conversations.sql)
- [x] T006 [P] Rewrite migration 003b_conversation_states.sql — prefix with prosauai., update FK to prosauai.conversations(id), update RLS (file: migrations/003b_conversation_states.sql)
- [x] T007 Rewrite migration 004_messages.sql — prefix with prosauai., add PARTITION BY RANGE (created_at), PK composta (id, created_at), create 3 initial monthly partitions, update RLS to prosauai_ops.tenant_id() (file: migrations/004_messages.sql)
- [x] T008 [P] Rewrite migration 005_agents_prompts.sql — prefix prosauai.agents and prosauai.prompts, update RLS to prosauai_ops.tenant_id() (file: migrations/005_agents_prompts.sql)
- [x] T009 [P] Rewrite migration 006_eval_scores.sql — prefix prosauai.eval_scores, remove FK REFERENCES messages(id), add comment explaining app-level validation, update RLS to prosauai_ops.tenant_id() (file: migrations/006_eval_scores.sql)
- [x] T010 Rewrite migration 007_seed_data.sql — replace psql \set variables with hardcoded deterministic UUIDs, prefix all tables with prosauai., use pure SQL (no psql-specific syntax) (file: migrations/007_seed_data.sql)
- [x] T011 Implement migration runner with asyncpg: bootstrap schema_migrations table, list .sql files in order, apply pending migrations in individual transactions, record checksum SHA-256, structured logging via structlog. Expose run_migrations() for library use and CLI via python -m (file: prosauai/ops/migrate.py, ~80 LOC) — ref: contracts/migration-runner.md
- [x] T012 Update asyncpg connection pool to set search_path = prosauai,prosauai_ops,public via server_settings parameter in create_pool() (file: prosauai/db/pool.py)
- [x] T013 Integrate migration runner into API startup lifespan — call await run_migrations() before create_pool(), fail-fast if migration fails (file: prosauai/main.py)
- [x] T014 Write tests for migration runner: applies DDL correctly, re-execution is idempotent, failed migration rolls back and blocks subsequent, checksum drift detection logs warning (file: tests/ops/test_migrate.py)

**Checkpoint**: All migrations rewritten with schema isolation. Migration runner applies them automatically. pool.py uses correct search_path. Schema isolation and deploy foundation are ready.

---

## Phase 3: User Story 2 — Schema Isolation Compativel com Supabase (Priority: P1)

**Goal**: Todas as tabelas de negocio no schema `prosauai`, helpers RLS em `prosauai_ops`, zero objetos custom em `auth` ou `public`.

**Independent Test**: Aplicar migrations em Postgres limpo e verificar schemas via `\dn` e queries em `information_schema.tables`.

**Note**: Core implementation is in Phase 2 (foundational). This phase adds validation and verification.

- [x] T015 [US2] Write integration test: apply all migrations to clean Postgres, verify prosauai schema contains all 7 business tables, prosauai_ops contains tenant_id() and schema_migrations, auth and public have no custom objects (file: tests/ops/test_schema_isolation.py)
- [x] T016 [US2] Write integration test: verify search_path resolves unqualified table names correctly — SELECT from messages, customers, conversations without schema prefix (file: tests/ops/test_schema_isolation.py)
- [x] T017 [US2] Write integration test: verify prosauai_ops.tenant_id() returns correct value when app.current_tenant_id is set via SET LOCAL (file: tests/ops/test_schema_isolation.py)

**Checkpoint**: Schema isolation verified — all queries work transparently via search_path, RLS function in correct namespace.

---

## Phase 4: User Story 1 — Deploy Seguro em VPS (Priority: P1)

**Goal**: O operador executa docker compose prod e todos os servicos sobem healthy, migrations aplicadas, logs rotacionados, monitoring funcional.

**Independent Test**: Subir stack em ambiente limpo com docker compose prod e verificar todos containers healthy + API respondendo /health.

- [x] T018 [US1] Remove ./migrations:/docker-entrypoint-initdb.d:ro volume mount from Postgres service — migrations now managed by runner in API startup (file: docker-compose.yml)
- [x] T019 [US1] Create docker-compose.prod.yml with production overrides: Phoenix Postgres backend with PHOENIX_SQL_DATABASE_SCHEMA=observability, Netdata container on 127.0.0.1:19999 with resource limits (mem_limit: 256m), retention-cron container with sleep 86400 loop and resource limits (mem_limit: 128m), add prod volumes (netdataconfig, netdatalib, netdatacache). Include VPS requirements comment: 2 vCPU, 4GB RAM, 40GB SSD (file: docker-compose.prod.yml)
- [x] T020 [US1] Create .env.example with all required environment variables documented: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, DATABASE_URL, PHOENIX_SQL_DATABASE_URL, plus retention-cron DATABASE_URL with service_role credentials (file: .env.example — update if exists)

**Checkpoint**: Full production stack deployable with single docker compose command. Fail-fast on migration errors.

---

## Phase 5: User Story 4 — Logs Persistentes e Rotacionados (Priority: P2)

**Goal**: Todos os containers Docker com log rotation configurado, prevenindo disk-full.

**Independent Test**: docker inspect mostra json-file driver com max-size e max-file em todos os services.

- [x] T021 [P] [US4] Add YAML anchor x-logging with json-file driver, max-size 50m, max-file 5, and apply logging: *default-logging to ALL existing services (api, redis, postgres, phoenix) (file: docker-compose.yml)

**Checkpoint**: Log rotation active on all services. Max disk usage for logs: 1.25GB.

---

## Phase 6: User Story 5 — Phoenix com Backend Postgres em Producao (Priority: P2)

**Goal**: Phoenix persiste traces em Postgres em producao, SQLite em dev.

**Independent Test**: Subir stack prod, gerar traces, reiniciar Phoenix, verificar que traces anteriores persistem na UI.

- [x] T022 [US5] Configure Phoenix in docker-compose.prod.yml: set PHOENIX_SQL_DATABASE_URL to postgresql connection string pointing to local Postgres, set PHOENIX_SQL_DATABASE_SCHEMA=observability, remove phoenix_data SQLite volume override (file: docker-compose.prod.yml)

**Checkpoint**: Phoenix uses Postgres in prod (traces survive restarts), SQLite in dev (zero-config).

---

## Phase 7: User Story 6 — Particionamento de Messages por Mes (Priority: P2)

**Goal**: Tabela messages particionada por RANGE(created_at) com particoes mensais, purge via DROP PARTITION.

**Independent Test**: Inserir dados em multiplas particoes, executar EXPLAIN ANALYZE com filtro de data, confirmar partition pruning. Dropar particao e confirmar remocao instantanea.

**Note**: Migration rewrite (T007) creates the partitioned table. This phase adds the partition manager for ongoing lifecycle.

- [x] T023 [US6] Implement partition manager: ensure_future_partitions(conn, table, months_ahead=3) creates monthly partitions with IF NOT EXISTS; drop_expired_partitions(conn, table, retention_days=90) drops partitions where all data exceeds retention; list_partitions(conn, table) returns partition names with row counts. All operations use structlog for logging (file: prosauai/ops/partitions.py, ~60 LOC)
- [x] T024 [US6] Write tests for partition manager: ensure_future_partitions creates correct monthly ranges idempotently, drop_expired_partitions only removes fully expired partitions, list_partitions returns accurate counts, INSERT into partition-less month fails with error (file: tests/ops/test_partitions.py)

**Checkpoint**: Partition lifecycle automated. Future partitions created proactively, expired partitions droppable instantly.

---

## Phase 8: User Story 3 — Compliance LGPD: Purge Automatico de Dados (Priority: P1)

**Goal**: Cron job diario purga dados expirados conforme ADR-018. Messages via DROP PARTITION, demais via batch DELETE.

**Independent Test**: --dry-run lista dados expiraveis sem deletar. Execucao real remove apenas dados alem do periodo de retencao.

**Depends on**: Phase 7 (partition manager for DROP PARTITION)

- [x] T025 [US3] Implement retention logic: purge_expired_messages using partitions.drop_expired_partitions() + ensure_future_partitions(); purge_expired_conversations DELETE batch (LIMIT 1000) on closed conversations > 90d; purge_expired_eval_scores DELETE batch > 90d; purge_expired_traces DELETE on observability schema spans > 90d. Never touch admin.audit_log. All comparisons use UTC. Orchestrator run_retention() calls all purge functions + logs totals with structlog (run_id, table, rows_purged, partitions_dropped, duration_ms) (file: prosauai/ops/retention.py, ~120 LOC) — ref: contracts/retention-cli.md
- [x] T026 [US3] Implement retention CLI entry point: argparse with --dry-run (default true), --database-url (default $DATABASE_URL), --log-level. Connects via asyncpg with asyncio.run(), calls run_retention(), exits with code 0/1/2 per contract (file: prosauai/ops/retention_cli.py, ~40 LOC) — ref: contracts/retention-cli.md
- [x] T027 [US3] Write tests for retention: dry-run lists without deleting, purge removes only expired data, partitions are created for future months, expired partitions are dropped, batch DELETE respects LIMIT, re-execution is idempotent, audit_log is never touched (file: tests/ops/test_retention.py)

**Checkpoint**: Data retention fully automated. LGPD compliance from day 1 of production.

---

## Phase 9: User Story 7 — Host Monitoring Basico na VPS (Priority: P3)

**Goal**: Dashboard web com metricas de CPU, RAM, disco e containers Docker.

**Independent Test**: Acessar localhost:19999 e verificar metricas de host e containers.

- [x] T028 [US7] Configure Netdata container in docker-compose.prod.yml: image netdata/netdata:stable, bind 127.0.0.1:19999, cap_add SYS_PTRACE, security_opt apparmor:unconfined, mount /proc /sys /var/run/docker.sock read-only, mem_limit 256m, restart unless-stopped (file: docker-compose.prod.yml)

**Checkpoint**: Host monitoring operational. Disk/RAM/CPU alerts pre-configured by Netdata defaults.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates to reflect infrastructure changes. ADRs, containers.md, blueprint.md.

- [x] T029 [P] Create ADR-024 schema isolation in Nygard format: document decision to use prosauai + prosauai_ops schemas instead of public + auth, motivation (Supabase compatibility, namespace isolation), consequences (search_path required, migrations rewritten) (file: platforms/prosauai/decisions/ADR-024-schema-isolation.md)
- [x] T030 [P] Update ADR-011: replace all references to auth.tenant_id() with prosauai_ops.tenant_id(), add section on schema isolation and search_path configuration in pool.py (file: platforms/prosauai/decisions/ADR-011-pool-rls-multi-tenant.md)
- [x] T031 [P] Update ADR-018: add Implementation section referencing prosauai/ops/retention.py, document partitioning as purge strategy (DROP PARTITION), document effective retention 90-120d due to monthly granularity (file: platforms/prosauai/decisions/ADR-018-data-retention-lgpd.md)
- [x] T032 [P] Update ADR-020: add note about PHOENIX_SQL_DATABASE_SCHEMA=observability for prod, document SQLite dev vs Postgres prod split via docker-compose.prod.yml (file: platforms/prosauai/decisions/ADR-020-phoenix-observability.md)
- [ ] T033 Update containers.md: add Netdata to container matrix, add retention-cron container, update Phoenix status (Postgres backend in prod), update Postgres status (schema isolation), add scaling notes for partitioned messages (file: platforms/prosauai/engineering/containers.md)
- [ ] T034 Update blueprint.md: add schema layout section (prosauai + prosauai_ops + observability + admin), add log persistence to infrastructure stack, document migration runner in deployment section (file: platforms/prosauai/engineering/blueprint.md)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US2 Schema Isolation (Phase 3)**: Depends on Foundational (Phase 2) — validation tests
- **US1 Deploy Seguro (Phase 4)**: Depends on Foundational (Phase 2) — docker-compose changes
- **US4 Logs (Phase 5)**: Independent of user stories — docker-compose config only
- **US5 Phoenix Postgres (Phase 6)**: Independent — docker-compose.prod.yml config
- **US6 Particionamento (Phase 7)**: Depends on Foundational (T007 creates partitioned table)
- **US3 LGPD Purge (Phase 8)**: Depends on Phase 7 (partition manager for DROP PARTITION)
- **US7 Monitoring (Phase 9)**: Independent — docker-compose.prod.yml config
- **Polish (Phase 10)**: Depends on all user stories being complete

### User Story Dependencies

- **US2 (P1)**: Foundational phase covers core implementation. Phase 3 adds validation tests.
- **US1 (P1)**: Depends on Foundational (migration runner) + US4 (logs) + US5 (Phoenix) for complete prod stack.
- **US3 (P1)**: Depends on US6 (partition manager for efficient purge via DROP PARTITION).
- **US4 (P2)**: Independent — can start after Foundational.
- **US5 (P2)**: Independent — can start after Foundational.
- **US6 (P2)**: Depends on Foundational (partitioned table created in T007).
- **US7 (P3)**: Independent — can start after Foundational.

### Within Foundational Phase

- T003 (migration 001) MUST run first — creates schemas referenced by all subsequent migrations
- T004, T005, T006, T008, T009 can run in parallel (independent table migrations)
- T007 depends on T003 (schemas exist) — creates partitioned messages table
- T010 depends on T003 (schema references) — seed data references prosauai tables
- T011 (migration runner) can be developed in parallel with migration rewrites
- T012 (pool.py) depends on T003 (schema names defined)
- T013 (main.py) depends on T011 (migration runner exists)
- T014 (tests) depends on T011 + T003-T010 (runner + migrations exist)

### Parallel Opportunities

```
After Phase 1 (Setup):
  T003 (migration 001) → then T004, T005, T006, T007, T008, T009 in parallel
  T011 (migration runner) can develop in parallel with migration rewrites
  T012 (pool.py) can develop in parallel with T011

After Phase 2 (Foundational):
  Phase 3 (US2), Phase 4 (US1), Phase 5 (US4), Phase 6 (US5), Phase 7 (US6), Phase 9 (US7) — all can start in parallel
  Phase 8 (US3) waits for Phase 7 (US6)

After all user stories:
  T029, T030, T031, T032 (ADR updates) — all in parallel
  T033, T034 — can run in parallel with ADR updates
```

---

## Parallel Example: Foundational Phase

```bash
# First: create schemas (blocks everything)
Task T003: "Rewrite migration 001_create_schema.sql"

# Then: all table migrations in parallel
Task T004: "Rewrite migration 002_customers.sql"
Task T005: "Rewrite migration 003_conversations.sql"
Task T006: "Rewrite migration 003b_conversation_states.sql"
Task T007: "Rewrite migration 004_messages.sql (partitioned)"
Task T008: "Rewrite migration 005_agents_prompts.sql"
Task T009: "Rewrite migration 006_eval_scores.sql"
Task T010: "Rewrite migration 007_seed_data.sql"

# In parallel with above: develop runner and pool
Task T011: "Implement migration runner"
Task T012: "Update pool.py search_path"
```

## Parallel Example: Post-Foundational

```bash
# All independent docker-compose and user story work in parallel
Task T018-T020: "US1 — Docker deploy config"
Task T021: "US4 — Log rotation"
Task T022: "US5 — Phoenix Postgres"
Task T023-T024: "US6 — Partition manager"
Task T028: "US7 — Netdata monitoring"

# Then after US6 completes:
Task T025-T027: "US3 — Retention cron"

# Finally all ADRs in parallel:
Task T029-T034: "Documentation updates"
```

---

## Implementation Strategy

### MVP First (US2 Schema Isolation + US1 Deploy)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US2 Schema Isolation (verify migrations)
4. Complete Phase 4: US1 Deploy Seguro (docker-compose prod)
5. **STOP and VALIDATE**: Deploy to clean Postgres, verify schemas, test API /health
6. Deploy/demo if ready — basic prod stack operational

### Incremental Delivery

1. Setup + Foundational → Schema isolation + migration runner ready
2. Add US2 verification → Confirm Supabase compatibility
3. Add US1 + US4 + US5 → Full prod Docker stack deployable
4. Add US6 + US3 → Partitioning + LGPD retention automated
5. Add US7 → Host monitoring operational
6. Polish → Documentation updated, ADRs current
7. Each phase adds operational capability without breaking previous

### Summary

| Metric | Value |
|---|---|
| Total tasks | 34 |
| Setup tasks | 2 |
| Foundational tasks | 12 |
| US1 (Deploy) tasks | 3 |
| US2 (Schema) tasks | 3 |
| US3 (LGPD Purge) tasks | 3 |
| US4 (Logs) tasks | 1 |
| US5 (Phoenix) tasks | 1 |
| US6 (Partitioning) tasks | 2 |
| US7 (Monitoring) tasks | 1 |
| Polish tasks | 6 |
| Parallelizable tasks | 16 (47%) |
| MVP scope | Phase 1-4 (17 tasks) |
| Estimated effort | 5 days |

---
handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "34 tasks geradas em 10 fases para epic 006 production readiness. Organizadas por user story (7 stories, P1-P3). MVP scope: Phase 1-4 (setup + foundational + schema isolation + deploy). 47% das tasks paralelizaveis. Nenhuma dependencia externa — todas as tasks sao executaveis com asyncpg + structlog + stdlib existentes. Proximo passo: analise de consistencia spec/plan/tasks antes de implementar."
  blockers: []
  confidence: Alta
  kill_criteria: "Se migrations do epic 005 ja foram aplicadas em producao antes deste epic, a estrategia de reescrita e invalida — necessario migration de renomeacao de schema."
