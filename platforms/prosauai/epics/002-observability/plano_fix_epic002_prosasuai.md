---
title: "Plano de Correção — Achados operacionais durante o Epic 002-observability"
epic: "002-observability"
platform: prosauai
date: 2026-04-10
status: proposed
owner: gabrielhamu
---

# Plano de Correção — Achados operacionais durante o Epic 002

## Sumário Executivo

Durante a execução assistida do epic 002-observability do prosauai, **12 problemas reais** foram identificados no madruga.ai (repo-tooling). Nenhum é bloqueante para o epic em si (que completou implement 51/51 e está em judge no momento da redação), mas juntos eles causaram:

- **1 corrupção de SQLite** (`row missing from index`) com perda de estado
- **4 zumbis de `pipeline_runs`/`traces`** acumulados por dias sem limpeza
- **Cegueira operacional total** — dag_executor não aparece no journald quando rodado via systemd
- **Crise de diagnóstico** por 30+ minutos enquanto eu caçava por que "não tem nada running"
- **Métricas cosmeticamente erradas** no portal (`16/12 nodes completed`)

Este plano consolida causa raiz de cada problema, compara alternativas com base em best practices atuais (validadas via Context7 contra OTel, SQLite e Python logging docs), e propõe um caminho de correção priorizado por severidade × reversibilidade × custo.

**Regra de leitura**: cada problema tem *Sintoma → Causa raiz → Evidência → Alternativas → Recomendação → Plano de aplicação*. Pule para o **Resumo & Priorização** no fim se quiser só o TL;DR.

---

## Classificação dos Achados

| # | Severidade | Título | Causa raiz (1-linha) | Ação recomendada |
|---|---|---|---|---|
| A1 | 🔴 BLOCKER | `.pipeline/madruga.db` tracked no git | Arquivo binário de runtime versionado com WAL ativo | Untrack + seed script idempotente |
| A2 | 🔴 BLOCKER | `dag_executor` cego no journald | `_configure_logging()` nunca roda quando o easter é iniciado via `uvicorn easter:app` | Mover logging config para `lifespan` startup |
| A3 | 🔴 BLOCKER | Zumbis em `pipeline_runs`/`traces` nunca reconciliados | Stale cleanup só roda em `resume` do epic corrente; traces de outros epics ficam órfãos para sempre | Startup sweep global no easter |
| A4 | 🟡 WARNING (já fixado) | Easter com conn SQLite stale do inode deletado | Conexão do lifespan segurada forever; reseed recria inode | **Já corrigido (commit `a879b46`)**, follow-up: aplicar em outros endpoints |
| A5 | 🟡 WARNING | Portal mostra `16/12` (implement sub-tasks inflam contagem) | `completed_nodes` conta cada `implement:T00N` como node separado | Contar implement como 1 node, 100% só quando TODAS as tasks terminam |
| A6 | 🟡 WARNING | `post_save.py` falha silenciosa com FK constraint | Assume que `upsert_epic` foi chamado antes mas não valida nem auto-cria | Auto-upsert stub em ausência + erro claro |
| A7 | 🟡 WARNING | 2 testes do easter pre-existing broken | Patches em `easter.asyncio.sleep` mas código usa `_interruptible_sleep` | Reescrever os 2 testes para mockar `_interruptible_sleep` |
| A8 | 🟡 WARNING | Easter shutdown com timeout de 2min e SIGKILL em filhos | `TimeoutStopSec=15s` + subprocess claude que ignora SIGTERM | Aumentar timeout + propagar sinal pros filhos |
| A9 | 🟡 WARNING | Gap de 30-60s entre `implement:T_i` e `T_{i+1}` no portal | `insert_run()` é chamado DEPOIS do subprocess terminar, não antes | Criar row `running` antes do dispatch |
| A10 | 🔵 NIT | `platforms/prosauai/epics/003-router-mece/` órfão untracked | Diretório de experimento anterior sem registro no DB nem roadmap | Revisar + decidir: deletar ou registrar formalmente |
| A11 | 🔵 NIT | Logs do easter sem `trace_id` binding | Estamos desenvolvendo observability mas não temos observability sobre o próprio tooling | Adicionar structlog contextvars bind |
| A12 | 🔵 NIT | Naming inconsistente: `easter` vs `madruga-easter` | Service name vs module name divergem | Padronizar um ou documentar o outro |

---

## A1 — `.pipeline/madruga.db` tracked no git

### Sintoma

- `git checkout <branch>` sobrescreve o arquivo enquanto o easter daemon tem fds abertos
- Stash do DB perde o `madruga.db-wal` (ignorado no `.gitignore`) → reaplicar o stash traz um snapshot sem as últimas escritas da WAL
- Testemunhei hoje: `sqlite3.DatabaseError: database disk image is malformed` depois de um `git stash pop` seguido por operação normal

### Causa raiz

`git ls-files .pipeline/` mostra `madruga.db` rastreado, mas `.gitignore` já ignora `madruga.db-wal` e `madruga.db-shm`. Isso é a **pior combinação possível**: o git controla o arquivo principal mas ignora os arquivos auxiliares que são parte integral do estado quando WAL está ativo. Qualquer `git checkout`/`stash`/`reset` pode:

1. Substituir o arquivo principal pelo snapshot da branch destino
2. Deixar um WAL órfão no filesystem que referencia inodes/páginas que não existem mais no arquivo trocado
3. Corromper índices quando o SQLite tentar recuperar estado a partir de um WAL inconsistente

