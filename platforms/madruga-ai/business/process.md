---
title: "Business Process"
updated: 2026-04-12
sidebar:
  order: 3
---
# Madruga AI — Business Flows

## Visao End-to-End

> [→ Ver arquitetura de containers](../engineering/containers/) | [→ Ver domain model](../engineering/domain-model/)

> O ciclo de vida completo de uma plataforma: documentar (1x), entregar epics (Nx), consultar (continuo), e autonomia via easter. O reconcile fecha o loop retroalimentando a documentacao. Queue promotion permite enfileirar epics para execucao sequencial automatica.

```mermaid
flowchart TB
    subgraph F1["Flow 1: Documentar Plataforma (1x)"]
        direction LR
        F1A["Criar Plataforma\n(/platform-new)"] --> F1B["Visao de Negocio\n(/vision)"]
        F1B --> F1C["Solution Overview\n(/solution-overview)"]
        F1C --> F1D["Processos de Negocio\n(/business-process)"]
        F1D --> F1E["Pesquisa Tecnologica\n(/tech-research)"]
        F1E --> F1F["Decisoes Arquiteturais\n(/adr)"]
        F1F --> F1G["Blueprint + DDD + Containers\n(/blueprint → /context-map)"]
        F1G --> F1H["Decompor em Epics\n(/epic-breakdown)"]
        F1H --> F1I["Roadmap\n(/roadmap)"]
    end

    subgraph F2["Flow 2: Epic Cycle (repete N vezes)"]
        direction LR
        F2A["Contexto do Epic\n(/epic-context)"] --> F2B["Especificar\n(/speckit.specify)"]
        F2B --> F2B2["Clarificar\n(/speckit.clarify)"]
        F2B2 --> F2C["Planejar + Tasks\n(/speckit.plan + .tasks)"]
        F2C --> F2D["Implementar\n(/speckit.implement)"]
        F2D --> F2E["Judge + QA\n(/judge + /qa)"]
        F2E --> F2F["Reconciliar\n(/reconcile)"]
        F2F --> F2G["Roadmap Reassess\n(/roadmap)"]
    end

    subgraph F3["Flow 3: Consultar (continuo)"]
        F3A["Portal: Diagramas + Dashboard + Roadmap + Changes\n(sem skill — consumo passivo)"]
    end

    subgraph F4["Flow 4: Easter (operacional)"]
        direction LR
        F4A["Execucao Autonoma do Epic Cycle\n(mesmas skills do Flow 2, via MADRUGA_MODE)"]
        F4B["Queue Promotion\n(auto-promove epics enfileirados)"]
        F4A --> F4B
    end

    F1I -->|"Para cada epic"| F2A
    F2G -->|"Proximo epic"| F2A
    F2F -.->|"Retroalimenta"| F1B
    F2F -.->|"Retroalimenta"| F1F
    F2F -.->|"Retroalimenta"| F1G

    F1 -.->|"Alimenta"| F3A
    F2 -.->|"Atualiza"| F3A

    F4A -.->|"Substitui PM no"| F2
    F4B -.->|"Promove proximo"| F2A
```

---

## Flow Overview

| # | Flow | Atores | Frequencia | Impacto |
|---|------|--------|-----------|---------|
| 1 | **Documentar Nova Plataforma** | PM-Arquiteto | 1x por plataforma | Fundacao — sem isso nenhum epic pode comecar |
| 2 | **Especificar e Entregar Epic** | PM-Arquiteto, Revisor | N vezes por plataforma | Core loop — onde valor e entregue |
| 3 | **Consultar Arquitetura** | Consumidor do Portal, Revisor | Continua | Alinhamento — time consulta decisions, estado e historico de commits |
| 4 | **Execucao Autonoma via Easter** | Easter, PM-Arquiteto | Continua | Autonomia — easter executa epic cycle, humano aprova gates criticos, queue promove proximo epic automaticamente |

### Skill Map — Flow 1: Documentar Nova Plataforma (L1)

