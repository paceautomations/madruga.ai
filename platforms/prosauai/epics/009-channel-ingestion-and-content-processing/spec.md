# Feature Specification: Channel Ingestion Normalization + Content Processing

**Feature Branch**: `epic/prosauai/009-channel-ingestion-and-content-processing`
**Created**: 2026-04-19
**Status**: Draft
**Input**: Epic pitch `009-channel-ingestion-and-content-processing/pitch.md` (scope reference: `research.md` preserves the full technical escope).

## Contexto do problema

Hoje, quando um cliente envia áudio, imagem, documento, sticker ou qualquer conteúdo não-textual pelo WhatsApp, o webhook responde `200 OK` mas o pipeline descarta a mensagem silenciosamente (filtro `if message.text:` em `api/webhooks.py`). Resultado: o cliente não recebe resposta, nenhum trace é registrado e o operador humano só descobre o problema quando o cliente reclama. Esta especificação cobre (a) normalização da camada de entrada para suportar múltiplos canais e tipos de conteúdo, (b) processamento real de mídia (transcrição de áudio, descrição de imagem, extração de PDF, etc.) e (c) validação arquitetural via um segundo canal (Meta Cloud API).

O escopo está dividido em 3 PRs mergeáveis isoladamente em `develop`, cada um reversível via feature flag por tenant — ver `pitch.md` para detalhes de cronograma e `research.md` para o material técnico completo.

## Clarifications

### Session 2026-04-19

- Q: Qual é a estratégia de geração das mensagens de fallback user-facing (budget estourado, feature desligada, circuit breaker aberto, mídia >25MB, PDF escaneado/encriptado, áudio alucinado)? → A: Marker estruturado + LLM com persona do tenant; hard-coded por tenant só se LLM indisponível.
- Q: Quais são os parâmetros numéricos do circuit breaker por tenant+provider e do retry? → A: 5 falhas consecutivas em janela de 60s abrem; 30s open; 1 tentativa half-open; re-open com backoff exponencial 30→60→120→300s. Retries 3 com base 500ms, jitter ±25%, limitado pelo budget de tempo do step.
- Q: Qual é o período de reload do arquivo de configuração de tenants (rollback de incidente)? → A: Poll periódico de 60 segundos por worker.
- Q: Como o sistema mapeia conteúdos que não se enquadram em nenhum dos 9 kinds previstos (ex.: vídeo, poll, pagamento WhatsApp Pay, notificação de chamada, edição de mensagem, mensagem de sistema)? → A: `kind="unsupported"` com `sub_type` tag; `text_representation` determinístico "[conteúdo não suportado: {sub_type} — por favor, envie texto]"; zero chamadas a provider externo.
- Q: Qual a metodologia de amostragem para SC-011 (alucinação ≤2%) e SC-012 (zero PII vazado)? → A: Amostra mensal aleatória estratificada por tenant ativo; revisão humana binária em rotação QA; 100 áudios (SC-011), 50 imagens (SC-012); tooling SQL via `pool_admin` + preview de mídia no portal admin.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cliente envia áudio e recebe resposta em contexto (Priority: P1)

Cliente do tenant **Ariel/ResenhAI** manda um áudio (PTT ou anexo) perguntando algo pelo WhatsApp. Hoje, o cliente fica no vácuo. Depois desta entrega, o sistema transcreve o áudio, trata a transcrição como a fala do cliente, gera uma resposta coerente e entrega via Evolution. O trace no portal mostra o step de processamento de conteúdo com o transcript visível.

**Why this priority**: é a correção do bug operacional mais visível e quantificável — mensagens de voz são a modalidade preferida de muitos clientes do varejo PT-BR, e cada áudio descartado hoje é um cliente silenciado. Sem esta história, o epic não entrega valor a ninguém. Todas as demais modalidades (imagem, documento) dependem da infraestrutura construída aqui.

**Independent Test**: enviar um áudio PTT (~10s) de um número real para um tenant com a feature ligada e verificar (a) que o cliente recebe uma resposta contextual à pergunta falada em menos de 8 segundos p95, (b) que o trace no Trace Explorer exibe o step `content_process` com o transcript completo, custo da API, latência e flag `cache_hit` e (c) que a resposta respeita o tom do agente (Ariel: informal; ResenhAI: profissional).

**Acceptance Scenarios**:

1. **Given** tenant `ariel-retail` com `content_processing.audio_enabled=true`, **When** cliente envia PTT de 10s perguntando "qual o horário de funcionamento?", **Then** o sistema transcreve o áudio, gera resposta textual com o horário correto e entrega em menos de 8s p95.
2. **Given** mesmo cliente envia áudio inaudível ou com apenas ruído (sem fala clara), **When** o modelo de transcrição retorna silêncio, alucinação ou duração <2s, **Then** o sistema devolve uma mensagem educada pedindo repetição (ex.: "não entendi, pode repetir?") em vez de responder ao texto alucinado.
3. **Given** tenant com `daily_budget_usd` já atingido no dia, **When** cliente envia áudio, **Then** o sistema não chama o provider de STT, registra fallback `budget_exceeded` e envia resposta informando que o atendimento automatizado retomará no dia seguinte ou será feito manualmente.
4. **Given** áudio > 25MB, **When** recebido, **Then** o download é rejeitado antes de consumir banda e o cliente recebe mensagem explicando limite de tamanho.
5. **Given** cliente envia áudio seguido imediatamente de texto complementar que entra no mesmo flush do debounce, **When** o pipeline processa, **Then** ambas as partes chegam ao modelo de geração como fala única concatenada (áudio transcrito + texto) e a resposta cobre as duas informações.

---

### User Story 2 — Cliente envia imagem e recebe resposta contextual (Priority: P1)

Cliente envia foto pelo WhatsApp, com ou sem legenda, perguntando sobre o produto ou problema mostrado. Hoje, a imagem é descartada. Depois desta entrega, o sistema gera uma descrição textual da imagem, combina com a legenda (se existir) e produz resposta coerente.

**Why this priority**: segunda modalidade mais comum no varejo (fotos de produto, comprovantes, cardápios, notas fiscais). Sem cobertura, o epic só resolve metade do problema.

**Independent Test**: enviar foto com legenda "qual o preço desse?" para um tenant com feature ligada. Verificar que a resposta referencia o item da imagem e que o trace exibe a descrição gerada no step `content_process`.

**Acceptance Scenarios**:

1. **Given** tenant com `content_processing.image_enabled=true` e `image.detail="low"`, **When** cliente envia foto de produto + legenda "tem esse?", **Then** o sistema gera descrição, combina com a legenda e responde com informação do item descrito (ex.: nome/preço/disponibilidade), em menos de 9s p95.
2. **Given** imagem sem legenda, **When** recebida, **Then** o sistema trata a descrição como input único e tenta uma resposta de engajamento ("vi que você mandou uma foto de X — posso ajudar com Y?").
3. **Given** tenant que exige leitura de texto em imagens (ex.: cardápio, nota), **When** configurado `image.detail="high"`, **Then** o sistema lê o texto da imagem e responde com base no conteúdo textual.
4. **Given** imagem com conteúdo sensível (ex.: CPF, cartão), **When** descrição é gerada, **Then** o texto descritivo passa pela camada de mascaramento PII existente antes de ser usado para compor a resposta ou exibido em logs.

---

### User Story 3 — Cliente envia documento (PDF, DOCX) e recebe resposta contextual (Priority: P2)

Cliente envia arquivo PDF de comprovante, contrato ou pedido. Hoje, o arquivo é descartado. Depois desta entrega, o sistema extrai texto, usa no contexto e responde.

**Why this priority**: menor volume que áudio/imagem, mas crítico em nichos (B2B, reembolsos). Aceita como P2 porque o caminho crítico é o mesmo de áudio/imagem — a integração de processors reaproveita a infraestrutura do P1.

**Independent Test**: enviar PDF de 3 páginas com comprovante de pagamento + caption "recebeu?". Verificar que a resposta confirma o recebimento referenciando valor/data extraídos.

**Acceptance Scenarios**:

1. **Given** tenant com `content_processing.document_enabled=true`, **When** cliente envia PDF de até 10 páginas com texto selecionável, **Then** o texto é extraído, tratado como input e a resposta referencia o conteúdo.
2. **Given** PDF escaneado (imagem sem OCR), **When** recebido, **Then** o sistema detecta ausência de texto extraível e devolve mensagem pedindo descrição manual.
3. **Given** PDF encriptado ou corrompido, **When** extração falha, **Then** o sistema registra o erro no trace e envia resposta informando falha na leitura.

---

### User Story 4 — Admin audita cada processamento de mídia no Trace Explorer (Priority: P1)

Engenheiro/operador abre o Trace Explorer (entregue no epic 008) e vê o step `content_process` como entrada própria no waterfall, com input (referência à mídia), output (transcrição/descrição), provider usado, custo em USD, latência e flag de cache hit.

**Why this priority**: sem observabilidade, qualquer regressão em qualidade, custo ou latência fica invisível até o cliente reclamar. É P1 porque o operador precisa responder em minutos quando "meu bot está caro" ou "meu bot está lento" — e este é o caminho crítico novo.

**Independent Test**: processar 5 áudios e 5 imagens de fixtures conhecidas, abrir cada trace no portal, confirmar que o step `content_process` aparece como 6º item do waterfall, que custo e latência são exibidos, e que o transcript/descrição completa (sem truncamento) está visível.

