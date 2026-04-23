'use client';

import { useRef, useState } from 'react';
import { submitFeedback } from '@/lib/api';
import { useChatStore } from '@/stores/chatStore';

const REASONS = ['부정확함', '느림', '주제 벗어남'] as const;
type Reason = (typeof REASONS)[number];

/**
 * L1 — per-card inline 👍 / 👎. Wires Langfuse score via `/api/feedback/score`.
 *
 * Spam guard:
 *   - 500ms debounce per click.
 *   - Session map (`chatStore.feedbackByTrace`) limits each trace_id to one submission.
 *   - Backend idempotency: repeated POSTs with the same trace_id are dropped server-side.
 */
export default function FeedbackRow() {
  const lastTraceId = useChatStore((s) => s.lastTraceId);
  const feedbackByTrace = useChatStore((s) => s.feedbackByTrace);
  const recordFeedback = useChatStore((s) => s.recordFeedback);

  const [reasonOpen, setReasonOpen] = useState(false);
  const [pickedReason, setPickedReason] = useState<Reason | null>(null);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const lastClickRef = useRef(0);

  if (!lastTraceId) return null;

  const already = feedbackByTrace[lastTraceId];

  const send = async (value: 'up' | 'down', extra?: { reason?: string; comment?: string }) => {
    const now = Date.now();
    if (now - lastClickRef.current < 500) return; // debounce
    lastClickRef.current = now;

    if (already) return; // session guard — one per trace

    try {
      setSubmitting(true);
      await submitFeedback({
        trace_id: lastTraceId,
        value,
        reason: extra?.reason,
        comment: extra?.comment?.slice(0, 60),
      });
      recordFeedback(lastTraceId, value);
      setReasonOpen(false);
    } catch {
      // silent — scoring is optional, don't interrupt UX
    } finally {
      setSubmitting(false);
    }
  };

  if (already) {
    return (
      <div
        className="mt-2 text-xs"
        data-testid="feedback-row-ack"
        style={{ color: 'var(--text-muted)' }}
      >
        {already === 'up' ? '👍 피드백 감사합니다' : '👎 의견을 반영하겠습니다'}
      </div>
    );
  }

  return (
    <div className="mt-2" data-testid="feedback-row">
      <div className="flex items-center gap-1.5">
        <span
          className="text-xs mr-1"
          style={{ color: 'var(--text-muted)' }}
        >
          이 답변 어떠셨나요?
        </span>
        <button
          type="button"
          data-testid="feedback-thumbs-up"
          disabled={submitting}
          onClick={() => send('up')}
          aria-label="좋아요"
          className="w-7 h-7 rounded-full flex items-center justify-center text-sm transition-colors disabled:opacity-50"
          style={{
            backgroundColor: 'var(--bg-tertiary)',
            color: 'var(--text-primary)',
          }}
        >
          👍
        </button>
        <button
          type="button"
          data-testid="feedback-thumbs-down"
          disabled={submitting}
          onClick={() => {
            setReasonOpen((v) => !v);
          }}
          aria-label="별로예요"
          aria-expanded={reasonOpen}
          className="w-7 h-7 rounded-full flex items-center justify-center text-sm transition-colors disabled:opacity-50"
          style={{
            backgroundColor: 'var(--bg-tertiary)',
            color: 'var(--text-primary)',
          }}
        >
          👎
        </button>
      </div>

      {reasonOpen ? (
        <div
          className="mt-2 p-3 rounded-xl"
          data-testid="feedback-reason-panel"
          style={{
            backgroundColor: 'var(--bg-tertiary)',
            border: '1px solid var(--border-color)',
          }}
        >
          <div className="flex flex-wrap gap-1.5">
            {REASONS.map((r) => {
              const active = pickedReason === r;
              return (
                <button
                  key={r}
                  type="button"
                  data-testid={`feedback-reason-${r}`}
                  onClick={() => setPickedReason(active ? null : r)}
                  className="text-xs px-3 py-1.5 rounded-full transition-colors"
                  style={{
                    backgroundColor: active
                      ? 'var(--brand-deep-blue)'
                      : 'var(--bg-primary)',
                    color: active ? '#ffffff' : 'var(--text-primary)',
                    border: `1px solid ${active ? 'var(--brand-deep-blue)' : 'var(--border-color)'}`,
                  }}
                >
                  {r}
                </button>
              );
            })}
          </div>
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value.slice(0, 60))}
            placeholder="추가 의견 (선택, 60자)"
            className="mt-2 w-full px-3 py-1.5 text-xs rounded-lg"
            style={{
              backgroundColor: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
            }}
          />
          <div className="mt-2 flex justify-end gap-1.5">
            <button
              type="button"
              onClick={() => {
                setReasonOpen(false);
                setPickedReason(null);
                setComment('');
              }}
              className="text-xs px-3 py-1.5 rounded-full"
              style={{
                color: 'var(--text-muted)',
                backgroundColor: 'transparent',
              }}
            >
              취소
            </button>
            <button
              type="button"
              data-testid="feedback-submit"
              disabled={submitting}
              onClick={() =>
                send('down', {
                  reason: pickedReason ?? undefined,
                  comment: comment.trim() || undefined,
                })
              }
              className="text-xs px-3 py-1.5 rounded-full font-semibold disabled:opacity-50"
              style={{
                backgroundColor: 'var(--brand-deep-blue)',
                color: '#ffffff',
              }}
            >
              제출
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
