# Implementation Plan: Admin Front — Dashboard Inicial

**Branch**: `epic/prosauai/007-admin-front-dashboard` | **Date**: 2026-04-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification de `spec.md` — fundação do painel admin com autenticação, monorepo e dashboard de mensagens.

## Summary

Este epic cria a fundação completa do painel administrativo do ProsaUAI: reestruturação do repositório em monorepo pnpm (`apps/api`, `apps/admin`, `packages/types`), backend admin na FastAPI existente (JWT HS256, dual asyncpg pools, rate limiting, health check), e frontend Next.js 15 com shadcn/ui exibindo dashboard de mensagens recebidas por dia. Implementação em 4 fases sequenciais, cada uma deixando o sistema funcional.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript/Node.js 20+ (frontend)
**Primary Dependencies**: FastAPI >=0.115, asyncpg >=0.30, PyJWT, passlib[bcrypt], slowapi (backend); Next.js 15, shadcn/ui, TanStack Query, recharts (frontend); dbmate (migrations); pnpm (monorepo)
**Storage**: PostgreSQL 15 (Supabase) com RLS, Redis 7 (rate limiting)
**Testing**: pytest (backend), vitest + testing-library (frontend)
**Target Platform**: Linux server (Docker Compose), desktop browser (admin panel)
**Project Type**: Web application (monorepo: API + admin frontend)
**Performance Goals**: Dashboard load < 3s, login flow < 10s total, health check < 1s
**Constraints**: Pipeline WhatsApp (epics 001-005) DEVE continuar funcional sem regressões. ~3 usuários admin em Tailscale.
**Scale/Scope**: ~3 admin users, ~365K mensagens/ano, 30 dias de dashboard

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Princípio | Status | Verificação |
|---|-----------|--------|-------------|
| I | Pragmatism Above All | ✅ PASS | JWT HS256 local é a solução mais simples para ~3 usuários. Sem overengineering (GoTrue adiado). |
| II | Automate Repetitive Tasks | ✅ PASS | dbmate automatiza migrations. Bootstrap via env vars automatiza primeiro admin. |
| III | Structured Knowledge | ✅ PASS | Monorepo organizado. Types compartilhados via pacote. |
| IV | Fast Action Over Excessive Planning | ✅ PASS | 4 fases incrementais, cada uma shippable. Circuit breaker: cortar gráfico e entregar só KPI se estourar prazo. |
| V | Alternatives and Trade-offs | ✅ PASS | Pesquisa documenta alternativas para auth, schema, migration tool, API pattern. |
| VI | Brutal Honesty | ✅ PASS | ADR-024 drift reconhecido abertamente. Cookie não-httpOnly com justificativa explícita. |
| VII | TDD | ✅ PASS | RLS smoke test como gate do PR 3. Testes de integração para auth. Testes e2e para dashboard. |
| VIII | Collaborative Decision Making | ✅ PASS | 18 decisões capturadas no epic-context com rationale. |
| IX | Observability and Logging | ✅ PASS | structlog existente. audit_log para eventos de auth. Health check para monitoramento. |

**Nenhuma violação identificada.** Complexidade tracking vazio — nenhuma justificativa necessária.

## Project Structure

### Documentation (this feature)

```text
platforms/prosauai/epics/007-admin-front-dashboard/
├── pitch.md             # Epic context (input)
├── spec.md              # Feature specification (input)
├── plan.md              # This file
├── research.md          # Phase 0 output — pesquisa técnica
├── data-model.md        # Phase 1 output — modelo de dados
├── quickstart.md        # Phase 1 output — setup local
├── contracts/
│   └── admin-api.md     # Phase 1 output — contrato da API admin
├── decisions.md         # Cross-cutting — log de decisões
└── tasks.md             # Phase 2 output (speckit.tasks)
```

### Source Code (repository — prosauai)

