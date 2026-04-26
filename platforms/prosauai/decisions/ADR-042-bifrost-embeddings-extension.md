---
title: 'ADR-042: Estender Bifrost com provider OpenAI embeddings (`/v1/embeddings`)'
status: Accepted
decision: Bifrost (proxy LLM em Go, ADR-002) ate epic 011 so suportava
  chat completions. Epic 012 estende com novo provider OpenAI para
  `/v1/embeddings`, reutilizando o pattern de adapter +
  rate-limit + spend tracking + circuit breaker do chat completions.
  Endpoint Bifrost `POST /v1/embeddings` aceita o body OpenAI canonical
  e responde com vetor 1536 dim. Cliente Python httpx usa
  `BIFROST_BASE_URL/v1/embeddings` com header `X-ProsaUAI-Tenant`.
alternatives: Chamada direta a OpenAI sem proxy, novo proxy dedicado
  para embeddings, BGE/Voyage self-hosted via API local, embeddings
  sync no api Python com biblioteca local
rationale: Centraliza rate-limit + spend tracking + breaker sob a mesma
  rede ja em prod (epic 005). Custo de extension <2 dias-pessoa-Go;
  maior gain e auditabilidade de custo OpenAI por tenant em uma so
  pagina (dashboard Bifrost). Cut-line: se >1 semana, fallback para
  chamada direta sem spend tracking (sacrifica SC-010 temporariamente).
---

# ADR-042: Estender Bifrost com provider OpenAI embeddings

**Status:** Accepted | **Data:** 2026-04-26 | **Relaciona:** [ADR-002](ADR-002-bifrost-llm-proxy.md), [ADR-013](ADR-013-pgvector-tenant-knowledge.md), [ADR-041](ADR-041-knowledge-document-replace-by-source-name.md), `../epics/012-tenant-knowledge-base-rag/`

> **Aceite:** entregue como descrito em PR-A (epic 012 / T021 + T022 + T023).
> Validado por `apps/api/tests/rag/test_embedder.py` (respx mocks) +
> dashboard `bifrost/dashboards/embeddings.json` (T080) + smoke
> quickstart Step 4.

> **Escopo:** Bifrost (`paceautomations/bifrost`) +
> `apps/api/prosauai/rag/embedder.py`. Coordenacao via PR coordenado
> mas merge separado por repo.

## Contexto

O epic 005 (ADR-002) escolheu Bifrost (proxy LLM em Go) como single
gateway para LLM calls com:

- Rate limiting per-tenant (proteje OpenAI quota global).
- Spend tracking per-tenant (rateio de custo OpenAI no Stripe).
- Circuit breaker (abre apos 5 falhas em 60s, fecha apos 1 sucesso).
- Header injection (`OpenAI-Beta`, retry policy).
- Audit de prompts via Bifrost logs (sem PII).

**Ate o epic 011** Bifrost so expunha `/v1/chat/completions`. O agente
pydantic-ai tinha config `base_url=$BIFROST_URL/v1` apontando para
chat completions OpenAI-compatible.

**Epic 012** introduz uma nova categoria de chamada LLM:
embeddings. Cada documento upload chama
`POST /v1/embeddings` (OpenAI `text-embedding-3-small`, 1536 dim) em
batch de ate 100 textos. Cada tool call em conversa idem para a query.

Tres caminhos possiveis:

1. **Estender Bifrost** com novo provider OpenAI embeddings.
2. **Chamada direta** OpenAI a partir do api Python (httpx +
   `OPENAI_API_KEY`).
3. **Novo proxy** dedicado para embeddings.

Cada um tem implicacao distinta para rate-limit, spend tracking,
breaker e auditoria.

## Decisao

We will **estender Bifrost** com um novo provider OpenAI configurado
exclusivamente para o endpoint `/v1/embeddings`, reutilizando o pattern
de adapter + middleware ja em producao para chat completions.

### Arquitetura

```
+----------------+    httpx    +----------+   OpenAI    +----------+
| api Python     |  ---------> | Bifrost  |  --------> | OpenAI    |
| rag/embedder.py|             | (Go)     |            | embed-3-S |
+----------------+             +----------+            +----------+
                                  |
                                  +-- rate limit per-tenant
                                  +-- spend tracking ($/tenant)
                                  +-- circuit breaker
                                  +-- audit logs (sem PII raw)
```

### Bifrost config (TOML em `paceautomations/bifrost/config/providers/`)

