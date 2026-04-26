# Quickstart — Epic 010 Handoff Engine + Multi-Helpdesk Integration

**Feature Branch**: `epic/prosauai/010-handoff-engine-inbox`
**Date**: 2026-04-23
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md) | **Data Model**: [data-model.md](./data-model.md)

---

## 0. Pre-requisitos (ambiente dev)

```bash
# Python 3.12
python3 --version  # >= 3.12

# Nenhuma dependencia Python nova neste epic
cd ~/repos/paceautomations/prosauai

# Servicos locais
docker compose up -d postgres redis   # ja configurados no repo
dbmate up                              # aplica migrations pendentes

# Branch correto
git checkout epic/prosauai/010-handoff-engine-inbox
git pull origin epic/prosauai/010-handoff-engine-inbox
```

Credenciais necessarias (dev):

- **Chatwoot** — acesso a uma instancia Chatwoot de dev. Usamos staging Pace (`https://chatwoot-staging.pace.ai`).
  - Gerar API token: `Profile > Access Token` no Chatwoot web UI.
  - Webhook secret: definir no `Integrations > Webhooks` do inbox de teste.
- **Evolution API** — ja operacional em dev (reuso epic 009).

```bash
# .env.local (nunca commitar)
CHATWOOT_API_TOKEN_DEV="<gerado no Chatwoot profile>"
CHATWOOT_WEBHOOK_SECRET_DEV="$(openssl rand -hex 32)"
```

---

## 1. Validacao incremental por PR

### PR-A — Data model + HelpdeskAdapter + ChatwootAdapter stub + pipeline safety net

#### 1.1 Aplicar migrations

```bash
cd ~/repos/paceautomations/prosauai
dbmate status

dbmate up  # aplica 20260501000001, 20260501000002, 20260501000003
```

Verifique:

```bash
psql $DATABASE_URL -c "\d+ public.conversations" | grep -E "(ai_active|ai_muted|external_refs)"
# Expect: 6 colunas novas

psql $DATABASE_URL -c "\d+ public.handoff_events"
# Expect: tabela com 8 colunas + 2 indices, RLS off

psql $DATABASE_URL -c "\d+ public.bot_sent_messages"
# Expect: tabela com 4 colunas + PK composto + 2 indices, RLS off
```

#### 1.2 Rodar suite existente (gate de merge SC-005)

```bash
cd apps/api
pytest -x tests/ -k "not (slow or e2e or benchmark)"
# Expect: 173 tests epic 005 + 191 tests epic 008 + suites epic 009 PASSING
# Fail → bloqueia merge.
```

#### 1.3 Validar contract tests

```bash
pytest tests/contract/test_helpdesk_adapter_contract.py -v
# Expect:
#   test_implements_protocol[ChatwootAdapter] PASSED
#   test_implements_protocol[NoneAdapter] PASSED
#   test_none_adapter_send_reply_raises PASSED
#   test_chatwoot_parse_assigned PASSED (depende fixture real T000)
```

#### 1.4 Mute manual via SQL direto (validar pipeline safety net)

Validar que, com `ai_active=false` setado **manualmente** no DB (sem webhook), o bot de fato nao responde:

```bash
# Terminal 1: rodar API
cd apps/api && uvicorn prosauai.main:app --reload --port 8050

# Terminal 2: escolher uma conversa de teste
TENANT_ID="..."
CONV_ID="..."
psql $DATABASE_URL -c "
  UPDATE conversations
  SET ai_active=false, ai_muted_reason='manual_toggle',
      ai_muted_at=now(), ai_muted_by_user_id='$ADMIN_USER_ID'
  WHERE id='$CONV_ID' AND tenant_id='$TENANT_ID';
"

# Terminal 3: simular inbound
curl -X POST http://localhost:8050/webhook/evolution/ariel-dev \
  -H "X-Webhook-Secret: $EVOLUTION_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/captured/evolution_text_simple.input.json

# Verificar logs: deve conter
#   pipeline_step_completed step=customer_lookup
#   pipeline_step_skipped step=generate reason=handoff_active
#   trace.emit ai_muted_skip
```

