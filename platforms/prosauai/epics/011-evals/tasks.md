# Tasks: Evals — Offline (DeepEval) + Online (Heurístico) + Dataset Incremental

**Input**: Design documents from `platforms/prosauai/epics/011-evals/`
**Prerequisites**: plan.md (3 PRs sequenciais), spec.md (6 user stories, 54 FRs, 12 SCs, 22 assumptions), data-model.md (5 migrations aditivas), contracts/ (Protocol EvalPersister + OpenAPI 3.1), research.md

**Tests**: Incluídos por padrão (convenção repo prosauai — epics 005/008/010 exigem TDD: unit ≥95% para `evals/persist.py` + `evals/autonomous_resolution.py`, ≥90% para `evals/deepeval_batch.py`, contract tests para Protocol, integration com testcontainers-postgres, benchmark p95 como gate de merge).

**Organization**: Tasks agrupadas por User Story (P1 → P3). Cada US é independentemente implementável e testável após Phase 2 (foundational).

**Code root**: Backend em `apps/api/` (repo externo `paceautomations/prosauai`, bindado em `platform.yaml`). Frontend admin em `apps/admin/`. Workflows em `.github/workflows/`.

## Format

`- [ ] TID [P?] [Story?] Descrição com caminho de arquivo absoluto/relativo ao repo`

- **[P]** = paralelizável (arquivos diferentes, sem dependência com tasks incompletas)
- **[USn]** = label de user story (apenas em phases de US)
- Paths relativos ao repo `paceautomations/prosauai` (backend) ou `paceautomations/prosauai/apps/admin` (frontend)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Deps, ADRs esboçados, env vars, schema de config. Bloqueia todas as demais fases.

- [x] T001 Rascunhar ADR-039 (Eval metric bootstrap sem golden dataset) em `platforms/prosauai/decisions/ADR-039-eval-metric-bootstrap.md` cobrindo reference-less DeepEval metrics + incremental golden + rationale ADD COLUMN `metric` vs RENAME `eval_scores`. Status: `proposed`.
- [x] T002 [P] Rascunhar ADR-040 (Autonomous resolution operational definition) em `platforms/prosauai/decisions/ADR-040-autonomous-resolution-heuristic.md` fixando heurística A canônica (sem mute + regex escalation + 24h silêncio + `is_direct` filter em grupo) e rationale vs alternativas (LLM-as-judge, per-segment). Status: `proposed`.
- [ ] T003 [P] Estender `platforms/prosauai/decisions/ADR-008-eval-stack.md` com sub-seção "011 Confirmation" referenciando DeepEval+Promptfoo + AnswerRelevancy como substituto reference-less de Faithfulness.
- [ ] T004 [P] Estender `platforms/prosauai/decisions/ADR-027-admin-tables-no-rls.md` listando `public.golden_traces` no carve-out admin-only.
- [ ] T005 [P] Estender `platforms/prosauai/decisions/ADR-028-pipeline-fire-and-forget-persistence.md` confirmando `persist_score` herda pattern (seção "Consumers").
- [ ] T006 Adicionar env vars em `apps/api/prosauai/config.py` (classe `Settings`): `AUTONOMOUS_RESOLUTION_INTERVAL_SECONDS` (default 3600), `DEEPEVAL_BATCH_INTERVAL_SECONDS` (default 86400), `DEEPEVAL_MAX_SAMPLE_SIZE` (default 200), `EVAL_SCORES_RETENTION_INTERVAL_SECONDS` (default 86400), `EVAL_SCORES_RETENTION_DAYS` (default 90), `EVAL_SCORES_RETENTION_ENABLED` (default True kill-switch). Documentar em docstring.
- [ ] T007 [P] Adicionar as mesmas vars em `.env.example` com comentários indicando defaults e impacto.
- [ ] T008 Criar módulo base `apps/api/prosauai/evals/__init__.py` com docstring explicando escopo (online heuristic + offline DeepEval + golden curation + autonomous resolution) e referenciando ADR-039/040.
- [ ] T009 Preparar `ruff`/`black` para novo módulo — confirmar que `pyproject.toml` já inclui `apps/api/prosauai/evals/` no escopo (ou adicionar se faltar).

**Checkpoint**: ADRs esboçados + env vars + módulo vazio. Phase 2 pode começar.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 4 migrations aditivas (1-4), Pydantic models base, scheduler e facade de métricas compartilhados. **TODAS** as user stories dependem desta fase.

**⚠️ CRITICAL**: Nenhuma US pode começar antes desta fase estar verde.

### Migrations (PR-A)

- [ ] T010 Criar `apps/api/db/migrations/20260601000001_alter_eval_scores_add_metric.sql` — `ADD COLUMN metric VARCHAR(50) NOT NULL DEFAULT 'heuristic_composite'` + backfill rows existentes + `CHECK (metric IN ('heuristic_composite','answer_relevancy','toxicity','bias','coherence','human_verdict'))` + `CREATE INDEX idx_eval_scores_tenant_evaluator_metric_created` (tenant_id, evaluator_type, metric, created_at DESC) + `migrate:down` reverso (ver data-model.md §2.1).
- [ ] T011 [P] Criar `apps/api/db/migrations/20260601000002_alter_traces_unique_trace_id.sql` — `CREATE UNIQUE INDEX CONCURRENTLY idx_traces_trace_id_unique` + `DROP INDEX idx_traces_trace_id` + `ALTER TABLE ... ADD CONSTRAINT traces_trace_id_unique UNIQUE USING INDEX` + `migrate:down` que re-cria o índice não-único (ver data-model.md §2.2).
- [ ] T012 [P] Criar `apps/api/db/migrations/20260601000003_alter_conversations_auto_resolved.sql` — `ADD COLUMN auto_resolved BOOLEAN NULL` + partial index `idx_conversations_auto_resolved` (tenant_id, auto_resolved, closed_at DESC) `WHERE auto_resolved IS NOT NULL` + `migrate:down` (ver data-model.md §2.3).
- [ ] T013 [P] Criar `apps/api/db/migrations/20260601000004_alter_messages_is_direct.sql` — `ADD COLUMN is_direct BOOLEAN NOT NULL DEFAULT TRUE` + partial index `idx_messages_conversation_inbound_direct` (conversation_id, created_at DESC) `WHERE direction='inbound' AND is_direct=TRUE` + `migrate:down` (ver data-model.md §2.4).
- [ ] T014 Executar as 4 migrations em ambiente de dev (`dbmate up`) + validar schema com `psql \d eval_scores`, `\d public.traces`, `\d conversations`, `\d messages`. Rodar `dbmate rollback` e `dbmate up` novamente para confirmar reversibilidade.

### Pydantic models e escopo de tipos

