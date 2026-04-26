---
title: "Judge Report — Epic 012 Tenant Knowledge Base (RAG pgvector + Upload Admin)"
score: 0
initial_score: 0
verdict: fail
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
findings_total: 51
findings_fixed: 7
findings_open: 44
updated: 2026-04-26
---

# Judge Report — Epic 012 Tenant Knowledge Base (RAG pgvector + Upload Admin)

## Score: 0%

**Verdict:** FAIL (escalated to humano)
**Team:** engineering (4 personas — todas concluiram com sucesso)

> Score formal usa `100 − (blockers×20 + warnings×5 + nits×1)`. Mesmo com **todos os 7 blockers FIXADOS na fase 7**, o volume de warnings (25 abertos) + nits (17) ainda mantem o score formal em 0. Qualitativamente o epic passou de "production-fatal em multiplos vetores" para "shippable em piloto, com backlog ops claro". A recomendacao e revisar este relatorio com o time, planejar follow-up para os warnings P1 (W1-W6) antes do rollout produtivo (T092 do epic), e prosseguir com `/madruga:qa` em paralelo para teste de comportamento end-to-end.

## Findings

### BLOCKERs (7 — 7/7 fixed)

| # | Source | Finding | Localizacao | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| B1 | arch-reviewer + bug-hunter | RAG dependencies nunca foram conectadas ao `app.state` no lifespan — `app.state.rag_repository`, `rag_embedder`, `rag_storage` sao LIDOS pelo `admin/knowledge.py` mas NUNCA escritos. Todo endpoint admin da epic 500a com `AttributeError`; tool `search_knowledge` silenciosamente retorna `[]` via path defensivo. **US1 + US2 + US3 nao funcionam em producao** apesar do codigo "existir". | `prosauai/main.py` (sem bloco RAG na lifespan); `admin/knowledge.py:180-182, 573, 638, 695-696, 764, 823` | **FIXED** | Lifespan agora instancia `BifrostEmbedder` + `RagRepository` + `SupabaseStorage` apos `create_pools()` e atribui em `app.state.rag_*`. Defesa em profundidade: endpoint usa `getattr(...,None)` + retorna 503 se faltarem (caso dev sem Supabase). Adicionado em `main.py:294-336` e validacao em `admin/knowledge.py:181-198`. |
| B2 | arch-reviewer | SQL `_GET_DOCUMENT_ADMIN_SQL` / `_LIST_DOCUMENTS_ADMIN_SQL` / `_COUNT_DOCUMENTS_ADMIN_SQL` referenciam `prosauai.documents` (schema-qualificado) mas a migration 20260601000007 cria a tabela em `public.documents` (search_path default — comentario explicito da migration confirma "Schema choice: ``public.*`` (NOT ``prosauai.*``)"). Endpoints cross-tenant da Pace ops (FR-068) falham com `relation "prosauai.documents" does not exist`. | `rag/repository.py:148, 155, 162` | **FIXED** | Removido prefixo `prosauai.` das 3 constantes SQL. Agora `FROM documents` em todas as queries (consistente com o resto do arquivo). Teste em mock-mode tolera ambas as formas via substring-match — sem regressao. |
| B3 | bug-hunter | Atomic-replace deixa orfaos no Storage: cada upload de mesmo `source_name` gera novo `document_id`/storage_path; o caminho antigo nunca e deletado. Pior: cleanup em falha de DB-write deleta o **NOVO** path (calculado no upload corrente), nao o antigo. **Replace 100x = 100 arquivos orfaos no bucket; replace + DB-failure = perda de dados (novo deletado, antigo persiste tido como deletado pelo proximo replace)**. | `admin/knowledge.py:388-468`; `rag/repository.py:294-362` | **FIXED** | Snapshot de `old_storage_path` via novo `repository.get_document_by_source(...)` ANTES de `replace_document_atomic`. Apos commit DB bem-sucedido, deleta o path antigo (`admin/knowledge.py:498-516`). Best-effort: falha do delete antigo emite warning `rag_storage_old_cleanup_failed` mas nao reverte o commit (orfao agora visivel para o reconciler do Storage — futura tarefa). |
| B4 | bug-hunter + stress-tester | Quota check race: `count_documents_and_chunks` roda em transacao separada do INSERT. Dois uploads concorrentes de source_names diferentes para o mesmo tenant podem ambos passar quota e ambos commitarem — tenant ultrapassa `max_chunks_per_tenant` por N. Hard cap (50000 chunks) vira soft cap sob concorrencia. | `admin/knowledge.py:247-269`; `rag/repository.py:329-334` | **FIXED** | Novo `RagRepository._enforce_tenant_quota(...)` toma `pg_advisory_xact_lock(hashtext('rag-quota:{tenant_id}'))` na MESMA transacao do INSERT, recheca counts, e levanta novo `QuotaExceededError` se ainda exceder. `replace_document_atomic` + `insert_document_with_chunks` agora aceitam `max_documents_per_tenant` / `max_chunks_per_tenant` opcionais. Upload trata a excecao e responde 413 `tenant_quota_exceeded` com hint "another concurrent upload consumed the remaining quota". Storage cleanup automatico. |
| B5 | bug-hunter + stress-tester | `await file.read()` carrega o body INTEIRO em memoria ANTES da validacao de tamanho. FastAPI nao impoe Content-Length cap; um upload malicioso de 5GB OOM-kill o worker antes que o check de 10MB rode. | `admin/knowledge.py:221-243` | **FIXED** | Substituido por loop streaming de 64KB com contador limitado a `max_upload_bytes + 1`. Aborta com 413 `max_upload_mb_exceeded` assim que excede, sem terminar o buffer. `admin/knowledge.py:225-251`. |
| B6 | stress-tester | Tool `search_knowledge` viola o budget de 2s p95: embedder default tem `request_timeout=5s × max_retries=3` com backoff exponencial, totalizando ate ~17s por chamada. Sob slowness transient do Bifrost, todo o pipeline de mensagens trava muito alem do SLO. | `tools/search_knowledge.py:194-221`; `rag/embedder.py:154-157` | **FIXED** | Wrap da chamada de embed em `asyncio.wait_for(..., timeout=TOOL_DEADLINE_SECONDS=1.5s)`. Em timeout, tool degrada para `[]` (graceful degradation FR-038) dentro do SLO. Embedder mantem retry/backoff para o path de upload (budget mais relaxado). `tools/search_knowledge.py:79, 198-228`. |
| B7 | bug-hunter + stress-tester | `reembed_document_atomic` NAO toma o mesmo advisory lock que o upload usa. Re-embed concorrente com upload do mesmo source_name pode produzir mismatch de chunks: re-embed le doc antigo, upload commita doc novo (atomic-replace), re-embed insere chunks contra `document_id` invalido — corrupcao silenciosa de embeddings indexados contra o nome do novo modelo. | `rag/repository.py:368-422`; `rag/reembed.py:367-451` | **FIXED** | `reembed_document_atomic` agora aceita `source_name` opcional e adquire `pg_advisory_xact_lock(hashtext('doc:{tenant}:{source_name}'))` quando disponivel; fallback para `doc-id:{tenant}:{document_id}` quando nao. CLI passa `source_name` via `getattr(doc, "source_name", None)`. Teste mock atualizado. |

