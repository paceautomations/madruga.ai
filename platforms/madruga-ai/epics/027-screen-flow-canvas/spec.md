# Especificação de Feature: Screen Flow Canvas

**Feature Branch**: `epic/madruga-ai/027-screen-flow-canvas`
**Criado**: 2026-05-05
**Status**: Draft
**Epic**: 027 — Screen Flow Canvas

---

## Contexto

L1 do madruga produz documentos densos (`vision`, `solution-overview`, `process`) mas não tem artefato visual que mostre **como o produto se parece** e **como as telas se conectam**. Stakeholder não-técnico lê 80KB de markdown sem formar mental model do que vai ser entregue. Plataformas brownfield (resenhai-expo) já têm telas construídas mas a documentação não captura nada disso.

A consequência é drift permanente entre documentação e realidade. Hoje, alguém querendo entender o fluxo de uma plataforma precisa: (1) ler 3 markdowns longos, (2) abrir o app real (se já existe), (3) inferir as transições. Não há nenhum lugar onde "qual botão leva pra qual tela" esteja explícito e versionado.

A solução precisa funcionar em três modos sem ramificar a infraestrutura: greenfield (tudo wireframe mock), brownfield (screenshot real onde a tela existe), e plataformas headless/tooling onde o conceito de "tela" não se aplica (opt-out explícito). resenhai-expo é o pilot único; madruga-ai e prosauai entram com `enabled: false` e validam o caminho de opt-out.

---

## Clarifications

### Session 2026-05-05

- Q: Lifecycle de captura inclui apenas `pending` e `captured` — qual estado representa falha (timeout, auth expirada, app crash)? → A: Adicionar `failed` ao enum, com `failure: {reason, occurred_at, retry_count}`. Renderer mostra badge "FALHOU" e tooltip; demais telas seguem normalmente.
- Q: Existe limite máximo de telas por `screen-flow.yaml` (escalabilidade do canvas e do ELK build-time)? → A: Hard reject em 100 telas no validator; warn em 50. ELK timeout 30s no build; >5s emite warn. Multi-arquivo por bounded context fica fora do escopo do v1.
- Q: Política de PII em screenshots commitados ao repo (LGPD/privacy)? → A: Test user DEVE ser sintético (nome demo, email `demo+playwright@<domain>`, zero PII real). `mock_routes` mascaram endpoints com dados de outros usuários. Validator exige `capture.test_user_marker` declarado no `platform.yaml` para auditoria.
- Q: Capture script — política de retry/timeout quando staging falha ou demora? → A: 3 retries com backoff exponencial (1s/2s/4s) por tela, timeout 30s no `page.goto`, total do workflow 30min. Telas que esgotam retries recebem `status: failed` e workflow exits 1 (CI alarm), mas YAML é committed com mix `captured`/`failed`.
- Q: `screen.id` — qual charset/formato é válido (impacto em filenames, URLs, refs YAML)? → A: Regex `^[a-z][a-z0-9_]{0,63}$` — lowercase, começa com letra, máximo 64 chars, apenas underscore como separador. Validator rejeita IDs fora do padrão.

---

## Cenários de Usuário & Testes

### US-01 — Stakeholder não-técnico vê o fluxo de telas como canvas navegável (P1)

O stakeholder de negócio (PM, fundador, cliente) abre o portal Astro de uma plataforma e encontra uma aba **Screens** que mostra, em um único canvas Figma-like, todas as telas do produto e como o usuário transita entre elas. Cada tela tem chrome de device (mobile bezel ou desktop chrome), badge indicando se é wireframe ou screenshot real, e arestas estilizadas (sucesso/erro/neutro/modal) explicando a transição.

**Por que P1**: É o entregável visível ao stakeholder e a razão de existir do epic. Sem o canvas renderizado, todo o resto é infraestrutura sem valor demonstrável. Substitui leitura linear de markdown por mental model espacial em segundos.

**Teste Independente**: Pode ser validado abrindo `/<platform>/screens` no portal local com uma fixture YAML de 8 telas e verificando que o canvas renderiza, é navegável (pan/zoom), e os tipos de aresta são visualmente distinguíveis. Entrega valor mesmo antes da captura real estar pronta — fixture com wireframes já comunica o fluxo.

**Cenários de Aceitação**:

1. **Dado** que uma plataforma tem `business/screen-flow.yaml` válido com 8+ telas, **quando** o stakeholder acessa `/<platform>/screens`, **então** o canvas renderiza todas as telas posicionadas via ELK (build-time), com pan e zoom funcionando a 60fps em desktop padrão.

2. **Dado** que o canvas está aberto, **quando** o stakeholder clica em uma aresta com label, **então** o label é legível, a aresta é estilizada conforme `style` (success=verde sólido, error=vermelho tracejado, neutral=cinza pontilhado, modal=azul sólido grosso), e o pattern visual é distinguível mesmo em color-blind simulator (deuteranopia + protanopia).

3. **Dado** que uma plataforma tem `screen_flow.enabled: false` em `platform.yaml`, **quando** o stakeholder navega no portal, **então** a aba **Screens** não aparece na sidebar dessa plataforma — opt-out invisível.

4. **Dado** que o portal Starlight está em modo escuro (`[data-theme="dark"]`), **quando** o canvas é renderizado, **então** todas as cores respeitam tokens CSS variáveis e o canvas permanece legível — nenhum elemento hardcoded em `bg-white text-black`.

---

### US-02 — Skill `madruga:business-screen-flow` gera YAML ancorado em `business/process.md` (P1)

O autor de documentação executa `/madruga:business-screen-flow <platform>` durante o pipeline L1. A skill lê `business/process.md` da plataforma como input obrigatório, propõe screens DERIVADAS das user journeys já documentadas, e produz `business/screen-flow.yaml` válido contra schema `screen-flow.schema.json`. Greenfield sem `process.md` resulta em rejeição clara da skill.

