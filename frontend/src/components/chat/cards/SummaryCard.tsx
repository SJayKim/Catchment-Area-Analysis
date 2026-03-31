'use client';

import { SummaryCardData } from '@/lib/types';
import InlineChart from './InlineChart';

interface SummaryCardProps {
  data: SummaryCardData | Record<string, unknown>;
}

const STATUS_CONFIG = {
  growing: { label: '성장', bg: 'rgba(16,185,129,0.15)', color: '#10b981' },
  stable: { label: '안정', bg: 'rgba(59,130,246,0.15)', color: '#3b82f6' },
  declining: { label: '침체', bg: 'rgba(239,68,68,0.15)', color: '#ef4444' },
};

export default function SummaryCard({ data }: SummaryCardProps) {
  const card = data as SummaryCardData;

  if (!card.districtName) {
    return (
      <div
        className="rounded-xl p-4"
        style={{ backgroundColor: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}
      >
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>데이터를 표시할 수 없습니다.</p>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[card.status] || STATUS_CONFIG.stable;

  const chartData = card.floatingPopulation?.byHour?.map((item) => ({
    hour: `${item.hour}시`,
    pop: item.pop,
  })) || [];

  return (
    <div
      className="rounded-xl shadow-sm overflow-hidden"
      style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-primary-500 to-primary-600 px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-white font-semibold text-sm">{card.districtName}</h3>
            <p className="text-primary-100 text-xs">{card.districtType}</p>
          </div>
          <span
            className="text-xs font-medium px-2 py-0.5 rounded-full"
            style={{ backgroundColor: statusConfig.bg, color: statusConfig.color }}
          >
            {statusConfig.label}
          </span>
        </div>
      </div>

      {/* Summary */}
      <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
        <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>{card.summary}</p>
      </div>

      {/* Floating Population */}
      {card.floatingPopulation && (
        <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
              유동인구
            </h4>
            <div className="text-right">
              <span className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                일 평균 {card.floatingPopulation.dailyAvg.toLocaleString()}명
              </span>
              <span className="text-xs ml-1" style={{ color: 'var(--text-muted)' }}>
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
        <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <h4 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-secondary)' }}>
            주요 업종 Top 5
          </h4>
          <div className="space-y-1.5">
            {card.topCategories.slice(0, 5).map((cat, index) => (
              <div key={index} className="flex items-center justify-between">
                <span className="text-sm" style={{ color: 'var(--text-primary)' }}>
                  <span style={{ color: 'var(--text-muted)' }} className="mr-1.5">{index + 1}.</span>
                  {cat.name}
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded"
                  style={{ color: 'var(--text-secondary)', backgroundColor: 'var(--bg-tertiary)' }}
                >
                  {cat.count}개
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Close Rate */}
      {card.closeRate && (
        <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <h4 className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: 'var(--text-secondary)' }}>
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
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              서울 평균 {card.closeRate.average.toFixed(1)}%
              {card.closeRate.current > card.closeRate.average
                ? ' 대비 높음'
                : ' 대비 낮음'}
            </span>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2" style={{ backgroundColor: 'var(--bg-tertiary)' }}>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          데이터 기준: {card.dataQuarter || '2025년 4분기'}
        </p>
      </div>
    </div>
  );
}
