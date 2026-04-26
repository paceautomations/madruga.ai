# Quickstart — Epic 012 (Tenant Knowledge Base — RAG pgvector + Upload Admin)

End-to-end smoke test: do schema vazio ate agente respondendo com chunk citado. Use este roteiro para validar PR-A + PR-B + PR-C em staging antes do rollout produtivo.

**Pre-requisitos**:

- Acesso ao repo `paceautomations/prosauai` (branch `epic/prosauai/012-tenant-knowledge-base-rag`).
- Acesso admin ao Supabase project (SQL editor + Storage).
- Acesso ao Bifrost config (repo `paceautomations/bifrost`).
- Tenant Ariel ja existente em `tenants.yaml` (ou tenant_id staging conhecido).
- Postman/curl + browser para admin UI.

---

## Step 1 — Habilitar pgvector extension (1x, ops manual)

No Supabase SQL editor, executar (idempotente):

```sql
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

Esperado: `vector | 0.8.0` (ou superior). Se vazio, contactar suporte Supabase para habilitar.

---

## Step 2 — Aplicar migrations

Da raiz do repo `prosauai`:

```bash
cd apps/api
dbmate up
```

Esperado:

```
Applying: 20260601000006_create_pgvector_extension
Applying: 20260601000007_create_documents
Applying: 20260601000008_create_knowledge_chunks
Applying: 20260601000009_create_knowledge_storage_bucket
```

Verificar tabelas:

```sql
\d prosauai.documents
\d prosauai.knowledge_chunks
SELECT indexname FROM pg_indexes WHERE tablename = 'knowledge_chunks';
```

Esperado: 4 indexes (pk, knowledge_chunks_embedding_hnsw_idx, knowledge_chunks_tenant_agent_idx, knowledge_chunks_document_idx).

---

## Step 3 — Criar bucket Supabase Storage `knowledge`

Via supabase CLI:

```bash
supabase storage create knowledge --project-ref <project_id>
# OR via SQL:
INSERT INTO storage.buckets (id, name, public) VALUES ('knowledge', 'knowledge', false);
```

Aplicar policy restrictiva (so service-role acessa):

```sql
CREATE POLICY "service_role_only" ON storage.objects
  FOR ALL
  TO service_role
  USING (bucket_id = 'knowledge');
```

Verificar:

```bash
supabase storage list knowledge --project-ref <project_id>
# Esperado: empty list (bucket criado vazio)
```

---

## Step 4 — Estender Bifrost com provider OpenAI embeddings

No repo `paceautomations/bifrost`:

1. Editar `config/providers/openai-embeddings.toml`:

   ```toml
   [providers.openai_embeddings]
   endpoint = "/v1/embeddings"
   target_url = "https://api.openai.com/v1/embeddings"
   api_key_env = "OPENAI_API_KEY"
   rate_limit_rpm = 3500
   rate_limit_tpm = 5000000
   timeout_seconds = 30
   spend_tracking_enabled = true
   cost_per_1k_tokens_usd = 0.00002
   ```

2. Restart Bifrost.

3. Testar via curl:

   ```bash
   curl -X POST http://bifrost.local/v1/embeddings \
     -H "Authorization: Bearer $OPENAI_API_KEY" \
     -H "X-ProsaUAI-Tenant: pace-internal" \
     -H "Content-Type: application/json" \
     -d '{"model": "text-embedding-3-small", "input": ["hello world"]}'
   ```

   Esperado: `200 OK` com `data: [{embedding: [0.123, ...], index: 0}], model: ..., usage: {...}`.

4. Verificar spend em DB:

   ```sql
   SELECT * FROM bifrost_spend
   WHERE provider = 'openai' AND endpoint = 'embeddings'
   ORDER BY created_at DESC LIMIT 5;
   ```

   Esperado: 1 row com `tenant_id = pace-internal.id`, `cost_usd > 0`.

---

## Step 5 — Habilitar `rag.enabled` para Ariel

Editar `apps/api/config/tenants.yaml`, encontrar o tenant `pace-internal` (Ariel):

```yaml
tenants:
  - id: pace-internal
    db_tenant_id: "00000000-0000-4000-a000-000000000001"
    # ... outros campos existentes
    rag:
      enabled: true
      top_k: 5
      max_upload_mb: 10
