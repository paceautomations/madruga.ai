export function formatDuration(ms: number | null): string {
  if (ms == null) return '\u2014';
  if (ms < 1_000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1_000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.round((ms % 60_000) / 1_000);
  return `${mins}m ${secs}s`;
}

export function formatCost(usd: number | null): string {
  if (usd == null) return '\u2014';
  return `$${usd.toFixed(4)}`;
}

export function formatCostRounded(usd: number): string {
  return `$${usd.toFixed(2)}`;
}

export function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function formatTokens(n: number | null): string {
  if (n == null) return '\u2014';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
