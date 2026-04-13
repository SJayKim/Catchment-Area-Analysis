'use client';

import { RecommendCardData } from '@/lib/types';
import SourcesCitation from './SourcesCitation';

interface RecommendCardProps {
  data: RecommendCardData | Record<string, unknown>;
}

function formatWon(value: number): string {
  if (value >= 10000) return `${(value / 10000).toFixed(0)}만원`;
  return `${value.toLocaleString()}원`;
}

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 80 ? 'bg-green-500' : score >= 60 ? 'bg-blue-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--border-color)' }}>
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-bold w-10 text-right" style={{ color: 'var(--text-primary)' }}>{score.toFixed(0)}</span>
    </div>
  );
}

export default function RecommendCard({ data }: RecommendCardProps) {
  const card = data as RecommendCardData;

  if (!card.recommendations || card.recommendations.length === 0) {
    return (
      <div
        className="rounded-xl p-4"
        style={{ backgroundColor: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}
      >
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>추천 데이터를 표시할 수 없습니다.</p>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl shadow-sm overflow-hidden"
      style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-3">
        <h3 className="text-white font-semibold text-sm">
          {card.districtName || '상권'} 업종 추천 Top {card.recommendations.length}
        </h3>
      </div>

      {/* Message */}
      {card.message && (
        <div
          className="px-4 py-2"
          style={{ backgroundColor: 'rgba(245,158,11,0.1)', borderBottom: '1px solid rgba(245,158,11,0.2)' }}
        >
          <p className="text-xs" style={{ color: '#fbbf24' }}>{card.message}</p>
        </div>
      )}

      {/* Recommendations */}
      <div style={{ borderColor: 'var(--border-color)' }}>
        {card.recommendations.map((rec, recIdx) => (
          <div
            key={rec.rank}
            className="px-4 py-3"
            style={recIdx < card.recommendations.length - 1 ? { borderBottom: '1px solid var(--border-color)' } : {}}
          >
            <div className="flex items-start justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold" style={{ color: 'var(--text-muted)' }}>{rec.rank}.</span>
                <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{rec.category_name}</span>
              </div>
              <div className="w-24">
                <ScoreBar score={rec.score} />
              </div>
            </div>
            <div className="ml-5 space-y-0.5">
              {rec.reasons.map((reason, i) => (
                <p key={i} className="text-xs flex items-start gap-1" style={{ color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-muted)' }} className="mt-0.5">├</span>
                  {reason}
                </p>
              ))}
              {rec.startup_cost && (
                <p className="text-xs flex items-start gap-1" style={{ color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-muted)' }} className="mt-0.5">└</span>
                  평균 창업비용 {formatWon(rec.startup_cost * 10000)}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <SourcesCitation
        sources={card.dataSources}
        quarter={`${card.quarter} · 분석 업종 ${card.total_categories_analyzed}개`}
        extraFooterText="추정치이며 실제 결과와 다를 수 있습니다"
      />
    </div>
  );
}
