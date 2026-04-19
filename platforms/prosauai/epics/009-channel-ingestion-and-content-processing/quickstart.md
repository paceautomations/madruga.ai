# Quickstart — Epic 009 Channel Ingestion Normalization + Content Processing

**Feature Branch**: `epic/prosauai/009-channel-ingestion-and-content-processing`
**Date**: 2026-04-19
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md) | **Data Model**: [data-model.md](./data-model.md)

---

## 0. Pré-requisitos (ambiente dev)

```bash
# Python 3.12
python3 --version  # >= 3.12

# Dependências novas do epic
cd ~/repos/paceautomations/prosauai
pip install "openai>=1.50" "pypdf>=4.0" "python-docx>=1.1"

# OpenAI API key (dev)
export OPENAI_API_KEY="sk-..."  # .env local, nunca commitar

# Serviços locais
docker compose up -d postgres redis  # já configurados no repo
dbmate up  # aplica migrations pendentes

# Branch correto
git checkout epic/prosauai/009-channel-ingestion-and-content-processing
git pull origin epic/prosauai/009-channel-ingestion-and-content-processing
```

---

## 1. Validação incremental por PR

### PR-A — Canonical schema + EvolutionAdapter + pipeline step 6 stub

#### 1.1 Aplicar migration

```bash
cd ~/repos/paceautomations/prosauai
dbmate status
dbmate up  # aplica 20260420_create_media_analyses.sql
```

Verifique:

```sql
psql $DATABASE_URL -c "\d+ public.media_analyses"
-- Expect: 14 colunas, RLS=off, OWNER=app_owner
```

#### 1.2 Rodar suíte existente (gate de merge)

```bash
cd apps/api
pytest -x tests/ -k "not (slow or e2e)"
# Expect: 173 tests epic 005 + 191 tests epic 008 PASSING
# Fail → bloqueia merge (SC-010).
```

#### 1.3 Validar contrato canonical

```bash
pytest tests/contract/test_channel_adapter_contract.py -v
# Expect:
#   test_implements_protocol[EvolutionAdapter] PASSED
#   test_normalize_produces_valid_canonical[evolution_audio_ptt.input.json] PASSED
#   ... (13 fixtures Evolution)
```

#### 1.4 Webhook alias retrocompat

```bash
# Terminal 1: rodar API
cd apps/api && uvicorn prosauai.main:app --reload --port 8050

# Terminal 2: enviar payload legacy
curl -X POST http://localhost:8050/webhook/whatsapp/ariel-dev \
  -H "X-Webhook-Secret: dev-secret" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/captured/evolution_text_simple.input.json

# Expect: 202 Accepted
# Logs: "POST /webhook/whatsapp/... (legacy alias → evolution)"
```

#### 1.5 Validar step `content_process` (stub) aparece no trace

```bash
# Mesmo comando acima
# Abrir http://localhost:3000/traces
# Esperar trace aparecer
# Expandir → verificar waterfall tem 14 steps (antes era 12)
# Step 6 = content_process, output: {"providers": ["text-placeholder"], "kind": "text"}
```

### PR-B — Content Processors reais

#### 2.1 Feature flags por tenant

Edite `tenants.yaml` (ou use `.claude/tenants.dev.yaml`):

```yaml
tenants:
  ariel-dev:
    webhook_secret: dev-secret
    content_processing:
      enabled: true
      audio_enabled: true
      image_enabled: true
      document_enabled: true
      daily_budget_usd: 10.00
      fallback_messages:
        "[budget_exceeded]": "Desculpe, atingi meu limite diário. Responderei por aqui amanhã cedo."
        "[provider_unavailable]": "Tive um problema técnico. Pode tentar de novo em instantes?"
        "[pdf_scanned]": "Esse PDF parece ser uma imagem. Você consegue me mandar o texto direto?"
```

#### 2.2 Aplicar migration PR-B

```bash
dbmate up  # aplica 20260505_create_processor_usage_daily.sql
psql $DATABASE_URL -c "\d+ public.processor_usage_daily"
```

#### 2.3 Áudio end-to-end (User Story 1)

```bash
# Terminal 1: API + worker
docker compose up -d postgres redis
cd apps/api && uvicorn prosauai.main:app --reload --port 8050

# Terminal 2: enviar fixture de áudio
curl -X POST http://localhost:8050/webhook/evolution/ariel-dev \
  -H "X-Webhook-Secret: dev-secret" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/captured/evolution_audio_ptt.input.json

# Expect:
# - 202 Accepted
# - Em ~3-5s: resposta de saída no log do worker
# - Logs mostram span processor.audio + openai.whisper.create
```

