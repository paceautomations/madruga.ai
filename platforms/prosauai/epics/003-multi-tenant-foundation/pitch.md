---
id: "003"
title: "Multi-Tenant Foundation — Auth + Parser Reality + Deploy"
status: drafted
phase: now
features:
  - "Tenant abstraction + TenantStore (YAML file-backed, 2 tenants reais desde dia 1)"
  - "Auth webhook via X-Webhook-Secret per-tenant (remove HMAC imaginario)"
  - "Idempotencia por (tenant_id, message_id) via Redis SETNX 24h"
  - "Parser Evolution v2.3.0: 12 correcoes criticas (messageType reais, @lid, mentionedJid, groups.upsert, group-participants.update)"
  - "Fixture-driven testing — 26 payloads reais capturados substituem fixture sintetica"
  - "Deploy isolado por rede: Tailscale (dev) + Docker network (prod Fase 1)"
owner: "gabrielhamu"
created: 2026-04-10
updated: 2026-04-10
target: ""
outcome: ""
arch:
  modules: [M1, M2, M3, M11]
  contexts: [channel]
  containers: [prosauai-api, redis, evolution-api]
---

# 003 — Multi-Tenant Foundation

## Escopo Arquitetural

| Camada | Blocos | Viewer |
|--------|--------|--------|
| Modulos | M1 (Recepcao), M2 (Debounce), M3 (Smart Router — interface apenas), M11 (Entrega) | [Containers (Interactive)](../../engineering/containers/) |
| Contextos | Channel | [Context Map](../../engineering/context-map/) |
| Containers | prosauai-api, redis, evolution-api | [Containers (Interactive)](../../engineering/containers/) |

## Problema

O epic 001 entregou o webhook + router + debounce funcionais contra uma fixture sintetica, mas validacao empirica com a Evolution API v2.3.0 real (capturas feitas em 2026-04-10) revelou **3 bloqueios totais** que impedem qualquer outro epic de rodar em producao:

1. **HMAC imaginario (100% de rejeicao).** O codigo valida `x-webhook-signature` HMAC-SHA256 no webhook. **A Evolution nunca assinou webhooks** (v1.x e v2.x confirmados por source-dive em `webhook.controller.ts` — zero chamadas a `createHmac`; issue upstream `EvolutionAPI/evolution-api#102` aberta em 2023 e **fechada sem implementacao em 2025**). Consequencia: 100% dos webhooks reais sao rejeitados com HTTP 401. O servico nao funciona com Evolution real.

2. **Parser divergente em 12 pontos criticos (50% de silenciamento).** O parser de `formatter.py` assume `messageType` com valores curtos (`image`, `video`, `audio`, `sticker`) — **nao existem**. A realidade e `imageMessage`, `videoMessage`, `audioMessage`, `stickerMessage`, `reactionMessage`, `pollCreationMessageV3`, `eventMessage`, `contactMessage`, `locationMessage`, `liveLocationMessage`, `documentMessage`, `conversation`. Resultado: 16 de 32 mensagens capturadas (50%) caem em "unknown type" com `text=""` silenciosamente. Alem disso: (a) `remoteJid` pode vir como `<15-digit>@lid` (formato Linked ID) com telefone real em `key.senderPn`; (b) `mentionedJid` vive em `data.contextInfo` (top-level), nao em `message.extendedTextMessage.contextInfo`; (c) `groups.upsert` traz `data` como **lista**, sem `key`; (d) `group-participants.update` traz `data` como dict **sem `key`**, com `{action, author, participants[]}`; (e) `quotedMessage` em `data.contextInfo.quotedMessage`; (f) campos Chatwoot/deviceListMetadata/base64 precisam ser ignorados silenciosamente.

3. **Arquitetura single-tenant nao acomoda o end-state.** [Vision](../../business/vision/) deixa explicito que ProsaUAI e uma plataforma **multi-tenant** — cada cliente tem sua propria instancia Evolution, seu webhook secret, sua config. Manter `Settings` globais (`evolution_api_url`, `evolution_api_key`, `mention_phone`) como esta hoje significa um refactor doloroso depois: `config.py`, `webhooks.py`, `dependencies.py`, `debounce.py`, `main.py` + todos os testes. Refactor de multi-tenancy posterior e historicamente uma das mudancas mais dolorosas em codebases single-tenant.

Este epic e **pre-requisito duro** para 004-router-mece, 005-conversation-core e todos os demais. Sem ele, nada do que vem depois roda em producao — nem no dev local, ja que o webhook hoje rejeita 100% das mensagens reais. O plano completo esta em [docs/prosauai/IMPLEMENTATION_PLAN.md](../../../../docs/prosauai/IMPLEMENTATION_PLAN.md) (2644 linhas, aprovado 2026-04-10).

## Valor de Negocio

- [ ] Servico recebe e processa 100% dos webhooks reais da Evolution v2.3.0 (hoje rejeita 100%)
- [ ] 26 fixtures capturadas de payloads reais passam em CI — fim da divergencia fixture-vs-producao
- [ ] Codigo ja e multi-tenant — refatoracao posterior zero para suportar N clientes
- [ ] 2 tenants reais (Ariel + ResenhAI) operando em paralelo desde o dia 1 — valida isolamento cross-tenant empiricamente
- [ ] Idempotencia neutraliza os retries agressivos da Evolution (ate 10 tentativas com backoff) — sem echo duplicado, sem efeitos colaterais duplicados
- [ ] Deploy nunca expoe porta publica (Tailscale no dev, Docker network na prod Fase 1) — superficie de ataque zero ate Fase 2
- [ ] Desbloqueia 004-router-mece, 005-conversation-core e todos os MVP epics subsequentes

## Solucao

Arquitetura multi-tenant **estrutural** com operacao single-tenant-no-VPS — Alternativa D do plano (§5.4). Codigo suporta N tenants, deploy opera com 2 (Ariel + ResenhAI internos). Admin API, Postgres e billing ficam para Fase 2/3.

**Modelo conceitual:**