Verificar via psql:

```sql
SELECT ai_active, ai_muted_reason FROM conversations WHERE id='<CONV_ID>';
-- Expect: ai_active=false, ai_muted_reason='manual_toggle'

-- Ainda sem handoff_events porque evento e gerado so por state.mute(),
-- nao via UPDATE direto (UPDATE SQL e escape hatch de dev).
```

#### 1.5 Benchmark de latencia (gate SC-004)

```bash
pytest tests/benchmarks/test_text_latency_no_regression.py -v
# Expect: p95 <= baseline epic 009 + 5ms
# Baseline armazenado em tests/benchmarks/baselines/text_latency_epic009.json
```

#### 1.6 Validar `external_refs.chatwoot` populado por `customer_lookup`

Payload Evolution real carrega `chatwootConversationId`:

```bash
# Enviar webhook Evolution com chatwootConversationId (fixture captured)
curl -X POST http://localhost:8050/webhook/evolution/ariel-dev \
  -H "X-Webhook-Secret: $EVOLUTION_WEBHOOK_SECRET" \
  -d @tests/fixtures/captured/evolution_text_with_chatwoot_id.input.json

# Verify populacao (via psql)
psql $DATABASE_URL -c "
  SELECT external_refs FROM conversations WHERE id='<conv_id>';
"
# Expect: {"chatwoot": {"conversation_id": 123, "inbox_id": 4}}
```

---

### PR-B — NoneAdapter + webhooks + scheduler + shadow mode

#### 2.1 Configurar Chatwoot webhook em dev

No Chatwoot web UI (staging Pace):

1. `Inboxes > <dev inbox> > Integrations > Webhooks`.
2. URL: `https://<ngrok>.io/webhook/helpdesk/chatwoot/ariel-dev` (ou tunnel equivalente).
3. Secret: `$CHATWOOT_WEBHOOK_SECRET_DEV`.
4. Events: `conversation_updated`, `conversation_status_changed`.

Ngrok local:

```bash
ngrok http 8050
# copia URL https:// para o Chatwoot webhook config
```

#### 2.2 Atualizar tenants.yaml

```yaml
# config/tenants.yaml (dev)
tenants:
  ariel-dev:
    helpdesk:
      type: chatwoot
      base_url: https://chatwoot-staging.pace.ai
      account_id: 1
      inbox_id: 3
      api_token: !env CHATWOOT_API_TOKEN_DEV
      webhook_secret: !env CHATWOOT_WEBHOOK_SECRET_DEV
    handoff:
      mode: on  # dev
      auto_resume_after_hours: 1  # dev conveniente
      human_pause_minutes: 5      # dev conveniente
      rules: []
```

#### 2.3 Validar webhook Chatwoot (US1)

No Chatwoot:
- Abrir uma conversa de teste.
- Clicar "Assign" e escolher o proprio usuario.
- Monitorar logs do API:

```
chatwoot_webhook_received tenant_slug=ariel-dev event_id=xxxx
hmac_validated
idempotency_check_passed
webhook_event_parsed event_type=assigned external_conversation_id=123
state.mute_conversation reason=chatwoot_assigned
handoff_event_persisted event_type=muted source=chatwoot_assigned
```

Verify via psql:

```sql
SELECT ai_active, ai_muted_reason, ai_muted_at FROM conversations
  WHERE external_refs->'chatwoot'->>'conversation_id' = '123';
-- Expect: ai_active=false, reason='chatwoot_assigned'

SELECT event_type, source, metadata FROM public.handoff_events
  WHERE conversation_id='<UUID>' ORDER BY created_at DESC LIMIT 5;
-- Expect: event_type='muted', source='chatwoot_assigned'
```

#### 2.4 Validar return-to-bot via webhook resolved (US2)

No Chatwoot: marcar conversa como "Resolved".

```
chatwoot_webhook_received event=conversation_status_changed status=resolved
state.resume_conversation source=helpdesk_resolved
handoff_event_persisted event_type=resumed source=helpdesk_resolved
```

