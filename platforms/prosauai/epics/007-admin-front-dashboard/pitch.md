---
epic: 007-admin-front-dashboard
title: Admin Front — Dashboard Inicial
appetite: 3 semanas
status: shipped
created: 2026-04-15
updated: 2026-04-15
delivered_at: 2026-04-15
---
# Epic 007 — Admin Front: Dashboard Inicial

## Problem

Hoje ProsaUAI não tem interface visual para operação. Toda observação do sistema — mensagens recebidas, tenants ativos, volume por dia — exige consultas SQL diretas no Postgres ou inspeção de logs no journalctl. Três consequências operacionais:

1. **Onboarding de clientes opaco**: não há "tela inicial" para mostrar ao cliente ou para operação interna validar que o pipeline está saudável.
2. **Troubleshooting demorado**: cada incidente começa com `psql` ou Phoenix; não há visão agregada de "mensagens/dia" acessível em 2 cliques.
3. **Base ausente para próximas telas**: epics planejados (tenants CRUD, conversas, handoff inbox, agent config) dependem de uma fundação — monorepo, auth, rotas `/admin`, dois pools asyncpg, stack Next.js — que ainda não existe.

Este epic entrega essa fundação **provando-a** com um único artefato visível: uma página `/admin` com gráfico de mensagens recebidas por dia (últimos 30d, agregadas cross-tenant) e um KPI de total no período. A partir daí, cada próxima tela é incremental.

## Appetite

**3 semanas** (1 dev full-time). Escopo fixo via Shape Up:

- F0 Pré-voo (RLS audit, decisão pnpm, inventário de deps): ~3h
- F1 Monorepo (mover código para `apps/api/`, criar `apps/admin/` + `packages/types/`): ~2 dias
- F2 Backend admin (migração 010/011, dois pools asyncpg, auth JWT + bcrypt, endpoints `/admin/*`, CORS): ~5 dias
- F3 Admin frontend (Next.js 15 App Router + shadcn/ui + TanStack Query + gráfico recharts): ~5 dias
- F4 Polish + docs: ~2 dias

Se estourar 3 semanas, **corta gráfico de linha e entrega só KPI** (gráfico vem no próximo ciclo). Se sobrar tempo, backlog curto: gráfico por tenant, export CSV, filtro de canal.

## Dependencies

- **ADR-010 (Next.js admin)**: confirma stack frontend. Este epic executa a decisão.
- **ADR-011 (Pool + RLS multi-tenant)**: base do isolamento. Este epic **expande** com role separation (`authenticated` NOSUPERUSER + `service_role` BYPASSRLS + `app_owner` NOLOGIN) — isolamento real em vez de "funciona por acidente porque código sempre chama `with_tenant`".
- **ADR-022 (Admin API)**: define prefix `/admin/*` no FastAPI existente (sem BFF separado). Este epic implementa.
- **ADR-024 (Schema isolation)**: aceita em papel, não aplicada no código (drift — todas as tabelas ainda em `public`). **Este epic não aplica ADR-024**; criará `admin_users` e `audit_log` também em `public`. Cleanup de schemas vira follow-up (ver Suggested Approach).
- **Pipeline WhatsApp existente** (epics 001–005): `messages` tabela viva em `public.messages` com coluna `tenant_id` e RLS. Admin consome via `pool_admin` (BYPASSRLS) para agregar cross-tenant.

Sem dependências em epics pendentes — tudo já está shipped.

## Captured Decisions

