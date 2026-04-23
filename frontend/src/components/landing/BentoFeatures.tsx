'use client';

interface Cell {
  id: string;
  emoji: string;
  title: string;
  desc: string;
  accent: 'blue' | 'teal' | 'amber' | 'rose' | 'indigo' | 'slate';
}

const CELLS: Cell[] = [
  {
    id: 'map',
    emoji: '🗺️',
    title: '지도 기반 탐색',
    desc: '1,650개 서울 상권을 한눈에. 클릭 한 번으로 핵심 지표 프리뷰.',
    accent: 'blue',
  },
  {
    id: 'chat',
    emoji: '💬',
    title: '대화형 AI 리포트',
    desc: '자연어로 질문하면 Claude + Gemini가 데이터를 해석해 답합니다.',
    accent: 'teal',
  },
  {
    id: 'compare',
    emoji: '📊',
    title: '2~3 상권 비교',
    desc: '다색 하이라이트로 동시에. 매출·유동인구·점포 한 장.',
    accent: 'amber',
  },
  {
    id: 'recommend',
    emoji: '🎯',
    title: '업종 추천',
    desc: '예산·상권 특성 기반 Top 5 업종 점수와 근거 제공.',
    accent: 'rose',
  },
  {
    id: 'simulation',
    emoji: '📈',
    title: '매출 시뮬레이션',
    desc: '월 예상 매출 p25/p50/p75 범위. 서울 평균 대비 자동 비교.',
    accent: 'indigo',
  },
  {
    id: 'pdf',
    emoji: '📄',
    title: 'PDF 리포트',
    desc: '분석 결과를 한 번에 PDF로 저장. 고객·투자자 공유용.',
    accent: 'slate',
  },
];

const ACCENT_MAP: Record<Cell['accent'], string> = {
  blue: 'var(--brand-deep-blue)',
  teal: 'var(--brand-teal)',
  amber: '#f59e0b',
  rose: '#f43f5e',
  indigo: '#6366f1',
  slate: '#64748b',
};

export default function BentoFeatures() {
  return (
    <section
      data-testid="bento-features"
      className="px-6 py-16"
      style={{ backgroundColor: 'var(--bg-secondary)' }}
    >
      <div className="max-w-6xl mx-auto">
        <h2
          className="text-2xl lg:text-3xl font-bold mb-2"
          style={{ color: 'var(--text-primary)' }}
        >
          무엇을 할 수 있나요?
        </h2>
        <p className="text-sm lg:text-base mb-10" style={{ color: 'var(--text-secondary)' }}>
          LLM 무호출 프리뷰부터 PDF 리포트까지. 클릭만으로 이어집니다.
        </p>

        <div
          className="grid gap-4"
          style={{
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          }}
        >
          {CELLS.map((cell) => (
            <article
              key={cell.id}
              data-testid={`bento-cell-${cell.id}`}
              className="p-5 rounded-2xl transition-all hover:-translate-y-1"
              style={{
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                boxShadow: '0 4px 20px -12px rgba(0,0,0,0.15)',
              }}
            >
              <div
                className="inline-flex items-center justify-center w-10 h-10 rounded-xl mb-3 text-xl"
                style={{
                  backgroundColor: `color-mix(in srgb, ${ACCENT_MAP[cell.accent]} 18%, transparent)`,
                  color: ACCENT_MAP[cell.accent],
                }}
                aria-hidden
              >
                {cell.emoji}
              </div>
              <h3
                className="text-base font-semibold mb-1"
                style={{ color: 'var(--text-primary)' }}
              >
                {cell.title}
              </h3>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                {cell.desc}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