Evidência da corrupção real vista hoje:
```
integrity_check: ('row 189 missing from index idx_pipeline_runs_trace',)
integrity_check: ('row 191 missing from index idx_pipeline_runs_platform_started',)
```
Ambos foram recuperáveis via `REINDEX`, mas o sintoma seguinte poderia ser perda de dados.

### Evidência no codebase

```bash
$ cat .gitignore | grep madruga
.pipeline/madruga.db-wal
.pipeline/madruga.db-shm

$ git ls-files .pipeline/madruga.db
.pipeline/madruga.db

$ git log --oneline -- .pipeline/madruga.db | head -3
17d9de7 feat: epic 001 Channel Pipeline — full L2 cycle
a2de626 fix: prevent false staleness from hook re-registration
5551850 feat: epic 023 commit traceability
```

O DB é re-commitado a cada épico. Uma convenção implícita — ninguém documenta, mas cada epic deixa um DB "seed" para a próxima sessão.

### Alternativas

| Opção | Prós | Contras | Risco |
|---|---|---|---|
| **(a) Untrack + `.gitignore`** | Trivial, elimina toda a classe de bug. Ninguém tem mais que pensar em stash/checkout. | Perde seed data para quem clona do zero — precisa criar mecanismo de seed explícito. | Quem já tem checkout continua com o arquivo; `git update-index --skip-worktree` resolve o intermediário. |
| **(b) Untrack + `seed.py` idempotente** ⭐ | Opção (a) + resolve seed corretamente. `seed.py` lê de `.pipeline/migrations/` e popula dados canônicos (platforms, epics shipped, pipeline_nodes). | Requer escrever o `seed.py` (~200 LOC). | Seed drift: se alguém esquece de atualizar o script quando adiciona dados novos, novos contribuidores pegam estado inconsistente. Mitigação: CI valida `make seed && diff` contra snapshot conhecido. |
| **(c) Manter tracked, mas checkpointar antes de cada operação git** | Zero mudança estrutural. Commit hook roda `PRAGMA wal_checkpoint(TRUNCATE)` antes de commit/stash. | Não resolve `git checkout` (que escreve no arquivo sem pre-hook). Solução parcial. | Outros engenheiros ou ferramentas podem fazer checkout sem passar pelo hook. |
| **(d) Migrar para Postgres local** | Resolve 100%, alinha com Supabase do prosauai. | Reescrita grande do madruga.ai (toda a camada db_*.py assume SQLite). | Escopo muito maior que o problema. Não recomendado agora. |
| **(e) Usar SQLite `VACUUM INTO` para produzir seed.db separado** | Arquivo "seed.db" é tracked, arquivo "madruga.db" é gitignored. Copier roda `seed.db → madruga.db` no setup. | Dois arquivos pra manter. Ainda exige convenção pra atualizar o seed. | Pequeno — mais complexo que (b) sem vantagem clara. |

### Recomendação: **(b) Untrack + seed script idempotente**

**Por quê:** Elimina a classe de bug. O SQLite docs explícitamente documentam que `PRAGMA wal_checkpoint(TRUNCATE)` é necessário antes de mover/copiar um DB com WAL ativo — algo que git checkout não faz. Context7 confirma que a Online Backup API é o único caminho "safe" para copiar DBs em uso, e essa API não é compatível com versionamento git. Seed scripts são o padrão da indústria para este caso (Rails `db:seed`, Django `loaddata`, Prisma `seed.ts`).

### Plano de aplicação

```bash
# Fase 1 — Untrack sem perder conteúdo (uma única vez, por todos os devs):
git rm --cached .pipeline/madruga.db
echo ".pipeline/madruga.db" >> .gitignore
echo ".pipeline/madruga.db-journal" >> .gitignore  # belt-and-suspenders
git commit -m "chore: untrack .pipeline/madruga.db — recriated via seed.py"
```

```python
# Fase 2 — Criar `.specify/scripts/seed.py` (idempotente, < 200 LOC):
# Responsabilidades:
#   1. get_conn() + migrate() (já existe)
#   2. upsert_platform("madruga-ai", ...) + upsert_platform("prosauai", ...) + test-plat
#   3. Para cada epic shipped conhecido: upsert_epic() com status="shipped"
#   4. Seed pipeline_nodes a partir de .specify/pipeline.yaml
#   5. NÃO inserir dados de runs/traces históricos (esses são ephemeral por máquina)
```

```makefile
# Fase 3 — Integrar no Makefile:
seed:
    python3 .specify/scripts/seed.py

# Onboarding novo contributor:
# 1) clone
# 2) make seed  (cria madruga.db do zero com dados canônicos)
# 3) systemctl --user start madruga-easter
```

```bash
# Fase 4 — Validar em CI:
# - make seed  (fresh install)
# - pytest .specify/scripts/tests/  (testes usam conn separada, não .pipeline/madruga.db)
```

**Esforço**: 4-6h (300-400 LOC incluindo tests + docs).
**Reversibilidade**: Alta — voltar para tracking é um `git add -f` e remover `.gitignore` entry.
**Impacto nos users**: Zero se o `seed.py` for idempotente (pode rodar em cima de DB existente sem quebrar).

---

## A2 — `dag_executor` cego no journald quando via systemd

### Sintoma

Durante o `implement` do epic 002, o claude subprocess morreu entre T018 e T019 e eu gastei 30+ minutos tentando entender o que aconteceu — o `journalctl --user -u madruga-easter` só mostrava linhas HTTP de `/api/*`. Zero mensagens do `dag_executor`. Zero erro. Silêncio completo. No fim descobri que era só um gap cosmético (T019 já estava rodando, mas em janela fora do poll).

