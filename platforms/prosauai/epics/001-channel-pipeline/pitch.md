---
id: "001"
title: "Channel Pipeline"
status: shipped
phase: now
features:
  - "Receber e responder mensagens"
  - "Agente em grupos WhatsApp"
owner: ""
created: 2026-03-25
updated: 2026-04-09
target: ""
outcome: ""
arch:
  modules: [M1, M2, M3, M11]
  contexts: [channel]
  containers: [prosauai-api, redis, evolution-api]
delivered_at: 2026-04-09
---

# 001 — Channel Pipeline

## Escopo Arquitetural

| Camada | Blocos | Viewer |
|--------|--------|--------|
| Modulos | M1 (Recepcao), M2 (Buffer), M3 (Smart Router), M11 (Entrega) | [Containers (Interactive)](../../engineering/containers/) |
| Contextos | Channel | [Context Map](../../engineering/context-map/) |
| Containers | prosauai-api, redis, evolution-api | [Containers (Interactive)](../../engineering/containers/) |

## Problema

Nao existe infraestrutura base para receber mensagens WhatsApp, rotear por tipo (individual/grupo/@mention) e responder. Sem isso, nenhum outro epico pode ser implementado. O repositorio `paceautomations/prosauai` ainda nao existe — este epic cria o projeto do zero (greenfield).

## Valor de Negocio

- [ ] Webhook Evolution API recebe mensagens e responde echo
- [ ] Smart Router separa 6 tipos de mensagem (zero custo LLM para grupo sem @mention)
- [ ] Debounce agrupa mensagens rapidas (UX: nao responde 3x para quem digita rapido)
- [ ] Grupos salvos sem invocar LLM (economia desde dia 1)
- [ ] HMAC-SHA256 webhook validation desde dia 1 (ADR-017)

## Solucao

FastAPI recebe webhooks Evolution API com validacao HMAC-SHA256 (ADR-017) → Smart Router classifica tipo (6 paths incluindo HANDOFF_ATIVO stub) e retorna `RouteResult` com `agent_id` (None nesta fase — usa tenant default) → Redis debounce agrupa mensagens rapidas via Lua script atomico (3s window + jitter 0-1s anti-avalanche) com keyspace notifications para flush → Echo response enviada via Evolution API. Mensagens de grupo sem @mention registradas apenas em log estruturado (structlog). Config via pydantic Settings + `.env`. Sem DB persistence, sem ARQ worker, sem LLM nesta fase.

### Interfaces / Contratos

```python
# prosauai/config.py
class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8040
    api_key: str
    evolution_api_url: str
    evolution_api_key: str
    evolution_instance_name: str
    redis_url: str = "redis://localhost:6379"
    debounce_seconds: float = 3.0
    mention_phone: str  # phone JID para detectar @mention
    webhook_secret: str  # HMAC-SHA256 secret (ADR-017)

# prosauai/core/router.py
class MessageRoute(str, Enum):
    SUPPORT = "support"              # Individual normal
    GROUP_RESPOND = "group_respond"  # Grupo com @mention
    GROUP_SAVE_ONLY = "group_save"   # Grupo sem @mention
    GROUP_EVENT = "group_event"      # Evento de grupo (join/leave)
    HANDOFF_ATIVO = "handoff_ativo"  # Handoff ativo (stub → IGNORE no epic 001)
    IGNORE = "ignore"                # from_me ou invalido

@dataclass
class RouteResult:
    route: MessageRoute
    agent_id: UUID | None  # None para IGNORE/GROUP_SAVE_ONLY; resolvido por routing_rules ou default
    reason: str | None = None

# Epic 001: agent_id sempre None (usa tenant default). Routing rules em epic 003.
# HANDOFF_ATIVO retorna route=IGNORE com reason="handoff not implemented"
def route_message(msg: ParsedMessage, settings: Settings) -> RouteResult: ...

# prosauai/core/formatter.py
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

# prosauai/channels/base.py
class MessagingProvider(ABC):
    async def send_text(self, instance: str, number: str, text: str) -> str: ...
    async def send_media(self, instance: str, number: str, media_type: str, media: str, caption: str | None = None) -> str: ...

# prosauai/channels/evolution.py
class EvolutionProvider(MessagingProvider):
    # POST /message/sendText/{instance}
    # POST /message/sendMedia/{instance}
    # Headers: {"apikey": self.api_key}
    ...

# prosauai/api/webhooks.py
# POST /webhook/whatsapp/{instance_name}
# Headers: x-webhook-signature (HMAC-SHA256)
# Returns: {"status": "queued|ignored", "route": route.value, "message_id": msg.message_id}
```

### Scope

**Dentro:**
- Scaffold repo `paceautomations/prosauai` (pyproject.toml, structure, CI basics)
- Webhook FastAPI (POST /webhook/whatsapp/{instance}) com HMAC-SHA256 validation
- Health check (GET /health)
- Smart Router (6 paths incluindo HANDOFF_ATIVO stub, regex @mention ANTES de LLM)
- Redis debounce (Lua atomic script + keyspace notifications, 3s window + jitter 0-1s anti-avalanche)
- Evolution API adapter (send text + media)
- Message formatter (Evolution payload → ParsedMessage)
- Echo response (sem LLM — responde com texto recebido)
- Docker Compose (api + redis)
- Test fixtures com payloads reais capturados da Evolution API (`tests/fixtures/evolution_payloads.json`)