```
webhook POST → TenantResolver(instance_name) → Auth(X-Webhook-Secret) → Idempotency(Redis SETNX) → Parse → Route → Debounce(keys per tenant) → EvolutionProvider(tenant credentials)
```

**Principais blocos:**

1. **`Tenant` dataclass (frozen, slots)** — config imutavel por tenant: `id`, `instance_name`, `evolution_api_url`, `evolution_api_key`, `webhook_secret`, `mention_phone`, `mention_lid_opaque`, `mention_keywords`, `enabled`. Dois campos **novos** vs epic 001: `mention_lid_opaque` (15-digit opaco do formato @lid) e `webhook_secret` (substitui o global).

2. **`TenantStore` file-backed** — carrega `config/tenants.yaml` no startup via lifespan, interpola `${ENV_VAR}` para secrets, indexa por `id` e por `instance_name`. Interface `find_by_instance()` + `get()` - migracao futura para DB (Fase 3) troca apenas o loader.

3. **`resolve_tenant_and_authenticate()`** — dependency FastAPI que: (a) resolve tenant por `instance_name` no path (404 se desconhecido), (b) valida `X-Webhook-Secret` em constant-time contra `tenant.webhook_secret` (401 se invalido), (c) retorna `(tenant, raw_body)` para o handler — evita re-ler o stream.

4. **`check_and_mark_seen(redis, tenant_id, message_id, ttl=86400)`** — Redis `SET NX EX` atomic. Key format `seen:{tenant_id}:{message_id}` com TTL 24h (cobre janela de retries da Evolution). Duplicate → `200 OK {status: "duplicate"}` sem processar.

5. **Parser Evolution v2.3.0 reescrito** — 12 correcoes empiricamente validadas contra 26 fixtures reais em `tests/fixtures/captured/`:
   - `_KNOWN_MESSAGE_TYPES` com nomes reais (`imageMessage`, `videoMessage`, `audioMessage`, `documentMessage`, `stickerMessage`, `locationMessage`, `liveLocationMessage`, `contactMessage`, `reactionMessage`, `pollCreationMessageV3`, `eventMessage`, `extendedTextMessage`, `conversation`)
   - Sender multi-formato: `@lid+senderPn` → usa `key.senderPn`; `@s.whatsapp.net+senderLid` → usa `remoteJid`; grupo `@g.us` → `key.participant`
   - Branches novas para `event=groups.upsert` (data=lista) e `event=group-participants.update` (data=dict sem key)
   - `mentionedJid` lido de `data.contextInfo` (top-level), funciona para `conversation` e `extendedTextMessage`
   - `quotedMessage` extraido → `is_reply` + `quoted_message_id`
   - `reactionMessage` → rota `IGNORE` com `reason="reaction"` (ambient signal, nao echo)
   - Campos irrelevantes ignorados silenciosamente: `messageContextInfo`, `chatwoot*`, `deviceListMetadata`, `data.message.base64`

6. **`ParsedMessage` schema expandido 12→22 campos** — compound sender identity (`sender_phone`, `sender_lid_opaque`), campos novos para 3 tipos de evento (messages/groups.upsert/group-participants.update), mentions como `mentioned_jids` (raw strings `<lid>@lid` ou `<phone>@s.whatsapp.net`), reply + reaction fields. Ver [data-model.md] gerado no speckit.plan.

7. **Debounce keys prefixadas por tenant** — `buf:{tenant_id}:{sender_key}:{ctx}` e `tmr:{tenant_id}:{sender_key}:{ctx}` onde `sender_key = sender_lid_opaque or sender_phone`. `parse_expired_key()` extrai `(tenant_id, sender_key, group_id)`. Evita colisao cross-tenant quando 2 instancias tem phone numbers coincidentes.

8. **`_flush_echo` resolve tenant por chave** — callback do debounce recebe `(tenant_id, sender_key, group_id, text)`, resolve `tenant_id → Tenant` via `app.state.tenant_store`, cria `EvolutionProvider(base_url=tenant.evolution_api_url, api_key=tenant.evolution_api_key)`, envia echo. Remove o closure global do epic 001.

9. **Router com signature minima `route_message(msg, tenant)`** — mudanca **cirurgica** de interface: troca `settings.mention_phone` por `tenant.mention_phone`, adiciona 3-strategy mention detection (@lid opaque → phone JID → keyword substring). **NAO mexe no enum `MessageRoute` nem no `if/elif` interno** — refactor completo fica para 004-router-mece (rip-and-replace). Zero conflito de merge entre 003 e 004.

10. **Deploy isolado por rede** — `docker-compose.yml` base sem `ports:`, `docker-compose.override.yml` (gitignored) bind Tailscale no dev, producao Fase 1 usa Docker network compartilhada com Evolution na mesma VPS.

### Interfaces / Contratos

