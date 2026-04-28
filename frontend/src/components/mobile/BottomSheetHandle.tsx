'use client';

import { useCallback } from 'react';
import { useChatStore, type SheetSnap } from '@/stores/chatStore';

const SNAP_ORDER: SheetSnap[] = ['hidden', 'peek', 'half', 'full'];

interface Props {
  onDragDelta?: (deltaY: number) => void;
  onDragEnd?: () => void;
}

export default function BottomSheetHandle({ onDragDelta, onDragEnd }: Props) {
  const snap = useChatStore((s) => s.sheetSnap);
  const setSnap = useChatStore((s) => s.setSheetSnap);

  const snapIndex = SNAP_ORDER.indexOf(snap);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>) => {
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        const next = Math.min(snapIndex + 1, SNAP_ORDER.length - 1);
        setSnap(SNAP_ORDER[next]);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = Math.max(snapIndex - 1, 0);
        setSnap(SNAP_ORDER[next]);
      } else if (e.key === 'Home') {
        e.preventDefault();
        setSnap('hidden');
      } else if (e.key === 'End') {
        e.preventDefault();
        setSnap('full');
      }
    },
    [snapIndex, setSnap],
  );

  const onPointerDown = useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      const startY = e.clientY;
      const target = e.currentTarget;
      let moved = false;
      // iOS Safari deadzone — `touch-action:none` + setPointerCapture 조합에서
      // 시트가 탭 직후 커지며 핸들이 손가락 아래로 들어오면 합성 pointerup 이
      // 발사됨. 6px 미만 이동은 탭으로 간주해 onDragEnd 를 호출하지 않음.
      const DEADZONE_PX = 6;
      target.setPointerCapture(e.pointerId);

      const move = (ev: PointerEvent) => {
        const dy = ev.clientY - startY;
        if (!moved && Math.abs(dy) > DEADZONE_PX) moved = true;
        if (moved) onDragDelta?.(dy);
      };
      const up = () => {
        target.removeEventListener('pointermove', move);
        target.removeEventListener('pointerup', up);
        target.removeEventListener('pointercancel', up);
        if (moved) onDragEnd?.();
      };
      target.addEventListener('pointermove', move);
      target.addEventListener('pointerup', up);
      target.addEventListener('pointercancel', up);
    },
    [onDragDelta, onDragEnd],
  );

  return (
    <button
      type="button"
      className="flex items-center justify-center w-full py-2 touch-target"
      style={{ touchAction: 'none' }}
      role="slider"
      aria-label="시트 높이 조절"
      aria-valuemin={0}
      aria-valuemax={SNAP_ORDER.length - 1}
      aria-valuenow={snapIndex}
      aria-valuetext={snap}
      onKeyDown={onKeyDown}
      onPointerDown={onPointerDown}
    >
      <span
        className="block rounded-full"
        style={{
          width: 36,
          height: 4,
          backgroundColor: 'var(--border-color)',
        }}
        aria-hidden="true"
      />
    </button>
  );
}
