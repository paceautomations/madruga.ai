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
8. `[2026-04-10 epic-context]` Campo agent opcional na regra; fallback para tenant_ctx.default_agent_id (ref: ADR-006 §routing-configuravel)
9. `[2026-04-10 epic-context]` Campo instance opcional no when; ausente = wildcard (ref: ADR-006)
10. `[2026-04-10 epic-context]` Exhaustiveness test = enumeracao enums+bools + Hypothesis + reachability-per-instance (ref: pipeline-contract-base.md auto-review)
11. `[2026-04-10 epic-context]` Rip-and-replace: remover enum MessageRoute e funcoes legadas no mesmo PR (ref: refactor discipline)
12. `[2026-04-10 epic-context]` Epic dedicado — nao absorvido em 005 Conversation Core (ref: Shape Up appetite)
13. `[2026-04-10 epic-context]` CLI router verify|explain como hook pre-commit + CI (ref: blueprint §2.2)
14. `[2026-04-10 epic-context]` Garantias MECE em 4 camadas: tipo + schema + runtime + CI (ref: blueprint §5 NFR testabilidade)
