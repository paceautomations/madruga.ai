# Feature Specification: Channel Pipeline

**Feature Branch**: `epic/prosauai/001-channel-pipeline`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: Infraestrutura base para receber mensagens WhatsApp via Evolution API, classificar por tipo, aplicar debounce, e responder echo — fundação para todos os épicos subsequentes.

## User Scenarios & Testing

### User Story 1 - Receber e Responder Mensagem Individual (Priority: P1)

Um usuario envia uma mensagem de texto pelo WhatsApp para o numero do bot. O sistema recebe a mensagem via webhook da Evolution API, valida a assinatura HMAC-SHA256, classifica como mensagem individual de suporte, e responde com echo do texto recebido.

**Why this priority**: Esta é a funcionalidade mais basica e essencial — sem ela, nenhuma outra interacao e possivel. Valida toda a cadeia: webhook → parser → router → resposta.

**Independent Test**: Enviar uma mensagem de texto pelo WhatsApp e verificar que o bot responde com o mesmo texto. Pode ser testado isoladamente com um payload real da Evolution API.

**Acceptance Scenarios**:

1. **Given** o webhook esta ativo e configurado, **When** um usuario envia "Ola, tudo bem?" pelo WhatsApp, **Then** o sistema responde com "Ola, tudo bem?" via Evolution API e retorna HTTP 200 com status "queued".
2. **Given** o webhook esta ativo, **When** um usuario envia uma mensagem com midia (imagem com legenda), **Then** o sistema extrai o texto da legenda e responde echo do texto.
3. **Given** o webhook esta ativo, **When** o proprio bot envia uma mensagem (from_me=true), **Then** o sistema ignora a mensagem e retorna HTTP 200 com status "ignored" e route "ignore".

---

### User Story 2 - Validacao de Seguranca no Webhook (Priority: P1)

O sistema valida a assinatura HMAC-SHA256 em toda requisicao recebida no webhook. Requests sem assinatura valida sao rejeitadas imediatamente.

**Why this priority**: Seguranca e requisito desde dia 1 (ADR-017). Sem validacao, qualquer ator malicioso pode injetar mensagens falsas no sistema.

**Independent Test**: Enviar requests com assinaturas validas e invalidas ao endpoint e verificar aceitacao/rejeicao.

**Acceptance Scenarios**:

1. **Given** o webhook esta ativo com secret configurado, **When** uma request chega com header `x-webhook-signature` contendo HMAC-SHA256 valido, **Then** o sistema processa normalmente e retorna HTTP 200.
2. **Given** o webhook esta ativo, **When** uma request chega sem header `x-webhook-signature`, **Then** o sistema retorna HTTP 401 Unauthorized.
3. **Given** o webhook esta ativo, **When** uma request chega com assinatura invalida, **Then** o sistema retorna HTTP 401 Unauthorized sem processar o payload.

---

### User Story 3 - Classificacao Inteligente de Mensagens de Grupo (Priority: P1)

Quando o bot esta em um grupo WhatsApp, o sistema classifica mensagens em tres categorias: grupo com @mention do bot (responde), grupo sem @mention (apenas registra), e evento de grupo (join/leave — ignora). Isso evita respostas indesejadas e custos desnecessarios com LLM em epicos futuros.

**Why this priority**: O Smart Router e fundacao para todos os fluxos. Classificacao errada gera respostas indesejadas em grupos (spam) ou silencio quando o usuario espera resposta.

**Independent Test**: Enviar mensagens de grupo com e sem @mention e verificar que apenas as com @mention geram resposta.

**Acceptance Scenarios**:

1. **Given** o bot esta em um grupo WhatsApp, **When** um membro envia "@prosauai qual o status?", **Then** o sistema classifica como GROUP_RESPOND e responde com echo do texto.
2. **Given** o bot esta em um grupo, **When** um membro envia "bom dia pessoal" sem mencionar o bot, **Then** o sistema classifica como GROUP_SAVE_ONLY, registra em log estruturado, e nao envia resposta.
3. **Given** o bot esta em um grupo, **When** um membro entra ou sai do grupo, **Then** o sistema classifica como GROUP_EVENT e ignora.
4. **Given** o bot esta em um grupo, **When** um membro menciona o phone JID do bot na mensagem, **Then** o sistema classifica como GROUP_RESPOND (deteccao por phone JID alem de keywords).

