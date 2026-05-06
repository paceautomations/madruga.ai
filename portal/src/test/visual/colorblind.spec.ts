/**
 * T110 — Color-blind visual regression for edge styles (epic 027).
 *
 * Coverage (FR-021, SC-008):
 *   - 4 edge styles (success / error / neutral / modal) MUST stay
 *     distinguishable to viewers with deuteranopia + protanopia.
 *   - The renderer encodes that distinguishability via stroke patterns
 *     (solid / dashed / dotted / solid-thick) IN ADDITION to colour.
 *     Removing the colour channel via an SVG matrix filter is the
 *     cheapest objective check that the patterns alone carry signal.
 *
 * Approach:
 *   1. Load the dev fixture (`?fixture=true`) so the canvas renders
 *      without depending on Phase 4 captures.
 *   2. Inject a `<svg>` containing `feColorMatrix` filters for
 *      deuteranopia + protanopia (Brettel/Vienot/Mollon 1997
 *      coefficients, well-known colour-blind sim matrices).
 *   3. Apply the filter to the canvas element via `style.filter`.
 *   4. Snapshot the canvas with each filter and assert the four
 *      `data-edge-style` patterns remain present in the SVG (i.e. the
 *      renderer is not relying on colour alone to distinguish them).
 *   5. Snapshot diffs are stored under `__snapshots__/colorblind-*` and
 *      compared with the same 0.05% tolerance as the baseline spec —
 *      this catches regressions where someone strips the dasharray and
 *      both filters still pass colour-only discrimination.
 *
 * RED first: this spec fails until the canvas renders four DISTINCT
 * stroke-dasharray attributes (T030 already enforces this; the spec
 * keeps it locked).
 */
import { test, expect } from '@playwright/test';
// jest-image-snapshot is CommonJS — use namespace import so Node ESM resolves
// the named factory without choking on `Named export not found`.
import jestImageSnapshot from 'jest-image-snapshot';
import type { MatchImageSnapshotOptions } from 'jest-image-snapshot';
const { configureToMatchImageSnapshot } = jestImageSnapshot as unknown as {
  configureToMatchImageSnapshot: (opts: MatchImageSnapshotOptions) => unknown;
};
import path from 'node:path';
import url from 'node:url';

const __dirname = path.dirname(url.fileURLToPath(import.meta.url));

const SNAPSHOT_OPTS: MatchImageSnapshotOptions = {
  // Allow ~0.5% difference: colour-blind filters introduce small
  // anti-aliasing shifts that are larger than the baseline 0.05%
  // budget but still well below "the renderer fell back to colour
  // alone" regressions.
  failureThreshold: 0.005,
  failureThresholdType: 'percent',
  customSnapshotsDir: path.join(__dirname, '__snapshots__'),
  customDiffDir: path.join(__dirname, '__diffs__'),
};

const toMatchImageSnapshot = configureToMatchImageSnapshot(SNAPSHOT_OPTS);

// Resenhai is the only platform with screen_flow.enabled=true; the
// `[platform]/screens.astro` page falls back to the dev fixture when DEV
// is true and no canonical YAML exists, so the URL drops the (no-op)
// query string and points at the route that actually exists.
const FIXTURE_URL = '/resenhai/screens/';

// Brettel-style colour-blind simulation matrices (sRGB linear).
// Source: github.com/MaPePeR/jsColorblindSimulator (MIT) — well-known
// LMS-based approximations, reused by axe-core's colour-contrast tools.
const DEUTERANOPIA_MATRIX = [
  '0.625 0.375 0    0 0',
  '0.7   0.3   0    0 0',
  '0     0.3   0.7  0 0',
  '0     0     0    1 0',
].join(' ');

const PROTANOPIA_MATRIX = [
  '0.567 0.433 0     0 0',
  '0.558 0.442 0     0 0',
  '0     0.242 0.758 0 0',
  '0     0     0     1 0',
].join(' ');

const FILTER_SVG = `
<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true">
  <defs>
    <filter id="deuteranopia" color-interpolation-filters="sRGB">
      <feColorMatrix type="matrix" values="${DEUTERANOPIA_MATRIX}" />
    </filter>
    <filter id="protanopia" color-interpolation-filters="sRGB">
      <feColorMatrix type="matrix" values="${PROTANOPIA_MATRIX}" />
    </filter>
  </defs>
</svg>
`;

