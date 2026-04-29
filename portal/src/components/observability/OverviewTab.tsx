import { useState, useMemo } from 'react';
import type { RunEntry, StatsData, SessionsData } from './ObservabilityDashboard';
import { formatDuration, formatCost, formatCostRounded, formatTime, formatTokens } from './formatters';
import EasterStatusBanner from './EasterStatusBanner';
import ActiveSessionsPanel from './ActiveSessionsPanel';

const EVAL_TIP_CSS = `
.eval-tip { position: relative; }
.eval-tip::after {
  content: attr(data-tip);
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
  font-size: 0.65rem;
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  color: var(--sl-color-gray-2, #ccc);
  background: var(--sl-color-gray-6, #1a1a1a);
  border: 1px solid var(--sl-color-gray-5, #333);
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.1s;
  z-index: 10;
}
.eval-tip:hover::after { opacity: 1; }
`;

// ── Types ──

interface OverviewTabProps {
  runs: RunEntry[];
  stats: StatsData | null;
  sessions: SessionsData | null;
  connected: boolean;
  platformIds?: string[];
}

type StatusFilter = 'all' | 'running' | 'completed' | 'failed' | 'cancelled';

type Dimension = 'quality' | 'adherence_to_spec' | 'completeness' | 'cost_efficiency';

const DIMENSIONS: { key: Dimension; short: string; tip: string; legend: string }[] = [
  { key: 'quality', short: 'Q', tip: 'Quality — output sem erros / Judge score (0-10)', legend: 'Quality (sem erros)' },
  { key: 'adherence_to_spec', short: 'A', tip: 'Adherence — seções markdown esperadas presentes (0-10)', legend: 'Adherence (seções esperadas)' },
  { key: 'completeness', short: 'C', tip: 'Completeness — linhas produzidas vs esperado (0-10)', legend: 'Completeness (linhas)' },
  { key: 'cost_efficiency', short: 'E', tip: 'Efficiency — custo vs média histórica (0-10)', legend: 'Efficiency (custo)' },
];

const STATUS_FILTERS: { id: StatusFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'running', label: 'Running' },
  { id: 'completed', label: 'Done' },
  { id: 'failed', label: 'Failed' },
  { id: 'cancelled', label: 'Cancelled' },
];

// ── Helpers ──

const STATUS_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  running:   { bg: '#2196F320', color: '#2196F3', label: 'Running' },
  completed: { bg: '#4CAF5020', color: '#4CAF50', label: 'Done' },
  failed:    { bg: '#F4433620', color: '#F44336', label: 'Failed' },
  cancelled: { bg: '#9E9E9E20', color: '#9E9E9E', label: 'Cancelled' },
};

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

// ── Styles ──

const cardStyle: React.CSSProperties = {
  padding: '0.75rem 1rem',
  background: 'var(--sl-color-gray-6, #1a1a1a)',
  borderRadius: 6,
  border: '1px solid var(--sl-color-gray-5, #333)',
  minWidth: 120,
  flex: '1 1 0',
  height: 80,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
};

const cardLabelStyle: React.CSSProperties = {
  fontSize: '0.65rem',
  color: 'var(--sl-color-gray-3, #888)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  fontWeight: 500,
  marginBottom: '0.25rem',
};

const cardValueStyle: React.CSSProperties = {
  fontSize: '1.25rem',
  fontWeight: 700,
  color: 'var(--sl-color-white, #fff)',
  lineHeight: 1.2,
};

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
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
};

const tdStyle: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  borderBottom: '1px solid var(--sl-color-gray-6, #222)',
  color: 'var(--sl-color-gray-2, #ccc)',
};

const monoStyle: React.CSSProperties = {
  fontFamily: 'monospace',
  fontSize: '0.75rem',
};

// ── Sub-components ──

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_BADGE[status] ?? STATUS_BADGE.cancelled;
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.15rem 0.5rem',
        borderRadius: '9999px',
        fontSize: '0.7rem',
        fontWeight: 600,
        background: cfg.bg,
        color: cfg.color,
        border: `1px solid ${cfg.color}40`,
      }}
    >
      {cfg.label}
    </span>
  );
}

function EvalBadge({ score }: { score: number | undefined }) {
  if (score == null) {
    return <span style={{ color: 'var(--sl-color-gray-5, #444)', fontSize: '0.65rem' }}>--</span>;
  }
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.05rem 0.3rem',
        borderRadius: 3,
        fontSize: '0.65rem',
        fontWeight: 600,
        color: scoreColor(score),
        background: scoreBg(score),
        border: `1px solid ${scoreColor(score)}30`,
        minWidth: 22,
        textAlign: 'center',
      }}
    >
      {score.toFixed(1)}
    </span>
  );
}

