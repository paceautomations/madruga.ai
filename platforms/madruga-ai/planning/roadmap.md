---
title: "Roadmap"
updated: 2026-04-05
---
# Madruga AI — Delivery Roadmap

> Sequencia de epics, milestones e definicao de MVP. North Star: 80% de epics processados autonomamente (pitch-to-PR sem intervencao humana).

---

## MVP

**MVP Epics:** 012 + 013 + 014 + 015 + 016 (todos os candidatos)
**MVP Criterion:** Pipeline executa pelo menos 1 epic completo (pitch-to-PR) em repo externo (ProsaUAI) com autonomia — human gates notificados via Telegram, specs revisadas por Subagent Judge, easter operando 24/7.
**Total MVP Estimate:** ~14w (team size: 1)

---

## Objetivos e Resultados

| Objetivo de Negocio | Product Outcome (leading indicator) | Baseline | Target | Epics |
|---------------------|--------------------------------------|----------|--------|-------|
| Autonomia do pipeline | % skills executaveis via CLI sem interacao manual | 0% | 80% | 013, 016 |
| Tempo de resposta a gates | Tempo medio entre notificacao e aprovacao de human gate | ∞ (manual) | < 30min | 014 |
| Qualidade de specs autonomas | % specs com review multi-perspectiva antes de implement | 0% | 100% | 015 |
| Pipeline cross-repo | Ciclos L2 executados em repos externos | 0 | ProsaUAI operacional | 012 |
| Uptime do pipeline | Horas/dia de easter operacional | 0 | 24h | 016 |

---

## Epics Shipped

```mermaid
gantt
    title Madruga AI — Epics Implementados
    dateFormat YYYY-MM-DD
    section Fundacao
    006 SQLite Foundation       :done, e006, 2026-03-29, 1d
    007 Directory Unification   :done, e007, 2026-03-29, 1d
    008 Quality & DX            :done, e008, 2026-03-29, 1d
    009 Decision Log BD         :done, e009, 2026-03-29, 1d
    010 Pipeline Dashboard      :done, e010, 2026-03-30, 1d
    011 CI/CD Pipeline          :done, e011, 2026-03-30, 1d
    012 Multi-repo Implement   :done, e012, 2026-03-31, 1d
    013 DAG Executor + Bridge    :done, e013, 2026-03-31, 1d
    014 Telegram Notifications   :done, e014, 2026-04-01, 1d
    015 Subagent Judge           :done, e015, 2026-04-01, 1d
    016 Easter 24/7              :done, e016, 2026-04-01, 1d
    section Post-MVP
    017 Observability & Evals    :done, e017, 2026-04-04, 1d
    018 Pipeline Hardening       :done, e018, 2026-04-05, 1d
    019 AI Infra as Code         :done, e019, 2026-04-05, 1d
    020 Code Quality & DX        :done, e020, 2026-04-05, 1d
    021 Pipeline Intelligence    :done, e021, 2026-04-05, 1d
```

