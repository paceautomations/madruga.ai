---
title: "ADR-017: Custom DAG Executor para Automacao do Pipeline"
status: accepted
date: 2026-03-30
---
# ADR-017: Custom DAG Executor para Automacao do Pipeline

## Status

Accepted — 2026-03-30

## Contexto

O pipeline Madruga AI tem 24 nodes em 2 niveis: L1 (13 nodes, foundation) e L2 (11 nodes por epic, ciclo de implementacao). Cada node tem dependencias, gate type (human/auto/1-way-door/auto-escalate), skill associada, e artefato de output. O DAG esta definido em `platform.yaml` e documentado em `pipeline-dag-knowledge.md`.

Hoje as skills sao invocadas manualmente via Claude Code (`/command`). O objetivo e automatizar a execucao: ler a definicao do DAG, resolver dependencias, despachar nodes prontos via `claude -p`, pausar em human gates, e adaptar automaticamente quando o YAML muda.

O runtime engine existente em `general/services/madruga-ai` tem um orchestrator (priority queue + semaphore) com fases hardcoded em Python. A nova abordagem deve ser data-driven: o YAML define o comportamento, nao o codigo.

## Decisao

Construir um custom DAG executor em Python que le `platform.yaml`, faz topological sort dos nodes, e executa sequencialmente via `claude -p` subprocess. Human gates pausam a execucao, gravam estado no SQLite, notificam via WhatsApp, e resumem quando aprovado.

**Estimativa realista de escopo:** 500-800 LOC para producao, distribuido em:
- DAG parser + topological sort (~80 LOC)
- Dispatch loop com state machine por node (~150 LOC)
- Human gate pause/resume (SQLite persist + CLI resume + WhatsApp notify) (~150 LOC)
- Error handling, retry, timeout, watchdog (~100 LOC)
- L2 epic cycle (branch management, scoping) (~100 LOC)
- Status reporting + integration com post_save.py (~50-100 LOC)

O YAML e o unico source of truth — mudar nodes, dependencias, ou gates no YAML altera o comportamento do executor sem tocar codigo Python.

**Nota sobre Prefect 3:** a rejeicao nao e por "stdlib-only" (o projeto ja usa FastAPI, pyyaml, etc.) mas por 3 razoes concretas: (1) human gates nao suportados no OSS — `pause_flow_run()` exige Prefect Cloud; (2) Prefect 3 removeu DAG explicito, exigindo traducao de YAML→Python flow; (3) 50+ dependencias transitivas para um problema que 800 LOC resolvem com deps que ja temos. Se Prefect OSS adicionar pause/resume nativo, reconsiderar.

## Alternativas Consideradas

### Alternativa A: Custom DAG Executor (escolhida)
- **Pros:** 500-800 LOC (gerenciavel), zero deps novas alem das existentes (pyyaml, sqlite3), YAML e source of truth direto, infraestrutura parcial existe (check-prerequisites.sh, post_save.py, db.py), human gates implementados exatamente como o projeto precisa, controle total
- **Cons:** sem crash recovery automatico (SQLite checkpoint apos cada node — perda maxima: re-executar 1 node), sem web UI dedicada (portal dashboard ja existe), human gate pause/resume e a parte mais complexa (persist state, wait signal, resume, handle timeout), requer testes unitarios + integracao dedicados
- **Fit:** Alto — reusa infraestrutura existente, controle total sobre human gates. Complexidade concentrada em 1 modulo testavel.

### Alternativa B: Prefect 3 (workflow orchestration, OSS)
- **Pros:** web UI para monitorar runs, retries/timeouts built-in, community ativa, Python-native
- **Cons:** **human gates NAO suportados no OSS** — `pause_flow_run()` so funciona no Prefect Cloud (pago). DAG-from-YAML requer camada de traducao (Prefect 3 removeu DAG explicito, usa Python control flow). ~50 packages de dependencia. Requer `prefect server start` rodando (~300MB RAM).
- **Rejeitada porque:** human gates sao requisito critico (10 de 13 nodes L1 sao human-gated). Sem suporte no OSS, e dealbreaker.

### Alternativa C: Temporal (durable execution)
- **Pros:** **melhor suporte a human gates** (signals + wait_condition — workflow dorme ate receber sinal, sem polling), crash recovery automatico (deterministic replay), duravel, local dev server disponivel
- **Cons:** requer Go binary (~112MB RAM), learning curve alta (constraints de deterministic replay: sem random, sem datetime.now() em workflows), `pip install temporalio` + Go server, overkill para 24 nodes single-user
- **Rejeitada porque:** complexidade desproporcional. O pipeline tem 24 nodes, nao milhares. SQLite checkpoint apos cada node + resume CLI cobre o caso de crash recovery. Se o pipeline crescer para 50+ nodes com alta concorrencia, Temporal e o upgrade natural (YAML source of truth permanece igual — so troca o backend de dispatch).

### Alternativa D: Apache Airflow
- **Pros:** DAG-native, scheduler maduro, web UI completa
- **Cons:** ~800MB RAM (scheduler + webserver + metadata DB), sem human gate nativo (precisa plugin externo), setup complexo em WSL2, DAG files sao Python (nao YAML-driven nativo), overhead massivo para o use case
- **Rejeitada porque:** resource usage e complexidade extremos para 24 nodes single-user. Ferramenta enterprise para problema single-developer.

## Consequencias

### Positivas
- YAML como unico source of truth — mudar o pipeline e editar um arquivo, nao codigo
- Zero dependencias novas — reusa Python stdlib + pyyaml + SQLite ja existentes
- Human gates implementados exatamente como o projeto precisa (SQLite + WhatsApp + resume CLI)
- Reusa 80% da infraestrutura: db.py, post_save.py, pipeline_nodes table, platform.yaml
- Migracao para Temporal e limpa se necessario: YAML fica igual, troca o dispatch backend

### Negativas
- Sem crash recovery automatico — se o processo morrer, o ultimo node completo esta no SQLite e o executor retoma dali, mas o node em andamento precisa re-executar
- Sem web UI dedicada para execucao — operador usa portal dashboard + CLI
- 500-800 LOC de codigo custom para manter (DAG parser, state machine, human gates, error handling)
- Human gate pause/resume e a parte mais complexa e requer testes dedicados (unit: DAG traversal, integration: pause/resume cycle)
- Schema SQLite pode precisar de extensoes (run IDs, attempt tracking, timestamps de pause/resume) nao previstas no schema atual

### Riscos
- Pipeline cresce para 50+ nodes com alta concorrencia → mitigacao: migrar dispatch para Temporal (YAML e node schema nao mudam)
- platform.yaml diverge do comportamento real (alguem muda YAML mas nao testa) → mitigacao: validacao automatica na inicializacao do executor (check deps existem, gates validos)

## Referencias

- [Prefect OSS vs Cloud](https://www.prefect.io/compare/prefect-oss)
- [Temporal Python SDK](https://docs.temporal.io/develop/python)
- [Temporal Workflow Pause via Signals](https://community.temporal.io/t/pausing-workflow-execution-until-signal-returns/6906)
- Implementacao existente: `.specify/scripts/post_save.py`, `.specify/scripts/db.py`
- DAG definition: `platforms/madruga-ai/platform.yaml` (pipeline.nodes)
- Pipeline knowledge: `.claude/knowledge/pipeline-dag-knowledge.md`
