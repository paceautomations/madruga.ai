# Research — Epic 016 Trigger Engine

**Phase 0 output**. Para cada NEEDS CLARIFICATION ou decisao tecnica nao trivial, alternativas analisadas com pros/cons + decisao final.

> NOTA: Os 30 itens em [pitch.md §Captured Decisions](./pitch.md) + 5 itens em [spec.md §Clarifications](./spec.md) cobrem **decisoes de produto/arquitetura ja tomadas** no epic-context e clarify. Este `research.md` cobre **alternativas tecnicas de implementacao** decididas no plan (D-PLAN-01..12).

---

## R1 — Mecanismo de source: cron-only vs PG NOTIFY vs hibrido

**Contexto**: triggers proativos podem ser disparados por (a) cron periodico observando estado do banco; (b) listener de eventos PG LISTEN/NOTIFY reagindo a INSERTs em `messages`/`conversations`; (c) hibrido (cron para timed + listener para event-reactive).

| Opcao | Pros | Cons |
|-------|------|------|
| **A. Cron-only** (escolhida — D-PLAN-01) | Simples; advisory lock singleton ja pattern em 4 epics (010, 011, 014, 015); zero deps externas; reusa scheduler module integral; deterministic; previsivel para load test; sem lock-global ADR-004 issue | Lag ate 15s entre evento e disparo (`time_after_last_inbound` atrasa 15s no pior caso); custos PG SELECT em cada tick (mitigado por indexes partial) |
| B. PG LISTEN/NOTIFY listener | Lag <100ms; reativo natural | ADR-004 explicitamente flaga lock-global; threshold para migrar para bridge pattern; complexidade extra (listener + reconciliation se conexao quebrar); precisa NOTIFY trigger em INSERT messages (mais 1 trigger PG); zero benefit para `time_before_scheduled_event` (sempre futuro, nao reativo) |
| C. Hibrido — cron para `time_before_scheduled_event` + listener para `time_after_last_inbound` | Lag <100ms onde matter; cron simples para timed | Dois paths para manter; ADR-004 lock issue; complicado teste integration |

**Decisao**: A (cron-only). Todos use cases v1 sao scheduled/timed (lembrete antes de jogo, follow-up apos consulta, abandoned cart 48h depois) — 15s de lag e operacionalmente irrelevante. PG NOTIFY listener (opcao B/C) vira **016.1+ apenas se demanda real-time aparecer** (e.g., abandoned cart reativo a INSERT em `messages` com janela <60s). Pattern epic 010/011/014 reusado integralmente.

**Trade-off explicito**: aceitamos max 15s de lag para todos triggers. Isso quebra demanda hipotetica de "trigger imediato apos evento" — se aparecer em 016.1+, hibrido com listener.

---

## R2 — Trigger definition storage: `tenants.yaml` blocks vs PG tables

**Contexto**: como persistir definicoes de triggers + templates para hot reload + auditoria + UI futura.

| Opcao | Pros | Cons |
|-------|------|------|
| **A. `tenants.yaml triggers.* + templates.*` blocks** (escolhida — D-PLAN-02) | Pattern consolidado em 4 epics (010 helpdesk, 013 integrations, 014 warmup, 015 nfr override) — **zero learning curve**; hot reload <60s ja existente via `config_poller`; YAML PR review e auditavel (git history); diff visual claro; sem migrations; sem CRUD APIs; zero infra | Ops precisa editar arquivo YAML (workflow de PR review); sem self-service tenant-facing UI v1; menos discovery que UI |
| B. Tabelas dedicadas `triggers` + `templates` no PG | UI editor pode escrever direto; valor "data is queryable"; multi-tenant isolation via RLS | +2 migrations + +4 endpoints CRUD + Pydantic schemas + hot reload reimplementado ou cache invalidation manual; YAML perdido em git history (audit em audit_log table); >2x esforco PR-A; agora UI virou must em PR-B (era nice-to-have); scope creep |
| C. Hibrido — YAML para triggers (config) + PG para templates (catalogo) | Templates sao catalogo (queryable) + triggers sao policies (versioned via git) | Mais complexidade conceitual; 2 fontes de verdade |

**Decisao**: A (tenants.yaml blocks). Pattern consolidado, hot reload ja funciona, audit nativo via git, zero scope creep. Self-service UI vira **epic 018 (Tenant Self-Admin)** quando ja tivermos comprovacao de uso real (30+ tenants). Manual ops em v1 (Pace controla operacao centralizada — vision §3 supports).

**Trade-off explicito**: ops precisa workflow de PR review para alterar trigger config — onboarding marginalmente mais lento que UI form. Aceitavel em v1; epic 018 destrava self-service quando volume justificar.

---

## R3 — Cooldown enforcement: Redis-only vs SQL-only vs hibrido

