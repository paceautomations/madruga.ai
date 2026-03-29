---
description: Mapeia codebase existente (brownfield) ou declara greenfield para qualquer plataforma
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
---

# Codebase Map — Mapeamento de Codebase

Detecta se o projeto e brownfield (codebase existente) ou greenfield (do zero). Se brownfield, analisa estrutura, dependencias, padroes e integracoes. Se greenfield, gera artefato minimo.

**Node opcional no DAG** — se nao executado, nao bloqueia nenhum no downstream.

## Regra Cardinal: ZERO Achismo sobre Codebase

Toda afirmacao sobre o codebase deve ser baseada em **leitura real de codigo**. Nenhuma suposicao sobre estrutura, padroes ou dependencias sem evidencia no filesystem.

**NUNCA:**
- Assumir que um padrao existe sem encontrar no codigo
- Inferir dependencias sem ler package.json/requirements.txt/go.mod equivalente
- Afirmar integracoes sem encontrar chamadas reais
- Inventar metricas (linhas de codigo, cobertura) sem medir

## Persona

Staff Engineer. Analise objetiva e factual. Mapeia o que existe, sem julgar. Portugues BR.

## Uso

- `/codebase-map fulano` — Mapeia codebase da plataforma "fulano"
- `/codebase-map` — Pergunta nome da plataforma

## Diretorio

Salvar em `platforms/<nome>/research/codebase-context.md`.

## Instrucoes

### 0. Pre-requisitos

Rodar `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill codebase-map` e parsear JSON.
- Se `ready: false`: ERROR listando dependencias faltantes.
- Se `ready: true`: ler artefatos em `available` como contexto.
- Ler `.specify/memory/constitution.md`.

### 1. Detectar Brownfield vs Greenfield

**Criterios de deteccao:**

| Criterio | Onde verificar | Resultado |
|----------|---------------|-----------|
| Campo `source_repo` no platform.yaml | `platforms/<nome>/platform.yaml` | Se existe → brownfield |
| Diretorio `src/` no repo referenciado | Repo ou diretorio local | Se existe → brownfield |
| Arquivos de dependencia (package.json, requirements.txt, go.mod, Cargo.toml, pom.xml) | Raiz do repo referenciado | Se existe → brownfield |

**Se NENHUM criterio atendido → GREENFIELD.**

### 2A. Fluxo Greenfield

Se greenfield, gerar artefato minimo:

```markdown
---
title: "Codebase Context"
updated: YYYY-MM-DD
---
# <Nome> — Codebase Context

> Projeto greenfield — nenhum codebase existente.

## Status

Greenfield. Nenhuma analise de codebase necessaria.

## Implicacoes

- Nao ha divida tecnica pre-existente
- Liberdade total para escolha de stack e padroes
- Nao ha integracoes legadas a considerar
```

Pular para secao 5 (Salvar).

### 2B. Fluxo Brownfield

Se brownfield, **spawnar Agent subagents em paralelo** para analise:

**Agent 1 — Estrutura de Arquivos:**
- Mapear arvore de diretorios (max 3 niveis)
- Identificar diretorios principais e seu proposito
- Contar arquivos por tipo/extensao

**Agent 2 — Dependencias:**
- Ler arquivos de dependencia (package.json, requirements.txt, etc.)
- Listar dependencias diretas com versoes
- Identificar frameworks e bibliotecas principais

**Agent 3 — Padroes Detectados:**
- Buscar padroes arquiteturais (MVC, hexagonal, DDD, monolith, microservices)
- Identificar padroes de codigo (design patterns recorrentes)
- Detectar convencoes de nomenclatura

**Agent 4 — Integracoes:**
- Buscar chamadas HTTP/gRPC/mensageria
- Identificar servicos externos referenciados
- Mapear pontos de integracao (APIs, webhooks, filas)

Consolidar resultados em `research/codebase-context.md`:

```markdown
---
title: "Codebase Context"
updated: YYYY-MM-DD
---
# <Nome> — Codebase Context

> Analise do codebase existente. Ultima atualizacao: YYYY-MM-DD.

---

## Resumo

[2-3 linhas: linguagem principal, framework, tamanho aproximado]

---

## Estrutura de Arquivos

[Arvore anotada — max 3 niveis com proposito de cada diretorio]

---

## Stack Tecnologico

| Categoria | Tecnologia | Versao | Notas |
|-----------|-----------|--------|-------|
| Linguagem | ... | ... | ... |
| Framework | ... | ... | ... |
| Database | ... | ... | ... |
| Infra | ... | ... | ... |

---

## Dependencias Principais

| Dependencia | Versao | Proposito |
|-------------|--------|-----------|
| ... | ... | ... |

---

## Padroes Detectados

| Padrao | Evidencia | Arquivo(s) |
|--------|-----------|-----------|
| ... | ... | ... |

---

## Integracoes

| Servico | Tipo | Endpoint/Topico | Arquivo(s) |
|---------|------|----------------|-----------|
| ... | ... | ... | ... |

---

## Observacoes

[Riscos, divida tecnica evidente, areas que precisam de atencao]
```

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Toda afirmacao tem arquivo de evidencia? | Adicionar referencia ou remover |
| 2 | Nenhuma suposicao sem leitura real? | Verificar ou marcar [NAO VERIFICADO] |
| 3 | Brownfield/greenfield corretamente detectado? | Re-verificar criterios |
| 4 | Dependencias com versao? | Ler arquivo de dependencia |
| 5 | Max 150 linhas (brownfield) / 15 linhas (greenfield)? | Condensar |

### 4. Gate: Auto

Este no tem gate **auto** — nao requer aprovacao humana. Salvar automaticamente.

### 5. Salvar + Relatorio

1. Salvar em `platforms/<nome>/research/codebase-context.md`
2. Informar ao usuario:

```
## Codebase Map gerado

**Arquivo:** platforms/<nome>/research/codebase-context.md
**Tipo:** [Greenfield | Brownfield]
**Linhas:** <N>

### Checks
[x] Deteccao brownfield/greenfield correta
[x] [Se brownfield] Todas afirmacoes com evidencia
[x] [Se brownfield] Dependencias com versao
[x] Limite de linhas respeitado

### Nota
Este e um no OPCIONAL do pipeline. Nenhum no downstream depende exclusivamente dele.
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| source_repo no platform.yaml aponta para repo inacessivel | Tratar como greenfield, avisar usuario |
| Codebase muito grande (>10k arquivos) | Limitar analise aos 3 niveis principais, amostrar padroes |
| Multiplas linguagens | Listar todas, focar na principal (mais arquivos) |
| Sem arquivos de dependencia | Inferir stack pelos arquivos, marcar [INFERIDO] |
| Platform.yaml sem campo source_repo | Verificar se ha src/ local, senao greenfield |
