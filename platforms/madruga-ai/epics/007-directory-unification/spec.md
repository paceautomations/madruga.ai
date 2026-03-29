# Feature Specification: Directory Unification

**Feature Branch**: `003-directory-unification`
**Created**: 2026-03-29
**Status**: Draft
**Input**: Epic 007 — Directory Unification. SpecKit opera em epics/, DAG dois níveis, renaming de skills, merge folder-arch, HANDOFF blocks, /pipeline unificado.

## User Scenarios & Testing

### User Story 1 — Operador executa SpecKit dentro do epic dir (Priority: P1)

O operador (engenheiro/arquiteto) invoca `/speckit.specify fulano 001` e o sistema cria `spec.md` dentro de `platforms/fulano/epics/001-channel-pipeline/` em vez de `specs/001/`. Todos os artefatos SpecKit (spec, plan, tasks, checklists, contracts, data-model) vivem no epic dir. O operador encontra tudo num lugar só.

**Why this priority**: Sem isso, o epic inteiro não faz sentido. É a mudança central que elimina a fragmentação entre `specs/` e `epics/`.

**Independent Test**: Rodar `create-new-feature.sh --base-dir platforms/fulano/epics/001-test` e verificar que `spec.md` é criado no path correto.

**Acceptance Scenarios**:

1. **Given** um epic existente em `platforms/fulano/epics/001-channel-pipeline/`, **When** operador roda `create-new-feature.sh --base-dir platforms/fulano/epics/001-channel-pipeline/`, **Then** `spec.md` é criado dentro do epic dir
2. **Given** scripts `setup-plan.sh` e `check-prerequisites.sh`, **When** invocados com `--base-dir` apontando para epic dir, **Then** leem e escrevem artefatos no epic dir
3. **Given** nenhum `--base-dir` passado, **When** operador roda scripts SpecKit, **Then** comportamento default em `specs/` é preservado

---

### User Story 2 — Operador visualiza pipeline L1 + L2 num único comando (Priority: P1)

O operador invoca `/pipeline madruga-ai` e vê: (1) tabela com status dos 13 nós do platform DAG (L1), (2) para cada epic existente, tabela com status dos 10 nós do epic cycle (L2), (3) diagrama Mermaid com cores por status (verde=done, amarelo=pending, cinza=skipped, vermelho=blocked, laranja=stale). Dados vêm do SQLite.

**Why this priority**: Observabilidade é o problema central descrito no pitch. Sem isso, o ciclo per-epic continua invisível.

**Independent Test**: Criar registros de teste no SQLite para L1 e L2, rodar `/pipeline`, verificar que ambos os níveis aparecem com dados corretos.

**Acceptance Scenarios**:

1. **Given** plataforma `madruga-ai` com pipeline_nodes no SQLite e epic_cycle_nodes para epic 006, **When** operador roda `/pipeline madruga-ai`, **Then** vê tabela L1 + tabela L2 para epic 006 + Mermaid colorido
2. **Given** nenhum epic_cycle_node registrado para um epic, **When** operador roda `/pipeline madruga-ai`, **Then** epic aparece com status "not started" e 0/10 nós completos
3. **Given** epic com nós em estados mistos (done, in-progress, pending), **When** Mermaid é gerado, **Then** cores refletem status correto de cada nó

---

### User Story 3 — Skills renomeados funcionam com novos nomes (Priority: P1)

O operador invoca `/vision fulano` (antes: `/vision-one-pager fulano`), `/epic-context fulano 001` (antes: `/discuss fulano 001`), `/adr fulano` (antes: `/adr-gen fulano`), `/qa fulano 001` (antes: `/test-ai fulano 001`). Nomes antigos não existem. Todas as referências em CLAUDE.md, knowledge, e DAG estão atualizadas.

**Why this priority**: Nomes confusos causam atrito diário. Rename é baixo esforço com resultado permanente.

**Independent Test**: Após rename, `grep -r "discuss\|adr-gen\|test-ai\|vision-one-pager\|folder-arch" .claude/ CLAUDE.md` retorna zero resultados.

**Acceptance Scenarios**:

1. **Given** skill `discuss.md` renomeado para `epic-context.md`, **When** operador invoca `/epic-context fulano 007`, **Then** skill executa normalmente
2. **Given** rename concluído, **When** busca por nomes antigos no repo, **Then** zero referências encontradas (exceto em commits/histórico)
3. **Given** DAG knowledge atualizado, **When** `/pipeline` lista nós, **Then** nomes novos aparecem (vision, adr, qa, epic-context)

---

### User Story 4 — Epic cycle rastreado no SQLite (Priority: P2)

O sistema persiste status de cada nó do epic cycle (epic-context, specify, clarify, plan, tasks, analyze, implement, verify, qa, reconcile) na tabela `epic_cycle_nodes` do SQLite. Cada execução de skill atualiza o status do nó correspondente. O check de pré-requisitos (`--epic --use-db`) consulta esta tabela para determinar quais nós já completaram.

**Why this priority**: Foundation para que `/pipeline` (US2) mostre dados reais. Sem schema, não há dados para visualizar.

**Independent Test**: Inserir registros de teste em `epic_cycle_nodes`, rodar `check-platform-prerequisites.sh --epic 007 --use-db`, verificar que retorna status correto.

**Acceptance Scenarios**:

1. **Given** migration `002_epic_cycle_nodes.sql` aplicada, **When** `db.py migrate()` roda, **Then** tabela `epic_cycle_nodes` existe com colunas corretas
2. **Given** epic 007 com nós epic-context=done e specify=pending, **When** `check-platform-prerequisites.sh --epic 007 --use-db --skill specify`, **Then** retorna `ready: true` (pré-req epic-context done)
3. **Given** epic 007 com nó epic-context=pending, **When** `check-platform-prerequisites.sh --epic 007 --use-db --skill specify`, **Then** retorna `ready: false` com missing dependency

---

### User Story 5 — HANDOFF blocks propagam contexto entre skills (Priority: P2)

Após cada skill com gate `human` gerar seu artefato, o footer contém um bloco YAML HANDOFF com: `from` (skill atual), `to` (próximo skill), `context` (texto livre com decisões e constraints relevantes), `blockers` (lista de impedimentos). O DAG knowledge inclui `handoff_template` por nó como referência para o daemon futuro.

**Why this priority**: Decisões se perdem entre skills hoje. HANDOFF resolve isso de forma estruturada e prepara para automação futura.

**Independent Test**: Rodar um skill (ex: `/vision fulano`), verificar que o artefato gerado contém bloco HANDOFF YAML válido no footer.

**Acceptance Scenarios**:

1. **Given** skill `epic-context` gera `context.md`, **When** artefato é escrito, **Then** footer contém bloco HANDOFF com `from: epic-context`, `to: specify`, `context` preenchido, `blockers: []`
2. **Given** DAG knowledge atualizado, **When** lê-se nó `vision`, **Then** campo `handoff_template` existe com `to: solution-overview`
3. **Given** skill encontra impedimento não resolvido, **When** artefato é gerado, **Then** HANDOFF.blockers lista o impedimento

---

### User Story 6 — Folder-arch absorvido no blueprint (Priority: P3)

O template do blueprint ganha seção "Folder Structure" com o conteúdo que antes vivia em `engineering/folder-structure.md`. O skill `folder-arch.md` é deletado. O DAG knowledge passa de 14 para 13 nós. Dependências de `domain-model` que apontavam para `folder-arch` passam a apontar para `blueprint`.

**Why this priority**: Simplificação do DAG. Folder-arch nunca foi um skill independente — é uma seção do blueprint.

**Independent Test**: Verificar que `folder-arch.md` não existe em `.claude/commands/madruga/`, blueprint template tem seção Folder Structure, DAG tem 13 nós.

**Acceptance Scenarios**:

1. **Given** blueprint template atualizado, **When** operador roda `/blueprint fulano`, **Then** output inclui seção "Folder Structure"
2. **Given** DAG knowledge com 13 nós, **When** `/pipeline fulano`, **Then** folder-arch não aparece na lista de nós
3. **Given** nó `domain-model` dependia de `folder-arch`, **When** DAG é atualizado, **Then** `domain-model` depende de `blueprint` (que já inclui folder structure)

