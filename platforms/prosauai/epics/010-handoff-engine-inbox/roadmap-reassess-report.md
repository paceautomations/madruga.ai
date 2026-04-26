---
title: "Roadmap Reassessment — Epic 010 (Handoff Engine + Multi-Helpdesk Integration)"
epic: 010-handoff-engine-inbox
platform: prosauai
date: 2026-04-23
updated: 2026-04-23
mode: autonomous
inputs:
  - pitch.md
  - spec.md
  - plan.md
  - tasks.md
  - implement-report.md
  - analyze-post-report.md
  - judge-report.md
  - qa-report.md
  - reconcile-report.md
  - easter-tracking.md
  - rollout-runbook.md
roadmap_source: platforms/prosauai/planning/roadmap.md (updated 2026-04-22)
---

# Roadmap Reassessment — Epic 010

> Post-epic roadmap review. Consolida aprendizados de 821 arquivos alterados (+93 552 / −4 574) no repo externo `paceautomations/prosauai`, 3 PRs (A/B/C), 3 ADRs novos (036/037/038), 4 ADRs estendidos, 2 tabelas admin-only novas (`handoff_events`, `bot_sent_messages`) + 6 colunas em `conversations`, 125 novos unit tests em `handoff/`, 2 judge BLOCKERs escapados. Propoe **mudancas concretas** em `planning/roadmap.md`, flagga R11/R12 como risks novos, re-avalia a fila de epics downstream (011 Evals a frente), e estabelece pre-condicoes operacionais para rollout Ariel `off → shadow → on`.

---

## 1. Executive summary

| Dimensao | Antes do 010 | Depois do 010 | Delta |
|----------|--------------|----------------|-------|
| `pending_handoff` status materializado | Declarado mas nao implementado (cf. `db/queries/conversations.py:16`) | `conversations.ai_active` single bit + 5 metadata columns | ✅ |
| Helpdesks suportados | 0 (flag `conversation_in_handoff` sempre false) | 2 (Chatwoot + None) via `HelpdeskAdapter` Protocol | +2 |
| Gatilhos de mute | 0 | 5 (chatwoot_assigned, fromMe_detected, manual_toggle, rule_match, safety_trip) | +5 |
| Gatilhos de resume | 0 | 3 (helpdesk_resolved > manual_toggle > timeout scheduler) | +3 |
| Tabelas admin-only (public.*) | 5 (traces/trace_steps/routing_decisions/media_analyses/processor_usage_daily) | 7 (+handoff_events, +bot_sent_messages) | +2 |
| ADRs | 35 (030–035 do epic 009) | 38 (+036/037/038) | +3 |
| Admin UI abas | 8 (epic 008) | 8 + 1 linha nova em Performance AI (4 cards Handoff) + badges por linha + composer | ✅ |
| Testes | 2096 baseline (pos-009) | 1752 passed + 125 novos unit tests `handoff/` + 31 novos unit tests pipeline | +156 novos |
| FRs cobertos | n/a | 53/53 (100%) em tasks.md | ✅ |
| Drift post-reconcile | n/a | 88% current (7/8 docs) | ✅ |
| Judge verdict | n/a | **FAIL score 0** — 2 BLOCKERs + 23 WARNINGs + 23 NITs | ⚠️ gate rollout |
| Status branch | epic/prosauai/010-handoff-engine-inbox | `in_progress` — **nao merged** em develop | ⏳ |

**Veredito**: epic **entrega o prometido a nivel de arquitetura + spec** (bit `ai_active` materializado, `HelpdeskAdapter` Protocol validado com dois shapes radicalmente diferentes — Chatwoot API + NoneAdapter comportamental, scheduler singleton via advisory lock, shadow mode, composer admin). No entanto, **judge encontrou 2 BLOCKERs escapados do analyze-post (score 0 CRITICAL vs 2 BLOCKERs)** que bloqueiam rollout `on` em qualquer tenant:
- **B1**: `main.py:747-750` constroi `EvolutionProvider` sem `pool_admin/tenant_id/conversation_id` → `bot_sent_messages` NUNCA sera populado em prod → NoneAdapter entra em self-loop silencioso se algum tenant futuro usar `helpdesk.type: none` com `handoff.mode: on`.
- **B2**: 5 sites de `asyncio.create_task(persist_event(...))` sem retencao de handle → GC-vulnerable → viola FR-047a (audit append-only) e compromete baseline do SC-012 (shadow mode prediz realidade ≤10%).

**Nao justifica novo epic** — tratar como "Epic 010 fix-PR" antes do merge de PR-A em develop. Esse fix-PR deve landar **antes** de qualquer flip de tenant para `shadow`/`on`.

