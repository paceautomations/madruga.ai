---
title: 'ADR-028: Pipeline trace persistence via fire-and-forget asyncio.create_task'
status: Accepted
decision: Persist trace + 12 trace_steps (and routing_decisions) in a single
  asyncio.create_task scheduled after the critical path, with batch INSERT in
  one transaction. Failures are logged and swallowed — never propagated.
alternatives: Synchronous INSERT inside deliver step, Redis write-ahead log +
  background drainer, Dedicated asyncpg pool with producer/consumer queue,
  Rely only on Phoenix (no local persistence)
rationale: Keeps the hot-path latency budget (SC-006 ≤10ms overhead) intact
  while still giving the admin plane durable, queryable data. Mirrors the
  OTel BatchSpanProcessor pattern already in production. Failures of the
  observability side MUST NOT degrade user-facing message delivery.
---
# ADR-028: Pipeline trace persistence via fire-and-forget asyncio.create_task

**Status:** Accepted | **Data:** 2026-04-17 | **Relaciona:** [ADR-020](ADR-020-phoenix-observability.md), [ADR-027](ADR-027-admin-tables-no-rls.md), [ADR-011](ADR-011-pool-rls-multi-tenant.md)

> **Escopo:** Epic 008 (Admin Evolution). Aplica-se à escrita nas três tabelas novas — `public.traces`, `public.trace_steps`, `public.routing_decisions` — que acontecem durante ou ao fim do pipeline de IA (`apps/api/prosauai/conversation/pipeline.py::process_conversation`) e do roteador MECE (`apps/api/prosauai/core/router/engine.py::RoutingEngine.evaluate`).

## Contexto

O epic 008 adiciona observability persistente ao pipeline de IA e ao roteador. Os pontos de gravação são:

1. **Fim do pipeline** — após `deliver` (resposta enviada via Evolution API), gravar 1 row em `traces` + 12 rows em `trace_steps` (um por etapa: `webhook_received`, `route`, `customer_lookup`, `conversation_get`, `save_inbound`, `build_context`, `classify_intent`, `generate_response`, `evaluate_response`, `output_guard`, `save_outbound`, `deliver`).
2. **Dentro do roteador** — após `RoutingEngine.evaluate()` retornar a decisão, gravar 1 row em `routing_decisions`, mesmo para decisões `DROP`/`LOG_ONLY`/`BYPASS_AI` (essas nunca invocam o pipeline).

Restrições:

- **SC-006** estabelece **overhead ≤10 ms no p95** do caminho crítico (medido em staging com baseline A/B).
- **FR-033 + FR-071** exigem que falha em persistir trace/decisão **não** pode bloquear entrega da resposta ao cliente final — requisito funcional, não apenas de performance.
- Volume: ~3.6 M traces/ano × 12 steps = ~43 M INSERTs/ano em `trace_steps` sozinhos.
- Supabase PostgreSQL — latência de round-trip ~5–15 ms para INSERT simples; 1 txn com 13 INSERTs = ~20–40 ms se síncrono.
- Precedente existente: `apps/api/prosauai/observability/setup.py` já usa **OTel BatchSpanProcessor** + **OTLPSpanExporter** para Phoenix — ou seja, export assíncrono batched já é o padrão de observability da plataforma (ADR-020). Falha do Phoenix export **não** quebra o pipeline hoje.

A pergunta: qual estratégia de persistência atende (a) SC-006 overhead ≤10 ms, (b) não bloqueia delivery, (c) mantém o caminho crítico legível?

## Decisão

We will usar **fire-and-forget via `asyncio.create_task`** com batch INSERT em **uma única transação** para persistir `traces + trace_steps` e `routing_decisions`. Padrão concreto:

### 1. Buffer in-memory durante o pipeline

`Pipeline.execute()` (renomeado internamente ou via wrapper) mantém um buffer `list[StepRecord]` preenchido por cada uma das 12 etapas. Cada `StepRecord` captura `order`, `name`, `status`, `started_at`, `ended_at`, `duration_ms`, `input_jsonb` (truncado 8KB), `output_jsonb` (truncado 8KB), `model`, `tokens_in`, `tokens_out`, `tool_calls`, `error_type`, `error_message`.

