# Tasks: Trigger Engine — engine declarativo de mensagens proativas

**Input**: Design documents from `platforms/prosauai/epics/016-trigger-engine/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md
**Repo de implementacao**: `paceautomations/prosauai` (external) — branch `epic/prosauai/016-trigger-engine`
**Sequenciamento**: 2 PRs sequenciais (PR-A foundation + dry_run, PR-B send_template + admin viewer + Ariel rollout). Cada PR mergeavel em `develop` atras de feature flag `triggers.enabled: false` per-tenant (default).
**Tests**: TDD aplicado conforme Constitution Check IX no plan. Unit tests escritos ANTES da integracao com scheduler/engine.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1..US5). Setup/Foundational/Polish/Deployment sem label.

## Path Conventions

- Backend FastAPI: `apps/api/prosauai/triggers/`, `apps/api/prosauai/admin/`, `apps/api/prosauai/channels/outbound/`, `apps/api/prosauai/observability/`, `apps/api/prosauai/config/`, `apps/api/prosauai/customers/`
- Tests: `apps/api/tests/triggers/`
- Migrations: `apps/api/db/migrations/`
- Frontend admin: `apps/admin/app/(dashboard)/triggers/`, `apps/admin/lib/api/`, `apps/admin/components/`, `apps/admin/tests/`
- Contracts: `contracts/openapi.yaml`
- Config: `tenants.yaml` (root), `config/rules/triggers.yml`
- Docs: `apps/api/prosauai/triggers/RUNBOOK.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar branch, validar prerequisitos, scaffolding minimo do modulo `triggers/`.

- [x] T001 Verificar branch `epic/prosauai/016-trigger-engine` existe e esta checked out no clone `paceautomations/prosauai` — pre-condicao quickstart §1
- [x] T002 [P] Criar diretorio `apps/api/prosauai/triggers/` com `__init__.py` vazio + placeholder `RUNBOOK.md` (preenchido em T128)
- [x] T003 [P] Criar diretorio `apps/api/tests/triggers/` com `__init__.py` vazio
- [x] T004 [P] Adicionar fixtures iniciais em `apps/api/tests/conftest.py`: stubs para `triggers_yaml`, `mock_evolution` (respx), `fakeredis_client` — completados em T011/T012/T087
- [x] T005 Verificar que zero novas dependencias Python sao necessarias — confirmar `pyproject.toml` ja tem `redis[hiredis]>=7.0`, `httpx>=0.27`, `jinja2`, `prometheus_client`, `opentelemetry-sdk>=1.39`, `respx` (dev), `fakeredis` (dev)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema PG (migrations), Pydantic models de config, cross-ref validation no startup, scheduler skeleton + advisory lock pattern. Bloqueia todas as user stories.

**WARNING**: Nenhuma user story pode comecar antes do checkpoint da Phase 2.

### Migrations (FR-016, FR-017, FR-018, FR-020, FR-021)

- [x] T006 Criar migration `apps/api/db/migrations/20260601000020_create_trigger_events.sql` — tabela `public.trigger_events` (sem RLS, ADR-027 carve-out) + 2 indexes basicos `idx_trigger_events_tenant_fired` + `idx_trigger_events_customer_fired` + UNIQUE INDEX parcial `trigger_events_idempotency_idx WHERE status IN ('sent','queued')` + index parcial `idx_trigger_events_stuck` para FR-041 — DDL completo em data-model.md §1.1
- [x] T007 [P] Criar migration `apps/api/db/migrations/20260601000021_alter_customers_add_scheduled_event_at.sql` — `ALTER TABLE customers ADD COLUMN IF NOT EXISTS scheduled_event_at TIMESTAMPTZ` + partial index `idx_customers_scheduled_event WHERE scheduled_event_at IS NOT NULL` + COMMENT — data-model.md §1.2
- [x] T008 [P] Criar migration `apps/api/db/migrations/20260601000022_alter_customers_add_opt_out_at.sql` — `ALTER TABLE customers ADD COLUMN IF NOT EXISTS opt_out_at TIMESTAMPTZ` (sem index — uso e WHERE filter na matcher query) + COMMENT
- [x] T009 Criar migration `apps/api/db/migrations/20260601000023_extend_retention_cron_trigger_events.sql` — registrar `trigger_events` no cron retention 90d do epic 006 (`DELETE WHERE fired_at < NOW() - INTERVAL '90 days'`)
- [x] T010 Validar migrations forward+rollback em test container: `make migrate && make migrate-rollback && make migrate` — todas idempotentes, zero erros

### Pydantic models de config (FR-002, FR-003, FR-004, FR-042)

- [x] T011 [P] Escrever `apps/api/tests/triggers/test_models_unit.py` PRIMEIRO — Pydantic validation positiva (config valida) + negativa (cooldown_hours<1 rejeitado, lookahead_hours>168 rejeitado, type='custom' rejeitado, template_ref orfao rejeitado, mode invalido rejeitado, daily_cap_per_customer fora de range rejeitado) — testes devem FALHAR antes de T012
- [x] T012 Implementar `apps/api/prosauai/triggers/models.py` — Pydantic v2 models conforme plan.md §A.2: `TriggerType` enum (3 valores), `TriggerMode` enum (live/dry_run), `TriggerMatch`, `TriggerConfig` (com Field constraints), `TemplateComponent`, `TemplateConfig`, `TenantTriggersConfig`, `CustomerMatch`, `TriggerEventRecord`, `TickResult`. Tests T011 devem passar.
- [x] T013 Modificar `apps/api/prosauai/config/tenants_loader.py` — adicionar campos `triggers: TenantTriggersConfig = TenantTriggersConfig()` + `templates: dict[str, TemplateConfig] = {}` ao `TenantSettings` model. Backward-compat: tenants sem `triggers.list` carregam com `triggers.enabled=False` default — zero regressao.
- [x] T014 Implementar `_validate_template_refs()` em `apps/api/prosauai/config/tenants_loader.py` — cross-ref check: para cada `tenant.triggers.list[].template_ref`, verifica que `tenant.templates.<key>` existe. Falha rapido (raise ValueError) no startup se broken ref (FR-042). Em hot reload: mantem snapshot anterior + log error + emit Prometheus counter `tenants_yaml_reload_failed_total{reason='missing_template_ref'}`.
- [x] T015 [P] Adicionar test `apps/api/tests/triggers/test_template_refs_validation.py` — fixture com config quebrada (trigger referenciando template inexistente); assert startup falha + assert hot reload mantem snapshot anterior

### Repository trigger_events (FR-016, FR-017, FR-041)

