# Madruga.ai vs Claude Code CLI — Benchmark & Melhorias

> **Objetivo**: Comparar a codebase do madruga.ai com as best practices extraidas do Claude Code CLI (`@anthropic-ai/claude-code` v2.1.88). Identificar o que estamos fazendo bem e oportunidades concretas de melhoria.
>
> **Criterios**: Priorizamos apenas o que faz sentido para **performance**, **consistencia** e **confiabilidade** do pipeline. Nada de over-engineering.

---

## Resumo dos Numeros

| Metrica | Madruga.ai | Claude Code CLI |
|---------|-----------|-----------------|
| Scripts Python | 11 arquivos, 4,855 linhas | ~2,215 arquivos TypeScript |
| Skills (slash commands) | 21 skills, 4,506 linhas | ~100 commands |
| Knowledge files | 7 arquivos, 780 linhas | Inline nos tools |
| Testes | 5 arquivos, 1,095 linhas | Extensivos (unitarios + integracao) |
| DB | SQLite WAL, 13 tabelas, 7 migrations | SQLite (session storage JSONL) |
| CI/CD | 1 workflow (ci.yml) | 6+ workflows |

---

## Parte 1: O Que Estamos Fazendo Bem

### 1. Pipeline como DAG com Topological Sort

**Como esta**: `dag_executor.py` usa Kahn's algorithm com deteccao de ciclos, circuit breaker, retry com exponential backoff, e watchdog timeout. Identico ao padrao de orquestracao do Claude Code.

**Por que e bom**: O Claude Code usa uma abordagem similar no `QueryEngine` (budget enforcement com 3 condicoes independentes de terminacao). Nosso DAG executor e um dos pontos mais solidos da codebase.

---

### 2. SQLite como State Store com WAL Mode

**Como esta**: `db.py` usa WAL mode, foreign keys, busy_timeout=5000ms, migrations versionadas, FTS5 com fallback para LIKE, e transaction batching via `_BatchConnection`.

**Por que e bom**: O Claude Code tambem usa SQLite (para sessions). Nosso approach e mais sofisticado em alguns aspectos — temos migration system, FTS5 search, e o `_ClosingConnection` wrapper que resolve o problema do sqlite3 nativo nao fechar no `with`.

---

### 3. Skill Contract Uniforme (6 Steps)

**Como esta**: Todo skill segue o contrato de 6 passos (Prerequisites → Context + Questions → Generate → Auto-review → Gate → Save). Documentado em `pipeline-contract-base.md`.

**Por que e bom**: Identico ao padrao do Claude Code onde cada tool segue um contrato uniforme (schema validation → checkPermissions → call → mapResult). Consistencia e a base da confiabilidade.

---

### 4. Knowledge Files Separados

**Como esta**: 7 knowledge files em `.claude/knowledge/` carregados on-demand por skills. Separam contrato (como fazer) de instrucao (o que fazer).

**Por que e bom**: O Claude Code faz o mesmo com system prompts separados por contexto. Evita duplicacao e mantém cada skill enxuta.

---

### 5. Structured Questions com Pushback Protocol

**Como esta**: O contrato base exige 4 categorias de perguntas (Premissas, Trade-offs, Gaps, Provocacao) com pushback de respostas fracas e uncertainty markers (`[VALIDAR]`, `[ESTIMAR]`, `[DEFINIR]`).

**Por que e bom**: Nao existe equivalente direto no Claude Code — isso e uma inovacao do madruga.ai que forca qualidade nas decisoes antes de gerar artifacts.

---

### 6. Human Gates com Pause/Resume

**Como esta**: O DAG executor suporta gates `human`, `1-way-door`, e `auto`. Pausa o pipeline, grava no DB, e retoma com `--resume`.

**Por que e bom**: O Claude Code tem um sistema similar (permission modes: default, plan, auto, bypass). Nosso approach e mais simples e adequado para o contexto (pipeline batch vs CLI interativo).

