---
epic: 014-alerting-whatsapp-quality
created: 2026-04-26
updated: 2026-04-26
---

# Registro de Decisoes — Epic 014 (Alerting + WhatsApp Quality)

1. `[2026-04-26 epic-context]` Stack alerting: Prometheus + Alertmanager self-hosted no `docker-compose.prod.yml` (2 services novos). Reusa pattern Phoenix/Infisical/retention-cron do epic 006. TSDB local em volume com retention 15d. (ref: Q1-A; ADR-045 novo)
2. `[2026-04-26 epic-context]` Metrics exposure: `prometheus_client` lib + endpoint `GET /metrics` no FastAPI app, scraped pelo Prometheus. Migration controlada com dual-emit (structlog facade legacy + Prometheus em paralelo). (ref: Q2-A; ADR-045)
3. `[2026-04-26 epic-context]` Quality monitoring: dual path — (i) Meta Cloud direct via Graph API poll a cada 15min; (ii) Evolution-hosted via quality inferida de error rate local + read receipts. Mesma metrica com label `source`. (ref: Q3-A; ADR-046 novo)
4. `[2026-04-26 epic-context]` Warm-up: cap manual em `tenants.yaml warmup.daily_cap_per_number` (default 1000 = Meta TIER_1K). Auto-warmup adiado para 014.1+. (ref: Q4-B)
5. `[2026-04-26 epic-context]` Send breaker scope: per `(tenant, phone_number_id)`. Abre quando error_rate >5%/5min OU quality_rating==RED OU tier downgrade TIER_1K apos 14d. Half-open apos 5min. DLQ Redis. (ref: Q5-A; ADR-015 extended)
6. `[2026-04-26 epic-context]` Cut-line v1: tudo em 2 semanas (monitoring + alerting + breaker + warm-up + admin Saude tab). Cut-line mole: admin tab vira 014.1 se sem 2 estourar. (ref: Q6-B)
7. `[2026-04-26 epic-context]` Admin Saude tab: nova aba (9a) com firing alerts + 6 sparklines + lista numeros WhatsApp (quality_rating + tier + cap usado). Read-only v1; actions em 014.1+. (ref: user-added 2026-04-26)
8. `[2026-04-26 epic-context]` Backend endpoint admin Saude: `GET /admin/metrics/health` proxy para Prometheus query API + Alertmanager API + `tenants.yaml` runtime. Cache Redis 30s. (ref: derivado #7)
9. `[2026-04-26 epic-context]` Failure handling poller: fire-and-forget per tenant. Falha em 1 tenant nao para o cron geral. Emit `whatsapp_quality_poll_errors_total`. (ref: ADR-028 reaffirmed)
10. `[2026-04-26 epic-context]` Failure handling app: pull-based — app expoe `/metrics` em-process, sem dependencia de Prometheus no startup. Prom down → metricas perdidas, app continua. (ref: ADR-045)
11. `[2026-04-26 epic-context]` Failure handling Alertmanager: down → Prom continua avaliando rules em estado pending. Sem perda permanente. Slack webhook tem retry build-in. (ref: ADR-045)
12. `[2026-04-26 epic-context]` Alert routing: Slack incoming webhook (channel `#prosauai-alerts`) + email ops fallback. PagerDuty para 1o cliente externo (014.1+). 3 severidades com agrupamento diferente (instant/5min/1h). (ref: sem pergunta — recomendacao base)
13. `[2026-04-26 epic-context]` Alert rules base (sem 1): 6 rules (service down, pipeline_p95 >3s, eval_score_below_threshold increase, tool_breaker_open, helpdesk_breaker_open, handoff_breaker_open). (ref: ADR-045)
14. `[2026-04-26 epic-context]` Alert rules WhatsApp (sem 2): 4 rules (quality RED 5min, quality YELLOW 30min, send_breaker_open 1min, send_throttled rate >0). (ref: ADR-046)
15. `[2026-04-26 epic-context]` Quality poll cadence: 15min interval com advisory lock singleton. Backoff 60s on Meta API 429. Circuit breaker apos 3 erros consecutivos. (ref: epic 010/011 pattern)
16. `[2026-04-26 epic-context]` Quality inferred derivation: janela 5min, error_rate >0.10 → RED; >0.05 OR read_receipt_ratio <0.50 → YELLOW; senao GREEN. Min sample 20 msgs antes de avaliar. (ref: ADR-046)
17. `[2026-04-26 epic-context]` Warm-up cap enforcement: `EvolutionProvider.send_text` consulta Redis counter `warmup:{tenant}:{phone_number_id}:{date}` antes do envio. Cap exceeded → `WhatsAppCapExceeded` → handoff via epic 010 OU mensagem amigavel. (ref: Q4-B implementation)
18. `[2026-04-26 epic-context]` Phone numbers source: nao cria nova tabela. Lista em runtime via TenantStore (Meta Cloud `phone_number_id` em `tenants.yaml`; Evolution derivado de instance name). (ref: Q3-A consequencia)
19. `[2026-04-26 epic-context]` Migration metrics legacy: dual-emit (eventos `event=metric` legacy + Prometheus em paralelo) durante semana 1. Cleanup em 014.1+ apos validacao. Zero downtime. (ref: Q2-A migration plan)
20. `[2026-04-26 epic-context]` Endpoint `/metrics` security: SEM auth (Prom scrape pattern). Bound apenas em rede Docker interna. Acesso externo via firewall, nao app. (ref: ADR-045)
21. `[2026-04-26 epic-context]` TSDB retention: 15 dias. Estimado ~150MB para 50 series × 1 sample/15s × 15d. Historico longo via Phoenix + admin DB. (ref: ADR-045)
22. `[2026-04-26 epic-context]` Cardinality control: labels alta cardinalidade proibidos (sem `customer_phone`, `message_id`, `trace_id`). CI check de cardinalidade. Hard cap 200 series por metric. (ref: ADR-045)
23. `[2026-04-26 epic-context]` Sparklines admin Saude: 6 series (pipeline_p95, send_error_rate, eval_coverage, handoff_rate, tool_breaker_count, autonomous_resolution). Janela 24h step 1min. Cache Redis 30s. (ref: #7 implementation)
24. `[2026-04-26 epic-context]` Alerts list admin: Alertmanager API `GET /api/v2/alerts`. Renderiza com badge severity + timestamp + runbook link. Acoes em 014.1+. (ref: #7 implementation)
25. `[2026-04-26 epic-context]` Phone numbers list admin: tabela tenant + phone_number_id + source + quality_rating + tier + sent_today + cap + % usado. Refresh on-demand. (ref: #7 implementation)
26. `[2026-04-26 epic-context]` Schema send_text: param opcional `phone_number_id` (deriva de instance name se ausente). Decoracao via `@with_send_breaker(tenant, phone_number_id)`. Minimo invasivo. (ref: minimo invasivo)
27. `[2026-04-26 epic-context]` Idempotencia send: inalterada — `EvolutionProvider` mantem `idempotency_key` epic 010 T080. Breaker abre antes do send → mensagem nao perde idempotencia. (ref: epic 010 reaffirmed)
28. `[2026-04-26 epic-context]` Observabilidade meta: novas series Prometheus (`whatsapp_phone_quality`, `whatsapp_phone_messaging_tier`, `whatsapp_send_total`, `whatsapp_send_throttled_total`, `whatsapp_send_breaker_open`, `whatsapp_quality_poll_total`, `whatsapp_quality_poll_errors_total`). (ref: ADR-046)
29. `[2026-04-26 epic-context]` OTel baggage: span `pipeline.send_out` ganha attrs `whatsapp.phone_number_id`, `whatsapp.quality_rating`, `whatsapp.tier`. Trace correlation via Phoenix. (ref: epic 002 reaffirmed)
30. `[2026-04-26 epic-context]` Rollout: Ariel sem 2 com `alerting.enabled: true` + `whatsapp.quality_monitoring: true` desde dia 1 (zero risco). Send breaker em `shadow` 3d antes de `enforce`. Warm-up cap em `enforce` direto. ResenhAI 7d depois. (ref: epic 010/011 pattern)
