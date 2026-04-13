---
id: "006"
title: "Production Readiness — Schema isolation, log persistence, data retention, VPS deploy"
status: shipped
phase: next
features:
  - "Schema isolation: tabelas de negocio em schema proprio, resolver conflito auth com Supabase"
  - "Phoenix backend migrado de SQLite para Postgres (Supabase)"
  - "Log persistence com retention 30d (LGPD compliance ADR-018)"
  - "Cron job de purge automatico (data retention ADR-018)"
  - "Particionamento de messages por mes (append-only scaling)"
  - "Host monitoring basico para VPS"
  - "Docker Compose production profile completo"
  - "Migration runner automatizado"
  - "Documentacao atualizada: ADRs novos + updates em containers.md, blueprint.md, roadmap.md"
owner: ""
created: 2026-04-12
updated: 2026-04-12
target: ""
outcome: ""
arch:
  modules: []
  contexts: [operations, observability]
  containers: [postgres, phoenix, prosauai-api]
delivered_at: 2026-04-12
---

# 006 — Production Readiness

## Escopo Arquitetural

| Camada | Blocos | Viewer |
|--------|--------|--------|
| Modulos | Infra transversal (sem modulos de dominio) | [Containers (Interactive)](../../engineering/containers/) |
| Contextos | Operations, Observability | [Context Map](../../engineering/context-map/) |
| Containers | postgres, phoenix, prosauai-api | [Containers (Interactive)](../../engineering/containers/) |

## Problema

O epic 005 (Conversation Core) entrega o MVP funcional: agente WhatsApp multi-tenant que responde com IA, persiste conversas em BD, com observabilidade total. Porem, a infraestrutura esta preparada para **desenvolvimento local**, nao para **producao numa VPS**.

Seis gaps concretos foram identificados ao cruzar o estado atual do codigo com os ADRs aprovados e a arquitetura target:

### Gap 1 — Tabelas de negocio no schema `public`

As 8 migrations do epic 005 (`001_create_schema.sql` a `007_seed_data.sql`, incluindo `003b_conversation_states.sql`) criam todas as tabelas no schema `public` do Postgres. O Supabase usa `public` para suas proprias tabelas e funcoes (auth, storage, realtime). **Conflito garantido no deploy.**

Alem disso, a migration `001_create_schema.sql` cria `CREATE SCHEMA IF NOT EXISTS auth` e a funcao `auth.tenant_id()`. O Supabase ja tem seu proprio schema `auth` com funcoes e tabelas (`auth.users`, `auth.sessions`, etc.). Criar `auth.tenant_id()` dentro do schema `auth` do Supabase pode colidir com funcoes existentes ou futuras do provider.

**Evidencia no codigo:**
- `migrations/001_create_schema.sql:9` — `CREATE SCHEMA IF NOT EXISTS auth;`
- `migrations/001_create_schema.sql:16` — `CREATE OR REPLACE FUNCTION auth.tenant_id()`
- `migrations/002_customers.sql:6` — `CREATE TABLE IF NOT EXISTS customers (` — sem schema prefix, vai para `public`
- Todas as 8 migrations seguem o mesmo padrao: tabelas no `public`, RLS referenciando `auth.tenant_id()`
- `007_seed_data.sql` insere dados iniciais de agents/prompts — tambem precisa referenciar schema `prosauai`
- ADR-023 ja preve `schema admin` para tenants/audit na Fase 3, mas nenhum schema para tabelas de negocio

**Impacto:** Se aplicar as migrations no Supabase como estao, ou (a) tabelas colidem com o namespace `public` do Supabase, ou (b) `auth.tenant_id()` conflita com o schema `auth` gerenciado pelo Supabase. Ambos cenarios exigem rewrite das migrations — muito mais doloroso com dados existentes.

### Gap 2 — Phoenix usando SQLite (nao Postgres)

O ADR-020 decide que Phoenix usa "Postgres backend (Supabase)" e o containers.md confirma. Mas o `docker-compose.yml` configura:

```yaml
PHOENIX_SQL_DATABASE_URL: ${PHOENIX_SQL_DATABASE_URL:-sqlite:///data/phoenix.db}
```

SQLite e single-writer e nao escala. Numa VPS com disco SSD limitado (tipicamente 40-80GB), o `phoenix.db` cresce sem controle e compete por disco com `pgdata`, logs e o proprio SO.

**Evidencia:** `docker-compose.yml:74`

**Impacto:** Phoenix degrada progressivamente apos ~1-5M spans. Queries ficam lentas, disco enche silenciosamente, nao ha vacuuming automatico.

### Gap 3 — Logs sem persistencia

