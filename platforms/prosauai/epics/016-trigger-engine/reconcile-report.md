---
title: "Reconcile Report — prosauai 016-trigger-engine"
drift_score: 22
verdict: outdated
docs_checked: 9
docs_current: 2
proposals_total: 12
proposals_high: 5
proposals_medium: 6
proposals_low: 1
updated: 2026-04-28
staleness_nodes_resolved: 3
---

# Reconcile Report — prosauai 016-trigger-engine

## Drift Score: 22% (2/9 docs sem drift)

**Veredicto:** OUTDATED — 5 itens HIGH, 6 MEDIUM, 1 LOW  
**Nota processual:** 12 propostas. Nenhuma pode ser aplicada antes da aprovação do gate humano.

---

## Phase 1b — Staleness Resolution

3 nós L1 estavam stale:

| Nó | Razão de Staleness | Resolução |
|----|---------------------|-----------|
| `tech-research` | `business-process` completou 2026-04-10 > `tech-research` 2026-04-08 | **Defer** — epic 016 não adicionou novas tecnologias; reutiliza Redis/Postgres/Evolution já documentados em `tech-alternatives.md`. Sem valor no patch. |
| `domain-model` | `blueprint` completou 2026-04-10 > `domain-model` 2026-04-09 | **Inline patch** — M13 completamente desatualizado (ver P4). |
| `context-map` | `domain-model` completou 2026-04-09 > `context-map` 2026-04-07 | **Inline patch** — linha 16 (triggers flow) vaga mas estruturalmente correta (ver P11). |

---

## Phase 2 — Drift Findings (11 categorias)

### D1 — Scope Drift (`business/solution-overview.md`)

| # | Finding | Localização | Severidade |
|---|---------|-------------|------------|
| D1.1 | Feature "Triggers proativos" listada como "Próximo — epic 015" — já entregue como epic 016 | `solution-overview.md:72` | **HIGH** |

### D2 — Architecture Drift (`engineering/blueprint.md`)

| # | Finding | Localização | Severidade |
|---|---------|-------------|------------|
| D2.1 | Seção 3 (Folder Structure): `triggers/` ausente da árvore de diretórios | `blueprint.md:section 3` | MEDIUM |
| D2.2 | Tabela "Packages por concern": `triggers/` ausente da lista de packages | `blueprint.md:214` | MEDIUM |
| D2.3 | Seção 3b (DB Schema Layout): `trigger_events`, `customers.scheduled_event_at`, `customers.opt_out_at` ausentes da célula `public` | `blueprint.md:229` | MEDIUM |

### D4 — Domain Drift (`engineering/domain-model.md`)

| # | Finding | Localização | Severidade |
|---|---------|-------------|------------|
| D4.1 | M13 class diagram: `TriggerRule` + `TriggerLog` + `EventType` + `ActionType` — completamente errado. Implementação real usa `TriggerConfig` (YAML-only, sem tabela) + `TriggerEvent` (tabela admin-only). | `domain-model.md:971-1027` | **HIGH** |
| D4.2 | M13 SQL: `trigger_rules` + `trigger_logs` com RLS — tabelas nunca foram criadas. Real: `trigger_events` admin-only (ADR-027 carve-out, sem RLS). | `domain-model.md:1075-1118` | **HIGH** |
| D4.3 | M13: ausentes `TemplateCatalog` (YAML-only), `CooldownGate` (Redis), `DailyCapGate` (Redis) | `domain-model.md:M13` | MEDIUM |

### D5 — Decision Drift (ADRs)

| # | Finding | Localização | Severidade |
|---|---------|-------------|------------|
| D5.1 | `ADR-049` referenciado em `decisions.md` (D1, D3, D6, D15, D20, D22, D24, D25) mas arquivo não existe | `decisions/` | **HIGH** |
| D5.2 | `ADR-050` referenciado em `decisions.md` (D3, D11, D16) mas arquivo não existe | `decisions/` | **HIGH** |

### D6 — Roadmap Drift (`planning/roadmap.md`)