**Por que P1**: Sem a skill, a YAML precisa ser escrita à mão sem ancoragem na spec do produto. A skill garante que screens sejam consequência das jornadas documentadas, não invenção isolada — preserva consistência cross-platform.

**Teste Independente**: Testável rodando `/madruga:business-screen-flow resenhai-expo` em uma plataforma com `process.md` populado e validando que o YAML gerado passa no `screen_flow_validator.py`. Sem dependência de captura ou renderer.

**Cenários de Aceitação**:

1. **Dado** que `platforms/<name>/business/process.md` existe e descreve N user journeys, **quando** a skill é executada, **então** ela lê o arquivo, propõe um conjunto inicial de screens derivadas das jornadas e grava `business/screen-flow.yaml` com `schema_version: 1`.

2. **Dado** que `process.md` não existe na plataforma alvo, **quando** a skill é invocada, **então** ela falha graciosamente com mensagem clara: "business/process.md não encontrado — execute /madruga:business-process antes" — não tenta inventar screens do zero.

3. **Dado** que o YAML gerado contém um `body.type` fora do vocabulário fechado de 10 (`heading, text, input, button, link, list, card, image, divider, badge`), **quando** o `screen_flow_validator.py` é executado, **então** retorna erro com line number e o tipo inválido — antes do hook de post-save aceitar o arquivo.

4. **Dado** que o YAML gerado declara `flows[].from` ou `to` referenciando `screen.id` inexistente, **quando** o validator roda, **então** rejeita com mensagem listando IDs declarados disponíveis.

5. **Dado** que a skill é executada em plataforma com `screen_flow.enabled: false` em `platform.yaml`, **quando** invocada, **então** sai imediatamente com mensagem "Plataforma opted-out: <skip_reason>" sem gerar arquivo.

---

### US-03 — Mantenedor declara opt-out explícito da feature em `platform.yaml` (P1)

O mantenedor de uma plataforma headless/tooling (madruga-ai) ou em fase precoce (prosauai admin frontend) precisa declarar que a feature screen-flow não se aplica e não verá a aba Screens, sem comprometer o pipeline L1.

**Por que P1**: Sem opt-out válido, o nó L1 vira mandatório de fato e quebra plataformas onde "tela" não faz sentido. O bloco `screen_flow` em `platform.yaml` é o contrato que torna a feature genuinamente opcional.

**Teste Independente**: Testável adicionando `screen_flow.enabled: false` ao `platforms/madruga-ai/platform.yaml` e verificando que (a) `platform_cli.py lint` aceita, (b) o nó DAG `business-screen-flow` é marcado como completed/skipped sem rodar a skill, (c) a aba Screens não aparece no portal.

**Cenários de Aceitação**:

1. **Dado** um `platform.yaml` com `screen_flow.enabled: false` e `skip_reason: "<texto>"`, **quando** `platform_cli.py lint <name>` roda, **então** o schema é validado com sucesso e `skip_reason` é exigido (lint falha se `enabled: false` sem `skip_reason`).

2. **Dado** uma plataforma opted-out, **quando** o pipeline L1 é executado em modo dispatch, **então** o nó `business-screen-flow` é resolvido como skipped sem invocar a skill, e nós downstream (`tech-research`) seguem normalmente.

3. **Dado** uma plataforma opted-out, **quando** o portal Astro faz build, **então** a entry "Screens" não é incluída em `routeData.ts` para essa plataforma e a rota `/<platform>/screens` não é gerada.

4. **Dado** um `platform.yaml` com `screen_flow.enabled: true`, **quando** o lint roda, **então** o schema obrigatório de `capture` é validado: `base_url`, `device_profile`, `auth`, `determinism`, `path_rules` precisam estar presentes ou o lint falha.

---

### US-04 — Pipeline captura screenshots reais determinísticos via Playwright (P2)

O autor da plataforma pilot (resenhai-expo) dispara `gh workflow run capture-screens.yml -f platform=resenhai-expo`. O workflow GitHub Actions roda em runner Linux, usa Playwright contra `https://dev.resenhai.com` (Expo Web staging permanente), aplica determinism layer (`addInitScript` + `addStyleTag` + service-worker cleanup + mock routes), captura PNGs por tela conforme YAML, salva em `business/shots/` via Git LFS, atualiza YAML com `captured_at` e `app_version`, e abre auto-commit.

**Por que P2**: É a entrega que materializa screenshots reais (badge `WEB BUILD`). Sem ela, o canvas nunca sai de wireframe mock pra brownfield. Mas o canvas com fixture já entrega valor (US-01), por isso P2.

**Teste Independente**: Testável rodando `python3 .specify/scripts/capture/screen_capture.py resenhai-expo` localmente após configurar `RESENHAI_TEST_EMAIL`/`RESENHAI_TEST_PASSWORD` em env. Validação binária: 2 runs back-to-back devem produzir PNGs com md5 idêntico em pelo menos 80% das telas.

**Cenários de Aceitação**:

1. **Dado** que `screen_flow.capture` está populado com `base_url`, `device_profile: iphone-15`, `auth.storage_state_path` válido, **quando** o capture script roda, **então** cada tela declarada no YAML é capturada conforme seu `route` ou `entrypoint`, salva em `business/shots/<screen-id>.png`, e o YAML é atualizado com `captured_at: <ISO8601>` e `status: captured`.

2. **Dado** dois runs consecutivos do mesmo capture script contra a mesma `base_url`, **quando** `md5sum business/shots/*.png` é comparado, **então** ≥80% das telas têm md5 idêntico (incluindo telas autenticadas com Service Worker cleanup ativo).

3. **Dado** uma plataforma com `clear_service_workers: true` em determinism config, **quando** o capture script processa cada tela, **então** executa `await ctx.clearCookies()` e `navigator.serviceWorker.unregister()` ANTES de cada `page.goto` — verificável via log estruturado.

4. **Dado** que um PNG capturado excede 500KB, **quando** o pre-commit hook valida arquivos `.png` em `business/shots/`, **então** rejeita o commit com mensagem indicando arquivo, tamanho real, e instrução de recompressão.