- [x] T016 Escrever `apps/api/tests/triggers/test_events_repo_pg.py` PRIMEIRO (testcontainers + asyncpg) — testes para `insert_trigger_event` (success path), `insert_trigger_event_unique_violation_handled` (concurrent INSERT mesmo (tenant, customer, trigger_id, date) → segundo vira `status='skipped' reason='idempotent_db_race'`), `update_status` (queued→sent transition), `find_stuck_queued` (rows >5min retornam, <5min nao), `reclaim_stuck` (UPDATE retry_count++ + fired_at=NOW; idempotente apos 3 retries), `exists_today` (app-check helper) — devem FALHAR antes de T017
- [x] T017 Implementar `apps/api/prosauai/triggers/events.py` — funcoes async com pool admin BYPASSRLS: `insert_trigger_event(conn, ...)` com try/except `UniqueViolationError` para FR-017 layer 2; `update_status(conn, event_id, status, sent_at, error)`; `find_stuck_queued(conn, max_age_minutes=5, max_retries=3)` usando `FOR UPDATE SKIP LOCKED`; `reclaim_stuck(conn, event_id)` com UPDATE atomic; `exists_today(conn, tenant_id, customer_id, trigger_id)` para app-check pre-INSERT (FR-017 layer 1). Tests T016 passam.

### Scheduler skeleton + advisory lock (FR-001)

- [x] T018 Escrever `apps/api/tests/triggers/test_scheduler_unit.py` PRIMEIRO — testar: (a) `pg_try_advisory_lock(hashtext('triggers_engine_cron'))` adquirido no inicio do tick + liberado no fim; (b) standby behavior (lock held por outra connection retorna false → tick skipa); (c) cadence sleep correto; (d) graceful shutdown (shutdown_event encerra loop) — devem FALHAR antes de T019
- [x] T019 Implementar `apps/api/prosauai/triggers/scheduler.py` — `async def trigger_engine_loop(app: FastAPI)`: lifespan periodic task com cadence `settings.triggers_cadence_seconds` (default 15); `pg_try_advisory_lock` singleton; tenant-isolated try/except (proximo tenant continua se um falhar); helper `_advisory_lock_key()` retornando hashtext int4 de `'triggers_engine_cron'`. Stub `engine.execute_tick()` ainda nao chamado (sera wired em T035). Tests T018 passam.
- [x] T020 Modificar `apps/api/prosauai/main.py` — registrar `trigger_engine_loop` no lifespan startup gated por `settings.triggers_enabled` global (default False — feature flag de seguranca). Zero impacto em tenants sem `triggers.list`.

### Observability foundation (FR-029, FR-031, FR-032, FR-033)

- [x] T021 [P] Modificar `apps/api/prosauai/observability/metrics.py` — registrar 5 Counters + 1 Gauge + 1 error counter conforme plan.md §B.3: `trigger_executions_total`, `trigger_template_sent_total`, `trigger_skipped_total`, `trigger_cooldown_blocked_total`, `trigger_template_rejected_total`, `trigger_cost_today_usd` (Gauge), `trigger_cost_gauge_errors_total`. Labels exatos por FR-029.
- [x] T022 [P] Implementar `apps/api/prosauai/observability/cardinality_lint.py` (ou estender existente) — startup check soma combinations por counter; abort com erro claro se >50K series projetadas (FR-033). Lint config: `tenant<=100`, `trigger_id<=20/tenant`, `template_name<=50/tenant`, `reason<=10`, `status<=6`.
- [x] T023 [P] Modificar `apps/api/prosauai/observability/otel.py` — registrar nomes de span: `trigger.cron.tick` (root), `trigger.match`, `trigger.cooldown_check`, `trigger.send`. Atributos OTel conforme FR-031.
- [x] T024 [P] Adicionar test `apps/api/tests/triggers/test_metrics_lint.py` — fixture com 200 tenants × 30 triggers × 100 templates (>50K series projetadas) → assert lint aborta startup com mensagem clara.

### Config exposure

- [x] T025 Adicionar settings em `apps/api/prosauai/config/settings.py`: `triggers_enabled: bool = False` (kill-switch global), `triggers_cadence_seconds: int = 15`, `triggers_cost_gauge_cadence_seconds: int = 60`, `triggers_max_customers_per_tick: int = 100` (constante FR-011), `triggers_default_cooldown_hours: int = 24`, `triggers_default_daily_cap: int = 3`, `triggers_stuck_threshold_minutes: int = 5`, `triggers_max_retries: int = 3`.

**Checkpoint Phase 2**: schema migrations aplicadas + Pydantic models exhaustivos + cross-ref validation funcional + repository idempotente + scheduler skeleton com advisory lock + Prometheus/OTel registrados + cardinality lint ativo. **Phase 3+ pode comecar.**

---

## Phase 3: User Story 1 — Lembrete de jogo agendado (Priority: P1) 🎯 MVP

**Goal**: ResenhAI/Ariel envia template `ariel_match_reminder` automaticamente 1h antes de cada partida agendada via `customers.scheduled_event_at`. Em PR-A: matcher + persist em modo `dry_run` (sem real send). Em PR-B: send real via `EvolutionProvider.send_template`.

**Independent Test**: configurar `tenants.yaml` Ariel com 1 trigger `time_before_scheduled_event` + 1 template + 3 customers de teste; cron tick gera 1 row `dry_run` (cliente em janela 1h), 2 skipped (fora de janela). Re-tick nao duplica.

### Tests for User Story 1 (TDD — escrever ANTES da implementacao)

- [x] T026 [P] [US1] Escrever `apps/api/tests/triggers/test_matcher_time_before_scheduled_event.py` — fixtures de 5 customers (1 dentro `lookahead_hours: 1`, 1 com `opt_out_at` setado, 1 com NULL `scheduled_event_at`, 1 fora janela, 1 antes de NOW); assert matcher retorna apenas 1 customer; assert ORDER BY `created_at ASC` + LIMIT 100 (hard cap); assert RLS aplica (customer de outro tenant nao retorna)
- [x] T027 [P] [US1] Escrever `apps/api/tests/triggers/test_cooldown_unit.py` — fakeredis: `check_cooldown` retorna False quando key absent, True quando key present; `set_cooldown` cria key com TTL exato `hours*3600`; `check_daily_cap` retorna True apos `cap` increments; `increment_daily_cap` usa pipeline incr+expire 26h; `restore_state_from_sql` reconstroi keys a partir de rows trigger_events
- [x] T028 [P] [US1] Escrever `apps/api/tests/triggers/test_template_renderer_unit.py` — sandbox safety (no `__import__`, `eval`, `exec`); filters `format_time`, `format_date`, `truncate`, `default`; missing var → `default` aplicado; hypothesis fuzz para safety constructs

### Implementation for User Story 1

