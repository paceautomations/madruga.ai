/**
 * Shared constants for the portal.
 * Single source of truth for route overrides and node navigation.
 */

/** Maps pipeline node IDs to portal route overrides (when default path resolution won't work). */
export const NODE_ROUTE_OVERRIDES: Record<string, string> = {
  'platform-new': '/control-panel/',
  'epic-breakdown': '/planning/roadmap/',
};

/** Human-readable labels for L1 pipeline nodes. */
export const NODE_LABELS: Record<string, string> = {
  'platform-new': 'Platform Setup',
  'vision': 'Vision',
  'solution-overview': 'Solution Overview',
  'business-process': 'Business Process',
  'tech-research': 'Tech Research',
  'codebase-map': 'Codebase Map',
  'adr': 'ADRs',
  'blueprint': 'Blueprint',
  'domain-model': 'Domain Model',
  'containers': 'Containers',
  'context-map': 'Context Map',
  'epic-breakdown': 'Epic Breakdown',
  'roadmap': 'Roadmap',
};

/** Resolve a pipeline node's output path to a portal URL. */
export function resolveNodeHref(platform: string, nodeId: string, output: string): string {
  const override = NODE_ROUTE_OVERRIDES[nodeId];
  if (override) return `/${platform}${override}`;
  if (output.startsWith('decisions/')) return `/${platform}/decisions/`;
  if (output.match(/^epics\/.*\/pitch\.md$/)) {
    return `/${platform}/${output.replace(/\.md$/, '')}/`;
  }
  return `/${platform}/${output.replace(/\.md$/, '')}/`;
}
