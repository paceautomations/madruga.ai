---
title: "Judge Report — Conversation Core (Epic 005)"
score: 76
initial_score: 76
verdict: fail
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
findings_total: 12
findings_fixed: 0
findings_open: 12
updated: 2026-04-12
---
# Judge Report — Conversation Core (Epic 005)

## Score: 76%

**Verdict:** FAIL (< 80)
**Team:** Tech Reviewers (4 personas)

**Nota:** Score < 80 mas sem BLOCKERs. Todos os 20 requisitos funcionais estão implementados (FR coverage 100%). Os WARNINGs são gaps de hardening (timeouts, enforcement de limites) que não afetam funcionalidade core mas impactam resiliência em produção. Recomenda-se priorizar W1-W3 antes do deploy.

---

## Judge Pass — Metodologia

4 personas executadas em paralelo. Findings brutos: 40 itens (10 arch + 10 bug + 9 simplifier + 11 stress).

Filtragem aplicada:
- **Accuracy**: 3 findings descartados por inexatidão factual
- **Deduplication**: 8 findings duplicados entre personas — mantido o melhor descrito
- **Severity reclassification**: 4 BLOCKERs propostos rebaixados para WARNING/NIT
- **Scope exclusion**: 4 findings descartados (referem a features explicitamente deferidas no pitch — Layers 2/3 guardrails, loop detection, per-tool circuit breaker)

### Reclassificações

| Finding Original | Persona | Severity Original | Severity Final | Justificativa |
|---|---|---|---|---|
| Fire-and-forget eval GC + silent exceptions | bug-hunter | BLOCKER | NIT | `save_eval_score` já tem try/except com `logger.exception` (pipeline.py:335). asyncio mantém referência forte a tasks em execução. O done_callback é cosmético. |
| Tool call hard limit not enforced | bug-hunter | BLOCKER | WARNING | pydantic-ai gerencia tool calls internamente — enforcement pós-hoc é a única opção sem fork do framework. Warning log é sinal operacional. Risco real de custo existe mas é baixo em MVP (<100 RPM). |
| DB pool exhaustion 8+ acquires/pipeline | stress-tester | BLOCKER | NIT | Conexões são adquiridas e liberadas sequencialmente (não retidas simultaneamente). Em qualquer momento, 1 pipeline usa no máximo 1 conexão. 10 concurrent pipelines = 10 conexões = exatamente o pool size. Overhead de acquire é real mas não causa exaustão. |
| Classification LLM no semaphore/timeout | stress-tester | BLOCKER | WARNING | pydantic-ai/httpx têm timeouts default internos. Classificação é chamada rápida (~500ms com gpt-4o-mini structured output). Risco real existe para cenários degradados. |
| Blocked outbound not saved | bug-hunter | WARNING | DESCARTADO | **Hallucination**: pipeline.py:630-640 salva `blocked_text` como outbound message ANTES de retornar. Finding factualmente incorreto. |
| ADR-016 Layers 2/3 absent | arch-reviewer | WARNING | DESCARTADO | Pitch §Rabbit Holes #3 explicitamente defers: "NAO implementar... Sem ML classifier (Layer B)". Decisão #4: "Guardrails somente Layer A (regex)". |
| ADR-016 loop detection absent | arch-reviewer | WARNING | DESCARTADO | Mesmo escopo deferido. ADR-016 §3 loop detection é escopo futuro (epics 014/015). |
| Per-tool retry/circuit breaker | arch-reviewer | NIT | DESCARTADO | Escopo futuro conforme pitch: "Avaliador LLM-as-judge — NAO. Sem ML classifier (Layer B)". |

---

## Findings

### BLOCKERs (0)

Nenhum BLOCKER confirmado após Judge Pass.

### WARNINGs (3 — 0/3 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| W1 | arch-reviewer + bug-hunter | **Tool call hard limit (ADR-016) logged but not enforced.** `_MAX_TOOL_CALLS_PER_CONVERSATION = 20` é verificado pós-hoc em `agent.py:294` com `logger.warning` mas nenhuma ação é tomada. O LLM pode executar 50+ tool calls antes da verificação. ADR-016 especifica "hard limit" que implica enforcement, não advisory. | `prosauai/conversation/agent.py:293-300` | OPEN | — |
| W2 | stress-tester | **Classification LLM call sem timeout explícito.** `classify_intent()` chama `agent.run()` sem `asyncio.wait_for()`. Diferente de `generate_response()` que tem timeout de 60s, a classificação pode travar indefinidamente se o provider estiver lento. | `prosauai/conversation/classifier.py:172` | OPEN | — |
| W3 | stress-tester | **Sem timeout end-to-end no pipeline.** Steps individuais têm timeouts (LLM 60s, pool acquire 5s) mas não há budget total. Sequência patológica: 5s pool wait + 60s classify + 5s pool wait + 60s generate + retry pode exceder 130s, violando SLA de 30s. `_flush_conversation` não tem timeout wrapper. | `prosauai/conversation/pipeline.py` (process_conversation) | OPEN | — |

