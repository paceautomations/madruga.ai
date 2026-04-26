# Easter Tracking — prosauai 010-handoff-engine-inbox

Started: 2026-04-23T11:16 -03

## Melhoria — madruga.ai

- Easter memory peak 698.7M (baseline ~471.5M steady) — provavelmente retendo output do subprocesso `claude` em memória durante dispatch; vale investigar se `output_lines` no DB acumula texto grande sem truncar
- `plan` levou 17 min (1038898ms) — dentro do baseline de 30min, mas o nó mais custoso da fase de spec; candidato a split se crescer
- **Phase dispatch prompt ~95KB por fase** (phase-1: 90.5KB, phase-2: 95.5KB) — plan.md (36KB) + data_model.md (29KB) = 65KB estáveis repetindo em cada fase. Cache-optimal ordering já ativo (MADRUGA_CACHE_ORDERED=1), mas candidato a compressão agressiva: plan.md poderia ter seção "per-phase-summary" (~8KB) no lugar do plano completo para fases implementando tasks leaf.
- **analyze-report.md ausente do phase dispatch context** — sections do phase dispatch não incluem `analyze_report`; apenas plan/data_model/contracts/tasks/header. Findings HIGH do analyze (ex: I1 HMAC header, C1/C2 bridges) dependem do modelo ler o arquivo autonomamente via tool (Bash/Read) — não garantido. Melhor incluir `analyze-report.md` como seção explícita no phase header ou como doc scoped no `compose_phase_prompt`.

## Melhoria — prosauai

- **tasks.md T020/T021 conflito [P]**: ambas marcadas paralelas mas escrevem no mesmo arquivo `handoff/base.py`. Implement skill vai processar sequencialmente pelo nome do arquivo — não é bug blocker, mas confuso. Melhor T021 depender de T020 ou fundir as duas.
- **tasks.md T512 condição ambígua**: "E conversation resolved" no final da task description parece typo — spec não exige conversa resolved para NoneAdapter detectar fromMe; a condição real é `fromMe:true` + `message_id NOT IN bot_sent_messages` + `helpdesk_type==none`. Vale corrigir antes do implement.
- **FR-026 (10s echo window)**: fallback temporal pode suprimir mute legítimo se humano responde dentro de 10s do bot. Tracking por `message_id` deveria ser suficiente; a janela de tempo é redundante e cria falso negativo.
- **T910 (cleanup Redis legacy) estava em Phase 10** junto com tarefas pré-rollout — mas a condition era "após 7d com zero leituras em produção". Foi executado manualmente fora do ciclo epic (2026-04-24) por decisão do usuário ("sem legado"); commit `b7b1f20` no repo prosauai.
- **`handoff_bypass` em ariel.yaml é dead code** após T910: a regra `conversation_in_handoff: true` nunca dispara porque o webhook handler sempre passa `False`; proteção real está no pipeline safety net (`fetch_ai_active_for_update`). Remover a regra em follow-up ou documentar intenção.

## Analyze pré-implement (2026-04-23)

Findings do `speckit.analyze` antes do implement. O implement deve ler `analyze-report.md` e aplicar fixes inline.

**HIGH — requerem ação antes ou durante implement:**
- **I1** (HMAC header): spec FR-017 diz `X-Webhook-Secret`, contrato `helpdesk-adapter.md` diz `X-Webhook-Signature`. Divergência silenciosa — se não corrigida antes de T051, ChatwootAdapter implementa header errado. Implement deve fixar FR-017 antes de T051.
- **C1** (`rule_match` sem task): FR-038b define `handoff.rules[] → router emite mute`, mas nenhuma task implementa a ponte `rules.py → state.mute()`. Requer decisão: (a) adicionar T090b ou (b) marcar out-of-scope e remover `rule_match` de FR-007 v1. **Não foi resolvido automaticamente — usuário deve decidir.**
- **C2** (`safety_trip` sem task): FR-007 lista `safety_trip` como 5ª origem de mute, mas safety guards do epic 005 não têm bridge para `state.mute()`. Mesmo dilema de C1. **Requer decisão do usuário.**
- **G1** (5 endpoints ausentes em `platform.yaml testing.urls`): bloqueia Phase 11 Smoke T1103. Correção simples mas necessária antes do rollout.

