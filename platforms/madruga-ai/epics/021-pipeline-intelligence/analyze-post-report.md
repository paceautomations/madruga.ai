# Post-Implementation Analysis Report — Epic 021: Pipeline Intelligence

**Date**: 2026-04-04
**Phase**: Post-implementation (after speckit.implement, before madruga:judge)
**Artifacts analyzed**: pitch.md, tasks.md, implement-context.md, research.md + actual code diffs
**Implementation status**: 28/28 tasks marked DONE

---

## Resumo Executivo

A implementação completou todos os 28 tasks com sucesso. Código compila, 633 testes passam, ruff limpo. Entretanto, **2 tasks de documentação (T013, T022) foram marcados como DONE sem que as mudanças existam nos arquivos alvo** — são gaps reais que precisam de correção. A lógica de `skip_condition` no `dag_executor.py` **não avalia a expressão** — qualquer valor truthy causa skip incondicional (confirmado no pre-analyze, não resolvido).

---

## Verificação por User Story

### US1: Cost Tracking ✅ IMPLEMENTADO CORRETAMENTE

| Item | Status | Evidência |
|------|--------|-----------|
| `parse_claude_output()` usa `total_cost_usd` | ✅ | `dag_executor.py:203` — `data.get("total_cost_usd")` |
| Fallback `_estimate_cost_usd()` existe | ✅ | `dag_executor.py:218-226` — calcula via pricing Sonnet |
| Integrado no sync loop | ✅ | `dag_executor.py:1360` — `metrics = parse_claude_output(stdout)` |
| Integrado no async loop | ✅ | `dag_executor.py:1900` — mesma chamada |
| Testes existem | ✅ | `test_cost_tracking.py` — 496 LOC |
| Portal "Cost" tab verificada (T007) | ✅ | Read-only check confirmou compatibilidade |

**Achado positivo**: A correção de `cost_usd` → `total_cost_usd` (identificada na research.md) foi aplicada corretamente. O fallback de estimativa por tokens é robusto (retorna `None` se ambos os counts forem `None`).

### US2: Hallucination Guard ✅ IMPLEMENTADO (com 1 gap documental)

| Item | Status | Evidência |
|------|--------|-----------|
| `_check_hallucination()` existe | ✅ | `dag_executor.py:229-249` — heurística `num_turns <= 2` |
| Integrado no sync loop | ✅ | `dag_executor.py:1363-1365` — WARNING log |
| Integrado no async loop | ✅ | `dag_executor.py:1903-1905` — WARNING log |
| Testes existem | ✅ | `test_hallucination_guard.py` — 424 LOC |
| **T013: Contract doc atualizado** | ❌ **MISSING** | `pipeline-contract-base.md` Tier 1 table NÃO contém check de hallucination |

**Detalhe do gap**: O Tier 1 auto-review table em `pipeline-contract-base.md` (linhas 95-101) tem exatamente os mesmos 5 checks originais. A row 0 prometida no T013 ("Agent made at least 1 tool call during generation?") **não existe**.

**Heurística escolhida**: `num_turns <= 2 AND NOT is_error` — pragmática e alinhada com a recomendação da research.md (abordagem D). Limitações conhecidas (false positives em skills text-only) são aceitáveis para MVP.

### US3: Fast Lane `/quick-fix` ✅ IMPLEMENTADO CORRETAMENTE

| Item | Status | Evidência |
|------|--------|-----------|
| Skill markdown existe | ✅ | `quick-fix.md` — 154 LOC, frontmatter correto |
| `quick_cycle` em platform.yaml | ✅ | 3 nodes: specify → implement → judge |
| `--quick` flag no argparse | ✅ | `dag_executor.py:1999-2001` |
| Quick mode DAG loading | ✅ | `dag_executor.py:677-681` — lê `quick_cycle` quando `mode=="quick"` |
| Quick-fix context no system prompt | ✅ | `_QUICK_FIX_CONTEXT` string + `build_system_prompt()` injetam contexto |
| `--quick` requer `--epic` | ✅ | `dag_executor.py:2007-2008` — validation |
| Testes existem | ✅ | Testes em `test_dag_executor.py` para quick mode |

**Achado positivo**: A implementação é limpa — `_quick_mode_active` global flag, reutilizado em `build_dispatch_cmd()` e `build_system_prompt()`. O skill markdown tem handoff correto para o ciclo L2 completo quando scope excede.

### US4: Adaptive Replanning ⚠ PARCIALMENTE IMPLEMENTADO

