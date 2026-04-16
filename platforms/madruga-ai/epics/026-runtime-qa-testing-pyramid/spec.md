# Especificação de Feature: Runtime QA & Testing Pyramid

**Feature Branch**: `epic/madruga-ai/026-runtime-qa-testing-pyramid`
**Criado**: 2026-04-16
**Status**: Draft
**Epic**: 026 — Runtime QA & Testing Pyramid

---

## Contexto

O pipeline madruga executa 6 camadas de QA, mas apenas 3 funcionam de forma confiável. As camadas L4 (Build Verification), L5 (API Testing) e L6 (Browser Testing) ou são puladas silenciosamente ou dependem de detecção heurística frágil — o relatório diz "passou" quando na prática nada de runtime foi verificado.

7 bugs de deployment escaparam do Epic 007 (prosauai — Admin Dashboard), todos capturaríveis por runtime QA: Dockerfile com diretórios inexistentes, URLs com IP errado, variáveis de ambiente ausentes, jornadas de login quebradas. Nenhum era obscuro — foram ignorados porque o pipeline simplesmente não tentou executá-los.

Este epic fecha o buraco: o pipeline passa a **conhecer como iniciar cada plataforma, quais URLs devem existir, e quais jornadas de usuário devem funcionar** — declarados explicitamente pelo mantenedor da plataforma, executados automaticamente pelo QA.

---

## Clarifications

### Session 2026-04-16

- Q: journeys.md deve ter formato machine-readable estruturado (YAML parseável) ou texto-guia por convenção para LLM? → A: **Formato estruturado YAML embedded em Markdown** — cada journey definida como bloco YAML que `qa_startup.py` parseia com pyyaml para steps de API, e o QA skill (LLM) lê para Playwright steps. Evita ambiguidade de prosa livre; alinha com ADR-004 (stdlib + pyyaml). Ver FR-021 (novo).

- Q: O JSON output de `qa_startup.py --validate-env` deve incluir os valores das variáveis de ambiente ou apenas os nomes? → A: **Apenas nomes (keys), nunca valores.** `env_present` e `env_missing` contêm somente nomes de variáveis. Nenhum valor de variável aparece em stdout, logs ou artefatos — previne vazamento de segredos. Ver FR-022 (novo).

- Q: Qual o fallback de `speckit.analyze` URL coverage check para frameworks além de FastAPI e Next.js? → A: **WARN explícito** — "Framework não reconhecido: URL coverage check disponível apenas para FastAPI e Next.js/React. Verificar cobertura manualmente." Nunca SKIP silencioso. Next.js detecta tanto `page.tsx`/`page.ts` (rotas UI) quanto `route.ts`/`route.js` (rotas API App Router). Ver FR-017 atualizado.

- Q: Qual a definição determinística de "placeholder HTML" para o WARN de US-04 cenário 3 / FR-013? → A: **Placeholder HTML** é detectado por qualquer um destes padrões no body da resposta: (1) conteúdo < 500 bytes após strip de whitespace; (2) presença literal de "You need to enable JavaScript", "React App", "Vite + React", "Welcome to nginx", "It works!"; (3) `<body>` com apenas whitespace; (4) HTTP 200 com `Content-Type` não sendo `text/html` para URL declarada como `type: frontend`. Ver FR-023 (novo).

- Q: `qa_startup.py` deve reiniciar automaticamente containers Docker obsoletos (já rodando mas health check falha) ou apenas reportar? → A: **Nunca reiniciar automaticamente** — destruição de estado é irreversível. Estratégia: se health check passa em containers já rodando → OK; se falha → WARN: "Serviços em execução mas health checks falharam. Execute `docker compose down && docker compose up -d` manualmente." `qa_startup.py` jamais executa `docker compose down`. Ver Casos de Borda atualizado.

---

## Cenários de Usuário & Testes

### US-01 — Mantenedor declara configuração de testes da plataforma (P1)

O mantenedor da plataforma precisa ensinar o pipeline como iniciar seus serviços, quais URLs validar e quais variáveis de ambiente são obrigatórias. Hoje essa informação não existe em nenhum lugar acessível ao pipeline.

**Por que P1**: É o fundamento de tudo — sem a declaração de configuração, nenhuma outra melhoria é possível. Representa a mudança de paradigma de "pipeline advinha" para "pipeline executa o que foi declarado".

**Teste Independente**: Pode ser validado adicionando o bloco `testing:` a um `platform.yaml` existente e verificando que o `platform_cli.py lint` valida o schema sem erros. Entrega valor imediato como documentação viva de como iniciar a plataforma.

