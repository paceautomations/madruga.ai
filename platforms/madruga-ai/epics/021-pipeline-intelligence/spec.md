# Feature Specification: Pipeline Intelligence

**Feature Branch**: `epic/madruga-ai/021-pipeline-intelligence`
**Created**: 2026-04-05
**Status**: Draft
**Input**: Epic 021 pitch — cost tracking, hallucination guard, fast lane, adaptive replanning

## User Scenarios & Testing

### User Story 1 — Visibilidade de Custos do Pipeline (Priority: P1) 🎯 MVP

O operador do pipeline (desenvolvedor ou tech lead) precisa saber quanto cada skill consome em tokens e custo real (USD) para tomar decisoes informadas sobre otimizacao e budget. Hoje as colunas `tokens_in`, `tokens_out`, `cost_usd` existem na tabela `pipeline_runs` mas nunca sao populadas — todos os valores sao NULL.

Apos cada dispatch (L1 ou L2), o sistema extrai automaticamente as metricas de uso do output JSON do CLI e persiste no banco. O portal "Cost" (epic 017) passa a exibir dados reais.

**Why this priority**: Visibilidade de custo e pre-requisito para qualquer decisao de otimizacao. Sem dados, qualquer ajuste e no escuro. Alem disso, e a mudanca com melhor ratio valor/esforco — uma unica correcao de campo (`cost_usd` → `total_cost_usd`) resolve o problema principal.

**Independent Test**: Executar um dispatch qualquer via `dag_executor.py`. Consultar `SELECT tokens_in, tokens_out, cost_usd FROM pipeline_runs ORDER BY id DESC LIMIT 1` — todos os valores devem ser NOT NULL. A tab "Cost" no portal deve renderizar os dados.

**Acceptance Scenarios**:

1. **Given** um dispatch L1 ou L2 bem-sucedido, **When** o dispatch completa, **Then** a row em `pipeline_runs` contem `tokens_in > 0`, `tokens_out > 0`, `cost_usd > 0`, `duration_ms > 0`.
2. **Given** um dispatch que falha (is_error=true no JSON), **When** o dispatch completa com erro, **Then** as metricas de custo ainda sao registradas (queremos rastrear custo inclusive de falhas).
3. **Given** um output JSON malformado ou vazio, **When** o parse falha, **Then** as metricas ficam NULL (fallback seguro, sem quebrar o pipeline).
4. **Given** dados populados em `pipeline_runs`, **When** o operador acessa a tab "Cost" no portal, **Then** os graficos mostram custo por skill e custo acumulado por epic.

---

### User Story 2 — Deteccao de Output Fabricado (Priority: P1) 🎯 MVP

Quando um skill gera um artifact sem fazer nenhuma chamada de ferramenta (zero reads, zero writes), o output provavelmente e alucinado — o agente "inventou" conteudo sem consultar os artifacts de dependencia. Hoje o pipeline aceita esse output silenciosamente.

O sistema deve detectar dispatches com zero tool calls e emitir um WARNING no log. O output e aceito (warning-only mode), mas a anomalia fica registrada para analise.

**Why this priority**: Seguranca contra output fabricado e um check de alto valor e baixo custo. Mesmo como warning-only, a visibilidade permite identificar problemas antes que se propaguem pelo pipeline.

**Independent Test**: Executar um dispatch mock que retorna JSON com `num_turns <= 2` (indicativo de zero tool calls). Verificar que um WARNING aparece nos logs contendo "hallucination" ou "fabricated".

**Acceptance Scenarios**:

1. **Given** um dispatch que completa com `num_turns <= 2` e `is_error = false`, **When** o hallucination guard executa, **Then** um WARNING e logado indicando output possivelmente fabricado.
2. **Given** um dispatch com `num_turns > 2`, **When** o hallucination guard executa, **Then** nenhum warning e emitido.
3. **Given** um output JSON malformado, **When** o hallucination guard executa, **Then** o guard retorna false (fail-open — nao bloqueia o pipeline por falha de parse).
4. **Given** um dispatch com `is_error = true` e `num_turns <= 2`, **When** o hallucination guard executa, **Then** nenhum warning e emitido (erros nao sao alucinacoes).

