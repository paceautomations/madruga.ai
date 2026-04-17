# Feature Specification: Admin Evolution — Plataforma Operacional Completa

**Feature Branch**: `epic/prosauai/008-admin-evolution`
**Created**: 2026-04-17
**Status**: Draft
**Input**: Épico 008 — evolução do admin entregue no 007 (login + 1 KPI) para uma plataforma operacional com 8 abas funcionais cobrindo todo o ciclo de vida da conversa: observação (Conversations, Trace Explorer, Performance), gestão (Agents, Routing, Tenants), segurança (Audit) e overview enriquecido.

## Clarifications

### Session 2026-04-17

- Q: Quais thresholds específicos definem verde/âmbar/vermelho dos KPI cards (Overview) e da tabela Saúde por Tenant? → A: **Quality Score** (escala 0–100) — verde ≥85, âmbar 70–84, vermelho <70. **Latência P95** — verde ≤2 s, âmbar 2–5 s, vermelho >5 s. **Containment Rate** — verde ≥75%, âmbar 60–74%, vermelho <60%. **Fallback Rate** — verde <10%, âmbar 10–20%, vermelho >20%. **Erros (janela 24 h)** — verde 0, âmbar 1–5, vermelho >5. **Conversas Ativas** e **Mensagens Hoje** não recebem cor por valor absoluto (métricas de volume); são exibidas apenas com delta vs. dia anterior (delta positivo = verde, delta ≥30% negativo em Conversas Ativas ou Mensagens Hoje = âmbar/vermelho a depender da magnitude).
- Q: A busca de conversas usa ILIKE ou full-text (tsvector/GIN)? FR-021 dizia "full-text" mas as Assumptions e decisão 16 do pitch dizem ILIKE. → A: **ILIKE** em v1 (confirmado). FR-021 é corrigido para eliminar a contradição. Migração para `tsvector + GIN` fica como follow-up quando ocorrer o primeiro de: >10k conversas ativas, P95 da busca >500 ms, ou necessidade de ranking por relevância.
- Q: O que conta como "fallback" no cálculo de fallback rate (FR-050, FR-051)? → A: Uma mensagem é contabilizada como fallback se ocorrer **qualquer** uma das condições: (i) intent classificado como `fallback`, `unknown` ou `out_of_scope` no step `classify_intent`; (ii) `intent_confidence < 0.5` registrado pelo mesmo step; (iii) resposta marcada como `safety_refused` pelo step `output_guard`; (iv) handoff humano iniciado pelo pipeline (AI desistiu). A contagem é por mensagem (não por conversa) e exclui mensagens onde o roteador decidiu `DROP`/`LOG_ONLY`/`BYPASS_AI` (essas não passam pelo pipeline de IA).
- Q: Como é calculado o status geral (verde/âmbar/vermelho) de cada tenant na tabela Saúde por Tenant? → A: Hierárquico. **Vermelho** se ocorrer qualquer um de: algum KPI do tenant (QS, Latência P95, Containment, Fallback, Erros) classificado como vermelho pelos thresholds acima, OU última mensagem processada há mais de 15 minutos (sinal de API travada para o tenant), OU taxa de erro em janela rolling de 5 minutos >10%. **Âmbar** se não é vermelho e ao menos um KPI do tenant está em âmbar. **Verde** caso contrário. Tenants com zero tráfego em 24 h são exibidos com status "—" (neutro), não verde.
- Q: Se o input de mensagens é desabilitado e o admin é somente leitura (FR-027), de onde vêm as bolhas "handoff humano" (FR-023)? → A: São mensagens outbound **já existentes** na tabela `messages`, gravadas via webhook do Evolution API quando um atendente humano responde pelo app de WhatsApp externo. O sinal é o campo existente que distingue origem AI vs. humano (ex.: `messages.role='human_operator'` ou `metadata.source='human'`, conforme o schema atual do pipeline). O admin apenas **renderiza** essas mensagens — não oferece qualquer envio. Label da bolha: nome do atendente quando disponível em `messages.metadata.operator_name`; fallback para "Atendente humano" + timestamp.

## User Scenarios & Testing *(mandatory)*

<!--
  Stories priorizadas por journey. Cada uma é independentemente testável (entregaria valor isolada).
  P1 = MVP mínimo viável. P2 = diferencial operacional. P3 = polish e governança.
-->

### User Story 1 — Inspecionar conversa de um cliente sem SQL (Priority: P1)

Um operador de atendimento recebe uma reclamação: "o bot respondeu errado ao João Silva ontem às 14h." Hoje ele precisa abrir um `psql`, montar um JOIN entre `customers`, `conversations` e `messages`, e ler a thread em linha de comando. Com o admin evoluído, ele abre a aba **Conversas**, busca por "João Silva", clica no item da lista e vê em **uma única tela**: a lista de contatos/conversas à esquerda, a thread completa ao centro (com bolhas inbound e AI outbound, timestamps e metadados) e o perfil do contato à direita (histórico, intent atual, quality score médio, tags).

**Why this priority**: resolve o problema #1 da dor operacional — conversas invisíveis. É o bloco mais usado no dia-a-dia (qualquer incidente começa aqui). Sem esta funcionalidade, todo o resto do épico perde tração porque o operador volta ao `psql` de qualquer forma.

**Independent Test**: um operador novo, sem acesso ao banco, consegue localizar e ler o thread completo de uma conversa específica a partir do nome ou trecho de mensagem do cliente em menos de 30 segundos, vendo também o perfil resumido do contato, sem tocar em `psql` ou `journalctl`.

**Acceptance Scenarios**:

1. **Given** existem pelo menos 10 conversas na base com clientes distintos, **When** o operador abre `/admin/conversations` e digita "João" na barra de busca, **Then** a lista filtra conversas cujo `display_name` do contato OU conteúdo de mensagem contém "João", em até 1 segundo.
2. **Given** o operador selecionou uma conversa na lista, **When** a coluna central carrega, **Then** ele vê todas as mensagens da conversa ordenadas cronologicamente, com bolhas visualmente distintas para inbound (cliente) e outbound (AI/humano), incluindo timestamps e, nas mensagens AI, metadados resumidos (latência, tokens, QS, link "Ver trace").
3. **Given** uma conversa está aberta, **When** o operador expande o painel de perfil, **Then** ele vê: nome, tenant, canal, status da conversa atual, intent corrente com confidence, QS médio da conversa, contagem de mensagens, histórico resumido (quantas conversas anteriores, QS histórico) e ações contextuais ("Ver todos os traces", "Fechar conversa").
4. **Given** uma conversa tem SLA em risco ou com breach, **When** a lista é renderizada, **Then** o item aparece no topo da ordenação, com indicador visual claro (chip de alerta âmbar/vermelho).
5. **Given** o operador clica em "Fechar conversa" no perfil, **When** a ação é confirmada, **Then** o status da conversa passa para `closed` e a lista atualiza o indicador em <2 segundos.

---

### User Story 2 — Debugar pipeline de IA com trace waterfall step-by-step (Priority: P1)

Um engenheiro de prompt recebe o report de um usuário: "a resposta veio errada e demorou 6 segundos." Hoje ele precisa rodar `journalctl -u prosauai-api | rg <trace_id>` e correlacionar manualmente com `messages.metadata` no banco e abrir Phoenix UI separado. Com o admin evoluído, ele abre **Trace Explorer**, filtra pelo período ou busca o `trace_id`, clica na linha e vê um waterfall visual das **12 etapas** do pipeline: cada etapa com barra proporcional de duração, status (ok/erro/skip), e accordion expansível com input, output, modelo usado, tokens, tool calls e mensagem de erro quando aplicável.

**Why this priority**: este é o diferencial técnico do épico — nenhum outro lugar dá essa visão. Resolve o problema #2 (pipeline caixa preta) e é pré-requisito para reduzir o MTTR de incidentes de prompt/modelo. Engineering bloqueia sem isso.

**Independent Test**: um engenheiro consegue identificar a etapa dominante em latência de uma conversa específica, ver input/output dessa etapa e detectar se houve erro, tudo a partir de um `trace_id` ou nome de contato, sem usar `journalctl`, Phoenix ou `psql`.

**Acceptance Scenarios**:

1. **Given** o pipeline de IA processou pelo menos 10 mensagens nas últimas 2 horas, **When** o engenheiro abre `/admin/traces`, **Then** ele vê uma lista paginada com: hora, contato, intent, duração total, custo estimado, status (ok/erro/degradado), filtrável por tenant, status e duração mínima.
2. **Given** um trace foi selecionado, **When** a página de detalhe carrega, **Then** ele vê as 12 etapas em um waterfall onde a largura de cada barra é proporcional à duração relativa e a etapa dominante (>60% do total) é destacada visualmente com cor de alerta.
3. **Given** o engenheiro clica em uma etapa (ex: `generate_response`), **When** o accordion expande, **Then** ele vê: modelo usado, tokens in/out, temperatura, system prompt (completo, colapsável), histórico de mensagens, resposta gerada e tool calls (quando aplicável).
4. **Given** uma das etapas falhou, **When** a página carrega, **Then** a linha da etapa com erro tem destaque visual (borda vermelha, fundo diferenciado) e está auto-expandida mostrando `error_type`, `error_message` e stack trace colapsável; etapas posteriores aparecem como `skipped`.
5. **Given** o engenheiro veio da aba Conversas clicando em "Ver trace", **When** a página abre, **Then** ele vê também um link "Ver Conversa →" no header do trace para navegar de volta ao contexto da thread.
6. **Given** um trace tem input/output superior a 8 KB, **When** o accordion expande, **Then** o valor é mostrado truncado com indicador claro `[truncado — tamanho original X KB]` para evitar sobrecarga do navegador.

---

### User Story 3 — Avaliar qualidade e custo do AI para decidir ajustes de prompt (Priority: P2)

Um líder de produto precisa decidir se compensa investir tempo em otimizar o prompt do agente Ariel. Hoje ele pergunta no Slack "qual o QS médio da semana?", alguém roda SQL, e a resposta volta em horas. Com a aba **Performance AI**, ele abre `/admin/performance`, escolhe período "últimos 7 dias" e tenant "pace-internal", e vê em uma tela: containment rate, QS médio com tendência, P95 de latência, fallback rate, distribuição de intents (com fallback rate por intent), heatmap de erros por hora/dia e custo estimado por tenant e por modelo.

**Why this priority**: transforma decisão guiada por intuição em decisão guiada por dados. Pré-requisito para qualquer iniciativa de melhoria contínua do agente. Não é P1 porque a operação sobrevive com Slack + SQL manual semanal, mas é decisivo para produto.

**Independent Test**: um líder de produto consegue identificar o intent com maior fallback rate, a hora do dia com mais erros e o modelo mais caro na última semana, sem precisar pedir dado a nenhum engenheiro.

**Acceptance Scenarios**:

1. **Given** existem pelo menos 7 dias de dados do pipeline, **When** o líder abre `/admin/performance` com período "últimos 7 dias" e tenant="pace-internal", **Then** ele vê KPIs agregados (containment rate, QS avg, P95 latência, fallback rate), cada um com delta vs. período anterior.
2. **Given** há pelo menos 3 intents distintos processados, **When** o gráfico de "Distribuição de Intents" renderiza, **Then** ele mostra barras horizontais ordenadas por volume decrescente, com codificação visual adicional para intents com alto fallback rate.
3. **Given** o período selecionado tem dias com erros em horários específicos, **When** o heatmap renderiza, **Then** ele mostra uma grade 24×7 onde cada célula tem intensidade de cor proporcional ao volume de erro naquele horário/dia, com tooltip mostrando contagem exata ao passar o mouse.
4. **Given** múltiplos modelos foram usados (ex: gpt-4o-mini e gpt-4o), **When** o gráfico "Custo por Modelo" renderiza, **Then** ele mostra o custo agregado em USD por modelo no período, com sparkline de 30 dias abaixo.
5. **Given** o líder é o primeiro usuário a abrir a aba em ≥5 minutos, **When** a página carrega, **Then** a agregação é recalculada e cacheada; usuários subsequentes dentro de 5 minutos recebem resposta em <200ms.

---

### User Story 4 — Monitorar saúde geral da plataforma em 10 segundos (Priority: P2)

O CTO entra no admin pela manhã e quer em 10 segundos saber: "está tudo bem?" Hoje ele precisa abrir 4 painéis (Phoenix, status page, logs, Grafana). Com o **Overview** enriquecido, uma única tela responde: 6 KPIs com sparkline das últimas 24h e delta vs. ontem (conversas ativas, mensagens hoje, containment rate, latência média, quality score, contagem de erros), feed de atividade ao vivo (novas conversas, SLA breach, erros), status dos componentes externos (API, Postgres, Redis, Evolution API, Phoenix) e tabela de saúde por tenant.

**Why this priority**: substitui o "ritual das 4 abas" matinal de liderança técnica. Alto impacto para poucos usuários. P2 porque P1 já cobre as investigações profundas — esta é a primeira porta de entrada.

**Independent Test**: um gestor técnico consegue identificar, em menos de 10 segundos após logar, se algum componente externo está degradado, se algum tenant está com QS fora do verde e se há erros nas últimas horas, sem clicar em nenhuma aba secundária.

**Acceptance Scenarios**:

1. **Given** o Overview é a tela pós-login, **When** a página carrega, **Then** os 6 KPI cards são visíveis em um grid acima da dobra, cada um com: valor numérico grande, label descritivo, sparkline 24h e delta vs. ontem com cor (verde = melhor, vermelho = pior, neutro = estável).
2. **Given** a plataforma processou mensagens nos últimos 15 minutos, **When** o Live Activity Feed renderiza, **Then** ele mostra até 50 eventos mais recentes (nova conversa, SLA breach, fallback, erro), com auto-refresh a cada 15 segundos, cada linha clicável para navegar ao contexto (conversa ou trace).
3. **Given** pelo menos um componente externo está down, **When** o painel System Health atualiza (polling 30s), **Then** o item com falha fica em estado visual distinto (ponto vermelho para down, âmbar para degradado) com timestamp da última verificação.
4. **Given** há 2+ tenants ativos, **When** a tabela "Saúde por Tenant" renderiza, **Then** ela lista cada tenant com: conversas ativas, QS médio, latência P50 e status geral (verde/âmbar/vermelho) calculado por regras documentadas.
5. **Given** o usuário clica em uma linha da tabela de tenants, **When** a navegação ocorre, **Then** o parâmetro `?tenant=<slug>` é aplicado a todas as outras abas.

---

### User Story 5 — Auditar decisões de roteamento para entender "por que essa mensagem não foi respondida" (Priority: P2)

Um atendente reporta: "um cliente mandou mensagem ontem às 16h e não teve resposta." Hoje ninguém sabe responder sem vasculhar logs. Com a aba **Roteamento**, o admin vê todas as decisões tomadas pelo roteador (incluindo `DROP` e `LOG_ONLY` que hoje são invisíveis): tipo de decisão, razão, regra que matchou, snapshot dos `MessageFacts` e trace_id associado. Também vê distribuição (donut) de tipos de decisão no período e top-N razões de DROP/BYPASS.

**Why this priority**: elimina categoria inteira de incidentes "silenciosos" (mensagens descartadas). Resolve o problema #4 do pitch. P2 porque o volume absoluto de reports dessa categoria é menor que de "resposta errada" (P1).

**Independent Test**: o admin consegue, a partir do número de telefone do cliente (hash) e uma janela de tempo, localizar a decisão de roteamento tomada para a mensagem dele, ver a razão do `DROP` (ex: `sender_is_bot`) e a regra que matchou, sem olhar `journalctl`.

**Acceptance Scenarios**:

1. **Given** o roteador processou ≥50 mensagens nas últimas 24h, **When** o admin abre `/admin/routing`, **Then** ele vê: painel de regras ativas por tenant (prioridade, condições, ação resultante, agente alvo), donut com distribuição dos 5 tipos de decisão (RESPOND / DROP / LOG_ONLY / BYPASS_AI / EVENT_HOOK) e tabela de decisões recentes.
2. **Given** o admin filtra por `decision_type=DROP`, **When** a tabela recarrega, **Then** ela mostra apenas as decisões de DROP com hora, contato (display_name ou phone_hash), preview da mensagem, razão e trace_id.
3. **Given** o admin clica em uma decisão específica, **When** o detalhe expande, **Then** ele vê: snapshot JSON da regra que matchou, snapshot JSON dos MessageFacts calculados e link para o trace associado (quando a decisão é RESPOND).
4. **Given** a aplicação do roteador tem regras carregadas em memória, **When** o painel de regras atualiza, **Then** ele reflete o estado atual sem precisar de restart da aplicação.

