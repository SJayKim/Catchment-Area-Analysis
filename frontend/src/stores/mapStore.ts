import { create } from 'zustand';
import type { HeatmapPoint } from '@/lib/api';

interface MapState {
  center: { lat: number; lng: number };
  zoom: number;
  activeLayers: string[];
  // Heatmap state
  heatmapEnabled: boolean;
  heatmapTimeSlot: number;
  heatmapPlaying: boolean;
  heatmapData: Record<string, HeatmapPoint[]> | null;
  heatmapLoading: boolean;

  setCenter: (center: { lat: number; lng: number }) => void;
  setZoom: (zoom: number) => void;
  toggleLayer: (layer: string) => void;
  setView: (center: { lat: number; lng: number }, zoom: number) => void;
  // Heatmap actions
  setHeatmapEnabled: (enabled: boolean) => void;
  setHeatmapTimeSlot: (slot: number) => void;
  setHeatmapPlaying: (playing: boolean) => void;
  setHeatmapData: (data: Record<string, HeatmapPoint[]> | null) => void;
  setHeatmapLoading: (loading: boolean) => void;
}

export const useMapStore = create<MapState>((set) => ({
  center: { lat: 37.5665, lng: 126.9780 },
  zoom: 11,
  activeLayers: ['polygon'],
  heatmapEnabled: false,
  heatmapTimeSlot: 12,
  heatmapPlaying: false,
  heatmapData: null,
  heatmapLoading: false,

  setCenter: (center) => set({ center }),

  setZoom: (zoom) => set({ zoom }),

  toggleLayer: (layer) =>
    set((state) => ({
      activeLayers: state.activeLayers.includes(layer)
        ? state.activeLayers.filter((l) => l !== layer)
        : [...state.activeLayers, layer],
    })),

  setView: (center, zoom) => set({ center, zoom }),

  setHeatmapEnabled: (enabled) => set({ heatmapEnabled: enabled }),
  setHeatmapTimeSlot: (slot) => set({ heatmapTimeSlot: slot }),
  setHeatmapPlaying: (playing) => set({ heatmapPlaying: playing }),
  setHeatmapData: (data) => set({ heatmapData: data }),
  setHeatmapLoading: (loading) => set({ heatmapLoading: loading }),
}));

// Expose for E2E tests (Playwright) — same pattern as chatStore / districtStore.
// Used to drive heatmap toggle and verify TimeSlider throttle without depending
// on the kakao map runtime.
if (typeof window !== 'undefined') {
  (window as unknown as { __mapStore?: typeof useMapStore }).__mapStore =
    useMapStore;
}
