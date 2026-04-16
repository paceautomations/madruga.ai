---
title: "026 — Runtime QA & Testing Pyramid"
epic_id: 026-runtime-qa-testing-pyramid
platform: madruga-ai
status: drafted
created: 2026-04-16
updated: 2026-04-16
---
# Epic 026 — Runtime QA & Testing Pyramid

> 7 bugs básicos de runtime escaparam do Epic 007 (prosauai — Admin Dashboard) apesar de Judge 85%
> e QA "healed 10 findings". Nenhum era obscuro. Este epic fecha o buraco: o pipeline passa a
> detectar e bloquear erros de deployment antes da entrega, para qualquer plataforma.

## Problema

O pipeline madruga executa 6 camadas de QA, mas apenas 3 delas rodam de forma confiável:

| Camada | Status atual | Problema |
|--------|-------------|---------|
| L1 Static Analysis | ✅ sempre roda | — |
| L2 Automated Tests | ✅ quando testes existem | — |
| L3 Code Review | ✅ sempre roda | — |
| L4 Build Verification | ⚠️ parcial | só quando build scripts detectados |
| L5 API Testing | ❌ skip silencioso | serviços nunca sobem; BLOCKER nunca emitido |
| L6 Browser Testing | ❌ skip silencioso | mesma causa raiz que L5 |

**Causa raiz**: o pipeline não conhece como iniciar os serviços de cada plataforma, não declara
quais URLs devem existir, e não tem jornadas de usuário para executar. L5/L6 "pulam"
silenciosamente — o relatório de QA diz "passed" quando na verdade não verificou nada de runtime.

**Bugs que escaparam (Epic 007)**:

| Bug | Camada que capturaria |
|-----|-----------------------|
| `COPY package.json` não existia no monorepo root | L4 (`docker compose build`) |
| `COPY .../public` diretório inexistente | L4 (`docker compose build`) |
| `localhost:3000` ERR_CONNECTION_TIMED_OUT | L5 (reachability check) |
| Dashboard KPIs vazios — API_URL no IP errado | L5 (URL validation) + env diff |
| Login não apareceu — cookie antigo inválido | Journey J-001 step 2 |
| Root `/` mostrava placeholder | Journey J-001 step 1 + screenshot |
| `JWT_SECRET`, `ADMIN_BOOTSTRAP_*` ausentes | env diff (GAP-06) |

**Todos os 7 bugs são de runtime e deployment — não de código.** As camadas estáticas
funcionaram corretamente. O buraco é que nenhuma camada de runtime rodou de fato.

## Apetite

2–3 semanas. Escopo fechado: os 12 gaps mapeados no MAKE_TEST_GREAT_AGAIN.md em 3 waves.
Sem mudanças no easter.py ou dag_executor.py — risco de auto-sabotagem mínimo.
Sem novas dependências externas — stdlib (urllib, subprocess, pathlib) + pyyaml (já presente).

## Dependências

- `platform.yaml` schema existente (extensível com bloco `testing:`)
- `platform_cli.py` (já parseia `platform.yaml`)
- Skill lint hook (`hook_skill_lint.py`) — valida edits em `.claude/commands/**` automaticamente
- Epic 024 — `isolation: branch` em prosauai (já shipped, sem blocker)

## Captured Decisions

