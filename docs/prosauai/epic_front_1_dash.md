# Epic Front 001 — Dashboard Inicial

**Objetivo:** primeira tela do painel admin da plataforma, com um gráfico de **Mensagens recebidas por dia**. Entregar a fundação (monorepo, auth, rotas `/admin`, dois pools asyncpg, stack Next.js) de forma que as próximas telas (tenants, conversas, agentes) sejam incrementais.

---

## Decisões arquiteturais (consolidadas)

| Tema | Decisão |
|---|---|
| Repositório | Monorepo — `apps/api` (FastAPI existente) + `apps/admin` (Next.js) + `packages/types` (OpenAPI→TS) |
| Docker | Mesmo `docker-compose.yml`. Serviço `admin` sobe sempre junto de `api`, `postgres`, `redis`, `phoenix` |
| Backend admin | Expandir FastAPI existente com router `/admin/*`. Nada de BFF separado |
| Isolamento de dados | **Dois pools asyncpg**: `pool_tenant` (role `authenticated`, RLS enforced via `FORCE ROW LEVEL SECURITY`) + `pool_admin` (role `service_role` BYPASSRLS). Variável de sessão usada pelas policies existentes: `app.current_tenant_id` (helper `public.tenant_id()`). Ambos os pools herdam `statement_cache_size=0` do pool atual (compatibilidade Supavisor) |
| Auth | **Fase 0 (este epic):** JWT simples emitido pela própria FastAPI, login email/senha, usuário admin bootstrap em migração. **Fase futura:** Supabase GoTrue self-hosted |
| RBAC | `app_metadata.platform_role` (admin interno) + tabela `tenant_memberships` (futuro). Neste epic só `platform_admin` |
| Frontend stack | Next.js 14 (App Router) + shadcn/ui (inclui shadcn Charts) + Tailwind + TanStack Query + TanStack Table + react-hook-form + zod + openapi-typescript |
| Design system / tokens | **shadcn/ui como fonte única de verdade.** Cores via CSS vars semânticas (`--background`, `--foreground`, `--primary`, `--card`, `--muted`, `--border`, `--chart-1..5`). Gráficos usam `shadcn Chart` (wrapper oficial sobre recharts) para herdar os mesmos tokens — sem Tremor, evitando conflito de paleta |
| Cache | Sem cache de servidor (Redis) nesta fase. TanStack Query no browser + índices Postgres + cursor pagination |
| URL tenant-scoped | `/admin/t/{slug}/...` (preparado; não usado ainda neste epic) |
| Auditoria | Tabela `audit_log` criada já; triggers só nas tabelas mutáveis por admin (não neste epic, pois não há mutação) |

---

## Entregável

Acessando `http://localhost:3000/admin`, após login:

- Layout base com sidebar, header com user menu, área de conteúdo.
- Página `/admin` (dashboard) com:
  - KPI no topo: total de mensagens recebidas (últimos 30 dias).
  - Gráfico de linha **Mensagens recebidas por dia** (últimos 30 dias), agregando todos os tenants.
  - Seletor simples de intervalo: 7d / 30d / 90d (só período; sem filtro por tenant nesta fase).

---

## Estrutura de diretórios resultante

```
prosauai/
├── apps/
│   ├── api/                    # = código atual de prosauai/ movido para cá
│   └── admin/                  # Next.js novo
│       ├── app/
│       │   ├── (auth)/login/page.tsx
│       │   ├── admin/
│       │   │   ├── layout.tsx
│       │   │   └── page.tsx    # dashboard
│       │   └── layout.tsx
│       ├── components/
│       │   ├── ui/             # shadcn (copiado via CLI)
│       │   └── charts/
│       ├── lib/
│       │   ├── api-client.ts   # fetch wrapper com JWT
│       │   └── auth.ts
│       ├── package.json
│       └── Dockerfile
├── packages/
│   └── types/
│       ├── api.ts              # gerado via openapi-typescript
│       └── package.json
├── docker-compose.yml          # adiciona serviço `admin`
├── migrations/
│   ├── 010_admin_auth.sql      # roles pg, admin_users, audit_log
│   └── 011_seed_admin_user.sql
└── pyproject.toml
```

---

## Fases e tasks

### Fase 0 — Pré-voo (F0)

