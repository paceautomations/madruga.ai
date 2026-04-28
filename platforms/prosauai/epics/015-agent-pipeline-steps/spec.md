# Feature Specification: Agent Pipeline Steps — sub-routing configurável por agente

**Feature Branch**: `epic/prosauai/015-agent-pipeline-steps`
**Created**: 2026-04-27
**Status**: Clarified
**Input**: Hoje cada agente da plataforma ProsaUAI executa como **uma única chamada LLM** (`generate_response()` no step 10 do pipeline de conversa). Esse modelo monolítico funciona bem para casos triviais ("Quem é o líder do ranking?"), mas falha quando: (a) a mensagem do cliente tem intenção ambígua e o agente "chuta" o domínio errado; (b) o agente generalista precisa simultaneamente entender contexto, escolher tool e responder com tom específico — tudo no mesmo prompt mega; (c) intenções diferentes deveriam invocar prompts/modelos diferentes ("billing" exige `gpt-5` cuidadoso, "saudação" pode usar `gpt-5-nano` barato). Este épico introduz **pipeline steps configuráveis por agente** (classifier → clarifier → resolver → specialist → summarizer), persistidos como dados (`agent_pipeline_steps` table — schema já definido em `domain-model.md` linha 244 e ADR-006). Comportamento atual permanece intacto: agentes **sem** steps continuam executando como single LLM call (zero deploy, zero regressão). Agentes **com** steps configurados executam cada step em sequência, encadeando outputs e podendo desviar de fluxo via `condition`.

## Clarifications

### Session 2026-04-27

Autonomous dispatch mode — decisões tomadas pelo agente seguindo o princípio "simplest thing that works" e priorizando previsibilidade operacional. Cada item está marcado `[DECISAO AUTONOMA]` para auditoria; um override humano via `decisions.md` durante implementação é o caminho normal de revisão.

- Q: Quais operadores são suportados pelo avaliador de `condition` JSONB e como múltiplas chaves se combinam? → A: Operadores suportados na v1 — `<`, `>`, `<=`, `>=`, `==`, `!=`, `in`. Sintaxe canônica `{"caminho.para.valor": "<operador><literal>"}` (ex: `{"classifier.confidence": "<0.6"}`, `{"classifier.intent": "==billing"}`, `{"classifier.intent": "in [billing,ranking_query]"}`). Múltiplas chaves no mesmo objeto JSON combinam por **AND implícito**. **Não há OR nem parênteses na v1** — para lógica disjunta, criar dois steps com condições mutuamente exclusivas (ex: dois `specialists` consecutivos, cada um com sua condição). `[DECISAO AUTONOMA]`
- Q: Qual a política de retry/fallback quando um step intermediário falha (timeout, erro de provider, parse de output)? → A: **Zero retry no v1**. Falha de qualquer step → marcar como erro no trace, marcar steps subsequentes como `skipped`, entregar a `FALLBACK_MESSAGE` canned PT-BR ao cliente (mesmo mecanismo do step 10 atual). Justificativa: previsibilidade de latência (sem timeouts cumulativos) e simplicidade de raciocínio. Retry inteligente fica como follow-up se métricas de produção justificarem. `[DECISAO AUTONOMA]`
- Q: Como o output do step `summarizer` é injetado nos steps subsequentes — substitui ou prepende ao histórico de mensagens? → A: **Substitui** o histórico longo no `pipeline_state` consumido pelos steps subsequentes (campo `summarized_context: str`). Os registros brutos em `messages` permanecem intactos para auditoria — o summarizer só afeta o que vai para o prompt dos steps seguintes. Justificativa: o objetivo do summarizer é REDUZIR token count; prepender duplicaria contexto e neutralizaria o ganho de custo. `[DECISAO AUTONOMA]`
- Q: O limite de 5 steps por agente é hard-coded ou configurável por tenant na v1? → A: **Hard-coded em 5 na v1**, igual para todos os tenants. Valor implementado como constante `MAX_PIPELINE_STEPS_PER_AGENT = 5` no validador do INSERT. Se um caso real legítimo exigir 6+ steps, abre-se uma decisão dedicada (ADR ou ajuste de constante via PR), não config dinâmica por tenant. Justificativa: configuração ajustável por tenant adiciona surface de erro sem benefício comprovado; 5 cobre todos os casos identificados em discovery. `[DECISAO AUTONOMA]`
- Q: Onde ficam armazenados os filtros `terminating_step` e `pipeline_version` referenciados em US5 e FR-062? → A: `messages.metadata` JSONB (campo existente, sem mudança de schema): `{"terminating_step": "clarifier", "pipeline_version": "<agent_config_version_id>", "pipeline_step_count": 3}`. O Trace Explorer (épico 008) lê `agent_version_id` da tabela `trace_steps` (já presente) para o filtro `pipeline_version`, e lê `output.terminating_step` do trace step `generate_response` (também já presente como JSONB) para o filtro `terminating_step`. **Zero novas colunas** em `messages`, `traces` ou `trace_steps`. Justificativa: aproveita schema existente, evita migrations adicionais, reduz acoplamento com épico 008. `[DECISAO AUTONOMA]`

## User Scenarios & Testing *(mandatory)*

<!--
  Stories priorizadas por valor de negócio. Cada uma é independentemente testável.
  P1 = MVP (executor de pipeline + 1-2 step types). P2 = step types adicionais + admin UI.
  P3 = recursos avançados (conditions, A/B canary por step).
-->

### User Story 1 — Reduzir custo do agente generalista usando classifier barato + specialist alvo (Priority: P1)

