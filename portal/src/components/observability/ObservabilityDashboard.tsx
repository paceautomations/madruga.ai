import { useState, useEffect, useRef, useCallback } from 'react';
import OverviewTab from './OverviewTab';

// ── Types ──

export interface RunEntry {
  run_id: string;
  epic_id: string | null;
  node_id: string;
  status: string;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  duration_ms: number | null;
  error: string | null;
  started_at: string;
  completed_at: string | null;
  evals: Record<string, number>;
}

export interface StatsSummary {
  total_runs: number;
  total_cost: number;
  total_tokens_in: number;
  total_tokens_out: number;
  avg_cost_per_run: number;
  avg_eval: number | null;
}

export interface StatsData {
  stats: { day: string; runs: number; total_cost: number; total_tokens_in: number; total_tokens_out: number; avg_duration_ms: number }[];
  period_days: number;
  summary: StatsSummary;
  top_nodes: { node_id: string; total_cost: number; run_count: number }[];
}

// ── Constants ──

const EASTER_BASE = 'http://localhost:18789';
const POLL_INTERVAL = 10_000;

// ── Helpers ──

type FetchResult<T> = { data: T; connected: true } | { data: null; connected: false };

async function fetchJSON<T>(url: string): Promise<FetchResult<T>> {
  try {
    const res = await fetch(url);
    if (!res.ok) return { data: null, connected: true };
    return { data: (await res.json()) as T, connected: true };
  } catch {
    return { data: null, connected: false };
  }
}

// ── Main Component ──

interface ObservabilityDashboardProps {
  platform: string;
}

export default function ObservabilityDashboard({ platform }: ObservabilityDashboardProps) {
  const [runs, setRuns] = useState<RunEntry[]>([]);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    const enc = encodeURIComponent(platform);

    const [runsRes, statsRes] = await Promise.all([
      fetchJSON<{ runs: RunEntry[] }>(`${EASTER_BASE}/api/runs?platform_id=${enc}&limit=200`),
      fetchJSON<StatsData>(`${EASTER_BASE}/api/stats?platform_id=${enc}&days=30`),
    ]);
    setConnected(runsRes.connected && statsRes.connected);
    if (runsRes.data) setRuns(runsRes.data.runs);
    if (statsRes.data) setStats(statsRes.data);

    setLoading(false);
  }, [platform]);

  useEffect(() => {
    setLoading(true);
    fetchData();

    intervalRef.current = setInterval(fetchData, POLL_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {loading && (
        <div style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--sl-color-gray-4, #666)', padding: '1rem 0' }}>
          Loading...
        </div>
      )}

      {!connected && !loading && (
        <div
          style={{
            padding: '0.75rem 1rem',
            background: '#FFC10712',
            border: '1px solid #FFC10740',
            borderRadius: 6,
            color: '#FFC107',
            fontSize: '0.8rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.25rem',
          }}
        >
          <strong>Easter server not reachable</strong>
          <span style={{ color: 'var(--sl-color-gray-3, #888)', fontSize: '0.75rem' }}>
            Observability data requires the Easter API running on <code style={{ fontSize: '0.75rem' }}>localhost:18789</code>.
            Start it with: <code style={{ fontSize: '0.75rem' }}>make easter</code>
          </span>
        </div>
      )}

      {!loading && (
        <OverviewTab runs={runs} stats={stats} connected={connected} />
      )}
    </div>
  );
}
