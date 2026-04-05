---
id: 021
title: "Pipeline Intelligence"
status: shipped
appetite: 2w
priority: P3
depends_on: [017]
blocks: []
updated: 2026-04-04
delivered_at: 2026-04-05
---
# Epic 021: Pipeline Intelligence

## Problem

Nao ha visibilidade sobre custos do pipeline: as colunas `tokens_in`, `tokens_out`, `cost_usd` na tabela `pipeline_runs` existem desde o epic 017 mas nunca sao populadas — impossivel saber qual skill consome mais tokens ou quanto custa um epic completo. Nao existe deteccao de output fabricado: se um skill gera um artifact sem fazer nenhum tool call (zero reads, zero writes), o output provavelmente e alucinado — mas o pipeline aceita silenciosamente. O pipeline de 24 skills e heavy demais para bug fixes: corrigir um typo requer o mesmo fluxo de 11 passos L2 que implementar um epic de 6 semanas.

## Appetite

**2w** — 4 tasks. Cost tracking e trivial (colunas ja existem, so popular). Hallucination guard e 1h. Fast lane e o mais complexo (~4h) mas e uma nova skill markdown + ajuste no dag_executor.

## Solution

### T1. Cost tracking (2h)

Popular as colunas existentes em `pipeline_runs` a partir do output JSON do `claude -p`.

**O que ja existe:**
- Tabela `pipeline_runs` com colunas `tokens_in`, `tokens_out`, `cost_usd`, `duration_ms` (migration 010)
- `insert_run()` em `db.py` ja aceita esses parametros
- `dag_executor.py` ja chama `insert_run()` apos cada dispatch

**O que falta:**
Parse do output JSON do `claude -p` para extrair metricas. O `claude -p --output-format json` retorna um JSON com campos de usage.

```python
def parse_claude_output(stdout: str) -> dict:
    """Extract token usage and cost from claude -p JSON output."""
    try:
        data = json.loads(stdout)
        return {
            "tokens_in": data.get("usage", {}).get("input_tokens"),
            "tokens_out": data.get("usage", {}).get("output_tokens"),
            "cost_usd": data.get("cost_usd"),
            "duration_ms": data.get("duration_ms"),
        }
    except (json.JSONDecodeError, KeyError):
        return {}
```

**Nota:** `_run_implement_tasks()` em `dag_executor.py:403-413` ja faz parse e passa metricas para `insert_run()`. O pattern existe — so falta replicar no `_dispatch_node()` (dispatch normal de skills L1/L2).

**Dashboard:** Com dados populados, o portal observability (epic 017) automaticamente mostra custos por skill/epic na tab "Cost".

### T2. Hallucination guard (1h)

Adicionar check no auto-review do contrato base: se o agent completou a geracao sem fazer nenhum tool call, rejeitar o output como provavelmente fabricado.

**Implementacao no `pipeline-contract-base.md`:**

Adicionar ao auto-review (Step 3) um check universal:

```markdown
| # | Check | Action on Failure |
|---|-------|-------------------|
| 0 | Agent made at least 1 tool call during generation? | REJECT — output likely fabricated. Re-prompt with explicit instruction to read dependency artifacts. |
```

**Implementacao no `dag_executor.py`:**

Apos `dispatch_with_retry()`, parsear o output JSON e verificar se houve tool calls:

```python
def _check_hallucination(stdout: str) -> bool:
    """Return True if output appears fabricated (zero tool calls)."""
    try:
        data = json.loads(stdout)
        tool_calls = data.get("tool_use_count", 0)
        if tool_calls == 0:
            log.warning("HALLUCINATION GUARD: Zero tool calls detected — output likely fabricated")
            return True
    except (json.JSONDecodeError, KeyError):
        pass
    return False
```

**Referencia:** GSD (Get Stuff Done) framework: "Agents completing with zero tool calls are rejected as fabricated — cheap, high-value check."

### T3. Fast lane `/quick-fix` (4h)

Nova skill `.claude/commands/madruga/quick-fix.md` que oferece um ciclo L2 comprimido para bug fixes e mudancas pequenas:

**Ciclo fast lane:**
```
specify (simplificado) → implement → judge
```

**O que pula:** plan, tasks, analyze (pre e post), qa, reconcile, clarify.

**Quando usar:**
- Bug fix com scope claro (1-2 arquivos)
- Typo/config change
- Mudanca em <50 LOC

**Implementacao:**

1. **Skill markdown** (`quick-fix.md`, ~80 LOC):
   - Frontmatter com `gate: human` (confirmacao antes de executar)
   - Coleta: descricao do problema, arquivo(s) afetado(s), tipo de mudanca
   - Gera `spec.md` minimalista (problema + fix esperado + acceptance criteria)
   - Delega para `speckit.implement` com scope restrito
   - Apos implement, roda `madruga:judge` para review

