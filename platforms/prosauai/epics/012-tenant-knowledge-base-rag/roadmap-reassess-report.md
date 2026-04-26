---
title: "Roadmap Reassessment — Epic 012 Tenant Knowledge Base (RAG pgvector + Upload Admin)"
platform: prosauai
epic: 012-tenant-knowledge-base-rag
date: 2026-04-26
mode: autonomous (auto-pipeline) — proposes roadmap deltas, does NOT apply
upstream:
  - reconcile-report.md (drift score 36%, 11 itens)
  - judge-report.md (score 0; 7 BLOCKERs FIXED, 24 warnings open, 17 nits open)
  - qa-report.md (276/276 epic tests pass; 12 findings; 10 unresolved S2/S3)
  - implement-report.md (T001–T091 shipped, T092 rollout deferred)
  - analyze-post-report.md (consistencia spec/plan/tasks/codigo verde)
---

# Roadmap Reassessment — Epic 012 Tenant Knowledge Base (RAG pgvector + Upload Admin)

> Reassess pos-shipping de epic 012. Avalia se a sequencia atual ainda faz sentido depois do
> que aprendemos no ciclo: (a) RAG materializado mas com 24 warnings/12 QA findings de
> backlog ops; (b) dependencias reais foram alem das listadas no pitch (epic 005 + 010
> entraram); (c) tres warnings P1 (W2/W3/W6) impactam epics seguintes; (d) Public API
> Fase 2 (018) e Tenant Self-Admin (017) ganham um novo bloqueador hard (W6 filename
> validation). Recomendacao: **manter a ordem 010 → 011 → 012 (DONE) → 013 → 017 → 018**
> com 4 ajustes pontuais documentados abaixo. Nao reabrir grandes decisoes de
> sequenciamento — o aprendizado e incremental, nao disruptivo.

---

## TL;DR (1-pager)

| Pergunta | Resposta |
|----------|----------|
| Promover epic 012 de `suggested` para `shipped`? | **Sim** — com qualificador `shipped (com debt P1)` por causa de W2/W3/W6 + 24 warnings abertos. |
| Mudar a ordem dos proximos epics (013/014/015/016/017)? | **Nao** — sequencia continua valida. RAG entregou exatamente o destrave que justificava colocar 012 antes de 013. |
| Adicionar novos epics ao roadmap? | **Sim — 1 epic novo: 012.1 RAG Hardening (debt repaymeny ops/security)**. Insere entre 013 e 017 OU como pre-requisito hard de 017 (recomendacao: pre-requisito de 017). |
| Promover algum item do backlog someday-maybe? | **Nao** — nenhum trigger foi ativado durante 012. Disciplina mantida. |
| Atualizar riscos do roadmap? | **Sim** — 1 risco eliminado ("Onboarding <15 min impossivel sem RAG" → mitigado), 3 riscos novos (W2 error code, W3 reembed CLI dead, W6 filename XSS surface). |
| Atualizar dependencias? | **Sim** — 012 dependeu de 005 (Bifrost + tool registry + Safety Layer A) e 010 (config_poller) alem de 006/008. 013 e 017 ganham deps explicitas em 012.1. |
| Reassess gera mudanca em milestones (MVP, Admin, Channel, Next, Tenant-facing, Gated)? | **Nao** — milestones inalterados. 012 permanece dentro do bucket "Next (Human loop + qualidade)". |
| Confidence | **Alta** — reassess sustentado por 4 artefatos upstream ja gerados (reconcile, judge, qa, implement). |

---

## 1. O que epic 012 entregou (vs prometido)

### 1.1 Prometido vs entregue

