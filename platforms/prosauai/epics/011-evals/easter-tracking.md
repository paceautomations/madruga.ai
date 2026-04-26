# Easter Tracking — prosauai 011-evals

Started: 2026-04-24T17:52:00Z

## Melhoria — madruga.ai

- **Phase-1 → Phase-2: ADRs sumiram do prompt (−29KB).** Phase-1 incluía `ADR-008 + ADR-027 + ADR-028` (via `file:` prefix = scan semântico de tasks mencionando a ADR). Phase-2 não cita essas ADRs em `tasks.md` → 0 ADRs no prompt. **Confirma que a inclusão é task-scoped (heurística mention-scan sobre tasks da phase)**, não dependência estática. Bom design. O que NÃO melhora: `plan.md` (45KB) e `data_model.md` (20KB) entram em 100% das phases — **a oportunidade persistente é esse bloco de 65KB**.
- **Phase-1 (T001-T009) foi no-op genuíno** — 10.3min, 0 commits. Verificado via `git log` no worktree da prosauai: primeiro commit é T018 (Phase-2). Phase-2 SIM commitou (T010-T020 todas). Phase-3 já iniciou commits em 7min (T021+T022). **Candidato a corte:** tasks Setup de "verify deps / review structure / check infra-pré-existente" custaram ~10min de claude sem gerar diff — ideal é `speckit.tasks` detectar tasks no-op via ausência de verbos `create/add/implement/write` e consolidar ou remover.
- **Log `"No changes to commit for prosauai/011-evals"` é enganoso** (log 17:59:31 e 18:23:29). Aparece depois de CADA phase completar, inclusive quando tasks commitaram individualmente (T018-T020 estão no git log apesar desse log "no changes"). Significa apenas "o commit de phase-level não encontrou diff pendente" — tasks já commitaram via hook individual. **Fix sugerido (`dag_executor.py`):** trocar a mensagem para `"Phase commit skipped — all tasks already self-committed"` ou silenciar quando `git diff --cached` estava vazio desde o início. Mensagem atual gerou falso alarme aqui.
- **Phase-3 prompt = 148.5KB** (phase-1: 121KB, phase-2: 99.5KB). Explosão vem da inclusão de `spec.md` (46.6KB) — user stories exigem spec. Agora plan+spec somam 92KB = 62% do prompt. Esta é a **menor janela útil de cache prefix**: plan (45,580 bytes, fixo em TODAS 11 phases) pode ser o único bloco consistentemente cacheable. Spec só aparece em US phases — não vale cachear. `compose_task_prompt` deveria reordenar: `plan` primeiro (prefixo cacheable estável), depois `spec/data_model/contracts` (variáveis por phase), depois `tasks/header/analyze_report` (variáveis por phase). Se `MADRUGA_CACHE_ORDERED=1` já faz isso, confirmar no log next tick.
- **Contracts NÃO são task-scoped** (ao contrário de ADRs) — `contract:evaluator-persist.md` (10,860 bytes) + `contract:README.md` (2,355 bytes) aparecem em phases 2, 3, 4 mesmo quando a phase é sobre crons/setup (nada a ver com persister). Diferente de ADRs (que sumiram em phase-2 por não serem mencionadas), contracts entram sempre. **Custo:** 13KB extras em phase-4 que não usa persister. **Fix sugerido:** aplicar mesma heurística mention-scan de ADRs aos contracts — incluir apenas se tasks da phase mencionam `contract:` ou o nome do contract. Economia estimada: 10-15KB em ~50% das phases.
- **Prompt da `implement:phase-1` = 121KB** (threshold saudável: 80KB). Composição (log 17:49:09):
  - `plan.md` = 45,580 bytes (38% do prompt)
  - `data-model.md` = 20,085 bytes
  - `ADR-028-pipeline-fire-and-forget-persistence.md` = 14,694 bytes (incluída inteira)
  - `ADR-027-admin-tables-no-rls.md` = 12,364 bytes (incluída inteira)
  - `contract:evaluator-persist.md` = 10,860 bytes
  - `ADR-008-eval-stack.md` = 2,178 bytes
  - `tasks.md` (sliced) = 5,174 bytes (OK — slice funcionou: 45994→5143)
  - Restante (contract README, analyze_report, header, .env.example, pyproject.toml, cue): ~14KB
