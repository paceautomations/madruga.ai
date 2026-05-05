/**
 * ScreenFlowCanvas (epic 027 — T031 + T083 + T084).
 *
 * xyflow wrapper that hosts the entire screen-flow visualisation:
 *   - Background dots
 *   - Non-interactive Controls (zoom in/out, fitView)
 *   - Pannable MiniMap
 *   - Custom node type `screen` (ScreenNode) and edge type `action`
 *     (ActionEdge)
 *
 * Flags chosen per FR-018:
 *   nodesDraggable=false, nodesConnectable=false, elementsSelectable=true,
 *   onlyRenderVisibleElements=true.
 *
 * Keyboard navigation (FR-019): native browser Tab cycles through
 * focusable nodes (ScreenNode renders `tabIndex=0`); Enter is bubbled
 * up to the first child hotspot when one is mounted (Phase 7 — T080).
 *
 * Hotspot interaction layer (T083 + T084):
 *   - `hotspotsVisible` state (default true) is exposed via HotspotContext
 *     and toggled by tecla `H` (FR-025, target <50ms — listener writes
 *     state synchronously and React commits within the next rAF).
 *   - `onHotspotActivate(flow)` animates the matching edge for ~250ms
 *     and then calls `fitView` on the destination node with a 350ms
 *     duration (FR-026, total budget <700ms). The canvas root exposes
 *     `data-active-target` once the camera settles so the visual spec
 *     can detect completion without polling xyflow internals.
 *
 * Tokens come from screen-flow-tokens.css; Background colour follows
 * the Starlight theme without overrides.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import ScreenNode, { type ScreenNodeData } from './ScreenNode';
import ActionEdge, { type ActionEdgeData } from './ActionEdge';
import { HotspotContext } from './HotspotContext';
import type {
  CanvasEdge,
  CanvasNode,
  Flow,
} from '../../lib/screen-flow';
import './ScreenFlowCanvas.css';

interface ScreenFlowCanvasProps {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  /** Set false to hide the MiniMap (e.g. for embedded thumbnails). */
  showMiniMap?: boolean;
}

const NODE_TYPES = {
  screen: ScreenNode,
};

const EDGE_TYPES = {
  action: ActionEdge,
};

// Animation budgets (FR-026, SC-004). Sum stays under 700 ms with margin.
const EDGE_ANIM_MS = 250;
const FIT_VIEW_MS = 350;

export default function ScreenFlowCanvas({
  nodes,
  edges,
  showMiniMap = true,
}: ScreenFlowCanvasProps) {
  return (
    <ReactFlowProvider>
      <CanvasInner nodes={nodes} edges={edges} showMiniMap={showMiniMap} />
    </ReactFlowProvider>
  );
}

function CanvasInner({ nodes, edges, showMiniMap }: ScreenFlowCanvasProps) {
  const [hotspotsVisible, setHotspotsVisible] = useState(true);
  const [activeTarget, setActiveTarget] = useState<string | null>(null);
  const [animatedEdgeId, setAnimatedEdgeId] = useState<string | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const reactFlow = useReactFlow();

  // Reconstruct the per-screen flow list from edges so each ScreenNode
  // knows which hotspots to render. Memoized on edges identity to avoid
  // churn during pan/zoom.
  const flowsByScreen = useMemo(() => {
    const map = new Map<string, Flow[]>();
    for (const e of edges) {
      const flow: Flow = {
        from: e.source,
        to: e.target,
        on: e.data.on,
        style: e.data.style,
        label: e.data.label,
      };
      const list = map.get(e.source) ?? [];
      list.push(flow);
      map.set(e.source, list);
    }
    return map;
  }, [edges]);

  // Build a fast lookup edge.id by (from, on) so onActivate can find the
  // edge to animate without iterating the full list each time.
  const edgeIdByFlow = useMemo(() => {
    const map = new Map<string, string>();
    for (const e of edges) {
      map.set(`${e.source}::${e.data.on}::${e.target}`, e.id);
    }
    return map;
  }, [edges]);

  // Window-level keydown so synthetic events from the visual spec land
  // here regardless of focus location (the spec dispatches via
  // window.dispatchEvent). The handler is intentionally cheap — a single
  // setState — so the round-trip stays within FR-025's 50 ms budget.
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'h' || e.key === 'H') {
        setHotspotsVisible((v) => !v);
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const onHotspotActivate = useCallback(
    (flow: Flow) => {
      const edgeId = edgeIdByFlow.get(`${flow.from}::${flow.on}::${flow.to}`);
      if (edgeId) {
        setAnimatedEdgeId(edgeId);
      }
      // Keep the edge animation visible for ~EDGE_ANIM_MS, then move the
      // camera. Both timings combined target <700 ms (FR-026).
      window.setTimeout(() => {
        try {
          reactFlow.fitView({
            nodes: [{ id: flow.to }],
            duration: FIT_VIEW_MS,
            padding: 0.4,
            maxZoom: 1.2,
          });
        } catch {
          // fitView may throw if the node is missing — degrade silently.
        }
      }, EDGE_ANIM_MS);
      // Mark the destination once fitView completes so the visual spec
      // can synchronise on a deterministic DOM signal.
      window.setTimeout(() => {
        setActiveTarget(flow.to);
        setAnimatedEdgeId(null);
      }, EDGE_ANIM_MS + FIT_VIEW_MS);
    },
    [edgeIdByFlow, reactFlow],
  );

  // Cast our domain types into xyflow's Node<T> / Edge<T> shape with the
  // `flows` slice attached so ScreenNode can render hotspots.
  const flowNodes = useMemo<Node<ScreenNodeData>[]>(
    () =>
      nodes.map((n) => ({
        id: n.id,
        type: 'screen',
        position: n.position,
        data: {
          ...n.data,
          flows: flowsByScreen.get(n.id) ?? [],
        },
        draggable: false,
        selectable: true,
        connectable: false,
      })),
    [nodes, flowsByScreen],
  );

  const flowEdges = useMemo<Edge<ActionEdgeData>[]>(
    () =>
      edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: 'action',
        data: e.data,
        animated: e.id === animatedEdgeId,
      })),
    [edges, animatedEdgeId],
  );

  const ctxValue = useMemo(
    () => ({ visible: hotspotsVisible, onActivate: onHotspotActivate }),
    [hotspotsVisible, onHotspotActivate],
  );

  return (
    <HotspotContext.Provider value={ctxValue}>
      <div
        ref={wrapperRef}
        className="screen-flow-canvas"
        data-testid="screen-flow-canvas"
        data-active-target={activeTarget ?? undefined}
        data-hotspots-visible={hotspotsVisible ? 'true' : 'false'}
        role="region"
        aria-label="Mapa de telas"
      >
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={NODE_TYPES}
          edgeTypes={EDGE_TYPES}
          // FR-018 — non-interactive layout flags.
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={true}
          onlyRenderVisibleElements={true}
          // Keyboard nav (FR-019): xyflow's built-in support already
          // routes Arrow / Enter when nodes are selectable + tabbable.
          fitView
          fitViewOptions={{ padding: 0.2, minZoom: 0.1, maxZoom: 1.5 }}
          minZoom={0.05}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={24} size={1} />
          <Controls showInteractive={false} />
          {showMiniMap ? (
            <MiniMap pannable nodeStrokeWidth={2} />
          ) : null}
        </ReactFlow>
      </div>
    </HotspotContext.Provider>
  );
}
