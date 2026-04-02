# Feature Specification: Daemon 24/7

**Feature Branch**: `epic/madruga-ai/016-daemon-24-7`
**Created**: 2026-04-01
**Status**: Draft
**Input**: Epic 016 — Daemon 24/7. Processo persistente que monitora o estado do DAG, dispara skills quando prerequisites sao atendidos, e opera continuamente. Ultimo epic do MVP.

## User Scenarios & Testing

### User Story 1 - Daemon inicia e opera continuamente (Priority: P1)

O operador inicia o daemon com um unico comando. O daemon conecta ao Telegram, verifica saude dos servicos externos, e comeca a monitorar o pipeline. O processo roda 24/7 sem intervencao, sobrevivendo a reinicializacoes via systemd.

**Why this priority**: Sem o daemon rodando continuamente, nenhuma das outras funcionalidades existe. E o alicerce de tudo.

**Independent Test**: Iniciar o daemon, verificar que os endpoints /health e /status respondem, que o bot Telegram esta conectado, e que o processo se mantem ativo por pelo menos 10 minutos sem erros.

**Acceptance Scenarios**:

1. **Given** o daemon nao esta rodando, **When** o operador executa o comando de inicio, **Then** o daemon inicia, conecta ao Telegram, e responde em /health com status 200 em menos de 10 segundos.
2. **Given** o daemon esta rodando, **When** o processo e encerrado por sinal (SIGTERM), **Then** o daemon faz shutdown gracioso — cancela tasks pendentes, fecha conexoes, e encerra sem erro em menos de 5 segundos.
3. **Given** o daemon caiu por erro inesperado, **When** systemd detecta a queda, **Then** o daemon e reiniciado automaticamente em menos de 10 segundos e retoma operacao do ponto onde parou (ultimo checkpoint SQLite).

---

### User Story 2 - Dispatch automatico de skills do pipeline (Priority: P1)

O daemon monitora a tabela de epics no banco de dados. Quando um epic muda para status `in_progress`, o daemon inicia automaticamente o ciclo L2 — dispara skills na ordem topologica do DAG, respeita dependencias, e pausa em human gates.

**Why this priority**: Este e o core value do daemon — automacao do pipeline. Sem dispatch automatico, o daemon e apenas um processo idle.

**Independent Test**: Criar um epic com status `in_progress` no banco, verificar que o daemon detecta e inicia o dispatch do primeiro node do ciclo L2.

**Acceptance Scenarios**:

1. **Given** um epic com status `in_progress` existe no banco, **When** o daemon faz polling, **Then** o daemon detecta o epic e inicia o ciclo L2 em menos de 30 segundos.
2. **Given** o daemon esta executando um node via subprocess, **When** o subprocess completa com sucesso, **Then** o daemon verifica outputs, registra no banco, e avanca para o proximo node.
3. **Given** um node falha apos 3 retries, **When** o circuit breaker abre, **Then** o daemon pausa o epic (status `blocked`), notifica via Telegram, e continua monitorando outros work items.
4. **Given** o daemon esta executando um subprocess longo, **When** o operador interage via Telegram (ex: aprovar um gate de outro epic), **Then** o daemon responde ao callback sem bloquear — subprocess e interacao sao concorrentes.

---

### User Story 3 - Notificacao e aprovacao de gates via Telegram (Priority: P1)

Quando o pipeline atinge um human gate (ex: gate=human ou gate=1-way-door), o daemon notifica o operador via Telegram com botoes inline. O operador aprova ou rejeita com um toque. O daemon registra a decisao e retoma ou para o pipeline conforme a resposta.

**Why this priority**: Human gates sao requisito critico — 10 de 13 nodes L1 sao human-gated. Sem notificacao bidirecional, o pipeline nao pode operar autonomamente.

**Independent Test**: Inserir um gate pendente no banco, verificar que o daemon envia notificacao Telegram com botoes Aprovar/Rejeitar, e que ao clicar Aprovar o pipeline retoma.

**Acceptance Scenarios**:

1. **Given** o pipeline atinge um node com gate=human, **When** o daemon detecta o gate pendente, **Then** envia notificacao Telegram com botoes inline (Aprovar/Rejeitar) em menos de 5 segundos.
2. **Given** o operador recebeu notificacao de gate, **When** clica "Aprovar", **Then** o daemon registra aprovacao no banco, edita a mensagem Telegram para remover botoes, e retoma o pipeline.
3. **Given** o operador recebeu notificacao de gate, **When** clica "Rejeitar", **Then** o daemon registra rejeicao, marca o epic como `blocked`, e edita a mensagem Telegram.
4. **Given** um gate esta pendente ha mais de 24 horas, **When** o timeout expira, **Then** o daemon envia lembrete via Telegram.