O ADR-018 define retention de 30 dias para application logs. O structlog bridge (epic 002) ja injeta `trace_id` e `span_id` nos logs estruturados. Porem:

- Logs vao para stdout do container (efemero)
- Nenhum log driver configurado no `docker-compose.yml`
- Nenhum servico de log aggregation (Loki, Better Stack, etc.) no stack
- Docker default (`json-file` driver) acumula logs sem rotation — disco enche

**Evidencia:**
- `docker-compose.yml` — nenhum `logging:` block em nenhum service
- ADR-018 tabela de retention: "Application logs | 30 dias | Nao | Log rotation"
- Nenhum epic implementa esse requisito

**Impacto:** (1) Perda de logs quando container reinicia. (2) Disco da VPS enche com logs nao-rotacionados. (3) Non-compliance com ADR-018. (4) Debugging em prod e cego — sem logs persistentes, sem busca, sem correlacao com traces.

### Gap 4 — Cron job de purge inexistente

O ADR-018 define: "Cron job diario para purge automatico de dados expirados. Tenant pode ajustar retention no admin panel." A tabela de retention especifica:

| Dado | Retention Default |
|------|------------------|
| Conversas (mensagens) | 90 dias |
| Phoenix traces | 90 dias |
| Application logs | 30 dias |
| Audit trail (security) | 365 dias |

**Nenhum epic implementa esse cron job.** Sem ele, dados crescem indefinidamente. A tabela `messages` (append-only, invariante 2) e a mais critica — e a que mais cresce.

**Impacto:** (1) Non-compliance com LGPD (principio de minimizacao de dados). (2) Postgres cresce sem controle. (3) Queries ficam progressivamente mais lentas sem particionamento. (4) Custo de storage cresce linearmente com tempo.

### Gap 5 — Tabela `messages` sem particionamento

A tabela `messages` e append-only (enforced por RLS policy `messages_append_only`). Cada mensagem de cada cliente de cada tenant e um INSERT. Nunca ha DELETE ou UPDATE. Com 10 tenants ativos, ~100 mensagens/dia por tenant = 1000 msgs/dia = 365K msgs/ano. Com 50 tenants: ~1.8M msgs/ano.

Sem particionamento, a tabela cresce como monolito. O purge do ADR-018 (90 dias) requer `DELETE` em tabela enorme — operacao lenta e cara em disco (write amplification).

Com particionamento por mes (`PARTITION BY RANGE (created_at)`):
- Purge vira `DROP PARTITION` — instantaneo, sem write amplification
- VACUUM opera por particao, nao na tabela inteira

**Nota sobre partition pruning:** As queries atuais do app (`repositories.py:312-365`) filtram por `conversation_id`, nao por `created_at` no WHERE. Partition pruning **nao beneficia** essas queries — o Postgres precisa scanear todas as particoes. O beneficio principal do particionamento e no **purge** (`DROP PARTITION` instantaneo vs DELETE lento) e em queries futuras com filtro temporal.

Para o volume projetado (365K msgs/ano com 10 tenants, ~1M rows em 3 anos), Postgres lida bem sem particao. Particionamento e uma otimizacao para **purge eficiente**, nao para performance de leitura no cenario atual

**Custo de fazer agora vs depois:** Criar tabela particionada desde o inicio = trocar `CREATE TABLE` na migration. Migrar tabela existente com dados para particionada = `pg_rewrite` + downtime + script de migracao. **Fazer agora e trivial; fazer depois e doloroso.**

### Gap 6 — Nenhum monitoring de host na VPS

Nenhum epic preve monitoramento basico de host (CPU, RAM, disco) antes da Fase 3 (epic 013 — Prometheus + Grafana). Numa VPS rodando 4-5 containers Docker, saber que o disco encheu ou a RAM acabou e critico.

**Impacto:** Falhas silenciosas. Container OOM-killed sem alerta. Disco cheio = Postgres crash. Sem visibilidade ate o usuario reportar que o agente parou de responder.

### Gap 7 — Migration runner inexistente

As migrations sao arquivos `.sql` estaticos na pasta `migrations/`. O docker-compose monta `./migrations:/docker-entrypoint-initdb.d:ro` no container Postgres, o que executa os scripts **apenas na primeira inicializacao do volume** (`pgdata` vazio). Apos a primeira inicializacao:

- Novas migrations nao sao aplicadas automaticamente
- Nao ha tracking de quais migrations ja rodaram
- Nao ha rollback
- Nao ha validacao de ordem

**Evidencia:** `docker-compose.yml:59` — `./migrations:/docker-entrypoint-initdb.d:ro`

**Impacto:** Ao evoluir o schema (novos epics, novos campos), nao ha mecanismo para aplicar mudancas incrementais. Risco de aplicar migration fora de ordem ou duplicada. Nao escala alem do MVP.

