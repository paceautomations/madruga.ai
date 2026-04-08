---
id: 020
title: "Code Quality & DX"
status: shipped
priority: P2
depends_on: [018]
blocks: []
updated: 2026-04-05
delivered_at: 2026-04-05
---
# Epic 020: Code Quality & DX

## Problem

`db.py` tem 2,268 linhas com 6 responsabilidades distintas misturadas (connection/migration, pipeline CRUD, decisions/memory, FTS5, observability, transactions). E o unico arquivo da codebase perto do limite critico — e a maior funcao do Claude Code (3,167 linhas em print.ts) recebeu nota 6.5/10 por razao identica. Logging e inconsistente: mix de `print("[ok]")`, `log.info()`, e `print()` direto — CI nao consegue parsear output sem regex. Skills podem driftar do contrato de 6 passos sem deteccao. Memories acumulam sem pruning — MEMORY.md pode ultrapassar o limite de 200 linhas sem aviso. `vision-build.py` e `sync_memory.py` nao tem nenhum teste automatizado.

**Depende de epic 018:** O split de db.py precisa da error hierarchy (T6 do 018) para que cada modulo use erros tipados em vez de SystemExit.

## Solution

### T1. Split db.py (4h)

Dividir `db.py` (2,268 LOC) em 4 modulos por responsabilidade:

| Modulo | Conteudo | LOC estimado |
|--------|----------|-------------|
| `db_core.py` | `get_conn()`, `_ClosingConnection`, `_BatchConnection`, `migrate()`, `transaction()`, `_check_fts5()` | ~400 |
| `db_pipeline.py` | `upsert_platform()`, `upsert_pipeline_node()`, `upsert_epic_node()`, `insert_run()`, `complete_run()`, `get_stale_nodes()`, `get_resumable_nodes()`, `get_pending_gates()`, `compute_epic_status()` | ~500 |
| `db_decisions.py` | `insert_decision()`, `get_decisions()`, `search_decisions()`, `import_adr_from_markdown()`, `export_decision_to_markdown()`, `insert_memory()`, `get_memories()`, `search_memories()`, `import_memory_from_markdown()`, `export_memory_to_markdown()`, FTS5 operations | ~800 |
| `db_observability.py` | `create_trace()`, `add_span()`, `complete_trace()`, `insert_eval_score()`, `get_eval_scores()`, observability queries | ~500 |

**Regras do split:**
- `db_core.py` e leaf — nao importa dos outros
- `db_pipeline.py`, `db_decisions.py`, `db_observability.py` importam de `db_core.py` (get_conn, migrate)
- Manter `db.py` como re-export facade para backward compat: `from db_core import *; from db_pipeline import *; ...`
- Todos os imports existentes continuam funcionando sem mudanca nos callers

**Migracao dos testes:**
- `test_db_core.py` — connection, migration, transaction tests
- `test_db_crud.py` → `test_db_pipeline.py` — renomear
- `test_db_decisions.py` — ja existe, manter
- `test_db_observability.py` — ja existe, manter

### T2. Structured logging (3h)

Padronizar saida de todos os scripts:

**Regra:** `log.*()` para operacoes internas, `print()` so para output final ao usuario.

**Implementacao:**
1. Substituir `print("[ok]")`, `print("[error]")`, `print("[skip]")` por `log.info()`, `log.error()`, `log.info()` respectivamente
2. Adicionar flag `--json` a `platform_cli.py`, `dag_executor.py`, `post_save.py` para output estruturado
3. Configurar `logging.basicConfig()` com format consistente: `%(asctime)s %(name)s %(levelname)s %(message)s`
4. Em modo `--json`: output NDJSON (uma linha JSON por evento)

**Pattern:**
```python
if args.json:
    logging.basicConfig(format='%(message)s', level=logging.INFO)
    # Custom handler que emite JSON
else:
    logging.basicConfig(format='%(levelname)s %(message)s', level=logging.INFO)
```

**Referencia:** Claude Code tem dual output: human-readable para CLI, NDJSON streaming para SDK/CI (`structuredIO.ts`).

### T3. Memory consolidation script (4h)

Criar `.specify/scripts/memory_consolidate.py` (~200 LOC):

**Funcionalidades:**
1. **Detect stale**: memories >90 dias sem atualizacao
2. **Detect contradictions**: 2+ memories sobre o mesmo topico com informacao conflitante (heuristico: mesmo `type` + similaridade no `description`)
3. **Convert dates**: datas relativas para absolutas
4. **Prune**: marcar memories stale para review (nao deletar automaticamente)
5. **Index check**: validar que MEMORY.md <200 linhas

**Output:** report com acoes sugeridas (prune, merge, update). Mode `--dry-run` por default, `--apply` para executar.

**Referencia:** Claude Code Dream system (Orient → Gather → Consolidate → Prune). Principio: "memoria e pista, nao verdade".

### T4. Skill contract validation no linter (2h)

Estender `skill-lint.py` com novas validacoes de contrato:

| Check | Severity | Implementacao |
|-------|----------|---------------|
| Skill referencia `pipeline-contract-base.md`? | WARNING | Grep no body |
| Tem secao `## Output Directory`? | WARNING | Regex no body |
| Frontmatter `gate` e valido? | ERROR | Check contra set canonico |
| Tem `### 0. Prerequisites` ou referencia a check-prerequisites? | NIT | Regex |
| Frontmatter tem `handoffs`? | NIT | Check YAML key |

**Reutilizar:** `lint_single_skill()` em `skill-lint.py` — adicionar checks ao loop existente.

### T5. Memoization (1h)

Aplicar `functools.lru_cache` a funcoes que leem filesystem repetidamente:

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def _discover_platforms():
    """Read platforms/ directory — cached for session lifetime."""
    ...
```

**Locais:**
- `platform_cli.py:_discover_platforms()` — chamada N vezes em `status --all`
- `platform_cli.py:_load_manifest()` — le platform.yaml toda vez

**Invalidacao:** `lru_cache` nao tem TTL, mas nao precisa — scripts sao short-lived (single invocacao). Para `new` e `sync`, chamar `_discover_platforms.cache_clear()`.

### T6. Testes para vision-build.py e sync_memory.py (4h)

**`test_vision_build.py` (~150 LOC):**
- Mock LikeC4 JSON com containers, domains, relations, integrations
- Testar: AUTO markers populados corretamente, `--validate-only` nao escreve, `--export-png` gera erro graceful sem likec4 CLI
- Mock `subprocess.run` para simular likec4 build/export

**`test_sync_memory.py` (~100 LOC):**
- Testar: import memory from markdown, export memory to markdown, round-trip sem perda
- Testar: frontmatter parsing com tipos (user, feedback, project, reference)
- Testar: MEMORY.md index update

## Rabbit Holes

- **Split db.py com backward compat facade** — nao quebrar imports existentes. Re-export tudo de db.py
- **Structured logging nao precisa de structlog** — stdlib logging e suficiente. structlog e dep externa
- **Memory consolidation nao deleta automaticamente** — sugere, nao executa (--dry-run default)
- **Nao reescrever skill-lint.py** — adicionar checks ao loop existente, nao refatorar

## No-gos

- Mudancas no schema do SQLite
- Mudancas em skills (.claude/commands/)
- Portal/frontend changes
- Pre-commit hooks (scope de governance, epic 019)
- Adicionar dependencias externas (structlog, pydantic)

## Acceptance Criteria

- [ ] `db.py` splitado em 4 modulos, re-export facade funcional
- [ ] Zero `print("[ok]")` / `print("[error]")` nos scripts — tudo via `log.*`
- [ ] `platform_cli.py status --all --json` emite NDJSON
- [ ] `python3 .specify/scripts/memory_consolidate.py --dry-run` produz report
- [ ] `skill-lint.py` detecta skill sem `## Output Directory` (WARNING)
- [ ] `_discover_platforms()` usa `lru_cache`
- [ ] `test_vision_build.py` existe com >=5 test cases
- [ ] `test_sync_memory.py` existe com >=5 test cases
- [ ] Todos os imports existentes de `from db import ...` continuam funcionando
- [ ] `make test` passa
- [ ] `make ruff` passa

## Implementation Context

### Arquivos a modificar
| Arquivo | LOC atual | Mudanca |
|---------|-----------|---------|
| `.specify/scripts/db.py` | 2,268 | T1 — split + re-export facade |
| `.specify/scripts/platform_cli.py` | 889 | T2 (logging) + T5 (memoization) |
| `.specify/scripts/dag_executor.py` | 1,649 | T2 (logging) |
| `.specify/scripts/post_save.py` | 506 | T2 (logging) |
| `.specify/scripts/skill-lint.py` | 358 | T4 (contract checks) |

### Arquivos a criar
| Arquivo | Estimativa |
|---------|-----------|
| `.specify/scripts/db_core.py` | ~400 LOC |
| `.specify/scripts/db_pipeline.py` | ~500 LOC |
| `.specify/scripts/db_decisions.py` | ~800 LOC |
| `.specify/scripts/db_observability.py` | ~500 LOC |
| `.specify/scripts/memory_consolidate.py` | ~200 LOC |
| `.specify/scripts/tests/test_vision_build.py` | ~150 LOC |
| `.specify/scripts/tests/test_sync_memory.py` | ~100 LOC |

### Funcoes existentes a reutilizar
- `_check_fts5()` em `db.py` — pattern de memoizacao a generalizar
- `lint_single_skill()` em `skill-lint.py` — loop existente para adicionar checks
- `_discover_platforms()` em `platform_cli.py` — alvo de lru_cache

### Decisoes
- **Re-export facade**: db.py mantem `from db_core import *` etc para zero breaking changes
- **stdlib logging > structlog**: sem deps externas
- **Memory consolidation dry-run by default**: seguranca — nunca deleta sem confirmacao

---

> **Source**: madruga_next_evolution.md Tier B (B1-B5) + IMPROVEMENTS W8
> **Benchmark**: Claude Code Dream system, Akita article (db.py vs print.ts 3,167 lines)
