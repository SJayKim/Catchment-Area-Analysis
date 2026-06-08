# 앱인토스(Apps in Toss) 미니앱 배포 계획

## Context

MarketScope (Next.js 14 App Router + FastAPI) 를 토스 슈퍼앱 안에 미니앱으로 노출해 3,000만 유저 reach 확보가 목표. 앱인토스 공식 가이드(WebView 미니앱) 제약:

- **SSR 금지** — CSR/SSG 정적 빌드만 허용. `.ait` 번들에 `dist/web/index.html` 필수.
- **외부 URL 리다이렉트 금지** — 정적 산출물이 번들에 직접 포함되어야 함.
- 외부 API 호출(FastAPI) 자체는 가능하나 SSE 60초 스트리밍은 검수팀 사전 확인 권장.

현재 `frontend/` 의 SSR 의존 3개(`output: 'standalone'` / `rewrites()` / `app/layout.tsx::cookies()` / `app/proxy/kakao-sdk/route.ts`) 가 차단 요인. 사용자 선택: **별도 트랙(`apps-in-toss` git branch + `frontend-mini/` 디렉토리)** 으로 분기해 기존 웹 운영(`marketscope.robitlabs.co.kr`) 회귀 없이 미니앱 전용 CSR 빌드만 따로 관리.

## Scope

### In Scope
- `frontend-mini/` 신규 디렉토리 — 기존 `frontend/` 복제 후 SSR 제거 + 정적 export 전환
- 백엔드는 **기존 프로덕션 그대로 재사용** (FastAPI on `marketscope.robitlabs.co.kr`, 별도 인프라 변경 없음)
- 미니앱 WebView 안에서 동작하는 모든 기능: 지도(F01) · 챗(F02) · 카드(F03/05/07/09) · 히트맵(F06) · 피드백(F12) · 프리뷰(F13)
- 앱인토스 콘솔 입점 신청 + `.ait` 번들 제출까지

### Out of Scope
- F10 PDF 리포트 — html2canvas + @react-pdf/renderer 가 WebView 안에서 파일 저장 동작 제한적, 1차 출시 보류 (이슈 등록만)
- 기존 웹 prod 코드 수정 — `frontend/`, `server/`, `docker-compose.prod.yml` 변경 없음
- Phase 2 (OAuth/결제/Tier 게이팅) — 미니앱 출시와 무관
- 토스 SDK 결제·인증 연동 — 1차 무료 베타로 출시

## Design

### 1. 디렉토리 / 브랜치 전략

```
Catchment-Area-Analysis/         (main branch — 기존 운영)
├── frontend/                   ← 변경 없음
├── server/                     ← 변경 없음
└── ...

apps-in-toss branch:
├── frontend-mini/              ← 신규 (frontend/ 에서 시작)
│   ├── next.config.mjs         ← output: 'export', rewrites() 제거
│   ├── src/app/
│   │   ├── layout.tsx          ← cookies() 제거, localStorage 테마 hydration
│   │   ├── proxy/              ← 디렉토리 삭제 (Route Handler 금지)
│   │   └── ...
│   ├── src/lib/kakaoSdkLoader.ts  ← 신규 (클라이언트 직접 로드)
│   ├── .env.production         ← NEXT_PUBLIC_API_URL=https://marketscope.robitlabs.co.kr/api
│   └── scripts/build-ait.sh    ← out/ → dist/web/ → .ait 번들
└── docs/plan/infra/apps-in-toss-deploy.md  ← 본 plan 의 상시 버전
```

### 2. 핵심 변경점 (3 블로커 해소)

#### 2-1. `frontend-mini/next.config.mjs`
```mjs
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,            // 정적 호스팅 호환
  env: {
    NEXT_PUBLIC_KAKAO_MAP_KEY: process.env.NEXT_PUBLIC_KAKAO_MAP_KEY || '',
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '',
  },
  // rewrites() 제거 — 정적 export 미지원
};
```

#### 2-2. `frontend-mini/src/app/layout.tsx` (cookies() 제거)
- `cookies()` import 삭제
- `data-theme` 속성은 inline `<script>` 로 SSR 없이 localStorage 읽어 첫 paint 전에 set:
  ```tsx
  <head>
    <script dangerouslySetInnerHTML={{ __html:
      `try{var t=localStorage.getItem('theme')||'light';
       if(t!=='system')document.documentElement.setAttribute('data-theme',t);}catch(e){}`
    }} />
  </head>
  ```
