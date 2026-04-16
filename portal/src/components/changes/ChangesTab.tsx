import { useCallback, useEffect, useMemo, useState } from 'react';
import { EASTER_BASE } from '../../lib/constants';

// ── Types ──

interface Commit {
  sha: string;
  message: string;
  author: string;
  platform_id: string;
  epic_id: string | null;
  source: string;
  committed_at: string;
  reconciled_at: string | null;
  files: string[];
  host_repo: string | null;
}

interface CommitsResponse {
  commits: Commit[];
  total: number;
  limit: number;
  offset: number;
}

interface StatsResponse {
  total_commits: number;
  by_epic: Record<string, number>;
  by_platform: Record<string, number>;
  adhoc_count: number;
  adhoc_pct: number;
}

interface ChangesTabProps {
  repoUrl?: string;
}

// ── Helpers ──

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-CA'); // YYYY-MM-DD
  } catch {
    return iso.slice(0, 10);
  }
}

function shortSha(sha: string): string {
  return sha.slice(0, 7);
}

const PAGE_SIZE = 50;

// ── Styles (matching control-panel token system) ──

const S = {
  section: { marginBottom: '2rem' } as const,
  sectionHeader: {
    display: 'flex', alignItems: 'baseline', gap: '0.5rem',
    marginBottom: '0.6rem',
  } as const,
  h2: {
    margin: 0, fontSize: '0.78rem', fontWeight: 700,
    textTransform: 'uppercase' as const, letterSpacing: '0.08em',
    color: 'var(--d-text3)',
  },
  meta: { fontSize: '0.68rem', color: 'var(--d-text4)' } as const,

  // Stats row
  statsRow: {
    display: 'flex', alignItems: 'baseline', gap: 0,
    marginBottom: '1.25rem', paddingBottom: '1.25rem',
    borderBottom: '1px solid var(--d-border)',
    flexWrap: 'wrap' as const,
  },
  stat: {
    display: 'flex', flexDirection: 'column' as const, alignItems: 'center',
    padding: '0 1.2rem', borderRight: '1px solid var(--d-border)',
  },
  statLast: { borderRight: 'none', paddingRight: 0 } as const,
  statFirst: { paddingLeft: 0 } as const,
  statValue: {
    fontSize: '1.6rem', fontWeight: 800, color: 'var(--d-text)',
    lineHeight: 1, fontVariantNumeric: 'tabular-nums',
  } as const,
  statLabel: {
    fontSize: '0.6rem', fontWeight: 500, textTransform: 'uppercase' as const,
    letterSpacing: '0.08em', color: 'var(--d-text4)', marginTop: '0.3rem',
    whiteSpace: 'nowrap' as const,
  },

  // Filters
  filterBar: {
    display: 'flex', gap: '0.5rem', marginBottom: '0.75rem',
    flexWrap: 'wrap' as const, alignItems: 'center',
  },
  select: {
    fontSize: '0.75rem', padding: '0.3rem 0.5rem',
    background: 'var(--d-surface)', color: 'var(--d-text2)',
    border: '1px solid var(--d-border)', borderRadius: 'var(--d-r)',
    cursor: 'pointer',
  } as const,
  input: {
    fontSize: '0.75rem', padding: '0.3rem 0.5rem',
    background: 'var(--d-surface)', color: 'var(--d-text2)',
    border: '1px solid var(--d-border)', borderRadius: 'var(--d-r)',
    width: '130px',
  } as const,
  filterLabel: {
    fontSize: '0.6rem', fontWeight: 600, color: 'var(--d-text4)',
    textTransform: 'uppercase' as const, letterSpacing: '0.06em',
    marginRight: '0.15rem',
  } as const,

  // Table
  table: {
    width: '100%', borderCollapse: 'collapse' as const,
    fontSize: '0.78rem',
  },
  th: {
    textAlign: 'left' as const, padding: '0.4rem 0.5rem',
    borderBottom: '1px solid var(--d-border)',
    fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase' as const,
    letterSpacing: '0.06em', color: 'var(--d-text4)',
    whiteSpace: 'nowrap' as const,
  },
  td: {
    padding: '0.35rem 0.5rem',
    borderBottom: '1px solid color-mix(in srgb, var(--d-border) 50%, transparent)',
    color: 'var(--d-text2)', verticalAlign: 'top' as const,
  },
  shaLink: {
    fontFamily: 'var(--sl-font-mono, monospace)', fontSize: '0.72rem',
    color: 'var(--sl-color-accent)', textDecoration: 'none',
  } as const,
  epicBadge: {
    fontSize: '0.6rem', padding: '0.08rem 0.3rem', borderRadius: '3px',
    fontWeight: 700, whiteSpace: 'nowrap' as const,
  } as const,
  adhocBadge: {
    background: 'color-mix(in srgb, var(--d-amber) 15%, var(--d-card))',
    color: 'var(--d-amber)',
  } as const,
  epicTagBadge: {
    background: 'color-mix(in srgb, var(--d-green) 12%, var(--d-card))',
    color: 'var(--d-green)',
  } as const,
  reconcilePendingBadge: {
    background: 'color-mix(in srgb, var(--d-red, #e66) 15%, var(--d-card))',
    color: 'var(--d-red, #e66)',
    fontSize: '0.58rem', padding: '0.06rem 0.28rem', borderRadius: '3px',
    fontWeight: 700, whiteSpace: 'nowrap' as const, marginLeft: '0.3rem',
  } as const,
  msgCell: {
    maxWidth: '320px', overflow: 'hidden',
    textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
  } as const,

  empty: { textAlign: 'center' as const, padding: '3rem', color: 'var(--d-text3)' },

  // Pagination
  paginationBar: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginTop: '0.75rem', fontSize: '0.72rem', color: 'var(--d-text4)',
  } as const,
  pageBtn: {
    fontSize: '0.72rem', padding: '0.25rem 0.6rem',
    background: 'var(--d-surface)', color: 'var(--d-text2)',
    border: '1px solid var(--d-border)', borderRadius: 'var(--d-r)',
    cursor: 'pointer',
  } as const,
  pageBtnDisabled: {
    opacity: 0.4, cursor: 'default', pointerEvents: 'none' as const,
  } as const,
} as const;

