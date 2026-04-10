---
title: 'ADR-023: TenantStore migration plan — YAML file → Postgres (Fase 3 multi-tenant)'
status: Proposed
decision: Migracao one-shot YAML → Postgres com cutover, mantendo interface TenantStore identica
alternatives: Dual-write YAML + Postgres durante transicao, manter YAML indefinidamente, migrar para etcd/Consul
rationale: Trigger objetivo (>=5 tenants OU dor operacional). Migracao one-shot e mais simples que dual-write. Postgres herda RLS do ADR-011, audit log vira natural, billing integration vira viavel.
---
# ADR-023: TenantStore migration plan — YAML file → Postgres (Fase 3 multi-tenant)

**Status:** Proposed | **Data:** 2026-04-10

> **Status note:** Esta ADR e **acionavel apenas a partir da Fase 3** (epic 013). Documentada agora (2026-04-10) durante o draft do epic 003 para registrar trigger explicito e migration plan, evitando dual-write desnecessario ou debate na hora.

## Contexto

A Fase 1 (epic 003) implementa `TenantStore` file-backed YAML — adequado para 1-5 tenants internos. A Fase 2 (epic 012) mantem o mesmo storage YAML mas adiciona Admin API + hot reload. Em ambas, o `tenants.yaml` e a **single source of truth**, e a interface `TenantStore` e:

```python
class TenantStore:
    def __init__(self, tenants: list[Tenant]): ...
    @classmethod
    def load_from_file(cls, path: Path) -> TenantStore: ...
    def find_by_instance(self, instance_name: str) -> Tenant | None: ...
    def get(self, tenant_id: str) -> Tenant | None: ...
    def all_enabled(self) -> list[Tenant]: ...
```

Quando o ProsauAI atingir certa escala, YAML deixa de ser viavel:

- **>=5 tenants reais**: edicao concorrente fica frequente, atomic write + mtime lock comeca a falhar em corner cases
- **Dor operacional**: backup do tenants.yaml fica desconectado do backup do Supabase principal; rollback de operacao admin exige `git revert` no repo (frictioso)
- **Audit trail demanda**: stdout logs do epic 002 nao sao queryable historicamente (TTL 90d Phoenix); auditoria proper exige tabela append-only persistente
- **Billing integration**: Bifrost spend tracking + Stripe webhook handlers precisam de queries relacionais (`tenants JOIN usage_events`) — YAML nao suporta
- **Self-service signup**: Stripe `payment_succeeded` webhook precisa criar tenant atomicamente em transaction com row em `subscriptions` — YAML write nao e transactional com Postgres

A decisao a tomar e: **quando migrar YAML → Postgres, e como?**

## Decisao

We will migrar `TenantStore` de YAML file para Postgres em **migracao one-shot com cutover**, executada como primeira tarefa do epic 013 (Fase 3), mantendo a **interface `TenantStore` identica** para evitar refactor da app.

### Trigger de migracao (objetivo)

Implementar a migracao quando **qualquer** das condicoes for satisfeita:

1. **>=5 tenants reais simultaneos** em producao
2. **Primeiro incidente de noisy neighbor mensuravel** (1 tenant degradando outros — circuit breaker per-tenant abre 1+ vez por dia)
3. **Demanda explicita de billing automatizado** via Stripe (e nao manual via planilha)
4. **Demanda explicita de audit log persistente** (cliente enterprise pede log de quem habilitou/disabilitou)

Sem trigger objetivo, **nao migrar**. YAML e suficiente para 1-4 tenants.

### Schema Postgres novo