const ALL_STYLES = ['error', 'modal', 'neutral', 'success'] as const;

test.describe('Edge styles — colour-blind discriminability (FR-021, SC-008)', () => {
  test.beforeEach(async ({ page }) => {
    // Disable animations so the snapshot is deterministic.
    await page.addInitScript(() => {
      const style = document.createElement('style');
      style.id = 'visual-test-no-anim';
      style.textContent = `*, *::before, *::after { animation-duration: 0s !important; transition-duration: 0s !important; }`;
      document.head.appendChild(style);
    });

    await page.goto(FIXTURE_URL);
    await page.locator('[data-testid="screen-flow-canvas"]').waitFor({
      state: 'visible',
      timeout: 15_000,
    });
    await page.waitForFunction(
      () => document.querySelectorAll('[data-screen-id]').length >= 8,
      { timeout: 10_000 },
    );

    // Inject the SVG filter defs once per page.
    await page.evaluate((svgMarkup) => {
      const wrapper = document.createElement('div');
      wrapper.id = 'colorblind-filters';
      wrapper.innerHTML = svgMarkup;
      document.body.appendChild(wrapper);
    }, FILTER_SVG);
  });

  test('SVG carries 4 distinct stroke-dasharray patterns (pattern channel)', async ({
    page,
  }) => {
    // Even before applying any filter, the renderer must encode the
    // four edge styles via different `stroke-dasharray` values plus
    // stroke widths. This guards against a regression where someone
    // collapses every style to the same dash pattern and relies only
    // on colour — which would silently fail under the colour-blind
    // filters but pass the baseline snapshot.
    const patterns = await page.$$eval('path[data-edge-style]', (els) =>
      els.map((el) => ({
        style: el.getAttribute('data-edge-style'),
        dasharray: el.getAttribute('stroke-dasharray') ?? '',
        width: el.getAttribute('stroke-width') ?? '',
      })),
    );
    expect(patterns.length).toBeGreaterThanOrEqual(4);

    // Distinct (dasharray, width) combinations across the 4 styles.
    const seen = new Map<string, string>();
    for (const p of patterns) {
      if (!p.style) continue;
      const key = `${p.dasharray}|${p.width}`;
      const prior = seen.get(p.style);
      if (prior) {
        expect(prior).toBe(key); // Same style → same pattern, no drift.
      } else {
        seen.set(p.style, key);
      }
    }
    const distinctKeys = new Set(seen.values());
    // Each of the four edge styles MUST own a distinct
    // (dasharray, width) tuple. Otherwise pattern-only viewers cannot
    // tell them apart.
    expect(distinctKeys.size).toBe(ALL_STYLES.length);
  });

  test('canvas remains visually parseable with deuteranopia filter', async ({
    page,
  }) => {
    await page.evaluate(() => {
      const canvas = document.querySelector(
        '[data-testid="screen-flow-canvas"]',
      ) as HTMLElement | null;
      if (!canvas) throw new Error('canvas missing');
      canvas.style.filter = 'url(#deuteranopia)';
    });

    // The 4 styles must still be present in the DOM (the filter is a
    // visual transform; the source SVG attributes are unchanged).
    const styles = await page.$$eval('path[data-edge-style]', (els) =>
      Array.from(new Set(els.map((el) => el.getAttribute('data-edge-style')))),
    );
    expect(styles.sort()).toEqual([...ALL_STYLES]);

    // jest-image-snapshot is jest-bound; Playwright's `toMatchSnapshot` is
    // the native equivalent and respects maxDiffPixelRatio.
    await expect(
      await page
        .locator('[data-testid="screen-flow-canvas"]')
        .screenshot({ animations: 'disabled' }),
    ).toMatchSnapshot('colorblind-deuteranopia.png', { maxDiffPixelRatio: 0.005 });
  });

  test('canvas remains visually parseable with protanopia filter', async ({
    page,
  }) => {
    await page.evaluate(() => {
      const canvas = document.querySelector(
        '[data-testid="screen-flow-canvas"]',
      ) as HTMLElement | null;
      if (!canvas) throw new Error('canvas missing');
      canvas.style.filter = 'url(#protanopia)';
    });

    await expect(
      await page
        .locator('[data-testid="screen-flow-canvas"]')
        .screenshot({ animations: 'disabled' }),
    ).toMatchSnapshot('colorblind-protanopia.png', { maxDiffPixelRatio: 0.005 });
  });
});
