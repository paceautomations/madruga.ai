---
title: "Feature Specification: DAG Executor + SpeckitBridge"
updated: 2026-03-31
status: Draft
---
# Feature Specification: DAG Executor + SpeckitBridge

**Feature Branch**: `epic/madruga-ai/013-dag-executor-bridge`
**Created**: 2026-03-31
**Status**: Draft
**Input**: Epic 013 — Runtime automatizado para pipeline Madruga AI

## User Scenarios & Testing

### User Story 1 — Execucao L1 do DAG (Priority: P1)

Operador executa `dag_executor.py --platform madruga-ai` e o executor le os 13 nodes L1 de `platform.yaml`, faz topological sort (Kahn's algorithm), e despacha cada node sequencialmente via `claude -p`. Para cada node, verifica exitcode 0 E existencia dos arquivos de output no filesystem. Progresso gravado no SQLite apos cada node.

**Why this priority**: Sem execucao L1, nenhuma outra funcionalidade do executor tem valor. E o fluxo principal.

**Independent Test**: Executar `dag_executor.py --platform madruga-ai --dry-run` e verificar que imprime a ordem topologica correta dos 13 nodes sem executar nenhum.

**Acceptance Scenarios**:

1. **Given** platform.yaml com 13 nodes L1, **When** `dag_executor.py --platform madruga-ai --dry-run`, **Then** imprime ordem topologica correta (platform-new → vision → ... → roadmap)
2. **Given** node com exitcode 0 e output files existentes, **When** dispatch completa, **Then** node marcado como `done` no DB via post_save.py
3. **Given** node com exitcode 0 mas output file ausente, **When** verificacao pos-dispatch, **Then** node marcado como `failed` com erro "output not found: <path>"
4. **Given** node opcional com skip_condition satisfeita, **When** executor avalia, **Then** node marcado como `skipped`

---

### User Story 2 — Human Gate Pause/Resume (Priority: P1)

Executor atinge node com gate type `human` ou `1-way-door` → grava `gate_status=waiting_approval` no DB → imprime mensagem com instrucoes → exit 0 (nao bloqueia). Operador aprova via `platform.py gate approve <run-id>`. Operador re-executa com `--resume` → executor pula nodes completos e retoma do proximo pronto.

**Why this priority**: 10 de 13 nodes L1 tem human gate. Sem gate state machine, executor nao pode operar.

**Independent Test**: Executar pipeline ate primeiro human gate, verificar que grava no DB e sai. Aprovar via CLI. Re-executar com --resume e verificar que retoma do ponto correto.

**Acceptance Scenarios**:

1. **Given** executor atinge node com gate=human, **When** dispatch necessario, **Then** grava `gate_status=waiting_approval` no DB, imprime "Aguardando aprovacao para <node>. Execute: platform.py gate approve <run-id>", exit 0
2. **Given** run com gate_status=waiting_approval, **When** `platform.py gate approve <run-id>`, **Then** DB atualizado: gate_status=approved, gate_resolved_at=now
3. **Given** run com gate_status=waiting_approval, **When** `platform.py gate reject <run-id>`, **Then** DB atualizado: gate_status=rejected, gate_resolved_at=now
4. **Given** nodes [A:done, B:waiting_approval(approved), C:pending], **When** `--resume`, **Then** executor pula A, despacha B (ja aprovado), continua para C
5. **Given** `platform.py gate list`, **When** existem gates pendentes, **Then** lista run-id, platform, node, tempo esperando

---

### User Story 3 — Error Handling: Retry, Circuit Breaker, Watchdog (Priority: P1)

Quando `claude -p` falha, executor retenta 3x com backoff exponencial (5s, 10s, 20s). Apos 5 falhas consecutivas (qualquer node), circuit breaker abre e suspende execucao por 300s. Se `claude -p` nao responde apos timeout configuravel, watchdog envia SIGKILL.

**Why this priority**: `claude -p` pode falhar por rate limit, timeout, ou bug. Sem resiliencia, uma falha mata o pipeline inteiro.

**Independent Test**: Simular falha de subprocess e verificar que retry ocorre 3x com delays corretos. Simular 5 falhas e verificar circuit breaker abre.

**Acceptance Scenarios**:

1. **Given** node falha na 1a tentativa, **When** retry ativo, **Then** retenta apos 5s. Se falha novamente, retenta apos 10s. Se falha novamente, retenta apos 20s. Apos 3 retries, marca como failed.
2. **Given** 5 nodes falharam consecutivamente, **When** proximo dispatch, **Then** circuit breaker abre: "Circuit breaker OPEN — suspendendo execucao por 300s"
3. **Given** circuit breaker aberto ha >300s, **When** proximo dispatch, **Then** half-open: tenta 1 node. Se sucesso, fecha. Se falha, reabre.
4. **Given** claude -p rodando ha mais que MADRUGA_EXECUTOR_TIMEOUT (default 600s), **When** watchdog detecta, **Then** SIGKILL no subprocess, node marcado failed com erro "timeout after Ns"
5. **Given** todas chamadas usam claude -p, **When** dispatch, **Then** flag `--output-format json` sempre presente (evita stream-json bug)

---

### User Story 4 — SpeckitBridge: Prompt Composition Generalizado (Priority: P2)

Generalizar `compose_prompt()` de `implement_remote.py` para aceitar qualquer skill type. Para skills L1 (madruga:*), monta prompt com instrucao de skill + contexto de artefatos de dependencia. Para skills L2 (speckit.*), monta prompt similar ao implement mas adaptado por tipo. `compose_skill_prompt()` e a funcao central.

**Why this priority**: Necessario para que o dispatch funcione — cada node precisa de um prompt correto para claude -p.

**Independent Test**: Chamar compose_skill_prompt() com diferentes skill types e verificar que prompts sao corretos e contem artefatos de dependencia.

**Acceptance Scenarios**:

1. **Given** node L1 com skill "madruga:vision" e depends=["platform-new"], **When** compose_skill_prompt(), **Then** prompt contem "Execute /madruga:vision madruga-ai" + conteudo de platform.yaml como contexto
2. **Given** node L2 com skill "speckit.implement" e epic "013-dag-executor-bridge", **When** compose_skill_prompt(), **Then** usa compose_prompt() existente (context.md + spec.md + plan.md + tasks.md)
3. **Given** node L2 com skill "speckit.specify" e epic slug, **When** compose_skill_prompt(), **Then** prompt contem "Execute /speckit.specify" + context.md + pitch.md como contexto
4. **Given** artefato de dependencia nao existe, **When** compose_skill_prompt(), **Then** log warning e prossegue sem aquele artefato (nao falha)

---

### User Story 5 — Execucao L2 por Epic (Priority: P2)

Operador executa `dag_executor.py --platform madruga-ai --epic 013-dag-executor-bridge` e o executor le os 11 nodes de `epic_cycle.nodes` em platform.yaml. Estado armazenado na tabela `epic_nodes`. Mesma logica de dispatch/gate/retry, so muda a fonte do DAG e a tabela de estado.

**Why this priority**: L2 e o ciclo de implementacao de epics. Sem L2, pipeline so faz foundation (L1).

**Independent Test**: `dag_executor.py --platform madruga-ai --epic 013-dag-executor-bridge --dry-run` imprime ordem L2 correta.

**Acceptance Scenarios**:

1. **Given** platform.yaml com 11 nodes epic_cycle, **When** `--epic 013-dag-executor-bridge --dry-run`, **Then** imprime: epic-context → specify → clarify? → plan → tasks → analyze → implement → analyze-post → verify → qa? → reconcile
2. **Given** epic em execucao L2, **When** node completa, **Then** estado gravado em `epic_nodes` (nao pipeline_nodes)
3. **Given** node L2 com template `{epic}/spec.md`, **When** verificacao de output, **Then** resolve {epic} para `epics/013-dag-executor-bridge/spec.md`

---

### User Story 6 — Resume apos Crash/Restart (Priority: P2)

Apos crash, restart, ou gate approval, operador re-executa com `--resume`. Executor le estado do DB, identifica nodes completos, e retoma do primeiro node pronto (deps satisfeitas, nao completo). Tempo de resume < 5s (NFR Q8).

**Why this priority**: Sem resume, qualquer interrupcao exige re-executar todo o pipeline desde o inicio.

**Independent Test**: Marcar N nodes como done no DB, executar com --resume, verificar que comeca do node N+1.

**Acceptance Scenarios**:

1. **Given** DB com nodes [A:done, B:done, C:pending, D:pending], **When** `--resume`, **Then** executor comeca de C (pula A e B)
2. **Given** DB com node B gate_status=approved, **When** `--resume`, **Then** executor executa B (ja aprovado) e continua
3. **Given** DB com node B gate_status=waiting_approval (nao aprovado), **When** `--resume`, **Then** executor imprime "Gate pendente para B" e exit 0
4. **Given** DB com 13 nodes (10 done), **When** `--resume`, **Then** resume completa em < 5s (leitura DB + skip)

---

### Edge Cases

- DAG com ciclo (dependencia circular): abortar com erro "Cycle detected in DAG: [nodes]"
- Node com dependencia de node que nao existe: abortar com erro "Unknown dependency: <dep> for node <node>"
- platform.yaml sem secao `pipeline`: abortar com erro "No pipeline section in platform.yaml"
- --epic sem epic_cycle em platform.yaml: abortar com erro "No epic_cycle section in platform.yaml"
- claude binary nao encontrado (shutil.which("claude") is None): abortar com erro "claude CLI not found"
- DB locked (SQLITE_BUSY): busy_timeout=5000ms ja configurado, retry transparente
- Dois executores simultaneos: nao suportado neste epic (single executor). Segundo executor ve estado inconsistente — documentar como limitacao.

## Requirements

### Functional Requirements

- **FR-001**: Sistema DEVE parsear `platform.yaml` secao `pipeline.nodes` e extrair nodes com id, skill, outputs, depends, gate, layer, optional
- **FR-002**: Sistema DEVE parsear `platform.yaml` secao `pipeline.epic_cycle.nodes` quando flag `--epic` presente
- **FR-003**: Sistema DEVE executar topological sort via Kahn's algorithm com deteccao de ciclos
- **FR-004**: Sistema DEVE despachar cada node via `subprocess.run(["claude", "-p", prompt, "--cwd", cwd, "--output-format", "json"])` com timeout
- **FR-005**: Sistema DEVE verificar output de cada node: exitcode == 0 AND todos os arquivos em `outputs` existem no filesystem
- **FR-006**: Sistema DEVE gravar estado de cada node no DB via `upsert_pipeline_node()` (L1) ou `upsert_epic_node()` (L2)
- **FR-007**: Sistema DEVE pausar em nodes com gate `human` ou `1-way-door`: gravar gate_status=waiting_approval, imprimir instrucoes, exit 0
- **FR-008**: Sistema DEVE implementar `platform.py gate approve <run-id>` que grava gate_status=approved + gate_resolved_at
- **FR-009**: Sistema DEVE implementar `platform.py gate reject <run-id>` que grava gate_status=rejected + gate_resolved_at
- **FR-010**: Sistema DEVE implementar `platform.py gate list` que lista gates pendentes com run-id, platform, node, tempo
- **FR-011**: Sistema DEVE retentar nodes falhados 3x com backoff exponencial (5s, 10s, 20s)
- **FR-012**: Sistema DEVE implementar circuit breaker: abrir apos 5 falhas consecutivas, recovery em 300s, half-open tenta 1
- **FR-013**: Sistema DEVE implementar watchdog: SIGKILL apos MADRUGA_EXECUTOR_TIMEOUT (default 600s) via subprocess timeout
- **FR-014**: Sistema DEVE compor prompt por skill type via `compose_skill_prompt()`: L1 madruga:* e L2 speckit.*
- **FR-015**: Sistema DEVE suportar `--resume`: ler estado do DB, pular nodes done/skipped, retomar do proximo pronto
- **FR-016**: Sistema DEVE suportar `--dry-run`: imprimir ordem de execucao sem despachar
- **FR-017**: Sistema DEVE pular nodes opcionais quando skip_condition satisfeita
- **FR-018**: Sistema DEVE registrar cada execucao via insert_run()/complete_run() em pipeline_runs

### Non-Functional Requirements

- **NFR-001**: Zero dependencias novas (apenas stdlib Python + pyyaml existente)
- **NFR-002**: Sync subprocess — sem asyncio (concorrencia e epic 016)
- **NFR-003**: 500-800 LOC de producao (excluindo testes)
- **NFR-004**: Resume em < 5s (leitura DB + skip de nodes completos)
- **NFR-005**: pathlib.Path para todos os caminhos
- **NFR-006**: logging.getLogger(__name__) por modulo
- **NFR-007**: SQLite WAL mode com busy_timeout=5000ms

### Key Entities

- **Node**: Unidade de execucao no DAG. Atributos: id, skill, outputs, depends, gate, layer, optional, skip_condition
- **Run**: Registro de execucao de um node. Atributos: run_id, platform_id, epic_id, node_id, status, gate_status, timestamps
- **CircuitBreaker**: State machine com 3 estados (closed/open/half-open). Atributos: failure_count, last_failure_at, state

## Success Criteria

### Measurable Outcomes

- **SC-001**: `dag_executor.py --platform madruga-ai --dry-run` imprime ordem topologica correta dos 13 nodes L1
- **SC-002**: `dag_executor.py --platform madruga-ai --epic 013 --dry-run` imprime ordem dos 11 nodes L2
- **SC-003**: Todos os testes pytest passam (>= 15 testes)
- **SC-004**: LOC de producao entre 500-800 (excluindo testes)
- **SC-005**: Resume completa em < 5s com 10 nodes ja completos
- **SC-006**: ruff check e ruff format passam sem erros
- **SC-007**: Migration 007 aplica sem erro e gate_status visivel no schema

## Assumptions

- `claude` CLI esta instalado e acessivel via PATH
- `.pipeline/madruga.db` existe com migrations ate 006 aplicadas
- `platform.yaml` segue o schema existente (validado por platform.py lint)
- Nao ha execucao concorrente — single executor (concorrencia e epic 016)
- Telegram notifications nao estao no scope (epic 014)
- Subagent Judge nao esta no scope (epic 015)

---
handoff:
  from: speckit.specify
  to: speckit.plan
  context: "Spec completa: 6 user stories, 18 FRs, 7 NFRs. Pronto para plan."
  blockers: []
  confidence: Alta
