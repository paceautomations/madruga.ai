---
title: 'ADR-011: Pool + RLS como modelo de isolamento multi-tenant'
status: Accepted
decision: Pool + RLS
alternatives: Silo (banco por tenant), Schema separado (1 banco, N schemas), Pool
  sem RLS (apenas WHERE tenant_id = ?)
rationale: 'Uma unica superficie de infra (Postgres faz tudo: relacional + vetorial
  + eventos) — menos pecas = menos coisas pra quebrar'
---
# ADR-011: Pool + RLS como modelo de isolamento multi-tenant
**Status:** Accepted | **Data:** 2026-03-25

## Contexto
Fulano atende multiplos tenants (clientes) na mesma plataforma. Precisamos definir como isolar dados entre tenants — tanto no banco relacional quanto no vector store (pgvector) e cache (Redis). O time e de 5 pessoas, entao a complexidade operacional precisa ser minima.

Existem 3 modelos classicos de isolamento multi-tenant:
1. **Silo** — banco/instancia separada por tenant
2. **Schema separado** — mesmo banco, schema por tenant
3. **Pool compartilhado** — mesmas tabelas, `tenant_id` em toda row

## Decisao
We will usar Pool compartilhado com Row-Level Security (RLS) do PostgreSQL como modelo unico de isolamento, aplicado em todas as camadas:

- **Relacional:** Supabase PostgreSQL com RLS policies por tenant em todas as tabelas
- **Vetorial:** pgvector na mesma instancia, namespaced por `tenant_id` (sem servico de vetores separado)
- **Cache:** Redis Streams com consumer groups por tenant (ADR-003)
- **LLM:** Bifrost proxy com rate limiting e cost tracking por tenant (ADR-002)
- **Eventos:** PG LISTEN/NOTIFY com tenant context na transacao (ADR-004)

Regras obrigatorias:
- `SET LOCAL` dentro de transaction para setar tenant context — NUNCA `SET` global (anti-pattern #1)
- `CREATE INDEX` em toda coluna `tenant_id` para performance do RLS
- Cache invalidation via LISTEN/NOTIFY ou TTL maximo de 5 minutos (anti-pattern #7)

## Alternativas consideradas

### Silo (banco por tenant)
- Pros: Isolamento maximo, backup/restore trivial por tenant, zero risco de vazamento
- Cons: Custo inviavel para escalar 100+ tenants (1 Postgres por cliente), complexidade operacional enorme (N instancias, N migrations, N backups), time de 5 nao consegue operar

### Schema separado (1 banco, N schemas)
- Pros: Bom isolamento sem custo de N instancias, backup por schema, queries nao cruzam
- Cons: Migrations rodam N vezes (1 por schema) — operacionalmente pesado, nao escala bem apos 500 tenants, sem ganho real de seguranca sobre RLS para o nosso caso

### Pool sem RLS (apenas WHERE tenant_id = ?)
- Pros: Mais simples de implementar, sem overhead do RLS engine
- Cons: Um bug no WHERE = vazamento de dados entre tenants, seguranca depende 100% do desenvolvedor nunca esquecer o filtro, sem rede de seguranca

## Consequencias
- [+] Uma unica superficie de infra (Postgres faz tudo: relacional + vetorial + eventos) — menos pecas = menos coisas pra quebrar
- [+] RLS como rede de seguranca — mesmo que codigo esqueca WHERE, banco bloqueia acesso cross-tenant
- [+] Custo marginal por tenant proximo de zero (1 row a mais, nao 1 instancia a mais)
- [+] Migrations rodam uma vez so (shared schema)
- [+] Operacionalmente viavel para time de 5
- [-] RLS adiciona overhead em queries (mitiga com indices em tenant_id)
- [-] Backup/restore de 1 tenant e mais complexo (filtrar rows, nao dump schema)
- [-] Risco teorico: bug no RLS policy = vazamento. Mitiga com testes automatizados de isolamento
- [-] SET LOCAL requer disciplina — todo acesso ao banco precisa passar pelo middleware de tenant

## Hardening obrigatorio de seguranca

> **Referencia**: CVE-2025-48757 — 170+ apps expostas por RLS desabilitado no Supabase. 83% das databases Supabase expostas sao por misconfiguracao de RLS.

### 1. Wrapper function (CRITICO)
```sql
-- Permite cache por statement (STABLE) e previne bypass (SECURITY DEFINER)
CREATE OR REPLACE FUNCTION auth.tenant_id()
RETURNS UUID AS $$
  SELECT (auth.jwt() -> 'app_metadata' ->> 'tenant_id')::UUID;
$$ LANGUAGE SQL STABLE SECURITY DEFINER;
```

### 2. Policy padrao para TODA tabela
```sql
-- Template obrigatorio — aplicar em toda tabela com tenant_id
ALTER TABLE {tabela} ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {tabela}
  USING (tenant_id = auth.tenant_id());
```

### 3. Views SEMPRE com security_invoker
```sql
-- PG 15+ — previne bypass via views com security_definer
CREATE VIEW ... WITH (security_invoker = true);
```

### 4. Regras inviolaveis
- **NUNCA usar `user_metadata`** em RLS policies — editavel pelo usuario autenticado. Usar apenas `app_metadata` controlado pelo server
- **NUNCA expor service role key** no backend que processa mensagens WhatsApp. Usar apenas JWT scoped ao tenant
- **NUNCA testar RLS com superuser** — bypassa RLS por default, dando falsa confianca. Criar roles de teste com mesmas permissoes que `authenticated`
- **Index em toda coluna `tenant_id`** — sem index, RLS causa 10x slowdown (45ms → 450ms para 10K rows)

### 5. Testes automatizados cross-tenant
```python
# Rodar em CI — cria 2 tenants e asserta zero leak
async def test_rls_isolation():
    # Insert data as tenant_a
    await db.execute("SET LOCAL app.tenant_id = 'tenant_a'")
    await db.execute("INSERT INTO messages (tenant_id, content) VALUES ('tenant_a', 'secret')")

    # Query as tenant_b — DEVE retornar zero
    await db.execute("SET LOCAL app.tenant_id = 'tenant_b'")
    result = await db.fetch("SELECT * FROM messages")
    assert len(result) == 0, "RLS BREACH: tenant_b viu dados de tenant_a"
```