---

### User Story 7 — Artefatos migrados de specs/ para epics/ (Priority: P3)

Os artefatos de `specs/001-atomic-skills-dag-pipeline/` e `specs/002-sqlite-foundation/` são movidos para `platforms/madruga-ai/epics/005-atomic-skills-dag/` e `platforms/madruga-ai/epics/006-sqlite-foundation/` respectivamente. O diretório `specs/` é removido. Histórico Git preservado via `git log --follow`.

**Why this priority**: Limpeza necessária mas não bloqueia as demais user stories. Pode ser feita primeiro (por ser pré-requisito conceitual) ou por último.

**Independent Test**: Verificar que `specs/` não existe, artefatos estão nos epic dirs, `git log --follow` mostra histórico.

**Acceptance Scenarios**:

1. **Given** `specs/002-sqlite-foundation/` existe, **When** migração executada, **Then** conteúdo está em `platforms/madruga-ai/epics/006-sqlite-foundation/` e `specs/` não existe
2. **Given** migração concluída, **When** `git log --follow platforms/madruga-ai/epics/006-sqlite-foundation/spec.md`, **Then** histórico completo aparece

---

### User Story 8 — epic_cycle declarado no Copier template (Priority: P2)

O template Copier (`platform.yaml.jinja`) ganha seção `epic_cycle` com os 10 nós do ciclo per-epic (epic-context, specify, clarify, plan, tasks, analyze, implement, verify, qa, reconcile). Cada nó tem `outputs`, `depends`, `gate`, e `optional` (para clarify, qa, reconcile). Novas plataformas scaffolded via `copier copy` já vêm com esta seção. Plataformas existentes recebem via `copier update`.

**Why this priority**: Declaração formal do epic cycle no manifesto. Foundation para que `/pipeline` e `check-platform-prerequisites.sh --epic` funcionem.

**Independent Test**: Scaffoldar nova plataforma com `copier copy`, verificar que `platform.yaml` gerado contém seção `epic_cycle` com 10 nós.

**Acceptance Scenarios**:

1. **Given** template Copier atualizado, **When** `copier copy .specify/templates/platform/ platforms/test-platform/`, **Then** `platform.yaml` contém `epic_cycle.nodes` com 10 nós
2. **Given** plataforma existente `fulano`, **When** `copier update platforms/fulano/`, **Then** `platform.yaml` ganha seção `epic_cycle` (não sobrescreve conteúdo existente customizado)
3. **Given** nó `clarify` marcado `optional: true`, **When** lê `platform.yaml`, **Then** campo `optional` e `skip_condition` presentes

---

### Edge Cases

- O que acontece se `--base-dir` aponta para um path que não existe? → Scripts devem criar o diretório se não existir (mesmo comportamento atual de `specs/`)
- O que acontece se `specs/` já foi deletado e alguém roda script sem `--base-dir`? → Scripts usam default `specs/` e criam se necessário (retrocompatibilidade)
- O que acontece se `epic_cycle_nodes` é consultado para um epic sem registros? → Retorna todos os nós como `pending` (status default)
- O que acontece se o operador invoca um skill pelo nome antigo (ex: `/discuss`)? → Comando não encontrado. Mensagem de erro padrão do Claude Code.
- O que acontece se `copier update` é rodado numa plataforma que já tem `epic_cycle` customizado? → `_skip_if_exists` protege customizações. Merge manual se necessário.

## Requirements

### Functional Requirements

