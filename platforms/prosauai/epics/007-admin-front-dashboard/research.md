# Research — Epic 007: Admin Front Dashboard Inicial

**Branch**: `epic/prosauai/007-admin-front-dashboard` | **Date**: 2026-04-15

## 1. Divergências ADRs vs. Decisões do Epic

### 1.1 Auth: JWT HS256 via FastAPI vs. Supabase Auth (ADR-010/Blueprint)

**Contexto**: O blueprint e ADR-010 indicam Supabase Auth (GoTrue) para autenticação do admin. O pitch decide JWT HS256 emitido pela própria FastAPI com PyJWT + bcrypt (passlib).

- **Decisão**: JWT HS256 via FastAPI (PyJWT)
- **Rationale**: Supabase Auth (GoTrue) adiciona dependência externa e complexidade de configuração para ~3 usuários internos em Tailscale. JWT HS256 local é suficiente e mais simples. Migração para GoTrue fica como follow-up quando houver portal de cliente.
- **Alternativas consideradas**:
  - A) Supabase Auth direto — mais robusto (refresh tokens, MFA), mas overengineering para escopo interno
  - B) X-Admin-Token estático (ADR-022 fase 2) — mais simples, mas sem auditoria de quem acessou
  - C) **JWT HS256 local (escolhido)** — equilíbrio: identidade do admin no token, sem dependência externa
- **Risco**: Se GoTrue for adotado depois, migração requer alterar cookie format + middleware Next.js. Mitigação: abstrair auth em módulo isolado (`prosauai/auth/`).

### 1.2 Schema Location: `public` vs. `admin` (ADR-024)

**Contexto**: ADR-024 reserva schema `admin` para tabelas administrativas (epic 013). O pitch decide criar `admin_users` e `audit_log` em `public`.

- **Decisão**: Tabelas em `public`
- **Rationale**: ADR-024 nunca foi aplicada no código — todas as tabelas existentes estão em `public` (drift documentado). Criar tabelas no schema `admin` agora requer configurar `search_path` e alterar pool connections, gerando risco de regressão no pipeline existente.
- **Alternativas consideradas**:
  - A) Schema `admin` (ADR-024) — correto arquiteturalmente, mas risco de regressão
  - B) **Schema `public` (escolhido)** — pragmático, cleanup vira epic separado
  - C) Schema `prosauai` — semanticamente errado (admin_users não é entidade de negócio)

### 1.3 Admin API: FastAPI Router vs. BFF Separado (ADR-022)

**Contexto**: ADR-022 define endpoints `/admin/tenants/*` com `X-Admin-Token`. O pitch expande para JWT auth + novos endpoints (`/admin/auth/*`, `/admin/metrics/*`).

- **Decisão**: Expandir FastAPI existente com router `/admin/*`
- **Rationale**: BFF separado (Next.js API routes) adicionaria um hop de rede e complexidade operacional. FastAPI já tem toda a infra (pools, logging, Redis). Admin endpoints são leves (<5 rotas neste epic).
- **Alternativas consideradas**:
  - A) BFF em Next.js API routes — isola frontend de detalhes backend, mas duplica auth + pool management
  - B) **Router no FastAPI existente (escolhido)** — zero overhead, reutiliza infra
  - C) Serviço FastAPI separado — justificável com >20 endpoints, overengineering agora

## 2. dbmate como Migration Tool

### Pesquisa