---

## Valor de Negocio

Este epic nao adiciona features visiveis ao usuario final. O valor e **operacional e de compliance**:

1. **Deploy para VPS sem surpresas** — schema isolation, log rotation, monitoring previnem os 3 incidentes mais comuns em first deploy
2. **LGPD compliance** — cron de purge e unico item hard-blocker legal. Sem ele, a plataforma viola o principio de minimizacao de dados desde o dia 1 de prod
3. **Longevidade do banco** — particionamento e schema separation garantem que o BD escala por 12+ meses sem intervenção manual
4. **Debugging em prod** — logs persistentes + host monitoring = capacidade de diagnosticar problemas sem SSH no servidor
5. **Foundation para epics futuros** — epic 013 (Ops Fase 3) assume Prometheus + Grafana; este epic entrega o minimo viavel para operar antes disso

## Appetite

**1 semana** (5 dias uteis). Escopo controlado: infraestrutura e config, zero mudanca em logica de negocio. A maioria dos itens sao edits em migrations existentes, config no docker-compose, e scripts utilitarios.

## Solution

### S1 — Schema Isolation (Gap 1)

Reorganizar as migrations para usar schemas dedicados:

| Schema | Conteudo | Responsavel |
|--------|----------|-------------|
| `prosauai` | Tabelas de negocio: customers, conversations, conversation_states, messages, agents, prompts, eval_scores, enums | Epic 005 (migrations reescritas) |
| `prosauai_ops` | Funcoes RLS helper (`tenant_id()`), extensions (`uuid-ossp`) | Epic 006 (este) |
| `admin` | Tenants, audit_log (Fase 3, ADR-023 — apenas schema criado, tabelas futuras) | Epic 013 |
| `observability` | Reservado para Phoenix (gerenciado pelo Phoenix, nao por migrations manuais) | Phoenix auto-manage |

**Por que `prosauai_ops` em vez de `auth` para o tenant_id() helper?**

O Supabase gerencia o schema `auth` (tabelas `users`, `sessions`, `refresh_tokens`, funcoes `auth.uid()`, `auth.jwt()`, etc.). Criar funcoes custom nesse schema:
- Pode ser sobrescrito por updates do Supabase
- Viola o contrato de "schema gerenciado pelo provider"
- Causa confusao sobre ownership da funcao

A funcao `prosauai_ops.tenant_id()` e semanticamente identica a `auth.tenant_id()` mas vive em namespace controlado pelo projeto. Todas as RLS policies referenciam `prosauai_ops.tenant_id()` em vez de `auth.tenant_id()`.

**Impacto nas migrations existentes:**
- Migration 001: trocar `CREATE SCHEMA auth` por `CREATE SCHEMA prosauai; CREATE SCHEMA prosauai_ops;` + funcao em `prosauai_ops`
- Migrations 002-006: prefixar todas as tabelas com `prosauai.` (ex: `prosauai.customers`)
- Todas as RLS policies: trocar `auth.tenant_id()` por `prosauai_ops.tenant_id()`
- `SET search_path = prosauai, prosauai_ops, public` na connection string ou no pool init

**Impacto no codigo Python (`pool.py`):**

O `pool.py` atual (`prosauai/db/pool.py`) nao configura `search_path` — todas as queries usam nomes de tabela sem schema prefix (ex: `SELECT * FROM messages`). Apos mover tabelas para schema `prosauai`, **todas as queries do app quebram** se `search_path` nao for configurado.

Solucao recomendada: adicionar `server_settings` no `asyncpg.create_pool()`:

```python
pool = await asyncpg.create_pool(
    dsn=settings.database_url,
    server_settings={'search_path': 'prosauai,prosauai_ops,public'},
    ...
)
```

Com isso, **zero mudanca nas queries SQL existentes** — o `search_path` resolve `messages` como `prosauai.messages` transparentemente. O migration runner (S7) deve usar a mesma configuracao

### S2 — Phoenix Postgres Backend (Gap 2)

Alterar `docker-compose.yml` e criar `docker-compose.prod.yml`:

**Dev (docker-compose.yml):** manter SQLite como default para setup rapido local.

**Prod (docker-compose.prod.yml):**
```yaml
phoenix:
  environment:
    PHOENIX_SQL_DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}?options=-c%20search_path%3Dobservability
```

Phoenix gerencia seu proprio schema internamente. O `search_path=observability` isola as tabelas do Phoenix das tabelas de negocio.

**Alternativa avaliada e rejeitada:** Phoenix apontando para Supabase externo. Razao: traces sao write-heavy (fire-and-forget de cada span). Escrever traces no Supabase remoto adiciona latencia de rede e consome connection slots. Para VPS single-node, Postgres local e mais eficiente para traces. Supabase e reservado para dados de negocio (queries complexas, RLS, backups gerenciados).

