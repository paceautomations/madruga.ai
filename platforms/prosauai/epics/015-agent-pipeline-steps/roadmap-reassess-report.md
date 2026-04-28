---
type: roadmap-reassess-report
epic: 015-agent-pipeline-steps
date: 2026-04-27
reassessor: madruga:roadmap (L2 terminal node)
previous_roadmap_updated: 2026-04-17
status: proposta
verdict: APPLY_PATCHES_AND_REPRIORITIZE
next_epic_recommendation: 016-pipeline-hardening (P1) seguido de 017-agent-versioning-canary (P2)
---

# Roadmap Reassess — Pos Epic 015 (Agent Pipeline Steps)

**Data:** 2026-04-27 | **Cycle:** L2 (terminal node 12/12) | **Modo:** Autonomo (dispatch)

---

## 1. Executive Summary

Epic 015 **shipou o coração do sub-routing configurável** (executor declarativo + 5 step types + condition evaluator + sub_steps tracing) mas chega ao terminal L2 com dois pacotes de débito que precisam ser refletidos no roadmap antes do próximo ciclo:

- **Entregue:** PR-1..PR-4 mergeados (Foundational + executor + 3 step types core + tracing + resolver/summarizer); PR-5/PR-6 frontend executados (admin UI + Trace Explorer sub_steps + filtros). 132/132 testes do epic 015 verdes; suite total 2534/2535. SC-008 (regressão zero) + SC-010 (overhead p95 ≤5 ms) verificados pelo `test_pipeline_backwards_compat.py` + benchmark T051. Zero novas dependências Python. Cut-line `[DECISAO AUTONOMA]`: PR-5/PR-6 mantidos; Phase 9 (US4 — group-by-version canary) **DEFERRED** per D-PLAN-02.
- **Em aberto:** 5 BLOCKERs do Judge (B1-B5) + 16 WARNINGs + 9 NITs no repo externo `paceautomations/prosauai`. Judge verdict **FAIL score 35/100** com fixes bloqueados por sandbox. Reconcile drift score 54.5% (5/11 docs OUTDATED) com 6 doc-side diffs prontos para aplicar (ADR-006 amend, ADR-019 amend, domain-model.md, blueprint.md, tech-alternatives.md, roadmap.md). 17 Open Items rastreados (OI-1..OI-17).
- **Consequência para roadmap:** (a) o slot "022 Agent Pipeline Steps" no roadmap atual está errado — o epic foi entregue em **015** e precisa de status `shipped-pendente-blockers`; (b) o **5 BLOCKERs do judge são incompatíveis com produção** — pool starvation, exceção narrow no executor, cross-tenant attach via `id()` reuse, audit_log NotNullViolation, race em PUT replace — e exigem **epic 016 dedicado de hardening** antes de qualquer outro consumer do executor; (c) **Phase 9 deferred cria seam claro** para epic 017 (agent-versioning + canary) com escopo bem definido; (d) renumeração do roadmap precisa absorver os dois novos epics (016 + 017) e validar que os slots futuros 015-022 (atualmente listados em "Epics Futuros") continuam fazendo sentido após desbloquear `agent_config_versions`.

**Veredito:** APPLY_PATCHES_AND_REPRIORITIZE — aplicar 6 doc-diffs do reconcile (ADR-006/019 amends, domain-model, blueprint, tech-alternatives, roadmap) **antes** de iniciar epic 016. Criar epic 016-pipeline-hardening (1-2 sem) cobrindo B1-B5 + W1-W4-W11 + W14-W16. Postergar epic 017-agent-versioning-canary até 016 fechar.

**Confidence:** Alta com ressalva. A ressalva é que os BLOCKERs do judge **não foram fix-and-validados** (sandbox bloqueou edits no repo externo). Métricas de produção ainda não confirmaram que o overhead se mantém ≤5 ms p95 sob carga real (SC-010 foi medido em benchmark sintético; validação em staging fica como OI-16).

---

## 2. O Que Mudou (learnings do epic 015)

