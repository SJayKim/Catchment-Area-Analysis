'use client';

import { ReactNode, useCallback, useEffect, useRef, useState } from 'react';
import { useChatStore, type SheetSnap } from '@/stores/chatStore';
import BottomSheetHandle from './BottomSheetHandle';

const SNAP_VH: Record<SheetSnap, number> = {
  hidden: 4,
  peek: 15,
  half: 55,
  full: 90,
};

const SNAP_ORDER: SheetSnap[] = ['hidden', 'peek', 'half', 'full'];

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function haptic() {
  if (typeof navigator === 'undefined') return;
  if (prefersReducedMotion()) return;
  try {
    navigator.vibrate?.(10);
  } catch {
    /* iOS / unsupported — silent */
  }
}

interface Props {
  children: ReactNode;
  ariaLabel?: string;
}

export default function BottomSheet({
  children,
  ariaLabel = '상권 정보 시트',
}: Props) {
  const snap = useChatStore((s) => s.sheetSnap);
  const setSnap = useChatStore((s) => s.setSheetSnap);
  const [dragDelta, setDragDelta] = useState(0);
  const prevSnap = useRef<SheetSnap>(snap);
  const sheetRef = useRef<HTMLDivElement>(null);

  // snap 변경 시 haptic (prev != current 일 때만)
  useEffect(() => {
    if (prevSnap.current !== snap) {
      haptic();
      prevSnap.current = snap;
    }
  }, [snap]);

  const snapIndex = SNAP_ORDER.indexOf(snap);
  const baseVh = SNAP_VH[snap];

  // drag delta 적용된 실시간 높이 (상단으로 드래그 → vh 증가)
  const dragVh =
    typeof window !== 'undefined' && window.innerHeight > 0
      ? (-dragDelta / window.innerHeight) * 100
      : 0;
  const liveVh = Math.max(4, Math.min(95, baseVh + dragVh));

  const onDragDelta = useCallback((delta: number) => {
    setDragDelta(delta);
  }, []);

  const onDragEnd = useCallback(() => {
    // 가장 가까운 snap 으로 정착
    const target = liveVh;
    let closest: SheetSnap = 'hidden';
    let minDist = Infinity;
    for (const s of SNAP_ORDER) {
      const d = Math.abs(SNAP_VH[s] - target);
      if (d < minDist) {
        minDist = d;
        closest = s;
      }
    }
    // 빠른 swipe-down 감지: 드래그 마지막 delta 가 +50px 이상이면 한 단계 아래
    if (dragDelta > 80 && snapIndex > 0) {
      closest = SNAP_ORDER[snapIndex - 1];
    } else if (dragDelta < -80 && snapIndex < SNAP_ORDER.length - 1) {
      closest = SNAP_ORDER[snapIndex + 1];
    }
    setSnap(closest);
    setDragDelta(0);
  }, [liveVh, dragDelta, snapIndex, setSnap]);

  const reduced = prefersReducedMotion();
  const transition =
    dragDelta !== 0 || reduced
      ? 'none'
      : 'height 220ms cubic-bezier(0.32, 0.72, 0, 1)';

  return (
    <div
      ref={sheetRef}
      role="dialog"
      aria-modal="false"
      aria-label={ariaLabel}
      className="fixed left-0 right-0 bottom-0 z-30 flex flex-col"
      style={{
        height: `${liveVh}vh`,
        transition,
        backgroundColor: 'var(--bg-primary)',
        borderTop: '1px solid var(--border-color)',
        borderTopLeftRadius: 16,
        borderTopRightRadius: 16,
        boxShadow: '0 -4px 16px rgba(0,0,0,0.08)',
        touchAction: 'pan-y',
      }}
    >
      <BottomSheetHandle onDragDelta={onDragDelta} onDragEnd={onDragEnd} />
      <div
        className="flex-1 overflow-y-auto thin-scrollbar"
        style={{
          touchAction: 'pan-y',
          // BottomNav 높이(56) + safe-area. nav 가 sheet content 를 가리지 않도록.
          paddingBottom: 'calc(56px + env(safe-area-inset-bottom))',
        }}
      >
        {children}
      </div>
    </div>
  );
}
