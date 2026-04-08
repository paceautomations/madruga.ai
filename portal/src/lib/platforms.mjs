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
 * Load pipeline-status.json (fresh read every call — no stale cache in dev).
 */
function findStatusFile() {
  // Try __dirname-relative first (works in dev mode when __dirname = src/lib)
  const fromDirname = path.join(__dirname, '..', 'data', 'pipeline-status.json');
  if (fs.existsSync(fromDirname)) return fromDirname;
  // Fallback for build/prerender (where __dirname = dist/.prerender/chunks)
  const fromCwd = path.join(process.cwd(), 'src', 'data', 'pipeline-status.json');
  if (fs.existsSync(fromCwd)) return fromCwd;
  return null;
}

export function loadStatusData() {
  try {
    const statusPath = findStatusFile();
    if (!statusPath) return null;
    return JSON.parse(fs.readFileSync(statusPath, 'utf8'));
  } catch {
    return null;
  }
}

/**
 * Load epic status from pipeline-status.json (DB source of truth).
 * Returns a map of epicId → { status, ... } for the given platform.
 */
function loadDbEpicStatus(platformName) {
  const statusData = loadStatusData();
  if (!statusData) return {};
  const platform = (statusData.platforms || []).find((p) => p.id === platformName);
  if (!platform?.l2?.epics) return {};
  const map = {};
  for (const e of platform.l2.epics) {
    map[e.id] = e;
  }
  return map;
}

/**
 * Discover epics for a platform by reading pitch.md frontmatter,
 * enriched with DB status from pipeline-status.json.
 * Returns sorted array of { dir, id, title, status, phase }.
 */
export function discoverEpics(platformName, platformsDir) {
  const dir = platformsDir ?? PLATFORMS_DIR;
  const epicsDir = path.join(dir, platformName, 'epics');
  if (!fs.existsSync(epicsDir)) return [];

  const dbEpics = loadDbEpicStatus(platformName);

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
      const epicKey = fm.id != null ? String(fm.id) : d.name.split('-')[0];
      // DB status takes precedence over frontmatter
      const dbEpic = dbEpics[d.name] || dbEpics[epicKey];
      const effectiveStatus = dbEpic?.status ?? fm.status ?? 'planned';
      return {
        dir: d.name,
        id: epicKey,
        title: fm.title ?? d.name,
        status: effectiveStatus,
        phase: effectiveStatus === 'shipped' ? null
          : effectiveStatus === 'in_progress' ? 'now'
          : (fm.phase ?? 'later'),
        delivered_at: fm.delivered_at instanceof Date
          ? fm.delivered_at.toISOString().slice(0, 10)
          : (fm.delivered_at ?? null),
      };
    })
    .filter(Boolean)
    .sort((a, b) => {
      const aShipped = a.status === 'shipped';
      const bShipped = b.status === 'shipped';
      if (aShipped && bShipped) {
        const dc = String(b.delivered_at ?? '').localeCompare(String(a.delivered_at ?? ''));
        return dc !== 0 ? dc : String(b.id).localeCompare(String(a.id));
      }
      if (aShipped !== bShipped) return aShipped ? -1 : 1;
      return String(b.id).localeCompare(String(a.id));
    });
}

export function buildSidebar(platforms) {
  return platforms.map((p) => {
    const epics = discoverEpics(p.name);
    const epicItems = epics.map((e) => ({
      label: `${e.id} · ${e.title}`,
      link: `/${p.name}/epics/${e.dir}/pitch/`,
      badge: e.phase && phaseBadgeVariant[e.phase]
        ? { text: e.phase, variant: phaseBadgeVariant[e.phase] }
        : undefined,
    }));

    return {
      label: p.title || p.name,
      collapsed: false,
      items: [
        {
          label: 'Control Panel',
          link: `/${p.name}/control-panel/`,
          attrs: { style: 'font-weight: 600' },
        },
        {
          label: 'Business',
          autogenerate: { directory: `${p.name}/business` },
        },
        {
          label: 'Engineering',
          autogenerate: { directory: `${p.name}/engineering` },
        },
        {
          label: 'ADRs',
          collapsed: true,
          items: [
            { label: 'Decision Overviews', link: `/${p.name}/decisions/` },
            { label: 'ADRs', collapsed: true, autogenerate: { directory: `${p.name}/decisions` } },
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
