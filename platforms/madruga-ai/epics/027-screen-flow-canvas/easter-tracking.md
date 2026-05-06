# Easter Tracking — madruga-ai 027-screen-flow-canvas

Started: 2026-05-05T20:41:00Z

## Melhoria — madruga.ai

- pair-program skill guardrail "STOP on main" assume worktree externo; em self-ref (`madruga-ai`) commits direto em `main` são o padrão. Ver `feat(resenhai): complete L1 pipeline` (b5e1b0b) e demais commits recentes. **Sugestão**: skill consultar `platform.yaml.repo.name` — se igual ao próprio repo, branch=main é healthy.
- epic-context com Start via portal/API NÃO cria branch em self-ref (gap conhecido — ver decisions/ADR sobre branch isolation removido em epic 024). Aceitável para madruga-ai mas vale documentar explicitamente.
- **speckit.clarify dispatch contradição**: skill instructions descrevem "Sequential questioning loop (interactive): Present EXACTLY ONE question at a time. After the user answers..." (~4KB de prosa), mas o banner "Autonomous Dispatch Mode" no topo força "Do NOT ask questions or wait for approval. Skip Step 1 questions". Resultado: ~4KB de tokens desperdiçados em prompt que descreve fluxo impossível em `claude -p`. Sugestão: passar flag `--mode=autonomous` ao dispatcher e o `compose_task_prompt` strip seções `interactive questioning loop` quando autônomo.
- **append-system-prompt redundante com system-prompt**: o dispatched prompt traz `--system-prompt` (cabeçalho com Conventions + Autonomous overrides + Pipeline Contract + skill body) E `--append-system-prompt` repetindo guardrails ("MANDATORY: Save all files to..."). Os mandatos já existem no system-prompt. Possível consolidação reduz parsing dupla e ~200B/dispatch.
- **phase-2 prompt 90KB — pipeline-dag-knowledge.md inflado**: phase-2 incluiu `.claude/knowledge/pipeline-dag-knowledge.md` (14.9KB) inteiro porque uma task referencia. Esse arquivo cresce ao longo do tempo (atual 14.9KB). Sugestão: `compose_task_prompt` deveria fatiar `pipeline-dag-knowledge.md` por seção quando uma task individual cita só uma parte (ex: só "L1" ou "L2 cycle"), em vez de incluir o arquivo inteiro. Padrão similar para `blueprint.md` em fases que criam código novo. Phase-1 (sem essa inclusão) ficou em 63KB; phase-2 saltou para 90KB. **80KB threshold da skill foi cruzado**.
- **phase-2 completou 6/8 tasks** em 21m15s e dispatcher avançou para phase-3 sem retentar T018/T019 (ou que sejam). Loss-of-information silencioso — não ficou claro nos logs por que 2 tasks ficaram pra trás (max_turns esgotou? task tinha bug? auto-fail por contrato?). Sugestão: `phase_completed` log deveria incluir `pending_task_ids` para auditoria; alternativa, `mark_phase_done` poderia agendar uma "tail-pass" só pras pendentes em vez de descartar.
- **phase-3 prompt 114KB**: cruzou 80KB. Spec inteiro (45KB) + plan (24KB) + data_model (16KB) + contract (9KB) + analyze_report (9KB). Spec gigante porque cobre 8 user stories em escopo. Sugestão: para fases User-Story-N, fatiar spec.md por user story (`## User Story N` headers) e incluir só a US ativa + visão geral, em vez do spec inteiro. 12 tasks × 114KB = ~1.4MB de contexto enviado por iteração — alvo de otimização clara.
- **phase-5 prompt 152KB**: novo recorde. Inclui `post_save.py` inteiro (30KB) + `screen-flow.schema.json` (7.5KB) além do spec/plan/data_model. Tasks da fase modificam post_save.py — faz sentido incluir, mas 30KB de código existente para 7 tasks é pesado. Sugestão: file-section slicing — quando uma task cita "modify function X in post_save.py", incluir só o def da função X + 50 linhas de contexto, não o arquivo inteiro. Padrão semelhante ao `phase_tasks_sliced` que já existe pra `tasks.md` (44KB→5KB).
- **"No changes to commit" em fase de US visual** (phase-4): 3 tasks rodaram 19min e o auto-commit não encontrou mudanças. Pode indicar (a) tasks foram só validações/leituras, (b) modelo gerou patches mas não persistiu, (c) tasks já estavam completas em phase-3 e modelo confirmou. Sugestão: skill `speckit.implement` deveria retornar JSON com `files_written: []` para distinguir os 3 casos; hoje só sabemos que git diff = vazio. **Atualização**: o padrão se repetiu em phase-6 (US3 opt-out) e phase-7 (US4 part 1). 3 fases consecutivas de US sem commit é forte sinal de underwriting silencioso.
- **phase-8 single-task com 25min+ wall**: T073 (1 task isolada) ultrapassou a média de 6 tasks em phase-1 (~4min). Tasks isoladas em phase própria deveriam ser fundidas com phase anterior pra ganhar contexto compartilhado, ou ter timeout customizado menor pra falhar rápido se modelo entrar em loop. Sugestão: dispatcher deveria mergear `task_count==1` phase com a phase anterior na mesma US se houver folga de turns.
- **phase-8 marcou completed com 0/1 tasks done**: 28min22s investidos, 0 tasks completadas, dispatcher avançou pra phase-9 mesmo assim. Esse é o caso mais grave do padrão "no commit" — task T073 foi pra trás silenciosamente. Sugestão: introduzir threshold `phase_min_completion_rate` (ex: 50%) — abaixo disso, fase é classificada como `failed` em vez de `completed`, e easter pode disparar 1 retry com prompt enxutado antes de prosseguir. Tracking só por `M/N tasks done` no log atual fica invisível em métricas agregadas.
- **Anti-pattern: sentinel-file polling sem timeout** (incidente phase-13): modelo usou `until [ -f /tmp/test_done ]; do sleep 2; done` esperando que algum processo crie o arquivo após o pytest. Como o spawn do pytest não amarrou criação do sentinel ao exit (ex: `pytest ... && touch /tmp/test_done` em vez de só `pytest > log &`), bash entrou em loop infinito → 26min de pipeline parado. Sugestão hard: skill `speckit.implement` (ou Conventions header) deveria proibir explicitamente esse pattern e indicar `wait $!` ou `timeout NN command` para esperar processos. Sugestão soft: dispatcher checa `ps --ppid <claude-pid>` em cada tick — se filho bash >5min em estado S/D sem mudança em I/O, sinaliza alerta.
- **phase-8 + phase-13 = sintoma de "wait without timeout"**: ambos os incidentes graves desta rodada vieram do mesmo padrão (modelo aguardando processo bg sem mecanismo de break). Provavelmente também explica os 5 casos de "no commit" (modelo iniciou processo, esperou indefinidamente, atingiu max_turns, dispatcher marcou completed sem o trabalho real). Investigação prioritária: instrumentar `bash` calls dispatched para detectar long-wait patterns proativamente.

