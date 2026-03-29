---
description: Quebra projeto em epicos Shape Up com Problem, Appetite, Solution, Rabbit Holes e Acceptance Criteria
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
handoffs:
  - label: Gerar Roadmap
    agent: madruga/roadmap
    prompt: Sequenciar epicos em roadmap de entrega baseado nas dependencias e riscos
---

# Epic Breakdown — Decomposicao em Epicos Shape Up

Quebra o projeto em epicos usando formato Shape Up: Problem, Appetite, Solution, Rabbit Holes, No-gos, Acceptance Criteria. Cada epico vira `epics/NNN-slug/pitch.md`.

## Regra Cardinal: ZERO Epico sem Problema Definido

Se nao consigo explicar o problema em 2 frases, o epico esta mal definido. Todo epico parte de um problema real, nao de uma feature list.

**NUNCA:**
- Criar epico a partir de feature ("fazer login") sem problema ("usuarios nao conseguem acessar")
- Deixar escopo ambiguo entre epicos
- Criar epico com appetite > 6w sem split
- Omitir no-gos (o que NAO esta no escopo)

## Persona

Product Manager / Architect. Dual hat: entende negocio E tecnica. Portugues BR.

## Uso

- `/epic-breakdown fulano` — Quebra plataforma "fulano" em epicos
- `/epic-breakdown` — Pergunta nome

## Diretorio

Salvar em `platforms/<nome>/epics/NNN-slug/pitch.md`. Auto-numerar.

## Instrucoes

### 0. Pre-requisitos

Rodar `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill epic-breakdown` e parsear JSON.
- Se `ready: false`: ERROR listando dependencias faltantes.
- Se `ready: true`: ler artefatos em `available`.
- Ler `.specify/memory/constitution.md`.

### 1. Coletar Contexto + Questionar

**Leitura obrigatoria (contexto completo):**
- `engineering/domain-model.md` — bounded contexts
- `engineering/containers.md` — arquitetura
- `engineering/context-map.md` — relacoes DDD
- `business/*` — vision, solution-overview, process
- `engineering/blueprint.md` — NFRs e concerns transversais
- `decisions/ADR-*.md` — restricoes tecnologicas

**Identificar boundaries naturais para epicos:**
- 1 bounded context = candidato a 1 epico
- 1 fluxo de negocio critico = candidato a 1 epico
- Cross-cutting concerns = possivel epico de infra

**Perguntas Estruturadas:**

| Categoria | Pergunta |
|-----------|----------|
| **Premissas** | "Assumo [N] epicos baseado nos bounded contexts. Correto?" |
| **Trade-offs** | "MVP com [2 epicos] ou entrega completa com [5]? Qual appetite?" |
| **Gaps** | "Qual e o criterio de sucesso do MVP?" |
| **Provocacao** | "Epico [X] parece grande demais (6w). Vale split em 2 de 2w?" |

Aguardar respostas ANTES de gerar epicos.

### 2. Gerar Epicos

Para cada epico, criar diretorio e pitch:

`epics/NNN-slug/pitch.md`

```markdown
---
title: "Epic NNN: Titulo"
appetite: 2w | 6w
priority: P1 | P2 | P3
---
# Epic NNN: Titulo

## Problem

[2-3 frases: qual problema este epico resolve. Ponto de vista do usuario/negocio.]

## Appetite

**[2w | 6w]** — [justificativa do tamanho]

## Solution

[Approach de alto nivel. O que sera construido, nao como. 1-2 paragrafos.]

### Bounded Contexts envolvidos
- [Context A] — [o que muda neste context]
- [Context B] — [o que muda]

### Containers impactados
- [Container X] — [o que muda]

## Rabbit Holes

[Coisas que podem consumir tempo desnecessario. Onde NÃO se aprofundar.]

1. [Rabbit hole 1] — [por que evitar]
2. [Rabbit hole 2] — [por que evitar]

## No-gos

[Explicitamente fora do escopo deste epico.]

1. [No-go 1] — [sera tratado em qual epico ou nunca]
2. [No-go 2]

## Acceptance Criteria

[Checklist testavel. Quando todos marcados, epico esta done.]

- [ ] [Criterio 1 — mensuravel]
- [ ] [Criterio 2]
- [ ] [Criterio 3]

## Dependencias

- Depende de: [epico NNN] (se aplicavel)
- Bloqueia: [epico NNN] (se aplicavel)
```

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Todo epico tem problema definido (nao feature)? | Reescrever como problema |
| 2 | Appetite realista (2w ou 6w)? | Ajustar ou split |
| 3 | No-gos explicitos? | Adicionar |
| 4 | Acceptance criteria testaveis? | Tornar mensuravel |
| 5 | Nenhum overlap de escopo entre epicos? | Resolver |
| 6 | Bounded contexts mapeados para epicos? | Mapear |
| 7 | Dependencias entre epicos acyclicas? | Resolver ciclos |
| 8 | Toda decisao tem >=2 alternativas documentadas? | Adicionar |
| 9 | Trade-offs explicitos? | Adicionar pros/cons |
| 10 | Premissas marcadas [VALIDAR] ou com dado? | Marcar [VALIDAR] |

### 4. Gate de Aprovacao: 1-Way-Door

**ATENCAO: Gate 1-way-door.** Escopo dos epicos define TODA a implementacao downstream (roadmap, specs, tasks, codigo).

Apresentar:

| # | Epico | Problema | Appetite | Contexts | Deps |
|---|-------|----------|----------|----------|------|
| 1 | NNN: [titulo] | [resumo] | 2w/6w | [contexts] | [deps] |

**Para CADA epico, pedir confirmacao:**

> **Epico NNN: [titulo]**
> Problema: [resumo]
> Appetite: [Xw]
> Inclui: [lista de scopo]
> Exclui (no-gos): [lista]
> Depende de: [epicos]
>
> **Confirma escopo? Isso define a implementacao. (sim/nao/ajustar)**

### 5. Salvar + Relatorio

```
## Epicos gerados

**Diretorio:** platforms/<nome>/epics/
**Epicos:** <N>
**Appetite total:** <N> semanas

| Epico | Appetite | Prioridade |
|-------|----------|-----------|
| NNN: [titulo] | Xw | P1/P2/P3 |

### Checks
[x] Problemas definidos (nao features)
[x] Appetites realistas
[x] No-gos explicitos
[x] Acceptance criteria testaveis
[x] Zero overlap de escopo
[x] Aprovacao por epico (gate 1-way-door)

### Proximo Passo
`/roadmap <nome>` — Sequenciar epicos em roadmap de entrega.
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Projeto muito pequeno (1 epico) | OK — 1 epico e valido |
| Muitos epicos (>8) | Agrupar relacionados ou questionar granularidade |
| Appetite total > 6 meses | Alertar sobre risco de escopo |
| Dependencia circular entre epicos | Resolver split ou merge |
| Context sem epico associado | Verificar se context e necessario agora |