Verify:

```sql
SELECT ai_active FROM conversations WHERE id='<UUID>';
-- Expect: true
```

#### 2.5 Validar auto-resume cron (US2 timeout)

```bash
# Forca uma conversa em mute com auto_resume_at no passado
psql $DATABASE_URL -c "
  UPDATE conversations
  SET ai_active=false, ai_muted_reason='fromMe_detected',
      ai_muted_at=now() - interval '2 hours',
      ai_auto_resume_at=now() - interval '1 minute'
  WHERE id='<CONV_ID>';
"

# Aguardar proxima iteration do cron (<= 60s)
sleep 70

# Verify
psql $DATABASE_URL -c "
  SELECT ai_active FROM conversations WHERE id='<CONV_ID>';
"
# Expect: true

psql $DATABASE_URL -c "
  SELECT event_type, source FROM public.handoff_events
  WHERE conversation_id='<CONV_ID>' ORDER BY created_at DESC LIMIT 1;
"
# Expect: resumed, timeout
```

#### 2.6 Validar NoneAdapter fromMe (US4)

Configurar tenant de teste com `helpdesk.type: none`:

```yaml
tenants:
  none-dev:
    helpdesk:
      type: none
    handoff:
      mode: on
      auto_resume_after_hours: 24
      human_pause_minutes: 5
      rules: []
```

```bash
# 1. Simular bot enviando mensagem (ja grava bot_sent_messages)
# (pipeline normal com uma conversa nao-mutada → bot responde → Evolution send → bot_sent_messages INSERT)

# 2. Simular webhook Evolution com fromMe:true, message_id NAO em bot_sent_messages (humano)
curl -X POST http://localhost:8050/webhook/evolution/none-dev-instance \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/captured/evolution_fromMe_human.input.json

# Logs esperados:
#   noneadapter_fromme_detected message_id=humano-xxx
#   state.mute_conversation reason=fromMe_detected auto_resume_at=<now+5min>
```

Validar group skip:

```bash
curl -X POST http://localhost:8050/webhook/evolution/none-dev-instance \
  -H "Content-Type: application/json" \
  -d '<payload com is_group=true e fromMe=true>'

# Expect logs:
#   noneadapter_group_skip message_id=...
# Nenhum mute deve ter sido emitido
```

Validar bot echo tolerance:

```bash
# Enviar fromMe:true com message_id que acabou de ser inserido em bot_sent_messages (ultimos 10s)
# Expect: noneadapter_bot_echo → no mute
```

#### 2.7 Validar shadow mode

```yaml
tenants:
  ariel-dev:
    handoff:
      mode: shadow  # trocar para shadow
```

Aguardar config_poller (<=60s) + reload.

Acionar webhook Chatwoot assignee (igual 2.3):

```sql
-- conversations.ai_active NAO deve ter mudado
SELECT ai_active FROM conversations WHERE id='<UUID>';
-- Expect: true (nao mutou)

-- Mas handoff_events registrou como shadow=true
SELECT event_type, source, shadow FROM public.handoff_events
  WHERE conversation_id='<UUID>' ORDER BY created_at DESC LIMIT 1;
-- Expect: muted, chatwoot_assigned, shadow=true
```

#### 2.8 Validar circuit breaker

```bash
# Simular Chatwoot indisponivel (bloquear port 443 outbound para chatwoot domain)
sudo iptables -A OUTPUT -d chatwoot-staging.pace.ai -j DROP

# Trigger 5+ pushs de private note (simular via pipeline com kind=audio)
# Cada falha incrementa breaker counter

# Verify apos 5 falhas em 60s:
grep "helpdesk_breaker_open" apps/api/logs/app.log
# Expect: tenant=ariel-dev helpdesk=chatwoot

# Apos 30s do breaker open:
#   helpdesk_breaker_half_open
# Se proxima chamada succeed:
#   helpdesk_breaker_closed

# Cleanup
sudo iptables -D OUTPUT -d chatwoot-staging.pace.ai -j DROP
```