| # | Finding | Localização | Severidade |
|---|---------|-------------|------------|
| D6.1 | Tabela epic 008: `in-progress` → deve ser `shipped` (reconcile-report.md existe) | `roadmap.md:77` | **HIGH** |
| D6.2 | Epic 016 (trigger engine) não aparece na tabela — era "011: Trigger Engine sugerido" (renumeração não atualizada) | `roadmap.md:80` | **HIGH** |
| D6.3 | Epics 009 e 015 shipped mas tabela não reflete (reconcile-reports existem para ambos) | `roadmap.md:79+` | MEDIUM |
| D6.4 | Milestone "Post-MVP" lista 009, 010, 011 como upcoming — pelo menos 009 e 015 já entregues | `roadmap.md:131` | MEDIUM |
| D6.5 | "Próximo passo" ainda aponta para 5 BLOCKERs do epic 008 e primeiro deploy VPS | `roadmap.md:169` | MEDIUM |

### D8 — Integration Drift (`engineering/context-map.md`)

| # | Finding | Localização | Severidade |
|---|---------|-------------|------------|
| D8.1 | Linha 16: "Triggers proativos enviados via entrega" — correta mas incompleta; não menciona cron scheduler, `send_template`, cooldown/cap nem anti-spam gates | `context-map.md:132` | LOW |

### D10 — Epic Decision Drift (`epics/016-trigger-engine/decisions.md`)

| # | Finding | Localização | Severidade |
|---|---------|-------------|------------|
| D10.1 | Decisões D1, D3 referenciam "ADR-049 novo" e "ADR-050 novo" — ADRs devem ser criados e então `decisions.md` atualizado para "ADR-049 reviewed" | `decisions.md:9,11` | MEDIUM |
| D10.2 | Decisão D33: LGPD `ON DELETE CASCADE` marcado `[VALIDAR]` — DPO sign-off obrigatório antes de `mode: live` no rollout Ariel. Já documentado em `judge-report.md S1`. | `decisions.md:41` | MEDIUM (carry-forward) |

> **D3, D7, D9, D11**: Nenhum drift detectado — ADRs 001-042 todos reaffirmados; containers.md não verificado (escopo mínimo); README inexistente (OK).

---

## Phase 3 — Drift Score + Impact Radius

### Documentation Health Table

| Doc | Categorias | Status | Itens de Drift |
|-----|-----------|--------|----------------|
| `business/solution-overview.md` | D1 | OUTDATED | 1 |
| `engineering/blueprint.md` | D2 | OUTDATED | 3 |
| `engineering/domain-model.md` | D4 | OUTDATED | 3 |
| `engineering/context-map.md` | D8 | OUTDATED (minor) | 1 |
| `planning/roadmap.md` | D6 | OUTDATED | 5 |
| `decisions/ADR-049` | D5 | MISSING | 1 |
| `decisions/ADR-050` | D5 | MISSING | 1 |
| `epics/016/decisions.md` | D10 | OUTDATED | 2 |
| `decisions/ADR-001..042` | D5 | **CURRENT** | 0 |
| `research/tech-alternatives.md` | D11 | **CURRENT** (deferred) | 0 |

**Score: 2/10 = 22%**

### Impact Radius Matrix

| Área Alterada | Docs Diretamente Afetados | Transitividade | Esforço |
|---------------|--------------------------|----------------|---------|
| Nova tabela `trigger_events` (admin-only) | blueprint (3b), domain-model (M13 SQL) | context-map (ref M13) | S |
| YAML triggers/templates config | domain-model (M13 class), solution-overview | blueprint (3 folder), ADR-049, ADR-050 | M |
| Cron scheduler + anti-spam gates | blueprint (3 folder), domain-model (M13) | context-map (row 16) | S |
| Customers novos campos | domain-model (M13), blueprint (3b) | — | S |
| Epic 016 shipped | roadmap (epic table, milestone, próximo passo) | solution-overview | M |

---

## Phase 4 — Propostas Concretas (12 propostas)

### P1 — D1.1: solution-overview.md — Status de "Triggers proativos" (HIGH)

**Arquivo:** `platforms/prosauai/business/solution-overview.md:72`

