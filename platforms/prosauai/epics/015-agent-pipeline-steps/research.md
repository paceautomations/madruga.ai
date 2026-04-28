# Research — Phase 0: Agent Pipeline Steps

**Epic**: 015-agent-pipeline-steps
**Date**: 2026-04-27
**Status**: Resolved (autonomous dispatch)

Este documento registra as 5 alternativas-chave avaliadas no Phase 0 com pros/cons e justificativa da escolha. As decisões alimentam o `plan.md` Section "Decision Audit Trail" (D-PLAN-01..D-PLAN-12).

---

## R1 — Onde armazenar `sub_steps` do pipeline executor

**Contexto**: cada execução de pipeline gera 1..5 sub-spans dentro do step `generate_response` (top-level `step_order=9` em `trace_steps`). Trace Explorer (épico 008) lê `trace_steps` e renderiza waterfall. Spec deixou em aberto qual storage usar.

### Alternativa A — Nova coluna `sub_steps JSONB` em `public.trace_steps` (ESCOLHIDA)

```sql
ALTER TABLE public.trace_steps ADD COLUMN sub_steps JSONB;
COMMENT ON COLUMN ... 'capped 32 KB total; 4 KB per sub-step';
```

- Pros:
  - Migration trivial (1 linha, idempotente via `ADD COLUMN IF NOT EXISTS`).
  - Query natural: `SELECT step_order, name, status, sub_steps FROM trace_steps WHERE trace_id=$1 ORDER BY step_order`.
  - Frontend renderiza com 0 round-trip extra (já busca trace inteiro).
  - Cap natural 5 sub-steps × 4 KB = 20 KB cabe folgado; cap superior 32 KB protege contra inflação.
  - Coluna NULL para top-level rows não-`generate_response` e para agentes single-call (zero overhead histórico).
- Cons:
  - Sub-steps não são indexáveis individualmente (não dá pra `WHERE sub_steps[*].status='error'` sem GIN expensive).
  - Se um dia precisar agregar "qual % de pipelines têm erro no specialist?" requer parse da coluna em SQL ou ETL.
- Migration impact: 1 ALTER, sem riscos (adicionar coluna nullable é online em PG ≥11).

### Alternativa B — Tabela separada `public.trace_sub_steps` com `parent_step_id` FK

```sql
CREATE TABLE public.trace_sub_steps (
    id UUID PK,
    parent_step_id UUID REFERENCES trace_steps(id) ON DELETE CASCADE,
    sub_order INT,
    sub_type TEXT CHECK IN (...),
    status, duration_ms, input_jsonb, output_jsonb, ...
);
CREATE INDEX idx_sub_parent ON trace_sub_steps(parent_step_id);
```

- Pros:
  - Sub-steps indexáveis individualmente — agregações fáceis ("p95 latência do classifier", "% erros no specialist por agente").
  - Cap por sub-step naturalmente granular (mesmo schema de truncate existente).
  - Escalável se futuro pedir 20+ sub-steps por trace.
- Cons:
  - +1 JOIN no Trace Explorer (ou +1 query LATERAL).
  - +1 migration substancial; +RLS policy (ou heredada explicitamente).
  - Volume previsto absurdamente baixo (pipeline shippa com 6 tenants × 30k traces/dia × 3 sub-steps média = 540k rows/dia → 16M/mês). asyncpg + index = tranquilo, mas bloat operacional sem ganho proporcional.
- Migration impact: +tabela + RLS + índice + JOIN no admin.

### Alternativa C — Sub-steps aninhados dentro de `output_jsonb` da row `generate_response`

```python
output_jsonb = {
    "response_text": ...,
    "tokens_in": ...,
    "sub_steps": [...]  # aninhado aqui
}
```

- Pros:
  - Zero migration.
  - Zero código novo de persistência (já é JSONB).
- Cons:
  - **Estoura cap de 8 KB existente** em `output_jsonb` (FR-034 / step_record DEFAULT_MAX_BYTES) com facilidade — 5 sub-steps × ~2 KB cada já saturam.
  - Atalho que vai precisar voltar atrás em 3 meses para granularidade.
  - Schema/contrato confuso: o que está em `output_jsonb.response_text` vs `output_jsonb.sub_steps[-1].output.response_text`?

### Decisão: **Alternativa A** (D-PLAN-01)