**Fora:**
- LLM / pydantic-ai agents (epico 002)
- Database persistence em Supabase (epico 002 — por ora log estruturado only)
- Routing rules configuravel por phone number (epico 003 — por ora usa tenant default)
- Agent pipeline steps (epico 016 — por ora single LLM call)
- Admin panel (epico 007)
- Handoff (epico 005 — enum presente, handler stub)
- Triggers proativos (epico 006)
- ARQ worker (simplificar: processar sincrono no webhook por ora)
- Infisical secrets management (epic posterior — por ora .env + Settings)
- Evolution API no Docker Compose (mock em testes, real so em staging)

## Rabbit Holes

- **Evolution API payload muda entre versoes** → Adapter pattern, testar com payloads reais capturados. Suportar: text, extendedText, image, document, video, audio, sticker, contact, location. Fixtures em `tests/fixtures/evolution_payloads.json` alimentadas com capturas reais
- **Redis Lua atomicity** → Usar EVAL com script unico, nao multiplos comandos separados. Adicionar jitter aleatorio (0-1s) no TTL do buffer para evitar avalanche de flushes simultaneos. Keyspace notifications (`__keyevent@0__:expired`) para trigger de flush
- **Worker overload sob pico** → ARQ `max_jobs` limita batches concorrentes (ex: 20). Semaforo asyncio limita chamadas LLM simultaneas (ex: 10). Backpressure: se fila > 100 jobs, worker desacelera consumo. Sem isso, 1000 msgs/s gera centenas de batches explodindo downstream
- **@mention detection** → Regex case-insensitive para phone JID + keywords ["@resenhai", "@prosauai"]. Checar ANTES de enviar para LLM
- **from_me loop** → Webhook recebe mensagens enviadas pelo proprio bot. Primeiro check no router: `if from_me: return IGNORE`
- **Group events** → member_joined/member_left vem como mensagens normais. Detectar via campo `messageType` ou ausencia de `body`
- **HMAC-SHA256 validation** → Rejeitar 100% das requests sem signature valida (ADR-017). Secret configuravel por `.env` nesta fase

## Tasks

- [ ] Scaffold repo prosauai (pyproject.toml, folder structure, .env.example, docker-compose.yml, ruff config)
- [ ] Smart Router — 6 paths (HANDOFF_ATIVO stub) com 8+ testes unitarios
- [ ] Message formatter — parse Evolution payload + format WhatsApp output
- [ ] Channel abstraction + Evolution provider (send_text, send_media)
- [ ] FastAPI app + webhook endpoint (HMAC-SHA256) + health check
- [ ] Redis debounce (Lua script + keyspace notifications + buffer keys)
- [ ] Test fixtures — capturar payloads reais da Evolution API em `tests/fixtures/evolution_payloads.json`
- [ ] Integration tests — webhook flow completo (8+ cases)
- [ ] Docker Compose funcional (api + redis)

## Criterios de Sucesso

- [ ] `POST /webhook/whatsapp/{instance}` com payload real → 200 OK
- [ ] Request sem HMAC-SHA256 valido → 401 Unauthorized
- [ ] Mensagem individual → echo response enviada via Evolution API
- [ ] Mensagem grupo sem @mention → log estruturado, zero resposta
- [ ] Mensagem grupo com @mention → echo response
- [ ] `GET /health` → 200 `{"status": "ok"}`
- [ ] `pytest` → 14+ testes passando (8 unit + 6 integration)
- [ ] `ruff check .` → zero errors
- [ ] Docker Compose sobe api + redis sem erros

## Decisoes

| Data | Decisao | Rationale |
|------|---------|-----------|
| 2026-03-25 | pydantic-ai v1.70 como agent framework | Native Pydantic 2, MCP+A2A (ADR-001) |
| 2026-03-25 | Echo sem LLM nesta fase | Validar infra antes de adicionar complexidade LLM |
| 2026-03-25 | Sem ARQ worker nesta fase | Simplificar: processar sincrono. Worker no epico 002 |
| 2026-03-25 | Sem DB persistence nesta fase | Log estruturado suficiente para echo. Supabase no epico 002 |
| 2026-04-09 | RouteResult inclui agent_id desde dia 1 | Evita breaking change futuro. None = usa tenant default. Routing rules no epic 003 |
| 2026-04-09 | Enum com 6 rotas (incl. HANDOFF_ATIVO stub) | Alinhado com domain model. Stub retorna IGNORE. Evita breaking change no epic 005 |
| 2026-04-09 | HMAC-SHA256 webhook validation desde dia 1 | ADR-017 obrigatorio: "validar signature de TODA webhook recebida" |
| 2026-04-09 | Redis Lua + keyspace notifications para debounce | Atomico, sobrevive restart. Alternativa asyncio.create_task descartada por risco de perda |
| 2026-04-09 | Docker Compose sem Evolution API | Mock em testes, Evolution real so em staging. Compose leve (api + redis) |
| 2026-04-09 | Config via pydantic Settings + .env | Sem Infisical nesta fase. Swap futuro transparente via Settings |
| 2026-04-09 | Log estruturado para msgs grupo sem @mention | Sem DB nesta fase. structlog com phone_hash, group_id, route |
| 2026-04-09 | Test fixtures com payloads reais da Evolution API | Captura manual de todos os tipos de mensagem. Fonte unica de truth para mocks |
| 2026-04-09 | Repo externo paceautomations/prosauai | Respeita platform.yaml repo binding. Scaffold como primeira task do epic |