```

Commit + push em branch staging. Aguardar config_poller (<=60s) ou restart `api`:

```bash
docker-compose restart api
```

Verificar log:

```bash
docker-compose logs -f api | grep "tenant_config_reloaded"
# Esperado: tenant_config_reloaded{tenant=pace-internal}
```

---

## Step 6 — Upload primeiro documento via curl

Preparar arquivo de teste:

```bash
cat > /tmp/faq.md <<'EOF'
# FAQ Ariel — Comunidade Pace Internal

## Horario de funcionamento

A Pace funciona de segunda a sexta, das 9h as 18h. Em feriados nacionais
estamos fechados. Para urgencias fora do expediente, contactar via WhatsApp
do gestor de plantao.

## Politica de reembolso

Reembolsos sao processados em ate 7 dias uteis apos solicitacao. Nao
reembolsamos servicos ja prestados, apenas planos nao iniciados.

## Como contactar suporte

Nosso suporte responde via WhatsApp (Ariel bot) ou email
suporte@pace.com.br. Tempo medio de resposta: 2 horas em horario comercial.
EOF
```

Upload via curl (ajustar token JWT):

```bash
TENANT_ID="00000000-0000-4000-a000-000000000001"
ADMIN_TOKEN="<seu_jwt_admin>"

curl -X POST "http://localhost:8000/admin/knowledge/documents?tenant_id=$TENANT_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@/tmp/faq.md"
```

Esperado (201):

```json
{
  "document_id": "uuid-...",
  "source_name": "faq.md",
  "source_type": "md",
  "chunks_created": 4,
  "total_tokens": 280,
  "cost_usd": 0.0000056,
  "embedding_model": "text-embedding-3-small",
  "replaced_existing": false
}
```

Tempo: <10s.

Verificar DB:

```sql
SELECT id, source_name, chunks_count, embedding_model
FROM prosauai.documents WHERE tenant_id = '00000000-0000-4000-a000-000000000001';

SELECT count(*) FROM prosauai.knowledge_chunks
WHERE tenant_id = '00000000-0000-4000-a000-000000000001';
-- Esperado: count = chunks_created
```

Verificar Storage:

```bash
supabase storage ls knowledge/00000000-0000-4000-a000-000000000001/ --project-ref <project_id>
# Esperado: 1 arquivo {document_id}.md
```

---

## Step 7 — Habilitar tool `search_knowledge` no agente Ariel

Encontrar agent_id do Ariel:

```sql
SELECT id, tenant_id, system_prompt FROM prosauai.agents
WHERE tenant_id = '00000000-0000-4000-a000-000000000001';
```

Atualizar `tools_enabled` via API:

```bash
AGENT_ID="<agent_id_ariel>"

curl -X PATCH "http://localhost:8000/admin/agents/$AGENT_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tools_enabled": ["search_knowledge"]}'
```

Esperado: `200 OK` com `tools_enabled: ["search_knowledge"]`.

---

## Step 8 — Smoke message via WhatsApp simulator (epic 008)

Abrir admin UI: `http://localhost:3000/admin/conversations`

Selecionar conversa de teste do tenant Ariel. Mandar mensagem:

> "qual o horario de funcionamento?"

Aguardar resposta do agente (~3-5s).

Esperado:

> "A Pace funciona de segunda a sexta, das 9h as 18h. Em feriados nacionais estamos fechados. Para urgencias fora do expediente, contactar via WhatsApp do gestor de plantao."

(Resposta cita literalmente texto do FAQ chunk.)

---

## Step 9 — Verificar Trace Explorer (epic 008)

