---
title: 'ADR-003: Redis Streams + DLQ para mensageria'
status: Accepted
decision: Redis Streams + DLQ
alternatives: RabbitMQ, BullMQ, Celery
rationale: Sem infra adicional — aproveita Redis existente
---
# ADR-003: Redis Streams + DLQ para mensageria
**Status:** Accepted (parcialmente implementado) | **Data:** 2026-03-23 | **Atualizado:** 2026-04-12

## Contexto
O sistema precisa de uma fila de mensagens para comunicacao assincrona entre agentes, com suporte a retry, dead-letter queue (DLQ) e consumer groups. Redis ja faz parte do stack existente.

## Decisao
We will usar Redis Streams com DLQ pattern para toda mensageria entre agentes.

Motivos:
- Redis ja esta no stack — zero infra adicional
- Streams suportam consumer groups, ACK e pending entries nativamente
- DLQ implementavel com XCLAIM + stream separada
- Latencia sub-millisegundo para o volume esperado

## Alternativas consideradas

### RabbitMQ
- Pros: Protocolo AMQP robusto, DLQ nativo, routing complexo com exchanges, battle-tested em producao
- Cons: Mais um servico para operar (Erlang), overhead de infra, overkill para o volume atual

### BullMQ
- Pros: API moderna, bom para filas de jobs, dashboard incluso (Bull Board)
- Cons: SDK Python nao e production-ready (focado em Node.js), adiciona dependencia de Node no stack Python

### Celery + Redis broker
- Pros: Padrao de facto para task queues em Python, comunidade enorme, battle-tested, suporte nativo a retry/scheduling/priority
- Cons: Overhead significativo (worker processes, beat scheduler), consumer groups menos eficientes que Redis Streams nativo, nao aproveita XREADGROUP — usa LPUSH/BRPOP internamente

## Consequencias
- [+] Sem infra adicional — aproveita Redis existente
- [+] Performance excelente para o volume projetado (< 10k msgs/min)
- [+] Consumer groups permitem escalar consumers horizontalmente
- [-] DLQ nao e first-class — requer implementacao manual com XCLAIM
- [-] Se volume crescer muito (> 100k msgs/min), pode precisar migrar para solucao dedicada

## Evolucao futura (Phase 5+)
**NATS JetStream** emergiu como alternativa superior para message broker em AI agent systems:
- 100M msgs/sec (vs Redis ~1.5M ops/sec em Pub/Sub)
- Single binary, zero external deps, sub-millisecond tail latency
- At-least-once delivery nativo, durable consumers, replay via JetStream
- Footprint operacional dramaticamente menor que Kafka ou Redis Streams standalone

Recomendacao: manter Redis Streams para Phase 1-4 (volume <10K msgs/min). Avaliar migracao para NATS JetStream no Phase 5+ quando escalar para multi-tenant de verdade. Redis continua no stack como state store e cache — apenas o papel de message broker principal seria migrado.

## Status de implementacao (2026-04-12)

A decisao de usar Redis como unica infra de mensageria foi mantida, mas a implementacao nos epics 001-004 adotou um pattern mais simples que Redis Streams:

| Aspecto | Decisao original | Implementacao real |
|---------|-----------------|-------------------|
| **Debounce** | Redis Streams (XADD/XREADGROUP) | Redis Lists (RPUSH) + keyspace notifications (`__keyevent@0__:expired`) |
| **Idempotency** | — | Redis SET NX EX (`seen:{tenant_id}:{message_id}`, TTL 24h) |
| **Consumer groups** | XREADGROUP | PubSub (psubscribe em keyevent:expired) |
| **DLQ** | XCLAIM + stream separada | Nao implementado (fail-open: em caso de erro Redis, processa mesmo assim) |
| **Atomicidade** | Streams nativo | Lua scripts atomicos (LRANGE + DEL no flush) |

**Justificativa da divergencia:** O volume atual (2 tenants internos, <100 msgs/min) nao justifica a complexidade de Redis Streams. O pattern de Lists + keyspace notifications e mais simples, debugavel e suficiente. Redis Streams sera adotado quando o worker (ARQ) for introduzido no epic 005+ e o volume justificar consumer groups reais.

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