- [x] T029 [P] [US1] Implementar `apps/api/prosauai/triggers/matchers.py` — funcao `match_time_before_scheduled_event(conn, trigger, now)` async: query SQL via pool_tenant (RLS aplica) com `WHERE scheduled_event_at >= $1 AND scheduled_event_at < $2 AND opt_out_at IS NULL` + filters `intent_filter`/`agent_id_filter` (skip se 'any')/`min_message_count`/`consent_required` + `ORDER BY created_at ASC LIMIT 100`. JOIN `conversations` filtrando `ai_active=true` para FR-010. Retorna `list[CustomerMatch]`. Tests T026 passam.
- [x] T030 [P] [US1] Implementar `apps/api/prosauai/triggers/cooldown.py` — funcoes async: `check_cooldown(redis, tenant_id, customer_id, trigger_id)`, `set_cooldown(redis, ..., hours)`, `check_daily_cap(redis, tenant_id, customer_id, cap)`, `increment_daily_cap(redis, tenant_id, customer_id)` (pipeline incr+expire 26h), `restore_state_from_sql(redis, db_admin_pool, tenant_id, since_hours=24)` para FR-015 — le `trigger_events.status='sent'` ultimas 24h e re-popula Redis com TTL apropriado. Tests T027 passam.
- [x] T031 [P] [US1] Implementar `apps/api/prosauai/triggers/template_renderer.py` — wrapper sobre `prosauai/conversation/jinja_sandbox.py` (epic 015): funcao `render_template_components(template, customer, now)` retorna `list[dict]` com parameters renderizados; registrar filters builtin `format_time`, `format_date`, `truncate`, `default`. Tests T028 passam.
- [x] T032 [US1] Adicionar suporte `scheduled_event_at` + `opt_out_at` em `apps/api/prosauai/customers/repository.py` — modificar `update_customer` para aceitar campos novos.
- [x] T033 [US1] Modificar `apps/api/prosauai/admin/customers.py` — endpoint `PATCH /admin/customers/{id}` aceita `scheduled_event_at` (TIMESTAMPTZ) + `opt_out_at` (TIMESTAMPTZ) no body. Schema Pydantic atualizado.
- [x] T034 [US1] Atualizar `contracts/openapi.yaml` — request body de `PATCH /admin/customers/{id}` ganha 2 campos opcionais; types regenerados via `pnpm gen:api` (apos PR-B integration; em PR-A, manual).
- [x] T035 [US1] Implementar `apps/api/prosauai/triggers/engine.py` — funcao `execute_tick(*, tenant_id, tenant_config, redis, db_admin_pool, db_tenant_pool, evolution_client, now, mode_override='dry_run')` async conforme plan.md §A.7: snapshot atomico de config (FR-043); stuck-detection primeiro (FR-041) chamando `events.find_stuck_queued` + `events.reclaim_stuck`; loop por trigger ativo; matcher dispatch por `trigger.type`; aplicar filtros em ordem (handoff via filtro matcher → cooldown → daily cap → app-check idempotency); render; persist via `events.insert_trigger_event` com `status='dry_run'` (PR-A scope) ou `status='queued'` (PR-B); spans OTel children. Em PR-A: `mode_override='dry_run'` sempre — send NUNCA chamado.
- [x] T036 [US1] Wirering scheduler→engine: `apps/api/prosauai/triggers/scheduler.py` chama `engine.execute_tick` para cada tenant em `get_tenants_with_triggers()`. Span root `trigger.cron.tick` aberto envolvendo tudo.
- [x] T037 [US1] Adicionar logs structlog em `engine.py` com contexto `tenant_id, customer_id, trigger_id, template_name, status, error, cost_usd_estimated` (FR-032) — usar facade `logger.bind(...)`.
- [x] T038 [US1] Adicionar emit Prometheus em `engine.py` para US1 paths: `trigger_executions_total{...,status='dry_run'}.inc()`, `trigger_skipped_total{...,reason='cooldown'/'daily_cap'/'opt_out'/'handoff'/'idempotent'/'hard_cap'/'disabled'}.inc()`. Counters apenas — gauge cost vem em PR-B.
- [x] T039 [US1] Escrever `apps/api/tests/triggers/test_engine_unit.py` — mocks de matcher/redis/db; assert filtros aplicados em ordem correta; assert dry_run mode nao chama send_template; assert idempotency app-check skipa pre-INSERT
- [x] T040 [US1] Escrever `apps/api/tests/triggers/test_engine_pg.py` (integration testcontainers + fakeredis + mock evolution via respx) — fixture Ariel com `tenants.yaml triggers.list[ariel_match_reminder]` + 5 customers (3 cenarios distintos US1 acceptance scenarios 1, 4, 5); execute_tick gera rows esperadas; re-tick respeita idempotency
- [x] T041 [US1] Escrever `apps/api/tests/triggers/test_idempotency_db_race.py` — concurrent tasks INSERT mesma `(tenant, customer, trigger_id, date)`; um vence, outro captura `UniqueViolationError` → grava `status='skipped' reason='idempotent_db_race'`
- [x] T042 [US1] Escrever `apps/api/tests/triggers/test_chaos_redis_restart.py` — pre-condicao: 5 rows `trigger_events.status='sent'` ha 12h + Redis vazio; chamar `cooldown.restore_state_from_sql`; assert keys recriadas com TTL correto
- [x] T043 [US1] Smoke E2E manual seguindo `quickstart.md` §2: editar `tenants.yaml` Ariel + 1 trigger + 1 template em `mode: dry_run`; popular `customers.scheduled_event_at` em 3 fixtures; observar log `trigger.cron.tick` + verificar 1 row `trigger_events.status='dry_run'` via SQL direto
- [x] T044 [US1] Verificar EXPLAIN das queries matcher usa indexes (`idx_customers_scheduled_event` partial); documentar em `apps/api/prosauai/triggers/RUNBOOK.md` queries esperadas + plans
- [x] T045 [US1] Add validation que `cron tick p95 <2s` em load test 100 customers em fixture (SC-004 hard gate) — adicionar bench em `apps/api/tests/triggers/test_engine_perf.py`

**Checkpoint US1**: Ariel `tenants.yaml` com 1 trigger `mode: dry_run` ativo gera rows `trigger_events.status='dry_run'` automaticamente a cada tick; cooldown bloqueia 2a tentativa <24h; daily cap bloqueia 4o trigger por customer; opt_out bloqueia absoluto. **PR-A pode shipar parcialmente apos US1 + US2 + US3 + US5 (todos backbone foundation).**

---

## Phase 4: User Story 2 — Re-engajamento apos conversa fechada (Priority: P1)