- **Consequência:** este mesmo bloco `plan + data_model + 3 ADRs` (≈94KB de "contexto estável") será repetido em **todas as 11 phases** do epic. Candidato direto a cache-optimal prefix — mover seções estáveis para o TOPO do user prompt para bater no 1h-TTL cache do Claude (já implementado via `MADRUGA_CACHE_ORDERED=1`, mas precisa verificar se o bloco de 94KB está de fato no prefixo estável).
- **Hipótese a validar:** ADRs inteiras estão sendo injetadas por `_DOC_CANDIDATE_RULES` ou path heuristic? Se 3 ADRs somam 29KB e só 1 delas (ADR-008 eval-stack) é topicamente relevante ao epic de evals, ADR-027 e ADR-028 podem estar entrando por mention-scan em vez de relevância semântica. Investigar `dag_executor.compose_task_prompt` → seção de inclusão de ADRs.
- **Slicing funcionando bem:** `phase_tasks_sliced 45994→5143` (tasks.md cortada pra phase 1), `phase_spec_skipped` (spec não incluída na phase 1). Estratégia de scope está ativa.
- **(2026-04-25 tick) Watchdog acoplado ao Telegram polling.** O service morreu hoje 10:50 com `Watchdog timeout (limit 2min)!` precedido por `TelegramNetworkError: HTTP Client says - Request timeout`. Ou seja: queda momentânea de rede no aiogram bloqueou o heartbeat do systemd e o processo foi morto pelo próprio service manager. **Fix sugerido (`easter.py`):** desacoplar o sdnotify/heartbeat do polling do Telegram — ou rodar o heartbeat num thread/asyncio task dedicada que não depende da resposta da API do Telegram. Atualmente uma queda de 60s no Telegram = restart total do daemon. Backup: aumentar `WatchdogSec` no service file de 2min para 5min (paliativo).
- **(2026-04-25 tick) Phase-5 prompt = 140.8KB** — confirma padrão de phase-3 (148KB) e phase-4. Composição: `cue=64 plan=45580 spec=46586 data_model=20085 contract:README=2355 contract:evaluator-persist=10860 analyze_report=7512 tasks=4649 header=3087`. ADRs corretamente fora (zero menção em tasks da Phase 5). Reforça oportunidade do prefix-cache + slicing de plan.md por phase.
- **(2026-04-25 tick) Cache 1h-TTL sobrevive APENAS dentro de um único `claude -p`** (across as 150 turns), NÃO entre dispatches de phase. Evidência: `tok_in` totaliza **78.7M** após 4 phases (phase-2: 24M, phase-3: 24M, phase-4: 13.5M). Se o prefix-cache funcionasse cross-phase, esperaríamos ~6-10M total, não 78M. Cada phase paga writes do prefix de 65-100KB do zero. **Lever de alto impacto:** (a) phase-scoped pre-slicing de `plan.md` e `data_model.md` (gerar `plan-phase5.md` extraindo só seções relevantes — heurística por header match com tasks da phase), OU (b) explorar reuso de session via `--continue` (incompatível com `--no-session-persistence` atual — ADR-021 trade-off). Custo atual: $57.25 nas 4 phases concluídas, projeção $130-150 ao final do epic.
  - **CORREÇÃO (tick 2026-04-25 11:21):** o easter loga `claude_cache_metrics` ao final de cada phase. Phase-6: `cache_read=10.77M cache_create=161KB tokens_in=10.93M hit_rate=0.99` — **99% de hit rate DENTRO da phase**. Quer dizer que dos 10.93M `tokens_in` reportados, **só ~161KB foi cache_create** (write inicial) e o resto (~99%) foi cache_read (lido do prefix cache, custo ~10% do preço normal). Os 78.7M acumulados que eu citei NÃO refletem custo real — refletem total de tokens processados (incluindo cache reads). Custo real reflete só os cache_creates + per-turn deltas + outputs. **Conclusão revista:** cache prefix DENTRO da phase está funcionando MUITO bem (99%); meu argumento original sobre cross-phase ainda vale (cada phase paga seu próprio cache_create de ~150-200KB), mas o impacto financeiro é MUITO menor do que eu estimei. Custo real total parece estar na faixa de $57 agreed, não $130-150 projetado. Reduce-prompt levers continuam válidos (menos cache_create = menos custo + faster TTFT) mas a urgência cai. **TODO próximo tick:** loggar o ratio cache_create/cache_read por phase para confirmar.
