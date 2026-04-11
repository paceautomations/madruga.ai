---
epic: 004-router-mece
created: 2026-04-10
updated: 2026-04-10
---
# Registro de Decisoes — Epic 004

1. `[2026-04-10 epic-context]` Router em 2 layers: classify() puro + RoutingEngine declarativo (ref: blueprint §4.6, domain-model Router aggregate)
2. `[2026-04-10 epic-context]` MessageFacts com enums fechados + invariantes __post_init__ (ref: domain-model Channel BC)
3. `[2026-04-10 epic-context]` Hit policy UNIQUE — overlap = ERROR, sem escape hatch (ref: DMN 1.3 decision table UNIQUE)
4. `[2026-04-10 epic-context]` Decision como discriminated union pydantic com 5 subtipos (ref: blueprint §1 pydantic 2 stack, ADR-001)
5. `[2026-04-10 epic-context]` classify() puro; StateSnapshot pre-carregado via MGET no caller (ref: blueprint §4.6 sans-I/O, ADR-003)
6. `[2026-04-10 epic-context]` 1 YAML por tenant em config/routing/<slug>.yaml (ref: ADR-006 §routing-configuravel, blueprint §4.5)
7. `[2026-04-10 epic-context]` Default obrigatorio no schema YAML; pydantic rejeita config sem catch-all (ref: MECE construction invariant)
8. `[2026-04-10 epic-context]` Campo agent opcional na regra; fallback para tenant.default_agent_id (ref: ADR-006 §routing-configuravel)
9. `[2026-04-10 epic-context]` Campo instance opcional no when; ausente = wildcard (ref: ADR-006)
10. `[2026-04-10 epic-context]` Exhaustiveness test = enumeracao enums+bools + Hypothesis + reachability-per-instance (ref: pipeline-contract-base.md auto-review)
11. `[2026-04-10 epic-context]` Rip-and-replace: remover enum MessageRoute, route_message, _is_bot_mentioned, _is_handoff_ativo no mesmo PR (ref: refactor discipline)
12. `[2026-04-10 epic-context]` Epic dedicado — nao absorvido em 005 Conversation Core (ref: Shape Up appetite)
13. `[2026-04-10 epic-context]` CLI router verify|explain como hook pre-commit + CI (ref: blueprint §2.2)
14. `[2026-04-10 epic-context]` Garantias MECE em 4 camadas: tipo + schema + runtime + CI (ref: blueprint §5 NFR testabilidade)
15. `[2026-04-10 epic-context draft-promotion]` [REVISADO] classify() consome InboundMessage (renomeado de ParsedMessage), nao dict — reaproveita ACL do epic 003 com 26 fixtures reais; zero canais alternativos planejados; rename alinha com domain-model.md:40-53 que ja usa InboundMessage como aggregate do Channel BC (ref: epic 003 formatter.py, domain-model.md:40-53, DDD anti-corruption layer)
16. `[2026-04-10 epic-context draft-promotion]` MentionMatchers frozen value object como 3o parametro de classify(); sem classe FactExtractor — pureza FCIS e sobre side effects, nao aridade; h11 sans-I/O faz o mesmo (per-connection config no construtor); evita fragmentar definicao de "mention" entre webhooks.py e router.py (ref: Bernhardt Functional Core Imperative Shell, h11 state machine pattern)
17. `[2026-04-10 epic-context draft-promotion]` default_agent_id: UUID | None aditivo flat no Tenant dataclass (nao via settings JSONB intermediario) — epic 003 nao shipou o campo apesar do domain-model.md:162-168 prometer; flat e type-safe no startup; quando epic 013 migrar para Postgres, JSONB settings vira colunas tipadas progressivamente (ref: domain-model.md:162-168, ADR-006 §default-agent, epic 003 tenant.py)
18. `[2026-04-10 epic-context draft-promotion]` 2 spans irmaos router.classify + router.decide sob webhook_whatsapp + 6 constantes flat em conventions.py (MATCHED_RULE, ROUTING_ACTION, DROP_REASON, EVENT_HOOK_TARGET, MESSAGE_IS_REACTION, MESSAGE_MEDIA_TYPE) — OTel guidance: operacoes com duracao/failure mode independentes = spans, nao events; reconcile-report do 002 ja pre-aprovou matched_rule como atributo compativel; namespace flat segue padrao existente (ref: OTel spec signals/traces, epic 002 reconcile-report, conventions.py)
19. `[2026-04-10 epic-context draft-promotion]` Fixtures reais config/routing/ariel.yaml + config/routing/resenhai.yaml (sem pace-automations.yaml legado) — 003 opera com 2 tenants reais desde dia 1; fixtures reais provam multi-tenant empiricamente e alinham com test_captured_fixtures.py TEST_TENANTS (ref: epic 003 pitch §2 tenants reais, tests/integration/test_captured_fixtures.py)
20. `[2026-04-10 epic-context draft-promotion]` conversation_in_handoff lido de Redis key handoff:{tenant_id}:{sender_key} em 004 com fallback False; escrita da key e contrato aberto documentado para epic 005 (Conversation Core) ou epic 011 (Admin Handoff Inbox) — fact precisa existir no modelo MECE agora para a regra handoff_bypass compilar, mesmo sem escritor no estado atual (ref: epic 005 scope, epic 011 Admin Handoff Inbox)
21. `[2026-04-10 epic-context draft-promotion]` is_membership_event: bool derivado de event == "group-participants.update" AND action in {add,remove,promote,demote}; nao expor group_event_action como fact separado — evita explosao de enums ortogonais em MessageFacts (ref: epic 003 ParsedMessage schema, MECE minimality principle)
