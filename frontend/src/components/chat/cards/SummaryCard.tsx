'use client';

import { SummaryCardData } from '@/lib/types';
import InlineChart from './InlineChart';

interface SummaryCardProps {
  data: SummaryCardData | Record<string, unknown>;
}

const STATUS_CONFIG = {
  growing: { label: '성장', color: 'bg-green-100 text-green-700' },
  stable: { label: '안정', color: 'bg-blue-100 text-blue-700' },
  declining: { label: '침체', color: 'bg-red-100 text-red-700' },
};

export default function SummaryCard({ data }: SummaryCardProps) {
  const card = data as SummaryCardData;

  if (!card.districtName) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <p className="text-sm text-gray-500">데이터를 표시할 수 없습니다.</p>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[card.status] || STATUS_CONFIG.stable;

  const chartData = card.floatingPopulation?.byHour?.map((item) => ({
    hour: `${item.hour}시`,
    pop: item.pop,
  })) || [];

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-primary-500 to-primary-600 px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-white font-semibold text-sm">{card.districtName}</h3>
            <p className="text-primary-100 text-xs">{card.districtType}</p>
          </div>
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusConfig.color}`}
          >
            {statusConfig.label}
          </span>
        </div>
      </div>

      {/* Summary */}
      <div className="px-4 py-3 border-b border-gray-100">
        <p className="text-sm text-gray-700 leading-relaxed">{card.summary}</p>
      </div>

      {/* Floating Population */}
      {card.floatingPopulation && (
        <div className="px-4 py-3 border-b border-gray-100">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              유동인구
            </h4>
            <div className="text-right">
              <span className="text-sm font-bold text-gray-800">
                일 평균 {card.floatingPopulation.dailyAvg.toLocaleString()}명
              </span>
              <span className="text-xs text-gray-400 ml-1">
                (피크: {card.floatingPopulation.peakHour}시)
              </span>
            </div>
          </div>
          {chartData.length > 0 && (
            <InlineChart
              data={chartData}
              type="bar"
              dataKey="pop"
              xKey="hour"
              color="#60a5fa"
              height={120}
            />
          )}
        </div>
      )}

      {/* Top Categories */}
      {card.topCategories && card.topCategories.length > 0 && (
        <div className="px-4 py-3 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            주요 업종 Top 5
          </h4>
          <div className="space-y-1.5">
            {card.topCategories.slice(0, 5).map((cat, index) => (
              <div key={index} className="flex items-center justify-between">
                <span className="text-sm text-gray-700">
                  <span className="text-gray-400 mr-1.5">{index + 1}.</span>
                  {cat.name}
                </span>
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                  {cat.count}개
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Close Rate */}
      {card.closeRate && (
        <div className="px-4 py-3 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
            폐업률
          </h4>
          <div className="flex items-center gap-3">
            <span
              className={`text-lg font-bold ${
                card.closeRate.current > card.closeRate.average
                  ? 'text-red-500'
                  : 'text-green-500'
              }`}
            >
              {card.closeRate.current.toFixed(1)}%
            </span>
            <span className="text-xs text-gray-400">
              서울 평균 {card.closeRate.average.toFixed(1)}%
              {card.closeRate.current > card.closeRate.average
                ? ' 대비 높음'
                : ' 대비 낮음'}
            </span>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50">
        <p className="text-xs text-gray-400">
          데이터 기준: {card.dataQuarter || '2025년 4분기'}
        </p>
      </div>
    </div>
  );
}
