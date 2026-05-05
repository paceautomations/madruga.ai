/**
 * T081 — Hotspot interaction visual spec (epic 027).
 *
 * Verifies the runtime invariants behind FR-025, FR-026 and SC-004:
 *   - Pressing `H` toggles hotspot visibility in <50ms (measured via the
 *     Performance API around the keydown event).
 *   - Clicking a numbered hotspot animates the corresponding edge AND
 *     centres `fitView` on the destination screen — total wall-clock
 *     budget is <700ms.
 *
 * Does NOT compare screenshots (that's covered by
 * `screen-flow-canvas.spec.ts`). The intent here is to prove the
 * interaction budget without coupling the test to pixel-level diffs.
 *
 * RED first: this spec fails until Hotspot is wired into ScreenNode +
 * ScreenFlowCanvas (T082-T085).
 */
import { test, expect } from '@playwright/test';

const FIXTURE_URL = '/madruga-ai/screens/?fixture=true';

test.describe('Hotspot interaction', () => {
  test.beforeEach(async ({ page }) => {
    // Disable CSS transitions/animations so duration measurements reflect
    // pure handler cost, not animation playback.
    await page.addInitScript(() => {
      const style = document.createElement('style');
      style.id = 'visual-test-no-anim';
      style.textContent = `*, *::before, *::after { animation-duration: 0s !important; transition-duration: 0s !important; }`;
      document.head.appendChild(style);
    });
    await page.goto(FIXTURE_URL);
    await page
      .locator('[data-testid="screen-flow-canvas"]')
      .waitFor({ state: 'visible', timeout: 15_000 });
    await page.waitForFunction(
      () => document.querySelectorAll('[data-screen-id]').length >= 8,
      { timeout: 10_000 },
    );
    // Ensure at least one hotspot was rendered before we interact.
    await page.waitForFunction(
      () => document.querySelectorAll('[data-hotspot-flow]').length >= 1,
      { timeout: 10_000 },
    );
  });

  test('renders numbered hotspots over the canvas (FR-024)', async ({ page }) => {
    const count = await page.locator('[data-hotspot-flow]').count();
    expect(count).toBeGreaterThanOrEqual(1);
    const firstBadgeText = await page
      .locator('[data-hotspot-flow]')
      .first()
      .innerText();
    expect(firstBadgeText.trim()).toMatch(/^\d+$/);
  });

  test('pressing H toggles hotspot visibility within 50ms (FR-025)', async ({
    page,
  }) => {
    // Move focus into the canvas so the keydown is captured.
    await page.locator('[data-testid="screen-flow-canvas"]').click();

    // First press hides — measure wall clock between dispatch and the
    // observed visibility flip.
    const hideMs = await page.evaluate(async () => {
      const start = performance.now();
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'h' }));
      // Allow React to flush within a single rAF tick.
      await new Promise<void>((r) => requestAnimationFrame(() => r()));
      const visible = document
        .querySelector('[data-hotspot-flow]')
        ?.getAttribute('data-visible');
      const end = performance.now();
      return { duration: end - start, visible };
    });
    expect(hideMs.duration).toBeLessThan(50);
    expect(hideMs.visible).toBe('false');

    // Second press shows.
    const showMs = await page.evaluate(async () => {
      const start = performance.now();
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'h' }));
      await new Promise<void>((r) => requestAnimationFrame(() => r()));
      const visible = document
        .querySelector('[data-hotspot-flow]')
        ?.getAttribute('data-visible');
      const end = performance.now();
      return { duration: end - start, visible };
    });
    expect(showMs.duration).toBeLessThan(50);
    expect(showMs.visible).toBe('true');
  });

  test('clicking a hotspot centres camera in <700ms (FR-026, SC-004)', async ({
    page,
  }) => {
    const totalMs = await page.evaluate(async () => {
      const hotspot = document.querySelector(
        '[data-hotspot-flow]',
      ) as HTMLElement | null;
      if (!hotspot) throw new Error('no hotspot present');
      const target = hotspot.getAttribute('data-hotspot-to');
      const start = performance.now();
      hotspot.click();
      // Wait for the camera transition to complete. We poll the data
      // attribute that ScreenFlowCanvas sets on the active flow target.
      const deadline = start + 1500;
      while (performance.now() < deadline) {
        const settled = document
          .querySelector('[data-testid="screen-flow-canvas"]')
          ?.getAttribute('data-active-target');
        if (settled === target) break;
        await new Promise<void>((r) => requestAnimationFrame(() => r()));
      }
      return performance.now() - start;
    });
    expect(totalMs).toBeLessThan(700);
  });
});
