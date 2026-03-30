# Madruga.AI — Comprehensive Codebase Review

**Data**: 2026-03-30
**Revisores**: Equipe emulada (PM, Designer, Engenheiros, Arquiteto, Business Owner)
**Escopo**: End-to-end — Python scripts, portal frontend, pipeline skills, templates, database, testes

---

## Resumo Executivo

O madruga.ai é um sistema de documentação de arquitetura bem estruturado, com pipeline automatizado de 24 skills, portal Astro/Starlight, e SQLite como state store. O portal **compila com sucesso** (77 páginas, 34s build). O Python tem **2 ruff warnings** (variáveis não utilizadas). **1 teste falha** (containers.md removido do template) + **1 teste que nunca pode falhar** (assert capturado por except). Existem **inconsistências de integridade no DAG** e **FTS5 sem sanitização de input**.

### Scorecard

| Área | Status | Score |
|------|--------|-------|
| Portal Build | OK (77 pages) | 9/10 |
| Python Lint (ruff) | 2 warnings | 8/10 |
| Template Tests | 1 FAIL + 1 broken test (16 pass) | 6/10 |
| Platform Lint | 1 warn (fulano context-map) | 8/10 |
| Pipeline DAG Integrity | 2 DB violations + 1 YAML mismatch | 5/10 |
| Skill Contract Compliance | Persona missing in 13 L1 skills | 7/10 |
| DB Schema & Migrations | OK (5 migrations) | 9/10 |
| Security | FTS5 input unsanitized, symlink bypass | 7/10 |
| Frontend UX | LikeC4 broken in dev, 404 links, mobile overflow | 5/10 |
| Code Quality | Solid, minor DRY issues | 8/10 |
| **Overall** | | **7/10** |

---

## 1. BLOCKERS (Quebram funcionalidade)

### 1.1 [B1] Teste `test_auto_markers_present` falha — `containers.md` removido do template

**Arquivo**: `.specify/templates/platform/tests/test_template.py:60`
**Problema**: O template Jinja2 `containers.md.jinja` foi deletado (visível no git status: `D .specify/templates/platform/template/engineering/containers.md.jinja`), mas o teste ainda tenta ler `engineering/containers.md` no scaffold gerado.
**Impacto**: `pytest` falha. Qualquer CI bloqueado.
**Fix**: Atualizar o teste para remover a assertiva sobre `containers.md`, ou restaurar o template.

### 1.2 [B2] DAG Integrity Violation — `adr=done` mas `tech-research=pending`

**Arquivo**: `.pipeline/madruga.db` (tabela `pipeline_nodes`)
**Problema**: Para ambas as plataformas (fulano e madruga-ai):
- `tech-research` está como `pending`
- `adr` está como `done`
- Mas no DAG, `adr` depende de `tech-research`

Isso significa que o estado do DB não reflete a realidade. O `reseed_from_filesystem` marca nós como `done` baseado na existência de arquivos, sem verificar integridade de dependências.
**Impacto**: Dashboard mostra estados inconsistentes. Skills podem pular prerequisites.
**Fix**: Adicionar validação de integridade no `seed_from_filesystem()` — ao marcar um nó como `done`, verificar se todas as dependências também estão `done`. Alternativa: adicionar um comando `platform.py validate-dag <name>` que detecte e corrija inconsistências.

### 1.3 [B3] Fulano faltando arquivos que o lint espera

**Problema**: `platforms/fulano/engineering/context-map.md` e `platforms/fulano/business/process.md` não existem, mas o lint os espera (e o DAG tem `context-map=pending` enquanto `containers=done`, que depende de `domain-model` mas não de `context-map`).
**Impacto**: O lint reporta `[warn]`, não bloqueia. Mas a ausência de `context-map.md` é inconsistente com `containers=done` se o portal sidebar referencia este arquivo.

### 1.4 [B4] madruga-ai `platform.yaml` missing `analyze-post` node + wrong `reconcile` dependency

**Arquivo**: `platforms/madruga-ai/platform.yaml` (epic_cycle section)
**Problema**: Comparando com fulano (correto, 11 nós), madruga-ai tem apenas **10 nós** no epic_cycle:
- Falta o nó `analyze-post` entre `implement` e `verify`
- `reconcile.depends` aponta para `["verify"]` em vez de `["qa"]`

