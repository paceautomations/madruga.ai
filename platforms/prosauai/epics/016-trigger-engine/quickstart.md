# Quickstart — Epic 016 Trigger Engine

**Phase 1 output**. Setup local + validacao end-to-end das 5 user stories da spec.

> Pre-condicao: estar no branch `epic/prosauai/016-trigger-engine` no clone `paceautomations/prosauai` (CWD do dev). Migrations PR-A.1 ja commitadas.

---

## 1. Setup local

### 1.1 Stack docker-compose (recomendado para validacao manual)

```bash
cd ~/repos/paceautomations/prosauai
git checkout epic/prosauai/016-trigger-engine

# Levantar PG 15 + Redis + FastAPI + Phoenix
docker compose up -d postgres redis phoenix

# Aplicar migrations (incluindo as 4 novas do epic 016)
make migrate

# Verificar trigger_events table created
docker compose exec postgres psql -U postgres -d prosauai \
    -c "\d public.trigger_events"

# Verificar customers ALTER aplicado
docker compose exec postgres psql -U postgres -d prosauai \
    -c "\d public.customers" | grep -E "scheduled_event_at|opt_out_at"
```

### 1.2 Stack testcontainers (para suite automatizada)

```bash
# Roda automaticamente via pytest fixtures
cd apps/api
pytest tests/triggers/ -v
```

---

## 2. Seed Ariel + 1 trigger + 1 template (PR-A dry_run mode)

### 2.1 Editar `tenants.yaml` para adicionar Ariel triggers/templates

```yaml
# tenants.yaml — apos epic 015 layout
ariel:
  # ... existing fields (epic 003+) ...
  phone_number_id: "abc123def"
  evolution_instance: "ariel-prod"

  # NEW (epic 016)
  triggers:
    enabled: true
    cadence_seconds: 15
    cost_gauge_cadence_seconds: 60
    daily_cap_per_customer: 3
    list:
      - id: ariel_match_reminder
        type: time_before_scheduled_event
        enabled: true
        mode: dry_run                    # SHADOW MODE — sem real send
        lookahead_hours: 1
        cooldown_hours: 24
        template_ref: match_reminder_pt
        match:
          intent_filter: any
          agent_id_filter: any
          consent_required: true

  templates:
    match_reminder_pt:
      name: ariel_match_reminder        # Meta template name (post-approval)
      language: pt_BR
      components:
        - type: body
          parameters:
            - type: text
              ref: "{{ customer.name }}"
            - type: text
              ref: "{{ customer.scheduled_event_at | format_time }}"
      approval_id: meta_approval_xyz123
      cost_usd: 0.0085
```

### 2.2 Verificar Pydantic validation startup

```bash
# Reiniciar FastAPI — deve nascer sem erro
docker compose restart api
docker compose logs api --tail=50

# Procurar log:
# {"event": "triggers_config_loaded", "tenant": "ariel", "trigger_count": 1, "template_count": 1}
# Se houver template_ref orfao, log: {"event": "triggers_config_invalid", "error": "template_ref 'XYZ' not found in templates.*"}
# E processo nao sobe (FR-042).
```

---

## 3. Seed customers de teste

### 3.1 Inserir 4 customers (ResenhAI Ariel) com `scheduled_event_at` em diferentes janelas

