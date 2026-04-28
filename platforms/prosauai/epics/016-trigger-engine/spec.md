# Feature Specification: Trigger Engine — engine declarativo de mensagens proativas

**Feature Branch**: `epic/prosauai/016-trigger-engine`
**Created**: 2026-04-28
**Status**: Draft
**Input**: Hoje a plataforma ProsaUAI **so envia mensagens em resposta a inbound** (`EvolutionProvider.send_text` reactive-only). A vision §6 firma a tese comercial em duas pernas — service conversations user-initiated gratis + custo variavel em proativos via templates aprovados — mas a Phase 2 do ADR-006 (`IF condition THEN action configuravel`) **nunca foi implementada**: zero infra de trigger no codigo, zero tabela `trigger_events`, zero metodo `send_template()`. Use cases concretos parados: ResenhAI manda lembrete de jogo manualmente via WhatsApp pessoal e nao escala alem de 5-10 partidas/semana; e-commerce/servicos (segmentos vision §1.2 e §1.3) tem mercado bloqueado por falta de carrinho abandonado, follow-up apos compra, lembrete de consulta. Risk #4 da vision (ban WhatsApp por proativos exagerados) sem mitigacao especifica — qualquer engine sem cooldown granular vira gerador de ban. Esta epic entrega: **engine declarativo cron-driven** com 3 trigger types pre-built (`time_before_scheduled_event`, `time_after_conversation_closed`, `time_after_last_inbound`); **`tenants.yaml triggers.*` + `templates.*` blocks** para config sem deploy (hot reload <60s); **cooldown granular per (tenant, customer, trigger_id) + global daily cap per customer** anti-spam/anti-ban; novo metodo `EvolutionProvider.send_template()` integrado com circuit breaker + warm-up cap do epic 014; tabela `public.trigger_events` (admin-only carve-out ADR-027) com audit trail completo + LGPD SAR cascade; admin history viewer read-only filtravel; **5 metricas Prometheus + 2 alert rules** (cost overrun + template rejection rate). Comportamento atual permanece intacto: tenants/agentes sem `triggers.list` continuam reactive-only — zero deploy, zero regressao.

## Clarifications

### Session 2026-04-28

Autonomous dispatch mode — todas as decisoes vem do `epic-context` (2026-04-26, modo `--draft`) ja capturadas em [pitch.md §Captured Decisions](./pitch.md) (30 itens) e [decisions.md](./decisions.md). Esta sessao herda a base e marca eventuais ambiguidades restantes como `[DECISAO AUTONOMA]` para auditoria. Override humano via `decisions.md` durante implementacao continua sendo o caminho normal.

- Q: Quando o admin modifica `tenants.yaml triggers.*` durante uma execucao em curso de cron tick, qual e a semantica esperada para o tick atual e os subsequentes? → A: **O tick em execucao quando a config e modificada termina com a config antiga** (snapshot lido no inicio do tick). O proximo tick (apos hot reload <60s) usa a config nova. Justificativa: simplicidade de raciocínio e ausencia de mid-tick reconfigure (tick e curto, ~2s, leitura snapshot e atomica). `[DECISAO AUTONOMA]`
- Q: Qual a politica quando um template e referenciado em `triggers.list[].template_ref` mas nao existe em `templates.*` daquele tenant? → A: **Validacao no startup falha rapido** (Pydantic + cross-ref check no startup) — servico nao sobe se referencia esta quebrada. Hot reload tambem rejeita config invalida e mantem snapshot anterior em uso (loga warning + alerta operador). Justificativa: trigger sem template = bug certo de producao; melhor crashar deploy do que silenciosamente skip todos os triggers afetados. `[DECISAO AUTONOMA]`
- Q: Quando um trigger gera um proativo e o cliente responde dentro de N minutos, como o sistema correlaciona a resposta ao trigger original (para attribution futura, alem do ai_active heuristica do epic 010)? → A: **Sem attribution explicita em v1**. `messages.metadata.triggered_by` (campo JSONB existente, sem migration) recebe `{trigger_id, fired_at, template_name}` na proxima inbound de N=24h apos o `trigger_events.sent_at`. Apenas record-keeping para 016.X+ analytics. **Heuristica `auto_resolved` (ADR-040)** continua imutavel (ai_active permanece true, condicao a satisfeita). `[DECISAO AUTONOMA]`
- Q: Como o sistema trata customers cujo `phone_number` foi `OPT_OUT` registrado em algum momento (cliente respondeu STOP/SAIR ou similar)? → A: v1 usa **flag `customers.opt_out_at TIMESTAMPTZ NULL`** (migration nova, junto com `scheduled_event_at`). Match v1 sempre filtra `WHERE opt_out_at IS NULL` (consent_required default true). Detector automatico de STOP/SAIR fica em 016.1+ (manual ops registra opt-out em v1). Justificativa: opt-in herdado nao distingue cliente que respondeu STOP — adicionar coluna agora e barato; detector automatico exige NLP que custa fora da appetite. `[DECISAO AUTONOMA]`
- Q: Em ambiente multi-tenant, como o sistema garante que um trigger configurado para tenant A nao alcance customers de tenant B (cross-tenant leak)? → A: **Matchers usam `pool_tenant` (per-request RLS)** com `SET LOCAL app.tenant_id = $tenant_id` — pattern epic 003 reusado. Cada query do matcher e SELECT com tenant_id implicito via RLS. Tests de regressao validam que matcher de tenant A nao retorna customers de tenant B. Justificativa: RLS ja e o controle obrigatorio em todas queries cross-tenant; reusa pattern, zero novidade arquitetural. `[DECISAO AUTONOMA]`

#### Round 2 — clarify pass (2026-04-28)

