'use client';

import { RiskCardData } from '@/lib/types';
import InlineChart from './InlineChart';

interface RiskCardProps {
  data: RiskCardData | Record<string, unknown>;
}

const GRADE_STYLES: Record<string, string> = {
  '매우 안정': 'text-green-600 bg-green-50',
  '양호': 'text-blue-600 bg-blue-50',
  '주의': 'text-yellow-600 bg-yellow-50',
  '위험': 'text-red-600 bg-red-50',
  '데이터 부족': 'text-gray-500 bg-gray-50',
};

function StabilityGauge({ score, grade }: { score: number | null; grade: string }) {
  if (score === null) {
    return (
      <div className="text-center py-2">
        <p className="text-sm text-gray-500">{grade}</p>
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

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-700">상권 안정성</span>
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-gray-800">{score}점</span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${GRADE_STYLES[grade] || GRADE_STYLES['양호']}`}>
            {grade}
          </span>
        </div>
      </div>
      <div className="h-2.5 bg-gray-200 rounded-full overflow-hidden">
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
      <span className="text-xs text-gray-600 w-20 truncate" title={category}>{category}</span>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${isLow ? 'bg-red-400' : 'bg-blue-400'}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className={`text-xs font-medium w-16 text-right ${isLow ? 'text-red-500' : 'text-gray-600'}`}>
        {avgMonths.toFixed(1)}개월 {isLow ? '⚠' : ''}
      </span>
    </div>
  );
}

export default function RiskCard({ data }: RiskCardProps) {
  const card = data as RiskCardData;

  if (!card.stability) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <p className="text-sm text-gray-500">리스크 데이터를 표시할 수 없습니다.</p>
      </div>
    );
  }

  const maxSurvival = card.survival_by_category?.length
    ? Math.max(...card.survival_by_category.map((s) => s.avg_months))
    : 1;

  const trendChartData = card.quarterly_trend?.map((q) => ({
    quarter: q.quarter,
    open: q.open,
    close: q.close,
  })) || [];

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-red-500 to-rose-500 px-4 py-3">
        <h3 className="text-white font-semibold text-sm">
          ⚠ {card.districtName || '상권'} 리스크 분석
        </h3>
      </div>

      {/* Stability Score */}
      <div className="px-4 py-3 border-b border-gray-100">
        <StabilityGauge score={card.stability.score} grade={card.stability.grade} />
        {card.stability.trend?.detail && (
          <p className="text-xs text-gray-500 mt-1.5">📉 {card.stability.trend.detail}</p>
        )}
        {card.stability.message && (
          <p className="text-xs text-gray-500 mt-1">{card.stability.message}</p>
        )}
      </div>

      {/* Survival by Category */}
      {card.survival_by_category && card.survival_by_category.length > 0 && (
        <div className="px-4 py-3 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            📊 업종별 평균 생존 기간
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
        <div className="px-4 py-3 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            🚨 위험 업종
          </h4>
          <div className="space-y-1">
            {card.risk_categories.map((item, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-sm text-gray-700">• {item.category}</span>
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
        <div className="px-4 py-3 border-b border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            📈 분기별 개폐업 추이
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
      <div className="px-4 py-2 bg-gray-50">
        <p className="text-xs text-gray-400">
          데이터 기준: {card.quarterly_trend?.[card.quarterly_trend.length - 1]?.quarter || '최신 분기'}
          {card.stability.quarters_analyzed > 0 && ` · ${card.stability.quarters_analyzed}분기 분석`}
        </p>
      </div>
    </div>
  );
}
