# Pesquisa: Production Readiness — Schema Isolation, Data Retention, VPS Deploy

**Epic**: 006-production-readiness
**Data**: 2026-04-12
**Status**: Completo

## 1. Schema Isolation no Supabase

### Contexto

O Supabase gerencia os schemas `auth` (autenticação), `storage` (arquivos) e usa `public` para tabelas próprias e do usuário. A migration 001 atual cria `CREATE SCHEMA IF NOT EXISTS auth` e a função `auth.tenant_id()` — ambos conflitam com o Supabase.

### Decisão

Usar schemas dedicados: `prosauai` para tabelas de negócio, `prosauai_ops` para funções operacionais (RLS helpers, migration tracking).

### Racional

- **Namespacing claro**: Tabelas do app não colidem com objetos do Supabase em `public` ou `auth`
- **Supabase safe**: O provider gerencia `auth.*` — criar funções custom lá é risco de sobrescrita em updates
- **search_path transparente**: `SET search_path = prosauai,prosauai_ops,public` permite queries existentes funcionarem sem schema prefix
- **Isolamento futuro**: Schema `admin` reservado para epic 013 (TenantStore Postgres)

### Alternativas Consideradas

| Alternativa | Prós | Contras | Veredicto |
|---|---|---|---|
| **A — Manter `public`** | Zero mudança | Conflita com Supabase, sem isolamento | Rejeitada |
| **B — Schema único `prosauai`** | Simples | Mistura dados de negócio com ops (migration tracking, RLS helpers) | Rejeitada |
| **C — `prosauai` + `prosauai_ops`** | Separação clara dados vs ops, Supabase-safe | 2 schemas para gerenciar | **Escolhida** |
| **D — Database separado** | Isolamento total | Complexidade de connection management, Supabase não permite múltiplos DBs no free tier | Rejeitada |

### Impacto no Código

- **pool.py**: Adicionar `server_settings={'search_path': 'prosauai,prosauai_ops,public'}` no `asyncpg.create_pool()`. Zero mudança em queries SQL.
- **Migrations 001-007**: Reescrever com schema prefix. Como nenhum dado de produção existe, reescrita é segura.
- **RLS policies**: Trocar `auth.tenant_id()` por `prosauai_ops.tenant_id()` em todas as policies.

---

## 2. Migration Runner com asyncpg

### Contexto

O projeto usa asyncpg direto (sem ORM). Adicionar psycopg2 ou Yoyo viola o princípio de minimizar dependências. O migration runner precisa executar DDL (CREATE TABLE, CREATE SCHEMA) e DML (INSERT seed data).

### Decisão

Script Python custom usando asyncpg com wrapper `asyncio.run()`. Tracking via tabela `prosauai_ops.schema_migrations`.

### Racional

- **asyncpg suporta DDL**: `CREATE TABLE`, `CREATE SCHEMA`, `ALTER TABLE` funcionam perfeitamente via `conn.execute()`
- **Transações por migration**: Cada arquivo `.sql` é executado dentro de uma transaction. DDL em Postgres é transacional (diferente de MySQL)
- **Sem dependência nova**: asyncpg já é dependência do projeto
- **Simplicidade**: ~80 linhas de código (leitura de arquivos, execute, tracking)

### Alternativas Consideradas

| Alternativa | Prós | Contras | Veredicto |
|---|---|---|---|
| **A — Yoyo** | Maduro, rollback | Depende de psycopg2 (nova dep) | Rejeitada |
| **B — Alembic** | Popular, integra SQLAlchemy | Requer SQLAlchemy (projeto não usa) | Rejeitada |
| **C — dbmate** | Go binary, SQL puro | Não Python, binary extra no container | Rejeitada |
| **D — Script custom asyncpg** | Zero deps novas, alinhado com stack | Sem rollback built-in | **Escolhida** |
| **E — psql subprocess** | Zero deps Python | Parsing de output frágil, psql não garantido no container | Rejeitada |

### Detalhes Técnicos

- asyncpg DDL: `await conn.execute("CREATE TABLE ...")` funciona normalmente. DDL em Postgres é transacional.
- Gotcha: `asyncpg` não suporta múltiplos statements em um único `execute()`. O runner precisa fazer `split` por `;` ou usar `conn.execute()` para o arquivo inteiro (asyncpg >= 0.27 suporta múltiplos statements no `execute`).
- Seed data (007): Usa `\set` do psql — incompatível com asyncpg. Reescrever com placeholders Python ou hardcoded UUIDs.
- Forward-only: Sem rollback. Migrations são idempotentes (IF NOT EXISTS). Se falhar, corrigir e re-aplicar.