---

### User Story 6 — Gerenciar agentes e comparar versões de prompt (Priority: P3)

Um engenheiro de prompt quer entender o impacto de mudar o `system_prompt` do agente Ariel Bot da v2 para a v3. Com a aba **Agentes**, ele vê a lista de agentes por tenant, abre o Ariel Bot e navega pelas tabs internas: Configuração (modelo, temperatura, tools, métricas rápidas), Prompts (pills com versões v1/v2/v3, diff side-by-side ao selecionar duas versões, visualizador com seções coloridas para `safety_prefix` / `system_prompt` / `safety_suffix`) e Métricas (KPIs do agente vs. média da plataforma, sparkline 30d).

**Why this priority**: gestão avançada, não é pré-requisito para incident response. P3 porque engenharia de prompt hoje é rara (1-2x por mês).

**Independent Test**: um engenheiro consegue comparar duas versões de prompt de um agente em diff side-by-side, ver as tools habilitadas e as métricas rápidas do agente, sem abrir o banco nem o repositório.

**Acceptance Scenarios**:

1. **Given** existem ≥2 agentes configurados, **When** o admin abre `/admin/agents`, **Then** ele vê lista à esquerda (240px) com agentes filtráveis por tenant e área de detalhe à direita com 3 tabs.
2. **Given** um agente tem 3 versões de prompt, **When** o admin abre a tab "Prompts", **Then** ele vê pills com v1/v2/v3 (v3 marcada como ativa) e pode selecionar duas versões para ver diff side-by-side.
3. **Given** uma versão de prompt é selecionada, **When** o visualizador renderiza, **Then** as 3 seções (safety_prefix, system_prompt, safety_suffix) são visualmente distintas com fundos diferenciados, preservando whitespace.
4. **Given** o admin clica em "Ativar" em uma versão antiga, **When** a ação é confirmada, **Then** `active_prompt_id` do agente é atualizado e a v ativa muda no UI.

---

### User Story 7 — Administrar tenants (ativar/desativar, ver uso) (Priority: P3)

Um admin financeiro precisa desativar temporariamente um tenant inadimplente. Com a aba **Tenants**, ele vê lista de tenants com status, conversas ativas, QS médio e última atividade; clica no tenant e vê detalhe com agentes associados, métricas dos últimos 7 dias e toggle de ativação.

**Why this priority**: baixa frequência (raramente se desativa tenant). Crítico quando precisa, mas não bloqueia operação diária.

**Independent Test**: um admin consegue localizar um tenant pelo slug, ver o volume e QS dele na última semana e desativar o tenant com 1 clique, sem acesso ao banco.

**Acceptance Scenarios**:

1. **Given** existem ≥2 tenants cadastrados, **When** o admin abre `/admin/tenants`, **Then** ele vê tabela com nome, slug, status, conversas ativas, QS médio e timestamp do último webhook recebido.
2. **Given** o admin clica no tenant, **When** o detalhe carrega, **Then** ele vê configuração, agentes associados (com link para aba Agentes), métricas 7d (volume, QS, containment, custo) e toggle `enabled`.
3. **Given** o admin desativa um tenant, **When** confirma a ação, **Then** `tenants.enabled=false` é persistido e o roteador da próxima mensagem aplica a regra de bloqueio (comportamento já existente do router).

---

### User Story 8 — Revisar eventos de segurança e login (Priority: P3)

Um responsável de segurança precisa verificar tentativas anômalas de login. Com a aba **Auditoria**, ele vê timeline paginada com: hora, ação, usuário, IP e detalhes; filtros por tipo de ação, por usuário e por período; destaque visual para eventos sensíveis (`rate_limit_hit`, múltiplas falhas do mesmo IP).

**Why this priority**: compliance e post-mortem. Baixa frequência, alto valor quando precisa. P3.

**Independent Test**: um responsável de segurança consegue listar todos os `login_failed` dos últimos 7 dias para um IP específico e todas as ações de um usuário administrador, sem consultar o banco.

**Acceptance Scenarios**:

1. **Given** a tabela `audit_log` tem ≥100 eventos, **When** o admin abre `/admin/audit`, **Then** ele vê timeline paginada (50 por página, cursor-based) com hora, ação, usuário (email), IP e coluna de detalhes.
2. **Given** o admin filtra por `action=login_failed` e período=7 dias, **When** a lista recarrega, **Then** apenas os eventos desse tipo são mostrados, em até 1 segundo.
3. **Given** há 3+ `login_failed` do mesmo IP nas últimas 24h, **When** o evento é renderizado, **Then** a linha tem destaque visual de alerta (cor distinta) e uma tag indicando "múltiplas falhas".

---

### Edge Cases

