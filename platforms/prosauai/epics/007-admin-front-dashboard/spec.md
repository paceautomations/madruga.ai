# Feature Specification: Admin Front — Dashboard Inicial

**Feature Branch**: `epic/prosauai/007-admin-front-dashboard`
**Created**: 2026-04-15
**Status**: Clarified
**Input**: Criar a fundação do painel administrativo do ProsaUAI com autenticação, reestruturação em monorepo, e uma página de dashboard mostrando volume de mensagens recebidas por dia nos últimos 30 dias.

## User Scenarios & Testing

### User Story 1 - Login no Painel Admin (Priority: P1)

Um administrador do ProsaUAI precisa acessar o painel administrativo de forma segura. Ele navega até a URL do admin, vê uma tela de login, insere suas credenciais (email e senha) e, após autenticação bem-sucedida, é redirecionado ao dashboard. Caso as credenciais estejam incorretas, recebe uma mensagem de erro clara.

**Why this priority**: Sem autenticação funcional, nenhuma outra funcionalidade do painel é acessível. É o portão de entrada obrigatório.

**Independent Test**: Pode ser testado acessando `/admin/login`, inserindo credenciais válidas e verificando o redirecionamento ao dashboard. Entrega valor ao garantir que apenas usuários autorizados acessam o painel.

**Acceptance Scenarios**:

1. **Given** um administrador com credenciais válidas cadastradas, **When** ele insere email e senha corretos na tela de login, **Then** é autenticado e redirecionado para `/admin` (dashboard).
2. **Given** um visitante sem credenciais, **When** ele tenta acessar `/admin` diretamente, **Then** é redirecionado para `/admin/login`.
3. **Given** um administrador, **When** ele insere credenciais inválidas, **Then** vê uma mensagem de erro genérica ("Credenciais inválidas") sem revelar qual campo está incorreto.
4. **Given** um atacante tentando brute force, **When** ele excede 5 tentativas de login por minuto (por IP + email), **Then** recebe resposta de rate limit (HTTP 429) e deve aguardar antes de tentar novamente.
5. **Given** um administrador autenticado, **When** sua sessão expira (após 24 horas), **Then** é redirecionado ao login na próxima navegação.
6. **Given** um administrador autenticado, **When** ele clica no botão de logout no header, **Then** o cookie JWT é removido e ele é redirecionado para `/admin/login`.

---

### User Story 2 - Visualizar Dashboard com Volume de Mensagens (Priority: P1)

Um administrador autenticado acessa a página principal do painel (`/admin`) e visualiza um gráfico de barras mostrando a quantidade de mensagens recebidas por dia nos últimos 30 dias, junto com um KPI exibindo o total de mensagens no período. Essa visão é cross-tenant (todas as organizações agregadas).

**Why this priority**: É o único artefato visível que prova a fundação inteira — auth, pools de banco, frontend, backend e integração end-to-end. Sem ele, o epic não entrega valor tangível.

**Independent Test**: Pode ser testado fazendo login e verificando que o dashboard exibe o gráfico com dados reais (ou zerados se não houver mensagens). Entrega valor ao dar visibilidade operacional instantânea ao time.

**Acceptance Scenarios**:

1. **Given** um administrador autenticado e mensagens existentes no sistema, **When** ele acessa `/admin`, **Then** vê um gráfico mostrando mensagens por dia nos últimos 30 dias e um KPI com o total do período.
2. **Given** um administrador autenticado e nenhuma mensagem no período, **When** ele acessa `/admin`, **Then** vê o gráfico com todos os dias em zero e o KPI exibindo "0".
3. **Given** dias sem nenhuma mensagem dentro do período de 30 dias, **When** o dashboard é renderizado, **Then** esses dias aparecem no gráfico com valor zero (gap-fill), sem buracos na linha do tempo.
4. **Given** um administrador autenticado, **When** ele visualiza o dashboard, **Then** os dados são carregados em até 3 segundos, com indicador de carregamento visível durante a espera.
5. **Given** o backend indisponível temporariamente, **When** o dashboard tenta carregar dados, **Then** exibe uma mensagem de erro amigável com opção de tentar novamente.

