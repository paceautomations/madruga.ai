---
id: "003"
title: "Epic 003: Error tracking — adotar Sentry para visibilidade de crashes"
status: planned
priority: P1
phase: now
date: 2026-05-04
---
# Epic 003: Error tracking — adotar Sentry para visibilidade de crashes

## Problem

Crashes em produção são invisíveis. O codebase tem apenas `services/supabase/logging.ts` (logging custom para `logs_sistema`), o que não captura stack traces nativos iOS/Android, não desofusca código Hermes minified e não emite alerts. Detecção de bugs depende de **reclamação manual via WhatsApp** do usuário. Estamos prestes a entrar em fase de cobrança (epic-001) e migração de infra crítica (epic-002) — operar nesse cenário sem error tracking é negligente.

## Outcome esperado

- Sentry SDK `@sentry/react-native` integrado em mobile (iOS/Android/Web) e Edge Functions.
- Source maps Hermes uploadados automaticamente via EAS Build (`@sentry/wizard` + integration EAS).
- Release tracking via `eas update` channel + Sentry release.
- Performance tracing nas rotas críticas: registrar jogo (F3), Magic Link OTP (§5 business-process), Stripe checkout (📋 epic-001).
- Session replay opt-in para debug avançado.
- Alerts configurados para: crash rate > 1%, regressão por release, errors em Edge Functions.
- PII masking auditado — nenhum email/phone/userId raw em context.
- Métrica de sucesso: 100% dos crashes do app (mobile + web + Edge) chegam ao Sentry com stack trace desofuscado.

## Dependencies

- Depends on: 000-foundation.
- Blocks: **001-stripe** (cobrança não vai para prod sem visibilidade). **002-edge-migration** (migração crítica sem visibilidade).

## Notes

- ADR-012 ratifica Sentry vs Bugsnag / Rollbar / status quo.
- Free tier 5k errors/mo cobre os primeiros meses; escala para $26/mo no plano paid.
- LGPD: avaliar EU Cloud caso volume exigir; self-host GlitchTip OSS como fallback se ROI piorar.
