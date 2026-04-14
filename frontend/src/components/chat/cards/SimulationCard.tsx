'use client';

import { memo, useMemo } from 'react';
import { SimulationCardData } from '@/lib/types';
import SourcesCitation from './SourcesCitation';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface SimulationCardProps {
  data: SimulationCardData | Record<string, unknown>;
}

function formatSales(value: number): string {
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억원`;
  if (value >= 10_000) return `${Math.round(value / 10_000)}만원`;
  return `${value.toLocaleString()}원`;
}

const BAR_COLORS = ['#f59e0b', '#3b82f6', '#10b981'];
const BAR_LABELS = ['하위 (p25)', '평균', '상위 (p75)'];

function SimulationCard({ data }: SimulationCardProps) {
  const card = data as SimulationCardData;

  const chartData = useMemo(
    () => [
      { name: '하위', value: card.simulation?.low ?? 0, label: BAR_LABELS[0] },
      { name: '평균', value: card.simulation?.avg ?? 0, label: BAR_LABELS[1] },
      { name: '상위', value: card.simulation?.high ?? 0, label: BAR_LABELS[2] },
    ],
    [card.simulation?.low, card.simulation?.avg, card.simulation?.high]
  );

  if (!card.simulation) {
    return (
      <div
        className="rounded-xl p-4"
        style={{ backgroundColor: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}
      >
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          시뮬레이션 데이터를 표시할 수 없습니다.
        </p>
      </div>
    );
  }

  const { basis, percentiles, seoul_comparison } = card;

  return (
    <div
      className="rounded-xl shadow-sm overflow-hidden"
      style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-500 to-indigo-600 px-4 py-3">
        <h3 className="text-white font-semibold text-sm">
          {card.districtName || '상권'} {card.category_name || '업종'} 매출 시뮬레이션
        </h3>
      </div>

      {/* Chart */}
      <div className="px-4 pt-4 pb-2">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
            <XAxis
              dataKey="name"
              tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
              axisLine={{ stroke: 'var(--border-color)' }}
            />
            <YAxis
              tickFormatter={(v: number) => formatSales(v)}
              tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
              axisLine={{ stroke: 'var(--border-color)' }}
              width={70}
            />
            <Tooltip
              formatter={(value: number) => [formatSales(value), '예상 월매출']}
              contentStyle={{
                backgroundColor: 'var(--bg-tertiary)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                color: 'var(--text-primary)',
              }}
            />
            {seoul_comparison && (
              <ReferenceLine
                y={seoul_comparison.seoul_avg}
                stroke="#ef4444"
                strokeDasharray="5 5"
                label={{
                  value: `서울 평균 ${formatSales(seoul_comparison.seoul_avg)}`,
                  fill: '#ef4444',
                  fontSize: 11,
                  position: 'right',
                }}
              />
            )}
            <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={50}>
              {chartData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={BAR_COLORS[index]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Summary numbers */}
      <div
        className="mx-4 mb-3 rounded-lg p-3 grid grid-cols-3 gap-2 text-center"
        style={{ backgroundColor: 'var(--bg-tertiary)' }}
      >
        {chartData.map((d, i) => (
          <div key={d.name}>
            <p className="text-xs mb-1" style={{ color: BAR_COLORS[i] }}>
              {d.label}
            </p>
            <p className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
              {formatSales(d.value)}
            </p>
          </div>
        ))}
      </div>

      {/* Seoul comparison */}
      {seoul_comparison && (
        <div
          className="mx-4 mb-3 rounded-lg px-3 py-2 flex items-center justify-between"
          style={{
            backgroundColor: seoul_comparison.diff_percent >= 0 ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
            border: `1px solid ${seoul_comparison.diff_percent >= 0 ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
          }}
        >
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            서울 평균 대비
          </span>
          <span
            className="text-sm font-bold"
            style={{ color: seoul_comparison.diff_percent >= 0 ? '#10b981' : '#ef4444' }}
          >
            {seoul_comparison.diff_percent > 0 ? '+' : ''}{seoul_comparison.diff_percent}% ({seoul_comparison.label})
          </span>
        </div>
      )}

      {/* Basis info */}
      <div className="mx-4 mb-3 space-y-1">
        <p className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
          산출 근거
        </p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs" style={{ color: 'var(--text-secondary)' }}>
          <span>현재 점포 수: {basis.store_count}개</span>
          <span>총 월매출: {formatSales(basis.total_monthly_sales)}</span>
          {basis.additional_competitors > 0 && (
            <span className="col-span-2" style={{ color: '#f59e0b' }}>
              + 추가 경쟁점 {basis.additional_competitors}개 반영
            </span>
          )}
          {basis.unit_price && (
            <span className="col-span-2">
              객단가: {basis.unit_price.toLocaleString()}원 (기본 대비 ×{basis.price_ratio})
            </span>
          )}
        </div>
        {!percentiles.reliable && (
          <p className="text-xs" style={{ color: '#f59e0b' }}>
            표본 수 부족 ({percentiles.sample_count}개) — 참고용 범위
          </p>
        )}
      </div>

      {/* Disclaimer */}
      <div
        className="mx-4 mb-3 rounded-lg px-3 py-2"
        style={{ backgroundColor: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.15)' }}
      >
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {card.disclaimer || '본 시뮬레이션은 카드매출 기반 추정치이며, 실제 매출과 다를 수 있습니다.'}
        </p>
      </div>

      {/* Sources */}
      <SourcesCitation
        sources={card.dataSources}
        quarter={card.quarter}
      />
    </div>
  );
}

export default memo(SimulationCard);