```python
# prosauai/core/tenant.py
@dataclass(frozen=True, slots=True)
class Tenant:
    id: str
    instance_name: str
    evolution_api_url: str
    evolution_api_key: str
    webhook_secret: str
    mention_phone: str              # E.164 — legacy group mention + fallback
    mention_lid_opaque: str         # 15-digit opaco — modern group mention (primary)
    mention_keywords: tuple[str, ...] = field(default=())
    enabled: bool = True


# prosauai/core/tenant_store.py
class TenantStore:
    def __init__(self, tenants: list[Tenant]): ...
    @classmethod
    def load_from_file(cls, path: Path) -> TenantStore:
        """Load tenants.yaml, interpolating ${ENV_VAR} references."""
    def find_by_instance(self, instance_name: str) -> Tenant | None: ...
    def get(self, tenant_id: str) -> Tenant | None: ...


# prosauai/api/dependencies.py
async def resolve_tenant_and_authenticate(
    request: Request,
    instance_name: str,
) -> tuple[Tenant, bytes]:
    """Resolve tenant from path + validate X-Webhook-Secret (constant-time)."""


# prosauai/core/idempotency.py
async def check_and_mark_seen(
    redis: Redis,
    tenant_id: str,
    message_id: str,
    ttl_seconds: int = 86400,
) -> bool:
    """True se primeiro sighting; False se duplicate. Redis SETNX atomic."""


# prosauai/core/formatter.py — ParsedMessage expandido
EventType = Literal["messages.upsert", "groups.upsert", "group-participants.update"]
MediaType = Literal[
    "image", "video", "audio", "document", "sticker",
    "location", "live_location", "contact",
    "poll", "event", "reaction",
]

class ParsedMessage(BaseModel):
    # Tenant context
    tenant_id: str
    # Event metadata
    event: EventType
    instance_name: str
    instance_id: str | None = None
    message_id: str
    timestamp: datetime
    # Sender (compound)
    sender_phone: str | None = None
    sender_lid_opaque: str | None = None
    sender_name: str | None = None
    from_me: bool = False
    # Conversation context
    is_group: bool = False
    group_id: str | None = None
    # Content
    text: str = ""
    media_type: MediaType | None = None
    media_url: str | None = None
    media_mimetype: str | None = None
    media_is_ptt: bool = False
    media_duration_seconds: int | None = None
    media_has_base64_inline: bool = False
    # Mentions
    mentioned_jids: list[str] = Field(default_factory=list)
    # Reply
    is_reply: bool = False
    quoted_message_id: str | None = None
    # Reaction
    reaction_emoji: str | None = None
    reaction_target_id: str | None = None
    # Group event
    is_group_event: bool = False
    group_subject: str | None = None
    group_participants_count: int | None = None
    group_event_action: str | None = None
    group_event_participants: list[str] = Field(default_factory=list)
    group_event_author_lid: str | None = None

    @property
    def sender_key(self) -> str:
        """Stable identity for debounce/idempotency. @lid > phone > 'unknown'."""
        return self.sender_lid_opaque or self.sender_phone or "unknown"


# prosauai/core/router.py — minimal interface change
def route_message(msg: ParsedMessage, tenant: Tenant) -> RouteResult:
    """Interface apenas: troca settings por tenant, mantem logica if/elif.
    Refactor completo (classify + RoutingEngine) e problema do 004-router-mece.
    """
```

### Schema YAML de tenants

```yaml
# config/tenants.yaml (gitignored; template em config/tenants.example.yaml)
tenants:
  - id: pace-internal
    instance_name: Ariel
    evolution_api_url: https://evolutionapi.pace-ia.com
    evolution_api_key: ${PACE_EVOLUTION_API_KEY}
    webhook_secret: ${PACE_WEBHOOK_SECRET}
    mention_phone: "5511910375690"
    mention_lid_opaque: "146102623948863"    # descoberto via /webhook/find + mention real
    mention_keywords:
      - "@ariel"
    enabled: true

  - id: resenha-internal
    instance_name: ResenhAI
    evolution_api_url: https://evolutionapi.pace-ia.com
    evolution_api_key: ${RESENHA_EVOLUTION_API_KEY}
    webhook_secret: ${RESENHA_WEBHOOK_SECRET}
    mention_phone: "5511970972463"
    mention_lid_opaque: "..."
    mention_keywords:
      - "@resenha"
    enabled: true
```

### Scope

**Dentro (Fase 1 do IMPLEMENTATION_PLAN.md):**

- `Tenant` dataclass + `TenantStore` YAML loader com interpolacao `${ENV_VAR}`
- `resolve_tenant_and_authenticate()` dependency (remove HMAC, adiciona X-Webhook-Secret)
- `check_and_mark_seen()` helper de idempotencia Redis SETNX
- `Settings` refatorado — remove campos tenant-specific, fica so global (host/port/redis/debounce/tenants_file)
- `formatter.py` reescrito: 12 correcoes do parser contra fixtures reais
- `ParsedMessage` schema expandido (12 → 22 campos) + `sender_key` property
- `router.py` **interface minima** (`settings` → `tenant`), 3-strategy mention detection (`mention_lid_opaque` → `mention_phone` → keywords)
- `debounce.py` com keys `buf:/tmr:{tenant_id}:{sender_key}:{ctx}` + `parse_expired_key` atualizado
- `webhooks.py` com fluxo completo (resolver → auth → idempotency → parse → route → debounce)
- `main.py` lifespan carrega `TenantStore`, `_make_flush_callback(app)` resolve tenant por chave
- `docker-compose.yml` sem `ports:`, volume `./config/tenants.yaml:/app/config/tenants.yaml:ro`
- `docker-compose.override.example.yml` template gitignored com bind Tailscale
- Porta 8050 (substituindo 8040 que conflita com madruga-ai daemon)
- **Test suite fixture-driven**: `test_captured_fixtures.py` parametriza 26 pares `tests/fixtures/captured/*.input.json` + `*.expected.yaml`; deleta `tests/fixtures/evolution_payloads.json` sintetica
- Rewrite de `test_hmac.py` → `test_auth.py`; `test_router.py`, `test_debounce.py`, `test_formatter.py`, `test_webhook.py` atualizados para nova interface
- README + `.env.example` + `tenants.example.yaml` documentados (inclui workflow de discovery do `mention_lid_opaque` para novo tenant)

**Fora (explicitamente):**

- Admin API (`POST/GET/DELETE /admin/tenants`) — **Fase 2** ([ADR-022](../../decisions/ADR-022-admin-api.md))
- Caddy reverse proxy + TLS publico — **Fase 2** ([ADR-021](../../decisions/ADR-021-caddy-edge-proxy.md))
- Rate limiting per-tenant — **Fase 2** (ja existe ADR-015, acionavel na Fase 2)
- Migracao `TenantStore` YAML → Postgres — **Fase 3** ([ADR-023](../../decisions/ADR-023-tenant-store-postgres-migration.md)); trigger: >=5 tenants reais
- Billing/usage tracking — **Fase 3** (existe ADR-012, acionavel na Fase 3)
- Circuit breaker per-tenant — **Fase 3** (existe ADR-015, parcial)
- Refactor completo do router (`classify()` + `RoutingEngine` + discriminated union `Decision`) — **004-router-mece** (rip-and-replace)
- Supabase / RLS / tabelas persistentes — **005-conversation-core** e adiante
- mTLS, JWT `jwt_key` da Evolution — rejeitados explicitamente no §9.3 do plano
- HMAC signing fallback — removido completo, zero compat layer (rip-and-replace §4.1)