- **(2026-04-25 tick) Log "Phase dispatch: 11 phases, 105 total pending tasks"** mas `tasks.md` lista apenas Phase 1-10. Off-by-one no `dag_executor` quando conta phases? Possível causa: parse capturando alguma linha que matcha `^## Phase` falsamente, ou contador inicializa em 1 e termina em 11 inclusive. Investigar `phase_dispatch` parse loop.
  - **CORREÇÃO (tick 12:34):** Não é off-by-one — é o `MADRUGA_PHASE_MAX_TASKS=12` dividindo phases que excedem o cap. Phase 9 (Polish, 18 tasks T082-T099) foi split em part 1 (T082-T093, 12 tasks) + part 2 (T094-T099, 6 tasks). Total: 10 phases originais + 1 split = **11 sub-phases**. Funcional, mas o **node_id no DB fica enganoso**: `implement:phase-9` = part 1, `implement:phase-10` = part 2 do phase 9 (NÃO o phase 10 original). E quando o phase 10 real (Deployment Smoke) dispatchar, vai virar `implement:phase-11` no DB. **Fix sugerido (`dag_executor.py` phase dispatcher):** preservar o número original com sufixo de parte — ex. `implement:phase-9.1` e `implement:phase-9.2`, mantendo `implement:phase-10` para o Deployment Smoke real. Auditoria de runs por phase do tasks.md fica direta. Hoje: confusão garantida em qualquer query de cost/duration por phase.
- **(2026-04-25 tick) Same-error CB precisa classificar infra vs LLM.** Phase-5 já falhou 2x antes do dispatch atual: ontem 19:09 (zombie no daemon crash) + hoje 10:50 (watchdog timeout). Ambas são falhas de **infraestrutura do orchestrator**, não do conteúdo da task — o claude nem chegou a rodar. O `dispatch_with_retry_async` registrou ambas como falhas seguidas e o CB foi **seeded com 1 prior failure** no resume atual. Se este dispatch falhar por qualquer motivo (mesmo content-related), CB OPEN dispara prematuramente. **Fix sugerido (`dag_executor.py`):** tag `error_class` no `pipeline_runs.error` (`infra` para zombie/watchdog/CB-OPEN, `task` para exit code do claude, `transient` para rate limit). CB conta apenas `task` failures. Atualmente trata tudo igual.

## Melhoria — prosauai

