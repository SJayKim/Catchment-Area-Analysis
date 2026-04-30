import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: '이용약관 — MarketScope AI',
  description: 'MarketScope AI 이용약관 (초안). 정식 출시 전 외부 변호사 검토 예정.',
  robots: { index: false, follow: false },
};

export default function TermsPage() {
  return (
    <main
      data-testid="terms-page"
      className="min-h-screen px-6 py-12"
      style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
    >
      <div className="max-w-3xl mx-auto">
        <nav className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
          <Link href="/" className="hover:underline" data-testid="terms-back-home">
            ← 홈으로
          </Link>
        </nav>

        <div
          className="inline-block mb-4 px-3 py-1 rounded-full text-xs font-medium"
          style={{
            backgroundColor: 'color-mix(in srgb, var(--brand-deep-blue) 12%, transparent)',
            color: 'var(--brand-deep-blue)',
          }}
        >
          초안 — 외부 변호사 검토 전
        </div>

        <h1
          className="text-3xl lg:text-4xl font-bold mb-3"
          style={{ color: 'var(--text-primary)' }}
        >
          이용약관
        </h1>
        <p className="text-sm mb-8" style={{ color: 'var(--text-muted)' }}>
          최종 갱신: 2026-04-30 (베타)
        </p>

        <section className="space-y-6 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          <p>
            본 약관은 MarketScope AI 베타 서비스 이용에 적용되는 임시 초안입니다. 정식
            출시 전 외부 법률 검토를 거쳐 갱신될 예정이며, 갱신 시 본 페이지에서 즉시
            반영합니다.
          </p>
          <h2 className="text-lg font-semibold pt-4" style={{ color: 'var(--text-primary)' }}>
            1. 서비스 성격
          </h2>
          <p>
            MarketScope AI 는 서울 열린데이터 광장 · 공공데이터포털 등 공개 출처의
            상권 데이터를 AI 가 해석해 제공하는 정보 서비스입니다. 분석 결과는
            참고용이며, 투자 · 창업 의사결정의 책임은 이용자에게 있습니다.
          </p>
          <h2 className="text-lg font-semibold pt-4" style={{ color: 'var(--text-primary)' }}>
            2. 베타 기간 무료 이용
          </h2>
          <p>
            베타 기간 동안 결제 · 로그인 없이 모든 기능을 무료로 제공합니다. 정식 출시
            시점의 요금제는 별도 공지합니다.
          </p>
          <h2 className="text-lg font-semibold pt-4" style={{ color: 'var(--text-primary)' }}>
            3. 데이터 출처와 면책
          </h2>
          <p>
            제공되는 통계는 원천 데이터의 갱신 주기에 따라 최신성과 차이가 있을 수
            있습니다. 운영자는 데이터의 정확성을 보장하지 않으며, 이용자가 분석 결과를
            토대로 한 의사결정에 대해 어떠한 책임도 지지 않습니다.
          </p>
          <h2 className="text-lg font-semibold pt-4" style={{ color: 'var(--text-primary)' }}>
            4. 문의
          </h2>
          <p>
            약관에 관한 문의는 푸터의 피드백 채널을 이용해 주세요.
          </p>
        </section>
      </div>
    </main>
  );
}