## Notas

(Append-only — adicionar descobertas durante implementacao)

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|---------|----------------------|
| 1 | Repo | Scaffold repo externo `paceautomations/prosauai` como primeira task | platform.yaml repo binding |
| 2 | Routing | Enum com 6 rotas (incl. HANDOFF_ATIVO stub → IGNORE) | domain-model Channel BC |
| 3 | Security | HMAC-SHA256 webhook validation obrigatoria desde dia 1 | ADR-017 |
| 4 | Debounce | Redis Lua script atomico + keyspace notifications para flush | ADR-003, blueprint §4.6 |
| 5 | Infra | Docker Compose apenas api + redis; Evolution API mockada | ADR-005 §hardening |
| 6 | Config | pydantic Settings + .env; Infisical em epic posterior | ADR-017 (futuro) |
| 7 | Persistence | Log estruturado (structlog) para msgs sem resposta; zero DB | blueprint §1 (Supabase no epic 002) |
| 8 | Testing | Fixtures com payloads reais capturados da Evolution API | ADR-005 (payload instavel entre versoes) |
| 9 | Processing | Sincrono no webhook; sem ARQ worker nesta fase | containers.md (worker no epic 002) |
| 10 | Forward-compat | RouteResult.agent_id desde dia 1 (None = tenant default) | domain-model Router aggregate |

## Resolved Gray Areas

**Debounce sem worker**: Redis Lua script atomico com keyspace notifications resolve o flush apos 3s. O subscriber de expired keys vive como asyncio background task no FastAPI (nao ARQ). Alternativa asyncio.create_task puro descartada por risco de perda de msgs em restart.

**6 vs 5 rotas**: Domain model define HANDOFF_ATIVO como 6a rota. Implementar enum completo com stub (retorna IGNORE + reason) para evitar breaking change no epic 005.

**Webhook security**: ADR-017 e explicito ("validar signature de TODA webhook"). Implementar desde dia 1 com secret via `.env`. Nao e over-engineering — e requisito.

**"Salvar" msgs grupo**: Apenas log estruturado com campos relevantes (phone_hash, group_id, route, timestamp). Consultavel via log aggregation. DB real no epic 002.

**Evolution API em dev**: Mocks baseados em payloads reais capturados. O usuario vai enviar todos os tipos de mensagem para Evolution API e capturar os payloads em `tests/fixtures/evolution_payloads.json`. Isso garante fidelidade dos testes sem peso de rodar Evolution local.

## Applicable Constraints

| Constraint | Source | Impact |
|-----------|--------|--------|
| HMAC-SHA256 obrigatorio em toda webhook | ADR-017 | Validacao no middleware FastAPI |
| Evolution API v2.x instavel — fixar versao | ADR-005 §hardening | Nao usar tag `latest` |
| Channel Adapter pattern (interface abstrata) | ADR-005, context-map | MessagingProvider ABC |
| Redis Streams para mensageria (futuro) | ADR-003 | Debounce usa Redis direto; Streams no epic 002 com worker |
| Config nunca em codigo | ADR-017 | pydantic Settings + .env |
| Debounce jitter obrigatorio | blueprint §4.6 | Lua script adiciona 0-1s aleatorio no TTL |
| from_me check primeiro no router | pitch §rabbit-holes | Evita loop infinito de echo |

## Suggested Approach

1. **Scaffold** — criar repo `paceautomations/prosauai` com estrutura de folders do blueprint, pyproject.toml (ruff, pytest, deps), .env.example, docker-compose.yml (api + redis)
2. **Core models** — `ParsedMessage`, `MessageRoute` enum (6 valores), `RouteResult` dataclass
3. **Message formatter** — `parse_evolution_message()` com payloads reais como fixtures
4. **Smart Router** — `route_message()` com 6 paths, regex @mention, from_me guard
5. **Channel adapter** — `MessagingProvider` ABC + `EvolutionProvider` (send_text, send_media)
6. **Redis debounce** — Lua script atomico (EVAL), keyspace notifications subscriber, flush handler
7. **FastAPI app** — webhook endpoint (HMAC middleware), health check, debounce integration
8. **Echo handler** — processar sincrono: parse → route → debounce → echo via EvolutionProvider
9. **Docker Compose** — api + redis, healthchecks
10. **Test fixtures** — capturar payloads reais, popular `tests/fixtures/evolution_payloads.json`

> **Proximo passo:** `/speckit.specify prosauai 001` — especificar feature detalhada a partir deste contexto.