```bash
docker compose exec postgres psql -U postgres -d prosauai <<EOF
-- Customer A: jogo em 50 min (DENTRO da janela lookahead_hours=1)
INSERT INTO customers (tenant_id, phone_number_e164, name, scheduled_event_at)
VALUES (
  '00000000-0000-0000-0000-000000000001'::uuid,  -- Ariel tenant_id
  '+5521987654321',
  'Joao Customer A',
  NOW() + INTERVAL '50 minutes'
);

-- Customer B: jogo em 25 horas (FORA — alem do lookahead)
INSERT INTO customers (tenant_id, phone_number_e164, name, scheduled_event_at)
VALUES (
  '00000000-0000-0000-0000-000000000001'::uuid,
  '+5521987654322',
  'Pedro Customer B',
  NOW() + INTERVAL '25 hours'
);

-- Customer C: jogo em 30 min (DENTRO da janela ainda — lookahead inclui ate +1h)
INSERT INTO customers (tenant_id, phone_number_e164, name, scheduled_event_at)
VALUES (
  '00000000-0000-0000-0000-000000000001'::uuid,
  '+5521987654323',
  'Maria Customer C',
  NOW() + INTERVAL '30 minutes'
);

-- Customer D: jogo em 50 min mas opt_out_at SET (DEVE SER EXCLUIDO)
INSERT INTO customers (tenant_id, phone_number_e164, name, scheduled_event_at, opt_out_at)
VALUES (
  '00000000-0000-0000-0000-000000000001'::uuid,
  '+5521987654324',
  'Ana Customer D OPTED OUT',
  NOW() + INTERVAL '50 minutes',
  NOW() - INTERVAL '7 days'
);
EOF
```

---

## 4. Validar US1 — Lembrete antes de jogo (dry_run mode)

### 4.1 Aguardar proximo cron tick (max 15s)

```bash
# Logs em tempo real
docker compose logs -f api 2>&1 | grep -E "trigger_(cron|tick|matched|skipped)"

# Esperado em 1 tick:
# {"event": "trigger.cron.tick", "tenant_count": 1, "trigger_count": 1, "tick_duration_ms": 234}
# {"event": "trigger.match.completed", "tenant": "ariel", "trigger_id": "ariel_match_reminder", "candidates_matched": 2}
#   (customer A + customer C dentro de janela; B fora; D excluido por opt_out)
```

### 4.2 Verificar persistencia em `trigger_events`

```bash
docker compose exec postgres psql -U postgres -d prosauai <<EOF
SELECT te.id, c.name, te.trigger_id, te.template_name, te.status, te.error,
       te.cost_usd_estimated, te.fired_at, te.retry_count
FROM trigger_events te
JOIN customers c ON c.id = te.customer_id
WHERE te.tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
ORDER BY te.fired_at DESC;
EOF
```

**Esperado**:
- 2 rows com `status='dry_run'` (customer A + customer C — dentro da janela)
- 0 rows para customer B (matcher exclui — fora da janela)
- 0 rows para customer D (matcher exclui — opt_out_at IS NOT NULL)

### 4.3 Verificar Prometheus counters

```bash
curl -s http://localhost:8050/metrics | grep -E "trigger_(executions|skipped)_total"
```

**Esperado**:
```
trigger_executions_total{tenant="ariel",trigger_id="ariel_match_reminder",status="dry_run"} 2
trigger_skipped_total{tenant="ariel",trigger_id="ariel_match_reminder",reason="opt_out"} 1
```

### 4.4 Verificar idempotencia

Aguardar 30s (proximo cron tick):

```bash
# Mesmo SELECT
# Esperado: AINDA 2 rows (idempotency dia: nao duplicate)
# Logs: {"event": "trigger_skipped", "reason": "idempotent", ...}
```

---

## 5. Validar US2 — Re-engagement apos conversa fechada

### 5.1 Adicionar trigger `consult_reminder` em `tenants.yaml`

```yaml
ariel:
  triggers:
    list:
      # ... ariel_match_reminder ...
      - id: consult_reminder
        type: time_after_conversation_closed
        enabled: true
        mode: dry_run
        lookahead_hours: 24
        cooldown_hours: 168              # 1 semana
        template_ref: consult_reminder_pt
        match:
          consent_required: true
  templates:
    # ... match_reminder_pt ...
    consult_reminder_pt:
      name: consult_reminder
      language: pt_BR
      components:
        - type: body
          parameters:
            - type: text
              ref: "{{ customer.name }}"
      approval_id: meta_approval_xyz789
      cost_usd: 0.0085
```

Aguardar hot reload <60s.

### 5.2 Seed conversation closed em janela

