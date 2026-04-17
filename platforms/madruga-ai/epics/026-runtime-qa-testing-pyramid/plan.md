# Plano de Implementação: Runtime QA & Testing Pyramid

**Branch**: `epic/madruga-ai/026-runtime-qa-testing-pyramid`  
**Data**: 2026-04-16  
**Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `platforms/madruga-ai/epics/026-runtime-qa-testing-pyramid/spec.md`

---

## Sumário

O pipeline madruga passa a **conhecer como iniciar cada plataforma, quais URLs devem existir, e quais jornadas de usuário devem funcionar** — declarados em `platform.yaml` (bloco `testing:`) e `journeys.md`. Um novo script Python (`qa_startup.py`) implementa a infraestrutura de runtime: startup de serviços, health checks, validação de env vars e reachability de URLs. As camadas L4/L5 do skill `qa.md` são atualizadas para emitir BLOCKER em vez de SKIP silencioso. `speckit.analyze` passa a detectar rotas novas sem cobertura. `blueprint` gera scaffold de testes para novas plataformas.

**Causa raiz resolvida**: 7 bugs de deployment escaparam do Epic 007 (prosauai) porque L5/L6 faziam skip silencioso. Nenhuma camada de runtime rodou de fato. Este epic fecha o buraco sem tocar `easter.py` nem `dag_executor.py`.

---

## Technical Context

**Language/Version**: Python 3.11+ (qa_startup.py, test_qa_startup.py, platform_cli.py extension); Markdown + YAML (skill files, journeys.md, platform.yaml extension)  
**Primary Dependencies**: stdlib (`subprocess`, `pathlib`, `urllib.request`, `urllib.error`, `json`, `argparse`, `time`, `re`, `os`) + `pyyaml` (já presente em todo o projeto) — zero novas dependências externas  
**Storage**: `platform.yaml` (YAML — extended schema); `journeys.md` (Markdown + YAML fenced blocks); `.env` / `.env.example` (leitura de keys apenas); nenhuma tabela nova no SQLite  
**Testing**: `pytest` + `unittest.mock` — `test_qa_startup.py` usa mocks de `subprocess.run`, `urllib.request.urlopen` e `Path.read_text`; nenhum serviço real necessário para `make test`  
**Target Platform**: Linux (onde o pipeline madruga.ai executa); portável para macOS (dev local)  
**Project Type**: Internal tooling — script CLI (`qa_startup.py`) + edições em skill markdown files + extensão de schema YAML  
**Performance Goals**: `qa_startup.py --start` completa em `ready_timeout` (60–120s configurável); health check polling a cada 2s; `--validate-urls` completa em < 30s para ≤ 20 URLs  
**Constraints**: ADR-004 (stdlib + pyyaml only — zero deps externas); ADR-021 (skill edits via Edit/Write direto em bare-lite dispatch); skills editados passam no `skill-lint.py` após cada edição  
**Scale/Scope**: 2 plataformas neste epic (madruga-ai, prosauai); extensível a qualquer plataforma futura via bloco `testing:` opcional

---

## Constitution Check

*GATE: Deve passar antes do Phase 0 research. Re-verificado após Phase 1 design.*

| Princípio | Check | Status |
|-----------|-------|--------|
| **I. Pragmatismo** | Solução mais simples que resolve os 7 bugs (stdlib only, bloco opcional no yaml existente) | ✅ PASS |
| **II. Automatizar repetitivo** | A detecção de startup, env diff e health checks são tarefas manuais hoje — automatizadas por este epic | ✅ PASS |
| **IV. Ação rápida + TDD** | `test_qa_startup.py` escrito junto com `qa_startup.py` (TDD); mudanças são aditivas (sem breaking changes) | ✅ PASS |
| **V. Alternativas** | Todas as decisões documentadas em `research.md` com alternativas rejeitadas | ✅ PASS |
| **VII. TDD** | `qa_startup.py` tem suite de testes completa antes de qualquer skill edit que o referencia | ✅ PASS |
| **IX. Observability** | JSON output estruturado em todos os modos de operação; stderr para progress logs | ✅ PASS |

**Violações**: Nenhuma. O bloco `testing:` é puramente aditivo — plataformas sem ele mantêm comportamento atual.

