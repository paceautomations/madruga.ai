---
description: Recomenda proximo passo do pipeline DAG baseado em status e prioridade de layer
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
---

# Pipeline Next — Proximo Passo

Skill read-only. Analisa status do pipeline e recomenda proximo no a executar. NAO auto-executa — apenas sugere.

## Regra: NUNCA Auto-Executar

Esta skill RECOMENDA. O usuario decide quando e se executa. Zero execucao automatica.

## Persona

Pipeline Advisor. Conciso, direto. Portugues BR.

## Uso

- `/pipeline-next fulano` — Proximo passo para "fulano"
- `/pipeline-next` — Pergunta plataforma

## Instrucoes

### 1. Coletar Status

Rodar: `.specify/scripts/bash/check-platform-prerequisites.sh --json --status --platform <nome>`

### 2. Analisar e Recomendar

**Filtrar nos com status=ready.**

**Se 1 ready:**
```
## Proximo Passo Recomendado

**`/<skill> <platform>`**
- O que faz: [descricao 1 linha]
- Dependencias: [ja atendidas]
- Gate: [human/auto/1-way-door]

Para executar: `/<skill> <platform>`
```

**Se multiplos ready:**
Listar todos e recomendar por esta logica de prioridade:
1. **Non-optional antes de optional** (critical path primeiro)
2. **Mais dependentes downstream primeiro** (desbloqueia mais work)
3. **Layer como tiebreaker:** business > research > engineering > planning

Dentro do mesmo layer: menos dependencias pendentes = primeiro.

**Se nenhum ready E todos done:**
```
## Pipeline Completo! 🎉

Todas as 14 etapas estao done.
Proximo: iniciar implementacao pelo primeiro epico do roadmap com `/discuss <platform> <NNN>` (onde NNN e o numero do epico).
```

**Se nenhum ready E alguns blocked:**
```
## Nenhuma Etapa Disponivel

Bloqueadores:
| Skill | Blocked por |
|-------|-----------|
| ... | ... |

Resolva os bloqueadores primeiro.
```

### 3. Apresentar

Mostrar recomendacao. NAO executar. Aguardar usuario.

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Script falha | ERROR: pre-requisito python3 nao instalado |
| Platform.yaml sem pipeline section | ERROR: rodar `copier update` na plataforma |
| Nome de plataforma invalido | Perguntar nome correto |
