# Contract: Tenant Configuration Schema

**Date**: 2026-04-10  
**Epic**: `003-multi-tenant-foundation`  
**Type**: YAML Configuration File

---

## File Location

```
config/tenants.yaml     # Active config (gitignored)
config/tenants.example.yaml  # Template (committed)
```

## Schema

```yaml
tenants:
  - id: string              # REQUIRED — unique tenant identifier
    instance_name: string    # REQUIRED — unique Evolution instance name
    evolution_api_url: string  # REQUIRED — base URL (supports ${ENV_VAR})
    evolution_api_key: string  # REQUIRED — API key (supports ${ENV_VAR})
    webhook_secret: string     # REQUIRED — X-Webhook-Secret (supports ${ENV_VAR})
    mention_phone: string      # REQUIRED — E.164 phone number (min 10 chars)
    mention_lid_opaque: string # REQUIRED — 15-digit @lid identifier
    mention_keywords:          # OPTIONAL — list of keyword triggers
      - string
    enabled: boolean           # OPTIONAL — default true
```

## Environment Variable Interpolation

Qualquer valor pode conter `${ENV_VAR}` que é resolvido no momento do loading:

```yaml
evolution_api_key: ${PACE_EVOLUTION_API_KEY}
# Resolved to the value of os.environ["PACE_EVOLUTION_API_KEY"]
```

**Regras**:
- Pattern: `\$\{(\w+)\}` (regex)
- Se a variável não existir no ambiente → `ValueError` no startup
- Interpolação múltipla no mesmo valor: `${PREFIX}/${SUFFIX}` → suportado
- Escape: não suportado (se precisar de literal `${...}`, use env var)

## Validation Rules (Startup)

| Rule | Error |
|------|-------|
| File not found | `FileNotFoundError` |
| Invalid YAML syntax | `ValueError: Invalid YAML` |
| `${ENV_VAR}` undefined | `ValueError: Environment variable 'X' not set` |
| Duplicate `id` | `ValueError: Duplicate tenant id: 'X'` |
| Duplicate `instance_name` | `ValueError: Duplicate instance_name: 'X'` |
| Empty `id` | `ValueError: Tenant id cannot be empty` |
| Empty `instance_name` | `ValueError: instance_name cannot be empty` |
| Empty `webhook_secret` | `ValueError: webhook_secret cannot be empty` |

## Lifecycle

- Loaded once at application startup (via `lifespan`)
- Immutable during runtime
- Changes require service restart
- Hot reload NOT supported in Phase 1

---

handoff:
  from: speckit.plan (contracts)
  to: speckit.tasks
  context: "Schema de configuração de tenants documentado com validações e regras de interpolação."
  blockers: []
  confidence: Alta
  kill_criteria: "Se formato YAML precisar de campos adicionais para Fase 2."
