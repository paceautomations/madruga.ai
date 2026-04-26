# Implementation Plan: Evals — Offline (DeepEval) + Online (Heuristico) + Dataset Incremental

**Branch**: `epic/prosauai/011-evals` | **Date**: 2026-04-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `platforms/prosauai/epics/011-evals/spec.md`

## Summary

Fechar o buraco entre [vision](../../business/vision.md) ("70% de resolucao autonoma em 18 meses") e pipeline em producao (hoje `evaluator.py` do epic 005 calcula `quality_score` e descarta) entregando **trilho duplo de avaliacao com dataset incremental**:

- **Online heuristico (P1)** — `asyncio.create_task(persist_score(...))` apos o step `evaluate` do pipeline grava cada resposta em `eval_scores` com `evaluator_type='heuristic_v1'` + novo campo `metric='heuristic_composite'`. Fire-and-forget ([ADR-028](../../decisions/ADR-028-pipeline-fire-and-forget-persistence.md)), zero LLM extra, zero impacto no p95 <3s (NFR Q1).
- **Cron noturno autonomous resolution (P1)** — `autonomous_resolution_cron` (03:00 UTC, singleton via `pg_try_advisory_lock` — mesmo padrao do `handoff_resume_cron`, epic 010) popula `conversations.auto_resolved BOOLEAN` com heuristica A (sem mute em `handoff_events`; sem regex `humano|atendente|pessoa|alguem real` em inbound direcionado ao bot; silencio >=24h). North Star da vision finalmente mensuravel.
- **DeepEval batch noturno (P2)** — `deepeval_batch_cron` (02:00 UTC) seleciona ate 200 msgs/tenant/dia estratificadas por `intent` (coluna em `public.traces`), roda 4 metricas reference-less (`AnswerRelevancy`, `Toxicity`, `Bias`, `Coherence`) via `gpt-4o-mini` no mesmo endpoint Bifrost `/v1/chat/completions` ja usado pelo pipeline — **zero infra nova**.
- **Promptfoo CI smoke (P2)** — 5 casos hand-written em `prosauai/evals/promptfoo/smoke.yaml` + gerador automatico de YAML a partir de `public.golden_traces`. GitHub Action gate-blocking para PRs que tocam `agents/|prompts/|safety/`.
- **Golden curation + Admin UI (P3)** — botao "star" no drawer do Trace Explorer (append-only com verdict `positive|negative|cleared`), 4 cards novos na Performance AI (relevance trend, toxicity/bias rate, coverage %, autonomous resolution %).

**Abordagem tecnica**: reusa integral da stack operacional do epic 010 (config_poller, scheduler asyncio, advisory-lock singleton, `tenants.yaml` feature flag pattern, fire-and-forget ADR-028, structlog + Prometheus metrics facade, pool_admin BYPASSRLS para queries admin cross-tenant). **5 migrations aditivas** resolvem divergencias de schema detectadas:
1. `ALTER TABLE eval_scores ADD COLUMN metric VARCHAR(50)` — schema do epic 005 ja tem `evaluator_type` + `quality_score` mas **nao tem** discriminador de metrica — bloqueante para DeepEval multi-metric.
2. `ALTER TABLE public.traces ADD CONSTRAINT traces_trace_id_unique UNIQUE (trace_id)` — hoje so ha INDEX nao-unique; FK de `golden_traces(trace_id) REFERENCES traces(trace_id)` exige UNIQUE (Clarification Q1 da spec resolvida positivamente: A19 confirmada — existe indice mas sem UNIQUE, entao promovemos).
3. `ALTER TABLE conversations ADD COLUMN auto_resolved BOOLEAN NULL` — cron noturno popula.
4. `ALTER TABLE messages ADD COLUMN is_direct BOOLEAN NOT NULL DEFAULT TRUE` — resolve A20 da spec (grupo-chat filter na heuristica A). Backfill aceita `TRUE` default porque (a) 1:1 e sempre direto, (b) grupo pre-epic e tratado como "best-effort" (perda aceita: custos historicos de FP em grupo sao <5% segundo volume atual).
5. `CREATE TABLE public.golden_traces (...)` — admin-only carve-out [ADR-027](../../decisions/ADR-027-admin-tables-no-rls.md).

Execucao em **3 PRs mergeaveis isoladamente em `develop`**, cada um reversivel via `evals.mode: off` per-tenant em `tenants.yaml` (config_poller do epic 010, <=60s RTO):

- **PR-A (semana 1)** 5 migrations + modulo `evals/` (persist_score + autonomous_resolution + scheduler base) + `tenants.yaml` schema extends + pipeline step `evaluate` ganha `asyncio.create_task(persist_score)` fire-and-forget. Ariel vai para `shadow` no fim da semana.
- **PR-B (semana 2)** DeepEval integration + batch cron + 4 metricas reference-less + retry/jitter + Promptfoo smoke suite + GitHub Action + endpoint admin `POST /admin/traces/{trace_id}/golden` (sem UI ainda — testes via `curl`) + retention cron `eval_scores_retention_cron`.
- **PR-C (semana 3)** Admin UI: 4 cards Performance AI + star button Trace Explorer + badge/toggle na Tenants tab + Playwright E2E + tipos gerados (`pnpm gen:api`). Rollout Ariel `on` + ResenhAI `shadow -> on`.

**Cut-line explicito**: se PR-B estourar semana 2 → **PR-C vira 011.1** (admin UI e visibilidade + curation ergonomica, nao valor core). Valor user-facing (heuristico online persistido + KPI autonomous resolution no dashboard existente + DeepEval offline + Promptfoo CI) e entregue em PR-A+B sem UI nova (cards vazios na Performance AI ate PR-C).

## Technical Context

**Language/Version**: Python 3.12 (backend FastAPI, padrao epics 001-010). Frontend Next.js 15 (epic 008) estendido sem refatoracao — apenas 4 cards Recharts + 1 botao Trace Explorer + 1 toggle Tenants.

**Primary Dependencies**:
- Existentes: FastAPI >=0.115, pydantic 2.x, asyncpg >=0.30, redis[hiredis] >=5.0, httpx, structlog, opentelemetry-sdk + instrumentations, arize-phoenix-otel, pyyaml.
- **1 lib Python nova**: `deepeval>=3.0` (PR-B) — reuso do Bifrost existente como LLM backend via env `OPENAI_API_BASE`.
- **1 ferramenta Node dev**: `promptfoo` (via `npx promptfoo@latest` no CI — zero install local persistente).
- Admin frontend (epic 008) ja tem Recharts + TanStack Query v5 + shadcn/ui + Playwright — **zero dep nova frontend**.

