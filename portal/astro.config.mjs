// @ts-check
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import react from '@astrojs/react';
import mermaid from 'astro-mermaid';
import { LikeC4VitePlugin } from 'likec4/vite-plugin';
import { discoverPlatforms, buildSidebar } from './src/lib/platforms.mjs';

const platforms = discoverPlatforms();

// --- Eager symlink sync (runs at import time, before Starlight loader) ---
// Starlight's docs loader checks src/content/docs/ during config phase,
// before Vite's buildStart fires. We must create symlinks eagerly so the
// directory and its content exist when the loader first scans.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const docsDir = path.join(__dirname, 'src', 'content', 'docs');
const platformsDir = path.resolve(__dirname, '..', 'platforms');
const portalSections = ['business', 'engineering', 'decisions', 'research', 'planning', 'model'];

function syncPlatformSymlinks() {
  fs.mkdirSync(docsDir, { recursive: true });

  // Cleanup dangling symlinks (recursive one level into platform dirs)
  for (const entry of fs.readdirSync(docsDir)) {
    const entryPath = path.join(docsDir, entry);
    try {
      const stat = fs.lstatSync(entryPath);
      if (stat.isSymbolicLink() && !fs.existsSync(entryPath)) {
        fs.unlinkSync(entryPath);
      } else if (stat.isDirectory() && !stat.isSymbolicLink()) {
        for (const sub of fs.readdirSync(entryPath)) {
          const subPath = path.join(entryPath, sub);
          try {
            const subStat = fs.lstatSync(subPath);
            if (subStat.isSymbolicLink() && !fs.existsSync(subPath)) {
              fs.unlinkSync(subPath);
            }
          } catch { /* ignore */ }
        }
      }
    } catch { /* ignore */ }
  }

  // Create per-section symlinks for each platform
  for (const p of platforms) {
    const platformDocsDir = path.join(docsDir, p.name);
    fs.mkdirSync(platformDocsDir, { recursive: true });

    for (const section of portalSections) {
      const target = path.join(platformsDir, p.name, section);
      const link = path.join(platformDocsDir, section);

      if (fs.existsSync(target) && !fs.existsSync(link)) {
        fs.symlinkSync(target, link, 'dir');
      }
    }

    // Symlink platform.yaml for discoverability
    const yamlTarget = path.join(platformsDir, p.name, 'platform.yaml');
    const yamlLink = path.join(platformDocsDir, 'platform.yaml');
    if (fs.existsSync(yamlTarget) && !fs.existsSync(yamlLink)) {
      fs.symlinkSync(yamlTarget, yamlLink);
    }

    // Symlink only pitch.md files from epics (not SpecKit working files)
    const epicsDir = path.join(platformsDir, p.name, 'epics');
    if (fs.existsSync(epicsDir)) {
      const portalEpicsDir = path.join(platformDocsDir, 'epics');
      fs.mkdirSync(portalEpicsDir, { recursive: true });

      for (const epicEntry of fs.readdirSync(epicsDir)) {
        const epicSrc = path.join(epicsDir, epicEntry);
        if (!fs.statSync(epicSrc).isDirectory()) continue;

        const pitchSrc = path.join(epicSrc, 'pitch.md');
        if (fs.existsSync(pitchSrc)) {
          const epicDocsDir = path.join(portalEpicsDir, epicEntry);
          fs.mkdirSync(epicDocsDir, { recursive: true });
          const pitchLink = path.join(epicDocsDir, 'pitch.md');
          if (!fs.existsSync(pitchLink)) {
            fs.symlinkSync(pitchSrc, pitchLink);
          }
        }
      }
    }
  }
}

// Run eagerly so docs/ exists before Starlight loader scans
syncPlatformSymlinks();

// Vite plugin re-runs the same sync on buildStart (handles watch-mode changes)
function platformSymlinksPlugin() {
  return {
    name: 'platform-symlinks',
    buildStart() {
      syncPlatformSymlinks();
    },
  };
}

export default defineConfig({
  site: 'https://madruga.ai',
  vite: {
    resolve: { preserveSymlinks: true },
    esbuild: {
      // Ensure consistent JSX runtime for likec4:react/* virtual modules
      jsx: 'automatic',
      jsxImportSource: 'react',
    },
    server: {
      watch: {
        // Follow symlinks into platforms/ so markdown edits trigger HMR
        followSymlinks: true,
        // Explicitly watch platforms dir (symlink targets live outside portal/)
        ignored: ['!**/platforms/**'],
      },
      fs: {
        // Allow Vite to serve files from platforms/ (outside portal root)
        allow: ['..'],
      },
    },
    plugins: [
      platformSymlinksPlugin(),
      LikeC4VitePlugin({
        workspace: '../platforms',
      }),
    ],
  },
  integrations: [
    starlight({
      title: 'Madruga-AI',
      logo: {
        src: './src/assets/logo.png',
        alt: 'madruga.ai',
      },
      favicon: '/favicon.png',
      routeMiddleware: './src/routeData.ts',
      customCss: ['./src/styles/custom.css'],
      components: {
        Header: './src/components/CustomHeader.astro',
        NotFound: './src/components/NotFound.astro',
      },
      head: [
        { tag: 'script', attrs: { src: '/sidebar-toggle.js', defer: true } },
        { tag: 'script', attrs: { src: '/svg-pan-zoom.min.js' } },
        { tag: 'script', attrs: { src: '/mermaid-interactive.js', defer: true } },
      ],
      sidebar: buildSidebar(platforms),
    }),
    react(),
    mermaid(),
  ],
});
