---
title: "ADR-012: Error tracking — Sentry (gap atual; adoção proposta)"
status: proposed
date: 2026-05-04
decision: >
  Adotar Sentry como error tracking + release health + performance tracing para RN + web, com source maps Hermes automáticos via integração EAS Build oficial.
alternatives: >
  Bugsnag; Rollbar; manter logging ad-hoc atual (descartado)
rationale: >
  Hoje crashes em produção são invisíveis (`services/supabase/logging.ts` é apenas logging custom). Sentry é o padrão de fato para RN+Hermes+web, com release health, session replay e integração EAS oficial.
---
# ADR-012: Error tracking — Sentry (proposto)

## Status

Proposed — 2026-05-04 — gap a fechar em épico dedicado (epic-error-tracking)

## Context

**GAP em produção**: ResenhAI hoje **não tem error tracking dedicado**. Codebase usa apenas `services/supabase/logging.ts` (logging custom para tabela `logs_sistema` no Supabase). Isso significa: (a) crashes em produção (especialmente nativos iOS/Android) **não geram alerta**; (b) **stack traces Hermes minified** não são desofuscados — quando um log é registrado, é praticamente ilegível; (c) **release health** (% sessões sem erro por versão do app) é desconhecido; (d) detecção de bugs depende de **reclamação manual via WhatsApp** do usuário.

Estamos prestes a entrar em fase de cobrança (épico-001-stripe) e migração de infra crítica (épico-002-edge-migration) — operar nesse cenário sem error tracking é negligente.

## Decision

Adotar **Sentry** com SDK `@sentry/react-native`. Integração com EAS Build via `@sentry/wizard` para source maps automáticos no upload do bundle Hermes. Release tracking via `eas update` channel + Sentry release. Performance tracing nas rotas críticas (registrar jogo, OTP, checkout). Session replay opt-in para debug avançado. Plano: **free tier 5k errors/mo** inicialmente; escalar para $26/mo quando volume passar. Convenção: erros são reportados mas PII fica fora (mesmo masking de ADR-011).

## Alternatives Considered

### Alternative A: Sentry (proposed)
- **Pros:** padrão de fato RN+web+Hermes; source maps automáticos; release health; performance tracing; session replay; OTel-compatível; integração EAS oficial.
- **Cons:** pricing escala com volume (5k → $26 → mais alto); precisa manutenção de DSN secret + sourcemaps upload em CI.
- **Fit:** Único `high` fit para Hermes + EAS combo.

### Alternative B: Bugsnag
- **Pros:** stability scores por release (excelente para release gates); dashboard limpo.
- **Cons:** comunidade RN menor; sem session replay nativo; pricing free tier 7.5k events ($59/mo+ pago).
- **Why rejected:** Sentry oferece superset de features e adoção amplamente maior em RN.

### Alternative C: Rollbar
- **Pros:** telemetry e RQL queries; pricing similar.
- **Cons:** RN SDK menos maduro; comunidade pequena; UX datada.
- **Why rejected:** RN é cidadão de primeira em Sentry, segunda em Rollbar.

### Alternative D: Manter logging ad-hoc atual (`services/supabase/logging.ts`) — descartado
- **Why rejected:** invisibilidade total de crashes em produção. Risco operacional inaceitável após Stripe ir live.

## Consequences

### Positive
- Crashes detectados em minutos, não dias.
- Stack traces Hermes desofuscados via sourcemaps automáticos.
- Release health dá go/no-go signal para EAS Update.
- Performance tracing identifica regressões em telas críticas.

### Negative
- **Custo recorrente**: $26/mo no plano paid quando passar 5k errors/mo (esperado em < 6m após Stripe live).
- **Integração inicial**: épico dedicado (~3-5 dias) — wizard + sourcemaps + DSN + smoke test + alerts.
- **Disciplina de PII**: mesmas regras de ADR-011 — Sentry não pode receber email/phone raw em context.

### Risks
- **Risco:** volume > 100k errors/mo eleva custo desproporcional. **Mitigação:** avaliar self-host GlitchTip OSS (compatível com SDK Sentry) se ROI piorar.
- **Risco:** LGPD exigir hosting BR. **Mitigação:** Sentry tem EU region; plano de saída = self-host GlitchTip.
- **Risco:** sourcemaps falharem em CI silenciosamente — stack traces continuam minified. **Mitigação:** smoke test no pipeline (CI verifica símbolo conhecido após upload).

## References

- https://sentry.io/customers/ — empresas em produção
- https://docs.sentry.io/platforms/react-native/ — SDK docs
- https://docs.sentry.io/platforms/react-native/manual-setup/expo/ — Expo + EAS integration
- codebase-context.md §13-§14 — `services/supabase/logging.ts` é o status atual
