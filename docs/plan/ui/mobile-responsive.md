# Mobile Responsive Plan

> 작성: 2026-04-23
> 카테고리: `ui`
> 상태: 계획 수립 (구현 전)
> 선행 / 병행: `docs/plan/ui/landing-onboarding-feedback.md` (Phase E 모바일 bottom sheet 일부 중복 — 본 Plan 이 **확장·흡수**)
> 독립 진행 가능: Accuracy Gap Fix W1~W4, Phase 2 Premium 과 무관

---

## Context

### 배경

현재 MarketScope AI 는 **데스크톱 우선 설계**. SplitPanel(30~80% drag) · deck.gl · Recharts · SSE 스트리밍 모두 데스크톱 해상도 기준으로 구현되어 있고, 모바일 방문자는 **UI 깨짐 / 터치 조작 불가** 로 이탈 가능성이 높다. 소상공인·창업 준비 페르소나는 현장(매장·카페)에서 **스마트폰으로 접근하는 비율이 높을 것으로 추정** (정량 트래픽 지표는 Phase 1 관측 대상).

`landing-onboarding-feedback.md` Phase E 에서 모바일 bottom sheet 단 1축을 짧게 다뤘으나, **모바일 대응은 레이아웃 · 제스처 · 키보드 · 성능 · PWA · 접근성 · 오프라인 등 10개 축의 구조적 작업**으로, 별도 Plan 분리가 필요하다.

### 현 구현 갭 (Explore 조사, 2026-04-23)

| # | 항목 | 현 상태 | 판정 | 영향 |
|---|---|---|---|---|
| 1 | viewport meta tag | `app/layout.tsx` 부재 (html lang="ko" 만) | ❌ 없음 | 모바일 초기 스케일 미제어, 확대/축소 깨짐 |
| 2 | Tailwind breakpoint 사용 | 9건 (5파일, `lg:` 중심, 랜딩 컴포넌트) | 🟡 부분 | 앱 본체(`/app`) 는 모바일 분기 없음 |
| 3 | SplitPanel 모바일 분기 | 없음 (`onMouseDown` 만, `onTouchStart` 부재) | ❌ 없음 | 터치 드래그 비동작, 2열 고정 |
| 4 | 터치 이벤트 / `touch-action` | 0건 | ❌ 없음 | 지도 pan 과 외부 스크롤 충돌 |
| 5 | `useIsMobile` · media query 훅 | 0건 | ❌ 없음 | 조건부 UI 렌더 불가 |
| 6 | Bottom sheet / Drawer 컴포넌트 | 0건 (`landing-onboarding-feedback.md` 에만 계획) | ❌ 없음 | 모바일 레이아웃 기반 부재 |
| 7 | ChatInput 가상키보드 대응 (`100dvh`, `VisualViewport`, safe-area) | 0건 | ❌ 없음 | iOS/Android 키보드 노출 시 입력창 가림 |
| 8 | 한글 IME 조합 가드 (`compositionstart/end`) | 0건 | ❌ 없음 | Enter 조합 중 오전송 가능성 |
| 9 | PWA manifest / Service Worker | 없음 (`next-pwa` / `workbox` 미설치) | ❌ 없음 | 홈 설치 · 오프라인 fallback 불가 |
| 10 | `next/image` · `next/font` · AVIF | `next/image` 0건 · 폰트는 `layout.tsx:44~47` CDN link 로만 Pretendard 로드 · `images.formats` 미설정 | 🟡 부분 | 번들 · LCP 최적화 여지 |
| 11 | aria-label · `role="dialog"` | 2건 (RoleSelector · SourcesCitation) · dialog 0건 | 🟡 부분 | WCAG 2.2 + KWCAG 2.2 미달 |
| 12 | Playwright 모바일 device | `playwright.config.ts` chromium 1개 프로젝트만 | ❌ 없음 | 모바일 회귀 0 |

### 2026 모바일 UI/UX 트렌드 리서치 델타 (2026-04-23)

> 10축 리서치 종합. 출처: Google Maps sheets-first (9to5Google) · Airbnb mobile (Mobbin) · ChatGPT/Claude iOS · Naver CLOVA CSR · WCAG 2.5.8 · KWCAG 2.2 · web.dev Core Web Vitals · Workbox stale-while-revalidate · Pretendard GitHub · Toss Design System.

| 축 | 2026 트렌드 | MarketScope 반영 |
|---|---|---|
| M1. PWA vs Native | iOS 26 홈추가 웹앱 기본 · Capacitor = web→native 최단 · RN 완전 이식 비효율 | **Phase 1 = Responsive + PWA manifest** · Phase 2 에 Capacitor wrap 가능성 검토 |
| M2. Map UX | Google Maps **sheets-first 3-snap** (peek/half/full) · Airbnb `map-full-bleed + card peek` · deck.gl inertia | `<768px` 지도 full-bleed + **Vaul-style 3-snap (15/55/90vh)** · 폴리곤 터치 hit-area 2배 |
| M3. Chat/AI UX | ChatGPT/Claude iOS: composer `env(safe-area-inset-bottom)` + `100dvh` · 자동 스크롤은 **사용자 스크롤 중단 시 멈춤** · 진입 vertical chip · 대화 중 horizontal chip · CLOVA Korean STT 최강 | `ChatInput` VirtualKeyboard API + `100dvh` + IntersectionObserver 하단 stick + IME 가드 |
| M4. Navigation | Bottom nav 2~5탭 (한국 B2C = 4탭 + 중앙 primary) · 삼성 Internet PWA 친화 | 모바일 **2-tab bottom nav** (지도 / 챗) · 햄버거 금지 · Phase 2 에 `내 리포트` 탭 |
| M5. Gesture / Haptic | Compound swipe + distinct haptic · View Transitions Baseline · iOS haptic 미완 · pull-to-refresh 보수적 | 시트 snap 전환 `navigator.vibrate(10)` Android only · VT cross-document · pull-to-refresh 금지 |
| M6. Perf Budget | LCP ≤ 2.5s / INP ≤ 200ms / CLS ≤ 0.1 (p75 mobile) · AVIF 95% 지원 · Pretendard Variable subset | Galaxy A35 · throttled 4G 기준 벤치 · AVIF 정적 / WebP 동적 · `next/font/local` Pretendard subset |
| M7. Accessibility | WCAG 2.5.8 AA **24×24 최소** · Material 48dp 권장 · KWCAG 2.2 | 최소 터치 타깃 **44×44px** · 본문 16px · contrast 4.5:1 · axe-core Playwright |
| M8. Input / IME | Native picker 선호 · pg_trgm fuzzy 검색 · 무한 스크롤 지양 | `compositionstart/end` 가드 · 카테고리 chip grid · "더 보기" 페이지네이션 |
| M9. Offline | Workbox SWR 3-tier · SSE 는 NetworkOnly bypass · 지하철 Wi-Fi dropout 대응 | `/api/districts/*` SWR 24h · `/proxy/kakao-sdk` CacheFirst 7d · `/api/chat` SW bypass 필수 |
| M10. Feedback | 카드 👍👎 (Langfuse score) · 카카오 채널 deeplink · sonner toast 1-stack | 기존 `landing-onboarding-feedback.md` Phase C 와 **정합** — 본 Plan 에서는 toast/haptic 통합만 |

### 메모리 참조 교훈

- `feedback_marketscope_sse_format.md` — 모바일에서도 SSE 포맷 불변. PWA Service Worker 가 `/api/chat` 을 가로채면 표준 SSE 버퍼링 재발 → **SW bypass 필수**.
- `feedback_next_public_api_url_frontend_port.md` — PWA 매니페스트 scope 가 `/` 로 바뀌어도 `NEXT_PUBLIC_API_URL` backend 포트(`8002`) 직접 호출 경로는 유지. rewrite 경유 금지.
- `feedback_stale_container_vs_source.md` — 모바일 레이아웃/폰트 변경은 Docker `next standalone` 재빌드 필수. E2E 전 이미지 타임스탬프 확인.
- `feedback_react_event_keys_unique.md` — Bottom sheet 내부 여러 카드 list 렌더 시 key 는 `${card_type}-${trace_id}-${idx}` 복합.
- `feedback_e2e_user_message_pollution.md` — 모바일 E2E 에서 chat textarea 내용이 `body.innerText()` 매처에 노출. 검증 키워드와 분리.
- `feedback_check_env_before_test.md` — USE_MOCK 상태가 모바일 프리뷰 shape 와도 연관. Mock(D3001~D3005) vs Real(1650) 구분 유지.
- `feedback_python_utf8_windows.md` — PWA manifest JSON 스크립트 작성 시 UTF-8 명시.

