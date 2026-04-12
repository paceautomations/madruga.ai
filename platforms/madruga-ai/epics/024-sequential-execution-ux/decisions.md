---
epic: 024-sequential-execution-ux
created: 2026-04-10
updated: 2026-04-12
---
# Registro de Decisões — Epic 024

1. `[2026-04-10 epic-context]` Substituir worktree por checkout direto no clone principal via `repo.isolation: branch` opt-in em `platform.yaml` (ref: ADR-006, ADR-004)
2. `[2026-04-10 epic-context]` Adicionar status `queued` ao CHECK constraint da tabela `epics` via migration 017 — padrão rec-tabela SQLite (ref: ADR-004, migration 009)
3. `[2026-04-10 epic-context]` Trigger de promoção inserido após `_running_epics.discard(epic_id)` no `dag_scheduler` de `easter.py` — síncrono via `asyncio.to_thread` (ref: ADR-006)
4. `[2026-04-10 epic-context]` Manter `drafted` = planejado sem ordem, `queued` = próximo na fila com auto-promoção — statuses distintos com transições explícitas (ref: ADR-009)
5. `[2026-04-10 epic-context]` Cascade base ao promover: branch de HEAD do epic anterior no clone externo; fallback para `origin/base_branch` se já merged (ref: ADR-010)
6. `[2026-04-10 epic-context]` Dirty tree guard via `git status --porcelain` antes de checkout — output não vazio pausa epic com gate humano + ntfy (ref: ADR-006, ADR-010)
7. `[2026-04-10 epic-context]` Failure handling: 3 retries com backoff 1s/2s/4s → status `blocked` + ntfy alert; idempotente via upsert após branch criada (ref: ADR-006)
8. `[2026-04-10 epic-context]` Manter raw subprocess para operações git — stdlib constraint, sem gitpython/pygit2 (ref: ADR-004)
9. `[2026-04-10 epic-context]` Merge automático de PRs fora do escopo — permanece gate humano para revisão de código (ref: ADR-013)
10. `[2026-04-11 planning-session]` Hook de promoção em easter.py respeita env var `MADRUGA_QUEUE_PROMOTION` (default off) — código commitado fica inativo até export explícito, permitindo merge seguro antes de ativação (ref: ADR-021 dispatch kill-switches, CLAUDE.md bare-lite precedents)
11. `[2026-04-11 planning-session]` Ciclo L2 de 024 roda interativo no chat, nunca via dag_executor dispatch — epic reescreve o próprio dag_executor, autônomo = cegueira. Gates humanos inegociáveis (ref: auto-sabotage guardrail Camada 3)
12. `[2026-04-11 planning-session]` Ordem aditiva das tasks: migration 017 → db_pipeline aditivo → platform_cli queue → ensure_repo (função isolada) → implement_remote (call-site swap) → easter.py hook por último. Cada commit com make test verde (ref: Camadas 2+5)
13. `[2026-04-11 planning-session]` Pré-condição da fase de implementação: stop easter + backup .pipeline/madruga.db. Pós-condição: qa verde ANTES de restart easter (ref: Camadas 0+1)
14. `[2026-04-12 implement]` Removido worktree.py — branch isolation é o único modo para plataformas externas. worktree.py + testes + CLI subcommands removidos. Rollback via git revert se necessário. (ref: user decision, supersedes decision #1 isolation opt-in)