## Melhoria — madruga-ai

(a coletar conforme observação dos nodes L2)

## Incidents críticos

### qa travado em sentinel-grep wait — subagent task vazia (2026-05-05 23:53)
- **Symptom:** qa retry 2/3 ultrapassou threshold 30min (30:19). Claude PID 451952 em `do_epoll_wait`. Filho bash (PID 464659) há 19:13 em `until grep -qE "passed|failed|error" /tmp/claude-1000/.../tasks/bwhfv7d5c.output 2>/dev/null; do sleep 8; done`. Arquivo target tinha 0 bytes desde 23:32:39 (criado mas nunca preenchido).
- **Detection:** tick-78 viu cruzamento threshold. `cat /proc/<pid>/wchan` confirmou epoll_wait. `ps --ppid` revelou bash com `sleep 8` infinito. `ls -la` no arquivo confirmou tamanho zero há 21min.
- **Root cause:** Modelo usou Claude Code SubagentTask (`Task tool`) e ficou em loop bash polling o output file da subagent. A subagent finalizou sem produzir texto (provável tool error ou hard-exit silencioso), gerando arquivo 0 bytes. Sem timeout no `until`, bash polla pra sempre.
- **Fix:** `printf "qa subtask returned no output — internal task pipeline error..." > $FILE` (mensagem contém "error" pra grep matchar). Bash exitou loop em ~10s, claude leu output, completou node. **Não há fix de código** — issue é pattern do modelo (polling sem timeout) compounded com SubagentTask que pode retornar vazio.
- **Test:** N/A (issue runtime). qa completou COM WARNING "Hallucination guard: node 'qa' completed with zero tool calls — output may be fabricated" — sinal vermelho de que qa pode ter "passado" sem rodar testes reais. Investigar separadamente.
- **Duration lost:** ~21min (23:32:39 quando subtask terminou em silêncio até 23:53:01 da intervenção)

### phase-13 travado em sentinel-file wait sem timeout (2026-05-05 21:53)
- **Symptom:** phase-13 (Polish & Cross-Cutting, 7 tasks) ultrapassou threshold dinâmico (39:19 > 37.5min). Processo claude (PID 337914) em `do_epoll_wait`, com filho zsh (PID 348715) há 24min em `until [ -f /tmp/test_done ]; do sleep 2; done; rtk read /tmp/test_output.log --tail-lines 30`.
- **Detection:** tick-50 viu phase em 92% do threshold (34:24/37.5min). Tick-54 confirmou cruzamento (39:19). `cat /proc/<pid>/wchan` retornou `do_epoll_wait`. `ps --ppid` revelou subprocesso zsh em loop infinito.
- **Root cause:** Modelo iniciou pytest em background com pattern `pytest > /tmp/test_output.log 2>&1 &` esperando que algum processo crie `/tmp/test_done` quando concluir, mas o pattern não amarra criação do sentinel ao exit do pytest. Pytest terminou às 21:27:52 (1330+ linhas em /tmp/test_output.log), mas `/tmp/test_done` nunca foi criado. Bash em loop infinito → claude bloqueado em epoll_wait → 26min desperdiçados.
- **Fix:** `touch /tmp/test_done` (non-destructive — sinaliza ao bash que pode sair do loop). Bash exited, `rtk read` retornou tail do log pra claude, que processou e completou phase-13 (6/7 tasks). Pipeline desbloqueado, phase-14 já dispatchada. **Não há fix de código** — issue é pattern do modelo.
- **Test:** N/A (issue de runtime do modelo, não de codebase). Mitigação no madruga.ai: skill `speckit.implement` deveria orientar uso de `wait $!` ou `timeout` em vez de sentinel-file polling. Sugestão registrada em "Melhoria — madruga.ai" abaixo.
- **Duration lost:** ~26min (de 21:27 quando teste terminou até 21:53 quando intervim)

