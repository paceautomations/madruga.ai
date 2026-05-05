/**
 * ScreenFlowCanvas (epic 027 — T031).
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
 * Tokens come from screen-flow-tokens.css; Background colour follows
 * the Starlight theme without overrides.
 */
import { useMemo } from 'react';
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import ScreenNode, { type ScreenNodeData } from './ScreenNode';
import ActionEdge, { type ActionEdgeData } from './ActionEdge';
import type {
  CanvasEdge,
  CanvasNode,
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

export default function ScreenFlowCanvas({
  nodes,
  edges,
  showMiniMap = true,
}: ScreenFlowCanvasProps) {
  // Cast our domain types into xyflow's Node<T> / Edge<T> shape.
  const flowNodes = useMemo<Node<ScreenNodeData>[]>(
    () =>
      nodes.map((n) => ({
        id: n.id,
        type: 'screen',
        position: n.position,
        data: n.data,
        draggable: false,
        selectable: true,
        connectable: false,
      })),
    [nodes],
  );

  const flowEdges = useMemo<Edge<ActionEdgeData>[]>(
    () =>
      edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: 'action',
        data: e.data,
      })),
    [edges],
  );

  return (
    <ReactFlowProvider>
      <div
        className="screen-flow-canvas"
        data-testid="screen-flow-canvas"
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
    </ReactFlowProvider>
  );
}
