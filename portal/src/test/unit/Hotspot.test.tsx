/**
 * T080 — Hotspot component tests (epic 027).
 *
 * Coverage (FR-024 / FR-025 / FR-027 / SC-021):
 *   - Numbered badge (1, 2, 3...) renders the integer.
 *   - Outline 1px dashed via tokens (`--hotspot-outline`).
 *   - aria-label cites the destination ("Vai para tela <id>").
 *   - tabIndex=0 → focusable; Enter/Space activates onActivate(flow).
 *   - Visible by default; hidden when `visible={false}`.
 *   - Coords 0-1 are projected as percent-based positioning (FR-027).
 *
 * RED first: this file fails until Hotspot.tsx exists.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Hotspot from '../../components/screens/Hotspot';
import type { Flow } from '../../lib/screen-flow';

const flow: Flow = {
  from: 'login',
  to: 'home',
  on: 'submit',
  style: 'success',
  label: 'Login OK',
};

const COORDS = { x: 0.25, y: 0.5, w: 0.5, h: 0.1 };

describe('Hotspot', () => {
  it('renders the numbered badge with the supplied index', () => {
    render(<Hotspot flow={flow} index={3} coords={COORDS} />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('exposes a descriptive aria-label citing the destination', () => {
    render(<Hotspot flow={flow} index={1} coords={COORDS} />);
    const button = screen.getByRole('button');
    expect(button.getAttribute('aria-label')).toMatch(/Vai para tela home/);
  });

  it('uses the flow.label when provided to enrich the aria-label', () => {
    render(<Hotspot flow={flow} index={1} coords={COORDS} />);
    const button = screen.getByRole('button');
    expect(button.getAttribute('aria-label')).toMatch(/Login OK/);
  });

  it('uses the dashed outline class so tokens can style it', () => {
    render(<Hotspot flow={flow} index={1} coords={COORDS} />);
    const button = screen.getByRole('button');
    expect(button.className).toMatch(/hotspot/);
  });

  it('is keyboard focusable (tabIndex=0)', () => {
    render(<Hotspot flow={flow} index={1} coords={COORDS} />);
    const button = screen.getByRole('button');
    expect(button.getAttribute('tabindex')).toBe('0');
  });

  it('activates onActivate(flow) when clicked', () => {
    const handler = vi.fn();
    render(
      <Hotspot flow={flow} index={1} coords={COORDS} onActivate={handler} />,
    );
    fireEvent.click(screen.getByRole('button'));
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(flow);
  });

  it('activates onActivate(flow) on Enter keypress', () => {
    const handler = vi.fn();
    render(
      <Hotspot flow={flow} index={1} coords={COORDS} onActivate={handler} />,
    );
    const button = screen.getByRole('button');
    fireEvent.keyDown(button, { key: 'Enter', code: 'Enter' });
    expect(handler).toHaveBeenCalledWith(flow);
  });

  it('activates onActivate(flow) on Space keypress', () => {
    const handler = vi.fn();
    render(
      <Hotspot flow={flow} index={1} coords={COORDS} onActivate={handler} />,
    );
    const button = screen.getByRole('button');
    fireEvent.keyDown(button, { key: ' ', code: 'Space' });
    expect(handler).toHaveBeenCalledWith(flow);
  });

  it('is visible by default and exposes data-visible attribute', () => {
    render(<Hotspot flow={flow} index={1} coords={COORDS} />);
    const button = screen.getByRole('button');
    expect(button.getAttribute('data-visible')).toBe('true');
  });

  it('hides via aria-hidden when visible={false}', () => {
    render(
      <Hotspot flow={flow} index={1} coords={COORDS} visible={false} />,
    );
    const button = screen.getByRole('button', { hidden: true });
    expect(button.getAttribute('data-visible')).toBe('false');
    expect(button.getAttribute('aria-hidden')).toBe('true');
  });

  it('positions itself using normalized 0-1 coords as percentages', () => {
    render(<Hotspot flow={flow} index={1} coords={COORDS} />);
    const button = screen.getByRole('button') as HTMLElement;
    // Style values are written as strings via inline style attribute.
    expect(button.style.left).toBe('25%');
    expect(button.style.top).toBe('50%');
    expect(button.style.width).toBe('50%');
    expect(button.style.height).toBe('10%');
  });

  it('does not call onActivate for unrelated keys', () => {
    const handler = vi.fn();
    render(
      <Hotspot flow={flow} index={1} coords={COORDS} onActivate={handler} />,
    );
    fireEvent.keyDown(screen.getByRole('button'), { key: 'a' });
    expect(handler).not.toHaveBeenCalled();
  });
});