5. **Dado** dois disparos simultâneos do workflow `capture-screens.yml` para `platform=resenhai-expo`, **quando** os runs concorrem, **então** o bloco `concurrency: { group: "capture-${{ matrix.platform }}", cancel-in-progress: false }` enfileira o segundo, evitando race em writes ao YAML.

6. **Dado** que `mock_routes` declara `{ match: "**/api/notifications/unread", body: { count: 0 } }`, **quando** o capture script renderiza uma tela autenticada, **então** a request casada é interceptada e respondida com o body declarado — sem chamada à API real.

---

### US-05 — Stakeholder navega entre telas clicando em hotspots numerados (P2)

Em uma tela com `flows` declarados, hotspots aparecem como badges numerados (1, 2, 3) sobre o componente clicável referenciado por `testid`. Click no hotspot anima a aresta correspondente sendo desenhada e em seguida `fitView` centraliza a câmera na tela destino com easing. Tecla `H` toggla visibilidade dos hotspots quando autor quer screenshot "limpo".

**Por que P2**: Discoverability do fluxo dentro do canvas. Sem isso, o usuário precisa identificar transições só pelas arestas externas. Hotspots tornam cada tela auto-documentada. P2 porque US-01 já entrega o canvas básico — hotspots são incremental.

**Teste Independente**: Testável carregando fixture com 3 telas conectadas por hotspots no Playwright + jest-image-snapshot, simulando click no badge "1" da primeira tela, e verificando que a câmera centra na tela destino dentro de 600ms.

**Cenários de Aceitação**:

1. **Dado** uma tela com `flows: [{from: "<this>", to: "home", on: "<body-id-with-testid>"}]`, **quando** o canvas renderiza essa tela, **então** um badge numerado `1` aparece sobre o componente correspondente, com outline 1px tracejado e aria-label descrevendo a ação ("Vai para tela home").

2. **Dado** que hotspots estão visíveis (default), **quando** o usuário pressiona tecla `H` com foco no canvas, **então** todos os hotspots são escondidos; pressionar `H` novamente os reexibe.

3. **Dado** que o usuário clica em um hotspot numerado, **quando** o evento dispara, **então** (a) a aresta correspondente é animada (~250ms), (b) `fitView` é chamado com easing pra tela destino (~350ms), (c) total <700ms.

4. **Dado** que o usuário usa apenas teclado, **quando** Tab move foco entre nodes do canvas, **então** Enter aciona o primeiro hotspot focado da tela atual — keyboard navigation funcional sem mouse.

5. **Dado** que coords do hotspot estão normalizadas 0-1 no YAML, **quando** o profile do device muda (iphone-15 → desktop), **então** o hotspot é reposicionado proporcionalmente sem necessidade de recapturar.

---

### US-06 — Reverse-reconcile detecta drift e marca telas como pending (P2)

Quando o autor faz commit em arquivo de tela do app (ex: `app/(auth)/login.tsx` no resenhai-expo) e roda `madruga:reverse-reconcile resenhai-expo`, o aggregate lê `screen_flow.capture.path_rules` da plataforma, mapeia o arquivo modificado para `screen.id`, e reescreve `screen-flow.yaml` setando `capture.status: pending` na entry correspondente. Portal renderiza badge "AGUARDANDO" até o próximo capture run.

**Por que P2**: Fecha o loop de drift entre código real e screenshot armazenado. Sem isso, screenshots ficam stale e a documentação volta ao problema original. P2 porque depende de US-04 estar funcional pra ter screenshots a invalidar.

**Teste Independente**: Testável fazendo commit em `app/(auth)/login.tsx` em um clone do resenhai-expo, rodando `madruga:reverse-reconcile resenhai-expo`, e verificando que `business/screen-flow.yaml` agora tem `screens[id=login].capture.status: pending`.

**Cenários de Aceitação**:

1. **Dado** que `path_rules` declara `{pattern: 'app/\\(auth\\)/(\\w+)\\.tsx', screen_id_template: '{1}'}`, **quando** um commit toca `app/(auth)/login.tsx`, **então** `reverse_reconcile_aggregate.py` mapeia para `screen.id = "login"` e enfileira patch JSON.

2. **Dado** que `screen_flow_mark_pending.py` recebe o patch, **quando** executa, **então** reescreve o YAML preservando ordem e comentários, modificando apenas `screens[id=login].capture.status` de `captured` para `pending`.

3. **Dado** que `path_rules` não casa com nenhum padrão para um arquivo modificado, **quando** o aggregate roda, **então** o arquivo segue o fluxo normal de drift detection (cai em `_DOC_CANDIDATE_RULES` ou continua sem patch específico de screen-flow).

4. **Dado** uma plataforma com `screen_flow.enabled: false`, **quando** `reverse-reconcile` roda, **então** o módulo de screen-flow é skipped silenciosamente — nenhum patch de screen-flow é gerado.

---

### US-07 — Drift por commit de doc-self-edit não dispara cascata (P3)

Commits que tocam apenas arquivos sob `platforms/<p>/{business,engineering,decisions,planning}/` são classificados como `doc-self-edit` e auto-reconciliados sem invocar LLM nem gerar patches de screen-flow. Evita o loop circular "patch screen-flow.yaml baseado em commit que editou screen-flow.yaml".

**Por que P3**: Robustez do pipeline. Sem essa regra, edits manuais ao YAML disparariam cascata absurda. Já existe lógica equivalente em reverse-reconcile (Decision-context citado na pitch); este US apenas garante que screen-flow respeita a regra.

**Teste Independente**: Testável fazendo commit que altera apenas `platforms/resenhai-expo/business/screen-flow.yaml`, rodando `madruga:reverse-reconcile resenhai-expo`, e verificando que nenhum patch é gerado e o commit é marcado como reconciled automaticamente.

**Cenários de Aceitação**:

1. **Dado** um commit que toca apenas `platforms/<p>/business/screen-flow.yaml`, **quando** o classify aggregate roda, **então** o commit recebe label `doc-self-edit` e é marcado como reconciled sem ler o conteúdo do diff.

2. **Dado** um commit que toca `platforms/<p>/business/screen-flow.yaml` E também `app/(auth)/login.tsx`, **quando** o aggregate roda, **então** o classifier separa: o doc-edit é auto-reconciled, o app-edit gera patch normal de screen-flow.

---

### US-08 — Bundle budget e a11y são gates obrigatórios no CI (P3)

CI valida via `size-limit` que a rota `/<platform>/screens/*` não excede orçamento definido (esperado 700-900KB ungz). Falha de build se exceder. Edges e nodes têm `aria-label`, keyboard nav funcional, edges distinguíveis em color-blind simulator.

**Por que P3**: Garantias de longo prazo. P3 porque US-01 já entrega rendering aceitável; este US protege regressão futura.

**Teste Independente**: Testável adicionando dep desnecessária ao `ScreenFlowCanvas.tsx` que infle bundle, rodando `npm run build` no portal, e verificando que `size-limit` falha com erro indicando tamanho atual vs budget.

**Cenários de Aceitação**:

1. **Dado** que `size-limit.config.json` define budget para `/screens/*`, **quando** o CI roda em PR que infle bundle além do limite, **então** o job falha com mensagem clara: "Bundle excedeu budget: <atual> vs <limite>".

2. **Dado** que outras rotas (`/<platform>/index.astro`) têm budget separado, **quando** o screen-flow infla apenas a rota `/screens/*`, **então** outras rotas mantêm seus tamanhos atuais validados pelo gate.

3. **Dado** que cada `ScreenNode` é renderizado, **quando** screen reader navega o canvas, **então** lê `aria-label` descritivo (ex: "Tela login: campos de email e senha, botão Entrar").

4. **Dado** simulação de deuteranopia (color-blind simulator), **quando** o canvas renderiza arestas success+error+neutral+modal, **então** os 4 estilos permanecem distinguíveis por pattern (sólido/tracejado/pontilhado) além da cor.

---

### Casos de Borda