- Q: A idempotencia por `(tenant_id, customer_id, trigger_id, fired_at::date)` (FR-017) deve ser garantida apenas por logica de aplicacao ou tambem por constraint de banco como defesa em profundidade? → A: **Defense-in-depth: partial UNIQUE INDEX no banco** alem da checagem aplicacional. Migration cria `CREATE UNIQUE INDEX trigger_events_idempotency_idx ON public.trigger_events (tenant_id, customer_id, trigger_id, (fired_at::date)) WHERE status IN ('sent', 'queued');`. Permite multiplos rows `skipped/rejected/dry_run/failed` (auditoria), mas garante no maximo 1 row `sent` ou `queued` por dia per `(tenant, customer, trigger_id)`. Conflito durante INSERT (race condition entre matcher concorrente — improvavel com advisory lock, mas nao impossivel) eleva `UniqueViolationError` capturado e tratado como `status='skipped' reason='idempotent_db_race'`. Justificativa: FR-017 sozinho protege contra re-tick normal; index protege contra race conditions exoticas e contra bugs futuros que esquecam o check aplicacional — custo zero em writes (audit trail essencialmente append-only). `[DECISAO AUTONOMA]`
- Q: Quando stuck-detection (FR-041) re-processa uma row `status='queued'` ha >=5min, o proximo tick INSERT um novo row ou UPDATE in-place o row existente? → A: **UPDATE in-place** com `retry_count` incrementado. Schema ganha coluna `retry_count INT NOT NULL DEFAULT 0` em `trigger_events` (ja na migration inicial). Recovery flow: matcher pega row (`status='queued' AND fired_at < NOW() - INTERVAL '5 min' AND retry_count < 3`), faz `UPDATE ... SET retry_count=retry_count+1, fired_at=NOW()` em transacao, depois tenta send. Apos 3 retries, marca `status='failed'`. Justificativa: (a) preserva integridade do audit trail (1 row = 1 trigger fired, mesmo apos crashes); (b) interage limpo com idempotencia DB (mesma chave logica nao gera 2 rows sent); (c) `retry_count` visivel no admin viewer ajuda diagnostico (cron crash recorrente vira evidencia). `[DECISAO AUTONOMA]`
- Q: Quando LGPD SAR deleta um customer (`DELETE FROM customers WHERE id=X`), o ON DELETE CASCADE em `trigger_events.customer_id` apaga audit trail completo daquele customer. Isso e aceitavel ou devemos anonimizar (manter rows com `customer_id=NULL` + `payload` redacted)? → A: **Hard delete via CASCADE — aceitavel em v1**. ADR-018 ja firma direito ao apagamento; auditoria de billing/cost agregada permanece intacta porque `cost_usd_estimated` e `tenant_id` nao dependem de `customer_id`. Trade-off documentado: SAR delete remove evidencia per-customer (operador nao consegue auditar "este cliente recebeu lembrete?" apos delete), mas isso e o **proposito** da SAR. Para evitar perda de metricas operacionais, gauge `trigger_cost_today_usd{tenant}` e calculada no momento do fired_at e armazenada em metric backend (Prometheus retention 30d) — ja independente do row. Anonimizacao (path alternativo) requer migration nova + redaction logic + queries especiais — fora da appetite. `[DECISAO AUTONOMA]` `[VALIDAR]` se DPO/jurıdico requer log redacted vs delete em 016.1+
- Q: Qual auth/RBAC governa `GET /admin/triggers/events` (FR-035/FR-037)? → A: **Reusa middleware de admin do epic 008** sem novo controle. Endpoint requer header de admin auth (Bearer token validado contra `admin_users` table existente). Em v1, todo admin autenticado ve todos tenants (super-admin); filtro `tenant_id` na query e cosmetic (nao security boundary — admin pode listar qualquer tenant). Tenant-scoped admin (admin que so ve seu proprio tenant) fica em epic 018 (Tenant Self-Admin) — quando shipa, RBAC ganha role check `WHERE tenant_id = current_admin.scoped_tenant_id`. UI Admin (FR-037) usa mesma TanStack Query auth do epic 008. Justificativa: zero auth nova, super-admin only e suficiente em v1 (Pace controla operacao centralizada — vision §3 supports). `[DECISAO AUTONOMA]`
- Q: O job separado que atualiza gauge `trigger_cost_today_usd{tenant}` a cada 60s (FR-030) usa qual lock pattern e como degrada em falha? → A: **Lifespan task FastAPI separado com advisory lock proprio** `pg_try_advisory_lock(hashtext('triggers_cost_gauge_cron'))` — pattern epic 010/011/014. Cadence 60s configuravel via `triggers.cost_gauge_cadence_seconds`. Falha (DB indisponivel, query timeout): emite log error + Prometheus gauge retem ultimo valor (Prometheus default behavior) + counter `trigger_cost_gauge_errors_total{reason}`. Em standby (lock held por outra replica), tick atual skipa silenciosamente sem warning. Recovery: na proxima janela, replica vencedora atualiza com SUM atual — sem buffer de "lost ticks". Justificativa: gauge e snapshot recovery-tolerant (perder 1-2 ticks de 60s nao afeta alert >R$50/dia que dispara em 5min); lock garante singleton em multi-replica; pattern reusado zero novidade. `[DECISAO AUTONOMA]`

## User Scenarios & Testing *(mandatory)*

<!--
  Stories priorizadas por valor de negocio + sequenciamento de risco. Cada uma e independentemente testavel.
  P1 = MVP (engine + 1-2 trigger types ponta a ponta). P2 = trigger types adicionais + observabilidade operacional.
  P3 = recursos defensivos (anti-spam invariants visiveis para auditoria).
-->

### User Story 1 — Lembrete de jogo agendado para clientes ResenhAI (Priority: P1)

Um operador da ResenhAI hoje envia manualmente, do seu WhatsApp pessoal, lembretes 1h antes de cada partida do cliente. Com 5-10 partidas por semana cresce intratavel — operador esquece, manda 5 minutos antes do jogo, perde lembretes nos fim-de-semana, nao escala para 50 clientes simultaneos. Com a Trigger Engine, ele cria um template aprovado pela Meta (`ariel_match_reminder`), cadastra em `tenants.yaml templates.match_reminder_pt`, adiciona o trigger `ariel_match_reminder` em `tenants.yaml triggers.list` com `type: time_before_scheduled_event` + `lookahead_hours: 1` + `cooldown_hours: 24`, e popula `customers.scheduled_event_at` para cada cliente com a hora da proxima partida (via API admin). A partir do proximo cron tick (<=15s apos hot reload), o sistema **automaticamente** dispara um lembrete 1h antes de cada partida agendada, sem intervencao humana, com audit trail completo em `public.trigger_events`.

**Why this priority**: e o use case canonico da vision (`Trigger | Mensagem proativa enviada pelo agente por evento ou agendamento — exemplo: lembrete enviado 1h antes do jogo`), tem dor humana mensuravel (operador fazendo manualmente nao escala) e e o caso mais simples para validar o engine ponta-a-ponta — sem ele, nada no epic tem valor.

**Independent Test**: o engenheiro consegue, via SQL direto + edicao de `tenants.yaml`, configurar 1 template (`match_reminder_pt`) + 1 trigger (`ariel_match_reminder`) + 3 customers de teste com `scheduled_event_at` em 1h, 25h e 30min. Apos o proximo cron tick: customer da partida em 1h recebe template (visivel em `messages` outbound + `trigger_events.status='sent'`); customer da partida em 25h e ignorado (fora do `lookahead_hours`); customer da partida em 30min e ignorado (ja passou da janela `lookahead_hours`). Reexecutar o cron tick na sequencia nao envia template duplicado para o customer ja atendido (idempotencia por `(tenant, customer, trigger_id, fired_at::date)`).