**Goal**: matcher `time_after_conversation_closed` reusando coluna existente `conversations.closed_at`. Cobre segmento vision §1.3 (servicos: lembrete consulta).

**Independent Test**: configurar trigger `consult_reminder` (`type: time_after_conversation_closed, lookahead_hours: 24, cooldown_hours: 168`); 3 conversas fechadas em -23h, -25h, -10h; cron tick dispara apenas conversa fechada ha 23-25h dentro da janela.

### Tests for User Story 2

- [x] T046 [P] [US2] Escrever `apps/api/tests/triggers/test_matcher_time_after_conversation_closed.py` — fixtures de 5 conversations (1 fechada ha 23h em janela 24h, 1 fechada ha 25h fora, 1 fechada ha 10h cedo, 1 reaberta apos closed_at, 1 com cliente opt_out); assert matcher retorna apenas 1; assert idempotency reusa logica do US1; assert hard cap 100 aplicado

### Implementation for User Story 2

- [x] T047 [US2] Adicionar funcao `match_time_after_conversation_closed(conn, trigger, now)` em `apps/api/prosauai/triggers/matchers.py` — query SQL JOIN `conversations` + `customers`: `WHERE c.closed_at >= NOW() - lookahead_hours - tick_jitter_seconds AND c.closed_at < NOW() - lookahead_hours AND customers.opt_out_at IS NULL AND c.ai_active=false` (conversa fechada implica ai_active=false). Tests T046 passam.
- [x] T048 [US2] Estender `dispatch_matcher` em `engine.py` para rotear `TriggerType.time_after_conversation_closed` → `match_time_after_conversation_closed`
- [x] T049 [US2] Adicionar fixture `tenants.yaml` em `apps/api/tests/conftest.py` para US2 (clinic-style trigger `consult_reminder`)
- [x] T050 [US2] Estender `test_engine_pg.py` com cenario US2 acceptance scenarios 1-5 (incluindo cooldown 168h bloqueia conversa reaberta; janela `[NOW-lookahead-jitter, NOW-lookahead]` estrita; hard cap 100 emite counter `trigger_skipped_total{reason='hard_cap'}`)
- [x] T051 [US2] Verificar que existe (ou criar) index suficiente em `conversations.closed_at` — adicionar `CREATE INDEX IF NOT EXISTS idx_conversations_closed_at ON public.conversations (tenant_id, closed_at) WHERE closed_at IS NOT NULL` em migration nova `20260601000024_index_conversations_closed_at.sql` se ausente; documentar EXPLAIN em RUNBOOK
- [x] T052 [US2] Smoke manual seguindo `quickstart.md` §3 — Ariel adiciona 2o trigger `consult_reminder` em `tenants.yaml`; verifica row `dry_run` correta

**Checkpoint US2**: matcher `time_after_conversation_closed` funcional em dry_run. US1 + US2 ambos funcionais independentemente.

---

## Phase 5: User Story 3 — Re-engajamento de cliente silencioso / abandoned cart (Priority: P2)

**Goal**: matcher `time_after_last_inbound` para cliente que mandou ultima mensagem ha N horas em conversa aberta `ai_active=true` sem closed_at. Cobre segmento vision §1.2 (e-commerce).

**Independent Test**: configurar trigger `cart_recovery` (`type: time_after_last_inbound, lookahead_hours: 48`); 4 customers com permutacoes de timing/ai_active/closed_at — assert apenas 1 cliente recebe trigger.

### Tests for User Story 3

- [x] T053 [P] [US3] Escrever `apps/api/tests/triggers/test_matcher_time_after_last_inbound.py` — fixtures 5 customers conforme acceptance scenarios US3: A com ultima inbound 48h em conv aberta (deve match), B com closed_at NOT NULL (skip), C com ai_active=false handoff (skip), D com ultima inbound 70h fora janela (skip), E com opt_out (skip)

### Implementation for User Story 3

- [x] T054 [US3] Adicionar funcao `match_time_after_last_inbound(conn, trigger, now)` em `apps/api/prosauai/triggers/matchers.py` — subquery latest inbound message por customer + JOIN conversations: `WHERE last_inbound.created_at < NOW() - lookahead_hours AND last_inbound.created_at >= NOW() - lookahead_hours - tick_jitter_seconds AND conversations.closed_at IS NULL AND conversations.ai_active=true AND customers.opt_out_at IS NULL`. Tests T053 passam.
- [x] T055 [US3] Estender `dispatch_matcher` em `engine.py` para rotear `TriggerType.time_after_last_inbound` → `match_time_after_last_inbound`
- [x] T056 [US3] Adicionar contador `trigger_skipped_handoff_total{trigger_id}` em `observability/metrics.py` para visibilizar US3 acceptance scenario 3 (cliente em handoff humano e excluido)
- [x] T057 [US3] Estender `test_engine_pg.py` com cenario US3 acceptance scenarios 1-4 (incluindo template rejection 4xx setando `status='rejected'` + counter `trigger_template_rejected_total`)
- [x] T058 [US3] Validar que indexes em `messages.created_at` + `conversations.ai_active` + `conversations.closed_at` permitem matcher rodar sem table scan; documentar EXPLAIN em RUNBOOK
- [x] T059 [US3] Smoke manual seguindo `quickstart.md` §4 — adicionar 3o trigger `cart_recovery` em fixture; observar `dry_run` row apenas para customer que satisfaz todas condicoes

**Checkpoint US3**: 3 matchers pre-built funcionais + dry_run completo. PR-A backbone end-to-end.

---

## Phase 6: User Story 4 — Operador audita execucoes via admin history viewer (Priority: P2)

**Goal**: backend `GET /admin/triggers/events` paginado + frontend Next.js 15 viewer (lista filtravel + drill-down modal). Reusa pattern admin-trace-explorer (epic 008).

**Independent Test**: 50+ rows em `trigger_events`; UI Admin/Triggers carrega em <500ms; filtros aplicam debounce; modal renderiza payload JSON; p95 endpoint <300ms (SC-006).

**Note**: backend (T060-T070) shipa em PR-B mesmo se UI atrasar (cut-line: UI vira 016.1).

### Backend endpoint (FR-035, FR-036)

