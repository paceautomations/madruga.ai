# Research: SQLite Foundation

**Feature**: 002-sqlite-foundation
**Date**: 2026-03-29

## Research Tasks

### R1. SQLite WAL Mode + Concurrency

**Decision**: WAL mode com `busy_timeout=5000` e `journal_size_limit=67108864` (64MB)
**Rationale**: WAL permite leituras concorrentes durante writes. `busy_timeout` evita SQLITE_BUSY em writes concorrentes (CLI single-user, mas scripts podem rodar em paralelo). Blueprint §1.6 já especifica essa config.
**Alternatives**: DELETE journal (mais lento, bloqueia leituras durante write), WAL2 (experimental, não suportado no Python stdlib)

### R2. Python sqlite3 Best Practices

**Decision**: `conn.row_factory = sqlite3.Row` para acesso por nome de coluna. Funções recebem `conn` como argumento (caller controla lifecycle). `executescript()` para migrations (auto-commit).
**Rationale**: Row factory é mais ergonômico que tuples. Passing conn permite transações explícitas no caller. executescript é o padrão para DDL multi-statement.
**Alternatives**: dict_factory custom (mais overhead), ORM (dep externa), named tuples (menos flexível)

### R3. Migration Runner Patterns

**Decision**: SQL files numerados (`001_initial.sql`, `002_add_column.sql`) com tabela `_migrations` para tracking. Cada migration roda em transaction implícita do executescript.
**Rationale**: Padrão da indústria (Rails, Django, Alembic). Simples de implementar (~20 linhas). Migrations versionadas no git.
**Alternatives**: Alembic (dep externa, over-engineering), manual DDL (sem versionamento), schema-diff tools (complexidade)

### R4. Content Hash Strategy

**Decision**: SHA256 truncado a 12 chars hex com prefixo `sha256:`. Ex: `sha256:a1b2c3d4e5f6`.
**Rationale**: SHA256 é padrão, built-in no Python. 12 chars hex = 48 bits = colisão praticamente impossível para ~100 files. Prefixo permite extensão futura (ex: `blake3:`).
**Alternatives**: MD5 (inseguro, sem vantagem de performance significativa), full SHA256 (64 chars, desnecessário), CRC32 (colisões)

### R5. GitHub Actions Patterns para Monorepo

**Decision**: 3 jobs paralelos no mesmo workflow. Trigger em push + PR. Matrix strategy para plataformas no likec4 job.
**Rationale**: Jobs paralelos = CI mais rápido. Um workflow (não 3) = mais simples de manter. Matrix para likec4 escala automaticamente com novas plataformas.
**Alternatives**: 3 workflows separados (mais arquivos, harder to coordinate), single serial job (mais lento), path-based triggers (premature optimization, complicado de manter)

### R6. Seed Strategy — Import de Estado Existente

**Decision**: `seed_from_filesystem(conn, platform_id)` lê platform.yaml para DAG nodes, scana diretórios para file existence + hash, scana epics/ para epic registry. Idempotente via INSERT OR REPLACE.
**Rationale**: BD precisa refletir estado real. Seed é one-shot na primeira execução + re-runnable para sync. Idempotente garante que re-runs são seguros.
**Alternatives**: Manual INSERT (tedioso, error-prone), dump/restore (sem dados existentes para dumpar), git-based import (complexo, nem todo estado está no git)

## NEEDS CLARIFICATION: Resolved

Nenhum item pendente. Todas decisões tomadas no context.md e validadas nesta pesquisa.
