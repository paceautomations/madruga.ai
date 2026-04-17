# Easter Tracking — prosauai 008-admin-evolution

Started: 2026-04-17T11:37:00Z

## Melhoria — madruga.ai

- **Easter retenta DirtyTreeError em loop infinito (30s backoff)** — `easter.py:281` trata como `dag_scheduler_error` genérico. DirtyTreeError é user-actionable (não vai resolver sozinho). Sugestão: classificar exceptions em `transient` vs `user-actionable`; user-actionable sai do loop após 1 retry e notifica via Telegram com ação sugerida. Hoje gasta CPU + polui logs até alguém intervir.
- **Mensagem do DirtyTreeError não sugere comando de diagnóstico** — `ensure_repo.py:207` lista os arquivos mas não diz o que fazer. Adicionar `Hint: cd <repo_path> && git status` ao raise reduz friction de debug. ~3 LOC.
- **Portal Start button não faz pre-flight check no repo externo** — usuário clica Start, status vai para `in_progress`, easter dispara, falha por dirty tree, fica em loop. Preventivo melhor: `POST /api/epics/{platform}/{epic}/start` valida `git status` no repo externo antes de mudar status. Bloqueia com mensagem amigável "repo prosauai tem 2 arquivos untracked: <list>. Limpe antes de iniciar".
- **🔴 PONTO A RESOLVER — `epic-context` deve garantir que TODO contexto fique no epic dir** — qualquer referência externa apontada como input (path para `docs/prosauai/`, link para Notion, gist, copy-paste em system-reminder, etc.) precisa terminar dentro de `platforms/<p>/epics/<NNN>/` para que SpecKit consuma automaticamente nas etapas seguintes. Hoje a skill apenas CITA o path externo no pitch — se o arquivo está fora do epic dir, `speckit.specify`/`plan` podem não ler. Soluções possíveis: (a) auto-mover arquivo apontado via `--ref <path>`, (b) auto-copiar como `epics/<NNN>/reference-<basename>.md` + atualizar refs no pitch, (c) fail-fast se input file está fora de epic dir até user mover. Sem isso, qualquer detalhamento (specs UI, payloads, SQL queries) fica órfão e o épico construído acima fica anêmico de contexto. **Manifestou-se neste épico**: usuário passou doc de 1001 linhas em `madruga.ai/docs/prosauai/`, fix manual necessário durante pair-program para mover.
- **Backup periódico do madruga.db quebra com `sqlite3.ProgrammingError: thread`** — `easter.py:471` cria conn fora da thread executor. Apareceu em log de 06:06 (boot anterior). Não é crítico (próximo boot reseta) mas é noise nos logs.
- **Telegram bot conflict — duas instâncias do aiogram rodando** — desde 09:20:44 logs do easter (PID 30837 / uvicorn) mostram `TelegramConflictError: terminated by other getUpdates request`. 15 retries com backoff exponencial (~5s cada). Indica outro processo polling o mesmo bot @madrugaAI_bot id=8618777736. Pode ser: (a) outra instância do easter rodando em background (verificar `pgrep -af easter`), (b) script de dev local, (c) leak de boot anterior. Não bloqueia o pipeline mas polui logs e gasta rede. Sugestão: lock distribuído para o getUpdates loop OR file lock que impede 2 daemons do bot ativo.
- **🟡 Branch swap RECORRENTE em dispatched claude — investigar urgente** — repete em TODA dispatch que termina. Logs confirmados: 08:45:27 (specify), 08:49:01 (clarify). Padrão: `"claude -p changed branch to 'epic/madruga-ai/026-runtime-qa-testing-pyramid', reverted to 'epic/prosauai/008-admin-evolution'"`. Disallowed tools incluem `git checkout/branch-/switch`, então o vetor pode ser: (a) `git worktree add` (não bloqueado), (b) Write em `.git/HEAD`, (c) algum side-effect interno do `claude -p` (sessão, hooks). Proteção funciona (dag_executor reverte), MAS gera 1 ERROR log por nó — vai poluir métricas Phoenix/observabilidade quando epic 002 estiver mais maduro. Ações sugeridas em ordem de impacto: (1) instrumentar `dag_executor` para logar QUEM mudou o HEAD (stack trace ou audit do filesystem mtime de `.git/HEAD`); (2) adicionar `Bash(git worktree:*)` + Read/Write `.git/HEAD` ao disallowedTools; (3) se persistir, abrir issue no `claude` CLI sobre side-effect de branch state.
- **🟠 Prompt da implement:phase-1 = 134KB (acima do threshold 80KB)** — log às 09:09:18 mostra `phase_prompt_composed sections={cue: 64, plan: 22147, spec: 43549, data_model: 15238, contract:README.md: 2271, tasks: 48217, header: 3263} total_bytes=134749`. Phase 1 = "Setup (Shared Infrastructure)" com APENAS 6 tasks (T001-T006), mas recebe a spec completa de 8 user stories (43KB) e o tasks.md inteiro com 158 tasks (48KB). Cache-optimal prefix (gotcha CLAUDE.md `MADRUGA_CACHE_ORDERED=1`) ajuda no custo (mesmo prefixo nas tasks 2..N), mas o tamanho absoluto polui o context window e diminui qualidade do modelo. Sugestões em ordem: (1) **Scope-aware composer**: para phase de "Setup" (zero user-story tasks), excluir spec.md inteiro — basta plan + data_model + contracts. (2) Para phases "User Story N", incluir SÓ a seção daquela story em spec.md (parsing via `## User Story N` headers). (3) tasks.md sempre incluído inteiro? Não — incluir header + tasks daquela phase só. Economia esperada: 70-80KB por phase de setup, 30-50KB por phase de user story. Valida `compose_task_prompt` em `dag_executor.py:1291` ou wherever phase composition lives.
- **🔴 PONTO A RESOLVER — dispatched claude rodou `make test` no repo ERRADO** — durante implement:phase-1 do prosauai/008, o claude executou `make test 2>&1 | tail -40` cujo subprocess pytest rodou `python3 -m pytest .specify/scripts/tests/` (testes do MADRUGA.AI, não do prosauai). Causa: o CWD do dispatched claude é `madruga.ai/` (onde easter roda), não o repo da plataforma. As 6 tasks já estão [X] em tasks.md, mas `make test` está pendurado há 10+ min validando código irrelevante. **Custo:** ~10min de CPU/wallclock já gastos + ~5-10min mais até pytest terminar = ~15-20min desperdiçados por phase. Para 18 phases, isso é **4-6h de waste se cada phase rodar o mesmo make test**. Sugestões: (a) `--append-system-prompt` deve ESPECIFICAR o repo de testes (`cd <code_dir> && make test` se phases produzirem código), (b) ou injetar override de `make test` para um wrapper que respeita `code_dir`, (c) ou simplesmente dizer "do not run repo-level test commands; trust per-task assertions". Para Phase 1 que é só audit, nem precisa rodar testes nenhum.
- **Lição pair-program (2026-04-17 ~10:33)** — durante observação de implement:phase-1, classifiquei como critical com base em `pipeline_runs.status='running'` há 27min + subprocess `claude` ELAPSED 26min + pytest 59524 com CPU time travado em 2:40. Pedi e recebi aprovação para `kill 59524`. Pós-kill descobri que o pipeline já tinha avançado naturalmente: phase-1 completed às 10:04 local (~55min total), phase-2 completed às 10:26 (~22min), phase-3 já running há 7min. **O pytest 59524 que matei era de phase-2 ou 3 (ELAPSED 1h3min → started ~09:30, não phase-1 que começou 09:09)**. Cache do snapshot pipeline_runs estava certo, mas eu interpretei mal o vínculo entre processos. Lição: na próxima borderline, query `pipeline_runs` MAIS DE UMA VEZ no mesmo tick antes de classificar critical, e correlacione subprocess timestamps com node start times. Net effect do kill: removeu um pytest pendurado (provavelmente positivo), sem dano ao pipeline.