---

### User Story 4 - Degradacao quando Telegram esta indisponivel (Priority: P2)

Quando o Telegram Bot API esta unreachable, o daemon nao para de funcionar. Ele muda para modo degradado: continua processando auto gates, pausa human gates, e envia alertas via ntfy.sh como fallback. Quando Telegram volta, o daemon retoma notificacoes normalmente.

**Why this priority**: Resiliencia e importante mas nao bloqueia MVP. O daemon deve ser util mesmo com Telegram fora.

**Independent Test**: Simular Telegram unreachable (health check falha 3x), verificar que o daemon muda para modo log-only + ntfy, e que auto gates continuam sendo processados.

**Acceptance Scenarios**:

1. **Given** o daemon esta operando normalmente, **When** Telegram API fica unreachable por 3 health checks consecutivos, **Then** o daemon muda para modo degradado (log-only + ntfy alerts), continua processando auto gates, e pausa human gates.
2. **Given** o daemon esta em modo degradado, **When** Telegram volta a responder, **Then** o daemon detecta em menos de 60 segundos, retoma notificacoes Telegram, e envia resumo dos gates pendentes acumulados.
3. **Given** o daemon esta em modo degradado com ntfy configurado, **When** um evento critico ocorre (node falhou, circuit breaker abriu), **Then** o daemon envia alerta via ntfy.sh.

---

### User Story 5 - Monitoramento via endpoints HTTP (Priority: P2)

O operador pode verificar o status do daemon e do pipeline via endpoints HTTP locais. O endpoint /health e usado pelo systemd para watchdog. O endpoint /status retorna o estado completo do pipeline em JSON.

**Why this priority**: Observabilidade e importante para operacao, mas o daemon funciona sem endpoints HTTP (Telegram cobre interacao).

**Independent Test**: Com o daemon rodando, fazer GET /health e GET /status e verificar respostas corretas.

**Acceptance Scenarios**:

1. **Given** o daemon esta rodando e saudavel, **When** GET /health, **Then** retorna 200 com corpo `{"status": "ok"}`.
2. **Given** o daemon esta rodando, **When** GET /status, **Then** retorna 200 com JSON contendo: estado do Telegram (connected/degraded), epics em execucao, nodes pendentes, estado do circuit breaker.
3. **Given** o daemon perdeu conexao com Telegram, **When** GET /health, **Then** retorna 200 (daemon esta vivo) mas /status indica Telegram como `degraded`.

---

### Edge Cases

- O que acontece quando o daemon inicia e ja existe um epic `in_progress` com nodes parcialmente completos? O daemon deve retomar do ultimo checkpoint (resume).
- O que acontece se dois epics estao `in_progress` simultaneamente para a mesma plataforma self-ref? O daemon processa o de maior prioridade primeiro e enfileira o segundo (sequencial obrigatorio).
- O que acontece se o subprocess `claude -p` fica preso (hang, sem output)? Watchdog timer com SIGKILL apos timeout configuravel (default 600s).
- O que acontece se o SQLite esta locked (outro processo escrevendo)? WAL mode + busy_timeout=5000ms resolve. Se persistir apos timeout, log erro e retry na proxima iteracao de polling.
- O que acontece se o operador reinicia o daemon enquanto um subprocess `claude -p` esta rodando? Graceful shutdown envia SIGTERM ao subprocess, aguarda ate 10s, depois SIGKILL.
- O que acontece se o daemon recebe callback de um gate que ja foi resolvido via CLI? Responde com "Gate ja resolvido" e nao altera estado.
- O que acontece se env vars obrigatorias (bot token, chat ID) nao estao definidas? O daemon inicia em modo sem Telegram (log-only), sem human gates habilitados, e loga warning.

## Requirements

### Functional Requirements

