# Feature Specification: Handoff Engine + Multi-Helpdesk Integration

**Feature Branch**: `epic/prosauai/010-handoff-engine-inbox`
**Created**: 2026-04-23
**Status**: Draft
**Input**: Epic pitch `010-handoff-engine-inbox/pitch.md` (escopo integral, trade-offs e rollout plan preservados no pitch).

## Contexto do problema

Hoje, quando um atendente humano do tenant responde uma conversa pelo Chatwoot (integração Evolution ja existente — todo webhook carrega `chatwootConversationId`), o bot do ProsaUAI **nao sabe que o humano assumiu** e continua respondendo no proximo inbound do cliente. O resultado operacional em Ariel e ResenhAI e conversa dupla: humano responde via Chatwoot, cliente replica, bot responde por cima. UX quebrada e atendente frustrado.

O status `pending_handoff` esta **declarado mas nao materializado** no schema ([apps/api/prosauai/db/queries/conversations.py:16](apps/api/prosauai/db/queries/conversations.py#L16) comenta explicitamente "not yet materialised in the DB schema"). A flag `conversation_in_handoff` em [core/router/facts.py:66](apps/api/prosauai/core/router/facts.py#L66) e **sempre false**. A vision promete "Handoff — Transferencia de conversa do agente para atendente humano com todo o contexto" (`business/vision.md:169`), e o principio #2 de produto (`business/solution-overview.md:86`) e "IA e copiloto, nao piloto — o humano sempre pode assumir". Ambos impossiveis hoje.

Este epic fecha o buraco com (a) **um unico bit de estado** `ai_active` na conversation — handoff nao e estado intermediario, e ausencia de AI; (b) um **padrao adapter para helpdesks** (`ChatwootAdapter` + `NoneAdapter` no v1; Blip/Zendesk em epics futuros) que sincroniza esse bit com o que o helpdesk faz; (c) **admin composer emergencia** pra Pace ops intervir em qualquer tenant; (d) **metricas completas** no Performance AI tab. Multi-tenant e multi-helpdesk desde o dia um.

O escopo esta dividido em 3 PRs mergeaveis isoladamente em `develop`, cada um reversivel via feature flag per-tenant (`handoff.mode: off | shadow | on`) — ver `pitch.md` para cronograma detalhado e decisoes capturadas.

## Clarifications

### Session 2026-04-23 (epic-context activation)

- Q: Fonte unica de verdade para `ai_active` — Postgres ou Redis replicado? → A: Postgres `conversations.ai_active` e unica fonte de verdade. Router le direto do PG no `customer_lookup` step; fact `conversation_in_handoff` e Redis key `handoff:*` deprecated no PR-A (mantidos com logs `handoff_redis_legacy_read` para telemetria de obsolescencia), removidos no PR-B apos 7d com zero leituras.
- Q: Scheduler de auto-resume — ARQ worker novo ou asyncio periodic task? → A: Asyncio periodic task no FastAPI lifespan com singleton via `pg_try_advisory_lock(hashtext('handoff_resume_cron'))`. Cadencia 60s. Shutdown graceful aguarda iteration corrente via `asyncio.wait(timeout=5s)`. Zero infra nova.
- Q: Retention da tabela `bot_sent_messages` usada pela deteccao fromMe do NoneAdapter? → A: 48h retention (nao 7d). Cleanup cron `bot_sent_messages_cleanup_cron` a cada 12h. Risco residual apos 48h e zero porque bot nao re-envia mesma mensagem com mesmo ID.
- Q: Estrategia de rollout — feature flag binaria (off/on) ou com shadow mode intermediario? → A: Tri-estado `off | shadow | on`. Shadow emite eventos `handoff_events` com `shadow=true` mas **nao** muta `ai_active` — permite medir false-mute rate com trafego real antes de flipar `on`. +~50 LOC, removivel pos-validacao do primeiro tenant.
- Q: Identidade outbound do admin composer emergencia (quem aparece no Chatwoot do tenant)? → A: `sender_name = admin_user.email` (JWT sub). Atendente do tenant ve especificamente qual membro da Pace interveio. Trade-off aceito: expoe email interno Pace. Audit `handoff_events.metadata.admin_user_id` registra o sub do JWT. NoneAdapter (sem helpdesk): composer retorna 409 Conflict.
- Q: NoneAdapter em conversa de grupo — mesma semantica de 1:1 ou skip? → A: Skip silencioso da deteccao `fromMe` quando `inbound.is_group=true`. Log estruturado `noneadapter_group_skip`. Consistente com Decisao 21 do pitch (handoff v1 so 1:1; grupos continuam sempre com bot).

### Session 2026-04-23 (clarify)

> Resolucoes aplicadas em modo autonomo (pipeline dispatch) com base em best practices e consistencia com epics vizinhos. Confianca: Alta em Q1/Q3/Q4, Media em Q2/Q5 (dependem de fixture real de webhook Chatwoot a capturar no PR-A).

- Q: Retention de `handoff_events` nao estava definida em `FR-047`. Qual politica aplicar? → A: **90 dias de retencao full-detail** em `public.handoff_events`, alinhado com `trace_steps` do epic 008 (ADR-027 carve-out). Cleanup via cron diario `handoff_events_cleanup_cron` singleton (`pg_try_advisory_lock(hashtext('handoff_events_cleanup'))`). Agregados para metricas Performance AI sao calculados em tempo de query (index em `(tenant_id, created_at)`) — sem materialized view em v1. Archiving para cold storage fica em backlog.
- Q: Quais eventos exatos do Chatwoot o webhook handler deve processar em v1? → A: **Dois eventos apenas**: `conversation_updated` (detecta `assignee_id` delta → dispara `on_conversation_assigned` quando non-null, `on_conversation_resolved` quando vira null) e `conversation_status_changed` (detecta `status=resolved` → dispara resume). NAO subscrever `message_created`, `conversation_created`, `message_updated` em v1 — transcripts ja fluem via pipeline (FR-023) e criacao de conversa ProsaUAI e sempre disparada pelo cliente via Evolution, nunca pelo Chatwoot. Payloads desconhecidos retornam 200 OK no-op (FR-019).
- Q: Shape exato de `handoff.rules[]` em `tenants.yaml` (FR-038)? → A: **Array de strings referenciando regras ja existentes do router epic 004** (ex: `["customer_requests_human", "unresolved_after_3_turns"]`). Quando regra casa, router emite `state.mute_conversation(reason='rule_match', source='rule_match', metadata={'rule_name': <name>})`. Em v1 nao ha DSL novo para handoff rules — reuso integral da engine 004. Array vazio `[]` e o default (nenhuma regra automatica; so trigger por helpdesk/fromMe/manual).
- Q: Default e range valido para `auto_resume_after_hours` em `tenants.yaml`? → A: **Default 24** (conservador; cobre fim de expediente + overnight). **Range valido 1..168** (min 1h, max 1 semana). Valores fora do range → config_poller rejeita o reload com log de erro, mantem config anterior, emite metric `tenant_config_reload_failed{tenant}`. Tenant pode setar `null` para desabilitar timeout (so helpdesk_resolved ou manual_toggle retomam) — caso de uso: tenant dedicado a conversas de longa duracao.
- Q: Quando e como `conversations.external_refs.chatwoot.conversation_id` e populado inicialmente? → A: **Durante o pipeline step `customer_lookup`** (que ja amortiza reads per FR-022). Quando webhook Evolution carrega `chatwootConversationId` nao-null e `conversations.external_refs->'chatwoot'` ainda nao tem esse ID, pipeline faz UPDATE atomico (`SET external_refs = jsonb_set(external_refs, '{chatwoot}', $1::jsonb, true)`). Updates subsequentes com mesmo `conversation_id` sao no-op via comparacao. Primeiro webhook Chatwoot que chegar antes dessa populacao (improvavel, mas possivel em bootstrap) faz lookup reverso via Chatwoot API para correlacionar sender → fallback conservador; se falhar, 200 OK no-op + metric `chatwoot_webhook_unlinked_total{tenant}`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Atendente assume conversa no Chatwoot e bot silencia (Priority: P1)

Cliente do tenant **Ariel/ResenhAI** esta conversando com o bot pelo WhatsApp. A conversa chega ao Chatwoot (integracao Evolution ja operacional). Um atendente humano "assume" a conversa no Chatwoot (atribuindo a si mesmo). A partir desse momento, o bot **para imediatamente de responder** e as proximas mensagens do cliente nao disparam geracao de resposta automatica. O atendente responde manualmente via Chatwoot; o cliente recebe a resposta humana via Evolution/WhatsApp normalmente. Bot e humano **nunca respondem em cima um do outro**.

**Why this priority**: e o bug operacional mais visivel em producao hoje — cada conversa dupla e uma reclamacao direta do atendente. Sem esta historia, o epic nao entrega valor. Todas as outras historias (auto-resume, composer admin, metricas) dependem do bit `ai_active` funcionando aqui.

**Independent Test**: em ambiente staging com Chatwoot conectado, enviar mensagem como cliente, verificar que bot responde; atribuir a conversa no Chatwoot a um atendente; enviar nova mensagem do cliente — verificar que bot **nao** responde (trace mostra step `ai_muted_skip`), atendente responde via Chatwoot, cliente recebe apenas a resposta humana.

**Acceptance Scenarios**:

1. **Given** conversa ativa com `ai_active=true`, **When** atendente atribui a conversa a si mesmo no Chatwoot (webhook `conversation.assignee_changed` com assignee nao-null), **Then** ProsaUAI recebe o webhook em <500ms p95, valida HMAC, seta `ai_active=false` com `ai_muted_reason='chatwoot_assigned'`, emite evento `handoff_events` e o proximo inbound do cliente **nao** dispara LLM.
2. **Given** conversa com `ai_active=false` por assignee Chatwoot, **When** cliente envia nova mensagem, **Then** pipeline recebe, registra trace completo ate o step `generate` mas emite step `ai_muted_skip` e nao chama o provedor LLM — mensagem do cliente continua aparecendo no Chatwoot normalmente.
3. **Given** conversa com `ai_active=false`, **When** atendente responde via Chatwoot, **Then** a resposta segue o caminho normal Chatwoot→Evolution→WhatsApp; o bot nao produz output concorrente.
4. **Given** tenant com `handoff.mode=off`, **When** webhook Chatwoot chega, **Then** o webhook e ignorado (HTTP 200 para Chatwoot nao reencolhar retries) e `ai_active` permanece `true` — kill switch validado.
5. **Given** webhook duplicado (mesmo `chatwoot_event_id` reenviado por retry do Chatwoot), **When** recebido, **Then** segundo processamento e no-op (idempotency key Redis `handoff:wh:{chatwoot_event_id}` TTL 24h) e responde 200 sem gerar evento duplicado.
6. **Given** dois eventos concorrentes chegam simultaneamente (ex.: webhook Chatwoot + toggle manual admin), **When** processados em paralelo, **Then** `pg_advisory_xact_lock(hashtext(conversation_id))` serializa — apenas uma transicao prevalece, a outra observa o estado atualizado e pula ou re-aplica sem divergencia.

---

### User Story 2 — Atendente resolve conversa e bot retoma automaticamente (Priority: P1)

Atendente termina o atendimento humano e marca a conversa como "resolved" no Chatwoot. O bot precisa voltar a responder automaticamente quando o cliente enviar uma nova mensagem futura. Caso o atendente esqueca de resolver, um **timeout configuravel por tenant** (default 24h) garante que a conversa nao fica silenciada para sempre. O retorno do bot e **silencioso** — bot nao envia "oi" ao cliente; espera o proximo inbound organico.

**Why this priority**: sem return-to-bot, tenants ficam com conversas permanentemente mudas e o produto e inutilizavel — toda conversa que passou por humano vira "humano-only forever". Sem o timeout, um atendente que esquece de resolver (cenario comum fim de expediente) quebra o auto-atendimento do dia seguinte.

**Independent Test**: mutar uma conversa manualmente via SQL (simulando mute anterior), marcar como resolved no Chatwoot, verificar que `ai_active` volta para `true` com evento `source='helpdesk_resolved'`. Em paralelo, setar `ai_auto_resume_at` para 1 minuto no passado em outra conversa e aguardar rodada do cron — verificar resume com `source='timeout'`.

**Acceptance Scenarios**:

1. **Given** conversa com `ai_active=false` por `chatwoot_assigned`, **When** atendente marca a conversa como resolved no Chatwoot (webhook `conversation_resolved` ou `assignee_changed` com assignee=null), **Then** ProsaUAI seta `ai_active=true`, emite evento `event_type='resumed', source='helpdesk_resolved'`, e o proximo inbound do cliente dispara o pipeline normalmente.
2. **Given** conversa mutada ha mais de 24h (ou outro valor configurado em `tenant.handoff.auto_resume_after`), **When** scheduler `handoff_auto_resume_cron` roda (cadencia 60s), **Then** a conversa recebe `ai_active=true`, evento `source='timeout'`, e permanece silenciosa — bot nao envia mensagem proativa.
3. **Given** tenant com 2 replicas da API rodando em paralelo, **When** ambas tentam rodar o auto-resume cron, **Then** `pg_try_advisory_lock(hashtext('handoff_resume_cron'))` garante que apenas 1 replica executa; a outra dorme e re-tenta no proximo ciclo.
4. **Given** shutdown graceful do servico enquanto o cron esta executando a iteration, **When** sinal SIGTERM chega, **Then** `asyncio.wait(timeout=5s)` aguarda a iteration corrente terminar antes de finalizar — sem iteration abandonada em estado parcial.
5. **Given** conversa retoma via timeout, **When** cliente envia nova mensagem apos horas do retomar, **Then** primeiro inbound passa por safety guards normais (router, guards de seguranca) — nao ha short-circuit nem tratamento especial.
6. **Given** priorizacao de gatilhos de retorno — helpdesk resolve > toggle manual > timeout, **When** tres gatilhos competem no mesmo instante, **Then** resolve do helpdesk prevalece (evento e gravado com `source='helpdesk_resolved'`) e os demais observam o estado ja retomado.

---

### User Story 3 — Admin ve estado de handoff e pode toggar manualmente (Priority: P1)

Engenheiro/operador abre a aba Conversas no admin ProsaUAI (entregue no epic 008) e para cada conversa ve um **badge visivel**: "AI ativa" (verde) ou "AI silenciada por: {reason} desde {time}" (vermelho). Na tela de detalhe da conversa, um botao "Silenciar AI" / "Retomar AI" permite forcar o estado manualmente — util em escalacao de incidente ou quando um atendente externo do tenant esquece de marcar resolved.

**Why this priority**: ops precisa de visibilidade em minutos quando "o bot esta respondendo quando nao deveria" ou "o bot parou sozinho". Sem esta tela, o estado do bit `ai_active` fica invisivel ate alguem consultar SQL diretamente. Toggle manual e escape hatch para casos onde o helpdesk nao foi atualizado.

**Independent Test**: abrir admin em staging, localizar conversa ativa, verificar badge verde. Clicar "Silenciar AI" — verificar badge vira vermelho com motivo "manual_toggle" e timestamp. Enviar mensagem do cliente no WhatsApp — verificar que bot nao responde. Clicar "Retomar AI" — verificar badge volta verde. Enviar nova mensagem — verificar que bot responde.

**Acceptance Scenarios**:

1. **Given** admin autenticado abrindo lista de conversas, **When** tela renderiza, **Then** cada linha exibe badge de estado AI (verde/vermelho) alem das colunas ja existentes do epic 008 — sem regressao de latencia de inbox (<100ms mantido).
2. **Given** admin na tela de detalhe da conversa, **When** clica "Silenciar AI", **Then** chamada a `POST /admin/conversations/{id}/mute` seta `ai_active=false, ai_muted_reason='manual_toggle', ai_muted_by_user_id=<JWT.sub>`, emite evento e UI atualiza badge em <2s.
3. **Given** admin clica "Retomar AI" em conversa mutada, **When** backend processa, **Then** seta `ai_active=true`, emite evento `source='manual_toggle'`, limpa `ai_auto_resume_at`, e UI reflete badge verde.
4. **Given** admin tenta toggar em conversa de outro tenant (admin sem escopo), **When** chamada chega ao backend, **Then** autorizacao rejeita com 403 — nenhuma escrita ocorre.
5. **Given** admin Pace ops com acesso cross-tenant (via `pool_admin` BYPASSRLS, ADR-027), **When** toga conversa de qualquer tenant, **Then** operacao succeeds e audit log registra `admin_user_id` para rastreabilidade.

---

### User Story 4 — Tenant sem helpdesk: atendente responde direto no WhatsApp (NoneAdapter) (Priority: P2)

Um tenant novo (onboarding futuro) nao tem Chatwoot nem outro helpdesk — o atendente usa o celular com WhatsApp Business e responde direto ao cliente. Nesse cenario, toda mensagem que o atendente envia chega via Evolution com `fromMe: true`. O sistema precisa **detectar automaticamente** que um humano respondeu (por outra via que nao o bot) e silenciar a IA por um periodo configuravel (default 30 min), renovando o timer a cada nova mensagem do humano. Em conversa de grupo, o skip e silencioso (grupos estao fora do escopo v1 de handoff).

**Why this priority**: Ariel/ResenhAI ja tem Chatwoot — historia 1 resolve o caso primario. NoneAdapter cobre onboarding de tenants que comecam sem infraestrutura. P2 porque a arquitetura do adapter (historia 1) ja existe e NoneAdapter reusa; sem clientes Pace pedindo agora, o risco de atrasar e baixo. Alem disso, valida a abstracao `HelpdeskAdapter` com dois shapes radicalmente diferentes (Chatwoot API vs. detecao comportamental via Evolution).

**Independent Test**: tenant staging configurado com `helpdesk.type: none`. Enviar mensagem como cliente — bot responde, `bot_sent_messages` grava o ID retornado pelo `sendText`. Simular webhook Evolution com `fromMe: true` e `message_id` nao presente em `bot_sent_messages` — verificar que `ai_active` fica `false` por 30 min (`ai_auto_resume_at = now + 30min`, `source='fromMe_detected'`). Simular segundo `fromMe:true` — verificar que timer reinicia. Em paralelo, simular webhook `fromMe:true` com `message_id` que casa com `bot_sent_messages` (bot echo) — verificar que **nao** muta.

**Acceptance Scenarios**:

1. **Given** tenant com `helpdesk.type: none` e conversa ativa, **When** Evolution envia webhook com `fromMe: true` e `message_id` nao registrado em `bot_sent_messages`, **Then** sistema seta `ai_active=false`, `ai_muted_reason='fromMe_detected'`, `ai_auto_resume_at = now + tenant.handoff.human_pause_minutes` (default 30), emite evento.
2. **Given** bot acabou de enviar mensagem e Evolution retorna echo com `fromMe: true`, **When** webhook chega com `message_id` presente em `bot_sent_messages` (sent_at <10s atras), **Then** sistema **nao** muta — classifica como echo do bot.
3. **Given** conversa com NoneAdapter e mute ativo, **When** humano envia segunda mensagem `fromMe:true`, **Then** `ai_auto_resume_at` e atualizado para `now + human_pause_minutes` (timer reinicia).
4. **Given** conversa de grupo (`inbound.is_group=true`) com tenant `helpdesk.type: none`, **When** webhook `fromMe: true` chega, **Then** NoneAdapter **skip silencioso** da deteccao (log estruturado `noneadapter_group_skip`), conversa permanece com `ai_active=true`, bot continua respondendo normalmente.
5. **Given** tabela `bot_sent_messages` com entradas acima de 48h, **When** cron `bot_sent_messages_cleanup_cron` roda (cadencia 12h), **Then** entradas antigas sao deletadas; novas continuam sendo gravadas.

---

### User Story 5 — Pace ops usa composer emergencia para intervir em qualquer tenant (Priority: P2)

Engenheiro Pace identifica um incidente em producao (ex.: configuracao quebrada de um tenant, cliente VIP bloqueado, atendente do tenant fora do ar). Abre a conversa no admin ProsaUAI e usa um **composer de emergencia** que envia mensagem direto para o cliente via o helpdesk configurado no tenant — a mensagem aparece no Chatwoot do tenant como se tivesse saido do helpdesk, assinada com o **email do admin Pace** para que o atendente do tenant saiba especificamente quem da Pace interveio. Uso esperado: ≤5% do trafego.

**Why this priority**: composer e escape hatch de ops, nao fluxo primario. Se atrasar, PR-A+B ainda entregam o valor core (bot nao fala em cima do humano). P2 porque depende de PR-A+B estarem estaveis e porque NoneAdapter (tenant sem helpdesk) deve responder 409 — o que so faz sentido depois do adapter protocol estar consolidado.

**Independent Test**: autenticado como admin Pace, abrir conversa de um tenant com Chatwoot configurado, digitar mensagem no composer, clicar enviar. Verificar (a) mensagem chega ao cliente via WhatsApp, (b) mensagem aparece no Chatwoot do tenant com `sender_name=<admin.email>`, (c) `handoff_events` registra `event_type='admin_reply_sent'` com `metadata.admin_user_id=<JWT.sub>`. Repetir com tenant `helpdesk.type: none` — verificar resposta 409 Conflict com `{error: 'no_helpdesk_configured'}`.

**Acceptance Scenarios**:

1. **Given** admin Pace em conversa de tenant com `helpdesk.type: chatwoot`, **When** envia mensagem via composer, **Then** endpoint `POST /admin/conversations/{id}/reply` delega a `ChatwootAdapter.send_operator_reply()`, injeta `sender_name=<JWT.email>`, mensagem e entregue ao cliente em <2s p95.
2. **Given** mensagem enviada via composer, **When** chega ao Chatwoot, **Then** aparece no thread do tenant com identidade do admin Pace (email), permitindo atendente do tenant ver quem interveio.
3. **Given** admin tenta usar composer em tenant com `helpdesk.type: none`, **When** requisicao chega, **Then** backend responde 409 Conflict com `{error: 'no_helpdesk_configured'}` — UI mostra mensagem explicativa "tenant nao tem helpdesk configurado".
4. **Given** Chatwoot do tenant esta off (circuit breaker aberto), **When** admin envia via composer, **Then** requisicao falha com 503 e UI exibe "helpdesk indisponivel, tente em alguns minutos"; `handoff_events` nao e gravado (fire-and-forget com visibility para o caller).
5. **Given** mensagem enviada com sucesso via composer, **When** `handoff_events` e persistido, **Then** metadata inclui `admin_user_id=<JWT.sub>` para auditoria granular sem expor o email no payload do evento.

---

### User Story 6 — Admin audita taxas e duracoes de handoff no Performance AI (Priority: P2)

Admin abre a aba Performance AI (entregue no epic 008) e ve uma nova linha dedicada a Handoff, com 4 cards: (1) **Taxa de handoff** — % conversas com ao menos 1 evento mute no periodo; (2) **Duracao media silenciada** — avg `resumed_at - muted_at`; (3) **Breakdown por origem** — pie chart das 5 origens (`chatwoot_assigned`, `fromMe_detected`, `manual_toggle`, `rule_match`, `safety_trip`); (4) **SLA breaches** — count de conversas onde o timeout foi acionado (atendente esqueceu de resolver).

**Why this priority**: observabilidade e valor operacional continuo, nao gate de merge. Com PR-A+B, o sistema **funciona**; com PR-C, o sistema e **monitoravel**. P2 porque e follow-up natural do admin evolution (epic 008) e nao bloqueia nenhum usuario final.

**Independent Test**: popular staging com ao menos 10 eventos de handoff variados (multiplas origens, com e sem timeout). Abrir Performance AI > linha Handoff. Verificar que 4 cards renderizam em <3s, com numeros coerentes vs. query SQL direta em `handoff_events`.

**Acceptance Scenarios**:

1. **Given** tenant com 50 conversas no periodo e 12 eventos de handoff, **When** admin abre Performance AI, **Then** card "Taxa" exibe ~24% (12/50), card "Duracao media" exibe minutos/horas apropriados, pie chart mostra distribuicao por origem.
2. **Given** 3 conversas que atingiram auto_resume por timeout, **When** Performance AI carrega, **Then** card "SLA breaches" exibe 3 com link para filtrar no Trace Explorer.
3. **Given** shadow mode ativo em algum tenant, **When** admin visualiza Performance AI, **Then** eventos `shadow=true` aparecem em cor distinta (cinza/hachurado) e nao contam para as metricas principais — permitem comparar "quanto seria mutado" sem efeito real.
4. **Given** range de datas selecionado no filtro existente do epic 008, **When** admin muda para "ultimos 7d", **Then** todos os 4 cards recalculam para o periodo sem recarregar a pagina.
5. **Given** tenant sem nenhum evento de handoff no periodo, **When** renderiza, **Then** cards mostram "N/A" ou zero de forma clara (nao quebram layout).

---

### User Story 7 — Rollout shadow mode valida false-mute antes de flipar on (Priority: P3)

Antes de ligar handoff pra valer em producao, admin Pace configura o primeiro tenant (Ariel) em `handoff.mode: shadow`. Por 7 dias, todos os gatilhos de mute sao **registrados como eventos** mas **nao mutam** o bot. Admin observa no Performance AI quantos mutes teriam ocorrido e compara com telemetria de "humano respondeu mesmo" para estimar false-mute rate. Se o numero estiver sustentavel, flipa para `on`; se nao, ajusta regras e repete.

**Why this priority**: shadow e pratica operacional opcional — se o time julgar que o risco e aceitavel direto (trafego baixo hoje, reversao trivial via `mode: off`), pode pular. P3 porque adiciona ~50 LOC e 4 testes mas e removivel apos validacao do primeiro tenant. Decisao de remover ou manter o codigo de shadow fica para retro pos-epic.

**Independent Test**: configurar Ariel em `handoff.mode: shadow` no staging. Rodar 48h de trafego sintetico com alguns webhooks Chatwoot de assignee. Verificar que `handoff_events` tem entradas com `shadow=true` e que `conversations.ai_active` permanece `true` em todas. Verificar no Performance AI que eventos shadow aparecem em estilo visual distinto.

**Acceptance Scenarios**:

1. **Given** tenant com `handoff.mode: shadow`, **When** webhook Chatwoot de assignee chega, **Then** evento `handoff_events` e gravado com `shadow=true` e `ai_active` **nao** muda (bot continua respondendo).
2. **Given** mesmo tenant em shadow, **When** cliente envia mensagem, **Then** bot responde normalmente — pipeline `generate` safety net ignora shadow events.
3. **Given** admin Pace observou 7d de shadow sem false-mute relatado, **When** altera `tenants.yaml` para `handoff.mode: on` (proximo poll 60s carrega), **Then** proximos webhooks passam a mutar de fato sem deploy.
4. **Given** codigo de shadow mode e considerado desnecessario apos validacao, **When** for removido em epic follow-up, **Then** mudanca e localizada em ~3 pontos: `state.mute_conversation()`, Performance AI rendering, testes do shadow.

---

### Edge Cases

- **Echo do proprio bot (R2)**: Evolution pode devolver `fromMe: true` para mensagens que o bot acabou de enviar. Tracking `bot_sent_messages` + janela de tolerancia `sent_at < 10s` garante zero false positive de auto-mute.
- **Webhook duplicado**: Chatwoot pode reenviar o mesmo evento em retry. Idempotency key Redis (TTL 24h) garante processamento unico.
- **Chatwoot muda formato de webhook entre versoes**: fixtures reais capturadas em dev + contract test detectam regressao. Versao Chatwoot fixada no `tenants.yaml` per-tenant.
- **Chatwoot downtime**: circuit breaker per-helpdesk abre apos 5 falhas em 60s. Bot **continua** respondendo normal (mute nao depende de Chatwoot estar vivo — mute ja foi commitado no PG). So private notes fire-and-forget falham silenciosamente ate breaker fechar.
- **Auto-resume re-engaja bot em conversa encerrada pelo cliente**: bot e silencioso no resume (nao envia "oi"). Primeiro inbound pos-resume passa por guards normais; se cliente nao escrever, bot nao fala.
- **Composer emergencia cria confusao "quem respondeu"**: badge visivel no Chatwoot note + sender_name=<admin.email> deixam explicito. Audit log persistido.
- **Shared Chatwoot Pace vira bottleneck com >20 tenants**: rate limit per-tenant direcao ProsaUAI→Chatwoot via token bucket Redis. Implementado so se virar problema (monitorado via metric `helpdesk_api_4xx`).
- **Migration `ai_active=true` default em tenants em conversa ativa**: migration e aditiva e nao altera comportamento. `handoff.mode: off` default protege rollout — nada muda ate Pace ligar explicitamente.
- **NoneAdapter em conversa de grupo**: skip silencioso + log estruturado. v1 nao suporta handoff em grupos (semantica ambigua — quem e "o humano"?). Grupos continuam com bot.
- **Meta Cloud janela 24h expirada**: quando helpdesk tenta responder via Meta Cloud fora da janela 24h, adapter retorna erro. Admin UI mostra alerta "janela expirou, cliente precisa escrever primeiro". Nao tenta template approved.
- **Dois eventos concorrentes na mesma conversa**: `pg_advisory_xact_lock(hashtext(conversation_id))` serializa. Granularidade alta (por conversation_id) = zero contention em cargas reais.
- **Race entre pipeline start e mute**: step `generate` faz `SELECT ai_active FOR UPDATE` imediatamente antes do call LLM. Se flip aconteceu entre pipeline inicio e gen, skip sem delivery.
- **Deprecacao Redis key `handoff:*` quebra leitor esquecido**: PR-A mantem read path ativo com log `handoff_redis_legacy_read`. PR-B remove so depois de 7d com zero leituras.

## Requirements *(mandatory)*

### Functional Requirements

#### Estado e transicoes

- **FR-001**: Sistema MUST armazenar um unico bit de estado `conversations.ai_active BOOLEAN NOT NULL DEFAULT TRUE` indicando se o bot pode responder naquela conversa.
- **FR-002**: Sistema MUST gravar metadata de mute em colunas adicionais: `ai_muted_reason TEXT NULL`, `ai_muted_at TIMESTAMPTZ NULL`, `ai_muted_by_user_id UUID NULL`, `ai_auto_resume_at TIMESTAMPTZ NULL`.
- **FR-003**: Sistema MUST considerar Postgres `conversations.ai_active` como **unica fonte de verdade**. Router e pipeline leem direto do PG no step `customer_lookup`.
- **FR-004**: Sistema MUST manter temporariamente (PR-A) a Redis key `handoff:{tenant}:{sender_key}` e o fact `conversation_in_handoff` apenas para telemetria de obsolescencia (log estruturado `handoff_redis_legacy_read`); remocao ocorre em PR-B apos 7d com zero leituras.
- **FR-005**: Toda transicao de `ai_active` MUST ser protegida por `pg_advisory_xact_lock(hashtext(conversation_id))` para prevenir corrida entre webhook, fromMe detection, toggle manual e auto-resume.
- **FR-006**: Toda transicao MUST seguir ordenacao: (a) commit de `ai_active` no PG, (b) emissao de evento em `handoff_events`, (c) side effects fire-and-forget (push private note, sync externo). Side effects NUNCA precedem o commit.

#### Triggers de mute

- **FR-007**: Sistema MUST aceitar 5 origens validas de mute, cada uma gerando evento `handoff_events.source`: `chatwoot_assigned`, `fromMe_detected`, `manual_toggle`, `rule_match`, `safety_trip`.
- **FR-008**: Ao receber webhook Chatwoot `conversation.assignee_changed` com `assignee_id` nao-null e `conversation_id` mapeavel via `conversations.external_refs`, sistema MUST chamar `state.mute_conversation(reason='chatwoot_assigned')`.
- **FR-009**: Ao receber webhook Chatwoot `conversation.resolved` ou `assignee_changed` com assignee=null, sistema MUST chamar `state.resume_conversation(source='helpdesk_resolved')`.
- **FR-010**: NoneAdapter MUST interceptar webhooks Evolution com `fromMe: true`: se `message_id` NAO esta em `bot_sent_messages` para aquele tenant → mute com `reason='fromMe_detected'` e `ai_auto_resume_at = now + tenant.handoff.human_pause_minutes` (default 30 min).
- **FR-011**: NoneAdapter MUST renovar `ai_auto_resume_at` a cada novo `fromMe:true` que nao seja echo do bot (timer reinicia).
- **FR-012**: NoneAdapter MUST pular silenciosamente a deteccao `fromMe` quando `inbound.is_group=true`, emitindo log estruturado `noneadapter_group_skip` com `tenant_id` e `conversation_id`.

#### Gatilhos de retorno (auto-resume)

- **FR-013**: Sistema MUST implementar 3 gatilhos de retorno ao bot, com priorizacao `helpdesk_resolved > manual_toggle > timeout`:
  - (a) webhook do helpdesk sinalizando assignee=null ou conversation resolved,
  - (b) scheduler periodico disparando `ai_auto_resume_at < now()`,
  - (c) admin toga manualmente via endpoint `/admin/conversations/{id}/unmute`.
- **FR-014**: Scheduler `handoff_auto_resume_cron` MUST rodar como asyncio periodic task no FastAPI lifespan com cadencia 60s, singleton cross-replicas via `pg_try_advisory_lock(hashtext('handoff_resume_cron'))`.
- **FR-015**: Shutdown graceful MUST aguardar iteration corrente do cron via `asyncio.wait(timeout=5s)` antes de finalizar, para evitar iteration abandonada em estado parcial.
- **FR-016**: Retorno ao bot MUST ser silencioso — sistema NUNCA envia mensagem proativa ao cliente ao retomar (sem "oi"); bot so responde quando proximo inbound organico chega, passando por guards normais.

#### Webhook Chatwoot

- **FR-017**: Endpoint `POST /webhook/helpdesk/chatwoot/{tenant_slug}` MUST validar assinatura HMAC via header `X-Webhook-Signature` (hex digest de `HMAC-SHA256(webhook_secret, raw_body)`, comparacao constant-time via `hmac.compare_digest`). Secret per-tenant definido em `tenants.yaml:helpdesk.webhook_secret`. Scheme e **custom do prosauai** (nao o oficial `X-Chatwoot-Signature` do Chatwoot Cloud) porque Chatwoot self-hosted per-tenant permite configurar header arbitrario.
- **FR-017a**: Webhook handler MUST processar explicitamente apenas dois tipos de evento Chatwoot em v1 (Clarify Q2): (a) `conversation_updated` — detecta delta em `assignee_id` e dispara `on_conversation_assigned` (assignee_id non-null) ou `on_conversation_resolved` (assignee_id virou null); (b) `conversation_status_changed` — quando `status=resolved`, dispara resume. Outros tipos (`message_created`, `conversation_created`, `message_updated`) sao registrados em log com `event_type=unhandled` e respondem 200 OK sem side effect.
- **FR-018**: Webhook handler MUST ser idempotente via Redis SET NX `handoff:wh:{chatwoot_event_id}` TTL 24h. Segundo recebimento do mesmo event_id retorna 200 sem gerar evento duplicado.
- **FR-019**: Webhook handler MUST responder sempre 200 OK ao Chatwoot, mesmo quando tenant esta em `mode: off`, quando payload e desconhecido ou quando conversa ainda nao esta linkada via `external_refs` — para evitar retries infinitos do helpdesk.
- **FR-020**: Circuit breaker per-helpdesk MUST abrir apos 5 falhas consecutivas em 60s, meia-abrir apos 30s, fechar apos 1 sucesso; quando aberto, pula chamadas outbound (push private note, send operator reply) e emite metric `helpdesk_breaker_open{tenant,helpdesk}`.

#### Pipeline safety net

- **FR-021**: Pipeline step `generate` MUST fazer `SELECT ai_active FROM conversations WHERE id=$1 FOR UPDATE` imediatamente antes da chamada LLM; se `false`, pula geracao e emite trace step `ai_muted_skip` com `ai_muted_reason`.
- **FR-022**: Pipeline step `customer_lookup` MUST amortizar o read de `ai_active` junto com a resolucao do customer (single SELECT), substituindo o read Redis atual em `api/webhooks/__init__.py:175`.
- **FR-022a**: Pipeline step `customer_lookup` MUST popular `conversations.external_refs.chatwoot.{conversation_id, inbox_id}` quando o webhook Evolution carrega `chatwootConversationId` nao-null e o campo ainda nao contem esse ID (UPDATE atomico via `jsonb_set`). Primeira mensagem da conversa cria o linkage; mensagens subsequentes com mesmo ID sao no-op por comparacao.
- **FR-023**: Pipeline MUST continuar rodando content processing (epic 009) mesmo quando `ai_active=false` — atendente precisa ver transcript de audio como private note. Push da private note e fire-and-forget; falha nao bloqueia pipeline.

#### NoneAdapter infraestrutura

- **FR-024**: Sistema MUST manter tabela `bot_sent_messages (tenant_id, message_id, sent_at, conversation_id)` com PK `(tenant_id, message_id)` para tracking de mensagens enviadas pelo bot.
- **FR-025**: Outbound Evolution MUST gravar `bot_sent_messages` apos cada send bem-sucedido, fire-and-forget.
- **FR-026** **[DEPRECATED 2026-04-24]**: Requisito removido em follow-up do epic 010. A semantica original ("janela de 10s mesmo sem match de `message_id`") foi implementada como AND restrito (`message_id = $2 AND sent_at >= now() - 10s`), anulando o beneficio da retention de 48h — echoes legitimos com match exato mas sent_at > 10s eram classificados como operador real e mutavam erroneamente. Deteccao de echo agora usa **apenas** match por PK `(tenant_id, message_id)` em `bot_sent_messages`; retention 48h (FR-027) e a unica janela. Nao implementar.
- **FR-027**: Cron `bot_sent_messages_cleanup_cron` MUST rodar a cada 12h, singleton cross-replicas via `pg_try_advisory_lock(hashtext('bsm_cleanup_cron'))`, e deletar entradas com `sent_at < now() - interval '48 hours'`.

#### Admin API

- **FR-028**: Endpoint `POST /admin/conversations/{id}/mute` MUST aceitar JSON opcional `{reason?: string}`, setar `ai_active=false, ai_muted_reason='manual_toggle', ai_muted_by_user_id=<JWT.sub>` e emitir evento.
- **FR-029**: Endpoint `POST /admin/conversations/{id}/unmute` MUST setar `ai_active=true`, limpar `ai_muted_reason/at/by/auto_resume_at` e emitir evento `source='manual_toggle'`.
- **FR-030**: Endpoint `POST /admin/conversations/{id}/reply` (composer emergencia) MUST delegar ao adapter do helpdesk do tenant, injetando `sender_name=<JWT.email>` e registrando `handoff_events.metadata.admin_user_id=<JWT.sub>`.
- **FR-031**: Endpoint `/admin/conversations/{id}/reply` em tenant com `helpdesk.type: none` MUST retornar 409 Conflict com body `{error: 'no_helpdesk_configured'}`.
- **FR-032**: Admin endpoints MUST respeitar escopo de tenant do JWT (admin do tenant so opera em conversas do proprio tenant) exceto para Pace ops com `pool_admin` BYPASSRLS (ADR-027).

#### Admin UI

- **FR-033**: Lista de conversas no admin MUST exibir badge de estado AI (verde "AI ativa" ou vermelho "AI silenciada por: {reason} desde {time}") em cada linha, sem regressao de latencia de inbox (<100ms mantido).
- **FR-034**: Tela de detalhe da conversa MUST exibir botao contextual "Silenciar AI" quando `ai_active=true` ou "Retomar AI" quando `false`.
- **FR-035**: Tela de detalhe MUST exibir composer de emergencia para Pace ops com textarea e botao "Enviar como Pace ops" quando helpdesk do tenant e diferente de `none`.
- **FR-036**: Aba Performance AI MUST adicionar linha "Handoff" com 4 cards: taxa, duracao media, breakdown por origem (pie chart Recharts), SLA breaches (count de timeouts).
- **FR-037**: Cards Performance AI MUST respeitar o filtro de range de datas existente do epic 008 e recalcular sem recarregar a pagina.

#### Feature flag e rollout

- **FR-038**: `tenants.yaml` MUST aceitar bloco `helpdesk: {type: chatwoot|none, credentials: {...}}` e bloco separado `handoff: {mode: off|shadow|on, auto_resume_after_hours: int|null, human_pause_minutes: int, rules: [string]}` (ortogonal: helpdesk = infra, handoff = comportamento).
- **FR-038a**: `handoff.auto_resume_after_hours` MUST aceitar inteiros no range `1..168` (1h a 1 semana) ou `null` para desabilitar timeout. Default `24`. Valores fora do range fazem config_poller rejeitar o reload com log de erro + metric `tenant_config_reload_failed{tenant}` — configuracao anterior permanece ativa.
- **FR-038b**: `handoff.rules[]` MUST ser array de strings referenciando nomes de regras ja existentes do router (epic 004). Default `[]`. Quando uma regra listada casa durante o step `route` do pipeline, router emite `state.mute_conversation(reason='rule_match', source='rule_match', metadata={'rule_name': <name>})`. V1 nao introduz DSL novo de rules — reuso integral de 004.
- **FR-038c**: `handoff.human_pause_minutes` MUST aceitar inteiros no range `1..1440` (1 minuto a 24h). Default `30`. Usado apenas por `NoneAdapter` no calculo de `ai_auto_resume_at` (FR-010).
- **FR-039**: Default `handoff.mode` MUST ser `off` — ate Pace ligar explicitamente, nenhum tenant tem comportamento alterado.
- **FR-040**: Em `handoff.mode: shadow`, sistema MUST gravar eventos `handoff_events` com flag `shadow=true` mas NAO mutar `ai_active`. Pipeline `generate` ignora shadow events.
- **FR-041**: Em `handoff.mode: off`, webhooks Chatwoot MUST ser recebidos e respondidos 200 OK mas ignorados (no-op) — nenhum evento gerado.
- **FR-042**: config_poller MUST re-ler `tenants.yaml` a cada 60s; mudancas de `handoff.mode` entram em vigor sem deploy.

#### Adapter pattern

- **FR-043**: Sistema MUST definir Protocol `HelpdeskAdapter` em `apps/api/prosauai/handoff/base.py` com metodos: `on_conversation_assigned()`, `on_conversation_resolved()`, `push_private_note()`, `send_operator_reply()`, `verify_webhook_signature()`.
- **FR-044**: Sistema MUST prover `ChatwootAdapter` (httpx client + HMAC verify + Chatwoot API v1) e `NoneAdapter` (Evolution hook + fromMe detection) como implementacoes v1.
- **FR-045**: Registry `get_helpdesk_adapter(helpdesk_type)` MUST retornar a implementacao apropriada ou levantar `UnknownHelpdesk` se tipo nao registrado.
- **FR-046**: Adicao de novo adapter (ex.: Blip, Zendesk) em epic futuro MUST requerer apenas nova classe + registro + fixtures de webhook, sem mudanca no core.

#### Event sourcing e auditoria

- **FR-047**: Tabela `handoff_events` MUST ser append-only em schema `public` (admin-only, carve-out ADR-027) com colunas `(id, tenant_id, conversation_id, event_type, source, metadata jsonb, shadow bool, created_at)` e indices `(tenant_id, created_at)` + `(conversation_id, created_at)`.
- **FR-047a**: Retention de `handoff_events` MUST ser **90 dias** full-detail, alinhado com `trace_steps` do epic 008. Cleanup via cron diario `handoff_events_cleanup_cron` — asyncio periodic task singleton cross-replicas via `pg_try_advisory_lock(hashtext('handoff_events_cleanup'))`, cadencia 24h, executa `DELETE FROM handoff_events WHERE created_at < now() - interval '90 days'` em batches de 1000 linhas. Agregados para metricas Performance AI sao calculados em tempo de query — sem materialized view em v1.
- **FR-048**: Todo mute/unmute MUST emitir evento correspondente. `event_type` varia: `muted`, `resumed`, `admin_reply_sent`, `breaker_open`, `breaker_closed`.
- **FR-049**: `metadata` MUST conter contexto especifico ao evento: para `muted` → `{reason, source, triggered_by, external_refs}`; para `admin_reply_sent` → `{admin_user_id, message_id, helpdesk_conversation_id}`.
- **FR-050**: Operator IDs externos (Chatwoot assignee_id, etc.) MUST ser armazenados em `metadata` mas NAO tagueados em metricas Prometheus/Phoenix — evita cardinality explosion.

#### Observabilidade

- **FR-051**: `conversation_id` e `tenant_id` MUST ser propagados em OpenTelemetry baggage desde o webhook inbound original ate o POST pro helpdesk — Trace Explorer (epic 008) deve mostrar cadeia completa.
- **FR-052**: Sistema MUST expor metricas Prometheus: `handoff_events_total{tenant, event_type, source}`, `handoff_duration_seconds_bucket{tenant}`, `helpdesk_webhook_latency_seconds{tenant, helpdesk}`, `helpdesk_breaker_open{tenant, helpdesk}`.
- **FR-053**: Logs MUST ser estruturados (structlog) com campos padrao: `tenant_id`, `conversation_id`, `event_type`, `source`, `helpdesk_type`, `admin_user_id` (quando aplicavel).

### Key Entities

- **Conversation**: ja existe. Ganha colunas `ai_active`, `ai_muted_reason`, `ai_muted_at`, `ai_muted_by_user_id`, `ai_auto_resume_at`, `external_refs JSONB` (ex.: `{"chatwoot": {"conversation_id": 123, "inbox_id": 4}}`).
- **HandoffEvent**: nova entidade append-only em `public`. Registra toda transicao de estado de handoff — origem, destino, reason, metadata, se foi shadow. Base de todas as metricas e auditorias.
- **BotSentMessage**: nova tabela tracking. `(tenant_id, message_id, conversation_id, sent_at)`. Retention 48h. Fundamental para deteccao `fromMe` do NoneAdapter distinguir humano de echo do bot.
- **HelpdeskAdapter**: contrato de integracao. Cada helpdesk (Chatwoot, None, futuro Blip/Zendesk) implementa. Isola o core ProsaUAI das especificidades de API externa.
- **TenantHandoffConfig**: bloco em `tenants.yaml`. Governa `mode`, `auto_resume_after`, `human_pause_minutes`, `rules`. Poll 60s — sem deploy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **Zero respostas do bot em conversas com atendente humano atuando** — em periodo de 30d pos-rollout full (Ariel e ResenhAI em `mode: on`), numero de mensagens do bot entregues em conversas com `ai_active=false` e zero. Medido via query `handoff_events WHERE event_type='muted'` cruzada com `messages.sent_by_bot_at BETWEEN muted_at AND resumed_at`.
- **SC-002**: **Latencia webhook Chatwoot → mute efetivo <500ms p95** — tempo entre `POST /webhook/helpdesk/chatwoot` e `ai_active=false` commitado no PG. Measurado via metric `helpdesk_webhook_latency_seconds`.
- **SC-003**: **Latencia admin composer → outbound <2s p95 end-to-end** — tempo entre `POST /admin/conversations/{id}/reply` e mensagem entregue ao cliente via helpdesk.
- **SC-004**: **Zero regressao de latencia no pipeline de texto** — p95 do pipeline em mensagens que NAO disparam handoff permanece ate 5ms pior que baseline do epic 009 (medido em dia de trafego similar).
- **SC-005**: **Zero regressao em suites existentes** — 173 tests epic 005 + 191 tests epic 008 + suites epic 009 continuam passando. Pipeline CI verde.
- **SC-006**: **False positives de fromMe NoneAdapter <1%** — em periodo de teste com tenant `helpdesk.type: none`, menos de 1% dos eventos `fromMe_detected` sao de echo do bot (validado via auditoria de trace no Trace Explorer).
- **SC-007**: **Idempotencia de webhook 100%** — em teste de carga com 1000 webhooks duplicados, zero eventos duplicados em `handoff_events` e zero mutes duplicados.
- **SC-008**: **Cron auto-resume dentro de SLA 60s** — conversas com `ai_auto_resume_at` no passado sao retomadas em no maximo 60s (proxima rodada do cron), medido em staging com 50 conversas.
- **SC-009**: **Circuit breaker valida isolamento** — com Chatwoot down simulado, (a) bot continua respondendo tenants sem mute ativo; (b) mutes ja commitados permanecem; (c) private notes fire-and-forget pulam silenciosamente; (d) metric `helpdesk_breaker_open` alerta apos 5min aberto.
- **SC-010**: **Observabilidade 100%** — todo evento de handoff aparece no Trace Explorer com cadeia completa (`conversation_id` + `tenant_id` em baggage desde o webhook original). Performance AI tab renderiza 4 cards em <3s em dataset com 10k eventos.
- **SC-011**: **Rollout reversivel 100%** — em teste de chaos, alterar `handoff.mode: on → off` via `tenants.yaml` faz com que proximo webhook (dentro de 60s) seja ignorado e bot volte a responder. Reversao sem deploy validada.
- **SC-012**: **Shadow mode prediz realidade com erro ≤10%** — apos 7d de shadow em Ariel, a taxa predita de mute shadow casa com a taxa real observada apos flip para `on` dentro de 10% de diferenca (feedback loop de validacao de false-mute).
- **SC-013**: **Admin UI p95 <2s** — abrir tela de detalhe de conversa (com badge + historico + composer) em <2s p95 no dataset real de Ariel (centenas de conversas no tenant).
- **SC-014**: **Auditoria cross-tenant para Pace ops** — 100% das mensagens enviadas via admin composer sao rastreaveis em `handoff_events.metadata.admin_user_id` com matching em audit_logs existente.

## Assumptions

- **A1**: Integracao Chatwoot ↔ Evolution ja esta operacional — todo webhook Evolution ja injeta `chatwootConversationId` (ref: `tests/fixtures/captured/README.md:208-211`). Este epic consome essa integracao; nao a constroi.
- **A2**: Chatwoot da Pace continua operacional e sera a unica instancia Chatwoot usada em producao v1 (compartilhada entre Ariel e ResenhAI via inboxes separados). Tenants futuros podem ter Chatwoot proprio em VPS propria — shape do `tenants.yaml` ja acomoda.
- **A3**: `pool_admin` BYPASSRLS (ADR-027) ja existe e permite que endpoints admin ProsaUAI leiam/escrevam cross-tenant. Novas tabelas admin (`handoff_events`) usam o mesmo padrao.
- **A4**: Advisory locks Postgres (`pg_try_advisory_lock`, `pg_advisory_xact_lock`) estao disponiveis — reuso de mecanismo ja usado em `ops/migrate.py`.
- **A5**: Trace Explorer e Performance AI tab do epic 008 sao estaveis e extensiveis — este epic adiciona uma linha (Performance AI) e um badge (Conversations), sem refatoracao.
- **A6**: Equipes de ops Pace estao disponiveis para operar o rollout shadow → on em 2 tenants durante 4 semanas (cronograma em pitch.md §Rollout Plan).
- **A7**: Nenhuma biblioteca Python nova e necessaria — reuso de httpx, asyncpg, redis[hiredis], structlog, opentelemetry-sdk ja presentes.
- **A8**: Blip, Zendesk, Freshdesk, Front e outros helpdesks sao **escopo fora** — abordados em epic 010.1 quando houver cliente demandando. HelpdeskAdapter protocol ja acomoda.
- **A9**: Handoff em conversa de grupo e **escopo fora**. Semantica ambigua ("quem e o humano?") — v1 so 1:1. NoneAdapter pula grupos silenciosamente.
- **A10**: Migration `ai_active=true` default em producao e aditiva (novo campo, novo indice) — sem alteracao de comportamento ate flag ligar. Testada com cold start de PG em dataset de staging.
- **A11**: SLA breach notifications em Slack/email estao **fora do escopo** — eventos sao publicados; integracao com canais de alerta vira no epic 014 (Alerting + WhatsApp Quality).
- **A12**: Migration de conversas historicas e **fora do escopo** — epic nao re-processa conversas fechadas antes do deploy. Todas conversas existentes entram com `ai_active=true`.
- **A13**: Cleanup do codigo de shadow mode apos validacao do primeiro tenant e decisao operacional pos-epic — nao e gate de merge.
- **A14**: Exposicao do email interno Pace no Chatwoot do tenant (via `sender_name = admin_user.email` do composer) e trade-off aceito conscientemente. Se virar problema, fallback para shared "Pace Ops" agent e mudanca de ~30 LOC em epic follow-up.
- **A15**: Template Meta Cloud fora da janela 24h e **fora do escopo** — adapter retorna erro; UI mostra alerta. Engenharia de templates aprovados e epic separado.

---

**Proximos passos pos-aprovacao deste spec**:

1. `/speckit.clarify 010` — reduzir ambiguidades restantes (historico de tenants com `handoff.mode` fora de `off|shadow|on`, semantica de `handoff.rules`, retencao de `handoff_events`).
2. `/speckit.plan 010` — design artifacts: migrations exatas, Pydantic schemas, adapter signatures, contract tests.
3. `/speckit.tasks 010` — T001+ lista ordenada por dependencia.
4. ADR-036 (`ai_active` unified bit), ADR-037 (HelpdeskAdapter pattern), ADR-038 (fromMe auto-detection semantics).