### 타 Plan 과의 관계

| Plan | 관계 | 조정 |
|---|---|---|
| `landing-onboarding-feedback.md` Phase E5 (MobileBottomSheet.tsx) | **흡수** — 본 Plan 이 3-snap 정식 구현 소유 | 해당 Plan Phase E5 체크박스는 `→ 본 Plan Phase B 참조` 주석만 남김 |
| `landing-onboarding-feedback.md` Phase E (Theme toggle · View Transitions) | **일치** — 본 Plan 은 system preference + cookie 구조 그대로 사용 | 없음 |
| `accuracy-gap-fix.md` W1~W4 | 완전 독립 | 없음 |
| `commercialization-plan.md` (Phase 2 Premium) | **보완** — OAuth2/결제는 모바일 UX 의존도 높음. 본 Plan 완료 후 진행 권장 | Phase 2 UX 착수 전 본 Plan merge |
| `tailwind-v4-oklch-migration.md` (후속) | **선행** — v4 마이그레이션은 본 Plan의 breakpoint/token 안정화 뒤 | 본 Plan v3.4 hex 기반 |

### 전체 원칙

1. **Responsive-first, PWA 최소 구성** — manifest.json + SW (Workbox manual) 만. install prompt, push 미사용 (Phase 2 확장).
2. **Mobile-first Tailwind 문법 유지** — 기존 랜딩 컴포넌트가 `sm: lg:` 혼용 중이나 본 Plan 은 `mobile-first (no prefix) → sm: → md: → lg:` 일관 적용.
3. **단일 코드베이스 유지** — `components/mobile/*` 분리보다는 기존 컴포넌트에 breakpoint 분기 + `useIsMobile` 훅. 중복 렌더 트리 비용 관리.
4. **SSE 무손상** — Workbox `NetworkOnly` 로 `/api/chat` bypass. Service Worker 가 스트리밍을 가로채지 않도록 route matcher 명시.
5. **기존 다크/라이트 CSS 변수 구조 존중** — `landing-onboarding-feedback.md` Phase A3 에서 확정될 `[data-theme]` attribute 구조 그대로 사용.

---

## Scope

### In

- **M1 PWA 최소 구성**: `app/manifest.ts` + Workbox 기반 수동 SW (offline.html + API SWR) — next-pwa 의존 없이 `public/sw.js` + Next.js route
- **M2 모바일 Bottom Sheet**: 3-snap (15vh peek / 55vh half / 90vh full) · 지도 full-bleed · Vaul 라이브러리 선택적 도입 (또는 수제 CSS scroll-snap)
- **M3 ChatInput 모바일 대응**: `100dvh` + `env(safe-area-inset-bottom)` + VirtualKeyboard API + VisualViewport API fallback + 한글 IME `compositionstart/end` 가드
- **M4 Bottom Nav (모바일 전용)**: 2탭 (`지도 탐색` · `챗 분석`) · iOS home indicator safe-area
- **M5 Gesture / Haptic**: sheet snap 전환 시 `navigator.vibrate(10)` (Android) · View Transitions morph · reduced-motion fallback
- **M6 Performance**: viewport meta · Pretendard Variable `next/font/local` 전환 · `images.formats = ['image/avif','image/webp']` · 번들 분석 · deck.gl 모바일 파라미터 튜닝
- **M7 Accessibility**: 최소 44×44px 터치 타깃 유틸 · 본문 16px · aria-label 전수 점검 · `role="dialog"` · axe-core Playwright 통합
- **M8 Input**: IME 가드 · category 선택 bottom sheet chip grid · 상권 검색 드롭다운 상한 8 + "전체 보기"
- **M9 Offline**: Workbox 3-tier (districts SWR · kakao-sdk CacheFirst · chat NetworkOnly bypass) · `/offline.html` fallback · SSE 재연결 UX
- **M10 Feedback 통합**: `sonner` toast 도입 (1-stack) · 카카오 채널 deeplink fallback 확인 (`kakaotalk://channel/...`) · 기존 Phase C 와 연계
- **E2E**: Playwright `iPhone 12` + `Galaxy S21` device project 2종 추가 · 모바일 전용 ring 스펙 다수

### Out

- **Capacitor / React Native wrap**: Phase 2 성공 지표 도달 후 별도 Plan (`docs/plan/infra/capacitor-wrap.md` 가칭)
- **Push Notification**: iOS Safari 제약 + 정책 설계 필요 · Phase 2
- **Naver CLOVA STT 음성 입력**: 백엔드 라우트 + API 키 관리 필요 · Phase 2 에서 `docs/plan/feature/voice-input.md`
- **Install prompt 커스텀 배너**: 자동 `beforeinstallprompt` 감지만 → 사용자 경험 테스트 후 Phase 2
- **Tailwind v4 / OKLCH 재매핑**: 별도 Plan
- **카카오톡 채널 연동 폼 (`/api/feedback` 자체 수집)**: `feedback-self-hosted.md` 2차 Plan
- **Accuracy Gap Fix 관련 UI 변경**: W1~W4 에서 처리

---

## Design

### 1. 레이아웃 전략 (Breakpoint · 진입점)

#### 1.1 Tailwind breakpoint 재정의

```ts
// tailwind.config.ts screens 확장 (override 아님)
screens: {
  'xs': '375px',    // iPhone SE / Galaxy A 소형
  'sm': '640px',    // 기본
  'md': '768px',    // tablet 시작 (본 Plan 의 데스크톱/모바일 분기 기준)
  'lg': '1024px',   // SplitPanel 활성 기준
  'xl': '1280px',
  '2xl': '1536px',
}
```

#### 1.2 Breakpoint 별 `/app` 레이아웃

| 구간 | 레이아웃 | 설명 |
|---|---|---|
| `< 768px` (모바일) | **Map full-bleed + Bottom Sheet + Bottom Nav 2-tab** | 지도는 `100dvw × 100dvh` · sheet snap 15/55/90vh · 하단 nav 고정 56px |
| `768 ~ 1023px` (tablet) | **Fixed SplitPanel 50/50** | drag 비활성 · 지도 왼쪽 50% · 챗 오른쪽 50% · Bottom Nav 숨김 |
| `≥ 1024px` (desktop) | **기존 SplitPanel 30~80% drag** 유지 | 변경 없음 |

#### 1.3 `useIsMobile` 훅

```typescript
// frontend/src/hooks/useBreakpoint.ts 신규
export function useBreakpoint() {
  const [bp, setBp] = useState<'mobile'|'tablet'|'desktop'>('desktop');
  useEffect(() => {
    const mobile = window.matchMedia('(max-width: 767px)');
    const tablet = window.matchMedia('(min-width: 768px) and (max-width: 1023px)');
    const update = () => setBp(mobile.matches ? 'mobile' : tablet.matches ? 'tablet' : 'desktop');
    update();
    mobile.addEventListener('change', update);
    tablet.addEventListener('change', update);
    return () => { mobile.removeEventListener('change', update); tablet.removeEventListener('change', update); };
  }, []);
  return bp;
}
```

SSR 안전: 초기값 `'desktop'` 로 서버 렌더 · 클라이언트 hydration 후 실제 값. 첫 프레임 flash 허용 (기존 dynamic import 패턴과 일치).

#### 1.4 viewport meta

`app/layout.tsx` 에 `export const viewport: Viewport` 추가:

```typescript
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',  // safe-area-inset 활성화
  userScalable: true,     // a11y 위해 zoom 차단 금지 (KWCAG 2.2)
  maximumScale: 5,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#FFFFFF' },
    { media: '(prefers-color-scheme: dark)', color: '#0F172A' },
  ],
};
```

---

### 2. Bottom Sheet (3-snap) · 모바일 핵심

> Google Maps sheets-first 패턴. `landing-onboarding-feedback.md` Phase E 의 2-snap 계획을 **3-snap 으로 확장**하고 본 Plan 에서 정식 구현.