A coluna dedicada com cap 32 KB e truncate per-sub-step a 4 KB cobre 100% dos casos da v1 sem JOIN, sem migration tabular, e mantém schema de top-level rows estável. Se um dia precisarmos de agregação per-sub-step, a migração para tabela separada continua possível (UNNEST + INSERT) — não é one-way door.

---

## R2 — Onde colocar o pipeline executor

**Contexto**: o ponto de entrada hoje é `pipeline.py:_generate_with_retry()` chamando `agent.py:generate_response()`. O executor declarativo precisa rodar APENAS quando o agente tem ≥1 step configurado.

### Alternativa A — Novo módulo `prosauai/conversation/pipeline_executor.py` (ESCOLHIDA)

`pipeline.py:_generate_with_retry()` faz lookup, escolhe um dos dois caminhos:

```python
steps = await pipeline_steps_repo.list_active_steps(conn, agent_id)
if not steps:
    return await generate_response(...)
return await execute_agent_pipeline(steps=steps, ...)
```

- Pros:
  - Testabilidade: `pipeline_executor` é unitestável sem `pipeline.py` inteiro.
  - Separação clara de responsabilidades: `pipeline.py` orquestra os 13 top-level steps; `pipeline_executor.py` orquestra os ≤5 sub-steps internos.
  - Switch de 5 linhas em `_generate_with_retry` minimiza superfície de regressão.
- Cons:
  - +1 módulo (~400 LOC).
  - Ligeira duplicação de pattern (semáforo, timeout, OTel span) — mitigável extraindo helper compartilhado.

### Alternativa B — Branch inline dentro de `_generate_with_retry`

Toda lógica nova vive em `pipeline.py` num `if steps:` gigante.

- Pros:
  - Sem novo módulo.
- Cons:
  - `pipeline.py` já tem 1500+ LOC; +400 LOC de orquestração interna é ilegível.
  - Testes do executor passam pelo top-level pipeline → fixtures pesadas.
  - Risco maior de regressão silenciosa.

### Alternativa C — Reescrever `agent.py:generate_response()` para sempre passar pelo executor (mesmo single-step)

Single-call vira "pipeline de 1 step specialist".

- Pros:
  - Modelo unificado.
- Cons:
  - **Quebra FR-021 / SC-010** (zero overhead para agentes sem pipeline).
  - Quebra invariante "pipeline_steps=[] = comportamento atual byte-equivalente".
  - Refatoração massiva → risco gigante para uma feature que precisa ser opt-in.

### Decisão: **Alternativa A** (D-PLAN-03)

Módulo separado preserva backward compat (caminho default inalterado), maximiza testabilidade, e mantém `pipeline.py` legível.

---

## R3 — Sintaxe e implementação do avaliador de `condition`

**Contexto**: spec FR-024 + Clarif-1 fixou sintaxe `{"caminho.para.valor": "<operador><literal>"}` com AND-implícito, sem OR/parens. Plan precisa decidir como parsear/avaliar.

### Alternativa A — Regex parser + dict scope lookup (ESCOLHIDA)

```python
_PRED_RE = re.compile(r"^\s*(<=|>=|!=|==|<|>|in)\s*(.+?)\s*$")

def evaluate(condition: dict | None, scope: dict) -> bool:
    if not condition:  # None ou {}
        return True
    for path, predicate in condition.items():
        match = _PRED_RE.match(predicate)
        if not match:
            log.warning("condition_predicate_unparseable", path=path, predicate=predicate)
            return False
        op, literal = match.groups()
        actual = _resolve_path(scope, path)
        if actual is _MISSING:
            log.warning_once_per_step("condition_path_missing", ...)
            return False
        if not _OPS[op](actual, _coerce_literal(literal, type(actual))):
            return False
    return True
```

- Pros:
  - 100 LOC, fácil de revisar.
  - Sem dependência nova.
  - Comportamento previsível: chave não existe → False; sintaxe quebrada → False + warning.
  - `_coerce_literal` faz casting baseado no tipo do `actual` (float vs string) — evita bugs `"0.6" < "0.92"` (lex compare).
- Cons:
  - Sem OR/parens — explicitamente fora de escopo (FR-024).
  - Se v2 quiser DSL mais rica, refatoração. Aceito.

### Alternativa B — `ast.literal_eval` + `eval()` sandboxed

Permite expressões Python literais (`classifier.confidence < 0.6 and classifier.intent == 'billing'`).

- Pros:
  - Sintaxe natural, OR/parens grátis.
