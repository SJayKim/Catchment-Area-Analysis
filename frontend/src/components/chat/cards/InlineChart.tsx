'use client';

import { memo, useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

interface InlineChartProps {
  data: Record<string, unknown>[];
  type?: 'bar' | 'line';
  dataKey: string;
  xKey: string;
  color?: string;
  height?: number;
}

interface ChartTokens {
  grid: string;
  axis: string;
  tooltipBg: string;
  tooltipText: string;
  tooltipBorder: string;
}

// D.7 — Recharts 가 raw 색상 값을 요구하므로 CSS 변수를 컴포넌트 mount 시점에
// `getComputedStyle` 로 1회 resolve 후 useState 캐싱. 라이트/다크 팔레트 모두
// globals.css 에 정의되어 있어 자동 추종.
const FALLBACK_TOKENS: ChartTokens = {
  grid: '#334155',
  axis: '#94a3b8',
  tooltipBg: '#1e293b',
  tooltipText: '#f8fafc',
  tooltipBorder: '#334155',
};

function readToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return v || fallback;
}

function InlineChart({
  data,
  type = 'bar',
  dataKey,
  xKey,
  color = '#3b82f6',
  height = 150,
}: InlineChartProps) {
  const [tokens, setTokens] = useState<ChartTokens>(FALLBACK_TOKENS);

  useEffect(() => {
    setTokens({
      grid: readToken('--chart-grid', FALLBACK_TOKENS.grid),
      axis: readToken('--chart-axis', FALLBACK_TOKENS.axis),
      tooltipBg: readToken('--chart-tooltip-bg', FALLBACK_TOKENS.tooltipBg),
      tooltipText: readToken('--chart-tooltip-text', FALLBACK_TOKENS.tooltipText),
      tooltipBorder: readToken('--chart-tooltip-border', FALLBACK_TOKENS.tooltipBorder),
    });
  }, []);

  if (!data || data.length === 0) return null;

  const tooltipStyle = {
    fontSize: 11,
    borderRadius: 8,
    backgroundColor: tokens.tooltipBg,
    border: `1px solid ${tokens.tooltipBorder}`,
    color: tokens.tooltipText,
  };

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        {type === 'bar' ? (
          <BarChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={tokens.grid} />
            <XAxis
              dataKey={xKey}
              tick={{ fontSize: 10, fill: tokens.axis }}
              axisLine={{ stroke: tokens.grid }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: tokens.axis }}
              axisLine={{ stroke: tokens.grid }}
              tickFormatter={(v: number) =>
                v >= 10000 ? `${(v / 10000).toFixed(0)}만` : v.toLocaleString()
              }
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(value: number) => [value.toLocaleString(), dataKey]}
            />
            <Bar dataKey={dataKey} fill={color} radius={[2, 2, 0, 0]} />
          </BarChart>
        ) : (
          <LineChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={tokens.grid} />
            <XAxis
              dataKey={xKey}
              tick={{ fontSize: 10, fill: tokens.axis }}
              axisLine={{ stroke: tokens.grid }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: tokens.axis }}
              axisLine={{ stroke: tokens.grid }}
              tickFormatter={(v: number) =>
                v >= 10000 ? `${(v / 10000).toFixed(0)}만` : v.toLocaleString()
              }
            />
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(value: number) => [value.toLocaleString(), dataKey]}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

export default memo(InlineChart);
