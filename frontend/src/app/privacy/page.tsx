import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: '개인정보처리방침 — MarketScope AI',
  description:
    'MarketScope AI 개인정보처리방침 (초안). 정식 출시 전 외부 변호사 검토 예정.',
  robots: { index: false, follow: false },
};

export default function PrivacyPage() {
  return (
    <main
      data-testid="privacy-page"
      className="min-h-screen px-6 py-12"
      style={{ backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}
    >
      <div className="max-w-3xl mx-auto">
        <nav className="mb-6 text-sm" style={{ color: 'var(--text-secondary)' }}>
          <Link href="/" className="hover:underline" data-testid="privacy-back-home">
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
          개인정보처리방침
        </h1>
        <p className="text-sm mb-8" style={{ color: 'var(--text-muted)' }}>
          최종 갱신: 2026-04-30 (베타)
        </p>

        <section className="space-y-6 text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          <p>
            본 방침은 MarketScope AI 베타 서비스의 개인정보 처리에 관한 임시
            초안입니다. 정식 출시 전 외부 법률 검토 후 갱신됩니다.
          </p>
          <h2 className="text-lg font-semibold pt-4" style={{ color: 'var(--text-primary)' }}>
            1. 수집 항목
          </h2>
          <p>
            베타 단계에서는 회원가입 없이 서비스가 제공되며, 별도의 식별 가능한
            개인정보를 수집하지 않습니다. 다만 다음 정보는 운영 · 품질 개선 목적으로
            처리될 수 있습니다.
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>요청 IP · User-Agent (보안 및 이상 탐지)</li>
            <li>채팅 세션 ID · 메시지 (인메모리 30분 TTL)</li>
            <li>사용자가 명시적으로 입력한 피드백 본문</li>
          </ul>
          <h2 className="text-lg font-semibold pt-4" style={{ color: 'var(--text-primary)' }}>
            2. 보관 기간
          </h2>
          <p>
            세션 데이터는 인메모리 저장소에 30분간 보관 후 자동 삭제됩니다. 피드백
            본문은 서비스 개선 목적으로 별도 보관할 수 있으며, 본인 식별이 불가능한
            형태로 처리합니다.
          </p>
          <h2 className="text-lg font-semibold pt-4" style={{ color: 'var(--text-primary)' }}>
            3. 제 3자 제공
          </h2>
          <p>
            법령에 의한 경우를 제외하고 이용자 정보를 제 3자에게 제공하지 않습니다. AI
            응답 생성을 위해 Anthropic · Google 의 모델 API 를 사용하며, 해당 처리는
            각 사의 정책을 따릅니다.
          </p>
          <h2 className="text-lg font-semibold pt-4" style={{ color: 'var(--text-primary)' }}>
            4. 문의
          </h2>
          <p>
            개인정보 처리 관련 문의는 푸터의 피드백 채널을 이용해 주세요.
          </p>
        </section>
      </div>
    </main>
  );
}