**Cenários de Aceitação**:

1. **Dado** que um `platform.yaml` existe sem bloco `testing:`, **quando** o mantenedor adiciona o bloco com `startup.type: docker`, health checks e lista de URLs, **então** o `platform_cli.py lint` valida o schema com sucesso e nenhum erro é emitido.

2. **Dado** um `platform.yaml` com bloco `testing:` válido, **quando** qualquer campo obrigatório do bloco é removido (ex: `startup.type`), **então** o lint falha com mensagem clara indicando o campo ausente.

3. **Dado** um `platform.yaml` com `testing:` declarado, **quando** o pipeline de QA roda para esta plataforma, **então** ele usa o bloco como fonte autoritativa — não tenta inferir como iniciar a plataforma por heurística.

4. **Dado** um `platform.yaml` sem bloco `testing:`, **quando** o pipeline de QA roda, **então** o comportamento atual é preservado sem alterações (retrocompatibilidade garantida).

---

### US-02 — Pipeline inicia serviços automaticamente e valida saúde (P1)

O QA skill precisa iniciar os serviços da plataforma, aguardar que estejam prontos, e falhar com BLOCKER (não SKIP silencioso) se não conseguir.

**Por que P1**: Causa raiz dos 7 bugs escapados. Se os serviços nunca subiram durante o QA, nenhuma validação de runtime aconteceu. Este é o gap mais crítico a fechar.

**Teste Independente**: Pode ser testado rodando `qa_startup.py --start` em uma plataforma com `testing:` declarado e verificando que os health checks respondem antes do timeout.

**Cenários de Aceitação**:

1. **Dado** uma plataforma com `testing.startup.type: docker`, **quando** o QA skill inicia, **então** ele executa `docker compose up -d` no diretório correto e aguarda todos os health checks declarados responderem dentro do `ready_timeout`.

2. **Dado** que os serviços não sobem dentro do `ready_timeout`, **quando** o QA está esperando os health checks, **então** ele emite BLOCKER com mensagem clara: qual health check falhou, o output de erro de startup, e sugestão de diagnóstico.

3. **Dado** que os serviços já estão rodando quando o QA começa, **quando** o health check inicial responde imediatamente, **então** o startup é pulado sem tentar reiniciar.

4. **Dado** uma plataforma com `testing:` block e serviços **não** rodando, **quando** o QA skill tentaria anteriormente emitir `⏭️ L5: No server running — skipping`, **então** agora emite `❌ L5: BLOCKER — serviços inacessíveis apesar de testing.urls declarado`.

---

### US-03 — Pipeline valida variáveis de ambiente obrigatórias antes do deploy (P1)

Variáveis de ambiente ausentes são a causa mais comum de falhas silenciosas em runtime. O pipeline deve comparar o `.env.example` contra o `.env` real e bloquear se variáveis marcadas como `required_env` estiverem ausentes.

**Por que P1**: Três dos 7 bugs escapados (`JWT_SECRET`, `ADMIN_BOOTSTRAP_EMAIL`, `ADMIN_BOOTSTRAP_PASSWORD`) eram variáveis ausentes detectáveis por comparação simples de arquivos.

**Teste Independente**: Testável criando um `.env` sem `JWT_SECRET` e verificando que o pipeline emite BLOCKER antes de qualquer teste de runtime.

**Cenários de Aceitação**:

1. **Dado** uma plataforma com `required_env: [JWT_SECRET, DATABASE_URL]`, **quando** o `.env` real não contém `JWT_SECRET`, **então** o pipeline emite BLOCKER antes de qualquer layer de runtime: `❌ ENV: JWT_SECRET ausente — variável obrigatória declarada em testing.required_env`.

2. **Dado** todas as variáveis `required_env` presentes no `.env`, **quando** o env diff roda, **então** o pipeline emite apenas INFO listando variáveis presentes e segue para as próximas layers.

3. **Dado** uma variável presente em `.env.example` mas **não** em `required_env`, **quando** essa variável está ausente no `.env`, **então** o pipeline emite WARN (não BLOCKER): variável opcional ausente.

4. **Dado** uma plataforma sem `env_file` declarado no bloco `testing:`, **quando** o env diff seria executado, **então** a etapa é pulada silenciosamente sem erro.

---

### US-04 — Pipeline verifica reachability de todas as URLs declaradas (P2)