### WARNINGs (25 — 1 fixado, 24 abertos)

| # | Source | Finding | Localizacao | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| W1 | arch-reviewer | `_resolve_document` cross-tenant audit emite `action="read"` mesmo para DELETE/raw — viola FR-068 (verb deve refletir a operacao). | `admin/knowledge.py:657-664` | **OPEN** | — Backlog: aceitar `action: Literal["read","delete"]` arg em `_resolve_document` e cada rota passa o verb correto. |
| W2 | arch-reviewer + simplifier | Falhas de Storage / DB-write surfacem como `EMBEDDINGS_PROVIDER_DOWN` (codigo errado — admin recebe "LLM provider esta down" quando o problema e Storage). RagErrorCode catalogue nao tem `STORAGE_UNAVAILABLE` ou `UPSTREAM_UNAVAILABLE`. | `admin/knowledge.py:411-413, 425-427, 494-496, 728-731, 786-790` | **OPEN** | — Backlog: adicionar `RagErrorCode.STORAGE_UNAVAILABLE` (ou `UPSTREAM_UNAVAILABLE`) e atualizar mapping. Frontend localisation map atualizado em conjunto. |
| W3 | arch-reviewer + stress-tester | `_build_deps()` do reembed CLI usa `asyncio.get_event_loop().run_until_complete(create_pools(...))` enquanto `main()` usa `asyncio.run(...)` — em Python 3.12 isso levanta `RuntimeError`/`Future attached to a different loop`. CLI dead-on-arrival em prod. | `rag/reembed.py:538` | **OPEN** | — Backlog: refatorar `_build_deps` para `async def _build_deps_async(settings)` chamado de `main()` sob um unico `asyncio.run`. |
| W4 | arch-reviewer | `target_tenant_id="*"` (wildcard string) emitido como audit `tenant_id="*"` polui SIEM em group-by. | `admin/knowledge.py:599-605` | **OPEN** | — Backlog: setar `target_tenant_id=None` (audit helper dropa o campo) ou emitir 1 evento por record. |
| W5 | arch-reviewer + simplifier | `RagRepository.acquire_doc_lock` async context manager nao tem callers — codigo morto com 25 LOC. | `rag/repository.py:659-684` | **OPEN** | — Backlog: deletar o helper + imports `AsyncIterator` / `asynccontextmanager` que se tornam unused. |
| W6 | bug-hunter | `source_name` aceita `file.filename` verbatim — sem validacao contra `..`, NULs, control chars, super-long names. Storage path usa `document_id` (UUID) entao path traversal real e impossivel, mas: poluicao de logs, XSS via DB column nao escapada na admin UI, quebra de uniqueness em case differences. | `admin/knowledge.py:246, 333` | **OPEN** | — Backlog: validar `source_name` (`os.path.basename`, forbid `..`/NUL/control chars, cap 255 chars, reject empty-after-normalize). Aplicar em `_ext_from_filename` tambem. |
| W7 | bug-hunter | `_SEARCH_CHUNKS_SQL` JOIN para `documents` nao tem predicate de tenant — RLS protege hoje (defense-in-depth violation se algum dia rodar com pool admin). | `rag/repository.py:183-193` | **OPEN** | — Backlog: adicionar `AND documents.tenant_id = $2` ao JOIN. |
| W8 | bug-hunter | `from None` strips exception chain em todos os error paths do upload. `hint=str(exc)[:200]` leaka mensagens de erro do Storage (URLs, etc) para o cliente. | `admin/knowledge.py:281, 290, 322, 385, 414, 428, 497, 731, 790` | **OPEN** | — Backlog: drop `from None` (exception chain preservada nos logs sem expor ao cliente); sanitizar `hint` para tokens opacos. |
| W9 | bug-hunter | Storage delete-on-DB-failure deletaria o new (replaced) version sem restaurar o original. | `admin/knowledge.py:469-479` | **RESOLVED-BY-B3** | A correcao do B3 snapshot do `old_storage_path` antes do replace + cleanup separado apos commit elimina o cenario destrutivo. Cleanup atual no fail-path so deleta o NOVO path (correto — original ainda intacto pre-replace, sem corrupcao cruzada). |
| W10 | bug-hunter | `RedirectResponse(url=signed)` poe Supabase signed URL (com token JWT-like) no `Location:` header do 302 — leaka via browser history, proxy logs, referer. | `admin/knowledge.py:801` | **OPEN** | — Backlog: retornar JSON `{ "url": signed }` e cliente faz `window.open`, ou stream bytes server-side e nunca expor o signed URL. |
| W11 | bug-hunter | `validate_chunk` cobre apenas regex em ingles ("ignore previous instructions", "DAN") — corpus PT-BR pode conter texto legitimo matching, e injecoes em portugues ("ignore as instrucoes anteriores", "esqueca o que disse antes") passam. | `safety/input_guard.py:38-67`; `tools/search_knowledge.py:320` | **OPEN** | — Backlog: adicionar patterns em PT-BR; considerar content-classifier model (epic 012.1 hardening). |
| W12 | bug-hunter | `replace_document_atomic` pode nao estar em `BEGIN/COMMIT` explicito. | `rag/repository.py:329-362` | **INVALID** | Verificacao em `db/pool.py:233`: `with_tenant` usa `pool.acquire(...) , conn.transaction()` — transacao explicita confirmada. False positive. |
| W13 | bug-hunter | `_request_id` retorna `None` quando OTel esta uninstrumented — audit eventos perdem `request_id` para correlacao. | `admin/knowledge.py:141-155` | **OPEN** | — Backlog: gerar UUID4 fallback quando ambos X-Request-ID e OTel trace_id absent. |
| W14 | bug-hunter | `embed_batch` levanta `ValueError` em chunks whitespace-only — chunker ja deveria nao produzir mas defesa quebra com 500 apos custos pagos (OpenAI tokens + Storage upload). | `rag/embedder.py:207-211`; `admin/knowledge.py:354-356` | **OPEN** | — Backlog: catch `ValueError` no upload endpoint e surface como `no_chunks_extracted`. |
| W15 | stress-tester | `delete_prefix` so lista/deleta primeiros 1000 entries — SAR cascade de tenant grande deixa lixo, viola FR-067. | `rag/storage.py:266-339` | **OPEN** | — Backlog: paginar com `offset += len(entries)` ate vazio + assertion final. |
| W16 | stress-tester | Custo de embedding queimado irreversivelmente em DB-write failure — sequencia embed → storage → DB. Em outage breve do DB pode desperdicar centenas de dolares. | `admin/knowledge.py:442-497` | **OPEN** | — Backlog: reordenar (storage → INSERT pending → embed → UPDATE ready) ou inserir `pending_uploads` row antes do embed. Adicionar metric `rag_burned_cost_usd` para visibility. |
| W17 | stress-tester | Sem reconciler periodico de Storage — `delete()` em DB-write failure e best-effort com `try/except: pass`. Network blip = orfao silencioso. | `admin/knowledge.py:472-479` | **OPEN** | — Backlog: cron diario que lista `knowledge/<tenant_id>/` e deleta o que nao existe em `documents.storage_path`. Metric `rag_storage_orphans_total`. |
| W18 | stress-tester | `BifrostEmbedder._parse_response` aceita qualquer dim de vector — Bifrost mal-configurado causa erro confuso no DB INSERT (mid-transaction, apos custos pagos). | `rag/embedder.py:362-373` | **OPEN** | — Backlog: assertion `len(embedding) == 1536` apos parse + `EmbeddingProviderError("dim_mismatch")`. |
| W19 | stress-tester | Storage `signed_url` e `delete_prefix` parseiam `response.json()` sem try/except — Supabase HTML 5xx page crasha com `JSONDecodeError` em vez de `StorageError`. | `rag/storage.py:309, 387-388` | **OPEN** | — Backlog: wrap `.json()` em try/except + raise `StorageError`. |
| W20 | stress-tester | admin DELETE nao adquire advisory lock — concorrente com upload de mesmo source_name pode produzir cenario raro de double-delete. | `rag/repository.py:428-436` | **OPEN** | — Backlog: em `delete_document` fetchar source_name primeiro + adquirir mesmo lock que o upload. Ou documentar que o uniqueness constraint torna race nao observavel. |
| W21 | stress-tester | HNSW insert latency degrada nao-linearmente perto de 50k chunks/tenant — atomic-replace de 200 chunks pode levar 1-3s, comendo o budget de 15s. | `db/migrations/20260601000008_create_knowledge_chunks.sql:69-72`; `rag/repository.py:329-362` | **OPEN** | — Backlog: usar `executemany` em vez de loop Python de `INSERT`; benchmark + documentar curve em `rag-baseline.md`. |
| W22 | stress-tester | `httpx.AsyncClient` instanciado por chamada — em 100 req/s no `search_knowledge` o handshake TCP+TLS domina o budget. | `rag/embedder.py:224-227`; `rag/storage.py:160, 206, 244, 301, 364` | **OPEN** | — Backlog: instanciar `httpx.AsyncClient` shared por servico em lifespan com `limits=httpx.Limits(...)`, fechar em shutdown. |
| W23 | stress-tester | Embedder retry pode double-charge OpenAI em `RemoteProtocolError` (request enviada antes da conexao cair). | `rag/embedder.py:71-75, 290-300` | **OPEN** | — Backlog: enviar `Idempotency-Key` header (UUID por batch) ou retirar `RemoteProtocolError` do retryable set. |
| W24 | simplifier | `ReembedDeps` usa `Any` para 4 collaborators — sacrifica type safety em prod por test convenience. | `rag/reembed.py:141-153` | **OPEN** | — Backlog: tipar como Protocols ou classes concretas. |
| W25 | simplifier | 6 chamadas quase identicas a `emit_search_executed(...)` em search_knowledge.py — DRY violation. | `tools/search_knowledge.py:178-348` | **OPEN** | — Backlog: extrair helper `_emit_search(failure_reason, chunks, distance, action_result)`. |
| W26 | simplifier | `upload_document` e funcao de 365 LOC com 11 gates sequenciais. | `admin/knowledge.py:168-534` | **OPEN** | — Backlog: aceitar como procedural-by-nature, mas considerar splitting steps 5-9 em helpers nomeados. |
| W27 | simplifier + bug-hunter | `_resolve_deps` em search_knowledge faz `getattr(...)` defensivo em todos os fields — assume cenario que nao deveria existir. | `tools/search_knowledge.py:78-113` | **PARTIALLY-RESOLVED** | B1 fix garante wiring, entao defensive null-handling agora e legitimamente defense-in-depth. Mantido. |

