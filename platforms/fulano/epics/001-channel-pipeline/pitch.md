---
id: "001"
title: "Channel Pipeline"
status: planned
phase: now
appetite: "1 semana"
features:
  - "Receber e responder mensagens"
  - "Agente em grupos WhatsApp"
owner: ""
created: 2026-03-25
target: ""
outcome: ""
arch:
  modules: [M1, M2, M3, M11]
  contexts: [channel]
  containers: [fulano-api, redis, evolution-api]
---

# 001 — Channel Pipeline

## Escopo Arquitetural

| Camada | Blocos | Viewer |
|--------|--------|--------|
| Modulos | M1 (Recepcao), M2 (Buffer), M3 (Smart Router), M11 (Entrega) | [Containers (Interactive)](/fulano/containers/) |
| Contextos | Channel | [Context Map](/fulano/context-map/) |
| Containers | fulano-api, redis, evolution-api | [Containers (Interactive)](/fulano/containers/) |

## Problema

Nao existe infraestrutura base para receber mensagens WhatsApp, rotear por tipo (individual/grupo/@mention) e responder. Sem isso, nenhum outro epico pode ser implementado.

## Appetite

1 semana. Se nao cabe nesse tempo, cortamos scope — nao estendemos prazo.

## Valor de Negocio

- [ ] Webhook Evolution API recebe mensagens e responde echo
- [ ] Smart Router separa 5 tipos de mensagem (zero custo LLM para grupo sem @mention)
- [ ] Debounce agrupa mensagens rapidas (UX: nao responde 3x para quem digita rapido)
- [ ] Grupos salvos sem invocar LLM (economia desde dia 1)

## Solucao

FastAPI recebe webhooks Evolution API → Smart Router classifica tipo (5 paths) → Redis debounce agrupa mensagens rapidas (3s window, Lua atomic) → ARQ worker processa batch → Echo response enviada via Evolution API. Todas mensagens persistidas em Supabase PostgreSQL.

### Interfaces / Contratos

```python
# fulano/config.py
class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8040
    api_key: str
    evolution_api_url: str
    evolution_api_key: str
    evolution_instance_name: str
    redis_url: str = "redis://localhost:6379"
    database_url: str
    debounce_seconds: float = 3.0
    mention_phone: str  # phone JID para detectar @mention

# fulano/core/router.py
class MessageRoute(str, Enum):
    SUPPORT = "support"              # Individual normal
    GROUP_RESPOND = "group_respond"  # Grupo com @mention
    GROUP_SAVE_ONLY = "group_save"   # Grupo sem @mention
    GROUP_EVENT = "group_event"      # Evento de grupo (join/leave)
    IGNORE = "ignore"                # from_me ou invalido

def route_message(msg: ParsedMessage, settings: Settings) -> MessageRoute: ...

# fulano/core/formatter.py
class ParsedMessage(BaseModel):
    phone: str
    text: str
    sender_name: str | None
    message_id: str
    is_group: bool
    group_id: str | None
    from_me: bool
    mentioned_phones: list[str]
    media_type: str | None
    media_url: str | None
    timestamp: datetime
    instance: str
    is_group_event: bool

def parse_evolution_message(payload: dict, instance: str) -> ParsedMessage: ...
def format_for_whatsapp(text: str) -> str: ...

# fulano/channels/base.py
class MessagingProvider(ABC):
    async def send_text(self, instance: str, number: str, text: str) -> str: ...
    async def send_media(self, instance: str, number: str, media_type: str, media: str, caption: str | None = None) -> str: ...

# fulano/channels/evolution.py
class EvolutionProvider(MessagingProvider):
    # POST /message/sendText/{instance}
    # POST /message/sendMedia/{instance}
    # Headers: {"apikey": self.api_key}
    ...

# fulano/api/webhooks.py
# POST /webhook/whatsapp/{instance_name}
# Returns: {"status": "queued|ignored", "route": route.value, "message_id": msg.message_id}
```

### Scope

**Dentro:**
- Webhook FastAPI (POST /webhook/whatsapp/{instance})
- Health check (GET /health)
- Smart Router (5 paths, regex @mention ANTES de LLM)
- Redis debounce (Lua atomic, 3s window)
- Evolution API adapter (send text + media)
- Message formatter (Evolution payload → ParsedMessage)
- Echo response (sem LLM — responde com texto recebido)
- Docker Compose (api + redis)

**Fora:**
- LLM / pydantic-ai agents (epico 002)
- Database persistence em Supabase (epico 002 — por ora in-memory/log)
- Admin panel (epico 007)
- Handoff (epico 005)
- Triggers proativos (epico 006)
- ARQ worker (simplificar: processar sincrono no webhook por ora)

## Rabbit Holes

- **Evolution API payload muda entre versoes** → Adapter pattern, testar com payload real capturado. Suportar: text, extendedText, image, document, video, audio, sticker, contact, location
- **Redis Lua atomicity** → Usar EVAL com script unico, nao multiplos comandos separados
- **@mention detection** → Regex case-insensitive para phone JID + keywords ["@resenhai", "@fulano"]. Checar ANTES de enviar para LLM
- **from_me loop** → Webhook recebe mensagens enviadas pelo proprio bot. Primeiro check no router: `if from_me: return IGNORE`
- **Group events** → member_joined/member_left vem como mensagens normais. Detectar via campo `messageType` ou ausencia de `body`

## Tasks

- [ ] Project scaffold + config (pyproject.toml, requirements.txt, .env.example, docker-compose.yml)
- [ ] Smart Router — 5 paths com 6+ testes unitarios
- [ ] Message formatter — parse Evolution payload + format WhatsApp output
- [ ] Channel abstraction + Evolution provider (send_text, send_media)
- [ ] FastAPI app + webhook endpoint + health check
- [ ] Redis debounce (Lua script + buffer keys)
- [ ] Integration tests — webhook flow completo (6+ cases)
- [ ] Docker Compose funcional (api + redis)

## Criterios de Sucesso

- [ ] `POST /webhook/whatsapp/{instance}` com payload real → 200 OK
- [ ] Mensagem individual → echo response enviada via Evolution API
- [ ] Mensagem grupo sem @mention → salva (log), zero resposta
- [ ] Mensagem grupo com @mention → echo response
- [ ] `GET /health` → 200 `{"status": "ok"}`
- [ ] `pytest` → 12+ testes passando (6 unit + 6 integration)
- [ ] `ruff check .` → zero errors
- [ ] Docker Compose sobe api + redis sem erros

## Decisoes

| Data | Decisao | Rationale |
|------|---------|-----------|
| 2026-03-25 | pydantic-ai v1.70 como agent framework | Native Pydantic 2, MCP+A2A (ADR-001) |
| 2026-03-25 | Echo sem LLM nesta fase | Validar infra antes de adicionar complexidade LLM |
| 2026-03-25 | Sem ARQ worker nesta fase | Simplificar: processar sincrono. Worker no epico 002 |
| 2026-03-25 | Sem DB persistence nesta fase | In-memory/log suficiente para echo. Supabase no epico 002 |

## Notas

(Append-only — adicionar descobertas durante implementacao)
