---
epic: 013-agent-tools-v2
created: 2026-04-25
updated: 2026-04-25
---

# Registro de Decisoes — Epic 013 (Agent Tools v2)

1. `[2026-04-25 epic-context]` Escopo v1: framework declarativo + 1 lighthouse connector real (Google Calendar). Estoque/CRM nao implementados nesta epic — framework pronto para absorver YAMLs novos sob demanda. (ref: Q1-A epic-context draft)
2. `[2026-04-25 epic-context]` Formato canonico de connector: YAML spec por connector + Pydantic auto-gen via `pydantic.create_model()`. (ref: ADR-043 novo, ADR-014 extended)
3. `[2026-04-25 epic-context]` Credenciais por tenant: `tenants.yaml integrations.*` blocks (espelha pattern `helpdesk.*` epic 010). Hot reload <60s via config_poller. (ref: ADR-017 reaffirmed, epic 010 pattern)
4. `[2026-04-25 epic-context]` Auth modes v1: API key (Header/Bearer/Query) + OAuth 2 client_credentials (service account JWT). User-OAuth + refresh tokens adiados para 013.1. (ref: ADR-044 novo)
5. `[2026-04-25 epic-context]` Tool naming convention: prefix `{integration}.{action}` (`gcal.create_event`). Builtin Python tools sem prefixo coexistem (e.g., `search_knowledge` epic 012). Mitiga tool squatting. (ref: ADR-016 #3 reaffirmed)
6. `[2026-04-25 epic-context]` Admin UI scope: incluida em 013 ao custo de estender appetite 2 → 3 semanas. Cut-line: UI vira 013.1 se semana 2 estourar. (ref: Q6-B)
7. `[2026-04-25 epic-context]` Connector spec storage: specs versionadas via git em `apps/api/connectors/*.yaml` (monorepo da app). Pace controla catalogo; tenant escolhe quais habilitar. (ref: ADR-043)
8. `[2026-04-25 epic-context]` Failure handling: retry 3x backoff (ADR-016) + circuit breaker per `(tenant, integration)` (estende ADR-015) + DLQ Redis. LLM recebe `tool_unavailable` → escala para handoff via epic 010. (ref: ADR-015 extended, ADR-016 reaffirmed)
9. `[2026-04-25 epic-context]` Cost tracking: Phoenix span attributes (`tool.connector.cost_usd`, `duration_ms`, `tokens_estimated`). Zero infra nova; billing futuro deriva de spans. (ref: ADR-028, ADR-020)
10. `[2026-04-25 epic-context]` Eval extension adiada para 013.1. Reference-less metrics do epic 011 cobrem regressao grosseira; `ToolFaithfulness` espera 30d baseline. (ref: epic 011 reaffirmed)
11. `[2026-04-25 epic-context]` Schema strict via Pydantic gen: cada `ConnectorSpec` produz `pydantic.BaseModel` runtime. Nenhum param `Any`/`dict` aceito. Validators builtin (iso8601_datetime, email, phone_e164, enum, regex). (ref: ADR-014 + ADR-016 reaffirmed, ADR-043 novo)
12. `[2026-04-25 epic-context]` Server-side `tenant_id` injection: wrapper injeta `ctx.tenant_id` antes do template; nunca aparece no Pydantic schema do tool. (ref: ADR-014 + ADR-016 invariante)
13. `[2026-04-25 epic-context]` Tool execution wrapper: novo `prosauai/tools/connector_runtime.py` (parse → validate → inject tenant_id → resolve secrets → render → httpx → response_mapping → span → breaker). (ref: novo modulo)
14. `[2026-04-25 epic-context]` OAuth 2 client_credentials flow: `prosauai/tools/auth/oauth_client_credentials.py` via `google-auth` + cache Redis com TTL `expires_in - 60s`. (ref: ADR-044 novo)
15. `[2026-04-25 epic-context]` Hot reload de credenciais: `tenants.yaml` mudancas em `integrations.*` invalidam cache OAuth via Redis `DEL tools:auth:{tenant}:{integration}` no config_poller. (ref: epic 010 pattern reaffirmed)
16. `[2026-04-25 epic-context]` Connector hard limits per-spec: YAML opcional `hard_limits` (timeout, RPM, max response bytes). Default 5s/60RPM/256KB. (ref: ADR-016 reaffirmed)
17. `[2026-04-25 epic-context]` Admin UI persistence sem DB: escreve direto em `tenants.yaml` via `ruamel.yaml` (preserva comentarios). Sem tabela `tenant_integrations`. (ref: Q3-A consequencia)
18. `[2026-04-25 epic-context]` Connector lighthouse: Google Calendar com 3 tools (`gcal.list_upcoming_events`, `gcal.create_event`, `gcal.find_free_slots`). Service account JWT. Caso de uso real Ariel/ResenhAI. (ref: Q1-A lighthouse de prova)
19. `[2026-04-25 epic-context]` Naming compatibility: `search_knowledge` (epic 012 builtin) sem prefixo; YAML connectors exigem prefixo `{integration}.{action}`. Validacao no startup. (ref: Q5-B consequencia)
20. `[2026-04-25 epic-context]` Glob whitelist: `tools_enabled` aceita `['gcal.*', 'crm.lookup_*', 'search_knowledge']`. Resolver expande no startup do agent + cache. (ref: Q5-B consequencia)
21. `[2026-04-25 epic-context]` Observabilidade: novas metricas Prometheus via structlog facade (`tool_calls_total`, `tool_call_duration_seconds`, `tool_breaker_open_total`, `tool_auth_refresh_total`). Logs canonicos. (ref: ADR-028 + epic 010 pattern)
22. `[2026-04-25 epic-context]` OTel baggage: wrapper attacha `tool.name`, `tool.integration`, `tool.connector.spec_version` ao span. (ref: epic 002 reaffirmed)
23. `[2026-04-25 epic-context]` Feature flag shape: `tools.enabled: bool` per-tenant (kill switch global) + `tools.integrations.<name>.enabled: bool` per-integration. Default `false` (opt-in). Reload <60s. (ref: Q3-A pattern)
24. `[2026-04-25 epic-context]` Rollout: Ariel `off → shadow (3d) → on`. Shadow grava spans + eval_scores mas mock response (nao executa tool real). ResenhAI fica para 013.1 sob demanda. (ref: Q6-B + epic 010/011 pattern)
25. `[2026-04-25 epic-context]` Custom validators no YAML: builtin types (iso8601_datetime, email, phone_e164, enum, regex). Pydantic field validators auto-attached. (ref: ADR-016 #2 reaffirmed)
26. `[2026-04-25 epic-context]` Response mapping: subset de JSONPath stdlib (`$`, `.field`, `[*]`, `[N]`). Sem `jsonpath-ng` lib pesada. (ref: KISS)
27. `[2026-04-25 epic-context]` Idempotencia: tools que mutam estado externo recebem `idempotency_key = sha256(tenant_id + conversation_id + tool_name + sorted_params)`. Header `Idempotency-Key` quando spec declarar `idempotent: true`. (ref: novo)
28. `[2026-04-25 epic-context]` Risco tool squatting mitigado via prefix + validacao no startup (registry rejeita name colidindo). (ref: ADR-016 #3 reaffirmed)
29. `[2026-04-25 epic-context]` Drift no blueprint section 8: refs antigos a "Fase 3 (epic 013)" sao da numeracao pre 2026-04-22 (Postgres TenantStore migration esta hoje em slot 020). Anotado para reverse-reconcile pos-promocao. (ref: drift detectado)
30. `[2026-04-25 epic-context]` LGPD: tool calls com PII seguem invariantes existentes — sem armazenamento adicional alem do trace ja persistido pelo epic 008. SAR cascade via `trace_id`. (ref: ADR-018 reaffirmed)
