# Research — 003 Multi-Tenant Foundation

**Date**: 2026-04-10  
**Epic**: `epic/prosauai/003-multi-tenant-foundation`  
**Spec**: [spec.md](./spec.md)

## 1. Evolution API v2.3.0 — Webhook Authentication Reality

### Decision: `X-Webhook-Secret` header estático per-tenant

**Rationale**: Source dive no `webhook.controller.ts` da Evolution API (v1.x e v2.x) confirmou zero chamadas a `createHmac`. A issue upstream `EvolutionAPI/evolution-api#102` foi aberta em 2023 e **fechada sem implementação em 2025**. O único mecanismo de autenticação suportado é o header `X-Webhook-Secret` definido na configuração da instância. Validação empírica em 2026-04-10 com duas instâncias reais (Ariel e ResenhAI) confirmou que o header é enviado corretamente.

**Alternatives considered**:
1. **HMAC-SHA256 (status quo)** — Rejeitado. Evolution nunca implementou; 100% dos webhooks reais são rejeitados. Manter código morto é deceptive.
2. **mTLS entre Evolution e ProsaUAI** — Rejeitado. Complexidade operacional desproporcional para 2 tenants internos em Fase 1. Não suportado nativamente pela Evolution.
3. **JWT (`jwt_key` da Evolution)** — Rejeitado. Campo existe no config da Evolution mas não é usado para assinar webhooks; é para autenticação da API de management (direction inversa).
4. **`X-Webhook-Secret` estático per-tenant (escolhido)** — Simples, eficaz, único mecanismo que a Evolution realmente suporta. Constant-time compare via `hmac.compare_digest()` previne timing attacks.

**Sources**: Evolution API source code (`webhook.controller.ts`), issue #102, captura empírica 2026-04-10.

---

## 2. Evolution API v2.3.0 — Formato Real de Payloads

### Decision: Parser reescrito contra 26 fixtures reais capturadas

**Rationale**: 36 webhooks reais capturados de 2 instâncias Evolution (Ariel + ResenhAI) em 2026-04-10, anonimizados para 26 pares de fixtures (`*.input.json` + `*.expected.yaml`). Análise revelou 12 divergências críticas entre o parser do epic 001 e os payloads reais.

**Divergências identificadas**:

| # | Problema | Parser Epic 001 | Realidade v2.3.0 |
|---|----------|-----------------|-------------------|
| 1 | `messageType` | Valores curtos: `image`, `video` | Valores reais: `imageMessage`, `videoMessage`, etc. |
| 2 | Sender `@lid` | Não tratado | `remoteJid` = `<15-digit>@lid`, phone real em `key.senderPn` |
| 3 | `mentionedJid` | Em `message.extendedTextMessage.contextInfo` | Em `data.contextInfo` (top-level) |
| 4 | `groups.upsert` | `data` como dict com `key` | `data` como **lista** sem `key` |
| 5 | `group-participants.update` | Assume `data.key` existe | `data` é dict **sem `key`**, com `{action, author, participants[]}` |
| 6 | `quotedMessage` | Não extraído | Em `data.contextInfo.quotedMessage` |
| 7 | `reactionMessage` | Não reconhecido | Tipo real com `reactionMessage.key` e `reactionMessage.text` |
| 8 | `pollCreationMessageV3` | Não reconhecido | Tipo real de enquete |
| 9 | `eventMessage` | Não reconhecido | Tipo real de evento no chat |
| 10 | `conversation` vs `extendedText` | `extendedText` é nome do tipo | Tipo real é `extendedTextMessage` |
| 11 | Campos irrelevantes | Não filtrados | `messageContextInfo`, `chatwoot*`, `deviceListMetadata`, `base64` poluem |
| 12 | `locationMessage` vs `liveLocationMessage` | Ambos como `location` | Tipos distintos no payload |

**Alternatives considered**:
1. **Patch incremental do parser** — Rejeitado. 12 divergências são profundas demais para patches; rewrite é mais limpo e testável.
2. **Schema validation com JSON Schema** — Rejeitado. Payloads da Evolution são inconsistentes entre versões; schema rígido quebraria com updates.
3. **Rewrite com fixture-driven TDD (escolhido)** — Cada correção validada contra fixtures reais. Zero suposições — se não está em uma fixture capturada, não é implementado.

---

## 3. Multi-Tenant Architecture — YAML-backed TenantStore

### Decision: Alternativa D — multi-tenant estrutural, single-tenant operacional

