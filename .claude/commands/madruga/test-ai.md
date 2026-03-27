---
description: Testa apps como QA humano — navega, observa e diagnostica bugs via Playwright
disable-model-invocation: true
argument-hint: "[URL] ou [explore <URL>] ou [setup] ou [heal]"
arguments:
  - name: target
    description: "URL, 'explore <URL>', 'setup [nome]', ou 'heal'"
    required: false
---

# Test AI — QA Humano via Playwright

Testa aplicacoes web como um QA humano faria: navega, interage, observa visualmente, diagnostica bugs e corrige. Pipeline completo automatico pos-feature.

## Uso

- `/test-ai` — Auto-detecta feature (git diff), gera cenarios, testa, corrige, reporta
- `/test-ai http://localhost:3000` — Testa URL especifica com pipeline completo
- `/test-ai explore http://localhost:3000` — Navegacao exploratoria livre (sem plano)
- `/test-ai setup` — Gera knowledge file para o projeto atual (interativo)
- `/test-ai setup resenhai-expo` — Gera knowledge com nome especifico
- `/test-ai heal` — Re-entra no heal loop para findings da sessao

## Pre-requisitos

- Playwright MCP configurado (browser_navigate, browser_snapshot, browser_take_screenshot, etc.)
- App rodando em URL acessivel (localhost ou staging)
- `.claude/knowledge/test-ai-template.md` — template para gerar knowledge de projeto
- `.claude/knowledge/test-ai-<projeto>.md` — (OPCIONAL) contexto especifico do projeto. Criado via `/test-ai setup`

---

## Instrucoes

### 0. Bootstrap e Auto-Detect

1. **Parse argumentos:**
   - `$ARGUMENTS` contem "setup": → Phase Setup
   - `$ARGUMENTS` contem "explore": → modo exploratorio, pular para Phase 3
   - `$ARGUMENTS` contem "heal": → Phase 4 (requer findings FAIL na sessao atual; se nao ha, informar "Rode `/test-ai` primeiro")
   - `$ARGUMENTS` contem URL (http/https): → usar como base_url
   - `$ARGUMENTS` vazio: → modo default (full pipeline)

2. **Buscar project knowledge (opcional):**
   ```
   Glob .claude/knowledge/test-ai-*.md
   ```
   - Filtrar: ignorar `test-ai-template.md` (eh o template)
   - Se encontrar arquivo(s): ler o mais relevante (match por nome do diretorio/repo atual)
   - Se NAO encontrar: funcionar sem — infere tudo do diff (zero config)

3. **Se project knowledge existe, extrair:**
   - `base_url` da tabela Environments
   - Credenciais da tabela Auth
   - Journeys P0-P2 como cenarios S1 para Phase 1
   - Screens & Pages para definir viewports por rota
   - Business Rules para informar julgamento no Phase 3g
   - Known Issues para filtrar dos findings

4. **Auto-detectar feature construida:**
   ```bash
   git log main..HEAD --oneline
   git diff main...HEAD
   ```

5. **Determinar base_url (se nao veio do knowledge):**
   - Se URL explicita nos args: usar diretamente
   - Inferir do diff: buscar `PORT`, `localhost`, `baseURL`, `NEXT_PUBLIC_`, `VITE_` no codigo
   - Se nao conseguir: **AskUserQuestion** — "Em qual URL a app esta rodando?"

---

### Phase Setup — Gerar Project Knowledge

**Trigger:** `/test-ai setup` ou `/test-ai setup <nome>`

1. **Ler template:** `.claude/knowledge/test-ai-template.md`

2. **Explorar projeto automaticamente:**
   - `package.json` / `requirements.txt` → stack, scripts (dev, start, seed)
   - `.env` / `.env.local` / `docker-compose.yml` → URLs, ports, credenciais
   - `README.md` → instrucoes de setup
   - Rotas/routes (buscar por router, routes, pages/) → telas do app
   - Estrutura de pastas → arquitetura

3. **Pre-preencher template** com o que inferiu (App, Environments, stack, rotas detectadas)

4. **AskUserQuestion** para completar secoes que precisam de input humano:
   ```
   Detectei o seguinte do projeto:
   - Stack: [inferido]
   - URL: [inferida]
   - Rotas: [lista]

   Preciso que voce complete:
   1. Credenciais de teste (email/senha por role)
   2. 3-5 jornadas criticas do app (ex: login → dashboard → criar pedido)
   3. Regras de negocio que devo saber (ex: preco minimo, limite de items)
   4. Bugs conhecidos que NAO devo reportar
   5. Viewport principal de cada tela (mobile/desktop/responsive)
   ```

