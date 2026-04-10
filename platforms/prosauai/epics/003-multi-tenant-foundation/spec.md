# Feature Specification: Multi-Tenant Foundation — Auth + Parser Reality + Deploy

**Feature Branch**: `epic/prosauai/003-multi-tenant-foundation`  
**Created**: 2026-04-10  
**Status**: Draft  
**Input**: Fundação multi-tenant estrutural para ProsaUAI — corrigir 3 bloqueios críticos que impedem operação em produção: HMAC imaginário (100% rejeição), parser divergente (50% silenciamento), arquitetura single-tenant incompatível com end-state.

## User Scenarios & Testing

### User Story 1 — Webhook recebe e autentica mensagens reais da Evolution (Priority: P1)

Um operador configura a instância Evolution para enviar webhooks ao ProsaUAI apontando para `http://<host>:8050/webhook/whatsapp/<instance_name>`. Quando uma mensagem real chega, o sistema resolve o tenant pelo `instance_name` no path, valida o header `X-Webhook-Secret` contra o secret configurado para aquele tenant, e aceita o webhook para processamento. Hoje, 100% dos webhooks reais são rejeitados porque o código valida HMAC-SHA256 que a Evolution nunca implementou.

**Why this priority**: Sem autenticação funcional, o serviço inteiro é inutilizável com a Evolution real. É o bloqueio #1 — nenhuma outra funcionalidade importa se webhooks são rejeitados na porta de entrada.

**Independent Test**: Enviar um POST com header `X-Webhook-Secret` correto para `/webhook/whatsapp/Ariel` e verificar que retorna 200. Enviar com secret errado e verificar 401. Enviar com instance_name desconhecido e verificar 404.

**Acceptance Scenarios**:

1. **Given** um tenant "Ariel" configurado com `webhook_secret=abc123`, **When** um POST chega em `/webhook/whatsapp/Ariel` com header `X-Webhook-Secret: abc123`, **Then** o sistema retorna HTTP 200 e processa a mensagem.
2. **Given** um tenant "Ariel" configurado, **When** um POST chega sem header `X-Webhook-Secret` ou com valor incorreto, **Then** o sistema retorna HTTP 401 sem processar.
3. **Given** nenhum tenant com instance_name "Desconhecido", **When** um POST chega em `/webhook/whatsapp/Desconhecido`, **Then** o sistema retorna HTTP 404.
4. **Given** o tenant "Ariel" com `enabled: false`, **When** um POST chega em `/webhook/whatsapp/Ariel`, **Then** o sistema retorna HTTP 404 (tenant inativo tratado como inexistente).

---

### User Story 2 — Parser reconhece todos os tipos de mensagem reais da Evolution v2.3.0 (Priority: P1)

Quando um webhook é aceito, o parser interpreta corretamente o payload da Evolution v2.3.0. Isso inclui: 13 tipos de mensagem com nomes reais (`imageMessage`, `videoMessage`, etc.), resolução de sender em 3 formatos (`@lid`, `@s.whatsapp.net`, grupo com `participant`), extração de mentions em `data.contextInfo`, tratamento de eventos `groups.upsert` (data como lista) e `group-participants.update` (data como dict sem key), e extração de replies e reactions. Hoje, 50% das mensagens caem em "unknown type" silenciosamente.

**Why this priority**: Empata com P1 do auth — mesmo que o webhook seja aceito, metade das mensagens são silenciadas pelo parser incorreto. Parser funcional é pré-requisito para qualquer lógica de roteamento ou resposta.

**Independent Test**: Rodar o parser contra 26 fixtures capturadas de payloads reais e verificar que todos os campos declarados nos expected files correspondem ao output.

**Acceptance Scenarios**:

1. **Given** um payload com `messageType: imageMessage`, **When** o parser processa, **Then** `media_type=image` é extraído corretamente (não "unknown type").
2. **Given** um payload com `remoteJid` no formato `<15-digit>@lid` e `key.senderPn` preenchido, **When** o parser processa, **Then** `sender_phone` vem de `key.senderPn` e `sender_lid_opaque` vem do `remoteJid`.
3. **Given** um payload de `groups.upsert` onde `data` é uma lista, **When** o parser processa, **Then** o evento é reconhecido como `groups.upsert` com `group_id`, `group_subject` e `group_participants_count` extraídos.
4. **Given** um payload de `group-participants.update` sem campo `key`, **When** o parser processa, **Then** `group_event_action`, `group_event_participants` e `group_event_author_lid` são extraídos, e um `message_id` é sintetizado.
5. **Given** um payload com `data.contextInfo.mentionedJid` preenchido, **When** o parser processa, **Then** `mentioned_jids` contém os JIDs listados.
6. **Given** um payload com `data.contextInfo.quotedMessage`, **When** o parser processa, **Then** `is_reply=True` e `quoted_message_id` é extraído.
7. **Given** um payload do tipo `reactionMessage`, **When** o parser processa, **Then** `reaction_emoji` e `reaction_target_id` são extraídos, e a rota é `IGNORE` com `reason=reaction`.
8. **Given** um payload com `fromMe: true`, **When** o parser processa, **Then** a rota é `IGNORE` com `reason=from_me`.
9. **Given** 26 fixtures capturadas de payloads reais, **When** o test suite parametrizado roda, **Then** 100% passam com campos declarados correspondendo ao output.

---

### User Story 3 — Isolamento multi-tenant para 2 tenants simultâneos (Priority: P1)

O sistema suporta 2 tenants (Ariel e ResenhAI) operando simultaneamente com isolamento completo. Cada tenant tem suas próprias credenciais Evolution, seu webhook secret, e suas configurações de mention. Mensagens para o tenant Ariel nunca são visíveis ou processadas pelo ResenhAI e vice-versa. Chaves de debounce e idempotência são prefixadas por tenant, eliminando colisões cross-tenant.

**Why this priority**: Multi-tenancy é o fundamento arquitetural que desbloqueia todos os epics futuros. Validar com 2 tenants reais desde o dia 1 garante que o isolamento funciona empiricamente, não apenas em teoria.

**Independent Test**: Configurar 2 tenants, enviar webhooks para ambos, verificar que cada um processa apenas suas mensagens, e que chaves Redis são corretamente prefixadas.

**Acceptance Scenarios**:

1. **Given** 2 tenants configurados (Ariel e ResenhAI), **When** uma mensagem chega para `/webhook/whatsapp/Ariel`, **Then** apenas o tenant Ariel processa a mensagem.
2. **Given** 2 tenants com `mention_phone` idêntico (cenário sintético de teste), **When** ambos recebem mensagens, **Then** as chaves Redis de debounce são distintas (`buf:pace-internal:...` vs `buf:resenha-internal:...`).
3. **Given** o mesmo `message_id` enviado para 2 tenants diferentes, **When** ambos processam, **Then** ambos aceitam (idempotência é per-tenant, não global).
4. **Given** o flush callback do debounce dispara, **When** o sistema resolve o tenant pela chave, **Then** usa as credenciais Evolution específicas daquele tenant para enviar o echo.

---

### User Story 4 — Idempotência neutraliza retries da Evolution (Priority: P2)

A Evolution API reenvia webhooks com retries agressivos (até 10 tentativas com backoff exponencial). O sistema detecta mensagens duplicadas e responde `200 OK {status: "duplicate"}` sem reprocessar. Isso evita efeitos colaterais duplicados (echo duplicado, futuras persistências em DB, chamadas a LLM).

**Why this priority**: Sem idempotência, cada retry da Evolution gera efeitos colaterais duplicados. Não é um bloqueio total como auth/parser (o serviço funciona, apenas duplica), mas é essencial para operação confiável.

**Independent Test**: Enviar o mesmo payload com mesmo `message_id` duas vezes e verificar que o segundo retorna `duplicate`.

**Acceptance Scenarios**:

1. **Given** uma mensagem com `message_id=ABC` para tenant `pace-internal`, **When** chega pela primeira vez, **Then** é processada normalmente.
2. **Given** a mesma mensagem `message_id=ABC` para tenant `pace-internal`, **When** chega pela segunda vez (retry), **Then** retorna `200 OK {status: "duplicate"}` sem processar.
3. **Given** TTL de 24h configurado, **When** uma mensagem chega 25h depois de ser marcada, **Then** é processada novamente (TTL expirou).
4. **Given** `message_id=ABC` para tenant `pace-internal` já processada, **When** `message_id=ABC` chega para tenant `resenha-internal`, **Then** é processada normalmente (idempotência é per-tenant).

---

### User Story 5 — Deploy seguro sem portas expostas (Priority: P2)

O serviço roda na porta 8050 sem expor nenhuma porta publicamente. No ambiente dev, o acesso é via Tailscale VPN. Na produção Fase 1, o serviço comunica com a Evolution via Docker network privada compartilhada. Nenhuma porta é acessível pela internet.

