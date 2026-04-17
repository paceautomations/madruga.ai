# MAKE_TEST_GREAT_AGAIN.md

> Trigger: Epic 007 (prosauai — Admin Dashboard) entregou código aprovado pelo pipeline (Judge 85%,
> QA "healed 10 findings") mas 7 bugs básicos de runtime escaparam. Nenhum era obscuro — Docker não
> buildava, porta não acessível, tela em branco, variável de ambiente faltando.
>
> Este documento mapeia o que o pipeline faz bem, todos os gaps com análise profunda, e propõe uma
> evolução que funciona para **qualquer plataforma** (Python+venv, Node.js, Docker Compose, scripts,
> Makefile). O objetivo final: erros básicos de runtime se tornam inaceitáveis — o pipeline os
> detecta e bloqueia antes da entrega.

---

## 0. Os 7 bugs que escaparam (Epic 007)

| # | Bug | Categoria | Por que escapou |
|---|-----|-----------|-----------------|
| 1 | `COPY package.json` — arquivo não existia no monorepo root | Build quebrado | Pipeline nunca executou `docker compose build` |
| 2 | `COPY .../public` — diretório opcional inexistente | Build quebrado | Mesmo acima |
| 3 | `localhost:3000` → ERR_CONNECTION_TIMED_OUT | Porta inacessível | Nenhuma verificação de reachability |
| 4 | Dashboard KPIs vazios — API URL apontava para IP Tailscale | Config errada | `.env` nunca validado contra uso real |
| 5 | Tela de login não aparecia — cookie antigo válido ainda presente | Fluxo não testado | Nenhuma jornada de usuário executada |
| 6 | Root `/` exibia placeholder — redirect para `/admin` ausente | Routing regression | Nenhuma navegação de browser automatizada |
| 7 | Login falhava — `JWT_SECRET`, `ADMIN_BOOTSTRAP_*` ausentes | Config faltando | `.env.example` nunca comparado com `.env` real |

**Padrão**: todos são problemas de **runtime e deployment**, não de código. As camadas estáticas
(L1 ruff/eslint, L3 code review, Judge 4-personas) funcionaram como esperado. O buraco é que L5
(API) e L6 (browser) foram silenciosamente pulados porque os serviços não estavam rodando — e o
pipeline nunca tentou subi-los.

---

## Part 1 — O que o pipeline já faz bem

### 1.1 Static Analysis (QA L1) — FORTE

- `ruff`, `eslint`, `tsc`, `mypy`, `prettier` sempre rodam no diff inteiro
- Bloqueia merge em qualquer erro; heal loop auto-corrige o que é automático
- Agnóstico de plataforma: detecta tooling disponível e adapta

### 1.2 Code Review + Judge 4-Personas — FORTE

Encontrou e corrigiu bugs reais *antes de qualquer teste de runtime*:
- `pool.acquire()` starvation sob logins concorrentes
- `bcrypt` bloqueando o event loop
- UUID type mismatch em chamada asyncpg
- `timeout=5.0` faltando em pool acquire

Esses bugs só aparecem sob carga em staging. Judge score 85% (3 BLOCKERs fixados).

### 1.3 Testes automatizados — SÓLIDO (backend)

prosauai: 57 arquivos de teste, `--cov-fail-under=80` no `pyproject.toml`.
- 824 testes rodaram; fixtures capturadas reais (26+ pares de payload Evolution API)
- Testes de isolação multi-tenant, auth routes, health endpoint cobertos

### 1.4 Consistência spec↔código (speckit.analyze ×2) — SÓLIDO

- Pré-implementação: encontrou FR duplicados, rate limit scope errado
- Pós-implementação: 13 mismatches (handler wired mas não registrado, código redundante)

### 1.5 Documentation drift (reconcile) — SÓLIDO

Detectou 33% drift pós-Epic 007 (6/9 docs desatualizados). Funciona bem como safety net de docs.

---

## Part 2 — Filosofia: Testing Pyramid para o pipeline madruga

O pipeline atual entrega confiável as **duas camadas de baixo**. As três de cima são ignoradas ou
manuais. O objetivo desta evolução é completar a pirâmide.

```
                      /\
                     /E2E\
                    / Jornadas de usuário (journeys.md)
                   /--------\
                  /  System   \
                 /  Todos URLs, /health, screenshots, config válida
                /--------------\
               /  Integration   \
              /  Contratos API, DB, multi-serviço
             /------------------\
            /   Unit / Static    \
           /  pytest, jest, ruff, tsc  ← já funciona
          /------------------------\
```

**Princípio central**: o QA skill deve se tornar um especialista na plataforma que está testando.
Não um verificador genérico de "o que conseguir rodar" — um agente que conhece as jornadas,
os serviços, os endpoints, e as telas dessa plataforma específica.

---

## Part 3 — Nova estrutura: Testing Manifest por plataforma

### 3.1 O problema de não ter um manifesto

O QA atual não sabe:
- Como subir os serviços dessa plataforma (Docker? venv? npm? Make?)
- Quais URLs existem e o que cada uma deve retornar
- Quais jornadas de usuário validar
- Quais variáveis de ambiente são obrigatórias

Ele opera cego — detecta heuristicamente o que pode e pula o resto silenciosamente.

### 3.2 Solução: `platforms/<name>/testing/`

Cada plataforma ganha um diretório de testing com dois arquivos:

```
platforms/<name>/
  testing/
    manifest.yaml   ← como subir, quais URLs, env required
    journeys.md     ← jornadas de usuário com steps e assertions
```

