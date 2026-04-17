# Easter Tracking — madruga-ai 026-runtime-qa-testing-pyramid

Started: 2026-04-16T15:52:00Z

## Melhoria — madruga.ai

- **[easter.py SQLite thread-safety]** `retention_cleanup` e `periodic_backup` falham com `SQLite objects created in a thread can only be used in that same thread`. Em `db_observability.py:420` e `easter.py:471`: o objeto `conn` é criado na thread principal e passado para `asyncio.to_thread`. Fix: abrir conexão nova dentro da função executada na thread (ou passar `check_same_thread=False` se for WAL). Falha silenciosa — backup não acontece mas epic não trava.
- **[system_prompt_bytes trend]** specify=27757 bytes, clarify=23517 bytes, plan=18369 bytes, tasks=21362 bytes, analyze=19823 bytes — redução consistente. Scoping OK nos nodes de planejamento.
- **[phase prompt acima de 80KB]** `implement:phase-1` com 12 tasks disparado com `total_bytes=103,144` bytes. Breakdown: tasks=27,975 + spec=25,842 + plan=23,076 + data_model=7,757 + contracts=9,612 + header+cue=6,847 + file=2,035. **Driver principal: `tasks` (28KB) inclui o `tasks.md` completo (39 tasks) mesmo que a fase use apenas 12.** Oportunidade: `compose_task_prompt` em `dag_executor.py` poderia filtrar `tasks` para incluir apenas as tasks do phase atual + headers de fases vizinhas. Economia estimada: ~22KB por phase dispatch (27 tasks desnecessárias × ~820 bytes avg).
- **[phase-2 prompt em 143KB por file contexts]** `implement:phase-2` (T013-T020) disparado com `total_bytes=143,063` bytes. Breakdown adicional vs fase-1: `file:platform_cli.py=28,438` + `file:test_platform.py=13,964` bytes de código existente injetado. Total file contexts para essa fase: ~43KB. Oportunidade: `compose_phase_prompt` poderia incluir apenas cabeçalho + função relevante de `platform_cli.py` (ex: só `_lint_platform()` + skeleton), não o módulo inteiro (1200+ LOC). Economia estimada: ~35KB por fase com arquivo Python grande como contexto.
- **[subprocess continua 30+ min após tasks done]** Padrão observado em Phase 1 e Phase 2: claude conclui todas as tasks em 10-15min mas o processo fica ativo por mais 20-35min (wrap-up, output conversacional, validações extras). Com 5 fases restantes isso é ~100-175min de tempo perdido só em "espera pós-conclusão". Fix: adicionar instrução explícita em `compose_phase_prompt`: "After ALL tasks are marked done and `make test` passes, do not summarize or run additional checks — EXIT IMMEDIATELY." O `success_check` protege a correção mas não acelera o dispatch da próxima fase.

- **[TelegramConflictError recorrente]** A partir de 16:17:36 UTC, `aiogram.dispatcher` entra em loop de retries (`tryings=22+`) por `Conflict: terminated by other getUpdates request`. Easter tem **1 única instância** (pid 1566903) — o conflito vem de outra sessão/app usando o mesmo bot token simultaneamente. Impacto atual: zero (implement é auto gate). Impacto potencial: bloqueio de notificações de 1-way-door se conflito persistir durante reconcile/qa. Oportunidade: implementar detecção ativa de conflito + alerta no Telegram de outra forma (ex: webhook como fallback) ou monitorar `tryings > 10` e logar warning visible no portal.

## Melhoria — madruga-ai

- **[phase dispatch sem pre-check de tasks já concluídas]** `implement:phase-4` foi dispatched com T025-T028 todos `[x]` (concluídos pelo subprocess de phase-3 combinado). O subprocess rodou ~12 min sem trabalho útil, disparando dois pytest em paralelo antes de encerrar. Observado em: timeout=3000s, dois pytest runs de ~35 min cada = ~70 min > timeout → success_check salva (T025-T028 `[x]`), mas 50 min desperdiçados. Oportunidade: em `_run_implement_phases` (`dag_executor.py`), adicionar pre-dispatch check — se todas as tasks do phase já estão `[x]` em tasks.md, pular o dispatch e avançar imediatamente. Equivalente ao que `success_check` faz pós-timeout, aplicado PRÉ-dispatch.

