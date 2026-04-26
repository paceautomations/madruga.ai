---
id: "013"
title: "Agent Tools v2 — Connector framework declarativo + Google Calendar lighthouse + admin UI"
slug: 013-agent-tools-v2
appetite: "3 semanas"
status: drafted
priority: P2
depends_on: ["011-evals", "012-tenant-knowledge-base-rag"]
created: 2026-04-25
updated: 2026-04-25
---

# Epic 013 — Agent Tools v2 (Connector framework + Google Calendar lighthouse + admin UI)

> **DRAFT** — planejado enquanto epic 011 (Evals) executa e epic 012 (RAG) ainda esta em fila. Promocao via `/madruga:epic-context prosauai 013` (sem `--draft`) faz delta review e cria branch.

## Problema

A [vision](../../business/vision.md) e o [solution-overview](../../business/solution-overview.md) prometem agentes que **agem**, nao apenas conversam — fazer reservas, consultar estoque, agendar visitas, sincronizar com sistemas do tenant. Hoje (pos epics 005-012) o agente sabe **conversar** e, depois do epic 012 chegar, **consultar a base de conhecimento do tenant via RAG**. O que ele ainda nao sabe e: **chamar APIs externas com credenciais do tenant**.

Gap concreto em producao:

1. **`tools/registry.py` esta vazio**. O modulo foi criado em epic 005 com decorator `@register_tool` (ADR-014), mas o `__init__.py` confirma: *"No tool implementations are currently registered; agents run prompt-only."* Epic 012 vai adicionar `search_knowledge` como **primeiro tool real** ([decision #4 do pitch 012](../012-tenant-knowledge-base-rag/pitch.md)). Epic 013 entrega o **framework declarativo + 1 connector externo real (Google Calendar)** que prova o caminho para todos os connectors futuros.

2. **Roadmap promete "conectores declarativos (estoque, agenda, CRM generico)"** ([roadmap](../../planning/roadmap.md)). Sem framework, cada nova tool exige PR + code review + deploy — viola anti-pattern #13 do ADR-006 (onboarding de novo cliente nao depende de eng).

3. **ADR-014 ja travou a arquitetura** (registry declarativo, server-side `tenant_id` injection, schema Pydantic strict, whitelist enforcement, `requires_integration` field). Mas o ADR descreve o **comportamento** — o **formato concreto** de spec de connector + onde credenciais por tenant vivem + auth modes suportados ainda nao estao definidos. Epic 013 fecha esse gap.

4. **Tenant credentials hoje nao tem home**. Helpdesk credentials (epic 010) vivem em `tenants.yaml` blocos `helpdesk.*`. Para tools externas, o pattern paralelo (`integrations.*`) ainda nao existe — sem ele, qualquer connector real fica no ar.

5. **Admin nao consegue habilitar/configurar tools por tenant**. Hoje tools enabled e campo JSONB no agent config (ADR-006), mas a propria lista de connectors disponiveis e o status de credenciais por tenant nao tem UI — admin nao sabe se um tenant pode usar `gcal.create_event` ate o agente tentar e falhar em runtime.

6. **Tool name flat sem namespace abre porta para tool squatting** (risco #3 do ADR-016). `create_event` pode colidir entre dois connectors. Sem prefixo `{integration}.{action}`, nao da pra fazer whitelist por integracao no agent config.

Epic 013 entrega:

- **Framework declarativo**: connector descrito por **YAML spec** (auth, base_url, params, response mapping). Pydantic models auto-gerados a partir da spec — schema strict mantido (ADR-016 risk #2).
- **Google Calendar como lighthouse connector** real: prova OAuth 2 client_credentials, datetime params, response shaping, breaker. **Demais connectors (estoque, CRM) ficam para 013.1+** sob demanda real de tenant — o framework esta pronto pra absorver, nao pre-builda especulativamente.
- **`tenants.yaml integrations.*` blocks**: per-tenant credentials, hot reload <60s (pattern epic 010 helpdesk).
- **Admin UI nova aba "Integracoes"**: lista connectors registrados + status de credenciais por tenant + form para wire integration → enable per agent + indicador de token expiry.
- **Convencao de naming `{integration}.{action}`**: `gcal.list_upcoming_events`, `gcal.create_event`. Whitelist por integracao no agent config (`tools_enabled: ['gcal.*']` futuro). Compatibilidade com `search_knowledge` builtin (Python tool, sem prefixo) coexiste no mesmo `TOOL_REGISTRY`.

## Appetite

**3 semanas** (1 dev full-time, sequencia de PRs mergeaveis em `develop`, reversivel via `tools.enabled: false` per-tenant em <60s).

| Semana | Entrega | Gate |
|--------|---------|------|
| Sem 1 | `ConnectorSpec` parser + Pydantic auto-gen + secrets adapter (`tenants.yaml integrations.*`) + retry/breaker per `(tenant, integration)` + Google Calendar YAML escrito (sem rodar) | Unit tests verdes; spec parseia sem rodar HTTP |
| Sem 2 | OAuth 2 client_credentials flow + Google Calendar lighthouse end-to-end + integration tests com httpx mock + Phoenix span attrs `tool.connector.*` | Ariel shadow: registry registra `gcal.list_upcoming_events` sem erro; chamada real bem-sucedida em service account de teste |
| Sem 3 | Admin UI nova aba "Integracoes" (lista connectors + form OAuth credentials + enable per agent + token expiry badge) + rollout `off → shadow → on` Ariel; ResenhAI fica para 013.1 (sem demanda de calendario imediata) | Ariel `on` em 1 agent real com Google Calendar service account; admin consegue desabilitar via UI em <60s |

**Cut-line**: se semana 2 estourar (provavel: OAuth setup com Google Workspace + service account permissions surpreende), a **admin UI vira 013.1**. Valor user-facing critico (framework + Google Calendar funcional via YAML/CLI) sobrevive sem UI. Agentes ainda chamam `gcal.*` tools normalmente; admin gerencia via PR no `tenants.yaml` no curto prazo.

**Cut-line dura**: se semana 1 estourar (improvavel — parser YAML + Pydantic gen e escopo bem delimitado), Google Calendar vira 013.1 e o framework fica somente com unit tests e mock connector. Esse cenario sinaliza problema arquitetural maior — sem connector real, framework nao se prova.

## Dependencies

Prerrequisitos (em curso ou shipped):

- **011-evals (em curso)** — necessario porque tools introduzem nova superficie de regressao (LLM hallucina sobre tool output, parametros mal preenchidos, response shaping errado). `eval_scores` com `evaluator='heuristic_v1'` ja pega regressao grosseira pos-tool. Extensao especifica para tools (e.g., `ToolFaithfulness`) **adiada para 013.1** apos 30d de baseline.
- **012-tenant-knowledge-base-rag (drafted)** — define o **primeiro pattern de tool real**: `search_knowledge` como **builtin Python tool** registrado via `@register_tool` (sem YAML — connector externo nao se aplica, e RAG interno). Epic 013 mantem esse pattern coexistindo com YAML connectors no mesmo `TOOL_REGISTRY`. Se 012 atrasar e merger depois de 013, zero impacto — registry ja suporta dois caminhos.
- **010-handoff-engine-inbox (shipped)** — `tenants.yaml` hot reload <60s + config_poller pattern + circuit breaker per `(tenant, helpdesk)` reaproveitados para `(tenant, integration)`.
- **008-admin-evolution (shipped)** — admin Next.js 15 + pool_admin BYPASSRLS + TanStack Query + shadcn/ui. Nova aba "Integracoes" reusa pattern existente (form + list + actions); `openapi-typescript` continua gerando tipos a partir de `contracts/openapi.yaml`.
- **005-conversation-core (shipped)** — pipeline 14-step com tool calling pydantic-ai ja suportado. Step `agent.generate` recebe tools resolvidas via `get_tools_for_agent(prompt.tools_enabled)`.

Pre-requisitos que **nao bloqueiam** mas sao considerados:

- **Google Workspace service account**: precisa ser provisionado pelo Pace (1x setup) com escopo `calendar.events.readonly` + `calendar.events`. Time de ops: ~30 minutos.
- **Bifrost extension** (item do epic 012 — `/v1/embeddings`): inalterado por epic 013. Tools externas chamam APIs do tenant **direto via httpx** (nao passam por Bifrost — Bifrost so roteia LLM).

ADRs novos desta epic (draft — promocao pode ajustar):

- **ADR-043** — Connector Spec YAML format (schema declarativo: `name`, `auth`, `http.method/url/params`, `response_mapping`, `hard_limits`)
- **ADR-044** — Connector Auth modes v1 (API key Header/Bearer/Query + OAuth 2 client_credentials; full user-OAuth + token refresh adiados para 013.1)

ADRs estendidos (nao substituidos):

- **ADR-014** tool-registry — registry agora suporta **dois paths**: (a) Python tools via `@register_tool` (status quo, usado por `search_knowledge` do epic 012); (b) YAML connectors auto-registrados no startup via `ConnectorSpec.load_all()`. `TOOL_REGISTRY` aceita ambos sob o mesmo dict.
- **ADR-015** noisy-neighbor — circuit breaker estendido de `(tenant)` para `(tenant, integration)`. Tenant que abusa de `gcal` nao quebra `crm.*` do mesmo tenant.
- **ADR-016** agent-runtime-safety — hard limits aplicados per-connector via `hard_limits` no YAML (timeout, rate limit per minute). Server-side `tenant_id` injection mantido como invariante (tools nunca recebem `tenant_id` como param do LLM).
- **ADR-017** secrets-management — Infisical permanece como long-term target. v1 usa `tenants.yaml integrations.*` blocks. Migration path: o **adapter `SecretsResolver` e o ponto unico de injecao**; trocar implementacao YAML→Infisical em 013.1+ nao requer mudar connector specs.
- **ADR-027** admin-tables-no-rls — sem novas tabelas admin-only neste epic. UI consome `tenants.yaml` via API + status runtime via Redis (breaker state).

Dependencias externas:

- **`httpx`** — ja dependencia.
- **`google-auth`** — biblioteca Python para service account JWT signing. Lib oficial Google, ~2 MB. Substitui implementacao manual de JWT signing para OAuth 2 client_credentials.
- **`pydantic`** — ja dependencia. `create_model()` runtime usado para Pydantic gen a partir do YAML spec.
- **Sem novas deps no admin frontend** — reusa shadcn/ui Form + Input + Switch.

## Captured Decisions

| # | Area | Decisao | Referencia |
|---|------|---------|-----------|
| 1 | Escopo v1 | **Framework declarativo + 1 lighthouse connector real (Google Calendar)**. Estoque/CRM genericos do roadmap **NAO** sao implementados nesta epic — framework esta pronto para absorver via PR de YAML novo (zero deploy de codigo). Ship-as-you-go. | Q1-A (epic-context draft 2026-04-25) |
| 2 | Formato canonico de connector | **YAML spec por connector** (`apps/api/connectors/*.yaml`). Pydantic model auto-gerado em runtime via `pydantic.create_model()` a partir de `required_params` + `optional_params`. Mantem ADR-016 schema strict sem hand-written models por connector. | Q2-A; ADR-043 novo; ADR-014 extended |
| 3 | Credenciais por tenant | **`tenants.yaml integrations.*` blocks** (espelha pattern `helpdesk.*` do epic 010). Hot reload <60s via config_poller existente. ADR-017 (Infisical) fica long-term em 013.1+ via `SecretsResolver` interface. | Q3-A; ADR-017 reaffirmed; epic 010 pattern |
| 4 | Auth modes v1 | **API key (Header/Bearer/Query)** + **OAuth 2 client_credentials** (service account JWT, cobre Google Calendar service-account workflow). User-OAuth com refresh token + storage adiados para 013.1+. | Q4-A; ADR-044 novo |
| 5 | Tool naming convention | **Prefix `{integration}.{action}`** (`gcal.list_upcoming_events`, `gcal.create_event`). Whitelist por integracao no agent config (`tools_enabled: ['gcal.*']` parser de glob). Builtin tools sem integration externa (e.g., `search_knowledge` do epic 012) ficam sem prefixo — registry aceita ambos. Mitiga risco tool squatting (ADR-016 #3). | Q5-B; ADR-016 reaffirmed |
| 6 | Admin UI scope | **Inclusa em 013** (Q6-B): nova aba "Integracoes" no admin com (a) lista de connectors registrados (read-only do registry); (b) form per-tenant para preencher credentials da `integrations.*` block; (c) Switch `enabled` per-tenant per-integration; (d) badge token-expiry (OAuth) com warning <7d para vencer. **Estende appetite para 3 semanas** (era 2). Cut-line: se semana 2 estourar, UI vira 013.1. | Q6-B |
| 7 | Connector spec storage | **Specs versionadas via git** em `apps/api/connectors/*.yaml` (monorepo da app, nao do madruga.ai). Tenant nao escreve YAML — Pace controla catalogo. Tenant **escolhe** quais habilitar via `tenants.yaml`. Custom tenant connectors em fase futura (013.x ou epic dedicado). | derivado Q1+Q2; ADR-043 |
| 8 | Failure handling | **Reusa retry budget do ADR-016** (max 3 retries com backoff exponencial 1s/4s/16s — mesmos valores do Evolution API ja em prod). **Circuit breaker per `(tenant, integration)`** abre apos 50 erros/5min, half-open apos 5min, DLQ Redis (`dlq:tools:{tenant}:{integration}`). LLM recebe `tool_unavailable` exception → orquestrador escala para handoff via epic 010. | ADR-015 extended; ADR-016 reaffirmed |
| 9 | Cost tracking | **Phoenix span attributes** (`tool.connector.cost_usd`, `tool.connector.duration_ms`, `tool.connector.tokens_estimated`) emitidos pelo wrapper. **Zero infra nova** — `usage_events` e billing (epic 019) derivam de spans. | ADR-028 fire-and-forget; ADR-020 reaffirmed |
| 10 | Eval extension | **Adiada para 013.1**. Reference-less metrics do epic 011 (AnswerRelevancy, Toxicity) cobrem regressao grosseira. `ToolFaithfulness` (LLM output reflete tool result) e dificil sem golden dataset — espera 30d de producao para calibrar. | epic 011 reaffirmed |
| 11 | Schema strict via Pydantic gen | Cada `ConnectorSpec` produz uma `pydantic.BaseModel` em runtime via `pydantic.create_model("Gcal_CreateEvent", **fields)`. Validators para datetime ISO-8601, email, telefone, etc. fornecidos via `validators:` block opcional no YAML. **Nenhum param `Any` ou `dict` aceito** (ADR-016 #2). | ADR-014 + ADR-016 reaffirmed; ADR-043 novo |
| 12 | Server-side tenant_id injection | Wrapper do connector injeta `ctx.tenant_id` antes de aplicar template do `http.url`. Tenant_id nunca aparece no Pydantic schema do tool — LLM nao pode passa-lo (anti-confused-deputy ADR-014 + ADR-016). | invariante existente |
| 13 | Tool execution wrapper | Novo modulo `prosauai/tools/connector_runtime.py`: (a) parseia YAML, (b) valida params via Pydantic gerado, (c) injeta `tenant_id` server-side, (d) resolve credentials via `SecretsResolver`, (e) renderiza URL/headers/body templated, (f) executa httpx, (g) aplica `response_mapping` (JSONPath), (h) emite span Phoenix, (i) trata erros via breaker. | novo |
| 14 | OAuth 2 client_credentials flow | `prosauai/tools/auth/oauth_client_credentials.py`: usa `google-auth` para JWT signing → exchange por access_token via `https://oauth2.googleapis.com/token` → cache em Redis com TTL = `expires_in - 60s`. Refresh proativo no proximo request apos expiry (no background daemon — KISS). | ADR-044 novo |
| 15 | Hot reload de credenciais | `tenants.yaml` mudancas em `integrations.*` block invalidam cache OAuth do tenant especifico via Redis `DEL tools:auth:{tenant}:{integration}` no config_poller. Connectors nao precisam restart. | epic 010 pattern reaffirmed |
| 16 | Connector hard limits per-spec | YAML opcional `hard_limits: {timeout_seconds, rate_limit_per_minute, max_response_bytes}`. Default conservador: 5s timeout, 60 RPM por tenant, 256KB response. Override por connector (e.g., Calendar lista pode pedir 30s). | ADR-016 reaffirmed |
| 17 | Admin UI persistence | UI **nao** persiste em DB — escreve direto em `tenants.yaml` via endpoint `POST /admin/tenants/{slug}/integrations` (rewrites bloco isolado, mantem comentarios via `ruamel.yaml`). Mudanca disparada em <60s pelo config_poller existente. Sem tabela `tenant_integrations` em PG. | Q3-A consequencia direta |
| 18 | Connector lighthouse v1 | **Google Calendar** com 3 tools: `gcal.list_upcoming_events`, `gcal.create_event`, `gcal.find_free_slots`. Service account JWT (Workspace domain-wide delegation se tenant tiver Google Workspace; standalone se nao). Caso de uso real: agente Ariel agenda visita interna, agente ResenhAI consulta calendario de jogos. | Q1-A; lighthouse de prova |
| 19 | Naming compatibility com builtin tools | `search_knowledge` (epic 012) **fica sem prefixo** — e builtin Python sem integracao externa. Registry aceita: (a) `name=create_event` (rejeitado se `connector_spec` presente — exige prefixo); (b) `name=gcal.create_event` (YAML connector); (c) `name=search_knowledge` (Python builtin sem prefixo). Validacao no startup. | Q5-B consequencia |
| 20 | Glob whitelist | Agent config `tools_enabled` aceita glob: `['gcal.*', 'crm.lookup_*', 'search_knowledge']`. Resolver expande no startup do agent + cache. | Q5-B consequencia |
| 21 | Observabilidade | Novas metricas Prometheus via structlog facade: `tool_calls_total{tenant, integration, action, status}`, `tool_call_duration_seconds{tenant, integration, action}`, `tool_breaker_open_total{tenant, integration, reason}`, `tool_auth_refresh_total{tenant, integration, status}`. Logs structlog: `tenant_id, conversation_id, tool_name, integration, duration_ms, status_code`. | ADR-028 + epic 010 pattern |
| 22 | OTel baggage | Wrapper attacha `tool.name`, `tool.integration`, `tool.connector.spec_version` ao span. `trace_id` ja propaga desde epic 002. | epic 002 reaffirmed |
| 23 | Feature flag shape | `tools.enabled: bool` per-tenant em `tenants.yaml` (kill switch global). `tools.integrations.<name>.enabled: bool` per-integration. Defaults: `false` em ambos para tenants existentes — opt-in. Reload <60s via config_poller. | Q3-A pattern |
| 24 | Rollout per-tenant | **Ariel `off → shadow (3d) → on`**. Shadow grava spans + persiste eval_scores mas **nao executa tool reais** (mock response amigavel pro LLM); valida que registry resolve, params validam, credenciais resolvem. Pos-shadow OK, flip para `on`. **ResenhAI fica para 013.1** se nao houver demanda de calendario imediata — eu **nao** lanco connector ocioso. | Q6-B + epic 010/011 pattern |
| 25 | Custom validators no YAML | `validators:` block opcional com builtin types: `iso8601_datetime`, `email`, `phone_e164`, `enum:[a,b,c]`, `regex:^pattern$`. Pydantic field validators auto-attached. Reduz LLM passar lixo. | ADR-016 #2 reaffirmed |
| 26 | Response mapping | `response_mapping:` opcional usa subset de JSONPath: `$.items[*].summary`, `$.[0].id`. Implementacao stdlib (sem `jsonpath-ng` lib pesada — escopo limitado a `$`, `.field`, `[*]`, `[N]`). | KISS |
| 27 | Idempotencia | Tools que mutam estado externo (POST/PUT/DELETE) recebem `idempotency_key` server-side gerado: `sha256(tenant_id + conversation_id + tool_name + sorted_params)`. Headers `Idempotency-Key` quando connector spec declarar `idempotent: true`. Previne double-create em retry. | novo |
| 28 | Risco tool squatting | Mitigado via prefix `{integration}.{action}` (Q5-B) + validacao no startup (registry rejeita name colidindo entre 2 connectors diferentes). | ADR-016 #3 reaffirmed |
| 29 | Drift no blueprint section 8 | Blueprint refs antigos a "Fase 3 (epic 013)" (Postgres TenantStore migration) sao da numeracao pre 2026-04-22 — hoje slot 013 e Agent Tools v2, Postgres migration foi para slot 020. Anotado para reverse-reconcile pos-promocao desta epic. | drift detectado durante draft |
| 30 | LGPD | Tool calls com PII (e.g., calendar event com nome cliente) seguem invariantes existentes — sem armazenamento adicional alem do trace ja persistido pelo epic 008. SAR (ADR-018) cobre via `trace_id` cascade ja implementado. | ADR-018 reaffirmed |

## Resolved Gray Areas

Decisoes tomadas durante este epic-context (2026-04-25, modo `--draft`):

1. **Escopo v1 (Q1)** — Framework declarativo + 1 lighthouse connector real (Google Calendar). **NAO** implementar estoque/CRM agora — framework esta pronto para absorver YAMLs novos sob demanda. Ship-as-you-go reduz risco de over-engineering em connectors sem cliente concreto.

2. **Formato canonico (Q2)** — YAML spec por connector + Pydantic auto-gen em runtime. Substitui hand-written Python por connector. Specs versionadas via git no monorepo da app.

3. **Credenciais por tenant (Q3)** — `tenants.yaml integrations.*` blocks. Espelha pattern `helpdesk.*` do epic 010 — hot reload <60s, zero infra nova. ADR-017 Infisical fica long-term sob mesmo `SecretsResolver` interface.

4. **Auth modes (Q4)** — API key (Header/Bearer/Query) + OAuth 2 client_credentials (service account JWT). Cobre ~95% das SaaS APIs e o lighthouse Google Calendar via service account. Full user-OAuth + refresh tokens adiados para 013.1.

5. **Tool naming convention (Q5)** — Prefix `{integration}.{action}`. Mitiga tool squatting (ADR-016 #3) + permite glob whitelist. Builtin Python tools (ex: `search_knowledge` do epic 012) coexistem sem prefixo.

6. **Admin UI scope (Q6)** — Inclusa em 013 ao custo de **estender appetite de 2 → 3 semanas**. Cut-line dura: UI vira 013.1 se semana 2 estourar.

7. **Failure handling (sem pergunta — segui recomendacao)** — Retry 3x backoff (ADR-016) + breaker per `(tenant, integration)` (estende ADR-015) + DLQ Redis. LLM recebe `tool_unavailable` exception → escala para handoff via epic 010.

8. **Cost tracking (sem pergunta)** — Phoenix span attributes. Zero infra nova; billing futuro (epic 019) deriva de spans.

9. **Eval extension (sem pergunta)** — Adiada para 013.1. Reference-less metrics do epic 011 cobrem regressao grosseira; `ToolFaithfulness` espera 30d de producao para calibrar.

10. **Drift no blueprint section 8 (detectado durante context)** — Refs antigos a "Fase 3 (epic 013)" sao da numeracao pre 2026-04-22. Anotado para reverse-reconcile pos-promocao.

## Applicable Constraints

**Do blueprint** ([engineering/blueprint.md](../../engineering/blueprint.md)):

- Python 3.12, FastAPI, asyncpg, redis[hiredis], structlog, opentelemetry, httpx — **so 1 lib nova** (`google-auth` para service account JWT).
- NFR Q1 (p95 <3s) — tools adicionam latencia. Budget per tool ~500ms (timeout default 5s no spec, mas hard SLA p95 <3s do pipeline). Slow tools sao escalados via breaker.
- NFR Q4 (safety bypass <1%) — schema strict + whitelist + server-side tenant_id (ADR-014 + ADR-016 invariantes).
- NFR Q11 (guardrail latency <260ms) — connectors nao impactam guardrails (sao downstream do safety).
- ADR-014 — registry agora suporta dois paths (Python + YAML). Whitelist enforcement preservado.
- ADR-015 — circuit breaker estendido per `(tenant, integration)`.
- ADR-016 — hard limits aplicados via `hard_limits` no YAML; schema strict via Pydantic gen; server-side tenant_id injection invariante.
- ADR-017 — Infisical long-term; v1 usa `tenants.yaml integrations.*` blocks via `SecretsResolver` interface.
- ADR-027 — sem novas tabelas admin-only neste epic.
- ADR-028 — fire-and-forget para emissao de span; tool execution **nao** e fire-and-forget (LLM precisa do resultado).
- ADR-029 — pricing constant inalterado; cost tracking de tool calls fica como new column em `usage_events` (epic 019, fora do escopo).

**Do epic 010** (helpdesk pattern reusado):

- Config_poller hot reload <60s.
- Circuit breaker per `(tenant, helpdesk)` → estendido para `(tenant, integration)`.
- Feature flag shape `off | shadow | on` per-tenant.

**Do epic 011** (eval pattern reusado):

- Reference-less metrics ja em producao.
- `eval_scores` table com `evaluator='heuristic_v1'` cobre tool-using responses sem extensao especifica.

**Do epic 012** (RAG dependency leve):

- `search_knowledge` builtin Python tool registrado via `@register_tool` — coexiste com YAML connectors no mesmo `TOOL_REGISTRY`.

## Suggested Approach

**3 PRs sequenciais** mergeaveis em `develop`. Cada PR atras de feature flag `tools.enabled: false` por default — risco zero em prod.

### PR-A (Sem 1) — Framework foundation

Backend foundation. Sem connector real ainda. Tudo unit-tested.

- `apps/api/prosauai/tools/connector_spec.py`: parser YAML → `ConnectorSpec` dataclass.
- `apps/api/prosauai/tools/pydantic_gen.py`: `build_param_model(spec) → BaseModel` via `pydantic.create_model()`.
- `apps/api/prosauai/tools/secrets_resolver.py`: interface + impl `YamlSecretsResolver` lendo `tenants.yaml integrations.*`.
- `apps/api/prosauai/tools/breaker.py`: `IntegrationBreaker` per `(tenant, integration)`. Reusa pattern `prosauai/handoff/breaker.py` do epic 010.
- `apps/api/prosauai/tools/registry.py`: extensao para auto-load YAMLs + glob whitelist resolver. Backward-compat com `@register_tool`.
- `apps/api/connectors/gcal.yaml`: spec escrita mas nao executa em PR-A.
- `apps/api/tests/unit/tools/`: testes para parser, pydantic gen, breaker, secrets resolver, glob resolver, naming validation.

Gate: unit tests verdes; CI lint pass; spec YAML parseia; Pydantic gerado valida cases positivos + negativos.

### PR-B (Sem 2) — Google Calendar lighthouse

End-to-end real connector. Validacao com service account de teste.

- `apps/api/prosauai/tools/auth/oauth_client_credentials.py`: JWT signing via `google-auth` + exchange + cache Redis.
- `apps/api/prosauai/tools/connector_runtime.py`: wrapper completo (parse → validate → inject tenant_id → resolve secrets → render URL/headers → httpx call → response_mapping → span emission → breaker).
- `apps/api/prosauai/tools/jsonpath_lite.py`: subset de JSONPath stdlib (`$`, `.field`, `[*]`, `[N]`).
- `apps/api/connectors/gcal.yaml`: 3 tools (`list_upcoming_events`, `create_event`, `find_free_slots`).
- `apps/api/tests/integration/tools/test_gcal_lighthouse.py`: testes contra `respx` mock + 1 smoke test em service account real (ariel-test workspace).
- Phoenix instrumentation: `tool.connector.*` span attributes.

Gate: smoke test em service account real bem-sucedido; Phoenix UI mostra spans com cost; breaker testado via fault injection.

### PR-C (Sem 3) — Admin UI + Ariel rollout

Admin UI nova aba "Integracoes" + Ariel shadow → on.

- `apps/admin/app/(dashboard)/integrations/page.tsx`: lista connectors + status credenciais.
- `apps/admin/app/(dashboard)/integrations/[name]/page.tsx`: form per-connector + per-tenant.
- `apps/api/prosauai/api/admin/integrations.py`: GET/POST/DELETE endpoints. Escreve em `tenants.yaml` via `ruamel.yaml` (preserva comentarios).
- `contracts/openapi.yaml`: novos endpoints + types regenerados via `pnpm gen:api`.
- `tenants.yaml integrations.gcal_default`: bloco real para Ariel.
- Rollout: `tools.enabled: false → true (off mode)` → 24h smoke → `tools.integrations.gcal.enabled: shadow` → 3d → `on`.

Gate: Ariel agente real chama `gcal.find_free_slots` em conversa de teste e responde com resultado correto; admin desabilita via UI em <60s e proxima call falha com `tool_disabled`.

### Cut-line execucao

| Cenario | Acao |
|---------|------|
| Sem 1 estourar (>5d) | Pause; revisar parser complexity. Se Pydantic gen bloquear, fallback para hand-written models — ADR-014 ainda funciona, perde-se declarativeness. **PR-B vira 013.1** (sinaliza problema arquitetural). |
| Sem 2 estourar (>5d) | OAuth Google complica? Skip OAuth client_credentials, deliver com **API key only** (Q4 vira recomendacao A v0). Google Calendar fica em 013.1. PR-C entra com framework + auth API-key sample (ex: weather API). |
| Sem 3 estourar (>5d) | UI vira 013.1. PR-C entrega rollout via `tenants.yaml` direto + CLI helper `python -m prosauai.tools.connectors enable --tenant ariel --integration gcal`. |
| Tudo no prazo | ResenhAI rollout vira 013.1 sob demanda real (sem necessidade de calendario imediata). |

## Riscos especificos desta epic

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| OAuth 2 client_credentials com Google Workspace surpreende em domain-wide delegation | Alto | Media | PR-B comeca com smoke test isolado em service account; se falhar, fallback API-key only documentado em cut-line |
| Pydantic `create_model()` runtime tem custo de cold-start | Baixo | Baixa | Cache global de models gerados (1x por startup); benchmark em PR-A |
| Glob whitelist abre buracos (e.g., `*.*` permite tudo) | Medio | Media | Validacao no startup: rejeita patterns ambiguos como `*.*`, `*` standalone; aceita so `prefix.*`, `prefix.action` |
| Tool name colision (registry rejeita silenciosamente como hoje) | Medio | Baixa | Startup falha hard se 2 specs declararem mesmo `name`. Logs nivel ERROR + exit code 1 |
| `ruamel.yaml` rewriting `tenants.yaml` corrompe comentarios em edge cases | Medio | Baixa | PR-C inclui smoke test que faz round-trip + diff em fixtures reais; backup `.bak` antes de cada write |
| Tool latencia >3s estoura NFR Q1 p95 | Alto | Media | `hard_limits.timeout_seconds` default 5s, mas wrapper enforca soft cap 2s — alem disso, breaker abre. NFR Q1 amortizado pelo fato de tools serem chamados em ~10% das mensagens (estimativa) |
| Idempotency key colide em retry rapido | Baixo | Baixa | Hash inclui timestamp slot 1s; collision improvavel em janela de retry |
| Token OAuth expiry race (token expira durante chamada) | Medio | Baixa | Cache TTL = `expires_in - 60s` (margem 1 min) + retry 1x com refresh forcado em 401 |
| Service account permissions divergem entre Workspace tenants | Medio | Alta (em prod com clientes externos) | Smoke test no admin UI valida permissions ao adicionar credentials; falha cedo com mensagem clara |

## Anti-objetivos (out of scope)

- **Estoque/CRM connectors reais** — framework esta pronto, mas builds especulativos sem cliente concreto sao banidos. 013.1+ sob demanda.
- **Custom tenant connectors** (tenant escreve YAML proprio) — riscos de seguranca + UX complexa. Pace controla catalogo em v1.
- **Full user-OAuth com refresh tokens** — exige token storage + background refresh worker. 013.1 dedicado.
- **Bifrost integration para tools** — tools chamam APIs do tenant direto (Bifrost so roteia LLM). Sem mudanca em ADR-002.
- **Tool marketplace publico** — explicitamente rejeitado em ADR-014 alternativas; nao aparece nesta epic.
- **`ToolFaithfulness` eval metric** — adiada para 013.1 apos 30d de baseline com epic 011 reference-less metrics.
- **Streaming/long-running tool calls** — v1 sincrono <30s. Async/webhook callback fica fora.
- **Tool-orchestrated workflows** (tool A → output → tool B) — pydantic-ai ja suporta tool chaining no LLM-loop nativamente; sem orchestration explicita do nosso lado.

---

> **Proximo passo (apos promocao via `/madruga:epic-context prosauai 013` sem `--draft`)**: `/speckit.specify prosauai 013-agent-tools-v2` para spec formal a partir desta pitch + delta review se mudou algo entre 2026-04-25 e a promocao.
