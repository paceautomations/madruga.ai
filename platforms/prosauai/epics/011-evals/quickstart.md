# Quickstart: Epic 011 — Evals

**Phase 1 output** — setup dev + validacao incremental por PR (PR-A/PR-B/PR-C) + validacao por User Story (US1-US6) + rollback de emergencia + troubleshooting de schema drift.

**Target audience**: engineer implementando PRs deste epic no repo externo `paceautomations/prosauai`.

---

## 1. Pre-requisitos

```bash
# Python 3.12 + asyncpg + deepeval (PR-B somente)
pyenv local 3.12
poetry install
poetry add deepeval@^3.0 --group main  # PR-B

# Postgres 15 local via Docker compose
cd /home/gabrielhamu/repos/paceautomations/prosauai
docker compose up -d postgres redis

# Apply migrations
dbmate --env PROSAUAI_DATABASE_URL=postgres://... up

# Bifrost local (epic 002) — ja rodando no compose
curl http://localhost:8051/health  # espera 200

# Promptfoo (PR-B) — CLI via npx, zero install
npx promptfoo@latest --version
```

Environment vars (`.env`):

```bash
# Existentes (epics anteriores) — sem mudanca
DATABASE_URL=postgres://...
BIFROST_BASE_URL=http://localhost:8051
OPENAI_API_BASE=http://localhost:8051/v1
JWT_SECRET=...

# Novas (epic 011)
AUTONOMOUS_RESOLUTION_INTERVAL_SECONDS=3600          # cron cadence (default 1h)
DEEPEVAL_BATCH_INTERVAL_SECONDS=86400                # daily
DEEPEVAL_MAX_SAMPLE_SIZE=200
EVAL_SCORES_RETENTION_INTERVAL_SECONDS=86400         # daily
EVAL_SCORES_RETENTION_DAYS=90
EVAL_SCORES_RETENTION_ENABLED=1                       # kill switch
```

---

## 2. PR-A validacao — Semana 1 (migrations + heuristico online + autonomous resolution)

### 2.1 Merge gates

1. `poetry run pytest -x tests/unit/evals/ tests/unit/pipeline/ tests/integration/test_heuristic_online_flow.py tests/integration/test_autonomous_resolution_flow.py`
2. `poetry run pytest tests/benchmarks/test_pipeline_p95_no_regression.py` — gate SC-003 (p95 ≤ baseline epic 010 +0ms).
3. `poetry run pytest` — zero regression suite completa (epic 005+008+010).
4. `dbmate up && dbmate down && dbmate up` — migrations reversiveis.

### 2.2 US1 validacao — heuristico online persiste

```bash
# 1. Ligar Ariel em shadow
yq -i '.tenants.ariel.evals.mode = "shadow"' apps/api/config/tenants.yaml

# 2. Aguardar config_poller (≤60s)
sleep 65

# 3. Disparar fixture de mensagem sintetica (reuso tests/fixtures/captured/)
curl -X POST http://localhost:8050/webhook/evolution/smoke-instance \
  -H 'Content-Type: application/json' \
  -d @tests/fixtures/captured/evolution_simple_message.input.json

# 4. Aguardar pipeline completar (~2s)
sleep 3

# 5. Validar row em eval_scores
psql "$DATABASE_URL" -c "
  SELECT evaluator_type, metric, quality_score, details
  FROM eval_scores
  WHERE tenant_id = (SELECT id FROM tenants WHERE slug='ariel')
    AND created_at > NOW() - INTERVAL '10 seconds';
"
# Esperado: 1 row com evaluator_type='heuristic_v1', metric='heuristic_composite', quality_score ∈ [0,1]
```

### 2.3 US2 validacao — autonomous_resolution_cron

