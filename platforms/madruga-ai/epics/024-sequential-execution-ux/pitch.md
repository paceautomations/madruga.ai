---
title: "024 — Sequential Execution UX"
epic_id: 024-sequential-execution-ux
platform: madruga-ai
status: drafted
created: 2026-04-10
updated: 2026-04-10
---
# Epic 024 — Sequential Execution UX

> Abrir o repo de uma plataforma externa e ver a branch ativa sendo construída em tempo real. Enfileirar 2–3 epics com um comando e deixá-los executar em sequência sem intervençao humana entre eles.

## Problema

O fluxo atual de implementação de epics em plataformas externas (ex: prosauai) tem dois atritos críticos:

**Atrito 1 — Invisibilidade durante execução**
O `dag_executor` cria um git worktree em `{repos_base_dir}/{org}/{repo}-worktrees/{epic}`. O desenvolvedor que abre `~/repos/paceautomations/prosauai` no editor vê o estado de `develop` — não o epic sendo construído. Para acompanhar a implementação em tempo real é necessário navegar manualmente até o diretório do worktree, que muda a cada epic.

**Atrito 2 — Ausência de fila automática**
Não existe mecanismo para enfileirar 2–3 epics para execução sequencial. Hoje o fluxo é: (a) rodar epic N, (b) esperar terminar, (c) rodar `/madruga:epic-context` manualmente para o epic N+1. Qualquer ausência do operador entre epics paralisa o pipeline.

Consequências observadas:
1. Desenvolvedor perde visibilidade do progresso real durante o ciclo L2
2. Pipeline pausa entre epics aguardando intervenção manual desnecessária
3. A assimetria conceitual "branch no madruga.ai + worktree no repo externo" gera confusão operacional persistente

## Apetite

1–2 semanas. Escopo fechado: flag `isolation: branch`, status `queued`, hook de auto-promoção, migração 017. Sem auto-merge automático de PRs, sem stack de mais de 3 epics simultâneos, sem UI no portal (isso seria epic futuro).

## Dependências

Nenhum blocker externo. Depende de:
- `009_add_drafted_status.sql` — padrão de migração SQLite a ser seguido (rec-tabela)
- `_running_epics` global em `easter.py` — ponto de inserção do hook
- `ensure_repo.py::ensure_repo()` — retorna path do clone principal (já existe)

## Captured Decisions

| # | Área | Decisão | Referência Arquitetural |
|---|------|---------|------------------------|
| 1 | Isolamento externo | Substituir worktree por checkout direto no clone principal via `repo.isolation: branch` opt-in em `platform.yaml` | ADR-006 (sequential invariant), ADR-004 (stdlib) |
| 2 | Status enum | Adicionar status `queued` ao CHECK constraint da tabela `epics` via migration 017 (padrão rec-tabela SQLite) | ADR-004 (SQLite WAL), migration 009 (precedente) |
| 3 | Trigger do hook | Inserir chamada de promoção após `_running_epics.discard(epic_id)` no `dag_scheduler` de `easter.py` — síncrono, dentro do poll loop | ADR-006 (asyncio single-process) |
| 4 | Semântica drafted vs queued | Manter `drafted` = "planejado sem comprometimento de ordem". `queued` = "próximo na fila, executar quando slot abrir". Statuses distintos com transições explícitas | ADR-009 (Shape Up epics) |
| 5 | Cascade base para branch | Ao promover epic N+1: criar branch de epic N no clone externo (worktree atual = clone principal depois da mudança). Se N já foi merged, `git fetch` + branch de `origin/base_branch` | ADR-010 (subprocess git) |
| 6 | Guard dirty tree | Antes de `git checkout -b` no clone externo: `git status --porcelain` — se output não vazio, pausar epic com gate humano via ntfy | ADR-006 (gate types), ADR-010 (subprocess) |
| 7 | Failure handling | 3 retries com backoff (1s, 2s, 4s) → status `blocked` + ntfy alert. Idempotente: upsert de branch_name ocorre DEPOIS de criar a branch, prevenindo estado inconsistente | ADR-006 (resilience) |
| 8 | Subprocess vs library | Manter raw `subprocess` para operações git — stdlib constraint (ADR-004), operações são simples, overhead de gitpython/pygit2 não justificado | ADR-004 (stdlib + pyyaml only) |
| 9 | Merge automático | Fora do escopo. PRs de merge permanecem gate humano para revisão de código. O hook não faz `gh pr merge`. | ADR-013 (decision gates) |
| 10 | Feature flag no hook de easter | Hook de promoção respeita env var `MADRUGA_QUEUE_PROMOTION` (default **off**). Mesmo com código commitado, em runtime o hook só ativa quando explicitamente habilitado — padrão já usado em `MADRUGA_BARE_LITE`, `MADRUGA_KILL_IMPLEMENT_CONTEXT`, etc | ADR-021 (dispatch kill-switches), ADR-006 (safe rollouts) |