Um engenheiro de prompt observa que o agente padrão do tenant `pace-internal` (Ariel Bot) processa **todas** as mensagens — incluindo saudações triviais ("oi", "bom dia", "obrigado") — usando `gpt-5-mini` com system prompt de 4 KB e 6 tools habilitadas. Custo médio: USD 0.0042 por mensagem; latência média: 1.8 s. Hoje 38% das mensagens são triviais e não precisam desse aparato. Com pipeline steps, ele configura no admin do agente Ariel: **step 1** (classifier, modelo `gpt-5-nano`, prompt curto "classifique a intent em uma de: greeting, simple_query, billing, ranking_query, complex") seguido de **step 2** (specialist, modelo dependendo da classificação — `gpt-5-nano` para greeting/simple_query, `gpt-5-mini` para billing/ranking_query/complex). Resultado esperado: custo médio cai para USD 0.0018 (-57%) e latência para 0.9 s nos casos triviais.

**Why this priority**: dor financeira concreta e mensurável (custo unitário e latência são tracked em produção desde épico 002). É o caso mais simples, com payoff imediato e independente de mudanças no admin UI (config inicial pode ser feita via SQL direto pelo time de engenharia). Sem este step type funcionando ponta-a-ponta, nada no épico tem valor.

**Independent Test**: o engenheiro consegue, via SQL direto na tabela `agent_pipeline_steps`, configurar 2 steps para um agente de teste (classifier + specialist) e processar 20 mensagens reais (greetings + billing) com o pipeline encadeando os steps corretamente. As mensagens classificadas como `greeting` usam `gpt-5-nano` no specialist (verificável em `messages.metadata.model_used`), enquanto as classificadas como `billing` usam `gpt-5-mini`. Custo médio das `greeting` cai pelo menos 50% comparado à execução atual.

**Acceptance Scenarios**:

1. **Given** um agente `ariel-test` configurado com 2 pipeline steps (step 1: classifier `gpt-5-nano` com 5 intent labels; step 2: specialist com mapping `intent → model`), **When** uma mensagem `"oi tudo bem?"` é processada pelo pipeline de conversa, **Then** o trace persistido em `traces`/`trace_steps` (épico 008) mostra 2 sub-spans dentro do step 10 (`generate_response`), o classifier retorna `intent="greeting"` e o specialist usa `gpt-5-nano` para gerar a resposta final.
2. **Given** o mesmo agente, **When** uma mensagem `"qual a fatura desse mês?"` chega, **Then** o classifier retorna `intent="billing"` e o specialist é executado com `gpt-5-mini` (modelo configurado para `billing` no `routing_map`).
3. **Given** um agente `ariel-baseline` **sem** pipeline steps configurados, **When** uma mensagem chega, **Then** o pipeline executa exatamente como hoje (single LLM call em `generate_response()`), sem mudança de comportamento, latência ou custo observável (regressão zero).
4. **Given** o classifier retorna uma intent fora do mapeamento configurado (ex: `"unknown"` enquanto o `routing_map` só tem `greeting`/`billing`/`ranking_query`/`complex`), **When** o specialist precisa decidir o modelo, **Then** o sistema usa o `default_model` declarado no step config como fallback — sem erro, sem fallback canned.
5. **Given** 1000 mensagens reais reprocessadas em staging com o agente Ariel ativo (com pipeline) vs. baseline (sem pipeline), **When** os custos são agregados, **Then** o custo total da configuração com pipeline é **pelo menos 30% menor** que o baseline e o quality score médio cai no máximo 0.05 pontos (aceitável dada a economia).

---

### User Story 2 — Desambiguar pedidos vagos antes de gerar resposta cara (Priority: P1)

Um operador analisa relatórios semanais e nota que 14% das conversas têm o cliente reformulando a pergunta logo após a primeira resposta do bot ("não, não foi isso que perguntei", "eu queria saber sobre X, não Y"). O problema raiz: o LLM resolve cedo demais sobre uma interpretação errada de mensagens curtas e ambíguas ("e o jogo de ontem?", "manda aí"). Com pipeline steps, o engenheiro adiciona um step **clarifier** entre classifier e specialist: se o classifier retorna `confidence < 0.6` ou intent `ambiguous`, o clarifier (modelo `gpt-5-nano`, prompt "elabore uma pergunta curta para esclarecer a intenção do usuário") gera uma pergunta de esclarecimento que vai direto pro cliente, **pulando** os steps subsequentes (RESPOND com texto do clarifier). Assim, o agente gasta uma chamada barata para confirmar entendimento em vez de uma chamada cara que erra.

**Why this priority**: ataca diretamente uma métrica de qualidade (taxa de retomadas). Lança mão da feature `condition` (campo JSONB já presente no schema). Tem impacto compound — qualquer agente generalista pode adotar o padrão. P1 porque, junto com US1, fecha os dois usos mais óbvios e dá densidade de adoção no v1.

**Independent Test**: o engenheiro configura 3 steps (classifier + clarifier + specialist) com `condition` no clarifier `{"classifier.confidence": "<0.6"}`. Processando uma mensagem ambígua ("e ai"), o trace mostra que o classifier executou, o clarifier executou (porque a condição matchou) e o specialist **não** executou (foi pulado). A resposta entregue ao cliente é o output do clarifier (uma pergunta).

**Acceptance Scenarios**:

1. **Given** um agente com 3 steps (classifier, clarifier com `condition: {"classifier.confidence": "<0.6"}`, specialist), **When** uma mensagem ambígua produz `confidence=0.4`, **Then** o clarifier executa, gera "Você pode me dar mais contexto sobre o que precisa?" e o specialist é marcado como `skipped` no trace (sem cobrança de tokens).
2. **Given** o mesmo agente, **When** o classifier retorna `confidence=0.92`, **Then** o clarifier é `skipped` e o specialist executa normalmente.
3. **Given** o clarifier executa e seu output é a resposta final, **When** o pipeline grava o `messages` outbound, **Then** o campo `messages.metadata.terminating_step` registra `"clarifier"` para auditoria.
4. **Given** uma condição mal-formada (chave inexistente, ex: `{"classifier.foo": "<0.6"}`), **When** o pipeline avalia a condição, **Then** o sistema **não trava** — a condição é tratada como `false` (step não executa) e um warning é logado uma vez por agente/step (não a cada execução, para não floodar os logs).

---