**Acceptance Scenarios**:

1. **Given** trace de uma conversa que incluiu áudio, **When** admin abre o trace no portal, **Then** o step `content_process` aparece no waterfall com transcript, provider, custo, latência e `cache_hit=false` no primeiro hit.
2. **Given** o mesmo áudio enviado duas vezes consecutivas (mesmo hash sha256), **When** processado, **Then** o segundo trace exibe `cache_hit=true`, custo zero, latência <50ms no step.
3. **Given** um tenant com volume alto (milhares de mídias no dia), **When** admin filtra "Performance AI" no portal, **Then** vê gráfico diário de custo por processor (áudio, imagem, documento) e por tenant.
4. **Given** uma rodada de processamento com falha parcial (ex.: Whisper 5xx), **When** trace é consultado, **Then** o step `content_process` mostra status de erro com a causa e a entrada continua gerando resposta via fallback.

---

### User Story 5 — Admin alterna feature flag e budget por tenant sem redeploy (Priority: P1)

Admin configura em `tenants.yaml` (ou UI futura) quais modalidades estão ligadas e o orçamento diário por tenant. Alterações entram em vigor no próximo poll do config, sem deploy.

**Why this priority**: rollout seguro e reversível. Cada tenant tem realidade comercial distinta — Ariel pode começar com só áudio, ResenhAI com tudo. Se provider tem incidente, admin desliga sem precisar de deploy. É P1 porque sem ele o rollout é all-or-nothing e o epic fica bloqueado em prod.

**Independent Test**: ligar `audio_enabled=false` em um tenant, enviar áudio, verificar que o sistema responde com fallback educado (sem chamada ao provider). Religar, verificar que volta a transcrever.

**Acceptance Scenarios**:

1. **Given** tenant com `content_processing.enabled=false`, **When** cliente envia qualquer mídia, **Then** o sistema registra o evento no trace mas não chama providers externos, e devolve mensagem genérica pedindo envio em texto.
2. **Given** tenant com `content_processing.enabled=true` mas `image_enabled=false`, **When** cliente envia imagem, **Then** só imagem cai no fallback; áudio e documento continuam funcionando.
3. **Given** `daily_budget_usd=10.00` e acumulado do dia já em 9.95 USD, **When** chega mídia cujo custo estimado ultrapassa o budget, **Then** o processor retorna `budget_exceeded`, a mensagem do fallback gracioso é enviada e a linha de `processor_usage_daily` não é incrementada pela chamada cancelada.
4. **Given** admin atualiza `daily_budget_usd` de 10 → 50 em `tenants.yaml`, **When** o próximo reload de config acontece (periódico, sem deploy), **Then** novas mensagens respeitam o novo limite.

---

### User Story 6 — Engenheiro pluga um segundo canal (Meta Cloud API) sem tocar o core (Priority: P2)

Engenheiro implementa adapter para Meta Cloud API (WhatsApp Business direto). Prova de que a abstração de canal não é "Evolution-shaped": pipeline, processors, router e observabilidade continuam funcionando sem alteração.

**Why this priority**: valor estratégico (reduzir dependência de Evolution como único caminho) + validação arquitetural. É P2 porque não gera valor user-facing direto no v1 — nenhum cliente do Ariel/ResenhAI migra para Meta Cloud imediatamente. Mas é gate de merge para confirmar que a inversão de acoplamento funcionou: se MetaCloudAdapter não couber, o epic falhou mesmo com áudio funcionando.

**Independent Test**: rodar a suite contra fixtures reais Meta Cloud (texto, áudio, imagem, mensagem interativa). Verificar que o pipeline processa normalmente e que a diff do PR-C toca **zero arquivos** em `pipeline.py`, `processors/`, `core/router/`.

**Acceptance Scenarios**:

1. **Given** payload real capturado de Meta Cloud API (formato oficial WhatsApp Business), **When** o webhook correspondente recebe, **Then** o adapter normaliza para `CanonicalInboundMessage` válido e o pipeline processa sem distinguir a origem.
2. **Given** duas mensagens com mesmo `external_message_id` mas sources diferentes (uma Evolution, outra Meta), **When** ambas chegam ao sistema, **Then** ambas são processadas como distintas (idempotency key compõe `source + source_instance + external_message_id`).
3. **Given** verificação de assinatura Meta Cloud (`X-Hub-Signature-256`), **When** webhook é chamado, **Then** pedidos com assinatura inválida são rejeitados com 401 antes de qualquer parsing.

---

### User Story 7 — Cliente envia sticker, reação, localização ou contato (Priority: P3)

Modalidades menos frequentes. Cada uma gera `text_representation` textual que o modelo de geração consegue contextualizar ("o cliente reagiu com 👍", "o cliente enviou localização X,Y", "o cliente compartilhou contato de Z").

