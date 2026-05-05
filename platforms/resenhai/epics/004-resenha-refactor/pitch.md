---
id: "004"
title: "Epic 004: Refactor god-screen `resenha.tsx`"
status: planned
priority: P2
date: 2026-05-04
---
# Epic 004: Refactor god-screen `resenha.tsx`

## Problem

`app/(app)/management/resenha.tsx` tem **2200 linhas e 18 commits nos últimos 90 dias** (codebase-context.md §13) — é simultaneamente o maior arquivo da base e o de maior churn. Concentra UI de gestão de resenha, fluxo de eventos e regras de campeonato num único screen, fazendo com que cada feature touched obrigue mexer no mesmo arquivo gigante. Velocity em features dessa área está caindo perceptivelmente (bug rate em commits recentes maior que outras telas).

## Outcome esperado

- `resenha.tsx` decomposta em sub-rotas via Expo Router file-based:
  - `(app)/management/resenha/index.tsx` — listagem/dashboard de resenha
  - `(app)/management/resenha/event-create.tsx` — criação de evento
  - `(app)/management/resenha/event-detail.tsx` — detalhe de resenha agendada
  - `(app)/management/resenha/championship-create.tsx` — criação de campeonato (extraída do god-screen)
- Components reutilizáveis movidos para `components/resenha/` quebrados por subdomínio.
- Hooks de presença / ranking / champ extraídos para `hooks/` por feature.
- Cobertura de testes mantida ≥ 90% (regra critical paths) durante o refactor — aproveitar 1695 Jest tests existentes como rede de proteção.
- Maior arquivo resultante deve ter ≤ 500 LOC.
- Métrica de sucesso: tempo médio de delivery de feature em "gestão de resenha" cai 40% nos 30d pós-merge `[VALIDAR]`; god-screen deixa de aparecer no top 3 de churn 90d.

## Dependencies

- Depends on: **003-error-tracking** (Sentry detecta regressão durante refactor).
- Recomendação: rodar após 001-stripe ir live para evitar mudar área crítica antes do produto monetizar.
- Blocks: **005-database-decomposition** (refactor de DB se beneficia de telas já decompostas — invariantes ficam mais claros).

## Notes

- Prazo Shape Up: ~3-4 semanas.
- Risco: regressão em fluxo crítico de criação de campeonato — mitigar com Playwright E2E reforçado pré-merge.
- Considerar visual regression (screenshot diff) para validar que UI continua pixel-equivalente.