### NITs (9 — 0/9 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| N1 | arch + bug + simplifier | **Duplicate RLS context manager**: `_acquire_conn` (customer.py:63-100) duplica `with_tenant` (pool.py:79-117). Pipeline inteiro usa `_acquire_conn` enquanto `with_tenant` é código morto no fluxo de conversação. Manutenção: fix em um não propaga ao outro. | `customer.py:63` vs `pool.py:79` | OPEN | — |
| N2 | simplifier | **`_CHARS_PER_TOKEN` duplicated** em `context.py:35` e `pipeline.py:93`. pipeline.py tem comentário admitindo: "duplicated from context.py". | `pipeline.py:93` | OPEN | — |
| N3 | simplifier | **4 unused repository methods**: `ConversationRepo.get_by_id`, `ConversationStateRepo.get_by_conversation`, `MessageRepo.count_by_conversation`, `EvalScoreRepo.list_by_conversation`. Nenhum chamado em código de produção. | `repositories.py:244,348,377,583` | OPEN | — |
| N4 | simplifier | **`ClassificationResult.prompt_template` + `_INTENT_TO_TEMPLATE` + `_resolve_template` são dead code.** Campo `prompt_template` é setado mas nunca lido por nenhum consumer. Pipeline ignora completamente. | `classifier.py:104-121`, `models.py:222` | OPEN | — |
| N5 | bug-hunter | **PII regex patterns sem word boundaries.** CPF regex `\d{3}\.?\d{3}\.?\d{3}-?\d{2}` pode matchear sequências de 11 dígitos que não são CPFs (telefones, CEPs). Adicionar `\b` reduziria false positives. | `safety/patterns.py:44-50` | OPEN | — |
| N6 | bug-hunter | **Hardcoded nil UUIDs no fallback response.** `UUID("00000000-0000-0000-0000-000000000000")` para conversation_id e message_id. Colisão entre todas as respostas fallback. | `pipeline.py:521-522` | OPEN | — |
| N7 | arch-reviewer | **Sandwich prompt sem separadores.** `f"{prefix}{prompt}{suffix}"` concatena sem `\n\n`. Se prefix não termina com newline, boundary entre safety instructions e prompt é invisível ao LLM. | `agent.py:123` | OPEN | — |
| N8 | bug-hunter + stress-tester | **httpx.AsyncClient criado por tool call.** `_fetch_rankings` cria novo client a cada chamada (TCP handshake repetido). Recomenda-se client reutilizável. | `tools/resenhai.py:120` | OPEN | — |
| N9 | bug-hunter + stress-tester | **Fire-and-forget eval task done_callback poderia logar erros.** O callback `lambda t: t.result() if not t.cancelled() and not t.exception() else None` descarta exceções silenciosamente. Embora `save_eval_score` tenha seu próprio try/except, falhas no wrapper externo passam despercebidas. | `pipeline.py:763` | OPEN | — |

---

## Findings do Analyze-Post (Upstream)

| # | Severity | Finding | Status | Ação |
|---|----------|---------|--------|------|
| PF-001 | MEDIUM | SC-001 (<30s, 95%) sem teste de latência e2e | OPEN | Adicionar `assert elapsed < 30.0` no integration test ou benchmark separado |
| PF-002 | MEDIUM | SC-007 (cobertura ≥80%) sem `--cov-fail-under=80` | OPEN | Adicionar ao pyproject.toml: `addopts = "--cov=prosauai --cov-fail-under=80"` |
| PF-003 | LOW | FR-007/FR-019 duplicação textual na spec | OPEN | Atualizar spec.md: FR-007 foca classificação, FR-019 foca template selection |
| PF-004 | LOW | Flowchart data-model.md mostra guard antes de save (implementação é save→guard) | OPEN | Atualizar flowchart para refletir ordem real + nota sobre auditoria |
| PF-005 | LOW | ConversationState na spec descreve "metadados" genéricos vs campos explícitos na implementação | OPEN | Atualizar descrição para listar campos reais |
| PF-006 | LOW | LOC estimate divergência (3900→4500→8721 real) | ACEITO | Registrar como aprendizado — estimativas conservadoras por design |

