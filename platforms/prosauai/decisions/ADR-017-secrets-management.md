---
title: 'ADR-017: Secrets Management — Vault, encryption e rotation'
status: Accepted
decision: Infisical (self-hosted)
alternatives: .env files, Supabase sem encryption (plain text em tabela com RLS),
  Secrets hardcoded no codigo, HashiCorp Vault
rationale: Secrets nunca em plain text — encryption at rest e in transit
---
# ADR-017: Secrets Management — Vault, encryption e rotation
**Status:** Accepted | **Data:** 2026-03-25

## Contexto
ProsaUAI gerencia credenciais sensiveis de multiplos tenants: tokens da Evolution API (WhatsApp), API keys de LLM providers, webhooks secrets, credenciais de integracoes externas. Agentes AI operam em real-time sem supervisao humana direta, amplificando o impacto de qualquer vazamento.

Riscos especificos:
- Se token da Evolution API de um tenant vaza, atacante envia mensagens como aquele tenant
- Se service role key do Supabase vaza, atacante bypassa RLS e acessa dados de TODOS os tenants
- Se LLM API keys sao compartilhadas sem isolamento, um tenant pode esgotar cota de outro
- Webhooks sem validacao permitem injection de eventos falsos

Static API keys em .env ou variaveis de ambiente compartilhadas sao insuficientes para agentes AI multi-tenant.

## Decisao
We will adotar secrets management centralizado desde o dia 1, com encryption por tenant e rotation automatica.

### 1. Vault (Infisical self-hosted)

Escolha: **Infisical** (open-source, MIT) como secret manager.

| Criterio | Infisical | HashiCorp Vault |
|----------|-----------|-----------------|
| Complexidade | Baixa (Docker Compose) | Alta (Consul, storage backend) |
| UI | Moderna, dev-friendly | Funcional, enterprise |
| Custo | Free self-hosted | Free OSS, enterprise pago |
| Dynamic secrets | Sim | Sim (mais maduro) |
| Licenca | MIT | BSL 1.1 (nao mais OSS puro) |

Motivo: Infisical tem menor footprint operacional para time de 5. Migra para Vault se precisar de dynamic secrets mais avancados.

### 2. Envelope Encryption por Tenant

```
┌─────────────────────────────────────────┐
│            Infisical Vault              │
│                                         │
│  Master Key (KEK)                       │
│  ├── DEK_tenant_A (encrypted)           │
│  ├── DEK_tenant_B (encrypted)           │
│  └── DEK_tenant_C (encrypted)           │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│         Supabase: tenant_credentials    │
│                                         │
│  tenant_id │ credential_type │ value    │
│  ─────────┼────────────────┼─────────  │
│  A        │ evolution_token │ ENC(...)  │ ← encrypted com DEK_A
│  A        │ llm_api_key    │ ENC(...)  │
│  B        │ evolution_token │ ENC(...)  │ ← encrypted com DEK_B
└─────────────────────────────────────────┘
```

- Master Key (KEK) vive no Vault — nunca no app server
- Data Encryption Key (DEK) por tenant — rotation de DEK nao requer re-encrypt de tudo
- Tabela `tenant_credentials` no Supabase com RLS (ADR-011) + encryption at rest
- App server decrypta em memoria, nunca persiste secret decryptado em disco/log

### 3. Key Rotation Automatica

| Secret | Rotation | Metodo |
|--------|----------|--------|
| Evolution API tokens | 30 dias | Cron job + Infisical rotation API |
| LLM API keys | 30 dias | Rotate no provider, update no Vault |
| Webhook secrets | 90 dias | Gerar novo secret, atualizar Evolution API config |
| DEK por tenant | 180 dias | Re-encrypt credentials com novo DEK |
| Supabase JWT secret | 90 dias | Rotate via Supabase dashboard/API |

### 4. Webhook X-Webhook-Secret Obrigatorio (atualizado epic 003)

```python
# TODA webhook da Evolution API DEVE ser validada
# NOTA: Evolution API nao implementa HMAC-SHA256 (confirmado via source-dive).
# Implementacao real usa header X-Webhook-Secret per-tenant com constant-time compare.
import hmac

def validate_webhook(request, tenant_webhook_secret: str) -> bool:
    secret = request.headers.get("X-Webhook-Secret")
    if not secret:
        return False  # rejeitar silenciosamente
    return hmac.compare_digest(secret, tenant_webhook_secret)
```

Requests sem secret valido sao rejeitados com 401. Logados como security event no Phoenix (ADR-020).

### 5. Runtime Secret Injection

```python
# Secrets injetados via pydantic-ai dependency injection
# NUNCA via environment variables compartilhadas
class TenantDeps(BaseModel):
    tenant_id: UUID
    evolution_token: str  # decrypted em runtime do Vault
    llm_api_key: str      # decrypted em runtime do Vault

@agent.tool
async def send_whatsapp(ctx: RunContext[TenantDeps], message: str, to: str):
    # token vem do ctx.deps, nao de env var
    await evolution.send(
        token=ctx.deps.evolution_token,
        to=to,
        message=message
    )
```

### 6. Audit Trail

Toda leitura de secret logada com:
- `tenant_id`
- `agent_id`
- `credential_type`
- `timestamp`
- `source_ip`
- `action` (read, rotate, create, delete)

Logs imutaveis no Phoenix ou storage separado. Retention: 1 ano (compliance).

## Alternativas consideradas

### .env files
- Pros: Simples, familiar, zero infra adicional
- Cons: Nao suporta multi-tenant (secrets compartilhados), sem rotation, sem audit, sem encryption. Se .env vaza, TODOS os tenants comprometidos. Inaceitavel para producao multi-tenant

### Supabase sem encryption (plain text em tabela com RLS)
- Pros: Simples, RLS protege acesso cross-tenant
- Cons: Backup do banco contem secrets em plain text. DBA com acesso ao banco ve tudo. Nao atende compliance. Se service role key vaza, todos os secrets expostos

### Secrets hardcoded no codigo
- Pros: Nenhuma
- Cons: Inaceitavel. Versionado no git, visivel para todo dev, impossivel de rotacionar

### HashiCorp Vault
- Pros: Mais maduro, dynamic secrets avancados, enterprise battle-tested
- Cons: Complexidade operacional alta (Consul, storage backend), licenca BSL 1.1 (nao mais OSS puro), overkill para time de 5 no momento. Migrar para Vault se Infisical nao atender

## Consequencias
- [+] Secrets nunca em plain text — encryption at rest e in transit
- [+] Vazamento de 1 DEK compromete apenas 1 tenant (blast radius limitado)
- [+] Rotation automatica reduz janela de exposicao
- [+] Webhook HMAC previne injection de eventos falsos
- [+] Audit trail completo para compliance e forensics
- [+] Runtime injection via pydantic-ai elimina secrets em env vars compartilhadas
- [-] Infra adicional (Infisical Docker container) para operar
- [-] Latencia adicional para decrypt em runtime (~1-5ms por secret read, mitiga com cache em memoria com TTL curto)
- [-] Complexidade de rotation — precisa de graceful handoff (periodo onde old e new key sao validos)
- [-] Time precisa aprender Infisical (curva de aprendizado baixa, mas e mais uma ferramenta)

---

> **Proximo passo:** `/madruga:blueprint prosauai` — consolidar stack de engenharia a partir dos ADRs aprovados.
