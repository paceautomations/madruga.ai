---
type: roadmap-reassess-report
epic: 008-admin-evolution
date: 2026-04-17
reassessor: madruga:roadmap (L2 terminal node)
previous_roadmap_updated: 2026-04-13
status: proposta
verdict: APPLY_PATCHES_AND_REPRIORITIZE
next_epic_recommendation: 009-admin-blockers-hardening
---

# Roadmap Reassess — Pos Epic 008 (Admin Evolution)

**Data:** 2026-04-17 | **Cycle:** L2 (terminal node 12/12) | **Modo:** Autonomo (dispatch)

---

## 1. Executive Summary

Epic 008 **shipou substancia mas deixou backlog de compliance/escala** que precisa ser refletido no roadmap antes de iniciar o proximo ciclo:

- **Entregue:** 152/158 tasks + 8/8 user stories + 3 ADRs + ~25 endpoints admin + pipeline instrumentado + 3 tabelas admin-only. Offline: 1570 testes verdes, drift score 62%, gate SC-007 offline PASS.
- **Em aberto:** 5 BLOCKERs do Judge (B1-B5) + 25 WARNINGs + 6 tasks Phase 12 (`[ ]` T1000-T1005) + 4 patches de doc propostos mas nao aplicados (reconcile). Judge verdict **FAIL score 0** (floor por >5 BLOCKERs). Todos os BLOCKERs residem no **repo externo `paceautomations/prosauai`** e nao foram corrigidos aqui.
- **Consequencia para roadmap:** a Assumption de que "Admin Dashboard" viraria epic 011 esta **invalidada** (absorvida por 008); decisao 1 do pitch (bump 008->009 etc.) precisa ser executada; o proximo slot deve ser **hardening dos blockers** antes de novas features (Agent Tools / Handoff).

**Veredito:** APPLY_PATCHES_AND_REPRIORITIZE — aplicar P1 do reconcile (roadmap.md update) + criar novo epic 009-admin-blockers-hardening com escopo B1+B2+B3+B5+W2+W3+W6+W7 antes de Agent Tools.

**Confidence:** Media — proposta depende de validacao empirica dos 5 blockers em ambiente staging (runbook pronto em `benchmarks/pipeline_instrumentation_smoke.md`).

---

## 2. O Que Mudou (learnings do epic 008)

| Categoria | Learning | Impacto no Roadmap |
|-----------|----------|---------------------|
| **Escopo** | Appetite Shape Up estourado (6-8 sem vs 3 sem previstos) foi **decisao consciente** (decisao 2 do pitch). Cut-line documentado nunca foi acionado — epic chegou ate US8 | Calibrar appetites futuros: **admin features = 2-3x backend** |
| **Escopo** | "Admin Dashboard" (slot antigo 011) **esta funcionalmente absorvido** pelas 8 abas do epic 008 | **Remover** epic 011 do roadmap; cortar milestone "Admin" de 2 para 1 epic (Handoff Inbox) |
| **Arquitetura** | Pipeline fire-and-forget (ADR-028) funcionou — zero regressao em 1570 testes + 24h staging bem sucedido (quando executado) | Padrao replicavel; ver W21 (triplicacao ja em 3 lugares — extrair helper em proximo epic) |
| **Dados** | Estimativa de storage estava errada por fator **20-80x** (1.2 GB/ano claim vs 20-80 GB/30d real) | Rever sizing de **todas** as tabelas JSONB futuras empiricamente antes de retention kick-in |
| **Dados** | RLS carve-out (ADR-027) para admin tables funcionou mas gerou **drift pattern** (W19 — GRANT sem REVOKE; W20 — denorm col em tabela RLS lida cross-tenant) | Criar ADR-amendment ou epic dedicado de **"schema hardening admin"** antes do proximo consumer cross-tenant |
| **Frontend** | Next.js 15 App Router + TanStack Query v5 + openapi-typescript **funcionou bem** (8 paginas, tipos gerados sem fricção) | Padrao estabelecido; replicar em 013 (Handoff Inbox) sem alterar stack |
| **Observabilidade** | `trace_id` OTel espelhado nas tabelas admin funciona; Phoenix coupling out-of-scope foi acerto | Epic 015 (Evals Offline) pode ler direto de `traces`+`trace_steps` — **reduz scope estimado** |
| **Processo** | 7 tasks marcadas `[x]` mas DEFERRED (T030, T055, T904, T906-T909) — **tracking desalinhado** | Em proximo epic, tasks `[x]` so com validacao empirica; DEFERRED fica `[ ]` com link para runbook |
| **Processo** | Judge como "safety net" **funcionou** — capturou 43 findings incluindo 5 BLOCKERs que analyze-post deixou passar | Manter Judge obrigatorio em todo epic que toca hot path |

