---
title: "ADR-016: Web client é PWA standalone, não browser puro (retroativo)"
status: accepted
date: 2026-05-05
decision: >
  Tratar o cliente Web como **PWA instalável** (standalone fullscreen no iOS Safari), não como
  browser. Inclui Service Worker, manifest, detecção e enforcement de modo standalone, viewport
  CSS dinâmico (`--vh`) — tudo já em produção.
alternatives: >
  Web puramente como browser (sem PWA); app nativo Web separado (4ª codebase)
rationale: >
  Decisão tomada no início (PWA infra committada desde 2025); ADR retroativo formaliza porque
  containers.md trata Web como "Browser" puro, omitindo PWA — perda de contexto para épicos de
  performance Web e instalação.
---
# ADR-016: Web client é PWA standalone, não browser puro (retroativo)

## Status

Accepted (retroativo — 2026-05-05). Implementado desde lançamento web. Conecta com
[ADR-001](../ADR-001-mobile-framework-expo-rn/) (Expo unifica mobile + web) e
[containers.md container "Web Static"](../../engineering/containers/).

## Context

ResenhAI é um app multi-plataforma (iOS + Android + Web) com **single codebase** Expo.
A versão Web não é "site institucional ou catálogo", é **a mesma experiência completa do app**
rodando em browser. Para igualar a UX nativa (sem barras do browser, gestos consistentes,
viewport correto), o web precisa ser **PWA instalável**.

A solução já em produção inclui:

- [`public/manifest.json`](../../resenhai-expo/public/manifest.json) — manifest PWA com nome,
  ícones e cor de tema.
- [`public/sw.js`](../../resenhai-expo/public/sw.js) — Service Worker registrado em
  `app/+html.tsx`; cacheia bundle estático e dispara prompt de instalação.
- [`utils/isStandalone.ts`](../../resenhai-expo/utils/isStandalone.ts) (~10KB) —
  (a) detecta `display-mode: standalone`,
  (b) força fullscreen no iOS Safari (esconde barras),
  (c) calcula viewport `--vh` dinâmico (CSS variable) para corrigir o bug clássico do iOS de
      `100vh` incluir a barra de URL.
- `app/+html.tsx` injeta meta tags PWA: `apple-mobile-web-app-capable`, `theme-color`,
  `viewport-fit=cover`, etc.
- `app/_layout.tsx` chama `enforceFullscreen()` em mount.

Sem ADR, isso fica invisível: containers.md trata o container "Web Static" como Docker+nginx
servindo bundle, sem mencionar PWA. Quem entrar em épico de performance Web ou de offline-first
não vai saber que metade do trabalho já existe.

## Decision

1. **Web é um PWA standalone**, não browser puro. Toda decisão sobre Web (deploy, performance,
   offline) deve assumir esse contexto.
2. **Service Worker** é responsável pelo cache do bundle estático e pelo prompt de instalação;
   é **registrado em build** via `app/+html.tsx`, não em runtime.
3. **iOS Safari standalone enforcement** é tratado como first-class — `utils/isStandalone.ts` é
   load-bearing; bug nesse arquivo quebra a UX completa no iOS web.
4. **Viewport CSS dinâmico**: estilos `100vh` puro são **proibidos** no codebase web; usar
   `var(--vh, 1vh) * 100` (definido em `isStandalone.ts`).
5. **Deploy** continua via Hostinger (Docker + nginx) — manifest e SW são parte do bundle estático.
6. **Roadmap não pago**: testes E2E de PWA (instalação, offline, manifest) ainda não existem
   formalmente — débito reconhecido em `e2e/` `[VALIDAR — confirmar com Lighthouse no CI]`.

## Alternatives Considered

### Alternative A: PWA standalone (escolhido — retroativo)
- **Pros:** UX igual ao mobile nativo (sem barras); instalável no celular sem App Store; offline
  primeiro nível; reaproveita 100% código RN+Expo.
- **Cons:** complexidade extra (SW, manifest, enforcement iOS); Lighthouse bugs intermitentes;
  cache de SW exige cuidado em deploy (versionar bundle).
- **Fit:** alta — é a única forma de paridade real com mobile.

### Alternative B: Web como browser puro (sem PWA)
- **Pros:** simplicidade; sem SW, sem manifest, sem enforcement.
- **Cons:** UX mobile-web ruim (barras de URL ocupam espaço, viewport quebra, sem instalação);
  conversão menor.
- **Why rejected:** público acessa principalmente do celular; PWA é a forma de não ter app na
  Play Store/App Store cobrar 30%.

### Alternative C: 4ª codebase Web (Next.js / SPA pura)
- **Pros:** controle total da UX web; SSR; SEO.
- **Cons:** dobra superfície de manutenção; perde compartilhamento de componentes/RN.
- **Why rejected:** stack atual cobre 90% do que SSR/SEO traria; benefício não compensa custo.

## Consequences

### Positive
- UX web mobile próxima ao nativo (com fullscreen + viewport correto).
- Instalação no celular sem submeter à App Store.
- Cache via SW reduz latência percebida em 2ª visita.
- Bundle único Expo serve mobile + web.

### Negative
- **`isStandalone.ts` é load-bearing**: bug nele quebra UX iOS web.
- **Cache de SW pode bugar em deploy**: usuário ficar preso em bundle antigo. Mitigação:
  versionamento de SW + skipWaiting on activate (`[VALIDAR — implementação atual de skipWaiting]`).
- **Sem testes E2E de PWA**: regressões em manifest/SW só aparecem em produção. Mitigação:
  adicionar Lighthouse PWA score ao CI `[VALIDAR — não está no `deploy-hostinger.yml`]`.

### Risks
- **Risco**: Apple muda contrato de standalone iOS Safari (já mudou várias vezes).
  **Mitigação**: monitorar mudanças de iOS PWA; `isStandalone.ts` precisa ser adaptado.
- **Risco**: dev escreve `100vh` puro em CSS novo. **Mitigação**: lint rule
  `[VALIDAR — adicionar a constitution.md]` que proíbe `vh` direto em estilos web.
- **Risco**: SW serve bundle antigo após deploy. **Mitigação**: cache busting versionado em
  `expo export --platform web` + `Cache-Control` em nginx + skipWaiting.

## References

- [`public/manifest.json`](../../resenhai-expo/public/manifest.json) — manifest PWA
- [`public/sw.js`](../../resenhai-expo/public/sw.js) — Service Worker
- [`utils/isStandalone.ts`](../../resenhai-expo/utils/isStandalone.ts) — detect + enforce + viewport
- `app/+html.tsx` — meta tags PWA
- [`docker/nginx.conf`](../../resenhai-expo/docker/nginx.conf) — `Cache-Control` para web bundle
- [containers.md container "Web Static"](../../engineering/containers/) — atualizado para refletir PWA
