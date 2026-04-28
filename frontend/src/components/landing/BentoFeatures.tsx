'use client';

import {
  Columns3,
  FileText,
  Map,
  MessagesSquare,
  Target,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react';

interface Cell {
  id: string;
  Icon: LucideIcon;
  title: string;
  desc: string;
  accent: 'blue' | 'teal' | 'amber' | 'rose' | 'indigo' | 'slate';
}

const CELLS: Cell[] = [
  {
    id: 'map',
    Icon: Map,
    title: '지도 기반 상권 탐색',
    desc: '서울 1,650개 상권을 한 화면에서 탐색하고, 폴리곤을 클릭해 핵심 지표를 바로 확인합니다.',
    accent: 'blue',
  },
  {
    id: 'chat',
    Icon: MessagesSquare,
    title: '대화형 리포트',
    desc: '질문을 던지면 필요한 지표를 골라 근거와 함께 답합니다.',
    accent: 'teal',
  },
  {
    id: 'compare',
    Icon: Columns3,
    title: '2~3 상권 나란히 비교',
    desc: '매출·유동인구·점포 구성을 다색 하이라이트로 같은 화면에서 대조합니다.',
    accent: 'amber',
  },
  {
    id: 'recommend',
    Icon: Target,
    title: '유망 업종 추천',
    desc: '상권 특성과 예산 조건을 반영해 Top 5 업종을 점수와 근거로 제시합니다.',
    accent: 'rose',
  },
  {
    id: 'simulation',
    Icon: TrendingUp,
    title: '월 매출 시뮬레이션',
    desc: 'p25·중앙값·p75 범위를 서울 평균과 함께 자동 비교합니다.',
    accent: 'indigo',
  },
  {
    id: 'pdf',
    Icon: FileText,
    title: 'PDF 리포트 저장',
    desc: '분석 결과를 한 파일로 정리해 고객·투자자 공유용으로 내보냅니다.',
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
          지도 클릭에서 시작해, 비교·추천·시뮬레이션·PDF까지 한 흐름으로 이어집니다.
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
                className="inline-flex items-center justify-center w-10 h-10 rounded-xl mb-3"
                style={{
                  backgroundColor: `color-mix(in srgb, ${ACCENT_MAP[cell.accent]} 14%, transparent)`,
                  color: ACCENT_MAP[cell.accent],
                }}
                aria-hidden
              >
                <cell.Icon size={20} strokeWidth={1.75} />
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
