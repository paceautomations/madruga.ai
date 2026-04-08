---
epic: 023-commit-traceability
created: 2026-04-08
updated: 2026-04-08
---
# Registro de Decisoes — Epic 023

1. `[2026-04-08 epic-context]` Estender BC Pipeline State para commits, nao criar BC novo (ref: domain-model.md BC #2)
2. `[2026-04-08 epic-context]` Tabela nomeada `commits` (nao `changes`) — acoplamento a git eh aceitavel (ref: ADR-004)
3. `[2026-04-08 epic-context]` Post-commit hook em Python, nao shell — consistencia com stack (ref: ADR-004, blueprint)
4. `[2026-04-08 epic-context]` Backfill desde epic 001, commits pre-006 todos linkados a 001-inicio-de-tudo (ref: convencao epic branches)
5. `[2026-04-08 epic-context]` Identificacao de plataforma: branch first, fallback file path, default madruga-ai (ref: platform.yaml repo binding)
6. `[2026-04-08 epic-context]` Identificacao de epic: branch pattern + tag [epic:NNN] como override (ref: pipeline contract branch guard)
7. `[2026-04-08 epic-context]` Commits multi-plataforma: 1 row por plataforma afetada, aceitar duplicatas (ref: pragmatismo > elegancia)
8. `[2026-04-08 epic-context]` Portal: nova aba "Changes" no control panel existente (ref: blueprint deploy topology)
9. `[2026-04-08 epic-context]` Hook best-effort + reseed como safety net (ref: padrao post_save --reseed)
