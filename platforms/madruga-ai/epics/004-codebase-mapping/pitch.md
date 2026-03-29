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

A fase PLAN hoje opera como se todo projeto fosse greenfield. Em cenarios brownfield, isso gera plans que ignoram codigo existente. Solucao: **agentes paralelos mapeiam o codebase antes do PLAN**.

Criar skill `speckit.map` que executa antes do PLAN usando subagents paralelos:

1. **Stack detection**: identifica linguagens, frameworks, versoes, e build tools em uso
2. **Scan estrutural**: lista diretorios, arquivos, e suas responsabilidades inferidas (via docstrings, README, nome do arquivo)
3. **Pattern detection**: identifica patterns em uso (repository pattern, adapter pattern, factory, etc.)
4. **Convention extraction**: detecta convencoes de naming, organizacao de testes, config management
5. **File structure mapping**: monta arvore de diretorios com anotacoes de responsabilidade por modulo
6. **Relevant modules**: filtra apenas modulos relevantes para a spec em questao (usando keyword matching)

Output e `codebase-map.md` com secoes:
- Stack e ferramentas detectadas
- Estrutura de diretorios relevante (tree filtrado)
- Modulos existentes relacionados (com 1-liner de descricao)
- Patterns em uso
- Convencoes detectadas
- Sugestoes de reuso ("considerar estender X ao inves de criar novo Y")

A fase PLAN recebe `spec.md + codebase-map.md` ao inves de apenas `spec.md`.

## Rabbit Holes

- **Nao tentar entender todo o codigo** — foco em patterns, convencoes, e estrutura. Nao e code review nem analise semantica profunda.
- **Nao gerar codigo** — o mapeamento so documenta o que existe. Nao sugere implementacao, apenas informa o PLAN.
- **Nao mapear codebase inteiro** — apenas modulos relevantes para a spec. Usar keywords da spec para filtrar.
- **Nao bloquear pipeline se mapping falhar** — se codebase-map.md nao puder ser gerado, PLAN roda sem ele (degradacao graceful)
- **Nao persistir codebase-map.md permanentemente** — e artefato efemero, gerado fresh para cada pipeline run

## No-gos

- **Nao fazer analise de qualidade do codigo** — mapping nao e linting nem code review. Nao emite julgamentos sobre o codigo existente.
- **Nao seguir dependencias externas** — mapeia apenas o codebase local. Nao resolve nem analisa pacotes de terceiros.
- **Nao usar LLM para inferir intencao do codigo** — usar heuristica mecanica (AST, regex, nomes de arquivo). LLM so e usado para formatar o output.

## Criterios de Aceitacao

- [ ] `speckit.map` gera `codebase-map.md` com stack, estrutura, modulos, patterns, e convencoes
- [ ] Agentes paralelos executam deteccao de stack, patterns, e convencoes
- [ ] codebase-map.md filtra apenas modulos relevantes para a spec em questao
- [ ] Fase PLAN recebe codebase-map.md como input adicional
- [ ] Plans gerados com codebase-map.md propoem menos duplicacao (metrica: PRs com "already exists" comments)
- [ ] Skill funciona para codebases Python e TypeScript
- [ ] Pipeline nao falha se mapping falhar (graceful degradation)