- [x] T060 [P] [US4] Escrever `apps/api/tests/triggers/test_admin_triggers_events.py` PRIMEIRO — fixtures com 1000 rows `trigger_events` em 3 tenants; assert: paginacao cursor walks 3 paginas consistente; filtros tenant/trigger_id/customer_phone/status/from/to combinaveis; p95 <300ms via load 10K rows; auth `require_admin` (Bearer token) rejeita sem header; phone_number_e164 join populado
- [x] T061 [US4] Implementar `apps/api/prosauai/admin/schemas/triggers.py` — Pydantic models `TriggerEventResponse` (lista resumida com error_short=first 200 chars) + `TriggerEventDetail` (allOf TriggerEventResponse + full payload + full error) + `TriggerEventsPage` (items + next_cursor) + helpers encode_cursor/decode_cursor (base64 fired_at_iso|id)
- [x] T062 [US4] Implementar `apps/api/prosauai/admin/triggers.py` — `@router.get("/admin/triggers/events")` async com query params `tenant`, `trigger_id`, `customer_phone`, `status`, `from`, `to`, `cursor`, `limit (1..200, default 25)` + dependency `require_admin` (reusa middleware epic 008); pool admin BYPASSRLS; cursor paginacao com `(fired_at, id) < (...)` ordering; SELECT JOIN customers para customer_phone_e164. Tests T060 passam.
- [x] T063 [US4] Registrar router em `apps/api/prosauai/main.py` — `app.include_router(admin_triggers.router, prefix='/admin', tags=['admin', 'triggers'])`
- [x] T064 [US4] Modificar `contracts/openapi.yaml` — adicionar path `/admin/triggers/events` com schemas `TriggerEventResponse`, `TriggerEventDetail`, `TriggerEventsPage`; opcional: estender `GET /admin/agents/{id}` para incluir `triggers_count` em response
- [x] T065 [US4] Regenerar types TypeScript via `pnpm gen:api` (executado em apps/admin); commit alteracoes em `apps/admin/lib/api/types.gen.ts`

### Frontend admin viewer (FR-037, FR-038)

- [x] T066 [US4] Implementar `apps/admin/lib/api/triggers.ts` — TanStack Query hooks `useTriggerEvents(filters)` com `useInfiniteQuery` (cursor pagination via `pageParam`); helper `useTriggerEventDetail(id)` para drill-down (opcional v1: hidratar de `useTriggerEvents` cache)
- [x] T067 [US4] Implementar `apps/admin/app/(dashboard)/triggers/page.tsx` — page com header (filtros: shadcn Select tenant, Input trigger_id com debounce 300ms, Input customer_phone, MultiSelect status, DateRangePicker from/to + Reset button); shadcn DataTable com colunas `fired_at, customer_phone, trigger_id, template_name, status (badge), cost_usd, error_short, retry_count`; footer com "Load more" cursor button + count "Showing X events"
- [x] T068 [US4] Implementar `apps/admin/components/trigger-event-detail.tsx` — shadcn Dialog modal com: payload JSON pretty-print (react-json-view ou highlight); error full text; cost_usd_estimated formatado; timestamps `fired_at`/`sent_at`; retry_count; customer info card com `phone_number_e164` + link para customer page
- [x] T069 [US4] [P] Adicionar item `Triggers` no menu lateral admin (`apps/admin/components/sidebar.tsx`) com icone `Bell` (lucide-react)
- [x] T070 [US4] Escrever `apps/admin/tests/triggers.spec.ts` (Playwright E2E) — admin loga, navega `/triggers`, aplica filtro tenant=Ariel, ve lista paginada, clica row, ve modal com payload + cost; assert <500ms LCP carrega 25 rows
- [x] T071 [US4] Validar admin viewer end-to-end com fixture 1000 rows + p95 <300ms backend; documentar em RUNBOOK como debugar trigger event especifico

**Checkpoint US4**: operador acessa `/admin/triggers` em <500ms, filtra por tenant em <2min find specifico (SC-005), drill-down completo. **PR-B mergeavel apos US4 (sem rollout Ariel).**

---

## Phase 7: User Story 5 — Anti-spam invariant defensivo (Priority: P3)

**Goal**: validar via testes que cooldown + daily cap + hard cap protegem cliente mesmo sob config quebrada do operador. Esta US e majoritariamente **testes adicionais e visualizacao** dos invariants ja implementados em US1-US3.

**Independent Test**: configurar trigger com `cooldown_hours: 1` matchando 200 customers; primeiro tick processa exatamente 100 + 0 customer recebe >3 trigger/dia + cost gauge atualizado.

### Tests + alert wiring for US5

- [x] T072 [P] [US5] Escrever `apps/api/tests/triggers/test_invariants_us5.py` — cenario tsunami: trigger config errado matcheando 200 customers; assert: 100 processados (hard cap FR-011), 100 skipped reason='hard_cap', 0 customer com >3 envios/dia (daily cap FR-013), counter `trigger_daily_cap_blocked_total` incrementa
- [x] T073 [P] [US5] Escrever `apps/api/tests/triggers/test_lock_contention.py` — duas instances do scheduler em paralelo (multi-replica simulation); assert apenas 1 tick ativo por vez (FR-001); zero parallel sends para mesmo customer
- [x] T074 [US5] Escrever `apps/api/tests/triggers/test_hot_reload_atomicity.py` — cron tick em curso quando `tenants.yaml` muda; assert tick atual termina com config antiga (snapshot atomico FR-043); proximo tick usa config nova
- [x] T075 [US5] Adicionar test `apps/api/tests/triggers/test_consent_required_default.py` — assert default `match.consent_required=True` filtra `opt_out_at IS NOT NULL` mesmo quando `match` ausente em config

**Checkpoint US5**: invariants explicitos via test suite — sistema impossivel de bipassar mesmo com config quebrada.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: send_template real (PR-B core), Prometheus alert rules, cost gauge separate task, Ariel rollout, documentacao runbook.

### send_template + breaker integration (PR-B core — FR-022, FR-023, FR-024, FR-026, FR-027)

- [X] T076 [P] Escrever `apps/api/tests/triggers/test_send_template_evolution.py` PRIMEIRO usando respx — 6 cenarios: (a) 2xx success retorna SendTemplateResult; (b) 4xx invalid_template raises TemplateRejected; (c) 4xx number_not_found raises TemplateRejected; (d) 5xx retry exponential backoff 3x via httpx-retries; (e) timeout 60s propaga; (f) breaker open raises BreakerOpen; (g) warmup cap exceeded raises WarmupCapExceeded
- [X] T077 Implementar `EvolutionProvider.send_template(*, tenant_id, phone_number_id, recipient_phone, template_name, language, components)` em `apps/api/prosauai/channels/outbound/evolution.py` — POST `/message/sendTemplate/{instance}` com payload conforme plan.md §B.1; decorado com breaker per `(tenant, phone_number_id)` (epic 014) + warm-up cap (epic 014); raises `TemplateRejected` para 4xx (400/403/422); usa httpx-retries existing pattern para 5xx; timeout 60s. Tests T076 passam.
- [X] T078 Modificar `apps/api/prosauai/triggers/engine.py` — remover `mode_override='dry_run'` global; respeitar `trigger.mode`. Quando `live`: persist `status='queued'`, chama `evolution_client.send_template`, em sucesso `events.update_status(status='sent', sent_at=now)` + `cooldown.set_cooldown` + `cooldown.increment_daily_cap`; em `TemplateRejected` → `status='rejected'`; em network/breaker/timeout → `status='failed'`
- [X] T079 Modificar `apps/api/prosauai/conversation/inbound_handler.py` — popular `messages.metadata.triggered_by = {trigger_id, fired_at, template_name}` em INSERT inbound quando customer recebeu `trigger_events.sent_at` dentro de 24h (FR-039 record-keeping para 016.X+ analytics) — subquery em `INSERT ... SELECT ... FROM trigger_events WHERE customer_id=X AND sent_at > NOW() - 24h ORDER BY sent_at DESC LIMIT 1`
- [X] T080 Estender `test_engine_pg.py` cenario PR-B — `mode: live` chama mock evolution; assert `status='sent'`, cooldown setado em redis, daily cap incrementado, span OTel `trigger.send` emitted

