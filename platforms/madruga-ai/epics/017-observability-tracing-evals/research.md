# Research: Observability, Tracing & Evals

**Date**: 2026-04-02 | **Epic**: 017-observability-tracing-evals

## R1: Claude CLI JSON Output Format

**Question**: Quais campos o `claude -p --output-format json` retorna e como extrair tokens/custo?

**Finding**: O Claude CLI com `--output-format json` retorna um objeto JSON no stdout com a seguinte estrutura relevante:

```json
{
  "type": "result",
  "subtype": "success",
  "cost_usd": 0.123,
  "duration_ms": 45000,
  "duration_api_ms": 42000,
  "is_error": false,
  "num_turns": 5,
  "result": "...",
  "session_id": "...",
  "total_cost_usd": 0.123,
  "usage": {
    "input_tokens": 5000,
    "output_tokens": 3000,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 2000
  }
}
```

**Campos a extrair**:
- `usage.input_tokens` → `tokens_in`
- `usage.output_tokens` → `tokens_out`
- `cost_usd` (ou `total_cost_usd`) → `cost_usd`
- `duration_ms` → `duration_ms`

**Defensive parsing**: O JSON pode variar entre versoes do CLI. Usar `json.loads()` com `try/except` e `.get()` para cada campo, defaulting to `None`.

**Decision**: Parse com `json.loads(stdout)` no `dispatch_node_async`, extrair campos com `.get()`, retornar dict de metricas.
**Rationale**: Campos ja existem no schema (`pipeline_runs.tokens_in/out/cost_usd/duration_ms`), so precisam ser populados.
**Alternatives**: (1) Nao parsear — perde metricas, (2) Parsear via regex — fragil e desnecessario quando temos JSON valido.

---

## R2: Reuso de `pipeline_runs` como Spans

**Question**: Criar tabela `spans` separada ou reusar `pipeline_runs` com `trace_id` FK?

**Finding**: A tabela `pipeline_runs` ja contem todos os campos de um span:

| Campo span (spec) | Campo existente em `pipeline_runs` |
|---|---|
| node_id | `node_id` |
| skill | inferido via node_id → platform.yaml |
| started_at / completed_at | `started_at`, `completed_at` |
| status | `status` (running/completed/failed/cancelled) |
| tokens_in / tokens_out | `tokens_in`, `tokens_out` (existem, sempre NULL) |
| cost_usd | `cost_usd` (existe, sempre NULL) |
| duration_ms | `duration_ms` (existe, sempre NULL) |
| error | `error` |

O unico campo ausente e `trace_id` para agrupar spans em um trace.

**Decision**: Adicionar `trace_id TEXT REFERENCES traces(trace_id)` a `pipeline_runs` via `ALTER TABLE ADD COLUMN`. Nao criar tabela `spans`.
**Rationale**: Evita duplicacao de dados, reutiliza infraestrutura existente (insert_run, complete_run, get_runs). Dados historicos sem trace_id (pre-017) ficam com trace_id=NULL, o que e correto (nao tinham trace).
**Alternatives**: (1) Tabela `spans` separada — duplica dados, requer migrar historico, duas fontes de verdade. (2) View SQL — overhead desnecessario para abstraction.

---

## R3: SQLite ALTER TABLE ADD COLUMN Safety

**Question**: `ALTER TABLE pipeline_runs ADD COLUMN trace_id` e seguro em SQLite?

**Finding**: SQLite suporta `ALTER TABLE ADD COLUMN` nativamente desde versao 3.2.0 (2005). A operacao:
- E atomica e instantanea (nao reescreve a tabela)
- Colunas adicionadas recebem valor DEFAULT (NULL se nao especificado)
- Foreign keys em colunas adicionadas funcionam normalmente
- WAL mode nao afeta a operacao

**Constraint**: `ALTER TABLE ADD COLUMN` em SQLite nao suporta `NOT NULL` sem DEFAULT. Como `trace_id` e nullable (dados historicos nao tem trace), isso nao e problema.

**Decision**: Usar `ALTER TABLE ADD COLUMN` diretamente. Seguro e performante.
**Rationale**: Operacao nativa do SQLite, sem risco de perda de dados, instantanea.

---

## R4: Eval Scoring Strategy

**Question**: Como implementar scoring em 4 dimensoes sem rodar Judge completo por node?

**Finding**: O Judge pattern existente (`.claude/commands/madruga/judge.md`) roda 4 subagents + judge pass, custando ~$0.50-1.00 por execucao. Rodar isso para cada um dos ~11 nodes de um epic seria ~$5-10 por run — inviavel para observabilidade automatica.

**Estrategia por dimensao**:

| Dimensao | Metodo V1 | Custo |
|----------|-----------|-------|
| `quality` | Se Judge report existe: `judge_score/100*10`. Senao: heuristica (output nao vazio + sem marcadores de erro) → default 7.0 | Zero |
| `adherence_to_spec` | Verificar se output contem sections esperadas (via regex em templates definidos em platform.yaml). Score proporcional a sections presentes/esperadas | Zero |
| `completeness` | `min(10, line_count / expected_line_count * 10)` onde expected vem do historico ou threshold fixo por node type | Zero |
| `cost_efficiency` | `10 - min(10, cost_usd / budget_per_node * 10)` onde budget = historico medio * 1.5. Se sem historico, score 5.0 (neutro) | Zero |