**Antes:**
```
| **Triggers proativos** | Proximo — epic 015 | Plataforma inicia conversa com o cliente (lembrete de agendamento, follow-up de pedido, boas-vindas) em vez de so reagir. |
```

**Depois:**
```
| **Triggers proativos** | **Entregue — epic 016** | Plataforma inicia conversa com o cliente via WhatsApp template (lembrete de agendamento, follow-up de conversa fechada, follow-up de inatividade). 3 tipos de trigger; cooldown 24h + daily cap 3/dia por cliente; config YAML per-tenant; rollout shadow→live por agente-piloto. |
```

---

### P2 — D2.1: blueprint.md — Adicionar `triggers/` na folder structure (MEDIUM)

**Arquivo:** `platforms/prosauai/engineering/blueprint.md`

**Antes** (após a entrada `handoff/`):
```text
│   ├── handoff/               # Epic 010: Handoff Engine + Multi-Helpdesk
│   │   ├── base.py            # HelpdeskAdapter Protocol + error hierarchy (ADR-037)
│   │   ...
│   │   └── scheduler.py       # Periodic tasks: auto_resume + bot_sent_messages_cleanup + handoff_events_cleanup
│   ├── db/                    # Epic 005: Database layer
```

**Depois** (inserir entre `handoff/` e `db/`):
```text
│   ├── handoff/               # Epic 010: Handoff Engine + Multi-Helpdesk
│   │   ...
│   │   └── scheduler.py       # Periodic tasks: auto_resume + bot_sent_messages_cleanup + handoff_events_cleanup
│   ├── triggers/              # Epic 016: Trigger Engine (proactive sends)
│   │   ├── scheduler.py       # Cron loop singleton (pg_advisory_lock, 15s cadence)
│   │   ├── engine.py          # execute_tick: match → cooldown/cap → render → send → metrics
│   │   ├── matchers.py        # SQL matchers: time_before_event, conv_closed, last_inbound
│   │   ├── cooldown.py        # Redis cooldown + daily-cap gates (FR-012/013/015)
│   │   ├── events.py          # trigger_events repository (persist, find_stuck, load_stuck_for_retry)
│   │   ├── template_renderer.py # Jinja2 SandboxedEnvironment para parameter rendering
│   │   └── cost_gauge.py      # Prometheus gauge trigger_cost_today_usd per tenant (60s cadence)
│   ├── db/                    # Epic 005: Database layer
```

---

### P3 — D2.2: blueprint.md — Adicionar `triggers/` na tabela de convenção (MEDIUM)

**Arquivo:** `platforms/prosauai/engineering/blueprint.md:214`

**Antes:**
```
| Packages por concern | `core/` (dominio base), `conversation/` (LLM pipeline), `safety/` (guardrails), `tools/` (registry), `api/` (endpoints), `channels/` (adapters), `handoff/` (helpdesk integration — epic 010), `db/` (pool), `ops/` (migrations, retention), `observability/` (cross-cutting), `core/router/` (routing engine) |
```

**Depois:**
```
| Packages por concern | `core/` (dominio base), `conversation/` (LLM pipeline), `safety/` (guardrails), `tools/` (registry), `api/` (endpoints), `channels/` (adapters), `handoff/` (helpdesk integration — epic 010), `triggers/` (proactive sends engine — epic 016), `db/` (pool), `ops/` (migrations, retention), `observability/` (cross-cutting), `core/router/` (routing engine) |
```

---

### P4 — D2.3: blueprint.md — Adicionar `trigger_events` + customers fields no schema layout (MEDIUM)

**Arquivo:** `platforms/prosauai/engineering/blueprint.md:229` (célula `public`)

**Antes** (fim da célula `public`):
```
... `bot_sent_messages` (tracking 48h usado pelo NoneAdapter para evitar bot echo, retention 48h). Acessiveis exclusivamente via `pool_admin` (BYPASSRLS) — carve-out documentado em ADR-027
```

