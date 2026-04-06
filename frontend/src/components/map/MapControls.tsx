'use client';

import { useMapStore } from '@/stores/mapStore';

interface MapControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
}

export default function MapControls({ onZoomIn, onZoomOut }: MapControlsProps) {
  const { activeLayers, toggleLayer, heatmapEnabled, setHeatmapEnabled, setHeatmapPlaying } = useMapStore();
  const isPolygonActive = activeLayers.includes('polygon');

  const toggleHeatmap = () => {
    if (heatmapEnabled) {
      setHeatmapPlaying(false);
    }
    setHeatmapEnabled(!heatmapEnabled);
  };

  return (
    <div className="absolute top-4 right-4 flex flex-col gap-2 z-10">
      {/* Zoom Controls */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <button
          onClick={onZoomIn}
          className="block w-9 h-9 flex items-center justify-center text-gray-600 hover:bg-gray-100 transition-colors"
          title="확대"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
        <div className="h-px bg-gray-200" />
        <button
          onClick={onZoomOut}
          className="block w-9 h-9 flex items-center justify-center text-gray-600 hover:bg-gray-100 transition-colors"
          title="축소"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
          </svg>
        </button>
      </div>

      {/* Layer Toggle */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <button
          onClick={() => toggleLayer('polygon')}
          className={`w-9 h-9 flex items-center justify-center transition-colors ${
            isPolygonActive
              ? 'text-primary-600 bg-primary-50'
              : 'text-gray-400 hover:bg-gray-100'
          }`}
          title="상권 영역 표시"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"
            />
          </svg>
        </button>
      </div>

      {/* Heatmap Toggle */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <button
          onClick={toggleHeatmap}
          className={`w-9 h-9 flex items-center justify-center transition-colors ${
            heatmapEnabled
              ? 'text-orange-600 bg-orange-50'
              : 'text-gray-400 hover:bg-gray-100'
          }`}
          title="유동인구 히트맵"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