**Quem cria**: `madruga:blueprint` gera o esqueleto; cada epic atualiza via reconcile.
**Quem lê**: QA skill lê como primeira ação, antes de qualquer outra coisa.
**Quem atualiza**: `speckit.tasks` adiciona task de update a journeys.md para epics com novos FRs.

### 3.3 Formato: `manifest.yaml`

```yaml
# platforms/<name>/testing/manifest.yaml

startup:
  type: docker           # docker | venv | npm | make | script | none
  # docker: usa docker compose up -d
  # venv: ativa .venv e roda o comando abaixo
  # npm: roda npm run dev / pnpm dev
  # make: roda make <target>
  # script: roda script custom
  # none: serviços externos, não há startup local
  command: null          # override opcional; null = usa default do type
  ready_timeout: 60      # segundos para aguardar health_check ficar verde

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
  # Registro completo de todos os endpoints/telas que devem ser testados
  # Atualizado a cada epic que adiciona ou remove URLs
  - url: http://localhost:8050/health
    type: api
    label: Health Check
    expect_status: 200
    expect_schema: '{"status": "string", "checks": "object"}'
  - url: http://localhost:8050/api/auth/login
    type: api
    method: POST
    label: Login endpoint
    expect_status: [200, 401]
  - url: http://localhost:3000
    type: frontend
    label: Root (should redirect to /admin)
    expect_redirect: /admin
  - url: http://localhost:3000/login
    type: frontend
    label: Login page
    expect_contains: ["email", "password", "entrar"]
  - url: http://localhost:3000/admin/dashboard
    type: frontend
    label: Dashboard (authenticated)
    requires_auth: true
    expect_contains: ["KPI", "gráfico"]

required_env:
  # Vars sem as quais o serviço inicia mas se comporta de forma quebrada
  # (diferente de vars que fazem o processo crashar no startup — essas o health check pega)
  - JWT_SECRET
  - ADMIN_BOOTSTRAP_EMAIL
  - ADMIN_BOOTSTRAP_PASSWORD

env_file: .env.example   # fonte de verdade para o diff de vars
journeys_file: testing/journeys.md
```

### 3.4 Formato: `journeys.md`

```markdown
# Testing Journeys — <platform>

> Atualizado em: YYYY-MM-DD (epic NNN)
> Cada jornada mapeia um fluxo de usuário real. QA executa todas automaticamente.
> Falha em qualquer step é BLOCKER na entrega do epic.

---

## Journey J-001: Admin Login — Happy Path
**Epic de origem**: 007-admin-front-dashboard
**User story**: US-001
**URLs**: POST /api/auth/login, GET /admin, GET /admin/dashboard

### Steps
1. GET http://localhost:3000 → redireciona para /login (HTTP 302 ou meta-refresh)
2. Screenshot: tela de login visível (campos email + senha + botão)
3. POST /api/auth/login `{"email": "$ADMIN_BOOTSTRAP_EMAIL", "password": "$ADMIN_BOOTSTRAP_PASSWORD"}`
   → HTTP 200, body contém `"token"` ou cookie `admin_token` setado
4. GET http://localhost:3000/admin/dashboard (com cookie)
   → HTTP 200, body contém texto "KPI" ou "dashboard"
5. Screenshot: dashboard com pelo menos 1 card de KPI visível (não placeholder, não loading)

### Assertions
- [ ] Redirect da root para /login funciona
- [ ] Campos de login renderizam
- [ ] Credenciais corretas → autenticado com sucesso
- [ ] Dashboard carrega com dados reais (não vazio)

### Failure scenarios
- Credenciais erradas → HTTP 401, mensagem de erro visível
- Cookie expirado → redirect para /login (não mostrar dashboard vazio)

---

## Journey J-002: Webhook ingest — Multi-tenant isolation
**Epic de origem**: 001-channel-pipeline
**URLs**: POST /webhook/{tenant_id}

### Steps
1. POST /webhook/ariel com payload válido e secret correto → HTTP 200
2. POST /webhook/resenhai com mesmo msg_id → HTTP 200 (deduplication ativa)
3. POST /webhook/ariel com secret errado → HTTP 401
4. POST /webhook/unknown_tenant → HTTP 404

### Assertions
- [ ] Tenant A não vê mensagens do Tenant B
- [ ] Duplicate msg_id → idempotência (não processa duas vezes)
- [ ] Auth failures retornam 4xx, não 5xx

---
```

**Regras de manutenção das journeys.md:**
- Toda journey tem `Epic de origem` — qual epic a criou
- `reconcile` verifica se epics novos adicionaram FRs sem journey correspondente (HIGH se faltando)
- `speckit.tasks` gera task explícita: "T{N}: Adicionar/atualizar Journey J-NNN em journeys.md"
- QA reporta timestamp do último `Last validated` por journey

---

## Part 4 — Gaps revisados (plataforma-agnósticos)

---

### GAP-01: Pipeline nunca sobe os serviços para testar

**Problema genérico**: Não é "pipeline não usa docker" — é "pipeline não detecta e inicia a
plataforma de nenhuma forma antes de tentar testar L5/L6".

**Análise**: O QA atual pula L5 e L6 silenciosamente se nada está rodando. O problema não é
Docker-específico: uma plataforma Python-only com `uvicorn` ou um CLI Node.js com `npm run dev`
teriam exatamente o mesmo problema.

**Startup types e como detectar cada um:**

