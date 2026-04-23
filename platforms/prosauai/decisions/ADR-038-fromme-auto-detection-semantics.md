---
title: 'ADR-038: fromMe auto-detection semantics for NoneAdapter'
status: Draft
decision: >
  Tenants without an external helpdesk (`helpdesk.type: none`) rely on
  Evolution's `data.key.fromMe=true` flag to detect that a human operator
  replied to the customer. The NoneAdapter.handle_evolution_fromme hook
  (a) persists every bot-outbound in a `public.bot_sent_messages` tracking
  table, (b) classifies inbound `fromMe=true` events as bot echoes when
  the `(tenant_id, message_id)` pair exists in the table within a 10 s
  tolerance window, and (c) mutes the conversation with
  `reason='fromMe_detected'` + `auto_resume_at = now +
  tenant.handoff.human_pause_minutes` otherwise. Group conversations are
  skipped silently (v1 scope). Tracking rows retain for 48 h, cleaned up
  by a singleton cron.
alternatives: >
  Redis TTL instead of Postgres table for bot-sent tracking; no tolerance
  window (exact message_id match only); no group skip (attempt group
  handoff); hook via pipeline customer_lookup step instead of webhook; no
  retention cron (rely on Postgres TTL extension); wait for conversation
  to exist via DB trigger; rely solely on admin manual toggle.
rationale: >
  Postgres gives us transactional durability across restarts (Redis would
  lose entries on failover, causing false-positive mutes). The 10 s
  tolerance absorbs webhook delivery latency for echos of the bot's own
  messages. The 48 h retention matches Evolution's message retention for
  receipt resolution. Group skip aligns with Decision 21 of the epic
  pitch ("v1 handoff is 1:1 only"). Hooking at the webhook level keeps
  the detection independent of the pipeline customer-lookup step, which
  may run much later (debounce window). Fire-and-forget creation of
  background tasks ensures the webhook response stays on the 500 ms P95
  budget (SC-002).
---

# ADR-038: fromMe auto-detection semantics for NoneAdapter

**Status:** Draft | **Data:** 2026-04-23 | **Relaciona:** [ADR-036](ADR-036-ai-active-unified-mute-state.md), [ADR-037](ADR-037-helpdesk-adapter-pattern.md), [ADR-027](ADR-027-admin-tables-no-rls.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md)

> **Escopo:** Epic 010 (Handoff Engine + Multi-Helpdesk), PR-B. Aplica-se ao
> `NoneAdapter` (`apps/api/prosauai/handoff/none.py`), ao handler de webhook
> Evolution (`apps/api/prosauai/api/webhooks/evolution.py`) e ao scheduler
> (`apps/api/prosauai/handoff/scheduler.py`).

## Contexto

Tenants que ainda não operam com helpdesk externo (`helpdesk.type: none`) precisam de um mecanismo para que o bot silencie automaticamente quando um atendente humano responde ao cliente via outra linha WhatsApp. O único sinal disponível é o `data.key.fromMe=true` que a Evolution envia tanto para (a) mensagens que o próprio bot enviou via `sendText` e que voltam como echo, quanto para (b) mensagens que um humano (operador) digitou no WhatsApp Business.

Sem uma forma de **distinguir (a) de (b)**, qualquer tratamento ingênuo de `fromMe=true` geraria um loop: toda mensagem enviada pelo bot causaria um mute automático da conversa, bloqueando o próximo turno da IA.

Opções consideradas para tracking:

- **Redis** — TTL natural, baixa latência, mas perde dados em failover → false-positive mute.
- **Postgres** (escolhido) — durabilidade transacional, compartilhado por múltiplos workers, retention cron controlado.
- **In-memory dict** — não sobrevive a restart, inviabiliza multi-worker.

Opções para distinguir echo vs. humano:

- **Match exato de `message_id`** — funciona mas perde echoes que reusam IDs (edge case raro, mas possível em retransmissões Evolution).
- **Match de `message_id` + janela de tolerância** (escolhido) — row em `bot_sent_messages` com `sent_at >= now() - 10s` é classificada como echo; matches fora da janela são tratados como humano (operador respondeu depois).
- **Timestamp only** — vulnerável a mensagens fora de ordem.

## Decisão

### 1. Tabela de tracking

```sql
CREATE TABLE public.bot_sent_messages (
    tenant_id       UUID NOT NULL,
    message_id      TEXT NOT NULL,
    conversation_id UUID NOT NULL,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, message_id)
);
```