### User Story 3 — Configurar pipeline de um agente pelo admin sem SQL (Priority: P2)

Um engenheiro de prompt quer experimentar uma terceira variação: adicionar um **summarizer** após N mensagens da conversa, para encolher o context window e reduzir custo. Hoje, configurar pipeline steps exige SQL direto (que produto/ops não tem permissão para executar). Com a UI de Agentes do admin (épico 008, aba Agentes/Configuração), aparece uma sub-seção **Pipeline Steps** mostrando os steps atuais em ordem, com ações para: adicionar step (escolher tipo entre classifier/clarifier/resolver/specialist/summarizer), reordenar (drag-and-drop ou up/down), editar config (modelo, prompt slug, tools, threshold) e excluir. Mudanças passam pelo mesmo workflow de versionamento de agente (`agent_config_versions`, ADR-019) — gerar nova versão, ativar via diff visual, rollback imediato em caso de regressão.

**Why this priority**: democratiza a feature, mas o workflow operacional sobrevive sem a UI durante o roll-out inicial (engenharia configura para os primeiros 3 agentes via SQL). P2 porque depende de mudanças coordenadas no admin (épico 008) e UX precisa ser polida para evitar config quebrado.

**Independent Test**: um engenheiro de prompt, sem acesso ao banco, consegue adicionar um step `summarizer` no fim do pipeline do agente Ariel via UI, configurar `condition: {"context.message_count": ">15"}` e confirmar que a próxima mensagem nessa conversa dispara a sumarização. A versão do agente avança em 1 (`active_version_id` aponta para a nova versão) e o `audit_log` registra a mudança com email do operador.

**Acceptance Scenarios**:

1. **Given** o admin abre a aba Agentes → Ariel Bot → Configuração, **When** a sub-seção Pipeline Steps renderiza, **Then** ele vê a lista ordenada de steps existentes (label, tipo, modelo, condições resumidas) com botões "Adicionar step", "Editar", "Reordenar", "Remover".
2. **Given** o admin clica em "Adicionar step" e seleciona tipo `summarizer`, **When** o formulário renderiza, **Then** apenas os campos relevantes ao tipo summarizer aparecem (modelo, prompt_slug, max_input_tokens, condition opcional) — sem campos de classifier (intent_labels) ou specialist (routing_map).
3. **Given** o admin salva a alteração, **When** o backend processa, **Then** uma nova `agent_config_versions` é criada com snapshot completo (incluindo o novo step), a versão antiga permanece como `archived`, e o admin vê a nova versão como `pending` até clicar em "Ativar".
4. **Given** o admin ativa a nova versão, **When** o roteador atende a próxima mensagem para o tenant, **Then** o pipeline já executa com a nova configuração (config hot reload — sem deploy).
5. **Given** uma config inválida é submetida (ex: step `specialist` sem `default_model`, `step_order` duplicado, `condition` com sintaxe quebrada), **When** o backend valida, **Then** retorna erro 422 com mensagem específica e a UI exibe em campo destacado — sem persistir a versão.
6. **Given** o admin descobre que a nova config piorou QS, **When** clica em "Rollback para versão anterior", **Then** a versão `active` reverte para a anterior em <1 s, sem perda de dados.

---

### User Story 4 — Comparar versões de pipeline lado-a-lado para decidir promoção (Priority: P2)

Após configurar pipeline (US3), o engenheiro de prompt quer evidência objetiva antes de promover a versão nova para 100% do tráfego. Com canary rollout per-version (ADR-019, mecanismo já existente para prompts/temperature), ele põe 10% do tráfego do agente Ariel na versão 5 (com pipeline) e 90% na versão 4 (single call), por 48 h. A aba Performance AI agrupa métricas **por versão** quando o agente está em canary: custo total por versão, QS médio, latência P95, fallback rate, distribuição de intents. Se a versão 5 entrega QS ≥ baseline e custo menor, ele promove para 100%; senão, rollback imediato.

**Why this priority**: amplifica o valor de US1/US2 ao permitir mudanças seguras. Reaproveita 100% do mecanismo de canary existente (sem nova UI complexa, apenas extensão de filtros). P2 porque a feature funciona sem ela (engenheiros podem comparar manualmente via SQL e Performance AI), mas sem ela o ciclo de iteração é lento.

**Independent Test**: o engenheiro coloca o agente Ariel em canary (v4=90%, v5=10%) por 48 h em staging com tráfego sintético controlado. Na aba Performance AI, ele consegue: (a) filtrar por agente Ariel + período "últimos 2 dias" + group_by `agent_version`; (b) ver 2 colunas com KPIs (QS, custo, latência) lado-a-lado; (c) ver intervalo de confiança ou pelo menos N de cada coluna. A decisão de promote/rollback é baseada nesses números — não em SQL ad-hoc.

**Acceptance Scenarios**:

1. **Given** o agente Ariel está em canary com v4 (single call) e v5 (pipeline), **When** o engenheiro abre `/admin/performance` com filtros tenant=`pace-internal` e agent=`ariel`, **Then** os KPI cards mostram um toggle "Group by version" que, ativado, divide os números entre v4 e v5 com a contagem de mensagens em cada.
2. **Given** o toggle está ativo, **When** os gráficos renderizam, **Then** os gráficos de tendência (QS, latência, custo) usam linhas distintas para v4 e v5, com legenda visível.
3. **Given** menos de 50 mensagens em uma das versões no período, **When** os KPIs renderizam, **Then** o card daquela versão mostra label `"insuficiente — N=42"` em vez de número, evitando decisões com amostra pequena (regra ADR-019, item 16 do domain-model `Minimum sample size`).
4. **Given** o engenheiro promove v5 para 100% via "Ativar versão", **When** o tráfego começa a fluir, **Then** v4 vai para `archived` e o toggle "Group by version" some da UI (pois só há uma versão ativa).

---

### User Story 5 — Auditar execução de pipeline step por step a partir do trace de uma conversa (Priority: P2)