**Acceptance Scenarios**:

1. **Given** um tenant `resenhai` com `templates.match_reminder_pt` aprovado em Meta + trigger `ariel_match_reminder` (`type: time_before_scheduled_event`, `lookahead_hours: 1`, `cooldown_hours: 24`, `enabled: true`) + 1 customer com `scheduled_event_at = NOW() + 50min`, **When** o cron tick executa, **Then** o sistema cria row em `trigger_events` (status `queued` -> `sent`), envia template via `EvolutionProvider.send_template`, atualiza Redis cooldown `cooldown:resenhai:{customer_id}:ariel_match_reminder` com TTL 24h, e emite span OTel `trigger.cron.tick` -> `trigger.match` -> `trigger.send`.
2. **Given** o mesmo cenario, **When** o cron tick **re-executa** 30s depois (o lookahead_hours ainda matcha), **Then** o sistema detecta row existente em `trigger_events` para `(resenhai, customer_id, ariel_match_reminder, fired_at::date)` e **nao envia template duplicado** — incrementa apenas `trigger_skipped_total{reason="idempotent"}`.
3. **Given** customer ja recebeu trigger `ariel_match_reminder` ha 5h, **When** outro `scheduled_event_at` do mesmo customer (jogo seguinte) chega na janela `lookahead_hours: 1`, **Then** o sistema bloqueia via cooldown 24h (`trigger_cooldown_blocked_total{trigger_id}` incrementa) e cria row `trigger_events.status='skipped'` com `error='cooldown_active_until=...'`.
4. **Given** trigger `enabled: false` na config, **When** cron tick executa, **Then** o trigger e ignorado (zero row criada, zero metric incrementada para esse trigger).
5. **Given** customer com `opt_out_at IS NOT NULL`, **When** matcher avalia, **Then** customer e excluido (filtro RLS + WHERE `opt_out_at IS NULL`) e contador `trigger_skipped_total{reason="opt_out"}` incrementa.

---

### User Story 2 — Re-engajamento apos conversa fechada (Priority: P1)

Um operador de servicos (vision §1.3 segmento — clinica, salao, prestador) quer enviar follow-up 24h apos toda conversa que terminou em compromisso confirmado: *"Oi {nome}, foi otimo te atender! Lembramos sua consulta amanha as {hora}, confirma?"*. Hoje, ele acompanha planilha manual e dispara WhatsApp pessoal — falha em 30% dos casos por esquecimento. Com a Trigger Engine, ele cria template `consult_reminder_pt`, adiciona trigger `consult_reminder` (`type: time_after_conversation_closed`, `lookahead_hours: 24`, `cooldown_hours: 168` — 1 semana), e o sistema dispara automaticamente 24h apos `conversations.closed_at` (campo ja existente).

**Why this priority**: P1 porque (a) e o segundo trigger type pre-built, validando que o engine generaliza alem de `scheduled_event_at`; (b) reusa coluna existente (`conversations.closed_at`) sem migration adicional; (c) cobre segmento vision §1.3 inteiro (servicos), abrindo go-to-market.

**Independent Test**: o engenheiro configura trigger `consult_reminder` (`type: time_after_conversation_closed`, `lookahead_hours: 24`). Cria 3 conversas de teste em estado `closed` com `closed_at` em -23h, -25h, -10h. Apos cron tick: conversa fechada ha 23-25h dispara template (dentro do `lookahead_hours: 24` com tolerancia de tick); conversa fechada ha 10h e ignorada (cedo demais); conversa fechada ha 50h e ignorada (ja saiu da janela — matcher tem cap `closed_at >= NOW() - lookahead_hours - tick_jitter`).

**Acceptance Scenarios**:

1. **Given** trigger `consult_reminder` (`type: time_after_conversation_closed`, `lookahead_hours: 24`, `cooldown_hours: 168`) + conversa do customer X fechada ha 24h05min, **When** cron tick executa, **Then** matcher retorna customer X, sistema envia template, cria row `trigger_events.status='sent'`.
2. **Given** mesma conversa, **When** cron tick re-executa 30s depois, **Then** idempotencia bloqueia (mesma logica US1).
3. **Given** conversa X fechada novamente apos 1h (cliente reabriu e fechou de novo), **When** matcher avalia, **Then** o cooldown 168h (1 semana) bloqueia novo trigger ate semana seguinte.
4. **Given** conversa fechada ha 25h (5min apos a janela `lookahead_hours: 24`), **When** matcher executa, **Then** customer e excluido — janela `[NOW - lookahead_hours - tick_jitter, NOW - lookahead_hours]` e o filtro estrito.
5. **Given** match_count exceeds hard cap 100 customers/tick, **When** cron processa, **Then** sistema processa primeiros 100 customers (sorted `customers.created_at` ASC) + emite `trigger_skipped_total{reason="hard_cap"}` com count truncado + log warn `tenant=X trigger_id=Y customers_truncated=Z`.

---

### User Story 3 — Re-engajamento de cliente silencioso (e-commerce abandoned cart) (Priority: P2)

Um operador de e-commerce (vision §1.2 segmento) quer atingir clientes que enviaram a ultima mensagem ha 48h **sem ter recebido handoff humano e sem ter conversa fechada** — perfil tipico de "carrinho abandonado" em conversa de pre-venda. Mensagem: *"Oi {nome}! Reservei sua duvida sobre o produto X. Quer que eu finalize seu pedido?"*. Hoje impossivel sem engine. Com a Trigger Engine, configura trigger `cart_recovery` (`type: time_after_last_inbound`, `lookahead_hours: 48`, `cooldown_hours: 72` — 3 dias entre tentativas, max 1 retry).

**Why this priority**: P2 (nao P1) porque (a) o terceiro trigger type tem semantica mais sutil (filtro de "conversa nao fechada e ai_active=true") + maior risco de spam/ban se config errada; (b) operador tem workaround mais decente que servicos (relatorio semanal de carrinhos abandonados ja existe em alguns BI); (c) pre-requisito de validacao Ariel (US1) para destravar — primeiro provar que engine + cooldown funcionam, depois liberar segmentos novos.

**Independent Test**: o engenheiro configura trigger `cart_recovery` (`type: time_after_last_inbound`, `lookahead_hours: 48`). Cria 4 customers: A com ultima inbound ha 48h em conversa aberta (ai_active=true) -> deve enviar; B com ultima inbound ha 48h mas conversa fechada -> nao envia (filtro nega); C com ultima inbound ha 48h mas em handoff humano (ai_active=false) -> nao envia; D com ultima inbound ha 70h -> nao envia (fora da janela).

**Acceptance Scenarios**:

1. **Given** trigger `cart_recovery` + customer A com ultima inbound ha 48h em conversa aberta `ai_active=true`, **When** cron tick executa, **Then** sistema envia template, cria row `trigger_events.status='sent'`.
2. **Given** customer B com ultima inbound ha 48h mas `conversations.closed_at IS NOT NULL`, **When** matcher avalia, **Then** customer B e excluido (filtro inner join + WHERE `closed_at IS NULL`).
3. **Given** customer C com `conversations.ai_active=false` (em handoff), **When** matcher avalia, **Then** customer C e excluido + counter `trigger_skipped_handoff_total{trigger_id}` incrementa.
4. **Given** o template `cart_recovery_pt` foi rejeitado pela Meta no momento do envio (4xx response), **When** sistema processa o erro, **Then** atualiza row `trigger_events.status='rejected'` com `error=meta_4xx_message` + incrementa `trigger_template_rejected_total{tenant, template_name, reason}` + dispara alert critical 1min via Slack/Telegram.

---

### User Story 4 — Operador audita execucoes recentes via admin history viewer (Priority: P2)

Um operador da ResenhAI recebe call do cliente Joao reclamando: *"Recebi lembrete de jogo errado ontem!"*. Hoje, sem audit trail, operador da plataforma nao consegue responder em <30 min — precisa abrir banco direto, escrever query SQL, comparar com config YAML. Com a Trigger Engine, ele abre Admin -> Triggers, filtra por `customer_id=joao` + `tenant=resenhai` + range de datas, ve a row `trigger_events` com `template_name`, `payload renderizado`, `cost_usd_estimated`, `error=null`, `sent_at=2026-04-27 19:00`. Drill-down mostra os parametros exatos enviados ao template Meta. Em <2 min ele responde ao cliente com a verdade auditada (config tinha `lookahead_hours: 1` mas `scheduled_event_at` do Joao estava 24h adiantado por bug de fuso).

**Why this priority**: P2 (nao P1) porque o use case **operacional** sobrevive ao curto prazo via SQL direto na tabela `public.trigger_events` — engenharia tem acesso, suporte podera ser escalado de outra forma na semana 1. Mas e P2 (nao P3) porque sem ele a feature nao e auditavel pelo operador medio em <2min e o "Trigger erradicio" se torna viral nas reclamacoes do cliente.

**Independent Test**: com Ariel rodando em producao com 3 dias de trigger_events acumulados, operador abre `/admin/triggers/events` na UI, aplica filtros (`tenant=resenhai`, `from=2026-04-25`, `to=2026-04-28`), ve lista paginada com 50 rows, clica em uma row e ve modal com payload JSON completo + cost_usd + error detalhado + timestamps. Tempo medio operador: <2 min para encontrar info especifica.

**Acceptance Scenarios**:

1. **Given** 50 rows em `trigger_events` para tenant resenhai nas ultimas 24h, **When** operador acessa `/admin/triggers/events?tenant=resenhai&from=...&to=...`, **Then** UI renderiza tabela paginada (cursor pagination, 25 per page) com colunas `fired_at, customer_phone, trigger_id, template_name, status, cost_usd, error_short`.
2. **Given** mesma tabela, **When** operador filtra por `status=rejected`, **Then** apenas rows com Meta 4xx aparecem.
3. **Given** operador clica em uma row, **When** modal drilldown abre, **Then** mostra `payload` JSONB completo (parametros renderizados), `error` full, `cost_usd_estimated`, `fired_at`, `sent_at`, `customer.phone_number_e164`, `trigger.type`, `trigger.template_ref`.
4. **Given** operador filtra `customer_phone="+5521..."`, **When** UI consulta backend, **Then** retorna apenas rows daquele customer (admin pool BYPASSRLS, mas filtro `tenant_id` continua aplicado para evitar cross-tenant leak na UI).
5. **Given** request com 1000 rows na pagina, **When** backend processa, **Then** responde p95 <300ms (cursor pagination + index `(tenant_id, fired_at DESC)`).

---

### User Story 5 — Anti-spam invariant defensivo: cooldown e cap protegem cliente (Priority: P3)

Um operador novato configura por engano um trigger `daily_offer` com `lookahead_hours: 24` + `cooldown_hours: 1` (vez de 24). Ao primeiro tick, o engine identifica 200 customers elegiveis. Sem invariants defensivos, todos receberiam 24 mensagens em 1 dia — ban WhatsApp + dor de imagem. Com US5, o sistema **garante por design** que mesmo o pior bug de config nunca cause: (a) mais de 3 proativos por customer/dia (global daily cap, default `triggers.daily_cap_per_customer: 3`); (b) mais de 100 envios por trigger/tick (hard cap 100). Operador erra config, sistema protege.

**Why this priority**: P3 nao porque seja menos importante (e DEFENSIVO core) mas porque e **invariant testavel automaticamente sem rollout real** — toda a logica e exercitada pelos testes de US1/US2/US3. Esta US existe para deixar **explicito o contrato de invariants** que o sistema deve manter, mesmo sob config quebrada.

**Independent Test**: configurar trigger `bug_test` (`cooldown_hours: 1`, `lookahead_hours: 24`) que normalmente matcharia 200 customers. Primeiro tick processa 100 (hard cap) + 3 envios por customer (global cap) + cooldown 1h ate proximo tick. Ao final do dia, sistema gravou exatamente `min(200, 100 customers/tick) * min(daily_cap=3, ticks_per_day_per_customer)` envios — nunca >3 por customer/dia.

**Acceptance Scenarios**:

1. **Given** trigger configurado matcheando 200 customers em 1 tick, **When** matcher retorna lista, **Then** sistema processa apenas os primeiros 100 (sorted `customers.created_at` ASC) + emite `trigger_skipped_total{reason="hard_cap"}` com `count=100`.
2. **Given** customer X ja recebeu 3 proativos hoje (qualquer trigger), **When** matcher avalia trigger Y para customer X, **Then** sistema bloqueia + counter `trigger_daily_cap_blocked_total{tenant}` incrementa + cria row `trigger_events.status='skipped'` com `error='daily_cap_exceeded:3/3'`.
3. **Given** Redis perdeu state (restart), **When** primeiro tick apos restart executa, **Then** sistema **nao re-envia** triggers ja sent_today: matcher cruza com `trigger_events` (SQL fallback) para reconstruir cooldown/cap counts antes de qualquer send.
4. **Given** cron tick demora >2s, **When** lock advisory persiste, **Then** proximo tick aguarda lock (no parallel ticks) — pattern epic 010/011/014.
5. **Given** alert rule `trigger_cost_today_usd{tenant} > 50`, **When** custo agregado de 1 tenant cruza R$50/dia, **Then** Alertmanager dispara warning Slack 5min — operador pode silenciar via Alertmanager se for campanha intencional.

---

### Edge Cases

