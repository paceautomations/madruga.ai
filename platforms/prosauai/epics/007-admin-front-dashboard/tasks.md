# Tasks: Admin Front — Dashboard Inicial

**Input**: Design documents from `platforms/prosauai/epics/007-admin-front-dashboard/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/admin-api.md, quickstart.md
**Branch**: `epic/prosauai/007-admin-front-dashboard`

**Tests**: Incluídos — constitution (Princípio VII TDD) exige testes. RLS smoke test é gate crítico (plan.md).

**Organization**: Tasks organizadas por fases do plan.md, mapeadas às user stories do spec.md.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências)
- **[Story]**: User story associada (US1=Login, US2=Dashboard, US3=Monorepo, US4=Bootstrap, US5=Health)

## Path Conventions

- **Backend**: `apps/api/prosauai/` (FastAPI, movida da raiz)
- **Frontend**: `apps/admin/src/` (Next.js 15 App Router)
- **Types**: `packages/types/` (@prosauai/types)
- **Migrations**: `apps/api/db/migrations/` (dbmate)
- **Tests backend**: `apps/api/tests/` (pytest)
- **Tests frontend**: `apps/admin/` (vitest)
- **Config raiz**: `pnpm-workspace.yaml`, `docker-compose.yml`, `.env.example`

---

## Phase 1: Setup — Monorepo + dbmate (F0 + F1)

**Purpose**: Reorganizar repositório em monorepo pnpm e integrar dbmate. Sem alteração funcional.

**Maps to**: User Story 3 (Reestruturação em Monorepo — P1)

- [x] T001 [US3] Instalar e configurar dbmate: criar `dbmate.yml` na raiz do repo com `DATABASE_URL`, diretório de migrations em `apps/api/db/migrations/`, e tabela `schema_migrations`
- [x] T002 [US3] Converter migrations existentes (001-008) de `docker-entrypoint-initdb.d/` para formato dbmate em `apps/api/db/migrations/` (YYYYMMDDHHMMSS_name.sql com seções `-- migrate:up` e `-- migrate:down`)
- [x] T003 [US3] Mover código existente para `apps/api/`: mover `prosauai/`, `tests/`, `tools/`, `config/`, `Dockerfile`, `pyproject.toml` para `apps/api/`
- [x] T004 [US3] Atualizar imports e referências após mover para `apps/api/`: ajustar `pyproject.toml` (paths, entry points), imports internos, `Dockerfile` (WORKDIR, COPY paths), CI config
- [x] T005 [US3] Criar `pnpm-workspace.yaml` na raiz com `apps/*` e `packages/*`
- [x] T006 [P] [US3] Scaffold `apps/admin/` com Next.js 15 App Router: `pnpm create next-app apps/admin` com TypeScript, Tailwind, App Router, src/ directory
- [x] T007 [P] [US3] Criar `packages/types/` com `package.json` (@prosauai/types), `tsconfig.json`, e arquivo placeholder `api.ts`
- [x] T008 [US3] Atualizar `docker-compose.yml`: alterar context da API para `./apps/api`, adicionar service `migrate` (dbmate up), adicionar service `admin` (Next.js), configurar `depends_on` com condition `service_healthy`
- [x] T009 [US3] Criar `docker-compose.override.yml` para dev: volumes para hot reload (API + Admin), port mappings (API:8050, Admin:3000), env vars de desenvolvimento
- [x] T010 [US3] Criar `.env.example` na raiz do monorepo com todas as variáveis: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD`, `ADMIN_FRONTEND_ORIGIN`, `NEXT_PUBLIC_API_URL`

**Checkpoint**: Monorepo funcional. `docker compose up` sobe API + Redis + Postgres. `dbmate up` aplica migrations existentes. Next.js scaffold inicia em localhost:3000. Todos os testes do pipeline (001-005) passam sem regressão.

---

## Phase 2: Foundational — DB Roles + Pools + Tabelas Admin (F2.1–F2.3)

**Purpose**: Infraestrutura de banco (roles, tabelas admin, índice) e separação de pools asyncpg. BLOQUEIA todas as user stories de auth e dashboard.

**⚠️ CRITICAL**: Nenhuma user story de auth/dashboard pode começar até esta fase estar completa.

- [x] T011 Criar migration dbmate `20260415000001_create_roles_and_grants.sql` em `apps/api/db/migrations/`: criar roles `app_owner` (NOLOGIN NOSUPERUSER), `authenticated` (LOGIN NOSUPERUSER), `service_role` (LOGIN BYPASSRLS); `ALTER TABLE ... OWNER TO app_owner` para tabelas existentes; `FORCE ROW LEVEL SECURITY` em tabelas de negócio; GRANTs via `ALTER DEFAULT PRIVILEGES`
- [x] T012 Criar migration dbmate `20260415000002_create_admin_users.sql` em `apps/api/db/migrations/`: tabela `admin_users` conforme data-model.md (id UUID PK, email UNIQUE, password_hash, is_active, created_at, last_login_at), índice `idx_admin_users_email`, owner `app_owner`, GRANTs para `service_role` (SELECT, INSERT, UPDATE)
- [x] T013 [P] Criar migration dbmate `20260415000003_create_audit_log.sql` em `apps/api/db/migrations/`: tabela `audit_log` conforme data-model.md (id UUID PK, action VARCHAR(50), actor_id FK, ip_address INET, details JSONB, created_at), índices (`idx_audit_log_created_at`, `idx_audit_log_action`), owner `app_owner`, GRANTs para `service_role` (SELECT, INSERT)
- [x] T014 [P] Criar migration dbmate `20260415000004_create_idx_messages_created_at.sql` em `apps/api/db/migrations/`: `CREATE INDEX CONCURRENTLY idx_messages_created_at ON messages(created_at DESC)`
- [x] T015 Refatorar `apps/api/prosauai/pool.py`: split em dual pool — `pool_tenant` (role `authenticated`, RLS enforced, min_size=2, max_size=10) + `pool_admin` (role `service_role`, BYPASSRLS, min_size=1, max_size=5). Ambos com `statement_cache_size=0`. Atualizar lifespan da FastAPI para criar/fechar ambos os pools
- [x] T016 Atualizar call sites existentes em `apps/api/prosauai/` para usar `pool_tenant` explicitamente (rg "pool\.(acquire|execute|fetch)" para inventário). Pipeline WhatsApp DEVE continuar usando pool com RLS enforced
- [x] T017 Escrever teste de integração RLS smoke em `apps/api/tests/integration/test_rls_isolation.py`: verificar que `authenticated` sem `SET LOCAL` retorna 0 rows; verificar que `service_role` vê tudo; verificar `FORCE ROW LEVEL SECURITY` ativo

**Checkpoint**: Roles criadas, tabelas admin existem, dual pool funcional. RLS smoke test PASSA. Pipeline WhatsApp inteiro funcional com pool_tenant.

---

## Phase 3: User Story 1 — Login no Painel Admin (Priority: P1) 🎯 MVP

**Goal**: Administrador faz login seguro no painel admin via email/senha, recebe cookie JWT, é redirecionado ao dashboard. Rate limiting protege contra brute force.

**Independent Test**: Acessar `/admin/login`, inserir credenciais válidas, verificar redirecionamento ao dashboard. Credenciais inválidas mostram erro genérico. 6ª tentativa em 1 min retorna 429.

### Tests for User Story 1

- [x] T018 [P] [US1] Escrever teste unitário de JWT em `apps/api/tests/unit/test_jwt.py`: create_token retorna JWT válido com sub/email/exp/iat; verify_token decodifica corretamente; token expirado levanta exceção; token com secret errado levanta exceção
- [x] T019 [P] [US1] Escrever teste unitário de passwords em `apps/api/tests/unit/test_passwords.py`: hash_password retorna hash bcrypt; verify_password aceita senha correta; verify_password rejeita senha incorreta
- [x] T020 [P] [US1] Escrever teste de integração auth em `apps/api/tests/integration/test_auth_routes.py`: POST /admin/auth/login com credenciais válidas retorna 200 + cookie; POST com credenciais inválidas retorna 401; POST /admin/auth/logout retorna 200 e remove cookie; GET /admin/auth/me com cookie válido retorna admin; GET /admin/auth/me sem cookie retorna 401; rate limit retorna 429 após 5 tentativas

### Implementation for User Story 1

- [x] T021 [P] [US1] Implementar módulo JWT em `apps/api/prosauai/auth/jwt.py`: funções `create_access_token(admin_id, email)` e `verify_access_token(token)` usando PyJWT HS256, secret via `JWT_SECRET` env, expiração 24h
- [x] T022 [P] [US1] Implementar módulo passwords em `apps/api/prosauai/auth/passwords.py`: funções `hash_password(plain)` e `verify_password(plain, hashed)` usando passlib bcrypt
- [x] T023 [US1] Implementar dependencies em `apps/api/prosauai/auth/dependencies.py`: FastAPI `Depends(get_current_admin)` que extrai cookie `admin_token`, verifica JWT, busca admin no `pool_admin`, retorna dados do admin ou 401
- [x] T024 [US1] Implementar rotas de auth em `apps/api/prosauai/admin/auth_routes.py`: `POST /admin/auth/login` (valida credenciais, emite cookie JWT, registra audit_log login_success/login_failed), `POST /admin/auth/logout` (remove cookie, registra audit_log logout), `GET /admin/auth/me` (retorna admin autenticado)
- [x] T025 [US1] Configurar rate limiting com slowapi em `apps/api/prosauai/admin/auth_routes.py`: limiter com Redis backend, 5/min por IP+email no endpoint login, registrar `rate_limit_hit` no audit_log quando atingido
- [x] T026 [US1] Configurar CORS em `apps/api/prosauai/main.py`: adicionar `CORSMiddleware` com `origins=[ADMIN_FRONTEND_ORIGIN]`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`
- [x] T027 [US1] Criar router admin em `apps/api/prosauai/admin/router.py`: registrar `auth_routes` e `metrics_routes` com prefix `/admin`, incluir no app FastAPI em `main.py`
- [x] T028 [US1] Adicionar settings de auth em `apps/api/prosauai/config.py`: `JWT_SECRET`, `ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD`, `ADMIN_FRONTEND_ORIGIN` via pydantic-settings

**Checkpoint**: Login/logout funcional via API. Rate limiting ativo. Audit log registra eventos. Testes unitários e integração passam.

---

## Phase 4: User Story 4 — Bootstrap do Primeiro Administrador (Priority: P2)

**Goal**: Na primeira inicialização, criar admin automaticamente via env vars sem depender de interface.

**Independent Test**: Iniciar sistema com `ADMIN_BOOTSTRAP_EMAIL`/`PASSWORD` configurados, verificar que admin é criado. Reiniciar — sem duplicatas.

- [x] T029 [US4] Implementar bootstrap em `apps/api/prosauai/auth/bootstrap.py`: função `bootstrap_admin(pool_admin)` que verifica se `admin_users` está vazia, lê env vars `ADMIN_BOOTSTRAP_EMAIL`/`PASSWORD`, valida senha (8+ chars), cria admin com hash bcrypt. Idempotente — ignora se admin existe
- [x] T030 [US4] Integrar bootstrap no lifespan da FastAPI em `apps/api/prosauai/main.py`: chamar `bootstrap_admin(pool_admin)` após criação dos pools no startup. Log info se criou, debug se já existia
- [x] T031 [US4] Escrever teste de integração bootstrap em `apps/api/tests/integration/test_bootstrap.py`: bootstrap cria admin quando tabela vazia; bootstrap ignora quando admin existe; bootstrap sem env vars não cria nem falha; bootstrap com senha < 8 chars loga warning e não cria

**Checkpoint**: Admin bootstrap funcional e idempotente. Testes passam.

---

## Phase 5: User Story 5 — Endpoint de Health Check (Priority: P2)

**Goal**: API expõe `/health` para docker-compose e monitoramento verificarem que está operacional.

**Independent Test**: GET /health retorna 200 com status de DB + Redis quando tudo OK, 503 quando algo falha.

- [x] T032 [P] [US5] Implementar health check em `apps/api/prosauai/health.py`: endpoint `GET /health` que verifica conexão DB (SELECT 1 via pool_admin) e Redis (PING), retorna JSON `{status, checks: {database, redis}, version}`, HTTP 200 se tudo ok, 503 se algo falhar
- [x] T033 [P] [US5] Escrever teste de integração health em `apps/api/tests/integration/test_health.py`: /health retorna 200 quando DB+Redis ok; /health retorna 503 com detail quando DB falha; /health retorna 503 com detail quando Redis falha
- [x] T034 [US5] Registrar router de health em `apps/api/prosauai/main.py` e atualizar healthcheck do docker-compose para usar `GET /health`

**Checkpoint**: Health check funcional. Docker-compose usa para `depends_on` condition.

---

## Phase 6: User Story 2 — Dashboard com Volume de Mensagens (Priority: P1)

**Goal**: Admin autenticado acessa `/admin` e vê gráfico de barras com mensagens/dia (30d) + KPI total. Cross-tenant.

**Independent Test**: Login → dashboard exibe gráfico com dados reais (ou zeros). Dias sem mensagens aparecem com barra zero. Loading state visível. Error state com retry.

### Tests for User Story 2

- [x] T035 [P] [US2] Escrever teste de integração metrics em `apps/api/tests/integration/test_metrics_routes.py`: GET /admin/metrics/messages-per-day retorna 200 com 30 dias; retorna gap-fill (dias sem mensagens = 0); retorna total correto; requer auth (401 sem cookie); parâmetro days funciona (max 90)

### Implementation for User Story 2 — Backend

- [x] T036 [US2] Implementar endpoint metrics em `apps/api/prosauai/admin/metrics_routes.py`: `GET /admin/metrics/messages-per-day` com query param `days` (default 30, max 90), query SQL com `generate_series` gap-fill + `GROUP BY date AT TIME ZONE 'America/Sao_Paulo'` via `pool_admin`, retorna JSON conforme contrato (`period`, `total`, `daily[]`)

### Implementation for User Story 2 — Frontend Base

- [x] T037 [US2] Inicializar shadcn/ui em `apps/admin/`: rodar `pnpm dlx shadcn@latest init`, configurar tailwind.config.ts com tokens, instalar componentes: Button, Input, Card, Skeleton, Alert
- [x] T038 [US2] Instalar componente shadcn Chart em `apps/admin/`: `pnpm dlx shadcn@latest add chart` (wrapper recharts), configurar tokens `--chart-1..5` em `globals.css`
- [x] T039 [US2] Implementar API client em `apps/admin/src/lib/api-client.ts`: fetch wrapper com `credentials: 'include'` (enviar cookie), base URL via `NEXT_PUBLIC_API_URL` (default `http://localhost:8050`), error handling genérico
- [x] T040 [US2] Implementar AuthProvider em `apps/admin/src/lib/auth.tsx`: React context com `useAuth()` hook (login, logout, user, isAuthenticated), chama `/admin/auth/login`, `/admin/auth/logout`, `/admin/auth/me`
- [x] T041 [US2] Implementar Edge middleware em `apps/admin/middleware.ts`: validar presença + não-expiração do cookie `admin_token`, redirecionar para `/admin/login` se ausente/expirado, matcher exclui `/admin/login`

### Implementation for User Story 2 — Login Page

- [x] T042 [US2] Implementar página de login em `apps/admin/src/app/admin/login/page.tsx`: formulário email + senha com react-hook-form + zod validation, chama `useAuth().login()`, redireciona para `/admin` após sucesso, exibe mensagem de erro genérica ("Credenciais inválidas") em caso de falha, exibe mensagem de rate limit (429)
- [x] T043 [US2] Implementar componente LoginForm em `apps/admin/src/components/auth/login-form.tsx`: inputs email/senha com shadcn Input, botão submit com shadcn Button, loading state durante request, error state com shadcn Alert

### Implementation for User Story 2 — Dashboard Page

- [x] T044 [US2] Implementar layout admin em `apps/admin/src/app/admin/layout.tsx`: sidebar (navegação futura — links placeholder) + header (email do admin via `useAuth()`, botão logout)
- [x] T045 [P] [US2] Implementar componente Sidebar em `apps/admin/src/components/layout/sidebar.tsx`: navegação lateral com link ativo para Dashboard, placeholder para telas futuras (Tenants, Conversas)
- [x] T046 [P] [US2] Implementar componente Header em `apps/admin/src/components/layout/header.tsx`: exibe email do admin, botão logout que chama `useAuth().logout()`
- [x] T047 [US2] Implementar hook `useMessagesPerDay` em `apps/admin/src/hooks/use-messages-per-day.ts`: TanStack Query hook que chama `GET /admin/metrics/messages-per-day`, retorna `{data, isLoading, isError, refetch}`
- [x] T048 [P] [US2] Implementar componente KPI Card em `apps/admin/src/components/dashboard/kpi-card.tsx`: shadcn Card exibindo total de mensagens no período, loading state com Skeleton, formatar número com separador de milhar
- [x] T049 [P] [US2] Implementar componente MessageVolumeChart em `apps/admin/src/components/dashboard/message-volume-chart.tsx`: shadcn Chart (BarChart recharts) com dados diários, XAxis com datas formatadas, YAxis com contagem, tooltip com detalhes, cor via `--chart-1` token
- [x] T050 [US2] Implementar página dashboard em `apps/admin/src/app/admin/page.tsx`: usar `useMessagesPerDay` hook, renderizar KPI Card + MessageVolumeChart, loading state (Skeletons) enquanto carrega, error state com Alert + botão retry
- [x] T051 [US2] Implementar root layout em `apps/admin/src/app/layout.tsx`: providers (AuthProvider, QueryClientProvider do TanStack Query), Tailwind globals, metadata

**Checkpoint**: Login end-to-end funcional. Dashboard exibe gráfico + KPI com dados reais. Gap-fill visual. Loading/error states. Testes integração backend passam.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Finalização, Docker, tipos compartilhados, documentação.

- [x] T052 [P] Criar Dockerfile standalone para Next.js em `apps/admin/Dockerfile`: multi-stage build (deps → build → standalone), output standalone, porta 3000
- [x] T053 [P] Gerar tipos TypeScript do OpenAPI em `packages/types/api.ts`: script `export_openapi.py` em `packages/types/` que exporta schema FastAPI, `openapi-typescript` gera tipos TS, adicionar script `generate` no `package.json`
- [x] T054 [P] Atualizar `apps/api/.env.example` e `apps/admin/.env.example` com todas as variáveis necessárias, documentadas com comentários
- [x] T055 Validar setup completo via quickstart.md: `docker compose up --build` sobe tudo (API + Admin + Postgres + Redis + migrate), login funciona, dashboard exibe dados
- [x] T056 Rodar suite completa de testes do pipeline existente (001-005) para confirmar zero regressões após todas as mudanças

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup/Monorepo)**: Sem dependências — iniciar imediatamente
- **Phase 2 (Foundational/DB)**: Depende de Phase 1 (monorepo estruturado) — BLOQUEIA phases 3-6
- **Phase 3 (US1 Login Backend)**: Depende de Phase 2 (pools + tabelas admin)
- **Phase 4 (US4 Bootstrap)**: Depende de Phase 2 (tabela admin_users) + Phase 3 (módulo passwords)
- **Phase 5 (US5 Health)**: Depende de Phase 2 (dual pool) — pode rodar em PARALELO com Phase 3
- **Phase 6 (US2 Dashboard)**: Depende de Phase 3 (auth backend para login) + Phase 1 (Next.js scaffold)
- **Phase 7 (Polish)**: Depende de todas as phases anteriores

### User Story Dependencies

```
Phase 1 (Monorepo) ──┬── Phase 2 (DB/Pools) ──┬── Phase 3 (US1: Login Backend) ── Phase 4 (US4: Bootstrap)
                      │                         │                                        │
                      │                         ├── Phase 5 (US5: Health) [PARALLEL]      │
                      │                         │                                        │
                      │                         └── Phase 6 (US2: Dashboard) ─────────────┘
                      │                                                                    │
                      └────────────────────────────────────────────────────────── Phase 7 (Polish)
```

- **US3 (Monorepo)**: Phase 1 inteira
- **US1 (Login)**: Phase 3 (backend auth) + Phase 6 parcial (frontend login)
- **US2 (Dashboard)**: Phase 6 (frontend dashboard + backend metrics)
- **US4 (Bootstrap)**: Phase 4
- **US5 (Health)**: Phase 5

### Within Each Phase

- Tests DEVEM ser escritos ANTES da implementação (TDD — Constitution VII)
- Models/migrations antes de services
- Services antes de endpoints
- Backend antes de frontend (para a mesma funcionalidade)
- Core implementation antes de integração

### Parallel Opportunities

- **Phase 1**: T006 e T007 podem rodar em paralelo (scaffold admin + types package)
- **Phase 2**: T013 e T014 podem rodar em paralelo (audit_log + índice messages)
- **Phase 3**: T018, T019, T020 (testes) em paralelo; T021, T022 (jwt + passwords) em paralelo
- **Phase 5**: TODA a phase pode rodar em paralelo com Phase 3/4
- **Phase 6**: T045, T046 (sidebar + header) em paralelo; T048, T049 (KPI + chart) em paralelo
- **Phase 7**: T052, T053, T054 em paralelo

---

## Parallel Example: Phase 3 (Login)

```bash
# Testes em paralelo (TDD — escrever ANTES):
Task T018: "Teste unitário JWT em apps/api/tests/unit/test_jwt.py"
Task T019: "Teste unitário passwords em apps/api/tests/unit/test_passwords.py"
Task T020: "Teste integração auth em apps/api/tests/integration/test_auth_routes.py"

# Implementação core em paralelo:
Task T021: "Módulo JWT em apps/api/prosauai/auth/jwt.py"
Task T022: "Módulo passwords em apps/api/prosauai/auth/passwords.py"

# Sequencial (depende de T021+T022):
Task T023: "Dependencies em apps/api/prosauai/auth/dependencies.py"
Task T024: "Rotas auth em apps/api/prosauai/admin/auth_routes.py"
Task T025: "Rate limiting em apps/api/prosauai/admin/auth_routes.py"
```

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3 + 6 parcial)

1. Complete Phase 1: Monorepo + dbmate → repo reorganizado
2. Complete Phase 2: DB roles + pools → infraestrutura pronta
3. Complete Phase 3: Login backend → auth funcional via API
4. Complete Phase 6: Frontend login + dashboard → **valor tangível**
5. **STOP and VALIDATE**: Login end-to-end + dashboard com gráfico = MVP entregue

### Incremental Delivery

1. Phase 1 → Monorepo funcional, pipeline não regride
2. Phase 2 → DB hardened, dual pools, RLS smoke passa
3. Phase 3 → Login API funcional (pode testar via curl)
4. Phase 4 → Bootstrap funcional (primeiro admin sem SQL manual)
5. Phase 5 → Health check para docker-compose
6. Phase 6 → Frontend completo = epic entregue
7. Phase 7 → Polish, Docker prod, tipos compartilhados

### Circuit Breaker (do pitch)

Se estourar 3 semanas: **cortar gráfico de barras (T049, T050 parcial) e entregar só KPI card**. Tasks T048 (KPI Card) e T042-T044 (login + layout) são suficientes para MVP mínimo.

---

## Summary

| Métrica | Valor |
|---------|-------|
| Total de tasks | 56 |
| Phase 1 (Monorepo/Setup) | 10 tasks |
| Phase 2 (Foundational/DB) | 7 tasks |
| Phase 3 (US1 Login) | 11 tasks |
| Phase 4 (US4 Bootstrap) | 3 tasks |
| Phase 5 (US5 Health) | 3 tasks |
| Phase 6 (US2 Dashboard) | 17 tasks |
| Phase 7 (Polish) | 5 tasks |
| Tasks paralelizáveis | 22 marcadas [P] |
| User stories cobertas | 5/5 (US1-US5) |

---
handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "56 tasks em 7 fases sequenciais cobrindo 5 user stories. MVP = Phases 1-3+6 (monorepo + DB + auth + dashboard). Circuit breaker: cortar gráfico se >3 semanas. RLS smoke test é gate de Phase 2. Pipeline WhatsApp regressão testada em T056."
  blockers: []
  confidence: Alta
  kill_criteria: "Se o pipeline WhatsApp (001-005) regredir após reestruturação monorepo (Phase 1) ou troca de roles (Phase 2), o epic precisa ser pausado e o dano revertido."