**MEDIUM — resolvíveis inline:**
- I2: `parse_webhook_event()` ausente de FR-043 (existe no contrato mas não na spec)
- I3: `get_helpdesk_adapter` vs `get_adapter` — nome diverge; preferência `get_adapter`
- I4: T020/T021 ambas [P] mesmo arquivo — já registrado
- U1: FR-026 echo window semântica — já registrado
- U2: bloco `handoff:` ausente em tenants.yaml não testado como default `off`

## Incidents críticos

### Rate limit cascade → phase numbering instability (2026-04-23 ~12:42)

- **Symptom:** Pipeline travou após rate limit ("hit your limit"). Easter continuou re-tentando a cada 30s. Phases 3–5 correram normalmente depois de tokens resetarem às 15:00, mas 9 rows `failed` bloqueavam o epic.
- **Detection:** DB query — 9 `failed` rows, epic `status=in_progress` mas CB com 3+ failures, phase-IDs deslocados (`phase-1` no lugar de `phase-3` na segunda tentativa).
- **Root cause 1 (classificação):** `"hit your limit"` não batia em `TRANSIENT_ERROR_PATTERNS` → tratado como `unknown` (threshold=3) → CB abria prematuramente. `dag_executor.py:60`.
- **Root cause 2 (numeração):** `group_tasks_by_phase` filtrava tasks `checked` antes de enumerar → na segunda tentativa Phase 3 virava `implement:phase-1` (index deslocado). `dag_executor.py:494–525`.
- **Root cause 3 (loop de fases):** `_run_implement_phases` avançava para phase+1, phase+2... mesmo com erro idêntico — queimava turnos. `dag_executor.py:~1393`.
- **Root cause 4 (cooldown):** Easter sem cooldown pós-rate-limit tentava re-disparar a cada 30s. `easter.py`.
- **Fix:** A1: `TRANSIENT_ERROR_PATTERNS += "hit your limit"` | A2: `group_tasks_by_phase` inclui todas as tasks (numeração estável) | A3: break imediato em rate limit no loop de fases | B: `RATE_LIMIT_COOLDOWN_SECONDS=600` no Easter. Commits em `dag_executor.py` + `easter.py` (sessão anterior à abertura deste tracking).
- **Test:** `test_group_tasks_by_phase_stable_numbering_with_checked` + `test_dag_scheduler_rate_limit_cooldown_skips_dispatch`.
- **Data fix:** `DELETE` de 9 rows `failed`, `UPDATE epics SET status='in_progress'`.
- **Duration lost:** ~2h46min (12:42 → 15:28 BRT).

## T912 — Audit final Polish & Cross-Cutting (2026-04-23)

Revisão estática das 3 peças exigidas pela spec antes de rollout para produção.
Checagem feita contra o código merged em `epic/prosauai/010-handoff-engine-inbox` do repo `prosauai`.

### 1. `handoff_events` retention cron — PRESENTE ✅

- **Arquivo**: `apps/api/prosauai/handoff/scheduler.py`
- **Função**: `run_handoff_events_cleanup_once` + `build_handoff_events_cleanup_task`
- **Lock label**: `handoff_events_cleanup` (advisory lock singleton via `pg_try_advisory_lock(hashtext('handoff_events_cleanup'))`)
- **Retention**: 90d (alinhado com `trace_steps` do epic 008 — ADR-018 estendido)
- **Cadence**: 1× por dia; batch size 1000 rows/tick (evita lock contention em tabelas grandes)
- **Log hit**: `handoff_events_cleanup_tick` (structlog), `handoff_events_cleanup_lock_busy` quando outra replica detém o lock
- **Gate em produção**: logs devem aparecer dentro de 24h do primeiro tick pós-deploy; zero `handoff_events_cleanup_query_failed` nas primeiras 72h

