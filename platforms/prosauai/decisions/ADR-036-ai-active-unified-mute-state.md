---
title: 'ADR-036: ai_active como único bit de estado de mute do handoff'
status: Accepted
decision: Substituir o campo enum `pending_handoff` (multi-step planejado no pitch)
  por uma única coluna BOOLEAN `conversations.ai_active DEFAULT TRUE`. Quando FALSE,
  o pipeline emite `ai_muted_skip` e retorna sem chamar o LLM. A escrita do estado
  é serializada via `pg_advisory_xact_lock(hashtext(conversation_id))`.
alternatives: Enum multi-step (off/pending/active/resuming), Redis key legado
  handoff:{tenant}:{sender_key}, Flag em memória no debounce buffer,
  Event-sourcing puro sem coluna de estado
rationale: Um único bit elimina estados intermediários ilegais, simplifica o
  circuit-breaker da pipeline e é compatível com advisory-lock advisory. Redis
  era write-open (nunca implementado) — substituído por PG que já tem
  consistência transacional. Enum multi-step criaria 4+ transições de estado
  e um estado machine não necessário para o valor core da feature.
---
# ADR-036: `ai_active` como único bit de estado de mute do handoff

**Status:** Accepted | **Data:** 2026-04-23 | **Relaciona:** [ADR-011](ADR-011-pool-rls-multi-tenant.md), [ADR-027](ADR-027-admin-tables-no-rls.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md)

> **Escopo:** Epic 010 (Handoff Engine + Multi-Helpdesk). Aplica-se ao esquema de `conversations`, ao pipeline de IA (`pipeline.py`), ao módulo `handoff/state.py`, às queries DB (`db/queries/conversations.py`) e ao roteador MECE (`core/router/facts.py`).

## Contexto

O pitch do epic 010 propôs um campo `pending_handoff` como enum com múltiplos estados para sinalizar transições de handoff graduais (e.g. `off → pending → active → resuming`). As referências a esse campo estão em `core/router/facts.py:66` (comentário "always False until epic 005/011") e `db/queries/conversations.py:16` (TODO `pending_handoff not yet materialised`).

Durante o design detalhado (data-model.md, plan.md PR-A) identificou-se que:

1. **O valor core da feature é binário**: o bot deve falar ou não deve falar. A lógica de transição (quem disparou o mute, quando, com que motivo) é metadata do evento, não do estado de runtime.
2. **Estados intermediários criam bugs sutis**: um enum `pending` exige que o pipeline saiba *qual* handler vai confirmar a transição, introduzindo janelas de race condition onde o estado é `pending` mas nenhum handler está ativo.
3. **Advisory lock serializa race conditions**: `pg_advisory_xact_lock(hashtext(conversation_id))` garante serialização de `mute`/`resume` concorrentes — o enum multi-step não adiciona proteção adicional.
4. **Operadores precisam de simplicidade**: mute manual via SQL deve ser `UPDATE conversations SET ai_active=false`. Um enum exigiria conhecimento da máquina de estados.

### Referências ao `pending_handoff` a remover

- `core/router/facts.py` comentário L66: "always False until epic 005/011 implement the key write" → substituído por leitura de `conversations.ai_active` via `StateSnapshot.build()`.
- `db/queries/conversations.py` TODO L16: "pending_handoff not yet materialised" → substituído pelas funções `fetch_ai_active`, `update_ai_active`, `update_external_refs_chatwoot`.

## Decisão

We will usar **uma única coluna BOOLEAN `conversations.ai_active DEFAULT TRUE`** como única fonte de verdade para o estado de mute do handoff. A decisão se decompõe em 4 partes:

### 1. Schema

```sql
-- Migration 20260501000001_create_handoff_fields.sql
ALTER TABLE conversations
  ADD COLUMN ai_active         BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN ai_muted_reason   TEXT,
  ADD COLUMN ai_muted_at       TIMESTAMPTZ,
  ADD COLUMN ai_muted_by_user_id UUID,
  ADD COLUMN ai_auto_resume_at TIMESTAMPTZ,
  ADD COLUMN external_refs     JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX CONCURRENTLY idx_conversations_ai_auto_resume_pending
  ON conversations (ai_auto_resume_at)
  WHERE ai_active=false AND ai_auto_resume_at IS NOT NULL;
```

- `ai_active=TRUE` → bot pode responder (padrão)
- `ai_active=FALSE` → bot mudo; pipeline emite `ai_muted_skip` e retorna `response_text=""`
- Colunas de metadata (`ai_muted_reason`, `ai_muted_at`, `ai_muted_by_user_id`, `ai_auto_resume_at`) são observacionais — não afetam a lógica de runtime
- `external_refs JSONB` armazena mapeamentos por helpdesk (e.g. `{"chatwoot": {"conversation_id": 123, "inbox_id": 4}}`)

### 2. Escrita serializada via advisory lock

```python
# handoff/state.py
async def mute_conversation(conn, conversation_id, ...):
    # Adquire lock exclusivo por conversa — serializa mute/resume concorrentes
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtext($1))", conversation_id
    )
    # UPDATE ai_active=false
    await conn.execute(
        "UPDATE conversations SET ai_active=false, ... WHERE id=$1",
        conversation_id
    )
    # Fire-and-forget event persist (ADR-028)
    asyncio.create_task(persist_event(...))
```

O advisory lock é transacional: libera automaticamente no commit/rollback, evitando deadlocks por TTL.