---

## 3. Particionamento de Messages no Postgres 15

### Contexto

A tabela `messages` é append-only (INSERT only, UPDATE/DELETE denied por RLS). Cresce linearmente com o número de conversas. Purge de 90 dias (ADR-018) requer remoção eficiente.

### Decisão

`PARTITION BY RANGE (created_at)` com partições mensais. UNIQUE index global em `id` para manter FK de `eval_scores`.

### Racional

- **Purge eficiente**: `DROP TABLE prosauai.messages_2026_01` é instantâneo (DDL, não DML) — bypassa RLS automaticamente
- **PG 15 suporte**: FK em tabela particionada funciona desde PG 12. UNIQUE index global em coluna non-partition-key funciona desde PG 11
- **PK composta**: `PRIMARY KEY (id, created_at)` é necessária — PG exige partition key na PK/UNIQUE

### Validação PG 15 — Correção sobre UNIQUE index

**CORREÇÃO**: A spec e o pitch assumiam que PG 15 suporta `UNIQUE(id)` em tabela particionada por `created_at`. Isso é **INCORRETO**. A documentação do Postgres é explícita:

> "Unique constraints (and thus primary keys) on partitioned tables must include all the partition key columns."

Não é possível criar `CREATE UNIQUE INDEX ON messages(id)` sem incluir `created_at`. Portanto, `UNIQUE(id, created_at)` é o máximo que PG oferece.

### Impacto na FK eval_scores.message_id

Sem `UNIQUE(id)`, a FK `eval_scores.message_id REFERENCES messages(id)` não funciona. Três opções avaliadas:

| Opção | Descrição | Prós | Contras | Veredicto |
|---|---|---|---|---|
| **A — FK composta** | Adicionar `message_created_at` em eval_scores, FK `(message_id, message_created_at) REFERENCES messages(id, created_at)` | Integridade no BD | Coluna extra, queries mais verbosas | Viável mas complexo |
| **B — Drop FK, app-level** | Remover REFERENCES, validar no código Python | Zero overhead, simples | Perde integridade referencial no BD | **Escolhida** |
| **C — Trigger custom** | Trigger que verifica existência antes de INSERT em eval_scores | Integridade sem FK formal | Lento, frágil, manutenção | Rejeitada |

**Decisão: Opção B.** Racional:
- UUID v4 collision probability é ~1e-37 — na prática, `message_id` sempre referencia um message real
- eval_scores é tabela de auditoria, não crítica para integridade transacional
- O código em `EvalScoreRepo.create()` já recebe `message_id` de um message conhecido
- Simplicidade alinhada com constitution (Princípio I: pragmatismo)

### Automação de Partições

O cron de retention (S4) gerencia o lifecycle completo:
1. **Criar** partições para os próximos 3 meses (idempotente via `IF NOT EXISTS`)
2. **Dropar** partições onde todos os dados têm > 90 dias

Critério de drop conservador: uma partição mensal inteira só é removida quando `max(created_at) < now() - interval '90 days'`. Na prática, retenção efetiva = 90-120 dias.

---

## 4. Phoenix (Arize) com Postgres Backend

### Contexto

Phoenix 8.22.1 suporta Postgres como backend via `PHOENIX_SQL_DATABASE_URL`. Em dev, SQLite é conveniente (zero config). Em prod, Postgres garante persistência e escala.

### Decisão

Dev = SQLite (default). Prod = Postgres local da VPS com `search_path=observability`.

### Racional

