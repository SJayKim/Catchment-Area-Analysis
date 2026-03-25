import { create } from 'zustand';
import { District } from '@/lib/types';

interface DistrictState {
  selected: District | null;
  isCompareMode: boolean;
  compareList: District[];
  hoveredCode: string | null;
  select: (district: District) => void;
  deselect: () => void;
  setHovered: (code: string | null) => void;
  toggleCompareMode: () => void;
  addToCompare: (district: District) => void;
  removeFromCompare: (code: string) => void;
  clearCompare: () => void;
}

export const useDistrictStore = create<DistrictState>((set) => ({
  selected: null,
  isCompareMode: false,
  compareList: [],
  hoveredCode: null,

  select: (district) => set({ selected: district }),

  deselect: () => set({ selected: null }),

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