```bash
docker compose exec postgres psql -U postgres -d prosauai <<EOF
-- Pegar customer A
INSERT INTO conversations (tenant_id, customer_id, ai_active, closed_at)
VALUES (
  '00000000-0000-0000-0000-000000000001'::uuid,
  (SELECT id FROM customers WHERE phone_number_e164='+5521987654321'),
  TRUE,
  NOW() - INTERVAL '24 hours'      -- DENTRO janela
);
EOF
```

### 5.3 Aguardar tick + verificar

```sql
SELECT trigger_id, COUNT(*) FROM trigger_events GROUP BY trigger_id;
-- Esperado: ariel_match_reminder=2, consult_reminder=1
```

---

## 6. Validar US3 — Abandoned cart (time_after_last_inbound)

### 6.1 Adicionar trigger `cart_recovery` + template em `tenants.yaml`

```yaml
ariel:
  triggers:
    list:
      # ... ariel_match_reminder + consult_reminder ...
      - id: cart_recovery
        type: time_after_last_inbound
        enabled: true
        mode: dry_run                    # SHADOW MODE — sem real send
        lookahead_hours: 48
        cooldown_hours: 72               # 3 dias entre tentativas
        template_ref: cart_recovery_pt
        match:
          consent_required: true
  templates:
    # ... match_reminder_pt + consult_reminder_pt ...
    cart_recovery_pt:
      name: cart_recovery
      language: pt_BR
      components:
        - type: body
          parameters:
            - type: text
              ref: "{{ customer.name | default('cliente') }}"
      approval_id: meta_approval_xyz_us3
      cost_usd: 0.0085
```

Aguardar hot reload <60s — `config_poller` aplica sem restart.

### 6.2 Seed conversas + mensagens inbound em diferentes janelas

Os 4 customers (A, B, C, D) ja existem do §3. Agora cada um precisa de
uma conversa + mensagens inbound para testar a janela de 48h:

```bash
docker compose exec postgres psql -U postgres -d prosauai <<EOF
-- Customer A: ultima inbound ha 48h05min em conv aberta ai_active=true → MATCH.
WITH conv_a AS (
    INSERT INTO conversations (tenant_id, customer_id, agent_id, status, ai_active, closed_at)
    VALUES (
      '00000000-0000-0000-0000-000000000001'::uuid,
      (SELECT id FROM customers WHERE phone_number_e164='+5521987654321'),
      '00000000-0000-0000-0000-000000000010'::uuid,  -- placeholder agent_id
      'active', TRUE, NULL
    ) RETURNING id, tenant_id
)
INSERT INTO messages (tenant_id, conversation_id, direction, content, created_at)
SELECT tenant_id, id, 'inbound', 'Tenho duvida no produto X', NOW() - INTERVAL '48 hours 5 minutes'
FROM conv_a;

-- Customer B: ultima inbound ha 48h05min mas conversa CLOSED → SKIP.
WITH conv_b AS (
    INSERT INTO conversations (tenant_id, customer_id, agent_id, status, ai_active, closed_at)
    VALUES (
      '00000000-0000-0000-0000-000000000001'::uuid,
      (SELECT id FROM customers WHERE phone_number_e164='+5521987654322'),
      '00000000-0000-0000-0000-000000000010'::uuid,
      'closed', TRUE, NOW() - INTERVAL '2 hours'
    ) RETURNING id, tenant_id
)
INSERT INTO messages (tenant_id, conversation_id, direction, content, created_at)
SELECT tenant_id, id, 'inbound', 'Pergunta sobre produto Y', NOW() - INTERVAL '48 hours 5 minutes'
FROM conv_b;

-- Customer C: ultima inbound ha 48h05min mas ai_active=false (handoff) → SKIP.
WITH conv_c AS (
    INSERT INTO conversations (
      tenant_id, customer_id, agent_id, status, ai_active,
      ai_muted_reason, ai_muted_at, closed_at
    )
    VALUES (
      '00000000-0000-0000-0000-000000000001'::uuid,
      (SELECT id FROM customers WHERE phone_number_e164='+5521987654323'),
      '00000000-0000-0000-0000-000000000010'::uuid,
      'active', FALSE,
      'manual_toggle', NOW() - INTERVAL '1 hour', NULL
    ) RETURNING id, tenant_id
)
INSERT INTO messages (tenant_id, conversation_id, direction, content, created_at)
SELECT tenant_id, id, 'inbound', 'Quero falar com humano', NOW() - INTERVAL '48 hours 5 minutes'
FROM conv_c;

-- Customer D ja foi opted out em §3 — mesmo seedando uma conv aberta + msg
-- inbound em janela, o matcher vai filtrar via opt_out_at IS NULL.
WITH conv_d AS (
    INSERT INTO conversations (tenant_id, customer_id, agent_id, status, ai_active, closed_at)
    VALUES (
      '00000000-0000-0000-0000-000000000001'::uuid,
      (SELECT id FROM customers WHERE phone_number_e164='+5521987654324'),
      '00000000-0000-0000-0000-000000000010'::uuid,
      'active', TRUE, NULL
    ) RETURNING id, tenant_id
)
INSERT INTO messages (tenant_id, conversation_id, direction, content, created_at)
SELECT tenant_id, id, 'inbound', 'Comprar produto Z?', NOW() - INTERVAL '48 hours 5 minutes'
FROM conv_d;
EOF
```