- **Phase-3 entregando em ritmo saudável** — T021 (EvalPersister Protocol contract tests) e T022 (PoolPersister + EvalPersister Protocol) commitados nos primeiros 7min. Commit messages bem formatadas (`feat(011): TNNN <descrição>`). Untracked: `apps/api/prosauai/evals/heuristic_online.py` (sem T-ref — provável trabalho em progresso de task atual).
- **Phase-2 também entregou**: T018 (validate tenants.yaml evals:* block), T019 (default evals: block for Ariel+ResenhAI mode=off), T020 (wire EvalsScheduler into FastAPI lifespan) — foundational cumpriu o papel.
- **Task consolidation pattern observado (boa prática)** — T026 (OTel span em `PoolPersister.persist`) foi implementada inline com T022 (implementação do `PoolPersister`). Em vez de 2 commits, claude consolidou num commit T022 e deixou T026 marcada `[x]` na tasks.md com nota auto-documentada explicando a consolidação (linhas 151-154 de `persist.py`, atributos do span, exception handling). **Por que é bom:** evita commit fragmentado quando dependência natural existe; preserva rastreabilidade porque a nota aponta file:line exato. **Recomendação (madruga.ai):** capturar esse padrão no `speckit.implement` como heurística formal — "se task N+k tem touchpoint exclusivo no arquivo já tocado por task N e o escopo é <3 linhas, consolidar e documentar inline".
- **(2026-04-25 tick) Phase-4 (Cron Autonomous Resolution) entregou completa** — 35 commits desde T006 até T046. Phase-3 commitou T021-T031 (PoolPersister + tests + heuristic_online + p95 benchmark). Phase-4 commitou T032-T039 (autonomous_resolution cron + AdvisoryLockGuard + EvalsScheduler tests). Phase-5 já em curso: T040-T046 commitados (deepeval>=3.0 dep, BifrostDeepEvalModel adapter, batch wrappers/sampler/runner/spans, deepeval_batch_cron registrado em main.py:lifespan). Untracked atual: `apps/api/tests/unit/evals/test_deepeval_model.py` + `apps/api/tests/fixtures/deepeval_mock_responses.json` — provável task T047 (testes do model adapter) em andamento agora.
- **(2026-04-25 tick) Cobertura de testes está consistente** — phase-3 entregou 4 commits dedicados a testes (T027-T031: 18 PoolPersister cases + 13 heuristic_online + persist hook + e2e + benchmark p95). Phase-4 entregou 4 commits de teste (T035 + T036+T039 + T037+T038). Padrão saudável: cada cluster de implementação seguido por 1-2 commits de teste. **Sem cobertura visível ainda:** commits T032-T034 (autonomous_resolution cron) commitaram juntos sem testes próprios — testes vieram em T035 (1 commit depois). Aceitável dado que T035 é dedicado a "unit tests for autonomous_resolution cron". Conclusão: prosauai está respeitando TDD-light bem, sem cantos.
- **(2026-04-25 11:21 tick) Phase-5 e Phase-6 ambas concluídas em 14min cada** — Phase-5 (US3 DeepEval Batch, 5 tasks T047-T051) completou em 840s. Phase-6 (US4 Promptfoo CI Smoke Suite, 6 tasks T052-T057) completou em 795s — log explícito `Phase 'Phase 6...' completed: 6/6 tasks done`. Phase-7 (US5 Golden Curation, 12 tasks T058-T069) dispatchou agora 11:21:27 com `max_turns=290 timeout=4200s` — phase mais ambiciosa do epic (12 tasks vs média 5-6). Vai tomar até 70min se chegar no timeout.
- **(2026-04-25 11:21 tick) Telegram transient survived sem watchdog kill** — log `telegram_recovered after_failures=1` às 11:13:28 indica que houve outra falha do Telegram polling, mas desta vez o easter sobreviveu (não morreu por watchdog). Significa que o restart às 10:53 trouxe alguma resiliência adicional, OU foi sorte (a falha demorou < 2min para recuperar). Comparando com 10:50 onde falha durou ~5s antes do watchdog matar: o threshold de morte é estreito. Reforça a recomendação de desacoplar heartbeat do polling.
- **(2026-04-25 12:09 tick) Novo modo de falha do Telegram: `TelegramConflictError`.** Diferente do `TelegramNetworkError` (timeout de rede, fatal pro watchdog). Aqui a mensagem é `"Conflict: terminated by other getUpdates request; make sure that only one bot instance is running"`, em loop com backoff exponencial (1s→1.36s→1.65s→1.98s→2.69s→3.39s...). Investigado: NÃO há outra instância local rodando (só PID 865787). Causa é **session stale do lado do Telegram** — o restart de 10:53 deixou uma sessão de polling cached na cloud, e agora as 2 (a velha cached + a nossa atual) competem. Resolve sozinho quando a sessão velha expira (~5-15min). **Por que importa:** (a) o backoff exponencial protege o watchdog (sleeps são curtos, heartbeat continua), diferente do NetworkError; (b) ainda é poluição de log e desperdiça CPU; (c) fix real seria chamar `bot.delete_webhook(drop_pending_updates=True)` no startup do easter para invalidar a sessão antiga deterministicamente. Fix sugerido em `easter.py` lifespan handler.
- **(2026-04-25 12:09 tick) Memory growth do uvicorn:** 474MB no startup às 10:53 → **1.3GB às 12:09** (1h16min). ~826MB de crescimento. Não é por subprocess — claude tem PID separado (937484, 0.9% MEM = ~250MB). É no próprio uvicorn/easter. Possíveis causas: (a) histórico de eventos acumulando em memória (DAG executor mantém logs em RAM por epic), (b) connections SSE/WebSocket não fechando, (c) leak no aiogram (cache de sessões). **Não é blocker** mas tendência preocupante — em epic longo (~2-3 dias de runtime) o uvicorn vai estourar facilmente RAM. Fix sugerido: adicionar `tracemalloc.start()` no startup + endpoint debug `/admin/memprof` que retorna top-N alocações. Daria visibilidade barata.
- **(2026-04-25 13:20 tick) Autonomous mode bypassa `auto-escalate` gates silenciosamente.** Evidência: judge do epic 011 reportou `score: 50, verdict: fail` (BLOCKERs 2/2 fixed ✓, mas 5 WARNINGs e 28 NITs OPEN), abaixo do threshold 80. Pipeline continuou direto para `qa` sem qualquer pausa, prompt ao usuário via Telegram, ou notificação. O **autonomous dispatch prompt** (em `dag_executor._dispatch_env`) instrui claude `Treat ALL gates as auto` — o que é correto durante a execução de uma skill individual, MAS o **dispatcher do dag_executor** também está pulando o checkpoint de auto-escalate (deveria notificar mesmo se autoseguir). Trade-off real: ou (a) autonomous bypassa silenciosamente (situação atual — bug invisível) ou (b) autonomous notifica e segue (visibilidade sem bloquear) ou (c) autonomous pausa em escalates (perde a vantagem do modo autônomo). **Fix sugerido (mínimo):** quando `judge.verdict==fail` em autonomous mode, enviar Telegram message não-bloqueante via `notify_judge_fail(score, blockers, warnings)` ANTES de dispatchar o próximo nó. Mantém autonomia, ganha visibilidade. As 5 WARNINGs do epic 011 podem ter ficado por aí sem o usuário saber até reconcile/roadmap.
- **(2026-04-25 12:09 tick) Commit órfão entre phase-7 e phase-8: `5562aec feat: epic 011-evals — implement tasks`.** Mensagem genérica (sem T-ref), aparece no `git log` da prosauai entre os commits de phase-7 (terminando em `0e0a815 T046`) e os de phase-8 (`ecf77ae T070`). Provável fonte: o `dag_executor` faz um phase-level `git commit` no fim de cada phase para capturar mudanças não-commitadas pelo claude. Quando claude já commitou tudo individualmente, o commit do dag fica vazio E a mensagem genérica continua no log. **Fix sugerido:** verificar `git diff --cached` antes do phase commit; pular se vazio. Já é o comportamento atual mas a mensagem `"epic 011-evals — implement tasks"` sugere que o commit não foi pulado dessa vez (pode ter pegado um arquivo modificado pelo hook PostToolUse — ex: `tasks.md` com `[X]` updates do final da phase). Investigar `dag_executor.py` no handler de phase completion.
- **(2026-04-25 12:22 tick) Phase com `cost_usd=$0.00` apesar de duration > 0 — bug reincidente.** Já 2 ocorrências:
  - **phase-8** (DB): 2131s, $0.00 ❌ — phase pesada (frontend+API)
  - **phase-11** (DB) = Deploy Smoke real: 1101s, $0.00 ❌ — phase smoke (sem commits)

  Demais phases reportam corretamente: phase-5=$10.36, phase-6=$7.57, phase-7=$13.77, phase-9=$10.67, phase-10=$2.23 (estes 2 últimos são as partes de Phase 9 split).

  **Hipótese refinada após 2ª ocorrência:** não é só max_turns hit (phase-11 só tinha 6 tasks, max_turns=170, irrelevante). Os 2 casos com $0 não compartilham max_turns nem duration nem natureza. Nova hipótese: o `dag_executor` parsa o ÚLTIMO `claude_cache_metrics` line do stdout, mas se claude emite o JSON final com algum delimiter/format alternativo (ex: pretty-print ao invés de oneline) o regex do parser falha silenciosamente. Outra possibilidade: claude às vezes emite a metric ANTES das últimas turns (ex: depois de uma tool call grande) e o parser pega esse intermediário, não o final. **Fix sugerido:** (a) logar warning quando `cost_usd=0 AND duration_ms>0` (visibilidade); (b) usar JSON robust parser (ler último JSON object com `usage` field) ao invés de regex line-match. **Custo real subnotificado** estimado em $15-25 (phase-8 = 35min de claude work não é grátis). Reconciliação manual via API logs precisaria pra fechar a conta.

