---
title: 'ADR-041: Knowledge document lifecycle: atomic replace by source_name'
status: Accepted
decision: v1 do RAG (epic 012) NAO versiona documentos. Upload com
  `source_name` ja existente e tratado como **atomic replace**: em
  uma unica transacao, DELETE chunks antigos -> DELETE row antiga em
  `documents` -> DELETE arquivo no Supabase Storage -> INSERT novo
  document + chunks + Storage upload. Concorrencia serializada por
  `pg_advisory_xact_lock(hashtext('doc:{tenant_id}:{source_name}'))`.
  `UNIQUE(tenant_id, source_name)` no DB enforces o invariant.
alternatives: Versionamento explicit (`documents.version`),
  append-only com soft-delete, fingerprint dedup automatico,
  hard-delete + re-upload manual obrigatorio
rationale: KISS para v1. Replace cobre 95% do caso real (atualizar
  FAQ ou regulamento) sem overhead de UI/SQL/audit de versioes. Custo
  de re-embed total e baixo (~R$0.005 por replace tipico de 200
  chunks). Versionamento promovido para 012.1 se 2+ tenants pedirem.
---

# ADR-041: Knowledge document lifecycle — atomic replace by source_name

**Status:** Accepted | **Data:** 2026-04-26 | **Relaciona:** [ADR-013](ADR-013-pgvector-tenant-knowledge.md), [ADR-018](ADR-018-data-retention-lgpd.md), [ADR-042](ADR-042-bifrost-embeddings-extension.md), `../epics/012-tenant-knowledge-base-rag/`

> **Aceite:** entregue como descrito em PR-B (epic 012 / T020 +
> T029 + T030). Validado por `tests/integration/rag/test_upload_atomic_replace.py`
> + smoke quickstart Step 6.

> **Escopo:** Epic 012 (Tenant Knowledge Base — RAG). Aplica-se a
> `apps/api/prosauai/rag/repository.py`,
> `apps/api/prosauai/admin/knowledge.py` (endpoint `POST /admin/knowledge/documents`),
> `apps/api/db/migrations/20260601000007_create_documents.sql`
> (constraint `UNIQUE(tenant_id, source_name)`).

## Contexto

O epic 012 entrega o caminho minimo para um tenant subir documentos
(PDF, MD, TXT) que o agente consulta via tool `search_knowledge`. O
caso de uso real e simples:

> "Atualizei o FAQ. Quero que o agente passe a usar a versao nova
> agora."

Tres dimensoes precisam ser definidas no v1:

1. **Identidade**: como o tenant referencia "o mesmo documento" entre
   uploads? Por nome do arquivo? Por hash? Por ID gerado?
2. **Lifecycle**: o que acontece com o documento antigo quando o novo
   chega? Coexistem? Substitui? Branch?
3. **Concorrencia**: dois admins (ou o mesmo admin em duas abas) que
   re-upload simultaneo do mesmo `source_name` — quem ganha?

A spec do epic 012 (FR-015, FR-016, decisao 7 do pitch) ja prescreveu
"replace by source_name" como caminho preferido. Este ADR formaliza
o trade-off e o algoritmo concreto, alinhado com o pattern de
isolation-cascade do ADR-013.

Riscos do **nao-decidir** este ponto:

- Re-upload sem replace deixa documentos duplicados poluindo retrieval
  (chunks duplicados aumentam ruido na busca cosine).
- Dois uploads concorrentes sem lock criam linha duplicada na tabela
  + chunks orfaos no `knowledge_chunks` se a UNIQUE falhar a meio do
  caminho.
- Falha em qualquer step (Storage 503, embedder 503) sem rollback
  poderia deixar a tabela `documents` inconsistente com Storage
  (row sem arquivo OU arquivo sem row).

## Decisao

We will tratar uploads com `source_name` ja existente como **atomic
replace** em uma unica transacao Postgres, serializada por advisory
lock per-(tenant, source_name).

### Algoritmo

