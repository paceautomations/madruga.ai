---
description: Gera arquitetura de containers C4 L2 com diagramas LikeC4 para qualquer plataforma
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
handoffs:
  - label: Gerar Context Map (DDD)
    agent: madruga/context-map
    prompt: Gerar context map com relacoes entre bounded contexts baseado no domain model e containers
---

# Containers — Arquitetura C4 Level 2

Gera arquitetura de containers (~200 linhas) com diagrama C4 L2, tabela de containers, protocolos de comunicacao e NFRs por container. Inclui LikeC4 DSL para portal interativo.

## Regra Cardinal: ZERO Container sem Responsabilidade Clara

Um container = uma razao de existir. Se dois containers fazem a mesma coisa, mesclar. Se um container faz tudo, separar.

**NUNCA:**
- Criar container "utils" ou "shared" como runtime separado
- Separar em microservices sem justificativa de escala/equipe
- Omitir protocolos de comunicacao entre containers
- Criar container sem owner claro (qual bounded context pertence)

## Persona

Staff Engineer com 15+ anos. Foco em simplicidade operacional. "E possivel com menos containers?" Portugues BR.

## Uso

- `/containers fulano` — Gera containers para "fulano"
- `/containers` — Pergunta nome

## Diretorio

Salvar em:
- `platforms/<nome>/engineering/containers.md`
- `platforms/<nome>/model/platform.likec4`
- `platforms/<nome>/model/views.likec4`

## Instrucoes

### 0. Pre-requisitos

Rodar `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill containers` e parsear JSON.
- Se `ready: false`: ERROR listando dependencias faltantes.
- Se `ready: true`: ler artefatos em `available`.
- Ler `.specify/memory/constitution.md`.

### 1. Coletar Contexto + Questionar

**Leitura obrigatoria:**
- `engineering/domain-model.md` — bounded contexts e agregados
- `engineering/blueprint.md` — stack, NFRs, topologia
- `decisions/ADR-*.md` — decisoes de stack que impactam containers
- `model/spec.likec4` — element types existentes (NUNCA redefinir)
- `model/ddd-contexts.likec4` — naming de bounded contexts

**Perguntas Estruturadas:**

| Categoria | Pergunta |
|-----------|----------|
| **Premissas** | "Assumo [N] containers baseado nos bounded contexts. Correto?" |
| **Trade-offs** | "Monolito modular (simples, 1 deploy) ou microservices (complexo, deploy independente)?" |
| **Gaps** | "Blueprint nao especifica [messaging pattern]. Definir?" |
| **Provocacao** | "Voce realmente precisa de [N] containers? Comece com monolito modular e split depois." |

Aguardar respostas ANTES de gerar.

### 2. Gerar Artefatos

**Arquivo 1: engineering/containers.md**

```markdown
---
title: "Container Architecture"
updated: YYYY-MM-DD
---
# <Nome> — Container Architecture (C4 Level 2)

> Containers, responsabilidades, protocolos e NFRs. Ultima atualizacao: YYYY-MM-DD.

---

## Diagrama de Containers

```mermaid
graph TD
  ...
```

---

## Tabela de Containers

| Container | Tecnologia | Responsabilidade | Bounded Contexts | Protocolo In | Protocolo Out |
|-----------|-----------|-----------------|-----------------|-------------|--------------|
| ... | ... | ... | ... | ... | ... |

---

## Comunicacao Inter-Container

| De | Para | Protocolo | Dados | Sincrono? |
|----|------|-----------|-------|-----------|
| ... | ... | ... | ... | ... |

---

## NFRs por Container

| Container | Latencia P95 | Throughput | Disponibilidade | Notas |
|-----------|-------------|-----------|----------------|-------|
| ... | ... | ... | ... | ... |

---

## Data Ownership

| Container | Stores | Dados | Padrao |
|-----------|--------|-------|--------|
| ... | ... | ... | Database per service / Shared DB |
```

**Arquivo 2: model/platform.likec4**
- Definir elementos LikeC4 para cada container
- Relationships entre containers

**Arquivo 3: model/views.likec4**
- Views para o portal interativo
- Container view principal

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Todo container tem responsabilidade unica? | Mesclar ou justificar |
| 2 | Nenhum container orfao (desconectado)? | Conectar ou remover |
| 3 | Protocolos definidos para toda comunicacao? | Adicionar |
| 4 | NFRs mensuraveis por container? | Adicionar targets |
| 5 | LikeC4 syntax valida? | Corrigir |
| 6 | Max 200 linhas (.md)? | Condensar |
| 7 | Data ownership claro? | Definir |
| 8 | Toda decisao tem >=2 alternativas documentadas? | Adicionar |
| 9 | Trade-offs explicitos (pros/cons)? | Adicionar pros/cons |
| 10 | Premissas marcadas [VALIDAR] ou com dado? | Marcar [VALIDAR] |
| 11 | Consistencia entre .md e .likec4? | Alinhar |

### 4. Gate de Aprovacao: Human

Apresentar ao usuario:

**Resumo da Arquitetura de Containers:**
- Containers: [N]
- Comunicacoes: [N]
- Padrao: [monolito modular / microservices / hibrido]

**Decisoes-chave:**
| # | Decisao | Alternativa simples | Alternativa robusta | Escolha |
|---|---------|--------------------|--------------------|---------|
| 1 | ... | ... | ... | ... |

**Perguntas de validacao:**
1. E possivel com menos containers?
2. Protocolos de comunicacao fazem sentido?
3. Data ownership esta correto?
4. NFRs por container sao realistas?

Aguardar aprovacao antes de salvar.

### 5. Salvar + Relatorio

```
## Containers gerados

**Arquivos:**
- platforms/<nome>/engineering/containers.md (<N> linhas)
- platforms/<nome>/model/platform.likec4
- platforms/<nome>/model/views.likec4

**Containers:** <N>
**Comunicacoes:** <N>

### Checks
[x] Responsabilidade unica por container
[x] Zero containers orfaos
[x] Protocolos definidos
[x] NFRs com targets
[x] LikeC4 syntax valida

### Proximo Passo
`/context-map <nome>`
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Domain model com 1 bounded context | Gerar 1 container (monolito) — nao forcar split |
| Muitos containers (>8) | Desafiar: "Voce tem equipe para manter 8 servicos?" |
| LikeC4 syntax error | Validar contra spec antes de salvar |
| Conflito com blueprint topologia | Alinhar com blueprint, propor update se necessario |
