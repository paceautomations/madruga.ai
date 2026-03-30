# Implementation Plan: BD como Source of Truth para Decisions + Memory

**Branch**: `epic/madruga-ai/009-decision-log-bd` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `platforms/madruga-ai/epics/009-decision-log-bd/spec.md`

## Summary

Inverter o fluxo de decisoes e memory: BD (SQLite) passa a ser a fonte canonica para novas decisoes. Markdown e exportado do BD. Para ADRs existentes, import retroativo popula o BD; se editados manualmente, markdown vence via re-import. Inclui: migration 003 (schema), API expandida em db.py, import retroativo dos ADRs existentes + memory files, export Nygard structurally equivalent, FTS5 full-text search, e tabela de links entre decisoes.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib only: sqlite3, hashlib, json, pathlib, uuid, re, yaml via pyyaml)
**Primary Dependencies**: pyyaml (ja presente), sqlite3 (stdlib)
**Storage**: SQLite WAL mode em `.pipeline/madruga.db`
**Testing**: pytest (pattern existente em `.specify/scripts/tests/`)
**Target Platform**: Linux (CLI tools, nao web service)
**Project Type**: CLI / pipeline tooling
**Performance Goals**: FTS5 queries <100ms para 50+ decisoes
**Constraints**: Python stdlib only para db.py (exceto pyyaml); zero dependencias novas
**Scale/Scope**: ~20-50 decisions, ~10-20 memory entries inicialmente

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Pragmatism | PASS | Solucao simples — ALTER TABLE + novas funcoes no db.py existente |
| II. Automate | PASS | Import/export automatizados via CLI |
| III. Structured Knowledge | PASS | Exatamente o objetivo — decisions e memory estruturados e queryaveis |
| IV. Fast Action | PASS | Reutiliza infra existente (db.py, platform.py, migrations) |
| V. Alternatives | PASS | Documentadas no context.md (A vs B vs C) |
| VI. Brutal Honesty | PASS | — |
| VII. TDD | PASS | Testes primeiro para cada funcao nova |
| VIII. Collaborative | PASS | Clarifications resolvidos |
| IX. Observability | PASS | logger.info em cada operacao, eventos no audit log |

## Review Notes

Auto-review levantou issues. Fixes incorporados:

| Issue | Severidade | Fix |
|-------|-----------|-----|
| "Byte-identical export" irrealista | BLOCKER | Relaxado para "structurally equivalent" — mesmas sections e frontmatter fields, whitespace pode diferir |
| `migrate()` strip de `--` quebra triggers FTS5 | BLOCKER | Corrigir `migrate()` para detectar trigger/view blocks e nao splitar `;` dentro deles |
| Parsing inconsistente entre ADRs | BLOCKER | Mapear variacoes reais dos ADRs antes de implementar parser. Parser fail-safe: warning + skip |
| FTS5 triggers podem nao disparar com ON CONFLICT | WARNING | Testar explicitamente em test suite |
| CLI flags em post_save.py viola SRP | WARNING | Mover import/export para `platform.py` (ja tem subcommands) |
| ALTER TABLE com constraints | WARNING | Usar nullable columns + DEFAULT |
| FTS5 startup check | NIT | Adicionar check no `migrate()` — fallback graceful se FTS5 indisponivel |
| `decision_links` sem consumidor ainda | NIT | Manter como P3 (ultimo a implementar), schema criado mas API pode ser deferida |
| Reviewer propoe mudar para Alternativa A (BD como index) | REJEITADO | Decisao do usuario foi explicitamente B. Mantemos B com pragmatismo nos edge cases |

## Project Structure

### Documentation (this epic)

```text
platforms/madruga-ai/epics/009-decision-log-bd/
├── context.md           # Implementation context
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research
├── data-model.md        # Phase 1 data model
└── tasks.md             # Phase 2 task breakdown (via /speckit.tasks)
```

### Source Code (repository root)

```text
.pipeline/
├── migrations/
│   ├── 001_initial.sql          # Existing
│   ├── 002_indexes_and_fixes.sql # Existing
│   └── 003_decisions_memory.sql  # NEW — schema changes + FTS5 + triggers
└── madruga.db                    # Runtime DB (gitignored)

.specify/scripts/
├── db.py                # MODIFY — expand decision/memory API + fix migrate()
├── platform.py          # MODIFY — add import/export subcommands
└── tests/
    ├── conftest.py      # Existing (tmp_db fixture)
    ├── test_db_crud.py  # Existing
    └── test_db_decisions.py  # NEW — decision import/export/search + memory tests
```

**Structure Decision**: Nenhum novo diretorio. Import/export vai para `platform.py` (ja tem subcommands new/lint/sync/register/list). Testes dedicados em novo arquivo.

## Research

### R1: FTS5 no Python 3.11+ stdlib