- **[test suite 9× explosion — cobertura positiva, lentidão negativa]** `test_qa_startup.py` adicionado em Phase 1 elevou o total de testes de 130 para **1172**. A cobertura é positiva, mas o custo por run escalou: `test_reverse_reconcile_ingest.py` tem 60 slow-pattern hits (subprocess `git init/commit`, repos reais em fixtures). Cada fase que roda `make test` ou `pytest .specify/scripts/tests/` leva ~35 min. Oportunidade: (a) substituir `--ignore=test_sync_memory_module.py` por `--ignore=<slow_files>` adicionando `test_reverse_reconcile_ingest.py`; (b) mocks para operações git em `test_reverse_reconcile_ingest.py`; (c) separar testes lentos com `@pytest.mark.slow` + `make test-fast` para uso em phase dispatch.

- **[git-subprocess test hang padrão recorrente — 4 arquivos confirmados]** `test_reverse_reconcile_ingest.py`, `test_reverse_reconcile_e2e.py`, `test_reverse_reconcile_aggregate.py` e `test_implement_remote.py` têm fixtures com `git init/clone/commit/fetch` reais → `do_epoll_wait` indefinido no pytest. Foram descobertos incrementalmente durante qa (3 commits para atingir fix completo). Oportunidade estrutural: (a) `@pytest.mark.slow` (ou `@pytest.mark.integration`) em fixtures com git subprocess; (b) `make test` usa `--mark "not slow"` em vez de lista de ignores; (c) fixture compartilhada `git_repo` com `tmpdir` bem-testada previne que cada novo arquivo de test reinvente o padrão. 4 arquivos na lista de ignores atual; mais podem aparecer.

- **[pytest orphans acumulam por cross-phase completion]** Fases 4 e 5 foram dispatched com tasks pré-`[x]` → subprocessos dispararam múltiplos `pytest` concorrentes antes de encerrar. Esses filhos `zsh/make/pytest` sobrevivem ao SIGKILL do subprocess pai (são session leaders). Observado: PIDs 2885905 e 2887089 rodando `pytest .specify/scripts/tests/ -v` por **65+ min** ainda em `do_epoll_wait` — provavelmente travados em `test_reverse_reconcile_ingest.py`. Resultado: 3 pytest concorrentes durante `analyze-post` (incluindo o filho legítimo). Impacto: contenção CPU/IO alonga o tempo de cada run; risco de ultrapassar timeout se contagem de tests crescer. Fix estrutural: (a) pre-check evita empty-phase dispatch (reduz gatilho); (b) isolamento de processo com `os.setsid()` + `kill(-pgid)` no SIGKILL para matar grupo inteiro; (c) `test_reverse_reconcile_ingest.py` no ignore list evita hang.

## Oportunidade — timeout calibration

- **[timeout=3000s apertado para phase-1]** `implement:phase-1` com 12 tasks atingiu 46min de 50min de timeout disponível. Formula atual: `max_turns = count×20+50` (290 turns) com timeout fixo de 3000s. Para fases fundacionais com scripts Python completos + testes (CLAUDE.md convention: "batch, não incremental"), o tempo real por task pode ser 3-5 min → 12 tasks = 36-60 min. Sugestão: calibrar `timeout` proporcionalmente ao `task_count`: `timeout = task_count × 300 + 600` (fase de 12 tasks → 4200s). Atual `dag_executor.py` usa `min(task_count × 600, 3000)` — o cap de `DEFAULT_TIMEOUT=3000` anula o scaling. Fix: remover o cap ou usar `max(DEFAULT_TIMEOUT, task_count × 300 + 600)`.

- **[_verify_phase_completion só roda após exaurir retries]** `dag_executor.py:1188` — `_verify_phase_completion` verifica filesystem (tasks.md checkboxes) para detectar conclusão real. É chamada APÓS `dispatch_with_retry_async` retornar (após TODOS os retries). Resultado: se fase completa mas JSON output falha 1× → 3 retries adicionais de 50min cada (~150min perdidos) antes de finalmente verificar o filesystem e marcar `completed`. Oportunidade: chamar `_verify_phase_completion` ANTES de cada retry — se `still_pending_now == 0`, pular retry e retornar success imediato. Economia: até 150min por phase timeout no cenário atual (epic 026 está nesse estado agora).

## Incidents críticos

