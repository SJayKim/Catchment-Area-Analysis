'use client';

import { CompareCardData } from '@/lib/types';

interface CompareCardProps {
  data: CompareCardData | Record<string, unknown>;
}

const STATUS_LABEL: Record<string, { label: string; icon: string }> = {
  growing: { label: '성장', icon: '🟢' },
  stable: { label: '안정', icon: '🟡' },
  declining: { label: '침체', icon: '🔴' },
};

function formatSales(value: number): string {
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(0)}만`;
  return value.toLocaleString();
}

function Winner({ values, higherIsBetter = true }: { values: number[]; higherIsBetter?: boolean }) {
  if (values.length < 2) return null;
  const best = higherIsBetter ? Math.max(...values) : Math.min(...values);
  const idx = values.indexOf(best);
  if (values.every((v) => v === best)) return <span className="text-xs text-gray-400">-</span>;
  return <span className="text-xs text-green-600 font-medium">#{idx + 1} ▲</span>;
}

export default function CompareCard({ data }: CompareCardProps) {
  const card = data as CompareCardData;

  if (!card.districts || !card.district_codes) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
        <p className="text-sm text-gray-500">비교 데이터를 표시할 수 없습니다.</p>
      </div>
    );
  }

  const codes = card.district_codes;
  const districts = codes.map((c) => card.districts[c]).filter(Boolean);
  const names = codes.map((c) => card.districtNames?.[c] || c);

  const metrics = [
    {
      label: '유동인구',
      values: districts.map((d) => d.floating_pop),
      format: (v: number) => `${(v / 10000).toFixed(1)}만/일`,
      higherIsBetter: true,
    },
    {
      label: '주 연령대',
      values: districts.map((d) => d.main_age),
      format: (v: string) => v,
      isText: true,
    },
    {
      label: '점포 수',
      values: districts.map((d) => d.store_count),
      format: (v: number) => `${v.toLocaleString()}개`,
      higherIsBetter: true,
    },
    {
      label: '월 매출',
      values: districts.map((d) => d.monthly_sales),
      format: (v: number) => formatSales(v),
      higherIsBetter: true,
    },
    {
      label: '폐업률',
      values: districts.map((d) => d.close_rate),
      format: (v: number) => `${v.toFixed(1)}%`,
      higherIsBetter: false,
    },
    {
      label: '상태',
      values: districts.map((d) => d.status),
      format: (v: string) => {
        const s = STATUS_LABEL[v] || STATUS_LABEL.stable;
        return `${s.icon} ${s.label}`;
      },
      isText: true,
    },
  ];

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-500 to-indigo-600 px-4 py-3">
        <h3 className="text-white font-semibold text-sm">
          📊 상권 비교: {names.join(' vs ')}
        </h3>
      </div>

      {/* Comparison Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left px-4 py-2 text-xs font-medium text-gray-500"></th>
              {names.map((name, i) => (
                <th key={i} className="text-center px-3 py-2 text-xs font-semibold text-gray-700">
                  {name}
                </th>
              ))}
              <th className="text-center px-3 py-2 text-xs font-medium text-gray-500">판정</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric, idx) => (
              <tr key={idx} className={idx % 2 === 0 ? 'bg-gray-50' : ''}>
                <td className="px-4 py-2 text-xs font-medium text-gray-500">{metric.label}</td>
                {metric.values.map((val, i) => (
                  <td key={i} className="text-center px-3 py-2 text-sm text-gray-800">
                    {metric.format(val as never)}
                  </td>
                ))}
                <td className="text-center px-3 py-2">
                  {metric.isText ? (
                    <span className="text-xs text-gray-400">-</span>
                  ) : (
                    <Winner
                      values={metric.values as number[]}
                      higherIsBetter={metric.higherIsBetter}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* AI Summary */}
      {card.aiSummary && (
        <div className="px-4 py-3 border-t border-gray-100">
          <h4 className="text-xs font-semibold text-gray-500 mb-1">💬 AI 종합 의견</h4>
          <p className="text-sm text-gray-700 leading-relaxed">{card.aiSummary}</p>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 border-t border-gray-100">
        <p className="text-xs text-gray-400">
          데이터 기준: {districts[0]?.quarter || '최신 분기'}
        </p>
      </div>
    </div>
  );
}
