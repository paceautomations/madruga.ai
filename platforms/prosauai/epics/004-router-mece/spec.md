# Feature Specification: Router MECE — Classificação Pura + Regras Externalizadas + Agent Resolution

**Feature Branch**: `epic/prosauai/004-router-mece`
**Created**: 2026-04-10
**Status**: Draft
**Input**: Refatorar o router do prosauai separando classificação de mensagens (fatos puros) de regras de roteamento (configuração externa), resolver agent_id que está sempre None, e garantir propriedade MECE por construção em 4 camadas.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Classificação MECE de Mensagens (Priority: P1)

O sistema classifica cada mensagem recebida via WhatsApp em um conjunto de fatos ortogonais e mutuamente exclusivos, sem ambiguidade. Cada mensagem produz exatamente um conjunto de fatos que descreve: canal (individual ou grupo), tipo de evento, tipo de conteúdo, se é mensagem própria, se há menção ao bot, se é duplicata, e se a conversa está em modo de atendimento humano.

**Why this priority**: Esta é a fundação de todo o roteamento. Se a classificação for ambígua ou incompleta, todas as decisões downstream herdam o erro. A propriedade MECE (Mutually Exclusive, Collectively Exhaustive) garante que nenhuma mensagem cai em "limbo" e nenhuma mensagem casa com dois caminhos conflitantes.

**Independent Test**: Pode ser testado isoladamente enviando qualquer payload de mensagem e verificando que o resultado da classificação é determinístico, completo e não-ambíguo. Entrega valor imediato: elimina os bugs estruturais do enum `MessageRoute` atual que conflata tipo, estado e ação.

**Acceptance Scenarios**:

1. **Given** uma mensagem individual de texto de um contato externo, **When** o sistema classifica a mensagem, **Then** os fatos retornados indicam canal=individual, tipo_evento=message, tipo_conteudo=text, from_me=false, has_mention=false.
2. **Given** uma mensagem em grupo com menção ao bot, **When** o sistema classifica, **Then** os fatos indicam canal=group, has_mention=true, com o group_id preenchido.
3. **Given** uma reação (emoji) a uma mensagem, **When** o sistema classifica, **Then** os fatos indicam tipo_conteudo=reaction.
4. **Given** uma mensagem com `from_me=true` (eco do próprio bot), **When** o sistema classifica, **Then** os fatos indicam from_me=true.
5. **Given** uma mensagem duplicada (já processada anteriormente), **When** o sistema classifica, **Then** os fatos indicam is_duplicate=true.
6. **Given** uma mensagem individual de contato que está em atendimento humano (handoff), **When** o sistema classifica, **Then** os fatos indicam conversation_in_handoff=true.
7. **Given** um evento de entrada/saída de membro em grupo, **When** o sistema classifica, **Then** os fatos indicam is_membership_event=true e tipo_evento=group_membership.
8. **Given** qualquer combinação inválida de fatos (ex: has_mention=true em canal individual), **When** o sistema tenta construir os fatos, **Then** a construção é rejeitada com erro de validação.

---

### User Story 2 — Regras de Roteamento Externalizadas por Tenant (Priority: P1)

O operador do sistema configura as regras de roteamento de cada tenant (cliente) em um arquivo de configuração externo, sem necessidade de alterar código ou fazer deploy. Cada tenant possui seu próprio conjunto de regras com prioridades, e o sistema garante que as regras são mutuamente exclusivas (sem sobreposição).

**Why this priority**: Sem externalização, qualquer mudança de regra de negócio (ex: "mensagem individual vai para vendas em vez de suporte") exige alteração de código, PR, CI, deploy. Com regras externas, o ciclo de mudança cai de horas para minutos. Isso desbloqueia o admin panel (epic 009) e a migração para banco de dados (epic 006).

**Independent Test**: Pode ser testado criando/editando um arquivo de configuração YAML e verificando que o sistema carrega as regras corretamente, rejeita configurações inválidas, e aplica as regras na ordem de prioridade.

**Acceptance Scenarios**:

1. **Given** um arquivo de configuração válido com 9 regras para um tenant, **When** o sistema carrega a configuração, **Then** todas as 9 regras são carregadas e validadas com sucesso.
2. **Given** um arquivo de configuração sem regra padrão (default), **When** o sistema tenta carregar, **Then** a carga é rejeitada com erro explicativo ("configuração sem regra default").
3. **Given** um arquivo com duas regras de mesma prioridade, **When** o sistema tenta carregar, **Then** a carga é rejeitada com erro ("prioridade duplicada").
4. **Given** um arquivo com duas regras cujas condições se sobrepõem (mesma mensagem casaria com ambas), **When** o sistema valida as regras, **Then** a validação detecta a sobreposição e rejeita a configuração.
5. **Given** dois tenants distintos (Ariel e ResenhAI), **When** o sistema carrega as configurações, **Then** cada tenant opera com seu próprio conjunto de regras independentes.
6. **Given** um arquivo com campo desconhecido ou tipo inválido, **When** o sistema tenta carregar, **Then** a carga é rejeitada com erro específico do campo.

---

### User Story 3 — Resolução de Agent por Regra (Priority: P1)

Quando o sistema decide que uma mensagem deve ser respondida (ação RESPOND), ele identifica qual agente de IA específico deve tratar aquela mensagem. O agente pode ser definido diretamente na regra de roteamento ou, na ausência, usar o agente padrão configurado para o tenant.

**Why this priority**: Hoje o campo `agent_id` é sempre None — o epic 005 (Conversation Core + LLM) depende diretamente de receber um agent_id válido para saber qual modelo/prompt usar. Sem esta resolução, o 005 teria que hardcodar um default, perdendo toda a flexibilidade do roteamento configurável.

**Independent Test**: Pode ser testado configurando regras com e sem agent específico, e verificando que o Decision resultante sempre carrega um agent_id válido para ações RESPOND.

**Acceptance Scenarios**:

1. **Given** uma regra RESPOND com agent específico configurado, **When** a mensagem casa com essa regra, **Then** a decisão carrega o agent_id da regra.
2. **Given** uma regra RESPOND sem agent específico e um tenant com agent padrão configurado, **When** a mensagem casa com essa regra, **Then** a decisão carrega o agent_id padrão do tenant.
3. **Given** uma regra RESPOND sem agent e um tenant sem agent padrão, **When** a mensagem casa com essa regra, **Then** o sistema reporta erro claro ("tenant sem agent padrão configurado").
4. **Given** uma regra LOG_ONLY ou DROP, **When** a mensagem casa com essa regra, **Then** a decisão não carrega agent_id (campo não existe nesse tipo de decisão).

---

### User Story 4 — Decisões Tipadas por Ação (Priority: P2)

O sistema retorna decisões de roteamento como tipos distintos por ação (responder, apenas logar, descartar, bypass para humano, hook de evento), cada um carregando apenas os campos válidos para aquela ação. Consumidores downstream processam cada tipo de decisão de forma exaustiva — o compilador/linter garante que nenhum tipo foi esquecido.

**Why this priority**: Elimina uma classe inteira de bugs onde o código tenta acessar `agent_id` de uma decisão DROP (que não tem agente) ou `drop_reason` de uma decisão RESPOND (que não tem motivo de descarte). Erros que hoje seriam descobertos em produção passam a ser detectados em tempo de desenvolvimento.

**Independent Test**: Pode ser testado verificando que cada tipo de decisão carrega apenas seus campos válidos e que um match/case sobre todos os tipos é exaustivo (analisador estático prova completude).

**Acceptance Scenarios**:

1. **Given** uma decisão de tipo RESPOND, **When** o consumidor inspeciona a decisão, **Then** ela contém agent_id, matched_rule, e opcionalmente reason.
2. **Given** uma decisão de tipo DROP, **When** o consumidor inspeciona, **Then** ela contém matched_rule e reason obrigatório, mas não contém agent_id.
3. **Given** uma decisão de tipo BYPASS_AI, **When** o consumidor inspeciona, **Then** ela contém target (ex: handoff) e matched_rule.
4. **Given** uma decisão de tipo EVENT_HOOK, **When** o consumidor inspeciona, **Then** ela contém target (ex: handler de membership) e matched_rule.
5. **Given** um consumidor que trata apenas 4 dos 5 tipos de decisão, **When** análise estática é executada, **Then** o analisador reporta que o tratamento não é exaustivo.