**Re-check pós-Phase 1**: Após design dos contratos, nenhuma violação detectada. `qa_startup.py` permanece stdlib + pyyaml; sem abstrações desnecessárias.

---

## Estrutura do Projeto

### Documentação (este epic)

```text
platforms/madruga-ai/epics/026-runtime-qa-testing-pyramid/
├── plan.md              # Este arquivo
├── research.md          # Decisões de implementação (Phase 0)
├── data-model.md        # Entidades: TestingManifest, Journey, StartupResult
├── contracts/
│   ├── qa_startup_cli.md    # CLI interface + JSON output schema
│   └── journeys_schema.md   # journeys.md format + parsing rules
└── tasks.md             # Gerado pelo speckit.tasks (próxima etapa)
```

### Arquivos Criados/Modificados no Repo

```text
# NOVO — infraestrutura Python
.specify/scripts/qa_startup.py               # script CLI (Phase 1)
.specify/scripts/tests/test_qa_startup.py    # testes do qa_startup.py (Phase 1)

# MODIFICADO — platform.yaml (testing: block adicionado)
platforms/madruga-ai/platform.yaml           # testing: npm/portal (Phase 2)
platforms/prosauai/platform.yaml             # testing: docker/serviços (Phase 2)

# NOVO — journeys de teste por plataforma
platforms/madruga-ai/testing/journeys.md     # J-001: portal, J-002: CLI (Phase 2)
platforms/prosauai/testing/journeys.md       # J-001: login, J-002: webhook, J-003: cookie (Phase 2)

# MODIFICADO — skill files (edição via Edit/Write direto — ADR-021)
.claude/commands/madruga/qa.md               # Phase 3 (GAP-06, BLOCKER vs SKIP) + Phase 4 (startup + manifest)
.claude/commands/speckit.tasks.md            # Phase 5 (Deployment Smoke phase)
.claude/commands/madruga/qa.md              # Phase 5 (Journey Execution)
.claude/commands/speckit.analyze.md          # Phase 6 (URL coverage check)
.claude/commands/madruga/blueprint.md        # Phase 6 (scaffold testing: + journeys.md)

# MODIFICADO — template Copier
.specify/templates/platform/template/platform.yaml.jinja  # testing: skeleton (Phase 2)

# MODIFICADO — platform_cli.py lint
.specify/scripts/platform_cli.py             # _lint_testing_block() (Phase 2)
```

**Decisão de estrutura**: Arquivos separados por responsabilidade. `qa_startup.py` é um script standalone (não importa outros módulos madruga.ai além de pyyaml) para funcionar em CWD externo sem problemas de PYTHONPATH.

---

## Complexity Tracking

Nenhuma violação de Constituição. A seção abaixo documenta apenas as escolhas não-óbvias:

| Escolha | Por que necessária | Alternativa mais simples rejeitada porque |
|---------|-------------------|------------------------------------------|
| Bloco `testing:` em `platform.yaml` | Centraliza config; reutiliza parser YAML existente | Arquivo `testing/manifest.yaml` separado criaria mais proliferação de arquivos e um novo parser |
| YAML fenced blocks em `journeys.md` | Machine-readable + human-readable no mesmo arquivo | `journeys.yaml` separado: documentação menos legível; `journeys.md` em prosa: não parseável |
| `qa_startup.py` standalone (sem imports do madruga.ai) | Funciona com qualquer PYTHONPATH em CI externo | Importar `config.py` forçaria configurar PYTHONPATH para cada plataforma externa |

---

## Fases de Implementação

A ordem das fases é **inviolável por dependência**:
- Phase 1 (qa_startup.py + testes) DEVE preceder qualquer skill edit que o referencie (Phase 3+)
- Phase 2 (platform.yaml) DEVE preceder Phase 4 (que lê o testing: block)
- Phase 6 (analyze + blueprint) pode rodar em paralelo com Phase 5

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
    (infraestrutura)   (config)   (QA Wave 1) (QA Wave 2) (journeys+tasks) (analyze+blueprint) (smoke)