## Resolved Gray Areas

**1. worktree serve para algo com `isolation: branch`?**
Não para plataformas com `isolation: branch`. O `work_dir` em `implement_remote.py:158` hoje é `create_worktree()`. Com a flag, passa a ser `ensure_repo()` — o clone principal na branch do epic. O arquivo `worktree.py` permanece no codebase para plataformas que optem por `isolation: worktree` (padrão). Se todas as plataformas migrarem para branch, vira dead code e pode ser removido em epic de cleanup.

**2. GitHub PR diff mostra só as mudanças do epic N+1 ou inclui N?**
Validado via pesquisa. O diff de PR usa `git diff main...branch-B` (3-dot syntax), que calcula a partir do merge-base. Após o PR de N ser merged para develop, o merge-base de N+1 passa a ser o commit de merge de N. O PR de N+1 mostra *apenas* os commits de N+1. Correto e limpo sem rebase obrigatório. Rebase opcional (`git rebase origin/develop`) disponível para linearizar histórico.

**3. O que acontece com os artifacts do draft (pitch.md) quando o epic é promovido?**
Draft artifacts vivem em `platforms/{platform}/epics/NNN/pitch.md` commitados na branch onde o draft foi criado (geralmente `main`). Durante a promoção, `promote_next_queued()` faz `git checkout main -- platforms/{platform}/epics/NNN/` na nova branch do epic, trazendo os arquivos do draft. Commit automático com mensagem `feat: promote queued epic NNN (delta review)`.

**4. Quem chama `--queue`? É flag de `epic-context` ou comando separado?**
Flag de `epic-context`: `/madruga:epic-context --queue prosauai 004-slug`. Comportamento: cria/atualiza pitch.md em `main` (igual a `--draft`) + seta status=`queued` no DB (diferente de `--draft` que seta `drafted`). Isso sinaliza ao easter que este epic deve ser promovido automaticamente quando o slot abrir. Epics `drafted` continuam sendo promoção manual.

**5. `compute_epic_status()` não precisa ser atualizado para `queued`?**
Sim, precisa. A função tem guard: `if current_status in ("blocked", "cancelled", "shipped", "drafted"): return current_status, None`. Precisa adicionar `"queued"` a esta lista — epics na fila não devem ter status derivado automaticamente de nós concluídos (ainda não executaram). Sem essa mudança, um epic `queued` poderia ser promovido erroneamente para `in_progress` pela lógica de nós.

**6. `_EPIC_STATUS_MAP` em db_pipeline.py precisa de entrada?**
Sim. Adicionar `"queued": "queued"` ao dicionário (linha ~30). Sem isso, `post_save.py --epic-status queued` seria silenciosamente mapeado para `None` e poderia causar erros de INSERT.

## Applicable Constraints

- **ADR-004 (stdlib)**: Sem novas dependências. Tudo via subprocess, pathlib, sqlite3.
- **ADR-006 (asyncio single-process)**: O hook de promoção roda síncrono no poll loop. Operações git são blocking I/O — usar `asyncio.to_thread()` para não bloquear o event loop (padrão já usado em `dag_executor.py`).
- **ADR-010 (claude -p subprocess)**: `implement_remote.py` usa `cwd=str(work_dir)` para lançar `claude -p`. Com `isolation: branch`, `work_dir` muda de `worktree_path` para `clone_path`. Sem impacto no subprocess em si — só no diretório.
- **Sequential invariant (pipeline-dag-knowledge.md §8)**: O lock `_running_epics` permanece global. O hook de promoção respeita: só promove quando `_running_epics` está vazio. Não existem dois epics `in_progress` simultâneos.
- **SQLite WAL + single-writer (ADR-004)**: Promoção usa `db_write_lock()` (fcntl, já em `db_core.py`) para proteger o upsert de status.
- **Migration pattern (009_add_drafted_status.sql)**: Seguir exatamente o padrão de rec-tabela com `PRAGMA foreign_keys = OFF/ON` e índices recreados.