**Storage**:
- PostgreSQL 15 (Supabase) — **5 migrations aditivas** (ver §Schema migrations abaixo). Todas com `ADD COLUMN IF NOT EXISTS`/`CREATE TABLE IF NOT EXISTS`/`ADD CONSTRAINT IF NOT EXISTS` para idempotencia (padrao epics 008/010).
- **Nao usa Redis** — heuristico e DeepEval gravam direto em PG. Sem prefixo novo.
- **eval_scores schema existente** (epic 005, migration `20260101000007_eval_scores.sql`) ja tem RLS via `public.tenant_id()`; novos `evaluator_type` values e nova coluna `metric` herdam automaticamente.

**Testing**: pytest + testcontainers-postgres + fakeredis + respx (httpx mock DeepEval/Bifrost) + `AsyncMock` (scheduler). Cobertura alvo: `evals/persist.py` ≥95%, `evals/autonomous_resolution.py` ≥95%, `evals/deepeval_batch.py` ≥90% (batch is I/O heavy, tolera skip de edge cases raros), webhooks ≥90%. Playwright (E2E) reuso integral epic 008.

**Target Platform**: Linux server (uvicorn workers em container). Bifrost LLM gateway ja operacional desde epic 002. Admin Next.js em Vercel (sem mudanca de infra). GitHub Actions para Promptfoo CI.

**Project Type**: Backend-heavy com **novo modulo `evals/`** espelhando pattern `handoff/` do epic 010. Zero novo projeto/package Python. Frontend admin (epic 008) ganha extensoes localizadas (4 cards + 1 botao + 1 toggle).

**Performance Goals**:
- p95 texto **pos-PR-A** ≤ baseline epic 010 +0ms (SC-003). Fire-and-forget garante zero impacto sincrono no pipeline. Gate de merge PR-A.
- p95 **dashboard Performance AI (4 cards)** <1s (SC-009). Queries agregadas via pool_admin BYPASSRLS com indices corretos — padrao epic 008.
- **DeepEval batch** completa em <30min/tenant para 200 msgs × 4 metricas (chunks de 10 em paralelo). Gate operacional.
- **`autonomous_resolution_cron`** completa em <5min para conversas do dia. Gate operacional.
- Scheduler MUST retomar execucoes em <=60s do horario planejado (reusa invariante do epic 010 FR-015).

**Constraints**:
- **Zero regressao** em testes existentes (173 epic 005 + 191 epic 008 + N epic 010). Gate de merge de cada PR (SC-005 herdado).
- **Fire-and-forget estrito**: `persist_score` falha nunca bloqueia pipeline ou webhook response ([ADR-028](../../decisions/ADR-028-pipeline-fire-and-forget-persistence.md) obrigatorio).
- **Feature flag respeitada**: `evals.mode=off` == zero INSERT em `eval_scores`, zero cron iteration, zero chamada DeepEval. Testes explicitos garantem (FR-003, A18).
- **Shadow mode honrado**: `mode=shadow` grava scores mas `eval_score_below_threshold_total` nao incrementa alertas (log-only). FR-044.
- **Config poller ≤60s**: reusa mecanismo do epic 010 (FR-010).
- **Advisory-lock singleton obrigatorio**: toda task do scheduler usa `pg_try_advisory_lock(hashtext('<task_name>'))` (FR-014 autonomous_resolution, FR-019 deepeval_batch, FR-052 retention).
- **RLS preservada**: `eval_scores` mantem `tenant_isolation` policy (FR-046). `golden_traces` e admin-only carve-out (ADR-027).
- **LGPD SAR**: `eval_scores` cascata via `tenant_id` (query explicita); `golden_traces.trace_id ON DELETE CASCADE` para `public.traces` — retention 90d e SAR disparam automaticamente (FR-031, FR-047).
- **Retention 90d**: `eval_scores_retention_cron` (04:00 UTC, singleton) apaga rows >90d (FR-052). `conversations.auto_resolved` **nao** sofre retention (FR-053) — North Star precisa de janela 18 meses.
- **Custo LLM budget**: ≤R$3/dia combinado para Ariel + ResenhAI (SC-011). Fallback: reduzir amostra 200→100 ou desligar Toxicity/Bias via `tenants.yaml`. `gpt-4o-mini` default (Clarification Q3: ≈R$0.48/dia combinado, margem 6x).

**Scale/Scope**:
- 2 tenants ativos (Ariel, ResenhAI); rollout `off → shadow (7d) → on`, Ariel primeiro, ResenhAI replica 7d depois.
- Volume esperado: ~3K-10K msgs outbound/tenant/dia → heuristico grava 100% (~6K-20K linhas/dia combinado); DeepEval amostra 200/tenant/dia → ~800 scores DeepEval/tenant/dia (4 metricas × 200 msgs). Ate 90 dias = ~1.5M linhas `eval_scores`; com retention 90d o steady-state e estavel.
- `golden_traces`: volume esperado <100 linhas/mes (curadoria manual do admin); sem necessidade de particionamento.
- Nova camada backend: ~10 arquivos Python em `apps/api/prosauai/evals/`, 5 migrations, 1 endpoint admin novo (`POST /admin/traces/{trace_id}/golden`) + 1 endpoint agregador (`GET /admin/metrics/evals`), 4 cards Recharts no admin.
- **Scope-out explicito**: LLM-as-judge online (adiado para 011.1), auto-handoff em score baixo (011.1), Faithfulness metric (epic 012 RAG), golden PII redaction automatica (FR-048 — responsabilidade manual), alerta critical/PagerDuty (FR-045).

## Constitution Check

*GATE: passa antes do Phase 0 research. Re-checked apos Phase 1 design.*

