---
title: 'ADR-001: LikeC4 como Source of Truth'
status: Accepted
decision: We will use LikeC4 as the single source of truth for all architecture models,
  with `.likec4` files in `platforms/<name>/model/` and JSON export feeding the vision-build
  pipeline.
alternatives: Structurizr DSL, Mermaid-only, PlantUML
rationale: DSL declarativa com tipagem de elementos (person, platform, api, worker,
  boundedContext, module) mapeia diretamente para C4 + DDD
---
# ADR-001: LikeC4 como Source of Truth para Modelos Arquiteturais
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

Precisamos de uma ferramenta para modelar arquitetura (C4 + DDD Context Map) que seja versionavel em git, renderizavel no portal Starlight, e editavel por humanos e LLMs. O modelo precisa ser exportavel como JSON para alimentar pipelines automatizados (vision-build.py popula tabelas markdown via AUTO markers). A ferramenta deve suportar multi-project (N plataformas no mesmo repo) e ter hot reload para iteracao rapida.

## Decisao

We will use LikeC4 as the single source of truth for all architecture models, with `.likec4` files in `platforms/<name>/model/` and JSON export feeding the vision-build pipeline.

## Alternativas consideradas

### Structurizr DSL
- Pros: maduro, amplamente adotado, suporte nativo a C4
- Cons: requer JVM para renderizar, sem React component para embed direto, licenca comercial para features avancadas, DSL menos flexivel para DDD patterns customizados

### Mermaid-only
- Pros: suporte nativo em GitHub/GitLab, zero setup, LLMs ja conhecem bem
- Cons: nao tem tipagem de elementos (C4 kinds), sem export JSON estruturado, diagramas complexos ficam ilegiveisveis, sem multi-project

### PlantUML
- Pros: extremamente maduro, vasta documentacao, suporte C4 via stdlib
- Cons: requer servidor Java para renderizar, sintaxe verbosa, sem React component, sem hot reload, output apenas imagem (sem JSON estruturado)

## Consequencias

- [+] DSL declarativa com tipagem de elementos (person, platform, api, worker, boundedContext, module) mapeia diretamente para C4 + DDD
- [+] Export JSON permite pipeline automatizado (vision-build.py) sem parsing manual
- [+] React component (`likec4:react/<name>`) permite embed direto no portal Starlight
- [+] Multi-project nativo via `likec4.config.json` — cada plataforma tem seu namespace
- [+] Hot reload via `likec4 serve` para iteracao rapida durante design
- [-] Ferramenta relativamente nova — comunidade menor que Structurizr/Mermaid
- [-] LLMs tem menos treinamento em LikeC4 DSL comparado com Mermaid/PlantUML
- [-] Dependencia de VitePlugin customizado para integracao com Astro