| # | Passo | Ator | Skill / Comando | Artefato | Gate |
|---|-------|------|-----------------|----------|------|
| 1 | Criar Plataforma | PM-Arquiteto | `/platform-new` | platform.yaml | human |
| 2 | Visao de Negocio | PM-Arquiteto | `/vision` | business/vision.md | human |
| 3 | Solution Overview | PM-Arquiteto | `/solution-overview` | business/solution-overview.md | human |
| 4 | Processos de Negocio | PM-Arquiteto | `/business-process` | business/process.md | human |
| 5 | Pesquisa Tecnologica | PM-Arquiteto | `/tech-research` | research/tech-alternatives.md | 1-way-door |
| 6 | Mapeamento de Codebase (opcional) | Madruga AI | `/codebase-map` | research/codebase-context.md | auto |
| 7 | Decisoes Arquiteturais | PM-Arquiteto | `/adr` | decisions/ADR-*.md | 1-way-door |
| 8 | Blueprint | PM-Arquiteto | `/blueprint` | engineering/blueprint.md | human |
| 9 | Modelo de Dominio | PM-Arquiteto | `/domain-model` | engineering/domain-model.md | human |
| 10 | Containers | PM-Arquiteto | `/containers` | engineering/containers.md | human |
| 11 | Context Map | PM-Arquiteto | `/context-map` | engineering/context-map.md | human |
| 12 | Decompor em Epics | PM-Arquiteto | `/epic-breakdown` | epics/*/pitch.md | 1-way-door |
| 13 | Roadmap | PM-Arquiteto | `/roadmap` | planning/roadmap.md | human |

### Skill Map — Flow 2: Especificar e Entregar Epic (L2)

| # | Passo | Ator | Skill / Comando | Artefato | Gate |
|---|-------|------|-----------------|----------|------|
| 1 | Iniciar epic | PM-Arquiteto | `/epic-context` | branch + contexto | human |
| 2 | Especificar | Madruga AI | `/speckit.specify` | spec.md | auto |
| 3 | Clarificar | Madruga AI | `/speckit.clarify` | spec.md (atualizada) | auto |
| 4 | Planejar | Madruga AI | `/speckit.plan` | plan.md | auto |
| 5 | Quebrar em tarefas | Madruga AI | `/speckit.tasks` | tasks.md | auto |
| 6 | Verificacao consistencia | Madruga AI | `/speckit.analyze` | analyze-report.md | auto |
| 7 | Implementar | Madruga AI | `/speckit.implement` | codigo + implement-report.md | auto |
| 8 | Verificacao pos | Madruga AI | `/speckit.analyze` | analyze-post-report.md | auto |
| 9 | Review multi-perspectiva | Madruga AI | `/judge` | judge-report.md | auto |
| 10 | QA | Madruga AI | `/qa` | qa-report.md | auto |
| 11 | Reconciliar | Madruga AI | `/reconcile` | reconcile-report.md | auto |
| 12 | Roadmap Reassess | Madruga AI | `/roadmap` | roadmap-reassess-report.md | auto |

> **Nota:** No modo interativo (MADRUGA_MODE=manual), steps 1-5 pausam para human approval. No modo autonomo (MADRUGA_MODE=auto), todos os gates sao auto exceto 1-way-door (que sempre escala para humano).

### Skill Map — Flow 3: Consultar Arquitetura

> Sem skills de pipeline — consumo passivo via portal. Inclui: diagramas Mermaid inline, dashboard de pipeline, historico de commits por epic (tab Changes), ADRs pesquisaveis, observabilidade (traces, evals, custo).

### Skill Map — Flow 4: Easter (operacional)

> Mesmas skills do Flow 2, executadas autonomamente pelo easter via DAG executor + MADRUGA_MODE. Apos epic ser shipped, queue promotion auto-promove o proximo epic enfileirado. Ver tabela do Flow 2.

---

## Deep Dive — Flow 1: Documentar Nova Plataforma

> O PM-Arquiteto cria e documenta uma plataforma do zero, passando por visao de negocio, pesquisa tecnologica, decisoes arquiteturais e planejamento. Este fluxo acontece **1 vez por plataforma** e produz toda a fundacao necessaria para iniciar entregas.

### Happy Path

```mermaid
sequenceDiagram
    actor PM as PM-Arquiteto
    participant Plataforma as Madruga AI

    rect rgb(230, 245, 255)
    note over PM, Plataforma: Fase 1 — Negocio (~2h)
    PM->>+Plataforma: Criar nova plataforma (nome, descricao)
    Plataforma-->>-PM: Estrutura scaffolded (pastas, manifesto)

    PM->>+Plataforma: Definir visao de negocio
    Plataforma->>PM: Perguntas estruturadas (mercado, personas, metricas)
    PM->>Plataforma: Respostas e validacoes
    Plataforma-->>-PM: Visao documentada (Playing to Win)

    PM->>+Plataforma: Definir solucao e features
    Plataforma->>PM: Perguntas (personas, prioridades, MVP)
    PM->>Plataforma: Respostas
    Plataforma-->>-PM: Solution Overview com feature map priorizado

    PM->>+Plataforma: Mapear processos de negocio
    Plataforma->>PM: Candidatos de fluxos para priorizar
    PM->>Plataforma: Priorizacao (3-5 fluxos)
    Plataforma-->>-PM: Fluxos mapeados com diagramas
    end

    rect rgb(255, 245, 230)
    note over PM, Plataforma: Fase 2 — Pesquisa (~1h)
    PM->>+Plataforma: Pesquisar alternativas tecnologicas
    Plataforma->>PM: Matriz de decisao (min 3 alternativas por decisao)
    note right of PM: 1-way-door — decisao irreversivel
    PM->>Plataforma: Aprovacao por decisao
    Plataforma-->>-PM: Pesquisa registrada com fontes verificaveis
    end

    rect rgb(230, 255, 230)
    note over PM, Plataforma: Fase 3 — Engenharia (~3h)
    PM->>+Plataforma: Registrar decisoes arquiteturais
    note right of PM: 1-way-door — decisao irreversivel
    Plataforma->>PM: ADRs com alternativas e consequencias
    PM->>Plataforma: Aprovacao por ADR
    Plataforma-->>-PM: ADRs registrados

    PM->>+Plataforma: Definir blueprint tecnico
    Plataforma-->>-PM: NFRs, topologia de deploy, glossario

    PM->>+Plataforma: Modelar dominio (DDD)
    Plataforma-->>-PM: Bounded contexts, agregados, invariantes, schemas

    PM->>+Plataforma: Definir containers (C4 Level 2)
    Plataforma-->>-PM: Containers, protocolos, diagramas Mermaid

    PM->>+Plataforma: Mapear relacoes entre contextos
    Plataforma-->>-PM: Context map com padroes DDD
    end

    rect rgb(245, 230, 255)
    note over PM, Plataforma: Fase 4 — Planejamento (~1h)
    PM->>+Plataforma: Decompor em epics (Shape Up)
    note right of PM: 1-way-door — decisao irreversivel
    Plataforma->>PM: Epics candidatos com problema, appetite, scope
    PM->>Plataforma: Validacao e ajustes
    Plataforma-->>-PM: Epics registrados no roadmap

    PM->>+Plataforma: Sequenciar entregas (roadmap)
    Plataforma->>PM: Sequencia por risco/dependencia + MVP
    PM->>Plataforma: Aprovacao
    Plataforma-->>-PM: Roadmap com milestones e timeline
    end

    note over PM, Plataforma: Plataforma pronta — iniciar ciclo de epics (Flow 2)
```

### Excecoes

```mermaid
sequenceDiagram
    actor PM as PM-Arquiteto
    participant Plataforma as Madruga AI

    PM->>+Plataforma: Iniciar qualquer etapa
    alt Dependencia nao existe
        Plataforma-->>PM: ERRO — artefato X nao encontrado. Executar etapa Y primeiro.
    else Plataforma ja tem artefato
        Plataforma->>PM: Artefato existente encontrado. Reescrever ou iterar?
        PM->>Plataforma: Decisao
    else Pesquisa sem fontes verificaveis
        Plataforma-->>PM: Dados marcados [FONTE NAO VERIFICADA] — requer validacao manual
    else Epic com appetite > 6 semanas
        Plataforma-->>PM: Epic muito grande — proposta de split em 2+ epics menores
        PM->>Plataforma: Aprovacao do split
    end
    Plataforma-->>-PM: Fluxo retomado
```

**Premissas para este fluxo:**
- PM-Arquiteto tem contexto de negocio suficiente para responder perguntas estruturadas
- Cada etapa salva seu artefato e registra progresso no banco de estado automaticamente (`post_save.py`)
- Decisoes irreversiveis (1-way-door) sempre exigem aprovacao explicita por item — nunca em batch
- Cada commit e rastreado automaticamente no banco via post-commit hook

---

## Deep Dive — Flow 2: Especificar e Entregar Epic

> O PM-Arquiteto pega um epic do roadmap, especifica, planeja, implementa, testa e reconcilia a documentacao. Este fluxo acontece **N vezes por plataforma** — e onde valor de negocio e efetivamente entregue. Ao final, mudancas na implementacao retroalimentam a documentacao de negocio e engenharia.

### Happy Path

```mermaid
sequenceDiagram
    actor PM as PM-Arquiteto
    participant Plataforma as Madruga AI
    participant Docs as Documentacao<br/>(Business + Engineering)

    rect rgb(230, 245, 255)
    note over PM, Plataforma: Fase 1 — Contexto e Especificacao
    PM->>+Plataforma: Iniciar epic N do roadmap
    Plataforma->>Plataforma: Criar branch dedicado (epic/<platform>/<NNN-slug>)
    Plataforma-->>-PM: Contexto capturado (decisoes, gray areas)

    PM->>+Plataforma: Especificar feature (/speckit.specify)
    Plataforma->>PM: Perguntas (requisitos, edge cases, criterios)
    PM->>Plataforma: Respostas
    Plataforma-->>-PM: Especificacao com requisitos e acceptance criteria

    PM->>+Plataforma: Clarificar ambiguidades (/speckit.clarify)
    Plataforma->>PM: Ate 5 perguntas direcionadas
    PM->>Plataforma: Respostas
    Plataforma-->>-PM: Spec atualizada sem ambiguidades
    end

    rect rgb(255, 245, 230)
    note over PM, Plataforma: Fase 2 — Design e Planejamento
    PM->>+Plataforma: Planejar implementacao (/speckit.plan)
    Plataforma-->>-PM: Design tecnico (componentes, contratos, modelo de dados)

    PM->>+Plataforma: Quebrar em tarefas (/speckit.tasks)
    Plataforma-->>-PM: Lista ordenada por dependencia

    Plataforma->>Plataforma: Verificacao de consistencia (spec vs plan vs tasks)
    end

    rect rgb(230, 255, 230)
    note over PM, Plataforma: Fase 3 — Implementacao
    Plataforma->>Plataforma: Executar todas as tarefas (codigo)
    Plataforma->>Plataforma: Verificacao pos-implementacao (consistencia)

    Plataforma->>Plataforma: Review multi-perspectiva (judge — 4 personas + 1 juiz)
    alt Review limpo
        Plataforma->>PM: Relatorio de review limpo
    else Bloqueios encontrados
        Plataforma->>PM: Bloqueios que requerem decisao
        PM->>Plataforma: Decisao
    end
    end

    rect rgb(255, 230, 230)
    note over PM, Plataforma: Fase 4 — Qualidade e Reconciliacao
    Plataforma->>Plataforma: QA completo (analise estatica + testes + code review)
    opt Problemas encontrados
        Plataforma->>Plataforma: Corrigir automaticamente (heal loop)
    end
    Plataforma->>PM: Relatorio de qualidade

    Plataforma->>Plataforma: Reconciliar documentacao (9 categorias de drift)
    Plataforma->>PM: Propostas de atualizacao (side-by-side diffs)
    PM->>Plataforma: Aprovacao das mudancas
    Plataforma->>Docs: Atualizar Business docs (se impactados)
    Plataforma->>Docs: Atualizar Engineering docs (se impactados)
    Plataforma->>PM: Drift score + docs sincronizados
    end

    rect rgb(245, 230, 255)
    note over PM, Plataforma: Fase 5 — Reassess e Merge
    Plataforma->>Plataforma: Roadmap reassess (repriorizar epics restantes)
    PM->>PM: PR + code review + merge para branch principal
    end

    note over PM, Plataforma: Repetir Flow 2 para proximo epic do roadmap
```

### Excecoes

```mermaid
sequenceDiagram
    actor PM as PM-Arquiteto
    participant Plataforma as Madruga AI
    participant Docs as Documentacao<br/>(Business + Engineering)

    PM->>+Plataforma: Qualquer etapa do epic
    alt Nao esta no branch correto
        Plataforma-->>PM: ERRO — branch guard. Deve estar em epic/<platform>/<NNN>
    else Spec tem marcadores [NEEDS CLARIFICATION]
        Plataforma-->>PM: Recomendacao: executar clarificacao antes de prosseguir
    else QA encontra falhas criticas
        Plataforma->>Plataforma: Heal loop — corrigir automaticamente
        Plataforma->>PM: Relatorio do que foi corrigido
        note right of PM: Reconcile roda DEPOIS do QA<br/>porque heal loop pode criar novo drift
    else Drift score >= 0.3 no reconcile
        Plataforma->>PM: Drift alto — requer revisao manual detalhada
        PM->>Plataforma: Aprovacao item por item
        Plataforma->>Docs: Aplicar correcoes aprovadas
    else Epic com tasks nao concluidas
        Plataforma-->>PM: Verificacao falha — tasks marcadas done sem codigo correspondente
        PM->>Plataforma: Decisao (implementar ou remover do scope)
    end
    Plataforma-->>-PM: Fluxo retomado
```

**Premissas para este fluxo:**
- Todo epic roda em branch dedicado — nunca diretamente no branch principal
- O reconcile e o passo que fecha o loop: implementacao retroalimenta Business e Engineering docs
- QA e obrigatorio — camadas de teste se adaptam ao que esta disponivel (analise estatica sempre, testes automatizados quando existem, browser QA quando aplicavel)
- Apos merge, o estado do epic e registrado automaticamente no banco
- Commits sao rastreados via post-commit hook com atribuicao automatica a platform e epic

---

## Deep Dive — Flow 3: Consultar Arquitetura

> Qualquer membro do time acessa o portal para consultar a arquitetura de uma plataforma: diagramas, decisoes, estado do pipeline, historico de commits e roadmap. Este fluxo e **continuo** — o portal reflete o estado atual dos artefatos versionados.

### Happy Path

```mermaid
sequenceDiagram
    actor Cons as Consumidor do Portal
    participant Portal as Portal (Documentacao Visual)
    participant Artefatos as Artefatos Versionados

    Cons->>+Portal: Acessar portal
    Portal->>Artefatos: Auto-descoberta de plataformas
    Portal-->>Cons: Lista de plataformas com lifecycle stage

    Cons->>Portal: Selecionar plataforma
    Portal-->>Cons: Sidebar com secoes (Business, Engineering, Decisions, Epics)

    alt Consultar arquitetura
        Cons->>Portal: Abrir diagrama de containers
        Portal->>Artefatos: Carregar modelo Mermaid (inline em .md)
        Portal-->>Cons: Diagrama interativo (zoom, pan, click-through)
    else Consultar decisoes
        Cons->>Portal: Abrir lista de ADRs
        Portal-->>Cons: ADRs com contexto, alternativas e consequencias
    else Consultar estado do pipeline
        Cons->>Portal: Abrir dashboard (tab Execution)
        Portal->>Artefatos: Carregar estado do banco
        Portal-->>Cons: DAG visual (L1 + L2), progresso por epic, filtros
    else Consultar historico de mudancas
        Cons->>Portal: Abrir tab Changes
        Portal-->>Cons: Commits por epic, stats ad-hoc vs epic-bound, filtros
    else Consultar observabilidade
        Cons->>Portal: Abrir tab Observability
        Portal-->>Cons: Traces, evals (4 dimensoes), custo por run, export CSV
    else Consultar roadmap
        Cons->>Portal: Abrir roadmap
        Portal-->>Cons: Epics shipped, candidatos, timeline, riscos
    end

    Cons-->>-Portal: Informacao obtida — alinhamento sem reuniao
```

### Excecoes

```mermaid
sequenceDiagram
    actor Cons as Consumidor do Portal
    participant Portal as Portal (Documentacao Visual)

    Cons->>+Portal: Acessar plataforma
    alt Plataforma sem diagramas
        Portal-->>Cons: Secao de diagramas vazia — "Modelo ainda nao criado"
    else Artefato desatualizado (drift detectado)
        Portal-->>Cons: Banner "Ultima atualizacao: X dias atras"
    else Portal nao compila
        Portal-->>Cons: Erro de build — verificar logs
    end
    Portal-->>-Cons: Orientacao sobre proximo passo
```

**Premissas para este fluxo:**
- O portal auto-descobre plataformas escaneando manifesto de cada uma
- Diagramas Mermaid inline nos `.md` sao renderizados pelo portal (astro-mermaid v2.0.1)
- O dashboard reflete o estado do banco (atualizado a cada save de skill)
- Tab Changes mostra historico de commits por epic com atribuicao automatica
- Documentacao versionada e sempre a fonte da verdade — o portal e view layer

---

## Deep Dive — Flow 4: Execucao Autonoma via Easter

> O easter (FastAPI + asyncio) executa o ciclo de epics autonomamente via DAG executor. O PM-Arquiteto aprova human gates via Telegram ou CLI. Tres modos de operacao (MADRUGA_MODE): manual (pausa em gates), interactive (prompt y/n), auto (execucao end-to-end). Apos epic concluido, queue promotion auto-promove o proximo epic enfileirado.

### Happy Path

```mermaid
sequenceDiagram
    actor PM as PM-Arquiteto
    participant Easter as Easter (Agente Autonomo)
    participant Plataforma as Madruga AI
    participant Docs as Documentacao<br/>(Business + Engineering)
    participant DB as madruga.db

    PM->>Easter: Enfileirar epics (platform_cli.py queue)
    Easter->>DB: Epics marcados como 'queued' (FIFO)

    rect rgb(230, 245, 255)
    note over Easter, Plataforma: Execucao Autonoma (Epic N)
    Easter->>Plataforma: Criar branch + capturar contexto
    Easter->>Plataforma: Especificar + Clarificar
    Easter->>Plataforma: Planejar + quebrar em tarefas
    Easter->>Plataforma: Verificar consistencia (analyze)
    Easter->>Plataforma: Implementar (tarefas via claude -p)
    Easter->>Plataforma: Verificar + Judge (4 personas + juiz)
    Easter->>Plataforma: QA + heal loop
    Easter->>Plataforma: Reconciliar + roadmap reassess
    Easter->>Docs: Atualizar Business + Engineering docs
    end

    alt Decisao reversivel (2-way door)
        Easter->>Easter: Tomar decisao autonomamente
    else Decisao irreversivel (1-way door)
        Easter->>PM: Escalar via Telegram (inline keyboard)
        note right of PM: Ex: mudanca de schema, API publica, ADR novo
        PM->>Easter: Aprovacao (ou rejeicao com direcao)
    end

    rect rgb(230, 255, 230)
    note over Easter, DB: Queue Promotion (auto)
    Easter->>DB: Epic N → status 'shipped'
    Easter->>DB: Consultar proximo epic queued (FIFO)
    alt Existe epic na fila
        Easter->>Plataforma: Checkout branch cascade (a partir do tip do epic anterior)
        Easter->>DB: Epic N+1 → status 'in_progress'
        note over Easter, Plataforma: Ciclo reinicia automaticamente
    else Fila vazia
        Easter->>Easter: Aguardar proximo poll (idle)
    end
    end
```

### Excecoes

```mermaid
sequenceDiagram
    actor PM as PM-Arquiteto
    participant Easter as Easter (Agente Autonomo)

    Easter->>Easter: Executando epic
    alt Context rot (qualidade degrada)
        Easter->>Easter: Iniciar nova wave com contexto limpo
    else Drift score alto apos reconcile
        Easter->>PM: Escalar — drift >= 0.3 requer revisao humana
        PM->>Easter: Direcao para correcao
    else Falha de API (rate limit, timeout)
        Easter->>Easter: Retry com backoff exponencial (5, 10, 20s)
        alt Falha persistente (3 consecutivas)
            Easter->>Easter: Epic → status 'blocked'
            Easter->>PM: Notificar via Telegram/ntfy
        end
    else Dirty tree na promocao
        Easter->>Easter: Epic queued → status 'blocked'
        Easter->>PM: Notificar — commit ou stash antes de retomar
    else Bloqueio em verificacao
        Easter->>PM: Tasks marcadas done mas sem codigo — requer decisao
    end
```

**Premissas para este fluxo:**
- Easter usa as **mesmas skills** que o PM-Arquiteto usa interativamente — zero duplicacao
- Decisoes 1-way door **sempre** escalam para humano, mesmo em modo autonomo (MADRUGA_MODE=auto nao bypassa 1-way-door)
- Queue promotion e always-on — quando um epic e shipped e a fila tem epics queued, o proximo e auto-promovido
- Epics executam sequencialmente — 1 por plataforma. Promocao respeita FIFO (ordered by updated_at)
- Cascade branch: novo epic parte do tip do epic anterior (nao de main), garantindo historico incremental

---

## Deep Dive — Ciclo de Vida de Epics e Cascade Workflow

> Esta secao detalha como epics sao criados, enfileirados, promovidos e executados. O modelo de cascata garante que cada epic parte do ponto onde o anterior parou, sem conflitos de branch.

### Status Transitions

```mermaid
stateDiagram-v2
    [*] --> proposed: epic-breakdown cria pitch.md
    proposed --> drafted: /epic-context --draft (artefatos em main)
    drafted --> queued: platform_cli.py queue (FIFO)
    drafted --> in_progress: /epic-context (cria branch)
    queued --> drafted: platform_cli.py dequeue
    queued --> in_progress: Easter auto-promote (FIFO)
    in_progress --> shipped: Todos os 12 nodes L2 concluidos
    in_progress --> blocked: 3 falhas consecutivas ou dirty tree
    blocked --> in_progress: Intervencao manual + retry
    shipped --> [*]
```

### Modos de Criacao de Epic

| Modo | Comando | O que Acontece | Status Resultante | Quando Usar |
|------|---------|----------------|-------------------|-------------|
| **Normal** | `/epic-context <platform> <epic>` | Cria branch `epic/<platform>/<NNN-slug>`, captura contexto, inicia L2 | `in_progress` | Epic pronto para executar agora |
| **Draft** | `/epic-context --draft <platform> <epic>` | Cria artefatos (pitch.md, research) em main, SEM criar branch | `drafted` | Planejar antecipadamente enquanto outro epic executa |
| **Queue** | `platform_cli.py queue <platform> <epic>` | Marca epic drafted como queued para auto-promocao | `queued` | Enfileirar para execucao sequencial via easter |

### Logica de Cascade Branch

Quando um novo epic e promovido (manual ou auto), o branch e criado a partir do **tip do epic anterior**, nao de `origin/main`. Isso garante historico incremental:

```mermaid
gitgraph
    commit id: "main (L1 completo)"
    branch epic/platform/001-first
    commit id: "001: specify + plan"
    commit id: "001: implement"
    commit id: "001: reconcile"
    branch epic/platform/002-second
    commit id: "002: cascade from 001 tip"
    commit id: "002: implement"
    commit id: "002: reconcile"
    branch epic/platform/003-third
    commit id: "003: cascade from 002 tip"
```

**Algoritmo de cascade** (`_get_cascade_base` em queue_promotion.py):
1. Lista branches locais com prefixo `epic/<platform>/` ordenados por data (mais recente primeiro)
2. Para cada candidato, verifica se tem commits a frente de `origin/base_branch`
3. Se encontra branch com commits ahead → usa como base
4. Se nenhum encontrado → usa `origin/base_branch` (primeiro epic da plataforma)

### Queue Promotion (Auto)

Quando um epic e shipped, o easter hook automaticamente:

1. **Consulta fila:** `get_next_queued_epic(platform_id)` — busca o mais antigo por `updated_at ASC`
2. **Dirty-tree guard:** Verifica se o clone tem mudancas nao commitadas. Se sim → epic vira `blocked` + notificacao ntfy
3. **Branch creation:** Checkout branch com cascade base (tip do epic anterior)
4. **Artifact migration:** Traz artefatos de draft (pitch.md, etc) do base_branch via `git checkout <base> -- <epic_dir>`
5. **Commit:** `feat: promote queued epic {NNN} (cascade from {base_branch})`
6. **DB update:** `status = 'in_progress'`, `branch_name` preenchido
7. **Retry:** 3 tentativas com backoff (1s, 2s, 4s). Falha permanente → `blocked`

### Quick-Fix (Fast Lane)

Para bug fixes e mudancas pequenas, o **quick cycle** pula plan/tasks/analyze/qa/reconcile:

| # | Passo | Skill | Gate |
|---|-------|-------|------|
| 1 | Especificar | `/speckit.specify` | human |
| 2 | Implementar | `/speckit.implement` | auto |
| 3 | Judge | `/judge` | auto-escalate |

Invocado via `dag_executor.py --platform <name> --epic <slug> --quick`.

---

## Deep Dive — Ferramentas e Scripts

> Referencia completa de todas as ferramentas disponíveis para operar o pipeline.

### CLI Principal — platform_cli.py

```bash
# Gestao de plataformas
python3 .specify/scripts/platform_cli.py new <name>              # scaffold via copier
python3 .specify/scripts/platform_cli.py lint <name>             # validar estrutura
python3 .specify/scripts/platform_cli.py lint --all              # validar todas
python3 .specify/scripts/platform_cli.py list                    # listar plataformas
python3 .specify/scripts/platform_cli.py sync [name]             # copier update

# Estado do pipeline
python3 .specify/scripts/platform_cli.py status <name>           # pipeline status (tabela)
python3 .specify/scripts/platform_cli.py status --all --json     # JSON para portal
python3 .specify/scripts/platform_cli.py use <name>              # definir plataforma ativa
python3 .specify/scripts/platform_cli.py current                 # mostrar plataforma ativa

# Dados
python3 .specify/scripts/platform_cli.py register <name>         # registrar no DB
python3 .specify/scripts/platform_cli.py import-adrs <name>      # importar ADRs → DB
python3 .specify/scripts/platform_cli.py export-adrs <name>      # exportar DB → ADR markdown
python3 .specify/scripts/platform_cli.py import-memory           # importar .claude/memory → DB
python3 .specify/scripts/platform_cli.py export-memory           # exportar DB → memory markdown

# Queue de epics
python3 .specify/scripts/platform_cli.py queue <name> <epic>     # drafted → queued
python3 .specify/scripts/platform_cli.py dequeue <name> <epic>   # queued → drafted
python3 .specify/scripts/platform_cli.py queue-list <name>       # listar fila FIFO
```

### DAG Executor

```bash
# Executar pipeline
python3 .specify/scripts/dag_executor.py --platform <name> --dry-run     # print execution order
python3 .specify/scripts/dag_executor.py --platform <name>                # executar L1
python3 .specify/scripts/dag_executor.py --platform <name> --epic <slug>  # executar L2 epic
python3 .specify/scripts/dag_executor.py --platform <name> --resume       # resume checkpoint

# Gates
python3 .specify/scripts/platform_cli.py gate list <name>                # listar gates pendentes
python3 .specify/scripts/platform_cli.py gate approve <run-id>           # aprovar gate
```

### Easter (Daemon 24/7)

```bash
# Controle do servico
systemctl --user start madruga-easter       # iniciar
systemctl --user stop madruga-easter        # parar
systemctl --user restart madruga-easter     # reiniciar
journalctl --user -u madruga-easter -f      # logs em tempo real

# Endpoints REST
GET /health              # liveness probe (200 OK)
GET /status              # estado completo (telegram, epics ativos)
GET /api/traces          # lista traces com paginacao
GET /api/traces/{id}     # trace detail com spans + evals
GET /api/evals           # eval scores com filtros
GET /api/stats           # stats agregados por dia
GET /api/export/csv      # export traces/spans/evals
```

### Post-Save (Registro de Estado)

```bash
# Registrar artefato (chamado automaticamente por cada skill no Step 5)
python3 .specify/scripts/post_save.py --platform <name> --node <id> \
    --skill <skill> --artifact <path>

# Para epics
python3 .specify/scripts/post_save.py --platform <name> --epic <epic-id> \
    --node <id> --skill <skill> --artifact <path>

# Re-seed do banco
python3 .specify/scripts/post_save.py --reseed --platform <name>   # re-seed plataforma
python3 .specify/scripts/post_save.py --reseed-all                 # re-seed todas
```

### Make Targets

```bash
make test            # pytest (.specify/scripts/tests/)
make coverage        # pytest com coverage report (htmlcov/)
make lint            # validar todas plataformas
make ruff            # ruff check Python
make ruff-fix        # auto-fix ruff
make status          # pipeline status todas plataformas
make status-json     # export JSON para portal
make seed            # re-seed DB (idempotente)
make seed-force      # drop DB + re-seed do zero
make portal-dev      # portal dev server (localhost:4321)
make portal-build    # portal production build
make portal-install  # instalar deps portal
make install-hooks   # instalar git post-commit hook
make install-services # symlink systemd user services
make up              # iniciar servicos (easter)
make down            # parar servicos
make restart         # reiniciar servicos
make logs            # tail logs (easter + portal)
```

### Variaveis de Ambiente

| Variavel | Default | Proposito |
|----------|---------|-----------|
| `MADRUGA_MODE` | `manual` | Gate mode: manual (pausa), interactive (prompt y/n), auto (end-to-end) |
| `MADRUGA_EXECUTOR_TIMEOUT` | `3000` (s) | Timeout por skill dispatch |
| `MADRUGA_MAX_CONCURRENT` | `3` | Max dispatches simultaneos |
| `MADRUGA_BARE_LITE` | `1` (on) | Dispatch com flags bare-lite (--strict-mcp-config, --tools, etc). `0` → legacy |
| `MADRUGA_SCOPED_CONTEXT` | `1` (on) | Incluir docs scoped por task (data-model, contracts). `0` → inclui tudo |
| `MADRUGA_CACHE_ORDERED` | `1` (on) | Reordenar prompt para cache-optimal prefix. `0` → legacy order |
| `MADRUGA_KILL_IMPLEMENT_CONTEXT` | `1` (on) | Desabilitar implement-context.md append/read. `0` → legacy |
| `MADRUGA_STRICT_SETTINGS` | `0` (off) | Adicionar `--setting-sources project`. Requer audit de settings.local.json |
| `MADRUGA_DISPATCH` | `0` | Flag setado internamente por dag_executor em sessoes dispatch. Previne storms de hooks |
| `ANTHROPIC_API_KEY` | (keychain) | Claude API auth (opcional — keychain preferido) |
| `MADRUGA_TELEGRAM_BOT_TOKEN` | — | Telegram bot auth |
| `MADRUGA_SENTRY_DSN` | — | Sentry error tracking (opcional) |
| `MADRUGA_NTFY_TOPIC` | — | ntfy.sh push alerts (fallback de Telegram) |

### Diagrama de Relacionamento entre Ferramentas

```mermaid
graph TD
    subgraph human["Interface Humana"]
        CLI["platform_cli.py"]
        Skills["Skills (/madruga:* /speckit.*)"]
        Portal["Portal (browser)"]
    end

    subgraph daemon["Daemon"]
        Easter["easter.py (FastAPI)"]
        DAG["dag_executor.py"]
    end

    subgraph data["Dados"]
        DB[("madruga.db")]
        FS["Artefatos (.md)"]
        Git["Git (branches/commits)"]
    end

    subgraph external["Externos"]
        Claude["claude -p"]
        TG["Telegram API"]
    end

    CLI -->|"SQL"| DB
    CLI -->|"queue/dequeue"| DB
    Skills -->|"post_save.py"| DB
    Skills -->|"grava"| FS
    Portal -->|"read JSON"| DB

    Easter -->|"dispatch"| DAG
    Easter -->|"poll gates"| DB
    Easter -->|"promote queue"| DB
    Easter -->|"HTTPS"| TG

    DAG -->|"subprocess"| Claude
    DAG -->|"git ops"| Git
    DAG -->|"runs/traces"| DB

    Claude -->|"gera"| FS
```

---

## Deep Dive — Commit Traceability

> Cada commit no repositorio e automaticamente rastreado e atribuido a uma plataforma e epic.

### Post-Commit Hook

O git post-commit hook (`hook_post_commit.py`) e instalado via `make install-hooks` e executa automaticamente a cada commit:

1. **Parse commit:** sha, message, author, date, lista de arquivos modificados
2. **Platform detection** (prioridade):
   - Branch `epic/<platform>/<NNN>` → extrai platform do nome
   - File paths (`platforms/<name>/`) → detecta plataforma(s) impactada(s)
   - Default → `madruga-ai` (commits na infra do pipeline)
3. **Epic linking** (prioridade):
   - Branch pattern `epic/<platform>/<NNN-slug>` → extrai NNN-slug
   - Tag `[epic:NNN]` no commit message → usa NNN
   - Nenhum → `NULL` (commit ad-hoc, visivel no portal como "ad-hoc")
4. **Persist:** INSERT na tabela `commits` (sha, message, author, platform_id, epic_id, source=hook, files_json)

**Backfill:** Commits historicos foram retroativamente importados via `backfill_commits.py`. Reseed tambem sincroniza commits via `git log`.

---

## Premissas Globais

| # | Premissa | Status |
|---|----------|--------|
| 1 | PM-Arquiteto e o unico operador humano no ciclo hoje | Confirmado |
| 2 | Todo artefato salvo registra estado automaticamente no banco de estado | Confirmado |
| 3 | Decisoes irreversiveis sempre requerem aprovacao explicita por item | Confirmado |
| 4 | O reconcile fecha o loop — implementacao retroalimenta Business e Engineering | Confirmado |
| 5 | Easter opera com as mesmas skills do modo interativo | Confirmado |
| 6 | Portal reflete estado atual — le diretamente dos artefatos versionados | Confirmado |
| 7 | O epic cycle (Flow 2) e o fluxo mais executado — roda N vezes por plataforma | Confirmado |
| 8 | Epics executam sequencialmente — 1 por plataforma por vez | Confirmado |
| 9 | Commits rastreados automaticamente via post-commit hook | Confirmado |
| 10 | Queue promotion e always-on — auto-promove proximo epic queued quando slot libera | Confirmado |
| 11 | Diagramas Mermaid inline em .md sao a source of truth visual (ADR-020) | Confirmado |

---

## Glossario de Atores

| Ator | Quem e | Aparece nos fluxos |
|------|--------|--------------------|
| **PM-Arquiteto** | Engenheiro que documenta arquitetura, especifica features e opera o pipeline. Hoje: Gabriel Hamu. | 1, 2, 4 |
| **Revisor** | Engenheiro senior que revisa PRs e aprova decisoes irreversiveis. | 2 |
| **Consumidor do Portal** | Qualquer membro do time que consulta documentacao e estado. | 3 |
| **Easter** | Processo persistente (FastAPI + asyncio) que executa o epic cycle autonomamente. Modos: manual, interactive, auto (MADRUGA_MODE). Promove epics da fila automaticamente. | 4 |
| **Madruga AI** | A plataforma como um todo — interface CLI + skills + banco de estado. | 1, 2 |
| **Portal** | Interface visual que renderiza documentacao, dashboards, commits e observabilidade. | 3 |
| **Documentacao** | Artefatos versionados de Business e Engineering, atualizados pelo reconcile. | 2, 4 |
| **Pair-Program** | Companion que observa easter runs em tempo real. Classifica ticks como healthy/opportunity/critical. Intervem cirurgicamente so em issues criticos. | 4 |
