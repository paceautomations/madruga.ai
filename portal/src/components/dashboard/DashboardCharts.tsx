import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts';
import { formatCostRounded, formatDuration } from '../observability/formatters';
import { EASTER_BASE } from '../../lib/constants';

// ── Types ──

interface StatsDay { day: string; runs: number; total_cost: number; total_tokens_in: number; total_tokens_out: number; avg_duration_ms: number }
interface Summary { total_runs: number; total_cost: number; total_tokens_in: number; total_tokens_out: number; avg_cost_per_run: number; failed_runs: number; avg_eval: number | null }
interface TopNode { node_id: string; total_cost: number; run_count: number }
interface StatusDay { day: string; status: string; count: number }
interface ScoreDay { day: string; dimension: string; avg_score: number }
interface DurationNode { node_id: string; avg_duration_ms: number; run_count: number }
interface ScoreBucket { bucket: string; count: number }

interface StatsResponse {
  stats: StatsDay[];
  summary: Summary;
  top_nodes: TopNode[];
  stats_by_status: StatusDay[];
  avg_scores_by_day: ScoreDay[];
  avg_duration_by_node: DurationNode[];
  score_distribution: ScoreBucket[];
  period_days: number;
}

interface DashboardChartsProps {
  platformIds: string[];
}

// ── Constants ──

const STATUS_COLORS: Record<string, string> = {
  completed: '#4CAF50', failed: '#F44336', cancelled: '#9E9E9E', running: '#2196F3',
};
const EVAL_COLORS: Record<string, string> = {
  quality: '#6366f1', adherence_to_spec: '#22c55e', completeness: '#f59e0b', cost_efficiency: '#ef4444',
};
const EVAL_SHORT: Record<string, string> = {
  quality: 'Q', adherence_to_spec: 'A', completeness: 'C', cost_efficiency: 'E',
};
const CHART_BG = 'var(--sl-color-gray-6, #1a1a1a)';
const CHART_BORDER = '1px solid var(--sl-color-gray-5, #333)';
const GRID_COLOR = '#333';
const TEXT_COLOR = '#888';

// ── Helpers ──

function shortDay(iso: string): string {
  try { return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); }
  catch { return iso; }
}

const TOOLTIP_STYLE: React.CSSProperties = {
  background: 'var(--sl-color-gray-7, #1a1a1a)', border: '1px solid var(--sl-color-gray-5, #333)',
  color: 'var(--sl-color-white, #fff)', borderRadius: 6, fontSize: '0.72rem',
};

const FILTER_INPUT_STYLE: React.CSSProperties = {
  fontSize: '0.72rem', background: 'var(--sl-color-gray-7, #111)', color: 'var(--sl-color-white, #fff)',
  border: CHART_BORDER, borderRadius: 4, padding: '0.25rem 0.4rem',
};

// ── Styles ──

const cardStyle: React.CSSProperties = {
  padding: '0.75rem 1rem',
  background: 'var(--sl-color-gray-6, #1a1a1a)', borderRadius: 6,
  border: '1px solid var(--sl-color-gray-5, #333)',
  flex: '1 1 0', minWidth: 100, height: 80,
  display: 'flex', flexDirection: 'column', justifyContent: 'center',
};

const chartBoxStyle: React.CSSProperties = {
  background: CHART_BG, border: CHART_BORDER, borderRadius: 8,
  padding: '1rem', minHeight: 280,
};

const chartTitleStyle: React.CSSProperties = {
  fontSize: '0.8rem', fontWeight: 600, color: 'var(--sl-color-white, #fff)',
  margin: '0 0 0.75rem 0',
};

const filterRowStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', margin: '0 0 1rem 0',
};

// ── Sub-components ──