**Why this priority**: P3 porque volume é residual em maioria dos tenants. Aceito no epic para fechar a matriz e evitar regressão onde estas modalidades caiam em fallback silencioso como hoje.

**Independent Test**: enviar uma reação, uma localização e um contato. Verificar que cada um produz uma `text_representation` interpretável e que a resposta final é coerente.

**Acceptance Scenarios**:

1. **Given** cliente reage com emoji 👍 em mensagem anterior do bot, **When** pipeline recebe, **Then** o texto representativo ("cliente reagiu com 👍 à mensagem X") entra no contexto sem gerar resposta redundante do bot (lógica de roteador decide se responde).
2. **Given** cliente envia localização, **When** processada, **Then** o texto representativo inclui nome do local (se enviado) + coordenadas e o bot pode tratar no próximo turno.
3. **Given** cliente envia sticker, **When** processado, **Then** o texto representativo é "[sticker: {descrição}]" — não tenta interpretar como imagem (fallback intencional, evita custo).

---

### Edge Cases

- **Áudio alucinado pelo Whisper** (silêncio transcrito como "Legendas em português"): filtro determinístico por duração <2s ou match com blocklist retorna texto representativo `[áudio curto sem fala clara]`.
- **Imagem com PII visual** (CPF, cartão, endereço visível): camada de mascaramento PII existente aplicada ao `text_representation` antes de logar/persistir.
- **URL WhatsApp expirada (410)**: retenção de 14d da URL em `media_analyses` alinhada com expiração natural do signed URL; erros 410 após 14d são tratados como "mídia expirada" sem reprocessamento.
- **Múltiplas mensagens no debounce flush (áudio + texto)**: pipeline recebe `list[CanonicalInboundMessage]`, processa cada uma, concatena `text_representation` único para o gerador.
- **Retry de webhook (mesma `external_message_id` enviada 2x)**: idempotency key evita reprocessamento e cobrança em dobro.
- **Provider STT/vision indisponível (5xx ou timeout)**: circuit breaker por tenant abre após N falhas consecutivas; enquanto aberto, todos os próximos de mesmo kind caem em fallback gracioso.
- **Base64 inline no payload Evolution**: quando disponível, adapter pula o download HTTP, economiza 100–300ms.
- **PDF com texto em imagem (escaneado sem OCR)**: detectado quando extração retorna string vazia — devolve mensagem pedindo que o cliente envie texto.
- **PDF encriptado**: erro de extração registrado no trace; fallback genérico.
- **Arquivo > 25MB (limite Whisper)**: rejeitado antes do download via header `content-length`.
- **Retroalimentação do hash**: dois clientes de tenants distintos enviando o mesmo arquivo (mesmo sha256) compartilham cache? Sim — cache é global por sha256 + kind + prompt_version; PII reside em `media_analyses.text_result` (com retenção) e não no cache Redis.
- **Webhook legado `/webhook/whatsapp/{instance_name}`**: mantém retrocompat redirecionando para o novo handler Evolution; remoção fica para epic futuro após métricas confirmarem zero tráfego.
- **Conteúdos fora do enum `kind`** (vídeo, poll, pagamento WhatsApp Pay, notificação de chamada, mensagem editada, mensagem de sistema/status de grupo): mapeados para `kind="unsupported"` com `sub_type` preservado. `text_representation="[conteúdo não suportado: {sub_type} — por favor, envie texto]"` gerado deterministicamente pelo processor `unsupported`, sem chamadas externas. Cliente recebe fallback tonalizado via LLM conforme FR-031.
- **Geração LLM indisponível durante fallback**: se o próprio LLM de resposta estiver fora (breaker no provider do gerador, não do processor de mídia), o sistema MUST usar a string hard-coded por tenant em `content_processing.fallback_messages.{marker}`, garantindo que o cliente NUNCA receba mensagem com marker em bracket notation.

## Requirements *(mandatory)*

### Functional Requirements

**Ingestão multi-canal**

- **FR-001**: O sistema MUST aceitar webhooks de pelo menos dois canais distintos (Evolution API e Meta Cloud API) através de endpoints separados, cada um com verificação de autenticação específica (token/segredo por canal).
- **FR-002**: O sistema MUST normalizar cada payload de canal para um formato único `CanonicalInboundMessage` antes de qualquer lógica de negócio — pipeline, roteador e processors NUNCA leem campos canal-específicos.
- **FR-003**: O sistema MUST suportar a adição de um novo canal exclusivamente através de (a) novo adapter implementando o contrato `verify_webhook()` + `normalize()` e (b) novo handler de webhook — sem alteração em `pipeline.py`, `processors/`, `core/router/` ou schema de dados.
- **FR-004**: Cada mensagem MUST ter `idempotency_key = sha256(source + source_instance + external_message_id)` garantindo que reentregas do mesmo canal NÃO sejam reprocessadas E que IDs coincidentes entre canais diferentes NÃO colidam.
- **FR-005**: O sistema MUST preservar a URL pública do webhook atual `/webhook/whatsapp/{instance_name}` como alias que encaminha ao novo handler Evolution, garantindo deploy zero-break.