### Causa raiz (verificada no código)

1. `.specify/scripts/dag_executor.py:43`: `log = logging.getLogger(__name__)` — usa `logging` padrão, **não structlog**
2. `.specify/scripts/easter.py:792`: `_configure_logging()` configura `logging.basicConfig(format="%(message)s", level=INFO)` + structlog wrapping
3. `.specify/scripts/easter.py:826`: `_configure_logging(args.verbose)` é chamado **dentro de `easter.main()`**
4. `~/.config/systemd/user/madruga-easter.service:7`: `ExecStart=uvicorn easter:app --host 127.0.0.1 --port 18789`

O systemd roda `uvicorn` diretamente. O `uvicorn` importa `easter:app` e chama ASGI lifecycle. **`easter.main()` nunca é invocado.** Portanto `_configure_logging()` nunca roda. O root `logging` fica no default da biblioteca (WARNING, sem handler configurado), e todos os `log.info(...)` do `dag_executor` são suprimidos silenciosamente.

Para structlog também há problema: o `logger` do easter é `structlog.get_logger(__name__)`, configurado no topo do módulo. Mas `dag_executor` NÃO usa structlog — usa `logging` padrão. São dois universos isolados.

### Alternativas

| Opção | Prós | Contras | Risco |
|---|---|---|---|
| **(a) Chamar `_configure_logging()` dentro do `lifespan`** | Mínima mudança. 1 linha de código. | Se `uvicorn` já configurou seus próprios handlers, pode conflitar. | Baixo — `basicConfig` é idempotente e uvicorn respeita root config se feito antes. |
| **(b) Unificar tudo em structlog + logging.LoggingHandler** ⭐ | Padrão OTel Python: `LoggingHandler` captura `logging` e emite como LogRecord que o structlog/OTel processa. Logs aparecem tanto no journald quanto no Phoenix (forward-compat com epic 002!). | Refactor de ~50 call sites do `log.info/error/warning` no `dag_executor.py`. | Médio — precisa de teste cuidadoso. |
| **(c) Shim: reconfigurar logging no import top de `easter.py`** | Rode `_configure_logging()` no import, antes mesmo do uvicorn instanciar app. | Hack — polui o import-time com side effects. | Alto risco de ordem de import. |
| **(d) Mudar service para chamar `easter.main()`** | `ExecStart=python3 -m easter` ou similar. Garante que main() roda. | Exige wrapper porque `uvicorn.run(app, ...)` dentro de `main()` bloqueia diferente do notify protocol systemd-notify. Precisaria de adaptação. | Médio. |

### Recomendação: **(a) + (b) combinados**

**Fase curta (a)**: mover a chamada `_configure_logging()` para **dentro do `lifespan()`**, logo no início (antes de qualquer `logger.info`). Isso resolve 90% do problema hoje, com 5 linhas de diff.

**Fase longa (b)**: substituir `log = logging.getLogger(__name__)` do `dag_executor` por `log = structlog.get_logger(__name__)` e padronizar com o easter. Context7 confirma que padrão OTel Python usa `LoggingHandler` para capturar `logging` padrão — quando epic 002 concluir, a mesma `LoggingHandler` vai emitir pro Phoenix com `trace_id` automaticamente injetado. Faz parte da mesma iniciativa.

### Plano de aplicação

```python
# Fase curta (a) — em easter.py lifespan, após acquire do lock:
@asynccontextmanager
async def lifespan(app: FastAPI):
    _easter_state.easter_state = "running"
    _easter_state.start_time = time.time()

    # Logging config — MUST run before any logger.info() call.
    # When easter is started via `uvicorn easter:app` (as systemd does),
    # easter.main() never runs, so _configure_logging() must be invoked here.
    verbose = os.environ.get("MADRUGA_VERBOSE", "").lower() in ("1", "true", "yes")
    _configure_logging(verbose)

    # ... rest of lifespan
```

```python
# Fase longa (b) — em dag_executor.py:
# Substituir:
#   log = logging.getLogger(__name__)
# Por:
#   import structlog
#   log = structlog.get_logger(__name__)
#
# E padronizar chamadas:
#   log.info("Resuming ... with epic=%s", epic_id)  →  log.info("resuming", epic=epic_id)
#
# Estimado: ~50 sites, 2-3h incluindo tests.
```

**Esforço**: fase (a) 15min; fase (b) 3-4h.
**Reversibilidade**: trivial.
**Impacto**: enorme — todo o pipeline fica debuggable em tempo real.

---

## A3 — Zumbis em `pipeline_runs`/`traces` nunca reconciliados globalmente

### Sintoma

Encontrei 4 zumbis no DB:
- `d7888b4d` (epic 001 implement:T040) — **11 horas** em `running`
- 3 traces de `021-pipeline-intelligence` — **5 dias** em `running`
- O epic 001 já está `shipped`, o 021 já está `shipped`. Mas os runs/traces continuam "running" para sempre.

O portal exibia o run `d7888b4d` como "Running" na primeira screenshot que você enviou — causando a confusão "epic 001 também tá running?". Limpei manualmente via SQL hoje.

### Causa raiz (verificada no código)

`dag_executor.py:1310-1337` tem stale cleanup, mas **apenas sob duas condições**:

1. `run_pipeline_async` é chamado com `resume=True`
2. Limpeza filtrada por `platform_id=? AND epic_id=?` — **só para o epic corrente**

Resultado: runs/traces órfãos de epics **diferentes** (ou de epics já shipped) nunca são tocados. Além disso, quando o easter é morto via SIGKILL (como aconteceu hoje no `systemctl restart` que deu timeout), nenhum cleanup roda.

### Alternativas

| Opção | Prós | Contras | Risco |
|---|---|---|---|
| **(a) Startup sweep no `lifespan()` do easter** ⭐ | Roda 1× por restart. Simples: `UPDATE pipeline_runs SET status='failed', error='zombie — daemon restart' WHERE status='running' AND started_at < now - 1 hour`. Idem traces. | Pode haver race com um restart rápido enquanto outro epic está realmente rodando (poll_interval 15s). Solução: usar `now - 1h` threshold. | Baixo — timing conservador. |
| **(b) Watchdog periódico no `dag_scheduler`** | Roda a cada poll. Detecta zumbis mais cedo. | 1× por poll é overkill — 99% das vezes não há zumbi novo. Custo baixo mesmo assim. | Baixo. |
| **(c) Constraint de DB (CHECK)** | Banco rejeita estados inválidos. | SQLite não tem TTL nativo; precisaria de triggers ou app-level clock. Solução frágil. | Médio — complica migrations. |
| **(d) Process supervisor pattern** | Daemon mantém tabela de "filhos que devem existir" e cross-refs contra `ps`. | Complexo, exige OS-specific code. | Alto. |

### Recomendação: **(a) Startup sweep + (b) Watchdog periódico como belt-and-suspenders**

**Por quê:** (a) cobre o caso comum (restart após crash). (b) cobre o caso raro (daemon vivo mas epic travado por bug). Ambos são 10-15 LOC cada. Melhor ter os dois.

### Plano de aplicação

```python
# Em easter.py:
async def _sweep_zombies(conn: sqlite3.Connection) -> None:
    """Mark stale 'running' runs/traces as failed — zombies from crashed daemons."""
    now = _now()
    threshold = "-1 hour"  # runs older than 1h without heartbeat are zombies

    runs_swept = conn.execute(
        "UPDATE pipeline_runs SET status='failed', "
        "error=COALESCE(error, 'zombie — daemon restart detected'), "
        "completed_at=? "
        "WHERE status='running' AND started_at < datetime('now', ?) "
        "AND (gate_status IS NULL OR gate_status != 'waiting_approval')",
        (now, threshold),
    ).rowcount

    traces_swept = conn.execute(
        "UPDATE traces SET status='failed', completed_at=? "
        "WHERE status='running' AND started_at < datetime('now', ?)",
        (now, threshold),
    ).rowcount

    conn.commit()
    if runs_swept or traces_swept:
        logger.warning(
            "zombie_sweep_done",
            runs_swept=runs_swept,
            traces_swept=traces_swept,
        )

# Chamar dentro de lifespan() após migrate():
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... lock acquire, logging config ...
    from db import get_conn, migrate
    conn = get_conn()
    migrate(conn)
    await _sweep_zombies(conn)  # ← novo
    app.state.db_conn = conn
    # ... rest
```

```python
# Em dag_scheduler (belt-and-suspenders):
# Rodar sweep a cada 60s (4 polls), não a cada poll:
_last_sweep_monotonic = 0.0
async def dag_scheduler(...):
    global _last_sweep_monotonic
    while not shutdown_event.is_set():
        try:
            if time.monotonic() - _last_sweep_monotonic > 60:
                poll_conn = get_conn()
                try:
                    await _sweep_zombies(poll_conn)
                finally:
                    poll_conn.close()
                _last_sweep_monotonic = time.monotonic()
            # ... rest of poll loop
```

**Esforço**: 1-2h incluindo tests.
**Reversibilidade**: alta.
**Impacto**: resolve "limpeza de crises anteriores sem intervenção manual".

---

## A4 — Easter com connection SQLite stale (JÁ FIXADO)

**Status**: Commit `a879b46` aplica fix B (reopen conn por poll/request) em `dag_scheduler` e `/api/sessions`.

**Follow-up necessário** (não é o mesmo bug, é o mesmo padrão):

Outros endpoints HTTP do easter que usam `request.app.state.db_conn`:
- `/api/traces` (linha 662)
- `/api/traces/{trace_id}` (linha 670)
- `/api/runs` (linha 688)
- `/api/evals` (linha 711)
- `/api/stats` (linha 726)
- `/api/export/csv` (linha 763)
- `/api/commits` (linha 786)
- `/api/commits/stats` (linha 805)

Todos vulneráveis ao mesmo bug: depois de `make seed` + `systemctl reload`, esses endpoints retornam dados do inode deletado. Menos crítico porque são read-only e o portal refaz as queries, mas ainda inconsistente.

### Recomendação: dependency injection com `get_conn` helper

```python
# Em easter.py:
from fastapi import Depends

async def get_fresh_conn():
    from db import get_conn as _gc
    conn = _gc()
    try:
        yield conn
    finally:
        conn.close()

@app.get("/api/traces")
async def list_traces(
    platform_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
    conn = Depends(get_fresh_conn),  # ← substitui request.app.state.db_conn
):
    ...
```

Apply em todos os 8 endpoints. Remover `app.state.db_conn` completamente (deixar apenas o `conn` do lifespan para cleanup final). 

**Esforço**: 30min.
**Reversibilidade**: trivial.