Diligência obrigatória antes de tocar em código. ~2-3h, resultado documentado como ADR ou nota no PR 1.

- **F0.1 Audit de RLS real.** Conectar no Postgres como user `prosauai` e rodar `SELECT schemaname, tablename, rowsecurity, forcerowsecurity FROM pg_tables WHERE schemaname='public';` + `SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname='prosauai';`. **Achado esperado:** `prosauai` é superuser (criado pelo docker via `POSTGRES_USER`), e **superuser ignora RLS incondicionalmente — mesmo com `FORCE ROW LEVEL SECURITY`**. Conclusão: o isolamento RLS hoje **só funciona por acidente** (porque o código sempre chama `with_tenant` que seta a variável) — não há rede de segurança real. A F2.1 resolve criando roles não-superuser (`authenticated`, `service_role`) e trocando a app para usar elas. Superuser `prosauai` fica reservado para migrations.
- **F0.2 Mapear call sites de pool.** Listar todos os usos do pool atual e confirmar que **100%** usam `with_tenant()` (contract manager que seta `app.current_tenant_id`). Qualquer `pool.acquire()` cru hoje passa a quebrar depois da F2.3 quando o role perder privilégios de owner. Comando: `rg "pool\.(acquire|execute|fetch)" apps/api/prosauai/`.
- **F0.3 Decidir gerenciador de pacotes Node.** Recomendação: **pnpm** (workspaces nativos, diskspace, velocidade). Commitar `pnpm-lock.yaml`. Documentar no README.
- **F0.4 Inventário de deps novas.** Python: `PyJWT>=2.9`, `passlib[bcrypt]>=1.7`. Node: ver F3.3 consolidado.
- **F0.5 Local do epic.** Mover este arquivo para `platforms/epics/007-admin-front-dashboard/epic.md` (seguindo convenção existente: `001-channel-pipeline`, …, `006-production-readiness`).

**Critério:** ADR curta ou seção no README documentando: owner das tabelas, qual variável RLS (`app.current_tenant_id`), decisão pnpm, deps a instalar.

### Fase 1 — Reestruturação em monorepo (F1)

- **F1.1** Mover `prosauai/` (código Python), `tests/`, `tools/`, `config/`, `migrations/`, `Dockerfile` para `apps/api/`. Manter `docker-compose.yml`, `platforms/`, `phoenix-dashboards/`, `.env.example`, `README.md` na raiz. Atualizar `pyproject.toml` (ou movê-lo para `apps/api/`), paths no `docker-compose.yml`, imports. Rodar `pytest` completo.
- **F1.2** Criar `apps/admin/` vazio com `package.json` (`"name": "@prosauai/admin"`) e `pnpm-workspace.yaml` na raiz listando `apps/*` e `packages/*`. Commitar `pnpm-lock.yaml`.
- **F1.3** Criar `packages/types/` com `package.json` (`"name": "@prosauai/types"`). Gerar o OpenAPI **offline** (sem precisar API rodando em CI): script Python `apps/api/scripts/export_openapi.py` que importa `prosauai.main:app` e escreve `packages/types/openapi.json`. Depois, `pnpm --filter @prosauai/types generate` roda `openapi-typescript openapi.json -o src/api.ts`. Export único: `export * from './api'`. Dev rápido via URL (`http://localhost:8050/openapi.json`) também fica documentado.
- **F1.4** Atualizar `docker-compose.yml`:
  - Build da api: `context: ./apps/api`.
  - Adicionar **healthcheck na api** (não existe hoje): `test: curl -f http://localhost:8050/health` — necessário para `admin.depends_on.api.condition: service_healthy`.
  - Trocar env `DATABASE_URL` do serviço `api` para apontar ao role `authenticated` (ver F2.1 / tabela de env vars). Manter `POSTGRES_USER=prosauai` (superuser) **apenas** para initdb e migrations — a app nunca conecta como ele.
  - Adicionar serviço `admin`: `build: ./apps/admin`, porta 3000, `depends_on: api (service_healthy)`, healthcheck próprio. O healthcheck do admin requer rota `app/api/health/route.ts` no Next.js (retornar `{ok: true}`) — criar em F3.1.
  - Serviço `admin` **sempre** sobe.
