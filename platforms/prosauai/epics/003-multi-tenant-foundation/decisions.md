---
epic: 003-multi-tenant-foundation
created: 2026-04-10
updated: 2026-04-10
---
# Registro de Decisoes — Epic 003

1. `[2026-04-10 epic-context]` Alternativa D — multi-tenant estrutural, operando single-tenant-VPS com 2 tenants reais (Ariel + ResenhAI) desde dia 1 (ref: vision §1 end-state, blueprint §4.5 Multi-Tenancy, IMPLEMENTATION_PLAN.md §5.4)
2. `[2026-04-10 epic-context]` Remove HMAC completo — rip-and-replace, zero compat layer. Evolution nunca assinou webhooks (issue #102 fechada sem implementacao) (ref: IMPLEMENTATION_PLAN.md §4.1, ADR-017)
3. `[2026-04-10 epic-context]` Auth via X-Webhook-Secret estatico per-tenant, constant-time compare (ref: IMPLEMENTATION_PLAN.md §4.2.1, §4.5 validacao empirica 2026-04-10, blueprint §4.7)
4. `[2026-04-10 epic-context]` Idempotencia por (tenant_id, message_id) via Redis SETNX, TTL 24h (ref: blueprint §4.6, IMPLEMENTATION_PLAN.md §9.4, §9.5)
5. `[2026-04-10 epic-context]` Tenant como frozen dataclass + TenantStore file-backed YAML com interpolacao ${ENV_VAR} (ref: ADR-017 secrets, blueprint §4.5, ADR-023 futura migracao para Postgres)
6. `[2026-04-10 epic-context]` Parser reescrito com 12 correcoes contra 26 fixtures reais capturadas; fixture sintetica deletada (ref: IMPLEMENTATION_PLAN.md §7.6.2.1, blueprint §5 NFR testabilidade)
7. `[2026-04-10 epic-context]` ParsedMessage expandido 12 → 22 campos; schema unico com discriminator event:EventType cobre messages.upsert + groups.upsert + group-participants.update (ref: domain-model Channel BC, blueprint §1 pydantic 2)
8. `[2026-04-10 epic-context]` Sender identity compound (sender_phone + sender_lid_opaque); sender_key property = sender_lid_opaque or sender_phone (ref: IMPLEMENTATION_PLAN.md §8.0.1, Descoberta #3)
9. `[2026-04-10 epic-context]` 3-strategy mention detection: mention_lid_opaque (primary modern groups) → mention_phone (legacy) → keywords substring (ref: IMPLEMENTATION_PLAN.md §6.10, domain-model Channel BC)
10. `[2026-04-10 epic-context]` Debounce keys prefixadas: buf:/tmr:{tenant_id}:{sender_key}:{ctx}; parse_expired_key retorna (tenant_id, sender_key, group_id) (ref: blueprint §4.5 tenant isolation, ADR-003)
11. `[2026-04-10 epic-context]` _flush_echo removido; _make_flush_callback(app) resolve tenant via app.state.tenant_store ao executar (ref: IMPLEMENTATION_PLAN.md §6.11, §9.8, blueprint §4.6 sans-I/O)
12. `[2026-04-10 epic-context]` Router T7 = mudanca cirurgica de interface (settings → tenant + 3-strategy mention). Enum MessageRoute e if/elif intocados — refactor completo e do 004-router-mece rip-and-replace (ref: Shape Up epic boundary, 004-router-mece/pitch.md)
13. `[2026-04-10 epic-context]` Deploy: docker-compose.yml sem ports:, override.yml bind Tailscale no dev, Docker network privada na prod Fase 1 (ref: blueprint §2.2 DevX, §4.7 superficie de ataque minima, IMPLEMENTATION_PLAN.md §7.1, §7.2)
14. `[2026-04-10 epic-context]` Porta 8050 — evita colisao com madruga-ai (8040) e Evolution Manager (8080); mantem padrao sequencial 80X0 (ref: IMPLEMENTATION_PLAN.md §7.5)
15. `[2026-04-10 epic-context]` reactionMessage → IGNORE com reason=reaction; reaction_emoji/reaction_target_id extraidos mesmo assim para log/futuro (ref: IMPLEMENTATION_PLAN.md §8.0.3)
16. `[2026-04-10 epic-context]` Fase 2 (Caddy + Admin API + rate limit) e Fase 3 (Postgres TenantStore + billing + circuit breaker) documentadas AGORA em business/engineering + ADR-021/022/023 (ref: user request 2026-04-10, vision end-state)
17. `[2026-04-10 epic-context]` Sequencia 003 + 004 back-to-back — ambos epics partem de main separadamente, prod hold entre merges, deploy unico apos 004 merge (ref: user request 2026-04-10, Shape Up sequential epics discipline)
18. `[2026-04-10 epic-context]` Observability do 002: spans nasceriam single-tenant; delta review na promocao do 003 adiciona tenant_id como span attribute em configure_observability (~5 linhas) (ref: epic 002 research, blueprint §4.4)
19. `[2026-04-10 epic-context]` Single PR strategy — rip-and-replace HMAC + parser + multi-tenant em 1 PR; estados intermediarios quebrados sao piores que PR grande (ref: IMPLEMENTATION_PLAN.md §8.1.1, epic 001 precedent)
20. `[2026-04-10 epic-context]` Test strategy: 26 pares fixture capturados em CI via test_captured_fixtures.py parametrico; partial assertion loader; chaves _* informacionais ignoradas (ref: IMPLEMENTATION_PLAN.md §8.0.2, blueprint §5 NFR)