### 6.3 Aguardar tick + validar persistencia exclusivamente para customer A

```bash
docker compose logs -f api 2>&1 | grep -E "trigger_(cron|tick|matched|skipped).*cart_recovery"

# Esperado em 1 tick:
# {"event": "trigger.match.completed", "trigger_id": "cart_recovery", "candidates_matched": 1}
```

```sql
SELECT te.id, c.name, te.trigger_id, te.status, te.error, te.fired_at
FROM trigger_events te
JOIN customers c ON c.id = te.customer_id
WHERE te.trigger_id = 'cart_recovery'
ORDER BY te.fired_at DESC;
```

**Esperado**:
- 1 row `status='dry_run'` para customer A (`+5521987654321`)
- 0 rows para customer B (matcher exclui via `closed_at IS NOT NULL`)
- 0 rows para customer C (matcher exclui via `ai_active = FALSE`)
- 0 rows para customer D (matcher exclui via `opt_out_at IS NOT NULL`)

### 6.4 Verificar Prometheus counters

```bash
curl -s http://localhost:8050/metrics | grep -E "trigger_(executions|skipped_handoff|skipped)_total.*cart_recovery"
```

**Esperado** (apos 1 tick — handoff skip happens at the matcher SQL level
in production, so the dedicated counter only fires when a candidate leaks
past the matcher and the engine catches it via defense-in-depth):

```
trigger_executions_total{tenant="ariel",trigger_id="cart_recovery",status="dry_run"} 1
```

Se for forcado um seed que vaze um candidate `ai_active=False` ate a engine
(simulado via integration test, nao manual), espera-se tambem:

```
trigger_skipped_handoff_total{tenant="ariel",trigger_id="cart_recovery"} 1
trigger_skipped_total{tenant="ariel",trigger_id="cart_recovery",reason="handoff"} 1
```

### 6.5 Idempotencia

Aguardar 30s (proximo cron tick):

```sql
SELECT status, COUNT(*) FROM trigger_events WHERE trigger_id='cart_recovery' GROUP BY status;
-- Esperado: dry_run=1, skipped=1 (segundo tick gera skipped reason='idempotent')
```

### 6.6 Cobertura testada via suite automatizada

Toda a logica acima e coberta pelos seguintes testes:

* `tests/triggers/test_matcher_time_after_last_inbound.py` (T053):
  - Customer A 48h em conv aberta `ai_active=true` → matched
  - Customer B `closed_at NOT NULL` → excluido
  - Customer C `ai_active=false` (handoff) → excluido
  - Customer D `opt_out_at IS NOT NULL` → excluido
  - Customer E ultima inbound ha 70h → excluido (fora janela)
