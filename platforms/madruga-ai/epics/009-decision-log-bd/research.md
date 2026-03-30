# Research: BD como Source of Truth para Decisions + Memory

**Date**: 2026-03-29

## R1: FTS5 Availability in Python 3.11+ stdlib

**Decision**: FTS5 esta disponivel no sqlite3 do Python 3.11+ em todas as distros mainstream.
**Rationale**: O sqlite3 compilado com Python 3.11+ inclui FTS5 por padrao. Verificavel com:
```python
sqlite3.connect(':memory:').execute("CREATE VIRTUAL TABLE test USING fts5(content)")
```
**Alternatives considered**:
- FTS3/FTS4: Menos features (no prefix queries, no column filters). Rejeitado.
- External search lib (whoosh, tantivy): Perde stdlib-only constraint. Rejeitado.

## R2: Parsing de Frontmatter YAML em Markdown

**Decision**: Usar pyyaml (ja presente) para parsear frontmatter entre `---` markers. Conteudo apos segundo `---` parseado por regex para sections (## Heading).
**Rationale**: pyyaml ja e dependencia de `seed_from_filesystem()`. Regex para sections e simples para formato Nygard padronizado.
**Alternatives considered**:
- python-frontmatter lib: Dependencia nova — rejeitada por constraint stdlib-only (+pyyaml).
- Regex puro para YAML: Fragil para valores com caracteres especiais. Rejeitado.

## R3: Content Hash para Sync Detection

**Decision**: SHA-256 do conteudo completo do arquivo markdown. Funcao `compute_file_hash()` ja existe em db.py.
**Rationale**: Reutiliza implementacao existente. Mesma semantica usada por pipeline_nodes.
**Alternatives considered**:
- Hash apenas do frontmatter: Perde deteccao de mudancas no body. Rejeitado.
- mtime-based: Fragil com git (clone reseta mtime). Rejeitado.

## R4: Export Format — Nygard Template

**Decision**: Template string em Python que replica exatamente o formato observado nos ADRs existentes (ADR-001 a ADR-019).
**Rationale**: Analisado ADR-001-pydantic-ai.md como referencia. Formato:
```
---
title: "ADR-NNN: titulo"
status: Status
decision: "decisao"
alternatives: "alt1, alt2"
rationale: "rationale"
---
# ADR-NNN: titulo
**Status:** Status | **Data:** YYYY-MM-DD | **Atualizado:** YYYY-MM-DD

## Contexto
[context]

## Decisao
[decision text + motivos]

## Alternativas consideradas
### Alternative 1
- Pros: ...
- Cons: ...

## Consequencias
[consequences as bullet list]
```
**Alternatives considered**:
- Jinja2 template: Dependencia nova — rejeitada.
- Markdown lib (mdformat): Dependencia nova — rejeitada.

## R5: Memory File Format

**Decision**: Arquivos em `.claude/memory/` usam frontmatter com campos `name`, `description`, `type`. Body e o conteudo da memory.
**Rationale**: Formato definido pelo auto-memory system em CLAUDE.md. Nao ha opcao — e o formato que Claude Code gera.
**Alternatives**: N/A — formato fixo.

## R6: FTS5 Sync Strategy

**Decision**: Usar FTS5 content tables com triggers para manter sync automatico.
**Rationale**: SQLite FTS5 suporta `content=table` que sincroniza automaticamente via triggers. Alternativamente, external content tables com triggers manuais INSERT/UPDATE/DELETE.
**Alternatives considered**:
- Manual rebuild (DROP + repopulate): Simples mas lento para datasets grandes. Rejeitado para uso futuro.
- Separate FTS population script: Mais codigo, mais chances de dessync. Rejeitado.

**Implementacao**: Usar external content table pattern com triggers:
```sql
CREATE VIRTUAL TABLE decisions_fts USING fts5(
    title, context, consequences,
    content=decisions, content_rowid=rowid
);
-- Triggers para manter sync
CREATE TRIGGER decisions_ai AFTER INSERT ON decisions BEGIN
    INSERT INTO decisions_fts(rowid, title, context, consequences)
    VALUES (new.rowid, new.title, new.context, new.consequences);
END;
```