#### 2.1 Snap point 상태 머신

```
┌────────────────────┐
│ peek (15vh, ~120px)│ ← 기본값 (지도 클릭 전에는 hidden)
│ 상권명 + 주요 3지표 │
└─────────┬──────────┘
          │ drag-up / CTA tap
          ▼
┌────────────────────┐
│ half (55vh)        │
│ PreviewCard +      │
│ suggestion chips   │
└─────────┬──────────┘
          │ drag-up / "AI 분석 보기"
          ▼
┌────────────────────┐
│ full (90vh)        │
│ SSE 챗 + 카드 list │
│ + composer        │
└────────────────────┘

drag-down → 이전 snap · 빠른 swipe-down → 2단계 skip
peek 에서 swipe-down → hidden (지도만, 10vh 미세 handle 유지)
```

#### 2.2 구현 선택지

- **옵션 A (채택)**: 수제 — CSS `scroll-snap-type: y mandatory` + `scroll-snap-align: start` 3-section. `IntersectionObserver` 로 snap 감지. 번들 0 추가.
- **옵션 B**: `vaul` (Emil Kowalski) — shadcn drawer-bottom-4 패턴. deps +2KB. 동적 높이 더 자연스러우나 `deck.gl` 터치와 경로 겹칠 때 `body` scroll lock 충돌 가능.

**결정**: 옵션 A. 실 구현에서 제스처 미세 튜닝이 필요하면 B 로 fallback.

#### 2.3 컴포넌트 구조

```
frontend/src/components/mobile/
├── MobileLayout.tsx          # 지도 full-bleed + BottomSheet + BottomNav (모바일 진입점)
├── BottomSheet.tsx           # 3-snap container
├── BottomSheetHandle.tsx     # drag indicator (36×4px) + aria-label
├── BottomNav.tsx             # 2탭 네비 (지도 / 챗)
└── MobileMapControls.tsx     # 기존 MapControls 모바일 버전 (우측 하단, sheet 위로 offset)
```

- `MobileLayout.tsx` 는 `useBreakpoint() === 'mobile'` 일 때만 렌더. `app/app/page.tsx` 에서 분기.
- sheet 내부는 **기존 `ChatPanel` · `PreviewCard` 재사용**, prop 조정만.

#### 2.4 제스처 · Haptic

- 지도 영역: `touch-action: pan-y pinch-zoom` (Kakao Map native gesture 보존)
- Sheet handle: `touch-action: none` (drag 전용)
- Sheet content: `touch-action: pan-y` (내부 스크롤 + snap 드래그 병행)
- Snap 전환 완료 시: `navigator.vibrate?.(10)` (Android 만 실제 피드백, iOS silent fail 안전)
- reduced-motion 시: snap transition duration 0.01ms · vibrate skip

---

### 3. Bottom Nav (모바일 전용)

#### 3.1 2-tab 구조

```
┌───────────────────────────────────────┐
│  [탭 1: 지도]         [탭 2: 챗]      │
│   🗺️ 지도 탐색        💬 분석 대화     │
│   (default)           (badge: N)     │
└───────────────────────────────────────┘
 padding-bottom: max(8px, env(safe-area-inset-bottom))
 height: 56px + safe-area
 z-index: 40 (sheet 30 / fab 50 / modal 60)
```

- **탭 1 (지도)**: sheet 를 peek/hidden 상태로 수축. 지도 조작 집중.
- **탭 2 (챗)**: sheet full(90vh) 로 확장. 기존 대화 히스토리 우선.
- 뱃지: `chatStore.messages` 중 마지막 읽음 이후 신규 메시지 개수 (로컬 상태).

#### 3.2 접근성

- `role="tablist"` + 각 버튼 `role="tab"` · `aria-selected` · `aria-controls`
- 최소 터치 타깃 44×44px · 아이콘 24px + 라벨 12px
- `prefers-reduced-motion` 시 탭 전환 애니메이션 0.01ms

---

### 4. ChatInput 모바일 키보드 대응

#### 4.1 CSS 전략

```css
/* ChatInput 컨테이너 */
.chat-composer {
  position: sticky;
  bottom: 0;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
  /* keyboard 활성 시 자연 들림 (VirtualKeyboard + dvh) */
}

.chat-panel-mobile {
  height: 100dvh;              /* keyboard 감안 동적 vh */
  display: grid;
  grid-template-rows: auto 1fr auto;  /* header / messages / composer */
}
```

#### 4.2 VirtualKeyboard API (progressive enhancement)

```typescript
// app/layout.tsx or ChatInput.tsx
if ('virtualKeyboard' in navigator) {
  (navigator as any).virtualKeyboard.overlaysContent = true;
  // CSS env(keyboard-inset-height) 활성화 (Chrome/Edge)
}
```

미지원 브라우저 (iOS Safari) 는 `VisualViewport` API 로 fallback:

```typescript
window.visualViewport?.addEventListener('resize', () => {
  const delta = window.innerHeight - (window.visualViewport?.height ?? 0);
  document.documentElement.style.setProperty('--kb-inset', `${delta}px`);
});
```

CSS 에서 `--kb-inset` 활용해 composer padding 동적 조정.

#### 4.3 한글 IME 가드

```typescript
// ChatInput.tsx onKeyDown
function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
  if (e.key === 'Enter' && !e.shiftKey) {
    // IME 조합 중 Enter 무시 (한글/일본어/중국어 공통)
    if (e.nativeEvent.isComposing) return;
    e.preventDefault();
    handleSend();
  }
}
```

**주의**: Chrome Android 에서 `isComposing` 이 일부 false positive 보고됨 → 보조적으로 `e.keyCode === 229` 체크 (legacy but widely deployed).

#### 4.4 자동 스크롤 (LibreChat 패턴)

- `MessageList.tsx` 에 `IntersectionObserver` 로 하단 100px 이내 감지 → `isAtBottom` state
- 스트리밍 중 `isAtBottom === true` 인 경우만 `scrollIntoView({behavior: 'smooth'})`
- 사용자가 위로 스크롤 → 자동 스크롤 중단 + 하단 우측에 "↓ 최신 메시지" FAB 노출 (클릭 시 하단 복귀)

---

### 5. PWA 최소 구성

#### 5.1 Manifest (`app/manifest.ts`)

```typescript
import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'MarketScope AI — 서울 상권 분석',
    short_name: 'MarketScope',
    description: '서울시 1,650개 상권을 AI 로 분석하는 지도 기반 서비스',
    start_url: '/',
    display: 'standalone',
    background_color: '#FFFFFF',
    theme_color: '#0B3D91',
    lang: 'ko',
    scope: '/',
    orientation: 'portrait',
    icons: [
      { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
    shortcuts: [
      { name: '지도 탐색', url: '/app?tab=map', icons: [{ src: '/icons/map.png', sizes: '96x96' }] },
      { name: '챗 분석', url: '/app?tab=chat', icons: [{ src: '/icons/chat.png', sizes: '96x96' }] },
    ],
  };
}
```

#### 5.2 Service Worker (Workbox 수동)

```javascript
// public/sw.js — 수동 작성 (next-pwa 도입 없이)
import {registerRoute, NavigationRoute} from 'workbox-routing';
import {StaleWhileRevalidate, CacheFirst, NetworkOnly, NetworkFirst} from 'workbox-strategies';
import {ExpirationPlugin} from 'workbox-expiration';

// 1. API JSON SWR — 24h 최대 100 entries
registerRoute(
  ({url}) => url.pathname.startsWith('/api/districts'),
  new StaleWhileRevalidate({
    cacheName: 'districts-api',
    plugins: [new ExpirationPlugin({maxEntries: 100, maxAgeSeconds: 60*60*24})],
  })
);

// 2. Kakao SDK proxy — 7d
registerRoute(
  ({url}) => url.pathname === '/proxy/kakao-sdk',
  new CacheFirst({cacheName: 'kakao-sdk', plugins: [new ExpirationPlugin({maxEntries: 2, maxAgeSeconds: 60*60*24*7})]})
);

// 3. SSE chat — 반드시 bypass (memory: marketscope_sse_format)
registerRoute(
  ({url}) => url.pathname === '/api/chat',
  new NetworkOnly()
);

// 4. HTML navigation — NetworkFirst + offline fallback
registerRoute(
  new NavigationRoute(
    new NetworkFirst({
      cacheName: 'pages',
      networkTimeoutSeconds: 3,
    })
  )
);

self.addEventListener('install', e => e.waitUntil(caches.open('offline').then(c => c.add('/offline.html'))));
self.addEventListener('fetch', e => {
  // NavigationRoute 실패 시 offline fallback
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(() => caches.match('/offline.html')));
  }
});
```