## Rabbit Holes

- **Mention detection em 3 strategies e ordem sensivel.** Primary `mention_lid_opaque` (modern groups), fallback `mention_phone` (legacy), last resort keywords substring. Fixture `resenhai_msg_group_text_mention_jid` valida que strategy 1 funciona; sem ela, 100% dos mentions em grupo modernos falhariam silenciosamente. Testar os 3 paths separadamente.

- **Descoberta do `mention_lid_opaque` para novo tenant.** Nao e inferivel do `mention_phone`. Workflow: (1) configurar webhook temporario apontando para capture tool; (2) pedir pra alguem mencionar o bot em um grupo; (3) ler `data.contextInfo.mentionedJid` no capture; (4) extrair o `<15-digit>@lid`; (5) guardar em `tenants.yaml`. Documentar em README.

- **Cross-tenant key collision em Redis.** Sem prefixo de tenant, 2 tenants com phone numbers coincidentes (improvavel mas possivel) colidiriam nas chaves `buf:/tmr:/seen:`. Prefixo elimina — testar com 2 tenants + mesmo phone sintetico.

- **Evolution envia webhook com retries agressivos (ate 10x).** Idempotencia tem que cobrir a janela completa: 24h TTL e folga confortavel. Sem idempotencia, qualquer efeito colateral (futuras persistencias em DB, cobranca, envio a LLM) duplica.

- **`groups.upsert` dispara em **qualquer** mudanca do grupo** (nome, participantes, settings). `data` e lista com 1+ group objects. Parser precisa iterar, nao assumir `data[0]`. Fixtures `resenhai_groups_upsert_initial_2p` e `ariel_groups_upsert_after_add_3p` cobrem 2 casos reais.

- **`group-participants.update` nao tem `data.key`.** O parser atual assume que todo evento tem `data.key.id`. Branch nova precisa sintetizar `message_id` a partir de `{id}-{timestamp}` (ou similar). Fixture `resenhai_group_participants_update_add` valida.

- **`ParsedMessage` de evento de grupo vs mensagem e o **mesmo** schema.** Campos opcionais marcam qual tipo de evento e. Alternativa descartada: 3 schemas distintos (`MessageEvent`, `GroupsUpsertEvent`, `GroupParticipantsUpdateEvent`) — demais cerimonia para ganho marginal. Um schema com `event: EventType` discriminator cobre tudo.

- **`reactionMessage` como `IGNORE` com reason=reaction.** Alternativa descartada: rota dedicada `REACTION`. Razao: reactions sao ambient signal, nao pedido de acao — echoar e UX estranho. Se no futuro quisermos notificar o agente quando reagem, promovemos. Extrai `reaction_emoji` e `reaction_target_id` no `ParsedMessage` mesmo assim (logging + futuro).

- **Loader YAML com interpolacao `${ENV_VAR}`.** Alternativa descartada: secrets no YAML commitavel. Razao obvia: vazamento. Alternativa considerada: carregar secrets do Infisical — rejeitada **nesta fase** porque Infisical ainda nao esta deployado (ADR-017 planejado), envs sao suficientes para 2 tenants internos.

- **Test loader ignora chaves nao declaradas.** Fixtures `*.expected.yaml` podem ter `_note` ou chaves informacionais. Loader compara apenas os campos declarados no schema canonico (§8.0.2 do plano). Partial assertion — fixtures minimas sao baratas.

- **Porta 8050 vs 8040.** 8040 conflita com `madruga-ai` daemon. 8050 continua padrao `80X0` do Gabriel sem colidir. Afeta: `.env`, `docker-compose.yml`, `Dockerfile` EXPOSE, `config.py` default, `conftest.py`, README, webhook URL reapontado na Evolution.

- **Observability (epic 002) precisa de `tenant_id` nos spans.** Quando 002 shipar primeiro, spans nascem single-tenant. Ao promover 003 depois, delta review adiciona `tenant_id` como span attribute via `gen_ai.*` ou `prosauai.*` conventions. Mitigacao trivial (~5 linhas no `configure_observability`), mas precisa estar na lista de revisao do epic-context.

- **004-router-mece ja drafted assume que 003 entrega `route_message(msg, tenant)`.** Task T7 deste epic entrega exatamente essa assinatura minima. 004 faz rip-and-replace do corpo. Se T7 mexer demais, 004 vai ter merge hell. Regra: **T7 e cirurgica — 10-20 linhas no maximo.**

## Tasks