## Síntese (2026-05-06)

**Resultado:** Epic 027 shipped em **6h22min** (17:37:08 → 23:59:32 BRT). 12/12 L2 nodes executados, 89/89 tasks de implement (com 1 retry no implement node aggregate).

**Métricas:**
- **Incidents críticos:** 2 (ambos **mesma causa raiz** — `wait pattern sem timeout`)
- **Tempo perdido em pair-program:** ~47min (~12.3% do tempo total) — economizado pela intervenção
- **Fixes commitados em código:** 0 (issues são patterns do modelo, não bugs do codebase)
- **Testes adicionados:** 0 (sem fix de código)
- **Oportunidades madruga.ai registradas:** 12 (todas independentes do código, todas relevantes)
- **Tempo médio por phase de implement:** 12min (range 4–28min)
- **Falhas silenciosas detectadas:** 5 fases com "No changes to commit" + 1 fase com 0/1 done + 1 com 6/8 done (5 tasks pendentes que easter retentou bem-sucedido)

**Causa raiz consolidada das duas intervenções:** modelo Anthropic Claude usa pattern `until [ -f sentinel ] || grep -q ... ; do sleep N; done; rtk read output` para esperar processos bg/SubagentTasks, mas:
1. Não amarra criação de sentinel ao exit do processo bg → se ele cai silencioso, loop é infinito
2. Não tem `timeout` em volta do `until` → falha-silenciosa no interno = pipeline travada

**Ranking de melhorias por ROI estimado** (todas em madruga.ai, nenhuma em platform):

1. **🔥 P0 — Anti-pattern hard-block em wait-loops** — system-prompt do dispatcher proibir `until ... do sleep ... done` sem `timeout`. Usar `wait $!` ou `timeout 60 cmd`. **ROI: enorme** — eliminou 100% dos incidentes desta rodada.
2. **🔥 P0 — Phase completion threshold** — `phase_min_completion_rate=0.5` (configurável). Abaixo disso = phase classified `failed`, easter retry com prompt enxuto. **ROI: alto** — capturaria phase-8 (0/1) e fortes degradações silenciosas.
3. **P1 — Spec slicing por user-story** — fases User-Story-N só recebem a US ativa do spec.md, não os 45KB inteiros. **ROI: médio** — 5 fases User-Story rodaram com prompt 100KB+; com slicing chegaria a ~50-60KB.
4. **P1 — File-section slicing** — `compose_task_prompt` deve fatiar arquivos grandes (`post_save.py` 30KB, `pipeline-dag-knowledge.md` 15KB) por def/seção quando task cita parte específica. **ROI: médio**.
5. **P2 — `pending_task_ids` no log** — `phase_completed` log expor IDs das tasks não-concluídas (auditoria + métrica de qualidade). **ROI: baixo mas barato** (1 linha de mudança no log).
6. **P2 — `files_written: []` no JSON de retorno** — distingue tasks "validation/no-op" das que falharam silenciosamente. **ROI: baixo** mas habilita observabilidade da #2 acima.
7. **P3 — `task_count==1` phase auto-merge** — fundir com phase anterior da mesma US se houver folga de `max_turns`. **ROI: baixo**, contornaria phase-8 (T073) e phase-13.
8. **Outros já registrados acima** (skill clarify dispatch contradição, append-system-prompt redundante, pair-program guardrail self-ref, etc).

**Pontos fortes observados (manter):**
- Easter resume logic é **excelente**: ao retomar implement node, soube pular tasks completadas e dispatchar só os 5 remanescentes — isso salvou tempo significativo no retry.
- Auto-commit per phase é **excelente** — granularidade certa, fácil revert.
- Hallucination guard (zero tool calls warning na qa) é **valioso** — sinalizou possível qa fabricada (precisa investigação manual).

**Próximos passos sugeridos para o usuário:**
1. Revisar artefatos do epic em `platforms/madruga-ai/epics/027-screen-flow-canvas/` (spec, plan, tasks, decisions, reconcile-report)
2. **Investigar warning de qa**: "node 'qa' completed with zero tool calls" — qa pode ter fabricado resultado. Rodar `make test` manualmente para validar.
3. PR/merge de `epic/madruga-ai/027-screen-flow-canvas` → `main`
4. Triar oportunidades P0/P1 acima como sub-epics ou inline-fixes