#### 5.3 SW 등록 (클라이언트)

```typescript
// frontend/src/components/pwa/ServiceWorkerRegister.tsx
'use client';
useEffect(() => {
  if ('serviceWorker' in navigator && process.env.NODE_ENV === 'production') {
    navigator.serviceWorker.register('/sw.js', {scope: '/'});
  }
}, []);
```

`app/layout.tsx` 에 `<ServiceWorkerRegister />` 배치.

#### 5.4 `/offline.html`

- Pretendard 임베드 (inline base64 subset 또는 system-ui fallback)
- 마지막 selected district localStorage 복원 시도 → 프리뷰만 정적 렌더
- "연결 복구 후 다시 시도" CTA

---

### 6. 성능 예산 · 이미지 · 폰트

#### 6.1 Core Web Vitals 예산 (Galaxy A35 + 4G throttling 기준)

| 지표 | 목표 | 도구 |
|---|---|---|
| LCP | ≤ 2.5s | Lighthouse mobile / WebPageTest |
| INP | ≤ 200ms | Chrome DevTools perf · real user monitoring (Phase 2) |
| CLS | ≤ 0.1 | Lighthouse |
| TTFB | ≤ 800ms | prod-smoke 측정 |
| 번들 (initial JS) | ≤ 200KB gzip `/app` 진입 | `next build --profile` + `@next/bundle-analyzer` |

#### 6.2 Pretendard `next/font/local` 전환

현재 `layout.tsx:44~47` 에서 CDN link 사용 → 자체 호스팅 변경:

```typescript
// app/layout.tsx
import localFont from 'next/font/local';

const pretendard = localFont({
  src: '../../public/fonts/PretendardVariable.subset.woff2',
  variable: '--font-pretendard',
  display: 'swap',
  weight: '100 900',
});
```

- Korean subset (`KR` + Latin) 으로 WOFF2 40KB 내외
- `font-display: swap` 으로 FOIT 0 / FOUT 허용
- `preload` 자동 (next/font)

#### 6.3 `next.config.mjs` 이미지 포맷

```javascript
images: {
  formats: ['image/avif', 'image/webp'],
  deviceSizes: [375, 640, 768, 1024, 1280, 1536],
  imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
}
```

랜딩 Hero PNG → AVIF 전환 (Phase A10 대응).

#### 6.4 deck.gl 모바일 파라미터

- `HeatmapLayer.radiusPixels`: 데스크톱 40 → 모바일 30 (INP 개선)
- `GeoJsonLayer.lineWidthMinPixels`: 데스크톱 1 → 모바일 2 (폴리곤 가독성)
- `autoHighlight: true` 모바일 유지 (터치 hover 대체)

---

### 7. 접근성 (WCAG 2.2 AA + KWCAG 2.2)

#### 7.1 터치 타깃

```css
/* globals.css @layer utilities */
.touch-target {
  min-width: 44px;
  min-height: 44px;
}
```

모든 `button`/`a`/`chip` 에 적용. Tailwind utility class 로 정의.

#### 7.2 본문 가독성

- `body { font-size: 16px; line-height: 1.6; }` (기본 유지 확인)
- 카드 내 수치 데이터 14px 허용 · 라벨 12px 허용 · 본문 ≥ 16px
- contrast: light 모드 4.5:1 이상 · dark 모드 그대로

#### 7.3 aria 전수 점검

| 컴포넌트 | 현 상태 | 추가 필요 |
|---|---|---|
| `MapContainer` | 0 | `role="application" aria-label="서울시 상권 지도"` + 키보드 focus outline |
| `BottomSheet` | (신규) | `role="dialog" aria-modal="false" aria-label="상권 정보"` |
| `BottomSheetHandle` | (신규) | `role="slider" aria-valuemin="0" aria-valuemax="2" aria-valuenow="..."` + 키보드 arrow 지원 |
| `BottomNav` | (신규) | `role="tablist"` + 각 `role="tab" aria-selected` |
| `ChatInput` | 0 | `aria-label="메시지 입력"` |
| `Card` 전체 | 0 | `role="article" aria-labelledby="..."` |
| FAB | 0 | `aria-label="피드백 남기기"` |
| 이미지 `<img>` | — | `alt` 필수, 장식은 `alt=""` + `aria-hidden="true"` |

#### 7.4 axe-core 자동 검증

```typescript
// playwright.config.ts projects 에 추가
import {injectAxe, checkA11y} from '@axe-core/playwright';
// spec 내: await injectAxe(page); await checkA11y(page, null, {detailedReport: true});
```

axe 규칙: WCAG 2.2 AA · KWCAG 2.2 (한국어 규칙 미지원 → 기본 axe + 수동 QA 조합).

---

### 8. 상태 관리 · 라우팅

#### 8.1 `chatStore` 확장

```typescript
// stores/chatStore.ts 추가 상태
mobileTab: 'map' | 'chat';      // bottom nav active tab
setMobileTab: (tab) => void;
sheetSnap: 'hidden' | 'peek' | 'half' | 'full';
setSheetSnap: (snap) => void;
unreadCount: number;            // bottom nav badge
```

#### 8.2 URL 파라미터 (모바일 탭 deep link)

- `/app?tab=map` → mobileTab='map' 초기값
- `/app?tab=chat&q=홍대` → chat 탭 + prefill (기존 랜딩 chip 흐름과 호환)

#### 8.3 탭 ↔ Sheet snap 매핑

| tab | 기본 snap | 동작 |
|---|---|---|
| `map` | `hidden` 또는 `peek` (상권 선택 시) | 지도 조작 우선 |
| `chat` | `full` | 챗 인터랙션 우선 |

---

### 9. Offline · 에러 복구

#### 9.1 SSE 재연결 UX

```
SSE disconnect 감지 (fetch reader 중단)
  ↓
Toast: "연결이 불안정해요. 다시 시도할까요?" + [재시도] 버튼
  ↓
재시도 클릭 → session_id 유지한 채 /api/chat POST 재요청
  ↓
마지막 `done` 이벤트 미수신 시 duplicate message 경고 + dedupe
```

#### 9.2 localStorage 키

- `ms_last_district` : 마지막 선택 상권 code + name
- `ms_session_id` : chatStore sessionId 보존 (SW offline 도 session 유지)
- `ms_theme` : 테마 (`landing-onboarding-feedback.md` Phase E15 와 공유)

---

### 10. 테스트 (Playwright 확장)

```typescript
// playwright.config.ts projects 추가
{name: 'mobile-iphone', use: {...devices['iPhone 12']}},
{name: 'mobile-galaxy', use: {...devices['Galaxy S9+']}},   // 2026 이후 S21 device 프로필 추가 예정
{name: 'tablet-ipad', use: {...devices['iPad Pro']}},
```

- 모바일 spec 은 `frontend/e2e/ring2-journeys/j07-mobile-*.spec.ts` 등 신규
- 기존 데스크톱 spec 은 `chromium` project 로만 실행
- axe-core a11y 는 mobile project 에 한정 (데스크톱 회귀는 별도 Phase)

---

## Checklist

### Phase A — Foundation (P0 · 1.5d)

- [ ] A1. `app/layout.tsx` 에 `export const viewport: Viewport` 추가 (`viewport-fit: cover` + `themeColor`)
- [ ] A2. `tailwind.config.ts` screens 확장 (`xs: 375px`) 및 mobile-first 일관 적용 가이드 추가 (JSDoc)
- [ ] A3. `hooks/useBreakpoint.ts` 신규 (SSR 안전, `'desktop'` 초기값)
- [ ] A4. `globals.css` 에 `.touch-target` utility + `env(safe-area-inset-*)` CSS 변수 정의 (`--safe-top`, `--safe-bottom`, `--safe-left`, `--safe-right`)
- [ ] A5. `app/app/page.tsx` 에서 `useBreakpoint()` 로 `MobileLayout` vs 기존 SplitPanel 분기
- [ ] A6. 768~1023px tablet 구간 SplitPanel 50/50 고정 (drag 비활성)
- [ ] A7. `playwright.config.ts` 에 mobile 2종 + tablet 1종 device project 추가