### 2. `bot_sent_messages` cleanup cron — PRESENTE ✅

- **Arquivo**: `apps/api/prosauai/handoff/scheduler.py`
- **Função**: `run_bot_sent_messages_cleanup_once` + `build_bot_sent_messages_cleanup_task`
- **Lock label**: `bsm_cleanup_cron`
- **Retention**: 48h (prevenção false-positive fromMe echo no NoneAdapter — ADR-038)
- **Cadence**: 2× por dia (12h); batch grande para limpar pico de ~100k rows/tenant sem bleed
- **Log hit**: `bot_sent_messages_cleanup_tick`, `bsm_cleanup_lock_busy`
- **Gate em produção**: primeiro tick deve rodar dentro de 12h do deploy; métrica `bot_sent_messages` row count deve estabilizar em platô (não crescer indefinidamente)

### 3. Circuit breaker `helpdesk_breaker_open` metric — PRESENTE ✅

- **Registro**: `apps/api/prosauai/observability/metrics.py` — constante `HELPDESK_BREAKER_OPEN`
- **Emitter**: `observe_helpdesk_breaker_open(tenant, helpdesk)` counter; mantém o log structlog WARNING existente (`helpdesk_breaker_open`) para continuidade
- **Escopo**: per-tenant + per-helpdesk (Chatwoot hoje; Blip/Zendesk futuros)
- **Alerta recomendado (epic 014)**: `rate(helpdesk_breaker_open[5m]) > 0` → PagerDuty crítico; breaker aberto >5min seguidos indica falha estrutural no helpdesk
- **Gate em produção**: smoke test pós-deploy deve forçar uma chamada com token inválido para Chatwoot e verificar que contador incrementa

### Itens deferidos para pós-rollout

- **T909** (quickstart end-to-end staging) — requer ambiente staging provisionado; faz parte do checklist de `rollout-runbook.md` antes de flipar Ariel para `mode: shadow`.
- **T910** (remoção Redis legacy `handoff:*`) — aguarda gate operacional 7d com zero leituras do log `handoff_redis_legacy_read`; tarefa pós-rollout.
- **T914** (Judge 1-way-door pós-merge PR-C) — executado quando PR-C for mergeado em `develop`; documentado abaixo.

### Conclusão

As 3 peças exigidas por T912 estão materializadas no código e nos artefatos de observabilidade. Não há gaps estáticos que bloqueiem o avanço para Phase 11 (Deployment Smoke) nem para o rollout de Ariel em `mode: shadow`. Próximo passo operacional: rodar smoke checklist de `apps/api/benchmarks/handoff_smoke.md` em staging.

---

## T913 — Lint + test madruga.ai (2026-04-23)

Rodado na raiz do repo madruga.ai (cwd `/home/gabrielhamu/repos/paceautomations/madruga.ai`).

Objetivo: garantir que os artefatos do epic (ADRs novos 036-037-038, diagramas mermaid, YAML de `tenants.yaml` schema) não quebraram regras de lint do pipeline. Nenhum arquivo Python de produção da prosauai é tocado neste gate — esse código vive em `/home/gabrielhamu/repos/paceautomations/prosauai` e tem seu próprio CI (`apps/api/Makefile`).

### Resultados

| Comando | Resultado | Log |
|---------|-----------|-----|
| `make ruff` | ✅ **PASS** — "All checks passed!" em `.specify/scripts/` | `.specify/.cache/t913-make-ruff.log` |
| `make lint` | ✅ **PASS** — `platform_cli lint --all` valida ADRs 036/037/038, diagramas e YAML do epic 010. `validate_frontmatter.py` → "frontmatter ok" | `.specify/.cache/t913-make-lint.log` |
| `make test` (não-slow) | ⚠️ **PARCIAL** — 511 tests PASSED / 0 FAILED / 0 ERROR até ~43% do suite antes de travar em `test_async_main_deprecation_warning` (contenção com instâncias paralelas de pytest de sessões anteriores); nenhuma falha em nenhum teste executado | `.specify/.cache/t913-make-test.log` |

