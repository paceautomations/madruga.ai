import { useState, useEffect, useCallback, memo, Component } from 'react';
import type { ReactNode } from 'react';
import {
  ReactFlow,
  Handle,
  Position,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// ── Types ──

interface PipelineNodeData {
  id: string;
  status: string;
  layer: string;
  gate: string;
  optional: boolean;
  depends: string[];
  outputs: string[];
  platform: string;
  label: string;
  [key: string]: unknown;
}

interface EpicNode {
  id: string;
  status: string;
  completed_at: string | null;
}

interface EpicData {
  id: string;
  title: string;
  status: string;
  nodes: EpicNode[];
}

interface Platform {
  id: string;
  title: string;
  lifecycle: string;
  l1: {
    nodes: PipelineNodeData[];
    progress_pct: number;
  };
  l2: {
    epics: EpicData[];
  };
}

interface PipelineDAGProps {
  platforms: Platform[];
}

// ── Constants ──

const STATUS_COLORS: Record<string, string> = {
  done: '#4CAF50',
  pending: '#FFC107',
  blocked: '#F44336',
  skipped: '#6b7280',
  stale: '#FF9800',
};

const STATUS_ICON: Record<string, string> = {
  done: '✓',
  pending: '○',
  blocked: '✗',
  skipped: '–',
  stale: '⚠',
};

// ── Error Boundary ──

class DAGErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: '0.5rem', color: 'var(--sl-color-gray-3, #999)' }}>
          <p>Erro ao carregar DAG.</p>
          <code style={{ fontSize: '0.85em', opacity: 0.7 }}>{this.state.error.message}</code>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Custom Node ──

const PipelineNode = memo(({ data }: NodeProps<Node<PipelineNodeData>>) => {
  const color = STATUS_COLORS[data.status] || '#666';
  const icon = STATUS_ICON[data.status] || '?';

  const handleClick = () => {
    if (data.outputs?.length) {
      const path = data.outputs[0].replace(/\.md$/, '').replace(/\.likec4$/, '');
      window.location.href = `/${data.platform}/${path}/`;
    }
  };

  return (
    <div
      onClick={handleClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick(); }}
      role={data.outputs?.length ? 'link' : undefined}
      tabIndex={data.outputs?.length ? 0 : undefined}
      aria-label={`${data.label}: ${data.status}`}
      style={{
        padding: '6px 10px',
        borderRadius: 6,
        border: `2px solid ${color}`,
        background: `${color}15`,
        cursor: data.outputs?.length ? 'pointer' : 'default',
        minWidth: 130,
        textAlign: 'center',
      }}
      title={`${data.id} (${data.status}) — ${data.gate} gate`}
    >
      <Handle type="target" position={Position.Top} style={{ background: color, width: 5, height: 5 }} />
      <div style={{ fontSize: '0.7rem', fontWeight: 600, color, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
        <span>{icon}</span>
        <span>{data.label}</span>
      </div>
      <div style={{ fontSize: '0.55rem', color: 'var(--sl-color-gray-3, #888)', marginTop: 1 }}>
        {data.layer} · {data.gate}{data.optional ? ' · opt' : ''}
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: color, width: 5, height: 5 }} />
    </div>
  );
});

const nodeTypes = { pipeline: PipelineNode };

// ── ELK Layout (lazy initialized) ──

let elkInstance: any = null;

async function getElk() {
  if (!elkInstance) {
    const ELK = (await import('elkjs/lib/elk.bundled.js')).default;
    elkInstance = new ELK();
  }
  return elkInstance;
}

async function computeLayout(
  nodes: Node<PipelineNodeData>[],
  edges: Edge[],
): Promise<{ nodes: Node<PipelineNodeData>[]; edges: Edge[] }> {
  const elk = await getElk();
  const result = await elk.layout({
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.spacing.nodeNode': '35',
      'elk.layered.spacing.nodeNodeBetweenLayers': '50',
      'elk.edgeRouting': 'ORTHOGONAL',
    },
    children: nodes.map((n) => ({ id: n.id, width: 150, height: 48 })),
    edges: edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  });

  return {
    nodes: nodes.map((node) => {
      const elkNode = result.children?.find((c: any) => c.id === node.id);
      return { ...node, position: { x: elkNode?.x ?? 0, y: elkNode?.y ?? 0 } };
    }),
    edges,
  };
}