---

### User Story 3 - Reestruturação em Monorepo (Priority: P1)

A equipe de desenvolvimento precisa que o repositório seja reorganizado em estrutura monorepo para suportar o frontend admin ao lado da API existente, sem quebrar o pipeline de mensagens WhatsApp que já opera em produção.

**Why this priority**: Sem a reorganização do repositório, não há onde o frontend admin viva. É pré-requisito estrutural para todas as funcionalidades visuais.

**Independent Test**: Pode ser testado verificando que, após a reestruturação, todos os testes existentes do pipeline de mensagens passam sem alteração funcional e o novo projeto frontend é inicializável.

**Acceptance Scenarios**:

1. **Given** o repositório atual com código na raiz, **When** a reestruturação é concluída, **Then** a API vive em `apps/api/`, o admin em `apps/admin/`, e tipos compartilhados em `packages/types/`.
2. **Given** a reestruturação concluída, **When** os testes do pipeline existente (epics 001–005) são executados, **Then** todos passam sem regressões.
3. **Given** a reestruturação concluída, **When** o docker-compose é executado, **Then** ambos os serviços (API e Admin) inicializam corretamente.

---

### User Story 4 - Bootstrap do Primeiro Administrador (Priority: P2)

Na primeira implantação do sistema, é necessário criar o administrador inicial sem depender de uma interface. Um mecanismo de bootstrap (via variáveis de ambiente) cria automaticamente o primeiro usuário admin na inicialização, caso não exista nenhum.

**Why this priority**: Necessário para que o login funcione na primeira vez, mas é uma operação única e não impacta o uso diário.

**Independent Test**: Pode ser testado iniciando o sistema com as variáveis de bootstrap configuradas e verificando que o usuário admin é criado no banco.

**Acceptance Scenarios**:

1. **Given** o sistema iniciado pela primeira vez sem usuários admin, **When** as variáveis `ADMIN_BOOTSTRAP_EMAIL` e `ADMIN_BOOTSTRAP_PASSWORD` estão configuradas, **Then** um usuário administrador é criado automaticamente.
2. **Given** um usuário admin já existente, **When** o sistema reinicia com variáveis de bootstrap, **Then** nenhum usuário duplicado é criado.
3. **Given** variáveis de bootstrap ausentes ou vazias, **When** o sistema inicia, **Then** nenhum erro é lançado e nenhum usuário é criado (o sistema apenas não terá admin até que um seja criado manualmente).

---

### User Story 5 - Endpoint de Health Check (Priority: P2)

O serviço de API precisa expor um endpoint de verificação de saúde para que o docker-compose e ferramentas de monitoramento possam verificar se a API está operacional antes de iniciar serviços dependentes.

**Why this priority**: Garante que o serviço admin só inicie quando a API estiver pronta, evitando erros de conexão na inicialização.

**Independent Test**: Pode ser testado fazendo uma requisição ao endpoint e verificando resposta de sucesso.

**Acceptance Scenarios**:

1. **Given** a API iniciada e operacional, **When** uma requisição é feita ao endpoint de saúde, **Then** retorna sucesso com indicação de que o sistema está saudável.
2. **Given** a API com problema de conexão ao banco, **When** o health check é chamado, **Then** retorna indicação de falha com informação do componente afetado.

---

### Edge Cases

- O que acontece quando o banco de dados fica indisponível durante uma requisição ao dashboard? O sistema deve exibir mensagem de erro amigável e não expor detalhes internos.
- O que acontece se o token JWT expirar durante a navegação? O usuário deve ser redirecionado ao login sem perda de contexto (URL de retorno preservada).
- O que acontece quando há milhões de mensagens no período de 30 dias? A query de agregação deve usar índice dedicado e retornar em tempo aceitável (< 3s).
- O que acontece quando o cookie JWT é manipulado ou inválido? O sistema deve rejeitar a sessão e forçar novo login.
- O que acontece se o administrador bootstrap tentar usar uma senha fraca? A senha deve atender requisitos mínimos (8+ caracteres).
- O que acontece se o rate limit do login bloquear um usuário legítimo? O bloqueio é temporário (1 minuto) e a mensagem de erro indica quando pode tentar novamente.