| # | Área | Decisão | Referência Arquitetural |
|---|------|---------|-------------------------|
| 1 | Roadmap | Antecipar epic admin como 007, empurrando "Configurable Routing" para 008+ | planning/roadmap.md (reassess no final do ciclo) |
| 2 | Estrutura | Monorepo pnpm com `apps/api`, `apps/admin`, `packages/types` | ADR-010 |
| 3 | Backend admin | Expandir FastAPI existente com router `/admin/*`, sem BFF separado | ADR-022 |
| 4 | Isolamento DB | Dois pools asyncpg: `pool_tenant` (role `authenticated`, RLS enforced) + `pool_admin` (role `service_role`, BYPASSRLS). `statement_cache_size=0` em ambos (compat Supavisor) | ADR-011 (expansão) |
| 5 | Ownership de tabelas | `app_owner` NOLOGIN NOSUPERUSER é owner; `authenticated` e `service_role` recebem GRANTs via `ALTER DEFAULT PRIVILEGES` | ADR-011 hardening (CVE-2025-48757) |
| 6 | Schema location | `admin_users` e `audit_log` em `public` (junto com tabelas atuais). Migração para schema `prosauai` / `admin` fica em epic de cleanup futuro | ADR-024 (aceita, não aplicada — drift conhecido) |
| 7 | Auth | Fase 0: JWT HS256 emitido pela FastAPI (PyJWT), bcrypt via passlib, admin bootstrap via `ADMIN_BOOTSTRAP_EMAIL/PASSWORD`. Fase futura: Supabase GoTrue | ADR-022 |
| 8 | Rate limit login | `slowapi` com 5 tentativas/min por IP+email incluído neste epic | Risco aceito acima, mitigado |
| 9 | Cookie JWT | Não-httpOnly, `SameSite=Lax`, `Secure` em prod. Motivo: Edge middleware Next precisa ler via `req.cookies`. CSP estrita + escopo admin interno (Tailscale) mitigam XSS | ADR-022 (follow-up: httpOnly + refresh quando GoTrue entrar) |
| 10 | Query KPI | `messages` em `public.*`, admin usa `pool_admin` (BYPASSRLS) com `GROUP BY (created_at AT TIME ZONE 'America/Sao_Paulo')::date` e gap-fill via `generate_series` | ADR-011 (BYPASSRLS intencional para admin) |
| 11 | Timezone | Hardcoded `America/Sao_Paulo` (Pace opera no Brasil) | [VALIDAR] quando houver tenants internacionais |
| 12 | Frontend stack | Next.js 15 App Router + shadcn/ui + Tailwind + TanStack Query + TanStack Table + react-hook-form + zod + openapi-typescript | ADR-010 |
| 13 | Design system | shadcn/ui como fonte única de verdade. Gráficos via `shadcn Chart` (wrapper oficial sobre recharts) herdando tokens `--chart-1..5`. **Tremor descartado** (paleta conflitante) | ADR-010 |
| 14 | Migration tool | Adotar **dbmate** (single-binary Go) neste epic. Substitui `docker-entrypoint-initdb.d` que só roda na primeira init do volume | Novo ADR será criado em F0 |
| 15 | Índice dashboard | `CREATE INDEX idx_messages_created_at ON messages(created_at DESC)` — agregação cross-tenant por dia sem scan | ADR-011 (performance RLS) |
| 16 | Package manager Node | pnpm (workspaces nativos, diskspace, velocidade). Commitar `pnpm-lock.yaml` | Decisão F0.3 do doc base |
| 17 | Healthcheck API | Adicionar endpoint `/health` no FastAPI (não existe hoje) — necessário para `depends_on.api.condition: service_healthy` do serviço admin | Novo, docker-compose |
| 18 | CORS | `CORSMiddleware` com origem via `ADMIN_FRONTEND_ORIGIN` env (default `http://localhost:3000`), `allow_credentials=True` | Novo |

## Resolved Gray Areas

**Numeração do epic (1A)**
Q: roadmap planejava 007=Configurable Routing e 011=Admin Dashboard. Este trabalho é 007 ou 011?
R: **007**. Antecipar admin dashboard desbloqueia UX + validação visual de observabilidade. "Configurable Routing" vira 008+. Reassess do roadmap via `/madruga:roadmap` no fim do ciclo reflete mudança.

**ADR-024 vs. query cross-tenant (2B)**
Q: como admin agrega `messages` entre tenants, dado que ADR-024 pede schemas isolados?
R: **Manter como está**. Descoberta: ADR-024 nunca foi aplicada no código — tabelas estão em `public`, pool.py não configura `search_path`. ADR-024 é sobre namespaces de schema (não schema-per-tenant, que foi rejeitado no ADR-011). Admin consulta `public.messages` via `pool_admin` BYPASSRLS — trivial e correto para o modelo Pool + RLS. Cleanup de schemas (aplicar ADR-024 de verdade) vira epic separado.

**Migration tool (3A)**
Q: depender de `docker-entrypoint-initdb.d` (só roda na primeira init) ou adotar ferramenta real?
R: **Adotar dbmate** neste epic. Single binary, idempotente, tracking via `schema_migrations` table, suporta up/down. Janela natural — epic já mexe em migrations 010/011. ADR curto vai cobrir a decisão.

**Cookie JWT (4A)**
Q: httpOnly ou não?
R: **Não-httpOnly** (`SameSite=Lax`, `Secure` em prod). Edge middleware Next lê `req.cookies` direto; httpOnly exigiria rota proxy intermediária ou perder validação no middleware. Escopo admin interno (~3 usuários em Tailscale) + CSP estrita mitigam XSS. Migração para httpOnly + refresh token fica junto com GoTrue.

**Rate limit login (5A)**
Q: incluir agora ou adiar?
R: **Incluir** (`slowapi` com Redis existente como backend, 5/min por IP+email). Custo ~30min vs. risco real de brute force mesmo em Tailscale. Sem motivo para adiar.

