// One-shot screenshot capture for T134 (epic 027 phase 12).
// Reads URLs from platforms/madruga-ai/platform.yaml `testing.urls` (type: frontend),
// writes PNGs into smoke-shots/, and validates content is NOT placeholder.
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const URLS = [
  {
    url: 'http://localhost:4321',
    label: 'portal-home',
    expectContains: ['madruga'],
  },
  {
    url: 'http://localhost:4321/madruga-ai/business/vision/',
    label: 'madruga-ai-vision',
    expectContains: ['vision', 'madruga'],
  },
];

const REPO_ROOT = resolve(process.cwd(), '..');
const OUT_DIR = resolve(
  REPO_ROOT,
  'platforms/madruga-ai/epics/027-screen-flow-canvas/smoke-shots',
);
mkdirSync(OUT_DIR, { recursive: true });

// Look only for "placeholder content" markers — NOT the CSS `::placeholder`
// pseudo-class or HTML `placeholder=""` attribute, both of which are
// legitimate and appear in the rendered HTML (Pagefind reset / form inputs).
const PLACEHOLDER_MARKERS = [
  'lorem ipsum',
  'todo: write content',
  'tktk',
  'coming soon',
  'this is a placeholder',
  'content placeholder',
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();

let exitCode = 0;
for (const entry of URLS) {
  try {
    const resp = await page.goto(entry.url, { waitUntil: 'networkidle', timeout: 30000 });
    const status = resp ? resp.status() : 0;
    const html = await page.content();
    const lower = html.toLowerCase();

    const png = `${OUT_DIR}/${entry.label}.png`;
    await page.screenshot({ path: png, fullPage: false });

    const placeholders = PLACEHOLDER_MARKERS.filter((m) => lower.includes(m.toLowerCase()));
    const expectMissing = entry.expectContains.filter((c) => !lower.includes(c.toLowerCase()));

    const ok = status === 200 && placeholders.length === 0 && expectMissing.length === 0;
    console.log(JSON.stringify({
      url: entry.url,
      label: entry.label,
      status,
      png,
      bytes: html.length,
      placeholders,
      expect_missing: expectMissing,
      ok,
    }));
    if (!ok) exitCode = 1;
  } catch (err) {
    console.log(JSON.stringify({ url: entry.url, label: entry.label, error: String(err) }));
    exitCode = 1;
  }
}

await ctx.close();
await browser.close();
process.exit(exitCode);
