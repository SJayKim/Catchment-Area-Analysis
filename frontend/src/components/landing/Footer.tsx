'use client';

export default function Footer() {
  const kakaoUrl = process.env.NEXT_PUBLIC_KAKAO_CHANNEL_URL;
  const tallyUrl = process.env.NEXT_PUBLIC_FEEDBACK_FORM_URL;
  const feedbackHref = kakaoUrl || tallyUrl || null;
  const repoUrl = process.env.NEXT_PUBLIC_REPO_URL || null;
  const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL || null;

  return (
    <footer
      className="px-6 py-12"
      style={{
        backgroundColor: 'var(--bg-secondary)',
        borderTop: '1px solid var(--border-color)',
      }}
    >
      <div className="max-w-6xl mx-auto grid gap-8 sm:grid-cols-2 lg:grid-cols-[1.5fr,1fr,1fr,1fr]">
        <div>
          <div
            className="text-lg font-bold mb-2"
            style={{ color: 'var(--brand-deep-blue)' }}
          >
            MarketScope AI
          </div>
          <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>
            서울 1,650개 상권 AI 분석 서비스. 베타 기간 무료.
          </p>
          <p className="text-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
            데이터: 서울 열린데이터 광장 (유동인구·추정매출·점포·상주인구) ·
            공공데이터포털. 본 서비스의 분석 결과는 참고용이며 투자·창업
            의사결정의 책임은 이용자에게 있습니다.
          </p>
        </div>

        <div>
          <div
            className="text-sm font-semibold mb-3"
            style={{ color: 'var(--text-primary)' }}
          >
            제품
          </div>
          <ul className="space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
            <li>
              <a href="/app" className="hover:underline focus:outline-none focus-visible:underline focus-visible:ring-2 focus-visible:ring-blue-500 rounded">
                지도에서 시작하기
              </a>
            </li>
            <li>
              <a href="#how-it-works" className="hover:underline focus:outline-none focus-visible:underline focus-visible:ring-2 focus-visible:ring-blue-500 rounded">
                사용 방법
              </a>
            </li>
          </ul>
        </div>

        <div>
          <div
            className="text-sm font-semibold mb-3"
            style={{ color: 'var(--text-primary)' }}
          >
            지원
          </div>
          <ul className="space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
            {feedbackHref ? (
              <li>
                <a
                  href={feedbackHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:underline focus:outline-none focus-visible:underline focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                  data-testid="footer-feedback-link"
                >
                  피드백 보내기
                </a>
              </li>
            ) : null}
            {repoUrl ? (
              <li>
                <a
                  href={repoUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:underline focus:outline-none focus-visible:underline focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                  data-testid="footer-repo-link"
                >
                  GitHub
                </a>
              </li>
            ) : null}
          </ul>
        </div>

        <div>
          <div
            className="text-sm font-semibold mb-3"
            style={{ color: 'var(--text-primary)' }}
          >
            법적
          </div>
          <ul className="space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
            <li>
              <a
                href="/terms"
                className="hover:underline focus:outline-none focus-visible:underline focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                data-testid="footer-terms-link"
              >
                이용약관
              </a>
            </li>
            <li>
              <a
                href="/privacy"
                className="hover:underline focus:outline-none focus-visible:underline focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                data-testid="footer-privacy-link"
              >
                개인정보처리방침
              </a>
            </li>
            {contactEmail ? (
              <li>
                <a
                  href={`mailto:${contactEmail}`}
                  className="hover:underline focus:outline-none focus-visible:underline focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
                  data-testid="footer-contact-link"
                >
                  문의
                </a>
              </li>
            ) : null}
          </ul>
        </div>
      </div>

      <div
        className="max-w-6xl mx-auto mt-8 pt-6 text-xs"
        style={{
          borderTop: '1px solid var(--border-color)',
          color: 'var(--text-muted)',
        }}
      >
        © 2026 MarketScope AI · All rights reserved.
      </div>
    </footer>
  );
}
