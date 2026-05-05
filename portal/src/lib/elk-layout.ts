/**
 * ELK layout (epic 027 — T025).
 *
 * Build-time wrapper around `elkjs` that converts the structural graph
 * produced by `screen-flow.ts` into positioned xyflow nodes. Runs on the
 * Astro server during page render so the client bundle is ELK-free
 * (FR-017).
 *
 * Implementation notes:
 *   - Uses `elk.bundled.js` (single-file build), which works both on
 *     Node/SSG and as a fallback inside Vite without a workerUrl plugin.
 *   - Layered algorithm (FR-049: typical screen flows are hierarchical).
 *   - `meta.layout_direction` selects DOWN | RIGHT (default DOWN).
 *   - Node sizes follow the device profile (393×852 / 1440×900) so ELK
 *     accounts for chrome dimensions used by the renderer.
 *   - Hard timeout 30s with a 5s warn (FR-049). Anything longer aborts
 *     the build with a structured error so authors learn early.
 *   - Singleton ELK instance avoids worker-spawn cost across pages.
 */
import type {
  CanvasEdge,
  CanvasNode,
  CaptureProfile,
  ScreenFlow,
} from './screen-flow';

const PROFILE_DIMENSIONS: Record<CaptureProfile, { w: number; h: number }> = {
  'iphone-15': { w: 393, h: 852 },
  desktop: { w: 1440, h: 900 },
};

const CHROME_PADDING = { x: 16, y: 48 };

const ELK_LAYOUT_TIMEOUT_MS = 30_000; // FR-049 hard cap
const ELK_LAYOUT_WARN_MS = 5_000; // FR-049 warn threshold

interface ElkLikeNode {
  id: string;
  width: number;
  height: number;
  x?: number;
  y?: number;
}
interface ElkLikeGraph {
  id: string;
  layoutOptions: Record<string, string>;
  children: ElkLikeNode[];
  edges: Array<{ id: string; sources: string[]; targets: string[] }>;
}

// Lazy ELK loader (matches the pattern used by PipelineDAG.tsx).
let elkInstance: { layout: (g: ElkLikeGraph) => Promise<ElkLikeGraph> } | null =
  null;
async function getElk() {
  if (!elkInstance) {
    const mod = (await import('elkjs/lib/elk.bundled.js')) as unknown as {
      default: new () => { layout: (g: ElkLikeGraph) => Promise<ElkLikeGraph> };
    };
    const Ctor = mod.default ?? (mod as unknown as new () => never);
    elkInstance = new Ctor();
  }
  return elkInstance;
}

/**
 * Run ELK against the canvas graph and return positioned nodes.
 * `edges` pass through unchanged — xyflow re-routes them client-side.
 *
 * Throws `Error("ELK layout exceeded …")` when elkjs hangs longer than
 * `ELK_LAYOUT_TIMEOUT_MS`. Astro propagates the error so a corrupt YAML
 * can't silently ship a broken canvas.
 */
export async function applyElkLayout(
  flow: ScreenFlow,
  graph: { nodes: CanvasNode[]; edges: CanvasEdge[] },
  options: { signal?: AbortSignal } = {},
): Promise<{ nodes: CanvasNode[]; edges: CanvasEdge[] }> {
  if (graph.nodes.length === 0) return graph;

  const direction = flow.meta.layout_direction ?? 'DOWN';
  const dim = PROFILE_DIMENSIONS[flow.meta.capture_profile];

  const elkGraph: ElkLikeGraph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': direction,
      'elk.spacing.nodeNode': '64',
      'elk.layered.spacing.nodeNodeBetweenLayers': '96',
      'elk.edgeRouting': 'ORTHOGONAL',
    },
    children: graph.nodes.map((n) => ({
      id: n.id,
      width: dim.w + CHROME_PADDING.x * 2,
      height: dim.h + CHROME_PADDING.y * 2,
    })),
    edges: graph.edges.map((e) => ({
      id: e.id,
      sources: [e.source],
      targets: [e.target],
    })),
  };

  const elk = await getElk();
  const start = Date.now();
  const result = await runWithTimeout(
    elk.layout(elkGraph),
    ELK_LAYOUT_TIMEOUT_MS,
    options.signal,
  );
  const elapsed = Date.now() - start;

  if (elapsed > ELK_LAYOUT_WARN_MS) {
    // eslint-disable-next-line no-console
    console.warn(
      `[screen-flow] ELK layout took ${elapsed}ms — consider splitting the YAML or declaring manual positions (FR-049).`,
    );
  }

  const positioned = graph.nodes.map((n) => {
    const child = result.children.find((c) => c.id === n.id);
    return {
      ...n,
      position: child && typeof child.x === 'number' && typeof child.y === 'number'
        ? { x: child.x, y: child.y }
        : n.position,
    };
  });

  return { nodes: positioned, edges: graph.edges };
}

/**
 * Convenience wrapper used by Astro pages. Builds the structural graph
 * and applies ELK in one call.
 */
export async function buildPositionedGraph(flow: ScreenFlow): Promise<{
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}> {
  const { buildLayoutGraph } = await import('./screen-flow');
  const graph = buildLayoutGraph(flow);
  return applyElkLayout(flow, graph);
}

function runWithTimeout<T>(
  p: Promise<T>,
  ms: number,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(
        new Error(
          `ELK layout exceeded ${ms}ms — abort. Reduce screens, declare manual positions, or split the YAML by bounded context (FR-049).`,
        ),
      );
    }, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new Error('ELK layout aborted'));
      },
      { once: true },
    );
    p.then(
      (v) => {
        clearTimeout(timer);
        resolve(v);
      },
      (e) => {
        clearTimeout(timer);
        reject(e);
      },
    );
  });
}
