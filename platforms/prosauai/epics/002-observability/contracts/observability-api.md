# Contracts — Observability API

**Branch**: `epic/prosauai/002-observability` | **Date**: 2026-04-10

## 1. Módulo `prosauai.observability` — Interface Pública

### `setup.py` — Ponto de Entrada

```python
def configure_observability(settings: Settings) -> None:
    """Configura OTel SDK + Phoenix exporter + structlog bridge.
    
    Chamado uma vez no lifespan startup de main.py.
    
    Pré-condição: settings.otel_enabled == True
    Pós-condição: TracerProvider configurado globalmente
    
    Se settings.otel_enabled == False, retorna sem configurar (no-op).
    """
```

### `conventions.py` — SpanAttributes Constants

```python
class SpanAttributes:
    """Constantes para atributos customizados de spans (namespace prosauai.*)."""
    
    # Tenant + Identity
    TENANT_ID = "tenant_id"
    PHONE_HASH = "prosauai.phone_hash"
    
    # Routing
    ROUTE = "prosauai.route"
    AGENT_ID = "prosauai.agent_id"
    IS_GROUP = "prosauai.is_group"
    FROM_ME = "prosauai.from_me"
    GROUP_ID = "prosauai.group_id"
    
    # Messaging (OTel Semantic Conventions)
    MESSAGING_SYSTEM = "messaging.system"
    MESSAGING_DESTINATION = "messaging.destination.name"
    MESSAGING_MESSAGE_ID = "messaging.message.id"
    
    # Debounce
    DEBOUNCE_BUFFER_SIZE = "prosauai.debounce.buffer_size"
    DEBOUNCE_WAIT_MS = "prosauai.debounce.wait_ms"
    
    # Provider
    PROVIDER_NAME = "prosauai.provider"
    PROVIDER_HTTP_STATUS = "http.response.status_code"
    
    # GenAI (reserved for epic 003)
    GEN_AI_SYSTEM = "gen_ai.system"
    GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
```

### `structlog_bridge.py` — Processor

```python
def add_otel_context(logger, method_name, event_dict) -> dict:
    """Structlog processor — injeta trace_id/span_id do span OTel ativo.
    
    Pré-condição: nenhuma (safe para chamar sem span ativo)
    Pós-condição: event_dict contém trace_id (32 hex) e span_id (16 hex) 
                  se houver span ativo válido; caso contrário, sem modificação.
    """
```

---

## 2. Health Endpoint — Contrato Estendido

### Request
```
GET /health
```

### Response (200 OK — sempre)
```json
{
    "status": "ok",
    "redis": true,
    "observability": {
        "status": "ok",
        "last_export_success": true
    }
}
```

### Response (200 OK — degraded)
```json
{
    "status": "degraded",
    "redis": false,
    "observability": {
        "status": "degraded",
        "last_export_success": false
    }
}
```

**Nota**: O campo `observability` é informacional. O status geral do API (`status`) continua determinado apenas pelo Redis. Nunca retorna 503 por falha OTel.

---

## 3. Docker Compose — Container Phoenix

### Contrato de Rede
| Container | Porta | Protocolo | Exposto |
|-----------|-------|-----------|---------|
| phoenix | 6006 | HTTP | UI (localhost only) |
| phoenix | 4317 | gRPC | OTLP collector (interno compose) |

### Variáveis de Ambiente Obrigatórias
| Variável | Valor | Descrição |
|----------|-------|-----------|
| `PHOENIX_SQL_DATABASE_URL` | `postgresql://...` | Connection string Supabase com schema observability |
| `PHOENIX_PROJECT_NAME` | `prosauai` | Nome do projeto no Phoenix UI |

### Dependências
```yaml
phoenix:
  depends_on: []  # Phoenix é independente
api:
  depends_on:
    redis: service_healthy
    # Phoenix NÃO é dependency — API funciona sem Phoenix (fire-and-forget)
```

---

## 4. Settings — Novas Variáveis de Ambiente

| Variável | Tipo | Default | Obrigatória | Descrição |
|----------|------|---------|-------------|-----------|
| `PHOENIX_GRPC_ENDPOINT` | str | `http://localhost:4317` | Não | Endpoint gRPC do collector Phoenix |
| `OTEL_SERVICE_NAME` | str | `prosauai-api` | Não | Nome do serviço no OTel Resource |
| `OTEL_SAMPLER_ARG` | float | `1.0` | Não | Taxa de sampling (1.0 = 100%, 0.1 = 10%) |
| `TENANT_ID` | str | `prosauai-default` | Não | ID do tenant (placeholder para multi-tenant) |
| `DEPLOYMENT_ENV` | str | `development` | Não | Ambiente de deploy |
| `OTEL_ENABLED` | bool | `true` | Não | Habilita/desabilita OTel SDK |

---

## 5. Span Hierarchy — Contrato de Nomes

### Jornada Típica (1 mensagem direta → echo)
```
webhook_whatsapp [SERVER]               # root span
├── parse_evolution_message [INTERNAL]  # auto (FastAPI middleware)
├── route_message [INTERNAL]            # manual span
├── debounce.append [INTERNAL]          # manual span
│   └── RPUSH [CLIENT]                 # auto (redis instrumentation)
...
debounce.flush [INTERNAL]               # manual span (parent via W3C context)
├── LRANGE [CLIENT]                    # auto (redis)
├── DEL [CLIENT]                       # auto (redis)
├── format_for_whatsapp [INTERNAL]     # manual span
└── send_echo [INTERNAL]               # manual span
    └── POST evolution-api [CLIENT]    # auto (httpx instrumentation)
```

### Jornada com Debounce (3 msgs rápidas → 1 echo)
```
webhook_whatsapp [1] → debounce.append [1]    # trace A (parent)
webhook_whatsapp [2] → debounce.append [2]    # trace A (linked)
webhook_whatsapp [3] → debounce.append [3]    # trace A (linked)
...
debounce.flush [parent=1, links=[2,3]]
├── format_for_whatsapp
└── send_echo → POST evolution-api
```
