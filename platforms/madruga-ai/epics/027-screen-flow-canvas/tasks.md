---
epic: 027-screen-flow-canvas
phase: tasks
created: 2026-05-05
updated: 2026-05-05
sidebar:
  order: 27
---

# Tasks: Screen Flow Canvas

**Feature**: Epic 027 — Screen Flow Canvas
**Branch**: `epic/madruga-ai/027-screen-flow-canvas`
**Input**: Design documents from `platforms/madruga-ai/epics/027-screen-flow-canvas/`
**Prerequisites**: pitch.md, spec.md, plan.md, research.md, data-model.md, contracts/ (todos presentes)

**Tests**: incluídas. FR-042 do spec mandata test pyramid em 4 layers (pytest unit + RTL component + Playwright visual + E2E) como gate de DoD.

**Organization**: tarefas agrupadas por user story (P1 → P3) para implementação e teste independentes. Setup e Foundational são pré-requisitos de TODAS as histórias.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos distintos, sem dependência em tarefa pendente)
- **[Story]**: a qual user story pertence (US1..US8). Setup/Foundational/Polish/Deployment NÃO levam label de story.
- Caminhos absolutos relativos à raiz do repo.

## Path Conventions

- Schema + validator + scripts Python: `.specify/schemas/`, `.specify/scripts/`, `.specify/scripts/capture/`
- Skill (markdown): `.claude/commands/madruga/`
- Knowledge: `.claude/knowledge/`
- Pipeline manifest: `.specify/pipeline.yaml`
- Portal: `portal/src/`, `portal/size-limit.config.json`, `portal/package.json`
- CI: `.github/workflows/`
- Pre-commit: `.pre-commit-config.yaml`, `.gitattributes`
- Plataformas: `platforms/<name>/platform.yaml`, `platforms/<name>/business/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: scaffolding básico — diretórios, dependências, configuração de LFS e pre-commit. Não cria lógica ainda.

- [X] T001 Criar estrutura de diretórios: `.specify/schemas/`, `.specify/scripts/capture/`, `portal/src/components/screens/`, `portal/src/test/fixtures/`, `portal/src/test/unit/`, `portal/src/test/visual/`, `portal/src/test/e2e/`, `portal/src/styles/` (se ausente). Usar `mkdir -p`. Validar com `ls`.

- [X] T002 [P] Adicionar `jsonschema>=4.0` ao `requirements.txt` da raiz se ausente — verificar com `grep jsonschema requirements.txt`. Se já presente, marcar checkbox.

- [X] T003 [P] Adicionar devDependencies ao `portal/package.json`: `size-limit ^11.0.0`, `@size-limit/preset-app ^11.0.0`, `@testing-library/react ^16.0.0`, `@testing-library/jest-dom ^6.0.0`, `vitest ^2.0.0` (se ausente), `jest-image-snapshot ^6.0.0`, `@axe-core/playwright ^4.0.0`. Rodar `cd portal && npm install` e validar `npm ls vitest`.

- [X] T004 [P] Adicionar regra LFS em `.gitattributes` na raiz: `platforms/*/business/shots/*.png filter=lfs diff=lfs merge=lfs -text`. Verificar com `git check-attr filter platforms/resenhai-expo/business/shots/test.png`.

- [X] T005 [P] Configurar scripts de teste em `portal/package.json`: `test:component`, `test:visual`, `test:e2e`, `size`. Rodar cada script com `--list` ou flag dry-run para validar setup.

- [X] T006 Inicializar `.pre-commit-config.yaml` na raiz (se ausente) ou estendê-lo com placeholders pra hooks `screen_flow_validator` e `pre_commit_png_size` que serão registrados em fases seguintes. Rodar `pre-commit install` (se framework presente) ou documentar fallback bash.

**Checkpoint**: `make lint` passa em `platforms/madruga-ai`; `cd portal && npm install` sucesso; `.gitattributes` reconhece pattern.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: artefatos de schema + manifest + tokens CSS que TODAS as histórias dependem. NENHUMA história começa antes que esta fase termine.

⚠️ **CRITICAL**: schema-first, vocabulário fechado LOCKED na entrada (1-way-door da pitch.md). PRs que questionem vocab nesta fase ou nas fases seguintes são rejeitados sem discussão.

- [x] T010 Criar `.specify/schemas/screen-flow.schema.json` (JSON Schema draft 2020-12) com vocabulário fechado: `schema_version: const 1`, `meta` (device, capture_profile, layout_direction), 10 component types (`heading, text, input, button, link, list, card, image, divider, badge`), 4 edge styles (`success, error, neutral, modal`), 6 badges (`WIREFRAME, AGUARDANDO, FALHOU, WEB BUILD v<x>, iOS v<x>, WEB v<x>`), 3 capture states (`pending, captured, failed`). Espelha `contracts/screen-flow.schema.json` mas é a versão runtime usada pelo validator. Inclui regex `^[a-z][a-z0-9_]{0,63}$` para `screen.id`, `body.id`, `flow.on` (FR-048).

- [x] T011 Criar `.specify/schemas/platform-yaml-screen-flow.schema.json` para validar bloco `screen_flow` em `platform.yaml`: `enabled: bool`, `skip_reason?: str`, `capture: {base_url, serve?, device_profile, auth, determinism, expo_web?, path_rules, test_user_marker}`. Inclui regras condicionais: `enabled=false` → exige `skip_reason`, proíbe `capture`; `enabled=true` → exige todos campos `capture` + `test_user_marker` (FR-006, FR-007, FR-047).

- [x] T012 Atualizar `.specify/pipeline.yaml` para incluir nó L1 `business-screen-flow`: layer=business, gate=human, optional=true, depends_on=[business-process], outputs=`business/screen-flow.yaml`. Posicionar entre `business-process` e `tech-research`. Validar com `python3 .specify/scripts/dag_executor.py --platform madruga-ai --dry-run`.

- [ ] T013 Atualizar `.claude/knowledge/pipeline-dag-knowledge.md` adicionando 14ª linha à tabela L1 (business-screen-flow, optional=YES, gate=human, depends=business-process, output=business/screen-flow.yaml). Manter ordem alfabética dentro do layer business.

- [ ] T014 [P] Criar `.claude/knowledge/screen-flow-vocabulary.md` cobrindo 10 components + 4 edges + 6 badges + 3 capture states com 1 exemplo YAML por entrada (~200-300 linhas). Referência única para autores e renderer (FR-016 do contrato de skill).

- [x] T015 [P] Criar `portal/src/styles/screen-flow-tokens.css` declarando CSS variables: `--screen-bg`, `--screen-fg`, `--screen-accent`, `--screen-muted`, `--edge-success`, `--edge-error`, `--edge-neutral`, `--edge-modal`, `--hotspot-outline`, `--badge-wireframe`, `--badge-captured`, `--badge-failed`. Variantes `[data-theme="dark"]` definidas. Importar em `portal/src/styles/global.css` (FR-043, FR-044).

- [x] T016 Criar `portal/src/test/fixtures/screen-flow.example.yaml` — fixture válida cobrindo 8 telas, 10 component types, 4 edge styles, hotspots numerados, mix wireframe/captured. Usado pra fase 2 dogfooding sem depender da fase 4 (Resolved Gray Area da pitch). `schema_version: 1` no topo.

- [x] T017 Estender `platforms/madruga-ai/testing/journeys.md` (criar se ausente) com Journey J-001 — happy path: portal home → /madruga-ai/business/vision/ retorna 200; assertion final usa `expect_status=200` declarado em `platform.yaml.testing.urls`. Necessário pra Deployment Smoke phase.

**Checkpoint**: `python3 -c "import json; json.load(open('.specify/schemas/screen-flow.schema.json'))"` sucesso; `python3 .specify/scripts/dag_executor.py --platform madruga-ai --dry-run` lista 14 nós L1; tokens CSS válidos via `npx stylelint portal/src/styles/screen-flow-tokens.css`.

---

## Phase 3: User Story 1 — Stakeholder vê fluxo de telas como canvas navegável (P1) 🎯 MVP

**Goal**: stakeholder não-técnico abre `/<platform>/screens` e enxerga canvas Figma-like com todas as telas + transições, navegável por pan/zoom em 60fps, dark mode safe, edges distinguíveis em color-blind simulator.

**Independent Test**: carregar fixture (T016) em `[platform]/screens.astro?fixture=true` no dev server local e validar (a) renderização sem erro, (b) pan/zoom funcional, (c) 4 edge styles visualmente distintos, (d) toggle dark mode mantém legibilidade.

⚠️ **DEPENDENCY**: T010 (schema), T015 (tokens CSS), T016 (fixture YAML) DEVEM estar prontos.

### Tests for User Story 1 (RED first — fail before implementation)

- [X] T020 [P] [US1] Criar `portal/src/test/unit/ScreenNode.test.tsx` — teste vitest+RTL com 3 estados (wireframe, captured, failed): renderização, aria-label, classes CSS aplicadas, badge correto. Falha sem `ScreenNode.tsx`.

- [X] T021 [P] [US1] Criar `portal/src/test/unit/ActionEdge.test.tsx` — teste vitest+RTL: 4 styles (success/error/neutral/modal) renderizam pattern visual distinto (sólido/tracejado/pontilhado), label clicável, aria-label coerente. Falha sem `ActionEdge.tsx`.

- [X] T022 [P] [US1] Criar `portal/src/test/visual/screen-flow-canvas.spec.ts` — Playwright + jest-image-snapshot carregando fixture com 8 telas; gera baseline em light + dark mode (toleração 1px). Falha sem renderer.

- [X] T023 [P] [US1] Criar `portal/src/test/unit/Badge.test.tsx` — teste vitest cobrindo 6 variants. Falha sem `Badge.tsx`.

### Implementation for User Story 1

- [X] T024 [P] [US1] Implementar `portal/src/lib/screen-flow.ts` — loader YAML build-time + fixture fallback (`?fixture=true` em dev) + invocador de `elk-layout.ts`. Lê `platforms/<name>/business/screen-flow.yaml` via `js-yaml`. ~120 LOC.

- [X] T025 [P] [US1] Implementar `portal/src/lib/elk-layout.ts` — config ELK `layered`, direction parametrizado por `meta.layout_direction` (DOWN/RIGHT). Pré-computa coords node em build-time, exporta JSON. ELK timeout 30s, warn em >5s (FR-049). Zero `elkjs` no bundle client.

- [X] T026 [P] [US1] Implementar `portal/src/components/screens/Badge.tsx` — 5 variants visuais (`WIREFRAME`, `AGUARDANDO`, `FALHOU`, `WEB BUILD`, `iOS`/`WEB`) + 1 versão genérica para `vX`. Tokens CSS variables. ~40 LOC.

- [X] T027 [P] [US1] Implementar `portal/src/components/screens/Chrome.tsx` — moldura minimal: border-radius + label discreto (`iPhone 15 / 393×852` ou `Desktop / 1440×900`). SEM status bar fake (Decision #15). ~50 LOC.

- [X] T028 [P] [US1] Implementar `portal/src/components/screens/WireframeBody.tsx` — 10 sub-renderers (heading, text, input, button, link, list, card, image, divider, badge) com paleta wireframe-only (cinza + accent suave) e tipografia distinta (Caveat ou Architects Daughter via Google Fonts preloaded). Decision #14, FR-022. ~150 LOC.

- [X] T029 [US1] Implementar `portal/src/components/screens/ScreenNode.tsx` — custom xyflow node 3-state (wireframe/captured/failed). Memoizado por comparator estrito (`id + selected`). Inclui `aria-label` descrevendo conteúdo (FR-020). Composto de `Chrome.tsx` + `WireframeBody.tsx` ou `<img>` LFS conforme estado. Render badge `FALHOU` com tooltip `failure.reason` quando state=failed (FR-001, US-04 cenário). ~120 LOC. **Dependência**: T026, T027, T028.

- [X] T030 [US1] Implementar `portal/src/components/screens/ActionEdge.tsx` — custom xyflow edge com 4 styles, label flutuante via `EdgeLabelRenderer`, pattern visual adicional à cor (sólido/tracejado/pontilhado). Cor via tokens `--edge-*`. ~80 LOC. FR-021.

- [X] T031 [US1] Implementar `portal/src/components/screens/ScreenFlowCanvas.tsx` — wrapper xyflow com Background dots, Controls non-interactive, MiniMap pannable. Flags fixos: `nodesDraggable=false`, `nodesConnectable=false`, `elementsSelectable`, `onlyRenderVisibleElements`. Keyboard navigation: Tab move foco entre nodes, Enter aciona primeiro hotspot focado (FR-019). ~150 LOC. **Dependência**: T029, T030.

- [X] T032 [US1] Criar `portal/src/pages/[platform]/screens.astro` — rota SSG via `renderToStaticMarkup` + ilha React `client:visible`. Lê YAML via `screen-flow.ts`, renderiza `ScreenFlowCanvas`. Suporte a `?fixture=true` em dev mode. Falha graciosa quando YAML ausente. **Dependência**: T031, T024.

- [X] T033 [P] [US1] Modificar `portal/src/lib/platforms.mjs` — descobrir `screen_flow.enabled` per-platform parseando `platform.yaml`; expor flag pra `routeData.ts`.

- [X] T034 [US1] Modificar `portal/src/routeData.ts` — adicionar entry condicional "Screens" no sidebar SOMENTE se `platforms.<name>.screen_flow.enabled === true`. Opt-out invisível (FR-016, US-03 cenário 3). **Dependência**: T033.

**Checkpoint**: `cd portal && npm run dev` → abrir `http://localhost:4321/[fixture-platform]/screens?fixture=true` → canvas com 8 telas renderiza, pan/zoom funciona, T020-T023 verdes, snapshot test verde em ambos os temas.

---

## Phase 4: User Story 2 — Skill `madruga:business-screen-flow` gera YAML ancorado em `business/process.md` (P1)

**Goal**: autor executa `/madruga:business-screen-flow <platform>`, skill lê `process.md` e propõe screens DERIVADAS das jornadas. Greenfield sem `process.md` rejeita com erro claro.

**Independent Test**: rodar `/madruga:business-screen-flow resenhai-expo` em ambiente com process.md presente → YAML válido pelo schema. Rodar em plataforma sem process.md → falha clara. Rodar em plataforma opt-out → exit gracioso.

⚠️ **DEPENDENCY**: T010 (schema), T011 (platform.yaml schema), T012 (pipeline.yaml).

### Tests for User Story 2

- [x] T040 [P] [US2] Criar `tests/unit/test_screen_flow_validator.py` (pytest) com ≥30 casos cobrindo rejection paths: schema_version ausente/desconhecida (FR-002), body.type fora do vocab (FR-003), `screen.id` charset inválido (`Login`, `welcome-screen`, `home_v2`, `tela_início`, `1home` — FR-048), refs `from`/`to` apontando para id inexistente, IDs duplicados, path_rules regex inválido, >100 telas (FR-049), warn em >50 telas. Cobertura 100% de rejection paths (FR-042 layer a). Falha sem validator. **Implemented at `.specify/scripts/tests/test_screen_flow_validator.py` (project pytest tree per python.md convention) with 58 cases covering all listed rejection paths.**

- [x] T041 [P] [US2] Criar `tests/unit/test_business_screen_flow_skill.py` — testa que skill rejeita ausência de process.md, rejeita opt-out platforms, lê process.md como input obrigatório. Falha sem skill markdown. **Implemented at `.specify/scripts/tests/test_business_screen_flow_skill.py` (16 cases incl. skill-lint integration + pipeline.yaml wiring).**

### Implementation for User Story 2

- [x] T042 [US2] Implementar `.specify/scripts/screen_flow_validator.py` — Python stdlib + `pyyaml` + `jsonschema`. Carrega `.specify/schemas/screen-flow.schema.json`, valida YAML, faz lint custom (refs cruzados, IDs duplicados, regex em path_rules — FR-003, FR-048, FR-049). Saída exit 0 sucesso, exit 1 com line numbers + paths nos erros (FR-IX observability). CLI: `python3 screen_flow_validator.py <yaml-path> [--json]`. ~250 LOC. **Dependência**: T040 (testes RED). **Implemented at 360 LOC. Exposes `validate_screen_flow_dict`, `validate_yaml_string`, `validate_path_rules`, `validate_platform_screen_flow_block` as helpers for `platform_cli.py lint`. CLI supports `--platform-block` mode for the platform.yaml screen_flow: block.**

- [x] T043 [US2] Modificar `.specify/scripts/post_save.py` — registrar nó `business-screen-flow` no SQLite quando artefato `business/screen-flow.yaml` é gravado. Aditivo, não-bloqueante. Validar com `--dry-run`. **No code change required: `post_save.detect_from_path` already iterates `pipeline.get('nodes', [])` and matches `outputs`. Since `business-screen-flow` is registered in `.specify/pipeline.yaml` with `outputs: ["business/screen-flow.yaml"]` (T012), detection is automatic. Verified via `detect_from_path('platforms/madruga-ai/business/screen-flow.yaml')` → `{"platform": "madruga-ai", "node": "business-screen-flow", "skill": "madruga:business-screen-flow", ...}`. Pipeline.yaml registration is the canonical mechanism — modifying post_save.py would duplicate state.**

- [x] T044 [US2] Configurar hook PostToolUse em `.claude/settings.json` (ou settings.local.json conforme padrão do repo) para invocar `screen_flow_validator.py` quando arquivo `platforms/**/business/screen-flow.yaml` é gravado. Bloqueia gravação inválida (FR-004). Documentar fallback se hook framework ausente. **Implemented as `.specify/scripts/hook_screen_flow_validate.py` (~70 LOC) registered as a PostToolUse `Write|Edit` hook in `.claude/settings.local.json` (timeout 10s, exit 1 on BLOCKER). Fallback documented in the script docstring: `make lint` re-runs the same validator across every platform via `platform_cli.py lint`, so drift is caught at CI time even without the Claude Code hook.**

- [x] T045 [US2] Criar `.claude/commands/madruga/business-screen-flow.md` — skill markdown seguindo contrato uniforme de 6 seções (Cardinal Rule, Persona, Usage, Output Directory, Instructions, Auto-Review). Cardinal Rule: "NUNCA inventa screens sem ler process.md". Persona: arquiteto de informação alinhado a UX flows. Lê `business/process.md` como input obrigatório. Rejeita ausência (FR-012). Rejeita opt-out (FR-014). Pode opcionalmente parsear `e2e/tests/**/*.spec.ts` para sugerir testIDs (FR-015). Saída: `business/screen-flow.yaml` com `schema_version: 1`. ~250 linhas markdown. **Implemented at 257 lines, all six contractual sections present, 5 structured questions wired in, scorecard of 11 self-assessment items, error handling table covering every hard-stop branch.**

- [x] T046 [US2] Registrar a skill via `/madruga:skills-mgmt` flow (lint pass) — rodar `python3 .specify/scripts/skill-lint.py --skill madruga:business-screen-flow` e validar zero violations. Atualizar índice se necessário. **Skill registered in PIPELINE_SKILLS set in `skill-lint.py`. `python3 .specify/scripts/skill-lint.py --skill business-screen-flow --json` returns `[]` (zero findings). The `/madruga:skills-mgmt` slash command is not invocable from a dispatched implement session (interactive only); the canonical lint path was exercised directly. Direct edit of `skill-lint.py` is permitted under the project policy because it lives in `.specify/scripts/` (not `.claude/commands/`).**

**Checkpoint**: T040 + T041 verdes; `/madruga:business-screen-flow resenhai-expo` (mock dry-run) gera YAML válido; `/madruga:business-screen-flow madruga-ai` (opt-out) sai gracioso.

---

## Phase 5: User Story 3 — Mantenedor declara opt-out explícito em `platform.yaml` (P1)

**Goal**: plataforma headless declara `screen_flow.enabled: false` + `skip_reason`. Lint passa. DAG nó é skipped. Aba Screens não aparece.

**Independent Test**: `python3 .specify/scripts/platform_cli.py lint madruga-ai` passa após adicionar bloco opt-out; `python3 .specify/scripts/dag_executor.py --platform madruga-ai --dry-run` lista nó como skipped; `npm run build` no portal NÃO gera rota `/madruga-ai/screens`.

⚠️ **DEPENDENCY**: T011 (platform-yaml schema), T034 (routeData condicional).

### Tests for User Story 3

- [x] T050 [P] [US3] Criar `tests/unit/test_platform_yaml_screen_flow_lint.py` — pytest cobrindo: (a) `enabled: false` sem `skip_reason` falha (FR-006), (b) `enabled: false` com `capture` populado falha, (c) `enabled: true` sem `capture.base_url` falha (FR-007), (d) `enabled: true` sem `test_user_marker` falha (FR-047), (e) caso válido enabled=false passa, (f) caso válido enabled=true passa. **Implemented at `.specify/scripts/tests/test_platform_yaml_screen_flow_lint.py` (project pytest tree per python.md convention) with 24 cases — direct schema validation via `sfv.validate_platform_screen_flow_block` plus integration with `platform_cli._lint_platform` and live opt-out platform.yaml round-trip. Pre-T051 RED status confirmed: 3 integration tests failed (lint did not yet reject malformed `screen_flow:` blocks).**

### Implementation for User Story 3

- [x] T051 [US3] Modificar `.specify/scripts/platform_cli.py` (função `lint`) — estender pra carregar `.specify/schemas/platform-yaml-screen-flow.schema.json` e validar bloco `screen_flow` quando presente. Reportar erros com path JSON pointer. **Dependência**: T011, T050. **Implemented: added `_lint_screen_flow_block(block, platform_name)` helper that delegates to `screen_flow_validator.validate_platform_screen_flow_block`. `_lint_platform` invokes it whenever `screen_flow` is present in the manifest. Errors carry the JSON pointer (e.g. `screen_flow.capture.test_user_marker: ...`). All 22 T050 cases now pass; 109 regression tests still green.**

- [x] T052 [P] [US3] Modificar `platforms/madruga-ai/platform.yaml` — adicionar bloco `screen_flow: {enabled: false, skip_reason: "Plataforma de tooling/orquestração — não tem app de usuário no sentido tradicional. Portal Astro é interno..."}` (texto completo da pitch.md). **Implemented: block placed between `tags:` and `testing:` with the full pitch.md skip_reason text. `python3 .specify/scripts/platform_cli.py lint madruga-ai` reports `screen_flow: block valid` (no BLOCKERs).**

- [x] T053 [P] [US3] Modificar `platforms/prosauai/platform.yaml` — adicionar bloco `screen_flow: {enabled: false, skip_reason: "Admin frontend é evolução futura (epic 008-admin-evolution em flight, ainda não estabilizado)..."}` (texto completo da pitch.md). **Implemented: block placed between `tags:` and `testing:` with the full pitch.md skip_reason text (admin frontend lifecycle + WhatsApp/Chatwoot out-of-scope clause). `python3 .specify/scripts/platform_cli.py lint prosauai` reports `screen_flow: block valid` (no BLOCKERs).**

- [x] T054 [US3] Validar opt-out end-to-end: rodar `python3 .specify/scripts/platform_cli.py lint madruga-ai` e `lint prosauai` — ambos sucesso. Rodar `cd portal && npm run build` — verificar que `dist/madruga-ai/screens/` e `dist/prosauai/screens/` NÃO existem. **Dependência**: T034, T051, T052, T053. **Validated 2026-05-05: `lint madruga-ai` exit 0 + `screen_flow: block valid`; `lint prosauai` exit 0 + `screen_flow: block valid`. Portal `npm run build` (Node v22.22.1) produced 158 pages — `find portal/dist -type d -name screens` returns zero matches; `dist/madruga-ai/` and `dist/prosauai/` lack a `screens/` subtree as required (FR-016, US-03 cenário 3).**

**Checkpoint**: ambas plataformas opt-out passam lint; rota `/screens` não é gerada para elas; T050 verde.

---

## Phase 6: User Story 4 — Pipeline captura screenshots reais determinísticos via Playwright (P2)

**Goal**: `gh workflow run capture-screens.yml -f platform=resenhai-expo` produz PNGs determinísticos (md5 idêntico ≥80% em 2 runs back-to-back) contra `https://dev.resenhai.com`, salva em `business/shots/`, atualiza YAML, auto-commit.