Isso viola a regra do pipeline: "qa runs before reconcile because its heal loop may modify code".
**Impacto**: Para a plataforma madruga-ai, o post-implementation consistency check é pulado, e reconcile pode rodar antes do QA.
**Fix**: Adicionar `analyze-post` node e corrigir `reconcile.depends` para `["qa"]`.

### 1.5 [B5] FTS5 SQL injection via user-supplied query

**Arquivo**: `.specify/scripts/db.py:944-961` (função `search_decisions`) e `:1205` (`search_memories`)
**Problema**: O parâmetro `query` é passado diretamente como FTS5 `MATCH` value. FTS5 suporta operadores booleanos (`AND`, `OR`, `NOT`, `NEAR`), filtros de coluna (`title:foo`). Uma query malformada (e.g., aspas desbalanceadas) causa `sqlite3.OperationalError` sem try/except. O fallback LIKE não escapa `%` e `_`.
**Impacto**: Crash em buscas com caracteres especiais. Não é exploitable para data exfiltration (FTS5 é read-only), mas é UX quebrada.
**Fix**: Wrap FTS5 MATCH em try/except, sanitizar/escapar caracteres especiais na query.

### 1.6 [B6] Test `test_kebab_case_validation` nunca pode falhar

**Arquivo**: `.specify/templates/platform/tests/test_template.py:75-103`
**Problema**: O teste usa `except Exception` que captura tanto erros do copier quanto o próprio `AssertionError` na linha 100. Se o copier aceitar um nome inválido, o `assert` que deveria falhar é capturado pelo except e o teste passa silenciosamente.
**Fix**: Usar `except (subprocess.CalledProcessError, FileNotFoundError)` em vez de `except Exception`.

### 1.7 [B7] LikeC4 diagrams broken in dev mode — `jsxDEV is not a function`

**Arquivo**: `portal/src/components/viewers/LikeC4Diagram.tsx`
**Problema**: TODAS as páginas de diagrama LikeC4 (`/landscape/`, `/containers/`, `/context-map/`, `/bc/*`, `/business-flow/`) dão erro `TypeError: jsxDEV is not a function`. Causa: mismatch de JSX runtime entre os virtual modules `likec4:react/*` e a versão do React (19.2.4) configurada no portal. O LikeC4 Vite plugin emite JSX que espera o dev runtime (`jsxDEV`), mas o bundle usa o production runtime (`jsx`).
**Impacto**: Páginas de diagrama ficam **completamente em branco** em dev mode. O error boundary não captura porque o erro ocorre durante a hydration inicial.
**Fix**: Investigar compatibilidade entre `likec4` 1.51.0 e React 19. Possíveis soluções: pin React 18, ou configurar `react.jsxRuntime` no Vite config.

### 1.8 [B8] Dashboard links para rotas inexistentes (404s)

**Arquivo**: `portal/src/pages/[platform]/dashboard.astro:181-183` e `portal/src/components/dashboard/PipelineDAG.tsx:110-111`
**Problema**: A lógica de URL do dashboard faz strip de `.md` e `.likec4` do `outputs[0]` para construir links, mas nem todos os outputs mapeiam para rotas do portal:
- `Platform Setup` → `/{platform}/platform.yaml/` → **404** (YAML não é página)
- `Containers` → `/{platform}/model/platform/` → **404** (deveria linkar para `/containers/`)
**Fix**: Criar mapa output→URL no dashboard (e.g., `platform.yaml` → dashboard, `model/platform.likec4` → `/containers/`, `model/views.likec4` → `/landscape/`).

### 1.9 [B9] Missing `qa-template.md` knowledge file

**Arquivo**: `.claude/commands/madruga/qa.md:99` referencia `.claude/knowledge/qa-template.md`
**Problema**: O arquivo não existe. A skill QA diz "if exists" então degrada gracefully, mas o setup flow perde valor sem o template.
**Fix**: Criar o arquivo ou remover a referência.

---

## 2. WARNINGS (Funciona, mas com risco)

### 2.1 [W1] Variáveis não utilizadas em `platform.py`

**Arquivo**: `.specify/scripts/platform.py:550,581`
**Problema**: `yaml_nodes` e `epic_cycle_nodes` são definidas mas nunca usadas (ruff F841).
**Fix**: Remover as duas linhas.

### 2.2 [W2] Dashboard depende de arquivo estático `pipeline-status.json`