| # | Epic | Descricao | Status | Concluido |
|---|------|-----------|--------|-----------|
| 006 | SQLite Foundation | BD SQLite (WAL mode) como state store para pipeline. Tabelas: platforms, pipeline_nodes, epics, epic_nodes, pipeline_runs, events, artifact_provenance. db.py com stdlib Python. Migrations incrementais. | **shipped** | 2026-03-29 |
| 007 | Directory Unification | SpecKit opera em epics/ (unificado). DAG dois niveis (L1 + L2). platform.yaml como manifesto declarativo. Copier template atualizado. | **shipped** | 2026-03-29 |
| 008 | Quality & DX | Boilerplate extraido para knowledge files. Skills enxutas. Auto-review por tier. Verify + QA + Reconcile skills implementadas. | **shipped** | 2026-03-29 |
| 009 | Decision Log BD | BD como source of truth para decisions e memory. FTS5 full-text search. CLI import/export. 5 novas migrations. 20+ funcoes em db.py. | **shipped** | 2026-03-29 |
| 010 | Pipeline Dashboard | Dashboard visual no portal Starlight. CLI `status` com tabela + JSON. Mermaid DAG. Filtros por plataforma. | **shipped** | 2026-03-30 |
| 011 | CI/CD Pipeline | GitHub Actions: lint (ruff + platform lint), db-tests, template tests, bash-tests, portal-build. 6 jobs. | **shipped** | 2026-03-30 |
| 012 | Multi-repo Implement | git worktree para repos externos. ensure_repo (SSH/HTTPS), worktree isolado, implement_remote (claude -p --cwd), PR via gh. 3 scripts, 28 testes. | **shipped** | 2026-03-31 |
| 013 | DAG Executor + SpeckitBridge | Custom DAG executor: Kahn's topological sort, claude -p dispatch, human gates (CLI pause/resume), retry/circuit breaker/watchdog. 494 LOC + 110 LOC extensions. 43 testes. | **shipped** | 2026-03-31 |
| 014 | Telegram Notifications | Bot Telegram standalone (aiogram 3.x): notifica human gates pendentes, inline keyboard approve/reject, health check, backoff exponencial, offset persistence. Migration 008. 28 testes. | **shipped** | 2026-04-01 |
| 015 | Subagent Judge + Decision Classifier | Tech-reviewers: 4 personas paralelas (Arch Reviewer, Bug Hunter, Simplifier, Stress Tester) + Judge pass. Decision Classifier (risk score). Substitui verify (L2) e Tier 3 (L1). YAML config extensivel. 47 testes. | **shipped** | 2026-04-01 |
| 016 | Easter 24/7 | FastAPI + asyncio easter: dag_scheduler (poll epics, dispatch pipeline), Telegram integration (gate approvals via inline keyboard), health_checker (degradation state machine + systemd watchdog), ntfy.sh fallback, Sentry. Endpoints /health + /status. systemd unit file. 393 LOC easter + ~200 LOC async dag_executor. 221 testes. | **shipped** | 2026-04-01 |
| 017 | Observability, Tracing & Evals | Traces hierarquicos por pipeline run (trace → spans), eval scoring heuristico (4 dimensoes: quality, adherence, completeness, cost_efficiency), API REST (/api/traces, /api/stats, /api/evals, /api/export/csv), portal React (4 tabs: Runs, Traces, Evals, Cost), cleanup automatico 90 dias, context threading no DAG (analyze→judge→qa→reconcile), auto-escalate gate. Migration 010. eval_scorer.py + observability_export.py. 393 testes. | **shipped** | 2026-04-04 |
| 018 | Pipeline Hardening & Safety | Context managers em dag_executor (elimina connection leaks), input validation (platform names, URLs, gate types), error hierarchy tipada (errors.py), graceful shutdown com signal handlers, path traversal security em post_save. | **shipped** | 2026-04-05 |
| 019 | AI Infrastructure as Code | CODEOWNERS (.claude/ requer review), CONTRIBUTING.md (regras de PR, commits, AI code), SECURITY.md (trust model, secrets, subprocess isolation), PR template, skill-lint com blast radius detection. | **shipped** | 2026-04-05 |
| 020 | Code Quality & DX | db.py (2.268 LOC) dividido em 4 modulos (db_core, db_pipeline, db_decisions, db_observability). Error hierarchy (errors.py). Structured logging (log_utils.py). Memory consolidation. 644 testes em 29 arquivos (~10.800 LOC). | **shipped** | 2026-04-05 |
| 021 | Pipeline Intelligence | Cost tracking (tokens_in/out, cost_usd parseados do claude -p JSON output). Hallucination guard (detecta outputs sem tool calls). Quick-fix skill (fast lane L2: specify→implement→judge). | **shipped** | 2026-04-05 |

---

## Delivery Sequence

