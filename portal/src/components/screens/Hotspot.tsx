/**
 * Hotspot component (epic 027 — T082).
 *
 * Numbered overlay (1, 2, 3...) rendered on top of a captured/wireframe
 * screen, marking where a user can click to follow a `Flow` to another
 * screen.
 *
 * Spec coverage:
 *   - FR-024 — visible by default with a numbered badge + 1px dashed
 *     outline (token `--hotspot-outline`).
 *   - FR-025 — `visible` prop drives toggle behaviour; ScreenFlowCanvas
 *     toggles it on tecla `H`.
 *   - FR-026 — emits `onActivate(flow)` so the canvas can run the
 *     animation + fitView sequence within the <700ms budget.
 *   - FR-027 — coords are normalized 0-1 along x/y/w/h and projected to
 *     percent positioning so hotspots survive a profile swap without
 *     re-capture.
 *
 * Accessibility (FR-019, FR-020):
 *   - role="button", focusable (tabIndex=0).
 *   - Enter / Space activate the flow (matches native button semantics
 *     without relying on a native <button> element — keeps the overlay
 *     transparent to xyflow's selection layer).
 *   - aria-label cites the destination screen.id (and optional flow.label).
 */
import type { CSSProperties, KeyboardEvent, MouseEvent } from 'react';
import type { Flow } from '../../lib/screen-flow';
import './Hotspot.css';

export interface HotspotCoords {
  /** All values are 0-1 normalized; projected as percent positioning. */
  x: number;
  y: number;
  w: number;
  h: number;
}

interface HotspotProps {
  flow: Flow;
  /** 1-based index — surfaces the numbered badge. */
  index: number;
  coords: HotspotCoords;
  /** Defaults to `true`. Set to `false` to hide via aria-hidden. */
  visible?: boolean;
  onActivate?: (flow: Flow) => void;
}

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0;
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}

function pct(n: number): string {
  // Drop trailing zeros so the inline style stays predictable for tests.
  const v = clamp01(n) * 100;
  return `${v % 1 === 0 ? v.toFixed(0) : v.toFixed(2)}%`;
}

export default function Hotspot({
  flow,
  index,
  coords,
  visible = true,
  onActivate,
}: HotspotProps) {
  const ariaLabel = `Vai para tela ${flow.to}${flow.label ? ` — ${flow.label}` : ''}`;

  const handleClick = (e: MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    onActivate?.(flow);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ' || e.code === 'Space') {
      e.preventDefault();
      e.stopPropagation();
      onActivate?.(flow);
    }
  };

  const style: CSSProperties = {
    left: pct(coords.x),
    top: pct(coords.y),
    width: pct(coords.w),
    height: pct(coords.h),
  };

  return (
    <div
      role="button"
      tabIndex={0}
      className="screen-flow-hotspot"
      data-hotspot-flow={`${flow.from}->${flow.to}`}
      data-hotspot-to={flow.to}
      data-hotspot-on={flow.on}
      data-visible={visible ? 'true' : 'false'}
      aria-label={ariaLabel}
      aria-hidden={visible ? undefined : true}
      style={style}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
    >
      <span className="screen-flow-hotspot__badge">{index}</span>
    </div>
  );
}
