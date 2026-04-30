'use client';

import Link from 'next/link';
import { useEffect } from 'react';

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * D.1 — `/app` segment error boundary.
 * 지도/챗 패널의 unhandled error 를 catch — Kakao SDK 로드 실패, SSE 연결
 * 끊김 등에서 사용자가 빈 화면 보지 않도록 함.
 */
export default function AppError({ error, reset }: Props) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error('[AppError]', error);
  }, [error]);

  return (
    <div
      data-testid="app-route-error"
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
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      </div>
      <h1 className="text-xl font-bold mb-2">분석 화면을 불러오지 못했습니다</h1>
      <p
        className="text-sm mb-6 max-w-md"
        style={{ color: 'var(--text-secondary)' }}
      >
        네트워크 또는 지도 SDK 로딩에 문제가 있을 수 있습니다. 다시 시도하거나
        랜딩으로 돌아가 주세요.
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
          data-testid="app-route-error-reset"
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
          data-testid="app-route-error-home"
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
