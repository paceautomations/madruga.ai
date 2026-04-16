---
epic: 007-admin-front-dashboard
created: 2026-04-15
updated: 2026-04-15T21:00:00
---
# Registro de Decisoes — Epic 007

1. `[2026-04-15 epic-context]` Antecipar epic admin como 007, empurrando "Configurable Routing" para 008+ (ref: planning/roadmap.md)
2. `[2026-04-15 epic-context]` Monorepo pnpm com apps/api, apps/admin, packages/types (ref: ADR-010)
3. `[2026-04-15 epic-context]` Expandir FastAPI existente com router /admin/*, sem BFF separado (ref: ADR-022)
4. `[2026-04-15 epic-context]` Dois pools asyncpg: pool_tenant (authenticated, RLS enforced) + pool_admin (service_role, BYPASSRLS), ambos statement_cache_size=0 (ref: ADR-011 expansao)
5. `[2026-04-15 epic-context]` app_owner NOLOGIN NOSUPERUSER como owner; authenticated e service_role via ALTER DEFAULT PRIVILEGES (ref: ADR-011 hardening CVE-2025-48757)
6. `[2026-04-15 epic-context]` admin_users e audit_log em public (nao em schema prosauai/admin). Cleanup ADR-024 vira epic separado (ref: ADR-024 drift)
7. `[2026-04-15 epic-context]` JWT HS256 PyJWT, bcrypt passlib, admin bootstrap via ADMIN_BOOTSTRAP_EMAIL/PASSWORD (ref: ADR-022)
8. `[2026-04-15 epic-context]` slowapi com 5/min por IP+email incluido neste epic (ref: risco brute force)
9. `[2026-04-15 epic-context]` Cookie JWT nao-httpOnly, SameSite=Lax, Secure em prod; migrar httpOnly com GoTrue (ref: ADR-022 follow-up)
10. `[2026-04-15 epic-context]` Query KPI via pool_admin BYPASSRLS, GROUP BY date em America/Sao_Paulo, gap-fill generate_series (ref: ADR-011)
11. `[2026-04-15 epic-context]` Timezone hardcoded America/Sao_Paulo [VALIDAR] quando houver tenants internacionais (ref: escopo v1)
12. `[2026-04-15 epic-context]` Next.js 15 App Router + shadcn/ui + Tailwind + TanStack Query + TanStack Table + react-hook-form + zod + openapi-typescript (ref: ADR-010)
13. `[2026-04-15 epic-context]` shadcn/ui fonte unica; graficos via shadcn Chart sobre recharts; Tremor descartado (ref: ADR-010)
14. `[2026-04-15 epic-context]` Adotar dbmate como migration tool, substituindo docker-entrypoint-initdb.d (ref: novo ADR F0)
15. `[2026-04-15 epic-context]` Indice idx_messages_created_at para agregacao cross-tenant por dia (ref: ADR-011 performance)
16. `[2026-04-15 epic-context]` pnpm como package manager Node, commitar pnpm-lock.yaml (ref: F0.3 doc base)
17. `[2026-04-15 epic-context]` Endpoint /health no FastAPI para healthcheck docker-compose (ref: novo)
18. `[2026-04-15 epic-context]` CORSMiddleware com origem via ADMIN_FRONTEND_ORIGIN, allow_credentials=True (ref: novo)
19. `[2026-04-15 implement]` Migration T014: Usado CREATE INDEX (nao CONCURRENTLY) porque dbmate wraps migrations em transacoes. Nota adicionada na migration para prod executar CONCURRENTLY manualmente se necessario. (ref: T014)
20. `[2026-04-15 implement]` T015: pool_admin usa admin_database_url com fallback para database_url quando vazio, permitindo single-DSN deployments sem config extra. (ref: T015, config.py)
21. `[2026-04-15 implement]` T016: Mantido app.state.pg_pool como alias para pools.tenant para backward compatibility total com pipeline existente. Pipeline usa getattr fallback. (ref: T016, main.py)
22. `[2026-04-15 implement]` T044: Usado route group `(authenticated)` no Next.js App Router para separar login page (sem sidebar/header) das paginas autenticadas (com sidebar/header). Plan previa layout unico em /admin/layout.tsx mas isso wrapparia login com chrome indesejado. (ref: T044, Next.js App Router conventions)