## Applicable Constraints

Do blueprint + ADRs:

- **Python 3.12 + FastAPI >=0.115** (blueprint active tech stack).
- **asyncpg >=0.30** — ambos pools herdam `statement_cache_size=0` (Supavisor compat, já configurado no pool atual).
- **Redis 7** — disponível e pode servir como backend do `slowapi`.
- **RLS obrigatório** (ADR-011 hardening): `SET LOCAL app.current_tenant_id`, nunca `SET` global; `FORCE ROW LEVEL SECURITY` em todas as tabelas de negócio; `NOSUPERUSER` nas roles app.
- **PT-BR em prose, EN em código** (CLAUDE.md).
- **Porta API = 8050** (não 8000). Frontend aponta via `NEXT_PUBLIC_API_URL`.
- **Variável RLS = `app.current_tenant_id`** (helper `public.tenant_id()`). Migrations 001–008 já usam.
- **Branch naming**: `epic/prosauai/007-admin-front-dashboard` (criada a partir de `origin/develop`).
- **Supabase compat**: novos objetos só em schemas já nossos (`public` com parcimônia, nunca em `auth`).

## Suggested Approach

Implementar em 7 PRs sequenciais, cada um deixando o sistema funcional:

1. **PR 0 — F0 pré-voo**: ADR curto documentando role separation real, decisão pnpm, decisão dbmate, audit de call sites (`rg "pool\.(acquire|execute|fetch)"` confirma que todos passam por `with_tenant`). Nenhum código ainda.
2. **PR 1 — F1.1 mover para `apps/api/`**: mover `prosauai/`, `tests/`, `tools/`, `config/`, `migrations/`, `Dockerfile` para `apps/api/`. Atualizar `pyproject.toml`, `docker-compose.yml` (`context: ./apps/api`), imports. CI verde.
3. **PR 2 — F1.2–F1.5 monorepo**: `pnpm-workspace.yaml`, `apps/admin/` vazio, `packages/types/` com script `export_openapi.py`, `docker-compose.yml` + `docker-compose.override.yml` (healthcheck api + admin com volume dev).
4. **PR 3 — F2.1–F2.3 DB + pools**: migração 010 (roles `authenticated` NOSUPERUSER + `service_role` BYPASSRLS + `app_owner` NOLOGIN, `ALTER TABLE ... OWNER TO app_owner`, `FORCE ROW LEVEL SECURITY`, GRANTs, `admin_users`, `audit_log`, índice `idx_messages_created_at`). Migration 011 bootstrap via script Python. Pool split em `pool_tenant` + `pool_admin`. **Dbmate integrado aqui.** Testes do pipeline existente DEVEM passar após troca de role.
5. **PR 4 — F2.4–F2.7 auth + endpoints**: `apps/api/prosauai/auth/` (jwt.py, passwords.py, dependencies.py), router `/admin/*` (login, me, metrics/messages-per-day), `slowapi`, CORS. Testes: unit JWT, integração login, RLS smoke (`authenticated` sem `SET LOCAL` retorna 0 rows; `service_role` vê tudo).
6. **PR 5 — F3.1–F3.6 frontend base**: Next.js 15 scaffold, shadcn/ui init + componentes, `lib/api-client.ts` + `lib/auth.tsx`, middleware presença-cookie, página login.
7. **PR 6 — F3.7–F3.10 dashboard**: layout admin (sidebar + header), página `/admin` com seletor período + KPI + gráfico shadcn Chart, Dockerfile standalone.
8. **PR 7 — F4 polish**: gerar `packages/types/api.ts`, README docs, `.env.example`, CI ajustado.

**Princípios operacionais:**

- **Dbmate first** — antes de qualquer código novo, integrar dbmate. Sem isso PR 3 vira um nó.
- **RLS smoke test como gate** — no PR 3 não merge até teste provar que `authenticated` sem `SET LOCAL` retorna vazio.
- **Pipeline WhatsApp é intocável** — após PR 3 (troca de role), rodar testes de integração de 001–005. Qualquer regressão aborta.
- **Next.js LTS pinado** — travar versão no `package.json` para evitar surpresa em minor bumps.
- **Follow-ups registrados** (para próximos epics / roadmap reassess):
  - Cleanup ADR-024 (mover tabelas para schema `prosauai`, configurar `search_path` no pool).
  - Migrar cookie para httpOnly + refresh token quando GoTrue entrar.
  - Triggers de `audit_log` quando houver mutações admin.
  - Rate limit mais granular (tenant-level) quando portal de cliente entrar.