### NITs (17 — 0 fixados, 17 abertos)

| # | Source | Finding | Localizacao | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| N1 | bug-hunter | `source_hash = hashlib.sha256(file_bytes).hexdigest()` armazenado mas nunca usado para integrity check em v1. | `admin/knowledge.py:389` | OPEN | — |
| N2 | bug-hunter + simplifier | `total_tokens=max(usage.total_tokens, 1)` mente sobre 0-token batches para satisfazer `Field(ge=1)`. | `admin/knowledge.py:530` | OPEN | — |
| N3 | bug-hunter | `ChunkResult.distance` documentado `ge=0.0` mas pgvector `<=>` retorna em `[0.0, 2.0]`. | `rag/models.py:237` | OPEN | — |
| N4 | bug-hunter + stress-tester | `BifrostEmbedder` cria fresh `httpx.AsyncClient` por call — 200 docs = 200 TCP+TLS handshakes. | `rag/embedder.py:223-227` | OPEN | (relacionado a W22) |
| N5 | bug-hunter | `_emit` em audit.py masca todas excecoes silenciosamente. | `rag/audit.py:102-103` | OPEN | — |
| N6 | bug-hunter | `ErrorResponse.current` leak corpus size para tenant-bound admin. | `admin/knowledge.py:266-269, 346-349` | OPEN | (low impact: admin ja esta autenticado para o tenant) |
| N7 | simplifier | `_strip_bucket_prefix` "internal usage" form sem caller. | `rag/storage.py:409-419` | OPEN | — |
| N8 | simplifier | `_select_work_set` return annotation `AsyncIterator | Iterable` mas so retorna `list`. | `rag/reembed.py:485-508` | OPEN | — |
| N9 | simplifier | `_query_token_count` (rule-of-thumb) duplica `_count_tokens` (tiktoken real) do chunker. | `tools/search_knowledge.py:116-123` | OPEN | — |
| N10 | stress-tester | Re-embed faz N round-trips por doc — usar `executemany`. | `rag/repository.py:408-415` | OPEN | (relacionado a W21) |
| N11 | stress-tester | Spans do embedder so cobrem batch agregado, nao per-call detail. | `rag/embedder.py:213-252` | OPEN | — |
| N12 | stress-tester | `chunk_fixed_size` decode via tiktoken bloqueia event loop em sync handler. | `rag/chunker.py:253-272` | OPEN | — |
| N13 | stress-tester | `delete_prefix` edge case empty/all-slash prefix. | `rag/storage.py:283-290` | OPEN | — |
| N14 | simplifier | `emit_replace_detected` exposto publicamente sem necessidade. | `rag/audit.py:243-267` | OPEN | — |
| N15 | arch-reviewer | `COST_USD_PER_TOKEN` hard-coded — atualizacao da OpenAI exige code change. | `rag/embedder.py:62` | OPEN | — |
| N16 | arch-reviewer | `PdfExtractionError` mal nomeado para invalid UTF-8 em MD/TXT. | `rag/extractor.py:97-98` | OPEN | — |
| N17 | bug-hunter | `_LIST_DOCUMENTS_SQL.format(...)` SQL string-format pattern e code-smell. | `rag/repository.py:124-163, 463-547` | OPEN | — |