| Categoria | Learning | Impacto no Roadmap |
|-----------|----------|---------------------|
| **Escopo** | Cut-line `[DECISAO AUTONOMA]` foi acionado em modo **expandir** (PR-5/PR-6 mantidos) e não cortar. Veio de ganho de momentum: PR-1..PR-4 fecharam dentro de 2.5 semanas e o time tinha capacidade marginal. | Calibrar cut-lines futuros como **gatilho real** (data + métrica de progresso), não como compromisso teórico. Documentar que cut-line foi NÃO acionado e por quê. |
| **Escopo** | Phase 9 DEFERRED foi **corretamente identificada na plan** (D-PLAN-02) e não em pós-mortem — `agent_config_versions` (ADR-019) foi documentado como "Accepted but not shipped" desde o plan, evitando descoberta tardia. | Padrão a replicar: **pre-flight check em ADRs aprovados vs. produção** antes de qualquer plan que dependa deles. Adicionar como passo em `/speckit.plan`. |
| **Arquitetura** | Executor declarativo + sub_steps JSONB column funcionou — backwards-compat byte-equivalente confirmado por `test_pipeline_backwards_compat.py` + benchmark T051 ≤5 ms p95 em ambiente sintético. | Padrão de orquestração reutilizável; mesmo modelo serve para trigger engine (epic futuro) e RAG step injection (epic 012 / KB-RAG). |
| **Dados** | `trace_steps.sub_steps` JSONB com cap 32 KB / 4 KB por elemento ficou dentro do orçamento estimado (~1.8 GB cumulativos em 30d / 6 tenants), MAS a estimativa **ainda não foi validada empiricamente** com pipeline configurado em produção. | Antes de adoção em >1 tenant, instrumentar `trace_steps_substeps_bytes_p95` (T074) e medir 7d em staging. Risco análogo ao da estimativa errada do epic 008 (factor 20-80x). |
| **Decisões** | 12 D-PLAN entries capturadas + 1 promoção candidata (D-PLAN-02 → ADR via `/madruga:adr`). 4 D-PLANs ficam epic-local (LOW priority); 5 promoções MEDIUM ficam para reavaliação pós-produção. | Manter o padrão: emitir D-PLAN-XX com rationale + alternativa rejeitada DURANTE o plan, não apenas post-hoc. Pipeline executor é case-study positivo. |
| **Sandbox/Modo Autônomo** | Tanto o judge quanto o reconcile foram bloqueados por sandbox para edits no repo externo `paceautomations/prosauai`. Resultado: 21 fixes desejáveis + 6 doc-diffs ficaram **propostos mas não aplicados**. | Para próximo epic externo: **ou** liberar sandbox para edits no repo bound (com guard-rails extras), **ou** aceitar que findings de judge/reconcile viram backlog e planejar epic de hardening dedicado **explicitamente no roadmap** desde o início. |
| **Frontend** | PR-5/PR-6 (admin UI + Trace Explorer extension) reusaram TanStack Query v5 + shadcn + openapi-typescript do epic 008 sem fricção. Discriminated union para 5 step types funcionou bem com Pydantic + zod paralelo. | Padrão estabelecido para qualquer epic que toque admin UI: replicar stack do 008 sem alterar dependências. Documentar como ADR de "frontend baseline" se >2 epics replicarem. |
| **Observabilidade** | Sub-spans `conversation.pipeline.step` + structlog dedup-once-per-(agent_id, step_index) evitaram log flood em condition errors. | Pattern de "warn-once por chave" é replicável; considerar extrair `prosauai/common/warn_once.py` se aparecer em 3º consumer (regra de três). |
| **Processo** | Reconcile capturou **5 OUTDATED docs** entre business/engineering/decisions/planning — drift score 54.5%. ADRs aprovados (ADR-006, ADR-019) precisaram de amendments por mudanças que estendem (não contradizem) suas decisões. | Padrão a registrar: **mudança que estende ADR aprovado** vira `## YYYY-MM Amendment` no próprio ADR, não novo ADR. Já documentado no `/madruga:reconcile` como pattern. |
| **Processo** | 7 tasks Phase 9 marcadas `[x]` mas com nota "DEFERRED per T110" — mesma anti-pattern do epic 008 (T030, T055, T904 etc.). | Em próximo epic, tasks `[x]` só com validação empírica concluída; DEFERRED → `[~]` com link para o slot futuro. Atualizar template de tasks.md para incluir esse marker. |

---

## 3. Renumeração de Epics (proposta)

O roadmap atual lista o epic em "Epics Futuros" como **slot 022 — Agent Pipeline Steps**. Realidade: o epic foi materializado e shipped no slot **015**. Precisa de:

1. **Promover 015** da seção "Epics Futuros" para a tabela principal com status `shipped-pendente-blockers`.
2. **Inserir 016 (NOVO) — Pipeline Hardening** como next epic P1 (cobre BLOCKERs B1-B5 + WARN priorizados).
3. **Inserir 017 (NOVO) — Agent Versioning + Canary** como follow-up P2 (materializa ADR-019 e habilita Phase 9 deferred).
4. **Bump de slots futuros** 015-022 (epics ainda não materializados) → 018-024 para abrir espaço.
5. **Validar** se "epic 022 Agent Pipeline Steps" no roadmap atual era apenas placeholder ou se deve ser deletado da seção (já que o real é 015 shipped). `[DECISAO AUTONOMA]`: deletar a entrada placeholder; cross-link em "Epics Shipped" aponta para 015.

### Antes (roadmap atual em 2026-04-17)

| Slot | Epic | Status |
|------|------|--------|
| 7 | 007: Admin Front Foundation | shipped |
| 8 | 008: Admin Evolution | in-progress (152/158) |
| 9 | 009: Agent Tools | sugerido |
| 10 | 010: Handoff Engine | sugerido |
| 11 | 011: Trigger Engine | sugerido |
| 13 | 013: Admin Handoff Inbox | sugerido (depende de 010) |
| 022 | 022: Agent Pipeline Steps | placeholder em "Epics Futuros" |

### Depois (proposta pos-015)

| Slot | Epic | Mudança | Deps | Prioridade |
|------|------|---------|------|------------|
| 7 | **007: Admin Front Foundation** | sem mudança — shipped | 006 | done |
| 8 | **008: Admin Evolution** | sem mudança — shipped (gated em B1-B5 do 008) | 006, 007 | done* |
| 9 | **009: Agent Tools** | sem mudança — sugerido | 006 | P2 |
| 10 | **010: Handoff Engine** | sem mudança — sugerido (epic dir 010-handoff-engine-inbox já existe) | 006, 008 | P2 |
| 11 | **011: Trigger Engine** | sem mudança — sugerido | 010 | P3 |
| 13 | **013: Admin Handoff Inbox** | sem mudança — sugerido (depende de 010) | 010 | P3 |
| **015** | **015: Agent Pipeline Steps** ⬅ promovido de "Epics Futuros" | **shipped-pendente-blockers** (PR-1..PR-6, Phase 9 deferred) | 008 | done* |
| **016** | **016: Pipeline Hardening** (NOVO) | **NEW** — fecha B1-B5 + W1/W2/W3/W4/W11/W14/W15/W16 do judge-report; aplica 6 doc-diffs do reconcile | 015 | **P1 — next** |
| **017** | **017: Agent Versioning + Canary** (NOVO, ex-D-PLAN-02 follow-up) | **NEW** — materializa `agent_config_versions` (ADR-019) + traffic split per agent_version + group-by-version UI; habilita US4/Phase 9 do 015 | 015, 016 | P2 |
| ~~022 Agent Pipeline Steps~~ | placeholder em "Epics Futuros" | **REMOVIDO** — substituído por 015 shipped | — | — |

