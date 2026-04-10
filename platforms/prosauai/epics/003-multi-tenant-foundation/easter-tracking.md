---
epic: 003-multi-tenant-foundation
session: live-tracking (2026-04-10)
status: em-andamento
---
# Easter Tracking — Epic 003 Multi-Tenant Foundation

Acompanhamento assistido em tempo real da execucao do epic 003 pelo daemon easter. Objetivo: mapear o que esta funcionando bem vs o que pode melhorar. **Este arquivo e atualizado iterativamente** durante a sessao de acompanhamento.

## Contexto da execucao

- **Daemon**: `madruga-easter.service` (PID 1407617, uvicorn em :18789, up desde 12:37 BRT)
- **Epic dispatched**: 2026-04-10 15:53:24 UTC (12:53 BRT) — ~20s apos promocao do `drafted → in_progress`
- **Modo**: L2 async, gate=auto, pipeline 12 nodes
- **Repo externo**: `prosauai` — usa **worktree** em `/home/gabrielhamu/repos/prosauai-worktrees/003-multi-tenant-foundation`
- **Base branch**: `develop` (commit `35642e7 Merge epic/prosauai/002-observability into develop`)
- **Trace ID**: `12b04e976e5b4aae876af7971c340516`

## Pre-gate (resolvido)

Minha Captured Decision #18 temia que 002 nao estivesse em `develop` — este risco esta **resolvido**. Develop tem:
- `35642e7 Merge epic/prosauai/002-observability into develop`
- `67cdc81 feat: epic 002-observability — QA fixes and reports`
- `1c751b1 feat: epic 002-observability — implement tasks`
- `91dd8b6 feat: multi-tenant auth plan, real-payload fixture catalog, port 8050`

Implicacao: o scope real do observability delta (~25-30 LOC em 4-5 arquivos) e aplicavel como previsto. O worktree do 003 ja tem `prosauai/observability/*.py`, `phoenix-dashboards/`, e o `port=8040` do 002 que precisa ser mudado para `port=8050` (ja na base `91dd8b6`, mas 002 sobrescreveu).

## Timeline observada

| Node | Dispatched | Completed | Duracao | Status | Output |
|------|-----------|-----------|---------|--------|--------|
| epic-context | — | 15:53:12 UTC | — (pre-easter, manual) | done | pitch.md (555 LOC), decisions.md (29 LOC) |
| specify | 15:53:29 | 15:56:50 | 3m 21s | done | spec.md (273 LOC) |
| clarify | 15:56:50 | 15:59:12 | 2m 22s | done | spec.md (re-hashed, mesmo sha256) |
| plan | 15:59:12 | 16:07:48 | 8m 36s | done | plan.md (441 LOC, preenchido), research.md (182), data-model.md (410), quickstart.md (174), contracts/ (75+168 LOC), checklists/ (37 LOC) |
| tasks | 16:08:20 | 16:12:04 | 3m 44s | done | tasks.md (359 LOC, 46 tasks T001-T046 em 10 phases/7 user stories) |
| analyze | 16:13:07 | 16:16:39 | 3m 32s | done | analyze-report.md (14 findings + coverage matrix, 1 GAP identificado) |
| implement | 16:17:03 | (em-andamento) | — | running | Task-by-task (1 claude subprocess per task, 600s timeout). T001 completo em 57s, T002 em progresso |
| analyze | — | — | — | pending | — |
| implement | — | — | — | pending | — |
| analyze-post | — | — | — | pending | — |
| judge | — | — | — | pending | — |
| qa | — | — | — | pending | — |
| reconcile | — | — | — | pending | — |
| roadmap-reassess | — | — | — | pending | — |

## Observacoes — FUNCIONANDO BEM

### 1. Pickup rapido pelo easter
- Daemon detectou o `in_progress` em ~20s apos o `post_save.py` transicionar o status. Latencia de polling minima.
- `external_repo_skip_checkout` correto — daemon nao tentou fazer checkout inadequado no madruga.ai, sabia que precisa de worktree para o repo externo.

