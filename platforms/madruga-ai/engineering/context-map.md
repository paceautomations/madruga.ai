---
title: "Context Map"
updated: 2026-04-02
---
# Context Map (DDD Estrategico)

Mapa de dominios do Madruga AI seguindo Domain-Driven Design estrategico. O sistema e composto por 6 bounded contexts: 2 core (Documentation, Specification), 2 supporting (Execution, Intelligence), e 2 generic (Integration, Observability).

## Mapa de Dominios

```mermaid
graph TB
    subgraph core["Core Domains"]
        doc["Documentation<br/><i>Plataformas, Portal,<br/>LikeC4 Models, AUTO Markers</i>"]
        spec["Specification<br/><i>SpecKit Pipeline, Skills,<br/>Templates, Constitution</i>"]
    end

    subgraph supporting["Supporting Domains"]
        exec["Execution<br/><i>Easter, DAG Executor,<br/>MADRUGA_MODE</i>"]
        intel["Intelligence<br/><i>Subagent Judge (ADR-019),<br/>Decision Classifier, Stress Test</i>"]
    end

    subgraph generic["Generic Domains"]
        integ["Integration<br/><i>Telegram, GitHub,<br/>Claude API, LikeC4, Sentry</i>"]
        obs["Observability<br/><i>Dashboard, Health,<br/>Metrics, Sentry SDK</i>"]
    end

    doc <-->|"Customer-Supplier"| spec
    spec <-->|"Customer-Supplier"| exec
    exec -->|"ACL"| integ
    intel <-->|"Customer-Supplier"| exec
    obs -.->|"Pub-Sub"| doc
    obs -.->|"Pub-Sub"| spec
    obs -.->|"Pub-Sub"| exec
    obs -.->|"Pub-Sub"| intel
    obs -.->|"Pub-Sub"| integ
    integ -->|"Conformist"| ext["APIs Externas<br/><i>Claude, GitHub,<br/>Telegram, Sentry</i>"]

    style core fill:#E3F2FD
    style supporting fill:#FFF8E1
    style generic fill:#F3E5F5
    style ext fill:#FFEBEE
```

<!-- AUTO:domains -->
| # | Dominio | Tipo | Modulos | Responsabilidade |
|---|---------|------|---------|------------------|
| 1 | **Documentation** | Core | Portal, Platform CLI, Vision Build, LikeC4 Models | Gerencia plataformas documentadas, portal SSG, modelos de arquitetura e populacao automatica de tabelas via AUTO markers |
| 2 | **Specification** | Core | SpecKit Skills, Copier Templates | Pipeline de especificacao (specify -> plan -> tasks -> implement), composicao de prompts (via dag_executor), scaffolding de plataformas |
| 3 | **Execution** | Supporting | Easter, DAG Executor | Execucao autonoma: easter asyncio (FastAPI), DAG executor le pipeline de platform.yaml, 3 modos de operacao (MADRUGA_MODE) |
| 4 | **Intelligence** | Supporting | Subagent Judge (ADR-019), Decision Classifier, Stress Test | Review multi-perspectiva via 4 personas + 1 juiz, classificacao 1-way/2-way door, gates de aprovacao, stress testing |
| 5 | **Integration** | Generic | Telegram Adapter (aiogram), GitHub Client, Claude API Client, LikeC4 CLI, Sentry SDK | ACL para sistemas externos — isola contratos externos do dominio interno |
| 6 | **Observability** | Generic | Dashboard, Health Checks, SQLite Metrics, Sentry SDK | Visibilidade operacional: dashboard FastAPI, health checks, metricas em SQLite, error tracking via Sentry |
<!-- /AUTO:domains -->

## Relacoes entre dominios

<!-- AUTO:relations -->
| # | Upstream | Downstream | Padrao | Descricao |
|---|----------|------------|--------|-----------|
| 1 | **Documentation** | **Specification** | Customer-Supplier | Specification consome contexto de visao e modelo de arquitetura de Documentation para gerar specs |
| 2 | **Specification** | **Execution** | Customer-Supplier | Execution consome specs, plans e tasks gerados por Specification para executar o pipeline |
| 3 | **Execution** | **Integration** | ACL (Anti-Corruption Layer) | Execution acessa sistemas externos via ACL — contratos externos nao vazam para o dominio |
| 4 | **Intelligence** | **Execution** | Customer-Supplier | Subagent Judge e Decision Classifier servem Execution com reviews multi-perspectiva e classificacao de decisoes durante fases do pipeline |
| 5 | **Observability** | **Todos** | Pub-Sub (fire-and-forget) | Observability subscreve eventos de todos os contextos sem acoplamento — falha silenciosa |
| 6 | **Integration** | **APIs Externas** | Conformist | Integration conforma-se aos contratos de Claude API, GitHub API, Telegram Bot API (aiogram), LikeC4 CLI e Sentry |
<!-- /AUTO:relations -->

## Integracoes externas (ACL)

| Sistema | Protocolo | Direcao | Responsavel |
|---------|-----------|---------|-------------|
| **Claude API** | `claude -p` subprocess | Madruga -> Claude | Integration.ClaudeAPIClient |
| **GitHub** | `gh` CLI / REST API | Madruga -> GitHub | Integration.GitHubClient |
| **Telegram** | HTTPS (Telegram Bot API, aiogram) | Madruga -> Telegram | Integration.TelegramAdapter |
| **LikeC4 CLI** | Subprocess (`likec4`) | Madruga -> LikeC4 | Integration.LikeC4CLI |
| **Copier CLI** | Subprocess (`copier`) | Madruga -> Copier | Specification.CopierTemplate |
| **Sentry** | HTTPS (SDK → cloud) | Madruga -> Sentry | Integration.SentrySDK |

## Decisoes Estrategicas

### Por que Documentation e Specification sao Core?

Estes dois dominios capturam a **proposta de valor unica** do Madruga AI: documentar arquitetura de forma viva (Documentation) e transformar especificacoes em codigo via pipeline estruturado (Specification). Sem eles, o sistema nao tem razao de existir.

### Por que ACL entre Execution e Integration?

Sistemas externos mudam seus contratos sem aviso. A Anti-Corruption Layer garante que mudancas no Claude API, GitHub API ou Telegram Bot API **nao propagam** para a logica de orquestracao. Cada bridge traduz formatos externos para modelos internos.

### Por que Observability e fire-and-forget?

O dashboard e metricas **nunca** devem bloquear a execucao do pipeline. Se o dashboard cair, o easter continua operando normalmente. A relacao pub-sub garante desacoplamento total. Sentry opera como fire-and-forget — falha de envio nao afeta o easter.
