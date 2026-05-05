/**
 * ActionEdge (epic 027 — T030).
 *
 * Custom xyflow edge that maps the four flow styles defined in spec
 * FR-001 + FR-021 onto a colour token AND a stroke pattern, so colour-
 * blind viewers can still tell them apart:
 *
 *   success → solid,           --edge-success
 *   error   → dashed,          --edge-error
 *   neutral → dotted,          --edge-neutral
 *   modal   → solid (3 px),    --edge-modal
 *
 * The label (when supplied) renders via xyflow's EdgeLabelRenderer so it
 * stays anchored to the path mid-point even after pan/zoom.
 *
 * `data-edge-style` attribute is set on the visible <path> so the
 * Phase 3 visual spec can count distinct styles in the rendered SVG.
 */
import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from '@xyflow/react';
import './ActionEdge.css';

export interface ActionEdgeData {
  style: 'success' | 'error' | 'neutral' | 'modal';
  label?: string;
  on?: string;
  [key: string]: unknown;
}

const PATTERNS: Record<ActionEdgeData['style'], { dasharray: string; width: number }> = {
  success: { dasharray: '', width: 2 },
  error: { dasharray: '6 4', width: 2 },
  neutral: { dasharray: '2 4', width: 2 }, // dotted-ish
  modal: { dasharray: '', width: 3 },
};

const COLOURS: Record<ActionEdgeData['style'], string> = {
  success: 'var(--edge-success)',
  error: 'var(--edge-error)',
  neutral: 'var(--edge-neutral)',
  modal: 'var(--edge-modal)',
};

export default function ActionEdge(props: EdgeProps) {
  const data = (props.data ?? { style: 'neutral' }) as ActionEdgeData;
  const style = data.style;
  const pattern = PATTERNS[style];
  const colour = COLOURS[style];

  const [path, labelX, labelY] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        markerEnd={props.markerEnd}
        markerStart={props.markerStart}
        style={{
          ...props.style,
          stroke: colour,
          strokeWidth: pattern.width,
        }}
        // BaseEdge does not forward arbitrary props, so emit a sibling
        // <path> carrying the data attribute the tests inspect.
      />
      <path
        d={path}
        data-edge-style={style}
        stroke={colour}
        strokeWidth={pattern.width}
        strokeDasharray={pattern.dasharray || undefined}
        fill="none"
        style={{ stroke: colour, pointerEvents: 'none' }}
      />
      {data.label ? (
        <EdgeLabelRenderer>
          <div
            className={`action-edge__label action-edge__label--${style}`}
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            }}
            role="note"
            aria-label={`Transição ${style}: ${data.label}`}
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}