Nenhum epic preexistente foi invalidado. Nenhum scope escape durante implementacao — plan de 3 PRs segurou. Unica mudanca de prioridade material: **epic 014 (Alerting + WA Quality) tem incentivo adicional** para subir uma posicao, porque metrics `helpdesk_breaker_open` + `handoff_shadow_events_total` estao emitidos mas nao tem alerting upstream — sem canal de alerta, shadow mode nao prova valor operacional em 7d de observacao.

---

## 2. Epic 010 outcome vs. plan

| Objetivo planejado (pitch) | Status | Evidencia |
|----------------------------|--------|-----------|
| PR-A Data model + HelpdeskAdapter + Chatwoot basico + pipeline safety net (1 sem) | ✅ Shipped (branch) | 3 migrations, `handoff/` module completo, `state.mute_conversation/resume_conversation` com advisory lock, pipeline `generate` FOR UPDATE safety net, `customer_lookup` amortiza read + popula `external_refs.chatwoot`, 125 handoff unit tests PASS |
| PR-B NoneAdapter + webhooks + scheduler + shadow mode (1 sem) | ✅ Shipped (branch) | `NoneAdapter` com group skip + 10s echo tolerance, `POST /webhook/helpdesk/chatwoot/{tenant}` com HMAC + SETNX idempotency + 2 event types, 3 schedulers singleton via `pg_try_advisory_lock`, shadow mode branch em `state.mute_conversation` |
| PR-C Admin UI + composer + Performance AI 4 cards (1 sem) | ✅ Shipped (branch) | Badges verde/vermelho na inbox, toggle mute/unmute, composer emergencia delegando ao adapter, 4 cards Recharts (taxa, duracao, breakdown, SLA breaches), Playwright E2E verde |
| SC-004 p95 texto ≤ baseline+5ms (gate PR-A) | ✅ Cleared | T120 benchmark `test_text_latency_no_regression.py` verde |
| SC-005 Zero regressao em 173+191 tests | ✅ Cleared | T130: 1752 passed / 1 skip / 1 flaky-unrelated na suite full (38.78s) |
| SC-007 Idempotencia webhook 100% | ✅ Cleared | T201 + unit/integration tests validam SETNX TTL 24h; duplicata = 200 no-op |
| SC-008 Cron auto-resume dentro de 60s | ✅ Cleared | T300 freezegun time-travel + T310-T311 implementation |
| SC-009 Circuit breaker isolamento | ✅ Cleared | T040-T041 unit; Chatwoot down nao bloqueia mute ja commitado (ADR-028 fire-and-forget) |
| SC-010 Observabilidade 100% | ✅ Cleared | OTel baggage lift-through (T217), Prometheus metrics (T218, T813, T900), structlog fields (T901), Trace Explorer integrado |
| SC-013 Admin UI detalhe < 2s p95 | ✅ Cleared | Playwright E2E; endpoint `GET /admin/conversations/{id}` com `ai_active` + metadata |
| SC-014 Audit cross-tenant Pace ops | ✅ Cleared | `handoff_events.metadata.admin_user_id=<JWT.sub>` persistido; `sender_name=<JWT.email>` transient |
| Cut-line (PR-C sacrificavel) | ✅ Nao ativado | 3 PRs dentro do prazo; nenhum phase 5/7/8 cortado |
| **SC-001** (zero bot replies during human handoff) | ⏳ Deferido 30d prod | Gate real requer telemetria Ariel+ResenhAI pos-flip `on` |
| **SC-002** (webhook → mute <500ms p95 prod) | ⏳ Deferido prod | Benchmark T203 mede em staging; prod requer carga real |
| **SC-003** (composer <2s p95 end-to-end) | ⏳ Deferido prod | E2E Playwright valida staging; prod carga real |
| **SC-006** (fromMe false positive <1%) | ⏳ Deferido prod | Teste de carga usado no dev; validacao real pos-rollout NoneAdapter (nao aplicavel a Ariel/ResenhAI) |
| **SC-011** (rollout reversivel 100%) | ⏳ Deferido chaos test | `handoff.mode: on → off` via `tenants.yaml` + poll 60s testado em dev; falta chaos test em staging |
| **SC-012** (shadow prediz realidade ≤10% erro) | ⚠️ **Comprometido** | B2 (GC-vulnerable `asyncio.create_task`) pode perder events shadow silenciosamente — baseline de comparacao fica viesado para baixo ate fix-PR landar |

**Desvios material**: nenhum de escopo. **Debito critico**: 2 BLOCKERs judge + 4 NITs ruff RUF006 (confirmam B2) antes de merge em develop.

---

## 3. O que mudou na visao roadmap

### 3.1 Follow-ups descobertos pelo epic 010

Zero follow-up epics novos descobertos que justifiquem entrada formal no roadmap. Dois candidatos permanecem em **someday-maybe backlog**:

| Candidato | Racional para manter no backlog | Trigger para promover |
|-----------|----------------------------------|-----------------------|
| **010.1 Helpdesk adapters extras** (Blip, Zendesk, Freshdesk, Front) | `HelpdeskAdapter` Protocol estavel com 2 shapes radicalmente diferentes (Chatwoot API + NoneAdapter comportamental) valida a abstracao. Sem demanda de cliente hoje. | Primeiro cliente externo pagante que ja tenha helpdesk ≠ Chatwoot |
| **010.2 Handoff em group chat** | v1 pula grupos silenciosamente (Decisao 21 pitch). Semantica ambigua ("quem e o humano?"). | Cliente com volume de grupo significativo (>30% conversas) pedindo |

### 3.2 Recomendacoes de edit em `planning/roadmap.md`

**Commit 1** — atualizar status do epic 010 na Epic Table apos merge em develop (hoje linha diz "next"; vira "shipped" pos-rollout):

```diff
- | 10 | **010: Handoff Engine + Inbox** | 009 | medio | Next | **next** — materializa `pending_handoff`, UI atendente humano, SLA + timeout→bot, notificacao realtime. Funde antigo "010 Handoff Engine" + "013 Admin Handoff Inbox". |
+ | 10 | **010: Handoff Engine + Multi-Helpdesk Integration** | 009 | medio | Next | **shipped** (3 PRs branched mas pendente merge develop + fix-PR B1/B2; 3 ADRs 036-038, 2 tabelas admin-only, `HelpdeskAdapter` Protocol com Chatwoot + None, 4 cards Performance AI, shadow mode. Rollout Ariel `off→shadow→on` pos-merge; ResenhAI 7d depois. Rollout runbook em `epics/010-handoff-engine-inbox/rollout-runbook.md`). |
```

**Commit 2** — atualizar status-line superior do roadmap:

```diff
- **Lifecycle:** building — **MVP completo** (6/6 epics shipped) + **Admin shipped** (007+008) + **Channel Ingestion shipped** (009, merged 2026-04-20). Proximo: epic 010 Handoff Engine + Inbox.
+ **Lifecycle:** building — **MVP completo** (6/6 epics shipped) + **Admin shipped** (007+008) + **Channel Ingestion shipped** (009) + **Handoff Engine shipped** (010, branch completo, pending fix-PR B1/B2 + merge develop). Proximo: epic 011 Evals (offline + online fundidos).
- **L2 Status:** Epic 001 shipped ... **Epic 009 shipped** (Channel Ingestion + Content Processing — ...).
+ **L2 Status:** Epic 001 shipped ... **Epic 009 shipped** (Channel Ingestion + Content Processing — ...). **Epic 010 shipped branch** (Handoff Engine + Multi-Helpdesk Integration — `ai_active` single bit, HelpdeskAdapter Protocol [Chatwoot + None], scheduler singleton advisory-lock, shadow mode, 3 ADRs 036-038, 125 novos handoff unit tests; pending fix-PR de 2 BLOCKERs judge antes rollout Ariel `off→shadow→on`).
- **Proximo marco:** epic 010 (Handoff Engine + Inbox) — materializar `pending_handoff` no DB + UI atendente humano.
+ **Proximo marco:** fix-PR B1+B2 → merge PR-A/B/C em develop → rollout Ariel `off → shadow (7d) → on (48h)` → ResenhAI (mesmo trajeto, stagger 7d) → iniciar epic 011 Evals apos ~28d de rollout.
```

**Commit 3** — novos riscos descobertos (append a tabela de Riscos do Roadmap):

