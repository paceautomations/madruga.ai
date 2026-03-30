---
title: 'ADR-008: MECE Artifact Model'
status: Accepted
decision: We will enforce a MECE artifact model where each documentation artifact
  has exactly one owner (the skill/phase that generates it) and one purpose (the question
  it answers), with no content duplication across artifacts.
alternatives: Ad-hoc docs (cada dev escreve onde quiser), Wiki (Notion, Confluence),
  Shared docs (Google Docs)
rationale: Cada artefato tem ownership claro — daemon sabe exatamente o que atualizar
---
# ADR-008: MECE Artifact Model para Documentacao
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

Sistemas de documentacao tipicamente sofrem de: duplicacao (mesma info em 3 lugares), ownership ambiguo (quem atualiza o que?), e drift (docs desatualizados). Precisamos de um modelo onde cada artefato tem exatamente 1 owner (skill/pipeline que o gera) e 1 purpose (o que ele responde), garantindo Mutually Exclusive, Collectively Exhaustive (MECE). Isso e critico para o daemon autonomo, que precisa saber exatamente qual artefato atualizar.

## Decisao

We will enforce a MECE artifact model where each documentation artifact has exactly one owner (the skill/phase that generates it) and one purpose (the question it answers), with no content duplication across artifacts.

## Alternativas consideradas

### Ad-hoc docs (cada dev escreve onde quiser)
- Pros: zero friction para criar docs, flexibilidade total
- Cons: duplicacao inevitavel, ownership ambiguo, docs ficam stale rapidamente, impossivel automatizar updates

### Wiki (Notion, Confluence)
- Pros: colaboracao em tempo real, busca, comentarios, templates
- Cons: fora do git (perde versionamento), drift inevitavel com codigo, nao acessivel por LLMs facilmente, vendor lock-in

### Shared docs (Google Docs)
- Pros: colaboracao real-time, comentarios inline, historico de versoes
- Cons: fora do git, sem automacao (vision-build.py nao pode popular), ownership difuso, nao acessivel por CLI/LLM

## Consequencias

- [+] Cada artefato tem ownership claro — daemon sabe exatamente o que atualizar
- [+] Zero duplicacao — informacao vive em um lugar so
- [+] Pipeline automatizado — vision-build.py popula AUTO markers sem ambiguidade
- [+] Auditavel — git blame mostra quem/quando/por que cada artefato mudou
- [-] Rigidez — criar um doc novo requer decidir owner e purpose (overhead para docs ad-hoc)
- [-] Curva de aprendizado — novos contribuidores precisam entender o modelo MECE
- [-] Cross-references necessarios — como info nao duplica, docs precisam linkar uns aos outros