**Conteúdo tipado e processamento**

- **FR-006**: O sistema MUST representar o conteúdo de cada mensagem como uma lista de `ContentBlock` discriminada por `kind` ∈ {text, audio, image, document, sticker, location, contact, reaction, unsupported}.
- **FR-007**: Para cada `kind` com processamento específico, o sistema MUST executar um processor que retorna `text_representation` textual utilizável pelo gerador de resposta, sem tornar o pipeline ciente do tipo.
- **FR-008**: O sistema MUST transcrever áudio (PTT e anexo) para texto em PT-BR quando `content_processing.audio_enabled=true` e o tenant tem budget disponível.
- **FR-009**: O sistema MUST gerar descrição textual de imagem quando `content_processing.image_enabled=true`, suportando dois modos de detalhe (básico e alto) configuráveis por tenant.
- **FR-010**: O sistema MUST extrair texto de documentos PDF e DOCX quando `content_processing.document_enabled=true`, até o limite de páginas configurado.
- **FR-011**: Para modalidades não suportadas por processor específico (sticker, reaction, location, contact) E para conteúdos que não se enquadram em nenhum dos 9 `kind`s previstos (vídeo, poll, pagamento WhatsApp Pay, notificação de chamada, mensagem editada, mensagem de sistema), o sistema MUST gerar `text_representation` determinístico a partir de metadados, sem chamar providers externos. Conteúdos fora do enum caem em `kind="unsupported"` com `sub_type` tag preservado (ex.: `sub_type="video"`) e `text_representation="[conteúdo não suportado: {sub_type} — por favor, envie texto]"`.

**Debounce multi-mensagem**

- **FR-012**: O sistema MUST aceitar que um único flush do debounce contenha múltiplas `CanonicalInboundMessage` (ex.: áudio + texto enviados em sequência curta) e processá-las como uma fala única concatenada.

**Observabilidade**

- **FR-013**: O sistema MUST registrar um step `content_process` no trace da mensagem com: input (referência ao kind e metadados), output (text_representation completo), provider usado, custo em USD, latência, flag `cache_hit` e status (ok/error).
- **FR-014**: O sistema MUST persistir em tabela `media_analyses` cada análise de mídia completa (não truncada) para auditoria, acessível apenas via pool admin (carve-out ADR-027).
- **FR-015**: O sistema MUST agregar uso diário por (tenant, kind, provider) em `processor_usage_daily` para permitir enforcement de budget e visualização no portal.
- **FR-016**: Traces antigos (gerados antes deste epic) MUST continuar renderizando no Trace Explorer com os 12 steps originais, sem migração de dados.

**Feature flags e budget**

- **FR-017**: Cada tenant MUST ter controle granular via `content_processing.{enabled, audio_enabled, image_enabled, document_enabled, daily_budget_usd}`, carregado do arquivo de configuração do tenant e reloadável sem deploy. Reload é feito por poll periódico a cada 60 segundos em cada worker — RTO de rollback de incidente ≤ 60s.
- **FR-018**: Quando o tenant ultrapassa `daily_budget_usd`, o sistema MUST retornar um fallback gracioso via marker estruturado (`text_representation="[budget_exceeded]"` + metadados) sem chamar o provider externo. O step de geração de resposta LLM traduz o marker em mensagem tonalizada conforme a persona do tenant (ver FR-031).
- **FR-019**: Quando `content_processing.enabled=false` para um tenant, todas as modalidades não-texto MUST cair em fallback genérico via marker estruturado (`text_representation="[feature_disabled: {kind}]"`) e NUNCA chamar providers externos.

**Performance e robustez**

- **FR-020**: O sistema MUST rejeitar downloads de mídia cujo `content-length` exceda 25MB antes de iniciar o download, para não consumir banda e memória em mídias que serão rejeitadas pelo provider.
- **FR-021**: Quando o payload do canal já inclui o binário da mídia em base64, o sistema MUST pular o download HTTP e usar o binário inline.
- **FR-022**: O sistema MUST aplicar cache por `sha256` do binário + kind + versão do prompt com TTL de 14 dias, compartilhado entre tenants, para reduzir custo e latência de mídias idênticas.
- **FR-023**: O sistema MUST aplicar circuit breaker por tenant+provider: após 5 falhas consecutivas dentro de uma janela de 60 segundos, o breaker abre por 30 segundos; ao expirar, 1 requisição half-open determina fechamento (sucesso) ou reabertura com backoff exponencial (30s → 60s → 120s → 300s cap, reset após 10 min sem falhas). Enquanto aberto, todas as chamadas subsequentes ao mesmo provider caem em fallback gracioso via marker (`[provider_unavailable]`).
- **FR-024**: O sistema MUST aplicar retry com jitter em falhas transitórias de providers (5xx, timeout de rede): até 3 tentativas com backoff exponencial base 500ms e jitter ±25% (ex.: 500ms, 1s, 2s aproximados), respeitando o limite total de tempo alocado ao step (15s áudio, 12s imagem, 15s documento). Timeout do step aborta retries remanescentes e aciona fallback.