**Rationale**: Análise de 4 alternativas no IMPLEMENTATION_PLAN.md §5.2-5.4, validadas contra a visão de produto (multi-tenant end-state) e restrições operacionais (2 tenants internos, sem Postgres, sem Admin API).

**Alternatives considered**:
1. **Alternativa A — single-tenant puro** — Rejeitado. Refactor doloroso posterior (§5.2 documenta dor histórica de migração single→multi em codebases similares).
2. **Alternativa B — multi-tenant via env vars** — Rejeitado. Não escala para N tenants; cada novo tenant requer redeploy com novas vars.
3. **Alternativa C — multi-tenant com Postgres + Admin API** — Rejeitado **nesta fase**. Over-engineering para 2 tenants internos; Postgres (Supabase) ainda não está deployado.
4. **Alternativa D — multi-tenant estrutural, YAML-backed (escolhido)** — `Tenant` dataclass frozen + `TenantStore` carrega `tenants.yaml` no startup. Interface `find_by_instance()` + `get()` é idêntica ao futuro DB-backed store (Fase 3, ADR-023). Código suporta N tenants; deploy opera com 2.

**Key design decisions**:
- `Tenant` é `@dataclass(frozen=True, slots=True)` (não Pydantic `BaseModel`) por performance e imutabilidade.
- Interpolação `${ENV_VAR}` via regex `\$\{(\w+)\}` no loader — secrets nunca ficam no YAML.
- Index dual: por `id` e por `instance_name` (ambos O(1) lookup via dict).
- Startup falha se: YAML ausente, `${ENV_VAR}` não definida, `id`/`instance_name` duplicados.
- Hot reload não suportado na Fase 1 (restart required) — otimização prematura para 2 tenants.

---

## 4. Idempotência — Redis SETNX com TTL 24h

### Decision: `SET NX EX` atômico por `(tenant_id, message_id)`

**Rationale**: Evolution API reenvia webhooks com até 10 retries com backoff exponencial. Sem idempotência, efeitos colaterais duplicam (echo, futuras persistências, chamadas a LLM).

**Alternatives considered**:
1. **Hash do body como chave** — Rejeitado. Timestamps de retry variam; hash seria diferente para cada tentativa.
2. **Bloom filter** — Rejeitado. False positives perderiam mensagens legítimas; complexidade desnecessária.
3. **SETNX por `message_id` global** — Rejeitado. Cross-tenant collision quando tenants compartilham a mesma instância Evolution (improvável mas possível).
4. **SETNX por `(tenant_id, message_id)` com TTL 24h (escolhido)** — Key format `seen:{tenant_id}:{message_id}`. Atômico. TTL cobre janela completa de retries. Isolamento per-tenant.

**Fail-open policy**: Se Redis estiver indisponível, processa a mensagem (preferível processar duplicada a perder mensagem). Log warning.

---

## 5. Mention Detection — 3-Strategy Pattern

### Decision: `mention_lid_opaque` → `mention_phone` → keywords

**Rationale**: WhatsApp moderno usa identificadores `@lid` (Linked ID) de 15 dígitos opacos em vez de phone JIDs. Groups modernos enviam mentions com `@lid` em `data.contextInfo.mentionedJid`. Fallback para phone JID cobre grupos legacy. Keyword substring cobre texto livre ("@ariel").

**Alternatives considered**:
1. **Apenas phone JID** — Rejeitado. 100% dos mentions em grupos modernos falhariam (usam `@lid`).
2. **Apenas keyword** — Rejeitado. Falso positivos quando texto contém keyword por acidente.
3. **3-strategy em ordem de prioridade (escolhido)** — Strategy 1 (`mention_lid_opaque` em `mentioned_jids`) cobre 100% dos mentions reais. Strategy 2 (phone JID) cobre legacy. Strategy 3 (keyword) é catch-all para texto livre.

**Discovery workflow** para `mention_lid_opaque`: documentado no README — (1) configurar webhook temporário, (2) pedir menção ao bot em grupo, (3) ler `data.contextInfo.mentionedJid`, (4) extrair `<15-digit>@lid`, (5) guardar em `tenants.yaml`.

---

## 6. Debounce Keys — Tenant-Prefixed Pattern

### Decision: `buf:{tenant_id}:{sender_key}:{ctx}` e `tmr:{tenant_id}:{sender_key}:{ctx}`

**Rationale**: Sem prefixo de tenant, 2 tenants com sender keys coincidentes colidiriam. `sender_key = sender_lid_opaque or sender_phone` é a identidade estável do sender.

