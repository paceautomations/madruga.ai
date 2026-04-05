---
title: "Judge Report — Epic 021: Pipeline Intelligence"
score: 77
verdict: fail
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
updated: 2026-04-04
---
# Judge Report — Epic 021: Pipeline Intelligence

## Score: 77%

**Verdict:** FAIL (threshold: 80%)
**Team:** Tech Reviewers (4 personas)
**Escalation reason:** Score < 80 → requer aprovação humana

---

## Resumo Executivo

A implementação é funcionalmente sólida — 633 testes passam, ruff limpo, 8/8 acceptance criteria atendidos. Os 2 WARNINGs são: (1) `skip_condition` nunca é avaliada (feature `roadmap-reassess` está tecnicamente quebrada como projetada), e (2) `git add -A` em `_auto_commit_epic()` pode capturar arquivos sensíveis. Nenhum BLOCKER sobreviveu ao Judge pass. O score de 77% reflete 2 WARNINGs e 13 NITs — a maioria são oportunidades de simplificação e não problemas funcionais.

---

## Findings

### BLOCKERs (0)

Nenhum. O arch-reviewer levantou skip_condition como BLOCKER, mas o Judge reclassificou para WARNING: o nó `roadmap-reassess` é **opcional** e para ≤2w (maioria dos epics) o skip é o comportamento desejado. Impacto real é baixo.

### WARNINGs (2)

| # | Persona | Finding | Localização | Sugestão |
|---|---------|---------|-------------|----------|
| W1 | arch-reviewer, bug-hunter | `skip_condition` nunca é avaliada — `if node.optional and node.skip_condition:` trata qualquer string não-vazia como truthy, skip incondicional. A expressão `"epic.appetite <= '2w'"` no platform.yaml é config theater, não avaliação real. Roadmap-reassess será SEMPRE skippado. | `dag_executor.py:1181-1182`, `dag_executor.py:1781-1782`, `platform.yaml:215` | Implementar evaluator mínimo OU trocar para flag booleano `skip: true`. Não publicar semântica de expressão que implica avaliação runtime sem implementar o evaluator. |
| W2 | arch-reviewer, bug-hunter, stress-tester | `_auto_commit_epic()` usa `git add -A` que staged TUDO no working directory — inclui potencialmente `.env`, arquivos temporários, outputs parciais de dispatches falhados. Viola orientação do CLAUDE.md ("prefer adding specific files by name"). 3 de 4 personas flaggaram. | `dag_executor.py:629` | Usar `git add` com paths explícitos (diretório do epic) ou no mínimo auditar `.gitignore` antes. |

### NITs (13)

| # | Persona | Finding | Localização | Sugestão |
|---|---------|---------|-------------|----------|
| N1 | arch-reviewer, simplifier | `_quick_mode_active` é um global mutável no módulo, setado em 2 lugares e lido em `build_dispatch_cmd()`. Coupling implícito. `build_dispatch_cmd()` já aceita `quick_mode` como parâmetro explícito. | `dag_executor.py:85, 1098, 1699, 1630` | Remover o global, passar `quick_mode` explicitamente na call chain. |
| N2 | simplifier | `SKILL_FILE_MAP` (23 entries) é redundante — `build_system_prompt()` já tem fallback convention-based que derive o path do skill name. Todas as entries seguem a convenção. | `dag_executor.py:95-121` | Deletar dict. O fallback cobre 100% dos casos. |
| N3 | simplifier | `NODE_TOOLS` tem 14/21 entries idênticas ao `DEFAULT_TOOLS`. Verbosidade sem valor. | `dag_executor.py:131-161` | Manter apenas os 7 nodes que diferem do default. |
| N4 | arch-reviewer, bug-hunter | `_estimate_cost_usd()` usa pricing Sonnet hardcoded ($3/$15 por 1M tokens). Se modelo mudar, estimativa silenciosamente incorreta. | `dag_executor.py:214-215` | Logar WARNING quando usar estimativa, incluir nome do modelo. Aceitável para MVP — `total_cost_usd` é o path primário. |
| N5 | bug-hunter | `_check_hallucination()` retorna True para `num_turns <= 2` — pode gerar false positives em skills legítimos que completam rápido. Sem whitelist de skills isentos. | `dag_executor.py:229-249` | Incluir threshold e razão no log WARNING. Considerar whitelist futura. Warning-only mode mitiga risco. |
| N6 | bug-hunter | `parse_claude_output()` captura `AttributeError` por acidente (`.get()` em dict nunca raisa, mas em list sim). Funciona, mas por coincidência. | `dag_executor.py:186-210` | Adicionar `isinstance(data, dict)` check explícito após `json.loads` (como `_check_hallucination` já faz). |
| N7 | bug-hunter, stress-tester | `build_system_prompt()` lê 4-5 arquivos sem limit de tamanho. Arquivo malformado ou binário geraria prompt gigante. | `dag_executor.py:build_system_prompt()` | Adicionar cap por arquivo (50KB) e log warning se excedido. |
| N8 | stress-tester | `_auto_commit_epic()` não tem timeout nos `subprocess.run`. Git pendurado bloqueia pipeline indefinidamente. | `dag_executor.py:_auto_commit_epic()` | Adicionar `timeout=30` nos subprocess calls. |
| N9 | simplifier | `_CONVENTIONS_HEADER` é string hardcoded que duplica trecho do CLAUDE.md. Se CLAUDE.md mudar, essa string silenciosamente diverge. | `dag_executor.py:173-180` | Ler seção do CLAUDE.md real ou aceitar como está (2KB total). |
| N10 | simplifier | Import `datetime` dentro de `format()` do `_NDJSONFormatter` — executa em cada log line no modo JSON. | `dag_executor.py:52` | Mover import para top do módulo. |
| N11 | stress-tester, bug-hunter | `_make_abort_check()` usa mesma `conn` SQLite do loop principal. Em contexto async, pode causar "database is locked". Fail-open: exceções retornam False (não abortar). | `dag_executor.py:1006-1021` | Usar conexão dedicada ou proteger com Lock. Logar exceções em WARNING. |
| N12 | arch-reviewer | dag_executor.py cresceu para 2041 LOC com 6+ responsabilidades misturadas (dispatch, observability, prompt assembly, orchestration). | `dag_executor.py (inteiro)` | Extrair dispatch config + prompt assembly para módulo separado. Escopo futuro. |
| N13 | bug-hunter | `_check_hallucination()` aceita `float` para `num_turns`. Um valor como `1.9` passaria o check `<= 2` como True. Turns devem ser inteiros. | `dag_executor.py:239` | Aceitar apenas `int` ou cast explícito. |

