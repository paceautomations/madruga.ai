---
id: ADR-049
title: "Trigger Engine: Cron-Only v1 com Advisory Lock + YAML Config"
status: reviewed
deciders: [gabrielhamu]
date: 2026-04-29
supersedes: ~
---
# ADR-049 — Trigger Engine: Cron-Only v1 + Advisory Lock + YAML Config

## Status: reviewed

## Contexto

O epic 016 introduziu a necessidade de um mecanismo que despache mensagens proativas
(WhatsApp templates via Evolution API) de forma controlada, respeitando cooldown por
cliente, cap diario e consent (LGPD). As opcoes avaliadas foram:

1. **Cron-only** — loop poll de 15s com `pg_try_advisory_lock` singleton, SQL matchers puros
2. **PG NOTIFY / LISTEN** (ADR-004) — event-driven, sem poll, latencia quase zero
3. **Worker queue (ARQ/Celery)** — tarefas enfileiradas por evento, retry nativo

O sistema ja usava `pg_try_advisory_lock` em epics 010 e 014 para singletons de
maint/cron. PG NOTIFY exige reconexao ao broker e gestao de canal; para proactive sends
a latencia de 15s e aceita. Worker queue adiciona nova infra nao justificada para o
volume v1 (um agente-piloto Ariel, ~10-50 disparos/dia estimados).

## Decisao

Mecanismo de source: **cron-only em v1** (15s cadence + `pg_try_advisory_lock`
singleton por tenant). Pattern consolidado de epics 010/011/014.

Config em `tenants.yaml triggers.*` (hot-reload <60s via config_poller existente —
zero nova infra). 3 trigger types v1:

- `time_before_scheduled_event` — `customers.scheduled_event_at` dentro do lookahead
- `time_after_conversation_closed` — conversa fechada ha N horas
- `time_after_last_inbound` — ultima mensagem inbound ha N horas

PG NOTIFY listener (ADR-004) adiado para 016.1+ quando demanda real-time aparecer.

Engine implementada em `prosauai/triggers/` (scheduler.py, engine.py, matchers.py,
cooldown.py, events.py, template_renderer.py, cost_gauge.py).

## Consequencias

**Positivas:**
- Zero nova infra — reutiliza Postgres, Redis, Evolution provider ja provisionados
- Pattern conhecido: advisory lock singleton ja testado em 2 epics anteriores
- Config YAML hot-reload elimina restart para adicionar/desativar triggers

**Negativas / Trade-offs:**
- Latencia ate 15s entre elegibilidade e disparo (aceitavel para use-cases v1)
- Poll SQL a cada 15s por tenant — escala linearmente com N tenants (aceitavel ate ~50)
- PG NOTIFY (ADR-004) deferred — implementar em 016.1+ se latencia se tornar requisito

**NITs documentados no judge-report.md (backlog 016.1):**
- `intent_filter`, `agent_id_filter`, `min_message_count` declarados em YAML mas nao
  honrados em SQL (apenas warning log) — matchers reais em 016.1+
- Circuit breaker Evolution nao verificado sob 5xx storm (W5) — QA load test pendente

## Refs

- decisions.md D1, D2, D6, D15, D20–D25
- [ADR-004](ADR-004-webhook-event-bus.md) (PG NOTIFY — deferred)
- [ADR-027](ADR-027-admin-only-tables.md) (pool_admin carve-out)
- [judge-report.md](../epics/016-trigger-engine/judge-report.md)
