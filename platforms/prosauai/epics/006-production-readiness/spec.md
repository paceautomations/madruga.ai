# Feature Specification: Production Readiness — Schema Isolation, Log Persistence, Data Retention, VPS Deploy

**Feature Branch**: `epic/prosauai/006-production-readiness`
**Created**: 2026-04-12
**Status**: Draft
**Input**: Epic 006 pitch — preparar infraestrutura ProsauAI para deploy em VPS de produção, resolvendo 7 gaps identificados: schema isolation, Phoenix Postgres backend, log persistence, data retention cron, particionamento de messages, host monitoring e migration runner.

## User Scenarios & Testing

### User Story 1 — Deploy Seguro em VPS (Priority: P1)

O operador da plataforma (DevOps/founder) executa `docker compose -f docker-compose.yml -f docker-compose.prod.yml up` na VPS e todos os serviços sobem sem conflitos de schema, com migrations aplicadas automaticamente, logs rotacionados e monitoring básico funcional.

**Why this priority**: Sem deploy funcional, nenhuma das outras capacidades importa. Este é o cenário que desbloqueia produção.

**Independent Test**: Pode ser verificado em VPS limpa (ou VM local) executando o docker compose prod e confirmando que todos os containers estão healthy, migrations aplicadas e UI do monitoring acessível.

**Acceptance Scenarios**:

1. **Given** uma VPS limpa com Docker instalado e `.env` configurado, **When** o operador executa `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`, **Then** todos os containers sobem healthy em menos de 2 minutos, migrations são aplicadas automaticamente e a API responde em `/health`.
2. **Given** o stack rodando em produção, **When** o operador executa `docker compose up` novamente após atualização com novas migrations, **Then** apenas migrations pendentes são aplicadas (idempotência) e nenhuma migration duplicada é executada.
3. **Given** uma migration com erro de sintaxe SQL, **When** o container tenta subir, **Then** o container falha no startup (fail-fast) com mensagem de erro clara indicando qual migration falhou, e a API NÃO inicia.

---

### User Story 2 — Schema Isolation Compatível com Supabase (Priority: P1)

As tabelas de negócio vivem no schema `prosauai`, funções helper de RLS em `prosauai_ops`, e nenhum objeto custom é criado nos schemas `auth` ou `public` do Supabase. O operador pode aplicar as migrations no Supabase sem conflitos.

**Why this priority**: Sem schema isolation, o deploy no Supabase (provedor de Postgres em produção) falha ou corrompe objetos gerenciados pelo provider. Blocker absoluto para produção.

**Independent Test**: Aplicar migrations em instância Supabase de teste e verificar que schemas `auth` e `public` não foram modificados (exceto extensions necessárias como `uuid-ossp`).

**Acceptance Scenarios**:

1. **Given** um Postgres Supabase limpo, **When** as migrations são aplicadas, **Then** o schema `prosauai` contém todas as tabelas de negócio (customers, conversations, conversation_states, messages, agents, prompts, eval_scores), o schema `prosauai_ops` contém a função `tenant_id()` e a tabela `schema_migrations`, e o schema `auth` NÃO contém nenhuma função ou tabela custom.
2. **Given** tabelas criadas no schema `prosauai`, **When** a aplicação se conecta com `search_path = prosauai,prosauai_ops,public`, **Then** todas as queries existentes (sem schema prefix) funcionam sem modificação.
3. **Given** as RLS policies configuradas, **When** uma query é executada com `tenant_id` setado via `SET LOCAL`, **Then** `prosauai_ops.tenant_id()` retorna o valor correto e as policies filtram dados por tenant.

---

### User Story 3 — Compliance LGPD: Purge Automático de Dados (Priority: P1)

Um cron job diário executa automaticamente o purge de dados expirados conforme ADR-018, garantindo compliance com o princípio de minimização de dados da LGPD desde o dia 1 de produção.

**Why this priority**: Requisito legal. Sem purge automático, a plataforma viola a LGPD desde o primeiro dia com dados reais. Risco jurídico direto.