function KpiCard({ label, value, delta, invertDelta }: { label: string; value: string; delta: number | null; invertDelta?: boolean }) {
  const isPositive = delta != null && delta > 0;
  const deltaGood = invertDelta ? !isPositive : isPositive;
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: '0.62rem', color: 'var(--sl-color-gray-3, #888)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem' }}>
        <span style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--sl-color-white, #fff)' }}>{value}</span>
        {delta != null && (
          <span style={{ fontSize: '0.65rem', fontWeight: 600, color: deltaGood ? '#22c55e' : '#ef4444' }}>
            {isPositive ? '\u2191' : '\u2193'}{Math.abs(delta).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  );
}

function ChartBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={chartBoxStyle}>
      <div style={chartTitleStyle}>{title}</div>
      {children}
    </div>
  );
}

// ── Pivot helpers ──

function pivotStatusByDay(rows: StatusDay[]): Record<string, Record<string, number>>[] {
  const byDay = new Map<string, Record<string, number>>();
  for (const r of rows) {
    if (!byDay.has(r.day)) byDay.set(r.day, { day: r.day } as unknown as Record<string, number>);
    byDay.get(r.day)![r.status] = r.count;
  }
  return [...byDay.values()] as unknown as Record<string, Record<string, number>>[];
}

function pivotScoresByDay(rows: ScoreDay[]): Record<string, unknown>[] {
  const byDay = new Map<string, Record<string, unknown>>();
  for (const r of rows) {
    if (!byDay.has(r.day)) byDay.set(r.day, { day: r.day });
    byDay.get(r.day)![r.dimension] = Number(r.avg_score?.toFixed(1));
  }
  return [...byDay.values()];
}

// ── Main Component ──