```toml
[providers.openai-embeddings]
type        = "openai"
base_url    = "https://api.openai.com/v1"
api_key     = "${OPENAI_API_KEY}"
endpoints   = ["/embeddings"]
rate_limit_per_tenant = 1000  # req/min — far below OpenAI 3500/min global
default_model = "text-embedding-3-small"

[providers.openai-embeddings.spend_tracking]
enabled = true
# OpenAI pricing 2026-04: $0.02 / 1M tokens
cost_per_million_input_tokens_usd = 0.02

[providers.openai-embeddings.breaker]
failure_threshold = 5
failure_window_seconds = 60
recovery_threshold = 1
```

### Adapter Go (~150 LOC, `paceautomations/bifrost/adapters/openai_embeddings.go`)

Reusa interfaces ja existentes em `adapters/openai_chat.go`:

```go
type OpenAIEmbeddingsAdapter struct {
    BaseURL  string
    APIKey   string
    Pricing  PricingConfig
}

func (a *OpenAIEmbeddingsAdapter) Forward(
    ctx context.Context, tenant string, body []byte,
) (*Response, error) {
    // 1. Parse body para extrair `input` (string ou array) + `model`.
    // 2. Forward POST /v1/embeddings.
    // 3. Parse `usage.total_tokens` da resposta.
    // 4. Compute spend = total_tokens * pricing.per_million / 1_000_000.
    // 5. Emit metric `bifrost_spend{provider="openai-embeddings", tenant}`.
    // 6. Return body + spend headers (`X-Bifrost-Spend-USD`).
}
```

### Cliente Python (`apps/api/prosauai/rag/embedder.py`)

```python
class BifrostEmbedder:
    """OpenAI-compatible embeddings client routed through Bifrost."""

    def __init__(self, base_url: str, http_client: httpx.AsyncClient) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = http_client
        self._model = "text-embedding-3-small"

    async def embed_batch(
        self, texts: list[str], *, tenant_slug: str
    ) -> tuple[list[list[float]], EmbedUsage]:
        body = {"input": texts, "model": self._model}
        headers = {"X-ProsaUAI-Tenant": tenant_slug}
        # Retry exponential 3x on 429 / 503 / timeout.
        async for attempt in retrying(max_retries=3):
            with attempt:
                response = await self._client.post(
                    f"{self._base_url}/v1/embeddings",
                    json=body, headers=headers, timeout=30.0,
                )
                response.raise_for_status()
                payload = response.json()
        embeddings = [item["embedding"] for item in payload["data"]]
        usage = EmbedUsage(
            total_tokens=payload["usage"]["total_tokens"],
            cost_usd=float(response.headers.get("X-Bifrost-Spend-USD", 0)),
            model=self._model,
        )
        return embeddings, usage
```

## Alternativas consideradas

### Chamada direta a OpenAI sem Bifrost

- **Pros**:
  - Zero linhas de Go a escrever.
  - Latencia <50ms vs ~150ms (1 hop a menos).
  - Independente de Bifrost (bifurcacao de blast radius).
- **Cons**:
  - **Rate limit global** OpenAI compartilhado entre todos os tenants —
    1 tenant abusivo derrubaria os outros.
  - **Sem spend tracking per-tenant** — invoice OpenAI vem agregado;
    rateio manual mensal.
  - **Sem circuit breaker** — falha OpenAI 503 cascateia em uploads
    travados.
  - **Sem audit centralizado** — logs distribuidos no api Python.
  - SC-010 ("Bifrost spend accuracy <=2% diff vs invoice OpenAI") nao
    realizavel.
- **Por que rejeitado**: ganha 100ms, perde 4 garantias operacionais.
  Reservado como **cut-line** se Bifrost extension >1 semana — opcao
  fallback temporario.

### Novo proxy dedicado para embeddings

- **Pros**:
  - Bifrost continua simples (so chat completions).
  - Permitiria provider hibrido (BGE local + OpenAI fallback) facil.
- **Cons**:
  - +1 servico para operar (deploy, monitor, alarms).
  - Dois pontos de spend tracking (Bifrost chat + novo proxy).
  - Custo de manutencao 2x.
- **Por que rejeitado**: viola "menos pecas". Bifrost ja tem 90% do
  pattern; reuso > nova caixa.

### BGE/Voyage self-hosted via API local

- **Pros**:
  - Zero custo OpenAI per-call.
  - Privacy (nada sai do nosso ambiente).
  - Modelo open-source = sem lock-in.
- **Cons**:
  - **Dim mismatch**: BGE-M3 = 1024 dim, Voyage = 1024-2048 dim. Schema
    pgvector ja decidido para 1536 dim (OpenAI). Trocar exige migration
    custosa.
  - Self-host = +1 servico GPU para operar.
  - Quality tradeoff conhecido para PT-BR (BGE-M3 e bom mas nao testado
    em production em PT-BR).
