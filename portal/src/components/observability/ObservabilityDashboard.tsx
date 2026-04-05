import { useState, useEffect, useRef, useCallback } from 'react';
import RunsTab from './RunsTab';
import TracesTab from './TracesTab';
import CostTab from './CostTab';
import EvalsTab from './EvalsTab';

// ── Types ──

export interface Trace {
  trace_id: string;
  platform_id: string;
  epic_id: string | null;
  mode: 'l1' | 'l2';
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  total_nodes: number;
  completed_nodes: number;
  total_tokens_in: number | null;
  total_tokens_out: number | null;
  total_cost_usd: number | null;
  total_duration_ms: number | null;
  started_at: string;
  completed_at: string | null;
}

export interface Span {
  run_id: string;
  node_id: string;
  status: string;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  duration_ms: number | null;
  error: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface EvalScore {
  score_id: string;
  trace_id: string | null;
  platform_id: string;
  epic_id: string | null;
  node_id: string;
  run_id: string | null;
  dimension: 'quality' | 'adherence_to_spec' | 'completeness' | 'cost_efficiency';
  score: number;
  metadata: string | null;
  evaluated_at: string;
}

export interface TraceDetail {
  trace: Trace;
  spans: Span[];
  eval_scores: EvalScore[];
}

export interface DayStat {
  day: string;
  runs: number;
  total_cost: number;
  total_tokens_in: number;
  total_tokens_out: number;
  avg_duration_ms: number;
}

export interface StatsSummary {
  total_runs: number;
  total_cost: number;
  total_tokens_in: number;
  total_tokens_out: number;
  avg_cost_per_run: number;
}

export interface TopNode {
  node_id: string;
  total_cost: number;
  run_count: number;
}

export interface StatsData {
  stats: DayStat[];
  period_days: number;
  summary: StatsSummary;
  top_nodes: TopNode[];
}

// ── Constants ──

type TabId = 'runs' | 'traces' | 'evals' | 'cost';

const TABS: { id: TabId; label: string }[] = [
  { id: 'runs', label: 'Runs' },
  { id: 'traces', label: 'Traces' },
  { id: 'evals', label: 'Evals' },
  { id: 'cost', label: 'Cost' },
];

const EASTER_BASE = 'http://localhost:8040';
const POLL_INTERVAL = 10_000;

// ── Helpers ──

async function fetchJSON<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ── Main Component ──

interface ObservabilityDashboardProps {
  platform: string;
}

export default function ObservabilityDashboard({ platform }: ObservabilityDashboardProps) {
  const [activeTab, setActiveTab] = useState<TabId>('runs');
  const [traces, setTraces] = useState<Trace[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<TraceDetail | null>(null);
  const [evalScores, setEvalScores] = useState<EvalScore[]>([]);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    setError(null);

    try {
      if (activeTab === 'runs' || activeTab === 'traces') {
        const data = await fetchJSON<{ traces: Trace[] }>(
          `${EASTER_BASE}/api/traces?platform_id=${encodeURIComponent(platform)}&limit=50`,
        );
        if (data) setTraces(data.traces);
      }

      if (activeTab === 'evals') {
        const data = await fetchJSON<{ scores: EvalScore[] }>(
          `${EASTER_BASE}/api/evals?platform_id=${encodeURIComponent(platform)}&limit=100`,
        );
        if (data) setEvalScores(data.scores);
      }

      if (activeTab === 'cost') {
        const data = await fetchJSON<StatsData>(
          `${EASTER_BASE}/api/stats?platform_id=${encodeURIComponent(platform)}&days=30`,
        );
        if (data) setStats(data);
      }
    } catch {
      setError('Failed to connect to easter');
    } finally {
      setLoading(false);
    }
  }, [activeTab, platform]);

  useEffect(() => {
    setLoading(true);
    fetchData();

    intervalRef.current = setInterval(fetchData, POLL_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData]);

  const fetchTraceDetail = useCallback(async (traceId: string) => {
    const data = await fetchJSON<TraceDetail>(`${EASTER_BASE}/api/traces/${traceId}`);
    if (data) setSelectedTrace(data);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Tab Bar */}
      <div
        style={{
          display: 'flex',
          gap: '0.25rem',
          borderBottom: '2px solid var(--sl-color-gray-5, #333)',
          paddingBottom: '0',
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '0.5rem 1rem',
              border: 'none',
              borderBottom: activeTab === tab.id
                ? '2px solid var(--sl-color-accent, #0284c7)'
                : '2px solid transparent',
              background: activeTab === tab.id
                ? 'var(--sl-color-gray-6, #1a1a1a)'
                : 'transparent',
              color: activeTab === tab.id
                ? 'var(--sl-color-white, #fff)'
                : 'var(--sl-color-gray-3, #888)',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: activeTab === tab.id ? 600 : 400,
              marginBottom: '-2px',
              borderRadius: '4px 4px 0 0',
              transition: 'color 0.15s, border-color 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
        {loading && (
          <span
            style={{
              marginLeft: 'auto',
              alignSelf: 'center',
              fontSize: '0.7rem',
              color: 'var(--sl-color-gray-4, #666)',
            }}
          >
            Loading...
          </span>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div
          style={{
            padding: '0.5rem 0.75rem',
            background: '#F4433615',
            border: '1px solid #F44336',
            borderRadius: 4,
            color: '#F44336',
            fontSize: '0.8rem',
          }}
        >
          {error}
        </div>
      )}

      {/* Tab Content */}
      <div style={{ minHeight: 200 }}>
        {activeTab === 'runs' && (
          <RunsTab traces={traces} onSelectTrace={fetchTraceDetail} selectedTrace={selectedTrace} />
        )}
        {activeTab === 'traces' && (
          <TracesTab traces={traces} onSelectTrace={fetchTraceDetail} selectedTrace={selectedTrace} />
        )}
        {activeTab === 'evals' && (
          <EvalsTab scores={evalScores} />
        )}
        {activeTab === 'cost' && (
          <CostTab stats={stats} />
        )}
      </div>
    </div>
  );
}