**Decision**: Scoring puramente quantitativo/heuristico em V1. Zero custo adicional de LLM. Judge scores integrados quando o node `judge` roda (ja previsto no L2 cycle).
**Rationale**: Observabilidade deve ser barata. Metricas quantitativas cobrem 80% do valor. Judge qualitativo ja roda no step 9 do L2 — basta ingerir o resultado.
**Alternatives**: (1) Mini-Judge (1 prompt rapido por node) — ~$0.05/node, melhor qualidade mas aumenta tempo. Considerar para V2. (2) DeepEval — 20+ deps, metricas genericas, nao mapeiam para pipeline.

---

## R5: Portal Data Fetching — Polling vs SSE vs Static JSON

**Question**: Como o portal consome dados de observabilidade em tempo real?

**Finding**: Tres opcoes avaliadas:

| Opcao | Pros | Cons |
|-------|------|------|
| **Polling 10s** (fetch periodico) | Trivial em React, sem infra extra, tolerante a falhas | Latencia de ate 10s, requests desnecessarios quando idle |
| **SSE** (Server-Sent Events) | Real-time, eficiente em bandwidth | Requer streaming no easter, Astro islands hydration complexa |
| **Static JSON** (pattern existente) | Consistente com dashboard.astro | Requer rebuild/re-export, nao e real-time, nao funciona para dados em progresso |

**Decision**: Polling 10s via `fetch()` + `setInterval()` em React islands com `client:load`.
**Rationale**: Latencia de 10s e aceitavel para monitoramento humano. Zero complexidade adicional no easter (endpoints JSON simples). Consistente com decisao do pitch (decisao 5).
**Alternatives**: SSE para V2 se polling for insuficiente (improvavel para single-user).

**Easter URL**: O portal roda em `localhost:4321` (Astro dev) e o easter em `localhost:8040`. Em dev, requests cross-origin requerem CORS headers no easter. Adicionar `CORSMiddleware` ao FastAPI.

---

## R6: Retention Cleanup — Cascading Deletes

**Question**: Como deletar traces antigos sem deixar spans/evals orfaos?

**Finding**: SQLite suporta `ON DELETE CASCADE` em foreign keys quando `PRAGMA foreign_keys=ON` (ja configurado em `get_conn()`). Porem, `ALTER TABLE ADD COLUMN` nao suporta definir FK constraints inline — a FK so e enforced se declarada no CREATE TABLE original.

**Approach**: A migration 010 cria `traces` e `eval_scores` com FK CASCADE. Para `pipeline_runs.trace_id` (adicionado via ALTER TABLE), o CASCADE nao sera automatico — mas podemos deletar em ordem: `eval_scores` → `pipeline_runs` → `traces` (3 DELETEs na mesma transacao).

**Decision**: Cleanup via 3 DELETEs sequenciais na mesma transacao, ordenados por dependencia. Nao depender de CASCADE para pipeline_runs.trace_id.
**Rationale**: Mais explicito e robusto que CASCADE. O overhead de 3 queries e negligivel para cleanup diario.

---

## R7: Waterfall Visualization

**Question**: Como renderizar o waterfall de traces no portal sem bibliotecas pesadas?

**Finding**: Opcoes avaliadas:

| Opcao | Pros | Cons |
|-------|------|------|
| SVG puro (React) | Zero deps, leve, customizavel | Mais codigo, sem tooltips nativos |
| Mermaid Gantt | Ja integrado no portal | Nao interativo, layout limitado |
| Recharts | Popular, React-native, bar charts | ~100KB bundle, overkill para waterfall |

**Decision**: SVG puro renderizado em React. Cada span = `<rect>` com largura proporcional a duracao, posicionado por `started_at` relativo ao trace.start. Tooltip via `<title>` SVG nativo.
**Rationale**: Zero deps adicionais, ~50 LOC, performance otima, customizacao total.
**Alternatives**: Recharts para V2 se precisarmos de graficos mais sofisticados na aba de Custos (bar chart de custo acumulado).

**Nota sobre CostTab**: Para graficos de custo acumulado (bar chart por dia/semana), usar SVG puro tambem. Se insuficiente, considerar `recharts` como dep opcional apenas para CostTab (tree-shaking via dynamic import).

---

## R8: CORS Configuration for Easter

**Question**: Como permitir requests do portal (localhost:4321) ao easter (localhost:8040)?

**Finding**: FastAPI tem `CORSMiddleware` builtin via Starlette:

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321", "http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

**Decision**: Adicionar CORSMiddleware ao easter com origins limitados a localhost. Sem wildcard.
**Rationale**: Seguro (only localhost), necessario para fetch cross-origin. FastAPI middleware builtin, zero deps extras.