Em admin UI -> Trace Explorer -> filtrar pela mensagem enviada.

Esperado:

```
agent.generate (3.2s)
├── tool_call.search_knowledge (1.4s)
│   └── rag.search (1.3s)
│       attributes:
│         rag.query_tokens = 6
│         rag.chunks_returned = 5
│         rag.distance_top1 = 0.21
│         rag.cost_usd = 0.0000001
│         rag.embedding_model = text-embedding-3-small
│   └── rag.embed (0.35s)  -- query embedding
│       attributes:
│         embed.batch_size = 1
│         embed.tokens_total = 6
│         embed.cost_usd = 0.0000001
└── llm.completion (1.5s)
    -- final response composed with chunks
```

---

## Step 10 — Smoke admin UI (PR-C)

Abrir `http://localhost:3000/admin/knowledge`.

Esperado: nova entry "Base de Conhecimento" no sidebar (icon BookOpen).

Verificar tabela mostra 1 row com `source_name=faq.md, source_type=md (badge azul), chunks_count=4, size=720 B, uploaded_at="ha alguns segundos"`.

Click na linha -> Sheet abre com metadata + primeiros 3 chunks (texto preview).

Click em actions menu -> "Download original" -> baixa `faq.md` byte-identico.

Click em "Adicionar documento" -> Dialog abre. Drag-drop `/tmp/faq.md` (mesmo nome). Esperado: AlertDialog "Documento existente sera substituido. Os 4 chunks atuais serao removidos." Confirmar. Apos ~10s, tabela atualiza com novos chunks.

Verificar atomic-replace no DB:

```sql
SELECT id, source_name, chunks_count
FROM prosauai.documents WHERE source_name = 'faq.md';
-- Esperado: 1 row com novo document_id (UUID diferente do anterior)

SELECT count(*) FROM prosauai.knowledge_chunks
WHERE tenant_id = '00000000-0000-4000-a000-000000000001';
-- Esperado: count = novo chunks_count (sem chunks orfaos do antigo)
```

---

## Step 11 — Smoke delete

Click actions menu -> "Excluir" -> confirmar.

Esperado: `204 No Content`. Tabela atualiza (sumiu).

Verificar cascade:

```sql
SELECT count(*) FROM prosauai.documents
WHERE tenant_id = '00000000-0000-4000-a000-000000000001';
-- Esperado: 0

SELECT count(*) FROM prosauai.knowledge_chunks
WHERE tenant_id = '00000000-0000-4000-a000-000000000001';
-- Esperado: 0 (cascade FK)
```

```bash
supabase storage ls knowledge/00000000-0000-4000-a000-000000000001/ --project-ref <project_id>
# Esperado: empty
```

Verificar Trace Explorer: span historico de `rag.search` da Step 8 ainda existe (append-only). Renderiza `source_name = "(deleted)"` no JOIN.

---

## Step 12 — Smoke kill-switch (revert via flag)

Editar `tenants.yaml`:

```yaml
rag:
  enabled: false
```

Commit + push. Aguardar config_poller (<=60s).

Tentar upload novamente:

```bash
curl -X POST "http://localhost:8000/admin/knowledge/documents?tenant_id=$TENANT_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@/tmp/faq.md"
```

Esperado: `403 Forbidden` com `{"error": "rag_not_enabled_for_tenant"}`.

Mandar mensagem teste novamente -> agente responde sem chamar tool (verify Trace Explorer: nao tem subspan `tool_call.search_knowledge`).

Re-habilitar setando `enabled: true` -> mesmo upload retorna `201` em <=60s sem deploy.

---

## Step 13 — Cleanup de staging

```bash
# Apagar documents/chunks do tenant teste
curl -X DELETE "http://localhost:8000/admin/sar/<test_customer_id>" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# OU SQL direto (cuidado: cascade real)
DELETE FROM prosauai.documents WHERE tenant_id = '<test_tenant_id>';
```

---

## Validation checklist

