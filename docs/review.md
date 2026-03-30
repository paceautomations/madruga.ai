# Madruga.AI — Comprehensive Codebase Review

**Data**: 2026-03-30
**Revisores**: Equipe emulada (PM, Designer, Engenheiros, Arquiteto, Business Owner)
**Escopo**: End-to-end — Python scripts, portal frontend, pipeline skills, templates, database, testes

---

## Resumo Executivo

O madruga.ai é um sistema de documentação de arquitetura bem estruturado, com pipeline automatizado de 24 skills, portal Astro/Starlight, e SQLite como state store. O portal **compila com sucesso** (77 páginas, 34s build). O Python tem **2 ruff warnings** (variáveis não utilizadas). **1 teste falha** (containers.md removido do template). Existem **inconsistências de integridade no DAG** do pipeline.

### Scorecard

| Área | Status | Score |
|------|--------|-------|
| Portal Build | OK (77 pages) | 9/10 |
| Python Lint (ruff) | 2 warnings | 8/10 |
| Template Tests | 1 FAIL (16 pass) | 7/10 |
| Platform Lint | 1 warn (fulano context-map) | 8/10 |
| Pipeline DAG Integrity | 2 violations | 6/10 |
| DB Schema & Migrations | OK (5 migrations) | 9/10 |
| Security | OK (path traversal protected) | 9/10 |
| Frontend UX | Good, needs polish | 7/10 |
| Code Quality | Solid, minor DRY issues | 8/10 |
| **Overall** | | **8/10** |

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

### 2.10 [W10] `pipeline_runs` table está vazia e sem uso

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

### 3.7 [N7] `decision_links` tabela vazia

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
| 3 | W1 — Remover variáveis não usadas | WARNING | Baixo | 2 min | P1 |
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
