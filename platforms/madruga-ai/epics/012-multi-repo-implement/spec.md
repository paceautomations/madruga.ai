# Feature Specification: Multi-repo Implement

**Feature Branch**: `epic/madruga-ai/012-multi-repo-implement`
**Created**: 2026-03-31
**Status**: Draft
**Input**: Epic 012 — habilitar speckit.implement para operar em repositorios externos via git worktree

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clonar Repositorio Externo (Priority: P1)

O arquiteto precisa que o sistema tenha uma copia local do repositorio de codigo da plataforma-alvo antes de executar qualquer ciclo de implementacao. Ao executar um comando de clone/ensure, o sistema clona o repositorio automaticamente (SSH primeiro, fallback HTTPS) ou atualiza se ja existir localmente.

**Why this priority**: Sem o repositorio local, nenhuma operacao de implementacao e possivel. E o pre-requisito fundamental de todo o fluxo.

**Independent Test**: Executar `platform.py ensure-repo fulano` e verificar que o repositorio `fulano-api` existe em `~/repos/paceautomations/fulano-api/` com `.git` valido.

**Acceptance Scenarios**:

1. **Given** plataforma fulano com `repo: {org: paceautomations, name: fulano-api}` em platform.yaml, **When** o arquiteto executa `platform.py ensure-repo fulano`, **Then** o repositorio e clonado em `{repos_base_dir}/paceautomations/fulano-api/` via SSH
2. **Given** repositorio ja existe localmente, **When** o arquiteto executa `platform.py ensure-repo fulano`, **Then** o sistema executa `git fetch --all --prune` sem re-clonar
3. **Given** SSH falha (sem chave configurada), **When** clone via SSH retorna erro, **Then** o sistema tenta HTTPS automaticamente e completa o clone
4. **Given** clone parcial (diretorio existe mas `.git` incompleto), **When** o arquiteto executa ensure-repo, **Then** o sistema detecta inconsistencia, remove o diretorio parcial e re-clona do zero
5. **Given** plataforma self-referencing (madruga-ai, `repo.name: madruga.ai`), **When** o arquiteto executa ensure-repo, **Then** o sistema identifica self-ref e retorna o path do repo atual sem clonar

---

### User Story 2 - Criar Worktree para Epic (Priority: P1)

O arquiteto precisa de um ambiente isolado para implementar codigo de um epic sem interferir no working tree principal do repositorio. O sistema cria um git worktree dedicado com branch nomeada conforme convencao da plataforma.

**Why this priority**: Worktree e o mecanismo de isolamento que permite implementacao segura sem afetar trabalho em andamento no repositorio.

**Independent Test**: Executar `platform.py worktree fulano 001-channel-pipeline` e verificar que o worktree existe com a branch correta.

**Acceptance Scenarios**:

1. **Given** repositorio fulano-api clonado localmente, **When** o arquiteto executa `platform.py worktree fulano 001-channel-pipeline`, **Then** um worktree e criado em `{repos_base_dir}/fulano-api-worktrees/001-channel-pipeline/` com branch `epic/fulano/001-channel-pipeline` baseada em `main`
2. **Given** worktree ja existe (crash recovery), **When** o arquiteto executa o mesmo comando, **Then** o sistema reutiliza o worktree existente sem erro
3. **Given** worktree criado anteriormente, **When** o arquiteto executa cleanup apos merge, **Then** o sistema remove o worktree e deleta a branch local
4. **Given** platform.yaml define `base_branch: develop`, **When** worktree e criado, **Then** a branch e baseada em `develop` e nao em `main`

---

### User Story 3 - Implementar em Repositorio Externo (Priority: P1)

O arquiteto executa o ciclo de implementacao de um epic e o sistema automaticamente resolve o repositorio da plataforma, prepara o worktree, injeta contexto dos documentos (spec/plan/tasks do madruga.ai) e invoca `claude -p` com `--cwd` apontando para o worktree do repositorio externo.

**Why this priority**: E o caso de uso principal — o orquestrador que conecta documentacao (madruga.ai) com codigo (repo externo).

**Independent Test**: Executar `implement_remote.py --platform fulano --epic 001-channel-pipeline` e verificar que `claude -p` foi invocado com cwd no worktree correto e prompt contendo spec+plan+tasks.

**Acceptance Scenarios**:

1. **Given** epic 001 tem spec.md, plan.md e tasks.md em `platforms/fulano/epics/001-channel-pipeline/`, **When** o arquiteto executa implement_remote.py, **Then** o sistema le os artefatos, compoe um prompt concatenado e invoca `claude -p --cwd={worktree_path}` com o conteudo
2. **Given** repositorio nao existe localmente, **When** implement_remote.py e executado, **Then** o sistema executa ensure_repo automaticamente antes de criar o worktree
3. **Given** `claude -p` excede o timeout (30min default), **When** timeout e atingido, **Then** o processo e encerrado com mensagem de erro clara e o worktree e preservado para retry
4. **Given** plataforma self-referencing (madruga-ai), **When** implement_remote.py e executado, **Then** o sistema pula clone/worktree e opera diretamente no repo atual

---

### User Story 4 - Criar PR no Repositorio Externo (Priority: P2)

Apos a implementacao, o sistema faz push da branch e cria um Pull Request no repositorio correto usando `gh pr create` com cwd no worktree.

**Why this priority**: Complementa o fluxo de implementacao. Pode ser executado manualmente se a automacao falhar.

**Independent Test**: Apos implementacao, executar push + PR e verificar que o PR aparece no repositorio correto no GitHub.

**Acceptance Scenarios**:

1. **Given** worktree com commits de implementacao, **When** PR e solicitado, **Then** o sistema executa `git push -u origin {branch}` seguido de `gh pr create --base {base_branch}` com cwd no worktree
2. **Given** push falha (sem permissao), **When** erro de push, **Then** mensagem de erro clara indicando problema de permissao
3. **Given** PR ja existe para a branch, **When** PR e solicitado novamente, **Then** o sistema detecta e retorna a URL do PR existente

---

### Edge Cases

- O que acontece se o repositorio foi deletado remotamente? → ensure_repo falha com mensagem clara "repositorio nao encontrado"
- O que acontece se a branch do epic ja existe no remote? → worktree detecta e reutiliza (checkout ao inves de criar nova branch)
- O que acontece se `gh` CLI nao esta instalado? → PR creation falha com mensagem "gh CLI nao encontrado — instale via https://cli.github.com/"
- O que acontece se `platform.yaml` nao tem bloco `repo:`? → erro com mensagem "plataforma {name} nao tem repo: configurado em platform.yaml"
- O que acontece se o prompt composto excede 100KB? → truncar artefatos mais antigos (context.md primeiro), manter tasks.md completo
- O que acontece se Ctrl+C durante `claude -p`? → worktree preservado, log warning, proximo run reutiliza o worktree existente

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistema DEVE clonar repositorios via SSH, com fallback automatico para HTTPS em caso de falha
- **FR-002**: Sistema DEVE detectar repositorios ja existentes e executar fetch ao inves de clone
- **FR-003**: Sistema DEVE detectar clones parciais (diretorio sem `.git` valido) e re-clonar automaticamente
- **FR-004**: Sistema DEVE criar git worktrees isolados com branch nomeada por `{epic_branch_prefix}{epic_slug}`
- **FR-005**: Sistema DEVE reutilizar worktrees existentes (crash recovery) ao inves de falhar
- **FR-006**: Sistema DEVE ler `repo.org`, `repo.name`, `repo.base_branch` e `repo.epic_branch_prefix` de `platform.yaml`
- **FR-007**: Sistema DEVE detectar plataformas self-referencing e pular clone/worktree
- **FR-008**: Sistema DEVE ler artefatos de epic (spec.md, plan.md, tasks.md, context.md) do diretorio `platforms/<name>/epics/<NNN>/` e injetar como contexto no prompt
- **FR-009**: Sistema DEVE invocar `claude -p --cwd={worktree_path}` com prompt composto contendo artefatos do epic
- **FR-010**: Sistema DEVE fazer push da branch e criar PR via `gh pr create` com `cwd=worktree`
- **FR-011**: Sistema DEVE oferecer comandos CLI `ensure-repo` e `worktree` via `platform.py`
- **FR-012**: Sistema DEVE usar lockfile com PID para serializar operacoes de clone concorrentes no mesmo repositorio
- **FR-013**: Sistema DEVE limpar worktrees (remove + delete branch) via comando explicito de cleanup
- **FR-014**: Sistema DEVE respeitar timeout configuravel para `claude -p` (default 30min, via env `MADRUGA_IMPLEMENT_TIMEOUT`)

### Non-Functional Requirements

- **NFR-001**: Apenas stdlib Python + pyyaml — sem dependencias novas
- **NFR-002**: Sync subprocess (sem asyncio) — compativel com uso CLI interativo
- **NFR-003**: Total de codigo novo < 500 LOC (excluindo testes)
- **NFR-004**: Todos os caminhos via `pathlib.Path` — sem string concatenation para paths
- **NFR-005**: Logging via `logging.getLogger(__name__)` — INFO default, DEBUG via flag `-v`

### Key Entities

- **Platform**: Entidade central com `repo_org`, `repo_name`, `base_branch`, `epic_branch_prefix`. Fonte: platform.yaml.
- **Repository**: Repositorio git local em `{repos_base_dir}/{org}/{name}`. Pode ser clonado (externo) ou self-ref (este repo).
- **Worktree**: Copia isolada de um repositorio para trabalho em um epic especifico. Path: `{repos_base_dir}/{name}-worktrees/{epic_slug}/`.
- **Epic Artifacts**: Conjunto de documentos (pitch.md, context.md, spec.md, plan.md, tasks.md) que vivem em `platforms/<name>/epics/<NNN>/` no madruga.ai.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Arquiteto consegue clonar repositorio externo (fulano-api) em menos de 2 minutos via um unico comando
- **SC-002**: Worktree e criado com branch correta em menos de 5 segundos
- **SC-003**: Implementacao remota (ensure_repo → worktree → claude -p) funciona end-to-end sem intervencao manual alem do comando inicial
- **SC-004**: PR e criado no repositorio correto (fulano-api) e nao no madruga.ai
- **SC-005**: Crash recovery funciona — apos interrupcao, o proximo run reutiliza o worktree existente sem erro
- **SC-006**: Plataformas self-referencing (madruga-ai) continuam funcionando sem regressao

## Assumptions

- SSH keys estao configuradas para o GitHub do operador (fallback HTTPS disponivel)
- `gh` CLI esta instalado e autenticado para criar PRs
- `claude` CLI esta instalado com subscription ativa
- `platform.yaml` de plataformas com repo externo ja tem o bloco `repo:` configurado (fulano ja tem)
- `repos_base_dir` default e `~/repos/` — consistente com a convencao do general
- Operador unico — concorrencia de clones e edge case, lockfile e precaucao
- `pyyaml` ja e dependencia do projeto — nao viola constraint stdlib-only

---
handoff:
  from: speckit.specify
  to: speckit.clarify
  context: "Spec completa com 4 user stories, 14 FRs, 5 NFRs. Zero markers [NEEDS CLARIFICATION]. Pronto para plan ou clarify (se necessario)."
  blockers: []
  confidence: Alta
  kill_criteria: "Se claude -p nao suportar --cwd para repos externos, abordagem inteira precisa ser revista"