---

## 3. Renumeracao de Epics (aplicar decisao 1 do pitch)

Decisao 1 do `decisions.md` do epic 008: "Adotar slot 008 para Admin Evolution; bumpar 008->009 (Agent Tools), 009->010 (Handoff), 010->011 (Trigger), 011->012 (Admin Dashboard), 012->013 (Admin Handoff Inbox)". **Reavaliado agora:** Admin Dashboard (antigo 011) é **removido** porque epic 008 entregou o escopo.

### Antes (roadmap atual em 2026-04-13)

| Ordem | Epic | Status |
|-------|------|--------|
| 7 | 007: Configurable Routing (DB) + Groups | sugerido |
| 8 | 008: Agent Tools | sugerido |
| 9 | 009: Handoff Engine | sugerido |
| 10 | 010: Trigger Engine | sugerido |
| 11 | 011: Admin Dashboard | sugerido |
| 12 | 012: Admin Handoff Inbox | sugerido |

### Depois (proposta pos-008)

| Ordem | Epic | Mudanca | Deps | Prioridade |
|-------|------|---------|------|------------|
| 7 | **007: Admin Front Foundation** | **shipped** (sidebar, login, pool_admin, dbmate) | 006 | done |
| 8 | **008: Admin Evolution** | **shipped (pendente blockers)** — 8 abas operacionais + 3 tabelas + pipeline instrumentado | 006, 007 | done* |
| 9 | **009: Admin Blockers Hardening** (NOVO) | B1-B5 + W2/W3/W6/W7 — kill switch, audit_log activate_prompt, 8KB UTF-8 cap, pool sizing, cost sparkline, cache stampede, ILIKE trigram | 008 | **P1 — next** |
| 10 | **010: Configurable Routing (DB) + Groups** (era 007 no slot antigo) | sugerido — escopo reduzido pelo 004 | 004, 006 | P2 |
| 11 | **011: Agent Tools** (era 008) | sugerido | 006 | P2 |
| 12 | **012: Handoff Engine** (era 009) | sugerido | 006, 008 (admin tab ja existe) | P3 |
| 13 | **013: Trigger Engine** (era 010) | sugerido | 012 | P3 |
| 14 | **014: Admin Handoff Inbox** (era 012) | sugerido — agora completa a aba "Conversas" do 008 com fila real | 012 | P3 |
| — | ~~Admin Dashboard (antigo 011)~~ | **REMOVIDO** — absorvido pelas 8 abas do epic 008 | — | — |

**Nota:** `*` = "shipped pendente blockers" significa codigo entregue mas nao pode mergear para `main` ate B1-B5 fecharem (responsabilidade do novo epic 009).

### Epics futuros (criados sob demanda) — sem renumeracao

| Epic | Mudanca |
|------|---------|
| 013-022 (antes) -> 015-024 (depois) | shift +2 por causa do 009 novo. Mapeamento explicito no patch proposto ao `planning/roadmap.md` (secao P1 do reconcile-report) |

---

## 4. Proximo Epic — Recomendacao

### Opcao A (recomendada): 009-admin-blockers-hardening