### S3 — Log Persistence (Gap 3)

Duas camadas complementares:

**Camada 1 — Docker log rotation (dia 1, custo zero):**

```yaml
# docker-compose.yml — aplicar a TODOS os services
x-logging: &default-logging
  logging:
    driver: json-file
    options:
      max-size: "50m"
      max-file: "5"
```

Previne disco cheio. 50MB * 5 arquivos * 5 services = max 1.25GB de logs. Logs acessiveis via `docker compose logs` mesmo apos restart.

**Camada 2 — Log aggregation (recomendado, custo ~$0-5/mês):**

Adicionar sidecar ou log shipper para enviar logs a servico externo:

| Opcao | Custo | Setup | Retention | Busca |
|-------|-------|-------|-----------|-------|
| Better Stack (Logtail) | Free 1GB/mes | 1 env var + drain | 3 dias (free) / 30d (paid) | Full-text + structured |
| Grafana Cloud (Loki) | Free 50GB/mes | Promtail sidecar | 14 dias (free) | LogQL |
| Vector + file | $0 | Container sidecar | Local (disco) | grep/jq |

**Recomendacao:** Better Stack free tier como ponto de partida. Setup minimo (Docker log driver suporta HTTP drain). Upgrade para Grafana Cloud Loki quando epic 013 implementar Prometheus + Grafana (stack unificada).

**Para compliance ADR-018 (30d retention):** Docker `json-file` driver rotaciona **por tamanho, nao por tempo**. Se um service gera >250MB de logs em 10 dias, logs mais antigos sao descartados antes dos 30 dias. A retention de 30d depende do volume real de logs — monitorar apos deploy e ajustar `max-size` se necessario. Para **garantia** de 30d, log aggregation externo (Camada 2) deve ser tratado como requisito, nao opcional.

### S4 — Data Retention Cron Job (Gap 4)

Implementar script Python standalone + agendamento via cron do host ou container dedicado:

```
prosauai/ops/
    __init__.py
    retention.py      # Logica de purge por tipo de dado
    retention_cli.py  # Entry point CLI: python -m prosauai.ops.retention_cli
```

**Regras de purge (conforme ADR-018):**

| Alvo | Query | Retention | Metodo |
|------|-------|-----------|--------|
| `prosauai.messages` | `WHERE created_at < now() - interval '90 days'` | 90d (default, configuravel por tenant) | `DROP PARTITION` se particionado, `DELETE` em batch se nao |
| `prosauai.conversations` | `WHERE status = 'closed' AND closed_at < now() - interval '90 days'` | 90d | DELETE cascade (messages ja removidas) |
| `prosauai.conversation_states` | Orphaned states (conversation deletada) | Cascade | FK ON DELETE CASCADE |
| `prosauai.eval_scores` | `WHERE created_at < now() - interval '90 days'` | 90d | DELETE em batch |
| Phoenix traces | `DELETE FROM spans WHERE start_time < now() - interval '90 days'` | 90d | SQL direto no schema do Phoenix |

**Agendamento:**

```yaml
# docker-compose.prod.yml
retention-cron:
  image: prosauai:latest
  command: >
    sh -c "while true; do
      python -m prosauai.ops.retention_cli --dry-run=false;
      sleep 86400;
    done"
  environment:
    DATABASE_URL: postgresql://...
  depends_on:
    postgres:
      condition: service_healthy
```

Alternativa: `crontab` no host (`0 3 * * * docker compose exec api python -m prosauai.ops.retention_cli`). Menos elegante, mais simples.

**RLS Bypass para Purge:**

A tabela `messages` tem policy RLS `messages_no_delete` que nega todo DELETE (`FOR DELETE USING (false)`). O cron de purge precisa bypassing RLS:

| Metodo | Descricao | Seguranca |
|--------|-----------|-----------|
| `DROP PARTITION` | DDL, nao DML — bypassa RLS policies automaticamente | Seguro (operacao administrativa, nao query de dados) |
| Role `service_role` (Supabase) | Supabase service_role tem `BYPASSRLS` por default | Seguro se credencial for exclusiva do cron container |
| `SET LOCAL role = 'postgres'` | Superuser ignora RLS | Evitar — privilegio excessivo |

**Recomendacao:** Para mensagens particionadas, usar `DROP PARTITION` (instantaneo, sem DML). Para tabelas nao particionadas (conversations, eval_scores), executar DELETE com role `service_role` do Supabase. O container `retention-cron` usa `DATABASE_URL` com credencial service_role dedicada (nao a mesma do app que usa role RLS-restricted).

