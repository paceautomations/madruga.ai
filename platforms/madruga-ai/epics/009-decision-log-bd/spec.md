# Feature Specification: BD como Source of Truth para Decisions + Memory

**Feature Branch**: `epic/madruga-ai/009-decision-log-bd`
**Created**: 2026-03-29
**Status**: Draft
**Input**: Inverter fluxo de decisoes — BD e a fonte, markdown e a view. Inclui decisions e memory no mesmo epic.

## User Scenarios & Testing

### User Story 1 - Registrar decisao via skill (Priority: P1)

Um operador do pipeline executa um skill (ex: `madruga:adr`) que toma decisoes arquiteturais. A decisao e registrada no BD central e um arquivo markdown e exportado automaticamente no formato Nygard para a pasta `decisions/` da plataforma correspondente.

**Why this priority**: E o fluxo principal — toda decisao deve nascer no BD. Sem isso, nada funciona.

**Independent Test**: Executar `insert_decision()` com dados de uma decisao e verificar que (a) o registro existe no BD com todos os campos, (b) o arquivo ADR-*.md foi exportado no formato Nygard identico ao atual.

**Acceptance Scenarios**:

1. **Given** um BD inicializado com migration 003, **When** um skill chama `insert_decision()` com titulo, contexto, decisao, alternativas e consequencias, **Then** o registro e criado no BD com ID unico, timestamps, e content_hash
2. **Given** uma decisao inserida no BD, **When** `export_decision_to_markdown()` e chamado, **Then** um arquivo ADR-NNN-slug.md e criado na pasta `platforms/<name>/decisions/` com formato Nygard identico ao atual (frontmatter YAML + sections)
3. **Given** uma decisao com status "accepted", **When** uma nova decisao a substitui, **Then** a decisao original tem status "superseded" e campo `superseded_by` apontando para a nova

---

### User Story 2 - Importar ADRs existentes para o BD (Priority: P1)

Um operador executa um comando de import retroativo que le todos os arquivos ADR-*.md existentes (19 da Fulano), parseia o frontmatter YAML e conteudo, e popula a tabela `decisions` no BD.

**Why this priority**: Sem import retroativo, o BD comeca vazio e nao tem valor imediato. Os 19 ADRs da Fulano sao o dataset de validacao.

**Independent Test**: Executar `--import-adrs --platform fulano` e verificar que 19 registros aparecem no BD com campos corretos.

**Acceptance Scenarios**:

1. **Given** 19 arquivos ADR-*.md em `platforms/fulano/decisions/`, **When** o comando de import e executado, **Then** 19 registros sao criados na tabela `decisions` com platform_id="fulano"
2. **Given** um ADR com frontmatter contendo title, status, decision, alternatives, rationale, **When** importado, **Then** os campos correspondentes no BD sao populados corretamente
3. **Given** um ADR ja importado e sem alteracoes, **When** o import e re-executado, **Then** o registro nao e duplicado (upsert via content_hash)

---

### User Story 3 - Consultar decisoes no BD (Priority: P2)

Um operador ou skill consulta decisoes por plataforma, epic, status, tipo ou texto livre. O BD retorna resultados estruturados sem precisar grep em arquivos markdown.

**Why this priority**: E o principal beneficio de ter decisions no BD — queries ricas que markdown nao suporta.

**Independent Test**: Inserir 5 decisoes com diferentes plataformas/status/tipos e executar queries com filtros, verificando resultados corretos.

**Acceptance Scenarios**:

1. **Given** decisoes de multiplas plataformas no BD, **When** `get_decisions(platform_id="fulano")` e chamado, **Then** retorna apenas decisoes da Fulano ordenadas por data
2. **Given** decisoes com diferentes status, **When** consultado com filtro `status="accepted"`, **Then** retorna apenas decisoes aceitas
3. **Given** decisoes com texto no campo `context`, **When** busca FTS5 por palavra-chave, **Then** retorna decisoes que contem o termo no contexto, titulo ou consequencias

---

### User Story 4 - Registrar e consultar memory entries (Priority: P2)

Um operador ou skill registra entradas de memoria (user, feedback, project, reference) no BD. As entradas sao consultaveis por tipo, plataforma ou texto livre. O BD e a fonte canonica; arquivos `.claude/memory/*.md` sao exportados do BD.

**Why this priority**: Memory no BD permite queries cross-session que o sistema de arquivos nao suporta.

**Independent Test**: Inserir memory entries de cada tipo e verificar CRUD completo + busca FTS5.

**Acceptance Scenarios**:

1. **Given** BD inicializado, **When** `insert_memory()` e chamado com tipo "feedback" e conteudo, **Then** o registro e criado com ID unico e timestamps
2. **Given** memories de tipos diferentes, **When** consultado com filtro `type="project"`, **Then** retorna apenas memories do tipo project
3. **Given** arquivos existentes em `.claude/memory/`, **When** o import retroativo e executado, **Then** os arquivos sao parseados e registros criados no BD; a partir dai, BD e a fonte e os arquivos sao exportados do BD

---

### User Story 5 - Rastrear links entre decisoes (Priority: P3)

Um operador consulta quais decisoes dependem de, substituem ou contradizem outras decisoes. O BD mantem um grafo de relacionamentos entre decisoes.

**Why this priority**: Permite impact analysis — saber que mudar ADR-011 afeta ADR-016.

**Independent Test**: Criar 3 decisoes com links (A supersedes B, C depends_on A) e consultar o grafo.

**Acceptance Scenarios**:

1. **Given** duas decisoes no BD, **When** um link "supersedes" e criado entre elas, **Then** o link aparece em queries de ambas as direcoes
2. **Given** decisao A com 3 dependentes, **When** consultado "quais decisoes dependem de A?", **Then** retorna as 3 decisoes corretas
3. **Given** link types (supersedes, depends_on, related, contradicts), **When** consultado por tipo, **Then** retorna apenas links do tipo solicitado

---

### Edge Cases

- O que acontece quando um ADR markdown e editado manualmente apos ser exportado do BD? → Hash mismatch detectado; import re-sincroniza (markdown vence)
- O que acontece quando o BD e corrompido ou deletado? → `--import-adrs` reconstroi a partir dos markdowns existentes (backup natural)
- O que acontece quando dois skills tentam inserir a mesma decisao simultaneamente? → SQLite WAL mode + busy_timeout=5000 garante serialization; upsert via decision_id evita duplicatas
- O que acontece quando um ADR tem frontmatter malformado? → Parser reporta warning e pula o arquivo; nao bloqueia o import dos demais
- O que acontece quando `.claude/memory/` tem arquivos sem frontmatter valido? → Parser extrai o que puder; conteudo sem metadados recebe tipo "project" como default

## Requirements

### Functional Requirements

- **FR-001**: Sistema DEVE permitir inserir decisoes no BD com campos: titulo, contexto, decisao, alternativas, consequencias, status, tipo, tags, platform_id, epic_id, skill
- **FR-002**: Sistema DEVE exportar cada decisao do BD para arquivo markdown no formato Nygard structurally equivalent ao formato atual dos ADRs (mesmas sections e frontmatter fields; whitespace pode diferir)
- **FR-003**: Sistema DEVE importar ADRs markdown existentes para o BD, parseando frontmatter e conteudo das sections (Contexto, Decisao, Alternativas, Consequencias)
- **FR-004**: Sistema DEVE detectar re-import via content_hash (SHA-256) e fazer upsert sem duplicar registros
- **FR-005**: Sistema DEVE suportar busca full-text (FTS5) em decisoes por titulo, contexto e consequencias
- **FR-006**: Sistema DEVE manter tabela de links entre decisoes com tipos: supersedes, depends_on, related, contradicts, amends
- **FR-007**: Sistema DEVE permitir inserir memory entries com tipos: user, feedback, project, reference
- **FR-008**: Sistema DEVE importar arquivos de `.claude/memory/` para tabela memory_entries, parseando frontmatter (name, description, type)
- **FR-009**: Sistema DEVE suportar busca full-text (FTS5) em memory entries por nome, descricao e conteudo
- **FR-010**: Sistema DEVE registrar evento no audit log (tabela events) para cada insercao/atualizacao de decisao ou memory
- **FR-011**: Sistema DEVE suportar batch export de todas as decisoes de uma plataforma para markdown
- **FR-012**: Sistema DEVE auto-numerar ADRs exportados (proximo numero disponivel na pasta decisions/)

### Key Entities

- **Decision**: Registro de decisao arquitetural ou trade-off. Atributos: ID, titulo, contexto, decisao, alternativas, consequencias, status, tipo, tags, platform, epic, skill, number (presente apenas em ADRs formais), hash, timestamps. ADR formal: tem `number` + `skill=adr`. Micro-decision: sem `number`, `skill` indica a origem
- **Decision Link**: Relacionamento entre decisoes. Atributos: from_id, to_id, tipo (supersedes, depends_on, related, contradicts, amends)
- **Memory Entry**: Registro de memoria persistente. Atributos: ID, tipo (user/feedback/project/reference), nome, descricao, conteudo, source, platform, hash, timestamps
- **Event**: Registro de audit trail (append-only). Ja existente no schema.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% dos 19 ADRs existentes da Fulano sao importados corretamente no BD com zero perda de informacao
- **SC-002**: Markdown exportado do BD e structurally equivalent ao formato Nygard atual (mesmas sections, mesmos frontmatter fields, conteudo semantico preservado; whitespace pode diferir)
- **SC-003**: Busca full-text retorna resultados relevantes em menos de 100ms para um dataset de 50+ decisoes
- **SC-004**: Toda decisao registrada via skill gera automaticamente o arquivo markdown correspondente sem intervencao manual
- **SC-005**: Re-import de ADRs nao editados resulta em zero alteracoes no BD (idempotencia verificavel via hash)
- **SC-006**: Memory entries importadas de `.claude/memory/` sao queryaveis por tipo e texto livre

## Clarifications

### Session 2026-03-29

- Q: Qual e a direcao canonica para memory? → A: BD e a fonte; `.claude/memory/*.md` e exportado do BD (Alternativa B consistente com decisions)
- Q: Micro-decisions usam tipos diferentes de ADRs formais? → A: Mesmo enum de decision_type. Diferenciar ADR formal vs micro-decision pelo campo `skill` (adr = formal) e presenca de `number` (ADRs tem numero, micro-decisions nao)

## Assumptions

- Python 3.11+ garante FTS5 disponivel no sqlite3 da stdlib
- O formato de frontmatter YAML dos ADRs existentes e consistente (title, status, decision, alternatives, rationale como campos do YAML)
- SQLite WAL mode ja configurado em get_conn() suporta concorrencia necessaria
- O portal le ADRs como arquivos markdown estaticos — nao acessa o BD diretamente
- `.claude/memory/` usa frontmatter com campos name, description, type conforme documentado no auto-memory system
- Nenhuma dependencia externa alem de pyyaml (ja presente para seed_from_filesystem)
