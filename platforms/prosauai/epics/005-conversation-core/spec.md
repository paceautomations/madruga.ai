# Feature Specification: Conversation Core

**Feature Branch**: `epic/prosauai/005-conversation-core`  
**Created**: 2026-04-12  
**Status**: Draft  
**Input**: Substituir o handler echo por um pipeline completo de conversação com IA, persistência em BD, e multi-tenancy — transformando o ProsaUAI em um agente WhatsApp funcional que responde com inteligência 24/7.

## User Scenarios & Testing

### User Story 1 - Resposta IA a Mensagem Individual (Priority: P1)

Um cliente envia uma mensagem de texto pelo WhatsApp para o número do agente. O sistema recebe a mensagem, processa pelo pipeline de conversação (lookup do cliente, montagem de contexto, guardrails, geração via LLM), e responde com uma mensagem relevante e contextual em PT-BR.

**Why this priority**: Esta é a proposta de valor fundamental do ProsaUAI. Sem resposta IA, a plataforma não entrega valor algum. Todos os epics anteriores (001-004) são infraestrutura para este momento.

**Independent Test**: Enviar uma mensagem WhatsApp para o número do agente e verificar que a resposta é gerada por IA (não é echo), é relevante ao contexto da mensagem, e chega em tempo hábil (<30s).

**Acceptance Scenarios**:

1. **Given** um cliente envia "Qual o horário de funcionamento?" pelo WhatsApp, **When** o pipeline processa a mensagem, **Then** o agente responde com informação relevante baseada no system prompt do tenant em menos de 30 segundos.
2. **Given** um cliente envia uma mensagem pela primeira vez, **When** o pipeline processa, **Then** um registro de customer é criado automaticamente, uma conversa é iniciada, e a resposta é entregue.
3. **Given** um cliente envia uma mensagem e o LLM falha (timeout/erro), **When** o pipeline detecta a falha, **Then** uma mensagem de fallback é enviada ("Desculpe, não consegui processar sua mensagem. Tente novamente em instantes.").

---

### User Story 2 - Contexto Conversacional Persistente (Priority: P1)

Um cliente envia múltiplas mensagens em sequência. O agente mantém contexto das mensagens anteriores (sliding window de 10 mensagens) e responde de forma coerente com o histórico da conversa, sem repetir informações já dadas.

**Why this priority**: Respostas stateless destroem a experiência do usuário. Contexto é o que diferencia um chatbot útil de um frustrante. Co-prioridade P1 porque sem contexto a resposta IA perde valor rapidamente.

**Independent Test**: Enviar 3 mensagens sequenciais onde a terceira referencia a primeira. Verificar que a resposta da terceira mensagem demonstra conhecimento do conteúdo da primeira.

**Acceptance Scenarios**:

1. **Given** um cliente perguntou "Vocês vendem camisetas?" e recebeu "Sim, temos vários modelos", **When** o cliente pergunta "Quais cores disponíveis?", **Then** o agente responde sobre cores de camisetas (não pede para repetir o assunto).
2. **Given** uma conversa tem mais de 10 mensagens, **When** uma nova mensagem chega, **Then** o contexto inclui apenas as 10 mensagens mais recentes (sliding window) e a resposta permanece coerente.
3. **Given** um cliente retorna após um período de inatividade menor que 24h, **When** a conversa anterior ainda está ativa, **Then** o histórico persistido é recuperado e o contexto é mantido.
4. **Given** um cliente retorna após mais de 24h de inatividade, **When** a conversa anterior foi encerrada automaticamente, **Then** uma nova conversa é criada e o agente responde sem contexto da conversa anterior.

---

### User Story 3 - Multi-Tenant com Agentes Independentes (Priority: P2)

Dois tenants (Ariel e ResenhAI) operam simultaneamente com agentes IA independentes. Cada agente tem seu próprio system prompt, personalidade e comportamento. Mensagens de clientes de um tenant nunca influenciam respostas do outro.

**Why this priority**: Multi-tenancy é requisito arquitetural fundamental (epics 003-004 já prepararam), mas o valor imediato para o usuário final é a resposta IA em si (P1). Multi-tenant garante escalabilidade e isolamento.

**Independent Test**: Configurar 2 tenants com system prompts distintos (ex: um formal, outro informal). Enviar a mesma pergunta para ambos e verificar que as respostas refletem personalidades diferentes.

**Acceptance Scenarios**:

1. **Given** tenant Ariel tem system prompt "Você é um assistente formal de barbearia", **When** um cliente do Ariel pergunta "Oi, tudo bem?", **Then** o agente responde de forma formal e contextualizada ao negócio de barbearia.
2. **Given** tenant ResenhAI tem system prompt "Você é um assistente de futebol", **When** um cliente do ResenhAI pergunta "Oi, tudo bem?", **Then** o agente responde com linguagem de futebol, diferente do tenant Ariel.
3. **Given** 2 tenants recebem mensagens simultaneamente, **When** ambos processam, **Then** nenhuma mensagem ou contexto vaza entre tenants (isolamento RLS verificado).

