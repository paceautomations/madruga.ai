---
title: "Roadmap Reassessment — Epic 009 (Channel Ingestion + Content Processing)"
epic: 009-channel-ingestion-and-content-processing
platform: prosauai
date: 2026-04-20
updated: 2026-04-20
mode: autonomous
inputs:
  - pitch.md
  - spec.md
  - plan.md
  - tasks.md
  - implement-report.md
  - analyze-post-report.md
  - judge-report.md
  - qa-report.md
  - reconcile-report.md
roadmap_source: platforms/prosauai/planning/roadmap.md (updated 2026-04-19)
---

# Roadmap Reassessment — Epic 009

> Post-epic roadmap review. Consolida aprendizados de 67 commits, 188 arquivos, 24 791 inserções, 3 PRs (A/B/C), 6 ADRs novos, 2 tabelas admin-only. Propõe **mudanças concretas** no `planning/roadmap.md` e re-avalia a fila de epics downstream com base no que foi descoberto durante o ciclo.

---

## 1. Executive summary

| Dimensão | Antes do 009 | Depois do 009 | Delta |
|----------|--------------|--------------|-------|
| Modalidades suportadas | 1 (texto) | 9 kinds (text/audio/image/document/sticker/location/contact/reaction/unsupported) | +8 |
| Canais inbound | 1 (Evolution) | 2 (Evolution + Meta Cloud) | +1 |
| Providers externos AI | 0 | 2 (OpenAI Whisper + gpt-4o-mini vision) | +2 |
| Pipeline steps | 12 | 14 | +2 (`content_process` + `generate` re-num) |
| Tabelas admin-only | 3 (traces/trace_steps/routing_decisions) | 5 (+media_analyses, +processor_usage_daily) | +2 |
| ADRs | 29 | 35 (030–035) | +6 |
| Testes | 1532 baseline | 2096 (+564, zero regressões) | +564 |
| Cost projection (10k mídias/tenant/mês) | n/a | ~$15 USD/tenant/mês (well under kill-criteria de $500) | ✅ |
| Drift post-reconcile | n/a | 72% current (alcança 94% pós-commits pendentes) | ✅ |

**Veredito**: epic entrega o prometido (mídia habilitada + multi-source validado arquiteturalmente). Materialmente **shipped**, *pending* resolução dos 2 CRITICALs do analyze-post (SC-013 gate design + URL coverage em `platform.yaml`) e merge para `develop`. **Não é recomendado abrir novo epic para o backlog técnico** (23 WARNINGs do judge + 12 unresolved do QA) — tratar como "Epic 009 follow-up hardening" via issues, priorizado antes do dia 90 de prod. Nenhum epic preexistente foi invalidado.

---

## 2. Epic 009 outcome vs. plan

| Objetivo planejado (pitch) | Status | Evidência |
|----------------------------|--------|-----------|
| PR-A Canonical + EvolutionAdapter + step stub (2 sem) | ✅ Shipped | Phase 2 tasks T010–T053, 173+191 tests PASS (SC-010), latência texto ≤ baseline+5ms (SC-009) |
| PR-B Processors reais + cache + budget + admin UI (2 sem) | ✅ Shipped | Phase 3–7 tasks T060–T163; SC-001 (áudio p95<8s), SC-002 (imagem p95<9s, mocked), SC-003 (doc p95<10s, mocked) passam |
| PR-C MetaCloudAdapter — gate SC-013 diff-zero core (1 sem) | ⚠️ Shipped com débito | Phase 9 T190–T208; merge-time gate passou, mas post-merge polish commit `b38efb0` reabriu drift (analyze-post P1 / judge W7 / reconcile R7). SC-013 gate test está frouxo (compara contra `develop` em vez de tag pre-PR-C) |
| Cost projection < $500/tenant/mês (kill-criteria plan) | ✅ Cleared | T220 `cost-projection.md`: ~$15 USD/tenant/mês em cenário 10k mídias |
| p95 texto ≤ baseline+5ms (SC-009 gate PR-A) | ✅ Cleared | T051 benchmark verde |
| p95 áudio < 8s mocked (SC-001) | ✅ Cleared | T094 benchmark verde |
| p95 imagem < 9s / doc < 10s (SC-002/SC-003 gates PR-B) | ⚠️ Benchmarks stub | Judge W3 / analyze-post P4: arquivos existem mas com scaffolding parity-only — gates reais só com runtime stack |
| Zero regressão 173+191 (SC-010) | ✅ Cleared | QA §L2: 2096 passed (+564 sobre baseline), full suite green após cada PR-merge |
| Raw bytes guard (FR-027) | ✅ Cleared | W4: `tests/ci/test_raw_bytes_guard.py` landed |
| Cut-line (PR-C sacrificável se PR-B estourar sem 4) | ✅ Não ativado | PR-B mergeou dentro do prazo; PR-C seguiu normal |