**Observação importante:** os epic-dirs `009-channel-ingestion-and-content-processing`, `011-evals`, `012-tenant-knowledge-base-rag` **já existem** em `platforms/prosauai/epics/` mas seu status no roadmap atual é confuso. Isso é **fora-do-escopo** desta reassess (foram criados em ciclos anteriores que não passaram pelo terminal node de roadmap-reassess) e devem ser tratados em uma reassess explícita do roadmap quando o próximo epic L1 começar. `[DECISAO AUTONOMA]`: este relatório **não tenta reconciliar** os mismatches herdados — apenas adiciona 015/016/017 sem mexer nos slots existentes.

---

## 4. Próximo Epic — Recomendação

### Opção A (recomendada): 016-pipeline-hardening

**Problema:** Epic 015 não pode ser promovido como produção-ready com 5 BLOCKERs abertos. Tentar pular para 016 = agent-versioning sem fechar o débito do executor expõe os 5 BLOCKERs em superfície N×.

**Appetite:** 1-2 semanas (≤200 LOC + testes + 1 migration de índice).

**Escopo mínimo (must — todos os 5 BLOCKERs + WARN críticos):**
- **B1** Converter `_PIPELINE_EXEC_METADATA` para `WeakKeyDictionary` ou `asyncio.ContextVar` — eliminar `id()` reuse cross-tenant. (~20 LOC)
- **B2** Broaden executor exception filter para `(Exception,)` com explicit allow-list de provider errors (httpx, openai, anthropic, pydantic_ai). (~15 LOC)
- **B3** Fix divergent error path em `cost_usd` coerce — reusar helper `_safe_decimal()` em ambos os call-sites. (~10 LOC)
- **B4** Adicionar expression index `idx_audit_log_pipeline_steps_agent` em `(details->>'agent_id', created_at DESC)` filtrado por `action='agent_pipeline_steps_replaced'`. (1 migration)
- **B5** Adicionar `pg_advisory_xact_lock` (chave hash de `agent_id`) na PUT replace transaction — eliminar last-writer-wins race. (~25 LOC)

**Escopo stretch (should — WARN priorizados):**
- **W1+W2+W12** Tighten `_OP_PATTERN` regex com `\b` boundary e single-source-of-truth (eliminar duplicata em `pipeline_steps.py:293`). (~20 LOC + testes hypothesis)
- **W4** `audit_log.ip_address INET NULL` schema relax + app-layer fallback `0.0.0.0/0` sentinel — sem perder rows. (1 migration + ~15 LOC)
- **W11** REVOKE write em `agent_pipeline_steps` de `pool_admin` ou pre-validar `tenant_id` no admin endpoint. (1 migration ou ~15 LOC)
- **W13+W14** Extrair `_extract_tokens()` + `_zero_cost()` para `prosauai/conversation/steps/_helpers.py` (rule of three já violada 5×). Refator `_validate_step_config` para registry-pattern. (~70 LOC movidas + ~50 reescritas)
- **W15** Cachear pydantic-ai `Agent` instances per (model, prompt_version) — eliminar 30-100 ms de CPU por step × 5 steps. (~30 LOC + LRU cache)
- **W16** Adicionar circuit breaker simples (consecutive-failures threshold) + jitter no retry. (~50 LOC + dep zero — implementar inline)

**Escopo absolutamente fora (cut-line):**
- **W5** Rollback para "no pipeline" via DELETE explícito — vira ADR-amendment, não epic 016. Operacional: documentar no runbook.
- **W6** Dead code em `_serialise_sub_steps` — NIT cleanup, não bloqueia.
- **W7** `ClarifierConfig.max_question_length` admin/runtime drift — fixa em ADR ou aceita 140 hard-coded.
- **W8/W9/W10** Schema docs vs implementation drift — vira tarefa de doc-author dentro do reconcile.
- **N1-N9** Nits ficam para 016 stretch ou epic 017+.

**Out-of-scope absolutos:**
- Implementar `agent_config_versions` (vira epic 017).
- Adicionar novos step types (mantém 5 atuais).
- Mudar grammar de `condition` (mantém v1 — operadores `<,>,<=,>=,==,!=,in` + AND-implicit).

**Justificativa da prioridade:** os 5 BLOCKERs todos têm **probabilidade Alta** de manifestar com >1 tenant adotando pipeline. B1 (cross-tenant attach via `id()`) é uma vulnerabilidade de isolamento que viola RLS na prática. B5 (race em PUT replace) corrompe `audit_log` silenciosamente. Adicionar epic 017 (versioning) sem fechar isso = duplicar surface de ataque sobre a mesma fundação frágil.

**Kill criteria do epic 016:** se durante implementação (a) substituir `_PIPELINE_EXEC_METADATA` por `ContextVar` exigir refactor profundo no `pipeline.py:_run_pipeline` (passa o `PipelineExecutionResult` como retorno em vez de side-channel) — escopo arquitetural, não pontual; (b) `pg_advisory_xact_lock` colidir com algum lock já em uso pelo `pool_admin` em outros endpoints — exige inventário de locks antes de continuar; (c) o stretch (W13+W14 refactor) demorar >3d por dependências em `agent.py:get_enabled_tools` — corta-se o stretch e fica para 017+.

