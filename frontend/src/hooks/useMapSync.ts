'use client';

import { useEffect, useRef } from 'react';
import { useDistrictStore } from '@/stores/districtStore';
import { useMapStore } from '@/stores/mapStore';
import { useChatStore } from '@/stores/chatStore';

export function useMapSync() {
  const selected = useDistrictStore((s) => s.selected);
  const selectSource = useDistrictStore((s) => s.selectSource);
  const setView = useMapStore((s) => s.setView);
  const prevSelectedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!selected) {
      prevSelectedRef.current = null;
      return;
    }

    // Only trigger auto-query if this is a new selection
    if (prevSelectedRef.current === selected.code) return;
    prevSelectedRef.current = selected.code;

    // Center map on selected district (for map clicks)
    if (selectSource === 'map' && selected.center) {
      setView(selected.center, 5);
    }

    // Only auto-query when selection came from map click, not from chat
    if (selectSource === 'chat') return;

    // Guard: need center coordinates
    if (!selected.center || (!selected.center.lat && !selected.center.lng)) return;

    // Auto-query for district summary using store directly (no dual-instance issue)
    useChatStore.getState().sendMessage(
      `${selected.name} 상권 요약해줘`,
      selected.code
    );
  }, [selected, selectSource, setView]);
}