**Qualidade de saída**

- **FR-025**: Transcrições de áudio MUST passar por filtro determinístico que detecta alucinações comuns (silêncio transcrito como frases recorrentes do modelo, duração < 2s com match de blocklist) e substitui por texto representativo neutro.
- **FR-026**: Descrições de imagem MUST passar pela camada de mascaramento PII existente antes de serem usadas no contexto de geração ou persistidas em logs/traces.

**Estratégia de mensagens de fallback**

- **FR-031**: Para TODOS os cenários de fallback user-facing (budget estourado, feature desligada, circuit breaker aberto, mídia >25MB, PDF escaneado, PDF encriptado, áudio alucinado/muito curto, provider 5xx após retries, conteúdo `unsupported`), o sistema MUST usar estratégia de "marker estruturado + geração LLM":
  - Processor retorna `ProcessedContent.text_representation` com marker determinístico em bracket notation (ex.: `[budget_exceeded]`, `[provider_unavailable]`, `[audio_silent]`, `[pdf_scanned]`, `[pdf_encrypted]`, `[media_too_large: {size_mb}]`, `[feature_disabled: {kind}]`, `[content_unsupported: {sub_type}]`).
  - O step de geração de resposta LLM reconhece markers via instrução no system prompt do agente do tenant e produz mensagem tonalizada conforme a persona (Ariel informal; ResenhAI profissional).
  - Se a própria geração LLM falhar (provider do gerador indisponível), o sistema MUST recorrer a uma string hard-coded por tenant configurada em `tenants.yaml::content_processing.fallback_messages.{marker}` como última rede. Default global é fornecido caso a chave esteja ausente.
- **FR-032**: Cada marker de fallback MUST ser registrado no trace (`content_process.output.marker`) para facilitar análise de volume de incidentes e regressão no Trace Explorer.

**LGPD e retenção**

- **FR-027**: O sistema MUST NÃO persistir bytes raw de áudios/imagens/documentos em nenhuma tabela — apenas a URL do provedor (com expiração natural) e o texto extraído.
- **FR-028**: Após 14 dias, o sistema MUST anular `source_url` em `media_analyses`; após 90 dias, MUST deletar a linha completa.

**Segurança**

- **FR-029**: Cada webhook MUST validar autenticação do canal correspondente (token Evolution; assinatura HMAC Meta Cloud) e rejeitar payloads inválidos com 401 antes de qualquer processamento.

**Compatibilidade**

- **FR-030**: A refatoração da camada de ingestão MUST manter 100% dos testes existentes (suite do epic 005 com 173 testes e do epic 008 com 191 testes) passando sem alteração funcional.

### Key Entities

- **CanonicalInboundMessage**: representação source-agnostic de uma mensagem recebida. Atributos: `source`, `source_instance`, `external_message_id`, `idempotency_key`, `tenant_id`, `sender`, `conversation_ref`, `content: list[ContentBlock]`, `received_at`, `raw_payload` (auditoria). Relação: 1:N com `ContentBlock`.
- **ContentBlock**: unidade tipada de conteúdo discriminada por `kind` ∈ {text, audio, image, document, sticker, location, contact, reaction, unsupported}. Cada kind carrega atributos específicos (ex.: `url`, `mime_type`, `duration`, `caption`). Quando `kind="unsupported"`, o atributo `sub_type` carrega a classificação original do canal (ex.: `video`, `poll`, `payment`, `call_notification`, `edited`, `system`). Relação: N:1 com `CanonicalInboundMessage`.
- **ProcessedContent**: resultado de um processor. Atributos: `kind`, `provider`, `text_representation`, `cost_usd`, `latency_ms`, `cache_hit`, `status` ∈ {ok, error, budget_exceeded, unsupported}, `marker?` (identificador de fallback em bracket notation para casos não-ok, ex.: `[budget_exceeded]`), `error_reason?`, `raw_response?` (para audit). Relação: 1:1 com `ContentBlock` processado.
- **MediaAnalysis**: persistência auditável de uma análise. Atributos: `id`, `tenant_id`, `message_id`, `content_sha256`, `source_url` (nullable após 14d), `kind`, `provider`, `text_result` completo, `cost_usd`, `latency_ms`, `cache_hit`, `created_at`. Admin-only, sem RLS (carve-out ADR-027). Retenção: URL 14d, linha 90d.
- **ProcessorUsageDaily**: agregação diária de custo e volume. Atributos: `(tenant_id, date, kind, provider)`, `count`, `cost_usd_sum`, `cache_hits`, `cache_misses`. Suporta enforcement de budget. Admin-only.
- **ChannelAdapter** (Protocol): contrato `verify_webhook(request)` + `normalize(payload) -> list[CanonicalInboundMessage]`. Não acessa DB nem providers externos. Registro por nome em registry singleton.
- **ContentProcessor** (Protocol): contrato `process(block: ContentBlock, ctx: ProcessorContext) -> ProcessedContent`. Registrado por `kind`. Isolado: recebe todas as dependências via `ProcessorContext`.
- **ProcessorContext**: injeção de dependências para processors. Atributos: `tenant_config`, `cache`, `budget_tracker`, `providers` (STT, vision, etc.), `logger`, `tracer`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Correção funcional (P1 user stories)**

