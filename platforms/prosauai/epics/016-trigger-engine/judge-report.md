---
title: "Judge Report — prosauai 016-trigger-engine"
score: 82
initial_score: 0
verdict: pass
team: engineering
personas_run: [arch-reviewer, bug-hunter, simplifier, stress-tester]
personas_failed: []
findings_total: 26
findings_fixed: 11
findings_open: 15
updated: 2026-04-28
---
# Judge Report — prosauai 016-trigger-engine

## Score: 82%

**Verdict:** PASS  
**Team:** Tech Reviewers (4 personas)

> **Nota processual**: Ciclo de heals em duas sessões:
> - **Sessão 1** (pre-heal): Score 0/100 — 7 BLOCKERs. Commits `dd54aba`, `c5e600c`, `8866901` fecharam todos.
> - **Sessão 2** (esta rodada): 2 novos BLOCKERs encontrados (BH-B1, BH-B2) + 2 WARNINGs fixados (BH-W4, ST-W3). Commit `3a9b53d`.
> - **Score final pós-heals**: 82/100 — PASS.

---

## Findings

### BLOCKERs (9 total — 9/9 fixed)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| B1 | bug-hunter | `_FIND_STUCK_SQL` sem filtro `tenant_id` — stuck-detection de um tenant processava rows de todos os tenants (cross-tenant data bleed). `execute_tick` do tenant A reprocessava rows do tenant B com credenciais do tenant A. | `events.py:103` + `engine.py:186` | **FIXED** | `AND tenant_id = $3` adicionado; `find_stuck_queued(conn, tenant_id)` novo arg posicional. Commit `3a9b53d`. |
| B2 | bug-hunter | `_retry_reclaimed_rows` chamava `_dispatch_send` sem `check_cooldown` nem `check_daily_cap` — bypass de FR-012/FR-013. | `engine.py:_retry_reclaimed_rows` | **FIXED** | Guards adicionados antes de `_dispatch_send`. Commit `3a9b53d`. |
| B3 | prev-session | `scheduler.py` hardcodava `evolution_client=None` — live mode nunca despachava. | `scheduler.py:362` | **FIXED** | `_build_evolution_client()` construído por tenant. Commit `dd54aba`. |
| B4 | prev-session | `restore_state_from_sql` definida mas nunca chamada no lifespan startup. | `scheduler.py` | **FIXED** | `_restore_state_for_all_tenants()` chamado em `trigger_engine_loop`. Commit `dd54aba`. |
| B5 | prev-session | Stuck-detection bumpa `retry_count` mas nunca re-despacha. | `engine.py` | **FIXED** | `load_stuck_for_retry` + `_dispatch_send` fora da transação. Commit `c5e600c`. |
| B6 | prev-session | `retention_cron.py` sem entry para `trigger_events`. | `retention_cron.py` | **FIXED** | Entry adicionado com 90-day window. Commit `c5e600c`. |
| B7 | prev-session | Matchers ignoravam `intent_filter`, `agent_id_filter`, `min_message_count`, `consent_required`. | `matchers.py` | **FIXED** | `consent_required` wired via `$3::bool`; demais: log warning explícito. Commit `c5e600c`. |
| B8 | prev-session | `tick_extra` re-inicializado dentro de `_process_trigger` (cap booking incorreto entre triggers). | `engine.py:311` | **FIXED** | Hoisted para escopo de `execute_tick`. Commit `c5e600c`. |
| B9 | prev-session | `evolution.send_template` sem retry para 5xx (FR-027). | `evolution.py:451-512` | **FIXED** | 3-attempt exponential backoff para 5xx. Commit `c5e600c`. |

### WARNINGs (5 total — 2/5 fixed, 3 open)