---

## A5 — Portal mostra `16/12` durante implement

### Sintoma

Portal card exibe `completed_nodes / total_nodes`. Como cada `implement:T001..T051` é inserido em `pipeline_runs` como uma row completed, o contador vai 5 → 6 → 7 → ... conforme as tasks passam. `total_nodes` permanece 12 (o tamanho do DAG L2). Resultado visual: `7/12`, `20/12`, `56/12`. Confuso.

Seu feedback claro: **"implement é 1 node só; 39/40 tasks ≠ 0.975 node, é 0 nodes. Só conta como concluído quando 100% das tasks terminaram."**

### Causa raiz

`easter.py:597-603`:
```python
agg = conn.execute(
    "SELECT SUM(cost_usd) AS cost, SUM(tokens_in) AS tin, SUM(tokens_out) AS tout, "
    "COUNT(CASE WHEN status='completed' THEN 1 END) AS completed, "
    "MAX(COALESCE(completed_at, started_at)) AS last_activity "
    "FROM pipeline_runs WHERE trace_id=?",
    (tid,),
).fetchone()
```

`agg["completed"]` conta **cada row** como um node. Mas implement tem muitas rows — uma por task.

### Alternativas

| Opção | Prós | Contras | Risco |
|---|---|---|---|
| **(a) `COUNT(DISTINCT base_node)`** onde `base_node` = `substr(node_id, 0, instr(node_id, ':'))` ou `node_id` se não contém ':' | Simples, SQL puro. | `implement:T001` vira `implement` no distinct — ok, mas se o filtro ignora linhas incompletas, ainda temos a dúvida "como saber que implement terminou?". | Médio. |
| **(b) Lógica em Python: contar implement como 1 se e somente se `implement_completed == implement_total`** ⭐ | Semantica exata do seu feedback. Portal mostra 5/12 durante implement, salta pra 6/12 só quando 51/51 termina. | ~15 linhas Python no endpoint. | Baixo. |
| **(c) Coluna `parent_node` em `pipeline_runs`** | Schema-level. Consultas mais simples. | Migration + backfill. Não resolve o cálculo em si, só organiza melhor. | Médio. |
| **(d) Normalizar `pipeline_runs` em 2 tabelas (runs + run_tasks)** | Design limpo. | Refactor grande. Muitos call sites. | Alto. |

### Recomendação: **(b) Lógica em Python**

O fix cabe em uma helper:

```python
def _count_completed_nodes(conn: sqlite3.Connection, trace_id: str) -> int:
    """Count DAG nodes fully complete. 'implement' only counts when ALL tasks done."""
    rows = conn.execute(
        "SELECT node_id, status FROM pipeline_runs WHERE trace_id=?",
        (trace_id,),
    ).fetchall()

    completed: set[str] = set()
    implement_total = 0
    implement_done = 0

    for r in rows:
        nid = r["node_id"]
        status = r["status"]
        if nid.startswith("implement:"):
            implement_total += 1
            if status == "completed":
                implement_done += 1
        else:
            if status == "completed":
                completed.add(nid)

    # 'implement' counts only when every sub-task is done
    if implement_total > 0 and implement_done == implement_total:
        completed.add("implement")

    return len(completed)
```

Chamar em `/api/sessions` no lugar do `agg["completed"]`.

**Bonus**: também ajusta `total_nodes` — quando a taxa é `implement_done/implement_total`, o portal pode exibir isso como "progress sub-indicator" dentro do card:

```python
session.update({
    "completed_nodes": _count_completed_nodes(conn, tid),
    "implement_progress": {
        "done": implement_done,
        "total": implement_total,
    } if implement_total else None,
})
```

Frontend pode mostrar: `5/12 (implement: 32/51)` durante a execução.

**Esforço**: 1h incluindo testes + frontend ajuste.
**Reversibilidade**: alta.

---

## A6 — `post_save.py` falha silenciosa com FK constraint

### Sintoma

Hoje, ao rodar `post_save.py --platform prosauai --epic 002-observability --artifact epics/002-observability/pitch.md`, recebi:

```
sqlite3.IntegrityError: FOREIGN KEY constraint failed
```

Sem indicação de QUAL FK falhou. Era porque o epic 002 ainda não existia na tabela `epics`.

### Causa raiz

`db_pipeline.py:upsert_epic_node` faz `INSERT INTO epic_nodes (platform_id, epic_id, ...)` que tem FK `(platform_id, epic_id) REFERENCES epics`. Se o epic não existe, a FK dispara exceção crua que sobe até `sys.exit(1)` sem context.

### Alternativas

| Opção | Prós | Contras |
|---|---|---|
| **(a) Auto-upsert stub do epic** | Mais amigável. Zero friction no onboarding. | Silenciosamente mascara casos reais de "epic id errado" — se você errar o nome, cria um stub novo. |
| **(b) Erro explícito com instrução** ⭐ | Falha rápida. Mensagem ensina a resolver. | Exige 1 passo extra (rodar `upsert_epic`) no fluxo atual. |
| **(c) Ambos: `--create-epic` flag** | Flexibilidade. | Mais complexidade. |

### Recomendação: **(b) com hint explícito**