// ── Component ──

export default function ChangesTab({ repoUrl }: ChangesTabProps) {
  // Stats (fetched once)
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [statsError, setStatsError] = useState(false);

  // Commits (paginated)
  const [commits, setCommits] = useState<Commit[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [platformFilter, setPlatformFilter] = useState('all');
  const [epicFilter, setEpicFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState<'all' | 'epic' | 'adhoc'>('all');
  const [reconciledFilter, setReconciledFilter] = useState<'all' | 'true' | 'false'>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Fetch stats on mount
  useEffect(() => {
    fetch(`${EASTER_BASE}/api/commits/stats`)
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d: StatsResponse) => setStats(d))
      .catch(() => setStatsError(true));
  }, []);

  // Derive filter options from stats
  const { platforms, epics } = useMemo(() => {
    if (!stats) return { platforms: [] as string[], epics: [] as string[] };
    return {
      platforms: Object.keys(stats.by_platform).sort(),
      epics: Object.keys(stats.by_epic).sort(),
    };
  }, [stats]);

  // Fetch commits when filters or page change
  const fetchCommits = useCallback(() => {
    const params = new URLSearchParams();
    if (platformFilter !== 'all') params.set('platform_id', platformFilter);
    if (epicFilter === '__adhoc__') {
      params.set('commit_type', 'adhoc');
    } else if (epicFilter !== 'all') {
      params.set('epic_id', epicFilter);
    } else if (typeFilter !== 'all') {
      params.set('commit_type', typeFilter);
    }
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (reconciledFilter !== 'all') params.set('reconciled', reconciledFilter);
    params.set('limit', String(PAGE_SIZE));
    params.set('offset', String(offset));

    setLoading(true);
    fetch(`${EASTER_BASE}/api/commits?${params}`)
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then((d: CommitsResponse) => {
        setCommits(d.commits);
        setTotal(d.total);
      })
      .catch(() => {
        setCommits([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [platformFilter, epicFilter, typeFilter, reconciledFilter, dateFrom, dateTo, offset]);

  useEffect(() => { fetchCommits(); }, [fetchCommits]);

  // Reset to page 0 when filters change
  const updateFilter = useCallback(
    <T,>(setter: (v: T) => void) => (v: T) => { setter(v); setOffset(0); },
    [],
  );

  // Pagination
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (statsError && commits.length === 0 && !loading) {
    return (
      <div style={S.empty}>
        Cannot connect to Easter API at <code>{EASTER_BASE}</code>.<br />
        Start the server with <code>python3 .specify/scripts/easter.py</code>
      </div>
    );
  }

  const totalCommits = stats?.total_commits ?? total;
  const epicCount = stats ? Object.keys(stats.by_epic).length : 0;
  const adhocPct = stats?.adhoc_pct ?? 0;

  return (
    <div>
      {/* ── Stats ── */}
      <div style={S.statsRow}>
        <div style={{ ...S.stat, ...S.statFirst }}>
          <span style={S.statValue}>{totalCommits}</span>
          <span style={S.statLabel}>Total Commits</span>
        </div>
        <div style={S.stat}>
          <span style={S.statValue}>{epicCount}</span>
          <span style={S.statLabel}>Epics</span>
        </div>
        <div style={S.stat}>
          <span style={S.statValue}>{Math.round(100 - adhocPct)}<span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--d-text3)' }}>%</span></span>
          <span style={S.statLabel}>Epic Coverage</span>
        </div>
        <div style={{ ...S.stat, ...S.statLast }}>
          <span style={S.statValue}>{adhocPct.toFixed(1)}<span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--d-text3)' }}>%</span></span>
          <span style={S.statLabel}>Ad-hoc</span>
        </div>
      </div>

      {/* ── Per-Epic Breakdown ── */}
      {stats && (
        <div style={S.section}>
          <div style={S.sectionHeader}>
            <h2 style={S.h2}>Commits by Epic</h2>
            <span style={S.meta}>{epicCount} epics tracked</span>
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            {Object.entries(stats.by_epic)
              .sort(([, a], [, b]) => b - a)
              .map(([epicId, count]) => (
                <div
                  key={epicId}
                  style={{
                    padding: '0.3rem 0.55rem',
                    background: 'var(--d-surface)',
                    border: '1px solid var(--d-border)',
                    borderLeft: '3px solid var(--d-green)',
                    borderRadius: 'var(--d-r)',
                    fontSize: '0.72rem',
                    display: 'flex', alignItems: 'baseline', gap: '0.35rem',
                  }}
                >
                  <span style={{ fontFamily: 'var(--sl-font-mono, monospace)', fontWeight: 700, color: 'var(--d-text4)', fontSize: '0.6rem' }}>
                    {epicId.split('-')[0]}
                  </span>
                  <span style={{ color: 'var(--d-text2)' }}>
                    {epicId.replace(/^\d+-/, '')}
                  </span>
                  <span style={{ fontWeight: 800, color: 'var(--d-text)', fontVariantNumeric: 'tabular-nums' }}>
                    {count}
                  </span>
                </div>
              ))}
            {epicCount === 0 && (
              <span style={{ fontSize: '0.72rem', color: 'var(--d-text4)' }}>No epic commits yet</span>
            )}
          </div>
        </div>
      )}

      {/* ── Filters ── */}
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <h2 style={S.h2}>Commit Log</h2>
          <span style={S.meta}>
            {loading ? 'Loading...' : `${total} commits`}
            {total !== totalCommits && !loading ? ` of ${totalCommits} total` : ''}
          </span>
        </div>

        <div style={S.filterBar}>
          <span style={S.filterLabel}>Platform</span>
          <select style={S.select} value={platformFilter} onChange={(e) => updateFilter(setPlatformFilter)(e.target.value)}>
            <option value="all">All</option>
            {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>

          <span style={S.filterLabel}>Epic</span>
          <select style={S.select} value={epicFilter} onChange={(e) => updateFilter(setEpicFilter)(e.target.value)}>
            <option value="all">All</option>
            <option value="__adhoc__">Ad-hoc only</option>
            {epics.map((ep) => <option key={ep} value={ep}>{ep}</option>)}
          </select>

          <span style={S.filterLabel}>Type</span>
          <select style={S.select} value={typeFilter} onChange={(e) => updateFilter(setTypeFilter)(e.target.value as 'all' | 'epic' | 'adhoc')}>
            <option value="all">All</option>
            <option value="epic">Epic</option>
            <option value="adhoc">Ad-hoc</option>
          </select>

          <span style={S.filterLabel}>Reconciled</span>
          <select style={S.select} value={reconciledFilter} onChange={(e) => updateFilter(setReconciledFilter)(e.target.value as 'all' | 'true' | 'false')}>
            <option value="all">All</option>
            <option value="false">Needs reconcile</option>
            <option value="true">Reconciled</option>
          </select>

          <span style={S.filterLabel}>From</span>
          <input type="date" style={S.input} value={dateFrom} onChange={(e) => updateFilter(setDateFrom)(e.target.value)} />

          <span style={S.filterLabel}>To</span>
          <input type="date" style={S.input} value={dateTo} onChange={(e) => updateFilter(setDateTo)(e.target.value)} />
        </div>

        {/* ── Table ── */}
        <div style={{ overflowX: 'auto', opacity: loading ? 0.5 : 1, transition: 'opacity 0.15s' }}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>SHA</th>
                <th style={S.th}>Message</th>
                <th style={S.th}>Author</th>
                <th style={S.th}>Platform</th>
                <th style={S.th}>Epic</th>
                <th style={S.th}>Date</th>
              </tr>
            </thead>
            <tbody>
              {commits.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} style={{ ...S.td, textAlign: 'center', color: 'var(--d-text4)', padding: '1.5rem' }}>
                    No commits match the current filters.
                  </td>
                </tr>
              )}
              {commits.map((c) => {
                // Per-commit URL: prefer host_repo (where SHA physically lives,
                // set by the inserter) over the page-derived repoUrl. This handles
                // cross-repo work where platform_id (work owner) differs from the
                // repo containing the SHA — e.g. prosauai work committed in madruga.ai.
                const commitRepo = c.host_repo
                  ? `https://github.com/${c.host_repo}`
                  : repoUrl;
                const rawSha = c.sha.includes(':') ? c.sha.split(':', 1)[0] : c.sha;
                return (
                <tr key={`${c.sha}-${c.platform_id}`}>
                  <td style={S.td}>
                    {commitRepo ? (
                      <a
                        href={`${commitRepo}/commit/${rawSha}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={S.shaLink}
                        title={c.sha}
                      >
                        {shortSha(rawSha)}
                      </a>
                    ) : (
                      <code style={{ fontSize: '0.72rem', color: 'var(--d-text2)' }} title={c.sha}>
                        {shortSha(rawSha)}
                      </code>
                    )}
                  </td>
                  <td style={{ ...S.td, ...S.msgCell }} title={c.message}>
                    {c.message}
                  </td>
                  <td style={{ ...S.td, fontSize: '0.72rem', whiteSpace: 'nowrap' }}>
                    {c.author}
                  </td>
                  <td style={{ ...S.td, fontFamily: 'var(--sl-font-mono, monospace)', fontSize: '0.68rem' }}>
                    {c.platform_id}
                  </td>
                  <td style={S.td}>
                    {c.epic_id ? (
                      <span style={{ ...S.epicBadge, ...S.epicTagBadge }}>{c.epic_id}</span>
                    ) : (
                      <span style={{ ...S.epicBadge, ...S.adhocBadge }}>ad-hoc</span>
                    )}
                    {!c.reconciled_at && (
                      <span style={S.reconcilePendingBadge} title="Not yet reconciled into docs">drift</span>
                    )}
                  </td>
                  <td style={{ ...S.td, fontSize: '0.72rem', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {formatDate(c.committed_at)}
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* ── Pagination ── */}
        {totalPages > 1 && (
          <div style={S.paginationBar}>
            <button
              style={{ ...S.pageBtn, ...(page <= 1 ? S.pageBtnDisabled : {}) }}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={page <= 1}
            >
              Previous
            </button>
            <span>Page {page} of {totalPages}</span>
            <button
              style={{ ...S.pageBtn, ...(page >= totalPages ? S.pageBtnDisabled : {}) }}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={page >= totalPages}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