- [ ] **T0** — Criar branch `epic/prosauai/003-multi-tenant-foundation` a partir de main (gate de promocao)
- [ ] **T1** — `prosauai/core/tenant.py`: `Tenant` dataclass frozen/slots + docstring (mention strategy)
- [ ] **T2** — `prosauai/core/tenant_store.py`: `TenantStore` + `load_from_file()` com interpolacao `${ENV_VAR}` (+ `pyyaml` no pyproject)
- [ ] **T3** — `config/tenants.example.yaml` template + `config/tenants.yaml` gitignored (2 tenants: Ariel + ResenhAI)
- [ ] **T4** — `prosauai/config.py`: remove campos tenant-specific; deixa `host/port/debug/redis_url/debounce_*/tenants_file/idempotency_ttl_seconds`
- [ ] **T5** — `prosauai/core/idempotency.py`: `check_and_mark_seen()` com Redis `SET NX EX`
- [ ] **T6** — `prosauai/api/dependencies.py`: remove `verify_webhook_signature`, adiciona `resolve_tenant_and_authenticate()` (404 unknown / 401 wrong secret / constant-time compare)
- [ ] **T6b** — `formatter.py`: `_KNOWN_MESSAGE_TYPES` com nomes reais (`imageMessage`/`videoMessage`/`audioMessage`/`documentMessage`/`stickerMessage`/`locationMessage`/`liveLocationMessage`/`contactMessage`/`reactionMessage`/`pollCreationMessageV3`/`eventMessage`/`extendedTextMessage`/`conversation`)
- [ ] **T6c** — `formatter.py`: resolucao de sender multi-formato — `@lid+senderPn` usa `key.senderPn`; `@s.whatsapp.net+senderLid` usa `remoteJid`; grupo `@g.us` usa `key.participant`. `ParsedMessage` expoe `sender_phone` + `sender_lid_opaque`
- [ ] **T6d** — `formatter.py`: branch `event=groups.upsert` (data=lista, sem key) → extrai `group_id`, `subject`, `participants_count`
- [ ] **T6e** — `formatter.py`: branch `event=group-participants.update` (data=dict sem key) → extrai `action`, `author`, `participants[]`; sintetiza `message_id`
- [ ] **T6f** — `formatter.py`: `mentionedJid` lido de `data.contextInfo` (top-level), funciona para `conversation` + `extendedTextMessage`
- [ ] **T6g** — `formatter.py`: extrai `quotedMessage` de `data.contextInfo.quotedMessage` → `is_reply` + `quoted_message_id`
- [ ] **T6h** — `tenant.py` + `router.py`: adiciona `mention_lid_opaque` ao schema; `_is_bot_mentioned()` compara 3 strategies (lid → phone → keywords)
- [ ] **T6i** — `formatter.py`: ignora silenciosamente `messageContextInfo`/`chatwoot*`/`deviceListMetadata`/`data.message.base64`/`status`/`source` (loga `instanceId` como metadado)
- [ ] **T6j** — `router.py`: `reactionMessage` → `IGNORE` com `reason="reaction"`; extrai `reaction_emoji` + `reaction_target_id` no `ParsedMessage`
- [ ] **T7** — `router.py`: assinatura `route_message(msg, tenant)` — **apenas interface**, logica if/elif intocada (rip-and-replace e do 004-router-mece)
- [ ] **T8** — `api/webhooks.py`: fluxo completo (resolver → auth → parse → idempotency → route → debounce)
- [ ] **T9** — `debounce.py`: keys `buf:/tmr:{tenant_id}:{sender_key}:{ctx}`; `parse_expired_key()` retorna `(tenant_id, sender_key, group_id)`
- [ ] **T10** — `main.py`: lifespan carrega `TenantStore.load_from_file()` em `app.state.tenant_store`
- [ ] **T11** — `main.py`: `_make_flush_callback(app)` resolve tenant por chave, cria `EvolutionProvider` per-tenant, envia echo
- [ ] **T12** — `docker-compose.yml`: remove `ports:`, adiciona volume `./config/tenants.yaml:/app/config/tenants.yaml:ro`
- [ ] **T13** — `docker-compose.override.example.yml` template (gitignored real); bind Tailscale no dev
- [ ] **T14** — `.env.example` + `.env` (gitignored) + `.gitignore` atualizado
- [ ] **T15** — README atualizado: dev (Tailscale), prod Fase 1 (Docker network), onboarding de novo tenant (inclui descoberta do `mention_lid_opaque`), how-to adicionar fixture
- [ ] **T16** — `tests/integration/test_captured_fixtures.py` parametrico — carrega 26 pares `tests/fixtures/captured/*.{input.json,expected.yaml}`, roda `parse_evolution_message` + `route_message`, compara campos declarados
- [ ] **T17** — Deletar `tests/fixtures/evolution_payloads.json` sintetica + todos os testes que dependem dela (apos T6b-T6j + T16 passarem)
- [ ] **T18** — Reescrita de `test_hmac.py` → `test_auth.py` (X-Webhook-Secret + 404 unknown + 401 wrong + constant-time)
- [ ] **T19** — Atualizar `test_router.py` (Tenant em vez de Settings; 3-strategy mention), `test_debounce.py` (novas keys), `test_webhook.py` (cross-tenant isolation + idempotency)
- [ ] **T20** — `tests/conftest.py`: fixtures `sample_tenant`, `tenant_store`, `load_captured_fixture_pair(name)` helper; remove fixtures de `webhook_secret`
- [ ] **T21** — End-to-end real: Evolution envia webhook para `http://<host>:8050/webhook/whatsapp/Ariel` → processa + envia echo (+ validacao manual com ResenhAI)

## Criterios de Sucesso

**Auth + infra:**

- [ ] `docker compose up` sobe sem erro com `.env` + `tenants.yaml` minimos
- [ ] Request sem header `X-Webhook-Secret` → 401
- [ ] Request com `instance_name` desconhecido → 404
- [ ] Request com secret errado → 401
- [ ] Porta 8050 **nao** exposta em `0.0.0.0` em producao (apenas Docker network ou Tailscale em dev)

**Fixture-driven parser correctness (26 pares, payloads reais):**

- [ ] Todas as 26 fixtures em `tests/fixtures/captured/*.input.json` parseadas sem excecao
- [ ] Campos declarados em cada `.expected.yaml` batem com o `ParsedMessage` gerado
- [ ] Rota declarada em cada `.expected.yaml` bate com `route_message()`
- [ ] **16 de 16 midias** reconhecidas por `messageType` real (imageMessage, videoMessage, audioMessage, etc.)
- [ ] `mentionedJid` em `data.contextInfo` lido corretamente — fixture `resenhai_msg_group_text_mention_jid` classifica como `group_respond`
- [ ] `@lid + senderPn`: `ariel_msg_individual_lid_text_simple` extrai `sender_phone` + `sender_lid_opaque`
- [ ] `@s.whatsapp.net + senderLid`: `ariel_msg_individual_legacy_text` extrai ambos
- [ ] Grupo com `participant=@lid`: `resenhai_msg_group_text_no_mention` tem `sender_lid_opaque`, `sender_phone=None`, rota `group_save`
- [ ] `groups.upsert` com data=lista: `resenhai_groups_upsert_initial_2p`, `ariel_groups_upsert_after_add_3p` parsed sem crash, rota `group_event`
- [ ] `group-participants.update` sem key: `resenhai_group_participants_update_add` parsed sem crash, `action=add`, rota `group_event`
- [ ] Reply com quotedMessage: `ariel_msg_individual_lid_text_reply` tem `is_reply=True`, `quoted_message_id`
- [ ] `fromMe: true` ignorado: todas as 5 fixtures `*_fromme` roteadas como `ignore` com reason `from_me`
- [ ] Reaction: `ariel_msg_individual_lid_reaction` extrai `reaction_emoji="❤️"`, rota `ignore` reason=`reaction`