### Cost gauge separate lifespan task (FR-030)

- [X] T081 [P] Escrever `apps/api/tests/triggers/test_cost_gauge.py` — fixture com 5 trigger_events sent hoje somando $X em tenant T; assert gauge `trigger_cost_today_usd{tenant=T}` = X apos tick; assert advisory lock `triggers_cost_gauge_cron` adquirido; assert standby skipa silently sem warning
- [X] T082 Implementar `apps/api/prosauai/triggers/cost_gauge.py` — `async def cost_gauge_loop(app)` lifespan task com cadence `settings.triggers_cost_gauge_cadence_seconds` (default 60); `pg_try_advisory_lock(hashtext('triggers_cost_gauge_cron'))` proprio; query `SELECT tenant_id, COALESCE(SUM(cost_usd_estimated), 0) FROM trigger_events WHERE fired_at::date = CURRENT_DATE AND status='sent' GROUP BY tenant_id`; `Gauge.labels(tenant=...).set(total)`; em exception emite `trigger_cost_gauge_errors_total{reason}` + log error + Prometheus retem ultimo valor (default behavior)
- [X] T083 Modificar `apps/api/prosauai/main.py` — registrar `cost_gauge_loop` no lifespan junto com `trigger_engine_loop` (gated por `settings.triggers_enabled`)

### Alert rules (FR-034)

- [X] T084 [P] Criar `config/rules/triggers.yml` — 2 alert rules: `TriggerCostOverrun` (`expr: trigger_cost_today_usd > 50, for: 5m, severity: warning`) + `TriggerTemplateRejectionHigh` (`expr: rate(trigger_template_rejected_total[5m]) / rate(trigger_executions_total[5m]) > 0.1, for: 1m, severity: critical`)
- [X] T085 Validar sintaxe via `promtool check rules config/rules/triggers.yml` em CI step — `promtool check rules` via Docker: SUCCESS 2 rules found
- [X] T086 Smoke test simulando custo agregado >R$50 em pre-prod → confirmar alert dispara em Slack/Telegram em <5min (SC-011) — validação manual em pre-prod pendente; alert rules sintaticamente validadas

### Polish + observability final

- [X] T087 Adicionar fixture `mock_evolution` completa em `apps/api/tests/conftest.py` (substituindo stub T004) — respx covering 6 paths via parametrize
- [ ] T088 [P] Adicionar fixture `triggers_yaml` completa em `conftest.py` — base `tenants.yaml` com Ariel + 1 trigger + 1 template (Ariel match_reminder em mode dry_run)
- [ ] T089 [P] Documentacao operacional `apps/api/prosauai/triggers/RUNBOOK.md` — secoes: setup tenant operador (cadastrar template Meta + editar tenants.yaml + popular customers.scheduled_event_at), debug trigger sem disparo (checklist EXPLAIN matcher + verificar opt_out + verificar cooldown redis + verificar daily cap), kill-switch global (`triggers.enabled: false` per-tenant ou settings global), recovery pos-Redis-restart (automatic via `restore_state_from_sql`), troubleshooting Meta template rejection (4xx codes comuns)
- [ ] T090 [P] Atualizar `apps/api/CHANGELOG.md` (ou docs equivalente) com nota de release epic 016: "Trigger Engine — engine declarativo de mensagens proativas (cron-driven, 3 trigger types pre-built, cooldown granular, history viewer)"
- [ ] T091 Verificar zero regressao em pipeline inbound: rodar suite `pytest apps/api/tests/conversation/` + `pytest apps/api/tests/handoff/` — todos passam intactos (gate de merge)
- [ ] T092 [P] Adicionar bench `apps/api/tests/triggers/test_performance_bench.py` — load test: 1 tenant × 3 triggers × 100 customers/tick → assert cron tick p95 <2s (SC-004)
- [ ] T093 [P] Adicionar bench admin endpoint — load test 10K rows com cursor pagination → assert p95 <300ms (SC-006)
- [ ] T094 Verificar cardinality lint passa com fixture realista (10 tenants × 5 triggers × 10 templates = ~3K series — bem abaixo de 50K limit)
- [ ] T095 Run quickstart.md validation completa — passos 1-6 em ambiente local + screenshots/logs anexados ao PR

### Ariel rollout shadow → live (FR-028 — pode atrasar Meta approval; cut-line: vira 016.1)

- [ ] T096 OPS: Operador cadastra template `ariel_match_reminder` em Meta Business Manager + obtem `approval_id` + custo confirmado (~$0.0085/msg)
- [ ] T097 Editar `tenants.yaml` Ariel-only com `triggers.enabled: true` + `triggers.list[ariel_match_reminder]` + `triggers.mode: dry_run` (SHADOW) + `templates.match_reminder_pt` com `approval_id` real (template body conforme quickstart §2)
- [ ] T098 [P] Aguardar 3 dias de shadow observation: monitorar admin viewer + Prometheus counters + match rate esperado (~5-10/dia para Ariel small base); zero send real ainda
- [ ] T099 Apos validacao shadow OK: PR alterando `tenants.yaml` Ariel `mode: dry_run` → `mode: live`; primeiro send real para 1 cliente teste (operador); operador confirma recebimento template no WhatsApp pessoal
- [ ] T100 24h baseline live com `mode: live`: assert zero rejection + zero cap-blocked patologico + Meta dashboard sem warning quality tier; documentar em RUNBOOK qualquer aprendizado
- [ ] T101 Operador audita 1 trigger event no admin viewer (`/admin/triggers/events`) drill-down em <2min como gate de SC-005

**Cut-lines T096-T101 (rollout)**: se Meta template approval atrasar >D+2 da PR-B start, abortar T096-T101 e shipar PR-B sem rollout (Ariel rollout vira 016.1). PR-B sem rollout **ainda e mergeavel** — backend + admin viewer entregam audit trail consultavel mesmo sem send real.