```text
prosauai/                          # Repositório paceautomations/prosauai
├── apps/
│   ├── api/                       # FastAPI existente (movida da raiz)
│   │   ├── prosauai/
│   │   │   ├── main.py            # App FastAPI + lifespan
│   │   │   ├── config.py          # Settings (pydantic-settings)
│   │   │   ├── pool.py            # Dual pool: pool_tenant + pool_admin
│   │   │   ├── auth/              # NOVO: módulo de autenticação
│   │   │   │   ├── __init__.py
│   │   │   │   ├── jwt.py         # Criação/validação JWT HS256
│   │   │   │   ├── passwords.py   # Hash/verify bcrypt (passlib)
│   │   │   │   ├── dependencies.py # FastAPI Depends(get_current_admin)
│   │   │   │   └── bootstrap.py   # Admin bootstrap via env vars
│   │   │   ├── admin/             # NOVO: rotas admin
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py      # APIRouter prefix="/admin"
│   │   │   │   ├── auth_routes.py # login, logout, me
│   │   │   │   └── metrics_routes.py # messages-per-day
│   │   │   ├── health.py          # NOVO: endpoint /health
│   │   │   └── ...                # Módulos existentes (pipeline WhatsApp)
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   │   ├── test_jwt.py
│   │   │   │   └── test_passwords.py
│   │   │   ├── integration/
│   │   │   │   ├── test_auth_routes.py
│   │   │   │   ├── test_metrics_routes.py
│   │   │   │   ├── test_rls_isolation.py  # CRÍTICO: smoke test RLS
│   │   │   │   └── test_health.py
│   │   │   └── ...                # Testes existentes do pipeline
│   │   ├── db/
│   │   │   └── migrations/        # NOVO: dbmate migrations
│   │   │       ├── 20260415000001_create_roles_and_grants.sql
│   │   │       ├── 20260415000002_create_admin_users.sql
│   │   │       ├── 20260415000003_create_audit_log.sql
│   │   │       └── 20260415000004_create_idx_messages_created_at.sql
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   └── .env.example
│   └── admin/                     # NOVO: Next.js 15 App Router
│       ├── src/
│       │   ├── app/
│       │   │   ├── layout.tsx     # Root layout (Tailwind, providers)
│       │   │   └── admin/
│       │   │       ├── layout.tsx  # Admin layout (sidebar + header)
│       │   │       ├── page.tsx    # Dashboard (gráfico + KPI)
│       │   │       └── login/
│       │   │           └── page.tsx # Login page
│       │   ├── components/
│       │   │   ├── ui/            # shadcn/ui components
│       │   │   ├── dashboard/
│       │   │   │   ├── message-volume-chart.tsx
│       │   │   │   └── kpi-card.tsx
│       │   │   ├── auth/
│       │   │   │   └── login-form.tsx
│       │   │   └── layout/
│       │   │       ├── sidebar.tsx
│       │   │       └── header.tsx
│       │   ├── lib/
│       │   │   ├── api-client.ts  # Fetch wrapper com credentials
│       │   │   └── auth.tsx       # AuthProvider + useAuth hook
│       │   └── hooks/
│       │       └── use-messages-per-day.ts  # TanStack Query hook
│       ├── middleware.ts           # Auth cookie validation (Edge)
│       ├── next.config.ts
│       ├── tailwind.config.ts
│       ├── tsconfig.json
│       ├── package.json
│       └── Dockerfile
├── packages/
│   └── types/                     # NOVO: @prosauai/types
│       ├── api.ts                 # Generated from OpenAPI
│       ├── package.json
│       └── tsconfig.json
├── pnpm-workspace.yaml
├── docker-compose.yml             # Atualizado: monorepo context
├── docker-compose.override.yml    # Dev: volumes, port overrides
├── dbmate.yml                     # NOVO: dbmate config
└── .env.example                   # NOVO: root-level env template
```

**Structure Decision**: Monorepo pnpm com `apps/api` (FastAPI existente migrada da raiz) + `apps/admin` (Next.js 15 novo) + `packages/types` (tipos TS gerados do OpenAPI). Decisão #2 do epic-context. Docker Compose na raiz orquestra todos os serviços.

