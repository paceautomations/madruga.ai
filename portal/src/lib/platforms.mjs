/**
 * Platform discovery and sidebar generation.
 * Reads platforms / * /platform.yaml at build time to dynamically configure the portal.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const yaml = require('js-yaml');

// Resolve platforms dir relative to the repo root (works in both dev and build)
const __dirname = path.dirname(fileURLToPath(import.meta.url));

function findPlatformsDir() {
  // Walk up from current file to find platforms/ directory
  let dir = __dirname;
  for (let i = 0; i < 10; i++) {
    const candidate = path.join(dir, 'platforms');
    if (fs.existsSync(candidate)) return candidate;
    dir = path.dirname(dir);
  }
  // Fallback: relative to process.cwd()
  return path.resolve(process.cwd(), '../platforms');
}

const PLATFORMS_DIR = findPlatformsDir();

export function discoverPlatforms(platformsDir) {
  const dir = platformsDir ?? PLATFORMS_DIR;
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter(
      (d) =>
        d.isDirectory() &&
        fs.existsSync(path.join(dir, d.name, 'platform.yaml')),
    )
    .map((d) => {
      const manifest = yaml.load(
        fs.readFileSync(path.join(dir, d.name, 'platform.yaml'), 'utf8'),
      );
      return manifest;
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function buildSidebar(platforms) {
  return platforms.map((p) => ({
    label: p.title || p.name,
    collapsed: true,
    items: [
      {
        label: 'Business',
        items: [
          { slug: `${p.name}/business/vision` },
          ...(p.views.flows?.length
            ? [{ label: 'Business Process', link: `/${p.name}/business-flow/` }]
            : []),
          { slug: `${p.name}/business/solution-overview` },
        ],
      },
      {
        label: 'Engineering',
        items: [
          { label: 'System Landscape', link: `/${p.name}/landscape/` },
          { label: 'Containers', link: `/${p.name}/containers/` },
          {
            label: 'Context Map',
            items: [
              { label: 'Context Map', link: `/${p.name}/context-map/` },
              ...p.views.structural
                .filter((v) => v.id.endsWith('Detail'))
                .map((v) => ({
                  label: v.label,
                  link: `/${p.name}/bc/${v.id.replace('Detail', '').toLowerCase()}/`,
                })),
            ],
          },
          { slug: `${p.name}/engineering/domain-model` },
          { slug: `${p.name}/engineering/integrations` },
          { slug: `${p.name}/engineering/blueprint` },
        ],
      },
      {
        label: 'Planning',
        items: [
          { label: 'Roadmap', link: `/${p.name}/roadmap/` },
          { label: 'Epics', autogenerate: { directory: `${p.name}/epics` } },
        ],
      },
      {
        label: 'ADRs',
        collapsed: true,
        items: [
          { label: 'Decision Overviews', link: `/${p.name}/decisions/` },
          { label: 'ADRs', autogenerate: { directory: `${p.name}/decisions` } },
        ],
      },
      {
        label: 'Research',
        collapsed: true,
        autogenerate: { directory: `${p.name}/research` },
      },
    ],
  }));
}

export function buildViewPaths(platform) {
  const paths = {
    index: `/${platform.name}/landscape/`,
    containers: `/${platform.name}/containers/`,
    contextMap: `/${platform.name}/context-map/`,
  };

  for (const flow of platform.views.flows ?? []) {
    const slug = flow.id
      .replace(/([A-Z])/g, '-$1')
      .toLowerCase()
      .replace(/^-/, '');
    paths[flow.id] = `/${platform.name}/${slug}/`;
  }

  for (const view of platform.views.structural) {
    if (view.id.endsWith('Detail')) {
      const slug = view.id.replace('Detail', '').toLowerCase();
      paths[view.id] = `/${platform.name}/bc/${slug}/`;
    }
  }

  return paths;
}