**Safeguards:**
- `--dry-run` mode obrigatorio no primeiro deploy (loga o que seria deletado, nao deleta)
- Logs de cada execucao com count de rows deletadas por tabela
- Nunca deleta `admin.audit_log` (365d retention, sem purge automatico)
- Respeita retention configuravel por tenant (query joinada com config do tenant)
- Cron container usa credencial `service_role` separada — nunca compartilha com app container

### S5 — Particionamento de Messages (Gap 5)

Reescrever `migrations/004_messages.sql` para criar tabela particionada:

```sql
CREATE TABLE prosauai.messages (
    id              UUID NOT NULL DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    conversation_id UUID NOT NULL,
    direction       message_direction NOT NULL,
    content         TEXT NOT NULL,
    content_type    VARCHAR(50) NOT NULL DEFAULT 'text',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (id, created_at)  -- PK inclui partition key
) PARTITION BY RANGE (created_at);
```

**Criacao automatica de particoes:**

Script ou funcao PG que cria particoes para os proximos 3 meses:

```sql
-- Criar particao para abril 2026
CREATE TABLE prosauai.messages_2026_04
    PARTITION OF prosauai.messages
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
```

**Automacao:** Incluir no cron de retention (S4):
1. **Criar** particoes futuras (3 meses a frente)
2. **Dropar** particoes expiradas (>90 dias)

**Trade-offs:**

| Aspecto | Sem particionamento | Com particionamento |
|---------|--------------------|--------------------|
| CREATE TABLE | Simples | PK deve incluir `created_at` |
| FK de conversation_id | Direto | FK nao suportada em tabela particionada PG — usar trigger ou constraint check |
| Purge (90d) | DELETE lento, write amplification | DROP PARTITION instantaneo |
| Queries por data | Full table scan | Partition pruning (somente queries com filtro `created_at` no WHERE) |
| Complexidade | Zero | Moderada (automacao de particoes) |

**Decisao sobre FK:** Postgres nao suporta FK referenciando tabela particionada **como child**. A FK `messages.conversation_id → conversations.id` funciona normalmente (messages referencia conversations, nao o contrario). A limitacao e que `conversations.id` nao pode ter FK apontando para `messages` particionada — o que nao e necessario no schema atual.

**IMPORTANTE:** A FK `messages.conversation_id REFERENCES conversations(id)` funciona em tabela particionada a partir do **Postgres 12+**. Supabase usa PG 15 — sem problema. A PK composta `(id, created_at)` e necessaria porque PG exige que a partition key faca parte da PK/UK.

**FK INBOUND — `eval_scores.message_id REFERENCES messages(id)`:**

Com PK composta `(id, created_at)`, a coluna `id` sozinha perde a constraint UNIQUE. A FK em `eval_scores` (migration 006:14) que referencia `messages(id)` **quebra**.

| Opcao | Descricao | Pros | Cons |
|-------|-----------|------|------|
| A — UNIQUE global em `id` | `CREATE UNIQUE INDEX ON prosauai.messages(id)` | FK funciona sem mudanca em eval_scores | PG 15 suporta unique indexes globais em partitioned tables. Verificar compatibilidade Supabase. Custo de escrita marginal (UUID = distribuicao uniforme) |
| B — Drop FK, constraint na app | Remover `REFERENCES messages(id)` de eval_scores. Validar no codigo Python | Zero overhead. Simples | Perde garantia de integridade referencial no BD |
| C — FK composta | Adicionar `message_created_at` em eval_scores. FK `(message_id, message_created_at) REFERENCES messages(id, created_at)` | Integridade mantida | Coluna extra em eval_scores. Queries mais verbosas |

**Recomendacao:** Opcao A. PG 15 suporta `CREATE UNIQUE INDEX ... ON partitioned_table(col)` desde PG 11 (com restricoes resolvidas no 14+). UUID v4 distribui uniformemente entre particoes. Custo de storage: ~40 bytes por row de overhead no index — negligivel para volume projetado.

### S6 — Host Monitoring Basico (Gap 6)

Adicionar monitoramento minimo de VPS sem depender de Prometheus/Grafana (que vem no epic 013):

**Opcao recomendada: Netdata agent**

```yaml
# docker-compose.prod.yml
netdata:
  image: netdata/netdata:stable
  ports:
    - "127.0.0.1:19999:19999"
  cap_add:
    - SYS_PTRACE
  volumes:
    - /proc:/host/proc:ro
    - /sys:/host/sys:ro
    - /var/run/docker.sock:/var/run/docker.sock:ro
  restart: unless-stopped
```

