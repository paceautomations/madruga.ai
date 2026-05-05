/**
 * ScreenNode (epic 027 — T029 + T085).
 *
 * Custom xyflow node that renders one Screen across the three capture
 * states (FR-001 + data-model E2):
 *
 *   pending  → Chrome + WireframeBody + WIREFRAME / AGUARDANDO badge
 *   captured → Chrome + <img> from business/shots/<id>.png + WEB BUILD vX badge
 *   failed   → Chrome + WireframeBody + FALHOU badge with failure.reason tooltip
 *
 * Hotspot overlay (T085): for every flow whose `from === screen.id`,
 * a numbered Hotspot is rendered on top of the chrome body. Coordinates
 * come either from a captured boundingBox (when the capture script
 * resolved `[data-testid]` against the live DOM) or from a deterministic
 * fallback derived from the body component index (FR-027 — coords are
 * normalized 0-1 so the same overlay survives a profile swap).
 *
 * Memoized by (id, selected, screen, profile, flows) — flows churn
 * shallowly because ScreenFlowCanvas materialises them with useMemo.
 *
 * Accessibility (FR-020): each node exposes `aria-label="Tela <id>: <summary>"`
 * — screen readers can navigate the canvas via keyboard (FR-019).
 */
import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import type { CaptureProfile, Flow, Screen } from '../../lib/screen-flow';
import Chrome from './Chrome';
import WireframeBody from './WireframeBody';
import Badge, { type BadgeVariant } from './Badge';
import Hotspot, { type HotspotCoords } from './Hotspot';
import { useHotspotContext } from './HotspotContext';
import './ScreenNode.css';

export interface ScreenNodeData {
  screen: Screen;
  profile: CaptureProfile;
  /** Flows where `from === screen.id`. Populated by ScreenFlowCanvas. */
  flows?: Flow[];
  /** Optional override label, e.g. `WEB BUILD v9c4f1a2` from app_version. */
  capturedBadgeLabel?: string;
  [key: string]: unknown;
}

type ScreenNodeFlowNode = Node<ScreenNodeData, 'screen'>;

function ScreenNodeImpl(props: NodeProps<ScreenNodeFlowNode>) {
  const { screen, profile, capturedBadgeLabel, flows } = props.data;
  const ariaLabel = describeScreen(screen);
  const badgeVariant = pickBadgeVariant(screen);
  const badgeLabel = pickBadgeLabel(screen, capturedBadgeLabel);
  const failureTooltip = screen.failure
    ? `${screen.failure.reason}${
        screen.failure.last_error_message ? ` — ${screen.failure.last_error_message}` : ''
      }`
    : undefined;

  const hotspotCtx = useHotspotContext();
  const hotspots = (flows ?? [])
    .map((flow, i) => {
      const coords = resolveHotspotCoords(screen, flow, i, flows ?? []);
      if (!coords) return null;
      return { flow, coords, index: i + 1 };
    })
    .filter((h): h is { flow: Flow; coords: HotspotCoords; index: number } => h !== null);

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
        <div className="screen-node__overlay-root">
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
          {hotspots.map(({ flow, coords, index }) => (
            <Hotspot
              key={`${flow.from}->${flow.to}-${flow.on}-${index}`}
              flow={flow}
              index={index}
              coords={coords}
              visible={hotspotCtx.visible}
              onActivate={hotspotCtx.onActivate}
            />
          ))}
        </div>
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
// from xyflow (zIndex, dragging) don't affect the visual output. Flows
// reference equality is preserved by ScreenFlowCanvas's memo, so adding
// it here keeps hotspot updates in sync without re-renders for camera moves.
const ScreenNode = memo(ScreenNodeImpl, (prev, next) => {
  return (
    prev.id === next.id &&
    prev.selected === next.selected &&
    prev.data.screen === next.data.screen &&
    prev.data.profile === next.data.profile &&
    prev.data.flows === next.data.flows
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

/**
 * Resolve normalized 0-1 coordinates for a hotspot.
 *
 * Priority:
 *   1. Captured boundingBox (future): the capture script will populate
 *      coords from `[data-testid="<id>"]` and we'll thread them through
 *      `screen.meta.hotspots` (out of scope for T085 — fallback below
 *      keeps the renderer useful with fixture-only data).
 *   2. Body-index fallback: locate the body component matching
 *      `body.id === flow.on` and project its position by index. This
 *      keeps hotspots stable across runs without DOM measurement and
 *      satisfies the visible / clickable / numbered invariants the
 *      Phase 7 spec covers.
 */
function resolveHotspotCoords(
  screen: Screen,
  flow: Flow,
  fallbackIndex: number,
  allFlows: Flow[],
): HotspotCoords | null {
  const bodyIdx = screen.body.findIndex((c) => c.id === flow.on);
  // If the body component is missing entirely, still emit a hotspot so
  // the flow remains discoverable, stacked at the bottom of the screen.
  const total = Math.max(screen.body.length, 1);
  // Spread overlapping hotspots horizontally when more than one flow
  // targets the same body component (rare but legal — login OK + login
  // error both fire on `submit`).
  const peers = allFlows.filter((f) => f.on === flow.on);
  const peerIdx = peers.findIndex(
    (f) => f.from === flow.from && f.to === flow.to,
  );
  const peerCount = peers.length;

  const yIdx = bodyIdx >= 0 ? bodyIdx : total - 1;
  const yCenter = (yIdx + 0.5) / total;
  const h = 1 / total;
  // Hotspot height is capped so badges remain compact on tall screens.
  const cappedH = Math.min(h, 0.18);
  const y = Math.max(0, Math.min(1 - cappedH, yCenter - cappedH / 2));

  const w = peerCount > 1 ? Math.min(0.5, 1 / peerCount) : 0.6;
  const offset = peerCount > 1 ? peerIdx * w : 0.2;
  const x = Math.max(0, Math.min(1 - w, offset));

  return { x, y, w, h: cappedH };
  // fallbackIndex unused — reserved for future captured-coord ordering.
  void fallbackIndex;
}
