---
epic: 027-screen-flow-canvas
phase: plan
created: 2026-05-05
updated: 2026-05-05
sidebar:
  order: 27
---

# Implementation Plan: Screen Flow Canvas

**Branch**: `epic/madruga-ai/027-screen-flow-canvas` | **Date**: 2026-05-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `platforms/madruga-ai/epics/027-screen-flow-canvas/spec.md`

## Summary

Adicionar uma feature L1 **opcional** (`madruga:business-screen-flow`) que produz `business/screen-flow.yaml` por plataforma (vocabulário fechado de 10 components + 4 edges + 6 badges + 3 capture states), renderiza esse YAML como canvas Figma-like (xyflow + ELK build-time + SSG) numa nova aba **Screens** condicional do portal Astro Starlight, captura screenshots reais via Playwright determinístico contra Expo Web staging (resenhai-expo), e fecha o loop de drift via reverse-reconcile lendo `path_rules` declarativos per-platform de `platform.yaml.screen_flow.capture`.

A abordagem técnica é três camadas:

1. **Schema-first** — `screen-flow.schema.json` (vocabulário fechado, `schema_version: 1`) + extensão de `platform.yaml` com bloco `screen_flow` (toggle `enabled` + `capture` config) validados por `screen_flow_validator.py` (Python stdlib + `pyyaml`) acionado no hook PostToolUse.
2. **Renderer build-time** — Astro 6 Server Component carrega YAML, ELK pré-computa layout (zero `elkjs` no client), `renderToStaticMarkup` produz SSG, ilha React hidrata com `client:visible`. xyflow v12 com flags non-interactive + custom nodes memoizados. Tokens CSS variables respeitam dark/light mode do Starlight; edges com pattern (sólido/tracejado/pontilhado) além de cor pra color-blind.
3. **Captura Linux-only** — runner GitHub Actions ubuntu-latest, Playwright Chromium, profiles `iphone-15` / `desktop`, determinism via `addInitScript` + `addStyleTag` + `clearCookies()` + `serviceWorker.unregister()` + `page.route()` mocks. Auth via `storageState` pre-baked (env vars `<PREFIX>_TEST_EMAIL`/`_TEST_PASSWORD`). 3 retries + backoff exponencial; status `failed` first-class; concurrency block evita race em writes ao YAML.

Drift detection estende `reverse_reconcile_aggregate.py` lendo `screen_flow.capture.path_rules` (regex declarativo per-platform) e enfileirando patches para `screen_flow_mark_pending.py` que reescreve o YAML setando `capture.status: pending`. Bundle budget enforced via `size-limit` no CI; test pyramid em 4 layers (pytest unit + RTL component + Playwright visual + 1 E2E).

## Technical Context

**Language/Version**:
- Python 3.11+ (validator, capture orchestrator, mark_pending, hooks)
- TypeScript / React 19 (renderer, custom xyflow nodes/edges, hotspot logic)
- Bash (GH Actions workflow snippets)
- Node 20+ (Astro 6 build, Playwright runtime)

**Primary Dependencies**:
- Backend: stdlib + `pyyaml` (schema parsing), `jsonschema` para validar `screen-flow.schema.json` contra YAML (já presumida disponível no `requirements.txt` do repo; se ausente, adicionar como única dep nova Python)
- Frontend (portal já tem): `@xyflow/react ^12.10.2`, `elkjs ^0.11.1` (movido para devDependency build-time only — preservado no `package.json`), `js-yaml ^4.1.1`, `astro ^6.1.9`, `@astrojs/starlight ^0.38.4`, React 19
- Frontend novo: `size-limit` + `@size-limit/preset-app` (devDependency CI-only), `@testing-library/react` + `@testing-library/jest-dom` + `jest-image-snapshot` + `vitest` (já se usa vitest no portal? confirmar; senão adotar) — mínimo de novas deps possível
- Captura: `@playwright/test` (devDependency portal), Chromium driver via `npx playwright install chromium`
- Pre-commit: `pre-commit` framework já presente no repo (assumir); se não, hook bash inline em `.git/hooks/pre-commit` é fallback

