/**
 * WireframeBody (epic 027 — T028).
 *
 * Renders the array of `BodyComponent` entries declared in a Screen
 * using the FROZEN vocabulary of 10 component types (FR-001):
 *
 *   heading | text | input | button | link | list | card | image | divider | badge
 *
 * Decision #14 + FR-022: paleta wireframe-only (greyscale + soft accent),
 * tipografia distinta da app real (Caveat preloaded via Google Fonts) e
 * sem sombras pesadas. The visual language signals "this is a wireframe"
 * without saying so explicitly, so authors and stakeholders never confuse
 * a placeholder with a captured screen.
 *
 * Each sub-renderer is a small, branchless function so the bundle stays
 * predictable. `meta` props are read defensively because authors may
 * leave optional fields off.
 */
import type { BodyComponent } from '../../lib/screen-flow';
import './WireframeBody.css';

interface WireframeBodyProps {
  body: BodyComponent[];
}

export default function WireframeBody({ body }: WireframeBodyProps) {
  return (
    <div className="wireframe-body" role="presentation">
      {body.map((c, i) => (
        <ComponentRenderer key={`${c.type}-${c.id ?? i}`} component={c} />
      ))}
    </div>
  );
}

function ComponentRenderer({ component }: { component: BodyComponent }) {
  switch (component.type) {
    case 'heading':
      return <Heading text={component.text} />;
    case 'text':
      return <Text text={component.text} />;
    case 'input':
      return <Input text={component.text} testid={component.testid} />;
    case 'button':
      return (
        <Button
          text={component.text}
          testid={component.testid}
          variant={component.meta?.variant as string | undefined}
        />
      );
    case 'link':
      return <Link text={component.text} testid={component.testid} />;
    case 'list':
      return <List items={component.meta?.items as string[] | undefined} />;
    case 'card':
      return (
        <Card
          title={component.meta?.title as string | undefined}
          body={component.meta?.body as string | undefined}
        />
      );
    case 'image':
      return (
        <Image
          text={component.text}
          aspect={component.meta?.aspect as string | undefined}
        />
      );
    case 'divider':
      return <Divider />;
    case 'badge':
      return (
        <BadgeStub
          text={component.text}
          variant={component.meta?.variant as string | undefined}
        />
      );
    default:
      return null;
  }
}

// ── Sub-renderers ──────────────────────────────────────────────────────

function Heading({ text }: { text?: string }) {
  return <div className="wf-heading">{text ?? 'Heading'}</div>;
}

function Text({ text }: { text?: string }) {
  return <div className="wf-text">{text ?? 'Lorem ipsum'}</div>;
}

function Input({ text, testid }: { text?: string; testid?: string }) {
  return (
    <div className="wf-input" data-testid={testid}>
      <span className="wf-input__placeholder">{text ?? 'input'}</span>
    </div>
  );
}

function Button({
  text,
  variant,
  testid,
}: {
  text?: string;
  variant?: string;
  testid?: string;
}) {
  return (
    <button
      type="button"
      className={`wf-button wf-button--${variant ?? 'default'}`}
      data-testid={testid}
    >
      {text ?? 'Button'}
    </button>
  );
}

function Link({ text, testid }: { text?: string; testid?: string }) {
  return (
    <a className="wf-link" data-testid={testid} href="#" onClick={(e) => e.preventDefault()}>
      {text ?? 'Link'}
    </a>
  );
}

function List({ items }: { items?: string[] }) {
  const rows = items ?? ['Item 1', 'Item 2', 'Item 3'];
  return (
    <ul className="wf-list">
      {rows.map((row) => (
        <li key={row} className="wf-list__item">
          {row}
        </li>
      ))}
    </ul>
  );
}

function Card({ title, body }: { title?: string; body?: string }) {
  return (
    <div className="wf-card">
      {title ? <div className="wf-card__title">{title}</div> : null}
      {body ? <div className="wf-card__body">{body}</div> : null}
      {!title && !body ? <div className="wf-card__placeholder">Card</div> : null}
    </div>
  );
}

function Image({ text, aspect }: { text?: string; aspect?: string }) {
  return (
    <div
      className="wf-image"
      style={aspect ? { aspectRatio: aspect.replace(':', ' / ') } : undefined}
      role="img"
      aria-label={text ?? 'Image placeholder'}
    >
      <span className="wf-image__icon" aria-hidden="true">
        🖼
      </span>
      {text ? <span className="wf-image__caption">{text}</span> : null}
    </div>
  );
}

function Divider() {
  return <hr className="wf-divider" />;
}

function BadgeStub({ text, variant }: { text?: string; variant?: string }) {
  return (
    <span
      className={`wf-badge wf-badge--${variant ?? 'default'}`}
      data-variant={variant}
    >
      {text ?? 'Badge'}
    </span>
  );
}