### Opção B (não recomendada agora): 017-agent-versioning-canary

**Problema:** ADR-019 está "Accepted but not shipped". Épico 015 deferred Phase 9 (US4 — group-by-version) por isso. Materializar `agent_config_versions` + traffic split + group-by-version UI completa o escopo original do 015.

**Appetite estimado:** 2-3 semanas (tabela + endpoints CRUD + traffic_pct mechanism + UI).

**Por que não agora:** os 5 BLOCKERs do 015 ainda estão abertos. Versioning sobre fundação frágil multiplica os bugs (cada version vai ter o mesmo race em PUT replace, mesma exception narrow, etc.). 016 prepara o terreno para 017 ser barato.

**Quando vira P1:** após 016 fechar com smoke validado em staging; OU se a primeira tentativa de canary real (split de tráfego entre dois agentes equivalentes em produção) bloquear em alguma decisão de prompt/modelo por 7+ dias por falta de comparação A/B objetiva.

### Opção C (não recomendada): 010-handoff-engine ou 011-evals (dirs já existem)

**Problema:** os epic-dirs existem mas sem entrada explícita no roadmap em estado consistente. Tentar abri-los agora ignora o débito do 015 e adiciona um terceiro forearm aberto na mesma ferramenta (executor).

**Por que não agora:** mesmo argumento da Opção B — fundação ainda frágil.

**Quando vira P1:** após 016 fechar e com decisão explícita de roadmap-reassess no epic anterior daquela linha de trabalho.

---

## 5. Outcomes (atualizados pos-015)

| Objetivo de Negócio | Outcome Mensurável | Baseline (pre-015) | Target 90d | Epics que Contribuem |
|---------------------|---------------------|---------------------|-------------|----------------------|
| Reduzir custo médio do agente generalista | USD/mensagem em `messages.cost_usd` agregado por agent | ~USD 0.0042 (Ariel single-call) | -30% (~USD 0.0029) | **015 (entregue, dependendo de adoção real)**, 016 hardening (preserva benefício), 017 versioning (canary objetivo) |
| Reduzir latência p95 para casos triviais (greeting/simple_query) | latency_ms_p95 por intent | ~1800 ms | <1000 ms | **015 (entregue)**, 016 (preserva), W15 cache de Agent reduz mais ~150 ms |
| Reduzir taxa de retomadas ("não foi isso que perguntei") | % conversas com 2+ reformulações nas primeiras 3 mensagens | 14% (estimado) | -30% (≤10%) | **015 (entregue — clarifier US2)** |
| Configurar pipeline sem SQL | % sessões de config via UI vs SQL direto | 0% (só SQL) | >80% (após PR-5 em produção) | **015 PR-5 (entregue)**, 016 hardening (mantém UI confiável) |
| Tempo médio de adicionar/ativar 1 step novo | minutos do login admin até step ativo | ~30 min via SQL + redeploy mental | <3 min via UI (SC-006) | **015 PR-5 (entregue)** |
| Identificar step responsável por latência/erro em 1 mensagem | minutos do trace_id ao diagnóstico | >60 min (logs + journalctl) | <1 min via Trace Explorer (SC-007) | **015 PR-6 (entregue)**, 008 (Trace Explorer base) |
| Comparar versões de agente lado-a-lado (canary objetivo) | # decisões de promote/rollback baseadas em group-by-version | 0 (não disponível) | ≥1 promoção/quarter usando o canary | **017 (proposto)** — Phase 9 deferred do 015 |
| Adoção do pipeline em tenants ativos | # tenants com ≥1 step ativo em produção | 0 | ≥2 em 60d (SC-011) | **016 hardening** (pré-requisito de adoção segura), 015 (pipeline entregue) |

**Confiança nos outcomes:** Média. 5 dos 8 outcomes ficam `[VALIDAR]` até **(a) primeiro tenant configurar pipeline em produção via SQL** (operacional — runbook OI-runbook pronto) **e (b) 7d de telemetria real** (`messages.cost_usd`, `latency_ms_p95`, `trace_steps_substeps_bytes_p95`). Outcomes **5, 6** são técnico-de-feature e ficam Alta sem precisar de adoção (UI funciona, Trace Explorer funciona).

---

## 6. Novos Riscos Identificados pelo Epic 015

