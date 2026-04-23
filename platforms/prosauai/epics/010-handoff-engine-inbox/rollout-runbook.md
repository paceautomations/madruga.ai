---
epic: 010-handoff-engine-inbox
task: T811
created: 2026-04-23
updated: 2026-04-23
owners: pace-ops
---

# Rollout Runbook — Handoff Engine

> Playbook operacional para o caminho `off → shadow (7d) → on` do epic 010.
> Aplicavel a **cada tenant individualmente**. Ariel e o primeiro; ResenhAI
> replica o mesmo trajeto com 7 dias de defasagem.

Documentos relacionados: [spec.md](./spec.md), [pitch.md](./pitch.md),
[plan.md](./plan.md), [decisions.md](./decisions.md).

---

## Gate diagram

```
   off          shadow          on
    |             |              |
    |-- 1 dia --> |-- 7 dias --> |
    |  (sanity)   | (validacao)  | (producao)
    |             |              |
   nada          eventos         mute real
   acontece      persistidos     conversas
    -            com shadow=true silenciadas
                 ai_active=true
```

Cada transicao entre estados exige que os criterios do estado corrente
tenham sido cumpridos antes do flip. Nenhum flip e feito cedo — o custo
de desligar (rollback `mode: on → off` em <60s) e baixo, o custo de
subir errado (silenciar bot em conversa onde humano nao vai responder) e
alto.

---

## Estado inicial: `handoff.mode: off`

**Duracao minima**: 1 dia (sanity check do deploy).

**O que acontece**:
- Webhook Chatwoot recebido → **200 OK** devolvido, nenhum evento gerado,
  `ai_active` inalterado. Adapter eh chamado com `handoff_mode=off` e
  curto-circuita na primeira linha de `state.mute_conversation`.
- Composer admin (`POST /admin/conversations/{id}/reply`) continua
  funcionando — nao depende de `handoff.mode`.
- Scheduler `handoff_auto_resume_cron` roda normalmente mas nenhum candidato
  porque nenhuma conversa foi mutada.

**Criterios para promover a `shadow`**:

1. [ ] Tenant configurado em `tenants.yaml` com bloco `helpdesk:` valido
       (credenciais testadas via curl manual no Chatwoot API).
2. [ ] Webhook Chatwoot cadastrado apontando para
       `https://<api>/webhook/helpdesk/chatwoot/<tenant-slug>` com
       `webhook_secret` matching.
3. [ ] Fixture real do primeiro webhook assignee capturada e copiada para
       `apps/api/tests/fixtures/captured/` (gate de teste).
4. [ ] Linkage `external_refs.chatwoot` populando em >=1 conversa via
       `customer_lookup` step (queryable via SQL).
5. [ ] Gate PR-A + PR-B merged; migrations aplicadas em producao; zero
       regression nos 173+191 tests + benchmarks (SC-004, SC-005).
6. [ ] Alerta Prometheus configurado para `chatwoot_webhook_unlinked_total`
       em produto — sinaliza buracos de linkage.

**Ativacao**: editar `tenants.yaml` do tenant alvo, setar
`handoff.mode: shadow`, aguardar proxima rodada do config_poller (60s).
Validar via log `tenant_config_reloaded{tenant=<slug>}`.

---

## Estado intermediario: `handoff.mode: shadow`

**Duracao planejada**: 7 dias corridos (inclui ciclo de atendimento
semanal completo — fim de semana + horario comercial + overnight).

**O que acontece**:
- Webhook Chatwoot assignee_changed / status_resolved → evento persistido
  em `public.handoff_events` com `shadow=true`, `conversations.ai_active`
  **nao muda**. Bot continua respondendo normalmente.
- `NoneAdapter` fromMe tambem registra eventos `shadow=true` sem mutar
  (quando aplicavel; Ariel/ResenhAI tem Chatwoot, entao essa trilha fica
  latente em shadow).
- Cron `handoff_auto_resume_cron` segue sem candidatos.
- Performance AI exibe os 4 cards com **visual hachurado** (cinza) e
  slices do pie com `fillOpacity=0.45` (T712-T713) — sinal visual claro
  de que os numeros sao **predicoes**, nao producao.
- Metrics dedicadas: `handoff_shadow_events_total{tenant, event_type, source}`
  alem do `handoff_events_total` principal — facilita o diff pos-flip
  (SC-012).

**Observacao continua (pace-ops)**:

Diariamente (ou sob demanda), inspecionar:

1. **Taxa de eventos shadow**: quantos mutes shadow estao sendo
   previstos? Dashboard Grafana `handoff_shadow_events_total` rate.
2. **Distribuicao por origem**: `chatwoot_assigned` e dominante (esperado).
   `rule_match` nao-zero indica regra do router epic 004 que merece
   revisao antes de flipar `on`.
3. **False-mute candidates**: conversas onde `ai_active=true` mas evento
   shadow `muted` foi emitido e o cliente continuou interagindo com o
   bot > 5 min — indica que o atendente nao assumiu de fato (ex:
   auto-assign de automacao Chatwoot).
4. **Amostragem qualitativa**: 5-10 conversas por dia em que houve
   evento shadow sao revisadas manualmente (log + transcript Chatwoot)
   para classificar: "humano assumiu de verdade" vs "false mute".

**Criterios para promover a `on`**:

1. [ ] **False-mute rate ≤ 5%** — medido sobre amostra de ≥ 100 eventos
       shadow ao longo dos 7 dias. Se for maior, investigar causa raiz
       (auto-assign, pre-assignment, bot treinado em outra automacao) e
       ajustar antes de flipar.