**Idempotencia + debounce:**

- [ ] Mesmo `message_id` duas vezes (mesmo tenant) → segundo request `status=duplicate`, sem processar
- [ ] Mesmo `message_id` em tenants diferentes → ambos processam (chave Redis prefixada)
- [ ] Debounce key format: `buf:{tenant_id}:{sender_key}:{ctx}` onde `sender_key = sender_lid_opaque or sender_phone`

**Cross-tenant validation:**

- [ ] Com 2 tenants configurados (Ariel + ResenhAI), mensagem pro Ariel **nao** e recebida pelo ResenhAI
- [ ] `groups.upsert` dispara webhooks para os 2 tenants — cada um processa independentemente

**End-to-end real:**

- [ ] Evolution real envia webhook para `http://<host>:8050/webhook/whatsapp/Ariel` com `X-Webhook-Secret` correto → processa com sucesso, envia echo
- [ ] Mesma validacao para ResenhAI

**Interface com 004-router-mece:**

- [ ] `grep -c "settings\." prosauai/core/router.py` = 0 (zero referencias a `Settings` no router)
- [ ] T7 entrega diff <= 30 linhas em `router.py` (excluindo `_is_bot_mentioned`)
- [ ] `route_message(msg, tenant)` assinatura estavel — nao muda ate 004 comecar

**Documentacao:**

- [ ] README documenta onboarding de novo tenant (copiar template, editar YAML, gerar secret, discovery do `mention_lid_opaque`, configurar webhook na Evolution)
- [ ] `tests/fixtures/captured/README.md` mantido como source-of-truth da matriz MECE
- [ ] `decisions.md` com >=15 entries referenciando arquitetura

**Todos:**

- [ ] Todos os testes unitarios passam
- [ ] Todos os testes de integracao passam
- [ ] `test_captured_fixtures.py` passa (26 casos parametricos)
- [ ] Ruff + mypy strict sem erros em `prosauai/core/tenant.py`, `tenant_store.py`, `idempotency.py`, `formatter.py`, `router.py`

## Decisoes

| Data | Decisao | Rationale |
|------|---------|-----------|
| 2026-04-10 | Alternativa D — multi-tenant estrutural, operando single-tenant-VPS | Refactor futuro zero; validado empiricamente com 2 tenants reais desde dia 1; evita dor de refactor posterior documentada no §5.2 |
| 2026-04-10 | Remove HMAC completo (rip-and-replace, zero compat) | Evolution nunca assinou webhooks; manter codigo morto e deceptive; issue upstream #102 fechada sem implementacao |
| 2026-04-10 | Auth via `X-Webhook-Secret` estatico per-tenant | Unico mecanismo que a Evolution suporta de verdade; validado empiricamente em 2026-04-10 (§4.5); constant-time compare |
| 2026-04-10 | Idempotencia por `(tenant_id, message_id)` via Redis SETNX 24h | `message_id` e unico garantido; hash do body furaria dedupe por timestamps de retry; TTL cobre janela completa de retries |
| 2026-04-10 | `TenantStore` file-backed YAML com interpolacao `${ENV_VAR}` | Commitavel como template; secrets em env; migracao para DB (Fase 3) troca apenas o loader; ADR-023 documenta trigger |
| 2026-04-10 | `ParsedMessage` expandido 12 → 22 campos, schema unico para 3 eventos | Discriminator `event: EventType` cobre `messages.upsert`/`groups.upsert`/`group-participants.update` sem explodir em 3 classes |
| 2026-04-10 | `sender_key = sender_lid_opaque or sender_phone` | @lid e estavel entre individual/group; fallback para phone em legacy; unica chave para debounce+idempotency keys |
| 2026-04-10 | 3-strategy mention detection: @lid opaque → phone JID → keyword substring | Strategy 1 cobre 100% dos mentions em grupos modernos; strategy 2 legacy; strategy 3 texto livre ("@ariel") |
| 2026-04-10 | Parser reescrito contra 26 fixtures reais; fixture sintetica deletada | 16/32 mensagens reais caem em "unknown type" com parser atual; fixtures reais sao single source of truth |
| 2026-04-10 | Debounce keys prefixadas `buf:/tmr:{tenant_id}:{sender_key}:{ctx}` | Evita colisao cross-tenant; facilita debug via `redis-cli keys 'buf:pace-internal:*'` |
| 2026-04-10 | `_flush_echo` resolve tenant por chave, sem closure global | Credenciais sao per-tenant; closure global capturava `app.state.settings` que nao existe mais |
| 2026-04-10 | Router T7 = interface minima (`settings` → `tenant`), NAO mexe no if/elif | Refactor completo e do 004-router-mece (rip-and-replace); T7 cirurgica evita merge hell |
| 2026-04-10 | Deploy: `docker-compose.yml` sem `ports:`, override.yml bind Tailscale no dev | Superficie de ataque zero ate Fase 2; nenhuma porta publica em dev nem em prod Fase 1 |
| 2026-04-10 | `reactionMessage` → `IGNORE` com `reason="reaction"` (nao rota dedicada) | Reactions sao ambient signal; extrai `reaction_emoji` pra log/futuro, nao echoar; promovivel depois se necessario |
| 2026-04-10 | Porta 8050 (nao 8040, nao 8080) | 8040 colide com madruga-ai daemon; 8080 colide com Evolution Manager; 8050 continua padrao 80X0 sem conflito |
| 2026-04-10 | Sequencia 003 + 004 back-to-back, prod deploy apos 004 | Both epics partem de main separadamente; prod hold entre merges; evita cascade rebase risk |
| 2026-04-10 | Fase 2 (Caddy + Admin API + rate limit) e Fase 3 (Postgres + billing + circuit breaker) documentados AGORA em business/engineering + ADRs | Pedido explicito do usuario; evita que end-state vire surpresa futura; ADR-021/022/023 novos |

