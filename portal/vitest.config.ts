/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import react from '@astrojs/react';

/**
 * Vitest config for Phase 3 component tests (epic 027).
 *
 * - jsdom environment for React Testing Library.
 * - `globals: true` so the @testing-library/jest-dom matchers are picked up
 *   without per-file imports.
 * - Setup file injects `import '@testing-library/jest-dom/vitest'` once.
 * - Scope is locked to `src/test/unit/` to keep visual / e2e specs out of
 *   the component runner.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/test/unit/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test/unit/setup.ts'],
    css: true,
  },
});
