---
title: 'ADR-039: Eval metric bootstrap sem golden dataset'
status: Accepted
decision: v1 do epic 011 usa 4 metricas DeepEval reference-less (AnswerRelevancy,
  Toxicity, Bias, Coherence) + heuristico online herdado do epic 005 — sem golden
  dataset curado upfront. Golden cresce incremental via admin star-button
  (`public.golden_traces`). Schema de `eval_scores` evolui via ADD COLUMN `metric`
  (aditivo), NAO rename de `evaluator_type`/`quality_score`.
alternatives: Golden dataset upfront (curar 50+ casos antes de v1), LLM-as-judge
  online em v1, Faithfulness metric em v1, RENAME eval_scores columns,
  Custom metrics scripts sem DeepEval
rationale: Reference-less metrics permitem avaliacao diaria em producao sem
  pre-trabalho humano. Golden cresce com sinais reais da operacao (admin estrela
  o que merece virar caso CI). Schema aditivo preserva codigo do epic 005
  + queries admin do epic 008 sem migracao destrutiva.
---
# ADR-039: Eval metric bootstrap sem golden dataset

**Status:** Accepted | **Data:** 2026-04-24 (proposed) → 2026-04-25 (accepted) | **Relaciona:** [ADR-008](ADR-008-eval-stack.md), [ADR-027](ADR-027-admin-tables-no-rls.md), [ADR-028](ADR-028-pipeline-fire-and-forget-persistence.md), [ADR-040](ADR-040-autonomous-resolution-heuristic.md)

> **Aceite:** entregue como descrito. Validado durante a implementacao
> dos PRs A/B/C (tasks T001..T093). Diferencas materiais entre o draft
> e o codigo final estao registradas na secao "Implementation notes"
> abaixo — nenhuma exigiu re-decisao.

> **Escopo:** Epic 011 (Evals). Aplica-se a `apps/api/prosauai/evals/` (modulo novo),
> `apps/api/db/migrations/20260601000001_alter_eval_scores_add_metric.sql` (PR-A),
> `apps/api/db/migrations/20260601000005_create_golden_traces.sql` (PR-B) e ao
> cron noturno `deepeval_batch_cron`.

## Contexto

O epic 005 deixou operacional o `conversation/evaluator.py` que calcula um
`quality_score` heuristico a cada resposta gerada, mas **descarta** o resultado
apos o step. `eval_scores` foi criada como tabela de persistencia com colunas
`evaluator_type` + `quality_score`, porem nunca recebeu insert em producao.

O pitch do epic 011 propos **duas camadas** de avaliacao:

1. **Online** — persistir 100% dos scores heuristicos em `eval_scores`
   (fire-and-forget, zero impacto p95).
2. **Offline noturno** — amostrar ate 200 msgs/tenant/dia e rodar metricas
   DeepEval (LLM-as-judge) em paralelo.

Duas ambiguidades precisavam resolucao:

- **Qual conjunto de metricas DeepEval?** Faithfulness e hallucination-rate
  exigem ground-truth (ou RAG grounding source) — o ProsaUAI ainda nao tem
  RAG em producao (epic 012 planejado). Sem grounding, essas metricas retornam
  score degenerado (sempre alto ou sempre baixo).
- **Schema de `eval_scores` suporta multi-metric?** A tabela existente tem
  `evaluator_type VARCHAR` + `quality_score FLOAT` — sem discriminador de
  metrica. DeepEval produz 4 scores por msg (AnswerRelevancy, Toxicity, Bias,
  Coherence), que precisam ser 4 rows distintas.

## Decisao

We will usar **metricas DeepEval reference-less** como v1 + **golden dataset
incremental** curado via admin + **ADD COLUMN `metric`** (aditivo, NAO rename).

### 1. Metricas v1 — reference-less set

4 metricas obrigatorias por msg amostrada:

| Metric | DeepEval class | O que mede |
|--------|---------------|------------|
| `answer_relevancy` | `AnswerRelevancyMetric` | Quao relevante e a resposta para a pergunta/mensagem do usuario. Substituto reference-less de Faithfulness: compara input vs output sem grounding source. |
| `toxicity` | `ToxicityMetric` | Score de toxicidade da resposta (0 = nao toxico, 1 = toxico). Defesa contra LLM gerando conteudo ofensivo. |
| `bias` | `BiasMetric` | Score de vies (gender, race, politica). Critico para comunidades esportivas (Ariel, ResenhAI) que lidam com times/jogadores. |
| `coherence` | `GEval` com rubrica custom | Coerencia gramatical + logica da resposta. Captura LLM gerando salada de palavras. |