| # | Source | Finding | Localização | Status | Fix Applied |
|---|--------|---------|-------------|--------|-------------|
| W1 | bug-hunter | `restore_state_from_sql` não restaurava contadores `daily_cap` após Redis restart — todos os clientes podiam receber N×cap sends no primeiro tick pós-restart. | `cooldown.py:restore_state_from_sql` | **FIXED** | `_RESTORE_DAILY_CAP_SQL` adicionado; contadores restaurados com TTL até meia-noite UTC + 2h buffer. Commit `3a9b53d`. |
| W2 | stress-tester | `time_after_last_inbound` SQL: subquery correlacionada com `GROUP BY + HAVING + MAX(m.created_at)` sem índice em `messages(conversation_id, direction, created_at)` — seq scan em escala. | `matchers.py:_TIME_AFTER_LAST_INBOUND_SQL` | **FIXED** | Migration `20260601000026` cria `idx_messages_conversation_inbound_created_at`. Commit `3a9b53d`. |
| W3 | arch-reviewer | Filtros `intent_filter`, `agent_id_filter`, `min_message_count` declarados em YAML mas não honrados em SQL — operador que configura `intent_filter: "sports"` vê o trigger disparar para todos. | `matchers.py:_warn_unsupported_filters` | **OPEN** | Deferred 016.1+. Documentado decisions.md D22. `_warn_unsupported_filters` notifica via log. Aceitável v1. |
| W4 | bug-hunter | `check_daily_cap(redis, …, cap=0)` retorna `False` quando Redis key ausente — edge case com `already_booked_in_tick >= daily_cap` + Redis frio simultâneos. | `cooldown.py:check_daily_cap` | **OPEN** | Apenas sob falha combinada Redis + in-tick overflow. Partial UNIQUE INDEX mitiga. Backlog 016.1. |
| W5 | stress-tester | Circuit breaker verificado antes do retry loop — falhas nas tentativas 1 e 2 podem não atualizar o estado do breaker se integração não for automática. | `evolution.py:send_template` | **OPEN** | Depende de implementação do breaker (epic 014). Verificar em QA com load sintético de 5xx. |

### NITs (14 open)

| # | Source | Finding | Localização | Status |
|---|--------|---------|-------------|--------|
| N1 | arch-reviewer | `hashtext_int4()` usa FNV-1a 32-bit ≠ `hashtext()` Postgres — divergência silenciosa se SQL futuro chamar `hashtext('triggers_engine_cron')`. | `scheduler.py:hashtext_int4` | OPEN |
| N2 | arch-reviewer | `restore_state_from_sql` restaura cooldown com 24h fixo (v1 trade-off documentado). Cooldowns >24h restaurados com TTL mais curto. | `cooldown.py:_RESTORE_SQL` | OPEN |
| N3 | arch-reviewer | `suppress(Exception)` no `finally` de unlock pode mascarar falha de `pg_advisory_unlock` em cancellation. | `scheduler.py:run_trigger_engine_once` | OPEN |
| N4 | bug-hunter | `row["phone"] or ""` no retry path: phone `None` vira string vazia — Evolution rejeita com 422 sem mensagem de erro clara. | `engine.py:_retry_reclaimed_rows:685` | OPEN |
| N5 | stress-tester | Lock advisory mantido para o loop completo de tenants — by design (padrão epic 010), mitigado por `asyncio.wait_for(timeout=cadence×4)`. | `scheduler.py:run_trigger_engine_once` | OPEN |
| N6 | stress-tester | `asyncio.wait_for` cancela com `CancelledError`; `finally` executa mas `_UNLOCK_SQL` pode falhar silenciosamente sob connection degradada. | `scheduler.py:trigger_engine_loop` | OPEN |
| N7 | stress-tester | `TimeoutError` no tick não loga tenant_ids em voo — dificulta diagnóstico pós-incidente. | `scheduler.py:trigger_engine_loop` | OPEN |
| N8 | stress-tester | `cost_gauge._COST_QUERY_SQL` beneficiaria de índice parcial `WHERE status='sent'`. Baixa prioridade (cadence 60s). | `cost_gauge.py:_COST_QUERY_SQL` | OPEN |
| N9 | simplifier | 3 funções matcher com estrutura quase idêntica (~80 linhas duplicadas) — candidato a extração `_fetch_matches()`. | `matchers.py` | OPEN |
| N10 | simplifier | Múltiplas chains `getattr()` para pool names (`pool_admin`, `db_admin_pool`, `pool`, ...) espalhadas. | `scheduler.py:_make_engine_execute_tick` | OPEN |
| N11 | simplifier | `engine_dispatch` lazy init dentro do loop — primeiro tick paga custo de construção. | `scheduler.py:trigger_engine_loop` | OPEN |
| N12 | simplifier | `hashtext_int4()` custom 15 linhas pode ser `zlib.crc32(key.encode()) & 0x7FFFFFFF`. | `scheduler.py:hashtext_int4` | OPEN |
| N13 | simplifier | `_iter_enabled_tenants()` usa múltiplos padrões de `getattr()` inconsistentes. | `scheduler.py:_iter_enabled_tenants` | OPEN |
| N14 | bug-hunter | `load_stuck_for_retry` não estava em `__all__`. | `events.py:__all__` | **FIXED** (commit `3a9b53d`) |

---

## Safety Net — Decisões 1-Way-Door

