---
id: 017
title: "Observability, Tracing & Evals"
status: shipped
priority: 4
updated: 2026-04-02
delivered_at: 2026-04-04
---
# Observability, Tracing & Evals

## Problem

Adicionar observabilidade real-time, tracing hierarquico e eval scoring ao pipeline L2 automatizado. Dados persistidos em SQLite (extendendo schema existente), dashboards no portal Astro existente, evals via Judge pattern + metricas quantitativas.

## Dependencies

- Depends on: 016 (easter 24/7), 013 (DAG executor)
- Blocks: nenhum

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|---------|----------------------|
| 1 | Infra observabilidade | SQLite-only (sem Langfuse/Phoenix). Extender schema existente com tabelas traces/spans/eval_scores | ADR-016 (structlog + SQLite metrics + Sentry), ADR-012 (WAL mode) |
| 2 | Captura de tokens/cost | Parse JSON output do `claude -p --output-format json` no dag_executor para popular `pipeline_runs.tokens_in/out/cost_usd/duration_ms` | ADR-010 (claude -p subprocess), ADR-017 (custom DAG executor) |
| 3 | Granularidade spans | Node-level apenas em V1. LLM-call level futuro via MCP/hooks | ADR-017 (custom DAG executor) |
| 4 | Evals | Judge pattern (4 personas) para evals qualitativos + metricas quantitativas simples (output size, time, tokens, errors). Sem DeepEval em V1 | ADR-019 (subagent judge pattern) |
| 5 | Real-time portal | Polling 10s via fetch periodico. Easter FastAPI expoe endpoints de dados. Portal React islands consomem | ADR-016 (dashboard no portal Astro), ADR-006 (asyncio easter) |
| 6 | Schema eval_scores | 4 dimensoes fixas (quality, adherence_to_spec, completeness, cost_efficiency) + campo `metadata` JSON | ADR-012 (SQLite WAL) |
| 7 | Retention | 90 dias no SQLite + opcao de export CSV para analise historica | ADR-016 (cleanup periodico) |
| 8 | Portal UX | 1 pagina `/[platform]/observability` com tabs (Runs, Traces, Evals, Cost). Lazy-load por tab se necessario | ADR-003 (Astro Starlight portal) |

## Resolved Gray Areas

### 1. Por que nao Langfuse/Phoenix?
ADR-016 define "graduar para OTel+Grafana quando 3+ servicos". Hoje temos 1 easter. SQLite-only cobre 80% do valor com zero infra extra. Langfuse exigiria Docker + Postgres + ClickHouse (~1GB RAM) e fragmentaria a UI.

### 2. Por que node-level e nao LLM-call-level?
O dag_executor despacha `claude -p` como subprocess opaco. Nao temos visibilidade intra-subprocess sem instrumentacao do Claude CLI. Node-level (start, end, tokens, cost, status, error) e o que temos disponivel. Expandir para LLM-call level requer MCP ou hooks do Claude Code — escopo futuro.

### 3. Por que Judge e nao DeepEval?
Judge ja esta validado (epic 015, 4 personas + decision classifier). DeepEval adiciona ~20 packages de dependencia para metricas genericas (faithfulness, relevance) que nao mapeiam diretamente para "qualidade de spec" ou "aderencia ao blueprint". Metricas quantitativas (tokens, cost, duration, output size) sao triviais de capturar sem framework.

### 4. Por que polling e nao SSE?
SSE e mais elegante mas requer client-side streaming no Astro (islands hydration). Polling 10s com fetch periodico e trivial em React, e a latencia de 10s e aceitavel para monitoramento humano. O easter ja tem FastAPI — basta adicionar 2-3 endpoints JSON.

## Applicable Constraints

| Constraint | Source | Impacto |
|-----------|--------|---------|
| Python stdlib + pyyaml (deps minimas) | CLAUDE.md | Sem deps novas para tracing/evals. structlog ja esta no projeto |
| SQLite WAL mode, single-writer | ADR-012 | Traces/spans/evals compartilham a mesma DB. Writes serializados ok para easter single-user |
| Portal Astro + React islands | ADR-003 | Componentes React para dashboards, fetch via useEffect polling |
| Easter FastAPI + asyncio | ADR-006 | Endpoints de dados no easter existente |
| LOC estimates x1.5-2x | CLAUDE.md | Estimar ~400-600 LOC real (migration + executor changes + API endpoints + React components) |
| Scripts < 300 LOC: batch + testes | CLAUDE.md | Cada modulo < 300 LOC escrito completo com testes de uma vez |

## Suggested Approach

### Fase 1: Schema + Captura (backend)
1. **Migration 010**: tabelas `traces`, `spans`, `eval_scores` + indices (009 ja usada por `drafted` status)
2. **dag_executor.py**: criar trace no inicio do pipeline run, span por node, parse JSON output para tokens/cost
3. **db.py**: funcoes para insert/query traces, spans, eval_scores
4. **Easter endpoints**: GET `/api/traces`, `/api/traces/{id}/spans`, `/api/evals`, `/api/stats`

### Fase 2: Evals (scoring)
5. **eval_scorer.py**: post-node scoring usando Judge pattern (qualitativo) + metricas quantitativas
6. Persistir scores em `eval_scores` via post_save ou inline no executor

### Fase 3: Portal (frontend)
7. **Pagina `/[platform]/observability`** com 4 tabs:
   - **Runs**: timeline de pipeline runs (status, duration, cost total)
   - **Traces**: waterfall de spans por run (node hierarchy, timing)
   - **Evals**: scoreboard com trends por node/dimensao
   - **Cost**: tokens e custo acumulado por periodo
8. Polling 10s para updates real-time
9. **Retention cleanup**: periodic task no easter (DELETE WHERE created_at < 90 dias)

### Entregaveis estimados
- 1 migration SQL 010 (~50 LOC)
- dag_executor changes (~100 LOC)
- db.py novas funcoes (~150 LOC) — nota: db.py ja cresceu ~100 LOC com compute_epic_status/seed_epic_nodes_from_disk; novas funcoes de trace/span/eval sao adicionais
- easter endpoints (~100 LOC)
- eval_scorer.py (~150 LOC)
- React components (4 tabs) (~400 LOC)
- Testes (~200 LOC)
- **Total estimado: ~1150 LOC** (x1.5 = ~1700 LOC com boilerplate)