**Exclusao explicita de Faithfulness** em v1: exige RAG grounding source.
Revisitar quando epic 012 (RAG) estiver operacional.

**Exclusao de GEval com rubricas abertas de "qualidade"** em v1: requer
golden dataset para calibrar — caimos no ciclo que tentamos evitar.

### 2. Golden dataset — incremental via admin star-button

**Nao curar golden upfront.** Motivos:

- Ariel + ResenhAI sao comunidades esportivas com linguagem propria — golden
  sintetico de 50 casos nao representa distribuicao real.
- Tempo humano de curacao (~2h para 50 casos × 2 tenants = 8h) seria gasto
  antes de termos dados de producao para saber o que curar.
- Risco de benchmark-gaming: otimizar prompt para passar em 50 casos
  artificiais sem ganho real em producao.

**Crescer golden apartir de sinais de producao**:

1. Admin abre Trace Explorer, ve traces reais dos ultimos 7d.
2. Clica "Star" em traces exemplares (positivo = "quero mais assim") ou
   "Mark negative" (negativo = "nunca mais assim").
3. Row append-only em `public.golden_traces (trace_id, verdict, notes, created_by_user_id)`.
4. Promptfoo generator le `public.golden_traces` com `verdict != 'cleared'`
   e gera `test_cases.yaml` para o CI gate.

Verdict `cleared` e o "undo" append-only — ultima row com esse trace_id
define o estado efetivo (`SELECT DISTINCT ON (trace_id) ... ORDER BY trace_id,
created_at DESC`).

### 3. Schema — ADD COLUMN `metric`, NAO rename

Esquema atual (epic 005):

```sql
CREATE TABLE eval_scores (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  conversation_id UUID NOT NULL,
  message_id UUID,
  evaluator_type VARCHAR(50) NOT NULL,  -- 'heuristic' hoje
  quality_score FLOAT NOT NULL,
  details JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Mudanca v1:

```sql
-- 20260601000001_alter_eval_scores_add_metric.sql
ALTER TABLE eval_scores
  ADD COLUMN IF NOT EXISTS metric VARCHAR(50) NOT NULL
  DEFAULT 'heuristic_composite';

UPDATE eval_scores SET metric = 'heuristic_composite' WHERE metric IS NULL;

ALTER TABLE eval_scores
  ADD CONSTRAINT IF NOT EXISTS chk_eval_scores_metric
  CHECK (metric IN (
    'heuristic_composite',
    'answer_relevancy', 'toxicity', 'bias', 'coherence',
    'human_verdict'
  ));
