---
id: 004
title: "speckit.map — Mapeamento de Codebase Existente"
status: proposed
phase: pitch
appetite: small-batch
priority: next
arch:
  modules: [analyzeEngine, specifyPhase]
  contexts: [specification]
  containers: [speckitSkills, speckitBridge]
---
# speckit.map — Mapeamento de Codebase Existente

## Problema

A fase PLAN gera designs sem conhecer o codigo existente. Resultado:

1. **Duplicacao de codigo** — plan propoe criar modulo que ja existe com nome diferente
2. **Integracao ignorada** — plan nao sabe que ja existe um adapter para o servico X
3. **Convencoes violadas** — plan propoe patterns diferentes dos ja usados no codebase
4. **Estimativas infladas** — tasks incluem trabalho que ja esta feito
5. **Refactor desnecessario** — plan propoe solucao greenfield quando bastava estender modulo existente

## Appetite

1-2 semanas (small batch). O mapping nao precisa ser perfeito — precisa ser "bom o suficiente" para informar o plan. Precisao de 80% e aceitavel.

## Solucao

Criar skill `speckit.map` que executa antes do PLAN e gera `map.md`:

1. **Scan estrutural**: lista diretorios, arquivos, e suas responsabilidades inferidas (via docstrings, README, nome do arquivo)
2. **Dependency graph**: imports e dependencias entre modulos (via AST parsing para Python, regex para outros)
3. **Pattern detection**: identifica patterns em uso (repository pattern, adapter pattern, factory, etc.)
4. **Convention extraction**: detecta convencoes de naming, organizacao de testes, config management
5. **Relevant modules**: filtra apenas modulos relevantes para a spec em questao (usando embedding similarity ou keyword matching)

Output e `map.md` com secoes:
- Estrutura de diretorios relevante (tree filtrado)
- Modulos existentes relacionados (com 1-liner de descricao)
- Patterns em uso
- Convencoes detectadas
- Sugestoes de reuso ("considerar estender X ao inves de criar novo Y")

A fase PLAN recebe `spec.md + map.md` ao inves de apenas `spec.md`.

## Rabbit Holes

- **Nao tentar entender semantica profunda** — mapping e estrutural, nao semantico. Nao e code review.
- **Nao mapear codebase inteiro** — apenas modulos relevantes para a spec. Usar keywords da spec para filtrar.
- **Nao bloquear pipeline se mapping falhar** — se map.md nao puder ser gerado, PLAN roda sem ele (degradacao graceful)
- **Nao persistir map.md permanentemente** — e artefato efemero, gerado fresh para cada pipeline run

## Criterios de Aceitacao

- [ ] `speckit.map` gera `map.md` com estrutura, modulos, patterns, e convencoes
- [ ] map.md filtra apenas modulos relevantes para a spec em questao
- [ ] Fase PLAN recebe map.md como input adicional
- [ ] Plans gerados com map.md propoem menos duplicacao (metrica: PRs com "already exists" comments)
- [ ] Skill funciona para codebases Python e TypeScript
- [ ] Pipeline nao falha se mapping falhar (graceful degradation)
