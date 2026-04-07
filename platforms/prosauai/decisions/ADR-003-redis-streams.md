---
title: 'ADR-003: Redis Streams + DLQ para mensageria'
status: Accepted
decision: Redis Streams + DLQ
alternatives: RabbitMQ, BullMQ
rationale: Sem infra adicional — aproveita Redis existente
---
# ADR-003: Redis Streams + DLQ para mensageria
**Status:** Accepted | **Data:** 2026-03-23 | **Atualizado:** 2026-03-25

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
