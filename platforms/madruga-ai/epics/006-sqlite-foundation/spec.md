# Feature Specification: SQLite Foundation

**Feature Branch**: `002-sqlite-foundation`
**Created**: 2026-03-29
**Status**: Draft
**Input**: SQLite foundation for madruga.ai pipeline — BD para estado, CI workflow, guardrails de hallucination

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pipeline State Persistence (Priority: P1)

Como arquiteto, quero que toda skill que gera um artefato registre automaticamente no banco de dados: qual nó completou, quando, o hash do output, e as decisões tomadas. Assim, `/pipeline` pode consultar estado real via SQL em vez de scan de filesystem.

**Why this priority**: Fundação de toda observabilidade. Sem BD, pipeline status depende de file existence (0 bytes conta como "done"). Staleness invisível. Decisions perdidas entre sessões.

**Independent Test**: Rodar `python3 -c "from db import get_conn, migrate; migrate()"` — BD criado com 8 tabelas. Inserir pipeline_node e consultar — round-trip funciona.

**Acceptance Scenarios**:

1. **Given** repo sem `.pipeline/madruga.db`, **When** `db.migrate()` é chamado, **Then** BD é criado com 8 tabelas e todos indexes
2. **Given** BD inicializado, **When** `db.upsert_pipeline_node('prosauai', 'vision', 'done', output_hash='sha256:abc')`, **Then** `db.get_pipeline_nodes('prosauai')` retorna o nó com status 'done'
3. **Given** BD com nós existentes, **When** `db.get_stale_nodes('prosauai')`, **Then** retorna nós cujas dependências têm `completed_at` mais recente
4. **Given** BD inicializado, **When** `db.seed_from_filesystem('prosauai')` com plataforma existente, **Then** tabelas `platforms`, `pipeline_nodes`, e `epics` são populadas do filesystem
5. **Given** BD já populado, **When** `db.seed_from_filesystem('prosauai')` rodado novamente, **Then** upsert atualiza sem duplicar (idempotente)

---

### User Story 2 - CI Pipeline (Priority: P1)

Como desenvolvedor, quero que toda PR no GitHub seja validada automaticamente: lint de plataformas, build de modelos LikeC4, e teste do template Copier. PRs inválidas não mergeiam.

**Why this priority**: Previne regressões. `platform.yaml` sem `pipeline:` nunca mais entra no main. Modelos LikeC4 inválidos são pegos antes do merge.

**Independent Test**: Submeter PR com `platform.yaml` inválido — workflow deve falhar e bloquear merge.

**Acceptance Scenarios**:

1. **Given** PR com alteração em `platforms/`, **When** CI roda, **Then** `platform.py lint --all` executa e bloqueia merge se falhar
2. **Given** PR com alteração em `model/*.likec4`, **When** CI roda, **Then** `likec4 build` executa para cada plataforma com diretório model/
3. **Given** PR com alteração em `.specify/templates/`, **When** CI roda, **Then** copier copy roda com `--defaults` em dir temporário e valida output
4. **Given** push to main, **When** CI roda, **Then** todos os 3 jobs executam em paralelo

---

### User Story 3 - Prerequisites via BD (Priority: P2)

Como arquiteto, quero que o check de prerequisites consulte o banco de dados quando disponível, detectando não só "arquivo existe" mas "arquivo foi gerado pelo pipeline, não está stale, e tem hash válido".

**Why this priority**: Prerequisites robustos previnem execução de skills com inputs desatualizados. Complementa US1.

**Independent Test**: Rodar `check-platform-prerequisites.sh --json --status --platform prosauai --use-db` — output JSON inclui hash e timestamps do BD.

**Acceptance Scenarios**:

1. **Given** BD populado via seed, **When** `--use-db --status --platform prosauai`, **Then** output JSON inclui `output_hash` e `completed_at` para cada nó done
2. **Given** BD com nó stale, **When** `--use-db --skill blueprint`, **Then** output inclui warning `"stale": true` com razão
3. **Given** BD não existe, **When** `--use-db` passado, **Then** fallback para file existence com warning "DB not found, using filesystem"

---

### User Story 4 - Hallucination Guardrails (Priority: P2)

Como arquiteto, quero que skills de research admitam quando não têm dados em vez de fabricar sources. URLs verificáveis são obrigatórias para afirmações factuais.

**Why this priority**: Qualidade dos artefatos de decisão. ADRs com sources fabricadas propagam decisões erradas por todo o pipeline.

**Independent Test**: Grep por `[DADOS INSUFICIENTES]` em tech-research.md e adr-gen.md — presente em ambos.

**Acceptance Scenarios**:

1. **Given** `tech-research.md`, **When** inspecionada, **Then** Cardinal Rule contém diretiva `[DADOS INSUFICIENTES]`
2. **Given** `adr-gen.md`, **When** inspecionada, **Then** Cardinal Rule contém diretiva de URL obrigatório
3. **Given** `pipeline-dag-knowledge.md`, **When** inspecionada, **Then** auto-review checklist universal inclui check para sources verificáveis

---

### Edge Cases

