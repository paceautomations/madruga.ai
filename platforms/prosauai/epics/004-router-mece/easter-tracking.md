---
epic: 004-router-mece
started: 2026-04-10
---
# Easter Tracking — Epic 004 Router MECE

Live incident log + session synthesis (Phase 5 do `/madruga:pair-program`).
Append-only enquanto o epic esta em execucao.

## Incident: Worktree branch collision — manual branch creation before dispatch (2026-04-10 20:06)

**Symptom:** `dag_scheduler_error` em loop (consecutive_errors=1, backoff_s=30). `git worktree add -b epic/prosauai/004-router-mece origin/epic/prosauai/003-multi-tenant-foundation` falhava com `fatal: a branch named 'epic/prosauai/004-router-mece' already exists` no repo externo `paceautomations/prosauai`.

**Detection:** Phase 1 signal — journalctl mostrou 3 `dag_scheduler_error` consecutivos em 80s logo apos promocao do epic 004.

**Root cause:** Dois problemas encadeados em [worktree.py:112-126](../../../../.specify/scripts/worktree.py#L112-L126):
1. **Manual pre-create no repo externo**: durante a promocao do draft (skill `epic-context`), criei a branch `epic/prosauai/004-router-mece` manualmente no clone principal (`/home/gabrielhamu/repos/paceautomations/prosauai`). Easter logo depois tentou criar worktree em `/home/gabrielhamu/repos/prosauai-worktrees/004-router-mece` e falhou porque a branch **ja existia localmente** (mas nao no remoto).
2. **Cascade base desatualizado**: `_get_cascade_base` escolheu `origin/epic/prosauai/003-multi-tenant-foundation` como base, mas 003 ja tinha mergeado em `develop` (commit `a7e56aa`). Mesmo se a branch nao existisse, o base point nao era o canonical `develop`.
3. **Segundo problema encadeado**: apos push da branch para origin, worktree caiu no ramo "branch exists on remote — checking out", mas falhou com `'epic/prosauai/004-router-mece' is already used by worktree at '/home/gabrielhamu/repos/paceautomations/prosauai'` porque o clone principal ainda tinha a branch como HEAD checked out. Git worktree nao permite 2 checkouts simultaneos da mesma branch.

**Fix:** Duas intervencoes cirurgicas no repo externo (zero codigo alterado em `worktree.py`):
1. `git push -u origin epic/prosauai/004-router-mece` — cria tracking remoto e faz `_branch_exists_on_remote` retornar True no proximo ciclo, desviando para o branch `if` (checkout sem `-b`).
2. `git checkout develop` no clone principal — libera a branch para o worktree separado do easter.

**Test:** Nao aplicavel — root cause foi erro operacional de mistura manual+automatico, nao bug de codigo. Contudo, worktree.py tem gap real: **nao verifica branch local antes de chamar `git worktree add -b`**. Ver Improvement Opportunities abaixo.

**Duration lost:** ~3 minutos (2026-04-10 20:06 primeiro erro → 20:09:08 worktree ready). Backoff de 30s entre tentativas manteve o custo baixo.

**Files touched (external repo, manual):**
- `[push] epic/prosauai/004-router-mece → origin/epic/prosauai/004-router-mece`
- `[checkout] /home/gabrielhamu/repos/paceautomations/prosauai → develop`

**Recovery confirmed at 20:09:08:**
- `Worktree ready: /home/gabrielhamu/repos/prosauai-worktrees/004-router-mece`
- `Skipping completed node: epic-context`
- `Dispatching node 'specify' async (skill: speckit.specify, timeout: 3000s)`
- Child process PID 1611026, wchan `do_epoll_wait` — healthy API call in progress.

## Incident: T004 scaffold timeout + successful retry (2026-04-10 20:56)

**Symptom:** `implement:T004` rodou 10:34 (limite 600s) e foi abortado pelo easter com `timeout after 600s`. Retry automatico (1/3) rodou em 55s e completou.

**Detection:** Phase 1 signal — task em `running` por mais que ~8min chamou atencao (baseline T001-T003 foi 100-200s). Journalctl mostrou o evento de timeout explicito.

**Root cause (hipotese):** T004 e scaffold trivial ("Criar arquivos `facts.py`, `engine.py`, `loader.py`, `verify.py`, `matchers.py`, `errors.py`, `__init__.py` vazios"). Scaffold foi criado (arquivos existem no worktree), mas o agent do claude -p nao conseguiu finalizar o response na primeira tentativa. Causas possiveis:
- Backpressure/latency na API Anthropic (hipotese A)
- Agent entrou em loop de auto-simplify ou trying to do extra work (hipotese B)
- Response buffer transmitindo slow token stream (hipotese C)

Sem stdout JSON capturado no primeiro dispatch (easter mata o processo antes), nao e possivel distinguir A/B/C. Baseline do epic 003 foi de ~50-80s per scaffold task, entao 10min+ e anomalo.

**Fix:** Nenhum — easter ja resolve sozinho via retry. Sistema comportou-se como design.

**Retry efficiency:** `implement:T004` dispatch #2 completou em 55s, mostrando que o trabalho ja estava feito no filesystem (scaffold files ja existiam) — agent do retry provavelmente so verificou existencia e retornou done imediatamente. Custo perdido: ~11 min (10 timeout + 12.8s backoff + 55s retry), mas sem mudanca de estado suja no DB.

**Test:** Nao aplicavel. E um case de resiliencia de pipeline, nao bug de codigo.

**Duration lost:** ~11 minutos (0 perda real de trabalho — retry aproveitou scaffold ja criado).

**Files created successfully during T004 (visto via find no worktree):**
- `prosauai/core/router/__init__.py`
- `prosauai/core/router/facts.py`
- `prosauai/core/router/engine.py`
- `prosauai/core/router/loader.py`
- `prosauai/core/router/verify.py`
- `prosauai/core/router/matchers.py`
- `prosauai/core/router/errors.py`

**Recovery confirmed at 20:57:45:**
- `Task T004 completed (4/51)` — pipeline avancou para T005

## Pattern: Silent hang in claude -p response stream (recorrente)

**Observado em:** T004 (scaffold), T006 (enums em facts.py). Ambos sao tasks triviais (scaffold vazio / enums de ~30 LOC) que hangaram no dispatch #1 e completaram em segundos no retry #2.

**Simptoma padrao:**
1. Agent executa o trabalho no filesystem (arquivos existem no worktree durante o hang)
2. Child process PID permanece vivo com `wchan=do_epoll_wait` (API network call)
3. `{"type":"result"}` final do JSON stream nao chega em tempo habil
4. Easter dispara `timeout after 600s`
5. Retry 1/3 completa em 55-90s (porque o filesystem ja tem o resultado, agent so reconhece e retorna done)

**Root cause provavel:** claude -p stream de tokens nao finaliza response apos Write tool call bem-sucedido. Pode ser:
- Agent entra em loop pos-Write tentando auto-review demorado
- Anthropic API backpressure prolongando streaming
- `--output-format json` buffer waiting no flush

**Impacto acumulado ate aqui:** ~22 min perdidos em 2 timeouts (10min + 11min cada), **zero perda de trabalho** — retries aproveitam o filesystem.

**Custo relativo:** 22 min perdidos / ~70 min total de run ate agora = ~31% overhead. Alto. Candidato #1 para improvement opportunity: reduzir timeout ou ativar early termination quando Write bem-sucedida.

**Nao intervi** — o sistema se recupera sozinho. Documentado como pattern recorrente na synthesis abaixo.

---

## Session Synthesis (em andamento)

Sera atualizado quando o epic completar (ou em checkpoint intermediario).

### Root causes (ate agora)

- **Mistura manual+automatico ao promover draft** — ao criar branches manualmente no clone principal do repo externo durante `epic-context`, quebrei o assumption do `worktree.py` de que ele e o unico criador de branches. Preventivo: quando promover draft, deixar easter criar tudo via worktree, ou pushar branches manuais para origin imediatamente (antes do primeiro dispatch).

### Improvement opportunities

- **`worktree.py` deveria detectar branch local existente**: `create_worktree` so chama `_branch_exists_on_remote`. Se a branch existe localmente mas nao remotamente, cai no ramo errado e falha com `git worktree add -b <existing>`. Fix mais limpo: adicionar `_branch_exists_locally(repo_path, branch)` e tratar 3 casos: (a) existe em remote → checkout sem `-b`; (b) existe so local → push + checkout sem `-b` ou `git worktree add <path> <branch>` (sem `-b`); (c) nao existe → create com `-b`.
- **`worktree.py` deveria verificar branch checkout collision**: antes de `git worktree add`, checar `git branch --list <branch>` + `git worktree list` para detectar que a branch ja esta checked out em outro worktree. Mensagem de erro mais clara que `'X' is already used by worktree at 'Y'`.
- **Cascade base logic desatualizado apos merge**: `_get_cascade_base` preferiu `origin/epic/prosauai/003-multi-tenant-foundation` sobre `origin/develop` apesar do 003 ja ter mergeado. Deveria preferir `origin/<base_branch>` quando a ultima shipped branch ja foi mergeada nele. Gap pre-existente, nao bloqueador, mas gera confusao.
- **`epic-context` skill deveria documentar**: quando promover draft, a skill cria branch madruga **e** branch no repo externo. Se o usuario ja criou branch manualmente, pular. Fluxo atual e inconsistente com a assumption do `worktree.py`.
- **Pair-program pre-flight deveria checar push state**: antes de deixar easter rodar, verificar que toda branch local de epic tem tracking remoto. `git rev-parse --abbrev-ref <branch>@{upstream}` retorna nao-zero se nao tem tracking.

### Metrics (ate agora)

- Incidents: 1 (worktree branch collision, 2 falhas encadeadas)
- Time lost: ~3 min
- Fixes committed: 0 (intervencoes foram operacionais no repo externo, nao em codigo)
- Tests added: 0
- Improvement items registered: 5
