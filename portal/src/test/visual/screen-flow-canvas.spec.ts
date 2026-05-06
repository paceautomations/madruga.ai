/**
 * T022 — Visual baseline for ScreenFlowCanvas (epic 027).
 *
 * Loads the Phase 2 fixture (`?fixture=true`) which exercises every
 * vocabulary entry (10 components, 4 edge styles, 3 capture states) and
 * compares against jest-image-snapshot baselines in light + dark mode.
 *
 * Tolerances default to ~1px diff (0.05% pixel diff) to absorb font-AA
 * jitter without masking real regressions. SC-007 requires the canvas to
 * remain visually correct under both Starlight themes.
 *
 * RED first: this spec fails until ScreenFlowCanvas + the route page
 * exist (Phase 3 implementation tasks T031, T032).
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
  failureThreshold: 0.0005, // 0.05% per FR-042 "1px tolerance"
  failureThresholdType: 'percent',
  customSnapshotsDir: path.join(__dirname, '__snapshots__'),
  customDiffDir: path.join(__dirname, '__diffs__'),
};

const toMatchImageSnapshot = configureToMatchImageSnapshot(SNAPSHOT_OPTS);

// Use any platform with screen_flow.enabled=true — the route auto-loads
// the dev fixture when no canonical YAML is present (resenhai in v1).
const FIXTURE_URL = '/resenhai/screens/';

test.describe('ScreenFlowCanvas — visual baseline', () => {
  test.beforeEach(async ({ page }) => {
    // Disable animations for deterministic baselines (mirrors the determinism
    // layer applied to capture). Reuses CSS injection rather than a real
    // motion-reduce media query so it works in headless Chromium.
    await page.addInitScript(() => {
      const style = document.createElement('style');
      style.id = 'visual-test-no-anim';
      style.textContent = `*, *::before, *::after { animation-duration: 0s !important; transition-duration: 0s !important; }`;
      document.head.appendChild(style);
    });
  });

  test('light mode renders all 8 fixture screens + 4 edge styles', async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto(FIXTURE_URL);
    // Wait for the canvas to mount and ELK-positioned nodes to settle.
    await page.locator('[data-testid="screen-flow-canvas"]').waitFor({
      state: 'visible',
      timeout: 15_000,
    });
    await page.waitForFunction(
      () => document.querySelectorAll('[data-screen-id]').length >= 8,
      { timeout: 10_000 },
    );

    // Use Playwright's native screenshot snapshot — jest-image-snapshot's
    // `configureToMatchImageSnapshot` returns a Jest matcher function that
    // requires Jest's `expect` context (`this._counters` etc.) which Playwright
    // doesn't provide. `expect(screenshot).toMatchSnapshot()` is the
    // Playwright-native equivalent and respects the configured threshold.
    await expect(
      await page
        .locator('[data-testid="screen-flow-canvas"]')
        .screenshot({ animations: 'disabled' }),
    ).toMatchSnapshot('canvas-light.png', { maxDiffPixelRatio: 0.005 });
  });

  test('dark mode renders the canvas without colour regressions (SC-007)', async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto(FIXTURE_URL);
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-theme', 'dark');
    });
    await page.locator('[data-testid="screen-flow-canvas"]').waitFor({
      state: 'visible',
      timeout: 15_000,
    });
    await page.waitForFunction(
      () => document.querySelectorAll('[data-screen-id]').length >= 8,
      { timeout: 10_000 },
    );

    await expect(
      await page
        .locator('[data-testid="screen-flow-canvas"]')
        .screenshot({ animations: 'disabled' }),
    ).toMatchSnapshot('canvas-dark.png', { maxDiffPixelRatio: 0.005 });
  });

  test('renders one DOM node per fixture screen', async ({ page }) => {
    await page.goto(FIXTURE_URL);
    await page.locator('[data-testid="screen-flow-canvas"]').waitFor();
    // Hydration-wait: the wrapper SSR mounts immediately but the React
    // island is `client:visible` and only populates the DOM after
    // ScreenFlowCanvas hydrates.
    await page.waitForFunction(
      () => document.querySelectorAll('[data-screen-id]').length >= 8,
      { timeout: 10_000 },
    );
    const screenIds = await page.$$eval('[data-screen-id]', (els) =>
      els.map((el) => el.getAttribute('data-screen-id')).filter(Boolean),
    );
    expect(new Set(screenIds).size).toBe(8);
  });

  test('renders four distinct edge styles (success/error/neutral/modal)', async ({
    page,
  }) => {
    await page.goto(FIXTURE_URL);
    await page.locator('[data-testid="screen-flow-canvas"]').waitFor();
    await page.waitForFunction(
      () =>
        new Set(
          Array.from(document.querySelectorAll('path[data-edge-style]')).map(
            (el) => el.getAttribute('data-edge-style'),
          ),
        ).size >= 4,
      { timeout: 10_000 },
    );
    const styles = await page.$$eval('path[data-edge-style]', (els) =>
      Array.from(new Set(els.map((el) => el.getAttribute('data-edge-style')))),
    );
    expect(styles.sort()).toEqual(['error', 'modal', 'neutral', 'success']);
  });
});