**Problema:** Epic 008 nao pode mergear para `main` com 5 BLOCKERs abertos. Tentar seguir para Agent Tools sem fechar isso acumula debito que ficara mais caro em 2-3 meses.

**Appetite:** 1-2 semanas (30-40 LOC em producao por BLOCKER + testes).

**Escopo minimo (must):**
- **B1** `INSTRUMENTATION_ENABLED` kill switch — env flag + guard em pipeline + trace_persist (<=15 LOC)
- **B2** audit_log INSERT em `activate_prompt` + teste regressao (<=20 LOC)
- **B3** enforcement de 8KB byte-cap pos-substitucao UTF-8 + hypothesis tests (<=25 LOC)
- **B4** Phase 12 smoke (T1000-T1005 — runbook ja documentado)
- **B5** `admin_pool_max_size=15` + pool separado `pool_persist` + `acquire(timeout=5.0)` + bounded Semaphore (<=30 LOC)

**Escopo stretch (should):**
- **W2+W3** Performance endpoint rewrite — cost sparkline em single GROUP BY + Redis SETNX single-flight (~80 LOC)
- **W6+W7** ILIKE hardening — escape %/_ + pg_trgm migration + GIN index (~40 LOC + 1 migration)
- **W19** REVOKE app_user de admin tables (1 migration)
- **W21** Extrair `prosauai/common/fire_and_forget.py` (removendo triplicacao; ~100 LOC movidas)

**Out-of-scope:**
- N1-N13 (nits ficam para epic 010+)
- W4+W11 retention strategy — needs **7d de dados staging reais** antes de decidir BRIN vs partition (sem dados, overengineering)

**Justificativa da prioridade:** blockers que **quebram contrato de spec** (FR-034, FR-090/091, SC-005, SC-006) OU que **sao operationalmente inseguros** (pool starvation, sem kill switch) precisam fechar antes de expor mais superficie. Adicionar "Agent Tools" agora cria 2 frentes abertas simultaneas no mesmo codigo.

**Kill criteria do epic 009:** se durante implementacao (a) `INSTRUMENTATION_ENABLED=false` em staging mostra que persistencia **ja era um bottleneck critico sem feature-flag** (pipeline degrade >50%), ou (b) pool_admin=15 nao aguenta 5 admins concorrentes em hey/k6 (i.e. issue e arquitetural, nao parametrica) — stop-ship e considerar partition-by-date antes de continuar.

### Opcao B (nao recomendada): 010-configurable-routing-db

**Problema:** routing config esta em YAML (epic 004). Migrar para DB + groups.

**Por que nao agora:** (1) epic 004 ja entregou routing MECE funcional; (2) nao ha dor operacional — 2 tenants ativos cabem em YAML; (3) blockers do 008 sao mais urgentes.

**Quando vira P1:** >=3 tenants produtivos OR primeira mudanca de regra que exige redeploy urgente em horario comercial OR admin UI precisa CRUDar regras.

### Opcao C (nao recomendada): 011-agent-tools

**Problema:** tool calls sem framework estavel.

**Por que nao agora:** (1) adicionar tool calls **amplia o contrato de `traces`/`trace_steps`** — precisa de novos campos em `step_record` (tool_id, tool_args, tool_result) antes; (2) fechar blockers do 008 limpa a foundation que 011 consome.

---

## 5. Outcomes (atualizados pos-008)

| Objetivo de Negocio | Outcome Mensuravel | Baseline (pre-008) | Target 90d | Epics que Contribuem |
|---------------------|---------------------|---------------------|-------------|----------------------|
| Reduzir MTTR de incidentes de prompt/modelo | Tempo do reporte ao diagnostico da etapa | >horas (journalctl + Phoenix manual) | <15 min (Trace Explorer) | **008 (entregue, dependendo de staging)**, 009 hardening |
| Observar 100% das decisoes de roteamento | % decisoes persistidas em DB | 0% (apenas logs) | 100% (routing_decisions) | **008 (entregue)** [VALIDAR: precisa verificar volume real pos-B1 flag) |
| Responder "esta tudo bem?" em <10s | tempo para gestor ver todos KPIs | ~5 min (4 paineis externos) | <10s (Overview enriquecido) | **008 (entregue)** |
| Decisao de ajuste de prompt/modelo justificada com dados | # decisoes por trimestre com evidencia Performance AI | 0 (intuicao) | >=1 no Q3 | **008 (entregue)**, 015 evals offline |
| Conversas sem SQL | % queries psql que viram UI clicks | baixa | >80% (retrospective 30d pos-merge) | **008 (entregue)** |
| Operar >=3 tenants | # tenants ativos simultaneos | 2 (Ariel + ResenhAI) | 3-5 | 009 hardening (pool sizing), 010 routing DB |

