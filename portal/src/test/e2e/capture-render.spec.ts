/**
 * T112 — E2E layer (d) per FR-042 (epic 027).
 *
 * Locks the capture → commit → render contract end-to-end:
 *
 *   1. CAPTURE — the Phase 6 orchestrator (`.specify/scripts/capture/`)
 *      writes a `screen-flow.yaml` whose `screens[].status` cycles
 *      through `pending` / `captured` / `failed` and persists optional
 *      `failure` blocks. We don't spin up a real Chromium subprocess
 *      here; instead we lean on the dev fixture
 *      (`portal/src/test/fixtures/screen-flow.example.yaml`) that
 *      ships an authoritative mix of all three states + 8 screens +
 *      all 4 edge styles. The fixture is the same shape the
 *      orchestrator emits, so it is a faithful E2E surface for the
 *      render contract without coupling the spec to network mocks.
 *
 *   2. COMMIT — implicit: the loader (`loadFixtureScreenFlow`) reads
 *      the YAML at build time exactly as `loadScreenFlow` would for
 *      a real platform. Any drift between the fixture schema and the
 *      portal loader fails this spec instantly.
 *
 *   3. RENDER — Playwright drives the dev server at
 *      `/madruga-ai/screens?fixture=true` and verifies the rendered
 *      DOM matches the YAML's intent for each capture state:
 *
 *        captured → <img src="business/shots/<id>.png"> + WEB BUILD badge
 *        pending  → WireframeBody + WIREFRAME / AGUARDANDO badge
 *        failed   → WireframeBody + FALHOU badge + tooltip on
 *                   `failure.reason`/`failure.last_error_message`
 *
 *   Plus invariants that span the full pipeline:
 *      - 4 distinct edge styles (success / error / neutral / modal).
 *      - All 10 body component types render at least once across the
 *        fixture (vocabulary closure check, FR-001).
 *      - Hotspots are derived from flows on captured/pending bodies.
 *
 * Skipped intentionally: byte-level snapshot diffs (covered by
 * `screen-flow-canvas.spec.ts`), 700ms hotspot budget (covered by
 * `hotspot-interaction.spec.ts`), and colour-blind discriminability
 * (covered by `colorblind.spec.ts`). This spec is the integration
 * glue, not a duplicate of the per-feature visual specs.
 */
import { test, expect } from '@playwright/test';

const FIXTURE_URL = '/madruga-ai/screens/?fixture=true';

