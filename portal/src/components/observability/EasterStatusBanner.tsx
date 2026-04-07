import type { SessionsData } from './ObservabilityDashboard';
import { formatUptime } from './formatters';

interface EasterStatusBannerProps {
  sessions: SessionsData | null;
  connected: boolean;
  todayCompletedCount: number;
}

const PULSE_CSS = `
@keyframes easter-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
`;

type BannerTheme = { dot: string; label: string; labelColor: string; bg: string; border: string };

function getTheme(sessions: SessionsData | null, connected: boolean): BannerTheme {
  if (!connected || !sessions) {
    return {
      dot: '#ef4444', label: 'Unreachable', labelColor: '#ef4444',
      bg: 'color-mix(in srgb, #ef4444 8%, var(--sl-color-gray-7, #111))',
      border: '#ef444440',
    };
  }
  if (sessions.easter_state === 'degraded') {
    return {
      dot: '#f59e0b', label: 'Degraded', labelColor: '#f59e0b',
      bg: 'color-mix(in srgb, #f59e0b 8%, var(--sl-color-gray-7, #111))',
      border: '#f59e0b40',
    };
  }
  return {
    dot: '#22c55e', label: 'Running', labelColor: '#22c55e',
    bg: 'color-mix(in srgb, #22c55e 6%, var(--sl-color-gray-7, #111))',
    border: '#22c55e40',
  };
}

export default function EasterStatusBanner({ sessions, connected, todayCompletedCount }: EasterStatusBannerProps) {
  const theme = getTheme(sessions, connected);
  const isAlive = connected && sessions != null;

  const stats: { label: string; value: string }[] = [
    { label: 'Active', value: String(sessions?.running_epics.length ?? 0) },
    { label: 'Queued', value: String(sessions?.queued_epics.length ?? 0) },
    { label: 'Completed Today', value: String(todayCompletedCount) },
    { label: 'Poll Interval', value: isAlive ? `${sessions.poll_interval_seconds}s` : '\u2014' },
  ];

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: PULSE_CSS }} />
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          margin: 0,
          background: theme.bg, border: `1px solid ${theme.border}`,
          borderRadius: 6, padding: '0.75rem 1.25rem',
          minHeight: 80,
        }}
      >
        {/* Left: status dot + label */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', margin: 0 }}>
          <div
            style={{
              width: 10, height: 10, borderRadius: '50%', background: theme.dot, flexShrink: 0, margin: 0,
              animation: isAlive ? 'easter-pulse 2s infinite' : 'none',
            }}
          />
          <div style={{ margin: 0 }}>
            <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--sl-color-white, #fff)', margin: 0, lineHeight: 1.3 }}>
              Easter Service{' '}
              <span style={{ color: theme.labelColor, fontSize: '0.75rem' }}>{theme.label}</span>
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--sl-color-gray-3, #888)', margin: 0, lineHeight: 1.3 }}>
              {isAlive
                ? `PID ${sessions.pid} \u00B7 up ${formatUptime(sessions.uptime_seconds)}`
                : 'Service not reachable'}
            </div>
          </div>
        </div>

        {/* Right: stats */}
        <div style={{ display: 'flex', gap: '1.5rem', margin: 0 }}>
          {stats.map((s) => (
            <div key={s.label} style={{ textAlign: 'center', margin: 0 }}>
              <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--sl-color-white, #fff)', lineHeight: 1.2, margin: 0 }}>
                {s.value}
              </div>
              <div style={{ fontSize: '0.62rem', color: 'var(--sl-color-gray-4, #666)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
