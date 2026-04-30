'use client';

import { useEffect, useRef, useState } from 'react';

interface Props {
  open: boolean;
  onClose: () => void;
  formUrl: string;
}

const IFRAME_TIMEOUT_MS = 5000;

/**
 * Tally.so iframe modal (L3 fallback).
 * ESC closes, click outside closes, body scroll locks while open.
 *
 * D.5 — iframe `onLoad` 가 5s 안에 발화하지 않거나 `onError` 가 트리거되면
 * 폴백 UI 노출 (corp 환경에서 Tally 도메인 차단 케이스 대응). mailto + Kakao
 * 채널 링크 두 경로 제공.
 */
export default function FeedbackModal({ open, onClose, formUrl }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const iframeReadyRef = useRef(false);
  const [showFallback, setShowFallback] = useState(false);

  const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || null;
  const kakaoUrl = process.env.NEXT_PUBLIC_KAKAO_CHANNEL_URL || null;

  useEffect(() => {
    if (!open) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);

    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  useEffect(() => {
    if (!open) {
      iframeReadyRef.current = false;
      setShowFallback(false);
      return;
    }
    const t = window.setTimeout(() => {
      if (!iframeReadyRef.current) setShowFallback(true);
    }, IFRAME_TIMEOUT_MS);
    return () => window.clearTimeout(t);
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="피드백 폼"
      data-testid="feedback-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(15,23,42,0.75)' }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="relative w-full max-w-xl h-[75vh] rounded-2xl overflow-hidden"
        style={{ backgroundColor: 'var(--bg-primary)' }}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="닫기"
          className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full flex items-center justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          style={{
            backgroundColor: 'var(--bg-tertiary)',
            color: 'var(--text-primary)',
          }}
        >
          ✕
        </button>
        {showFallback ? (
          <div
            data-testid="feedback-modal-fallback"
            className="w-full h-full flex flex-col items-center justify-center text-center px-6"
          >
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center mb-4"
              style={{ backgroundColor: 'var(--bg-tertiary)' }}
              aria-hidden
            >
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ color: 'var(--warning)' }}
              >
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
              </svg>
            </div>
            <h3
              className="text-base font-semibold mb-1"
              style={{ color: 'var(--text-primary)' }}
            >
              폼이 열리지 않았어요
            </h3>
            <p
              className="text-xs mb-5 max-w-sm"
              style={{ color: 'var(--text-secondary)' }}
            >
              회사 보안 정책으로 외부 폼이 차단된 환경일 수 있습니다. 아래 채널로
              직접 의견을 보내주세요.
            </p>
            <div className="flex flex-col gap-2 w-full max-w-xs">
              {contactEmail ? (
                <a
                  href={`mailto:${contactEmail}?subject=MarketScope%20AI%20피드백`}
                  data-testid="feedback-modal-mailto"
                  className="px-4 py-2 rounded-lg text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  style={{
                    backgroundColor: 'var(--brand-deep-blue)',
                    color: '#ffffff',
                  }}
                >
                  이메일로 보내기
                </a>
              ) : null}
              {kakaoUrl ? (
                <a
                  href={kakaoUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  data-testid="feedback-modal-kakao"
                  className="px-4 py-2 rounded-lg text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                  style={{
                    backgroundColor: 'var(--bg-tertiary)',
                    color: 'var(--text-primary)',
                  }}
                >
                  카카오 채널로 보내기
                </a>
              ) : null}
              {!contactEmail && !kakaoUrl ? (
                <p
                  className="text-xs"
                  style={{ color: 'var(--text-muted)' }}
                >
                  연락 채널이 설정되지 않았습니다. 잠시 후 다시 시도해 주세요.
                </p>
              ) : null}
            </div>
          </div>
        ) : (
          <iframe
            data-testid="feedback-modal-iframe"
            src={formUrl}
            title="피드백 폼"
            className="w-full h-full border-0"
            loading="lazy"
            onLoad={() => {
              iframeReadyRef.current = true;
            }}
            onError={() => setShowFallback(true)}
          />
        )}
      </div>
    </div>
  );
}
