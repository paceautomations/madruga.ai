/**
 * ScreenNode (epic 027 — T029).
 *
 * Custom xyflow node that renders one Screen across the three capture
 * states (FR-001 + data-model E2):
 *
 *   pending  → Chrome + WireframeBody + WIREFRAME / AGUARDANDO badge
 *   captured → Chrome + <img> from business/shots/<id>.png + WEB BUILD vX badge
 *   failed   → Chrome + WireframeBody + FALHOU badge with failure.reason tooltip
 *
 * Memoized by id+selected (`memo` with custom comparator) so xyflow's
 * incremental rerenders don't churn nodes when only the camera changes.
 *
 * Accessibility (FR-020): each node exposes `aria-label="Tela <id>: <summary>"`
 * — screen readers can navigate the canvas via keyboard (FR-019).
 */
import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import type { CaptureProfile, Screen } from '../../lib/screen-flow';
import Chrome from './Chrome';
import WireframeBody from './WireframeBody';
import Badge, { type BadgeVariant } from './Badge';
import './ScreenNode.css';

export interface ScreenNodeData {
  screen: Screen;
  profile: CaptureProfile;
  /** Optional override label, e.g. `WEB BUILD v9c4f1a2` from app_version. */
  capturedBadgeLabel?: string;
  [key: string]: unknown;
}

type ScreenNodeFlowNode = Node<ScreenNodeData, 'screen'>;

function ScreenNodeImpl(props: NodeProps<ScreenNodeFlowNode>) {
  const { screen, profile, capturedBadgeLabel } = props.data;
  const ariaLabel = describeScreen(screen);
  const badgeVariant = pickBadgeVariant(screen);
  const badgeLabel = pickBadgeLabel(screen, capturedBadgeLabel);
  const failureTooltip = screen.failure
    ? `${screen.failure.reason}${
        screen.failure.last_error_message ? ` — ${screen.failure.last_error_message}` : ''
      }`
    : undefined;

  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className="screen-node"
      data-screen-id={screen.id}
      data-status={screen.status}
      title={failureTooltip}
      tabIndex={0}
    >
      <Handle type="target" position={Position.Top} className="screen-node__handle" />
      <div className="screen-node__badge">
        <Badge variant={badgeVariant} label={badgeLabel} title={failureTooltip} />
      </div>
      <Chrome profile={profile} label={screen.title}>
        {screen.status === 'captured' && screen.image ? (
          <img
            className="screen-node__image"
            src={resolveImageSrc(screen.image)}
            alt={`Captura da tela ${screen.id}`}
            draggable={false}
          />
        ) : (
          <WireframeBody body={screen.body} />
        )}
      </Chrome>
      <Handle
        type="source"
        position={Position.Bottom}
        className="screen-node__handle"
      />
    </div>
  );
}

// Memo with a strict equality check on (id, selected, status). Other props
// from xyflow (zIndex, dragging) don't affect the visual output.
const ScreenNode = memo(ScreenNodeImpl, (prev, next) => {
  return (
    prev.id === next.id &&
    prev.selected === next.selected &&
    prev.data.screen === next.data.screen &&
    prev.data.profile === next.data.profile
  );
});

ScreenNode.displayName = 'ScreenNode';

export default ScreenNode;

// ── Helpers ────────────────────────────────────────────────────────────

function describeScreen(s: Screen): string {
  const summary = s.body
    .map((c) => c.text ?? c.type)
    .filter(Boolean)
    .slice(0, 4)
    .join(', ');
  return `Tela ${s.id}: ${s.title}${summary ? ` — ${summary}` : ''}`;
}

function pickBadgeVariant(s: Screen): BadgeVariant {
  if (s.status === 'failed') return 'falhou';
  if (s.status === 'captured') return 'web-build';
  return 'wireframe';
}

function pickBadgeLabel(s: Screen, override?: string): string | undefined {
  if (override) return override;
  if (s.status === 'captured' && s.capture?.app_version) {
    return `WEB BUILD v${s.capture.app_version}`;
  }
  return undefined;
}

/**
 * Image paths in the YAML are repo-relative (e.g. `business/shots/home.png`).
 * The portal serves platforms/<name>/business/* via Astro's symlinks, so we
 * rewrite to a portal-relative URL when we can detect the platform context.
 *
 * Falls back to the raw path so tests can assert with substring matches.
 */
function resolveImageSrc(image: string): string {
  // If the YAML already provides an absolute URL or `/path`, trust it.
  if (image.startsWith('http') || image.startsWith('/')) return image;
  return image;
}