## Complexity Tracking

> Nenhuma violação da Constitution. Tabela vazia — todas as decisões são justificadas sem exceções.

## Phase 0: Research — Consolidado

**Status**: ✅ Completo — ver `research.md`

Resumo das pesquisas:
1. **Auth divergência**: JWT HS256 via FastAPI escolhido sobre Supabase Auth (overengineering) e X-Admin-Token (sem identidade). Documentado em `research.md §1.1`.
2. **Schema location**: `public` sobre `admin` schema (ADR-024 drift). Documentado em `research.md §1.2`.
3. **dbmate**: Escolhido sobre Alembic (requer SQLAlchemy), Flyway (Java), golang-migrate (UX inferior). Documentado em `research.md §2`.
4. **Monorepo pnpm**: Estrutura validada, CI seletivo via `--filter`. Documentado em `research.md §3`.
5. **Dual pool**: asyncpg suporta múltiplos pools sem problemas. Documentado em `research.md §4`.
6. **shadcn Chart**: BarChart sobre recharts com tokens CSS. Documentado em `research.md §5`.
7. **Rate limiting**: slowapi + Redis, 5/min por IP+email. Documentado em `research.md §6`.

## Phase 1: Design & Contracts — Consolidado

**Status**: ✅ Completo

### Artefatos gerados:

1. **data-model.md**: 2 tabelas novas (`admin_users`, `audit_log`), 1 índice novo (`idx_messages_created_at`), 3 roles expandidas (`app_owner`, `authenticated`, `service_role`), query KPI com gap-fill.
2. **contracts/admin-api.md**: 5 endpoints (`POST /admin/auth/login`, `POST /admin/auth/logout`, `GET /admin/auth/me`, `GET /admin/metrics/messages-per-day`, `GET /health`), cookie JWT spec, error format.
3. **quickstart.md**: Setup local passo-a-passo, Docker Compose, troubleshooting.

## Phase 2: Implementation Strategy

### Fases de Implementação

A implementação segue 4 fases sequenciais, alinhadas com o "Suggested Approach" do pitch mas consolidadas para eficiência:

---

### Fase 1 — Monorepo + dbmate (F0 + F1)

**Objetivo**: Reorganizar o repositório em monorepo pnpm e integrar dbmate como migration tool, sem alterar comportamento funcional.

**Escopo**:
- Integrar dbmate: instalar, configurar `dbmate.yml`, converter migrations existentes (001-008) para formato dbmate
- Mover código existente para `apps/api/`: `prosauai/`, `tests/`, `tools/`, `config/`, `Dockerfile`
- Atualizar `pyproject.toml`, imports, CI, `docker-compose.yml` (context `./apps/api`)
- Criar `pnpm-workspace.yaml` com `apps/*` e `packages/*`
- Scaffold `apps/admin/` (Next.js 15 vazio) e `packages/types/` (estrutura base)
- Atualizar `docker-compose.yml`: service `migrate` (dbmate up), healthcheck na API
- Criar `docker-compose.override.yml` para dev (volumes, ports)

**Gate (não merge sem)**:
- Todos os testes existentes do pipeline (epics 001-005) passam sem regressão
- `docker compose up` sobe API + Redis + Postgres sem erros
- `dbmate up` aplica todas as migrations existentes de forma idempotente
- Next.js scaffold inicia em `http://localhost:3000` (página default)

**Risco**: Caminhos de import quebrados após mover para `apps/api/`. Mitigação: usar `rg "from prosauai\." | wc -l` antes e depois para garantir que todos os imports foram atualizados.

---

### Fase 2 — DB Roles + Pools + Tabelas Admin (F2.1–F2.3)

**Objetivo**: Criar infraestrutura de banco (roles, tabelas admin, índice) e separar pools asyncpg.

