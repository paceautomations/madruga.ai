---
title: 'ADR-027: Admin-only tables without RLS (carve-out from ADR-011)'
status: Accepted
decision: New admin-observability tables (traces, trace_steps, routing_decisions)
  live in public.* WITHOUT row-level security; acesso exclusivo via pool_admin (BYPASSRLS).
alternatives: Apply RLS with tenant_id policy (ADR-011 default), Put admin tables
  in admin schema with GRANT-based isolation, Keep data in messages.metadata JSONB
  (no new tables)
rationale: Admin é consumidor cross-tenant por design — RLS adiciona custo sem benefício
  porque toda leitura faz bypass. Escritas vêm do pipeline/router que já usam pool_admin.
  Superfície de erro fica contida em um único pool + logging estruturado.
---
# ADR-027: Admin-only tables without RLS (carve-out from ADR-011)

**Status:** Accepted | **Data:** 2026-04-17 | **Supersede:** — | **Relaciona:** [ADR-011](ADR-011-pool-rls-multi-tenant.md), [ADR-018](ADR-018-data-retention-lgpd.md), [ADR-020](ADR-020-phoenix-observability.md)

> **Escopo:** Epic 008 (Admin Evolution). Esta ADR documenta uma **exceção explícita** ao invariante RLS-everywhere estabelecido em ADR-011. Tabelas novas criadas no epic 008 **não** receberão `ENABLE ROW LEVEL SECURITY`.

## Contexto

O epic 008 introduz três tabelas novas para sustentar o admin operacional:

| Tabela | Volume/ano estimado | Função |
|--------|---------------------|--------|
| `public.traces` | ~3.6 M rows | Trace parent (1 row por mensagem que passa pelo pipeline de IA) |
| `public.trace_steps` | ~43 M rows | 12 etapas por trace — input/output JSONB truncados em 8 KB |
| `public.routing_decisions` | ~3.6 M rows | Decisão do roteador MECE (inclui DROP/LOG_ONLY invisíveis hoje) |

[ADR-011](ADR-011-pool-rls-multi-tenant.md) estabelece que **toda tabela com `tenant_id` deve ter RLS habilitado** com a policy `USING (tenant_id = public.tenant_id())`. Essa regra é a rede de segurança que impede vazamentos cross-tenant quando o código esquece um `WHERE tenant_id=$1`.

Para as três novas tabelas, entretanto, **todos os consumidores são cross-tenant por design**:

- **Leitura**: endpoints `/admin/*` (epic 007 + 008) precisam ver **todos os tenants** para:
  - Dropdown "Todos os tenants" no header (decisão 9 do pitch).
  - Overview KPIs agregados sem filtro (FR-010, FR-012).
  - Saúde por Tenant (FR-015).
  - Audit de decisões DROP/LOG_ONLY cross-tenant (FR-073).
- **Escrita**: o pipeline (`apps/api/prosauai/conversation/pipeline.py`) e o router (`apps/api/prosauai/core/router/engine.py`) escrevem via `pool_admin` porque o contexto do `SET LOCAL app.current_tenant_id` não está disponível no momento do `asyncio.create_task(persist_trace(...))` fire-and-forget (decisão 4 do pitch, ADR-028).

Em todas as situações práticas o acesso às novas tabelas será via role que já **bypassa** RLS. Aplicar RLS adiciona:

- Custo de configuração (policy + teste cross-tenant em CI que não agrega valor real).
- Overhead de avaliação da policy em cada SELECT (mesmo que bypassed) quando queries antigas são executadas pelo `pool_tenant` por engano — em vez de falhar cedo, retorna 0 rows, mascarando bugs.
- Confusão mental: desenvolvedor vê RLS habilitado e assume que pode usar `pool_tenant` para ler.

## Decisão

We will **NOT enable row-level security** nas três tabelas novas (`public.traces`, `public.trace_steps`, `public.routing_decisions`). O isolamento é garantido por:

1. **Acesso único via `pool_admin`** — apenas role `admin_role` (BYPASSRLS, já existente do epic 007) tem `GRANT SELECT/INSERT/DELETE` nas tabelas.
2. **Revogar acesso do `tenant_role`** — `REVOKE ALL ON traces, trace_steps, routing_decisions FROM tenant_role` explicitamente nas migrations.
3. **Documentação inline** — `COMMENT ON TABLE` em cada tabela referencia esta ADR: `'NO RLS — admin-only via pool_admin. See ADR-027.'`
4. **Teste negativo em CI** — novo teste em `apps/api/tests/integration/admin/test_rls_isolation.py` que tenta `SELECT FROM traces` usando `pool_tenant` e assert **permission denied** (não zero rows — permission denied é fail-loud).

Esta decisão é **restrita ao epic 008** e **não se aplica** a tabelas futuras com dados aplicacionais (que continuam sob ADR-011 default).

## Alternativas consideradas

### Aplicar RLS com policy tenant_id (ADR-011 default)