---

### 7. Copier Template System

**Como esta**: Template em `.specify/templates/platform/` com `copier.yml`, `_skip_if_exists`, e testes de validacao.

**Por que e bom**: Multi-platform scaffolding com sync automatico. O Claude Code nao tem equivalente direto — cada "platform" dele e hard-coded.

---

### 8. Config como Modulo Leaf-of-DAG

**Como esta**: `config.py` tem 14 linhas, zero imports alem de `pathlib`, define todas as paths como constantes.

**Por que e bom**: Identico ao padrao `src/constants/` do Claude Code — zero imports para evitar ciclos. Nosso `config.py` e exemplar nesse aspecto.

---

### 9. Circuit Breaker no DAG Executor

**Como esta**: `CircuitBreaker` com estados closed/open/half-open, max failures, recovery timeout.

**Por que e bom**: O Claude Code usa circuit breakers em varios lugares (auto-compaction com 3 falhas consecutivas, denial tracking com 3/20 thresholds). Nosso e classico e bem implementado.

---

### 10. Testes com Mocking Adequado

**Como esta**: 1,095 linhas de testes cobrindo dag_executor, db_gates, ensure_repo, implement_remote, worktree. Usam `unittest.mock.patch` corretamente no modulo-alvo.

**Por que e bom**: Boa cobertura dos scripts criticos. Padroes de mock corretos (aprendizado do epic 012 — mock no modulo que importa, nao no modulo que define).

---

## Parte 2: Oportunidades de Melhoria

### P1 — Alta Prioridade (impacto direto em confiabilidade)

---

#### M1. Input Validation com Schema (Zod-like)

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | Validacao ad-hoc: `if not yaml_path.exists()`, `if not raw_nodes`, `raise SystemExit(...)`. Sem schemas formais. |
| **Sugestao** | Criar dataclasses ou Pydantic models para `platform.yaml`, `Node`, frontmatter de skills. Validar na entrada, falhar cedo com mensagens claras. |
| **Por que** | O Claude Code usa **Zod schemas** em 100% dos tools. Cada input e validado contra um schema antes de qualquer processamento. Isso previne erros silenciosos — um campo faltando no `platform.yaml` hoje pode causar falha 3 nodes depois no pipeline. |

**Exemplo concreto**:
```python
# Atual: validacao implícita
nodes.append(Node(
    id=n["id"],        # KeyError se faltar
    skill=n["skill"],  # KeyError se faltar
    ...
))

# Sugestao: schema explicito
from dataclasses import dataclass

@dataclass
class NodeSchema:
    id: str
    skill: str
    outputs: list[str] = field(default_factory=list)
    depends: list[str] = field(default_factory=list)
    gate: str = "auto"
    
    def __post_init__(self):
        if not self.id: raise ValueError("Node.id is required")
        if not self.skill: raise ValueError("Node.skill is required")
        valid_gates = {"auto", "human", "1-way-door", "auto-escalate"}
        if self.gate not in valid_gates:
            raise ValueError(f"Invalid gate '{self.gate}'. Valid: {valid_gates}")
```

**Impacto**: Erros detectados 10x mais cedo. Mensagens de erro uteis ao inves de `KeyError: 'id'`.

---

#### M2. Error Handling Consistente (Error Hierarchy)

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | Mix de `raise SystemExit(...)`, `log.error() + return 1`, `print("[error]")`. Sem hierarquia de erros. |
| **Sugestao** | Criar hierarquia minima: `MadrugaError` base, `PipelineError`, `ValidationError`, `DispatchError`. Usar em vez de SystemExit. |
| **Por que** | O Claude Code tem hierarquia clara: `ClaudeError → MalformedCommandError, AbortError, ShellError, ConfigParseError`. Permite catch granular, logging consistente, e recovery paths. |