- **Trigger config muda durante tick em execucao**: tick atual completa com snapshot antigo da config; proximo tick usa config nova (hot reload <60s).
- **Template referenciado nao existe em `templates.*`**: validacao Pydantic no startup falha rapido — servico nao sobe; hot reload rejeita config invalida e mantem snapshot anterior + warning + alert.
- **Customer sem `scheduled_event_at` (NULL)**: matcher `time_before_scheduled_event` exclui via `WHERE scheduled_event_at IS NOT NULL` — zero overhead, zero erro.
- **Cron tick de 15s nao termina antes do proximo (lock contention)**: `pg_try_advisory_lock` retorna false, log warn `tenant=ALL tick_skipped reason=lock_held`, proximo tick reentrenta. Sem fila acumulando — triggers perdidos sao re-avaliados no proximo tick com sucesso.
- **Tenant `triggers.enabled: false`**: skipa todo o tenant antes de qualquer query custosa — preserva CPU/IO.
- **Conversa em handoff humano (`ai_active=false`)**: trigger nunca dispara para esse customer (filtro matcher), mesmo que cooldown nao bloqueie.
- **Customer com `opt_out_at IS NOT NULL`**: trigger nunca dispara (filtro matcher absoluto, ignora cooldown e cap).
- **Cron tick falha mid-way (cron crash)**: proximo tick re-avalia tudo — rows com `status='queued'` ha >5min sao reprocessadas (stuck-detection). Idempotencia evita duplicate sent.
- **Hot reload de `tenants.yaml` quebra YAML parse**: mantem snapshot anterior + emite log error + alert (pattern existing config_poller).
- **Customer apaga conta WhatsApp entre matcher e send**: Evolution retorna 4xx (number not found), sistema marca `status='rejected'` + incrementa `trigger_template_rejected_total{reason='number_not_found'}` (sem retry).
- **Mesma `scheduled_event_at` em milhares de customers (campanha)**: hard cap 100/tick + cron 15s = max 400/min/trigger throughput. Operador planeja antecipacao via `lookahead_hours` mais largo se necessario.
- **Tick processa parte dos customers entao trava (timeout)**: rows ja com `status='sent'` permanecem; rows `status='queued'` voltam ao pool no proximo tick (idempotencia previne duplicate).
- **Daily cap `triggers.daily_cap_per_customer` ausente em `tenants.yaml`**: usa default 3 (constante codigo). Override per-tenant via `triggers.daily_cap_per_customer: N`.
- **Cliente recebe trigger e responde com STOP/SAIR**: v1 nao detecta automaticamente — operador precisa chamar `PATCH /admin/customers/{id}` setando `opt_out_at`. Detector NLP automatico fica em 016.1+.

## Requirements *(mandatory)*

### Functional Requirements

#### Engine + scheduler

- **FR-001**: Sistema MUST executar um cron tick a cada 15 segundos (configuravel via `triggers.cadence_seconds`, default 15) com singleton garantido por `pg_try_advisory_lock(hashtext('triggers_engine_cron'))` — pattern epic 010/011/014.
- **FR-002**: Sistema MUST suportar 3 trigger types pre-built em v1: `time_before_scheduled_event`, `time_after_conversation_closed`, `time_after_last_inbound`. Tipos custom (e.g., `type: custom`) MUST ser rejeitados com erro de validacao em v1 (escape hatch fica em 016.1+).
- **FR-003**: Sistema MUST ler config de triggers/templates a partir de `tenants.yaml triggers.*` e `tenants.yaml templates.*` blocks per tenant, com hot reload em <=60s via `config_poller` existente.
- **FR-004**: Sistema MUST validar config (Pydantic) no startup E em cada hot reload — config invalida no startup MUST falhar rapido (servico nao sobe); config invalida em hot reload MUST manter snapshot anterior + emitir log error + alert.
- **FR-005**: Sistema MUST tratar `triggers.enabled: false` (per tenant) como kill-switch — skipa todo o tenant antes de qualquer query.
- **FR-006**: Sistema MUST tratar `triggers.list[].enabled: false` (per trigger) como kill-switch individual — trigger e ignorado mas demais do tenant continuam.

#### Matchers + filters

- **FR-007**: Matchers MUST executar queries via `pool_tenant` (per-request RLS) com `SET LOCAL app.tenant_id = $tenant_id` — pattern epic 003.
- **FR-008**: Matchers MUST aplicar filtros declarativos `match.intent_filter`, `match.agent_id_filter`, `match.min_message_count`, `match.consent_required` (default true). v1 MUST NOT suportar SQL custom em `match.*`.
- **FR-009**: Matchers MUST excluir customers com `opt_out_at IS NOT NULL` quando `match.consent_required: true` (default).
- **FR-010**: Matchers MUST excluir customers cuja conversa atual esteja em handoff humano (`conversations.ai_active = false`) — usar JOIN com latest conversation.
- **FR-011**: Matchers MUST aplicar **hard cap de 100 customers** por trigger por tick — acima disso, processa primeiros 100 (sorted `customers.created_at` ASC) + emite log warn + counter Prometheus `trigger_skipped_total{reason="hard_cap"}`.

#### Cooldown + cap

- **FR-012**: Sistema MUST aplicar cooldown per `(tenant_id, customer_id, trigger_id)` com TTL = `cooldown_hours * 3600` segundos via Redis chave `cooldown:{tenant}:{customer}:{trigger_id}`.
- **FR-013**: Sistema MUST aplicar global daily cap per `(tenant_id, customer_id)` com counter Redis `daily_cap:{tenant}:{customer}:{YYYY-MM-DD}`, TTL 26h, max default 3 (override via `triggers.daily_cap_per_customer`).
- **FR-014**: Cooldown ou cap hit MUST resultar em `trigger_events.status='skipped'` com `error` descritivo + incrementar contador Prometheus apropriado (`trigger_cooldown_blocked_total` ou `trigger_daily_cap_blocked_total`).
- **FR-015**: Apos Redis restart (state perdido), proximo tick MUST reconstruir cooldown/cap counts via fallback SQL contra `trigger_events` antes de processar sends — zero duplicate sends por restart.

#### Persistencia + idempotencia