### Phase B — Bottom Sheet + Bottom Nav (P0 · 3d)

- [ ] B1. `components/mobile/BottomSheet.tsx` 신규 — 3-snap (15vh peek / 55vh half / 90vh full) · CSS scroll-snap
- [ ] B2. `components/mobile/BottomSheetHandle.tsx` — drag indicator 36×4px + `role="slider"` + 키보드 arrow 지원
- [ ] B3. `components/mobile/MobileLayout.tsx` — 지도 full-bleed + BottomSheet 통합 컨테이너
- [ ] B4. `components/mobile/BottomNav.tsx` — 2-tab (`지도` / `챗` + 뱃지) · `role="tablist"`
- [ ] B5. `components/mobile/MobileMapControls.tsx` — 기존 `MapControls` 를 상단 우측으로 offset (sheet peek 위)
- [ ] B6. `chatStore` 에 `mobileTab`, `sheetSnap`, `unreadCount`, `setMobileTab`, `setSheetSnap` 상태/액션 추가
- [ ] B7. 지도 폴리곤 클릭 → `setSheetSnap('peek')` 자동 · CTA "AI 분석 보기" → `setSheetSnap('full') + setMobileTab('chat')`
- [ ] B8. `useMapSync` 와 sheet snap 전환 동기 (기존 자동 쿼리 OFF 유지)
- [ ] B9. deck.gl 터치 파라미터 튜닝 — `radiusPixels` 30, `lineWidthMinPixels` 2, `autoHighlight` 유지
- [ ] B10. `navigator.vibrate(10)` snap 전환 haptic (Android 만 효과) · reduced-motion 시 skip
- [ ] B11. `MobileBottomSheet` 에 `role="dialog" aria-modal="false" aria-label="상권 정보"` + focus trap off (탭은 background 와 왕복 허용)
- [ ] B12. `landing-onboarding-feedback.md` Phase E1~E5 의 BottomSheet 체크박스 → 본 Plan 참조 주석으로 교체

### Phase C — ChatInput · IME · 자동 스크롤 (P0 · 2d)

- [ ] C1. `ChatInput.tsx` · `ChatPanel.tsx` 에 `100dvh` + `env(safe-area-inset-bottom)` 적용
- [ ] C2. VirtualKeyboard API 감지 + overlaysContent=true · CSS `env(keyboard-inset-height)` 참조
- [ ] C3. `VisualViewport` API fallback (iOS Safari) · `--kb-inset` CSS 변수 동기
- [ ] C4. IME 가드 — `onKeyDown` 에서 `e.nativeEvent.isComposing` + `e.keyCode === 229` fallback
- [ ] C5. `MessageList.tsx` 에 `IntersectionObserver` 기반 `isAtBottom` state
- [ ] C6. 스트리밍 자동 scroll 은 `isAtBottom === true` 일 때만 `scrollIntoView`
- [ ] C7. "↓ 최신 메시지" FAB — `isAtBottom === false` + 신규 메시지 존재 시 노출 (우하단 · safe-area 준수)
- [ ] C8. `ChatInput` `aria-label="메시지 입력"` + placeholder 최소 16px
- [ ] C9. 기존 `sonner` 유사 toast 컴포넌트 도입 (또는 수제) — 1-stack, `env(safe-area-inset-bottom)` 위

### Phase D — PWA Manifest + Service Worker (P1 · 2d)

- [ ] D1. `app/manifest.ts` 신규 (name / short_name / theme_color / icons / shortcuts)
- [ ] D2. `public/icons/` 에 192 / 512 / maskable 아이콘 3종 생성 (SVG 원본 → PNG 변환 스크립트)
- [ ] D3. `public/sw.js` 수동 작성 — Workbox modules import · 4-tier 라우팅 (districts SWR / kakao-sdk CacheFirst / chat NetworkOnly / nav NetworkFirst+offline fallback)
- [ ] D4. `components/pwa/ServiceWorkerRegister.tsx` 신규 · `app/layout.tsx` 에 mount (production 만)
- [ ] D5. `public/offline.html` 생성 — 마지막 district localStorage 복원 + Pretendard inline subset
- [ ] D6. `package.json` 에 `workbox-routing`, `workbox-strategies`, `workbox-expiration`, `workbox-core` 추가 (runtime dep)
- [ ] D7. SSE bypass 검증 — `/api/chat` 이 SW 를 우회하는지 DevTools Application > Service Workers 로 확인 (memory: `marketscope_sse_format`)
- [ ] D8. `next.config.mjs` `headers()` 에 `/sw.js` 에 대해 `Service-Worker-Allowed: /` + `Cache-Control: no-cache` 명시
- [ ] D9. 개발환경 SW 비활성 가드 (`NODE_ENV !== 'production'` 조건)

### Phase E — 성능 · 이미지 · 폰트 (P1 · 1.5d)

- [ ] E1. Pretendard Variable WOFF2 subset 생성 · `public/fonts/` 배치 · `next/font/local` 전환
- [ ] E2. `layout.tsx` 의 기존 CDN link 제거 (메모리 참조로 인한 FOUT 회귀 주의)
- [ ] E3. `next.config.mjs` `images.formats = ['image/avif', 'image/webp']` + `deviceSizes` 설정
- [ ] E4. 랜딩 Hero PNG → AVIF 전환 (light/dark 2종, `<picture>` + `next/image`)
- [ ] E5. `@next/bundle-analyzer` 설치 + CI artifact — `/app` initial JS gzip ≤ 200KB 확인
- [ ] E6. deck.gl 동적 import 유지 · `ssr: false` · 모바일 파라미터 (`radiusPixels` 30)
- [ ] E7. Lighthouse mobile 자동 측정 CI job (GitHub Actions) — LCP ≤ 2.5s, CLS ≤ 0.1, INP ≤ 200ms (실측 모바일 CPU 4× throttle)
- [ ] E8. `connection: slow-3g` 에뮬레이션 manual QA — 프리뷰 정상 표시 확인

### Phase F — 접근성 · 문서 · E2E (P1 · 2d)

- [ ] F1. `MapContainer` aria-label + 키보드 포커스 outline (Kakao Map wrapper)
- [ ] F2. 5 Card 타입 전수 `role="article" aria-labelledby`
- [ ] F3. FeedbackFab · FeedbackRow (landing plan Phase C) aria-label 추가 (이미 계획됨, 본 Plan 에서 상호 확인)
- [ ] F4. `@axe-core/playwright` 설치 + mobile project 에만 `injectAxe` + `checkA11y` 주입
- [ ] F5. 수동 QA — TalkBack (Galaxy) · VoiceOver (iPhone) 지도 / 카드 / 시트 낭독
- [ ] F6. `docs/architecture/frontend.md` — 모바일 섹션 신규 (BottomSheet · BottomNav · PWA · breakpoint 표)
- [ ] F7. `docs/spec/features/F11-landing.md` · `F12-feedback.md` 에 모바일 동작 추가 기술
- [ ] F8. `docs/spec/feature-list.md` 에 M02 (Mobile Responsive) · M03 (PWA) 신규 행
- [ ] F9. Ring0 `00-stack-up.spec.ts` 확장 — mobile project 에서도 200 OK
- [ ] F10. Ring2 `j07-mobile-first-time.spec.ts` 신규 — 랜딩(모바일) → role chip → /app → sheet peek → half → full → chat 흐름
- [ ] F11. Ring2 `j08-mobile-comparison.spec.ts` 신규 — 상권 2개 비교 (터치로 long-press/double-tap 선택)
- [ ] F12. Ring1 `m02-pwa-manifest.spec.ts` — manifest.json 응답 shape · theme_color · scope
- [ ] F13. Ring1 `m03-offline.spec.ts` — SW 등록 후 network offline → `/offline.html` 렌더
- [ ] F14. Ring3 `neg-mobile-orientation.spec.ts` — landscape 모바일에서도 sheet 동작 확인
- [ ] F15. Ring3 `neg-sse-disconnect.spec.ts` — SSE 중단 시 재시도 toast 노출
- [ ] F16. `docs/status/current-status.md` 에 Phase 완료 + 서비스 지표 (모바일 세션 비중 · PWA 설치율) 항목 추가