function SummaryCards({ stats }: { stats: StatsData | null }) {
  const summary = stats?.summary;
  const avgEval = summary?.avg_eval ?? null;

  return (
    <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'stretch' }}>
      {[
        { label: 'Total Cost', value: summary ? formatCostRounded(summary.total_cost) : '--', color: undefined },
        { label: 'Total Runs', value: String(summary?.total_runs ?? '--'), color: undefined },
        { label: 'Avg Eval', value: avgEval != null ? avgEval.toFixed(1) : '--', color: avgEval != null ? scoreColor(avgEval) : undefined },
        { label: 'Tokens', value: summary ? formatTokens((summary.total_tokens_in ?? 0) + (summary.total_tokens_out ?? 0)) : '--', color: undefined },
      ].map((card) => (
        <div key={card.label} style={cardStyle}>
          <div style={cardLabelStyle}>{card.label}</div>
          <div style={{ ...cardValueStyle, color: card.color ?? cardValueStyle.color }}>{card.value}</div>
        </div>
      ))}
    </div>
  );
}

function FilterBar({
  statusFilter,
  onStatusChange,
  platformFilter,
  onPlatformChange,
  platformIds,
  search,
  onSearchChange,
  resultCount,
  totalCount,
}: {
  statusFilter: StatusFilter;
  onStatusChange: (f: StatusFilter) => void;
  platformFilter: string;
  onPlatformChange: (f: string) => void;
  platformIds: string[];
  search: string;
  onSearchChange: (v: string) => void;
  resultCount: number;
  totalCount: number;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
      {/* Platform filter chips */}
      {platformIds.length > 0 && (
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          {[{ id: 'all', label: 'All' }, ...platformIds.map((id) => ({ id, label: id }))].map((p) => {
            const active = platformFilter === p.id;
            const chipColor = 'var(--sl-color-accent, #0284c7)';
            return (
              <button
                key={p.id}
                onClick={() => onPlatformChange(p.id)}
                style={{
                  padding: '0.25rem 0.6rem', borderRadius: '9999px',
                  fontSize: '0.7rem', fontWeight: active ? 600 : 400,
                  border: `1px solid ${active ? chipColor : 'var(--sl-color-gray-5, #333)'}`,
                  background: active ? `${chipColor}18` : 'transparent',
                  color: active ? chipColor : 'var(--sl-color-gray-3, #888)',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                {p.label}
              </button>
            );
          })}
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.25rem' }}>
        {STATUS_FILTERS.map((f) => {
          const active = statusFilter === f.id;
          const chipColor = f.id === 'all' ? 'var(--sl-color-accent, #0284c7)' : (STATUS_BADGE[f.id]?.color ?? '#888');
          return (
            <button
              key={f.id}
              onClick={() => onStatusChange(f.id)}
              style={{
                padding: '0.25rem 0.6rem',
                borderRadius: '9999px',
                fontSize: '0.7rem',
                fontWeight: active ? 600 : 400,
                border: `1px solid ${active ? chipColor : 'var(--sl-color-gray-5, #333)'}`,
                background: active ? `${chipColor}18` : 'transparent',
                color: active ? chipColor : 'var(--sl-color-gray-3, #888)',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      <input
        type="text"
        value={search}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder="Search epic, node, run..."
        style={{
          flex: '1 1 180px',
          maxWidth: 300,
          padding: '0.3rem 0.6rem',
          fontSize: '0.75rem',
          fontFamily: 'monospace',
          background: 'var(--sl-color-gray-6, #1a1a1a)',
          color: 'var(--sl-color-gray-2, #ccc)',
          border: '1px solid var(--sl-color-gray-5, #333)',
          borderRadius: 4,
          outline: 'none',
        }}
      />

      <span style={{ fontSize: '0.7rem', color: 'var(--sl-color-gray-4, #666)', marginLeft: 'auto' }}>
        {resultCount === totalCount ? `${totalCount} nodes` : `${resultCount} of ${totalCount}`}
      </span>
    </div>
  );
}

function RunRow({ run, showPlatform }: { run: RunEntry; showPlatform: boolean }) {
  return (
    <tr
      style={{ transition: 'background 0.15s' }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--sl-color-gray-6, #1a1a1a)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
    >
      <td style={tdStyle}><StatusBadge status={run.status} /></td>
      {showPlatform && <td style={{ ...tdStyle, ...monoStyle, fontSize: '0.7rem' }}>{run.platform_id ?? '—'}</td>}
      <td style={{ ...tdStyle, ...monoStyle }}>{run.epic_id ?? '—'}</td>
      <td style={{ ...tdStyle, ...monoStyle, fontWeight: 500 }}>{run.node_id}</td>
      <td style={tdStyle}>{formatDuration(run.duration_ms)}</td>
      <td style={tdStyle}>{formatCost(run.cost_usd)}</td>
      <td style={{ ...tdStyle, ...monoStyle }}>
        {formatTokens(run.tokens_in)}/{formatTokens(run.tokens_out)}
      </td>
      {DIMENSIONS.map((d) => (
        <td key={d.key} style={{ ...tdStyle, textAlign: 'center' }}>
          <EvalBadge score={run.evals[d.key]} />
        </td>
      ))}
      <td style={{ ...tdStyle, ...monoStyle, color: 'var(--sl-color-gray-4, #666)' }}>
        {run.run_id.slice(0, 8)}
      </td>
      <td style={{ ...tdStyle, fontSize: '0.75rem' }}>{formatTime(run.started_at)}</td>
    </tr>
  );
}

// ── Main Component ──

export default function OverviewTab({ runs, stats, sessions, connected, platformIds = [] }: OverviewTabProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [platformFilter, setPlatformFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const showPlatformCol = platformIds.length > 0;

  const filtered = useMemo(() => {
    let result = runs;
    if (platformFilter !== 'all') {
      result = result.filter((r) => r.platform_id === platformFilter);
    }
    if (statusFilter !== 'all') {
      result = result.filter((r) => r.status === statusFilter);
    }
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (r) =>
          (r.platform_id ?? '').toLowerCase().includes(q) ||
          (r.epic_id ?? '').toLowerCase().includes(q) ||
          r.node_id.toLowerCase().includes(q) ||
          r.run_id.toLowerCase().includes(q) ||
          r.status.toLowerCase().includes(q),
      );
    }
    return result;
  }, [runs, statusFilter, platformFilter, search]);

  const todayCompletedCount = useMemo(() => {
    const today = new Date().toDateString();
    return runs.filter((r) => r.status === 'completed' && r.started_at && new Date(r.started_at).toDateString() === today).length;
  }, [runs]);

  if (!runs.length && !connected) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--sl-color-gray-4, #666)', fontSize: '0.85rem' }}>
        Waiting for Easter connection...
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <style dangerouslySetInnerHTML={{ __html: EVAL_TIP_CSS }} />
      <SummaryCards stats={stats} />

      <EasterStatusBanner
        sessions={sessions}
        connected={connected}
        todayCompletedCount={todayCompletedCount}
      />

      {sessions && sessions.running_epics.length > 0 && (
        <ActiveSessionsPanel sessions={sessions} />
      )}

      <div style={{ fontSize: '0.68rem', color: 'var(--sl-color-gray-4, #666)', lineHeight: 1.4 }}>
        {DIMENSIONS.map((d, i) => (
          <span key={d.key}>
            {i > 0 && ' · '}
            <strong style={{ color: 'var(--sl-color-gray-3, #888)' }}>{d.short}</strong> {d.legend}
          </span>
        ))}
      </div>

      <FilterBar
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        platformFilter={platformFilter}
        onPlatformChange={setPlatformFilter}
        platformIds={platformIds}
        search={search}
        onSearchChange={setSearch}
        resultCount={filtered.length}
        totalCount={runs.length}
      />

      {filtered.length === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--sl-color-gray-4, #666)', fontSize: '0.85rem' }}>
          {runs.length === 0 ? 'No node executions found' : 'No nodes match filters'}
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Status</th>
                {showPlatformCol && <th style={thStyle}>Platform</th>}
                <th style={thStyle}>Epic</th>
                <th style={thStyle}>Node</th>
                <th style={thStyle}>Duration</th>
                <th style={thStyle}>Cost</th>
                <th style={thStyle}>Tokens</th>
                {DIMENSIONS.map((d) => (
                  <th key={d.key} style={{ ...thStyle, textAlign: 'center', minWidth: 30, cursor: 'help', position: 'relative' }} className="eval-th">
                    <span className="eval-tip" data-tip={d.tip}>{d.short}</span>
                  </th>
                ))}
                <th style={thStyle}>Run</th>
                <th style={thStyle}>Started</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((run) => (
                <RunRow key={run.run_id ?? `${run.platform_id}-${run.epic_id}-${run.node_id}-${run.started_at}`} run={run} showPlatform={showPlatformCol} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