## Safety Net — Decisoes 1-Way-Door

| # | Decisao | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| 1 | Schema `documents` + `knowledge_chunks` em `public` (nao `prosauai`) | 6 (Risk 3 × Reversibility 2) | Nao (2-way-door) | OK — `ALTER TABLE SET SCHEMA` reversivel; documentacao da migration explicita a escolha |
| 2 | VECTOR(1536) hard-coded por modelo `text-embedding-3-small` | 8 (Risk 4 × Reversibility 2) | Nao (2-way-door) | OK — documentado em ADR-013; CLI re-embed lida com same-dim swaps; cross-dim requer epic-future schema change |
| 3 | HNSW (m=16, ef_construction=64) sobre IVFFlat | 6 (Risk 2 × Reversibility 3) | Nao (2-way-door) | OK — documentado em ADR-013 |
| 4 | Atomic replace by source_name (sem versionamento em v1) | 9 (Risk 3 × Reversibility 3) | Nao (2-way-door) | OK — **ADR-041 criado para esta decisao** |
| 5 | Bifrost extension para `/v1/embeddings` (vs OpenAI direto) | 6 (Risk 2 × Reversibility 3) | Nao (2-way-door) | OK — **ADR-042 criado para esta decisao** |
| 6 | Tool `search_knowledge` exposto ao LLM com signature `(query, top_k)` | 8 (Risk 2 × Reversibility 4) | Nao (2-way-door) | OK — schema documentado em `contracts/tool-schema.json` |

