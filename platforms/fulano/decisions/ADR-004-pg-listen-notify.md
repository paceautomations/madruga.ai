---
title: "ADR-004: PG LISTEN/NOTIFY para eventos real-time"
status: Accepted
decision: "PG LISTEN/NOTIFY"
alternatives: "Supabase Realtime, Polling"
rationale: "Nativo PG, ~1ms, entrega confiavel dentro da transacao"
---
# ADR-004: PG LISTEN/NOTIFY para eventos real-time
**Status:** Accepted | **Data:** 2026-03-23 | **Atualizado:** 2026-03-25

## Contexto
Precisamos notificar o frontend e outros servicos sobre mudancas de estado em tempo real (ex: novo handoff, status update). Postgres ja e o banco principal. Supabase Realtime e uma alternativa managed.

## Decisao
We will usar PG LISTEN/NOTIFY nativo para eventos real-time.

Motivos:
- Entrega confiavel dentro da transacao — evento so dispara se commit acontece
- Sem dependencia externa — usa o Postgres que ja temos
- Simplicidade: `NOTIFY channel, payload` direto no SQL ou trigger
- Sem custo adicional de infra ou servico managed

## Alternativas consideradas

### Supabase Realtime
- Pros: WebSocket pronto, SDK frontend incluso, zero backend code para broadcast
- Cons: Semantica at-most-once (pode perder eventos), dependencia de servico externo, custo em escala, debugging opaco

### Polling com HTTP
- Pros: Simples de implementar, sem conexao persistente
- Cons: Latencia alta (intervalo de polling), desperdicio de recursos, nao escala bem

## Consequencias
- [+] Garantia de entrega vinculada a transacao — sem eventos fantasma
- [+] Zero infra adicional
- [+] Payload JSON flexivel (ate 8KB por mensagem)
- [-] Nao escala para broadcast massivo (1 conexao PG por listener)
- [-] Requer bridge (ex: pg2redis ou custom listener) para expor via WebSocket ao frontend
- [-] **Lock global**: Transacoes com NOTIFY pendente adquirem lock contra toda a instancia PostgreSQL, serializando transacoes. Mitigacao abaixo

## Regras obrigatorias
1. **NOTIFY sempre em transacao isolada** — NUNCA dentro de transacao de negocio (reduz contencao do lock global)
2. **Threshold de escala**: se >50 concurrent listeners ou >1K notificacoes/min, migrar para bridge pattern (PG trigger → NATS/Redis pub)
3. **PgDog proxy** como alternativa para escalar sem trocar de tecnologia — implementa pub/sub no proxy layer
