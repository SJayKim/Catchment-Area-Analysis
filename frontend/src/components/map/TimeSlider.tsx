'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useMapStore } from '@/stores/mapStore';

const TIME_LABELS: Record<number, string> = {
  0: '0시',
  3: '3시',
  6: '6시',
  9: '9시',
  12: '12시',
  15: '15시',
  18: '18시',
  21: '21시',
};

export default function TimeSlider() {
  const {
    heatmapEnabled,
    heatmapTimeSlot,
    heatmapPlaying,
    setHeatmapTimeSlot,
    setHeatmapPlaying,
  } = useMapStore();

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const rafRef = useRef<number | null>(null);

  // Play/pause animation
  useEffect(() => {
    if (heatmapPlaying) {
      intervalRef.current = setInterval(() => {
        setHeatmapTimeSlot((useMapStore.getState().heatmapTimeSlot + 1) % 24);
      }, 1000);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [heatmapPlaying, setHeatmapTimeSlot]);

  // C.3 — rAF throttle. 마우스 드래그/키보드 ArrowLeft·Right 가
  // onChange 를 매 frame 발행해 HeatmapLayer useEffect([heatmapTimeSlot])
  // 가 즉시 재실행되던 비용 제거.
  useEffect(() => {
    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, []);

  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const v = Number(e.target.value);
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        setHeatmapTimeSlot(v);
      });
    },
    [setHeatmapTimeSlot]
  );

  const togglePlay = useCallback(() => {
    setHeatmapPlaying(!heatmapPlaying);
  }, [heatmapPlaying, setHeatmapPlaying]);

  if (!heatmapEnabled) return null;

  return (
    <div
      className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-2.5 rounded-xl shadow-lg"
      style={{
        zIndex: 15,
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        backdropFilter: 'blur(8px)',
        border: '1px solid rgba(255,255,255,0.1)',
        minWidth: '360px',
      }}
    >
      {/* Play/Pause */}
      <button
        onClick={togglePlay}
        className="w-8 h-8 flex items-center justify-center rounded-full transition-colors hover:bg-white/10"
        title={heatmapPlaying ? '일시정지' : '재생'}
      >
        {heatmapPlaying ? (
          <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="4" width="4" height="16" />
            <rect x="14" y="4" width="4" height="16" />
          </svg>
        ) : (
          <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
            <polygon points="5,3 19,12 5,21" />
          </svg>
        )}
      </button>

      {/* Time display */}
      <span className="text-white font-mono text-sm w-10 text-center">
        {String(heatmapTimeSlot).padStart(2, '0')}시
      </span>

      {/* Slider */}
      <div className="flex-1 relative">
        <input
          type="range"
          min={0}
          max={23}
          step={1}
          value={heatmapTimeSlot}
          onChange={handleSliderChange}
          className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
          style={{
            background: `linear-gradient(to right, #3b82f6 ${(heatmapTimeSlot / 23) * 100}%, rgba(255,255,255,0.2) ${(heatmapTimeSlot / 23) * 100}%)`,
          }}
        />
        {/* Tick labels */}
        <div className="flex justify-between mt-1 px-0.5">
          {Object.entries(TIME_LABELS).map(([hour, label]) => (
            <span
              key={hour}
              className="text-[10px]"
              style={{ color: 'rgba(255,255,255,0.4)' }}
            >
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
