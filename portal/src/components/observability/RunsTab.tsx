import { useState, useCallback } from 'react';
import type { Trace, Span, TraceDetail } from './ObservabilityDashboard';
import { formatDuration, formatCost, formatTime } from './formatters';

// ── Types ──

interface RunsTabProps {
  traces: Trace[];
  onSelectTrace: (traceId: string) => void;
  selectedTrace: TraceDetail | null;
}

// ── Helpers ──

const STATUS_BADGE: Record<string, { bg: string; color: string; label: string }> = {
  running:   { bg: '#2196F320', color: '#2196F3', label: 'Running' },
  completed: { bg: '#4CAF5020', color: '#4CAF50', label: 'Completed' },
  failed:    { bg: '#F4433620', color: '#F44336', label: 'Failed' },
  cancelled: { bg: '#9E9E9E20', color: '#9E9E9E', label: 'Cancelled' },
};

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

// ── Badge ──

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

// ── Span Detail Row ──

function SpanRow({ span }: { span: Span }) {
  const spanBadge = STATUS_BADGE[span.status] ?? STATUS_BADGE.cancelled;
  return (
    <tr>
      <td style={{ ...tdStyle, paddingLeft: '2rem', fontFamily: 'monospace', fontSize: '0.75rem' }}>
        {span.node_id}
      </td>
      <td style={tdStyle}>
        <span style={{ color: spanBadge.color, fontSize: '0.75rem' }}>{span.status}</span>
      </td>
      <td style={tdStyle}>{formatDuration(span.duration_ms)}</td>
      <td style={tdStyle}>{formatCost(span.cost_usd)}</td>
      <td style={tdStyle}>
        {span.error ? (
          <span style={{ color: '#F44336', fontSize: '0.7rem' }} title={span.error}>
            {span.error.length > 60 ? span.error.slice(0, 60) + '...' : span.error}
          </span>
        ) : '—'}
      </td>
    </tr>
  );
}

// ── Main Component ──

export default function RunsTab({ traces, onSelectTrace, selectedTrace }: RunsTabProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleRowClick = useCallback(
    (traceId: string) => {
      if (expandedId === traceId) {
        setExpandedId(null);
      } else {
        setExpandedId(traceId);
        onSelectTrace(traceId);
      }
    },
    [expandedId, onSelectTrace],
  );

  if (!traces.length) {
    return (
      <div
        style={{
          padding: '2rem',
          textAlign: 'center',
          color: 'var(--sl-color-gray-4, #666)',
          fontSize: '0.85rem',
        }}
      >
        No runs found
      </div>
    );
  }

  return (
    <table style={tableStyle}>
      <thead>
        <tr>
          <th style={thStyle}>Status</th>
          <th style={thStyle}>Trace</th>
          <th style={thStyle}>Epic</th>
          <th style={thStyle}>Duration</th>
          <th style={thStyle}>Cost</th>
          <th style={thStyle}>Nodes</th>
          <th style={thStyle}>Started</th>
        </tr>
      </thead>
      <tbody>
        {traces.map((trace) => {
          const isExpanded = expandedId === trace.trace_id;
          const spans =
            isExpanded && selectedTrace?.trace.trace_id === trace.trace_id
              ? selectedTrace.spans
              : null;

          return (
            <TraceRow
              key={trace.trace_id}
              trace={trace}
              isExpanded={isExpanded}
              spans={spans}
              onClick={handleRowClick}
            />
          );
        })}
      </tbody>
    </table>
  );
}

// ── Trace Row (extracted to avoid inline re-renders) ──

function TraceRow({
  trace,
  isExpanded,
  spans,
  onClick,
}: {
  trace: Trace;
  isExpanded: boolean;
  spans: Span[] | null;
  onClick: (id: string) => void;
}) {
  return (
    <>
      <tr
        onClick={() => onClick(trace.trace_id)}
        style={{
          cursor: 'pointer',
          background: isExpanded ? 'var(--sl-color-gray-6, #1a1a1a)' : 'transparent',
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => {
          if (!isExpanded) e.currentTarget.style.background = 'var(--sl-color-gray-6, #1a1a1a)';
        }}
        onMouseLeave={(e) => {
          if (!isExpanded) e.currentTarget.style.background = 'transparent';
        }}
      >
        <td style={tdStyle}>
          <StatusBadge status={trace.status} />
        </td>
        <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: '0.75rem' }}>
          {trace.trace_id.slice(0, 8)}
          <span style={{ color: 'var(--sl-color-gray-4, #666)', marginLeft: '0.4rem' }}>
            {trace.mode.toUpperCase()}
          </span>
        </td>
        <td style={tdStyle}>{trace.epic_id ?? '—'}</td>
        <td style={tdStyle}>{formatDuration(trace.total_duration_ms)}</td>
        <td style={tdStyle}>{formatCost(trace.total_cost_usd)}</td>
        <td style={tdStyle}>
          {trace.completed_nodes}/{trace.total_nodes}
        </td>
        <td style={{ ...tdStyle, fontSize: '0.75rem' }}>{formatTime(trace.started_at)}</td>
      </tr>

      {/* Expanded span details */}
      {isExpanded && (
        <tr>
          <td colSpan={7} style={{ padding: 0 }}>
            <div
              style={{
                background: 'var(--sl-color-gray-7, #111)',
                borderLeft: '3px solid var(--sl-color-accent, #0284c7)',
                margin: '0 0.5rem',
              }}
            >
              {spans == null ? (
                <div
                  style={{
                    padding: '0.75rem 1rem',
                    color: 'var(--sl-color-gray-4, #666)',
                    fontSize: '0.8rem',
                  }}
                >
                  Loading spans...
                </div>
              ) : spans.length === 0 ? (
                <div
                  style={{
                    padding: '0.75rem 1rem',
                    color: 'var(--sl-color-gray-4, #666)',
                    fontSize: '0.8rem',
                  }}
                >
                  No spans recorded
                </div>
              ) : (
                <table style={{ ...tableStyle, fontSize: '0.75rem' }}>
                  <thead>
                    <tr>
                      <th style={{ ...thStyle, paddingLeft: '2rem' }}>Node</th>
                      <th style={thStyle}>Status</th>
                      <th style={thStyle}>Duration</th>
                      <th style={thStyle}>Cost</th>
                      <th style={thStyle}>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {spans.map((span) => (
                      <SpanRow key={span.run_id} span={span} />
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