- **Conversa sem mensagens**: a lista não deve mostrar conversas sem mensagens; se uma conversa for listada mas a thread estiver vazia, a coluna central exibe estado vazio descritivo ("sem mensagens ainda").
- **Trace sem todas as 12 etapas**: quando uma etapa foi pulada legitimamente (ex: `output_guard` quando PII check desabilitado) ou falhou no meio, o waterfall mostra só as etapas executadas e as subsequentes como `skipped`.
- **Cliente sem `display_name`**: a lista e o perfil devem cair para o telefone mascarado (ex: "(11) ****-1234") como label.
- **Muitos tenants (>50)**: dropdown de tenant no header deve ter busca/filtro. Tabela "Saúde por Tenant" do Overview pagina se >20 tenants.
- **Busca com muitos resultados**: lista de conversas limita a 200 itens visíveis; se a busca excede, mostra mensagem "Refine a busca".
- **Dados de 24h ausentes em novo tenant**: KPI cards exibem `—` em vez de `0` quando não há dados suficientes para calcular delta.
- **Custo quando modelo não mapeado**: se um modelo não está no mapping de pricing, o custo é mostrado como `—` (não `$0.00`) com tooltip "modelo sem pricing mapeado".
- **Timestamp futuro** (drift de clock): exibir com ícone de alerta em vez de falhar.
- **Input/output >8 KB**: truncar no servidor e marcar `[truncado]` no UI com tamanho original; nunca enviar >16 KB no payload.
- **Tenant desativado**: mantém acesso read-only no admin (auditoria); novas mensagens são bloqueadas pelo roteador (comportamento existente).
- **Sessão admin expirada durante navegação**: qualquer 401 de endpoint deve redirecionar para `/login` com flash message preservando a URL original como `?next=`.
- **Feed de atividade com 0 eventos**: mostra estado vazio amigável, não uma área em branco.
- **Heatmap de erros sem dados no período**: cada célula = 0, cor neutra, tooltip "sem erros registrados"; não deve renderizar vazio ou erro.
- **Concorrência em "Fechar conversa"**: se outra sessão já fechou a conversa, o UI mostra erro 409 e recarrega o estado.
- **Routing decision sem match de regra**: a UI mostra "regra: default" e destaca como categoria "sem regra explícita" no breakdown.

## Requirements *(mandatory)*

### Functional Requirements

**Navegação e layout**

- **FR-001**: O admin MUST expor um menu lateral com 8 itens de navegação: Overview, Conversas, Trace Explorer, Performance AI, Agentes, Roteamento, Tenants, Auditoria.
- **FR-002**: O admin MUST expor um seletor global de tenant no cabeçalho com opção "Todos os tenants" (default) e um item por tenant ativo; a seleção MUST propagar como filtro para todas as abas via parâmetro de URL, sendo a única fonte de verdade.
- **FR-003**: O admin MUST operar em dark mode como única opção visual na v1.

**Aba Overview**

- **FR-010**: O sistema MUST exibir 6 KPI cards no Overview: Conversas Ativas, Mensagens Hoje, Containment Rate, Latência Média, Quality Score e Erros.
- **FR-011**: Cada KPI card MUST mostrar valor atual, label, sparkline das últimas 24h e delta vs. mesmo intervalo do dia anterior, com codificação de cor conforme os seguintes thresholds: Quality Score — verde ≥85, âmbar 70–84, vermelho <70; Latência P95 — verde ≤2 s, âmbar 2–5 s, vermelho >5 s; Containment Rate — verde ≥75%, âmbar 60–74%, vermelho <60%; Fallback Rate — verde <10%, âmbar 10–20%, vermelho >20%; Erros (24h) — verde 0, âmbar 1–5, vermelho >5. Cards de volume (Conversas Ativas, Mensagens Hoje) NOT MUST receber cor por valor absoluto — apenas delta vs. dia anterior (verde se positivo; âmbar/vermelho se queda ≥30% / ≥50%). Dados insuficientes para delta MUST exibir `—`.
- **FR-012**: O Overview MUST exibir um Live Activity Feed com até 50 eventos recentes (nova conversa, SLA breach, fallback de intent, erro de pipeline, AI resolveu sem handoff), com auto-refresh a cada 15 segundos.
- **FR-013**: Cada linha do feed MUST ser clicável para navegar ao contexto (conversa ou trace).
- **FR-014**: O Overview MUST exibir um painel System Health verificando API, Postgres, Redis, Evolution API e Phoenix com polling de 30 segundos.
- **FR-015**: O Overview MUST exibir uma tabela Saúde por Tenant com conversas ativas, QS médio, latência P50 e status geral calculado hierarquicamente: **vermelho** se qualquer KPI do tenant (QS, Latência P95, Containment, Fallback, Erros) for vermelho OU última mensagem processada há mais de 15 min OU taxa de erro em janela rolling de 5 min >10%; **âmbar** se não é vermelho e ao menos um KPI em âmbar; **verde** caso contrário. Tenants com zero tráfego em 24 h MUST ser exibidos com status "—" (neutro), não verde.

**Aba Conversas**

- **FR-020**: O sistema MUST exibir uma lista de conversas paginada por cursor, ordenada por SLA breach primeiro, depois "em risco", depois atividade recente descendente.
- **FR-021**: A busca de conversas MUST casar, via ILIKE case-insensitive, contra `customers.display_name` OU `messages.content` no tenant filtrado; migração para `tsvector + GIN` fica como follow-up quando ocorrer o primeiro de: >10k conversas ativas, P95 da busca >500 ms, ou necessidade de ranking por relevância.
- **FR-022**: Cada item da lista MUST mostrar: avatar com iniciais, nome, preview da última mensagem (1 linha truncada), timestamp, intent atual, quality score e indicador de SLA quando aplicável.
- **FR-023**: Ao selecionar uma conversa, o sistema MUST exibir a thread completa com bolhas visualmente distintas para inbound (cliente), AI outbound e handoff humano. Mensagens de handoff humano são derivadas do campo de origem existente da tabela `messages` (quando a mensagem foi enviada por atendente humano via WhatsApp externo e capturada pelo webhook do Evolution API); o admin apenas renderiza essas mensagens — NOT MUST oferecer envio. Label da bolha humana: nome do operador quando disponível em `messages.metadata.operator_name`, com fallback para "Atendente humano".
- **FR-024**: Cada bolha AI outbound MUST expor metadados expansíveis por hover: latência, tokens, quality score e link direto para o trace associado.
- **FR-025**: O sistema MUST exibir separador visual entre mensagens quando o intent da conversa muda.
- **FR-026**: O painel de perfil do contato MUST exibir: nome, tenant, canal, status da conversa atual, intent atual com confidence, QS médio, contagem de mensagens, histórico resumido, tags e ações (ver traces, fechar conversa).
- **FR-027**: O input de mensagem MUST estar desabilitado com placeholder indicando "somente leitura" (envio é via WhatsApp externo).
- **FR-028**: O operador MUST conseguir fechar uma conversa via ação no perfil; a mudança de status é persistida e refletida na lista.