**O que monitora out-of-the-box:**
- CPU, RAM, disco (uso e I/O)
- Network (bandwidth, errors)
- Containers Docker (CPU, RAM, restart count)
- Alertas pre-configurados (disco >80%, RAM >90%, etc.)

**Nota de seguranca:** Montar `/var/run/docker.sock` (mesmo read-only) expoe a API Docker ao container — pode listar containers, imagens, volumes e secrets. Para VPS com dados sensíveis, avaliar o trade-off. Alternativa: Netdata sem o Docker collector (perde metricas por container, mantem host metrics) ou cAdvisor (sem socket mount).

**Alternativa minima (custo zero, sem container):**

Script bash no crontab do host que checa disco e envia alerta via webhook:

```bash
# /etc/cron.d/prosauai-disk-check
*/15 * * * * root df -h / | awk 'NR==2 && int($5)>80 {system("curl -X POST webhook_url -d disk_alert")}'
```

**Recomendacao:** Netdata para a Fase 1 (setup 5 minutos, UI local, sem custo). Substituir por Prometheus + Grafana no epic 013 quando justificar.

### S7 — Migration Runner (Gap 7)

Substituir o pattern `initdb.d` por um migration runner proper:

**Opcao recomendada: Yoyo Migrations**

Yoyo e um migration runner Python minimalista (SQL puro, sem ORM). Alinha com o approach do projeto (asyncpg direto, sem ORM).

```
migrations/
    0001.create-schemas.sql
    0001.rollback.sql
    0002.customers.sql
    0002.rollback.sql
    ...
    yoyo.ini
```

**Alternativas avaliadas:**

| Runner | Pros | Cons | Veredicto |
|--------|------|------|-----------|
| Yoyo | Python, SQL puro, simples, rollback | Menos popular | **Recomendado** — alinha com filosofia do projeto |
| Alembic | Popular, integra com SQLAlchemy | Requer SQLAlchemy (projeto usa asyncpg direto) | Overkill |
| Flyway | Popular, Java ecosystem | Container Java separado, overhead | Overkill |
| dbmate | Go binary, SQL puro, zero deps | Nao Python | Bom alternativo |
| Manual (scripts numerados) | Zero deps | Sem tracking, sem rollback, sem validacao | Status quo — insuficiente |

**Decisao: Script Python custom (nao Yoyo).**

O projeto usa asyncpg direto sem ORM e mantem principio "stdlib + pyyaml". Adicionar Yoyo (que depende de psycopg2) so para <15 migrations e overhead injustificado. Script custom:

1. Cria tabela `prosauai_ops.schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ)`
2. Lista `migrations/*.sql` em ordem numerica
3. Aplica apenas as que nao estao na tabela
4. Registra cada aplicacao

~50 linhas de Python. Sem rollback (desnecessario para schema forward-only), com tracking e idempotencia. Usa `psycopg2` sync (migrations rodam antes do app — nao precisa async).

**Integracao com docker-compose:**

```yaml
# Remover: ./migrations:/docker-entrypoint-initdb.d:ro
# Adicionar:
api:
  command: >
    sh -c "python -m prosauai.ops.migrate && uvicorn prosauai.main:app --host 0.0.0.0 --port 8050"
```

Migrations rodam antes do app iniciar. Se falharem, container nao sobe (fail-fast).

---

## Dependencies

| Dep | Status | Impacto |
|-----|--------|---------|
| 005 Conversation Core | **shipped** | Migrations existem no repo. Nenhum ambiente Postgres de producao recebeu as migrations — reescrita e segura (nao ha dados a migrar). Se migrations forem aplicadas em prod antes do 006, sera necessario migration de renomeacao de schema (mais complexo) |
| ADR-018 (Data Retention) | Accepted | Define regras de retention que este epic implementa |
| ADR-020 (Phoenix) | Accepted | Define Phoenix com Postgres backend — este epic implementa |
| ADR-011 (Pool + RLS) | Accepted | Define RLS pattern — este epic ajusta namespace da funcao helper |
| ADR-023 (TenantStore Postgres) | Proposed | Define schema `admin` — este epic reserva o namespace |

## Rabbit Holes

1. **Alembic, SQLAlchemy ou Yoyo** — NAO. O projeto usa asyncpg direto sem ORM. Adicionar SQLAlchemy so para migration runner e overhead desnecessario. Script custom ~50 LOC e suficiente para <15 migrations e alinha com filosofia do projeto (zero deps extras).
2. **Grafana + Prometheus agora** — NAO. Epic 013 (Fase 3) e o lugar certo. Netdata cobre monitoring basico sem a complexidade de provisionar dashboards.
3. **Log aggregation pago** — NAO como requisito. Docker log rotation (camada 1) e obrigatoria. Aggregation externo e recomendado mas nao blocker para deploy.
4. **Particionamento de TODAS as tabelas** — NAO. So `messages` justifica (append-only, maior volume). Demais tabelas sao pequenas ou tem lifecycle diferente.
5. **Supabase managed para Phoenix** — NAO. Traces sao write-heavy. Postgres local na VPS e mais eficiente para o volume de spans. Supabase e para dados de negocio.
6. **CI/CD pipeline** — NAO neste epic. Deploy manual via SSH + docker compose e suficiente para Fase 1 com 2 tenants. CI/CD automatizado quando houver mais de 1 pessoa deployando.