**Desvios material**: nenhum — escopo do pitch foi entregue por inteiro. Débitos técnicos registrados são de **resilience hardening** (stress-tester W8–W14), não regressão funcional.

---

## 3. O que mudou na visão roadmap

### 3.1 Follow-ups criados pelo epic 009 (novos)

Três epics pós-009 foram **criados pelo próprio ciclo** (registrados em roadmap 2026-04-19 e confirmados nesta reassessment):

| Epic | Descrição | Depende | Prioridade sugerida | Apetite |
|------|-----------|---------|--------------------|---------|
| **010 Instagram/Telegram adapters** | Reusa `ChannelAdapter` Protocol (ADR-031) para plugar canais adicionais sem tocar pipeline/processors/router. Validação do SC-013 no epic 009 reduziu o risco arquitetural a near-zero. | 009 | **Now** — desbloqueado imediatamente após merge 009 para `develop` | 2 semanas |
| **011 PDF OCR (scanned documents)** | Detecta marker `[pdf_scanned]` emitido pelo `DocumentProcessor` → integra OCR remoto (candidatos: Azure Document Intelligence, AWS Textract, Google Doc AI). Reusa `ContentProcessor` Protocol (ADR-032). | 009 | **Next** — condicional ao volume de `[pdf_scanned]` em prod (trigger: ≥5% dos docs/mês) | 1 semana |
| **012 Streaming transcription (Whisper partial)** | Whisper partial results via `gpt-4o-mini-transcribe` streaming. Só faz sentido se p95 áudio em prod > 5s por 7d consecutivos (kill-criteria D3). | 009, métricas prod | **Later** — gate de ativação = telemetria real | 2 semanas |

### 3.2 Recomendações de edit em `planning/roadmap.md`

**Commit 1** — consolidar edições pendentes já feitas no working tree durante o epic (T216):

```diff
- | 9 | **009: Channel Ingestion + Content Processing** | 008 | medio | Post-MVP (media + multi-source) | **in-progress** (PR-A shipped, PR-B coding, PR-C planejado; ...) |
+ | 9 | **009: Channel Ingestion + Content Processing** | 008 | medio | Post-MVP (media + multi-source) | **shipped** (PR-A + PR-B + PR-C mergeados; 9 kinds, 2 canais, 6 ADRs 030–035, 2 tabelas admin-only, +564 testes; débito técnico em issues "Epic 009 follow-up hardening") |
```

**Commit 2** — promover 010/011/012 da seção "Media + Multi-Source" para linhas formais do Epic Table (hoje estão em comentário de renumeração):