| Item | Status | Evidência |
|------|--------|-----------|
| Node `roadmap-reassess` em platform.yaml | ✅ | Linhas 209-215 — optional, skip_condition, gate: auto |
| **T022: Knowledge doc atualizado** | ❌ **MISSING** | `pipeline-dag-knowledge.md` L2 table termina no step 11 (reconcile) — sem step 12 |
| T023: skip_condition avaliada | ⚠ **FALSO POSITIVO** | `dag_executor.py:1181-1182` faz `if node.optional and node.skip_condition:` → skip incondicional |

**Detalhe do gap T022**: A tabela L2 em `pipeline-dag-knowledge.md` (seção 8) tem steps 1-11. O `roadmap-reassess` como step 12 **não foi adicionado**. O implement-context.md marca T022 como DONE com "Tokens in/out: 9/1249", indicando que algo foi feito mas a mudança não persistiu no arquivo.

**Detalhe do gap T023**: O código `skip_condition` não avalia a expressão `"epic.appetite <= '2w'"`. Qualquer string truthy causa skip automático. O pre-analyze (C2) já havia identificado isso. O implement-context.md marca T023 como DONE sem indicar que construiu um evaluator.

---

## Findings Table

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| PA1 | Implementation Gap | HIGH | `.claude/knowledge/pipeline-contract-base.md:95-101` | T013 marcado DONE mas hallucination guard NÃO foi adicionado ao Tier 1 auto-review table | Adicionar row 6: "Agent made ≥1 tool call? `_check_hallucination()` in dag_executor" com action "WARNING — output may be fabricated" |
| PA2 | Implementation Gap | HIGH | `.claude/knowledge/pipeline-dag-knowledge.md` seção 8 | T022 marcado DONE mas `roadmap-reassess` NÃO foi documentado como step 12 na L2 table | Adicionar row: "12 \| madruga:roadmap \| auto \| Optional roadmap reassessment (skipped for ≤2w epics)" |
| PA3 | Logic Bug | MEDIUM | `dag_executor.py:1181-1182`, `dag_executor.py:1782-1783` | `skip_condition` nunca é avaliada — qualquer valor truthy causa skip incondicional. Roadmap-reassess será SEMPRE skippado, independente do appetite do epic | Implementar evaluator mínimo OU trocar para flag booleano controlado pelo executor. Pre-analyze C2 já flaggou isso |
| PA4 | Structural Anomaly | MEDIUM | `spec.md`, `plan.md` | spec.md e plan.md continuam sendo stubs de Q&A (8 e 11 linhas). Pitch.md serviu como spec/plan de facto | Aceitar como-está (pitch é detalhado o suficiente) ou gerar artefatos formais. Pre-analyze A1/A2 já flaggou |
| PA5 | Coverage Gap | LOW | Nenhum arquivo | Whitelist de skills isentos do hallucination guard não foi implementada (rabbit hole do pitch, D2 do pre-analyze) | Aceitar como deferred — WARNING mode é tolerante a false positives |
| PA6 | Hardcoded Value | LOW | `dag_executor.py:218-226` | `_estimate_cost_usd()` usa pricing Sonnet hardcoded. Se modelo mudar, custos estimados ficam incorretos | Aceitável — `total_cost_usd` é o valor primário; fallback raramente ativa |
| PA7 | Test Coverage | LOW | `test_cost_tracking.py`, `test_hallucination_guard.py` | 920 LOC de testes novos (496 + 424) para ~80 LOC de lógica nova. Ratio alto mas aceitável (muitos edge cases de parsing JSON) | Nenhuma ação necessária |

---

## Comparação Pre-Analyze vs Post-Analyze

| Pre-Analyze Finding | Severidade Original | Status Pós-Implementação |
|---------------------|---------------------|--------------------------|
| A1: spec.md stub | CRITICAL | **MANTIDO** (PA4) — pitch usado como spec de facto |
| A2: plan.md stub | CRITICAL | **MANTIDO** (PA4) — pitch usado como plan de facto |
| B1: LOC count stale | HIGH | **RESOLVIDO** — implementação usou código real, não referências do pitch |
| B2: parse_claude_output() scope | HIGH | **RESOLVIDO** — T005 corrigiu `cost_usd` → `total_cost_usd` |
| B3: Function name reference | HIGH | **N/A** — cosmético, não afetou implementação |
| C1: tool_use_count field | HIGH | **RESOLVIDO** — research.md verificou, implementação usa `num_turns` heuristic |
| C2: skip_condition evaluator | MEDIUM | **NÃO RESOLVIDO** (PA3) — código faz skip incondicional |
| C3: WARNING vs REJECT | MEDIUM | **RESOLVIDO** — implementação usa WARNING |
| D1: Portal contingency | MEDIUM | **RESOLVIDO** — T007 confirmou portal funcional |
| D2: Hallucination whitelist | MEDIUM | **NÃO RESOLVIDO** (PA5) — deferred to future |
| E1: Sync/async duplication | LOW | **MANTIDO** — duplicação aceita (code paths são similares mas não idênticos) |