---

### User Story 5 — Detecção de Menção Tenant-Aware (Priority: P2)

O sistema detecta se o bot foi mencionado em uma mensagem de grupo usando as configurações específicas de cada tenant (identificador LID, número de telefone, palavras-chave). A detecção é configurável por tenant sem alteração de código.

**Why this priority**: Cada tenant (Ariel, ResenhAI) tem identificadores de bot diferentes. A detecção de menção hardcoded no código impede operação multi-tenant correta. Externalizar os matchers como dados do tenant mantém a classificação pura e configurável.

**Independent Test**: Pode ser testado com mensagens de grupo contendo diferentes tipos de menção (JID, telefone, keyword) para diferentes tenants, verificando que cada tenant detecta corretamente as suas menções.

**Acceptance Scenarios**:

1. **Given** um tenant configurado com LID opaque e uma mensagem de grupo mencionando esse LID, **When** o sistema verifica menção, **Then** retorna has_mention=true.
2. **Given** um tenant configurado com número de telefone e uma mensagem mencionando o JID correspondente, **When** o sistema verifica, **Then** retorna has_mention=true.
3. **Given** um tenant configurado com keyword "bot" e uma mensagem contendo "oi bot", **When** o sistema verifica, **Then** retorna has_mention=true.
4. **Given** uma mensagem de grupo sem nenhuma menção ao bot do tenant, **When** o sistema verifica, **Then** retorna has_mention=false.
5. **Given** dois tenants com keywords diferentes, **When** a mesma mensagem é avaliada para cada tenant, **Then** o resultado pode diferir conforme as configurações de cada um.

---

### User Story 6 — Verificação e Explicação de Configuração (Priority: P2)

O operador ou desenvolvedor verifica se uma configuração de roteamento é válida antes de commitá-la, e pode simular qual regra casaria para um conjunto específico de fatos. Isso funciona tanto localmente (pre-commit) quanto em CI.

**Why this priority**: Configuração YAML sem validação é bomba-relógio — erros silenciosos em produção. A verificação local e em CI fecha o loop de qualidade: configuração inválida não entra no repositório.

**Independent Test**: Pode ser testado executando o verificador contra arquivos válidos e inválidos, e o explicador contra cenários específicos de fatos.

**Acceptance Scenarios**:

1. **Given** um arquivo de configuração válido, **When** o operador executa a verificação, **Then** o sistema reporta sucesso com contagem de regras carregadas.
2. **Given** um arquivo com sobreposição de regras, **When** o operador executa a verificação, **Then** o sistema reporta erro detalhado indicando quais regras se sobrepõem.
3. **Given** um conjunto de fatos (ex: canal=individual, from_me=false), **When** o operador pede explicação para um tenant específico, **Then** o sistema retorna qual regra casou e por quê.
4. **Given** um commit que altera arquivos de configuração de roteamento, **When** o hook de pre-commit executa, **Then** a verificação roda automaticamente e bloqueia o commit se houver erro.

---

### User Story 7 — Observabilidade do Roteamento (Priority: P3)

Para cada mensagem processada, o sistema registra em spans de observabilidade separados a etapa de classificação e a etapa de decisão, com atributos estruturados que permitem filtragem e análise no painel de monitoramento (Phoenix). Logs estruturados incluem a regra que casou em cada decisão.

**Why this priority**: Observabilidade é essencial para diagnóstico em produção, mas não bloqueia funcionalidade. É um diferenciador de maturidade operacional que complementa o sistema de tracing já entregue no epic 002.

**Independent Test**: Pode ser testado enviando mensagens e verificando que os spans aparecem corretamente no sistema de tracing, com os atributos esperados.

**Acceptance Scenarios**:

1. **Given** uma mensagem processada pelo router, **When** o operador consulta o sistema de tracing, **Then** encontra dois spans irmãos (classificação e decisão) sob o span principal do webhook.
2. **Given** uma decisão RESPOND, **When** o operador inspeciona o span de decisão, **Then** encontra os atributos matched_rule, action e agent_id.
3. **Given** uma decisão DROP, **When** o operador inspeciona o span de decisão, **Then** encontra os atributos matched_rule, action e drop_reason.
4. **Given** qualquer mensagem processada, **When** o operador consulta os logs estruturados, **Then** cada entrada inclui matched_rule como campo.