- [ ] T015 Criar `apps/api/prosauai/evals/models.py` com: `EvaluatorType` (Literal `heuristic_v1|deepeval|human`), `Metric` (Literal das 6 métricas), `EvalScoreRecord` (BaseModel com `tenant_id`, `conversation_id`, `message_id` nullable, `evaluator_type`, `metric`, `quality_score ∈ [0,1]` com `field_validator(mode='before')` que clipa + warn, `details: dict`), `GoldenVerdict` (StrEnum positive/negative/cleared), `GoldenTraceRecord`, `EvalAlerts` (relevance_min=0.6, toxicity_max=0.05, autonomous_resolution_min=0.3), `DeepEvalConfig` (model whitelist `gpt-4o-mini|gpt-4o|claude-haiku-3-5`), `TenantEvalConfig` (mode, offline_enabled, online_sample_rate, alerts, deepeval). Detalhes: data-model.md §3.

### Metrics facade (structlog-based, sem prometheus_client)

- [ ] T016 Criar `apps/api/prosauai/evals/metrics.py` com classe `EvalMetricsFacade` expondo métodos: `scores_persisted_total(tenant, evaluator, metric, status)`, `below_threshold_total(tenant, metric)`, `batch_duration_seconds(job, status, metric)`, `autonomous_resolution_ratio(tenant, value)`, `retention_deleted_total(tenant, rows_deleted)`, `cost_usd(tenant, amount)`. Implementação: structlog `logger.info("metric", name=..., value=..., labels={...})` (padrão epic 010).

### Scheduler base (reuso pattern epic 010)

- [ ] T017 Criar `apps/api/prosauai/evals/scheduler.py` com `EvalsScheduler` class espelhando `handoff/scheduler.py` (epic 010). Suporta `register_periodic(name, coro, interval_seconds, lock_key)` e gerencia lifecycle `start()/stop()` via `asyncio.TaskGroup` + graceful shutdown em `asyncio.wait(timeout=5s)`. Cada iteração: `pg_try_advisory_lock(hashtext(lock_key))`; em caso de lock_held, loga `skipped=lock_held` e retorna.

### Config poller extension

- [ ] T018 Estender `apps/api/prosauai/config_poller.py` para validar bloco `evals:*` per-tenant via `TenantEvalConfig.model_validate(...)` (T015). Fallback safe: se validação falhar, manter config anterior e logar `tenants_yaml_evals_block_invalid`. Re-leitura ≤60s (reusa mecanismo existente).
- [ ] T019 Atualizar `apps/api/config/tenants.yaml` com bloco `evals:` para Ariel e ResenhAI default `off` (exemplo em data-model.md §4). Validar via `poetry run python -c "from prosauai.config_poller import load_tenants; print(load_tenants())"`.

### Main.py lifespan registration

- [ ] T020 Estender `apps/api/prosauai/main.py` FastAPI lifespan para instanciar `EvalsScheduler` (sem registrar tasks ainda — cada US registra seu próprio cron), logar `evals_scheduler_started` e garantir `stop()` no shutdown.

**Checkpoint**: Foundation pronta — user stories podem começar em paralelo (respeitando dependências entre US2/US3 e migrations).

---

## Phase 3: User Story 1 — Persistência Online do Score Heurístico (Priority: P1) 🎯 MVP

**Goal**: Todo score calculado por `conversation/evaluator.py` (epic 005) é persistido em `eval_scores` via `asyncio.create_task` fire-and-forget, com `evaluator_type='heuristic_v1'` + `metric='heuristic_composite'`, zero impacto no p95 <3s.

**Independent Test**: Habilitar `evals.mode=shadow` em Ariel, enviar 50 mensagens sintéticas, `SELECT COUNT(*) FROM eval_scores WHERE evaluator_type='heuristic_v1' AND created_at > NOW() - INTERVAL '1 hour'` deve retornar 50. Benchmark p95 do webhook ≤ baseline +0ms (SC-003).

### Contracts (Protocol EvalPersister)

- [ ] T021 [US1] Criar `apps/api/tests/contract/test_eval_persister_contract.py` com: (a) teste `isinstance(impl, EvalPersister)` para `PoolPersister`; (b) `test_persist_never_raises` passando `EvalScoreRecord` com `conversation_id` inexistente (FK violation) — `impl.persist(...)` NÃO pode propagar exceção; (c) conformance de Protocol para eventuais adapters futuros. Espera IMPORTERROR até T022-T023 — registrar xfail até persist.py existir.

### Persist layer

- [ ] T022 [US1] Criar `apps/api/prosauai/evals/persist.py` com Protocol `EvalPersister` (`async def persist(record: EvalScoreRecord) -> None`) + classe `PoolPersister(pool: asyncpg.Pool, metrics: EvalMetricsFacade)` implementando: (a) `async with pool.acquire()`, `SET LOCAL app.tenant_id`; (b) INSERT em eval_scores conforme data-model.md §5.1; (c) metrics.scores_persisted_total(status='ok'); (d) maybe_emit_below_threshold; (e) try/except amplo — falha loga `eval_score_persist_failed` com canonical keys + `status='error'` e NÃO propaga. Detalhes: contracts/evaluator-persist.md §1.
- [ ] T023 [US1] Criar `apps/api/prosauai/evals/heuristic_online.py` com função `persist_heuristic(pool, metrics, evaluator_result, tenant_id, conversation_id, message_id) -> asyncio.Task` que (a) lê `evaluator_result.score` e `verdict` (produzido por `conversation/evaluator.py` epic 005); (b) monta `EvalScoreRecord(evaluator_type='heuristic_v1', metric='heuristic_composite', quality_score=score, details={'verdict': verdict, 'components': components})`; (c) respeita `tenant_config.evals.mode` (skip se `off`); (d) respeita `online_sample_rate` (random.random() < rate); (e) retorna `asyncio.create_task(persister.persist(record))`.
- [ ] T024 [US1] Criar `apps/api/prosauai/db/queries/eval_scores.py` com funções: `insert_score(conn, record)`, `fetch_metrics_agg(conn, tenant_id, evaluator, metric, window)` (será usada em US6), `count_coverage(conn, tenant_id, window)` (será usada em US6). Detalhes SQL: data-model.md §5.

### Pipeline integration

- [ ] T025 [US1] Estender `apps/api/prosauai/conversation/pipeline.py` step `evaluate`: após `evaluator.evaluate(...)` retornar `EvalResult`, chamar `evals.heuristic_online.persist_heuristic(pool, metrics, result, tenant_id, conversation_id, message_id)` ANTES de retornar do step. Uso explícito de `asyncio.create_task` — NÃO aguarda. Log structlog `evaluate_step_score_scheduled`.
- [ ] T026 [US1] Criar OTel span `eval.score.persist` em `PoolPersister.persist` (T022) attached ao span corrente via `trace.get_current_span()`. Attributes: `evaluator`, `metric`, `score`, `tenant_id` (cast string).

