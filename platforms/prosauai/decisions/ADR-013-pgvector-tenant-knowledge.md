---
title: 'ADR-013: pgvector namespaced como knowledge store per tenant'
status: Accepted
decision: pgvector namespaced
alternatives: Pinecone (servico dedicado), Weaviate (self-hosted), Vector DB separado
  por tenant (modelo Botpress), Fine-tuning por tenant
rationale: Zero infra adicional — pgvector roda no mesmo Postgres (principio "menos
  pecas")
---
# ADR-013: pgvector namespaced como knowledge store per tenant
**Status:** Accepted | **Data:** 2026-03-25

## Contexto
Cada tenant precisa de uma knowledge base propria (documentos, FAQs, dados) para alimentar o RAG dos agentes. Precisamos definir onde armazenar embeddings e como isolar o conhecimento entre tenants. O mercado oferece servicos dedicados (Pinecone, Weaviate) ou extensoes do banco relacional (pgvector).

## Decisao
We will usar pgvector na mesma instancia Supabase PostgreSQL, com isolamento por `tenant_id` + `namespace` — sem servico de vetores separado.

Arquitetura:
```sql
-- Tabela de chunks com isolamento por tenant
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    agent_id UUID NOT NULL REFERENCES agents(id),
    chunk TEXT NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB DEFAULT '{}',
    source_type TEXT,  -- pdf, docx, markdown, url
    created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS policy (herda modelo ADR-011)
ALTER TABLE knowledge_chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON knowledge_chunks
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Indice vetorial HNSW (preferido sobre IVFFlat — sem necessidade de re-index)
CREATE INDEX idx_knowledge_tenant_embedding
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

Query RAG padrao:
```sql
SELECT chunk, embedding <=> $query_vector AS distance
FROM knowledge_chunks
WHERE tenant_id = $tenant_id
  AND agent_id = $agent_id
ORDER BY distance
LIMIT 5;  -- max 5 chunks por query (controle de custo)
```

Fluxo de upload:
1. Tenant sobe documento via admin panel (PDF, DOCX, markdown)
2. Sistema extrai texto e chunka
3. Embedding via API (Claude ou OpenAI)
4. INSERT na tabela — live na proxima query (zero retraining)

Compliance (LGPD):
- Knowledge base deletado integralmente ao encerrar conta do tenant
- Dados do cliente sao propriedade do cliente (principio inviolavel — Vision Brief)
- Media retention policy: documentos de grupo anonimizados apos 30 dias (anti-pattern #9)

## Alternativas consideradas

### Pinecone (servico dedicado)
- Pros: Otimizado para busca vetorial, escala automatica, managed (zero ops), metadata filtering nativo
- Cons: +1 servico para gerenciar e pagar, dados sensiveis fora do ambiente, latencia de rede adicional (roundtrip ao servico), vendor lock-in, custo cresce com volume de vetores

### Weaviate (self-hosted)
- Pros: Open-source, multi-tenant nativo, schema-based, hybrid search (BM25 + vector)
- Cons: +1 infra para operar (Java/Go), complexidade de deploy e monitoring, overhead operacional para time de 5, overkill para o volume esperado

### Vector DB separado por tenant (modelo Botpress)
- Pros: Isolamento maximo de vetores, backup/restore simples por tenant
- Cons: Custo multiplicado por N tenants, operacionalmente inviavel apos 50 tenants, namespace resolve o mesmo problema com custo zero

### Fine-tuning por tenant
- Pros: Modelo customizado ao dominio do cliente, potencialmente melhor qualidade
- Cons: Caro (custo de training), lento (horas/dias), nao faz sentido para knowledge base que muda frequentemente, RAG resolve 95% dos casos

## Consequencias
- [+] Zero infra adicional — pgvector roda no mesmo Postgres (principio "menos pecas")
- [+] RLS protege vetores igual ao resto dos dados (herda ADR-011)
- [+] Garantias transacionais — upload de knowledge e atomico com o resto das operacoes
- [+] Knowledge update e instantaneo (INSERT, nao retraining)
- [+] Custo marginal proximo de zero por tenant
- [-] pgvector e menos otimizado que servicos dedicados para busca em escala (>1M vetores por tenant)
- [-] Embedding API e custo adicional por upload (mitiga com batch processing)

## Evolucao: pgvectorscale (Timescale)
pgvector 0.8.x + **pgvectorscale** muda o cenario competitivo:
- **StreamingDiskANN**: Indice baseado em DiskANN (Microsoft Research), otimizado para SSD ao inves de RAM
- **Benchmarks (50M Cohere, 768 dim)**: 11x QPS vs Qdrant em filtered queries, 28x menor p95 latency vs Pinecone, 75% menos custo self-hosted
- **Suporte ate 16.000 dimensoes** (vs 2.000 do pgvector nativo)
- **HNSW desde o inicio**: Usar HNSW (nao IVFFlat) — sem necessidade de re-index periodico, performance superior para o volume esperado
- Avaliar pgvectorscale quando volume de vetores crescer significativamente (>1M por tenant)

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
