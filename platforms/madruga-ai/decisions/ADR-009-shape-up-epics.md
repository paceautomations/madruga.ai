---
title: 'ADR-009: Shape Up Epics'
status: Accepted
decision: We will use Shape Up pitch format for all epics, stored as `platforms/<name>/epics/NNN-slug/pitch.md`
  with YAML frontmatter linking to architecture model (contexts, containers, modules).
alternatives: Scrum user stories, Kanban cards (titulo + descricao livre), Free-form
  docs (RFC-style)
rationale: Appetite explicito — forca decisao de budget antes de comecar (1-2 semanas
  ou 4-6 semanas)
---
# ADR-009: Shape Up Pitches para Gestao de Epics
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

Precisamos de um formato para descrever unidades de trabalho (epics) que: (1) defina claramente o problema e appetite (budget de tempo), (2) identifique rabbit holes antes de comecar, (3) seja legivel por LLMs para execucao autonoma pelo easter, e (4) forca priorizacao explicita (now/next/later). O formato deve ser compativel com o pipeline spec-to-code e mapeavel para bounded contexts e containers.

## Decisao

We will use Shape Up pitch format for all epics, stored as `platforms/<name>/epics/NNN-slug/pitch.md` with YAML frontmatter linking to architecture model (contexts, containers, modules).

## Alternativas consideradas

### Scrum user stories
- Pros: formato amplamente conhecido, "As a X, I want Y, so that Z" e simples
- Cons: foco em deliverables atomicos (nao em problemas), sem appetite/budget explicito, sem rabbit holes, fragmentacao excessiva para trabalho de arquitetura

### Kanban cards (titulo + descricao livre)
- Pros: zero overhead de formato, flexibilidade total
- Cons: sem estrutura — LLM nao consegue extrair problema/solucao/riscos de forma confiavel, sem appetite (trabalho expande sem limite), sem acceptance criteria explicito

### Free-form docs (RFC-style)
- Pros: flexivel, permite profundidade variavel, familiar para engenheiros senior
- Cons: sem padrao — cada doc tem estrutura diferente, dificil de automatizar parsing, sem campos obrigatorios (appetite, rabbit holes)

## Consequencias

- [+] Appetite explicito — forca decisao de budget antes de comecar (1-2 semanas ou 4-6 semanas)
- [+] Rabbit holes documentados — evita time sinks conhecidos
- [+] Frontmatter YAML permite pipeline automatizado (easter le pitch e sabe quais contexts/containers sao afetados)
- [+] Acceptance criteria como checklist — verificavel por automacao
- [+] Formato padronizado — LLMs conseguem extrair e gerar pitches de forma confiavel
- [-] Overhead para mudancas pequenas — nem tudo justifica um pitch completo
- [-] Requer disciplina para manter pitches atualizados conforme implementacao avanca
