---
id: "006"
title: "Epic 006: Observabilidade — painel de saúde + NFR dashboards"
status: planned
priority: P3
date: 2026-05-04
---
# Epic 006: Observabilidade — painel de saúde + NFR dashboards

## Problem

NFRs definidos em [blueprint.md](../../engineering/blueprint.md) (P95 < 300ms, availability 99,5%, error rate < 1%, conversão OTP > 70%) são **alvos sem instrumentação completa** — temos PostHog para eventos de produto e Sentry (📋 após epic-003) para errors, mas não há painel consolidado que mostre saúde do sistema em tempo real. Incidentes são detectados via reclamação ou após o fato; não há alerting proativo para SLO breach.

## Outcome esperado

- Dashboard consolidado (Sentry + PostHog + Supabase metrics nativos) mostrando:
  - P95 latência por endpoint crítico (registrar jogo, OTP, checkout)
  - Crash rate por release (mobile + web + Edge)
  - Conversão de funnels críticos (Onboarding F1, Resenha F3, Cobrança F5)
  - Uptime do pipeline WhatsApp (§1-§4 business-process) — Edge Function whatsapp-webhook + Evolution API
  - Health do BaaS (connection pool, query duration p99) via Supabase API metrics
- Alerts configurados para: SLO breach por > 5min, error rate > 1% por release, queue Stripe webhook > 30s, Evolution API ban detectado.
- Runbook de incidentes documentado (`docs/runbooks/`) — passo-a-passo por categoria de alerta.
- Status page público (statuspage.io ou similar) `[VALIDAR — necessidade depende de tier B2B Enterprise]`.
- Métrica de sucesso: detecção média de incidente cai de N horas (reclamação manual) para < 5 min.

## Dependencies

- Depends on: **003-error-tracking** (Sentry é a fundação de error/performance tracing — extends).
- Recomendação: rodar após 001 + 002 estabilizarem (precisa de baseline de erros pós-cobrança e pós-migração para definir SLOs realistas).

## Notes

- Prazo Shape Up: ~2-3 semanas (boa parte é configuração).
- Custo: Sentry plan paid (já contratado pelo epic-003); PostHog grátis no tier atual; Supabase metrics nativos sem custo extra.
- Considerar OpenTelemetry semantic conventions (ADR-012 menciona compatibilidade) caso decisão de exportar traces para tooling externo.