- **FR-001**: Scripts SpecKit (`create-new-feature.sh`, `setup-plan.sh`, `check-prerequisites.sh`) DEVEM aceitar flag `--base-dir <path>` para operar em diretório customizado
- **FR-002**: Quando `--base-dir` não é passado, scripts DEVEM manter comportamento default em `specs/`
- **FR-003**: Script `check-platform-prerequisites.sh` DEVE aceitar flag `--epic <NNN>` para verificar status de nós do epic cycle
- **FR-004**: Script `check-platform-prerequisites.sh` DEVE aceitar flag `--use-db` para consultar SQLite em vez de filesystem
- **FR-005**: Tabela `epic_nodes` (já existente em 001_initial.sql) DEVE ser utilizada para rastrear status dos nós do epic cycle. Colunas: platform_id, epic_id, node_id, status, output_hash, completed_at, completed_by. Nenhuma nova migration necessária
- **FR-006**: Skills renomeados (vision, epic-context, adr, qa) DEVEM funcionar com novos nomes sem aliases
- **FR-007**: Todas as referências a nomes antigos (discuss, adr-gen, test-ai, vision-one-pager, folder-arch) DEVEM ser atualizadas em CLAUDE.md, pipeline-dag-knowledge.md, e scripts
- **FR-008**: Template do blueprint DEVE incluir seção "Folder Structure" com conteúdo absorvido de folder-arch
- **FR-009**: DAG knowledge DEVE ser atualizado para 13 nós (sem folder-arch) com dependências corrigidas
- **FR-010**: Skill `/pipeline` DEVE exibir status de L1 (platform DAG) e L2 (epic cycle) a partir do SQLite
- **FR-011**: Skill `/pipeline` DEVE gerar diagrama Mermaid com cores por status (verde=done, amarelo=pending, cinza=skipped, vermelho=blocked, laranja=stale)
- **FR-012**: Template Copier DEVE incluir seção `epic_cycle` com 10 nós no `platform.yaml.jinja`
- **FR-013**: Artefatos gerados por skills com gate human DEVEM incluir bloco HANDOFF YAML no footer
- **FR-014**: DAG knowledge DEVE incluir campo `handoff_template` em cada nó
- **FR-015**: Artefatos de `specs/001-*` e `specs/002-*` DEVEM ser migrados para epic dirs correspondentes
- **FR-016**: Diretório `specs/` DEVE ser removido após migração

### Key Entities

- **EpicCycleNode**: Registro de status de um nó do epic cycle para um epic específico. Atributos: platform_id, epic_id, node_id, status (pending/done/stale/blocked/skipped), output_hash, completed_at, completed_by. Tabela `epic_nodes` no SQLite.
- **HandoffBlock**: Bloco YAML estruturado no footer de artefatos. Atributos: from (skill origem), to (skill destino), context (texto livre), blockers (lista).
- **PipelineView**: Representação consolidada de L1 + L2 para visualização. Combina dados de `pipeline_nodes` (L1) e `epic_nodes` (L2) com Mermaid dinâmico.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Operador encontra todos os artefatos de um epic (pitch, context, spec, plan, tasks, reports) num único diretório — zero navegação entre `specs/` e `epics/`
- **SC-002**: `/pipeline madruga-ai` mostra status completo de ambos os níveis (L1 + L2) em menos de 5 segundos
- **SC-003**: Zero referências a nomes antigos de skills (discuss, adr-gen, test-ai, vision-one-pager, folder-arch) no codebase ativo
- **SC-004**: Novas plataformas scaffolded via Copier já incluem `epic_cycle` no manifesto sem intervenção manual
- **SC-005**: Contexto entre skills é preservado via HANDOFF blocks — operador não precisa re-explicar decisões ao avançar no pipeline
- **SC-006**: 100% dos testes existentes continuam passando após todas as mudanças (zero regressão)
- **SC-007**: Diretório `specs/` eliminado do repositório

## Assumptions

- O operador é o único usuário do sistema (single-operator). Não há risco de breaking change para terceiros com os renames.
- Epic 005 corresponde a `specs/001-atomic-skills-dag-pipeline/` e epic 006 a `specs/002-sqlite-foundation/`. Mapeamento confirmado pelo histórico do projeto.
- O daemon (epic 008+) consumirá HANDOFF blocks e `epic_cycle` do platform.yaml. O formato definido aqui é estável o suficiente para não requerer breaking changes futuros.
- `copier update` em plataformas existentes adicionará `epic_cycle` sem sobrescrever seções customizadas (comportamento `_skip_if_exists` do Copier).
- Scripts SpecKit existentes (create-new-feature.sh, setup-plan.sh, check-prerequisites.sh) aceitam modificação incremental com `--base-dir` sem reescrita da lógica interna.