- **dbmate** (v2.x): single binary Go, suporta PostgreSQL, tracking via tabela `schema_migrations`, migrations em SQL puro (up/down), idempotente.
- **Alternativas avaliadas**:
  - Alembic: Python nativo, mas requer modelo SQLAlchemy (prosauai usa asyncpg raw). [FONTE?: https://alembic.sqlalchemy.org/]
  - Flyway: Java runtime, pesado para o contexto.
  - golang-migrate: similar ao dbmate, mas dbmate tem melhor UX (`dbmate up`, `dbmate rollback`).
  - **dbmate (escolhido)**: sem runtime Python, SQL puro compatível com asyncpg raw, single binary para Docker.

### Integração

- Migrations em `apps/api/db/migrations/` (formato `YYYYMMDDHHMMSS_name.sql`).
- Container Docker do dbmate ou binary copiado no Dockerfile da API.
- `docker-compose` service `migrate` que roda `dbmate up` antes de `api` e `admin` subirem.
- Migrations existentes (001-008 em `docker-entrypoint-initdb.d/`) devem ser convertidas para formato dbmate. **Risco**: conversão requer manter idempotência para ambientes que já rodaram as migrations originais.

## 3. Monorepo pnpm — Best Practices 2026

### Pesquisa

- **pnpm workspaces**: suporta `apps/*` e `packages/*` nativamente via `pnpm-workspace.yaml`.
- **Shared types**: pacote `@prosauai/types` em `packages/types/` com tipos TypeScript gerados a partir do OpenAPI schema da FastAPI.
- **Docker context**: cada app tem seu Dockerfile; `docker-compose.yml` na raiz do monorepo com `context: .` e `dockerfile: apps/admin/Dockerfile`.
- **CI**: `pnpm --filter <app> install/build/test` para builds seletivos.

### Estrutura decidida

```
prosauai/
├── apps/
│   ├── api/           # FastAPI existente (movida da raiz)
│   │   ├── prosauai/  # código Python
│   │   ├── tests/
│   │   ├── db/
│   │   │   └── migrations/  # dbmate migrations
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── admin/         # Next.js 15 (novo)
│       ├── src/
│       │   ├── app/       # App Router pages
│       │   ├── components/
│       │   ├── lib/       # api-client, auth context
│       │   └── hooks/
│       ├── package.json
│       └── Dockerfile
├── packages/
│   └── types/         # @prosauai/types (OpenAPI → TS)
│       ├── api.ts     # generated
│       └── package.json
├── pnpm-workspace.yaml
├── docker-compose.yml
├── docker-compose.override.yml  # dev volumes, port overrides
└── .env.example
```

## 4. Pool Separation — asyncpg Dual Pool

### Pesquisa

- asyncpg suporta múltiplos pools no mesmo processo sem problemas.
- `statement_cache_size=0` obrigatório em ambos (Supavisor compat, já configurado).
- **pool_tenant**: role `authenticated` (NOSUPERUSER), RLS enforced. Usado pelo pipeline de mensagens existente.
- **pool_admin**: role `service_role` (BYPASSRLS). Usado exclusivamente por rotas `/admin/*`.

### Implementação

```python
# pool.py — dual pool init
pool_tenant = await asyncpg.create_pool(
    dsn=settings.database_url,
    min_size=2, max_size=10,
    server_settings={"statement_cache_size": "0"},
    # connection init: SET ROLE authenticated
)

pool_admin = await asyncpg.create_pool(
    dsn=settings.database_url,
    min_size=1, max_size=5,
    server_settings={"statement_cache_size": "0"},
    # connection init: SET ROLE service_role
)
```

- **Risco**: Se `service_role` não existir no Supabase gerenciado, precisa criar via migration. Supabase cria `service_role` por padrão — [VALIDAR] no ambiente de prod.

## 5. shadcn Chart (recharts) — Dashboard Gráfico

### Pesquisa

- shadcn/ui oferece `Chart` component como wrapper oficial sobre recharts desde Q4 2024.
- Tokens CSS `--chart-1` a `--chart-5` herdam do tema shadcn.
- `BarChart` de recharts para contagens diárias discretas — decisão do spec (barras, não linha).
- Gap-fill no backend (SQL `generate_series`) garante que o frontend receba todos os 30 dias.

### Implementação frontend

```tsx
// Componente MessageVolumeChart
<ChartContainer config={chartConfig}>
  <BarChart data={dailyData}>
    <XAxis dataKey="date" />
    <YAxis />
    <Bar dataKey="count" fill="var(--chart-1)" />
  </BarChart>
</ChartContainer>
```

## 6. Rate Limiting — slowapi + Redis

### Pesquisa

- `slowapi` é wrapper do `limits` para Starlette/FastAPI. Suporta Redis como backend storage.
- Configuração: `5/minute` por key composta `IP:email`.
- Redis 7 já disponível no ambiente.

### Implementação

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"redis://{settings.redis_host}:{settings.redis_port}/1"
)

@router.post("/admin/auth/login")
@limiter.limit("5/minute", key_func=lambda req: f"{get_remote_address(req)}:{req.json().get('email','')}")
async def login(request: Request, body: LoginRequest): ...
```

## 7. Next.js Middleware — Auth Cookie Validation

### Pesquisa

- Next.js 15 Edge middleware roda no Edge Runtime (subset de Node.js APIs).
- Cookie JWT não-httpOnly (`SameSite=Lax`, `Secure` em prod) permite leitura via `req.cookies` no middleware.
- Middleware valida presença + não-expiração do JWT (decode sem verify no edge, full verify no server).
- Rota `/admin/login` é excluída do middleware via `matcher`.

### Implementação

```typescript
// middleware.ts
export function middleware(request: NextRequest) {
  const token = request.cookies.get("admin_token")?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/admin/login", request.url));
  }
  // Decode (no verify) to check exp — full verify happens server-side
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.exp * 1000 < Date.now()) {
      return NextResponse.redirect(new URL("/admin/login", request.url));
    }
  } catch {
    return NextResponse.redirect(new URL("/admin/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/((?!login).*)"],
};
```

---
handoff:
  from: research.md
  to: data-model.md
  context: "Todas as clarificações técnicas resolvidas. Divergências com ADRs documentadas e justificadas. Stack confirmada: FastAPI JWT HS256, dbmate, pnpm monorepo, dual asyncpg pool, shadcn Chart."
  blockers: []
  confidence: Alta
  kill_criteria: "Se pool_admin com BYPASSRLS não funcionar no Supabase gerenciado, o modelo de acesso admin precisa ser repensado."
