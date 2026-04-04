import type { Trace, Span, TraceDetail } from './ObservabilityDashboard';
import { formatDuration, formatCost, formatTokens, formatTime } from './formatters';

// ── Props ──

interface TracesTabProps {
  traces: Trace[];
  onSelectTrace: (traceId: string) => void;
  selectedTrace: TraceDetail | null;
}

// ── Constants ──

const STATUS_COLOR: Record<string, string> = {
  completed: '#4CAF50',
  failed:    '#F44336',
  running:   '#2196F3',
  cancelled: '#9E9E9E',
};

const SVG_LEFT_LABEL_WIDTH = 120;
const SVG_BAR_AREA_WIDTH = 600;
const SVG_TOTAL_WIDTH = SVG_LEFT_LABEL_WIDTH + SVG_BAR_AREA_WIDTH + 20;
const ROW_HEIGHT = 28;
const BAR_HEIGHT = 18;
const BAR_Y_OFFSET = (ROW_HEIGHT - BAR_HEIGHT) / 2;
const MIN_BAR_WIDTH = 4;

// ── Waterfall SVG ──

function WaterfallChart({ spans, trace }: { spans: Span[]; trace: Trace }) {
  if (spans.length === 0) {
    return (
      <div style={{ padding: '1rem', color: 'var(--sl-color-gray-4, #666)', fontSize: '0.8rem' }}>
        No spans recorded for this trace.
      </div>
    );
  }

  const traceStart = new Date(trace.started_at).getTime();

  // Compute the end of the latest span (or trace completion) for scale
  let maxEnd = traceStart;
  for (const span of spans) {
    const end = span.completed_at
      ? new Date(span.completed_at).getTime()
      : span.started_at
        ? new Date(span.started_at).getTime() + (span.duration_ms ?? 0)
        : traceStart;
    if (end > maxEnd) maxEnd = end;
  }
  const totalRange = maxEnd - traceStart || 1; // avoid div-by-zero

  const svgHeight = spans.length * ROW_HEIGHT + 4;

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg
        width={SVG_TOTAL_WIDTH}
        height={svgHeight}
        viewBox={`0 0 ${SVG_TOTAL_WIDTH} ${svgHeight}`}
        style={{ display: 'block', fontFamily: 'monospace', fontSize: '11px' }}
      >
        {spans.map((span, i) => {
          const spanStart = span.started_at
            ? new Date(span.started_at).getTime()
            : traceStart;
          const spanDuration = span.duration_ms ?? 0;

          const offsetFrac = (spanStart - traceStart) / totalRange;
          const widthFrac = spanDuration / totalRange;

          const x = SVG_LEFT_LABEL_WIDTH + offsetFrac * SVG_BAR_AREA_WIDTH;
          const barWidth = Math.max(widthFrac * SVG_BAR_AREA_WIDTH, MIN_BAR_WIDTH);
          const y = i * ROW_HEIGHT + BAR_Y_OFFSET;

          const color = STATUS_COLOR[span.status] ?? STATUS_COLOR.cancelled;

          const tooltipLines = [
            `Node: ${span.node_id}`,
            `Status: ${span.status}`,
            `Duration: ${formatDuration(span.duration_ms)}`,
            `Tokens in: ${formatTokens(span.tokens_in)}`,
            `Tokens out: ${formatTokens(span.tokens_out)}`,
            `Cost: ${formatCost(span.cost_usd)}`,
          ];
          if (span.error) tooltipLines.push(`Error: ${span.error}`);
          const tooltip = tooltipLines.join('\n');

          return (
            <g key={span.run_id}>
              {/* Node label */}
              <text
                x={SVG_LEFT_LABEL_WIDTH - 8}
                y={i * ROW_HEIGHT + ROW_HEIGHT / 2}
                textAnchor="end"
                dominantBaseline="central"
                fill="var(--sl-color-gray-2, #ccc)"
              >
                {span.node_id}
              </text>

              {/* Bar */}
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={BAR_HEIGHT}
                rx={3}
                ry={3}
                fill={color}
                opacity={0.85}
              >
                <title>{tooltip}</title>
              </rect>

              {/* Duration label to the right of the bar */}
              {span.duration_ms != null && (
                <text
                  x={x + barWidth + 6}
                  y={i * ROW_HEIGHT + ROW_HEIGHT / 2}
                  dominantBaseline="central"
                  fill="var(--sl-color-gray-3, #888)"
                  fontSize="10"
                >
                  {formatDuration(span.duration_ms)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ── Legend ──

function Legend() {
  const items = [
    { color: STATUS_COLOR.completed, label: 'Completed' },
    { color: STATUS_COLOR.failed, label: 'Failed' },
    { color: STATUS_COLOR.running, label: 'Running' },
    { color: STATUS_COLOR.cancelled, label: 'Cancelled' },
  ];
  return (
    <div style={{ display: 'flex', gap: '1rem', fontSize: '0.7rem', color: 'var(--sl-color-gray-3, #888)' }}>
      {items.map((it) => (
        <span key={it.label} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: 2,
              background: it.color,
              display: 'inline-block',
            }}
          />
          {it.label}
        </span>
      ))}
    </div>
  );
}

// ── Main Component ──

export default function TracesTab({ traces, onSelectTrace, selectedTrace }: TracesTabProps) {
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
        No traces found
      </div>
    );
  }

  const selectedId = selectedTrace?.trace.trace_id ?? '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {/* Trace selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <label
          htmlFor="trace-select"
          style={{ fontSize: '0.8rem', color: 'var(--sl-color-gray-3, #888)', whiteSpace: 'nowrap' }}
        >
          Trace:
        </label>
        <select
          id="trace-select"
          value={selectedId}
          onChange={(e) => {
            if (e.target.value) onSelectTrace(e.target.value);
          }}
          style={{
            flex: 1,
            maxWidth: 420,
            padding: '0.35rem 0.5rem',
            fontSize: '0.8rem',
            fontFamily: 'monospace',
            background: 'var(--sl-color-gray-6, #1a1a1a)',
            color: 'var(--sl-color-gray-2, #ccc)',
            border: '1px solid var(--sl-color-gray-5, #333)',
            borderRadius: 4,
          }}
        >
          <option value="">Select a trace...</option>
          {traces.map((t) => (
            <option key={t.trace_id} value={t.trace_id}>
              {t.trace_id.slice(0, 8)} — {t.status} — {t.mode.toUpperCase()}
              {t.epic_id ? ` — ${t.epic_id}` : ''}
              {' — '}
              {formatTime(t.started_at)}
            </option>
          ))}
        </select>
        <Legend />
      </div>

      {/* Waterfall or empty state */}
      {selectedTrace ? (
        <div
          style={{
            background: 'var(--sl-color-gray-7, #111)',
            border: '1px solid var(--sl-color-gray-5, #333)',
            borderRadius: 6,
            padding: '0.75rem',
          }}
        >
          {/* Trace summary header */}
          <div
            style={{
              display: 'flex',
              gap: '1.5rem',
              flexWrap: 'wrap',
              marginBottom: '0.75rem',
              fontSize: '0.75rem',
              color: 'var(--sl-color-gray-3, #888)',
            }}
          >
            <span>
              Status:{' '}
              <strong style={{ color: STATUS_COLOR[selectedTrace.trace.status] ?? '#9E9E9E' }}>
                {selectedTrace.trace.status}
              </strong>
            </span>
            <span>Duration: <strong style={{ color: 'var(--sl-color-gray-2, #ccc)' }}>{formatDuration(selectedTrace.trace.total_duration_ms)}</strong></span>
            <span>Nodes: <strong style={{ color: 'var(--sl-color-gray-2, #ccc)' }}>{selectedTrace.trace.completed_nodes}/{selectedTrace.trace.total_nodes}</strong></span>
            <span>Cost: <strong style={{ color: 'var(--sl-color-gray-2, #ccc)' }}>{formatCost(selectedTrace.trace.total_cost_usd)}</strong></span>
            <span>Tokens: <strong style={{ color: 'var(--sl-color-gray-2, #ccc)' }}>{formatTokens(selectedTrace.trace.total_tokens_in)} in / {formatTokens(selectedTrace.trace.total_tokens_out)} out</strong></span>
          </div>

          <WaterfallChart spans={selectedTrace.spans} trace={selectedTrace.trace} />
        </div>
      ) : (
        <div
          style={{
            padding: '2rem',
            textAlign: 'center',
            color: 'var(--sl-color-gray-4, #666)',
            fontSize: '0.8rem',
            border: '1px dashed var(--sl-color-gray-5, #333)',
            borderRadius: 6,
          }}
        >
          Select a trace above to view the waterfall timeline.
        </div>
      )}
    </div>
  );
}