Após iniciar os serviços, o pipeline deve verificar que todas as URLs declaradas no `testing.urls` são acessíveis, retornam o status esperado, e contêm o conteúdo esperado.

**Por que P2**: Dois dos 7 bugs escapados eram de URL (timeout e IP errado). Depende de US-02 (serviços precisam estar rodando).

**Teste Independente**: Testável executando `qa_startup.py --validate-urls` com um serviço rodando e verificando que URLs acessíveis passam e inacessíveis geram BLOCKER.

**Cenários de Aceitação**:

1. **Dado** uma URL declarada como `expect_status: 200`, **quando** a URL retorna 404, **então** o pipeline emite BLOCKER: `❌ L5: http://localhost:3000/login retornou 404, esperado 200`.

2. **Dado** uma URL declarada com `expect_redirect: /login`, **quando** a URL retorna 200 sem redirecionar (ex: mostra placeholder), **então** o pipeline emite BLOCKER com screenshot do conteúdo recebido.

3. **Dado** uma URL `type: frontend` declarada, **quando** ela retorna 200 mas o body é HTML vazio ou placeholder padrão, **então** o pipeline emite WARN: `L5: http://localhost:3000 responde mas conteúdo parece placeholder`.

4. **Dado** uma URL inacessível (connection refused), **quando** o validate-urls roda, **então** BLOCKER com sugestão específica baseada no tipo: docker → checar `docker compose ps`, npm → checar se `npm run dev` está rodando.

---

### US-05 — Pipeline executa jornadas de usuário e reporta resultados (P2)

Jornadas de usuário críticas (login, fluxo principal, edge cases) devem ser executadas automaticamente pelo QA skill com steps declarados em `journeys.md`.

**Por que P2**: Dois dos 7 bugs (login não apareceu, root mostrava placeholder) só seriam detectados por execução de jornada — não por verificação de URL isolada.

**Teste Independente**: Testável criando um `journeys.md` com J-001 (happy path) e verificando que o QA skill executa cada step e reporta resultado.

**Cenários de Aceitação**:

1. **Dado** um `journeys.md` com J-001 marcado como `required: true`, **quando** o step de login falha (página não carrega formulário), **então** o pipeline emite BLOCKER: `❌ J-001 FAIL step 2 — formulário de login não encontrado`.

2. **Dado** uma jornada com step marcado como `screenshot: true`, **quando** o step é executado, **então** um screenshot é capturado e incluído no relatório de QA.

3. **Dado** todos os steps de J-001 passando, **quando** a jornada completa, **então** o pipeline reporta `✅ J-001 PASS (N steps)` com tempo de execução.

4. **Dado** Playwright MCP indisponível, **quando** uma jornada tem steps de browser, **então** os steps de browser são marcados como `SKIP — Playwright não disponível` e o restante da jornada (steps de API) continua.

---

### US-06 — speckit.analyze detecta rotas novas sem cobertura de QA (P3)

Após implementação de novas rotas/endpoints, o analyze pós-implement deve comparar as rotas encontradas no diff contra as URLs declaradas no `testing.urls` e emitir HIGH finding para rotas não cobertas.

**Por que P3**: Previne regressão futura: ao adicionar novas rotas sem atualizar `platform.yaml`, o QA silenciosamente deixa de cobri-las. A detecção automática fecha o loop.

**Teste Independente**: Testável adicionando uma rota FastAPI ao diff sem declarar em `testing.urls` e verificando que o analyze emite HIGH finding.

**Cenários de Aceitação**:

1. **Dado** um diff que adiciona `@router.get("/api/v1/channels")` em FastAPI, **quando** `/api/v1/channels` não está listado em `testing.urls`, **então** o analyze emite HIGH: "Rota nova não declarada em platform.yaml testing.urls — adicionar para cobertura de QA".

2. **Dado** um diff que adiciona arquivo `app/channels/page.tsx` em Next.js, **quando** a rota `/channels` não está em `testing.urls`, **então** o analyze emite HIGH para cobertura ausente.

3. **Dado** uma plataforma sem bloco `testing:`, **quando** o analyze pós-implement roda, **então** o URL coverage check é pulado silenciosamente sem erro.

---

### US-07 — Novas plataformas recebem scaffold de testing via blueprint (P3)

Ao criar uma nova plataforma via `madruga:blueprint`, o skill deve gerar automaticamente o bloco `testing:` skeleton no `platform.yaml`, um `journeys.md` estruturado, e opcionalmente o workflow de CI.

