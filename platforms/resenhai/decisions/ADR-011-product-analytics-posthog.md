---
title: "ADR-011: Product analytics — PostHog (combo analytics + flags + replays)"
status: accepted
date: 2026-05-04
decision: >
  Adotar PostHog (US Cloud) como product analytics, feature flags e session replay no mesmo SDK (`posthog-react-native`). PII masking obrigatório (email/phone/userId).
alternatives: >
  Mixpanel; Amplitude; Google Analytics 4
rationale: >
  Único produto que cobre analytics + feature flags + session replay no mesmo SDK e dashboard, com OSS self-host opcional para LGPD futuro e pricing previsível. Concorrentes exigem 2-3 ferramentas integradas para o mesmo escopo.
---
# ADR-011: Product analytics — PostHog

## Status

Accepted — 2026-05-04 (retroativo)

## Context

ResenhAI precisa medir: (a) funnels — Onboarding completion (F1), Resenha → Registrar jogo (F3), Stripe checkout (F5); (b) retention cohorts — DAU/WAU/MAU por grupo, churn pós-cupom; (c) feature usage — que telas são acessadas, quais features de tier Rei são usadas; (d) session replay — debug visual de bugs reportados. Convenção mandatória do projeto: PII masking obrigatório (`maskUserId`, `maskEmail`, `maskPhone`) — CLAUDE.md:117-125 do resenhai-expo. Stack atual em produção: `posthog-react-native` 4.34, US Cloud (`us.i.posthog.com`).

## Decision

Adotar **PostHog 4.34** (US Cloud) como produto analytics + feature flags + session replay. SDK `posthog-react-native` integrado em `services/analytics.ts` e inicializado em `app/_layout.tsx`. Eventos seguem convenção snake_case (`game_registered`, `championship_created`, `tier_upgraded`). PII jamais é enviada raw — passa por `utils/logger.ts` com masking.

## Alternatives Considered

### Alternative A: PostHog (chosen)
- **Pros:** combo único analytics + flags + replays no mesmo SDK; OSS self-host opcional (preparação para LGPD); pricing previsível (free 1M events/mo); EU/US Cloud disponível.
- **Cons:** funnels menos refinados que Mixpanel; comunidade menor que Amplitude no enterprise.
- **Fit:** Único `high` fit no combo de capabilities.

### Alternative B: Mixpanel
- **Pros:** funnels e impact reports best-in-class; JQL queries; UX premium.
- **Cons:** sem feature flags nativos; sem session replay; pricing por MTU surpreende em escala.
- **Why rejected:** combo analytics+flags+replay exige 2-3 ferramentas separadas (Mixpanel + LaunchDarkly + LogRocket).

### Alternative C: Amplitude
- **Pros:** cohort analysis e behavioral predictions enterprise-grade.
- **Cons:** pricing enterprise opaco > 100k MTU; RN SDK menos polido; sem session replay.
- **Why rejected:** custo de escalar para enterprise sem benefício para SaaS SMB.

### Alternative D: Google Analytics 4
- **Pros:** gratuito ilimitado; cobertura web universal.
- **Cons:** sampling em volume; latência 24-48h em reports; modelo event web-centric (apps são segunda classe); sem session replay; sem feature flags.
- **Why rejected:** inadequado para mobile-first analytics em app B2C com loop semanal.

## Consequences

### Positive
- 1 SDK = 3 use cases (analytics + flags + replays) — reduz overhead de integração.
- Feature flags permitem A/B teste de UX (ex: 2 layouts de ranking) sem deploy.
- Session replay acelera debug de issues reportados pelo Dono da Resenha.

### Negative
- **PII masking obrigatório**: esquecer 1 lugar = vazamento de email/phone para PostHog Cloud. Disciplina de revisão exige rigor (CLAUDE.md:117-125).
- **US Cloud**: dados de usuários BR transitam por servidor US — risco de compliance LGPD (consentimento explícito requerido). Mitigação: avaliar EU Cloud ou self-host se LGPD demanda escalar.
- **1M events/mo no free tier**: passa rápido em escala (1.000 grupos × 30 eventos/dia ≈ 900k/mês). Plano pago começa a partir de R$ inflado para SMB BR.

### Risks
- **Risco:** PostHog cobrar > $0.0001/event no futuro. **Mitigação:** pricing previsível na contratação atual; self-host PostHog Community se inviabilizar.
- **Risco:** LGPD exigir hosting BR. **Mitigação:** migrar para EU Cloud (closer to BR) ou self-host (PostHog Open Source).
- **Risco:** PII vaza por código sem masking. **Mitigação:** lint rule no projeto + code review obrigatório em qualquer chamada `posthog.capture(...)`.

## References

- https://posthog.com/customers — empresas em produção
- CLAUDE.md (resenhai-expo):117-125 — convenção PII masking
- codebase-context.md §8 — SDK em produção
- `services/analytics.ts` — implementação atual