- **F1.5** Criar `docker-compose.override.yml` (ou estender o existente) para **dev**: montar volume `./apps/admin:/app` no serviço admin e sobrescrever command para `pnpm dev` (hot-reload). Em prod, Dockerfile multi-stage produz build standalone (F3.10).

**Critério:** `docker compose up` sobe tudo; testes Python passam; `/openapi.json` acessível.

### Fase 2 — Backend admin mínimo (F2)

- **F2.1** Migração `010_admin_auth.sql`:
  - Criar roles Postgres **não-superuser**: `CREATE ROLE authenticated LOGIN PASSWORD :'auth_pwd' NOSUPERUSER NOBYPASSRLS;` + `CREATE ROLE service_role LOGIN PASSWORD :'svc_pwd' NOSUPERUSER BYPASSRLS;`. **Crítico:** NOSUPERUSER — superuser ignora RLS e BYPASSRLS simultaneamente, tornando qualquer política ineficaz.
  - Migrar **ownership** das tabelas para um role neutro (`CREATE ROLE app_owner NOLOGIN NOSUPERUSER;` + `ALTER TABLE <cada> OWNER TO app_owner;`) — assim `authenticated` não é owner nem superuser, e RLS é enforced de verdade.
  - `ALTER TABLE <cada tabela de negócio> FORCE ROW LEVEL SECURITY;` — belt + suspenders: força RLS mesmo para o owner `app_owner` (nunca usado para queries, mas caso alguma migration use-o).
  - `GRANT USAGE ON SCHEMA public TO authenticated, service_role;` + `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated, service_role;` + `GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated, service_role;` + `GRANT EXECUTE ON FUNCTION public.tenant_id() TO authenticated, service_role;`.
  - `ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated, service_role;` — migrations futuras que criem tabelas herdam os grants automaticamente.
  - Policy `service_role` redundante (defesa em profundidade): `CREATE POLICY service_role_all ON <tabela> TO service_role USING (true) WITH CHECK (true);`.
  - Tabela `admin_users (id uuid PK, email text UNIQUE, password_hash text, platform_role text DEFAULT 'platform_admin', created_at timestamptz, last_login_at timestamptz)`.
  - Tabela `audit_log (id uuid PK, actor_id uuid, action text, resource_type text, resource_id text, metadata jsonb, created_at timestamptz)` — **tabela simples, sem particionamento**. Índice em `(created_at DESC, actor_id)`. Particionar apenas quando houver escrita e volume exigir.
  - Índice auxiliar para o dashboard: `CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);` (hoje só existe `idx_messages_tenant` e composto `(conversation_id, created_at)` — insuficiente para agregação cross-tenant por dia).
- **F2.2** Bootstrap do admin user — **não via migration SQL**. Motivos: (a) `docker-entrypoint-initdb.d/*.sql` só roda na **primeira** inicialização do Postgres (volume vazio); devs com pgdata existente nunca rodariam o seed; (b) senha em bcrypt não cabe em SQL puro. Solução:
  - Script `apps/api/scripts/bootstrap_admin.py` — lê `ADMIN_BOOTSTRAP_EMAIL`/`ADMIN_BOOTSTRAP_PASSWORD`, gera hash bcrypt, conecta via `DATABASE_URL_ADMIN` (service_role) e faz `INSERT ... ON CONFLICT (email) DO NOTHING`.
  - Invocado no entrypoint do container `api` (antes do `uvicorn`) ou via `docker compose exec api python scripts/bootstrap_admin.py`. Documentar no README.
  - **Também definir uma estratégia de migração para tabelas novas**: hoje o repo depende de `docker-entrypoint-initdb.d`, que não re-executa. Para a 010 aplicar em ambientes já inicializados, documentar: `docker compose exec postgres psql -U prosauai -d prosauai -f /docker-entrypoint-initdb.d/010_admin_auth.sql`. Ferramenta de migration real (Alembic, `yoyo-migrations`, `dbmate`) fica como follow-up (risco abaixo).
