# Feature Specification: Commit Traceability

**Feature Branch**: `epic/madruga-ai/023-commit-traceability`
**Created**: 2026-04-08
**Status**: Draft
**Input**: Vincular cada commit a um epic ou marcar como ad-hoc. Visibilidade total de mudanças no DB e no portal.

## User Scenarios & Testing

### User Story 1 - Consultar commits de um epic (Priority: P1)

Como operador da plataforma, quero ver todos os commits associados a um epic específico para entender o volume e escopo de mudanças que compuseram aquela entrega.

**Why this priority**: É a consulta mais frequente — ao revisar um epic (reconcile, QA, retrospectiva), a primeira pergunta é "o que mudou?". Sem isso, o operador precisa rodar `git log` manualmente com filtros de branch.

**Independent Test**: Pode ser testado executando o backfill para um epic conhecido (ex: epic 012) e verificando que o DB retorna os commits corretos via `get_commits_by_epic('012-...')`.

**Acceptance Scenarios**:

1. **Given** o backfill foi executado e o epic 012 tem commits no DB, **When** o operador consulta commits do epic 012 via DB query, **Then** o sistema retorna todos os commits que pertenceram à branch `epic/madruga-ai/012-*`, com SHA, mensagem, autor e data.
2. **Given** um epic ainda não tem commits no DB, **When** o operador consulta commits desse epic, **Then** o sistema retorna uma lista vazia (sem erro).
3. **Given** um commit foi feito na branch do epic 023, **When** o post-commit hook roda, **Then** o commit aparece automaticamente no DB vinculado ao epic 023.

---

### User Story 2 - Registrar commits automaticamente via hook (Priority: P1)

Como desenvolvedor trabalhando em um epic, quero que cada commit feito na branch do epic seja registrado automaticamente no DB sem nenhuma ação manual.

**Why this priority**: É o mecanismo central de captura — sem o hook, nenhum commit novo é rastreado. Compartilha prioridade P1 com a consulta porque são indissociáveis (captura sem consulta é inútil e vice-versa).

**Independent Test**: Fazer um commit em uma branch `epic/madruga-ai/023-*` com o hook instalado e verificar que a tabela `commits` tem uma nova row com os dados corretos.

**Acceptance Scenarios**:

1. **Given** o post-commit hook está instalado, **When** um commit é feito na branch `epic/madruga-ai/023-commit-traceability`, **Then** o DB registra o SHA, mensagem, autor, data, plataforma `madruga-ai`, epic `023-commit-traceability` e lista de arquivos afetados.
2. **Given** o hook está instalado e um commit toca arquivos em `platforms/prosauai/` e `platforms/madruga-ai/`, **When** o commit é feito em main, **Then** o DB registra 2 rows — uma para cada plataforma — ambas com epic_id NULL (ad-hoc).
3. **Given** o hook falha (ex: DB locked), **When** o commit é feito, **Then** o commit completa normalmente (hook não bloqueia) e um aviso é emitido em stderr.
4. **Given** um commit contém a tag `[epic:015]` na mensagem, **When** o hook roda, **Then** o epic_id é definido como `015-*` (override do branch pattern).

---

### User Story 3 - Visualizar commits no portal (Priority: P2)

Como operador da plataforma, quero ver uma aba "Changes" no control panel do portal com tabela de commits, filtros e estatísticas para ter visibilidade sem sair do browser.

**Why this priority**: A visualização depende dos dados (P1). É alto valor porque elimina a necessidade de rodar `git log` localmente, mas pode ser entregue após o backend estar funcional.

**Independent Test**: Acessar o portal, navegar até o control panel, abrir a aba "Changes" e verificar que a tabela mostra commits com colunas corretas e filtros funcionando.

**Acceptance Scenarios**:

1. **Given** o DB tem commits de múltiplos epics e commits ad-hoc, **When** o operador abre a aba "Changes" no portal, **Then** a tabela exibe: SHA (link para GitHub), mensagem, plataforma, epic (ou "ad-hoc"), data — ordenados por data decrescente.
2. **Given** a aba "Changes" está aberta, **When** o operador filtra por plataforma "prosauai", **Then** apenas commits que tocam a plataforma prosauai são exibidos.
3. **Given** a aba "Changes" está aberta, **When** o operador filtra por tipo "ad-hoc", **Then** apenas commits sem epic vinculado são exibidos.
4. **Given** o DB tem commits, **When** a aba "Changes" carrega, **Then** stats são exibidas: total commits por epic e percentual ad-hoc vs epic.