**Why this priority**: Segurança de rede é importante mas não é um bloqueio funcional imediato. O serviço pode ser testado localmente sem o deploy final. É P2 porque depende da infraestrutura estar funcional (P1s).

**Independent Test**: Executar `docker compose up` e verificar que nenhuma porta está bindada em `0.0.0.0`.

**Acceptance Scenarios**:

1. **Given** o `docker-compose.yml` base, **When** `docker compose up` executa, **Then** nenhuma porta está exposta em `0.0.0.0`.
2. **Given** o `docker-compose.override.yml` para dev, **When** aplicado, **Then** a porta 8050 é bindada apenas no IP Tailscale.
3. **Given** o ambiente de produção Fase 1, **When** o serviço e a Evolution estão na mesma Docker network, **Then** comunicam via DNS interno do Docker sem tráfego saindo do host.

---

### User Story 6 — Observabilidade multi-tenant nos spans e logs (Priority: P2)

Spans de OpenTelemetry e logs estruturados incluem `tenant_id` como atributo per-request, permitindo filtrar traces e logs por tenant no Phoenix. O `tenant_id` é removido do Resource (que é process-wide) e movido para atributos de span individuais. Dashboards Phoenix existentes continuam funcionando sem alteração.

**Why this priority**: Observabilidade é essencial para operar em produção com 2 tenants, mas depende do multi-tenant estar implementado primeiro. Dashboards já existem do epic 002 — só precisa trocar a fonte do valor.

**Independent Test**: Enviar webhooks para 2 tenants diferentes e verificar no Phoenix que cada span tem o `tenant_id` correto.

**Acceptance Scenarios**:

1. **Given** um webhook processado para tenant `pace-internal`, **When** o trace é exportado, **Then** todos os spans contêm `tenant_id=pace-internal` como atributo.
2. **Given** o Resource do OpenTelemetry, **When** inspecionado, **Then** NÃO contém `tenant_id` (é process-wide, multi-tenant incompatível).
3. **Given** logs estruturados do handler, **When** inspecionados, **Then** contêm `tenant_id` via `structlog.contextvars`.
4. **Given** dashboards Phoenix do epic 002, **When** consultados, **Then** continuam funcionando (chave `tenant_id` nos spans preservada, apenas a fonte mudou).

---

### User Story 7 — Onboarding de novo tenant documentado (Priority: P3)

Um administrador consegue adicionar um novo tenant seguindo a documentação: copiar template, editar YAML, gerar webhook secret, descobrir `mention_lid_opaque` via workflow documentado, configurar webhook na Evolution, e reiniciar o serviço.

**Why this priority**: Com apenas 2 tenants internos na Fase 1, o onboarding não é frequente. Mas documentar o processo agora evita perda de conhecimento e prepara para escala futura.

**Independent Test**: Seguir o README de onboarding e verificar que um novo tenant (sintético em teste) é reconhecido pelo sistema.

**Acceptance Scenarios**:

1. **Given** o README com instruções de onboarding, **When** um administrador segue os passos, **Then** um novo tenant é funcional em menos de 15 minutos.
2. **Given** um novo tenant configurado sem `mention_lid_opaque`, **When** o workflow de descoberta é seguido, **Then** o valor correto é obtido e o tenant responde a mentions em grupo.

---

### Edge Cases

- **Webhook com body vazio ou JSON inválido**: o sistema retorna 400 sem crash.
- **Tenant com `enabled: false`**: tratado como inexistente (404), sem leak de informação.
- **`message_id` ausente no payload**: o parser sintetiza um ID a partir de campos disponíveis ou rejeita com log de warning.
- **Redis indisponível durante check de idempotência**: o sistema processa a mensagem (fail-open) e loga warning — preferível processar duplicada a perder mensagem.
- **`tenants.yaml` com `${ENV_VAR}` não definida**: startup falha com erro claro indicando qual variável está faltando.
- **Payload com campos inesperados (Chatwoot metadata, deviceListMetadata, base64)**: ignorados silenciosamente sem erro.
- **Dois webhooks para o mesmo tenant chegam simultaneamente com mesmo `message_id`**: race condition resolvida pelo atomicidade do Redis SETNX — apenas o primeiro processa.
- **`groups.upsert` com lista vazia em `data`**: parser trata como no-op, loga warning.
- **Mention detection falha em todas as 3 strategies**: mensagem roteada como `group_save` (não é mention), sem erro.
- **Tenants com `id` ou `instance_name` duplicados no YAML**: startup falha com erro claro listando os conflitos — nunca override silencioso.
- **`tenants.yaml` editado em runtime**: mudanças não têm efeito até restart do serviço (hot reload não suportado na Fase 1).