Um engenheiro recebe um report: "a resposta do bot ao cliente João demorou 9 segundos e veio fora do contexto." Ele abre o Trace Explorer (épico 008), localiza o trace, e dentro do step `generate_response` (step 10) vê **sub-steps** correspondentes ao pipeline configurado: classifier (320 ms, output `intent=billing`), clarifier (skipped, condição não bateu), specialist (8.2 s, output texto). Ele identifica que a latência veio do specialist e que o classifier escolheu billing quando deveria ser ranking_query — o problema está no prompt do classifier, não no specialist. Sem essa visibilidade, a investigação levaria horas.

**Why this priority**: torna a feature debugável em produção. Sem ela, qualquer regressão produz reports do tipo "está mais lento" ou "está respondendo errado" sem qualquer pista do que está acontecendo entre os modelos. P2 porque inicialmente é possível debugar via logs estruturados (épico 002), mas o custo cognitivo é alto.

**Independent Test**: a partir de um `trace_id` de uma mensagem real processada com pipeline configurado, o engenheiro consegue, na página de detalhe do trace, expandir o step `generate_response` e ver N sub-steps (um por step do pipeline) com duração, modelo usado, tokens, input e output, em formato consistente com os outros 11 steps do pipeline principal.

**Acceptance Scenarios**:

1. **Given** um trace de uma mensagem processada com pipeline de 3 steps (classifier, clarifier, specialist), **When** o engenheiro abre a página de detalhe do trace e expande o step `generate_response`, **Then** ele vê 3 sub-rows (um por step do pipeline) com mesma estrutura visual dos outros steps top-level: barra de duração, status, accordion expansível com input/output/modelo/tokens.
2. **Given** um step foi `skipped` (condição não bateu), **When** ele renderiza, **Then** aparece com estilo visual de inatividade, label "skipped" e texto curto explicando o motivo (ex: `"condition: classifier.confidence >= 0.6 (got 0.92)"`).
3. **Given** um step falhou (timeout, erro de provider), **When** o trace renderiza, **Then** o step com erro tem destaque visual, e os steps subsequentes aparecem como `skipped` (sem chamada extra ao LLM) — o specialist nunca é chamado se o classifier falhou.
4. **Given** o engenheiro filtra a lista de traces por `pipeline_version=v5` ou por `terminating_step=clarifier`, **When** a lista recarrega, **Then** apenas os traces que matcham os filtros aparecem.

---

### User Story 6 — Operação default unchanged: agentes sem pipeline continuam single-call (Priority: P1)

Todos os ~6 tenants ativos hoje rodam com agentes em modo single LLM call. Nenhum deles deve ser obrigado a migrar para pipeline. Quando este épico shippa, o comportamento default de qualquer agente recém-criado **continua sendo single call** (zero pipeline steps configurados). O time de produto adiciona pipeline gradualmente, agente por agente, conforme decida que vale a pena.

**Why this priority**: invariante crítico de produção. Sem essa garantia, este épico é um risco enorme para todos os clientes ativos. Toda a base de testes existente (épicos 005, 004, 002) deve continuar passando sem alterações. P1 obrigatório.

**Independent Test**: rodar a suíte completa de testes existentes do prosauai (`apps/api/prosauai/tests/`) e verificar que 100% passa antes do merge. Adicionalmente, comparar A/B em staging: 1000 mensagens de produção real reprocessadas com o agente atual (sem pipeline) vs. agente atual com 0 steps configurados; resultados (QS, custo, latência, modelo usado, conteúdo gerado) devem ser **idênticos** dentro de margem ≤1% (excluindo variabilidade natural do LLM).

**Acceptance Scenarios**:

1. **Given** um agente com `pipeline_steps=[]` (zero steps), **When** uma mensagem é processada, **Then** o pipeline executa exatamente o `generate_response()` atual (sem código novo de orquestração ativado), sem latência adicional ≥5 ms (overhead da consulta `pipeline_steps WHERE agent_id=...` zeradinha).
2. **Given** a suíte de testes do prosauai (`pytest apps/api/prosauai/tests/`), **When** o épico é mergeado, **Then** 100% dos testes existentes passam sem modificação.
3. **Given** uma comparação em staging de 1000 mensagens reais reprocessadas (mesmas mensagens, mesmas seeds, mesmo agente sem pipeline), **When** os outputs são comparados, **Then** distribuição de QS, latência, custo e modelo usado são estatisticamente equivalentes ao baseline.
4. **Given** um operador remove acidentalmente todos os steps de um agente que tinha pipeline, **When** a próxima mensagem chega, **Then** o agente volta para single-call sem erro nem necessidade de restart.

---

### Edge Cases

- **Loop infinito teórico**: um step `clarifier` cuja condição sempre é true e cuja resposta sempre dispara reinício do classifier. **Mitigação**: pipeline executa cada step **no máximo 1 vez por mensagem do cliente**; não há retorno ao início do pipeline dentro de uma única chamada `process_conversation`.
- **Cadeia de steps muito longa**: pipeline com 8+ steps configurados (improvável, mas possível). **Mitigação**: limite hard de **5 steps por agente** validado no schema; tentativas de inserir o 6º falham com 422 e mensagem clara.
- **Step config gigante**: `config` JSONB com 100 KB de prompt embedded. **Mitigação**: limite de 16 KB por step (prompt deve referenciar `prompt_slug` em vez de embutir texto); validação no INSERT.
- **Output de step não-JSON-parseable quando o próximo step espera JSON**: classifier retorna texto livre quando deveria retornar `{"intent": ..., "confidence": ...}`. **Mitigação**: schema de output esperado declarado no `config` do step; falha de parse marca o step como erro, logs estruturados, e os subsequentes fazem `skip` — sem crash do pipeline.
- **Ciclo concorrente em hot-reload**: um operador edita o agente enquanto uma mensagem está sendo processada — a thread em curso continua usando a versão antiga, a próxima mensagem usa a nova. **Mitigação**: snapshot da config (incluindo pipeline steps) é capturado **uma vez** no início do `process_conversation` (step 6 `build_context` ou similar) e referenciado por toda a execução; hot reload afeta só a próxima invocação.
- **Tool call no specialist ainda demora muito**: pipeline ajuda no roteamento, mas se o specialist final ainda usa `gpt-5` e chama 3 tools custosas (asyncpg query a ResenhAI), latência total continua alta. **Mitigação**: este épico **não** ataca latência de tools (escopo é orquestração entre LLM calls); recomenda como follow-up usar `tools_enabled` per-step.
- **Cenário multi-tenant misturado**: tenant A migra para pipeline, tenant B mantém single-call. **Mitigação**: configuração é por agente (e o agente é por tenant via FK); 100% isolado.
- **Pipeline com classifier sem specialist subsequente**: configuração inválida (classifier sem nada a seguir produz output que não vira mensagem). **Mitigação**: validação no schema — todo pipeline DEVE terminar em um step que produz texto (specialist, resolver, clarifier).
- **Race entre versão canary e ativação**: durante canary 90/10 v4/v5, o operador clica em "Ativar v5". **Mitigação**: ação de Ativar transiciona explícita e atomicamente — v4 vai para archived, v5 para active, traffic_pct=100 (mecanismo ADR-019 já existente).