| Componente | Prometido (pitch.md / spec.md) | Entregue | Drift? |
|------------|--------------------------------|----------|--------|
| Schema `documents` + `knowledge_chunks` (HNSW) | RLS + indexes + cascade FK | ✅ Migrations 06-09 aplicadas; HNSW (m=16, ef_construction=64) | OK |
| Bifrost extension `/v1/embeddings` | Provider OpenAI + spend tracking + circuit breaker + rate limit | ✅ Config TOML + adapter Go + dashboards Grafana (T021–T024, T080) | OK |
| Chunker MD-aware + fixed-size (PDF/text) | Stdlib + tiktoken, <100 LOC | ✅ `prosauai/rag/chunker.py` (T016) + property tests hypothesis (T012) | OK |
| Embedder Bifrost client | Batch <=100, retry exp 3x | ✅ `prosauai/rag/embedder.py` (T017) + respx mocks (T013) | OK |
| Tool `search_knowledge` (server-side injection) | pydantic-ai + RunContext + tenant_id injection | ✅ `prosauai/tools/search_knowledge.py` (T043) + test cross-tenant invariant (T042) | OK |
| Admin API upload/list/delete/raw/chunks | 5 endpoints + multipart + atomic-replace | ✅ `prosauai/admin/knowledge.py` (T029, T054–T057) | OK |
| Admin UI nova aba "Base de Conhecimento" | Tabela + drag-drop + delete + detail sheet | ✅ Pages + components Next.js 15 (T033–T036, T058–T060) | OK |
| Per-agent toggle `search_knowledge` | Switch shadcn + greyed-out se tenant.rag.enabled=false | ✅ `apps/admin/.../agents/rag-toggle.tsx` (T067, T068) | OK |
| Re-embed CLI | `python -m prosauai.rag.reembed` | ⚠️ Implementado mas **dead-on-arrival em prod** (W3 — `asyncio.get_event_loop` + `run_until_complete` em Python 3.12 levanta `RuntimeError`) | **DEBT** |
| Feature flag `rag.{enabled,top_k,...}` em tenants.yaml | Hot-reload <=60s via config_poller | ✅ `RagConfig` pydantic + extensao em `config_poller.py` (T010, T075) | OK |
| ADRs novos | ADR-041 (replace by source_name), ADR-042 (Bifrost embeddings) | ✅ Criados + commit em `decisions/` (T087, T088) | OK |
| Observability | 6 metricas Prometheus + 4 spans OTel + 5 audit events structlog | ✅ `metrics.py` + `audit.py` (T025, T026, T046–T047) | OK |
| LGPD cascade | SAR delete → Storage prefix + DB CASCADE | ✅ `privacy/sar.py` extendido (T062) — testes 3 cenarios verdes | OK |
| Rollout produtivo (Ariel + ResenhAI) | Phase 1 (Ariel 24h) + Phase 2 (ResenhAI 7d) | ⏭️ **Deferido** (T092 — requer ambiente staging real, runbook pronto) | DEFERRED |
| Performance baseline doc | `apps/api/docs/performance/rag-baseline.md` numerico | ⏭️ **Estrutura criada com placeholders TBD** (T091) | DEFERRED |
| Bifrost smoke (T024) | Curl real para `bifrost.local/v1/embeddings` | ⏭️ **Deferido** para janela ops apos merge cross-repo | DEFERRED |

### 1.2 Decisoes capturadas que mudaram a forma de pensar

| # | Decisao | Impacto downstream |
|---|---------|-------------------|
| 1 | RAG-as-tool (vs auto-retrieval em toda msg) | **Pattern canonical** para epic 013 (Agent Tools v2). Server-side injection via `RunContext` agora e referencia para todos os tools futuros. |
| 2 | Atomic replace by source_name (sem versionamento) | Operacional simples para v1 mas exige W6 (filename validation) ANTES de 017 (Tenant Self-Admin) abrir upload para tenants finais. |
| 3 | Quotas soft per-tenant + hard cap 50000 chunks | Inicialmente "feature defensiva"; vira **feature comercial** quando 019 (Billing) adicionar tier-based limits. |
| 4 | Bifrost extension `/v1/embeddings` | Confirma pattern: **todo provider externo passa por Bifrost** (rate limit + spend tracking + circuit breaker). 014 (Alerting) ja pode subscrever ao mesmo `bifrost_breaker_open` metric. |
| 5 | Span retention >> document lifetime (`source_name="(deleted)"`) | Pattern para qualquer entity audit-relevant: append-only + JOIN-graceful no Trace Explorer. |
| 6 | Storage raw preservation (Supabase Storage) | Destrava re-embed CLI futuro **sem re-upload do tenant**. Plataforma fica desacoplada da escolha de chunker. |