---

### User Story 4 - Popular histórico retroativo (Priority: P2)

Como operador, quero executar o backfill para popular o DB com todo o histórico de commits desde o epic 001 para ter rastreabilidade completa desde o início do projeto.

**Why this priority**: Essencial para histórico completo, mas é execução única (one-time). Pode ser feito após hook e DB estarem funcionando.

**Independent Test**: Executar o backfill no repositório atual e verificar que commits do epic 001 (21 commits conforme pitch) estão no DB, commits de epics subsequentes estão corretamente vinculados, e commits diretos em main estão marcados como ad-hoc.

**Acceptance Scenarios**:

1. **Given** o DB está vazio de commits, **When** o backfill é executado, **Then** todos os commits desde o primeiro (5f62946) são registrados no DB com plataforma e epic corretos.
2. **Given** commits pré-epic-006 (5f62946..d6befe0), **When** o backfill os processa, **Then** todos são vinculados ao epic `001-inicio-de-tudo`.
3. **Given** merges de branches `epic/*` existem no histórico, **When** o backfill os processa, **Then** os commits individuais de cada branch são vinculados ao epic correspondente.
4. **Given** o backfill já foi executado antes, **When** é executado novamente, **Then** nenhum commit duplicado é criado (idempotência via INSERT OR IGNORE no SHA UNIQUE).

---

### User Story 5 - Reseed corrige commits ausentes (Priority: P3)

Como operador, quero que o `post_save.py --reseed` sincronize commits para corrigir gaps quando o hook falhou ou commits foram feitos em outro ambiente.

**Why this priority**: Safety net — só é necessário quando algo deu errado. Menor frequência de uso, mas garante consistência.

**Independent Test**: Remover um commit do DB manualmente, rodar reseed, e verificar que o commit reaparece.

**Acceptance Scenarios**:

1. **Given** um commit existe no git mas não no DB (hook falhou), **When** reseed é executado, **Then** o commit é inserido no DB com classificação correta.
2. **Given** todos os commits já estão no DB, **When** reseed é executado, **Then** nenhuma duplicata é criada e a execução completa sem erros.

---

### Edge Cases

- O que acontece quando o commit toca apenas arquivos fora de `platforms/`? → Classificado como plataforma `madruga-ai` (fallback default).
- Como lidar com commits de merge (merge commits)? → Registrados normalmente; o backfill usa merge commits para reconstruir a associação branch→epic.
- O que acontece se o DB não existir quando o hook roda? → Hook falha silenciosamente (best-effort), commit não é bloqueado. Reseed corrige depois.
- Como tratar commits com squash? → Registrar o merge commit com referência ao branch de origem; commits individuais do branch são perdidos no squash por design do git.
- O que acontece com commits em branches que não são `epic/*` nem `main`? → Se o branch não segue o padrão `epic/<platform>/<NNN>`, epic_id = NULL (ad-hoc). Plataforma inferida por file path ou fallback madruga-ai.
- Commit vazio (`--allow-empty`)? → Registrado com files_json = [] (lista vazia). Não é bloqueado.

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE criar uma tabela `commits` no SQLite com campos: id, sha (UNIQUE), message, author, platform_id, epic_id (nullable), source, committed_at, files_json, created_at.
- **FR-002**: O sistema DEVE fornecer funções CRUD no módulo DB: `insert_commit`, `get_commits_by_epic`, `get_commits_by_platform`, `get_adhoc_commits`.
- **FR-003**: O sistema DEVE registrar automaticamente cada commit via post-commit hook ao ser feito no repositório.
- **FR-004**: O hook DEVE identificar a plataforma com prioridade: (1) branch match `epic/<platform>/<NNN>`, (2) file paths em `platforms/<X>/`, (3) fallback `madruga-ai`.
- **FR-005**: O hook DEVE identificar o epic com prioridade: (1) branch match `epic/<platform>/<NNN-slug>`, (2) tag `[epic:NNN]` na mensagem, (3) NULL (ad-hoc).
- **FR-006**: Para commits que tocam múltiplas plataformas, o sistema DEVE registrar uma row por plataforma afetada.
- **FR-007**: O hook DEVE ser best-effort — se falhar, o commit não é bloqueado. Erros devem ir para stderr.
- **FR-008**: O sistema DEVE fornecer um script de backfill que popula o histórico de commits desde o epic 001.
- **FR-009**: O backfill DEVE ser idempotente — re-execução não cria duplicatas (INSERT OR IGNORE no SHA UNIQUE).
- **FR-010**: O backfill DEVE usar estratégia híbrida: merge history para epic branches + first-parent para commits diretos em main.
- **FR-011**: Commits pré-epic-006 (5f62946..d6befe0) DEVEM ser vinculados ao epic `001-inicio-de-tudo`.
- **FR-012**: O portal DEVE exibir uma aba "Changes" no control panel com tabela de commits.
- **FR-013**: A aba "Changes" DEVE suportar filtros por: plataforma, epic, tipo (epic/ad-hoc), período.
- **FR-014**: A aba "Changes" DEVE exibir estatísticas: total commits por epic, percentual ad-hoc vs epic.
- **FR-015**: O SHA na tabela do portal DEVE ser um link clicável para o commit no GitHub.
- **FR-016**: O reseed (`post_save.py --reseed`) DEVE incluir sincronização de commits via `git log`.
- **FR-017**: O hook DEVE completar em menos de 500ms para não impactar a experiência de commit.
- **FR-018**: Os dados de commits DEVEM ser exportados para JSON estático (padrão existente de pipeline-status.json) para consumo pelo portal.

