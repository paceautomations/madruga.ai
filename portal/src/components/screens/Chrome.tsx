/**
 * Chrome component (epic 027 — T027).
 *
 * Minimal device frame around a screen: rounded outer border + a small,
 * unobtrusive label (`iPhone 15 / 393×852` or `Desktop / 1440×900`).
 *
 * Decision #15 (pitch.md): we deliberately DO NOT render fake status
 * bars (no "9:41", no battery, no carrier). They suggest production-
 * fidelity that wireframes / brownfield captures don't have, and they
 * shift focus away from flow content.
 *
 * Tokens come from screen-flow-tokens.css (FR-043, FR-044) so the chrome
 * tracks light/dark mode without hard-coded colours.
 */
import type { ReactNode } from 'react';
import type { CaptureProfile } from '../../lib/screen-flow';
import './Chrome.css';

const PROFILE_LABELS: Record<CaptureProfile, string> = {
  'iphone-15': 'iPhone 15 / 393×852',
  desktop: 'Desktop / 1440×900',
};

const PROFILE_DIMENSIONS: Record<CaptureProfile, { w: number; h: number }> = {
  'iphone-15': { w: 393, h: 852 },
  desktop: { w: 1440, h: 900 },
};

interface ChromeProps {
  profile: CaptureProfile;
  /** Body content (wireframe sub-renderers or captured <img>). */
  children: ReactNode;
  /** Optional override of the visible label, e.g. screen.title. */
  label?: string;
}

export default function Chrome({ profile, children, label }: ChromeProps) {
  const dim = PROFILE_DIMENSIONS[profile];
  const subtitle = PROFILE_LABELS[profile];
  return (
    <div
      className={`screen-chrome screen-chrome--${profile}`}
      data-profile={profile}
      style={{ '--chrome-w': `${dim.w}px`, '--chrome-h': `${dim.h}px` } as never}
    >
      <div className="screen-chrome__body">{children}</div>
      <div className="screen-chrome__label" aria-hidden="true">
        {label ?? subtitle}
      </div>
    </div>
  );
}
