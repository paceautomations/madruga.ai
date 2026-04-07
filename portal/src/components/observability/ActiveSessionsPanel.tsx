import { useState, useEffect } from 'react';
import type { SessionsData, ActiveSession } from './ObservabilityDashboard';
import { formatCostRounded, formatRelativeTime, formatUptime } from './formatters';

// ── L2 Pipeline Nodes ──

const L2_NODES = [
  { id: 'epic-context', short: 'EC' },
  { id: 'specify', short: 'SP' },
  { id: 'clarify', short: 'CL' },
  { id: 'plan', short: 'PL' },
  { id: 'tasks', short: 'TK' },
  { id: 'analyze-pre', short: 'A1' },
  { id: 'implement', short: 'IM' },
  { id: 'analyze-post', short: 'A2' },
  { id: 'judge', short: 'JG' },
  { id: 'qa', short: 'QA' },
  { id: 'reconcile', short: 'RE' },
  { id: 'roadmap-reassess', short: 'RM' },
] as const;

const NODE_COLORS: Record<string, { bg: string; color: string }> = {
  completed: { bg: '#22c55e', color: '#fff' },
  running: { bg: '#6366f1', color: '#fff' },
  failed: { bg: '#ef4444', color: '#fff' },
  cancelled: { bg: '#9e9e9e', color: '#fff' },
  pending: { bg: 'var(--sl-color-gray-5, #333)', color: 'var(--sl-color-gray-3, #888)' },
};

const PULSE_NODE_CSS = `
@keyframes node-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
`;

// ── Helpers ──

function getSessionStatus(session: ActiveSession): { label: string; bg: string; color: string } {
  if (!session.current_node && session.completed_nodes === 0) {
    return { label: 'Starting', bg: '#2196F320', color: '#2196F3' };
  }
  if (session.last_activity) {
    const diff = (Date.now() - new Date(session.last_activity).getTime()) / 1000;
    if (diff > 300) return { label: 'Stalled', bg: '#ef444420', color: '#ef4444' };
  }
  if (session.current_node) {
    return { label: 'Executing', bg: '#2196F320', color: '#2196F3' };
  }
  return { label: 'Idle', bg: '#9E9E9E20', color: '#9E9E9E' };
}

function formatWallTime(startedAt: string | null, now: number): string {
  if (!startedAt) return '\u2014';
  const diff = Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 1000));
  return formatUptime(diff);
}

function getNodeStatus(session: ActiveSession, nodeId: string): string {
  const match = session.node_statuses.find((n) => n.node_id === nodeId);
  if (match) return match.status;
  if (session.current_node === nodeId) return 'running';
  return 'pending';
}

// ── Sub-components ──

