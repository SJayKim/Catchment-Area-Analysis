# frontend/ — MarketScope AI 프론트엔드

Next.js 14 (App Router, TypeScript) 단일 페이지 — 지도 · 챗 · 카드 UI 3개 서브시스템.
상세 아키텍처: [../docs/architecture/frontend.md](../docs/architecture/frontend.md).

## 빌드 & 테스트

```bash
npm install
npm run dev                 # port 3000
npx tsc --noEmit            # 타입체크
npm run lint                # next lint
npm run test:e2e            # Playwright E2E (전체)
npm run test:e2e:ring0      # ~ring3 링별 실행
```

> ⚠ **`npm test` 스크립트는 없다** — E2E 는 반드시 `npm run test:e2e`.
> Playwright 4 project (chromium / mobile-iphone / mobile-galaxy / tablet-ipad), base URL `E2E_BASE_URL || http://localhost:3001`.

## 자주 틀리는 것 (gotcha)

- **SSE 포맷**: 백엔드는 `event:` 라인 없이 `data: {json}` 안에 `type` 을 임베드한다. 표준 SSE 파서 쓰지 말 것 — `lib/sseParser.ts`(async generator) + `lib/eventHandlers.ts` 사용. `SSEEvent` 유니온 10종(`error` 포함).
- **`NEXT_PUBLIC_API_URL`**: chat SSE 는 Next rewrite 를 우회하고 backend 포트(:8000)로 직접 호출해야 버퍼링이 없다. frontend 포트(:3000) 금지. build-time bake-in 이라 변경 시 재빌드 필요.
- **`NEXT_PUBLIC_KAKAO_MAP_KEY`**: docker build args 도 호스트 셸 env 를 읽는다 — e2e frontend 재빌드 전 `export` 필수(아니면 dummy 키 bake 로 지도 사망).
- **React 이벤트 key**: `tool-${name}` 류 type-only id 는 동일 도구 다회 호출 시 duplicate-key 경고 — 인스턴스별 unique id 사용.
- **TS optional chaining 숫자 비교**: `obj?.prop >= N` 은 strict TS2532 → `(obj?.prop ?? 0) >= N`.
- **Playwright**: `./node_modules/.bin/playwright` 직접 호출 (npx 는 글로벌 캐시 빈 config 실행 함정). SSE 는 `page.route` 가로채기 금지(버퍼링 타임아웃) — 직접 backend POST.

## 구조 요약

- **Zustand 4 스토어**: `chat` / `district` / `map` / `toast` (`window.__*Store` 디버그 노출).
- **라우트**: `/`(랜딩 F11) · `/app`(분석) · `/privacy` · `/terms` · `/proxy/kakao-sdk`. route 별 `error.tsx` + `loading.tsx`.
- **Card 5종**: summary / compare / recommend / risk / simulation (`components/chat/cards/registry.ts`).
