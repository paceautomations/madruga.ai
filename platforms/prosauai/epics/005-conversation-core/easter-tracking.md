# Easter Tracking — prosauai 005-conversation-core

Started: 2026-04-12T12:05

## Melhoria — madruga.ai
- **Branch switch sistematico**: todos os nodes pre-implement (specify, clarify, plan, tasks, analyze-post) mudaram branch para `main` durante execucao; dag_executor reverteu automaticamente. O `--disallowedTools Bash(git checkout:*)` esta no dispatch mas `claude -p` provavelmente usa `git switch` ou mecanismo interno. Verificar se `Bash(git switch:*)` tambem precisa estar na disallowedTools.
- System prompt sizes razoaveis: specify=26KB, clarify=22KB, plan=17KB, implement=23KB, qa=38KB — todos abaixo de 80KB.
- **Phase dispatch metricas incorretas**: `implement:phase-2` registrou `duration_ms=4475` e `tokens_out=48` no DB, mas log mostra 16min reais e "4/4 tasks done". O recording de metricas no phase dispatch mode captura dados do wrapper, nao do subprocess claude real.
- **Auto-commit falhou por `.hypothesis`**: dag_executor tentou `git add .` apos implement, mas `.hypothesis/` causou erro (`paths are ignored by .gitignore`). Warning non-blocking mas auto-commit nao funcionou. Precisa filtrar ignored files antes de `git add`.
- **Implement marcou `epic_nodes.implement` como `done` com tasks incompletas**: apos SIGKILL, 39/63 tasks estavam completed + 1 cancelled, mas `epic_nodes.implement.status='done'`. O dag_executor nao checa se TODAS as sub-tasks foram concluidas antes de marcar o node como done. Corrigido manualmente resetando para `pending`.

## Melhoria — prosauai
- Implement tasks nao commitam automaticamente — 39 tasks geraram 42 arquivos (9285 LOC) que ficaram uncommitted. Easter nao consegue resumir apos restart porque `_checkout_epic_branch` checa `git status --porcelain`. Candidato a melhoria: dag_executor commitar automaticamente apos cada fase ou ao final do implement node.
- `.hypothesis/unicode_data/` modificado como side-effect de tests — nao era tracked nem gitignored corretamente.

## Incidents criticos

### docker-compose.yml dirty tree (2026-04-12 09:04)
- **Symptom:** Easter falhou ao dispatch com `DirtyTreeError`
- **Detection:** journalctl log — `ensure_repo.DirtyTreeError` no primeiro dispatch attempt
- **Root cause:** Volume mount `config/routing:/app/config/routing:ro` adicionado durante epic 004 mas nao commitado. `queue_promotion.py:55` checa `git status --porcelain` antes de checkout.
- **Fix:** Commitado na branch epic/prosauai/005-conversation-core (sha `5834f38`)
- **Test:** Easter retomou automaticamente no backoff seguinte (30s)
- **Duration lost:** ~1 min

### Easter SIGKILL #1 + DirtyTreeError on resume (2026-04-12 11:48)
- **Symptom:** Easter service stopped (`Failed with result 'timeout'`), T040 orphaned as `running`
- **Detection:** `systemctl --user is-active` → `failed`; T040 running com PID morto
- **Root cause:** Algo triggerou `systemctl stop` do easter. Easter recebeu SIGTERM, T040 falhou (exitcode 143), tentou retry, mas systemd escalou para SIGKILL apos timeout de 64s. No restart, 42 arquivos uncommitted das tasks T001-T039 bloquearam o checkout.
- **Fix:** (1) Cancelado row orfao T040. (2) Commitado 42 arquivos (sha `0d15a36`). (3) Restaurado `.hypothesis/`. (4) Reiniciado easter.
- **Test:** Easter retomou e avancou para analyze-post
- **Duration lost:** ~4 min

### Easter SIGKILL #2 durante judge (2026-04-12 12:07)
- **Symptom:** Easter morto novamente durante judge node
- **Detection:** `systemctl --user is-active` → `failed`
- **Root cause:** Mesmo padrao — `systemctl stop` externo triggerou SIGTERM → SIGKILL. Judge cancelado.
- **Fix:** Cancelado judge row orfao. Resetado `epic_nodes.implement` e `epic_nodes.analyze-post` para `pending` (implement tinha sido marcado done com tasks faltando). Reiniciado easter apos melhorias no `make up`.
- **Test:** Easter retomou implement a partir de T040 com phase dispatch mode
- **Duration lost:** ~15 min (inclui tempo de melhorias no easter)

## Sintese (2026-04-12)

### Root causes
- **Dirty tree no repo externo bloqueando checkout** — afetou 2 incidents (docker-compose.yml + 42 arquivos uncommitted). Causa raiz: implement tasks escrevem codigo mas nao commitam; `_checkout_epic_branch` rejeita dirty tree. Fix: commits manuais (sha `5834f38`, `0d15a36`). Prevencao: easter agora faz auto-commit apos implement (melhoria implementada durante a sessao).
- **Easter SIGKILL por stop externo** — afetou 2 incidents (T040 + judge). Causa raiz: algo triggerou `systemctl --user stop madruga-easter` durante execucao (provavelmente hooks de melhorias no madruga.ai). O stop-sigterm timeout de 64s nao e suficiente para o subprocess claude terminar gracefully. Prevencao: considerar `TimeoutStopSec=120` no service file.

### Improvement opportunities
- **Tooling**: dag_executor deve commitar automaticamente apos cada fase do implement (nao so ao final) para evitar DirtyTreeError em restarts
- **Tooling**: metricas de duration/tokens no phase dispatch mode estao incorretas (phase-2: 4.5s registrado vs 16min real). Investigar `_record_run_result()` para phase nodes.
- **Pipeline**: `epic_nodes.implement` foi marcado `done` com 39/63 tasks — o guard `_aggregate_completed_nodes` no easter.py funciona, mas o `upsert_epic_node` chamado pelo `post_save` marca done prematuramente. Precisa de guard adicional.
- **Pipeline**: auto-commit do implement falha com `.hypothesis` ignored — filtrar `--ignore-errors` ou listar arquivos explicitamente em vez de `git add .`
- **Skills**: `claude -p` muda branch para `main` em todo node (branch switch sistematico). Safety net funciona (revert automatico), mas e desperdicio. Adicionar `Bash(git switch:*)` ao disallowedTools.
- **Infra**: `TimeoutStopSec=64` no systemd e curto para nodes longos (judge ~12min). Aumentar para 120s ou usar `KillMode=mixed` para matar subprocess antes do main.

### Metrics
- Incidents: 3
- Time lost: ~20 min
- Fixes committed: 2 (sha `5834f38`, `0d15a36`)
- Tests added: 0 (incidents foram operacionais, nao bugs de codigo)
- Total pipeline duration: ~5h (12:05 → 16:56, com pausas e melhorias)
- Total implement tasks: 63 (39 task-by-task + 24 phase dispatch)
- All 12 L2 nodes completed successfully