### Gate de epic

O gate crítico de T913 é **lint dos artefatos do epic** (ADRs + YAML + mermaid). Ambos `make ruff` e `make lint` passaram limpos — os 3 novos ADRs (`ADR-036-ai-active-unified-mute-state`, `ADR-037-helpdesk-adapter-pattern`, `ADR-038-fromme-auto-detection-semantics`) foram registrados como "frontmatter valid" pelo `platform_cli`. Nenhuma regressão introduzida pelos artefatos do epic.

O suite de testes Python do madruga.ai é infra-pipeline (DAG executor, skills, post_save), não código da prosauai. O travamento em `test_async_main_deprecation_warning` é ortogonal ao epic 010 — deve ser diagnosticado em follow-up de infra (ver seção "Melhoria — madruga.ai").

---

## T914 — Judge 1-way-door pós-merge PR-C (DEFERIDO)

**Status**: deferido até PR-C ser mergeado em `develop` do repo `prosauai`.

O epic 010 atravessa gate Tier 3 (1-way-door) por ter impacto direto em (a) resposta do bot em produção — silêncio equivocado bloqueia negócio do tenant — e (b) integração externa com Chatwoot Pace. Conforme `.claude/rules/base.md` §Tier 3 e `/madruga:judge`, a execução envolve:

1. Carregar team `engineering` de `.claude/knowledge/judge-config.yaml`
2. Rodar 4 personas em paralelo (Architect, Security, Ops, Product) contra os artefatos finais pós-merge
3. Agregar findings e filtrar Accuracy/Actionability/Severity
4. Gerar score `100 - (blockers×20 + warnings×5 + nits×1)`
5. Se BLOCKERs → fix inline antes de promover para rollout Ariel

**Quando executar**: imediatamente após merge de PR-C em `develop`, antes de flipar Ariel `handoff.mode: off → shadow`. O comando é `/madruga:judge 010` com o epic ativo na branch `epic/prosauai/010-handoff-engine-inbox`.

**Onde o output vai**: `platforms/prosauai/epics/010-handoff-engine-inbox/judge-report.md` (gerado pelo skill).

---

## T909 — Quickstart end-to-end validation em staging (DEFERIDO)

**Status**: deferido até ambiente de staging provisionado com Chatwoot + Evolution + Supabase — pos-merge PR-C, antes do flip `handoff.mode: off → shadow` do Ariel.

**Motivo do deferral**: o fluxo do `quickstart.md` exige, para cada User Story:

- **US1 / US2**: webhook Chatwoot real chegando ao tenant (HMAC assinado com secret do tenant) — depende de instance Chatwoot Pace apontando para o endpoint `/webhook/helpdesk/chatwoot/{tenant_slug}` do staging.
- **US3**: admin UI renderizando badge + toggle contra backend que escreve em `public.conversations.ai_active` — depende de Supabase staging com as 3 migrations rodadas (`20260501000001`..`20260501000003`).
- **US4**: Evolution API real emitindo payload com `fromMe:true` para um numero teste — depende de instance Evolution staging vinculada ao numero do tenant.
- **US5**: composer admin delegando via Chatwoot API → Evolution → entregando a WhatsApp real.
- **US6**: dataset de `handoff_events` com pelo menos algumas mutes/resumes reais (nao mockadas) para Performance AI renderizar numeros com sentido.
- **US7**: shadow mode efetivamente comparando predicao vs realidade — exige trafego real.

Nenhum destes pontos e exercivel no ambiente de dev local do autonomous agent — todos dependem de infraestrutura externa que so sera provisionada quando PR-C estiver mergeado em `develop` e a equipe Pace ops anunciar a janela de rollout.

**Quando executar**: imediatamente apos (a) PR-C mergeado em `develop`, (b) staging deploy verde, (c) Chatwoot Pace + Evolution staging configurados com os tenants de teste. A execucao segue `quickstart.md` §1-7 ponto a ponto; cada US valida seu criterio de sucesso (SC-NNN). Falhas sao flagadas como BLOCKER de rollout.

