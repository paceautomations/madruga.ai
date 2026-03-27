import { lazy, Suspense, useMemo } from 'react';

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

export default function LikeC4Diagram({ viewId, platform, viewPaths }: Props) {
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
              enableElementDetails
              enableRelationshipDetails
              enableNotations
              onNavigateTo={(nextViewId: string) => {
                const path = viewPaths[nextViewId];
                if (path) {
                  window.location.href = path;
                }
              }}
            />
          </mod.LikeC4ModelProvider>
        ),
      };
    });
  }, [platform, viewId, viewPaths]);

  return (
    <Suspense
      fallback={
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
          }}
        >
          Carregando diagrama...
        </div>
      }
    >
      <DiagramComponent />
    </Suspense>
  );
}
