---
title: "Judge Report — Epic 004: Router MECE"
score: 90
initial_score: 66
verdict: pass
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
findings_total: 14
findings_fixed: 8
findings_open: 6
updated: 2026-04-11
---
# Judge Report — Epic 004: Router MECE

## Score: 90%

**Verdict:** PASS
**Team:** Tech Reviewers (4 personas)
**Initial Score:** 66% → **Post-Fix Score:** 90%

---

## Findings

### BLOCKERs (0 — 0/0 fixed)

Nenhum BLOCKER detectado.

### WARNINGs (5 — 4/5 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| W1 | arch-reviewer, bug-hunter, simplifier, stress-tester (4/4) | `StateSnapshot.load()` async classmethod no módulo puro `facts.py` viola o padrão sans-I/O declarado na pitch. Método nunca chamado em produção (dead code) — webhook handler constrói `StateSnapshot` manualmente. Introduz precedente de I/O no core domain. | `prosauai/core/router/facts.py:75-102` | [FIXED] | Removido `StateSnapshot.load()` de `facts.py`. Testes de `TestStateSnapshotLoad` substituídos por `TestStateSnapshot` (construção direta). |
| W2 | stress-tester | `redis.mget()` para handoff check no webhook handler não tem `try/except`. Se Redis ficar indisponível após o idempotency check, exceção não tratada retorna HTTP 500, podendo gerar retry storms da Evolution API. | `prosauai/api/webhooks.py:148-151` | [FIXED] | Adicionado `try/except Exception` com fallback `conversation_in_handoff=False` (fail-open) e log warning `handoff_check_failed`. |
| W3 | bug-hunter | `Rule.matches()` ignora silenciosamente chaves `when` desconhecidas (forward-compat por design). Um typo como `form_me` em vez de `from_me` faria a regra casar mais amplamente que o esperado — risco de segurança no roteamento. | `prosauai/core/router/engine.py:164-168` | [FIXED] | Adicionado `_validate_when_keys` field_validator em `RuleConfig` que rejeita chaves não presentes em `MessageFacts.__dataclass_fields__` no load time. Typos agora geram erro de validação na carga da config. |
| W4 | bug-hunter | `resenhai.yaml` usa `default: action: RESPOND` sem agent explícito. Se tenant não tiver `default_agent_id`, todas as mensagens não casadas (reactions, events desconhecidos) causam `AgentResolutionError` → HTTP 500 em runtime. | `config/routing/resenhai.yaml:120` + `prosauai/core/router/engine.py:230` | [FIXED] | Adicionada validação cruzada no startup (`main.py` lifespan): se tenant tem regras RESPOND sem agent explícito e não tem `default_agent_id`, emite log `WARNING` com detalhes. Não é fail-fast (para não quebrar deploy com tenant em setup) mas alerta o operador. |
| W5 | analyze-post PI3 | SC-010 exige análise estática (`mypy --strict`) provando exhaustiveness do `match/case`. Implementação tem o padrão correto (5 cases + case _ guard), mas prova formal não automatizada em CI. | CI pipeline config | [OPEN — CI configuration] | Fora do escopo de código. Recomendação: adicionar `mypy --strict prosauai/core/router/` ao CI. |

### NITs (9 — 4/9 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| N1 | arch-reviewer | Classify span seta `SpanAttributes.ROUTING_ACTION` (`prosauai.action`) com valor de `event_kind` (ex: "message"), semanticamente incorreto — ROUTING_ACTION é a ação de roteamento (respond, drop), não o tipo de evento. | `prosauai/core/router/__init__.py:100-101` | [FIXED] | Alterado para `"prosauai.event_kind"` no classify span. O decide span mantém `ROUTING_ACTION` com o valor correto. |
| N2 | arch-reviewer | `DefaultConfig` não tem campo `target` + usa `extra="forbid"`, impossibilitando `BYPASS_AI` ou `EVENT_HOOK` como ação default. Nenhum validator impede essas ações. | `prosauai/core/router/loader.py:86-105` | [SKIPPED — NIT] | Impacto zero: ambos os YAMLs reais usam DROP/RESPOND como default. Documentar para futuro. |
| N3 | arch-reviewer | `RoutingEngine` dataclass não tem `slots=True`, inconsistente com todos os outros frozen dataclasses do módulo. | `prosauai/core/router/engine.py:184` | [FIXED] | Adicionado `slots=True`. |
| N4 | bug-hunter | `_to_decision()` não tem branch `case _` com raise. Se uma nova `Action` for adicionada sem atualizar o match, retorna `None` silenciosamente. | `prosauai/core/router/engine.py:228-263` | [FIXED] | Adicionado `case _: raise ValueError(f"Unknown action: {rule.action}")`. |
| N5 | bug-hunter | Overlap checker usa placeholder strings para campos livres (`instance`, `sender_phone`, `group_id`). Se regras filtrarem por `instance` específico, overlap checker pode perder conflitos ou gerar falsos positivos. | `prosauai/core/router/loader.py:192-255` | [SKIPPED — NIT] | Limitação documentada. Testes de reachability (`test_mece_reachability.py`) complementam com verificação por instance declarado em cada YAML. |
| N6 | bug-hunter | Keyword matching usa substring (`"ai" in text`), susceptível a falsos positivos com keywords curtas (ex: "ai" casa com "wait", "again"). | `prosauai/core/router/matchers.py:74-76` | [SKIPPED — NIT] | Design decision documentada. Tenants devem usar keywords suficientemente específicas. Word-boundary matching (regex) seria mais seguro mas adiciona complexidade. |
| N7 | simplifier | `load_all_routing_configs()` parseia cada YAML duas vezes: uma para peek no campo `tenant`, outra dentro de `load_routing_config()`. | `prosauai/core/router/loader.py:423-444` | [SKIPPED — NIT] | Startup-only, impacto de performance irrelevante com 2 tenants. Refatorar quando necessário. |
| N8 | simplifier | `_check_unique_priorities` e `_check_unique_names` usam padrão O(n²) com lista em vez de set. | `prosauai/core/router/loader.py:169-183` | [FIXED] | Trocado `list` por `set` para O(n) duplicate detection. |
| N9 | stress-tester | `keyword.lower()` é computado em cada chamada de `matches()` em vez de pré-computado na construção. | `prosauai/core/router/matchers.py:76-78` | [SKIPPED — NIT] | Frozen dataclass com `slots=True` impede `__post_init__` com `object.__setattr__` para campo não declarado. Keywords são poucos e matches() é chamada uma vez por mensagem. Impacto negligenciável. |

