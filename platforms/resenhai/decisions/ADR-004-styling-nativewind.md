---
title: "ADR-004: Styling system — NativeWind 4 (Tailwind para RN)"
status: accepted
date: 2026-05-04
decision: >
  Adotar NativeWind 4 + Tailwind CSS 3 como sistema único de estilização para iOS, Android e Web, com tokens centralizados em `lib/design-system.ts`.
alternatives: >
  Tamagui; Restyle (Shopify); StyleSheet.create
rationale: >
  Único caminho que compartilha classes Tailwind 1:1 entre web e mobile, mantém complexidade `low` e preserva design tokens centrais já em uso (`lib/design-system.ts`).
---
# ADR-004: Styling system — NativeWind 4 (Tailwind para RN)

## Status

Accepted — 2026-05-04 (retroativo) — confiança Média

## Context

ResenhAI roda em iOS, Android e Web (Expo Router). O design system precisa ser unificado: as mesmas cores, espaçamentos e tipografia em qualquer plataforma. Convenção do projeto exige tokens centralizados em `lib/design-system.ts`, sem cores hardcoded em componentes (CLAUDE.md do resenhai-expo:113,217 — codebase-context.md §12). Equipe já conhece Tailwind do front-end web.

## Decision

Adotar **NativeWind 4.1 + Tailwind CSS 3.4** como camada única de estilização. Tokens (`colors`, `spacing`, `radii`, `typography`) em `lib/design-system.ts` mapeados para `tailwind.config.js`. Dark mode via classe `dark:` nativo do Tailwind. NativeWind compila as classes para `StyleSheet.create()` em build via Babel — runtime cost equivalente ao StyleSheet manual.

## Alternatives Considered

### Alternative A: NativeWind 4 (chosen)
- **Pros:** classes Tailwind idênticas entre web e mobile; jit compiler; dark mode nativo; complexidade `low`; design tokens unificados.
- **Cons:** debug das classes geradas exige plugin VSCode; comunidade ainda pequena (~7.5k stars).
- **Fit:** Único `high` fit em code-share web/mobile + tokens centrais.

### Alternative B: Tamagui
- **Pros:** compilador AOT extrai estilos estáticos (perf web+mobile top); tokens tipados.
- **Cons:** setup pesado (babel + metro + next plugins); curva alta; lock-in.
- **Why rejected:** ganho de perf não justifica reescrita; complexidade extra para equipe de 2.

### Alternative C: Restyle (Shopify)
- **Pros:** theming tipado pelo TS; simplicidade.
- **Cons:** só RN — sem code-share com web (que usa Tailwind no resenhai); manutenção lenta da Shopify.
- **Why rejected:** quebra a unificação de design tokens com web.

### Alternative D: StyleSheet.create nativo
- **Pros:** zero deps; performance máxima; oficial.
- **Cons:** sem theming; sem code-share com web; verbose em design system de 100+ componentes.
- **Why rejected:** projeto cresceu além do que StyleSheet manual escala (~11k LOC components — codebase-context.md §5).

## Consequences

### Positive
- Onboarding de dev com Tailwind background é instantâneo.
- Tokens em `lib/design-system.ts` aplicados consistentemente.
- Dark mode com 1 classe.

### Negative
- IntelliSense de classes em VSCode requer plugin Tailwind CSS específico.
- Debug visual (DevTools) mostra classes geradas, não a string Tailwind original — overhead cognitivo.
- Confiança **Média** (vs Alta de outros ADRs): se RN 0.82 chegar antes de NativeWind v5, podemos ter incompatibilidade temporária com New Architecture.

### Risks
- **Risco:** lista de feed renderizando >100 cards com jank em Android low-end. **Mitigação:** já adotar FlashList + memoization; reavaliar Tamagui se persistir.
- **Risco:** NativeWind v5 atrasar suporte a New Architecture. **Mitigação:** monitorar release notes; ter Tamagui mapeado como Plan B.

## References

- https://www.nativewind.dev — docs
- CLAUDE.md (resenhai-expo):113,217 — convenção de design tokens
- codebase-context.md §12 (decisão pré-existente)