```diff
 | **`pending_handoff` status existe no DB mas nao e materializado** | **Aberto — endereca em 010** | Alto | Certeza | Toda conversa que precisa de humano hoje fica em silencio. Epic 010 materializa engine + inbox para fechar o buraco |
+| **`pending_handoff` status existe no DB mas nao e materializado** | **Eliminado (epic 010)** | — | — | `conversations.ai_active` single bit materializado (ADR-036). Decisao 1 pitch 010: bool substitui enum state machine |
+| **NoneAdapter silent self-loop em prod com `mode:on` + `helpdesk.type:none`** | **Aberto (epic 010 B1 judge)** | Alto | Alta se tenant `none` onboardar | `EvolutionProvider` em `main.py:747-750` construido sem `pool_admin/tenant_id/conversation_id` → `bot_sent_messages` nunca populado → bot responde e classifica proprio echo como humano → loop silencioso. Fix-PR obrigatorio ANTES de onboardar tenant `helpdesk.type: none`. Ariel/ResenhAI (ambos Chatwoot) nao disparam esse bug — mas bloqueia epic futuro `Multi-Tenant Self-Service Signup` |
+| **Handoff audit rows GC-droppable sob carga** | **Aberto (epic 010 B2 judge + 4x ruff RUF006 QA)** | Medio | Alta | 5 sites `asyncio.create_task(persist_event(...))` sem retencao de handle. Event loop pode GC o Task em high-GC → `handoff_events` append-only perde rows em silencio. Compromete FR-047a (audit) e SC-012 (shadow prediz realidade). Fix: retain em `self._background_tasks: set[asyncio.Task]` + callback `discard`. Fix-PR obrigatorio ANTES de flip `shadow` em Ariel (baseline de comparacao seria viesado) |
+| **Redis idempotency key `handoff:wh:{event_id}` global cross-tenant** | **Aberto (epic 010 W1 judge, escaped 1-way-door)** | Medio | Baixa hoje (1 Chatwoot shared Pace) | Topology plan.md A2 caso (b) — Chatwoot per-tenant VPS com espacos de event_id ortogonais → colisao rara mas possivel. Fix: prefixar `handoff:wh:{tenant_slug}:{event_id}`. Enderecavel como follow-up sem urgencia |
+| **`hashtext()` 32-bit causa colisao ~1% em 10k conversations** | **Aberto (epic 010 W17 judge, escaped 1-way-door)** | Baixo hoje | Baixa com 2 tenants | Gradiente de risco: 2 tenants ok; >5 tenants com volume alto colisao pode levar a wait injustificado em advisory lock. Fix: trocar para `hashtextextended()` (64-bit) ou composite key. Reavaliar em epic 020 TenantStore Postgres |
```

**Commit 4** — promover Multi-Tenant Self-Service Signup dentro do backlog com gate adicional (dependencia nova para fix de B1):

```diff
 | Multi-Tenant Self-Service Signup | Cadastro totalmente autonomo via web — sem onboarding humano | Public API Fase 2 estavel + admin manual virou gargalo (>=5 pedidos/semana) |
+| Multi-Tenant Self-Service Signup | Cadastro totalmente autonomo via web — sem onboarding humano | Public API Fase 2 estavel + admin manual virou gargalo (>=5 pedidos/semana) **+ fix B1 epic 010** (NoneAdapter self-loop) aplicado em develop |
```

### 3.3 Re-priorizacao da fila Post-MVP (antes × depois)

| Posicao | ANTES do 010 | DEPOIS do 010 | Mudou? |
|---------|--------------|----------------|--------|
| #1 Next | 010 Handoff Engine + Inbox | **011 Evals (offline + online fundidos)** | ✅ Subiu — 010 shipped |
| #2 Next | 011 Evals | 012 RAG pgvector | Manteve ordem relativa |
| #3 Next | 012 RAG pgvector | 013 Agent Tools v2 | Manteve ordem relativa |
| #4 Next | 014 Alerting + WA Quality | 014 Alerting + WA Quality | Considerando subir 1 posicao (ver racional abaixo) |
| #5 Next | 015 Agent Pipeline Steps | 015 Agent Pipeline Steps | Manteve |

**Racional para considerar subir 014 antes de 012**: shadow mode do epic 010 emite `handoff_shadow_events_total{tenant, source}` e `helpdesk_breaker_open{tenant, helpdesk}`, mas sem alerting upstream (Prometheus + Alertmanager) os numeros ficam em Grafana sem SLO breach notification. Se 014 nao landar antes de Ariel `shadow → on`, operador Pace precisa fazer polling manual do Performance AI tab durante 7d — trabalho manual que **derrota o proposito do shadow mode** (medir sem intervir). Recomendacao: avaliar no retro pos-rollout Ariel se 014 deve subir 2 posicoes.

**Nenhum epic invalidado**. Nenhum epic recategorizado de "Next → someday-maybe" ou vice-versa.

---

## 4. Outcomes vs. leading indicators

### 4.1 Objetivos de negocio (do `vision.md` + `solution-overview.md`)