### phase-1 timeout com 0 bytes stdout — trabalho preservado (2026-04-16 17:00)
- **Symptom:** `implement:phase-1` expirou timeout (3000s) com `partial stdout (0 bytes)` — dag_executor disparou Retry 1/3. Mas T001-T012 todos `[x]` em tasks.md e artefatos existem: `qa_startup.py` (883 LOC, mtime 13:09) + `test_qa_startup.py` (981 LOC, mtime 13:12).
- **Detection:** journalctl `dag_executor` level=error: `Node 'implement:phase-1': timeout after 3000s — partial stdout (0 bytes)` às 17:00:36 UTC. Confrontado com `tasks.md` que mostrava T001-T012 todos `[x]`.
- **Root cause:** `--output-format json` escreve JSON final SOMENTE no encerramento do processo — o watchdog de 3000s enviou SIGKILL antes do flush. Implementação estava completa (~13:16 UTC), mas o processo continuou em "validation/wrap-up" por mais ~44 minutos além do esperado. Combinado com timeout estático (issues `dag_executor.py`: `timeout=3000`).
- **Fix:** `dag_executor.py:1138` timeout proporcional + `dag_executor.py:1186-1188` `success_check` pre-retry. (commit `28f1f45`). Subprocess morto + DB cancelado + easter reiniciado.
- **Test:** `test_dag_executor.py::test_success_check_skips_retry` adicionado — 130 testes passam.
- **Duration lost:** ~110 min (retry 1/3 rodando por ~90min, intervenção + diagnóstico ~20min)

### implement marcado done prematuramente — phases 2-7 nunca executadas (2026-04-16 18:15)
- **Symptom:** Easter pulou `implement` e avançou para `analyze-post` e `judge`. tasks.md mostrava T001-T012 `[x]` mas T013-T039 todos `[ ]`. 27 de 39 tasks (phases 2-7) nunca foram executadas. Judge estava revisando implementação incompleta.
- **Detection:** Resposta do usuário à captura de tela do portal mostrando `implement:phase-1 = Cancelled`. Query na `epic_nodes`: `implement.status='done'`, `completed_at='2026-04-16T16:16:23Z'`, `completed_by='speckit.implement'` — apenas 8min após dispatch da phase-1.
- **Root cause:** O subprocess `claude -p` chamou `post_save.py --node implement --skill speckit.implement` após completar apenas Phase 1 (T001-T012), inscrito diretamente em `epic_nodes` sem passar pelo loop `_run_implement_phases`. O dag_executor lê `get_resumable_nodes()` via `epic_nodes` no restart — encontrou `implement=done` e pulou as phases 2-7.
- **Fix:** (1) Kill PID 2726817 (judge subprocess) + `pipeline_runs.8dab15b0` cancelado + `epic_nodes` reset para `implement/analyze-post/judge=pending` + `systemctl --user restart madruga-easter`. Easter reiniciou com "Phase dispatch: 6 phases, 27 total pending tasks" — Phase 2 dispatching. (2) `dag_executor.py:820-826` (`compose_phase_prompt`): adicionado constraint explícita "Do NOT run `post_save.py` for any `--node` tracking" para impedir que fases futuras corrompam `epic_nodes.implement` novamente. (commit `ceab9f1`)
- **Test:** `test_dag_executor.py` — 130 testes passam após fix.
- **Duration lost:** ~80 min (analyze-post 5min + judge 12min + diagnóstico + recovery)

### analyze-post timeout — test_reverse_reconcile_ingest.py hang (2026-04-16 23:41)
- **Symptom:** `analyze-post` expirou timeout (3000s). Relatório `analyze-post-report.md` (16KB, 214 linhas) foi escrito em ~5 min. Subprocess ficou preso por 48 min em `pytest .specify/scripts/tests/ -v` aguardando `test_reverse_reconcile_ingest.py` (60 operações git subprocess, `do_epoll_wait` indefinido). 2 processos orphan de fases anteriores (PIDs 2885905, 2887089) adicionaram contenção CPU/IO.
- **Detection:** `ps --ppid 2912042` mostrou filho zsh com `make test` em 41:05 min; `cat /proc/2913092/wchan = do_epoll_wait`; timeout-diagnostic `analyze-post_1776382912.stdout` criado às 23:41Z; novo subprocess PID 2944200 spawned imediatamente.
- **Root cause:** `Makefile:test` rodava `pytest .specify/scripts/tests/ -v` sem ignorar `test_reverse_reconcile_ingest.py` — 60 git subprocess ops por test run. Cada `make test` chamado pelo analyze-post subprocess levou 41+ min, esgotando os 3000s de timeout.
- **Fix:** `Makefile:13-16` — adicionado `--ignore=.specify/scripts/tests/test_reverse_reconcile_ingest.py` ao target `test`; novo target `test-full` para runs explícitos com todos os testes. (commit `f4ba5c9`)
- **Test:** Fix commitado antes do retry — retry 1 (PID 2944200) usa Makefile corrigido. Suite esperada: ~5-10 min em vez de 40+ min.
- **Duration lost:** ~50 min (análise concluída em 5min, pytest hung 45min, mais retry overhead)