**Escopo**:
- Migration 010: roles (`app_owner` NOLOGIN, `authenticated` NOSUPERUSER, `service_role` BYPASSRLS), `ALTER TABLE ... OWNER TO app_owner`, `FORCE ROW LEVEL SECURITY`, GRANTs, `ALTER DEFAULT PRIVILEGES`
- Migration 011: tabela `admin_users` (schema em `data-model.md`)
- Migration 012: tabela `audit_log` (schema em `data-model.md`)
- Migration 013: índice `idx_messages_created_at` em `messages(created_at DESC)`
- Refactor `pool.py`: split em `pool_tenant` (role `authenticated`, RLS enforced) + `pool_admin` (role `service_role`, BYPASSRLS)
- Script de bootstrap admin: executado no lifespan da FastAPI, cria admin se tabela vazia e env vars presentes

**Gate (não merge sem)**:
- RLS smoke test: `authenticated` sem `SET LOCAL` retorna 0 rows; `service_role` vê tudo
- Pipeline WhatsApp inteiro funcional com `pool_tenant` (rodar suite de testes 001-005)
- Bootstrap cria admin na primeira execução, ignora se já existe
- `FORCE ROW LEVEL SECURITY` ativo em todas as tabelas de negócio

**Risco**: `CREATE ROLE` pode exigir superuser no Supabase gerenciado. [VALIDAR] — se bloqueado, usar roles existentes do Supabase (`anon`, `authenticated`, `service_role` que Supabase já cria).

---

### Fase 3 — Auth Backend + Endpoints Admin (F2.4–F2.7)

**Objetivo**: Implementar autenticação JWT e endpoints da API admin.

**Escopo**:
- Módulo `prosauai/auth/`: `jwt.py` (create/verify JWT HS256), `passwords.py` (bcrypt hash/verify), `dependencies.py` (FastAPI `Depends(get_current_admin)`), `bootstrap.py` (admin bootstrap)
- Router `/admin/auth/*`: `POST /login` (emite cookie JWT + audit_log), `POST /logout` (remove cookie + audit_log), `GET /me` (dados do admin autenticado)
- Router `/admin/metrics/*`: `GET /messages-per-day` (query com gap-fill, retorna JSON conforme contrato)
- Endpoint `GET /health` (verifica DB + Redis, retorna status)
- Rate limiting: `slowapi` com Redis, 5/min por IP+email no login
- CORS: `CORSMiddleware` com `ADMIN_FRONTEND_ORIGIN`, `allow_credentials=True`
- Testes: unit JWT, unit passwords, integration login flow, integration metrics, integration health, RLS isolation

**Gate (não merge sem)**:
- Login retorna cookie JWT válido por 24h
- Rate limit bloqueia 6ª tentativa em 1 minuto
- `/admin/metrics/messages-per-day` retorna 30 dias com gap-fill
- `/health` retorna status real de DB + Redis
- `audit_log` registra login_success, login_failed, rate_limit_hit
- Pipeline WhatsApp não impactado (sem alterações nos routers existentes)

**Risco**: `slowapi` pode conflitar com middleware existente da FastAPI. Mitigação: adicionar `limiter` como app state, não como middleware global.

---

### Fase 4 — Frontend Admin + Polish (F3 + F4)

**Objetivo**: Implementar o frontend Next.js com login, dashboard e gráfico.

**Escopo**:
- Scaffold Next.js 15 App Router completo em `apps/admin/`
- shadcn/ui init + instalar componentes: Button, Input, Card, Chart, Skeleton, Alert
- `lib/api-client.ts`: fetch wrapper com `credentials: 'include'` para enviar cookie
- `lib/auth.tsx`: AuthProvider + `useAuth` hook (login, logout, estado)
- `middleware.ts`: Edge middleware que valida presença + expiração do cookie JWT
- Página `/admin/login`: formulário email/senha com validação (zod + react-hook-form), mensagens de erro, redirect após login
- Layout `/admin/layout.tsx`: sidebar (navegação futura) + header (email do admin, botão logout)
- Página `/admin/page.tsx` (dashboard): KPI card (total mensagens 30d) + gráfico de barras (shadcn Chart / recharts)
- `hooks/use-messages-per-day.ts`: TanStack Query hook para buscar dados do endpoint
- Loading states (Skeleton) e error states (Alert com retry)
- Dockerfile standalone para Next.js
- `packages/types/api.ts`: tipos TypeScript gerados do OpenAPI (via `openapi-typescript`)
- `.env.example` na raiz, README com instruções

