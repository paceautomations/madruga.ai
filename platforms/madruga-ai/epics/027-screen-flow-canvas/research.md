---
epic: 027-screen-flow-canvas
phase: phase-0
created: 2026-05-05
updated: 2026-05-05
sidebar:
  order: 1
---

# Research — Phase 0

Resolve `NEEDS CLARIFICATION` do Technical Context e consolida decisões fundamentadas. Cada tópico segue: Decision → Rationale → Alternatives Considered.

> **Nota**: Decisões 1-way-door da pitch.md (D1-D24) já estão capturadas em `decisions.md`. Este documento foca nas escolhas técnicas residuais que emergem ao detalhar implementação — sem retomar decisões já trancadas.

---

## R1. Stack visual — xyflow v12 (mantido) vs alternativas

**Decision**: `@xyflow/react v12.10.2` + custom nodes + custom edges + ELK build-time. Já presente no portal, zero custo marginal.

**Rationale**:
- xyflow v12 é o padrão moderno de canvas DAG em React (sucessor de react-flow); API estável, comunidade ativa, TypeScript native, ~600KB ungz mas tree-shakeable
- Custom nodes via `nodeTypes` permitem renderizar Chrome de device + WireframeBody + screenshot real sem fork
- Custom edges via `edgeTypes` + `EdgeLabelRenderer` cobrem 4 estilos (success/error/neutral/modal) com label flutuante clicável
- Performance flags built-in (`onlyRenderVisibleElements`, `nodesDraggable=false`) cobrem requisitos sem custom render loop

**Alternatives Considered**:
- **Reaflow** (~250KB) — mais leve mas mantenedor único e API menos estável; perde por confiabilidade de longo prazo.
- **react-digraph** — abandonado (último commit 2022); rejeitado.
- **Mermaid puro com `astro-mermaid`** — já em uso pra diagramas mas não suporta hotspots clicáveis sobre imagens reais nem custom nodes complexos; perde por capability.
- **D3 + custom render** — máximo controle mas ~3-5 dias só pra reimplementar pan/zoom/edge routing; não cabe no appetite.

---

## R2. Layout engine — ELK build-time vs Dagre client-side

**Decision**: ELK (`elkjs ^0.11.1`) configurado como `org.eclipse.elk.algorithm: 'layered'` rodando em build-time no Astro Node SSR. Layout pré-computado é serializado no HTML; client recebe positions estáticas e zero `elkjs` runtime.