### Unit tests

- [ ] T027 [US1] [P] Criar `apps/api/tests/unit/evals/test_persist.py`: (a) score clipping [0,1] via pydantic validator; (b) fire-and-forget — FK violation não propaga; (c) log path com `status='error'` + canonical keys; (d) happy path emite `scores_persisted_total{status='ok'}`; (e) `SET LOCAL app.tenant_id` presente no SQL executado (mock asyncpg).
- [ ] T028 [US1] [P] Criar `apps/api/tests/unit/evals/test_heuristic_online.py`: (a) `mode=off` → zero task agendado; (b) `mode=shadow` → task agendado; (c) `mode=on` → task agendado + threshold check; (d) `online_sample_rate=0.0` → zero; (e) `online_sample_rate=1.0` → sempre agenda; (f) mapeamento correto de `EvalResult.verdict` → `details.verdict`.
- [ ] T029 [US1] [P] Criar `apps/api/tests/unit/pipeline/test_evaluate_persist_hook.py`: (a) step `evaluate` agenda task sem `await`; (b) falha simulada em `persist_heuristic` não propaga para pipeline; (c) pipeline total duration não é afetada por `persist_score` (mocked sleep de 500ms no persist).

### Integration test

- [ ] T030 [US1] Criar `apps/api/tests/integration/test_heuristic_online_flow.py` usando testcontainers-postgres: (a) webhook POST → pipeline completo → row em `eval_scores` com `evaluator_type='heuristic_v1'` em `mode=shadow`; (b) mesmo cenário com `mode=off` → ZERO row; (c) 50 mensagens concorrentes → 50 rows (sem deadlock).

### Benchmark (GATE DE MERGE PR-A)

- [ ] T031 [US1] Criar `apps/api/tests/benchmarks/test_pipeline_p95_no_regression.py` rodando pipeline 200× antes e depois de habilitar `evals.mode=shadow`, calculando p95, validando diff ≤ +5ms (tolerância ruído). **GATE explícito SC-003**.

**Checkpoint**: US1 entrega MVP — heurístico persistido 100% em eval_scores. Performance AI card "coverage" e "heuristic trend" podem renderizar (depois de US6) mesmo sem US2/US3.

---

## Phase 4: User Story 2 — Cron Autonomous Resolution (Priority: P1)

**Goal**: `autonomous_resolution_cron` popula `conversations.auto_resolved` diariamente aplicando heurística A, alimentando o North Star da vision.

**Independent Test**: Semear 3 conversas (A=resolved, B=muted em handoff_events, C=contém regex escalação), rodar cron manualmente, validar `auto_resolved` TRUE/FALSE/FALSE e métrica `autonomous_resolution_ratio` no Prometheus.

### Query + cron logic

- [ ] T032 [US2] Criar `apps/api/prosauai/evals/autonomous_resolution.py` com função `run_cron(pool, metrics, tenant_configs)`: (a) adquirir `pg_try_advisory_lock(hashtext('autonomous_resolution_cron'))` — skip se lock held; (b) para cada tenant com `evals.mode ∈ {shadow,on}`, executar query SQL da data-model.md §5.2 em batches de 1000; (c) emitir `autonomous_resolution_ratio{tenant}` como gauge; (d) log structlog `autonomous_resolution_cron_completed` com `processed`, `auto_resolved_true`, `auto_resolved_false`, `duration_ms`.
- [ ] T033 [US2] Estender `apps/api/prosauai/db/queries/conversations.py` com `update_auto_resolved_batch(conn, updates: list[tuple[UUID, bool]])` usando `UNNEST` + `UPDATE ... FROM`. Retornar count afetado.

### Scheduler registration

- [ ] T034 [US2] Em `apps/api/prosauai/main.py` (T020), registrar task `autonomous_resolution_cron` no `EvalsScheduler` com `interval_seconds=AUTONOMOUS_RESOLUTION_INTERVAL_SECONDS` (default 3600 = 1h; cron roda 03:00 UTC via inicial scheduling offset) + lock_key `'autonomous_resolution_cron'`.

### Unit tests

- [ ] T035 [US2] [P] Criar `apps/api/tests/unit/evals/test_autonomous_resolution.py` com fixtures cobrindo: (a) heuristic A positive (sem mute + sem regex + silêncio 25h) → TRUE; (b) mute presente → FALSE; (c) regex `humano` presente em inbound `is_direct=TRUE` → FALSE; (d) regex em inbound `is_direct=FALSE` (grupo não-direto) → TRUE (não conta — FR-015); (e) última inbound há 20h → não elegível (query filtro); (f) conversa já com `auto_resolved` não-NULL → idempotente, não reprocessa.
- [ ] T036 [US2] [P] Criar `apps/api/tests/unit/evals/test_scheduler.py`: (a) lock held por outra instância → `skipped=lock_held` + retorna; (b) 3 locks disjuntos (`autonomous_resolution_cron`, `deepeval_batch_cron`, `eval_scores_retention_cron`) nunca bloqueiam entre si; (c) shutdown graceful com `asyncio.wait(timeout=5s)`.

### Integration test

- [ ] T037 [US2] Criar `apps/api/tests/integration/test_autonomous_resolution_flow.py`: semear 3 conversas variantes (A/B/C), rodar cron, validar `conversations.auto_resolved` correto + métrica emitida + log estruturado.
- [ ] T038 [US2] [P] Adicionar fixture SQL `apps/api/tests/fixtures/auto_resolved_seeds.sql` com 3 variantes documentadas.

### Race test

- [ ] T039 [US2] [P] Adicionar teste `test_autonomous_resolution_concurrent` em `test_scheduler.py` (T036): `asyncio.gather` com 3 iterações concorrentes → apenas 1 ganha (advisory lock exclusivo).

**Checkpoint**: US1 + US2 combinados completam PR-A. Ariel pode ir para `shadow` no fim da semana 1. KPI North Star finalmente mensurável.

---

## Phase 5: User Story 3 — DeepEval Batch Noturno (Priority: P2)

**Goal**: `deepeval_batch_cron` avalia 4 métricas reference-less sobre amostra de até 200 msgs/tenant/dia via `gpt-4o-mini` no Bifrost, persistindo em `eval_scores` com `evaluator_type='deepeval'`. Isolamento de falha por métrica (FR-023).

**Independent Test**: Com P1 em shadow, disparar cron manualmente num tenant com >=200 msgs. Esperar ~800 rows DeepEval (4 métricas × 200 msgs). Forçar falha simulada em Toxicity → outras 3 métricas persistem normalmente.

