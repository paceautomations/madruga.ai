---
title: "ADR-010: Build & Deploy — EAS (Expo) + GitHub Actions"
status: accepted
date: 2026-05-04
decision: >
  Adotar EAS Build/Submit/Update (Expo) para mobile + GitHub Actions para web (Hostinger via SSH+Docker) e Supabase deployments (paths-filtered).
alternatives: >
  Codemagic; fastlane + GitHub Actions; App Center (descartado — EOL Mar/2025)
rationale: >
  EAS é o caminho oficial Expo 54 com OTA Updates nativo (expo-updates) — que sozinho justifica o pricing $99/mo; integração com GitHub Actions cobre web e Supabase com convenção develop→staging, main→produção já estabelecida no repo.
---
# ADR-010: Build & Deploy — EAS + GitHub Actions

## Status

Accepted — 2026-05-04 (retroativo)

## Context

ResenhAI publica em 3 alvos: (a) iOS via TestFlight + App Store; (b) Android via Google Play; (c) Web via Hostinger (Docker + nginx, deploy SSH). Conta com 2 GH Actions já em produção: `deploy-hostinger.yml` (web, push develop/main + manual) e `deploy-supabase.yml` (migrations + functions, paths-filtered). EAS já configurado em `eas.json` com profiles staging/production. Convenção: `develop` → staging (`dev.resenhai.com`); `main` → produção (`resenhai.com`) — CLAUDE.md:303-305 do resenhai-expo. Apple-Specific Password e service account Google Play já provisionados (codebase-context.md §10).

App Center foi descontinuado pela Microsoft em março de 2025 — não é mais alternativa.

## Decision

Adotar **EAS Build + EAS Submit + EAS Update** para mobile e **GitHub Actions** para web e Supabase. Pricing: EAS Production plan $99/mo (cobre prioridade de fila + builds ilimitados em conta). OTA via EAS Update (channels production/preview). Deploy web via SSH+Docker para Hostinger. Migrations Supabase via `supabase-deploy` action paths-filtered.

## Alternatives Considered

### Alternative A: EAS + GitHub Actions (chosen)
- **Pros:** EAS Update OTA nativo (sozinho justifica o $99/mo); integração Expo 54 perfeita; submit automático para stores; EAS Insights para build analytics; GH Actions já estabelecido para web/DB.
- **Cons:** vendor lock-in em Expo; pricing pode subir; OTA limitado a JS (não código nativo).
- **Fit:** Único `high` fit em Expo managed workflow.

### Alternative B: Codemagic
- **Pros:** M2 Macs rápidos; bom para flows custom Flutter+RN; preço por minuto pode ser menor em apps small.
- **Cons:** **perde EAS Update OTA** (precisaria implementar próprio com expo-updates standalone); sem integração Expo profiles nativa.
- **Why rejected:** OTA é feature crítica para iterar pós-release; sair do EAS = perder ferramenta.

### Alternative C: fastlane + GitHub Actions
- **Pros:** zero vendor cost; controle total.
- **Cons:** Google reduziu investimento em fastlane desde 2024; runner macOS GH Actions é caro ($0.08/min); sem OTA nativo (precisa implementar pipeline OTA custom).
- **Why rejected:** custo de manter pipeline custom > $99/mo do EAS; mantemo simplicidade.

### Alternative D: App Center (Microsoft, descartado)
- **Why rejected:** EOL em março de 2025; não é mais opção.

## Consequences

### Positive
- OTA Updates instantâneo em produção (correção de bug em horas, não dias de review).
- Expo SDK upgrades suportados oficialmente pela Expo team (releases mensais).
- Convenção develop→staging / main→produção alinhada com Git Flow.

### Negative
- **$99/mo recorrente** — soma com Supabase Pro ($25/mo) + PostHog (free tier) + Easypanel n8n (~$15/mo, sai com épico-002) = ~$140/mo de infra fixa.
- **Lock-in Expo**: sair do managed workflow para bare RN é doloroso; eject não é trivial.
- **Build queue**: priority é Production plan; em horário de pico ainda há fila.

### Risks
- **Risco:** EAS pricing subir > $300/mo. **Mitigação:** revisitar para Codemagic + fastlane + OTA custom.
- **Risco:** sair do Expo managed workflow (decisão futura). **Mitigação:** todas as libs nativas são vendoras (sem fork custom de RN core), facilitando eject planejado.
- **Risco:** Hostinger SSH key vazar / deploy quebrar. **Mitigação:** secret rotation no GH Actions; logs de deploy auditados.

## References

- https://docs.expo.dev/eas/ — EAS docs
- CLAUDE.md (resenhai-expo):281-305 — convenção de deploy
- codebase-context.md §9 — pipelines hoje em produção
- codebase-context.md §10 — secrets envolvidas (`[VALIDAR]` algumas fora de `.env.example`)
