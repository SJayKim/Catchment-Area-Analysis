'use client';

import { useDistrictStore } from '@/stores/districtStore';

export default function StatusBar() {
  const selected = useDistrictStore((s) => s.selected);

  return (
    <div data-testid="statusbar" className="h-8 bg-gray-50 border-t border-gray-200 flex items-center px-4 text-xs text-gray-500 flex-shrink-0">
      <span>데이터 기준: 2025년 4분기</span>
      <span className="mx-2">|</span>
      {selected ? (
        <span>
          선택:{' '}
          <span className="text-gray-700 font-medium">{selected.name}</span>{' '}
          <span className="text-gray-400">{selected.type}</span>
        </span>
      ) : (
        <span>지도에서 상권을 선택하세요</span>
      )}
    </div>
  );
}