## No-gos

- Nenhuma mudanca em logica de negocio (conversation pipeline, router, debounce)
- Sem Prometheus/Grafana (epic 013)
- Sem Caddy edge proxy (epic 012)
- Sem Admin API (epic 012)
- Sem TenantStore Postgres (epic 013 — mas schema `admin` e reservado)
- Sem CI/CD pipeline

## Acceptance Criteria

1. **Schema isolation**: Todas as tabelas de negocio vivem no schema `prosauai`. Funcao `prosauai_ops.tenant_id()` funcional. Nenhuma tabela ou funcao no schema `auth` ou `public` (exceto extensions).
2. **Supabase-safe**: Migrations aplicaveis num Supabase real sem conflitos de namespace. Testado com `supabase db push` ou equivalente.
3. **Phoenix Postgres**: `docker-compose.prod.yml` configura Phoenix com Postgres backend. UI acessivel e traces persistidos apos restart do container Phoenix.
4. **Log rotation**: Todos os services no docker-compose tem `logging` configurado com `max-size` e `max-file`. Verificavel com `docker inspect`.
5. **Purge funcional**: `python -m prosauai.ops.retention_cli --dry-run` lista corretamente os dados que seriam purgados. `--dry-run=false` executa o purge. Logs de execucao com contagem de rows. Purge de messages usa `DROP PARTITION` (bypassa RLS). Purge de demais tabelas usa role `service_role` com `BYPASSRLS`.
6. **Particionamento messages**: Tabela `messages` criada como `PARTITION BY RANGE (created_at)`. Particoes para 3 meses criadas automaticamente. `EXPLAIN ANALYZE` de query com filtro de data mostra partition pruning. UNIQUE index global em `id` garante integridade da FK `eval_scores.message_id`.
7. **Migration runner**: Migrations aplicadas automaticamente no startup do container. Tabela de tracking registra quais migrations ja rodaram. Re-executar o runner nao aplica migrations duplicadas.
8. **Host monitoring**: Dashboard Netdata acessivel na VPS (localhost:19999). Alertas de disco e RAM funcionais.
9. **Docker Compose prod**: `docker-compose.prod.yml` completo com todos os services configurados para producao (log rotation, Phoenix Postgres, Netdata, retention cron).
10. **Documentacao atualizada**: containers.md, blueprint.md, roadmap.md refletem as mudancas. ADR novo para schema isolation.

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|---------|----------------------|
| 1 | Schema | Tabelas de negocio em `prosauai`, helpers em `prosauai_ops`, admin reservado para Fase 3 | ADR-011, ADR-023 (atualizar ambos) |
| 2 | Schema | `prosauai_ops.tenant_id()` substitui `auth.tenant_id()` para evitar conflito com Supabase | ADR-011 (atualizar) |
| 3 | Phoenix | SQLite para dev, Postgres para prod (`docker-compose.prod.yml`) | ADR-020 (ja decide; este epic implementa) |
| 4 | Logs | Docker json-file com rotation obrigatorio; aggregation externo recomendado | ADR-018 (atualizar consequencias) |
| 5 | Retention | Cron job Python diario. DROP PARTITION para messages, DELETE batch para demais | ADR-018 (ja decide; este epic implementa) |
| 6 | Messages | PARTITION BY RANGE (created_at) por mes | Novo — documentar em ADR-018 ou ADR dedicado |
| 7 | Migrations | Script Python custom (~50 LOC) com tracking em `prosauai_ops.schema_migrations` | Novo — nenhum ADR existente |
| 8 | Monitoring | Netdata ate epic 013 (Prometheus + Grafana) | Containers.md (atualizar) |

## Suggested Approach

### Fase 1 — Schema + Migrations (dias 1-2)

1. Criar ADR-024 para schema isolation (documenta decisao `prosauai` + `prosauai_ops`)
2. Reescrever migration 001: criar schemas `prosauai`, `prosauai_ops`, extensions, funcao `prosauai_ops.tenant_id()`
3. Reescrever migrations 002-006: prefixar tabelas com `prosauai.`, atualizar RLS policies para `prosauai_ops.tenant_id()`
4. Reescrever migration 004 (messages): adicionar `PARTITION BY RANGE (created_at)`
5. Implementar migration runner (script custom `prosauai/ops/migrate.py`)
6. Criar script de criacao automatica de particoes (`prosauai/ops/partitions.py`)
7. Testar: aplicar migrations em Postgres limpo, verificar schemas, RLS, partitions
8. Atualizar ADR-011: trocar `auth.tenant_id()` por `prosauai_ops.tenant_id()`