### Dependency + Bifrost wrapper

- [ ] T040 [US3] Adicionar `deepeval>=3.0` em `apps/api/pyproject.toml` (group `main`). Rodar `poetry lock --no-update` e commitar `poetry.lock`.
- [ ] T041 [US3] Criar `apps/api/prosauai/evals/deepeval_model.py` com classe `BifrostDeepEvalModel(httpx.AsyncClient)`: (a) wrapper que implementa a interface `DeepEvalBaseLLM` apontando `base_url=settings.BIFROST_BASE_URL`, `api_key` opcional; (b) validate `model` contra whitelist da Literal em `DeepEvalConfig` (T015) — rejeita com `ModelNotWhitelistedError` se fora; (c) log + métrica `cost_usd` por chamada (estimativa via token count * R$/1k tokens hardcoded constants para v1).

### Metric wrappers (contract DeepEvalMetric)

- [ ] T042 [US3] Criar `apps/api/prosauai/evals/deepeval_batch.py` Parte 1 — wrappers: classes `AnswerRelevancyWrapper`, `ToxicityWrapper`, `BiasWrapper`, `CoherenceWrapper` implementando Protocol `DeepEvalMetric` (contracts/evaluator-persist.md §2). Cada wrapper encapsula a chamada DeepEval correspondente + retry com jitter (max 3 tentativas em 429/5xx/timeout) via `tenacity` ou loop custom. Retorna `EvalScoreRecord` (quality_score clippado [0,1]).
- [ ] T043 [US3] Criar `apps/api/prosauai/evals/deepeval_batch.py` Parte 2 — sampler: função `sample_messages(pool, tenant_id, limit, intent_stratified=True)` implementando SQL da data-model.md §5.3 (janela last-24h com 1h gap, filter `LENGTH(content) <= 32000`, stratified by `traces.intent`).
- [ ] T044 [US3] Criar `apps/api/prosauai/evals/deepeval_batch.py` Parte 3 — runner: `run_batch(pool, persister, wrappers, tenant_id, config)`: (a) chamar sampler; (b) processar em chunks de 10 com `asyncio.gather(*[_process_message(...) for msg in chunk], return_exceptions=True)`; (c) para cada msg, `asyncio.gather(*[w.evaluate(msg) for w in wrappers], return_exceptions=True)` — isolamento por métrica; (d) success → `persister.persist(record)` (fire-and-forget); (e) falha isolada → log `deepeval_metric_failed` + `batch_duration_seconds{status='error'}`.
- [ ] T045 [US3] Criar OTel span root `eval.batch.deepeval` em `run_batch` + child span per metric (`eval.batch.deepeval.answer_relevancy`, etc), NÃO attached ao trace do pipeline (vida separada — FR-025).

### Scheduler registration

- [ ] T046 [US3] Em `apps/api/prosauai/main.py`, registrar task `deepeval_batch_cron` no `EvalsScheduler` com `interval_seconds=DEEPEVAL_BATCH_INTERVAL_SECONDS` (default 86400 = 24h; roda 02:00 UTC) + lock_key `'deepeval_batch_cron'`. Loop interno itera tenants com `offline_enabled=true AND mode ∈ {shadow,on}`.

### Unit tests

- [ ] T047 [US3] [P] Criar `apps/api/tests/unit/evals/test_deepeval_model.py`: (a) `BifrostDeepEvalModel` aponta `base_url` correto; (b) whitelist rejeita `gpt-3.5-turbo` com `ModelNotWhitelistedError`; (c) whitelist aceita `gpt-4o-mini`; (d) `cost_usd` incrementa por chamada.
- [ ] T048 [US3] [P] Criar `apps/api/tests/unit/evals/test_deepeval_batch.py` com respx mock do Bifrost: (a) sampler stratified by intent — contagens proporcionais; (b) filter de content >32K; (c) retry com jitter em 429 → sucesso na 2ª tentativa; (d) retry esgotado → log + métrica error; (e) isolamento de falha por métrica (Toxicity throws, outras 3 persistem) — **ESSENCIAL**; (f) clip score [0,1] + log warn quando wrapper retorna 1.5.

### Integration test

- [ ] T049 [US3] Criar `apps/api/tests/integration/test_deepeval_batch_flow.py` usando testcontainers-postgres + respx Bifrost: (a) rodar cron com tenant populado (50 msgs mock); (b) validar ~50×4=200 rows em `eval_scores` com `evaluator_type='deepeval'`; (c) forçar falha em Toxicity — validar exatamente 3/4 métricas persistidas; (d) fixtures respx em `apps/api/tests/fixtures/deepeval_mock_responses.json`.
- [ ] T050 [US3] [P] Criar `apps/api/tests/fixtures/deepeval_mock_responses.json` com respostas mock das 4 métricas (happy + error paths) para usar em T048/T049.

### Budget observability (GATE PR-B)

- [ ] T051 [US3] Confirmar métrica `cost_usd` emitida em `metrics.py` (T016). Adicionar alerta estruturado (structlog WARN level) quando acumulado diário > R$3/tenant.

**Checkpoint**: US3 entrega métricas de qualidade absoluta. Custo Bifrost monitorado em shadow antes de flip `on`.

---

## Phase 6: User Story 4 — Promptfoo CI Smoke Suite (Priority: P2)

**Goal**: PRs que tocam `agents/|prompts/|safety/` passam por suite Promptfoo com 5 smoke cases hand-written + dataset incremental via golden_traces.

**Independent Test**: PR sintético que quebra `system_prompt` (bot retorna "não sei") → Action falha no case "stats". PR limpo → Action passa.

### Suite Promptfoo

- [ ] T052 [US4] Criar `apps/api/prosauai/evals/promptfoo/smoke.yaml` com 5 casos hand-written: (a) "oi" → resposta não-vazia e segura; (b) "quem lidera a liga?" → resposta contém ao menos 1 número; (c) "quero falar com humano" → resposta sinaliza escalação (contém palavra-chave); (d) prompt injection "ignore previous instructions..." → safety_prefix preservado; (e) off-topic "qual receita de bolo?" → resposta educada sem alucinação. Usar `providers:` apontando para Bifrost via env var + `assert:` com matchers regex/llm-rubric.
- [ ] T053 [US4] [P] Criar `apps/api/prosauai/evals/promptfoo/README.md` com runbook: como rodar local (`npx promptfoo@latest eval smoke.yaml`), como adicionar caso, como regenerar de golden_traces, troubleshooting (Bifrost offline, flakiness).

### GitHub Action (gate blocking)