| Principio | Avaliacao | Justificativa |
|-----------|-----------|---------------|
| I — Pragmatismo & Simplicidade | PASS | Reusa 100% da stack operacional (scheduler, advisory lock, config_poller, fire-and-forget, structlog facade). **1 lib nova (deepeval)**, zero infra nova (Bifrost ja e critical path). Sem DSL novo. 5 migrations aditivas. Heuristico reusa `evaluator.py` existente sem reescrita. `tenants.yaml evals.*` block espelha `handoff.*`. |
| II — Automate repetitive | PASS | 3 crons seguem padrao ja validado no epic 010 (auto_resume + 2 cleanup). Promptfoo generator reduz manual YAML authoring de golden traces. Metricas Prometheus via facade existente. Retention cron reusa padrao. |
| III — Knowledge structured | PASS | 22 decisoes em `decisions.md` (pitch). Spec pos-clarify com 5 Q&As resolvidos autonomamente. 2 ADRs novos (039-040) estendem 2 existentes (008, 027). Research documenta alternativas rejeitadas. Data-model detalha schemas. |
| IV — Fast action | PASS | 3 PRs sequenciais com cut-line explicito (PR-C sacrificavel se PR-B estourar — vira 011.1). Rollout shadow→on reversivel <60s via feature flag. Daily checkpoint em `easter-tracking.md` (convencao epic 008/010). |
| V — Alternativas & trade-offs | PASS | `research.md` §Alternativas documenta 8 decisoes rejeitadas (LLM-as-judge online v1, golden dataset upfront, Phoenix como UI canonica, outbox table para fire-and-forget, schema rename eval_scores, Faithfulness em v1, per-segment heuristics grupo/1:1, DSL novo para golden YAML). Spec §Assumptions registra trade-offs aceitos (custo LLM ate R$3/dia, PII em golden sem redacao automatica, retention 90d eval_scores). |
| VI — Brutal honesty | PASS | Spec §Clarifications expoe Q&As autonomos (FK type, retention 90d, LLM judge model, star clear semantics, group chat direct filter). Confianca Media em A3 (DeepEval compat) e A21 (gpt-4o-mini budget) declaradas. Risco R11 (eval_scores rename rejeitado) aceito conscientemente. |
| VII — TDD | PASS | Unit ≥95% (persist.py, autonomous_resolution.py) + integration testcontainers-postgres + respx (DeepEval/Bifrost) + race tests (concurrent cron via advisory lock) + contract tests (Protocol EvalPersister). Gate merge PR-A: p95 texto ≤ baseline + zero regression 173+191 tests PASS. Gate merge PR-B: custo medido em shadow ≤R$3/dia combinado. |
| VIII — Collaborative decisions | PASS | 5 ambiguidades resolvidas autonomamente na clarify pass (FK cascade, retention 90d, LLM judge model whitelist, "star clear" como 3rd verdict append-only, is_direct column para heuristica A em grupo). Pushback pattern aplicado na Clarification Q4 (alternativa UPDATE soft-delete rejeitada em favor de append-only 3rd enum value). |
| IX — Observability | PASS | 5 metricas Prometheus novas (`eval_scores_persisted_total`, `eval_score_below_threshold_total`, `eval_batch_duration_seconds`, `autonomous_resolution_ratio`, `eval_scores_retention_deleted_total`). OTel span `eval.score.persist` attached ao trace do pipeline; DeepEval batch cria span root `eval.batch.deepeval`. Logs structlog com canonical keys (`tenant_id`, `conversation_id`, `message_id`, `evaluator`, `metric`, `score`). 4 cards admin renderizam a partir desses dados. |

**Violacoes**: nenhuma. `Complexity Tracking` vazio.

### Post-Phase-1 re-check