| Risco | Impacto | Probabilidade | Mitigação proposta no próximo ciclo |
|-------|---------|---------------|---------------------------------------|
| `_PIPELINE_EXEC_METADATA` cross-tenant attach via `id()` reuse (B1) | **Alto** — viola isolamento RLS na camada de aplicação | Média (depende de carga + GC pressure) | Epic 016: `WeakKeyDictionary` ou `ContextVar` |
| Executor exception filter narrow (B2) | **Alto** — provider error não-classificado crasha message-delivery, viola FR-026 | Alta (provider 5xx storms recorrentes) | Epic 016: `(Exception,)` + allow-list rebroadcast |
| Cost coercion divergent error paths (B3) | Médio — InvalidOperation crasha após LLM bem-sucedido | Baixa (depende de provider devolver NaN/Inf) | Epic 016: `_safe_decimal` helper único |
| Audit-log rollback query sem expression index (B4) | Médio — rollback intermitente >100k audit rows | Alta (volume cresce com adoção admin) | Epic 016: migration `idx_audit_log_pipeline_steps_agent` |
| Race em PUT replace sem optimistic locking (B5) | **Alto** — last-writer-wins corrompe audit_log timeline silenciosamente | Alta (em qualquer cenário 2+ admins) | Epic 016: `pg_advisory_xact_lock` por `agent_id` |
| `_OP_PATTERN` typo silently misparsed como `in` op (W1) | Baixo — admin passes 422, runtime fails closed | Média (operadores typam) | Epic 016: `\b` boundary + reject empty `in [...]` |
| `audit_log.ip_address INET NOT NULL` causa silent loss (W4) | Médio — viola compliance (SOX/GDPR completeness) | Média (depende de proxy strip de X-Forwarded-For) | Epic 016: schema relax para `INET NULL` + app-layer fallback |
| `pool_admin` BYPASSRLS escreve em tabela RLS-on (W11) | Médio — surface para cross-tenant em endpoint futuro | Baixa (mitigado por validação atual) | Epic 016: REVOKE write OR pre-validar `tenant_id` |
| 5x duplicate `_extract_tokens` + `_zero_cost` (W13) | Baixo — drift inevitável | Alta (regra de 3 violada 5×) | Epic 016: extrair `prosauai/conversation/steps/_helpers.py` |
| `pydantic_ai.Agent(...)` reconstruído por chamada (W15) | Médio — 30-100 ms × 5 steps em hot path | Alta (todo pipeline configurado) | Epic 016: LRU cache per (model, prompt_version) |
| Sem backoff/circuit breaker em LLM calls (W16) | **Alto** — provider 429 storm = thundering herd | Média (com >2 tenants reais) | Epic 016: circuit breaker simples + jitter |
| `agent_config_versions` ausente (D-PLAN-02 + ADR-019 amend) | Médio — sem canary objetivo, decisões de promote ficam intuitivas | Certa (já materializado) | Epic 017 (versioning + canary) |
| `trace_steps.sub_steps` storage ainda não validado em produção | Médio — análogo ao erro de sizing 20-80x do epic 008 | Média | Epic 016: instrumentar `trace_steps_substeps_bytes_p95` (T074) + 7d staging antes de adoção em ≥2 tenants |
| Reconcile drift score 54.5% — 5 docs OUTDATED não aplicados | Baixo — documentação contradiz produção | Certa | Epic 016 D0: aplicar 6 doc-diffs do reconcile-report |

---

## 7. Não Este Ciclo (exclusões conscientes)

| Item | Motivo da Exclusão (data) | Revisitar Quando |
|------|---------------------------|-------------------|
| **`agent_config_versions` table + traffic split** | D-PLAN-02 — 015 tinha appetite 3 sem; versioning soma 1.5-2 sem; cut-line sustentado | Epic 017 (NEW) — após 016 fechar |
| **OR/parens no condition evaluator** | FR-024 v1 deliberadamente conservadora; superset compatível com AST futuro | Quando aparecer 3º caso real que não cabe em condições mutuamente exclusivas |
| **Configurável `MAX_PIPELINE_STEPS_PER_AGENT` por tenant** | FR-003 — hard-coded 5; configurabilidade adiciona surface sem benefício comprovado | Quando aparecer 1º caso real legítimo de 6+ steps (raro, espera-se nunca) |
| **Retry inteligente entre steps** | FR-026 — fallback canned imediato; previsibilidade de latência > recuperação parcial | Se métricas de produção mostrarem >5% mensagens caindo em fallback por step intermediário transient |
| **Granularidade de canary per-step** | Escopo é per-agent-version (017); per-step é epic próprio | Quando 017 estabilizar e aparecer caso real de A/B intra-pipeline |
| **6º step type (validator/enricher/etc.)** | Out-of-scope — 5 tipos cobrem usos imediatos identificados; CHECK pode ser estendido sem migration breaking | Quando 2+ tenants pedirem o mesmo novo tipo |
| **Redis cache de `pipeline_steps` lookup** | D-PLAN-05 — SC-010 ≤5 ms p95 atendido sem cache; cache adiciona stale config surface | Se produção mostrar p95 > 3 ms sustained por 7d |
| **Materialized view de Performance AI per-version** | Depende de 017 (versioning); cache Redis 5 min do 008 já cobre <5 admins | Após 017 + >10 admins ou >3 versões ativas simultaneamente |
| **W5 Rollback para "no pipeline" via UI** | Operacional via SQL; admin/UI fica confuso ("0 steps salvos = pipeline?"); aceita-se DELETE explícito | Quando primeiro admin pedir rollback "para single-call" e SQL não estiver disponível |
| **W6 dead code cleanup em `_serialise_sub_steps`** | NIT — funcionalmente correto, só misleading | Hygiene em epic 017+ |
| **W7 `max_question_length` runtime hard-cap** | Aceita-se 140 hard-coded ou vira admin schema validation com `Literal[140]` | Quando primeiro tenant pedir clarifier longo (>140) |
| **N1 índice incluindo `tenant_id`** | RLS predicate adiciona `tenant_id` no scan; índice atual SC-010 atendido | Após adoção em ≥3 tenants e telemetria mostrar overhead lookup >2 ms |

---

## 8. Mudanças Propostas no `planning/roadmap.md`

Pré-requisito: aplicar 6 doc-diffs do `reconcile-report.md` (OI-1..OI-6) **antes** de iniciar epic 016.

### Seção Status (linhas 12-17 do roadmap atual)