- **SC-001**: 100% dos áudios PTT e anexados com duração ≤ 60s e tamanho ≤ 25MB recebidos por tenants com `audio_enabled=true` geram resposta textual relevante ao conteúdo em menos de 8 segundos (p95) end-to-end entre webhook e entrega da resposta.
- **SC-002**: 100% das imagens (com ou sem legenda) recebidas por tenants com `image_enabled=true` geram resposta contextual em menos de 9 segundos (p95) end-to-end.
- **SC-003**: 100% dos documentos PDF/DOCX com texto extraível recebidos por tenants com `document_enabled=true` geram resposta referenciando o conteúdo em menos de 10 segundos (p95) end-to-end.
- **SC-004**: Zero mensagens de mídia descartadas silenciosamente. Toda mensagem recebida aparece em um trace — mesmo em caso de fallback por feature desligada ou budget estourado.

**Observabilidade (P1 user story 4)**

- **SC-005**: 100% dos traces de conversas que tocaram mídia exibem o step `content_process` no portal com input, output, provider, custo em USD, latência em ms e flag `cache_hit` preenchidos e legíveis sem truncamento.
- **SC-006**: Admin consegue identificar a origem de qualquer regressão de custo ou latência por tenant em menos de 5 minutos usando os filtros existentes do Trace Explorer + novo gráfico de custo diário por processor.

**Performance e economia**

- **SC-007**: Após 7 dias em produção, taxa de `cache_hit` em processors de mídia é ≥ 30% — evidência de que dedup por sha256 está economizando chamadas a providers externos.
- **SC-008**: Zero casos em produção de tenant que estourou `daily_budget_usd` resultando em timeout de resposta ou crash. 100% dos casos de budget estourado resultam em fallback gracioso dentro do mesmo SLA de resposta de texto (p95 ≤ 2s pior que baseline).
- **SC-009**: Latência p95 de conversas puramente textuais após o merge do PR-A NÃO piora em mais de 5ms comparado ao baseline pré-epic (gate de merge de PR-A).

**Qualidade e não-regressão**

- **SC-010**: Suite do epic 005 (173 testes) + epic 008 (191 testes) passa 100% sem alteração funcional após cada um dos três PRs — gate de merge obrigatório.
- **SC-011**: Taxa de alucinação de transcrição (texto retornado pelo provider que não corresponde à fala real) fica ≤ 2% em amostra mensal de 100 áudios PT-BR após aplicação do filtro determinístico de silêncio. **Metodologia**: sample aleatório estratificado por tenant ativo no período (peso proporcional ao volume), draw via query SQL em `media_analyses` pelo `pool_admin`; revisão humana binária (alucinação: sim/não) feita em rotação pelo time de QA comparando transcript × áudio original (acesso à `source_url` quando ainda dentro do prazo de 14d, ou descartando a amostra se expirada); resultado registrado em planilha mensal com link para o trace original.
- **SC-012**: Zero vazamentos de PII (CPF, cartão, endereço físico, email, telefone) em `text_representation` de imagens descritas, verificado por amostragem mensal de 50 casos. **Metodologia**: sample aleatório estratificado por tenant; pré-filtro automático via regex para flagrar candidatos antes da revisão humana binária (vazamento: sim/não); reviewer em rotação QA via preview de imagem no portal admin (acesso pool_admin) + texto descritivo exibido lado-a-lado; qualquer caso positivo dispara hotfix no mascaramento PII + re-verificação do mês.

**Validação arquitetural (P2 user story 6)**

