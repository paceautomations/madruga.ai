# Implementation Plan: Tenant Knowledge Base — RAG pgvector + Upload Admin

**Branch**: `epic/prosauai/012-tenant-knowledge-base-rag` | **Date**: 2026-04-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `epics/012-tenant-knowledge-base-rag/spec.md`

## Summary

Materializa o que ADR-013 prometeu ha 6 semanas: tabelas `documents` + `knowledge_chunks` (pgvector + HNSW) com RLS per-tenant, extensao Bifrost para `/v1/embeddings` (OpenAI `text-embedding-3-small`, 1536 dim), API admin `/admin/knowledge/documents` (upload sync ate 10MB com replace-by-source_name atomico), tool `search_knowledge` no `tools/registry.py` (primeiro tool real do registry pos-epic 010, com server-side `tenant_id`/`agent_id` injection via pydantic-ai deps), feature flag `rag.{enabled,top_k,max_upload_mb,max_documents_per_tenant,max_chunks_per_tenant}` per-tenant em `tenants.yaml` com hot-reload <=60s via config_poller (epic 010), CLI re-embed para upgrades de modelo futuros (raw preservado em Supabase Storage), admin UI nova aba "Base de Conhecimento" no Next.js (epic 008) + toggle per-agente em "Agentes". Escopo v1 deliberadamente enxuto: MD/text/PDF (PyMuPDF reuse epic 009), sem versionamento, sem distance threshold, sem dedup automatica. Reversivel via `rag.enabled: false` em <=60s sem deploy. 3 PRs sequenciais mergeaveis em `develop`, cada um com kill-switch independente. Custo embedding ~R$0.0001/chunk (~R$0.10 por tenant onboarding completo).

## Technical Context

**Language/Version**: Python 3.12 (backend, FastAPI), TypeScript 5.x (admin Next.js 15 App Router), Go 1.22+ (Bifrost extension config + adapter)
**Primary Dependencies**:
- Backend: FastAPI >=0.115, pydantic 2.x, pydantic-ai >=1.70, asyncpg >=0.30 (com pgvector 0.8.x via SQL-side, sem driver py extra), httpx, structlog, redis[hiredis] >=5.0, **tiktoken** (ja dependencia epic 005), **PyMuPDF** (ja dependencia epic 009 — content processor reuse)
- OTel: `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-instrumentation-asyncpg` (todos ja epic 002)
- Admin: Next.js 15 App Router + shadcn/ui + Tailwind v4 + TanStack Query v5 + openapi-typescript (dev) + lucide-react (todos ja epic 008)
- Bifrost (Go): proxy/gateway interno (epic 005). Estende config TOML com novo provider OpenAI para `/v1/embeddings`. Reusa pattern de chat completions para rate limit + spend tracking + circuit breaker.
- Zero libs novas em Python ou TypeScript. **Apenas `tiktoken` e `PyMuPDF` reusados (ja em `pyproject.toml`).**

**Storage**:
- PostgreSQL 15 (Supabase managed) com extension `vector` (pgvector >=0.8). 2 novas tabelas em schema `prosauai`: `documents` (raw metadata + storage path) e `knowledge_chunks` (text + embedding VECTOR(1536) + metadata). HNSW index sobre `embedding vector_cosine_ops` (m=16, ef_construction=64). RLS ativo em ambas (policy `tenant_isolation` herdada ADR-011).
- Supabase Storage bucket `knowledge` para raw files. Path: `knowledge/{tenant_id}/{document_id}.{ext}`. Policy restrita ao service-role da Pace.
- Redis 7 (existente) — sem uso novo. Embeddings sao computadas sync no upload (sem cache em v1; latencia da OpenAI ja < 500ms para 100 textos batch).

**Testing**:
- pytest >=8.0 (existente) + pytest-asyncio + hypothesis (chunker property tests) + respx (mocks Bifrost)
- Playwright (admin UI smoke — existente epic 008)
- Coverage gate: 85% para modulos novos (`prosauai/rag/*`, `prosauai/tools/search_knowledge.py`)

**Target Platform**: Linux server (Docker compose para api + admin; Bifrost ja em prod). Supabase managed PG + Storage. OpenAI API (via Bifrost) external dependency.

**Project Type**: Web service (backend FastAPI + frontend Next.js admin) com extensao em proxy Go (Bifrost).