```python
async def upload_document_atomic(
    *,
    tenant_id: UUID,
    source_name: str,
    raw_bytes: bytes,
    source_type: str,
    embedder: Embedder,
    storage: SupabaseStorage,
    pool: asyncpg.Pool,
) -> DocumentUploadResponse:
    # 1. Compute hash (FR-072) BEFORE any side-effect.
    source_hash = hashlib.sha256(raw_bytes).hexdigest()

    # 2. Extract + chunk + embed OUTSIDE the transaction
    #    (CPU/IO heavy; no DB locks held while OpenAI is being called).
    chunks = chunk(extract(raw_bytes, source_type))
    embeddings, usage = await embedder.embed_batch(
        [c.text for c in chunks], tenant_slug=tenant_slug
    )

    # 3. Open a single write transaction.
    new_doc_id = uuid4()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 3a. Per-(tenant, source_name) advisory lock — serialises
            #     concurrent re-uploads of THE SAME document.
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1))",
                f"doc:{tenant_id}:{source_name}",
            )

            # 3b. Check if a previous version exists.
            old = await conn.fetchrow(
                "SELECT id, storage_path FROM prosauai.documents "
                "WHERE tenant_id=$1 AND source_name=$2",
                tenant_id, source_name,
            )

            if old is not None:
                # 3c. CASCADE FK takes care of knowledge_chunks.
                await conn.execute(
                    "DELETE FROM prosauai.documents WHERE id=$1",
                    old["id"],
                )
                # 3d. Best-effort Storage delete of OLD raw — failure
                #     is logged but does not abort (the next upload
                #     will overwrite anyway).
                try:
                    await storage.delete(storage_path=old["storage_path"])
                except StorageError as exc:
                    logger.warning("rag_old_blob_orphan", reason=str(exc))

            # 3e. INSERT new document row.
            new_path = await storage.upload(
                tenant_id=tenant_id,
                document_id=new_doc_id,
                ext=ext_for(source_type),
                file_bytes=raw_bytes,
            )
            await conn.execute(
                "INSERT INTO prosauai.documents (...) VALUES (...)",
                new_doc_id, tenant_id, source_name, source_hash,
                source_type, new_path, len(raw_bytes), len(chunks),
                EMBEDDING_MODEL,
            )
            # 3f. Bulk INSERT chunks.
            await conn.copy_records_to_table(
                "knowledge_chunks",
                schema_name="prosauai",
                records=[(uuid4(), tenant_id, None, new_doc_id, i,
                         c.text, c.tokens, e, EMBEDDING_MODEL, {})
                        for i, (c, e) in enumerate(zip(chunks, embeddings))],
            )

    return DocumentUploadResponse(
        document_id=new_doc_id,
        chunks_created=len(chunks),
        replaced_existing=(old is not None),
        cost_usd=usage.cost_usd,
        ...
    )
```

### Invariantes garantidos

| Invariante | Mecanismo |
|------------|-----------|
| Nunca dois rows ativos com mesmo `(tenant_id, source_name)` | UNIQUE constraint no DB (T006) + advisory lock |
| Chunks orfaos zero (`document_id` apontando para row deletada) | FK `ON DELETE CASCADE` em `knowledge_chunks.document_id` |
| Documento "fantasma" no Storage sem row no DB | Storage upload **dentro** da transacao (passo 3e); rollback DB rollback do upload via best-effort delete (logged se falhar) |
| Concorrencia 2 uploads simultaneos do mesmo source_name | `pg_advisory_xact_lock(hashtext('doc:{tenant_id}:{source_name}'))` serializa; o segundo aguarda |
| Embedder 503 nao deixa row inconsistente | Embed e calculado ANTES de abrir transacao; falha => 503 retorno sem mutacao |

## Alternativas consideradas

### Versionamento explicit (`documents.version` + `is_current`)

- **Pros**:
  - Historico completo navegavel.
  - Rollback instantaneo para versao anterior (SET `is_current=true` na N-1).
  - Audit trail de "quem mudou o que e quando" gratuito.
