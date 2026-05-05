---
title: "Epic 027 — Screen Flow Canvas"
epic: 027-screen-flow-canvas
status: drafted
appetite: 2 weeks
created: 2026-05-05
updated: 2026-05-05
sidebar:
  order: 27
---

# Epic 027 — Screen Flow Canvas

## Problema

L1 do madruga produz documentos densos em texto (vision, solution-overview, process) mas não tem artefato visual que mostre **como o produto se parece** e **como as telas se conectam**. Stakeholder não-técnico lê 80KB de markdown sem formar mental model do que vai ser entregue. Plataformas brownfield (resenhai-expo) já têm telas construídas mas a documentação não captura nada disso.

A consequência é drift permanente entre documentação e realidade. Hoje, alguém querendo entender o fluxo de uma plataforma precisa: (1) ler 3 markdowns longos, (2) abrir o app real (se já existe), (3) inferir as transições. Não há nenhum lugar onde "qual botão leva pra qual tela" esteja explícito e versionado.

Para plataformas greenfield, o problema é o inverso: a doc precisa servir como spec do que vai ser construído, mas não há vocabulário compartilhado entre business e engineering pra descrever telas de forma consistente. Cada autor inventa sua própria notação, o renderer precisa cobrir N variantes, e a comparabilidade entre plataformas se perde.

A solução precisa funcionar em três modos sem ramificar a infraestrutura: greenfield (tudo wireframe mock), brownfield (screenshot real onde a tela existe), e plataformas headless/tooling onde o conceito de "tela" não se aplica (opt-out explícito).

## Appetite

**10 working days** — revisado em 2026-05-05 após Crítica 1 (design + arquitetura). Saída inicial era 10 dias (estimativa conservadora), reduzido pra 8 dias após Validation Evidence, agora de volta a 10 com 14 itens incorporados da crítica (paleta wireframe distinta, a11y + dark mode invariantes, SW cleanup, path_rules per-platform, schema versioning, test pyramid concreto). Hard timebox Shape Up — sem buffer adicional.

## Dependências

**Arquiteturais (já satisfeitas)**:
- `engineering/blueprint.md` — Astro 6 + Starlight, React 19, @xyflow/react v12, SQLite WAL, Mermaid via astro-mermaid
- `engineering/domain-model.md` — modelo do pipeline DAG existente (referência pra padrão de artefato L1)
- ADR-003 — escolha React/Astro pra portal
- ADR-020 — Mermaid inline em .md (referência de como diagramas vivem na doc)

**Externas — todas validadas em 2026-05-05**:
- ✅ **Quota Git LFS** na org `paceautomations`: plano **Free** (500 MB storage, 1 GB bandwidth/mês), uso atual = 0 objetos LFS em qualquer repo, headroom ~16x sobre estimativa do epic (~9MB com 1 plataforma habilitada). Bandwidth é o eixo a monitorar (clones CI com `lfs: true`)
- ✅ **Expo Web do resenhai-expo já roda em produção**: staging em `https://dev.resenhai.com` é a build web. Audit de deps **não é mais necessário** — o team já mantém compatibilidade web (`react-native-web 0.21.2`, expo SDK 54, scripts `build:web` + `serve:static`). 8 PNGs em `docs/app_info_photos/` provam captura funciona
- ✅ **Determinism via Playwright validada com teste real** (2 runs back-to-back contra dev.resenhai.com): welcome + login produziram PNGs **byte-idênticos** (md5 match) com `addInitScript` (Date/Math/animate) + `addStyleTag` + `networkidle`. Caminho 1 confirmado, zero PR externo necessário
- (Não-bloqueante) Test user dedicado no Supabase staging do resenhai-expo via `e2e/auth.setup.ts` (que **já existe**) — credenciais via env vars `RESENHAI_TEST_EMAIL`/`RESENHAI_TEST_PASSWORD`

## Solution

Nova skill L1 **opcional** `madruga:business-screen-flow` (entre `business-process` e `tech-research`, padrão `optional: true` igual `codebase-map`) que gera `business/screen-flow.yaml` por plataforma. YAML carrega telas + transições + estado de captura.

Portal ganha aba **Screens** na sidebar (renderizada condicionalmente — só aparece se a plataforma tem `screen-flow.yaml`), alimentada por canvas xyflow Figma-like com:
- **Custom nodes** com chrome de device (mobile bezel SVG ou desktop chrome) renderizando wireframe (greenfield) ou screenshot real (brownfield)
- **Custom edges** com 4 estilos visuais (success/error/neutral/modal) e label clicável
- **Hotspots** sobrepostos às imagens reais permitindo click em botão → câmera voa pra tela destino com easing
- **Layout automático** via ELK em build-time (zero peso elkjs no bundle do client)

Captura de telas reais via Playwright unificado: viewport iPhone 15 pra plataformas mobile (após `npx expo export -p web`), viewport desktop pra web. Único runner Linux no GitHub Actions, sem macOS, sem Maestro, sem simuladores.

resenhai-expo é o caso piloto único neste epic — plataforma mais complexa do conjunto e a única com `screen_flow.enabled: true` em v1. madruga-ai e prosauai entram com `enabled: false` (com `skip_reason` documentado), validando o caminho de opt-out e provando que a feature é genuinamente opcional na L1.

## Captured Decisions