```sql
-- schema admin (separado do schema observability do epic 002)
CREATE SCHEMA IF NOT EXISTS admin;

-- Tenants table (substitui tenants.yaml)
CREATE TABLE admin.tenants (
    id TEXT PRIMARY KEY,
    instance_name TEXT NOT NULL UNIQUE,
    evolution_api_url TEXT NOT NULL,
    evolution_api_key_encrypted TEXT NOT NULL,  -- via Infisical SDK ou pgcrypto
    webhook_secret_encrypted TEXT NOT NULL,
    mention_phone TEXT NOT NULL,
    mention_lid_opaque TEXT NOT NULL,
    mention_keywords TEXT[] DEFAULT ARRAY[]::TEXT[],
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT,  -- admin user (Fase 3 JWT subject)
    metadata JSONB DEFAULT '{}'::jsonb  -- billing tier, limits, custom fields
);

CREATE INDEX idx_tenants_enabled ON admin.tenants(enabled) WHERE enabled = true;
CREATE INDEX idx_tenants_instance_name ON admin.tenants(instance_name);

-- Audit log (append-only)
CREATE TABLE admin.audit_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT REFERENCES admin.tenants(id),
    actor TEXT NOT NULL,  -- JWT subject ou 'system'
    action TEXT NOT NULL,  -- create | update | enable | disable | rotate_secret | delete
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_log_tenant ON admin.audit_log(tenant_id, created_at DESC);

-- RLS herdada do ADR-011 padrao
ALTER TABLE admin.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin.audit_log ENABLE ROW LEVEL SECURITY;

-- Multi-org admins (Fase 3): policy permite admin so ver tenants do seu org
CREATE POLICY tenant_admin_isolation ON admin.tenants
    USING (
        (auth.jwt() ->> 'role' = 'platform_admin')
        OR (metadata ->> 'org_id' = (auth.jwt() ->> 'org_id'))
    );
```

### TenantStore loader novo

```python
# prosauai/core/tenant_store.py — Fase 3
class TenantStore:
    # Interface IDENTICA — codigo da app nao muda
    def __init__(self, tenants: list[Tenant]): ...
    def find_by_instance(self, instance_name: str) -> Tenant | None: ...
    def get(self, tenant_id: str) -> Tenant | None: ...
    def all_enabled(self) -> list[Tenant]: ...

    @classmethod
    async def load_from_db(cls, conn: asyncpg.Connection) -> TenantStore:
        rows = await conn.fetch(
            "SELECT id, instance_name, evolution_api_url, "
            "       pgp_sym_decrypt(evolution_api_key_encrypted, $1) AS evolution_api_key, "
            "       pgp_sym_decrypt(webhook_secret_encrypted, $1) AS webhook_secret, "
            "       mention_phone, mention_lid_opaque, mention_keywords, enabled "
            "FROM admin.tenants WHERE enabled = true",
            settings.tenant_encryption_key,
        )
        tenants = [Tenant(**dict(row)) for row in rows]
        return cls(tenants)

    # load_from_file ainda existe — usado em testes e dev local
```

### Migration plan (one-shot)

```text
PR#1 (epic 013, dia 1):
  1. Criar schema admin.tenants + admin.audit_log no Supabase (migration tool: alembic ou raw SQL)
  2. Implementar TenantStore.load_from_db() (novo metodo)
  3. Implementar prosauai/core/tenant_writer.py (CRUD via asyncpg)
  4. Atualizar prosauai/api/admin.py para escrever no DB em vez de YAML
  5. Adicionar feature flag TENANT_STORE_BACKEND={file|db} em Settings (default: file na Fase 2)
  6. Testes: load_from_db, write_tenant, audit_log entries

PR#2 (epic 013, dia 2-3):
  1. Migration script standalone: tools/migrate_tenants_yaml_to_db.py
     - Le tenants.yaml atual
     - Insere cada tenant em admin.tenants (encriptando secrets via pgcrypto)
     - Insere audit log entry "migrated_from_yaml" para cada
     - Verifica row count vs YAML count
  2. Dry-run mode (--dry-run flag)

PR#3 (epic 013, dia 3 — cutover):
  1. Backup tenants.yaml para tenants.yaml.bak
  2. Rodar migration script com --dry-run, validar
  3. Rodar migration script real
  4. Trocar TENANT_STORE_BACKEND=db em prod env
  5. Restart prosauai-api (lifespan agora carrega TenantStore.load_from_db)
  6. Smoke test: webhook real + admin API ainda funcionam
  7. Deletar tenants.yaml apos 24h de operacao limpa em prod
```

### Estrategia de cutover