## Clarifications

### Session 2026-04-15

- Q: Qual o tempo de expiração do token JWT? → A: 24 horas (ferramenta interna, ~3 usuários em Tailscale, sem refresh token nesta fase).
- Q: Tipo de gráfico no dashboard — barras ou linha? → A: Gráfico de barras (contagens diárias são valores discretos, barras comunicam melhor que linha para este caso de uso).
- Q: Existe mecanismo de logout para o administrador? → A: Sim — botão de logout no header que limpa o cookie JWT e redireciona para `/admin/login`.
- Q: Quais eventos vão para a tabela `audit_log` no banco vs. apenas structured logs? → A: Apenas eventos de autenticação (login bem-sucedido, login falhado, rate limit atingido) vão para `audit_log`. Acessos ao dashboard ficam apenas em structured logs (evitar ruído no banco).
- Q: Como adicionar novos administradores além do bootstrap inicial? → A: Neste epic, apenas via bootstrap (env vars) ou INSERT direto no banco. CRUD de administradores via interface é follow-up em epic futuro.

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE autenticar administradores via email e senha, emitindo um token JWT com expiração de 24 horas ao autenticar com sucesso.
- **FR-002**: O sistema DEVE proteger todas as rotas administrativas (`/admin/*`), exigindo sessão válida para acesso.
- **FR-003**: O sistema DEVE redirecionar usuários não autenticados que tentem acessar rotas protegidas para a página de login.
- **FR-004**: O sistema DEVE limitar tentativas de login a 5 por minuto por combinação de IP e email.
- **FR-005**: O sistema DEVE exibir na página principal do admin um gráfico de barras de mensagens recebidas por dia nos últimos 30 dias, agregadas de todas as organizações.
- **FR-006**: O sistema DEVE exibir um indicador numérico (KPI) com o total de mensagens no período de 30 dias.
- **FR-007**: O sistema DEVE preencher dias sem mensagens com valor zero no gráfico (gap-fill), garantindo continuidade visual da linha do tempo.
- **FR-008**: O sistema DEVE usar timezone `America/Sao_Paulo` para agregação de mensagens por dia. [VALIDAR] quando houver tenants internacionais.
- **FR-009**: O sistema DEVE permitir a criação de um administrador inicial via configuração de ambiente (bootstrap), sem necessidade de interface.
- **FR-010**: O sistema DEVE impedir a criação de administradores duplicados durante o processo de bootstrap.
- **FR-011**: O sistema DEVE expor um endpoint de verificação de saúde que indique se a API e suas dependências estão operacionais.
- **FR-012**: O sistema DEVE isolar o acesso a dados — consultas administrativas cross-tenant devem usar um canal de acesso dedicado que bypassa o isolamento por organização, enquanto o pipeline de mensagens existente continua operando com isolamento estrito.
- **FR-013**: O sistema DEVE suportar a estrutura de monorepo com API, frontend admin e pacote de tipos compartilhados coexistindo sem interferência.
- **FR-014**: O sistema DEVE registrar eventos de autenticação (login bem-sucedido, login falhado, rate limit atingido) na tabela `audit_log` no banco de dados. Acessos ao dashboard são registrados apenas em structured logs (não no banco).
- **FR-019**: O sistema DEVE permitir que o administrador faça logout, removendo o cookie JWT e redirecionando para a página de login.
- **FR-020**: O sistema DEVE expirar tokens JWT após 24 horas, forçando re-autenticação.
- **FR-015**: O sistema DEVE exibir indicador de carregamento enquanto dados do dashboard estão sendo obtidos.
- **FR-016**: O sistema DEVE exibir mensagem de erro amigável quando não for possível carregar dados do dashboard, com opção de tentar novamente.
- **FR-017**: O sistema DEVE configurar proteção contra requisições cross-origin (CORS), permitindo apenas a origem do frontend admin.
- **FR-018**: O sistema DEVE gerenciar migrações de banco de dados de forma idempotente, suportando aplicação incremental (up) e reversão (down).

