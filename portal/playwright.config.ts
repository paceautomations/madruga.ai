import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for visual + e2e specs (epic 027).
 *
 * Two projects share a single dev server:
 *   - visual: jest-image-snapshot baselines (1px tolerance) for the canvas.
 *   - e2e: end-to-end capture→commit→render integration spec.
 *
 * Reasoning: a single config file keeps the baseline + e2e specs in sync
 * with `npm run dev`, and matches the package.json scripts which already
 * pass `--config=playwright.config.ts`.
 */
export default defineConfig({
  testDir: './src/test',
  // Visual + E2E are two separate runners.
  projects: [
    {
      name: 'visual',
      testDir: './src/test/visual',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        // Force consistent rendering for snapshots.
        deviceScaleFactor: 1,
      },
    },
    {
      name: 'e2e',
      testDir: './src/test/e2e',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  // Reuse a running dev server when available; spin one up otherwise.
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:4321',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  use: {
    baseURL: 'http://localhost:4321',
  },
});
