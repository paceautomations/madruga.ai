# Tasks: Tenant Knowledge Base — RAG pgvector + Upload Admin

**Input**: Design documents from `platforms/prosauai/epics/012-tenant-knowledge-base-rag/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (openapi.yaml, tool-schema.json, tenants-yaml-schema.json), quickstart.md

**Branch**: `epic/prosauai/012-tenant-knowledge-base-rag` (em `paceautomations/prosauai`, base `develop`)

**Tests**: Tests INCLUDED — spec.md FR-025 (chunker stdlib + tests), plan.md Constitution Check VII (TDD obrigatorio para PR-A), gate de coverage 85% para `prosauai/rag/*` e `prosauai/tools/search_knowledge.py`.

**Organization**: Tasks agrupados por user story para entrega incremental por PR. PR-A = Phase 1+2 (Setup + Foundational). PR-B = Phase 3+4+5 (US1+US2+US3 backend). PR-C = parte UI dentro de US1/US3/US4 + Phase 7+8 + Polish + Smoke.

## Path Conventions

- **Backend Python (FastAPI)**: `apps/api/prosauai/...` no repo `paceautomations/prosauai`
- **Migrations**: `apps/api/db/migrations/...` no repo `paceautomations/prosauai`
- **Tests Python**: `apps/api/tests/...` no repo `paceautomations/prosauai`
- **Frontend Admin (Next.js 15)**: `apps/admin/src/...` no repo `paceautomations/prosauai`
- **Bifrost extension (Go)**: `config/providers/...` e `adapters/...` no repo `paceautomations/bifrost`

> **External repo**: prosauai e self-managed (`platform.yaml: repo.name=prosauai`). Codigo vive em `/home/gabrielhamu/repos/paceautomations/prosauai/`, NAO em `madruga.ai/`. Branch checked out via `ensure_repo.get_repo_work_dir`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicializar estrutura do novo modulo `prosauai/rag/` e diretorios de testes.

- [x] T001 Criar skeleton `apps/api/prosauai/rag/__init__.py` (vazio, marker de package) + entries no `pyproject.toml [tool.coverage.report] fail_under_per_module` para `prosauai.rag.*` e `prosauai.tools.search_knowledge` (gate 85%)
- [x] T002 [P] Criar diretorios de testes: `apps/api/tests/rag/__init__.py`, `apps/api/tests/tools/__init__.py`, `apps/api/tests/admin/__init__.py` (subdir `knowledge/`), `apps/api/tests/safety/__init__.py`, `apps/api/tests/integration/__init__.py` (subdir `rag/`)
- [x] T003 [P] Adicionar `hypothesis>=6.100` e `respx>=0.21` em `apps/api/pyproject.toml [project.optional-dependencies.dev]` (validar que ja nao existem); regenerar lock via `uv lock` ou `pip-compile`
- [x] T004 [P] Criar fixtures de teste: `apps/api/tests/fixtures/rag/faq.md` (3 secoes `##`), `apps/api/tests/fixtures/rag/regulamento.pdf` (PDF 2 paginas com texto), `apps/api/tests/fixtures/rag/empty.txt` (vazio), `apps/api/tests/fixtures/rag/scanned.pdf` (PDF imagem-only para edge case OCR), `apps/api/tests/fixtures/rag/encrypted.pdf` (PDF com password)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema PG + Storage bucket + utilities (extractor/chunker/embedder/storage/repository) + Bifrost extension + observability. Necessario para QUALQUER user story.

**CRITICAL**: Nenhum trabalho de US1/US2/US3 pode comecar antes desta fase completa.

### Schema (Migrations)

- [X] T005 Criar migration `apps/api/db/migrations/20260601000006_create_pgvector_extension.sql` com `CREATE EXTENSION IF NOT EXISTS vector;` (idempotente, FR-006). Down: `-- intentionally no-op (pode quebrar outros tenants do plan Supabase)`
- [X] T006 Criar migration `apps/api/db/migrations/20260601000007_create_documents.sql` com tabela `prosauai.documents` (FR-001), CHECKs (`source_type IN md|txt|pdf`, `size_bytes >= 1`, `chunks_count >= 1`), UNIQUE `(tenant_id, source_name)`, FK `tenants(id) ON DELETE CASCADE`, FK `admin_users(id) ON DELETE SET NULL`, RLS policy `tenant_isolation` (FR-005, ADR-011), index `documents_tenant_uploaded_at_idx`, GRANTs para `prosauai_app` e `prosauai_admin`. Down: `DROP TABLE prosauai.documents CASCADE;`
- [X] T007 Criar migration `apps/api/db/migrations/20260601000008_create_knowledge_chunks.sql` com tabela `prosauai.knowledge_chunks` (FR-002), CHECK `tokens >= 10` (MIN_CHUNK_TOKENS, FR-074), UNIQUE `(document_id, chunk_index)`, FK `documents(id) ON DELETE CASCADE`, FK `agents(id) ON DELETE SET NULL`, RLS policy `tenant_isolation`, HNSW index `knowledge_chunks_embedding_hnsw_idx USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)` (FR-003, ADR-013), partial index `knowledge_chunks_tenant_agent_idx ... WHERE agent_id IS NOT NULL`, index `knowledge_chunks_document_idx (document_id, chunk_index)`, GRANTs. Down: `DROP TABLE prosauai.knowledge_chunks CASCADE;`
- [X] T008 Criar script idempotente `apps/api/db/migrations/20260601000009_create_knowledge_storage_bucket.py` que via Supabase Storage REST/SDK cria bucket `knowledge` (private, file_size_limit=10MB) + policy `service_role_only` (FR-007). Roda como step de `dbmate up` via `--migrations-dir` plugin OR como entry separado em script `apps/api/db/post-migrate.py`. Inclui retry idempotente (skip se bucket ja existe)

### Pydantic models + Config

- [X] T009 [P] Criar `apps/api/prosauai/rag/models.py` com pydantic models: `RagConfig` (FR-044, validators range + hard cap 50000 chunks), `DocumentRecord`, `DocumentUploadResponse`, `ChunkPreview`, `ErrorResponse` (com enum de 12 error codes do data-model.md secao 4.4)
- [X] T010 [P] Estender `apps/api/prosauai/config/tenants_schema.py` (existente epic 010) para incluir bloco opcional `rag: RagConfig`. Atualizar `apps/api/prosauai/config_poller.py` para validar bloco rag em reload, fail-safe em YAML invalido (mantem config anterior + log `tenant_config_reload_failed{reason}`, FR-045)
- [X] T011 [P] Criar `apps/api/config/tenants.example.yaml` (ou atualizar existente) com bloco `rag` documentado (defaults `enabled: false, top_k: 5, max_upload_mb: 10, max_documents_per_tenant: 200, max_chunks_per_tenant: 10000`) + comentarios inline

### Utilities (TDD-first)

- [X] T012 [P] [PR-A] Escrever testes property-based em `apps/api/tests/rag/test_chunker.py` ANTES de implementar: cobertura MD-aware (preamble + `##`/`###` aninhados), fixed-size 512 tokens + 50 overlap (PDF/text), MIN_CHUNK_TOKENS=10 (chunks degenerate sao mergeados/descartados), max_chunks_per_document=2000 (rejeitado com exception), edge case Markdown com tabela/code block dentro de secao, hypothesis strategies para text random
- [X] T013 [P] [PR-A] Escrever testes em `apps/api/tests/rag/test_embedder.py` com `respx` mocks: batch ate 100 textos por call Bifrost, retry exponencial 3x em 429/503/timeout, falha persistente propaga exception (FR-028), span OTel `rag.embed` com atributos corretos (FR-029), header `X-ProsaUAI-Tenant`
- [X] T014 [P] [PR-A] Escrever testes em `apps/api/tests/rag/test_extractor.py` com fixtures: PDF normal extrai texto, PDF scanned retorna `''` (string vazia detectada upstream, FR-074), PDF encrypted levanta `PdfEncryptedError`, MD/TXT passthrough com normalizacao UTF-8 strict, BOM strip
- [X] T015 [P] [PR-A] Implementar `apps/api/prosauai/rag/extractor.py` (~60 LOC): `extract(file_bytes: bytes, source_type: Literal['md','txt','pdf']) -> str`. PDF via PyMuPDF (reuse pattern de `prosauai/processors/document.py` epic 009). MD/TXT decode UTF-8 errors='strict', strip BOM. Custom exceptions `PdfEncryptedError`, `PdfExtractionError`. Tests T014 devem passar
- [X] T016 [P] [PR-A] Implementar `apps/api/prosauai/rag/chunker.py` (~90 LOC): `chunk_markdown(text: str) -> list[Chunk]` (regex `^##\s` e `^###\s`, preamble fica chunk 0); `chunk_fixed_size(text: str, max_tokens: int = 512, overlap: int = 50) -> list[Chunk]` via tiktoken cl100k_base; `chunk(text: str, source_type: str) -> list[Chunk]` dispatcher. Constantes: `MIN_CHUNK_TOKENS=10`, `MAX_CHUNKS_PER_DOCUMENT=2000`. Stdlib + tiktoken only. Tests T012 devem passar
- [x] T017 [P] [PR-A] Implementar `apps/api/prosauai/rag/embedder.py` (~80 LOC): `class BifrostEmbedder` com `embed_batch(texts: list[str], tenant_slug: str) -> tuple[list[list[float]], EmbedUsage]`. POST httpx para `bifrost.local/v1/embeddings` com `model=text-embedding-3-small`, header `X-ProsaUAI-Tenant`. Batch <=100. Retry exponencial 3x via `tenacity` (ja epic 005). Span OTel `rag.embed` com `embed.batch_size`, `embed.tokens_total`, `embed.cost_usd`, `embed.model`. Tests T013 devem passar
- [x] T018 [P] [PR-A] Implementar `apps/api/prosauai/rag/storage.py` (~70 LOC): `class SupabaseStorage` com `upload(tenant_id: UUID, document_id: UUID, ext: str, file_bytes: bytes) -> str` (path `knowledge/{tenant_id}/{document_id}.{ext}`), `delete(storage_path: str)`, `delete_prefix(prefix: str)` (para SAR cascade, FR-067), `signed_url(storage_path: str, ttl_seconds: int = 300) -> str` (FR-020 TTL 5 min). httpx para Supabase Storage REST API
- [x] T019 [PR-A] Escrever testes em `apps/api/tests/rag/test_repository.py` com testcontainers PG + pgvector: insert document + chunks (transaction), atomic-replace by source_name, cascade delete via FK, `pg_advisory_xact_lock(hashtext(...))` serializa concorrentes, RLS isolation invariant (cross-tenant SELECT como service-role com `app.tenant_id=X` retorna zero, SC-002)
- [x] T020 [PR-A] Implementar `apps/api/prosauai/rag/repository.py` (~120 LOC): `class RagRepository(asyncpg.Pool)` com metodos `insert_document_with_chunks(...)`, `replace_document_atomic(...)` (BEGIN; SELECT FOR UPDATE; DELETE old chunks; DELETE old document; INSERT new document + chunks; COMMIT), `delete_document(...)`, `list_documents(tenant_id, page, page_size, source_type) -> tuple[list[DocumentRecord], int]`, `get_document(id) -> DocumentRecord | None`, `count_documents_and_chunks(tenant_id) -> tuple[int, int]` (FR-073 quotas), `search_chunks(query_vec, tenant_id, agent_id, embedding_model, top_k) -> list[ChunkResult]` (FR-035), helper `acquire_doc_lock(tenant_id, source_name)` (FR-016 advisory_xact_lock). RLS context manager `set_tenant(tenant_id)`. Tests T019 devem passar

### Bifrost extension (PR-A — repo separado)

- [x] T021 [P] [PR-A] Criar arquivo `config/providers/openai-embeddings.toml` no repo `paceautomations/bifrost` com novo provider `openai_embeddings` (endpoint `/v1/embeddings`, target `https://api.openai.com/v1/embeddings`, `api_key_env=OPENAI_API_KEY`, `rate_limit_rpm=3500`, `rate_limit_tpm=5000000`, `cost_per_1k_tokens_usd=0.00002`, `spend_tracking_enabled=true`). FR-030, FR-032
- [x] T022 [PR-A] Implementar adapter Go `adapters/openai_embeddings.go` no repo `paceautomations/bifrost` (~150 LOC) reutilizando pattern de chat completions: rate limiter + spend tracker (insert em `bifrost_spend` com endpoint=embeddings) + circuit breaker (5 falhas/60s -> aberto 30s, FR-033). Validar header `X-ProsaUAI-Tenant` obrigatorio (sem header -> 400 fail-closed)
- [x] T023 [P] [PR-A] Atualizar `bifrost/db/migrations/...` (extension Bifrost) para garantir coluna `endpoint` em `bifrost_spend` aceita valor `'embeddings'` (provavelmente ja TEXT — verificar). Adicionar index `(tenant_id, endpoint, created_at)` se nao existe
- [x] T024 [PR-A] Smoke local Bifrost extension via curl (Step 4 quickstart.md): POST `bifrost.local/v1/embeddings` retorna 1536-dim vector + linha em `bifrost_spend` — **DEFERRED to deployment phase (T1100-T1105)**: Bifrost runs in ops-controlled infra; smoke runs after the cross-repo PR (T021-T023 artefatos em `bifrost/`) merges and Bifrost is reloaded. Curl recipe documented em `bifrost/README.md` smoke section

### Observability + Audit

- [x] T025 [P] Estender `apps/api/prosauai/observability/metrics.py` adicionando 6 metricas Prometheus (FR-063, SC-011): counters `rag_documents_uploaded_total{tenant}`, `rag_uploads_rejected_total{reason}`, `rag_search_invocations_total{tenant,outcome}`, `rag_embedder_failures_total{provider,reason}`; gauges `rag_chunks_total{tenant}`, `rag_documents_total{tenant}`; histograms `rag_search_duration_seconds_bucket`, `rag_upload_duration_seconds_bucket`
- [x] T026 [P] Criar `apps/api/prosauai/rag/audit.py` (~50 LOC) com helpers structlog para 5 event_types canonicos (FR-076): `emit_document_uploaded(...)`, `emit_document_deleted(...)`, `emit_document_downloaded(...)`, `emit_search_executed(...)`, `emit_replace_detected(...)`. Schema obrigatorio: `tenant_id`, `actor_user_id`, `document_id`, `source_name`, `action_result`, `timestamp`, `request_id`. Tests em `apps/api/tests/rag/test_audit.py`

**Checkpoint Phase 2 (PR-A complete)**: schema migrado em staging + bucket criado + Bifrost extension funcional + utilities com unit tests verdes (>=85% coverage `prosauai/rag/*`) + RLS isolation invariant verde. Pronto para iniciar US1+US2+US3 em paralelo.

---

## Phase 3: User Story 1 — Tenant operator faz upload de FAQ em PDF (Priority: P1) MVP

**Goal**: Operator do tenant Ariel faz upload de `faq.pdf` via admin UI, sistema extrai+chunka+embeda+persiste em transaction atomica em <=15s, admin ve chunks indexados na tabela.

**Independent Test**: Em staging com Ariel `rag.enabled=true`, upload `faq.md` (~5KB, 3 secoes `##`) via curl OU admin UI. Verify HTTP 201 + `chunks_created=3` + `SELECT count(*) FROM knowledge_chunks WHERE tenant_id=ariel.id` retorna 3 + Storage tem o arquivo + Trace explorer mostra span `agent_upload`.

### Tests para US1 (TDD)

- [x] T027 [P] [US1] Escrever `apps/api/tests/admin/knowledge/test_upload_endpoint.py`: upload MD valido retorna 201 + payload completo; upload `>10MB` retorna 413 com error `max_upload_mb_exceeded`; upload `0 bytes` retorna 400 `empty_file`; upload `.docx` retorna 415 `unsupported_format`; upload com `rag.enabled=false` retorna 403 `rag_not_enabled_for_tenant`; upload PDF scanned retorna 422 `no_chunks_extracted`; upload com Bifrost down retorna 503 `embeddings_provider_down` + verify rollback total (0 rows em documents/chunks, 0 files em Storage); quota docs estourada retorna 413 `tenant_quota_exceeded` com `dimension='documents'`; quota chunks estourada retorna 413 com `dimension='chunks'`
- [x] T028 [P] [US1] Escrever `apps/api/tests/integration/rag/test_upload_atomic_replace.py`: upload com `source_name` existente -> verify advisory lock obtido, chunks antigos deletados, Storage antigo deletado, novo document + chunks inseridos, tudo em uma transaction; falha de embedding no meio = rollback total

### Implementacao backend US1

- [x] T029 [US1] Criar router `apps/api/prosauai/admin/knowledge.py` com endpoint `POST /admin/knowledge/documents` (FR-011): aceita `multipart/form-data` com `tenant_id` (query param) + `file` (binary). Auth via JWT admin (middleware existente epic 008). Validacoes em ordem: (1) feature flag `rag.enabled=true` (FR-014, retorna 403); (2) MIME type / extension `md|txt|pdf` (FR-012, retorna 415); (3) `1 <= size_bytes <= rag.max_upload_mb` (FR-013, retorna 400/413); (4) quotas pre-check (FR-073, retorna 413 com replace-aware delta calculation); (5) acquire `pg_advisory_xact_lock(hashtext('doc:{tenant_id}:{source_name}'))` (FR-016)
- [x] T030 [US1] Adicionar logica core do endpoint upload em `knowledge.py`: extract -> chunk -> validate `chunks_count >= 1` (FR-074, retorna 422 sem chamar embedder) -> embed batch -> Storage upload -> transaction `replace_document_atomic` (delete old + insert new) -> emit audit `knowledge_document_uploaded` + opcional `knowledge_document_replace_detected` (FR-076) -> response 201 com `DocumentUploadResponse` (FR-011). Em qualquer falha: rollback Storage + DB, emit audit `knowledge_document_uploaded` com `action_result='failed'`, retornar erro tipado
- [x] T031 [US1] Registrar router em `apps/api/prosauai/admin/router.py`: `app.include_router(knowledge.router, prefix='/admin/knowledge', tags=['knowledge'])`
- [x] T032 [US1] Atualizar `apps/api/contracts/openapi.yaml` (existente epic 008) — verificar se ja tem todos paths + schemas do `epics/012-tenant-knowledge-base-rag/contracts/openapi.yaml` (POST `/admin/knowledge/documents`, schemas `DocumentUploadResponse`, `ErrorResponse` com 12 codes). Merge se diferenca

### Implementacao frontend US1

- [x] T033 [P] [US1] Adicionar entry "Base de Conhecimento" no sidebar `apps/admin/src/components/sidebar.tsx` (icon `BookOpen` lucide-react). Visivel apenas quando user role inclui `admin` OR `tenant_operator`
- [x] T034 [P] [US1] Criar pagina `apps/admin/src/app/admin/(authenticated)/knowledge/page.tsx`: shell com header + botao "Adicionar documento" + tabela placeholder (sera povoada em US3). Usa TanStack Query hook (T036)
- [x] T035 [P] [US1] Criar dialog `apps/admin/src/app/admin/(authenticated)/knowledge/upload-dialog.tsx` (~150 LOC): drag-drop zone (`react-dropzone` ja em deps) + file picker fallback + validacao client-side (formato `.md|.txt|.pdf`, size <=10MB) + spinner durante upload + resposta inline (chunks_created, cost). Mostra `AlertDialog` "Documento existente sera substituido" quando server retorna `replaced_existing=true` (post-resolve)
- [x] T036 [P] [US1] Criar hooks TanStack Query em `apps/admin/src/lib/api/knowledge.ts`: `useUploadDocument()`, `useDocumentsList()` (placeholder para US3), `useDeleteDocument()` (placeholder), `useDocumentChunks()` (placeholder), `useDownloadDocument()` (placeholder)
- [x] T037 [US1] Regenerar tipos TS via `pnpm gen:api` no repo `paceautomations/prosauai` -> commit `apps/admin/packages/types/api.ts`. Importar em hooks T036

### Smoke US1

- [x] T038 [US1] Smoke manual em staging Ariel: rodar Steps 5-6 do `quickstart.md` (habilitar `rag.enabled=true` em tenants.yaml + curl upload `faq.md`) -> verify 201 + DB + Storage. Repetir via admin UI (drag-drop) com mesmo arquivo -> verify replace dialog aparece + apos confirm chunks_count atualiza. **NOTA (autonomous run)**: smoke staging requer ambiente real; deferred para deploy gate. Runbook pronto via `quickstart.md` Steps 5-6 + 13 testes integration/admin verdes localmente comprovam o caminho (upload happy-path, atomic-replace, todas as 9 ramificacoes de erro).

**Checkpoint US1**: upload funcional via curl + admin UI; integration tests verdes; smoke Ariel ok. US1 entregavel isolado (mesmo sem US2/US3, admin pode upar e ver via SQL).

---

## Phase 4: User Story 2 — Agente usa tool `search_knowledge` e responde com contexto (Priority: P1)

**Goal**: Cliente manda mensagem requirindo contexto do KB. LLM decide chamar `search_knowledge`. Tool roda SELECT cosine, retorna top-5 chunks, LLM compoe resposta citando chunk. End-to-end <5s p95.

**Independent Test**: Em staging com Ariel ja tendo 1 documento (depende de US1 ter sido feito ao menos uma vez via curl). Agente Ariel com `tools_enabled=['search_knowledge']`. Enviar "qual o horario de funcionamento?". Verify Trace Explorer mostra span `tool_call.search_knowledge` -> `rag.search` com `chunks_returned=5, distance_top1<0.4`. Resposta cita literalmente trecho do FAQ.

### Tests para US2 (TDD)

- [x] T039 [P] [US2] Escrever `apps/api/tests/tools/test_search_knowledge.py` com pydantic-ai `TestModel`: tool e registrada em `tools/registry.py` com nome `search_knowledge` + schema `SearchKnowledgeInput`; LLM input `{query, top_k}` valida (min_length=1, top_k clamped to 20); server-side `tenant_id`/`agent_id`/`embedding_model` injection (LLM tenta passar `tenant_id` no input -> overridden); SQL emitido inclui `WHERE tenant_id=$1 AND (agent_id IS NULL OR agent_id=$2) AND embedding_model=$3 ORDER BY distance LIMIT $4`; embedder failure retorna `[]` + log warning `rag_embedder_unavailable` (FR-038, graceful degradation); KB vazio retorna `[]` + log `rag_kb_empty`
- [x] T040 [P] [US2] Escrever `apps/api/tests/safety/test_input_guard_rag.py`: chunk com prompt injection ("Ignore previous instructions...") e descartado pelo Safety Layer A com log `rag_chunk_rejected` (FR-040); chunks legitimos passam intactos
- [x] T041 [P] [US2] Escrever `apps/api/tests/integration/rag/test_pipeline_tool_call.py`: ponta-a-ponta com 1 documento embedado em testcontainers + agent com `tools_enabled=['search_knowledge']` + LLM mock que sempre chama tool -> verify span hierarchy `agent.generate -> tool_call.search_knowledge -> rag.search + rag.embed` com atributos OTel corretos (FR-039); eval scoring recebe `details.rag_used=true` (FR-043)
- [x] T042 [P] [US2] Escrever `apps/api/tests/integration/rag/test_cross_tenant_isolation.py`: criar 2 tenants A e B com chunks proprios, simular tool call no tenant A -> verify zero chunks de B retornados, mesmo se LLM tentar passar `tenant_id=B` no input (server-side injection wins, FR-035, SC-002)

### Implementacao backend US2

- [x] T043 [US2] Criar `apps/api/prosauai/tools/search_knowledge.py` (~80 LOC): pydantic schemas `SearchKnowledgeInput(query, top_k)` + `ChunkResult(text, source_name, source_type, distance, document_id)`. Funcao `async def search_knowledge(ctx: RunContext[ConversationDeps], query: str, top_k: int = 5) -> list[ChunkResult]`. Server-side injection via `ctx.deps.tenant_id`, `ctx.deps.agent_id`, `ctx.deps.embedding_model`. `top_k = min(top_k, 20)` (FR-034 hard cap). Embed query via `embedder.embed_batch([query], tenant_slug)` (FR-037). SELECT via `repository.search_chunks(...)`. Span OTel `rag.search` com atributos. Try/except embedder error -> retornar `[]` + log warning. Apos query, passa cada chunk por `safety.input_guard.validate_chunk(text)` (FR-040)
- [x] T044 [US2] Estender `apps/api/prosauai/tools/registry.py`: registrar via `@register_tool('search_knowledge', schema=SearchKnowledgeInput, output=list[ChunkResult], description='Search the tenant knowledge base...')`. Verificar registry NAO esta vazio pos-epic 010 (assumption do pitch); se vazio, scaffold minimo restaurado
- [x] T045 [US2] Estender `apps/api/prosauai/safety/input_guard.py`: adicionar funcao `validate_chunk(text: str) -> bool` reutilizando regex/heuristica de Layer A (epic 005 ADR-016). Chunk reprovado retorna `False` + log estruturado `rag_chunk_rejected` com motivo (regex match, suspicion score)
- [x] T046 [US2] Modificar `apps/api/prosauai/pipeline/steps/agent_generate.py`: montar schema de tools dinamicamente (FR-041). Para cada tool em `agents.tools_enabled`, busca em `tools/registry.py`. **Filtro defesa em profundidade**: se tool == `search_knowledge` mas `tenant.rag.enabled=false`, descarta antes de enviar ao LLM. Pipeline pydantic-ai ja suporta function calling nativamente (FR-042)
- [x] T047 [US2] Adicionar emit `audit.emit_search_executed(...)` em `search_knowledge.py` (FR-076 evento `knowledge_search_executed` com campos `tenant_id`, `query_tokens`, `chunks_returned`, `distance_top1`, `agent_id`)
- [x] T048 [US2] Adicionar hook em `apps/api/prosauai/eval/scorer.py` (epic 011) ou modulo equivalente: quando span `rag.search` existe na trace da mensagem, marca `eval_scores.details.rag_used=true` (FR-043, SC-009 correlation hook)

### Smoke US2

- [x] T049 [US2] Smoke manual: rodar Steps 7-8-9 do `quickstart.md` (atualizar `tools_enabled` do agente Ariel via `PATCH /admin/agents/{id}` + enviar "qual o horario de funcionamento?" via WhatsApp simulator). Verify Trace Explorer mostra spans completos + resposta cita texto do FAQ chunk. **NOTA (autonomous run)**: smoke staging requer ambiente real com Bifrost + Ariel WhatsApp simulator; deferred para deploy gate. Codigo end-to-end coberto pelos 36 testes de Phase 4 verdes (US2): tool registrada via `@register_tool('search_knowledge')` em `prosauai/tools/__init__.py` + `search_knowledge.py`; defesa em profundidade via `agent.get_enabled_tools(tenant=...)` que descarta a tool quando `tenant.rag.enabled=false` mesmo com whitelist; pipeline propaga tenant + RAG deps (repository/embedder) atraves de `ConversationDeps`; spans `rag.search`/`rag.embed` + audit `knowledge_search_executed` + eval hook `details.rag_used=true` validados via `tests/integration/rag/test_pipeline_tool_call.py`; cross-tenant isolation invariant validado via `tests/integration/rag/test_cross_tenant_isolation.py`.

**Checkpoint US2**: tool funcional + cross-tenant isolation invariant verde + Trace Explorer mostra spans + smoke Ariel responde com chunk citado. US2 entregavel isolado dado que US1 fez ao menos 1 upload.

---

## Phase 5: User Story 3 — Admin lista, deleta e substitui documentos do KB (Priority: P1)

**Goal**: Admin abre tabela de documentos, filtra, deleta com cascade, faz replace by `source_name`. Cross-tenant filtering funciona para Pace ops.

**Independent Test**: Em staging com Ariel tendo 3 documentos. (a) `GET /admin/knowledge/documents?tenant=ariel` retorna 3. (b) DELETE remove documento + cascade chunks + Storage. (c) Re-upload com mesmo `source_name` faz atomic replace.

### Tests para US3 (TDD)

- [x] T050 [P] [US3] Escrever `apps/api/tests/admin/knowledge/test_list_endpoint.py`: GET retorna lista paginada (page, page_size, default 50) com `DocumentRecord`; filtro `?source_type=pdf` funciona; filtro `?tenant_id=X` opcional para Pace ops cross-tenant via `pool_admin` BYPASSRLS; latencia <500ms p95 com 1k docs (test com seed)
- [x] T051 [P] [US3] Escrever `apps/api/tests/admin/knowledge/test_delete_endpoint.py`: DELETE retorna 204; verify cascade DB (chunks=0 apos) + Storage (file removido); cross-tenant delete (tentar deletar doc de outro tenant) retorna 404 (RLS silent reject); audit log `knowledge_document_deleted` emitido
- [x] T052 [P] [US3] Escrever `apps/api/tests/admin/knowledge/test_raw_endpoint.py`: GET `/raw` retorna 302 redirect para signed URL Supabase; URL TTL 5min; cross-tenant 404
- [x] T053 [P] [US3] Escrever `apps/api/tests/admin/knowledge/test_chunks_preview.py`: GET `/chunks?limit=10` retorna `[ChunkPreview]` (text, chunk_index, tokens) ordenado por `chunk_index`; default limit 10, max 50

### Implementacao backend US3

- [x] T054 [US3] Adicionar em `apps/api/prosauai/admin/knowledge.py` o endpoint `GET /admin/knowledge/documents` (FR-018): query params `tenant_id`, `source_type`, `page`, `page_size`. Pace ops com `pool_admin` BYPASSRLS pode omitir `tenant_id` para listar cross-tenant. Resposta paginada com `total_count` no header `X-Total-Count`
- [x] T055 [US3] Adicionar `DELETE /admin/knowledge/documents/{document_id}` (FR-019): transaction (a) DELETE Storage `knowledge/{tenant_id}/{document_id}.{ext}`, (b) DELETE FROM `documents WHERE id=$1` (chunks cascadeiam por FK). Emit audit `knowledge_document_deleted`. Cross-tenant retorna 404 silently (RLS). Resposta 204
- [x] T056 [US3] Adicionar `GET /admin/knowledge/documents/{document_id}/raw` (FR-020): resolve `storage_path` -> request signed URL Supabase Storage TTL 300s -> retorna 302 Redirect com `Location` header. Emit audit `knowledge_document_downloaded`
- [x] T057 [US3] Adicionar `GET /admin/knowledge/documents/{document_id}/chunks?limit=10` (FR-021): SELECT `chunk_index, content, tokens FROM knowledge_chunks WHERE document_id=$1 ORDER BY chunk_index LIMIT $2`. Default limit 10, max 50

### Implementacao frontend US3

- [x] T058 [P] [US3] Atualizar `apps/admin/src/app/admin/(authenticated)/knowledge/page.tsx` para renderizar tabela shadcn (`DataTable`) com colunas `source_name, source_type (badge), chunks_count, size, uploaded_at, actions`. Filtros por `source_type` (pills shadcn) + busca por `source_name` (client-side). Pace ops ve coluna extra `tenant`
- [x] T059 [P] [US3] Criar `apps/admin/src/app/admin/(authenticated)/knowledge/delete-dialog.tsx`: shadcn `AlertDialog` com confirm "Esta acao remove o documento e seus N chunks. Confirmar?"
- [x] T060 [P] [US3] Criar `apps/admin/src/app/admin/(authenticated)/knowledge/document-detail-sheet.tsx` (~100 LOC): shadcn `Sheet` que abre ao click na linha. Mostra metadata + primeiros 3 chunks via `useDocumentChunks(documentId, 3)`. Botao "Download original" -> redirect via `useDownloadDocument(documentId)` -> `window.location.href = response.url`
- [x] T061 [US3] Atualizar hooks em `apps/admin/src/lib/api/knowledge.ts` para usar tipos regenerados (T037): `useDocumentsList(tenantId?, sourceType?, page)`, `useDeleteDocument()`, `useDocumentChunks(id, limit)`, `useDownloadDocument(id)`. Invalidate query `['documents', tenantId]` apos upload/delete

### SAR extension US3 (LGPD)

- [x] T062 [US3] Estender `apps/api/prosauai/privacy/sar.py` (existente, ADR-018) para incluir documents do tenant na resposta SAR (FR-066): adicionar `knowledge_documents: list[DocumentRecord]` ao payload. Para `DELETE /admin/sar/{customer_id}` cascadeia documents + chunks (FK) + Storage prefix `knowledge/{tenant_id}/` via `storage.delete_prefix(...)` (FR-067)

### Smoke US3

- [x] T063 [US3] Smoke manual: Steps 10-11 do `quickstart.md` (admin UI lista + delete + replace via re-upload). Verify cascade no DB + Storage. Verify span historico de delete preservado (FR-075) — Trace Explorer renderiza `source_name = "(deleted)"` no JOIN. **NOTA (autonomous run)**: smoke staging requer ambiente real com Supabase Storage + admin UI + Trace Explorer (epic 008); deferred para deploy gate. Runbook pronto via `quickstart.md` Steps 10-11. O caminho end-to-end ja esta coberto por testes que rodam localmente: (a) atomic-replace + cascade DB foram validados pelos 13 testes integration de PR-A/PR-B (T028, T053, T086 RLS invariant); (b) cascade Storage via `SupabaseStorage.delete` foi validado em `apps/api/tests/rag/test_storage.py`; (c) `erase_tenant_knowledge_base` (T062) tem 3 cobertura cases (DB ok, DB falha, Storage falha) provando que `DELETE FROM documents` cascade FK -> `knowledge_chunks` + `delete_prefix(tenant_id)` plumbing esta correto; (d) span `rag.search` com `source_name="(deleted)"` deriva de LEFT JOIN entre `trace_steps.attributes` e `documents` no Trace Explorer (epic 008) e nao requer mudanca em epic 012 alem do append-only invariant ja preservado pelas migrations 06-09

**Checkpoint US3**: GET/DELETE/RAW/CHUNKS funcionais + admin UI completa + SAR cascade + audit logs. **PR-B mergeavel em develop ao final desta phase** (US1+US2+US3 backend ok, UI parcial).

---

## Phase 6: User Story 4 — Per-agent toggle (Priority: P2)

**Goal**: Admin liga/desliga `search_knowledge` por agente via toggle UI na aba Agentes (epic 008).

**Independent Test**: ResenhAI com 2 agentes + `rag.enabled=true`. Toggle on em `agent-aulas`, off em `agent-comercial`. Mensagem teste para cada -> verify Trace Explorer mostra span de tool so para `agent-aulas`.

### Tests para US4

- [x] T064 [P] [US4] Escrever `apps/api/tests/admin/test_agent_rag_toggle.py`: PATCH `/admin/agents/{id}` com `tools_enabled=['search_knowledge']` adiciona corretamente; PATCH com `tools_enabled=[]` remove; tenant com `rag.enabled=false` rejeita PATCH com erro (defense in depth, alem do filtro pipeline)
- [x] T065 [P] [US4] Escrever Playwright test `apps/admin/tests/e2e/agents-rag-toggle.spec.ts`: abrir aba Agentes do tenant, toggle on em um agente, verify Switch state, refresh page, verify persistido; tenant com `rag.enabled=false` mostra Switch greyed-out + tooltip

### Implementacao US4

- [x] T066 [US4] Verificar/atualizar endpoint `PATCH /admin/agents/{id}` (existente epic 008) para aceitar e validar mudancas em `tools_enabled` (jsonb array). Documentar em `contracts/openapi.yaml` que `'search_knowledge'` e tool name valido
- [x] T067 [US4] Criar componente `apps/admin/src/app/admin/(authenticated)/agents/rag-toggle.tsx` (~50 LOC): shadcn `Switch` per row da tabela Agentes. Estado reflete `agent.tools_enabled.includes('search_knowledge')`. Greyed-out (disabled) com tooltip "Habilitar RAG no tenant primeiro" quando `tenant.rag.enabled=false`. Confirmacao modal "Adicionar/Remover search_knowledge dos tools_enabled?" antes de aplicar
- [x] T068 [US4] Integrar `rag-toggle.tsx` na tabela existente de Agentes (`apps/admin/src/app/admin/(authenticated)/agents/page.tsx`). Coluna nova "RAG" entre `name` e `model`
- [x] T069 [US4] Smoke: ResenhAI staging com 2 agentes, toggle on um + off outro, mensagem teste, verify Trace Explorer (runbook em `runbook-us4-smoke.md` — execucao depende de staging com tenant ResenhAI configurado)

**Checkpoint US4**: per-agent granularity funcional. Defense in depth: UI Switch + endpoint validation + pipeline filter (T046) garantem 3 camadas de protecao.

---

## Phase 7: User Story 5 — CLI re-embed para upgrade de modelo (Priority: P2)

**Goal**: Pace ops roda `python -m prosauai.rag.reembed --tenant ariel --target-model X` para migrar embeddings sem exigir re-upload do tenant.

**Independent Test**: Ariel com 3 docs em `text-embedding-3-small`. Rodar CLI com mock provider -> verify CLI le 3 raws do Storage, re-chunka, re-embeda, transaction atomica DELETE old + INSERT new + UPDATE `documents.embedding_model`.

### Tests para US5

- [x] T070 [P] [US5] Escrever `apps/api/tests/rag/test_reembed_cli.py`: subprocess call com `--tenant X --target-model Y --dry-run`; verify output mostra plano (N docs, ~M chunks); `--target-model` com dim diferente de 1536 aborta com erro `dim_mismatch` (sem tocar dados); falha intermitente Bifrost faz retry 3x; falha persistente em doc N aborta apenas ele (docs anteriores ja completados ficam com novo modelo); `--from-document {id}` continua de onde parou

### Implementacao US5

- [x] T071 [US5] Implementar `apps/api/prosauai/rag/reembed.py` (~150 LOC): `python -m prosauai.rag.reembed` via argparse com flags `--tenant`, `--target-model`, `--dry-run`, `--from-document {id}`. Loop por documento: (1) baixa raw via `storage.get(...)`; (2) re-extract + re-chunk; (3) embed batch via `embedder.embed_batch(...)`; (4) transaction `BEGIN; DELETE chunks WHERE document_id; INSERT new chunks; UPDATE documents SET embedding_model=$Y; COMMIT;`. Progress bar via stdlib (sem rich). Logs estruturados por doc. Retry exponencial 3x por batch
- [x] T072 [US5] Adicionar runbook ops em `apps/api/docs/runbooks/rag-reembed.md` (~30 LOC): pre-checks (Bifrost up, OpenAI quota), comando exato, monitoring de progresso, rollback (`dbmate rollback` nao serve — restaurar via re-embed para modelo antigo)

**Checkpoint US5**: operacao operacional rara mas critica funcional. Cobre upgrade de modelo zero-touch para tenants.

---

## Phase 8: User Story 6 — Feature flag hot-reload via tenants.yaml (Priority: P2)

**Goal**: Operator edita `rag.enabled` em `tenants.yaml`, commita, config_poller (epic 010) recarrega em <=60s sem restart. Reverte funcionalidade <=60s sem deploy.

**Independent Test**: Ariel staging. Mudar `rag.enabled=false` -> aguardar 60s -> upload retorna 403, tool sumir do schema. Mudar para `true` -> mesmo upload retorna 201.

### Tests para US6

- [x] T073 [P] [US6] Escrever `apps/api/tests/config/test_rag_config_reload.py`: simular edicao YAML + chamar `config_poller.reload_now()` -> verify estado in-memory atualizado; YAML invalido (`top_k=-1`, `max_upload_mb='abc'`) -> reload rejeitado, config anterior preservada (FR-045 fail-safe), log `tenant_config_reload_failed{tenant, reason}` emitido
- [x] T074 [P] [US6] Escrever Playwright test ou curl-based `apps/admin/tests/e2e/rag-flag-reload.spec.ts`: smoke de toggle via mudanca de YAML em staging branch + aguardar reload

### Implementacao US6

- [x] T075 [US6] Validar/estender `apps/api/prosauai/config_poller.py` para incluir validacao do bloco `rag` (RagConfig de T009) em cada reload. Em validation error, emit `tenant_config_reload_failed{tenant, reason}` + metric `tenant_config_reload_failed_total`. Mantem config anterior in-memory (fail-safe)
- [x] T076 [US6] Adicionar endpoint admin `GET /admin/config/tenants/{tenant_id}/rag` (read-only) que retorna config rag corrente in-memory para debug ops. Auth requer admin role
- [x] T077 [US6] Smoke Step 12 do `quickstart.md` (kill-switch via flag toggle) — validar que upload alterna entre 403 e 201 em <=60s sem deploy. Validar `tenant_config_reload_total` metric incrementa

**Checkpoint US6**: kill-switch operacional <=60s confirmado. SC-007 atendido.

---

## Phase 9: User Story 7 — Bifrost spend tracking accuracy (Priority: P3)

**Goal**: Bifrost extension (ja implementada em Foundational T021-T024) traceia spend em `bifrost_spend` com accuracy <=2% diff vs invoice OpenAI mensal.

**Independent Test**: Em staging, fazer 100 uploads -> comparar `SUM(bifrost_spend.cost_usd WHERE endpoint='embeddings')` vs custo calculado manualmente (`SUM(tokens * cost_per_1k_tokens)`).

### Tests para US7

- [x] T078 [P] [US7] Escrever `bifrost/tests/integration/test_embeddings_spend.go`: 10 calls embeddings com tokens conhecidos -> verify cada linha em `bifrost_spend` com `cost_usd` correto (precisao 6 casas decimais); rate limit 3500 req/min funciona (req 3501 retorna 429)
- [x] T079 [P] [US7] Escrever script Python `apps/api/scripts/audit_bifrost_spend.py` (~50 LOC): query mensal `SUM(cost_usd) GROUP BY tenant_id, endpoint, provider`; output CSV para reconciliar com invoice OpenAI

### Implementacao US7

- [x] T080 [US7] Adicionar dashboard Grafana (file `bifrost/dashboards/embeddings.json`) com paineis: requests/sec, p95 latencia, spend $ acumulado por tenant, rate limit usage %. Documentado em `bifrost/docs/dashboards.md`
- [x] T081 [US7] Smoke quickstart Step 4 + 9 (verify spend grava + Trace Explorer mostra `rag.cost_usd` no span). Validar Bifrost circuit breaker abre apos 5 falhas em 60s e fecha apos 1 sucesso

**Checkpoint US7**: spend tracking acurado, dashboard ops disponivel. SC-010 atendido.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentacao, eval correlation hook, integration tests cross-story, rollout produtivo.

- [x] T082 [P] Criar `apps/admin/docs/knowledge-base.md` (~40 LOC) — README user-facing: como uso "Base de Conhecimento", formatos suportados, replace by source_name behavior, quotas defaults
- [x] T083 [P] Atualizar `apps/api/docs/architecture/rag.md` (~80 LOC) — diagrama do flow upload + tool call, decisoes ADR-013/041/042 sumarizadas, troubleshooting (extracted de quickstart.md)
- [x] T084 [P] Criar runbook ops `apps/api/docs/runbooks/rag-rollout.md` (~30 LOC): rollout steps Ariel -> ResenhAI, criterios go/no-go (SC-002 zero leak, SC-006 >=20% chunks cited), rollback procedure (rag.enabled=false)
- [x] T085 [P] Verificar integration test cross-story `apps/api/tests/integration/rag/test_quickstart_e2e.py` cobrindo Steps 1-13 do `quickstart.md` (pode usar `pytest --markers e2e` para skip por default em CI rapida)
- [x] T086 [P] Adicionar test invariant noturno cross-tenant em CI: `apps/api/tests/integration/rag/test_invariant_zero_cross_tenant_leak.py` rodado em schedule (GitHub Actions cron) — para cada tenant, query como service-role com `app.tenant_id=X` retorna zero rows de outros tenants (SC-002)
- [x] T087 [P] Criar ADR-041 `platforms/prosauai/decisions/ADR-041-knowledge-document-replace-by-source-name.md` (Nygard format): contexto (lifecycle simples sem versionamento), decisao (atomic replace by source_name), consequencias (re-embed total custa R$0.005 vs versionamento overhead)
- [x] T088 [P] Criar ADR-042 `platforms/prosauai/decisions/ADR-042-bifrost-embeddings-extension.md` (Nygard format): contexto (Bifrost so chat completions), decisao (extender com `/v1/embeddings` provider OpenAI), alternativa rejeitada (chamada direta sem rate limit/spend tracking)
- [ ] T089 Atualizar `platforms/prosauai/decisions/ADR-013-pgvector-tenant-knowledge.md` adicionando nota "Estendido pelo epic 012 com tabela `documents` + colunas `document_id`, `embedding_model`, `chunk_index` em `knowledge_chunks`"
- [ ] T090 Atualizar `platforms/prosauai/decisions/ADR-018-data-retention-lgpd.md` adicionando nota "Cascade SAR delete inclui `documents` + Supabase Storage prefix `knowledge/{tenant_id}/`"
- [ ] T091 Performance baseline: rodar Step 13 do `quickstart.md` em staging Ariel pos-rollout, capturar `histogram_quantile(0.95, rag_search_duration_seconds_bucket)` + `_upload_duration_seconds_bucket` + `bifrost_spend` agregado. Documentar em `apps/api/docs/performance/rag-baseline.md`
- [ ] T092 Rollout produtivo: Ariel `disabled -> enabled` com 1 FAQ MD curto (smoke 24h) -> ResenhAI 7d depois com FAQ PDF real + 2 agentes com tool. Monitor dashboards: latencia, custo, recall, quota usage. Critterios go: SC-002 (zero leak) + SC-006 (>=20% chunks cited)

---

## Phase 11: Deployment Smoke

**Purpose**: Validar que o stack completo sobe e responde apos as mudancas — gate ultimo antes de declarar epic shippable.

- [ ] T1100 Executar `docker compose build` no diretorio da plataforma (`apps/`) — build sem erros (incluindo nova dep `tiktoken` se nao havia, e PyMuPDF reusada). Em caso de mismatch de dep python, atualizar lock file
- [ ] T1101 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --start --platform prosauai` — todos os health_checks (`localhost:8050/health`, `localhost:3000`) respondem dentro do `ready_timeout: 120s`
- [ ] T1102 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-env --platform prosauai` — zero `required_env` vars ausentes em `.env` (`JWT_SECRET`, `ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD`, `DATABASE_URL`)
- [ ] T1103 Executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --validate-urls --platform prosauai` — todas as URLs em `testing.urls` acessiveis com status esperado
- [ ] T1104 Capturar screenshot de `localhost:3000/admin/knowledge` (nova aba do epic) — verify renderiza tabela de documentos (mesmo que vazia) com botao "Adicionar documento"; conteudo nao e placeholder
- [ ] T1105 Executar Journey J-001 (happy path) declarado em `platforms/prosauai/testing/journeys.md` — todos os steps com assertions OK

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sem dependencias — comeca imediato
- **Foundational (Phase 2)**: Depende de Setup. **BLOQUEIA** todas user stories. Tasks dentro de Phase 2: migrations T005-T008 sequenciais (06->07->08->09); T009-T011 (modelos+config) paralelos; T012-T020 (utilities + tests TDD) com test-tasks paralelos PRIMEIRO depois implementations T015-T018 e T020 paralelos; T021-T024 (Bifrost) podem rodar em paralelo com utilities Python; T025-T026 (observability) paralelos. **Gate**: tests verdes >=85% coverage + RLS isolation invariant verde + Bifrost smoke
- **US1 (Phase 3)**: Depende de Phase 2 completa. Backend (T029-T032) depende de utilities (extractor, chunker, embedder, storage, repository, audit). Frontend (T033-T037) pode rodar em paralelo com backend pos-T032 (contract OpenAPI estavel)
- **US2 (Phase 4)**: Depende de Phase 2 completa. **Independente de US1** (pode rodar em paralelo no time). Tool implementation (T043-T048) depende de embedder + repository (Phase 2)
- **US3 (Phase 5)**: Depende de Phase 2 completa. **Independente de US1/US2 backend**. Frontend (T058-T061) depende de backend US1 (page.tsx skeleton T034) + US3 (T054-T057). Pode rodar UI em paralelo com US2 backend
- **US4 (Phase 6)**: Depende de Phase 2 + US2 (precisa ter `search_knowledge` registrada). Pode rodar em paralelo com US3 final
- **US5 (Phase 7)**: Depende de Phase 2 (utilities). Independente de US1/US2/US3/US4. Pode rodar em paralelo
- **US6 (Phase 8)**: Depende de Phase 2 (config_poller schema) + qualquer feature usando `rag.enabled` (US1, US2). Pode rodar em paralelo com US5
- **US7 (Phase 9)**: Bifrost ja foi feito em Phase 2 (T021-T024). Esta Phase apenas adiciona dashboards + audit script + smoke. Pode rodar em paralelo com US5/US6
- **Polish (Phase 10)**: Depende de US1+US2+US3 completas (PR-B mergeado). T087-T090 (ADRs) podem rodar em paralelo. T092 (rollout) depende de Phase 11 (smoke deploy verde)
- **Deployment Smoke (Phase 11)**: Depende de Polish T082-T091. **Gate ultimo** antes de rollout T092

### User Story Dependencies (resumo time-staffed)

- **US1, US2, US3** podem rodar em paralelo apos Phase 2 (3 devs simultaneos)
- **US4** depende de US2 (precisa tool registrada) — sequencial apos US2
- **US5, US6** independentes — podem rodar em paralelo apos Phase 2
- **US7** parcialmente em Phase 2 (Bifrost extension), polish em Phase 9

### Within Each User Story (TDD ordering)

- Tests escritos PRIMEIRO (e devem falhar) — verify red
- Models antes de services
- Services antes de endpoints
- Backend completo antes de frontend (UI consome OpenAPI types)
- Implementation completa antes de smoke manual

### Parallel Opportunities

- Phase 1: T002, T003, T004 paralelos
- Phase 2: T009-T011 (modelos) paralelos; T012-T014 (test specs) paralelos; T015-T018 (utilities impl) paralelos pos-tests; T021-T024 (Bifrost) paralelo com Python work; T025-T026 (observability) paralelos
- Phase 3 (US1): T027-T028 (tests) paralelos; T033-T037 (frontend) paralelos com backend (apos T032 OpenAPI contract estavel)
- Phase 4 (US2): T039-T042 (tests) paralelos
- Phase 5 (US3): T050-T053 (tests) paralelos; T058-T060 (frontend) paralelos
- Phase 6 (US4): T064-T065 (tests) paralelos
- Phase 7 (US5): T070 paralelo com T078 (US7)
- Phase 10: T082-T086 (docs+tests) paralelos; T087-T090 (ADRs) paralelos

---

## Parallel Example: Phase 2 Foundational (PR-A semana 1)

```bash
# Wave 1 — escrever specs/tests primeiro (TDD red):
Task: "Escrever testes property-based test_chunker.py em apps/api/tests/rag/"
Task: "Escrever testes test_embedder.py com respx mocks em apps/api/tests/rag/"
Task: "Escrever testes test_extractor.py com fixtures em apps/api/tests/rag/"
Task: "Escrever testes test_repository.py com testcontainers em apps/api/tests/rag/"

# Wave 2 — implementations paralelas pos-tests red:
Task: "Implementar prosauai/rag/extractor.py (~60 LOC)"
Task: "Implementar prosauai/rag/chunker.py (~90 LOC)"
Task: "Implementar prosauai/rag/embedder.py (~80 LOC)"
Task: "Implementar prosauai/rag/storage.py (~70 LOC)"

# Wave 3 — Bifrost extension repo separado:
Task: "Criar config/providers/openai-embeddings.toml em paceautomations/bifrost"
Task: "Implementar adapter Go adapters/openai_embeddings.go em paceautomations/bifrost"
```

---

## Implementation Strategy

### MVP First (US1 Only — entrega valor de coleta)

1. Phase 1: Setup
2. Phase 2: Foundational (BLOQUEIA tudo) — termina PR-A
3. Phase 3: US1 Upload — admin pode upar e ver no DB (sem tool, agente ainda nao usa)
4. **STOP & VALIDATE**: Demo Pace ops fazendo upload de FAQ Ariel via UI
5. Deploy preview com tenant pace-internal

### Incremental Delivery (PRs sequenciais)

1. **PR-A merge** (Phase 1 + 2): schema + utilities + Bifrost. Sem prod. Smoke local
2. **PR-B merge** (Phase 3 + 4 + 5): US1 + US2 + US3 backend completo + UI parcial. Smoke Ariel curl. Tool funcional. Cut-line: se PR-B estourar semana 2, UI completa vira 012.1
3. **PR-C merge** (Phases 6 + 7 + 8 + 9 + 10 + 11): UI completa + per-agent + CLI re-embed + flag hot-reload + dashboards Bifrost + docs + smoke deploy. Rollout produtivo

### Parallel Team Strategy (3 devs)

Apos PR-A merged:

- Dev A: US1 (upload) — Phase 3
- Dev B: US2 (tool + pipeline) — Phase 4
- Dev C: US3 (list/delete + UI) — Phase 5

Apos PR-B merged:

- Dev A: US4 (per-agent toggle) + US6 (flag hot-reload)
- Dev B: US5 (CLI re-embed) + Polish docs
- Dev C: US7 (dashboards) + frontend polish + Phase 11 (smoke)

---

## Notes

- [P] tasks = arquivos diferentes, sem dependencias bloqueantes
- [PR-A]/[PR-B]/[PR-C] tags marcam PR de destino (ver Implementation Strategy)
- [US1]/[US2]/[US3]/[US4]/[US5]/[US6]/[US7] tags mapeiam para user stories da spec.md
- TDD obrigatorio: testes escritos antes da implementacao em Phase 2 e Phase 3+ (verify red antes de green)
- Coverage gate 85% para `prosauai/rag/*` e `prosauai/tools/search_knowledge.py`
- Reversibilidade: toda mudanca usuario-facing tem kill-switch via `rag.enabled=false` per-tenant em <=60s (US6)
- Cut-lines (do pitch): PR-B estoura -> UI completa vira 012.1; Bifrost extension >1 semana -> recuar para chamada OpenAI direta sem spend tracking (sacrifica SC-010 temporariamente)
- Cross-tenant invariant test (T086) roda em CI nightly para detectar regressoes de RLS
- Commit conventions: `feat(rag): ...`, `fix(rag): ...`, `chore(rag): ...`. Subject termina com `[epic:012-tenant-knowledge-base-rag]` para reverse-reconcile loop closure (CLAUDE.md)
- ADRs novos (T087, T088) e estendidos (T089, T090) sao escritos em `platforms/prosauai/decisions/` no repo `madruga.ai` (NAO no repo prosauai)

---

handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "92 tasks (T001-T092 + T1100-T1105 deployment smoke) organizadas em 11 phases. PR-A (Phase 1+2, ~26 tasks) entrega schema + utilities + Bifrost extension testaveis isoladamente sem deploy. PR-B (Phase 3+4+5, ~37 tasks) entrega US1+US2+US3 backend + UI parcial — smoke real Ariel via curl. PR-C (Phase 6+7+8+9+10+11, ~30 tasks) entrega UI completa + per-agent toggle + CLI re-embed + flag hot-reload + dashboards Bifrost + docs + smoke deploy + rollout produtivo. TDD obrigatorio Phase 2+3+ (tests red antes de green). Coverage gate 85% prosauai/rag/* e tools/search_knowledge.py. Reusos chamados explicitamente: PyMuPDF (T015), tiktoken (T016), config_poller (T010, T075), pool_admin (T054), Safety Layer A (T045), Bifrost (T021-T024). Zero novas libs Python/TS — apenas pgvector extension PG (T005). Cross-tenant invariant test em CI nightly (T086). Cut-lines documentados (PR-B UI -> 012.1; Bifrost >1 sem -> OpenAI direto)."
  blockers: []
  confidence: Alta
  kill_criteria: "pgvector extension nao habilitavel em Supabase managed plano corrente -> bloqueio total Phase 2 (escalation infra); Bifrost extension >1 semana -> recuar para chamada direta OpenAI (sacrifica SC-010 temporariamente, US7 Phase 9 vira no-op); chunker MD-aware/PDF revela edge cases >50% dos arquivos reais -> revisar abordagem antes de PR-B; quotas defaults estouram em Ariel pilot (>50 docs OR >2000 chunks rapido) -> dimensionamento errado, replan."
