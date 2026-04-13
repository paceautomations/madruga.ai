---
title: 'ADR-024: Schema Isolation — prosauai + prosauai_ops'
status: Accepted
decision: Schemas dedicados (prosauai + prosauai_ops) em vez de public + auth
alternatives: Usar public (default), schema unico custom, schema por tenant
rationale: Compatibilidade Supabase (zero conflito com schemas gerenciados) + isolamento
  claro entre dados de negocio e infraestrutura operacional
---
# ADR-024: Schema Isolation — prosauai + prosauai_ops
**Status:** Accepted | **Data:** 2026-04-12 | **Epic:** 006-production-readiness

## Contexto

ProsaUAI usa Supabase como provedor de Postgres gerenciado. O Supabase gerencia ativamente os schemas `auth` (autenticacao) e `public` (tabelas do dashboard). Criar objetos custom nesses schemas causa conflitos:

1. **`public`**: Supabase cria tabelas de gerenciamento e assume ownership do schema. Migrations do Supabase podem conflitar com tabelas custom.
2. **`auth`**: Schema gerenciado pelo GoTrue (auth engine). Criar funcoes como `auth.tenant_id()` — como feito originalmente no [ADR-011](ADR-011-pool-rls-multi-tenant.md) — pode ser sobrescrito por atualizacoes do Supabase.

Alem disso, a funcao RLS helper (`tenant_id()`) e a tabela de tracking de migrations (`schema_migrations`) sao infraestrutura operacional, nao dados de negocio. Mistura-los no mesmo namespace dificulta auditoria e backup seletivo.

## Decisao

Criar 4 schemas dedicados com responsabilidades claras:

| Schema | Responsabilidade | Gerenciado por |
|--------|-----------------|----------------|
| `prosauai` | Tabelas de negocio (customers, conversations, conversation_states, messages, agents, prompts, eval_scores) | Migrations da app |
| `prosauai_ops` | Infraestrutura operacional: funcao `tenant_id()` (RLS helper), tabela `schema_migrations` (tracking) | Migrations da app |
| `observability` | Tabelas do Phoenix (Arize) — traces, spans | Phoenix (auto-managed via `PHOENIX_SQL_DATABASE_SCHEMA`) |
| `admin` | Reservado para epic 013 — `tenants`, `audit_log` | Futuro |

### Resolucao de nomes via search_path

Para manter compatibilidade com queries existentes (sem schema prefix), o connection pool configura:

```python
# prosauai/db/pool.py
pool = await asyncpg.create_pool(
    dsn=settings.database_url,
    server_settings={'search_path': 'prosauai,prosauai_ops,public'},
)
```

Queries como `SELECT * FROM messages` resolvem como `prosauai.messages` transparentemente. Zero mudanca em codigo de repositorios.

### Funcao RLS migrada

```sql
-- Antes (ADR-011 original):
CREATE OR REPLACE FUNCTION auth.tenant_id() ...

-- Depois (epic 006 + hardening Supabase):
CREATE OR REPLACE FUNCTION public.tenant_id()
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT current_setting('app.current_tenant_id', true)::uuid
$$;
```

A funcao vive em `public` (nao `prosauai_ops`) para garantir resolucao via `search_path` sem depender de schemas da app. Supabase nao cria objetos em `public` com nome `tenant_id`, eliminando risco de colisao. Todas as RLS policies referenciam `public.tenant_id()` (resolvido sem prefix via `search_path`).

## Alternativas consideradas

### Continuar usando `public` + `auth`

- Pros: Zero mudanca, funciona em Postgres standalone
- Cons: Conflito direto com Supabase — `auth` e gerenciado pelo GoTrue, `public` pelo dashboard. Atualizacoes do Supabase podem sobrescrever objetos custom. Risco real de perda de dados/funcoes

### Schema unico custom (ex: `prosauai` para tudo)

- Pros: Mais simples — 1 schema em vez de 2
- Cons: Mistura dados de negocio com infraestrutura operacional. `schema_migrations` e `tenant_id()` nao sao dados de negocio. Dificulta auditoria e backup seletivo

### Schema por tenant (multi-schema)

- Pros: Isolamento maximo entre tenants
- Cons: Complexidade operacional alta — N schemas = N migrations por deploy. Nao escala alem de 50 tenants. Pool + RLS (ADR-011) ja resolve isolamento de dados. Rejeitado no ADR-011

## Consequencias

- [+] Zero conflito com Supabase — schemas `auth` intocado. `public` contem apenas `tenant_id()` SECURITY DEFINER (sem extensions — usa `gen_random_uuid()` built-in)
- [+] Separacao clara entre dados de negocio (`prosauai`) e infraestrutura (`prosauai_ops`)
- [+] Phoenix isolado em `observability` — tabelas de traces nao misturam com dados de negocio
- [+] Schema `admin` reservado — epic 013 nao precisa reorganizar nada
- [+] Queries existentes funcionam sem modificacao via `search_path`
- [-] `search_path` deve ser configurado em toda conexao (pool.py, migration runner, retention cron)
- [-] Todas as 7 migrations do epic 005 foram reescritas com schema prefix (one-time cost)
- [-] Desenvolvedores devem estar cientes do `search_path` ao criar queries diretas (ex: psql)

## Referencias

- [ADR-011](ADR-011-pool-rls-multi-tenant.md) — Pool + RLS como modelo de isolamento multi-tenant
- [Epic 006 plan.md](../epics/006-production-readiness/plan.md) — Plano de implementacao
- [Epic 006 data-model.md](../epics/006-production-readiness/data-model.md) — Layout completo dos schemas