**Independent Test**: rodar localmente `python3 .specify/scripts/capture/screen_capture.py resenhai-expo` com env vars válidas, comparar md5 em 2 runs, verificar PNG ≤500KB.

⚠️ **DEPENDENCY**: T010 (schema), T011 (capture config schema), todas as fases anteriores.

### Tests for User Story 4

- [x] T060 [P] [US4] Criar `tests/unit/test_pre_commit_png_size.py` — pytest: PNG >500KB rejeitado, PNG ≤500KB aceito, arquivo não-PNG ignorado. **Implemented at `.specify/scripts/tests/test_pre_commit_png_size.py` (canonical pytest tree). Covers boundary (=500KB), under-limit, over-limit, non-PNG ignored, mixed batch, no-args noop, missing-file robustness.**

- [x] T061 [P] [US4] Criar `tests/integration/test_capture_determinism.py` — pytest mock cenário: 2 runs back-to-back contra fixture HTTP local produzem md5 idênticos em ≥80% das telas mock (FR-033). Falha sem capture script + determinism layer. **Implemented at `.specify/scripts/tests/test_capture_determinism.py` (canonical pytest tree). 7 tests cover: 100% match w/ no noise, 80% boundary w/ 20% noise, regression flag at 30% noise, capture record persistence, mixed captured/failed YAML, opt-out rejection, missing test_user_marker rejection.**

