'use client';

const STEPS = [
  {
    num: '01',
    title: '지도에서 상권 클릭',
    desc: '서울 1,650개 상권 폴리곤 중 하나를 선택합니다.',
  },
  {
    num: '02',
    title: '핵심 지표 프리뷰 (Free · LLM 무호출)',
    desc: '지역 유형, 주요 업종 Top 3, 유동인구 추이를 즉시 확인하세요.',
  },
  {
    num: '03',
    title: '"AI 분석 보기" → 심층 리포트',
    desc: '요약·비교·추천·리스크·시뮬레이션 카드를 스트리밍으로 받습니다.',
  },
];

export default function HowItWorks() {
  return (
    <section
      id="how-it-works"
      data-testid="how-it-works"
      className="px-6 py-16"
      style={{ backgroundColor: 'var(--bg-primary)' }}
    >
      <div className="max-w-4xl mx-auto">
        <h2
          className="text-2xl lg:text-3xl font-bold mb-10"
          style={{ color: 'var(--text-primary)' }}
        >
          3단계면 끝납니다
        </h2>

        <ol className="relative border-l-2 pl-8 space-y-8" style={{ borderColor: 'var(--border-color)' }}>
          {STEPS.map((step, idx) => (
            <li key={step.num} className="relative">
              <span
                className="absolute -left-[2.35rem] top-0 inline-flex items-center justify-center w-10 h-10 rounded-full font-bold text-sm"
                style={{
                  backgroundColor: 'var(--brand-deep-blue)',
                  color: '#ffffff',
                }}
                aria-hidden
              >
                {idx + 1}
              </span>
              <div
                className="text-xs font-mono mb-1"
                style={{ color: 'var(--brand-teal)' }}
              >
                STEP {step.num}
              </div>
              <h3
                className="text-lg font-semibold mb-1"
                style={{ color: 'var(--text-primary)' }}
              >
                {step.title}
              </h3>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                {step.desc}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