```mermaid
gantt
    title Madruga AI — Roadmap de Entrega
    dateFormat YYYY-MM-DD
    section MVP
    012 Multi-repo Implement     :done, e012, 2026-03-31, 1d
    013 DAG Executor + Bridge    :done, e013, 2026-03-31, 1d
    014 Telegram Notifications   :done, e014, 2026-04-01, 1d
    015 Subagent Judge           :done, e015, 2026-04-01, 1d
    016 Easter 24/7              :done, e016, 2026-04-01, 1d
    section Post-MVP
    017 Observability & Evals    :done, e017, 2026-04-04, 1d
    018 Pipeline Hardening       :done, e018, 2026-04-05, 1d
    019 AI Infra as Code         :done, e019, 2026-04-05, 1d
    020 Code Quality & DX        :done, e020, 2026-04-05, 1d
    021 Pipeline Intelligence    :done, e021, 2026-04-05, 1d
```

### Sequencia e Justificativa

| Ordem | Epic | Risco | Justificativa da Posicao |
|-------|------|-------|--------------------------|
| 1 | 012 Multi-repo Implement | Medio | Value-first: desbloqueia ProsaUAI imediatamente. Escopo bem definido + reutilizacao de db.py. Real: 1d. |
| 2 | 013 DAG Executor + SpeckitBridge | Alto | Value: runtime funcional. Real: ~1d. Infraestrutura existente (db.py, post_save.py) + decisoes bem capturadas em context.md reduziram escopo. |
| 3 | 014 Telegram Notifications | Baixo | Depende da gate state machine de 013. aiogram e framework maduro — baixo risco tecnico. Real: 1d. |
| 3 | 015 Subagent Judge + Decision Classifier | Medio→Baixo | Paralelo com 014. Agent tool ja provado. Knowledge files = maioria do deliverable. Calibracao validada com 7 ADRs reais. |
| 4 | 016 Easter 24/7 | Baixo | Ultimo — monta em cima de tudo. Mecanico: asyncio event loop + health checks + systemd. Real: 1d. |
| 5 | 017 Observability, Tracing & Evals | Baixo | Primeiro post-MVP. Infraestrutura completa (easter, db.py, portal). Heuristicas simples — sem ML. Real: 1d. |

> 014 e 015 podem rodar em paralelo apos 013. Gantt mostra sequencial por team size = 1.

---

## Dependencias

```mermaid
graph LR
    E012["012 Multi-repo\nImplement (2w)"]
    E013["013 DAG Executor\n+ SpeckitBridge (6w)"]
    E014["014 Telegram\nNotifications (2w)"]
    E015["015 Subagent Judge\n+ Decision Classifier (2w)"]
    E016["016 Easter 24/7 (2w)"]
    E017["017 Observability\nTracing & Evals (2w)"]

    E012 --> E013
    E013 --> E014
    E013 --> E015
    E014 --> E016
    E015 --> E016
    E016 --> E017
```

---

## Milestones

| Milestone | Epics | Criterio de Sucesso | Estimativa |
|-----------|-------|---------------------|------------|
| **ProsaUAI Operacional** | 012 | `speckit.implement` executa em repo ProsaUAI via worktree, PR criado com `gh` | Semana 2 | Tooling pronto (ensure_repo, worktree, implement_remote). Falta teste end-to-end com ProsaUAI real. |
| **Runtime Funcional** | 012, 013 | DAG executor processa 1 pipeline L1 completo via CLI, human gates pausam/resumem corretamente | Semana 8 | Tooling pronto (ensure_repo, worktree, dag_executor). Falta teste end-to-end com claude -p real. |
| **Autonomia MVP** | 012-016 | 1 epic completo (pitch-to-PR) processado pelo easter em repo ProsaUAI, com Telegram notifications e Subagent Judge review | **Alcancado 2026-04-01** — todos os 5 epics MVP shipped. MADRUGA_MODE=auto habilita execucao end-to-end. Falta validacao end-to-end com ProsaUAI real. |

---

## Proximos Epics (candidatos)

> Todos os epics planejados (018-021) foram shipped em 2026-04-05. Proximos candidatos a definir.

| # | Candidato | Problema | Prioridade | Status |
|---|-----------|----------|------------|--------|
| — | ProsaUAI end-to-end | Primeiro epic completo processado pelo Easter em repo externo ProsaUAI — validacao real do pipeline autonomo pitch-to-PR | P0 | candidato |
| — | Roadmap auto-atualizado | Roadmap gerado automaticamente do estado real dos ciclos, com drift score e status de milestones | P2 | candidato |