**Decision**: FTS5 esta disponivel no sqlite3 do Python 3.11+ em todas as distros mainstream.
**Rationale**: Verificavel com `conn.execute("CREATE VIRTUAL TABLE test USING fts5(content)")`. Adicionar check no startup com fallback graceful (skip FTS tables se indisponivel).
**Alternatives**: FTS3/FTS4 (menos features), external search lib (perde stdlib-only constraint).

### R2: Parsing de frontmatter YAML em markdown

**Decision**: Usar pyyaml para parsear frontmatter entre `---` markers. Conteudo apos segundo `---` parseado por regex para sections (`## Heading`).
**Rationale**: pyyaml ja e dependencia. Parser deve ser fail-safe: warning + skip em caso de frontmatter malformado.
**Variacao real dos ADRs**: Mapear headers e frontmatter fields de todos os ADRs existentes antes de implementar. Aceitar variacoes (ex: "Decisao" vs "Decision", subsections com `###`).

### R3: Content hash para sync detection

**Decision**: SHA-256 do conteudo completo do arquivo (`compute_file_hash()` existente).
**Conflict resolution**: Se hash do markdown != hash no BD → markdown vence (re-import). BD e fonte para novos; markdown e fallback para edits manuais.

### R4: Export Nygard — structurally equivalent

**Decision**: Exportar com template string que produz output structurally equivalent ao formato atual. Mesmas sections, mesmos frontmatter fields. Whitespace e formatacao podem diferir minimamente.
**Rationale**: Roundtrip byte-identical e irrealista devido a variacoes de whitespace, encoding, e trailing newlines.
**Validacao**: Testes verificam que sections existem, frontmatter fields estao corretos, e conteudo semantico e preservado.

### R5: Memory file format

**Decision**: Arquivos `.claude/memory/*.md` usam frontmatter com `name`, `description`, `type`. Parser identico ao de ADRs.
**BD e fonte**: Novas memories nascem no BD e sao exportadas para `.claude/memory/`. Import retroativo popula BD com memories existentes.

### R6: FTS5 sync strategy

**Decision**: FTS5 external content tables com triggers INSERT/UPDATE/DELETE.
**Risco**: `migrate()` atual faz strip de `--` e split de `;` que pode quebrar trigger bodies. Fix: detectar blocos `CREATE TRIGGER ... END;` e nao splitar dentro deles.
**Alternativa segura**: Se `migrate()` fix for complexo, criar FTS tables e triggers via `conn.executescript()` em funcao Python separada chamada apos migration.

## Data Model

### Existing Tables (modified)

**decisions** (ALTER TABLE — 5 new columns, all nullable):
| Column | Type | Default | Description |
|--------|------|---------|-------------|
| content_hash | TEXT | NULL | SHA-256 do markdown exportado |
| decision_type | TEXT | NULL | (technology, architecture, process, integration, tradeoff) |
| context | TEXT | NULL | "Por que" — extraido de ## Contexto |
| consequences | TEXT | NULL | Extraido de ## Consequencias |
| tags_json | TEXT | '[]' | JSON array de tags |

Nota: CHECK constraints nao sao suportados em ALTER TABLE ADD COLUMN no SQLite. Validacao via codigo Python.

**Diferenciacao ADR formal vs micro-decision**: ADR formal tem `number` NOT NULL + `skill='adr'`. Micro-decision tem `number` NULL.

### New Tables

**decision_links**:
| Column | Type | Constraint |
|--------|------|------------|
| from_decision_id | TEXT | FK → decisions(decision_id) ON DELETE CASCADE |
| to_decision_id | TEXT | FK → decisions(decision_id) ON DELETE CASCADE |
| link_type | TEXT | CHECK (supersedes, depends_on, related, contradicts, amends) |
| PK | | (from_decision_id, to_decision_id, link_type) |

**memory_entries**:
| Column | Type | Description |
|--------|------|-------------|
| memory_id | TEXT PK | hex random |
| platform_id | TEXT FK nullable | NULL = cross-platform |
| type | TEXT NOT NULL | CHECK (user, feedback, project, reference) |
| name | TEXT NOT NULL | Short name |
| description | TEXT | One-line description |
| content | TEXT NOT NULL | Full body |
| source | TEXT | Origin (skill, session, manual) |
| file_path | TEXT | Original/export path |
| content_hash | TEXT | SHA-256 |
| created_at | TEXT NOT NULL | ISO 8601 |
| updated_at | TEXT NOT NULL | ISO 8601 |

**decisions_fts** (FTS5): indexes decisions.title, decisions.context, decisions.consequences
**memory_fts** (FTS5): indexes memory_entries.name, memory_entries.description, memory_entries.content

### Indexes

