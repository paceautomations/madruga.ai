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

## Extensao — Epic 010 (Handoff Engine)

O epic 010 adiciona **mais duas tabelas** sob o mesmo carve-out:

| Tabela | Volume/ano estimado | Função |
|--------|---------------------|--------|
| `public.handoff_events` | ~12 k rows (2 tenants × 500 eventos/mes × 12 meses) | Audit append-only: mutes/resumes/breaker transitions/admin replies (retention 90d via cron FR-047a) |
| `public.bot_sent_messages` | ~200 k rows (peak 100k/tenant) | Tracking 48h usado pelo NoneAdapter para evitar `fromMe` false-positive (retention 48h via cron) |

A justificativa e identica a documentada nas secoes acima:

- **Leitura cross-tenant por design** — Performance AI (epic 010 T710
  `handoff_metrics`) e o Trace Explorer filtram por tenant via URL param,
  mas a query executa via `pool_admin` (BYPASSRLS) para pagar o custo
  zero de RLS em agregados.
- **Escrita via `pool_admin`** — `prosauai.handoff.events.persist_event`
  e `prosauai.handoff.state` usam exclusivamente o pool admin (o modulo
  `handoff/` nao toca `pool_tenant` em nenhum caminho).
- **Append-only** — `handoff_events` e `bot_sent_messages` nunca sao
  atualizadas; `UPDATE` intencionalmente ausente do GRANT. Retention
  via cron `DELETE` (ADR-018 estendido).

Migrations criadas seguindo o mesmo template:

```sql
-- 20260501000002_create_handoff_events.sql (epic 010)
-- ALTER TABLE public.handoff_events ENABLE ROW LEVEL SECURITY;  -- intencionalmente ausente
REVOKE ALL ON public.handoff_events FROM PUBLIC;
REVOKE ALL ON public.handoff_events FROM tenant_role;
GRANT  SELECT, INSERT, DELETE ON public.handoff_events TO admin_role;
COMMENT ON TABLE public.handoff_events IS
  'Handoff audit trail (append-only). NO RLS — admin-only via pool_admin. See ADR-027 + ADR-036.';

-- 20260501000003_create_bot_sent_messages.sql (epic 010)
-- ALTER TABLE public.bot_sent_messages ENABLE ROW LEVEL SECURITY;  -- intencionalmente ausente
REVOKE ALL ON public.bot_sent_messages FROM PUBLIC;
REVOKE ALL ON public.bot_sent_messages FROM tenant_role;
GRANT  SELECT, INSERT, DELETE ON public.bot_sent_messages TO admin_role;
COMMENT ON TABLE public.bot_sent_messages IS
  'Bot-sent message tracking (48h retention). NO RLS — admin-only via pool_admin. See ADR-027 + ADR-038.';
```

Teste de regressao equivalente em
`apps/api/tests/integration/admin/test_rls_isolation_handoff.py`:

```python
@pytest.mark.asyncio
async def test_pool_tenant_cannot_read_handoff_events(pool_tenant):
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with pool_tenant.acquire() as conn:
            await conn.fetch("SELECT id FROM public.handoff_events LIMIT 1")


@pytest.mark.asyncio
async def test_pool_tenant_cannot_read_bot_sent_messages(pool_tenant):
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with pool_tenant.acquire() as conn:
            await conn.fetch("SELECT message_id FROM public.bot_sent_messages LIMIT 1")
```

**Restricao operacional identica**: novas tabelas admin-only criadas
fora do epic 010 exigem ADR nova (ou extensao desta), para impedir que
a excecao vire regra. Esta extensao documenta apenas as tabelas do
epic 010 — se o epic 011 precisar de mais carve-outs, deve justificar
a necessidade em nova ADR ou secao.

---

## Extensao — Epic 011 (Evals)

O epic 011 (Evals) adiciona **uma tabela** sob o mesmo carve-out:

| Tabela | Volume/ano estimado | Funcao |
|--------|---------------------|--------|
| `public.golden_traces` | <1 k rows (curadoria manual pelo admin) | Admin estrela traces exemplares (verdict append-only: `positive\|negative\|cleared`). Promptfoo generator le essa tabela para produzir suite de CI incremental. |

A justificativa e identica as tabelas dos epics 008 e 010:

- **Leitura cross-tenant por design** — admin UI (Trace Explorer do
  epic 008) mostra traces de qualquer tenant e permite estrelar.
  Promptfoo generator (cron manual ou on-demand) le todas as rows
  cross-tenant para produzir 1 YAML global (gate CI nao e per-tenant).
- **Escrita via `pool_admin`** — endpoint admin
  `POST /admin/traces/{trace_id}/golden` (epic 011 PR-B) grava via
  `pool_admin`; operadores Pace sao os unicos escritores.
- **Append-only** — tabela nunca sofre UPDATE. `verdict='cleared'` e
  o "undo" append-only (ultima row por trace_id define o estado
  efetivo). `UPDATE` intencionalmente fora do GRANT.
- **FK a `public.traces`** — `golden_traces.trace_id REFERENCES
  public.traces(trace_id) ON DELETE CASCADE` garante cleanup automatico
  quando retention 30d (ADR-018) apaga o trace parent. Sem risco de
  orphan. Requer `public.traces(trace_id)` UNIQUE (migration
  `20260601000002_alter_traces_unique_trace_id.sql`, que promove
  o indice nao-unique existente).

Migration criada seguindo o mesmo template:

```sql
-- 20260601000005_create_golden_traces.sql (epic 011)
-- ALTER TABLE public.golden_traces ENABLE ROW LEVEL SECURITY;  -- intencionalmente ausente
CREATE TABLE IF NOT EXISTS public.golden_traces (
    id                 UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id           TEXT          NOT NULL REFERENCES public.traces(trace_id) ON DELETE CASCADE,
    verdict            TEXT          NOT NULL CHECK (verdict IN ('positive', 'negative', 'cleared')),
    notes              TEXT,
    created_by_user_id UUID,
    created_at         TIMESTAMPTZ   NOT NULL DEFAULT now()
);

REVOKE ALL ON public.golden_traces FROM PUBLIC;
REVOKE ALL ON public.golden_traces FROM tenant_role;
GRANT  SELECT, INSERT ON public.golden_traces TO admin_role;
-- UPDATE + DELETE intencionalmente ausentes — append-only.
-- (DELETE automatico via ON DELETE CASCADE do FK.)

COMMENT ON TABLE public.golden_traces IS
  'Admin-curated exemplar traces. Append-only. NO RLS — admin-only via pool_admin. See ADR-027 + ADR-039.';
```

Teste de regressao equivalente em
`apps/api/tests/integration/admin/test_rls_isolation_evals.py`:

```python
@pytest.mark.asyncio
async def test_pool_tenant_cannot_read_golden_traces(pool_tenant):
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with pool_tenant.acquire() as conn:
            await conn.fetch("SELECT id FROM public.golden_traces LIMIT 1")
```

**Tabelas NAO admin-only no epic 011**: `eval_scores` (existe desde o
epic 005 — mantem RLS `tenant_isolation`). `conversations.auto_resolved`
e `messages.is_direct` sao **colunas novas em tabelas existentes** —
herdam o RLS da tabela parent sem mudanca.

**Restricao operacional identica** continua valendo: novas tabelas
admin-only criadas fora dos epics 008/010/011 exigem nova ADR ou secao.

---

> **Próximo passo:** migrations no PR 1 (T010–T013) criam as tabelas seguindo este template. Code review exige citação explícita a esta ADR ao revisar as DDLs.
