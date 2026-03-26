'use client';

import { RecommendCardData } from '@/lib/types';

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
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-bold text-gray-700 w-10 text-right">{score.toFixed(0)}</span>
    </div>
  );
}

export default function RecommendCard({ data }: RecommendCardProps) {
  const card = data as RecommendCardData;

  if (!card.recommendations || card.recommendations.length === 0) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <p className="text-sm text-gray-500">추천 데이터를 표시할 수 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-3">
        <h3 className="text-white font-semibold text-sm">
          💡 {card.districtName || '상권'} 업종 추천 Top {card.recommendations.length}
        </h3>
      </div>

      {/* Message */}
      {card.message && (
        <div className="px-4 py-2 bg-amber-50 border-b border-amber-100">
          <p className="text-xs text-amber-700">{card.message}</p>
        </div>
      )}

      {/* Recommendations */}
      <div className="divide-y divide-gray-100">
        {card.recommendations.map((rec) => (
          <div key={rec.rank} className="px-4 py-3">
            <div className="flex items-start justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-gray-400">{rec.rank}.</span>
                <span className="text-sm font-semibold text-gray-800">{rec.category_name}</span>
              </div>
              <div className="w-24">
                <ScoreBar score={rec.score} />
              </div>
            </div>
            <div className="ml-5 space-y-0.5">
              {rec.reasons.map((reason, i) => (
                <p key={i} className="text-xs text-gray-500 flex items-start gap-1">
                  <span className="text-gray-300 mt-0.5">├</span>
                  {reason}
                </p>
              ))}
              {rec.startup_cost && (
                <p className="text-xs text-gray-500 flex items-start gap-1">
                  <span className="text-gray-300 mt-0.5">└</span>
                  평균 창업비용 {formatWon(rec.startup_cost * 10000)}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 border-t border-gray-100">
        <p className="text-xs text-gray-400">
          데이터 기준: {card.quarter} · 분석 업종 {card.total_categories_analyzed}개
        </p>
        <p className="text-xs text-gray-400 mt-0.5">
          ⚠ 추정치이며 실제 결과와 다를 수 있습니다
        </p>
      </div>
    </div>
  );
}