---

### User Story 4 - Resposta IA em Grupo com @Mention (Priority: P2)

Um usuário menciona o agente em um grupo WhatsApp. O agente processa apenas mensagens com @mention, ignora as demais, e responde no grupo com contexto relevante.

**Why this priority**: Grupos são um canal relevante para PMEs (grupos de clientes, comunidades). O router MECE (epic 004) já diferencia mensagens individuais de grupo — o pipeline de conversação precisa respeitar essa decisão.

**Independent Test**: Enviar mensagem com @mention do agente em um grupo e verificar que a resposta é entregue no grupo. Enviar mensagem sem @mention e verificar que o agente não responde.

**Acceptance Scenarios**:

1. **Given** um grupo WhatsApp com o agente adicionado, **When** um membro envia "@agente qual a programação de hoje?", **Then** o agente responde no grupo com informação relevante.
2. **Given** um grupo WhatsApp com o agente, **When** um membro envia mensagem sem @mention, **Then** o agente não responde (decisão do router: `IgnoreDecision`).

---

### User Story 5 - Consulta de Dados ResenhAI via Tool Call (Priority: P3)

Um cliente do tenant ResenhAI pergunta sobre rankings ou estatísticas de futebol. O agente usa um tool call para consultar dados do ResenhAI e inclui a informação na resposta.

**Why this priority**: Tool calls demonstram a extensibilidade do agente, mas são específicos de um tenant. O pipeline core (P1-P2) entrega valor sem tools.

**Independent Test**: Enviar pergunta "Qual o ranking atual?" para o agente ResenhAI e verificar que a resposta inclui dados reais do sistema ResenhAI.

**Acceptance Scenarios**:

1. **Given** um cliente do ResenhAI pergunta "Quem está em primeiro no ranking?", **When** o agente processa, **Then** o agente chama o tool de ranking, obtém dados, e responde com a informação.
2. **Given** o serviço ResenhAI está indisponível, **When** o tool call falha, **Then** o agente responde que não conseguiu obter os dados no momento e sugere tentar novamente.

---

### User Story 6 - Guardrails de Segurança (Priority: P3)

Mensagens de entrada contendo PII (CPF, telefone, email) são detectadas pelos guardrails regex. O sistema trata PII adequadamente na entrada e garante que a saída do LLM não exponha PII em logs ou traces.

**Why this priority**: Segurança é importante mas os guardrails regex são uma camada básica. O sistema já opera em ambiente controlado (PMEs conhecidas). Guardrails ML são escopo futuro.

**Independent Test**: Enviar mensagem contendo um CPF e verificar que o PII é detectado, tratado (hash em logs), e que a resposta do agente não repete o CPF.

**Acceptance Scenarios**:

1. **Given** um cliente envia mensagem contendo um CPF (ex: "Meu CPF é 123.456.789-00"), **When** o input guard processa, **Then** o PII é detectado e hasheado nos logs/traces (nunca em texto plano).
2. **Given** o LLM gera resposta contendo um número de telefone, **When** o output guard processa, **Then** o PII é removido ou mascarado antes do envio.
3. **Given** uma mensagem contém PII na entrada, **When** o input guard processa, **Then** a mensagem é processada normalmente (PII não bloqueia) mas o PII é hasheado em todos os logs e traces. O bloqueio de entrada ocorre apenas para mensagens que excedem o limite de tamanho (>4000 chars) ou conteúdo malicioso detectado por regex.

---

### Edge Cases

- O que acontece quando o LLM retorna resposta vazia? O avaliador heurístico rejeita e tenta retry 1x; se falhar novamente, envia mensagem de fallback.
- O que acontece quando o cliente envia mensagem muito longa (>4000 chars)? O input guard trunca ou rejeita com mensagem informativa.
- O que acontece quando múltiplas mensagens chegam no mesmo debounce window com agent_ids diferentes? O pipeline usa o agent_id da última mensagem no buffer.
- O que acontece quando o pool de conexões Postgres está esgotado? O pipeline falha graciosamente com mensagem de fallback e registra erro nos logs.
- O que acontece quando o semáforo de LLM (10) está cheio? A requisição aguarda até um slot liberar; se timeout (60s), envia fallback.
- O que acontece quando um customer já existe mas mudou de tenant? O customer é identificado por phone+tenant_id (chave composta), então um novo registro é criado para o novo tenant.
- O que acontece quando a conversa ativa não existe para o customer? Uma nova conversa é criada automaticamente no primeiro contato ou quando a anterior foi encerrada.
- O que acontece quando a conversa atinge 24h de inatividade? O sistema encerra automaticamente a conversa (status: closed, reason: inactivity_timeout). Próxima mensagem cria nova conversa.
- O que acontece quando o connection pool Postgres está esgotado? O pipeline aguarda até 5s por uma conexão livre; se timeout, envia mensagem de fallback e registra erro nos logs.