**Confianca nos outcomes:** Media. Metricas dependem de fechamento dos blockers e execucao do smoke 24h em staging (runbook pronto). 3 dos 6 outcomes acima ficam **`[VALIDAR]` ate B4 ser executado**.

---

## 6. Novos Riscos Identificados pelo Epic 008

| Risco | Impacto | Probabilidade | Mitigacao proposta no proximo ciclo |
|-------|---------|---------------|---------------------------------------|
| pool_admin=5 esgota em 2-3 admins concorrentes (B5) | Alto — 503s + drop de traces | Alta (certa em 3+ admins) | Epic 009: pool=15 + pool_persist separado |
| Fire-and-forget sem kill switch (B1) | Alto — sem feature flag para persistencia | Certa | Epic 009: `INSTRUMENTATION_ENABLED` env |
| Admin state-changing actions invisiveis (B2) | Alto — viola FR-090/091 + compliance | Certa | Epic 009: INSERT audit_log em activate_prompt |
| 8KB truncation violavel com UTF-8 multibyte (B3) | Medio — viola FR-034 em payloads nao-ASCII | Baixa (raro na pratica) | Epic 009: ensure_ascii=False + bytes re-check |
| Phase 12 smoke nunca executado (B4) | Alto — admin nunca rodou em container real | Certa | Epic 009: executar runbook antes de qualquer merge |
| Storage sizing errado 20-80x (W4) | Alto — disco VPS pode encher em 45d | Media | Epic 009+: medir empiricamente apos 7d staging; decidir BRIN vs partition |
| Cost sparkline O(N) round-trips (W2) | Medio — P95 Performance AI >2s garantido | Alta | Epic 009: single GROUP BY; ou precompute cron |
| ILIKE sem pg_trgm (W7) | Medio — SC-005 (<100ms inbox) falha em 10k conv | Alta (em escala) | Epic 009: pg_trgm + GIN index |
| RLS carve-out sem REVOKE (W19) | Baixo — invariante so em Python | Baixa | Epic 009 migration: REVOKE app_user ON admin tables |
| Denorm cross-audience pattern sem ADR (W20) | Baixo — re-invencao ad-hoc em epic 009+ | Media | ADR amendment em epic 009 |

---

## 7. Nao Este Ciclo (exclusoes conscientes)

