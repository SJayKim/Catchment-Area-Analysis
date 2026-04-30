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
 *
 * 2026-04-28 hotfix (district-click-race-2026-04-28): the previous prevRef
 * guard skipped setPreview whenever the new click had the same code as the
 * last `selected` — including the case where sendMessage had wiped
 * `chatStore.preview` to null. Result: clicking the *same* district again
 * after running an analysis left the preview slot empty. The new guard
 * keys on the actual rendered preview's district_code, not on a stale ref.
 */
export function useMapSync() {
  const selected = useDistrictStore((s) => s.selected);
  const selectSource = useDistrictStore((s) => s.selectSource);
  const setView = useMapStore((s) => s.setView);
  // Tracks the (code, source) pair of the most recent click we acted on.
  // Used purely to deduplicate identical re-renders triggered by Zustand
  // returning a new selected reference on every set call.
  const lastHandledRef = useRef<{ code: string; source: string | null } | null>(null);

  useEffect(() => {
    if (!selected) {
      lastHandledRef.current = null;
      // B.1 — deselect (재클릭) 시 PreviewCard 잔존 방지.
      // SSE 진행 중에는 chatStore.sendMessage 가 이미 preview 를 null 로 wipe 한
      // 상태이므로 no-op. map-origin deselect 시에만 의미 있음.
      const store = useChatStore.getState();
      if (store.preview || store.previewError) {
        store.clearPreview();
      }
      return;
    }

    // Center map when selection originates from a map click. Center is
    // independent of preview — always run for map-origin selections.
    if (selectSource === 'map' && selected.center) {
      setView(selected.center, 5);
    }

    // Auto-preview only for map-origin clicks (chat-origin already handled
    // via the SSE map_cmd path that drives selectDistrict(_, 'chat')).
    if (selectSource !== 'map') {
      lastHandledRef.current = { code: selected.code, source: selectSource };
      return;
    }
    if (!selected.center || (!selected.center.lat && !selected.center.lng)) return;

    const store = useChatStore.getState();
    const currentPreviewCode = store.preview?.district_code;

    // Skip setPreview only when:
    //   (1) we already handled this exact (code, source) pair last time, AND
    //   (2) the rendered preview still matches this code (i.e. it was not
    //       wiped by sendMessage).
    // Otherwise — re-fire setPreview so the slot recovers.
    const sameAsLast =
      lastHandledRef.current?.code === selected.code &&
      lastHandledRef.current?.source === selectSource;
    const previewStillFresh = currentPreviewCode === selected.code;
    if (sameAsLast && previewStillFresh) return;

    lastHandledRef.current = { code: selected.code, source: selectSource };

    // Zero-LLM preview — no automatic chat message.
    store.setPreview(selected.code);

    // 모바일 레이아웃에서는 폴리곤 클릭 시 sheet 를 peek 로 올려 프리뷰 노출.
    // snap 이 이미 hidden 보다 위라면 유지 (사용자가 이미 half/full 로 올린 상태).
    if (store.sheetSnap === 'hidden') {
      store.setSheetSnap('peek');
    }
  }, [selected, selectSource, setView]);
}