---

## 재검토 (Self-Review Gate)

### 엣지케이스

1. **iOS Safari 에서 `100dvh` 버그** — 오래된 iOS 15 이하는 `dvh` 미지원. fallback `min-height: -webkit-fill-available` 병기.
2. **VirtualKeyboard API 미지원** (iOS Safari 전체) — VisualViewport fallback 에서 resize 이벤트가 조합 중 트리거되면 IME 방해. `compositionstart` 동안 resize listener 무시.
3. **Service Worker 가 SSE 를 버퍼링** (memory `marketscope_sse_format`) — `/api/chat` NetworkOnly 강제. 개발환경에서 SW 비활성화 + DevTools 로 수동 검증.
4. **PWA 설치 후 `NEXT_PUBLIC_API_URL`** — 매니페스트 `scope: '/'` 이지만 backend 포트(`8002`) 직접 호출 경로는 CORS 그대로 적용 (memory: `next_public_api_url_frontend_port`).
5. **Kakao Map SDK 가 오프라인에서 로드 실패** — CacheFirst 로 캐싱, 최초 온라인 1회 필수. offline 상태에서 앱 진입 시 지도 대신 "연결 필요" placeholder + 프리뷰만 지원.
6. **Bottom Sheet snap 과 deck.gl pinch-zoom 제스처 충돌** — 지도 영역 `touch-action: pan-y pinch-zoom`, sheet handle `touch-action: none`, sheet content `touch-action: pan-y`. 테스트 기기에서 실기 확인 필수.
7. **한글 IME `keyCode 229` deprecated 경고** — Chrome 은 여전히 동작. 대안 `isComposing` 우선, 229 는 보조 체크로만.
8. **Snap 전환 애니메이션 중 swipe 연속 입력** — 진행 중엔 추가 제스처 무시 (`isTransitioning` flag 500ms).
9. **Bottom Nav 와 FAB (피드백) 공존** — FAB 은 sheet full 상태일 때 `bottom: 120px` (nav 56px + sheet handle 여유). 충돌 시 sheet 내부 우측으로 이동.
10. **iPhone landscape 모드** — `100dvh` 가 매우 낮음. sheet full 이 composer 를 가릴 수 있음. landscape 시 snap full 을 `100dvh` 대신 `95dvh` 로 clamp.
11. **모바일 PDF 다운로드 (F10)** — iOS Safari 는 `blob:` URL 다운로드 대신 새 탭 preview 유도. 경고 toast + Share Sheet 가이드.
12. **Android Chrome 커스텀 탭 (카카오 채널 deeplink)** — `kakaotalk://channel/...` 실패 시 `https://pf.kakao.com/_xxx` fallback.
13. **Pretendard subset 누락 문자** — 특수기호 (☆⚫✨) 가 subset 에서 빠지면 Inter fallback. 랜딩 카피 검토 후 필요 문자 포함.
14. **Accuracy Gap Fix W2 의 conversational query rewriting** — 모바일 컴포저에서 짧게 입력하는 경향 증가 → W2 의 history rewrite 부담 증가 가능. Phase F 완료 후 W2 재측정.
15. **Playwright mobile emulation ≠ 실기기** — emulation 은 resolution·touch 시뮬레이션만. 실기 QA 별도 예약 (Phase F5).

### 메모리 교훈 매칭

| 교훈 | 적용 지점 |
|---|---|
| `feedback_marketscope_sse_format.md` | D3 SW 라우팅 — `/api/chat` NetworkOnly · D7 bypass 수동 검증 |
| `feedback_playwright_sse_capture.md` | F10/F13 — mobile E2E 에서도 SSE 캡처 시 route 가로채기 금지, 직접 backend POST |
| `feedback_react_event_keys_unique.md` | B2 sheet handle · B4 nav tab · C7 `↓ 최신` FAB 모두 instance-level key |
| `feedback_e2e_user_message_pollution.md` | F10/F11 — 모바일 spec 의 user 쿼리와 검증 키워드 분리 |
| `feedback_python_utf8_windows.md` | D3 sw.js 작성 스크립트 UTF-8 명시 |
| `feedback_stale_container_vs_source.md` | F9~F16 모든 mobile E2E 실행 전 frontend/backend 빌드 시각 확인 |
| `feedback_probe_endpoint_shape_first.md` | D1 manifest shape 는 curl + 브라우저 DevTools 로 확정 후 F12 spec |
| `feedback_next_public_api_url_frontend_port.md` | D7 SW scope 와 backend port 공존 확인 |
| `feedback_check_env_before_test.md` | F9 모바일 E2E 도 USE_MOCK 여부 검증 (Mock: D3001~D3005) |

### 타 Plan 과의 충돌

| 충돌 후보 | 평가 |
|---|---|
| `landing-onboarding-feedback.md` Phase E1~E5 (모바일 bottom sheet) | **흡수**. 본 Plan Phase B 가 3-snap 으로 확장 · 해당 Plan 체크박스는 참조로 대체 |
| `landing-onboarding-feedback.md` Phase E6~E10 (View Transitions + reduced-motion) | **일치**. 본 Plan 은 동일 정책 사용 |
| `landing-onboarding-feedback.md` Phase E11~E16 (테마 토글) | **일치**. SSR cookie 기반 초기값 · localStorage 백업 · mobile 에서도 Toolbar 슬롯 |
| `landing-onboarding-feedback.md` Phase C (피드백 3-layer) | **연계**. FAB 위치 모바일 분기 · toast 통합 (sonner) |
| `accuracy-gap-fix.md` W1~W4 | 무관 |
| `commercialization-plan.md` (Phase 2 Premium) | **후속 의존**. 본 Plan 완료 후 OAuth2/결제 모바일 UX 구현 시작 |
| `tailwind-v4-oklch-migration.md` (후속) | **선행**. 본 Plan 의 breakpoint/token 안정화 후 v4 마이그레이션 |
| 후속 `capacitor-wrap.md` (가칭) | **선행**. 본 Plan 의 PWA 구조가 Capacitor wrap 의 전제 |

### 보류/미결 의사결정

- **Vaul 라이브러리 채택 여부** — Phase B1 수제 구현 시도 후, 제스처 부자연스러움 판단되면 Vaul 도입. 결정 시점: Phase B 중간 리뷰.
- **2-tab vs 3-tab Bottom Nav** — 현재 2-tab. `내 리포트` 탭은 Phase 2 상용화 때 즐겨찾기/저장 기능과 함께 도입.
- **Install prompt 자동 배너** — `beforeinstallprompt` 감지 후 커스텀 배너 노출은 Phase 2. Phase 1 은 매니페스트만.
- **SSE 재연결 자동화** — Phase C9 toast + 사용자 재시도 버튼. 완전 자동 재연결은 Phase 2 (network flap 빈도 관측 후).
- **iPad Pro 별도 레이아웃** — 현재 tablet 50/50 고정. 세로 iPad 는 애매할 수 있음. Phase F5 수동 QA 후 재검토.

---

## Scenario (E2E Ring Mapping)

포맷: `<RING>-<FEATURE>-<CASE>` (CLAUDE.md 규약)

### Ring 0 (Preflight)

| ID | 검증 | 파일 |
|---|---|---|
| 0-MOBILE-STACK | `mobile-iphone` + `mobile-galaxy` + `tablet-ipad` 각 device project 에서 `/` 및 `/app` 200 OK + viewport meta 존재 | `00-stack-up.spec.ts` 확장 |
| 0-MANIFEST | `/manifest.webmanifest` (또는 `/manifest.json`) 200 OK + application/manifest+json | 동 |

### Ring 1 (Features)