| Tipo | Indicador | Comando padrão | Indicador de ready |
|------|-----------|---------------|-------------------|
| `docker` | `docker-compose.yml` ou `compose.yaml` | `docker compose up -d` | health_check URL responde 200 |
| `venv` | `.venv/` + `pyproject.toml` com `[tool.scripts]` | `source .venv/bin/activate && uvicorn ...` | `curl /health` |
| `npm` | `package.json` com script `dev` ou `start` | `npm run dev` ou `pnpm dev` | porta configurada em `package.json` responde |
| `make` | `Makefile` com target `run` ou `start` | `make run` | health_check URL responde |
| `script` | `scripts/start.sh` ou similar | declarado em manifest.yaml | health_check URL responde |
| `none` | plataforma é puramente código/biblioteca | n/a | testes unitários rodam direto |

**Root cause no caso Epic 007**: `manifest.yaml` não existe → QA não sabe que tipo de startup usar
→ tenta adivinhar → falha silenciosamente → pula L5/L6.

#### Alternativas

**A. QA lê `testing/manifest.yaml` e executa startup declarado** (Recomendado)
- QA lê `startup.type` do manifest, executa o comando apropriado, aguarda `health_checks` ficarem
  verdes (timeout configurável), depois prossegue com L5/L6
- Se startup falha → BLOCKER com output do comando de erro
- Se manifest não existe → WARNING + instrução para criar
- Pros: Funciona para todos os tipos de plataforma; comportamento previsível; falha explicativa
- Cons: Requer que manifest.yaml exista e seja mantido; execução de subprocesso no contexto QA

**B. QA detecta heuristicamente o startup sem manifest**
- Presença de `docker-compose.yml` → tenta `docker compose up -d`
- Presença de `.venv/` + `pyproject.toml` → tenta `uvicorn` via config
- Presença de `package.json` com script `dev` → tenta `npm run dev`
- Pros: Zero configuração adicional
- Cons: Heurísticas falham para setups não-padrão; comportamento opaco; não declarativo

**C. BLOCKER explícito em vez de SKIP silencioso**
- Se L5/L6 não conseguem rodar → BLOCKER (não skip), epic não fecha
- Pros: Força resolução sem exigir infraestrutura de startup automatizada
- Cons: Requer que o desenvolvedor suba manualmente antes do QA rodar; ainda depende de intervenção

**Recomendação**: A é o objetivo final, B como fallback enquanto A é implementado, C como política
imediata (zero tolerance para SKIP silencioso).

---

### GAP-02: Reachability dos serviços não é validada

**Problema genérico**: O serviço pode "estar rodando" mas inacessível do contexto onde o teste
roda. Exemplos: porta bound em IP específico (Tailscale, bridge Docker), serviço em container sem
expose para host, URL com schema errado (http vs https), proxy em frente à porta real.

**Isso não é Docker-específico.** Um `uvicorn` pode subir em `0.0.0.0:8000` mas `.env` configurar
`API_URL=http://192.168.1.x:8000` — browser no host recebe connection refused.

#### Alternativas

**A. QA valida reachability de cada URL do manifest via request real** (Recomendado)
- Para cada `health_checks` e `urls` no manifest: faz request real e verifica
  - HTTP response chega (não connection refused/timeout)
  - Status code dentro do esperado
  - Body contém o pattern esperado
- Se falhar: BLOCKER com URL + erro + sugestão (ex: "bind em 127.0.0.1 se rodando em WSL2")
- Pros: Cobre Docker, venv, npm, qualquer tipo; detecta bugs de configuração de rede
- Cons: Requer URLs declaradas no manifest

**B. QA tenta URL alternativa automaticamente**
- Se `http://localhost:8050` falha mas algum container está rodando: tenta `http://0.0.0.0:8050`,
  `http://127.0.0.1:8050`; lista os ports expostos via `docker ps`
- Pros: Reduz falsos negativos
- Cons: Obscurece o problema real (configuração errada deve ser corrigida, não contornada)

**C. Validar que variáveis de URL no .env resolvem para o mesmo host**
- Parse `.env` para `*_URL`, `*_API_URL`, `NEXT_PUBLIC_*` — verificar que o host está acessível
- Pros: Pega a classe de bug "URL configurada incorretamente no env"
- Cons: Só cobre variáveis de ambiente, não hardcoded URLs no código

**Recomendação**: A (validação explícita de cada URL do manifest) + C (validação de env URL vars).

---

### GAP-03: L5 (API) e L6 (browser) nunca ativam automaticamente

**Problema genérico**: O QA atual precisa de dois inputs externos para ativar as camadas de runtime:
1. Serviços já rodando (GAP-01)
2. `base_url` passado explicitamente pelo usuário ou DAG executor

Sem esses dois, ambas as camadas são silenciosamente puladas.

**Isso afeta toda plataforma**, não só prosauai. Qualquer epic que não passar `base_url` para o QA
nunca terá L5/L6 executado.

#### Alternativas

**A. `platform.yaml` declara `testing.manifest` e DAG executor injeta no QA** (Recomendado)
- `dag_executor.compose_task_prompt` para o nó QA: lê `testing/manifest.yaml`, injeta como
  contexto no prompt do QA — incluindo todos os `health_checks.url` e `urls`
- QA usa isso como sua base, não precisa de input externo
- Pros: Funciona sem interação humana; consistente entre epics; plataforma declara suas URLs
- Cons: Requer manifest.yaml atualizado; um-time setup por plataforma

**B. QA descobre URLs do manifest autonomamente**
- QA lê `platforms/<name>/testing/manifest.yaml` como primeira ação (Step 0)
- Se manifest não existe → emite WARNING e cria template
- Pros: Sem mudança no DAG executor
- Cons: QA precisa saber o nome da plataforma ativa (já disponível via `platform_cli.py current`)

