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

Verificar plataforma existe e tem docs de arquitetura.

### 1. Detectar Drift

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

### 2. Propor Atualizacoes

Para cada drift: identificar doc afetado, propor mudanca especifica.

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Todo drift identificado? | Re-scan |
| 2 | Atualizacoes consistentes entre docs? | Verificar cross-references |
| 3 | LikeC4 syntax valida? | Corrigir |

### 4. Gate: Human

Apresentar drift report e atualizacoes propostas. Pedir aprovacao antes de aplicar.

### 5. Salvar + Relatorio

```
## Reconciliacao completa

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