### 3. Pipeline safety net — FOR UPDATE antes do LLM

```python
# pipeline.py — antes do generate_response
async with _acquire_conn(pool, tenant_id) as conn:
    row = await conn.fetchrow(
        "SELECT ai_active, ai_muted_reason FROM conversations WHERE id=$1 FOR UPDATE",
        conversation_id
    )
    if row and not row["ai_active"]:
        # Emite ai_muted_skip, retorna response_text=""
        return ConversationResponse(response_text="", is_fallback=True, ...)
```

O `FOR UPDATE` serializa contra mutes que acontecem durante os ~100 ms de latência do `classify_intent`. Fail-open: se o `FOR UPDATE` falhar, a pipeline usa o valor amortizado pré-lido (`_conv_ai_active`).

### 4. Leitura amortizada — pool_admin após conversation_get (T070)

```python
# pipeline.py — após conversation_get, antes de save_inbound
if pool_admin:
    handoff_state = await fetch_ai_active(pool_admin, conversation.id)
    _conv_ai_active = handoff_state.get("ai_active", True)  # safe default
    _conv_external_refs = handoff_state.get("external_refs") or {}
```

Usa `pool_admin` (BYPASSRLS — ADR-027) para evitar `SET LOCAL` extra dentro da pipeline.

## Consequências

### Positivas

- **Operação simples**: mute manual via SQL `UPDATE conversations SET ai_active=false WHERE id=$1` — sem máquina de estados.
- **Zero race conditions**: advisory lock + FOR UPDATE em dois pontos cobrem toda janela de race.
- **Step `ai_muted_skip` rastreável**: Admin Waterfall mostra claramente quando e por que o LLM foi pulado, sem gap no trace.
- **Rollout gradual seguro**: `handoff.mode=off` (default implícito) → pipeline nunca muta; `mode=shadow` → muta só o evento, não o bit; `mode=on` → muta o bit.

### Negativas / Trade-offs

- **`FOR UPDATE` adiciona ~2–5 ms ao p95 do caminho crítico** quando o lock está disputado. Aceitável dado o budget de SC-004 (baseline+5 ms).
- **Redis key legado (`handoff:{tenant}:{sender_key}`) não é removida no PR-A** — continua sendo lida no roteador para compatibilidade; telemetria `handoff_redis_legacy_read` rastreia o rollout. Remoção planejada para PR-B após validação em staging.
- **Sem histórico inline**: o estado atual (`ai_active`) não carrega histórico de mute/resume. Esse papel é de `public.handoff_events` (append-only).

## Alternativas descartadas

### Enum `pending_handoff` multi-step

**Proposta original** do pitch: `off | pending | active | resuming`. Cada helpdesk dispatcher teria que entender qual transição de estado acionar.

**Problema**: estados intermediários (`pending`, `resuming`) criam janelas onde o estado não é nem "bot fala" nem "bot está mudo", exigindo que toda peça de código que lê o estado entenda a semântica de cada transição. O advisory lock já serializa as transições — o enum não adiciona valor.

### Redis key legado (`handoff:{tenant}:{sender_key}`)

A key Redis **nunca foi escrita** em produção (a escrita estava planejada para epic 005/011 mas não foi implementada). A leitura está no webhook handler como "contrato aberto". Manter Redis como fonte de verdade criaria:

- Necessidade de sincronização entre Redis e PG no mute/resume
- TTL management separado do `ai_auto_resume_at`
- Operação de mute manual precisaria escrever em dois lugares

### Flag em memória no debounce buffer

Inviável em multi-instance deployment. Não persiste entre restarts. Não suporta mute de conversas que já estão em debounce buffer.

### Event-sourcing puro (sem coluna de estado)

Lento: derivar o estado atual exigiria replay de todos os eventos de uma conversa a cada requisição. `SELECT max(event_type) FROM handoff_events WHERE conversation_id=$1` seria um anti-pattern para latência no hot-path.

## Referências de código

| Arquivo | Linha | Descrição |
|---------|-------|-----------|
| `apps/api/prosauai/conversation/pipeline.py` | ~1092 | Amortized read (T070) |
| `apps/api/prosauai/conversation/pipeline.py` | ~1328 | FOR UPDATE safety net (T072) |
| `apps/api/prosauai/conversation/step_record.py` | STEP_NAMES[13] | `ai_muted_skip` step name |
| `apps/api/prosauai/handoff/state.py` | `mute_conversation` | Advisory lock + UPDATE |
| `apps/api/prosauai/db/queries/conversations.py` | `fetch_ai_active` | Pool_admin amortized query |
| `apps/api/prosauai/db/queries/conversations.py` | `fetch_ai_active_for_update` | FOR UPDATE safety net query |
| `apps/api/prosauai/core/router/facts.py` | `StateSnapshot.build` | PG precedence over Redis |
| `apps/api/prosauai/api/webhooks/__init__.py` | `handoff_redis_legacy_read` | Deprecation telemetry |

---
handoff:
  from: speckit.implement
  to: speckit.implement
  context: "ADR-036 documenta a decisão de usar ai_active BOOLEAN como bit unificado
    de mute. Próximas tasks: T111 ADR-037 (HelpdeskAdapter pattern), T120 benchmark
    gate PR-A, T130-T131 merge gates."
  blockers: []
  confidence: Alta
  kill_criteria: "Se a latência do FOR UPDATE ultrapassar baseline+10ms em staging
    (SC-004), considerar substituição por flag Redis-first com PG eventual."
