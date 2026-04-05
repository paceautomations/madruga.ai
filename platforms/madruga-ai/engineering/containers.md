---
title: "Containers"
updated: 2026-04-02
---
# C4 L2 — Containers

Visao de containers (unidades deployaveis) do Madruga AI. O sistema combina um portal de documentacao SSG, ferramentas CLI em Python, um runtime engine asyncio com DAG executor, e integracoes com sistemas externos (Claude API, GitHub, Telegram).

## Diagrama

```mermaid
graph TB
    subgraph users["Usuarios"]
        dev["Engenheiro / Arquiteto"]
        claude["Claude Code (interativo)"]
        easter_user["Easter (autonomo)"]
    end

    subgraph portal_group["Portal (SSG)"]
        portal["Portal<br/>Astro + Starlight<br/>:4321"]
        likec4_viewer["LikeC4 Viewer<br/>React Components"]
    end

    subgraph cli_tools["CLI Tools (Python)"]
        platform_cli["Platform CLI<br/>platform_cli.py"]
        vision_build["Vision Build<br/>vision-build.py"]
    end

    subgraph runtime["Runtime Engine (Python asyncio)"]
        easter["Easter<br/>easter.py<br/>:8040"]
        dag_executor["DAG Executor<br/>dag_executor.py"]
    end

    subgraph intelligence["Intelligence (Python)"]
        judge["Subagent Judge<br/>Claude Code Agent tool"]
    end

    subgraph observability["Observability"]
        dashboard["Dashboard<br/>FastAPI + HTML<br/>:8040"]
        sentry_sdk["Sentry SDK<br/>Error Tracking"]
    end

    subgraph storage["Storage"]
        sqlite["SQLite<br/>madruga.db<br/>(state + metrics)"]
        filesystem["Filesystem<br/>.likec4, .md, .yaml"]
        git["Git<br/>Version Control"]
    end

    subgraph external["Sistemas Externos"]
        claude_api["Claude API<br/>claude -p subprocess"]
        github["GitHub<br/>Issues, PRs"]
        telegram["Telegram<br/>Bot API (aiogram)"]
        likec4_cli["LikeC4 CLI<br/>npm global"]
        copier_cli["Copier CLI<br/>pip"]
        sentry_cloud["Sentry Cloud<br/>Free Tier"]
    end

    dev --> portal
    dev --> platform_cli
    dev --> dashboard

    portal --> filesystem
    portal --> likec4_viewer
    likec4_viewer --> filesystem

    platform_cli --> copier_cli
    platform_cli --> filesystem
    vision_build --> likec4_cli
    vision_build --> filesystem

    easter --> dag_executor
    dag_executor --> claude_api
    dag_executor --> judge

    judge --> claude_api

    easter --> sqlite
    dag_executor --> sqlite
    dashboard --> sqlite
    sentry_sdk --> sentry_cloud

    dag_executor --> github

    style portal fill:#E1F5FE
    style easter fill:#FFF3E0
    style dashboard fill:#F3E5F5
    style sqlite fill:#E8F5E9
    style claude_api fill:#FFEBEE
    style dag_executor fill:#FFF3E0
```

<!-- AUTO:containers -->
| # | Container | Tecnologia | Responsabilidade | Porta |
|---|-----------|-----------|------------------|-------|
| 1 | **Portal** | Astro + Starlight + LikeC4 React | Site SSG de documentacao de arquitetura com diagramas interativos; auto-descobre todas as plataformas | :4321 |
| 2 | **Platform CLI** | Python (platform_cli.py) | Gerencia plataformas: new, lint, sync, register, status, import/export | CLI |
| 3 | **Vision Build** | Python (vision-build.py) | Exporta LikeC4 JSON e popula tabelas AUTO em markdown | CLI |
| 4 | **SpecKit Skills** | Markdown (.claude/commands/) | 24 skills consumidos interativamente pelo Claude Code ou autonomamente pelo easter | Claude Code |
| 5 | **Easter** | Python asyncio (easter.py) + FastAPI | Processo 24/7 que orquestra execucao autonoma do pipeline. DAG scheduler, Telegram polling, health checks, gate poller. Endpoints /health + /status | :8040 |
| 6 | **DAG Executor** | Python (dag_executor.py) | Le pipeline DAG de platform.yaml, resolve dependencias (topological sort), despacha nodes via claude -p, gerencia human gates (3 modos: manual/interactive/auto via MADRUGA_MODE), retry com circuit breaker | Lib |
| 7 | **Subagent Judge** | Python + Claude Code Agent tool | Subagent Paralelo + Judge Pattern (ADR-019): 4 personas (Architecture Reviewer, Bug Hunter, Simplifier, Stress Tester) + 1 juiz que filtra por Accuracy/Actionability/Severity. Output: BLOCKER/WARNING/NIT | Lib |
| 8 | **State Store** | SQLite WAL (madruga.db) | Persistencia de pipeline state, epics, decisions, memory, provenance, metrics | File |
| 9 | **Dashboard** | FastAPI + HTML | Dashboard web de status, metricas, e pipeline progress | :8040 |
| 10 | **Copier Templates** | Jinja2 + YAML | Scaffolding de novas plataformas com estrutura padrao | CLI |
| 11 | **Telegram Adapter** | Python (aiogram) | Adapter para Telegram Bot API (ADR-018) — send, ask_choice (inline buttons), alert, gate approvals | HTTPS outbound |
<!-- /AUTO:containers -->

## Requisitos Nao-Funcionais

| NFR | Target | Mecanismo | Container |
|-----|--------|-----------|-----------|
| **Disponibilidade** | 24/7 (easter) | asyncio event loop com health check | Easter |
| **Resiliencia** | 3 retries por fase | Retry com backoff + marcacao `blocked` | DAG Executor |
| **DAG resume** | < 5s retomada | SQLite checkpoint por node, resume CLI | DAG Executor |
| **Build time** | < 30s (portal SSG) | Astro static build + symlinks | Portal |
| **Storage** | Zero ops | SQLite file-based, sem servidor | State Store |
| **Observabilidade** | Health em < 500ms | FastAPI endpoint dedicado | Dashboard |
| **Isolamento** | ACL por integracao | Anti-Corruption Layer pattern | Todas integracoes |
| **Idempotencia** | Fases re-executaveis | Check de pre-condicoes + context acumulado | DAG Executor |
| **Extensibilidade** | N plataformas | Copier template + auto-discovery | Portal, Platform CLI |
| **Versionamento** | Tudo em Git | Filesystem-first, zero lock-in | Todos |
| **Concorrencia** | Max 3 claude -p | Semaforo asyncio | DAG Executor |