**Arquivo**: `portal/src/pages/[platform]/dashboard.astro:19`
**Problema**: O dashboard importa `../../data/pipeline-status.json` que precisa ser gerado manualmente (`platform.py status --all --json > portal/src/data/pipeline-status.json`). Se o arquivo não existe ou está desatualizado, o dashboard mostra "Sem dados de pipeline".
**Fix**: Automatizar a geração do JSON como parte do `npm run dev` ou `npm run build` via script no `package.json`:
```json
"prebuild": "python3 ../.specify/scripts/platform.py status --all --json > src/data/pipeline-status.json",
"predev": "python3 ../.specify/scripts/platform.py status --all --json > src/data/pipeline-status.json"
```

### 2.3 [W3] Portal sem `site` no `astro.config.mjs` — sitemap falha

**Arquivo**: `portal/astro.config.mjs`
**Problema**: Build warning: `The Sitemap integration requires the 'site' astro.config option. Skipping.`
**Fix**: Adicionar `site: 'https://madruga.ai'` (ou a URL real) no `defineConfig`.

### 2.4 [W4] `_split_sql_statements` é frágil para SQL complexo

**Arquivo**: `.specify/scripts/db.py:146-176`
**Problema**: O parser de SQL para migrations usa split por `;` com handling de triggers, mas não trata strings quoted que contêm `;`, multi-line strings, ou blocos `BEGIN...END` fora de triggers (e.g., CTEs complexas). Para as migrations atuais funciona, mas é uma bomba-relógio para migrations futuras.
**Fix**: Documentar a limitação em comentário ou migrar para `conn.executescript()` com commit manual.

### 2.5 [W5] `compute_file_hash` lê arquivo inteiro em memória

**Arquivo**: `.specify/scripts/db.py:245-248`
**Problema**: `Path(path).read_bytes()` carrega o arquivo completo na RAM. Para arquivos markdown isso é OK, mas se alguém usar para arquivos grandes (imagens, exports JSON grandes), pode ser problemático.
**Fix**: Considerar leitura em chunks para robustez:
```python
def compute_file_hash(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()
```

### 2.6 [W6] Cada `upsert_*` faz `conn.commit()` individual

**Arquivo**: `.specify/scripts/db.py` (múltiplas funções: `upsert_platform`, `upsert_pipeline_node`, `upsert_epic`, `upsert_epic_node`, `insert_decision`, etc.)
**Problema**: Cada operação de escrita faz seu próprio commit. O `transaction()` context manager existe para batching, mas não é usado em `seed_from_filesystem()` nem em `record_save()` (post_save.py), que fazem múltiplas escritas sequenciais.
**Impacto**: Performance degradada em batch operations (e.g., reseed de todas as plataformas faz N commits por plataforma). Risco de estado inconsistente se o processo falha entre commits.
**Fix**: Usar `transaction()` em `seed_from_filesystem()` e `record_save()`.

### 2.7 [W7] `cmd_import_memory` faz glob recursivo genérico

**Arquivo**: `.specify/scripts/platform.py:451-453`
**Problema**: `memory_dir.rglob("memory")` pode encontrar diretórios "memory" em locais inesperados dentro de `.claude/projects/`. Deveria ser mais específico.

### 2.8 [W8] Portal: `discoverPlatforms()` não valida schema do YAML

**Arquivo**: `portal/src/lib/platforms.mjs:47-51`
**Problema**: Se `platform.yaml` tem YAML inválido ou falta campos (name, views), o build crasharia sem mensagem clara.
**Fix**: Adicionar try/catch com mensagem descritiva.

### 2.9 [W9] LikeC4Diagram platformLoaders é manual

**Arquivo**: `portal/src/components/viewers/LikeC4Diagram.tsx:6-9`
**Problema**: Cada nova plataforma precisa de uma entrada manual no map `platformLoaders`. O `platform.py register` tenta injetar automaticamente, mas usa regex frágil.
**Fix**: A limitação é do Vite (imports estáticos). Documentar claramente no onboarding e no CLAUDE.md (já está documentado, mas reforçar no `register` output).

### 2.10 [W10] `epic-breakdown` default output doesn't match DAG declaration

**Arquivo**: `.claude/commands/madruga/epic-breakdown.md:37-41`
**Problema**: DAG declara output `epics/*/pitch.md` mas Mode 1 (default) só adiciona entradas em `planning/roadmap.md` sem criar diretórios `epics/`. O skill `roadmap.md:44` tenta ler `epics/*/pitch.md` que podem não existir.
**Fix**: Atualizar roadmap skill para também ler da tabela em `planning/roadmap.md`, não só dos pitch files.