**Rationale**:
- ELK gera layouts hierárquicos limpos com edge routing ortogonal — caso exato de screen flows (entry → main → branches)
- Build-time elimina ~500KB do bundle client e ~50-200ms de TTI
- `elkjs` já é dependência do portal (presumivelmente para outros usos); marginal cost zero
- ELK timeout 30s configurável (Decision #21) — abort do build com erro estruturado se exceder

**Alternatives Considered**:
- **Dagre client-side** (~150KB) — mais leve mas produz layouts feios em DAGs com branches paralelas (típico de screen flows); rejeitado por UX.
- **dagre-d3** — variação com renderer próprio (não combina com xyflow); descartado.
- **Custom force-directed (D3)** — fluido mas instável: nodes "flutuam" entre re-renders; rejeitado.
- **Hand-positioned (sem layout engine)** — força autor a definir `position: {x, y}` em todas as telas; rejeitado por UX (autor não deve fazer trabalho de layout). Mantido como **escape hatch opcional** pra casos com ciclo (validator detecta ciclo e força hand-position).

---

## R3. Determinism em screenshots — Playwright API vs flag no app

**Decision**: `addInitScript` (Date freeze + Math.random seed + animate stub) + `addStyleTag` (transitions/animations off) + `clearCookies()` + `serviceWorker.unregister()` + `page.route()` (mock endpoints voláteis declarados em `mock_routes`) + `storageState` (cookie de login pre-baked).

**Rationale**:
- Validation Evidence 2026-05-05: 2 telas (welcome + login) testadas em runs back-to-back contra `dev.resenhai.com` produziram PNGs byte-idênticos (md5 match) — caminho confirmado empiricamente
- Zero PR externo no resenhai-expo: invariante "zero edits externos" preservado (Decision #26)
- Custos: ~30 LOC de orquestração no `screen_capture.spec.ts`
- Risco residual: telas autenticadas com SW ativo (resenhai-expo tem `public/sw.js`) podem cachear respostas — mitigado por `serviceWorker.unregister()` antes de cada `page.goto` (Decision #18)

**Alternatives Considered**:
- **Flag `?screenshot=1` no app (PR externo)** — máximo controle mas exige coordenação cross-team contínua; rejeitado por custo de manutenção e quebra do invariante "zero edits externos". Mantido como **escalada incremental** (~10 LOC `data-volatile` em elementos crônicos) só se PNG noise virar problema mensurável após 5 runs em produção.
- **Visual regression (Percy/Chromatic)** — ferramentas pagas pra detectar diff visual, não pra reproduzir PNGs determinísticos; concern separado, fora de escopo (NO-GO list explícito).
- **`page.screenshot({ animations: 'disabled' })`** — só desabilita animações, não cobre Date.now/Math.random/SW staleness; insuficiente sozinho mas usado em conjunto com as outras técnicas.

---

## R4. Storage de imagens — Git LFS vs CDN externo

**Decision**: Git LFS na org `paceautomations` (plano Free: 500MB storage / 1GB bandwidth/mês). `.gitattributes` declara `*.png filter=lfs diff=lfs merge=lfs -text` no scope de `business/shots/`. Pre-commit hook Python rejeita PNG >500KB (FR-034).

**Rationale**:
- Mantém invariante "repo é a fonte da verdade" — sem credencial de write em CI, sem lifecycle externo, sem dependência de uptime
- Validação 2026-05-05: 0 objetos LFS em qualquer repo da org → 100% de quota disponível
- Estimativa: ~9MB ativo (1 plataforma × 30 telas × 300KB médio); ~50MB histórico ano 1 → ~10% da quota Free em storage e ~5% em bandwidth
- Portal Astro durante build resolve LFS server-side sob demanda (no Vercel ou Hostinger); cliente final recebe `<img src>` resolvido pra URL/pathname normal

**Alternatives Considered**:
- **Vercel Blob** — fácil mas introduz credencial write em CI + lifecycle de versões + dependência uptime; rejeitado por complexidade. **Mantido como migração trivial** (campo `image:` aceita URL) caso quota LFS aperte (trigger em 800MB/mês bandwidth ou 300MB storage — Decision #22).
- **AWS S3 + CloudFront** — overkill pra escala atual; introduz IAM, billing separado, configuração extra; rejeitado.
- **Commitar PNGs sem LFS** — repo tamanho explode (~30 telas × 300KB × N versões = GBs em meses); rejeitado.
- **Não commitar (gerar a cada build)** — quebra reprodutibilidade; PR review perde visibilidade de mudança visual; rejeitado.

---

## R5. Captura web pra apps mobile — Expo Web vs Maestro vs simulator

**Decision**: Playwright contra Expo Web staging (`https://dev.resenhai.com` já em produção). Único runner Linux ubuntu-latest no GitHub Actions. Profile `iphone-15` (393×852 viewport) para apps mobile, `desktop` (1440×900) para web puro.

**Rationale**:
- Validation Evidence 2026-05-05: dev.resenhai.com já é Expo Web em produção; team mantém compat ativamente (`react-native-web 0.21.2`, expo SDK 54, scripts `build:web` + `serve:static`); 8 PNGs já em `docs/app_info_photos/`
- Linux runner ~80% mais barato que macOS runner em GH Actions
- Fidelidade native ↓ ~10-15% em troca de complexidade ↓ ~70% — trade-off justificado para doc arquitetural (não QA visual)
- Risco residual: deps native-only (mapas, câmera, push) renderizam vazias em web — mitigação operacional (telas problemáticas ficam em mock visíveis)

**Alternatives Considered**:
- **Maestro** (mobile native) — flow-based, fidelidade 100% mas exige macOS runner ($) + Xcode + simulator; rejeitado pra v1. Possível epic futuro `screen-capture-native` na NO-GO list.
- **Detox** — automação E2E pra React Native; fidelidade alta mas curva íngreme + macOS runner; rejeitado.
- **Simulator screenshots manuais** — não scalable, drift permanente; rejeitado.
- **Capacitor / Cordova WebView** — não se aplica (resenhai-expo é Expo, não híbrido); descartado.

---

## R6. Auth automation — `storageState` vs login programático per-screen

**Decision**: `storageState` Playwright pre-baked via `e2e/auth.setup.ts` (que já existe no resenhai-expo). Captura reusa o JSON de cookies/localStorage por toda a sessão; não loga novamente entre telas.

**Rationale**:
- `e2e/auth.setup.ts` já existe e já é mantido pelo team do resenhai-expo — zero código novo
- Login uma única vez no início do workflow → reuso de cookies + tokens em todas as N telas → muito mais rápido
- Determinístico: mesmo storageState = mesma identidade do usuário entre runs

**Alternatives Considered**:
- **Login programático per-screen** — re-login a cada `page.goto` é lento (~2-5s extra por tela), introduz variabilidade temporal nos timestamps de session, viola determinism; rejeitado.
- **API token estático em env var** — alguns apps usam tokens longa-validade; resenhai-expo usa Supabase auth com refresh tokens, então `storageState` é o pattern correto.
- **OAuth flow simulado por Playwright** — overkill se o app já tem `auth.setup.ts` funcionando.

---

## R7. Bundle size budget — `size-limit` vs `bundlesize` vs `lighthouse-ci`

**Decision**: `size-limit ^11` + `@size-limit/preset-app` como devDependencies do portal. Configuração em `portal/size-limit.config.json` define budget per-route (`/<platform>/screens/*` esperado 700-900KB ungz após baseline da fase 2; outras rotas mantêm tamanhos atuais).

**Rationale**:
- `size-limit` é o padrão moderno; integra direto com Webpack/Vite/esbuild output e CI
- Failing build é clear ("Bundle excedeu: 920KB vs 900KB limit") — gate medível
- Suporta multiple targets (uma config gera N gates: rota /screens/* + rotas demais)

**Alternatives Considered**:
- **`bundlesize`** — antigo, menos manutenido (último release 2021); rejeitado.
- **`lighthouse-ci`** — overkill pra rota estática SSG; mede TTI/LCP/etc mas é instável em CI runners (variabilidade de hardware); rejeitado.
- **Manual measurement (commitar build artifacts)** — não é gate, é audit retroativo; rejeitado.

---

## R8. A11y testing — `axe-core` vs `pa11y` vs manual

**Decision**: `@axe-core/playwright` numa única smoke test no E2E spec (custo baixo). Cobertura mínima: aria-labels presentes em nodes, edges com role apropriado, keyboard nav (Tab/Enter) funcional. Color-blind verification via `jest-image-snapshot` em modo simulator (deuteranopia + protanopia) — opcional (gate visual).

**Rationale**:
- `axe-core` é padrão WCAG, baseline confiável, ~zero false positives em ambiente controlado
- Smoke test é suficiente — full a11y audit é overkill para rota interna de doc

**Alternatives Considered**:
- **`pa11y`** — mais antigo, similar coverage; `axe-core` tem melhor integração com Playwright; rejeitado.
- **Manual testing** — não-scalable; gate manual quebra fast iteration; rejeitado.
- **Lighthouse a11y score** — score numérico arbitrário, instável em CI; rejeitado.

---

## R9. Service Worker cleanup — `unregister()` vs `caches.delete()` vs reload-only

**Decision**: `navigator.serviceWorker.getRegistrations()` + `Promise.all(rs.map(r => r.unregister()))` + `caches.delete()` (todos os caches) ANTES de cada `page.goto`. Acionado quando `clear_service_workers: true` em `capture.determinism`.

**Rationale**:
- `unregister()` remove o SW do escopo; `caches.delete()` limpa Cache Storage usado pelo SW
- `clearCookies()` complementa removendo session storage residual
- Validation Evidence 2026-05-05 testou só rotas públicas (welcome, login) que não exercitam SW; telas autenticadas DEVEM passar pelo cleanup pra garantir determinism

**Alternatives Considered**:
- **Reload-only** (`page.reload({ waitUntil: 'networkidle' })`) — não limpa SW state, pode mostrar dados cacheados de captura anterior; rejeitado.
- **Bypass SW** (`request.headers['service-worker'] = 'script'`) — só evita registro novo, não limpa o ativo; insuficiente.
- **`page.context().clearCookies()` apenas** — não cobre Cache Storage do SW; insuficiente.
- **Disable SW via Chrome flag** — possível mas afeta debugability; descartado em favor de `unregister()` explícito.

---

## R10. Concurrency em GH Actions — `concurrency` block vs lock-via-issue

**Decision**: Bloco `concurrency` no `capture-screens.yml`:

```yaml
concurrency:
  group: "capture-${{ matrix.platform }}"
  cancel-in-progress: false
```

Per-platform group; runs subsequentes para a mesma plataforma são enfileirados (não cancelados). Runs para plataformas diferentes rodam em paralelo (matrix).

**Rationale**:
- Built-in do GH Actions, zero custo
- `cancel-in-progress: false` preserva trabalho do run atual; se 2 dispatches manuais batem, segundo aguarda
- Per-platform group evita sequencialização desnecessária entre plataformas independentes

**Alternatives Considered**:
- **Lock-via-issue** (criar issue antes de rodar, fechar após) — pattern complexo para problema simples; rejeitado.
- **Sequential matrix** (`max-parallel: 1`) — bloqueia plataformas independentes; rejeitado.
- **Sem concurrency control** — race em writes ao YAML; rejeitado por correctness.

---

## R11. Schema versioning — JSON Schema `$schema` vs custom field

**Decision**: Campo customizado `schema_version: 1` no topo de cada `screen-flow.yaml`. Validator rejeita ausência ou versão desconhecida. JSON Schema (`$id` ou `$schema`) é interno do `screen-flow.schema.json` (referência ao draft 2020-12) — não exposto ao autor humano.

**Rationale**:
- `schema_version` é simples, legível, parser-agnostic; autor humano consegue ler e entender
- JSON Schema `$schema` é metadata da própria spec do schema, não do dado validado
- Migration path explícito (`migrate_v1_to_v2.py`) quando vier breaking change

**Alternatives Considered**:
- **`$schema` no YAML do dado** — confunde dois conceitos (schema de schema vs schema do dado); rejeitado.
- **Sem versioning** — primeira mudança breaking quebra todas as plataformas silenciosamente; rejeitado por correctness.
- **Hash do schema como versioning** — opaco, autor não consegue entender; rejeitado.

---

## R12. Pre-commit hook — Python vs Bash vs Husky

**Decision**: Hook em Python (`pre_commit_png_size.py` ~30 LOC) registrado via `pre-commit` framework (já em uso no repo). Hook lê arquivos `*.png` modificados em `business/shots/` e rejeita se >500KB.

**Rationale**:
- `pre-commit` framework já presumido em uso no repo (CLAUDE.md menciona convenção); não introduz nova ferramenta
- Python coerente com stack do `.specify/scripts/`
- Hook modular: outros hooks (validator) seguem mesmo pattern

**Alternatives Considered**:
- **Bash hook** — funciona mas Python é mais legível e portável; pre-commit framework prefere Python/Node.
- **Husky** — Node-based, exige `.husky/` dir + `package.json` integration; pre-commit framework é stack-neutral; rejeitado por preferência do repo.
- **CI-only check (sem pre-commit)** — autor descobre tarde; rejeitado por DX.

---

## R13. Test framework — Vitest vs Jest

**Decision**: `vitest ^1.5+` para testes unitários do portal (component tests). Justificativa: integração nativa com Vite (Astro 6 usa Vite), execução paralela rápida, API compatível com Jest (`jest-image-snapshot` funciona via plugin).

**Rationale**:
- Astro 6 + React 19 + Vite stack canônico de 2026 prefere Vitest
- API quase idêntica a Jest — curva de aprendizado zero pra dev que veio de Jest
- `jest-image-snapshot` funciona via plugin de compatibilidade

**Alternatives Considered**:
- **Jest** — mais maduro mas exige config Webpack/Babel duplicada (Astro usa Vite); rejeitado por overhead.
- **node:test (built-in Node)** — minimalista mas snapshot testing precário; rejeitado.
- **Bun test runner** — rápido mas ecossistema menos maduro; rejeitado.

> **Decisão registrada como nova em `decisions.md` (#27 a ser adicionada na transição para tasks)**.

---

## R14. JSON Schema validator (Python) — `jsonschema` vs `pydantic` vs custom

**Decision**: `jsonschema ^4.17` para validação principal de YAML contra `screen-flow.schema.json`. Validações complementares (refs `from`/`to` consistentes, IDs únicos, charset de `screen.id`) implementadas em Python puro no `screen_flow_validator.py`.

**Rationale**:
- `jsonschema` é canônico para validação JSON Schema draft 2020-12; baixo custo
- Já presumida disponível no `requirements.txt` do repo (uso por outros scripts)
- Validações cross-field (refs entre flows e screens) saem do JSON Schema scope — implementadas direto em Python

**Alternatives Considered**:
- **Pydantic v2** — validação com type system, mas duplicaria a definição (schema JSON + Pydantic models); rejeitado por DRY.
- **Custom validator (Python puro)** — overkill, reescreve `jsonschema`; rejeitado.
- **`fastjsonschema`** — mais rápido mas menos manutenido; `jsonschema` é o padrão.

> **Decisão registrada como nova em `decisions.md` (#28 a ser adicionada na transição para tasks)**.

---

## Summary Table

| # | Topic | Decision | Reference |
|---|-------|----------|-----------|
| R1 | Stack visual | xyflow v12 + custom nodes/edges | Decision #4 |
| R2 | Layout engine | ELK build-time SSR | Decision #4 (cont.) |
| R3 | Determinism | Playwright addInitScript + route + storageState + SW cleanup | Decisions #8, #18 |
| R4 | Storage imagens | Git LFS Free quota | Decision #7 |
| R5 | Captura mobile | Playwright + Expo Web staging Linux runner | Decision #6 |
| R6 | Auth | storageState pre-baked (e2e/auth.setup.ts existente) | platform.yaml schema (#13) |
| R7 | Bundle budget | size-limit per-route | Decision #24 |
| R8 | A11y testing | @axe-core/playwright smoke + jest-image-snapshot color-blind | Decision #18 |
| R9 | SW cleanup | unregister() + caches.delete() + clearCookies() | Decision #18 |
| R10 | Concurrency | GH Actions concurrency block per-platform | Decision #20 |
| R11 | Schema versioning | Custom schema_version: 1 field | Decision #21 |
| R12 | Pre-commit | Python via pre-commit framework | Decision #7 |
| R13 | Test framework | Vitest (novo, registrar #27) | Phase 1 emergent |
| R14 | JSON validator | jsonschema lib + custom Python (novo, registrar #28) | Phase 1 emergent |

**Conclusão**: Todos os `NEEDS CLARIFICATION` resolvidos. Prosseguir para Phase 1 (data-model + contracts + quickstart).