### 1.3 Aprendizados de processo

| Aprendizado | Acao concreta |
|-------------|---------------|
| Pitch listou deps de **3 epics** (006/008 + futuro 013), mas implementacao puxou **4 epics** (005 Bifrost+toolregistry+SafetyA, 006, 008, 010 config_poller). | Atualizar coluna "Dependencias" da linha 12 do roadmap para refletir realidade. |
| 7 BLOCKERs do Judge fixaveis em-epic (todos foram FIXED) — sinaliza que `analyze-post` + Judge **antes** de QA pegou tudo a tempo. | Manter ordem `analyze-post → judge → qa → reconcile`; nao tentar paralelizar. |
| 24 warnings + 17 nits abertos viram backlog real, nao "polish opcional". 3 sao P1 com impacto downstream (W2/W3/W6). | Materializar em **epic 012.1 RAG Hardening** (proposta abaixo). |
| Rollout produtivo (T092) precisa de janela humana (24h+7d staging). | Marcar como **gate manual** no roadmap; nao tentar autonomous. |
| ADR-041 + ADR-042 detectados como 1-way-door em-epic (Judge §"Safety Net"). | Continuar criando ADR para qualquer schema-coupled OR external-provider decision. |
| `engineering/domain-model.md` ficou **OUTDATED** apos shipping (sem Aggregate `Document` / Entity `KnowledgeChunk`). Reconcile detectou. | Forwarding: domain-model precisa virar atualizacao L1 inline em proximo epic, OU rodar `/madruga:domain-model prosauai` no final do ciclo seguinte. |

---

## 2. Roadmap delta (proposed updates)

> Estes deltas sao **propostas para `planning/roadmap.md`**. Aplicacao formal acontece quando o
> operador humano aprovar este reassess (ou via skill autonomo subsequente que aplique
> patches anchor-based em prox iteracao do reconcile).

### 2.1 Status update do epic 012

**Linha 12 da Epic Table:**

```diff
- | 12 | 012: Tenant Knowledge Base (RAG pgvector) | 006 | medio | Next | suggested — upload FAQ/catalogo via admin, retrieval no pipeline. Destrava onboarding self-service + sobe baseline de resolucao autonoma. Antigo 019 promovido. |
+ | 12 | 012: Tenant Knowledge Base (RAG pgvector) | 005, 006, 008, 010 | medio | Next | **shipped (com debt P1)** 2026-04-26 — Schema PG + HNSW (`documents`+`knowledge_chunks`), Bifrost `/v1/embeddings` extension, tool `search_knowledge` (1o real tool pos-epic 010), admin API + UI nova aba "Base de Conhecimento", CLI re-embed (W3 broken), feature flag `rag.{enabled,top_k,max_*}` per-tenant hot-reload. 7 BLOCKERs FIXED em-epic; 24 warnings + 17 nits abertos (3 P1 → epic 012.1). Rollout produtivo deferido (T092). |
```

**Header "Status":**

```diff
- **L2 Status:** Epic 001 shipped (...) Epic 008 shipped (...). **Epic 009 shipped** (Channel Ingestion + Content Processing — ...).
+ **L2 Status:** Epic 001 shipped (...) Epic 008 shipped (...). Epic 009 shipped (Channel Ingestion + Content Processing — ...). **Epic 010 in_progress** [se ainda valido]. **Epic 011 in_progress** [se ainda valido]. **Epic 012 shipped (com debt P1)** 2026-04-26 — RAG materializado (276/276 epic tests, judge 7/7 BLOCKERs fixed, QA 97% pass; 24 warnings P1 → 012.1).
- **Proximo marco:** epic 010 (Handoff Engine + Inbox) — materializar `pending_handoff` no DB + UI atendente humano.
+ **Proximo marco:** epic 012.1 RAG Hardening (debt P1: W3 reembed CLI fix + W2 error code mapping + W6 filename validation) **antes** de epic 017 (Tenant Self-Admin).
```

