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

<!-- bullets adicionados durante o epic -->

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

<!-- template:
### <título curto> (<YYYY-MM-DD HH:MM>)
- **Symptom:** <o que foi visto>
- **Detection:** <qual sinal capturou>
- **Root cause:** <1 frase + file:line>
- **Fix:** <file:line — o que mudou> (commit `<sha>`)
- **Test:** <arquivo de teste adicionado/atualizado>
- **Duration lost:** <minutos>
-->

## Síntese

<!-- preenchido no último tick -->