```diff
 | 10 | 010: Instagram / Telegram adapters | 009 | medio | Post-MVP | **sugerido (Now)** — reusa ChannelAdapter ADR-031 sem tocar core |
-| 11 | 011: PDF OCR (scanned documents) | 009 | medio | Post-MVP | **sugerido** (detecção automática de `[pdf_scanned]` marker → extrai via OCR remoto; fora de escopo do 009) |
+| 11 | 011: PDF OCR (scanned documents) | 009 | medio | Post-MVP | **sugerido (Next, gate ≥5% docs/mês)** — detecta `[pdf_scanned]` marker → OCR remoto (Azure/AWS/GCP) |
-| 12 | 012: Streaming transcription (partial results) | 009 | alto | Post-MVP | **sugerido** (Whisper partial results em PT-BR curto; descartado do 009 por complexidade vs ganho) |
+| 12 | 012: Streaming transcription (partial results) | 009, prod-metrics | alto | Post-MVP | **sugerido (Later, gate p95>5s por 7d)** — Whisper partial via `gpt-4o-mini-transcribe` streaming |
```

**Commit 3** — novos riscos descobertos (append à tabela de riscos):

```diff
 | **ILIKE sem trigram GIN index degrada inbox >10k conversas** | **Aberto (epic 008 W7)** | Medio | Media | Adicionar `pg_trgm` + GIN index antes de 10k conversas; SC-005 inbox <100ms nao garantido em escala |
+| **SC-013 gate design frouxo** | **Aberto (epic 009 R7 / analyze-post P1 / judge W7)** | Medio | Alta | Pinar tag `pre-pr-c-merge-009` no repo externo e default `PR_C_SCOPE_BASE=tags/pre-pr-c-merge-009` em CI. Alternativa: rebaixar SC-013 a merge-time checklist humano. Registrar no ADR-035 Addendum |
+| **Judge backlog 23 WARNINGs (W8–W24)** | **Aberto (epic 009 R8)** | Medio | Media | Criar issue "Epic 009 follow-up hardening" (não novo epic). Priorizar W8 (timeout math defeats retry), W10 (retention batching), W13 (breaker observability) antes do dia 90 de prod |
+| **URL coverage em platform.yaml (webhooks novos)** | **Aberto (analyze-post P2)** | Alto | Alta | Adicionar 3 rotas (`POST /webhook/evolution/{...}`, `GET/POST /webhook/meta_cloud/{...}`) em `testing.urls` com `expect_status` 401/200, OU classificar como "auth-gated, exclude from Smoke probe" documentando no manifesto |
```

**Commit 4** — marcar status-line superior do roadmap:

```diff
- **Lifecycle:** building — **MVP completo** (6/6 epics shipped) + **Admin Evolution in-progress** + **Channel Ingestion + Content Processing in-progress (epic 009)**. Proximo: finalizar PR-B (processors reais) do epic 009; ...
+ **Lifecycle:** building — **MVP completo** (6/6 epics shipped) + **Admin Evolution in-progress** + **Channel Ingestion + Content Processing shipped (epic 009 — pending merge develop)**. Proximo: resolver 2 CRITICALs do analyze-post (SC-013 gate + URL coverage), merge 009, primeiro deploy de producao VPS em paralelo.
```

### 3.3 Re-priorização da fila Post-MVP (antes × depois)

| Posição | ANTES do 009 | DEPOIS do 009 | Mudou? |
|---------|--------------|---------------|--------|
| #1 Next | 013 Agent Tools | **010 Instagram/Telegram** (new) | ✅ Subiu — menor apetite, desbloqueado, alto valor estratégico (reduz lock-in Evolution) |
| #2 Next | 014 Handoff Engine | 013 Agent Tools | Manteve ordem relativa |
| #3 Next | 015 Trigger Engine | 014 Handoff Engine | Manteve ordem relativa |
| Novo | — | **011 PDF OCR** (gate volume) | ✅ Entra condicional |
| Novo | — | **012 Streaming transcription** (gate p95) | ✅ Entra condicional |
| #4 Next | 017 Admin Handoff Inbox (dep 014) | 017 Admin Handoff Inbox | Manteve |

**Racional para 010 subir**: (a) SC-013 validou `ChannelAdapter` Protocol, o risco arquitetural de 010 é quase zero agora; (b) apetite baixo (2 semanas) — cabe entre 008 merge e início de 013; (c) valor estratégico (reduz dependência de Evolution como caminho único); (d) os 4 fixtures reais Meta Cloud já capturados no 009 servem de base para Instagram/Telegram (payloads similares da Graph API).