## Incidents críticos

### Phase-5 zombie no primeiro dispatch (2026-04-24 19:09) — auto-recovered
- **Symptom:** `pipeline_runs` com `node_id=implement:phase-5 status=failed duration_ms=0 error="zombie — daemon restart or crash"`. Token counters zerados.
- **Detection:** Watermark da row é depois de phase-4 completar 18:53. O dispatch foi feito mas o processo subjacente do claude não chegou a registrar conclusão antes do daemon morrer (provável OOM ou crash sem dump no journal local — gap de 15h entre 19:09 e o restart das 10:53 não tem logs visíveis no `journalctl --since "10 min ago"`).
- **Root cause:** Não confirmada — pode ser (a) crash do `easter` por NTB hibernando/suspending, (b) OOM no claude subprocess, (c) outro motivo. Sem core dump preservado.
- **Fix:** Não houve fix de código — o auto-resume do `dag_executor` ao restart corretamente skipou os 6 nodes completados (`epic-context, specify, clarify, plan, tasks, analyze`) + 4 phases (1-4) e re-dispatchou phase-5 do zero. Falha original ficou registrada com `error="zombie — daemon restart or crash"` graças ao detector de zombies.
- **Test:** N/A
- **Duration lost:** ~15h13min wall-clock (19:09 → 10:50 — mas o NTB pode ter ficado offline parte desse tempo, então custo real é mais baixo). Token cost: $0 (zerado).