**Por que P3**: Reduz fricção de adoção — a configuração de testes é parte do scaffold inicial, não algo que o mantenedor precisa adicionar manualmente depois.

**Teste Independente**: Testável executando o blueprint para uma nova plataforma e verificando que o `platform.yaml` gerado inclui o bloco `testing:` preenchido com o tipo correto baseado na stack escolhida.

**Cenários de Aceitação**:

1. **Dado** uma nova plataforma com stack Docker escolhida no blueprint, **quando** o `platform.yaml` é gerado, **então** inclui `testing.startup.type: docker` com health checks placeholder e lista de URLs vazia estruturada.

2. **Dado** uma nova plataforma com `repo:` binding declarado, **quando** o blueprint gera os artefatos, **então** cria `.github/workflows/ci.yml` com jobs: lint, test, build.

3. **Dado** uma nova plataforma com stack npm escolhida, **quando** o `journeys.md` é gerado, **então** contém J-001 placeholder estruturado com steps vazios mas comentados com exemplos.

---

### Casos de Borda

- O que acontece quando `docker compose up -d` sobe mas um dos containers sai imediatamente? → O health check timeout deve detectar falha e o BLOCKER deve incluir o output de `docker compose logs` do container problemático.
- O que acontece quando os containers Docker já estão rodando mas com versão obsoleta (stale) e os health checks falham? → `qa_startup.py` emite WARN: "Serviços em execução mas health checks falharam. Containers podem estar obsoletos — execute `docker compose down && docker compose up -d` manualmente para reiniciar." O script NUNCA executa `docker compose down` automaticamente (irreversível — pode causar perda de dados de desenvolvimento).
- O que acontece quando `ready_timeout` expira mas metade dos health checks passa? → BLOCKER lista explicitamente quais health checks passaram e quais falharam para facilitar diagnóstico.
- O que acontece quando prosauai usa Tailscale IP e o QA roda localmente sem Tailscale? → `qa_startup.py` detecta falha de reachability e emite BLOCKER: "Configure port binding em `docker-compose.override.yml` — copiar de `docker-compose.override.example.yml`".
- O que acontece quando `journeys.md` declara um journey mas a plataforma não tem `startup.type` configurado? → Journey steps de API podem rodar (não dependem de startup), steps de browser são marcados como SKIP se serviços não acessíveis.
- O que acontece quando `validate-env` roda mas não existe `.env` (apenas `.env.example`)? → WARN informando que `.env` não foi encontrado, instruções sobre como criar a partir do `.env.example`.

---

## Requisitos

### Requisitos Funcionais

**Configuração de Testes:**

- **FR-001**: O sistema DEVE suportar um bloco `testing:` opcional em `platform.yaml` com campos: `startup` (type, command, ready_timeout), `health_checks`, `urls`, `required_env`, `env_file`, `journeys_file`.
- **FR-002**: O `platform_cli.py lint` DEVE validar o schema do bloco `testing:` quando presente e reportar campos inválidos ou ausentes.
- **FR-003**: O template Copier DEVE suportar geração do bloco `testing:` com valores padrão baseados na stack declarada.
- **FR-004**: Plataformas sem bloco `testing:` DEVEM manter comportamento atual do pipeline sem qualquer alteração — retrocompatibilidade total.

**Infraestrutura de Runtime:**

- **FR-005**: O sistema DEVE prover um script CLI (`qa_startup.py`) com operações independentes: `--start`, `--validate-env`, `--validate-urls`, `--parse-config`, `--full`.
- **FR-006**: O `qa_startup.py` DEVE suportar os tipos de startup: `docker`, `npm`, `make`, `venv`, `script`, `none` — com comandos padrão por tipo e override via `testing.startup.command`.
- **FR-007**: O `qa_startup.py` DEVE emitir saída JSON estruturada com `status` (ok/warn/blocker), `findings` (com level, message, detail), resultados de health checks, env diff e URLs.
- **FR-008**: O `qa_startup.py` DEVE receber `--platform <name>` para localizar o `platform.yaml` no repositório madruga.ai e `--cwd <path>` para executar comandos no diretório correto da plataforma.

**QA Skill — Comportamento:**

