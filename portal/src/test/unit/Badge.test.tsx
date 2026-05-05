/**
 * T023 — Badge component tests (epic 027).
 *
 * 6 vocabulary entries (FR-001):
 *   WIREFRAME — slate, used while screen.status=pending
 *   AGUARDANDO — slate, drift-pending state (re-capture queued)
 *   FALHOU    — red, status=failed (FR-001 + US-04)
 *   WEB BUILD v<x> — green, web/expo capture
 *   iOS v<x>      — green, native iOS capture (future)
 *   WEB v<x>      — green, browser capture (future)
 *
 * Verifies colour token hookup, label text, and accessible role.
 *
 * RED first: this file fails until Badge.tsx exists.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Badge, { type BadgeVariant } from '../../components/screens/Badge';

const VARIANTS: Array<{
  variant: BadgeVariant;
  label?: string;
  text: RegExp;
  cssClass: string;
}> = [
  { variant: 'wireframe', text: /wireframe/i, cssClass: 'badge-wireframe' },
  { variant: 'aguardando', text: /aguardando/i, cssClass: 'badge-wireframe' },
  { variant: 'falhou', text: /falhou/i, cssClass: 'badge-failed' },
  {
    variant: 'web-build',
    label: 'WEB BUILD v9c4f1a2',
    text: /web build v9c4f1a2/i,
    cssClass: 'badge-captured',
  },
  {
    variant: 'ios',
    label: 'iOS v1.2.3',
    text: /ios v1\.2\.3/i,
    cssClass: 'badge-captured',
  },
  {
    variant: 'web',
    label: 'WEB v1.2.3',
    text: /web v1\.2\.3/i,
    cssClass: 'badge-captured',
  },
];

describe('Badge', () => {
  it.each(VARIANTS)('renders the "$variant" variant', ({ variant, label, text, cssClass }) => {
    render(<Badge variant={variant} label={label} />);
    const node = screen.getByText(text);
    expect(node).toBeInTheDocument();
    expect(node.closest('[class*="badge"]')).toHaveClass(cssClass);
  });

  it('exposes role="status" so AT users hear state changes', () => {
    render(<Badge variant="falhou" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('passes through an optional title (tooltip) attribute', () => {
    render(<Badge variant="falhou" title="page.goto timeout (3 retries)" />);
    const node = screen.getByText(/falhou/i).closest('[title]');
    expect(node?.getAttribute('title')).toMatch(/timeout/);
  });

  it('falls back to the variant token when no label is supplied', () => {
    render(<Badge variant="web-build" />);
    // No explicit label → still renders something readable, not empty.
    expect(screen.getByRole('status').textContent).toMatch(/web build/i);
  });
});