---

### User Story 4 - Debounce de Mensagens Rapidas (Priority: P2)

Quando um usuario envia varias mensagens em sequencia rapida (ex: "oi" + "tudo bem?" + "preciso de ajuda"), o sistema agrupa essas mensagens em uma unica antes de processar, evitando multiplas respostas fragmentadas.

**Why this priority**: Melhora significativa na experiencia do usuario. Sem debounce, o bot responderia 3 vezes para alguem que digita rapido, gerando confusao.

**Independent Test**: Enviar 3 mensagens em menos de 3 segundos e verificar que o sistema processa como uma unica mensagem concatenada.

**Acceptance Scenarios**:

1. **Given** o debounce esta configurado com janela de 3 segundos, **When** um usuario envia 3 mensagens em 2 segundos, **Then** o sistema agrupa as 3 mensagens e processa como uma unica.
2. **Given** o debounce esta ativo, **When** um usuario envia uma mensagem e depois outra apos 5 segundos, **Then** o sistema processa cada mensagem separadamente.
3. **Given** multiplos usuarios enviam mensagens simultaneamente, **When** o debounce processa, **Then** cada buffer e independente por usuario (mensagens de usuarios diferentes nunca sao misturadas).

---

### User Story 5 - Health Check e Operacao via Docker (Priority: P2)

O operador do sistema pode verificar a saude da aplicacao via endpoint dedicado e subir todo o ambiente com um unico comando Docker Compose.

**Why this priority**: Essencial para operacao e deploy, mas nao afeta o fluxo de mensagens do usuario final.

**Independent Test**: Executar `docker compose up` e verificar que `GET /health` retorna 200 OK.

**Acceptance Scenarios**:

1. **Given** a aplicacao esta rodando, **When** um request GET e enviado para `/health`, **Then** o sistema retorna HTTP 200 com body `{"status": "ok"}`.
2. **Given** o docker-compose.yml esta configurado, **When** o operador executa `docker compose up`, **Then** os servicos api e redis sobem sem erros e a aplicacao responde em `/health`.
3. **Given** o Redis esta indisponivel, **When** um request GET e enviado para `/health`, **Then** o sistema indica degradacao no status.

---

### User Story 6 - Handoff Ativo (Stub) (Priority: P3)

O sistema reconhece mensagens que deveriam ser tratadas como handoff ativo (transferencia para atendente humano), mas nesta fase apenas registra e ignora — o handler real sera implementado no epico 005.

**Why this priority**: Nao entrega valor direto nesta fase, mas a presenca do enum e do stub evita breaking changes futuros.

**Independent Test**: Verificar que o router classifica corretamente como HANDOFF_ATIVO e retorna IGNORE com reason explicativa.

**Acceptance Scenarios**:

1. **Given** uma mensagem e classificada como handoff ativo, **When** o router processa, **Then** retorna route IGNORE com reason "handoff not implemented".

---

### Edge Cases

- **Payload invalido ou malformado**: O sistema retorna HTTP 400 com mensagem de erro descritiva sem crashar.
- **Tipo de mensagem desconhecido da Evolution API**: O sistema classifica como IGNORE e registra em log para analise futura.
- **Mensagem sem texto (ex: sticker, location, contact)**: O sistema extrai informacao relevante do tipo de midia ou classifica como IGNORE se nao houver texto processavel.
- **Redis indisponivel durante debounce**: O sistema processa a mensagem sem debounce (fallback sincrono) e registra warning no log.
- **Mensagem duplicada (mesmo message_id)**: O sistema processa normalmente nesta fase (idempotencia via DB no epico 002).
- **Unicode e emojis no texto**: O sistema preserva caracteres especiais sem corromper.
- **Mensagens muito longas (>4096 caracteres)**: O sistema processa sem truncar nesta fase (limite sera avaliado no epico 002 com LLM).
- **Multiplos @mentions na mesma mensagem**: O sistema detecta corretamente se o bot foi mencionado entre multiplas mencoes.
- **Falha no envio via Evolution API**: O sistema registra erro em log estruturado (phone_hash, message_id, error_detail) e descarta — sem retry nesta fase.