## Requirements *(mandatory)*

### Functional Requirements

**Schema e dados**

- **FR-001**: O sistema MUST persistir, por agente, uma sequência ordenada de pipeline steps na tabela `agent_pipeline_steps` (schema já em `domain-model.md` linha 244): `id`, `tenant_id` (FK), `agent_id` (FK), `step_order` (INT, único por agente), `step_type` (ENUM: `classifier|clarifier|resolver|specialist|summarizer`), `config` (JSONB), `condition` (JSONB nullable), `is_active` (BOOL), timestamps.
- **FR-002**: O sistema MUST validar que `(agent_id, step_order)` é único — não permitir 2 steps com a mesma ordem para o mesmo agente.
- **FR-003**: O sistema MUST limitar o número total de steps por agente a no máximo **5** via constante `MAX_PIPELINE_STEPS_PER_AGENT = 5` (hard-coded, **não configurável por tenant na v1** — ver Clarifications 2026-04-27); tentativas de inserir o 6º step retornam erro 422.
- **FR-004**: O sistema MUST limitar o tamanho da coluna `config` por step a no máximo **16 KB**; tentativas acima retornam erro 422 com indicação para usar `prompt_slug` em vez de embutir texto.
- **FR-005**: A coluna `agent_pipeline_steps` MUST ter Row-Level Security ativada com policy de isolamento por `tenant_id` (consistente com todas as outras tabelas business).
- **FR-006**: O sistema MUST criar índices em `(agent_id, step_order)` e `(tenant_id)` para garantir lookup eficiente do pipeline durante o `process_conversation`.

**Tipos de step**

- **FR-010**: O sistema MUST suportar 5 tipos de step: `classifier`, `clarifier`, `resolver`, `specialist`, `summarizer`.
- **FR-011**: Step `classifier` MUST receber input do step anterior (ou `ConversationState` original se for o primeiro) e produzir output JSON estruturado com `intent` (string), `confidence` (float 0–1) e `explanation` (string opcional).
- **FR-012**: Step `clarifier` MUST receber o output do classifier (incluindo `confidence`) e produzir uma pergunta de esclarecimento como texto curto (≤140 chars) que vira a resposta final ao cliente, marcando `terminating_step="clarifier"` no trace.
- **FR-013**: Step `resolver` MUST resolver entidades / referências do contexto (ex: "o último jogo" → game_id concreto) usando tools habilitadas, produzindo um JSON estruturado com as entidades extraídas para consumo do specialist.
- **FR-014**: Step `specialist` MUST gerar a resposta final ao cliente (texto livre), usando modelo selecionável via `routing_map: {intent → model}` ou `default_model` quando o intent não está no mapping.
- **FR-015**: Step `summarizer` MUST receber as últimas N mensagens da conversa (configurável via `max_input_messages`, default 20) e produzir um resumo curto que **substitui** (não prepende) o histórico longo no `pipeline_state.summarized_context` consumido pelos steps subsequentes — ver Clarifications 2026-04-27. Os registros brutos em `messages` permanecem intactos. Usa modelo barato por padrão (`gpt-5-nano`).

**Execução**

- **FR-020**: O sistema MUST, ao processar uma mensagem, carregar os pipeline steps **uma vez** (snapshot atômico) no início do `process_conversation` para evitar inconsistência entre steps causada por hot reload concorrente.
- **FR-021**: Quando `agent_pipeline_steps` está vazio para o agente alvo, o pipeline MUST executar exatamente o comportamento atual de `generate_response()` — single LLM call — sem qualquer overhead observável (latência adicional ≤5 ms).
- **FR-022**: Quando há ≥1 step configurado, o sistema MUST executar steps em ordem `step_order ASC`, encadeando o output do step N como input do step N+1, com snapshot do `ConversationState` enriquecido a cada step.
- **FR-023**: Antes de executar um step, o sistema MUST avaliar a `condition` JSONB (quando presente). Condição truthy → step executa; falsy ou erro de avaliação → step é marcado `skipped` e não consome tokens.
- **FR-024**: O avaliador de `condition` MUST suportar os operadores **`<`, `>`, `<=`, `>=`, `==`, `!=`, `in`** (lista de literais) sobre o output de steps anteriores e sobre o `context` (ex: `{"classifier.confidence": "<0.6"}`, `{"classifier.intent": "==billing"}`, `{"classifier.intent": "in [billing,ranking_query]"}`, `{"context.message_count": ">15"}`). Múltiplas chaves no mesmo objeto JSON combinam por **AND implícito**. **OR e parênteses não são suportados na v1** — para lógica disjunta usar steps separados com condições mutuamente exclusivas. Chaves não encontradas no escopo resolvem para `false` (sem crash) e disparam warning logado uma vez por agente/step. Ver Clarifications 2026-04-27.
- **FR-025**: Quando um step retorna texto que vira a resposta final ao cliente (ex: clarifier), os steps subsequentes MUST ser marcados `skipped` no trace.
- **FR-026**: Quando um step falha (erro de LLM, timeout, parse de output), o sistema MUST marcar o step como erro no trace, marcar os subsequentes como `skipped` e cair em fallback canned (mesmo mecanismo do step 10 atual — FALLBACK_MESSAGE PT-BR). **Zero retry no v1** — falha → fallback imediato, sem nova tentativa do mesmo step nem skip-and-continue. Ver Clarifications 2026-04-27.
- **FR-027**: O timeout total do pipeline (todos os steps somados) MUST respeitar o `_PIPELINE_TIMEOUT_SECONDS` global atual (60 s); estouro → fallback canned.
- **FR-028**: Cada step individual MUST ter timeout próprio configurável via `config.timeout_seconds` (default 30 s, máximo 60 s).
- **FR-029**: O sistema MUST persistir o pipeline executado (lista de steps com tipo, modelo, duração, status, input/output truncados a 8 KB) como sub-steps dentro do step `generate_response` no schema de tracing existente (épico 008 — `traces` + `trace_steps`).
- **FR-030**: A persistência fire-and-forget de sub-steps NOT MUST bloquear a entrega da resposta ao cliente (mesma regra de ouro do trace top-level).

