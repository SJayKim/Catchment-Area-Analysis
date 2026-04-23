'use client';

import { useEffect, useState } from 'react';

const EMOJIS: Array<{ value: number; label: string; emoji: string }> = [
  { value: 1, label: '별로', emoji: '😡' },
  { value: 2, label: '아쉬움', emoji: '😞' },
  { value: 3, label: '보통', emoji: '😐' },
  { value: 4, label: '괜찮음', emoji: '🙂' },
  { value: 5, label: '매우 만족', emoji: '😍' },
];

function isoWeek(d: Date): string {
  const year = d.getUTCFullYear();
  const week = Math.ceil(
    ((d.getTime() - Date.UTC(year, 0, 1)) / 86400000 + 1) / 7,
  );
  return `${year}${String(week).padStart(2, '0')}`;
}

function cookieKey(): string {
  return `ms_survey_week_${isoWeek(new Date())}`;
}

function hasCookie(name: string): boolean {
  if (typeof document === 'undefined') return false;
  return document.cookie.split('; ').some((c) => c.startsWith(`${name}=`));
}

function setCookie(name: string): void {
  if (typeof document === 'undefined') return;
  const sevenDays = 7 * 24 * 60 * 60;
  document.cookie = `${name}=1; path=/; max-age=${sevenDays}; SameSite=Lax`;
}

interface Props {
  trigger: boolean;
  onDismiss?: () => void;
}

/**
 * L2 — 무료 한도 소진 microsurvey.
 * `trigger=true` 일 때 (부모가 `messageCount >= DAILY_FREE_LIMIT` 로 판단) 노출.
 * 주 1회 쿠키 상한, dismiss 가능, GA4 dataLayer 이벤트로 수집 (backend 수정 0).
 */
export default function FreeLimitSurvey({ trigger, onDismiss }: Props) {
  const [open, setOpen] = useState(false);
  const [mood, setMood] = useState<number | null>(null);
  const [premium, setPremium] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (trigger && !hasCookie(cookieKey())) setOpen(true);
  }, [trigger]);

  const close = () => {
    setOpen(false);
    setCookie(cookieKey());
    onDismiss?.();
  };

  const submit = () => {
    if (mood === null) return;
    try {
      const w = window as unknown as { dataLayer?: unknown[] };
      if (!w.dataLayer) w.dataLayer = [];
      w.dataLayer.push({
        event: 'free_limit_survey',
        mood,
        premium_interest: premium,
      });
    } catch {
      // ignore — GA4 blocked
    }
    setSubmitted(true);
    setCookie(cookieKey());
    window.setTimeout(() => {
      setOpen(false);
      onDismiss?.();
    }, 1500);
  };

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="분석 피드백 짧은 설문"
      data-testid="free-limit-survey"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(15,23,42,0.6)' }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-6"
        style={{
          backgroundColor: 'var(--bg-primary)',
          border: '1px solid var(--border-color)',
        }}
      >
        <div className="flex items-start justify-between mb-4">
          <h3
            className="text-base font-semibold"
            style={{ color: 'var(--text-primary)' }}
          >
            한 번만 의견을 듣고 싶어요
          </h3>
          <button
            type="button"
            onClick={close}
            aria-label="닫기"
            className="text-lg"
            style={{ color: 'var(--text-muted)' }}
          >
            ✕
          </button>
        </div>

        {submitted ? (
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            감사합니다. 더 나은 분석을 만드는 데 쓰겠습니다.
          </p>
        ) : (
          <>
            <p
              className="text-sm mb-3"
              style={{ color: 'var(--text-secondary)' }}
            >
              방금 받은 분석, 얼마나 도움이 됐나요?
            </p>
            <div className="flex justify-between mb-4">
              {EMOJIS.map((e) => {
                const active = mood === e.value;
                return (
                  <button
                    key={e.value}
                    type="button"
                    data-testid={`survey-mood-${e.value}`}
                    onClick={() => setMood(e.value)}
                    aria-label={e.label}
                    aria-pressed={active}
                    className="flex flex-col items-center gap-1 px-2 py-1.5 rounded-xl transition-all"
                    style={{
                      backgroundColor: active
                        ? 'color-mix(in srgb, var(--brand-deep-blue) 14%, transparent)'
                        : 'transparent',
                    }}
                  >
                    <span className="text-2xl" aria-hidden>
                      {e.emoji}
                    </span>
                    <span
                      className="text-[11px]"
                      style={{
                        color: active
                          ? 'var(--brand-deep-blue)'
                          : 'var(--text-muted)',
                      }}
                    >
                      {e.label}
                    </span>
                  </button>
                );
              })}
            </div>

            {mood !== null && mood >= 4 ? (
              <div
                className="mb-4 p-3 rounded-xl"
                style={{ backgroundColor: 'var(--bg-tertiary)' }}
              >
                <p
                  className="text-xs mb-2"
                  style={{ color: 'var(--text-secondary)' }}
                >
                  Premium 요금(월 ₩9,900)에 관심 있으신가요?
                </p>
                <div className="flex gap-1.5">
                  {['네', '아니오', '나중에'].map((opt) => {
                    const active = premium === opt;
                    return (
                      <button
                        key={opt}
                        type="button"
                        data-testid={`survey-premium-${opt}`}
                        onClick={() => setPremium(opt)}
                        className="text-xs px-3 py-1.5 rounded-full transition-colors"
                        style={{
                          backgroundColor: active
                            ? 'var(--brand-deep-blue)'
                            : 'var(--bg-primary)',
                          color: active ? '#ffffff' : 'var(--text-primary)',
                          border: `1px solid ${active ? 'var(--brand-deep-blue)' : 'var(--border-color)'}`,
                        }}
                      >
                        {opt}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}

            <div className="flex justify-end gap-1.5">
              <button
                type="button"
                onClick={close}
                className="text-xs px-3 py-1.5 rounded-full"
                style={{ color: 'var(--text-muted)' }}
              >
                다음에
              </button>
              <button
                type="button"
                data-testid="survey-submit"
                onClick={submit}
                disabled={mood === null}
                className="text-xs px-3 py-1.5 rounded-full font-semibold disabled:opacity-50"
                style={{
                  backgroundColor: 'var(--brand-deep-blue)',
                  color: '#ffffff',
                }}
              >
                제출
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