- **SC-013**: PR-C (Meta Cloud Adapter) é mergeado sem nenhuma alteração em `apps/api/prosauai/pipeline.py`, nenhum arquivo em `apps/api/prosauai/processors/` e nenhum arquivo em `apps/api/prosauai/core/router/`. A diff do PR-C é confinada a `channels/inbound/meta_cloud/`, `api/webhooks/meta_cloud.py`, fixtures e ADR-035.
- **SC-014**: Fixture capturada de payload real Meta Cloud produz `CanonicalInboundMessage` válido via `MetaCloudAdapter.normalize()` e percorre o pipeline completo produzindo trace idêntico em estrutura ao de Evolution (mesmos 14 steps).

**Rollout seguro**

- **SC-015**: Qualquer modalidade de qualquer tenant pode ser desligada em menos de 2 minutos via alteração em `tenants.yaml` seguida de reload periódico — sem deploy, sem restart de pods.
- **SC-016**: Aumento de custo mensal em providers externos por tenant é previsível via `processor_usage_daily`: erro de projeção entre acumulado observado e custo final do mês é ≤ 10% após 7 dias de dados.

## Assumptions

- **Volume esperado alto**: 10k+ mídias/mês por tenant ativo é o cenário de planejamento. Cache, budget e circuit breaker são infraestrutura obrigatória, não opcional.
- **Usuários finais esperam resposta síncrona**: envio de áudio/imagem pelo WhatsApp cria expectativa de resposta única em tempo razoável. Mensagens de follow-up ("recebi, estou processando" + resposta depois) foram descartadas por quebrarem a UX padrão de WhatsApp. Se p95 real de áudio > 5s após 1 mês em produção, revisitar em retro.
- **OpenAI é escolha default de provider** para STT (whisper-1) e vision (gpt-4o-mini via Responses API). Swap futuro para outros providers (Deepgram, Claude, Gemini) é viabilizado pelo contrato `ContentProcessor` + `ProcessorContext`, mas está fora do escopo v1. Documentado no ADR-033.
- **Transcrições em PT-BR são a prioridade**. Qualidade em outros idiomas é best-effort; não é parte do critério de aceite.
- **Budget enforcement é best-effort no boundary do dia**: agregado em `processor_usage_daily` consulta-se single-row antes do processor rodar; possíveis chamadas simultâneas dentro da mesma janela que empurrem o acumulado acima do budget são aceitáveis (erro ≤ 1 chamada acima do limite por minuto).
- **Retenção 14d da URL do WhatsApp alinha com a expiração natural do signed URL Meta** — fora deste prazo, reprocessar qualquer mídia é inviável sem o binário original (que não armazenamos).
- **Operação Ariel vai em primeiro** (rollout progressivo). Tenant ResenhAI é ativado após observação de 7 dias em Ariel sem regressão.
- **Evolution API continua como canal primário** durante o epic. Meta Cloud adapter serve apenas como validação arquitetural em v1; migração de tráfego real para Meta Cloud é escopo de epic futuro.
- **Reuso de infra existente**: Redis (debounce + idempotência + novo cache), PostgreSQL via `pool_app`/`pool_admin`, OTel já instrumentado (fastapi/httpx/redis), pricing table do ADR-029, camada PII existente. Não há reescrita de infra compartilhada.
- **Portal admin entregue no epic 008 cobre o frontend de trace + performance** sem mudança estrutural — só acréscimo de uma entrada no enum `STEP_NAMES` e um novo gráfico na aba Performance AI.
- **Hallucination filter no Whisper é determinístico** (duração + blocklist). Detecção semântica via LLM auxiliar fica fora do escopo v1 — volume de áudios curtos ruidosos é suficiente para validar eficácia da heurística.
- **Feature flag reload é periódico** (não event-driven): reload a cada N minutos no worker é aceitável para tenant config. Rollback imediato de incidente tolera latência até o próximo reload.
- **Escopos explicitamente fora do v1**: Instagram, Telegram, frames de vídeo, extração tabular de PDF, transcription streaming, detecção automática de OCR em PDF escaneado, tradução de conteúdo, classificação automática de documentos. Endereçados em epics 010–012.

---

handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada com 5 Q&As autonomamente respondidas (marker+LLM fallback, circuit breaker numérico, reload 60s, unsupported kinds com sub_type, metodologia de amostragem SC-011/SC-012). 32 FRs (2 novos: FR-031 fallback strategy, FR-032 marker no trace), 16 SCs (SC-011/SC-012 agora com metodologia). Próxima etapa: plan gera data-model, contracts e research."
  blockers: []
  confidence: Alta
  kill_criteria: "Invalidada se (a) MetaCloudAdapter exige mudança no schema Canonical após adoção no pipeline, (b) p95 de áudio >15s em teste de carga antes do PR-B (forçaria repensar UX síncrona — ver Assumption §UX), ou (c) provider OpenAI é rejeitado por compliance (obrigaria refazer ADR-033)."