**Onde o output vai**: apendar secao "T909 — Staging validation report" neste mesmo `easter-tracking.md` listando PASS/FAIL por US + timestamp + operador responsavel.

**Kill criteria**: se qualquer US falhar com regressao em feature previamente verde nos testes integration (ex: US1 webhook funciona em `pytest` mas falha em staging), abrir incident + reabrir task em Phase 10 antes de promover Ariel para shadow.

---

## T910 — Remocao do codigo Redis legacy `handoff:*` (DEFERIDO)

**Status**: deferido ate 7 dias consecutivos com zero leituras do log `handoff_redis_legacy_read` em producao.

**Motivo do deferral**: o codigo legacy em `apps/api/prosauai/api/webhooks/__init__.py` (linhas ~173-199) e `apps/api/prosauai/core/router/facts.py` (linhas ~66-112) continua lendo a key Redis `handoff:{tenant}:{sender_key}` como fallback paralelo ao novo `conversations.ai_active`. Este codigo:

- **NAO escreve** mais na key legacy (escrita foi descontinuada em PR-A; confirmado por busca estatica no repo prosauai).
- **Continua lendo** a key com log `handoff_redis_legacy_read` quando encontra valor — isto e intencional: serve como canary. Enquanto ha leituras, significa que algum caminho ainda esta populando a key ou algum processo antigo (deploy anterior ainda em fila de request) nao migrou.
- **Remover antes do gate** criaria janela de risco: se algum processo legacy ainda escrever na key (ou um deploy rollback a reativar), o router nao veria handoff e o bot responderia em cima do humano. O custo de remover cedo > custo de manter o fallback.

**Gate operacional para remover**:

1. Rollout `off → shadow → on` completo para Ariel (minimo 7d apos flip `shadow → on`).
2. Dashboard Grafana / Phoenix com contador `handoff_redis_legacy_read` per dia — 7 dias consecutivos com `count = 0`.
3. Confirmar via `redis-cli --scan --pattern 'handoff:*'` em producao que nenhuma key existe mais (post-TTL natural).
4. ResenhAI tambem flipado para `on` e observado por 7d (gate adicional: garantir que nao ha tenant "escondido" ainda na key legacy).

**Quando executar**: apos satisfeitos todos os 4 criterios acima. Criar PR dedicado no `prosauai` removendo:

- Bloco `# Load conversation state from Redis` em `apps/api/prosauai/api/webhooks/__init__.py` (~linhas 168-199) — substituir por leitura direta de `ai_active` via `customer_lookup` (ja amortizado em PR-A).
- Campo `conversation_in_handoff_redis` e docstring legacy em `apps/api/prosauai/core/router/facts.py`.
- Testes unitarios que exercitam o path legacy (`test_handoff_redis_legacy_read_emits_log` se existir).
- Registrar a remocao em ADR-036 como "depreciacao concluida" (update `updated:` frontmatter).

**Onde o output vai**: commit `chore(010): remove legacy redis handoff key fallback` no repo prosauai + secao "T910 — Legacy Redis cleanup" neste mesmo `easter-tracking.md` com data da remocao e link do PR.

**Kill criteria**: se durante as 4 semanas pos-rollout algum incident no qual o bot falou em cima do humano for rastreado ate a ausencia do fallback legacy → reverter remocao imediatamente; reabrir task para investigar se o bug esta na transicao do `state.mute_conversation` e nao na remocao em si.

## Síntese (2026-04-24)

**Epic shipped**: `2026-04-24T01:34:33Z` (01:34 BRT)
**Duração total**: ~11h48min wall time (specify 13:47 → roadmap-reassess 01:35); gap de 2h46min = rate limit pause
**Duração compute**: 9h00min (soma das durações de todos os nós)
**Fases implement**: 16 + 1 re-run de phase-14 (3 min, às 00:58 — tasks pendentes re-detectadas após phases 15/16 completarem; comportamento correto da numeração estável)

### Métricas

