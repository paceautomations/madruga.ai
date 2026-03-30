---
title: "Business Process"
updated: 2026-03-30
---
# Madruga AI — Business Flows

> Mapeamento dos fluxos de negocio ponta a ponta. Comeca pela visao end-to-end e depois detalha cada etapa. Ultima atualizacao: 2026-03-30.

---

## Visao End-to-End

> O ciclo de vida completo de uma plataforma: documentar (1x), entregar epics (Nx), consultar (continuo), e no futuro, autonomia via daemon. O reconcile fecha o loop retroalimentando a documentacao.

```mermaid
flowchart TB
    subgraph F1["Flow 1: Documentar Plataforma (1x)"]
        direction LR
        F1A[Criar Plataforma] --> F1B[Visao de Negocio]
        F1B --> F1C[Solution Overview]
        F1C --> F1D[Processos de Negocio]
        F1D --> F1E[Pesquisa Tecnologica]
        F1E --> F1F[Decisoes Arquiteturais]
        F1F --> F1G[Blueprint + DDD + Containers]
        F1G --> F1H[Decompor em Epics]
        F1H --> F1I[Roadmap]
    end

    subgraph F2["Flow 2: Epic Cycle (repete N vezes)"]
        direction LR
        F2A[Contexto do Epic] --> F2B[Especificar]
        F2B --> F2C[Planejar + Tasks]
        F2C --> F2D[Implementar]
        F2D --> F2E[Verificar + QA]
        F2E --> F2F[Reconciliar]
        F2F --> F2G[PR + Merge]
    end

    subgraph F3["Flow 3: Consultar (continuo)"]
        F3A[Portal: Diagramas + Dashboard + Roadmap]
    end

    subgraph F4["Flow 4: Daemon (futuro)"]
        F4A[Execucao Autonoma do Epic Cycle]
    end

    F1I -->|"Para cada epic"| F2A
    F2G -->|"Proximo epic"| F2A
    F2F -.->|"Retroalimenta"| F1B
    F2F -.->|"Retroalimenta"| F1F
    F2F -.->|"Retroalimenta"| F1G

    F1 -.->|"Alimenta"| F3A
    F2 -.->|"Atualiza"| F3A

    F4A -.->|"Substitui PM no"| F2
```

---

## Flow Overview

| # | Flow | Atores | Frequencia | Impacto |
|---|------|--------|-----------|---------|
| 1 | **Documentar Nova Plataforma** | PM-Arquiteto | 1x por plataforma | Fundacao — sem isso nenhum epic pode comecar |
| 2 | **Especificar e Entregar Epic** | PM-Arquiteto, Revisor | N vezes por plataforma | Core loop — onde valor e entregue |
| 3 | **Consultar Arquitetura** | Consumidor do Portal, Revisor | Continua | Alinhamento — time consulta decisions e estado |
| 4 | **Revisao e Aprovacao de Entrega** | Revisor, PM-Arquiteto | 1x por epic | Qualidade — gate antes de merge `[FUTURO]` |

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
    note right of PM: ⚠ Decisao irreversivel
    PM->>Plataforma: Aprovacao por decisao
    Plataforma-->>-PM: Pesquisa registrada com fontes verificaveis
    end

    rect rgb(230, 255, 230)
    note over PM, Plataforma: Fase 3 — Engenharia (~3h)
    PM->>+Plataforma: Registrar decisoes arquiteturais
    note right of PM: ⚠ Decisao irreversivel
    Plataforma->>PM: ADRs com alternativas e consequencias
    PM->>Plataforma: Aprovacao por ADR
    Plataforma-->>-PM: ADRs registrados

    PM->>+Plataforma: Definir blueprint tecnico
    Plataforma-->>-PM: NFRs, topologia de deploy, glossario

    PM->>+Plataforma: Modelar dominio (DDD)
    Plataforma-->>-PM: Bounded contexts, agregados, invariantes, schemas

    PM->>+Plataforma: Definir containers (C4 Level 2)
    Plataforma-->>-PM: Containers, protocolos, diagramas LikeC4

    PM->>+Plataforma: Mapear relacoes entre contextos
    Plataforma-->>-PM: Context map com padroes DDD
    end

    rect rgb(245, 230, 255)
    note over PM, Plataforma: Fase 4 — Planejamento (~1h)
    PM->>+Plataforma: Decompor em epics (Shape Up)
    note right of PM: ⚠ Decisao irreversivel
    Plataforma->>PM: Epics candidatos com problema, appetite, scope
    PM->>Plataforma: Validacao e ajustes
    Plataforma-->>-PM: Epics registrados no roadmap

    PM->>+Plataforma: Sequenciar entregas (roadmap)
    Plataforma->>PM: Sequencia por risco/dependencia + MVP
    PM->>Plataforma: Aprovacao
    Plataforma-->>-PM: Roadmap com milestones e timeline
    end

    note over PM, Plataforma: ✓ Plataforma pronta — iniciar ciclo de epics (Flow 2)
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
- Cada etapa salva seu artefato e registra progresso no banco de estado automaticamente
- Decisoes irreversiveis (⚠) sempre exigem aprovacao explicita por item — nunca em batch