- **Cutover, nao dual-write**: nao escrever em YAML + DB simultaneamente. Razao: dual-write cria estados inconsistentes (YAML escreve mas DB falha = drift). Escolher um e ir.
- **Rollback plan**: se algo der errado nas primeiras 24h, restaurar `tenants.yaml.bak` + voltar `TENANT_STORE_BACKEND=file` + restart. Os audits do periodo dual ficam no DB (sao append-only, nao perdem).
- **Janela de risco**: ~5 minutos (tempo de restart do container). Como ProsauAI roda atras de Caddy ([ADR-021](ADR-021-caddy-edge-proxy.md)) com health check, Caddy serve `503` durante o restart. Webhooks da Evolution sao retry-aware (ate 10x backoff exponencial), entao o periodo de downtime e absorvido.
- **Comunicacao**: tenants externos sao avisados 24h antes via email automatizado. Operacao em janela de baixo trafego (madrugada BR).

## Alternativas consideradas

### Dual-write YAML + Postgres durante transicao
- **Pros:** zero downtime, rollback trivial (desliga DB write, fica so YAML)
- **Cons:** **states drift**: se write em YAML succeed mas DB falha, dois sources of truth divergem; logica fica complexa (qual leitura ganha?); duplica codigo de write em 2 lugares; **scope creep**: o que era cutover de 3 PRs vira refactor de varias semanas. **Rejeitado por engenharia desnecessaria.**

### Manter YAML indefinidamente
- **Pros:** zero migracao, zero risco
- **Cons:** **bloqueia self-service** (Stripe webhook nao consegue criar tenant atomicamente em transaction com row em `subscriptions`); audit log fica em logs ephemeros (90d Phoenix TTL); billing manual sem foundation transactional. **Aceitavel ate o trigger objetivo, rejeitado depois.**

### Migrar para etcd / Consul
- **Pros:** key-value distribuido com watch nativo, popular em K8s
- **Cons:** **mais 1 servico** para operar; sem queries relacionais (nao integra com `usage_events`/`audit_log`/`subscriptions`); **divorcia tenant config do Supabase principal** que ja temos; sem RLS herdada; **rejeitado** — Postgres single source of truth e o pattern do projeto inteiro ([ADR-011](ADR-011-pool-rls-multi-tenant.md)).

### Migrar para SQLite local
- **Pros:** zero dependencia externa, file-based como YAML
- **Cons:** mesma falta de audit/RLS/relational queries que YAML; nao e Supabase (precisa duplicar backup, nao integra com schema admin); **rejeitado** — overhead de SQL sem o beneficio relacional.

## Consequencias

- [+] **Interface `TenantStore` IDENTICA** — codigo da app (webhooks.py, debounce.py, lifespan) nao muda. Apenas o loader e diferente.
- [+] **Audit log persistente** com queries relacionais (`SELECT * FROM admin.audit_log WHERE tenant_id = ?`)
- [+] **RLS herdada** do padrao [ADR-011](ADR-011-pool-rls-multi-tenant.md) — multi-org admin futuro funciona automaticamente
- [+] **Stripe integration viavel** — webhook handler cria tenant + subscription em uma transaction
- [+] **Backup/restore unificado** com Supabase principal — pg_dump cobre tudo
- [+] **Encryption-at-rest** dos secrets via pgcrypto ou Infisical SDK
- [+] **Migracao one-shot** e simples (3 PRs, ~3 dias de trabalho), nao um refactor multi-semanas
- [-] **Janela de downtime** ~5 minutos durante cutover (mitigado pelo retry da Evolution + Caddy 503 graceful)
- [-] **Mais 1 servico no critical path do startup** — se Supabase estiver inacessivel no lifespan, app nao sobe. Mitigacao: cache local em arquivo se DB temporariamente down (futuro)
- [-] **Migration script precisa ser idempotente** — rodar duas vezes nao deve criar duplicatas. Mitigacao: `INSERT ... ON CONFLICT (id) DO UPDATE`
- [-] **Encryption key management** novo — `tenant_encryption_key` precisa estar em Infisical (ja documentado em [ADR-017](ADR-017-secrets-management.md))
- [-] **Migracao e 1-way-door operacional** — uma vez no DB, voltar para YAML e dor. Mitigacao: backup pre-cutover preservado por 30 dias.

---

> **Proximo passo:** monitorar trigger objetivo (>=5 tenants OU dor operacional). Quando satisfeito, implementar como parte do epic 013 (Operacao Fase 3) junto com circuit breaker, billing automation e alertas.