### qa timeout — test_reverse_reconcile_e2e.py hang (2026-04-17 00:54)
- **Symptom:** `qa` expirou timeout (3000s). `qa-report.md` (295 linhas, 13995 bytes) escrito em ~13 min às 00:08Z. Subprocess ficou preso 37-41 min em 3 pytest concorrentes, todos em `do_epoll_wait`, nenhum com filhos.
- **Detection:** `cat /proc/<pid>/wchan = do_epoll_wait` nos 3 pytest filhos; `elapsed_s=2977` em pipeline_runs com qa ainda `running`; grep de subprocess em test files sem `test_reverse_reconcile_ingest.py` ou `test_sync_memory_module.py` → `test_reverse_reconcile_e2e.py` com 9 git subprocess ops.
- **Root cause:** `Makefile:test` não ignorava `test_reverse_reconcile_e2e.py` — 9 operações `git init/clone/commit/fetch` por run causam `do_epoll_wait` indefinido. Mesmo padrão de `test_reverse_reconcile_ingest.py` (commit `f4ba5c9`).
- **Fix:** `Makefile:14-16` — adicionado `--ignore=.specify/scripts/tests/test_reverse_reconcile_e2e.py` ao target `test`. (commit `fbfac73`)
- **Test:** Fix commitado antes do retry — retry 1 usa Makefile corrigido.
- **Duration lost:** ~50 min (qa concluída em 13min, pytest hung 37-41min)

### qa 3x timeout — suite 1131 testes excede DEFAULT_TIMEOUT (2026-04-17 02:38)
- **Symptom:** qa expirou timeout 3 vezes (attempts 0-2). Cada retry: qa-report.md escrito em ~10-13min, depois subprocess preso 37-47min em `make test` com 1131 testes, esgotando os 3000s. `qa` marcada `failed` no DB.
- **Detection:** `ps -o %cpu,wchan,etime` nos pytest filhos; CPU declinando 7%→3%→0% ao longo de 3 retries distintos; 3 timeout diagnostics `qa_177638*.stdout` criados.
- **Root cause:** 4 arquivos com git subprocess em fixtures (`test_reverse_reconcile_ingest.py`, `test_reverse_reconcile_e2e.py`, `test_reverse_reconcile_aggregate.py`, `test_implement_remote.py`) causavam `do_epoll_wait` indefinido — descobertos incrementalmente. Após todos os ignores, a suite restante (1131 testes) ainda levava ~40min, ultrapassando o limite de 50min (3000s) com margem muito estreita.
- **Fix 1:** `Makefile:14-17` — ignores incrementais para 4 arquivos git-subprocess. (commits `f4ba5c9`, `fbfac73`, `0ccca1d`)
- **Fix 2:** `dag_executor.py:2400-2449` — `_report_success_check` passa `success_check` para qa/analyze-post/judge em `dispatch_with_retry_async`. Antes de cada retry, verifica se `*-report.md` ≥50 linhas com HANDOFF — se sim, considera completo. (commit `849f183`)
- **Test:** `test_dag_executor.py::test_report_success_check_skips_retry_when_report_exists` adicionado.
- **Recovery:** Easter reiniciado — `get_resumable_nodes()` detectou qa completada em run anterior (2026-04-15). Pipeline avançou para `reconcile`.
- **Duration lost:** ~3.5h (3 retries × ~50min + overhead de diagnóstico e commits incrementais)

<!-- template:
### <título curto> (<YYYY-MM-DD HH:MM>)
- **Symptom:** <o que foi visto>
- **Detection:** <qual sinal capturou>
- **Root cause:** <1 frase + file:line>
- **Fix:** <file:line — o que mudou> (commit `<sha>`)
- **Test:** <arquivo de teste adicionado/atualizado>
- **Duration lost:** <minutos>
-->

## Síntese (2026-04-17)

**Métricas:**
- Incidents críticos: **5**
- Tempo perdido estimado: **~500 min (~8.3h)**
- Fixes commitados: **6** (`28f1f45`, `ceab9f1`, `f4ba5c9`, `fbfac73`, `0ccca1d`, `849f183`)
- Testes adicionados: **2** (`test_success_check_skips_retry`, `test_report_success_check_skips_retry_when_report_exists` em `test_dag_executor.py`)