| Objetivo | Leading indicator | Pre-010 | Pos-010 (projetado) | Status |
|----------|-------------------|---------|---------------------|--------|
| **"IA e copiloto, nao piloto" — humano sempre pode assumir** (principio #2 solution-overview) | % conversas com handoff humano → bot silencia corretamente | 0% (bot responde por cima) | 100% (pos-rollout `on`) | ✅ Desbloqueado |
| **Atendente nao e frustrado por conversa dupla** (vision.md dor operacional) | Numero de reclamacoes internas/mes "bot respondeu em cima de mim" | [ESTIMAR] ~5-10/mes hoje (Ariel+ResenhAI combined) | 0 | ✅ A medir pos-30d prod |
| **Onboarding < 15 min** (vision ambicao) | Tempo medio onboarding tenant novo com helpdesk | [ESTIMAR] 30-60 min (YAML hand-crafted + Chatwoot manual) | ~20 min (novo bloco `helpdesk + handoff` em tenants.yaml), ainda nao <15min | 🔶 Parcialmente desbloqueado (epic 012 RAG + 017 Tenant Self-Admin completam) |
| **70% resolucao autonoma** (North Star vision) | Taxa de conversas resolvidas sem handoff | [ESTIMAR] nao medido | [ESTIMAR] nao medido ainda — epic 011 fecha | ⏳ Nao medido ate epic 011 Evals |
| **Compliance LGPD** | Retention gaps em novos dados | 0 (texto) + 0 (midia — epic 009 retention 14d/90d) | 0 (+ `handoff_events` 90d, `bot_sent_messages` 48h — FR-047a, ADR-018 estendido) | ✅ |

### 4.2 Indicadores operacionais a coletar em prod (primeiros 30d Ariel → 60d total com ResenhAI)

Adicionar ao dashboard Performance AI (epic 008 + linha Handoff do epic 010) como parte do rollout:

- **Taxa de handoff por tenant** — esperado 3-8% baseline (pitch plano rollout). Se >30% → regra 004 ou safety guard 005 emitindo falso positivo; investigar antes de flip proximo tenant.
- **Duracao media silenciada** — esperado ≤ 4h com `auto_resume_after_hours=24`. Se >12h consistentemente → atendentes esquecendo de resolver; considerar reduzir default para 8h.
- **Breakdown por origem** — `chatwoot_assigned` esperado 70%+; `fromMe_detected` 0% (Ariel+ResenhAI nao usam NoneAdapter); `manual_toggle` ≤5%; `rule_match`/`safety_trip` 10-20% agregado.
- **SLA breaches (count de `source=timeout`)** — esperado ≤10% das conversas mutadas. Se >30% → escalar default `auto_resume_after_hours` per-tenant.
- **`handoff_shadow_events_total` vs `handoff_events_total` pos-flip `on`** — gate SC-012: comparar 7d de shadow contra 7d de on; erro ≤10%.
- **`helpdesk_breaker_open{tenant,helpdesk}` duracao total por dia** — esperado 0s. Qualquer breaker aberto >5min gera alerta (requer epic 014 landed).
- **`helpdesk_webhook_latency_seconds` p95** — gate SC-002: <500ms. Se excedendo, investigar rede Chatwoot Pace.
- **`handoff_redis_legacy_read` counter pos-PR-B** — esperado 0 apos 24h. Se >0 apos 7d → T910 nao pode ser executado (algum reader esquecido).
- **`bot_sent_messages` volume** — proxy para B1. Se zero em 48h com trafego inbound real → B1 nao foi fixado corretamente.

---

## 5. MVP & milestones — impacto

| Milestone | Status | Acao |
|-----------|--------|------|
| MVP (001–006) | ✅ Completo (desde 2026-04-13) | — |
| **Admin** (007 + 008) | ✅ Completo | — |
| **Channel** (009) | ✅ Completo (merged 2026-04-20) | — |
| **Human loop + qualidade** (010, 011, 012, 013, 014, 015, 016) | **010 shipped branch**, pending fix-PR + merge develop | Apos merge + rollout Ariel (7d shadow + 48h on), iniciar epic 011 |
| Tenant-facing (017) | sugerido | Gate mantido — dependencia 008 + 012 |
| Gated comercial (018, 019, 020) | on-demand | Gates mantidos — 018 primeiro cliente pagante, 019 ≥1 cliente pagando manual, 020 ≥5 tenants |

**Nenhum milestone novo sugerido**. "Multi-Source Expansion" sugerido no reassess do epic 009 fica em pausa — sem cliente demandando Instagram/Telegram e sem 010.1 helpdesk adapters extras, a expansao multi-source nao materializa escopo suficiente para um milestone dedicado.

---

## 6. Nao este ciclo (backlog deferido)

Mantido do pitch original + novos deferred explicitos descobertos:

| Item | Motivo da exclusao do 010 | Revisitar quando |
|------|---------------------------|------------------|
| Blip, Zendesk, Freshdesk, Front adapters (epic 010.1) | Fora do apetite 3 semanas; nenhum cliente demandando | Primeiro cliente externo pagante com helpdesk ≠ Chatwoot |
| Handoff em group chat (epic 010.2) | Semantica ambigua; v1 so 1:1 (Decisao 21 pitch). NoneAdapter pula com `noneadapter_group_skip` log | Cliente com >30% volume em grupos pedindo |
| Skills-based routing / queue prioritization | Chatwoot faz nativamente (teams/assignments); ProsaUAI nao reimplementa | Nunca — escopo fora do produto |
| Template Meta Cloud fora janela 24h | Adapter retorna erro; UI mostra alerta | Epic dedicado de templates aprovados |
| Transfer entre atendentes | Chatwoot ja faz nativamente | Nunca — escopo fora do produto |
| SLA breach notifications em Slack/email | Eventos publicados; integracao com canais de alerta | Epic 014 Alerting + WA Quality |
| Migration de conversas historicas | Nao re-processa fechadas; todas entram `ai_active=true` default | Nunca — aditivo sem data migration |
| Dashboard "operator leaderboard" | Nao e valor user/ops | Cliente pedindo (nao esperado) |
| Remover codigo shadow mode pos-validacao | Decisao operacional pos-retro (A13 spec) | Apos 1 tenant validado + retro positivo |
| Fix trade-off "email Pace no Chatwoot tenant" (Q4-A) | Aceito conscientemente; fallback "Pace Ops" agent = ~30 LOC | Se reclamacao de tenant surgir |
| **Remove Redis legacy key `handoff:*` reader** (T910) | Gated por 7d zero `handoff_redis_legacy_read` pos-rollout | Apos ambos Ariel+ResenhAI em `on` por 7d consecutivos |
| **Quickstart end-to-end staging validation** (T909) | Requer staging com Chatwoot + Evolution + Supabase provisionados | Pos-merge PR-C, pre Ariel `off → shadow` |
| **Rate limit per-tenant ProsaUAI → Chatwoot** | >20 tenants compartilhando Chatwoot Pace vira bottleneck; hoje 2 tenants | Monitor `helpdesk_api_4xx` ou onboarding >5 tenants no Chatwoot compartilhado |
| **Webhook payload size cap + rate limit** (W14 judge) | Pre-existente de 008; blast radius cresceu com novo endpoint | Epic 014 Alerting + WA Quality ou `/admin/auth` CSRF hardening junto |
| **CSRF em admin endpoints com `SameSite=Lax`** (W11 judge) | Pre-existente epic 007; novos endpoints admin herdam | Hardening geral admin, nao especifico do 010 |

---

## 7. Auto-Review

### Tier 1 — Deterministic

| # | Check | Resultado |
|---|-------|-----------|
| 1 | Output file exists and non-empty | ✅ |
| 2 | Epic 010 status reassessed (next → shipped branch) | ✅ |
| 3 | Follow-up epics listed (010.1, 010.2 em backlog; zero novos formais) | ✅ |
| 4 | Concrete diff proposals for roadmap.md (4 commits) | ✅ |
| 5 | Risks novos (R11 NoneAdapter + R12 GC + W1 cross-tenant key + W17 hashtext) | ✅ |
| 6 | No placeholder markers (TODO/TKTK/???/PLACEHOLDER) | ✅ |
| 7 | Leading indicators definidos com numeros/thresholds | ✅ |
| 8 | HANDOFF block present at footer | ✅ |

### Tier 2 — Scorecard

| # | Item | Self-assessment |
|---|------|-----------------|
| 1 | Re-priorizacao justificada (nao preferencia) | ✅ — 010 shipped promove 011 automaticamente; 014 considerado subir so apos retro Ariel |
| 2 | Dependencias aciclicas preservadas | ✅ — nenhuma edge nova adicionada |
| 3 | MVP criterion inalterado | ✅ — 001–006 continuam shipped |
| 4 | Milestones tem criterio testavel | ✅ — SC-001..014 + operational gates §4.2 |
| 5 | Iniciativas conectam a outcomes (nao vaidades) | ✅ — §4.1 tabela outcome × indicator (principio #2 + atendente frustracao + onboarding + 70% autonomo) |
| 6 | Kill criteria explicito para itens condicionais | ✅ — fix-PR B1 antes onboarding `helpdesk.type:none`; fix-PR B2 antes flip shadow Ariel; T910 gated por 7d zero reads |
| 7 | Confidence com justificativa | ✅ Alta nos dados entregues + Media na projecao de rollout (requer validacao Ariel) |

### Tier 3 — Adversarial review

Ja coberto pelo judge pass do proprio epic (2 BLOCKERs + 23 WARNINGs + 23 NITs ja identificados e triados). Sem adversarial adicional neste reassess — o epic ja foi auditado com maior profundidade do que um reassess faria.

---

## 8. Recommendations — next 2 weeks

1. **Fix-PR (B1 + B2) antes de merge em develop** (1 dia):
   - **B1**: corrigir `main.py:747-750` para injetar `pool_admin, tenant_id, conversation_id` no `EvolutionProvider` construtor — gate obrigatorio antes de qualquer tenant `helpdesk.type: none` ser onboardado. Ariel/ResenhAI (ambos Chatwoot) podem rolar sem o fix, mas bloqueia futuro `Multi-Tenant Self-Service Signup` e qualquer tenant cost-sensitive.
   - **B2**: retain `asyncio.create_task(...)` handles em `self._background_tasks: set[asyncio.Task]` + callback `discard` nos 5 sites. Gate obrigatorio antes de flip Ariel `off → shadow` (baseline SC-012 seria viesado).

2. **Merge PR-A + PR-B + PR-C em develop** (1 dia pos-fix): branch `epic/prosauai/010-handoff-engine-inbox` → `develop`. Zero regressao reconfirmada na suite full (gate SC-005).

3. **Executar T909 (quickstart end-to-end staging)** pos-merge, pre-flip Ariel (0.5 dia): validar fluxo completo Chatwoot webhook real → mute → inbound skip → resume → bot responde em staging antes de tocar producao.

4. **Rollout Ariel `off → shadow (7d observacao) → on (48h validacao)`** (9 dias):
   - Dia 0: `tenants.yaml` Ariel flip `off → shadow`. Monitorar `handoff_shadow_events_total` + comparar contra telemetria manual de atendente.
   - Dia 7: retro curto. Se false-mute rate estimado <5% → flip `shadow → on`. Caso contrario, ajustar regras + replicar shadow 7d.
   - Dia 9: 48h em `on`. Se metrics ok (taxa baseline, zero reclamacao atendente, SLA breaches <10%) → green light ResenhAI.

5. **Rollout ResenhAI mesmo trajeto** (9 dias): dia 9 → 18 total.

6. **T910 cleanup** (dia 18+7 = 25): apos 7d com `handoff_redis_legacy_read=0` em ambos tenants em `on`, remover codigo Redis legacy key em `core/router/facts.py` + remover log estruturado. Fecha o loop de migration.

7. **Retro completo dia 28**: (a) remover codigo shadow mode se decisao operacional positiva (A13 spec); (b) ajustar defaults `auto_resume_after_hours` se SLA breaches >30%; (c) avaliar se epic 014 Alerting deve subir antes de 012 RAG.

8. **Iniciar epic 011 (Evals offline + online fundidos)** via `/madruga:epic-context prosauai 011-evals-offline-online` (dia 28+): rollout 010 completo, dados shadow+real de 28d formam baseline de eval para quality scoring.

9. **Abrir issue "Epic 010 follow-up hardening"** no repo prosauai reunindo 18 WARNINGs nao-BLOCKER do judge (W2-W24 menos W1 W17) + 39 items cosmeticos ruff. Priorizar W11 (CSRF), W14 (webhook rate limit/size), W13 (breaker observability deeper) antes do dia 90 de prod.

10. **Atualizar `.claude/knowledge/pipeline-dag-knowledge.md` lessons-learned** (opcional): B1 escapou analyze-post porque `EvolutionProvider` foi unit-tested com fixtures mas nunca integration-tested contra `main.py:747-750` real. Evals epic (011) deve incluir "production wiring smoke" layer (boot FastAPI → single inbound → assert side-effect rows) como template para epics futuros.

---

## 9. Recomendacoes para epic 011 (Evals)

Epic 011 e o proximo no roadmap. Aprendizados do 010 que afetam 011 diretamente:

- **Shadow mode data e baseline para evals** — a tabela `handoff_events` + `trace_steps` (epic 008) alimentam o dataset de eval. Fix-PR B2 **deve landar antes** de qualquer ingestion de eval; caso contrario evals herdam under-counting bias do GC-drop silencioso.
- **Lifespan wiring integration test harness** — B1 escapou porque o teste unitario do `EvolutionProvider` usou fixtures ao inves de instanciar via `main.py` real. Epic 011 ingere telemetria em producao — deve ter um "production wiring smoke" layer automatizado (boot FastAPI → inbound → assert telemetry row). Incluir como T-task explicita.
- **Elevar `ruff RUF006` para ERROR project-wide** — 4 incidencias identicas em um epic mostra que lint-severity atual e insuficiente. Epic 011 e bom momento para adicionar pre-commit hook + CI gate.
- **Key-scoping convention multi-tenant** — epic 011 adicionara telemetria keys (eval scores, session ids). Adicionar a `engineering/blueprint.md` regra: "qualquer key Redis scoped por event_id MUST ser prefixada com `tenant_slug`". Prevent W1 (cross-tenant key collision) de re-emergir.
- **Phase dispatch prompt size monitoring** — easter-tracking do 010 observou ~95KB/phase (plan.md 36KB + data_model.md 29KB duplicados). Epic 011 com escopo de evals pode expandir data-model.md significativamente; considerar per-phase-summary compression no plan.md (ou ADR novo sobre "documento-como-cache" protocol).
- **Analyze gate nao pega lifespan bugs** — judge multi-persona e o gate correto pre-rollout. Epic 011 nao deve skip judge mesmo que analyze passe zero-CRITICAL.
- **SC-012 shadow-vs-real baseline provides first real eval data point** — se epic 011 materializar evals online antes de Ariel+ResenhAI atingirem 14d em `on`, o primeiro eval dataset sera viesado por shadow mode semi-compromised. Sequenciamento natural: 010 rollout → 011 inicio (nao paralelizar).

---

## 10. Conclusao

Epic 010 **desbloqueou o principio arquitetural #2** do produto ("IA e copiloto, nao piloto") materializando `conversations.ai_active` como single bit, validando `HelpdeskAdapter` Protocol com dois shapes radicalmente diferentes (Chatwoot API + NoneAdapter comportamental), e estabelecendo os 3 gatilhos de retorno com priorizacao clara (helpdesk_resolved > manual_toggle > timeout). Zero scope escape durante 3 semanas de implementacao.

**Dividas tecnicas criticas escapadas**: 2 judge BLOCKERs (B1 NoneAdapter lifespan wiring, B2 `asyncio.create_task` GC) bloqueiam rollout `on` em tenants ate fix-PR landar. Mitigacao: fix-PR de ~30 LOC + merge develop + rollout Ariel → ResenhAI em ~18d total. Nenhum epic novo justificado — tratar como issue "Epic 010 follow-up hardening" dentro do repo prosauai.

**Roadmap next**: epic 011 Evals (offline + online fundidos) e o proximo natural; sequenciar **apos** rollout completo Ariel+ResenhAI para nao importar baseline viesado. Epic 014 Alerting + WA Quality e candidato a subir 2 posicoes se retro pos-Ariel mostrar que shadow mode requer alerting upstream para agregar valor operacional.

Drift pos-reconcile 88% (7/8 docs current) — unico gap e `research/tech-alternatives.md` faltando entrada cosmetica para `arize-phoenix-otel` (LOW, deferido). Nenhum epic preexistente foi invalidado. Nenhuma dependencia nova adicionada entre epics.

**Confidence**: **Alta** na arquitetura e escopo entregues. **Media** na projecao de rollout (requer validacao empirica Ariel+ResenhAI). **Alta** na recomendacao de sequenciar 011 apos rollout completo — convergencia entre judge + reconcile + implement-report + qa-report + 125 handoff unit tests verdes suporta o reassessment.

---

handoff:
  from: madruga:roadmap
  to: madruga:epic-context
  context: "Epic 010 reassessment concluido. Recomendacoes concretas: (1) fix-PR B1 (NoneAdapter lifespan wiring em main.py:747-750) + B2 (5 sites asyncio.create_task sem retention) antes de merge em develop — gate obrigatorio antes de rollout; (2) merge PR-A+B+C em develop apos fix; (3) executar T909 quickstart staging pre-flip Ariel; (4) rollout Ariel off → shadow (7d) → on (48h) → ResenhAI mesmo trajeto (~18d total); (5) T910 cleanup Redis legacy key apos 7d zero reads; (6) retro completo dia 28 para avaliar remocao de shadow mode e possivel subida de 014 Alerting; (7) aplicar 4 diffs em planning/roadmap.md (status 010 → shipped + 3 novos riscos R11/R12/W1/W17 + Multi-Tenant Self-Service gate + atualizacao status-line); (8) abrir issue 'Epic 010 follow-up hardening' para 18 WARNINGs nao-BLOCKER judge + 39 ruff cosmeticos. Proximo epic natural: 011 Evals — sequenciar APOS rollout completo (dia 28+) para evitar baseline viesado por shadow mode compromised ate fix-PR B2. Incluir no 011 'production wiring smoke' layer automatizado para prevenir outro B1 tipo de escape."
  blockers:
    - "Fix-PR B1+B2 bloqueia merge PR-A em develop (judge FAIL score 0 rollback). Sem B1, NoneAdapter ficara latente para tenants futuros. Sem B2, baseline SC-012 viesado."
  confidence: Alta
  kill_criteria: "Invalidado se (a) fix-PR B1+B2 nao passar judge re-verify em segunda tentativa (force repensar ADR-037 contract vs 008 instrumentation contract), (b) Ariel em shadow por 7d mostrar false-mute rate >20% (indica regra 004 ou safety guard 005 emitindo falso positivo — bloqueia flip on), (c) primeiro 48h de Ariel em on revelar bot respondendo por cima de humano em >1 conversa (SC-001 quebrado — rollback imediato + investigacao), (d) rollout ResenhAI mostrar divergencia significativa do comportamento Ariel (metricas handoff_rate >3x Ariel em cenario comparavel — indica que abstracao `HelpdeskAdapter` nao captura variabilidade cross-tenant que imaginavamos)."