**Validar no portal** (http://localhost:3000):

1. Abrir **Trace Explorer** → filtrar por tenant `ariel-dev` → último trace.
2. Expandir → step `content_process` deve mostrar:
   - `input: {kind: "audio", mime_type: "audio/ogg", duration: ...}`
   - `output: {provider: "openai/whisper-1", text_representation: "...", cost_usd: 0.001, latency_ms: ~1500, cache_hit: false, status: "ok"}`
3. Clicar no step → abrir modal → ver transcript completo (não truncado).

**Validar no DB**:

```sql
psql $DATABASE_URL <<SQL
SELECT kind, provider, length(text_result), cost_usd, cache_hit, status
  FROM public.media_analyses
  ORDER BY created_at DESC LIMIT 1;
SQL
-- Expect: 1 row, kind=audio, cost_usd > 0, status=ok
```

#### 2.4 Cache hit (SC-007)

Enviar a MESMA fixture de áudio novamente:

```bash
curl -X POST http://localhost:8050/webhook/evolution/ariel-dev -H "X-Webhook-Secret: dev-secret" -H "Content-Type: application/json" -d @tests/fixtures/captured/evolution_audio_ptt.input.json
```

Novo trace deve mostrar:
- step `content_process`: `cache_hit: true`, `cost_usd: 0`, `latency_ms < 50`

#### 2.5 Budget exceeded fallback (SC-008)

```bash
# Saturar o budget artificialmente
psql $DATABASE_URL <<SQL
INSERT INTO public.processor_usage_daily (tenant_id, day, kind, provider, count, cost_usd_sum, cache_hits, cache_misses)
VALUES ((SELECT id FROM public.tenants WHERE slug='ariel-dev'), current_date, 'audio', 'openai/whisper-1', 9999, 10.00, 0, 9999)
ON CONFLICT (tenant_id, day, kind, provider) DO UPDATE SET cost_usd_sum = 10.00;
SQL

# Enviar áudio
curl -X POST http://localhost:8050/webhook/evolution/ariel-dev -H "X-Webhook-Secret: dev-secret" -H "Content-Type: application/json" -d @tests/fixtures/captured/evolution_audio_ptt.input.json

# Expect:
# - 202 Accepted
# - Worker log: "budget_exceeded for tenant ariel-dev"
# - NENHUMA chamada ao OpenAI (mock ou real)
# - Resposta final ao cliente: string configurada em fallback_messages.[budget_exceeded] da tenant
```

#### 2.6 Imagem end-to-end (User Story 2)

```bash
curl -X POST http://localhost:8050/webhook/evolution/ariel-dev \
  -H "X-Webhook-Secret: dev-secret" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/captured/evolution_image_with_caption.input.json
```

Validar:
- Trace tem step `content_process` com `kind=image`, `provider=openai/gpt-4o-mini`, `detail=low`.
- `media_analyses.text_result` inclui descrição da imagem.
- Custo esperado: `0.013 USD` (±5%) — 85 tokens × $0.15/1M.

#### 2.7 Documento end-to-end (User Story 3)

```bash
curl -X POST http://localhost:8050/webhook/evolution/ariel-dev \
  -H "X-Webhook-Secret: dev-secret" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/captured/evolution_document_pdf.input.json
```

Validar:
- `media_analyses.provider = "internal/pypdf"` (extração local, cost_usd=0).
- Texto extraído aparece em `text_result`.

#### 2.8 Modalidades "light" (sticker, location, contact, reaction)

```bash
for fx in sticker reaction location contact; do
  curl -X POST http://localhost:8050/webhook/evolution/ariel-dev \
    -H "X-Webhook-Secret: dev-secret" \
    -H "Content-Type: application/json" \
    -d @tests/fixtures/captured/evolution_${fx}.input.json
done
```

Validar que cada trace tem `content_process` com:
- `provider = "internal/deterministic"`
- `cost_usd = 0`
- `latency_ms < 10`
- `text_representation` descritivo (ex: "[sticker 😀]", "[localização: -23.5, -46.6]")

#### 2.9 Unsupported kind (vídeo)

```bash
curl -X POST http://localhost:8050/webhook/evolution/ariel-dev \
  -H "X-Webhook-Secret: dev-secret" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/captured/evolution_video.input.json
```

Validar:
- `content_process.output.marker = "[content_unsupported: video]"`
- Resposta ao cliente via LLM (tonalizada) pede texto.

#### 2.10 Admin Performance AI — gráfico de custo

Abrir http://localhost:3000/performance-ai. Após os testes acima, o gráfico "Custo de mídia/dia" (Recharts stacked bar) deve mostrar:
- barra do dia com 3 segmentos (audio, image, document) empilhados.
- soma dos USD ≈ 0.014.

### PR-C — Meta Cloud Adapter (validação arquitetural)

#### 3.1 Fixtures reais

```bash
ls apps/api/tests/fixtures/captured/meta_cloud_*.input.json
# Expect: 4 arquivos (text, audio, image, interactive)
```

#### 3.2 Verify handshake

```bash
curl "http://localhost:8050/webhook/meta_cloud/ariel-dev?hub.mode=subscribe&hub.verify_token=dev-meta-token&hub.challenge=12345"
# Expect: 200 OK, body: 12345
```

#### 3.3 Payload Meta Cloud → pipeline sem distinção

```bash
# Gerar assinatura HMAC válida (script helper)
python3 apps/api/scripts/sign_meta_webhook.py \
  tests/fixtures/captured/meta_cloud_audio.input.json dev-app-secret

# Output: X-Hub-Signature-256: sha256=abc...

# Curl com assinatura
curl -X POST http://localhost:8050/webhook/meta_cloud/ariel-dev \
  -H "X-Hub-Signature-256: sha256=abc..." \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/captured/meta_cloud_audio.input.json

# Expect: 202 Accepted, trace percorre as mesmas 14 etapas do Evolution.
```

#### 3.4 Validar gate SC-013 (zero mudança core)

```bash
git diff develop..HEAD --stat apps/api/prosauai/pipeline.py apps/api/prosauai/processors/ apps/api/prosauai/core/router/
# Expect: sem output (zero bytes).
```

#### 3.5 Cross-source idempotency

Enviar payload Evolution com `id=X` e payload Meta Cloud com `message.id=X` (mesmo external_id):

```bash
# Ambos devem ser aceitos e processados como mensagens distintas
# (idempotency_key = sha256(source+instance+id) → diferente)
```

---

## 2. Rollback de emergência

### 2.1 Desligar feature globalmente

```bash
# Editar tenants.yaml: content_processing.enabled=false em todos tenants
git commit -am "chore: emergency disable content processing"
git push
# Aguardar ≤60s (poll do worker)
```

### 2.2 Rollback da migration (PR-B)

```bash
# Se 20260505 quebrar algo:
dbmate rollback  # drop processor_usage_daily

# Re-deploy com budget disabled:
# config: BUDGET_ENFORCEMENT=off → todos tenants processam sem check
```

### 2.3 Rollback total da camada Canonical (PR-A)

**Não recomendado** — revert `canonical.py` quebra 173+191 tests do epic 005/008. Em emergência, manter `/webhook/whatsapp/` alias ativo + reverter `api/webhooks/evolution.py` para versão do epic 008 via `git revert <sha>`.

---

## 3. Validação por User Story (spec.md)

| US | Script de validação | Sucesso |
|----|---------------------|---------|
| US1 Áudio | §1 PR-B §2.3 | Resposta em ≤8s p95 + trace com transcript |
| US2 Imagem | §2.6 | Resposta em ≤9s p95 + trace com descrição |
| US3 Documento | §2.7 | Resposta em ≤10s p95 + trace com texto extraído |
| US4 Trace Explorer | §2.3 passo "Validar no portal" | Step `content_process` no waterfall com todos os campos |
| US5 Feature flags + budget | §2.1 + §2.5 | Flags reloadam em ≤60s; budget exceeded → fallback gracioso |
| US6 Meta Cloud | PR-C §3.1-3.4 | Pipeline processa Meta Cloud sem diff em core |
| US7 Sticker/reação/localização | §2.8 | text_representation gerado sem chamada externa |

---

## 4. Benchmarks (gates de merge)

| Gate | Comando | Target |
|------|---------|--------|
| SC-009 latência texto PR-A | `pytest benchmarks/test_text_latency.py` | p95 ≤ baseline+5ms |
| SC-001 latência áudio PR-B | `pytest benchmarks/test_audio_e2e.py` | p95 ≤ 8000ms |
| SC-010 não-regressão | `pytest tests/ -x` | 173+191 tests PASS |
| SC-013 meta_cloud zero-touch | `git diff develop..HEAD --stat <paths core>` | empty diff |

---

## 5. Observabilidade no dev loop

```bash
# Tail logs estruturados
cd apps/api && uvicorn prosauai.main:app --reload --port 8050 2>&1 | jq -r '. | "\(.timestamp) [\(.level)] \(.message)"'

# Filtrar spans content_process
curl http://localhost:6006/v1/traces | jq '.[] | select(.spans[].name | startswith("processor."))'
```

---

## 6. Troubleshooting comum

| Sintoma | Causa provável | Fix |
|---------|----------------|-----|
| `ModuleNotFoundError: openai` | `pip install` não rodou | `pip install -r apps/api/requirements.txt` |
| 401 no webhook | `X-Webhook-Secret` errado | Conferir `tenants.yaml::tenants[instance].webhook_secret` |
| `content_process` não aparece no trace | `STEP_NAMES` não atualizado | `git diff` em `observability/step_record.py` — deve ter 14 entries |
| `cost_usd=null` na Performance AI | Provider não mapeado em `pricing.py` | Conferir `PRICING_TABLE["openai/whisper-1"]` existe |
| `media_analyses` vazia mas trace OK | Fire-and-forget falhou silenciosamente | `grep -r "persist media_analysis" logs/` → procurar exception |
| Cache hit sempre false | Prompt version bumpado sem intenção | Verificar `AudioProcessor.prompt_version` em `processors/audio.py` |
| Meta Cloud 401 constante | HMAC signature desalinhada | Usar helper `scripts/sign_meta_webhook.py` em dev; nunca reusar body após parse |

---

## 7. Limpeza pós-validação

```bash
# Purgar buffers debounce em dev
redis-cli FLUSHDB

# Resetar media_analyses para dev
psql $DATABASE_URL -c "TRUNCATE public.media_analyses, public.processor_usage_daily;"

# Voltar para develop limpo
git checkout develop
git pull
```