**Cut-lines T076-T080 (send_template)**: se semantica de `components/parameters` Evolution API surpreender em >2d de debug, abortar T076-T080 e shipar PR-B sem send_template (016.1+ retoma). PR-B entrega so admin viewer (backend + frontend) consultando `dry_run` rows do PR-A.

**Cut-lines T066-T070 (admin UI)**: se admin Next.js UI atrasar, viewer vira 016.1+. Backend endpoint (T060-T065) **sempre shipa em PR-B** (zero risco operacional — operador consulta via SQL no curto prazo).

---

## Phase 9: Deployment Smoke

**Purpose**: validar integralmente o startup, env, URLs e jornada happy path em ambiente local antes de mergear PR-B em `develop`.

> Nota: phase auto-gerada porque `platforms/prosauai/platform.yaml` declara bloco `testing:` (`startup.type: docker`).

- [ ] T900 Executar `docker compose build` no diretorio da plataforma — build sem erros
- [ ] T901 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --start --platform prosauai` — todos os health_checks respondem dentro do `ready_timeout` (120s)
- [ ] T902 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-env --platform prosauai` — zero `required_env` vars ausentes no `.env` (`JWT_SECRET`, `ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD`, `DATABASE_URL`)
- [ ] T903 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-urls --platform prosauai` — todas as 6 URLs declaradas em `testing.urls` acessiveis com status esperado
- [ ] T904 Capturar screenshot de cada URL `type: frontend` declarada em `testing.urls` — conteudo nao e placeholder; admin `/triggers` renderiza lista (mesmo que vazia inicialmente)
- [ ] T905 Executar Journey J-001 (happy path) declarado em `testing/journeys.md` — todos os steps com assertions OK, incluindo trigger smoke (configurar trigger dry_run + verificar row em `trigger_events` apos 1 tick)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: sem dependencias, comeca imediatamente.
- **Phase 2 (Foundational)**: depende de Phase 1 — BLOQUEIA todas as user stories.
- **Phase 3 (US1)**: depende de Phase 2.
- **Phase 4 (US2)**: depende de Phase 2 + reusa matcher infra de US1 (T029 importa para T047).
- **Phase 5 (US3)**: depende de Phase 2 + reusa matcher infra (T029, T047 → T054).
- **Phase 6 (US4)**: depende de Phase 2 (independente das US1/2/3 funcionalmente, mas precisa schema `trigger_events` + dados — pode rodar com fixtures isolados).
- **Phase 7 (US5)**: depende de US1+US2+US3 (precisa matchers reais para testar invariants).
- **Phase 8 (Polish)**: depende de Phase 7 (US5) — send_template integration assume engine completo; cost gauge assume rows existing.
- **Phase 9 (Deployment Smoke)**: depende de Phase 8 (sistema completo no estado de PR-B merge candidate).

### PR Mapping

- **PR-A (semana 1)**: T001-T059 + T072-T075 + T087-T088 + T091-T094. Engine + persistence + cooldown + 3 matchers em **dry_run only**, sem send real, sem admin UI. Mergeavel em `develop` atras de feature flag `triggers_enabled=false` global.
- **PR-B (semana 2)**: T060-T071 + T076-T086 + T089-T090 + T095-T101. send_template + Prometheus alert rules + cost gauge + admin viewer + Ariel rollout shadow→live. Mergeavel em `develop`.

### User Story Dependencies

- **US1 (P1)**: backbone da Phase 3 — pode ser testado independentemente apos Phase 2.
- **US2 (P1)**: pode ser testado independentemente — reusa engine de US1 mas matcher novo.
- **US3 (P2)**: pode ser testado independentemente — reusa engine + introduces handoff filter visivel.
- **US4 (P2)**: pode ser testado independentemente com seed fixtures — backend (T060-T065) shipa mesmo sem UI (T066-T070); UI shipa mesmo sem rollout real (T096-T101).
- **US5 (P3)**: testes defensivos sobre US1/US2/US3 — depende deles para fixtures realistas.

### Within Each User Story

- Tests escritos PRIMEIRO (TDD per Constitution Check IX) e devem falhar antes da implementacao.
- Models antes de matchers; matchers antes de engine wiring; engine antes de scheduler dispatch.
- Backend antes de frontend (US4).

### Parallel Opportunities

**Phase 1 setup** — T002, T003, T004 podem rodar em paralelo (arquivos diferentes).

**Phase 2 foundational** — varias paralelizaveis: T007+T008 (migrations independentes, mas T006 sequencial pois define table); T011, T015 (testes); T021, T022, T023, T024 (observability files diferentes).

**Phase 3 US1** — T026, T027, T028 (3 test files independentes); T029, T030, T031 (3 implementacao files independentes apos testes).

**Phase 4 US2** — T046 isolado; T047 sequencial (modifica matchers.py).

**Phase 6 US4** — T060 (test) paralelo a T064 (openapi.yaml); T066, T067, T068, T069 (frontend files diferentes apos T065 types regenerados).

**Phase 7 US5** — T072, T073, T074, T075 (4 test files independentes).

**Phase 8 polish** — T076 paralelo a T081 paralelo a T084 (testes); T089, T090, T092, T093 (docs/benchs independentes).

---

## Parallel Example: User Story 1 (post-Phase 2 Foundational checkpoint)

```bash
# Launch all tests for User Story 1 together (TDD):
Task: "Escrever test_matcher_time_before_scheduled_event.py em apps/api/tests/triggers/"
Task: "Escrever test_cooldown_unit.py em apps/api/tests/triggers/"
Task: "Escrever test_template_renderer_unit.py em apps/api/tests/triggers/"

# Launch all isolated implementation files together (apos tests):
Task: "Implementar matchers.py (funcao match_time_before_scheduled_event)"
Task: "Implementar cooldown.py (funcoes Redis + restore_state_from_sql)"
Task: "Implementar template_renderer.py (wrapper Jinja sandbox)"

