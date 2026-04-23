'use client';

import { useEffect, useRef } from 'react';
import { useDistrictStore } from '@/stores/districtStore';
import { useMapStore } from '@/stores/mapStore';
import { useChatStore } from '@/stores/chatStore';

/**
 * Sync map selection → chat panel.
 *
 * Before 2026-04-23: Selecting a district from the map would auto-fire
 *   `{name} 상권 요약해줘` into `/api/chat`, consuming the full PAE pipeline
 *   (6~8 Tool calls + 5+ Card streams) on every click. That was wasteful
 *   for pure exploratory clicks.
 *
 * After 2026-04-23 (Plan: landing-onboarding-feedback §4,7):
 *   Map click → fetch zero-LLM preview (`/api/districts/{code}/preview`) and
 *   render it in the chat panel with suggested-question chips. The user then
 *   decides whether to trigger the full pipeline by clicking chips or "AI
 *   분석 보기".
 */
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

    if (prevSelectedRef.current === selected.code) return;
    prevSelectedRef.current = selected.code;

    // Center map when selection originates from a map click
    if (selectSource === 'map' && selected.center) {
      setView(selected.center, 5);
    }

    // Auto-preview only for map-origin clicks (chat-origin already handled)
    if (selectSource !== 'map') return;
    if (!selected.center || (!selected.center.lat && !selected.center.lng)) return;

    // Zero-LLM preview — no automatic chat message.
    const store = useChatStore.getState();
    store.setPreview(selected.code);

    // 모바일 레이아웃에서는 폴리곤 클릭 시 sheet 를 peek 로 올려 프리뷰 노출.
    // snap 이 이미 hidden 보다 위라면 유지 (사용자가 이미 half/full 로 올린 상태).
    if (store.sheetSnap === 'hidden') {
      store.setSheetSnap('peek');
    }
  }, [selected, selectSource, setView]);
}
