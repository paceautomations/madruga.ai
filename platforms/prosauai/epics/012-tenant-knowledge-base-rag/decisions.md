---
epic: 012-tenant-knowledge-base-rag
created: 2026-04-24
updated: 2026-04-24
---
# Registro de Decisoes — Epic 012 (DRAFT)

> Decisoes tentativas em draft mode. Promocao (normal mode depois) fara delta review e marcara revisoes com `[REVISADO YYYY-MM-DD]`.

1. `[2026-04-24 epic-context]` Formatos v1: MD + text + PDF apenas. DOCX/URL crawl adiados para 012.1. PDF reusa PyMuPDF do epic 009. (ref: Q1-A draft 2026-04-24)
2. `[2026-04-24 epic-context]` Embedding provider: OpenAI text-embedding-3-small (1536 dim) via Bifrost extension. Alinhado com schema ADR-013. Custo ~R$0.0001/chunk. (ref: Q2-A; ADR-013 confirmed; ADR-042 novo)
3. `[2026-04-24 epic-context]` Chunking strategy: Markdown header-aware para .md (chunka em ##/###); fixed-size 512 tokens + 50 overlap para PDF/text. Stdlib only <100 LOC. (ref: Q3-B)
4. `[2026-04-24 epic-context]` Retrieval integration: RAG como tool opcional — search_knowledge(query, top_k=5) no tool registry. LLM decide quando chamar. (ref: Q4-B; blueprint tools/registry.py)
5. `[2026-04-24 epic-context]` Scope KB: per-tenant default com agent_id opcional (IS NULL = shared). Schema ADR-013 ja acomoda. (ref: Q5-B; ADR-013)
6. `[2026-04-24 epic-context]` Upload UX: sync upload ate 10MB. Async queue adiada para 012.1. (ref: Q6-A)
7. `[2026-04-24 epic-context]` Document lifecycle: replace by source_name (atomic transaction). Sem versionamento em v1. (ref: Q8-I-A; ADR-041 novo)
8. `[2026-04-24 epic-context]` Raw file storage: Supabase Storage bucket knowledge path {tenant_id}/{document_id}.{ext}. Permite re-chunking/re-embedding futuro sem re-upload. (ref: Q8-II-A)
9. `[2026-04-24 epic-context]` Re-embedding on model change: via Supabase Storage reprocess — CLI python -m prosauai.rag.reembed --tenant X. Coluna embedding_model TEXT NOT NULL em knowledge_chunks. (ref: Q7 resolved by Q8-II-A)
10. `[2026-04-24 epic-context]` Nova tabela documents(id, tenant_id, source_name, source_hash, source_type, storage_path, size_bytes, uploaded_by_user_id, uploaded_at, chunks_count, embedding_model, UNIQUE(tenant_id, source_name)) com RLS. (ref: ADR-011 + ADR-013 extended)
11. `[2026-04-24 epic-context]` knowledge_chunks schema expansao: adiciona document_id FK CASCADE + chunk_index + embedding_model. Cascade delete simplifica lifecycle. (ref: ADR-013 extended)
12. `[2026-04-24 epic-context]` HNSW index: hnsw(embedding vector_cosine_ops) WITH (m=16, ef_construction=64). Query cosine distance. (ref: ADR-013 confirmed)
13. `[2026-04-24 epic-context]` Retrieval params: default top_k=5. Distance threshold nao aplicado em v1 (LLM filtra no contexto). Threshold per-tenant adiado para 012.1. (ref: Q4-B; simplicity-first)
14. `[2026-04-24 epic-context]` Bifrost extension: novo provider OpenAI para /v1/embeddings com rate limiting + spend tracking igual ao chat completions. prosauai/rag/embedder.py chama Bifrost, nao OpenAI direto. (ref: ADR-042 novo; ADR-012 billing)
15. `[2026-04-24 epic-context]` Feature flag: tenants.yaml bloco rag: {enabled, top_k, min_distance?, max_upload_mb} per-tenant. Default disabled. Config_poller do epic 010 re-le em <=60s. (ref: pattern epic 010)
16. `[2026-04-24 epic-context]` Rollout: Ariel disabled -> enabled com 1 FAQ MD curto (smoke) -> ResenhAI 7d depois com catalogo PDF real. Sem shadow mode — RAG ligado = tool disponivel. (ref: simplificado vs 010/011)
17. `[2026-04-24 epic-context]` Admin UI: nova aba Base de Conhecimento no sidebar. Tabela com source_name, source_type, chunks_count, size, uploaded_at, actions. Upload dialog drag-drop. (ref: epic 008 extension)
18. `[2026-04-24 epic-context]` LGPD: DELETE /admin/knowledge/documents/{id} cascade (DB + Storage). SAR endpoint (ADR-018) estendido para listar documents do tenant. Cross-tenant embedding proibido via RLS. (ref: ADR-018 extended)
19. `[2026-04-24 epic-context]` Tool call observability: search_knowledge execucao vira span OTel rag.search no trace. Atributos: rag.query_tokens, rag.chunks_returned, rag.distance_top1, rag.cost_usd. Aparece no Trace Explorer. (ref: pattern epic 002)
20. `[2026-04-24 epic-context]` Eval integration: tool call marca eval_scores.details.rag_used=true. Epic 011 correlaciona RAG vs quality. (ref: epic 011 hook)
21. `[2026-04-24 epic-context]` Sem re-index periodico HNSW (ADR-013 escolheu HNSW para evitar isso). ANALYZE nightly via retention-cron. (ref: ADR-013)
22. `[2026-04-24 epic-context]` Prompt injection surface: chunks retornados podem conter injecao (OWASP #1 RAG injection). Safety Layer A (epic 005) valida chunks antes de LLM. Hardening RAG-especifico adiado para 012.1. (ref: ADR-016 extended)
