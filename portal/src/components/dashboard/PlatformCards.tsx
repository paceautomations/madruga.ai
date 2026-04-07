import { useState, useEffect, useCallback } from 'react';
import { formatCostRounded } from '../observability/formatters';

// ── Types ──

interface PlatformSummary {
  id: string;
  title: string;
  lifecycle: string;
  l1_progress_pct: number;
  l1_total: number;
  l1_done: number;
  active_epics: number;
  total_epics: number;
}

interface PlatformStats {
  total_cost: number;
  total_runs: number;
  avg_eval: number | null;
}

interface PlatformCardsProps {
  platforms: PlatformSummary[];
  selected: string;
  onSelect?: (platformId: string) => void;
}

const EASTER_BASE = 'http://localhost:18789';

// ── Component ──

export type { PlatformSummary };

export default function PlatformCards({ platforms, selected, onSelect }: PlatformCardsProps) {
  const [statsMap, setStatsMap] = useState<Record<string, PlatformStats>>({});

  const fetchStats = useCallback(async () => {
    const results: Record<string, PlatformStats> = {};
    await Promise.all(
      platforms.map(async (p) => {
        try {
          const res = await fetch(`${EASTER_BASE}/api/stats?platform_id=${encodeURIComponent(p.id)}&days=30`);
          if (res.ok) {
            const data = await res.json();
            results[p.id] = {
              total_cost: data.summary?.total_cost ?? 0,
              total_runs: data.summary?.total_runs ?? 0,
              avg_eval: data.summary?.avg_eval ?? null,
            };
          }
        } catch { /* ignore — cards show without stats */ }
      }),
    );
    setStatsMap(results);
  }, [platforms]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return (
    <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', margin: 0 }}>
      {platforms.map((p) => {
        const isSelected = p.id === selected;
        const stats = statsMap[p.id];
        return (
          <div
            key={p.id}
            onClick={() => {
              if (onSelect) {
                onSelect(p.id);
              } else {
                const url = new URL(window.location.href);
                url.searchParams.set('platform', p.id);
                url.hash = 'execution';
                window.location.href = url.toString();
              }
            }}
            style={{
              flex: '1 1 180px', maxWidth: 260, margin: 0,
              padding: '0.85rem 1rem', borderRadius: 8, cursor: 'pointer',
              background: 'var(--sl-color-gray-6, #1a1a1a)',
              border: `2px solid ${isSelected ? 'var(--sl-color-accent, #0284c7)' : 'var(--sl-color-gray-5, #333)'}`,
              transition: 'border-color 0.15s',
            }}
          >
            {/* Header: name + lifecycle */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '0 0 0.5rem 0' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--sl-color-white, #fff)', margin: 0 }}>
                {p.id}
              </span>
              <span style={{
                fontSize: '0.6rem', fontWeight: 500, padding: '0.1rem 0.35rem',
                borderRadius: 3, background: 'var(--sl-color-gray-5, #333)',
                color: 'var(--sl-color-gray-2, #ccc)', margin: 0,
              }}>
                {p.lifecycle}
              </span>
            </div>

            {/* L1 progress */}
            <div style={{ margin: '0 0 0.5rem 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--sl-color-gray-4, #666)', margin: '0 0 0.15rem 0' }}>
                <span style={{ margin: 0 }}>L1: {Math.round(p.l1_progress_pct)}%</span>
                <span style={{ margin: 0 }}>{p.l1_done}/{p.l1_total}</span>
              </div>
              <div style={{ height: 5, background: 'var(--sl-color-gray-5, #333)', borderRadius: 3, overflow: 'hidden', margin: 0 }}>
                <div style={{ height: '100%', width: `${p.l1_progress_pct}%`, background: '#22c55e', borderRadius: 3, margin: 0 }} />
              </div>
            </div>

            {/* Stats row */}
            <div style={{ fontSize: '0.7rem', color: 'var(--sl-color-gray-3, #888)', margin: 0 }}>
              {stats ? (
                <span style={{ margin: 0 }}>
                  {formatCostRounded(stats.total_cost)} · {stats.total_runs} runs
                  {stats.avg_eval != null && ` · ${stats.avg_eval.toFixed(1)} avg`}
                </span>
              ) : (
                <span style={{ margin: 0 }}>Loading...</span>
              )}
            </div>

            {/* Epics */}
            <div style={{ fontSize: '0.65rem', color: 'var(--sl-color-gray-4, #666)', marginTop: '0.25rem' }}>
              {p.active_epics > 0
                ? <span style={{ color: '#22c55e', margin: 0 }}>{p.active_epics} epic{p.active_epics > 1 ? 's' : ''} active</span>
                : <span style={{ margin: 0 }}>{p.total_epics} epic{p.total_epics !== 1 ? 's' : ''}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