- **F2.3** `apps/api/prosauai/db/pool.py` + `apps/api/prosauai/config.py` + `apps/api/prosauai/main.py`:
  - Settings novas (`config.py`): `database_url_admin: str`, `admin_jwt_secret: str`, `admin_jwt_expires_minutes: int = 60`, `admin_frontend_origin: str = "http://localhost:3000"`, `admin_bootstrap_email: str = ""`, `admin_bootstrap_password: str = ""`.
  - Pool atual vira `pool_tenant` — conecta via `DATABASE_URL` (role `authenticated`). Mantém `with_tenant()` context manager. Call sites existentes **não mudam** se F0.2 confirmou que todos usam `with_tenant`.
  - `pool_admin` novo — conecta via `DATABASE_URL_ADMIN` (role `service_role`). Usado **apenas** por routers `/admin/*` após `Depends(get_current_admin)`. Expor helper `with_admin(pool) -> AsyncContextManager[Connection]` que apenas `acquire` (sem transação obrigatória, sem `SET LOCAL`).
  - Ambos pools com `statement_cache_size=0` e o `_init_connection` (jsonb codec) já existentes.
  - Lifespan do FastAPI cria os dois em `app.state.pg_pool` (tenant) e `app.state.pg_pool_admin`; fecha ambos no shutdown.
  - Compose: adicionar env `DATABASE_URL_ADMIN=postgresql://service_role:${POSTGRES_SERVICE_ROLE_PASSWORD}@postgres:5432/${POSTGRES_DB}` e trocar `DATABASE_URL` existente para `authenticated:${POSTGRES_AUTHENTICATED_PASSWORD}`.
- **F2.4** `apps/api/prosauai/auth/` (novo):
  - Deps a adicionar em `pyproject.toml`: `PyJWT>=2.9`, `passlib[bcrypt]>=1.7`.
  - `jwt.py`: emit/verify JWT (HS256, segredo em `ADMIN_JWT_SECRET`, claims `sub`, `email`, `platform_role`, `iat`, `exp`).
  - `passwords.py`: `hash_password()` e `verify_password()` via `passlib.context.CryptContext(schemes=["bcrypt"])`.
  - `dependencies.py`: `get_current_admin()` FastAPI dep — extrai bearer do header `Authorization`, valida JWT, carrega `admin_users` row via `pool_admin`, falha 401 (sem/JWT inválido) ou 403 (role errada).
- **F2.5** `apps/api/prosauai/api/admin/` (novo router, prefix `/admin`):
  - `POST /admin/auth/login` → body `{email, password}` → valida bcrypt, atualiza `last_login_at`, retorna `{access_token, token_type: "bearer", expires_in, user}`. Rate limit fica fora de escopo (ver riscos).
  - `GET /admin/me` → retorna admin autenticado.
  - `GET /admin/metrics/messages-per-day?days=30` (default 30, max 365) → usa `pool_admin`, retorna `[{date: "YYYY-MM-DD", count: int}]` com **buckets em timezone `America/Sao_Paulo`** e **gap-fill** para dias sem mensagens:
    ```sql
    WITH days AS (
      SELECT generate_series(
        (now() AT TIME ZONE 'America/Sao_Paulo')::date - ($1::int - 1),
        (now() AT TIME ZONE 'America/Sao_Paulo')::date,
        '1 day'::interval
      )::date AS day
    )
    SELECT d.day AS date, COALESCE(COUNT(m.id), 0) AS count
    FROM days d
    LEFT JOIN messages m
      ON (m.created_at AT TIME ZONE 'America/Sao_Paulo')::date = d.day
     AND m.direction = 'inbound'
    GROUP BY d.day
    ORDER BY d.day;
    ```
    (Confirmar se "recebidas" = `direction='inbound'` — conferir enum em migration 004.)
- **F2.6** Testes:
  - Unit: JWT emit/verify (happy path, expirado, assinatura inválida), `hash_password`/`verify_password`.
  - Integração: login OK → 200 com JWT válido; login senha errada → 401; acesso sem token → 401; token com `platform_role` diferente → 403; `/admin/metrics/messages-per-day` retorna shape correto e gap-fill funciona com DB vazio (retorna N linhas com count=0).
  - **RLS smoke test**: conectar como `authenticated` **sem** setar `app.current_tenant_id` → `SELECT FROM messages` retorna 0 linhas (rede de segurança funciona). Conectar como `service_role` → vê todas as linhas sem precisar setar variável.
- **F2.7** `apps/api/prosauai/main.py`: adicionar `CORSMiddleware` com origens vindas de env (`ADMIN_FRONTEND_ORIGIN`, default `http://localhost:3000`). Allow `Authorization`, `Content-Type`. `allow_credentials=True` (necessário para cookies na próxima fase).