### Key Entities

- **Commit**: Representa um commit git registrado no DB. Atributos: SHA (identificador único), mensagem, autor, plataforma associada, epic associado (opcional), fonte de registro (hook/backfill/manual), data do commit, lista de arquivos afetados.
- **Platform**: Plataforma existente no sistema (ex: madruga-ai, prosauai). Relação 1:N com commits.
- **Epic**: Epic existente na pipeline. Relação 1:N com commits. Pode ser NULL para commits ad-hoc. Sem FK hard — relação lógica por texto.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% dos commits feitos com o hook instalado são registrados no DB em menos de 500ms.
- **SC-002**: O backfill captura pelo menos 95% dos commits históricos com associação correta de epic (conforme pitch, ~95% de precisão para commits antigos).
- **SC-003**: Os 21 commits do epic 001 estão corretamente vinculados no DB após backfill.
- **SC-004**: O operador consegue responder "quais commits compuseram o epic X?" em menos de 10 segundos via portal (vs. minutos com `git log` manual).
- **SC-005**: Re-execução do backfill não cria duplicatas (0 rows adicionais em segunda execução).
- **SC-006**: Falha do hook não impacta o fluxo de commit (0 commits bloqueados por falha de hook).
- **SC-007**: A aba "Changes" no portal carrega e exibe dados corretamente com filtros funcionais.

## Assumptions

- O repositório usa git como VCS e a estrutura de branches `epic/<platform>/<NNN-slug>` é seguida consistentemente (ref: ADR-004, pipeline contract).
- O SQLite DB (`.pipeline/madruga.db`) existe e está em WAL mode com busy_timeout=5000ms (ref: ADR-012).
- O portal já tem um control panel com abas (Execution, Observability) e suporta adição de novas abas.
- O padrão de JSON export estático (pipeline-status.json) é o mecanismo de comunicação entre scripts Python e portal React/Astro.
- Commits de merge squashados perdem granularidade individual — isso é aceitável e inerente ao design do git.
- O hook Python executará em ~200ms na maioria dos ambientes (máquina local, SSD), dentro do limite de 500ms.
- A ferramenta `make install-hooks` ou equivalente será o mecanismo de instalação do hook (hooks git não são versionados automaticamente).
- O campo `epic_id` é TEXT sem FK hard porque epics podem não existir no DB quando o hook registra o commit (ex: backfill retroativo).
- Scripts seguem o limite de <300 LOC cada (hook ~150 LOC, backfill ~200 LOC, DB functions ~80 LOC integradas em db_pipeline.py).

---
handoff:
  from: speckit.specify
  to: speckit.clarify
  context: "Spec completa para commit traceability — 5 user stories, 18 FRs, 7 success criteria. Pitch muito detalhado com 9 decisões capturadas. Sem [NEEDS CLARIFICATION] pendentes. Pronta para clarify ou plan direto."
  blockers: []
  confidence: Alta
  kill_criteria: "Se a decisão de usar SQLite para commits for revertida (ex: migração para PostgreSQL), toda a abordagem de hook+backfill precisa ser revista."