**C. Usuário deve sempre fornecer URL**
- Documentar no QA skill: "sempre passe a URL base: `/madruga:qa http://localhost:3000`"
- Pros: Zero implementação
- Cons: Esquecido 100% das vezes em runs automáticos pelo DAG executor

**Recomendação**: B (QA lê manifest autonomamente) com A como refinamento (DAG injeta). C é o
status quo e prova que não funciona.

---

### GAP-04: Nenhuma jornada de usuário é executada

**Problema genérico**: O QA valida que serviços sobem e URLs respondem, mas não valida que os
**fluxos de negócio** funcionam de ponta a ponta. Um login que retorna 200 mas exibe tela em branco
passa no healthcheck e falha na jornada.

**Isso é o gap mais crítico**: a plataforma pode estar "saudável" por todos os indicadores
técnicos mas estar entregando uma experiência quebrada para o usuário real.

#### Alternativas

**A. QA lê `journeys.md` e executa cada journey como test case** (Recomendado)
- QA Step L5.5 (Journey Testing): lê `testing/journeys.md`, executa steps sequencialmente usando
  HTTP requests (para journeys API) e Playwright MCP (para journeys frontend)
- Para cada journey: reporta PASS/FAIL com step de falha e evidência (screenshot para UI,
  response body para API)
- Falha em qualquer journey marcada como `required: true` → BLOCKER
- Pros: Valida comportamento real, não apenas disponibilidade; documentação e testes são a mesma coisa
- Cons: Requer journeys.md atualizado; Playwright MCP necessário para UI journeys

**B. QA gera journeys ad-hoc a partir da spec.md**
- QA lê spec.md, identifica user stories, deriva steps de teste dinamicamente
- Pros: Não exige manutenção de journeys.md
- Cons: Geração não-determinística; testes não são commitados no repo; não acumulam entre epics

**C. Journeys como testes automatizados no repo (pytest + playwright)**
- `speckit.tasks` gera tasks: "Escrever teste e2e para Journey J-001 usando playwright/pytest"
- Testes ficam em `tests/e2e/` do repo da plataforma, rodam no QA L2
- Pros: Testes são código; rodados em CI; regressões detectadas automaticamente
- Cons: Mais trabalho de implementação; depende de disciplina para manter

**D. Combinação A + C**
- journeys.md como spec de alto nível (steps + assertions em linguagem natural)
- QA executa diretamente via Playwright MCP
- Tasks geram também testes de código `tests/e2e/` que espelham as journeys
- Pros: Documentação + testes de código + execução automática no QA
- Cons: Redundância proposital (dois lugares para manter)

**Recomendação**: A imediatamente (QA executa journeys.md via Playwright/requests), C como meta de
qualidade (journeys.md → testes de código commitados no repo). D é o estado ideal.

---

### GAP-05: Sem testes automatizados no frontend

**Problema genérico**: Qualquer plataforma com frontend (React, Next.js, Vue, Svelte, Astro) que
não declare um test runner não tem nenhuma camada de validação de componentes. O QA L2 pula
silenciosamente se `npm test` falha com "script not found".

**Padrão de evasão silenciosa é o problema real**: não é só que os testes não existem — é que o
pipeline aceita isso sem protestar.

#### Alternativas

**A. `npm test` ausente → BLOCKER (não skip) se há componentes .tsx no diff** (Recomendado imediato)
- QA L2: detecta arquivos `.tsx`/`.jsx`/`.vue`/`.svelte` no diff; se existem e `npm test` falha
  com "missing script" → BLOCKER com mensagem: "Frontend sem test runner — adicionar vitest ou jest"
- Pros: Cobre todas as tecnologias de frontend; sem falsos positivos em projetos puramente backend
- Cons: Não cria os testes — apenas impede entrega sem eles

**B. Blueprint gera test infrastructure como parte do scaffold frontend** (Recomendado estrutural)
- `madruga:blueprint` para plataformas com serviço frontend: inclui seção declarando
  `vitest` + `@testing-library/react` + `playwright` como dependências obrigatórias
- ADR documenta a escolha; `speckit.tasks` gera T001: "Configurar test infrastructure"
- Pros: Baked in desde o início; não é por-epic mas por-plataforma
- Cons: Catch-up necessário para plataformas existentes (prosauai)

**C. `speckit.analyze` (pós-implementação) verifica cobertura de componentes novos**
- Para cada novo arquivo `.tsx` no diff sem `*.test.tsx` correspondente → HIGH finding
- Pros: Enforcado por componente, não só por epic
- Cons: Pode ser ruído para componentes puramente de layout

**D. Constitution como non-negotiable**
- `spec/constitution.md` da plataforma declara: "todo componente com lógica de negócio tem teste"
- `speckit.analyze` verifica contra constitution → HIGH se violado
- Pros: Política explícita acordada pelo time
- Cons: Constitution precisa existir e ser mantida

**Recomendação**: A (imediato) + B (estrutural) + D (política). C é consequência natural de B+D.

---

### GAP-06: Config e variáveis de ambiente não validadas

**Problema genérico**: O app sobe, o health check passa, mas está mal configurado. Isso acontece
quando variáveis críticas têm defaults ruins ou silenciosamente ausentes — JWT_SECRET com valor
vazio não impede startup mas quebra auth; ADMIN_BOOTSTRAP_* ausente deixa o usuário sem como logar.

**Não é Docker-específico**: um `uvicorn` com `pydantic-settings` e `model_config = ConfigDict(extra='ignore')`
não crasha em variáveis faltando se elas têm defaults — elas simplesmente ficam wrongas.