| # | Área | Decisão | Referência Arquitetural |
|---|------|---------|------------------------|
| 1 | Testing config | Testing config declarada como bloco `testing:` em `platform.yaml` — não arquivo separado. Platform.yaml já é o manifesto da plataforma; centralizar evita proliferação de arquivos. | ADR-004 (stdlib, simplicidade) |
| 11 | Lifecycle testing: block | **Novas plataformas**: Copier template gera skeleton vazio → `blueprint` preenche baseado na stack → cada epic via `speckit.tasks` atualiza. **Plataformas existentes (retrofit)**: `speckit.tasks` detecta ausência de `testing:` block e gera `## Phase 1: Testing Foundation` com T001 (adicionar bloco) + T002 (criar journeys.md). **Manutenção contínua**: `reconcile` verifica journeys.md atualizado após cada epic. | pipeline-dag-knowledge.md L1/L2 |
| 2 | Skill file edits | Implement usa Edit/Write diretamente nos `.claude/commands/**`. Em bare-lite dispatch (`--disable-slash-commands`), `/madruga:skills-mgmt` não funciona. PostToolUse hook `hook_skill_lint.py` valida automaticamente após cada edit. `make lint-skills` após cada fase confirma integridade. | ADR-021 (bare-lite flags), CLAUDE.md skills-mgmt policy |
| 3 | Ativação do novo QA | Default-on quando `platform.yaml` contém bloco `testing:`. Sem feature flag. O bloco é o portão natural: plataformas sem ele mantêm comportamento atual. | ADR-004 (simplicidade, zero config) |
| 4 | qa_startup.py | Script Python dedicado (`.specify/scripts/qa_startup.py`) com interface CLI: `--start`, `--validate-env`, `--validate-urls`, `--json`. Recebe `--platform <name>` (para achar testing: no REPO_ROOT) e `--cwd <path>` (para executar comandos no repo da plataforma). | ADR-004 (stdlib + pyyaml only) |
| 5 | journeys.md por plataforma | `platforms/<name>/testing/journeys.md` — documento separado de `platform.yaml` por ser longo e textual. Referenciado via `testing.journeys_file` no `platform.yaml`. | ADR-004 (pragmatismo) |
| 6 | Plataformas neste epic | `testing:` block adicionado a `platforms/madruga-ai/platform.yaml`, `platforms/prosauai/platform.yaml`, e ao template Copier. `journeys.md` criados para ambas. Prosauai serve como validação end-to-end com serviços Docker reais. | Design: referência + validação real |
| 7 | BLOCKER vs SKIP | Quando `testing:` block existe e L5/L6 não conseguem rodar (serviços não sobem, health check falha): BLOCKER — não SKIP. Silêncio é mentira. | MAKE_TEST_GREAT_AGAIN.md GAP-01/03 |
| 8 | GitHub Actions (GAP-08) | `madruga:blueprint` gera `.github/workflows/ci.yml` para plataformas com `repo:` binding. Jobs: lint, tests, build. Docker build opcional (lento). | GAP-08 recommendation |
| 9 | Deployment Smoke Phase | `speckit.tasks` adiciona `## Phase N: Deployment Smoke` como última fase obrigatória, adaptada ao `startup.type` do manifest. | GAP-09 recommendation |
| 10 | URL Coverage check | `speckit.analyze` (post-implement) compara rotas no diff (FastAPI decorators, Next.js app/) contra `testing.urls` no `platform.yaml`. URLs não declaradas → HIGH finding. | GAP-12 recommendation |

## Resolved Gray Areas

**1. Como implement edita skill files em contexto bare-lite Easter?**
`speckit.implement` roda com `--disable-slash-commands` e `IMPLEMENT_TASK_TOOLS = "Bash,Read,Write,Edit,Glob,Grep"`. O `/madruga:skills-mgmt edit <skill>` é um slash command — não funciona neste contexto. A solução correta: tasks.md instrui implement a usar Edit/Write diretamente. O PostToolUse hook `hook_skill_lint.py` (configurado em CLAUDE.md) valida o resultado automaticamente. `python3 .specify/scripts/skill-lint.py --skill <name>` ao final de cada phase confirma. A policy skills-mgmt foi projetada para uso humano interativo.

**2. Por que `testing:` em `platform.yaml` e não `testing/manifest.yaml`?**
`platform.yaml` já é o manifesto declarativo da plataforma. Adicionar bloco `testing:` é uma extensão natural do schema existente. Evita criar um novo arquivo machine-readable, mantém tudo centralizado, e reutiliza o parser YAML já presente em `platform_cli.py`. `journeys.md` fica separado por ser documento longo e não machine-parseable.