**Contexto**: enforcement de cooldown 24h per `(tenant, customer, trigger_id)` + global daily cap 3/dia per `(tenant, customer)`.

| Opcao | Pros | Cons |
|-------|------|------|
| A. Redis-only (TTL chaves) | Latencia <1ms; TTL nativo; pattern epic 010 reusa | Quebra em restart do Redis (state perdido) → duplicate sends ate proximo dia |
| B. SQL-only (query `trigger_events` antes de cada send) | Persistente; idempotente; zero state extra | Latencia ~5ms × 100 customers = 500ms por tick — pesa no <2s budget; precisa index novo `(tenant, customer, fired_at)` redundante |
| **C. Hibrido — Redis fast-path + SQL fallback** (escolhida — D-PLAN-03) | Latencia <1ms hot path; recovery via SQL pos-restart (FR-015); reusa `trigger_events` index existente (`customer_id, fired_at DESC`); zero duplicate sent garantido | +1 fluxo de codigo (restore_state_from_sql); test chaos para validar |

**Decisao**: C (hibrido). Redis e fast-path; on Redis empty (`EXISTS key=0` para todos os keys), engine chama `restore_state_from_sql` que le `trigger_events.status='sent'` ultimas 24h e re-popula Redis com TTL apropriado. Idempotencia em runtime garante zero duplicate mesmo se restore atrasar.

**Trade-off explicito**: aceitamos +1 modulo de codigo (cooldown.restore_state_from_sql) + +1 chaos test em troca de fast-path Redis com recovery garantido. Alternativa SQL-only pesaria 500ms por tick (25% do budget de 2s) — inaceitavel.

---

## R4 — Idempotencia: app-check vs DB UNIQUE vs hibrido

**Contexto**: garantir que mesma `(tenant, customer, trigger_id, fired_at::date)` nao gere 2 sends. Decidido em clarify Round 2 spec.md.

| Opcao | Pros | Cons |
|-------|------|------|
| A. App-check antes do INSERT | Simples; query SELECT `WHERE ... LIMIT 1` rapida (~1ms) | Race condition possivel em multi-replica (improvavel com advisory lock, mas nao impossivel se lock falhar); bug futuro pode esquecer check |
| B. DB UNIQUE INDEX only | Defesa em profundidade; impossivel race condition; zero overhead em writes | App ainda precisa tratar UniqueViolation; insert tenta, fail, recovery — 1 round-trip extra |
| **C. Hibrido — app-check + partial UNIQUE INDEX** (escolhida — D-PLAN-04) | App-check evita UniqueViolation 99.9% das vezes (custo 1 round-trip); index pega 0.1% race + futuros bugs; partial INDEX `WHERE status IN ('sent','queued')` permite multiplos rows skipped/rejected/dry_run/failed (audit) | +1 index (zero custo writes append-only); +1 catch handler |

**Decisao**: C (hibrido). FR-017 spec.md ja captura. Index parcial preserva audit trail completo (multiplos `skipped`, `rejected` permitidos), mas garante max 1 row `sent` ou `queued` por dia per `(tenant, customer, trigger_id)`. UniqueViolation captado e gravado como `status='skipped' reason='idempotent_db_race'`.

**Trade-off explicito**: aceitamos +1 partial UNIQUE INDEX (zero custo em writes append-only) e +1 catch handler em troca de defesa em profundidade. App-check sozinho seria suficiente em runtime atual mas frageil contra bugs futuros.

---

## R5 — Stuck-detection: insert nova row vs UPDATE in-place

**Contexto**: rows com `status='queued' AND fired_at < NOW() - 5min` precisam ser re-tentadas (cron crash mid-tick). Decidido em clarify Round 2.

| Opcao | Pros | Cons |
|-------|------|------|
| A. INSERT nova row a cada retry | Audit imutavel: cada tentativa = 1 row | Quebra idempotencia DB (mesma chave logica geraria 2+ rows `sent`/`queued`); audit fica confuso (3 rows para 1 trigger logico); precisa LATERAL JOIN para reconstruir historia |
| **B. UPDATE in-place + retry_count column** (escolhida — D-PLAN-05) | Preserva 1 row = 1 trigger logico; respeita idempotency UNIQUE; retry_count visivel no admin viewer ajuda diagnostico (cron crash recorrente vira evidencia); audit_log em separate table futuramente captura mudancas se preciso | UPDATE em concurrent transactions precisa `FOR UPDATE SKIP LOCKED` (ja usado); audit_history fica em campo timestamps + retry_count em vez de rows |
| C. Hibrido — UPDATE em-place + audit_log separado | Audit completo + idempotency preservada | +1 table; complexidade extra; nao necessario v1 |