5. **Salvar** em `.claude/knowledge/test-ai-<nome>.md`
   - Nome: kebab-case do projeto ou `$ARGUMENTS`

6. **Confirmar:** "Knowledge criado. Proximo `/test-ai` usara automaticamente."

---

### 1. Scenario Planning (automatico)

**NAO pede aprovacao — gera e segue.**

**Fontes de cenarios (em ordem de prioridade):**

1. **Journeys do knowledge** (se existir): P0-P2 viram cenarios S1/S2 automaticamente
2. **Screens do knowledge** (se existir): cada tela vira cenario de navegacao + viewport correto
3. **Git diff**: aplicar heuristicas abaixo para cenarios adicionais

**Heuristicas de cenario a partir do diff:**

| Pattern no diff | Cenarios gerados |
|-----------------|-----------------|
| Nova rota/pagina (route, page, view) | Happy path + 404 + unauthorized + estado vazio |
| Form/input (form, input, field, textarea) | Input valido + campos vazios + input invalido + submit erro |
| API endpoint (get, post, put, delete) | Sucesso + erro 4xx/5xx + loading state |
| Auth (login, logout, session, token) | Login valido + senha errada + sessao expirada |
| Lista/tabela (list, table, grid) | Vazio + poucos items + filtro/busca |
| CSS/responsive (media query, breakpoint) | Desktop 1280px + mobile 375px |
| Upload (file, upload, attachment) | Valido + muito grande + tipo invalido |
| Delete/remove (delete, remove, destroy) | Confirmar + cancelar exclusao |
| Modal/dialog (modal, dialog, popup) | Abrir + fechar + submit dentro |

**Prioridade automatica:**

| Tipo | Prioridade |
|------|-----------|
| Happy path de core feature | S1 |
| Tratamento de erro em jornada principal | S1 |
| Validacao de inputs | S2 |
| Estados vazios e edge cases | S2 |
| Responsividade | S3 |
| Cosmetico | S4 |

**Limitar a 15 cenarios max** — priorizar S1 e S2.

**Exibir no chat (informativo, NAO bloqueia):**
```
📋 Test Plan — [feature] (N cenarios: X S1, Y S2, Z S3)
| # | Jornada | Cenario | Prio |
Iniciando testes...
```

Se sem diff E sem knowledge: **AskUserQuestion** — "O que quer testar?"

---

### 2. DB/State Staging (smart auto)

**Com project knowledge:** usar credenciais e seed commands documentados. Zero perguntas.

**Sem project knowledge:**
- Auth: buscar em `.env`, `.env.local`, `docker-compose.yml`, `seed*.py`, `fixtures/`
  - Se encontrar: usar automaticamente
  - Se NAO encontrar: **AskUserQuestion** — credenciais de teste
- Seed: inferir comando ou perguntar

**Principio: so perguntar o que NAO da pra inferir.**

---

### 3. Execute Tests

**Regra snapshot vs screenshot:**
- Snapshot (accessibility tree) = SEMPRE primeiro. Rapido (2-5KB). Responde: elemento existe? texto? estado?
- Screenshot (vision) = SO quando: cenario Visual/Responsive, estado inesperado no snapshot, ou FAIL detectado

**Curiosidade proativa (OBRIGATORIO):**
Apos cada snapshot, analise TODOS os elementos interativos visiveis (botoes, links, tabs, menus, toggles, dropdowns, cards clicaveis). Para cada elemento que esteja dentro do escopo do teste:
- Se nunca foi testado → crie um mini-cenario on-the-fly e teste (click → snapshot → judge)
- Se parece relevante mas fora do escopo direto → registre como "descoberta" e teste rapidamente (1 click + snapshot)
- Se claramente fora do escopo (ex: link externo, footer generico) → ignore

**Principio:** Aja como um QA curioso, nao um script mecanico. Se voce ve 5 botoes na tela e so 1 esta no plano, teste os outros 4 tambem se fizerem sentido. Pergunte-se: "O que acontece se eu clicar aqui?" — e clique. Registre findings adicionais com tag `[EXPLORATORIO]`.

Para cada cenario:

#### 3a. Navigate
```
mcp__playwright__browser_navigate → base_url + rota
```
**Viewport** (ordem de prioridade):
1. Se knowledge tem Screens: usar viewport da tabela. Mobile-first → 375x812. Responsive → testar AMBOS.
2. Se cenario tem viewport especifico: `mcp__playwright__browser_resize`
3. Default: 1280x720

#### 3b. Snapshot ANTES (condicional)
Tirar snapshot ANTES somente se o cenario envolve transicao de estado (form submit, click que muda pagina). Para cenarios "pagina carrega corretamente", o snapshot DEPOIS eh suficiente.
```
mcp__playwright__browser_snapshot
```

#### 3c. Act
- `browser_fill_form` — preencher formularios
- `browser_click` — botoes, links (ref do snapshot)
- `browser_type` — campos especificos
- `browser_select_option` — dropdowns
- `browser_wait_for` — apos acoes async
- `browser_handle_dialog` — dialogs inesperados

#### 3d. Snapshot DEPOIS
```
mcp__playwright__browser_snapshot
```
Comparar: novos elementos? Sumiram? Texto mudou?

#### 3e. Verificar erros (condicional)
Checar console/network SO quando: snapshot DEPOIS mostra estado inesperado, cenario envolve API calls, ou FAIL suspeito.
```
mcp__playwright__browser_console_messages
mcp__playwright__browser_network_requests
```

#### 3f. Screenshot (CONDICIONAL)
Tirar SO se: cenario Visual/Responsive, snapshot inesperado, ou FAIL.
```
mcp__playwright__browser_take_screenshot → fullPage: true
```

**Analisar com vision usando template adequado:**

**Layout:** Verificar: layout quebrado? Secoes visiveis? Texto legivel? Cores consistentes? Espacamento?

**Form (pos-acao):** Verificar: feedback erro/sucesso? Validacao posicionada? Estado correto? Botoes corretos?

**Data display:** Verificar: dados presentes? Sem NaN/undefined/null? Alinhamento? Headers? Estado vazio tratado?

**Responsive:** Verificar: empilha corretamente? Texto legivel sem zoom? Touch targets 44px? Menu acessivel? Sem overflow?

**Antes/Depois:** Mudanca esperada aconteceu? Mudanca inesperada? Feedback visual adequado?

#### 3g. Judge

**Severity:**
- **S1 Critical** — Bloqueia uso. Crash, data loss, core quebrado, security (impede completar jornada)
- **S2 High** — Degrada experiencia. Workaround possivel mas ruim (completa com friccao)
- **S3 Medium** — Bug menor. Core OK mas inesperado (percebe mas nao impacta)
- **S4 Low** — Cosmetico. Spacing, cor, typo (so QA percebe)

**Status:**
- **PASS** — comportamento correto
- **FAIL (S1-S4)** — desvio do esperado
- **WARN** — funcional OK mas subotimo (console warnings, performance)
- **SKIP** — nao testavel (timeout, auth wall, feature ausente)

**Com knowledge:** business rules informam julgamento. Known issues sao filtrados (nao viram FAIL).

#### Progresso no chat
```
✅ #1 Login happy path — PASS
❌ #2 Login senha errada — FAIL (S2) — sem mensagem de erro
⚠️ #3 Dashboard mobile — WARN — console: React key warning
⏭️ #4 Upload arquivo — SKIP — feature ausente
```

#### 3h. Curiosidade entre cenarios
Apos completar um cenario, ANTES de ir pro proximo:
1. Revisar snapshot atual — ha elementos interativos nao cobertos pelo plano?
2. Para cada elemento relevante nao testado:
   - Click → snapshot → judge (mini-cenario, ~30s)
   - Se FAIL: registrar como finding com tag `[EXPLORATORIO]` e severity normal
   - Se PASS: registrar como `✅ [EXPLORATORIO] #N.X: [descricao] — PASS`
3. Limitar a 3 mini-cenarios exploratorios por cenario principal (evitar explosao)
4. Se descobrir area inteira nao mapeada (ex: modal com form complexo), criar cenarios S2 adicionais

#### Modo exploratorio (`explore`)
Se modo `explore` ativo (Phase 0 roteou direto pra ca):
- NAO ha cenarios pre-definidos. Navegar organicamente pelo snapshot.
- **Curiosidade MAXIMA**: clicar em TUDO que parece interativo. Cada pagina = inventario completo de elementos.
- Explorar: menu, forms, botoes, paginas internas, tabs, toggles, dropdowns, cards.
- Para cada elemento: click → observar → julgar. Nao pular nada visivel.
- Criar cenarios on-the-fly baseado no que ve.
- Parar apos 15-20 cenarios ou cobertura completa de elementos visiveis.