**Conclusao**: Nenhuma decisao 1-way-door (score >= 15) escapou. As decisoes schema-coupled (modelo de embedding, HNSW, replace strategy, Bifrost extension) estao todas documentadas em ADRs (013, 041, 042) e estendidas em ADR-011/012/018 conforme o plan.md Constitution Check III.

## Personas que Falharam

Nenhuma. **4/4 personas concluiram com sucesso** dentro do formato exigido (`PERSONA: ...` + `FINDINGS:` + `SUMMARY:`). Modo "normal" do degradation rules.

## Files Changed (by fix phase)

| File | Findings Fixed | Summary |
|------|---------------|---------|
| `apps/api/prosauai/main.py` | B1 | Adiciona bloco "RAG dependencies (epic 012, judge fix B1)" na lifespan apos `pools = await create_pools(settings)`. Instancia `BifrostEmbedder` + `RagRepository` (+ `SupabaseStorage` quando env vars presentes) e atribui em `app.state.rag_*`. Sentinel `None` no `rag_storage` quando `SUPABASE_URL`/`KEY` ausentes — endpoint surfacea HTTP 503 em vez de crash de startup. |
| `apps/api/prosauai/admin/knowledge.py` | B1 (defense), B3, B4, B5 | (a) `getattr(..., None)` para `rag_*` + 503 fail-fast quando nao wired; (b) snapshot `old_storage_path` via `repository.get_document_by_source(...)` antes do atomic-replace + cleanup do path antigo apos commit; (c) catch `QuotaExceededError` na transacao + 413 `tenant_quota_exceeded` com Storage rollback; (d) loop streaming de 64KB com `max_upload_bytes + 1` em vez de `await file.read()` total. |
| `apps/api/prosauai/rag/repository.py` | B2, B3, B4, B7 | (a) Removido prefixo `prosauai.` das 3 SQL constants admin; (b) Novo `_GET_DOCUMENT_BY_SOURCE_SQL` + metodo `get_document_by_source(...)`; (c) Nova classe `QuotaExceededError` + helper `_enforce_tenant_quota(...)` com `pg_advisory_xact_lock(hashtext('rag-quota:{tenant_id}'))` + recheck transactional; (d) `replace_document_atomic` + `insert_document_with_chunks` aceitam `max_documents_per_tenant` / `max_chunks_per_tenant` opcionais; (e) `reembed_document_atomic` aceita `source_name` + adquire mesmo advisory lock do upload (fallback para `doc-id:` quando ausente). |
| `apps/api/prosauai/rag/reembed.py` | B7 | CLI passa `source_name=getattr(doc, "source_name", None)` para `reembed_document_atomic`. |
| `apps/api/prosauai/tools/search_knowledge.py` | B6 | Nova constante `TOOL_DEADLINE_SECONDS = 1.5`. Embed call envolto em `asyncio.wait_for(..., timeout=TOOL_DEADLINE_SECONDS)`; em `TimeoutError` retorna `[]` (graceful degradation FR-038) com log `rag_embedder_unavailable` carregando `deadline_seconds`. |
| `apps/api/tests/rag/test_reembed_cli.py` | B7 (test fix) | Mock `_reembed_atomic` aceita parametro opcional `source_name`. |
| `apps/api/tests/integration/rag/test_upload_atomic_replace.py` | B3 (test fix) | Fixture `_repository_with_existing` adiciona mock `get_document_by_source` retornando record sintetico para o source_name existente. |