---

## Deep Dive — Flow 2: Especificar e Entregar Epic

> O PM-Arquiteto pega um epic do roadmap, especifica, planeja, implementa, testa e reconcilia a documentacao. Este fluxo acontece **N vezes por plataforma** — e onde valor de negocio e efetivamente entregue. Ao final, mudancas na implementacao retroalimentam a documentacao de negocio e engenharia.

### Happy Path

```mermaid
sequenceDiagram
    actor PM as PM-Arquiteto
    actor Rev as Revisor
    participant Plataforma as Madruga AI
    participant Docs as Documentacao<br/>(Business + Engineering)

    rect rgb(230, 245, 255)
    note over PM, Plataforma: Fase 1 — Contexto e Especificacao
    PM->>+Plataforma: Iniciar epic N do roadmap
    Plataforma->>Plataforma: Criar branch dedicado para o epic
    Plataforma-->>-PM: Contexto capturado (decisoes, gray areas)

    PM->>+Plataforma: Especificar feature
    Plataforma->>PM: Perguntas (requisitos, edge cases, criterios)
    PM->>Plataforma: Respostas
    Plataforma-->>-PM: Especificacao com requisitos e acceptance criteria

    opt Existem ambiguidades na spec
        PM->>+Plataforma: Clarificar ambiguidades
        Plataforma->>PM: Ate 5 perguntas direcionadas
        PM->>Plataforma: Respostas
        Plataforma-->>-PM: Spec atualizada sem ambiguidades
    end
    end

    rect rgb(255, 245, 230)
    note over PM, Plataforma: Fase 2 — Design e Planejamento
    PM->>+Plataforma: Planejar implementacao
    Plataforma-->>-PM: Design tecnico (componentes, contratos, modelo de dados)

    PM->>+Plataforma: Quebrar em tarefas
    Plataforma-->>-PM: Lista ordenada por dependencia

    Plataforma->>Plataforma: Verificacao de consistencia (spec vs plan vs tasks)
    end

    rect rgb(230, 255, 230)
    note over PM, Plataforma: Fase 3 — Implementacao
    Plataforma->>Plataforma: Executar todas as tarefas (codigo)
    Plataforma->>Plataforma: Verificacao pos-implementacao (consistencia)

    Plataforma->>Plataforma: Verificar aderencia (spec vs codigo)
    alt Aderencia OK
        Plataforma->>PM: Relatorio de verificacao limpo
    else Bloqueios encontrados
        Plataforma->>PM: Bloqueios que requerem decisao
        PM->>Plataforma: Decisao
    end
    end

    rect rgb(255, 230, 230)
    note over PM, Rev: Fase 4 — Qualidade e Reconciliacao
    PM->>+Plataforma: Executar QA completo
    Plataforma->>Plataforma: Analise estatica + testes + code review
    opt Problemas encontrados
        Plataforma->>Plataforma: Corrigir automaticamente (heal loop)
    end
    Plataforma-->>-PM: Relatorio de qualidade

    PM->>+Plataforma: Reconciliar documentacao
    Plataforma->>Plataforma: Comparar implementacao vs documentacao (9 categorias)
    Plataforma->>PM: Propostas de atualizacao (side-by-side diffs)
    PM->>Plataforma: Aprovacao das mudancas
    Plataforma->>Docs: Atualizar Business docs (se impactados)
    Plataforma->>Docs: Atualizar Engineering docs (se impactados)
    Plataforma-->>-PM: Drift score + docs sincronizados
    end

    rect rgb(245, 230, 255)
    note over PM, Rev: Fase 5 — Merge
    PM->>Rev: Solicitar revisao (PR)
    Rev->>Rev: Revisar codigo + docs + rastreabilidade
    Rev->>PM: Aprovacao (ou pedidos de ajuste)
    PM->>Plataforma: Merge para branch principal
    end

    note over PM, Plataforma: ↩ Repetir Flow 2 para proximo epic do roadmap
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

---

## Deep Dive — Flow 3: Consultar Arquitetura

> Qualquer membro do time acessa o portal para consultar a arquitetura de uma plataforma: diagramas, decisoes, estado do pipeline, e roadmap. Este fluxo e **continuo** — o portal reflete o estado atual dos artefatos versionados.

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
        Portal->>Artefatos: Carregar modelo LikeC4
        Portal-->>Cons: Diagrama interativo (zoom, pan, click-through)
    else Consultar decisoes
        Cons->>Portal: Abrir lista de ADRs
        Portal-->>Cons: ADRs com contexto, alternativas e consequencias
    else Consultar estado do pipeline
        Cons->>Portal: Abrir dashboard
        Portal->>Artefatos: Carregar estado do banco
        Portal-->>Cons: DAG visual (L1 + L2), progresso por epic, filtros
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
    alt Plataforma sem modelo LikeC4
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
- Diagramas LikeC4 sao interativos (nao imagens estaticas)
- O dashboard reflete o estado do banco (atualizado a cada save de skill)
- Documentacao versionada e sempre a fonte da verdade — o portal e view layer

---

## Deep Dive — Flow 4: Revisao e Aprovacao de Entrega (Visao Futura com Daemon)

> Hoje o PM-Arquiteto executa todo o ciclo interativamente. Na visao futura, um agente autonomo (Daemon) executa o ciclo de epics, e o Revisor valida entregas em pontos criticos. Este fluxo mostra **como sera** quando o daemon estiver operacional.

### Happy Path (Visao Futura)

```mermaid
sequenceDiagram
    actor PM as PM-Arquiteto
    actor Rev as Revisor
    participant Daemon as Daemon (Agente Autonomo)
    participant Plataforma as Madruga AI
    participant Docs as Documentacao<br/>(Business + Engineering)

    PM->>Daemon: Aprovar epic N para execucao autonoma

    rect rgb(230, 245, 255)
    note over Daemon, Plataforma: Execucao Autonoma
    Daemon->>Plataforma: Criar branch + capturar contexto
    Daemon->>Plataforma: Especificar (usando mesmas skills)
    Daemon->>Plataforma: Planejar + quebrar em tarefas
    Daemon->>Plataforma: Implementar (tarefas em waves com contexto limpo)
    Daemon->>Plataforma: Verificar + QA + Reconciliar
    Daemon->>Docs: Atualizar Business + Engineering docs
    end

    alt Decisao reversivel (2-way door)
        Daemon->>Daemon: Tomar decisao autonomamente
    else Decisao irreversivel (1-way door)
        Daemon->>PM: Escalar para aprovacao humana
        note right of PM: Ex: mudanca de schema, API publica, ADR novo
        PM->>Daemon: Aprovacao (ou rejeicao com direcao)
    end

    Daemon->>Rev: PR pronto para revisao
    Rev->>Rev: Validar codigo, docs, rastreabilidade spec→codigo
    alt Aprovado
        Rev->>Plataforma: Merge
        note over Daemon, Plataforma: ↩ Daemon inicia proximo epic automaticamente
    else Ajustes necessarios
        Rev->>Daemon: Feedback com pedidos de ajuste
        Daemon->>Daemon: Aplicar ajustes (novo ciclo heal)
        Daemon->>Rev: PR atualizado
    end