```python
# Em post_save.py, wrap do upsert_epic_node:
try:
    upsert_epic_node(conn, platform_id, epic_id, node_id, ...)
except sqlite3.IntegrityError as e:
    if "FOREIGN KEY" in str(e):
        # Check which FK failed
        epic_exists = conn.execute(
            "SELECT 1 FROM epics WHERE platform_id=? AND epic_id=?",
            (platform_id, epic_id),
        ).fetchone()
        if not epic_exists:
            sys.stderr.write(
                f"ERROR: epic '{epic_id}' not found for platform '{platform_id}'.\n"
                f"Run first:\n"
                f"  python3 -c \"from db_pipeline import upsert_epic; "
                f"import sqlite3; c=sqlite3.connect('.pipeline/madruga.db'); "
                f"upsert_epic(c, '{platform_id}', '{epic_id}', "
                f"status='in_progress', branch_name='epic/{platform_id}/{epic_id}'); "
                f"c.commit()\"\n"
            )
            sys.exit(1)
    raise
```

Ou mais limpo: criar `--auto-create-epic` flag e deixar OFF por default. Usuários que sabem o que estão fazendo ativam.

**Esforço**: 30min.

---

## A7 — 2 testes do easter pre-existing broken

### Sintoma

- `test_dag_scheduler_poll_interval` falha: `assert mock_sleep.await_count >= 1 → 0 >= 1`
- `test_dag_scheduler_respects_sequential_constraint` hang forever

Verificado por stash-and-rerun: ambos quebram **sem o meu fix**. Bug pre-existing.

### Causa raiz

Os testes patcham `easter.asyncio.sleep`:

```python
patch("easter.asyncio.sleep", new_callable=AsyncMock, side_effect=lambda _: shutdown.set())
```

Mas o código real (`easter.py:90-99`) usa:

```python
async def _interruptible_sleep(shutdown_event, seconds):
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=seconds)
        return True
    except TimeoutError:
        return False
```

`asyncio.wait_for` internamente usa `asyncio.sleep` só como timer do timeout, mas o uso é diferente: o mock com `side_effect=lambda _: shutdown.set()` não dispara porque `wait_for` não chama `asyncio.sleep` do namespace `easter.`.

### Recomendação

Reescrever os 2 testes para patchar `easter._interruptible_sleep` diretamente:

```python
# Antes:
patch("easter.asyncio.sleep", new_callable=AsyncMock, side_effect=lambda _: shutdown.set())

# Depois:
async def _fake_sleep(event, seconds):
    event.set()
    return True
patch("easter._interruptible_sleep", new=_fake_sleep)
```

**Esforço**: 30min incluindo verificar que todos os usos similares em outros testes estão corretos.

---

## A8 — Easter shutdown timeout 2min + SIGKILL em filhos

### Sintoma

`systemctl --user stop madruga-easter` ou `restart` demora 2 min e termina com SIGKILL em processos `sh`, `node`, `npm`, `claude`. Mensagem do systemd:

```
Killing process 1276279 (sh) with signal SIGKILL.
Killing process 1276280 (node) with signal SIGKILL.
Failed to kill control group ... ignoring: Invalid argument
```

### Causa raiz

- `madruga-easter.service:11`: `TimeoutStopSec=15`
- `dag_executor.run_pipeline_async` spawna `claude -p` via `asyncio.create_subprocess_exec`, sem signal propagation
- Claude subprocess pode durar minutos por task
- SIGTERM do systemd chega só no uvicorn, não nos filhos, então o lifespan tenta shutdown mas os filhos continuam vivos
- Depois de 15s, systemd SIGKILL tudo

### Alternativas

| Opção | Prós | Contras | Risco |
|---|---|---|---|
| **(a) Aumentar `TimeoutStopSec=120`** | Simples. 1 linha. | Não resolve o real problema — só mascara. Upgrade/restart fica lento. | Baixo. |
| **(b) Propagar SIGTERM pros filhos no shutdown** ⭐ | Resolve causa raiz. Filhos terminam limpos. | Precisa trackear PIDs dos subprocesses em `_running_epics` state. ~30 LOC. | Médio. |
| **(c) Start subprocess no `os.setsid`/process group + kill group** | Padrão Unix para "mata árvore inteira". | Claude subprocess pode reagir mal a SIGTERM no middle of a task. | Médio. |
| **(d) Implementar `shutdown()` gracioso no dag_scheduler** que espera tasks em progresso terminarem (bounded) | Mais elegante. | Requer estado compartilhado entre dag_scheduler e lifespan shutdown. | Médio. |

### Recomendação: **(b) + (a) como fallback**

```python
# Em dag_executor.py, tracker global dos children:
_active_subprocesses: set[asyncio.subprocess.Process] = set()

async def dispatch_with_retry_async(...):
    # ...
    proc = await asyncio.create_subprocess_exec(...)
    _active_subprocesses.add(proc)
    try:
        # ... wait for proc
    finally:
        _active_subprocesses.discard(proc)

# Em easter.py lifespan shutdown:
except* Exception as eg:
    # ...
finally:
    # Kill children before closing DB
    from dag_executor import _active_subprocesses
    for proc in list(_active_subprocesses):
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
    # Give them 5s to cleanup
    if _active_subprocesses:
        await asyncio.sleep(5)
    for proc in list(_active_subprocesses):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    conn.close()
```

E bumpar `TimeoutStopSec=60` como fallback seguro.

**Esforço**: 2h.
**Impacto**: restart rápido e limpo, logs claros do shutdown.

---

## A9 — Gap de 30-60s no portal entre `implement:T_i` e `T_{i+1}`

### Sintoma

Durante implement, o portal mostra `current_node: null` por dezenas de segundos entre tasks. Subprocess claude está vivo, mas o portal não sabe.

