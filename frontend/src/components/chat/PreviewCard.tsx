'use client';

import { DistrictPreview } from '@/lib/api';

interface Props {
  preview: DistrictPreview;
  onQuestion: (question: string) => void;
  onDeepAnalysis: () => void;
  disabled?: boolean;
}

function formatNumber(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return v.toLocaleString('ko-KR');
}

function formatDelta(pct: number | null | undefined): {
  label: string;
  tone: 'up' | 'down' | 'flat';
} {
  if (pct === null || pct === undefined) return { label: '', tone: 'flat' };
  const sign = pct > 0 ? '+' : '';
  const tone: 'up' | 'down' | 'flat' = pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat';
  return { label: `${sign}${pct.toFixed(1)}%`, tone };
}

function formatHour(hour: number | null | undefined): string {
  if (hour === null || hour === undefined) return '—';
  const next = (hour + 1) % 24;
  return `${hour}~${next}시`;
}

export default function PreviewCard({
  preview,
  onQuestion,
  onDeepAnalysis,
  disabled,
}: Props) {
  const delta = formatDelta(preview.floating_population.prev_quarter_delta_pct);
  const deltaColor =
    delta.tone === 'up'
      ? 'var(--success)'
      : delta.tone === 'down'
        ? 'var(--error)'
        : 'var(--text-muted)';

  return (
    <article
      data-testid="district-preview"
      className="rounded-2xl p-4 animate-msg-in"
      style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        boxShadow: '0 4px 20px -12px rgba(11,61,145,0.18)',
      }}
    >
      {/* Header */}
      <header className="flex items-start justify-between gap-2 mb-3">
        <div>
          <div
            className="text-[11px] font-semibold uppercase tracking-wider mb-1"
            style={{ color: 'var(--brand-teal)' }}
          >
            프리뷰 · LLM 무호출
          </div>
          <h3
            className="text-lg font-bold leading-tight"
            style={{ color: 'var(--text-primary)' }}
          >
            {preview.district_name}
          </h3>
          <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {preview.district_type}
            {preview.data_quarter ? ` · ${preview.data_quarter}` : ''}
          </div>
        </div>
      </header>

      {/* Top categories */}
      {preview.top_categories.length > 0 ? (
        <section className="mb-3">
          <div
            className="text-xs font-semibold mb-1.5"
            style={{ color: 'var(--text-secondary)' }}
          >
            주요 업종 Top 3
          </div>
          <ul className="space-y-1.5">
            {preview.top_categories.map((c, idx) => (
              <li
                key={`${idx}-${c.category_name.slice(0, 8)}`}
                className="flex items-center justify-between text-sm"
              >
                <span style={{ color: 'var(--text-primary)' }}>
                  {idx + 1}. {c.category_name}
                </span>
                <span className="flex items-center gap-2">
                  <span
                    className="h-1.5 rounded-full"
                    style={{
                      width: `${Math.max(8, Math.min(80, c.share_pct * 3))}px`,
                      backgroundColor: 'var(--brand-deep-blue)',
                      opacity: 0.3 + Math.min(0.7, c.share_pct / 40),
                    }}
                    aria-hidden
                  />
                  <span
                    className="text-xs tabular-nums"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {c.share_pct.toFixed(1)}% · {formatNumber(c.store_count)}개
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* Floating population */}
      <section
        className="mb-4 grid grid-cols-2 gap-2 p-3 rounded-xl"
        style={{ backgroundColor: 'var(--bg-tertiary)' }}
      >
        <div>
          <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
            유동인구 (분기)
          </div>
          <div
            className="text-base font-semibold tabular-nums"
            style={{ color: 'var(--text-primary)' }}
          >
            {formatNumber(preview.floating_population.daily_total)}
          </div>
          {delta.label ? (
            <div className="text-xs tabular-nums" style={{ color: deltaColor }}>
              전분기 대비 {delta.label}
            </div>
          ) : null}
        </div>
        <div>
          <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
            피크 시간대
          </div>
          <div
            className="text-base font-semibold tabular-nums"
            style={{ color: 'var(--text-primary)' }}
          >
            {formatHour(preview.floating_population.peak_hour)}
          </div>
        </div>
      </section>

      {/* Suggested questions */}
      {preview.suggested_questions.length > 0 ? (
        <section className="mb-4">
          <div
            className="text-xs font-semibold mb-2"
            style={{ color: 'var(--text-secondary)' }}
          >
            예시 질문
          </div>
          <div
            className="flex flex-wrap gap-1.5"
            data-testid="preview-suggested-chips"
          >
            {preview.suggested_questions.map((q, idx) => (
              <button
                key={`${idx}-${q.slice(0, 12)}`}
                type="button"
                data-testid={`preview-chip-${idx}`}
                onClick={() => onQuestion(q)}
                disabled={disabled}
                className="text-xs px-3 py-1.5 rounded-full disabled:opacity-50 disabled:cursor-not-allowed transition-colors hover:-translate-y-0.5"
                style={{
                  backgroundColor: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-color)',
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {/* Primary CTA */}
      <button
        type="button"
        data-testid="preview-deep-analysis"
        onClick={onDeepAnalysis}
        disabled={disabled}
        className="w-full py-2.5 rounded-xl font-semibold text-sm disabled:opacity-50 disabled:cursor-not-allowed transition-transform hover:-translate-y-0.5"
        style={{
          backgroundColor: 'var(--brand-deep-blue)',
          color: '#ffffff',
        }}
      >
        AI 분석 보기 →
      </button>

      <p
        className="mt-2 text-[11px] text-center"
        style={{ color: 'var(--text-muted)' }}
      >
        이 프리뷰는 데이터베이스 직접 조회입니다. 심층 분석은 AI 에이전트가 생성합니다.
      </p>
    </article>
  );
}