### Watchdog timeout no segundo dispatch (2026-04-25 10:50) — auto-recovered
- **Symptom:** `madruga-easter.service: Watchdog timeout (limit 2min)!` no journal logo após `TelegramNetworkError: HTTP Client says - Request timeout error`. Service foi killed pelo systemd e auto-restart subiu nova instância às 10:53:43.
- **Detection:** `journalctl --user -u madruga-easter` mostra a sequência: `health_check_failed (fail_count=1)` 10:50:33 → `TelegramNetworkError ... Request timeout` 10:50:38 → `Watchdog timeout (limit 2min)!` → restart 10:53:43 com `Resume async: 6 nodes already completed` + `Circuit breaker seeded with 1 prior failures` (a falha de 19:09).
- **Root cause:** **`easter.py` está acoplando o heartbeat (sdnotify) ao loop principal que também faz polling do Telegram**. Quando a API do Telegram trava por mais de 2min (rede WSL2 + Telegram cloud), o heartbeat não é enviado e o systemd mata o service. (file:line a confirmar — provavelmente `easter.py` startup_complete handler ou similar; não verifiquei o source ainda).
- **Fix:** Não aplicado nesta sessão (não é blocker — auto-resume cobriu). **Recomendação:** task de follow-up registrada em "Melhoria — madruga.ai" → desacoplar heartbeat do Telegram.
- **Test:** N/A — fix ainda não foi escrito.
- **Duration lost:** ~3min (10:50:33 → 10:53:43). Token cost: $0.

## Timeline (desde o início do epic)

| When (UTC) | Event | Status | Duration | $ |
|---|---|---|---|---|
| 2026-04-24 13:39 | Epic 011-evals criado (`drafted`) | — | — | — |
| 2026-04-24 16:50 | `specify` cancelado (1ª tentativa) | cancelled | 0 | $0 |
| 2026-04-24 16:55 | `specify` ✓ | completed | 7.0min | $1.64 |
| 2026-04-24 17:02 | `clarify` ✓ | completed | 5.5min | $2.11 |
| 2026-04-24 17:08 | `plan` ✓ (412 linhas) | completed | 16.6min | $4.54 |
| 2026-04-24 17:25 | `tasks` ✓ (514 linhas, 10 phases) | completed | 7.4min | $2.80 |
| 2026-04-24 17:32 | `analyze` ✓ | completed | 16.4min | $0.69 |
| 2026-04-24 17:49 | `implement:phase-1` (Setup) ✓ — no-op genuíno (0 commits) | completed | 10.3min | $5.09 |
| 2026-04-24 17:59 | `implement:phase-2` (Foundational T010-T020) ✓ | completed | 23.9min | $15.11 |
| 2026-04-24 18:23 | `implement:phase-3` (US1 Heuristic Online T021-T031) ✓ | completed | 29.7min | $15.64 |
| 2026-04-24 18:53 | `implement:phase-4` (US2 Cron Autonomous T032-T039) ✓ | completed | 15.7min | $9.62 |
| 2026-04-24 19:09 | `implement:phase-5` zombie/crash do daemon | **failed** | — | $0 |
| 2026-04-25 10:50 | watchdog timeout (Telegram net), service killed | restart | — | $0 |
| 2026-04-25 10:53 | `implement:phase-5` (US3 DeepEval T047-T051) re-dispatched | completed | 14.0min | (cache 99% hit) |
| 2026-04-25 11:08 | `implement:phase-6` (US4 Promptfoo CI Smoke T052-T057) ✓ — 6/6 done | completed | 13.25min | $TBD |
| 2026-04-25 11:21 | `implement:phase-7` (US5 Golden Curation T058-T069) dispatched (12 tasks, 70min timeout) | **running** | (~3min até agora) | em andamento |