### Auto-sabotage guardrails (self-ref platform)

Epic 024 modifica arquivos que o próprio pipeline executa em runtime (`easter.py`, `db_pipeline.py`, migration no `.pipeline/madruga.db`). Para evitar que a implementação quebre o pipeline durante o próprio ciclo, o plan/tasks DEVE respeitar as 6 camadas abaixo:

1. **Camada 0 — Quarentena do daemon**: `systemctl --user stop madruga-easter` ANTES de iniciar o `/speckit.implement`. Não restartar até `/madruga:qa` passar verde. Easter importa `easter.py` no boot — edits no módulo não afetam o daemon até restart, mas qualquer restart acidental no meio do epic carrega código meio-cozido.
2. **Camada 1 — Backup do DB**: `cp .pipeline/madruga.db .pipeline/madruga.db.bak-pre-024` antes de aplicar migration 017. `.pipeline/madruga.db` não é tracked (A1) — `git checkout` não restaura. Se migration brickar: stop easter → restaurar do backup.
3. **Camada 2 — Ordem aditiva das tasks**: Cada task deve manter o código base funcional isoladamente. Ordem obrigatória: (a) migration 017 primeiro, aditiva ao CHECK constraint; (b) `db_pipeline.py` — status map + guard, aditivo, não reescreve código existente; (c) `platform_cli.py queue` — comando novo sem reescrita; (d) `ensure_repo.py::get_repo_work_dir` — função nova que ainda NÃO é chamada por ninguém; (e) `implement_remote.py` — troca o ponto de chamada (agora `get_repo_work_dir` vira load-bearing); (f) `easter.py` hook — ÚLTIMO, porque é o daemon. Cada commit dessa sequência roda `make test` verde antes de avançar.
4. **Camada 3 — Implementação interativa, nunca via dispatcher**: O ciclo L2 desse epic roda por chamada manual de skills no chat, NÃO via `python3 dag_executor.py --epic 024-...`. Dispatch autônomo em bare-lite + epic que reescreve o próprio `dag_executor` = cegueira garantida quando algo quebrar. Gates humanos de cada skill são inegociáveis aqui.
5. **Camada 4 — Feature flag `MADRUGA_QUEUE_PROMOTION`**: O hook de promoção inserido em `easter.py::dag_scheduler` respeita env var (default **off**). Código commitado = inativo em runtime até export explícito. Precedente: `MADRUGA_BARE_LITE`, `MADRUGA_KILL_IMPLEMENT_CONTEXT`, `MADRUGA_SCOPED_CONTEXT`, `MADRUGA_CACHE_ORDERED` (todos já em CLAUDE.md). Ver decisão #10.
6. **Camada 5 — `make test` verde entre commits**: Pre-commit hook já roda ruff/format. Pytest é manual. Convenção para 024: **nenhum commit sem `make test` verde**. Se um commit quebra testes, volta atrás antes de prosseguir — não acumula quebras.

Essas camadas são APLICÁVEIS ao `/speckit.plan` e `/speckit.tasks` — o plano e a ordem de tasks devem refleti-las literalmente. Não são sugestões.

## Suggested Approach

### Fase 1 — `repo.isolation: branch` (problema 1)

**1a. Schema e plataforma:**
- Adicionar campo opcional `repo.isolation: worktree|branch` ao `platform.yaml` (default: `worktree` para não quebrar nada existente)
- Atualizar `platforms/prosauai/platform.yaml` com `isolation: branch`

**1b. `ensure_repo.py`:**
```python
def get_repo_work_dir(platform_name: str, epic_slug: str) -> Path:
    """Retorna work_dir correto baseado em isolation mode."""
    binding = _load_repo_binding(platform_name)
    if _is_self_ref(binding["name"]):
        return REPO_ROOT
    isolation = binding.get("isolation", "worktree")
    if isolation == "branch":
        repo_path = ensure_repo(platform_name)
        _checkout_epic_branch(repo_path, platform_name, epic_slug, binding)
        return repo_path
    else:
        from worktree import create_worktree
        return create_worktree(platform_name, epic_slug)
```

