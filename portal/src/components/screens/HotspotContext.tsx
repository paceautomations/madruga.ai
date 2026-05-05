/**
 * HotspotContext — wires ScreenNode/Hotspot to the canvas-level state.
 *
 * ScreenFlowCanvas owns the toggle state (FR-025) and the activation
 * handler (FR-026); ScreenNode renders hotspots and forwards them. We
 * use React Context to avoid prop drilling across the xyflow boundary
 * (ScreenNode is rendered by xyflow itself, not by us, so we cannot
 * pass props to it directly outside `data`).
 */
import { createContext, useContext } from 'react';
import type { Flow } from '../../lib/screen-flow';

export interface HotspotContextValue {
  visible: boolean;
  onActivate: (flow: Flow) => void;
}

const NOOP_VALUE: HotspotContextValue = {
  visible: true,
  onActivate: () => {
    /* no-op */
  },
};

export const HotspotContext = createContext<HotspotContextValue>(NOOP_VALUE);

export function useHotspotContext(): HotspotContextValue {
  return useContext(HotspotContext);
}