```

### Excecoes (Visao Futura)

```mermaid
sequenceDiagram
    actor PM as PM-Arquiteto
    participant Daemon as Daemon (Agente Autonomo)

    Daemon->>Daemon: Executando epic
    alt Context rot (qualidade degrada)
        Daemon->>Daemon: Iniciar nova wave com contexto limpo
    else Drift score alto apos reconcile
        Daemon->>PM: Escalar — drift >= 0.3 requer revisao humana
        PM->>Daemon: Direcao para correcao
    else Falha de API (rate limit, timeout)
        Daemon->>Daemon: Retry com backoff exponencial
        alt Falha persistente
            Daemon->>PM: Notificar — fallback para modo interativo
        end
    else Bloqueio em verificacao
        Daemon->>PM: Tasks marcadas done mas sem codigo — requer decisao
    end
```

**Premissas para este fluxo:**
- Daemon usa as **mesmas skills** que o PM-Arquiteto usa interativamente — zero duplicacao
- Decisoes 1-way door **sempre** escalam para humano, mesmo em modo autonomo
- Waves com subagents frescos mitigam context rot em execucoes longas
- O daemon nao esta implementado hoje — este fluxo e a visao de produto `[FUTURO]`

---

## Premissas Globais

| # | Premissa | Status |
|---|----------|--------|
| 1 | PM-Arquiteto e o unico operador humano no ciclo hoje | Confirmado |
| 2 | Todo artefato salvo registra estado automaticamente no banco de estado | Confirmado |
| 3 | Decisoes irreversiveis sempre requerem aprovacao explicita por item | Confirmado |
| 4 | O reconcile fecha o loop — implementacao retroalimenta Business e Engineering | Confirmado |
| 5 | Daemon operara com as mesmas skills do modo interativo | `[FUTURO]` |
| 6 | Portal reflete estado atual — le diretamente dos artefatos versionados | Confirmado |
| 7 | O epic cycle (Flow 2) e o fluxo mais executado — roda N vezes por plataforma | Confirmado |

---

## Glossario de Atores

| Ator | Quem e | Aparece nos fluxos |
|------|--------|--------------------|
| **PM-Arquiteto** | Engenheiro que documenta arquitetura, especifica features e opera o pipeline. Hoje: Gabriel Hamu. | 1, 2, 4 |
| **Revisor** | Engenheiro senior que revisa PRs e aprova decisoes irreversiveis. | 2, 4 |
| **Consumidor do Portal** | Qualquer membro do time que consulta documentacao e estado. | 3 |
| **Daemon** | Agente autonomo que executa o epic cycle sem intervencao humana. | 4 `[FUTURO]` |
| **Madruga AI** | A plataforma como um todo — interface CLI + skills + banco de estado. | 1, 2 |
| **Portal** | Interface visual que renderiza documentacao e dashboards. | 3 |
| **Documentacao** | Artefatos versionados de Business e Engineering, atualizados pelo reconcile. | 2, 4 |
