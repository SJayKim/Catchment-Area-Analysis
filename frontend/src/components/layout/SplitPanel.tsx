'use client';

import { useState, useCallback, useRef, useEffect, ReactNode } from 'react';
import { useBreakpoint } from '@/hooks/useBreakpoint';

interface SplitPanelProps {
  left: ReactNode;
  right: ReactNode;
}

export default function SplitPanel({ left, right }: SplitPanelProps) {
  const bp = useBreakpoint();
  const [leftRatio, setLeftRatio] = useState(60);
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);

  const dragEnabled = bp === 'desktop';
  const effectiveLeftRatio = bp === 'tablet' ? 50 : leftRatio;

  const handleMouseDown = useCallback(() => {
    if (!dragEnabled) return;
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [dragEnabled]);

  useEffect(() => {
    if (!dragEnabled) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      if (rafRef.current !== null) return;
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        if (!isDragging.current || !containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const ratio = (x / rect.width) * 100;
        setLeftRatio(Math.min(Math.max(ratio, 30), 80));
      });
    };

    const handleMouseUp = () => {
      isDragging.current = false;
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [dragEnabled]);

  return (
    <div
      ref={containerRef}
      className="flex flex-1 overflow-hidden"
      data-breakpoint={bp}
    >
      {/* Left Panel (Map) */}
      <div
        className="relative overflow-hidden"
        style={{ width: `${effectiveLeftRatio}%` }}
      >
        {left}
      </div>

      {/* Drag Handle — desktop 전용. tablet 은 고정선, 시각적 구분만 유지. */}
      <div
        className={
          dragEnabled
            ? 'w-1 bg-gray-200 hover:bg-primary-400 cursor-col-resize flex-shrink-0 transition-colors'
            : 'w-px bg-gray-200 flex-shrink-0'
        }
        onMouseDown={handleMouseDown}
        aria-hidden={!dragEnabled}
      />

      {/* Right Panel (Chat) */}
      <div
        className="relative overflow-hidden"
        style={{ width: `${100 - effectiveLeftRatio}%` }}
      >
        {right}
      </div>
    </div>
  );
}