- Cons:
  - `eval()` mesmo sandboxed = risco. JSONB vem de admin endpoint → input controlado, mas defesa-em-profundidade pede evitar.
  - `ast.literal_eval` não suporta operadores; precisaria de mini-walker custom.
  - Spec é explícita: sem OR/parens v1.

### Alternativa C — Mini-DSL com `pyparsing` ou `lark`

- Pros:
  - Gramática formal, extensível.
- Cons:
  - Dependência nova (proibido — assumption "Stack inalterada").
  - Overkill para JSONB de 2-3 chaves.

### Decisão: **Alternativa A** (D-PLAN-07)

Regex + dict scope. ~100 LOC, zero dep nova, comportamento estritamente conforme FR-024. Warning deduplicado via in-process LRU `(agent_id, step_index)` evita flood.

---

## R4 — Cache do lookup `agent_pipeline_steps`

**Contexto**: SC-010 exige overhead p95 ≤5 ms para agentes sem pipeline. O lookup é `SELECT ... FROM agent_pipeline_steps WHERE agent_id=$1 AND is_active=true ORDER BY step_order`.

### Alternativa A — Sem cache, asyncpg direto com índice (ESCOLHIDA)

`CREATE INDEX idx_pipeline_agent_active ON agent_pipeline_steps (agent_id, is_active, step_order)`.

- Pros:
  - Sub-ms na maioria dos casos (índice cobre tudo, query nem toca a heap se SELECT inclui só PK + step_order).
  - Zero invalidation logic.
  - Zero stale config (hot reload imediato).
- Cons:
  - Se prod mostrar p95 >3 ms, precisa adicionar cache depois. Plan documenta como follow-up.

### Alternativa B — Redis cache 60s TTL keyed em `pipeline_steps:{agent_id}`

- Pros:
  - Lookup ~1 ms via redis pipeline.
  - Bom para multi-replica (compartilhado).
- Cons:
  - Stale config até 60s.
  - Invalidation manual no PUT (admin) — bugs sutis.
  - Adicionar surface só pra economizar 1-2 ms é prematuro.

### Alternativa C — In-process LRU 5min TTL

- Pros:
  - Sub-µs.
- Cons:
  - Multi-replica = 5 caches diferentes; stale per-pod.
  - Hot reload via PUT precisaria de pubsub (overkill).

### Decisão: **Alternativa A** (D-PLAN-05)

Lookup direto via asyncpg + índice cobre SC-010 confortavelmente para 6-30 agentes ativos. Métrica `pipeline_steps_lookup_p95_ms` adicionada na PR-2 para validar em produção. Se passar de 3 ms, adicionar Redis cache (épico mínimo follow-up).

---

## R5 — Implementar `agent_config_versions` (ADR-019) agora ou depois?

**Contexto**: Spec assume que `agent_config_versions` existe (canary, snapshot, rollback). **Descoberta crítica**: a tabela NÃO existe em produção. Apenas `prompts.version` (varchar) + `agents.active_prompt_id` existem.

### Alternativa A — Não implementar agora, pipeline_steps direto em tabela própria (ESCOLHIDA)

Pipeline_steps são CRUD direto em `agent_pipeline_steps` (FK → `agents.id`). Rollback = `DELETE WHERE agent_id=X`. Histórico via `audit_log`.

- Pros:
  - Mantém escopo do épico em 3 semanas (apetite Shape Up).
  - PR-1..PR-4 entregam US1+US2+US6 (P1) sem dependência externa.
  - ADR-019 permanece aprovado, vira épico próprio quando demanda concreta justificar.
- Cons:
  - Sem canary verdadeiro per-version do pipeline (US4 fica reduzido — group-by-version usa apenas `active_prompt_id` mudando).
  - `messages.metadata.pipeline_version` (FR-064) fica NULL na v1 ou aponta pra `prompts.id` como proxy.
  - Spec menciona "snapshot dentro de `agent_config_versions.config_snapshot.pipeline_steps`" (FR-040) — esse comportamento fica dormante.

### Alternativa B — Implementar `agent_config_versions` neste épico (scope creep)

Adicionar PR-0 (1.5 semana) para criar tabela + lifecycle (draft→canary→active→rolled_back) + traffic split + admin endpoints + frontend.

- Pros:
  - Spec FR-040..FR-046 ficam genuinamente atendidos.
  - Canary verdadeiro disponível pra PR-6 (US4).