## Captured Decisions

| # | Area | Decision | Architectural Reference |
|---|------|---------|----------------------|
| 1 | Arquitetura | Alternativa D — multi-tenant estrutural, operando single-tenant-VPS | blueprint §4.5 Multi-Tenancy, vision §1 (multi-tenant end-state) |
| 2 | Auth | Rip-and-replace HMAC; `X-Webhook-Secret` estatico per-tenant em constant-time | blueprint §4.7 Failure Modes (webhook auth), ADR-017 (secrets) |
| 3 | Idempotencia | Redis SETNX 24h keyed por `(tenant_id, message_id)` | blueprint §4.6 channel pipeline, ADR-003 Redis Streams (pattern) |
| 4 | Tenant model | `Tenant` frozen dataclass + `TenantStore` file-backed YAML com `${ENV_VAR}` interpolation | blueprint §4.5 Multi-Tenancy, ADR-011 (Pool+RLS end-state) |
| 5 | Data model | `ParsedMessage` expandido 12 → 22 campos com `sender_key` property | domain-model Channel BC (parsing), blueprint §1 (pydantic 2) |
| 6 | Mention detection | 3-strategy: `mention_lid_opaque` → `mention_phone` → keywords substring | domain-model Channel BC, vision §3 (group AI agent moat) |
| 7 | Parser | 12 correcoes empiricamente validadas contra 26 fixtures reais; fixture sintetica deletada | IMPLEMENTATION_PLAN.md §7.6.2.1, blueprint §5 (NFR testabilidade) |
| 8 | Debounce | Keys prefixadas por `tenant_id`: `buf:/tmr:{tenant_id}:{sender_key}:{ctx}` | blueprint §4.5 tenant isolation, ADR-003 |
| 9 | Flush callback | `_make_flush_callback(app)` resolve tenant por chave (parse_expired_key extrai tenant_id) | blueprint §4.6 sans-I/O pattern, domain-model Router aggregate |
| 10 | Router interface | T7 = mudanca minima de assinatura (`settings` → `tenant`); enum e if/elif intocados | Shape Up appetite (boundary com epic 004), ADR-006 (router as data) |
| 11 | Deploy topology | `docker-compose.yml` sem `ports:`; override.yml bind Tailscale no dev; Docker network isolada na prod Fase 1 | blueprint §2.2 (DevX), §4.7 (superficie de ataque minima) |
| 12 | Port decision | 8050 final (8040 colide com madruga-ai, 8080 colide com Evolution Manager) | blueprint §1 (infra topology) |
| 13 | Test strategy | Fixture-driven com 26 pares capturados; partial assertion loader; `_*` keys ignoradas | blueprint §5 NFR testabilidade, epic 001 lesson learned |
| 14 | Scope boundary | Fase 0+1 apenas; Fase 2 (Caddy, admin API) e Fase 3 (Postgres, billing) documentadas como ADR-021/022/023 para evitar surpresa futura | vision §1 end-state, user request 2026-04-10 |
| 15 | Epic sequencing | 003 + 004 back-to-back, ambos de main; prod hold entre merges; deploy unico apos 004 | Shape Up discipline, user request 2026-04-10 |
| 16 | Observability delta | 002 shipa primeiro single-tenant; promocao do 003 adiciona `tenant_id` como span attribute via delta review | blueprint §4.4 observability (epic 002 compatibility) |

## Resolved Gray Areas

**Onde validar o `X-Webhook-Secret`:** dependency FastAPI `resolve_tenant_and_authenticate` executada antes de qualquer parsing. Alternativa descartada: middleware global — teria que resolver tenant globalmente antes do routing, misturando auth com dispatch. Dependency isolada por endpoint e mais clean.

**Como interpolar `${ENV_VAR}` no YAML:** regex simples `\$\{(\w+)\}` no `load_from_file()`. Alternativa descartada: `envsubst` CLI no entrypoint do Docker — quebra loading programatico em testes. Alternativa descartada: lib como `pydantic-settings` YAML source — overkill para 2 tenants e acopla demais. Regex pragmatica e ~15 linhas.

**Como descobrir `mention_lid_opaque` para novo tenant:** apontar webhook temporario para capture tool (ou webhook.site), pedir que alguem mencione o bot em um grupo do tenant, ler `data.contextInfo.mentionedJid`, extrair o `<15-digit>@lid`. Documentar passo-a-passo no README. Nao e possivel inferir do `mention_phone`.

**Schema unico vs 3 schemas discriminados:** schema unico com `event: EventType` discriminator + campos opcionais. Alternativa descartada: `MessageEvent`, `GroupsUpsertEvent`, `GroupParticipantsUpdateEvent` como dataclasses distintas com discriminated union. Razao: debounce e router consomem os 3 igualmente (extraem `sender_key`, `group_id`, routam), separar so complica sem ganho.

**`reactionMessage`: rota dedicada ou `IGNORE`?:** `IGNORE` com `reason="reaction"`. Alternativa descartada: rota `REACTION` que echoa "gostei tambem!". UX estranho, complica enum sem beneficio. Extrai `reaction_emoji` mesmo assim — promovivel pra rota depois se aparecer caso de uso.

**Observability do 002 precisa de `tenant_id`:** sim, mas **delta review resolve**. 002 shipa single-tenant; ao promover 003 (apos 002), delta review adiciona `tenant_id` em `configure_observability()` via `gen_ai.tenant.id` attribute (ou convention `prosauai.tenant.id`). Mitigacao trivial, ~5 linhas. Alternativa descartada: inverter ordem (parar 002, shipar 003 primeiro) — perde 40% do progresso do 002.