2. **DAG integration** — nova opcao em `dag_executor.py`:
   ```python
   def parse_dag(..., mode="l1"):
       if mode == "quick":
           return [
               Node(id="specify", skill="speckit.specify", ...),
               Node(id="implement", skill="speckit.implement", depends=["specify"], ...),
               Node(id="judge", skill="madruga:judge", depends=["implement"], ...),
           ]
   ```

3. **CLI**: `python3 .specify/scripts/dag_executor.py --platform <name> --epic <slug> --quick`

**Referencia:** GSD `/gsd:quick` — "The 24-skill pipeline is comprehensive but heavy for bug fixes."

### T4. Adaptive replanning hint (2h)

Apos `reconcile` completar um epic, adicionar step opcional que avalia se o roadmap precisa de ajuste.

**Implementacao:**
- Novo node opcional `roadmap-reassess` no `epic_cycle` de `platform.yaml`:
  ```yaml
  - id: roadmap-reassess
    skill: madruga:roadmap
    depends: [reconcile]
    gate: auto
    optional: true
    skip_condition: "epic.appetite <= '2w'"  # so para epics grandes
  ```
- O skill `roadmap` ja existe — recebe contexto do epic recem-concluido e avalia se dependencias/prioridades mudaram
- Output: diff sugerido no roadmap.md (auto-apply se mudanca < 3 linhas, escalar se maior)

**Referencia:** GSD adaptive replanning: "After each slice, replan based on discovered information."

## Rabbit Holes

- **Cost tracking depende do formato de output do claude -p** — se o formato mudar, o parse quebra. Usar try/except generoso + fallback para metricas vazias
- **Hallucination guard pode ter false positives** — skills que legitimamente nao precisam de tool calls (ex: skills que so geram texto). Configurar whitelist de skills isentos
- **Fast lane NAO e skip de quality** — ainda roda judge. E um ciclo mais curto, nao um bypass
- **Nao criar skill complexa** — quick-fix e ~80 LOC markdown, nao um mini-framework

## No-gos

- Mudancas no schema do SQLite (colunas ja existem)
- ML/AI para deteccao de qualidade (heuristicas simples sao suficientes)
- Dashboard novo no portal (usar tabs existentes do epic 017)
- Budget enforcement (limitar gastos por epic) — scope futuro
- Wave-based parallel execution — complexo, scope futuro

## Acceptance Criteria

- [X] `pipeline_runs` populada com `tokens_in`, `tokens_out`, `cost_usd` apos cada dispatch
- [X] Output com zero tool calls gera WARNING no log (hallucination guard)
- [X] `/quick-fix` skill existe e executa ciclo comprimido: specify → implement → judge
- [X] `--quick` flag funciona no dag_executor.py
- [X] `roadmap-reassess` node existe como opcional no epic_cycle
- [X] Portal tab "Cost" (epic 017) mostra dados reais de custo
- [X] `make test` passa
- [X] `make ruff` passa

## Implementation Context

### Arquivos a modificar
| Arquivo | LOC atual | Mudanca |
|---------|-----------|---------|
| `.specify/scripts/dag_executor.py` | 1,649 | T1 (parse_claude_output em dispatch normal), T2 (hallucination check), T3 (--quick mode) |
| `.claude/knowledge/pipeline-contract-base.md` | — | T2 (hallucination guard no auto-review) |
| `platforms/madruga-ai/platform.yaml` | — | T3 (quick mode nodes), T4 (roadmap-reassess node) |
| `.claude/knowledge/pipeline-dag-knowledge.md` | — | T4 (documentar roadmap-reassess) |

### Arquivos a criar
| Arquivo | Estimativa |
|---------|-----------|
| `.claude/commands/madruga/quick-fix.md` | ~80 LOC |
| `.specify/scripts/tests/test_cost_tracking.py` | ~50 LOC |
| `.specify/scripts/tests/test_hallucination_guard.py` | ~30 LOC |

### Funcoes existentes a reutilizar
- `parse_claude_output()` em `dag_executor.py` — ja existe para implement tasks, generalizar
- `insert_run()` em `db.py` — ja aceita tokens_in/out/cost_usd
- `_run_eval_scoring()` em `dag_executor.py` — pattern de scoring pos-dispatch
- Pipeline React components do epic 017 — tab "Cost" ja renderiza dados

### Decisoes
- **Heuristicas > ML**: zero tool calls = fabricado. Simples, barato, eficaz
- **Fast lane e skill markdown**: nao criar framework — ~80 LOC de instrucao
- **Roadmap-reassess opcional**: skip para epics <=2w (maioria), roda so para epics grandes

---

> **Source**: madruga_next_evolution.md Tier C (C1, C3, C6, C12)
> **Benchmark**: GSD hallucination guard + cost tracking + quick flow, IMPROVEMENTS I15/I17/I22/I18