**Storage**:
- YAML em disco: `platforms/<name>/business/screen-flow.yaml` (artefato versionado)
- Imagens em disco via Git LFS: `platforms/<name>/business/shots/<screen-id>.png` (`.gitattributes`)
- Metadata operacional: SQLite WAL existente (`.pipeline/madruga.db`) recebe registros via `post_save.py` quando o YAML é gravado; nenhuma tabela nova nesta epic
- Sem persistência runtime no portal: tudo é SSG estático

**Testing**:
- Python: `pytest` (já em uso no repo) — Layer (a) Unit do validator, ≥30 casos
- React: `vitest` + `@testing-library/react` — Layer (b) Component (ScreenNode 3 states, ActionEdge 4 styles, Hotspot numerado)
- Visual: Playwright + `jest-image-snapshot` — Layer (c) Visual snapshot do canvas com fixture de 8 telas, toleração 1px
- E2E: 1 spec Playwright integrando capture→commit→render contra fixture mock — Layer (d)
- Color-blind / a11y: usar Playwright + `axe-core` (`@axe-core/playwright`) numa única smoke pra garantir aria-labels e keyboard nav (não cobre 100% mas mantém custo baixo)

**Target Platform**:
- Portal estático: build em Astro 6 → output HTML+JS hospedado em Hostinger (deploy via workflow `deploy-hostinger.yml` existente)
- Capture runner: GitHub Actions `ubuntu-latest` (Linux only — sem macOS, sem Windows)
- Browser-alvo: Chromium (Playwright default); Safari/Firefox out of scope v1

**Project Type**: web application + python scripts (multi-target). Estrutura existente do repo: portal frontend em `portal/`, scripts/skills em `.specify/scripts/` e `.claude/commands/`, plataformas em `platforms/<name>/`. Não introduz nova hierarquia.