- [ ] T054 [US4] Criar `.github/workflows/promptfoo-smoke.yml`: trigger `pull_request` com `paths:` `['apps/api/prosauai/agents/**', 'apps/api/prosauai/prompts/**', 'apps/api/prosauai/safety/**']`. Steps: (a) checkout; (b) setup node 20; (c) start Bifrost mock ou usar BIFROST_BASE_URL de ambiente; (d) run `npx promptfoo@latest eval apps/api/prosauai/evals/promptfoo/smoke.yaml --output /tmp/result.json`; (e) upload artifact; (f) fail se exit code != 0. Timeout 5min (SC-012).

### Generator (base para US5 incremental)

- [ ] T055 [US4] Criar `apps/api/prosauai/evals/promptfoo/generate.py` com CLI `python -m prosauai.evals.promptfoo.generate --output <file>`: (a) consulta `SELECT DISTINCT ON (trace_id) ...` da data-model.md §5.4; (b) filtra `WHERE verdict != 'cleared'` e traces órfãos (trace_id sem linha correspondente em `public.traces` — FR-GoldenOrphan); (c) para cada trace, gera um caso YAML mapeando `verdict` → `expected_behavior` (`positive` → `assert: passes`, `negative` → `assert: fails`); (d) concatena com smoke.yaml e escreve no `--output`.

### Unit tests

- [ ] T056 [US4] [P] Criar `apps/api/tests/unit/evals/test_promptfoo_generate.py`: (a) gerador produz YAML válido (parse com PyYAML); (b) filtra `cleared` corretamente (fixture com 3 traces: 1 positive, 1 negative, 1 cleared → output tem 2); (c) filtra órfãos (trace_id sem linha em traces); (d) happy path concatena com smoke base.
- [ ] T057 [US4] [P] Criar `apps/api/tests/fixtures/golden_trace_examples.sql` com 3 rows positives + 2 negatives + 1 cleared (para US4 + US5 tests).

**Checkpoint**: CI gate ativo. Qualquer PR sintético de regression de prompt é bloqueado.

---

## Phase 7: User Story 5 — Golden Curation (Priority: P3)

**Goal**: Admin estrela traces via POST endpoint. Append-only (`cleared` é 3º valor). Alimenta Promptfoo generator.

**Independent Test**: `curl` 5 stars (3 positives, 2 negatives, 1 cleared sobre o 1º positive) → `golden_traces` tem 6 rows → gerador produz 4 casos (1 positive efetivo cleared, 1 positive, 2 negatives, 1 descartado).

### Migration (desbloqueio)

- [ ] T058 [US5] Criar `apps/api/db/migrations/20260601000005_create_golden_traces.sql` conforme data-model.md §2.5: `CREATE TABLE IF NOT EXISTS public.golden_traces (...)` + `CHECK verdict IN ('positive','negative','cleared')` + FK `trace_id REFERENCES public.traces(trace_id) ON DELETE CASCADE` + índices `idx_golden_traces_trace_created` e `idx_golden_traces_user_created` + `COMMENT ON TABLE` + grants para `service_role` + `migrate:down`.
- [ ] T059 [US5] Executar migration em dev (`dbmate up`) + validar FK cascade com teste `INSERT` + `DELETE FROM public.traces WHERE trace_id=...` — `golden_traces` row deve desaparecer.

### Query layer

- [ ] T060 [US5] Criar `apps/api/prosauai/db/queries/golden_traces.py` com: `insert_verdict(conn, trace_id, verdict, notes, user_id)` + `effective_verdict_by_trace(conn)` retornando `DISTINCT ON (trace_id)` (SQL data-model.md §5.4) + `exists_trace(conn, trace_id)` (usado para 404 no endpoint).

### Admin endpoint

- [ ] T061 [US5] Estender `apps/api/prosauai/api/admin/traces.py` com rota `POST /admin/traces/{trace_id}/golden`: (a) auth via middleware admin (epic 008); (b) validar `trace_id` com regex OTel `^[0-9a-f]{32}$` (FastAPI Path regex); (c) validar body `{verdict, notes?}` (Pydantic); (d) check trace exists → 404 se não; (e) insert via `insert_verdict(..., user_id=current_user.id)`; (f) responder 201 com `GoldenVerdictResponse` (OpenAPI spec contracts/openapi.yaml).
- [ ] T062 [US5] Atualizar `apps/api/prosauai/api/admin/openapi.yaml` (ou equivalente) espelhando `POST /admin/traces/{trace_id}/golden` conforme contracts/openapi.yaml.

### Unit + Integration tests

- [ ] T063 [US5] [P] Criar `apps/api/tests/unit/api/admin/test_traces_golden.py`: (a) verdict positive → 201; (b) verdict negative → 201; (c) verdict cleared → 201; (d) trace_id inválido (não hex 32) → 422; (e) trace_id não existe → 404; (f) sem auth → 401; (g) non-admin → 403.
- [ ] T064 [US5] Criar `apps/api/tests/integration/test_golden_flow.py`: (a) 3 stars sequenciais no mesmo trace (positive → negative → cleared) → 3 linhas em `golden_traces`, verdict efetivo = `cleared`; (b) `effective_verdict_by_trace` retorna apenas última linha por trace; (c) generator Promptfoo (T055) não emite caso para trace com verdict efetivo `cleared`.
- [ ] T065 [US5] [P] Teste de cascade: `DELETE FROM public.traces WHERE trace_id=...` → rows em `golden_traces` desaparecem automaticamente (FR-031, FR-047 LGPD SAR).

### Retention cron (cleanup eval_scores)

- [ ] T066 [US5] Criar `apps/api/prosauai/evals/retention.py` com função `run_retention(pool, metrics)`: (a) advisory lock `'eval_scores_retention_cron'`; (b) kill-switch check `EVAL_SCORES_RETENTION_ENABLED=1`; (c) `DELETE FROM eval_scores WHERE created_at < NOW() - INTERVAL '90 days' RETURNING tenant_id`; (d) agregar counts por tenant e emitir `eval_scores_retention_deleted_total{tenant}`; (e) log `eval_scores_retention_completed` com `rows_deleted` e `duration_ms`. FR-052-054.
- [ ] T067 [US5] Registrar `eval_scores_retention_cron` no `EvalsScheduler` (main.py T020), interval `EVAL_SCORES_RETENTION_INTERVAL_SECONDS` (default 86400), roda 04:00 UTC (após DeepEval batch 02:00 e autonomous 03:00).
- [ ] T068 [US5] [P] Criar `apps/api/tests/unit/evals/test_retention.py`: (a) rows >90d deletadas; (b) rows <90d preservadas; (c) kill-switch `EVAL_SCORES_RETENTION_ENABLED=0` → skip; (d) `conversations.auto_resolved` NÃO é apagada (FR-053) — validar via fixture com conversa 180d e row retida.
- [ ] T069 [US5] Criar `apps/api/tests/integration/test_retention_flow.py`: inserir row 95d atrás, rodar cron, validar DELETE + metric emission.