---

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| 1 | Supabase (PG 15) como BD — container Docker | 3 (Risk=3 × Reversibility=1) | N/A — decisão no pitch | ✅ Reversível: trocar BD é migration path known |
| 2 | pydantic-ai como framework LLM | 4 (Risk=2 × Reversibility=2) | N/A — decisão no pitch | ✅ Reversível: abstraído em agent.py |
| 3 | OpenAI direto sem Bifrost | 2 (Risk=2 × Reversibility=1) | N/A — decisão no pitch | ✅ Reversível: trocar URL do provider |
| 4 | Pipeline inline sem ARQ worker | 6 (Risk=3 × Reversibility=2) | N/A — decisão no pitch | ✅ Reversível: extrair para worker é refactor incremental |
| 5 | FlushCallback signature breaking change | 4 (Risk=2 × Reversibility=2) | N/A — decisions.md #10 | ✅ Backward compat com fallback None implementado |

**Nenhuma decisão 1-way-door escapou.** Todas as decisões têm score < 15 e são reversíveis.

---

## Personas que Falharam

Nenhuma. 4/4 personas retornaram findings válidos no formato correto.

---

## Files Changed (by fix phase)

Nenhum arquivo modificado. Todos os findings requerem mudanças no repositório `prosauai/` (código fonte) que está fora do escopo de escrita deste judge. Ações recomendadas documentadas abaixo.

---

## Recomendações

### Prioridade Alta (WARNINGs — resolver antes do deploy)

1. **W1 — Tool call enforcement**: Após `agent.run()` retornar, se `tool_calls_count > 20`, descartar resultado e retornar `FALLBACK_MESSAGE`. Alternativa: investigar se pydantic-ai suporta `max_tool_calls` como parâmetro do Agent.

2. **W2 — Classification timeout**: Wrapping `agent.run()` em `asyncio.wait_for(agent.run(...), timeout=15.0)` no `classify_intent()`. 15s é generoso para structured output.

3. **W3 — Pipeline timeout**: Envolver `_run_pipeline()` em `asyncio.wait_for(..., timeout=25.0)` dentro de `process_conversation()`. No timeout, retornar fallback imediatamente. 25s deixa margem para delivery.

### Prioridade Média (NITs com impacto — resolver no próximo sprint)

4. **N1 — Consolidar _acquire_conn**: Deletar `_acquire_conn` de customer.py. Usar `with_tenant` de pool.py em todos os módulos. Mover lógica de mock compat para os próprios testes.

5. **N5 — PII regex word boundaries**: Adicionar `\b` anchors nos patterns CPF e phone para reduzir false positives.

6. **N7 — Sandwich prompt separadores**: Alterar para `f"{prefix}\n\n{prompt}\n\n{suffix}".strip()`.

### Prioridade Baixa (NITs cosméticos — backlog)

7. **N2** — Importar `_estimate_tokens` de context.py em pipeline.py.
8. **N3** — Deletar 4 métodos de repo não utilizados.
9. **N4** — Deletar `prompt_template`, `_INTENT_TO_TEMPLATE`, `_resolve_template` (dead code).
10. **N6** — Usar `uuid4()` no fallback em vez de nil UUID.
11. **N8** — Criar httpx.AsyncClient no lifespan, reutilizar em tools.
12. **N9** — Adicionar logging no done_callback do eval task.

### Upstream (Analyze-Post)

13. **PF-001** — Adicionar assertion de latência no integration test.
14. **PF-002** — Adicionar `--cov-fail-under=80` ao pyproject.toml.

---

## Score Breakdown

| Item | Count | Penalty | Total |
|------|-------|---------|-------|
| BLOCKERs | 0 | ×20 | 0 |
| WARNINGs | 3 | ×5 | -15 |
| NITs | 9 | ×1 | -9 |
| **Total** | **12** | | **76** |

**Score antes de fixes:** 76
**Score após fixes:** 76 (nenhum fix aplicado — código fora do escopo de escrita)

---

## Contexto para QA

Implementação cobre 100% dos requisitos funcionais (FR-001 a FR-020). Todos os 63 tasks completados. ~8,721 LOC source + ~25,412 LOC tests (1,113 test cases). Pipeline de conversação substitui echo handler com sucesso. Os 3 WARNINGs são gaps de hardening de resiliência (timeouts e enforcement de limites) — não afetam funcionalidade core mas devem ser resolvidos antes de tráfego real.

---

handoff:
  from: judge
  to: qa
  context: "Judge completo para epic 005 — score 76% (FAIL). 0 BLOCKERs, 3 WARNINGs (tool call enforcement, classification timeout, pipeline timeout), 9 NITs. FR coverage 100%. Findings são de hardening/resiliência, não de funcionalidade. 4/4 personas executadas. Nenhuma decisão 1-way-door escapou. Recomenda-se resolver W1-W3 antes de QA full."
  blockers: ["W1: Tool call hard limit not enforced", "W2: Classification LLM no timeout", "W3: No pipeline-level timeout"]
  confidence: Media
  kill_criteria: "Se WARNINGs W1-W3 não forem resolvidos, o sistema pode violar o SLA de 30s e/ou incorrer em custos não controlados de tool calls em produção."