```diff
- **L2 Status:** Epic 001 shipped (...). Epic 008 in-progress (...).
- **Próximo marco:** merge epic 008 + primeiro deploy de produção VPS.
+ **L2 Status:** Epic 001-006 shipped (MVP). Epic 007 shipped (admin foundation). Epic 008 shipped-pendente-blockers (Admin Evolution — 152/158 tasks). **Epic 015 shipped-pendente-blockers** (Agent Pipeline Steps — PR-1..PR-6 mergeados; Phase 9 [US4 group-by-version] deferred para epic 017; 5 BLOCKERs + 16 WARN do judge abertos no repo externo).
+ **Próximo marco:** Epic 016-pipeline-hardening (1-2 sem) — fecha B1-B5 do 015 + 8 WARN priorizados; aplica 6 doc-diffs do reconcile. Depois: Epic 017-agent-versioning-canary (2-3 sem) ou Epic 010-handoff-engine conforme prioridade do produto.
```

### Epic Table — adicionar 3 linhas (após linha 77 atual)

```diff
+ | 14 | **015: Agent Pipeline Steps** | 008 | médio | Post-MVP | **shipped-pendente-blockers** (PR-1..PR-6 mergeados; Phase 9 deferred; 5 BLOCKERs + 16 WARN abertos) |
+ | 15 | **016: Pipeline Hardening** (NOVO) | 015 | baixo | Post-MVP | **proposto — P1 next** (1-2 sem; B1-B5 + W1/W2/W4/W11/W13/W15/W16 + 6 doc-diffs do reconcile) |
+ | 16 | **017: Agent Versioning + Canary** (NOVO) | 015, 016 | médio | Post-MVP | **proposto — P2** (2-3 sem; materializa ADR-019, habilita Phase 9 deferred do 015) |
```

### Tabela "Epics Futuros" — remover linha 022

```diff
- | 022: Agent Pipeline Steps | Pipeline de processamento configurável por agente (...) | 008 | Later |
+ (linha removida — epic foi materializado em 015 e está na tabela principal)
```

### Seção Dependencies (Mermaid) — acrescentar 3 nodes

```diff
   E008 --> E009[009 Agent Tools]
   E008 --> E010[010 Handoff Engine]
   E010 --> E011[011 Trigger Engine]
   E010 --> E013[013 Admin Handoff Inbox]
-  E009 --> E022[022 Agent Pipeline Steps]
+  E008 --> E015[015 Agent Pipeline Steps - shipped-pendente-blockers]
+  E015 --> E016[016 Pipeline Hardening - PROPOSTO]
+  E016 --> E017[017 Agent Versioning + Canary - PROPOSTO]
```

### Seção Milestones (linhas 124-134)

```diff
| Milestone | Epics | Critério | Estimativa |
| MVP | 001-006 | (sem mudança) | realizado |
| Admin | 007, 008, 013 | (sem mudança) | ~8 semanas |
+ | **Pipeline Sub-Routing** | **015, 016, 017** | **015 shipped-pendente-blockers; 016 fecha B1-B5 + WARN priorizados; 017 entrega versioning + canary objetivo** | **~5 semanas (016 + 017)** |
| Post-MVP | 009, 010, 011 | (sem mudança) | ~6 semanas |
```

### Seção Roadmap Risks — acrescentar 5 linhas

Ver seção 6 deste relatório — riscos B1-B5 (judge) + W4 + W11 + W15 + W16 + drift de docs do reconcile (status ABERTO + mitigação via epic 016).

### Seção Gantt (linhas 32-52)

```diff
    section Post-MVP
    009 Agent Tools         :a9, after a6, 2w
    010 Handoff Engine      :a10, after a6, 2w
    011 Trigger Engine      :a11, after a10, 1w
+   section Pipeline Sub-Routing
+   015 Agent Pipeline Steps (SHIPPED-BLOCKED) :active, a15, 2026-04-08, 3w
+   016 Pipeline Hardening :a16, after a15, 2w
+   017 Agent Versioning + Canary :a17, after a16, 3w
```

---

## 9. Auto-Review (Tier 1)

| # | Check | Status | Nota |
|---|-------|--------|------|
| 1 | Outputs em `roadmap-reassess-report.md` e não em `roadmap.md`? | ✅ | Correto — skill terminal do L2 produz relatório, não reescreve L1 diretamente |
| 2 | Epics existentes (001-008) preservados na renumeração? | ✅ | Renumeração só **adiciona** 015/016/017 sem deslocar slots existentes |
| 3 | Slot "022 Agent Pipeline Steps" placeholder removido com justificativa? | ✅ | Foi materializado em 015 — placeholder vira ruído (seção 3) |
| 4 | Novos epics 016 + 017 têm appetite + escopo definido? | ✅ | 016: 1-2 sem, B1-B5 + W priorizados (must) + W stretch; 017: 2-3 sem, materializa ADR-019 + canary |
| 5 | Dependências do novo DAG são acíclicas? | ✅ | 015 → 016 → 017 — linear e sem ciclos |
| 6 | Novos riscos mapeados para mitigação concreta? | ✅ | Seção 6 — 14 riscos com mitigation atribuída a 016 ou 017 |
| 7 | "Não Este Ciclo" com ≥3 itens + trigger? | ✅ | Seção 7 — 12 itens com trigger quantificado/qualitativo |
| 8 | Referência cruzada a decisions.md do epic (D-PLAN-02)? | ✅ | Seção 1, 4, 6, 7 citam D-PLAN-02 e propõem promotion via `/madruga:adr` |
| 9 | Outcomes refletem o que mudou (não só repete L1)? | ✅ | Seção 5 — baseline/target atualizados com 015 entregue + `[VALIDAR]` em 5/8 pendentes de adoção real |
| 10 | Patches ao roadmap.md concretos (diff-ready)? | ✅ | Seção 8 — 6 blocos `diff` aplicáveis pelo `reverse-reconcile` ou manualmente |
| 11 | Open Items herdados (judge + reconcile) rastreados? | ✅ | Seção 11 — 17 OIs (OI-1..OI-17) com origem + destino |
| 12 | Cut-line do epic 015 documentado (não acionado)? | ✅ | Seção 2 — cut-line foi NOT acionado por momentum positivo |

