---
title: "Containers"
updated: 2026-03-30
---
# C4 L2 — Containers

Visao de containers (unidades deployaveis) do Madruga AI. O sistema combina um portal de documentacao SSG, ferramentas CLI em Python, um runtime engine asyncio com DAG executor, e integracoes com sistemas externos (Claude API, GitHub, WhatsApp).

## Diagrama

```mermaid
graph TB
    subgraph users["Usuarios"]
        dev["Engenheiro / Arquiteto"]
        claude["Claude Code (interativo)"]
        daemon_user["Daemon (autonomo)"]
    end

    subgraph portal_group["Portal (SSG)"]
        portal["Portal<br/>Astro + Starlight<br/>:4321"]
        likec4_viewer["LikeC4 Viewer<br/>React Components"]
    end

    subgraph cli_tools["CLI Tools (Python)"]
        platform_cli["Platform CLI<br/>platform.py"]
        vision_build["Vision Build<br/>vision-build.py"]
        speckit_bridge["SpeckitBridge<br/>bridge.py"]
    end

    subgraph runtime["Runtime Engine (Python asyncio)"]
        daemon["Daemon<br/>daemon.py<br/>:8040"]
        dag_executor["DAG Executor<br/>dag_runner.py"]
        orchestrator["Orchestrator<br/>orchestrator.py"]
        pipeline["Pipeline Phases<br/>7 fases"]
    end

    subgraph intelligence["Intelligence (Python)"]
        debate["Debate Engine<br/>debate/"]
        decisions["Decision System<br/>decisions/"]
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
        whatsapp["WhatsApp<br/>via wpp-bridge :8030"]
        likec4_cli["LikeC4 CLI<br/>npm global"]
        copier_cli["Copier CLI<br/>pip"]
        sentry_cloud["Sentry Cloud<br/>Free Tier"]
    end

    dev --> portal
    dev --> platform_cli
    dev --> dashboard
    claude --> speckit_bridge

    portal --> filesystem
    portal --> likec4_viewer
    likec4_viewer --> filesystem

    platform_cli --> copier_cli
    platform_cli --> filesystem
    vision_build --> likec4_cli
    vision_build --> filesystem
    speckit_bridge --> filesystem

    daemon --> dag_executor
    daemon --> orchestrator
    dag_executor --> pipeline
    dag_executor --> claude_api
    orchestrator --> pipeline
    pipeline --> speckit_bridge
    pipeline --> claude_api
    pipeline --> debate
    pipeline --> decisions

    debate --> claude_api
    decisions --> whatsapp

    orchestrator --> sqlite
    dag_executor --> sqlite
    pipeline --> sqlite
    dashboard --> sqlite
    sentry_sdk --> sentry_cloud

    orchestrator --> github
    pipeline --> git

    style portal fill:#E1F5FE
    style daemon fill:#FFF3E0
    style dashboard fill:#F3E5F5
    style sqlite fill:#E8F5E9
    style claude_api fill:#FFEBEE
    style dag_executor fill:#FFF3E0
```

<!-- AUTO:containers -->
| # | Container | Tecnologia | Responsabilidade | Porta |
|---|-----------|-----------|------------------|-------|
| 1 | **Portal** | Astro + Starlight + LikeC4 React | Site SSG de documentacao de arquitetura com diagramas interativos; auto-descobre todas as plataformas | :4321 |
| 2 | **Platform CLI** | Python (platform.py) | Gerencia plataformas: new, lint, sync, register, status, import/export | CLI |
| 3 | **Vision Build** | Python (vision-build.py) | Exporta LikeC4 JSON e popula tabelas AUTO em markdown | CLI |
| 4 | **SpecKit Skills** | Markdown (.claude/commands/) | 20 skills consumidos interativamente pelo Claude Code | Claude Code |
| 5 | **SpeckitBridge** | Python (speckit/bridge.py) | Compositor que le skills/templates/constituicao e transforma skills interativos em prompts autonomos | Lib |
| 6 | **Daemon** | Python asyncio (daemon.py) + FastAPI | Processo 24/7 que orquestra execucao autonoma do pipeline. Inclui dashboard e health endpoints | :8040 |
| 7 | **DAG Executor** | Python (dag_runner.py) | Le pipeline DAG de platform.yaml, resolve dependencias (topological sort), despacha nodes via claude -p, gerencia human gates | Lib |
| 8 | **Orchestrator** | Python asyncio (orchestrator.py) | Gerencia ciclo de vida de epics, priority queue, slot semaphore, retries | Lib |
| 9 | **Pipeline Phases** | Python (7 modulos) | Executores das fases: specify, plan, tasks, implement, persona_interview, review, vision | Lib |
| 10 | **Debate Engine** | Python (debate/) | Debates multi-persona com convergencia para decisoes complexas | Lib |
| 11 | **Decision System** | Python (decisions/) | Classificador 1-way/2-way door com gates de aprovacao | Lib |
| 12 | **State Store** | SQLite WAL (madruga.db) | Persistencia de pipeline state, epics, decisions, memory, provenance, metrics | File |
| 13 | **Dashboard** | FastAPI + HTML | Dashboard web de status, metricas, e pipeline progress | :8040 |
| 14 | **Copier Templates** | Jinja2 + YAML | Scaffolding de novas plataformas com estrutura padrao | CLI |
| 15 | **wpp-bridge** | Node.js | Gateway HTTP para WhatsApp Web — send, receive, ask_choice | :8030 |
<!-- /AUTO:containers -->

## Requisitos Nao-Funcionais

| NFR | Target | Mecanismo | Container |
|-----|--------|-----------|-----------|
| **Disponibilidade** | 24/7 (daemon) | asyncio event loop com health check | Daemon |
| **Resiliencia** | 3 retries por fase | Retry com backoff + marcacao `blocked` | Orchestrator |
| **DAG resume** | < 5s retomada | SQLite checkpoint por node, resume CLI | DAG Executor |
| **Build time** | < 30s (portal SSG) | Astro static build + symlinks | Portal |
| **Storage** | Zero ops | SQLite file-based, sem servidor | State Store |
| **Observabilidade** | Health em < 500ms | FastAPI endpoint dedicado | Dashboard |
| **Isolamento** | ACL por integracao | Anti-Corruption Layer pattern | Todas integracoes |
| **Idempotencia** | Fases re-executaveis | Check de pre-condicoes + context acumulado | Pipeline Phases |
| **Extensibilidade** | N plataformas | Copier template + auto-discovery | Portal, Platform CLI |
| **Versionamento** | Tudo em Git | Filesystem-first, zero lock-in | Todos |
| **Concorrencia** | Max 3 claude -p | Semaforo asyncio | DAG Executor |