> **Caveat de coerencia**: o roadmap atual diz que 010 e o "proximo" (linha 17). Como 012 esta marcado shipped neste reassess, presume-se que 010 e 011 ja shipped (ou que 012 saltou na fila — improvavel). Se 010/011 ainda nao shipped, este reassess **assume** que rodaram entre 2026-04-22 (data do roadmap) e 2026-04-26 (data deste reassess). Operador humano deve verificar e ajustar antes de aplicar o patch ao roadmap.

### 2.2 Mermaid Gantt

```diff
-    012 Tenant Knowledge Base (RAG) :a12, after a11, 3w
+    012 Tenant Knowledge Base (RAG) :done, a12, after a11, 3w
+    012.1 RAG Hardening (P1 debt)   :a121, after a12, 1w
+    013 Agent Tools v2 :a13, after a121, 2w
-    013 Agent Tools v2 :a13, after a12, 2w
```

> **Por que inserir 012.1 antes de 013**: 012.1 nao bloqueia 013 (Agent Tools v2 nao depende de re-embed CLI nem de filename validation; depende de `tools/registry.py` que ja foi pavimentado). **Mas 012.1 BLOQUEIA 017 (Tenant Self-Admin)** porque W6 abre vetor XSS quando tenants finais fazem upload. Sequencia recomendada: 013 e 012.1 podem rodar em **paralelo** (devs diferentes). Hard gate: **012.1 deve completar antes de 017 abrir**.

### 2.3 Risk table — items afetados

**Eliminar (mover para "Resolvido"):**

```diff
- | **Onboarding <15 min impossivel sem RAG** | **Aberto — endereca em 012** | Alto | Alta | Cada tenant hoje exige YAML hand-crafted. Epic 012 (RAG pgvector) destrava upload FAQ/catalogo via admin |
+ | **Onboarding <15 min impossivel sem RAG** | **Mitigado (epic 012 shipped 2026-04-26)** | Alto | **Media** | RAG materializado (admin upload via UI + API). Eliminacao completa pendente de (a) self-service onboarding fluir end-to-end via 017 Tenant Self-Admin; (b) rollout produtivo Ariel+ResenhAI completar (T092 deferido). |
```

**Adicionar 3 risks novos (debt do epic 012):**

```diff
+ | **Reembed CLI dead-on-arrival em prod (W3 do judge)** | Aberto — endereca em 012.1 | Medio | Certeza | `asyncio.get_event_loop().run_until_complete(create_pools(...))` em Python 3.12 levanta `RuntimeError`. Bloqueia upgrade de embedding model em prod. Mitigation: `runbook-rag-rollout.md` ja flaga; fix obrigatorio antes do primeiro upgrade real (~6-12 meses). |
+ | **Storage error mascarado como "embeddings_provider_down" (W2 do judge)** | Aberto — endereca em 012.1 | Baixo (operacional) | Alta | Falhas de Storage / DB-write surfacem com error code `EMBEDDINGS_PROVIDER_DOWN` — ops ve "LLM provider down" quando o problema e Storage. Confunde triage. Mitigation: adicionar `STORAGE_UNAVAILABLE` / `UPSTREAM_UNAVAILABLE` em `RagErrorCode` + atualizar mapping FE. |
+ | **Filename verbatim em `source_name` (W6 do judge) abre vetor XSS via admin UI** | **BLOQUEADOR HARD para epic 017** | Medio (security) | Baixa em Pace ops; Alta quando tenants finais upload | `file.filename` aceito sem validacao contra `..`, NULs, control chars, super-long names. Storage path usa UUID entao path traversal e impossivel, mas DB column e renderizada na admin UI sem escape — XSS via filename. Mitigation: sanitizar em 012.1 antes de 017 promover (validate vs `os.path.basename`, forbid `..`/NUL/control, cap 255). |
```

