/**
 * T111 — Accessibility audit + keyboard-nav E2E (epic 027).
 *
 * Coverage (FR-019, FR-020, SC-008):
 *   - axe-core (`@axe-core/playwright`) sweeps the rendered canvas at
 *     `/[platform]/screens?fixture=true` and asserts ZERO P1 violations
 *     (impact "critical" / "serious"). P2 (moderate / minor) findings
 *     are surfaced as console warnings to keep the gate honest without
 *     blocking on cosmetic Starlight defaults.
 *   - Tab order: from an initial focus on the canvas root, repeated Tab
 *     keypresses must traverse `[data-screen-id]` ScreenNodes — proves
 *     `tabIndex=0` flows downstream of xyflow's container.
 *   - Enter on a focused hotspot must activate it: we verify the canvas
 *     transitions `data-active-target` to the flow's destination
 *     within the FR-026 budget (1500ms upper bound — the spec only
 *     cares that keyboard activation works, not that it's <700ms; that
 *     budget is enforced by hotspot-interaction.spec.ts).
 *
 * Non-goals: this spec does NOT cover colour-blind filters (covered by
 * `colorblind.spec.ts`) nor visual snapshots (covered by
 * `screen-flow-canvas.spec.ts`).
 */
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const FIXTURE_URL = '/resenhai/screens/';

test.describe('Screen-flow canvas — accessibility (FR-019, FR-020, SC-008)', () => {
  test.beforeEach(async ({ page }) => {
    // Pin animations to zero — axe occasionally reports motion-related
    // failures on hover transitions that are not actionable here.
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
  });

  test('axe-core scan reports zero critical/serious violations on the canvas', async ({
    page,
  }, testInfo) => {
    // Restrict the scan to the canvas region + its ancestors so we
    // don't fail on Starlight chrome we don't control. Tags are the
    // standard WCAG 2.1 AA + best-practice surface that maps to "P1".
    const results = await new AxeBuilder({ page })
      .include('[data-testid="screen-flow-canvas"]')
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    // Surface P2 findings via the test attachments so the developer
    // can triage them post-mortem without breaking the gate.
    const p1 = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );
    const p2 = results.violations.filter(
      (v) => v.impact === 'moderate' || v.impact === 'minor',
    );
    if (p2.length > 0) {
      await testInfo.attach('axe-p2-findings', {
        body: JSON.stringify(p2, null, 2),
        contentType: 'application/json',
      });
    }

    expect(
      p1,
      `axe-core P1 violations:\n${JSON.stringify(p1, null, 2)}`,
    ).toEqual([]);
  });

  test('Tab cycles focus across ScreenNode and Hotspot elements (FR-019)', async ({
    page,
  }) => {
    // Seed focus on the canvas wrapper. From there we expect the
    // browser's native sequential focus to walk into ScreenNodes
    // (tabIndex=0) and then into Hotspots (tabIndex=0 inside each).
    await page.locator('[data-testid="screen-flow-canvas"]').focus();

    const visited = new Set<string>();
    const MAX_TABS = 25;
    for (let i = 0; i < MAX_TABS; i++) {
      await page.keyboard.press('Tab');
      const tag = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el) return '';
        if (el.matches('[data-screen-id]')) return `screen:${el.getAttribute('data-screen-id')}`;
        if (el.matches('[data-hotspot-flow]')) return `hotspot:${el.getAttribute('data-hotspot-flow')}`;
        return '';
      });
      if (tag) visited.add(tag);
    }

    const screensVisited = Array.from(visited).filter((t) => t.startsWith('screen:'));
    const hotspotsVisited = Array.from(visited).filter((t) => t.startsWith('hotspot:'));

    // At least one ScreenNode and one Hotspot must be reachable purely
    // via keyboard. If this regresses, FR-019 is broken.
    expect(screensVisited.length).toBeGreaterThanOrEqual(1);
    expect(hotspotsVisited.length).toBeGreaterThanOrEqual(1);
  });

  test('Enter on a focused hotspot activates the flow (FR-019 + FR-026)', async ({
    page,
  }) => {
    // Walk Tab until a hotspot is focused, then press Enter and wait
    // for the canvas to mark `data-active-target`.
    await page.locator('[data-testid="screen-flow-canvas"]').focus();
    let focused = false;
    for (let i = 0; i < 30; i++) {
      await page.keyboard.press('Tab');
      const isHotspot = await page.evaluate(() =>
        document.activeElement?.matches('[data-hotspot-flow]') ?? false,
      );
      if (isHotspot) {
        focused = true;
        break;
      }
    }
    expect(focused, 'expected Tab to land on a hotspot within 30 presses').toBe(true);

    const expectedTarget = await page.evaluate(() =>
      (document.activeElement as HTMLElement | null)?.getAttribute('data-hotspot-to'),
    );
    expect(expectedTarget, 'focused hotspot must declare data-hotspot-to').toBeTruthy();

    await page.keyboard.press('Enter');

    // Generous upper bound — the 700 ms budget is enforced elsewhere.
    await page.waitForFunction(
      (target) =>
        document
          .querySelector('[data-testid="screen-flow-canvas"]')
          ?.getAttribute('data-active-target') === target,
      expectedTarget,
      { timeout: 1500 },
    );
  });

  test('every ScreenNode exposes an aria-label citing its screen id (FR-020)', async ({
    page,
  }) => {
    const labels = await page.$$eval('[data-screen-id]', (els) =>
      els.map((el) => ({
        id: el.getAttribute('data-screen-id'),
        label: el.getAttribute('aria-label') ?? '',
      })),
    );
    expect(labels.length).toBeGreaterThanOrEqual(8);
    for (const { id, label } of labels) {
      expect(label, `ScreenNode ${id} missing aria-label`).toMatch(/.+/);
      expect(label.toLowerCase()).toContain(String(id).toLowerCase());
    }
  });

  test('every visible Hotspot exposes an aria-label citing its destination', async ({
    page,
  }) => {
    const data = await page.$$eval('[data-hotspot-flow]', (els) =>
      els.map((el) => ({
        to: el.getAttribute('data-hotspot-to'),
        label: el.getAttribute('aria-label') ?? '',
        visible: el.getAttribute('data-visible'),
      })),
    );
    expect(data.length).toBeGreaterThanOrEqual(1);
    for (const { to, label, visible } of data) {
      // Hidden hotspots are still in the DOM but get aria-hidden=true;
      // we still want the label populated for when they re-appear.
      expect(label, `Hotspot to=${to} missing aria-label`).toMatch(/Vai para tela/);
      expect(label).toContain(String(to));
      expect(['true', 'false']).toContain(visible);
    }
  });
});