```bash
# 1. Semear conversas encerradas 3 variantes (A=resolved, B=muted, C=escalation regex)
psql "$DATABASE_URL" < tests/fixtures/auto_resolved_seeds.sql

# 2. Disparar cron manualmente (bypass scheduler)
curl -X POST http://localhost:8050/admin/debug/run_cron \
  -H 'Authorization: Bearer $ADMIN_JWT' \
  -d '{"task": "autonomous_resolution_cron"}'

# 3. Validar coluna populada
psql "$DATABASE_URL" -c "
  SELECT id, auto_resolved, close_reason
  FROM conversations
  WHERE id IN ('conv-a', 'conv-b', 'conv-c');
"
# Esperado: conv-a: TRUE; conv-b: FALSE (mute); conv-c: FALSE (regex)
```

### 2.4 Schema drift check

```bash
# Confirma que eval_scores.metric existe e FK golden_traces → traces funciona
psql "$DATABASE_URL" -c "\\d eval_scores"
# Esperado: coluna metric VARCHAR(50) NOT NULL + chk_eval_scores_metric

psql "$DATABASE_URL" -c "\\d public.traces" | grep "UNIQUE"
# Esperado: traces_trace_id_unique UNIQUE (trace_id)
```

### 2.5 Rollback PR-A

```bash
# 1. Revert tenants.yaml
yq -i '.tenants.ariel.evals.mode = "off"' apps/api/config/tenants.yaml

# 2. Aguardar config_poller
sleep 65

# 3. Confirmar zero INSERT novo em eval_scores
psql "$DATABASE_URL" -c "
  SELECT COUNT(*) FROM eval_scores WHERE created_at > NOW() - INTERVAL '5 minutes'
    AND evaluator_type='heuristic_v1';
"
# Esperado: contador estatico (nao incrementa)

# 4. Se migration causar problema: dbmate rollback
dbmate rollback  # reverte ultima migration (5 vezes)
```

---

## 3. PR-B validacao — Semana 2 (DeepEval + Promptfoo + golden + retention)

### 3.1 Merge gates

1. `poetry run pytest -x tests/unit/evals/test_deepeval_batch.py tests/unit/evals/test_deepeval_model.py tests/unit/evals/test_promptfoo_generate.py tests/unit/evals/test_retention.py tests/unit/api/admin/test_traces_golden.py tests/integration/test_deepeval_batch_flow.py tests/integration/test_golden_flow.py tests/integration/test_retention_flow.py`
2. `npx promptfoo@latest eval prosauai/evals/promptfoo/smoke.yaml` — 5 casos PASS localmente.
3. Custo Bifrost medido em shadow Ariel: `grep 'eval.deepeval.cost_usd' logs/*.log | jq 'add'` ≤ R$3/dia.
4. `dbmate up` — migration `golden_traces` idempotente.

### 3.2 US3 validacao — DeepEval batch

```bash
# 1. Ligar offline
yq -i '.tenants.ariel.evals.offline_enabled = true' apps/api/config/tenants.yaml

# 2. Disparar cron manualmente (com --dry-run para evitar custo)
curl -X POST http://localhost:8050/admin/debug/run_cron \
  -d '{"task": "deepeval_batch_cron", "dry_run": true}'

# 3. Validar scores persistidos
psql "$DATABASE_URL" -c "
  SELECT evaluator_type, metric, COUNT(*), AVG(quality_score)
  FROM eval_scores
  WHERE tenant_id = (SELECT id FROM tenants WHERE slug='ariel')
    AND evaluator_type = 'deepeval'
    AND created_at > NOW() - INTERVAL '10 minutes'
  GROUP BY 1, 2;
"
# Esperado: 4 rows (answer_relevancy, toxicity, bias, coherence), N ~= msgs amostradas
```

### 3.3 US4 validacao — Promptfoo CI

```bash
# 1. Rodar suite local
npx promptfoo@latest eval prosauai/evals/promptfoo/smoke.yaml
# Esperado: 5 casos PASS

# 2. Simular regression (quebrar system_prompt)
# Temporariamente altere apps/api/prosauai/agents/ariel/system.md para retornar "não sei"
npx promptfoo@latest eval prosauai/evals/promptfoo/smoke.yaml
# Esperado: case "cliente pede stats" FAIL

# 3. Reverter system.md
```

### 3.4 US5 validacao — golden curation via curl