**Versionamento e admin**

- **FR-040**: Mudanças em pipeline steps de um agente MUST gerar nova versão em `agent_config_versions` (ADR-019), incluindo snapshot da lista completa de steps no `config_snapshot`.
- **FR-041**: A nova versão MUST ficar em estado `pending` até ativação explícita pelo admin; ativação dispara troca atômica de `agents.active_version_id`.
- **FR-042**: O admin (épico 008, aba Agentes → Configuração) MUST exibir uma sub-seção **Pipeline Steps** com a lista atual em ordem visual (cards verticais ou tabela ordenada), botões para adicionar (com seletor de tipo), editar, reordenar (up/down) e remover steps.
- **FR-043**: O formulário de edição de step MUST mostrar apenas campos relevantes ao `step_type` selecionado (ex: classifier exige `intent_labels` e `model`; specialist exige `routing_map` e `default_model`; clarifier exige `model` e `prompt_slug`; summarizer exige `max_input_messages`).
- **FR-044**: O backend MUST validar config no momento do salvamento, retornando 422 com mensagens específicas (campo, motivo) quando inválido — incluindo: `step_order` duplicado/fora-de-ordem, `step_type` inválido, `routing_map` inválido (ex: modelo inexistente), `condition` com sintaxe quebrada, `prompt_slug` referenciando prompt arquivado.
- **FR-045**: Toda alteração ativada MUST gerar entrada em `audit_log` com email do operador, agente afetado, versão antiga e nova, e diff resumido (steps adicionados/removidos/editados).
- **FR-046**: O admin MUST permitir rollback imediato para a versão anterior (botão "Rollback") sem requerer aprovação adicional; troca atômica de `active_version_id` em <1 s.

**Canary e métricas**

- **FR-050**: O sistema MUST suportar canary rollout per-version (mecanismo ADR-019 existente) para versões com pipeline diferente — ex: v4 (sem pipeline, 90%) e v5 (com pipeline, 10%).
- **FR-051**: A aba Performance AI (épico 008) MUST suportar `group_by=agent_version` quando o agente está em canary, exibindo KPIs (QS, custo, latência P95, fallback rate) lado-a-lado por versão.
- **FR-052**: Versões com amostra <50 mensagens NOT MUST exibir números agregados; em vez disso, mostram label `"amostra insuficiente — N=X"` (consistente com regra do domain-model item 16).

**Trace e observabilidade**