---

## Roadmap Risks

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| `claude -p` instavel com prompts longos (stream-json bug) | Pipeline trava em nodes de implement | Media | **Mitigado**: `--output-format json` + subprocess `cwd=` (fix do --cwd). Watchdog SIGKILL. Retry 3x com backoff. |
| Gate state machine complexa demais para 013 | Atraso de 2-4w no epic mais critico | Media | **Nao ocorreu**: state machine implementada com 3 modos (MADRUGA_MODE) sem atrasos. |
| Calibracao de personas do Subagent Judge | Reviews com muito noise (false positives) | Media | **Mitigado**: 4 personas fixas + Judge filtra por Accuracy/Actionability/Severity. Calibrado com 7 ADRs reais. |
| aiogram breaking changes | TelegramAdapter quebra sem aviso | Baixa | Pin version. Health check detecta falha. Fallback log-only. Nao ocorreu ate agora. |
| Team size = 1 | Nenhum paralelismo real entre 014 e 015 | Alta | **Materializado**: todos os epics foram sequenciais. Appetite real ~1d cada (vs 2w planejado). |
| Documentation drift acumulado | Drift entre implementacao e docs cresce sem reconcile regular | Media | **Materializado**: 4/13 docs outdated no reconcile consolidado 017-021. Mitigacao: rodar reconcile apos cada epic. |
| stdlib shadowing (platform.py) | Import do modulo errado causa erros sutis | Media | **Mitigado**: renomeado para platform_cli.py + teste automatizado. |

---

## Nao Este Ciclo

| Item | Motivo da Exclusao | Revisitar Quando |
|------|--------------------|------------------|
| Namespace Unification (merge speckit.* em madruga.*) | Cosmetico, zero valor de negocio. Risco de churn em skills, docs e muscle memory. | Quando houver feedback de usuario externo pedindo namespace unico. |
| Developer Portal publico (Backstage-like) | Fora do scope — madruga-ai e ferramenta interna. Portal Starlight ja atende consumo interno. | Quando houver mais de 5 plataformas ativas ou usuarios externos. |
| Migracao de codigo de general/ | Abandonada. Runtime sera construido do zero em madruga.ai, capturando aprendizados mas sem migracao de codigo. | Nunca — decisao permanente (ADR-017, ADR-018). |
| Multi-tenant (N operadores) | Single-operator hoje (Gabriel). Multi-tenant adiciona autenticacao, isolamento, billing — complexidade injustificada. | Quando houver segundo operador com plataformas proprias. |
| Supabase migration | SQLite funciona bem na escala atual. | Quando >5 plataformas ativas ou portal precisar de real-time. |
| Wave-based parallel execution | Complexo (1-2d), valor especulativo. | Quando implementando epics grandes (6w+) com muitas tasks independentes. |
| Portal pipeline dashboard (visual DAG) | Nice-to-have. Portal ja tem status via CLI e tab Runs. | Quando 3+ plataformas ativas. |
| Pre-commit hooks (detect-secrets, shellcheck) | Overhead para solo dev. CI scan (epic 019) cobre o essencial. | Quando houver time >1 pessoa. |

---

## Notas da Revisao Tier 3

- Epic 014 antigo (Runtime Engine monolitico) foi splitado em 013+014+015 para evitar scope creep
- Epic 013 antigo (Namespace Unification) removido — cosmetico, zero valor de negocio
- Gate state machine centralizada em 013 — epics 014/015/016 consomem, nao estendem
- Estimativa total realista: ~14w (vs 8w otimista anterior). North Star 80% autonomia requer todos os 5 epics

---
handoff:
  from: roadmap
  to: epic-context
  context: "MVP completo (012-016 shipped). Epic 017 (Observability) em progresso. Proximo passo: completar L2 do epic 017."
  blockers: []
  confidence: Alta
  kill_criteria: "Mudanca fundamental nos epics planejados ou reordenacao de prioridades"