### Causa raiz (verificada em `dag_executor.py:578-589`)

```python
# run_implement_tasks loop:
success, error, stdout = await dispatch_with_retry_async(task_node, ...)  # blocks for minutes
# ...after subprocess returns...
metrics = parse_claude_output(stdout) if stdout else {}
run_id = insert_run(conn, ..., tokens_in=..., tokens_out=..., cost_usd=..., ...)
complete_run(conn, run_id, status="completed")
```

**O `insert_run()` é chamado DEPOIS do subprocess retornar**, com os metrics já populados. Então entre o start do subprocess (`await dispatch...`) e o `insert_run`, não há row representando a task em progresso.

No path não-implement (`dag_executor.py:1462`), a lógica é INVERSA: `insert_run` vem ANTES do dispatch.

### Recomendação

Corrigir inconsistência: em `run_implement_tasks`, criar o row com `status='running'` antes do dispatch, depois atualizar:

```python
# Em run_implement_tasks (substitui o bloco atual):
for task in pending:
    # ... resume logic ...

    # Insert running row BEFORE dispatch (portal visibility)
    run_id = insert_run(
        conn,
        platform_name,
        f"implement:{task.id}",
        epic_id=epic_slug,
        trace_id=trace_id,
    )
    # Subprocess can take minutes
    success, error, stdout = await dispatch_with_retry_async(task_node, ...)

    # Now update with metrics
    metrics = parse_claude_output(stdout) if stdout else {}
    if success:
        complete_run(
            conn, run_id, status="completed",
            tokens_in=metrics.get("tokens_in"),
            tokens_out=metrics.get("tokens_out"),
            cost_usd=metrics.get("cost_usd"),
            duration_ms=metrics.get("duration_ms"),
        )
    else:
        complete_run(conn, run_id, status="failed", error=error)
```

Isso exige que `complete_run` aceite metrics kwargs (já aceita — linha 1562 mostra uso similar).

**Esforço**: 30min.
**Impacto**: portal mostra `implement:T019 running` em tempo real. User experience significativamente melhor.

---

## A10 — `platforms/prosauai/epics/003-router-mece/` órfão

### Sintoma

Diretório untracked contém `pitch.md` + `decisions.md`, não está no roadmap nem no DB.

### Causa raiz

Provavelmente experimento de sessão anterior (quick-fix, draft mode, ou epic-breakdown que foi descartado).

### Recomendação

Investigar conteúdo dos 2 arquivos e decidir:
1. Se é relevante → `upsert_epic` + registrar no roadmap (mas bumpa a numeração de novo)
2. Se é lixo → `rm -r` e commitar a remoção

**Esforço**: 15min.

---

## A11 — Logs do easter sem `trace_id` binding

### Sintoma

Ironia pura: estamos desenvolvendo observability pro prosauai mas o próprio madruga.ai/easter não tem. Logs do easter não têm `trace_id` nem `epic_id` bound, impossibilitando correlação entre "daemon fez X" e "epic Y estava rodando".

### Recomendação

Usar `structlog.contextvars.bind_contextvars` no início de cada dispatch:

```python
# Em dag_scheduler, ao dispatchear um epic:
from structlog.contextvars import bind_contextvars, unbind_contextvars

bind_contextvars(
    epic_id=epic_id,
    platform=epic_platform_id,
    trace_id=trace_id or "unknown",
)
try:
    result = await run_pipeline_async(...)
finally:
    unbind_contextvars("epic_id", "platform", "trace_id")
```

Depois disso, todo `logger.info(...)` dentro de `run_pipeline_async` automaticamente carrega esses campos.

Combinando com A2 (logging unificado), o resultado é correlação automática entre logs do easter, logs do dag_executor, e no futuro traces do Phoenix.

**Esforço**: 1h.

---

## A12 — Naming `easter` vs `madruga-easter`

### Sintoma

- Module name: `easter` (`easter.py`)
- Service name: `madruga-easter.service`
- Repo name: `madruga.ai`
- Portal label: "Easter Service"

Inconsistente. Quem chega novo precisa mapear 3 nomes pra mesma coisa.

### Recomendação

Escolher 1 e documentar em `CLAUDE.md`:
- **Padronizar em `madruga-easter`** → renomear module? Não — muitos imports. Só documentar que "easter é o daemon do madruga". 1 linha no CLAUDE.md.

**Esforço**: 5min.

---

## Resumo & Priorização

### Matriz de priorização

| # | Título | Severidade | Esforço | Impacto | Ordem |
|---|---|---|---|---|---|
| A1 | `.pipeline/madruga.db` untrack + seed.py | 🔴 | 4-6h | Elimina corrupção de DB recorrente | **1** |
| A2 | `_configure_logging` no lifespan | 🔴 | 15min | Debug visibility imediato | **2** |
| A3 | Startup + periodic zombie sweep | 🔴 | 1-2h | Métricas corretas no portal | **3** |
| A4 | Follow-up HTTP endpoints DI | 🟡 | 30min | Consistência pós-reseed | **4** |
| A9 | insert_run antes do dispatch | 🟡 | 30min | Portal UX em implement | **5** |
| A5 | `completed_nodes` contar implement como 1 | 🟡 | 1h | Portal UX correto | **6** |
| A6 | `post_save.py` FK error explicit | 🟡 | 30min | Dev UX | **7** |
| A8 | Subprocess tree shutdown | 🟡 | 2h | Restart limpo | **8** |
| A2-long | `dag_executor` → structlog | 🔴 (longo) | 3-4h | Debug ricos, correlation IDs | **9** |
| A11 | `bind_contextvars` no dispatch | 🔵 | 1h | Correlation logs | **10** |
| A7 | Reescrever 2 testes broken | 🟡 | 30min | CI saudável | **11** |
| A10 | Decidir sobre `003-router-mece/` | 🔵 | 15min | Limpeza | **12** |
| A12 | Documentar naming | 🔵 | 5min | Onboarding | **13** |

