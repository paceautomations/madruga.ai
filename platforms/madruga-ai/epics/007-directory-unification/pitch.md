---
id: 007
title: "Directory Unification — SpecKit Opera em epics/, DAG Dois Níveis"
status: shipped
phase: pitch
appetite: 2w
priority: 2
delivered_at: 2026-03-29
updated: 2026-03-29
---
# Directory Unification — SpecKit Opera em epics/, DAG Dois Níveis

## Problema

SpecKit e Madruga operam em diretórios separados: SpecKit cria artifacts em `specs/<NNN>/` enquanto Madruga gera pitch.md e context.md em `platforms/<name>/epics/<NNN>/`. Isso causa:

1. **Dois mundos** — spec.md, plan.md, tasks.md vivem em `specs/` enquanto pitch.md, context.md, verify-report.md vivem em `epics/`. Sem lineage unificado
2. **DAG incompleto** — 10 skills do ciclo per-epic (epic-context, specify, plan, tasks, analyze, implement, verify, qa, reconcile) não são nós do DAG. Zero observabilidade per-epic
3. **Nomes confusos** — discuss, adr-gen, test-ai, vision-one-pager, folder-arch são nomes vagos ou inconsistentes
4. **Pipeline fragmentado** — pipeline-status e pipeline-next são 2 skills separadas que fazem o mesmo. Não cobrem per-epic
5. **Sem HANDOFF blocks** — context entre skills se perde. Decisions não propagam

## Appetite

1-2 semanas (small batch). Ajustes cirúrgicos em scripts + renaming + HANDOFF + /pipeline unificado.

## Solução

1. **Scripts SpecKit ganham `--base-dir`** — `create-new-feature.sh`, `setup-plan.sh`, `check-prerequisites.sh` aceitam path customizado (default: `specs/`, novo: `platforms/<name>/epics/<NNN>/`)
2. **`epic_cycle` no Copier template** — `platform.yaml.jinja` ganha seção com 10 nós do ciclo per-epic
3. **`--epic` flag** no `check-platform-prerequisites.sh` para checar nós do epic cycle no BD
4. **Rename skills** — discuss→epic-context, adr-gen→adr, test-ai→qa, vision-one-pager→vision
5. **Merge folder-arch em blueprint** — eliminar skill, absorver como seção
6. **HANDOFF blocks** — template no contrato base, todas skills incluem bloco YAML no artefato
7. **`/pipeline` unificado** — merge status+next em uma skill, lê SQLite para ambos DAG levels
8. **Migrar artifacts** — mover specs/002-sqlite-foundation/ para epics/006-sqlite-foundation/

## Rabbit Holes

- NÃO reescrever lógica interna do SpecKit (specify, plan, tasks, implement permanecem)
- NÃO implementar knowledge files em camadas (epic 008)
- NÃO implementar auto-review tiered (epic 008)
- NÃO adicionar elements/relationships ao BD (fase futura)

## Acceptance Criteria

1. `create-new-feature.sh --base-dir platforms/prosauai/epics/001-test` cria spec.md no epic dir
2. `platform.yaml` gerado pelo Copier tem seção `epic_cycle` com 10 nós
3. `check-platform-prerequisites.sh --json --platform prosauai --epic 001 --use-db` retorna status do epic cycle
4. `discuss.md` não existe; `epic-context.md` existe e funciona
5. `folder-arch.md` não existe; `blueprint.md` inclui seção Folder Structure
6. `/pipeline madruga-ai` mostra DAG nível 1 + progresso per-epic do BD
7. Todas skills com gate human têm HANDOFF block no template de output



## Captured Decisions