## Clarifications

### Session 2026-04-09

- Q: Quando o debounce agrupa multiplas mensagens, qual o formato de concatenacao? → A: Newline-separated (`\n`) — preserva limites de cada mensagem para LLM em epic 002.
- Q: Qual o comportamento quando o envio via Evolution API falha (send_text/send_media retorna erro)? → A: Log error (structlog) e drop — sem retry nesta fase. Retry vem com ARQ worker no epic 002.
- Q: A chave do buffer de debounce e por usuario global ou por (usuario, contexto de conversa)? → A: Por (phone, group_id|"direct") — buffers independentes por conversa. Usuario em 2 grupos tem 2 buffers separados.
- Q: A validacao HMAC-SHA256 usa o body raw (bytes) ou o JSON parseado? → A: Raw request body bytes — pratica padrao para webhook signatures, evita inconsistencias de serializacao.
- Q: As keywords de @mention (ex: "@prosauai", "@resenhai") sao configuráveis via env var ou hardcoded? → A: Configuravel via env var `MENTION_KEYWORDS` (comma-separated). Alinhado com FR-014 (sem hardcode).

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE receber webhooks da Evolution API no endpoint POST `/webhook/whatsapp/{instance_name}` e retornar HTTP 200 com payload JSON contendo status, route e message_id.
- **FR-002**: O sistema DEVE validar a assinatura HMAC-SHA256 de toda requisicao webhook usando o header `x-webhook-signature` e rejeitar com HTTP 401 requests sem assinatura valida. A validacao DEVE ser computada sobre o raw request body (bytes), nao sobre JSON re-serializado.
- **FR-003**: O sistema DEVE parsear payloads da Evolution API e extrair campos estruturados: phone, text, sender_name, message_id, is_group, group_id, from_me, mentioned_phones, media_type, media_url, timestamp, instance, is_group_event.
- **FR-004**: O sistema DEVE classificar cada mensagem em uma das 6 rotas: SUPPORT (individual normal), GROUP_RESPOND (grupo com @mention), GROUP_SAVE_ONLY (grupo sem @mention), GROUP_EVENT (join/leave), HANDOFF_ATIVO (stub → IGNORE), IGNORE (from_me ou invalido).
- **FR-005**: O sistema DEVE verificar `from_me` como primeiro check no router, retornando IGNORE imediatamente para mensagens enviadas pelo proprio bot.
- **FR-006**: O sistema DEVE detectar @mention do bot via regex case-insensitive comparando phone JID e keywords configuradas via env var `MENTION_KEYWORDS` (comma-separated, ex: "@resenhai,@prosauai") ANTES de qualquer processamento adicional.
- **FR-007**: O sistema DEVE agrupar mensagens rapidas do mesmo usuario usando debounce com janela configuravel (default 3 segundos) e jitter aleatorio de 0-1 segundo para evitar avalanche de flushes simultaneos. A chave do buffer e composta por `(phone, group_id|"direct")`, garantindo buffers independentes por conversa. Mensagens agrupadas sao concatenadas com newline (`\n`) preservando limites de cada mensagem.
- **FR-008**: O debounce DEVE usar operacao atomica no Redis (Lua script) para garantir consistencia, e keyspace notifications para trigger de flush apos expiracao do buffer.
- **FR-009**: O sistema DEVE responder com echo do texto recebido para mensagens classificadas como SUPPORT ou GROUP_RESPOND, enviando via Evolution API. Em caso de falha no envio (erro da Evolution API), o sistema DEVE registrar o erro em log estruturado e descartar — sem retry nesta fase (retry via ARQ worker no epic 002).
- **FR-010**: O sistema DEVE registrar em log estruturado (com phone_hash, group_id, route, timestamp) toda mensagem classificada como GROUP_SAVE_ONLY, sem enviar resposta.
- **FR-011**: O sistema DEVE expor endpoint GET `/health` retornando HTTP 200 com body `{"status": "ok"}`.
- **FR-012**: O sistema DEVE suportar envio de texto e midia (imagem, documento, video, audio) via adapter da Evolution API.
- **FR-013**: O sistema DEVE retornar `RouteResult` com campo `agent_id` (None nesta fase — usa tenant default) para compatibilidade futura com routing rules do epico 003.
- **FR-014**: O sistema DEVE ter configuracao externalizada via variaveis de ambiente, sem valores hardcoded no codigo.
- **FR-015**: O sistema DEVE funcionar via Docker Compose com servicos api e redis, subindo sem erros com um unico comando.