**Acumulado até agora:** 9 nodes ✓ + 1 running. Duration completa: ~2h13min wall-clock de claude. Tokens IN total: 78.7M. Custo: **$57.25** (todos os runs `completed`, infra failures não cobraram).

**Phases pendentes após esta:** Phase 6 (US4 Promptfoo CI), Phase 7 (US5 Golden Curation), Phase 8 (US6 Performance AI Tab + Admin), Phase 9 (Polish), Phase 10 (Deployment Smoke). Mais 5 phases. Projeção de custo: **$130-160 total ao final do epic** (se cada US-phase custar ~$15 e Polish/Deploy forem mais leves).

## Síntese (2026-04-25)

**Epic shipped:** 011-evals (`status=shipped, delivered_at=2026-04-25`).

### Métricas

| Métrica | Valor |
|---|---|
| Wall-clock claude (excl. overnight gap) | ~4h00min |
| Wall-clock total (incl. zombie 19:09→10:53) | ~22h |
| Phases L2 dispatchadas | 11 (10 originais + Phase 9 split em part1+part2) |
| Tasks implementadas | 99 (T001–T099) |
| Commits prosauai | 35+ no padrão `feat(011): TNNN ...` |
| **Custo somado (DB)** | **$93.98** |
| Custo real (estimado, c/ phases $0) | $110-120 (phase-8 e phase-11 ficaram $0 por bug) |
| Incidents críticos | 2 (todos auto-recovered, sem intervenção do pair-program) |
| Tempo perdido real | ~3min (watchdog 10:50). O zombie 19:09 foi overnight (NTB provavelmente hibernando), não custo de trabalho perdido — resume cobriu. |
| Fixes commitados pelo pair-program | 0 (observador puro — nenhum classificado como `critical` que exigisse intervenção cirúrgica) |
| Testes adicionados pelo pair-program | 0 |
| Judge score | 50/100 (FAIL): 2 BLOCKERs ✓ fixed, 5 WARNINGs OPEN, 28 NITs OPEN |

### Incidents por causa raiz

**Causa única para ambos: heartbeat do easter acoplado ao polling do Telegram (`easter.py` lifespan / aiogram dispatcher).**

- 2026-04-24 19:09 — phase-5 zombie/crash do daemon (causa não confirmada; provável NTB hibernou + Telegram timeout em loop matou o watchdog).
- 2026-04-25 10:50 — `Watchdog timeout (limit 2min)!` precedido por `TelegramNetworkError`. Service killed.

Ambos cobertos por auto-resume — 0 trabalho de claude perdido. **Único fix concreto que resolveria os dois:** desacoplar sdnotify do polling, ou subir `WatchdogSec` de 2min → 5min como paliativo.

### Melhorias mais acionáveis para madruga.ai (top 5 por impacto/custo)

1. **Watchdog ↔ Telegram desacoplamento** (`easter.py`) — fix raiz dos 2 incidents.
2. **Cost $0 bug no DB** (`dag_executor` JSON parser) — 2 ocorrências confirmadas (phase-8 + phase-11). Custo real subnotificado em ~$15-25 só neste epic.
3. **Autonomous bypass silencioso de auto-escalate** — judge score=50 (FAIL) passou direto pra qa sem notify. Mínimo: Telegram message não-bloqueante.
4. **Phase split node naming bug** (`implement:phase-10` no DB = phase-9 part 2, não phase 10 real). Renomear para `phase-9.1` e `phase-9.2` preservando tasks.md original.
5. **TelegramConflictError exponential storm** — `bot.delete_webhook(drop_pending_updates=True)` no startup invalidaria sessions cacheadas server-side.

### Melhorias para prosauai (curto)

- Pontos positivos: cobertura de testes consistente (TDD-light bem aplicado), commits no padrão `feat(011): TNNN ...`, task consolidation natural quando dependência é exclusiva.
- Pendência: 5 WARNINGs do judge OPEN (ver `judge-report.md`). Reconcile já rodou — se não foram resolvidos lá, ficam para o próximo ciclo.

### Próximos passos (não-bloqueantes)

- `/ship` para commitar este `easter-tracking.md` quando o usuário avaliar.
- Revisar `judge-report.md` para decidir o destino das 5 WARNINGs OPEN.
- Considerar criar issues para os 5 fixes top do madruga.ai (desacoplar watchdog é o de maior impacto/baixo custo).
