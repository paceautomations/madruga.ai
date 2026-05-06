---
title: "ADR-022: Screen Flow Canvas — vocabulário fechado, renderer SSG e captura determinística"
status: accepted
date: 2026-05-05
decision: Adicionar feature L1 opcional (`madruga:business-screen-flow`) que produz
  `business/screen-flow.yaml` por plataforma com vocabulário fechado (10 components +
  4 edges + 6 badges + 3 capture states), renderiza esse YAML como canvas Figma-like
  (xyflow v12 + ELK build-time + SSG) numa nova aba **Screens** condicional do portal,
  captura screenshots reais via Playwright determinístico contra staging Web, e fecha
  o loop de drift via reverse-reconcile lendo `path_rules` declarativos per-platform.
alternatives: Whimsical/Balsamiq como ferramenta externa; Mermaid puro para fluxos;
  Maestro para captura de telas em simulator iOS/Android; CDN externo (Vercel Blob,
  S3) em vez de Git LFS; flag `?screenshot=1` no app em vez de determinism via Playwright;
  Dagre client-side em vez de ELK build-time
rationale: Vocabulário fechado mantém o renderer simples e comparável cross-platform;
  ELK build-time entrega layouts hierárquicos limpos com zero peso runtime; determinism
  via Playwright API (~80% reproducibility grátis) evita coordenação cross-team com
  apps; Git LFS Free quota tem 16x headroom validado; capture é black-box contra
  staging existente (zero commits no `paceautomations/resenhai-expo`).
---
# ADR-022: Screen Flow Canvas — vocabulário fechado, renderer SSG e captura determinística

## Status

Accepted — 2026-05-05 (epic 027 — `epic/madruga-ai/027-screen-flow-canvas`)

## Contexto

Stakeholders (designers + product + engenharia) precisavam de uma representação visual unificada das telas reais de cada plataforma — wireframes intercambiáveis com screenshots, conectados por fluxos navegáveis — sem depender de ferramentas externas (Whimsical, Figma) que se desconectam da source-of-truth do código. O ciclo "design → spec textual → tela construída → screenshot manual em PR description" produzia drift permanente entre o que stakeholders viam e o que o app entregava.

Restrições adotadas:

1. **Sem novas ferramentas pagas**: ferramenta externa = mais um silo, mais uma dívida de manutenção, mais um lugar pra desync.
2. **Repo é fonte de verdade**: YAML descritivo + PNGs versionados; nada de "vai ver no Figma".
3. **Feature opcional**: nem toda plataforma precisa do canvas (madruga-ai e prosauai opted-out no v1).
4. **Zero commits externos**: a captura precisa rodar contra staging existente sem PR no repo do app.
5. **Determinism**: PNGs reproducíveis em CI para evitar diff noise em PRs.

## Decisão

Aplicar uma combinação de 28 decisões 1-way-door agrupadas em 7 áreas, com kill criteria explícitos por área:

### A. Estrutura de pipeline e escopo