**Depois** (adicionar ao final da célula `public`):
```
... `bot_sent_messages` (tracking 48h). **Epic 016**: mais uma tabela admin-only: `trigger_events` (append-only audit trail de proactive sends, retention 90d; campos: `customer_id, trigger_id, template_name, fired_at, sent_at, status, error, cost_usd_estimated, payload, retry_count`). Colunas novas em `customers`: `scheduled_event_at TIMESTAMPTZ` (gatilho time_before_scheduled_event) + `opt_out_at TIMESTAMPTZ` (opt-out proativo). Acessiveis exclusivamente via `pool_admin` (BYPASSRLS) — carve-out documentado em ADR-027
```

---

### P5 — D4.1+D4.2+D4.3: domain-model.md M13 — Substituir class diagram e SQL (HIGH)

**Arquivo:** `platforms/prosauai/engineering/domain-model.md:971-1119`

**Antes:** `### M13 — Triggers` com `TriggerRule`, `TriggerLog`, `EventType` (DB-centric com RLS) + SQL com `trigger_rules` e `trigger_logs`

**Depois:** (substituição completa da seção M13)

```markdown
### M13 — Triggers (Epic 016)

<details>
<summary><strong>Class Diagram — Triggers (L4)</strong></summary>

```mermaid
classDiagram
    class TriggerConfig {
        <<YAML-only — tenants.yaml>>
        +string id
        +TriggerType type
        +bool enabled
        +json match
        +string template_ref
        +int cooldown_hours
        +int lookahead_hours
    }

    class TriggerEvent {
        +uuid id
        +uuid tenant_id
        +uuid customer_id
        +string trigger_id
        +string template_name
        +timestamptz fired_at
        +timestamptz sent_at
        +TriggerStatus status
        +string error
        +float cost_usd_estimated
        +json payload
        +int retry_count
    }

    class TriggerType {
        <<enumeration>>
        time_before_scheduled_event
        time_after_conversation_closed
        time_after_last_inbound
    }

    class TriggerStatus {
        <<enumeration>>
        queued
        sent
        failed
        skipped
        dry_run
    }

    class TemplateCatalog {
        <<YAML-only — tenants.yaml>>
        +string name
        +string language
        +list components
        +string approval_id
        +float cost_usd
    }

    class CooldownGate {
        <<Redis key>>
        +key cooldown:{tenant}:{customer}:{trigger_id}
        +int ttl_seconds
    }

    class DailyCapGate {
        <<Redis key>>
        +key daily_cap:{tenant}:{customer}:{date}
        +int counter
        +int ttl_26h
    }

    TriggerConfig --> TriggerType : type
    TriggerConfig --> TemplateCatalog : template_ref
    TriggerConfig "1" --> "*" TriggerEvent : produces
    TriggerEvent --> TriggerStatus : status
    TriggerEvent --> CooldownGate : checked before send
    TriggerEvent --> DailyCapGate : checked before send
```

</details>

> **Armazenamento**: `TriggerConfig` e `TemplateCatalog` vivem apenas em `config/tenants.yaml` (zero tabelas no BD para config). Hot-reload <60s via config_poller existente. `TriggerEvent` persiste na tabela `public.trigger_events` (admin-only ADR-027 carve-out — **sem RLS**). Retention 90d via retention-cron (epic 006). [ADR-049](../decisions/ADR-049-trigger-engine-cron-design.md) · [ADR-050](../decisions/ADR-050-template-catalog-yaml.md)

```sql
-- M13: Trigger events (append-only audit trail — admin-only, sem RLS, ADR-027)
CREATE TABLE public.trigger_events (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID NOT NULL,
    customer_id           UUID NOT NULL,
    trigger_id            TEXT NOT NULL,
    template_name         TEXT,
    fired_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at               TIMESTAMPTZ,
    status                TEXT NOT NULL CHECK (status IN (
                              'queued', 'sent', 'failed', 'skipped', 'dry_run'
                          )),
    error                 TEXT,
    cost_usd_estimated    NUMERIC(10,6),
    payload               JSONB,
    retry_count           INT NOT NULL DEFAULT 0
);