- Phoenix suporta `PHOENIX_SQL_DATABASE_SCHEMA` env var desde v4.33.0 (PR #4474) — mecanismo oficial para schema isolation
- **NÃO usar `search_path` na connection URL** — a env var dedicada é mais confiável e explícita
- Tabelas Phoenix ficam isoladas no schema `observability`, sem conflito com `prosauai`
- Postgres local na VPS é mais eficiente que Supabase remoto para traces (write-heavy, fire-and-forget)

### Configuração Prod

```yaml
PHOENIX_SQL_DATABASE_URL: postgresql://user:pass@postgres:5432/prosauai
PHOENIX_SQL_DATABASE_SCHEMA: observability
```

O schema `observability` deve ser pré-criado na migration (`CREATE SCHEMA IF NOT EXISTS observability`). Phoenix cria suas tabelas dentro dele automaticamente.

### Fallback

Se a env var não funcionar em alguma edge case: criar database separado `phoenix_db` no mesmo Postgres.

---

## 5. Log Rotation e Persistence com Docker

### Contexto

Docker usa `json-file` driver por default sem rotation. Logs crescem indefinidamente até encher o disco.

### Decisão

YAML anchor `x-logging` aplicado a todos os services com `max-size: 50m`, `max-file: 5`.

### Racional

- **Docker Compose anchors**: `x-logging: &default-logging` funciona em docker-compose.yml e é herdado via `<<: *default-logging`
- **Prod override**: `docker-compose.prod.yml` pode sobrescrever logging config se necessário
- **Limite total**: 50MB × 5 files × 5 services = 1.25GB max no disco
- **Compliance ADR-018**: Para 2-10 tenants, 250MB por service deve cobrir >30 dias. Monitorar após deploy.

### Anchor YAML

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"
```

Cada service recebe `logging: *default-logging`. A anchor funciona no docker-compose.yml base e é preservada no merge com `docker-compose.prod.yml`.

---

## 6. Host Monitoring — Netdata

### Contexto

Nenhum monitoring de host existe antes do epic 013 (Prometheus + Grafana). Netdata é agente leve (~150MB RAM) com dashboard web built-in.

### Decisão

Netdata container no `docker-compose.prod.yml`, bind em `127.0.0.1:19999`.

### Racional

- **Setup 5 minutos**: Container Docker, zero config, dashboard funcional out-of-the-box
- **Mounts mínimos**: `/proc`, `/sys` (read-only) para métricas de host. `/var/run/docker.sock` (read-only) para métricas de containers
- **Segurança**: Bind apenas em localhost. Acesso via SSH tunnel

### Nota de Segurança sobre docker.sock

Montar `/var/run/docker.sock` expõe a API Docker ao container (pode listar containers, imagens, secrets). Trade-off aceito porque:
- VPS é single-tenant (operador = owner)
- Netdata é temporário (substituído por Prometheus no epic 013)
- Sem docker.sock, perde métricas por container (mantém apenas host metrics)

### Alternativas

| Alternativa | Prós | Contras | Veredicto |
|---|---|---|---|
| **A — Netdata** | Zero config, UI built-in, lightweight | docker.sock mount | **Escolhida** |
| **B — cAdvisor** | Sem docker.sock para host metrics | Sem dashboard, precisa Prometheus | Rejeitada (complexidade) |
| **C — Script bash no crontab** | Zero deps | Sem UI, sem histórico, sem alertas | Rejeitada (insuficiente) |
| **D — Node exporter + Grafana** | Stack definitiva | Overengineering para Fase 1 | Rejeitada (epic 013) |

---

## 7. Data Retention Cron — Container com Sleep Loop

### Contexto

O ADR-018 define purge diário. Opções: host crontab vs container dedicado.

### Decisão

Container Docker com `sleep 86400` loop e restart policy `unless-stopped`.

### Racional

- **Portabilidade**: Stack inteiro no Docker Compose, sem dependência de crontab do host
- **Idempotência natural**: Re-execução após restart não causa problemas — dados já purgados não são processados
- **UTC**: Todas as comparações de data usam `now() AT TIME ZONE 'UTC'`
- **Drift**: O `sleep 86400` tem drift natural (~1-2 segundos por ciclo). Para purge diário, drift é irrelevante

### Estrutura do Script

```
prosauai/ops/
    __init__.py
    migrate.py         # Migration runner (~80 LOC)
    partitions.py      # Criação/remoção de partições (~60 LOC)
    retention.py        # Lógica de purge por tipo de dado (~120 LOC)
    retention_cli.py    # CLI entry point com --dry-run (~40 LOC)
```

### Credenciais

O container `retention-cron` usa `DATABASE_URL` com role `service_role` do Supabase (BYPASSRLS). Separado do container `api` que usa role RLS-restricted. Isso permite que o cron execute `DELETE` em tabelas com RLS sem precisar de `SET LOCAL role`.

---

handoff:
  from: speckit.plan (Phase 0)
  to: speckit.plan (Phase 1)
  context: "Pesquisa completa. 7 decisões técnicas documentadas com alternativas. Pronto para design de data model e contracts."
  blockers: []
  confidence: Alta