### 2. Worktree hygiene
- Worktree criado automaticamente a partir de `origin/develop`, branch `epic/prosauai/003-multi-tenant-foundation` trackeada. Zero intervencao manual.
- Caminho previsivel: `/home/gabrielhamu/repos/prosauai-worktrees/<epic-slug>/`
- Isolamento total do working tree principal do prosauai.

### 3. Spec de altissima qualidade
`spec.md` (273 LOC) entrega o padrao ideal de user stories Shape Up/SpecKit:
- 6+ user stories com prioridades P1/P2
- Formato Given/When/Then rigoroso em 100% dos acceptance scenarios
- Cada story tem "Why this priority" + "Independent Test"
- Cobre todos os 3 bloqueios do pitch (HMAC imaginario, parser divergente, multi-tenant)
- User Story 6 "Observabilidade multi-tenant nos spans e logs" foi incluida automaticamente refletindo a decisao #16 revisada do pitch

### 4. Research.md substantivo
- 182 LOC com tabela de 12 divergencias do parser (cada uma com "Parser Epic 001 vs Realidade v2.3.0")
- Cita fontes reais (Evolution `webhook.controller.ts`, issue #102, captura empirica)
- Apresenta 3-4 alternativas por decisao com rationale

### 5. Data-model.md completo
- 410 LOC descrevendo Tenant, TenantStore, ParsedMessage, Redis keys, FlushCallback
- Inclui validacoes no loader e relationships
- Codigo Python idiomatico (`@dataclass(frozen=True, slots=True)`)

### 6. Artefatos de suporte (quickstart.md, contracts/, checklists/)
- quickstart.md com setup passo-a-passo (174 LOC)
- `contracts/tenant-config.md` e `contracts/webhook-api.md` (cobertura de I/O boundary)
- `checklists/requirements.md` (auto-gate pre-implement)

### 7. Context do delta review preservado
- O prompt do plan subprocess inclui a pitch.md revisada **inteira** (555 LOC), incluindo os `[REVISADO]` e `[NOVO]` marks das Captured Decisions #14, #16, #17, #18.
- Implicacao: o subprocess tem contexto completo do escopo real (~25-30 LOC obs delta, nao ~5), do pre-gate de 002-merged-to-develop, e do contrato preservado de `SpanAttributes.TENANT_ID`.
- Evidencia forte: plan.md source tree markers usam `observability/setup.py MODIFIED` e `observability/conventions.py UNCHANGED`, e tasks.md T040 literal diz "Verify SpanAttributes.TENANT_ID preserved — No code changes needed — just verification".

### 8. analyze-report.md e UMA JOIA de qualidade
14 findings produzidos pelo `speckit.analyze`, categorizados em 6 tipos:
- **Coverage (C1-C3)**: lacunas entre spec/SC e tasks — **C1 identificou um GAP real**: `SC-011 p99 < 100ms` nao tem nenhuma task de benchmark/load test no pipeline. Recomenda adicionar em Phase 10 ou remover SC-011.
- **Inconsistency (F1-F3)**: **F1 catch bom** — task IDs divergem (pitch usa T0-T21/T6b-T6j/T11b-T11f, tasks.md usa T001-T046), sem tabela de mapeamento explicita. **F2 catch ainda melhor** — `append_or_immediate()` mencionado em pitch T11e mas NAO em tasks.md T030; isto era um gap real no meu pitch que o analyze detectou.
- **Ambiguity (A1-A3)**: A1 pega uma palavra-chave "ou" ambigua no edge case de message_id sintetizacao.
- **Duplication (D1)**: T005 e T041 ambos removem `settings.tenant_id` — recomendacao correta de manter T041 como "verification task, grep-based".
- **Underspecification (U1-U2)**: U1 levanta privacy concern (resposta 404 precisa ser identica para disabled vs unknown tenant, sem leak de info).
- **Edge case (E1)**: falta unit test cobrindo resolucao de tenant no flush callback com 2 tenants.

**Coverage matrix** lista todos os 40 FRs e 11 SCs com mapeamento para task IDs, e explicita "Nenhuma task orfa" — todas as 46 tasks mapeiam para pelo menos 1 FR/SC/edge-case.

**Este e um exemplo cannonical de como um consistency check deve funcionar** — nao apenas lista problemas, mas categoriza severidade, cita source, e sugere acao. Worth considering como template para outras plataformas.

### 9. Task-by-task implement pattern
- Easter nao roda `speckit.implement` como 1 subprocess gigantesco. Ao inves, dispatch **1 task por vez** em subprocesses separados (`implement:T001`, `implement:T002`, ...) com timeout 600s (10 min) cada.
- Log de easter ja mostra: `"Task-by-task implement: 46 pending of 46 total"` + `"Task T001 completed (1/46)"`.
- **Beneficios**: (a) timeout curto evita subprocesses zumbi, (b) falha isolada (1 task falha nao mata as outras), (c) progresso granular visivel, (d) retry facil de 1 task.
- **Custo**: 46 subprocesses, 46 startups do claude CLI, overhead de ~3-5s por subprocess de setup (observado no DB).
- **Tempo estimado total**: se media 57s/task como T001 → ~44 min para 46 tasks. Se media 2min → ~92 min. Bench para trabalho L2 pesado.

## Observacoes — PODE MELHORAR

### 1. `plan.md` escrito como template vazio primeiro — `[CORRIGIDO apos plan completar]`
**Observacao inicial (incorreta)**: Suspeitei que plan.md estava "preso" em template porque tinha 104 LOC com placeholders enquanto research/data-model/quickstart ja estavam substantivos.

**Correcao apos plan completar** (16:07:48 UTC, 8m 36s total): **plan.md foi corretamente preenchido** — cresceu de 104 LOC (template scaffold) para 441 LOC com:
- Constitution Check de 9 principios ✅ com rationale
- Technical Context completo (Python 3.12, FastAPI, Redis 7, pydantic 2, etc.)
- Source tree com markers `NEW`/`MODIFIED`/`REWRITTEN`/`UNCHANGED`/`DELETED`
- **O delta observability do meu epic-context foi corretamente propagado**: `observability/setup.py MODIFIED`, `observability/conventions.py UNCHANGED` (contract preserved), alinhado com Captured Decisions #16 e #17 do pitch revisado

**O que aprendi**: `speckit.plan` segue um pipeline interno — primeiro gera scaffolds (plan.md template + research.md + data-model.md + quickstart.md + contracts/), depois itera sobre plan.md preenchendo secao por secao. Durante a execucao, plan.md parece "atrasado" mas e apenas ordem de escrita, nao bug.

**Risco residual (pequeno)**: durante o intervalo onde plan.md ainda esta template, um observador/readyness probe externo pode concluir erradamente que o plan ja terminou. Mitigacao possivel: marker file `plan.md.in-progress` ou status file em DB.

### 2. `clarify` produz mesmo `output_hash` que `specify`
Ambos registraram artefato `spec.md` com `sha256:5b4c26bf3bbb9069261f064a3e58d00bb543592fcc69917d274ebef842299ea7`. Duas leituras possiveis:
- **Leitura A (OK)**: clarify nao encontrou ambiguidades a resolver, entao spec.md ficou inalterado (menos provavel — o spec tem 10+ [NEEDS CLARIFICATION] potenciais marcados como P1/P2)
- **Leitura B (bug)**: clarify registrou o artefato sem rodar o diff corretamente, perdemos log de perguntas/respostas de clarificacao

**Sugestao**: clarify deveria registrar em arquivo separado as perguntas que fez + respostas (ex: `clarify-log.md`), mesmo que o resultado final seja spec.md intocado.

### 3. Timing dos nodes (baseline inicial)
Numeros observados ate agora:
- specify: 3m 21s
- clarify: 2m 22s
- plan: 9+ min (em andamento) — provavelmente o node mais longo

O `implement` node vai dominar o tempo total — expectativa e 20-40 min dado o escopo (25 tasks + novo observability delta). Worth tracking para comparar com outros epics.

### 4. Observabilidade da propria execucao
Poderia ter:
- Metrics em tempo real no portal showing node progress por epic
- Tempo gasto em "thinking tokens" vs "tool tokens" (claude subprocess)
- Contagem de subtasks spawned pelo claude internal
- Memoria / CPU por subprocess

Isso existe parcialmente (`db_observability` loga traces) mas nao esta visivel no acompanhamento live.

### 5. Easter nao notifica ao stop/crash
Se o subprocess plan cair (OOM, timeout, etc), precisa ser detectado polling do DB ou da process table. Uma notificacao push (Telegram, conforme ADR-018) seria util mesmo para eventos unhappy do easter.

### 6. T015 — context overload causando timeouts [OBSERVADO 14:21 BRT]
**O que aconteceu**: Task T015 (`formatter.py` expand ParsedMessage 12→22+ campos) deu timeout na tentativa 1 (14:10→14:21, 600s) e na tentativa 2 (14:21→14:32, 600s). Terceira tentativa rodando agora (14:32:49).

**Root cause probable**: Acumulacao de contexto — T014 ja tinha 2.86M tokens de input. O prompt de T015 inclui todos os prior task summaries + fixtures data acumulado. O subprocess claude nao consegue completar a escrita do formatter.py (task complexa, possivelmente tentando usar muitos tool calls) dentro de 600s.

**Retry behavior**:
- Retry 1 tentou `--resume` da sessao anterior (07725f55-454) — continuou a falhar
- Retries 2+ sem resume — reinicia do zero (potencialmente mais eficiente sem contexto acumulado de sessao anterior)

**Implicacoes para o sistema**:
- 600s timeout e adequado para tasks simples (T001-T013 todas <3min), mas pode ser insuficiente para tasks complexas late in the pipeline onde o contexto acumulado e grande
- **T018 tambem deu timeout** (15:09:59) — mesmo padrao de T015. O problema esta confirmado como sistematico para tasks de formatter.py que modificam um arquivo grande com contexto acumulado
- **Pattern confirmado** (2 datapoints — T015 e T018): tasks que modificam formatter.py timeoutam na primeira tentativa (~10 min), escrevem o arquivo antes de expirar, e completam rapido no retry (~3-5 min) porque encontram o arquivo ja escrito
- **Sugestao**: Timeout por task baseado na posicao no pipeline — tasks com index > 12 (ou context acumulado > 1M tokens) deveriam ter timeout maior (ex: 900-1200s)
- Alternativa: Resumo mais agressivo dos prior task summaries no prompt de cada task (truncar a 100 tokens por task anterior, nao incluir `files` completos)
- Observacao sobre `--resume`: T015 tentativa 1 usou `--resume 07725f55-454` e falhou. Tentativas seguintes sem resume tambem falharam mas foram mais curtas. **Hipotese**: a sessao resumida carrega contexto de ferramentas externas (file reads, prior edits) que aumenta o tempo de processamento interno do modelo, mesmo que o prompt de input seja similar

## Observacoes — INCIDENTE: Circuit Breaker + Context Window [16:52 BRT]

### Resumo do incidente
**O que aconteceu**: T031 falhou 4 vezes com `exitcode 1` (crash em 3-6s), nao timeout. Circuit breaker abriu apos T031+T032 exaustirem retries. T031-T046 (16 tasks) todas falharam. O implement encerrou com `status=failed`.

**Root cause**: Context window esgotado. Por T031 (31a task), o prompt acumulava summaries de T001-T030 + captured fixtures (26 pares JSON/YAML) + formatter.py completo. O subprocess claude morria imediatamente (5-6s) ao tentar processar o contexto — provavelmente a API rejeitava com erro de context limit.

**Evidencia**: Tentativas de T031 duravam 3-6 segundos. Um timeout levaria 600s. A diferenca e exatamente o comportamento de context window exceeded vs lentidao.

**Cascade**: Circuit breaker persiste no DB apos o epic falhar. Quando o daemon tentou dispatchar o proximo epic (madruga-ai/024-sequential-execution-ux) 32 segundos depois, o circuit breaker ainda estava OPEN e bloqueou o epic 024 imediatamente. **Dois epics afetados** por um unico evento de context overflow.

### Tasks nao implementadas (impacto real)
**Critico** (core do multi-tenant pipeline nao funciona sem estas):
- **T031** — `webhooks.py`: rewrite do handler para pipeline multi-tenant completo (still single-tenant HMAC)
- **T032** — `main.py`: `_make_flush_callback` com resolucao de tenant
- **T033** — `main.py`: startup loading TenantStore + `app.state.tenant_store`
- **T039** — `observability/setup.py`: remover `tenant_id` do Resource.create

**Importante** (testes e validacao):
- T034-T036: integration tests para idempotencia, debounce, webhook multi-tenant
- T037-T038: router.py tests, `append_or_immediate` test

**Auxiliar** (documentacao e lint):
- T040: verify `SpanAttributes.TENANT_ID` preserved (conventions.py UNCHANGED)
- T041: verify `tenant_id` removido de config.py (ja feito em T005, apenas verificacao)
- T042: README.md update
- T043: `ruff check/format`
- T044-T046: pytest, quickstart validation, E2E real

### Implicacoes sistemicas

**1. Context window budget nao e gerenciado**
O sistema acumula todos os summaries anteriores no prompt de cada task. Com 30+ tasks e captured fixtures pesadas (T014 = 2.8M tokens), o orçamento de context do modelo foi esgotado. **Nenhuma task de T031+ conseguia iniciar**.

**2. Sugestao de correcao**: rolling window no context de tasks
- Manter apenas os ultimos N tasks (ex: ultimos 5) no "Prior Tasks Completed" do prompt
- OU sumarizar os tasks anteriores em blocos (ex: "Tasks T001-T010 done: [100 palavra resumo]")
- OU usar context compression: o claude subprocess poderia receber apenas o diff de cada task (quais arquivos foram modificados, nao o conteudo completo)

**3. Circuit breaker precisa de TTL automatico post-epic**
O circuit breaker persistindo no DB e correto para epics que continuam. Mas quando um epic encerra com `status=failed`, o circuit breaker deveria ser resetado para o **proximo epic diferente** na fila. Atualmente, a persistencia do estado bloqueou o epic 024 do madruga-ai sem relacao com a causa da falha do 003.

**Sugestao**: circuit breaker com scope `epic_id` — nao persistir entre epics diferentes.

**4. O que o implement entregou (30/46 tasks)**
Apesar do incidente, 30 das 46 tasks foram implementadas com alta qualidade:
- Core multi-tenant: tenant.py, tenant_store.py, idempotency.py ✅
- Auth: dependencies.py rewrite (HMAC → X-Webhook-Secret) ✅
- Config: config.py refactor (7 campos removidos) ✅
- Formatter: ParsedMessage 22+ campos, message type names corretos, sender resolution, group events, mentions, replies, reactions, unknown field handling ✅
- Tests: conftest, test_tenant, test_tenant_store, test_idempotency, test_auth, test_captured_fixtures, test_formatter, test_debounce (parcial), test_router (parcial) ✅
- Router: route_message(msg, tenant) com 3-strategy mention detection ✅
- Debounce: tenant-prefixed keys buf:{tenant_id}:{sender_key}:{ctx} ✅

**O que falta para o sistema funcionar**: webhooks.py rewrite (T031) + main.py startup (T033). Sem estes, o servidor sobe mas routes webhook ainda usam o antigo handler single-tenant.

## Proximas observacoes

Vou continuar monitorando:
1. Quando `plan.md` for finalizado (esperado: nas proximas 5-15 min), validar se o template foi substituido
2. `tasks.md` — vai refletir as tasks T0-T21 + T6b-T6j + T11b-T11f do pitch ou vai regenerar do zero a partir do spec?
3. `analyze` (pre-implement) — consistency check spec vs plan vs tasks
4. `implement` — node mais critico, espero bastante atividade no worktree
5. `judge` — review por 4 personas, vai flagar multi-tenant concerns?
6. `qa` — rodar fixtures reais captured, vai bater 26 testes parametricos?
7. `reconcile` — vai encontrar drift de documentacao?

---

### 10. Qualidade do codigo gerado (worktree)

#### T001-T003 (avaliados antes)
- **tenant.py** (39 LOC): frozen dataclass, slots=True, 9 campos corretos, docstring alinhada com data-model.md. Zero bloat.
- **tenant_store.py** (183 LOC): loader com regex `${ENV_VAR}`, safe_load YAML, validacao duplicates + empty fields, O(1) lookup via `_by_id`/`_by_instance` dicts, type coercion `list→tuple` para keywords. Pragmatic `# type: ignore[arg-type]` no `enabled`.
- **pyproject.toml**: pyyaml adicionado como dependency.

**Gap menor**: data-model.md pede `mention_phone >= 10 chars` validation, mas tenant_store.py nao verifica comprimento. Nao e critico mas e um finding do analyze-report potencial.

#### T004 — tenants.example.yaml
- 80 LOC com comentarios extremamente ricos: curl command completo para configurar webhook no Evolution, instrucoes de como descobrir `mention_lid_opaque`, convencao de naming dos env vars (`pace-internal` → `PACE_INTERNAL_*`), comando python para gerar secrets.
- `${ENV_VAR}` placeholders para campos sensiveis, campos sem segredos (URLs, numeros de telefone) hardcoded diretamente (correto — nao sao secrets).
- **FINDING**: `mention_lid_opaque` do ResenhAI usa `${RESENHA_MENTION_LID_OPAQUE}` (value ainda desconhecido). Correto — o template reflete realidade.

#### T005 — config.py
- Refactor limpo: removidos 7 campos tenant-specific, adicionados `tenants_config_path` e `idempotency_ttl_seconds`.
- Detalhe excelente: `extra="ignore"` com comentario explicando que `.env` carrega vars `PACE_*`/`RESENHA_*` consumidas pelo TenantStore, nao por esta classe. Previne pydantic-settings de rejeitar env vars validas.
- Port default permanece 8050 (correto — 002 mudou de 8040 para 8050).

#### T006 — idempotency.py
- 71 LOC, logica perfeita: `seen:{tenant_id}:{message_id}` como key format (tenant-namespaced).
- `SET NX EX` atomico, `result is not None` (correto — SET NX retorna `True` em sucesso, `None` se key existe).
- Fail-open implementado corretamente: `except RedisError` loga warning e retorna `True` para processar a mensagem.

**Observacao geral**: o codigo segue o estilo do 001 (formatacao, imports, docstrings) — consistencia com a codebase existente. Nenhum boilerplate desnecessario. Baseline: ~1.3-2.2 min/task para tasks simples (T001-T006 sao todas novas criações/refactors simples).

## Pipeline timing baseline ate agora

| Node | Duracao | Custo observado |
|------|---------|-----------------|
| epic-context | manual | pitch.md (555 LOC) + decisions.md (29 LOC) |
| specify | 3m 21s | spec.md (273 LOC) — 6 user stories, Given/When/Then completo |
| clarify | 2m 22s | spec.md intocado (mesmo hash — nada a clarificar) |
| plan | 8m 36s | plan.md (441 LOC) + research (182) + data-model (410) + quickstart (174) + contracts (243) + checklists (37) = ~1487 LOC |
| tasks | 3m 44s | tasks.md (359 LOC, 46 tasks) |
| analyze | 3m 32s | analyze-report.md (14 findings + coverage matrix) |
| implement | em andamento | T001-T006 done (~2 min/task avg), T007 em andamento. 40/46 tasks pending. |

**Total pre-implement**: ~22 min (specify → analyze). O pipeline de planejamento e ~22 min para ~2100 LOC de artefatos — impressionante.

**Ultima atualizacao**: 17:30 BRT (T031 re-rodou com sucesso pos fixes, T032 em andamento)

## INCIDENTE + POSTMORTEM: T031-T046 cascade + bug 024 auto-dispatch [17:30 BRT]

### Sintomas observados
- T030 completou 18:56 UTC. T031 comecou 19:00 UTC resumindo sessao 239d8134 da US3.
- T031 primeira tentativa: rodou 3m8s e crashou com `exitcode 1` e stderr vazio.
- T031 retries 1-3 (sem `--resume`): crashes em 5-6 segundos cada, exitcode 1, stderr vazio.
- Mesma coisa para T032.
- Circuit breaker abriu apos 5 falhas consecutivas (CB_MAX_FAILURES=5).
- T033-T046: todas falharam com `circuit breaker OPEN` (14 tasks nao tentadas).
- Easter re-dispachou o epic 003 ~22 vezes entre 19:23 e 19:58 UTC, sempre batendo no CB.
- 30 segundos apos 003 terminar em failed, dispatched madruga-ai/024 — mas 024 era supostamente draft!

### 5 bugs encontrados (em cascata)

**Bug 1 — Session resume sem limite** (`dag_executor.py` `run_implement_tasks`)
`--resume` do claude CLI acumula tool-outputs entre tasks da mesma US. Dentro de US3 (T019-T030 — 12 tasks), o contexto da sessao resumida cresceu ate estourar o limite de 1M tokens do Claude Opus 4.6 [1m]. T017 sozinho ja bateu 3.19M tokens in (majoritariamente cache reads). T031 tentou resumir uma sessao ja saturada → crash na chamada a API.

**Bug 2 — Circuit breaker se auto-alimenta** (`dag_executor.py` `_seed_from_db`)
A funcao `_seed_from_db` contava TODAS as falhas recentes, inclusive as que o proprio CB bloqueou (`error='circuit breaker OPEN'`). Como cada dispatch bloqueado insere uma nova row `failed`, o seed via cada novo `open`, deixando o breaker permanentemente aberto. Cada re-dispatch do epic so fazia o CB se auto-realimentar.

**Bug 3 — Erros sem diagnostico** (`dag_executor.py` `dispatch_node_async`)
Quando `claude -p --output-format json` falha, o erro vem no stdout como `{"is_error": true, "subtype": "...", "result": "..."}` — nao vai para stderr. O codigo antigo so lia stderr: vazio → gravava `"exitcode 1"` sem contexto. Perdeu-se completamente o tipo real do erro (context overflow? rate limit? max_turns?).

**Bug 4 — Easter re-dispachava infinitamente** (`easter.py` `dag_scheduler`)
`poll_active_epics` so olha `status='in_progress'`. Um epic que falhar continua sendo re-dispachado a cada 15s (+ 30s cooldown) ate o usuario marcar manualmente como `blocked`. Nao havia contador de falhas consecutivas por epic → retry storm.

**Bug 5 — `upsert_epic` clobbers status em partial upsert** (`db_pipeline.py` `upsert_epic`)
Quando o caller nao passava `status`, `kwargs.get("status", "proposed")` defaultava para `"proposed"`, e o SQL `ON CONFLICT DO UPDATE SET status = excluded.status` sobrescrevia o valor existente. **Isso explica porque 024 foi auto-dispachado mesmo criado como `--draft`:**

1. User criou `/epic-context --draft madruga-ai 024` na branch `epic/prosauai/003`.
2. Skill escreveu `pitch.md` com `status: drafted`.
3. Primeira chamada a `post_save.py` inseriu 024 com `status=drafted`.
4. Segunda chamada (para `decisions.md`) disparou o auto-branch-name fallback em `post_save.py` linha 435-436: `upsert_epic(txn, platform, epic, title=..., branch_name=_current_branch)` — sem passar `status`.
5. Bug 5 clobbers `drafted` → `proposed`. E `_current_branch` era `epic/prosauai/003-multi-tenant-foundation` (branch do epic vizinho). Resultado: 024 ficou com `status=proposed` + `branch_name=epic/prosauai/003-multi-tenant-foundation` — duplamente errado.
6. O backfill marcou o node `epic-context` como `done` no 024.
7. `compute_epic_status(current='proposed', completed_ids={'epic-context'})` promoveu `proposed → in_progress` (linha 853 de `db_pipeline.py`).
8. Easter viu `status='in_progress'` → dispatched 024 → `specify` falhou porque a branch estava errada.

Reproduzi o bug 5 em teste unitario:
```python
upsert_epic(conn, 'p1', 'e1', status='in_progress')  # DB: in_progress
upsert_epic(conn, 'p1', 'e1', branch_name='epic/p1/e1')  # DB: proposed (clobbered!)
```

### Fixes aplicados (commit nesta branch)

1. **`dag_executor.py` `_seed_from_db`** — exclui rows com `error LIKE '%circuit breaker%'` do seeding. CB nao se auto-alimenta mais.

2. **`dag_executor.py` `_extract_claude_error`** — nova funcao que parseia o stdout JSON do claude CLI para extrair `is_error`, `subtype`, `result`/`error`. Agora falhas sao diagnosticadas com mensagens como `claude_error[error_during_execution: ...]` em vez de `exitcode 1`.

3. **`dag_executor.py` `run_implement_tasks`** — bounds de session-resume:
   - `SESSION_RESUME_MAX_TASKS=8` (default): maximo de 8 tasks consecutivas na mesma sessao claude.
   - `SESSION_RESUME_MAX_TOKENS=700000`: reset forcado se a task anterior usou > 700K tokens in.
   - Contador `resume_chain_length` tracked em memoria.
   - Log explicito: `"Session-resume bound tripped for T0XX (chain_len=8>=8) — forcing fresh session"`.

4. **`dag_executor.py` `run_implement_tasks`** — early-abort:
   - `IMPLEMENT_MAX_CONSECUTIVE_FAILURES=3`: para o batch apos 3 task failures consecutivas em vez de plow pelos 46 tasks.
   - Economia: antes desperdicava ~60s (cooldowns + retries) por task remanescente.

5. **`easter.py` `dag_scheduler`** — epic retry limit:
   - `_epic_fail_counts` dict em memoria por epic_id.
   - `MAX_EPIC_DISPATCH_FAILURES=3`: apos 3 falhas consecutivas no mesmo epic, marca `status='blocked'` no DB.
   - Notificacao ntfy + log `"epic_auto_blocked"`.
   - Sai do retry storm: usuario precisa investigar e manualmente marcar `in_progress` de novo.

6. **`db_pipeline.py` `upsert_epic`** — preserva status em partial upsert:
   - Usa sentinel `_UPSERT_EPIC_STATUS_UNSET`.
   - Se `status` nao eh passado, faz UPDATE explicito que NAO toca na coluna status.
   - Unit test confirma: `drafted → branch_name upsert → drafted` (preservado).

7. **`post_save.py` linha 435-436** — deriva branch_name do epic_id:
   - Prefere `f"epic/{platform}/{epic}"` ao git HEAD (evita cross-epic contamination).
   - So auto-materializa branch_name quando o epic esta `in_progress` — `drafted` continua com `branch_name=NULL`.
   - Passa `status=current["status"]` explicitamente quando chama `upsert_epic` (defense-in-depth).

### Reset + re-dispatch

- Deletadas 35 pipeline_runs do 024, status revertido para `drafted`, branch_name limpo.
- Deletadas 560 failed rows de 003 (T031-T046 + CB echoes). T001-T030 preservadas.
- Easter reiniciado (systemctl --user restart madruga-easter).
- **T031 re-rodou em 170s (2m50s) e completou com sucesso** com o novo codigo.
- `webhooks.py` agora tem 7284 bytes com pipeline multi-tenant completo (T031 + `resolve_tenant_and_authenticate`, tracer, tenant_id em spans, debounce com tenant_id, structlog contextvars).
- T032 (main.py) em andamento.

### Metricas do retry storm (antes do fix)

| Metrica | Valor |
|---------|-------|
| Tasks reais falhadas | 5 (T031-T035) |
| Retries por task | 4 (atempt + 3 backoff retries) |
| Re-dispatches do epic completo | 22 |
| pipeline_runs rows failed geradas | ~600 |
| Tokens gastos em crashes puros | dificil estimar — provavel > 10M tokens in em cache reads + writes parciais |
| Tempo perdido | ~1h entre primeiro crash e deteccao manual |