**Aba Trace Explorer**

- **FR-030**: O sistema MUST persistir, para cada mensagem processada pelo pipeline, um registro de trace (parent) com 12 registros de step (filhos), cobrindo: webhook_received, route, customer_lookup, conversation_get, save_inbound, build_context, classify_intent, generate_response, evaluate_response, output_guard, save_outbound, deliver.
- **FR-031**: Cada step persistido MUST incluir: ordem, nome, duração em ms, status (success/error/skipped), input (objeto estruturado, até 8 KB), output (objeto estruturado, até 8 KB), mensagem de erro quando aplicável.
- **FR-032**: O sistema MUST propagar o `trace_id` gerado pelo SDK de tracing existente para correlação entre os steps persistidos e spans externos do ecossistema de observabilidade.
- **FR-033**: A falha em persistir trace/steps NOT MUST bloquear a entrega da resposta ao usuário final (persistência fire-and-forget com log de falha).
- **FR-034**: Inputs e outputs com tamanho superior a 8 KB MUST ser truncados no servidor e marcados para a UI como `[truncado — tamanho original X KB]`.
- **FR-035**: A lista de traces MUST ser filtrável por tenant, status, duração mínima e período, com paginação cursor-based.
- **FR-036**: Cada linha da lista MUST exibir: hora, contato, intent, duração total, custo estimado, status.
- **FR-037**: A página de detalhe do trace MUST exibir um waterfall com barras proporcionais à duração relativa de cada step e destaque visual para o step dominante (>60% do total).
- **FR-038**: Cada step MUST ser expansível mostrando input, output, modelo usado, tokens in/out, tool calls e — quando error — tipo, mensagem e stack trace.
- **FR-039**: Steps posteriores a um erro MUST ser marcados `skipped` e exibidos com estilo visual de inatividade.
- **FR-040**: A página de detalhe do trace MUST incluir links para: conversa associada e navegação reversa à lista.

**Aba Performance AI**

- **FR-050**: O sistema MUST calcular e expor, por período selecionável (1d, 7d, 30d) e por tenant: containment rate, QS médio, P95 de latência e fallback rate. Uma mensagem é contabilizada como **fallback** quando ocorre qualquer uma das condições: (i) intent classificado como `fallback`, `unknown` ou `out_of_scope` no step `classify_intent`; (ii) `intent_confidence < 0.5` registrado por `classify_intent`; (iii) resposta marcada `safety_refused` por `output_guard`; (iv) handoff humano iniciado pelo pipeline. Mensagens onde o roteador decidiu `DROP`, `LOG_ONLY` ou `BYPASS_AI` NOT MUST ser contabilizadas no denominador do fallback rate (não passaram pelo pipeline de IA).
- **FR-051**: O sistema MUST exibir distribuição de intents no período (barras horizontais ordenadas por volume) com codificação adicional para fallback rate por intent.
- **FR-052**: O sistema MUST exibir tendência de quality score (P50 e P95) ao longo do período como gráfico de área + linha, com linha de referência no threshold crítico.
- **FR-053**: O sistema MUST exibir latência por step do pipeline em stacked horizontal bars com segmentos P50, P95-P50, P99-P95.
- **FR-054**: O sistema MUST exibir heatmap de erros em grade 24h×7d, com intensidade proporcional ao volume e toggle "Erros" / "Fallbacks".
- **FR-055**: O sistema MUST exibir custo agregado por tenant e por modelo, com sparkline de 30 dias.
- **FR-056**: O custo por mensagem MUST ser calculado como `tokens_in × preço_in + tokens_out × preço_out`, com preços por modelo em um mapping documentado no código.
- **FR-057**: As queries de agregação pesada do Performance AI MUST ser cacheadas por 5 minutos.

**Aba Agentes**

- **FR-060**: O sistema MUST listar agentes com filtro por tenant, exibindo estado habilitado/desabilitado.
- **FR-061**: O detalhe do agente MUST ter 3 tabs: Configuração (modelo, temperatura, max_tokens, tools), Prompts (versões + diff) e Métricas (KPIs vs. média da plataforma).
- **FR-062**: A tab Prompts MUST permitir selecionar duas versões de prompt e exibir diff side-by-side com linhas adicionadas/removidas.
- **FR-063**: O visualizador de prompt MUST exibir as seções `safety_prefix`, `system_prompt` e `safety_suffix` visualmente distintas, preservando whitespace.
- **FR-064**: O admin MUST conseguir ativar uma versão antiga de prompt (mudar `active_prompt_id` do agente) com confirmação explícita.

**Aba Roteamento**

- **FR-070**: O sistema MUST persistir cada decisão tomada pelo roteador para cada mensagem recebida, incluindo: tipo (RESPOND / DROP / LOG_ONLY / BYPASS_AI / EVENT_HOOK), razão, snapshot da regra que matchou, snapshot dos MessageFacts, `trace_id` e tenant.
- **FR-071**: A persistência da decisão MUST ser fire-and-forget — falha NOT MUST bloquear o roteamento em si.
- **FR-072**: O sistema MUST expor o estado atual das regras carregadas em memória por tenant (prioridade, condições, ação, agente alvo) via endpoint dedicado.
- **FR-073**: A página de Roteamento MUST exibir: painel de regras ativas, donut de distribuição de tipos de decisão no período, tabela de decisões recentes (incluindo DROPs) e top-N razões de DROP/BYPASS.
- **FR-074**: Cada decisão MUST ser expansível mostrando MessageFacts e regra que matchou em JSON.