**Exemplo concreto**:
```python
# Atual
raise SystemExit("ERROR: No pipeline.nodes section in platform.yaml")
raise SystemExit(f"ERROR: Cycle detected in DAG involving: {remaining}")

# Sugestao
class MadrugaError(Exception):
    """Base para todos os erros madruga.ai."""

class PipelineError(MadrugaError):
    """Erro no pipeline DAG."""

class ValidationError(MadrugaError):
    """Erro de validacao de input."""

# Uso
raise ValidationError("No pipeline.nodes section in platform.yaml")
raise PipelineError(f"Cycle detected in DAG: {remaining}")
```

**Impacto**: Testes podem capturar erros especificos. Logger pode classificar. `dag_executor.py` pode decidir retry vs abort baseado no tipo.

---

#### M3. Connection Management (Context Manager Consistente)

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | `dag_executor.py` faz `conn = get_conn()` e `conn.close()` manual em 5+ lugares, incluindo em branches de erro. Um `return 0` antes do `conn.close()` = leak. |
| **Sugestao** | Usar `with get_conn() as conn:` em 100% dos casos. O `_ClosingConnection` ja suporta isso. |
| **Por que** | O Claude Code usa context managers para TUDO (AbortController hierarchy, file locks, transactions). Resource leak e um dos bugs mais sutis — funciona em 99% dos testes mas falha em producao sob carga. |

**Exemplo concreto**:
```python
# Atual (dag_executor.py linhas 374-464)
conn = get_conn()
# ... 90 linhas de logica ...
if node.gate in HUMAN_GATES:
    conn.close()       # facil esquecer
    return 0
# ... mais logica ...
conn.close()           # e se exception antes?

# Sugestao
with get_conn() as conn:
    # ... toda a logica ...
    if node.gate in HUMAN_GATES:
        return 0       # _ClosingConnection fecha automaticamente
```

**Impacto**: Elimina classe inteira de bugs de resource leak. Ja temos a infraestrutura (`_ClosingConnection`) — so falta usar consistentemente.

---

#### M4. Fail-Closed Defaults nos Skills

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | Skills que nao definem `gate` default para `"auto"` em `parse_dag()`. `optional` default para `False`. Mas nao ha validacao de que o gate type e valido. |
| **Sugestao** | Validar gate types contra um set canonico. Default seguro: se um gate desconhecido aparecer, tratar como `human` (fail-closed). |
| **Por que** | O Claude Code usa fail-closed em tudo: `isConcurrencySafe: false` (assume nao-seguro), `isReadOnly: false` (assume que escreve). Um typo em `gate: "humam"` passaria silenciosamente como auto hoje. |

**Impacto**: Previne execucao acidental de nodes sem aprovacao humana por typo no YAML.

---

### P2 — Media Prioridade (consistencia e manutenibilidade)

---

#### M5. Memoizacao para Operacoes Repetidas

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | `_discover_platforms()` le o filesystem toda vez. `_check_fts5()` ja usa memoizacao (global `_FTS5_AVAILABLE`). Inconsistente. |
| **Sugestao** | Usar `functools.lru_cache` para `_discover_platforms()` e funcoes que leem `platform.yaml`. Invalidar no `sync` e `new`. |
| **Por que** | O Claude Code tem 3 estrategias de memoizacao (`memoizeWithTTL`, `memoizeWithTTLAsync`, `memoizeWithLRU`) usadas consistentemente. A `_check_fts5()` ja mostra que entendemos o padrao — so falta generalizar. |

**Impacto**: `platform.py status --all` le N vezes o filesystem. Com cache, 1 vez.

---

#### M6. Structured Logging (JSON para CI, Human para CLI)

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | Mix de `print(f"[ok]")`, `log.info()`, e `print()` direto. Nao ha formato estruturado para CI. |
| **Sugestao** | Padronizar: `log.*()` para operacoes, `print()` so para output final do usuario. Adicionar flag `--json` para output estruturado em CI. |
| **Por que** | O Claude Code tem dual output: human-readable para CLI, NDJSON streaming para SDK/CI (`structuredIO.ts`, `ndjsonSafeStringify.ts`). Nosso `platform.py status --all --json` ja faz isso para status — generalizar para todo o pipeline. |