**Independent Test**: Executar o cron em modo `--dry-run` contra banco com dados de teste e verificar que identifica corretamente os registros expirados. Executar sem dry-run e confirmar que deleta apenas dados além do período de retenção.

**Acceptance Scenarios**:

1. **Given** mensagens com mais de 90 dias na tabela `messages`, **When** o cron de retention executa, **Then** apenas partições onde TODOS os dados têm > 90 dias são removidas via `DROP PARTITION` (sem DML, bypassa RLS automaticamente). A partição do mês-limite permanece até expirar completamente (retenção efetiva 90-120 dias). Logs registram o count de rows removidas por partição.
2. **Given** conversas fechadas há mais de 90 dias, **When** o cron executa, **Then** as conversas são removidas e `conversation_states` orphaned são removidos via cascade.
3. **Given** o cron executando em modo `--dry-run`, **When** há dados expirados, **Then** o sistema lista o que seria removido por tabela/partição sem efetuar nenhuma exclusão.
4. **Given** a tabela `admin.audit_log` (futura), **When** o cron executa, **Then** registros de audit NUNCA são purgados (retention 365d, sem purge automático).

---

### User Story 4 — Logs Persistentes e Rotacionados (Priority: P2)

Todos os containers Docker têm log rotation configurado, prevenindo que disco da VPS encha com logs não-rotacionados. Logs sobrevivem ao restart do container e são acessíveis via `docker compose logs`.

**Why this priority**: Sem log rotation, o disco da VPS enche silenciosamente e causa crash de Postgres e demais serviços. Sem logs persistentes, debugging em produção é cego.

**Independent Test**: Verificar via `docker inspect` que todos os containers têm `json-file` driver com `max-size` e `max-file` configurados. Reiniciar um container e confirmar que logs anteriores estão acessíveis.

**Acceptance Scenarios**:

1. **Given** todos os services no docker-compose, **When** inspecionados com `docker inspect --format='{{.HostConfig.LogConfig}}'`, **Then** todos mostram driver `json-file` com `max-size: 50m` e `max-file: 5`.
2. **Given** um container gerando logs ativamente, **When** o total de logs ultrapassa 250MB (50m × 5 files), **Then** os logs mais antigos são rotacionados automaticamente sem intervenção manual.
3. **Given** um container que foi reiniciado, **When** o operador executa `docker compose logs <service>`, **Then** logs anteriores ao restart estão acessíveis (até o limite de rotation).

---

### User Story 5 — Phoenix com Backend Postgres em Produção (Priority: P2)

O Phoenix (Arize) persiste traces em Postgres em vez de SQLite no ambiente de produção, garantindo que traces sobrevivam a restarts e escalem além de 1M spans.

**Why this priority**: Phoenix com SQLite é single-writer e degrada progressivamente. Para produção com múltiplos tenants gerando spans continuamente, Postgres é necessário para longevidade.

**Independent Test**: Subir stack prod, enviar requests que geram traces, reiniciar container Phoenix e verificar que traces anteriores estão visíveis na UI.

**Acceptance Scenarios**:

1. **Given** o stack prod rodando com Phoenix configurado para Postgres, **When** requests são processados pela API, **Then** traces aparecem na UI do Phoenix (porta 6006) e persistem após restart do container Phoenix.
2. **Given** o ambiente de desenvolvimento (docker-compose.yml base), **When** Phoenix sobe, **Then** usa SQLite como backend (setup rápido, sem dependência de Postgres para dev).
3. **Given** Phoenix configurado com `search_path=observability`, **When** Phoenix cria suas tabelas internas, **Then** as tabelas ficam no schema `observability`, isoladas das tabelas de negócio em `prosauai`.

---

### User Story 6 — Particionamento de Messages por Mês (Priority: P2)

A tabela `messages` é criada como particionada por range de `created_at` (mensal), permitindo purge eficiente via `DROP PARTITION` e crescimento sustentável da tabela append-only.

**Why this priority**: A tabela `messages` é append-only e a que mais cresce. Sem particionamento, o purge de 90 dias requer DELETE massivo com write amplification. Fazer agora é trivial (trocar CREATE TABLE); fazer depois com dados existentes exige downtime.