**Aba Tenants**

- **FR-080**: O sistema MUST listar tenants com nome, slug, status, conversas ativas, QS médio e timestamp do último webhook.
- **FR-081**: O detalhe do tenant MUST incluir configuração, agentes associados (com links), métricas 7d e toggle de `enabled`.
- **FR-082**: O admin MUST conseguir ativar/desativar um tenant com confirmação; o roteador MUST respeitar o novo estado na próxima mensagem.

**Aba Auditoria**

- **FR-090**: O sistema MUST exibir timeline paginada de eventos da tabela de auditoria com cursor-based pagination (50/página).
- **FR-091**: Cada evento MUST exibir: hora, ação, usuário (email), IP e detalhes.
- **FR-092**: O sistema MUST permitir filtrar por tipo de ação, por usuário e por período (1d, 7d, 30d).
- **FR-093**: Eventos de segurança com padrões anômalos (3+ `login_failed` do mesmo IP em 24h, `rate_limit_hit`) MUST ter destaque visual distinto.

**Não-funcionais, segurança e retenção**

- **FR-100**: Todos os endpoints admin MUST requerer autenticação (cookie JWT existente do épico 007). 401 MUST redirecionar para login preservando a URL original.
- **FR-101**: Todos os dados expostos no admin MUST ser lidos via pool de banco com bypass de RLS (acesso cross-tenant), nunca via pool aplicacional.
- **FR-102**: As novas tabelas de trace, trace steps e routing decisions MUST ter retenção configurável (default 90 dias para routing, 30 dias para traces), aplicada por job de retenção existente.
- **FR-103**: O sistema MUST manter lista denormalizada de "última mensagem" (id, timestamp, preview 200 chars) na tabela de conversas para garantir listagem <100ms em >10k conversas.
- **FR-104**: A refatoração do pipeline para emitir os trace steps NOT MUST quebrar os testes existentes do épico 005 (pipeline) e épico 004 (router); 100% da suíte existente MUST passar antes do merge.

### Key Entities *(include if feature involves data)*

- **Trace**: representa a execução completa do pipeline de IA para uma mensagem recebida. Atributos-chave: id, `trace_id` (correlação com telemetria externa), tenant, mensagem associada, conversa, duração total, custo USD, status geral (ok/error), timestamps de início e fim. Relaciona-se com Trace Step (1:N) e com Mensagem (1:1).
- **Trace Step**: representa uma das 12 etapas do pipeline dentro de um trace. Atributos-chave: trace, ordem (1–12), nome, duração, status (success/error/skipped), input (JSON estruturado truncado), output (JSON estruturado truncado), erro (tipo + mensagem + stack opcional). Relaciona-se com Trace (N:1).
- **Routing Decision**: decisão tomada pelo roteador MECE para cada mensagem recebida. Atributos-chave: tenant, mensagem externa, hash do telefone do cliente, tipo (RESPOND / DROP / LOG_ONLY / BYPASS_AI / EVENT_HOOK), razão textual, snapshot da regra que matchou (JSON), snapshot dos `MessageFacts` (JSON), `trace_id` para correlação, timestamp.
- **Conversation (enriquecida)**: entidade existente, acrescida de campos denormalizados: id da última mensagem, timestamp da última mensagem, preview da última mensagem (200 chars). Mantém relação com Customer (N:1), ConversationState (1:1) e Messages (1:N) conforme domínio existente.
- **Activity Event**: entidade virtual (derivada, não persistida) — composição de: nova conversa criada, conversa fechada sem handoff, SLA em breach, fallback de intent, erro em trace. Gerada por consultas ad-hoc ao ler o Live Activity Feed.
- **Cost Map**: mapeamento modelo → preço por 1k tokens de entrada e saída. Atributos-chave: nome do modelo, preço por 1k tokens in, preço por 1k tokens out. Fonte: constante em código (v1); evolutivo para tabela editável quando >3 modelos ativos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um operador consegue localizar e abrir o thread completo de uma conversa específica (filtrada por nome do contato ou trecho de mensagem) em menos de **30 segundos**, sem usar `psql` nem `journalctl`.
- **SC-002**: Um engenheiro consegue identificar a etapa dominante em latência de um trace específico (e ver seu input/output) em menos de **30 segundos** a partir de um `trace_id` ou nome do contato.
- **SC-003**: O tempo total para responder "está tudo bem na plataforma?" cai de ~5 minutos (abrir 4 painéis externos) para **menos de 10 segundos** (Overview único).
- **SC-004**: 95% das requisições a endpoints de listagem (conversas, traces, audit) retornam em **menos de 300 ms** com dataset de 10k conversas + 50k traces; 95% das requisições a endpoints de agregação pesada (Performance AI) retornam em **menos de 2 s** no pior caso e **menos de 200 ms** quando servidos de cache.
- **SC-005**: A lista de conversas da aba Conversas renderiza em **menos de 100 ms** server-side com dataset de 10k conversas ativas.
- **SC-006**: A instrumentação do pipeline adiciona overhead de no máximo **10 ms** ao tempo total de resposta do pipeline (p95), medido por comparação A/B em staging.
- **SC-007**: Zero testes da suíte existente do pipeline e do router quebram com a refatoração de instrumentação — suíte 100% verde antes do merge.
- **SC-008**: Usuários conseguem identificar uma mensagem descartada pelo roteador (`DROP` / `LOG_ONLY`) e a razão em menos de **1 minuto** a partir do número de telefone (hash) e janela de tempo.
- **SC-009**: Cobertura do admin evoluído: ao final do épico, **nenhum incidente de produção dos últimos 30 dias** precisaria ter sido investigado via `psql` ou `journalctl` (revisão retroativa).
- **SC-010**: O episódio mais lento do fluxo de debugging de regressão de prompt cai de "horas" (hoje) para **menos de 15 minutos** (do reporte ao diagnóstico da etapa problemática).
- **SC-011**: O custo operacional por conversa (calculado via USD de tokens + fixo) fica visível e auditável por tenant/modelo, habilitando decisões de otimização; meta qualitativa: uma decisão de ajuste de prompt/modelo no próximo trimestre é justificada com dados do Performance AI.
- **SC-012**: 100% das decisões de roteamento das últimas 24h ficam persistidas e consultáveis via admin (hoje: 0%).

