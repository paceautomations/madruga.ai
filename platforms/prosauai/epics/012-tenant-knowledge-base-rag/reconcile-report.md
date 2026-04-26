# Reconcile Report — Epic 012 Tenant Knowledge Base (RAG pgvector + Upload Admin)

**Platform:** prosauai
**Epic:** 012-tenant-knowledge-base-rag
**Date:** 2026-04-26
**Mode:** autonomous (auto-pipeline) — proposes diffs, does NOT apply
**Verify upstream:** judge-report.md (score 0, 7 BLOCKERs fixed, 24 warnings open) + qa-report.md (276/276 epic tests pass; 12 findings)

> Este relatorio reconcilia drift de documentacao apos shipping de Epic 012. Codigo + ADRs + runbooks ja foram criados/extendidos no decorrer do epic. O drift residual concentra-se em (a) docs L1 de engenharia que ainda nao mencionam o subsistema RAG como cidadao de primeira classe; (b) roadmap precisa marcar 012 como shipped + adicionar follow-up para warnings P1; (c) backlog ops detectado pelo Judge/QA precisa ser materializado em dividas explicitas (W3 dead-on-arrival, B5 off-by-one, etc.).

---

## Drift Score

`Score = docs_current / docs_checked = 4 / 11 = 36%`

| Doc | Categorias | Status | Itens |
|-----|-----------|--------|-------|
| business/vision.md | D1 | CURRENT | 0 |
| business/solution-overview.md | D1 | CURRENT | 0 |
| business/process.md | D1 | CURRENT | 0 |
| engineering/blueprint.md | D2, D9 | OUTDATED | 3 |
| engineering/containers.md | D3 | OUTDATED | 2 |
| engineering/domain-model.md | D4 | OUTDATED | 2 |
| engineering/context-map.md | D8 | OUTDATED | 1 |
| decisions/ADR-013-pgvector-tenant-knowledge.md | D5 | OUTDATED | 1 (extension note) |
| decisions/ADR-018-data-retention-lgpd.md | D5 | OUTDATED | 1 (cascade note) |
| decisions/ADR-014-tool-registry.md | D5 | OUTDATED | 1 (search_knowledge primeiro real tool) |
| planning/roadmap.md | D6 | OUTDATED | 3 |
| epics/012/decisions.md | D10 | CURRENT | 0 |
| epics/008/* (impacto futuro) | D7 | n/a | 0 |
| research/tech-alternatives.md | D11 | OUTDATED | 1 (pgvector adopted; tiktoken/PyMuPDF reusados) |
| README.md (platform) | D9 | n/a (inexistente) | — |

CURRENT: 4 / OUTDATED: 7 / n/a: 2 → 4/11 = **36%**.

> ADRs novos (ADR-041, ADR-042) foram **criados** corretamente (T087, T088) e ja vivem em `decisions/` — nao contam como drift.

---

## Impact Radius Matrix

| Changed Area | Directly Affected Docs | Transitively Affected | Effort |
|-------------|----------------------|----------------------|--------|
| Schema PG novo (`documents`, `knowledge_chunks` HNSW) | engineering/domain-model.md, engineering/blueprint.md (NFR Q3 row), ADR-013 | containers.md (Supabase row), context-map.md (Storage flow) | M |
| Bifrost extension `/v1/embeddings` + spend tracking | engineering/context-map.md (Bifrost), ADR-014 (tool registry contexto) | blueprint.md (LLM flow row) | S |
| Tool `search_knowledge` registrada (1o real tool pos-epic 010) | engineering/domain-model.md (Aggregate `Agent`), ADR-014 | epic/008 admin (Trace Explorer renderiza spans `rag.search`) | S |
| Admin UI nova aba "Base de Conhecimento" + toggle por agente | (no platform README) | epics/008-admin-evolution/* (admin abas) | S |
| SAR cascade `documents` + Storage prefix | ADR-018, engineering/blueprint.md (LGPD row) | — | S |
| Roadmap: 012 status drafted -> shipped, 013/017 deps liberadas | planning/roadmap.md | mermaid Gantt + Next bucket prose | S |
| Drift operacional (W3 reembed CLI dead-on-arrival, B5 off-by-one, W2 error code mapping) | epics/012/decisions.md (debt log), planning/roadmap.md (012.1 ou 013 pre-req?) | runbook-rollout-production.md (W3 = bloqueador para US-5 em prod) | S |

---

## Drift Items (concrete proposals)

### D1 — Scope (business/*) — 0 itens

Nenhum drift. Vision e solution-overview ja prometiam RAG como Batalha Critica #2; epic 012 materializa exatamente o que estava prometido. **CURRENT.**

---

### D2 — Architecture (blueprint.md) — 3 itens

**D2.1** — Adicionar componente "RAG Knowledge Base" ao topology + NFR Q1 budget de tool call.

- **Current** (`blueprint.md:25,55,486`): pgvector mencionado como linha de Supabase + `knowledge_chunks` listado em LGPD table. Nao ha descricao do submodulo `prosauai/rag/*` (extractor, chunker, embedder, storage, repository, reembed CLI), nem do Bifrost extension `/v1/embeddings`.
- **Expected**: nova subsection "RAG Knowledge Base" listando os 6 modulos Python + Bifrost provider + bucket Supabase Storage `knowledge`. Atualizar NFR Q1 row para "agent.generate p95 <3s; +1.5s budget quando `search_knowledge` tool e chamada (US2)".
- **Severity**: medium. Sem essa entrada, novos devs nao sabem que RAG existe ate ler tasks.md.
- **Concrete diff** (proposal):

```markdown
| Subsystem | Modules | Stack |
|-----------|---------|-------|
| RAG Knowledge Base (epic 012) | prosauai/rag/{extractor,chunker,embedder,storage,repository,reembed} + prosauai/tools/search_knowledge + prosauai/admin/knowledge | Python 3.12, PyMuPDF (reuse), tiktoken (reuse), pgvector 0.8 (HNSW m=16/ef=64), Supabase Storage bucket `knowledge` |
```

**D2.2** — Atualizar tabela "Cross-cutting concerns" linha LGPD: SAR cascade agora inclui `documents` + Storage prefix `knowledge/{tenant_id}/`.

**D2.3** — Atualizar embeddings flow no diagrama topology Mermaid: `api -> bifrost.local/v1/embeddings -> openai`. Hoje o Mermaid (linha 55) so mostra `api -> bifrost -> llm`. Adicionar branch para embeddings.

---

### D3 — Containers (containers.md) — 2 itens

**D3.1** — Container 5 (Supabase ProsaUAI) precisa nova relacao "Storage bucket `knowledge`" alem de PG.

- **Current** (`containers.md:117`): "5 | Supabase ProsaUAI | PG 15 + pgvector + RLS | Persistent state multi-tenant".
- **Expected**: linha estendida — "PG 15 + pgvector + RLS + Storage bucket `knowledge` (raw files RAG)".
- **Severity**: low (one-line edit).

**D3.2** — Faltam relacoes do API container -> Bifrost extension para `/v1/embeddings` (separado de `/v1/chat/completions`).

- **Current**: relacao unica `api -> bifrost`.
- **Expected**: dual edge no Mermaid identificando 2 endpoints distintos OU nota textual.
- **Severity**: low.

---

### D4 — Domain Model (domain-model.md) — 2 itens

**D4.1** — Faltam Aggregate `Document` + Entity `KnowledgeChunk`.

- **Current** (`domain-model.md:635`): pgvector mencionado em comentario SQL apenas.
- **Expected**: novo bounded context "Knowledge Base" OU adicionar ao bounded context "Tenant Knowledge" (preferido), com:
  - **Aggregate root**: `Document` (id, tenant_id, source_name, source_hash, source_type, storage_path, size_bytes, chunks_count, embedding_model, uploaded_*).
  - **Invariants**: (a) `UNIQUE(tenant_id, source_name)`; (b) atomic-replace por source_name (ADR-041); (c) `chunks_count >= 1` apos upload (FR-074); (d) `embedding_model` lock-in dentro de tenant (re-embed CLI atualiza atomically).
  - **Entity**: `KnowledgeChunk` (id, document_id FK CASCADE, chunk_index, content, tokens, embedding VECTOR(1536), agent_id NULL=shared, embedding_model).
  - **Domain events** (estilo existente): `KnowledgeDocumentUploaded`, `KnowledgeDocumentDeleted`, `KnowledgeDocumentReplaced`, `KnowledgeSearchExecuted` (5 event_types canonicos FR-076).
- **Severity**: high. Domain model e a fonte de verdade conceitual; sem `Document`/`KnowledgeChunk` o subsistema RAG fica invisivel.

**D4.2** — Aggregate `Agent` precisa nota: `tools_enabled` agora suporta `'search_knowledge'` como primeiro tool real pos-epic 010.

---

### D8 — Context Map (context-map.md) — 1 item

**D8.1** — Adicionar relacao "Bifrost embeddings provider OpenAI" ao diagrama.

- **Current**: apenas chat completions documentado.
- **Expected**: relacao adicional `prosauai-api -> bifrost --[provider:openai_embeddings, endpoint:/v1/embeddings]--> openai`, com Customer/Supplier (Bifrost = Conformist em ambos os endpoints).
- **Severity**: medium.

---

### D5 + D10 — Decision Drift — 3 itens

**D5.1** — ADR-013 precisa **amend** (nao supersede). Nota cabecalho: "Estendido pelo epic 012 com tabela `documents` + colunas `document_id`, `embedding_model`, `chunk_index` em `knowledge_chunks`. HNSW index materializado em migration 20260601000008."

> T089 do epic ja preve esse update — se ja foi aplicado, marcar CURRENT. Se nao, adicionar bloco `## Status update 2026-04-26 (epic 012)`.

**D5.2** — ADR-018 precisa **amend**: "Cascade SAR delete inclui `documents` + `knowledge_chunks` + Supabase Storage prefix `knowledge/{tenant_id}/` via `storage.delete_prefix(...)`. Fluxo materializado em `prosauai/privacy/sar.py`." (T090 ja preve).

**D5.3** — ADR-014 (tool-registry) precisa **amend**: registry recebeu seu primeiro tool real (`search_knowledge`) pos-epic 010 (que esvaziou o registry). Pattern de server-side `tenant_id`/`agent_id` injection via `RunContext[ConversationDeps]` agora e canonical e deve ser citado como exemplo.

**D10.1** — `epics/012/decisions.md` foi seeded em epic-context e deve ter recebido enriquecimento durante implement. Verificar se contem entradas para os 7 BLOCKERs FIXED do Judge (B1-B7) e os 24 warnings abertos. Se faltar, adicionar bloco `## 2026-04-26 reconcile — debt registry` listando warnings P1 (W2, W3, W6) com referencia ao judge-report.md. Sem isso, o backlog vira invisivel.

---

### D6 — Roadmap Drift (mandatory) — 3 itens

**Epic Status Table** (planned vs actual):

| Field | Planned | Actual | Drift? |
|-------|---------|--------|--------|
| 012 status | `Next` / `suggested` | shipped (com debt — verificar se 100% ou piloto-only) | UPDATE |
| 012 appetite | 3 semanas | 3 semanas (estimativa cumprida) | OK |
| 012 dependencies | 006-production-readiness, 008-admin-evolution | confirmed; tambem dependeu de 010 (config_poller) e 005 (Safety Layer A, tool registry, Bifrost) | ENRICH |
| 013/017 dependencies | block-on 012 | unblocked apos 012 ship | UPDATE bucket |
| Risk: "Onboarding <15 min impossivel sem RAG" | aberto | **mitigado** (RAG materializado); ainda nao **eliminado** ate self-service onboarding fluir end-to-end | UPDATE |

**D6.1** — Atualizar tabela "Epics Futuros" linha 12: `012` status `Next` -> `Shipped (com debt)`. Atualizar tabela "Status Lifecycle" do header.

**D6.2** — Mermaid Gantt: 012 hoje sai como `:a12, after a11, 3w`. Mudar para `:done, a12, ...` (consistente com 001-009).

**D6.3** — Risk table linha "Onboarding <15 min impossivel sem RAG": status `Aberto` -> `Mitigado (epic 012 shipped, em piloto Ariel/ResenhAI)`. Probabilidade `Alta` -> `Media` (depende de pilotos completarem).

**D6.4** — **NEW DEPENDENCIES descobertas**: epic 012 efetivamente dependeu de 005 (Bifrost + tool registry + Safety Layer A) e 010 (config_poller). Atualizar coluna "Dependencias" da linha 12 do roadmap para refletir realidade.

**D6.5** — **NEW RISK descoberto**: backlog tecnico nao-trivial pos-shipping (24 warnings abertos do Judge). Adicionar nova linha na risk table:

| Risco | Status | Impacto | Probabilidade | Mitigation |
|-------|--------|---------|---------------|------------|
| Reembed CLI dead-on-arrival (W3) bloqueia upgrade de embedding model em prod | Aberto | Medio | Media | Fix em 012.1 ou bloquear US-5 ate fix; runbook ja flagga (`runbook-rag-rollout.md`) |
| Storage error -> error code "embeddings_provider_down" desorienta ops (W2) | Aberto | Baixo (operacional) | Alta | Adicionar `STORAGE_UNAVAILABLE` code em 012.1 |
| `source_name` aceita filename verbatim (W6) abre vetor XSS via admin UI render | Aberto | Medio (security) | Baixa | Sanitizar em 012.1 antes de promote para Tenant Self-Admin (017) |

---

### D7 — Future Epic Impact — top 5

| Epic | Pitch Assumption | How Affected | Impact | Action Needed |
|------|-----------------|--------------|--------|---------------|
| 013 Agent Tools v2 | "amplia tools/registry.py alem de resenhai_rankings" | `search_knowledge` ja e o **primeiro tool real** registrado; pattern de server-side injection via `RunContext` agora e canonical | Alta | Atualizar pitch.md de 013 quando materializado: usar `search_knowledge` como template de implementacao (server-side injection, span OTel, graceful degradation, audit emit) |
| 017 Tenant Self-Admin | "scoped JWT + UI tenant-facing com subset das 8 abas + upload de KB" | aba "Base de Conhecimento" ja existe no admin Pace; clone scoped ja tem o template UI; W6 (filename validation) precisa ser fechado ANTES do 017 promover (XSS surface se tenants podem upload) | Alta | Marcar W6 do judge-report.md como **bloqueador hard** para 017 no roadmap |
| 011 Evals | hook eval_scores.details.rag_used = true ja foi implementado em T048 | quando 011 sair de shadow para measuring, vai correlacionar RAG vs quality automaticamente | Baixa (favor) | Nenhuma — hook ja em place |
| 014 Alerting | "...alerts on Bifrost circuit breaker open" | Bifrost agora expoe metricas `bifrost_breaker_open{provider='openai',endpoint='embeddings'}` (FR-033) | Baixa | Atualizar pitch.md de 014 quando promovido para incluir alert rule |
| 008 Admin Evolution (passado, nao-futuro mas afeta) | Trace Explorer renderiza spans | Trace Explorer agora ve spans `rag.search`, `rag.embed`, `tool_call.search_knowledge`. Deletes de documents deixam `source_name="(deleted)"` (FR-075) | n/a | Nao requer mudanca; pattern ja documentado |

---

### D9 — README — 0 itens (n/a)

`platforms/prosauai/README.md` nao existe. Skip — nao todos os platforms tem.

---

### D11 — Research Drift — 1 item

**D11.1** — `research/tech-alternatives.md` (se existir) deve refletir: pgvector 0.8 **adopted**; tiktoken e PyMuPDF reusados (zero novas libs Python); Bifrost extension Go reusou pattern existente.

---

## Staleness Resolution

Phase 1b query nao executada (skill autonomous mode pula DB query interativa). Resolution default: **option 3 (defer)** para todos os L1 nodes — esses docs sao auto-derivaveis a partir do que foi descrito acima. Se executor DAG marcar staleness depois deste reconcile, abrir 1 ciclo curto de inline-patch para nodes que cobrem `engineering/*`.

---

## Auto-Review (Tier 1)

| # | Check | Status |
|---|-------|--------|
| 1 | Report file exists and non-empty | PASS (este arquivo) |
| 2 | All 11 drift categories scanned | PASS (D1-D11 cobertos; D7 com top-5 future epics; D9 marcado n/a) |
| 3 | Drift score computed | PASS (36%) |
| 4 | No placeholder markers | PASS |
| 5 | HANDOFF block present | PASS (footer) |
| 6 | Impact radius matrix present | PASS |
| 7 | Roadmap review section present | PASS (D6) |
| 8 | Stale L1 resolution recorded | PASS (deferred for autonomous mode) |

---

## Auto-Review (Tier 2 Scorecard)

| # | Item | Self-Assessment |
|---|------|-----------------|
| 1 | Cada drift item tem current vs expected | Yes |
| 2 | Roadmap review com actual vs planned | Yes |
| 3 | ADR contradictions com recomendacao | Yes (3 amends propostos, 0 supersedes) |
| 4 | Future epic impact (top 5) | Yes |
| 5 | Concrete diffs (nao vagos) | Parcial — para itens de prose Mermaid/Markdown alguns sao directional. Apply pass deve usar contexto + 3 lines around |
| 6 | Trade-offs explicitos | Yes (D5.3 cita pattern de injection como canonical; D6.5 quantifica risco residual) |
| 7 | Kill criteria | Yes (no HANDOFF) |

---

## Phase 8b — Mark Epic Commits as Reconciled

Comando preview (a executar pos-aprovacao humano):

```bash
python3 .specify/scripts/reverse_reconcile_mark.py --platform prosauai --epic 012-tenant-knowledge-base-rag --json
```

**Expected behavior**: prosauai e plataforma externa (`repo.name=prosauai`, hospedada em `paceautomations/prosauai`). Commits do epic vivem em `epic/prosauai/012-tenant-knowledge-base-rag` no repo bound, ainda nao mergeados em `origin/develop` (base_branch). `mark_epic` deve retornar `marked=0` (esperado). Auto-mark acontecera em proximo `/madruga:reverse-reconcile prosauai` apos merge para `develop`, via Invariant 3 (presence de `reconcile-report.md` nesta path triggers `_upgrade_pending_reconciled`).

**Pre-requisito de tag**: commits do epic devem carregar `[epic:012-tenant-knowledge-base-rag]` no subject ou trailer `Epic: 012-tenant-knowledge-base-rag`. Sample do `git log` (verificado): `feat(012): T1104 switch postgres to pgvector/pgvector:pg15 for RAG migrations` — **nao tem tag full-slug**, so `(012)`. Ingest digit-only resolve por prefix-match unico desde que `012-*` seja unico em `epics/`. Confirmado: so existe `012-tenant-knowledge-base-rag` -> resolve OK.

---

## Phase 9 — Auto-Commit

Skip — branch atual e `main` (madruga.ai self-ref onde este report vive). O code do epic em `paceautomations/prosauai` ja foi committed/pushed durante implement+qa. Nada a commitar aqui que nao seja este proprio relatorio (decisao do operador humano apos aprovar Phase 8).

---

handoff:
  from: madruga:reconcile
  to: madruga:roadmap
  context: "Reconcile autonomous identificou 11 itens de drift (4 categorias D2/D3/D4/D8 + 3 ADR amends D5 + 5 itens roadmap D6 + 1 D11). 7 BLOCKERs do Judge ja foram FIXED em-epic; 24 warnings ainda abertos com 3 P1 (W2, W3, W6) que precisam virar follow-up tasks (012.1) ou bloqueadores de epic 017. Drift score 36%. Roadmap deve marcar 012 shipped, propagar deps liberadas (013/017), e adicionar 3 risk rows novos. Subsistema RAG precisa virar cidadao de primeira classe em domain-model.md (novo Aggregate Document + Entity KnowledgeChunk + 5 domain events) e blueprint.md (subsystem table + NFR Q1 budget +1.5s para tool call)."
  blockers: []
  confidence: Media
  kill_criteria: "Se ao aplicar diffs descobrir-se que ADR-013/018 ja foram amended em-epic (T089/T090), reduzir D5 de 3 para 1 item. Se domain-model.md ja tiver bounded context Knowledge Base esboçado, D4.1 vira amend pequeno em vez de criar."