- **BD corrompido**: `db.py` detecta e recria via migration (`CREATE TABLE IF NOT EXISTS`)
- **Migration parcial**: Cada migration roda em transaction — falha faz rollback
- **Concurrent access**: WAL mode permite leituras concorrentes. Writes serializados com `busy_timeout=5000`
- **Platform sem pipeline section**: `seed_from_filesystem` faz skip com warning
- **Disco cheio**: SQLite retorna SQLITE_FULL — `db.py` catch e reporta mensagem clara
- **CI sem likec4 instalado**: Job falha com mensagem clara "likec4 not found"
- **CI sem copier instalado**: Job falha com mensagem clara "copier not found"

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistema DEVE criar `.pipeline/madruga.db` automaticamente na primeira chamada a `db.get_conn()`
- **FR-002**: Sistema DEVE rodar migrations SQL de `.pipeline/migrations/` em ordem numérica, tracking em tabela `_migrations`
- **FR-003**: Sistema DEVE criar 8 tabelas: platforms, pipeline_nodes, epics, epic_nodes, decisions, artifact_provenance, pipeline_runs, events
- **FR-004**: Sistema DEVE fornecer funções upsert para: platforms, pipeline_nodes, epics, epic_nodes
- **FR-005**: Sistema DEVE fornecer funções insert para: decisions, artifact_provenance, pipeline_runs, events
- **FR-006**: Sistema DEVE fornecer funções query: get_pipeline_nodes, get_epics, get_epic_nodes, get_decisions, get_stale_nodes, get_platform_status, get_epic_status
- **FR-007**: Sistema DEVE computar SHA256 hash de arquivos via `compute_file_hash(path)`
- **FR-008**: Sistema DEVE importar estado existente do filesystem via `seed_from_filesystem(platform_id)` de forma idempotente
- **FR-009**: `check-platform-prerequisites.sh` DEVE aceitar flag `--use-db` para consultar SQLite, com fallback para filesystem
- **FR-010**: GitHub Actions workflow DEVE rodar `platform.py lint --all` em toda PR e push to main
- **FR-011**: GitHub Actions workflow DEVE rodar `likec4 build` para cada plataforma com diretório model/
- **FR-012**: GitHub Actions workflow DEVE validar template Copier com `copier copy --defaults` em dir temporário
- **FR-013**: `tech-research.md` DEVE conter diretiva `[DADOS INSUFICIENTES]` na Cardinal Rule
- **FR-014**: `adr-gen.md` DEVE conter diretiva de URL obrigatório e `[FONTE NÃO VERIFICADA]` na Cardinal Rule
- **FR-015**: `pipeline-dag-knowledge.md` DEVE incluir instruções de integração SQLite no step 5 do contrato
- **FR-016**: `.pipeline/madruga.db` DEVE estar no `.gitignore`
- **FR-017**: `.pipeline/migrations/*.sql` DEVE estar versionado no git
- **FR-018**: `db.py` DEVE usar apenas stdlib Python (sqlite3, hashlib, json, pathlib, uuid) — zero dependências externas
- **FR-019**: BD DEVE usar WAL mode, foreign_keys=ON, e busy_timeout=5000
- **FR-020**: Cada migration DEVE rodar em transaction para rollback em caso de falha

### Key Entities

- **Platform**: Plataforma documentada (prosauai, madruga-ai). PK: platform_id (kebab-case). Atributos: name, title, lifecycle, repo_path
- **Pipeline Node**: Nó do DAG nível 1. Status do artefato de documentação. PK: (platform_id, node_id). Atributos: status, output_hash, completed_at, completed_by
- **Epic**: Epic Shape Up com pitch e ciclo de implementação. PK: (platform_id, epic_id). Atributos: title, status, appetite, branch_name
- **Epic Node**: Nó do DAG nível 2. Status do step no ciclo per-epic. PK: (platform_id, epic_id, node_id). Atributos: status, output_hash, completed_at
- **Decision**: Decisão tomada durante skill. Unifica ADR registry e decision log. PK: decision_id. Atributos: skill, title, status, decisions_json, assumptions_json
- **Artifact Provenance**: Registro de quem gerou cada artefato. PK: (platform_id, file_path). Atributos: generated_by, output_hash, generated_at
- **Pipeline Run**: Execução de um nó com tracking de tokens/custo. PK: run_id. Atributos: agent, tokens_in, tokens_out, cost_usd, duration_ms
- **Event**: Log imutável de ações no sistema. PK: event_id (autoincrement). Atributos: entity_type, entity_id, action, actor, payload

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Migration cria 8 tabelas em menos de 1 segundo
- **SC-002**: CRUD round-trip (insert + query) completa em menos de 50ms para qualquer tabela
- **SC-003**: Seed de plataforma com 15 epics e 14 pipeline nodes completa em menos de 5 segundos
- **SC-004**: CI workflow completa em menos de 5 minutos (3 jobs paralelos)
- **SC-005**: Zero PRs com platform.yaml inválido chegam ao main após CI ativado
- **SC-006**: 100% das skills de research contêm guardrails verificáveis via grep
- **SC-007**: `--use-db` retorna status com hash e timestamps para plataformas com BD populado
- **SC-008**: `db.py` tem zero dependências externas (apenas stdlib)

## Assumptions

- Python 3.11+ disponível no ambiente (já é prerequisite do madruga.ai)
- `sqlite3` module disponível (built-in no CPython padrão)
- GitHub Actions disponível no repositório com runners Ubuntu
- `likec4` CLI disponível via `npx likec4` nos runners (node_modules)
- `copier` >= 9.4.0 instalável via `pip install copier` nos runners
- Sistema single-user (sem concorrência de writes significativa)
- BD é estado local — reproduzível via `seed_from_filesystem()` a partir dos artefatos no git
- Plataformas prosauai e madruga-ai já possuem seção `pipeline:` no platform.yaml (pre-work completo)
