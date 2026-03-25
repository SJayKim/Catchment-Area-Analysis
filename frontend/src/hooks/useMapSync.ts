'use client';

import { useEffect, useRef } from 'react';
import { useDistrictStore } from '@/stores/districtStore';
import { useMapStore } from '@/stores/mapStore';
import { useChat } from './useChat';

export function useMapSync() {
  const selected = useDistrictStore((s) => s.selected);
  const setView = useMapStore((s) => s.setView);
  const { sendMessage } = useChat();
  const prevSelectedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!selected) {
      prevSelectedRef.current = null;
      return;
    }

    // Only trigger auto-query if this is a new selection
    if (prevSelectedRef.current === selected.code) return;
    prevSelectedRef.current = selected.code;

    // Center map on selected district
    if (selected.center) {
      setView(selected.center, 5);
    }

    // Auto-query for district summary
    sendMessage(`${selected.name} 상권 요약해줘`);
  }, [selected, setView, sendMessage]);
}
