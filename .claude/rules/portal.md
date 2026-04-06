---
paths:
  - "portal/**"
---
# Portal Conventions (Astro + Starlight)

- `portal/src/lib/platforms.mjs` auto-descobre plataformas via `platforms/*/platform.yaml`
- `portal/astro.config.mjs` constrói sidebar dinamicamente dos manifests
- `platformSymlinksPlugin()` em astro.config.mjs cria symlinks automaticamente — setup manual desnecessário
- Architecture diagrams use Mermaid inline in `.md` files, rendered by `astro-mermaid`

## Routes
Dynamic routes em `src/pages/[platform]/` geram páginas para todas plataformas no build.
