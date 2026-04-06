import type { EvalScore } from './ObservabilityDashboard';

// ── Types ──

interface EvalsTabProps {
  scores: EvalScore[];
  connected: boolean;
}

type Dimension = EvalScore['dimension'];

const DIMENSIONS: { key: Dimension; label: string }[] = [
  { key: 'quality', label: 'Quality' },
  { key: 'adherence_to_spec', label: 'Adherence' },
  { key: 'completeness', label: 'Completeness' },
  { key: 'cost_efficiency', label: 'Cost Eff.' },
];

// ── Helpers ──

/** Group scores by node_id, then by dimension, ordered by evaluated_at ascending. */
function buildScoreboard(scores: EvalScore[]) {
  const map = new Map<string, Map<Dimension, number[]>>();

  // Sort oldest-first so arrays are chronological
  const sorted = [...scores].sort(
    (a, b) => new Date(a.evaluated_at).getTime() - new Date(b.evaluated_at).getTime(),
  );

  for (const s of sorted) {
    if (!map.has(s.node_id)) map.set(s.node_id, new Map());
    const dimMap = map.get(s.node_id)!;
    if (!dimMap.has(s.dimension)) dimMap.set(s.dimension, []);
    dimMap.get(s.dimension)!.push(s.score);
  }

  // Sort nodes alphabetically
  const nodes = [...map.keys()].sort();

  return { nodes, map };
}

function latestScore(values: number[] | undefined): number | null {
  if (!values || values.length === 0) return null;
  return values[values.length - 1];
}