---

## 10. Tier 2 Scorecard

| Dimensão | Score | Justificativa |
|----------|-------|---------------|
| Alinhamento com learnings do epic | 95% | Renumeração + 016 hardening + 017 versioning refletem exatamente o que judge/reconcile apontaram. D-PLAN-02 promovido para epic próprio com escopo bem delimitado. |
| Qualidade das alternativas (≥2 por decisão) | 90% | Seção 4 apresenta 3 opções (A/B/C) com rationale + kill criteria explícitos para 016. Trade-offs em Não Este Ciclo. |
| Kill criteria explícitos | 95% | Epic 016 tem 3 kill criteria concretos; outcomes têm `[VALIDAR]` onde falta adoção real; report tem kill criteria próprio (final). |
| Rastreabilidade (refs a ADR/decisions/judge/reconcile) | 95% | Cada mudança referencia ADR-006, ADR-019, ADR-027, ADR-028, ADR-029, decisões D-PLAN-01..12, findings B1-B5/W1-W16, OI-1..OI-17. |
| Exclusões conscientes (Não Este Ciclo) | 90% | 12 itens com trigger quantificado; inclui OR/parens, retry, MAX configurável, granularidade per-step. |
| Confiança | 85% | Alta com ressalva — 5 BLOCKERs não validados em produção; SC-010 medido em sintético. Documentado claramente no Confidence (final). |
| **Score geral** | **92%** | Acima do threshold 80% — pronto para aplicar |

---

## 11. Próximos Passos Operacionais

1. **Aplicar 6 doc-diffs do reconcile-report** (OI-1..OI-6) — ADR-006 amend, ADR-019 amend, domain-model.md, blueprint.md, tech-alternatives.md, roadmap.md (P1) — ~30 min
2. **Aplicar mudanças propostas neste relatório no `planning/roadmap.md`** (seção 8) — adicionar slots 015/016/017 + remover placeholder 022 — ~10 min
3. **Promover D-PLAN-02 para ADR** via `/madruga:adr prosauai` — versioning bypass + rollback strategy (1-way-door + multi-epic implication) — ~20 min
4. **Criar `/madruga:epic-context prosauai 016-pipeline-hardening`** com escopo da seção 4 (Opção A) deste relatório — escopo já está pre-organizado por BLOCKER + WARN
5. **No repo externo `paceautomations/prosauai`**: abrir 5 issues para B1-B5 + 8 issues para W1/W2/W4/W11/W13/W14/W15/W16 vinculados ao novo epic 016
6. **Antes de qualquer adoção em produção**: documentar runbook "Configurar pipeline via SQL" baseado em `quickstart.md` § "Validar US1" (T030/T046/T085 já validaram localmente) — destino: `apps/api/docs/pipeline-steps-runbook.md` (T123 já criou)
7. **Após primeiro tenant adotar pipeline**: executar OI-16 (re-run benchmark T051 em CI on merge) + monitorar 7d `trace_steps_substeps_bytes_p95` em staging
8. **Após 016 fechar com smoke validado**: avaliar abertura de 017 vs prioridade do produto entre 010-handoff-engine, 011-evals, 009-agent-tools (epic-dirs já existem, status no roadmap precisa reassess separada)
9. **Fechar este ciclo L2** com `post_save.py --node roadmap --skill madruga:roadmap --artifact roadmap-reassess-report.md`

---

## 12. Open Items Herdados (Judge + Reconcile + QA — não acionáveis neste relatório)

Registrados para rastreabilidade:

| Origem | ID | Descrição | Destino |
|--------|----|----|---------|
| Judge | B1 | `_PIPELINE_EXEC_METADATA` cross-tenant attach via `id()` reuse | Epic 016 must |
| Judge | B2 | Executor exception filter narrow (não pega `httpx.HTTPStatusError`, etc.) | Epic 016 must |
| Judge | B3 | Cost coercion divergent error paths em `pipeline_executor.py:418-419` vs `:439` | Epic 016 must |
| Judge | B4 | Audit-log rollback query sem expression index | Epic 016 must |
| Judge | B5 | Race em PUT replace sem `pg_advisory_xact_lock` | Epic 016 must |
| Judge | W1-W16 | 16 warnings (regex, RLS, dedup, cache, circuit breaker) | Epic 016 stretch (8 priorizados) + epic 017+ (8 restantes) |
| Judge | N1-N9 | 9 nits | Epic 017+ |
| Reconcile | OI-1 | ADR-006 amend (D5.1) | aplicar agora |
| Reconcile | OI-2 | ADR-019 amend (D5.2) — status note + follow-up 017 | aplicar agora |
| Reconcile | OI-3 | domain-model.md updates (D4.1) | aplicar agora |
| Reconcile | OI-4 | blueprint.md NFR table update (D2.1) | aplicar agora |
| Reconcile | OI-5 | tech-alternatives.md enrichment (D11.1) | aplicar agora |
| Reconcile | OI-6 | roadmap.md update | aplicar agora (consolidado neste relatório seção 8) |
| Reconcile | OI-7..OI-12 | Hardening PR for 5 BLOCKERs + 8 WARN | Epic 016 |
| Reconcile | OI-13 | Fix L1 ruff findings (9 items) | Epic 016 hygiene |
| Reconcile | OI-14 | Open epic 015b (renomeado 017) — agent-versioning + canary | Epic 017 (proposed) |
| Reconcile | OI-15 | Promote D-PLAN-02 via `/madruga:adr` | passo 3 deste relatório |
| Reconcile | OI-16 | Re-run benchmark T051 em CI on merge | Epic 016 — verify SC-010 sustentado |
| Reconcile | OI-17 | Quarantine flaky `test_emits_processor_document_extract_span` | Epic 016 hygiene |
| QA | 1 flaky test | Pre-existente, suite 2534/2535 | OI-17 |
| QA | Phase 11 smoke | T130-T135 verde, exceto T135 sub_steps validation deferred | Epic 016 — validar com primeiro tenant em adoção |