**3. Como `qa_startup.py` acha os arquivos quando QA roda em plataforma externa?**
O QA skill é executado com `cwd=<external_repo>` (CODE_CWD_NODES no dag_executor). O `platform.yaml` de prosauai fica em `REPO_ROOT/platforms/prosauai/platform.yaml` (madruga.ai repo). `qa_startup.py` recebe `--platform prosauai` (para achar o `platform.yaml` via REPO_ROOT da config) e `--cwd /path/to/prosauai` (para executar `docker compose up -d` no repo correto). Padrão já usado em `implement_remote.py`.

**4. E o prosauai usa Tailscale para expor portas — como testar localmente?**
O `docker-compose.override.yml` do prosauai usa `${TAILSCALE_IP:-127.0.0.1}` como default para admin e `${TAILSCALE_IP}` para api (sem default). O bloco `testing:` de prosauai usa `localhost:8050` e `localhost:3000`. A validação deve verificar reachability e emitir mensagem clara se as portas não estão expostas (exemplo: "Configure `docker-compose.override.yml` com port binding para localhost").

**5. Lifecycle completo do `testing:` block — novas plataformas vs retrofit?**

**Novas plataformas** (L1 pipeline completo):
```
platform-new (Copier) → testing: skeleton vazio (type: none)
    ↓
blueprint (L1) → preenche testing: baseado na stack; cria testing/journeys.md com J-001 placeholder
    ↓
Cada epic L2 → speckit.tasks: gera tasks de update (novas URLs + journeys) + Smoke Phase
    ↓
reconcile → verifica journeys.md atualizado; propõe journeys para FRs sem cobertura
```

**Plataformas existentes (retrofit — prosauai no próximo epic após este):**
O `speckit.tasks` detecta ausência do `testing:` block e gera automaticamente `## Phase 1: Testing Foundation`:
- T001: Adicionar bloco `testing:` ao `platform.yaml` com startup.type, health_checks, URLs do epic
- T002: Criar `testing/journeys.md` com journeys para os FRs deste epic

Após esta fase, todas as fases seguintes já se beneficiam do novo QA.

**Resumo por skill responsável:**
| Skill | Responsabilidade |
|-------|-----------------|
| `platform-new` (Copier) | Skeleton `testing:` vazio (`type: none`) |
| `blueprint` (L1) | Preenche `testing:` + cria `journeys.md` template |
| `speckit.tasks` (L2) | Detecta ausência → Foundation Phase; ou atualiza URLs/journeys |
| `reconcile` (L2) | Verifica journeys.md; propõe journeys faltantes como patch |

**6. O epic não tem como auto-gerar Deployment Smoke Phase para si mesmo?**
`speckit.tasks` para ESTE epic roda ANTES de implementarmos a mudança em `speckit.tasks.md`. Portanto não haverá smoke phase auto-gerada. Solução: a `spec.md` incluirá explicitamente o requisito de fase de smoke, e o Suggested Approach aqui lista os tasks da Phase 7 que o tasks skill deve gerar a partir da spec.

**6. Epic self-referential risk?**
Diferente do Epic 024 (modificou `easter.py` + `dag_executor.py`), este epic NÃO toca o daemon nem o executor. Modifica apenas:
- Skill markdown files (lidos em invocação, não em boot do easter)
- Novo script Python additive (`qa_startup.py`)
- `platform.yaml` files (schema extension, não breaking)
- Template Copier

Risco de auto-sabotagem é mínimo. O QA deste epic (L2 node) vai usar o NOVO `qa.md` — que inclui o startup automático. Como `platforms/madruga-ai/platform.yaml` terá o `testing:` block neste ponto, o QA tentará iniciar o portal (`make portal-dev`) e validar. Isso é desejável — o epic valida sua própria infraestrutura.

## Applicable Constraints