- Admin-only via `pool_admin` BYPASSRLS (carve-out [ADR-027](ADR-027-admin-tables-no-rls.md)).
- Escrita fire-and-forget pelo `EvolutionProvider.send_text` após cada entrega bem-sucedida (ADR-028).
- `ON CONFLICT (tenant_id, message_id) DO NOTHING` para tolerar retries do outbound.

### 2. Janela de tolerância (10 s)

A query de lookup é:

```sql
SELECT 1
  FROM public.bot_sent_messages
 WHERE tenant_id = $1
   AND message_id = $2
   AND sent_at >= now() - ($3 || ' seconds')::interval
 LIMIT 1
```

Com `$3 = 10` (constante `BOT_ECHO_TOLERANCE_SECONDS`). O filtro temporal no próprio SQL garante que matches fora da janela retornem `NULL`, disparando o mute — o operador respondeu depois do bot ter enviado a mesma mensagem. É um trade-off consciente entre:

- **Janela pequena** (1-5 s) → rejeita echoes legítimos se a Evolution demorar mais.
- **Janela média** (10 s, escolhida) → cobre 99 %+ dos casos observados em dev.
- **Janela grande** (30 s+) → aumenta a janela de supressão de mute real após envio do bot.

### 3. Skip de conversas em grupo

```python
if canonical.is_group:
    logger.info("noneadapter_group_skip", ...)
    return False
```

v1 handoff é estritamente 1:1 (Decision 21 do pitch). A semântica de "quem é o humano" em grupo é ambígua — um admin do tenant que é também membro do grupo enviaria `fromMe=true` sem necessariamente assumir o atendimento. Fallback silencioso com log estruturado permite auditoria sem poluir métricas.

### 4. Retention + cleanup

```python
# scheduler.py
BOT_SENT_MESSAGES_RETENTION_HOURS = 48         # FR-027
BOT_SENT_MESSAGES_CLEANUP_INTERVAL_SECONDS = 12 * 3600  # 12h
BOT_SENT_MESSAGES_CLEANUP_BATCH_SIZE = 5_000
```

Cron singleton cross-replicas via `pg_try_advisory_lock(hashtext('bsm_cleanup_cron'))`. Disjoint do `AUTO_RESUME_LOCK_KEY` para evitar deadlock R3 (ver plan.md § Constitution Check).

### 5. Hook no webhook Evolution (T512)

```python
# api/webhooks/evolution.py
await dispatch(request, messages, correlation_id, tenant=tenant)
_maybe_trigger_noneadapter_fromme(request, tenant, messages)  # fire-and-forget
```

O hook:

1. Gatekeep por `tenant.helpdesk.type == "none"`.
2. Filtra mensagens com `is_from_me == True` (campo novo no `CanonicalInboundMessage`, T516).
3. Para cada uma, dispara `asyncio.create_task(_run_noneadapter_fromme(...))`.

A task:

1. Resolve `conversation_id` via lookup por `(tenant_id, phone_hash)` em `pool_admin`. Retorna `None` se a conversa não existir ainda (primeira mensagem do número) → skip silencioso.
2. Chama `NoneAdapter.handle_evolution_fromme(tenant, canonical, conversation_id)`.
3. Adapter executa o check de echo (etapa 2) e, se não for echo, chama `state.mute_conversation(reason='fromMe_detected', auto_resume_at=now + human_pause_minutes)`.

## Alternativas consideradas

### A. Redis TTL em vez de Postgres

**Rejeitada por**: perda de dados em Redis failover gera false-positive mutes que silenciam o bot indevidamente. Postgres oferece durabilidade transacional sem custo adicional significativo (cleanup cron de 12 h).

### B. Match exato de `message_id` sem janela de tolerância

**Rejeitada por**: echoes com clock skew entre Evolution e Postgres podem chegar com `sent_at` em qualquer ordem relativa. A janela de 10 s cobre o ruído sem aumentar material o false-positive rate.

### C. Não skipar grupos (tentar detectar humano em grupo)

**Rejeitada por**: semântica ambígua. Quem é "o humano" em um grupo com múltiplos participantes? Reabrir o escopo exigiria uma ADR dedicada e estenderia o epic para 4+ semanas.

### D. Hook via `customer_lookup` step em vez de webhook

**Rejeitada por**: o step `customer_lookup` só roda após o debounce (janela de ~3-15 s). Um operador respondendo enquanto o bot está processando a fila perderia a chance de mutar. Webhook dispara imediatamente.

### E. Esperar a conversa existir antes de mutar (DB trigger)

