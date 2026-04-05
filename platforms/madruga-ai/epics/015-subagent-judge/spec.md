# Feature Specification: Tech Reviewers + Decision Classifier

**Feature Branch**: `epic/madruga-ai/015-subagent-judge`
**Created**: 2026-04-01
**Status**: Draft
**Input**: Sistema de review multi-perspectiva extensível com 4 personas paralelas + Judge pass, Decision Classifier com score de risco, integrado ao pipeline L1+L2

## User Scenarios & Testing

### User Story 1 — Review automatizado de artefatos no pipeline (Priority: P1)

O operador do pipeline executa uma skill com gate 1-way-door (ex: `/madruga:adr`). Após a skill gerar o artefato, o sistema automaticamente lança 4 revisores especializados em paralelo (Architecture Reviewer, Bug Hunter, Simplifier, Stress Tester). Cada revisor analisa o artefato sob sua perspectiva e produz uma lista de findings. Um Judge recebe todos os findings, filtra noise por Accuracy/Actionability/Severity, e apresenta ao operador um report consolidado com score numérico e findings classificados (BLOCKER/WARNING/NIT).

**Why this priority**: É o núcleo do epic — sem o sistema de review multi-perspectiva, as demais funcionalidades não têm propósito. Substitui o review genérico atual (Tier 3) e o verify (L2) por um mecanismo de qualidade muito superior.

**Independent Test**: Pode ser testado executando qualquer skill com gate 1-way-door e verificando que o report consolidado aparece com findings das 4 personas antes do gate approval.

**Acceptance Scenarios**:

1. **Given** uma skill com gate 1-way-door está gerando um artefato, **When** a geração completa, **Then** 4 revisores são lançados em paralelo, cada um produz findings independentes, e um Judge consolida os findings em um report com score numérico.
2. **Given** os 4 revisores produziram 12 findings brutos, **When** o Judge avalia cada finding, **Then** findings que falham em Accuracy, Actionability ou Severity são filtrados, e o report final contém apenas findings válidos classificados como BLOCKER, WARNING ou NIT.
3. **Given** o Judge encontrou 1 BLOCKER, **When** o report é apresentado, **Then** a skill tenta corrigir o BLOCKER automaticamente antes de apresentar ao operador, e o report mostra o que foi corrigido.
4. **Given** o Judge não encontrou BLOCKERs, **When** o report é apresentado no gate, **Then** o score é ≥80 e o operador vê um resumo limpo de WARNINGs e NITs.

---

### User Story 2 — Judge substitui verify no ciclo L2 (Priority: P1)

O operador executa o ciclo L2 de um epic. Após analyze-post, em vez do antigo verify, o sistema executa o Judge (tech-reviewers) que avalia a implementação sob 4 perspectivas: aderência arquitetural, bugs/edge cases, simplicidade, e resiliência a stress. O Judge gera um `judge-report.md` com score e findings, na mesma posição do DAG onde o verify ficava.

**Why this priority**: Essencial para o fluxo L2 — sem isso, o pipeline L2 perde a etapa de validação de qualidade.

**Independent Test**: Executar um ciclo L2 completo e verificar que após analyze-post, o Judge roda (em vez do verify) e gera `judge-report.md` com score.

**Acceptance Scenarios**:

1. **Given** uma implementação completou analyze-post no ciclo L2, **When** o próximo passo é executado, **Then** o Judge (tech-reviewers) roda com as 4 personas avaliando o código implementado contra spec, tasks e arquitetura.
2. **Given** o Judge concluiu a avaliação, **When** o report é gerado, **Then** `judge-report.md` contém: score numérico, lista de findings por persona, verdict (pass/fail), e recomendações acionáveis.
3. **Given** o score do Judge é < 80, **When** o gate auto-escalate é avaliado, **Then** o resultado é escalado para o operador (ou Telegram no L2 automatizado) para decisão humana.

---

### User Story 3 — Classificação de decisões 1-way-door com score de risco (Priority: P2)

Durante a execução de uma skill L2, o sistema encontra uma decisão que precisa ser tomada (ex: remover uma coluna do banco). O Decision Classifier calcula um score de risco (Risco × Reversibilidade). Se o score ≥15, a decisão é classificada como 1-way-door: a execução pausa e o operador é notificado via Telegram com contexto, alternativas e botões de approve/reject. Se o score <15, a decisão é tomada automaticamente como 2-way-door.

**Why this priority**: Complementar ao Judge — garante que decisões críticas durante a execução não passem despercebidas. Mas o pipeline funciona sem isso (o Judge no final serve como safety net).

**Independent Test**: Simular uma decisão com score ≥15 durante uma skill L2 e verificar que o sistema pausa e envia notificação Telegram com inline keyboard.

**Acceptance Scenarios**:

1. **Given** uma skill L2 encontra a decisão "drop column legacy_id", **When** o Classifier calcula o score (Risco=5 × Reversibilidade=5 = 25), **Then** a decisão é classificada como 1-way-door e a execução pausa.
2. **Given** uma decisão 1-way-door foi detectada, **When** a execução pausa, **Then** uma notificação Telegram é enviada com: descrição da decisão, contexto, alternativas e botões approve/reject.
3. **Given** o operador aprova a decisão via Telegram, **When** a resposta é recebida, **Then** a execução retoma automaticamente.
4. **Given** uma skill L2 encontra a decisão "rename internal variable", **When** o Classifier calcula o score (Risco=1 × Reversibilidade=1 = 1), **Then** a decisão é tratada como 2-way-door e a execução segue automaticamente.

---

### User Story 4 — Configuração extensível de times de revisores (Priority: P2)

O operador quer adicionar um novo time de revisores (ex: `product` com PM e Designer) para rodar em skills de especificação. Ele cria os arquivos de prompt das novas personas, adiciona a entrada no YAML de configuração com o nome do time, lista de personas e pontos de execução, e o novo time passa a rodar automaticamente nas skills configuradas.

**Why this priority**: Importante para extensibilidade futura, mas o sistema funciona com apenas o time `engineering` inicial.

**Independent Test**: Adicionar um entry no YAML com um time fictício e verificar que os prompts são carregados e os subagents são lançados corretamente.

**Acceptance Scenarios**:

1. **Given** o YAML de configuração contém um time `engineering` com 4 personas, **When** o Judge é invocado, **Then** exatamente 4 subagents são lançados em paralelo usando os prompts das personas configuradas.
2. **Given** o operador adiciona um novo time `product` com 2 personas no YAML, **When** o Judge é invocado em um ponto configurado para esse time, **Then** 2 subagents adicionais são lançados com os prompts corretos.
3. **Given** um arquivo de prompt de persona não existe no caminho configurado, **When** o Judge é invocado, **Then** o sistema reporta erro claro indicando qual persona e qual caminho está faltando.

---

### User Story 5 — Judge como safety net para 1-way-doors que escaparam (Priority: P3)

O Judge, ao rodar no final do ciclo (posição do antigo verify), também revisa todas as decisões tomadas durante o ciclo L2. Se identifica uma decisão que deveria ter sido classificada como 1-way-door mas que passou como 2-way-door (escapou do Classifier inline), flagga como BLOCKER. Isso impede que decisões irreversíveis cheguem ao merge sem aprovação humana.

**Why this priority**: É uma rede de segurança — o Classifier inline deveria pegar a maioria dos casos. O safety net é para edge cases.

**Independent Test**: Forçar uma decisão 1-way-door que não foi detectada inline e verificar que o Judge a flagga como BLOCKER no report final.

**Acceptance Scenarios**:

1. **Given** durante o implement, uma decisão de "remover endpoint público" foi tomada automaticamente (Classifier não detectou), **When** o Judge roda no final, **Then** o Architecture Reviewer identifica a decisão como 1-way-door e o Judge a classifica como BLOCKER.
2. **Given** o Judge encontrou uma 1-way-door que escapou, **When** o report é apresentado, **Then** o finding inclui: qual decisão, por que é 1-way-door, e a recomendação de reverter ou obter aprovação.

---

### Edge Cases