- **FR-016**: Sistema MUST persistir cada execucao de trigger em `public.trigger_events` (admin-only, ADR-027 carve-out) com schema completo: `id UUID PK, tenant_id, customer_id, trigger_id TEXT, template_name TEXT, fired_at TIMESTAMPTZ, sent_at TIMESTAMPTZ NULL, status TEXT CHECK ('queued','sent','failed','skipped','rejected','dry_run'), error TEXT NULL, cost_usd_estimated NUMERIC(10,4), payload JSONB, retry_count INT NOT NULL DEFAULT 0`.
- **FR-017**: Sistema MUST garantir idempotencia por `(tenant_id, customer_id, trigger_id, fired_at::date)` em **2 niveis**: (a) checagem aplicacional antes do send — query existing rows e skip se ja existe `status IN ('sent','queued')`; (b) defesa em profundidade no banco — `CREATE UNIQUE INDEX trigger_events_idempotency_idx ON public.trigger_events (tenant_id, customer_id, trigger_id, (fired_at::date)) WHERE status IN ('sent', 'queued')` (index parcial). Conflitos de race condition (improvaveis com advisory lock mas nao impossiveis) levantam `UniqueViolationError` que MUST ser capturado e gravado como `status='skipped' reason='idempotent_db_race'`.
- **FR-018**: Sistema MUST aplicar retention 90 dias em `trigger_events` via cron existente epic 006 (estendido para nova tabela).
- **FR-019**: Sistema MUST cascadear LGPD SAR sobre `trigger_events` via FK `customer_id` com `ON DELETE CASCADE` (hard delete quando customer e SAR-deleted) — ADR-018 reaffirmed. Trade-off documentado: hard delete remove evidencia per-customer no audit trail; metricas operacionais agregadas (custo agregado, taxas) permanecem em Prometheus retention 30d (ja independente de `customer_id`). Anonimizacao alternativa (set `customer_id=NULL` + redact `payload`) adiada para 016.1+ se DPO/juridico requerer. `[VALIDAR]`
- **FR-020**: Sistema MUST adicionar coluna `customers.scheduled_event_at TIMESTAMPTZ NULL` (migration nova) para habilitar matcher `time_before_scheduled_event`.
- **FR-021**: Sistema MUST adicionar coluna `customers.opt_out_at TIMESTAMPTZ NULL` (migration nova) para habilitar opt-out hard filter.

#### Send path

- **FR-022**: `EvolutionProvider` MUST expor metodo novo `send_template(template_name, language, components, recipient_phone)` chamando `POST /message/sendTemplate/{instance}` da Evolution API.
- **FR-023**: `send_template` MUST ser decorado com circuit breaker per `(tenant, phone_number_id)` — pattern epic 014 reusado, sem novo breaker.
- **FR-024**: `send_template` MUST respeitar warm-up cap diario per `(tenant, phone_number_id)` — pattern epic 014 reusado, default 1000/dia.
- **FR-025**: Render de parametros (`{customer.name}`, `{customer.scheduled_event_at | format_time}`) MUST usar Jinja-like sandboxed reusando renderer epic 015. v1 suporta filters builtin: `format_time`, `format_date`, `truncate`, `default`. v1 MUST NOT permitir code execution.
- **FR-026**: Template rejection (Meta retorna 4xx) MUST resultar em `trigger_events.status='rejected'` + counter `trigger_template_rejected_total{tenant, template_name, reason}` + alert critical 1min via Slack/Telegram. v1 MUST NOT retry rejection (template e immutable; e bug de config).
- **FR-027**: Network error / 5xx Evolution MUST disparar retry exponential backoff 3x (pattern ADR-016) — se persiste apos retries, status=`failed` + alert + handoff via epic 010 nao aplica (proativos nao tem path de handoff).

#### Modo shadow + rollout

- **FR-028**: Sistema MUST suportar modo shadow per trigger via `triggers.list[].mode: 'dry_run'` (override transient; `enabled: true` + `mode: dry_run`) — matcher executa, persiste row `trigger_events.status='dry_run'`, **mas nao chama send_template**. Default `mode: live` quando `enabled: true`.

#### Observabilidade

- **FR-029**: Sistema MUST emitir 5 series Prometheus via structlog facade:
  - `trigger_executions_total{tenant, trigger_id, status}` (counter, status: queued/sent/failed/skipped/rejected/dry_run)
  - `trigger_template_sent_total{tenant, trigger_id, template_name}` (counter, success only)
  - `trigger_skipped_total{tenant, trigger_id, reason}` (counter, reason: cooldown/daily_cap/hard_cap/opt_out/handoff/idempotent/disabled)
  - `trigger_cooldown_blocked_total{tenant, trigger_id}` (counter, subset de skipped)
  - `trigger_template_rejected_total{tenant, template_name, reason}` (counter)
- **FR-030**: Sistema MUST emitir gauge `trigger_cost_today_usd{tenant}` derivado de `SUM(cost_usd_estimated) FROM trigger_events WHERE fired_at::date = CURRENT_DATE`. Atualizado a cada 60s (configuravel via `triggers.cost_gauge_cadence_seconds`) via lifespan task FastAPI separado com advisory lock proprio `pg_try_advisory_lock(hashtext('triggers_cost_gauge_cron'))` — pattern epic 010/011/014. Falhas (DB indisponivel, query timeout): emite log error + Prometheus retem ultimo valor + counter `trigger_cost_gauge_errors_total{reason}`. Standby (lock held por outra replica): skip silencioso sem warning.
- **FR-031**: Sistema MUST emitir spans OTel: span root `trigger.cron.tick` (atributos `trigger_count`, `tenant_count`, `tick_duration_ms`); children `trigger.match` (atributos `tenant_id, trigger_id, customers_matched`), `trigger.cooldown_check`, `trigger.send` (atributos `template_name, evolution_response_status, cost_usd`).
- **FR-032**: Logs structlog MUST incluir contexto: `tenant_id, customer_id, trigger_id, template_name, status, error, cost_usd_estimated`.
- **FR-033**: Cardinality control: labels Prometheus combinados MUST manter <50K series. Lint no startup valida (`tenant <= 100`, `trigger_id <= 20 per tenant`, `template_name <= 50 per tenant`, `reason <= 10`, `status <= 6`).

#### Alert rules

- **FR-034**: Sistema MUST registrar 2 alert rules em `config/rules/triggers.yml`:
  - `trigger_cost_today_usd{tenant} > 50` por 5min -> warning (Slack)
  - `rate(trigger_template_rejected_total[5m]) > 0.1` (mais de 10% de rejection rate em 5min) -> critical 1min (Slack/Telegram)

#### Admin API + UI

- **FR-035**: Backend MUST expor `GET /admin/triggers/events` com query params `tenant`, `trigger_id`, `customer_id` (busca por phone_e164 OU id), `status`, `from`, `to`, `cursor`, `limit` (default 25, max 200). Cursor pagination (sem cache — audit trail fresh). Auth MUST reusar middleware admin do epic 008 (Bearer token validado contra `admin_users`); v1 super-admin only ve todos tenants. Tenant-scoped admin RBAC fica em epic 018 (Tenant Self-Admin).
- **FR-036**: Backend MUST aplicar pool_admin BYPASSRLS no endpoint, MAS filtro `tenant_id` MUST ser sempre honrado quando enviado. Em v1, filtro `tenant_id` e cosmetico (admin pode listar qualquer tenant); em epic 018+ vira security boundary via role check `WHERE tenant_id = current_admin.scoped_tenant_id`.
- **FR-037**: UI Admin (epic 008) MUST adicionar aba `/admin/triggers` com lista paginada (colunas: `fired_at, customer_phone, trigger_id, template_name, status, cost_usd, error_short, retry_count`) + drill-down modal mostrando payload completo + erro full + timestamps + retry_count. Reusa TanStack Query auth do epic 008.
- **FR-038**: UI MUST suportar filtros (tenant, trigger_id, customer_phone, status, date range) com debounce 300ms.