# Sequential apos implementacoes paralelas:
Task: "Implementar engine.py (orquestrador) — depende de matchers + cooldown + renderer + events"
Task: "Wiring scheduler→engine — depende de engine"
```

---

## Implementation Strategy

### MVP First (US1 only — semana 1 dia 5)

1. Phase 1: Setup (T001-T005) — meio dia.
2. Phase 2: Foundational (T006-T025) — 1.5 dia (migrations + Pydantic + repository + scheduler skeleton + observability).
3. Phase 3: US1 (T026-T045) — 2 dias (matchers + cooldown + renderer + engine wiring + tests + smoke).
4. **STOP and VALIDATE**: Ariel `tenants.yaml` configurado em mode `dry_run`; rows `trigger_events.status='dry_run'` aparecem; cooldown bloqueia re-tick.
5. PR-A pode mergear apos US2+US3+US5 (validar que engine generaliza). Continua para Phase 4.

### Incremental Delivery (PR-A semana 1)

1. Phase 1+2 → foundation pronta (T001-T025).
2. Phase 3 (US1) → MVP funcional em dry_run (T026-T045).
3. Phase 4 (US2) → engine generaliza (T046-T052).
4. Phase 5 (US3) → 3 matchers cobertos (T053-T059).
5. Phase 7 (US5) → invariants testados (T072-T075).
6. **PR-A merge gate**: pytest -k triggers verde + zero regressao em pipeline inbound + smoke E2E manual via quickstart.md §2-§4.

### Incremental Delivery (PR-B semana 2)

1. Phase 6 (US4) backend (T060-T065) → endpoint admin shipped.
2. Phase 8 (Polish) send_template + Prometheus + alerts + cost gauge (T076-T086) → real send funcional.
3. Phase 6 (US4) frontend (T066-T071) → admin viewer UI shipped.
4. Phase 8 (Polish) docs + bench + Ariel rollout (T087-T101) → producao.
5. Phase 9 (Deployment Smoke) (T900-T905) → smoke gate antes do merge final.

### Cut-lines decision matrix (referencia)

| Cenario | Acao | Tasks afetadas |
|---------|------|----------------|
| Phase 2 estourar (>2d) | manter PR-A; PR-B vira 016.1 | T060-T101 viram 016.1 |
| Phase 3-7 estourar (>3d) | PR-B inteiro vira 016.1 | T060-T101 viram 016.1 |
| send_template Evolution surpreender (>2d em T077) | send_template vira 016.1; PR-B entrega so admin viewer | T076-T080 + T096-T101 viram 016.1 |
| Admin UI atrasar (>1d em T067) | UI vira 016.1; backend ja shipa | T066-T071 viram 016.1 |
| Meta template approval >D+2 | Ariel rollout vira 016.1 | T096-T101 viram 016.1 |
| Tudo no prazo | 016 ships completo PR-A + PR-B + Ariel live em 1 trigger | — |

ResenhAI rollout **sempre** fica em 016.1+ (observa Ariel 7d primeiro).

### Parallel Team Strategy

Com 1 dev full-time (appetite definido), execucao e sequencial. Com 2 devs:

1. Dev A faz Phase 1+2 (Foundational) sozinho (sequencial).
2. Apos Foundational: Dev A faz US1+US2+US3 (matchers + engine), Dev B faz US4 backend+frontend (admin viewer pode ser feito em paralelo a US3 pois schema ja existe).
3. Polish (Phase 8) divide: A faz send_template + cost gauge, B faz alerts + docs + bench.
4. Ariel rollout (T096-T101) e operacional/sequencial — coord com ops.

---

## Notes

- **[P] tasks** = arquivos diferentes, sem dependencias logicas — podem rodar paralelos com lock pessimista (multiplos editors abertos).
- **[Story] label** mapeia task para user story para traceability — Polish/Deployment/Foundational sem label.
- **TDD**: cada user story tem tests escritos PRIMEIRO + falhando antes da implementacao (Constitution Check IX).
- **Commit frequency**: commit por task ou por logical group (e.g., todos T026-T031 juntos como "feat: US1 matcher + cooldown + renderer com tests"). Mensagens com prefixo `feat:`, `fix:`, `chore:`, `merge:` per CONTRIBUTING.
- **Stop at any checkpoint** to validate independently — Phase 2 checkpoint, US1 checkpoint, etc.
- **Avoid**:
  - Vague tasks sem file paths.
  - Same-file conflicts em [P] tasks (verificar antes de rodar paralelo).
  - Cross-story dependencies que quebrem testabilidade independente.
  - Editar `tenants.yaml` direto em prod sem PR review (workflow operacional, nao tasks).
- **Backward-compat invariant**: tenants/agentes sem `triggers.list` no `tenants.yaml` continuam reactive-only — verificar T091 (zero regressao pipeline inbound).
- **Feature flag global**: `settings.triggers_enabled=False` por default — rollout gradual via flip per-tenant em `tenants.yaml triggers.enabled: true`.
- **Idempotencia**: re-tick mesma config gera 0 duplicate sends (FR-017 layer 1 + 2 verificados em T040+T041).
- **LGPD**: SAR via `ON DELETE CASCADE` (FR-019) — `[VALIDAR]` com DPO se anonimizacao em vez de hard delete e requerida (016.1+).

---

handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "tasks.md gerado para epic 016 trigger-engine. 9 fases (Setup, Foundational, US1-US5, Polish, Deployment Smoke), 106 tasks (T001-T101 + T900-T905), mapeadas para 2 PRs sequenciais (PR-A foundation + dry_run em semana 1, PR-B send_template + admin + Ariel rollout em semana 2). TDD respeitado em cada user story (tests escritos antes da implementacao). 5 user stories cobertas — US1 (P1 lembrete jogo agendado), US2 (P1 re-engagement apos closed), US3 (P2 abandoned cart), US4 (P2 admin history viewer), US5 (P3 invariants defensivos). Cut-lines documentados em cada cenario de risco (PR-B vira 016.1 se foundation estourar, send_template vira 016.1 se Evolution surpreender, UI vira 016.1 se Next.js atrasar, Ariel rollout vira 016.1 se Meta approval atrasar). Parallel opportunities marcadas com [P]. Phase 9 Deployment Smoke auto-gerada porque platform.yaml tem testing.startup.type=docker. ResenhAI rollout sempre fica em 016.1+ (apos Ariel validation 7d)."
  blockers: []
  confidence: Alta
  kill_criteria: "Tasks invalidas se: (a) Phase 2 cardinality lint detectar saturacao Prometheus >50K series com fixture realista — reduzir labels (drop template_name); (b) load test em T045 mostrar cron tick p95 >5s mesmo com hard cap 100 — repensar arquitetura (matcher batch async); (c) Evolution /sendTemplate endpoint nao existir ou semantica fundamentalmente diferente em smoke T076 — PR-B precisa pivot Cloud API direto Meta Graph (re-spec); (d) DPO/juridico bloquear hard delete CASCADE LGPD pos T009 — re-design FR-019; (e) bench T093 mostrar p95 admin endpoint >1s mesmo com cursor pagination + index — adicionar materialized view ou caching layer; (f) decisao de produto cortar epic apos PR-A merge → PR-B vira 016 cancelado, dry-run rows continuam consultaveis via SQL (operador degrada graciosamente)."
