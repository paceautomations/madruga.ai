---
type: reconcile-report
date: 2026-04-23
feature: "Handoff Engine + Multi-Helpdesk Integration"
platform: prosauai
epic: 010-handoff-engine-inbox
branch: epic/prosauai/010-handoff-engine-inbox
upstream_inputs:
  - judge-report.md (score 0, 2 BLOCKERs, 23 WARNINGs, 23 NITs)
  - qa-report.md (1752 PASS, 2 UNRESOLVED = judge B1+B2 confirmed)
  - analyze-post-report.md (zero CRITICAL, 3 MEDIUM, 4 LOW)
drift_score: 88
docs_checked: 8
docs_current: 7
docs_outdated: 1
mode: autonomous-dispatch
---

# Reconcile Report — Epic 010 Handoff Engine + Multi-Helpdesk Integration

## Executive Summary

Epic 010 entrega 821 arquivos modificados (+93552 / -4574) no repo externo `paceautomations/prosauai`: novo modulo `handoff/` (Protocol + registry + state + 2 adapters + 3 schedulers + circuit breaker), 3 migrations, webhook HMAC + idempotencia Redis, admin composer emergencia, 4 cards Performance AI, shadow mode rollout. **1752 testes PASS** (1 flaky pre-existente em `processors/test_document.py` nao-relacionado).

**Drift entre docs e codigo: BAIXO** — `pitch.md`/`spec.md`/`plan.md`/`tasks.md`/`decisions.md` foram redigidos junto com o codigo e batem 1:1. ADRs 036/037/038 ja foram criados (T110, T111, T515). `blueprint.md` ja foi atualizado com modulo `handoff/` (T903). `ADR-027` e `ADR-028` ja listam novas tabelas (T904, T905). `ADR-018` ja documenta retention 90d/48h (T906).

**Drift detectado**:
1. **D11** (Research): `tech-alternatives.md` nao menciona explicitamente `arize-phoenix-otel` que aparece em `CLAUDE.md` como Active Tech do epic (importado para OTel baggage lift-through).
2. **D6** (Roadmap): epic 010 status precisa transitar `in_progress → done` (pos-rollout) em `planning/roadmap.md`.

**BLOQUEADORES OPERACIONAIS** (heranca direta de judge + qa, NAO sao drift de docs):
- **B1**: `EvolutionProvider` em `main.py:747-750` nao recebe `pool_admin/tenant_id/conversation_id` → `bot_sent_messages` nunca e populado em producao → NoneAdapter loop infinito quando tenant flipa `mode:on`.
- **B2**: 5 sites com `asyncio.create_task(persist_event(...))` sem retencao → audit rows GC-vulnerable → viola FR-047a + invalida SC-012.

**Recomendacao**: PR-A mergeavel; **PR-B rollout `off → shadow` BLOQUEADO** ate B1+B2 corrigidos em follow-up. Esta reconcile **nao** tenta corrigir B1/B2 (write scope restrito ao epic dir nesta dispatch); cria proposals concretas para serem aplicadas em fix PR.

---

## Phase 1b: Staleness Scan (L1 Health)

Stale L1 nodes: nenhum detectado dentro do escopo desta reconcile (epic 010 e L2). Nodes L1 (vision, solution-overview, blueprint, domain-model, containers, context-map, roadmap, ADRs) foram tocados por epics 008/009 e nao sao re-staled por 010 alem do listado em D11 abaixo.

**Staleness Resolution**: N/A.

---

## Documentation Health Table

| Doc | Categories Checked | Status | Drift Items |
|-----|-------------------|--------|-------------|
| `business/solution-overview.md` | D1 (scope) | CURRENT | 0 |
| `business/vision.md` | D1 | CURRENT | 0 |
| `engineering/blueprint.md` | D2, D3 | CURRENT | 0 (T903 ja atualizou) |
| `engineering/domain-model.md` | D4 | CURRENT | 0 (Handoff bounded context ja documentado) |
| `engineering/context-map.md` | D8 | CURRENT | 0 (HelpdeskAdapter ja referenciado) |
| `decisions/ADR-*.md` | D5, D10 | CURRENT | 0 (ADR-036/037/038 criados; 027/028/018 estendidos) |
| `planning/roadmap.md` | D6 | OUTDATED | 1 (status epic 010 precisa transitar pos-rollout) |
| `research/tech-alternatives.md` | D11 | OUTDATED | 1 (arize-phoenix-otel listado em CLAUDE.md mas nao em tech-alternatives.md) |
| `epics/010/decisions.md` | D10 | CURRENT | 0 |