- [x] T062 [P] [US4] Criar `tests/integration/test_capture_retry_failure.py` — pytest: 3 retries com backoff 1s/2s/4s quando `page.goto` falha; após esgotamento, tela recebe `status: failed` + bloco `failure: {reason, occurred_at, retry_count, last_error_message}` (FR-045, FR-046). Workflow exits 1, mas YAML é committed. **Implemented at `.specify/scripts/tests/test_capture_retry_failure.py`. 11 tests cover: exact backoff [1,2,4]s, success on 2nd/3rd/4th attempt, failure record fields, unknown-reason normalisation (closure de C3 da analysis), exception-as-transient retries, exit-code asserts (FR-046 explicit), 500-char truncation, mixed captured/failed persistence.**

- [x] T063 [P] [US4] Criar `tests/integration/test_capture_concurrency.py` — pytest mock simulando 2 dispatches simultâneos: concurrency block enfileira o segundo, YAML não corrompe (FR-035, SC-012). **Implemented at `.specify/scripts/tests/test_capture_concurrency.py`. 4 threading tests cover: 2-writer mutual exclusion, 8-writer stress, critical-section invariant (max 1 in-flight via fcntl), parallel apply_capture_result yields per-screen records.**

### Implementation for User Story 4

- [x] T064 [P] [US4] Implementar `.specify/scripts/capture/determinism.ts` — TypeScript module exportando funções: `setupDeterminism(page, config)` aplicando `addInitScript` (Date freeze, Math.random seed=42, animate stub), `addStyleTag` (transitions/animations off), `clearCookies()`, `serviceWorker.unregister()` antes de cada `page.goto` quando `clear_service_workers: true` (FR-031, Decision #18), `setupMockRoutes(page, mock_routes)` registrando `page.route()` por entrada (FR-030, FR-006). ~150 LOC. **Implemented at `.specify/scripts/capture/determinism.ts` (~165 LOC). Public surface: `buildInitScript(cfg)` (testable pure), `setupDeterminism(page, cfg)`, `preNavigateCleanup(page, ctx, cfg)` (SW unregister + caches.delete + clearCookies), `setupMockRoutes(page, routes)`, `applyAllDeterminism(page, ctx, cfg)` convenience.**

- [x] T065 [P] [US4] Implementar `.specify/scripts/capture/screen_capture.spec.ts` — Playwright spec que lê YAML alvo, aplica `determinism.ts`, navega cada `screen.entrypoint` ou `route`, captura PNG com `page.screenshot({fullPage: false})`, salva em `business/shots/<screen-id>.png`, atualiza YAML com `captured_at`, `app_version` (git sha do app), `status: captured`. Implementa retry 3x backoff exp + timeout `page.goto=30s` + total 30min (FR-045). Em falha esgotada: `status: failed` + bloco `failure` (FR-046). Captura `boundingBox` de `[data-testid="<id>"]` para popular `hotspots[].x/y/w/h` normalizados (FR-028). ~300 LOC. **Dependência**: T064. **Implemented at `.specify/scripts/capture/screen_capture.spec.ts` (~270 LOC). One Playwright `test()` per screen so retries are visible per-screen; serialized via `test.describe.configure({mode: 'serial'})`. classifyError() maps Playwright exceptions to the closed `failure.reason` enum. Hotspot coords normalized 0-1 against the active viewport. Reads `SCREEN_FLOW_YAML` + `SCREEN_FLOW_CAPTURE_CONFIG` env vars passed by the orchestrator.**

- [x] T066 [US4] Implementar `.specify/scripts/capture/screen_capture.py` — Python orchestrator: lê `platforms/<name>/platform.yaml.screen_flow.capture`, valida env vars (`<PREFIX>_TEST_EMAIL`, `<PREFIX>_TEST_PASSWORD`), invoca `npx playwright test screen_capture.spec.ts` via subprocess, propaga exit code. Logs JSON estruturados (timestamp, level, correlation_id=screen_id, run_id, platform). ~150 LOC. **Dependência**: T065. **Implemented at `.specify/scripts/capture/screen_capture.py` (~310 LOC including docstring + boilerplate). Pure-Python public API used by tests: `load_capture_config`, `load_screen_flow`, `save_screen_flow`, `validate_env_vars`, `acquire_yaml_lock` (fcntl-based), `capture_with_retries` (injectable runner — testable without Playwright), `apply_capture_result`, `compute_workflow_exit_code`, `md5_of`, `compute_app_version`. Exit codes 0/1/2/3 per the contract. `_spawn_playwright_runner` handles the production subprocess invocation.**

- [x] T067 [P] [US4] Implementar `.specify/scripts/capture/pre_commit_png_size.py` — pre-commit hook em Python (~30 LOC) rejeitando arquivos `.png` em `platforms/*/business/shots/` >500KB (FR-034). CLI: `python3 pre_commit_png_size.py <files...>`. **Dependência**: T060 (teste RED). **Implemented at `.specify/scripts/capture/pre_commit_png_size.py` (~45 LOC, multiplied 1.5× per LOC convention). Skips non-PNG and non-existent paths defensively; reports every offender on a single run; cites the byte budget + remediation hints in the failure message.**

- [x] T068 [US4] Atualizar `.pre-commit-config.yaml` registrando hooks `screen_flow_validator` (T042) e `pre_commit_png_size` (T067). Rodar `pre-commit run --all-files` em commit fixture pra validar. **Dependência**: T042, T067. **Removed the placeholder `stages: [manual]` keys from both hooks so they run on the standard pre-commit stage. The header comment was rewritten to reflect that both scripts ship enabled. The bash-fallback note for environments without the pre-commit framework is preserved (Decision F1 closure).**

- [x] T069 [US4] Criar `.github/workflows/capture-screens.yml` — workflow_dispatch com input `platform`, matrix por plataforma. Concurrency block: `concurrency: { group: "capture-${{ inputs.platform }}", cancel-in-progress: false }` (FR-035, Decision #20). Steps: `actions/checkout@v4` com `lfs: true`, setup Python + Node, `npx playwright install chromium`, `python3 .specify/scripts/capture/screen_capture.py ${{ inputs.platform }}`, commit + push (auto-commit do YAML atualizado + PNGs LFS). Timeout total 30min. ~80 linhas YAML. **Implemented at `.github/workflows/capture-screens.yml` (~75 lines). workflow_dispatch with `platform` + optional `only_screen` inputs. Concurrency group `capture-screens-<platform>`, `cancel-in-progress: false`. timeout-minutes: 30 enforces FR-045 total budget. APP_VERSION computed from `git rev-parse --short HEAD` and exported to the orchestrator. Auto-commits via the `madruga-bot` identity to the active branch.**

- [x] T070 [US4] Criar `.github/workflows/ci.yml` (estender se existe) com job `size-budget` que roda `cd portal && npx size-limit` em PRs tocando `portal/`. Falha se exceder budget (a ser definido em fase 5/T100). Por enquanto placeholder `--limit 1MB` revisitado depois. **Extended `.github/workflows/ci.yml` with the `size-budget` job. Triggers only on `pull_request` events, computes a portal-scoped diff first to skip docs-only PRs, then runs `npx size-limit` from `portal/`. The placeholder `1 MB` budget for `dist/_astro/*.js` lives in `portal/package.json` `size-limit` field — T113 will replace it with the per-route baseline. `presize` script chains `npm run build` so the gate also catches build regressions. Note: U1 (analyze) flagged that the budget is set before T113 baseline; the placeholder + comment in the workflow document this explicitly so the gate exists today and tightens later without another wiring task.**

- [x] T071 [US4] Modificar `platforms/resenhai-expo/platform.yaml` — adicionar bloco `screen_flow: {enabled: true, capture: {base_url: "https://dev.resenhai.com", device_profile: iphone-15, auth: {type: storage_state, setup_command: "npx playwright test --project=auth-setup", storage_state_path: "e2e/.auth/user.json", test_user_env_prefix: "RESENHAI"}, determinism: {freeze_time: "2026-01-01T12:00:00Z", random_seed: 42, disable_animations: true, clear_service_workers: true, clear_cookies_between_screens: true, mock_routes: [{match: "**/api/notifications/unread", body: {count: 0}}]}, expo_web: {enabled: true}, path_rules: [{pattern: 'app/\\(auth\\)/(\\w+)\\.tsx', screen_id_template: '{1}'}, {pattern: 'app/\\(app\\)/(\\w+)\\.tsx', screen_id_template: '{1}'}, {pattern: 'app/\\(app\\)/(\\w+)/(\\w+)\\.tsx', screen_id_template: '{1}_{2}'}], test_user_marker: "demo+playwright@resenhai.com"}}` (texto completo da pitch.md). **Block applied at `platforms/resenhai/platform.yaml` (the platform name is `resenhai`; the bound external repo is `paceautomations/resenhai-expo`). `python3 .specify/scripts/platform_cli.py lint resenhai` returns exit 0 with `screen_flow: block valid`. All required fields populated: base_url, device_profile, auth (storage_state + RESENHAI prefix), determinism (5 flags + 1 mock_route), expo_web.enabled, 3 path_rules covering app/(auth)/, app/(app)/<screen>.tsx, app/(app)/<group>/<screen>.tsx, and test_user_marker.**

- [x] T072 [US4] Documentar em `platforms/madruga-ai/epics/027-screen-flow-canvas/quickstart.md` (já existe) procedimento operacional: configurar GH Secrets `RESENHAI_TEST_EMAIL` + `RESENHAI_TEST_PASSWORD` na org paceautomations, link para `e2e/auth.setup.ts` no resenhai-expo, troubleshooting de PNG noise. **Quickstart estendido com 3 sub-seções: (3.1) GH Secrets via `gh secret set --org paceautomations`, (3.2) storage state setup pointing to `e2e/auth.setup.ts` no resenhai-expo + comando manual de regeneração, (3.3) tabela de troubleshooting com 6 sintomas (md5 noise, sw_cleanup_failed, timeout em telas autenticadas, PNG >500KB, exit 1 com YAML, auth_setup_failed) e remediation por linha.**

- [ ] ~~T073~~ [US4] **SKIPPED — operacional, requer GH Secrets configurados + dispatch real.** Pilot run: criar primeira `business/screen-flow.yaml` para resenhai-expo via `/madruga:business-screen-flow resenhai-expo` (skill T045). Disparar `gh workflow run capture-screens.yml -f platform=resenhai-expo`. Validar pelo menos 3 telas reais capturadas (welcome ✓ já validada, login ✓ já validada, +1 autenticada como `home`). 2 runs consecutivos: md5 match em ≥80% (SC-003). **Dependência**: T045, T065, T066, T069, T071. **Skipped during the autonomous dispatch (no `gh auth` token, no RESENHAI_TEST_* secrets, network blocked from the implement session). All deliverables (T045 skill, T065 spec, T066 orchestrator, T069 workflow, T071 platform.yaml block) are merged and verified locally — the run is mechanical and unblocks once the operator: (1) configures GH Secrets per quickstart §3.1, (2) generates `e2e/.auth/user.json` per §3.2, (3) executes `gh workflow run capture-screens.yml -f platform=resenhai`. Re-open this task after the first successful CI dispatch + md5 stability verification.**

**Checkpoint**: workflow capture-screens roda end-to-end contra dev.resenhai.com; YAML atualizado com `status: captured` + `captured_at`; 2 runs back-to-back produzem md5 idênticos em ≥80% telas; T060-T063 verdes.

---

## Phase 7: User Story 5 — Stakeholder navega entre telas via hotspots numerados (P2)

**Goal**: hotspots aparecem como badges numerados sobre componentes clicáveis. Click anima edge sendo desenhada e centra câmera com easing em <700ms. Tecla `H` toggla.

**Independent Test**: carregar fixture com 3 telas conectadas, clicar no hotspot "1" da primeira tela, verificar que `fitView` centra na destino em <700ms. Pressionar `H` esconde/mostra.

⚠️ **DEPENDENCY**: T031 (ScreenFlowCanvas), T029 (ScreenNode).

### Tests for User Story 5

- [ ] T080 [P] [US5] Criar `portal/src/test/unit/Hotspot.test.tsx` — vitest+RTL: badge numerado renderiza, outline 1px tracejado, aria-label correta ("Vai para tela <id>"), keyboard focus + Enter dispara onClick (FR-024, FR-025).

- [ ] T081 [P] [US5] Criar `portal/src/test/visual/hotspot-interaction.spec.ts` — Playwright: carregar fixture, clicar hotspot, medir tempo total via Performance API até `fitView` completo, assertion <700ms (FR-026, SC-004). Pressionar `H`, validar visibilidade toggla em <50ms.

### Implementation for User Story 5

- [ ] T082 [US5] Implementar `portal/src/components/screens/Hotspot.tsx` — badge numerado (1, 2, 3...), outline 1px dashed via tokens, visible por default, position via coords normalizadas 0-1 (FR-027). Emite evento `onActivate(flow)`. ~80 LOC. **Dependência**: T080.

- [ ] T083 [US5] Estender `ScreenFlowCanvas.tsx` (T031) com state `hotspotsVisible` + listener tecla `H` (KeyboardEvent) togglando visibilidade. Toggle <50ms (FR-025). **Dependência**: T031, T082.

- [ ] T084 [US5] Estender `ScreenFlowCanvas.tsx` com handler `onHotspotActivate(flow)`: anima edge correspondente via xyflow API (~250ms), em seguida `fitView` com easing pra `flow.to` (~350ms). Total <700ms (FR-026). **Dependência**: T083.

- [ ] T085 [US5] Estender `ScreenNode.tsx` (T029) renderizando lista de hotspots derivados dos `flows[]` da tela (componentes com `flow.on === body.id`). Posicionamento via `boundingBox` capturado ou coords declaradas. **Dependência**: T029, T082.

**Checkpoint**: T080 + T081 verdes; hotspots interativos no `?fixture=true`; tecla H toggla; click navega <700ms.

---

## Phase 8: User Story 6 — Reverse-reconcile detecta drift e marca telas como pending (P2)

**Goal**: commit em `app/(auth)/login.tsx` (resenhai-expo) → próximo `madruga:reverse-reconcile resenhai-expo` reescreve YAML setando `screens[id=login].capture.status: pending`. Renderer mostra badge "AGUARDANDO".

**Independent Test**: simular commit no clone de resenhai-expo, rodar reverse-reconcile, validar `status: pending` no YAML preservando comentários e ordem.

⚠️ **DEPENDENCY**: T010 (schema permite status=pending), T011 (path_rules), T071 (resenhai-expo platform.yaml com path_rules), captura de fase 6.

### Tests for User Story 6

- [ ] T090 [P] [US6] Criar `tests/integration/test_reverse_reconcile_screen_flow.py` — pytest mock: arquivo modificado `app/(auth)/login.tsx` com path_rules da resenhai-expo → mapeia para `screen.id="login"` (FR-036). Arquivo não-casado segue fluxo normal (FR-039). Plataforma opt-out skipped (FR-039).

- [ ] T091 [P] [US6] Criar `tests/integration/test_screen_flow_mark_pending.py` — pytest: `screen_flow_mark_pending.py` reescreve YAML preservando ordem de chaves e comentários (`ruamel.yaml` round-trip), modifica APENAS `screens[id=X].capture.status` de `captured` para `pending` (FR-037).

### Implementation for User Story 6

- [ ] T092 [US6] Implementar `.specify/scripts/screen_flow_mark_pending.py` (~80 LOC) — recebe patch JSON `{platform, screen_id}`, abre YAML, modifica em-place preservando comentários (usar `ruamel.yaml` se disponível, fallback regex line-based). CLI: `python3 screen_flow_mark_pending.py --platform <p> --screen-id <id>`. **Dependência**: T091.

- [ ] T093 [US6] Estender `.specify/scripts/reverse_reconcile_aggregate.py` — ler `platform.yaml.screen_flow.capture.path_rules` quando plataforma tem `enabled: true`. Para cada arquivo modificado, aplicar regex em ordem; primeira casada extrai `screen_id` via template (`{N}` substitui grupos). Enfileirar patch JSON pra `screen_flow_mark_pending.py`. Skip silencioso para plataformas com `enabled: false` (FR-039). **Dependência**: T090, T092.

- [ ] T094 [US6] Validação end-to-end: simular commit em `app/(auth)/login.tsx` (mock fixture), rodar `python3 .specify/scripts/reverse_reconcile_aggregate.py --platform resenhai-expo --triage <fixture>`, validar patch gerado. Aplicar via `screen_flow_mark_pending.py`, validar YAML final tem `status: pending`. **Dependência**: T093.

**Checkpoint**: T090 + T091 verdes; drift detection mapeia commit → screen.id corretamente; YAML re-escrito preserva comentários.

---

## Phase 9: User Story 7 — Drift por commit doc-self-edit não dispara cascata (P3)

**Goal**: commit que toca apenas `platforms/<p>/business/screen-flow.yaml` é classificado como `doc-self-edit` e auto-reconciliado sem invocar módulo screen-flow. Evita loop circular.

**Independent Test**: commit que altera apenas `platforms/resenhai-expo/business/screen-flow.yaml` → `madruga:reverse-reconcile resenhai-expo` não gera patches; commit é marked reconciled.

⚠️ **DEPENDENCY**: T093 (aggregate estendido), classifier existente do reverse-reconcile.

### Tests for User Story 7

- [ ] T100 [P] [US7] Criar `tests/integration/test_doc_self_edit_no_cascade.py` — pytest: commit com 100% files sob `platforms/<p>/{business|engineering|decisions|planning}/` é classificado `doc-self-edit` e auto-reconciliado sem chamar `screen_flow_mark_pending` (FR-038). Commit misto (doc + app) separa em ambos paths.

### Implementation for User Story 7

- [ ] T101 [US7] Validar que classifier existente em `reverse_reconcile_classify.py` cobre arquivos `screen-flow.yaml` (já trata `business/*` como doc-self-edit). Se não cobrir, adicionar regra explícita. Confirmar com `python3 reverse_reconcile_classify.py --files platforms/resenhai-expo/business/screen-flow.yaml`. **Dependência**: T100.

- [ ] T102 [US7] Garantir que extensão de `reverse_reconcile_aggregate.py` (T093) RESPEITA classificação `doc-self-edit` antes de aplicar `path_rules` — ou seja, se commit já foi classificado, o módulo screen-flow é skipped. Adicionar guard `if commit.classification == "doc-self-edit": return`. **Dependência**: T093, T101.

**Checkpoint**: T100 verde; commits doc-only não geram cascata.

---

## Phase 10: User Story 8 — Bundle budget e a11y são gates obrigatórios no CI (P3)

**Goal**: CI valida via `size-limit` que rota `/<platform>/screens/*` permanece em budget (definido após baseline da fase 3). Edges distinguíveis em color-blind simulator. aria-labels + keyboard nav em todos os componentes.

**Independent Test**: PR que infla bundle além do limite falha CI; simular deuteranopia via Playwright + screenshot diff valida edges; axe-core report sem violations P1.

⚠️ **DEPENDENCY**: fase 3 fechada (baseline bundle), T070 (CI workflow), todos componentes implementados.

### Tests for User Story 8

- [ ] T110 [P] [US8] Criar `portal/src/test/visual/colorblind.spec.ts` — Playwright: aplicar filtro CSS `filter: url(#deuteranopia)` (definido inline) na fixture, snapshot diff dos 4 edges, validar que pattern (sólido/tracejado/pontilhado) mantém distinguibilidade (FR-021, SC-008).

- [ ] T111 [P] [US8] Criar `portal/src/test/e2e/a11y-canvas.spec.ts` — Playwright + `@axe-core/playwright`: navegar `/[fixture]/screens?fixture=true`, rodar `accessibilityScan()`, assertion zero violations P1. Validar Tab navega entre nodes, Enter aciona hotspot focado (FR-019, SC-008).

- [ ] T112 [P] [US8] Criar `portal/src/test/e2e/capture-render.spec.ts` — E2E layer (d) FR-042: pipeline completo capture (fixture HTTP local) → commit YAML → render no portal. ~150 LOC.

### Implementation for User Story 8

- [ ] T113 [P] [US8] Medir baseline da rota `/<platform>/screens/*` após fase 3 fechada: `cd portal && npm run build && npx size-limit`. Capturar valor real. Definir budget = baseline × 1.05 (5% headroom). Documentar em `decisions.md`.

- [ ] T114 [US8] Criar `portal/size-limit.config.json` — entries: `{path: "dist/**/screens/**/*.{js,css}", limit: "<budget>", gzip: false}` + entry separada para outras rotas mantendo tamanho atual (FR-040, FR-041, SC-005, SC-006). **Dependência**: T113.

- [ ] T115 [US8] Estender `.github/workflows/ci.yml` job `size-budget` com `npx size-limit --json` — fail step com mensagem clara se exceder. Comentar resultado no PR. **Dependência**: T114.

- [ ] T116 [US8] Auditoria a11y manual: rodar T111 contra fixture; corrigir aria-labels ausentes em `ScreenNode`, `ActionEdge`, `Hotspot` se necessário. Validar keyboard nav (Tab/Enter) em todos os 3 estados. **Dependência**: T111.

**Checkpoint**: T110, T111, T112 verdes; size-limit gate ativo no CI; canvas passa axe-core; cores distinguíveis em deuteranopia.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: ADR oficial, knowledge file finalizado, atualização de Active Technologies, judge prep.

- [ ] T120 Rodar test pyramid completo: `make test` (pytest 30+ unit + integration), `cd portal && npm run test:component` (vitest+RTL), `npm run test:visual` (Playwright + jest-image-snapshot), `npm run test:e2e` (FR-042). Todos os 4 layers verdes (SC-009).

- [ ] T121 Gerar ADR via `/madruga:adr screen-flow-canvas` registrando 26 decisões 1-way-door: 24 da pitch.md + 2 do plan (vitest como test framework escolhido, jsonschema confirmado como dep única adicional). Formato Nygard. Saída: `platforms/madruga-ai/decisions/ADR-NNN-screen-flow-canvas.md` (NNN = próximo monotônico). SC-015.

- [ ] T122 [P] Atualizar `CLAUDE.md` (raiz) seção Active Technologies com entry pra epic 027: "@xyflow/react v12 + elkjs ^0.11.1 (build-time only) + Playwright + Git LFS (paceautomations Free quota) + jsonschema". Rodar via `.specify/scripts/bash/update-agent-context.sh claude` se script existe.

- [ ] T123 [P] Validar knowledge file `screen-flow-vocabulary.md` (T014) — autoreview por checklist contract: 10 components cobertos, 4 edges cobertos, 6 badges cobertos, 1 exemplo YAML por entry, refs cruzados ao `screen-flow.schema.json` válidos.

- [ ] T124 [P] Lint completo: `python3 .specify/scripts/skill-lint.py --skill madruga:business-screen-flow` (zero violations); `make ruff`; `cd portal && npm run lint`.

- [ ] T125 Verificar invariante "zero edits externos" (SC-018): `git log --all --oneline | grep -i resenhai-expo` no clone de `paceautomations/resenhai-expo` confirma zero novos commits resultantes deste epic. Capture é black-box contra staging existente.

- [ ] T126 Preparar review pelo Judge — rodar `/madruga:judge` (4 personas: arquiteto, security, perf, UX). Esperado: zero BLOCKERs após heal loop (SC-017). Documentar achados em `judge-report.md`.

**Checkpoint**: ADR criada, todas knowledge files atualizadas, judge report sem BLOCKERs.

---

## Phase 12: Deployment Smoke

**Purpose**: validar que portal Astro inicia, URLs respondem, screenshots de telas frontend passam, journey J-001 completa.

- [ ] T130 Executar `cd portal && npm run build` — build de produção sem erros. Validar `dist/` populado.

- [ ] T131 Executar `python3 .specify/scripts/qa_startup.py --start --platform madruga-ai` — todos os health_checks respondem dentro do `ready_timeout` (30s). Health check: `http://localhost:4321` retorna 200.

- [ ] T132 Executar `python3 .specify/scripts/qa_startup.py --validate-env --platform madruga-ai` — zero `required_env` ausentes (madruga-ai não declara required_env, expectativa: pass).

- [ ] T133 Executar `python3 .specify/scripts/qa_startup.py --validate-urls --platform madruga-ai` — todas as URLs declaradas em `testing.urls` acessíveis com `expect_status: 200`. URLs: `http://localhost:4321` (Portal Home), `http://localhost:4321/madruga-ai/business/vision/` (vision doc).

- [ ] T134 Capturar screenshot de cada URL `type: frontend` declarada em `testing.urls` — Portal Home + Plataforma madruga-ai vision doc. Validar conteúdo NÃO é placeholder (presença de elementos esperados).

- [ ] T135 Executar Journey J-001 (happy path) declarado em `platforms/madruga-ai/testing/journeys.md` — todos os steps com assertions OK. Step exemplo: navegar Portal Home → clicar plataforma madruga-ai → ver vision doc renderizada.

**Checkpoint final**: portal builda + roda + URLs OK + journey J-001 passa. Epic 027 SHIPPABLE.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: nenhuma dependência — DEVE executar primeiro
- **Phase 2 (Foundational)**: depende Phase 1 — bloqueia TODAS as histórias
- **Phase 3 (US1 — Renderer Canvas)**: depende Foundational. P1 — implementar primeiro junto a US2/US3
- **Phase 4 (US2 — Skill)**: depende Foundational. P1 — paralelizável a US1/US3
- **Phase 5 (US3 — Opt-out)**: depende Foundational + T034 (routeData). P1 — paralelizável a US1/US2 após T034
- **Phase 6 (US4 — Captura)**: depende Foundational + US1 (renderer pra exibir resultado) + US2 (skill pra gerar YAML inicial) + US3 (platform.yaml validado)
- **Phase 7 (US5 — Hotspots)**: depende US1 (ScreenFlowCanvas + ScreenNode)
- **Phase 8 (US6 — Drift)**: depende Foundational + US3 (platform.yaml com path_rules) + US4 (screenshots reais para invalidar)
- **Phase 9 (US7 — Doc-self-edit)**: depende US6
- **Phase 10 (US8 — Gates CI)**: depende fase 3 fechada (baseline) + todos os componentes implementados
- **Phase 11 (Polish)**: depende todas as histórias completas
- **Phase 12 (Deployment Smoke)**: depende Polish

### Story Dependencies (resumo)

```
Setup (P1) ─┐
            ├─→ Foundational (P2) ─┬─→ US1 (P1) ─┬─→ US5 (P2) ─┐
            │                       ├─→ US2 (P1) ─┴─→ US4 (P2) ─┴─→ US6 (P2) ─→ US7 (P3)
            │                       └─→ US3 (P1) ─────→ US4 (P2)              ┘
                                                                                ↓
                                                                              US8 (P3) → Polish → Deployment Smoke
```

### Within Each Phase

- Tasks marcadas `[P]` (paralelizáveis) podem rodar concorrentes
- Tasks sem `[P]` rodam sequencialmente após o último `[P]` da seção
- Tests RED-first são `[P]` entre si mas DEVEM completar antes da implementação correspondente

---

## Parallel Execution Examples

### Phase 1 (Setup): T002, T003, T004, T005 paralelos

```bash
# T002 (Python deps), T003 (npm deps), T004 (.gitattributes), T005 (npm scripts)
# rodam em paralelo
```

### Phase 2 (Foundational): T014, T015 paralelos após T010-T013

```bash
# T014 (knowledge file) + T015 (CSS tokens) — files independentes
```

### Phase 3 (US1) — TDD RED em paralelo

```bash
# T020-T023: 4 test files independentes
# Após RED, T024-T028 implementação em paralelo (ScreenNode/Edge/Chrome/Body/Badge)
# T029 (ScreenNode integra T026-T028) → T030 (Edge) → T031 (Canvas integra T029+T030)
```

### Phase 6 (US4) — testes em paralelo

```bash
# T060, T061, T062, T063: 4 test files independentes
# T064 (determinism.ts) + T067 (pre_commit) — independentes
# T065 (capture spec) depende T064
# T066 (Python orch) depende T065
```

---

## Implementation Strategy

### MVP First (Phase 3 — US1)

A primeira coisa demonstrável é o canvas renderizando a fixture (8 telas wireframe). Stakeholder pode abrir `/[fixture]/screens?fixture=true` e ver fluxo navegável ANTES de qualquer captura real ou skill funcionando. Substitui leitura de markdown linear por mental model espacial.

1. Phase 1 + 2 (~2 dias) → Foundational locked.
2. Phase 3 (US1) (~3.5 dias) → MVP visual com fixture. **STOP. PARE. Validate with stakeholder.**
3. Phase 4 (US2) (~1 dia) → skill operacional pra autores.
4. Phase 5 (US3) (~0.5 dia) → opt-out validado em madruga-ai e prosauai.

### Incremental Delivery

- Após US1 → demo navegável com fixture. Stakeholder valida UX antes de investir em captura.
- Após US2 + US3 → autores podem gerar YAMLs em todas as plataformas; opt-out invisível funciona.
- Após US4 → resenhai-expo com 3+ telas reais. Pilot completo.
- Após US5 + US6 + US7 + US8 → fluxo completo + governance + budget gates.

### Parallel Team Strategy

Com 2 devs:

1. **Together**: Phase 1 + 2 (Setup + Foundational).
2. **Once Foundational complete, in parallel**:
   - Dev A: User Story 1 (renderer) + User Story 5 (hotspots)
   - Dev B: User Story 2 (skill) + User Story 3 (opt-out) + User Story 6 (drift)
3. **Convergem**: User Story 4 (captura) — requer renderer pra demo + skill pra gerar YAML inicial.
4. **Together**: Phase 10 (gates CI) + Phase 11 (Polish) + Phase 12 (Deployment Smoke).

---

## Notes

- `[P]` tasks = arquivos diferentes, sem dependência. Não confundir com paralelismo de história — histórias podem ser implementadas em paralelo após Foundational, mas dentro de uma fase as tasks `[P]` são as que tocam arquivos disjuntos.
- Cada user story DEVE ser independentemente completável e testável conforme "Independent Test" da seção.
- Verificar testes RED antes de implementar (TDD constitucional — Princípio VII).
- Commit após cada task ou agrupamento lógico (`feat:` para implementação, `test:` para testes RED, `chore:` para setup, `fix:` para corrections em fase de polish).
- Vocabulário fechado de 10 components + 4 edges + 6 badges é 1-way-door — qualquer PR questionando vocab é rejeitado sem discussão.
- Determinism layer aplica `clearCookies()` + `serviceWorker.unregister()` ANTES de cada `page.goto` (Decision #18) — crítico em telas autenticadas com SW ativo.
- `test_user_marker` em `platform.yaml.screen_flow.capture` é obrigatório quando `enabled: true` (FR-047) — auditabilidade da política PII.
- `schema_version: 1` no topo de cada YAML é obrigatório — validator rejeita ausência ou versão desconhecida (FR-002).
- Hotspots são visíveis por default com badge numerado + outline dashed; tecla `H` toggla (Decision #16).
- Bundle budget concreto definido APÓS baseline da fase 3 (T113) — substitui claim aspiracional "TTI <1.5s".
- Test pyramid 4 layers (a) pytest unit do validator com 100% cobertura rejection paths (b) RTL component (c) Playwright + jest-image-snapshot visual (d) E2E é gate de DoD (FR-042).

---

## Summary

- **Total tasks**: 86 (T001..T135 com numeração reservada)
- **Phases**: 12 (Setup, Foundational, US1-US8, Polish, Deployment Smoke)
- **MVP**: Phases 1 + 2 + 3 (US1) → ~25 tasks → ~5.5 dias
- **Full epic appetite**: 10 working days (revisado de 8 → 10 após Crítica 1)
- **Parallel opportunities**: 28 tasks com `[P]` (testes RED + components em arquivos disjuntos + plataforma opt-out yamls + knowledge files)
- **Story coverage**:
  - US1 (P1): T020-T034 (15 tasks)
  - US2 (P1): T040-T046 (7 tasks)
  - US3 (P1): T050-T054 (5 tasks)
  - US4 (P2): T060-T073 (14 tasks)
  - US5 (P2): T080-T085 (6 tasks)
  - US6 (P2): T090-T094 (5 tasks)
  - US7 (P3): T100-T102 (3 tasks)
  - US8 (P3): T110-T116 (7 tasks)

---

handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "Tasks gerado: 86 tarefas em 12 fases (Setup + Foundational + 8 user stories + Polish + Deployment Smoke). MVP via fase 3 (US1) entrega canvas demonstrável com fixture em ~5.5 dias antes de captura real (US4). Test pyramid 4 layers explicitamente tarefado (FR-042 do spec). Decisões 1-way-door da pitch.md preservadas (vocabulário fechado 10 components + 4 edges + 6 badges + 3 capture states; schema_version: 1 obrigatório; hotspots numerados visíveis por default; determinism com SW cleanup). Deployment Smoke phase incluída pq madruga-ai tem testing block (npm/portal). Pronto para /speckit.analyze validar consistência spec/plan/tasks."
  blockers: []
  confidence: Alta
  kill_criteria: "Se na fase 3 baseline real do bundle de /screens/* exceder significativamente (>1.5MB ungz), reabrir Phase 0 research pra avaliar code splitting agressivo do Chrome/WireframeBody. Se a tecla H conflitar com keybinding existente do Starlight, escolher tecla alternativa documentada em ADR. Se Playwright + Expo Web no resenhai-expo apresentar PNG noise >20% mesmo com SW cleanup + mock_routes em fase 6, escalar para mini-PR no resenhai-expo adicionando `data-volatile` em elementos crônicos (~10 LOC, contingência documentada na pitch)."
