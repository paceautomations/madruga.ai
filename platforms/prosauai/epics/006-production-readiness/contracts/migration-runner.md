# Contract: Migration Runner

**Tipo**: CLI / Library
**Módulo**: `prosauai.ops.migrate`
**Consumidor**: Container `api` (startup) + operador manual

## Interface — CLI

```bash
python -m prosauai.ops.migrate [OPTIONS]
```

### Opções

| Flag | Tipo | Default | Descrição |
|---|---|---|---|
| `--database-url` | string | `$DATABASE_URL` | Connection string Postgres |
| `--migrations-dir` | string | `./migrations` | Diretório com arquivos `.sql` |
| `--dry-run` | bool | `false` | Listar migrations pendentes sem aplicar |
| `--log-level` | string | `INFO` | Nível de log |

### Exit Codes

| Código | Significado |
|---|---|
| 0 | Sucesso (todas migrations aplicadas ou nenhuma pendente) |
| 1 | Erro de conexão com Postgres |
| 2 | Erro na execução de uma migration (transaction rolled back) |

## Interface — Library

```python
from prosauai.ops.migrate import run_migrations

# Usado no startup da API (main.py lifespan)
await run_migrations(
    dsn="postgresql://...",
    migrations_dir=Path("./migrations"),
    dry_run=False,
)
```

### Retorno

```python
@dataclass
class MigrationResult:
    applied: list[str]     # ["001_create_schema", "002_customers", ...]
    skipped: list[str]     # Já aplicadas anteriormente
    failed: str | None     # Nome da migration que falhou (None se sucesso)
    total_time_ms: float
```

## Comportamento

1. Conecta ao Postgres via asyncpg
2. Cria schema `prosauai_ops` e tabela `schema_migrations` se não existirem (bootstrap)
3. Lista arquivos `*.sql` em `migrations_dir`, ordena por nome (numérico)
4. Para cada arquivo NÃO registrado em `schema_migrations`:
   a. Lê conteúdo do arquivo
   b. Abre transaction
   c. Executa SQL (suporta múltiplos statements)
   d. Registra em `schema_migrations` (version, applied_at, checksum SHA-256)
   e. Commit
5. Se qualquer migration falhar: rollback da transaction, retorna erro, NÃO aplica migrations seguintes

## Invariantes

1. **Idempotente**: Re-execução nunca aplica migration já registrada
2. **Forward-only**: Sem rollback de migrations. Correções via nova migration
3. **Fail-fast**: Se migration N falha, migrations N+1..M não são tentadas
4. **Atomic por migration**: Cada migration é uma transaction isolada (DDL é transacional em Postgres)
5. **Checksum**: SHA-256 do conteúdo do arquivo armazenado para detecção de drift (warning se checksum mudou para migration já aplicada)

## Nota sobre Seed Data (migration 007)

A migration 007_seed_data.sql usa `\set` (psql-specific). No epic 006, esta migration é reescrita para usar SQL puro com UUIDs hardcoded (sem variáveis de ambiente). Os UUIDs dos tenants de dev/test são determinísticos e documentados.
