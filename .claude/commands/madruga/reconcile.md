---
description: Detecta drift entre implementacao e documentacao e propoe atualizacoes
arguments:
  - name: platform
    description: "Nome da plataforma/produto."
    required: false
argument-hint: "[nome-da-plataforma]"
handoffs:
  - label: Verificar Status do Pipeline
    agent: madruga/pipeline-status
    prompt: "Documentacao atualizada. Verificar status do pipeline."
---

# Reconcile — Deteccao e Correcao de Drift

Compara implementacao (git diff / PR) com documentacao de arquitetura. Identifica drift e propoe atualizacoes nos docs afetados.

## Regra Cardinal: ZERO Drift Silencioso

Todo desvio entre implementacao e documentacao deve ser explicitado. Nenhuma mudanca de arquitetura pode existir sem atualizacao correspondente nos docs.

## Persona

Architect / Documentation Guardian. Portugues BR.

## Uso

- `/reconcile fulano` — Reconcilia "fulano" pos-implementacao
- `/reconcile` — Pergunta plataforma

## Diretorio

Atualiza docs existentes em `platforms/<nome>/`. Report em `reconcile-report.md`.

## Instrucoes

### 0. Pre-requisitos

Rodar `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill reconcile` e parsear JSON.
- Se `ready: false`: ERROR listando dependencias faltantes.
- Se `ready: true`: ler artefatos em `available`.
- Ler `.specify/memory/constitution.md`.

### 1. Coletar Contexto + Detectar Drift

Ler:
- `git diff` ou `git log` recente
- `business/*` — vision, solution-overview, process
- `engineering/*` — blueprint, domain-model, containers, context-map
- `model/*.likec4` — modelos LikeC4

**Categorias de drift:**

| Categoria | Como Detectar |
|-----------|--------------|
| Scope drift | Features implementadas nao estao no solution-overview |
| Architecture drift | Implementacao diverge do blueprint/ADRs |
| Model drift | Containers/contexts mudaram mas LikeC4 nao atualizado |
| Domain drift | Novas entidades/agregados nao no domain-model |

**Perguntas Estruturadas:**

| Categoria | Pergunta |
|-----------|----------|
| **Premissas** | "Assumo que mudanca em [X] foi intencional. Correto?" |
| **Trade-offs** | "Atualizar docs agora (completo) ou marcar para proximo sprint (rapido)?" |
| **Gaps** | "Nao sei se mudanca em [X] afeta [doc Y]. Verificar?" |
| **Provocacao** | "Drift em [area] pode indicar que o ADR original precisa ser revisado." |

Aguardar respostas ANTES de propor atualizacoes.

### 2. Propor Atualizacoes

Para cada drift detectado, gerar proposta estruturada:

| # | Drift | Doc Afetado | Mudanca Proposta | Severidade |
|---|-------|-------------|-----------------|-----------|
| 1 | [descricao] | [arquivo] | [o que mudar] | alta/media/baixa |

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Todo drift identificado? | Re-scan |
| 2 | Atualizacoes consistentes entre docs? | Verificar cross-references |
| 3 | LikeC4 syntax valida? | Corrigir |
| 4 | Toda proposta tem >=2 alternativas? | Adicionar alternativa |
| 5 | Trade-offs explicitos? | Adicionar pros/cons |
| 6 | Premissas marcadas [VALIDAR] ou com dado? | Marcar [VALIDAR] |

### 4. Gate: Human

Apresentar drift report e atualizacoes propostas. Pedir aprovacao antes de aplicar.

### 5. Salvar + Relatorio

```
## Reconciliacao completa

**Arquivo:** platforms/<nome>/reconcile-report.md
**Linhas:** <N>
**Drifts detectados:** <N>
**Docs atualizados:** <N>
**Categorias:** [scope/architecture/model/domain]

Proximo: `/pipeline-status <nome>` para verificar estado do pipeline.
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Sem git diff (nada mudou) | Reportar "zero drift" |
| Docs de arquitetura incompletos | Listar gaps, sugerir completar pipeline |
| Drift muito grande | Sugerir re-executar skills afetadas |
