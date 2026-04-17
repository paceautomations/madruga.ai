# Contracts — Epic 008 Admin Evolution

Contratos de API expostos pelo admin FastAPI (`apps/api/prosauai/admin/*`) e consumidos pelo frontend Next.js (`apps/admin`).

## Arquivos

- [`openapi.yaml`](./openapi.yaml) — OpenAPI 3.1 spec completo (todos os endpoints `/admin/*`).

## Tipos gerados

O frontend consome tipos gerados via `openapi-typescript` a partir de `openapi.yaml`:

```bash
# apps/admin
pnpm dlx openapi-typescript ../../platforms/prosauai/epics/008-admin-evolution/contracts/openapi.yaml -o src/types/api.ts
```

Gerar tipos é **parte do PR 5** (primeiro PR de backend). Task na `tasks.md`.

## Contratos por aba do admin

| Aba frontend | Endpoints consumidos |
|--------------|----------------------|
| Overview | `/admin/metrics/overview`, `/admin/metrics/activity-feed`, `/admin/metrics/system-health`, `/admin/metrics/tenant-health` |
| Conversas | `/admin/conversations` (list + detail + patch), `/admin/conversations/{id}/messages` |
| Trace Explorer | `/admin/traces` (list), `/admin/traces/{id}` (detail) |
| Performance AI | `/admin/metrics/performance` |
| Agentes | `/admin/agents`, `/admin/agents/{id}`, `/admin/agents/{id}/prompts`, `/admin/agents/{id}/prompts/activate` |
| Roteamento | `/admin/routing/rules`, `/admin/routing/decisions`, `/admin/routing/decisions/{id}`, `/admin/routing/stats` |
| Tenants | `/admin/tenants`, `/admin/tenants/{slug}` (get + patch) |
| Auditoria | `/admin/audit` |
| (Header dropdown) | `/admin/tenants` |
| (Contact profile) | `/admin/customers`, `/admin/customers/{id}` |

## Convenções

- **Auth**: todos os endpoints requerem cookie JWT `admin_token`. 401 → frontend redireciona para `/login?next=<URL>`.
- **Tenant filter**: parâmetro `?tenant=<slug>` ou `?tenant=all` (default). Server Components leem via `searchParams`.
- **Paginação**: cursor-based (opaque base64). Resposta inclui `pagination: { next_cursor, has_more }`.
- **Cache**: `/admin/metrics/performance` tem `Cache-Control: max-age=300` (5 min), cacheado server-side em Redis.
- **PATCH concurrency**: endpoints PATCH retornam 409 se recurso foi modificado concorrentemente (check via `updated_at` ou ETag).
- **Erros**: formato `{ "error": "<slug>", "message": "<human>", "details": {...} }`.
