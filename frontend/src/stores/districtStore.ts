import { create } from 'zustand';
import { District } from '@/lib/types';

export type SelectSource = 'map' | 'chat' | null;

interface DistrictState {
  selected: District | null;
  selectSource: SelectSource;
  isCompareMode: boolean;
  compareList: District[];
  hoveredCode: string | null;
  select: (district: District, source?: SelectSource) => void;
  deselect: () => void;
  setHovered: (code: string | null) => void;
  toggleCompareMode: () => void;
  addToCompare: (district: District) => void;
  removeFromCompare: (code: string) => void;
  clearCompare: () => void;
}

export const useDistrictStore = create<DistrictState>((set) => ({
  selected: null,
  selectSource: null,
  isCompareMode: false,
  compareList: [],
  hoveredCode: null,

  select: (district, source = null) =>
    set({ selected: district, selectSource: source }),

  deselect: () => set({ selected: null, selectSource: null }),

  setHovered: (code) => set({ hoveredCode: code }),

  toggleCompareMode: () =>
    set((state) => ({
      isCompareMode: !state.isCompareMode,
      compareList: state.isCompareMode ? [] : state.compareList,
    })),

  addToCompare: (district) =>
    set((state) => {
      if (state.compareList.length >= 3) return state;
      if (state.compareList.some((d) => d.code === district.code)) return state;
      return { compareList: [...state.compareList, district] };
    }),

  removeFromCompare: (code) =>
    set((state) => ({
      compareList: state.compareList.filter((d) => d.code !== code),
    })),

  clearCompare: () => set({ compareList: [], isCompareMode: false }),
}));