- 기존 `frontend/src/app/globals.css` 의 `[data-theme='light'|'dark']` 팔레트 그대로 활용 (재사용)

#### 2-3. Kakao SDK 클라이언트 직접 로드 (Route Handler 제거)
- `frontend-mini/src/app/proxy/` 디렉토리 전체 삭제
- 신규 `frontend-mini/src/lib/kakaoSdkLoader.ts`:
  ```ts
  export function loadKakaoSdk(appKey: string): Promise<void> {
    return new Promise((res, rej) => {
      if ((window as any).kakao?.maps) return res();
      const s = document.createElement('script');
      s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${appKey}&autoload=false`;
      s.onload = () => (window as any).kakao.maps.load(() => res());
      s.onerror = rej;
      document.head.appendChild(s);
    });
  }
  ```
- `frontend-mini/src/components/map/MapContainer.tsx` 수정 — 기존 `/proxy/kakao-sdk` fetch 제거, `loadKakaoSdk()` 호출
- **Kakao 개발자 콘솔 작업** (사용자가 수동): "Web 도메인" 에 앱인토스 WebView origin 등록 (검수팀 확인 필요 — 일반적으로 `https://apps-in-toss.toss.im` 또는 미니앱별 sandbox origin)

### 3. 환경변수 / API 호출

| 변수 | 값 | 비고 |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://marketscope.robitlabs.co.kr/api` | 빌드 타임 bake. 기존 prod 백엔드 재사용 |
| `NEXT_PUBLIC_KAKAO_MAP_KEY` | (기존 prod 키 재사용) | Kakao 콘솔 도메인 화이트리스트만 추가 |

- `frontend-mini/src/lib/api.ts` 의 localhost fallback (`http://localhost:8002/api`) 은 production 빌드에서 도달 불가하도록 build script 에서 검증 (`scripts/build-ait.sh` 가 `grep -r 'localhost' out/` 0건 확인).

### 4. WebView 호환성 확인 사항

| 항목 | 리스크 | 대응 |
|---|---|---|
| SSE 60s 스트리밍 (`/api/chat`) | iOS WKWebView foreground 안정 / background suspend 시 끊김 | `chatStore.ts::sendMessage` 의 `AbortController` + 자동 재시도 그대로 활용. 검수팀에 사전 문의 |
| `deck.gl` WebGL (히트맵) | 구형 기기 WebGL 미지원 시 hide | `HeatmapLayer` mount 전 `canvas.getContext('webgl')` 체크 + fallback toast |
| `visualViewport` (`useKeyboardInset`) | WebView IME inset 차이 | 기존 훅 재사용, mobile-iphone E2E 로 회귀 |
| `localStorage` (Safari Private) | 이미 `feedback_*` memory 에 케이스 있음 (A1-EDGE-PRIVATE) | try/catch 가드 그대로 |

### 5. `.ait` 번들 생성

`frontend-mini/scripts/build-ait.sh`:
1. `npm ci`
2. `next build` → `out/` 디렉토리 (정적 산출물)
3. `mv out dist/web`
4. `dist/web/index.html` 존재 확인 (필수)
5. `grep -r 'localhost\|127.0.0.1' dist/web/` 0건 확인 (가드)
6. 앱인토스 SDK CLI 로 `.ait` 패키징 — 개발자센터 가이드 정확한 명령어 사전 조사 필요

### 6. 입점 절차 (콘솔 작업)