## Requirements

### Functional Requirements

**Tenant Management:**

- **FR-001**: O sistema DEVE carregar configuração de tenants de um arquivo YAML no startup, com interpolação de variáveis de ambiente (`${ENV_VAR}`) para secrets.
- **FR-002**: O sistema DEVE indexar tenants por `id` e por `instance_name` para lookup O(1).
- **FR-003**: O sistema DEVE rejeitar startup se o arquivo de tenants não existir ou tiver YAML inválido.
- **FR-004**: O sistema DEVE rejeitar startup se qualquer `${ENV_VAR}` referenciada não estiver definida no ambiente.
- **FR-004b**: O sistema DEVE rejeitar startup se houver tenants com `id` ou `instance_name` duplicados, indicando claramente quais entradas conflitam.
- **FR-004c**: O TenantStore NÃO suporta hot reload — mudanças em `tenants.yaml` exigem restart do serviço. YAML é carregado apenas uma vez no startup via lifespan.
- **FR-005**: Cada tenant DEVE ter: `id`, `instance_name`, `evolution_api_url`, `evolution_api_key`, `webhook_secret`, `mention_phone`, `mention_lid_opaque`, `mention_keywords`, `enabled`.

**Autenticação:**

- **FR-006**: O sistema DEVE resolver o tenant pelo `instance_name` no path do webhook (`/webhook/whatsapp/<instance_name>`).
- **FR-007**: O sistema DEVE retornar HTTP 404 se o `instance_name` não corresponder a nenhum tenant ativo.
- **FR-008**: O sistema DEVE validar o header `X-Webhook-Secret` contra o `webhook_secret` do tenant usando comparação constant-time.
- **FR-009**: O sistema DEVE retornar HTTP 401 se o header estiver ausente ou inválido.
- **FR-010**: O sistema NÃO DEVE implementar HMAC-SHA256 ou qualquer outro mecanismo de autenticação além de `X-Webhook-Secret`.

**Idempotência:**

- **FR-011**: O sistema DEVE verificar duplicidade por `(tenant_id, message_id)` antes de processar qualquer mensagem.
- **FR-012**: A verificação DEVE ser atômica via Redis `SET NX EX` com TTL de 24h.
- **FR-013**: Mensagens duplicadas DEVEM retornar `200 OK {"status": "duplicate"}` sem processamento.
- **FR-013b**: Mensagens processadas com sucesso DEVEM retornar `200 OK {"status": "processed"}` — formato consistente com a resposta de duplicate.
- **FR-014**: Se Redis estiver indisponível, o sistema DEVE processar a mensagem (fail-open) e logar warning.

**Parser Evolution v2.3.0:**

- **FR-015**: O parser DEVE reconhecer os 13 tipos de mensagem reais: `imageMessage`, `videoMessage`, `audioMessage`, `documentMessage`, `stickerMessage`, `locationMessage`, `liveLocationMessage`, `contactMessage`, `reactionMessage`, `pollCreationMessageV3`, `eventMessage`, `extendedTextMessage`, `conversation`.
- **FR-016**: O parser DEVE resolver sender em 3 formatos: (a) `@lid` + `senderPn` → usa `senderPn` como phone; (b) `@s.whatsapp.net` + `senderLid` → usa `remoteJid`; (c) grupo `@g.us` → usa `key.participant`.
- **FR-017**: O parser DEVE extrair `mentionedJid` de `data.contextInfo` (top-level).
- **FR-018**: O parser DEVE tratar `groups.upsert` com `data` como lista (extrair group_id, subject, participants_count).
- **FR-019**: O parser DEVE tratar `group-participants.update` com `data` como dict sem `key` (extrair action, author, participants; sintetizar message_id com fórmula `{instance_name}-{event}-{timestamp_epoch_ms}`).
- **FR-020**: O parser DEVE extrair `quotedMessage` de `data.contextInfo.quotedMessage` → `is_reply` + `quoted_message_id`.
- **FR-021**: O parser DEVE extrair `reaction_emoji` e `reaction_target_id` de `reactionMessage` e rotear como `IGNORE` com `reason=reaction`.
- **FR-022**: O parser DEVE ignorar silenciosamente campos irrelevantes: `messageContextInfo`, `chatwoot*`, `deviceListMetadata`, `data.message.base64`.
- **FR-023**: O parser DEVE popular um schema expandido com 22 campos incluindo compound sender identity, campos de evento de grupo, mentions, reply e reaction.