Para considerar Smoke Test bem-sucedido:

- [ ] Step 1: pgvector extension ativa
- [ ] Step 2: 4 migrations aplicadas, indexes criados (incluindo HNSW)
- [ ] Step 3: bucket `knowledge` criado com policy service_role_only
- [ ] Step 4: Bifrost retorna embedding 1536 dim + spend gravado
- [ ] Step 5: config_poller picked up `rag.enabled=true` em <=60s
- [ ] Step 6: upload retorna 201 com chunks_count > 0, Storage tem o arquivo
- [ ] Step 7: agente atualizado, `tools_enabled` contem `search_knowledge`
- [ ] Step 8: agente responde com texto do chunk citado (semantic match)
- [ ] Step 9: Trace Explorer mostra span hierarchy `agent.generate` -> `tool_call.search_knowledge` -> `rag.search` + `rag.embed`
- [ ] Step 10: admin UI funcional (lista, upload com replace, detail sheet)
- [ ] Step 11: delete cascadeia DB + Storage; spans historicos preservados com "(deleted)"
- [ ] Step 12: kill-switch via `rag.enabled=false` toma efeito em <=60s sem deploy

---

## Troubleshooting

| Sintoma | Causa provavel | Acao |
|---------|----------------|------|
| `CREATE EXTENSION vector` falha | Plano Supabase nao tem pgvector | Contactar suporte / upgrade plano |
| Migration HNSW falha (`unknown index method hnsw`) | pgvector < 0.5.0 | Upgrade pgvector |
| Bifrost retorna 404 | Endpoint nao roteado | Restart Bifrost apos config edit |
| Bifrost retorna 503 | OpenAI down OR API key invalida | Check OpenAI status + env var OPENAI_API_KEY |
| Upload retorna 403 mesmo com `enabled: true` | Config_poller nao recarregou | Esperar 60s OR restart api OR check log `tenant_config_reload_failed` |
| Agente nao chama tool | `tools_enabled` ausente OR system_prompt nao instrui | Adicionar instrucao explicita no system_prompt |
| `rag.search` span nao aparece | OTel nao instrumentado em `tools/search_knowledge.py` | Verify `with tracer.start_as_current_span("rag.search"):` em `search_knowledge.py` |
| Cascade delete deixa chunks orfaos | FK ON DELETE CASCADE nao aplicado | Verify `\d prosauai.knowledge_chunks` mostra `ON DELETE CASCADE` |
| Storage delete falha mas DB delete sucesso | Transaction sem 2-phase commit | Implementar order: Storage primeiro, DB depois (ja FR-009 spec) |

---

## Performance baseline (tirar antes do rollout)

Apos Step 9 (smoke success), medir e registrar:

```sql
-- Latencia upload (p50/p95)
SELECT
  percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (uploaded_at - created_at))) AS p50_seconds,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (uploaded_at - created_at))) AS p95_seconds
FROM prosauai.documents WHERE tenant_id = '<test_tenant>';
```

```promql
# Tool latencia
histogram_quantile(0.95, sum(rate(rag_search_duration_seconds_bucket[5m])) by (le))

# Embedder failures
sum(rate(rag_embedder_failures_total[5m])) by (provider, reason)
```

Esperado:

- Upload p95 <=15s
- Tool p95 <=2s
- Embedder failures: 0/min em condicoes normais

---

handoff:
  from: quickstart (Phase 1)
  to: tasks (Phase 2)
  context: "Quickstart end-to-end testavel cobrindo PR-A (steps 1-2-3) + PR-B (4-5-6-7-8-9) + PR-C (10-11-12). 13 steps + 13 checklist items + troubleshooting + performance baseline. Usar como roteiro de smoke pre-rollout."
  blockers: []
  confidence: Alta
  kill_criteria: "Step 1 (pgvector) falha -> bloqueio total. Step 4 (Bifrost) falha -> recuar para OpenAI direct (sacrifica SC-010)."
