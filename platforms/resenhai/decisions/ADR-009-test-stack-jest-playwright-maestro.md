---
title: "ADR-009: Test stack — Jest + Playwright (atual) + Maestro (proposto para native E2E)"
status: accepted
date: 2026-05-04
decision: >
  Manter Jest + Playwright como test stack core (1695 unit + 203 E2E web). Adicionar Maestro (mobile.dev) para cobrir gap de E2E nativo iOS/Android — não substitui Playwright web.
alternatives: >
  Vitest + Playwright; Detox para native E2E
rationale: >
  Migração de 1695 testes Jest tem ROI negativo dado preset jest-expo oficial e acoplamento com Hermes. Maestro (YAML declarativo, EAS integrado 2025) é mais simples que Detox e cobre o gap nativo sem flakiness histórico do Detox.
---
# ADR-009: Test stack — Jest + Playwright + Maestro

## Status

Accepted — 2026-05-04 (retroativo para Jest+Playwright; Maestro **proposto** para épico futuro)

## Context

Hoje (codebase-context.md §11): **Jest 29.7** com 1695 testes unit em 10 subdirs (`unit`, `hooks`, `services`, `utils`, `components`, `contexts`, `providers`, `screens`, `supabase-functions`, `ui`); **Playwright 1.57** com 203 testes E2E em 5 grupos (auth 68, ui 79, responsive 26, a11y 16, perf 15). Total: ~38k LOC de test code. Coverage targets: 70% min / 80% novo / 90% critical (auth/payments/invites — CLAUDE.md:172-174 do resenhai-expo).

**Gap identificado**: E2E nativo iOS/Android (Playwright cobre apenas web target). Sem isso, regressões específicas de plataforma (deep links, push notifications, EAS Update fluxo) escapam do CI até o teste manual em loja.

## Decision

- **Manter Jest 29.7 + jest-expo** preset oficial para todos os testes unit (cobertura completa do app, hooks, services, components). Status: Accepted.
- **Manter Playwright 1.57** para E2E web (target Hostinger, dev.resenhai.com / resenhai.com). Status: Accepted.
- **Adicionar Maestro (mobile.dev)** para E2E nativo iOS/Android, integrado com EAS Build (fluxo: build dev → Maestro flow contra .ipa/.apk → assertions). Status: Proposed — épico dedicado de test-coverage (a definir) ou integrado ao próximo épico de features novas.

## Alternatives Considered

### Alternative A: Jest + Playwright + Maestro (chosen)
- **Pros:** zero migração unit; Maestro cobre gap nativo com setup baixo; YAML declarativo é didático; EAS integration nativa em 2025.
- **Cons:** Jest watch lento em codebase grande; 3 ferramentas separadas para devops aprender.
- **Fit:** Único `high` fit que combina (a) zero downtime de migração e (b) cobertura nativa.

### Alternative B: Vitest + Playwright (mantido + Maestro)
- **Pros:** Vitest 2-5x mais rápido que Jest; ESM-native; melhor TS DX.
- **Cons:** RN preset Vitest ainda imaturo (incompatibilidades com jest-expo); migração de 1695 testes tem ROI negativo (esforço >> ganho de speed em watch).
- **Why rejected:** RN+Vitest não é caminho oficial Expo; risco de regressão alto.

### Alternative C: Jest + Playwright + Detox (Wix)
- **Pros:** Detox é E2E nativo maduro pós-Appium; gray-box (JS sync) ajuda com timing.
- **Cons:** flakiness histórico em CI (>15% reportado pela comunidade); Wix reduziu investimento em 2024; setup com Metro+native bridge é complexo.
- **Why rejected:** Maestro é mais simples e tem trajetória ascendente.

## Consequences

### Positive
- Cobertura nativa no CI fecha o último gap visível de test.
- Manter Jest preserva 1695 testes existentes — zero esforço de migração.
- Maestro YAML é didático; novo dev escreve flow em <1h.

### Negative
- 3 frameworks de test = 3 mental models para o dev (unit Jest, web E2E Playwright, native E2E Maestro).
- Maestro tem comunidade ainda crescendo — risco de ficar com bugs sem fix rápido.
- EAS integration de Maestro é via Action external (não nativa do EAS) — pode ter atrito em pricing/minutes.

### Risks
- **Risco:** Vitest publicar preset RN oficial estável com adapters jest-expo. **Mitigação:** revisitar este ADR; Vitest pode ser drop-in v6 futura.
- **Risco:** Maestro flakiness > 15% em CI. **Mitigação:** monitorar primeiros 30 runs; fallback para Detox se padrão se mantiver.
- **Risco:** Bug crítico só visível em E2E nativo escapa antes da adoção do Maestro. **Mitigação:** testes manuais reforçados em release até Maestro estar verde.

## References

- https://docs.expo.dev/develop/unit-testing/ — Expo testing
- https://maestro.mobile.dev/ — Maestro
- CLAUDE.md (resenhai-expo):141,158-162,172-174 — convenções de test
- codebase-context.md §11 — inventário de testes hoje
