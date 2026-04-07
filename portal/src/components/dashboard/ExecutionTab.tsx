import { useState, useMemo } from 'react';
import PlatformCards from './PlatformCards';
import PipelineDAG from './PipelineDAG';
import { NODE_LABELS, resolveNodeHref } from '../../lib/constants';

// ── Types ──

interface PlatformData {
  id: string;
  title: string;
  lifecycle: string;
  l1: { total: number; done: number; progress_pct: number; nodes: NodeData[] };
  l2: { epics: EpicData[] };
}

interface NodeData {
  id: string;
  status: string;
  layer: string;
  gate: string;
  optional: boolean;
  depends: string[];
  outputs: string[];
}

interface EpicData {
  id: string;
  title: string;
  status: string;
  total: number;
  done: number;
  progress_pct: number;
  nodes: { id: string; status: string }[];
}

interface ExecutionTabProps {
  allPlatforms: PlatformData[];
  initialPlatformId: string;
}

// ── Constants ──

const LAYERS = [
  { id: 'business', label: 'Business', color: '#3b82f6' },
  { id: 'research', label: 'Research', color: '#a78bfa' },
  { id: 'engineering', label: 'Engineering', color: '#10b981' },
  { id: 'planning', label: 'Planning', color: '#f59e0b' },
];

const GATE_ICON: Record<string, string> = {
  human: '\u{1F464}', auto: '\u26A1', '1-way-door': '\u{1F6AA}', 'auto-escalate': '\u26A1\u2191',
};

const PHASES = [
  { id: 'backlog', label: 'Backlog', stages: [] as string[] },
  { id: 'specifying', label: 'Specifying', stages: ['epic-context', 'specify', 'clarify'] },
  { id: 'planning', label: 'Planning', stages: ['plan', 'tasks', 'analyze'] },
  { id: 'building', label: 'Building', stages: ['implement', 'analyze-post', 'judge'] },
  { id: 'shipping', label: 'Shipping', stages: ['qa', 'reconcile'] },
  { id: 'shipped', label: 'Shipped', stages: [] as string[] },
];

const ALL_L2_STAGES = ['epic-context', 'specify', 'clarify', 'plan', 'tasks', 'analyze', 'implement', 'analyze-post', 'judge', 'qa', 'reconcile'];

// ── Helpers (same logic as original Astro frontmatter) ──

function groupByLayer(nodes: NodeData[]) {
  return LAYERS.map((layer) => ({
    ...layer,
    nodes: nodes.filter((n) => n.layer === layer.id),
    done: nodes.filter((n) => n.layer === layer.id && n.status === 'done').length,
    total: nodes.filter((n) => n.layer === layer.id).length,
  }));
}

function findNextStep(nodes: NodeData[]) {
  const doneIds = new Set(nodes.filter((n) => n.status === 'done').map((n) => n.id));
  for (const n of nodes) {
    if (n.status !== 'done' && n.status !== 'skipped') {
      if ((n.depends || []).every((d) => doneIds.has(d))) return n;
    }
  }
  return null;
}

function getEpicPhase(epic: EpicData): { phaseId: string; subStage: string } {
  if (epic.status === 'shipped') return { phaseId: 'shipped', subStage: '' };
  if (!epic.nodes || epic.nodes.length === 0) return { phaseId: 'backlog', subStage: '' };
  const doneIds = new Set(epic.nodes.filter((n) => n.status === 'done' || n.status === 'skipped').map((n) => n.id));
  if (doneIds.size >= ALL_L2_STAGES.length) return { phaseId: 'shipped', subStage: '' };
  if (doneIds.size === 0) return { phaseId: 'backlog', subStage: '' };
  let lastDoneIdx = -1;
  for (let i = ALL_L2_STAGES.length - 1; i >= 0; i--) {
    if (doneIds.has(ALL_L2_STAGES[i])) { lastDoneIdx = i; break; }
  }
  const nextStage = lastDoneIdx < ALL_L2_STAGES.length - 1 ? ALL_L2_STAGES[lastDoneIdx + 1] : ALL_L2_STAGES[lastDoneIdx];
  for (const phase of PHASES) {
    if (phase.stages.includes(nextStage)) return { phaseId: phase.id, subStage: nextStage };
  }
  return { phaseId: 'backlog', subStage: '' };
}