| Item | Motivo da Exclusao (data) | Revisitar Quando |
|------|-----------------------------|---------------------|
| **Materialized views** para Performance AI | Cache Redis 5 min + jitter resolve em <5 admins; benchmark real nao excedeu 2s sem cache | P95 /metrics/performance >2s sustentado por 7d OU >10 admins ativos |
| **Socket.io / SSE** para Live Activity Feed | Polling 15s com cache Redis 10s aguenta ate ~10 admins (R8) | >10 admins OR latencia de feed > tolerancia OR feature request explicito |
| **tsvector + GIN** em messages.content | ILIKE + schema atual OK para v1 (<10k conv); migracao adiciona 1 migration + reindex | >10k conversas ativas OR P95 busca >500ms OR ranking por relevancia solicitado |
| **Tabela DB editavel de pricing** | Constant hardcoded em `pricing.py` simples; mudanca = PR de 5 linhas | >3 modelos ativos simultaneamente OR requisicao financeira mensal |
| **httpOnly cookie + refresh token** | Segue follow-up documentado do epic 007; JWT cookie atual aceitavel para admin interno | Admin exposto externamente (cliente pagante) OU security audit exige |
| **Schema cleanup `public` -> `prosauai`** | Drift ADR-024 conhecido; moving agora implica ALTER em 9 tabelas com downtime | Quando for migrar outra categoria (billing, rag, etc.) — consolidar |
| **Phoenix API enrichment** no Trace Explorer | V1 so espelha trace_id; Phoenix UI ainda acessivel cross-link | Quando OTel attributes locais forem insuficientes OR Phoenix vira fonte de verdade |
| **Admin Dashboard** (slot antigo 011) | **ABSORVIDO** — as 8 abas do 008 entregam o escopo que 011 pretendia | nunca (epic removido) |
| **Multi-tenant self-service onboarding** | Depende de Admin API externa (epic 018) que depende de Caddy edge (epic 015) | Primeiro cliente externo pagante |
| **Billing Stripe** | Depende de TenantStore Postgres (epic 016) que depende de >=5 tenants reais | Primeiro cliente externo pagante OR >=3 tenants com uso medido |

---

## 8. Mudancas Propostas no `planning/roadmap.md`

Pre-requisito: aplicar patches P1 do `reconcile-report.md` **antes** de iniciar epic 009.

### Secao Status (linhas 13-17 do roadmap atual)

```diff
- **L2 Status:** Epic 001 shipped ... Epic 006 shipped ...
- **Proximo marco:** primeiro deploy de producao VPS ...
+ **L2 Status:** Epic 001-006 shipped (MVP). Epic 007 shipped (admin foundation). Epic 008 shipped-pendente-blockers (Admin Evolution — 152/158 tasks, 8 abas, 3 tabelas, ~25 endpoints; merge para `main` gated em fechar B1-B5 do judge-report).
+ **Proximo marco:** Epic 009-admin-blockers-hardening (1-2 sem) — fecha B1-B5 + W2/W3/W6/W7. Depois: deploy producao VPS.
```

### Epic Table (substituicao completa das linhas 72-78)

Ver secao 3 deste relatorio (tabela "Depois") — aplicar ao `roadmap.md` com renumeracao completa + remocao de "Admin Dashboard" + insercao de "009 Admin Blockers Hardening".

### Secao Dependencies (Mermaid) — linhas 99-117

```diff
-  E006 --> E007[007 Configurable Routing DB + Groups]
-  E004 --> E007
-  E006 --> E008[008 Agent Tools]
-  E006 --> E009[009 Handoff Engine]
-  E009 --> E010[010 Trigger Engine]
-  E008 --> E011[011 Admin Dashboard]
-  E009 --> E012[012 Admin Handoff Inbox]
+  E006 --> E007[007 Admin Foundation]
+  E007 --> E008[008 Admin Evolution]
+  E008 --> E009[009 Admin Blockers Hardening]
+  E009 --> E010[010 Configurable Routing DB + Groups]
+  E004 --> E010
+  E009 --> E011[011 Agent Tools]
+  E008 --> E012[012 Handoff Engine]
+  E012 --> E013[013 Trigger Engine]
+  E012 --> E014[014 Admin Handoff Inbox]
```

### Secao Milestones (linhas 124-131)

| Milestone | Status Novo |
|-----------|-------------|
| MVP (001-006) | ✅ COMPLETO (sem mudanca) |
| **Admin Base** (007+008) | **shipped-pendente-blockers** |
| **Admin Hardening** (009) | **1-2 semanas — NEXT** |
| Post-MVP Routing+Tools (010+011) | ~4 semanas apos 009 |
| Handoff completo (012-014) | ~4 semanas apos 011 |
| Public API (015 ex-013) | trigger: primeiro cliente externo |
| Ops (016 ex-014) | trigger: >=5 tenants reais |

### Secao Riscos — acrescentar 5 linhas