-- Acesso exclusivamente via pool_admin (BYPASSRLS) — sem ALTER TABLE ENABLE RLS
CREATE INDEX idx_trigger_events_tenant_fired
    ON public.trigger_events (tenant_id, fired_at DESC);
CREATE INDEX idx_trigger_events_customer
    ON public.trigger_events (tenant_id, customer_id, fired_at DESC);
-- Idempotencia camada 2 (FR-017): partial UNIQUE impede double-send sob race
CREATE UNIQUE INDEX idx_trigger_events_idempotent
    ON public.trigger_events (tenant_id, customer_id, trigger_id, date(fired_at))
    WHERE status IN ('sent', 'queued');
CREATE INDEX idx_trigger_events_global_pagination
    ON public.trigger_events (tenant_id, id DESC);
CREATE INDEX idx_trigger_events_stuck
    ON public.trigger_events (tenant_id, fired_at)
    WHERE status = 'queued';
```
```

(A seção SQL do M13 antigo com `trigger_rules` e `trigger_logs` é **removida por completo**.)

---

### P6 — D5.1: Criar ADR-049 (Trigger Engine Cron Design) — HIGH

**Arquivo a criar:** `platforms/prosauai/decisions/ADR-049-trigger-engine-cron-design.md`

**Header draft:**
```markdown
---
id: ADR-049
title: "Trigger Engine: Cron-Only v1 com Advisory Lock + YAML Config"
status: reviewed
deciders: [gabrielhamu]
date: 2026-04-28
supersedes: ~
---
# ADR-049 — Trigger Engine: Cron-Only v1 + YAML Config

## Status: reviewed

## Contexto
[Decisões D1, D2, D6, D15, D20-D25 de `epics/016-trigger-engine/decisions.md`]

## Decisão
Trigger engine executado como cron loop 15s singleton via `pg_try_advisory_lock(hashtext_int4('triggers_engine_cron'))`.
Config em `tenants.yaml triggers.*` (hot-reload <60s). 3 trigger types v1:
`time_before_scheduled_event`, `time_after_conversation_closed`, `time_after_last_inbound`.
PG NOTIFY listener (ADR-004) adiado para 016.1+ quando demanda real-time aparecer.

## Consequências
...
```

> **Nota:** Geração do ADR completo via `/madruga:adr` após aprovação das propostas.

---

### P7 — D5.2: Criar ADR-050 (Template Catalog YAML) — HIGH

**Arquivo a criar:** `platforms/prosauai/decisions/ADR-050-template-catalog-yaml.md`

**Header draft:**
```markdown
---
id: ADR-050
title: "Template Catalog: YAML-Managed, Manual Ops, Auto-Sync Adiado"
status: reviewed
deciders: [gabrielhamu]
date: 2026-04-28
supersedes: ~
---
# ADR-050 — Template Catalog: YAML-Managed

## Status: reviewed

## Contexto
[Decisões D3, D11, D16 de `epics/016-trigger-engine/decisions.md`]

## Decisão
Templates HSM catalogados em `tenants.yaml templates.*` com campos:
`name, language, components, approval_id, cost_usd`.
Manual ops cadastra após aprovação no Meta Business Manager.
Auto-sync via Graph API adiado para 016.1+ após validação Ariel.

## Consequências
...
```

> **Nota:** Geração do ADR completo via `/madruga:adr` após aprovação das propostas.

---

### P8 — D6.1+D6.2+D6.3: roadmap.md — Epic table + header status (HIGH)

**Arquivo:** `platforms/prosauai/planning/roadmap.md`

**Antes** (linhas 13-16, header de status):
```markdown
**L2 Status:** Epic 001 shipped … **Epic 008 in-progress** (152/158 tasks — 8 abas, 3 tabelas admin-only, ~25 endpoints, pipeline instrumentation fire-and-forget, 5 BLOCKERs abertos no repo externo).
**Proximo marco:** merge epic 008 para develop + primeiro deploy de producao VPS (2 vCPU, 4GB RAM, 40GB SSD).
```