| ID | 검증 | 파일 |
|---|---|---|
| 1-M02-VIEWPORT | `app/layout.tsx` 가 `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">` 렌더 | `m02-viewport.spec.ts` |
| 1-M02-BREAKPOINT | `useBreakpoint()` mobile/tablet/desktop 3구간 정확 감지 (`window.matchMedia` 모킹) | `m02-breakpoint.spec.ts` |
| 1-M02-SHEET-SNAP | BottomSheet 초기 hidden · 상권 클릭 → peek · drag-up → half → full · drag-down 역순 | `m02-sheet-snap.spec.ts` |
| 1-M02-SHEET-A11Y | handle `role="slider"` + arrow 키 snap 전환 + aria-valuenow 동기 | 동 |
| 1-M02-NAV | BottomNav 2탭 `role="tab"` · aria-selected · tap 전환 시 sheet snap 연동 | `m02-nav.spec.ts` |
| 1-M02-NAV-BADGE | 챗 메시지 수신 시 `지도` 탭 badge 증가 · 탭 활성화 시 0 | 동 |
| 1-M02-IME | Textarea 에 한글 조합 중 Enter → 전송 안 됨 · 조합 완료 후 Enter → 전송 | `m02-ime.spec.ts` |
| 1-M02-KB-INSET | VirtualKeyboard API mock · `--kb-inset` CSS 변수 업데이트 · composer 가림 없음 | `m02-keyboard.spec.ts` |
| 1-M02-AUTO-SCROLL | 스트리밍 중 하단 고정 · 사용자가 위로 스크롤 시 멈춤 · "↓ 최신 메시지" FAB 노출 | `m02-auto-scroll.spec.ts` |
| 1-M03-MANIFEST | `/manifest.webmanifest` shape (name / short_name / theme_color / icons 3종 / shortcuts) | `m03-pwa-manifest.spec.ts` |
| 1-M03-SW-REGISTER | production build 에서 `navigator.serviceWorker.controller` 존재 | `m03-sw-register.spec.ts` |
| 1-M03-SW-BYPASS-SSE | `/api/chat` 요청이 SW 를 우회 (SW fetch handler 에 hit 안 함) | 동 |
| 1-M03-OFFLINE | `context.setOffline(true)` 후 `/app` 재로드 → `/offline.html` 렌더 · 마지막 district 복원 | `m03-offline.spec.ts` |
| 1-M03-SWR | `/api/districts/polygons` 2회 호출 · 2번째는 캐시 hit (서버 요청 로그 기준) | `m03-swr.spec.ts` |
| 1-M02-FONT | Pretendard Variable `next/font/local` 로딩 + `font-display: swap` · CLS ≤ 0.1 | `m02-font.spec.ts` |
| 1-M02-AVIF | Hero 이미지가 AVIF 포맷으로 서빙 (Accept 헤더) | `m02-avif.spec.ts` |

### Ring 2 (Journeys)

| ID | 검증 | 파일 |
|---|---|---|
| 2-J07-FIRST-TIME-MOBILE | iPhone 12 — 랜딩 → role chip → CTA → /app → 지도 pinch-zoom → 상권 탭 → sheet peek → swipe-up half → chip 탭 → SSE 카드 수신 | `j07-mobile-first-time.spec.ts` |
| 2-J08-MOBILE-COMPARISON | Galaxy S9+ — 지도 2개 상권 tap (compare mode) → sheet full 자동 전환 → 비교 카드 수신 | `j08-mobile-comparison.spec.ts` |
| 2-J09-MOBILE-FEEDBACK | 카드 footer 👍 탭 → Langfuse score POST · FAB 탭 → 카카오 deeplink 시도 | `j09-mobile-feedback.spec.ts` |
| 2-J10-MOBILE-PWA | manifest 감지 → 홈화면 추가 (emulated) → 전체화면 standalone → 정상 동작 | `j10-mobile-pwa.spec.ts` |
| 2-J11-MOBILE-OFFLINE | 온라인 1회 방문 → 오프라인 전환 → 재방문 시 offline.html + 마지막 district 프리뷰 복원 | `j11-mobile-offline.spec.ts` |

### Ring 3 (Negative)

| ID | 검증 | 파일 |
|---|---|---|
| 3-NEG-MOBILE-LANDSCAPE | iPhone 12 landscape (844×390) → sheet full snap `95dvh` clamp · composer 가시 | `neg-mobile-orientation.spec.ts` |
| 3-NEG-SSE-DISCONNECT | 스트리밍 중 network offline 강제 → toast "연결 불안정" + 재시도 버튼 · dedupe 동작 | `neg-sse-disconnect.spec.ts` |
| 3-NEG-SW-DEV-DISABLED | `NODE_ENV !== production` 환경에서 SW 등록 skip (`navigator.serviceWorker.controller === null`) | `neg-sw-dev.spec.ts` |
| 3-NEG-IOS-DVH-FALLBACK | userAgent iOS 15 emulate → `100dvh` 대신 `-webkit-fill-available` fallback 적용 | `neg-ios-dvh.spec.ts` |
| 3-NEG-KAKAO-DEEPLINK-FAIL | `kakaotalk://` scheme 실패 시 `https://pf.kakao.com/_xxx` fallback | `neg-kakao-fallback.spec.ts` |
| 3-NEG-TOUCH-CONFLICT | 지도 pan 과 sheet drag 동시 터치 → 지도 우선 (handle 제외) | `neg-touch-conflict.spec.ts` |
| 3-NEG-A11Y-AXE | axe-core WCAG 2.2 AA 위반 0건 (mobile project 전체) | `neg-axe-audit.spec.ts` |

---

## Pass 반복

### Pass 1 — 기본 동작 (해피패스)

- [ ] Pass 1-A (Foundation): Ring0-MOBILE-STACK + Ring1 VIEWPORT/BREAKPOINT 전체 PASS
- [ ] Pass 1-B (Sheet + Nav): Ring1 SHEET-SNAP / SHEET-A11Y / NAV / NAV-BADGE + Ring2 J07 PASS
- [ ] Pass 1-C (Chat/IME): Ring1 IME / KB-INSET / AUTO-SCROLL + Ring2 J08 PASS
- [ ] Pass 1-D (PWA): Ring0 MANIFEST + Ring1 M03-MANIFEST / SW-REGISTER / SW-BYPASS-SSE / OFFLINE / SWR + Ring2 J10, J11 PASS
- [ ] Pass 1-E (Perf): Ring1 FONT / AVIF + Lighthouse mobile LCP ≤ 2.5s · CLS ≤ 0.1
- [ ] Pass 1-F (A11y): Ring3 NEG-A11Y-AXE + TalkBack/VoiceOver 수동 QA

Fail → 수정 → `docker compose build frontend` → 재실행.

### Pass 2 — 엣지

- [ ] Pass 2-EDGE-1: iPhone 12 landscape · sheet full clamp (Ring3 NEG-MOBILE-LANDSCAPE)
- [ ] Pass 2-EDGE-2: SSE disconnect 복구 toast · dedupe (Ring3 NEG-SSE-DISCONNECT)
- [ ] Pass 2-EDGE-3: iOS 15 UA · `-webkit-fill-available` fallback (Ring3 NEG-IOS-DVH-FALLBACK)
- [ ] Pass 2-EDGE-4: 카카오 deeplink 실패 fallback (Ring3 NEG-KAKAO-DEEPLINK-FAIL)
- [ ] Pass 2-EDGE-5: 지도 pan 과 sheet drag 충돌 (Ring3 NEG-TOUCH-CONFLICT)
- [ ] Pass 2-EDGE-6: SW dev 환경 비활성 (Ring3 NEG-SW-DEV-DISABLED)
- [ ] Pass 2-EDGE-7: `prefers-reduced-motion: reduce` — sheet snap transition 0.01ms · haptic skip
- [ ] Pass 2-EDGE-8: `prefers-color-scheme: dark` system 설정 시 테마 자동 dark · 라이트 토글 cookie 우선
- [ ] Pass 2-EDGE-9: 3G throttle (400kbps) 에서 Pretendard subset 로딩 후 FOIT 없음 · CLS ≤ 0.15 허용
- [ ] Pass 2-EDGE-10: Samsung Internet (Chromium 기반) 에서 PWA install prompt 동작
- [ ] Pass 2-EDGE-11: Kakao Map SDK 오프라인 시 placeholder 렌더

Fail → 수정 → Pass 1 회귀 재실행 포함.

### Pass 3 — 성능

