# Feature Specification: Observability — Tracing Total da Jornada de Mensagem

**Feature Branch**: `epic/prosauai/002-observability`  
**Created**: 2026-04-10  
**Status**: Draft  
**Input**: Implementar observabilidade fim-a-fim no pipeline de mensagens do ProsauAI — tracing completo da jornada webhook → router → debounce → echo com Phoenix (Arize) self-hosted, correlação log↔trace, dashboards operacionais, e forward-compat para LLM tracing (epic 003).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Debug de Mensagem por ID (Priority: P1)

Como operador do ProsauAI, quero consultar o que aconteceu com uma mensagem específica (dado um `message_id` ou `trace_id`) e ver o waterfall completo de toda a jornada — desde o webhook até o echo enviado — com timing por etapa, para diagnosticar problemas em menos de 30 segundos.

**Why this priority**: Sem essa capacidade, qualquer investigação de "por que a mensagem X não foi respondida?" exige arqueologia manual em logs distribuídos sem correlação — processo que leva minutos a horas e é a principal dor operacional hoje.

**Independent Test**: Pode ser testado enviando 1 mensagem via webhook e verificando que o Phoenix UI exibe um trace completo com 7+ spans (webhook → parse → route → debounce.append → debounce.flush → provider.send_text → echo.completed) com trace_id único.

**Acceptance Scenarios**:

1. **Given** uma mensagem enviada via webhook WhatsApp, **When** o operador abre o Phoenix UI e busca pelo `trace_id`, **Then** o waterfall exibe todas as etapas da jornada (webhook → parse → route → debounce.append → debounce.flush → provider.send_text → echo.completed) com duração individual por span.
2. **Given** um `trace_id` obtido do log estruturado, **When** o operador pesquisa esse ID no Phoenix, **Then** o trace correspondente é encontrado e exibe a árvore completa de spans.
3. **Given** uma mensagem que falhou em alguma etapa (ex: HMAC inválido), **When** o operador busca o trace, **Then** o span da falha está marcado com status ERROR e atributos descrevendo o motivo (sem expor PII).

---

### User Story 2 - Correlação Log↔Trace (Priority: P1)

Como desenvolvedor, quero que todo log estruturado emitido pelo `structlog` contenha automaticamente `trace_id` e `span_id` do contexto OTel ativo, para que eu possa navegar bidireccionalmente entre logs e traces — dado um log, abrir o trace; dado um trace, encontrar os logs.

**Why this priority**: Correlação é o mecanismo que conecta o mundo dos logs (stdout/JSON) com o mundo dos traces (Phoenix UI). Sem ela, os dois sistemas são ilhas isoladas e o valor do tracing cai pela metade.

**Independent Test**: Pode ser testado verificando que qualquer request ao API gera logs JSON com campos `trace_id` e `span_id` preenchidos, e que esses IDs correspondem a traces válidos no Phoenix.

**Acceptance Scenarios**:

1. **Given** uma requisição HTTP processada pelo FastAPI, **When** o `structlog` emite um event, **Then** o event dict contém `trace_id` (32 hex chars) e `span_id` (16 hex chars) do span ativo.
2. **Given** um `trace_id` de um log, **When** o operador busca no Phoenix, **Then** encontra o trace correspondente com spans da mesma requisição.
3. **Given** que não há span OTel ativo (ex: log emitido fora de contexto de request), **When** o `structlog` emite um event, **Then** `trace_id` e `span_id` não estão presentes (sem valores falsos ou zerados).

---

### User Story 3 - Trace Contínuo no Debounce (Priority: P1)

Como operador, quero que quando múltiplas mensagens rápidas do mesmo remetente sejam agrupadas pelo debounce, o trace resultante seja **contínuo** — mostrando todos os appends individuais e o flush final como spans de uma mesma árvore — para entender exatamente o que aconteceu no agrupamento.

**Why this priority**: O debounce é o componente mais complexo do pipeline (async, Redis keyspace notifications, delay configurável). Sem trace contínuo, a jornada "fica cortada" no append e recomeça no flush, impossibilitando correlação e diagnóstico de problemas de timing.

**Independent Test**: Pode ser testado enviando 3 mensagens rápidas para o mesmo remetente e verificando no Phoenix que existe 1 trace com 3 sub-spans de `debounce.append` e 1 span de `debounce.flush` conectados na mesma árvore.

**Acceptance Scenarios**:

1. **Given** 3 mensagens enviadas em sequência rápida para o mesmo número, **When** o debounce agrupa e faz flush, **Then** o Phoenix mostra 1 trace contínuo com 3 spans `debounce.append` e 1 span `debounce.flush` na mesma árvore.
2. **Given** propagação W3C Trace Context via payload Redis, **When** o flush handler recebe o callback, **Then** o span do flush é filho do contexto original do primeiro webhook (não é um trace novo). Appends subsequentes (2º e 3º) são registrados como OTel Links no span de flush (padrão OTel para message batching).
3. **Given** payloads legacy (sem `trace_context`), **When** o flush handler processa, **Then** o sistema cria um novo trace (degradação graciosa, sem erro).
4. **Given** 3 mensagens de remetentes diferentes em sequência, **When** cada uma gera seu próprio debounce buffer, **Then** cada flush gera um trace independente (sem mistura de contextos entre remetentes).

---

### User Story 4 - Dashboards Operacionais (Priority: P2)

Como operador do ProsauAI, quero acessar 5 dashboards curados no Phoenix UI — jornada por trace_id, funil por rota, latência por span (p50/p95/p99), failure modes, e saúde do debounce — para ter visibilidade contínua do comportamento do sistema sem precisar escrever queries ad-hoc.

**Why this priority**: Dashboards transformam dados brutos de traces em inteligência operacional acionável. Sem eles, o Phoenix é apenas um repositório de spans — útil para debug pontual, mas não para monitoramento contínuo.

**Independent Test**: Pode ser testado acessando `http://localhost:6006` após `docker compose up`, verificando que os 5 dashboards carregam e exibem dados de traces reais.

**Acceptance Scenarios**:

1. **Given** traces armazenados no Phoenix, **When** o operador acessa o dashboard "Funil por Rota", **Then** vê a distribuição de mensagens por `MessageRoute` (ECHO, AGENT, IGNORED, etc.) com contagens.
2. **Given** traces com timings variados, **When** o operador acessa o dashboard "Latência por Span", **Then** vê p50, p95 e p99 por tipo de span (webhook, route, debounce, echo).
3. **Given** traces com erros, **When** o operador acessa o dashboard "Failure Modes", **Then** vê agregação de falhas por tipo (HMAC inválido, malformed payload, Redis indisponível, Evolution API 5xx) com contagem, last_seen e link para sample trace.

---

### User Story 5 - Stack Único com Docker Compose (Priority: P2)

Como desenvolvedor, quero que `docker compose up` suba o Phoenix junto com `prosauai-api` e `redis` automaticamente, para que a observabilidade esteja sempre disponível sem configuração extra — cultura "observability is part of the product".

**Why this priority**: Se o Phoenix não sobe automaticamente, devs vão debugar sem ele. A barreira de ativação precisa ser zero para que a observabilidade se torne hábito, não exceção.

**Independent Test**: Pode ser testado executando `docker compose up` em ambiente limpo e verificando que os 3 containers (api, redis, phoenix) sobem e ficam healthy em menos de 60 segundos, com Phoenix UI acessível em `:6006`.

**Acceptance Scenarios**:

1. **Given** um clone limpo do repositório com `.env` configurado, **When** executo `docker compose up`, **Then** os 3 containers (prosauai-api, redis, phoenix) sobem e atingem status healthy em menos de 60 segundos.
2. **Given** os containers rodando, **When** acesso `http://localhost:6006`, **Then** o Phoenix UI carrega e está funcional.
3. **Given** o container Phoenix, **When** verifico a persistência, **Then** os dados de traces sobrevivem a um `docker compose restart` (volume nomeado).

---

### User Story 6 - Forward-Compat para LLM Tracing (Priority: P3)

Como arquiteto, quero que os spans já incluam atributos placeholder do namespace `gen_ai.*` (OTel GenAI Semantic Conventions), para que quando o epic 003 (Conversation Core) introduzir LLMs reais, a instrumentação existente aceite os novos atributos sem refactor.

**Why this priority**: Forward-compat é investimento de baixo custo agora (atributos placeholder) que evita refactor significativo depois. Não é urgente para o MVP mas é disciplina arquitetural.

**Independent Test**: Pode ser testado verificando que spans de echo possuem `gen_ai.system="echo"` e que o código de conventions.py tem constantes `GEN_AI_*` definidas.

**Acceptance Scenarios**:

1. **Given** uma mensagem processada pela rota ECHO, **When** o span de `_send_echo` é criado, **Then** contém atributo `gen_ai.system="echo"` como placeholder.
2. **Given** o módulo `conventions.py`, **When** inspecionado, **Then** contém constantes para `GEN_AI_SYSTEM`, `GEN_AI_REQUEST_MODEL` e outros atributos GenAI reservados para epic 003.

---

### User Story 7 - D0: Sync Documental (Priority: P1)

Como mantenedor da documentação, quero que as 12 propostas de atualização pendentes do reconcile do epic 001 sejam aplicadas aos 4 documentos afetados (`solution-overview.md`, `blueprint.md`, `containers.md`, `platform.yaml`), para que a documentação reflita a realidade entregue antes de começar a implementação do epic 002.

**Why this priority**: Documentação desatualizada (drift score 60%) compromete a integridade de todas as decisões arquiteturais subsequentes. D0 é pré-requisito lógico para implementação.

**Independent Test**: Pode ser testado verificando que os 4 docs refletem as entregas do epic 001 e que um reconcile subsequente retorna drift score 0% para os itens D0.

**Acceptance Scenarios**:

1. **Given** as propostas D1.1, D1.2, D1.3 pendentes, **When** aplicadas, **Then** `solution-overview.md` reflete as features entregues no epic 001.
2. **Given** a proposta D2.1 pendente, **When** aplicada, **Then** `blueprint.md` §3 (folder structure) reflete a estrutura real do código.
3. **Given** a proposta D3.1 pendente, **When** aplicada, **Then** `containers.md` possui seção "Implementation Status" com status real dos containers.
4. **Given** a proposta D6.4, **When** verificada, **Then** `platform.yaml` lifecycle reflete o estágio atual.

---

### Edge Cases