### Fase 2 — Docker + Prod Config (dia 3)

9. Criar `docker-compose.prod.yml` (extends docker-compose.yml)
10. Configurar log rotation em todos os services (`x-logging` anchor)
11. Configurar Phoenix com Postgres backend no prod profile
12. Adicionar Netdata container ao prod profile
13. Adicionar retention cron container ao prod profile
14. Remover `./migrations:/docker-entrypoint-initdb.d:ro` do Postgres
15. Adicionar migration runner ao startup do api container

### Fase 3 — Retention + Docs (dias 4-5)

16. Implementar `prosauai/ops/retention.py` (logica de purge)
17. Implementar `prosauai/ops/retention_cli.py` (CLI com --dry-run)
18. Testes: retention purge com dados de teste, partition drop, contagem de rows
19. Atualizar `containers.md`: adicionar Netdata, retention cron, status dos containers
20. Atualizar `blueprint.md`: schemas, log persistence, migration runner
21. Atualizar `roadmap.md`: adicionar epic 006, atualizar status
22. Atualizar ADR-018: referenciar implementacao do cron
23. Atualizar ADR-020: referenciar `docker-compose.prod.yml`

## Documentacao a Criar/Atualizar

### Novos documentos

| Documento | Conteudo |
|-----------|----------|
| `decisions/ADR-024-schema-isolation.md` | Decisao de usar schemas `prosauai` + `prosauai_ops` em vez de `public` + `auth`. Motivacao: compatibilidade Supabase, isolamento, namespace claro. |
| `epics/006-production-readiness/pitch.md` | Este documento |

### Documentos a atualizar

| Documento | Mudanca |
|-----------|---------|
| `decisions/ADR-011-pool-rls-multi-tenant.md` | Trocar todas as referencias `auth.tenant_id()` por `prosauai_ops.tenant_id()`. Adicionar secao sobre schema isolation. |
| `decisions/ADR-018-data-retention-lgpd.md` | Adicionar secao "Implementation" referenciando `prosauai/ops/retention.py`. Documentar particionamento de messages como estrategia de purge. |
| `decisions/ADR-020-phoenix-observability.md` | Adicionar nota sobre `docker-compose.prod.yml` com Postgres backend. Documentar que dev usa SQLite e prod usa Postgres. |
| `decisions/ADR-023-tenant-store-postgres-migration.md` | Confirmar que schema `admin` e compativel com novo layout de schemas. |
| `engineering/containers.md` | Adicionar Netdata ao Container Matrix. Atualizar Implementation Status (Postgres status, Phoenix backend). Adicionar retention cron ao scaling strategy. |
| `engineering/blueprint.md` | Atualizar secao de schemas. Adicionar log persistence ao stack. Documentar migration runner. |
| `planning/roadmap.md` | Adicionar epic 006 a tabela. Atualizar milestones (006 como pre-deploy). Adicionar ao gantt. |

## Riscos

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| Particionamento de messages quebra queries existentes do epic 005 | Alto | Baixa | PK composta `(id, created_at)` + UNIQUE global em `id`. FK `eval_scores.message_id` funciona via unique index. Queries por `conversation_id` nao se beneficiam de pruning mas mantem performance via index herdado |
| `prosauai_ops.tenant_id()` quebra RLS em tabelas ja criadas | Alto | Zero (se feito antes de prod) | Migrations sao reescritas, nao alteradas. Nenhum dado existe ainda |
| Phoenix nao suporta Postgres schema customizado | Medio | Baixa | Phoenix gerencia seu proprio schema. Se nao suportar `search_path`, usar database separado ou schema default |
| Script custom de migration tem bugs edge-case | Baixo | Baixa | Script e <50 LOC, testavel com pytest. Sem rollback (forward-only). Tracking via tabela `schema_migrations` garante idempotencia |
| Docker log rotation nao suficiente para 30d retention | Baixo | Media | Depende do volume de logs. 250MB por service deve cobrir 30d para 2-10 tenants. Monitorar e ajustar `max-size` |

---

> **Proximo passo:** Alinhar com epic 005 — se 005 ainda nao aplicou migrations em prod, reescrever as migrations e merge tudo junto. Se 005 ja mergeou com migrations no `public`, criar migration de renomeacao de schema (mais complexo, mas factivel).
