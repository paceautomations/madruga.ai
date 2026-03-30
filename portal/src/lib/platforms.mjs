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

/** Phase → Starlight badge variant mapping */
const phaseBadgeVariant = {
  now: 'success',
  next: 'caution',
  later: 'note',
};

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

/**
 * Discover epics for a platform by reading pitch.md frontmatter.
 * Returns sorted array of { dir, id, title, status, phase }.
 */
export function discoverEpics(platformName, platformsDir) {
  const dir = platformsDir ?? PLATFORMS_DIR;
  const epicsDir = path.join(dir, platformName, 'epics');
  if (!fs.existsSync(epicsDir)) return [];

  return fs
    .readdirSync(epicsDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => {
      const pitchPath = path.join(epicsDir, d.name, 'pitch.md');
      if (!fs.existsSync(pitchPath)) return null;
      const content = fs.readFileSync(pitchPath, 'utf8');
      const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);
      if (!fmMatch) return null;
      const fm = yaml.load(fmMatch[1]);
      return {
        dir: d.name,
        id: fm.id ?? d.name.split('-')[0],
        title: fm.title ?? d.name,
        status: fm.status ?? 'planned',
        phase: fm.phase ?? 'later',
      };
    })
    .filter(Boolean)
    .sort((a, b) => String(a.id).localeCompare(String(b.id)));
}

function platformFileExists(platformName, relPath) {
  return fs.existsSync(path.join(PLATFORMS_DIR, platformName, relPath));
}

export function buildSidebar(platforms) {
  return platforms.map((p) => {
    const epics = discoverEpics(p.name);
    const epicItems = epics.map((e) => ({
      label: `${e.id} · ${e.title}`,
      link: `/${p.name}/epics/${e.dir}/pitch/`,
      badge: phaseBadgeVariant[e.phase]
        ? { text: e.phase, variant: phaseBadgeVariant[e.phase] }
        : undefined,
    }));

    return {
      label: p.title || p.name,
      collapsed: true,
      items: [
        {
          label: 'Dashboard',
          link: `/${p.name}/dashboard/`,
          attrs: { style: 'font-weight: 600' },
        },
        {
          label: 'Business',
          items: [
            { slug: `${p.name}/business/vision` },
            { slug: `${p.name}/business/solution-overview` },
            ...(platformFileExists(p.name, 'business/process.md')
              ? [{ slug: `${p.name}/business/process` }]
              : []),
          ],
        },
        {
          label: 'Engineering',
          items: [
            {
              label: 'ADRs',
              collapsed: true,
              items: [
                { label: 'Decision Overviews', link: `/${p.name}/decisions/` },
                { label: 'ADRs', autogenerate: { directory: `${p.name}/decisions` } },
              ],
            },
            { slug: `${p.name}/engineering/blueprint` },
            { label: 'System Landscape', link: `/${p.name}/landscape/` },
            { slug: `${p.name}/engineering/domain-model` },
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
            { slug: `${p.name}/engineering/integrations` },
          ],
        },
        {
          label: 'Planning',
          items: [
            { slug: `${p.name}/planning/roadmap` },
            {
              label: 'Epics',
              collapsed: true,
              items: epicItems.length > 0
                ? epicItems
                : [{ label: 'Nenhum epic cadastrado', link: `/${p.name}/roadmap/` }],
            },
          ],
        },
        {
          label: 'Research',
          collapsed: true,
          autogenerate: { directory: `${p.name}/research` },
        },
      ],
    };
  });
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