- **Pros:** consistência com todas as outras tabelas; rede de segurança caso alguém leia via `pool_tenant` por engano.
- **Cons:**
  - Policy seria **sempre bypassed** (todo leitor usa `pool_admin`) — trabalho morto.
  - Queries agregadas cross-tenant (Overview, Performance AI) teriam que rodar com `SET LOCAL role admin_role` ou equivalente, sujas no código.
  - Performance: ADR-011 alerta para 10× slowdown sem índice em `tenant_id` — as queries admin sempre filtram por `started_at`/`tenant_id`, então o índice já existe, mas o optimizer pode escolher plano pior por causa da policy.
  - Falha silenciosa: um bug que use `pool_tenant` retornaria 0 rows (sem contexto tenant setado) em vez de erro claro.
- **Rejeitada porque:** overhead sem benefício. O teste negativo em CI cobre o caso de engano com erro loud.

### Colocar em schema `admin.*` com GRANT-based isolation

- **Pros:** separação física; documenta intenção (admin-only) via namespace.
- **Cons:**
  - Conflita com ADR-024 (drift aceito de `public.*`) — criaria terceiro schema (`prosauai`, `admin`, `public`) só neste epic.
  - Cross-schema joins com `conversations` e `messages` (que são `public.*`) ficam menos ergonômicos.
  - FK lógica `trace.conversation_id → conversations.id` pede ambas no mesmo schema para legibilidade.
- **Rejeitada porque:** ganho marginal vs. custo de navegação mental. `COMMENT ON TABLE` + naming (`trace_steps` é suficientemente específico) já sinaliza admin-only.

### Manter dados em `messages.metadata JSONB` (não criar tabelas novas)

- **Pros:** zero schema novo; herda RLS existente de `messages`.
- **Cons:** já rejeitado em R1 (research.md) — queries 10× mais lentas, sem índice tipado, sem FK, sem agregação eficiente para Performance AI.
- **Rejeitada porque:** inviabiliza SC-004 (p95 Performance AI ≤2s).

## Consequências

- [+] **Zero overhead de RLS** em queries agregadas da Overview e Performance AI (evita custo sem benefício).
- [+] **Fail-loud em vez de fail-silent** — tentar ler via pool errado retorna `permission denied`, pego cedo em testes e logs.
- [+] **Documentação explícita** — `COMMENT ON TABLE` + esta ADR tornam a exceção descobrível em code review.
- [+] **Retention simples** — `retention-cron` (ADR-018) executa `DELETE` via `pool_admin` sem precisar de contexto tenant (ADR-018 já permite isso).
- [-] **Perde rede de segurança** — se amanhã um endpoint novo expuser dados cross-tenant por engano, não há RLS para bloquear. Mitigação: todo endpoint `/admin/*` requer auth JWT (FR-100) e só roles admin passam no guard.
- [-] **Exceção viral** — se futuras tabelas admin-only surgirem, será tentador estendê-las para esta exceção. Mitigação: esta ADR restringe a exceção ao epic 008; novas tabelas exigem ADR nova.
- [-] **Não bloqueia vazamento por bug de join** — um `JOIN conversations ON ...` que expõe `conversation.content` cross-tenant passa sem RLS. Mitigação: endpoints admin usam pool_admin deliberadamente — não há caminho legítimo via pool_tenant.

## Operacionalização (migrations)

Cada uma das 3 migrations do PR 1 (T010–T012) inclui:

```sql
-- NÃO habilitar RLS — consumidor cross-tenant via pool_admin
-- ALTER TABLE public.traces ENABLE ROW LEVEL SECURITY;  -- intencionalmente ausente

-- Revogar acesso de tenant_role explicitamente (defense-in-depth)
REVOKE ALL ON public.traces FROM PUBLIC;
REVOKE ALL ON public.traces FROM tenant_role;
GRANT  SELECT, INSERT, DELETE ON public.traces TO admin_role;
-- UPDATE intencionalmente ausente — tabelas append-only

COMMENT ON TABLE public.traces IS
  'Pipeline execution trace (parent of trace_steps). NO RLS — admin-only via pool_admin. See ADR-027.';
```

Idem para `trace_steps` e `routing_decisions`.

## Teste de regressão

`apps/api/tests/integration/admin/test_rls_isolation.py`:

```python
@pytest.mark.asyncio
async def test_pool_tenant_cannot_read_traces(pool_tenant):
    """pool_tenant deve receber permission denied em traces (ADR-027 carve-out)."""
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with pool_tenant.acquire() as conn:
            await conn.execute("SET LOCAL app.current_tenant_id = $1", TENANT_A)
            await conn.fetch("SELECT id FROM public.traces LIMIT 1")
```

O teste falha se por algum motivo `tenant_role` tiver `GRANT SELECT` na tabela — sinalizando que a exceção foi quebrada.

---

> **Próximo passo:** migrations no PR 1 (T010–T013) criam as tabelas seguindo este template. Code review exige citação explícita a esta ADR ao revisar as DDLs.
