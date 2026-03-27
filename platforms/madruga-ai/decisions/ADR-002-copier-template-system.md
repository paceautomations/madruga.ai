---
title: "ADR-002: Copier para Scaffolding"
---
# ADR-002: Copier para Scaffolding de Plataformas
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

O sistema suporta N plataformas, cada uma com a mesma estrutura de diretorios (business/, engineering/, decisions/, epics/, model/). Precisamos de uma ferramenta que: (1) scaffold novas plataformas a partir de um template, (2) permita sync de mudancas estruturais para plataformas existentes sem sobrescrever conteudo customizado, (3) seja simples de usar via CLI, e (4) suporte Jinja2 para templating.

## Decisao

We will use Copier >= 9.4.0 as the template engine for scaffolding new platforms, with `_skip_if_exists` protecting platform-specific content during `copier update`.

## Alternativas consideradas

### Cookiecutter
- Pros: amplamente adotado, grande ecossistema de templates, LLMs conhecem bem
- Cons: sem `update` nativo (nao sincroniza mudancas estruturais em plataformas existentes), sem `_skip_if_exists`, fork-and-forget — cada plataforma diverge do template

### Yeoman
- Pros: ecossistema rico, composable generators, suporte a prompts interativos
- Cons: requer Node.js, complexidade desnecessaria para nosso caso (nao precisamos de generators compostos), sem update nativo

### Scripts manuais (bash/python)
- Pros: controle total, zero dependencia, simples para casos triviais
- Cons: nao escala — cada mudanca estrutural requer update manual em N plataformas, propenso a erros, sem dry-run, sem diff de mudancas

## Consequencias

- [+] `copier update` sincroniza mudancas estruturais sem sobrescrever conteudo customizado (via `_skip_if_exists`)
- [+] `.copier-answers.yml` rastreia estado do template por plataforma — reproducivel
- [+] Jinja2 templating permite customizacao via variaveis (nome, descricao, lifecycle)
- [+] `platform.py new <name>` encapsula o workflow completo (copier + register + lint)
- [-] Dependencia Python (copier) — mas ja usamos Python para vision-build.py e platform.py
- [-] Curva de aprendizado para `_skip_if_exists` e conflitos em `copier update`