function avgScore(values: number[] | undefined): number | null {
  if (!values || values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function scoreColor(score: number): string {
  if (score >= 7) return '#4CAF50';
  if (score >= 5) return '#FFC107';
  return '#F44336';
}

function scoreBg(score: number): string {
  if (score >= 7) return '#4CAF5018';
  if (score >= 5) return '#FFC10718';
  return '#F4433618';
}

// ── Sparkline SVG ──

const SPARK_W = 60;
const SPARK_H = 20;
const SPARK_PAD = 2;

/** Render a tiny sparkline as an SVG path for the last N scores. */
function Sparkline({ values }: { values: number[] }) {
  const data = values.slice(-10); // last 10 runs
  if (data.length < 2) return null;

  const minY = 0;
  const maxY = 10;
  const xStep = (SPARK_W - SPARK_PAD * 2) / (data.length - 1);
  const yRange = maxY - minY || 1;

  const points = data.map((v, i) => {
    const x = SPARK_PAD + i * xStep;
    const y = SPARK_PAD + (1 - (v - minY) / yRange) * (SPARK_H - SPARK_PAD * 2);
    return { x, y };
  });

  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const last = data[data.length - 1];
  const color = scoreColor(last);

  return (
    <svg
      width={SPARK_W}
      height={SPARK_H}
      viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
      style={{ display: 'block' }}
      role="img"
      aria-label={`Trend: ${data.join(', ')}`}
    >
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      {/* Dot on latest value */}
      <circle cx={points[points.length - 1].x} cy={points[points.length - 1].y} r={2} fill={color} />
    </svg>
  );
}

// ── Score Cell ──

function ScoreCell({ values }: { values: number[] | undefined }) {
  const latest = latestScore(values);
  if (latest == null) {
    return (
      <td style={tdStyle}>
        <span style={{ color: 'var(--sl-color-gray-4, #666)', fontSize: '0.75rem' }}>--</span>
      </td>
    );
  }

  const needsAttention = latest < 5;

  return (
    <td
      style={{
        ...tdStyle,
        background: needsAttention ? '#F4433610' : undefined,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span
          style={{
            display: 'inline-block',
            padding: '0.1rem 0.4rem',
            borderRadius: 4,
            fontSize: '0.8rem',
            fontWeight: 600,
            color: scoreColor(latest),
            background: scoreBg(latest),
            border: `1px solid ${scoreColor(latest)}30`,
            minWidth: 28,
            textAlign: 'center',
          }}
        >
          {latest.toFixed(1)}
        </span>
        {values && values.length >= 2 && <Sparkline values={values} />}
        {needsAttention && (
          <span
            style={{ fontSize: '0.65rem', color: '#F44336', fontWeight: 500 }}
            title="Score below 5 — needs attention"
          >
            !
          </span>
        )}
      </div>
    </td>
  );
}

// ── Styles ──

const tableStyle: React.CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '0.8rem',
};

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.5rem 0.75rem',
  borderBottom: '1px solid var(--sl-color-gray-5, #333)',
  color: 'var(--sl-color-gray-3, #888)',
  fontWeight: 500,
  fontSize: '0.75rem',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.04em',
};

const tdStyle: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  borderBottom: '1px solid var(--sl-color-gray-6, #222)',
  color: 'var(--sl-color-gray-2, #ccc)',
};

// ── Node Row ──

function NodeRow({
  nodeId,
  dimMap,
  hasAttention,
}: {
  nodeId: string;
  dimMap: Map<Dimension, number[]>;
  hasAttention: boolean;
}) {
  return (
    <tr
      style={{
        background: hasAttention ? '#F443360A' : undefined,
      }}
    >
      <td
        style={{
          ...tdStyle,
          fontFamily: 'monospace',
          fontSize: '0.75rem',
          whiteSpace: 'nowrap',
        }}
      >
        {nodeId}
        {hasAttention && (
          <span
            style={{
              marginLeft: '0.4rem',
              padding: '0.05rem 0.35rem',
              borderRadius: 9999,
              fontSize: '0.6rem',
              fontWeight: 600,
              background: '#F4433615',
              color: '#F44336',
              border: '1px solid #F4433630',
            }}
          >
            attention
          </span>
        )}
      </td>
      {DIMENSIONS.map((dim) => (
        <ScoreCell key={dim.key} values={dimMap.get(dim.key)} />
      ))}
      <td style={{ ...tdStyle, fontSize: '0.75rem', color: 'var(--sl-color-gray-3, #888)' }}>
        {computeAvg(dimMap)}
      </td>
    </tr>
  );
}

function computeAvg(dimMap: Map<Dimension, number[]>): string {
  const avgs: number[] = [];
  for (const dim of DIMENSIONS) {
    const a = avgScore(dimMap.get(dim.key));
    if (a != null) avgs.push(a);
  }
  if (avgs.length === 0) return '--';
  return (avgs.reduce((s, v) => s + v, 0) / avgs.length).toFixed(1);
}

// ── Main Component ──

export default function EvalsTab({ scores, connected }: EvalsTabProps) {
  if (!scores.length) {
    return (
      <div
        style={{
          padding: '2rem',
          textAlign: 'center',
          color: 'var(--sl-color-gray-4, #666)',
          fontSize: '0.85rem',
        }}
      >
        {connected ? 'No eval scores found' : 'Waiting for Easter connection...'}
      </div>
    );
  }

  const { nodes, map } = buildScoreboard(scores);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Legend */}
      <div style={{ display: 'flex', gap: '1rem', fontSize: '0.7rem', color: 'var(--sl-color-gray-3, #888)' }}>
        <span><span style={{ color: '#4CAF50' }}>&#9679;</span> &ge; 7 Good</span>
        <span><span style={{ color: '#FFC107' }}>&#9679;</span> &ge; 5 Fair</span>
        <span><span style={{ color: '#F44336' }}>&#9679;</span> &lt; 5 Needs attention</span>
      </div>

      {/* Scoreboard Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>Node</th>
              {DIMENSIONS.map((dim) => (
                <th key={dim.key} style={thStyle}>{dim.label}</th>
              ))}
              <th style={thStyle}>Avg</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((nodeId) => {
              const dimMap = map.get(nodeId)!;
              const hasAttention = DIMENSIONS.some((dim) => {
                const latest = latestScore(dimMap.get(dim.key));
                return latest != null && latest < 5;
              });
              return (
                <NodeRow key={nodeId} nodeId={nodeId} dimMap={dimMap} hasAttention={hasAttention} />
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
