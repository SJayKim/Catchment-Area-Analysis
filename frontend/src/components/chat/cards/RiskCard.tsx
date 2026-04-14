'use client';

import { memo, useMemo } from 'react';
import { RiskCardData } from '@/lib/types';
import InlineChart from './InlineChart';
import SourcesCitation from './SourcesCitation';

interface RiskCardProps {
  data: RiskCardData | Record<string, unknown>;
}

const GRADE_STYLES: Record<string, { color: string; bg: string }> = {
  '매우 안정': { color: '#10b981', bg: 'rgba(16,185,129,0.15)' },
  '양호': { color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
  '주의': { color: '#eab308', bg: 'rgba(234,179,8,0.15)' },
  '위험': { color: '#ef4444', bg: 'rgba(239,68,68,0.15)' },
  '데이터 부족': { color: '#94a3b8', bg: 'rgba(148,163,184,0.15)' },
};

function StabilityGauge({ score, grade }: { score: number | null; grade: string }) {
  if (score === null) {
    return (
      <div className="text-center py-2">
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{grade}</p>
      </div>
    );
  }

  const color =
    score >= 80
      ? 'bg-green-500'
      : score >= 60
        ? 'bg-blue-500'
        : score >= 40
          ? 'bg-yellow-500'
          : 'bg-red-500';

  const gradeStyle = GRADE_STYLES[grade] || GRADE_STYLES['양호'];

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>상권 안정성</span>
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{score}점</span>
          <span
            className="text-xs font-medium px-2 py-0.5 rounded-full"
            style={{ backgroundColor: gradeStyle.bg, color: gradeStyle.color }}
          >
            {grade}
          </span>
        </div>
      </div>
      <div className="h-2.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--border-color)' }}>
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

function SurvivalBar({ category, avgMonths, maxMonths }: { category: string; avgMonths: number; maxMonths: number }) {
  const pct = maxMonths > 0 ? (avgMonths / maxMonths) * 100 : 0;
  const isLow = avgMonths < 12;

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs w-20 truncate" style={{ color: 'var(--text-secondary)' }} title={category}>{category}</span>
      <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--bg-tertiary)' }}>
        <div
          className={`h-full rounded-full ${isLow ? 'bg-red-400' : 'bg-blue-400'}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className={`text-xs font-medium w-16 text-right ${isLow ? 'text-red-500' : ''}`} style={isLow ? {} : { color: 'var(--text-secondary)' }}>
        {avgMonths.toFixed(1)}개월
      </span>
    </div>
  );
}

function RiskCard({ data }: RiskCardProps) {
  const card = data as RiskCardData;

  const maxSurvival = useMemo(
    () =>
      card.survival_by_category?.length
        ? Math.max(...card.survival_by_category.map((s) => s.avg_months))
        : 1,
    [card.survival_by_category]
  );

  const trendChartData = useMemo(
    () =>
      card.quarterly_trend?.map((q) => ({
        quarter: q.quarter,
        open: q.open,
        close: q.close,
      })) || [],
    [card.quarterly_trend]
  );

  if (!card.stability) {
    return (
      <div
        className="rounded-xl p-4"
        style={{ backgroundColor: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}
      >
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>리스크 데이터를 표시할 수 없습니다.</p>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl shadow-sm overflow-hidden"
      style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-red-500 to-rose-500 px-4 py-3">
        <h3 className="text-white font-semibold text-sm">
          {card.districtName || '상권'} 리스크 분석
        </h3>
      </div>

      {/* Stability Score */}
      <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
        <StabilityGauge score={card.stability.score} grade={card.stability.grade} />
        {card.stability.trend?.detail && (
          <p className="text-xs mt-1.5" style={{ color: 'var(--text-secondary)' }}>{card.stability.trend.detail}</p>
        )}
        {card.stability.message && (
          <p className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{card.stability.message}</p>
        )}
      </div>

      {/* Survival by Category */}
      {card.survival_by_category && card.survival_by_category.length > 0 && (
        <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <h4 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-secondary)' }}>
            업종별 평균 생존 기간
          </h4>
          <div className="space-y-1.5">
            {card.survival_by_category.slice(0, 8).map((item, i) => (
              <SurvivalBar
                key={i}
                category={item.category}
                avgMonths={item.avg_months}
                maxMonths={maxSurvival}
              />
            ))}
          </div>
        </div>
      )}

      {/* Risk Categories */}
      {card.risk_categories && card.risk_categories.length > 0 && (
        <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <h4 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-secondary)' }}>
            위험 업종
          </h4>
          <div className="space-y-1">
            {card.risk_categories.map((item, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-sm" style={{ color: 'var(--text-primary)' }}>• {item.category}</span>
                <span className="text-xs text-red-500 font-medium">
                  폐업률 {item.close_rate.toFixed(1)}% ({item.warning})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quarterly Trend Chart */}
      {trendChartData.length > 0 && (
        <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <h4 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-secondary)' }}>
            분기별 개폐업 추이
          </h4>
          <InlineChart
            data={trendChartData}
            type="bar"
            dataKey="close"
            xKey="quarter"
            color="#f87171"
            height={120}
          />
        </div>
      )}

      {/* Footer */}
      <SourcesCitation
        sources={card.dataSources}
        quarter={card.quarterly_trend?.[card.quarterly_trend.length - 1]?.quarter || '최신 분기'}
        extraFooterText={card.stability.quarters_analyzed > 0 ? `${card.stability.quarters_analyzed}분기 분석` : undefined}
      />
    </div>
  );
}

export default memo(RiskCard);
