---
title: 'ADR-022: Admin API para gestao de tenants (Fase 2 multi-tenant)'
status: Proposed
decision: REST API com endpoints CRUD em /admin/tenants, auth via master token estatico
alternatives: gRPC admin API, GraphQL admin API, CLI-only (sem HTTP), Database direto via psql/pgcli
rationale: REST e simples, debugavel via curl, integravel com qualquer cliente. Master token estatico e suficiente para Fase 2 (1-5 tenants); JWT scoped fica para Fase 3 quando houver multi-org admins.
---
# ADR-022: Admin API para gestao de tenants (Fase 2 multi-tenant)

**Status:** Proposed | **Data:** 2026-04-10

> **Status note:** Esta ADR e **acionavel apenas a partir da Fase 2** (epic 012). Documentada agora (2026-04-10) durante o draft do epic 003 para registrar decisao end-state e evitar surpresa futura. Trigger de implementacao: primeiro cliente externo pagante (mesmo trigger de [ADR-021](ADR-021-caddy-edge-proxy.md)).

## Contexto

Na Fase 1 (epic 003 — Multi-Tenant Foundation), tenants sao gerenciados via edicao manual de `config/tenants.yaml`:

```yaml
tenants:
  - id: pace-internal
    instance_name: Ariel
    evolution_api_url: https://evolutionapi.pace-ia.com
    evolution_api_key: ${PACE_EVOLUTION_API_KEY}
    webhook_secret: ${PACE_WEBHOOK_SECRET}
    mention_phone: "5511910375690"
    mention_lid_opaque: "146102623948863"
    enabled: true
```

Para os 2 tenants internos (Pace Ariel + Pace ResenhAI), edicao manual e aceitavel. Para 1+ tenant externo na Fase 2, surge dor operacional:

1. **Vendas precisa criar tenants** sem mexer no repo (vendas nao tem `git push`)
2. **Cliente precisa de webhook_secret aleatorio** — gerar manualmente e propenso a erro
3. **Disable rapido de tenant abusivo** — editar YAML + commit + push + redeploy = lento demais para responder a incidente
4. **Audit trail** — quem habilitou/disabilitou/editou cada tenant? `git log` ajuda mas e indireto
5. **Hot reload** — editar YAML hoje exige restart do container; tenant criado precisa esperar restart

Na Fase 3 (epic 013), TenantStore migra para Postgres ([ADR-023](ADR-023-tenant-store-postgres-migration.md)) e a Admin API se torna a unica interface oficial. Mas ja na Fase 2 precisamos do **interface API** mesmo com storage YAML.

A pergunta e: **qual interface administrativa expor para gestao de tenants?**

## Decisao

We will expor uma **REST API admin** em `prosauai/api/admin.py` com endpoints CRUD em `/admin/tenants/*`, auth via header `X-Admin-Token` (master token estatico em env var), com hot reload do TenantStore via inotify watcher.

### Endpoints Fase 2

```
POST   /admin/tenants                 → cria tenant, gera webhook_secret aleatorio, persiste em tenants.yaml, dispara reload
GET    /admin/tenants                 → lista todos os tenants (sem secrets — apenas id, instance_name, enabled, created_at)
GET    /admin/tenants/{tenant_id}     → detalhe (sem secrets)
PATCH  /admin/tenants/{tenant_id}     → edita campos (mention_phone, mention_lid_opaque, mention_keywords, enabled)
DELETE /admin/tenants/{tenant_id}     → soft-delete (enabled=false). Hard delete exige flag explicito.
POST   /admin/tenants/{tenant_id}/rotate-secret  → gera novo webhook_secret, retorna 1x, marca antigo invalido
POST   /admin/tenants/reload          → forca reload do TenantStore sem restart (alternativa ao watcher)
GET    /admin/health                  → status do TenantStore (numero de tenants carregados, timestamp do ultimo reload)
GET    /admin/metrics                 → metricas basicas per-tenant (msgs/min, errors, debounces flushed)
```

### Auth Fase 2

```python
# prosauai/api/admin.py
async def verify_admin_token(request: Request) -> None:
    provided = request.headers.get("x-admin-token", "")
    expected = request.app.state.settings.admin_master_token
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(401, "Invalid admin token")
```

- **Master token** estatico em env var `ADMIN_MASTER_TOKEN`
- **Constant-time compare** para evitar timing attack
- **HTTPS obrigatorio** (Caddy faz TLS — [ADR-021](ADR-021-caddy-edge-proxy.md))
- **Rate limit per-IP** aplicado pelo Caddy (zona `admin_per_ip`)

### Schema POST /admin/tenants

```python
class CreateTenantRequest(BaseModel):
    id: str = Field(..., regex=r"^[a-z0-9-]{3,50}$")
    instance_name: str = Field(..., min_length=1, max_length=100)
    evolution_api_url: HttpUrl
    evolution_api_key: SecretStr
    mention_phone: str = Field(..., regex=r"^\d{10,15}$")
    mention_lid_opaque: str = Field(..., regex=r"^\d{15}$")
    mention_keywords: list[str] = Field(default_factory=list)

class CreateTenantResponse(BaseModel):
    id: str
    webhook_secret: SecretStr  # gerado pelo servidor — retornado UMA UNICA VEZ
    instance_url: str  # https://api.prosauai.com/webhook/whatsapp/{instance_name}
    created_at: datetime
    next_steps: list[str]  # array de instructions: ["1. Configure webhook na sua Evolution: ...", ...]
```

### Hot reload Fase 2

Duas estrategias suportadas:

1. **Inotify watcher** (default): `prosauai/core/tenant_store_watcher.py` usa `watchfiles` lib (asyncio-friendly) para detectar mudancas em `config/tenants.yaml` e re-carregar `app.state.tenant_store` em ate 500ms. Funciona para edicao manual + writes via Admin API.

2. **Endpoint dedicado** `POST /admin/tenants/reload`: forca reload sem watcher (fallback se watchfiles tiver problema).

Ambos garantem que mudancas no TenantStore propagam **sem restart do container**.

### Persistencia Fase 2

- Storage continua **YAML file** (`config/tenants.yaml`)
- Admin API faz: read YAML → mutate in-memory → write YAML atomic (tmp file + rename) → trigger reload
- Lock optimistic via mtime check (evita race condition entre 2 admins simultaneos)
- **Sem audit log** nesta fase — apenas log estruturado da operacao no stdout (`structlog admin_op`)

### Auth Fase 3 (futuro)

Quando Fase 3 chegar (epic 013), Admin API ganha:

- JWT scoped per-org (substitui master token unico)
- Audit log persistido em `audit_log` Postgres table (RLS isolada)
- Endpoint `GET /admin/audit?tenant_id=X` para investigacao
- Multi-org admins (para suporte a partner channel futuro)

## Alternativas consideradas

### gRPC admin API
- **Pros:** tipagem forte, performance, streaming
- **Cons:** debug via curl impossivel; tooling necessita protoc/gRPC client; vendas/admin nao consegue testar ad-hoc; **complexidade desproporcional para 1-5 tenants iniciais**. REST + curl resolve.

### GraphQL admin API
- **Pros:** query flexivel, schema introspectavel, single endpoint
- **Cons:** **overengineering** — Admin API tem ~10 operations bem definidas; GraphQL e otimo quando ha N relacoes complexas e clientes diferentes querem dados diferentes; aqui temos 1 cliente (vendas/admin), CRUD + 2 actions. REST e mais simples e mais debugavel.

### CLI-only (sem HTTP)
- **Pros:** zero superficie HTTP exposta; comando direto na VPS
- **Cons:** vendas nao tem acesso SSH a VPS; cada operacao admin exige Pace dev/SRE; **bloqueia self-service para vendas**, exatamente o problema que a Fase 2 quer resolver. Nao escala alem de 2-3 tenants.

### Database direto via psql/pgcli (Fase 3)
- **Pros:** zero codigo, acesso direto
- **Cons:** so funciona depois da migracao para Postgres (Fase 3); zero validacao (vendas pode quebrar schema); zero audit trail; sem geracao automatica de webhook_secret; sem hot reload. **Rejeitado por falta de safety net.**

### Auth via OAuth2/OIDC (Fase 2)
- **Pros:** integracao com Google Workspace ou Auth0
- **Cons:** **overkill para 1 admin user** (Pace internal). Adiciona 1-2 dependencias + complexidade de setup. Master token estatico e equivalente em seguranca para 1-org single-admin scenario. **Promovivel para JWT scoped na Fase 3** quando houver multi-org admins.

## Consequencias

- [+] **Vendas pode criar tenants via curl** sem mexer no repo
- [+] **Webhook secret aleatorio gerado pelo servidor** (`secrets.token_urlsafe(32)`) — sem erro humano
- [+] **Hot reload** propaga mudancas em ate 500ms — sem restart
- [+] **Disable rapido** de tenant abusivo via `PATCH /admin/tenants/{id}` `{enabled: false}`
- [+] **Atomic write** + mtime lock previne race condition entre 2 admins
- [+] **Compativel com YAML storage** da Fase 2 — migracao para Postgres na Fase 3 muda apenas o backend, interface fica igual
- [+] **Debugavel via curl** + Postman — vendas e ops conseguem usar sem ferramenta especializada
- [-] **Master token unico** = unico ponto de comprometimento. Mitigacao: rotacao manual periodica + alertas em 401 admin (futuro)
- [-] **Sem audit log persistente na Fase 2** — apenas stdout structured logs. Mitigacao: logs vao para Phoenix (epic 002) e podem ser queried por SpanQL. Audit table proper na Fase 3.
- [-] **Endpoints admin compartilham mesma app que webhook** — uma falha critica na admin API derruba o webhook tambem. Mitigacao: separar em container distinto (`prosauai-admin-api`) **so se** Fase 2 sentir essa dor; nao antecipar.
- [-] **Hot reload via inotify nao funciona em alguns sistemas de file** (NFS, alguns volumes Docker em macOS dev). Mitigacao: fallback para `POST /admin/tenants/reload` endpoint.
- [-] **`webhook_secret` aparece UMA VEZ** na resposta de POST/rotate — se vendas perder, precisa rotate. Documentar claramente.

## Refinamentos Fase 3

Quando Fase 3 (epic 013) entrar:

- **Auth via JWT scoped per-org** — substitui master token unico
- **`audit_log` table Postgres** — append-only, RLS isolada por org, queryable via `GET /admin/audit`
- **Endpoint `POST /admin/tenants/{id}/circuit-breaker/reset`** — reseta circuit breaker manualmente
- **Endpoint `POST /admin/tenants/{id}/replay-dlq`** — reprocessa mensagens da DLQ do tenant
- **OpenAPI spec exportada** + Swagger UI publicada em `/admin/docs` (gated por master token)
- **Webhook handler para Stripe** — `payment_succeeded` cria tenant automaticamente (self-service)

---

> **Proximo passo:** Trigger de implementacao = primeiro cliente externo pagante. Quando isso acontecer, implementar como parte do epic 012 (Public API Fase 2) junto com [ADR-021](ADR-021-caddy-edge-proxy.md).
