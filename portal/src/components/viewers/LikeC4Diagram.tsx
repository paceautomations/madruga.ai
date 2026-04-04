import { lazy, Suspense, useMemo, useRef, Component } from 'react';
import type { ReactNode } from 'react';

// Static import map — Vite requires static analysis for virtual modules.
// Add new platforms here when they are created.
const platformLoaders: Record<string, () => Promise<any>> = {
  fulano: () => import('likec4:react/fulano'),
  'madruga-ai': () => import('likec4:react/madruga-ai'),
};

interface Props {
  viewId: string;
  platform: string;
  viewPaths: Record<string, string>;
}

class DiagramErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          gap: '0.5rem',
          color: 'var(--sl-color-gray-3)',
        }}>
          <p>Erro ao carregar diagrama.</p>
          <code style={{ fontSize: '0.85em', opacity: 0.7 }}>
            {this.state.error.message}
          </code>
        </div>
      );
    }
    return this.props.children;
  }
}

function LoadingSpinner() {
  return (
    <div className="diagram-loading">
      <div className="diagram-spinner" />
      <span>Carregando diagrama...</span>
    </div>
  );
}

export default function LikeC4Diagram({ viewId, platform, viewPaths }: Props) {
  const viewPathsRef = useRef(viewPaths);
  viewPathsRef.current = viewPaths;
  const viewPathsKey = JSON.stringify(viewPaths);

  const DiagramComponent = useMemo(() => {
    const loader = platformLoaders[platform];
    if (!loader) {
      return () => <div>Platform &quot;{platform}&quot; not found in LikeC4 loader map.</div>;
    }
    return lazy(async () => {
      const mod = await loader();
      return {
        default: () => (
          <mod.LikeC4ModelProvider>
            <mod.ReactLikeC4
              viewId={viewId}
              style={{ width: '100%', height: '100%' }}
              pannable
              zoomable
              fitView
              keepAspectRatio={false}
              enableRelationshipDetails
              enableNotations
              showNavigationButtons
              onNavigateTo={(nextViewId: string) => {
                const path = viewPathsRef.current[nextViewId];
                if (path) {
                  window.location.href = path;
                }
              }}
            />
          </mod.LikeC4ModelProvider>
        ),
      };
    });
  }, [platform, viewId, viewPathsKey]);

  return (
    <DiagramErrorBoundary>
      <Suspense fallback={<LoadingSpinner />}>
        <DiagramComponent />
      </Suspense>
    </DiagramErrorBoundary>
  );
}