### 2.11 [W11] 13 L1 skills omitem seção `Persona` exigida pelo contrato

**Problema**: O contrato uniforme exige `## Persona` em cada skill, mas todos os 13 L1 skills omitem. Funciona na prática porque os contract files de layer (`pipeline-contract-business.md`, etc.) definem a persona.
**Fix**: Ou adicionar Persona nos skills ou atualizar o contrato para dizer "Persona inherited from layer contract."

### 2.12 [W12] `getting-started.md` omite `speckit.clarify` e `speckit.analyze`

**Arquivo**: `.claude/commands/madruga/getting-started.md:82-88`
**Problema**: A lista de comandos disponíveis não menciona `speckit.clarify` nem `speckit.analyze`.

### 2.13 [W13] `solution-overview.md` tem referência hardcoded ao fulano

**Arquivo**: `.claude/commands/madruga/solution-overview.md:56`
**Problema**: Diz "If `platforms/fulano/business/solution-overview.md` exists, read it as tone reference". Hardcoded para fulano.

### 2.14 [W14] `_check_fts5` leaks connection no path de erro

**Arquivo**: `.specify/scripts/db.py:44-57`
**Problema**: Se `CREATE VIRTUAL TABLE` falha, a conexão in-memory `c` não é fechada no `except` block.
**Fix**: Usar `try/finally` para fechar `c`.

### 2.15 [W15] `_validate_artifact_path` pode ser bypassed com symlinks

**Arquivo**: `.specify/scripts/post_save.py:53-58`
**Problema**: Usa `.resolve()` que segue symlinks. Se um symlink dentro do platform dir aponta para fora, o path resolvido passaria a validação. Risco baixo (CLI-only, chamado por Claude).

### 2.16 [W16] `_desc_text` retorna "None" string para description ausente

**Arquivo**: `.specify/scripts/vision-build.py:33-36`
**Problema**: Se `description` é `None`, `str(None)` retorna `"None"` que apareceria em tabelas markdown.
**Fix**: `return str(d) if d else ""`

### 2.17 [W17] `get_decision_links` falha com direction inválido

**Arquivo**: `.specify/scripts/db.py:616-641`
**Problema**: Se `direction` não é "from", "to", ou "both", `parts` fica vazio e `conn.execute("")` causa `OperationalError`.

### 2.18 [W18] `.pipeline/madruga.db` está commitado no git

**Problema**: O DB é staged (`A .pipeline/madruga.db`) e será commitado. É um state store local que deveria estar no `.gitignore`.
**Fix**: Verificar se o `.gitignore` exclui o DB. Se não, adicionar `*.db` ao `.pipeline/.gitignore`.

### 2.19 [W19] Missing index em `decisions.file_path`

**Arquivo**: `.specify/scripts/db.py:752`
**Problema**: `import_adr_from_markdown` faz query `WHERE platform_id=? AND (file_path=? OR file_path=?)`. Index `idx_decisions_platform` cobre `platform_id` mas não `file_path`. Para muitos decisions, pode ser lento.

### 2.20 [W20] `PROCESSED.delete` é no-op em `mermaid-interactive.js`

**Arquivo**: `portal/public/mermaid-interactive.js:154`
**Problema**: `PROCESSED.delete;` é referência de propriedade, não chamada de método. `WeakSet.delete` requer argumento. Linha morta/misleading.
**Fix**: Remover a linha (WeakSet auto-limpa via GC) ou usar `PROCESSED = new WeakSet()`.

### 2.21 [W21] Bundles JS oversized — 7.2MB total

**Problema**: Build gera chunks grandes:
- `internal.*.js` (LikeC4): **1.9MB**
- `elk.bundled.*.js` (ELK layout): **1.4MB**
- `treemap-*.js` (Mermaid): **443KB**
**Mitigação**: São lazy-loaded via `client:only`/`client:visible`. Considerar tree-shaking do LikeC4 ou dynamic import mais granular.

### 2.22 [W22] Mobile layout — kanban e layer cards overflow

**Arquivo**: `portal/src/pages/[platform]/dashboard.astro`
**Problema**: Em viewport 375px, layer cards e kanban columns transbordam horizontalmente. O breakpoint 550px não aplica `flex-wrap: wrap` no `.layer-grid`.

### 2.23 [W23] Epics com status "proposed" mas todos os nós done