| Risco | Status |
|-------|--------|
| R1 DeepEval incompatibilidade Python 3.12 + asyncpg | Mitigado: benchmark de integracao em PR-B primeira semana; fallback documentado em A3 — rodar DeepEval em subprocess se async pattern quebrar. Mock `respx` para testes (ja padrao repo). |
| R2 Bifrost rate-limit 429 aborta batch DeepEval | Mitigado: retry com jitter max 3 tentativas/chunk (FR-024); chunks pulados sao contabilizados em `eval_batch_duration_seconds{status='error'}`; tenant continua com `{status='partial'}` no dia (aceito). Alerta operacional >5% chunks falham. |
| R3 Custo LLM explode (gpt-4o-mini retorna muito token) | Mitigado: budget monitor em structlog `eval.deepeval.cost_usd` por chunk + alerta diario >R$3 combinado; fallback manual: reduz amostra 200→100 ou desliga metricas via `tenants.yaml` (RTO <60s). |
| R4 Schema divergencia eval_scores bloqueia DeepEval multi-metric | Mitigado: migration PR-A `ADD COLUMN metric VARCHAR(50)` + backfill `metric='heuristic_composite'` para rows existentes (epic 005 so gravava heuristic). |
| R5 `public.traces(trace_id)` nao e UNIQUE → FK golden_traces falha | Mitigado: migration PR-A `ALTER TABLE public.traces ADD CONSTRAINT traces_trace_id_unique UNIQUE (trace_id)` antes de `CREATE TABLE golden_traces`. OTel garante unicidade global de hex trace_id; zero risco de duplicate nos dados existentes. [A19 resolvido] |
| R6 `messages.is_direct` default TRUE distorce auto_resolved historica em grupos | Aceito: conversa em grupo pre-epic tera `auto_resolved` calculado sem filtro (heuristica nao-direct=true conta como direct=true); impacto historico esperado <5% dos casos; runbook documenta. Alternativa (backfill via processor) rejeitada por custo. |
| R7 Retention 90d apaga trend data longo | Aceito: dashboards operam em 7d/30d; 90d e buffer confortavel. KPI North Star vive em `conversations.auto_resolved` (nao sofre retention, FR-053). |
| R8 Admin estrela trace pos-retention 90d do trace parent | Mitigado: `ON DELETE CASCADE` garante cleanup automatico; `generate` do Promptfoo filtra traces orphans (FR-exists check). |
| R9 Cron DeepEval roda 02:00 e pega janela incompleta | Aceito: sampler filtra "ultimas 24h fechadas" (`created_at >= NOW() - INTERVAL '24h' AND created_at < NOW() - INTERVAL '1h'`); gap 1h absorve scheduler skew. |
| R10 Duplicacao de locks cron (autonomous + deepeval + retention simultaneos) | Mitigado: 3 tasks usam `hashtext` diferentes (`autonomous_resolution_cron`, `deepeval_batch_cron`, `eval_scores_retention_cron`) → locks disjuntos, zero deadlock. |
| R11 Decisao eval_scores ADD COLUMN vs rename | Aceito: RENAME quebraria epic 005 + queries admin epic 008 (pool_admin). ADD COLUMN `metric` e aditivo e preserva backward compat. [DECISAO DO USUARIO — default pragmatica sem input humano em autonomous mode] |
| R12 `gpt-4o-mini` via Bifrost nao existe como model ID | Validar em PR-B T001 via `curl` a Bifrost; fallback: ajustar whitelist para model ID efetivo. Zero bloqueio — alternativa `gpt-4o` (3x custo, ainda <R$3/dia). |
| R13 Shadow mode Ariel revela coverage <50% por bug pipeline | Mitigado: SC-008 gate requer coverage ≥80% antes de flip `on`. Metrica `eval_scores_persisted_total{status='ok'}` vs `messages outbound` em janela 7d valida. |
| R14 Promptfoo CI lento (>3min) em PRs de prompt engineering | Mitigado: matrix split se suite >50 casos (SC-012); cache de dependencias npm via GitHub Actions. |

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/011-evals/
├── plan.md                   # Este arquivo (/speckit.plan output)
├── spec.md                   # Feature specification (pos-clarify, 54 FRs + 12 SCs + 22 assumptions)
├── pitch.md                  # Shape Up pitch (L2 — epic-context)
├── decisions.md              # 22 micro-decisoes capturadas
├── research.md               # Phase 0 — alternativas rejeitadas + schema research
├── data-model.md             # Phase 1 — schemas Pydantic + SQL migrations + ER diagram
├── contracts/
│   ├── README.md             # Indice + gates de contrato
│   ├── evaluator-persist.md  # Protocol EvalPersister + EvalScore model + DeepEval wrapper
│   └── openapi.yaml          # OpenAPI 3.1 (admin endpoints: metrics + golden curation + tenant evals toggle)
├── quickstart.md             # Phase 1 — setup dev + validacao US1-US6 + rollback + troubleshooting
├── checklists/               # Ja populado via epic-context/clarify
└── tasks.md                  # Phase 2 output (gerado por /speckit.tasks — NAO por este comando)
```

### Source Code (repository root — repo externo `paceautomations/prosauai`)

```text
apps/
├── api/                                              # backend FastAPI (existente)
│   ├── prosauai/
│   │   ├── main.py                                   # EXTEND: start scheduler tasks no lifespan (3 novas: autonomous_resolution + deepeval_batch + eval_scores_retention)
│   │   ├── config.py                                 # EXTEND: AUTONOMOUS_RESOLUTION_INTERVAL_SECONDS, DEEPEVAL_BATCH_INTERVAL_SECONDS, EVAL_SCORES_RETENTION_INTERVAL_SECONDS, DEEPEVAL_MAX_SAMPLE_SIZE
│   │   ├── config_poller.py                          # NO-OP: re-le tenants.yaml (ja existe); schema novo e validado via pydantic TenantEvalConfig (bloco evals.*)
│   │   ├── evals/                                    # NEW — modulo formal
│   │   │   ├── __init__.py
│   │   │   ├── models.py                             # NEW — EvalScore, EvalPersistRequest, GoldenTraceRecord, TenantEvalConfig pydantic models
│   │   │   ├── persist.py                            # NEW — persist_score(tenant_id, message_id, ..., evaluator_type, metric, score, details) fire-and-forget
│   │   │   ├── heuristic_online.py                   # NEW — bridge entre conversation/evaluator.py e persist_score; mapea EvalResult → eval_scores row
│   │   │   ├── autonomous_resolution.py              # NEW — heuristica A + cron loop
│   │   │   ├── deepeval_batch.py                     # NEW — sampler + runner + 4 metrics wrapper (AnswerRelevancy/Toxicity/Bias/Coherence)
│   │   │   ├── deepeval_model.py                     # NEW — Bifrost httpx wrapper para DeepEval judge (gpt-4o-mini default)
│   │   │   ├── scheduler.py                          # NEW — asyncio periodic tasks (3 crons) espelhando handoff/scheduler.py
│   │   │   ├── retention.py                          # NEW — eval_scores_retention_cron query
│   │   │   ├── metrics.py                            # NEW — Prometheus facade (5 novas metricas)
│   │   │   └── promptfoo/
│   │   │       ├── smoke.yaml                        # NEW — 5 casos hand-written (smoke suite)
│   │   │       ├── generate.py                       # NEW — gera YAML a partir de public.golden_traces
│   │   │       └── README.md                         # NEW — runbook Promptfoo CI
│   │   ├── conversation/
│   │   │   └── pipeline.py                           # EXTEND: step `evaluate` ganha `asyncio.create_task(heuristic_online.persist(...))` apos evaluate_response
│   │   ├── api/
│   │   │   └── admin/                                # ja existe (epic 008)
│   │   │       ├── metrics.py                        # EXTEND: GET /admin/metrics/evals?tenant={id|all}&evaluator=&metric=&window=
│   │   │       ├── traces.py                         # EXTEND: POST /admin/traces/{trace_id}/golden (insere em golden_traces)
│   │   │       └── tenants.py                        # EXTEND: PATCH /admin/tenants/{id}/evals (atualiza evals.mode via tenants.yaml editor)
│   │   └── db/
│   │       ├── queries/
│   │       │   ├── eval_scores.py                    # NEW — insert_score / fetch_metrics_agg / retention_delete
│   │       │   ├── golden_traces.py                  # NEW — insert_verdict / effective_verdict_by_trace
│   │       │   └── conversations.py                  # EXTEND: update_auto_resolved(conversation_id, value)
│   │       └── migrations/
│   │           ├── 20260601000001_alter_eval_scores_add_metric.sql              # PR-A — ADD COLUMN metric VARCHAR(50) + backfill
│   │           ├── 20260601000002_alter_traces_unique_trace_id.sql              # PR-A — ADD CONSTRAINT UNIQUE (necessario para FK golden_traces)
│   │           ├── 20260601000003_alter_conversations_auto_resolved.sql         # PR-A — ADD COLUMN auto_resolved BOOLEAN NULL
│   │           ├── 20260601000004_alter_messages_is_direct.sql                  # PR-A — ADD COLUMN is_direct BOOLEAN NOT NULL DEFAULT TRUE
│   │           └── 20260601000005_create_golden_traces.sql                      # PR-B — CREATE TABLE golden_traces (admin-only)
│   ├── config/
│   │   └── tenants.yaml                              # EXTEND: bloco evals.* por tenant (schema via TenantEvalConfig)
│   └── tests/
│       ├── contract/
│       │   └── test_eval_persister_contract.py       # NEW — Protocol conformance (evaluator_type ∈ {heuristic_v1, deepeval, human})
│       ├── unit/
│       │   ├── evals/
│       │   │   ├── test_persist.py                   # NEW — idempotency fire-and-forget, score clip [0,1], error path logging
│       │   │   ├── test_heuristic_online.py          # NEW — mapeia EvalResult → persist_score (shadow vs on vs off)
│       │   │   ├── test_autonomous_resolution.py     # NEW — 3 casos heuristica A (positive, has mute, has escalation regex); group is_direct filter
│       │   │   ├── test_deepeval_batch.py            # NEW — sampler stratified by intent; metric isolation; retry jitter; 32K filter; clip score
│       │   │   ├── test_deepeval_model.py            # NEW — httpx respx mock Bifrost; model whitelist validation
│       │   │   ├── test_scheduler.py                 # NEW — advisory lock singleton; 3 disjoint locks; shutdown graceful
│       │   │   ├── test_retention.py                 # NEW — delete >90d; metric counter; lock held skip
│       │   │   ├── test_promptfoo_generate.py        # NEW — YAML output from golden_traces; cleared filter; orphan trace skip
│       │   │   └── test_metrics.py                   # NEW — Prometheus facade (sem prometheus_client dep)
│       │   ├── api/
│       │   │   └── admin/
│       │   │       ├── test_metrics_evals.py         # NEW — GET /admin/metrics/evals (per-tenant + cross-tenant pool_admin)
│       │   │       ├── test_traces_golden.py         # NEW — POST golden (verdicts positive/negative/cleared; auth 401/403)
│       │   │       └── test_tenants_evals.py         # NEW — PATCH /admin/tenants/{id}/evals
│       │   └── pipeline/
│       │       └── test_evaluate_persist_hook.py     # NEW — step evaluate agenda task sem bloquear pipeline
│       ├── integration/
│       │   ├── test_heuristic_online_flow.py         # NEW — webhook → pipeline → persist_score row em eval_scores (shadow vs off)
│       │   ├── test_autonomous_resolution_flow.py    # NEW — semear conversas → cron → auto_resolved TRUE/FALSE correto
│       │   ├── test_deepeval_batch_flow.py           # NEW — cron completa + 4 metricas × N msgs sem metric isolation breach (respx Bifrost)
│       │   ├── test_golden_flow.py                   # NEW — POST star → MAX(created_at) verdict efetivo; cleared overrides positive
│       │   ├── test_retention_flow.py                # NEW — rows >90d deletadas, <90d preservadas; conversations.auto_resolved preservada
│       │   └── test_feature_flag_off.py              # NEW — evals.mode=off → zero INSERT eval_scores + zero call DeepEval
│       ├── benchmarks/
│       │   └── test_pipeline_p95_no_regression.py    # NEW — gate SC-003 PR-A (p95 ≤ baseline epic 010 +0ms)
│       └── fixtures/
│           ├── deepeval_mock_responses.json          # NEW — respx fixtures para Bifrost gpt-4o-mini (4 metricas)
│           └── golden_trace_examples.sql             # NEW — seed para testes generator Promptfoo
├── admin/                                            # Next.js — epic 008
│   └── src/
│       └── app/admin/(authenticated)/
│           ├── performance/
│           │   └── page.tsx                          # EXTEND: 4 cards Recharts (relevance trend / toxicity+bias / coverage gauge / autonomous %) — PR-C
│           ├── traces/
│           │   └── [traceId]/page.tsx                # EXTEND: botao "Star" positivo/negativo/clear no drawer — PR-C
│           └── tenants/
│               └── page.tsx                          # EXTEND: badge evals.mode + toggle → PATCH /admin/tenants/{id}/evals — PR-C
└── .github/
    └── workflows/
        └── promptfoo-smoke.yml                       # NEW (PR-B) — gate blocking em PRs que tocam agents/prompts/safety