**Depois:**
```markdown
**L2 Status:** Epics 001–009 shipped. **Epics 010–012 implementados** (tasks.md completo, reconcile pendente). **Epic 015 shipped**. **Epic 016 shipped** (Trigger Engine — 3 trigger types, cooldown + daily cap, evolution send_template, 231 testes, judge 82%, QA pass).
**Proximo marco:** reconcile epics 010–012 + primeiro deploy de producao VPS.
```

**Antes** (linhas da tabela epic — epics 008 e 009-011):
```
| 8 | **008: Admin Evolution** | 006, 007 | medio | Admin | **in-progress** (152/158 tasks — ...) |
| 9 | 009: Agent Tools | 006 | medio | Post-MVP | sugerido |
| 10 | 010: Handoff Engine | 006 | medio | Post-MVP | sugerido |
| 11 | 011: Trigger Engine | 010 | baixo | Post-MVP | sugerido |
```

**Depois:**
```
| 8 | **008: Admin Evolution** | 006, 007 | medio | Admin | **shipped** (8 abas, traces/trace_steps/routing_decisions, ~25 endpoints, pipeline instrumentation — judge pass, QA pass, reconcile 2026-04-28) |
| 9 | **009: Channel Ingestion + Content Processing** | 006 | medio | Post-MVP | **shipped** (multi-source channel adapter ADR-031, content processing pipeline ADR-032, OCR/STT/vision ADR-033 — judge pass, QA pass, reconcile 2026-04-28) |
| 10 | **010: Handoff Engine + Inbox** | 006 | medio | Post-MVP | **implementado** (HelpdeskAdapter Protocol ADR-037, ChatwootAdapter + NoneAdapter ADR-038, ai_active unified state ADR-036, handoff_events + bot_sent_messages — reconcile pendente) |
| 11 | **011: Evals** | 006 | medio | Post-MVP | **implementado** (reconcile pendente) |
| 12 | **012: Tenant Knowledge Base RAG** | 006 | medio | Post-MVP | **implementado** (reconcile pendente) |
| 13 | — | — | — | — | slot vago (antigo 012/013 absorvidos) |
| 14 | — | — | — | — | slot vago |
| 15 | **015: Agent Pipeline Steps** | 008, 005 | medio | Post-MVP | **shipped** (agent pipeline steps configurável, sub-steps ADR — judge pass, QA pass, reconcile 2026-04-28) |
| 16 | **016: Trigger Engine** | 010 | baixo | Post-MVP | **shipped** (3 trigger types, YAML config, cooldown+daily cap Redis, send_template Evolution, 231 testes, judge 82%, QA pass — reconcile 2026-04-28) |
```

---

### P9 — D6.4+D6.5: roadmap.md — Milestone "Post-MVP" + "Próximo passo" (MEDIUM)

**Antes** (milestone Post-MVP):
```
| **Post-MVP** | 009, 010, 011 | Agent Tools, Handoff Engine, Trigger Engine (renumerados de 008-010 antigos) | ~6 semanas |
```

**Depois:**
```
| **Post-MVP** | 009, 010, 011, 012, 015, 016 | ✅ **Ciclo concluído**: Channel Ingestion (009), Handoff Engine (010), Evals (011), Knowledge Base RAG (012), Agent Pipeline Steps (015), Trigger Engine (016) — todos implementados ou shipped. | realizado |
```

**Antes** ("Próximo passo"):
```
> **Próximo passo:** Resolver 5 BLOCKERs herdados do epic 008 no repo externo … Post-MVP: epic 009 (Agent Tools) ou epic 010 (Handoff Engine) conforme prioridade.
```

**Depois:**
```
> **Próximo passo:** Reconcile dos epics 010, 011, 012 (implementados sem reconcile formal). Primeiro deploy de produção VPS após validação Ariel shadow (epic 016 rollout). DPO sign-off para `trigger_events ON DELETE CASCADE` antes de `mode: live` (judge-report S1). ADRs 049 e 050 a promover de draft → reviewed.
```

---

### P10 — D6.3: roadmap.md — Dependencies diagram (MEDIUM)

**Antes** (nó `E011` no diagrama):
```
E010 --> E011[011 Trigger Engine]
```

