import { ReactLikeC4, LikeC4ModelProvider } from 'likec4:react';

const VIEW_TO_PATH: Record<string, string> = {
  index: '/fulano/landscape/',
  containers: '/fulano/containers/',
  contextMap: '/fulano/context-map/',
  businessFlow: '/fulano/business-flow/',
  channelDetail: '/fulano/bc-channel/',
  conversationDetail: '/fulano/bc-conversation/',
  safetyDetail: '/fulano/bc-safety/',
  operationsDetail: '/fulano/bc-operations/',
};

export default function LikeC4Diagram({ viewId }: { viewId: string }) {
  return (
    <LikeC4ModelProvider>
      <ReactLikeC4
        viewId={viewId}
        style={{ width: '100%', height: '100%' }}
        pannable
        zoomable
        fitView
        keepAspectRatio={false}
        enableElementDetails
        enableRelationshipDetails
        enableNotations
        onNavigateTo={(nextViewId) => {
          const path = VIEW_TO_PATH[nextViewId];
          if (path) {
            window.location.href = path;
          }
        }}
      />
    </LikeC4ModelProvider>
  );
}
