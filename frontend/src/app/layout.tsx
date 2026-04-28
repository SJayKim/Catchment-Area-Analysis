import type { Metadata, Viewport } from 'next';
import { cookies } from 'next/headers';
import './globals.css';

export const metadata: Metadata = {
  title: 'MarketScope AI — 서울 1,650개 상권 분석',
  description:
    '지도 위 상권을 선택하면 유동인구·매출·업종 구성을 한 장의 리포트로 확인합니다. 베타 기간 무료.',
  openGraph: {
    title: 'MarketScope AI',
    description: '서울 1,650개 상권, 데이터로 읽다.',
    type: 'website',
    locale: 'ko_KR',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  userScalable: true,
  maximumScale: 5,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0f172a' },
  ],
};

type ThemePref = 'light' | 'dark' | 'system';

function resolveTheme(raw: string | undefined): ThemePref {
  if (raw === 'light' || raw === 'dark' || raw === 'system') return raw;
  return 'light'; // 한국 B2C 기본값
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const themeCookie = cookies().get('theme')?.value;
  const theme = resolveTheme(themeCookie);
  // 'system' 은 attribute 미지정 → CSS @media (prefers-color-scheme) 가 처리
  const dataThemeAttr = theme === 'system' ? undefined : theme;

  return (
    <html
      lang="ko"
      className="h-full"
      data-theme={dataThemeAttr}
      suppressHydrationWarning
    >
      <head>
        {/* Pretendard Variable — 한글 big-type + variable weight/width
            공식 CDN (jsdelivr) 의 dynamic subset CSS 사용 */}
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css"
        />
      </head>
      <body
        className="h-full"
        style={{
          backgroundColor: 'var(--bg-primary)',
          color: 'var(--text-primary)',
        }}
      >
        {children}
      </body>
    </html>
  );
}