#### Alternativas

**A. QA diff `.env.example` vs `.env` antes de iniciar** (Recomendado)
- Lê todas as keys de `.env.example`; verifica cada uma em `.env` real
- Heurística "required": key sem default no `.env.example` (linha sem `=valor` ou com `=` vazio),
  ou key com nome `*_SECRET`, `*_PASSWORD`, `*_KEY`, `*_TOKEN`
- Emite WARNING para opcionais, BLOCKER para required
- Pros: Funciona para qualquer plataforma que use `.env.example`; rápido (<1s)
- Cons: Heurística de "required vs opcional" pode ter falsos positivos

**B. `manifest.yaml` declara `required_env` explicitamente** (Recomendado complementar)
- Lista explícita, sem heurísticas
- Pros: Preciso; intenção explícita
- Cons: Deve ser mantida a cada epic que adiciona variáveis

**C. Health endpoint reporta missing config**
- `/health` retorna `{"status": "degraded", "missing_config": ["JWT_SECRET"]}` para vars required
  não setadas
- QA L5 pega automaticamente ao verificar health
- Pros: Validação em runtime, não apenas textual; útil também em prod/staging
- Cons: Requer que a plataforma implemente esse padrão; expõe nomes de vars (mitigável)

**D. `speckit.tasks` gera task de atualizar `required_env` no manifest quando novos envs são adicionados**
- Quando o diff inclui `.env.example` ou `settings.py/pydantic`, task automática:
  "T{N}: Atualizar `required_env` no testing/manifest.yaml"
- Pros: Mantém o manifest atualizado automaticamente
- Cons: Depende do QA e tasks estarem integrados

**Recomendação**: A + B (defesa dupla) + C (para plataformas backend com health endpoint). D como
processo de manutenção.

---

### GAP-07: Artefatos de build nunca são executados

**Problema genérico**: O pipeline verifica código mas não verifica se o código **builda**. Isso
afeta Docker images, pacotes Python (`python -m build`), bundles Node.js (`npm run build`),
scripts executáveis, CLIs com entrypoints declarados.

**Não é só Docker**: um `pydantic` model com sintaxe válida em Python mas com import circular
quebra só quando o módulo é importado — não detectado por linting mas detectado por `python -c
"import prosauai"`.

#### Alternativas

**A. QA L4 sempre tenta o build do projeto (tipo detectado via manifest)** (Recomendado)
- `docker compose build --dry-run` (Docker Compose v2.17+): valida Dockerfiles sem executar
- `npm run build` (Node.js): falha em erros de compilação TypeScript e import missing
- `python -c "import <main_module>"` (Python): detecta import errors, circulares, syntax errors
- `docker compose config --quiet` (Docker): valida YAML de compose sem acessar registry
- Pros: Captura a classe inteira de "builda localmente mas não no CI/container"
- Cons: `npm run build` pode ser lento (~30-90s); requer o ambiente correto

**B. `speckit.tasks` inclui task de verificação de build em cada epic**
- Task obrigatória: "T{N}: Verificar que `<build_command>` passa sem erros"
- Implementado como parte do speckit.implement
- Pros: Integrado ao flow de implementação
- Cons: Task pode ser skipada se o implementador não a considerar crítica

**C. Verificação de build como parte da fase de smoke (ver GAP-09)**
- Incluir build check na Deployment Smoke Phase gerada por speckit.tasks
- Pros: Agrupado com outros checks de runtime
- Cons: Rodado apenas no fim, não durante a implementação

**Recomendação**: A (QA sempre tenta build via manifest) + C (incluir em smoke phase).

---

### GAP-08: Sem CI/CD na plataforma

**Problema genérico**: O pipeline madruga roda apenas quando acionado manualmente para um epic.
Entre epics, qualquer commit direto para a branch base da plataforma pode quebrar o build,
os testes, ou os serviços — sem nenhuma validação automática.

**Impacto**: reverse-reconcile detecta *drift de documentação*, não *breakage de código*. São
problemas diferentes. Um bug introduzido entre epics fica invisível até o próximo epic.

#### Alternativas

**A. `madruga:blueprint` gera `.github/workflows/ci.yml` para plataformas com repo binding** (Recomendado)
- Workflow mínimo: `push` + `pull_request` em `develop` e `epic/**`
- Jobs: static analysis (ruff/eslint), unit tests (pytest/jest), build verification
- Não inclui Docker build por padrão (lento) — opcional via workflow_dispatch
- Pros: Standard; gratuito no GitHub; bloqueia PRs quebrados
- Cons: Arquivo a mais para manter; Docker em CI pode ser lento sem cache

**B. CI gerado como task em epics que tocam infra**
- `speckit.tasks` detecta mudanças em `Dockerfile`, `docker-compose.yml`, `package.json` root
  → gera task: "Adicionar/atualizar GitHub Actions CI"
- Pros: Targeted; não é universal, só quando relevante
- Cons: CI deveria existir sempre, não só quando infra muda

**C. `madruga:ship` valida CI antes do push**
- Antes do push, `ship` checa `gh run list --branch <current>` para falhas recentes
- Pros: Integrado ao workflow existente
- Cons: Inútil se CI não existe; não previne push se CI está demorando

**Recomendação**: A. CI é infraestrutura base, não feature. Blueprint deve gerá-lo por padrão para
qualquer plataforma com `repo:` binding.

---

### GAP-09: `speckit.tasks` não gera fase de Deployment Smoke

