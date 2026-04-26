# Contracts Index — Epic 011

Contratos formais entre componentes do epic 011. Cada contrato e testavel e versionado.

| Arquivo | Escopo | Gate |
|---------|--------|------|
| [evaluator-persist.md](./evaluator-persist.md) | Protocol `EvalPersister` (Python) + `EvalScore` model + DeepEval metric wrapper + isolamento de falha | Contract tests (`tests/contract/test_eval_persister_contract.py`) — PASS obrigatorio antes de merge PR-A/PR-B |
| [openapi.yaml](./openapi.yaml) | OpenAPI 3.1 dos 3 endpoints admin novos (`GET /admin/metrics/evals`, `POST /admin/traces/{trace_id}/golden`, `PATCH /admin/tenants/{id}/evals`) | Tipos TS gerados via `pnpm gen:api`; openapi-typescript faz validacao em build |

## Gates de contrato

1. **Protocol conformance**: `ChatwootAdapter` (epic 010) e referencia — contract test parametrizado garante que todo `EvalPersister` (heuristic_online / deepeval_batch / human_curator) satisfaz `isinstance(impl, EvalPersister)` + respeita shape `persist(EvalScoreRecord) -> None`.

2. **OpenAPI drift**: `gh action lint-openapi` valida `openapi.yaml` (swagger-cli validate). Frontend build falha se tipos gerados divergem da UI (`pnpm gen:api && pnpm type-check`).

3. **Schema drift**: data-model.md define 5 migrations; cada migration tem `migrate:down` reversivel; CI integration test valida `dbmate up && dbmate down && dbmate up`.

4. **Protocol stability**: mudancas em `EvalPersister.persist` assinatura requer:
   - Contract test atualizado.
   - ADR novo documentando a mudanca.
   - Migration de dados se schema `eval_scores` mudar.

## Relacao com outros epics

| Epic | Contrato interconectado | Ponto de contato |
|------|-------------------------|------------------|
| 002 (observability) | OTel span propagation | `eval.score.persist` span attached ao trace original; DeepEval batch cria span root `eval.batch.deepeval` |
| 005 (conversation-core) | `evaluate_response` retorna `EvalResult` | `heuristic_online.py` mapeia `EvalResult → EvalScoreRecord` |
| 008 (admin-evolution) | pool_admin BYPASSRLS + TanStack Query v5 + Recharts | `GET /admin/metrics/evals` usa pool_admin; admin UI estende Performance AI |
| 010 (handoff-engine) | Feature flag pattern + scheduler singleton + config_poller | `evals.mode` espelha `handoff.mode`; 3 crons reusam advisory lock pattern |