**Arquivo**: `portal/src/data/pipeline-status.json`
**Problema**: Epics 006, 007, 008 têm `status: "proposed"` mas todos 11 nós estão done. `getEpicPhase()` compensa verificando nós, mas o dado base é inconsistente.
**Fix**: `seed_from_filesystem` deveria atualizar status do epic quando todos os nós estão done.

### 2.24 [W24] Google Fonts carregado de CDN externo (render-blocking)

**Arquivo**: `portal/src/styles/custom.css:1`
**Problema**: `@import url('https://fonts.googleapis.com/css2?family=Poppins...')` — dependência externa. Se CDN cai, font cai para system-ui. Adiciona request render-blocking.
**Fix**: Self-host a font para portal interno.

### 2.25 [W25] `pipeline_runs` table está vazia e sem uso

**Arquivo**: `.pipeline/madruga.db`
**Problema**: Tabela `pipeline_runs` existe no schema mas tem 0 rows e nenhum código a referencia.
**Fix**: Documentar como future-use ou remover do schema.

---

## 3. NITS (Melhorias de qualidade)

### 3.1 [N1] `re` importado duas vezes em `platform.py`

**Arquivo**: `.specify/scripts/platform.py:27,152`
**Problema**: `re` é importado no topo do arquivo e novamente dentro de `cmd_new()`.

### 3.2 [N2] Argparse no `main()` de platform.py é manual

**Arquivo**: `.specify/scripts/platform.py:644-711`
**Problema**: O CLI usa parsing manual de `sys.argv` em vez de argparse. Funciona, mas adicionar novos sub-commands requer código boilerplate.
**Fix**: Migrar para `argparse` com subparsers, ou `click` para DX melhor.

### 3.3 [N3] Dashboard CSS inline pesado no `.astro` file

**Arquivo**: `portal/src/pages/[platform]/dashboard.astro:263-683`
**Problema**: ~420 linhas de CSS dentro do arquivo Astro. Funciona (scoped por padrão no Astro), mas dificulta manutenção.
**Fix**: Extrair para `dashboard.css` quando o design estabilizar.

### 3.4 [N4] Portal sem tratamento de erro para API de status

**Arquivo**: `portal/src/pages/api/`
**Problema**: O diretório `api/` existe mas não foi explorado. Se há endpoints de API, verificar error handling.

### 3.5 [N5] `PipelineDAG.tsx` usa `any` em vários locais

**Arquivo**: `portal/src/components/dashboard/PipelineDAG.tsx:150,180`
**Problema**: `elkInstance: any`, `result.children?.find((c: any) => ...)` — TypeScript `any` escapes reduzem type safety.

### 3.6 [N6] Copier template não gera `business/process.md`

**Arquivo**: `.specify/templates/platform/template/`
**Problema**: O template scaffolda `business/vision.md` e `business/solution-overview.md`, mas não `business/process.md`. O `business-process` skill gera este arquivo, mas o scaffold poderia incluir um placeholder.

### 3.7 [N7] `model/.gitignore` não está em `_skip_if_exists` — `copier update` sobrescreve

**Arquivo**: `.specify/templates/platform/copier.yml`
**Problema**: O template `model/.gitignore` tem `dist/`, `output/`, `node_modules/`. Fulano adicionou `.ruff_cache/` e `likec4.json`. Como `model/.gitignore` não está em `_skip_if_exists`, um `copier update` sobrescreveria as adições do fulano.
**Fix**: Adicionar `model/.gitignore` ao `_skip_if_exists` ou incluir as entradas extras no template.

### 3.8 [N8] `_skip_if_exists` contém `engineering/folder-structure.md` que não existe

**Arquivo**: `.specify/templates/platform/copier.yml`
**Problema**: Referência morta no `_skip_if_exists`. Inofensivo mas confuso.

### 3.9 [N9] CLAUDE.md diz "3 L2 nodes" mas são 4

**Arquivo**: `CLAUDE.md`
**Problema**: "20 skills: 13 L1 nodes + 3 L2 nodes + 4 utilities" — na verdade são 4 L2 (epic-context, verify, qa, reconcile) + 3 utilities.

### 3.8 [N8] `decision_links` tabela vazia

**Arquivo**: `.pipeline/madruga.db`
**Problema**: 0 rows. A funcionalidade de linking decisions existe no código mas nunca é chamada por nenhum skill.