## Clarifications

### Session 2026-04-12

- Q: Quando uma conversa é encerrada automaticamente (timeout de inatividade)? → A: 24h de inatividade (configurável por tenant). Nova conversa criada após timeout.
- Q: O que acontece com o resultado da classificação de intent (FR-007)? → A: Classificação determina template de prompt + é logada para analytics. Confiança <0.7 usa intent "general" como fallback.
- Q: Qual a estratégia de retry quando o LLM falha (FR-009)? → A: Mesmo prompt, sem backoff (pipeline inline não pode atrasar). Se retry também falha, mensagem de fallback.
- Q: O guardrail de PII na entrada bloqueia a mensagem ou apenas sanitiza logs? → A: PII na entrada: mensagem é processada normalmente (PII hasheado em logs/traces, texto original vai para LLM). PII na saída: mascarado/removido antes de enviar ao cliente.
- Q: Qual o tamanho do connection pool e comportamento quando esgotado? → A: Pool de 10 conexões (alinhado ao semáforo LLM). Esgotado: aguarda com timeout de 5s, depois mensagem de fallback.

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE receber mensagens WhatsApp via webhook (individual ou grupo com @mention), processar pelo pipeline de conversação, e responder com texto gerado por IA em menos de 30 segundos.
- **FR-002**: O sistema DEVE criar automaticamente um registro de customer na primeira interação, identificado pela combinação de número de telefone e tenant.
- **FR-003**: O sistema DEVE manter uma sliding window das últimas 10 mensagens como contexto para cada conversa, permitindo respostas contextuais.
- **FR-004**: O sistema DEVE persistir todas as conversas, mensagens e dados de customers em banco de dados relacional com RLS (Row-Level Security) por tenant.
- **FR-005**: O sistema DEVE aplicar guardrails regex na entrada para detecção de PII (CPF, telefone, email). PII detectado é hasheado (SHA-256) em logs e traces, mas a mensagem original é processada normalmente pelo pipeline (PII não bloqueia a entrada).
- **FR-006**: O sistema DEVE aplicar guardrails regex na saída do LLM para prevenir vazamento de PII na resposta ao cliente. PII detectado na saída é mascarado/removido antes do envio (diferente da entrada, onde apenas logs são sanitizados).
- **FR-007**: O sistema DEVE classificar a intenção da mensagem do cliente antes de gerar a resposta. A classificação determina o template de prompt usado e é registrada para analytics. Confiança abaixo de 0.7 aciona fallback para intent "general".
- **FR-008**: O sistema DEVE gerar respostas usando LLM (GPT-4o-mini como default) via framework de orquestração, com system prompt configurável por agente.
- **FR-009**: O sistema DEVE avaliar a qualidade da resposta gerada usando heurísticas (resposta vazia, muito curta <10 chars, encoding incorreto) e fazer retry 1x (mesmo prompt, sem backoff — pipeline inline não tolera delay adicional) antes de enviar mensagem de fallback.
- **FR-010**: O sistema DEVE suportar múltiplos tenants operando em paralelo com agentes IA independentes (system prompts, modelos e comportamentos diferentes).
- **FR-011**: O sistema DEVE preservar o `agent_id` resolvido pelo router através do debounce buffer até o flush callback, sem perda de informação.
- **FR-012**: O sistema DEVE suportar tool calls para consulta de dados externos (ex: ResenhAI ranking/stats) com controle de acesso (ACL pattern).
- **FR-013**: O sistema DEVE produzir spans OpenTelemetry para cada etapa do pipeline de conversação (customer lookup, context assembly, classify, generate, evaluate, deliver).
- **FR-014**: O sistema DEVE limitar chamadas LLM concorrentes a 10 via semáforo assíncrono.
- **FR-015**: O sistema DEVE respeitar hard limits: máximo 20 tool calls por conversa, timeout de 60 segundos por geração, e budget de 8K tokens de contexto.
- **FR-016**: O sistema DEVE garantir que mensagens são append-only (nunca editadas após criação).
- **FR-017**: O sistema DEVE manter no máximo uma conversa ativa por customer/channel.
- **FR-018**: O sistema DEVE encerrar automaticamente conversas após 24 horas de inatividade (configurável por tenant, range 1h-72h). Após encerramento, nova mensagem do customer cria uma nova conversa.
- **FR-019**: O sistema DEVE usar o resultado da classificação de intent para selecionar o template de prompt adequado e registrar a classificação para analytics. Intent com confiança <0.7 DEVE usar fallback "general".
- **FR-020**: O sistema DEVE manter um connection pool de 10 conexões Postgres (alinhado ao semáforo LLM). Quando esgotado, aguardar até 5 segundos antes de enviar mensagem de fallback.