function SessionCard({ session, hasConflict }: { session: ActiveSession; hasConflict: boolean }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const status = getSessionStatus(session);
  const progress = session.total_nodes > 0
    ? Math.round((session.completed_nodes / session.total_nodes) * 100)
    : 0;
  const accentColor = status.label === 'Stalled' ? '#f59e0b' : '#6366f1';

  return (
    <div style={{
      border: `1px solid ${status.label === 'Stalled' ? '#f59e0b60' : 'var(--sl-color-gray-5, #333)'}`,
      borderRadius: 8, padding: '1rem 1rem 1rem 1.15rem',
      background: 'var(--sl-color-gray-7, #0d0d0d)',
      position: 'relative', overflow: 'hidden', margin: 0,
    }}>
      {/* Left accent bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, width: 4, height: '100%',
        background: accentColor, borderRadius: '4px 0 0 4px',
      }} />

      {/* Top: epic name + status */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '0 0 0.65rem 0' }}>
        <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--sl-color-white, #fff)', margin: 0 }}>
          {session.epic_id}
          {hasConflict && (
            <span style={{ fontSize: '0.68rem', color: '#ef4444', marginLeft: '0.5rem' }}>
              &#9888; CONFLICT
            </span>
          )}
        </div>
        <span style={{
          fontSize: '0.68rem', fontWeight: 600, padding: '0.15rem 0.5rem',
          borderRadius: 5, background: status.bg, color: status.color,
          border: `1px solid ${status.color}40`, margin: 0, lineHeight: 1.4,
        }}>
          {status.label}
        </span>
      </div>

      {/* Meta grid 2x2 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem 1rem', margin: '0 0 0.75rem 0' }}>
        {[
          { label: 'Current Node', value: session.current_node ?? '\u2014', warn: false },
          { label: 'Wall Time', value: formatWallTime(session.started_at, now), warn: status.label === 'Stalled' },
          { label: 'Session Cost', value: formatCostRounded(session.session_cost_usd), warn: false },
          { label: 'Last Heartbeat', value: formatRelativeTime(session.last_activity), warn: status.label === 'Stalled' },
        ].map((item) => (
          <div key={item.label} style={{ margin: 0 }}>
            <div style={{ fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--sl-color-gray-4, #666)', margin: 0, lineHeight: 1.4 }}>
              {item.label}
            </div>
            <div style={{ fontSize: '0.8rem', fontWeight: 500, color: item.warn ? '#ef4444' : 'var(--sl-color-white, #fff)', margin: 0, lineHeight: 1.4 }}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {/* Progress bar */}
      <div style={{ margin: '0 0 0.6rem 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--sl-color-gray-4, #666)', margin: '0 0 0.2rem 0' }}>
          <span style={{ margin: 0 }}>Pipeline Progress</span>
          <span style={{ margin: 0 }}>{session.completed_nodes} / {session.total_nodes} nodes</span>
        </div>
        <div style={{ height: 6, background: 'var(--sl-color-gray-5, #333)', borderRadius: 3, overflow: 'hidden', margin: 0 }}>
          <div style={{
            height: '100%', borderRadius: 3, transition: 'width 0.5s',
            width: `${progress}%`, margin: 0,
            background: status.label === 'Stalled' ? '#f59e0b' : '#6366f1',
          }} />
        </div>
      </div>

      {/* Mini pipeline */}
      <div style={{ display: 'flex', gap: 3, margin: 0 }}>
        {L2_NODES.map((node) => {
          const nStatus = getNodeStatus(session, node.id);
          const colors = NODE_COLORS[nStatus] ?? NODE_COLORS.pending;
          const isRunning = nStatus === 'running';
          return (
            <div
              key={node.id}
              title={`${node.id} (${nStatus})`}
              style={{
                width: 18, height: 18, borderRadius: 4, flexShrink: 0, margin: 0,
                fontSize: '0.5rem', fontWeight: 600,
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                background: colors.bg, color: colors.color,
                animation: isRunning ? 'node-pulse 1.5s infinite' : 'none',
              }}
            >
              {node.short}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main Component ──

interface ActiveSessionsPanelProps {
  sessions: SessionsData;
}

export default function ActiveSessionsPanel({ sessions }: ActiveSessionsPanelProps) {
  const runningCount = sessions.running_epics.length;
  const allEpicIds = sessions.running_epics.map((s) => s.epic_id);

  const platformCounts = new Map<string, number>();
  for (const s of sessions.running_epics) {
    platformCounts.set(s.platform_id, (platformCounts.get(s.platform_id) ?? 0) + 1);
  }

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: PULSE_NODE_CSS }} />
      <div style={{
        background: 'var(--sl-color-gray-6, #1a1a1a)',
        border: '1px solid var(--sl-color-gray-5, #333)',
        borderRadius: 8, overflow: 'hidden', margin: 0,
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0.7rem 1.25rem', margin: 0,
          borderBottom: '1px solid var(--sl-color-gray-5, #333)',
          background: 'var(--sl-color-gray-7, #0d0d0d)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--sl-color-white, #fff)', margin: 0 }}>
              Active Sessions
            </span>
            <span style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              background: '#6366f1', color: '#fff', fontSize: '0.65rem', fontWeight: 600,
              borderRadius: 10, padding: '0.1rem 0.5rem', minWidth: 20, margin: 0,
            }}>
              {runningCount}
            </span>
          </div>
          <span style={{ fontSize: '0.68rem', color: 'var(--sl-color-gray-4, #666)', margin: 0 }}>
            Auto-refreshes every 5s
          </span>
        </div>

        {/* Session cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: runningCount > 1 ? '1fr 1fr' : '1fr',
          gap: '1rem', padding: '1rem 1.25rem', margin: 0,
        }}>
          {sessions.running_epics.map((session) => (
            <SessionCard
              key={session.epic_id}
              session={session}
              hasConflict={(platformCounts.get(session.platform_id) ?? 0) > 1}
            />
          ))}
        </div>

        {/* Poll info bar */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap',
          padding: '0.6rem 1.25rem', fontSize: '0.72rem', margin: 0,
          color: 'var(--sl-color-gray-4, #666)',
          borderTop: '1px solid var(--sl-color-gray-5, #333)',
        }}>
          <span style={{ margin: 0 }}>Epics found: <code style={{ fontSize: '0.68rem', background: 'var(--sl-color-gray-5, #333)', padding: '0.12rem 0.35rem', borderRadius: 4, margin: 0 }}>
            {allEpicIds.length > 0 ? allEpicIds.join(', ') : 'none'}
          </code></span>
          <span style={{ marginLeft: 'auto' }}>Poll interval: <code style={{ fontSize: '0.68rem', background: 'var(--sl-color-gray-5, #333)', padding: '0.12rem 0.35rem', borderRadius: 4, margin: 0 }}>
            {sessions.poll_interval_seconds}s
          </code></span>
        </div>
      </div>
    </>
  );
}
