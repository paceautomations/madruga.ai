---
type: qa-report
date: 2026-04-06
feature: "022-mermaid-migration"
branch: "epic/madruga-ai/022-mermaid-migration"
layers_executed: ["L1", "L2", "L3", "L4"]
layers_skipped: ["L5", "L6"]
findings_total: 24
pass_rate: "75%"
healed: 0
unresolved: 24
---
# QA Report — 022 Mermaid Migration (LikeC4 → Mermaid Inline)

**Data:** 06/04/2026 | **Branch:** `epic/madruga-ai/022-mermaid-migration` | **Arquivos alterados:** 91
**Camadas executadas:** L1, L2, L3, L4 | **Camadas ignoradas:** L5 (sem servidor), L6 (sem Playwright)

---

## Resumo

| Status | Contagem |
|--------|----------|
| ✅ PASS | 18 |
| 🔧 HEALED | 0 |
| ⚠️ WARN | 7 |
| ❌ UNRESOLVED | 14 |
| ⏭️ SKIP | 3 |

> **Nota:** Heal loop nao executado — permissoes de edicao nao disponiveis nesta sessao. Todos os findings estao OPEN com instrucoes exatas de fix.

---

## L1: Analise Estatica

| Ferramenta | Resultado | Findings |
|------------|-----------|----------|
| ruff check | ✅ limpo | — |
| ruff format | ✅ limpo | 57 arquivos ja formatados |

---

## L2: Testes Automatizados

| Suite | Passed | Failed | Skipped |
|-------|--------|--------|---------|
| pytest | 633 | 0 | 0 |

✅ Todos os 633 testes passam, incluindo `test_template.py` (que foi atualizado para remover expectativas de `model/`).

---

## L3: Code Review

### Verificacoes Core da Migracao (PASS)

