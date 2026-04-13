# Quickstart: Production Readiness (Epic 006)

**Epic**: 006-production-readiness
**Data**: 2026-04-12

## Pré-requisitos

- Docker + Docker Compose v2
- VPS com mínimo 2 vCPU, 4GB RAM, 40GB SSD
- `.env` configurado com credenciais do Supabase (ou Postgres local)
- Epic 005 (Conversation Core) merged no repo

## Setup Rápido — Dev

```bash
# 1. Clone e configure
git clone <repo> && cd prosauai
cp .env.example .env  # editar credenciais

# 2. Suba o stack (dev — Phoenix com SQLite, sem Netdata)
docker compose up -d

# 3. Migrations são aplicadas automaticamente no startup da API
docker compose logs api | grep "migration"
# Deve mostrar: "Applied migration 001_create_schema ... 007_seed_data"

# 4. Verifique saúde
docker compose ps  # todos healthy
curl http://localhost:8050/health  # via Tailscale ou port override
```

## Setup Rápido — Produção (VPS)

```bash
# 1. Configure .env com credenciais de produção
cp .env.example .env
# Editar: POSTGRES_USER, POSTGRES_PASSWORD, DATABASE_URL, PHOENIX_SQL_DATABASE_URL

# 2. Suba com profile de produção
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 3. Verifique migrations
docker compose logs api | grep "migration"

# 4. Verifique schemas
docker compose exec postgres psql -U prosauai -c "\dn"
# Deve listar: prosauai, prosauai_ops, observability, admin, public

# 5. Verifique partições de messages
docker compose exec postgres psql -U prosauai -c "\d+ prosauai.messages"
# Deve mostrar: PARTITION BY RANGE (created_at) com 3+ partições

# 6. Verifique monitoring
# Via SSH tunnel: ssh -L 19999:localhost:19999 user@vps
# Abrir: http://localhost:19999 (Netdata dashboard)

# 7. Verifique log rotation
docker inspect --format='{{.HostConfig.LogConfig}}' prosauai-api-1
# Deve mostrar: {json-file map[max-file:5 max-size:50m]}
```

## Testando Data Retention

```bash
# Dry-run (lista o que seria purgado, sem deletar)
docker compose exec retention-cron python -m prosauai.ops.retention_cli --dry-run

# Execução real (em produção, roda automaticamente via sleep loop)
docker compose exec retention-cron python -m prosauai.ops.retention_cli
```

## Verificação de Schema Isolation

```sql
-- Conectar no Postgres
-- Verificar que nenhum objeto custom existe em auth ou public
SELECT schemaname, tablename FROM pg_tables
WHERE schemaname IN ('auth', 'public')
AND tablename NOT IN ('spatial_ref_sys');  -- extension table, ok

-- Verificar tabelas de negócio no schema prosauai
SELECT tablename FROM pg_tables WHERE schemaname = 'prosauai';
-- Esperado: customers, conversations, conversation_states, messages_*, agents, prompts, eval_scores

-- Verificar função RLS
SELECT proname, pronamespace::regnamespace FROM pg_proc WHERE proname = 'tenant_id';
-- Esperado: tenant_id | prosauai_ops
```

## Arquivos Novos/Modificados

### Novos

| Arquivo | Descrição |
|---|---|
| `prosauai/ops/__init__.py` | Package ops |
| `prosauai/ops/migrate.py` | Migration runner (~80 LOC) |
| `prosauai/ops/partitions.py` | Criação/remoção de partições (~60 LOC) |
| `prosauai/ops/retention.py` | Lógica de purge por tipo de dado (~120 LOC) |
| `prosauai/ops/retention_cli.py` | CLI entry point com --dry-run (~40 LOC) |
| `docker-compose.prod.yml` | Overrides de produção |
| `tests/ops/test_migrate.py` | Testes do migration runner |
| `tests/ops/test_retention.py` | Testes do cron de retention |
| `tests/ops/test_partitions.py` | Testes de criação/remoção de partições |

### Modificados

| Arquivo | Mudança |
|---|---|
| `migrations/001-007` | Reescritos com schema prefix + particionamento |
| `docker-compose.yml` | Log rotation em todos os services |
| `prosauai/db/pool.py` | `server_settings={'search_path': 'prosauai,prosauai_ops,public'}` |

---

handoff:
  from: speckit.plan (quickstart)
  to: speckit.tasks
  context: "Quickstart com instruções de setup dev e prod. Lista de arquivos novos e modificados documentada."
  blockers: []
  confidence: Alta