**Decisao**: B (UPDATE in-place + retry_count). FR-041 spec.md ja captura. Schema ja inclui `retry_count INT DEFAULT 0`. Recovery flow:
1. Matcher pega rows `WHERE status='queued' AND fired_at < NOW() - 5min AND retry_count < 3 FOR UPDATE SKIP LOCKED`.
2. UPDATE `retry_count++, fired_at=NOW()`.
3. Tenta send novamente.
4. Apos 3 retries, marca `status='failed'`.

**Trade-off explicito**: audit per-tentativa fica em retry_count + ultimo `error` (sobrescreve). Adequado v1 — debug raramente precisa de N tentativas separadas. Se virar must, audit_log table em 016.1+.

---

## R6 — Trigger types: 3 pre-built vs custom escape hatch

**Contexto**: oferecer apenas 3 trigger types pre-built (`time_before_scheduled_event`, `time_after_conversation_closed`, `time_after_last_inbound`) ou incluir um quarto `custom` com expression evaluator.

| Opcao | Pros | Cons |
|-------|------|------|
| **A. 3 pre-built apenas** (escolhida — D-PLAN-06) | Cobre 80% use cases roadmap; matchers SQL otimizados (indexes existing); zero surface attack (eval safety); validation Pydantic exhaustiva; testavel; previsivel | Trigger novo exige PR + code review (mas operadores tem 3 templates prontos para 80%) |
| B. 3 pre-built + `custom` com expression evaluator (DSL ou Python sandbox) | Flexibilidade tenant-specific | Surface attack expression eval (mesmo sandboxed); validation extremamente complexa; SQL dinamico ou matcher Python = perf imprevisivel; debug hard; Trojan horse (operador quebra prod com 1 expression mal escrita) |
| C. 3 pre-built + JSON-config `custom` (operadores compilam matcher Python e enviam PR) | Estende matchers via PR (nao runtime) | Mesma de A — operador faz PR — sem ganho; tras complexidade de runtime extension |

**Decisao**: A (3 pre-built). Roadmap mapeia 80% use cases nas 3 categorias. `custom` com expression vira **016.1+ apenas se baseline 30d mostrar demanda real**. Por agora, novo trigger type = PR no codigo (matcher novo + test integration). Aceitavel — operadores tem 3 templates funcionais.

**Trade-off explicito**: aceitamos onboarding rate marginal (PR para novo type) em troca de seguranca + performance + simplicity. Custom escape hatch aumenta surface attack proporcional a complexidade evaluator.

---

## R7 — `trigger_events` admin-only carve-out vs RLS per-tenant

**Contexto**: ADR-027 firma carve-out para tabelas de auditoria admin-only (`traces`, `trace_steps`, `routing_decisions`). Aplica a `trigger_events`?

| Opcao | Pros | Cons |
|-------|------|------|
| **A. Admin-only carve-out (sem RLS)** (escolhida — D-PLAN-10) | Consistente com ADR-027; queries cross-tenant simples (admin viewer); zero overhead RLS check em todo INSERT (~100K writes/dia/tenant); pool_admin BYPASSRLS reusa pattern epic 008 | Ops precisa garantir que app sempre filtra `tenant_id` em queries (cosmetic em v1, security em epic 018) |
| B. RLS per-tenant (igual a `messages`, `customers`) | Security boundary nativa; admin precisa BYPASSRLS para queries cross-tenant | Inconsistente com ADR-027; +1 trigger per INSERT; complica admin viewer (precisa SECURITY DEFINER func ou pool BYPASSRLS); zero ganho real (admin ja tem BYPASSRLS) |

**Decisao**: A (admin-only, sem RLS). ADR-027 ja firma o pattern; aplicar consistentemente. Filtro `tenant_id` em queries da UI e cosmetic em v1 (admin pode listar qualquer tenant — super-admin) e vira security boundary em epic 018 (Tenant Self-Admin) via role check `WHERE tenant_id = current_admin.scoped_tenant_id`.

**Trade-off explicito**: admin pode listar qualquer tenant em v1 — adequado pois Pace controla operacao centralizada (vision §3 supports). Tenant Self-Admin (epic 018) introduz RBAC tenant-scoped quando shipa.

---

## Decisoes adicionais (D-PLAN-07..D-PLAN-12 nao listadas em R1..R7)

### D-PLAN-07 — Manual ops cadastra templates Meta em `tenants.yaml`

**Alternativas**: (a) manual ops; (b) auto-sync via Meta Graph API.

**Decisao**: (a). Graph API exigiria 1 dep nova (`requests` ou `httpx` ja em uso, OK; mas precisa OAuth token + reconciliation de approval async 24-48h). Approval Meta e workflow humano por natureza — ops verifica catalog Meta e edita YAML. Auto-sync 016.1+.

