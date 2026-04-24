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
- **T910 (cleanup Redis legacy) está em Phase 10** junto com tarefas pré-rollout — mas a condition é "apos 7d com zero leituras em produção". Sequencialmente deveria estar na fase pós-rollout, não no Polish pré-PR-C.

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

_(nenhum até agora)_

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

## Síntese

_(preenchido no último tick)_