- **Cons**:
  - 2x SQL (SELECT + UPDATE), nova coluna, nova UI para listar versoes
    e rollback.
  - Cresce sem bound — quem decide podar versoes antigas?
  - Embeddings antigos ocupam HNSW (custo de busca).
  - Complexity para retrieval: por padrao filtra `is_current=true` em
    cada query, mas alguns casos de uso (ex.: "consulta sobre regulamento
    de 2024") quereriam versoes antigas.
- **Por que rejeitado em v1**: solving for a problem 0 tenants relataram.
  Promovido para 012.1 se 2+ tenants pedirem.

### Append-only com soft-delete (`documents.deleted_at`)

- **Pros**:
  - Recovery facil de delete acidental.
  - Audit log natural (linha sempre existe, so muda flag).
- **Cons**:
  - Retrieval precisa filtrar `deleted_at IS NULL` em todo lugar.
  - HNSW continua indexando chunks "deletados" — custo crescente.
  - Tenant que quer purga LGPD precisa de hard-delete mesmo, defeating
    the purpose.
- **Por que rejeitado**: forca complexity em todo retrieval para um
  caso de uso (recovery) que e raro e ja coberto pelo Storage retention.

### Fingerprint dedup automatico (`source_hash` UNIQUE)

- **Pros**:
  - Re-upload de mesmo arquivo identico vira no-op (zero custo embed).
  - Detecta duplicatas entre `source_name` diferentes mesmo conteudo.
- **Cons**:
  - Tenant pode legitimamente subir o mesmo conteudo com 2 nomes
    diferentes (ex.: "FAQ Pace 2026.md" + "FAQ.md" como bookmark).
  - UNIQUE em hash adiciona constraint que pode falhar em update (re-edit
    do arquivo de uma virgula gera novo hash, ok; mas hash colision
    bizarra entre tenants seria bloqueante — RLS resolve mas adiciona
    edge case).
- **Por que rejeitado**: `source_hash` fica armazenado em `documents`
  para integrity-check (FR-072) mas v1 NAO faz dedup automatico. Promovido
  para 012.1 se relevante.

### Hard-delete + re-upload manual obrigatorio

- **Pros**:
  - Comportamento explicito (admin clicou "deletar" antes de subir
    novo).
  - Zero magic — sem regra "se source_name existe, faz X".
- **Cons**:
  - 2 cliques pra fazer o que o admin queria fazer em 1.
  - Janela entre delete e upload novo deixa o agente sem o documento
    (degrada qualidade de retrieval temporariamente).
  - Erro humano: admin esquece de re-upload, agente fica mudo.
- **Por que rejeitado**: pior UX, mais erro humano, sem ganho de
  controle real (ja temos audit log per-replace).

## Consequencias

- [+] **Mental model simples**: "subir o mesmo nome substitui". Match
  exato com a metafora "salvar arquivo no Drive".
- [+] **Atomicidade real**: ou o documento novo esta 100% indexado, ou
  o antigo permanece — nunca um estado misto.
- [+] **Custo controlado**: re-embed total custa ~R$0.005 por replace
  tipico (200 chunks * R$0.0001/chunk * 2 [old + new]). Aceitavel para
  v1.
- [+] **Concorrencia segura**: advisory lock per-(tenant, source_name)
  serializa apenas quando necessario — uploads de documentos diferentes
  nao se afetam.
- [+] **HNSW saudavel**: chunks antigos sao removidos imediatamente,
  index nao acumula entradas mortas.
- [-] **Sem historico**: tenant que precisa do conteudo antigo precisa
  baixar (botao "Baixar raw") ANTES de re-upload. Documentado em
  `apps/admin/docs/knowledge-base.md`.
- [-] **Best-effort Storage delete**: se a transacao SQL commit mas o
  delete do raw antigo falhar, fica um blob orfao no bucket. Mitigacao:
  GC noturno (futuro) ou monitor `rag_old_blob_orphan` em logs.
- [-] **Custo de re-embed**: se o tenant tem 50 docs e re-uploadou 49
  em sequencia (re-import de batch), pagou 49x re-embed. Mitigacao:
  futuro skip-if-hash-matches (012.1).
- [-] **Bound implicito**: tenant que quer manter historico precisa
  escolher nomes diferentes (`faq-2026-04.md`, `faq-2026-05.md`).
  Trade-off aceitavel para v1.

## Implementation notes (epic 012, T020 + T029 + T030)

- O advisory lock usa `hashtext('doc:{tenant_id}:{source_name}')` —
  string composta cobre tanto `tenant_id` quanto `source_name` em um
  unico int8. Colisoes de hashtext sao raras e o pior caso e dois
  uploads de tenants/nomes distintos serializarem desnecessariamente
  (lock spurious mas zero crash).
- O calculo de hash SHA-256 (FR-072) acontece DENTRO do endpoint, ANTES
  de comecar embed/extract — garante que `source_hash` reflete o raw
  exato gravado em `documents`.
- O storage upload ocorre **dentro** da transacao SQL (passo 3e):
  - Vantagem: se INSERT na tabela falhar, o rollback do Postgres
    automaticamente reverte; chamamos `storage.delete` no rollback path
    para limpar o blob.
  - Desvantagem: a transacao SQL fica aberta enquanto httpx upa
    multipart. Mitigacao: `request_timeout_seconds=30` no
    `SupabaseStorage`; lock period <30s.
- Audit: o evento `knowledge_document_uploaded` carrega
  `replaced_existing: bool` para o caller distinguir replace de novo
  upload (FR-076).

## Referencias

- Spec: `platforms/prosauai/epics/012-tenant-knowledge-base-rag/spec.md` (FR-015, FR-016, FR-072)
- Plan: `platforms/prosauai/epics/012-tenant-knowledge-base-rag/plan.md` § Constraints
- Test: `apps/api/tests/integration/rag/test_upload_atomic_replace.py`
- Quickstart: Steps 6 (smoke replace) + 11 (admin UI replace)
- ADR-013: pgvector namespaced + RLS herdada
- ADR-018: SAR cascade delete cobre Storage prefix `knowledge/{tenant_id}/`

---

> **Proximo passo:** revisar 012.1 (`/madruga:epic-context prosauai 013`)
> para promover versionamento se >=2 tenants pedirem.
