/**
 * T021 — ActionEdge component tests (epic 027).
 *
 * Verifies the four edge styles (success / error / neutral / modal) defined
 * in spec FR-001 and the visual pattern requirement (FR-021): each style
 * pairs a colour token with a stroke pattern (solid / dashed / dotted) so
 * color-blind viewers can still tell them apart.
 *
 * Also asserts the floating label rendered via EdgeLabelRenderer is present
 * (when supplied) and exposes coherent aria semantics.
 *
 * RED first: this file fails until ActionEdge.tsx exists.
 */
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';

// EdgeLabelRenderer renders into a portal whose target only exists inside a
// full <ReactFlow> instance. Stub it inline so the label JSX is reachable from
// the test DOM — we still exercise the real ActionEdge logic.
vi.mock('@xyflow/react', async () => {
  const actual = await vi.importActual<typeof import('@xyflow/react')>('@xyflow/react');
  return {
    ...actual,
    EdgeLabelRenderer: ({ children }: { children?: unknown }) =>
      children as JSX.Element,
  };
});

import ActionEdge, { type ActionEdgeData } from '../../components/screens/ActionEdge';

type EdgeStyle = ActionEdgeData['style'];

const STYLE_PATTERNS: Record<EdgeStyle, RegExp> = {
  // success → solid (no dasharray) → empty or 'none' or '0'
  success: /^(?:|none|0|)$/,
  // error → dashed
  error: /\d/,
  // neutral → dotted (Playwright/SVG dotted is "dot dash" pair like "1 5" or "2 4")
  neutral: /\d/,
  // modal → solid 3px
  modal: /^(?:|none|0|)$/,
};

const STYLE_COLORS: Record<EdgeStyle, RegExp> = {
  // We accept either CSS variable hookup or computed colour. Keys must be
  // distinguishable in tests via the inline style or className.
  success: /var\(--edge-success/i,
  error: /var\(--edge-error/i,
  neutral: /var\(--edge-neutral/i,
  modal: /var\(--edge-modal/i,
};

function renderEdge(style: EdgeStyle, label?: string) {
  return render(
    <ReactFlowProvider>
      <svg width={400} height={200}>
        <ActionEdge
          id={`edge-${style}`}
          source="from"
          target="to"
          sourceX={20}
          sourceY={20}
          targetX={300}
          targetY={150}
          sourcePosition={'bottom' as never}
          targetPosition={'top' as never}
          data={{ style, label }}
          markerStart={undefined}
          markerEnd={undefined}
          style={{}}
          interactionWidth={0}
          selected={false}
          animated={false}
          source-handleId={null as never}
          target-handleId={null as never}
        />
      </svg>
    </ReactFlowProvider>,
  );
}

describe('ActionEdge', () => {
  it.each<EdgeStyle>(['success', 'error', 'neutral', 'modal'])(
    'renders style "%s" with the expected colour token',
    (style) => {
      const { container } = renderEdge(style);
      const path = container.querySelector('path[data-edge-style]');
      expect(path).not.toBeNull();
      expect(path!.getAttribute('data-edge-style')).toBe(style);
      const inlineStyle = path!.getAttribute('style') ?? '';
      const stroke = path!.getAttribute('stroke') ?? '';
      expect(stroke + inlineStyle).toMatch(STYLE_COLORS[style]);
    },
  );

  it('applies a distinct stroke pattern per style (solid / dashed / dotted)', () => {
    const styles: EdgeStyle[] = ['success', 'error', 'neutral', 'modal'];
    const dasharrays = styles.map((style) => {
      const { container } = renderEdge(style);
      const path = container.querySelector('path[data-edge-style]')!;
      return path.getAttribute('stroke-dasharray') ?? '';
    });
    // Patterns must be distinguishable across the four styles. We accept
    // duplicates only between success/modal (both solid), but error must
    // differ from neutral, and both must differ from solid.
    expect(dasharrays[1]).not.toBe(dasharrays[0]); // error != success
    expect(dasharrays[2]).not.toBe(dasharrays[0]); // neutral != success
    expect(dasharrays[2]).not.toBe(dasharrays[1]); // neutral != error
  });

  it('respects the per-style stroke-width (modal is thicker)', () => {
    const widths = (['success', 'error', 'neutral', 'modal'] as EdgeStyle[]).map(
      (style) => {
        const { container } = renderEdge(style);
        const path = container.querySelector('path[data-edge-style]')!;
        return Number(path.getAttribute('stroke-width') ?? '0');
      },
    );
    expect(widths[3]).toBeGreaterThan(widths[0]); // modal > success
  });

  it('renders an accessible label when provided', () => {
    // EdgeLabelRenderer (xyflow) renders into a portal whose target is created
    // by the parent <ReactFlow>. Outside a ReactFlow instance the portal target
    // doesn't exist, but we can still assert the role+aria-label that the
    // component declares — that's the actual a11y contract (FR-021).
    const { getByLabelText } = renderEdge('success', 'Login OK');
    const label = getByLabelText(/Transição success: Login OK/i);
    expect(label).toBeInTheDocument();
    expect(label.textContent).toBe('Login OK');
  });

  it('omits the label DOM when no label prop is supplied', () => {
    const { queryByLabelText } = renderEdge('error');
    expect(queryByLabelText(/Transição/i)).toBeNull();
  });

  it('matches stroke-dasharray empty/null for solid styles', () => {
    const { container } = renderEdge('success');
    const path = container.querySelector('path[data-edge-style]')!;
    const dash = path.getAttribute('stroke-dasharray') ?? '';
    expect(dash).toMatch(STYLE_PATTERNS.success);
  });
});