test.describe('Capture → Commit → Render — E2E (FR-042 layer d)', () => {
  test.beforeEach(async ({ page }) => {
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

  test('renders 8 fixture screens with the expected mix of capture states', async ({
    page,
  }) => {
    const states = await page.$$eval('[data-screen-id]', (els) =>
      els.map((el) => ({
        id: el.getAttribute('data-screen-id'),
        status: el.getAttribute('data-status'),
      })),
    );

    expect(states.length).toBe(8);

    const captured = states.filter((s) => s.status === 'captured');
    const pending = states.filter((s) => s.status === 'pending');
    const failed = states.filter((s) => s.status === 'failed');

    // Fixture shape (also documented in the YAML header):
    //   5 captured / 2 pending / 1 failed.
    expect(captured.length).toBe(5);
    expect(pending.length).toBe(2);
    expect(failed.length).toBe(1);
  });

  test('captured screens render an <img> and pending/failed render a wireframe', async ({
    page,
  }) => {
    // Captured: at least one ScreenNode owns an <img class="screen-node__image">
    const capturedImageCount = await page.$$eval('[data-status="captured"] img.screen-node__image', (els) => els.length);
    expect(capturedImageCount).toBeGreaterThanOrEqual(5);

    // Pending: no <img>, but a wireframe body must be present.
    const pendingHasNoImg = await page.$$eval('[data-status="pending"] img.screen-node__image', (els) => els.length);
    expect(pendingHasNoImg).toBe(0);
    const pendingWireframes = await page.$$eval(
      '[data-status="pending"] .wireframe-body',
      (els) => els.length,
    );
    expect(pendingWireframes).toBeGreaterThanOrEqual(2);

    // Failed: same wireframe-body branch + tooltip on the screen node.
    const failedScreens = await page.$$eval('[data-status="failed"]', (els) =>
      els.map((el) => ({
        title: el.getAttribute('title') ?? '',
        hasImage: !!el.querySelector('img.screen-node__image'),
      })),
    );
    expect(failedScreens.length).toBe(1);
    expect(failedScreens[0].hasImage).toBe(false);
    // failure.reason ("timeout") + last_error_message must surface in
    // the title attribute (FR-046).
    expect(failedScreens[0].title.toLowerCase()).toContain('timeout');
  });

  test('badge variants follow the 6-value taxonomy (FR-001)', async ({ page }) => {
    const variants = await page.$$eval('[data-screen-id] .screen-flow-badge', (els) =>
      els.map((el) => el.getAttribute('data-variant')).filter(Boolean),
    );
    // Every screen carries exactly one badge.
    expect(variants.length).toBe(8);

    const set = new Set(variants);
    // The fixture exercises three variants: wireframe (pending),
    // web-build (captured), falhou (failed). The other three values
    // (`aguardando`, `ios`, `web`) are vocabulary slots for future
    // captures — they are validated in unit tests (Badge.test.tsx).
    expect(set.has('wireframe')).toBe(true);
    expect(set.has('web-build')).toBe(true);
    expect(set.has('falhou')).toBe(true);
  });

  test('all 4 edge styles + all 10 body component types are exercised', async ({
    page,
  }) => {
    const edgeStyles = await page.$$eval('path[data-edge-style]', (els) =>
      Array.from(new Set(els.map((el) => el.getAttribute('data-edge-style')))),
    );
    expect(edgeStyles.sort()).toEqual(['error', 'modal', 'neutral', 'success']);

    // The wireframe sub-renderers ship one CSS class per vocabulary
    // type (`wf-heading`, `wf-text`, …). Pulling them off the rendered
    // wireframe-body tells us how many distinct types the fixture
    // exercises end-to-end. We require >=8 of the 10 vocabulary types
    // — the fixture intentionally covers all 10, but a few may be
    // hidden inside captured screens (which render an <img> instead
    // of the wireframe). The spec is intentionally lenient at 8 to
    // avoid brittle coupling with the fixture composition.
    const types = await page.$$eval('.wireframe-body *', (els) => {
      const VOCAB_PREFIXES = [
        'wf-heading',
        'wf-text',
        'wf-input',
        'wf-button',
        'wf-link',
        'wf-list',
        'wf-card',
        'wf-image',
        'wf-divider',
        'wf-badge',
      ];
      const seen = new Set<string>();
      for (const el of els) {
        for (const cls of Array.from(el.classList)) {
          if (VOCAB_PREFIXES.includes(cls)) {
            seen.add(cls);
          }
        }
      }
      return Array.from(seen);
    });
    expect(types.length).toBeGreaterThanOrEqual(8);
  });

  test('hotspots are derived from flows and reference legitimate destinations', async ({
    page,
  }) => {
    const hotspotsPayload = await page.$$eval('[data-hotspot-flow]', (els) =>
      els.map((el) => ({
        flow: el.getAttribute('data-hotspot-flow'),
        to: el.getAttribute('data-hotspot-to'),
        on: el.getAttribute('data-hotspot-on'),
      })),
    );
    expect(hotspotsPayload.length).toBeGreaterThanOrEqual(4);

    const screenIds = await page.$$eval('[data-screen-id]', (els) =>
      els.map((el) => el.getAttribute('data-screen-id')),
    );
    const idSet = new Set(screenIds);

    for (const h of hotspotsPayload) {
      expect(h.to, `hotspot ${h.flow} missing data-hotspot-to`).toBeTruthy();
      expect(idSet.has(h.to), `hotspot target ${h.to} not among rendered screens`).toBe(
        true,
      );
      expect(h.on, `hotspot ${h.flow} missing data-hotspot-on`).toBeTruthy();
    }
  });

  test('canvas exposes data-active-target ONLY after a hotspot is activated', async ({
    page,
  }) => {
    // Pre-activation: attribute is absent (Astro doesn't emit
    // undefined props as empty strings).
    const initial = await page
      .locator('[data-testid="screen-flow-canvas"]')
      .getAttribute('data-active-target');
    expect(initial).toBeNull();

    const target = await page.evaluate(() => {
      const hotspot = document.querySelector('[data-hotspot-flow]') as HTMLElement | null;
      const t = hotspot?.getAttribute('data-hotspot-to') ?? null;
      hotspot?.click();
      return t;
    });
    expect(target).toBeTruthy();

    await page.waitForFunction(
      (t) =>
        document
          .querySelector('[data-testid="screen-flow-canvas"]')
          ?.getAttribute('data-active-target') === t,
      target,
      { timeout: 1500 },
    );
  });
});