```bash
# 1. Pegar um trace_id recente
TRACE_ID=$(psql "$DATABASE_URL" -Atc "SELECT trace_id FROM public.traces ORDER BY started_at DESC LIMIT 1")

# 2. Estrelar positive
curl -X POST http://localhost:8050/admin/traces/$TRACE_ID/golden \
  -H 'Authorization: Bearer $ADMIN_JWT' \
  -d '{"verdict": "positive", "notes": "exemplo de handoff correto"}'
# Esperado: 201 com id UUID

# 3. Estrelar cleared (desfazer)
curl -X POST http://localhost:8050/admin/traces/$TRACE_ID/golden \
  -H 'Authorization: Bearer $ADMIN_JWT' \
  -d '{"verdict": "cleared"}'
# Esperado: 201 (nova linha, verdict efetivo agora = cleared)

# 4. Gerar suite Promptfoo a partir de golden_traces
poetry run python -m prosauai.evals.promptfoo.generate --output /tmp/golden_cases.yaml
# Esperado: YAML filtrando traces com verdict efetivo = cleared (zero casos se apenas 1 star cleared)
```

### 3.5 Retention cron

```bash
# Simular row antiga (>90d)
psql "$DATABASE_URL" -c "
  INSERT INTO eval_scores (tenant_id, conversation_id, message_id, evaluator_type, metric, quality_score, created_at)
  SELECT tenant_id, conversation_id, message_id, 'heuristic_v1', 'heuristic_composite', 0.5, NOW() - INTERVAL '95 days'
  FROM eval_scores LIMIT 1;
"

# Disparar cron
curl -X POST http://localhost:8050/admin/debug/run_cron \
  -d '{"task": "eval_scores_retention_cron"}'

# Validar counter + row deletada
psql "$DATABASE_URL" -c "
  SELECT COUNT(*) FROM eval_scores WHERE created_at < NOW() - INTERVAL '90 days';
"
# Esperado: 0
```

---

## 4. PR-C validacao — Semana 3 (Admin UI + rollout)

### 4.1 Merge gates

1. `pnpm gen:api` gera tipos sem erro; `pnpm type-check` passa.
2. `pnpm test:e2e tests/e2e/evals.spec.ts` — Playwright suite verde.
3. Smoke manual: login admin → abrir Performance AI → 4 cards renderizam dados Ariel.
4. Toggle `evals.mode` via Tenants tab → config_poller aplica em ≤60s (observado via logs).

### 4.2 US6 validacao — 4 cards

```bash
# 1. Abrir admin
open http://localhost:3000/admin/performance

# 2. Selecionar tenant Ariel (com mode=on 7d)
# Esperado: 4 cards com dados reais
#   - AnswerRelevancy line chart 7d com >=1 ponto por dia
#   - Toxicity + Bias stacked area
#   - Coverage gauge: online ~100%, offline ~5-10%
#   - Autonomous resolution bignumber + sparkline

# 3. Selecionar tenant ResenhAI (com mode=off)
# Esperado: skeleton "Evals desabilitados para este tenant"
```

### 4.3 Playwright smoke

```bash
pnpm test:e2e tests/e2e/evals.spec.ts
# Cenarios:
# - Performance AI renderiza 4 cards sem erro
# - Star button em trace abre toast
# - Toggle evals.mode em Tenants tab chama PATCH
```

### 4.4 Rollout Ariel on

```bash
# 1. Confirmar 7d shadow com coverage >=80%
psql "$DATABASE_URL" -c "
  WITH msgs AS (SELECT COUNT(DISTINCT id) AS total FROM messages
                WHERE tenant_id=(SELECT id FROM tenants WHERE slug='ariel')
                  AND direction='outbound' AND created_at > NOW() - INTERVAL '7 days'),
       scored AS (SELECT COUNT(DISTINCT message_id) AS scored FROM eval_scores
                  WHERE tenant_id=(SELECT id FROM tenants WHERE slug='ariel')
                    AND evaluator_type='heuristic_v1' AND created_at > NOW() - INTERVAL '7 days')
  SELECT (scored::float / msgs.total) AS coverage FROM msgs, scored;
"

# 2. Flip mode
yq -i '.tenants.ariel.evals.mode = "on"' apps/api/config/tenants.yaml
sleep 65

# 3. Monitorar 48h: metricas + alertas + custo
grep 'eval.deepeval.cost_usd' logs/*.log | jq 'add'
```