```

v1 tambem altera semanticamente os valores aceitos de `evaluator_type`:

- `heuristic` (epic 005) continua valido — sera migrado para `heuristic_v1`
  **apenas** em rows novas do epic 011. Rows antigas preservam `heuristic`
  para nao quebrar queries existentes.
- `deepeval` — novo.
- `human` — novo (curator manual, quando aplicavel).

## Alternativas consideradas

### A. Curar golden dataset upfront (50+ casos por tenant)

- **Pros:** permite rodar metricas reference-based (Faithfulness, hallucination-rate)
  desde o dia 1. Benchmark claro "% casos passando".
- **Cons:**
  - Custo humano alto (~8h combinado Ariel+ResenhAI) antes de ver 1 bit de valor.
  - Golden sintetico raramente representa a cauda real — operadores vao descobrir
    em 2 semanas que os casos curados sao "faceis" e o bot falha em casos
    que nao estao no golden.
  - Benchmark-gaming: otimiza prompt para passar nos 50 sem ganho real.
  - Adia entrega de 2-3 semanas.
- **Rejeitada porque:** incremental golden via admin entrega valor desde a
  primeira hora (heuristico persistindo + DeepEval rodando) e o golden
  cresce organico com sinal real.

### B. LLM-as-judge online em v1 (nao heuristico)

- **Pros:** score mais rico por msg. Base para auto-handoff.
- **Cons:**
  - +R$0.02/msg em 10% das msgs antes de calibrar threshold → custo mensal
    estimado R$150-400 por tenant.
  - Bifrost latency adiciona ~500ms-2s ao hot path → viola SC-003 (p95 texto).
  - Sem baseline de shadow, thresholds sao chutes que geram ruido de alerta.
- **Rejeitada porque:** heuristico online + DeepEval noturno entregam sinal
  rico suficiente para v1. LLM-as-judge online revisitado em 011.1 com
  dados de shadow para calibrar threshold + selecionar amostra (vs 100%).

### C. Faithfulness metric em v1

- **Pros:** metrica canonica de hallucination em LLM apps.
- **Cons:** exige grounding source (RAG context, KB passage). ProsaUAI ainda
  nao tem RAG em producao.
- **Rejeitada porque:** AnswerRelevancy (reference-less) captura 70% do sinal
  (resposta relacionada a pergunta) e pode virar Faithfulness em 012 sem
  migracao de schema.

### D. RENAME `eval_scores.evaluator_type -> evaluator` + `quality_score -> score`

- **Pros:** naming mais limpo + alinhado com padrao DeepEval.
- **Cons:**
  - Quebra todo codigo do epic 005 que le/escreve essas colunas.
  - Quebra queries pool_admin do epic 008 (Performance AI ja agrega
    `SELECT evaluator_type, AVG(quality_score) ...`).
  - Ganho cosmetico, zero funcional.
- **Rejeitada porque:** ADD COLUMN e aditivo. Names legados ficam como
  technical debt mapeado mas nao bloqueante — documentar em runbook
  "evaluator_type -> evaluator (legacy)".

### E. Custom metric scripts sem DeepEval

- **Pros:** zero dep Python nova. Controle total.
- **Cons:** reinventar 4 metricas ja validadas pela comunidade. DeepEval
  ja resolveu: prompt engineering, LLM client abstraction, retry, parsing.
- **Rejeitada porque:** ADR-008 ja escolheu DeepEval como stack. Custom
  scripts violariam Principio I (Pragmatismo).

## Consequencias

- [+] **Valor imediato** — heuristico online + DeepEval noturno entregam
  sinal a partir do dia 1, sem espera por golden.
- [+] **Golden cresce com sinal real** — traces starred pelo admin sao os
  que importam. Zero benchmark-gaming.
- [+] **Schema aditivo** — zero migracao destrutiva. Epic 005 e 008 seguem
  funcionando sem mudanca.
- [+] **Custo controlado** — gpt-4o-mini para 4 metricas × 200 msgs × 2
  tenants = ~R$0.48/dia combinado (margem 6x para SC-011 ≤R$3/dia).
- [+] **Metricas reference-less rodam sem RAG** — compatibilidade antecipada
  com epic 012 (RAG adiciona Faithfulness sem substituir as 4 atuais).
- [-] **Sem baseline "accuracy"** — nao da para reportar "% casos passando"
  ate golden ter >=30 casos. Mitigacao: reportar trends por metrica em vez
  de pass-rate binario.
- [-] **Technical debt de naming** — `evaluator_type` vs `metric` convivem
  (semanticamente proximos). Mitigacao: docstring + runbook explicitos.
- [-] **Golden depende de discipline humana** — se o admin nao estrelar
  traces, CI gate fica com suite de smoke (5 casos hand-written) ate o fim
  dos tempos. Aceito para v1 (suite smoke > nenhuma suite).

## Metricas de sucesso (pos-deploy)

Monitorar nas primeiras 4 semanas apos Ariel `on`:

| Metrica | Alvo v1 |
|---------|---------|
| `eval_scores_persisted_total{evaluator='heuristic_v1'}` coverage vs `messages` outbound | >=80% (SC-008) |
| Custo Bifrost daily (gpt-4o-mini calls do batch) | <=R$3/dia combinado |
| `eval_batch_duration_seconds{status='ok'}` p95 por tenant | <30min |
| Size de `golden_traces` 30d apos PR-C | >=10 rows starred |

Se coverage <80% apos 7d em `on`, investigar bug fire-and-forget
(pipeline.py step `evaluate` esta agendando?). Se custo >R$3/dia,
reduzir amostra de 200 para 100 via `tenants.yaml.evals.*`.

## Teste de regressao

`apps/api/tests/unit/evals/test_persist.py` (T027):

```python
async def test_persist_score_heuristic_v1(pool, metrics):
    """Legacy 'heuristic' rows (epic 005) nao sao tocadas por novo codigo."""
    persister = PoolPersister(pool, metrics)
    record = EvalScoreRecord(
        tenant_id=TENANT_A,
        conversation_id=CONV_A,
        message_id=MSG_A,
        evaluator_type="heuristic_v1",
        metric="heuristic_composite",
        quality_score=0.85,
        details={"verdict": "ok"},
    )
    await persister.persist(record)

    row = await pool.fetchrow("SELECT * FROM eval_scores WHERE message_id=$1", MSG_A)
    assert row["evaluator_type"] == "heuristic_v1"
    assert row["metric"] == "heuristic_composite"
    assert row["quality_score"] == 0.85