#### Operacional + safety

- **FR-039**: `messages.metadata.triggered_by` (campo JSONB existente, sem migration) MUST receber `{trigger_id, fired_at, template_name}` na proxima inbound do customer dentro de 24h apos `trigger_events.sent_at` — record-keeping para 016.X+ analytics.
- **FR-040**: Cron tick MUST completar em <2s (via hard cap 100 customers/trigger + indexes adequados em `customers.scheduled_event_at`, `conversations.closed_at`, `messages.created_at`).
- **FR-041**: Stuck-detection: rows com `status='queued' AND fired_at < NOW() - INTERVAL '5 min' AND retry_count < 3` MUST ser reprocessadas pelo proximo tick via **UPDATE in-place** (`UPDATE ... SET retry_count=retry_count+1, fired_at=NOW()` em transacao, depois retry send). Apos 3 retries, marca `status='failed'`. Preserva integridade do audit trail (1 row = 1 trigger fired logico) e respeita idempotencia DB (mesma chave logica `(tenant, customer, trigger_id, fired_at::date)`).
- **FR-042**: Sistema MUST validar no startup que toda referencia `triggers.list[].template_ref` aponta para um item existente em `templates.*` — caso contrario, falha rapido.
- **FR-043**: Cron tick MUST usar snapshot atomico de config no inicio do tick — modificacoes de config durante tick NAO afetam o tick em curso (proximo tick pega config nova).

### Key Entities

- **Trigger**: declaracao em `tenants.yaml triggers.list[]` que descreve quando proativos devem disparar. Atributos: `id` (string unica per tenant), `type` (enum: time_before_scheduled_event/time_after_conversation_closed/time_after_last_inbound), `enabled` (bool), `lookahead_hours` (int), `cooldown_hours` (int), `template_ref` (FK string para `templates.*`), `match` (objeto com filtros), `mode` (enum: live/dry_run, default live).
- **Template**: declaracao em `tenants.yaml templates.<key>` representando um template aprovado pela Meta. Atributos: `name` (Meta template name), `language` (e.g., pt_BR), `components[]` (estrutura Meta com parameters[]), `approval_id` (Meta), `cost_usd` (constante para billing). Nao mutavel pelo runtime — operador atualiza via PR no `tenants.yaml`.
- **TriggerEvent**: row em `public.trigger_events` representando 1 execucao de trigger. Atributos: `id, tenant_id, customer_id, trigger_id, template_name, fired_at, sent_at, status, error, cost_usd_estimated, payload (JSONB com parametros renderizados), retry_count`. Idempotencia garantida em 2 niveis: app-check antes do send + partial UNIQUE INDEX `WHERE status IN ('sent','queued')`. Stuck rows (`status='queued' >5min`) re-processadas via UPDATE in-place ate 3 retries antes de virar `failed`. Retention 90d, admin-only ADR-027. SAR via `ON DELETE CASCADE` (hard delete; metricas operacionais agregadas permanecem em Prometheus).
- **Customer (extended)**: tabela `public.customers` ganha 2 colunas v1: `scheduled_event_at TIMESTAMPTZ NULL` (habilita matcher tempo-antes-evento) e `opt_out_at TIMESTAMPTZ NULL` (kill switch absoluto per customer). Demais atributos inalterados.
- **CooldownState (Redis)**: chave `cooldown:{tenant}:{customer}:{trigger_id}` (existencia = bloqueado, TTL = cooldown_hours * 3600). Volatil — recoverable via SQL fallback.
- **DailyCapCounter (Redis)**: chave `daily_cap:{tenant}:{customer}:{YYYY-MM-DD}` (counter, TTL 26h). Volatil — recoverable via SQL fallback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ResenhAI envia o primeiro lembrete de jogo proativo automatico para 1 cliente real **dentro de 5 dias uteis** apos start do epic, sem intervencao manual no envio.
- **SC-002**: **Zero ban** WhatsApp ou tier downgrade (Green/Yellow/Red) atribuido a esta epic durante os primeiros 30 dias de rollout em producao — mensurado por relatorio Meta Business Manager.
- **SC-003**: Em campanha de teste com 1000 customers em 1 tenant, **100%** dos customers que excederiam o cap diario de 3 sao bloqueados (zero >=4 envios para mesmo customer/dia).
- **SC-004**: **100%** dos cron ticks em producao completam em <2s (p95) — mensurado via histograma `trigger_cron_tick_duration_seconds`.
- **SC-005**: Operador consegue auditar uma execucao especifica de trigger (`/admin/triggers/events` filtro + drill-down) em **<2 minutos**, partindo da reclamacao do cliente.
- **SC-006**: Endpoint `GET /admin/triggers/events` responde com **p95 <300ms** quando query inclui paginacao (cursor) e filtro por tenant.
- **SC-007**: Apos primeiros 30 dias em producao, **template rejection rate <5%** (`rate(trigger_template_rejected_total[24h]) < 0.05 * rate(trigger_executions_total[24h])`).
- **SC-008**: **Zero duplicate sends** em testes de chaos (Redis restart + cron re-tick + 1000 simulated triggers): row count em `trigger_events.status='sent'` por `(tenant, customer, trigger_id, fired_at::date)` MUST ser sempre <=1.
- **SC-009**: Em smoke test de tsunami (1 trigger config errado matcheando 200 customers): sistema processa exatamente 100 (hard cap) + 0 customers acima — verificavel via `trigger_skipped_total{reason="hard_cap"}` em testes integracao.
- **SC-010**: Hot reload de `tenants.yaml` aplicada em **<=60s** mensurada por timestamp de modificacao do arquivo vs primeiro tick com nova config (lib `config_poller` ja existente).
- **SC-011**: Cost overrun alert dispara **dentro de 5min** apos `trigger_cost_today_usd{tenant}` cruzar R$50/dia — verificavel em pre-prod simulando custo agregado.
- **SC-012**: Em rollout shadow (3d com `mode: dry_run`), apos flip para `mode: live`, taxa de match efetiva (rows `status='sent'`) e **>=80%** da taxa observada em shadow (`status='dry_run'`) — desvio >20% indica bug em `mode: live` path.