### 2. Agendamento após o caminho crítico

Ao fim do span `conversation.process` (após `deliver` retornar sucesso — ou após captura do erro), disparar:

```python
# apps/api/prosauai/conversation/trace_persist.py
async def persist_trace(
    pool: asyncpg.Pool,
    trace: TracePayload,
    steps: list[StepRecord],
) -> None:
    """Batch INSERT trace + 12 steps in a single transaction.
    Raises on failure — caller MUST wrap in fire-and-forget."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO public.traces (...) VALUES (...)",
                ...,
            )
            await conn.executemany(
                "INSERT INTO public.trace_steps (...) VALUES (...)",
                [step.as_row() for step in steps],
            )


def persist_trace_fire_and_forget(
    pool: asyncpg.Pool,
    trace: TracePayload,
    steps: list[StepRecord],
) -> asyncio.Task[None]:
    """Schedule persistence; swallow and log any failure."""

    async def _safe() -> None:
        try:
            await persist_trace(pool, trace, steps)
        except Exception as exc:  # noqa: BLE001 — fire-and-forget by design
            logger.warning(
                "trace_persist_failed",
                trace_id=trace.trace_id,
                tenant_id=trace.tenant_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    return asyncio.create_task(_safe(), name=f"persist_trace:{trace.trace_id}")
```

### 3. Mesmo padrão para routing_decisions

`apps/api/prosauai/core/router/decision_persist.py::persist_routing_decision_fire_and_forget` segue a mesma forma: 1 INSERT, swallow + log, `asyncio.create_task`.

### 4. Graceful shutdown

Durante `FastAPI lifespan shutdown`, aguardar tarefas pendentes com `asyncio.wait(..., timeout=5.0)` antes de fechar o pool. Tarefas não-completadas são logadas como `trace_persist_drained_on_shutdown` (dano aceitável — telemetria, não dados do cliente).

## Alternativas consideradas

### A. INSERT síncrono dentro do `deliver` step

- **Pros:** garante persistência antes de o cliente ver a resposta; simplicidade (sem task tracking).
- **Cons:**
  - Soma ~20–40 ms ao p95 (SC-006 viola ≤10 ms).
  - Falha do Supabase → falha do pipeline → cliente vê fallback message. **Viola FR-033**.
  - Retries fazem o tempo de resposta explodir.
- **Rejeitada porque:** inviabiliza SC-006 e FR-033 simultaneamente.

### B. Redis write-ahead log + worker cron drenador

- **Pros:** desacoplamento total; buffer sobrevive a crash do Supabase.
- **Cons:**
  - Introduz **segunda fonte de verdade** — Redis stream precisa ser drenado, contado, conciliado com PG.
  - Consistency window = período em que trace existe no Redis mas não na UI — confuso para operador.
  - Novo worker = nova peça operacional para monitorar (viola Princípio I — Pragmatismo).
  - Retenção precisa ser coordenada entre Redis TTL e PG retention (ADR-018).
- **Rejeitada porque:** complexidade desproporcional para ganho marginal vs. fire-and-forget. A2 é viável se fire-and-forget for insuficiente (cenário: Supabase down por horas). Migração ficaria em backlog se P95 de `trace_persist_failed` >1% em prod.

### C. Pool asyncpg dedicado com producer/consumer queue

- **Pros:** isola escritas de observability das leituras do admin; controle fino de concorrência.
- **Cons:**
  - 2 pools para tunar (connections, max_size) — duplica complexidade de infra PG.
  - `asyncio.create_task` já executa no loop atual sem bloquear — ganho de queue é teórico.
  - Supabase não cobra por pool separado mas tem limite de conexões por plano — 2 pools consome slots desnecessariamente.
- **Rejeitada porque:** `asyncio.create_task` + reuso do `pool_admin` (ADR-027) é funcionalmente equivalente, sem custo adicional.