| Verificacao | Resultado | Detalhes |
|-------------|-----------|----------|
| Zero arquivos `.likec4` no repo | ✅ PASS | `find . -name "*.likec4"` retorna vazio |
| Zero `likec4.config.json` | ✅ PASS | Nenhum encontrado |
| Zero refs LikeC4 no portal/src/ | ✅ PASS | `grep -r "LikeC4\|likec4" portal/src/ --include=*.{ts,tsx,mjs,astro}` retorna vazio |
| Paginas .astro removidas | ✅ PASS | landscape, containers, context-map, bc/[context], business-flow — todas deletadas |
| LikeC4Diagram.tsx removido | ✅ PASS | Arquivo deletado |
| likec4.d.ts removido | ✅ PASS | Arquivo deletado |
| LikeC4VitePlugin removido do astro.config | ✅ PASS | Nenhuma referencia |
| buildViewPaths removido de platforms.mjs | ✅ PASS | Funcao nao existe mais |
| vision-build.py removido | ✅ PASS | Arquivo deletado |
| model/ removido (prosauai) | ✅ PASS | Diretorio deletado |
| model/ removido (madruga-ai) | ✅ PASS | Diretorio deletado |
| Mermaid diagramas em blueprint.md (prosauai) | ✅ PASS | Deploy topology + containers presentes |
| Mermaid diagramas em domain-model.md (prosauai) | ✅ PASS | Context map + BC classDiagrams |
| Mermaid diagramas em process.md (prosauai) | ✅ PASS | Overview + deep-dives por fase |
| Mermaid diagramas em blueprint.md (madruga-ai) | ✅ PASS | Deploy topology + containers |
| Mermaid diagramas em domain-model.md (madruga-ai) | ✅ PASS | Context map + BC classDiagrams |
| ADR-020 criado | ✅ PASS | `ADR-020-mermaid-inline-diagrams.md` existe |
| ADR-001 superseded | ✅ PASS | Status: Superseded, referencia ADR-020 |
| ADR-003 sem LikeC4VitePlugin | ✅ PASS | Zero mencoes |
| platform.yaml sem views/serve/build (ambas) | ✅ PASS | Blocos removidos |
| Template Copier sem model/ | ✅ PASS | Diretorio e arquivos .likec4.jinja removidos |
| CI sem job likec4 | ✅ PASS | Zero refs em ci.yml |
| CLAUDE.md (root) sem LikeC4 | ✅ PASS | Zero refs |
| platforms/madruga-ai/CLAUDE.md sem LikeC4 | ✅ PASS | Zero refs |
| platform_cli.py sem model/ em REQUIRED_DIRS | ✅ PASS | Atualizado |
| test_platform.py sem model/ refs | ✅ PASS | Atualizado |
| test_template.py sem model/*.likec4 refs | ✅ PASS | Reescrito |

### Findings — BLOCKERs (S1)

| # | Arquivo | Finding | Fix |
|---|---------|---------|-----|
| B1 | `.claude/knowledge/pipeline-dag-knowledge.md:21-22` | Linhas 21-22 ainda listam `model/ddd-contexts.likec4` e `model/platform.likec4, model/views.likec4` como outputs de domain-model e containers. Definicao canonica do DAG — prerequisite checks e skills referenciam. Viola FR-015. | Linha 21: mudar outputs para `engineering/domain-model.md`. Linha 22: mudar outputs para `engineering/blueprint.md`. |
| B2 | `.claude/knowledge/pipeline-contract-engineering.md:19-49` | Principios 4-5 dizem "LikeC4 is source of truth" e "Mermaid for flows, LikeC4 for structure." Linhas 22-49 prescrevem `likec4 build` validation e 8 convention checks para `.likec4`. Contrato injetado em todo skill engineering-layer. Contradiz ADR-020. | Substituir principio 4: "Mermaid inline is source of truth — diagramas vivem como blocos Mermaid em `.md`." Substituir principio 5: "Mermaid para todos diagramas — graph/flowchart para topologia, classDiagram para DDD, sequenceDiagram para fluxos." Deletar secoes "LikeC4 Validation" (22-31) e "LikeC4 Convention Checks" (33-49). |

### Findings — WARNINGs (S2)

| # | Arquivo | Finding | Fix |
|---|---------|---------|-----|
| W1 | `.claude/rules/likec4.md` | Arquivo de regras ativo — auto-carregado por path match. Injeta instrucoes LikeC4 stale. | Deletar arquivo inteiro. |
| W2 | `.claude/knowledge/likec4-syntax.md` | Referencia de sintaxe LikeC4 (212 linhas) — completamente morta apos migracao. | Deletar arquivo inteiro. |
| W3 | `.claude/rules/portal.md:5,10,12-13` | Titulo diz "LikeC4 React", referencia LikeC4VitePlugin e LikeC4Diagram.tsx platformLoaders — componentes deletados. | Reescrever titulo para "Portal Conventions (Astro + Starlight + Mermaid)". Remover linha 10 (LikeC4VitePlugin). Substituir linhas 12-13 com nota sobre astro-mermaid. |
| W4 | `.claude/knowledge/commands.md:11,30-42` | Secao "LikeC4" com `likec4 serve`, "Build Pipeline" com `vision-build.py`, register diz "inject LikeC4 loader". | Remover secao "## LikeC4" (30-34). Remover secao "## Build Pipeline" (36-42). Atualizar linha 11: `register <name>  # registrar plataforma no portal`. |
| W5 | `platforms/madruga-ai/engineering/blueprint.md:22-23,67,92,295` | Stack table lista "LikeC4 React" e "LikeC4 (.likec4 files)", error handling referencia LikeC4, NFR menciona `.likec4`. | Atualizar stack table: remover LikeC4. Atualizar error handling e NFR: substituir por Mermaid. |
| W6 | `platforms/madruga-ai/business/process.md:79-80` | Tabela do pipeline lista `model/ddd-contexts.likec4` e `model/platform.likec4 + model/views.likec4` como outputs. | Atualizar: domain-model → `engineering/domain-model.md`. Containers → `engineering/blueprint.md`. |
| W7 | `README.md:137-138,785` | Tabela do pipeline lista `.likec4` outputs. Copier section referencia `model/spec.likec4`. | Atualizar tabela: remover `.likec4` refs. Remover referencia copier. |

### Findings — Skills (S2, requerem `/madruga:skills-mgmt`)

| # | Skill | Finding | Fix via |
|---|-------|---------|---------|
| W8 | `.claude/commands/madruga/domain-model.md` | Descricao, outputs, secao 2b referenciam `model/ddd-contexts.likec4` e geracao LikeC4 DSL. | `/madruga:skills-mgmt edit domain-model` |
| W9 | `.claude/commands/madruga/containers.md` | Outputs `model/platform.likec4`, `model/views.likec4`. Instrucoes de geracao LikeC4 DSL. | `/madruga:skills-mgmt edit containers` |
| W10 | `.claude/commands/madruga/context-map.md:49-50` | Inputs referenciam `model/platform.likec4`, `model/ddd-contexts.likec4`. | `/madruga:skills-mgmt edit context-map` |
| W11 | `.claude/commands/madruga/platform-new.md` | Prerequisito `likec4` CLI e scaffold `model/`. | `/madruga:skills-mgmt edit platform-new` |
| W12 | `.claude/commands/madruga/reconcile.md:66` | Drift matrix referencia `model/platform.likec4`. | `/madruga:skills-mgmt edit reconcile` |

### Findings — NITs (S3)

| # | Arquivo | Finding | Fix |
|---|---------|---------|-----|
| N1 | `.claude/knowledge/pipeline-dag-knowledge.md:170` | Auto-review diz "Mermaid/LikeC4 diagrams" — deve ser "Mermaid diagrams". | Mudar para "Mermaid diagrams included where applicable". |
| N2 | `.specify/scripts/db_pipeline.py:736` | Extrai keys `views`, `serve`, `build` do platform.yaml para metadata JSON — keys removidas, metadata sempre vazia. | Remover keys stale ou substituir por existentes (tags, repo). |
| N3 | `.specify/scripts/tests/conftest.py:63` | Fixture inclui `model: model/` no platform.yaml canonico. | Remover `model: model/` da fixture. |
| N4 | `.claude/commands/madruga/solution-overview.md` | Lista "LikeC4" em blocklist de termos tecnicos. | `/madruga:skills-mgmt edit solution-overview` — remover refs. |
| N5 | `.claude/commands/madruga/skills-mgmt.md:28` | Tabela de dependencias referencia `likec4-syntax.md`. | `/madruga:skills-mgmt edit skills-mgmt` — remover entrada. |

---

## L4: Build Verification

| Comando | Resultado | Duracao |
|---------|-----------|---------|
| `cd portal && npm run build` | ✅ PASS | 42.65s (86 paginas) |
| `make test` (pytest) | ✅ PASS | 168.10s (633 testes) |
| `make lint` (platform lint) | ✅ PASS | prosauai ✅, madruga-ai ✅ |

---

## L5: API Testing

⏭️ Sem servidor rodando — ignorado.

---

## L6: Browser Testing

⏭️ Playwright nao ativado / sem features web novas — ignorado.

---

## Heal Loop

> **Permissoes de edicao nao disponiveis nesta sessao.** Todos os fixes estao documentados acima com instrucoes exatas.

| # | Camada | Finding | Status |
|---|--------|---------|--------|
| B1 | L3 | pipeline-dag-knowledge.md stale outputs | ❌ UNRESOLVED — precisa editar linhas 21-22 |
| B2 | L3 | pipeline-contract-engineering.md LikeC4 principles | ❌ UNRESOLVED — precisa reescrever linhas 19-49 |
| W1 | L3 | `.claude/rules/likec4.md` still exists | ❌ UNRESOLVED — deletar arquivo |
| W2 | L3 | `.claude/knowledge/likec4-syntax.md` still exists | ❌ UNRESOLVED — deletar arquivo |
| W3 | L3 | `.claude/rules/portal.md` stale content | ❌ UNRESOLVED — reescrever |
| W4 | L3 | `commands.md` stale sections | ❌ UNRESOLVED — remover secoes |
| W5 | L3 | `blueprint.md` stack table LikeC4 refs | ❌ UNRESOLVED — atualizar |
| W6 | L3 | `process.md` pipeline table stale outputs | ❌ UNRESOLVED — atualizar |
| W7 | L3 | `README.md` stale .likec4 refs | ❌ UNRESOLVED — atualizar |
| W8-W12 | L3 | 5 skills com refs LikeC4 | ❌ UNRESOLVED — requer `/madruga:skills-mgmt` |
| N1 | L3 | "Mermaid/LikeC4" text | ❌ UNRESOLVED — atualizar |
| N2 | L3 | db_pipeline.py stale metadata keys | ❌ UNRESOLVED — remover |
| N3 | L3 | conftest.py `model: model/` | ❌ UNRESOLVED — remover |
| N4-N5 | L3 | 2 skills com refs LikeC4 (nit) | ❌ UNRESOLVED — requer `/madruga:skills-mgmt` |

---

## Arquivos que Precisam de Fix (pelo heal loop)

### Editar diretamente (nao-skills)

| Arquivo | Mudanca |
|---------|---------|
| `.claude/knowledge/pipeline-dag-knowledge.md` | Linhas 21-22: atualizar outputs. Linha 170: remover "/LikeC4". |
| `.claude/knowledge/pipeline-contract-engineering.md` | Linhas 19-49: reescrever principios 4-5, deletar secoes LikeC4 Validation e Convention Checks. |
| `.claude/rules/likec4.md` | DELETAR arquivo inteiro. |
| `.claude/knowledge/likec4-syntax.md` | DELETAR arquivo inteiro. |
| `.claude/rules/portal.md` | Reescrever titulo, remover LikeC4VitePlugin e platformLoaders refs. |
| `.claude/knowledge/commands.md` | Remover secoes LikeC4 e Build Pipeline. Atualizar register desc. |
| `platforms/madruga-ai/engineering/blueprint.md` | Remover LikeC4 da stack table e refs em error handling/NFR. |
| `platforms/madruga-ai/business/process.md` | Linhas 79-80: atualizar outputs na tabela do pipeline. |
| `README.md` | Linhas 137-138: atualizar outputs. Linha 785: remover ref spec.likec4. |
| `.specify/scripts/db_pipeline.py` | Linha 736: remover keys stale (views, serve, build). |
| `.specify/scripts/tests/conftest.py` | Linha 63: remover `model: model/`. |

### Editar via `/madruga:skills-mgmt` (skills)

| Skill | Mudanca |
|-------|---------|
| `madruga/domain-model` | Desc, outputs, secao 2b: remover LikeC4 DSL, atualizar para Mermaid. |
| `madruga/containers` | Outputs, instrucoes: mudar de `.likec4` para Mermaid em `blueprint.md`. |
| `madruga/context-map` | Inputs: mudar de `model/*.likec4` para Mermaid sections em `.md`. |
| `madruga/platform-new` | Remover prereq `likec4` CLI, remover `model/` scaffold. |
| `madruga/reconcile` | Drift matrix: mudar `model/platform.likec4` para `blueprint.md`. |
| `madruga/solution-overview` | Remover "LikeC4" da blocklist. |
| `madruga/skills-mgmt` | Remover `likec4-syntax.md` da tabela de deps. |

---

## Licoes Aprendidas

1. **Migracao de tooling exige busca exaustiva de referencias** — grep por ".likec4", "LikeC4", "likec4", "model/" em TODO o repo, nao apenas nos arquivos listados no plano. A implementacao cobriu o core (portal, paginas, modelos, template, CI) mas deixou ~400 linhas de referencias mortas em knowledge files, rules, skills e scripts.

2. **Skills consumidos por LLMs sao "codigo executavel"** — references stale em `.claude/commands/` e `.claude/knowledge/` nao sao apenas documentacao: sao instrucoes que LLMs seguem literalmente. Um skill que diz "gere `model/ddd-contexts.likec4`" vai tentar gerar esse arquivo.

3. **Testes passam mas validam contrato antigo** — `conftest.py` fixture inclui `model: model/` que ja nao existe. Testes passam vacuamente mas nao validam o contrato novo. Importante atualizar fixtures apos mudancas de schema.

4. **Portal build funcional** — a remocao do LikeC4 do portal (VitePlugin, pages, componentes) foi feita corretamente. O build de 86 paginas completa em 42s.

5. **A convencao de editar skills via `/madruga:skills-mgmt`** cria um gap natural entre implementacao (que nao pode editar skills diretamente) e a necessidade de atualizar skills apos mudancas arquiteturais. Recomendacao: skills updates devem ser trackados explicitamente em tasks.md com responsavel definido.

---

handoff:
  from: madruga:qa
  to: madruga:reconcile
  context: "QA completo para 022-mermaid-migration. Core da migracao PASS (portal, diagramas, template, CI, testes). 24 findings UNRESOLVED — todos sao refs LikeC4 stale em knowledge/rules/skills/docs que nao foram limpos na implementacao. Heal loop bloqueado (sem permissao de edicao). Fixes documentados com instrucoes exatas. Prioridade: B1-B2 (pipeline DAG + contract), W1-W2 (delete files), depois o resto."
  blockers:
    - "B1: pipeline-dag-knowledge.md still lists .likec4 outputs"
    - "B2: pipeline-contract-engineering.md prescribes LikeC4 validation"
    - "W1-W12: 12 files with stale LikeC4 references"
  confidence: Media
  kill_criteria: "Se os BLOCKERs B1-B2 nao forem corrigidos, skills do pipeline vao gerar artefatos errados (tentando criar .likec4 files que nao existem mais)."