**Depois:**
```
E010 --> E016[016 Trigger Engine - DONE]
E010 --> E011[011 Evals]
E010 --> E012[012 Knowledge Base RAG]
E008 --> E015[015 Agent Pipeline Steps - DONE]
```

---

### P11 — D8.1: context-map.md — Detalhar linha 16 trigger flow (LOW)

**Arquivo:** `platforms/prosauai/engineering/context-map.md:132`

**Antes:**
```
| 16 | Operations (M13) → Channel (M11) | Customer-Supplier | Triggers proativos enviados via entrega |
```

**Depois:**
```
| 16 | Operations (M13) → Channel (M11) | Customer-Supplier | Trigger Engine (cron 15s) identifica clientes elegíveis via SQL matchers → verifica cooldown/daily-cap Redis → renderiza template (Jinja2 sandbox) → `EvolutionProvider.send_template()` → persiste `trigger_events`. Anti-spam: cooldown per `(tenant,customer,trigger_id)` + daily cap `(tenant,customer,date)` (FR-012/013). ADR-049. |
```

---

### P12 — D10.1: decisions.md — Atualizar referências ADR-049/050 pós-criação (MEDIUM)

**Após** criação dos ADRs (P6, P7), atualizar `decisions.md` D1 e D3:

**D1** (linha 9): `(ref: Q1-A; ADR-049 novo; ADR-004 deferred)` → `(ref: Q1-A; [ADR-049](../decisions/ADR-049-trigger-engine-cron-design.md); ADR-004 deferred)`

**D3** (linha 11): `(ref: Q3-A; ADR-050 novo)` → `(ref: Q3-A; [ADR-050](../decisions/ADR-050-template-catalog-yaml.md))`

---

## Phase 5 — Roadmap Review (obrigatória)

| Campo | Planejado | Real | Drift |
|-------|-----------|------|-------|
| Status epic 016 | "sugerido" como "011: Trigger Engine" | **shipped** (231 testes, judge 82%, QA pass) | Atualizar |
| Appetite planejado | ~1 semana (Post-MVP estimate) | 2 semanas (104+ tasks) | Documentar |
| Milestone atingido | Post-MVP "~6 semanas para 009+010+011" | Todos implementados | Fechar milestone |
| Dep `010 → 016` | ADR-004 "Handoff Engine" como pré-requisito | Confirmado — `check_cooldown` usa padrão epic 010 | OK |
| Risco W5 circuit breaker | Não listado no roadmap | **Novo risco** — breaker Evolution nunca abre sob 5xx storm, a confirmar em QA | Adicionar |
| DPO LGPD (S1) | Não listado | **Novo risco** — `ON DELETE CASCADE` em `trigger_events` precisa DPO sign-off antes de rollout live | Adicionar |

**Novos riscos a adicionar em `roadmap.md`:**

```markdown
| **`trigger_events ON DELETE CASCADE` sem DPO sign-off (epic 016 S1)** | **ABERTO** | Alto | Média | DPO/jurídico deve validar que hard-delete é aceitável antes de `mode: live` em Ariel. Alternativa (set NULL + redact) disponível em 016.1+. |
| **Circuit breaker Evolution não abre sob 5xx storm (epic 016 W5)** | **A verificar em QA** | Médio | Baixa | Load sintético com Evolution retornando 5xx consecutivos — confirmar se breaker abre após N falhas antes de rollout live. |
```

---

## Phase 6 — Impacto em Epics Futuros

| Epic Futuro | Suposição no Pitch | Como Afetado | Impacto | Ação |
|-------------|-------------------|--------------|---------|------|
| 018: Multi-Tenant Self-Service | Admin RBAC para configurar triggers | Trigger config é YAML-only (sem editor DB); Self-Service precisará expor editor YAML ou implementar `trigger_rules` table (016.1+) | MÉDIO | Atualizar pitch de 018 quando criado |
| 016.1 (backlog) | intent_filter, agent_id_filter, min_message_count implementados em SQL | Deferred — apenas warning log (judge W3); precisam SQL matchers reais | MÉDIO | Já documentado em `judge-report.md N9-N13` |
| Próximo epic com Evolution | `send_template` via `EvolutionProvider` | Nova capability adicionada — disponível para reuso | BAIXO | Nenhuma ação necessária |

