'use client';

/**
 * Hero Visual — 실 Kakao Map SDK 를 로드하지 않고,
 * CSS only 로 지도 폴리곤 + 카드 3종이 교차 fade-in 되는 "live-look" 데모.
 * LCP 비용 회피 + 번들 영향 0. prefers-reduced-motion 시 첫 프레임 고정.
 *
 * PNG 에셋은 추후 디자인 단계에서 public/hero/*.png 로 교체.
 * 지금은 SVG placeholder 로 shape 만 제공.
 */
export default function HeroVisual() {
  return (
    <div
      data-testid="hero-visual"
      className="relative w-full aspect-[4/3] rounded-3xl overflow-hidden"
      style={{
        backgroundColor: 'var(--bg-secondary)',
        border: '1px solid var(--border-color)',
        boxShadow: '0 20px 50px -25px rgba(11,61,145,0.25)',
      }}
    >
      {/* Map layer (SVG placeholder — 서울 폴리곤 느낌) */}
      <svg
        viewBox="0 0 400 300"
        className="absolute inset-0 w-full h-full"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden
      >
        <defs>
          <radialGradient id="hero-bg" cx="50%" cy="50%" r="75%">
            <stop offset="0%" stopColor="var(--brand-deep-blue)" stopOpacity="0.12" />
            <stop offset="100%" stopColor="var(--brand-deep-blue)" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="400" height="300" fill="url(#hero-bg)" />
        {/* 서울 상권 폴리곤 suggestion shapes */}
        <g stroke="var(--brand-deep-blue)" strokeWidth="1" fill="var(--brand-deep-blue)" fillOpacity="0.15">
          <polygon points="80,60 140,50 160,100 120,130 75,115" />
          <polygon points="200,80 260,70 280,130 230,150 195,115" />
          <polygon points="160,160 230,160 245,210 180,225 150,200" />
          <polygon points="280,180 340,170 345,230 290,240" />
        </g>
        <g fill="var(--brand-teal)">
          <circle cx="118" cy="95" r="5" opacity="0.85" />
          <circle cx="240" cy="115" r="5" opacity="0.85" />
          <circle cx="195" cy="195" r="5" opacity="0.85" />
        </g>
      </svg>

      {/* Card layer — 3장 cross-fade loop */}
      <div className="absolute inset-0">
        <div
          className="hero-frame absolute top-6 left-6 w-[60%] p-4 rounded-xl"
          style={{
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            boxShadow: '0 10px 30px -10px rgba(0,0,0,0.15)',
            animationDelay: '0s',
          }}
        >
          <div className="text-xs font-semibold mb-1" style={{ color: 'var(--brand-deep-blue)' }}>
            홍대입구 · 요약
          </div>
          <div className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            유동인구 상위 5%
          </div>
          <div className="flex items-end gap-1 h-10">
            {[30, 48, 65, 80, 72, 55, 40].map((h, i) => (
              <div
                key={i}
                className="flex-1 rounded-sm"
                style={{
                  height: `${h}%`,
                  backgroundColor: 'var(--brand-deep-blue)',
                  opacity: 0.25 + (h / 100) * 0.75,
                }}
              />
            ))}
          </div>
        </div>

        <div
          className="hero-frame absolute top-20 right-6 w-[50%] p-4 rounded-xl"
          style={{
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            boxShadow: '0 10px 30px -10px rgba(0,0,0,0.15)',
            animationDelay: '2.6s',
          }}
        >
          <div className="text-xs font-semibold mb-1" style={{ color: 'var(--brand-teal)' }}>
            강남 vs 성수 · 비교
          </div>
          <div className="flex gap-2 mt-2">
            <div className="flex-1">
              <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>강남</div>
              <div className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>₩58M</div>
            </div>
            <div className="flex-1">
              <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>성수</div>
              <div className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>₩42M</div>
            </div>
          </div>
          <div
            className="mt-2 h-1.5 rounded-full overflow-hidden"
            style={{ backgroundColor: 'var(--bg-tertiary)' }}
          >
            <div
              className="h-full"
              style={{ width: '72%', backgroundColor: 'var(--brand-teal)' }}
            />
          </div>
        </div>

        <div
          className="hero-frame absolute bottom-6 left-12 w-[55%] p-4 rounded-xl"
          style={{
            backgroundColor: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            boxShadow: '0 10px 30px -10px rgba(0,0,0,0.15)',
            animationDelay: '5.2s',
          }}
        >
          <div className="text-xs font-semibold mb-1" style={{ color: 'var(--warning)' }}>
            추천 업종 · Top 3
          </div>
          {['카페', '베이커리', '편의점'].map((name, i) => (
            <div key={name} className="flex items-center justify-between text-xs mt-1">
              <span style={{ color: 'var(--text-primary)' }}>
                {i + 1}. {name}
              </span>
              <span style={{ color: 'var(--text-muted)' }}>
                {[92, 84, 78][i]}점
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