**Problema genérico**: Tasks.md gera fases de implementação e testes unitários mas não inclui
nenhuma validação de que o produto funciona como deployado. A última fase de implementação é código
— não há fase de "subir, abrir, verificar".

**O resultado**: "done" significa "código escrito e testes passando" — não "produto funcionando".

#### Alternativas

**A. `speckit.tasks` adiciona fase de Deployment Smoke como última fase obrigatória** (Recomendado)
- Template de fase final gerado automaticamente, adaptado ao tipo de startup do manifest:

  Para `docker`:
  ```
  ## Phase N: Deployment Smoke
  - [ ] T{N}: `docker compose build` sem erros
  - [ ] T{N+1}: `docker compose up -d` && todos health_checks do manifest respondem 200
  - [ ] T{N+2}: Executar todas as journeys J-001..J-N do journeys.md manualmente
  - [ ] T{N+3}: Screenshot de cada tela principal (colada no PR ou epic)
  ```

  Para `venv`/Python:
  ```
  ## Phase N: Deployment Smoke
  - [ ] T{N}: `python -m <module>` importa sem erros
  - [ ] T{N+1}: `make run` sobe o servidor; `curl /health` retorna 200
  - [ ] T{N+2}: Executar journeys de API do journeys.md
  ```

  Para `npm`:
  ```
  ## Phase N: Deployment Smoke
  - [ ] T{N}: `npm run build` sem erros
  - [ ] T{N+1}: `npm run start` sobe; URL principal carrega
  - [ ] T{N+2}: Screenshot do happy path principal
  ```
- Pros: Faz o "não funciona no deploy" inaceitável; sem ambiguidade sobre o que "done" significa
- Cons: ~3-4 tasks adicionais por epic; requer manifest.yaml para adaptar o template

**B. `speckit.analyze` (pós-implement) detecta ausência de smoke tasks**
- Se nenhuma task menciona "smoke", "deploy", "docker up", "health" → HIGH finding
- Pros: Baixo custo de implementação
- Cons: Advisory — pode ser ignorado

**Recomendação**: A. Smoke phase é non-negotiable. Se tasks não inclui, epic não terminou.

---

### GAP-10: Sem validação visual (screenshots)

**Problema genérico**: Qualquer plataforma com interface de usuário (web, CLI com output visual,
dashboards) pode ter problemas de renderização que passam por todos os testes técnicos mas são
imediatamente visíveis a um humano em 1 segundo: tela em branco, dados ausentes, elementos fora
de posição, loading states travados.

**O pipeline nunca tira um screenshot de nada.**

#### Alternativas

**A. QA L6: screenshot obrigatório de cada URL `type: frontend` do manifest** (Recomendado mínimo)
- Quando L6 ativa (Playwright MCP disponível): navega a cada URL frontend do manifest,
  tira screenshot, embute no `qa-report.md`
- Validações básicas: título não vazio, sem overlay de erro, ao menos 1 elemento visível,
  body não é HTML de placeholder
- Pros: Near-zero effort; captura blank pages, 500 errors, routing failures, loading states
- Cons: Não detecta "dados errados" sem um baseline

**B. Screenshots de journeys como evidência de conclusão**
- Cada journey com steps de UI inclui screenshot obrigatório no passo final
- Armazenado em `epics/NNN/evidence/` como evidência de entrega
- Pros: Cria registro histórico de como a feature estava quando entregue
- Cons: Não é regression testing — é só evidência pontual

**C. Pixel diff contra golden baseline**
- Após primeiro run bem-sucedido, screenshots armazenados como golden em `testing/golden/`
- Runs subsequentes: diff pixel-a-pixel; delta > threshold → WARNING
- Pros: Detecção de regressão visual
- Cons: Frágil para conteúdo dinâmico; overhead de storage; setup complexo

**Recomendação**: A + B imediatamente. C como evolução futura (quando as plataformas estiverem
maduras o suficiente para ter UIs estáveis).

---

### GAP-11: `journeys.md` não existe em nenhuma plataforma

**Problema**: O conceito de jornada de usuário está nos pitches e nas specs, mas nunca se
consolida em um documento de teste que sobrevive de epic em epic. Cada epic testa (ou não testa)
seus próprios fluxos ad-hoc, sem acumular um repositório de cenários de teste.

**Impacto**: Regressões em journeys de epics anteriores nunca são detectadas. Epic 012 pode
quebrar a Journey J-001 de Epic 007 sem nenhuma validação automatizada.

#### Alternativas

**A. `madruga:blueprint` cria `testing/manifest.yaml` e `testing/journeys.md` como parte do scaffold** (Recomendado)
- Ambos os arquivos gerados com template vazio durante blueprint
- `reconcile` verifica se journeys.md está desatualizado (última epic sem journey registrada) → HIGH
- Pros: Estrutura estabelecida desde o início; reconcile mantém viva
- Cons: Template vazio precisa ser preenchido nos primeiros epics

**B. `speckit.tasks` gera task de criar/atualizar journey para cada epic com FRs de usuário**
- Detecta user stories no spec.md → gera task: "T{N}: Adicionar Journey J-NNN no journeys.md para US-NNN"
- Pros: Acoplado ao epic que introduz o fluxo
- Cons: Pode ser ignorado se developer não entender a importância

**C. `reconcile` atualiza journeys.md automaticamente**
- Após epic reconciliado, reconcile extrai user stories entregues + acceptance criteria e propõe
  novos entries em journeys.md como patch JSON
- Pros: Automático; usa o mesmo mecanismo de reverse-reconcile
- Cons: Geração automatizada pode ter qualidade variável