* `tests/triggers/test_engine_pg.py::test_us3_*` (T057):
  - happy path, closed-conv contract, handoff defense-in-depth +
    counter `trigger_skipped_handoff_total`, status='rejected'
    round-trip para PR-B.
* `apps/api/prosauai/triggers/RUNBOOK.md §query-plans-us3` (T058) —
  query plan `EXPLAIN ANALYZE` esperado + checklist de indexes.

---

## 7. Validar US4 — Admin history viewer (PR-B)

### 7.1 Subir admin Next.js

```bash
cd apps/admin
pnpm install
pnpm dev
# http://localhost:3000
```

### 7.2 Login + abrir aba Triggers

```
http://localhost:3000/triggers
```

Esperado:
- Header com filtros (tenant select, trigger_id input, customer_phone input, status multiselect, date range).
- Tabela mostra rows criadas em §4..§6 (com paginacao 25 default).
- Click row → modal abre com payload JSON pretty-print + cost + erro.

### 7.3 Filtrar por status='dry_run'

UI rapidamente mostra apenas as 3+ rows dry_run das stories anteriores.

### 7.4 Filtrar por customer_phone='+5521987654321'

UI mostra apenas rows do customer A (que apareceu em US1 + US2).

---

## 8. Validar US5 — Cooldown + daily cap defensive invariants (PR-A unit test)

### 8.1 Setup trigger com cooldown 1h e daily_cap_per_customer=3

```yaml
ariel:
  triggers:
    daily_cap_per_customer: 3
    list:
      - id: stress_test_trigger
        type: time_before_scheduled_event
        enabled: true
        mode: dry_run
        lookahead_hours: 24                # janela larga
        cooldown_hours: 1                  # MESMO BUG INTENCIONAL
        template_ref: match_reminder_pt
```

### 8.2 Seed 200 customers com scheduled_event_at em janela

```bash
# script de seed em tests/triggers/fixtures/seed_stress.sql
docker compose exec postgres psql -U postgres -d prosauai \
    -f /tests/triggers/fixtures/seed_stress.sql
```

### 8.3 Aguardar primeiro tick

```sql
SELECT
  COUNT(*) FILTER (WHERE status='dry_run') AS dry_runs,
  COUNT(*) FILTER (WHERE status='skipped' AND error LIKE 'hard_cap%') AS hard_capped
FROM trigger_events
WHERE trigger_id='stress_test_trigger';
```

**Esperado**:
- `dry_runs = 100` (hard cap 100 — FR-011)
- `hard_capped = 0` rows (apenas counter Prometheus incrementa; sem row INSERT para hard_cap reason — apenas log warn)

### 8.4 Aguardar 1h + segundo tick (cooldown expira)

```sql
-- Expected: agora apenas 100 NOVAS dry_run rows (mesmos customers; idempotency permite >1 row/dia? NAO).
-- Idempotency UNIQUE INDEX: WHERE status IN ('sent','queued') — mas dry_run nao esta em ('sent','queued')!
-- Decisao: dry_run is fora do UNIQUE INDEX para permitir testar shadow mode multiplas vezes/dia.
```

### 8.5 Mudar `mode: live` (so apos approve template Meta) + verificar daily cap

```sql
-- Apos cap atingido (3 sent/customer/dia), 4o trigger retorna status='skipped' reason='daily_cap'
SELECT COUNT(*) FROM trigger_events
WHERE customer_id = '<customer_X>' AND status='sent' AND fired_at::date=CURRENT_DATE;
-- Esperado: <= 3
```

---

## 9. Chaos test — Redis restart