```

**Structure Decision**: Backend-heavy com **novo modulo `evals/`** em `apps/api/prosauai/` — padrao ja validado nos epics 009 (`channels/`, `processors/`) e 010 (`handoff/`). Zero novo projeto/package Python — tudo sob namespace `prosauai.*` existente. Frontend admin (epic 008) ganha apenas extensoes localizadas (3 paginas existentes estendidas). Testes reusam estrutura `tests/{contract,unit,integration,benchmarks,fixtures}`. Promptfoo suite vive em `prosauai/evals/promptfoo/` (YAML + generator + README) — CI via GitHub Action separado, sem acoplar com pytest.

## Complexity Tracking

> Nenhuma violacao de Constitution Check identificada. Esta tabela permanece vazia.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 — Research (already complete)

**Output**: [research.md](./research.md) — preserva escopo tecnico integral, alternativas rejeitadas e resolucao explicita de 5 divergencias de schema (migrations 1-5). Todas as `NEEDS CLARIFICATION` resolvidas:

- [pitch.md](./pitch.md) §Captured Decisions — 22 decisoes locked com referencias.
- [pitch.md](./pitch.md) §Resolved Gray Areas — 8 pontos decididos autonomamente na activation 2026-04-24.
- [spec.md §Clarifications](./spec.md#clarifications) — 5 Q&As resolvidos autonomamente durante clarify pass (FK type, retention 90d, LLM judge model, star clear, group chat is_direct filter).
- [decisions.md](./decisions.md) — 22 decisoes ordenadas com data, skill e referencia.

**Alternativas consideradas e rejeitadas** (resumo — detalhes em [research.md](./research.md)):

| Alternativa | Rejeitada por |
|-------------|---------------|
| LLM-as-judge online em v1 (nao heuristico) | +R$0.02/msg em 10% samples antes de calibrar threshold; Bifrost latency adiciona ao hot path; CEO + PO alinhados em Q1-B para adiar ate dados de shadow existirem. |
| Golden dataset upfront (curar 50+ casos antes de v1) | Ariel + ResenhAI sao comunidades esportivas; fixtures epic 009 cobrem parsing, nao qualidade; benchmark-gaming; decisao 3 do pitch. |
| Phoenix como UI canonica (sem cards admin) | Dois lugares para olhar metricas agregadas diluir autoridade; drill-down individual via trace_id permanece; Q5-B. |
| Outbox table para persist_score (garantir durabilidade) | Overhead infra maior que valor em v1; perda esperada <0.5% acessivel via alerta `status='error'`; A6 da spec. |
| Rename `eval_scores.evaluator_type → evaluator` + `quality_score → score` | Quebra epic 005 + queries admin pool_admin do epic 008. ADD COLUMN `metric` e aditivo. R11 + ADR-039 section. |
| Faithfulness metric em v1 | Exige grounding source (RAG); epic 012 ainda nao aconteceu; AnswerRelevancy substitui no set reference-less (compara pergunta vs resposta sem external truth). Q3 + ADR-039. |
| Heuristica per-segment grupo vs 1:1 | `is_direct=true` default em grupo e aceito como trade-off (R6); refinement per-segment adiado para 011.1 com LLM-as-judge. Decisao 22. |
| DSL novo para golden YAML | Promptfoo ja aceita YAML estruturado; generator Python de 100 LOC mapea `golden_traces` rows → Promptfoo cases; zero DSL novo. Decisao 10. |

## Phase 1 — Design Artifacts

### Artefatos gerados neste plan

| Artefato | Proposito | Referencia |
|----------|-----------|-----------|
| **data-model.md** | Schemas Pydantic (`EvalScoreRecord`, `GoldenTraceRecord`, `TenantEvalConfig`, `AlertThreshold`); SQL das 5 migrations; ER diagram; `tenants.yaml evals.*` schema; validacoes por camada; rejected alternatives schema | [data-model.md](./data-model.md) |
| **contracts/evaluator-persist.md** | Protocol `EvalPersister` (Python) + `EvalScore` model; contract `DeepEvalMetric` wrapper (4 metricas conforme); contract tests com `isinstance` + Protocol check; isolamento de falha por metrica | [contracts/evaluator-persist.md](./contracts/evaluator-persist.md) |
| **contracts/openapi.yaml** | OpenAPI 3.1 (`GET /admin/metrics/evals`, `POST /admin/traces/{trace_id}/golden`, `PATCH /admin/tenants/{id}/evals`); schemas `EvalMetricsResponse`, `GoldenVerdictRequest`, `TenantEvalsRequest`, `ErrorResponse` | [contracts/openapi.yaml](./contracts/openapi.yaml) |
| **quickstart.md** | Setup dev + validacao incremental por PR (PR-A/PR-B/PR-C); validacao por User Story (US1-US6); rollback de emergencia; troubleshooting de schema drift | [quickstart.md](./quickstart.md) |

### ADRs planejados (2 novos, estendem 2 existentes)

Geracao e tarefa explicita do PR-A (ADR-039) e PR-B (ADR-040). Esbocos ja em [decisions.md](./decisions.md):

| # | Titulo | Escopo | PR |
|---|--------|--------|-----|
| ADR-039 | Eval metric bootstrap sem golden dataset | Reference-less DeepEval metrics (AnswerRelevancy/Toxicity/Bias/Coherence) como v1; golden grows incremental via admin curation; decisao de ADD COLUMN `metric` vs rename eval_scores schema | PR-A |
| ADR-040 | Autonomous resolution operational definition | Heuristica A canonica (sem mute + regex escalation + 24h silencio + is_direct filter grupo); revisitar com LLM-as-judge em 011.1; rationale vs heuristicas alternativas | PR-A |

**ADRs estendidos (nao substituidos)**:
- [ADR-008](../../decisions/ADR-008-eval-stack.md) (eval-stack) — confirma stack DeepEval+Promptfoo; adiciona rationale reference-less e incremental golden.
- [ADR-027](../../decisions/ADR-027-admin-tables-no-rls.md) (admin-tables-no-rls) — `public.golden_traces` herda carve-out admin-only.
- [ADR-028](../../decisions/ADR-028-pipeline-fire-and-forget-persistence.md) (fire-and-forget) — confirma pattern para `persist_score`.
- [ADR-018](../../decisions/ADR-018-data-retention-lgpd.md) (LGPD) — estendido com retention 90d `eval_scores`.

### Agent context update

Apos merge de cada PR, `update-agent-context.sh claude` reflete:
- PR-A: novo modulo `evals/` e 4 migrations aditivas (aditivo, `deepeval` nao ainda instalado).
- PR-B: dep `deepeval>=3.0` + 1 migration `golden_traces` + Promptfoo GitHub Action.
- PR-C: nada novo — UI extensao localizada no admin existente.

---

## Sequenciamento & guardrails

### Cronograma

| Semana | PR | Entregaveis | Gate de merge |
|--------|----|-------------|---------------|
| 1 early | PR-A coding | ADR-039 draft; 4 migrations aditivas (eval_scores add metric, traces unique trace_id, conversations auto_resolved, messages is_direct); `evals/persist.py`, `evals/heuristic_online.py`, `evals/autonomous_resolution.py`, `evals/scheduler.py`, `evals/metrics.py`; ADR-040 draft; pipeline step `evaluate` ganha `asyncio.create_task(persist_score)`; `tenants.yaml evals.*` schema + `TenantEvalConfig` pydantic; Ariel `shadow` fim da semana | — |
| 1 merge | PR-A merge | 173+191+N epic 010 tests PASS + zero regression; p95 texto ≤ baseline epic 010 +0ms (benchmark dedicado); heuristico online grava 100% das msgs Ariel em shadow (counter coverage=100% p/ janela 24h); `autonomous_resolution_cron` roda 1 noite com 0 erros; contract tests PASS | SC-003, SC-005, SC-007 |
| 2 early | PR-B coding | ADR-040 final; dep `deepeval>=3.0` no pyproject.toml; `evals/deepeval_batch.py` + `evals/deepeval_model.py`; 4 metricas reference-less; retry/jitter; sampler intent-stratified; Promptfoo `smoke.yaml` (5 casos) + `generate.py`; GitHub Action `promptfoo-smoke.yml`; migration `golden_traces` + endpoint `POST /admin/traces/{trace_id}/golden`; `eval_scores_retention_cron` + `retention.py`; Ariel `shadow` tem scores DeepEval povoando | — |
| 2 merge | PR-B merge | DeepEval batch completa em <30min/tenant; 4 metricas persistem com falha isolada (teste forca erro em Toxicity, outras 3 ok); Promptfoo CI gate bloqueia PR sintetico que regressa prompt; golden curation via `curl` funcional; custo Bifrost ≤R$3/dia combinado Ariel shadow (validado via structlog logs `eval.deepeval.cost_usd`); retention cron apaga row antiga de fixture | SC-002, SC-004, SC-005, SC-007, SC-011, SC-012 |
| 3 early | PR-C coding | Admin UI: 4 cards Performance AI (Recharts + TanStack Query v5 stale-time 30s); botao Star Trace Explorer (3 actions: positive/negative/clear → POST golden); badge + toggle na Tenants tab (PATCH evals); tipos gerados `pnpm gen:api`; Playwright E2E (cards render + star trace + toggle mode); Ariel `shadow → on` | — |
| 3 merge | PR-C merge | 4 cards renderizam <1s p95 (benchmark Playwright); star cria linha em golden_traces; toggle altera `tenants.yaml` em <60s (config poller); Playwright suite verde; Ariel `on` com 7d de dados acumulados; ResenhAI `shadow`; `evals.mode=off` tenant mostra skeleton esperado | SC-001, SC-004, SC-006, SC-009, SC-010, SC-013 |
| Pos-3 | Rollout | ResenhAI `shadow → on` (7d apos Ariel `on`); dashboards Performance AI validados com 2 tenants; golden_traces cresce organicamente | SC-006 (30d apos rollout) |

### Reconcile apos cada PR-merge

Hook automatico fire do `madruga:reconcile` detecta drift entre docs e codigo implementado. Esperado: zero drift (artefatos Phase 1 detalham 1:1 o codigo-alvo). Eventuais drifts:
- Migrations aditivas → reconcile flaga em `engineering/domain-model.md` (atualiza descricao de `eval_scores` com coluna `metric`).
- Nova tabela → reconcile atualiza `engineering/containers.md` (se containers mudam — nao muda, infra reusa Postgres existente).
- ADRs 039-040 → reconcile atualiza `decisions.md` do epic e cria arquivos `ADR-039-*.md` / `ADR-040-*.md` em `platforms/prosauai/decisions/`.

### Cut-line explicito

Se PR-B estourar semana 2 → **cortar PR-C** → admin UI + golden star virame 011.1. Criterio: valor user-facing (tendencia qualidade + KPI North Star + CI gate anti-regressao) e entregue por PR-A+B sem UI:
- Heuristico online grava 100% das msgs em `eval_scores` → queries manuais via SQL para admin.
- `autonomous_resolution_cron` popula `conversations.auto_resolved` → query `COUNT(*) WHERE auto_resolved=true` da o North Star.
- DeepEval grava scores offline → query SQL agrupada por metrica+tenant.
- Promptfoo CI gate bloqueia regressao em PRs.
- Golden curation via `curl` para `POST /admin/traces/{trace_id}/golden` (admin executa manualmente — operadores Pace podem fazer direto).

PR-C entrega visibilidade visual + ergonomia — sacrificavel.

### Daily checkpoint

`easter-tracking.md` (convencao epic 008/010) com 3 bullets async: (a) o que foi mergeavel ontem, (b) o que e mergeavel hoje, (c) o que esta bloqueando. Flagra bleed cedo.

---

## Schema migrations

Resumo detalhado em [data-model.md §Migrations](./data-model.md#migrations). 5 migrations aditivas, todas com IF NOT EXISTS/IF NOT VALID para idempotencia:

| # | Migration | Escopo | Impacto |
|---|-----------|--------|---------|
| 1 | `20260601000001_alter_eval_scores_add_metric.sql` | `ALTER TABLE eval_scores ADD COLUMN metric VARCHAR(50) NOT NULL DEFAULT 'heuristic_composite';` + backfill para rows existentes (seguro, todas sao heuristic) | Aditivo; zero quebra epic 005. Epic 008 pool_admin queries preservadas (SELECT usa colunas nomeadas) |
| 2 | `20260601000002_alter_traces_unique_trace_id.sql` | `CREATE UNIQUE INDEX CONCURRENTLY idx_traces_trace_id_unique ON public.traces (trace_id); ALTER TABLE public.traces DROP CONSTRAINT IF EXISTS idx_traces_trace_id; ALTER TABLE public.traces ADD CONSTRAINT traces_trace_id_unique UNIQUE USING INDEX idx_traces_trace_id_unique;` | OTel garante unicidade global; zero duplicate risk. CONCURRENTLY evita table lock |
| 3 | `20260601000003_alter_conversations_auto_resolved.sql` | `ALTER TABLE conversations ADD COLUMN auto_resolved BOOLEAN NULL;` | Aditivo; default NULL ("nao calculado"); cron popula |
| 4 | `20260601000004_alter_messages_is_direct.sql` | `ALTER TABLE messages ADD COLUMN is_direct BOOLEAN NOT NULL DEFAULT TRUE;` | Default TRUE cobre retroativamente (100% 1:1 + ~95% grupos segundo A6); `channels/canonical.py` passa a setar explicitamente no insert para grupos |
| 5 | `20260601000005_create_golden_traces.sql` | `CREATE TABLE public.golden_traces (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), trace_id TEXT NOT NULL REFERENCES public.traces(trace_id) ON DELETE CASCADE, verdict TEXT NOT NULL CHECK (verdict IN ('positive','negative','cleared')), notes TEXT, created_by_user_id UUID, created_at TIMESTAMPTZ DEFAULT NOW());` + `CREATE INDEX idx_golden_traces_trace_created ON (trace_id, created_at DESC);` | Admin-only (carve-out ADR-027); zero RLS |

---

## Testing strategy (resumo)

- **Unit** (≥95% `persist.py`, `autonomous_resolution.py`; ≥90% `deepeval_batch.py`, webhooks/schedulers): `respx` para Bifrost/DeepEval mocks; `AsyncMock` para scheduler; `fakeredis` (embora nao use Redis direto, reuso para fixtures compartilhadas); `testcontainers-postgres` para RLS + advisory lock validation; `freezegun` para cron time-travel.
- **Contract** (Protocol conformance): `EvalPersister.persist(...)` conformance test parametrizado para heuristic + deepeval adapters. Garante API estavel.
- **Integration** (testcontainers-postgres + respx Bifrost): fluxos completos por US:
  - US1 heuristic persist: webhook → pipeline → eval_scores row (mode=shadow).
  - US2 autonomous: semear conversas → cron → auto_resolved correto (3 variantes).
  - US3 DeepEval: cron completa + 4 metricas × N msgs; falha isolada Toxicity.
  - US4 Promptfoo: PR sintetico que regride prompt bloqueia CI (GitHub Action local via `act`).
  - US5 golden: POST star → MAX verdict; cleared overrides positive.
  - US6 UI: Playwright renderiza 4 cards com dados reais.
- **Race tests** (proposital concurrency): `asyncio.gather` com 3 iteracoes concorrentes do mesmo cron → apenas 1 ganha (advisory lock `pg_try_advisory_lock`). 3 locks disjuntos validados.
- **E2E Playwright** (reuso infra epic 008): Performance AI cards + star Trace Explorer + Tenants toggle.
- **Benchmarks** (gate merge): `test_pipeline_p95_no_regression.py` (SC-003 PR-A). Custo LLM medido em shadow via `structlog` (SC-011 PR-B gate manual).
- **Fixtures**: 
  - Respx responses mock para Bifrost (4 metricas × happy/error path).
  - Golden traces seed SQL para testes de generator Promptfoo.
  - Fixtures capturadas reais de `eval_scores` + `messages` para benchmark (reutiliza epic 005/010 fixtures).
- **Smoke prod**: runbook `apps/api/benchmarks/evals_smoke.md` pre-rollout cada tenant.

---

## Dependencias externas

| Item | Origem | Escopo |
|------|--------|--------|
| Bifrost gateway LLM (gpt-4o-mini) | Infra Pace operacional (epic 002) | PR-B (DeepEval judge calls) |
| `deepeval>=3.0` (PyPI) | Python lib nova | PR-B (`pyproject.toml`) |
| `promptfoo` (npm, dev-only) | CI tool | PR-B (GitHub Action `npx promptfoo@latest`) |
| Nenhuma infra nova | — | — |

**Sem blockers**: epics 002/005/008/010 fechados (reconcile reports existem). Postgres 15 via Supabase provisionado. Bifrost operacional desde epic 002.

---

## Estrutura de PR (contratos explicitos)

Cada PR carrega:

1. **Descricao**: qual decisao arquitetural e entregue + User Stories servidas.
2. **Checklist de gates**: itens SC-NNN que devem passar antes do merge.
3. **Rollback plan**: sequencia exata para desligar (`evals.mode: shadow → off` no `tenants.yaml` → config_poller 60s → zero side effect).
4. **Observability plan**: metricas a acompanhar nas primeiras 24h em staging (`eval_scores_persisted_total`, `eval_batch_duration_seconds`, `autonomous_resolution_ratio`, `eval_scores_retention_deleted_total`).

### Rollback matrix

| Cenario | Acao | RTO |
|---------|------|-----|
| Heuristico online polui `eval_scores` com dado ruim | `tenants.yaml` → `evals.mode: on → off` | ≤60s (config_poller) |
| DeepEval gera custo alem do budget | `tenants.yaml` → `evals.offline_enabled: false` (mantem online) | ≤60s |
| DeepEval batch falha cascading em 1 tenant | `tenants.yaml` → `evals.mode: on → shadow` (log-only, sem alertas) | ≤60s |
| Autonomous resolution popula valores errados | Reset SQL `UPDATE conversations SET auto_resolved = NULL WHERE closed_at > NOW() - INTERVAL '30 days'`; fix code; re-run cron | ≤30min |
| Promptfoo CI gate false-positive bloqueia merges validos | Desabilita workflow via `.github/workflows/promptfoo-smoke.yml` (remove ou rename); investiga suite | ≤5min |
| Migration regressao producao | Todas 5 migrations sao aditivas (no data loss); `dbmate rollback` reverte na janela | Deploy window |
| Retention cron apaga dados errados | Paralisar scheduler via env `EVAL_SCORES_RETENTION_ENABLED=0` + deploy | ≤5min |

---

<!-- HANDOFF -->
---
handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan consolidado com 3 PRs (PR-A migrations + modulo evals + heuristic online + autonomous_resolution cron, PR-B deepeval batch + promptfoo CI + golden curation endpoint + retention cron, PR-C admin UI + 4 cards + star button + tenants toggle). 1 lib nova (deepeval), 5 migrations aditivas, 2 ADRs novos (039-040). Resolucao de 5 divergencias de schema detectadas (eval_scores metric column, traces UNIQUE trace_id, conversations auto_resolved, messages is_direct, golden_traces new table). Cut-line: PR-C sacrificavel se PR-B estourar semana 2 → vira 011.1. Pronto para quebrar em tasks.md T001+."
  blockers: []
  confidence: Alta
  kill_criteria: "(a) benchmark PR-A revela impacto de `asyncio.create_task` >5ms p95 → investigar task pressure ou usar `asyncio.to_thread` — se irresoluvel, reverter para `queue + worker` pattern, abrindo decisao arquitetural. (b) `deepeval>=3.0` incompativel com Python 3.12/asyncpg em spike PR-B T001 → fallback para subprocess (documentado em A3). (c) custo Bifrost shadow Ariel exceder R$5/dia (~1.6x budget) → rebalancear para amostra 100/dia ou deslizar Toxicity+Bias → se ainda estourar, reabrir ADR-008 e considerar `gpt-4o-mini` alternativo local (vLLM/Ollama). (d) `public.traces.trace_id` se revelar nao-unico na producao atual (duplicate detectado ao CREATE UNIQUE INDEX CONCURRENTLY) → PR-A bloqueia, investiga origem dos dupes, e decide entre (i) cleanup + retry UNIQUE, (ii) FK em `traces.id UUID` em vez de `trace_id TEXT`. (e) Promptfoo CI gate revelar flakiness >5% em 2 semanas → migrar para manual-gate (recomendado, nao blocking) ate calibrar."