**Recomendação**: A (estrutura criada no blueprint) + B (tasks forçam preenchimento) + C
(reconcile propõe expansões). Três camadas de garantia.

---

### GAP-12: Ausência de URL coverage check por epic

**Problema**: Cada epic adiciona endpoints (API routes, páginas frontend, webhooks). Não há
verificação de que todos os endpoints novos foram adicionados ao manifest.yaml e cobertos por
alguma journey.

**Impacto**: URLs "órfãs" — existem no código, não estão no manifest, nunca são testadas por
qualquer camada.

#### Alternativas

**A. `speckit.analyze` (pós-implement) compara rotas no código vs manifest.yaml** (Recomendado)
- Para Python/FastAPI: extrai `@router.get/post/...` do diff; compara com `urls` do manifest
- Para Next.js: extrai arquivos em `app/` ou `pages/`; compara com `urls` do manifest
- URLs não cobertas → HIGH finding: "URL nova não declarada no testing/manifest.yaml"
- Pros: Enforcement automático; sem overhead manual
- Cons: Extração de rotas é heurística; pode perder rotas dinâmicas

**B. `speckit.tasks` gera task de atualizar manifest para FRs com novas rotas**
- Detecta FRs do tipo "API endpoint" ou "nova tela" → gera task:
  "T{N}: Adicionar URL `POST /api/xxx` ao testing/manifest.yaml"
- Pros: Proativo (durante planejamento, não após)
- Cons: Depende de disciplina para executar a task

**C. QA reporta URLs encontradas no código que não estão no manifest**
- QA grep rotas no diff, compara com manifest, reporta como WARNING
- Pros: Detecta na entrega
- Cons: Tardio demais; task não foi gerada

**Recomendação**: A (analyze enforcement) + B (tasks proativo). URL coverage deve ser
verificada antes e depois da implementação.

---

## Part 5 — Tabela-resumo dos Gaps

| Gap | Severidade | Bugs que capturaria | Fix recomendado | Esforço |
|-----|-----------|---------------------|----------------|---------|
| GAP-01: Sem startup de serviços | CRÍTICO | 1,2,3,4,5,6,7 | QA lê manifest.yaml, executa startup | Médio |
| GAP-02: Reachability não validada | ALTO | 3,4 | QA valida cada URL do manifest via request real | Baixo |
| GAP-03: L5/L6 não ativam | ALTO | 3,4,5,6 | QA lê manifest autonomamente (Step 0) | Baixo |
| GAP-04: Sem jornadas de usuário | ALTO | 5,6 + todas regressões | QA executa journeys.md via Playwright/requests | Médio |
| GAP-05: Sem testes de frontend | ALTO | 5,6 | Blocker se tsx no diff sem test runner | Médio |
| GAP-06: Config env não validada | MÉDIO | 5,6,7 | QA diff .env.example vs .env real | Baixo |
| GAP-07: Build não executado | MÉDIO | 1,2 | QA L4 executa build via manifest.startup.type | Baixo |
| GAP-08: Sem CI/CD | MÉDIO | todos (entre epics) | Blueprint gera GitHub Actions | Médio |
| GAP-09: Sem Deployment Smoke phase | MÉDIO | 1,2,3 | speckit.tasks appende fase obrigatória | Baixo |
| GAP-10: Sem screenshots | BAIXO | 5,6 | QA L6 screenshot em toda URL frontend | Baixo |
| GAP-11: journeys.md não existe | ALTO | regressões cross-epic | Blueprint cria template; reconcile mantém | Médio |
| GAP-12: URL coverage gaps | MÉDIO | qualquer URL sem teste | speckit.analyze verifica rotas vs manifest | Médio |

---

## Part 6 — Definition of "Done" para um Epic (revisada)

Um epic só está done quando TODOS os checks abaixo passam. Os checks são **platform-aware** — cada
um adapta o comando ao tipo declarado em `testing/manifest.yaml`.

```
PRÉ-IMPLEMENTAÇÃO
[ ] speckit.analyze (pre)   — zero HIGH findings (FR coverage, task ordering)

IMPLEMENTAÇÃO
[ ] speckit.implement       — todos os tasks green, incluindo Deployment Smoke Phase

PÓS-IMPLEMENTAÇÃO
[ ] speckit.analyze (post)  — zero HIGH findings (code conformance, URL coverage)

QUALIDADE DE CÓDIGO
[ ] judge score >= 80       — 3 BLOCKERs max (fixados), WARNINGs documentados

QA STATIC (L1)
[ ] lint clean              — ruff/eslint/tsc sem erros
[ ] type check clean        — mypy/tsc --noEmit sem erros

QA TESTES AUTOMATIZADOS (L2)
[ ] testes passando         — 100% green
[ ] coverage >= 80%         — backend e frontend
[ ] frontend tem test runner— package.json tem script "test" (se há .tsx no diff)

QA BUILD (L4)
[ ] build succeeds          — docker compose build / npm run build / python -m build sem erros
[ ] compose config clean    — docker compose config --quiet (se Docker)
[ ] env vars validadas      — todos required_env do manifest presentes no .env

QA RUNTIME (L5)
[ ] todos health_checks 200 — cada URL de health_check do manifest responde dentro do timeout
[ ] todas URLs validadas    — cada URL do manifest responde com status e body esperados
[ ] env reachability OK     — NEXT_PUBLIC_*/API_URL vars resolvem para hosts acessíveis

QA JOURNEYS (L5.5)
[ ] todas journeys passam   — cada journey J-NNN do journeys.md executada com PASS
[ ] journeys atualizado     — epic adicionou journeys para seus FRs

QA BROWSER (L6) — apenas se há URLs frontend no manifest
[ ] screenshot sem blank    — toda URL frontend carrega sem tela em branco ou overlay de erro
[ ] happy path capturado    — screenshot da jornada principal como evidência

DOCS
[ ] reconcile               — zero drift ou todos items endereçados
[ ] journeys.md updated     — novos fluxos documentados
[ ] manifest.yaml updated   — novas URLs declaradas
```