```

---

### Phase 1 — qa_startup.py + Testes (Python Infrastructure)

**Arquivos**: `.specify/scripts/qa_startup.py` + `.specify/scripts/tests/test_qa_startup.py`  
**LOC estimado**: ~300 LOC (script) + ~250 LOC (testes) = ~550 LOC total  
**Gate**: `make test` verde após esta phase

**Módulos internos de qa_startup.py**:

| Função | Responsabilidade |
|--------|-----------------|
| `load_manifest(platform, repo_root)` | Parseia `testing:` block do platform.yaml; retorna `TestingManifest | None` |
| `parse_journeys(content)` | Extrai blocos YAML de journeys.md; retorna `list[dict]` |
| `_read_env_keys(env_path)` | Lê apenas keys do .env (nunca valores) |
| `validate_env(manifest, cwd)` | Compara `required_env` vs .env real; gera findings |
| `quick_check(health_checks, timeout=3)` | Health check rápido (pré-startup) |
| `execute_startup(manifest, cwd)` | Executa comando de startup por tipo |
| `wait_for_health(health_checks, timeout)` | Polling até todos health checks passarem ou timeout |
| `start_services(manifest, cwd)` | Orquestra quick_check → execute_startup → wait_for_health |
| `validate_urls(manifest, cwd)` | Valida reachability e conteúdo de todas URLs |
| `_is_placeholder(body, content_type, url_type)` | Detecta placeholder HTML (4 critérios OR) |
| `run_full(manifest, cwd)` | Sequencia: start → validate_env → validate_urls |
| `main()` | Argparse + dispatch para operação correta |

**Cobertura de testes**:
- `test_load_manifest_*`: parsing de bloco válido, ausente, incompleto, tipo inválido
- `test_parse_journeys_*`: parsing de blocos YAML válidos, malformados, não-journey
- `test_read_env_keys_*`: .env presente, ausente, com comentários, com valores complexos
- `test_validate_env_*`: required presentes, required ausentes, optional ausentes
- `test_quick_check_*`: mock urlopen → 200, timeout, connection error
- `test_wait_for_health_*`: mock de loop de polling (todos ok, timeout, parcial)
- `test_execute_startup_*`: mock subprocess.run por tipo (docker, npm, make, none)
- `test_validate_urls_*`: 200 ok, 404 blocker, redirect check, placeholder WARN, connection refused
- `test_is_placeholder_*`: todos os 4 critérios individualmente
- `test_main_*`: integração CLI com argparse mock

---

### Phase 2 — Platform YAML: testing: block + lint + journeys.md

**Arquivos**:
- `platforms/madruga-ai/platform.yaml` — bloco `testing:` (startup type: npm)
- `platforms/prosauai/platform.yaml` — bloco `testing:` (startup type: docker)
- `platforms/madruga-ai/testing/journeys.md` — J-001, J-002
- `platforms/prosauai/testing/journeys.md` — J-001, J-002, J-003
- `.specify/templates/platform/template/platform.yaml.jinja` — skeleton opcional
- `.specify/scripts/platform_cli.py` — `_lint_testing_block()` + chamada em `_lint_platform()`
- `.specify/scripts/tests/test_platform.py` — testes do lint do testing: block

**Conteúdo de `platform.yaml` para madruga-ai**:
```yaml
testing:
  startup:
    type: npm
    command: "cd portal && npm run dev"
    ready_timeout: 30
  health_checks:
    - url: http://localhost:4321
      method: GET
      expect_status: 200
      label: Portal Dev Server
  urls:
    - url: http://localhost:4321
      type: frontend
      label: Portal Home
      expect_status: 200
    - url: http://localhost:4321/platforms/madruga-ai
      type: frontend
      label: Plataforma madruga-ai
      expect_status: 200
  required_env: []
  env_file: null
  journeys_file: testing/journeys.md
```

**Conteúdo de `platform.yaml` para prosauai**:
```yaml
testing:
  startup:
    type: docker
    command: null
    ready_timeout: 120
  health_checks:
    - url: http://localhost:8050/health
      method: GET
      expect_status: 200
      expect_body_contains: '"status"'
      label: API Backend
    - url: http://localhost:3000
      method: GET
      expect_status: 200
      label: Admin Frontend
  urls:
    - url: http://localhost:8050/health
      type: api
      label: Health Check
      expect_status: 200
    - url: http://localhost:8050/api/auth/login
      type: api
      label: Login endpoint
      expect_status: [200, 401]
    - url: http://localhost:3000
      type: frontend
      label: Root (deve redirecionar para /login)
      expect_redirect: /login
    - url: http://localhost:3000/login
      type: frontend
      label: Login page
      expect_contains: ["email", "password"]
  required_env:
    - JWT_SECRET
    - ADMIN_BOOTSTRAP_EMAIL
    - ADMIN_BOOTSTRAP_PASSWORD
    - DATABASE_URL
  env_file: .env.example
  journeys_file: testing/journeys.md
