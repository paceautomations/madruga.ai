# Easter Tracking — prosauai 012-tenant-knowledge-base-rag

Started: 2026-04-26

## Melhoria — madruga.ai

- **Portal kanban não invalida cache após erro do Start** — UI mostrou `DRAFTED` mesmo após o status já ter sido `in_progress` no DB; segundo click gerou erro 409 confuso ("expected drafted"). Fix: `POST /start` deve invalidar o cache do TanStack Query mesmo no path 409, ou fetch fresh do epic.
- **Easter loopa silenciosamente em `epic_skipped_dirty_tree`** — quando o repo externo está dirty, easter aborta e re-tenta a cada ~1min sem nenhum sinal humano (Telegram/portal). Fix: depois de N tentativas idênticas (ex: 3) emitir alerta e marcar epic como `auto-blocked` com motivo legível, em vez de seguir loopando.
- **Auto-blocking deveria suspender dispatches enquanto bloqueado** — easter loga `epic_skipped_dirty_tree` mas continua dispatchando o mesmo epic. Custos zero (curto-circuita rápido), mas polui logs e mascara o sintoma.

## Melhoria — prosauai

- **Patches do epic 011 ficaram dirty no repo externo** — `evals/autonomous_resolution.py` (refactor de advisory lock + regex `alguém real` com acento), `evals/metrics.py`, `privacy/sar.py` (73 linhas) e dois testes (141 inserções, 54 deleções) ficaram modificados sem commit ao final do 011. Origem provável: qa heal loop ou edição manual no final do 011 sem follow-up commit. Indicativo de gap no `qa` skill: deveria garantir clean tree antes de marcar epic como done.
- **Reconcile do 011 não detectou o dirty tree** — última run do reconcile (2026-04-25 13:35:53Z) marcou 011 como shipped sem flag pra esses 5 arquivos. Heurística faltando: ao final do reconcile, `git status -s` no repo externo deve estar vazio.

## Incidents críticos

### Epic 012 stuck `in_progress` sem branch nem pipeline_runs (2026-04-26 11:44)

- **Symptom:** Click em "Start" no portal gera 409 `Cannot start: status is 'in_progress', expected 'drafted'`. UI mostra DRAFTED, DB diz in_progress.
- **Detection:** Snapshot do DB (`epics` table) + ausência total de linhas em `pipeline_runs` para 012 + falta de `branch_name`.
- **Root cause:** Click em Start às 11:44:20Z flipou status corretamente (`drafted → in_progress`). Easter pegou e tentou despachar, mas o repo externo `paceautomations/prosauai` estava dirty na branch `epic/prosauai/011-evals` com 5 arquivos modificados (resíduo do epic 011 sem commit). Easter abortou com `epic_skipped_dirty_tree` e ficou loopando sem sinalizar nada.
- **Fix:** Usuário commitou os 5 arquivos manualmente como `494144c fix(011): judge-report fixes — accented escalation regex, breach-set prune, SAR phase order` na branch `epic/prosauai/011-evals`. Easter no próximo poll (11:53:08Z) detectou tree limpo, mergeou 011 em `develop` (`ec4dbf5`), criou branch `epic/prosauai/012-tenant-knowledge-base-rag`, e iniciou `specify` (epic-context já estava completed do `--draft` anterior).
- **Test:** N/A (incident operacional).
- **Duration lost:** ~9min entre primeiro skip (11:44:29Z) e início do specify (11:53:08Z).
- **Anti-recurrence:** Reconcile do 011 deveria ter falhado quando detectou `git status -s` não-vazio no repo externo. Adicionar checagem em `madruga:reconcile` (ou `madruga:qa` antes dele) que rejeita conclusão de epic com working tree dirty.

### Claude -p tentou fugir da branch durante judge (2026-04-26 16:54)

- **Symptom:** Log error no fim do `judge` node: `claude -p changed branch to 'develop', reverted to 'epic/prosauai/012-tenant-knowledge-base-rag'`.
- **Detection:** Guardrail do `dag_executor` que assertiona `git branch --show-current` antes/depois do dispatch — detectou desvio e reverteu silenciosamente. Trabalho do judge não foi perdido (cache_read=22.9M tokens, hit_rate=0.98 → análise efetiva), mas o sintoma indica que o judge prompt está pedindo (ou o agente está iniciando) algum `git checkout develop` durante review.
- **Root cause hipótese:** Skill `madruga:judge` provavelmente menciona "compare against develop" ou similar, e o agente faz `git checkout develop` literalmente em vez de `git diff develop...HEAD`. Precisa ler o skill pra confirmar.
- **Fix sugerido:** No `judge` skill, trocar instruções de "checkout develop" por `git diff develop...HEAD --stat` ou `git log develop..HEAD --oneline`. Manter o guardrail do dag_executor como rede de proteção.
- **Test:** Já temos guardrail. Adicionar log de quantas vezes o revert disparou por epic — se >0, escalar.

## Síntese

(preenchido no último tick)
