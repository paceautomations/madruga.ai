---
id: "005"
title: "Epic 005: Decomposição de `database.ts` por bounded context"
status: planned
priority: P2
date: 2026-05-04
---
# Epic 005: Decomposição de `database.ts` por bounded context

## Problem

`services/supabase/database.ts` tem **1598 linhas** — é a camada de acesso a dados monolítica para todos os bounded contexts (Identidade, Comunidade, Operação, Inteligência). Mudança em uma entidade (ex: alterar `Jogo`) força rebuild de testes que tocam o arquivo inteiro; mocks vazam entre contextos; novos devs precisam carregar contexto de tudo para mexer em qualquer parte. Context-map (anti-patterns) classificou esta situação como **Big Ball of Mud** entre Comunidade + Operação + Inteligência.

## Outcome esperado

- `services/supabase/database.ts` quebrado em módulos por bounded context:
  - `services/supabase/grupos.ts` — Comunidade (CRUD de grupos + membros)
  - `services/supabase/jogos.ts` — Operação (CRUD de jogos + invariantes)
  - `services/supabase/campeonatos.ts` — Operação (CRUD de campeonatos + inscrições)
  - `services/supabase/users.ts` — Identidade (já existe — consolidar)
  - `services/supabase/stats.ts` — Inteligência (queries de read models)
  - `services/supabase/audit.ts` — Operações Internas (`admin_audit_log`, `logs_sistema`)
- Cada módulo expõe API tipada via Zod schema do `lib/validation.ts` (ADR-002, ADR-003).
- `database.ts` mantido como reexport agregador durante transição (deprecation warning em 1 release; remover em release seguinte).
- Cobertura de testes ≥ 90% mantida durante o refactor.
- Maior arquivo resultante deve ter ≤ 400 LOC.
- Métrica de sucesso: invariantes de domínio vazam ≤ 1 testes mock cross-context (vs N hoje); `database.ts` removido em até 60d pós-merge inicial.

## Dependencies

- Depends on: **003-error-tracking** (Sentry detecta regressão).
- Depends on: **004-resenha-refactor** (god-screen refactor expõe bordas de contexto que tornam a decomposição da DB layer mais clara).
- Blocks: futuro épico de "queries cross-context formalizadas" se necessário.

## Notes

- Prazo Shape Up: ~3 semanas.
- Risco: mock patches em 1695 testes Jest podem precisar atualizar (CLAUDE.md `mock no módulo que define`). Mitigar com codemod automatizado.
- Domain-model.md §3 e §4 já definem boundary entre Operação e Inteligência — usar como guideline.
