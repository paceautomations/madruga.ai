# Tasks: Runtime QA & Testing Pyramid

**Input**: Design documents from `platforms/madruga-ai/epics/026-runtime-qa-testing-pyramid/`
**Prerequisites**: spec.md (required), plan.md (required), pitch.md (required), data-model.md, contracts/qa_startup_cli.md, contracts/journeys_schema.md
**Tests**: Incluídos — TDD para `qa_startup.py` (constitution, ADR-004); testes de lint para platform.yaml.

**Organization**: Tarefas agrupadas em 7 fases ordenadas por dependência (ver plan.md). A Phase 1 (infraestrutura Python) DEVE completar antes das Phases 3-4 que referenciam `qa_startup.py` em skill files. Dentro de cada phase, tarefas marcadas [P] podem rodar em paralelo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependências incompletas)
- **[Story]**: User story correspondente da spec.md ([US1]–[US7])
- Incluir caminhos de arquivo exatos nas descrições

---

## Phase 1: Foundational — Python Infrastructure: qa_startup.py

**Goal**: Implementar `qa_startup.py` com cobertura de testes completa. Todas as phases subsequentes dependem deste script existir e ter testes verdes.

**Independent Test**: `make test` verde após esta phase — test_qa_startup.py incluído na suite com 0 falhas.

**⚠️ CRÍTICO**: Fases 3–5 editam skill files que referenciam `qa_startup.py --start`, `--validate-env`, `--validate-urls`. Não editar skills antes desta phase estar completa.