```bash
# 1. Estado inicial: 5 sent rows hoje, cooldown Redis ativo
docker compose exec api curl http://localhost:8050/internal/triggers/dump_redis_state

# 2. Kill Redis
docker compose restart redis

# 3. Imediatamente: Redis vazio
docker compose exec redis redis-cli KEYS 'cooldown:*' | wc -l   # 0

# 4. Aguardar primeiro tick pos-restart
docker compose logs api | grep "restore_state_from_sql"
# Esperado: "Redis cold start; restoring 5 cooldown keys + 3 daily_cap counters from trigger_events"

# 5. Verificar Redis re-populado
docker compose exec redis redis-cli KEYS 'cooldown:*' | wc -l   # 5 (re-populado)

# 6. Re-tick: nenhum duplicate sent (idempotency UNIQUE INDEX captura se Redis falhar)
SELECT COUNT(*) FROM trigger_events
WHERE customer_id IN (...os 5 customers...)
  AND status='sent' AND fired_at::date=CURRENT_DATE;
-- Esperado: 5 (mesmos antes do restart)
```

---

## 10. Health checks

```bash
# Cron tick funcionando
curl http://localhost:8050/health/triggers
# {"trigger_engine_loop_alive": true, "last_tick_at": "2026-04-28T15:30:00Z", "lock_held_in_pg": true}

# Prometheus metrics
curl http://localhost:8050/metrics | grep "trigger_"

# OTel spans (Phoenix)
http://localhost:6006/projects/default/traces
# Filtrar por span name "trigger.cron.tick"
```

---

## 11. Kill switch operacional

```bash
# Emergency stop — desabilita tenant inteiro
yq eval '.ariel.triggers.enabled = false' -i tenants.yaml

# Hot reload aplica em <60s — proximo tick skip
# Logs: {"event": "trigger_tick_skipped", "tenant": "ariel", "reason": "tenant_disabled"}

# Emergency stop — desabilita 1 trigger especifico
yq eval '.ariel.triggers.list[0].enabled = false' -i tenants.yaml
# Outros triggers continuam normais
```

---

## 12. Validar SC numbers (ao final do PR-B + Ariel rollout 7d)

| SC | Como validar |
|----|-------------|
| SC-001 | Ariel envia 1 lembrete real para 1 cliente teste em <5d uteis |
| SC-002 | Meta Business Manager dashboard mostra zero ban/tier downgrade em 30d |
| SC-003 | Stress test §8 retorna `daily_cap_blocked = customers_count - 3 × N_days` exato |
| SC-004 | Grafana panel `trigger_cron_tick_duration_seconds` p95 < 2000 ms |
| SC-005 | Time the operator from incident report to admin viewer drill-down — <2 min |
| SC-006 | k6 load test 10K rows GET /admin/triggers/events p95 < 300 ms |
| SC-007 | Grafana 30d: `rate(trigger_template_rejected_total[24h]) / rate(trigger_executions_total[24h])` < 0.05 |
| SC-008 | Chaos test §9 zero duplicate `sent` |
| SC-009 | Stress test §8 dry_runs = 100 exato (hard cap) |
| SC-010 | Modificar `tenants.yaml` + `git commit` + medir tempo ate primeiro tick com nova config (timestamp file vs log line) |
| SC-011 | Pre-prod simulado custo agregado >R$50/dia → alert dispara em < 5min em Alertmanager |
| SC-012 | Comparar `count(status='sent')` apos flip vs `count(status='dry_run')` shadow 3d → desvio <20% |

---

handoff:
  from: speckit.plan (quickstart phase)
  to: speckit.tasks
  context: "Quickstart cobre setup local + validacao end-to-end das 5 user stories da spec.md (US1 lembrete jogo, US2 follow-up consulta, US3 abandoned cart, US4 admin viewer, US5 anti-spam invariants) + chaos Redis restart + 12 SC validation paths. Operador segue passo-a-passo para validar PR-A dry_run + PR-B real send + Ariel rollout."
  blockers: []
  confidence: Alta
  kill_criteria: "Quickstart invalido se: (a) tenants.yaml schema mudar drasticamente em PR-A.2; (b) Evolution `/sendTemplate` semantica obrigar recipient_phone em formato diferente de E.164; (c) admin viewer pagination quebrar em volume real (>10K rows) — re-fixture seed."