**Critério:** `curl -X POST http://localhost:8050/admin/auth/login` retorna JWT; `curl -H "Authorization: Bearer <jwt>" http://localhost:8050/admin/metrics/messages-per-day` retorna array com 30 entradas ordenadas; teste de RLS smoke passa; **pipeline WhatsApp existente continua funcionando** (webhook → insert em `messages` via role `authenticated` com `with_tenant`).

### Fase 3 — Admin frontend (F3)

- **F3.1** Scaffold Next.js (App Router, versão LTS atual — pinar no `package.json`, provavelmente 15.x) em `apps/admin/`: `pnpm create next-app` com TypeScript, Tailwind, ESLint, import alias `@/*`. Configurar `next.config.ts` com `output: 'standalone'` (Dockerfile leve). Criar `app/api/health/route.ts` retornando `NextResponse.json({ok: true})` (usado pelo healthcheck do compose).
- **F3.2** Instalar e inicializar shadcn/ui: `npx shadcn@latest init`. Adicionar componentes: `button`, `input`, `form`, `card`, `table`, `select`, `dropdown-menu`, `avatar`, `toast`, `chart` (wrapper oficial sobre recharts com tokens `--chart-1..5`), `sidebar` (block oficial).
- **F3.3** Instalar: `@tanstack/react-query`, `@tanstack/react-table`, `react-hook-form`, `zod`, `@hookform/resolvers`, `recharts` (dep transitiva do shadcn `chart`), `lucide-react` (ícones).
- **F3.4** `lib/api-client.ts`: fetch wrapper que lê o JWT do **cookie** `prosauai_admin_token` (via `document.cookie` ou helper), injeta `Authorization: Bearer <token>`, intercepta 401 chamando `logout()` (que limpa cookie e redireciona). Consome tipos de `@prosauai/types`. **Decisão de storage:** cookie não-httpOnly, `SameSite=Lax`, `Secure` em prod, `Path=/`, expira junto com o JWT. Motivo: middleware Edge do Next só lê cookies, não localStorage. Migração para httpOnly fica para quando GoTrue entrar.
- **F3.5** `lib/auth.tsx` (Context Provider): armazena `user` + `token`, expõe `useAuth()`, `login(email, pwd)`, `logout()`. `login` grava o cookie e chama `GET /admin/me` para popular `user`. `logout` limpa cookie e redireciona.
- **F3.6** Middleware Next.js (`middleware.ts`): lê cookie `prosauai_admin_token` de `req.cookies`; se ausente em rota `/admin/*` → `NextResponse.redirect('/login')`. **Validação de assinatura** não é feita aqui (Edge runtime não tem o segredo) — apenas presença. A validação real acontece no backend em toda request de dados; token forjado falha no `GET /admin/me` com 401, e o interceptor limpa tudo.
- **F3.7** Página `(auth)/login/page.tsx`: form email/senha com `react-hook-form` + `zod`, chama `POST /admin/auth/login`, salva token, redireciona `/admin`.
- **F3.8** Layout `app/admin/layout.tsx`:
  - Sidebar fixa com item "Dashboard" (resto placeholder).
  - Header com logo, nome do user, botão logout.
  - QueryClientProvider + Toaster.
- **F3.9** Página `app/admin/page.tsx` (dashboard):
  - Seletor de período (7d/30d/90d) — `Select` do shadcn.
  - KPI Card (total no período).
  - Gráfico de linha usando `shadcn Chart` (`ChartContainer` + recharts `LineChart`) com data no X, count no Y. Cores via `--chart-1` para herdar o tema.
  - Fonte de dados: `useQuery(["messages-per-day", days], () => apiClient.get("/admin/metrics/messages-per-day?days="+days))`.
  - Loading skeleton + error state.
- **F3.10** `Dockerfile` para admin (multi-stage build, Node 20 alpine, `output: standalone`).

**Critério:** login funciona, dashboard renderiza gráfico com dados reais do Postgres.

### Fase 4 — Integração e polimento (F4)