```

**Gate**: `python3 .specify/scripts/platform_cli.py lint --all` verde; `make test` verde (testes de lint do testing: block)

---

### Phase 3 — QA Skill Wave 1: Políticas Imediatas (non-breaking)

**Arquivo**: `.claude/commands/madruga/qa.md`  
**Tipo de mudança**: Aditiva — não quebra comportamento atual para plataformas sem `testing:` block

**Mudanças**:

1. **GAP-06 — Env diff** (nova subseção em Phase 0, antes de Environment Detection):
   ```markdown
   #### Env Diff (quando testing.env_file declarado)
   Se o bloco `testing:` existe e `testing.env_file` está declarado:
   ```bash
   python3 $REPO_ROOT/.specify/scripts/qa_startup.py \
     --platform $PLATFORM --cwd $(pwd) --validate-env --json
   ```
   - Variável em `required_env` ausente → BLOCKER imediato antes de qualquer runtime layer
   - Variável em `.env.example` mas não em `required_env` ausente → WARN
   ```

2. **GAP-01/03 — BLOCKER vs SKIP silencioso** (L5 check update):
   ```markdown
   Se `testing:` block existe e health checks falham ao tentar L5:
   - Antes: `⏭️ L5: No server running — skipping`
   - Depois: `❌ L5: BLOCKER — testing.urls declarado mas serviços inacessíveis.
     Execute: python3 $REPO_ROOT/.specify/scripts/qa_startup.py --start --platform $PLATFORM`
   ```

3. **GAP-10 — Screenshots obrigatórios** (em L6 quando Playwright disponível):
   ```markdown
   Para cada URL `type: frontend` em `testing.urls`: screenshot obrigatório.
   Validar: título não vazio, body não é placeholder HTML.
   ```

**Gate**: `python3 .specify/scripts/skill-lint.py --skill madruga/qa` verde

---

### Phase 4 — QA Skill Wave 2: Manifest Reading + Startup + Reachability

**Arquivo**: `.claude/commands/madruga/qa.md`  
**Tipo de mudança**: Novo **Phase 0: Testing Manifest** antes de Environment Detection

**Conteúdo do novo Phase 0**:

```markdown
### Phase 0: Testing Manifest

1. Detectar plataforma ativa:
   ```bash
   python3 $REPO_ROOT/.specify/scripts/platform_cli.py current
   ```

2. Ler testing: block:
   ```bash
   python3 $REPO_ROOT/.specify/scripts/qa_startup.py \
     --platform $PLATFORM --cwd $(pwd) --parse-config --json
   ```
   - `testing:` ausente: continuar para Environment Detection (comportamento atual)
   - `testing:` presente: usar como contexto autoritativo para L4/L5/L6

3. Iniciar serviços (se `startup.type != none`):
   ```bash
   python3 $REPO_ROOT/.specify/scripts/qa_startup.py \
     --platform $PLATFORM --cwd $(pwd) --start --json
   ```
   - health_check FAIL → BLOCKER com output de diagnóstico + logs
   - Serviços já rodando e saudáveis → OK, pular startup

4. Validar reachability de URLs:
   ```bash
   python3 $REPO_ROOT/.specify/scripts/qa_startup.py \
     --platform $PLATFORM --cwd $(pwd) --validate-urls --json
   ```
   - URL inacessível → BLOCKER com URL + sugestão por startup type
   - Placeholder detectado → WARN
```

**Gate**: `python3 .specify/scripts/skill-lint.py --skill madruga/qa` verde

---

### Phase 5 — Journey Execution + speckit.tasks Smoke Phase

**Arquivos**:
- `.claude/commands/madruga/qa.md` — novo **Phase L5.5: Journey Testing**
- `.claude/commands/speckit.tasks.md` — novo `## Phase N: Deployment Smoke` auto-gerado

**qa.md — Phase L5.5: Journey Testing**:

```markdown
### Phase L5.5: Journey Testing (quando journeys.md declarado)

Se `testing.journeys_file` está declarado e o arquivo existe:

Para cada journey em `journeys.md`:
1. Steps `type: api` → executar via Bash/curl com assertions de status e body
2. Steps `type: browser` → executar via Playwright MCP (navigate, snapshot, click, fill_form)
3. Screenshot obrigatório para steps marcados com `screenshot: true`
4. Journey `required: true` + FAIL → BLOCKER: `❌ J-001 FAIL step 3 — descrição da falha`
5. Journey `required: false` + FAIL → WARN
6. Steps de browser com Playwright indisponível → `SKIP — Playwright não disponível` (continua)
7. Report: `✅ J-001 PASS (5 steps, 3.2s)` ou `❌ J-001 FAIL step 2 — dashboard mostra KPIs vazios`
```

**speckit.tasks.md — Deployment Smoke Phase detection**:

```markdown
#### Deployment Smoke Phase (auto-gerada se testing: block presente)

Ao gerar tasks.md, detectar bloco `testing:` em platform.yaml:
```bash
python3 $REPO_ROOT/.specify/scripts/qa_startup.py \
  --platform $PLATFORM --parse-config --json 2>/dev/null
```

Se o bloco existe, adicionar como última fase do tasks.md:
```markdown
## Phase N: Deployment Smoke

- [ ] T{N}01: `qa_startup.py --start --platform <name>` — todos health_checks respondem
- [ ] T{N}02: `qa_startup.py --validate-env --platform <name>` — zero required vars ausentes
- [ ] T{N}03: `qa_startup.py --validate-urls --platform <name>` — todas URLs acessíveis
- [ ] T{N}04: Screenshot de cada URL `type: frontend` capturado e validado
- [ ] T{N}05: Journey J-001 (happy path) executado — todos steps com assertions
```
Adaptado ao startup.type: docker adiciona `docker compose build` antes de start.
```

**Gate**: `python3 .specify/scripts/skill-lint.py --skill madruga/qa` verde; `python3 .specify/scripts/skill-lint.py --skill speckit.tasks` verde

---

### Phase 6 — speckit.analyze URL Coverage + blueprint Scaffold

**Arquivos**:
- `.claude/commands/speckit.analyze.md` — URL coverage check pós-implement
- `.claude/commands/madruga/blueprint.md` — scaffold de testing: + journeys.md

**speckit.analyze.md — URL Coverage Check**:

```markdown
#### URL Coverage Check (pós-implement, quando testing: block presente)

Para Python/FastAPI: extrair decorators `@router.get/post/put/delete/patch` do diff
Para Next.js App Router: extrair arquivos novos em `app/*/page.tsx|ts` (UI) e `app/*/route.ts|js` (API)
Para Next.js Pages Router: extrair arquivos novos em `pages/`
Para outros frameworks: emitir WARN: "Framework não reconhecido: verificar cobertura manualmente"

Comparar rotas detectadas com `testing.urls` em platform.yaml.
Rotas sem correspondência → HIGH finding:
"Rota nova não declarada em platform.yaml testing.urls — adicionar para cobertura de QA"

Se `testing:` block ausente → skip silencioso, sem error.
```

**blueprint.md — Testing Scaffold**:

```markdown
#### Testing Scaffold (ao gerar platform.yaml + artefatos)

1. Incluir `testing:` skeleton em platform.yaml gerado:
   - `startup.type` inferido da stack: Python=script/venv, Docker=docker, Node=npm
   - `health_checks: []`, `urls: []` (preenchidos pelo mantenedor)

2. Criar `platforms/<name>/testing/journeys.md`:
   - Template com J-001 placeholder baseado na principal US declarada

3. Para plataformas com `repo:` binding:
   - Gerar `.github/workflows/ci.yml` com jobs: lint, test, build
   - Docker build no job build se startup.type=docker (com flag opcional)
```

**Gate**: `python3 .specify/scripts/skill-lint.py` (all skills) verde

---

### Phase 7 — Smoke Validation

**Propósito**: Validar a infraestrutura criada neste epic de ponta a ponta.

