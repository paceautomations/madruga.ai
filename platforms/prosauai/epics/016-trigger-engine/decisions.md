---
epic: 016-trigger-engine
created: 2026-04-26
updated: 2026-04-26
---

# Registro de Decisoes — Epic 016 (Trigger Engine)

1. `[2026-04-26 epic-context]` Mecanismo de source: cron-only em v1 (15s cadence + advisory lock singleton). PG NOTIFY listener (ADR-004) adiado para 016.1+ quando demanda real-time aparecer. Pattern epic 010/011/014. (ref: Q1-A; ADR-049 novo; ADR-004 deferred)
2. `[2026-04-26 epic-context]` Trigger definition storage: `tenants.yaml triggers.*` blocks (per-tenant). Hot reload <60s via config_poller existente. Zero infra nova. Pattern consolidado em 4 epics. (ref: Q2-A; ADR-049; pattern epic 010/013/014)
3. `[2026-04-26 epic-context]` Template catalog: `tenants.yaml templates.*` blocks com `name, language, components, approval_id, cost_usd`. Manual ops cadastra apos approval Meta Business Manager. Auto-sync Graph API adiado. (ref: Q3-A; ADR-050 novo)
4. `[2026-04-26 epic-context]` Cooldown granularity: per `(tenant, customer, trigger_id)` cooldown (default 24h) + global daily cap per `(tenant, customer)` (default 3 proativos/dia). Anti-spam + anti-ban risk #4. (ref: Q4-A)
5. `[2026-04-26 epic-context]` Admin UI: YAML-only config + history viewer read-only (lista filtravel + drill-down). Editor de config form-based vira 016.1+. (ref: Q5-B)
6. `[2026-04-26 epic-context]` Trigger types pre-built v1: 3 types — `time_before_scheduled_event`, `time_after_conversation_closed`, `time_after_last_inbound`. Engine generico aceita `custom` em 016.1+. (ref: Q6-A; ADR-049)
7. `[2026-04-26 epic-context]` Persistence: nova tabela `public.trigger_events` admin-only ADR-027 carve-out. Append-only, retention 90d via cron epic 006. Schema completo com `customer_id, trigger_id, template_name, fired_at, sent_at, status, error, cost_usd_estimated, payload`. (ref: ADR-027 reaffirmed)
8. `[2026-04-26 epic-context]` Send path: novo metodo `EvolutionProvider.send_template(template_name, language, components)` chamando `/message/sendTemplate/{instance}`. Decorado com breaker + warm-up cap epic 014. (ref: epic 014 reaffirmed)
9. `[2026-04-26 epic-context]` Failure handling: template rejection (Meta 4xx) → log + skip + alert critical (sem retry, immutable). Network/5xx → retry 3x backoff (ADR-016) → handoff via epic 010. (ref: ADR-016 reaffirmed; epic 014 alert pattern)
10. `[2026-04-26 epic-context]` Cooldown enforcement: Redis state `cooldown:{tenant}:{customer}:{trigger_id}` (TTL = cooldown_hours*3600) + `daily_cap:{tenant}:{customer}:{date}` (counter, TTL 26h). Hit → status=skipped + counter Prometheus. (ref: Q4-A implementation)
11. `[2026-04-26 epic-context]` LGPD compliance: opt-in herdado (cliente que mandou ≥1 msg = consentido). SAR cascadeia `trigger_events` via `customer_id` (FK CASCADE). Retention 90d. (ref: ADR-018 reaffirmed)
12. `[2026-04-26 epic-context]` Cost monitoring: Gauge Prometheus `trigger_cost_today_usd{tenant}`. Alert rule (epic 014) > R$50/dia/tenant warning 5min. Calibracao conservadora v1; ajusta apos 30d. (ref: epic 014 alert pattern)
13. `[2026-04-26 epic-context]` Cardinality: labels Prometheus `tenant` (≤100), `trigger_id` (≤2000 total), `status` (≤5), `reason` (≤10), `template_name` (≤5000 total). <50K series. Lint no startup. (ref: epic 014 reaffirmed)
14. `[2026-04-26 epic-context]` Eval impact: triggers nao quebram heuristica `auto_resolved` (ADR-040 condicao a — `ai_active` permanece true). Observa pos-rollout sem acao automatica em v1. (ref: ADR-040 reaffirmed)
15. `[2026-04-26 epic-context]` Trigger schema YAML: `triggers.list[].id|type|enabled|match|template_ref|cooldown_hours|lookahead_hours`. (ref: ADR-049 schema concrete)
16. `[2026-04-26 epic-context]` Template schema YAML: `templates.<key>.name|language|components[].parameters[].type|ref|approval_id|cost_usd`. (ref: ADR-050 schema concrete)
17. `[2026-04-26 epic-context]` Match parameter rendering: Jinja-like sandboxed (reusando renderer epic 015) com filters builtin (`format_time`, `format_date`, `truncate`, `default`). Sem code execution. (ref: epic 015 reaffirmed)
18. `[2026-04-26 epic-context]` Customers table extension: migration `ALTER TABLE customers ADD COLUMN scheduled_event_at TIMESTAMPTZ NULL`. Habilita trigger `time_before_scheduled_event`. (ref: minimo invasivo)
19. `[2026-04-26 epic-context]` Trigger executor module: novo `apps/api/prosauai/triggers/` (engine, matchers, scheduler, events, cooldown, template_renderer). Pattern espelha `prosauai/handoff/`. (ref: novo modulo)
20. `[2026-04-26 epic-context]` Send orchestration: cron tick reads tenants.yaml → matcher → cooldown/cap check → render → persist → send_template → update status → emit metrics + Redis state. (ref: ADR-049)
21. `[2026-04-26 epic-context]` Idempotencia: antes do send, valida `trigger_events` existing por `(tenant, customer, trigger_id, lookahead_window_iso)`. Se existe sent/queued, skip. Window ISO = `{trigger_id}:{customer}:{fired_at::date}`. (ref: ADR-049)
22. `[2026-04-26 epic-context]` Match conditions v1: `intent_filter`, `agent_id_filter`, `min_message_count`, `consent_required` (default true). Sem SQL custom; tudo declarativo. (ref: ADR-049)
23. `[2026-04-26 epic-context]` Observabilidade: 5 series Prometheus via facade — `trigger_executions_total`, `trigger_template_sent_total`, `trigger_skipped_total`, `trigger_cooldown_blocked_total`, `trigger_template_rejected_total`. (ref: epic 014 dep)
24. `[2026-04-26 epic-context]` OTel baggage: span novo `trigger.cron.tick` (root) + children `trigger.match`, `trigger.cooldown_check`, `trigger.send`. Phoenix correlation. (ref: epic 002 reaffirmed)
25. `[2026-04-26 epic-context]` Admin history viewer: `GET /admin/triggers/events` paginado + filtros + drill-down modal. Reusa pattern epic 008 trace explorer. (ref: Q5-B implementation)
26. `[2026-04-26 epic-context]` Backend endpoint: `GET /admin/triggers/events` com cursor pagination. Sem cache (audit trail fresh). (ref: Q5-B implementation)
27. `[2026-04-26 epic-context]` Rollout: Ariel agente-piloto novo com 1 trigger (`ariel_match_reminder`). Shadow 3d (status='dry_run' sem send) → flip para enabled se match rate esperado. ResenhAI fica para 016.1+ apos validacao Ariel. (ref: epic 010/011/015 pattern)
28. `[2026-04-26 epic-context]` Sample size guard: hard cap 100 customers/trigger/tick. Acima → log warn + processa primeiros 100 (sorted by `customers.created_at`). Anti-tsunami. (ref: safety net)
29. `[2026-04-26 epic-context]` Drift detection: blueprint glossario tem `Trigger`+`Cooldown` mas section 3 nao lista `triggers/` package. Anote para reverse-reconcile pos-promocao. (ref: drift detectado)
30. `[2026-04-26 epic-context]` Cost overrun alert: rule Prom `trigger_cost_today_usd{tenant} > 50` 5min → warning Slack. Calibracao conservadora v1; ajusta apos 30d. (ref: epic 014 alert pattern)
