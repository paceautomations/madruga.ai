# Admin API Contract — Epic 007

**Base URL**: `http://localhost:8050` (dev) | `https://api.prosauai.com` (prod)
**Prefix**: `/admin`
**Auth**: JWT HS256 via cookie `admin_token` (exceto endpoints de auth)

## Auth Endpoints

### POST /admin/auth/login

Autentica um administrador e emite cookie JWT.

**Rate Limit**: 5 tentativas/minuto por IP + email

**Request**:
```json
{
  "email": "admin@pace.com",
  "password": "senha_segura_123"
}
```

**Response 200** (Set-Cookie: admin_token=<jwt>):
```json
{
  "user": {
    "id": "uuid",
    "email": "admin@pace.com"
  },
  "expires_at": "2026-04-16T12:00:00Z"
}
```

**Response 401**:
```json
{
  "detail": "Credenciais inválidas"
}
```

**Response 429**:
```json
{
  "detail": "Muitas tentativas. Aguarde 1 minuto."
}
```

### POST /admin/auth/logout

Remove a sessão do administrador.

**Auth**: Requer cookie `admin_token` válido.

**Response 200**:
```json
{
  "detail": "Logout realizado"
}
```

### GET /admin/auth/me

Retorna dados do administrador autenticado.

**Auth**: Requer cookie `admin_token` válido.

**Response 200**:
```json
{
  "id": "uuid",
  "email": "admin@pace.com",
  "last_login_at": "2026-04-15T10:30:00Z"
}
```

**Response 401**:
```json
{
  "detail": "Não autenticado"
}
```

## Metrics Endpoints

### GET /admin/metrics/messages-per-day

Retorna contagem de mensagens recebidas por dia nos últimos 30 dias (cross-tenant).

**Auth**: Requer cookie `admin_token` válido.

**Query Parameters**:
- `days` (optional, default: 30, max: 90): número de dias para consultar

**Response 200**:
```json
{
  "period": {
    "start": "2026-03-16",
    "end": "2026-04-15"
  },
  "total": 12847,
  "daily": [
    { "date": "2026-03-16", "count": 423 },
    { "date": "2026-03-17", "count": 0 },
    { "date": "2026-03-18", "count": 512 },
    ...
  ]
}
```

**Notas**:
- Dias sem mensagens aparecem com `count: 0` (gap-fill via `generate_series`)
- Timezone: `America/Sao_Paulo` (hardcoded) [VALIDAR]
- Dados agregados cross-tenant via `pool_admin` (BYPASSRLS)

## Health Endpoint

### GET /health

Verifica saúde da API e dependências.

**Auth**: Nenhuma (público).

**Response 200**:
```json
{
  "status": "healthy",
  "checks": {
    "database": "ok",
    "redis": "ok"
  },
  "version": "0.5.0"
}
```

**Response 503**:
```json
{
  "status": "unhealthy",
  "checks": {
    "database": "error",
    "redis": "ok"
  },
  "error": "Database connection failed"
}
```

## Cookie JWT Specification

| Atributo | Valor |
|----------|-------|
| Name | `admin_token` |
| HttpOnly | `false` (Edge middleware precisa ler) |
| SameSite | `Lax` |
| Secure | `true` em prod, `false` em dev |
| Path | `/` |
| Max-Age | 86400 (24h) |
| Domain | Não definido (current domain) |

**JWT Payload**:
```json
{
  "sub": "uuid-do-admin",
  "email": "admin@pace.com",
  "exp": 1713268800,
  "iat": 1713182400
}
```

**JWT Secret**: `JWT_SECRET` env var (min 32 chars).

## Error Format

Todos os erros seguem o padrão FastAPI:

```json
{
  "detail": "Mensagem de erro legível"
}
```

HTTP status codes:
- `400` — Requisição inválida (validation)
- `401` — Não autenticado / token expirado
- `403` — Autenticado mas sem permissão
- `404` — Recurso não encontrado
- `429` — Rate limit excedido
- `500` — Erro interno
- `503` — Dependência indisponível (health check)
