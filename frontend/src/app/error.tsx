'use client';

import Link from 'next/link';
import { useEffect } from 'react';

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * D.1 — 글로벌 라우트 error boundary.
 * Next.js 14: error.tsx 는 동일 segment 의 모든 client error 를 catch.
 * digest 는 서버 콘솔의 동일 trace 와 매칭되는 해시 (Vercel/Next 표준).
 */
export default function GlobalError({ error, reset }: Props) {
  useEffect(() => {
    // 운영 환경에선 Langfuse 외 별도 로깅이 없으므로 console 로 남김.
    // eslint-disable-next-line no-console
    console.error('[GlobalError]', error);
  }, [error]);

  return (
    <div
      data-testid="route-error"
      className="min-h-screen flex flex-col items-center justify-center px-6 text-center"
      style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
    >
      <div
        className="w-14 h-14 rounded-full flex items-center justify-center mb-4"
        style={{ backgroundColor: 'var(--bg-tertiary)' }}
        aria-hidden
      >
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{ color: 'var(--error)' }}
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h1 className="text-xl font-bold mb-2">예상치 못한 오류가 발생했습니다</h1>
      <p
        className="text-sm mb-6 max-w-md"
        style={{ color: 'var(--text-secondary)' }}
      >
        잠시 후 다시 시도해 주세요. 문제가 계속되면 우측 하단 피드백으로 알려주세요.
      </p>
      {error.digest ? (
        <p
          className="text-[11px] mb-6 font-mono"
          style={{ color: 'var(--text-muted)' }}
        >
          오류 ID: {error.digest}
        </p>
      ) : null}
      <div className="flex gap-2">
        <button
          type="button"
          data-testid="route-error-reset"
          onClick={() => reset()}
          className="px-4 py-2 rounded-lg text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          style={{
            backgroundColor: 'var(--brand-deep-blue)',
            color: '#ffffff',
          }}
        >
          다시 시도
        </button>
        <Link
          href="/"
          data-testid="route-error-home"
          className="px-4 py-2 rounded-lg text-sm font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          style={{
            backgroundColor: 'var(--bg-tertiary)',
            color: 'var(--text-primary)',
          }}
        >
          홈으로 이동
        </Link>
      </div>
    </div>
  );
}