### D. Depender só de Phoenix (sem persistência local)

- **Pros:** zero schema novo; Phoenix já captura spans via OTel BatchSpanProcessor.
- **Cons:**
  - Phoenix é **observability tooling**, não fonte de verdade operacional. API não otimizada para queries de listagem paginada com filtros MECE.
  - Phoenix retention pode ser diferente da operacional (LGPD — ADR-018 exige 30d traces; Phoenix default pode ser maior/menor).
  - Falha de export Phoenix = perda do dado (sem escrita no PG de recuperação).
  - Admin UI do epic 008 depende de queries SQL com joins (conversations, customers, trace_steps) — Phoenix não expõe.
- **Rejeitada porque:** viola a premissa de R1 (fonte de verdade operacional precisa ser local).

## Consequências

- [+] **Hot path inalterado** — pipeline termina tão rápido quanto hoje (medido em PR 2 smoke 24h — SC-006).
- [+] **Falha de observability não derruba o cliente** — FR-033 + FR-071 atendidos por design.
- [+] **Batch INSERT em 1 txn** reduz round-trips Supabase de 13 → 1 (~15ms → ~3ms por trace).
- [+] **Alinhamento com padrão existente** — mesma filosofia do OTel BatchSpanProcessor (ADR-020).
- [+] **Simples de testar** — mock do pool permite asserted que falha não propaga (testes T021, T024, T040).
- [-] **Perda de trace em falha** — se o Supabase estiver down no momento do `persist_trace`, aquele trace **não** é recuperado. Mitigação: logs estruturados (`trace_persist_failed`) são alertáveis; Phoenix mantém o span como backup assíncrono; se P95 de falha >1% em prod, promover para alternativa B (write-ahead log).
- [-] **Graceful shutdown precisa aguardar tasks** — se o processo for killed com SIGKILL, tasks em voo são perdidas. Mitigação: FastAPI lifespan shutdown com `asyncio.wait(timeout=5.0)` + logs. Aceitável: perda máxima = ~1–2 segundos de traces durante deploy.
- [-] **Sem backpressure** — se `pool_admin` ficar saturado, mais tarefas são enfileiradas no event loop. Mitigação: `pool_admin` já configurado com `max_size=20` (epic 007); 3.6M traces/ano ÷ 365 × 86400 ≈ 0.12 inserts/s — bem abaixo do limite prático.
- [-] **Risco de vazamento de memória em task leak** — `asyncio.create_task` sem await pode acumular references em debug mode. Mitigação: passar `name=` explícito (já no código) + logging se shutdown encontrar >100 tasks pendentes.

## Métricas de sucesso (pós-deploy)

Monitorar por 7 dias após PR 2 merge:

| Métrica | Alvo |
|---------|------|
| `trace_persist_failed` rate | <0.1% das mensagens |
| Pipeline p95 overhead (A/B com baseline pré-PR2) | ≤10 ms |
| `persist_trace_drained_on_shutdown` count | <10 por deploy |
| Gap entre `message_created_at` e `trace_created_at` (p95) | <200 ms |

Se qualquer alvo for excedido sustentadamente por 3 dias, reavaliar e considerar alternativa B (Redis WAL).

## Teste de regressão

Em `apps/api/tests/unit/conversation/test_pipeline_instrumentation.py`:

```python
@pytest.mark.asyncio
async def test_persist_trace_failure_does_not_propagate(monkeypatch):
    """Fire-and-forget must swallow exceptions from persist_trace."""
    async def boom(*args, **kwargs):
        raise asyncpg.PostgresError("supabase down")
    monkeypatch.setattr("prosauai.conversation.trace_persist.persist_trace", boom)

    task = persist_trace_fire_and_forget(mock_pool, trace, steps)
    await task  # await the wrapper — should NOT raise
    assert task.exception() is None
```

---

> **Próximo passo:** PR 2 (T020–T030) implementa `trace_persist.py` + refactor do pipeline. Benchmark A/B em staging valida SC-006 antes do merge em prod.