- **F4.1** Gerar `packages/types/api.ts` via script e consumir no frontend.
- **F4.2** Adicionar `pnpm generate:types` ao fluxo de dev (doc no README).
- **F4.3** README do `apps/admin/` com setup, comandos, variáveis de ambiente.
- **F4.4** Adicionar `ADMIN_JWT_SECRET`, `DATABASE_URL_ADMIN`, `ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD` no `.env.example`.
- **F4.5** Teste manual end-to-end: `docker compose up` → `localhost:3000` → login → dashboard mostra gráfico.
- **F4.6** CI: ajustar workflow para rodar `pytest` em `apps/api` e `pnpm build` em `apps/admin` (se houver CI ativo).

**Critério:** onboarding de dev novo é `docker compose up` e funciona.

---

## Variáveis de ambiente novas

```bash
# Auth admin
ADMIN_JWT_SECRET=<random 32+ bytes, ex: openssl rand -hex 32>
ADMIN_JWT_EXPIRES_MINUTES=60
ADMIN_BOOTSTRAP_EMAIL=admin@pace.com
ADMIN_BOOTSTRAP_PASSWORD=<strong — trocar imediatamente após primeiro login quando houver endpoint>

# DB dual-pool
# DATABASE_URL existente continua — agora conectando como role "authenticated"
DATABASE_URL=postgresql://authenticated:<senha>@postgres:5432/prosauai
DATABASE_URL_ADMIN=postgresql://service_role:<senha>@postgres:5432/prosauai

# Senhas das roles Postgres (usadas pela migration 010 e pelos pools)
POSTGRES_AUTHENTICATED_PASSWORD=<gerar>
POSTGRES_SERVICE_ROLE_PASSWORD=<gerar>

# CORS
ADMIN_FRONTEND_ORIGIN=http://localhost:3000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8050
```

---

## Fora de escopo (explicitamente)

- CRUD de tenants, conversas, agentes, prompts — próximos epics.
- Rate limiting em `/admin/auth/login` — documentar como follow-up antes de expor publicamente.
- Endpoint de "trocar senha" — trocar senha do admin bootstrap hoje = re-seed via SQL.
- Portal do cliente (fase 2 do roadmap, outro epic).
- Supabase GoTrue — migrar depois; JWT próprio é suficiente para admin interno.
- SSO / magic link / MFA.
- Impersonation — só faz sentido quando houver portal de cliente.
- Custom domains / subdomains por tenant.
- Cache Redis para queries admin — só se medir gargalo.
- Triggers de audit_log — só quando houver mutações. Neste epic tabela fica criada mas sem uso.
- Real-time (SSE/WebSocket) — dashboard é pull simples.
- Observabilidade do frontend (Sentry, etc.).

---

## Notas de integração com o código existente