- O que acontece se o Phoenix estiver indisponível (container down)? O API continua funcionando normalmente — o exporter OTel falha silenciosamente (fire-and-forget), sem impacto nas requisições.
- O que acontece se o Redis estiver indisponível durante propagação de trace context? O debounce falha (comportamento existente do epic 001), e o trace registra o erro no span do append.
- O que acontece com payloads Redis legacy (sem `trace_context`)? Degradação graciosa — o flush handler cria um novo trace em vez de continuar um existente.
- O que acontece se o `structlog` emitir log fora de contexto OTel (ex: startup)? O processor simplesmente não adiciona `trace_id`/`span_id` — sem erro, sem valores zerados.
- O que acontece se o sampling filtrar um trace? Spans não são exportados ao Phoenix, mas o código continua executando normalmente. Logs ainda contêm `trace_id` (mesmo que o trace não exista no Phoenix).
- O que acontece se atributos PII forem acidentalmente adicionados a um span? O CI lint check (grep/ruff rule) detecta `phone` cru ou `text` raw em código de spans e falha o build.
- O que acontece com hot reload do uvicorn em dev? O SDK OTel pode ser reinicializado múltiplas vezes, gerando warnings. Documentação orienta aceitar warnings em dev ou desabilitar OTel condicionalmente.
- O que acontece quando múltiplas mensagens rápidas chegam com trace contexts diferentes? O primeiro contexto vira parent do flush span; os demais são registrados como OTel Links no span de flush (padrão OTel para message batching). Cada remetente distinto mantém buffers e traces separados.
- O que acontece em testes? O OTel SDK é desabilitado via `OTEL_SDK_DISABLED=true` (no-op TracerProvider). Testes que validam spans usam `InMemorySpanExporter` como fixture — sem dependência de Phoenix real.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE instrumentar automaticamente FastAPI, httpx e redis-py via auto-instrumentation OTel ao iniciar.
- **FR-002**: O sistema DEVE criar spans manuais nos pontos de domínio: `webhook_whatsapp`, `route_message`, `debounce.append`, `debounce.flush_handler`, `_send_echo`.
- **FR-003**: O sistema DEVE propagar W3C Trace Context (`traceparent` + `tracestate`) no payload Redis do DebounceManager para garantir trace contínuo entre append e flush. Quando múltiplas mensagens chegam para o mesmo buffer, o contexto do PRIMEIRO append vira parent do flush span; appends subsequentes são registrados como OTel Links.
- **FR-004**: O sistema DEVE injetar `trace_id` e `span_id` automaticamente em todo event do `structlog` quando houver span OTel ativo.
- **FR-005**: O sistema DEVE exportar spans para Phoenix via OTLPSpanExporter (HTTP) configurado via `settings.phoenix_endpoint`.
- **FR-006**: O sistema DEVE incluir atributos obrigatórios em todo span: `tenant_id`, `service.name`, `service.version`, `deployment.environment`.
- **FR-007**: O sistema DEVE incluir atributos de domínio nos spans relevantes: `prosauai.route`, `prosauai.phone_hash`, `prosauai.is_group`, `prosauai.from_me`, `messaging.system`, `messaging.message.id`.
- **FR-008**: O sistema DEVE suportar sampling head-based configurável via variável de ambiente `OTEL_TRACES_SAMPLER_ARG` (default: 1.0 em dev, 0.1 em prod).
- **FR-009**: O sistema NUNCA DEVE incluir PII em atributos de span — telefone sempre como `phone_hash` (SHA-256 truncado 12 chars), nunca texto raw da mensagem, nunca payload raw da Evolution API.
- **FR-010**: O container Phoenix DEVE subir automaticamente via `docker compose up` com volume persistente e healthcheck.
- **FR-011**: O Phoenix DEVE armazenar dados no Supabase Postgres usando schema dedicado `observability`.
- **FR-012**: O sistema DEVE fornecer 5 dashboards curados no Phoenix, documentados como SpanQL queries versionadas em `phoenix-dashboards/README.md`: (a) jornada por trace_id, (b) funil por rota, (c) latência p50/p95/p99, (d) failure modes, (e) saúde do debounce. Phoenix OSS não suporta export/import de dashboards — queries são documentação para recriação manual.
- **FR-013**: O endpoint `/health` DEVE estender o `HealthResponse` existente com campo `observability: {status: "ok"|"degraded", last_export_success: bool}`. O status OTel degradado NÃO causa HTTP 503 — observabilidade é não-crítica para o funcionamento do API.
- **FR-014**: O sistema DEVE suportar payloads Redis legacy (sem `trace_context`) com degradação graciosa — novo trace em vez de trace contínuo.
- **FR-015**: O sistema DEVE incluir atributos placeholder `gen_ai.system="echo"` nos spans de echo para forward-compat com epic 003.
- **FR-016**: O Lua script do DebounceManager DEVE aceitar payload JSON `{text, trace_context}` mantendo retrocompatibilidade com payload `text` standalone.
- **FR-017**: As 12 propostas de atualização documental pendentes do reconcile do epic 001 DEVEM ser aplicadas como D0 (4 docs: `solution-overview.md`, `blueprint.md`, `containers.md`, `platform.yaml`).
- **FR-018**: O ADR-020 (Phoenix substitui LangFuse v3) DEVE ser publicado, marcando ADR-007 como `Superseded by ADR-020`.
- **FR-019**: O OTel SDK DEVE ser desabilitável em testes via env var `OTEL_SDK_DISABLED=true` (no-op TracerProvider). Testes que assertam estrutura de spans DEVEM usar `InMemorySpanExporter` como fixture pytest.
- **FR-020**: A versão do Phoenix DEVE ser pinada: `arize-phoenix[pg]>=8.0,<9.0` no `pyproject.toml` e Docker image com tag correspondente no `docker-compose.yml`.

### Key Entities

- **Trace**: Representa a jornada completa de uma mensagem — do webhook ao echo. Identificado por `trace_id` (32 hex chars). Composto por múltiplos spans hierárquicos.
- **Span**: Unidade de trabalho dentro de um trace — cada etapa do pipeline (webhook, route, debounce.append, debounce.flush, echo) é um span com nome, duração, atributos e status.
- **SpanAttributes**: Conjunto de metadados anexados a cada span — atributos OTel padrão (`service.name`, `tenant_id`) + namespace custom `prosauai.*` (route, phone_hash, debounce metrics) + namespace reservado `gen_ai.*`.
- **W3C Trace Context Carrier**: Payload JSON contendo `traceparent` + `tracestate`, propagado junto do texto da mensagem no buffer Redis para reconectar trace entre append e flush.
- **Dashboard**: Visualização curada no Phoenix UI que agrega dados de traces para responder perguntas operacionais específicas (funil, latência, falhas, saúde do debounce).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operador consegue visualizar a jornada completa de uma mensagem (7+ spans) no Phoenix em menos de 30 segundos após o envio.
- **SC-002**: `docker compose up` sobe os 3 containers (api, redis, phoenix) e todos atingem status healthy em menos de 60 segundos.
- **SC-003**: Phoenix UI acessível em `http://localhost:6006` sem configuração adicional.
- **SC-004**: 3 mensagens rápidas no debounce resultam em 1 trace contínuo com 3 sub-spans append e 1 span flush na mesma árvore.
- **SC-005**: `grep trace_id=<X>` nos logs do container retorna todas as linhas estruturadas daquela jornada (correlação 100%).
- **SC-006**: 5 dashboards funcionais no Phoenix exibindo dados reais de traces.
- **SC-007**: Zero atributos de span contendo `phone` cru, `text` raw ou payload Evolution raw (validado por lint check no CI).
- **SC-008**: Overhead de latência p95 do webhook < 5ms comparado ao baseline do epic 001.
- **SC-009**: Suite de testes com 130+ testes passando (122 existentes + 8+ novos de observability) e `ruff check .` com zero erros.
- **SC-010**: Spans de echo contêm `gen_ai.system="echo"` placeholder verificável (forward-compat para epic 003).
- **SC-011**: 4 documentos atualizados (D0) com drift score do epic 001 reduzido a 0%.
- **SC-012**: ADR-020 publicado e ADR-007 marcado como superseded.

