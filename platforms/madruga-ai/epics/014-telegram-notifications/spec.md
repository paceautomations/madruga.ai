# Feature Specification: Telegram Notifications

**Feature Branch**: `epic/madruga-ai/014-telegram-notifications`
**Created**: 2026-04-01
**Status**: Draft
**Input**: Notificacoes Telegram para human gates do pipeline com inline keyboard approve/reject

## User Scenarios & Testing

### User Story 1 — Receber notificacao de gate pendente (Priority: P1)

O operador esta longe do terminal. O dag_executor para em um human gate (ex: `vision`, gate type `human`). O operador recebe uma mensagem no Telegram com detalhes do gate e botoes inline "Aprovar" / "Rejeitar".

**Why this priority**: Sem notificacao, o operador nao sabe que o pipeline parou. Este e o caso de uso primario — elimina o polling manual.

**Independent Test**: Criar um gate pendente no DB, iniciar o bot, verificar que a mensagem chega no Telegram com botoes corretos dentro de 30 segundos.

**Acceptance Scenarios**:

1. **Given** um gate `waiting_approval` existe em `pipeline_runs`, **When** o telegram_bot detecta o gate, **Then** o operador recebe mensagem no Telegram com: nome do node, plataforma, tipo de gate, e botoes inline "Aprovar" / "Rejeitar".
2. **Given** o gate ja foi notificado, **When** o bot poll novamente, **Then** nao envia mensagem duplicada.
3. **Given** multiplos gates pendentes existem, **When** o bot poll, **Then** envia uma mensagem separada para cada gate.

---

### User Story 2 — Aprovar gate via Telegram (Priority: P1)

O operador recebe a notificacao com botoes inline. Toca em "Aprovar". O gate e atualizado no DB e a mensagem original e editada para refletir a decisao.

**Why this priority**: Bidirecionalidade e requisito critico — sem approve via Telegram, o operador precisa voltar ao terminal.

**Independent Test**: Criar gate pendente, enviar notificacao, tocar "Aprovar" no Telegram, verificar que `gate_status` mudou para `approved` no DB e mensagem foi editada.

**Acceptance Scenarios**:

1. **Given** mensagem com botoes inline foi enviada para gate X, **When** operador toca "Aprovar", **Then** `pipeline_runs.gate_status` muda para `approved`, `gate_resolved_at` e preenchido.
2. **Given** operador aprovou gate X, **When** mensagem e atualizada, **Then** botoes inline sao removidos e texto indica "Aprovado".
3. **Given** operador tenta aprovar gate ja resolvido, **When** toca no botao, **Then** recebe mensagem "Gate ja foi resolvido".

---

### User Story 3 — Rejeitar gate via Telegram (Priority: P2)

O operador recebe a notificacao e decide rejeitar. Toca em "Rejeitar". O gate e atualizado no DB como rejeitado.

**Why this priority**: Rejeicao e menos frequente mas necessaria para gates 1-way-door onde o operador discorda da decisao proposta.

**Independent Test**: Criar gate pendente, enviar notificacao, tocar "Rejeitar", verificar que `gate_status` mudou para `rejected` no DB.

**Acceptance Scenarios**:

1. **Given** mensagem com botoes inline foi enviada para gate X, **When** operador toca "Rejeitar", **Then** `pipeline_runs.gate_status` muda para `rejected`, `gate_resolved_at` e preenchido.
2. **Given** operador rejeitou gate X, **When** mensagem e atualizada, **Then** botoes sao removidos e texto indica "Rejeitado".

---

### User Story 4 — Enviar alertas e mensagens de status (Priority: P2)

Alem de gates, o sistema pode enviar mensagens informativas: node concluido com sucesso, erro critico, pipeline completo. Estas mensagens nao requerem resposta.

**Why this priority**: Visibilidade do estado do pipeline sem precisar abrir terminal. Complementa as notificacoes de gate.

**Independent Test**: Chamar `send()` e `alert()` programaticamente, verificar que mensagens chegam formatadas corretamente no Telegram.

**Acceptance Scenarios**:

1. **Given** um adapter Telegram configurado, **When** `send("Pipeline completo")` e chamado, **Then** operador recebe mensagem de texto formatada em HTML.
2. **Given** um adapter Telegram configurado, **When** `alert("Node falhou", level="error")` e chamado, **Then** operador recebe mensagem com indicador visual de severidade.

---

### User Story 5 — Health check e resiliencia (Priority: P3)

O bot monitora sua propria conectividade com a API do Telegram. Se a API ficar inacessivel, o bot loga o problema e tenta reconectar com backoff exponencial.

**Why this priority**: Resiliencia e importante para operacao desatendida mas nao bloqueia o uso basico.

**Independent Test**: Simular falha na API do Telegram, verificar que o bot loga o erro e tenta reconectar apos intervalo crescente.

**Acceptance Scenarios**:

1. **Given** bot esta rodando, **When** API do Telegram fica inacessivel, **Then** bot loga warning e entra em modo retry com backoff exponencial (2s → 30s max, fator 1.8x).
2. **Given** bot esta em modo retry, **When** API volta, **Then** bot retoma operacao normal e envia mensagem de recuperacao.
3. **Given** bot reinicia, **When** conecta novamente, **Then** nao reprocessa updates ja tratados (offset persistence).

---

### Edge Cases

- O que acontece quando o operador toca "Aprovar" mas outro processo ja aprovou o gate via CLI? O bot deve detectar e informar "Gate ja resolvido".
- O que acontece se o bot reinicia enquanto ha gates pendentes nao-notificados? Deve detectar e notificar na reinicializacao.
- O que acontece se o token do bot e invalido? Falha com mensagem clara no log sem entrar em loop infinito.
- O que acontece se o chat_id configurado nao existe ou o bot nao tem acesso? Falha com mensagem descritiva.
- O que acontece com mensagens muito longas (>4096 chars Telegram limit)? Truncar com indicador "... [truncado]".

## Requirements

### Functional Requirements

- **FR-001**: Sistema DEVE prover interface abstrata `MessagingProvider` com metodos `send`, `ask_choice`, e `alert`, permitindo troca de implementacao sem alterar consumidores.
- **FR-002**: Sistema DEVE implementar `TelegramAdapter` que conecta via Telegram Bot API com long-polling (outbound HTTPS only).
- **FR-003**: Sistema DEVE monitorar tabela `pipeline_runs` periodicamente e enviar notificacao para cada gate com `gate_status='waiting_approval'` ainda nao notificado.
- **FR-004**: Sistema DEVE apresentar botoes inline "Aprovar" e "Rejeitar" em cada notificacao de gate, com callback data no formato `gate:{run_id}:{action}` respeitando limite de 64 bytes.
- **FR-005**: Sistema DEVE processar callbacks de aprovacao/rejeicao, atualizar `pipeline_runs` via `approve_gate()`/`reject_gate()`, e editar mensagem original removendo botoes e atualizando texto.
- **FR-006**: Sistema DEVE evitar notificacoes duplicadas para gates ja notificados.
- **FR-007**: Sistema DEVE persistir offset de updates no armazenamento local para evitar reprocessamento apos restart.
- **FR-008**: Sistema DEVE implementar health check periodico (verificacao de conectividade a cada 60s) com retry usando backoff exponencial em caso de falha.
- **FR-009**: Sistema DEVE formatar mensagens em HTML mode com indicadores visuais de severidade para alertas.
- **FR-010**: Sistema DEVE ler configuracao de acesso (token e chat ID) de variaveis de ambiente com prefixo padrao do projeto.
- **FR-011**: Sistema DEVE funcionar como script standalone executavel via linha de comando.

### Key Entities

- **MessagingProvider**: Interface abstrata que define contrato de comunicacao. Metodos: `send`, `ask_choice`, `alert`. Permite multiplas implementacoes (Telegram, futuro ntfy.sh, etc.).
- **TelegramAdapter**: Implementacao de MessagingProvider para Telegram Bot API. Encapsula aiogram Bot instance, formatacao HTML, inline keyboards.
- **Gate Notification**: Representacao de um gate pendente detectado via polling do DB. Contem: run_id, node_id, platform_id, epic_id, gate type, timestamp.
- **Callback Action**: Acao recebida via inline keyboard. Formato: `gate:{run_id}:{a|r}`. Mapeia para approve_gate()/reject_gate().

## Success Criteria

### Measurable Outcomes

- **SC-001**: Operador recebe notificacao no Telegram dentro de 30 segundos apos gate ser criado no pipeline.
- **SC-002**: Operador consegue aprovar ou rejeitar gate com um unico toque, sem precisar acessar terminal.
- **SC-003**: Apos approve/reject, estado do gate e atualizado no armazenamento em menos de 2 segundos.
- **SC-004**: Zero notificacoes duplicadas — cada gate gera exatamente uma mensagem.
- **SC-005**: Bot recupera automaticamente de falhas de conectividade sem intervencao humana.
- **SC-006**: Bot reinicia sem perder estado — nao reprocessa updates antigos e detecta gates pendentes na inicializacao.

## Assumptions

- Operador ja tem Telegram instalado e configurou o bot via @BotFather (token e chat_id disponiveis).
- Volume de notificacoes e baixo (< 20 mensagens/dia, bem abaixo dos limites da API).
- O bot roda na mesma maquina que o pipeline (acesso direto ao armazenamento local).
- Apenas um operador recebe notificacoes (single chat_id). Suporte a multiplos operadores esta fora do scope.
- Fallback para outros canais (ntfy.sh) esta fora do scope — sera implementado em epic posterior.
- O dag_executor ja grava gates corretamente na tabela `pipeline_runs` com `gate_status='waiting_approval'` (epic 013 + fix do QA).