### 3.8 [N8] Memory entries pouco utilizados

**Arquivo**: `.pipeline/madruga.db`
**Problema**: Apenas 2 entries na tabela `memory_entries`. O import/export funciona mas não é chamado automaticamente.
**Fix**: Considerar hook pós-sessão para auto-import de memories novas.

---

## 4. SUGESTOES DE FRONTEND (Portal UX/UI)

### 4.1 [F1] Adicionar dark/light mode toggle

**Status atual**: Portal é dark-only (Starlight default).
**Melhoria**: Starlight suporta `themes` nativamente. Adicionar toggle no header.

### 4.2 [F2] Dashboard — adicionar refresh automático em dev mode

**Melhoria**: Em dev mode, o dashboard poderia fazer polling do `pipeline-status.json` a cada 30s, ou usar Server-Sent Events para atualização real-time.

### 4.3 [F3] Dashboard — adicionar timeline de eventos

**Melhoria**: A tabela `events` tem 263 entries. Exibir um timeline de últimas atividades no dashboard (skill completions, ADR imports, etc.) daria contexto temporal.

### 4.4 [F4] Sidebar — indicador visual de progresso por plataforma

**Melhoria**: Ao lado do nome da plataforma no sidebar, mostrar um mini progress bar ou percentage do L1.

### 4.5 [F5] Decisões — index page com filtros

**Arquivo**: `portal/src/pages/[platform]/decisions.astro`
**Melhoria**: Página de listagem de ADRs com filtros por status (Accepted, Deprecated, Superseded), busca por texto (usar FTS5 do SQLite via API endpoint), e timeline visual.

### 4.6 [F6] LikeC4 diagrams — fallback quando modelo não compila

**Melhoria**: Se o modelo LikeC4 tem erros, o componente mostra erro genérico. Adicionar mensagem com instrução para rodar `likec4 serve` localmente para debug.

### 4.7 [F7] Mobile responsiveness do Kanban board

**Melhoria**: O kanban de epics empilha em telas < 550px, mas cada coluna fica muito estreita. Considerar horizontal scroll em mobile ou collapsible columns.

---

## 5. SUGESTOES DE AUTOMACAO

### 5.1 [A1] Automatizar geração do `pipeline-status.json`

**Prioridade**: Alta
**Impacto**: O dashboard é a peça central mas depende de arquivo manual.
**Proposta**: Pre-build hook no `package.json` que gera o JSON. Opcionalmente, um `post_save.py` hook que regenera após cada skill completion.

### 5.2 [A2] Validação de integridade do DAG como parte do `lint`

**Prioridade**: Alta
**Impacto**: Previne estados inconsistentes no DB.
**Proposta**: `platform.py lint <name>` deve verificar que se um nó está `done`, todas as suas dependências também estão `done`.

### 5.3 [A3] Auto-reseed após merge to main

**Prioridade**: Média
**Proposta**: Git hook (post-merge) que roda `post_save.py --reseed-all`. Já mencionado no memory do projeto mas não implementado.

### 5.4 [A4] Script de health-check unificado

**Prioridade**: Média
**Proposta**: Um único comando `platform.py health` que roda: lint, DAG validation, template test, portal build check, e DB integrity. Output: JSON report com status por check.

### 5.5 [A5] Geração automática do `platformLoaders` map

**Prioridade**: Baixa
**Proposta**: Build-time script que lê `platforms/*/platform.yaml` e gera o TypeScript map, eliminando o passo manual.

---

## 6. PRIORIZAÇÃO (Ordenada por Impacto × Esforço)