**Independent Test**: Criar tabela particionada, inserir dados em múltiplas partições, executar `EXPLAIN ANALYZE` com filtro de data e confirmar partition pruning. Dropar partição antiga e confirmar remoção instantânea.

**Acceptance Scenarios**:

1. **Given** a migration de messages aplicada, **When** `\d+ prosauai.messages` é executado, **Then** a tabela mostra `PARTITION BY RANGE (created_at)` e pelo menos 3 partições futuras existem.
2. **Given** dados inseridos em partições de meses diferentes, **When** uma query com `WHERE created_at BETWEEN '2026-04-01' AND '2026-04-30'` é executada, **Then** `EXPLAIN ANALYZE` mostra partition pruning (apenas 1 partição scaneada).
3. **Given** uma partição com mais de 90 dias, **When** `DROP TABLE prosauai.messages_2026_01` é executado, **Then** a remoção é instantânea (< 100ms), sem write amplification, e a RLS policy `messages_no_delete` NÃO bloqueia a operação (DDL bypassa RLS).
4. **Given** a tabela `eval_scores` com campo `message_id` (sem FK — limitação PG com tabelas particionadas), **When** um eval_score é criado referenciando um message existente, **Then** a integridade é garantida por UUID v4 + validação app-level (sem constraint no BD).

---

### User Story 7 — Host Monitoring Básico na VPS (Priority: P3)

O operador tem visibilidade de CPU, RAM, disco e saúde dos containers Docker via dashboard web acessível na VPS, com alertas automáticos para condições críticas.

**Why this priority**: Sem monitoring, falhas são silenciosas. Container OOM-killed ou disco cheio só é detectado quando usuário reporta que o agente parou. Monitoring básico previne os incidentes mais comuns em VPS.

**Independent Test**: Subir Netdata no docker-compose prod, acessar localhost:19999 e verificar que métricas de host e containers aparecem. Simular disco >80% e verificar alerta.

**Acceptance Scenarios**:

1. **Given** o stack prod rodando com Netdata, **When** o operador acessa `http://localhost:19999`, **Then** o dashboard mostra métricas de CPU, RAM, disco, rede e containers Docker em tempo real.
2. **Given** uso de disco acima de 80%, **When** Netdata detecta a condição, **Then** um alerta é gerado automaticamente (visível no dashboard).
3. **Given** Netdata bind apenas em `127.0.0.1:19999`, **When** acesso externo é tentado, **Then** a conexão é recusada (dashboard acessível apenas via SSH tunnel ou VPN).

---

### Edge Cases

- O que acontece se o Postgres não está healthy quando o migration runner tenta executar? O container da API deve falhar com erro claro e retry via Docker restart policy.
- O que acontece se uma partição futura não foi criada e uma mensagem chega com `created_at` fora do range coberto? O INSERT deve falhar com erro. O cron de partições cria 3 meses à frente para prevenir isso.
- O que acontece se o cron de retention falha no meio da execução? Logs devem registrar o ponto de falha. Na próxima execução, o cron retoma do ponto onde parou (idempotente por natureza — dados já deletados não são processados novamente).
- O que acontece com a partição do mês-limite (contém dados < 90 dias e > 90 dias)? A partição permanece intacta até que TODOS os dados tenham > 90 dias. Na prática, a retenção efetiva é 90-120 dias. Isso é aceito como trade-off entre simplicidade (sem DELETE parcial) e compliance (margem conservadora favorece o usuário).
- O que acontece se o container retention-cron reinicia durante execução do purge? A operação `DROP PARTITION` é atômica — ou completa ou não. DELETEs em batch nas demais tabelas são feitos com LIMIT para limitar impacto. Re-execução é idempotente.
- O que acontece se o volume de logs excede a capacidade de rotation antes de 30 dias? A compliance com ADR-018 (30d) depende do volume real. Se `max-size × max-file` não cobre 30 dias, logs antigos são perdidos. Monitorar e ajustar após deploy.
- O que acontece se o Netdata container consome recursos excessivos da VPS? Netdata é lightweight (~150MB RAM), mas em VPS com 2GB RAM pode impactar. Configurar limites de resources no docker-compose (`mem_limit`).

