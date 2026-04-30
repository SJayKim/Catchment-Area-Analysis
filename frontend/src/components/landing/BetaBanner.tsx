'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { X } from 'lucide-react';

const STORAGE_KEY = 'ms_beta_banner_dismissed';

function readDismissed(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function writeDismissed(): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, '1');
  } catch {
    // Safari Private mode 등 — 세션 내 dismiss 만 동작
  }
}

export default function BetaBanner() {
  const [dismissed, setDismissed] = useState<boolean | null>(null);

  useEffect(() => {
    setDismissed(readDismissed());
  }, []);

  if (dismissed !== false) {
    return null;
  }

  const handleDismiss = () => {
    writeDismissed();
    setDismissed(true);
  };

  return (
    <section
      data-testid="beta-banner"
      className="relative px-6 py-12"
      style={{
        backgroundColor: 'var(--brand-deep-blue)',
        color: '#ffffff',
      }}
    >
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="배너 닫기"
        data-testid="beta-banner-dismiss"
        className="absolute top-3 right-3 inline-flex items-center justify-center w-6 h-6 rounded-md transition-colors hover:bg-white/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
      >
        <X size={16} strokeWidth={2} aria-hidden />
      </button>
      <div className="max-w-4xl mx-auto text-center">
        <h2 className="text-2xl lg:text-3xl font-bold mb-2">
          베타 기간 무료. 의견이 서비스를 만듭니다.
        </h2>
        <p className="text-sm lg:text-base mb-6 opacity-90">
          결제·로그인 없이 지금 바로 사용해보세요. 피드백 주신 분께 정식 출시
          프로모션을 드립니다.
        </p>
        <Link
          href="/app"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-base transition-transform hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
          style={{
            backgroundColor: 'var(--brand-teal)',
            color: '#ffffff',
          }}
        >
          지금 시작하기 <span aria-hidden>→</span>
        </Link>
      </div>
    </section>
  );
}