- **Porta da API é 8050** (não 8000). Definida em [config.py:32](apps/api/prosauai/config.py#L32). Todas as URLs do epic já refletem isso.
- **Variável RLS é `app.current_tenant_id`** (não `app.tenant_id`). Helper existente em [migrations/001_create_schema.sql](migrations/001_create_schema.sql): `public.tenant_id()`. Todas as policies (002–008) já usam esse helper — nada a reescrever.
- **`with_tenant` context manager** em [pool.py:103-143](apps/api/prosauai/db/pool.py#L103-L143) usa `set_config('app.current_tenant_id', $1, true)` dentro de transação. F2.3 **não** precisa reescrever — só duplica o pattern em pool_admin (sem set_config).
- **Pipeline WhatsApp vivo** usa o pool existente via `app.state.pg_pool` em [main.py:140-141](apps/api/prosauai/main.py#L140-L141). Após F2.3, este pool passa a ser `pool_tenant` conectando como `authenticated`. Call sites em `conversation/customer.py`, `conversation/context.py`, `conversation/agent.py` precisam ser auditados (F0.2) — qualquer `pool.acquire()` cru sem `with_tenant` quebra.
- **`config/tenants.yaml`** é source of truth operacional (Evolution credentials, mention keywords). **`tenants`** (tabela DB, migration 008) é só registry de identidade (slug↔uuid). Este epic lê apenas `messages` — sem conflito. Uma futura tela "editar tenant" precisará decidir a fonte da verdade (provavelmente migrar YAML → DB).
- **Migrations rodam via `docker-entrypoint-initdb.d`** (compose linha 59) — **só na primeira init do volume**. Para aplicar 010 em ambiente existente, rodar manualmente (ver F2.2).
- **`tenants` policy `tenants_read_all`** (migration 008) permite SELECT para qualquer role. Intencional: tenants são metadata compartilhada. Admin lê via `service_role` normalmente; se um futuro endpoint de cliente listar tenants, receberá todos — precisará de filtro em código ou policy adicional em outro epic.

---

## Riscos e pontos de atenção

- **Mover código para `apps/api/`** quebra imports e CI. Fazer em PR isolado antes do restante do epic, com testes rodando verdes.
- **`FORCE ROW LEVEL SECURITY` muda o comportamento do pipeline existente** — hoje o role `prosauai` (superuser/owner) provavelmente bypassa RLS. Depois da 010, o app precisa setar `app.current_tenant_id` em **todo** call site ou inserts/selects quebram. F0.2 previne; testes de integração do webhook após F2.3 confirmam.
- **Dois roles Postgres** precisam de `GRANT` explícito em cada tabela existente. Auditar migração `010` com `\dp` no psql antes de mergear.
- **JWT simples (sem refresh)**: aceitar por enquanto; session de 1h reloga. Migrar para GoTrue quando portal cliente entrar.
- **Cookie não-httpOnly**: vulnerável a XSS. Mitigação nesta fase: escopo restrito (admin interno ~3 usuários, dev/Tailscale), CSP estrita no Next.js, dependências auditadas. Migrar para httpOnly + refresh token com GoTrue.
- **Sem rate limit em `/admin/auth/login`**: risco de brute force. Em dev/Tailscale é aceitável; antes de expor publicamente, adicionar `slowapi` ou Redis-based limiter (5 tentativas/min por IP+email).
- **Timezone hardcoded `America/Sao_Paulo`**: aceitável para este epic (Pace opera no Brasil). Se adicionar tenants internacionais, parametrizar via setting ou preferência do usuário admin.
- **Gráficos via shadcn Chart (recharts)**: escolhido para manter **tokens únicos** do shadcn (sem dois design systems convivendo). Tremor foi avaliado e descartado — paleta própria (`tremor-*` / cores Tailwind cruas) conflita com as CSS vars semânticas do shadcn. Se no futuro precisar de gráficos pesados (candlestick, heatmap, spark cards com delta), avaliar copiar **componentes pontuais** do Tremor Raw reescrevendo os tokens para `--chart-*`, ou adotar visx.
- **Bootstrap do admin por env var**: aceitável para MVP self-hosted. Documentar claramente que trocar senha exige re-seed ou endpoint futuro.
- **Sem ferramenta de migration real**: repo depende de `docker-entrypoint-initdb.d` hoje. Funciona para green-field, mas ambientes com volume existente precisam `psql -f` manual. Adotar Alembic/`yoyo-migrations`/`dbmate` é follow-up recomendado antes de deploy em produção com dados reais.
- **Dashboard requer dados**: `messages` pode estar vazia em dev novo. Documentar no README que o gráfico aparece vazio (gap-fill mostra 0) até o pipeline WhatsApp processar mensagens reais, ou criar um `scripts/seed_messages_demo.py` para popular com fake data.
- **Timezone na imagem Postgres**: `postgres:15-alpine` já inclui `tzdata`. `AT TIME ZONE 'America/Sao_Paulo'` funciona sem setup adicional.

---

## Ordem recomendada de PRs

0. PR 0: F0 (pré-voo) — ADR/nota documentando owner das tabelas, audit de call sites, decisão pnpm, deps novas.
1. PR 1: F1.1 (mover código para `apps/api/`) + CI verde.
2. PR 2: F1.2–F1.5 (monorepo pnpm, `packages/types`, compose com admin + override dev).
3. PR 3: F2.1–F2.3 (migração 010/011 com FORCE RLS + dois pools + bootstrap admin). **Testes do pipeline existente devem passar** após troca de role.
4. PR 4: F2.4–F2.7 (auth + endpoints admin + CORS + testes).
5. PR 5: F3.1–F3.6 (scaffold admin + auth frontend com cookie).
6. PR 6: F3.7–F3.10 (telas de login e dashboard).
7. PR 7: F4 (polish + docs).

Cada PR é mergeável de forma independente e deixa o sistema em estado funcional.
