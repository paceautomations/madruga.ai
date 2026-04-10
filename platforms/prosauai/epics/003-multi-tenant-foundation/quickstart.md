# Quickstart — 003 Multi-Tenant Foundation

**Date**: 2026-04-10  
**Epic**: `epic/prosauai/003-multi-tenant-foundation`

---

## Pré-requisitos

- Python 3.12+
- Redis 7 rodando (local ou Docker)
- Docker + Docker Compose (para deploy)
- Tailscale configurado (para acesso dev à VPS)
- 2 instâncias Evolution API configuradas (Ariel + ResenhAI)

## Setup Local (Desenvolvimento)

### 1. Clonar e instalar dependências

```bash
cd ~/repos/paceautomations/prosauai
git checkout epic/prosauai/003-multi-tenant-foundation
pip install -e ".[dev]"
```

### 2. Configurar environment variables

```bash
cp .env.example .env
# Editar .env com valores reais:
# PACE_EVOLUTION_API_KEY=...
# PACE_WEBHOOK_SECRET=...
# RESENHA_EVOLUTION_API_KEY=...
# RESENHA_WEBHOOK_SECRET=...
```

### 3. Configurar tenants

```bash
cp config/tenants.example.yaml config/tenants.yaml
# Editar config/tenants.yaml com valores reais
# (secrets já são interpolados via ${ENV_VAR} do .env)
```

### 4. Subir Redis

```bash
docker compose up redis -d
```

### 5. Rodar a aplicação

```bash
uvicorn prosauai.main:app --host 0.0.0.0 --port 8050 --reload
```

### 6. Testar manualmente

```bash
# Webhook para tenant Ariel
curl -X POST http://localhost:8050/webhook/whatsapp/Ariel \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: $(grep PACE_WEBHOOK_SECRET .env | cut -d= -f2)" \
  -d '{"event": "messages.upsert", "instance": "Ariel", "data": {"key": {"remoteJid": "5511999998888@s.whatsapp.net", "id": "TEST001", "fromMe": false}, "messageType": "conversation", "message": {"conversation": "teste"}, "messageTimestamp": 1712764800, "pushName": "Teste"}}'

# Esperado: 200 {"status": "processed"}

# Repetir mesmo request:
# Esperado: 200 {"status": "duplicate"}

# Tenant desconhecido:
curl -X POST http://localhost:8050/webhook/whatsapp/Desconhecido \
  -H "X-Webhook-Secret: qualquer" \
  -d '{}'
# Esperado: 404

# Secret errado:
curl -X POST http://localhost:8050/webhook/whatsapp/Ariel \
  -H "X-Webhook-Secret: errado" \
  -d '{}'
# Esperado: 401
```

## Rodar Testes

```bash
# Todos os testes
pytest

# Apenas testes de fixtures capturadas (26 casos)
pytest tests/integration/test_captured_fixtures.py -v

# Apenas testes unitários
pytest tests/unit/ -v

# Com coverage
pytest --cov=prosauai --cov-report=term-missing
```

## Deploy (Docker)

### Dev (com Tailscale)

```bash
cp docker-compose.override.example.yml docker-compose.override.yml
# Editar docker-compose.override.yml com IP Tailscale
docker compose up -d
```

### Prod Fase 1 (Docker network)

```bash
# Criar network compartilhada (se não existir)
docker network create pace-net

# Subir serviço (sem override — sem ports expostas)
docker compose up -d
```

## Onboarding de Novo Tenant

1. Gerar webhook secret: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Adicionar env vars ao `.env`: `NOVO_EVOLUTION_API_KEY=...`, `NOVO_WEBHOOK_SECRET=...`
3. Adicionar entry em `config/tenants.yaml` (copiar template)
4. Descobrir `mention_lid_opaque`:
   - Apontar webhook da Evolution para webhook.site ou capture tool
   - Pedir para alguém mencionar o bot em um grupo
   - Ler `data.contextInfo.mentionedJid` no capture
   - Extrair `<15-digit>@lid` e salvar em `tenants.yaml`
5. Configurar webhook na Evolution: `http://<host>:8050/webhook/whatsapp/<instance_name>`
6. Reiniciar o serviço: `docker compose restart api`

## Estrutura de Arquivos Relevantes

```
prosauai/
├── prosauai/
│   ├── main.py              # Lifespan loads TenantStore
│   ├── config.py            # Settings (global only — no tenant fields)
│   ├── core/
│   │   ├── tenant.py        # NEW: Tenant dataclass
│   │   ├── tenant_store.py  # NEW: TenantStore with YAML loader
│   │   ├── idempotency.py   # NEW: check_and_mark_seen()
│   │   ├── formatter.py     # REWRITTEN: 12 parser corrections
│   │   ├── router.py        # MODIFIED: route_message(msg, tenant)
│   │   └── debounce.py      # MODIFIED: tenant-prefixed keys
│   ├── api/
│   │   ├── dependencies.py  # REWRITTEN: resolve_tenant_and_authenticate()
│   │   └── webhooks.py      # MODIFIED: full multi-tenant flow
│   └── observability/
│       ├── setup.py         # MODIFIED: remove tenant_id from Resource
│       └── conventions.py   # UNCHANGED: SpanAttributes.TENANT_ID preserved
├── config/
│   ├── tenants.yaml         # gitignored
│   └── tenants.example.yaml # committed
├── tests/
│   ├── fixtures/captured/   # 26 real fixture pairs
│   ├── unit/
│   └── integration/
│       └── test_captured_fixtures.py  # NEW: parametric fixture tests
├── docker-compose.yml       # No ports exposed
├── docker-compose.override.example.yml  # Tailscale dev bind
└── .env.example
```

---

handoff:
  from: speckit.plan (quickstart)
  to: speckit.tasks
  context: "Quickstart completo com setup local, testes, deploy, e onboarding de novo tenant. Estrutura de arquivos documentada."
  blockers: []
  confidence: Alta
  kill_criteria: "Se estrutura de diretórios mudar significativamente durante implementação."