**Total esforço**: ~15-20h de dev bem focado. Pode ser quebrado em 3 PRs:
- **PR-1 (crítico, ~2h)**: A2 (lifespan logging), A3 (zombie sweep), A4 (DI endpoints)
- **PR-2 (UX, ~2h)**: A5 (implement counting), A6 (FK hint), A9 (insert_run)
- **PR-3 (estrutural, ~6h)**: A1 (untrack DB + seed.py), A2-long (structlog), A8 (shutdown)
- **PR-4 (housekeeping, ~2h)**: A7, A10, A11, A12

### Ordem sugerida de execução

1. **Hoje (unblock)**: A2 + A3 + A4 — resolve debug blindness + zumbis sem romper nada. Merge rápido na main.
2. **Esta semana**: A5 + A6 + A9 — portal UX fica confiável antes de rodar mais epics.
3. **Próxima semana**: A1 + A2-long + A8 — estrutural, merece cuidado e code review.
4. **Quando tiver tempo**: A7, A10, A11, A12.

### Riscos globais do plano

| Risco | Impacto | Mitigação |
|---|---|---|
| Migrar DB untrack quebra onboarding de quem já tem checkout | Alto | Comunicar via CLAUDE.md + incluir `make seed` no setup |
| Startup sweep muito agressivo marca como zombie tasks reais | Médio | Threshold de 1h é conservador. Logs do sweep permitem auditoria. |
| Mudança em `insert_run` order quebra metrics do portal | Baixo | `complete_run` aceita kwargs — zero regression |
| Fix A2 expõe tantos logs novos que confunde | Baixo | Default em INFO (não DEBUG) já filtra |

### Métricas de sucesso

Após todas as correções:

1. **Zero zumbis** detectados após 1 semana de operação normal (query: `SELECT COUNT(*) FROM pipeline_runs WHERE status='running' AND started_at < datetime('now', '-1 hour')` retorna 0)
2. **Portal mostra `current_node` em <5s** depois de qualquer transition (A5 + A9)
3. **Logs do dag_executor visíveis** em `journalctl --user -u madruga-easter` (A2)
4. **Zero `FOREIGN KEY constraint failed`** no uso normal (A6)
5. **`make seed && systemctl restart madruga-easter`** funciona sem corrupção (A1)
6. **`systemctl restart` em <15s** (A8 + TimeoutStopSec)

---

## Best Practices consultadas (Context7)

| Tema | Fonte | Aprendizado aplicado |
|---|---|---|
| SQLite hot backup | `/websites/sqlite_docs` | Online Backup API é a ÚNICA forma segura de copiar DB com WAL ativo — git checkout/stash não são, portanto A1 é inevitável |
| OTel Python + logging | `/open-telemetry/opentelemetry-python` | `LoggingHandler` unifica `logging` + OTel + structlog em uma pipeline — aplicado em A2-longo |
| W3C Trace Context propagation | `/websites/opentelemetry_io` | `TraceContextTextMapPropagator` é o carrier canônico — aplicado em A11 |
| structlog contextvars | OTel Python docs | `bind_contextvars` para correlação cross-async-task — aplicado em A11 |

---

## Observação meta

A **execução do próprio epic 002** provou várias premissas do pitch:

- ✅ **speckit.clarify é valioso**: preencheu 5 decisões técnicas não-óbvias (InMemorySpanExporter, sampler, SpanQL queries, Phoenix version, health endpoint degradation) — sem intervenção humana
- ✅ **speckit.plan gera 4 artefatos coerentes**: plan.md + research.md + data-model.md + quickstart.md + contracts/
- ✅ **speckit.tasks estruturou 51 tasks** com `[P]` markers corretos e fases explícitas
- ✅ **speckit.implement executou 51 tasks** sem falha, ritmo ~$1/task, custo total ~$60
- ⚠️ **Portal UX durante execução longa é frágil** — isso motivou A5, A9, A11
- ⚠️ **Debug sem logs foi doloroso** — isso motivou A2 como prioridade máxima

O plano acima **não é sobre o epic 002 em si** (que está indo bem) — é sobre o tooling madruga.ai que amadureceu menos rápido que o pipeline de skills.

---

## Próximo passo sugerido

```bash
# 1. Criar branch para o conjunto de fixes do PR-1 (crítico)
git checkout main
git checkout -b fix/easter-observability-hotfixes

# 2. Aplicar A2 + A3 + A4 (2h)
# 3. Rodar testes do easter (ignorar os 2 broken pre-existing)
python3 -m pytest .specify/scripts/tests/test_easter.py::test_dag_scheduler_detects_active_epic -v

# 4. PR pequeno e focado
gh pr create --title "fix(easter): logging config + zombie sweep + DI for HTTP endpoints" \
  --body "..."

# 5. Merge, restart easter, validar que logs do dag_executor aparecem no journald
systemctl --user restart madruga-easter
journalctl --user -u madruga-easter -f | grep -v "HTTP/1.1"
```

*Fim do plano.*