- [x] T001 Criar `.specify/scripts/qa_startup.py` com skeleton completo: imports (subprocess, pathlib, urllib.request, urllib.error, json, argparse, time, re, os, yaml), dataclasses (StartupConfig, HealthCheck, URLEntry, TestingManifest, Finding, HealthCheckResult, URLResult, StartupResult) per `data-model.md`, e estrutura argparse em `main()` com flags `--platform`, `--cwd`, `--json`, `--parse-config`, `--start`, `--validate-env`, `--validate-urls`, `--full`
- [x] T002 [P] Implementar `load_manifest(platform: str, repo_root: Path) -> TestingManifest | None` em `.specify/scripts/qa_startup.py` — ler `$REPO_ROOT/platforms/<platform>/platform.yaml` via yaml.safe_load; extrair bloco `testing:`; retornar None se ausente; mapear campos para dataclasses por `data-model.md`; handle campos opcionais com defaults
- [x] T003 [P] Implementar `parse_journeys(content: str) -> list[dict]` em `.specify/scripts/qa_startup.py` — extrair blocos YAML fenced com regex `r"```yaml\n(.*?)```"` (re.DOTALL); aplicar yaml.safe_load em cada bloco; manter apenas dicts onde `id` começa com `J-`; ignorar blocos malformados silenciosamente (per contracts/journeys_schema.md)
- [x] T004 [P] Implementar `_read_env_keys(env_path: Path) -> set[str]` em `.specify/scripts/qa_startup.py` — ler apenas nomes de variáveis (keys) do .env; pular comentários (#) e linhas vazias; extrair chave via split no primeiro `=`; retornar set vazio se arquivo ausente (FR-022: nunca ler valores)
- [x] T005 Implementar `validate_env(manifest: TestingManifest, cwd: Path) -> StartupResult` em `.specify/scripts/qa_startup.py` — comparar `manifest.required_env` vs keys lidos de `cwd / manifest.env_file`; finding BLOCKER por required_env ausente; WARN para chaves em `.env.example` mas ausentes no `.env` real e não em required_env; retornar StartupResult com `env_missing` e `env_present` contendo apenas nomes (FR-022); se `env_file` None → retornar StartupResult status:ok vazio
- [x] T006 Implementar `quick_check(health_checks: list[HealthCheck], timeout: int = 3) -> bool` em `.specify/scripts/qa_startup.py` — urllib.request.urlopen com timeout=3s para cada health check; retornar True se todos respondem com expect_status; capturar URLError/HTTPError silenciosamente; retornar False em qualquer falha
- [x] T007 Implementar `execute_startup(manifest: TestingManifest, cwd: Path) -> tuple[int, str]` em `.specify/scripts/qa_startup.py` — dispatch por startup.type: docker→`docker compose up -d`, npm→`npm run dev`, make→`make run`, venv/script→`manifest.startup.command` (obrigatório), none→noop; subprocess.run com cwd=cwd, capture_output=True, timeout=30; retornar (returncode, stderr); NUNCA executar docker compose down (invariante ADR)
- [x] T008 Implementar `wait_for_health(health_checks: list[HealthCheck], startup_type: str, timeout: int, cwd: Path) -> StartupResult` em `.specify/scripts/qa_startup.py` — polling loop a cada 2s via `quick_check()`; parar quando todos passam ou timeout expira; no timeout coletar `docker compose logs --tail 50` via subprocess se startup_type=docker; retornar StartupResult com HealthCheckResult por check e BLOCKER listing quais passaram/falharam
- [x] T009 Implementar `validate_urls(manifest: TestingManifest) -> StartupResult` em `.specify/scripts/qa_startup.py` — urllib.request por URLEntry; BLOCKER para ConnectionRefusedError/timeout (incluir hint por startup.type: docker→"checar docker compose ps + port bindings", npm→"checar se npm run dev está rodando"); BLOCKER para status code fora do esperado; handle `expect_redirect` (follow_redirects=False, checar Location header); WARN via `_is_placeholder()` para conteúdo placeholder; retornar StartupResult com URLResult por entry
- [x] T010 [P] Implementar `_is_placeholder(body: bytes, content_type: str, url_type: str) -> bool` em `.specify/scripts/qa_startup.py` — 4 critérios OR (FR-023): (1) len(body.strip()) < 500; (2) body contém qualquer literal ["You need to enable JavaScript", "React App", "Vite + React", "Welcome to nginx", "It works!"]; (3) `<body>` apenas com whitespace; (4) HTTP 200 com content_type não contendo "text/html" para url_type=="frontend"
- [x] T011 Implementar `start_services(manifest: TestingManifest, cwd: Path) -> StartupResult` e `run_full(manifest, cwd) -> StartupResult` e completar `main()` em `.specify/scripts/qa_startup.py` — `start_services`: quick_check→se ok retornar com skipped_startup:true, senão execute_startup→wait_for_health; `run_full`: sequenciar start→validate_env→validate_urls mergindo findings; `main()`: detectar REPO_ROOT via env var ou Path(__file__).parents[2], load_manifest, dispatch para operação, serializar StartupResult como JSON se --json else resumo texto, exit codes: 0=ok/warn, 1=blocker, 2=config error, 3=unexpected
- [x] T012 Criar `.specify/scripts/tests/test_qa_startup.py` com cobertura completa usando unittest.mock — testes para: `load_manifest` (bloco válido/ausente/incompleto); `parse_journeys` (YAML válido/malformado/não-journey); `_read_env_keys` (.env presente/ausente/comentários/values complexos); `validate_env` (required presente/ausente, optional ausente); `quick_check` + `wait_for_health` (mock urlopen → 200/timeout/error, loop parcial, timeout completo); `execute_startup` (mock subprocess.run por tipo incluindo none); `validate_urls` + `_is_placeholder` (todos 4 critérios individualmente, redirect, connection refused, status mismatch); `main()` CLI (argparse dispatch, exit codes) — rodar `make test` ao final para confirmar 0 falhas

**Checkpoint**: `make test` verde com test_qa_startup.py incluído. `python3 .specify/scripts/qa_startup.py --help` responde sem error. Fases 2–6 podem avançar.

---

## Phase 2: User Story 1 — Declaração de Configuração de Testes (P1)

**Goal**: Mantenedores de plataforma podem declarar como iniciar serviços, quais URLs validar e quais env vars são obrigatórias via bloco `testing:` no `platform.yaml`. Plataformas sem o bloco mantêm comportamento atual inalterado.

**Independent Test**: `python3 .specify/scripts/platform_cli.py lint --all` verde — madruga-ai e prosauai validam com testing: block sem erros; outras plataformas passam sem alteração.

- [x] T013 [US1] Adicionar bloco `testing:` a `platforms/madruga-ai/platform.yaml` — startup.type: npm, command: "cd portal && npm run dev", ready_timeout: 30; health_checks: [{url: http://localhost:4321, method: GET, expect_status: 200, label: "Portal Dev Server"}]; urls: [{url: http://localhost:4321, type: frontend, label: "Portal Home", expect_status: 200}, {url: http://localhost:4321/platforms/madruga-ai, type: frontend, label: "Plataforma madruga-ai", expect_status: 200}]; required_env: []; env_file: null; journeys_file: testing/journeys.md (per plan.md Phase 2)
- [x] T014 [US1] Adicionar bloco `testing:` a `platforms/prosauai/platform.yaml` — startup.type: docker, command: null, ready_timeout: 120; health_checks: 2 entries (API Backend http://localhost:8050/health com expect_body_contains: '"status"', Admin Frontend http://localhost:3000); urls: 4 entries (health GET 200, login POST [200,401], root com expect_redirect:/login, login page com expect_contains:["email","password"]); required_env: [JWT_SECRET, ADMIN_BOOTSTRAP_EMAIL, ADMIN_BOOTSTRAP_PASSWORD, DATABASE_URL]; env_file: .env.example; journeys_file: testing/journeys.md (per plan.md Phase 2)
- [x] T015 [P] [US1] Criar `platforms/madruga-ai/testing/journeys.md` com J-001 (Portal carrega e exibe plataformas, required: true, steps: browser navigate+screenshot+assert_contains "madruga-ai"+assert_contains "prosauai") e J-002 (Pipeline status visible via CLI, required: false, step: api GET http://localhost:4321 assert_status: 200) — formato YAML fenced por contracts/journeys_schema.md; doc em PT-BR
- [x] T016 [P] [US1] Criar `platforms/prosauai/testing/journeys.md` com J-001 (Admin Login Happy Path, required: true, steps: api GET http://localhost:3000 assert_redirect:/login + browser navigate+screenshot login page + browser fill_form email/password + click submit + screenshot + assert_contains "Dashboard"), J-002 (Webhook ingest + tenant isolation, required: false, step: api POST http://localhost:8050/api/v1/webhook assert_status: [200,422]), J-003 (Cookie expirado → redirect /login, required: false, step: browser navigate dashboard sem cookie + assert_contains "login") — formato YAML fenced per schema
- [x] T017 [US1] Adicionar skeleton `testing:` condicional ao `.specify/templates/platform/template/platform.yaml.jinja` — bloco `{%- if testing_startup_type is defined and testing_startup_type != 'none' %}` com campos: startup (type, command: null, ready_timeout: 60), health_checks: [], urls: [], required_env: [], env_file: null, journeys_file: testing/journeys.md (per data-model.md Template Copier section)
- [x] T018 [US1] Adicionar `_lint_testing_block(testing_data: dict, platform_name: str) -> list[str]` a `.specify/scripts/platform_cli.py` — validar: `startup.type` presente e em [docker, npm, make, venv, script, none]; se type=script ou venv, `startup.command` obrigatório; `health_checks` é lista (pode estar vazia); cada health_check tem `url` e `label`; `urls` é lista; cada url tem `url`, `type` (api|frontend), `label`; `required_env` é lista de strings — chamar de `_lint_platform()` quando chave `testing:` presente; retornar lista de strings de erro
- [x] T019 [US1] Adicionar testes de `_lint_testing_block()` em `.specify/scripts/tests/test_platform.py` — bloco testing: válido passa sem erros; startup.type ausente falha com mensagem; tipo inválido falha; type=script sem command falha; health_checks lista vazia passa; url com type inválido (api|frontend) falha; required_env com não-string falha; testing: ausente → _lint_testing_block não chamada
- [x] T020 [US1] Executar `python3 .specify/scripts/platform_cli.py lint --all` e `make test` — confirmar 0 erros de lint para madruga-ai e prosauai (com testing: block) e para todas as demais plataformas (sem testing: block, retrocompatibilidade); confirmar testes de T019 verdes

**Checkpoint**: `platform_cli.py lint --all` verde. `journeys.md` criados para madruga-ai e prosauai. Template Copier atualizado. Phases 3–4 podem editar qa.md.

---

## Phase 3: User Stories 2+3 — QA Skill Wave 1: Políticas Imediatas

**Goal**: Mudanças não-disruptivas em qa.md que valem independentemente de `testing:` block: env diff obrigatório (US-03), BLOCKER em vez de SKIP silencioso para L5 (US-02), screenshots obrigatórios para URLs frontend (US-04 parcial).

**Independent Test**: Após edições em qa.md, `python3 .specify/scripts/skill-lint.py --skill madruga/qa` retorna 0 erros.

- [x] T021 [US2] [US3] Editar `.claude/commands/madruga/qa.md` — adicionar subseção **Env Diff** na Phase 0 (antes de Environment Detection): quando `testing:` block existe e `testing.env_file` está declarado, executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --platform $PLATFORM --cwd $(pwd) --validate-env --json`; parsear JSON output; variável em `required_env` ausente → BLOCKER imediato com nome da var e mensagem `"variável obrigatória declarada em testing.required_env"`; variável em .env.example mas ausente e não em required_env → WARN; se `env_file` null → skip silencioso
- [x] T022 [US2] Editar `.claude/commands/madruga/qa.md` — atualizar comportamento L5 quando `testing:` block existe e services inacessíveis: substituir `⏭️ L5: No server running — skipping` por `❌ L5: BLOCKER — testing.urls declarado mas serviços inacessíveis. Execute: python3 $REPO_ROOT/.specify/scripts/qa_startup.py --start --platform $PLATFORM --cwd <platform_cwd>`; nunca skip silencioso quando testing: block declarado (GAP-01/03)
- [x] T023 [US4] Editar `.claude/commands/madruga/qa.md` — adicionar política GAP-10 em L6 (Browser Testing): quando Playwright MCP disponível e testing.urls declarado, capturar screenshot obrigatório para cada URL `type: frontend`; validar: título da página não vazio, body não é placeholder HTML per FR-023; screenshot ausente → WARN; conteúdo parece placeholder → WARN com URL
- [x] T024 Executar `python3 .specify/scripts/skill-lint.py --skill madruga/qa` — confirmar 0 erros de lint; se falhar, corrigir o qa.md antes de avançar para Phase 4

**Checkpoint**: qa.md passa skill-lint. Políticas não-disruptivas ativas (sem breaking change para plataformas sem testing: block).

---

## Phase 4: User Stories 2+3+4 — QA Skill Wave 2: Startup + Reachability

**Goal**: qa.md ganha Phase 0 completa que lê o testing: manifest, inicia serviços automaticamente e valida reachability de URLs. Depende de qa_startup.py (Phase 1) e mudanças da Wave 1 (Phase 3).

**Independent Test**: Após edições, `python3 .specify/scripts/skill-lint.py --skill madruga/qa` verde. Para plataformas sem testing: block, comportamento atual preservado.

- [ ] T025 [US2] [US3] [US4] Editar `.claude/commands/madruga/qa.md` — adicionar seção `### Phase 0: Testing Manifest` ANTES do Environment Detection existente: (1) detectar plataforma ativa via `python3 $REPO_ROOT/.specify/scripts/platform_cli.py current`; (2) ler testing: block via `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --platform $PLATFORM --cwd $(pwd) --parse-config --json`; (3) se testing: ausente (exit code 2) → continuar para Environment Detection com comportamento atual (retrocompatibilidade US-01 SC-007); (4) se testing: presente → usar como contexto autoritativo para L4/L5/L6
- [ ] T026 [US2] Editar `.claude/commands/madruga/qa.md` — adicionar passo de startup na Phase 0: executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --platform $PLATFORM --cwd $(pwd) --start --json`; parsear StartupResult; `status: blocker` → BLOCKER com lista de health checks falhados + diagnostic output (container logs incluídos no `detail`); `skipped_startup: true` → log INFO "Serviços já rodando e saudáveis — startup pulado"; `status: warn` → WARN e continuar
- [ ] T027 [US4] Editar `.claude/commands/madruga/qa.md` — adicionar passo de validação de URLs na Phase 0 (após startup): executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --platform $PLATFORM --cwd $(pwd) --validate-urls --json`; parsear URLResult por URL; connection refused → BLOCKER com URL + hint específico por startup.type (docker: "verifique docker compose ps e port bindings em docker-compose.override.yml"); status code inesperado → BLOCKER; placeholder HTML → WARN
- [ ] T028 Executar `python3 .specify/scripts/skill-lint.py --skill madruga/qa` — confirmar 0 erros; executar `make test` para verificar zero regressões em testes existentes

**Checkpoint**: qa.md com Phase 0 completa. L5/L6 nunca fazem skip silencioso para plataformas com testing: block. Startup automático e validação de URLs funcionais.

---

## Phase 5: User Story 5 — Journey Execution + Deployment Smoke Phase

**Goal**: qa.md executa jornadas declaradas em journeys.md. speckit.tasks gera automaticamente a fase de Deployment Smoke quando testing: block presente.

**Independent Test**: `python3 .specify/scripts/skill-lint.py --skill madruga/qa` e `python3 .specify/scripts/skill-lint.py --skill speckit.tasks` verdes após edições.

- [ ] T029 [US5] Editar `.claude/commands/madruga/qa.md` — adicionar `### Phase L5.5: Journey Testing` após validação de URLs (L5): (1) se `testing.journeys_file` declarado e arquivo existe, parsear journeys via formato YAML fenced per contracts/journeys_schema.md; (2) steps `type: api` → executar via Bash curl com assertions de status e body; (3) steps `type: browser` → executar via Playwright MCP (browser_navigate, browser_snapshot, browser_click, browser_fill_form); (4) step com `screenshot: true` → capturar screenshot obrigatório; (5) journey `required: true` + FAIL → BLOCKER: `❌ J-001 FAIL step N — <descrição da falha>`; (6) journey `required: false` + FAIL → WARN; (7) Playwright indisponível → marcar browser steps como SKIP e continuar API steps; (8) report por journey: `✅ J-001 PASS (N steps, Xs)` ou `❌ J-001 FAIL step N`
- [ ] T030 [US5] Editar `.claude/commands/speckit.tasks.md` — adicionar detecção de `testing:` block na geração de tasks.md: após determinar número da última fase (Phase N), executar `python3 $REPO_ROOT/.specify/scripts/qa_startup.py --platform $PLATFORM --parse-config --json 2>/dev/null`; se testing: presente (exit 0), adicionar `## Phase {N+1}: Deployment Smoke` como ÚLTIMA fase com tarefas: T{N+1}01 startup+health checks, T{N+1}02 validate-env (zero required vars ausentes), T{N+1}03 validate-urls (todas URLs acessíveis), T{N+1}04 screenshot de cada URL type:frontend, T{N+1}05 Journey J-001 happy path com assertions; adaptar ao startup.type (docker adiciona `docker compose build` antes de start; npm adiciona `npm run build`)
- [ ] T031 Executar `python3 .specify/scripts/skill-lint.py --skill madruga/qa` e `python3 .specify/scripts/skill-lint.py --skill speckit.tasks` — confirmar ambos verdes; executar `make test` para verificar zero regressões

**Checkpoint**: qa.md executa jornadas. speckit.tasks auto-gera Deployment Smoke Phase para plataformas com testing: block.

---

## Phase 6: User Stories 6+7 — URL Coverage + Blueprint Scaffold

**Goal**: speckit.analyze detecta rotas novas sem cobertura de QA pós-implementação (US-06). madruga:blueprint gera scaffold de testing: para novas plataformas (US-07). Estas duas mudanças são independentes entre si.

**Independent Test**: `python3 .specify/scripts/skill-lint.py` (todos os skills) verde após edições.

- [ ] T032 [P] [US6] Editar `.claude/commands/speckit.analyze.md` — adicionar **URL Coverage Check** na seção pós-implement: (1) se testing: block ausente → skip silencioso sem erro; (2) para Python/FastAPI: extrair decorators `@router.get/post/put/delete/patch` do diff; (3) para Next.js App Router: extrair arquivos novos `app/*/page.tsx|ts` (rotas UI) e `app/*/route.ts|js` (rotas API); (4) para Next.js Pages Router: extrair arquivos novos em `pages/`; (5) para frameworks não reconhecidos: WARN "Framework não reconhecido: URL coverage check disponível apenas para FastAPI e Next.js/React. Verificar cobertura manualmente" — NUNCA skip silencioso (FR-017); (6) comparar rotas detectadas com `testing.urls` em platform.yaml; rotas sem correspondência → HIGH finding: "Rota nova não declarada em platform.yaml testing.urls — adicionar para cobertura de QA"
- [ ] T033 [P] [US7] Editar `.claude/commands/madruga/blueprint.md` — adicionar **Testing Scaffold** ao gerar artefatos da plataforma: (1) incluir bloco `testing:` skeleton em platform.yaml gerado com startup.type inferido da stack (Python→script, Docker→docker, Node/npm→npm, indefinido→none), health_checks:[], urls:[], required_env:[], env_file: null, journeys_file: testing/journeys.md; (2) criar `platforms/<name>/testing/journeys.md` com template J-001 placeholder estruturado com steps vazios comentados baseados na US principal declarada; (3) para plataformas com `repo:` binding: gerar `.github/workflows/ci.yml` com jobs: lint, test, build — Docker build no job build se startup.type=docker (com flag opcional para CI lento)
- [ ] T034 Executar `python3 .specify/scripts/skill-lint.py` (todos os skills sem flag --skill) — confirmar 0 erros para qa.md, speckit.tasks.md, speckit.analyze.md, madruga/blueprint.md e todos os outros skills não modificados

**Checkpoint**: speckit.analyze detecta cobertura faltante. blueprint gera scaffold de testing: para novas plataformas. Skill lint verde para todos.

---

## Phase 7: Smoke Validation

**Purpose**: Validar de ponta a ponta que a infraestrutura criada neste epic funciona corretamente. Confirmar que critérios de sucesso SC-001 a SC-007 são atendíveis.

- [ ] T035 Executar `python3 .specify/scripts/qa_startup.py --platform madruga-ai --cwd . --validate-env --json` — confirmar: exit code 0, `status: "ok"`, `env_missing: []`, `env_present: []` (madruga-ai não tem required_env, resultado esperado OK vazio)
- [ ] T036 Executar `python3 .specify/scripts/qa_startup.py --platform prosauai --cwd . --parse-config --json` — confirmar: exit code 0, manifest contém `startup.type: docker`, `required_env` com exatamente 4 variáveis [JWT_SECRET, ADMIN_BOOTSTRAP_EMAIL, ADMIN_BOOTSTRAP_PASSWORD, DATABASE_URL]
- [ ] T037 Executar `python3 .specify/scripts/skill-lint.py` — confirmar exit code 0 e zero erros para todos os skills modificados: `madruga/qa.md`, `speckit.tasks.md`, `speckit.analyze.md`, `madruga/blueprint.md`
- [ ] T038 Executar `python3 .specify/scripts/platform_cli.py lint --all` — confirmar que o bloco `testing:` de madruga-ai e prosauai valida sem erros; confirmar que plataformas existentes sem `testing:` block (todas as demais) também passam sem alteração (SC-007)
- [ ] T039 Executar `make test` — confirmar 0 failures; confirmar que `test_qa_startup.py` está na suite e todos os testes passam; confirmar que testes existentes (test_platform.py, etc.) continuam verdes após mudanças desta phase

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Foundational: qa_startup.py)
  ↓ BLOCKS Phases 3–5 (skill edits que referenciam qa_startup.py)
Phase 2 (US-01: platform.yaml)
  ↓ BLOCKS Phase 4 (Phase 0 do qa.md lê testing: block)
Phase 3 (US-02+03 Wave 1)
  ↓ BLOCKS Phase 4 (Wave 2 adiciona ao qa.md que Wave 1 modificou)
Phase 4 (US-02+03+04 Wave 2)
Phase 5 (US-05: journeys + speckit.tasks)
Phase 6 (US-06+07: analyze + blueprint)  ← paralelo com Phase 5
Phase 7 (Smoke)
  ↑ Depende de todas as phases anteriores
```

### User Story Dependencies

- **US-01 (P1)**: Independente após Phase 1 — declara configuração sem runtime
- **US-02 (P1)**: Depende de Phase 1 (qa_startup.py `--start`) — startup automático no qa.md
- **US-03 (P1)**: Depende de Phase 1 (qa_startup.py `--validate-env`) — env diff no qa.md
- **US-04 (P2)**: Depende de Phase 1 (qa_startup.py `--validate-urls`) e US-02 (serviços sobem primeiro)
- **US-05 (P2)**: Depende de US-01 (journeys.md declarado) e US-02 (serviços rodando para steps API)
- **US-06 (P3)**: Depende de US-01 (testing.urls existe para comparação) — independente das outras
- **US-07 (P3)**: Independente — apenas edita blueprint.md

### Parallel Opportunities by Phase

| Phase | Paralelas internas |
|-------|--------------------|
| Phase 1 | T002 [P], T003 [P], T004 [P], T005 [P] após skeleton T001 |
| Phase 2 | T015 [P] e T016 [P] entre si; T013 e T014 paralelos |
| Phase 3 | T021, T022, T023 são edições no mesmo arquivo — rodar sequencialmente |
| Phase 4 | T025, T026, T027 são edições no mesmo arquivo — rodar sequencialmente |
| Phase 5 | T029 e T030 em arquivos diferentes — paralelos |
| Phase 6 | T032 [P] e T033 [P] em arquivos diferentes — paralelos |
| Phase 7 | T035–T039 são comandos de validação — rodar sequencialmente |

### Guardrails Críticos (auto-sabotagem)

| Regra | Verificação |
|-------|-------------|
| Phase 1 ANTES de Phases 3–5 | qa_startup.py deve existir antes de qualquer skill edit que o referencia |
| `skill-lint.py --skill <name>` após cada skill edit | Se lint falhar, reverter o edit antes de avançar |
| `make test` verde entre phases críticas | Após Phase 1 (testes novos), após Phase 5 (testes regressão) |
| Todas as mudanças aditivas sem testing: block | Plataformas existentes sem o bloco mantêm comportamento atual |
| `qa_startup.py` nunca executa comandos destrutivos | Invariante ADR: docker compose down jamais chamado |

---

## Implementation Strategy

**MVP Scope** (P1 — mínimo para fechar o buraco principal):
- Phase 1 (qa_startup.py) + Phase 2 (testing: blocks + journeys.md) + Phase 3 (QA Wave 1: env diff + BLOCKER vs SKIP)

Com apenas MVP: os 3 bugs de env vars ausentes (JWT_SECRET, etc.) são detectados via BLOCKER, e L5 não faz mais skip silencioso. 4 dos 7 bugs escapados seriam bloqueados.

**Full Scope** (Phases 1–7): Todos os 7 bugs detectados (SC-001 100%). Journey J-001 captura login broken e root placeholder. URL reachability captura IP errado e timeout.

**Sugestão de entrega incremental**:
1. Phases 1+2+3 → env diff + BLOCKER policy (impacto imediato sem risco)
2. Phase 4 → startup automático (maior valor, requer qa_startup.py completo)
3. Phases 5+6 → journey execution + future-proofing
4. Phase 7 → smoke validation final

---

## Summary

| Phase | Tasks | User Story | Arquivos Principais |
|-------|-------|------------|---------------------|
| Phase 1: Foundational | T001–T012 | Infrastructure | `.specify/scripts/qa_startup.py` + `test_qa_startup.py` |
| Phase 2: US-01 | T013–T020 | P1 | `platform.yaml` × 2, `journeys.md` × 2, `platform_cli.py`, `platform.yaml.jinja` |
| Phase 3: US-02+03 Wave 1 | T021–T024 | P1 | `.claude/commands/madruga/qa.md` |
| Phase 4: US-02+03+04 Wave 2 | T025–T028 | P1+P2 | `.claude/commands/madruga/qa.md` |
| Phase 5: US-05 | T029–T031 | P2 | `qa.md` + `.claude/commands/speckit.tasks.md` |
| Phase 6: US-06+07 | T032–T034 | P3 | `.claude/commands/speckit.analyze.md` + `.claude/commands/madruga/blueprint.md` |
| Phase 7: Smoke | T035–T039 | — | Validação CLI |
| **Total** | **39 tasks** | **7 USs** | **11 arquivos criados/modificados** |

**Parallel opportunities**: 7 tasks marcadas [P] — maior paralelismo em Phase 1 (skeleton → funções independentes) e Phase 6 (analyze [P] + blueprint [P]).

---
handoff:
  from: speckit.tasks
  to: speckit.analyze
  context: "39 tarefas em 7 fases ordenadas por dependência. Phase 1 (qa_startup.py) é bloqueante para Phases 3-5. Phase 2 (platform.yaml + lint + journeys.md) é bloqueante para Phase 4. Fases 5+6 podem rodar em paralelo após 4. Guardrail crítico: skill-lint.py após cada edição em .claude/commands/**. 11 arquivos serão criados/modificados; qa_startup.py (~300 LOC) + test_qa_startup.py (~250 LOC) são os artefatos Python mais pesados. MVP funcional com Phases 1+2+3 — fecha 4/7 bugs do Epic 007."
  blockers: []
  confidence: Alta
  kill_criteria: "Se _lint_testing_block() exigir refatoração breaking de platform_cli.py que quebre testes existentes em test_platform.py, ou se qa_startup.py descobrir que REPO_ROOT não está disponível como env var em contextos de CI externo (fallback: Path(__file__).parents[2])."