**Performance Goals**:
- Upload p95 <=15s para arquivos <=10MB (chunk count tipico <=200 + embedding paralelo via batch 100/call) — **SC-003**
- Tool `search_knowledge` p95 <=2s (1 embed call Bifrost + 1 SELECT cosine HNSW) — **SC-004**
- Admin GET documents list p95 <500ms para datasets ate 1k docs/tenant — **FR-018**
- HNSW recall@5 >=0.95 com `ef_search=40` (default pgvector). Tunable per-query se necessario.
- Bifrost spend tracking accuracy <=2% diff vs invoice OpenAI — **SC-010**

**Constraints**:
- **NFR Q1 (latencia pipeline)**: agent.generate p95 <3s overall (existente). RAG como tool adiciona 1 turn LLM (decision + retrieval + resposta final). Budget 1-1.5s extra **apenas quando tool e chamada**. Msgs sem tool call (ex.: "oi", "obrigado"): zero impacto. Msgs com tool: target p95 <5s end-to-end.
- **NFR Q3 (zero cross-tenant leak)**: RLS em `knowledge_chunks` + `documents` + Storage path com tenant_id no prefixo + policy Supabase Storage + server-side injection de `tenant_id` no tool (defesa em profundidade). Test invariant noturno verificando.
- **NFR Q8 (retention LGPD)**: documents + chunks participam do cron de retention; default sem expiracao automatica (tenant decide). SAR delete cascadeia DB + Storage prefix.
- **Chunker stdlib + tiktoken only**, <100 LOC funcional (FR-025). Sem LangChain.
- **Atomic-replace by source_name**: upload com nome existente = transaction unica (DELETE chunks + Storage + document antigo + INSERT novos). Falha em qualquer step rollback total. `pg_advisory_xact_lock(hashtext('doc:{tenant_id}:{source_name}'))` serializa concorrentes.
- **Server-side tool injection mandatorio**: `search_knowledge` recebe so `query`/`top_k` do LLM. `tenant_id`/`agent_id`/`embedding_model` injetados via pydantic-ai `RunContext[ConversationDeps]`. SQL parameter binding obrigatorio (asyncpg `$1, $2, ...`).
- **Safety Layer A (epic 005, ADR-016)** roda em cada chunk antes de envio ao LLM (mitigacao OWASP #1 RAG injection). Chunk reprovado descartado com log `rag_chunk_rejected`.
- **Bifrost extension complexity**: estimativa 2-3 dias. Cut-line se exceder: PR-A continua usando OpenAI direto temporariamente (sem rate limit/spend tracking) ate Bifrost pronto. SC-010 sacrificavel temporariamente.
- **Hard caps server-side independentes de config**: `max_chunks_per_tenant <= 50000` mesmo via override (proteje HNSW perf), `top_k <= 20` clampado (evita custo + ruido).

**Scale/Scope**:
- v1 target: ate 50 documentos por tenant, ~1000-2000 chunks por tenant. 2 tenants em rollout (Ariel + ResenhAI). HNSW handle facilmente neste volume.
- v1 limites configuraveis (defaults generosos): 200 docs / 10000 chunks per tenant. Override per-tenant em `tenants.yaml` para enterprise.
- Hard cap absoluto: 50000 chunks/tenant + 2000 chunks/document.
- Re-embed CLI lida com tenants ate ~10k chunks em <30 min (batch 100 textos/call Bifrost).
- Volume mensal projetado: <50 uploads/dia agregado em prod. <10k tool calls/dia agregado. Bifrost embeddings throughput previsto <1k req/min (longe do rate limit OpenAI 3500 req/min).
- Codigo novo backend: ~800 LOC Python (rag/embedder + chunker + extractor + reembed CLI + tool + admin endpoints + migration + tests). Frontend: ~600 LOC TS (nova aba KB + dialog upload + toggle agente). Bifrost: ~150 LOC Go config + adapter.

## Constitution Check

Evaluacao contra constitution v1.1.0 — 9 princípios.

| Princípio | Status | Justificativa |
|-----------|--------|---------------|
| **I. Pragmatism Above All** | PASS | Reusa PyMuPDF (epic 009), tiktoken (epic 005), pool_admin (epic 008), config_poller (epic 010), Safety Layer A (epic 005), Bifrost (epic 005). Zero novas libs Python/TS. Chunker stdlib <100 LOC. Sem LangChain. |
| **II. Automate Repetitive Tasks** | PASS | CLI `python -m prosauai.rag.reembed` automatiza upgrade de modelo (US-5). Replace-by-source_name automatiza atualizacao de FAQ (vs versionamento manual). Config_poller automatiza hot-reload de feature flag. |
| **III. Structured Knowledge** | PASS | Decisoes capturadas em pitch.md (22) + spec.md (Sessions 2026-04-24 + 2026-04-26). 2 novos ADRs propostos (ADR-041 replace-by-source_name, ADR-042 Bifrost embeddings extension). 4 ADRs estendidos (013, 011, 012, 018). |
| **IV. Fast Action Over Excessive Planning** | PASS | 3 PRs sequenciais mergeaveis em `develop`, cada um <1 semana. PR-A entrega schema + chunker + embedder testaveis isoladamente. PR-B entrega tool + API admin (smoke manual de upload em Ariel). PR-C entrega UI + rollout. Cut-line: se PR-B estourar, UI vira 012.1 (valor backend ja ship). |
| **V. Alternatives and Trade-offs** | PASS | Spec capturou alternativas para cada decisao: Pinecone vs pgvector (ADR-013); BGE vs OpenAI embeddings (rejeitado por dim mismatch); semantic vs MD-aware vs fixed-size chunking (escolhido hibrido); RAG-as-tool vs auto-retrieval (escolhido tool); ARQ async vs sync upload (escolhido sync); versionamento vs replace (escolhido replace, ADR-041 novo). |
| **VI. Brutal Honesty** | PASS | Pitch lista cut-line explicito: PR-C (UI) sacrificavel se PR-B estourar — vira 012.1 com CLI/API only. Bifrost extension cut-line: chamada direta OpenAI temporaria se >1 semana. PR-A sem deploy em prod. SC-010 (Bifrost spend accuracy) explicitamente sacrificavel temporariamente. Riscos chamados: prompt injection (mitigado por Safety Layer A em v1, hardening especifico adiado para 012.1); HNSW perf >10k chunks/tenant (re-tune `m`/`ef_construction` em epic futuro). |
| **VII. Test-Driven Development** | PASS | Plano explicita TDD para PR-A: chunker unit tests primeiro (property-based via hypothesis para edge cases MD aninhado, PDF multi-pagina, text sem quebra), embedder retry tests via respx, extractor format tests. PR-B: integration tests upload real (testcontainers PG + bucket mock), tool tests com pydantic-ai test fixtures. PR-C: Playwright smoke (upload, delete, toggle agente, send message + verify trace). Coverage gate 85% modulos novos. |
| **VIII. Collaborative Decision Making** | PASS | Spec pediu 22 decisoes em pitch + 5 clarifications session — todas com alternativas. Decisoes escaladas: ADR-041 e ADR-042 promovidos como decisoes formais (1-way-door — embedding model switch e replace strategy sao schema-coupled). |
| **IX. Observability and Logging** | PASS | structlog em todas operacoes (FR-076: 5 event_types canonicos: `knowledge_document_uploaded/deleted/downloaded`, `knowledge_search_executed`, `knowledge_document_replace_detected`). Spans OTel: `rag.search`, `rag.embed`, `tool_call.search_knowledge` (FR-029, FR-039, FR-065). Metricas Prometheus: `rag_documents_uploaded_total`, `rag_chunks_total`, `rag_search_invocations_total`, `rag_search_duration_seconds_bucket`, `rag_embedder_failures_total`, `rag_uploads_rejected_total{reason}` (FR-063 + SC-011). Trace Explorer (epic 008) renderiza spans. Eval scoring (epic 011) recebe `details.rag_used=true`. |

**Veredicto**: Pass. Zero violacoes. Nenhuma justificativa requerida em Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/012-tenant-knowledge-base-rag/
├── pitch.md             # Shape Up pitch (existente — drafted 2026-04-24)
├── spec.md              # Feature specification (existente — clarified 2026-04-26)
├── plan.md              # Este arquivo
├── research.md          # Phase 0 output — decisoes resolvidas (a maioria ja em pitch+spec)
├── data-model.md        # Phase 1 output — entidades + diagramas
├── quickstart.md        # Phase 1 output — passo-a-passo de smoke test
├── contracts/
│   ├── openapi.yaml     # Phase 1 — endpoints admin /admin/knowledge/*
│   ├── tool-schema.json # Phase 1 — schema function-calling de search_knowledge
│   └── tenants-yaml-schema.json # Phase 1 — bloco rag em tenants.yaml
├── decisions.md         # Cumulative micro-decisoes (epic-context seed + implement updates)
└── tasks.md             # Phase 2 output (criado por /speckit.tasks)
```

### Source Code (external repo `paceautomations/prosauai`)

> **Self-ref check**: platform `prosauai` tem `repo.name=prosauai`, repo.org=`paceautomations`. Codigo vive em `/home/gabrielhamu/repos/paceautomations/prosauai/`, **nao** em madruga.ai. Branch `epic/prosauai/012-tenant-knowledge-base-rag` checked out via `ensure_repo.get_repo_work_dir`.

Layout do repo `prosauai` (monorepo pnpm; backend Python em `apps/api/`, admin Next.js em `apps/admin/`):

```text
apps/api/
├── prosauai/
│   ├── rag/                          # NOVO modulo — toda logica RAG
│   │   ├── __init__.py
│   │   ├── embedder.py               # Cliente Bifrost /v1/embeddings (~80 LOC)
│   │   ├── chunker.py                # MD-aware + fixed-size, stdlib+tiktoken (~90 LOC)
│   │   ├── extractor.py              # PDF (PyMuPDF reuse) + MD/TXT passthrough (~60 LOC)
│   │   ├── reembed.py                # CLI python -m prosauai.rag.reembed (~150 LOC)
│   │   ├── storage.py                # Wrapper Supabase Storage SDK / REST (~70 LOC)
│   │   └── repository.py             # SQL CRUD para documents + chunks (~120 LOC)
│   ├── tools/
│   │   ├── registry.py               # Existente — adiciona search_knowledge via decorator
│   │   └── search_knowledge.py       # NOVO — pydantic schema + executor (~80 LOC)
│   ├── admin/
│   │   ├── knowledge.py              # NOVO router /admin/knowledge/* (~200 LOC)
│   │   └── router.py                 # Existente — include knowledge.router
│   ├── pipeline/steps/
│   │   └── agent_generate.py         # Modificacao: tools dinamicas com filtro feature-flag
│   ├── safety/
│   │   └── input_guard.py            # Existente — extender para validar chunks RAG
│   ├── config_poller.py              # Existente — schema valida bloco rag
│   ├── observability/
│   │   └── metrics.py                # Adicionar rag_* counters/histograms
│   └── privacy/
│       └── sar.py                    # Existente — extender SAR para listar+deletar documents
├── db/migrations/
│   ├── 20260601000006_create_pgvector_extension.sql      # CREATE EXTENSION (idempotente)
│   ├── 20260601000007_create_documents.sql               # tabela documents + RLS + indexes
│   ├── 20260601000008_create_knowledge_chunks.sql        # tabela knowledge_chunks + HNSW + RLS
│   └── 20260601000009_create_knowledge_storage_bucket.sql # CALL via supabase CLI / SQL
├── config/
│   └── tenants.example.yaml          # Adicionar exemplo de bloco rag
└── tests/
    ├── rag/
    │   ├── test_chunker.py           # property-based hypothesis
    │   ├── test_embedder.py          # respx mocks Bifrost
    │   ├── test_extractor.py         # fixtures PDF/MD/TXT
    │   ├── test_repository.py        # testcontainers PG + RLS isolation tests
    │   └── test_reembed_cli.py       # subprocess + mock provider
    ├── tools/
    │   └── test_search_knowledge.py  # pydantic-ai test fixtures + tenant injection
    ├── admin/
    │   └── test_knowledge_routes.py  # httpx TestClient + Storage mock
    ├── safety/
    │   └── test_input_guard_rag.py   # chunks com prompt injection
    └── integration/
        └── test_rag_e2e.py           # upload + tool call + verify chunks retornados

apps/admin/
├── src/app/admin/(authenticated)/
│   ├── knowledge/                    # NOVO route group
│   │   ├── page.tsx                  # Tabela documents
│   │   ├── upload-dialog.tsx         # Drag-drop + file picker (~150 LOC)
│   │   ├── delete-dialog.tsx         # AlertDialog confirm
│   │   └── document-detail-sheet.tsx # Sheet com primeiros chunks (~100 LOC)
│   └── agents/
│       └── rag-toggle.tsx            # Switch shadcn por agente (~50 LOC)
├── src/components/sidebar.tsx        # Modificacao: adicionar entry "Base de Conhecimento"
├── src/lib/api/knowledge.ts          # TanStack Query hooks (~80 LOC)
└── packages/types/api.ts             # Regenerado via pnpm gen:api a partir do openapi.yaml

# Bifrost extension (repo separado paceautomations/bifrost — gestao ops)
config/providers/openai-embeddings.toml   # Novo provider config
adapters/openai_embeddings.go              # Adapter ~150 LOC
```

**Structure Decision**: web-service (backend FastAPI + frontend Next.js admin). Codigo vive em `paceautomations/prosauai` (external repo, branch `epic/prosauai/012-tenant-knowledge-base-rag`). Bifrost extension em repo separado `paceautomations/bifrost` (gerenciado por ops; PR coordenado mas merge separado). Nao vive nada em `madruga.ai/` alem da documentacao deste epic.

## Phase 0 — Outline & Research

**Status**: Resolvido. Sessions de clarification (2026-04-24 draft + 2026-04-26 clarify) cobriram todos os NEEDS CLARIFICATION da spec. Nenhuma duvida tecnica restante para esta phase.

Decisoes consolidadas em [research.md](./research.md):

1. **Embedding model**: OpenAI `text-embedding-3-small` (1536 dim) via Bifrost extension. Alternativas BGE/Voyage/Cohere documentadas com motivo de rejeicao (dim mismatch + nova infra).
2. **Chunking strategy**: MD header-aware (`##`/`###`) + fixed-size 512 tokens / 50 overlap (PDF/text). Alternativas semantic chunking (LangChain) e recursive text splitter rejeitadas.
3. **Vector index**: HNSW (m=16, ef_construction=64) sobre `vector_cosine_ops`. Alternativa IVFFlat rejeitada (precisa re-index periodico). Alinhado ADR-013.
4. **Storage**: Supabase Storage bucket `knowledge` path `{tenant_id}/{document_id}.{ext}`. Alternativa "raw_content TEXT na tabela" rejeitada (perde layout PDF). Alternativa S3 rejeitada (Supabase ja managed).
5. **Atomic replace**: por `source_name` + transaction unica + advisory lock. Alternativa "versionamento explicit" rejeitada (overengineering v1, ADR-041 novo cobre).
6. **Tool integration**: `search_knowledge` via pydantic-ai function calling, tenant_id server-side injection. Alternativa "auto-retrieval em todo msg" rejeitada (custo+ruido).
7. **Feature flag**: `tenants.yaml` bloco `rag.{enabled, top_k, max_upload_mb, max_documents_per_tenant, max_chunks_per_tenant}` com hot-reload <=60s via config_poller existente.
8. **Bifrost embeddings extension**: novo provider OpenAI no config Bifrost, adapter Go reutiliza pattern de chat completions. ADR-042 novo. Alternativa "OpenAI direto" rejeitada (sem rate limit + sem spend tracking).
9. **Re-embed strategy**: Storage preserve raw -> CLI re-chunka + re-embeda. Alternativa "exigir re-upload do tenant" rejeitada (operacional inviavel).
10. **Quotas**: soft limits per-tenant em `tenants.yaml` (200 docs / 10000 chunks defaults) + hard caps server-side (50000 chunks max, 2000 chunks/doc max).
11. **Audit trail**: structlog estruturado, sem tabela `audit_log` dedicada em v1. 5 event_types canonicos + campos obrigatorios. Alternativa "tabela audit_log SQL" promovida para 012.1 se compliance externa exigir.
12. **Span retention em delete**: append-only spans seguem retention epic 002 (90d). Trace Explorer renderiza "(deleted)" gracefully. Alternativa "cascade FK cross-table" rejeitada (nao escala).

**Output**: [research.md](./research.md) consolida decisoes + alternativas + rationale.

## Phase 1 — Design & Contracts

**Prerequisites**: research.md complete (above).

### 1.1 Data Model

[data-model.md](./data-model.md) detalha:

- **Document**: tabela `documents` com `id, tenant_id, source_name, source_hash, source_type, storage_path, size_bytes, uploaded_by_user_id, uploaded_at, chunks_count, embedding_model`. UNIQUE(tenant_id, source_name). RLS tenant_isolation. Indexes: pk, unique, (tenant_id, uploaded_at DESC).
- **KnowledgeChunk**: tabela `knowledge_chunks` com `id, tenant_id, agent_id (NULL=shared), document_id (FK CASCADE), chunk_index, content, tokens, embedding VECTOR(1536), embedding_model, metadata JSONB, created_at`. RLS tenant_isolation. Indexes: pk, HNSW vector_cosine_ops, (tenant_id, agent_id), (document_id, chunk_index).
- **TenantRagConfig**: bloco YAML em `tenants.yaml`. Pydantic model `RagConfig(enabled: bool, top_k: int = 5, max_upload_mb: int = 10, max_documents_per_tenant: int = 200, max_chunks_per_tenant: int = 10000, min_distance_threshold: float | None = None)`. Validators: ranges, hard caps.
- **AgentToolEnabled**: existente `agents.tools_enabled JSONB array`. Recebe `'search_knowledge'` como primeiro real tool pos-epic 010. Toggle via PATCH endpoint epic 008.
- **State transitions**: Document tem 1 estado terminal (uploaded). Replace = DELETE + INSERT em transaction (sem in-place update). Delete = DELETE cascade.
- **Validation rules**: `size_bytes >= 1` (FR-074), `source_type IN ('md','txt','pdf')` (CHECK constraint), chunks_count >= 1 enforced apos chunking (FR-074), `top_k <= 20` server-side clamp (FR-034), quotas per-tenant (FR-073).

Diagramas Mermaid ER + state machine documentados em data-model.md.

### 1.2 Contracts

[contracts/openapi.yaml](./contracts/openapi.yaml) — OpenAPI 3.1 com endpoints novos:

- `POST /admin/knowledge/documents` — multipart upload (FR-011)
- `GET /admin/knowledge/documents` — list paginated (FR-018)
- `DELETE /admin/knowledge/documents/{id}` — cascade delete (FR-019)
- `GET /admin/knowledge/documents/{id}/raw` — 302 signed URL (FR-020)
- `GET /admin/knowledge/documents/{id}/chunks` — preview (FR-021)
- `PATCH /admin/agents/{id}` — modificar tools_enabled (existente epic 008, doc atualizado)
- `GET /admin/sar/{customer_id}` — extensao para listar documents do tenant (existente ADR-018)

Schemas: `DocumentRecord`, `DocumentUploadResponse`, `DocumentListResponse`, `ChunkPreview`, `ErrorResponse` (com `error` enum: `unsupported_format`, `max_upload_mb_exceeded`, `empty_file`, `rag_not_enabled_for_tenant`, `embeddings_provider_down`, `tenant_quota_exceeded`, `no_chunks_extracted`, `pdf_no_extractable_text`, `pdf_encrypted`).

[contracts/tool-schema.json](./contracts/tool-schema.json) — Function calling schema para `search_knowledge`:

```json
{
  "name": "search_knowledge",
  "description": "Search the tenant knowledge base for relevant chunks...",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "top_k": {"type": "integer", "default": 5, "maximum": 20}
    },
    "required": ["query"]
  }
}
```

Output schema: `[{text: str, source_name: str, source_type: str, distance: float, document_id: str}]`.

[contracts/tenants-yaml-schema.json](./contracts/tenants-yaml-schema.json) — JSON Schema para validacao do bloco `rag` em `tenants.yaml`. Validado pelo config_poller; YAML invalido rejeitado com fail-safe (config anterior permanece).

### 1.3 Quickstart

[quickstart.md](./quickstart.md) — cenario end-to-end testavel:

1. Habilitar `vector` extension no Supabase (1x).
2. Aplicar migrations 20260601000006-009 via dbmate.
3. Criar bucket Supabase Storage `knowledge`.
4. Habilitar Bifrost provider OpenAI embeddings (config TOML).
5. Set `rag.enabled: true` em `tenants.yaml` para Ariel + commit.
6. Aguardar config_poller (<=60s) ou restart api.
7. Upload `faq.md` via admin UI ou curl: `curl -F file=@faq.md /admin/knowledge/documents?tenant_id=...`.
8. Verify: 201 + chunks_count.
9. Toggle `search_knowledge` no agente Ariel via UI.
10. Enviar mensagem "qual o horario de funcionamento?" via WhatsApp simulator.
11. Verify Trace Explorer: span `tool_call.search_knowledge` + `rag.search` com `chunks_returned >= 1`, `distance_top1 < 0.4`.
12. Resposta do agente cita literalmente trecho do FAQ.
13. (Cleanup) DELETE /admin/knowledge/documents/{id} -> verify cascade DB + Storage.

### 1.4 Agent Context Update

Apos gerar Phase 1 artifacts, executar:

```bash
.specify/scripts/bash/update-agent-context.sh claude
```

Atualiza `CLAUDE.md` (project root) com nova tech detectada: tiktoken (ja existente, no-op), PyMuPDF (ja existente, no-op), pgvector (novo!). Adiciona `pgvector 0.8.x` aos Active Technologies.

**Re-evaluate Constitution Check post-design**: PASS. Phase 1 artifacts respeitam todos 9 princípios. Nenhuma violacao introduzida.

**Output**: data-model.md, contracts/*, quickstart.md, agent-specific file atualizado.

## Implementation Strategy (Phase 2 preview — feito por /speckit.tasks)

3 PRs sequenciais conforme pitch:

### PR-A — Schema + chunker + embedder (Sem 1)

**Foco**: data layer + utilities testaveis isoladamente. Sem deploy em prod. Smoke local.

1. Migration 20260601000006: `CREATE EXTENSION IF NOT EXISTS vector;` (idempotente, ops ja confirmou disponivel no plano Supabase).
2. Migration 20260601000007: tabela `documents` + RLS + indexes.
3. Migration 20260601000008: tabela `knowledge_chunks` + RLS + HNSW + secondary indexes.
4. Migration 20260601000009: criacao de bucket via supabase CLI ou script Python (idempotente).
5. `prosauai/rag/extractor.py`: PDF via PyMuPDF (reuse pattern de processors/document.py epic 009), MD/TXT passthrough com normalizacao UTF-8 strict.
6. `prosauai/rag/chunker.py`: MD-aware (parse headers regex) + fixed-size tiktoken cl100k_base (512 tokens, 50 overlap). MIN_CHUNK_TOKENS=10. Hypothesis property tests para edge cases.
7. `prosauai/rag/embedder.py`: cliente httpx para Bifrost `/v1/embeddings`, batch ate 100 textos, retry exponencial 3x (429/503/timeout), span OTel `rag.embed`. Header `X-ProsaUAI-Tenant`. Respx mocks nos tests.
8. `prosauai/rag/repository.py`: CRUD asyncpg para documents + chunks. RLS context manager (ja epic 003). `pg_advisory_xact_lock` helper.
9. Bifrost extension (repo separado): config OpenAI embeddings + adapter Go. PR coordenado mas merge independente.
10. Tests: pytest + hypothesis + respx. Coverage gate 85%.

**Gate**: unit tests verdes + integration test de RLS isolation (cross-tenant SELECT retorna zero). Sem prod.

### PR-B — Tool + admin API + Storage (Sem 2)

**Foco**: API admin upload/delete/list + tool registrada + integracao pipeline. Smoke real em Ariel via curl.

1. `prosauai/rag/storage.py`: wrapper Supabase Storage REST/SDK (httpx). Upload + delete + signed URL.
2. `prosauai/admin/knowledge.py`: router FastAPI com 5 endpoints (FR-011, FR-018, FR-019, FR-020, FR-021). Multipart upload + transaction atomic-replace + advisory lock + quotas (FR-073) + zero-chunk validation (FR-074) + structlog audit (FR-076).
3. `prosauai/tools/search_knowledge.py`: pydantic schema + executor SQL cosine. Server-side `tenant_id`/`agent_id`/`embedding_model` injection via `RunContext[ConversationDeps]`. Span OTel `rag.search`. Graceful degradation em embedder failure.
4. `prosauai/tools/registry.py`: `@register_tool("search_knowledge", ...)`.
5. `prosauai/safety/input_guard.py`: extender para validar chunks RAG (mesma regex/heuristica). Log `rag_chunk_rejected`.
6. `prosauai/pipeline/steps/agent_generate.py`: filtrar tools por feature flag `tenant.rag.enabled` (defesa em profundidade FR-041).
7. `prosauai/config_poller.py`: schema RagConfig + validators. Fail-safe em YAML invalido.
8. `prosauai/privacy/sar.py`: extender para listar + cascade delete documents (FR-066, FR-067).
9. `prosauai/observability/metrics.py`: 6 metricas Prometheus novas (FR-063 + SC-011).
10. `config/tenants.example.yaml`: exemplo do bloco rag.
11. Tests: integration tests upload real (testcontainers PG + Storage mock), tool tests com pydantic-ai TestModel, safety tests com chunks injection, RLS invariant test.
12. Smoke manual: curl upload de FAQ MD pequeno em Ariel staging. Toggle agente. Mensagem teste -> verify trace.

**Gate**: integration tests verdes + smoke Ariel ok + Bifrost spend tracking accuracy validado em curl direto.

### PR-C — Admin UI + rollout (Sem 3)

**Foco**: UI nova aba KB + toggle por agente + rollout produtivo Ariel + ResenhAI.

1. `apps/admin/src/components/sidebar.tsx`: entry "Base de Conhecimento" com icon BookOpen.
2. `apps/admin/src/app/admin/(authenticated)/knowledge/page.tsx`: tabela shadcn + filtros + actions menu.
3. `apps/admin/src/app/admin/(authenticated)/knowledge/upload-dialog.tsx`: drag-drop + file picker + validacao client-side + spinner + resposta inline.
4. `apps/admin/src/app/admin/(authenticated)/knowledge/delete-dialog.tsx`: AlertDialog confirm.
5. `apps/admin/src/app/admin/(authenticated)/knowledge/document-detail-sheet.tsx`: Sheet com metadata + primeiros 10 chunks.
6. `apps/admin/src/app/admin/(authenticated)/agents/rag-toggle.tsx`: Switch shadcn por agente. Greyed out se tenant.rag.enabled=false.
7. `apps/admin/src/lib/api/knowledge.ts`: TanStack Query hooks.
8. `pnpm gen:api` -> `packages/types/api.ts` regenerado.
9. `prosauai/rag/reembed.py`: CLI Python para upgrade de modelo (US-5). Subprocess tests + mock provider.
10. Playwright smoke: upload, delete, toggle, mensagem -> trace.
11. Docs: README curto admin UI; runbook ops para reembed CLI.
12. Rollout: Ariel `disabled -> enabled` com 1 FAQ MD (smoke 24h) -> ResenhAI 7d depois com FAQ PDF real.
13. Monitor: latencia, custo Bifrost spend, recall (distance_top1 distribution), quota usage.

**Gate**: rollout ResenhAI 7d sem incidentes + ResenhAI agente cita chunk em respostas reais (SC-006 >=20%) + zero cross-tenant leak (SC-002).

### Reversao

Cada PR e reversivel:

- PR-A: rollback migration via `dbmate rollback`. Sem efeito em prod (sem deploy).
- PR-B: `rag.enabled: false` em `tenants.yaml` -> uploads 403 + tool nao expoe. Documentos persistidos preservados.
- PR-C: revert admin UI commit -> sidebar volta sem entry. Backend continua funcional.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Nao aplica. Constitution Check passou em todos os 9 principios. Zero desvios.

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan completo. PR-A (schema+chunker+embedder) -> PR-B (API admin+tool) -> PR-C (UI+rollout). Reuso intensivo: PyMuPDF (epic 009), tiktoken (epic 005), config_poller (epic 010), pool_admin (epic 008), Safety Layer A (epic 005), Bifrost (epic 005). Zero novas libs Python/TS — apenas pgvector extension PG. 7 user stories prioritizadas (4xP1, 3xP2, 1xP3). 76 FRs + 12 SCs. Estimativa: 800 LOC backend + 600 LOC TS + 150 LOC Go Bifrost. /speckit.tasks deve quebrar em ~30-40 tasks com dependencias claras (migrations -> chunker/embedder/extractor -> repository -> tool -> admin endpoints -> UI). Tasks marcados [P] quando paralelizaveis dentro do mesmo PR."
  blockers: []
  confidence: Alta
  kill_criteria: "pgvector nao habilitavel no plano Supabase managed atual -> bloqueio total, escalation infra; Bifrost extension >1 semana -> recuar para OpenAI direct sem spend tracking (sacrifica SC-010); chunker MD-aware/PDF revela edge cases >50% dos arquivos reais (texto degenerate) -> revisar abordagem antes de prosseguir; quotas defaults estouram em piloto Ariel (>50 docs ou >2000 chunks rapidamente) -> dimensionamento errado, replan."