---

### User Story 8 — Migração Transparente do Router Legado (Priority: P3)

A substituição completa do router legado (enum MessageRoute, funções route_message, _is_bot_mentioned, _is_handoff_ativo) é feita de forma que todas as 26 fixtures reais de mensagens capturadas no epic 003 continuam produzindo as mesmas ações equivalentes no novo sistema.

**Why this priority**: Garantia de não-regressão. É a "rede de segurança" que prova que o refactor preserva o comportamento existente enquanto melhora a arquitetura.

**Independent Test**: Pode ser testado executando todas as 26 fixtures reais contra o novo router e verificando que cada uma produz a mesma ação que o router legado.

**Acceptance Scenarios**:

1. **Given** as 26 fixtures reais de mensagens capturadas do epic 003, **When** cada fixture é processada pelo novo router, **Then** a ação resultante é equivalente à ação do router legado.
2. **Given** a migração completa, **When** uma busca por referências ao enum legado (MessageRoute, route_message, _is_bot_mentioned, _is_handoff_ativo) é executada no código, **Then** zero ocorrências são encontradas.
3. **Given** a migração completa, **When** uma busca por "ParsedMessage" é executada no código e nos testes, **Then** zero ocorrências são encontradas (rename para InboundMessage concluído).

---

### Edge Cases

- O que acontece quando uma mensagem não casa com nenhuma regra configurada? → A regra default obrigatória sempre captura; configuração sem default é rejeitada na carga.
- O que acontece quando o Redis está indisponível para consultar estado de duplicata/handoff? → O carregamento de estado falha e o erro é propagado ao caller (fail-fast, sem classificação com dados incompletos).
- O que acontece quando um tenant não tem agent padrão e a regra casada é RESPOND sem agent? → Erro explícito em runtime + detectável previamente via verificação de configuração.
- O que acontece quando a chave Redis de handoff não existe (nenhum epic ainda escreve essa chave)? → Fallback seguro para false (conversa não está em handoff) — contrato aberto documentado para epics futuros.
- O que acontece com eventos de protocolo desconhecidos da Evolution API? → Classificados como event_kind=unknown, caem na regra default.
- O que acontece quando dois tenants compartilham a mesma instância de WhatsApp? → Arquiteturalmente impedido — cada instância é vinculada a exatamente 1 tenant (invariante do epic 003).
- O que acontece quando um tenant declarado em `tenants.yaml` não tem arquivo de roteamento em `config/routing/`? → Fail-fast no startup — serviço recusa iniciar. Detectável previamente via `router verify`.
- O que acontece quando o Redis responde lento (timeout) mas não está completamente indisponível? → Mesmo comportamento que indisponibilidade — `StateSnapshot.load()` propaga o timeout como erro ao caller (fail-fast). Não há fallback com dados stale.

## Clarifications

### Session 2026-04-10

