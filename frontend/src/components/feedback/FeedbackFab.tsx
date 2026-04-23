'use client';

import { useState } from 'react';
import FeedbackModal from './FeedbackModal';

/**
 * L3 FAB — general-purpose feedback channel.
 *
 * Priority:
 *   1. `NEXT_PUBLIC_KAKAO_CHANNEL_URL`   → 카카오톡 1:1 문의 (신탭)
 *   2. `NEXT_PUBLIC_FEEDBACK_FORM_URL`   → Tally iframe 모달
 *   3. (neither)                          → 숨김 (dev 오노출 방지)
 */
export default function FeedbackFab() {
  const kakao = process.env.NEXT_PUBLIC_KAKAO_CHANNEL_URL;
  const tally = process.env.NEXT_PUBLIC_FEEDBACK_FORM_URL;
  const [open, setOpen] = useState(false);

  const mode: 'kakao' | 'tally' | 'hidden' = kakao
    ? 'kakao'
    : tally
      ? 'tally'
      : 'hidden';

  if (mode === 'hidden') return null;

  const handleClick = () => {
    if (mode === 'kakao') {
      window.open(kakao, '_blank', 'noopener,noreferrer');
      return;
    }
    setOpen(true);
  };

  return (
    <>
      <button
        type="button"
        onClick={handleClick}
        data-testid="feedback-fab"
        data-feedback-mode={mode}
        aria-label="피드백 보내기"
        title="피드백 보내기"
        className="fixed z-40 flex items-center gap-2 px-4 py-3 rounded-full font-semibold text-sm shadow-lg transition-transform hover:-translate-y-0.5"
        style={{
          bottom: '1.5rem',
          right: '1.5rem',
          backgroundColor: 'var(--brand-deep-blue)',
          color: '#ffffff',
          boxShadow: '0 10px 30px -10px rgba(11,61,145,0.55)',
        }}
      >
        <span aria-hidden>💬</span>
        <span className="hidden sm:inline">피드백</span>
      </button>

      {mode === 'tally' && tally ? (
        <FeedbackModal
          open={open}
          onClose={() => setOpen(false)}
          formUrl={tally}
        />
      ) : null}
    </>
  );
}