- **🔴 PONTO A RESOLVER — `duration_ms` NULL em runs rescued por `success_check` (timeout sem stdout)** — implement:phase-1 do prosauai/008 sofreu timeout de 3000s sem capturar stdout JSON (0 bytes). O `success_check` rescue-path (commit `849f183`) detectou que o trabalho foi feito (tasks marcadas [X]) e marcou o run como `completed` corretamente. Mas as métricas (cost_usd, tokens_in, tokens_out, duration_ms) ficaram NULL no DB, e o portal mostra `—` em todas as colunas exceto Q/A/C/E.

  **Causa raiz:** [db_pipeline.py:459-467](.specify/scripts/db_pipeline.py#L459-L467):
  ```python
  reported = kwargs.get("duration_ms")
  if reported is not None and reported < _WALL_CLOCK_THRESHOLD_MS:  # ← bug: requires non-None
      # compute wall_ms from started_at to completed_at
  ```
  Quando `reported is None` (success_check rescue path), o fallback de wall-clock nem é tentado.

  **Fix proposto (~5 LOC):**
  ```python
  reported = kwargs.get("duration_ms")
  needs_wall_clock = reported is None or reported < _WALL_CLOCK_THRESHOLD_MS
  if needs_wall_clock:
      row = conn.execute("SELECT started_at FROM pipeline_runs WHERE run_id=?", (run_id,)).fetchone()
      if row and row[0]:
          wall_ms = int(
              (datetime.fromisoformat(completed_at) - datetime.fromisoformat(row[0])).total_seconds() * 1000
          )
          if reported is None or wall_ms > reported:
              kwargs["duration_ms"] = wall_ms
  ```

  **Impacto:** cost_usd e tokens não podem ser recuperados (vivem só no stdout perdido) — esses ficam NULL legitimamente. Mas `duration_ms` é trivialmente computável dos timestamps, então o fix preenche essa coluna em 100% dos casos.

  **Backward-compat:** `reported >= THRESHOLD` mantém comportamento atual; `reported < THRESHOLD` mantém substituição existente; novo caso `reported is None` entra no wall-clock branch.

  **Teste a adicionar** (em `tests/test_db_pipeline.py`): caso `complete_run(run_id, status='completed')` sem passar `duration_ms` → DB deve ter `duration_ms` calculado como `(completed_at - started_at) * 1000`.

  **Retro-fix (após code fix mergeado):** `UPDATE pipeline_runs SET duration_ms = CAST((julianday(completed_at) - julianday(started_at)) * 86400000 AS INTEGER) WHERE duration_ms IS NULL AND status='completed' AND completed_at IS NOT NULL` — preenche históricos.

  Manifestou-se em: implement:phase-1 (run_id `8718bb50`) — duration real ~55min (3322s).

## Melhoria — prosauai
- Repo nao tem `.playwright-mcp/` no `.gitignore` — qualquer rodada de Playwright MCP suja a tree e bloqueia easter. **RESOLVIDO** no commit `118a67d` durante este epic.

## Audit results — PR 0 / Setup Phase (2026-04-17)

> Resultados das tasks T004 (messages.metadata touches) e T005 (OTel instrumentation) do plano de tarefas do epic 008. Referência para PR 2 (instrumentation).

### T004 — `messages.metadata` audit

Comando executado (equivalente ao requerido):
`rg -n "metadata" apps/api/prosauai/conversation/ apps/api/prosauai/core/router/ --type py`

**Conclusão:** existe zero escrita em `messages.metadata` JSONB a partir do pipeline ou do router. A nova instrumentação de `trace_steps` NÃO duplica info hoje.

Detalhes:

- `apps/api/prosauai/conversation/pipeline.py::save_message` aceita `metadata: dict | None = None` como parâmetro opcional, mas **todas as três chamadas** (save_inbound linha 598, blocked outbound linha 653, save_outbound linha 747) invocam SEM passar metadata. `messages.metadata` fica sempre `{}` em produção. Oportunidade identificada mas descartada para o epic 008: a nova tabela `trace_steps` é consumidor canônico; aumentar acoplamento via `messages.metadata` seria duplicação.
- `apps/api/prosauai/conversation/classifier.py` usa `ClassificationResult.metadata` (linhas 164, 220, 239) — Pydantic **interno** do classifier output para carregar flags `fallback`/`reason`. Não é persistido em `messages.metadata`.
- `apps/api/prosauai/conversation/customer.py:56` lê (não escreve) `customers.metadata`.
- `apps/api/prosauai/conversation/models.py` (linhas 37, 75, 223) apenas define campos Pydantic `metadata` nas entidades; não são escritos pelo pipeline.
- `apps/api/prosauai/core/router/facts.py` (linhas 36, 177) — strings literais `"group_metadata"` para tipo de evento WhatsApp (protocolMessage). Sem relação com `messages.metadata`.

**Implicação para PR 2:** StepRecord + trace_steps não conflita com escrita existente. Nenhuma migração de dados necessária.

### T005 — OTel instrumentation audit

Comando executado (equivalente):
`rg -n "start_as_current_span|get_current_span" apps/api/prosauai/conversation/ apps/api/prosauai/observability/`

**Conclusão:** `Pipeline.execute()` (função pública `process_conversation`) já abre um span pai `conversation.process` em `apps/api/prosauai/conversation/pipeline.py:479-484`. Todos os steps executam dentro desse contexto OTel, então `opentelemetry.trace.get_current_span()` retorna span válido e `.get_span_context().trace_id` pode ser lido conforme R2. **Pré-requisito de R2 satisfeito.**

Spans filhos já existentes no pipeline (ordem de execução):

| # | Span name | Linha | Mapeia para step de `trace_steps` |
|---|-----------|-------|-----------------------------------|
| 1 | `conversation.resolve_agent` | 554 | *(não listado nos 12 — agent resolution é setup interno)* |
| 2 | `conversation.customer_lookup` | 565 | `customer_lookup` ✓ |
| 3 | `conversation.get_or_create` | 576 | `conversation_get` ✓ |
| 4 | `conversation.save_inbound` | 597 | `save_inbound` ✓ |
| 5 | `conversation.context_build` | 609 | `build_context` ✓ |
| 6 | `conversation.input_guard` | 619 | *(não listado nos 12 — pré-classificação)* |
| 7 | `conversation.classify` | 672 | `classify_intent` ✓ |
| 8 | `conversation.generate` | 697 | `generate_response` ✓ |
| 9 | `conversation.output_guard` | 725 | `output_guard` ✓ |
| 10 | `conversation.save_outbound` | 746 | `save_outbound` ✓ |
| 11 | `conversation.update_state` | 758 | *(não listado nos 12)* |
| 12 | `conversation.evaluate` | 378 | `evaluate_response` ✓ |
| 13 | `conversation.save_eval` | 835 | *(pós-resposta — não no hot path cronometrado)* |

**Drift detectado** (IMPORTANTE para PR 2): A lista de 12 etapas definida no plano do epic 008 é `webhook_received, route, customer_lookup, conversation_get, save_inbound, build_context, classify_intent, generate_response, evaluate_response, output_guard, save_outbound, deliver` — mas o pipeline atual **não** tem spans para `webhook_received`, `route` ou `deliver` no módulo `conversation/pipeline.py`. Estes provavelmente estão em `apps/api/prosauai/channels/whatsapp.py` (webhook_received) e `apps/api/prosauai/core/router/engine.py` (route) — precisam ser confirmados/instrumentados no PR 2. Em contrapartida, `resolve_agent`, `input_guard`, `update_state`, `save_eval` existem hoje mas não fazem parte dos 12.

**Decisão para PR 2** (proposta, a confirmar na implementação): manter a taxonomia de 12 nomes do plano como contrato externo (`trace_steps.name`). Mapear os spans existentes para os nomes canônicos. Spans fora do conjunto (ex: `resolve_agent`, `update_state`, `save_eval`) podem ser agregados ao step canônico mais próximo no `StepRecord` (ex: `resolve_agent` soma em `conversation_get`) OU aceitar que o conjunto real é maior que 12 e ajustar data-model.md para `CHECK (step_order BETWEEN 1 AND N)` com N dinâmico. Recomendação: manter 12 canônicos e **não emitir StepRecord** para os spans auxiliares (`resolve_agent`, `input_guard`, `update_state`, `save_eval`), preservando fidelidade ao spec FR-030 e plano.

### T006 — Pricing validation (recorded 2026-04-17)

Verificação manual contra ADR-025 + notas públicas OpenAI (2026-04):

| Modelo | research.md R14 | ADR-025 / código real | Status | Ação |
|--------|-----------------|----------------------|--------|------|
| gpt-4o | $0.0025 / $0.010 per 1k | mesmo | ✓ confirmado | sem alteração |
| gpt-4o-mini | $0.00015 / $0.0006 per 1k | mesmo | ✓ confirmado | sem alteração |
| gpt-5-mini | $0.0015 / $0.006 per 1k | ADR-025 menciona `gpt-5.4-mini` como default da família | `[VALIDAR]` | **flag `# TODO: confirm pricing`** em `pricing.py` + adicionar entrada `gpt-5.4-mini` com estimativa separada (preço ~3× gpt-5-mini conforme ADR-025) |

**Divergência entre documentação** encontrada: research.md R14 (decisão 17 do epic) referencia `gpt-5-mini`, mas ADR-025 define `gpt-5.4-mini` como modelo default em rotação (classifier + agent principal). O valor de `gpt-5.4-mini` não está publicado em nenhum ADR. Ação em PR 2 (T020): ambos entrando no dicionário; `gpt-5-mini` mantém valor do R14 + `[VALIDAR]`; `gpt-5.4-mini` entra com estimativa (0.00045 / 0.0027 per 1k = 3× gpt-5-mini baseline, consistente com ADR-025 "~3x o custo de 5-mini") + `[VALIDAR]`. Tests T021 cobrem ambos.

**Resolução final de T006:** aceitar ambos os modelos no dict com flag TODO; quando OpenAI publicar números oficiais (esperado Q3 2026), PR de 2 linhas remove os marcadores. Documentação fonte-de-verdade: este audit + research.md R14 + ADR-025.

## Incidents críticos

### DirtyTreeError bloqueia dispatch (2026-04-17 08:35)
- **Symptom:** easter dispara epic 008 mas `consecutive_errors=1, backoff_s=30` em loop. 3 falhas registradas em ~5min.
- **Detection:** `journalctl --user -u madruga-easter` — `ensure_repo.DirtyTreeError: /home/gabrielhamu/repos/paceautomations/prosauai has uncommitted changes`.
- **Root cause:** repo externo prosauai tem 2 arquivos untracked:
  - `?? .playwright-mcp/` — artefatos de teste Playwright (logs + screenshots de 2026-04-16)
  - `?? Evolução_front_admin.md` — copia da spec doc (idêntica byte-a-byte ao `/home/gabrielhamu/repos/paceautomations/madruga.ai/docs/prosauai/Evolução_front_admin.md`, confirmado via `diff -q`)
  - `ensure_repo._checkout_epic_branch` (line 207) recusa checkout com tree dirty para nao perder trabalho do usuario.
- **Fix:** (1) `rm prosauai/Evolução_front_admin.md` (duplicata, original ja em madruga.ai). (2) Append `.playwright-mcp/` ao `prosauai/.gitignore` + commit `118a67d "chore: ignore .playwright-mcp/ test artifacts"` na branch epic/prosauai/008-admin-evolution. (3) Move `madruga.ai/docs/prosauai/Evolução_front_admin.md` → `epics/008-admin-evolution/reference-spec.md` (vira input para SpecKit). (4) Update refs em pitch.md + decisions.md.
- **Test:** N/A (fix de dados/config, nao de codigo).
- **Duration lost:** ~30min (de 08:35 ate 09:39 intervencao).

### Pytest zumbi bloqueando implement:phase-1 (2026-04-17 ~10:33)
- **Symptom:** `pipeline_runs.status='running'` há 27min em implement:phase-1 + subprocess `claude -p` ELAPSED 26min + pytest 59524 travado com CPU time estagnado em 2:40. Zero stdout JSON emitido.
- **Detection:** `ps --ppid` + correlação com `pipeline_runs` durante tick do pair-program.
- **Root cause:** **dispatched claude executou `make test` no CWD errado** — rodou `python3 -m pytest .specify/scripts/tests/` (testes do madruga.ai) em vez dos testes do prosauai. Pytest do madruga.ai tinha suite pesada que deadlockou. `--append-system-prompt` não especifica `cd <code_dir>` antes de test commands.
- **Fix:** `kill 59524` destravou o wait de `claude -p`. Success_check rescue-path (commit `849f183`) detectou tasks [X] e marcou run completed. Fix sistêmico (dispatch) documentado em Melhoria — madruga.ai bullet 🔴 acima — não aplicado neste ciclo.
- **Test:** N/A neste ciclo (fix deferred).
- **Duration lost:** ~55min de wall-clock (phase-1: 09:09 → 10:04). Métricas NULL (cost/tokens/duration_ms) por falta de stdout — levou ao bullet 🔴 duration_ms separado.

### Phase-18 deadlock — 5 pytests zumbi (2026-04-17 ~13:08)
- **Symptom:** implement:phase-18 running há ~42min, 5 processos pytest acumulados (alguns ELAPSED >1h). Mesmo padrão do incidente anterior.
- **Detection:** `ps --ppid <easter-pid>` + user feedback "limpar os pytests zombies".
- **Root cause:** Mesmo sistêmico (wrong CWD em `make test` dispatched). Acúmulo desta vez foi pior porque 18 phases × mesmo bug = vazamento gradual de pytests.
- **Fix:** `kill -9` cascade nos 5 zombies + 2 adicionais que nasceram após (incluindo PID 317406). Pipeline retomou: Easter re-dispatched phase-1 (T030 deferred) + phase-2 (T904-T909 polish) = 152/152 tasks. **Observado durante:** 7 tasks pending foram absorvidas em novo dispatch sequencial — Easter usou DAG graceful retry após success_check mark.
- **Test:** N/A neste ciclo.
- **Duration lost:** ~45min de wall-clock.

## Síntese (2026-04-17)

### Métricas

| Métrica | Valor |
|---------|-------|
| Nodes executados | 30 (incluindo 18 phases + 2 retries implement) |
| Wall-clock total | 291 min (~4h51) |
| Custo total | $164.46 |
| Tasks entregues | 152 / 152 (100%) |
| Incidentes críticos | 3 |
| Tempo perdido em incidentes | ~130 min (~45% do total!) |
| Fixes commitados durante epic | 1 (`118a67d` .gitignore .playwright-mcp/) |
| Fixes deferred para follow-up | 4 (documentados com código pronto) |
| Oportunidades registradas | 9 (madruga.ai) + 1 (prosauai — resolvida) |

### Causas raiz (agrupadas por origem)

**RC-1: Dispatch não especifica CWD para subprocess de test** — causa raiz de 2 dos 3 incidentes (~100min perdidos). Manifesta como pytest zumbi quando dispatched claude roda `make test`. Solução: `--append-system-prompt` deve dizer `cd <code_dir>` antes de qualquer test command, ou injetar wrapper de `make test` que respeita `code_dir`.

**RC-2: Pre-flight check ausente no Start button** — causa raiz do incidente DirtyTreeError (~30min). Usuário clica Start sem saber que repo externo tem untracked files; Easter entra em loop infinito de retry. Solução: `POST /api/epics/{p}/{e}/start` valida `git status` no repo externo antes de promover status.

**RC-3: `success_check` rescue-path deixa métricas NULL** — efeito colateral do workaround de timeout: preserva funcionalidade (tasks marcadas, pipeline avança) mas perde `duration_ms`/`cost_usd`/`tokens`. Solução documentada com 5 LOC de patch + retro-fix SQL.

### Consolidado — Melhoria madruga.ai (por prioridade)

**🔴 CRÍTICO — aplicar antes do próximo epic:**

1. **Dispatched `make test` no CWD errado** (RC-1) — `--append-system-prompt` deve garantir `cd <code_dir>` antes de test commands. Impacto: ~100min/epic desperdiçados + pytests zumbi acumulam. Alvo: `dag_executor.compose_task_prompt` ou system prompt base.
2. **`duration_ms` NULL em success_check rescue** (RC-3) — 5 LOC em [db_pipeline.py:459-467](.specify/scripts/db_pipeline.py#L459-L467) + teste + retro-fix SQL. Patch completo documentado acima.
3. **`epic-context` não move refs externos para epic dir** — qualquer input file apontado via path deve ser auto-movido/copiado para `epics/<NNN>/` para que SpecKit consuma. Solução: flag `--ref <path>` com auto-copy.

**🟡 IMPORTANTE — aplicar no próximo sprint:**

4. **Branch swap em dispatched claude** (toda dispatch emite 1 ERROR) — instrumentar `dag_executor` para logar QUEM muda `.git/HEAD`; adicionar `Bash(git worktree:*)` + Write em `.git/HEAD` ao disallowedTools.
5. **DirtyTreeError não é classificado como user-actionable** (RC-2) — classificar exceptions em `transient` vs `user-actionable` no `easter.py:281`; user-actionable sai do loop após 1 retry com notificação Telegram.
6. **Prompt de phase de Setup = 134KB** — scope-aware composer: phases "Setup" não precisam de spec.md inteiro; phases "User Story N" incluem só a seção daquela story. Alvo: `compose_task_prompt`.

**🟢 POLISH:**

7. Pre-flight `git status` no `POST /api/epics/{p}/{e}/start` (RC-2) — bloqueia Start com mensagem amigável se repo externo está sujo.
8. Backup periódico do madruga.db quebra com `sqlite3.ProgrammingError` — `easter.py:471` cria conn fora da thread executor.
9. Telegram bot conflict (duas instâncias aiogram) — lock distribuído ou file lock para impedir 2 daemons ativos.

### Consolidado — Melhoria prosauai

Zero pendências novas. A única oportunidade registrada (`.playwright-mcp/` no `.gitignore`) foi resolvida durante o epic via commit `118a67d`.

### Lição processo (pair-program)

Na primeira intervenção crítica, classifiquei subprocess pytest como "trava de phase-1" baseado em timestamps batidos — mas o processo era de phase-2/3 (já em andamento). Lição: **na próxima classificação borderline, query `pipeline_runs` MAIS DE UMA VEZ no mesmo tick** e correlacione `started_at` dos nodes com ELAPSED dos subprocessos. Net effect neste caso foi neutro (pytest travado merecia kill), mas poderia ter sido destrutivo em outro contexto.

### Status final

Epic `shipped`, branch `epic/prosauai/008-admin-evolution` pronta para merge via PR. Fixes deferred ficam documentados aqui — aplicar em next epic ou em PR de infra dedicada em madruga.ai.