**Performance Goals**:
- Canvas rendering 60fps em desktop padrão (1440×900) com 30+ telas; degrada gracefully em ≤30fps com 50 telas (warn no validator a partir de 50)
- Click em hotspot → câmera centrada na tela destino: <700ms total (~250ms aresta animada + ~350ms `fitView` easing)
- Tecla `H` toggle hotspots: <50ms (re-render local sem layout)
- Bundle rota `/<platform>/screens/*`: target 700-900KB ungz (definido após baseline da fase 2 via `size-limit`); outras rotas mantêm tamanho atual (gate separado)
- ELK layout build-time: <5s pra layouts típicos (warn), abort em >30s (Decision #21)
- Capture script: 1-3 min por workflow run típico (≤10 telas); timeout duro 30 minutos

**Constraints**:
- **Zero edits externos**: nenhum commit em `paceautomations/resenhai-expo` (ou outro repo bound) é necessário (Decision #26). Capture é black-box contra staging existente
- **Vocabulário LOCKED**: 10 components + 4 edges + 6 badges + 3 capture states. PRs questionando vocab durante implementação são rejeitados sem discussão (1-way-door)
- **Schema versioning obrigatório**: `schema_version: 1` no topo de cada YAML; validator rejeita ausência ou versão desconhecida
- **A11y + dark mode invariantes não-negociáveis**: tokens CSS variables, edge patterns adicionais à cor, `aria-label`, keyboard nav (Tab/Enter)
- **PII**: test user sintético obrigatório; `test_user_marker` campo obrigatório em `platform.yaml.screen_flow.capture` quando `enabled: true`; `mock_routes` mascaram endpoints com risco
- **Determinism**: ≥80% das telas com PNG byte-idêntico em 2 runs back-to-back (md5 match), incluindo telas autenticadas com SW cleanup ativo
- **PNG ≤500KB**: pre-commit hook bloqueia commit; Git LFS mandatório pra `business/shots/*.png`
- **GitHub LFS Free quota**: 500MB storage / 1GB bandwidth/mês; SC-013 monitora ≤30% de uso após 30 dias; trigger de revisão em 800MB/mês bandwidth ou 300MB storage (Decision #22)
- **Concurrency**: 2 dispatches simultâneos do workflow não corrompem YAML (concurrency block per-platform)

**Scale/Scope**:
- Inicial: 1 plataforma habilitada (resenhai-expo, ~30 telas), 2 plataformas opted-out (madruga-ai, prosauai)
- Hard limit por YAML: 100 telas (validator reject); warn em 50 telas
- Crescimento esperado: 3-4 anos confortáveis dentro do limite; multi-arquivo por bounded context fica fora de v1
- Bundle volume real estimado: ~9MB ativo (1 plataforma × 30 telas × 300KB médio); ~50MB histórico ano 1
- Workflow runs estimados: ~10-20/mês (manual dispatch + auto-trigger pós-PR no resenhai-expo)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constituição (`.specify/memory/constitution.md` v1.1.0) avaliada:

| Princípio | Aplicação neste epic | Status |
|-----------|---------------------|--------|
| I. Pragmatism Above All | Stack reusada (xyflow + elkjs + Astro já presentes); zero novas deps Python (`pyyaml`+`jsonschema` já em uso); vocabulário fechado mantém renderer simples (~300 LOC) | ✅ |
| I. (cont.) Performance-aware | Bundle budget mensurável via `size-limit` (substitui claim aspiracional); ELK build-time ⇒ zero peso runtime; `onlyRenderVisibleElements` + `client:visible` lazy import | ✅ |
| II. Automate Repetitive Tasks | Hook PostToolUse roda validator automaticamente; pre-commit hook bloqueia PNG >500KB; capture script automatizado via GH Actions matrix; reverse-reconcile detecta drift sem intervenção manual | ✅ |
| III. Structured Knowledge | `screen-flow.schema.json` é fonte única de verdade do vocabulário; ADR-NNN registra 26 decisões 1-way-door; knowledge file `.claude/knowledge/screen-flow-vocabulary.md` para autores e renderer | ✅ |
| IV. Fast Action | 5 fases shippable independentes (cada fase mergeable se appetite estourar); fase 2 com fixture entrega valor antes de captura real estar pronta | ✅ |
| V. Alternatives & Trade-offs | Pitch.md documenta trade-offs explicitamente (Playwright vs Maestro, ELK vs Dagre, LFS vs CDN, addInitScript vs PR externo); Phase 0 research consolida alternativas consideradas | ✅ |
| VI. Brutal Honesty | Estimates 10 dias documentadas honestamente (subiu de 8 → 10 após Crítica 1 incorporar 14 itens); riscos identificados ANTES de começar (Validation Evidence 2026-05-05 reduziu 3 riscos antes do epic abrir) | ✅ |
| VII. TDD | Test pyramid 4 layers definido como gate de DoD; ≥30 casos pytest unit pra validator com 100% cobertura de rejection paths (FR-042); RTL+jest pra component; Playwright + jest-image-snapshot pra visual; E2E pra fluxo completo. Casos falham antes de implementar (Red→Green→Refactor) | ✅ |
| VIII. Collaborative Decisions | 24 decisões da pitch.md + 2 novas neste plan (test framework + jsonschema dep) registradas em `decisions.md`; gate human nas fases 1, 2, 4 (skill output, renderer baseline, pilot resenhai-expo); 1-way-door explícito ao trancar vocabulário | ✅ |
| IX. Observability | Capture script emite logs JSON estruturados (timestamp, level, correlation_id=screen_id, context=run_id+platform); validator reporta line numbers + paths nos erros; reverse-reconcile aggregate logga decisões de mapping path_rule→screen_id; CI gates emitem JSON resumido | ✅ |

**Resultado**: ZERO violações. Sem `Complexity Tracking` necessário.

**Re-check pós-Phase 1 design**: ver final deste plan — confirmado abaixo.

## Project Structure

### Documentation (this feature)

```text
platforms/madruga-ai/epics/027-screen-flow-canvas/
├── pitch.md              # Shape Up pitch (Phase pre-spec)
├── spec.md               # Spec clarificada (Phase pre-plan)
├── decisions.md          # Registro de decisões acumulado
├── easter-tracking.md    # Tracking de easter epic execution
├── plan.md               # Este arquivo (/speckit.plan output)
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   ├── screen-flow.schema.json
│   ├── platform-yaml-screen-flow.schema.json
│   └── capture-script.contract.md
└── tasks.md              # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
# Schema + Validator (Python)
.specify/schemas/
└── screen-flow.schema.json                  # NEW — vocabulário fechado v1

.specify/scripts/
├── screen_flow_validator.py                 # NEW — valida YAML contra schema + lint custom
├── screen_flow_mark_pending.py              # NEW — reescreve YAML c/ status pending preservando comentários
├── reverse_reconcile_aggregate.py           # MODIFIED — lê platform.yaml.screen_flow.capture.path_rules
├── platform_cli.py                          # MODIFIED — lint extends para validar bloco screen_flow
├── post_save.py                             # MODIFIED — registra screen-flow.yaml node em SQLite
└── capture/
    ├── __init__.py                          # NEW
    ├── screen_capture.py                    # NEW — orchestrator Python que invoca Playwright via subprocess
    ├── determinism.ts                       # NEW — lib TS importada pelo Playwright spec
    ├── screen_capture.spec.ts               # NEW — spec Playwright que lê YAML + aplica determinism
    └── pre_commit_png_size.py               # NEW — pre-commit hook (Python, ~30 LOC)

# Skill (Markdown)
.claude/commands/
└── madruga/
    └── business-screen-flow.md              # NEW — skill L1 opcional

# Knowledge
.claude/knowledge/
├── screen-flow-vocabulary.md                # NEW — referência única dos 10 components + 4 edges + 6 badges
└── pipeline-dag-knowledge.md                # MODIFIED — adiciona 14º node L1

# Pipeline manifest
.specify/
└── pipeline.yaml                            # MODIFIED — adiciona node business-screen-flow

# Portal (TypeScript / React)
portal/src/
├── pages/
│   └── [platform]/
│       └── screens.astro                    # NEW — rota condicional SSG
├── components/
│   └── screens/                             # NEW pasta
│       ├── ScreenFlowCanvas.tsx             # xyflow wrapper + Background + Controls + MiniMap + keyboard nav
│       ├── ScreenNode.tsx                   # custom node 3-state (wireframe/captured/failed) + memo
│       ├── ActionEdge.tsx                   # custom edge 4 styles + label flutuante
│       ├── Chrome.tsx                       # device frame minimal (sem status bar fake)
│       ├── WireframeBody.tsx                # 10 sub-renderers (paleta wireframe-only)
│       ├── Hotspot.tsx                      # badge numerado + outline dashed + toggle H
│       └── Badge.tsx                        # 5 variants
├── lib/
│   ├── screen-flow.ts                       # NEW — loader YAML (build-time) + ELK + fixture fallback
│   ├── elk-layout.ts                        # NEW — config ELK layered + direction param
│   └── platforms.mjs                        # MODIFIED — descobre screen_flow.enabled per-platform
├── styles/
│   └── screen-flow-tokens.css               # NEW — CSS variables tokens (light + dark)
├── test/
│   ├── fixtures/
│   │   └── screen-flow.example.yaml         # NEW — fixture de 8 telas pra fase 2 dogfooding
│   ├── unit/
│   │   ├── ScreenNode.test.tsx              # NEW
│   │   ├── ActionEdge.test.tsx              # NEW
│   │   └── Hotspot.test.tsx                 # NEW
│   ├── visual/
│   │   └── screen-flow-canvas.spec.ts       # NEW — Playwright + jest-image-snapshot
│   └── e2e/
│       └── capture-render.spec.ts           # NEW — 1 spec integração
└── routeData.ts                             # MODIFIED — entry "Screens" condicional

# Bundle gate
portal/
├── size-limit.config.json                   # NEW — budgets per-route
└── package.json                             # MODIFIED — devDependencies + scripts test:visual / test:component / test:e2e / size

# CI workflow
.github/workflows/
├── capture-screens.yml                      # NEW — workflow_dispatch + concurrency block
└── ci.yml                                   # MODIFIED — adiciona job "size-budget"

# LFS
.gitattributes                                # MODIFIED — `*.png filter=lfs diff=lfs merge=lfs -text`

# Pre-commit
.pre-commit-config.yaml                       # MODIFIED — hook screen_flow_validator + pre_commit_png_size

# Per-platform config (sample for resenhai-expo)
platforms/resenhai-expo/
├── platform.yaml                            # MODIFIED externamente — bloco screen_flow:enabled=true (do epic perspective: documentar em quickstart)
├── business/
│   ├── screen-flow.yaml                     # NEW — gerado pela skill
│   └── shots/                               # NEW — PNGs LFS
└── e2e/
    └── auth.setup.ts                        # JÁ EXISTE — reusado pra produzir storageState

# Per-platform config (opt-out)
platforms/madruga-ai/platform.yaml           # MODIFIED — bloco screen_flow:enabled=false + skip_reason
platforms/prosauai/platform.yaml             # MODIFIED — bloco screen_flow:enabled=false + skip_reason
```

**Structure Decision**: Web application multi-target (frontend portal + python scripts + skill markdown + CI workflow). Mantém hierarquia existente do repo (portal/, .specify/scripts/, .claude/commands/, .claude/knowledge/, .github/workflows/, platforms/). Zero nova hierarquia top-level — toda extensão é aditiva dentro de pastas existentes. Mudanças cross-cutting (`pipeline.yaml`, `routeData.ts`, `platforms.mjs`, `reverse_reconcile_aggregate.py`, `platform_cli.py`) são pontos de integração documentados em data-model.md.

## Phase 0 — Outline & Research

Saída: [research.md](./research.md)

Tópicos pesquisados e consolidados:

1. **Stack visual** — xyflow v12 vs alternativas (Reaflow, react-digraph, Mermaid puro); ELK vs Dagre vs custom force-directed.
2. **Determinism em screenshots** — `addInitScript` Playwright vs flag no app vs visual regression (Percy/Chromatic).
3. **Storage de imagens** — Git LFS vs Vercel Blob vs S3 + CDN.
4. **Captura web pra apps mobile** — Expo Web vs Maestro vs simulator-based screenshots.
5. **Auth automation pra capture** — `storageState` Playwright vs login programático por screen.
6. **Bundle size budget** — `size-limit` vs `bundlesize` vs lighthouse-ci.
7. **A11y testing** — `axe-core` vs `pa11y` vs manual testing.
8. **Service Worker cleanup** — `unregister()` vs `caches.delete()` vs page-reload-only.
9. **Concurrency em GH Actions** — `concurrency` block vs lock-via-issue vs sequential matrix.
10. **Schema versioning** — JSON Schema `$schema` vs custom `schema_version` field.

Cada tópico tem decisão + rationale + alternativas consideradas em research.md.

**Output**: research.md com todas as decisões fundamentadas, sem `NEEDS CLARIFICATION` remanescente.

## Phase 1 — Design & Contracts

**Prerequisites**: research.md complete (Phase 0).

Entregáveis:

1. **data-model.md** — entidades-chave (ScreenFlow, Screen, BodyComponent, Edge/Flow, Hotspot, CaptureProfile, PlatformScreenFlowConfig, PathRule, DeterminismConfig, CaptureRecord, CaptureFailure) com atributos, relações, validações e estados.

2. **contracts/** — 3 contratos formais:
   - `screen-flow.schema.json` — JSON Schema do YAML por plataforma (vocabulário fechado, schema_version: 1).
   - `platform-yaml-screen-flow.schema.json` — JSON Schema do bloco `screen_flow` em `platform.yaml`.
   - `capture-script.contract.md` — contrato I/O do capture script (entrada: YAML + env vars; saída: PNGs + YAML atualizado + exit code).

3. **quickstart.md** — guia operacional pós-epic: como habilitar a feature numa plataforma nova, como rodar capture localmente, como rodar capture via CI, como debugar PNG noise, como interpretar `status: failed`.

4. **Agent context update** — adicionar entradas pra Active Technologies em `CLAUDE.md` via `.specify/scripts/bash/update-agent-context.sh claude` (ou equivalente) refletindo `@xyflow/react v12` + `elkjs ^0.11.1` + Playwright + Git LFS introduzidos por este epic.

**Output**: data-model.md, contracts/* (3 arquivos), quickstart.md, CLAUDE.md atualizado com active tech do epic.

## Constitution Re-Check (Pós-Phase 1)

Re-avaliação após design completo:

| Princípio | Status | Observação |
|-----------|--------|-----------|
| I. Pragmatism / Performance | ✅ | data-model.md mantém invariante "schema-first, vocabulário fechado". contracts/screen-flow.schema.json formaliza sem expandir. |
| II. Automate | ✅ | Hooks PostToolUse + pre-commit + CI permanecem. Nada manual residual. |
| III. Knowledge | ✅ | contracts/ é fonte única; knowledge file referencia. |
| IV. Fast Action | ✅ | 5 fases shippable preservadas; fixture YAML em test/fixtures permite fase 2 sem fase 4. |
| V. Alternatives | ✅ | research.md cobre 10 tópicos com pros/cons. |
| VI. Brutal Honesty | ✅ | Riscos residuais (PNG noise em telas autenticadas, LFS bandwidth) explícitos. |
| VII. TDD | ✅ | Test pyramid 4 layers verificada em quickstart.md (workflow Red→Green). |
| VIII. Collaborative | ✅ | Decisões pós-Phase 1 (jsonschema dep, vitest vs jest) registradas em decisions.md. |
| IX. Observability | ✅ | capture-script.contract.md formaliza schema de logs JSON estruturados. |

**Resultado pós-Phase 1**: ZERO violações novas. Plan aprovado para Phase 2 (`/speckit.tasks`).

## Complexity Tracking

> Sem violações constitucionais — seção vazia conforme template.

Justificativas pré-emptivas pra escolhas que poderiam parecer over-engineering:

| Escolha | Por que NÃO é over-engineering | Alternativa simples rejeitada porque |
|---------|-------------------------------|--------------------------------------|
| Vocabulário fechado de 10 components (não livre-form HTML) | Sem trava, autoria humana e geração via skill divergem; renderer fica explosivo | HTML livre forçaria renderer a interpretar markup arbitrário, perdendo comparabilidade cross-platform |
| ELK em build-time (não Dagre client-side) | ELK gera layouts limpos pra fluxos hierárquicos (caso típico de screen flows); custo zero no client | Dagre é mais leve mas produz layouts feios em DAGs com branches; trade-off de UX > peso build-time |
| Determinism via Playwright API (não flag no app) | ~80% da reprodutibilidade vem grátis via `addInitScript` + `route` + `storageState`; zero PR externo | Flag `?screenshot=1` no app exigiria coordenação cross-team contínua e introduz dívida no app |
| Git LFS (não CDN externo) | Mantém invariante "repo é fonte de verdade"; quota Free 500MB/1GB tem ~16x headroom validado | CDN externo introduz credenciais write em CI, lifecycle de versões, dependência de uptime |
| Bundle budget concreto via size-limit (não claim "TTI <1.5s") | Aspiração sem instrumentação não é gate; `size-limit` mede o que realmente importa pra rota | Lighthouse-ci é overkill pra rota estática; bundlesize é menos manutenido |
| 4-layer test pyramid (não só E2E) | Unit do validator catch rejection path; component test catch render bug; visual catch regressão; E2E catch fluxo completo | Só E2E é lento (~minutos por run); só unit não pega bugs de render xyflow |

---

handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plan completo com Technical Context (Python 3.11+ + TS/React 19 + elkjs build-time), Constitution Check zero-violations duplo (pré + pós Phase 1), Project Structure aditiva (zero nova hierarquia top-level), Phase 0 research (10 tópicos consolidados em research.md), Phase 1 design (data-model com 11 entidades, contracts/ com 3 arquivos formais — JSON Schemas + capture script contract, quickstart operacional). Stack reusada: xyflow v12 + elkjs + Astro 6 + Starlight + Playwright (todos já no portal). Zero novas deps Python core (pyyaml + jsonschema já presentes). 5 fases implementáveis: schema+skill / renderer mock / capture web / pilot resenhai-expo / drift+budget+tests. Pronto para /speckit.tasks gerar tasks.md com phases agrupadas e dispatch otimizado."
  blockers: []
  confidence: Alta
  kill_criteria: "Se durante /speckit.tasks emergir necessidade de >2 novas deps Python OU se o test framework escolhido (vitest) não estiver presente no portal e a migração custar >0.5d, reabrir Phase 0 research. Se contracts/screen-flow.schema.json não for expressivo o suficiente pra capturar todo o vocabulário fechado em uma única especificação JSON Schema válida, repensar como múltiplos arquivos (1 por entidade)."
