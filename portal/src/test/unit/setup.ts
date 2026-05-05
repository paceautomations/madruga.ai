// Vitest setup — extends `expect` with @testing-library/jest-dom matchers
// (e.g. toBeInTheDocument, toHaveClass, toHaveAttribute). Imported once by
// vitest.config.ts → setupFiles, so individual test files don't need it.
import '@testing-library/jest-dom/vitest';