**Alternatives considered**:
1. **Keys sem prefixo (status quo)** — Rejeitado. Colisão cross-tenant possível.
2. **Redis databases separados por tenant** — Rejeitado. Complicação operacional desnecessária para 2 tenants.
3. **Prefixo `{tenant_id}:` em todas as chaves (escolhido)** — Simples, eficaz, debugável via `redis-cli keys 'buf:pace-internal:*'`.

---

## 7. Observability Delta — Resource vs Per-Span Attributes

### Decision: `tenant_id` removido do Resource, movido para per-span attribute

**Rationale**: Resource do OpenTelemetry é process-wide e imutável. Em multi-tenant, o `tenant_id` varia por request, não por processo. O epic 002 definiu `SpanAttributes.TENANT_ID = "tenant_id"` — contrato preservado. Apenas a **fonte** do valor muda (de `settings.tenant_id` singleton para `tenant.id` da dependency).

**Sites a alterar**:
1. `setup.py` L65-72: remover `"tenant_id": settings.tenant_id` do `Resource.create()`.
2. `config.py` L58: remover campo `tenant_id: str = "prosauai-default"`.
3. `webhooks.py` L83: trocar `settings.tenant_id` por `tenant.id`.
4. `debounce.py`: novo param `tenant_id` em `append()`, emitir como span attribute.
5. `main.py`: `_flush_echo` resolve tenant via `parse_expired_key` + `tenant_store.get()`.
6. `webhooks.py`: `structlog.contextvars.bind_contextvars(tenant_id=tenant.id)`.

**Dashboards Phoenix**: `phoenix-dashboards/README.md` (596 linhas, artefato do 002) já assume chave `tenant_id` nos spans — funciona sem mudança.

---

## 8. Deploy Topology — Zero Public Ports

### Decision: `docker-compose.yml` sem `ports:`, bind Tailscale no override

**Rationale**: Superfície de ataque zero até Fase 2. Evolution API e ProsaUAI na mesma VPS comunicam via Docker network privada.

**Alternatives considered**:
1. **Porta exposta em `0.0.0.0`** — Rejeitado. Ataque remoto possível.
2. **Caddy reverse proxy com TLS** — Rejeitado **nesta fase**. ADR-021 documenta para Fase 2.
3. **Docker network privada + Tailscale no dev (escolhido)** — Tráfego nunca sai do host em prod Fase 1; acesso dev via VPN.

**Port 8050**: escolhido por não conflitar com madruga-ai daemon (8040) nem Evolution Manager (8080).

---

## 9. Best Practices Researched

### FastAPI Dependency Injection para Multi-Tenant Auth
- Pattern: dependency que retorna `(Tenant, bytes)` — resolve tenant + valida auth + retorna body em um passo.
- Constant-time comparison via `hmac.compare_digest()` (stdlib Python) — sem dependência extra.
- Path parameter `{instance_name}` para tenant resolution é idiomatic FastAPI (type-safe, OpenAPI docs automático).

### Redis SETNX para Idempotência
- Pattern amplamente documentado: `SET key value NX EX ttl` é atômico e thread-safe.
- TTL deve cobrir window de retries + margem (24h é conservador e cobre cenários extremos).
- Key format com namespace previne colisões em Redis compartilhado.

### Frozen Dataclass vs Pydantic BaseModel para Config Imutável
- `@dataclass(frozen=True, slots=True)` tem overhead ~5x menor que Pydantic BaseModel para read-only data.
- Hashable por padrão — pode ser usado como dict key ou em sets.
- Slots reduz footprint de memória (~40% menor).
- Trade-off: sem validação automática do Pydantic (aceitável pois validação é feita no loader).

### YAML Interpolação de Environment Variables
- Pattern simples: regex `\$\{(\w+)\}` + `os.environ[match]`.
- Alternativa `pydantic-settings` YAML source: overkill para 2 tenants.
- Alternativa `envsubst`: quebra loading programático em testes.

---

handoff:
  from: speckit.plan (Phase 0)
  to: speckit.plan (Phase 1)
  context: "Pesquisa completa — 9 decisões de design validadas contra documentação, source code, e dados empíricos. Zero NEEDS CLARIFICATION restante."
  blockers: []
  confidence: Alta
  kill_criteria: "Se Evolution API mudar formato de webhook ou adicionar HMAC signing em versão futura, research §1 e §2 precisam revisão."