```sql
CREATE INDEX idx_decisions_type ON decisions(decision_type);
CREATE INDEX idx_decisions_hash ON decisions(content_hash);
CREATE INDEX idx_memory_type ON memory_entries(type);
CREATE INDEX idx_memory_platform ON memory_entries(platform_id);
CREATE INDEX idx_memory_hash ON memory_entries(content_hash);
CREATE INDEX idx_decision_links_to ON decision_links(to_decision_id);
```

## API Design (db.py functions)

### Decision Functions (new/modified)

| Function | Signature | Notes |
|----------|-----------|-------|
| `insert_decision()` | MODIFY — add kwargs for new columns | Backward compatible |
| `get_decisions()` | MODIFY — add optional filters: status, decision_type | Backward compatible |
| `export_decision_to_markdown()` | NEW (conn, decision_id, output_dir) → Path | Gera ADR-NNN-slug.md |
| `import_adr_from_markdown()` | NEW (conn, file_path, platform_id) → str | Parseia MD → upsert no BD |
| `import_all_adrs()` | NEW (conn, platform_id, decisions_dir) → int | Batch import |
| `sync_decisions_to_markdown()` | NEW (conn, platform_id, output_dir) → int | Batch export |
| `search_decisions()` | NEW (conn, query, platform_id=None) → list[dict] | FTS5 search |

### Decision Link Functions (new — P3, pode ser deferida)

| Function | Signature |
|----------|-----------|
| `insert_decision_link()` | (conn, from_id, to_id, link_type) → None |
| `get_decision_links()` | (conn, decision_id, direction="both") → list[dict] |

### Memory Functions (new)

| Function | Signature |
|----------|-----------|
| `insert_memory()` | (conn, type, name, content, **kwargs) → str |
| `get_memories()` | (conn, type=None, platform_id=None) → list[dict] |
| `update_memory()` | (conn, memory_id, **kwargs) → None |
| `delete_memory()` | (conn, memory_id) → None |
| `import_memory_from_markdown()` | (conn, file_path) → str |
| `import_all_memories()` | (conn, memory_dir) → int |
| `export_memory_to_markdown()` | (conn, memory_id, output_dir) → Path |
| `sync_memories_to_markdown()` | (conn, output_dir) → int |
| `search_memories()` | (conn, query, type=None) → list[dict] |

### platform.py CLI additions (NOT post_save.py)

| Subcommand | Action |
|------------|--------|
| `platform.py import-adrs <name>` | Import all ADR-*.md from platform decisions/ |
| `platform.py import-memory` | Import all .claude/memory/*.md |
| `platform.py export-adrs <name>` | Export all decisions to markdown |
| `platform.py export-memory` | Export all memories to markdown |

## Implementation Phases

### Phase 0: Prep (fix migrate + map ADR variations)
1. Fix `migrate()` to handle trigger bodies (`;` inside CREATE TRIGGER ... END)
2. Map all existing ADR frontmatter fields and section headers across all platforms
3. Add FTS5 availability check in `migrate()`

### Phase 1: Schema + Core CRUD (TDD)
1. Write failing tests for new columns + tables (RED)
2. Write migration 003_decisions_memory.sql
3. Implement expanded `insert_decision()` + `get_decisions()` (GREEN)
4. Write failing tests for memory CRUD (RED)
5. Implement memory CRUD (GREEN)
6. Refactor

### Phase 2: Import (TDD)
1. Write failing tests for markdown parsing + import with fixture ADRs (RED)
2. Implement `import_adr_from_markdown()` + `import_all_adrs()`
3. Implement `import_memory_from_markdown()` + `import_all_memories()` (GREEN)
4. Run import retroativo de todos os ADRs existentes + memory files
5. Validate SC-001

### Phase 3: Export (TDD)
1. Write failing tests for markdown export — validate structure, not byte-identity (RED)
2. Implement `export_decision_to_markdown()` (Nygard format)
3. Implement `export_memory_to_markdown()`
4. Implement batch sync functions (GREEN)
5. Validate SC-002 (structurally equivalent)

### Phase 4: FTS5 + Search (TDD)
1. Write failing tests for FTS5 search (RED)
2. Add FTS5 virtual tables + triggers to migration 003
3. Implement `search_decisions()` + `search_memories()` (GREEN)
4. Validate SC-003 (<100ms)

### Phase 5: CLI + Links (TDD)
1. Add subcommands to `platform.py`
2. Write failing integration tests (RED)
3. Implement import/export CLI (GREEN)
4. Implement `decision_links` CRUD (if time; P3)
5. Validate SC-004 + SC-005

## Complexity Tracking

No constitution violations. All complexity justified by spec requirements.

| Potential concern | Justification |
|-------------------|---------------|
| 5 ALTER TABLE columns | All nullable, backward compatible, no migration risk |
| FTS5 triggers | Standard SQLite pattern, tested explicitly |
| 2 new tables | Minimal schema, justified by spec FR-006 (links) and FR-007 (memory) |