## Clarifications

### Session 2026-04-10

- Q: Quando 3 mensagens rápidas chegam com 3 trace contexts diferentes, qual contexto se torna parent do span de flush? → A: Primeiro contexto vira parent; appends subsequentes adicionam OTel Links (padrão OTel para message batching).
- Q: Como o OTel SDK é desabilitado em testes para evitar ruído do exporter? → A: No-op TracerProvider via pytest fixture + env var `OTEL_SDK_DISABLED=true`. Testes que assertam spans usam InMemorySpanExporter.
- Q: Como o `/health` existente (retorna `{status, redis}`) incorpora status do OTel exporter? → A: Novo campo `observability: {status: "ok"|"degraded", last_export_success: bool}` no HealthResponse. Nunca retorna 503 por falha OTel (não-crítico).
- Q: Qual versão do Phoenix deve ser pinada? → A: `arize-phoenix[pg]>=8.0,<9.0` (latest stable com Postgres backend). Docker image pinada no tag correspondente.
- Q: Dashboards são exportados como JSON importável ou documentados como queries? → A: Documentados como SpanQL queries em `phoenix-dashboards/README.md` (version-controlled). Phoenix OSS não tem API de export/import de dashboards — queries são documentação, não artefato importável.

## Assumptions

- O cluster Docker local tem recursos suficientes para rodar 3 containers simultaneamente (~2GB RAM total: api + redis + phoenix).
- O Supabase Postgres aceita criação de schema customizado (`observability`) e o usuário tem permissão `CREATE SCHEMA`.
- O volume de mensagens atual é suficientemente baixo para sampling 100% em dev sem impacto de storage.
- A versão do Phoenix OSS suporta backend Postgres (pinada: `arize-phoenix[pg]>=8.0,<9.0` com `PHOENIX_SQL_DATABASE_URL`).
- Os testes existentes (122) do epic 001 continuam passando sem modificação após a instrumentação OTel (overhead desprezível em test mode).
- A Evolution API (provider WhatsApp) não modifica headers de resposta de forma que quebre a auto-instrumentation do httpx.
- O Redis keyspace notifications está habilitado (configuração do epic 001) e suporta payloads JSON expandidos sem limite de tamanho relevante (< 1KB por mensagem).
- O `structlog` é compatível com processors customizados que acessam o contexto OTel via `opentelemetry.trace.get_current_span()`.
- Hot reload do uvicorn em dev pode gerar warnings de reinicialização do OTel SDK — comportamento aceito (não é bug, é limitação conhecida).
- Phoenix UI não tem autenticação nativa robusta — em dev é localhost only; staging/prod exigirá reverse proxy com auth (fora do escopo deste epic).

---
handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada com 5 resoluções: (1) debounce multi-context usa primeiro parent + OTel Links, (2) testes via no-op TracerProvider + InMemorySpanExporter, (3) /health estende HealthResponse com campo observability não-crítico, (4) Phoenix pinado >=8.0,<9.0, (5) dashboards como SpanQL queries documentadas (sem export API). 20 FRs, 12 SCs. Pronta para planning."
  blockers: []
  confidence: Alta
  kill_criteria: "Se Phoenix >=8.0 não suportar Postgres backend, ou se OTel auto-instrumentation for incompatível com FastAPI lifespan tasks, a abordagem precisa ser revisada."