- **FR-060**: Cada execução de pipeline step MUST ser persistida como sub-step dentro do trace do `generate_response`, com: `step_type`, `step_order`, `model_used`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms`, `status`, `input` (≤8 KB truncado), `output` (≤8 KB truncado), `error_type`+`error_message` quando aplicável.
- **FR-061**: O Trace Explorer (épico 008) MUST renderizar sub-steps dentro do step `generate_response` quando presentes, em formato consistente com os steps top-level (waterfall, accordion expansível).
- **FR-062**: A lista de traces MUST permitir filtrar por `pipeline_version` (versão do agente que rodou) e `terminating_step` (qual step produziu a resposta final ao cliente). **Storage de filtros** — sem novas colunas: `pipeline_version` é lido de `trace_steps.agent_version_id` (campo existente do épico 008); `terminating_step` é lido de `trace_steps.output->>'terminating_step'` no row do `generate_response`. Ver Clarifications 2026-04-27.
- **FR-063**: Cada step persistido MUST conter `condition_evaluated` (boolean ou texto curto) quando o step é `skipped` por condição, para tornar o motivo do skip auditável sem inferência.
- **FR-064**: O sistema MUST escrever em `messages.metadata` JSONB (campo existente, sem mudança de schema) os campos `terminating_step` (string), `pipeline_version` (UUID do `agent_config_versions`) e `pipeline_step_count` (int) para cada mensagem outbound gerada via pipeline. Para mensagens de agentes single-call (sem pipeline), os campos NOT MUST ser escritos. Ver Clarifications 2026-04-27.

**Compatibilidade e regressão**

- **FR-070**: 100% dos testes existentes da suíte `apps/api/prosauai/tests/` (cobrindo épicos 002, 004, 005) MUST passar antes do merge sem modificação.
- **FR-071**: O comportamento de agentes existentes (sem `pipeline_steps`) NOT MUST mudar — mesmas latências, custos, modelos, outputs (validado por A/B teste em staging com 1000 mensagens reais).
- **FR-072**: A migração de schema (criação da tabela `agent_pipeline_steps` e índices) MUST ser idempotente; reaplicar a migration em DB com a tabela já existente é no-op.

### Key Entities *(include if feature involves data)*

- **Agent Pipeline Step**: representa uma etapa configurável do processamento de um agente. Atributos-chave: id, tenant_id (FK), agent_id (FK), step_order (INT), step_type (`classifier|clarifier|resolver|specialist|summarizer`), config (JSONB — modelo, prompt_slug, tools, threshold, intent_labels, routing_map, default_model, max_input_messages, timeout_seconds), condition (JSONB opcional, ex: `{"classifier.confidence": "<0.6"}`), is_active (BOOL), timestamps. Constraint: `UNIQUE(agent_id, step_order)`. Relaciona-se com Agent (N:1).
- **Pipeline Step Output**: estrutura conceitual (não persistida diretamente — vive no campo `output` do trace step) que representa o resultado de cada step. Schema depende do `step_type`: classifier → `{intent, confidence, explanation}`; clarifier → `{question_text}`; resolver → `{entities: {...}}`; specialist → `{response_text, model_used, tokens, tool_calls}`; summarizer → `{summary_text, message_count}`.
- **Pipeline Snapshot**: lista ordenada de steps capturada **uma vez** no início do `process_conversation`, garantindo consistência mesmo com hot reload concorrente. Conceitualmente um valor in-memory; não tem persistência própria além do snapshot dentro de `agent_config_versions.config_snapshot.pipeline_steps`.
- **Agent Config Version (estendido)**: entidade existente (ADR-019) — recebe campo adicional dentro de `config_snapshot`: `pipeline_steps` (array com snapshot dos steps daquela versão). Serve como source of truth histórica para auditoria e rollback.
- **Trace Step (estendido)**: entidade existente (épico 008) — para o step `generate_response` (step_order=8), passa a comportar uma lista de **sub_steps** (objeto JSON aninhado em `output` ou nova coluna `sub_steps` JSONB) representando os pipeline steps executados, cada um com a mesma estrutura de um trace step top-level. Decisão entre coluna nova vs. nested em `output` fica para fase de plan.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em uma janela de 30 dias após o roll-out do agente Ariel com pipeline (classifier + specialist), o **custo médio por mensagem cai em pelo menos 30%** comparado ao baseline pré-épico (medido em USD agregado por mensagem em `messages.cost_usd`).
- **SC-002**: A **latência P95** do pipeline para mensagens classificadas como `greeting`/`simple_query` cai para **menos de 1 s** (vs. ~1.8 s baseline atual).
- **SC-003**: O **quality score médio** do agente Ariel pós-pipeline NOT MUST cair mais de **0.05 pontos** vs. baseline (na escala 0–1 do épico 002 / scoring atual). Cair 0.05 ou mais = trigger automático de rollback.
- **SC-004**: A **taxa de retomadas** ("não, não foi isso que perguntei") cai em pelo menos **30%** após adicionar o step `clarifier` para mensagens com `confidence < 0.6` (medido por análise manual de 200 conversas amostradas pré e pós).
- **SC-005**: 100% das sessões de configuração de pipeline pelos engenheiros de prompt acontecem via UI do admin (épico 008), sem necessidade de SQL direto, após o ship de US3.
- **SC-006**: Um operador (sem acesso ao banco) consegue **adicionar um step novo, configurar e ativar** o pipeline de um agente em **menos de 3 minutos** a partir do login no admin.
- **SC-007**: Um engenheiro consegue **identificar a step responsável** por latência ou erro em uma mensagem específica em **menos de 1 minuto** a partir do `trace_id` ou nome do contato, via Trace Explorer.
- **SC-008**: 100% dos testes existentes (`apps/api/prosauai/tests/`) passam sem modificação no merge da branch `epic/prosauai/015-agent-pipeline-steps` para `develop`.
- **SC-009**: A regressão A/B em staging — 1000 mensagens reais reprocessadas com o agente baseline (sem pipeline) vs. com `pipeline_steps=[]` — produz outputs estatisticamente equivalentes (margem ≤1% em QS, custo, latência, modelo usado).
- **SC-010**: Overhead da consulta `agent_pipeline_steps WHERE agent_id=X` no caminho crítico do pipeline para agentes sem steps configurados MUST ser **≤5 ms p95** (medido em staging com 10 agentes ativos e 100k requests).
- **SC-011**: Após o ship, **pelo menos 2 dos 6 tenants ativos** adotam pipeline (≥1 step configurado) em até 60 dias, sem incidente de produção atribuído à feature (incidente = erro de runtime, regressão de QS >0.1, ou rollback emergencial).
- **SC-012**: 100% das execuções de pipeline persistidas em produção têm sub-steps no trace (visíveis no Trace Explorer), permitindo auditoria sem dependência de logs estruturados externos.
- **SC-013**: O custo de implementação do épico (medido em pessoa-semana de eng) fica em até **3 semanas** para a fase 1 (FR-001 a FR-030 + FR-070 a FR-072), permitindo decidir investimento adicional em UI/canary com dados de produção real (Shape Up cut-line).

## Assumptions

- **Schema base já existe**: a tabela `agent_pipeline_steps` está definida em `domain-model.md` (linha 244) e ADR-006, mas **ainda não foi criada em produção** (nenhum tenant usa pipeline hoje); este épico é a primeira implementação real.
- **Versionamento de agentes operacional**: `agent_config_versions` (ADR-019) está implementado e estável (validado nos épicos 005/008); este épico adiciona pipeline steps ao `config_snapshot` sem mudar a mecânica de canary.
- **Trace Explorer disponível**: épico 008 (Admin Evolution) shippa antes deste, fornecendo schema de `traces`/`trace_steps` e UI de detalhe; este épico estende o step `generate_response` com sub-steps mas reusa toda a infra de tracing.
- **5 tipos de step são suficientes para v1**: `classifier|clarifier|resolver|specialist|summarizer` cobrem os usos imediatos identificados; novos tipos (ex: `validator`, `enricher`) ficam como follow-up sem mudança breaking de schema (apenas extensão do CHECK).
- **Limite de 5 steps por agente**: deliberado para evitar configurações absurdas; **hard-coded em v1, não configurável por tenant** (Clarifications 2026-04-27); revisitar via PR/ADR se um caso real legítimo exigir 6+ steps (raro).
- **Backward compatibility absoluta**: agentes sem steps configurados executam exatamente como hoje. Esta é uma invariante não-negociável; qualquer regressão observável bloqueia merge.
- **Hot reload via snapshot atômico**: o pipeline steps são lidos uma vez por mensagem, no início do `process_conversation`. Não há tentativa de recarregar config a meio do pipeline.
- **Sem retry inteligente entre steps**: se qualquer step falhar, o sistema cai em FALLBACK canned imediatamente — não há "tente o specialist mais uma vez" ou "rode o resolver pra recolher contexto extra". Mantém pipeline simples e previsível. Confirmado em Clarifications 2026-04-27 (FR-026).
- **`prompt_slug` resolvido contra a tabela existente**: o campo `prompt_slug` em `config` referencia entradas em `prompts` (existentes via ADR-019); não há tabela separada para "step prompts".
- **Modelos disponíveis listados em pricing constant**: o validador de `routing_map` consulta a constante de preços (ADR-029) para verificar que cada modelo é conhecido pelo sistema; modelo desconhecido → 422.
- **Custo por step persistido**: cada sub-step tem `cost_usd` calculado via `calculate_cost(tokens, model)` (mecanismo ADR-029 existente); o agregado `messages.cost_usd` é a soma dos sub-steps.
- **Canary per-version reaproveitado**: nenhum mecanismo novo de canary é introduzido; v5 (com pipeline) compete com v4 (single call) usando o `traffic_pct` existente (ADR-019).
- **Configuração via SQL direto durante phase 1**: o ship de US1/US2 não exige a UI do admin (US3) — engenharia configura pipeline para os primeiros 2-3 agentes via SQL/migration, valida em produção, e só depois US3 entrega UI para produto/ops.
- **Sem A/B per-step**: este épico não introduz canary granular por step (ex: classifier v1 vs. v2 dentro do mesmo agente). Canary continua sendo per-version do agente inteiro. Granularidade adicional fica como follow-up.
- **Intent labels do classifier não compartilhados com router MECE**: o classifier do pipeline produz labels usadas internamente pelo specialist; **não** alimenta o roteador externo (épico 004) — são abstrações distintas (router classifica entrada bruta; classifier interno classifica intenção semântica para decidir modelo/prompt).
- **Apetite Shape Up**: 3 semanas para fases 1+2 (FR-001 a FR-046, US1+US2+US3). Cut-line: se passar de 4 semanas antes de finalizar US3, US3 vira épico próprio e este épico fecha com US1+US2 + configuração via SQL apenas.
- **Stack inalterada**: zero novas dependências Python; reaproveita pydantic-ai (já em uso), asyncpg, structlog, OpenTelemetry. Frontend (épico 008) reaproveita Next.js 15 + shadcn/ui + TanStack Query + Recharts existentes.
- **Cross-referência**: decisões finas de arquitetura (estrutura JSONB exata do `config` por step type, esquema de avaliação de `condition`, integração com `evals`) ficam em `pitch.md` (Captured Decisions) e serão revisadas em `decisions.md` durante a implementação.

---

handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificado em modo dispatch autônomo (sessão 2026-04-27). 5 ambiguidades de alto impacto resolvidas via [DECISAO AUTONOMA]: (1) gramática do avaliador de condition — operadores `<`, `>`, `<=`, `>=`, `==`, `!=`, `in`; AND-implicit; sem OR/parens v1 (FR-024); (2) política de retry — zero retry, fallback canned imediato em qualquer falha (FR-026); (3) summarizer substitui (não prepende) o histórico no `pipeline_state.summarized_context` consumido pelos steps subsequentes; `messages` raw preservado (FR-015); (4) limite de 5 steps hard-coded em `MAX_PIPELINE_STEPS_PER_AGENT`, não configurável por tenant na v1 (FR-003); (5) filtros `terminating_step` e `pipeline_version` reaproveitam `messages.metadata` JSONB + `trace_steps.agent_version_id` + `trace_steps.output->>'terminating_step'` — zero novas colunas (FR-062, FR-064 novo). Cobertura final: Domain/Data Clear; Functional Clear; NFR Clear; Edge Cases Clear; Constraints Clear; Integration Clear; Terminology Clear; Failure Handling Clear. Outstanding (deferido para plan): (a) granularidade do canary fica per-version (já decidido — confirmação suficiente); (b) decisão entre `sub_steps` JSONB nova coluna vs nested em `output` continua aberta — natural decidir no plan com base em queries de Trace Explorer existentes; (c) integração com evals (épico 017) fica como cross-reference no plan, não materialmente bloqueante para fase 1."
  blockers: []
  confidence: Alta
  kill_criteria: "Este spec clarificado fica inválido se: (a) decisão de descontinuar `agent_pipeline_steps` em favor de uma feature low-code mais ampla (ex: BPMN-style agent designer); (b) épico 008 (Trace Explorer + Performance AI) é descontinuado ou re-escopado, removendo a infra de visibilidade que US5/US4 dependem; (c) ADR-019 (agent config versioning) é re-arquitetado de forma incompatível antes do início da fase 1; (d) benchmarks reais em staging mostrarem que mesmo o pipeline mais simples (classifier+specialist) tem overhead estrutural >5% em latência total comparado a single-call (invalidando SC-002 e SC-009); (e) regressão de QS >0.1 nos primeiros 7 dias do canary com Ariel — força volta à prancheta com nova abordagem (talvez ferramenta declarativa em vez de pipeline imperativo); (f) durante plan se descobrir que a sintaxe de `condition` proposta na FR-024 conflita com algum padrão pré-existente em `agent_config_versions.config_snapshot` — re-abrir a clarification correspondente."
