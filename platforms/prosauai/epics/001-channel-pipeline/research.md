# Research: Channel Pipeline

**Epic**: 001-channel-pipeline  
**Date**: 2026-04-09  
**Status**: Complete

## 1. HMAC-SHA256 Webhook Validation em FastAPI

### Decision: Custom APIRoute com acesso ao raw body

### Rationale
FastAPI consome o request body ao parsear JSON via Pydantic. Para validar HMAC-SHA256, precisamos do raw body (bytes) ANTES do parsing. A abordagem mais limpa é usar `Request.body()` diretamente no endpoint ou via dependency, computar o HMAC, e só então parsear.

### Alternativas Consideradas

| Alternativa | Pros | Cons | Veredicto |
|-------------|------|------|-----------|
| **A) Middleware ASGI** | Intercepta antes de qualquer processamento; centralizado | Precisa fazer buffer do body (consume stream); complexidade ASGI; dificil retornar JSON errors padrao | Rejeitado |
| **B) Custom APIRoute class** | Intercepta antes do handler; acesso ao body; pattern documentado pelo FastAPI | Acoplamento a APIRoute; precisa custom route class | Rejeitado — over-engineering para 1 endpoint |
| **C) Dependency injection com Request.body()** | Simples; idiomático FastAPI; testável; body raw disponível via `await request.body()` | Body fica em memória (aceitável para payloads pequenos de webhook) | **Escolhido** |

### Implementação Recomendada

```python
import hmac
import hashlib
from fastapi import Request, HTTPException, Depends

async def verify_webhook_signature(request: Request, settings: Settings = Depends(get_settings)) -> bytes:
    """Dependency que valida HMAC e retorna raw body."""
    body = await request.body()
    signature = request.headers.get("x-webhook-signature", "")
    expected = hmac.new(
        settings.webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    return body
```

**Fonte**: [FastAPI Custom Request and Route](https://fastapi.tiangolo.com/how-to/custom-request-and-route) — pattern para acessar raw body.

---

## 2. Redis Debounce com Lua Script Atômico

### Decision: Lua EVAL com APPEND + PEXPIRE atômico + keyspace notifications para flush

### Rationale
O debounce precisa: (1) acumular mensagens em buffer, (2) resetar TTL a cada nova mensagem, (3) notificar quando o buffer expira para flush. Redis Lua scripts são atômicos — durante a execução, nenhum outro comando é processado. Keyspace notifications (`__keyevent@0__:expired`) disparam quando uma key expira, servindo como trigger de flush.

### Alternativas Consideradas

| Alternativa | Pros | Cons | Veredicto |
|-------------|------|------|-----------|
| **A) asyncio.sleep + in-memory dict** | Zero dependência externa; simples | Perde dados em restart; não escala horizontal; race conditions em concurrent access | Rejeitado |
| **B) Redis MULTI/EXEC (pipeline)** | Atômico em batch | Não é verdadeiramente atômico entre commands; outro client pode intercalar | Rejeitado |
| **C) Redis Lua EVAL** | Verdadeiramente atômico; sobrevive restart (dados no Redis); escalável | Lua scripts bloqueiam Redis durante execução (aceitável para scripts curtos <1ms) | **Escolhido** |
| **D) Redis Streams** | Built-in consumer groups; replay; DLQ | Over-engineering para debounce simples; complexidade de consumer groups | Rejeitado para epic 001 (será usado no epic 002 para worker) |

### Design do Lua Script

```lua
-- debounce_append.lua
-- KEYS[1] = buffer key (e.g., "debounce:{phone}:{group_id|direct}")
-- ARGV[1] = message text
-- ARGV[2] = TTL in milliseconds (debounce_seconds * 1000 + jitter)
-- Returns: current buffer size (number of messages)

local current = redis.call('GET', KEYS[1])
if current then
    -- Append com separator newline
    redis.call('APPEND', KEYS[1], '\n' .. ARGV[1])
else
    redis.call('SET', KEYS[1], ARGV[1])
end
redis.call('PEXPIRE', KEYS[1], ARGV[2])
return redis.call('STRLEN', KEYS[1])
```

### Keyspace Notifications

```bash
# Habilitar keyspace notifications para eventos de expiração
CONFIG SET notify-keyspace-events Ex
```

O subscriber escuta `__keyevent@0__:expired` e recebe o nome da key expirada. Como o valor já foi deletado na expiração, precisamos de uma shadow key pattern:

**Abordagem refinada**: Usar duas keys — `buffer:{id}` (dados) e `timer:{id}` (TTL trigger). O Lua script atualiza ambas. Quando `timer:{id}` expira, o subscriber lê e deleta `buffer:{id}` atomicamente via GETDEL.

```lua
-- debounce_append_v2.lua
-- KEYS[1] = buffer key "buf:{phone}:{ctx}"
-- KEYS[2] = timer key "tmr:{phone}:{ctx}"
-- ARGV[1] = message text
-- ARGV[2] = TTL in milliseconds

local current = redis.call('GET', KEYS[1])
if current then
    redis.call('APPEND', KEYS[1], '\n' .. ARGV[1])
else
    redis.call('SET', KEYS[1], ARGV[1])
end
-- Timer key controla expiração; buffer key não tem TTL
redis.call('SET', KEYS[2], '1')
redis.call('PEXPIRE', KEYS[2], ARGV[2])
-- Buffer key com TTL de safety (2x debounce) para evitar leak
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[2]) * 2)
return redis.call('STRLEN', KEYS[1])
```

### Flush Handler (Python)

```python
async def on_timer_expired(key: str):
    """Chamado quando timer:{phone}:{ctx} expira."""
    buffer_key = key.replace("tmr:", "buf:", 1)
    messages = await redis.getdel(buffer_key)  # Atômico: lê e deleta
    if messages:
        await process_debounced(buffer_key, messages.decode())
```