- **YAML com ciclo entre screens** (A→B→A): ELK falha em produzir layout limpo. → Validator detecta ciclo no DAG de flows e força autor a declarar `position` manual nos nós envolvidos via campo opcional `meta.position: {x, y}`.
- **Plataforma com `screen_flow.enabled: true` mas sem `path_rules` declarado**: → Lint falha — `path_rules` é obrigatório quando enabled.
- **Test user expirado/deletado em staging do resenhai-expo**: → `e2e/auth.setup.ts` falha em produzir `storageState`; capture script aborta com BLOCKER claro pedindo regeneração de credenciais.
- **Service Worker cleanup falha** (browser não suporta `serviceWorker.unregister`): → Capture script registra warn estruturado mas não aborta — captura prossegue, autor revisa md5 manualmente.
- **YAML sem `schema_version`**: → Validator rejeita imediatamente. Mensagem: "Campo obrigatório `schema_version` ausente — adicione `schema_version: 1` no topo".
- **YAML com `schema_version: 99` (versão desconhecida)**: → Validator rejeita com lista de versões suportadas e link para `migrate_v1_to_v<N>.py` quando aplicável.
- **Hotspot referencia `testid` que não existe no DOM capturado**: → Capture script registra warn estruturado e omite o hotspot do PNG; renderer usa coords normalizadas declaradas no YAML como fallback (badge ainda aparece, posicionado por coords).
- **PNG capturado >500KB**: → Pre-commit hook rejeita; autor escolhe entre (a) recortar viewport, (b) reduzir qualidade JPEG-style via Playwright `quality`, (c) revisar mock routes pra remover imagens decorativas pesadas.
- **Bandwidth Git LFS aproxima de 800MB/mês** (gatilho de revisão Decision #22): → Workflow CI emite warn em PR; revisão manual decide entre `git lfs prune` mensal ou migração para Vercel Blob.
- **Build do portal sem nenhum `screen-flow.yaml` populado** (greenfield total): → Aba Screens não aparece em nenhuma plataforma; fixture `?fixture=true` em dev permite testar renderer sem YAML real.
- **Skill `madruga:business-screen-flow` invocada quando `screen_flow.enabled: false`**: → Sai com mensagem amigável citando `skip_reason` da plataforma; não cria arquivo, não retorna erro.
- **Reverse-reconcile encontra commit `doc-self-edit` que toca exclusivamente `screen-flow.yaml`**: → Auto-reconciliado sem cascata; nenhum patch gerado.
- **Captura falha repetidamente (3 retries esgotados)**: → Tela recebe `status: failed` + bloco `failure: {reason, occurred_at, retry_count, last_error_message}`. Renderer mostra badge "FALHOU" com tooltip exibindo `failure.reason`. Workflow exits 1 (CI alarm), mas YAML é committed normalmente. Outras telas seguem.
- **YAML excede 100 telas**: → Validator rejeita imediatamente com mensagem orientando split em múltiplos `screen-flow*.yaml` por bounded context (work futuro). Warn em 50 alerta antes do hard limit.
- **ELK layout demora >30s no build**: → Build do portal aborta com erro estruturado pedindo simplificação (reduzir flows, dividir YAML, ou declarar `position` manual em telas-chave).
- **Plataforma com `enabled: true` mas sem `test_user_marker` declarado**: → Lint falha exigindo o campo. Captura não roda até o autor declarar qual test user é usado (auditabilidade).
- **`screen.id` com hyphens, CamelCase, ou unicode**: → Validator rejeita com mensagem citando charset permitido `^[a-z][a-z0-9_]{0,63}$` e exemplos válidos.
- **`mock_routes` não cobre endpoint que retorna PII de outros usuários**: → Captura roda mas screenshots podem conter dados reais visíveis. Mitigação operacional: review manual da primeira captura de cada tela autenticada antes de habilitar `auto-commit` em produção; `test_user_marker` registra qual conta foi usada para auditoria posterior.

---

## Requisitos

### Requisitos Funcionais

**Schema e Validator:**

- **FR-001**: O sistema DEVE definir `screen-flow.schema.json` com vocabulário fechado: 10 component types (`heading, text, input, button, link, list, card, image, divider, badge`), 4 edge styles (`success, error, neutral, modal`), 6 badge values (`WIREFRAME, AGUARDANDO, FALHOU, WEB BUILD v<x>, iOS v<x>, WEB v<x>`), e capture states (`pending, captured, failed`).
- **FR-002**: O `screen-flow.yaml` DEVE conter `schema_version: 1` no topo do arquivo. O validator DEVE rejeitar YAML sem o campo OU com versão desconhecida — mensagem inclui versões suportadas.
- **FR-003**: O `screen_flow_validator.py` DEVE rejeitar `body.type` fora do vocabulário, refs `from`/`to` em `flows` apontando para `screen.id` inexistente, IDs duplicados, e `path_rules` com sintaxe regex inválida.
- **FR-004**: O hook PostToolUse em `platforms/**/business/screen-flow.yaml` DEVE invocar o validator e bloquear gravação inválida.
- **FR-048**: O validator DEVE rejeitar `screen.id` que não case com regex `^[a-z][a-z0-9_]{0,63}$` — lowercase, começa com letra, máximo 64 chars, apenas underscore como separador (sem hyphens, sem CamelCase, sem unicode). Mesma regra aplica a `body.id` e `flow.on` para consistência.
- **FR-049**: O validator DEVE aplicar limites de escalabilidade: warn se `len(screens) > 50` (mensagem orientando split por bounded context), hard reject se `len(screens) > 100`. ELK layout build-time DEVE ter timeout de 30s — se exceder, abort do build com erro claro. Layout que tome >5s DEVE emitir warn estruturado nos logs do build.

**Configuração `platform.yaml`:**

- **FR-005**: O sistema DEVE estender o schema de `platform.yaml` com bloco opcional `screen_flow`: `{enabled: bool, skip_reason?: str, capture?: {base_url, serve?, device_profile, auth, determinism, expo_web?, path_rules}}`.
- **FR-006**: Quando `screen_flow.enabled: false`, o lint DEVE exigir `skip_reason` populado (não vazio) e rejeitar `capture` populado.
- **FR-007**: Quando `screen_flow.enabled: true`, o lint DEVE exigir `capture.base_url`, `capture.device_profile`, `capture.auth`, `capture.determinism`, e `capture.path_rules` populados.
- **FR-008**: O bloco `capture.auth` DEVE suportar tipo `storage_state` com campos `setup_command`, `storage_state_path`, `test_user_env_prefix` — credenciais sempre via env vars com prefixo declarado, nunca em arquivo.
- **FR-009**: O bloco `capture.determinism` DEVE suportar `freeze_time`, `random_seed`, `disable_animations`, `clear_service_workers`, `clear_cookies_between_screens`, `mock_routes: [{match, body|status}]`.
- **FR-010**: O bloco `capture.path_rules` DEVE ser lista de `{pattern: regex, screen_id_template: str}` per-platform — sem hardcoding em Python.

**Skill `madruga:business-screen-flow`:**

- **FR-011**: A skill DEVE ser registrada como nó L1 opcional (`optional: true`) com `depends_on: [business-process]`, layer `business`, gate `human`.
- **FR-012**: A skill DEVE ler `platforms/<name>/business/process.md` como input obrigatório. Se ausente, DEVE falhar com mensagem direcionando a executar `/madruga:business-process` antes — não inventar screens do zero.
- **FR-013**: A skill DEVE propor screens DERIVADAS das user journeys descritas em `process.md`, deixando autor humano validar e ajustar antes de gravar o YAML.
- **FR-014**: Quando invocada em plataforma com `screen_flow.enabled: false`, a skill DEVE sair imediatamente citando `skip_reason` — sem gerar arquivo.
- **FR-015**: A skill PODE opcionalmente parsear arquivos `e2e/tests/**/*.spec.ts` da plataforma alvo e sugerir `testid` disponíveis no momento de gerar `flows[].on`.

**Renderer (Portal):**

- **FR-016**: O portal DEVE renderizar a rota `/<platform>/screens` apenas quando `business/screen-flow.yaml` existe e `screen_flow.enabled: true` — entry "Screens" condicional em `routeData.ts`.
- **FR-017**: O renderer DEVE usar `@xyflow/react v12` + ELK build-time + SSG via `renderToStaticMarkup`. Layout pré-computado, hidratação com `client:visible`. Zero `elkjs` no bundle do client.
- **FR-018**: O renderer DEVE aplicar flags fixos: `nodesDraggable=false`, `nodesConnectable=false`, `elementsSelectable`, `onlyRenderVisibleElements`. Custom nodes memoizados por `id + selected`.
- **FR-019**: O renderer DEVE prover keyboard navigation: Tab move foco entre nodes, Enter aciona primeiro hotspot focado.
- **FR-020**: Cada `ScreenNode` DEVE ter `aria-label` descritivo (ex: "Tela <id>: <conteúdo principal>").
- **FR-021**: As 4 edge styles DEVEM ser distinguíveis por pattern adicional (sólido/tracejado/pontilhado) além da cor — testável em color-blind simulator.

**Wireframe + Chrome:**

- **FR-022**: Wireframes DEVEM usar paleta limitada (6 tons cinza + 1 accent suave default azul-acinzentado), tipografia distinta de "app real" (`Caveat` ou `Architects Daughter` via Google Fonts preloaded), border-radius padronizado, sem sombras pesadas, sem gradientes.
- **FR-023**: Chrome de device DEVE ser minimal: moldura com border-radius + label discreto (ex: `iPhone 15 / 393×852`). NÃO incluir status bar fake (sem hora "9:41", sem bateria).

**Hotspots:**

- **FR-024**: Hotspots DEVEM ser visíveis por default com badge numerado (1, 2, 3...) + outline 1px tracejado.
- **FR-025**: Tecla `H` (com foco no canvas) DEVE toggar visibilidade dos hotspots; estado é local à sessão (não persiste).
- **FR-026**: Click em hotspot DEVE animar a aresta correspondente (~250ms) e em seguida `fitView` na tela destino com easing (~350ms), total <700ms.
- **FR-027**: Coords de hotspot DEVEM ser normalizadas 0-1 no YAML — independentes de resolução/profile.
- **FR-028**: O capture script DEVE usar `boundingBox` de `[data-testid="<id>"]` para popular coords reais quando capturando brownfield. `testid` referencia testIDs JÁ EXISTENTES no app (sem nova convenção).

**Captura:**

- **FR-029**: O sistema DEVE prover `screen_capture.ts` (Playwright) com profiles `iphone-15` (393×852) e `desktop` (1440×900). Único runner Linux no GitHub Actions; sem macOS, sem Maestro.
- **FR-030**: O capture script DEVE aplicar determinism layer: `addInitScript` (Date freeze, Math.random seed, animate stub), `addStyleTag` (transitions/animations off), e mocks declarados em `mock_routes`.
- **FR-031**: Quando `clear_service_workers: true`, o capture script DEVE executar `await ctx.clearCookies()` e `navigator.serviceWorker.getRegistrations().then(rs => Promise.all(rs.map(r => r.unregister())))` ANTES de cada `page.goto`.
- **FR-032**: O capture script DEVE atualizar o YAML com `captured_at: <ISO8601>`, `app_version: <git-sha>`, `status: captured` para cada tela capturada com sucesso.
- **FR-033**: 2 runs back-to-back do capture script DEVEM produzir PNGs byte-idênticos (md5 match) em ≥80% das telas, incluindo telas autenticadas.
- **FR-034**: PNGs DEVEM ser armazenados em `business/shots/<screen-id>.png` via Git LFS. Pre-commit hook em Python DEVE rejeitar PNG >500KB.
- **FR-035**: O workflow `capture-screens.yml` DEVE declarar `concurrency: { group: "capture-${{ matrix.platform }}", cancel-in-progress: false }` para evitar race em writes ao YAML.
- **FR-045**: O capture script DEVE aplicar política de retry: 3 retries com backoff exponencial (1s, 2s, 4s) por tela quando `page.goto` falhar (timeout, network error, navegação interrompida). Timeout `page.goto` = 30s. Total timeout do workflow = 30 minutos. Telas que esgotam retries recebem `status: failed` + bloco `failure: {reason, occurred_at, retry_count, last_error_message}` no YAML.
- **FR-046**: Quando ao menos uma tela termina com `status: failed` ao final do run, o workflow DEVE exit 1 (CI alarm), MAS o YAML atualizado DEVE ser committed mesmo com mix `captured`/`failed` — autor decide próxima ação (re-run, ajustar mock, regenerar storageState).
- **FR-047**: O `platform.yaml.screen_flow.capture` DEVE incluir campo obrigatório `test_user_marker: <string>` quando `enabled: true`, identificando o test user designado (ex: `demo+playwright@resenhai.com`). Lint rejeita `enabled: true` sem o campo. Política operacional: test user usa apenas dados sintéticos (nomes, emails, conteúdo) — sem PII real. `mock_routes` DEVEM mascarar endpoints que retornam dados de outros usuários (listas de amigos, feeds, etc.) para impedir vazamento acidental em screenshots commitados.

**Drift Detection:**

- **FR-036**: O `reverse_reconcile_aggregate.py` DEVE ler `screen_flow.capture.path_rules` da plataforma e mapear arquivos modificados para `screen.id` via regex declarativo per-platform.
- **FR-037**: Quando um arquivo casa com `path_rules`, o aggregate DEVE enfileirar patch JSON para `screen_flow_mark_pending.py` setando `screens[id=<resolved>].capture.status: pending`.
- **FR-038**: Commits classificados como `doc-self-edit` (100% dos arquivos sob `platforms/<p>/{business|engineering|decisions|planning}/`) DEVEM ser auto-reconciliados sem invocar o módulo screen-flow.
- **FR-039**: Plataformas com `screen_flow.enabled: false` DEVEM ser skipped silenciosamente pelo módulo screen-flow do reverse-reconcile.

**CI Gates:**

- **FR-040**: O CI DEVE validar via `size-limit` que a rota `/<platform>/screens/*` permanece dentro de orçamento definido após baseline da fase 2 (esperado 700-900KB ungz). Build falha se exceder.
- **FR-041**: O CI DEVE validar que outras rotas (`/<platform>/index.astro`) mantêm tamanhos atuais — bundle do screen-flow não deve vazar.

**Test Pyramid:**

- **FR-042**: Test pyramid DEVE conter 4 layers: (a) Unit pytest para validator (≥30 casos cobrindo rejection paths, schema_version desconhecido, path_rules sintaxe inválida); (b) Component (React Testing Library + jest) para `ScreenNode` 3 estados, `ActionEdge` 4 styles, `Hotspot` numerado; (c) Visual (Playwright + jest-image-snapshot) com fixture de 8 telas, toleração 1px diff; (d) E2E (1 spec) integrando capture→commit→render contra fixture mock.

**A11y + Dark Mode:**

- **FR-043**: Todos os elementos visuais DEVEM usar tokens CSS variáveis (ex: `--screen-bg`, `--screen-fg`, `--screen-accent`, `--edge-success`) — proibido literais como `bg-white text-black` no código fonte.
- **FR-044**: Os tokens CSS DEVEM respeitar `[data-theme="dark"]` do Starlight — alternar tema do portal mantém canvas legível.

### Entidades-Chave

- **ScreenFlow**: Documento YAML por plataforma. Atributos: `schema_version`, `meta` (device, capture_profile, layout_direction), lista de `screens`, lista de `flows`.
- **Screen**: Tela individual. Atributos: `id` (charset `^[a-z][a-z0-9_]{0,63}$`), `title`, `status` (pending/captured/failed), `body` (lista de componentes do vocabulário), `image?` (path PNG quando captured), `position?` (override manual de layout), `meta` (capture_profile, route, entrypoint), `failure?` (preenchido quando status=failed).
- **BodyComponent**: Componente do corpo de uma tela. Atributos: `type` (1 dos 10 do vocabulário), `id`, `text?`, `testid?` (referência a testID existente no app, usado para hotspot coords).
- **Edge / Flow**: Aresta entre telas. Atributos: `from` (screen.id), `to` (screen.id), `on` (body component.id que dispara), `style` (success/error/neutral/modal), `label?`.
- **Hotspot**: Marcador visual sobre tela capturada. Atributos: coords normalizadas 0-1 (`x, y, w, h`), referência ao flow correspondente, badge numerado.
- **CaptureProfile**: Configuração de viewport e captura. Atributos: nome (iphone-15, desktop), dimensões (width × height), device descriptor (Playwright preset).
- **PlatformScreenFlowConfig**: Bloco em `platform.yaml`. Atributos: `enabled`, `skip_reason?`, `capture` (base_url, serve, device_profile, auth, determinism, expo_web, path_rules).
- **PathRule**: Regra de mapeamento arquivo→screen. Atributos: `pattern` (regex), `screen_id_template` (string com `{N}` para grupos capturados).
- **DeterminismConfig**: Configuração para captura reprodutível. Atributos: `freeze_time`, `random_seed`, `disable_animations`, `clear_service_workers`, `clear_cookies_between_screens`, `mock_routes`.
- **CaptureRecord**: Metadata de captura. Atributos: `captured_at` (ISO8601), `app_version` (git sha), `status` (pending/captured/failed), `image` (path PNG).
- **CaptureFailure**: Metadata de falha de captura. Atributos: `reason` (enum: `timeout, auth_expired, network_error, app_crash, sw_cleanup_failed, mock_route_unmatched, unknown`), `occurred_at` (ISO8601), `retry_count` (int), `last_error_message?` (string truncado a 500 chars).

---

## Critérios de Sucesso

### Outcomes Mensuráveis

- **SC-001**: resenhai-expo (pilot único) mostra ≥3 telas reais via Expo Web staging com badge "WEB BUILD v\<x\>" no canvas portal — `/resenhai-expo/screens` renderiza sem erro.
- **SC-002**: madruga-ai e prosauai validam o caminho de opt-out — `screen_flow.enabled: false` + `skip_reason` documentado, aba Screens NÃO aparece na sidebar dessas plataformas.
- **SC-003**: 2 runs back-to-back de `gh workflow run capture-screens.yml -f platform=resenhai-expo` produzem PNGs byte-idênticos (md5 match) em ≥80% das telas — incluindo telas autenticadas com Service Worker cleanup ativo.
- **SC-004**: Click em hotspot numerado dentro de tela centra câmera na tela destino com easing animation em <700ms (medido via Performance API). Tecla `H` toggla visibilidade dos hotspots em <50ms.
- **SC-005**: Bundle da rota `/<platform>/screens/*` permanece dentro do orçamento `size-limit` definido após baseline da fase 2 (esperado 700-900KB ungz). CI falha em PR que exceda.
- **SC-006**: Outras rotas do portal (`/<platform>/index.astro`) mantêm tamanho atual após introdução do screen-flow — `size-limit` valida zero vazamento.
- **SC-007**: Portal alterna entre `[data-theme="light"]` e `[data-theme="dark"]` e canvas permanece visualmente correto em todas as variantes (Chrome, Wireframe, 4 edges, hotspots, badges) — verificável via screenshot test em ambos os temas.
- **SC-008**: Edges são distinguíveis em color-blind simulator (deuteranopia + protanopia) — verificável via teste visual com filtros aplicados.
- **SC-009**: Test pyramid 4 layers verdes em `make test`: (a) ≥30 casos unit do validator com 100% cobertura de rejection paths; (b) component tests para ScreenNode/ActionEdge/Hotspot; (c) visual snapshot do canvas com fixture; (d) E2E capture→commit→render.
- **SC-010**: Validator rejeita YAML sem `schema_version` ou com versão desconhecida — verificável via 2+ casos de unit test.
- **SC-011**: Drift detection: commit em `app/(auth)/login.tsx` (resenhai-expo) faz `screens[id=login].capture.status` virar `pending` no próximo `madruga:reverse-reconcile resenhai-expo` — verificável end-to-end.
- **SC-012**: 2 dispatches simultâneos do workflow `capture-screens.yml` para mesma plataforma NÃO corrompem o YAML — concurrency block validado via teste de integração.
- **SC-013**: Quota Git LFS da org paceautomations permanece ≤30% do plano Free (storage ≤150MB, bandwidth mensal ≤300MB) após 30 dias do epic em produção — eixo bandwidth é o crítico.
- **SC-014**: Skill `madruga:business-screen-flow` executada em plataforma sem `business/process.md` falha com mensagem clara direcionando o autor a gerar `process.md` primeiro — taxa de erro ambíguo = 0%.
- **SC-015**: ADR-NNN é registrada com 24 decisões 1-way-door extraídas da pitch.md — uma fonte autoritativa para reconciliação futura.
- **SC-016**: Knowledge file `.claude/knowledge/screen-flow-vocabulary.md` cobre 10 components + 4 edges + 5 badges com exemplos YAML — referência única para autores e renderer.
- **SC-017**: `madruga:judge` review aprovado com 4 personas (sem BLOCKERs após heal loop).
- **SC-018**: Invariante "zero edits externos" — nenhum commit em `paceautomations/resenhai-expo` (ou outro repo bound) é necessário para o epic shippar. Captura é black-box contra staging existente.
- **SC-019**: Estado `failed` é first-class — verificável injetando timeout artificial em uma tela, rodando o capture, observando que (a) workflow exits 1, (b) YAML tem `status: failed` + bloco `failure` populado para essa tela, (c) outras telas terminam com `status: captured`, (d) renderer mostra badge "FALHOU" com tooltip do `failure.reason`.
- **SC-020**: Limite de escalabilidade enforced — verificável criando YAML com 101 screens dummies; validator rejeita imediatamente. YAML com 51 screens dummies emite warn mas passa.
- **SC-021**: Charset de `screen.id` enforced — verificável via 5+ casos de unit test do validator: rejeita `Login`, `welcome-screen`, `home_v2`, `tela_início`, `1home`; aceita `welcome`, `login`, `home`, `auth_login`, `screen_a`.
- **SC-022**: Política de PII verificável — `platform.yaml.screen_flow.capture.test_user_marker` é obrigatório quando `enabled: true` (lint test); ao menos 1 `mock_route` declarado em resenhai-expo mascara endpoint com risco de PII de outros usuários.

---

## Assunções

- O portal Astro Starlight existente já suporta entries condicionais em `routeData.ts` baseadas em presença de arquivo — não requer mudanças no core do portal além de leitura de `screen-flow.yaml` durante build.
- `@xyflow/react v12` já é dependência do portal (usada em pipeline DAG visualization). Adicionar `elkjs ^0.9` como devDependency build-time é puramente aditivo — não afeta bundle client.
- `business/process.md` existe nas plataformas que vão habilitar `screen_flow` (resenhai-expo confirmado; greenfield futuro deve gerar process.md primeiro como pré-requisito).
- `https://dev.resenhai.com` é staging permanente do Expo Web em produção e estará disponível durante a janela do epic — validado em 2026-05-05.
- Test user `RESENHAI_TEST_EMAIL` no Supabase staging do resenhai-expo permanece válido durante toda a janela do epic; `e2e/auth.setup.ts` já existe e produz `storageState`.
- O plano Free Git LFS da org paceautomations (500MB storage / 1GB bandwidth/mês) tem headroom suficiente para o epic — uso atual = 0 objetos LFS.
- `react-native-web 0.21.2` no resenhai-expo expõe `testID` como `data-testid` no DOM — confirmado pela presença de 54 usos de `testID=` no codebase do app.
- Service Worker cleanup via `navigator.serviceWorker.getRegistrations()` é suportado em Chromium (Playwright default browser) — pattern padrão da plataforma web.
- O campo `image` no YAML aceita path local relativo ao repo (LFS) hoje, e pode ser estendido para URL remota (Vercel Blob) sem breaking change futuro.
- Reverse-reconcile já lê `platform.yaml` durante o aggregate phase — adicionar leitura de `screen_flow.capture.path_rules` é puramente aditivo, não requer reescrita.
- O workflow `capture-screens.yml` rodará em runner Linux ubuntu-latest com Playwright já provisionado via `npx playwright install chromium` — sem necessidade de macOS runner.
- Coords normalizadas 0-1 são suficientes para reposicionar hotspots quando profile muda — mudança de aspect ratio (mobile→desktop) requer recapturar mas é caso raro (default por plataforma).
- A tecla `H` para toggle de hotspots não conflita com keybindings existentes do Starlight ou Astro — verificável via inspeção de event listeners globais.
- Bundle budget concreto será definido após fase 2 fechar baseline (esperado 700-900KB ungz para `/screens/*`) — substitui claim aspiracional "TTI <1.5s" por gate medível via `size-limit`.
- Plataformas opted-out (`enabled: false`) NÃO recebem geração de fixture — fixture é exclusiva de dev local via `?fixture=true` em `[platform]/screens.astro`.
- 1-way-door da fase 1 (vocabulário fechado de 10 components + 4 edges) está locked — PRs questionando vocab durante implementação são rejeitados sem discussão.
- Test user designado em `capture.test_user_marker` é mantido pelo time da plataforma com dados sintéticos — premissa operacional, não enforced pelo schema (schema garante presença do marker; conteúdo do user é responsabilidade humana).
- Limite hard de 100 screens por `screen-flow.yaml` é folgado para v1: plataformas reais (resenhai-expo) têm ~30 telas; 100 cobre projeções de 3-4 anos de crescimento sem necessidade de split. Quando uma plataforma se aproximar do limite, work futuro introduz multi-arquivo por bounded context.
- Backoff exponencial 1s/2s/4s com 3 retries cobre falhas transientes (network blips, cold-start lento). Falhas determinísticas (auth expirada, mock route mismatch) falham rápido nos 3 retries e ficam visíveis via `failure.reason`.

---

handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada com 5 ambiguidades resolvidas: (1) lifecycle de captura ganhou estado `failed` com bloco `failure` first-class, (2) escalabilidade limitada a 100 telas hard / 50 warn, ELK timeout 30s, (3) política de PII via `test_user_marker` obrigatório + mock_routes para mascaramento, (4) retry policy 3x com backoff 1s/2s/4s e timeouts 30s/30min, (5) `screen.id` charset locked em `^[a-z][a-z0-9_]{0,63}$`. Total: 8 USs, 49 FRs (4 novos), 22 SCs (4 novos), entidades Screen+CaptureRecord estendidas, CaptureFailure introduzida. 24 decisões 1-way-door da pitch.md preservadas. Pronto para detalhamento técnico em /speckit.plan."
  blockers: []
  confidence: Alta
  kill_criteria: "Se @xyflow/react v12 + ELK build-time não conseguir entregar canvas a 60fps com 30+ telas em desktop padrão, OU se determinism via Playwright addInitScript+route+storageState produzir <80% de PNGs byte-idênticos em telas autenticadas após 5 runs, OU se Git LFS Free quota se mostrar insuficiente (>80% de 500MB storage ou >80% de 1GB bandwidth/mês após 30 dias), OU se a política de PII via test_user sintético + mock_routes não for operacionalmente sustentável (auditoria do compliance review identifica vazamentos em mais de 1 tela autenticada)."