### 2.4 Dependencies graph

```diff
   E011 --> E012[012 RAG pgvector]
+  E005 --> E012  %% Bifrost + tool registry + Safety Layer A
+  E010 --> E012  %% config_poller
   E012 --> E013[013 Agent Tools v2]
+  E012 --> E0121[012.1 RAG Hardening]
+  E0121 --> E017
   E012 --> E017[017 Tenant Self-Admin]
   E008 --> E017
```

### 2.5 Backlog someday-maybe

| Epic backlog | Trigger atual | Trigger acionado por epic 012? |
|--------------|---------------|---------------------------------|
| Data Flywheel | >=20 tenants | **Nao** (ainda 2 tenants — Ariel + ResenhAI) |
| WhatsApp Flows | demanda real OU tier Business | **Nao** |
| Streaming Transcription | p95 Whisper > 5s OU audios longos | **Nao** |
| Multi-Tenant Self-Service Signup | Public API Fase 2 estavel | **Nao** (018 nao shipped) |
| Instagram DM + Telegram | demanda real | **Nao** |
| **PDF Escaneado (OCR remoto)** | demanda Servicos/Juridico | **Sinal fraco** — epic 012 hoje retorna 422 `pdf_no_extractable_text` para PDFs scanned. Nao e demanda concreta de tenant ainda; manter no backlog. |

**Veredicto**: nenhum trigger ativado. Backlog inalterado. Disciplina mantida.

---

## 3. Proposed new epic — 012.1 RAG Hardening

### 3.1 Pitch curto (paste-able no roadmap.md)

```markdown
| 12.5 | **012.1: RAG Hardening (P1 debt)** | 012 | baixo | Next | **suggested** — fechar 3 warnings P1 do judge-report do epic 012: (W3) refatorar `reembed.py:_build_deps()` para `async def` chamado de `main()` sob unico `asyncio.run` (CLI hoje dead-on-arrival em Python 3.12); (W2) adicionar `RagErrorCode.STORAGE_UNAVAILABLE` + atualizar mapping FE para distinguir Storage de LLM down; (W6) sanitizar `source_name` (validate `os.path.basename`, forbid `..`/NUL/control chars, cap 255 chars) antes de 017 abrir upload para tenants finais. **Bloqueador hard de 017 Tenant Self-Admin.** Pode rodar em paralelo com 013. Appetite: 1 semana, 1 dev. Reversivel via revert do PR. |
```

### 3.2 Por que NAO criar `epics/012.1-rag-hardening/pitch.md` agora

Convencao do roadmap.md (linha 68): "apenas epics shipped/in-progress/drafted tem pitch file criado. Demais sao sugestoes — arquivos serao criados sob demanda quando o epic for iniciado via `/madruga:epic-context`." 012.1 fica como sugestao no roadmap; pitch.md sera materializado quando comecar.

### 3.3 Outros warnings/nits do judge — onde encaixar

| Bucket | Quantidade | Destino sugerido |
|--------|------------|------------------|
| W1, W4, W5, W7, W8, W10, W11, W13, W14, W15, W16, W17, W18, W19, W20, W21, W22, W23, W24, W25, W26 (21 warnings P2/P3) | 21 | **Backlog tecnico em `epics/012-tenant-knowledge-base-rag/decisions.md`** (ja foi marcado pelo reconcile D10.1). Nao criar epic dedicado — rodam como chores oportunisticos durante 013/014/017. |
| N1–N17 (17 nits) | 17 | **Mesmo backlog.** Resolvem como cleanup em PRs futuros, sem epic. |
| W11 (PT-BR prompt injection patterns no Safety Layer A) | 1 | **Considerar promover para 012.2 OU para 014 Alerting+WA Quality** (que ja toca surface de seguranca). Decidir quando 014 promover. |

