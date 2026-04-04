# Data Model: Observability, Tracing & Evals

**Date**: 2026-04-02 | **Epic**: 017-observability-tracing-evals

## Entity Relationship

```
traces 1───* pipeline_runs (spans)
traces 1───* eval_scores
pipeline_runs 1───* eval_scores
platforms 1───* traces
```

## Entities

### Trace (NEW — `traces` table)

Representa uma execucao completa do pipeline (grupo de spans).

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| `trace_id` | TEXT | PK | UUID gerado no inicio do pipeline run |
| `platform_id` | TEXT | FK → platforms, NOT NULL | Plataforma executada |
| `epic_id` | TEXT | nullable | Epic slug (NULL para L1) |
| `mode` | TEXT | CHECK ('l1', 'l2'), NOT NULL, DEFAULT 'l1' | Modo do pipeline |
| `status` | TEXT | CHECK ('running', 'completed', 'failed', 'cancelled'), NOT NULL, DEFAULT 'running' | Estado do trace |
| `total_nodes` | INTEGER | DEFAULT 0 | Total de nodes no pipeline |
| `completed_nodes` | INTEGER | DEFAULT 0 | Nodes completados ate o momento |
| `total_tokens_in` | INTEGER | nullable | Soma de tokens de entrada |
| `total_tokens_out` | INTEGER | nullable | Soma de tokens de saida |
| `total_cost_usd` | REAL | nullable | Custo total em USD |
| `total_duration_ms` | INTEGER | nullable | Duracao total em ms |
| `started_at` | TEXT | NOT NULL, DEFAULT datetime('now') | Inicio da execucao |
| `completed_at` | TEXT | nullable | Fim da execucao |

**Indices**:
- `idx_traces_platform` ON (platform_id)
- `idx_traces_status` ON (status)
- `idx_traces_started` ON (started_at)

### Pipeline Run / Span (MODIFIED — `pipeline_runs` table)

Coluna adicionada via migration:

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| `trace_id` | TEXT | FK → traces (nullable) | Trace pai. NULL para runs pre-017 |

**Novo indice**:
- `idx_pipeline_runs_trace` ON (trace_id)

**Node-to-Skill mapping**: `node_id` maps 1:1 to the pipeline skill that produced it.
For L1 nodes, `node_id` matches the skill suffix (e.g., `node_id="vision"` → `madruga:vision`).
For L2 nodes, `node_id` matches the SpecKit skill (e.g., `node_id="specify"` → `speckit.specify`).
Implement tasks use the format `implement:<task_id>` (e.g., `implement:T003`).

**Campos existentes agora populados** (antes sempre NULL):
- `tokens_in` — input tokens do Claude CLI
- `tokens_out` — output tokens do Claude CLI
- `cost_usd` — custo em USD do node
- `duration_ms` — duracao em ms do node

### Eval Score (NEW — `eval_scores` table)

Avaliacao de qualidade de um artefato gerado por um node.

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| `score_id` | TEXT | PK | UUID gerado na avaliacao |
| `trace_id` | TEXT | FK → traces, nullable | Trace associado |
| `platform_id` | TEXT | FK → platforms, NOT NULL | Plataforma |
| `epic_id` | TEXT | nullable | Epic slug |
| `node_id` | TEXT | NOT NULL | Node avaliado |
| `run_id` | TEXT | FK → pipeline_runs, nullable | Run especifico |
| `dimension` | TEXT | CHECK ('quality', 'adherence_to_spec', 'completeness', 'cost_efficiency'), NOT NULL | Dimensao avaliada |
| `score` | REAL | CHECK (>= 0 AND <= 10), NOT NULL | Score de 0 a 10 |
| `metadata` | TEXT | nullable | JSON com dados adicionais |
| `evaluated_at` | TEXT | NOT NULL, DEFAULT datetime('now') | Timestamp da avaliacao |

**Indices**:
- `idx_eval_scores_trace` ON (trace_id)
- `idx_eval_scores_node` ON (platform_id, node_id)
- `idx_eval_scores_run` ON (run_id)

## Migration SQL (010_observability.sql)