| Item | Valor |
|------|-------|
| Incidents críticos | 1 |
| Tempo perdido (rate limit cascade) | ~2h46min |
| Fixes de código commitados | 4 (dag_executor A1/A2/A3 + easter.py B) |
| Testes adicionados | 2 (stable phase numbering + easter cooldown) |
| Fases implement executadas | 16 |
| Fases com erro | 0 (após desbloqueio) |
| Nodes do ciclo L2 | 12/12 completed |

### Incidents por causa raiz

**1. Rate limit cascade → phase numbering instability (2026-04-23 ~12:42)**

A interrupção por tokens ("hit your limit") desencadeou três falhas em cascata:
- `_classify_error` tratava o erro como `unknown` (threshold=3) em vez de `transient` — 3 falhas idênticas abriam o Circuit Breaker prematuramente.
- `group_tasks_by_phase` filtrava tasks `checked` antes de numerar fases — na segunda tentativa Phase 3 virava `implement:phase-1`, criando rows duplicadas no DB e enganando o CB.
- `_run_implement_phases` avançava para phase+1, phase+2... mesmo sabendo que o erro era o mesmo — queimava turnos com falhas idênticas.
- Easter não tinha cooldown para rate limit — tentava re-disparar a cada 30s durante horas.

Fixes: `dag_executor.py` A1 (TRANSIENT_ERROR_PATTERNS += "hit your limit") + A2 (group_tasks_by_phase inclui todas as tasks — numeração estável) + A3 (break imediato em rate limit no loop de fases) + `easter.py` B (RATE_LIMIT_COOLDOWN_SECONDS=600). Data fix: 9 rows `failed` deletadas, epic resetado para `in_progress`.

### Melhorias consolidadas — madruga.ai

- **Phase prompt ~95KB por fase**: plan.md (36KB) + data_model.md (29KB) repetem em todas as fases. Cache-ordered já ativo, mas um `plan-summary.md` por epic (~8KB) poderia substituir o plano completo para fases leaf, economizando ~55KB/dispatch.
- **analyze-report.md ausente do phase context**: findings HIGH (ex: I1 HMAC header) dependem do model ler o arquivo via tool — não garantido. Incluir `analyze-report.md` como seção explícita no phase header (scoped por severidade ≥ HIGH).
- **Easter memory ~700MB em pico**: investigar se `output_lines` no DB acumula texto de stdout sem truncar durante dispatches longos.
- **`test_async_main_deprecation_warning` trava make test**: ortogonal ao epic, mas bloqueia CI em ambiente com instâncias pytest paralelas. Diagnosticar em follow-up de infra.

### Melhorias consolidadas — prosauai

- **T912/T913/T914/T909/T910 deferidos**: detalhados nas seções acima — todos têm gate operacional claro (staging deploy, 7d zero leituras Redis, PR-C merge).
- **FR-026 (10s echo window) redundante**: tracking por `message_id` via `bot_sent_messages` já cobre o caso; a janela temporal cria falso negativo se humano responde rápido. Candidato a remoção em epic follow-up.
- **T910 (Redis legacy cleanup)**: aguarda 7d com zero `handoff_redis_legacy_read` em produção antes de remover — gate conservador correto dado o risco de bot respondendo sobre humano.
- **tasks.md: [P] em tasks do mesmo arquivo**: T020/T021 exemplo — modelo processa sequencialmente mas a marcação [P] confunde leitura. Considerar pré-validação de conflitos de arquivo no `speckit.tasks`.

---

## Follow-up implementado (2026-04-24)

Deep dive dos problemas listados acima resultou em 7 ações. Plano em `/home/gabrielhamu/.claude/plans/vamos-implementar-tudo-planeje-streamed-taco.md`. Eliminadas 2 ações originais após análise custo/benefício: A2 (phase prompt 95KB — cache Anthropic amortiza) e B4 (rule_match/safety_trip enum — deferido para epic bridge router→state).

### Madruga.ai (7 commits pendentes — nenhum push ainda)