#### 2.9 Benchmark latencia webhook (gate SC-002)

```bash
pytest tests/benchmarks/test_webhook_latency.py -v
# Expect: p95 < 500ms webhook → mute commit
```

---

### PR-C — Admin UI + metricas + rollout

#### 3.1 Admin lista conversas — badges (US3)

Abrir `http://localhost:3000/admin/conversations`:

- Conversas com `ai_active=true` → badge verde "AI ativa".
- Conversas com `ai_active=false` → badge vermelho "AI silenciada por: {reason} desde {time}".

Benchmark:

```bash
cd apps/admin
npx playwright test e2e/handoff.spec.ts --grep "inbox-latency"
# Expect: lista carrega em <100ms p95
```

#### 3.2 Toggle manual (US3)

1. Abrir conversa `ai_active=true`.
2. Clicar botao "Silenciar AI" → confirmar.
3. Badge vira vermelho "AI silenciada por: manual_toggle desde agora".
4. `handoff_events` tem entrada `event_type=muted, source=manual_toggle, metadata.admin_user_id=...`.
5. Clicar "Retomar AI" → badge verde.

#### 3.3 Composer emergencia (US5)

1. Abrir conversa de tenant Chatwoot (ariel-dev).
2. No composer, digitar "Oi, aqui e Pace ops". Clicar Enviar.
3. Validar:
   - Mensagem chega ao cliente no WhatsApp (via Chatwoot → Evolution).
   - Mensagem aparece no Chatwoot com `sender_name=<admin.email>`.
   - `handoff_events` tem `event_type=admin_reply_sent, source=manual_toggle, metadata.admin_user_id=<JWT.sub>`.

Testar 409:

1. Abrir conversa de tenant `none-dev`.
2. Composer deve estar **disabled** (UI detecta `helpdesk.type=none`) OU ao enviar retorna 409:

```json
{"error": "no_helpdesk_configured", "detail": "Tenant has no helpdesk; composer is not applicable"}
```

#### 3.4 Performance AI — 4 cards (US6)

Abrir `http://localhost:3000/admin/performance`:

Validar linha "Handoff" com 4 cards:
- **Taxa de handoff** — `COUNT DISTINCT conv WHERE handoff_events > 0 / COUNT DISTINCT conv`
- **Duracao media silenciada** — avg(resumed_at - muted_at) per conversation_id
- **Breakdown por origem** — pie chart 5 origens
- **SLA breaches** — count events com `source=timeout`

Range filter (reusa do epic 008): mudar para "ultimos 7d" → cards recalculam em <3s sem reload.

#### 3.5 E2E Playwright

```bash
cd apps/admin
npx playwright test e2e/handoff.spec.ts
# Expect: suite verde — login → lista → toggle → composer → verify
```

---

## 2. Validacao por User Story

| US | Status | Como validar (resumo) |
|----|--------|----------------------|
| US1 — Atendente assume conversa | PR-B | 2.3 |
| US2 — Return-to-bot automatico | PR-B | 2.4 + 2.5 |
| US3 — Admin badge + toggle manual | PR-C | 3.1 + 3.2 |
| US4 — NoneAdapter fromMe | PR-B | 2.6 |
| US5 — Composer emergencia | PR-C | 3.3 |
| US6 — Performance AI cards | PR-C | 3.4 |
| US7 — Shadow mode rollout | PR-B | 2.7 |

---

## 3. Rollback de emergencia

### 3.1 Desligar handoff para tenant especifico

```yaml
# tenants.yaml
tenants:
  ariel:
    handoff:
      mode: off   # era on
```

Deploy: basta editar o YAML e aguardar config_poller (<=60s). Sem deploy de codigo.

**Efeito imediato**: proximo webhook Chatwoot para aquele tenant e recebido e respondido 200 OK, mas nao gera mute. Conversas ja mutadas permanecem mutadas (manual unmute via `/admin/{id}/unmute` ou psql).

### 3.2 Desligar scheduler auto_resume

