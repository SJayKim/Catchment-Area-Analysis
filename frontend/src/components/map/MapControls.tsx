'use client';

import { useMapStore } from '@/stores/mapStore';

interface MapControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
}

export default function MapControls({ onZoomIn, onZoomOut }: MapControlsProps) {
  const { activeLayers, toggleLayer } = useMapStore();
  const isPolygonActive = activeLayers.includes('polygon');

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
    </div>
  );
}