- **Por que rejeitado**: dim mismatch isolado bloqueia. Promovido para
  013+ se custo OpenAI escalar > orcamento.

### Embeddings sync via biblioteca Python local

- **Pros**:
  - Zero rede (CPU-bound).
  - Determinismo absoluto.
- **Cons**:
  - Modelo local = GB de memoria, +inference latency 200-500ms para
    batch 100.
  - Dim 384 (sentence-transformers default) vs 1536 obrigatorio.
- **Por que rejeitado**: latencia + dim mismatch sao bloqueantes.

## Consequencias

- [+] **Spend tracking unificado**: dashboard Bifrost mostra custo
  OpenAI total + breakdown por tenant + breakdown chat-vs-embeddings.
  SC-010 (`<=2%` desvio vs invoice) realizavel.
- [+] **Rate limit per-tenant**: tenant abusivo (ex.: re-import de
  10000 documentos) e contido na entrada Bifrost antes de bater no
  OpenAI quota global.
- [+] **Circuit breaker**: OpenAI 503 abre o breaker apos 5 falhas em
  60s, evita cascata de uploads/tools travados; fecha apos 1 sucesso.
- [+] **Reuso maximo**: pattern de adapter + middleware ja em prod
  (epic 005). Extension e config TOML + ~150 LOC Go.
- [+] **Audit centralizado**: logs Bifrost capturam latencia, status,
  retry sem precisar adicionar metric ao api Python.
- [+] **Fallback documentado**: cut-line para chamada direta caso
  extension estoure (~1 semana) — sem bloquear o epic 012 inteiro.
- [-] **+1 hop**: ~100ms a mais por chamada (api Python -> Bifrost ->
  OpenAI vs api Python -> OpenAI). Aceitavel para batch de 100 textos
  em <1s total.
- [-] **Bifrost vira ponto unico**: outage de Bifrost para chat AND
  embeddings simultaneamente. Mitigacao: HA Bifrost (2 replicas, ja em
  prod) + SLO 99.9%.
- [-] **Acoplamento de versao**: extender Bifrost exige PR coordenado
  (api Python + Bifrost). Rollout = Bifrost deploy primeiro, depois api
  Python.

## Implementation notes (epic 012, T021-T023)

- **Coordenacao de PRs**:
  1. Bifrost PR (Go): config TOML + adapter + tests Go + dashboard JSON.
     Merge primeiro em `paceautomations/bifrost`.
  2. Validacao Bifrost staging via curl direct.
  3. api Python PR: `embedder.py` + tests respx + endpoint admin.
- **Header `X-ProsaUAI-Tenant`**: o api Python envia o `tenant_slug`
  (string short, NAO `tenant_id` UUID — mais legivel em logs Bifrost).
  Bifrost mapeia slug -> rate limit bucket + spend bucket.
- **Spend tracking**: a resposta Bifrost inclui header
  `X-Bifrost-Spend-USD` com o custo computado. O api Python agrega no
  `EmbedUsage` para audit (`knowledge_document_uploaded.cost_usd`).
- **Retry policy**: 3 tentativas com backoff exponencial (1s, 2s, 4s)
  em 429 / 503 / timeout. Ja implementado no httpx wrapper do epic 005;
  reusado.
- **Circuit breaker observability**: metric
  `bifrost_breaker_open{provider="openai-embeddings"}` em Prometheus.
  Alerta dispara em >0 por >2min consecutivos.
- **Cut-line fallback**: se a extension Bifrost atrasar >1 semana,
  ativar `RAG_EMBEDDER_DIRECT=true` e o `BifrostEmbedder` chamadar
  `https://api.openai.com/v1/embeddings` direto (mesmo client httpx,
  sem header tenant). Spend tracking fica fora durante a janela; SC-010
  diferido. Documentado em `apps/api/docs/runbooks/rag-rollout.md`.

## Referencias

- ADR-002: Bifrost LLM proxy (decisao base)
- ADR-013: pgvector + dim 1536 (constraint do schema)
- Spec: `platforms/prosauai/epics/012-tenant-knowledge-base-rag/spec.md` FR-026 a FR-033, SC-010
- Plan: `platforms/prosauai/epics/012-tenant-knowledge-base-rag/plan.md` § Bifrost extension
- Test: `apps/api/tests/rag/test_embedder.py` (respx mocks)
- Dashboard: `paceautomations/bifrost/dashboards/embeddings.json` (T080)
- OpenAI pricing 2026-04: https://openai.com/pricing — `text-embedding-3-small` $0.02/1M tokens

---

> **Proximo passo:** revisar 012.1 (`/madruga:epic-context prosauai 013`)
> para promover BGE self-hosted se custo OpenAI escalar acima do
> orcamento de R$2k/mes.