**Roteamento:**

- **FR-024**: O router DEVE aceitar `(ParsedMessage, Tenant)` como interface — sem referência a Settings globais.
- **FR-025**: O router DEVE implementar 3 strategies de mention detection em ordem: (1) `mention_lid_opaque` em `mentioned_jids`, (2) `mention_phone` em `mentioned_jids`, (3) keywords substring no texto.
- **FR-026**: O router NÃO DEVE alterar o enum `MessageRoute` nem a lógica if/elif interna — refactor completo é escopo do epic 004.

**Debounce:**

- **FR-027**: Chaves de debounce DEVEM ser prefixadas por tenant: `buf:{tenant_id}:{sender_key}:{ctx}` e `tmr:{tenant_id}:{sender_key}:{ctx}`.
- **FR-028**: `sender_key` DEVE ser `sender_lid_opaque or sender_phone` (identity estável).
- **FR-029**: O flush callback DEVE resolver o tenant pela chave (parse_expired_key) e usar credenciais Evolution específicas do tenant.

**Deploy:**

- **FR-030**: O `docker-compose.yml` base NÃO DEVE expor portas publicamente (nenhuma seção `ports:`).
- **FR-031**: O serviço DEVE usar a porta 8050 (não 8040 que conflita com madruga-ai daemon).
- **FR-032**: O volume `./config/tenants.yaml` DEVE ser montado read-only no container.

**Observabilidade:**

- **FR-033**: `tenant_id` DEVE ser removido do Resource do OpenTelemetry (process-wide, incompatível com multi-tenant).
- **FR-034**: `tenant_id` DEVE ser adicionado como atributo de span individual em cada request, populado via dependency de autenticação.
- **FR-035**: O contrato `SpanAttributes.TENANT_ID = "tenant_id"` DEVE ser preservado (compatibilidade com dashboards Phoenix do epic 002).
- **FR-036**: `structlog.contextvars.bind_contextvars(tenant_id=tenant.id)` DEVE ser chamado no início do handler para propagar em logs.

**Testes:**

- **FR-037**: O test suite DEVE incluir testes parametrizados contra 26 fixtures capturadas de payloads reais.
- **FR-038**: Cada fixture DEVE ter um par `*.input.json` + `*.expected.yaml`.
- **FR-039**: A fixture sintética anterior (`evolution_payloads.json`) DEVE ser deletada após os novos testes passarem.
- **FR-040**: Testes DEVEM validar isolamento cross-tenant (mensagem para tenant A não afeta tenant B).

### Key Entities

- **Tenant**: Configuração imutável por inquilino — id, instance_name, credenciais Evolution, webhook secret, configuração de mention (phone, lid_opaque, keywords), flag enabled. Carregado do YAML no startup, imutável durante runtime.
- **TenantStore**: Coleção indexada de Tenants com lookup por `id` e `instance_name`. File-backed (YAML) na Fase 1, migrável para banco de dados na Fase 3.
- **ParsedMessage**: Representação normalizada de um evento da Evolution — compound sender identity (phone + lid_opaque), metadados de evento, conteúdo, mentions, reply, reaction, dados de evento de grupo. Schema único para 3 tipos de evento discriminados por `event: EventType`.
- **Idempotency Key**: Par `(tenant_id, message_id)` armazenado em Redis como `seen:{tenant_id}:{message_id}` com TTL 24h. Garante processamento único por mensagem por tenant.
- **Debounce Keys**: Par de chaves Redis `buf:/tmr:{tenant_id}:{sender_key}:{ctx}` que agrupam mensagens consecutivas do mesmo sender para envio consolidado.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% dos webhooks reais da Evolution v2.3.0 são aceitos pelo sistema (hoje: 0% aceitos).
- **SC-002**: 100% das 26 fixtures capturadas de payloads reais passam no test suite parametrizado.
- **SC-003**: 100% dos tipos de mensagem reais (13 tipos) são reconhecidos corretamente pelo parser (hoje: 50% caem em "unknown type").
- **SC-004**: 2 tenants (Ariel e ResenhAI) operam em paralelo com isolamento completo validado por testes automatizados.
- **SC-005**: Zero mensagens duplicadas processadas quando a Evolution reenvia webhooks (até 10 retries).
- **SC-006**: Zero portas expostas publicamente na configuração base de deploy.
- **SC-007**: Tempo de onboarding de novo tenant inferior a 15 minutos seguindo a documentação.
- **SC-008**: Zero referências a `Settings` (singleton) no módulo de roteamento (`router.py`).
- **SC-009**: Diff do router (T7) não excede 30 linhas (excluindo `_is_bot_mentioned`) — interface mínima para compatibilidade com epic 004.
- **SC-010**: Todos os spans de OpenTelemetry contêm `tenant_id` correto per-request; dashboards Phoenix existentes continuam funcionais sem alteração.
- **SC-011**: Latência p99 de aceitação do webhook (auth + idempotency + parse) inferior a 100ms — antes do debounce assíncrono.