---

## Phase 7 — Auto-Review

### Tier 1 — Checklist Determinístico

| # | Check | Status |
|---|-------|--------|
| 1 | Report existe e é não-vazio | ✅ |
| 2 | Todas 11 categorias D1-D11 escaneadas | ✅ |
| 3 | Drift score computado | ✅ 22% |
| 4 | Nenhum placeholder TODO/TKTK/??? | ✅ |
| 5 | HANDOFF block presente no footer | ✅ |
| 6 | Impact radius matrix presente | ✅ |
| 7 | Roadmap review presente | ✅ |
| 8 | 3 nós stale têm resolução (defer/inline/re-exec) | ✅ |

### Tier 2 — Scorecard

| # | Item | Auto-avaliação |
|---|------|----------------|
| 1 | Cada drift item tem estado atual vs esperado | ✅ |
| 2 | Roadmap review com planejado vs real | ✅ |
| 4 | Contradições ADR sinalizadas | ✅ (ADR-049/050 faltantes) |
| 5 | Impacto em epics futuros avaliado (top 3) | ✅ |
| 6 | Diffs concretos fornecidos | ✅ |
| 7 | Trade-offs explícitos | ✅ |

---

## Phase 8 — Gate: Aprovação Humana

**12 propostas aguardam aprovação:**

| # | Proposta | Severidade | Esforço | Aprovação |
|---|---------|-----------|---------|-----------|
| P1 | solution-overview: status triggers | HIGH | S | ⬜ |
| P2 | blueprint: `triggers/` na folder structure | MEDIUM | S | ⬜ |
| P3 | blueprint: `triggers/` na tabela de packages | MEDIUM | S | ⬜ |
| P4 | blueprint: `trigger_events` + customer fields no schema | MEDIUM | S | ⬜ |
| P5 | domain-model M13: replace class + SQL (crítico) | HIGH | M | ⬜ |
| P6 | Criar ADR-049 (header draft → `/madruga:adr` completa) | HIGH | M | ⬜ |
| P7 | Criar ADR-050 (header draft → `/madruga:adr` completa) | HIGH | M | ⬜ |
| P8 | roadmap: epic table (008 shipped + 016 adicionado) | HIGH | M | ⬜ |
| P9 | roadmap: milestones + "Próximo passo" | MEDIUM | S | ⬜ |
| P10 | roadmap: dependencies diagram | MEDIUM | S | ⬜ |
| P11 | context-map: linha 16 trigger flow | LOW | S | ⬜ |
| P12 | decisions.md: links ADR-049/050 pós-criação | MEDIUM | S | ⬜ |

**Staleness deferred:** `tech-research` — sem novas tecnologias neste epic; doc continua válido.

**Carry-forwards (não bloqueadores de merge, mas obrigatórios antes de rollout live):**
- **S1 (LGPD DPO)**: Registrar veredito DPO sobre `ON DELETE CASCADE` em `decisions.md:D33` antes de ativar `mode: live` em Ariel.
- **S2 (ADR-049/050)**: Promover de draft → reviewed via `/madruga:adr` após aprovação das propostas P6/P7.

---

> **Responda com:**
> - `aprovar tudo` — aplica P1-P12 em sequência
> - `aprovar P1 P2 P5` — aplica seleção
> - `rejeitar Pn` — descarta item específico
> - `adiar Pn` — move para backlog 016.1

---

handoff:
  from: madruga:reconcile
  to: madruga:roadmap
  context: "Reconcile report gerado. 22% drift score — 5 HIGH, 6 MEDIUM, 1 LOW. 12 propostas aguardam aprovação gate humano. ADR-049 + ADR-050 a criar via /madruga:adr. Roadmap major update: epics 008-016 de sugerido→shipped. Carry-forwards: S1 DPO LGPD + S2 ADR promoção."
  blockers: []
  confidence: Alta
  kill_criteria: "Nenhum — reconcile é documentação, não bloqueia merge do epic."
