import { create } from 'zustand';

interface MapState {
  center: { lat: number; lng: number };
  zoom: number;
  activeLayers: string[];
  setCenter: (center: { lat: number; lng: number }) => void;
  setZoom: (zoom: number) => void;
  toggleLayer: (layer: string) => void;
  setView: (center: { lat: number; lng: number }, zoom: number) => void;
}

export const useMapStore = create<MapState>((set) => ({
  center: { lat: 37.5665, lng: 126.9780 },
  zoom: 11,
  activeLayers: ['polygon'],

  setCenter: (center) => set({ center }),

  setZoom: (zoom) => set({ zoom }),

  toggleLayer: (layer) =>
    set((state) => ({
      activeLayers: state.activeLayers.includes(layer)
        ? state.activeLayers.filter((l) => l !== layer)
        : [...state.activeLayers, layer],
    })),

  setView: (center, zoom) => set({ center, zoom }),
}));