## Clarifications

### Session 2026-04-12

- Q: Como o purge lida com partições no limite de 90 dias (uma partição mensal pode conter dados < 90 dias e > 90 dias)? → A: Abordagem conservadora — `DROP PARTITION` apenas quando TODOS os dados da partição têm > 90 dias. A partição do mês-limite permanece até expirar completamente. Na prática, a retenção efetiva é 90-120 dias dependendo do timing. Isso simplifica a lógica (sem DELETE parcial dentro de partição) e é mais seguro para compliance.
- Q: O migration runner deve usar psycopg2 (sync, nova dependência) ou asyncpg (já existente) ou psql (subprocess)? → A: Usar asyncpg com wrapper `asyncio.run()`. O projeto já depende de asyncpg e não tem psycopg2 nas dependências. Adicionar psycopg2 viola o princípio de minimizar dependências da constitution. O migration runner executa queries simples (INSERT, DDL) que asyncpg suporta perfeitamente. Alternativa psql via subprocess rejeitada: requer parsing de output e não está garantido no container Python.
- Q: Quais são os requisitos mínimos da VPS para rodar o stack completo de produção? → A: Mínimo 2 vCPU, 4GB RAM, 40GB SSD. Justificativa: Postgres (~512MB shared_buffers), Phoenix (~1GB para traces), API (~256MB), Netdata (~150MB), retention-cron (~64MB), Redis (~128MB) = ~2.1GB base + SO + headroom. Com 2GB RAM o Netdata pode causar OOM; 4GB é o mínimo seguro. Disco 40GB: pgdata ~5GB/ano, logs max 1.25GB, traces ~10GB/ano, SO ~5GB = ~21GB com margem.
- Q: Como garantir que o cron de retention é confiável com a abordagem de container com sleep loop (drift, restart, timezone)? → A: O container usa `sleep 86400` (24h) com logging estruturado de cada execução. Idempotência natural elimina riscos de re-execução após restart. Para timezone, usar UTC em todas as comparações de data (`now() AT TIME ZONE 'UTC'`). O Docker restart policy `unless-stopped` garante que o container reinicia após crash. Não usar host crontab para manter portabilidade do stack Docker.
- Q: O Phoenix (Arize) suporta configuração de schema via `search_path` na connection string? → A: Sim, Phoenix cria suas tabelas no schema default da conexão. Configurar `options=-c search_path=observability` na DATABASE_URL funciona com PG 15 (Supabase). Adicionar validação pós-deploy: verificar que tabelas Phoenix existem no schema `observability` via `SELECT table_name FROM information_schema.tables WHERE table_schema = 'observability'`. Se Phoenix não respeitar search_path, fallback: criar database separado `phoenix_db` no mesmo Postgres.

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE criar todas as tabelas de negócio no schema `prosauai` (customers, conversations, conversation_states, messages, agents, prompts, eval_scores e tipos enum).
- **FR-002**: O sistema DEVE criar funções helper de RLS no schema `prosauai_ops`, incluindo `tenant_id()` com semântica idêntica à atual `auth.tenant_id()`.
- **FR-003**: O sistema NÃO DEVE criar nenhum objeto (tabela, função, schema) dentro dos schemas `auth` ou `public` do Postgres (exceto extensions como `uuid-ossp` que requerem `public`).
- **FR-004**: O sistema DEVE reservar o schema `admin` para uso futuro (epic 013 — tenants, audit_log) sem criar tabelas nele.
- **FR-005**: A conexão do pool asyncpg DEVE configurar `search_path = prosauai,prosauai_ops,public` para que queries existentes funcionem sem schema prefix.
- **FR-006**: O migration runner DEVE aplicar arquivos `.sql` da pasta `migrations/` em ordem numérica, registrar cada aplicação na tabela `prosauai_ops.schema_migrations` e ser idempotente (re-execução não aplica migrations já registradas). O runner DEVE usar asyncpg (dependência já existente) com wrapper `asyncio.run()` — NÃO adicionar psycopg2 como nova dependência.
- **FR-007**: O migration runner DEVE executar ANTES do startup da aplicação (fail-fast: se migration falha, API não inicia).
- **FR-008**: A tabela `messages` DEVE ser criada com `PARTITION BY RANGE (created_at)` com partições mensais.
- **FR-009**: O sistema DEVE criar automaticamente partições para os próximos 3 meses e remover partições totalmente expiradas (onde TODOS os dados têm >90 dias) como parte do cron de retention. A retenção efetiva é 90-120 dias devido à granularidade mensal das partições.
- **FR-010**: A tabela `messages` NÃO terá UNIQUE index global em `id` — PostgreSQL não suporta unique constraint em coluna que não faz parte da partition key (`created_at`). Integridade referencial de `eval_scores.message_id` é garantida por UUID v4 (probabilidade de colisão ~1e-37) + validação app-level.
- **FR-011**: Todos os services no docker-compose DEVEM ter log rotation configurado (`json-file` driver, `max-size: 50m`, `max-file: 5`).
- **FR-012**: O cron de data retention DEVE executar diariamente (via container Docker com `sleep 86400` e restart policy `unless-stopped`) e purgar dados conforme períodos definidos no ADR-018: messages 90d, conversations fechadas 90d, eval_scores 90d, Phoenix traces 90d, audit_log NUNCA (365d, sem purge automático). Todas as comparações de data DEVEM usar UTC (`now() AT TIME ZONE 'UTC'`).
- **FR-013**: O cron DEVE suportar modo `--dry-run` que lista o que seria purgado sem efetuar exclusões.
- **FR-014**: O purge de messages particionadas DEVE usar `DROP PARTITION` (DDL, bypassa RLS automaticamente). Purge de tabelas não-particionadas DEVE usar role com `BYPASSRLS` (service_role do Supabase).
- **FR-015**: O `docker-compose.prod.yml` DEVE configurar Phoenix com backend Postgres (em vez de SQLite) usando env var `PHOENIX_SQL_DATABASE_SCHEMA=observability` (mecanismo oficial desde Phoenix v4.33.0).
- **FR-016**: O `docker-compose.prod.yml` DEVE incluir container Netdata para monitoring de host, bind apenas em `127.0.0.1:19999`.
- **FR-017**: O cron de retention DEVE logar cada execução com contagem de rows removidas por tabela/partição.
- **FR-018**: O migration runner DEVE usar a mesma configuração de `search_path` que a aplicação para garantir consistência de referências.
- **FR-019**: O `docker-compose.prod.yml` DEVE documentar requisitos mínimos de VPS: 2 vCPU, 4GB RAM, 40GB SSD. Containers com resource limits configurados (Netdata `mem_limit: 256m`, retention-cron `mem_limit: 128m`).
- **FR-020**: O Phoenix DEVE criar tabelas no schema `observability` via env var `PHOENIX_SQL_DATABASE_SCHEMA=observability` (mecanismo oficial). A validação de que Phoenix criou tabelas no schema ocorre indiretamente no cron de retention (`purge_expired_traces` verifica existência de `observability.spans`). Se Phoenix não respeitar a env var, fallback documentado: database separado `phoenix_db`.
- **FR-021**: O cron de retention DEVE ser idempotente: re-execução após restart do container não causa duplicação de purge nem erros. Logging estruturado (structlog) com campos `run_id`, `table`, `rows_purged`, `partitions_dropped`, `duration_ms` para cada execução.