- **ADR-004 (stdlib)**: `qa_startup.py` usa apenas `subprocess`, `pathlib`, `urllib.request` (stdlib) + `pyyaml` (já dependência). Zero novas libs.
- **ADR-021 (bare-lite)**: `--disable-slash-commands` em implement tasks. Skills editadas via Edit/Write direto (ver Decisão #2).
- **Skills-mgmt policy**: PostToolUse lint hook compensa. `python3 skill-lint.py --skill <name>` ao final de cada phase.
- **MADRUGA_PHASE_DISPATCH=1**: Tasks organizadas em fases com headers `## Phase N:` para dispatch agrupado. Máx 12 tasks/phase (`MADRUGA_PHASE_MAX_TASKS`).
- **Pipeline sequencial (ADR-006)**: Este epic bloqueia novos epics de madruga-ai durante execução.
- **SQLite WAL (ADR-004)**: Nenhuma migration nova — sem tabela nova, sem alteração de schema BD.

## Suggested Approach

O epic tem 7 fases ordenadas por dependência. Cada fase é independentemente válida após `make test` verde.

### Phase 1 — Python Infrastructure: qa_startup.py

Implementar o script que o QA skill vai invocar. Deve existir e ter testes ANTES de qualquer skill edit que o referencie.

**Arquivo**: `.specify/scripts/qa_startup.py`

Interface CLI:
```bash
# Valida env (diff .env.example vs .env real)
python3 qa_startup.py --platform prosauai --cwd /path/to/prosauai --validate-env --json

# Inicia serviços e aguarda health checks
python3 qa_startup.py --platform prosauai --cwd /path/to/prosauai --start --json

# Valida reachability de todas as URLs do testing.urls
python3 qa_startup.py --platform prosauai --cwd /path/to/prosauai --validate-urls --json

# Encadeia: start + validate-urls + validate-env
python3 qa_startup.py --platform prosauai --cwd /path/to/prosauai --full --json
```

Output JSON padrão (para consumo pelo QA skill):
```json
{
  "status": "ok|warn|blocker",
  "findings": [
    {"level": "BLOCKER|WARN|INFO", "message": "...", "detail": "..."}
  ],
  "health_checks": {"API": "ok", "Admin Frontend": "ok"},
  "env_missing": ["JWT_SECRET"],
  "env_present": ["DATABASE_URL"],
  "urls": [
    {"url": "http://localhost:8050/health", "status": 200, "ok": true},
    {"url": "http://localhost:3000", "status": 200, "ok": true}
  ]
}
```

Startup types e comandos padrão:
| Type | Comando padrão | Override |
|------|----------------|---------|
| `docker` | `docker compose up -d` | `testing.startup.command` |
| `venv` | detecta main app em `pyproject.toml` | `testing.startup.command` (obrigatório) |
| `npm` | `npm run dev` | `testing.startup.command` |
| `make` | `make run` | `testing.startup.command` |
| `script` | `testing.startup.command` (obrigatório) | — |
| `none` | nada | — |

**Arquivo de testes**: `.specify/scripts/tests/test_qa_startup.py`
- Testar parsing do bloco `testing:` (válido, ausente, incompleto)
- Testar `validate_env` com env vars presentes/ausentes
- Testar `wait_for_health` com mock de `urllib.request.urlopen`
- Testar `startup_service` com mock de `subprocess.run`
- Testar `validate_urls` com mock de requests

### Phase 2 — Platform YAML: testing: block

Adicionar o schema ao template Copier e às plataformas reais. Criar journeys.md de referência.

**Template Copier** (`.specify/templates/platform/template/platform.yaml.jinja`):
```yaml
{%- if testing_startup_type is defined %}
testing:
  startup:
    type: {{ testing_startup_type | default('none') }}
    command: null
    ready_timeout: 60
  health_checks: []
  urls: []
  required_env: []
  env_file: .env.example
  journeys_file: testing/journeys.md
{%- endif %}
```

**`platforms/madruga-ai/platform.yaml`** — bloco `testing:`:
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

**`platforms/prosauai/platform.yaml`** — bloco `testing:`:
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
      method: POST
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
    - url: http://localhost:3000/admin/dashboard
      type: frontend
      label: Dashboard (autenticado)
      requires_auth: true
  required_env:
    - JWT_SECRET
    - ADMIN_BOOTSTRAP_EMAIL
    - ADMIN_BOOTSTRAP_PASSWORD
    - DATABASE_URL
  env_file: .env.example
  journeys_file: testing/journeys.md
```

**Nota**: Portas de prosauai expostas via `docker-compose.override.yml`. Se `localhost:8050` não responder, `qa_startup.py` emite BLOCKER: "Configure port binding em docker-compose.override.yml — copiar de docker-compose.override.example.yml".

**`platforms/madruga-ai/testing/journeys.md`** — jornadas mínimas:
- J-001: Portal carrega e exibe plataformas
- J-002: Pipeline status visible via CLI

**`platforms/prosauai/testing/journeys.md`** — jornadas críticas:
- J-001: Admin Login Happy Path (root → /login → autenticar → dashboard com dados)
- J-002: Webhook ingest + tenant isolation (POST /webhook/{tenant_id})
- J-003: Cookie expirado → redirect para /login (não mostrar dashboard vazio)

### Phase 3 — QA Skill Wave 1: Políticas Imediatas

Mudanças não-disruptivas que valem independentemente do `testing:` block.

Editar `.claude/commands/madruga/qa.md`:

1. **GAP-06 — Env diff** (antes de qualquer layer, sempre que `env_file` declarado):
   ```
   python3 $REPO_ROOT/.specify/scripts/qa_startup.py \
     --platform $PLATFORM --cwd $(pwd) --validate-env --json
   ```
   - Vars em `required_env` ausentes → BLOCKER imediato
   - Vars opcionais ausentes → WARN (não bloqueia)

2. **GAP-01/03 parcial — BLOCKER vs SKIP silencioso**:
   Quando `testing:` block existe e L5 não consegue rodar:
   - Antes: `⏭️ L5: No server running — skipping`
   - Depois: `❌ L5: BLOCKER — testing.urls declarado mas serviços inacessíveis. Rode qa_startup.py --start --platform X`

3. **GAP-10 — Screenshots obrigatórios** quando Playwright disponível:
   Para cada URL `type: frontend` no `testing.urls`, screenshot obrigatório.
   Validações: título não vazio, sem overlay de erro, body não é placeholder HTML.

### Phase 4 — QA Skill Wave 2: Manifest Reading + Startup + Reachability

Mudanças que dependem do `testing:` block no `platform.yaml`.

Editar `.claude/commands/madruga/qa.md` — **Phase 0 (antes de Environment Detection)**:

```markdown
### Phase 0: Testing Manifest

1. Detectar plataforma ativa:
   ```bash
   python3 $REPO_ROOT/.specify/scripts/platform_cli.py current
   ```

2. Ler `platform.yaml` testing block:
   ```bash
   python3 $REPO_ROOT/.specify/scripts/qa_startup.py \
     --platform $PLATFORM --cwd $(pwd) --parse-config --json
   ```
   - Se `testing:` block ausente: continuar para Environment Detection (comportamento atual)
   - Se presente: usar como contexto autoritativo para layers L4/L5/L6

3. Iniciar serviços (se `startup.type != none`):
   ```bash
   python3 $REPO_ROOT/.specify/scripts/qa_startup.py \
     --platform $PLATFORM --cwd $(pwd) --start --json
   ```
   - Aguarda health_checks até `ready_timeout`
   - Health check FAIL → BLOCKER com output do erro de startup
   - Startup já rodando → OK, pular

4. Validar reachability de todas as URLs do manifest:
   ```bash
   python3 $REPO_ROOT/.specify/scripts/qa_startup.py \
     --platform $PLATFORM --cwd $(pwd) --validate-urls --json
   ```
   - URL inacessível (connection refused/timeout) → BLOCKER com URL + sugestão
   - Status code fora do esperado → BLOCKER
   - Body sem conteúdo esperado → WARN
```

### Phase 5 — QA Skill Wave 3: Journey Execution + speckit.tasks Smoke Phase

1. **Editar `qa.md`** — adicionar **Phase L5.5: Journey Testing** (após L5, antes de L6):

   Para cada journey em `testing/journeys.md`:
   - Steps de API: `urllib.request` (ou Bash curl) com assertions de status/body
   - Steps de browser: Playwright MCP (`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_fill_form`)
   - Screenshot obrigatório nos steps marcados com `screenshot: true`
   - Journey FAIL → BLOCKER se marcada como `required: true`
   - Report: `✅ J-001 PASS (5 steps)` ou `❌ J-001 FAIL step 3 — dashboard shows empty KPIs`

2. **Editar `speckit.tasks.md`** — adicionar **Deployment Smoke Phase** como última fase obrigatória:

   O tasks skill detecta o `testing:` block do `platform.yaml` e gera:
   ```markdown
   ## Phase N: Deployment Smoke

   ### Startup & Health
   - [ ] T{N}: `qa_startup.py --start --platform <name>` — todos health_checks respondem 200
   - [ ] T{N+1}: `qa_startup.py --validate-env --platform <name>` — zero vars required ausentes

   ### URL Coverage
   - [ ] T{N+2}: `qa_startup.py --validate-urls --platform <name>` — todas as URLs do manifest acessíveis
   - [ ] T{N+3}: Screenshot de cada URL `type: frontend` capturado (via Playwright ou curl + headers)

   ### Journeys
   - [ ] T{N+4}: Executar Journey J-001 (happy path) — steps completos com assertions
   ```
   Adaptado ao `startup.type`: docker usa `docker compose build` antes, npm usa `npm run build`, etc.

### Phase 6 — speckit.analyze + blueprint

1. **Editar `speckit.analyze.md`** — adicionar URL Coverage check (pós-implement):

   Para Python/FastAPI: extrai `@router.get/post/put/delete/patch` do diff.
   Para Next.js: extrai arquivos novos em `app/` ou `pages/` do diff.
   Compara com `testing.urls` em `platform.yaml`.
   URLs sem correspondência → HIGH finding: "Rota nova não declarada em platform.yaml testing.urls — adicionar para cobertura de QA".

2. **Editar `madruga/blueprint.md`** — adicionar scaffold de testing:

   - Ao gerar `platform.yaml` via blueprint: incluir `testing:` skeleton (startup.type baseado na stack escolhida)
   - Criar `platforms/<name>/testing/journeys.md` com template vazio mas estruturado (J-001 placeholder por US principal)
   - Para plataformas com `repo:` binding: gerar `.github/workflows/ci.yml` com jobs: lint, test, build

### Phase 7 — Smoke Validation

Fase final: validar que a infraestrutura criada neste epic funciona de ponta a ponta.

- `python3 .specify/scripts/qa_startup.py --platform madruga-ai --cwd . --validate-env --json` → OK (sem required_env)
- `python3 .specify/scripts/qa_startup.py --platform prosauai --cwd /path/to/prosauai --validate-env --json` → lista vars ausentes/presentes corretamente
- `python3 .specify/scripts/skill-lint.py` → todos os skills válidos
- `python3 .specify/scripts/platform_cli.py lint --all` → todos os platform.yaml válidos
- `make test` → todos os testes verdes (incluindo test_qa_startup.py)

### Guardrails (auto-sabotagem)

Este epic é de baixo risco de auto-sabotagem comparado ao 024 (não toca easter.py/dag_executor.py), mas tem 2 regras críticas:

1. **Ordem de fases é inviolável**: qa_startup.py (Phase 1) deve estar completo e testado ANTES de qualquer skill file referenciar `qa_startup.py --start`. A implementação da Phase 1 ANTES das Phases 3-4 garante isso estruturalmente.

2. **Cada skill edit deve passar skill-lint**: `python3 .specify/scripts/skill-lint.py --skill <name>` após cada edição em `.claude/commands/**`. Se lint falhar, reverter o edit e corrigi-lo antes de avançar para a próxima task.

3. **`make test` verde entre phases críticas**: Após Phase 1 (qa_startup.py + testes), após Phase 5 (skill edits), antes da Phase 7.

4. **Comportamento aditivo**: Todas as mudanças são opcionais quando `testing:` block ausente. Plataformas existentes sem o bloco mantêm comportamento atual intacto.