### D-PLAN-08 — Admin viewer read-only em PR-B; sem editor de config

**Alternativas**: (a) viewer + editor form-based em PR-B; (b) viewer-only em PR-B + editor 016.1+.

**Decisao**: (b). YAML PR review e codigo vivente, audit nativo, zero risco de override em runtime. Editor adicionaria scope (Pydantic schema → form generator → optimistic update → validation client-side → audit_log) que nao agrega valor no day-1 (ops ja edita YAML hoje em outros epics). Editor vira 016.1+ apos 30d uso real.

### D-PLAN-09 — Opt-out manual via `customers.opt_out_at`

**Alternativas**: (a) coluna nova + manual ops; (b) detector NLP automatico (STOP/SAIR).

**Decisao**: (a). Detector NLP exigiria modelo + treino + thresholds + reviewer humano = fora appetite. Coluna nova e barata (zero index, uso e WHERE filter). Ops registra opt-out via `PATCH /admin/customers/{id}` quando cliente reclama. Detector NLP automatico vira 016.1+ apos baseline 30d.

### D-PLAN-11 — Cost gauge separate lifespan task

**Alternativas**: (a) inline no trigger_engine_loop (calcular SUM antes de retornar tick); (b) lifespan task separada com lock proprio.

**Decisao**: (b). Cron tick principal e hot path 15s; gauge query agregada SUM `WHERE fired_at::date = CURRENT_DATE` custa ~50-100ms — desacoplar evita slow path. Advisory lock proprio (`hashtext('triggers_cost_gauge_cron')`) garante 1 replica ativa em multi-replica deploy. Cadence 60s e suficiente para alert >R$50/dia em 5min (max 2 ticks de lag = ~120s, ainda dentro do for: 5min do alert).

### D-PLAN-12 — Hard delete LGPD via CASCADE

**Alternativas**: (a) hard delete via `ON DELETE CASCADE`; (b) anonimizar (set `customer_id=NULL` + redact `payload`).

**Decisao**: (a). ADR-018 firma direito ao apagamento (RGPD/LGPD). Metricas operacionais agregadas (`trigger_cost_today_usd`, taxa de rejection) permanecem em Prometheus retention 30d — ja independente de `customer_id`. Anonimizacao alternativa exige migration nova + redaction logic + queries especiais (e SAR delete remove evidencia per-customer — esse e o **proposito**). `[VALIDAR]` se DPO/juridico requer audit trail completo apos SAR — em 016.1+.

---

## Sumario de fontes

| Item | Fonte / referencia |
|------|---------------------|
| Pattern scheduler + advisory lock | `apps/api/prosauai/handoff/scheduler.py` (epic 010 shipped) |
| Pattern cooldown Redis | `apps/api/prosauai/handoff/cooldown.py` (epic 010) |
| Pattern admin BYPASSRLS pool | epic 008 (`apps/api/prosauai/admin/pool.py`) |
| Pattern config_poller hot reload | `apps/api/prosauai/config/tenants_loader.py` (epic 010/013/014/015) |
| Pattern Jinja sandboxed renderer | `apps/api/prosauai/conversation/jinja_sandbox.py` (epic 015) |
| ADR-006 Phase 2 | `platforms/prosauai/decisions/ADR-006-agent-as-data.md` |
| ADR-027 admin-only carve-out | `platforms/prosauai/decisions/ADR-027-admin-tables-no-rls.md` |
| ADR-018 LGPD SAR + retention | `platforms/prosauai/decisions/ADR-018-data-retention-lgpd.md` |
| Vision §6 tese comercial proativos | `platforms/prosauai/business/vision.md#6` |
| Meta WhatsApp template approval workflow | https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates (24-48h SLA) |
| Evolution API `/message/sendTemplate` | (a confirmar em PR-B smoke test — kill criterion) |

---

handoff:
  from: speckit.plan (research phase)
  to: speckit.plan (data-model phase)
  context: "7 alternativas R1..R7 + 5 decisoes D-PLAN-07..12 documentadas. Decisoes finais: cron-only v1, tenants.yaml blocks, cooldown hibrido Redis+SQL fallback, idempotencia hibrida app+DB partial UNIQUE, stuck-detection UPDATE in-place + retry_count, 3 pre-built sem custom v1, admin-only carve-out, manual templates Meta, viewer read-only sem editor v1, opt-out manual coluna nova, cost gauge separate task, hard delete CASCADE LGPD."
  blockers: []
  confidence: Alta
  kill_criteria: "Research invalido se descoberta nova mudar trade-off: (a) Evolution `/sendTemplate` semantica nao bater com proposto; (b) DPO requerer anonimizacao em vez de delete; (c) PG NOTIFY listener provar lag <100ms necessario para use case real-time critico no roadmap."