---

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| 1 | Remoção de enum `MessageRoute` + `route_message()` + `_is_bot_mentioned()` + `_is_handoff_ativo()` | 12 (remove feature × hours) | N/A — refactor interno, zero consumers externos | 2-way-door ✅ — 26 fixtures reais comprovam equivalência |
| 2 | Rename `ParsedMessage` → `InboundMessage` | 1 (rename/refactor × minutes) | N/A — rename interno | 2-way-door ✅ |
| 3 | Adição de `default_agent_id` a `Tenant` | 2 (schema add × minutes) | N/A — campo aditivo, backward-compatible | 2-way-door ✅ |

**Nenhuma decisão 1-way-door escapou.** Todas as mudanças são reversíveis sem perda de dados.

---

## Personas que Falharam

Nenhuma — 4/4 personas completaram com sucesso.

---

## Files Changed (by fix phase)

| File | Findings Fixed | Summary |
|------|---------------|---------|
| `prosauai/core/router/facts.py` | W1 | Removido `StateSnapshot.load()` async classmethod (sans-I/O violation) |
| `prosauai/api/webhooks.py` | W2 | Adicionado try/except no handoff MGET com fail-open |
| `prosauai/core/router/loader.py` | W3, N8 | Validação de `when` keys + set para duplicate detection |
| `prosauai/main.py` | W4 | Cross-validação startup: RESPOND sem agent + tenant sem default |
| `prosauai/core/router/__init__.py` | N1 | Classify span usa `prosauai.event_kind` em vez de `ROUTING_ACTION` |
| `prosauai/core/router/engine.py` | N3, N4 | `slots=True` em RoutingEngine + `case _` fallback em `_to_decision` |
| `tests/unit/test_facts.py` | W1 | Testes de `StateSnapshot.load()` substituídos por testes de construção |

---

## Recomendações

### Para findings OPEN:

1. **W5 (mypy CI)**: Adicionar `mypy --strict prosauai/core/router/` como step no CI pipeline. O código já está correto (match/case com 5 cases + unreachable guard), mas a prova formal automatizada fortalece a garantia de exhaustiveness. Prioridade: MEDIUM.

2. **N2 (DefaultConfig target)**: Quando/se um tenant precisar de `BYPASS_AI` ou `EVENT_HOOK` como ação default, adicionar campo `target` a `DefaultConfig` ou restringir ações default via validator. Prioridade: LOW (nenhum caso de uso atual).

3. **N5 (overlap string fields)**: Considerar enumerar valores de `instance` declarados nas regras durante overlap analysis. Os testes de reachability (`test_mece_reachability.py`) já cobrem parcialmente este gap. Prioridade: LOW.

4. **N6 (keyword precision)**: Documentar nos tenants.example.yaml que keywords curtas (< 3 caracteres) podem gerar falsos positivos. Considerar word-boundary matching em epic futuro se isso se tornar problema. Prioridade: LOW.

5. **N7 (double YAML parse)**: Refatorar `load_all_routing_configs` para aceitar dados já parseados quando o número de tenants crescer significativamente. Prioridade: LOW.

6. **N9 (keyword .lower())**: Se o número de keywords por tenant crescer ou throughput de mensagens aumentar, considerar pré-computar keywords em lowercase. Prioridade: LOW.

### Validação final:

- **947 testes passando** (32 skipped — hypothesis database, não relevante)
- **Ruff lint**: 0 erros
- **Zero referências ao enum legado** confirmado via grep
- **MECE property tests**: todas as ~400 combinações válidas verificadas para ambos os YAMLs reais

---
handoff:
  from: judge
  to: qa
  context: "Judge report completo. Score 90% (PASS). 14 findings totais: 8 fixados, 6 open (1 WARNING de CI config + 5 NITs de design). Nenhum BLOCKER. Nenhuma decisão 1-way-door escapou. 947 testes passando. Pronto para QA testing."
  blockers: []
  confidence: Alta
  kill_criteria: "Se os testes de propriedade MECE falharem após as alterações do Judge, ou se a remoção de StateSnapshot.load() quebrar código downstream não detectado."
