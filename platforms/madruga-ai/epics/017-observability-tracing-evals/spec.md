# Feature Specification: Observability, Tracing & Evals

**Feature Branch**: `epic/madruga-ai/017-observability-tracing-evals`
**Created**: 2026-04-02
**Status**: Draft
**Input**: Adicionar observabilidade real-time, tracing hierarquico e eval scoring ao pipeline L2 automatizado.

## User Scenarios & Testing

### User Story 1 - Monitorar execucao de pipeline em tempo real (Priority: P1)

Como operador do pipeline, quero visualizar o progresso de um pipeline run enquanto ele executa, com status de cada node (pendente, executando, completo, erro), para identificar rapidamente onde o pipeline esta e se algo travou.

**Why this priority**: Sem visibilidade em tempo real, o operador precisa inspecionar logs manualmente ou esperar o pipeline terminar para saber se houve problemas. Essa e a capacidade mais basica de observabilidade.

**Independent Test**: Iniciar um pipeline run e verificar no portal que o status de cada node atualiza automaticamente conforme o pipeline avanca. Um node em execucao deve aparecer como "executando" em ate 10 segundos.

**Acceptance Scenarios**:

1. **Given** um pipeline run em execucao, **When** o operador abre a pagina de observabilidade, **Then** ve a lista de nodes com status atualizado (pendente/executando/completo/erro) e tempo decorrido.
2. **Given** um node falha durante execucao, **When** o operador consulta o dashboard, **Then** o node aparece com status "erro" e uma mensagem resumida do problema.
3. **Given** nenhum pipeline em execucao, **When** o operador abre a pagina, **Then** ve o historico dos ultimos runs com status final e duracao total.

---

### User Story 2 - Rastrear consumo de tokens e custo por run (Priority: P1)

Como operador do pipeline, quero ver quanto cada pipeline run e cada node individual consumiu em tokens (entrada/saida) e custo estimado em USD, para controlar gastos e identificar nodes caros.

**Why this priority**: Custo e a restricao mais critica em operacoes com LLM. Sem visibilidade de custo por node, o operador nao consegue otimizar nem definir budgets.

**Independent Test**: Executar um pipeline run completo e verificar que cada node exibe tokens consumidos e custo estimado. O total do run deve ser a soma dos nodes.

**Acceptance Scenarios**:

1. **Given** um pipeline run completo, **When** o operador abre os detalhes do run, **Then** ve tokens de entrada, tokens de saida e custo estimado (USD) por node e o total do run.
2. **Given** multiplos runs ao longo do tempo, **When** o operador consulta a aba de custos, **Then** ve o custo acumulado por periodo (dia/semana) e tendencia.
3. **Given** um node que nao produziu dados de tokens (ex: falhou antes de completar), **When** exibido no dashboard, **Then** mostra "dados indisponiveis" sem quebrar o calculo total.

---

### User Story 3 - Avaliar qualidade dos artefatos gerados (Priority: P2)

Como operador do pipeline, quero que cada artefato gerado pelo pipeline receba uma avaliacao de qualidade em dimensoes padronizadas, para identificar nodes que consistentemente produzem saida de baixa qualidade e precisam de ajuste.

**Why this priority**: Metricas de custo e tempo medem eficiencia, mas nao qualidade. Evals permitem detectar degradacao de qualidade antes que impacte o produto final.

**Independent Test**: Executar um pipeline run e verificar que cada node recebe scores em 4 dimensoes. Os scores devem ser persistidos e visiveis no portal.

**Acceptance Scenarios**:

1. **Given** um node completa com sucesso, **When** o sistema avalia o artefato, **Then** atribui scores de 0 a 10 em 4 dimensoes: qualidade geral, aderencia a especificacao, completude e eficiencia de custo.
2. **Given** multiplos runs do mesmo node, **When** o operador consulta a aba de evals, **Then** ve a tendencia de scores ao longo do tempo (melhorando, piorando, estavel).
3. **Given** um score abaixo de 5 em qualquer dimensao, **When** exibido no dashboard, **Then** o node e destacado visualmente como "atencao necessaria".

---

### User Story 4 - Visualizar trace hierarquico de um run (Priority: P2)

Como operador do pipeline, quero ver um diagrama tipo waterfall mostrando a sequencia de nodes executados em um run, com duracao relativa de cada um, para entender onde o pipeline gasta mais tempo.

**Why this priority**: O trace hierarquico complementa o monitoramento de status com uma visao temporal que permite identificar gargalos de performance.

**Independent Test**: Executar um pipeline run completo e abrir a visualizacao de trace. Deve exibir cada node como uma barra horizontal proporcional a sua duracao, empilhados verticalmente na ordem de execucao.

**Acceptance Scenarios**:

1. **Given** um pipeline run completo, **When** o operador abre a visualizacao de traces, **Then** ve um waterfall com cada node mostrando inicio, duracao e status.
2. **Given** um pipeline run com node que demorou significativamente mais que os outros, **When** exibido no waterfall, **Then** a barra do node e proporcionalmente maior, facilitando identificar o gargalo.

---

### User Story 5 - Limpeza automatica de dados antigos (Priority: P3)

Como operador do pipeline, quero que dados de observabilidade mais antigos que 90 dias sejam automaticamente removidos, com opcao de exportar antes, para evitar crescimento ilimitado do armazenamento.

**Why this priority**: Sem retencao automatica, o banco de dados cresce indefinidamente. Porem, 90 dias cobre a grande maioria dos casos de analise retroativa.

**Independent Test**: Verificar que apos 90 dias, registros antigos sao removidos automaticamente. Verificar que e possivel exportar dados antes da remocao.

**Acceptance Scenarios**:

1. **Given** registros de observabilidade com mais de 90 dias, **When** o processo de limpeza executa, **Then** os registros sao removidos automaticamente.
2. **Given** o operador deseja preservar dados historicos, **When** solicita exportacao, **Then** recebe os dados em formato CSV para analise externa.

---

### Edge Cases

- O que acontece quando o pipeline run e interrompido no meio (ex: processo morto)? O trace deve registrar o estado parcial com status "interrompido".
- O que acontece quando o node nao retorna dados de tokens (ex: subprocess falha antes de gerar output JSON)? O sistema registra o node com tokens/custo como nulos sem impactar outros nodes.
- O que acontece quando multiplos pipeline runs executam simultaneamente? Cada run deve ter seu proprio trace isolado, sem misturar dados.
- O que acontece quando o banco de dados esta temporariamente inacessivel? A execucao do pipeline nao deve ser bloqueada; dados de observabilidade sao best-effort.
- O que acontece com evals de nodes que produziram artefatos vazios ou minimos? O eval deve registrar score baixo em completude e sinalizar no dashboard.

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE registrar automaticamente um trace para cada pipeline run, contendo: identificador unico, plataforma, epic (quando aplicavel), timestamp de inicio e fim, status final e custo total.
- **FR-002**: O sistema DEVE registrar um span para cada node executado dentro de um run, contendo: nome do node, skill executada, timestamps de inicio/fim, status (sucesso/erro/cancelado), tokens de entrada, tokens de saida, custo estimado em USD e duracao.
- **FR-003**: O sistema DEVE capturar dados de tokens e custo a partir do output estruturado do processo de execucao de cada node.
- **FR-004**: O sistema DEVE atribuir scores de avaliacao (0-10) em 4 dimensoes fixas para cada node que completa com sucesso: qualidade geral, aderencia a especificacao, completude e eficiencia de custo.
- **FR-005**: O sistema DEVE expor dados de observabilidade via endpoints consultaveis pelo portal, incluindo: lista de traces, detalhes de spans por trace, scores de avaliacao e estatisticas agregadas.
- **FR-006**: O portal DEVE exibir uma pagina de observabilidade por plataforma com 4 secoes: Runs (timeline), Traces (waterfall), Evals (scoreboard com tendencias) e Custos (acumulado por periodo).
- **FR-007**: O portal DEVE atualizar os dados exibidos automaticamente a cada 10 segundos sem necessidade de refresh manual.
- **FR-008**: O sistema DEVE remover automaticamente registros de observabilidade com mais de 90 dias.
- **FR-009**: O sistema DEVE permitir exportar dados de observabilidade em formato CSV para analise externa.
- **FR-010**: O sistema DEVE persistir scores de avaliacao com metadata extensivel para acomodar dimensoes adicionais no futuro.
- **FR-011**: Falhas na gravacao de dados de observabilidade NAO DEVEM interromper a execucao do pipeline. Observabilidade e aditiva, nao bloqueante.
- **FR-012**: O sistema DEVE incluir metricas quantitativas por node alem dos evals qualitativos: tamanho do output (bytes/linhas), duracao e contagem de erros.

### Key Entities

- **Trace**: Representa a execucao completa de um pipeline run. Contem identificador, plataforma, epic, timestamps, status e metricas agregadas (custo total, duracao total).
- **Span**: Representa a execucao de um node individual dentro de um trace. Contem referencia ao trace pai, nome do node, skill, timestamps, status, tokens e custo.
- **Eval Score**: Representa a avaliacao de qualidade de um artefato gerado por um node. Contem referencia ao span, dimensao avaliada, score numerico (0-10) e metadata adicional.
- **Stats Agregado**: Visao calculada de metricas acumuladas (custo por periodo, media de scores por node, tendencias temporais). Nao e entidade persistida — derivada de traces, spans e eval scores.

## Success Criteria

### Measurable Outcomes

- **SC-001**: O operador consegue identificar o status de qualquer node em execucao em ate 10 segundos apos abertura do dashboard.
- **SC-002**: 100% dos pipeline runs completados tem trace com dados de tokens e custo por node.
- **SC-003**: O operador consegue identificar o node mais caro de um run em menos de 30 segundos usando o dashboard.
- **SC-004**: 100% dos nodes completados com sucesso recebem eval scores nas 4 dimensoes dentro de 60 segundos apos conclusao.
- **SC-005**: Registros com mais de 90 dias sao removidos automaticamente sem intervencao manual.
- **SC-006**: O dashboard de observabilidade carrega e exibe dados em menos de 3 segundos mesmo com 90 dias de historico.
- **SC-007**: A captura de dados de observabilidade adiciona menos de 5% ao tempo total de execucao do pipeline.
- **SC-008**: O operador consegue exportar dados historicos em CSV em menos de 1 minuto para qualquer periodo dentro da janela de retencao.

## Assumptions

- O executor do pipeline ja produz output estruturado (JSON) contendo dados de tokens e custo por node. Caso nao produza, o sistema registra esses campos como nulos.
- O portal Astro existente suporta adicao de novas paginas e componentes React interativos (islands).
- O daemon FastAPI existente aceita adicao de novos endpoints sem refatoracao significativa.
- A carga de trabalho e single-user (um operador). Nao ha necessidade de autenticacao nem controle de acesso no portal.
- O volume de dados e moderado (dezenas de runs por dia, nao milhares). Otimizacoes de escala nao sao necessarias em V1.
- Evals qualitativos usam o Judge pattern ja validado no projeto (4 personas + decision classifier). Nao sera necessario implementar o Judge do zero.
- Export CSV e um processo sob demanda, nao automatizado. O operador dispara manualmente quando necessario.
- A janela de retencao de 90 dias e fixa em V1. Configurabilidade por plataforma e escopo futuro.
