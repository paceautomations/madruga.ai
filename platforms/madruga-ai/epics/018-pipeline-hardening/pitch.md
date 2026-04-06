---
id: 018
title: "Pipeline Hardening & Safety"
status: shipped
appetite: 2w
priority: P1
depends_on: []
blocks: [020]
updated: 2026-04-05
delivered_at: 2026-04-05
---
# Epic 018: Pipeline Hardening & Safety

## Problem

O pipeline DAG tem falhas de confiabilidade que se acumulam: connection leaks (conn.close() manual em 5+ lugares do dag_executor.py sem try/finally), validacao ad-hoc de inputs (KeyError 3 nodes downstream de um campo faltando no platform.yaml), ausencia de hierarquia de erros (mix de SystemExit, log.error+return, print("[error]")), e um typo em `gate: "humam"` passa silenciosamente como auto — executando nodes sem aprovacao humana. Nao ha graceful shutdown: Ctrl+C durante dispatch deixa subprocess orfao sem checkpoint. Nomes de plataforma e URLs de repo nao sao sanitizados (`ensure_repo.py` roda `git clone` com input do usuario sem validacao).

Esses riscos sao cumulativos: cada nova plataforma e cada novo epic amplifica a probabilidade de falha silenciosa.

## Appetite

**2w** — 7 tasks bem definidas, todas em scripts existentes. Historico mostra appetite 2w = ~1d de execucao real. Nenhuma decisao arquitetural — so aplicar patterns ja provados (context managers, dataclasses, signal handlers).

## Solution

### T1. Context managers em dag_executor.py (1h)

Substituir todas as ocorrencias de `conn = get_conn()` + `conn.close()` por `with get_conn() as conn:`. A infraestrutura ja existe: `_ClosingConnection` em `db.py` suporta context manager.

**Locais especificos:**
- `dag_executor.py:924` — `run_pipeline()` (sync version)
- `dag_executor.py:1375` — `_run_pipeline_sync()` (fallback version)
- `dag_executor.py:1395` — `conn.close()` antes de `return 0` no branch de gate pendente

**Pattern:**
```python
# Antes
conn = get_conn()
# ... 90 linhas de logica ...
if gate_pending:
    conn.close()  # facil esquecer
    return 0
conn.close()  # e se exception antes?

# Depois
with get_conn() as conn:
    # ... toda a logica ...
    if gate_pending:
        return 0  # _ClosingConnection fecha automaticamente
```

### T2. Fail-closed gate defaults (30min)

Em `parse_dag()` (`dag_executor.py:465-509`), validar o campo `gate` contra o set canonico. Gate desconhecido → tratar como `human` (fail-closed).

```python
VALID_GATES = {"auto", "human", "1-way-door", "auto-escalate"}

def parse_dag(...):
    for n in raw_nodes:
        gate = n.get("gate", "auto")
        if gate not in VALID_GATES:
            log.warning("Unknown gate '%s' for node '%s' — treating as 'human' (fail-closed)", gate, n["id"])
            gate = "human"
        nodes.append(Node(..., gate=gate, ...))
```

**Referencia:** Claude Code usa fail-closed em tudo: `isConcurrencySafe: false`, `isReadOnly: false`. Um default seguro previne execucao acidental.

### T3. Circuit breaker no skill dispatch (15min)

Em `dispatch_with_retry()`, apos 3 falhas CONSECUTIVAS do MESMO skill, desabilitar retries. Antropic perdeu ~250K API calls/dia por falta disso na compactacao.

```python
if consecutive_failures >= 3:
    log.error("Skill '%s' failed 3x consecutively. Disabling retries.", node.skill)
    return False, "consecutive failure limit reached", ""
```

### T4. Path security (1h)

**4a.** Validar nomes de plataforma em `platform_cli.py` (new, use, lint):
```python
import re
PLATFORM_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
if not PLATFORM_NAME_RE.match(name):
    raise SystemExit(f"ERROR: Invalid platform name '{name}'. Use lowercase, digits, hyphens only.")
```

**4b.** Em `ensure_repo.py:_load_repo_binding()`, validar org/name contra `^[a-zA-Z0-9._-]+$`.

**4c.** Block path traversal: em qualquer lugar que recebe path do usuario, rejeitar `..` segments.

### T5. Input validation com dataclasses (3h)

Criar dataclasses para validacao de entrada em `dag_executor.py`:

```python
from dataclasses import dataclass, field

@dataclass
class NodeSchema:
    id: str
    skill: str
    outputs: list[str] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    gate: str = "auto"
    layer: str = ""
    optional: bool = False
    skip_condition: str | None = None

    def __post_init__(self):
        if not self.id:
            raise ValueError("Node.id is required")
        if not self.skill:
            raise ValueError("Node.skill is required")
        if self.gate not in VALID_GATES:
            log.warning("Unknown gate '%s' for node '%s' — treating as 'human'", self.gate, self.id)
            self.gate = "human"
```