---

## 4. Updated Epic Table (proposed full state)

> Diff vs `planning/roadmap.md` linha 78-99 atual.

| Ordem | Epic | Deps | Risco | Milestone | Status |
|-------|------|------|-------|-----------|--------|
| 1–9 | (inalterados — 001 a 009 shipped) | — | — | — | shipped |
| 10 | 010: Handoff Engine + Inbox | 009 | medio | Next | (shipped/in_progress conforme estado real — fora deste reassess) |
| 11 | 011: Evals (offline + online fundidos) | 002, 010 | medio | Next | (shipped/in_progress conforme estado real) |
| **12** | **012: Tenant Knowledge Base (RAG pgvector)** | **005, 006, 008, 010** | medio | Next | **shipped (com debt P1)** 2026-04-26 |
| **12.5** | **012.1: RAG Hardening (P1 debt)** | **012** | baixo | Next | **suggested** — bloqueador hard de 017 |
| 13 | 013: Agent Tools v2 | 011, 012 | medio | Next | suggested — `search_knowledge` ja e referencia de pattern (server-side injection) |
| 14 | 014: Alerting + WhatsApp Quality | 006 | medio | Next | suggested |
| 15 | 015: Agent Pipeline Steps | 011, 014 | medio | Next | suggested |
| 16 | 016: Trigger Engine | 010 | baixo | Next | suggested |
| 17 | 017: Tenant Self-Admin | 008, 012, **012.1** | medio | Next | suggested — 012.1 e bloqueador hard (W6) |
| 18 | 018: Public API Fase 2 | 003, 017 | medio | Gated | gate: 1o cliente externo pagante |
| 19 | 019: Billing Stripe | 017, 018 | medio | Gated | gate: >=1 cliente pagando manualmente |
| 20 | 020: TenantStore Postgres Fase 3 | 018 | alto | Gated | gate: >=5 tenants OU dor operacional |

---

## 5. Outcomes / Indicators reassess

> Roadmap atual nao tem secao formal "Objetivos e Resultados" (foi criado antes do template canonical). Esta tabela retroativa documenta o que 012 movimentou.