---

### User Story 3 — Fast Lane para Bug Fixes (Priority: P2)

O pipeline de 24 skills (11 passos L2) e heavy demais para mudancas pequenas. Corrigir um typo, ajustar uma config, ou resolver um bug de 1-2 arquivos nao deveria exigir plan, tasks, analyze, qa e reconcile.

O operador invoca `/quick-fix` (uso manual/interativo) e executa um ciclo comprimido: specify → implement → judge. Tres passos em vez de onze.

**Why this priority**: Produtividade do desenvolvedor. A maioria das mudancas do dia-a-dia sao pequenas. Sem fast lane, o pipeline incentiva bypass manual — pior que nao ter pipeline.

**Independent Test**: Executar `python3 .specify/scripts/dag_executor.py --platform madruga-ai --epic test --quick --dry-run` e verificar que apenas 3 nodes aparecem: specify, implement, judge.

**Acceptance Scenarios**:

1. **Given** o operador invoca `/quick-fix` com descricao de bug, **When** o skill processa, **Then** uma spec minimalista e gerada (problema + fix esperado + acceptance criteria).
2. **Given** a spec minimalista gerada, **When** o ciclo prossegue, **Then** implement executa com scope restrito seguido de judge para review.
3. **Given** o flag `--quick` passado ao `dag_executor.py`, **When** o DAG e construido, **Then** apenas 3 nodes sao incluidos (specify, implement, judge) com dependencias corretas.
4. **Given** uma mudanca que excede 50 LOC ou 2 arquivos, **When** o operador tenta usar quick-fix, **Then** o sistema recomenda o ciclo L2 completo (recomendacao, nao bloqueio).

---

### User Story 4 — Reavaliacao Adaptativa do Roadmap (Priority: P3)

Apos `reconcile` completar um epic grande (appetite > 2 semanas), o pipeline sugere automaticamente uma reavaliacao do roadmap. Epics longos frequentemente revelam informacoes que impactam a priorizacao dos proximos epics.

**Why this priority**: Melhoria incremental de planejamento. O valor e de longo prazo — so se manifesta apos multiplos epics completados. Por isso P3.

**Independent Test**: Verificar que `platform.yaml` contem o node `roadmap-reassess` como opcional, com `skip_condition` para epics <= 2w. Dry-run com epic >2w deve incluir o node; dry-run com epic <=2w deve pula-lo.

**Acceptance Scenarios**:

1. **Given** um epic com appetite > 2w que completa reconcile, **When** o ciclo L2 avanca, **Then** o node `roadmap-reassess` executa e sugere ajustes ao roadmap.
2. **Given** um epic com appetite <= 2w que completa reconcile, **When** o ciclo L2 avanca, **Then** o node `roadmap-reassess` e pulado (skip_condition).
3. **Given** mudancas sugeridas ao roadmap com menos de 3 linhas, **When** o reassess completa, **Then** as mudancas sao aplicadas automaticamente.
4. **Given** mudancas sugeridas ao roadmap com 3+ linhas, **When** o reassess completa, **Then** o sistema escala para aprovacao humana.

---

### Edge Cases