function buildKanban(epics: EpicData[]) {
  const columns: Record<string, (EpicData & { subStage: string })[]> = {};
  for (const p of PHASES) columns[p.id] = [];
  for (const epic of epics) {
    const { phaseId, subStage } = getEpicPhase(epic);
    columns[phaseId]?.push({ ...epic, subStage });
  }
  return columns;
}

// ── Styles (matching original CSS using inline styles + CSS vars) ──

const S = {
  hero: { display: 'flex', alignItems: 'center', gap: '1.5rem', marginBottom: '1.75rem', paddingBottom: '1.25rem', borderBottom: '1px solid var(--sl-color-gray-5, #333)', flexWrap: 'wrap' as const, margin: 0 },
  stat: { display: 'flex', flexDirection: 'column' as const, alignItems: 'center', padding: '0 1.2rem', borderRight: '1px solid var(--sl-color-gray-5, #333)', margin: 0 },
  statLast: { borderRight: 'none', paddingRight: 0 },
  statValue: { fontSize: '1.6rem', fontWeight: 800, color: 'var(--sl-color-white, #fff)', lineHeight: 1, fontVariantNumeric: 'tabular-nums' as const, margin: 0 },
  statUnit: { fontSize: '0.9rem', fontWeight: 600, color: 'var(--sl-color-gray-3, #888)' },
  statLabel: { fontSize: '0.6rem', fontWeight: 500, textTransform: 'uppercase' as const, letterSpacing: '0.08em', color: 'var(--sl-color-gray-4, #666)', marginTop: '0.3rem', whiteSpace: 'nowrap' as const },
  nextStep: { marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.45rem 0.75rem', background: 'var(--sl-color-gray-6, #181818)', border: '1px solid var(--sl-color-gray-5, #333)', borderRadius: 6, margin: 0 },
  nextLabel: { fontSize: '0.6rem', textTransform: 'uppercase' as const, letterSpacing: '0.08em', color: '#22c55e', fontWeight: 700, margin: 0 },
  nextCommand: { fontSize: '0.78rem', padding: '0.12rem 0.4rem', background: 'var(--sl-color-gray-7, #111)', borderRadius: 4, color: 'var(--sl-color-white, #fff)', fontWeight: 500, margin: 0 },
  nextDesc: { fontSize: '0.68rem', color: 'var(--sl-color-gray-3, #888)', margin: 0 },
  section: { marginBottom: '2rem' },
  sectionHeader: { display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginBottom: '0.6rem' },
  sectionTitle: { margin: 0, fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: '0.08em', color: 'var(--sl-color-gray-3, #888)' },
  sectionMeta: { fontSize: '0.68rem', color: 'var(--sl-color-gray-4, #666)', margin: 0 },
  progressTrack: { background: 'var(--sl-color-gray-5, #333)', borderRadius: 2, height: 3, overflow: 'hidden' as const, margin: '0 0 0.9rem 0' },
  layerGrid: { display: 'flex', gap: '0.5rem', alignItems: 'stretch' },
  nodeRow: { display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.2rem 0.25rem', borderRadius: 3, fontSize: '0.78rem', textDecoration: 'none', color: 'inherit', margin: 0 },
  staleAlert: { display: 'flex', alignItems: 'flex-start', gap: '0.5rem', padding: '0.55rem 0.75rem', background: 'color-mix(in srgb, #f97316 8%, var(--sl-color-gray-7, #111))', border: '1px solid color-mix(in srgb, #f97316 40%, var(--sl-color-gray-5, #333))', borderLeft: '3px solid #f97316', borderRadius: 6, marginBottom: '1rem', fontSize: '0.75rem', color: 'var(--sl-color-gray-2, #ccc)' },
  kanbanBoard: { display: 'flex', gap: '0.4rem', alignItems: 'stretch' },
  colHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.3rem 0.45rem', margin: '0 !important', background: 'var(--sl-color-gray-6, #181818)', borderRadius: '6px 6px 0 0', border: '1px solid var(--sl-color-gray-5, #333)', borderBottom: 'none' },
  colTitle: { fontSize: '0.6rem', fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: '0.06em', color: 'var(--sl-color-gray-4, #666)', margin: 0 },
  colCount: { fontSize: '0.55rem', background: 'var(--sl-color-gray-3, #888)', color: 'var(--sl-color-black, #000)', borderRadius: 8, padding: '0.05rem 0.3rem', fontWeight: 800, minWidth: 14, textAlign: 'center' as const, margin: 0 },
  colBody: { flex: 1, margin: 0, padding: '0.3rem', background: 'var(--sl-color-gray-7, #111)', border: '1px solid var(--sl-color-gray-5, #333)', borderRadius: '0 0 6px 6px', display: 'flex', flexDirection: 'column' as const, gap: '0.25rem' },
  epicCard: { display: 'block', padding: '0.45rem 0.5rem', background: 'var(--sl-color-gray-6, #181818)', border: '1px solid var(--sl-color-gray-5, #333)', borderRadius: 5, textDecoration: 'none', color: 'var(--sl-color-white, #fff)', margin: 0 },
  footerMeta: { fontSize: '0.65rem', color: 'var(--sl-color-gray-4, #666)', textAlign: 'right' as const, marginTop: '0.75rem', opacity: 0.6 },
};

const STATUS_ICON: Record<string, { icon: string; color: string }> = {
  done: { icon: '\u2713', color: '#22c55e' },
  pending: { icon: '\u25CB', color: '#f59e0b' },
  blocked: { icon: '\u2717', color: '#ef4444' },
  stale: { icon: '\u26A0', color: '#f97316' },
  skipped: { icon: '\u2013', color: '#6b7280' },
};

// ── Main Component ──

export default function ExecutionTab({ allPlatforms, initialPlatformId }: ExecutionTabProps) {
  const [selectedId, setSelectedId] = useState(initialPlatformId);

  const platform = allPlatforms.find((p) => p.id === selectedId);
  const hasData = !!platform;

  const summaries = useMemo(() => allPlatforms.map((p) => ({
    id: p.id,
    title: p.title || p.id,
    lifecycle: p.lifecycle || 'unknown',
    l1_progress_pct: p.l1?.progress_pct || 0,
    l1_total: p.l1?.total || 0,
    l1_done: p.l1?.done || 0,
    active_epics: (p.l2?.epics || []).filter((e) => e.status === 'in_progress').length,
    total_epics: (p.l2?.epics || []).length,
  })), [allPlatforms]);

  const layers = hasData ? groupByLayer(platform.l1.nodes) : [];
  const staleNodes = hasData ? platform.l1.nodes.filter((n) => n.status === 'stale') : [];
  const nextStep = hasData ? findNextStep(platform.l1.nodes) : null;
  const kanban = hasData ? buildKanban(platform.l2.epics) : {};
  const totalEpics = hasData ? platform.l2.epics.length : 0;
  const shippedEpics = hasData ? (kanban['shipped']?.length || 0) : 0;
  const activeEpics = hasData ? totalEpics - (kanban['backlog']?.length || 0) - shippedEpics : 0;

  const handleSelect = (id: string) => {
    setSelectedId(id);
    // Update URL without reload
    const url = new URL(window.location.href);
    url.searchParams.set('platform', id);
    window.history.replaceState(null, '', url.toString());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', margin: 0 }}>
      {/* Platform cards */}
      <div style={{ margin: 0 }}>
        <div style={S.sectionHeader}>
          <h2 style={S.sectionTitle}>Platforms</h2>
          <span style={S.sectionMeta}>{allPlatforms.length} platforms</span>
        </div>
        <PlatformCards platforms={summaries} selected={selectedId} onSelect={handleSelect} />
      </div>

      {!hasData ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--sl-color-gray-3, #888)', margin: 0 }}>
          <p style={{ margin: 0 }}>No pipeline data for <strong>{selectedId}</strong>. Run <code>python3 .specify/scripts/platform_cli.py status --all --json</code></p>
        </div>
      ) : (
        <>
          {/* Hero stats */}
          <div style={{ ...S.hero, marginBottom: '1.75rem', paddingBottom: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 0, margin: 0 }}>
              {[
                { value: `${Math.round(platform.l1.progress_pct)}`, unit: '%', label: 'L1 Completo' },
                { value: `${totalEpics}`, unit: '', label: 'Epics' },
                { value: `${activeEpics}`, unit: '', label: 'Em progresso' },
                { value: `${shippedEpics}`, unit: '', label: 'Shipped' },
              ].map((s, i, arr) => (
                <div key={s.label} style={{ ...S.stat, ...(i === arr.length - 1 ? S.statLast : {}), ...(i === 0 ? { paddingLeft: 0 } : {}) }}>
                  <span style={S.statValue}>{s.value}{s.unit && <span style={S.statUnit}>{s.unit}</span>}</span>
                  <span style={S.statLabel}>{s.label}</span>
                </div>
              ))}
            </div>
            {nextStep && (
              <div style={S.nextStep}>
                <span style={S.nextLabel}>Proximo passo</span>
                <code style={S.nextCommand}>/{nextStep.id} {selectedId}</code>
                <span style={S.nextDesc}>{NODE_LABELS[nextStep.id] || nextStep.id} · {nextStep.gate} gate</span>
              </div>
            )}
            {!nextStep && platform.l1.progress_pct >= 100 && (
              <div style={S.nextStep}>
                <span style={S.nextLabel}>L1 completo — pronto para epics</span>
              </div>
            )}
          </div>

          {/* Stale alert */}
          {staleNodes.length > 0 && (
            <div style={S.staleAlert}>
              <span style={{ color: '#f97316', fontSize: '0.9rem', flexShrink: 0, lineHeight: 1.3, margin: 0 }}>&#9888;</span>
              <div style={{ flex: 1, margin: 0 }}>
                <strong>{staleNodes.length} artefato(s) desatualizado(s)</strong> — dependencias mudaram apos a geracao.
                <span style={{ display: 'block', marginTop: '0.2rem', fontFamily: 'var(--sl-font-mono, monospace)', fontSize: '0.68rem', color: 'var(--sl-color-gray-3, #888)' }}>
                  Re-execute: {staleNodes.map((n) => `/${n.id}`).join(', ')}
                </span>
              </div>
            </div>
          )}

          {/* L1 Foundation */}
          <div style={S.section}>
            <div style={S.sectionHeader}>
              <h2 style={S.sectionTitle}>Fundacao da Plataforma</h2>
              <span style={S.sectionMeta}>{platform.l1.done}/{platform.l1.total} nos</span>
            </div>
            <div style={S.progressTrack}>
              <div style={{ height: '100%', width: `${platform.l1.progress_pct}%`, background: '#22c55e', borderRadius: 2, margin: 0 }} />
            </div>
            <div style={S.layerGrid}>
              {layers.map((layer) => (
                <div
                  key={layer.id}
                  style={{
                    flex: 1, margin: 0, border: '1px solid var(--sl-color-gray-5, #333)',
                    borderLeft: `3px solid ${layer.color}`, borderRadius: 6,
                    padding: '0.6rem 0.65rem', background: 'var(--sl-color-gray-7, #111)',
                    display: 'flex', flexDirection: 'column', minWidth: 0,
                    ...(layer.done === layer.total ? { background: `color-mix(in srgb, ${layer.color} 4%, var(--sl-color-gray-7, #111))` } : {}),
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem', paddingBottom: '0.35rem', borderBottom: '1px solid var(--sl-color-gray-5, #333)' }}>
                    <h3 style={{ margin: 0, fontSize: '0.75rem', fontWeight: 700, color: layer.color }}>{layer.label}</h3>
                    <span style={{ fontSize: '0.65rem', color: 'var(--sl-color-gray-4, #666)', fontVariantNumeric: 'tabular-nums', fontWeight: 600, margin: 0 }}>{layer.done}/{layer.total}</span>
                  </div>
                  <div style={{ flex: 1, margin: 0 }}>
                    {layer.nodes.map((n) => {
                      const si = STATUS_ICON[n.status] || STATUS_ICON.pending;
                      const href = n.status === 'done' && n.outputs?.length ? resolveNodeHref(selectedId, n.id, n.outputs[0]) : undefined;
                      return (
                        <a key={n.id} href={href} style={{ ...S.nodeRow, ...(n.status === 'skipped' ? { textDecoration: 'line-through', color: 'var(--sl-color-gray-4, #666)' } : {}) }} title={`${n.id}: ${n.status} (${n.gate})`}>
                          <span style={{ width: 14, textAlign: 'center', fontWeight: 700, fontSize: '0.7rem', flexShrink: 0, color: si.color, margin: 0 }}>{si.icon}</span>
                          <span style={{ flex: 1, color: n.status === 'done' ? 'var(--sl-color-white, #fff)' : 'var(--sl-color-gray-2, #ccc)', margin: 0 }}>{NODE_LABELS[n.id] || n.id}</span>
                          {n.optional && <span style={{ fontSize: '0.5rem', padding: '0.05rem 0.25rem', borderRadius: 3, background: 'var(--sl-color-gray-6, #181818)', color: 'var(--sl-color-gray-4, #666)', textTransform: 'uppercase', fontWeight: 700, margin: 0 }}>opt</span>}
                          <span style={{ fontSize: '0.6rem', flexShrink: 0, opacity: 0.7, margin: 0 }}>{GATE_ICON[n.gate] || ''}</span>
                        </a>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Kanban */}
          <div style={S.section}>
            <div style={S.sectionHeader}>
              <h2 style={S.sectionTitle}>Epics</h2>
              <span style={S.sectionMeta}>{totalEpics} epics · {activeEpics} ativos</span>
            </div>
            <div style={S.kanbanBoard}>
              {PHASES.map((phase) => {
                const cards = kanban[phase.id] || [];
                return (
                  <div key={phase.id} style={{ flex: 1, margin: 0, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                    <div style={S.colHeader}>
                      <span style={S.colTitle}>{phase.label}</span>
                      {cards.length > 0 && <span style={S.colCount}>{cards.length}</span>}
                    </div>
                    <div style={S.colBody}>
                      {cards.map((epic) => (
                        <a key={epic.id} href={`/${selectedId}/epics/${epic.id}/pitch/`} style={{ ...S.epicCard, ...(phase.id === 'shipped' ? { borderLeft: '2px solid #22c55e', opacity: 0.65 } : {}) }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.1rem' }}>
                            <span style={{ fontSize: '0.6rem', color: 'var(--sl-color-gray-4, #666)', fontWeight: 700, fontFamily: 'var(--sl-font-mono, monospace)', margin: 0 }}>{epic.id.split('-')[0]}</span>
                            {epic.subStage && <span style={{ fontSize: '0.5rem', padding: '0.05rem 0.25rem', borderRadius: 3, background: 'var(--sl-color-gray-7, #111)', color: 'var(--sl-color-gray-4, #666)', textTransform: 'uppercase', fontWeight: 700, margin: 0 }}>{epic.subStage}</span>}
                          </div>
                          <span style={{ display: 'block', fontSize: '0.72rem', lineHeight: 1.3, color: 'var(--sl-color-gray-2, #ccc)', margin: 0 }}>{epic.title}</span>
                          {epic.done > 0 && (
                            <div style={{ marginTop: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                              <div style={{ flex: 1, height: 2, background: 'var(--sl-color-gray-5, #333)', borderRadius: 1, overflow: 'hidden', margin: 0 }}>
                                <div style={{ height: '100%', width: `${epic.progress_pct}%`, background: '#22c55e', borderRadius: 1, margin: 0 }} />
                              </div>
                              <span style={{ fontSize: '0.55rem', color: 'var(--sl-color-gray-4, #666)', fontVariantNumeric: 'tabular-nums', margin: 0 }}>{epic.done}/{epic.total}</span>
                            </div>
                          )}
                        </a>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* DAG */}
          <div style={S.section}>
            <details style={{ border: '1px solid var(--sl-color-gray-5, #333)', borderRadius: 6, overflow: 'hidden' }}>
              <summary style={{ display: 'flex', alignItems: 'baseline', gap: '0.6rem', padding: '0.6rem 0.85rem', cursor: 'pointer', background: 'var(--sl-color-gray-6, #181818)', userSelect: 'none' }}>
                <h2 style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600, color: 'var(--sl-color-gray-2, #ccc)' }}>Pipeline DAG</h2>
                <span style={S.sectionMeta}>Visualizacao interativa de dependencias</span>
              </summary>
              <div style={{ height: 550, background: 'var(--sl-color-gray-7, #111)' }}>
                <PipelineDAG platforms={[platform]} />
              </div>
            </details>
          </div>
        </>
      )}
    </div>
  );
}