### Key Entities

- **Administrador (Admin User)**: Representa um usuário com acesso ao painel administrativo. Atributos principais: identificador, email (único), senha (hash), data de criação, data de último acesso.
- **Evento de Auditoria (Audit Event)**: Representa um evento de autenticação registrado na tabela `audit_log` para rastreabilidade. Escopo neste epic: apenas eventos de auth (login_success, login_failed, rate_limit_hit). Atributos: identificador (UUID), tipo de ação (enum), ator (admin_id, nullable para falhas), IP de origem, detalhes do evento (JSONB), timestamp.
- **Mensagem (Message)**: Entidade existente no sistema. Relevante aqui como fonte de dados para o dashboard — atributos utilizados: data de criação, identificador da organização (tenant).

## Success Criteria

### Measurable Outcomes

- **SC-001**: Administradores conseguem fazer login e acessar o dashboard em menos de 10 segundos (tempo total: carregar página login + autenticar + carregar dashboard).
- **SC-002**: O dashboard carrega dados de 30 dias e exibe gráfico + KPI em menos de 3 segundos após autenticação.
- **SC-003**: 100% dos testes do pipeline de mensagens existente (epics 001–005) continuam passando após a reestruturação em monorepo.
- **SC-004**: Tentativas de brute force são bloqueadas após 5 tentativas por minuto, com zero falsos positivos para uso normal (1-2 tentativas).
- **SC-005**: O time de operação consegue verificar o volume de mensagens do sistema em 2 cliques (login + visualizar dashboard), eliminando a necessidade de consultas SQL diretas para essa informação.
- **SC-006**: O endpoint de health check responde em menos de 1 segundo e reflete corretamente o estado da API e do banco de dados.
- **SC-007**: O administrador bootstrap é criado com sucesso na primeira inicialização, permitindo primeiro acesso sem intervenção manual no banco.

## Assumptions

- A tabela de mensagens (`messages`) já existe em produção com coluna `created_at` e coluna `tenant_id`, e contém dados reais suficientes para validar o dashboard.
- O ambiente de produção usa Docker Compose como orquestrador, e os serviços são acessíveis via rede interna (Tailscale).
- O público-alvo do painel admin nesta fase é exclusivamente interno (~3 usuários da equipe Pace), operando dentro da rede Tailscale.
- O pipeline de mensagens WhatsApp (epics 001–005) está funcional e não deve sofrer nenhuma alteração comportamental neste epic.
- Redis 7 está disponível no ambiente e pode ser utilizado como backend para rate limiting.
- O banco de dados PostgreSQL 15 está operacional com as migrações 001–008 aplicadas (RLS configurado, helper `tenant_id()` existente).
- A stack definida nas ADRs (Next.js 15, shadcn/ui, FastAPI, asyncpg) está validada e não requer prova de conceito adicional.
- Mobile e responsividade avançada estão fora do escopo — o painel será acessado via desktop/laptop.
- Internacionalização está fora do escopo — interface e dados em português brasileiro, timezone fixo.
- O gráfico de barras pode ser substituído por apenas o KPI numérico se o escopo de 3 semanas for excedido (circuit breaker definido no pitch).
- Gestão de administradores (CRUD) via interface está fora do escopo deste epic. Novos admins são adicionados via bootstrap (env vars) ou INSERT direto no banco.

---
handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada com 5 resoluções: JWT 24h, gráfico de barras, logout explícito, audit_log só para auth events, admin management só via bootstrap/SQL. 20 FRs (3 novos: logout, JWT expiry, audit scope). Pronta para planejamento técnico."
  blockers: []
  confidence: Alta
  kill_criteria: "Se o pipeline de mensagens existente (001-005) não puder coexistir com a reestruturação monorepo sem regressões, o epic precisa ser repensado."