**T7 no router: interface minima ou refactor completo?:** **minima**. Zero conflito com 004-router-mece (que faz rip-and-replace de `route_message`). Se T7 refatorar algo alem da assinatura e dos 3-strategies de mention, 004 vai ter merge hell. Regra dura: diff <= 30 linhas.

**Fase 2/3 nos docs agora vs depois:** agora, por pedido explicito. 3 ADRs novos (ADR-021 Caddy, ADR-022 Admin API, ADR-023 TenantStore Postgres migration) + secoes novas em `vision.md`, `process.md`, `blueprint.md`, `containers.md`. Razao: evita que end-state vire surpresa futura e cria ponto de referencia para discussoes do Fase 2/3 quando chegarem.

**Single PR ou split?:** **single PR**. Rip-and-replace da HMAC + parser + multi-tenant nao tem como dividir sem criar estados intermediarios quebrados (e.g., "HMAC removido mas auth novo ainda nao existe"). Epic 001 foi 1 PR grande e deu certo. 003 segue o mesmo padrao.

**Deploy Fase 1 em VPS Hostinger com Evolution na mesma rede:** sim. Tanto ProsauAI quanto a instancia Evolution ja rodam na VPS Pace. Criar Docker network compartilhada (`pace-net` external) e apontar webhook para `http://api:8050/webhook/whatsapp/<instance>` — resolve por DNS interno do Docker, trafego nao sai do host. Porta 8050 nunca exposta.

## Applicable Constraints

| Constraint | Source | Impact |
|-----------|--------|--------|
| Multi-tenant desde dia 1 | vision §1 (end-state), business/solution-overview.md | Tenant como abstracao estrutural; refactor posterior e rejeitado (§5.2 alternativa B) |
| Secrets nunca em codigo | ADR-017 (secrets management) | Webhook secrets + Evolution API keys via `${ENV_VAR}` interpolation no tenants.yaml |
| pydantic 2 stack | ADR-001, blueprint §1 | `ParsedMessage` como `BaseModel`; `Tenant` como `@dataclass(frozen, slots)` por performance + imutabilidade |
| Sans-I/O no core | blueprint §4.6 | `classify`/`parse_evolution_message` puros; I/O em camada externa |
| Observabilidade structlog | blueprint §4.4 | `tenant_id` + `instance_name` + `sender_key` em todo log estruturado |
| Ruff strict + mypy strict | blueprint §5 | `Tenant` frozen dataclass + `Literal` enums forcam tipagem exata |
| Test-driven com fixtures reais | blueprint §5 NFR testabilidade, epic 001 lesson learned | 26 fixtures capturadas substituem fixture sintetica; CI roda todos via `test_captured_fixtures.py` |
| HMAC removido (rip-and-replace) | §4.1 do plano, Evolution #102 fechada | Zero compat layer; testes `test_hmac.py` deletados / reescritos como `test_auth.py` |
| Porta nao exposta na internet | §7.2/§7.3 do plano, blueprint §4.7 | `docker-compose.yml` sem `ports:`; override.yml so pra dev via Tailscale |
| Deploy Fase 1 em Docker network privada | §7.2 do plano | `pace-net` external compartilhada com Evolution; trafego interno |
| `mention_lid_opaque` descoberto empiricamente por tenant | §7.6.2.1 Descoberta #4 | README documenta workflow; nao e inferivel de `mention_phone` |
| 004-router-mece depende de `route_message(msg, tenant)` estavel | 004 pitch T7 reference | T7 e cirurgica; diff <=30 linhas; enum e if/elif intocados |
| 002-observability depende de `tenant_id` nos spans | blueprint §4.4, epic 002 research | Delta review no momento da promocao do 003 adiciona `tenant_id` em spans |

## Suggested Approach

1. **Scaffold tenant layer** — `tenant.py` + `tenant_store.py` + `tenants.example.yaml` + testes unitarios. Sem tocar em nada do epic 001.
2. **Idempotencia isolada** — `idempotency.py` + teste com Redis mock. Ainda sem integrar.
3. **Auth dependency** — reescreve `dependencies.py` com `resolve_tenant_and_authenticate`. Remove `verify_webhook_signature`. Reescreve teste `test_auth.py`.
4. **Parser correcoes (T6b-T6j)** — uma task por descoberta; testes sao paramétricos contra `tests/fixtures/captured/*.input.json`. Cada task adiciona fixtures no loader ate passar. Fixture sintetica deletada no final.
5. **Router T7 cirurgica** — apenas `settings` → `tenant` + 3-strategy mention. Diff <= 30 linhas. Teste `test_router.py` atualizado com `sample_tenant` fixture.
6. **Debounce keys com tenant_id** — `debounce.py` + `parse_expired_key`. Testes atualizados.
7. **Webhooks.py handler completo** — integra tudo: resolver → auth → parse → idempotency → route → debounce.
8. **Main.py lifespan** — carrega `TenantStore`; `_make_flush_callback(app)` resolve tenant por chave.
9. **Docker + deploy** — `docker-compose.yml` sem ports, `override.example.yml`, `.env.example`, porta 8050.
10. **End-to-end real** — apontar webhook real da Evolution para `http://<tailscale-ip>:8050/webhook/whatsapp/Ariel`, validar fluxo completo com mensagem real. Repetir com ResenhAI.
11. **Docs** — README com onboarding de novo tenant (inclui discovery de `mention_lid_opaque`); `decisions.md` append-only.

> **Proximo passo**: aguardar ship do epic 002 (Observability). Quando 002 mergar em main, rodar `/madruga:epic-context prosauai 003` (sem `--draft`) — delta review adiciona `tenant_id` nas conventions de span do `configure_observability()` (epic 002), cria branch `epic/prosauai/003-multi-tenant-foundation` a partir de main, e entra no ciclo L2 (`/speckit.specify` → ... → `/madruga:reconcile`).