- Q: A recarga de configuração de roteamento é feita apenas no startup ou suporta hot reload (file watcher/API trigger)? → A: Startup-only para epic 004. YAML é commitado em git, mudanças passam por PR → merge → restart do serviço. Hot reload fica para epic 006/009 (config DB-backed habilita mudanças em runtime). "Zero deploy" significa zero alteração de código — restart do serviço após edição de config é aceitável.
- Q: Qual o target de latência p99 para a chamada `route()` no hot-path (por mensagem)? → A: < 5ms p99 total (classify puro <1ms + decide linear <1ms + Redis MGET 2 keys ~2-3ms). Suficiente para webhook handler com throughput esperado.
- Q: O que acontece no startup se um tenant declarado em `tenants.yaml` não tem arquivo de configuração de roteamento correspondente? → A: Fail-fast — serviço recusa iniciar. Loader valida que todo tenant ativo tem `config/routing/<slug>.yaml` presente e válido. Detectável previamente via `router verify`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE classificar cada mensagem recebida em um conjunto de fatos ortogonais e determinísticos, sem ambiguidade. Nenhuma combinação válida de fatos pode ser construída que viole as invariantes do domínio (ex: menção em canal individual).
- **FR-002**: O sistema DEVE carregar regras de roteamento a partir de configuração externa (um arquivo por tenant), validando schema, unicidade de prioridades, presença de regra default, e ausência de sobreposição entre regras.
- **FR-003**: O sistema DEVE avaliar as regras em ordem de prioridade (menor número primeiro) e retornar a decisão da primeira regra que casa com os fatos da mensagem. Se nenhuma regra casa, a regra default é aplicada.
- **FR-004**: O sistema DEVE resolver o agent_id para toda decisão de tipo RESPOND: usando o agent da regra se especificado, ou o agent padrão do tenant como fallback. Ausência de ambos gera erro explícito.
- **FR-005**: O sistema DEVE retornar decisões tipadas por ação (responder, logar, descartar, bypass para humano, hook de evento), cada tipo carregando exclusivamente os campos válidos para aquela ação.
- **FR-006**: O sistema DEVE detectar menções ao bot em mensagens de grupo usando configuração específica do tenant (LID, telefone, keywords), sem lógica hardcoded.
- **FR-007**: O sistema DEVE rejeitar configurações com regras sobrepostas — para cada par de regras, se existe alguma combinação de fatos que casaria com ambas, a configuração é inválida.
- **FR-008**: O sistema DEVE prover verificação de configuração executável localmente e em CI, reportando erros com detalhes suficientes para correção.
- **FR-009**: O sistema DEVE prover explicação de roteamento: dado um conjunto de fatos e um tenant, informar qual regra casa e por quê.
- **FR-010**: O sistema DEVE registrar observabilidade em dois spans separados (classificação e decisão) com atributos estruturados, integrados ao sistema de tracing existente.
- **FR-011**: O sistema DEVE renomear o modelo de mensagem de `ParsedMessage` para `InboundMessage`, alinhando código com o modelo de domínio documentado.
- **FR-012**: O sistema DEVE adicionar o campo `default_agent_id` (opcional) ao modelo de tenant, carregando-o da configuração quando presente.
- **FR-013**: O sistema DEVE substituir completamente o router legado (enum MessageRoute, funções route_message, _is_bot_mentioned, _is_handoff_ativo), preservando equivalência comportamental comprovada pelas 26 fixtures reais.
- **FR-014**: O sistema DEVE consultar estado externo (duplicata e handoff) em uma única operação de leitura ao Redis antes da classificação pura, mantendo a classificação livre de efeitos colaterais.
- **FR-015**: O sistema DEVE executar verificação automática de configuração em hook de pre-commit para todos os arquivos de configuração de roteamento alterados.
- **FR-016**: O sistema DEVE carregar configurações de roteamento exclusivamente no startup (lifespan). Recarga em runtime (hot reload) está fora do escopo do epic 004 — mudanças de config exigem restart do serviço.
- **FR-017**: O sistema DEVE validar no startup que todo tenant ativo declarado em `tenants.yaml` possui arquivo de configuração de roteamento correspondente (`config/routing/<slug>.yaml`). Ausência de arquivo causa fail-fast (serviço não inicia).

### Key Entities