---

## 5. Rollback de emergencia

Qualquer cenario — RTO ≤60s via feature flag:

```bash
yq -i '.tenants.<tenant>.evals.mode = "off"' apps/api/config/tenants.yaml
# Zero INSERT em eval_scores apos config_poller poll (≤60s)
```

Cenarios especificos: [plan.md §Rollback matrix](./plan.md#rollback-matrix).

Desabilitar **apenas** DeepEval (mantem online):
```bash
yq -i '.tenants.<tenant>.evals.offline_enabled = false' apps/api/config/tenants.yaml
```

Kill retention cron:
```bash
export EVAL_SCORES_RETENTION_ENABLED=0
# Redeploy API — scheduler task skipa iteracao
```

---

## 6. Troubleshooting

### 6.1 Schema drift detectado

**Sintoma**: `column "metric" does not exist` em queries admin.

**Causa**: PR-A merged sem migration rodar.

**Fix**:
```bash
dbmate up
poetry run pytest tests/unit/evals/test_persist.py  # revalidar schema
```

### 6.2 FK violation em golden_traces

**Sintoma**: `insert or update on table "golden_traces" violates foreign key constraint`.

**Causa**: migration UNIQUE trace_id (migration 2) nao rodou antes do CREATE TABLE golden_traces (migration 5).

**Fix**: `dbmate rollback && dbmate up` — ordem garantida por nome do arquivo.

### 6.3 Cron nao executa

**Sintoma**: `autonomous_resolution_cron` nao popula `auto_resolved`.

**Diagnostico**:
```bash
# 1. Check scheduler started
grep 'handoff_scheduler_started\|evals_scheduler_started' logs/*.log

# 2. Check lock contention
psql "$DATABASE_URL" -c "
  SELECT pid, query, state, wait_event
  FROM pg_stat_activity
  WHERE query LIKE '%pg_try_advisory_lock%';
"

# 3. Trigger manualmente (bypass scheduler)
curl -X POST http://localhost:8050/admin/debug/run_cron -d '{"task": "autonomous_resolution_cron"}'
```

### 6.4 DeepEval retorna scores invalidos

**Sintoma**: logs `eval_score_clip_applied` frequentes.

**Diagnostico**: `gpt-4o-mini` pode retornar decimal fora de [0,1] em edge cases de prompt. Wrapper pydantic clipa.

**Fix**: se taxa >5%, revisar prompt template de DeepEval metric wrapper.

### 6.5 Coverage baixa em shadow

**Sintoma**: `coverage_pct` <50% apos 7d de shadow.

**Diagnostico**:
```bash
# Ratio de erros
grep 'eval_score_persist_failed' logs/*.log | wc -l
grep 'eval_scores_persisted_total{status="ok"}' logs/*.log | wc -l
```

**Causas comuns**:
- DB connection pool exaustion (aumentar pool size).
- FK violation (conversation_id nao foi criado antes da persist — bug de race no pipeline).
- Pipeline step `evaluate` nao esta agendando task (bug de integracao).

---

## 7. Runbooks operacionais

- **Calibrar thresholds alerta** — `docs/runbooks/evals-thresholds.md` (criado em PR-C).
- **Golden curation review** — `docs/runbooks/golden-curation.md` (criado em PR-C).
- **DeepEval cost alert response** — `docs/runbooks/deepeval-cost.md` (criado em PR-B).

---

## 8. References

- [plan.md](./plan.md) — PRs + cronograma + gates.
- [research.md](./research.md) — alternativas + schema research.
- [data-model.md](./data-model.md) — schemas + migrations SQL.
- [contracts/evaluator-persist.md](./contracts/evaluator-persist.md) — Protocol EvalPersister.
- [contracts/openapi.yaml](./contracts/openapi.yaml) — endpoints admin.
- [spec.md](./spec.md) — 54 FRs + 12 SCs + 22 assumptions.