// ── Build graph ──

function buildGraph(platform: Platform, showL2: boolean) {
  const nodes: Node<PipelineNodeData>[] = [];
  const edges: Edge[] = [];

  for (const n of platform.l1.nodes) {
    nodes.push({
      id: n.id,
      type: 'pipeline',
      position: { x: 0, y: 0 },
      data: { ...n, platform: platform.id, label: n.id },
    });
    for (const dep of n.depends || []) {
      edges.push({
        id: `${dep}->${n.id}`,
        source: dep,
        target: n.id,
        style: { stroke: 'var(--sl-color-gray-4, #555)', strokeWidth: 1.5 },
        animated: n.status === 'pending',
      });
    }
  }

  if (showL2) {
    for (const epic of platform.l2.epics) {
      if (!epic.nodes?.length) continue;
      for (const en of epic.nodes) {
        const nodeId = `${epic.id}/${en.id}`;
        nodes.push({
          id: nodeId,
          type: 'pipeline',
          position: { x: 0, y: 0 },
          data: {
            id: en.id, status: en.status, layer: 'epic', gate: '',
            optional: false, depends: [], outputs: [], platform: platform.id,
            label: `${epic.id.split('-')[0]}:${en.id}`,
          },
        });
      }
      if (epic.nodes.length > 0) {
        edges.push({
          id: `epic-breakdown->${epic.id}/${epic.nodes[0].id}`,
          source: 'epic-breakdown',
          target: `${epic.id}/${epic.nodes[0].id}`,
          style: { stroke: 'var(--sl-color-gray-4, #555)', strokeWidth: 1, strokeDasharray: '5 3' },
        });
      }
      for (let i = 1; i < epic.nodes.length; i++) {
        edges.push({
          id: `${epic.id}/${epic.nodes[i - 1].id}->${epic.id}/${epic.nodes[i].id}`,
          source: `${epic.id}/${epic.nodes[i - 1].id}`,
          target: `${epic.id}/${epic.nodes[i].id}`,
          style: { stroke: 'var(--sl-color-gray-4, #555)', strokeWidth: 1 },
        });
      }
    }
  }

  return { nodes, edges };
}

// ── Main ──

export default function PipelineDAG({ platforms }: PipelineDAGProps) {
  const [showL2, setShowL2] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<PipelineNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading] = useState(true);
  const platform = platforms[0];

  const updateLayout = useCallback(async () => {
    if (!platform) return;
    setLoading(true);
    const graph = buildGraph(platform, showL2);
    try {
      const layouted = await computeLayout(graph.nodes, graph.edges);
      setNodes(layouted.nodes);
      setEdges(layouted.edges);
    } catch (err) {
      console.error('ELK layout failed:', err);
      setNodes(graph.nodes);
      setEdges(graph.edges);
    }
    setLoading(false);
  }, [showL2, platform, setNodes, setEdges]);

  useEffect(() => { updateLayout(); }, [updateLayout]);

  if (!platform) {
    return <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--sl-color-gray-3, #999)' }}>Sem dados.</div>;
  }

  return (
    <DAGErrorBoundary>
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div style={{
          display: 'flex', gap: '1rem', padding: '0.4rem 0.75rem', alignItems: 'center',
          borderBottom: '1px solid var(--sl-color-gray-5, #333)',
          background: 'var(--sl-color-gray-7, #0d0d0d)', fontSize: '0.8rem',
        }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--sl-color-gray-2, #ccc)' }}>
            <input type="checkbox" checked={showL2} onChange={(e) => setShowL2(e.target.checked)} />
            Mostrar L2
          </label>
          {loading && <span style={{ color: 'var(--sl-color-gray-4, #666)', fontSize: '0.7rem' }}>Layout...</span>}
        </div>
        <div style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes} fitView minZoom={0.3} maxZoom={2}
          >
            <Controls position="bottom-right" />
            <MiniMap
              nodeColor={(node) => STATUS_COLORS[(node.data as PipelineNodeData)?.status] || '#666'}
              style={{ background: 'var(--sl-color-gray-7, #1a1a1a)' }}
            />
            <Background color="var(--sl-color-gray-5, #333)" gap={20} />
          </ReactFlow>
        </div>
      </div>
    </DAGErrorBoundary>
  );
}