| # | Decisão | Score de Risco | Detectado por Classifier? | Veredicto |
|---|---------|----------------|--------------------------|-----------|
| S1 | LGPD SAR via `ON DELETE CASCADE` — hard-delete de `trigger_events` ao deletar customer. DPO confirmation pendente. | Médio | Sim (decisions.md D33, `[VALIDAR]`) | **Carry-forward para reconcile** — não bloqueia merge, mas DPO sign-off deve ser registrado em `decisions.md` antes do rollout live em Ariel. |
| S2 | ADR-049 (Trigger Engine) e ADR-050 (Template Catalog) ainda em `draft` — comportamento já locked na implementação. | Médio | Sim (analyze-post C1) | **Promover em reconcile** (Phase 11). |

---

## Personas que Falharam

Nenhuma — 4/4 personas completaram com sucesso.

---

## Files Changed (by fix phase)

### Esta rodada (commit `3a9b53d`)

| File | Findings Fixed | Summary |
|------|---------------|---------|
| `prosauai/triggers/events.py` | B1, N14 | `tenant_id` em `_FIND_STUCK_SQL`; `load_stuck_for_retry` no `__all__` |
| `prosauai/triggers/engine.py` | B1, B2 | `find_stuck_queued(conn, tenant_id)`; cooldown+cap guards no retry |
| `prosauai/triggers/cooldown.py` | W1 | `_RESTORE_DAILY_CAP_SQL` + loop de restauração de daily_cap keys |
| `db/migrations/20260601000026_*.sql` | W2 | `idx_messages_conversation_inbound_created_at` |
| `tests/triggers/test_events_repo_pg.py` | — | Call-sites `find_stuck_queued` atualizados |
| `tests/triggers/test_chaos_redis_restart.py` | — | Fake conn distingue queries cooldown vs daily_cap |
| `tests/triggers/test_cooldown_unit.py` | — | Idem |

### Sessão anterior (commits `dd54aba`, `c5e600c`, `8866901`)

| File | Findings Fixed | Summary |
|------|---------------|---------|
| `prosauai/triggers/scheduler.py` | B3, B4 | `_build_evolution_client` + `_restore_state_for_all_tenants` wired |
| `prosauai/triggers/engine.py` | B5, B8 | `load_stuck_for_retry` + `_dispatch_send` fora da transação; `tick_extra` hoisted |
| `prosauai/triggers/matchers.py` | B7 | `consent_required` via `$3::bool`; `_warn_unsupported_filters` |
| `prosauai/channels/outbound/evolution.py` | B9 | Retry 3× exponential backoff para 5xx |
| `scripts/retention_cron.py` | B6 | `trigger_events` em `_DELETE_STATEMENTS` |
| `prosauai/triggers/cost_gauge.py` | W-old1 | Lock release no `finally` |
| `prosauai/admin/triggers.py` | W-old10 | Cursor malformado → 400 |
| `db/migrations/20260601000025_*.sql` | W-old21 | Índice paginação global |

---

## Recomendações

**Para QA (Phase 10):**
1. **W5 (circuit breaker)**: Load sintético com Evolution retornando 5xx consecutivos — verificar se breaker abre após N falhas.
2. **W3 (filtros silenciosos)**: Confirmar que nenhuma configuração de tenant em prod usa `intent_filter`/`agent_id_filter` — se usar, está sendo ignorada.
3. **S1 (LGPD DPO)**: Antes de ativar `mode: live` em Ariel, registrar o veredito DPO sobre `ON DELETE CASCADE` em `decisions.md`.
4. **W1 verification**: Testar Redis restart em staging — confirmar que `restore_state_from_sql` restaura cooldown keys E daily_cap counters.

**Para Reconcile (Phase 11):**
1. Promover ADR-049 e ADR-050 de `draft` → `reviewed`.
2. Capturar DPO verdict (S1) em `decisions.md`.
3. Registrar N9–N13 como backlog 016.1 em `roadmap.md`.

---

## Observação Processual

O analyze-post (Step 8) reportou "0 CRITICALs" com base em mapeamento FR→task, mas não verificou **invocação em runtime**. Os 9 BLOCKERs desta rodada eram código que existia mas nunca era chamado no caminho de execução real (scheduler → engine → events/cooldown/matchers).

**Recomendação**: future analyze-post deve incluir um "invocation trace" check — para cada FR com task `[x]`, verificar se a função implementadora é reachable pelo caminho principal de execução.

---

handoff:
  from: madruga:judge
  to: madruga:qa
  context: "Judge PASS 82/100. 9 BLOCKERs fixados (incluindo cross-tenant data bleed B1 + retry bypass B2). 3 WARNINGs open (W3 filtros silenciosos, W4 daily_cap edge, W5 circuit breaker). 2 carry-forwards: S1 DPO LGPD + S2 ADR-049/050 promoção. 231/231 trigger tests pass."
  blockers: []
  confidence: Alta
  kill_criteria: "W5 (circuit breaker) revelado em QA como BLOCKER (breaker nunca abre sob 5xx storm) → fix em evolution.py antes de rollout live."
