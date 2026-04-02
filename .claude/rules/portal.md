---
paths:
  - "portal/**"
---
# Portal Conventions (Astro + Starlight + LikeC4 React)

- `portal/src/lib/platforms.mjs` auto-descobre plataformas via `platforms/*/platform.yaml`
- `portal/astro.config.mjs` constrói sidebar dinamicamente dos manifests
- `platformSymlinksPlugin()` em astro.config.mjs cria symlinks automaticamente — setup manual desnecessário
- `LikeC4VitePlugin({ workspace: '../platforms' })` para multi-project support

## platformLoaders
Ao adicionar nova plataforma, adicionar o import em `platformLoaders` no arquivo `portal/src/components/viewers/LikeC4Diagram.tsx`. Usa `React.lazy` com imports per-project (`likec4:react/<name>`).

## Routes
Dynamic routes em `src/pages/[platform]/` geram páginas para todas plataformas no build.
