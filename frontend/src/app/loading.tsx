/**
 * D.1 — 글로벌 라우트 loading skeleton.
 * Next.js 14: loading.tsx 는 동일 segment Suspense fallback.
 * 랜딩/터미널 페이지 전환 시 잠깐 노출됨.
 */
export default function GlobalLoading() {
  return (
    <div
      data-testid="route-loading"
      role="status"
      aria-label="페이지 불러오는 중"
      className="min-h-screen flex flex-col items-center justify-center px-6"
      style={{ backgroundColor: 'var(--bg-primary)' }}
    >
      <div
        className="w-10 h-10 rounded-full border-4 animate-spin"
        style={{
          borderColor: 'var(--bg-tertiary)',
          borderTopColor: 'var(--brand-deep-blue)',
        }}
        aria-hidden
      />
      <p
        className="mt-4 text-sm"
        style={{ color: 'var(--text-muted)' }}
      >
        불러오는 중...
      </p>
    </div>
  );
}