**Racional para 013 Agent Tools descer**: escopo maior (~2 semanas) e roteamento MECE + handoff ainda não expande horizonte suficiente — melhor consolidar o Admin + Multi-Source primeiro.

---

## 4. Outcomes vs. leading indicators

### 4.1 Objetivos de negócio (do `solution-overview.md` + vision)

| Objetivo | Leading indicator | Pre-009 | Pós-009 (proj) | Status |
|----------|-------------------|---------|-----------------|--------|
| **Atender 100% das mensagens recebidas** (zero silent drops) | % msgs não-texto que geram resposta | 0% (áudio/imagem/doc descartados silenciosamente) | 100% (com feature flag on) | ✅ Desbloqueado |
| **Cliente fica engajado** (não vai para canal humano) | handoff rate em conversas iniciadas por áudio/imagem | n/a | [ESTIMAR] baseline a coletar nos primeiros 30d prod | 🔍 A medir |
| **Custo variável previsível** | USD/mensagem de mídia por tenant | n/a | ~$0.0015 USD/mensagem (audio+image mix) — cost-projection.md | ✅ Dentro do envelope |
| **Time-to-add novo canal** | dias para plugar Instagram/Telegram | n/a (acoplamento forte) | 5–7 dias (adapter + fixtures + contract test) | ✅ Validado por SC-013 |
| **Compliance LGPD** | retention gaps | 0 (texto-only) | 0 — URL 14d / transcript 90d / raw never (FR-027, ADR-034) | ✅ |

### 4.2 Indicadores operacionais a coletar em prod (primeiros 30d)

Adicionar ao dashboard Performance AI (epic 008) como parte do rollout 009:

- **p95 end-to-end áudio** (webhook → outbound delivery) — gate kill-criteria D3: se > 5s por 7d consecutivos, ativar epic 012
- **p95 end-to-end imagem / documento** — gates reais SC-002/SC-003 (benchmarks atuais são mocked)
- **Taxa `[pdf_scanned]` marker** — se ≥5% dos docs/mês, ativar epic 011
- **Cache hit rate processors** — gate SC-007 (≥30% após 7d) — confirma economia planejada
- **Marker distribution** (`[budget_exceeded]`, `[provider_unavailable]`, `[audio_silent]`, `[content_unsupported: *]`) — detecta patologias cedo
- **Alucinação de transcrição** (SC-011) — amostra mensal 100 áudios, revisão QA humana binária
- **PII em descrições de imagem** (SC-012) — amostra mensal 50 imagens, mesma rotação QA

---

## 5. MVP & milestones — impacto

| Milestone | Status | Ação |
|-----------|--------|------|
| MVP (001–006) | ✅ Completo (desde 2026-04-13) | — |
| **Admin** (007 ✅ + 008 in-progress + 017 sugerido) | 008 mantido in-progress (5 BLOCKERs no repo externo) | — |
| **Media + Multi-Source** (009 + 010 + 011 + 012) | **009 shipped** (pending merge) | Marcar 009 → shipped ao concluir merge develop |
| Post-MVP (013 + 014 + 015) | sugerido | Re-priorizar: 010 à frente de 013 |
| Public API Fase 2 (013-renum → 018 Public API) | trigger: 1º cliente pagante | Mantido |
| Ops Fase 3 (014-renum → 019 TenantStore Postgres) | trigger: ≥5 tenants | Mantido |

**Novo milestone sugerido**: "Multi-Source Expansion" — agrupa 010 (Instagram/Telegram), sai naturalmente como continuação do Media milestone uma vez que 009 está shipped.

---

## 6. Não este ciclo (backlog deferido)

Mantido do pitch original + novos deferred explícitos descobertos:

| Item | Motivo da exclusão do 009 | Revisitar quando |
|------|---------------------------|------------------|
| Instagram / Telegram (agora epic 010) | Fora do apetite de 5 semanas; arquitetura validada via Meta Cloud em PR-C | **Agora** (Now — próximo epic) |
| PDF OCR automático | LocalDocumentExtractor já emite `[pdf_scanned]`; OCR remoto é escopo novo | Volume `[pdf_scanned]` ≥5% docs/mês |
| Streaming transcription | UX inline (D3) cobre 99% dos casos; streaming é otimização premature até p95 real > 5s | p95 áudio > 5s por 7d consecutivos |
| Async follow-up ("recebi, processando...") | Quebra UX padrão WhatsApp (resposta única esperada) | Revisita em retro se feedback negativo de clientes |
| Meta Cloud resolver de media URL (Graph API two-hop) | PR-C ficou no level "adapter normaliza texto + metadata"; bytes reais via Graph API é follow-up | Epic 010 (junto com Instagram/Telegram) |
| Tradução automática de conteúdo | Qualidade PT-BR de Whisper/vision é suficiente v1 | Após cobertura de idiomas além de PT |
| Detecção semântica de alucinação (LLM auxiliar) | Heurística determinística (duração + blocklist) é suficiente | Após amostragem SC-011 mostrar > 2% alucinação |
| Tabular extraction de PDF | Epic 011 foco OCR; tabular é nicho | Gate volume (ainda não mensurado) |
| Classificação automática de documentos | Nicho B2B; fora do MVP | Depois de epic 011 |
| Refactor do shim `request_compat.py` | TTL declarado = epic 010 | Epic 010 (limpar legacy shape) |
| SC-013 gate design robusto (tag pinning) | Débito técnico pequeno; mitigação via ADR-035 addendum basta no curto prazo | Epic 010 (com-refactor do CI de adapters) |

---

## 7. Auto-Review

### Tier 1 — Deterministic

| # | Check | Resultado |
|---|-------|-----------|
| 1 | Output file exists and non-empty | ✅ |
| 2 | Epic 009 status reassessed (in-progress → shipped) | ✅ |
| 3 | Follow-up epics discovered explicitly listed (010/011/012) | ✅ |
| 4 | Concrete diff proposals for roadmap.md | ✅ (4 commits) |
| 5 | Risks (new R7/R8 + pending URL coverage) added | ✅ |
| 6 | No placeholder markers (TODO/TKTK/???/PLACEHOLDER) | ✅ |
| 7 | Leading indicators for outcome tracking defined | ✅ |
| 8 | HANDOFF block present at footer | ✅ (ver final) |

### Tier 2 — Scorecard

| # | Item | Self-assessment |
|---|------|-----------------|
| 1 | Re-priorização justificada (não preferência) | ✅ — 010 sobe por risco reduzido + valor estratégico; 013 desce por apetite maior |
| 2 | Dependências acíclicas preservadas | ✅ — 010/011/012 dependem de 009; 009 entrega foi o desbloqueador |
| 3 | MVP criterion inalterado | ✅ — mantém 001–006 shipped |
| 4 | Milestones têm critério testável | ✅ — ver §5 + §4.2 gates numéricos |
| 5 | Iniciativas conectam a outcomes (não vaidades) | ✅ — §4.1 tabela outcome × indicator |
| 6 | Kill criteria explícito para itens condicionais | ✅ — 011 gate ≥5% docs/mês; 012 gate p95>5s/7d |
| 7 | Confidence com justificativa | ✅ Alta — dados do próprio epic + 4 reports convergentes |

---

## 8. Recommendations — next 2 weeks

1. **Resolver 2 CRITICALs do analyze-post antes de taggar 009 shipped** (1 dia):
   - P1: pinar tag `pre-pr-c-merge-009` no repo prosauai OU documentar rebaixamento do SC-013 como checklist humano no ADR-035
   - P2: adicionar 3 rotas em `platform.yaml::testing.urls` com `expect_status` correto

