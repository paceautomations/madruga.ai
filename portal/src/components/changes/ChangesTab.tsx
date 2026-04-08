import { useMemo, useState } from 'react';

// ── Types ──

interface Commit {
  sha: string;
  message: string;
  author: string;
  platform_id: string;
  epic_id: string | null;
  source: string;
  committed_at: string;
  files: string[];
}

interface CommitsData {
  generated_at: string;
  commits: Commit[];
  stats: {
    by_epic: Record<string, number>;
    by_platform: Record<string, number>;
    adhoc_pct: number;
  };
}

interface ChangesTabProps {
  /** Pre-loaded commits-status.json data (null if file missing). */
  data: CommitsData | null;
  /** GitHub base URL derived from platform.yaml repo config. */
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
  msgCell: {
    maxWidth: '320px', overflow: 'hidden',
    textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
  } as const,

  empty: { textAlign: 'center' as const, padding: '3rem', color: 'var(--d-text3)' },
  footer: {
    fontSize: '0.65rem', color: 'var(--d-text4)',
    textAlign: 'right' as const, marginTop: '0.75rem', opacity: 0.6,
  },
} as const;

// ── Component ──

export default function ChangesTab({ data, repoUrl }: ChangesTabProps) {
  const [platformFilter, setPlatformFilter] = useState('all');
  const [epicFilter, setEpicFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState<'all' | 'epic' | 'adhoc'>('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Derive filter options
  const { platforms, epics } = useMemo(() => {
    if (!data) return { platforms: [] as string[], epics: [] as string[] };
    const p = Object.keys(data.stats.by_platform).sort();
    const e = Object.keys(data.stats.by_epic).sort();
    return { platforms: p, epics: e };
  }, [data]);

  // Apply filters
  const filtered = useMemo(() => {
    if (!data) return [];
    return data.commits.filter((c) => {
      if (platformFilter !== 'all' && c.platform_id !== platformFilter) return false;
      if (epicFilter !== 'all') {
        if (epicFilter === '__adhoc__' && c.epic_id !== null) return false;
        if (epicFilter !== '__adhoc__' && c.epic_id !== epicFilter) return false;
      }
      if (typeFilter === 'epic' && c.epic_id === null) return false;
      if (typeFilter === 'adhoc' && c.epic_id !== null) return false;
      if (dateFrom && c.committed_at.slice(0, 10) < dateFrom) return false;
      if (dateTo && c.committed_at.slice(0, 10) > dateTo) return false;
      return true;
    });
  }, [data, platformFilter, epicFilter, typeFilter, dateFrom, dateTo]);

  if (!data) {
    return <div style={S.empty}>No commit data available. Run <code>make status-json</code> to generate.</div>;
  }

  const totalCommits = data.commits.length;
  const epicCount = Object.keys(data.stats.by_epic).length;
  const adhocPct = data.stats.adhoc_pct;

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
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <h2 style={S.h2}>Commits by Epic</h2>
          <span style={S.meta}>{epicCount} epics tracked</span>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {Object.entries(data.stats.by_epic)
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
          {Object.keys(data.stats.by_epic).length === 0 && (
            <span style={{ fontSize: '0.72rem', color: 'var(--d-text4)' }}>No epic commits yet</span>
          )}
        </div>
      </div>

      {/* ── Filters ── */}
      <div style={S.section}>
        <div style={S.sectionHeader}>
          <h2 style={S.h2}>Commit Log</h2>
          <span style={S.meta}>{filtered.length} of {totalCommits} commits</span>
        </div>

        <div style={S.filterBar}>
          <span style={S.filterLabel}>Platform</span>
          <select style={S.select} value={platformFilter} onChange={(e) => setPlatformFilter(e.target.value)}>
            <option value="all">All</option>
            {platforms.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>

          <span style={S.filterLabel}>Epic</span>
          <select style={S.select} value={epicFilter} onChange={(e) => setEpicFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="__adhoc__">Ad-hoc only</option>
            {epics.map((ep) => <option key={ep} value={ep}>{ep}</option>)}
          </select>

          <span style={S.filterLabel}>Type</span>
          <select style={S.select} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as 'all' | 'epic' | 'adhoc')}>
            <option value="all">All</option>
            <option value="epic">Epic</option>
            <option value="adhoc">Ad-hoc</option>
          </select>

          <span style={S.filterLabel}>From</span>
          <input type="date" style={S.input} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />

          <span style={S.filterLabel}>To</span>
          <input type="date" style={S.input} value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>

        {/* ── Table ── */}
        <div style={{ overflowX: 'auto' }}>
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
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ ...S.td, textAlign: 'center', color: 'var(--d-text4)', padding: '1.5rem' }}>
                    No commits match the current filters.
                  </td>
                </tr>
              )}
              {filtered.map((c) => (
                <tr key={`${c.sha}-${c.platform_id}`}>
                  <td style={S.td}>
                    {repoUrl ? (
                      <a
                        href={`${repoUrl}/commit/${c.sha}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={S.shaLink}
                        title={c.sha}
                      >
                        {shortSha(c.sha)}
                      </a>
                    ) : (
                      <code style={{ fontSize: '0.72rem', color: 'var(--d-text2)' }} title={c.sha}>
                        {shortSha(c.sha)}
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
                  </td>
                  <td style={{ ...S.td, fontSize: '0.72rem', whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {formatDate(c.committed_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Footer ── */}
      <div style={S.footer}>
        Generated {data.generated_at ? formatDate(data.generated_at) : 'unknown'}
      </div>
    </div>
  );
}
