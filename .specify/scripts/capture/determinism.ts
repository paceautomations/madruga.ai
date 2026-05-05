/**
 * determinism.ts — apply the determinism layer to a Playwright Page.
 *
 * Implements FR-030, FR-031 of epic 027-screen-flow-canvas. Loaded by
 * `screen_capture.spec.ts` which iterates each screen and calls these helpers
 * BEFORE `page.goto`. The orchestrator (`screen_capture.py`) hands the
 * `DeterminismConfig` block (extracted from `platform.yaml`) over via the
 * `SCREEN_FLOW_CAPTURE_CONFIG` env var.
 *
 * Stack policy: zero new npm deps — only `@playwright/test` (already present).
 */

import type { BrowserContext, Page, Route } from "@playwright/test";

// ─────────────────────────────────────────────────────────────────────────────
// Public types — mirror the JSON Schema $defs.DeterminismConfig
// ─────────────────────────────────────────────────────────────────────────────

export interface MockRoute {
  /** Glob or Playwright regex (e.g. "**\/api/notifications/unread"). */
  match: string;
  body?: unknown;
  status?: number;
}

export interface DeterminismConfig {
  freeze_time?: string; // ISO 8601, default: no freeze
  random_seed?: number;
  disable_animations?: boolean; // default: true
  clear_service_workers?: boolean; // default: false
  clear_cookies_between_screens?: boolean; // default: false
  mock_routes?: MockRoute[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Init script payload — runs in the page's JS context BEFORE any other script
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Build the script source string. Captures freeze_time + random_seed via
 * closure-style template substitution. Pure — no I/O — easy to unit-test.
 */
export function buildInitScript(cfg: Pick<DeterminismConfig, "freeze_time" | "random_seed">): string {
  const frozen = cfg.freeze_time ? new Date(cfg.freeze_time).getTime() : null;
  const seed = typeof cfg.random_seed === "number" ? cfg.random_seed : null;
  return `
    (() => {
      // ── Date freeze ───────────────────────────────────────────────────
      const __FROZEN__ = ${frozen === null ? "null" : frozen};
      if (__FROZEN__ !== null) {
        const _RealDate = Date;
        // @ts-expect-error monkey-patch
        globalThis.Date = class extends _RealDate {
          constructor(...args) {
            if (args.length === 0) { super(__FROZEN__); return; }
            // @ts-expect-error spread
            super(...args);
          }
          static now() { return __FROZEN__; }
        };
        // Preserve native methods that some libs check via Object.is(Date, ...)
        Object.setPrototypeOf(globalThis.Date, _RealDate);
      }

      // ── Math.random with xorshift PRNG ───────────────────────────────
      const __SEED__ = ${seed === null ? "null" : seed};
      if (__SEED__ !== null) {
        let state = __SEED__ >>> 0 || 1;
        Math.random = function() {
          state ^= state << 13;
          state ^= state >>> 17;
          state ^= state << 5;
          state >>>= 0;
          return state / 0x100000000;
        };
      }

      // ── Disable native animation jitter ──────────────────────────────
      try {
        const _raf = globalThis.requestAnimationFrame;
        globalThis.requestAnimationFrame = (cb) => _raf(() => cb(0));
      } catch (_e) { /* env without rAF */ }
    })();
  `;
}

// ─────────────────────────────────────────────────────────────────────────────
// Public helpers — used by the spec
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Apply addInitScript + addStyleTag (transitions/animations off).
 * Idempotent — safe to call once per Page.
 */
export async function setupDeterminism(page: Page, cfg: DeterminismConfig): Promise<void> {
  await page.addInitScript({ content: buildInitScript(cfg) });

  if (cfg.disable_animations !== false) {
    await page.addStyleTag({
      content: `
        *, *::before, *::after {
          animation-duration: 0s !important;
          animation-delay: 0s !important;
          transition-duration: 0s !important;
          transition-delay: 0s !important;
          caret-color: transparent !important;
        }
      `,
    }).catch(() => { /* style tag may fail before any document — non-fatal */ });
  }
}

/**
 * Pre-`page.goto` hygiene: clear cookies + unregister service workers + drop
 * caches. Runs only when the corresponding flag is set in the config.
 *
 * FR-031 — Service Worker cleanup MUST happen BEFORE each navigation when
 * `clear_service_workers: true`.
 */
export async function preNavigateCleanup(
  page: Page,
  context: BrowserContext,
  cfg: DeterminismConfig,
): Promise<void> {
  if (cfg.clear_cookies_between_screens) {
    await context.clearCookies();
  }
  if (cfg.clear_service_workers) {
    try {
      await page.evaluate(async () => {
        if ("serviceWorker" in navigator) {
          const regs = await navigator.serviceWorker.getRegistrations();
          await Promise.all(regs.map((r) => r.unregister()));
        }
        if ("caches" in self) {
          const keys = await caches.keys();
          await Promise.all(keys.map((k) => caches.delete(k)));
        }
      });
    } catch (_err) {
      // Browser without SW support — non-fatal warn, capture proceeds.
      // The orchestrator (Python) will tag the next failure (if any) with
      // reason=sw_cleanup_failed.
    }
  }
}

/**
 * Register every mock route declared in config. Each route returns the
 * declared body (default JSON) or status. Unmatched real requests pass
 * through.
 *
 * FR-030 — `page.route()` per entry.
 */
export async function setupMockRoutes(page: Page, routes: MockRoute[] = []): Promise<void> {
  for (const r of routes) {
    await page.route(r.match, async (route: Route) => {
      const status = r.status ?? 200;
      if (r.body !== undefined) {
        await route.fulfill({
          status,
          contentType: "application/json",
          body: typeof r.body === "string" ? r.body : JSON.stringify(r.body),
        });
        return;
      }
      await route.fulfill({ status });
    });
  }
}

/**
 * Convenience: apply ALL determinism + mocks in one shot. Used by the spec.
 */
export async function applyAllDeterminism(
  page: Page,
  context: BrowserContext,
  cfg: DeterminismConfig,
): Promise<void> {
  await setupDeterminism(page, cfg);
  await setupMockRoutes(page, cfg.mock_routes ?? []);
  await preNavigateCleanup(page, context, cfg);
}