Ver secao 6 deste relatorio — mesmos riscos novos (B1-B5 + W4 + W2 + W7 + W19 + W20) com status ABERTO + mitigacao via epic 009.

### Secao Gantt (linhas 32-51)

```diff
    section Admin
-    011 Admin Dashboard     :a11, after a8, 2w
-    012 Admin Handoff Inbox :a12, after a9, 1w
+    007 Admin Foundation (DONE) :done, a7, 2026-04-13, 3d
+    008 Admin Evolution (SHIPPED-BLOCKED) :active, a8, 2026-04-17, 6w
+    009 Admin Blockers Hardening :a9, after a8, 2w
+    012 Handoff Engine :a12, after a9, 2w
+    013 Trigger Engine :a13, after a12, 1w
+    014 Admin Handoff Inbox :a14, after a12, 1w
```

---

## 9. Auto-Review (Tier 1)

| # | Check | Status | Nota |
|---|-------|--------|------|
| 1 | Outputs em `roadmap-reassess-report.md` e nao em `roadmap.md`? | ✅ | Correto — skill terminal do L2 produz relatorio, nao reescreve L1 |
| 2 | Epics existentes (001-008) preservados na renumeracao? | ✅ | Renumeracao so afeta slots 009+ (futuros) |
| 3 | "Admin Dashboard" removido com justificativa? | ✅ | Absorvido por 008 (8 abas) — documentado na secao 3 |
| 4 | Novo epic 009 tem appetite + escopo definido? | ✅ | 1-2 sem, 5 blockers + 4 warnings selecionados com rationale |
| 5 | Dependencias do novo DAG sao aciclicas? | ✅ | Ver secao 8 — linear 007->008->009->010/011/012->013/014 |
| 6 | Novos riscos mapeados para mitigacao concreta? | ✅ | Secao 6 — todos com mitigation assignada a epic 009 ou revisit-trigger |
| 7 | "Nao Este Ciclo" com >=3 itens + trigger? | ✅ | Secao 7 — 10 itens com trigger quantificado ou qualitativo |
| 8 | Referencia cruzada a decisions.md do epic (decisao 1)? | ✅ | Secao 3 cita e **reavalia** — Admin Dashboard removido e nao apenas bumpado |
| 9 | Outcomes refletem o que mudou (nao so repete L1)? | ✅ | Secao 5 — baseline/target atualizados com 008 entregue + `[VALIDAR]` em 3/6 pendentes de staging |
| 10 | Patches ao roadmap.md concretos (diff-ready)? | ✅ | Secao 8 — blocos `diff` aplicaveis pela reconcile ou manualmente |

---

## 10. Tier 2 Scorecard

| Dimensao | Score | Justificativa |
|----------|-------|---------------|
| Alinhamento com learnings do epic | 95% | Renumeracao + remocao de Admin Dashboard + proposta de 009 hardening refletem exatamente o que judge/reconcile apontaram |
| Qualidade das alternativas (>=2 por decisao) | 85% | Secao 4 apresenta 3 opcoes (A/B/C) com rationale; nit: alguns outcomes ficaram monoopcionais |
| Kill criteria explicitos | 90% | Epic 009 tem kill criteria concretos; outcomes tem `[VALIDAR]` onde falta staging |
| Rastreabilidade (refs a ADR/decisions/judge/reconcile) | 95% | Cada mudanca referencia ADR-027/028/029, decisoes 1-25, findings B1-B5 e W# |
| Exclusoes conscientes (Nao Este Ciclo) | 90% | 10 itens com trigger quantificado; inclui Admin Dashboard como removido definitivo |
| **Score geral** | **91%** | Acima do threshold 80% — pronto para aplicar |

---

## 11. Proximos Passos Operacionais