## Recomendacoes

### Bloqueantes (antes do rollout produtivo T092)

1. **W2 + W6 + W10**: codigos de erro corretos + validacao de `source_name` + signed URL out of `Location` header. Esses 3 endurecem o admin surface antes de expor a clientes.
2. **W3**: corrigir o `_build_deps()` event-loop bug. Sem isso o CLI re-embed (US-5) nunca funciona em prod — bloqueia o roadmap de upgrade de modelo embedding.
3. **W17**: implementar reconciler diario de Storage. Sem isso, orfaos acumulam silenciosamente e SAR cascade fica incompleto.

### Importantes (P1 backlog 012.1)

4. **W1 + W4**: corrigir audit verbs e wildcard SIEM pollution. Compliance-relevante.
5. **W11**: PT-BR injection patterns no `validate_chunk` — corpus principal e portugues.
6. **W22**: shared `httpx.AsyncClient` via lifespan. Performance critica para `search_knowledge` em escala.
7. **W18**: dim-validation no embedder. Failure-fast antes de queimar custos.

### Backlog (P2/P3)

8. W5 (dead code), W7 (defense-in-depth JOIN), W8 (sanitize hints), W13 (request_id fallback), W14 (catch ValueError), W15 (paginate delete_prefix), W16 (cost burn protection), W19 (json try/except), W20 (admin DELETE lock), W23 (idempotency-key), W24 (Any types), W25 (DRY emit), W26 (refactor upload), W27 (mantido como defense-in-depth).