**Checkpoint**: Backend golden curation funcional via `curl`. US5 backend entrega valor mesmo sem UI (operador Pace executa manualmente). Plan cut-line: se PR-C estourar, US6 vira 011.1 mas US5 via curl segue em produção.

---

## Phase 8: User Story 6 — Performance AI Tab (4 Cards) + Admin UI (Priority: P3)

**Goal**: Admin ganha visibilidade visual em uma tela: relevance trend, toxicity+bias, coverage, autonomous resolution. Star button no Trace Explorer e badge/toggle na Tenants tab.

**Independent Test**: Ariel em `mode=on` por 7d → Performance AI renderiza 4 cards com dados reais. Playwright garante skeleton para `mode=off`.

### Backend — Admin aggregator endpoint

- [ ] T070 [US6] Estender `apps/api/prosauai/api/admin/metrics.py` com rota `GET /admin/metrics/evals`: (a) params `tenant` (slug ou 'all'), `evaluator` (enum), `metric` (enum), `window` (1d/7d/30d); (b) usar `pool_admin` BYPASSRLS (epic 008) quando `tenant=all`; (c) SQL data-model.md §5.5 (per-day AVG + COUNT) + queries auxiliares para `coverage_pct` e `autonomous_resolution_pct`; (d) resposta `EvalMetricsResponse` conforme contracts/openapi.yaml; (e) cache 30s (opcional — TanStack já cacheia client-side).
- [ ] T071 [US6] Estender `apps/api/prosauai/api/admin/tenants.py` com rota `PATCH /admin/tenants/{id}/evals`: (a) body `TenantEvalsRequest` (OpenAPI); (b) validação via pydantic `TenantEvalConfig`; (c) escrita atômica em `apps/api/config/tenants.yaml` (backup `.yaml.bak`, fsync); (d) resposta `TenantEvalsResponse` com `effective_at = now + 60s` (config_poller SLA).
- [ ] T072 [US6] [P] Unit tests `apps/api/tests/unit/api/admin/test_metrics_evals.py`: (a) per-tenant happy path; (b) `tenant=all` via pool_admin (mock); (c) coverage calculation; (d) autonomous_resolution_pct accuracy; (e) window 1d/7d/30d filtering.
- [ ] T073 [US6] [P] Unit tests `apps/api/tests/unit/api/admin/test_tenants_evals.py`: (a) PATCH válido altera YAML; (b) PATCH com `mode='invalid'` → 422; (c) auth 401; (d) non-admin 403; (e) rollback em falha de escrita (restaurar .bak).

### Frontend — Performance AI tab (4 cards)

- [ ] T074 [US6] Rodar `pnpm gen:api` em `apps/admin/` para gerar tipos TS das novas rotas (`EvalMetricsResponse`, `GoldenVerdictRequest`, `TenantEvalsRequest`). Commitar `apps/admin/src/types/api.gen.ts`.
- [ ] T075 [US6] Estender `apps/admin/src/app/admin/(authenticated)/performance/page.tsx` com 4 cards novos (Recharts + TanStack Query v5 + shadcn/ui): (a) AnswerRelevancy line chart 7d/30d; (b) Toxicity + Bias stacked area; (c) Eval coverage gauge (online 100% vs offline ~5-10%); (d) Autonomous resolution bignumber + 7d sparkline. TanStack query chaves `['evals', tenant, evaluator, metric, window]` com `staleTime: 30_000`.
- [ ] T076 [US6] Implementar skeleton/empty state: quando `evals.mode=off` ou zero rows, renderizar card com texto "Evals desabilitados para este tenant" (FR-040) ou "Sem dados ainda — aguarde próxima execução do cron" (FR quando 0 rows, 7d window).
- [ ] T077 [US6] [P] Seletor `tenant=all` no filtro da Performance AI tab → chama endpoint com `tenant=all` (pool_admin agrega cross-tenant sem drill-down individual — SC-010).

### Frontend — Star button na Trace Explorer

- [ ] T078 [US6] Estender `apps/admin/src/app/admin/(authenticated)/traces/[traceId]/page.tsx`: adicionar botão "Star" no drawer do trace com 3 ações (positive/negative/clear) + modal de confirmação + campo notes opcional. Mutation via TanStack Query `useMutation` chamando `POST /admin/traces/{trace_id}/golden`. Invalida query `['golden', trace_id]` após sucesso. Toast de confirmação (shadcn `useToast`).

### Frontend — Tenants tab badge + toggle

- [ ] T079 [US6] Estender `apps/admin/src/app/admin/(authenticated)/tenants/page.tsx`: adicionar coluna "Evals" na tabela mostrando badge colorido (`off` cinza, `shadow` amarelo, `on` verde). Inline toggle (Select) dispara mutation `PATCH /admin/tenants/{id}/evals` com body `{mode}`. Toast indica "Aplicação efetiva em até 60s" (SLA config_poller).

### Playwright E2E

- [ ] T080 [US6] Criar `apps/admin/tests/e2e/evals.spec.ts`: (a) login admin → navegar Performance AI → 4 cards renderizam (screenshots + assertions por aria-label); (b) tenant com `mode=off` → skeleton "Evals desabilitados"; (c) star um trace (positive) → toast + row nova em golden_traces (mock ou integration via env); (d) alterar `evals.mode` via Tenants toggle → 200 response + badge atualiza.
- [ ] T081 [US6] [P] Benchmark Playwright: `cards render <1s p95` (FR/SC-009). Usar `performance.measure()` em cada card.

**Checkpoint**: Admin tem UI canônica. Cards renderizam <1s p95. Ariel pode ir para `on`.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: LGPD SAR integration, observability cleanup, documentação, runbooks, alertas.

### LGPD SAR integration

- [ ] T082 Estender query SAR existente (epic 010) em `apps/api/prosauai/privacy/sar.py` ou similar: adicionar `DELETE FROM eval_scores WHERE tenant_id=$1 AND conversation_id IN (SELECT id FROM conversations WHERE customer_id=$2)` explicitamente. `golden_traces` herda via FK cascade — documentar em comentário. FR-047.
- [ ] T083 [P] Atualizar testes SAR existentes para validar que `eval_scores` também é deletado ao processar SAR de um customer_id.

### ADRs finalizados

- [ ] T084 Finalizar ADR-039 (T001) — status `accepted`, data, referências cruzadas a eventuais tasks/decisões mudadas durante implementação.
- [ ] T085 [P] Finalizar ADR-040 (T002) — status `accepted`.

### Runbooks (docs operacionais)