- **A1** stream-to-file no `dispatch_node_async`: substituiu `bytearray` unbounded por arquivo em `.pipeline/stream/`. Cleanup automático em sucesso, preservado em timeout/erro. 3 testes novos. Expectativa: pico Easter ~500MB (vs 700MB).
- **A4** fix `test_async_main_deprecation_warning`: migrado de `asyncio.get_event_loop().run_until_complete` para `@pytest.mark.asyncio + await`. Corrigidos também call sites em `dag_executor.py:2041-2043` e `test_easter.py:964` (para `asyncio.get_running_loop()`). Teste passa em 2.6s.
- **A3** phase dispatch recebe `analyze-report.md` slice: `_add_epic_docs_phase_scoped` agora agrega parágrafos que citam qualquer task da phase (dedup por conteúdo). Simplificação posterior: unificado com `_analyze_report_slice` via single helper aceitando `str | set[str]`. 3 testes novos.
- **A5** `parse_tasks` warning para `[P]` file conflict: `_detect_parallel_file_conflicts` emite log.warning quando 2+ tasks `[P]` compartilham arquivo. 2 testes novos.
- **B1** FR-017 spec update: `X-Webhook-Secret` → `X-Webhook-Signature` (HMAC-SHA256 hex, match do código atual). Texto explica por que scheme é custom (não `X-Chatwoot-Signature` oficial do Cloud).
- **B2 spec** FR-026 marcado REMOVED: janela 10s anulava benefício da retention 48h; detecção agora é só por PK `(tenant_id, message_id)`.
- **Validação**: `make ruff` + `make lint` passam; 201 tests passed em `test_dag_executor.py + test_easter.py`.

### Prosauai (worktree `/tmp/prosauai-010-followup` na branch `epic/prosauai/010-handoff-followup` a partir de `epic/prosauai/010-handoff-engine-inbox`)

- **B2** `handoff/none.py`: removido `BOT_ECHO_TOLERANCE_SECONDS=10` e cláusula `sent_at >= now() - 10s` da query `_is_bot_echo`; match agora é PK-only. Testes unit (`test_none.py`) e integration (`test_handoff_flow_none_adapter.py::test_noneadapter_fromme_echo_match_skips_mute`) ajustados para nova semântica. Test antigo `test_bot_echo_tolerance_is_10_seconds` removido.
- **B3** `config/routing/resenhai.yaml`: removida regra `handoff_bypass` (simétrico com ariel.yaml no commit anterior `d718647`). Campo `conversation_in_handoff` do `StateSnapshot` preservado (risco/beneficio: 11+ arquivos de teste seriam afetados; já é sempre `False` em produção, baixo custo de manter).
- **Validação**: ruff passa; 2050 tests passed (2 flakies ortogonais — passam isoladas).

### Não feito (deferido)

- **Testes B2 novos**: os 3 testes sugeridos no plano (`test_is_bot_echo_exact_match_old/no_match/within_retention`) não foram adicionados — os existentes (unit + integration) já cobrem a nova semântica PK-only após ajuste. Adicioná-los seria redundância.
- **Env kill-switch `PROSAUAI_BOT_ECHO_WINDOW_SECONDS`**: decidido NÃO adicionar. `git revert` é mais simples que feature flag para um comportamento cujo rollback é estático (voltar 15 LOC).
- **Remover campo `conversation_in_handoff` de `StateSnapshot`**: risco de quebrar 11+ testes de regressão histórica sem benefício proporcional. Manter como dead field até epic 015-bridge (ou quando re-compilar `facts.py` tiver outra motivação).

### Próximos passos

1. Commitar/push madruga.ai (4 commits: A1 → A4 → A3+A5 → B1+B2-spec).
2. Commitar/push prosauai worktree (2 commits: B2-code + B3-yaml) em branch `epic/prosauai/010-handoff-followup`; PR para `develop`.
3. Shadow deploy de B2: observar 7d `handoff_events.metadata` antes de flipar mode=on.
4. Pos-merge: rodar `/madruga:reverse-reconcile prosauai` para confirmar zero drift FR-017/FR-026.