```bash
# Env var
export HANDOFF_AUTO_RESUME_ENABLED=0

# Reiniciar API
systemctl restart prosauai-api  # ou equivalente docker/k8s
```

Auto-resume cron pula iterations. Conversas com `auto_resume_at < now()` permanecem mutadas ate admin intervir.

### 3.3 Reverter migrations (caso extremo)

```bash
# NAO RECOMENDADO em prod, mas possivel (todas migrations aditivas)
dbmate rollback  # rollback 20260501000003 (bot_sent_messages)
dbmate rollback  # rollback 20260501000002 (handoff_events)
dbmate rollback  # rollback 20260501000001 (conversations +6 cols)
```

Data loss: apenas em `handoff_events` e `bot_sent_messages` (admin/tracking tables). Conversations perdem os 6 campos mas CHECK constraints bloqueiam inconsistency — nao afeta operacao do bot.

---

## 4. Troubleshooting

### 4.1 Webhook Chatwoot retorna 401

- Verificar `X-Webhook-Signature` presente no request (curl inspect).
- Verificar secret no `tenants.yaml` esta correto (match com Chatwoot integration config).
- Verificar body nao foi modificado por proxy intermediario (Chatwoot calcula HMAC sobre body raw).

### 4.2 Bot responde em cima do humano mesmo com mute

- `SELECT ai_active FROM conversations WHERE id=...` — confirmar bit esta false.
- Checar logs do pipeline: `grep pipeline_step_skipped` — deve aparecer.
- Se bit=false mas bot respondeu: verificar race entre pipeline start e mute commit. Provavel bug no safety net do step `generate` — abrir incident.

### 4.3 NoneAdapter mata o proprio bot (false positive)

- `SELECT * FROM bot_sent_messages WHERE message_id=<id>` — deve existir.
- Se nao existe: pipeline outbound nao gravou. Verificar `channels/outbound/evolution.py` grava apos send.
- Se existe mas `sent_at > 48h`: retention kickou em. Ajustar retention ou investigar por que bot echou mensagem tao antiga.

### 4.4 Webhook Chatwoot nao dispara mute

- Verificar integration no Chatwoot esta ativa + URL correta.
- Verificar event types selecionados (conversation_updated + conversation_status_changed).
- Verificar idempotency: `redis-cli KEYS 'handoff:wh:*'` — ver se ja foi processado (SETNX block).
- Verificar `external_refs.chatwoot.conversation_id` esta populado na conversation → se nao, webhook nao consegue mapear → `chatwoot_webhook_unlinked_total` metric incrementada.

### 4.5 Composer admin retorna 503

- Circuit breaker aberto → `grep helpdesk_breaker_open` nos logs.
- Chatwoot API retornando 5xx → checar status pagemu.
- Aguardar 30s (half-open) → tentar novamente. Se ainda 503, problema e no Chatwoot real.

---

## 5. Proximos passos pos-epic

- **Monitoring**: alertas Prometheus para `helpdesk_breaker_open > 5min`, `handoff_events_total{shadow=true}` crescendo sem fliping para `on`.
- **Epic 010.1**: BlipAdapter / ZendeskAdapter quando cliente demandar (contrato `HelpdeskAdapter` ja acomoda).
- **Epic 013 Agent Tools v2**: registry de tools reintroducido pode emitir rule `tool_failure → safety_trip` → `state.mute_conversation(reason='safety_trip')` — usa infra deste epic sem mudanca.
- **Epic 014 Alerting + WhatsApp Quality**: consome `handoff_events_total{source='timeout'}` para SLA breach notifications (Slack/email).

---

handoff:
  from: quickstart (Phase 1)
  to: tasks (Phase 2)
  context: "Quickstart com validacao incremental PR-A (data model + safety net via SQL direto) → PR-B (webhooks + NoneAdapter + scheduler + shadow) → PR-C (admin UI + metricas). Rollback matrix + troubleshooting + E2E por User Story. Pronto para decomposicao em tasks.md T001+."
  blockers: []
  confidence: Alta