1. 앱인토스 콘솔(https://apps-in-toss.toss.im) 파트너 가입
2. 미니앱 등록 — 카테고리: "비즈니스/생활" (상권 분석은 비금융이라 금융 인증 불필요 가정 → 검수팀 사전 확인 필수)
3. `.ait` 번들 업로드 + 메타데이터 (앱명, 아이콘, 스크린샷 5장)
4. 사전검토 요청 (커뮤니티 글 `/t/topic/3188` 참고)
5. 정식 심사 (운영/디자인/기능/보안)
6. 베타 출시 (오픈 베타 전환)

## Checklist + 재검토 + Scenario + Pass 반복 + Agent 모델 선택

### Checklist (원자 항목)

**Phase 0 — 사전 조사 (사용자/심사팀 확인)**
- [ ] 앱인토스 검수팀에 사전 문의: (1) SSE 60s 스트림 허용, (2) 상권분석(비금융) 카테고리 입점 가능, (3) WebView origin 도메인 확정값
- [ ] Kakao 개발자 콘솔에서 WebView origin 화이트리스트 등록 가능 여부 확인
- [ ] 앱인토스 SDK CLI 정확한 패키징 명령 + `.ait` 스펙 확인 (개발자센터 문서)

**Phase 1 — 코드 트랙 분기**
- [ ] `git checkout -b apps-in-toss`
- [ ] `cp -r frontend/ frontend-mini/` 후 `frontend-mini/package.json::name` → `marketscope-mini`
- [ ] `.gitignore` 에 `frontend-mini/out`, `frontend-mini/dist` 추가

**Phase 2 — SSR 제거**
- [ ] `frontend-mini/next.config.mjs` — `output:'export'` + `images.unoptimized` + `trailingSlash:true`, `rewrites()` 삭제
- [ ] `frontend-mini/src/app/layout.tsx` — `cookies()` 제거, inline theme hydration `<script>` 삽입
- [ ] `frontend-mini/src/app/proxy/` 디렉토리 삭제
- [ ] `frontend-mini/src/lib/kakaoSdkLoader.ts` 신규
- [ ] `frontend-mini/src/components/map/MapContainer.tsx` — `/proxy/kakao-sdk` fetch 코드 → `loadKakaoSdk()` 호출로 교체
- [ ] `frontend-mini/.env.production` — `NEXT_PUBLIC_API_URL=https://marketscope.robitlabs.co.kr/api`

**Phase 3 — 정적 export 검증**
- [ ] `cd frontend-mini && npm ci && npm run build`
- [ ] `out/` 또는 `dist/web/` 산출물 확인 (`index.html`, `_next/` 정적 자산)
- [ ] `npx serve out/` 로 로컬 부팅 → 챗/지도/히트맵/피드백 수동 smoke
- [ ] `grep -r 'localhost' out/` 0건 확인

**Phase 4 — WebView 환경 테스트**
- [ ] 앱인토스 sandbox 앱 다운로드 (iOS/Android)
- [ ] 로컬 dev 서버 (`out/`) sandbox 에서 로드 → 6 시나리오 smoke:
  - F01 폴리곤 클릭 + 프리뷰
  - F02 챗 SSE 스트림 60s 유지
  - F05 비교 모드 (다색)
  - F06 히트맵 (WebGL)
  - F12 피드백 mood + 모달
  - F13 프리뷰 카드 → 풀 분석 진입
- [ ] iOS Safari Private 모드 localStorage 가드 (A1-EDGE-PRIVATE) 회귀
- [ ] mobile-iphone viewport 에서 BottomNav (D9-WCAG258) 회귀

**Phase 5 — `.ait` 번들 + 입점**
- [ ] `scripts/build-ait.sh` 작성 + 실행
- [ ] 앱인토스 콘솔 미니앱 등록 + 메타데이터 입력
- [ ] 사전검토 요청 → 피드백 반영
- [ ] 정식 심사 제출
- [ ] 오픈 베타 전환 후 prod-smoke 회귀 (외부 도메인 smoke 와 별도로 미니앱 sandbox smoke)

### 재검토 (Self-Review Gate)

- **엣지 케이스**:
  - Kakao SDK 도메인 화이트리스트 등록 실패 → 지도 자체가 안 뜸 (가장 큰 리스크). Phase 0 사전 확인 필수
  - SSE 60s 검수 반려 → 챗을 짧은 polling 으로 fallback 하는 Phase 2.5 옵션 보유
  - F10 PDF — WebView 에서 파일 다운로드 트리거 제한 → 1차 출시 hide
- **메모리 교훈 인용**:
  - `feedback_next_public_api_url_frontend_port.md` — `NEXT_PUBLIC_API_URL` build-time bake-in, 런타임 override 불가 → `.env.production` 필수
  - `feedback_marketscope_sse_format.md` — type 임베드 SSE 포맷, sandbox 테스트 시 표준 SSE 파서 금지
  - `feedback_react_event_keys_unique.md` — 카드 다회 호출 duplicate-key (이미 fix 됨, 회귀 가드 유지)
  - `feedback_check_env_before_test.md` — USE_MOCK 환경 미지정 시 D3001/3120189 불일치, 미니앱은 prod 백엔드라 USE_MOCK=false 고정
- **타 Plan 충돌**:
  - 진행 중 `phase1-low-mid-risk-2026-04-23.md` (Refactoring Pass 2) — `chatStore.ts` 분할 작업과 머지 후 `frontend-mini/` 재동기화 절차 필요. 본 plan 은 Pass 2 머지 **후** 시작 권장
  - Phase 2 (OAuth/결제) Plan 들 — 미니앱 출시는 무관, 평행 진행 가능

### Scenario (E2E Ring Mapping)

| Ring | 시나리오 ID | 매핑 | 검증 |
|---|---|---|---|
| 0 | `R0-MINI-BUILD` | `out/index.html` + `_next/` 정적 자산 확인 | `ls out/index.html` |
| 0 | `R0-MINI-NO-LEAK` | `grep -r 'localhost\|127.0.0.1' out/` | exit 1 (0건) |
| 1 | `R1-MINI-F01-MAP` | 폴리곤 클릭 + 프리뷰 카드 | sandbox 수동 smoke |
| 1 | `R1-MINI-F02-SSE` | 챗 60s 스트림 + done.trace_id | sandbox 수동 smoke |
| 1 | `R1-MINI-F06-HEAT` | deck.gl WebGL 렌더 | sandbox 수동 smoke |
| 1 | `R1-MINI-F12-FB` | mood + 피드백 모달 + Tally fallback | sandbox 수동 smoke |
| 2 | `R2-MINI-J01` | 온보딩→피드백 통합 journey (j06 변형) | sandbox 수동 smoke |
| 3 | `R3-MINI-NEG-WEBGL` | WebGL 미지원 fallback | DevTools `--disable-webgl` |
| 3 | `R3-MINI-NEG-OFFLINE` | API 도달 불가 시 에러 boundary | sandbox airplane 모드 |

### Pass 반복

- **Pass 1 (기본)**: 정적 export 빌드 + 로컬 `npx serve` 6 기능 수동 smoke. FAIL 시 SSR 잔여 의존 추적
- **Pass 2 (엣지)**: 앱인토스 sandbox 에서 iOS WKWebView + Android WebView 실기기 6 기능 + 2 negative 시나리오. FAIL 시 WebView-specific 차이 (cookie, localStorage, fetch keepalive) 분석
- **Pass 3 (성능)**: TTFT 5s 이내, 챗 60s SSE drop 0건, 히트맵 16ms frame budget. 검수팀 권장 INP 기준 확인 후 적용

### Agent 모델 선택

- **설계 (Plan)**: Opus 4.7 — 본 plan 작성 (현재)
- **구현 (Implementation)**: Sonnet 4.6 — `frontend-mini/` 분기 + SSR 제거 + Kakao loader 작성
- **검증 (QA)**: Haiku 4.5 — 정적 산출물 grep 가드, sandbox smoke 시나리오 체크리스트 실행

## Validation (E2E 검증 방법)

```bash
# 1) 정적 export 빌드
cd frontend-mini
npm ci
NEXT_PUBLIC_API_URL=https://marketscope.robitlabs.co.kr/api \
NEXT_PUBLIC_KAKAO_MAP_KEY=<prod_key> \
npm run build

# 2) Phase 3 가드
test -f out/index.html || { echo "FAIL: no index.html"; exit 1; }
! grep -rn 'localhost\|127.0.0.1' out/ || { echo "FAIL: localhost leaked"; exit 1; }

# 3) 로컬 정적 호스팅 smoke
npx serve out -p 4173
# → http://localhost:4173 에서 F01/F02/F06/F12/F13 수동 smoke

# 4) 앱인토스 sandbox 연결 (개발자센터 가이드 따라)
#    sandbox 앱 → 로컬 IP:4173 로드 → 같은 Wi-Fi 필수

# 5) .ait 패키징 (CLI 명령은 Phase 0 에서 확인 후 확정)
bash scripts/build-ait.sh
# → marketscope-mini-v0.1.0.ait

# 6) 콘솔 업로드 → 사전검토 → 심사
```

## Metadata

| Field | Value |
|---|---|
| Plan ID | apps-in-toss-deploy |
| Owner | sjkim |
| Branch | `apps-in-toss` (신규) |
| Depends on | Refactoring Pass 2 머지 권장 (`phase1-low-mid-risk-2026-04-23.md`) |
| Risk | **High** — Kakao 도메인 화이트리스트 + SSE 검수 통과 여부가 외부 의존 |
| 예상 작업량 | Phase 0~3 = 1~2일, Phase 4 sandbox = 2~3일, Phase 5 심사 대기 = 1~2주 |
| Memory 인용 | `feedback_next_public_api_url_frontend_port.md`, `feedback_marketscope_sse_format.md`, `feedback_react_event_keys_unique.md`, `feedback_check_env_before_test.md` |
| 참고 자료 | https://developers-apps-in-toss.toss.im/intro/overview.html · https://techchat-apps-in-toss.toss.im/t/next-js-ssr-webview/3263 |