| # | Item | Tipo | Impacto | Esforço | Prioridade |
|---|------|------|---------|---------|-----------|
| 1 | B1 — Fix teste containers.md | BLOCKER | Alto | 5 min | P0 |
| 2 | B2 — DAG integrity validation | BLOCKER | Alto | 1h | P0 |
| 3 | B4 — madruga-ai platform.yaml missing analyze-post + wrong reconcile dep | BLOCKER | Alto | 10 min | P0 |
| 4 | B5 — FTS5 query sanitization | BLOCKER | Alto | 30 min | P0 |
| 5 | B6 — Fix test_kebab_case_validation except catching assert | BLOCKER | Médio | 5 min | P0 |
| 6 | B7 — LikeC4 jsxDEV runtime mismatch in dev mode | BLOCKER | Alto | 2h | P0 |
| 7 | B8 — Dashboard 404 links (platform.yaml, model/*.likec4) | BLOCKER | Alto | 30 min | P0 |
| 8 | B9 — Create qa-template.md | BLOCKER | Médio | 30 min | P1 |
| 9 | W1 — Remover variáveis não usadas | WARNING | Baixo | 2 min | P1 |
| 4 | W2/A1 — Automatizar pipeline-status.json | WARNING | Alto | 15 min | P1 |
| 5 | W3 — Adicionar `site` no astro.config | WARNING | Baixo | 1 min | P1 |
| 6 | W6 — Usar `transaction()` em batch ops | WARNING | Médio | 30 min | P2 |
| 7 | B3 — Fulano missing files | BLOCKER | Médio | 10 min | P2 |
| 8 | A2 — DAG validation no lint | AUTOMAÇÃO | Alto | 1h | P2 |
| 9 | F3 — Timeline de eventos no dashboard | FRONTEND | Alto | 2h | P2 |
| 10 | W4 — SQL parser documentation | WARNING | Baixo | 5 min | P3 |
| 11 | W5 — Hash em chunks | WARNING | Baixo | 10 min | P3 |
| 12 | F1 — Dark/light toggle | FRONTEND | Médio | 30 min | P3 |
| 13 | F5 — ADR index com filtros | FRONTEND | Médio | 3h | P3 |
| 14 | N2 — Argparse com subparsers | NIT | Baixo | 1h | P4 |
| 15 | A5 — Auto-gen platformLoaders | AUTOMAÇÃO | Baixo | 1h | P4 |

---

## 7. ESTADO DO PORTAL — O QUE UM FRONTEND EXCELENTE TERIA

O portal atual é funcional e limpo. Para ser **excelente**:

### Must-Have (próximo sprint)
1. **Live data**: Dashboard com dados real-time (não arquivo estático)
2. **Activity feed**: Timeline de últimas ações (a tabela `events` já tem os dados)
3. **Search**: Full-text search usando o FTS5 já implementado no SQLite
4. **Onboarding wizard**: Primeira visita mostra guided tour com `getting-started` integrado

### Nice-to-Have (backlog)
5. **Diff viewer**: Comparar versões de artifacts (usando git history)
6. **Decision graph**: Visualizar relações entre ADRs (a tabela `decision_links` já existe)
7. **Export**: Gerar PDF do estado completo de uma plataforma
8. **Multi-user awareness**: Mostrar quem está trabalhando em qual epic (se múltiplos Claude Code sessions)
9. **Notifications**: Webhooks/Slack quando um gate precisa de approval

---

## 8. TESTES EXECUTADOS

| Teste | Resultado | Detalhes |
|-------|-----------|----------|
| `npm run build` (portal) | PASS | 77 pages, 34.89s |
| `ruff check .specify/scripts/` | 2 warnings | F841 × 2 (unused vars) |
| `pytest .specify/templates/` | 16 pass, 1 FAIL | `test_auto_markers_present` (containers.md removed) |
| `platform.py lint --all` | PASS (1 warn) | fulano: context-map.md missing |
| DB integrity check | 2 violations | tech-research=pending but adr=done |
| DB schema | OK | 5 migrations applied, 22 tables |
| Security (path traversal) | PROTECTED | `_validate_artifact_path` in post_save.py |
| Portal pages rendered | 77/77 | All platforms, all sections |

---

## 9. ARQUITETURA — PONTOS FORTES

1. **Single source of truth**: LikeC4 → JSON → markdown tables via AUTO markers. Bem implementado.
2. **Copier template**: Multi-platform scaffolding funcional. `_skip_if_exists` protege customizações.
3. **SQLite como state store**: WAL mode, migrations, FK constraints. Schema bem normalizado.
4. **Pipeline DAG**: 24 skills com contrato uniforme de 6 passos. Gate types fazem sentido.
5. **Portal auto-discovery**: `platforms.mjs` descobre plataformas automaticamente. Symlinks via Vite plugin.
6. **Error boundaries**: Tanto `LikeC4Diagram.tsx` quanto `PipelineDAG.tsx` têm error boundaries React.
7. **Path traversal protection**: `post_save.py` valida que artifacts estão dentro do platform dir.
8. **FTS5 graceful degradation**: Se FTS5 não disponível, migrations são skippadas sem crash.

---

*Gerado por equipe emulada de review (PM + Engenharia + Arquitetura + UX) em 2026-03-30.*
