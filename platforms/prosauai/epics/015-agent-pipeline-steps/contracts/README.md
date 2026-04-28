# Contracts — Epic 015 Agent Pipeline Steps

Endpoints REST adicionados pelo épico 015. Todos exigem cookie de admin
(`get_current_admin`) e operam via `pool_admin` (BYPASSRLS — ADR-027).

| Phase | Status | Endpoint | Description |
|-------|--------|----------|-------------|
| PR-1 | shipped | (none) | Schema-only: tabela `agent_pipeline_steps` + coluna `trace_steps.sub_steps` |
| PR-2/3/4 | shipped | (none) | Backend pipeline executor — sem novos endpoints |
| PR-5 (P2) | planned | `GET /admin/agents/{id}/pipeline-steps` | List pipeline steps for an agent |
| PR-5 (P2) | planned | `PUT /admin/agents/{id}/pipeline-steps` | Replace pipeline steps (atomic) |
| PR-6 (P2) | planned | `GET /admin/traces/{id}` (modificado) | Inclui `sub_steps` no payload |
| PR-6 (P2) | planned | `GET /admin/performance` (modificado) | Aceita `?group_by=agent_version` |

## Files

- [`openapi.yaml`](./openapi.yaml) — OpenAPI 3.1 spec dos endpoints novos do PR-5.
  PR-6 estende endpoints existentes do épico 008; o spec completo dele
  vive em `platforms/prosauai/epics/008-admin-evolution/contracts/openapi.yaml`
  (próxima atualização incorpora `sub_steps` e `?group_by=agent_version`).

## Type generation (PR-5 setup)

Frontend usa `openapi-typescript` (já em uso pelo épico 008) para gerar
tipos a partir do OpenAPI. Após PR-5 mergear:

```bash
cd apps/admin
pnpm gen:openapi  # incorporates new schemas from epic 015
```

Os tipos ficam em `apps/admin/lib/api/generated.d.ts` e são usados pelos
hooks TanStack Query em `apps/admin/lib/api/pipeline-steps.ts`.
