---
title: 'ADR-003: Astro + Starlight Portal'
status: Accepted
decision: We will use Astro + Starlight as the documentation portal framework, with
  `platforms.mjs` for auto-discovery, symlinks for content, and `astro-mermaid`
  for diagram rendering.
alternatives: Docusaurus, MkDocs + Material, VitePress
rationale: Starlight gera site estatico otimizado — deploy trivial (Vercel, Netlify,
  S3)
---
# ADR-003: Astro + Starlight para Portal de Documentacao
**Status:** Accepted | **Data:** 2026-03-27

## Contexto

Precisamos de um portal web que: (1) renderize documentacao markdown de N plataformas, (2) renderize diagramas Mermaid inline via `astro-mermaid`, (3) gere sidebar dinamicamente a partir de `platform.yaml`, (4) suporte rotas dinamicas (`[platform]/`), e (5) tenha build estatico para deploy simples. O portal deve auto-descobrir plataformas sem configuracao manual.

## Decisao

We will use Astro + Starlight as the documentation portal framework, with `platforms.mjs` for auto-discovery, symlinks for content, and `astro-mermaid` for diagram rendering.

## Alternativas consideradas

### Docusaurus
- Pros: maduro, grande comunidade, suporte nativo a versioning, bom ecossistema de plugins
- Cons: bundle pesado (React SSR completo), sidebar config manual (nao suporta auto-discovery facilmente), integracao com VitePlugin requer workaround (Docusaurus usa webpack)

### MkDocs + Material
- Pros: Python (alinhado com nosso stack), temas excelentes, simplicidade
- Cons: sem rotas dinamicas, menos flexivel para customizacoes avancadas

### VitePress
- Pros: rapido, Vue-based, Vite nativo, bom DX
- Cons: sidebar config manual, menos features que Starlight para documentacao tecnica

## Consequencias

- [+] Starlight gera site estatico otimizado — deploy trivial (Vercel, Netlify, S3)
- [+] `platforms.mjs` auto-descobre plataformas via `platform.yaml` — zero config manual ao adicionar plataforma
- [+] `astro-mermaid` renderiza diagramas Mermaid inline nos documentos Markdown — zero config extra
- [+] Symlinks (`setup.sh`) permitem que content viva em `platforms/` mas seja servido como `src/content/docs/`
- [-] Astro ainda em evolucao rapida — breaking changes entre versoes
- [-] Symlinks exigem `setup.sh` que roda no `npm install` (postinstall hook)
- [-] Cada nova plataforma requer symlink setup (automatizado via postinstall hook)
