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

## Cross-Reference Links in Platform Docs

- **Always use relative paths** between platform docs (e.g., `[Vision](./vision/)`, `[ADR-011](../decisions/ADR-011-pool-rls-multi-tenant/)`).
- **Never use absolute paths** like `/prosauai/engineering/containers/` — they break when the route structure changes and section names are easy to omit.
- Relative path calculation from the source file's directory:
  - Same section: `./other-doc/`
  - Adjacent section: `../other-section/other-doc/`
  - From epics (nested deeper): `../../section/doc/`
- Use **original filename casing** (e.g., `ADR-011-...`, not `adr-011-...`).
- Always end with trailing slash (e.g., `../engineering/containers/`).