- **FR-001**: Sistema DEVE executar como processo persistente 24/7, sobrevivendo a reinicializacoes via mecanismo de supervisao (systemd).
- **FR-002**: Sistema DEVE monitorar a tabela de epics no banco de dados em intervalos configuraveis e iniciar o ciclo L2 automaticamente quando um epic muda para `in_progress`.
- **FR-003**: Sistema DEVE executar skills do pipeline na ordem topologica do DAG, respeitando dependencias entre nodes.
- **FR-004**: Sistema DEVE executar subprocessos de forma nao-bloqueante — interacoes com Telegram, health checks, e polling devem continuar enquanto subprocessos rodam.
- **FR-005**: Sistema DEVE limitar sessoes de subprocess concorrentes a um maximo configuravel (default 3).
- **FR-006**: Sistema DEVE pausar em human gates, notificar o operador via Telegram com botoes inline, e retomar quando aprovado.
- **FR-007**: Sistema DEVE retry subprocessos falhados com backoff exponencial (3 tentativas) e suspender apos falhas consecutivas (circuit breaker, 5 falhas → pausa de 5 minutos).
- **FR-008**: Sistema DEVE persistir estado de progresso apos cada node completo, permitindo retomada apos crash (resume do ultimo checkpoint).
- **FR-009**: Sistema DEVE detectar indisponibilidade do Telegram (3 health checks falhados) e mudar para modo degradado: continuar auto gates, pausar human gates, alertar via ntfy.sh.
- **FR-010**: Sistema DEVE retomar notificacoes Telegram automaticamente quando a conectividade e restaurada.
- **FR-011**: Sistema DEVE expor endpoint HTTP /health para verificacao de saude (systemd watchdog) e /status para estado do pipeline em JSON.
- **FR-012**: Sistema DEVE processar epics sequencialmente para plataformas self-ref (mesmo repositorio), nunca em paralelo.
- **FR-013**: Sistema DEVE fazer shutdown gracioso ao receber sinais de encerramento (SIGTERM/SIGINT), cancelando tasks e subprocessos de forma ordenada.
- **FR-014**: Sistema DEVE notificar o operador sobre decisoes 1-way-door detectadas durante execucao, pausando o pipeline ate aprovacao.
- **FR-015**: Sistema DEVE capturar e reportar erros automaticamente via servico de error tracking (Sentry).
- **FR-016**: Sistema DEVE usar logging estruturado (JSON) em todos os modulos para observabilidade.

### Key Entities

- **Daemon**: Processo principal que orquestra todas as tasks concorrentes (DAG scheduler, Telegram bot, health checker). Ciclo de vida: starting → running → degraded → shutting_down → stopped.
- **DAG Scheduler**: Task que faz polling no banco por epics prontos e despacha nodes na ordem topologica. Controla concorrencia via semaforo.
- **Telegram Integration**: Task que gerencia comunicacao bidirecional com operador — recebe callbacks, envia notificacoes de gates e decisoes.
- **Health Checker**: Task que verifica conectividade do Telegram periodicamente e controla transicao para modo degradado.
- **Circuit Breaker**: Controle de falhas consecutivas de subprocessos — fecha apos 5 falhas, recovery apos 5 minutos.

## Success Criteria

### Measurable Outcomes

- **SC-001**: O daemon inicia e responde em /health com status 200 em menos de 10 segundos apos o comando de inicio.
- **SC-002**: O daemon detecta um epic `in_progress` e inicia dispatch em menos de 30 segundos (intervalo de polling).
- **SC-003**: Notificacoes de gates chegam ao Telegram em menos de 5 segundos apos o pipeline atingir um human gate.
- **SC-004**: O daemon processa callbacks de aprovacao/rejeicao e retoma o pipeline em menos de 3 segundos apos o clique.
- **SC-005**: O daemon sobrevive a reinicializacao forcada (kill -9) e retoma do ultimo checkpoint em menos de 15 segundos via systemd restart.
- **SC-006**: O daemon opera por 72 horas continuas sem memory leak ou degradacao de performance.
- **SC-007**: Transicao para modo degradado (Telegram off) acontece em menos de 3 minutos (3 health checks de 60s).
- **SC-008**: O daemon faz shutdown gracioso em menos de 5 segundos ao receber SIGTERM.

## Assumptions

- O operador tem Python 3.12+ e systemd disponiveis no ambiente WSL2.
- O bot Telegram ja esta criado via @BotFather e as env vars (MADRUGA_TELEGRAM_BOT_TOKEN, MADRUGA_TELEGRAM_CHAT_ID) estao definidas.
- O banco SQLite (.pipeline/madruga.db) ja existe com schema migrado (epics 006, 009, 014 ja completos).
- O `claude` CLI esta instalado e autenticado no ambiente (subscription auth).
- O daemon roda como unico processo — nao ha outra instancia concorrente.
- ntfy.sh e opcional — daemon funciona sem ele, apenas sem fallback de notificacao.
- Sentry DSN e opcional — daemon funciona sem ele, apenas sem error tracking remoto.
- O daemon e acessivel apenas em localhost (127.0.0.1) — sem exposicao de rede externa.

---

handoff:
  from: speckit.specify
  to: speckit.clarify
  context: "Spec do daemon 24/7 completa com 5 user stories, 16 FRs, 8 success criteria. Sem [NEEDS CLARIFICATION]. Pronta para clarify ou direto para plan."
  blockers: []
  confidence: Alta
  kill_criteria: "Se o approach async (create_subprocess_exec) se provar inviavel com claude CLI, repensar arquitetura do dispatch."
