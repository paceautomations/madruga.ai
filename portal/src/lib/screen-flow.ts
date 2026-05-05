/**
 * Screen-flow YAML loader (epic 027 — T024).
 *
 * Build-time loader that parses `platforms/<name>/business/screen-flow.yaml`
 * (or the dev fixture under `?fixture=true`) into the canonical TypeScript
 * shapes consumed by the renderer (T029-T031). Keeps `js-yaml` and
 * `node:fs` calls server-side only — the client bundle stays small.
 *
 * The shapes mirror data-model.md (E1..E11) and are kept intentionally
 * close to the JSON-Schema vocabulary in `.specify/schemas/screen-flow.schema.json`
 * so a downstream renderer can pattern-match on `type` / `style` / `status`
 * without runtime checks.
 *
 * Wiring overview:
 *
 *   loadScreenFlow(platform)               // production
 *     ├── reads platforms/<p>/business/screen-flow.yaml
 *     └── returns ScreenFlow | null
 *
 *   loadScreenFlowFromFile(absPath)        // tests / fixture
 *     └── used by `?fixture=true` and the visual spec
 *
 *   buildLayoutGraph(flow, profile?)       // uses elk-layout.ts
 *     └── returns nodes + edges ready for xyflow
 */
import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';

// ── Vocabulary types (frozen to schema_version=1) ───────────────────────

export const COMPONENT_TYPES = [
  'heading',
  'text',
  'input',
  'button',
  'link',
  'list',
  'card',
  'image',
  'divider',
  'badge',
] as const;
export type ComponentType = (typeof COMPONENT_TYPES)[number];

export const EDGE_STYLES = ['success', 'error', 'neutral', 'modal'] as const;
export type EdgeStyle = (typeof EDGE_STYLES)[number];

export const CAPTURE_STATES = ['pending', 'captured', 'failed'] as const;
export type CaptureStatus = (typeof CAPTURE_STATES)[number];

export const CAPTURE_PROFILES = ['iphone-15', 'desktop'] as const;
export type CaptureProfile = (typeof CAPTURE_PROFILES)[number];

// ── Entity shapes (data-model.md) ───────────────────────────────────────

export interface BodyComponent {
  type: ComponentType;
  id?: string;
  text?: string;
  testid?: string;
  meta?: Record<string, unknown>;
}

export interface ScreenMeta {
  route?: string;
  entrypoint?: string;
  capture_profile?: CaptureProfile;
  wait_for?: string;
}

export interface CaptureRecord {
  captured_at: string;
  app_version: string;
  image_md5: string;
  viewport: { w: number; h: number };
}

export interface CaptureFailure {
  reason:
    | 'timeout'
    | 'auth_expired'
    | 'network_error'
    | 'app_crash'
    | 'sw_cleanup_failed'
    | 'mock_route_unmatched'
    | 'unknown';
  occurred_at: string;
  retry_count: number;
  last_error_message?: string;
}

export interface Screen {
  id: string;
  title: string;
  status: CaptureStatus;
  body: BodyComponent[];
  image?: string;
  position?: { x: number; y: number };
  meta?: ScreenMeta;
  capture?: CaptureRecord;
  failure?: CaptureFailure;
}

export interface Flow {
  from: string;
  to: string;
  on: string;
  style: EdgeStyle;
  label?: string;
}

export interface ScreenFlow {
  schema_version: 1;
  meta: {
    device: 'mobile' | 'desktop';
    capture_profile: CaptureProfile;
    layout_direction?: 'DOWN' | 'RIGHT';
  };
  screens: Screen[];
  flows: Flow[];
}

// ── Loaders ─────────────────────────────────────────────────────────────

/**
 * Locate the repo root from anywhere under portal/. Astro builds run with
 * cwd at portal/ so we walk one level up; tests under src/test may also
 * be invoked from portal/.
 */
function repoRoot(fromCwd = process.cwd()): string {
  // portal/ has package.json + ../platforms/. Walk up until we find one
  // containing both `platforms/` and `.specify/`.
  let dir = path.resolve(fromCwd);
  for (let depth = 0; depth < 6; depth++) {
    if (
      fs.existsSync(path.join(dir, 'platforms')) &&
      fs.existsSync(path.join(dir, '.specify'))
    ) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  // Best-effort fallback for unusual setups (e.g. Vite SSR).
  return path.resolve(fromCwd, '..');
}

/**
 * Read and parse a YAML file from disk, returning the shape unchanged.
 * Throws on YAML syntax errors so build-time failures surface loudly.
 */
export function loadScreenFlowFromFile(absPath: string): ScreenFlow {
  const raw = fs.readFileSync(absPath, 'utf8');
  const parsed = yaml.load(raw) as ScreenFlow;
  if (!parsed || typeof parsed !== 'object') {
    throw new Error(`screen-flow YAML at ${absPath} is empty or not an object`);
  }
  if (parsed.schema_version !== 1) {
    throw new Error(
      `screen-flow YAML at ${absPath}: unsupported schema_version=${
        (parsed as { schema_version?: unknown }).schema_version
      }. Only v1 is supported.`,
    );
  }
  return parsed;
}

/**
 * Production loader. Returns `null` when the platform opted out (file
 * missing) so callers can hide the "Screens" entry from the sidebar.
 */
export function loadScreenFlow(platform: string): ScreenFlow | null {
  const root = repoRoot();
  const candidate = path.join(
    root,
    'platforms',
    platform,
    'business',
    'screen-flow.yaml',
  );
  if (!fs.existsSync(candidate)) return null;
  return loadScreenFlowFromFile(candidate);
}

/**
 * Dev/test fixture loader. Resolves `?fixture=true` in pages and the
 * Phase 3 visual spec, decoupling the renderer from the still-pending
 * Phase 4 capture script.
 */
export function loadFixtureScreenFlow(): ScreenFlow {
  const root = repoRoot();
  const fixturePath = path.join(
    root,
    'portal',
    'src',
    'test',
    'fixtures',
    'screen-flow.example.yaml',
  );
  return loadScreenFlowFromFile(fixturePath);
}

// ── Layout graph builder (consumed by ScreenFlowCanvas) ─────────────────

export interface CanvasNode {
  id: string;
  type: 'screen';
  position: { x: number; y: number };
  data: {
    screen: Screen;
    profile: CaptureProfile;
  };
}

export interface CanvasEdge {
  id: string;
  source: string;
  target: string;
  type: 'action';
  data: {
    style: EdgeStyle;
    label?: string;
    on: string;
  };
}

/**
 * Materialise xyflow-ready nodes + edges WITHOUT running ELK. Layout is
 * applied by `applyElkLayout` in `elk-layout.ts` (build-time). Nodes ship
 * with `position={x:0,y:0}` until then.
 */
export function buildLayoutGraph(flow: ScreenFlow): {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
} {
  const profile = flow.meta.capture_profile;
  const nodes: CanvasNode[] = flow.screens.map((s) => ({
    id: s.id,
    type: 'screen' as const,
    position: s.position ?? { x: 0, y: 0 },
    data: { screen: s, profile },
  }));
  const edges: CanvasEdge[] = flow.flows.map((f, i) => ({
    id: `${f.from}--${f.on}->${f.to}-${i}`,
    source: f.from,
    target: f.to,
    type: 'action' as const,
    data: { style: f.style, label: f.label, on: f.on },
  }));
  return { nodes, edges };
}

// ── Convenience helpers ─────────────────────────────────────────────────

export function isOptedOut(platform: string): boolean {
  return loadScreenFlow(platform) === null;
}