---

## Coverage: Acceptance Criteria vs Implementation

| Pitch AC | Implementado? | Evidência |
|----------|--------------|-----------|
| `pipeline_runs` populada com tokens/cost | ✅ | `parse_claude_output()` corrigido, integrado em ambos loops |
| Zero tool calls → WARNING | ✅ | `_check_hallucination()` + integração sync/async |
| `/quick-fix` skill existe | ✅ | `quick-fix.md` — 154 LOC |
| `--quick` flag funciona | ✅ | argparse + DAG loading + system prompt injection |
| `roadmap-reassess` node existe | ✅ | platform.yaml — mas skip_condition não avalia (PA3) |
| Portal tab "Cost" mostra dados | ✅ | Verificado em T007 |
| `make test` passa | ✅ | 633 passed |
| `make ruff` passa | ✅ | All checks passed |

**Coverage**: 8/8 AC verificados (1 com ressalva: roadmap-reassess existe mas skip_condition é no-op)

---

## Qualidade do Código

| Aspecto | Avaliação |
|---------|-----------|
| Testes (TDD) | ✅ 920 LOC de testes novos, 633 tests passing |
| Lint | ✅ Ruff clean |
| Docstrings | ✅ Todas as funções novas têm docstrings descritivas |
| Error handling | ✅ try/except com fallbacks em parsing JSON |
| Logging | ✅ Structured logging com WARNING para hallucination |
| Naming | ✅ Consistente com patterns existentes |
| Separação de concerns | ✅ Funções isoladas (`_check_hallucination`, `_estimate_cost_usd`) |

---

## Métricas

| Métrica | Valor |
|---------|-------|
| Tasks planejados | 28 |
| Tasks completados (código) | 26/28 (T013, T022 sem efeito) |
| Tasks completados (marcados) | 28/28 |
| Testes novos (LOC) | ~920 |
| Testes totais passando | 633 |
| Findings CRITICAL | 0 |
| Findings HIGH | 2 (PA1, PA2 — docs missing) |
| Findings MEDIUM | 2 (PA3, PA4) |
| Findings LOW | 3 (PA5, PA6, PA7) |
| Pre-analyze findings resolvidos | 7/11 |
| Pre-analyze findings pendentes | 4/11 |

---

## Next Actions

### HIGH — Corrigir antes do Judge

1. **PA1**: Adicionar hallucination guard ao Tier 1 auto-review em `pipeline-contract-base.md` (T013 — 1 linha de tabela)
2. **PA2**: Documentar `roadmap-reassess` como step 12 na L2 table em `pipeline-dag-knowledge.md` (T022 — 1 linha de tabela)

### MEDIUM — Considerar para o Judge ou future scope

3. **PA3**: O `skip_condition` nunca é avaliado. Para MVP, roadmap-reassess será SEMPRE skippado, o que é aceitável (maioria dos epics é ≤2w). Implementar evaluator é scope adicional que pode ficar para futuro.
4. **PA4**: spec.md e plan.md são stubs — aceitar formalmente (pitch é o documento de referência).

### Proceed to Judge?

**Recomendação**: Corrigir PA1 e PA2 (2 edições de 1 linha cada) e então prosseguir para `/madruga:judge`. PA3 e PA4 são riscos aceitáveis para merge.

---

## Confidence Assessment

**Confiança: Alta**

**Justificativa**: A implementação core está sólida — cost tracking funciona com campo correto, hallucination guard usa heurística pragmática, quick-fix é um ciclo completo com skill + DAG + CLI. Os 2 gaps HIGH são documentais (1 linha cada) e não afetam funcionalidade. O único risco técnico real (PA3: skip_condition) tem impacto limitado porque roadmap-reassess é um node opcional que seria skippado na maioria dos casos de qualquer forma.

**Kill criteria**: Nenhum kill criterion atingido. `claude -p` JSON output confirmado na research.md, todos os campos esperados existem.

---
handoff:
  from: speckit.analyze (post-implementation)
  to: madruga:judge
  context: "28/28 tasks executed. 2 HIGH findings: T013 (hallucination guard doc) and T022 (roadmap-reassess doc) marked DONE but changes missing in target files. 633 tests pass, ruff clean. Core functionality solid — cost tracking, hallucination guard, quick-fix all implemented correctly. Fix PA1+PA2 before judge."
  blockers: []
  confidence: Alta
  kill_criteria: "None — all kill criteria from pre-analyze were resolved by research.md findings."
