'use client';

import { useState, useCallback, useRef, useEffect, ReactNode } from 'react';

interface SplitPanelProps {
  left: ReactNode;
  right: ReactNode;
}

export default function SplitPanel({ left, right }: SplitPanelProps) {
  const [leftRatio, setLeftRatio] = useState(60);
  const isDragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);

  const handleMouseDown = useCallback(() => {
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      // Skip if a rAF is already pending (cap at 60fps)
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
  }, []);

  return (
    <div ref={containerRef} className="flex flex-1 overflow-hidden">
      {/* Left Panel (Map) */}
      <div
        className="relative overflow-hidden"
        style={{ width: `${leftRatio}%` }}
      >
        {left}
      </div>

      {/* Drag Handle */}
      <div
        className="w-1 bg-gray-200 hover:bg-primary-400 cursor-col-resize flex-shrink-0 transition-colors"
        onMouseDown={handleMouseDown}
      />

      {/* Right Panel (Chat) */}
      <div
        className="relative overflow-hidden"
        style={{ width: `${100 - leftRatio}%` }}
      >
        {right}
      </div>
    </div>
  );
}