### Key Entities

- **ParsedMessage**: Representacao estruturada de uma mensagem recebida da Evolution API. Contem identificacao do remetente (phone, sender_name), conteudo (text, media_type, media_url), contexto (is_group, group_id, mentioned_phones), e metadados (message_id, timestamp, instance, from_me, is_group_event).
- **MessageRoute**: Classificacao da mensagem em uma das 6 categorias que determina o fluxo de processamento: SUPPORT, GROUP_RESPOND, GROUP_SAVE_ONLY, GROUP_EVENT, HANDOFF_ATIVO, IGNORE.
- **RouteResult**: Resultado da classificacao contendo a rota determinada, o agent_id associado (None nesta fase), e uma razao opcional para a classificacao.
- **Buffer de Debounce**: Agrupamento temporario de mensagens do mesmo usuario dentro da janela de tempo. Chave composta por `(phone, group_id|"direct")` — buffers independentes por conversa. Mensagens concatenadas com `\n`. Armazenado no Redis com TTL = debounce_seconds + jitter.

## Success Criteria

### Measurable Outcomes

- **SC-001**: O sistema processa uma mensagem individual do recebimento (webhook) ate a resposta echo em menos de 2 segundos (excluindo latencia de rede da Evolution API).
- **SC-002**: Requests sem assinatura HMAC-SHA256 valida sao rejeitadas em 100% dos casos, sem excepcao.
- **SC-003**: Mensagens de grupo sem @mention do bot geram zero respostas — apenas log estruturado.
- **SC-004**: O debounce agrupa corretamente 95%+ das mensagens rapidas enviadas dentro da janela configurada (3s).
- **SC-005**: O endpoint `/health` responde em menos de 200 milissegundos.
- **SC-006**: O suite de testes contem no minimo 14 testes (8 unitarios + 6 integracao) e todos passam com sucesso.
- **SC-007**: O linter (ruff) reporta zero erros no codigo-fonte.
- **SC-008**: Docker Compose sobe api + redis sem erros e a aplicacao responde no `/health` em ate 30 segundos apos `docker compose up`.
- **SC-009**: O Smart Router classifica corretamente 100% dos 6 tipos de mensagem definidos, verificavel via testes com payloads reais da Evolution API.

## Assumptions

- A Evolution API esta disponivel e configurada em um ambiente de staging externo; nao sera incluida no Docker Compose local (mock em testes).
- Os payloads reais da Evolution API serao capturados manualmente pelo usuario e disponibilizados como fixtures de teste em `tests/fixtures/evolution_payloads.json`.
- O repositorio `paceautomations/prosauai` sera criado do zero (greenfield) como primeira task do epic.
- Nesta fase, nao ha necessidade de persistencia em banco de dados — log estruturado via structlog e suficiente. Supabase sera introduzido no epico 002.
- O processamento de mensagens sera sincrono no webhook handler (sem ARQ worker). Worker assincrono sera introduzido no epico 002.
- A configuracao de secrets sera via `.env` + pydantic Settings. Integracao com Infisical sera em epic posterior.
- O campo `agent_id` no `RouteResult` sera sempre None nesta fase. O roteamento por agent sera implementado no epico 003.
- O handler de HANDOFF_ATIVO sera um stub que retorna IGNORE. Implementacao real no epico 005.
- Usuarios tem conexao estavel com a internet e o WhatsApp funciona normalmente.
- A Evolution API mantem compatibilidade com a versao fixada durante o desenvolvimento deste epic.

---
handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada com 5 pontos resolvidos: formato concatenacao debounce (newline), falha envio Evolution (log+drop), chave buffer (phone+group_id|direct), HMAC sobre raw bytes, mention_keywords configuravel via env var. Pronto para plan."
  blockers: []
  confidence: Alta
  kill_criteria: "Evolution API muda formato de payload de forma incompativel com o adapter pattern, ou Redis se mostra inadequado para debounce atomico."
