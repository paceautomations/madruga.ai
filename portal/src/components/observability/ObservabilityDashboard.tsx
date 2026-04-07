import { useState, useEffect, useRef, useCallback } from 'react';
import OverviewTab from './OverviewTab';

// ── Types ──

export interface RunEntry {
  run_id: string;
  platform_id?: string;
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

export interface SessionNodeStatus {
  node_id: string;
  status: string;
}

export interface ActiveSession {
  epic_id: string;
  platform_id: string;
  trace_id: string | null;
  started_at: string | null;
  current_node: string | null;
  current_node_started_at: string | null;
  session_cost_usd: number;
  tokens_in: number;
  tokens_out: number;
  completed_nodes: number;
  total_nodes: number;
  last_activity: string | null;
  node_statuses: SessionNodeStatus[];
}

export interface QueuedEpic {
  epic_id: string;
  platform_id: string;
}

export interface SessionsData {
  easter_state: string;
  telegram_status: string;
  uptime_seconds: number;
  pid: number;
  poll_interval_seconds: number;
  running_epics: ActiveSession[];
  queued_epics: QueuedEpic[];
}

// ── Constants ──

import { EASTER_BASE } from '../../lib/constants';
const POLL_INTERVAL = 10_000;
const STATUS_POLL_INTERVAL = 5_000;

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

/** Only call setState when data actually changed (avoids re-rendering 170+ table rows). */
function setIfChanged<T>(setter: React.Dispatch<React.SetStateAction<T>>, next: T, prev: React.RefObject<string>) {
  const json = JSON.stringify(next);
  if (json !== prev.current) {
    prev.current = json;
    setter(next);
  }
}

// ── Main Component ──

interface ObservabilityDashboardProps {
  platform?: string;      // undefined = global mode (all platforms)
  platformIds?: string[]; // list of all platform IDs for filter chips
}

export default function ObservabilityDashboard({ platform, platformIds = [] }: ObservabilityDashboardProps) {
  const [runs, setRuns] = useState<RunEntry[]>([]);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [sessions, setSessions] = useState<SessionsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const statusIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Dedup refs — avoid re-rendering 170+ rows when polled data hasn't changed
  const prevRuns = useRef('');
  const prevStats = useRef('');

  const platformParam = platform ? `platform_id=${encodeURIComponent(platform)}&` : '';

  const fetchData = useCallback(async () => {
    const [runsRes, statsRes] = await Promise.all([
      fetchJSON<{ runs: RunEntry[] }>(`${EASTER_BASE}/api/runs?${platformParam}limit=200`),
      fetchJSON<StatsData>(`${EASTER_BASE}/api/stats?${platformParam}days=30`),
    ]);
    const nowConnected = runsRes.connected && statsRes.connected;
    setConnected((prev) => prev !== nowConnected ? nowConnected : prev);
    if (runsRes.data) setIfChanged(setRuns, runsRes.data.runs, prevRuns);
    if (statsRes.data) setIfChanged(setStats, statsRes.data, prevStats);

    setLoading(false);
  }, [platformParam]);

  const fetchStatus = useCallback(async () => {
    const res = await fetchJSON<SessionsData>(`${EASTER_BASE}/api/sessions?${platformParam.slice(0, -1)}`);
    if (res.data) setSessions(res.data);
  }, [platformParam]);

  useEffect(() => {
    setLoading(true);
    fetchData();
    fetchStatus();

    intervalRef.current = setInterval(fetchData, POLL_INTERVAL);
    statusIntervalRef.current = setInterval(fetchStatus, STATUS_POLL_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (statusIntervalRef.current) clearInterval(statusIntervalRef.current);
    };
  }, [fetchData, fetchStatus]);

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
        <OverviewTab runs={runs} stats={stats} sessions={sessions} connected={connected} platformIds={platformIds} />
      )}
    </div>
  );
}