| # | Área | Decisão | Referência Arquitetural | Alternativa Rejeitada |
|---|------|---------|------------------------|----------------------|
| 1 | Storage model | Filesystem continua como fonte de verdade para artefatos. SQLite rastreia metadata (status, timestamps). Nenhuma mudança neste epic. | ADR-004 (file-based storage) | SQLite como storage primário — violaria ADR-004 e aumentaria acoplamento |
| 2 | Artifact ownership | Cada artefato no epic dir tem exatamente 1 owner (skill) e 1 purpose. `verify-report.md` é o único artefato genuinamente novo. | ADR-008 (MECE artifact model) | Artefatos compartilhados entre skills — cria ownership ambíguo |
| 3 | Scripts SpecKit | `create-new-feature.sh`, `setup-plan.sh`, `check-prerequisites.sh` ganham `--base-dir` para operar em `epics/<NNN>/`. Default permanece `specs/` para retrocompatibilidade durante transição. Lógica interna intacta. | Blueprint §3 (CI/CD), ADR-005 (SpecKit bridge) | Reescrever scripts — violaria pitch ("NÃO reescrever lógica interna do SpecKit") |
| 4 | Eliminação de `specs/` | Migrar `specs/001-*` e `specs/002-*` para `epics/` e **deletar `specs/`**. Corte limpo, sem README redirect. Git preserva histórico via `git log --follow`. | ADR-008 (MECE — um diretório por propósito) | Manter `specs/` com redirect — gambiarra que acumula |
| 5 | Renaming de skills | Rename atômico (único commit): discuss→epic-context, adr-gen→adr, test-ai→qa, vision-one-pager→vision, folder-arch eliminado. Sem aliases/symlinks. | Pipeline DAG knowledge, ADR-008 | Aliases temporários — dívida técnica que nunca é paga |
| 6 | Merge folder-arch em blueprint | Absorver conteúdo de `folder-structure.md` como seção "Folder Structure" no template do blueprint. Deletar skill `folder-arch.md`. DAG reduz de 14→13 nós. | Blueprint (já contém concerns transversais), ADR-008 | Manter deprecated — procrastinação |
| 7 | HANDOFF blocks | Bloco YAML no footer do artefato gerado + campo `handoff_template` nos nós do DAG knowledge. Formato: `from`, `to`, `context` (texto livre), `blockers` (lista). | ADR-013 (decision gates), Pipeline DAG knowledge | Só no artefato — easter futuro precisaria retrofit para routing automático |
| 8 | Epic cycle no SQLite | **Nova tabela `epic_cycle_nodes`** com FK para epic. Separada de `pipeline_nodes` (L1). Query limpa, schema explícito. | ADR-012 (SQLite WAL), Domain model §Execution | Expandir `pipeline_nodes` com colunas — polui queries, mistura 13 nós fixos com N×10 nós variáveis |
| 9 | `/pipeline` unificado | Merge de pipeline-status + pipeline-next em 1 skill. Lê SQLite para ambos os níveis (L1 + L2). Mermaid dinâmico com cores por status. | ADR-012 (SQLite WAL), Containers §Dashboard | Filesystem para L2 — inconsistente com L1 que já usa SQLite |
| 10 | Source of truth para status | `check-platform-prerequisites.sh --epic NNN --use-db` lê SQLite. Sem `--use-db`, fallback para filesystem (existência de arquivos). Consistente com comportamento L1 existente. | ADR-004, ADR-012 | Só filesystem — perde observabilidade do SQLite |

## Resolved Gray Areas

### GA1. Onde vivem artefatos SpecKit?

**Pergunta:** SpecKit cria em `specs/` ou `epics/`?
**Resposta:** Em `epics/<NNN-slug>/`. O `--base-dir` redireciona todos os scripts.
**Rationale:** ADR-008 (MECE) exige um local canônico. Dois diretórios para o mesmo propósito viola o princípio.

### GA2. Tabela SQLite para epic cycle — expandir ou criar?

**Pergunta:** Reusar `pipeline_nodes` ou criar `epic_cycle_nodes`?
**Resposta:** Criar `epic_cycle_nodes`. 5 epics × 10 nós = 50+ rows que não se misturam com os 13 nós fixos do platform DAG.
**Rationale:** Schema que escala sem refactor. Esforço marginal (+15min), resultado permanente.

### GA3. Formato do HANDOFF block

