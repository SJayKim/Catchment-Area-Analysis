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
  if (values.every((v) => v === best)) return <span className="text-xs" style={{ color: 'var(--text-muted)' }}>-</span>;
  return <span className="text-xs font-medium" style={{ color: '#10b981' }}>#{idx + 1} ▲</span>;
}

export default function CompareCard({ data }: CompareCardProps) {
  const card = data as CompareCardData;

  if (!card.districts || !card.district_codes) {
    return (
      <div
        className="rounded-xl p-4"
        style={{ backgroundColor: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}
      >
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>비교 데이터를 표시할 수 없습니다.</p>
      </div>
    );
  }

  const codes = card.district_codes;
  const districts = codes.map((c) => card.districts[c]).filter(Boolean);
  const names = codes.map((c) =>
    card.districtNames?.[c] || card.districts[c]?.district_name || c
  );

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
    <div
      className="rounded-xl shadow-sm overflow-hidden"
      style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}
    >
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
            <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
              <th className="text-left px-4 py-2 text-xs font-medium" style={{ color: 'var(--text-secondary)' }}></th>
              {names.map((name, i) => (
                <th key={i} className="text-center px-3 py-2 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {name}
                </th>
              ))}
              <th className="text-center px-3 py-2 text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>판정</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric, idx) => (
              <tr key={idx} style={idx % 2 === 0 ? { backgroundColor: 'var(--bg-tertiary)' } : {}}>
                <td className="px-4 py-2 text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{metric.label}</td>
                {metric.values.map((val, i) => (
                  <td key={i} className="text-center px-3 py-2 text-sm" style={{ color: 'var(--text-primary)' }}>
                    {metric.format(val as never)}
                  </td>
                ))}
                <td className="text-center px-3 py-2">
                  {metric.isText ? (
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>-</span>
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
        <div className="px-4 py-3" style={{ borderTop: '1px solid var(--border-color)' }}>
          <h4 className="text-xs font-semibold mb-1" style={{ color: 'var(--text-secondary)' }}>💬 AI 종합 의견</h4>
          <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>{card.aiSummary}</p>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2" style={{ backgroundColor: 'var(--bg-tertiary)', borderTop: '1px solid var(--border-color)' }}>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          데이터 기준: {districts[0]?.quarter || '최신 분기'}
        </p>
      </div>
    </div>
  );
}