### Key Entities

- **Schema `prosauai`**: Namespace para todas as tabelas de negócio da plataforma. Isola objetos do app do namespace `public` gerenciado pelo Supabase.
- **Schema `prosauai_ops`**: Namespace para funções helper operacionais (como `tenant_id()`) e tabela de tracking de migrations (`schema_migrations`). Separado de `prosauai` para distinção clara entre dados de negócio e infraestrutura operacional.
- **Tabela `schema_migrations`**: Registra quais migrations já foram aplicadas (version TEXT, applied_at TIMESTAMPTZ). Garante idempotência do migration runner.
- **Partições de `messages`**: Tabelas filhas criadas mensalmente (ex: `prosauai.messages_2026_04`) que herdam estrutura da tabela pai particionada. Permitem purge eficiente via DDL.
- **Container `retention-cron`**: Serviço Docker dedicado que executa o script de purge diariamente com credenciais `service_role` separadas.
- **Container `netdata`**: Agente de monitoring que coleta métricas de host (CPU, RAM, disco) e containers Docker, expondo dashboard em porta local.

## Success Criteria

### Measurable Outcomes

- **SC-001**: O operador consegue realizar deploy completo do stack em VPS limpa em menos de 10 minutos (do `git clone` ao primeiro health check respondendo).
- **SC-002**: Migrations são aplicadas automaticamente no startup sem intervenção manual, com 100% de idempotência (re-execução sem efeitos colaterais).
- **SC-003**: O uso de disco por logs Docker é limitado a no máximo 1.25GB total (250MB por service × 5 services), prevenindo disk-full em VPS com 40GB+.
- **SC-004**: O purge automático mantém o volume de dados dentro dos limites de retenção definidos (90 dias para messages/conversations, 30 dias para logs), verificável via query de contagem.
- **SC-005**: Traces do Phoenix persistem entre restarts do container, verificável acessando a UI e confirmando traces anteriores ao restart.
- **SC-006**: O operador tem visibilidade de saúde da VPS (CPU, RAM, disco, containers) via dashboard web sem necessidade de SSH para diagnóstico básico.
- **SC-007**: Nenhum objeto custom existe nos schemas `auth` ou `public` do Supabase após aplicação das migrations, verificável via query `SELECT * FROM information_schema.tables WHERE table_schema IN ('auth','public')`.
- **SC-008**: O purge de uma partição mensal de messages completa em menos de 1 segundo (DDL instantâneo), independente do número de rows na partição.

