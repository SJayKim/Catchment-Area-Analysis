# F12 — 피드백 3-layer

> 카드별 👍👎 · 무료 한도 microsurvey · FAB(카카오 1순위) 3 레이어.
> 2026-04-23 Plan `docs/plan/ui/landing-onboarding-feedback.md` §6.

## 1. 레이어 개요

| 레이어 | 컴포넌트 | 위치 | 데이터 경로 | DB 변경 |
|---|---|---|---|---|
| L1 | `FeedbackRow` | MessageList 꼬리 (`lastTraceId` 존재 시) | `POST /api/feedback/score` → Langfuse `score` API | ❌ |
| L2 | `FreeLimitSurvey` | Modal (messageCount ≥ 5) | GA4 `dataLayer.push('free_limit_survey', ...)` | ❌ |
| L3 | `FeedbackFab` | 우하단 fixed (랜딩 + 앱 공통) | `NEXT_PUBLIC_KAKAO_CHANNEL_URL` > `NEXT_PUBLIC_FEEDBACK_FORM_URL` > 숨김 | ❌ |

## 2. L1 — 카드별 👍👎

**데이터 모델**: trace 단위. 동일 `trace_id` 에 대한 중복 제출은:

- 클라이언트: `chatStore.feedbackByTrace[trace_id]` 세션 map 으로 1회 제한
- 클라이언트 debounce: 500ms 내 연속 클릭 첫 1회만 발송
- 서버: 24h Redis key `feedback:seen:{trace_id}` 로 idempotency. 2번째부터 HTTP 204

**스키마** (`POST /api/feedback/score`):

```json
{
  "trace_id": "...",
  "value": "up" | "down",
  "reason": "부정확함 | 느림 | 주제 벗어남 | null (max 32자)",
  "comment": "optional, max 120자"
}
```

> 서버 검증 (`api/routes/feedback.py::FeedbackScoreRequest`): `trace_id` 1~128자 · `value` `^(up|down)$` · `reason` max 32자 · `comment` max 120자.

**응답**:

| HTTP | 조건 |
|---|---|
| 202 | Langfuse 활성 + 정상 전송 |
| 204 | Langfuse off · 동일 trace 중복 · 외부 오류 (모두 silent drop) |

Langfuse numeric 매핑: `up=+1.0`, `down=-1.0`. `reason` + `comment` 는 ` | ` joiner 로
Langfuse score `comment` 필드에 전달.

**trace_id 출처**: SSE `done` 이벤트의 `trace_id` 필드 → `lib/eventHandlers.ts` →
`chatStore.lastTraceId`.

## 3. L2 — 무료 한도 microsurvey

**트리거**: `chatStore.messageCount >= DAILY_FREE_LIMIT` (`/app/page.tsx` 상수, 5).
**게이팅**: Phase 2 (상용화) 결합 예정. 현재는 UI 전용.

**상한**: 쿠키 `ms_survey_week_<YYYY WW>` 1주 만료 + dismiss 시 즉시 기록.

**UI**:

1. 문항 1 (필수): `"방금 받은 분석, 얼마나 도움이 됐나요?"` → 5-emoji (😡😞😐🙂😍)
2. 문항 2 (선택): **`NEXT_PUBLIC_PREMIUM_CTA_ENABLED === 'true'`(빌드 타임 env, 기본 off — Phase E.3) 이고** 문항 1 ≥ 4 응답 시만 `"Premium 요금(월 ₩9,900)에 관심 있으신가요?"` 네/아니오/나중에. 기본 환경(env 미설정)에서는 문항 2 미노출.

**수집**: `window.dataLayer.push({event:'free_limit_survey', mood, premium_interest})`.
GA4 차단 환경에서도 UI 는 성공 상태로 마감 (ACK 불필요).

## 4. L3 — FAB (랜딩/앱 공통)

**우선순위**:

1. `NEXT_PUBLIC_KAKAO_CHANNEL_URL` → 카카오톡 채널 1:1 문의 (신탭)
2. `NEXT_PUBLIC_FEEDBACK_FORM_URL` → Tally iframe 모달 (`FeedbackModal.tsx`, ESC 닫기)
3. 둘 다 부재 → **FAB 숨김** (dev 오노출 방지)

**배치**: `fixed bottom-right z-40`. 모바일에서 ChatInput 과 겹치지 않도록 Phase E 에서
bottom-sheet drag handle 옆으로 이동 예정.

**Footer 이중 노출**: `Footer.tsx` 에 동일 URL 링크. FAB 숨김 환경 또는 PDF 인쇄 view 를 위한
정적 경로.

## 5. 환경 변수

```bash
NEXT_PUBLIC_KAKAO_CHANNEL_URL=https://pf.kakao.com/_xxxxx/chat
NEXT_PUBLIC_FEEDBACK_FORM_URL=https://tally.so/r/xxxxx
NEXT_PUBLIC_PREMIUM_CTA_ENABLED=false   # L2 문항 2 (Premium CTA) 게이트 — 'true' 일 때만 노출 (기본 off)
```

빌드 타임 bake-in — 변경 시 frontend 재빌드 필수.

## 6. 스팸 가드 체크리스트

- [x] 클라이언트 debounce 500ms
- [x] 세션 `feedbackByTrace` dedup
- [x] 서버 24h Redis `feedback:seen:{trace_id}` idempotency
- [x] Langfuse score API failure → HTTP 204 silent (UX 영향 0)
- [x] Modal 단일 인스턴스 (body `overflow:hidden` lock)

## 7. E2E 시나리오 (Plan Ring1 F12)

- `1-F12-FAB-KAKAO` — KAKAO URL 설정 → FAB 클릭 시 `window.open` 해당 URL
- `1-F12-FAB-TALLY-FALLBACK` — KAKAO 미설정 + TALLY 설정 → iframe modal 열림
- `1-F12-CARD-THUMBS` — SummaryCard 하단 👍 → `/api/feedback/score` POST + 동일 trace 재클릭 시 ack
- `1-F12-SURVEY` — `FreeLimitSurvey` 강제 노출 → 5-emoji + dataLayer push
- `3-NEG-FEEDBACK-URL-MISSING` — 둘 다 부재 → FAB 숨김
- `3-NEG-CARD-SPAM` — 동일 trace 3회 → 2·3 번째 204 or 무반응

## 8. 2차 Plan (자체 구현 이관)

L1 Langfuse → `/api/feedback` 자체 테이블 + Alembic 004 이관은 별도 Plan
`docs/plan/ui/feedback-self-hosted.md` (미작성) 에서.