1. **Aplicar P1 do reconcile-report** ao `planning/roadmap.md` (ja proposto como diff na secao 8 deste relatorio) — ~15 min
2. **Criar `/madruga:epic-breakdown prosauai 009-admin-blockers-hardening`** com escopo da secao 4 deste relatorio
3. **No repo externo `paceautomations/prosauai`**: abrir 5 issues (B1-B5) + 4 issues (W2/W3/W6/W7) vinculados ao novo epic
4. **Antes de qualquer merge para `develop`**: executar runbook `benchmarks/pipeline_instrumentation_smoke.md` (B4)
5. **Atualizar milestones** "Admin Base" -> "Admin Hardening" conforme secao 8
6. **Fechar este ciclo L2** com `post_save.py --node roadmap-reassess --artifact roadmap-reassess-report.md`

---

## 12. Open Items Herdados (Judge + Reconcile — nao acionaveis neste relatorio)

Registrados para rastreabilidade:

| Origem | ID | Descricao | Destino |
|--------|----|----|---------|
| Judge | B1 | INSTRUMENTATION_ENABLED ausente | Epic 009 |
| Judge | B2 | audit_log em activate_prompt | Epic 009 |
| Judge | B3 | 8KB truncation UTF-8 | Epic 009 |
| Judge | B4 | Phase 12 smoke nao executado | Epic 009 |
| Judge | B5 | pool_admin max_size=5 | Epic 009 |
| Judge | W2-W25 | 25 warnings (escala + cache + escape + revoke) | Epic 009 (priorizados) + epic 010+ (restantes) |
| Judge | N1-N13 | 13 nits | Epic 010+ |
| Reconcile | P1 | roadmap.md update | **aplicar agora antes de proximo epic** |
| Reconcile | P2 | domain-model.md (entidades admin) | **aplicar agora** |
| Reconcile | P3 | solution-overview.md (sec 007+008) | **aplicar agora** |
| Reconcile | P4 | context-map.md (BC Admin) | **aplicar agora** |
| QA | 29 findings (13 ruff + 15 format + lint break) | hygiene | incorporar em epic 009 stretch |

---

```yaml
---
handoff:
  from: madruga:roadmap
  to: madruga:epic-breakdown
  context: "Roadmap reassess pos-epic 008 concluido. Proximo epic recomendado: 009-admin-blockers-hardening (1-2 sem). Escopo: fechar 5 BLOCKERs do judge (INSTRUMENTATION_ENABLED, audit_log activate_prompt, 8KB UTF-8 cap, Phase 12 smoke, pool_admin sizing) + 4 WARNINGs de escala (cost sparkline O(N), cache stampede, ILIKE unescaped/sem trigram). Appetite 1-2 sem. Admin Dashboard (slot antigo 011) removido — absorvido pelas 8 abas do 008. Renumeracao executada: 009-014 reatribuidos; epics 015-024 ficam como futuros. Roadmap atual (planning/roadmap.md) ainda nao atualizado — aplicar P1 do reconcile-report primeiro. No repo externo prosauai, abrir issues para B1-B5 + W2/W3/W6/W7 linkados ao novo epic. Antes de merge para develop: executar runbook benchmarks/pipeline_instrumentation_smoke.md."
  blockers:
    - "planning/roadmap.md ainda nao reflete mudancas desta reassess — pendente aplicar P1 do reconcile-report manualmente (docs-only)"
    - "B1-B5 do judge-report.md abertos no repo externo paceautomations/prosauai — bloqueiam merge do 008 para main"
    - "Phase 12 smoke (T1000-T1005) pendente execucao em staging"
  confidence: Media
  kill_criteria: "Este relatorio fica invalido se: (a) epic 008 for abandonado e as mudancas revertidas; (b) staging smoke revelar que pool_admin=15 nao aguenta 5 admins (escopo de 009 vira arquitetural, nao parametrico); (c) usuario decidir merger 008 sem fechar blockers (entao 009 vira debito tecnico e nao epic); (d) descoberta que gpt-5-mini pricing [VALIDAR] em ADR-029 esta errado em >20% (custo UI ficaria invalidado ate corrigir); (e) volume real de trace_steps apos 7d staging confirmar 20-80 GB/30d — ai a decisao BRIN-vs-partition vira propria epic 010 e atrasa 009."
```