**Impacto**: CI pode parsear output sem regex. Errors tem contexto maquina-legivel.

---

#### M7. Testes para Skills (Contrato Validation)

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | `skill-lint.py` valida frontmatter e estrutura. Mas nao testa se o contrato de 6 passos e seguido no corpo do skill. |
| **Sugestao** | Adicionar validacoes ao linter: (1) skill referencia `pipeline-contract-base.md`? (2) tem `## Step 0: Prerequisites`? (3) tem `## Output Directory`? (4) frontmatter `gate` e valido? |
| **Por que** | O Claude Code tem `extractSearchText()` com "drift caught by automated tests" — qualquer mudanca no tool que quebre o formato do transcript e detectada. Nosso skill-lint ja existe — so falta expandir as regras. |

**Impacto**: Previne drift silencioso quando alguem edita um skill e remove uma secao do contrato.

---

#### M8. Graceful Shutdown no DAG Executor

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | Se `dag_executor.py` recebe SIGINT durante um dispatch, o subprocess pode ficar orfao. Nao ha signal handler. |
| **Sugestao** | Adicionar signal handler que: (1) mata o subprocess ativo, (2) grava checkpoint no DB, (3) imprime comando de resume. |
| **Por que** | O Claude Code tem shutdown orquestrado em 6 etapas (disable mouse → unmount Ink → print resume hint → flush analytics). Nosso executor lida com timeout mas nao com interrupcao. |

**Exemplo concreto**:
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

**Impacto**: Ctrl+C nao deixa processos orfaos. Usuario sabe como retomar.

---

#### M9. Path Security Basica

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | Paths construidos com string concatenacao ou Path join. `ensure_repo.py` executa `git clone` com URL do usuario. Sem sanitizacao. |
| **Sugestao** | Validar: (1) nomes de plataforma contra `^[a-z0-9-]+$`, (2) URLs de repo contra patterns conhecidos, (3) paths contra traversal (`..`). |
| **Por que** | O Claude Code tem 6 camadas de path security (UNC blocking, case-insensitive comparison, symlink resolution, NTFS detection, device blocking). Nao precisamos de tudo isso, mas validacao basica de nomes e essencial. |

**Impacto**: Previne `platform.py new "../../../etc"` ou injection via nome de plataforma.

---

#### M10. Deferred Knowledge Loading

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | Cada skill declara `> **Contract**: Follow .claude/knowledge/pipeline-contract-base.md` como texto — o LLM precisa ler o arquivo. Se 5 skills rodam em sequencia, o mesmo arquivo e lido 5 vezes. |
| **Sugestao** | Criar um mecanismo de `@include` ou cache de knowledge files por sessao, similar ao `@include` directive do Claude Code CLAUDE.md system. |
| **Por que** | O Claude Code tem deferred tool loading (`ToolSearchTool` carrega schemas on-demand) e file dedup (`file_unchanged` stubs). Cada re-leitura consome tokens — em 5 skills isso sao ~1,000 tokens desperdicados. |

**Impacto**: Economia de tokens. Skills mais rapidos.

---

### P3 — Baixa Prioridade (nice-to-have, considerar em epics futuros)

---

#### M11. Race-to-Resolve para Human Gates

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | Human gates pausam o pipeline e exigem `gate approve <run-id>` via CLI. Unica forma de aprovacao. |
| **Sugestao** | Dado que epic 014 e sobre Telegram notifications, adicionar aprovacao via Telegram message (e.g., "approve NNN") como segunda fonte racing com CLI. |
| **Por que** | O Claude Code faz 5 fontes racing (UI, bridge, channel, hooks, classifier) via `createResolveOnce()`. Para nos, 2 fontes (CLI + Telegram) ja seria um salto de UX. |

