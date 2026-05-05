/**
 * Badge component (epic 027 — T026).
 *
 * Renders one of the six vocabulary badges declared in spec FR-001 + the
 * vocabulary knowledge file:
 *   - WIREFRAME / AGUARDANDO  → slate (pending or queued for re-capture)
 *   - FALHOU                  → red (status=failed)
 *   - WEB BUILD vX / iOS vX / WEB vX → green (status=captured)
 *
 * Tokens come from `screen-flow-tokens.css` so light + dark mode track
 * the rest of the canvas (FR-043, FR-044). `role="status"` lets AT users
 * hear state changes when a screen flips between wireframe/captured/failed.
 */
import './Badge.css';

export type BadgeVariant =
  | 'wireframe'
  | 'aguardando'
  | 'falhou'
  | 'web-build'
  | 'ios'
  | 'web';

interface BadgeProps {
  variant: BadgeVariant;
  /** Optional override (e.g. `WEB BUILD v9c4f1a2`). Falls back to the variant default. */
  label?: string;
  /** Optional tooltip — used by ScreenNode to surface failure.reason on FALHOU. */
  title?: string;
}

const VARIANT_DEFAULTS: Record<BadgeVariant, string> = {
  wireframe: 'WIREFRAME',
  aguardando: 'AGUARDANDO',
  falhou: 'FALHOU',
  'web-build': 'WEB BUILD',
  ios: 'iOS',
  web: 'WEB',
};

const VARIANT_CLASS: Record<BadgeVariant, string> = {
  wireframe: 'badge-wireframe',
  aguardando: 'badge-wireframe',
  falhou: 'badge-failed',
  'web-build': 'badge-captured',
  ios: 'badge-captured',
  web: 'badge-captured',
};

export default function Badge({ variant, label, title }: BadgeProps) {
  const text = label ?? VARIANT_DEFAULTS[variant];
  const className = `screen-flow-badge ${VARIANT_CLASS[variant]}`;
  return (
    <span
      role="status"
      className={className}
      data-variant={variant}
      title={title}
    >
      {text}
    </span>
  );
}