- O que acontece quando um subagent (persona) falha ou timeout durante o review? O Judge deve continuar com os findings das personas que completaram e reportar quais falharam.
- O que acontece quando o score do Classifier é exatamente 15 (threshold)? Deve ser tratado como 1-way-door (≥15, inclusive).
- O que acontece quando todas as 4 personas retornam zero findings? O Judge deve gerar report com score 100 e verdict "pass" — não é erro.
- O que acontece quando o Telegram está indisponível e uma decisão 1-way-door precisa ser notificada? A execução deve pausar e aguardar, com retry automático conforme backoff do telegram_adapter.
- O que acontece quando o operador rejeita uma decisão 1-way-door via Telegram? A skill deve receber a rejeição e ajustar a abordagem ou abortar a decisão.

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE suportar configuração de times de revisores via arquivo YAML, onde cada time define: nome, lista de personas (id + caminho do prompt), e pontos de execução no pipeline.
- **FR-002**: O sistema DEVE lançar todas as personas de um time em paralelo (via Agent tool) e aguardar todos os resultados antes de executar o Judge pass.
- **FR-003**: O Judge DEVE avaliar cada finding individual em 3 critérios: Accuracy (factualmente correto?), Actionability (ação clara para resolver?), Severity (impacto justifica atenção?), e filtrar findings que falham em qualquer critério.
- **FR-004**: O Judge DEVE classificar findings aprovados em 3 níveis: BLOCKER (impede aprovação), WARNING (atenção recomendada), NIT (melhoria menor).
- **FR-005**: O Judge DEVE gerar um score numérico: `100 - (blockers×20 + warnings×5 + nits×1)`, com mínimo 0.
- **FR-006**: O Judge DEVE gerar um report estruturado (`judge-report.md`) contendo: score, findings por persona, verdict (pass se score ≥80, fail se <80), e recomendações.
- **FR-007**: O sistema DEVE substituir o node `verify` no epic_cycle do `platform.yaml` pelo node `judge`, mantendo a mesma posição no DAG (após analyze-post, antes de qa).
- **FR-008**: O sistema DEVE substituir o auto-review Tier 3 no `pipeline-contract-base.md` pelo Judge com o time `engineering`, para skills com gate 1-way-door no L1.
- **FR-009**: O Decision Classifier DEVE calcular score de risco como `Risco (1-5) × Reversibilidade (1-5)` para cada decisão encontrada durante execução de skills L2.
- **FR-010**: Decisões com score ≥15 DEVEM ser classificadas como 1-way-door, pausar a execução, e notificar o operador via Telegram com contexto, alternativas e botões approve/reject.
- **FR-011**: Decisões com score <15 DEVEM ser tratadas automaticamente como 2-way-door sem intervenção humana.
- **FR-012**: O telegram_adapter DEVE suportar um novo tipo de notificação para decisões 1-way-door, reutilizando a infraestrutura existente (inline keyboard, backoff, offset persistence).
- **FR-013**: Se uma persona falhar ou timeout durante o review, o Judge DEVE continuar com os findings das personas que completaram e incluir no report quais personas falharam.
- **FR-014**: O Judge DEVE funcionar como safety net — ao rodar no final do ciclo L2, deve revisar decisões tomadas durante o ciclo e flaggar como BLOCKER qualquer 1-way-door que não foi detectada pelo Classifier inline.
- **FR-015**: A skill `/madruga:verify` DEVE ser removida ou redirecionada para o Judge, mantendo retrocompatibilidade no período de transição.

### Key Entities

- **ReviewTeam**: Time de revisores configurado via YAML. Atributos: nome, lista de personas, pontos de execução no pipeline.
- **Persona**: Revisor especializado com prompt específico. Atributos: id, papel, caminho do arquivo de prompt.
- **Finding**: Issue encontrada por uma persona. Atributos: persona de origem, severidade, descrição, localização, sugestão.
- **ConsolidatedReview**: Resultado do Judge pass. Atributos: findings filtrados (blockers, warnings, nits), score, verdict, personas que falharam.
- **RiskScore**: Resultado do Decision Classifier. Atributos: padrão detectado, risco (1-5), reversibilidade (1-5), score calculado, classificação (1-way/2-way).

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% dos artefatos gerados por skills com gate 1-way-door passam por review multi-perspectiva (4 personas) antes de chegar ao operador.
- **SC-002**: O Judge filtra ≥30% dos findings brutos como noise (false positives), resultando em reports mais limpos e acionáveis.
- **SC-003**: O tempo total de review (4 personas paralelas + Judge) não excede 3 minutos por artefato.
- **SC-004**: 100% das decisões com score ≥15 pausam a execução e notificam o operador antes de prosseguir.
- **SC-005**: O ciclo L2 funciona sem interrupções com o Judge no lugar do verify — zero regressão funcional.
- **SC-006**: Adicionar um novo time de revisores requer apenas: criar arquivos de prompt + adicionar entrada YAML. Nenhuma modificação de código.

## Assumptions

- O Agent tool do Claude Code suporta lançamento de 4+ subagents em paralelo numa única mensagem — capacidade já validada no pipeline existente (Tier 3, pm-discovery).
- O telegram_adapter existente (aiogram) está funcional e testado — a extensão para decisões reutiliza a mesma infraestrutura.
- O volume de reviews no início é baixo (~3 nodes 1-way-door por pipeline). Calibração do Judge será manual por observação, sem feedback loop automatizado neste epic.
- A tabela de patterns do Decision Classifier (score de risco) cobre os cenários mais comuns. Patterns não cobertos defaultam para 2-way-door (safe failure mode — o Judge final serve como safety net).
- O analyze (pre e post) continua inalterado — responsável por aderência documental. O Judge é complementar, responsável por qualidade funcional.
- L1 continua no terminal Claude Code (interativo). Automação via Telegram/easter é exclusiva do L2.

---
handoff:
  from: speckit.specify
  to: speckit.clarify
  context: "Spec do tech-reviewers com 5 user stories, 15 FRs, 6 success criteria. Judge substitui verify (L2) e Tier 3 (L1). Decision Classifier com score de risco. Extensível via YAML. Safety net para 1-way-doors que escaparam."
  blockers: []
  confidence: Alta
  kill_criteria: "Se Agent tool do Claude Code não suportar 4+ subagents paralelos, ou se o overhead de tokens tornar o review inviável economicamente (>$10 por review cycle)"