**1c. `_checkout_epic_branch()`:**
```python
def _checkout_epic_branch(repo_path, platform_name, epic_slug, binding):
    branch = f"{binding['epic_branch_prefix']}{epic_slug}"
    # 1. Dirty tree guard
    status = subprocess.run(["git", "status", "--porcelain"], cwd=str(repo_path),
                            capture_output=True, text=True, check=True)
    if status.stdout.strip():
        raise DirtyTreeError(f"{repo_path} tem mudanças não commitadas. Commit ou stash antes de iniciar o epic.")
    # 2. Branch já existe → checkout
    local = subprocess.run(["git", "branch", "--list", branch], cwd=str(repo_path),
                           capture_output=True, text=True).stdout.strip()
    if local:
        subprocess.run(["git", "checkout", branch], cwd=str(repo_path), check=True)
        return
    # 3. Branch nova → cascade
    subprocess.run(["git", "fetch", "origin"], cwd=str(repo_path), check=True)
    cascade_base = _get_cascade_base(repo_path, platform_name, binding["base_branch"])
    subprocess.run(["git", "checkout", "-b", branch, cascade_base], cwd=str(repo_path), check=True)
```

**1d. `implement_remote.py`:**
- Substituir `create_worktree()` por `get_repo_work_dir()` (importar de `ensure_repo`)

### Fase 2 — Status `queued` + auto-promoção (problema 2)

**2a. Migration 017:**
```sql
-- 017_add_queued_status.sql
PRAGMA foreign_keys = OFF;
DROP TABLE IF EXISTS epics_new;
CREATE TABLE epics_new (
    -- idêntico ao atual, com 'queued' adicionado ao CHECK
    status TEXT NOT NULL DEFAULT 'proposed'
           CHECK (status IN ('proposed','drafted','queued','in_progress','shipped','blocked','cancelled')),
    -- restante igual
);
INSERT INTO epics_new SELECT * FROM epics;
DROP TABLE epics;
ALTER TABLE epics_new RENAME TO epics;
-- recriar índices
PRAGMA foreign_keys = ON;
```

**2b. `db_pipeline.py` — 3 pontos de toque:**
1. `_EPIC_STATUS_MAP`: adicionar `"queued": "queued"`
2. `compute_epic_status()`: adicionar `"queued"` ao guard de não-regressão
3. Nova função `get_next_queued_epic(conn, platform_id) -> dict | None`

**2c. `platform_cli.py` — novo sub-comando:**
```bash
python3 platform_cli.py queue prosauai 004-channel-webhook  # seta status=queued
```

**2d. `easter.py` — hook de promoção:**
```python
# Após _running_epics.discard(epic_id) no dag_scheduler:
try:
    next_epic = get_next_queued_epic(poll_conn, epic_platform_id)
    if next_epic:
        await asyncio.to_thread(
            promote_queued_epic, next_epic["platform_id"], next_epic["epic_id"]
        )
except Exception:
    logger.exception("promotion_hook_failed", epic_id=epic_id)
    # Não aborta o poll loop — falha silenciosa + ntfy
```

**2e. `promote_queued_epic()` — nova função em `platform_cli.py` ou módulo dedicado:**
```python
def promote_queued_epic(platform_id: str, epic_id: str) -> None:
    """Promove epic queued → in_progress: cria branch + traz artifacts do draft."""
    # 1. get_repo_work_dir() — já cria branch via _checkout_epic_branch()
    # 2. git checkout main -- platforms/{platform}/epics/{NNN}/ (traz pitch.md do draft)
    # 3. git commit "feat: promote queued epic {NNN} (cascade from {prev_branch})"
    # 4. DB: upsert epic status=in_progress, branch_name=...
    # Retry 3x com backoff; em falha permanente: status=blocked + ntfy
```

### Sequência de testes

1. `test_isolation_branch.py` — verifica `get_repo_work_dir()` com mock de `platform.yaml`
2. `test_dirty_tree_guard.py` — verifica que `DirtyTreeError` é levantado corretamente
3. `test_queued_status_migration.py` — verifica migration 017 idempotente
4. `test_compute_epic_status_queued.py` — verifica guard de não-regressão para `queued`
5. `test_promote_queued_epic.py` — mock de subprocess git, verifica sequência de chamadas
6. `test_easter_promotion_hook.py` — mock de `promote_queued_epic`, verifica chamada após ship