2. [ ] **SC-012 / 10%** — taxa **predita** de mute deve casar com a taxa
       **real** observada pos-flip dentro de 10% de diferenca. Como nao
       temos dados reais em shadow, usamos a taxa historica de
       "conversa escalou para humano via Chatwoot" da ultima semana como
       baseline. Se shadow predicoes diferem >30% do baseline, pausar.
3. [ ] **Zero alertas criticos nos 7 dias**: `helpdesk_breaker_open`,
       `tenant_config_reload_failed`, `chatwoot_webhook_unlinked_total` >
       5% dos webhooks.
4. [ ] **Aprovacao explicita do tenant**: e-mail / slack do lead de ops
       do tenant confirmando ciencia do flip `on`.
5. [ ] **Janela de flip escolhida**: horario de baixo trafego
       (domingo 8h BRT ou segunda 10h BRT) — permite rollback com
       impacto minimo se surgir anomalia.

**Ativacao**: editar `tenants.yaml`, setar `handoff.mode: on`, commit + deploy
**ou** se infisical ja esta em polling, so commit e aguardar 60s. Validar
via metric `handoff_events_total{shadow=false}` aparecendo em rate
nao-zero.

---

## Estado final: `handoff.mode: on`

**Duracao**: indefinida (producao estavel).

**O que acontece**:
- Comportamento completo do epic 010: bot silencia quando atendente
  assume, retoma quando resolve ou timeout vence, composer admin opera
  end-to-end.
- Todos os SCs viram gates de producao: SC-001 (zero bot em conversa
  humana), SC-002 (latencia webhook <500ms p95), SC-011 (rollback <60s),
  etc.

**Monitoramento continuo (primeiras 48h pos-flip)**:

- **SC-001 contra-query**: a cada 6h, rodar
  ```sql
  SELECT count(*) FROM messages m
  JOIN handoff_events h ON h.conversation_id = m.conversation_id
  WHERE h.event_type = 'muted'
    AND m.sent_by_bot_at > h.created_at
    AND m.sent_by_bot_at < COALESCE(
      (SELECT created_at FROM handoff_events h2
       WHERE h2.conversation_id = h.conversation_id
         AND h2.event_type = 'resumed'
         AND h2.created_at > h.created_at
       ORDER BY h2.created_at ASC LIMIT 1),
      now()
    );
  ```
  Esperado: **0** linhas. Qualquer linha acima = SC-001 violado.

- **Taxa de mute observada vs predita**: comparar
  `handoff_events_total{shadow=false, event_type=muted, tenant=<slug>}` nas
  primeiras 48h contra media do shadow_events_total dos 7 dias
  anteriores. Diferenca >10% triggers investigacao.

- **Latencia webhook**: histogram `helpdesk_webhook_latency_seconds` p95
  deve ficar <500ms consistentemente. Alerta em p95 >800ms por 5min
  consecutivos.

- **Circuit breaker**: se `helpdesk_breaker_open{tenant=<slug>}` = 1 por
  >5 min, rollback para `shadow` enquanto Chatwoot e investigado.

---

## Rollback de emergencia

**Cenario**: mute indevido em massa / bot nao respondendo quando deveria
/ atendente reclamando que bot sumiu.

**Acao**: setar `handoff.mode: shadow` (ou `off` se shadow tambem esta
corrompido) no `tenants.yaml` e commitar. config_poller re-le em ate 60s
(FR-042). RTO: **≤60s**.

Nao e necessario deploy — o poller e o unico knob. Se o poller estiver
broken, `docker exec <api> kill -HUP 1` forca reload.

**Pos-rollback**:
1. Persistir motivo do rollback em `decisions.md` com data e link para o
   incidente.
2. Rodar query "conversas ainda mutadas pelo evento culpado" e limpar
   manualmente:
   ```sql
   UPDATE conversations SET
     ai_active = true,
     ai_muted_reason = NULL,
     ai_muted_at = NULL,
     ai_muted_by_user_id = NULL,
     ai_auto_resume_at = NULL
   WHERE ai_active = false
     AND ai_muted_reason = 'chatwoot_assigned'
     AND ai_muted_at > '<timestamp do bug>';
   ```
3. Re-validar shadow mode no tenant por +72h antes de tentar `on`
   novamente.

---

## Criterios de remocao do codigo de shadow

> Decisao operacional pos-epic (A13 spec). Nao e gate de merge.

O codigo de shadow mode pode ser removido no epic 010.1 (ou posterior) se:

1. Ambos Ariel e ResenhAI estao em `on` ha pelo menos 30 dias consecutivos
   sem rollback.
2. Nao ha tenants novos planejados que precisem de shadow como etapa de
   onboarding.
3. Equipe de ops confirma que o custo de manter shadow (~50 LOC em
   `state.py` + rendering Performance AI + metric counter dedicado) e
   maior que o valor de tera-lo de prontidao para novo tenant.

Se removido, a porta de entrada de um tenant novo passa direto de `off`
para `on`, aceitando o risco. Retornar a adicionar shadow sera ~30 min
de trabalho (branch `if handoff_mode == "shadow"` e rendering condicional
ja ancorados no design).

---

## Referencias

- FR-040 / FR-041 / FR-042 — semantica de modes e poller (spec.md).
- SC-011 — rollback <60s sem deploy (spec.md).
- SC-012 — shadow prediz realidade ±10% (spec.md).
- Decisao 14 — feature flag tri-estado (decisions.md).
- T710-T715 — rendering Performance AI shadow (tasks.md).
- T813 — metric dedicado `handoff_shadow_events_total` (tasks.md).