- **FR-009**: O QA skill DEVE executar env diff (comparação `required_env` vs `.env` real) como etapa pré-runtime, antes de qualquer layer L4/L5/L6, quando `env_file` está declarado.
- **FR-010**: Variáveis listadas em `required_env` ausentes no `.env` DEVEM gerar BLOCKER imediato — não WARN, não SKIP.
- **FR-011**: O QA skill DEVE iniciar os serviços da plataforma automaticamente quando `testing.startup.type != none` e `testing:` block está presente.
- **FR-012**: Falha de health check após `ready_timeout` DEVE gerar BLOCKER com output de diagnóstico — nunca SKIP silencioso.
- **FR-013**: O QA skill DEVE verificar reachability de todas as URLs declaradas em `testing.urls` e emitir BLOCKER para URLs inacessíveis ou com status code fora do esperado.
- **FR-014**: O QA skill DEVE capturar screenshot obrigatório para cada URL `type: frontend` quando Playwright MCP estiver disponível.
- **FR-015**: O QA skill DEVE executar jornadas declaradas em `journeys.md` quando o arquivo existir, reportando resultado por journey com BLOCKER para jornadas marcadas como `required: true` que falharem.

**Analyse Post-Implement:**

- **FR-016**: O `speckit.analyze` pós-implement DEVE comparar rotas novas detectadas no diff contra `testing.urls` declarado e emitir HIGH finding para rotas sem cobertura.
- **FR-017**: A detecção de rotas DEVE suportar: decorators FastAPI (`@router.get/post/put/delete/patch`) para Python; arquivos `page.tsx`/`page.ts` (rotas UI) e `route.ts`/`route.js` (rotas API App Router) em `app/` para Next.js; arquivos em `pages/` para Next.js Pages Router. Para frameworks não reconhecidos, o check DEVE emitir WARN: "Framework não reconhecido: URL coverage check disponível apenas para FastAPI e Next.js/React. Verificar cobertura manualmente." — nunca SKIP silencioso.

**Blueprint & Tasks:**

- **FR-018**: O `madruga:blueprint` DEVE gerar bloco `testing:` skeleton no `platform.yaml` com `startup.type` inferido da stack escolhida.
- **FR-019**: O `madruga:blueprint` DEVE gerar `platforms/<name>/testing/journeys.md` com J-001 placeholder estruturado para plataformas com `repo:` binding.
- **FR-020**: O `speckit.tasks` DEVE gerar `## Phase N: Deployment Smoke` como última fase obrigatória quando `testing:` block está presente no `platform.yaml` da plataforma.

- **FR-021**: O arquivo `journeys.md` DEVE usar formato machine-readable com blocos YAML por journey (parseáveis via pyyaml), seguindo o schema: `{id, title, required, steps: [{type, action, assert_status?, assert_redirect?, assert_contains?, screenshot?}]}`. O `qa_startup.py` DEVE parsear este formato para execução de steps `type: api`; o QA skill (LLM) usa o mesmo formato como contexto para steps `type: browser`.

- **FR-022**: O `qa_startup.py` NUNCA DEVE incluir valores de variáveis de ambiente na saída JSON ou em logs. Os arrays `env_present` e `env_missing` no output JSON DEVEM conter apenas nomes de variáveis (keys), nunca valores — prevenindo vazamento de segredos em artefatos de QA.

- **FR-023**: O critério de detecção de "placeholder HTML" para WARN em `validate-urls` DEVE ser determinístico: (1) body < 500 bytes após strip de whitespace; OU (2) body contém literais: "You need to enable JavaScript", "React App", "Vite + React", "Welcome to nginx", "It works!"; OU (3) `<body>` apenas com whitespace; OU (4) HTTP 200 com `Content-Type` não sendo `text/html` para URL `type: frontend`.

### Entidades-Chave

- **TestingManifest**: Configuração de testes declarada em `platform.yaml`. Atributos: tipo de startup, timeout de prontidão, lista de health checks, lista de URLs, variáveis de ambiente obrigatórias, arquivo de env, caminho para journeys.
- **HealthCheck**: Verificação de saúde de um serviço. Atributos: URL alvo, método HTTP, status esperado, conteúdo esperado no body (opcional), label descritivo.
- **URLEntry**: URL a ser validada pelo pipeline. Atributos: URL, tipo (api/frontend), label, status esperado, verificações de redirect ou conteúdo, flag de requer autenticação.
- **Journey**: Jornada de usuário a ser executada. Atributos: identificador (J-NNN), título, flag de obrigatória, lista de steps (cada step com tipo [`api`|`browser`], ação, assertion, flag de screenshot). Formato machine-readable: bloco YAML dentro do `journeys.md`, parseável por `qa_startup.py` via pyyaml. Exemplo: `{id: J-001, required: true, steps: [{type: api, action: "GET http://...", assert_status: 200}]}`.
- **StartupResult**: Resultado de inicialização de serviços. Atributos: status (ok/warn/blocker), lista de findings, estado de cada health check, log de erros de startup.