**Pergunta:** Qual schema YAML?
**Resposta:**
```yaml
handoff:
  from: epic-context
  to: specify
  context: "Spec deve endereçar as decisões capturadas acima. Constraints do blueprint aplicam."
  blockers: []
```
**Rationale:** Minimalista mas completo. `context` é texto livre para o próximo skill. `blockers` lista impedimentos não resolvidos. Duplicado no DAG knowledge como `handoff_template` por nó para routing futuro do easter.

### GA4. Migração de specs/ — mover vs redirect

**Pergunta:** Mover arquivos ou criar README apontando?
**Resposta:** Mover de fato e deletar `specs/`.
**Rationale:** Princípio I (pragmatismo). 14 arquivos, zero risco. Redirect é gambiarra.

### GA5. Renaming — atômico ou gradual?

**Pergunta:** Renomear tudo de uma vez ou manter aliases?
**Resposta:** Commit atômico. Renomear 5 skills + atualizar CLAUDE.md + pipeline-dag-knowledge.md + referências em scripts. Validar com grep pós-commit.
**Rationale:** Aliases criam confusão sobre "qual nome é o certo". Ninguém além do operador usa esses skills.

## Applicable Constraints

| # | Constraint | Fonte | Impacto neste epic |
|---|-----------|-------|-------------------|
| 1 | Zero external dependencies (Python stdlib only) | Blueprint §3, ADR-012 | Qualquer script novo usa apenas stdlib |
| 2 | SQLite WAL mode, FK=ON, busy_timeout=5000 | ADR-012 | Nova tabela `epic_cycle_nodes` segue mesmas pragmas |
| 3 | MECE artifact model | ADR-008 | Cada artefato tem 1 owner, 1 purpose |
| 4 | File-based storage como fonte de verdade | ADR-004 | SQLite é secondary index, não primary storage |
| 5 | Copier template `_skip_if_exists` | ADR-002 | `epic_cycle` adicionado ao template mas não sobrescreve platform.yaml existente — requer `copier update` |
| 6 | TDD para todo código | Constitution §VII | Scripts bash e migration SQL devem ter testes |
| 7 | NÃO reescrever lógica interna do SpecKit | pitch.md §Rabbit Holes | Apenas `--base-dir`, sem mudança de lógica |
| 8 | NÃO implementar knowledge layers ou auto-review tiered | pitch.md §Rabbit Holes | Escopo do epic 008 |

## Suggested Approach

### Ordem de execução (por dependência)

1. **Migração `specs/` → `epics/`** — Mover `specs/001-*` → `epics/005-atomic-skills-dag/`, `specs/002-*` → `epics/006-sqlite-foundation/`. Deletar `specs/`. Commit isolado.
2. **Renaming de skills** — Commit atômico: rename 5 arquivos + atualizar todas referências (CLAUDE.md, knowledge, scripts, DAG). Grep de validação.
3. **Merge folder-arch em blueprint** — Absorver conteúdo como seção, deletar skill, atualizar DAG (14→13 nós). Mesmo commit ou logo após.
4. **`--base-dir` nos scripts SpecKit** — `create-new-feature.sh`, `setup-plan.sh`, `check-prerequisites.sh`. Testes.
5. **`epic_cycle` no Copier template** — Adicionar seção em `platform.yaml.jinja`. Testes do template.
6. **Schema SQLite L2** — Migration `002_epic_cycle_nodes.sql`. Testes com `db.py`.
7. **HANDOFF blocks** — Adicionar `handoff_template` no DAG knowledge + template de output nas skills com gate human.
8. **`/pipeline` unificado** — Merge status+next, lê SQLite L1+L2, Mermaid dinâmico.

### Princípio de priorização

**Resultado >> esforço.** Todos os 8 deliverables são P0 — separar em fases cria overhead de context switching que custa mais do que fazer tudo junto. Small-batch = tudo de uma vez.

handoff:
  from: epic-context
  to: specify
  context: "Spec deve cobrir os 8 deliverables na ordem de execução definida acima. Decisões D1-D10 são vinculantes. Constraints C1-C8 aplicam. HANDOFF format definido em GA3."
  blockers: []