**Impacto**: Aprovar gates do celular sem abrir terminal.

---

#### M12. Stale-While-Revalidate para Platform Status

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | `platform.py status` consulta DB + filesystem a cada chamada. |
| **Sugestao** | Cache em memoria com TTL de 30s. Retorna stale imediatamente, revalida em background. |
| **Por que** | Padrao `memoizeWithTTL` do Claude Code. Util quando dashboard faz polling frequente. |

**Impacto**: Status instantaneo para dashboard.

---

#### M13. Telemetry Markers para Analytics

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | `post_save.py` grava skill completion no DB com timestamps. Sem metricas de duracao ou custo. |
| **Sugestao** | Adicionar campos: `duration_seconds`, `token_count`, `cost_usd` (do output JSON do claude -p). |
| **Por que** | O Claude Code rastreia `totalCostUSD`, `totalAPIDuration`, `toolDuration` por turn. Saber quanto cada skill custa permite otimizar a sequencia do pipeline. |

**Impacto**: Dados para otimizar pipeline. "Qual skill e mais caro? Qual da mais retry?"

---

#### M14. Multi-Writer Safety no DB

| Aspecto | Atual | Sugestao |
|---------|-------|----------|
| **Como esta** | `db.py` documenta o risco: "concurrent long-running writes may hit SQLITE_BUSY". Sem lock file. |
| **Sugestao** | Adicionar file-based lock (como o Claude Code usa `lockfile.lockSync()`) para operacoes de escrita criticas. |
| **Por que** | Se dois `dag_executor.py` rodam simultaneamente para plataformas diferentes, compartilham o mesmo `madruga.db`. WAL + busy_timeout ajuda, mas nao resolve escritas longas. |

**Impacto**: Previne corrupcao em cenarios de CI paralelo.

---

## Parte 3: Resumo Executivo

### O Que NAO Mudar

| Area | Motivo |
|------|--------|
| SQLite como state store | Mais limpo que singleton em memoria (abordagem do Claude Code). Manter. |
| Config.py como leaf-of-DAG | 14 linhas, zero imports. Perfeito. Nao adicionar logica. |
| Skill contract de 6 passos | Equivalente ao tool contract do Claude Code. Ja funciona. |
| Circuit breaker no executor | Implementacao classica e correta. Nao complicar. |
| Knowledge files separados | Separacao de concerns. Manter on-demand loading. |
| Copier template system | Nao existe equivalente no Claude Code. Vantagem nossa. |

### Roadmap de Melhorias Sugerido

| Fase | Melhorias | Esforco | Impacto |
|------|-----------|---------|---------|
| **Imediato** (proximo epic) | M3 (context managers), M4 (fail-closed gates) | 1h | Alto — elimina bugs de leak e typo |
| **Curto prazo** (1-2 sprints) | M1 (schemas), M2 (error hierarchy), M8 (graceful shutdown) | 4h | Alto — confiabilidade do pipeline |
| **Medio prazo** (3-4 sprints) | M5 (memoizacao), M6 (structured logging), M7 (skill lint++) | 4h | Medio — consistencia e DX |
| **Backlog** | M9 (path security), M10 (deferred loading), M11 (race gates), M12 (stale cache), M13 (telemetry), M14 (DB lock) | 8h+ | Variado — avaliar por epic |

### Principio Guia

> **Do Claude Code**: "Fail-closed defaults. Deny always wins. Defense in depth."
>
> **Traduzido para madruga.ai**: Valide inputs na entrada, feche resources no finally, trate gates desconhecidos como human, e nunca confie em string concatenacao para paths.

---

> **Gerado**: 2026-04-01 | **Fonte**: Comparacao de `madruga.ai` (4,855 LOC Python + 4,506 LOC skills) com `@anthropic-ai/claude-code` v2.1.88 (2,215 files TypeScript)
