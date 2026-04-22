# ProsaUAI — Decisions Log

Running log de micro-decisoes aplicadas em docs via skills `madruga:reconcile` e `madruga:reverse-reconcile`. ADRs formais em [decisions/](decisions/).

---

- [2026-04-20 reverse-reconcile] containers.md: adicionado container #13 `dbmate-migrate` (one-shot migration runner) na Container Matrix. Container estava em producao desde epic 006 mas nao figurava na doc. (refs: `23c92ff`, `2aea1c8`, `859c64b`, `88a88b5`, `ce17469`)
- [2026-04-20 reverse-reconcile] domain-model.md: adicionada subsecao "Tabelas admin-only (epic 008 — ADR-027)" cobrindo `public.admin_users`, `public.audit_log`, schema-level grants (`pool_admin` BYPASSRLS / `pool_app` RLS-enforced) e coluna `trace_steps.span_id`. (refs: `0554cd7`, `23c92ff`, `41a035f`, `59b1903`, `9e41fec`)
- [2026-04-22 reverse-reconcile] containers.md: pipeline prosauai-api promovido de 12-step para 13-step com step 6 `content_process` (Whisper STT + gpt-4o-mini vision via `run_content_process` — ADR-032), `RedisProcessorCache` + `PgBudgetTracker` no startup, e split explicito de roles `pool_tenant`=`authenticated`/NOBYPASSRLS vs `pool_admin`=`service_role`/BYPASSRLS (ADR-011 + ADR-027). (refs: `c45f658`, `f48cf35`)
- [2026-04-22 reverse-reconcile] blueprint.md: arvore de modulos em `conversation/` — pipeline.py agora documentado como 13-step (step 6 content_process — ADR-032), alinhado ao epic 009. (refs: `c45f658`, `f48cf35`)