**Fonte**: [Redis EVAL documentation](https://redis.io/docs/latest/commands/eval/) — atomicidade garantida durante execução Lua. [Redis Keyspace Notifications](https://redis.io/docs/latest/develop/use/keyspace-notifications/) — `Ex` flag para expired events.

---

## 3. redis.asyncio para Subscriber de Keyspace Notifications

### Decision: redis.asyncio PubSub com psubscribe em asyncio task

### Rationale
O redis-py suporta async nativo via `redis.asyncio`. O subscriber de keyspace notifications roda como background task no FastAPI lifespan, usando `psubscribe("__keyevent@0__:expired")` com pattern matching.

### Implementação Recomendada

```python
import redis.asyncio as aioredis

async def keyspace_listener(redis_client: aioredis.Redis, handler):
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("__keyevent@0__:expired")
    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            key = message["data"].decode()
            if key.startswith("tmr:"):
                await handler(key)
```

**Fonte**: [redis-py async examples](https://github.com/redis/redis-py/blob/master/docs/examples/asyncio_examples.ipynb) — pattern para async PubSub.

---

## 4. FastAPI Lifespan para Background Tasks

### Decision: Lifespan context manager para inicializar Redis subscriber

### Rationale
FastAPI 0.109+ usa lifespan events (substitui on_startup/on_shutdown). O subscriber de keyspace notifications é iniciado no startup e cancelado no shutdown.

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    redis = aioredis.from_url(settings.redis_url)
    task = asyncio.create_task(keyspace_listener(redis, on_timer_expired))
    app.state.redis = redis
    app.state.listener_task = task
    yield
    # Shutdown
    task.cancel()
    await redis.close()
```

---

## 5. Evolution API Payload Structure

### Decision: Adapter pattern com ParsedMessage como modelo canônico

### Rationale
A Evolution API v2.x tem payloads instáveis entre versões (ADR-005). O adapter pattern isola o core do formato específico da API. Todos os testes usam payloads reais capturados como fixtures.

### Tipos de Mensagem Suportados

| Tipo | Campo no payload | Extração de texto |
|------|-----------------|-------------------|
| text | `message.conversation` | Direto |
| extendedText | `message.extendedTextMessage.text` | Direto |
| image | `message.imageMessage.caption` | Caption ou None |
| document | `message.documentMessage.caption` | Caption ou None |
| video | `message.videoMessage.caption` | Caption ou None |
| audio | `message.audioMessage` | None (sem texto) |
| sticker | `message.stickerMessage` | None (sem texto) |
| contact | `message.contactMessage.displayName` | Display name |
| location | `message.locationMessage` | Lat/Lon como texto |

### Detecção de Grupo e @mention

```python
# Grupo: key contém "@g.us"
is_group = "@g.us" in remote_jid

# @mention: verificar mentioned_phones + keywords no texto
mentioned = payload.get("message", {}).get("extendedTextMessage", {}).get("contextInfo", {}).get("mentionedJid", [])
keywords = settings.mention_keywords  # ["@prosauai", "@resenhai"]
is_mentioned = (
    settings.mention_phone in mentioned
    or any(kw.lower() in text.lower() for kw in keywords)
)
```

---

## 6. Estrutura de Projeto e Dependências

### Decision: Estrutura flat alinhada com blueprint, pyproject.toml com deps mínimas

### Dependências do Epic 001

| Pacote | Versão | Justificativa |
|--------|--------|---------------|
| fastapi | >=0.115.0 | Framework web (lifespan, dependencies) |
| uvicorn[standard] | >=0.30.0 | ASGI server |
| pydantic | >=2.0 | Validação e Settings |
| pydantic-settings | >=2.0 | Gerenciamento de configuração via .env |
| redis[hiredis] | >=5.0 | Client Redis async com parser C |
| structlog | >=24.0 | Logging estruturado |
| httpx | >=0.27.0 | HTTP client async para Evolution API |

**Dev dependencies**: pytest, pytest-asyncio, pytest-cov, ruff, httpx (para TestClient)

---

## 7. Docker Compose (api + redis)

### Decision: Compose mínimo com healthchecks

```yaml
services:
  api:
    build: .
    ports: ["8040:8040"]
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8040/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  redis:
    image: redis:7-alpine
    command: redis-server --notify-keyspace-events Ex
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3
```

**Nota**: `--notify-keyspace-events Ex` habilita keyspace notifications na inicialização do Redis.

---

## 8. Fallback de Debounce sem Redis

### Decision: Processar mensagem imediatamente sem debounce quando Redis indisponível

### Rationale
Se Redis estiver indisponível durante o debounce, a mensagem é processada imediatamente (sem agrupamento) com warning no log. Isso garante que o sistema não para completamente por falha do Redis — degrada gracefully.

### Alternativas Consideradas

| Alternativa | Pros | Cons | Veredicto |
|-------------|------|------|-----------|
| **A) Falhar com 503** | Explicito; client pode retry | Perde mensagem se webhook não tem retry nativo | Rejeitado |
| **B) In-memory fallback** | Mantém debounce | Perde dados em restart; complexidade dual | Rejeitado |
| **C) Processar sem debounce** | Simples; mensagem nunca perdida | Pode gerar respostas duplicadas em burst | **Escolhido** |

---

handoff:
  from: speckit.plan (Phase 0)
  to: speckit.plan (Phase 1)
  context: "Todas as pesquisas concluídas. HMAC via dependency injection, debounce via dual-key Lua + keyspace notifications, Evolution API adapter pattern, redis.asyncio para subscriber. Pronto para data-model e contracts."