- **MessageFacts**: Representação imutável dos fatos extraídos de uma mensagem — canal, tipo de evento, tipo de conteúdo, flags booleanas (from_me, has_mention, is_duplicate, etc.). Ortogonal por construção.
- **Rule**: Uma regra de roteamento com nome, prioridade, condição (quando casa), ação, e opcionalmente agente e motivo.
- **Decision**: O resultado do roteamento — uma decisão tipada por ação que carrega apenas os campos válidos para aquele tipo de decisão. 5 subtipos: Respond, LogOnly, Drop, BypassAI, EventHook.
- **RoutingEngine**: Motor de regras que avalia regras ordenadas por prioridade contra fatos da mensagem.
- **MentionMatchers**: Configuração imutável de detecção de menção por tenant (3 estratégias: LID, telefone, keyword).
- **StateSnapshot**: Estado pré-carregado do Redis (duplicata + handoff) necessário para classificação.
- **Tenant** (existente, estendido): Modelo de tenant que ganha campo `default_agent_id` para resolução de agente.
- **InboundMessage** (renomeado de ParsedMessage): Modelo de mensagem recebida já parseada, servindo como anti-corruption layer contra a API externa.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Toda mensagem recebida é classificada em exatamente 1 conjunto de fatos — comprovado por teste de propriedade que enumera todas as ~400 combinações válidas e verifica unicidade de match.
- **SC-002**: Configuração de roteamento inválida (sem default, prioridade duplicada, sobreposição de regras) é rejeitada 100% das vezes na carga, antes de chegar a produção.
- **SC-003**: Mudanças de regras de roteamento são aplicadas editando configuração externa — zero alterações de código necessárias para mudar comportamento de roteamento.
- **SC-004**: Toda decisão RESPOND carrega agent_id válido — nenhuma decisão RESPOND com agent_id ausente chega ao consumidor downstream.
- **SC-005**: As 26 fixtures reais do epic 003 produzem ações equivalentes no novo router — zero regressão comportamental.
- **SC-006**: Zero referências ao enum legado (MessageRoute), funções legadas (route_message, _is_bot_mentioned, _is_handoff_ativo) ou nome antigo (ParsedMessage) permanecem no código após migração.
- **SC-007**: Verificação de configuração executa em menos de 5 segundos por arquivo, viabilizando uso em pre-commit sem fricção.
- **SC-008**: Cada mensagem processada gera 2 spans de observabilidade (classificação + decisão) com atributos estruturados visíveis no painel de monitoramento.
- **SC-009**: 95+ testes automatizados passando, cobrindo: classificação (unit), regras (unit), engine (integration), property tests (exaustivo + hypothesis), CLI (integration), migração (equivalência com fixtures reais).
- **SC-010**: Análise estática confirma que todo consumidor da decisão trata todos os 5 tipos de ação exaustivamente.
- **SC-011**: A chamada `route()` completa (classify + decide + Redis MGET) executa em < 5ms p99, viabilizando uso no hot-path do webhook sem degradar latência.
- **SC-012**: No startup, o sistema valida que todo tenant ativo tem configuração de roteamento correspondente — ausência causa fail-fast com mensagem de erro clara.

## Assumptions

- O epic 003 (Multi-Tenant Foundation) está shipado e estável — tenant store, parser, auth, debounce, e as 26 fixtures reais são a baseline confiável.
- O epic 002 (Observability) está shipado — o sistema de tracing (OTel + Phoenix) e as convenções de atributos em `conventions.py` já existem e seguem o padrão flat `prosauai.*`.
- O Redis está disponível e operacional em todos os ambientes — a consulta de estado (duplicata/handoff) depende dele.
- A chave Redis de handoff (`handoff:{tenant_id}:{sender_key}`) não é escrita por nenhum código atual — o fallback para false (não está em handoff) é o comportamento esperado até epics futuros (005/011) implementarem a escrita. [VALIDAR] quando epic 005 for especificado.
- Dois tenants reais existem e operam: Ariel (pace-internal) e ResenhAI (resenha-internal). Suas configurações de roteamento são similares mas não idênticas (prioridades diferentes refletindo perfis de uso distintos).
- O campo `default_agent_id` no tenant é opcional (None) — tenants existentes continuam funcionando sem ele. O campo se torna obrigatório na prática quando regras RESPOND sem agent específico existem na configuração.
- A regra de hook pre-commit é executável no ambiente de desenvolvimento dos contribuidores — Python 3.12+ e as dependências do projeto estão disponíveis.
- O escopo de expressividade das condições nas regras é intencionalmente limitado a igualdade + conjunção (sem OR, NOT, regex, glob) — isso é uma decisão de design, não uma limitação.
- A recarga de configuração de roteamento é feita exclusivamente no startup do serviço. Hot reload (file watcher, API trigger) está fora do escopo — fica para epic 006/009 quando a config migrar para banco de dados.

---
handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada com 3 perguntas resolvidas: (1) config reload = startup-only para 004, (2) route() latency < 5ms p99, (3) missing YAML = fail-fast no startup. Spec agora tem 17 FRs, 12 SCs, 8 edge cases. Pronta para planejamento técnico."
  blockers: []
  confidence: Alta
  kill_criteria: "Se o epic 003 (Multi-Tenant Foundation) apresentar regressões que invalidem as 26 fixtures reais, ou se a arquitetura sans-I/O para classify() se provar inviável com o Redis lookup."