Tambem criar `PlatformConfig` dataclass para validar platform.yaml na entrada.

**Decisao:** dataclasses (stdlib) sobre Pydantic — conforme ADR de stdlib-only.

### T6. Error hierarchy (2h)

Criar modulo `errors.py` em `.specify/scripts/`:

```python
class MadrugaError(Exception):
    """Base para todos os erros madruga.ai."""

class PipelineError(MadrugaError):
    """Erro no pipeline DAG (ciclos, nodes faltando, dispatch failure)."""

class ValidationError(MadrugaError):
    """Erro de validacao de input (YAML invalido, campo faltando)."""

class DispatchError(MadrugaError):
    """Erro ao despachar skill via claude -p."""

class GateError(MadrugaError):
    """Erro em gate (timeout, rejection, gate type invalido)."""
```

Substituir `raise SystemExit(...)` por erros tipados nos scripts: `dag_executor.py`, `post_save.py`, `ensure_repo.py`, `platform_cli.py`.

**Referencia:** Claude Code tem hierarquia: `ClaudeError → MalformedCommandError, AbortError, ShellError, ConfigParseError`.

### T7. Graceful shutdown (1h)

Signal handler em `dag_executor.py`:

```python
import signal

_active_process: subprocess.Popen | None = None

def _handle_sigint(sig, frame):
    if _active_process:
        _active_process.terminate()
    log.info("Interrupted. Resume with: --resume")
    sys.exit(130)

signal.signal(signal.SIGINT, _handle_sigint)
```

**Referencia:** Claude Code tem shutdown orquestrado em 6 etapas (disable mouse → unmount Ink → print resume hint → flush analytics).

## Rabbit Holes

- **Nao refatorar o DAG executor inteiro** — scope e adicionar safety, nao reescrever
- **Nao usar Pydantic** — stdlib only (dataclasses). Resistir a tentacao de adicionar deps
- **Nao mexer nos testes existentes** — adicionar testes para as novas validacoes, nao reescrever os 43 existentes
- **Error hierarchy nao precisa cobrir 100% dos raise** — comecar pelos mais comuns (SystemExit em parse_dag, ensure_repo) e expandir depois

## No-gos

- Mudancas no schema do SQLite (isso e epic diferente)
- Mudancas no portal ou frontend
- Refactoring de db.py (isso e epic 020)
- Structured logging (isso e epic 020)
- Mudancas em skills (.claude/commands/) — scope e scripts Python

## Acceptance Criteria

- [ ] Zero `conn = get_conn()` sem context manager em dag_executor.py
- [ ] Gate type invalido em platform.yaml resulta em WARNING + tratamento como `human`
- [ ] 3 falhas consecutivas do mesmo skill desabilita retries automaticamente
- [ ] Nome de plataforma `"../../../etc"` rejeitado com erro claro
- [ ] `Node` e `PlatformConfig` validados via dataclass `__post_init__`
- [ ] `raise SystemExit(...)` substituido por erros tipados nos 4 scripts principais
- [ ] Ctrl+C durante dispatch termina subprocess, salva checkpoint, imprime --resume
- [ ] `make test` passa (testes existentes + novos)
- [ ] `make ruff` passa

## Implementation Context

### Arquivos a modificar
| Arquivo | LOC atual | Mudanca |
|---------|-----------|---------|
| `.specify/scripts/dag_executor.py` | 1,649 | T1+T2+T3+T5+T7 |
| `.specify/scripts/ensure_repo.py` | 161 | T4+T6 |
| `.specify/scripts/platform_cli.py` | 889 | T4+T6 |
| `.specify/scripts/post_save.py` | 506 | T6 |

### Arquivos a criar
| Arquivo | Estimativa |
|---------|-----------|
| `.specify/scripts/errors.py` | ~30 LOC |
| `.specify/scripts/tests/test_errors.py` | ~50 LOC |
| `.specify/scripts/tests/test_path_security.py` | ~40 LOC |

### Funcoes existentes a reutilizar
- `_ClosingConnection` em `db.py` — context manager ja pronto
- `CircuitBreaker` em `dag_executor.py` — pattern a replicar para dispatch
- `get_conn()` em `db.py` — ja retorna `_ClosingConnection`

### Decisoes arquiteturais
- **dataclasses > Pydantic**: stdlib only (ADR existente)
- **Fail-closed > fail-open**: unknown gate → human (pattern Claude Code)
- **Signal handler simples**: SIGINT only, sem orchestracao complexa

---

> **Source**: madruga_next_evolution.md Tier S (S1-S3, S6) + Tier A (A1-A3)
> **Benchmark**: Claude Code fail-closed defaults, error hierarchy, graceful shutdown