```sql
-- Trace: agrupa spans (pipeline_runs) de uma execucao completa
CREATE TABLE IF NOT EXISTS traces (
    trace_id       TEXT PRIMARY KEY,
    platform_id    TEXT NOT NULL,
    epic_id        TEXT,
    mode           TEXT NOT NULL DEFAULT 'l1'
                   CHECK (mode IN ('l1', 'l2')),
    status         TEXT NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    total_nodes    INTEGER DEFAULT 0,
    completed_nodes INTEGER DEFAULT 0,
    total_tokens_in  INTEGER,
    total_tokens_out INTEGER,
    total_cost_usd   REAL,
    total_duration_ms INTEGER,
    started_at     TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at   TEXT,
    FOREIGN KEY (platform_id) REFERENCES platforms(platform_id)
);

-- Link pipeline_runs (spans) to parent trace
ALTER TABLE pipeline_runs ADD COLUMN trace_id TEXT REFERENCES traces(trace_id);

-- Eval scores: 4 dimensoes por node avaliado
CREATE TABLE IF NOT EXISTS eval_scores (
    score_id     TEXT PRIMARY KEY,
    trace_id     TEXT,
    platform_id  TEXT NOT NULL,
    epic_id      TEXT,
    node_id      TEXT NOT NULL,
    run_id       TEXT,
    dimension    TEXT NOT NULL
                 CHECK (dimension IN ('quality', 'adherence_to_spec',
                        'completeness', 'cost_efficiency')),
    score        REAL NOT NULL CHECK (score >= 0 AND score <= 10),
    metadata     TEXT,
    evaluated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (trace_id) REFERENCES traces(trace_id),
    FOREIGN KEY (platform_id) REFERENCES platforms(platform_id),
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

-- Indices para queries frequentes
CREATE INDEX IF NOT EXISTS idx_traces_platform ON traces(platform_id);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_started ON traces(started_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_trace ON pipeline_runs(trace_id);
CREATE INDEX IF NOT EXISTS idx_eval_scores_trace ON eval_scores(trace_id);
CREATE INDEX IF NOT EXISTS idx_eval_scores_node ON eval_scores(platform_id, node_id);
CREATE INDEX IF NOT EXISTS idx_eval_scores_run ON eval_scores(run_id);
```

## Validation Rules

### Trace
- `trace_id` e UUID v4 gerado por `uuid.uuid4().hex`
- `status` transiciona: `running` → `completed|failed|cancelled`
- `completed_at` e preenchido somente quando `status` != `running`
- Metricas agregadas (`total_*`) sao calculadas somando spans na `complete_trace()`

### Eval Score
- Cada node pode ter ate 4 eval_scores (uma por dimensao)
- `score` e REAL entre 0.0 e 10.0 (permite decimais)
- `metadata` e JSON livre (ex: `{"method": "heuristic", "judge_score": 85}`)
- Duplicate check: nao inserir se ja existe score para (run_id, dimension)

### Pipeline Run (Span)
- `trace_id` nullable para compatibilidade com dados pre-017
- `tokens_in`, `tokens_out`, `cost_usd`, `duration_ms` agora populados pelo executor
- Se Claude CLI nao retornar JSON valido, campos ficam NULL (best-effort)

## State Transitions

### Trace Lifecycle

```
[created] → running → completed   (pipeline terminou ok)
                    → failed      (node falhou, pipeline abortou)
                    → cancelled   (interrupted / circuit breaker)
```

### Eval Score Lifecycle

Eval scores sao imutaveis — criados uma vez apos o node completar. Se o node re-executar (retry), novos scores sao criados com novo `run_id`.

## Queries Frequentes

### Top-level: listar traces recentes
```sql
SELECT t.*, 
       COUNT(pr.run_id) as span_count,
       SUM(CASE WHEN pr.status='completed' THEN 1 ELSE 0 END) as completed_spans
FROM traces t
LEFT JOIN pipeline_runs pr ON pr.trace_id = t.trace_id
WHERE t.platform_id = ?
GROUP BY t.trace_id
ORDER BY t.started_at DESC
LIMIT ? OFFSET ?
```

### Spans de um trace
```sql
SELECT * FROM pipeline_runs
WHERE trace_id = ?
ORDER BY started_at ASC
```

### Eval scores por node (trend)
```sql
SELECT es.*, pr.started_at as run_date
FROM eval_scores es
JOIN pipeline_runs pr ON es.run_id = pr.run_id
WHERE es.platform_id = ? AND es.node_id = ?
ORDER BY es.evaluated_at DESC
LIMIT ?
```

### Stats agregados por periodo
```sql
SELECT 
    date(t.started_at) as day,
    COUNT(*) as runs,
    SUM(t.total_cost_usd) as total_cost,
    SUM(t.total_tokens_in) as total_tokens_in,
    SUM(t.total_tokens_out) as total_tokens_out,
    AVG(t.total_duration_ms) as avg_duration
FROM traces t
WHERE t.platform_id = ? 
  AND t.started_at >= date('now', ?)
GROUP BY date(t.started_at)
ORDER BY day
```

### Cleanup (retention 90 dias)
```sql
-- Ordem: dependentes primeiro
DELETE FROM eval_scores WHERE evaluated_at < datetime('now', '-90 days');
DELETE FROM pipeline_runs WHERE trace_id IN (
    SELECT trace_id FROM traces WHERE started_at < datetime('now', '-90 days')
);
DELETE FROM traces WHERE started_at < datetime('now', '-90 days');
```