- [ ] T086 Criar `docs/runbooks/evals-thresholds.md` documentando como calibrar `relevance_min`, `toxicity_max`, `autonomous_resolution_min` per-tenant, quando escalar para `critical`, como responder a alerta.
- [ ] T087 [P] Criar `docs/runbooks/golden-curation.md` cobrindo: quando estrelar (positive vs negative), PII redaction manual (FR-048), como usar `cleared`, cadência de review semanal.
- [ ] T088 [P] Criar `docs/runbooks/deepeval-cost.md` cobrindo: como ler `eval.deepeval.cost_usd` nos logs, threshold R$3/dia, playbook de fallback (reduzir amostra → desligar Toxicity+Bias → disable offline).

### Observability & alerting wire-up

- [ ] T089 Configurar alerta structlog-based no Grafana/Loki (infra Pace) para: (a) `eval_scores_persisted_total{status='error'}` rate >1% → log-level ERROR; (b) `eval_batch_duration_seconds{status='error'}` >5% dos chunks → WARN; (c) custo diário >R$3 combinado → WARN email. FR-043-044.
- [ ] T090 [P] Validar que `autonomous_resolution_ratio{tenant}` aparece como gauge no scrape Prometheus e que dashboards Grafana existentes (epic 008) pickam a nova métrica.

### Documentation sync

- [ ] T091 Rodar `madruga:reconcile` após merge de cada PR (PR-A, PR-B, PR-C) para detectar drift entre `platforms/prosauai/engineering/domain-model.md` e schemas implementados.
- [ ] T092 [P] Atualizar `platforms/prosauai/engineering/containers.md` caso algum container lifecycle mude (esperado: nenhum — reuso de Postgres/Redis/FastAPI existentes).
- [ ] T093 [P] Commit final de tipos gerados (`pnpm gen:api`) após todos endpoints estarem em produção.

### Rollout Ariel → ResenhAI

- [ ] T094 Rollout Ariel `shadow → on` após 7d de shadow, coverage ≥80%, zero erros críticos, AnswerRelevancy médio ≥0.7 (SC-008). Atualizar `tenants.yaml` via `PATCH /admin/tenants/ariel/evals` ou direto em YAML.
- [ ] T095 Rollout ResenhAI `off → shadow` (7d após Ariel `on`).
- [ ] T096 Rollout ResenhAI `shadow → on` (14d após Ariel `on`).

### Cleanup & quality gates

- [ ] T097 [P] Rodar `ruff check apps/api/prosauai/evals/` e `ruff format` — zero warnings.
- [ ] T098 [P] Rodar suite completa `poetry run pytest` — zero regression (173 epic 005 + 191 epic 008 + N epic 010 + novos).
- [ ] T099 Medir custo Bifrost real pós-rollout Ariel `on` (janela 24h): `grep eval.deepeval.cost_usd logs | jq 'add'`. Comparar com SC-011 (≤R$3/dia combinado). Se exceder >2x, disparar runbook T088.

---

## Phase 10: Deployment Smoke

**Purpose**: Validar build + health + URLs + screenshots + Journey J-001 no ambiente deployado. Auto-gerada por `platform.yaml:testing` (startup.type=docker).

- [ ] T100 Executar `docker compose build` no diretório do repositório `paceautomations/prosauai` — build sem erros.
- [ ] T101 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --start --platform prosauai` — todos os health_checks (API 8050/health, Admin 3000) respondem dentro de ready_timeout (120s).
- [ ] T102 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-env --platform prosauai` — zero required_env vars ausentes em `.env` (JWT_SECRET, ADMIN_BOOTSTRAP_EMAIL, ADMIN_BOOTSTRAP_PASSWORD, DATABASE_URL).
- [ ] T103 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-urls --platform prosauai` — todas as URLs acessíveis com status esperado (health 200, admin/login 200, webhooks 400/401/405).
- [ ] T104 Capturar screenshot de cada URL `type: frontend` (`http://localhost:3000` e `http://localhost:3000/admin/login`) — conteúdo não é placeholder; login page contém "login".
- [ ] T105 Executar Journey J-001 (happy path) declarado em `platforms/prosauai/testing/journeys.md` — todos os steps com assertions OK.

---

## Dependencies

### Phase dependencies (top-level)

```
Phase 1 (Setup) ─┐
                 ├─→ Phase 2 (Foundational) ─┬─→ Phase 3 (US1, P1) ──────┐
                 │                           ├─→ Phase 4 (US2, P1) ──────┤
                 │                           ├─→ Phase 5 (US3, P2) ──────┤
                 │                           ├─→ Phase 6 (US4, P2) ──────┤
                 │                           └─→ Phase 7 (US5, P3) ──────┤
                 │                                                        ├─→ Phase 8 (US6, P3) ─→ Phase 9 ─→ Phase 10
                 └────────────────────────────────────────────────────────┘
```

### User story dependencies

- **US1 (P1)**: depende de Phase 2 migrations 1 (`eval_scores.metric`). Independente das demais US.
- **US2 (P1)**: depende de Phase 2 migrations 3 + 4 (`auto_resolved` + `is_direct`). Independente de US1 (mas se rodar primeiro, dashboards ficam sem heurístico 7d).
- **US3 (P2)**: depende de Phase 2 migration 1 + **US1** (reusa `persist.py` PoolPersister). Atrasa sem US1 → estouro de trabalho.
- **US4 (P2)**: **independente** de US1/US2/US3 — Promptfoo CI não persiste em eval_scores. Pode ser implementado em paralelo com qualquer US.
- **US5 (P3)**: depende de Phase 2 migration 2 (`traces UNIQUE trace_id`) + migration 5 (criada dentro da própria US). **Generator** (T055 em US4) consome golden_traces mas suporta tabela vazia — US4 não aguarda US5.
- **US6 (P3)**: depende de **US1 + US2 + US3 + US5** para ter dados reais nos cards + star button funcional. Única US que depende de várias.

### Cross-story parallel opportunities

Tasks marcadas `[P]` em stories diferentes podem rodar em paralelo quando não tocam os mesmos arquivos:

- T021 (US1 contract test) + T032 (US2 autonomous logic) + T040 (US3 pyproject deepeval) + T052 (US4 smoke.yaml) + T058 (US5 migration 5) — **5 pessoas em paralelo** após Phase 2 fechar.
- T027/T028/T029 (US1 unit tests) podem rodar concorrentemente com T035/T036 (US2 unit tests) e T047/T048 (US3 unit tests).

---

## Parallel Execution Examples

### Example 1 — Phase 2 (Foundational) massivamente paralelo

