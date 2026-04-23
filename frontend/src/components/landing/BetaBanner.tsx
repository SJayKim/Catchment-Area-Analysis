'use client';

import Link from 'next/link';

export default function BetaBanner() {
  return (
    <section
      data-testid="beta-banner"
      className="px-6 py-12"
      style={{
        backgroundColor: 'var(--brand-deep-blue)',
        color: '#ffffff',
      }}
    >
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
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-base transition-transform hover:-translate-y-0.5"
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