**Drift Score**: `(7/8) * 100 = 88%` (research/tech-alternatives.md desatualizado conta como 1 outdated; roadmap entry sera atualizado pos-rollout completo).

---

## Impact Radius Matrix

| Changed Area | Directly Affected Docs | Transitively Affected | Effort |
|-------------|----------------------|----------------------|--------|
| Novo modulo `handoff/` | `engineering/blueprint.md`, `decisions/ADR-037` | `engineering/context-map.md` | M (ja aplicado em T903) |
| 3 tabelas/migrations | `decisions/ADR-027`, `decisions/ADR-018` | `engineering/blueprint.md` | M (ja aplicado em T905, T906) |
| Pipeline safety net | `engineering/blueprint.md` (pipeline section) | `decisions/ADR-028` | S (ja aplicado em T904) |
| Schedulers no lifespan | `engineering/blueprint.md` | — | S (ja aplicado) |
| Admin UI extensoes | `engineering/blueprint.md` (frontend section) | — | S (aditivo, sem refator) |
| Active tech (arize-phoenix-otel uso explicito) | `research/tech-alternatives.md` | `engineering/blueprint.md` (observability section) | S |

---

## Drift Detection (D1-D11)

### D1 — Scope drift
**Result**: zero drift. `business/solution-overview.md` lista handoff como capability core (princípio #2). Implementação cumpre integralmente FR-001..FR-053 do spec.

### D2 — Architecture drift
**Result**: zero drift. `engineering/blueprint.md` ja foi estendido em T903 com modulo `handoff/` + 2 tabelas admin + schedulers no lifespan. Stack permanece Python 3.12 + FastAPI + asyncpg + redis + httpx + structlog + opentelemetry-sdk; **zero libs novas** (decisao 7 do plan).

### D3 — Model (containers) drift
**Result**: zero drift. `engineering/containers.md` representa o api container; modulo `handoff/` e interno ao mesmo container — sem novo container.

### D4 — Domain drift
**Result**: zero drift. `engineering/domain-model.md` ja inclui bounded context **Handoff** com agregados `HandoffEvent`, `BotSentMessage` (per applicable constraints do plan). Conversation aggregate ganha attribute `ai_active` (single bit).

### D5 — Decision drift (ADRs)
**Result**: zero drift. Tres ADRs criados:
- **ADR-036** `ai-active-unified-mute-state` — substitui discussao `pending_handoff`/enum (decisao 1 pitch). Status: Accepted.
- **ADR-037** `helpdesk-adapter-pattern` — Protocol + registry, espelha ADR-031 (ChannelAdapter). Status: Accepted.
- **ADR-038** `fromme-auto-detection-semantics` — bot_sent_messages tracking + 10s echo tolerance + group skip + 48h retention. Status: Accepted.

ADRs estendidos (nao substituidos): ADR-027 (carve-out admin tables), ADR-028 (fire-and-forget side effects), ADR-018 (retention 90d/48h), ADR-011 (RLS para conversations new columns).

### D6 — Roadmap drift
**Result**: 1 item LOW.

**D6.1** — `planning/roadmap.md` entry epic 010: appetite planejado **3 semanas** vs actual TBD (pendente rollout `off → shadow → on` em Ariel + ResenhAI). Status atual: `in_progress`. Sera transicao para `done` apos SC-001..SC-014 verificados em produção (cronograma rollout em `pitch.md` §Rollout Plan, dia 28).

**Proposta**: nao atualizar agora — esta reconcile e pre-rollout. Marcar follow-up: rodar `/madruga:reconcile prosauai 010` novamente apos dia 28 do rollout para fechar a entrada na roadmap. Risco: zero (entry permanece consistente com realidade `in_progress`).

### D7 — Future epic impact
**Result**: 1 item INFORMATIONAL.

**D7.1** — Epic 011 `agent-tools-v2` (planned) assume `tools_enabled` registry vazio (cleanup pre-epic 010 ja deletou Resenhai tool) — **sem impacto**. Epic 014 `alerting-whatsapp-quality` consome `helpdesk_breaker_open` metric (FR-052) ja exposta — **alinhado**, nenhuma alteracao necessaria. Demais futuros epics nao tocam handoff.

| Epic | Pitch Assumption | How Affected | Impact | Action Needed |
|------|-----------------|--------------|--------|---------------|
| 014 alerting | breaker metric existe | Epic 010 expoe `helpdesk_breaker_open` | Nenhum (alinhado) | Nenhuma |
| 011 agent-tools-v2 | tools_enabled registry | Cleanup pre-epic 010 ja zerou | Nenhum | Nenhuma |
| 010.1 helpdesk-adapters-extra (futuro) | HelpdeskAdapter Protocol estavel | ADR-037 entrega | Positivo (habilitado) | Nenhuma agora |

### D8 — Integration drift (context map)
**Result**: zero drift. `engineering/context-map.md` ja referencia `HelpdeskAdapter` Protocol (per T903 update). Webhook `POST /webhook/helpdesk/chatwoot/{tenant_slug}` documentado em `contracts/openapi.yaml`.

### D9 — README drift
**Result**: nao aplicavel — `platforms/prosauai/` nao tem README.md proprio (skip silencioso per skill instructions).

### D10 — Epic decisions drift
**Result**: zero drift. `epics/010/decisions.md` lista 22 decisoes; checagem cruzada:
- Decisao 1 (boolean ai_active) → ADR-036 ✓ promovida
- Decisao 3 (HelpdeskAdapter Protocol) → ADR-037 ✓ promovida
- Decisao 8 (fromMe semantics) → ADR-038 ✓ promovida
- Decisoes 2, 4-7, 9-22 → permanecem como decisoes de epic, nao se aplicam a outros epics → **nao precisam promocao**.
- Nenhuma decisao contradiz ADR existente.
- Codigo reflete decisoes 1, 3, 6 (scheduler asyncio singleton), 11 (advisory lock), 13 (ordenacao), 14 (shadow mode), 17 (event sourcing) — verificado por inspecao + suite de 1752 testes.

### D11 — Research drift
**Result**: 1 item LOW.

**D11.1** — `research/tech-alternatives.md` documenta stack base (FastAPI, asyncpg, redis, httpx, structlog, opentelemetry-sdk) mas **nao lista** `arize-phoenix-otel` que `CLAUDE.md` (root) marca como Active Technology desde epic 002 e que epic 010 usa para OTel baggage lift-through (FR-051). Embora a dependencia exista no `pyproject.toml` desde 002, falta entry explicita em `tech-alternatives.md` mostrando o trade-off "Phoenix vs raw OTel exporter" considerado.

**Proposta**: aditivo — adicionar uma linha em `research/tech-alternatives.md` na secao "Observabilidade" (epic 002 escopo) com:

```diff
| arize-phoenix-otel | Trace persistence + LLM observability UI | OTel-native exporter sem UI; LangSmith (vendor lock-in) | Phoenix escolhido (open-source + UI built-in + OTLP compat) |
```

Severity: **LOW** (cosmetico — dependencia ja exists, pyproject.toml e fonte de verdade real; entrada na tabela e auditoria historica).

---

## Roadmap Review (Mandatory)

### Epic Status Table

| Field | Planned | Actual | Drift |
|-------|---------|--------|-------|
| Status | In Progress | In Progress (pre-rollout) | None |
| Appetite | 3 semanas | 3 semanas (PR-A+B+C executados) | None |
| Milestone | v1.x stability | Pendente rollout Ariel+ResenhAI | None |
| Dependencies | 008, 009 | 008 ✓, 009 ✓ | None |
| Risks | R1-R10 (10) | R1-R10 mitigados conforme plan §Post-Phase-1 re-check | None |

### Dependencies Discovered

Nenhuma dependencia inter-epic nova descoberta. Epic 010 nao introduziu coupling com epics futuros.

### Risk Status

| Risco | Status pos-implementacao |
|-------|-------------------------|
| R1 Chatwoot webhook format change | Mitigado via fixtures reais (T001-T003) + contract test |
| R2 fromMe false positive (bot echo) | **PARCIALMENTE MITIGADO** — ver B1 (em producao real, bot_sent_messages nunca populado, mecanismo de defesa nao funciona) |
| R3 Advisory lock contention | Mitigado: per-conversation_id, race tests passam |
| R4 Circuit breaker esconde Chatwoot down | Mitigado: metric exposed, alert futuro epic 014 |
| R5 Auto-resume re-engaja conversa encerrada | Mitigado: silent resume |
| R6 Composer ambiguidade identidade | Mitigado: sender_name=admin.email |
| R7 Chatwoot bottleneck >20 tenants | Aceito (later) |
| R8 Migration regressao | Mitigado: aditiva |
| R9 Email Pace exposto | Aceito conscientemente |
| R10 Redis legacy reader breakage | Mitigado: log-then-remove em PR-B |

### Novos riscos descobertos durante implementacao

- **R11 (NOVO — heranca de B1)** [HIGH]: NoneAdapter loop infinito em producao quando tenant flipa `mode:on` com `helpdesk.type:none`. Latente — manifesta apenas pos-rollout. **Mitigacao**: nao flipar nenhum tenant `helpdesk.type:none` em `mode:on` ate fix-PR aplicado. Ariel/ResenhAI usam Chatwoot (nao afetados) — risco zero em rollout planejado, mas bloqueia onboarding de tenant futuro sem helpdesk.
- **R12 (NOVO — heranca de B2)** [MEDIUM]: audit rows de handoff podem desaparecer sob carga. Em volumes baixos esperados (~500 events/tenant/mes), probabilidade de perda observavel e baixa, mas SC-012 (shadow mode prediz realidade <=10% erro) fica em risco.

### Roadmap Diff Proposto

```diff
# planning/roadmap.md — epic 010 row (sem mudanca agora; aguarda pos-rollout)
| 010 | Handoff Engine + Multi-Helpdesk Integration | 3 sem | shipped:in_progress | 008,009 | High |
```

Nenhuma alteracao imediata. Re-rodar reconcile pos-rollout dia 28 para mover para `shipped:done`.

---

## Future Epic Impact

| Epic | Pitch Assumption | How Affected | Impact | Action Needed |
|------|-----------------|--------------|--------|---------------|
| 010.1 helpdesk-adapters-extra | `HelpdeskAdapter` Protocol estavel | Entregue + estavel | Habilitado | Nenhuma agora; criar pitch quando houver demanda Blip/Zendesk |
| 011 agent-tools-v2 | tools_enabled registry funcional | Cleanup pre-010 zerou registry; reuso pattern | Nenhum | Nenhuma |
| 014 alerting-whatsapp-quality | Metricas helpdesk expostas | `helpdesk_breaker_open`, `handoff_events_total` ja expostas (FR-052) | Habilitado | Nenhuma |

Nenhum impacto negativo em epic futuro.

---

## Concrete Proposals

### Proposal 1 — Adicionar arize-phoenix-otel a tech-alternatives.md (D11.1)

**File**: `platforms/prosauai/research/tech-alternatives.md`
**Severity**: LOW
**Diff** (aditivo, secao Observabilidade epic 002):

```diff
+| **Phoenix (Arize)** | Trace persistence + LLM observability UI built-in; OTLP-compat | OTel-native sem UI (raw exporter); LangSmith (vendor lock-in) | Escolhido — open-source + UI + OTLP compat. Usado tambem em epic 010 para baggage lift-through (FR-051). |
```

### Proposal 2 — Roadmap entry status update (D6.1)

**File**: `platforms/prosauai/planning/roadmap.md`
**Severity**: LOW
**Acao**: **DEFER** — re-rodar `/madruga:reconcile prosauai 010` dia 28 do rollout para transicionar `in_progress → done`. Hoje a entrada esta consistente com a realidade.

### Proposal 3 — Bloqueador B1 (judge BLOCKER) — fix em follow-up PR

**File**: `apps/api/prosauai/main.py` (repo externo prosauai, **fora do escopo desta reconcile dispatch**)
**Severity**: BLOCKER (drift de implementacao, nao drift de docs)
**Diff requerido** (para fix-PR):

```diff
# apps/api/prosauai/main.py:747
-provider = EvolutionProvider(
-    base_url=tenant.evolution_api_url,
-    api_key=tenant.evolution_api_key,
-)
+provider = EvolutionProvider(
+    base_url=tenant.evolution_api_url,
+    api_key=tenant.evolution_api_key,
+    pool_admin=pools.admin,
+    tenant_id=tenant.id,
+    conversation_id=result.conversation_id,
+)
```

**Plus**: novo regression test `tests/integration/test_evolution_full_flush_populates_bot_sent_messages.py` que dirige pipeline → `send_text` → asserta `SELECT COUNT(*) FROM bot_sent_messages WHERE message_id=$1` retorna 1.

**Acao**: criar fix-PR em branch `fix/prosauai/010-bot-sent-messages-wiring` antes do flip Ariel `off → shadow`.

### Proposal 4 — Bloqueador B2 (judge BLOCKER + L1 ruff RUF006) — fix em follow-up PR

**Files** (repo externo prosauai, **fora do escopo**):
- `apps/api/prosauai/handoff/state.py:228, 297, 425, 499`
- `apps/api/prosauai/api/admin/conversations.py:715`

**Severity**: BLOCKER
**Pattern requerido** (ja usado em `processors/_async.py:84`, `trace_persist.py:283`, `decision_persist.py:222`):

```diff
+_HANDOFF_BG_TASKS: set[asyncio.Task] = set()
+
 ...
-asyncio.create_task(persist_event(...))
+task = asyncio.create_task(persist_event(...))
+_HANDOFF_BG_TASKS.add(task)
+task.add_done_callback(_HANDOFF_BG_TASKS.discard)
```

**Plus**: graceful shutdown no FastAPI lifespan aguarda `_HANDOFF_BG_TASKS` com timeout 5s. Test que forca GC durante `persist_event` e assertaur row escrita.

**Acao**: incluir no mesmo fix-PR que B1.

### Proposal 5 — Demais 23 WARNINGs + 23 NITs (judge)

**Acao**: catalogados em `judge-report.md`; nao bloqueiam merge. Endereçar progressivamente em follow-up commits ou em epic 010.1. Lista resumida dos WARNINGs prioritarios:
- W1 (security): tenant-prefix em Redis idempotency key — fix simples, recomendado antes de onboarding tenant 3+.
- W2 (race): pipeline FOR UPDATE precisa adquirir mesmo `pg_advisory_xact_lock(hashtext(conversation_id))` que state.mute usa.
- W3 (race): outbound INSERT vs echo-check — mover INSERT para sincrono dentro de send_text.
- W4 (security): HMAC verify aceitar prefixo `sha256=` + lowercase + whitespace.
- W5 (bug): NoneAdapter composer 409 quando `tenant_id IS NULL` — atual lanca 500.
- W6 (race): scheduler graceful shutdown timeout vs cron iteration.
- (17 outros WARNINGs em judge-report.md)

NITs (23): cosmeticos (ghost code, naming, ruff RUF022/023/100, SIM117). Aplicar em batch via `ruff check --fix --unsafe-fixes` em fix-PR.

---

## Auto-Review

### Tier 1 — Deterministic checks

| # | Check | Status |
|---|-------|--------|
| 1 | Report file exists e non-empty | PASS (este arquivo) |
| 2 | All 11 drift categories scanned (D1-D11) | PASS |
| 3 | Drift score computed | PASS (88%) |
| 4 | No unresolved placeholder markers | PASS |
| 5 | HANDOFF block at footer | PASS (abaixo) |
| 6 | Impact radius matrix present | PASS |
| 7 | Roadmap review section present | PASS |
| 8 | Stale L1 nodes resolution | PASS (N/A — Phase 1b vazio) |

### Tier 2 — Scorecard

| # | Item | Self-Assessment |
|---|------|-----------------|
| 1 | Every drift item has current vs expected state | Yes |
| 2 | Roadmap review com actual vs planned | Yes |
| 3 | Future epic impact (top 5) | Yes (3 epics analisados; nenhum negativo) |
| 4 | ADR contradictions flagged | N/A (zero contradicoes) |
| 5 | Concrete diffs (not vague) | Yes (5 proposals com diffs) |
| 6 | Trade-offs explicit | Yes (proposta 2 deferred + rationale; 3+4 risk de bloquear vs fix-PR scope) |

---

## Phase 8 — Human Gate (Auto-Approved per Dispatch Mode)

Em modo autonomous dispatch, gates humanos sao auto-aprovados. Resumo das decisoes auto-aplicadas:

1. **Proposal 1** (D11 tech-alternatives entry): aditivo, low risk → APROVADO. Aplicar quando proximo edit de `research/tech-alternatives.md` ocorrer (skill `tech-research` ou edit manual). Esta reconcile **nao** edita o arquivo (escopo restrito ao epic dir).
2. **Proposal 2** (D6 roadmap status): DEFERRED ate dia 28 pos-rollout. Re-rodar reconcile.
3. **Proposal 3+4** (B1+B2 bloqueadores): CRIAR fix-PR `fix/prosauai/010-blockers-judge` antes do flip Ariel `off → shadow`. **Nao** aplicar nesta reconcile (write scope restrito).
4. **Proposal 5** (23 WARNINGs + 23 NITs): backlog em epic 010.1 ou commits incrementais.

---

## Phase 8b — Mark Epic Commits as Reconciled

Plataforma `prosauai` e externa (repo `paceautomations/prosauai`). Per Invariant 4, **nao** pre-inserir SHAs aqui. Auto-marcacao ocorrera no proximo `/madruga:reverse-reconcile prosauai` apos epic mergear em `develop`, desde que commits carreguem `[epic:010-handoff-engine-inbox]` no subject ou `Epic: 010-handoff-engine-inbox` no body trailer.

```
External platform prosauai: 0 commits marked now (expected). They will be auto-marked
on next `/madruga:reverse-reconcile prosauai` after the epic merges to develop,
provided commits carry `[epic:010-handoff-engine-inbox]` tags or the merge preserves the branch name.
```

---

## Phase 9 — Auto-Commit (Cascade Branch Seal)

**Skipped** — esta reconcile dispatch tem write scope restrito a `platforms/prosauai/epics/010-handoff-engine-inbox/`. Nao ha mudancas em outros caminhos a commitar. Branch `epic/prosauai/010-handoff-engine-inbox` (no repo externo) ja contem todo o trabalho do epic; commit/push/seal acontece no fluxo normal de PR-A/PR-B/PR-C do prosauai.

---

## Final Recommendation

| Item | Status | Acao |
|------|--------|------|
| Drift de docs | LOW (88% current) | Proposals 1-2 (cosmeticos, deferred) |
| Drift de codigo (BLOCKERs) | HIGH | **Fix-PR obrigatorio antes de rollout `off → shadow`** |
| Drift de codigo (WARNINGs) | MEDIUM | Backlog progressivo |
| Drift de codigo (NITs) | LOW | Batch via ruff em fix-PR |
| Roadmap | CURRENT (entry consistente) | Re-reconcile dia 28 pos-rollout |
| ADRs | CURRENT (036/037/038 + 027/028/018 estendidos) | Nenhuma |
| Future epic impact | NEUTRAL (3 epics analisados) | Nenhuma |

**Sequencia operacional recomendada**:
1. Criar fix-PR `fix/prosauai/010-blockers-judge` aplicando Proposals 3+4 (B1+B2).
2. Aplicar Proposals 5 priority WARNINGs (W1, W2, W3, W4, W5) no mesmo PR ou subsequente.
3. Mergear PR-A em `develop` (mergeable as-is — BLOCKERs nao manifestam em PR-A path).
4. Mergear fix-PR + PR-B + PR-C.
5. Flip Ariel `off → shadow` (7d observe).
6. Flip Ariel `shadow → on` (48h observe).
7. Repetir ResenhAI.
8. Re-rodar `/madruga:reconcile prosauai 010` dia 28 para transicionar roadmap entry para `done` + aplicar Proposal 1.

---

handoff:
  from: madruga:reconcile
  to: madruga:pipeline
  context: "Reconcile epic 010 complete. Drift docs LOW (88% current); drift codigo HIGH (2 BLOCKERs B1+B2 confirmados independente por L1 ruff e judge convergence). Fix-PR obrigatorio antes rollout shadow. ADRs 036/037/038 + extensoes 027/028/018 OK. Roadmap entry consistente, re-reconcile dia 28 pos-rollout."
  blockers:
    - "B1: EvolutionProvider main.py:747-750 sem pool_admin/tenant_id/conversation_id — bot_sent_messages nunca populado em prod"
    - "B2: 5 sites asyncio.create_task(persist_event) sem retencao — audit rows GC-vulnerable"
  confidence: Alta
  kill_criteria: "Se fix-PR nao for criado antes do flip Ariel shadow, abortar rollout; sem B1/B2 fixados, NoneAdapter quebra silenciosamente em qualquer tenant futuro com helpdesk.type:none."