- Cons:
  - +1.5 semana → 4.5 semanas total → estoura cut-line.
  - Risco de incomplete (se PR-0 atrasar, todos os PRs subsequentes ficam bloqueados).
  - ADR-019 é épico próprio em si — empacotar viola "Shape Up boundary".

### Alternativa C — Subset mínimo: adicionar `agents.config_version INT` que incrementa em CADA mutation de pipeline_steps

- Pros:
  - `messages.metadata.pipeline_version` ganha valor estável (int monotônico per-agent).
- Cons:
  - Não é canary — só versão linear sem traffic split.
  - Confunde semântica: "version" implica histórico, mas não temos snapshot.

### Decisão: **Alternativa A** (D-PLAN-02)

Não implementar `agent_config_versions` neste épico. Pipeline_steps direto. Documentar follow-up em decisions.md durante implement. `messages.metadata.pipeline_version` fica como string `"unversioned-v1"` (não NULL) para distinguir "feature ativa, mas sem versionamento" de "agente single-call". Quando ADR-019 shippar (épico próprio), retroativamente popular versões e atualizar metadata.

---

## Cross-cutting Findings

### F1 — `prompts.version` é varchar, não monotônico global

`agents` tem `active_prompt_id UUID`, mas não há `version_number INT`. Plan trata `prompt_slug` em config como string opaca que mapeia 1:1 para `prompts.version`.

### F2 — Trace Explorer já lê `agent_version_id` em `trace_steps`

Coluna existe (épico 008). Hoje fica NULL para a maioria dos rows. Quando `agent_config_versions` shippar, popular automaticamente. Por enquanto, neutro.

### F3 — `_record_step` helper já cuida de timing + status

Reusar 100%. Sub-steps emitem estrutura serializada que cabe em StepRecord, persistida via `trace_persist`.

### F4 — `pricing.calculate_cost` cobre todos os modelos esperados (gpt-5-nano/mini)

Validador de `routing_map` consulta o dict de pricing constant (ADR-029). Modelo desconhecido → 422 no PUT admin.

### F5 — Semáforo LLM compartilhado (`_LLM_SEMAPHORE`) limita concorrência total

Pipeline com 5 steps consome 5 slots sequencialmente, não em paralelo. Nada a mudar.

---

## Open Questions deferred to implement

- **OQ-1**: Devemos emitir métrica Prometheus `pipeline_step_duration_seconds` por `step_type` ou `pipeline_overall_duration_seconds`? — Decidir em PR-3 baseado em consumo do dashboard épico 002.
- **OQ-2**: `condition` deveria suportar comparação com null literal (`"==null"`)? — Improvável caso real; deferir até alguém pedir.
- **OQ-3**: Limite de 16 KB por config é per-step ou cumulativo? — Per-step (consistente com plan); validador soma tudo só para garantir que coluna `config` JSONB inteira não estoura limites de PG.

---

## References

- Spec: [`spec.md`](./spec.md) — clarifications session 2026-04-27.
- Domain model: [`platforms/prosauai/engineering/domain-model.md`](../../engineering/domain-model.md) lines 244-263 (schema base).
- ADR-006 — Agent-as-Data: [`platforms/prosauai/decisions/ADR-006-agent-as-data.md`](../../decisions/ADR-006-agent-as-data.md).
- ADR-019 — Agent config versioning: [`platforms/prosauai/decisions/ADR-019-agent-config-versioning.md`](../../decisions/ADR-019-agent-config-versioning.md) (não implementado em produção, ver D-PLAN-02).
- ADR-027 — Admin tables sem RLS: [`platforms/prosauai/decisions/ADR-027-admin-tables-no-rls.md`](../../decisions/ADR-027-admin-tables-no-rls.md).
- ADR-028 — Pipeline fire-and-forget: [`platforms/prosauai/decisions/ADR-028-pipeline-fire-and-forget-persistence.md`](../../decisions/ADR-028-pipeline-fire-and-forget-persistence.md).
- ADR-029 — Cost pricing constant: [`platforms/prosauai/decisions/ADR-029-cost-pricing-constant.md`](../../decisions/ADR-029-cost-pricing-constant.md).
- Pipeline atual: `apps/api/prosauai/conversation/pipeline.py:_generate_with_retry` (linha 490) e `agent.py:generate_response` (linha 324).
- Trace persistence: `apps/api/prosauai/conversation/step_record.py` + `trace_persist.py`.