export default function DashboardCharts({ platformIds }: DashboardChartsProps) {
  const [data, setData] = useState<StatsResponse | null>(null);
  const [prevData, setPrevData] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [platformFilter, setPlatformFilter] = useState<string>('');
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));

  const fetchData = useCallback(async () => {
    const params = new URLSearchParams();
    if (platformFilter) params.set('platform_id', platformFilter);
    params.set('start_date', startDate);
    params.set('end_date', endDate);

    // Fetch current period + previous period for delta
    const daysDiff = Math.max(1, Math.round((new Date(endDate).getTime() - new Date(startDate).getTime()) / 86400000));
    const prevEnd = new Date(startDate);
    prevEnd.setDate(prevEnd.getDate() - 1);
    const prevStart = new Date(prevEnd);
    prevStart.setDate(prevStart.getDate() - daysDiff);
    const prevParams = new URLSearchParams(params);
    prevParams.set('start_date', prevStart.toISOString().slice(0, 10));
    prevParams.set('end_date', prevEnd.toISOString().slice(0, 10));

    try {
      const [res, prevRes] = await Promise.all([
        fetch(`${EASTER_BASE}/api/stats?${params}`),
        fetch(`${EASTER_BASE}/api/stats?${prevParams}`),
      ]);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
      if (prevRes.ok) {
        const prevJson = await prevRes.json();
        setPrevData(prevJson.summary ?? null);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [platformFilter, startDate, endDate]);

  useEffect(() => {
    setLoading(true);
    fetchData();
  }, [fetchData]);

  // Derived chart data
  const statusPivot = useMemo(() => data?.stats_by_status ? pivotStatusByDay(data.stats_by_status) : [], [data]);
  const scoresPivot = useMemo(() => data?.avg_scores_by_day ? pivotScoresByDay(data.avg_scores_by_day) : [], [data]);

  // Delta calculations (month vs month)
  const delta = useMemo(() => {
    if (!data?.summary || !prevData) return { cost: null, runs: null, eval: null, passRate: null };
    const s = data.summary;
    const p = prevData;
    const pct = (curr: number, prev: number) => prev > 0 ? ((curr - prev) / prev) * 100 : null;
    const passRate = s.total_runs > 0 ? ((s.total_runs - (s.failed_runs ?? 0)) / s.total_runs) * 100 : 0;
    const prevPassRate = p.total_runs > 0 ? ((p.total_runs - (p.failed_runs ?? 0)) / p.total_runs) * 100 : 0;
    return {
      cost: pct(s.total_cost, p.total_cost),
      runs: pct(s.total_runs, p.total_runs),
      eval: s.avg_eval != null && p.avg_eval != null ? pct(s.avg_eval, p.avg_eval) : null,
      passRate: pct(passRate, prevPassRate),
    };
  }, [data, prevData]);

  if (loading && !data) {
    return <div style={{ textAlign: 'center', padding: '2rem', color: TEXT_COLOR, fontSize: '0.8rem' }}>Loading charts...</div>;
  }

  if (!data) {
    return <div style={{ textAlign: 'center', padding: '2rem', color: TEXT_COLOR, fontSize: '0.8rem' }}>No data available. Is Easter running?</div>;
  }

  const s = data.summary;
  const failedRuns = s.failed_runs ?? 0;
  const passRate = s.total_runs > 0 ? ((s.total_runs - failedRuns) / s.total_runs) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Filters */}
      <div style={filterRowStyle}>
        <label style={{ fontSize: '0.72rem', color: TEXT_COLOR }}>
          From{' '}
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
            style={FILTER_INPUT_STYLE} />
        </label>
        <label style={{ fontSize: '0.72rem', color: TEXT_COLOR }}>
          To{' '}
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
            style={FILTER_INPUT_STYLE} />
        </label>
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          style={FILTER_INPUT_STYLE}
        >
          <option value="">All Platforms</option>
          {platformIds.map((id) => <option key={id} value={id}>{id}</option>)}
        </select>
      </div>

      {/* KPI Strip */}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'stretch' }}>
        <KpiCard label="Total Cost" value={formatCostRounded(s.total_cost)} delta={delta.cost} invertDelta />
        <KpiCard label="Total Runs" value={String(s.total_runs)} delta={delta.runs} />
        <KpiCard label="Avg Eval" value={s.avg_eval != null ? s.avg_eval.toFixed(1) : '--'} delta={delta.eval} />
        <KpiCard label="Pass Rate" value={`${passRate.toFixed(0)}%`} delta={delta.passRate} />
      </div>

      {/* Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* 1. Cost Trend */}
        <ChartBox title="Cost Trend">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data.stats}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
              <XAxis dataKey="day" tickFormatter={shortDay} tick={{ fontSize: 10, fill: TEXT_COLOR }} />
              <YAxis tick={{ fontSize: 10, fill: TEXT_COLOR }} tickFormatter={(v: number) => `$${v.toFixed(0)}`} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Area type="monotone" dataKey="total_cost" stroke="#6366f1" fill="#6366f130" name="Cost (USD)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartBox>

        {/* 2. Runs by Status */}
        <ChartBox title="Runs by Status">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={statusPivot}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
              <XAxis dataKey="day" tickFormatter={shortDay} tick={{ fontSize: 10, fill: TEXT_COLOR }} />
              <YAxis tick={{ fontSize: 10, fill: TEXT_COLOR }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              {Object.entries(STATUS_COLORS).map(([key, color]) => (
                <Bar key={key} dataKey={key} stackId="status" fill={color} name={key} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>

        {/* 3. Eval Scores Trend */}
        <ChartBox title="Eval Scores Trend">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={scoresPivot}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
              <XAxis dataKey="day" tickFormatter={shortDay} tick={{ fontSize: 10, fill: TEXT_COLOR }} />
              <YAxis domain={[0, 10]} tick={{ fontSize: 10, fill: TEXT_COLOR }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: '0.65rem' }} />
              {Object.entries(EVAL_COLORS).map(([dim, color]) => (
                <Line key={dim} type="monotone" dataKey={dim} stroke={color} dot={false}
                  name={EVAL_SHORT[dim] ?? dim} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartBox>

        {/* 4. Cost by Node */}
        <ChartBox title="Cost by Node (Top 10)">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.top_nodes || []} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
              <XAxis type="number" tick={{ fontSize: 10, fill: TEXT_COLOR }} tickFormatter={(v: number) => `$${v.toFixed(0)}`} />
              <YAxis type="category" dataKey="node_id" tick={{ fontSize: 9, fill: TEXT_COLOR }} width={100} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="total_cost" fill="#6366f1" name="Cost (USD)" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>

        {/* 5. Duration by Node */}
        <ChartBox title="Avg Duration by Node (Top 10)">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.avg_duration_by_node || []} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
              <XAxis type="number" tick={{ fontSize: 10, fill: TEXT_COLOR }} tickFormatter={(v: number) => formatDuration(v)} />
              <YAxis type="category" dataKey="node_id" tick={{ fontSize: 9, fill: TEXT_COLOR }} width={100} />
              <Tooltip contentStyle={TOOLTIP_STYLE}
                formatter={(v: number) => formatDuration(v)} />
              <Bar dataKey="avg_duration_ms" fill="#f59e0b" name="Avg Duration" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>

        {/* 6. Score Distribution */}
        <ChartBox title="Score Distribution">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.score_distribution || []}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
              <XAxis dataKey="bucket" tick={{ fontSize: 10, fill: TEXT_COLOR }} />
              <YAxis tick={{ fontSize: 10, fill: TEXT_COLOR }} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="count" name="Runs" radius={[3, 3, 0, 0]}>
                {(data.score_distribution || []).map((entry) => (
                  <Cell key={entry.bucket} fill={
                    entry.bucket === '8-10' ? '#22c55e' :
                    entry.bucket === '6-8' ? '#4CAF50' :
                    entry.bucket === '4-6' ? '#FFC107' :
                    entry.bucket === '2-4' ? '#f59e0b' : '#ef4444'
                  } />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>

        {/* 7. Epic Lead Time — derived from stats (placeholder: avg duration trend) */}
        <ChartBox title="Avg Run Duration Trend">
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data.stats}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
              <XAxis dataKey="day" tickFormatter={shortDay} tick={{ fontSize: 10, fill: TEXT_COLOR }} />
              <YAxis tick={{ fontSize: 10, fill: TEXT_COLOR }} tickFormatter={(v: number) => formatDuration(v)} />
              <Tooltip contentStyle={TOOLTIP_STYLE}
                formatter={(v: number) => formatDuration(v)} />
              <Area type="monotone" dataKey="avg_duration_ms" stroke="#22c55e" fill="#22c55e30" name="Avg Duration" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartBox>

        {/* 8. Platform Comparison — only when global (no platform filter) */}
        {!platformFilter && platformIds.length > 1 && (
          <ChartBox title="Platform Comparison">
            <PlatformComparisonChart platformIds={platformIds} startDate={startDate} endDate={endDate} />
          </ChartBox>
        )}
      </div>
    </div>
  );
}

// ── Platform Comparison Sub-chart ──

function PlatformComparisonChart({ platformIds, startDate, endDate }: { platformIds: string[]; startDate: string; endDate: string }) {
  const [compData, setCompData] = useState<{ id: string; cost: number; runs: number; eval: number }[]>([]);

  useEffect(() => {
    Promise.all(
      platformIds.map(async (id) => {
        try {
          const res = await fetch(`${EASTER_BASE}/api/stats?platform_id=${id}&start_date=${startDate}&end_date=${endDate}`);
          if (res.ok) {
            const json = await res.json();
            return { id, cost: json.summary?.total_cost ?? 0, runs: json.summary?.total_runs ?? 0, eval: json.summary?.avg_eval ?? 0 };
          }
        } catch { /* ignore */ }
        return { id, cost: 0, runs: 0, eval: 0 };
      }),
    ).then(setCompData);
  }, [platformIds, startDate, endDate]);

  if (!compData.length) return null;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={compData}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} />
        <XAxis dataKey="id" tick={{ fontSize: 10, fill: TEXT_COLOR }} />
        <YAxis yAxisId="cost" tick={{ fontSize: 10, fill: TEXT_COLOR }} tickFormatter={(v: number) => `$${v}`} />
        <YAxis yAxisId="runs" orientation="right" tick={{ fontSize: 10, fill: TEXT_COLOR }} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Legend wrapperStyle={{ fontSize: '0.65rem' }} />
        <Bar yAxisId="cost" dataKey="cost" fill="#6366f1" name="Cost ($)" />
        <Bar yAxisId="runs" dataKey="runs" fill="#22c55e" name="Runs" />
      </BarChart>
    </ResponsiveContainer>
  );
}
