/**
 * D.1 — `/app` segment loading skeleton.
 * 좌측 grey 지도 placeholder + 우측 dot loader 로 SplitPanel 형태 미리 흉내.
 */
export default function AppLoading() {
  return (
    <div
      data-testid="app-route-loading"
      role="status"
      aria-label="분석 화면 불러오는 중"
      className="h-screen w-screen flex"
      style={{ backgroundColor: 'var(--bg-primary)' }}
    >
      <div
        className="flex-1 animate-pulse"
        style={{ backgroundColor: 'var(--bg-tertiary)' }}
        aria-hidden
      />
      <div
        className="w-[420px] flex flex-col items-center justify-center"
        style={{
          backgroundColor: 'var(--bg-primary)',
          borderLeft: '1px solid var(--border-color)',
        }}
      >
        <div className="flex gap-1.5" aria-hidden>
          <span
            className="w-2.5 h-2.5 rounded-full animate-bounce"
            style={{
              backgroundColor: 'var(--brand-deep-blue)',
              animationDelay: '0ms',
            }}
          />
          <span
            className="w-2.5 h-2.5 rounded-full animate-bounce"
            style={{
              backgroundColor: 'var(--brand-deep-blue)',
              animationDelay: '150ms',
            }}
          />
          <span
            className="w-2.5 h-2.5 rounded-full animate-bounce"
            style={{
              backgroundColor: 'var(--brand-deep-blue)',
              animationDelay: '300ms',
            }}
          />
        </div>
        <p
          className="mt-4 text-sm"
          style={{ color: 'var(--text-muted)' }}
        >
          분석 화면 준비 중...
        </p>
      </div>
    </div>
  );
}
