import type { StatsData, DayStat, TopNode } from './ObservabilityDashboard';
import { formatTokens, formatCostRounded } from './formatters';

// ── Types ──

interface CostTabProps {
  stats: StatsData | null;
  connected: boolean;
}

// ── Helpers ──

function formatDay(iso: string): string {
  try {
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return iso;
  }
}

// ── Styles ──

const cardStyle: React.CSSProperties = {
  padding: '0.75rem 1rem',
  background: 'var(--sl-color-gray-6, #1a1a1a)',
  borderRadius: 6,
  border: '1px solid var(--sl-color-gray-5, #333)',
  minWidth: 120,
  flex: '1 1 0',
};

const cardLabelStyle: React.CSSProperties = {
  fontSize: '0.65rem',
  color: 'var(--sl-color-gray-3, #888)',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.04em',
  fontWeight: 500,
  marginBottom: '0.25rem',
};

const cardValueStyle: React.CSSProperties = {
  fontSize: '1.25rem',
  fontWeight: 700,
  color: 'var(--sl-color-white, #fff)',
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: '0.75rem',
  fontWeight: 600,
  color: 'var(--sl-color-gray-2, #ccc)',
  textTransform: 'uppercase' as const,
  letterSpacing: '0.04em',
  marginBottom: '0.5rem',
};

// ── Bar Chart Constants ──

const CHART_WIDTH = 600;
const CHART_HEIGHT = 200;
const BAR_GAP = 4;
const LABEL_HEIGHT = 20;
const Y_AXIS_WIDTH = 50;
const CHART_PAD_TOP = 10;

// ── Bar Chart ──