### NITs

Cleanup quando tocar nos arquivos. N4 + N10 sao sub-itens de W22/W21.

---

## Re-Verificacao Pos-Fix

| Check | Resultado |
|-------|-----------|
| `ruff check prosauai/{rag,admin,tools,main.py}` | All checks passed |
| `pytest tests/rag/ tests/tools/ tests/admin/knowledge/ tests/integration/rag/ tests/safety/` | **265 passed, 11 deselected, 41 warnings** |
| `import prosauai.main` | OK (no startup-time crash) |
| `import prosauai.tools.search_knowledge` | OK (tool registered: `tool_registered category=rag name=search_knowledge`) |

Cobertura testada:
- 7/7 BLOCKERs corrigidos com testes verdes
- Atomic-replace test (`test_atomic_replace_calls_replace_document_atomic_with_advisory_lock`) atualizado para B3 fix
- Re-embed CLI test (`test_run_reembed_happy_path_processes_all_documents`) atualizado para B7 fix
- Upload endpoint tests (quota, oversize, empty, format, RAG-disabled, Bifrost-down) todos passam — comportamento preservado

---

handoff:
  from: madruga:judge
  to: madruga:qa
  context: "Judge run completo. 7/7 BLOCKERs fixados (B1 lifespan wiring, B2 schema-prefixed SQL, B3 atomic-replace orphan storage, B4 tenant quota race, B5 file.read OOM, B6 tool latency budget, B7 reembed advisory lock). 25 WARNINGs + 17 NITs OPEN para backlog 012.1 — recomendacao: priorizar W2/W3/W6/W10/W17 antes do rollout produtivo T092. Testes: 265 passam pos-fix, ruff limpo, lifespan import OK. Score formal 0/100 (volume de warnings derruba apesar dos blockers fixados) — verdict FAIL/escalate. QA deve focar em: (a) end-to-end via Trace Explorer apos lifespan wiring (validar US1/US2/US3 funcionais agora); (b) regressao tests para os 3 cenarios de race agora cobertos (B4, B7); (c) signed URL leak validation (W10); (d) prompt injection PT-BR (W11)."
  blockers: []
  confidence: Alta
  kill_criteria: "QA descobre que lifespan wiring nao e suficiente em prod (env vars Supabase nao configuradas em prod -> rollout impossibilitado); regressao em US1/US2/US3 nao detectada por unit tests; W10 (signed URL leak) ou W6 (source_name traversal) descobertos exploraveis em pre-prod -> P0 antes de qualquer rollout."