## Assumptions

- **Premissa: cron-only resolve v1**. Todos os 3 trigger types pre-built sao **scheduled/timed** (sem necessidade de event-reactive). PG NOTIFY listener (ADR-004) adiado para 016.1+ se demanda real-time aparecer (e.g., abandoned cart reativo a INSERT em `messages`). [VALIDAR] em pos-rollout 30d.
- **Premissa: WhatsApp templates pre-aprovados por operador**. Cadastro manual via Meta Business Manager (24-48h por template). Auto-sync Graph API adiado para 016.1+. v1 confia em operador inserir `approval_id` correto em `tenants.yaml templates.*`.
- **Premissa: opt-in herdado e suficiente para LGPD v1**. Cliente que enviou >=1 inbound = consentido por servico. Detector automatico de STOP/SAIR fica em 016.1+ — operador registra opt-out manual via `PATCH /admin/customers/{id}` setando `opt_out_at`.
- **Premissa: 100 customers/trigger/tick e safe**. Calibrado conservador (Evolution API `/sendTemplate` rate limit nao publicamente documentado; presumido >=400/min/instance). Ajusta em 016.1 apos 30d producao.
- **Premissa: cooldown 24h + cap 3/dia sao defaults razoaveis**. ResenhAI use case (1 lembrete por jogo, 1-2 jogos/cliente/semana) cabe no cap. E-commerce abandoned cart (1 retry max) cabe. Servicos lembrete consulta (1 follow-up) cabe. [VALIDAR] em pos-rollout — operador pode override per-tenant.
- **Premissa: `tenants.yaml` e o lugar certo para config**. Pattern consolidado em 4 epics (010, 013, 014, 015). Self-service tenant-facing UI vira Tenant Self-Admin (epic 018, depende de 013). Pace controla catalogo em v1.
- **Premissa: epic 014 (Quality + Breaker) shipa antes ou em paralelo**. Send_template depende de circuit breaker + warm-up cap. Cut-line: se 014 nao shipa antes do PR-B, 016 entrega so engine + dry_run em PR-A; PR-B vira 016.1.
- **Premissa: Evolution API endpoint `/message/sendTemplate/{instance}` existe e funciona como `/message/sendText`**. Smoke test em PR-B prova premissa. Se falhar, fallback path: usar Evolution `presence/typing` + send_text com warning para operador (degradacao funcional documentada).
- **Premissa: index `(tenant_id, fired_at DESC)` em `trigger_events` cobre admin viewer p95 <300ms**. Volume estimado v1: <1M rows/mes/tenant (3 triggers ativos x 100 customers/tick x 4 ticks/min x 60 x 24 x 30 = ~13M/mes mas 99% sao skipped — apenas ~10K sent/mes/tenant). Index suporta ate 100M rows facilmente. [VALIDAR] em load test.
- **Dependencia: epic 010 (Handoff Engine) shipped** — pattern scheduler (lifespan task + advisory lock) + structlog facade reusados integralmente.
- **Dependencia: epic 014 (Alerting WhatsApp Quality) drafted** — circuit breaker + warm-up cap + Prometheus + Alertmanager. Hard dep para PR-B.
- **Dependencia: epic 015 (Agent Pipeline Steps) drafted** — Jinja-like sandboxed renderer reusado para parameter substitution.
- **Dependencia: epic 008 (Admin Evolution) shipped** — pool_admin BYPASSRLS + TanStack Query v5 + shadcn/ui. UI history viewer reusa pattern existente.
- **Dependencia: epic 003 (Multi-Tenant) shipped** — pool_tenant per-request RLS para matcher queries.
- **Dependencia: epic 005 (Conversation Core) shipped** — `EvolutionProvider`, `customers`, `conversations`, `messages` tables.
- **Dependencia: epic 006 (Production Readiness) shipped** — migration runner, retention cron extensivel.
- **Escopo limite: zero novas dependencias externas Python**. `pyyaml` + `ruamel.yaml` + `redis[hiredis]` + `httpx` + `opentelemetry` ja sao deps do projeto. Renderer Jinja-like reusa epic 015.
- **Escopo limite: zero mudancas em `messages` schema**. `metadata` JSONB existente acomoda `triggered_by`. Apenas `customers` ganha 2 colunas (`scheduled_event_at`, `opt_out_at`).
- **Escopo limite: nao implementa A/B testing per template, multi-step trigger flows, schedule absoluto (cron-style "todo dia 9h"), self-service tenant-facing UI, eval per-trigger LLM-as-judge** — todos adiados para 016.1+ ou 016.X+.

---

## Dependencies

- **Inputs (consumidos como contexto)**:
  - [pitch.md](./pitch.md) — 30 captured decisions + appetite + cut-lines
  - [decisions.md](./decisions.md) — registro auditavel das 30 decisoes
  - [vision.md §6](../../business/vision.md) — tese comercial proativos
  - [business/process.md](../../business/process.md) — fluxo conversa atual
  - [decisions/ADR-006](../../decisions/ADR-006-agent-as-data.md) — Phase 2 IF/THEN config
  - [decisions/ADR-027](../../decisions/ADR-027-admin-tables-no-rls.md) — admin-only carve-out
  - [decisions/ADR-018](../../decisions/ADR-018-data-retention-lgpd.md) — SAR cascade pattern
  - [decisions/ADR-040](../../decisions/ADR-040-autonomous-resolution-heuristic.md) — auto_resolved nao quebra
- **Outputs (consumidos por skills downstream)**:
  - `/speckit.clarify prosauai 016-trigger-engine` — proxima etapa da L2 cycle
  - `/speckit.plan prosauai 016-trigger-engine` — gera plan.md a partir desta spec

---

handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada com 10 [DECISAO AUTONOMA] markers (5 da specify + 5 da clarify pass): idempotencia em 2 niveis (app + partial UNIQUE INDEX), stuck-detection via UPDATE in-place + retry_count (max 3), SAR hard delete CASCADE com [VALIDAR] DPO, admin auth super-admin only via middleware epic 008, cost gauge separate lifespan task com advisory lock proprio. 43 FRs (FR-016/FR-017/FR-019/FR-030/FR-035/FR-036/FR-037/FR-041 atualizados), 12 SCs, 5 user stories, schema final inclui retry_count. Pronto para plan."
  blockers: []
  confidence: Alta
  kill_criteria: "Se Evolution API /message/sendTemplate/{instance} nao existir ou tiver semantica fundamentally diferente de send_text, FR-022/FR-023/FR-024 sao invalidados e PR-B precisa pivot para Cloud API direto (re-spec required). Se DPO/juridico requerer audit trail completo apos SAR (anonimizar em vez de hard delete), FR-019 + schema migration precisam re-design (impacto em 016.1)."