| # | Área | Decisão | Referência arquitetural |
|---|------|---------|------------------------|
| 1 | DAG L1 | Skill `madruga:business-screen-flow` é nó **opcional** (igual `codebase-map`), entre `business-process` e `tech-research`, gate `human` | pipeline-dag-knowledge.md tabela L1 |
| 2 | Numeração | Epic NNN=**027** (próximo monotônico após 026), gap 025 permanente | Convenção em `platforms/madruga-ai/epics/` |
| 3 | Plataformas-alvo | **resenhai-expo** = pilot único (`enabled: true`); **madruga-ai** + **prosauai** = opt-out (`enabled: false`) — valida 3 modos da feature opcional | platform.yaml.screen_flow schema (Decision #13) |
| 4 | Stack visual | Renderer = **@xyflow/react v12** + ELK build-time + SSG via `renderToStaticMarkup`; layout pré-computado, hidratação `client:visible` | blueprint.md §1 (React+Astro), ADR-003 |
| 5 | Vocabulário | Body = **10 types LOCKED** (`heading, text, input, button, link, list, card, image, divider, badge`). Edges = **4 styles LOCKED** (`success, error, neutral, modal`) | screen-flow.schema.json (introduzido) |
| 6 | Captura | **Playwright único** com profiles device — `iphone-15` default mobile, `desktop` 1440×900 default web. Sem Maestro, sem macOS runner | [VALIDAR] auditoria de deps Expo dia 1 |
| 7 | Storage | **Git LFS** com pre-commit hook validando PNG ≤500KB. Plano Free GitHub: 500MB storage / 1GB bandwidth/mês. Estimado 25-30MB total → ~16x headroom em storage. Bandwidth monitorado | .gitattributes + Free plan paceautomations |
| 8 | Determinism | **Playwright `addInitScript` + `page.route()` + `storageState`** resolvem ~80% sem tocar no app: congela `Date.now()`/`Math.random()`, mocka endpoints voláteis (notifications, unread counts), reusa cookie de login. **Zero PR externo no v1**. Escalar pra `data-volatile` no app (~10 LOC) só se PNG noise virar problema mensurável após 5 runs | Playwright docs (addInitScript, route, storageState) |
| 9 | Hotspots | Coords **normalizadas 0-1** (não pixels). YAML declara `testid: "<existing-testid>"` por componente body que tem ação em `flows` — captura usa `boundingBox` de `[data-testid="<id>"]`. **Sem nova convenção no app** — usa testIDs já existentes (54 em resenhai-expo). **Visíveis por default** com badge numerado (1, 2, 3) + outline 1px dashed. Toggle show/hide via tecla `H` | screen-flow.schema.json + 54 testID usages confirmados |
| 11 | Drift detection | Reverse-reconcile lê `platform.yaml.screen_flow.capture.path_rules` (regex declarativo per-platform, NÃO hardcoded em Python) → marca `capture.status: pending` no YAML. Resenhai-expo: `app/\(auth\)/(\w+)\.tsx` + `app/\(app\)/(\w+)\.tsx`. Cada plataforma define suas próprias rules baseado no framework | reverse_reconcile_aggregate.py + per-platform path_rules schema |
| 10 | Badge taxonomy | 5 valores LOCKED: `WIREFRAME`, `AGUARDANDO`, `WEB BUILD v<x>`, `iOS v<x>`, `WEB v<x>` | ScreenNode renderer |
| 12 | Performance | xyflow runtime flags fixos: `nodesDraggable=false nodesConnectable=false elementsSelectable onlyRenderVisibleElements`. Custom nodes memoizados | xyflow performance docs |
| 13 | platform.yaml.screen_flow schema | Bloco LOCKED com 2 níveis: `{enabled, skip_reason}` + `capture: {base_url, serve, device_profile, auth, determinism, expo_web, path_rules}`. Auth via `storage_state_path` + `test_user_env_prefix` (credenciais sempre via env vars, nunca em arquivo). Mock routes declarativos. Ver "Per-platform config examples" abaixo | platform.yaml validator (introduzido) |
| 14 | Wireframe design system | Linguagem visual **distinta** de "app real": paleta limitada a 6 tons cinza + 1 accent suave (default azul-acinzentado), tipografia mono ou hand-drawn (`Caveat`/`Architects Daughter` via Google Fonts), border-radius padronizado, sem sombras pesadas, sem gradientes. Sinaliza honestamente "isso é spec, não design final". Custos: ~50 LOC adicional no `WireframeBody.tsx`, ~5KB de Google Font preloaded | Whimsical/Balsamiq pattern + brand consistency |
| 15 | Chrome mínimo (sem teatro) | Bezel reduzido a moldura com border-radius + 1 label discreto (`iPhone 15 / 393×852`). **Sem** status bar fake "9:41 100% bateria" — convenção de keynote Apple sem valor em doc arquitetural. Economia: ~150 LOC vs design original | YAGNI principle |
| 16 | Hotspots discoverability | Visíveis por default com numeração (`1`, `2`, `3`) + outline 1px dashed. Toggleable via tecla `H` ou botão UI. Funciona em touch (sem hover) e desktop. Click anima edge sendo desenhada antes do `fitView` no destino | UX discoverability + WCAG 2.5.5 |
| 17 | A11y + dark mode invariantes | (a) Tokens CSS variáveis, nunca cores literais — `--screen-bg`, `--screen-fg`, `--screen-accent`, `--edge-success` etc. (b) Edges com pattern adicional além da cor (sólido/tracejado/pontilhado) — redundância visual pra color-blind. (c) `aria-label` em cada node descrevendo a tela. (d) Keyboard nav: Tab move foco entre nodes, Enter aciona hotspot focado. NÃO-NEGOCIÁVEL no v1 | WCAG 1.4.1, 2.1.1, Starlight dark mode tokens |
| 18 | Determinism cleanup | `addInitScript` + `addStyleTag` é insuficiente em telas autenticadas com Service Worker. Capture script DEVE: `await ctx.clearCookies()` + `await page.evaluate(() => navigator.serviceWorker?.getRegistrations().then(rs => Promise.all(rs.map(r => r.unregister()))))` ANTES de cada `page.goto`. Resenhai-expo tem SW ativo (`public/sw.js`) | observação direta + risco real fase 4 |
| 19 | Skill upstream | Skill `madruga:business-screen-flow` LÊ `business/process.md` da plataforma como input obrigatório. Ancora screens nas user journeys já documentadas (não inventa do zero). Greenfield sem process.md = skill rejeita com erro pedindo gerar process.md primeiro | pipeline-dag-knowledge.md depends_on já lista business-process |
| 20 | Concurrency safety | GH Action `capture-screens.yml` declara `concurrency: { group: "capture-${{ matrix.platform }}", cancel-in-progress: false }`. Evita race em writes ao YAML quando dispatch manual encontra auto-trigger | GH Actions docs |
| 21 | Schema versioning | YAML obrigatório `schema_version: 1` no top. Validator rejeita versões desconhecidas. Migration path documentado pra v2 quando vier (script `migrate_v1_to_v2.py`). Sem isso, primeira mudança breaking quebra todas as plataformas silenciosamente | JSON Schema best practice |
| 22 | LFS lifecycle (futuro) | Política documentada: ano 1 confortável (estimado 9MB ativo, ~50MB histórico). Ano 2: avaliar `git lfs prune` mensal em CI OU migração pra Vercel Blob (campo `image:` aceita URL). Trigger de revisão: bandwidth >800MB/mês ou storage >300MB | GitHub LFS docs |
| 23 | Bundle budget mensurável | Após fase 2 fechar baseline, definir budget concreto da rota `/screens/*` via `size-limit` no CI. Range esperado: 600-900KB ungz (xyflow + custom nodes + ELK output como JSON, sem ELK runtime). Falha de build se exceder o budget. Substitui claim aspiracional "TTI <1.5s" por gate medível | size-limit docs |
| 24 | Test pyramid explícito | 4 layers: (a) **Unit** (Python pytest): 30+ casos do validator (rejection schema), 100% cobertura. (b) **Component** (React Testing Library + jest): ScreenNode renderiza 3 estados, ActionEdge 4 styles, hotspots numerados. (c) **Visual** (Playwright + jest-image-snapshot): canvas com fixture de 8 telas, toleração 1px diff. (d) **E2E** (1 spec): pipeline completo capture→commit→render contra fixture mock | test-pyramid pattern |

## Resolved Gray Areas

**Por que vocabulário fechado de 10 components?**
Sem trava, autoria humana e geração via skill divergem. Renderer fica explosivo. Vocabulário fechado é o que torna B (xyflow custom) sustentável: skill consegue gerar consistente, autores não inventam novos primitivos, renderer fica simples (~300 LOC). Adicionar 11º depois é trivial; renomear existente é breaking change cross-platform.

**Por que linguagem visual distinta pra wireframe (Decision #14)?**
Renderizar wireframes com Tailwind/shadcn-like primitives produziria caixas que parecem "app real meia-boca": gradientes suaves, bordas arredondadas, fonts modernas. Stakeholder confunde com design final, pergunta "vai ser exatamente assim?", e o badge `WIREFRAME` vira mentira visual. Tools dedicados (Whimsical, Balsamiq, Excalidraw) usam linguagem visual EXPLICITAMENTE não-final: paleta cinza com accent único, tipografia mono ou hand-drawn, border-radius 0 ou 100% (não meio-termo), zero gradiente, zero sombra pesada. Custo: ~50 LOC + Google Font preloaded. Benefício: honestidade visual entre `WIREFRAME` (low-fi) e `WEB BUILD` (real screenshot) — dois modos visualmente distintos previne mal-entendidos.

**Por que cortar status bar fake (Decision #15)?**
A versão original investia ~280 LOC em chrome SVG: bezel + notch + status bar com "9:41" 100% bateria. Status bar é convenção de keynote Apple (App Store screenshots), sem valor em documentação arquitetural. Stakeholder lendo screen flow não tem interesse em saber se tem notch ou bateria cheia — interesse é fluxo. Bezel mínimo (border-radius 32px + label discreto `iPhone 15 / 393×852`) entrega "moldura" útil sem teatro. Saving: ~150 LOC.

**Por que hotspots visíveis por default (Decision #16)?**
Especificação original: `opacity-0 hover:opacity-20`. Falha em touch device (sem hover, hotspots nunca aparecem). Falha em desktop até passar mouse (discoverability zero). Padrão Figma prototype mode: hotspots SEMPRE visíveis com badge numerado (1, 2, 3) ao lado de elementos clicáveis + outline subtle. Toggle `H` esconde quando autor quer screenshot "limpo" pra apresentação. Custo: +30 LOC. Benefício: UX correto em todos os contextos.

**Por que a11y + dark mode como invariante não-negociável (Decision #17)?**
Portal Starlight TEM dark mode toggle. Hardcode `bg-white text-black` quebra dark mode = unreadable. Edges diferenciadas só por COR (success=verde, error=vermelho) falham pra color-blind users (8% dos homens). Sem keyboard nav, sem aria-labels, canvas é unreachable pra screen readers. Custo: ~0.5d adicional. Não-negociável porque débito de a11y composta — corrigir depois custa 5x mais que fazer certo da primeira vez.

**Por que limpar Service Worker entre captures (Decision #18)?**
Resenhai-expo tem `public/sw.js` ativo (5.4KB). SW cacheia respostas. Sem clearing, captura 2 vê dados cacheados de captura 1 → PNG diferente. Validation Evidence (2026-05-05) testou só `/welcome` e `/login` (públicas, leves). Telas autenticadas (`/home`, `/groups`) usarão SW ativamente. `addInitScript` + `addStyleTag` não cobrem essa fonte. ~10 LOC: `clearCookies()` + `serviceWorker.unregister()` antes de cada `page.goto`.

**Por que skill lê process.md como upstream (Decision #19)?**
Skill `madruga:business-screen-flow` originalmente "perguntava pra o user e gerava YAML". Em greenfield isso vira "user inventa screens do zero", desancorando da spec do produto. `business/process.md` JÁ EXISTE em todas as plataformas e lista as user journeys do domínio. A skill DEVE ler como input obrigatório e propor screens DERIVADAS das jornadas — humano valida e ajusta, mas não inventa do zero. Greenfield sem process.md = skill rejeita com erro pedindo gerar `business-process` primeiro.

**Por que `data-testid` por componente declarado em YAML, sem prefixo convencionado (Decision #9)?**
Validação 2026-05-05: 54 usos de `testID=` em resenhai-expo. React Native expõe `testID` como `data-testid` em react-native-web. Versão original propôs convenção `nav-` (testID="nav-btn-entrar") — mas ainda exigiria adicionar prefixo aos testIDs existentes (= edit no app). Refinamento: YAML declara `testid: "<existing-id>"` no body de cada componente clicável: `{ type: button, id: btn_entrar, testid: "login-submit-btn" }`. Capture script usa `[data-testid="login-submit-btn"]` exato. **Zero novo atributo no app**. Trade-off: autor da YAML precisa saber o testID existente — mitigação: skill `business-screen-flow` pode opcionalmente ler arquivos `e2e/` da plataforma e sugerir testIDs disponíveis.

**Por que path_rules per-platform em YAML (Decision #11 reformulada)?**
Versão original hardcoded regex `src/screens/*Screen.tsx` em Python. Mas resenhai-expo usa expo-router file-based: `app/(auth)/login.tsx` — regex original literalmente nunca casaria. Cada plataforma tem framework próprio (Next.js: `pages/`, expo-router: `app/`, React: `src/screens/`). Path rules em `platform.yaml.screen_flow.capture.path_rules` é schema-driven: cada plataforma declara seus padrões, validator confirma sintaxe, reverse-reconcile lê e aplica. Adicionar nova plataforma não requer mudança no código Python.

**Por que `schema_version: 1` obrigatório (Decision #21)?**
YAML schema é "LOCKED" mas evolução é inevitável (vocabulário cresce, novos campos surgem). Sem versão no top do arquivo, primeira mudança breaking quebra todas as plataformas silenciosamente. Validator rejeita versões desconhecidas — força migration path explícito (`migrate_v1_to_v2.py`). 10 LOC, zero custo, dívida técnica zero.

**Por que bundle budget mensurável ao invés de "TTI <1.5s" (Decision #23)?**
TTI <1.5s é aspiracional sem instrumentação. xyflow é ~600KB ungz, ELK é build-time (zero client), custom code TBD. Promessa baseada em palavra. `size-limit` no CI define budget concreto após fase 2 fechar baseline (provavelmente 700-900KB ungz pra rota `/screens/*`). Falha de build se exceder. Substitui aspiração por gate medível.

**Por que Playwright + Expo Web ao invés de Maestro?**
Decisão de trade-off: fidelidade native ↓ ~10-15% em troca de complexidade de infra ↓ ~70%. Justificada porque o screen-flow é doc arquitetural, não QA visual. Stakeholder lê pra entender fluxo, não pra auditar pixel iOS. CI custo cai ~80% (Linux runner vs macOS). Risco residual: deps native-only em resenhai-expo (mapas, câmera, push) que renderizam vazias em web. Mitigação: audit dia 1 + plano B (telas com dep problemática ficam em mock).

**Por que ELK em build-time, não Dagre em client?**
Dagre é mais leve mas produz layouts feios em fluxos hierárquicos (que é exatamente o caso de screen flows: entry → main → branches). ELK (`org.eclipse.elk.algorithm: 'layered'`) gera layouts limpos com edge routing orthogonal. Custo do ELK (~500KB) é zero porque roda em build-time no Astro Node — nunca chega no bundle client.

**Por que determinism via Playwright `addInitScript` ao invés de flag no app?**
Versão original do pitch propunha PR externo no resenhai-expo adicionando handler `?screenshot=1`. Após investigação das APIs do Playwright, descobriu-se que ~80% da determinism vem grátis sem tocar no app: `addInitScript` injeta JS antes do app carregar e permite override de `Date.now()`, `Math.random()`, `Element.prototype.animate`. `page.route()` mocka endpoints voláteis (`/api/notifications/unread`, `/api/user/me`). `storageState` reusa cookie de login feito uma vez. `addStyleTag` injeta CSS pra desabilitar animações e esconder banners de cookie. Custo: zero LOC no app externo, zero coordenação cross-team. Trade-off aceito: 1-2 elementos por tela podem ainda variar (avatar dinâmico, contador unread server-rendered). Se isso virar PNG noise mensurável após 5 runs, escalada incremental: ~10 LOC no resenhai-expo adicionando `data-volatile` em elementos crônicos (vs 50 LOC original com flag completa). Caminho de menor superfície externa.

**Por que Git LFS e não CDN externo?**
Mantém invariante "repo é a fonte da verdade". CDN externo introduz credencial de write em CI, lifecycle de versões, dependência de uptime. Quota Free GitHub LFS na org `paceautomations` (500MB storage / 1GB bandwidth/mês, validada em 2026-05-05) é confortável: estimado 25-30MB pra 3 plataformas × 30 telas × 200KB médio. Eixo a monitorar é bandwidth — workflows com `lfs: true` em todo run podem somar rápido. Mitigação: `actions/checkout@v4` com `lfs: false` quando não precisa do binário; portal Astro renderiza via `<img src>` (resolução LFS lado servidor sob demanda no Vercel). Se quota apertar, migração pra Vercel Blob é trivial (mudança no campo `image` de path → URL).

**Por que iPhone 15 e não iPhone 15 Pro?**
393×852 (15) vs 430×932 (15 Pro). Diferença é ~10% em altura. iPhone 15 base é a referência mais comum em design (Pro Max e base concentram maior share). Convenção pode mudar via `meta.capture_profile` per-platform sem breaking change. Decisão é low-stakes; locking pra evitar bikeshedding.

**Por que coords normalizadas 0-1?**
Permite mostrar a mesma captura em diferentes resoluções no canvas (zoom in/out do xyflow muda render size). Coords em pixel obrigariam recapturar tudo se profile mudar. Normalizado é o invariante físico (proporção do device).

**madruga-ai opt-out: como dogfooding na fase 2 sem screen-flow.yaml próprio?**
Risco identificado: portal renderer não tem caso self-referential pra testar enquanto resenhai-expo fase 4 não chega. Mitigação: criar `portal/src/test/fixtures/screen-flow.example.yaml` com screens fictícias cobrindo os 10 component types + 4 edge styles. Página `[platform]/screens.astro` aceita `?fixture=true` em dev pra carregar a fixture ao invés do YAML real. Assim fase 2 é testável sem depender de fase 4.

## Validation Evidence (2026-05-05)

Validado **antes** do epic começar pra de-riscar 1-way-doors:

**Quota Git LFS** (paceautomations org):
- Plan: Free → 500 MB storage / 1 GB bandwidth/mês
- Uso atual: 0 objetos LFS em qualquer repo (madruga.ai, resenhai-expo, prosauai)
- Headroom estimado: ~55x sobre uso projetado do epic (~9MB)

**Expo Web já roda em produção** (resenhai-expo):
- Stack: Expo SDK 54, react-native-web 0.21.2, expo-router 6
- Staging: `https://dev.resenhai.com` é a build web (HTTP 200 verified)
- Pipeline existente: `npm run build:web` + `npm run serve:static` + `e2e/tests/screenshots/` + projeto `screenshots` no `playwright.config.ts`
- Evidência: `docs/app_info_photos/` tem 8 PNGs commitados (welcome, login, home, groups, games, ranking, profile, settings) em 1284×2778

**Determinism via Playwright addInitScript** (validação real contra staging):
```
=== RUN 1 ===  welcome md5=6ec3345c7ed2…  size=325.5KB
               login   md5=437713cabd94…  size=362.7KB
=== RUN 2 ===  welcome md5=6ec3345c7ed2…  size=325.5KB    [BYTE-IDÊNTICO]
               login   md5=437713cabd94…  size=362.7KB    [BYTE-IDÊNTICO]
Result: 2/2 identical
```
- Setup: `addInitScript` (Date freeze 2026-01-01, Math.random seed=42, animate stub) + `addStyleTag` (transitions/animations off) + `networkidle` wait
- Código tocado em resenhai-expo: **0 LOC**
- Tempo: ~25s pra 2 runs × 2 telas
- Tamanho médio PNG: 344KB (abaixo do limite 500KB)

## Per-platform config examples

Schema completo em `platform.yaml` por plataforma — referência operacional pro time saber rodar e reproduzir.

### resenhai-expo (pilot, enabled=true)

```yaml
# platforms/resenhai-expo/platform.yaml
screen_flow:
  enabled: true
  capture:
    base_url: "https://dev.resenhai.com"
    # serve omitido — staging permanente, sem build local no CI inicial
    device_profile: iphone-15
    auth:
      type: storage_state
      setup_command: "npx playwright test --project=auth-setup"
      storage_state_path: "e2e/.auth/user.json"
      test_user_env_prefix: "RESENHAI"
      # → RESENHAI_TEST_EMAIL e RESENHAI_TEST_PASSWORD via GH Secrets
    determinism:
      freeze_time: "2026-01-01T12:00:00Z"
      random_seed: 42
      disable_animations: true
      clear_service_workers: true   # crítico — resenhai-expo tem public/sw.js
      clear_cookies_between_screens: true
      # Hotspots referem testIDs JÁ existentes no app via campo `testid:` no body de cada componente da YAML (Decision #9). Sem prefixo, sem nova convenção no app.
      mock_routes:
        # endpoints voláteis identificados na fase 4 com base em telas autenticadas
        - { match: "**/api/notifications/unread", body: { count: 0 } }
    expo_web:
      enabled: true
      # incompatible_deps preenchido se aparecer problema; validação 2026-05-05 já confirma compat
    # Drift detection: regex declarativo per-platform pra reverse-reconcile
    path_rules:
      - { pattern: 'app/\(auth\)/(\w+)\.tsx',          screen_id_template: '{1}' }
      - { pattern: 'app/\(app\)/(\w+)\.tsx',           screen_id_template: '{1}' }
      - { pattern: 'app/\(app\)/(\w+)/(\w+)\.tsx',     screen_id_template: '{1}_{2}' }
```

# screen-flow.yaml topo
schema_version: 1
meta:
  device: mobile
  capture_profile: iphone-15
  ...

**Como rodar localmente** (depois do epic):
```bash
cd /home/gabrielhamu/repos/paceautomations/madruga.ai
export RESENHAI_TEST_EMAIL=demo+playwright@resenhai.com
export RESENHAI_TEST_PASSWORD=...  # do .env ou 1Password
python3 .specify/scripts/capture/screen_capture.py resenhai-expo
```

**Como rodar via CI**:
```bash
gh workflow run capture-screens.yml -f platform=resenhai-expo
```

### prosauai (opt-out, enabled=false)

```yaml
# platforms/prosauai/platform.yaml
screen_flow:
  enabled: false
  skip_reason: |
    Admin frontend é evolução futura (epic 008-admin-evolution em flight, ainda não estabilizado).
    Reabilitar quando admin tiver pelo menos 5 telas estáveis em rota pública navegável.
    Conversas do usuário são WhatsApp/Chatwoot — não são "screens" do app, ficam permanentemente
    out-of-scope desse mecanismo.
```

**Sem aba Screens na sidebar do portal** — opt-out invisível.

### madruga-ai (opt-out, enabled=false)

```yaml
# platforms/madruga-ai/platform.yaml
screen_flow:
  enabled: false
  skip_reason: |
    Plataforma de tooling/orquestração — não tem "app de usuário" no sentido tradicional.
    O portal Astro é interno (visualização de docs do próprio madruga). Caso queira documentar
    fluxo do portal, reabilitar com base_url=http://localhost:4321 e device_profile=desktop.
```

**Sem aba Screens na sidebar do portal** — opt-out invisível.

## Applicable Constraints

**Do blueprint.md**:
- Stack frontend já travado em React 19 + Astro 6 + Starlight + @xyflow/react v12 (ADR-003) — não introduzir biblioteca de canvas alternativa
- Mermaid é o padrão pra diagramas inline em .md (ADR-020) — screen-flow não substitui isso, complementa
- SQLite WAL é o estado mutável; YAML é stateless artifact — captura não toca DB

**Do pipeline-contract-base.md**:
- L1 nodes opcionais não bloqueiam downstream (igual `codebase-map`)
- Skill segue contrato de 6 seções uniformes (Cardinal Rule, Persona, Usage, Output, Instructions, Auto-Review)
- Gate human pra L1 business layer
- PT-BR pro conteúdo gerado, EN pra IDs/code

**Do CLAUDE.md**:
- Edits a `.claude/commands/` MUST passar por `/madruga:skills-mgmt` — registrar a nova skill via skill-creation flow oficial
- ADRs em formato Nygard
- Branch isolation por epic (`epic/madruga-ai/027-screen-flow-canvas`)
- Bare-lite dispatch já cobre cache prefix; sem mudanças nesse layer

**Do package.json existente do portal**:
- Adicionar **apenas `elkjs ^0.9`** como devDependency (build-time only) — sem novas runtime deps no client
- xyflow v12 já em uso pelo pipeline DAG visualization (zero custo marginal)

## Suggested Approach

**5 fases shippable** (cada fase mergeable se appetite estourar).

**Fase 1 — Schema + Skill skeleton (2 dias)**
- `screen-flow.schema.json` com vocabulário completo: `schema_version: 1` obrigatório (Decision #21) + 10 components + 4 edges + capture states + hotspots normalized
- `platform.yaml.screen_flow` schema bloco completo: enabled/skip_reason + capture (base_url/serve/device_profile/auth/determinism/expo_web/path_rules)
- `screen_flow_validator.py` invocável via hook_post_save: rejeita types fora do vocabulário, valida refs from/to em flows, lint de IDs duplicados, rejeita schema_version desconhecido, valida path_rules sintaxe regex
- Skill `madruga:business-screen-flow` registrada em `.claude/commands/` via `/madruga:skills-mgmt create`. **Lê `business/process.md` como input obrigatório (Decision #19)** — rejeita se ausente
- pipeline.yaml ganha o nó com `optional: true`, `depends_on: [business-process]`, layer `business`, gate `human`
- pipeline-dag-knowledge.md atualiza tabela L1 com 14º node
- DoD: `/madruga:business-screen-flow resenhai-expo` lê process.md e gera YAML válido; opt-out em madruga-ai/prosauai exits gracefully; YAML sem schema_version é rejeitado

**Fase 2 — Renderer mock-only (3.5 dias)**
- `portal/src/lib/screen-flow.ts` (loader YAML + ELK layouter build-time, com fixture fallback `?fixture=true` pra dev sem YAML real)
- `portal/src/lib/elk-layout.ts` (config `layered` direction `DOWN`/`RIGHT` baseado em `meta.layout_direction`)
- `portal/src/styles/screen-flow-tokens.css` — tokens CSS variables (`--screen-bg`, `--screen-fg`, `--screen-accent`, `--edge-success`...) que respeitam `[data-theme="dark"]` do Starlight (Decision #17)
- `ScreenFlowCanvas.tsx` (xyflow wrapper com Background dots, Controls non-interactive, MiniMap pannable, **keyboard nav** Tab/Enter)
- `ScreenNode.tsx` 3-state com memo comparator estrito (`id + selected`); **aria-label** descrevendo a tela (Decision #17)
- `ActionEdge.tsx` 4 styles + label flutuante via `EdgeLabelRenderer`; **pattern adicional** (sólido/tracejado/pontilhado) pra redundância visual além de cor (Decision #17)
- `Chrome.tsx` minimal — moldura com border-radius + label profile (Decision #15). SEM `StatusBar.tsx`. Saving: ~150 LOC vs design original
- `WireframeBody.tsx` 10 sub-renderers usando paleta wireframe-only (cinza + accent suave) e tipografia distinta (Caveat ou Architects Daughter via Google Fonts preloaded). Decision #14
- `Hotspot.tsx` visível por default com badge numerado + outline dashed; toggle `H` (Decision #16)
- `Badge.tsx` 5 variants
- `[platform]/screens.astro` com SSG via `renderToStaticMarkup` + island `client:visible`
- routeData.ts ganha entry "Screens" condicional (só aparece se YAML existir)
- DoD: aba Screens da resenhai-expo mostra wireframes interativos a 60fps com fixture 30+ telas; Tab navega entre nodes; dark mode renderiza corretamente; color-blind simulator mostra edges distinguíveis

**Fase 3 — Captura web (Playwright) (2 dias)**
- `screen_capture.ts` com profiles + storageState + mask (locator `[data-volatile]` opcional) + hotspots via boundingBox em **`[data-testid^="nav-"]`** (convenção já existente — 54 usos no resenhai-expo, Decision #9)
- Determinism layer (`screen_capture/determinism.ts`):
  - `addInitScript` (Date/Math/animate overrides)
  - `addStyleTag` (transitions/animations off)
  - **`clearCookies()` + `navigator.serviceWorker.unregister()` antes de cada `page.goto`** (Decision #18) — crítico em telas autenticadas com SW
  - `page.route()` registry pra mockar endpoints voláteis declarados em `platform.yaml.screen_flow.capture.determinism.mock_routes`
- GitHub Action `capture-screens.yml` com `workflow_dispatch` (matrix por plataforma) + **`concurrency` block per-platform** (Decision #20)
- Git LFS setup: `.gitattributes` + pre-commit hook em Python (~30 LOC) que rejeita PNG >500KB
- Auto-commit do YAML atualizado (`captured_at`, `app_version`, `hotspots`, `status: captured`) — auto-commit ao madruga.ai trigga `deploy-hostinger.yml` existente, portal rebuilds
- DoD: `gh workflow run capture-screens -f platform=resenhai-expo` enche `business/shots/`, portal renderiza imagens com hotspots clicáveis. Determinism check: 2 runs back-to-back produzem PNGs idênticos (`md5sum` antes/depois). Concurrent runs não corrompem YAML

**Fase 4 — Pilot resenhai-expo (1 dia)**
Reduzido de 2 dias após validação 2026-05-05 — pipeline já existe e funciona, fase é adaptação não criação.
- Adaptar `e2e/tests/screenshots/appstore-screenshots.spec.ts` existente: ler nossa YAML, usar nossos profiles + determinism layer
- Apontar workflow pra `https://dev.resenhai.com` (staging já é Expo Web em produção — sem `npx expo export` local necessário no CI inicial)
- Configurar env vars `RESENHAI_TEST_EMAIL`/`RESENHAI_TEST_PASSWORD` em GH Secrets, reutilizar `e2e/auth.setup.ts` pra produzir storageState
- Identificar endpoints voláteis (notifications unread, last seen, etc) — declarar em `resenhai-expo/platform.yaml:screen_flow.capture.determinism.mock_routes`
- DoD: pelo menos 3 telas reais (welcome ✓ já validada, login ✓ já validada, +1 autenticada como `home`) com badge "WEB BUILD v\<x\>"; 2 runs consecutivos byte-idênticos (md5 match — já provado em welcome+login)
- Escalation gate (não acionado): se ≥3 telas autenticadas tiverem PNG noise após determinism layer, aprovar mini-PR de ~10 LOC adicionando `data-volatile` em elementos crônicos identificados

**Fase 5 — Drift + bundle budget + test pyramid (1.5 dias)**
- Estender `reverse_reconcile_aggregate.py` lendo `platform.yaml.screen_flow.capture.path_rules` (Decision #11) — mapeamento per-platform via regex declarativo, NÃO hardcoded
- `screen_flow_mark_pending.py` (~80 LOC) que reescreve YAML setando `capture.status: pending`
- **Bundle budget gate** (Decision #23): `size-limit.config.json` no portal com regra pra rota `/screens/*` (~700-900KB ungz target). Falha de build se exceder. CI gate.
- **Test pyramid completo** (Decision #24):
  - Unit: 30+ casos do validator em pytest (rejection schema, path_rules sintaxe inválido, schema_version desconhecido)
  - Component: ScreenNode 3 estados, ActionEdge 4 styles, Hotspot numerado — React Testing Library + jest
  - Visual: snapshot do canvas com fixture de 8 telas via Playwright + jest-image-snapshot (toleração 1px diff)
  - E2E: 1 spec integrando capture→commit→render contra fixture mock
- Performance flags revisitados (`onlyRenderVisibleElements`, memo comparator validado com profiler)
- DoD: commit em `app/(auth)/login.tsx` (resenhai-expo) faz `screen_flow.login.capture.status` virar `pending` no próximo `madruga:reverse-reconcile resenhai-expo`. Bundle gate ativo no CI. 4 layers de teste verdes

**Critérios de aceite globais (DoD do epic)**:
1. `/madruga:business-screen-flow <platform>` lê `business/process.md` e gera YAML válido pelo schema com `schema_version: 1`
2. resenhai-expo: ≥3 telas reais via Expo Web com badge "WEB BUILD"
3. madruga-ai + prosauai: `enabled: false` no platform.yaml + skip_reason documentado, sem aba Screens na sidebar
4. Click em hotspot numerado dentro de node centra câmera na tela destino com easing animation; tecla `H` toggla visibilidade dos hotspots
5. **Bundle budget**: `size-limit` no CI mantém rota `/screens/*` dentro do orçamento definido após baseline de fase 2 (esperado 700-900KB ungz). Build falha se exceder
6. Bundle xyflow não impacta outras rotas (`size-limit` valida que `/[platform]/index.astro` mantém tamanho atual)
7. **Dark mode**: portal alterna `[data-theme="dark"]` e renderer respeita 100% (visualmente verificado em todas variantes de Chrome/Wireframe/Edge)
8. **A11y**: keyboard nav (Tab/Enter), aria-labels nos nodes, edges distinguíveis em color-blind simulator (deuteranopia + protanopia)
9. **Test pyramid 4 layers verdes**: (a) pytest unit 30+ casos validator, (b) jest+RTL component, (c) Playwright + jest-image-snapshot visual, (d) 1 spec E2E integração
10. **Determinism**: 2 runs back-to-back de capture-screens.yml produzem PNGs byte-idênticos (md5 match) em ≥80% das telas (incluindo autenticadas com SW cleanup ativo)
11. **Concurrency safety**: 2 dispatches simultâneos do workflow não corrompem YAML (concurrency block validado via teste integração)
12. **Schema versioning**: validator rejeita YAML sem `schema_version` ou com versão desconhecida
13. Drift detection: commit em `app/(auth)/login.tsx` (resenhai-expo) faz `screen_flow.login.capture.status` virar `pending` no próximo `madruga:reverse-reconcile`
14. ADR-NNN registrada com **24 decisões 1-way-door**
15. Knowledge file `.claude/knowledge/screen-flow-vocabulary.md` cobrindo 10 components + 4 edges + 5 badges com exemplos
16. `madruga:judge` review aprovado (4 personas)
17. **Invariante "zero edits externos"**: validar que nenhum commit em `paceautomations/resenhai-expo` (ou outro repo bound) é necessário pra epic shippar — todos artefatos vivem em `madruga.ai`. Captura é black-box contra staging

**Rabbit holes (NO-GO list explícito)**:
- ❌ Visual regression testing (Percy/Chromatic) — concern separado
- ❌ Captura native real via Maestro/simulador — possível epic futuro `screen-capture-native`
- ❌ Multi-device matrix (iPhone + Pixel + iPad) — só `iphone-15` v1
- ❌ Live editing no portal — read-only viewer, autoria via skill
- ❌ Diff before/after entre captures — overkill
- ❌ Component reuse via monorepo — fora de escopo
- ❌ Auth multi-tenant em capture — `storageState` pre-baked com 1 user demo
- ❌ Deep links nativos — só URL web v1
- ❌ Animação prototype-mode (transição entre telas estilo Figma) — só `fitView` com easing
- ❌ Chrome WhatsApp/Chatwoot pra prosauai chat — fica pra quando prosauai opt-in

**Riscos e mitigações**:

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| ~~`expo export -p web` quebra resenhai-expo~~ | ~~Média~~ → **Eliminado** | Validado 2026-05-05: dev.resenhai.com já é Expo Web em produção, 8 screenshots já comitados em `docs/app_info_photos/`, time mantém web compat ativamente |
| ~~Determinism via `addInitScript` não cobre variabilidade~~ | ~~Média~~ → **Baixa** | Validado 2026-05-05: 2 telas (welcome+login), 2 runs back-to-back, md5 byte-idêntico. Risco residual só em telas autenticadas com dados live (escalada incremental documentada) |
| ELK gera layout feio em fluxos com ciclos | Média | Validador detecta ciclo e força autor a definir `position` manual em telas envolvidas |
| Git LFS bandwidth estoura (1GB/mês) | Baixa | Workflows com `lfs: false` exceto onde estritamente necessário; portal Vercel resolve LFS server-side; `actions/checkout@v4` granular |
| Git LFS storage estoura (500MB) | Muito baixa | Estimado ~9MB pra 1 plataforma habilitada × 30 telas × 300KB; free tier 500MB tem ~55x folga |
| madruga-ai opt-out impede dogfooding self-ref | Média | Test fixture YAML em `portal/src/test/fixtures/` durante fase 2; permite desenvolvimento sem depender de fase 4 |
| xyflow bundle (~600KB) impacta perf de outras rotas | Baixa | `client:visible` + lazy import garante que só rota /screens carrega |
| ~~Hotspots via `data-action-id` exigem mudança no app~~ | ~~Média~~ → **Eliminado** | Decision #9 refinada: YAML declara `testid:` referindo testIDs JÁ existentes (54 em resenhai-expo). Zero novo atributo no app. Trade-off transferido pro autor da YAML conhecer testIDs (mitigado pela skill que pode parsear `e2e/` files) |
| Service Worker do resenhai-expo causa staleness em telas autenticadas | Alta (em fase 4) | Decision #18: capture script chama `clearCookies()` + `serviceWorker.unregister()` antes de cada `page.goto`. Validado contra `public/sw.js` |
| Bundle real estoura budget (700-900KB) durante implementação | Média | Decision #23: `size-limit` no CI desde fase 2 catch instantaneamente. Plano B: code splitting interno (separar `Chrome.tsx` + `WireframeBody.tsx` em chunks lazy) |
| autor da YAML não sabe testIDs do app (gap de conhecimento) | Média | Skill `business-screen-flow` opcionalmente parseia arquivos `e2e/tests/**/*.spec.ts` da plataforma e sugere testIDs disponíveis durante geração interativa |
| Bikeshedding em vocabulário durante fase 1 | Média | 10 components LOCKED na entrada do epic; PRs questionando vocab são rejeitados sem discussão |
| Test user resenhai-expo expira/é deletado em staging | Baixa | `e2e/auth.setup.ts` já reseed-aware no time atual; documentar em `screen_flow.capture.auth` o procedimento |
