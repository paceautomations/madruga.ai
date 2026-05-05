---
id: "007"
title: "Epic 007: E2E nativo iOS/Android via Maestro"
status: planned
priority: P3
date: 2026-05-04
---
# Epic 007: E2E nativo iOS/Android via Maestro (opcional)

## Problem

Cobertura E2E hoje é **só web** — Playwright cobre 203 testes em 5 grupos (auth, ui, responsive, a11y, perf), mas regressões específicas de plataforma nativa (deep links, push notifications, fluxo de EAS Update OTA, integração com WhatsApp via deep link) **escapam do CI até o teste manual em loja**. Cobertura web alta dá falsa sensação de segurança pre-release.

## Outcome esperado

- Maestro (mobile.dev) integrado ao pipeline EAS Build — flow YAML executado contra `.ipa` e `.apk` em devices reais (cloud) por release.
- Suite mínima cobrindo:
  - Onboarding completo (F1) com Magic Link OTP em test mode
  - Registrar jogo (F3) com gesture nativo
  - Deep link de convite (`resenhai://invite?token=...`)
  - Push notifications (rodar test push e validar render)
  - Fluxo OTA Update (force-update simulation)
- Testes integrados ao GH Actions (gates de merge para `main`/`develop`).
- Métrica de sucesso: detectar 1 regressão nativa antes da loja (validação retrospectiva do investimento).

## Dependencies

- Depends on: **003-error-tracking** (sentry capta crashes durante run E2E).
- Recomendação: rodar **somente se** 1+ regressões nativas escaparem para produção em 6m após epic-003 — **épico opcional**, não-bloqueante.

## Notes

- Prazo Shape Up: ~2 semanas.
- ADR-009 ratifica Maestro vs Detox.
- Custo: Maestro Cloud free tier ou self-host — `[VALIDAR]` baseado em volume de runs.
- Status `opcional/futuro` por decisão do founder — só acionar se ROI ficar visível.