**Rejeitada por**: triggers são difíceis de debugar e acoplam a lógica de handoff ao schema. O skip silencioso quando `conversation_id is None` é um trade-off aceito: primeira mensagem `fromMe=true` em um número novo não causa mute, mas também não há nada a mutar (bot ainda não respondeu nada).

### F. Sem retention cron (deixar a tabela crescer)

**Rejeitada por**: ~100k rows/tenant por mês em tenants ativos. Sem cleanup, a tabela cresceria linearmente e o `INDEX idx_bot_sent_messages_sent_at` degradaria. 48 h de retention cobre o window de echo-check com folga.

## Consequências

### Positivas

- **False-positive rate < 1%** (SC-006): tracking exato + janela de tolerância + skip de grupo cobrem os casos conhecidos.
- **Zero regressão de latência de webhook**: hook é fire-and-forget via `asyncio.create_task`; resposta 202 Accepted não aguarda o mute.
- **Observabilidade via logs estruturados**: `noneadapter_group_skip`, `noneadapter_bot_echo`, `noneadapter_fromme_muted`, `noneadapter_fromme_no_conversation`.
- **Reversível via feature flag**: `handoff.mode: on → off` desliga o pipeline de mute sem deploy (via `config_poller`).
- **Cleanup assíncrono não bloqueia o hot path**: batch size 5000 + 12 h cadence mantêm o DB saudável sem thrash.

### Negativas / Trade-offs

- **Requer `conversations.customer_id` + `customers.phone_hash`**: lookup falha para senders sem phone (pure @lid). Isso é aceitável: tenants NoneAdapter raramente têm pure @lid senders em v1.
- **Primeira mensagem `fromMe=true` em número novo não muta**: a conversa ainda não existe. Trade-off com a alternativa E: aceitar o gap de uma mensagem vs. adicionar triggers.
- **Janela de 10 s é calibrada para o ambiente atual Evolution**: se a latência de echo aumentar significativamente (>10 s p95), revisar a constante.

### Neutras

- **Dependências externas**: nenhuma (stdlib `hmac`, `hashlib`, `asyncio` já em uso).
- **Performance do hook**: 1 lookup de echo + 1 lookup de conversation_id + 1 UPDATE (no path de mute). ~2-5 ms no steady state.

## Kill criteria

Esta ADR é invalidada se:

1. **False-positive rate exceder 5%** em produção após 30 dias de shadow mode em Ariel → revisar janela de tolerância e/ou introduzir um segundo sinal (ex.: verificar se o conteúdo da mensagem corresponde a uma geração de LLM recente).
2. **Evolution mudar o semantic de `fromMe`** (ex.: passar a setar `fromMe=true` em mensagens forwarded) → redesign da detecção; pode requerer heurísticas adicionais baseadas no `pushName`.
3. **A janela de echo de 10 s provar-se insuficiente** (p95 de echo > 10 s) → aumentar para 20-30 s OU introduzir ACK assíncrono Evolution → provider callback.
4. **Handoff em grupo virar requisito** de algum tenant → redesenho completo: precisa semantic de "operator role" no metadata do grupo.

## Links

| Arquivo | Descrição |
|---------|-----------|
| `apps/api/prosauai/handoff/none.py` | `NoneAdapter.handle_evolution_fromme` + `_is_bot_echo` |
| `apps/api/prosauai/handoff/scheduler.py` | `run_bot_sent_messages_cleanup_once` + `build_bot_sent_messages_cleanup_task` |
| `apps/api/prosauai/api/webhooks/evolution.py` | Hook `_maybe_trigger_noneadapter_fromme` |
| `apps/api/prosauai/channels/canonical.py` | Campo `is_from_me` no `CanonicalInboundMessage` (T516) |
| `apps/api/prosauai/channels/outbound/evolution.py` | Escrita fire-and-forget em `bot_sent_messages` após `sendText` |
| `apps/api/db/migrations/20260501000003_create_bot_sent_messages.sql` | Schema da tabela |
| `apps/api/tests/unit/handoff/test_none.py` | Unit tests T500 |
| `apps/api/tests/integration/test_handoff_flow_none_adapter.py` | Integration tests T502 |

---
handoff:
  from: speckit.implement
  to: speckit.reconcile
  context: "ADR-038 documenta a semântica de fromMe auto-detection no NoneAdapter:
    tracking em Postgres (bot_sent_messages), janela de tolerância de 10 s,
    skip de grupo, retention 48 h via cleanup cron singleton, hook
    fire-and-forget no webhook Evolution."
  blockers: []
  confidence: Alta
  kill_criteria: "Se FP rate > 5% em produção OU Evolution mudar semantic de fromMe OU handoff em grupo virar requisito."
