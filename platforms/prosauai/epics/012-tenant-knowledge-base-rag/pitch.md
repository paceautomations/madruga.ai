---
id: "012"
title: "Tenant Knowledge Base — RAG pgvector + upload admin"
slug: 012-tenant-knowledge-base-rag
appetite: "3 semanas"
status: shipped
priority: P1
depends_on: ["006-production-readiness", "008-admin-evolution"]
created: 2026-04-24
updated: 2026-04-24
delivered_at: 2026-04-26
---

# Epic 012 — Tenant Knowledge Base (RAG pgvector + upload admin)

> **DRAFT** — planejado enquanto epic 011 (Evals) executa. Promocao via `/madruga:epic-context prosauai 012` (sem `--draft`) faz delta review e cria branch.

## Problema

A [vision](../../business/vision.md#L88) promete **self-service onboarding <15 minutos** como Batalha Critica #2. Hoje isso e **impossivel estruturalmente**: cada tenant novo exige que um dev da Pace escreva YAML a mao com persona, system prompt, regras de negocio, catalogo de produtos, stats do cliente. Ariel e ResenhAI funcionam porque o time **conhece o negocio**; um cliente externo entrar exigiria dias de onboarding manual, nao minutos.

O gap concreto em producao:

1. **Agente nao sabe nada alem do system_prompt**. Sem RAG, o unico modo de fazer o bot responder "qual e o horario de funcionamento?" ou "voces tem X produto?" e hardcoded no prompt — nao escala alem de 5-10 FAQs.
2. **Tenants enviam PDFs de catalogo/FAQ por whatsapp pros devs**. Workflow real observado: cliente manda PDF de FAQ, dev copia trechos pro system_prompt, commita. Overhead humano absurdo.
3. **ADR-013 (Aceito 2026-03-25) decidiu pgvector + schema `knowledge_chunks`** mas a tabela **nunca foi criada** — schema existe so no ADR. Todo o plano de RAG ficou no papel.
4. **Risco aberto no [roadmap](../../planning/roadmap.md#L185)**: "Onboarding <15 min impossivel sem RAG" — endereca em 012.
5. **Baseline de resolucao autonoma (North Star 70%)** impossivel de subir sem o agente ter contexto do negocio especifico. Epic 011 vai medir, mas epic 012 e o que **faz o numero subir**.

A vision ja decidiu a estrategia ha 6 semanas (ADR-013). Epic 012 **materializa** o que o ADR prometeu: migration + API de upload + admin UI + RAG tool no pipeline. Escopo v1 deliberadamente enxuto: Markdown/text/PDF, upload sync <=10MB, per-tenant, retrieval como tool opcional.

## Appetite

**3 semanas** (1 dev full-time, 1 PR mergeavel em develop, reversivel via `rag.enabled: false` per-tenant em <60s).

| Semana | Entrega | Gate |
|--------|---------|------|
| Sem 1 | Migration `knowledge_chunks` + `documents` + HNSW index; Bifrost extension para `/embeddings`; chunker MD-aware + PDF (PyMuPDF reuse do epic 009) | Unit tests verdes |
| Sem 2 | `POST /admin/knowledge/documents` (upload sync atomic); `DELETE`; `GET` list; tool `search_knowledge` no tool registry; Supabase Storage bucket + RLS | Ariel upload manual de 1 PDF real |
| Sem 3 | Admin UI (drag-drop + table + delete); feature flag `rag.enabled` + `rag.top_k` per-tenant; ResenhAI + Ariel rollout shadow->on | ResenhAI upload FAQ real, agente cita chunk em resposta |

**Cut-line**: se sem 2 estourar (provavel: Bifrost extension pra embeddings e mais complexo que estimado), UI da sem 3 vira scripts Python + API apenas — admin frontend vira 012.1. Valor user-facing (agente responde com contexto do tenant) sobrevive sem UI graca API + CLI.

## Dependencies

Prerrequisitos (todos `shipped` ou em curso):

- **006-production-readiness** — schema isolation (`prosauai` schema), migration runner fail-fast, retention cron. Novas tabelas herdam o pattern. Supabase pgvector extension precisa ser habilitada — ja disponivel na instancia (Supabase managed).
- **008-admin-evolution** — admin Next.js 15 + pool_admin BYPASSRLS + TanStack Query + shadcn/ui. UI de upload vira nova aba "Base de Conhecimento" ou adendo a aba "Agentes". Endpoints admin reusam auth + pool existente.
- **013-agent-tools-v2 (futuro)** — `tools/registry.py` ja existe (desde epic 005), foi esvaziado pre-epic 010 mas **mantido como scaffold**. Epic 012 vai adicionar `search_knowledge` como **1o tool real do registry**, antes de 013 oficialmente acontecer. Zero dependencia bloqueante.
- **005-conversation-core** — pipeline 14 steps, agent pydantic-ai, tool calling ja suportado nativamente. Step `agent.generate` hoje chama LLM sem tools; epic 012 popula `tools_enabled=['search_knowledge']` no agent config.

**Pre-requisitos que NAO bloqueiam** mas sao considerados:

- **011-evals (em_curso)** — quando epic 011 em shadow produzir scores, epic 012 pode usar golden curation pra medir impacto antes/depois do RAG. Nao bloqueia entrega.
- **Bifrost extension** — hoje Bifrost so roteia `/v1/chat/completions`. Precisa adicionar roteamento pra `/v1/embeddings`. Config + provider adapter. Estimativa 2-3 dias.

ADRs novos desta epic (draft — promocao pode ajustar):

- **ADR-041** — Document lifecycle: replace by source_name (sem versionamento em v1)
- **ADR-042** — Bifrost extension para embeddings (`/v1/embeddings` endpoint roteado)

ADRs estendidos (nao substituidos):

- **ADR-013** pgvector-tenant-knowledge — **materializado**. Schema expandido com tabela `documents` (nova) + colunas `document_id`, `embedding_model`, `chunk_index` em `knowledge_chunks`.
- **ADR-011** pool-rls-multi-tenant — `knowledge_chunks` + `documents` ambas com RLS + policy tenant_isolation + index tenant_id obrigatorio.
- **ADR-012** consumption-billing — embedding cost por tenant vira dado de billing via Bifrost spend tracking.
- **ADR-018** data-retention-lgpd — SAR cascadeia `documents` -> `knowledge_chunks` + DELETE Supabase Storage raw. Endpoint `/api/v1/sar/{customer_id}` nao afetado (customer_id != tenant_id).
- **ADR-025** gpt-5.4-mini default — inalterado. Embedding model independente: `text-embedding-3-small`.

Dependencias externas:

- **OpenAI `text-embedding-3-small`** — custo $0.00002/1K tokens (~R$0.0001 por chunk de 512 tokens). 1536 dim eval ADR-013 schema.
- **Supabase Storage** — bucket `knowledge` ja provisonavel (managed). Custo ~R$0.10/GB/mes.
- **PyMuPDF** — **ja e dependencia** do epic 009 (content processing para PDFs em mensagens). Reusa.

## Captured Decisions

| # | Area | Decisao | Referencia |
|---|------|---------|-----------|
| 1 | Formatos v1 | **MD + text + PDF** apenas. DOCX/URL crawl adiados para 012.1. PDF reusa PyMuPDF do epic 009. | Q1-A (epic-context draft 2026-04-24) |
| 2 | Embedding provider | **OpenAI `text-embedding-3-small` (1536 dim) via Bifrost extension**. Alinhado com schema ADR-013 (`VECTOR(1536)`). Custo ~R$0.0001/chunk. | Q2-A; ADR-013 confirmed; ADR-042 novo |
| 3 | Chunking strategy | **Markdown header-aware** para `.md` (chunka em `##`/`###`); **fixed-size 512 tokens + 50 overlap** para PDF/text. Sem LangChain. Implementacao stdlib <100 LOC. | Q3-B |
| 4 | Retrieval integration | **RAG como tool opcional** — `search_knowledge(query: str, top_k: int=5)` registrado em `tools/registry.py`. LLM decide quando chamar. Agentes com KB tem `tools_enabled=['search_knowledge']`. | Q4-B; blueprint `tools/registry.py` |
| 5 | Scope do KB | **Per-tenant default** (`agent_id IS NULL = shared`). `agent_id` opcional em chunks permite filtrar para agente especifico se tenant quiser. Schema ADR-013 ja acomoda. | Q5-B; ADR-013 |
| 6 | Upload UX | **Sync upload** ate 10MB. Chunk count tipico <200, embedding paralelo ~10s. Usuario aguarda e ve resultado inline. Async queue adiada para 012.1 (precisa ARQ worker). | Q6-A |
| 7 | Document lifecycle | **Replace by source_name** (atomic transaction): upload com `source_name` existente -> DELETE chunks antigos + DELETE Storage + INSERT novo document + chunks. Sem versionamento em v1. | Q8-I-A; ADR-041 novo |
| 8 | Raw file storage | **Supabase Storage bucket `knowledge`** path `{tenant_id}/{document_id}.{ext}`. Permite re-chunking/re-embedding futuro sem exigir re-upload do tenant. | Q8-II-A |
| 9 | Re-embedding | **Via Supabase Storage reprocess** — quando upgrade de modelo ou mudanca de chunker, CLI `python -m prosauai.rag.reembed --tenant X` le raw do Storage e re-embeda. Zero acao do tenant. Coluna `embedding_model TEXT NOT NULL` em `knowledge_chunks` para audit + query isolation. | Q7 resolved by Q8-II-A |
| 10 | Schema — nova tabela documents | `documents(id UUID PK, tenant_id, source_name, source_hash, source_type, storage_path, size_bytes, uploaded_by_user_id, uploaded_at, chunks_count, embedding_model, UNIQUE(tenant_id, source_name))`. RLS tenant_isolation. | ADR-011 + ADR-013 extended |
| 11 | Schema — knowledge_chunks expansao | ADR-013 schema + novas colunas: `document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE`, `chunk_index INT NOT NULL`, `embedding_model TEXT NOT NULL`. Cascade delete simplifica lifecycle. | ADR-013 extended |
| 12 | HNSW index params | `hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)` ja decidido em ADR-013. Query `embedding <=> $query_vector` (cosine distance). | ADR-013 confirmed |
| 13 | Retrieval params | Default `top_k=5`, distance threshold nao aplicado em v1 (retorna sempre top-5 mesmo que distantes — LLM filtra no contexto). Threshold `rag.min_distance_threshold` per-tenant em `tenants.yaml` para 012.1. | Q4-B; simplicity-first |
| 14 | Bifrost extension | Bifrost ganha config de provider OpenAI para `/v1/embeddings`. Mesmo pattern de rate limiting + spend tracking do chat completions. `prosauai/rag/embedder.py` faz POST para Bifrost, nao direto na OpenAI. | ADR-042 novo; ADR-012 billing |
| 15 | Feature flag | **`tenants.yaml` bloco `rag: {enabled: bool, top_k: int, min_distance: float?, max_upload_mb: int}`** per-tenant. Default `enabled: false`. Config_poller do epic 010 re-le em <=60s. | pattern epic 010 |
| 16 | Rollout per-tenant | **Ariel `disabled -> enabled` com 1 FAQ MD curto (smoke)** -> ResenhAI 7d depois com catalogo PDF real. Sem shadow mode — RAG ligado = agente pode usar tool. Validacao e se tool e efetivamente chamada e resposta usa o chunk. | simplificado vs 010/011 |
| 17 | Admin UI | **Nova aba "Base de Conhecimento"** no sidebar admin (ou adendo em Agentes). Tabela: source_name, source_type, chunks_count, size, uploaded_at, actions (download original, delete). Upload dialog drag-drop + file picker. | epic 008 extension |
| 18 | Privacy / LGPD | `DELETE /admin/knowledge/documents/{id}` faz cascade (DB + Storage). SAR endpoint (ADR-018) estendido para listar `documents` do tenant. Cross-tenant embedding explicitamente proibido via RLS. | ADR-018 extended |
| 19 | Tool call observability | `search_knowledge` tool execucao vira span OTel `rag.search` no trace. Atributos: `rag.query_tokens`, `rag.chunks_returned`, `rag.distance_top1`, `rag.cost_usd`. Aparece no Trace Explorer do epic 008. | pattern epic 002 |
| 20 | Eval integration | Quando tool e chamada, fact "response used RAG" marca `eval_scores.details.rag_used=true`. Epic 011 pode correlacionar RAG vs quality. | epic 011 hook |
| 21 | Re-index strategy | Sem re-index periodico HNSW (ADR-013 decidiu HNSW justamente pra evitar isso). `ANALYZE` em nightly cron reuse do retention-cron (epic 006). | ADR-013 |
| 22 | Prompt injection surface | Chunks retornados pelo RAG **podem conter instrucoes injetadas** (risco OWASP #1 RAG injection — ver ADR-016). Safety Layer A do epic 005 valida chunks antes de enviar pro LLM (sandwich pattern). Em v1 confia em ADR-016 existente; hardening especifico de RAG em 012.1. | ADR-016 extended |

## Resolved Gray Areas

Decisoes tomadas durante este epic-context draft (2026-04-24):

1. **Formatos (Q1)** — MD + text + PDF. DOCX/URL crawl adiados. Risco de atrito aceito: tenant converte PDF/DOCX no site de sua escolha antes (modo 2026 — qualquer AI converte).
2. **Embedding provider (Q2)** — OpenAI via Bifrost. Custo desprezivel (~R$0.10/tenant onboarding completo). BGE self-hosted rejeitado: quebraria schema ADR-013 (1024 dim != 1536) + nova infra.
3. **Chunking (Q3)** — Header-aware MD + fixed PDF/text. Semantic chunking rejeitado: complexidade + vendor lock sem ganho proporcional.
4. **Retrieval integration (Q4)** — RAG as tool. Retrieval automatico em toda msg rejeitado: custo/ruido em msgs triviais ("oi") + risco de hallucination. Alinha com 013 Agent Tools v2.
5. **Scope KB (Q5)** — Per-tenant com `agent_id` opcional. Per-agent strict rejeitado: duplica docs comuns + UX complexo. Per-tenant only rejeitado: sem flex futura.
6. **Upload UX (Q6)** — Sync <=10MB. Async ARQ rejeitado: puxa componente proprio de epic; BackgroundTasks FastAPI rejeitado: nao persistente em restart.
7. **Document lifecycle (Q8-I)** — Replace by source_name. Versionamento rejeitado: overengineering para PME; diff-based rejeitado: complexidade enorme por ganho minimo (re-embed total custa R$0.005).
8. **Raw storage (Q8-II)** — Supabase Storage. "So chunks" rejeitado: amarra em decisoes de chunking. "raw_content TEXT" rejeitado: perde layout original.
9. **Re-embedding model change (Q7)** — Resolvido via Q8-II: reprocess do raw no Storage; zero acao do tenant.
10. **Agent tools_enabled toggle** — quando `rag.enabled=true` no tenant, admin tem toggle per-agente para adicionar `search_knowledge` em `tools_enabled`. Nem todo agente do tenant precisa usar RAG (ex: agente de onboarding pode nao precisar).
11. **Tool usage visibility** — admin ve no Trace Explorer se tool foi chamada em cada msg (span `rag.search` existe ou nao).
12. **Downtime behavior** — Bifrost /embeddings down: upload falha com erro claro. OpenAI direto rate-limit: retry exponencial 3x. Retrieval em runtime down: tool retorna `[]` (lista vazia) + log warning — agente responde sem contexto ao inves de quebrar pipeline.

## Applicable Constraints

**Do blueprint** ([engineering/blueprint.md](../../engineering/blueprint.md)):

- Python 3.12, FastAPI, asyncpg, httpx, structlog — **zero libs novas em Python**. PyMuPDF ja existe (epic 009).
- Supabase PG 15 + pgvector extension disponivel.
- NFR Q1 (p95 <3s) — RAG como tool adiciona 1 LLM turn (tool decision + retrieval + resposta). Budget: 1-1.5s extra apenas quando tool e chamada. Msgs sem tool call: zero impacto.
- NFR Q3 (zero cross-tenant leak) — RLS em `knowledge_chunks` + `documents` + Storage path com tenant_id no prefixo + policy Supabase Storage.
- NFR Q8 (retention) — documents + chunks participam do cron de retention; default sem expiracao (tenant decide).
- ADR-011 RLS — obrigatorio, sem excecao.
- ADR-013 pgvector — schema base. Pretty much direct use.
- ADR-016 agent safety — Layer A regex roda em chunks retornados pelo RAG (RAG injection mitigation).
- ADR-018 LGPD — SAR + cascade delete.
- ADR-027 admin-tables-no-rls — **NAO se aplica** aqui — `documents` e `knowledge_chunks` tem `tenant_id` direto e sao tenant-scoped, nao admin-only. Ficam em schema `prosauai` com RLS.
- ADR-028 fire-and-forget — **nao aplica** no upload (admin aguarda resultado sync). Aplica em telemetria downstream (span persist).

**Do epic 008** ([epics/008-admin-evolution/](../008-admin-evolution/)):

- Next.js 15 App Router + TanStack Query v5 + shadcn/ui + Tailwind v4.
- Pool_admin BYPASSRLS para listar documents cross-tenant se needed (admin Pace monitora todos).
- OpenAPI 3.1 em `contracts/openapi.yaml` — novos endpoints geram tipos via `pnpm gen:api`.
- Dark mode unico.

**Do epic 010** ([epics/010-handoff-engine-inbox/](../010-handoff-engine-inbox/)):

- Feature flag shape `tenants.yaml` com `handoff.mode` como referencia. `rag.enabled` segue convencao.
- Config_poller <=60s hot reload.

**Do epic 011** (em curso):

- Schema pattern de admin tables + tenant-scoped coexistindo no mesmo schema.

## Suggested Approach

Dividir em **3 PRs sequenciais mergeaveis em develop**, cada um reversivel via `rag.enabled: false`:

### PR-A (semana 1) — Schema + embedder + chunker

1. Habilitar extension pgvector no Supabase (operacao ops manual: `CREATE EXTENSION vector;` via SQL editor).
2. Migration nova: `CREATE TABLE documents (...)` + `CREATE TABLE knowledge_chunks (...)` (refletindo ADR-013 + expansoes) + RLS policies + indexes + HNSW.
3. Migration Supabase Storage: CLI cria bucket `knowledge` com policy tenant-based.
4. `prosauai/rag/__init__.py` novo modulo:
   - `embedder.py` — cliente Bifrost `/v1/embeddings`, batch de ate 100 textos por call, retry 3x.
   - `chunker.py` — MD header-aware + fixed-size fallback, stdlib only, <100 LOC + testes.
   - `extractor.py` — PDF via PyMuPDF (reuse do epic 009 content processor), MD/text passthrough.
5. Bifrost config extension (arquivo Go config + reload): adicionar provider OpenAI embeddings. Testar localmente.
6. Testes unit: chunker edge cases (MD aninhado, PDF multi-pagina, text sem quebra), embedder retry, extractor formatos.
7. Sem deploy em prod; smoke local.

### PR-B (semana 2) — API admin + Supabase Storage + tool

1. `POST /admin/knowledge/documents` multipart/form-data:
   - valida formato + size;
   - upload raw Storage;
   - transaction: DELETE old chunks/document/storage se source_name existe + INSERT novo + chunks;
   - retorna `{document_id, chunks_created, total_tokens, cost_usd}`.
2. `DELETE /admin/knowledge/documents/{id}` — cascade.
3. `GET /admin/knowledge/documents` — lista paginada com filtros `?tenant=...`.
4. `GET /admin/knowledge/documents/{id}/raw` — redirect signed URL Supabase Storage para download.
5. `prosauai/tools/search_knowledge.py`:
   - Pydantic schema `SearchKnowledgeInput(query: str, top_k: int = 5)`.
   - Registra em `tools/registry.py` como `@register_tool("search_knowledge")`.
   - Executa SELECT cosine distance com LIMIT top_k, retorna lista de chunks + metadata.
   - Server-side `tenant_id + agent_id` injection (ADR-011).
6. Agents table: admin pode marcar `tools_enabled=['search_knowledge']` via endpoint existente do epic 008.
7. `tenants.yaml` schema: `rag: {enabled, top_k, max_upload_mb}`.
8. Testes integration: upload real de MD pequeno, verify chunks insertidos + Storage file existe + tool retorna match.
9. Ariel smoke upload manual de 1 FAQ MD (via curl ou Insomnia).

### PR-C (semana 3) — Admin UI + rollout

1. Sidebar admin: nova aba "Base de Conhecimento" (icon BookOpen lucide).
2. Pagina lista: tabela shadcn Table com source_name, source_type (badge), chunks_count, size, uploaded_at, actions menu.
3. Upload dialog: drag-drop zone + file picker + formato/size validation client-side + progress spinner + resposta inline.
4. Delete confirmacao modal.
5. Download original via link (signed URL).
6. Agents tab: toggle "RAG enabled" por agente (adiciona/remove `search_knowledge` de `tools_enabled`).
7. Tipos gerados: `pnpm gen:api` -> commit.
8. Playwright smoke: upload file, verify tabela atualizou; toggle RAG em agente; mandar msg, verify agente usou tool (via trace).
9. ResenhAI rollout: upload FAQ real de comunidade de futevolei; medir se agente cita chunk em respostas reais.
10. Docs: README curto no admin "como usar base de conhecimento"; runbook ops (reembed CLI).

### Invariantes obrigatorios

- **Atomic replace** — upload com `source_name` existente e all-or-nothing. Falha de embedding no meio = rollback total (DB + Storage).
- **Tenant isolation** — knowledge_chunks.tenant_id = documents.tenant_id = Storage path tenant_id. Cross-tenant query retorna zero.
- **Tool tenant_id injection server-side** — `search_knowledge` NUNCA confia em `tenant_id` vindo do LLM; runtime injeta via pydantic-ai deps.
- **Embedding model lock-in dentro de tenant** — um tenant tem todos chunks do mesmo `embedding_model`. Re-embed CLI atualiza tudo junto.
- **Feature flag off == zero side effect** — `rag.enabled=false` -> tool nao aparece em `tools_enabled` renderizado; endpoint upload retorna 403.
- **LGPD cascade complete** — SAR delete tenant cascadeia documents + chunks + Storage bucket prefix.

---

> **Proximo passo (quando 011 shipped):** `/madruga:epic-context prosauai 012` (sem `--draft`) para promover — fara delta review contra mudancas ocorridas durante 011 (novos ADRs, schema drift, reframing de escopo) e criara branch `epic/prosauai/012-tenant-knowledge-base-rag`.