---

## Part 7 — Roadmap de implementação

### Wave 1 — Políticas imediatas (zero código novo, mudança em skills)

1. **GAP-01 parcial**: QA: SKIP silencioso → BLOCKER explícito. Nenhum skip sem BLOCKER primeiro.
2. **GAP-06**: QA diff `.env.example` vs `.env` antes de qualquer layer
3. **GAP-07 parcial**: QA L4: `docker compose config --quiet` (ou equivalente por tipo)
4. **GAP-09**: `speckit.tasks`: Deployment Smoke Phase obrigatória no template
5. **GAP-10**: QA L6: screenshot obrigatório em toda URL frontend quando Playwright disponível

### Wave 2 — Estrutura de testing manifest (novo arquivo, mudança em blueprint + QA)

6. **GAP-11**: `madruga:blueprint` gera `testing/manifest.yaml` + `testing/journeys.md`
7. **GAP-03**: QA lê `testing/manifest.yaml` como Step 0 (antes de qualquer outra ação)
8. **GAP-01**: QA executa `startup.command` do manifest e aguarda `health_checks` ficarem verdes
9. **GAP-02**: QA valida reachability de cada URL do manifest via HTTP request real
10. **GAP-12 parcial**: `speckit.tasks` gera task de atualizar manifest para FRs com novas rotas

### Wave 3 — Journey execution + URL coverage (mudança em QA + analyze)

11. **GAP-04**: QA executa `journeys.md` como L5.5 — steps via HTTP requests + Playwright
12. **GAP-12**: `speckit.analyze` extrai rotas do diff e compara com manifest.urls
13. **GAP-05 estrutural**: Blueprint declara test infrastructure para frontends (vitest + playwright)
14. **GAP-08**: Blueprint gera `.github/workflows/ci.yml` para plataformas com `repo:` binding

---

## Appendix A — Epic 007: bugs vs gaps

| Bug | Gap responsável | Teria sido capturado por |
|-----|----------------|--------------------------|
| 1 — `COPY package.json` não encontrado | GAP-07 + GAP-01 | `docker compose build` no QA L4 |
| 2 — `COPY .../public` não encontrado | GAP-07 + GAP-01 | `docker compose build` no QA L4 |
| 3 — localhost:3000 ERR_CONNECTION_TIMED_OUT | GAP-01 + GAP-02 | QA sobe serviços + valida reachability |
| 4 — Dashboard KPIs vazios | GAP-01 + GAP-02 + GAP-04 | Journey J-001 step 4 (dashboard com dados) |
| 5 — Login page não apareceu | GAP-01 + GAP-04 | Journey J-001 step 2 (screenshot tela login) |
| 6 — Root `/` mostra placeholder | GAP-01 + GAP-04 + GAP-10 | Journey J-001 step 1 + screenshot root |
| 7 — Bootstrap env vars faltando | GAP-06 | QA diff .env.example vs .env |

---

## Appendix B — Exemplos de startup detection por tipo

```yaml
# Docker Compose (prosauai)
startup:
  type: docker
  command: docker compose up -d   # default; omitir se padrão
  ready_timeout: 90               # segundos
  health_checks:
    - url: http://localhost:8050/health
      expect_status: 200

# Python + venv (script de dados, CLI)
startup:
  type: venv
  command: uvicorn myapp.main:app --host 0.0.0.0 --port 8000
  ready_timeout: 15
  health_checks:
    - url: http://localhost:8000/health
      expect_status: 200

# Node.js standalone
startup:
  type: npm
  command: pnpm run dev          # default: npm run dev
  ready_timeout: 30
  health_checks:
    - url: http://localhost:3000
      expect_status: 200

# Makefile
startup:
  type: make
  command: make run
  ready_timeout: 20
  health_checks:
    - url: http://localhost:8080/ping
      expect_status: 200

# Biblioteca/SDK (sem servidor)
startup:
  type: none
  # L5/L6 não rodam — apenas L1/L2/L3
```

---

## Appendix C — Princípios de engenharia que guiam estas mudanças

1. **Shift left**: detectar problemas o mais cedo possível na pipeline. Erros de build devem ser
   capturados na fase de build, não na fase de QA ou, pior, na entrega.

2. **No silent skips**: qualquer skip de uma camada de validação deve emitir um BLOCKER. Silêncio
   é mentira — o sistema não pode dizer "passou" quando não verificou.

3. **Behavior over structure**: validar que o produto faz o que deveria fazer, não apenas que o
   código compila e os testes unitários passam. A testing pyramid sem as camadas de sistema e E2E
   é incompleta.

4. **Documentation = executable spec**: `journeys.md` não é documentação — é a especificação
   executável do comportamento esperado. Se não pode ser executado, não é documentação.

5. **Platform-aware QA**: o QA não é um verificador genérico. Ele deve ler o manifesto da
   plataforma e se tornar especialista no produto que está validando antes de executar qualquer
   teste.

6. **Defense in depth**: cada camada de teste é independente. Static analysis não substitui
   testes de runtime. Testes unitários não substituem testes de jornada. CI não substitui QA
   manual de novas features.