- Output JSON do CLI muda de formato em versao futura — parse deve falhar silenciosamente (metricas NULL, pipeline continua).
- Dispatch com `num_turns` alto mas sem tool calls reais — false negative do hallucination guard (edge case raro, aceitavel para MVP).
- Skills que legitimamente nao usam tools (ex: geracao de texto puro) — false positive do hallucination guard. Futuro: whitelist de skills isentos (nao no escopo deste epic).
- Quick-fix invocado para mudanca grande — recomendacao para usar ciclo completo, sem bloqueio hard.
- Roadmap-reassess sugere mudanca grande — escalation para humano, nao auto-apply.

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE extrair `tokens_in`, `tokens_out`, `cost_usd` e `duration_ms` do output JSON de cada dispatch e persistir em `pipeline_runs`.
- **FR-002**: O sistema DEVE usar o campo `total_cost_usd` (nao `cost_usd`) do JSON do CLI, conforme verificado na pesquisa T001.
- **FR-003**: O sistema DEVE registrar metricas mesmo quando o dispatch falha (`is_error = true`), pois custos de falhas tambem sao relevantes.
- **FR-004**: O sistema DEVE emitir WARNING quando um dispatch completa com heuristica de zero tool calls (`num_turns <= 2` e `is_error = false`).
- **FR-005**: O hallucination guard DEVE operar em modo warning-only — nao rejeitar ou bloquear output.
- **FR-006**: O skill `/quick-fix` DEVE oferecer ciclo L2 comprimido (specify → implement → judge) para mudancas pequenas.
- **FR-007**: O `dag_executor.py` DEVE suportar flag `--quick` que constroi DAG com apenas 3 nodes.
- **FR-008**: O node `roadmap-reassess` DEVE existir como opcional no `epic_cycle`, executando apenas para epics com appetite > 2 semanas.
- **FR-009**: O parse de metricas DEVE falhar silenciosamente (retornar valores vazios) quando o JSON esta malformado ou ausente — nunca quebrar o pipeline.
- **FR-010**: O auto-review do contrato base DEVE incluir check de hallucination guard como item universal (Tier 1).

### Key Entities

- **pipeline_runs**: Registro de cada execucao de skill no pipeline. Campos relevantes: `tokens_in`, `tokens_out`, `cost_usd`, `duration_ms`, `node_id`, `epic_id`, `platform`.
- **Dispatch Output**: JSON retornado pelo `claude -p --output-format json`. Campos-chave: `total_cost_usd`, `usage.input_tokens`, `usage.output_tokens`, `duration_ms`, `num_turns`, `is_error`.
- **Quick Cycle**: Subconjunto do `epic_cycle` com 3 nodes (specify, implement, judge) definidos em `platform.yaml`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% dos dispatches futuros tem `tokens_in`, `tokens_out` e `cost_usd` NOT NULL em `pipeline_runs`.
- **SC-002**: O operador consegue identificar o skill mais caro de um epic em menos de 30 segundos (via portal tab "Cost").
- **SC-003**: Dispatches com zero tool calls geram WARNING visivel nos logs em 100% dos casos detectaveis pela heuristica.
- **SC-004**: Bug fixes de 1-2 arquivos sao completados em 3 passos (vs 11 no ciclo completo) — reducao de ~73% no overhead de processo.
- **SC-005**: Epics grandes (>2w) recebem sugestao automatica de reavaliacao do roadmap apos conclusao.
- **SC-006**: Nenhuma mudanca quebra `make test` ou `make ruff`.

## Assumptions

- O formato do output JSON de `claude -p --output-format json` permanece estavel nas proximas versoes do CLI (versao atual: 2.1.90). Se mudar, o parse falha silenciosamente — sem impacto no pipeline, apenas metricas ficam NULL ate correcao.
- As colunas `tokens_in`, `tokens_out`, `cost_usd`, `duration_ms` ja existem na tabela `pipeline_runs` (migration 010, epic 017) — nao e necessario alterar schema.
- A heuristica `num_turns <= 2` e suficiente para MVP de hallucination detection. False positives em skills que nao usam tools sao aceitaveis por enquanto.
- O portal "Cost" tab (epic 017) ja tem componentes React que renderizam dados de custo — so precisam de dados reais populados.
- O skill `/quick-fix` e invocado manualmente pelo operador — nao ha automacao de deteccao de "mudanca pequena".
- O `dag_executor.py` suporta `optional: true` e `skip_condition` em nodes — nao e necessario implementar mecanismo novo para `roadmap-reassess`.

---
handoff:
  from: speckit.specify
  to: speckit.clarify
  context: "Spec completa para 4 features (cost tracking, hallucination guard, quick-fix, roadmap-reassess). Nenhum [NEEDS CLARIFICATION] pendente — todas as decisoes foram tomadas no pitch e validadas na pesquisa T001. Zero ambiguidades criticas restantes."
  blockers: []
  confidence: Alta
  kill_criteria: "Se o formato JSON do claude CLI mudar drasticamente (remocao dos campos usage/total_cost_usd/num_turns), US1 e US2 precisam redesign significativo."
