# Quickstart: Channel Pipeline

**Epic**: 001-channel-pipeline  
**Date**: 2026-04-09

---

## Pré-requisitos

- Python 3.12+
- Docker e Docker Compose
- Redis 7+ (via Docker ou local)

---

## Setup Rápido

### 1. Clonar e instalar

```bash
cd paceautomations/prosauai
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configurar ambiente

```bash
cp .env.example .env
# Editar .env com valores reais:
# - EVOLUTION_API_URL, EVOLUTION_API_KEY, EVOLUTION_INSTANCE_NAME
# - WEBHOOK_SECRET (gerar: python -c "import secrets; print(secrets.token_hex(32))")
# - MENTION_PHONE (JID do bot)
# - MENTION_KEYWORDS (@prosauai,@resenhai)
```

### 3. Subir via Docker Compose

```bash
docker compose up -d
# Verificar saúde:
curl http://localhost:8040/health
# Esperado: {"status": "ok", "redis": true}
```

### 4. Rodar manualmente (dev)

```bash
# Terminal 1: Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine redis-server --notify-keyspace-events Ex

# Terminal 2: API
uvicorn prosauai.main:app --host 0.0.0.0 --port 8040 --reload
```

---

## Testar

```bash
# Rodar todos os testes
pytest

# Apenas unitários
pytest tests/unit/

# Apenas integração
pytest tests/integration/

# Com cobertura
pytest --cov=prosauai --cov-report=term-missing

# Lint
ruff check .
ruff format --check .
```

---

## Testar Webhook Manualmente

```bash
# Gerar assinatura HMAC
export WEBHOOK_SECRET="seu-secret-aqui"
export PAYLOAD='{"instance":"test","data":{"key":{"remoteJid":"5511999998888@s.whatsapp.net","fromMe":false,"id":"ABC123"},"message":{"conversation":"Ola mundo"},"messageType":"conversation","messageTimestamp":1712000000},"event":"messages.upsert"}'
export SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $2}')

# Enviar webhook
curl -X POST http://localhost:8040/webhook/whatsapp/test \
  -H "Content-Type: application/json" \
  -H "x-webhook-signature: $SIGNATURE" \
  -d "$PAYLOAD"

# Esperado: {"status":"queued","route":"support","message_id":"ABC123"}
```

---

## Estrutura do Projeto

```
prosauai/
├── prosauai/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py             # Settings (pydantic-settings)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── formatter.py      # parse_evolution_message(), format_for_whatsapp()
│   │   ├── router.py         # route_message(), MessageRoute, RouteResult
│   │   └── debounce.py       # DebounceManager (Lua script + keyspace listener)
│   ├── channels/
│   │   ├── __init__.py
│   │   ├── base.py           # MessagingProvider ABC
│   │   └── evolution.py      # EvolutionProvider (httpx)
│   └── api/
│       ├── __init__.py
│       ├── webhooks.py        # POST /webhook/whatsapp/{instance}
│       ├── health.py          # GET /health
│       └── dependencies.py    # verify_webhook_signature, get_settings
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   └── evolution_payloads.json
│   ├── unit/
│   │   ├── test_router.py
│   │   ├── test_formatter.py
│   │   └── test_debounce.py
│   └── integration/
│       ├── test_webhook.py
│       └── test_health.py
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

handoff:
  from: speckit.plan (quickstart)
  to: speckit.tasks
  context: "Quickstart documentado com setup, testes e estrutura do projeto. Pronto para task breakdown."