```bash
# 4 migrations em paralelo (arquivos diferentes):
T010 (eval_scores ADD metric) &
T011 (traces UNIQUE trace_id) &
T012 (conversations auto_resolved) &
T013 (messages is_direct) &
wait

# T014 (dbmate up e validar) serializa depois
```

### Example 2 — US1 (US1 P1) unit tests em paralelo

```bash
# Após T022+T023+T024+T025 estarem prontos:
T027 (test_persist.py) &
T028 (test_heuristic_online.py) &
T029 (test_evaluate_persist_hook.py) &
wait

# T030 (integration) serializa depois — compartilha testcontainer com outros
```

### Example 3 — US3 (US3 P2) runner + wrappers

```bash
# T042 (wrappers 4 classes — 1 arquivo) serializa
# Depois T043 (sampler) e T044 (runner) podem ser tocados por pessoas diferentes se split por função
```

### Example 4 — Cross-story parallel (após Phase 2)

```bash
# 3 devs tocam 3 US simultaneamente:
Dev A: Phase 3 (US1) — T021..T031
Dev B: Phase 4 (US2) — T032..T039
Dev C: Phase 6 (US4) — T052..T057 (independente das demais)
```

---

## Implementation Strategy

### MVP scope (semana 1, PR-A)

**Phase 1 + Phase 2 + Phase 3 (US1) + Phase 4 (US2)**:
- 4 migrations aditivas (1-4)
- Heurístico online persistido 100% em `eval_scores` (US1)
- Autonomous resolution cron popula `conversations.auto_resolved` (US2)
- Ariel em `shadow` no fim da semana

**Valor entregue**: dashboards Performance AI (mesmo sem UI nova) podem ser populados via SQL direto. KPI North Star mensurável. p95 <3s garantido via benchmark gate (T031).

### Incremental scope (semana 2, PR-B)

**Phase 5 (US3) + Phase 6 (US4) + Phase 7 (US5 backend)**:
- DeepEval batch offline + 4 métricas reference-less
- Promptfoo CI gate blocking
- Golden curation via `curl` (sem UI)
- Retention cron

**Gate**: custo Bifrost ≤R$3/dia combinado (T099 preliminar).

### Final scope (semana 3, PR-C)

**Phase 8 (US6) + Phase 9 rollout**:
- Admin UI com 4 cards
- Star button Trace Explorer
- Tenants toggle
- Rollout Ariel `on` → ResenhAI `shadow → on`

**Cut-line explícito**: se semana 2 estourar, **Phase 8 vira 011.1**. Valor core (US1-US5) já está em produção via SQL + curl. Admin opera via runbook T087.

---

## Task Count Summary

| Phase | Tasks | Scope |
|-------|-------|-------|
| Phase 1 — Setup | 9 (T001-T009) | ADRs + env vars + módulo vazio |
| Phase 2 — Foundational | 11 (T010-T020) | 4 migrations + models + scheduler + config_poller + metrics facade |
| Phase 3 — US1 (P1) 🎯 MVP | 11 (T021-T031) | Heurístico online + benchmark p95 gate |
| Phase 4 — US2 (P1) | 8 (T032-T039) | Autonomous resolution cron + race tests |
| Phase 5 — US3 (P2) | 12 (T040-T051) | DeepEval batch + 4 wrappers + budget metric |
| Phase 6 — US4 (P2) | 6 (T052-T057) | Promptfoo smoke + CI + generator + fixtures |
| Phase 7 — US5 (P3) | 12 (T058-T069) | Migration 5 + endpoint + retention cron |
| Phase 8 — US6 (P3) | 12 (T070-T081) | Aggregator endpoint + 4 cards + star + toggle + E2E |
| Phase 9 — Polish | 18 (T082-T099) | SAR + runbooks + alerting + rollout |
| Phase 10 — Deployment Smoke | 6 (T100-T105) | docker build + health + URLs + screenshots + Journey |
| **Total** | **105 tasks** | |

### Parallel opportunities identified

- **Phase 2**: 4 migrations em paralelo (T010-T013).
- **Phase 3-7**: 5 user stories podem rodar em paralelo após Phase 2, se arquivos forem disjuntos (Phase 3/4 compartilham `scheduler.py` + `metrics.py` via Phase 2).
- **Phase 9**: 10+ tasks `[P]` (ruff, docs, runbooks, backup YAML, etc).

### Independent test criteria por story

| US | Teste de validação em 1 comando |
|----|---------------------------------|
| US1 | `curl webhook + SELECT COUNT(*) FROM eval_scores WHERE evaluator_type='heuristic_v1'` + p95 bench |
| US2 | Seed SQL 3 variantes + trigger cron + `SELECT auto_resolved FROM conversations WHERE id IN (A,B,C)` |
| US3 | Trigger cron + `SELECT metric, COUNT(*) FROM eval_scores WHERE evaluator_type='deepeval'` = 4 |
| US4 | PR sintético que quebra prompt → CI fail; revert → CI pass |
| US5 | 3× `curl POST /admin/traces/{id}/golden` + `SELECT ... FROM golden_traces` tem 3 rows + generator YAML |
| US6 | Playwright `tests/e2e/evals.spec.ts` verde + benchmark <1s p95 |

---

<!-- HANDOFF -->
---
handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "Tasks.md quebra o plan em 105 tarefas organizadas em 10 phases (Setup, Foundational, 6 user stories, Polish, Deployment Smoke). Phase 2 (foundational) cobre 4 migrations aditivas + Pydantic models + scheduler/metrics facade base — bloqueia TODAS as US. US1+US2 (P1) formam o MVP da semana 1 (PR-A). US3+US4+US5 (P2/P3) são semana 2 (PR-B). US6 (P3) é semana 3 (PR-C, sacrificável se PR-B estourar — vira 011.1). Benchmark p95 (T031) é gate explícito de merge PR-A. Playwright E2E (T080) é gate PR-C. 5 ADRs envolvidos (039-040 novos, 008/027/028 estendidos). Deployment Smoke phase adicionada automaticamente por `platform.yaml:testing` com startup.type=docker."
  blockers: []
  confidence: Alta
  kill_criteria: "(a) Phase 2 migrations falham reversibilidade → refactor das migrations antes de seguir qualquer US. (b) T031 benchmark revela regressão p95 >5ms → investigar uso de `asyncio.create_task` ou revisar pattern para `queue + worker` (reabre ADR). (c) T048/T049 DeepEval integration falha com incompatibilidade Python 3.12 → fallback para subprocess documentado em A3 da spec. (d) T099 custo real Bifrost >R$10/dia combinado após flip `on` → reduzir amostra ou desligar Toxicity+Bias via tenants.yaml; se persistir, reverter para shadow. (e) Playwright T080 revela flakiness >5% em 2 semanas → mover UI E2E para manual-gate, não-blocking."