1. **Skill `madruga:business-screen-flow`** é nó L1 opcional, entre `business-process` e `tech-research`, gate `human` (Decision #1).
2. **Numeração NNN=027** (próximo monotônico após 026); gap 025 permanente (Decision #2).
3. **Plataformas-alvo v1**: resenhai-expo pilot único; madruga-ai + prosauai opt-out — valida 3 modos da feature opcional (Decision #3).

### B. Stack visual e vocabulário fechado

4. **Stack**: `@xyflow/react v12` + `elkjs ^0.11.1` build-time + SSG via `renderToStaticMarkup`, hidratação `client:visible` (Decision #4).
5. **Vocabulário fechado LOCKED**: 10 body component types (`heading`, `text`, `input`, `button`, `link`, `list`, `card`, `image`, `divider`, `badge`) + 4 edge styles (`success`, `error`, `neutral`, `modal`) + 6 badges (`WIREFRAME` / `AGUARDANDO` / `WEB BUILD v<x>` / `iOS v<x>` / `WEB v<x>` / `FALHOU`) + 3 capture states (`pending` / `captured` / `failed`) — Decisions #5, #10. PRs questionando vocab durante implementação são rejeitados sem discussão.
6. **Performance flags fixos no xyflow**: `nodesDraggable=false`, `nodesConnectable=false`, `elementsSelectable`, `onlyRenderVisibleElements`, custom nodes memoizados (Decision #12).
7. **Wireframe design system distinto** (D1): paleta limitada a 6 tons cinza + 1 accent suave + tipografia mono ou hand-drawn (Caveat/Architects Daughter via Google Fonts). Sinaliza honestamente "isso é spec, não design final" (Decision #15).
8. **Chrome mínimo, sem teatro** (D2): bezel reduzido a moldura com `border-radius` + 1 label discreto (`iPhone 15 / 393×852`). Sem status bar fake. Saving ~150 LOC vs design original (Decision #16).
9. **Hotspots discoverability** (D3): visíveis por default com numeração (1, 2, 3) + outline 1px dashed; toggleable via tecla `H`; click anima edge antes do `fitView` no destino (Decision #17).
10. **A11y + dark mode invariantes NÃO-NEGOCIÁVEIS** (D4): tokens CSS variables (`--screen-bg`/`-fg`/`-accent`/`-edge-*`), edges com pattern adicional além de cor (sólido/tracejado/pontilhado) pra color-blind, `aria-label` em cada node, keyboard nav `Tab/Enter` (Decision #18).

### C. Schema, validação e versionamento

11. **`schema_version: 1` obrigatório no topo de cada YAML** (A8): validator rejeita ausência ou versão desconhecida; migration path documentado pra v2 (Decision #22).
12. **`platform.yaml.screen_flow` schema LOCKED** com 2 níveis: `{enabled, skip_reason}` no toggle level + `capture: {base_url, serve, device_profile, auth, determinism, expo_web, path_rules, test_user_marker}` quando `enabled=true`. Credenciais sempre via env vars (`<PREFIX>_TEST_EMAIL`/`<PREFIX>_TEST_PASSWORD`); skip_reason obrigatório quando `enabled=false` (Decision #13).
13. **Skill upstream obrigatório** (A6): `madruga:business-screen-flow` LÊ `business/process.md` como input — ancora screens nas user journeys já documentadas; sem `process.md` = skill rejeita (Decision #20).

### D. Captura determinística

14. **Captura via Playwright único**, profiles `iphone-15` / `desktop`, sem Maestro, sem macOS runner (Decision #6). VALIDADO 2026-05-05 com teste real contra `dev.resenhai.com` (welcome+login byte-idêntico md5 em 2 runs back-to-back).
15. **Determinism via Playwright `addInitScript` (Date/Math/animate) + `page.route` (mocks endpoints voláteis) + `storageState` (cookie login pre-baked)**. Zero PR externo no v1. Escalada incremental pra ~10 LOC `data-volatile` apenas se PNG noise ≥3 telas após 5 runs em produção (Decision #8).
16. **Hotspots coords normalizadas 0-1**: YAML declara `testid: "<existing-id>"` por componente body com ação em flows; capture usa `boundingBox` de `[data-testid="<id>"]`. Sem nova convenção no app — usa testIDs já existentes (54 confirmados em resenhai-expo) — Decision #9.
17. **Service Worker cleanup** entre captures (A1): `clearCookies()` + `navigator.serviceWorker.unregister()` ANTES de cada `page.goto`. Crítico em telas autenticadas; resenhai-expo tem `public/sw.js` 5.4 KB ativo — Decision #19.

### E. Storage, drift e quota

18. **Storage Git LFS + pre-commit hook PNG ≤500KB** (Decision #7). Plano Free GitHub paceautomations: 500MB/1GB-mês, validado 2026-05-05 com 0 uso atual e ~16x headroom.
19. **LFS lifecycle policy futura** (A5): ano 1 confortável (~9 MB ativo, ~50 MB histórico). Trigger de revisão: bandwidth >800 MB/mês ou storage >300 MB → ano 2 avalia `git lfs prune` mensal em CI ou migração pra Vercel Blob (Decision #23).
20. **Drift detection via reverse-reconcile lendo `path_rules` per-platform** de `platform.yaml.screen_flow.capture.path_rules` (regex declarativo, NÃO hardcoded em Python). Cada plataforma declara seus padrões — resenhai-expo usa `app/(auth)/login.tsx` (regex hardcoded `src/screens/*Screen.tsx` nunca casaria) — Decision #11.

### F. Operacional e CI

21. **GH Actions concurrency safety** (A7): `capture-screens.yml` declara `concurrency: { group: "capture-${{ matrix.platform }}", cancel-in-progress: false }`. Evita race em writes ao YAML quando dispatch manual encontra auto-trigger (Decision #21).
22. **Bundle budget mensurável** (C1): `size-limit` no CI define budget concreto da rota `/screens/*`; falha de build se exceder. Substitui claim aspiracional "TTI <1.5s" por gate medível (Decision #24).
23. **Bundle baseline real é ~164 KB ungz, não 700-900 KB**: medição via `npx size-limit` contra `ScreenFlowCanvas*.js` (143.11 kB) + `screens.css` (20.64 kB) = **163.75 KB ungz**. xyflow + elkjs já compartilhados com outras rotas (control-panel, observability). Budget enforced = baseline × 1.05 (5% headroom): JS 150 KB + CSS 22 KB (Decision #27).
24. **`size-limit` usa preset `preset-app` com `brotli: false` + `gzip: false`**: medição honesta de bytes ungz (o que o browser baixa antes do decode); brotli/gzip são propriedades do servidor, não do bundle. Aceito +20s de CI por visibilidade de tempo de execução em hardware lento (Decision #28).

### G. Testes e qualidade

25. **Test pyramid explícito** (C2) — 4 layers como gate de DoD (Decision #25):
    - (a) `pytest` unit ≥30 casos do validator
    - (b) RTL + `vitest` component (3-state `ScreenNode` + 4 `ActionEdge` styles)
    - (c) Playwright + `jest-image-snapshot` visual com fixture de 8 telas, tolerância 1px
    - (d) 1 spec E2E integração capture→commit→render
26. **`vitest` como test framework escolhido para portal** (decisão consolidada no plan): vitest é coerente com o stack Vite/Astro, suporta `@testing-library/react` nativamente, e alinha com o portal existente. Alternativas rejeitadas: Jest (precisa transformer extra para ESM/Astro), Mocha (sem watch ergonomics).
27. **`jsonschema>=4.0` como única dep Python adicional** (decisão consolidada no plan): `pyyaml` já está no repo; `jsonschema` é necessário para validar `screen-flow.schema.json` contra o YAML por plataforma. Stdlib não tem JSON Schema validator equivalente. Trade-off aceito — ADR-021 recomenda stdlib + pyyaml mas a feature exige formal schema validation.
28. **Invariante "zero edits externos"** (Decision #26): nenhum commit em `paceautomations/resenhai-expo` (ou outro repo bound) é necessário pra epic shippar. Capture é black-box contra staging (`dev.resenhai.com`). Todos artefatos (YAML, shots, scripts, workflows) vivem em `madruga.ai`. Resenhai-expo só precisa: (a) manter staging deployado, (b) manter testIDs existentes, (c) prover credenciais de test user via env vars do CI.

### Appetite

**10 working days** (revisado de 8 → 10 após Crítica 1 incorporar 14 itens — paleta wireframe, a11y/dark mode invariantes, SW cleanup, path_rules per-platform, schema versioning, test pyramid concreto). Fase 2: 3→3.5d, Fase 5: 1→1.5d (Decision #14).

## Consequências

### Positivas

- **Source-of-truth visual unificada**: stakeholders vêem o mesmo canvas que o repo entrega — drift fica visível em PRs.
- **Vocabulário fechado mantém o renderer simples** (~300 LOC): zero risco de explosão de complexidade conforme novas plataformas adotam.
- **Captura determinística reproduz screenshots em CI**: PRs param de mostrar diff noise; reviewers focam em mudanças intencionais.
- **Bundle gate concreto via `size-limit`**: ~164 KB ungz inicial vs claim aspiracional original — baseline real desbloqueia evolução incremental sem regressão silenciosa.
- **Zero edits externos**: o epic shipa sem coordenação com o time do `resenhai-expo` (validado: app já tem staging + testIDs + Web build).
- **Feature opcional + opt-out explícito**: madruga-ai e prosauai não precisam adotar; bloco `screen_flow.enabled=false` + `skip_reason` documenta a escolha.

### Negativas

- **`jsonschema` é a primeira dep Python externa adicionada após ADR-021** que recomenda "stdlib + pyyaml". Justificada por necessidade formal de schema validation, mas estabelece precedente — futuras adições devem passar pelo mesmo crivo.
- **Vocabulário fechado é 1-way-door**: adicionar um 11º component type ou 5º edge style requer ADR + migração de YAMLs existentes + atualização do renderer + testes. Custo intencional pra prevenir creep.
- **Determinism via Playwright API tem teto de ~80%**: telas com PNG noise ≥3 após 5 runs em produção exigem escalada (~10 LOC `data-volatile` no app) — só na epic 027.x se acontecer.
- **Captura é Linux-only via GH Actions ubuntu-latest**: telas que dependem de Safari/iOS-specific behavior não são capturáveis no v1.
- **Git LFS Free quota é finita**: ano 1 confortável validado, mas trigger em 800 MB/mês bandwidth ou 300 MB storage exige ação operacional (Decision #23).

### Mitigações em vigor

- **Test pyramid 4 layers** como gate de DoD evita regressão visual silenciosa.
- **Size-limit no CI** previne crescimento descontrolado do bundle.
- **`schema_version: 1`** + reject de versões desconhecidas no validator quebra alto e cedo se schema mudar sem migration.
- **Feature flag opt-in via `screen_flow.enabled`** permite desligar plataforma com problema sem quebrar outras.
- **Concurrency block per-platform** no workflow CI evita corrupção de YAML em dispatches simultâneos.

## Kill criteria

Esta ADR deve ser revisitada (potencialmente revertida ou superseded) se:

1. **PNG noise crônico**: ≥3 telas em produção mostrando diff noise após 5 runs back-to-back, mesmo com `addInitScript` + `page.route` + `storageState` + SW cleanup ativos. Implica que determinism via Playwright API é insuficiente — escalada pra flag `?screenshot=1` no app vira mandatória.
2. **LFS quota estourar**: bandwidth >1 GB/mês ou storage >500 MB persistente por 2 meses consecutivos. Implica migração pra Vercel Blob ou S3 + CDN — campo `image:` aceita URL como contingência projetada.
3. **Vocabulário insuficiente**: ≥5 plataformas requisitando o mesmo 11º component type ou 5º edge style com casos legítimos não-modeláveis com vocab atual. Implica review formal do schema (incrementar `schema_version` para 2).
4. **Bundle exceder 250 KB ungz** (50% acima do baseline) sem feature óbvia justificando. Implica review de deps shared com outras rotas (xyflow, elkjs) ou code-splitting agressivo.
5. **Captura demorar >10 min/run** em ≥3 plataformas habilitadas. Implica paralelização (matrix por screen) ou redução do scope de captura.

## Referências

- Pitch: `platforms/madruga-ai/epics/027-screen-flow-canvas/pitch.md`
- Spec: `platforms/madruga-ai/epics/027-screen-flow-canvas/spec.md`
- Plan: `platforms/madruga-ai/epics/027-screen-flow-canvas/plan.md`
- Decisions log: `platforms/madruga-ai/epics/027-screen-flow-canvas/decisions.md`
- Schema: `.specify/schemas/screen-flow.schema.json`
- Skill: `.claude/commands/madruga/business-screen-flow.md`
- ADRs relacionadas:
  - ADR-003 (Astro Starlight portal) — base do renderer
  - ADR-004 (file-based storage) — YAML como source-of-truth
  - ADR-020 (Mermaid inline diagrams) — alternativa rejeitada para fluxos
  - ADR-021 (bare-lite dispatch) — recomenda stdlib+pyyaml; este ADR justifica exceção pra `jsonschema`
- Validation Evidence: 2026-05-05 — teste determinism contra `dev.resenhai.com` (welcome+login md5 byte-idêntico em 2 runs)
