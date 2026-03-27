---
title: "Containers"
updated: 2026-03-27
---
# C4 L2 — Containers

Visao de containers (unidades deployaveis) do Madruga AI. O sistema combina um portal de documentacao SSG, ferramentas CLI em Python, um runtime engine asyncio, e integracoes com sistemas externos (Claude API, Obsidian, GitHub, WhatsApp).

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
        daemon["Daemon<br/>daemon.py"]
        orchestrator["Orchestrator<br/>orchestrator.py"]
        kanban_poller["Kanban Poller<br/>kanban_poll.py"]
        pipeline["Pipeline Phases<br/>7 fases"]
    end

    subgraph intelligence["Intelligence (Python)"]
        debate["Debate Engine<br/>debate/"]
        decisions["Decision System<br/>decisions/"]
    end

    subgraph observability["Observability"]
        dashboard["Dashboard<br/>FastAPI + HTML<br/>:8080"]
    end

    subgraph storage["Storage"]
        sqlite["SQLite<br/>madruga.db"]
        filesystem["Filesystem<br/>.likec4, .md, .yaml"]
        git["Git<br/>Version Control"]
    end

    subgraph external["Sistemas Externos"]
        claude_api["Claude API<br/>Anthropic"]
        obsidian["Obsidian Vault<br/>Kanban Board"]
        github["GitHub<br/>Issues, PRs"]
        whatsapp["WhatsApp<br/>Notificacoes"]
        likec4_cli["LikeC4 CLI<br/>npm global"]
        copier_cli["Copier CLI<br/>pip"]
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

    daemon --> orchestrator
    daemon --> kanban_poller
    orchestrator --> pipeline
    kanban_poller --> obsidian
    pipeline --> speckit_bridge
    pipeline --> claude_api
    pipeline --> debate
    pipeline --> decisions

    debate --> claude_api
    decisions --> whatsapp
    decisions --> claude_api

    orchestrator --> sqlite
    pipeline --> sqlite
    dashboard --> sqlite

    orchestrator --> github
    pipeline --> git

    style portal fill:#E1F5FE
    style daemon fill:#FFF3E0
    style dashboard fill:#F3E5F5
    style sqlite fill:#E8F5E9
    style claude_api fill:#FFEBEE
```

<!-- AUTO:containers -->
| # | Container | Tecnologia | Responsabilidade | Porta |
|---|-----------|-----------|------------------|-------|
| 1 | **Portal** | Astro + Starlight + LikeC4 React | Site SSG de documentacao de arquitetura com diagramas interativos; auto-descobre todas as plataformas | :4321 |
| 2 | **Platform CLI** | Python (platform.py) | Gerencia plataformas: new, lint, sync, register, list | CLI |
| 3 | **Vision Build** | Python (vision-build.py) | Exporta LikeC4 JSON e popula tabelas AUTO em markdown | CLI |
| 4 | **SpecKit Skills** | Markdown (.claude/commands/) | 13 skills (4 madruga + 9 speckit) consumidos interativamente pelo Claude Code | Claude Code |
| 5 | **SpeckitBridge** | Python (speckit/bridge.py) | Compositor que le skills/templates/constituicao e transforma skills interativos em prompts autonomos | Lib |
| 6 | **Daemon** | Python asyncio (daemon.py) | Processo 24/7 que orquestra execucao autonoma do pipeline | Background |
| 7 | **Orchestrator** | Python asyncio (orchestrator.py) | Gerencia ciclo de vida de epics e avanco de fases | Lib |
| 8 | **Kanban Poller** | Python (kanban_poll.py) | Polling do kanban Obsidian a cada 60s para detectar mudancas | Background |
| 9 | **Pipeline Phases** | Python (7 modulos) | Executores das fases: specify, plan, tasks, implement, persona_interview, review, vision | Lib |
| 10 | **Debate Engine** | Python (debate/) | Debates multi-persona com convergencia para decisoes complexas | Lib |
| 11 | **Decision System** | Python (decisions/) | Classificador 1-way/2-way door com gates de aprovacao | Lib |
| 12 | **Memory Store** | SQLite (madruga.db) | Persistencia de epics, patterns, learning, persona accuracy | File |
| 13 | **Dashboard** | FastAPI + HTML | Dashboard web de status e metricas do pipeline | :8080 |
| 14 | **Copier Templates** | Jinja2 + YAML | Scaffolding de novas plataformas com estrutura padrao | CLI |
<!-- /AUTO:containers -->

## Requisitos Nao-Funcionais

| NFR | Target | Mecanismo | Container |
|-----|--------|-----------|-----------|
| **Disponibilidade** | 24/7 (daemon) | asyncio event loop com health check | Daemon |
| **Latencia de polling** | < 60s deteccao | Polling interval configuravel | Kanban Poller |
| **Resiliencia** | 3 retries por fase | Retry com backoff + marcacao `blocked` | Orchestrator |
| **Build time** | < 30s (portal SSG) | Astro static build + symlinks | Portal |
| **Storage** | Zero ops | SQLite file-based, sem servidor | Memory Store |
| **Observabilidade** | Health em < 500ms | FastAPI endpoint dedicado | Dashboard |
| **Isolamento** | ACL por integracao | Anti-Corruption Layer pattern | Todas integracoes |
| **Idempotencia** | Fases re-executaveis | Check de pre-condicoes + context acumulado | Pipeline Phases |
| **Extensibilidade** | N plataformas | Copier template + auto-discovery | Portal, Platform CLI |
| **Versionamento** | Tudo em Git | Filesystem-first, zero lock-in | Todos |
