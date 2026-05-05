---
title: "ADR-001: Mobile framework — Expo + React Native"
status: accepted
date: 2026-05-04
decision: >
  Adotar Expo SDK + React Native como framework cliente único para iOS, Android e Web, com Expo Router file-based para navegação e EAS Build/Update para CI e OTA.
alternatives: >
  Flutter 3.x; Native (Swift + Kotlin)
rationale: >
  Codebase compartilhada em TypeScript entre web e mobile, EAS Build maduro, OTA via expo-updates crítico para iteração rápida e custo de dev compatível com equipe de 2 contribuidores.
---
# ADR-001: Mobile framework — Expo + React Native

## Status

Accepted — 2026-05-04 (retroativo — decisão originalmente tomada na criação do app `[VALIDAR — data exata desconhecida]`)

## Context

ResenhAI é app multi-plataforma (iOS, Android, Web) para comunidades de esportes de areia. A equipe é de 2 contribuidores (codebase-context.md §3) e o orçamento do TAM brasileiro (1,7M praticantes) não comporta investir em duas codebases nativas separadas. Requisitos centrais: (a) iteração rápida com OTA updates (correção de bugs sem submeter à App Store / Google Play), (b) reuso máximo entre web e mobile (TypeScript, Zod schemas, RHF), (c) acesso a APIs nativas (camera para perfil, deep linking para convites WhatsApp, push notifications), (d) Hermes/New Architecture para perf razoável em devices Android low-end (Moto G, Samsung A — predominantes no TAM brasileiro).

## Decision

Adotar **Expo SDK 54 + React Native 0.81 + Expo Router 6** como camada cliente única para iOS, Android e Web. Build/CI via **EAS Build**; OTA via **expo-updates**; Submit via **EAS Submit**. Type system 100% TypeScript (strict).

## Alternatives Considered

### Alternative A: Expo + React Native (chosen)
- **Pros:** TS unificado web/mobile; ecossistema maduro (122k stars RN, 38k Expo); OTA crítico para iterar; EAS Build elimina infra própria; libs Brasil (PIX, WhatsApp helpers) cobertas; Hermes melhora perf RN.
- **Cons:** JS bridge ainda existe (mesmo com New Architecture); libs nativas custom exigem prebuild; lock-in em Expo managed workflow; OTA limitado a JS bundle (não atualiza código nativo).
- **Fit:** Único com fit `high` para 2 devs + iteração rápida + reuso TS web/mobile.

### Alternative B: Flutter 3.x
- **Pros:** Render próprio (Skia/Impeller), perf 60fps mais consistente; hot reload maduro; Material/Cupertino bem polidos.
- **Cons:** Reescrita total em Dart (todo o codebase TS perdido); ecossistema BR menos coberto (PIX, gateways); separa web e mobile (Flutter Web ainda imaturo).
- **Why rejected:** Custo de migração proibitivo (~58k LOC reescritos); separa stack web do mobile.

### Alternative C: Native (Swift + Kotlin)
- **Pros:** APIs novas no dia 1; perf máxima; sem bridge.
- **Cons:** 2 codebases independentes; 4x esforço de manutenção; sem code-sharing com web.
- **Why rejected:** Inviável com 2 devs e velocidade exigida pelo roadmap.

## Consequences

### Positive
- Codebase única reduz custo de manutenção e velocidade de feature delivery.
- OTA permite hotfix sem ciclo de review da loja.
- TypeScript + Zod schemas reaproveitáveis no Edge Functions Deno (ADR-005, ADR-006).

### Negative
- God-screen `app/(app)/management/resenha.tsx` (2200 LOC, 18 commits/90d — codebase-context.md §13) é sintoma de Expo Router file-based encorajar concentração de lógica em rotas grandes; tendência precisa ser combatida com convenções no blueprint.
- Hermes + New Architecture têm migrações ocasionais com breaking changes; cada upgrade Expo SDK exige regression test passada.
- Lock-in em Expo: sair do managed workflow (para bare RN) é doloroso; EAS pricing pode subir.

### Risks
- **Risco:** RN 0.82+ ou New Architecture trazerem incompatibilidade com NativeWind (ADR-004). **Mitigação:** monitorar releases NativeWind v5; ter fallback Tamagui mapeado.
- **Risco:** Performance crítica em listas (>100 items) com Hermes. **Mitigação:** já adotando FlashList em telas críticas `[VALIDAR — confirmar uso]`.

## References

- https://docs.expo.dev/eas/ — EAS docs
- https://reactnative.dev/showcase — empresas em produção
- codebase-context.md §4 (versions) e §13 (god-screen sinaliza débito)