---

## Critérios de Sucesso

### Outcomes Mensuráveis

- **SC-001**: Os 7 bugs que escaparam do Epic 007 (prosauai — Admin Dashboard) são detectados automaticamente quando o pipeline de QA roda com `testing:` block configurado — taxa de detecção = 7/7 (100%).
- **SC-002**: Zero skips silenciosos de L5/L6 para plataformas com bloco `testing:` declarado — toda omissão de validação de runtime gera BLOCKER ou WARN explícito no relatório.
- **SC-003**: Tempo médio para diagnosticar falha de deployment reduzido: a mensagem de BLOCKER inclui diagnóstico suficiente para identificar a causa raiz sem abrir logs manualmente.
- **SC-004**: Novas plataformas criadas via blueprint incluem configuração de testes funcional sem etapas manuais adicionais — cobertura imediata de L4/L5 desde o primeiro QA.
- **SC-005**: `make test` permanece verde (0 falhas) após todas as 7 fases de implementação, incluindo os testes de `test_qa_startup.py`.
- **SC-006**: Todos os skills modificados passam no `skill-lint.py` após cada edição — zero regressões de sintaxe de skill.
- **SC-007**: Plataformas existentes sem bloco `testing:` (todos exceto madruga-ai e prosauai) mantêm comportamento atual inalterado — zero breaking changes.

---

## Assunções

- O `platform_cli.py` já consegue parsear e validar campos customizados em `platform.yaml` via schema extensível — apenas o novo bloco `testing:` precisa ser adicionado ao schema.
- O `qa_startup.py` tem acesso ao `REPO_ROOT` via variável de ambiente já utilizada por outros scripts do pipeline (padrão existente em `implement_remote.py`).
- O Playwright MCP pode estar indisponível em alguns ambientes (CI, execução remota) — as validações de browser são gracefully degraded para SKIP quando não disponível.
- O bloco `testing:` é puramente aditivo ao schema do `platform.yaml` — não há campos existentes que precisem ser modificados ou renomeados.
- Os testes de `test_qa_startup.py` usam mocks de `subprocess.run` e `urllib.request.urlopen` — não requerem serviços reais rodando para passar no `make test`.
- A modificação dos skill files (`.claude/commands/**`) via Edit/Write direto é válida no contexto de bare-lite dispatch, compensada pelo PostToolUse hook de lint automático.
- Este epic não toca `easter.py` nem `dag_executor.py` — o risco de auto-sabotagem do pipeline durante a execução do próprio epic é mínimo.
- Prosauai usa `docker-compose.override.yml` para expor portas — o `qa_startup.py` emite instrução clara quando as portas não estão expostas em localhost.
- O epic 024 (branch checkout isolation) já está merged — o padrão de execução de QA em plataformas externas com `--cwd` está estável.
- O formato YAML para `journeys.md` é parseável por pyyaml (já dependência) sem bibliotecas adicionais — steps `type: api` são executados deterministicamente pelo `qa_startup.py`; steps `type: browser` são interpretados pelo QA skill (LLM) via Playwright MCP.
- Ambientes de CI que executam `qa_startup.py` não devem ter acesso a valores de env vars sensíveis através de artefatos — apenas a presença/ausência é relevante para diagnóstico; nenhum valor aparece em output.
- Frameworks além de FastAPI e Next.js não são prioridade neste epic — o WARN informativo é suficiente para não bloquear times usando outras stacks.

---

handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada com 5 decisões críticas resolvidas: (1) journeys.md usa formato YAML machine-readable (FR-021); (2) qa_startup.py nunca expõe valores de env vars em output JSON (FR-022); (3) FR-017 atualizado com fallback WARN para frameworks desconhecidos e suporte a route.ts Next.js App Router; (4) FR-023 define critérios determinísticos para placeholder HTML; (5) docker stale containers → WARN sem auto-restart. 23 FRs totais (20 originais + 3 novos). Pronto para planejamento técnico."
  blockers: []
  confidence: Alta
  kill_criteria: "Se o bloco testing: em platform.yaml não puder ser validado pelo lint sem modificar o schema parser existente de forma breaking, ou se qa_startup.py precisar de dependências além de stdlib + pyyaml para suportar os tipos de startup declarados."
