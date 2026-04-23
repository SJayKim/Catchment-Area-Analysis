'use client';

import { useEffect } from 'react';

/**
 * 모바일 키보드 노출 높이를 CSS 변수 `--kb-inset` 로 주입.
 *
 * - Chrome/Edge: VirtualKeyboard API (`overlaysContent=true`) → `env(keyboard-inset-height)` 자동 반영
 * - iOS Safari / 미지원 브라우저: `VisualViewport` resize 이벤트로 fallback 계산
 *
 * IME 조합 중 키보드가 깜빡여도 레이아웃 재계산이 composition 을 방해하지 않도록
 * `compositionstart/end` 동안 resize 업데이트 skip.
 */
export function useKeyboardInset(): void {
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // 1) Chromium VirtualKeyboard API — 지원 시 최우선
    const nav = navigator as Navigator & {
      virtualKeyboard?: { overlaysContent: boolean };
    };
    if (nav.virtualKeyboard) {
      nav.virtualKeyboard.overlaysContent = true;
      // Chrome/Edge 는 env(keyboard-inset-height) 로 CSS 에서 직접 접근 가능.
      // 추가 JS 업데이트 불필요.
    }

    // 2) VisualViewport fallback — iOS Safari, 구 Android WebView
    const vv = window.visualViewport;
    if (!vv) return;

    let composing = false;
    const onCompStart = () => {
      composing = true;
    };
    const onCompEnd = () => {
      composing = false;
    };
    const update = () => {
      if (composing) return;
      const delta = Math.max(0, window.innerHeight - vv.height);
      document.documentElement.style.setProperty('--kb-inset', `${delta}px`);
    };

    update();
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    window.addEventListener('compositionstart', onCompStart);
    window.addEventListener('compositionend', onCompEnd);

    return () => {
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
      window.removeEventListener('compositionstart', onCompStart);
      window.removeEventListener('compositionend', onCompEnd);
    };
  }, []);
}