---

### 4. Heal Loop

**Entra AUTOMATICAMENTE** se ha FAILs. Corrige sem pedir permissao.

Para cada FAIL (S1 primeiro):

#### 4a. Analisar root cause

| Pattern | Causa provavel | Onde buscar |
|---------|---------------|-------------|
| "undefined"/"null" renderizado | Campo faltando na API ou prop | Handler → serializer → component |
| Pagina em branco | Rota nao registrada ou guard | Router → middleware → component |
| Console 401/403 | Token expirado, permissao | Auth middleware → token → headers |
| Console CORS | Backend config | CORS allowed origins |
| Console 404 API | Endpoint ausente ou URL errada | API routes → URL no frontend |
| Form sem efeito | Handler nao wired | onClick/onSubmit no component |
| Loading infinito | Promise nao resolve | Async handler → error handling |
| React key warning | Key faltando em .map() | Component com lista |
| Redirect loop | Guard sempre true | Auth guard → redirect logic |

#### 4b. Localizar codigo
Grep + Read nos arquivos relevantes (rota, componente, handler).
**Ler ANTES de modificar.**

#### 4c. Aplicar fix
Edit tool. Informar: `🔧 Corrigindo #N: [descricao] em [file:line]`

#### 4d. Retest
Re-executar SO o cenario falho.

#### 4e. Judge
- PASS → `🔧 #N HEALED (X iter) — fix em [file:line]`
- FAIL + iter<5 → volta para 4a
- FAIL + iter>=5 → `❌ #N UNRESOLVED apos 5 tentativas`

---

### 5. Report

```markdown
## QA Report — [feature/URL]
**Data:** DD/MM/YYYY | **Branch:** [branch] | **URL:** [url]
**Cenarios:** N | **Taxa sucesso:** X% (PASS + HEALED / total)

### Resumo
| Status | Count |
|--------|-------|
| ✅ PASS | N |
| 🔧 HEALED | N |
| ⚠️ WARN | N |
| ❌ UNRESOLVED | N |
| ⏭️ SKIP | N |

### Findings
#### [S?] #N: [Jornada] — [Cenario]
**Esperado:** ... **Observado:** ... **Evidencia:** ... **Status:** HEALED/UNRESOLVED

### Arquivos Alterados
| Arquivo | Linha | Mudanca |

### Licoes Aprendidas
```

---

### 6. Persist

1. Criar dir se nao existir: `obsidian-vault/4_Documents/qa-reports/`
2. Salvar em `obsidian-vault/4_Documents/qa-reports/YYYY-MM-DD-<slug>.md` com frontmatter:
   ```yaml
   ---
   type: qa-report
   date: YYYY-MM-DD
   feature: "[nome]"
   url: "[url]"
   branch: "[branch]"
   scenarios_total: N
   pass_rate: "X%"
   ---
   ```
3. Informar: `📄 Report salvo: obsidian-vault/4_Documents/qa-reports/YYYY-MM-DD-<slug>.md`

---

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Browser nao instalado | `browser_install`, retry |
| URL nao responde | Informar: "App nao rodando. Iniciar servidor?" |
| Cenario timeout (>30s) | SKIP + screenshot + console |
| App crash | Console + screenshot, S1 FAIL, reload |
| Dialog/popup inesperado | `browser_handle_dialog` dismiss |
| Flaky (fail→pass no retest) | WARN tag "flaky" |
| Pagina vazia no snapshot | `browser_wait_for` 2s, retry, SKIP se persistir |

## Exemplo — Uso tipico pos-feature

```
> /test-ai

📋 Test Plan — Dashboard (8 cenarios: 3 S1, 3 S2, 2 S3)

✅ #1 Dashboard carrega — PASS
❌ #2 Filtro por data — FAIL (S2)
✅ #3 Paginacao — PASS
⚠️ #4 Mobile 375px — WARN — botao cortado

🔧 Corrigindo #2: handler faltando em Dashboard.tsx:89
🔧 #2 HEALED (1 iter)

## QA Report — Dashboard
Taxa sucesso: 100% (7 PASS + 1 HEALED) | WARN: 1
📄 Report salvo: obsidian-vault/4_Documents/qa-reports/2026-03-23-dashboard.md
```