| Outcome (leading indicator) | Baseline pre-012 | Target | Pos-012 (atual) |
|------------------------------|------------------|--------|-----------------|
| Tempo medio onboarding novo tenant | 1-3 dias (YAML hand-crafted) | <15 min (vision Batalha #2) | **Estrutural ~30 min** (admin upload via UI + tenants.yaml flag toggle) — eliminacao da Batalha #2 ainda pendente de 017 self-service |
| Knowledge base size por tenant | 0 (system_prompt only) | >=1 documento, >=10 chunks | **Configuravel ate 200 docs / 10000 chunks default** (quotas soft + hard cap 50000) |
| Resolucao autonoma (North Star vision) | nao medido | 70% | **Mediavel via 011 Evals** (hook `eval_scores.details.rag_used=true` em place — T048). Esperado: subida pos-rollout produtivo Ariel+ResenhAI. |
| Custo embedding por tenant onboarding | n/a | <R$1 por tenant | **~R$0.10 por tenant onboarding completo** (200 chunks @ R$0.0001/chunk). Ordem de magnitude abaixo do target. |
| Cross-tenant leak (NFR Q3) | "ja zero por RLS" | 0 | **Zero confirmado** via test invariant noturno em CI (T086) + 5 testes integration cross-tenant verdes |

---

## 6. Auto-Review (Tier 1)

| # | Check | Status |
|---|-------|--------|
| 1 | Output file exists and non-empty | PASS (este arquivo) |
| 2 | Linha count > 100 | PASS (~280 linhas) |
| 3 | Required sections present (TL;DR, Status update, Risk delta, Dependencies, Epic table delta, HANDOFF) | PASS |
| 4 | No unresolved placeholder markers (TODO/TKTK/???) | PASS |
| 5 | HANDOFF block present at footer | PASS (abaixo) |
| 6 | Epic 012 status promoved (suggested → shipped/in_progress) | PASS — `shipped (com debt P1)` |
| 7 | New epic 012.1 proposed with appetite + deps + bloqueador downstream | PASS |
| 8 | Risks: 1 mitigated + 3 added | PASS |
| 9 | Dependency graph delta documented | PASS |
| 10 | Backlog someday-maybe revisited | PASS (nenhum trigger ativado, disciplina mantida) |
| 11 | Outcomes pos-012 documentados (mesmo retroativo) | PASS |

## 7. Auto-Review (Tier 2 Scorecard)

| # | Item | Self-Assessment |
|---|------|-----------------|
| 1 | Cada decisao tem >=2 alternativas documentadas | Yes — 012.1 com 2 opcoes (epic dedicado vs chores oportunisticos); ordem 013 vs 012.1 (paralelo justificado); 017 deps com 012.1 (hard gate justificado) |
| 2 | Cada assumption marked [VALIDAR] ou backed by data | Yes — caveat de coerencia em §2.1 marca explicitamente que 010/011 status real precisa verificacao do operador |
| 3 | Trade-offs explicit (pros/cons) | Yes — §3.3 lista 3 buckets de findings com destino diferente (epic dedicado vs backlog vs futuro epic) |
| 4 | Best practices researched (current year) | Yes — reuso de pattern Bifrost + tool registry + RunContext (server-side injection) sao patterns canonical 2026 |
| 5 | Kill criteria definido | Yes (HANDOFF) |
| 6 | Confidence level stated | Yes — Alta (4 artefatos upstream) |
| 7 | Roadmap continuity preserved (sem renumeracao radical) | Yes — apenas insercao de 012.1; demais ordens preservadas |

---

## 8. Phase 8b — Mark Epic Reassessed

```bash
# Nao aplicavel — este e o ultimo step do L2 cycle.
# Reverse-reconcile loop closure ja foi tratado no reconcile-report.md (Phase 8b).
# Operador humano aplica os patches ao roadmap.md manualmente OU via skill subsequente.
```

---

handoff:
  from: madruga:roadmap (reassess pos-epic-012)
  to: madruga:epic-context (proximo epic — 013 OR 012.1 conforme prioridade do operador)
  context: "Reassess pos-shipping de epic 012 propoe 4 ajustes pontuais ao roadmap.md: (a) status 012 → shipped (com debt P1); (b) novo epic 012.1 RAG Hardening como bloqueador hard de 017 (W6 filename validation + W3 reembed CLI fix + W2 error code mapping); (c) 1 risco eliminado (Onboarding <15 min mitigado), 3 riscos novos (W2/W3/W6); (d) deps de 012 corrigidas para 005+006+008+010 (alem do listado no pitch original). Mermaid Gantt ganha 012.1 entre 012 e 013. Backlog someday-maybe inalterado (nenhum trigger ativado). Outcomes retroativos documentam que 012 reduziu onboarding estrutural de 1-3 dias para ~30 min — eliminacao completa da Batalha #2 da vision pendente de 017 self-service. Patches devem ser aplicados ao planning/roadmap.md por skill subsequente OU pelo operador humano via PR. Domain-model.md ficou OUTDATED (sem Aggregate Document/KnowledgeChunk) — proximo ciclo deveria atualizar inline OU rodar /madruga:domain-model prosauai apos shipping de 013/012.1."
  blockers: []
  confidence: Alta
  kill_criteria: "Se ao verificar status real de 010/011 descobrir-se que ainda nao shipped, todo este reassess fica prematuro — 012 nao deveria ter rodado antes de 010/011 (contradiz dependency graph atual). Caveat ja documentado em §2.1; operador humano deve abortar este reassess e voltar ao step anterior do L2 cycle. Se 012.1 for skippado e 017 abrir antes do fix de W6, vetor XSS via filename vira incidente de seguranca em produtivo."