**Gate (não merge sem)**:
- Login funcional end-to-end (digitar credenciais → ver dashboard)
- Dashboard exibe gráfico com dados reais (ou zeros se vazio)
- Gap-fill visual: dias sem mensagens aparecem com barra zero
- Redirect para login se cookie ausente/expirado
- Logout limpa cookie e redireciona para login
- Loading state visível durante fetch
- Error state com botão retry funcional
- `docker compose up` sobe tudo (API + Admin + Postgres + Redis + migrate)

**Risco**: Conflito de portas ou proxy entre Next.js dev server e FastAPI. Mitigação: Next.js em 3000, API em 8050, CORS configurado.

---

## Divergências com ADRs Existentes

| ADR | O que diz | O que este epic faz | Justificativa |
|-----|-----------|---------------------|---------------|
| ADR-010 | Supabase Auth + Supabase JS client | JWT HS256 via FastAPI, sem Supabase JS | GoTrue overengineering para ~3 users. Migração futura. |
| ADR-022 | X-Admin-Token estático (fase 2) | JWT HS256 com identidade | Token estático sem auditoria de quem acessou. JWT melhor. |
| ADR-024 | Schema `admin` para tabelas admin | Tabelas em `public` | ADR-024 nunca aplicada no código. Cleanup vira epic separado. |
| Blueprint | Socket.io para real-time admin | Sem Socket.io neste epic | Dashboard não precisa de real-time. Socket.io entra em epic de conversations. |

**Nota**: Estas divergências estão documentadas e justificadas nas decisões #3, #6, #7 do epic-context. Novos ADRs serão considerados no reconcile se as divergências se consolidarem como padrão.

## Follow-ups Registrados

Para próximos epics (registrar no roadmap reassess):

1. **Cleanup ADR-024**: Mover tabelas para schemas corretos (`prosauai`, `admin`), configurar `search_path` nos pools.
2. **Migrar auth para GoTrue**: Quando portal de cliente entrar. httpOnly cookie + refresh token.
3. **Triggers audit_log**: Quando houver mutações admin (CRUD de tenants, etc.).
4. **Rate limit tenant-level**: Quando portal de cliente entrar.
5. **Admin CRUD via interface**: CRUD de administradores sem depender de SQL direto.
6. **Gráfico por tenant + filtros**: Se sobrar tempo neste epic, senão follow-up.
7. **Socket.io real-time**: Para conversation viewer e handoff inbox (epics futuros).

## Constitution Re-Check (Post-Design)

| # | Princípio | Status | Nota |
|---|-----------|--------|------|
| I | Pragmatism | ✅ PASS | 4 fases incrementais, circuit breaker definido |
| IV | Fast Action | ✅ PASS | Cada fase é shippable independentemente |
| V | Alternatives | ✅ PASS | research.md documenta alternativas para cada decisão |
| VII | TDD | ✅ PASS | RLS smoke test, auth integration tests, e2e dashboard |
| IX | Observability | ✅ PASS | structlog + audit_log + health check |

**Resultado**: Todas as gates passam. Nenhuma violação.

---
handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plano completo com 4 fases: (1) monorepo+dbmate, (2) DB roles+pools+tabelas, (3) auth backend+endpoints, (4) frontend+polish. Artefatos de design prontos: research.md, data-model.md, contracts/admin-api.md, quickstart.md. Divergências com ADRs documentadas e justificadas. Pronto para breakdown de tasks."
  blockers: []
  confidence: Alta
  kill_criteria: "Se o pipeline WhatsApp (001-005) regredir após reestruturação monorepo ou troca de roles, o epic precisa ser pausado e o dano revertido imediatamente."
