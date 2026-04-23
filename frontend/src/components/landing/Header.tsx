'use client';

import Link from 'next/link';

export default function Header() {
  return (
    <header
      className="sticky top-0 z-40 flex items-center justify-between px-6 py-4 backdrop-blur"
      style={{
        backgroundColor: 'color-mix(in srgb, var(--bg-primary) 80%, transparent)',
        borderBottom: '1px solid var(--border-color)',
      }}
    >
      <Link
        href="/"
        className="flex items-center gap-2 text-lg font-bold tracking-tight"
        style={{ color: 'var(--brand-deep-blue)' }}
      >
        <span
          aria-hidden
          className="inline-block w-6 h-6 rounded-md"
          style={{ backgroundColor: 'var(--brand-deep-blue)' }}
        />
        MarketScope AI
      </Link>
      <nav className="flex items-center gap-3">
        <Link
          href="/app"
          data-testid="header-cta"
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg transition-colors"
          style={{
            backgroundColor: 'var(--brand-deep-blue)',
            color: '#ffffff',
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.backgroundColor = 'var(--brand-deep-blue-hover)')
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.backgroundColor = 'var(--brand-deep-blue)')
          }
        >
          시작하기
          <span aria-hidden>→</span>
        </Link>
      </nav>
    </header>
  );
}