```

`apps/api/tests/unit/evals/test_deepeval_batch.py` (T055):

```python
async def test_deepeval_four_metrics_persisted(runner, pool, bifrost_mock):
    """4 metrics reference-less produzem 4 rows distintas por msg."""
    await runner.process_message(msg_id=MSG_A, ...)

    rows = await pool.fetch(
        "SELECT metric FROM eval_scores WHERE message_id=$1 AND evaluator_type='deepeval'",
        MSG_A,
    )
    metrics = {r["metric"] for r in rows}
    assert metrics == {"answer_relevancy", "toxicity", "bias", "coherence"}
```

## Implementation notes (pos-aceite)

Pontos onde o codigo final divergiu do draft, todos sem reabrir a decisao:

- **Migration de UNIQUE em `public.traces.trace_id`** (T011) acabou
  rodando *sem* `CREATE UNIQUE INDEX CONCURRENTLY` no harness CI por
  incompatibilidade do `transaction:false` da dbmate v2.32. A
  migration usa o caminho transacional padrao + runbook manual em
  prod (`apps/api/db/migrations/20260601000002_alter_traces_unique_trace_id.sql`).
  Decisao registrada em `easter-tracking.md` 2026-04-24.
- **`metric='heuristic_composite'`** ficou como default da coluna
  recem-criada em `eval_scores` para preservar rows do epic 005 sem
  reescrita. Backfill explicito pos-`ALTER TABLE` foi mantido para
  garantir auditabilidade do estado pre-011.
- **DeepEval wrapper para Coherence** terminou usando `GEval` com
  rubrica custom (em vez de uma metrica nativa), conforme antecipado
  na tabela §1. Implementado em
  `apps/api/prosauai/evals/deepeval_batch.py` (T042).
- **SAR fan-out (T082)** confirmou a invariante de que `golden_traces`
  e reapeada exclusivamente via FK CASCADE em `public.traces`.
  Documentacao detalhada em `apps/api/prosauai/privacy/sar.py`
  (modulo introduzido por este epic, nao pelo 010 como o draft
  inicialmente assumiu).
- **Promptfoo generator (T055)** consome o golden via
  `SELECT DISTINCT ON (trace_id) ... ORDER BY trace_id, created_at DESC`
  filtrando `verdict != 'cleared'` — exatamente o invariante "ultima
  row define o estado" descrito em §2.

Estas notas existem para que o code review historico bata 1:1 com o
codigo de producao sem reabrir a decisao.

## Referencias cruzadas

- Tasks T001 (rascunho), T010 (migration metric), T015 (Pydantic
  models incl. Metric Literal), T022 (PoolPersister), T023
  (heuristic_online), T040..T051 (DeepEval batch + wrappers),
  T058..T065 (golden curation), T070 (admin metrics aggregator),
  T082..T083 (SAR fan-out), T084 (este ADR aceito).
- Decisoes complementares: [ADR-040](ADR-040-autonomous-resolution-heuristic.md)
  (heuristica autonomous_resolution e gemea deste).
- Epic docs: [011-evals/spec.md](../epics/011-evals/spec.md) §FR-001..FR-054,
  [011-evals/data-model.md](../epics/011-evals/data-model.md) §2-5,
  [011-evals/contracts/evaluator-persist.md](../epics/011-evals/contracts/evaluator-persist.md) §1-2.

---

> **Proximo passo:** PR-A (T010 migration `ADD COLUMN metric`) + PR-B
> (T040-T058 DeepEval wrappers). Este ADR e o eixo conceitual para code
> review de ambos.