- [ ] Pass 3-PERF-1: Galaxy A35 + 4G throttle — LCP ≤ 2.5s / INP ≤ 200ms / CLS ≤ 0.1 (Lighthouse mobile)
- [ ] Pass 3-PERF-2: `/app` 진입 initial JS gzip ≤ 200KB (bundle-analyzer artifact)
- [ ] Pass 3-PERF-3: 지도 pan/zoom 60fps 유지 (Chrome DevTools Performance trace · iPhone 12 emulation)
- [ ] Pass 3-PERF-4: Bottom sheet snap 전환 60fps · JS blocking ≤ 50ms
- [ ] Pass 3-PERF-5: SSE 첫 `thinking` 이벤트 수신 ≤ 1.5s (기존 TTFT 1.5s 유지, 모바일에서 회귀 없음)
- [ ] Pass 3-PERF-6: Pretendard WOFF2 ≤ 50KB · preload · `font-display: swap`
- [ ] Pass 3-PERF-7: deck.gl HeatmapLayer 24 슬롯 프리로드 모바일에서 5s 내 완료
- [ ] Pass 3-PERF-8: Service Worker 등록 · 첫 캐시 warmup 이 initial LCP 에 영향 없음 (`install` 이벤트가 main thread block 안 함)

Fail → 최적화 (subset 추가 · dynamic import 세분화 · deck.gl 파라미터 튜닝) → Pass 2 회귀.

---

## Agent 모델 선택

CLAUDE.md Plan 규약.

| 단계 | 추천 서브에이전트 | 모델 | 이유 |
|---|---|---|---|
| 설계 · 라이브러리 선택 (Vaul vs 수제) · a11y 정책 | 주 대화 (Claude Opus) | opus | 트레이드오프 판단 |
| BottomSheet/BottomNav 컴포넌트 구현 | `frontend-specialist` (or sonnet 직접) | sonnet | React JSX · CSS scroll-snap · 훅 |
| Service Worker + Workbox 라우팅 | sonnet 직접 | sonnet | 코드 작성 집중도 |
| Pretendard subset / AVIF 변환 스크립트 | sonnet 직접 | sonnet | 일회성 유틸 |
| E2E spec 작성/실행 | `qa-scenario-runner` | haiku | Playwright 결과 대량 출력 격리 |
| Lighthouse / axe 자동 검증 CI | `qa-scenario-runner` 또는 별도 shell | haiku | 반복 실행 |
| DB/Repository 영향 (Service Worker 가 백엔드 라우팅 오해 가능) 검증 | `db-validator` | haiku | alembic head · USE_MOCK 확인 |
| 코드 리뷰 (React key · SSE bypass · a11y) | `code-reviewer` | haiku | ruff/React/SSE 기계 점검 |

---

## Validation

### 완료 조건 (Definition of Done)

1. ✅ Ring 0/1/2/3 전체 신규 · 회귀 spec PASS (Mock + Real 양쪽, desktop + mobile-iphone + mobile-galaxy + tablet-ipad 4 project)
2. ✅ 모든 모바일 진입점에서 UI 깨짐 0건 (iPhone 12 · Galaxy S9+ · iPad Pro 수동 QA · landscape 포함)
3. ✅ Lighthouse mobile: LCP ≤ 2.5s / INP ≤ 200ms / CLS ≤ 0.1 / TTFB ≤ 800ms (Galaxy A35 + 4G throttling)
4. ✅ axe-core WCAG 2.2 AA 위반 0건 (mobile project) + TalkBack/VoiceOver 수동 낭독 통과
5. ✅ PWA: manifest 유효 · 홈 추가 가능 · 오프라인 fallback 동작 · SW `/api/chat` bypass 확인
6. ✅ `/app` initial JS gzip ≤ 200KB (bundle-analyzer)
7. ✅ `docs/architecture/frontend.md` · `docs/spec/feature-list.md` · `docs/status/current-status.md` 갱신
8. ✅ 기존 데스크톱 사양 회귀 0 (Ring 0~3 desktop 포함 전체 green)
9. ✅ 메모리 신규 기록 (예: `feedback_mobile_touch_conflict.md` · `feedback_sw_bypass_sse.md`) — 작업 중 학습 보존
10. ✅ `landing-onboarding-feedback.md` Phase E5 의 BottomSheet 체크박스 → 본 Plan 참조로 마이그레이션 완료

### 운영 지표 (Phase 완료 후 2주 관찰)

- 모바일 세션 비중 (GA4 · 목표 30%+, 현재 추정 불명)
- 모바일 bounce rate (랜딩 · 목표 ≤ 50%)
- Sheet full snap 도달률 (mobile 세션 중 %, 목표 40%+)
- PWA 설치율 (beforeinstallprompt accept, Phase 2 지표)
- 모바일 `/api/chat` 성공률 (SSE 정상 완료 · 목표 95%+)
- SW cache hit rate (`/api/districts` · 목표 60%+)
- 모바일 LCP p75 (RUM · 목표 ≤ 2.5s)
- TalkBack/VoiceOver 사용자 피드백 수집량 (카카오 채널 · 최소 1건)

---

## Metadata

- **작성자**: sjkim (Claude Opus 4.7 보조)
- **작성일**: 2026-04-23
- **소요 추정**:
  - Phase A 1.5d + Phase B 3d + Phase C 2d + Phase D 2d + Phase E 1.5d + Phase F 2d = **약 2~2.5주**
  - Vaul 도입 결정 시 B 단계 +0.5d
  - 실기기 수동 QA (TalkBack/VoiceOver/landscape) +0.5d
- **선행 의존**:
  - `landing-onboarding-feedback.md` Phase A (라우팅 분리 `/app`) 완료 권장 — 본 Plan 의 `/app` 진입점 전제
  - Phase A3 (`[data-theme]` attribute 구조) 완료 시 본 Plan 테마 연동 단순화
- **후속 Plan**:
  - `docs/plan/ui/tailwind-v4-oklch-migration.md` — 본 Plan 안정화 후 v4 + OKLCH 로 팔레트 재매핑
  - `docs/plan/infra/capacitor-wrap.md` (가칭) — 본 Plan PWA 구조 위에서 Capacitor 네이티브 wrap
  - `docs/plan/feature/voice-input.md` (가칭) — Naver CLOVA STT 통합
  - `docs/plan/ui/feedback-self-hosted.md` — 카카오 채널 → 자체 `/api/feedback` 이관 시 모바일 연동
- **Ring 회귀 영향**: Ring0~3 에 mobile/tablet project 3종 추가 (실행 시간 약 3배 증가 · CI 순차 예산 ≤ 30분)
- **Rollback 전략**:
  - Phase A (viewport/breakpoint): git revert 단위
  - Phase B (Sheet + Nav): feature flag `NEXT_PUBLIC_ENABLE_MOBILE_LAYOUT=false` → 기존 SplitPanel 강제 (임시 대응)
  - Phase C (ChatInput): IME 가드는 안전 (desktop 영향 없음) · `100dvh` 는 v3.4 fallback 유지
  - Phase D (PWA/SW): `public/sw.js` 제거 + `navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => r.unregister()))` 스크립트로 기기별 해제
  - Phase E (폰트/이미지): Pretendard CDN link 로 revert 가능 (F2 작업 전 브랜치 보존)
  - Phase F (a11y/E2E): 기존 spec 회귀 없음, device project 제거로 원상복귀
- **참고 (2026 모바일 트렌드 리서치 출처)**:
  - Google Maps sheets-first redesign (9to5Google · Android Police 2025)
  - Airbnb mobile map screen (Mobbin)
  - deck.gl Interactivity docs · HeatmapLayer 모바일 파라미터
  - OpenAI Apps SDK UI guidelines · LibreChat auto-scroll discussion
  - MDN VirtualKeyboard API · VisualViewport API · View Transition API
  - Workbox strategies · web.dev Stale-While-Revalidate
  - Naver Cloud CLOVA Speech Recognition
  - WCAG 2.5.8 Target Size · KWCAG 2.2 · Material Design 48dp
  - web.dev Core Web Vitals · corewebvitals.io 2026
  - Pretendard GitHub (dynamic subset) · Toss Design System mobile
  - LG Uplus RootMetrics 2026 (Korea 5G)
  - Mobiloud PWAs on iOS 2026 · PkgPulse RN vs Capacitor 2026
  - shadcn Drawer Bottom with Vaul
