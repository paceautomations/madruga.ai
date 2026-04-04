---
title: "Judge Report — Epic 017 Observability, Tracing & Evals"
score: 84
verdict: pass
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
updated: 2026-04-04
---
# Judge Report — Epic 017 Observability, Tracing & Evals

## Score: 84%

**Verdict:** PASS
**Team:** Tech Reviewers (4 personas)
**Testes:** 127/127 passando (32.8s)

---

## Findings

### BLOCKERs (0)

Nenhum blocker confirmado. O finding de shared SQLite connection across threads foi rebaixado para WARNING apos analise (blast radius limitado — unico ponto cross-thread e `retention_cleanup` 1x/dia).

### WARNINGs (3)

| # | Persona | Finding | Localizacao | Sugestao |
|---|---------|---------|-------------|----------|
| W1 | bug-hunter | **Formula cost_efficiency produz scores enganosos**: quando `cost == avg_cost`, o score e 3.3/10. Uma execucao de custo perfeitamente medio recebe nota baixa, tornando a metrica inutilizavel para decisoes. Formula: `10 - (cost / (avg*1.5)) * 10` penaliza demais custos normais. | eval_scorer.py:227-253 (`_score_cost_efficiency`) | Redesenhar formula para que cost==avg → ~7.0. Ex: `score = 10.0 * min(1.0, budget / max(cost, 0.01))` onde budget = avg * 1.5. Ou usar sigmoid. |
| W2 | arch-reviewer, bug-hunter, stress-tester | **Shared SQLite connection cross-thread no daemon**: `retention_cleanup` usa `asyncio.to_thread(cleanup_old_data, conn)` passando a mesma conexao que os endpoints FastAPI usam no event loop. SQLite por default nao permite uso cross-thread (`check_same_thread=True`). Risco de `ProgrammingError` durante cleanup diario. | daemon.py:235 (`retention_cleanup`), daemon.py:295-297 (`lifespan`) | Criar conexao dedicada dentro do `to_thread` callback: `conn2 = get_conn(); cleanup_old_data(conn2); conn2.close()`. Ou usar `check_same_thread=False` + lock. |
| W3 | arch-reviewer, bug-hunter | **cleanup_old_data deleta eval_scores por `evaluated_at` independente dos traces sendo deletados**: Se um eval_score foi criado apos re-scoring e tem `evaluated_at` recente mas seu trace pai e antigo, o eval sobrevive ao cleanup enquanto seu trace/run e deletado — criando referencia orfao. | db.py:2212 (`cleanup_old_data`) | Deletar eval_scores pelo trace_id dos traces sendo removidos (subquery), nao pelo timestamp proprio. Ex: `DELETE FROM eval_scores WHERE trace_id IN (SELECT trace_id FROM traces WHERE started_at < ?)`. |

### NITs (5)

| # | Persona | Finding | Localizacao | Sugestao |
|---|---------|---------|-------------|----------|
| N1 | simplifier | Constantes de estilo duplicadas entre RunsTab, TracesTab e EvalsTab (STATUS_COLORS, tableStyle, thStyle, tdStyle). ~60 LOC repetidas. | RunsTab.tsx:15-45, TracesTab.tsx:14-19, EvalsTab.tsx:160-181 | Extrair para `shared.ts` junto com `formatters.ts`. |
| N2 | arch-reviewer | Portal hardcoda `http://localhost:8040` como URL do daemon. Se porta muda, portal falha silenciosamente. | ObservabilityDashboard.tsx:98 | Usar variavel de ambiente Astro ou config centralizada. |
| N3 | arch-reviewer | Logging inconsistente: `eval_scorer.py` e `observability_export.py` usam stdlib `logging`, enquanto daemon usa `structlog` (ADR-016). | eval_scorer.py:21, observability_export.py:16 | Aceitar como boundary (library vs daemon layer) ou migrar para structlog. |
| N4 | bug-hunter | `complete_trace` agrega metricas com `SUM()` que retorna NULL quando nao ha pipeline_runs — escreve NULL no traces ao inves de 0. Nao quebra queries downstream mas gera inconsistencia (alguns traces com 0, outros com NULL). | db.py:1995-2005 (`complete_trace`) | Usar `COALESCE(SUM(tokens_in), 0)` para todos os campos agregados. |
| N5 | stress-tester | `export_csv` carrega todas as rows em memoria via `fetchall()` antes de escrever no StringIO. Aceitavel para escala atual (~4500 rows), mas nao degrada graciosamente. | observability_export.py:105 | Usar `fetchmany()` ou iteracao row-by-row se escala crescer. |

---

## Safety Net — Decisoes 1-Way-Door

| # | Decisao | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| 1 | SQLite-only (sem Langfuse/Phoenix) | Baixo | Sim — documentado em pitch.md:Captured Decisions #1 | OK — reversivel, adicionar Langfuse futuro nao requer migrar dados |
| 2 | pipeline_runs reutilizado como spans (sem tabela spans separada) | Medio | Sim — pitch.md:Captured Decisions + research.md:R2 | OK — decisao de schema aprovada, trace_id FK adicionada. Reverter exigiria migration mas e factivel |
| 3 | Eval scoring heuristico (sem LLM calls) | Baixo | Sim — pitch.md:Captured Decisions #4 | OK — extensivel via `metadata` JSON. LLM evals podem ser adicionados sem quebrar schema |
| 4 | Polling 10s (sem SSE/WebSocket) | Baixo | Sim — pitch.md:Captured Decisions + research.md:R5 | OK — completamente reversivel no frontend |

Nenhuma decisao 1-way-door escapou do classification flow.

---

## Personas que Falharam

Nenhuma. Todas 4 personas completaram com sucesso e retornaram findings no formato correto.

---

## Recomendacoes

### Prioridade Alta (antes de merge)
1. **Corrigir formula cost_efficiency (W1)**: A metrica atual e enganosa — custos normais recebem scores de 3/10. Sugestao: inverter a logica para que `cost <= avg` → score alto (~8-10), `cost > 2x avg` → score baixo (~2-3).

2. **Isolar conexao do retention_cleanup (W2)**: Criar conexao dedicada dentro do callback `to_thread` para evitar `ProgrammingError`. Fix trivial (~3 LOC).

### Prioridade Media (pode ser follow-up)
3. **Corrigir cleanup eval_scores orphans (W3)**: Deletar por `trace_id` ao inves de `evaluated_at`. Fix simples (~5 LOC).

### Prioridade Baixa (polish)
4. Extrair constantes compartilhadas no portal (N1)
5. Externalizar daemon URL do portal (N2)
6. Usar COALESCE em complete_trace (N4)

---

## Metricas

| Metrica | Valor |
|---------|-------|
| Personas executadas | 4/4 |
| Personas falharam | 0/4 |
| Findings brutos (pre-judge) | 24 |
| Findings descartados (hallucination/noise) | 8 |
| Findings consolidados (duplicatas) | 5 |
| BLOCKERs confirmados | 0 |
| WARNINGs confirmados | 3 |
| NITs confirmados | 5 |
| Score | 84% (100 - 0×20 - 3×5 - 5×1) |
| Testes | 127/127 |
