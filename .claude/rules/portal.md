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

The remark plugin `remarkResolveLinks` (wired in `astro.config.mjs` → `markdown.remarkPlugins`)
resolves relative links **filesystem-style from the source `.md`** at build time. If the
target exists under `platforms/<p>/`, the link is rewritten to the absolute portal URL
(`/<platform>/<section>/<doc>/`). If the target does not exist on disk, the plugin leaves
the link untouched so the browser can still do URL-style resolution (which is what works
for same-section links).

This means authors can **think filesystem-relative** and it just works:

- Same-section (`engineering/blueprint.md` → `engineering/containers.md`):
  `[containers](./containers/)` (filesystem) or `[containers](../containers/)` (URL-style) — both resolve.
- Cross-section (`business/process.md` → `engineering/domain-model.md`):
  `[domain-model](../engineering/domain-model/)` — plugin resolves filesystem, emits `/prosauai/engineering/domain-model/`.
- From epics (`epics/NNN/pitch.md` → `engineering/blueprint.md`):
  `[blueprint](../../engineering/blueprint/)` — plugin resolves.
- Anchors and queries are preserved: `../engineering/blueprint/#containers` is fine.
- `.md` extensions are stripped: both `../decisions/ADR-024-schema.md` and `../decisions/ADR-024-schema/` work.

Conventions:
- **Never use absolute paths** like `/prosauai/engineering/containers/` — plugin emits
  those at build; sources stay portable if a platform is renamed.
- Use **original filename casing** (e.g., `ADR-011-...`, not `adr-011-...`).
- Always end with trailing slash on directory-style targets (e.g., `../engineering/containers/`).

If a link 404s, the plugin didn't find the target on disk. Fix the source path — don't
add `../` levels to compensate for URL-style resolution quirks, since that re-introduces
the legacy breakage class.