### Findings Descartados pelo Judge (3)

| # | Persona | Finding | Razão do Descarte |
|---|---------|---------|-------------------|
| D1 | bug-hunter | "prompt passado diretamente ao subprocess pode causar command injection" | **Inacurado**: `subprocess.run` com lista NÃO usa shell expansion. O prompt é um argumento string único passado ao CLI, sem interpretação shell. |
| D2 | stress-tester | "retry backoffs [5, 10, 20] são curtos demais para LLM" | **Fora de escopo**: backoffs são pré-existentes (não introduzidos neste epic). Circuit breaker já existia. |
| D3 | simplifier | "sync/async duplication ~300 LOC" | **Fora de escopo**: duplicação é pré-existente. O sync path é usado para `--dry-run`. Não foi introduzido neste epic. |

---

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| — | Nenhuma decisão 1-way-door identificada | — | — | — |

**Análise**: Todas as mudanças deste epic são aditivas e reversíveis:
- `--quick` flag: removível sem impacto (2-way-door, score ≈ 2)
- `total_cost_usd` field name: corrigível (2-way-door, score ≈ 1)
- Hallucination guard (warning-only): desligável (2-way-door, score ≈ 2)
- `roadmap-reassess` node: opcional, removível (2-way-door, score ≈ 2)
- Sonnet pricing hardcoded: ajustável (2-way-door, score ≈ 1)

Nenhuma decisão 1-way-door escapou.

---

## Personas que Falharam

Nenhuma — 4/4 personas completaram com sucesso.

---

## Alinhamento com Analyze-Post

| Analyze-Post Finding | Judge Confirmação |
|---------------------|-------------------|
| PA1: T013 doc missing (pipeline-contract-base.md) | **NÃO coberto** por personas (foco em código, não docs). Permanece como gap — corrigir antes de merge. |
| PA2: T022 doc missing (pipeline-dag-knowledge.md) | **NÃO coberto** por personas. Permanece como gap — corrigir antes de merge. |
| PA3: skip_condition não avaliada | **CONFIRMADO** como W1 (3 personas flaggaram). |
| PA4: spec.md e plan.md são stubs | **NÃO coberto** (personas revisam código, não process artifacts). Aceitável — pitch.md é o doc de referência. |
| PA5: Whitelist hallucination guard | **CONFIRMADO** como N5. Deferred. |
| PA6: Hardcoded pricing | **CONFIRMADO** como N4. Aceitável para MVP. |

---

## Recomendações

### Antes de merge (MUST)

1. **W2: Trocar `git add -A` por paths explícitos** em `_auto_commit_epic()`. Risco real de staged secrets. Mudança de 1 linha.
2. **PA1: Adicionar hallucination guard ao Tier 1 auto-review** em `pipeline-contract-base.md`. Uma linha de tabela.
3. **PA2: Documentar roadmap-reassess como step 12** na L2 table em `pipeline-dag-knowledge.md`. Uma linha.

### Recomendado (SHOULD)

4. **W1: Resolver skip_condition** — ou implementar evaluator mínimo, ou trocar para `skip: true` booleano. A semântica de expressão sem evaluator é confusa.
5. **N1: Remover `_quick_mode_active` global** — passar `quick_mode` explicitamente.

### Future scope (NICE TO HAVE)

6. N2: Remover `SKILL_FILE_MAP` redundante
7. N3: Trimmar `NODE_TOOLS` para 7 entries
8. N4: Pricing configurável por modelo
9. N12: Extrair módulos de `dag_executor.py`

---

## Métricas do Judge

| Métrica | Valor |
|---------|-------|
| Personas executadas | 4/4 |
| Personas falharam | 0 |
| Findings totais (pré-filter) | 28 |
| Findings descartados | 3 (1 inacurado, 2 fora de escopo) |
| Findings consolidados | 15 (2 WARNINGs + 13 NITs) |
| Consenso (≥2 personas) | W1, W2, N1, N4, N5, N7, N11, N12 (8 findings) |
| Score | 77% |
| Verdict | FAIL (< 80%) |

---
handoff:
  from: madruga:judge
  to: madruga:qa
  context: "Judge score 77% (FAIL). 0 BLOCKERs, 2 WARNINGs (skip_condition dead, git add -A), 13 NITs. Requires human approval. Fix W2 (git add -A) + PA1/PA2 (missing docs) before merge. Code is functionally solid — 633 tests pass, all ACs met."
  blockers: []
  confidence: Alta
  kill_criteria: "Se git add -A commitar segredos em produção, ou se skip_condition causar skip de nodes obrigatórios no futuro."