## Assumptions

- **Usuários**: o admin é usado por equipe interna (operadores, engenheiros, produto, liderança técnica, segurança). Entre 3 e 10 usuários simultâneos no pico. Todos operam em desktop com conexão estável.
- **Épicos anteriores shipped**: 002 (observabilidade OTel/Phoenix), 004 (router MECE), 005 (pipeline 12 steps), 006 (retention cron), 007 (fundação admin — sidebar, login, pool admin, dbmate). Todos já no `main` do repo prosauai.
- **Stack frontend fixa**: Next.js 15 App Router + shadcn/ui + Tailwind v4 + Recharts + TanStack Query + lucide-react. Sem introdução de Tremor, MUI ou outras libs de UI.
- **Dark mode único na v1**: sem toggle light; tokens OKLCH já configurados.
- **Autenticação reaproveitada**: cookie JWT `admin_token` existente (épico 007). Migração para httpOnly + refresh fica como follow-up documentado, fora do escopo.
- **Pool de DB**: todas as queries admin via `pool_admin` (BYPASSRLS). Nenhuma role nova.
- **Schema das novas tabelas**: em `public.*` (drift conhecido documentado em ADR-024 do épico 007); cleanup para schema `prosauai` segue em backlog.
- **Branch do épico**: `epic/prosauai/008-admin-evolution` já existe no repo externo; o trabalho aproveita a branch existente.
- **Pricing por modelo**: hardcoded em código (constante versionada). Tabela DB editável vira backlog quando >3 modelos ativos.
- **Correlação trace_id**: reaproveita o `trace_id` já gerado pelo SDK OpenTelemetry ativo (épico 002); sem código novo de geração.
- **Integração Phoenix out-of-scope**: não consultamos API do Phoenix; apenas espelhamos `trace_id` para cross-reference manual. Enrichment via Phoenix vira épico futuro.
- **Persistência fire-and-forget**: falhas em persistir trace steps / routing decisions NOT devem bloquear delivery da resposta ao cliente final (padrão já usado pelo exporter do Phoenix).
- **Activity feed via polling**: v1 usa polling a 15 s; SSE e Socket.io ficam como evolução quando >10 admins simultâneos ou latência de feed > tolerável.
- **Busca de conversas**: ILIKE em `customers.display_name` e `messages.content` na v1; migração para `tsvector + GIN` quando >10k conversas ou P95 > 500 ms.
- **Retenção**: 30 dias para traces / trace steps, 90 dias para routing decisions (default, configurável via env). `retention-cron` do épico 006 é estendido.
- **Apetite**: excede deliberadamente os 3 semanas do Shape Up puro. Janela planejada: 6–8 semanas com cut-line explícito (cortar Agentes/Routing/Tenants/Audit para épico 009 se passar de 5 semanas antes de terminar Trace Explorer).
- **Cross-referência com pitch**: decisões específicas de arquitetura, ADRs novos e mitigações de risco estão registradas em `pitch.md` (Captured Decisions e Resolved Gray Areas) e `decisions.md`; este spec deliberadamente fica em nível de capacidade de negócio/operação.

---

handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificado. 5 ambiguidades resolvidas autonomamente (modo dispatch): (1) thresholds específicos verde/âmbar/vermelho para todos os KPIs do Overview e tabela Saúde por Tenant; (2) contradição ILIKE vs full-text na busca resolvida para ILIKE em v1 com critério de migração para tsvector+GIN; (3) definição formal de fallback (4 condições + exclusão de DROP/LOG_ONLY/BYPASS_AI do denominador); (4) regra hierárquica para status geral por tenant (vermelho > âmbar > verde, com status neutro '—' para tenants sem tráfego em 24h); (5) origem das bolhas de handoff humano (campo existente na tabela messages, renderização only — admin permanece read-only). Plan deve focar em arquitetura da persistência de traces + trace_steps + routing_decisions, refactor do Pipeline.execute com fire-and-forget INSERT, extensão do retention-cron, e separação clara de endpoints backend vs. frontend."
  blockers: []
  confidence: Alta
  kill_criteria: "Este spec fica inválido se: (a) pipeline de 12 etapas sofre refactor estrutural que muda os nomes dos steps antes do início da F1; (b) decisão de descontinuar o admin (ex: OEM de ferramenta externa tipo Retool); (c) cap de apetite cair para <3 semanas, forçando reescopo de épico 008 para só Conversas + Trace Explorer; (d) tenant health rules ou thresholds de KPI forem invalidados por benchmark real (ex: QS médio do Ariel já está em 75, invalidando threshold 'verde ≥85')."
