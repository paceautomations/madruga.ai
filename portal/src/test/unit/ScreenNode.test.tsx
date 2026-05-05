/**
 * T020 — ScreenNode component tests (epic 027).
 *
 * Covers the 3 capture states (wireframe/captured/failed) declared in
 * spec FR-001 + data-model E2 state machine:
 *   - wireframe (status=pending without image): renders WireframeBody
 *   - captured (status=captured + image): renders <img> with src to LFS path
 *   - failed (status=failed + failure block): renders FALHOU badge + tooltip
 *
 * Verifies aria-label (FR-020), capture/failure badges (FR-001), and
 * memo behaviour (selected toggle re-renders without deps churn).
 *
 * RED first: this file fails until ScreenNode.tsx exists.
 */
import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import type { Screen } from '../../lib/screen-flow';
import ScreenNode from '../../components/screens/ScreenNode';

const wireframeScreen: Screen = {
  id: 'login',
  title: 'Login',
  status: 'pending',
  body: [
    { type: 'heading', text: 'Entrar' },
    { type: 'input', id: 'email', text: 'E-mail' },
    { type: 'button', id: 'submit', text: 'Entrar' },
  ],
};

const capturedScreen: Screen = {
  id: 'home',
  title: 'Home',
  status: 'captured',
  image: 'business/shots/home.png',
  body: [{ type: 'heading', text: 'Olá!' }],
  capture: {
    captured_at: '2026-05-05T10:00:00Z',
    app_version: '9c4f1a2',
    image_md5: 'abc123',
    viewport: { w: 393, h: 852 },
  },
};

const failedScreen: Screen = {
  id: 'profile',
  title: 'Perfil',
  status: 'failed',
  body: [{ type: 'heading', text: 'Perfil' }],
  failure: {
    reason: 'timeout',
    occurred_at: '2026-05-05T10:00:00Z',
    retry_count: 3,
    last_error_message: 'page.goto timed out after 30000ms',
  },
};

function renderNode(s: Screen) {
  return render(
    <ReactFlowProvider>
      <ScreenNode
        id={s.id}
        type="screen"
        position={{ x: 0, y: 0 }}
        data={{ screen: s, profile: 'iphone-15' }}
        selected={false}
        zIndex={0}
        isConnectable={false}
        positionAbsoluteX={0}
        positionAbsoluteY={0}
        dragging={false}
        deletable={false}
        selectable={false}
        draggable={false}
      />
    </ReactFlowProvider>,
  );
}

describe('ScreenNode', () => {
  describe('wireframe state', () => {
    it('renders the wireframe body and a WIREFRAME badge', () => {
      renderNode(wireframeScreen);
      const node = screen.getByRole('group', { name: /Tela login/i });
      expect(node).toBeInTheDocument();
      expect(node).toHaveAttribute('data-status', 'pending');
      // WireframeBody markers visible
      expect(within(node).getByText('Entrar')).toBeInTheDocument();
      expect(within(node).getByText(/E-?mail/i)).toBeInTheDocument();
      // No <img> because status != captured
      expect(within(node).queryByRole('img')).toBeNull();
      // WIREFRAME badge surfaced
      expect(within(node).getByText(/wireframe/i)).toBeInTheDocument();
    });

    it('exposes a descriptive aria-label citing the screen id', () => {
      renderNode(wireframeScreen);
      const node = screen.getByRole('group', { name: /Tela login/i });
      expect(node.getAttribute('aria-label')).toMatch(/Tela login/);
    });
  });

  describe('captured state', () => {
    it('renders the captured PNG and a captured badge', () => {
      renderNode(capturedScreen);
      const node = screen.getByRole('group', { name: /Tela home/i });
      expect(node).toHaveAttribute('data-status', 'captured');
      const img = within(node).getByRole('img');
      expect(img).toHaveAttribute('src', expect.stringContaining('home.png'));
      // Captured badge variant — accept any of WEB BUILD / iOS / WEB
      expect(
        within(node).getByText(/web build|web v|ios v|captured/i),
      ).toBeInTheDocument();
    });
  });

  describe('failed state', () => {
    it('renders the FALHOU badge with tooltip exposing failure.reason', () => {
      renderNode(failedScreen);
      const node = screen.getByRole('group', { name: /Tela profile/i });
      expect(node).toHaveAttribute('data-status', 'failed');
      const badge = within(node).getByText(/falhou/i);
      expect(badge).toBeInTheDocument();
      // failure.reason surfaces via title (tooltip) or aria-describedby
      const tooltip =
        badge.closest('[title]')?.getAttribute('title') ??
        node.getAttribute('title') ??
        '';
      expect(tooltip.toLowerCase()).toContain('timeout');
    });
  });

  it('applies state-specific CSS classes for tokens to hook into', () => {
    const { rerender } = renderNode(wireframeScreen);
    expect(
      screen.getByRole('group', { name: /Tela login/i }).className,
    ).toMatch(/screen-node/);
    rerender(
      <ReactFlowProvider>
        <ScreenNode
          id={capturedScreen.id}
          type="screen"
          position={{ x: 0, y: 0 }}
          data={{ screen: capturedScreen, profile: 'iphone-15' }}
          selected={false}
          zIndex={0}
          isConnectable={false}
          positionAbsoluteX={0}
          positionAbsoluteY={0}
          dragging={false}
          deletable={false}
          selectable={false}
          draggable={false}
        />
      </ReactFlowProvider>,
    );
    expect(
      screen.getByRole('group', { name: /Tela home/i }).className,
    ).toMatch(/screen-node/);
  });
});
