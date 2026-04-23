---
epic: 010-handoff-engine-inbox
created: 2026-04-23
updated: 2026-04-23
---


# Registro de Decisoes — Epic 010

1. `[2026-04-23 epic-context]` Modelo de estado: boolean `ai_active` single-bit substitui state machine multi-step — handoff e ausencia de AI, nao estado intermediario (ref: ADR-036 novo)
2. `[2026-04-23 epic-context]` Source of truth: PG `conversations.ai_active` e fonte unica — router le direto do PG no `customer_lookup` step; Redis key `handoff:*` e fact `conversation_in_handoff` deprecated no PR-A, removidos no PR-B (ref: §B4; Q1-B)
3. `[2026-04-23 epic-context]` Adapter pattern: `HelpdeskAdapter` Protocol (on_conversation_assigned, on_conversation_resolved, push_private_note, send_operator_reply, verify_webhook_signature) + registry por helpdesk_type, espelha ChannelAdapter do epic 009 (ref: ADR-037 novo)
4. `[2026-04-23 epic-context]` Escopo v1 adapters: ChatwootAdapter + NoneAdapter apenas — Blip/Zendesk adiados para epic 010.1 quando houver cliente (ref: §B2)
5. `[2026-04-23 epic-context]` Triggers de mute: 5 origens validas — chatwoot_assigned, fromMe_detected, manual_toggle, rule_match, safety_trip — cada uma gera evento `handoff_events.source` (ref: §B5 + safety guards)
6. `[2026-04-23 epic-context]` Return-to-bot: 3 gatilhos priorizados (helpdesk resolve > toggle manual > timeout 24h default); scheduler = asyncio periodic task no FastAPI lifespan + pg_try_advisory_lock singleton, cadencia 60s (ref: §B6; Q2-A)
7. `[2026-04-23 epic-context]` Chatwoot sync: webhook idempotente via Redis SETNX `handoff:wh:{event_id}` TTL 24h + HMAC per-tenant; push private note fire-and-forget ADR-028 (ref: ADR-037; BP2, BP3)
8. `[2026-04-23 epic-context]` NoneAdapter fromMe: Evolution `fromMe:true` com message_id sem match em `bot_sent_messages` → mute com `ai_auto_resume_at = now + human_pause_minutes` (default 30min); SKIP em group chat (`is_group=true`); retention 48h + cleanup cron 12h (ref: ADR-038 novo; Q5, Q2 add-on)
9. `[2026-04-23 epic-context]` Linkage ProsaUAI ↔ helpdesk: coluna `conversations.external_refs JSONB` — sem migration por helpdesk novo (ref: §B7)
10. `[2026-04-23 epic-context]` Transcripts em handoff: content processing do epic 009 continua durante `ai_active=false`; ChatwootAdapter empurra como private note fire-and-forget, NoneAdapter skip silencioso (ref: §B8)
11. `[2026-04-23 epic-context]` Race prevention: `pg_advisory_xact_lock(hashtext(conversation_id))` em qualquer transicao de `ai_active` (ref: BP5)
12. `[2026-04-23 epic-context]` Safety net no pipeline: step `generate` faz `SELECT ai_active FROM conversations WHERE id=$1 FOR UPDATE` antes do LLM call; skip sem delivery se flip aconteceu (ref: BP6)
13. `[2026-04-23 epic-context]` Ordenacao de transicoes: mute primeiro (DB commit), side effects fire-and-forget depois — nunca antes do commit de `ai_active=false` (ref: BP7)
14. `[2026-04-23 epic-context]` Feature flag per-tenant: `handoff.mode: off | shadow | on` (default off); shadow emite eventos sem mutar para medir false-mute rate antes de flipar on; removivel apos validacao do primeiro tenant (ref: BP8; Q3-B)
15. `[2026-04-23 epic-context]` Admin composer: escape hatch ops Pace (≤5% trafego), endpoint delega ao adapter; identidade outbound `sender_name=admin_user.email`, audit metadata `admin_user_id`; NoneAdapter retorna 409 (ref: §B3; Q4-A)
16. `[2026-04-23 epic-context]` Shape tenants.yaml: blocos ortogonais `helpdesk: {type, credentials...}` + `handoff: {mode, auto_resume, human_pause_minutes, rules}` (ref: §B9)
17. `[2026-04-23 epic-context]` Event sourcing: tabela `handoff_events` append-only em public (admin-only ADR-027 carve-out); todo mute/unmute gera evento; metricas derivam de queries (ref: BP1)
18. `[2026-04-23 epic-context]` Metrica cardinality: operator IDs externos em metadata mas NAO tagueados em Prometheus/Phoenix; time series usa counters agregados (ref: BP9)
19. `[2026-04-23 epic-context]` OTel baggage: conversation_id + tenant_id em baggage desde webhook inbound ate POST pro helpdesk (ref: BP10)
20. `[2026-04-23 epic-context]` Chatwoot deployment: suporta (a) shared Pace com multiplos inboxes, (b) per-tenant em VPS propria, (c) sem Chatwoot (NoneAdapter) — mesmo shape tenants.yaml (ref: §B10)
21. `[2026-04-23 epic-context]` Group chat: v1 handoff so 1:1 — grupo continua sempre com bot, semantica ambigua no backlog (ref: §C)
22. `[2026-04-23 epic-context]` Meta Cloud janela 24h: adapter retorna erro fora da janela → admin mostra alerta "cliente precisa escrever primeiro"; sem template (ref: §C)
23. `[2026-04-23 implement]` Shadow mode code e **removivel pos-validacao** (A13 spec) — ~50 LOC concentrados em 3 pontos: (a) branch `if handoff_mode == "shadow"` em `state.mute_conversation` / `state.resume_conversation`; (b) rendering hachurado + fillOpacity em `handoff-metrics.tsx`; (c) metric dedicado `handoff_shadow_events_total` + chamada em `observe_handoff_event`. Criterios de remocao: Ariel + ResenhAI em `mode=on` ha ≥30d sem rollback + sem tenant novo planejado que precise de shadow como etapa de onboarding. Remocao fica no backlog do epic 010.1; re-adicionar shadow e ~30 min caso volte a ser necessario. (ref: A13 spec, T814, rollout-runbook.md §"Criterios de remocao do codigo de shadow")