function CostBarChart({ days }: { days: DayStat[] }) {
  if (days.length === 0) return null;

  const data = days.slice(-30); // last 30 days
  const maxCost = Math.max(...data.map((d) => d.total_cost), 0.01);
  const barCount = data.length;
  const availableWidth = CHART_WIDTH - Y_AXIS_WIDTH;
  const barWidth = Math.max(4, (availableWidth - BAR_GAP * barCount) / barCount);
  const chartArea = CHART_HEIGHT - LABEL_HEIGHT - CHART_PAD_TOP;

  // Y-axis ticks (3 levels)
  const ticks = [0, maxCost / 2, maxCost];

  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      style={{ width: '100%', maxWidth: CHART_WIDTH, height: 'auto' }}
      role="img"
      aria-label="Cost per day bar chart"
    >
      {/* Y-axis labels */}
      {ticks.map((val, i) => {
        const y = CHART_PAD_TOP + chartArea - (val / maxCost) * chartArea;
        return (
          <g key={i}>
            <line
              x1={Y_AXIS_WIDTH}
              y1={y}
              x2={CHART_WIDTH}
              y2={y}
              stroke="var(--sl-color-gray-5, #333)"
              strokeDasharray={i === 0 ? undefined : '4,4'}
              strokeWidth={0.5}
            />
            <text
              x={Y_AXIS_WIDTH - 6}
              y={y + 3}
              textAnchor="end"
              fill="var(--sl-color-gray-4, #666)"
              fontSize={9}
            >
              ${val.toFixed(2)}
            </text>
          </g>
        );
      })}

      {/* Bars */}
      {data.map((d, i) => {
        const x = Y_AXIS_WIDTH + i * (barWidth + BAR_GAP);
        const h = (d.total_cost / maxCost) * chartArea;
        const y = CHART_PAD_TOP + chartArea - h;

        const showLabel = barCount <= 15 || i % Math.ceil(barCount / 10) === 0;
        return (
          <g key={d.day}>
            <rect
              x={x}
              y={y}
              width={barWidth}
              height={Math.max(h, 1)}
              rx={2}
              fill="var(--sl-color-accent, #0284c7)"
              opacity={0.85}
            >
              <title>{`${formatDay(d.day)}: ${formatCostRounded(d.total_cost)} (${d.runs} run${d.runs !== 1 ? 's' : ''})`}</title>
            </rect>
            {showLabel && (
              <text
                x={x + barWidth / 2}
                y={CHART_HEIGHT - 2}
                textAnchor="middle"
                fill="var(--sl-color-gray-4, #666)"
                fontSize={8}
                transform={barCount > 10 ? `rotate(-45, ${x + barWidth / 2}, ${CHART_HEIGHT - 2})` : undefined}
              >
                {formatDay(d.day)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ── Top Nodes ──

function TopNodesList({ nodes }: { nodes: TopNode[] }) {
  if (nodes.length === 0) {
    return (
      <div style={{ fontSize: '0.8rem', color: 'var(--sl-color-gray-4, #666)' }}>
        No node cost data available
      </div>
    );
  }

  const maxCost = Math.max(...nodes.map((n) => n.total_cost), 0.01);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
      {nodes.map((node) => {
        const pct = (node.total_cost / maxCost) * 100;
        return (
          <div key={node.node_id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span
              style={{
                width: 90,
                fontSize: '0.75rem',
                fontFamily: 'monospace',
                color: 'var(--sl-color-gray-2, #ccc)',
                textAlign: 'right',
                flexShrink: 0,
              }}
            >
              {node.node_id}
            </span>
            <div
              style={{
                flex: 1,
                height: 16,
                background: 'var(--sl-color-gray-6, #1a1a1a)',
                borderRadius: 3,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: '100%',
                  background: 'var(--sl-color-accent, #0284c7)',
                  opacity: 0.75,
                  borderRadius: 3,
                  transition: 'width 0.3s',
                }}
              />
            </div>
            <span
              style={{
                width: 60,
                fontSize: '0.7rem',
                color: 'var(--sl-color-gray-3, #888)',
                flexShrink: 0,
              }}
            >
              {formatCostRounded(node.total_cost)}
            </span>
            <span
              style={{
                width: 45,
                fontSize: '0.65rem',
                color: 'var(--sl-color-gray-4, #666)',
                flexShrink: 0,
              }}
            >
              {node.run_count} run{node.run_count !== 1 ? 's' : ''}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Main Component ──

export default function CostTab({ stats, connected }: CostTabProps) {
  if (!stats) {
    return (
      <div
        style={{
          padding: '2rem',
          textAlign: 'center',
          color: 'var(--sl-color-gray-4, #666)',
          fontSize: '0.85rem',
        }}
      >
        {connected ? 'No cost data available' : 'Waiting for Easter connection...'}
      </div>
    );
  }

  const { summary, stats: days, top_nodes } = stats;
  const sortedNodes = top_nodes ?? [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Summary Cards */}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div style={cardStyle}>
          <div style={cardLabelStyle}>Total Cost</div>
          <div style={cardValueStyle}>{formatCostRounded(summary.total_cost)}</div>
        </div>
        <div style={cardStyle}>
          <div style={cardLabelStyle}>Tokens In</div>
          <div style={cardValueStyle}>{formatTokens(summary.total_tokens_in)}</div>
        </div>
        <div style={cardStyle}>
          <div style={cardLabelStyle}>Tokens Out</div>
          <div style={cardValueStyle}>{formatTokens(summary.total_tokens_out)}</div>
        </div>
        <div style={cardStyle}>
          <div style={cardLabelStyle}>Avg Cost / Run</div>
          <div style={cardValueStyle}>{formatCostRounded(summary.avg_cost_per_run)}</div>
        </div>
        <div style={cardStyle}>
          <div style={cardLabelStyle}>Total Runs</div>
          <div style={cardValueStyle}>{summary.total_runs}</div>
        </div>
      </div>

      {/* Bar Chart */}
      <div>
        <div style={sectionTitleStyle}>Cost per Day</div>
        {days.length > 0 ? (
          <CostBarChart days={days} />
        ) : (
          <div style={{ fontSize: '0.8rem', color: 'var(--sl-color-gray-4, #666)' }}>
            No daily data available
          </div>
        )}
      </div>

      {/* Top 5 Nodes by Cost */}
      <div>
        <div style={sectionTitleStyle}>Top 5 Nodes by Cost</div>
        <TopNodesList nodes={sortedNodes} />
      </div>
    </div>
  );
}