### Key Entities

- **Customer**: Representa um cliente identificado por telefone + tenant. Armazena informações de contato e preferências. Relaciona-se com múltiplas conversas ao longo do tempo.
- **Conversation**: Sessão de interação entre customer e agente. Possui estado (active, closed), pertence a um tenant, e contém múltiplas mensagens ordenadas cronologicamente. Encerramento automático após 24h de inatividade (configurável por tenant, range 1h-72h). Motivo de encerramento registrado (inactivity_timeout, user_closed, escalated).
- **Message**: Unidade atômica de comunicação dentro de uma conversa. Pode ser do customer (inbound) ou do agente (outbound). Append-only — nunca editada.
- **ConversationState**: Estado corrente da conversa incluindo contexto (sliding window), metadados e informações de sessão. Atualizado a cada interação.
- **Agent**: Configuração do agente IA de um tenant. Contém referência ao modelo LLM, system prompt, e configurações de comportamento.
- **Prompt**: Template de system prompt associado a um agente. Define personalidade, instruções e restrições do agente.
- **EvalScore**: Pontuação de qualidade da resposta gerada. Registrada de forma assíncrona, nunca bloqueia a entrega da resposta.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Clientes recebem resposta IA relevante (não-echo) em menos de 30 segundos após envio da mensagem, em 95% dos casos.
- **SC-002**: O contexto conversacional é mantido corretamente — respostas à 3ª mensagem em uma sequência demonstram conhecimento das mensagens anteriores em 100% dos testes.
- **SC-003**: 2 tenants (Ariel e ResenhAI) operam em paralelo com zero vazamento de dados entre eles (verificável por testes de isolamento RLS).
- **SC-004**: Respostas com problemas de qualidade (vazias, muito curtas, encoding incorreto) são detectadas e tratadas (retry + fallback) em 100% dos casos.
- **SC-005**: PII detectável por regex (CPF, telefone, email) nunca aparece em texto plano em logs ou traces — apenas hash SHA-256.
- **SC-006**: O pipeline completo (webhook → resposta) é rastreável fim-a-fim via spans OpenTelemetry no Phoenix.
- **SC-007**: Cobertura de testes unitários ≥80% para cada módulo do pipeline de conversação (M4-M10), com integration test do pipeline completo usando LLM mockado.
- **SC-008**: O agente ResenhAI consegue consultar dados de ranking/stats via tool call e incluir na resposta.

## Assumptions

- Clientes interagem via WhatsApp com conectividade estável (mensagens chegam via Evolution API já validadas pelos epics anteriores).
- O volume de mensagens no MVP é baixo (<100 RPM sustained), compatível com pipeline inline e semáforo de 10.
- GPT-4o-mini é suficiente para qualidade de resposta no MVP. Modelo pode ser trocado por agente sem alteração de código.
- O Supabase (Postgres 15) será provisionado como container Docker no mesmo ambiente. Sem managed service no MVP.
- OpenAI API key será fornecida via variável de ambiente (`.env`). Integração com Infisical é escopo futuro.
- System prompts iniciais serão fornecidos como seed data SQL para os 2 tenants (Ariel e ResenhAI).
- O router MECE (epic 004) já resolve corretamente o `agent_id` e a decisão de responder. O pipeline de conversação confia nessa decisão.
- Mensagens de grupo sem @mention já são filtradas pelo router (`IgnoreDecision`) e nunca chegam ao pipeline de conversação.
- Summarization de contexto não é necessária no MVP — conversas de PME raramente excedem 20 trocas.
- Handoff para humano (epic 008) e triggers proativos (epic 009) estão fora de escopo. `BypassAIDecision` do router continua como log-only.

---
handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada para Conversation Core (epic 005). 5 ambiguidades resolvidas: lifecycle/timeout (24h), classifier output (prompt template + analytics), retry strategy (sem backoff), PII guardrail behavior (entrada não bloqueia, saída mascara), pool sizing (10 conexões, 5s timeout). 20 requisitos funcionais, 7 entidades, 8 critérios de sucesso. Pronta para planejamento técnico."
  blockers: []
  confidence: Alta
  kill_criteria: "Se pydantic-ai não suportar tool calls com controle de acesso, ou se asyncpg+RLS apresentar overhead inaceitável no pipeline inline, a arquitetura precisa ser revisada."