```bash
# Script qa_startup.py funciona para madruga-ai (sem required_env)
python3 .specify/scripts/qa_startup.py \
  --platform madruga-ai --cwd . --validate-env --json
# Esperado: status ok, env_missing: [], env_present: []

# Script qa_startup.py lê testing: block de prosauai corretamente
python3 .specify/scripts/qa_startup.py \
  --platform prosauai --cwd . --parse-config --json
# Esperado: TestingManifest com startup.type=docker, 4 required_env vars

# Skill lint verde para todos os skills modificados
python3 .specify/scripts/skill-lint.py
# Esperado: zero erros

# Platform lint verde para todas as plataformas
python3 .specify/scripts/platform_cli.py lint --all
# Esperado: platform.yaml de madruga-ai e prosauai validam testing: block sem erros

# Testes verdes (incluindo test_qa_startup.py)
make test
# Esperado: 0 failures, test_qa_startup.py na suite
```

---

## Guardrails de Auto-Sabotagem

| Regra | Razão |
|-------|-------|
| Phase 1 antes das Phases 3–5 | qa_startup.py deve existir e ter testes ANTES de skills o referenciarem |
| `skill-lint.py --skill <name>` após cada skill edit | Skills inválidos quebram o pipeline |
| `make test` verde entre phases críticas | Phase 1 cria novos testes; garantir que passam |
| Todas as mudanças são aditivas se `testing:` block ausente | Retrocompatibilidade total — zero breaking changes |
| Nunca tocar `easter.py` nem `dag_executor.py` | Risco de auto-sabotagem mínimo |

---

## Mapeamento FR → Phase

| FRs | Phase | Arquivo principal |
|-----|-------|-------------------|
| FR-001, FR-004 | Phase 2 | platform.yaml |
| FR-002 | Phase 2 | platform_cli.py |
| FR-003 | Phase 2 | platform.yaml.jinja |
| FR-005, FR-006, FR-007, FR-008 | Phase 1 | qa_startup.py |
| FR-009, FR-010 | Phase 3 | qa.md (env diff) |
| FR-011, FR-012 | Phase 4 | qa.md (startup) |
| FR-013, FR-014, FR-023 | Phase 4 | qa.md (URLs) + qa_startup.py |
| FR-015, FR-021 | Phase 5 | qa.md (journeys) |
| FR-016, FR-017 | Phase 6 | speckit.analyze.md |
| FR-018, FR-019 | Phase 6 | blueprint.md |
| FR-020 | Phase 5 | speckit.tasks.md |
| FR-022 | Phase 1 | qa_startup.py (keys-only) |

---

## Critérios de Sucesso Verificáveis

| SC | Verificação no Smoke (Phase 7) |
|----|-------------------------------|
| SC-001 (7/7 bugs detectados) | `--validate-env` detecta vars ausentes; `--start` detecta Dockerfile errors; `--validate-urls` detecta URLs com IP errado |
| SC-002 (zero skips silenciosos) | qa.md emite BLOCKER quando testing: presente e serviços inacessíveis |
| SC-003 (diagnóstico suficiente) | BLOCKER inclui health check que falhou + logs + sugestão |
| SC-004 (novas plataformas com testing) | blueprint gera testing: skeleton automaticamente |
| SC-005 (make test verde) | Phase 7 executa `make test` |
| SC-006 (skill-lint verde) | Phase 7 executa `python3 .specify/scripts/skill-lint.py` |
| SC-007 (retrocompat) | Plataformas sem testing: não são afetadas (lint passa; qa.md comportamento atual preservado) |

---

---
handoff:
  from: speckit.plan
  to: speckit.tasks
  context: "Plano completo em 7 fases ordenadas por dependência (Phase 1: qa_startup.py + testes → Phase 2: platform.yaml + lint + journeys.md → Phases 3-4: qa.md em waves → Phase 5: journeys + tasks smoke phase → Phase 6: analyze + blueprint → Phase 7: smoke validation). Contratos definidos em contracts/qa_startup_cli.md e contracts/journeys_schema.md. Data model em data-model.md. 23 FRs mapeados para phases. Guardrails críticos: Phase 1 antes de qualquer skill edit; skill-lint após cada edit; make test entre phases críticas."
  blockers: []
  confidence: Alta
  kill_criteria: "Se qa_startup.py precisar de dependências além de stdlib + pyyaml para suportar os tipos de startup declarados, ou se a extensão de _lint_platform() para o bloco testing: exigir uma refatoração breaking do platform_cli.py que afete plataformas existentes."