---

## 13. Confiança + Kill Criteria

**Confiança:** Alta com ressalva. A reassess está bem fundamentada (judge findings + reconcile drift + plan/spec/tasks completos), mas 5 BLOCKERs **não foram fix-and-validados** em produção (sandbox bloqueou edits no repo externo) e SC-010 (overhead ≤5 ms p95) foi medido apenas em benchmark sintético. A confidence cai para Média se nos próximos 7 dias de staging os números reais divergirem da estimativa (~1.8 GB cumulativos `sub_steps`, p95 lookup ≤5 ms).

**Kill criteria — este relatório fica inválido se:**
- (a) Epic 016 for abandonado e os 5 BLOCKERs ficarem em produção sem mitigation — força repor a feature em "roadmap em débito" e considerar rollback do 015 (DELETE FROM agent_pipeline_steps) até hardening.
- (b) `agent_config_versions` shippar via outro caminho (ex: epic 017 absorvido por outra equipe ou produto pivoteia) — D5.2 amend de ADR-019 vira SUPERSEDE; epic 017 some do roadmap; Phase 9 deferred do 015 precisa ser re-scoped.
- (c) Telemetria de produção pós-adoção em ≥1 tenant mostrar overhead executor >5 ms p95 sustentado por 7d — D-PLAN-05 (no Redis cache) invalidado; epic 016 ou novo epic 016b precisa cachear lookup.
- (d) Storage `trace_steps.sub_steps` exceder 3× a estimativa (>5.4 GB cumulativos em 30d com pipeline em 1 tenant) — força repensar D-PLAN-01 (cap 32 KB → 16 KB ou tabela separada); epic 016 ou novo epic precisa abordar.
- (e) Produto decidir pivotear para "ferramenta declarativa low-code agent designer" em vez de pipeline imperativo — invalida toda a arquitetura do 015; epics 016/017 ficam órfãos; nova reassess obrigatória.
- (f) `agent_pipeline_steps.config` JSONB cap 16 KB se mostrar muito apertado em uso real (operador embutindo prompt grande no config) — força refator para `prompt_slug` mandatory ou cap maior; epic 016 ou epic dedicado.

---

```yaml
---
handoff:
  from: madruga:roadmap
  to: madruga:epic-context
  context: "Roadmap reassess pos-epic 015 concluido em modo dispatch autonomo. Veredito: APPLY_PATCHES_AND_REPRIORITIZE. Proximo epic recomendado: 016-pipeline-hardening (1-2 sem) cobrindo 5 BLOCKERs + 8 WARN priorizados do judge-report + 6 doc-diffs do reconcile-report. Apos 016 fechar, abrir 017-agent-versioning-canary (2-3 sem) que materializa ADR-019 e habilita Phase 9 deferred do 015 (US4 group-by-version). Renumeracao: 015 promovido de 'Epics Futuros' (slot 022) para tabela principal com status shipped-pendente-blockers; 016 e 017 inseridos como propostos. Slots 009-014 e 018-024 nao mudam (nota: epic-dirs 009-channel-ingestion, 010-handoff-engine-inbox, 011-evals, 012-tenant-knowledge-base-rag ja existem mas tem mismatch com roadmap atual — fora-do-escopo desta reassess, exige reassess proprio). Pre-requisito antes de iniciar 016: aplicar OI-1..OI-6 do reconcile-report.md (ADR-006/019 amends + domain-model + blueprint + tech-alternatives + roadmap). 17 Open Items rastreados. 5 BLOCKERs nao foram fix-and-validados (sandbox bloqueou edits no repo externo). SC-010 medido em sintetico — validacao em staging fica como OI-16. Phase 8b (mark commits reconciled) skipped per Invariants (epic branch ainda nao em origin/develop)."
  blockers:
    - "planning/roadmap.md ainda nao reflete mudancas — pendente aplicar P1 do reconcile-report + secao 8 deste relatorio"
    - "B1-B5 do judge-report.md abertos no repo externo paceautomations/prosauai — bloqueiam adocao do pipeline em producao"
    - "ADR-006 e ADR-019 amends pendentes (OI-1, OI-2)"
    - "D-PLAN-02 nao promovido para ADR ainda (OI-15) — bloqueia abertura limpa do 017"
  confidence: Alta
  kill_criteria: "Este relatorio fica invalido se: (a) epic 016 for abandonado e os 5 BLOCKERs ficarem em producao sem mitigation; (b) agent_config_versions shippar por outro caminho — D5.2 vira SUPERSEDE e 017 some; (c) telemetria de producao mostrar executor overhead >5 ms p95 sustained por 7d — D-PLAN-05 (no cache) invalidado; (d) trace_steps.sub_steps storage exceder 3x a estimativa (>5.4 GB/30d em 1 tenant) — D-PLAN-01 (cap 32 KB) precisa ser revisitado; (e) produto pivotear para 'low-code agent designer' invalidando arquitetura 015; (f) agent_pipeline_steps.config 16 KB cap se mostrar apertado em uso real — refator mandatory para prompt_slug."
```