## Assumptions

- A Evolution API v2.3.0 é a versão em produção e os 26 payloads capturados representam fielmente os formatos reais de webhook. Se a Evolution mudar o formato em versões futuras, o parser precisará de atualizações.
- O epic 002 (observability) já foi mergeado no branch `develop` do repositório prosauai antes do início deste epic. Se não, o escopo de observabilidade explode (implementar do zero vs ajustar 4-5 arquivos). [VALIDAR]
- Redis 7 está disponível e operacional no ambiente de deploy. O sistema depende de Redis para idempotência e debounce.
- Apenas 2 tenants internos (Ariel e ResenhAI) operam na Fase 1. O design suporta N tenants, mas não há necessidade de otimizar para centenas nesta fase.
- O `mention_lid_opaque` (identificador opaco de 15 dígitos do formato @lid) precisa ser descoberto empiricamente para cada tenant — não é inferível do número de telefone. Workflow de descoberta documentado no README.
- A VPS Hostinger possui Tailscale configurado para acesso dev e Docker instalado para produção Fase 1.
- O enum `MessageRoute` e a lógica if/elif do router são intocados neste epic — o refactor completo é responsabilidade do epic 004-router-mece.
- `pyyaml` é adicionado como dependência do projeto (já aprovado pela constituição — stdlib + pyyaml).
- O formato de chave Redis `seen:{tenant_id}:{message_id}` e `buf:/tmr:{tenant_id}:{sender_key}:{ctx}` é definitivo para a Fase 1. Migração de esquema de chaves (se necessária) seria breaking change.

## Clarifications

### Session 2026-04-10

- Q: TenantStore reload strategy — hot reload ou restart required quando `tenants.yaml` muda? → A: Restart required. Fase 1 com 2 tenants internos, hot reload é otimização prematura. YAML carregado apenas no startup via lifespan. Documentar no README que mudanças em `tenants.yaml` exigem restart do serviço.
- Q: Fórmula de síntese de `message_id` para eventos `group-participants.update` que não têm `data.key`? → A: `{instance_name}-{event}-{timestamp_epoch_ms}` — determinístico, único dentro do TTL de 24h da idempotência. Exemplo: `Ariel-group-participants.update-1712764800000`.
- Q: Formato do body de resposta HTTP para webhook processado com sucesso? → A: `200 OK {"status": "processed"}` — espelha o formato de duplicate (`{"status": "duplicate"}`) para consistência. Evolution recebe confirmação clara de que o webhook foi aceito.
- Q: Validação de duplicidade de tenants no startup — o que acontece se dois tenants têm o mesmo `id` ou `instance_name`? → A: Startup DEVE falhar com erro claro indicando quais tenants têm `id` ou `instance_name` duplicado. Override silencioso causaria bugs de roteamento impossíveis de debugar.
- Q: Target de latência p99 para processamento de webhook? → A: p99 < 100ms para aceitação do webhook (auth + idempotency check + parse), antes do debounce assíncrono. Razoável considerando Redis SETNX (~1ms) + constant-time compare (~0ms) + parse in-memory.

---

handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada com 5 resoluções: TenantStore sem hot reload (restart required), fórmula de message_id para group events, response body padronizado, validação de duplicidade no startup, e target p99 <100ms. 43 requisitos funcionais (3 novos: FR-004b, FR-004c, FR-013b) + SC-011. Pronta para planning."
  blockers: []
  confidence: Alta
  kill_criteria: "Se a Evolution API v2.3.0 mudar o formato de webhook significativamente, ou se o epic 002 não for mergeado antes do início da implementação, o spec precisa de revisão."