## Assumptions

- **Nenhum dado de produção existe ainda**: As migrations do epic 005 não foram aplicadas em nenhum Postgres de produção. Portanto, reescrever as migrations (adicionando schema prefix, particionamento) é seguro — não há dados a migrar.
- **Supabase é o Postgres de produção**: O deploy usa Supabase como provedor de Postgres gerenciado para dados de negócio. Phoenix usa Postgres local na VPS para traces (write-heavy, sem necessidade de managed service).
- **VPS single-node**: O deploy target é uma VPS única (Hetzner/DigitalOcean) rodando todos os containers via Docker Compose. Não há cluster ou orquestração (Kubernetes, Swarm).
- **2-10 tenants na Fase 1**: O volume projetado é baixo (100 msgs/dia/tenant ≈ 1000 msgs/dia total). Particionamento é otimização para purge, não para performance de leitura.
- **Postgres 15+**: Supabase usa PG 15, que suporta FK em tabelas particionadas e UNIQUE indexes globais em partitioned tables. As features de particionamento usadas dependem do PG 12+.
- **Docker Compose é suficiente para deploy**: Não há necessidade de CI/CD automatizado, Kubernetes ou orquestração para a Fase 1 com 2 tenants. Deploy manual via SSH + docker compose.
- **`service_role` do Supabase tem `BYPASSRLS`**: O role service_role padrão do Supabase tem permissão BYPASSRLS. O container de retention usa credenciais separadas (service_role) do container da API (role RLS-restricted).
- **Netdata como monitoring temporário**: Netdata será substituído por Prometheus + Grafana no epic 013. É solução bridge para ter visibilidade básica antes da stack completa de observabilidade.

---
handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada para epic 006 production readiness. 5 clarificações integradas: (1) purge conservador por partição completa (retenção efetiva 90-120d), (2) migration runner com asyncpg (sem nova dep), (3) VPS mínimo 2vCPU/4GB/40GB, (4) cron via container sleep loop + UTC + restart policy, (5) Phoenix schema observability via search_path com fallback documentado. Spec pronta para planejamento de implementação."
  blockers: []
  confidence: Alta
  kill_criteria: "Se migrations do epic 005 já foram aplicadas em produção antes deste epic, a estratégia de reescrita de migrations se torna inválida — seria necessário migration de renomeação de schema (muito mais complexo)."
