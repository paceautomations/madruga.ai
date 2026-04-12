# Easter Tracking — prosauai 005-conversation-core

Started: 2026-04-12

## Melhoria — madruga.ai
- **Branch switch sistematico**: `specify` e `clarify` (2/2 nodes) mudaram branch para `main` durante execucao; dag_executor reverteu automaticamente em ambos. O `--disallowedTools Bash(git checkout:*)` esta no dispatch mas `claude -p` provavelmente usa `git switch` ou execucao interna nao coberta pela blocklist. Verificar se `Bash(git switch:*)` tambem precisa estar na disallowedTools. O revert funciona (safety net ok), mas o branch switch e desperdicio de ciclos e risco latente.
- System prompt sizes razoaveis: specify=26KB, clarify=22KB, plan=17KB — todos bem abaixo do threshold de 80KB. Eficiencia de tokens ok nesta fase.
- **Phase dispatch metricas incorretas**: `implement:phase-2` registrou `duration_ms=4475` e `tokens_out=48` no DB, mas o log mostra 16min reais e "4/4 tasks done". O `_record_run_result()` provavelmente captura metricas do wrapper (rapido) e nao do subprocess claude real. Portal mostra dados enganosos. Investigar como `tokens_in/out` e `duration_ms` sao computados no phase dispatch mode vs task-by-task mode.

## Melhoria — prosauai
- Implement tasks nao commitam automaticamente — 39 tasks geraram 42 arquivos (9285 LOC) que ficaram uncommitted. Easter nao consegue resumir apos restart porque `_checkout_epic_branch` checa `git status --porcelain`. Candidato a melhoria: dag_executor commitar automaticamente apos cada N tasks ou ao final do implement node.
- `.hypothesis/unicode_data/` modificado como side-effect de tests — nao era tracked nem gitignored. Adicionar ao `.gitignore` do prosauai.

## Incidents criticos

### docker-compose.yml dirty tree (2026-04-12 09:04)
- **Symptom:** Easter falhou ao dispatch com `DirtyTreeError`
- **Detection:** journalctl log — `ensure_repo.DirtyTreeError` no primeiro dispatch attempt
- **Root cause:** Volume mount `config/routing:/app/config/routing:ro` adicionado durante epic 004 mas nao commitado. [ensure_repo.py:168](../../.specify/scripts/ensure_repo.py#L168) checa `git status --porcelain` antes de checkout.
- **Fix:** Commitado na branch epic/prosauai/005-conversation-core (sha `5834f38`). [docker-compose.yml](../../../prosauai/docker-compose.yml)
- **Test:** Easter retomou automaticamente no backoff seguinte (30s). Dispatch do node `specify` iniciou com sucesso.
- **Duration lost:** ~1 min (backoff automatico)

### Easter SIGKILL + DirtyTreeError on resume (2026-04-12 11:48)
- **Symptom:** Easter service stopped (`Failed with result 'timeout'`), T040 orphaned as `running`
- **Detection:** `systemctl --user is-active madruga-easter` → `failed`; T040 running com PID morto
- **Root cause:** Algo triggerou `systemctl stop` do easter (possivelmente trabalho de melhorias no madruga.ai). Easter recebeu SIGTERM, T040 falhou (exitcode 143), tentou retry, mas systemd escalou para SIGKILL apos timeout de 64s. No restart, `_checkout_epic_branch` encontrou 42 arquivos uncommitted (output das tasks T001-T039) + `.hypothesis/` dirty.
- **Fix:** (1) Cancelado row orfao T040 no DB. (2) Commitado 42 arquivos na branch epic (sha `0d15a36`). (3) Restaurado `.hypothesis/` com `git checkout --`. (4) Reiniciado easter. Easter retomou com implement=completed, avancou para analyze-post.
- **Test:** Easter retomou no backoff seguinte apos tree limpa. `analyze-post` dispatched com sucesso.
- **Duration lost:** ~4 min (SIGKILL + DirtyTreeError + commit + restart)

## Sintese
(preenchido no ultimo tick)