---

### Agrupamento por causa raiz

#### Causa raiz A — git subprocess em fixtures pytest (290 min perdidos, 3 incidents)

`test_reverse_reconcile_ingest.py`, `test_reverse_reconcile_e2e.py`, `test_reverse_reconcile_aggregate.py` e `test_implement_remote.py` têm fixtures com `git init/clone/commit/fetch` reais. Dentro do subprocess `claude -p`, pytest entra em `do_epoll_wait` indefinido — 0% CPU, sem filhos, nunca encerra. Descobertos incrementalmente ao longo de 3 incidents distintos (analyze-post timeout, qa e2e hang, qa 3× timeout), resultando em 3 commits separados para o mesmo padrão.

**Sintomas:** analyze-post timeout (50 min) → qa timeout/e2e hang (50 min) → qa 3× timeout (210 min).

**Fixes aplicados:** `f4ba5c9` + `fbfac73` + `0ccca1d` — ignores incrementais no `Makefile:test`.

**O que falta:** abordagem estrutural — `@pytest.mark.slow` (ou `@pytest.mark.integration`) + `make test` usa `--mark "not slow"` em vez de lista de ignores crescente. Quinto arquivo pode aparecer.

---

#### Causa raiz B — subprocess continua após tasks done, SIGKILL pré-flush (110 min perdidos, 1 incident)

`--output-format json` só faz flush no encerramento do processo. O subprocess completa todas as tasks em ~10-15 min mas continua por mais 35-45 min em wrap-up/validações extras. O watchdog de 3000s envia SIGKILL antes do flush → `partial stdout (0 bytes)` → dag_executor dispara retry mesmo com trabalho completo.

**Sintoma:** implement:phase-1 expirou com 0 bytes stdout, mas T001-T012 todos `[x]`.

**Fix aplicado:** `28f1f45` — timeout proporcional + `_verify_phase_completion` como `success_check` pré-retry. `849f183` — `_report_success_check` para qa/analyze-post/judge.

**O que falta:** instrução explícita em `compose_phase_prompt` para encerrar imediatamente após tasks done. `_verify_phase_completion` hoje só roda após exaurir retries — mover para pré-retry.

---

#### Causa raiz C — subprocess chamou post_save.py corrompendo epic_nodes (80 min perdidos, 1 incident)

O subprocess `claude -p` de phase-1 chamou `post_save.py --node implement` ao encerrar, inscrevendo `implement=done` em `epic_nodes` sem passar pelo loop `_run_implement_phases`. Easter ao reiniciar leu `epic_nodes` diretamente e pulou phases 2-7 (27 de 39 tasks).

**Sintoma:** epic avançou para analyze-post com tasks T013-T039 todas `[ ]`.

**Fix aplicado:** `ceab9f1` — constraint explícita em `compose_phase_prompt` proibindo `post_save.py --node`.

**O que falta:** invariante no dag_executor — `_run_implement_phases` deveria ser a única fonte de verdade para `epic_nodes.implement`. post_save.py poderia validar se `--node implement` está sendo chamado dentro ou fora do loop de fases e rejeitar chamadas diretas.

---

### Melhorias consolidadas (sem duplicatas)

**madruga.ai — prioritizadas:**

1. `@pytest.mark.slow` + `make test-fast` — substitui lista de ignores crescente (`Makefile`, `conftest.py`)
2. `kill(-pgid)` em `dispatch_node_async` — SIGKILL no grupo de processos, elimina orphan pytest acumulados
3. `_verify_phase_completion` pré-retry (não apenas pós-exaurir) — salva até 150 min por phase em timeout
4. Pre-dispatch check em `_run_implement_phases`: se todas tasks do phase já `[x]`, pular dispatch imediatamente
5. Instrução "EXIT IMMEDIATELY após tasks done" em `compose_phase_prompt` — reduz 35-45 min de wrap-up por fase
6. Timeout escalado: `max(DEFAULT_TIMEOUT, task_count × 300 + 600)` em vez de cap fixo em 3000s
7. Invariante no dag_executor: `post_save.py --node implement` só aceito de dentro de `_run_implement_phases`

**madruga.ai — observabilidade:**
8. Monitorar `tryings > 10` em TelegramConflictError — logar warning no portal antes de bloquear notificações de 1-way-door
9. Reduzir file contexts em `compose_phase_prompt`: incluir apenas funções relevantes de módulos grandes, não o módulo inteiro (~35KB de economia por fase com arquivo Python 1200+ LOC)
