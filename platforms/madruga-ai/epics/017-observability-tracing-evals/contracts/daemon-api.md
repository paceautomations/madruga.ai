# API Contract: Daemon Observability Endpoints

**Date**: 2026-04-02 | **Epic**: 017-observability-tracing-evals
**Base URL**: `http://localhost:8040`

## Authentication

Nenhuma. Single-user, localhost only. CORS limitado a `localhost:4321` e `localhost:3000`.

## Endpoints

### GET /api/traces

Lista traces com paginacao e filtros.

**Query Parameters**:

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `platform_id` | string | yes | — | Plataforma |
| `limit` | int | no | 50 | Max resultados |
| `offset` | int | no | 0 | Paginacao |
| `status` | string | no | — | Filtro: `running`, `completed`, `failed`, `cancelled` |

**Response 200**:

```json
{
  "traces": [
    {
      "trace_id": "a1b2c3d4",
      "platform_id": "madruga-ai",
      "epic_id": "017-observability-tracing-evals",
      "mode": "l2",
      "status": "completed",
      "total_nodes": 11,
      "completed_nodes": 11,
      "total_tokens_in": 50000,
      "total_tokens_out": 30000,
      "total_cost_usd": 1.23,
      "total_duration_ms": 300000,
      "started_at": "2026-04-02T10:00:00Z",
      "completed_at": "2026-04-02T10:05:00Z",
      "span_count": 11,
      "completed_spans": 11
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

**Response 400**: `{"error": "platform_id is required"}`

---

### GET /api/traces/{trace_id}

Detalhes de um trace com todos os spans e eval scores.

**Path Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `trace_id` | string | ID do trace |

**Response 200**:

```json
{
  "trace": {
    "trace_id": "a1b2c3d4",
    "platform_id": "madruga-ai",
    "epic_id": "017-observability-tracing-evals",
    "mode": "l2",
    "status": "completed",
    "total_nodes": 11,
    "completed_nodes": 11,
    "total_tokens_in": 50000,
    "total_tokens_out": 30000,
    "total_cost_usd": 1.23,
    "total_duration_ms": 300000,
    "started_at": "2026-04-02T10:00:00Z",
    "completed_at": "2026-04-02T10:05:00Z"
  },
  "spans": [
    {
      "run_id": "e5f6a7b8",
      "node_id": "specify",
      "status": "completed",
      "tokens_in": 5000,
      "tokens_out": 3000,
      "cost_usd": 0.12,
      "duration_ms": 30000,
      "error": null,
      "started_at": "2026-04-02T10:00:00Z",
      "completed_at": "2026-04-02T10:00:30Z"
    }
  ],
  "eval_scores": [
    {
      "score_id": "c9d0e1f2",
      "node_id": "specify",
      "run_id": "e5f6a7b8",
      "dimension": "quality",
      "score": 7.5,
      "metadata": "{\"method\": \"heuristic\"}",
      "evaluated_at": "2026-04-02T10:00:31Z"
    }
  ]
}
```

**Response 404**: `{"error": "trace not found"}`

---

### GET /api/evals

Eval scores com filtros por plataforma e node.

**Query Parameters**:

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `platform_id` | string | yes | — | Plataforma |
| `node_id` | string | no | — | Filtro por node |
| `dimension` | string | no | — | Filtro por dimensao |
| `limit` | int | no | 100 | Max resultados |

**Response 200**:

```json
{
  "scores": [
    {
      "score_id": "c9d0e1f2",
      "trace_id": "a1b2c3d4",
      "platform_id": "madruga-ai",
      "epic_id": "017-observability-tracing-evals",
      "node_id": "specify",
      "run_id": "e5f6a7b8",
      "dimension": "quality",
      "score": 7.5,
      "metadata": "{\"method\": \"heuristic\"}",
      "evaluated_at": "2026-04-02T10:00:31Z"
    }
  ],
  "total": 120
}
```

---

### GET /api/stats

Metricas agregadas por periodo (dia).

**Query Parameters**:

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `platform_id` | string | yes | — | Plataforma |
| `days` | int | no | 30 | Janela em dias (max 90) |

**Response 200**:

```json
{
  "stats": [
    {
      "day": "2026-04-01",
      "runs": 3,
      "total_cost": 2.45,
      "total_tokens_in": 150000,
      "total_tokens_out": 90000,
      "avg_duration_ms": 250000
    }
  ],
  "period_days": 30,
  "summary": {
    "total_runs": 42,
    "total_cost": 35.67,
    "total_tokens_in": 2100000,
    "total_tokens_out": 1260000,
    "avg_cost_per_run": 0.85
  }
}
```

---

### GET /api/export/csv

Export de dados em formato CSV.

**Query Parameters**:

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `platform_id` | string | yes | — | Plataforma |
| `entity` | string | yes | — | `traces`, `spans`, ou `evals` |
| `days` | int | no | 90 | Janela em dias |

**Response 200**:
- Content-Type: `text/csv; charset=utf-8`
- Content-Disposition: `attachment; filename="traces_madruga-ai_2026-04-02.csv"`
- Body: CSV com headers na primeira linha

**Exemplo (entity=traces)**:
```csv
trace_id,platform_id,epic_id,mode,status,total_nodes,completed_nodes,total_tokens_in,total_tokens_out,total_cost_usd,total_duration_ms,started_at,completed_at
a1b2c3d4,madruga-ai,017-observability-tracing-evals,l2,completed,11,11,50000,30000,1.23,300000,2026-04-02T10:00:00Z,2026-04-02T10:05:00Z
```

**Response 400**: `{"error": "entity must be one of: traces, spans, evals"}`

---

## Error Responses

Todos os endpoints retornam erros no formato:

```json
{
  "error": "descricao do erro"
}
```

| HTTP Code | When |
|-----------|------|
| 400 | Parametro obrigatorio ausente ou invalido |
| 404 | Recurso nao encontrado (trace_id) |
| 500 | Erro interno (DB inacessivel, etc.) |

## CORS

```python
CORSMiddleware(
    allow_origins=["http://localhost:4321", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

## Rate Limiting

Nenhum. Single-user, localhost only. Polling do portal a cada 10s = 6 req/min por tab ativa.