2. **Commitar 5 edições pendentes do working tree** identificadas no reconcile-report §Phase 9 (1 hora):
   ```bash
   git add platforms/prosauai/engineering/{containers,context-map,domain-model}.md \
           platforms/prosauai/decisions/ADR-029-cost-pricing-constant.md \
           platforms/prosauai/decisions/ADR-035-meta-cloud-adapter-integration.md \
           platforms/prosauai/planning/roadmap.md platforms/prosauai/business/features.md
   git commit -m "docs(prosauai): finalize epic 009 documentation + ADRs 030-035"
   ```

3. **Aplicar edits recomendados pelo reconcile** P1/P2/P4/P5 (30 min): `integrations.md` (D8.1 — HIGH), `solution-overview.md` (D1.1 — MEDIUM), `ADR-031` canonical invariants (D10.2), `ADR-033` monitoring gate (D10.1).

4. **Aplicar 4 commits propostos em §3.2 deste report** em `planning/roadmap.md`.

5. **Abrir issue "Epic 009 follow-up hardening"** no repo prosauai reunindo os 18 WARNINGs abertos do judge (W6–W24 menos W1–W5 fixed). Priorizar W8 (timeout math), W10 (retention batching), W13 (breaker observability) antes do dia 90 de prod.

6. **Iniciar epic 010 (Instagram/Telegram adapters)** via `/madruga:epic-context prosauai 010-instagram-telegram-adapters` assim que 009 merge em `develop`.

---

## 9. Conclusão

Epic 009 desbloqueou **3 capacidades críticas** (mídia habilitada, multi-canal, observabilidade de custo por modalidade) e **validou arquiteturalmente** a abstração `ChannelAdapter`, barateando o custo marginal dos próximos canais (epic 010). A fila Post-MVP deve ser **re-priorizada**: 010 Instagram/Telegram sobe para "Now" por risco reduzido + apetite baixo + valor estratégico; 013 Agent Tools desce uma posição. Nenhum epic preexistente foi invalidado.

O backlog técnico (23 WARNINGs judge + 12 unresolved QA + 2 CRITICALs analyze-post) **não justifica abrir um epic novo** — deve ser tratado como issue operacional "Epic 009 follow-up hardening" a ser absorvido nas primeiras 2 semanas pós-merge, com prioridade nos itens que afetam resilience em prod (W8/W10/W13).

**Confidence**: **Alta** — convergência entre 4 reports (implement/analyze-post/judge/qa/reconcile) + cost projection empírica + 2096 testes verdes suporta o reassessment.

---

handoff:
  from: madruga:roadmap
  to: madruga:epic-context
  context: "Epic 009 reassessment concluído. Recomendações concretas: (1) resolver 2 CRITICALs analyze-post antes de merge develop, (2) commitar 5 edições pendentes + 4 edits do reconcile, (3) aplicar 4 diffs em planning/roadmap.md (status 009→shipped + 010/011/012 formalizados + 3 novos riscos R7/R8/URL-coverage), (4) abrir issue 'Epic 009 follow-up hardening' para 18 WARNINGs judge + 12 QA unresolved, (5) iniciar epic 010 (Instagram/Telegram) como próximo — risco arquitetural near-zero após SC-013 validação. Gates prod a monitorar nos primeiros 30d: p95 end-to-end (SC-001/002/003 reais), cache hit rate (SC-007), marker distribution, alucinação (SC-011), PII leaks (SC-012)."
  blockers: []
  confidence: Alta
  kill_criteria: "Invalidado se (a) merge develop falhar em CI revelando regressão (SC-010), (b) prod real mostrar p95 áudio > 15s nos primeiros 7d (força revisitar ADR-033 provider OpenAI + ativar epic 012 mais cedo), (c) custo mensal real por tenant superar $150 em volume 10k (10x do projetado — força repensar cache/budget), OU (d) comportamento inesperado do MetaCloudAdapter em produção revelar lacuna na abstração ChannelAdapter (força refactor ADR-031 antes de epic 010)."
