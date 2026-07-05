# B01. 수익 모델 (Freemium) Spec

> Free로 사용자 유입 → Premium 전환으로 수익화

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| 모델 | Freemium (무료 기본 + 유료 프리미엄) |
| 무료 목적 | 사용자 유입 + 서비스 가치 체험 |
| 유료 목적 | 심층 분석 기능으로 전환 유도 |
| 타겟 고객 | 소상공인 예비 창업자, 부동산/상가 중개인 |
| 상태 | **Phase 2 미착수** — 현재 모든 기능이 Free 로 접근 가능. OAuth2 / 결제 / Tier 게이팅 미구현. |
| 로드맵 | [../../plan/business/commercialization-plan.md](../../plan/business/commercialization-plan.md) 참조 — Stage 1(검증) → Stage 2(Public Launch, M3~M4) 에서 인증/결제 구현 |

## 2. Tier 구분

> ⚠ 정합 주의 (2026-07-04): 현재 프런트 Tier 스텁(`frontend/src/hooks/useTier.ts`)은 `Tier = 'free' | 'pro' | 'team'` **3단** placeholder 타입을 정의한다 (하드코딩 `'free'` 반환, `FeatureGate` 도 동일 타입 사용). 본 문서의 Free/Premium **2단** 구조(§5.2 `users.tier` `'free' | 'premium'` 포함)와 명칭·단수가 다르므로, Phase 2 게이팅 구현 시 한쪽으로 확정해 정합시켜야 한다.

### 2.1 Free Tier

| 항목 | 제한 |
|------|------|
| 지도 상권 탐색 (F01) | 무제한 |
| AI 챗봇 질의 (F02) | **일 5회** |
| 기본 리포트 (F03) | 무제한 (캐싱된 데이터) |
| 그 외 기능 | 접근 불가 (업그레이드 유도 UI) |

**Free 제공 이유**: 기본 리포트만으로도 "이 상권이 어떤 곳인지" 파악 가능 → 가치를 체험하고 심층 분석 니즈가 생기면 전환.

### 2.2 Premium Tier

| 항목 | 내용 |
|------|------|
| AI 챗봇 질의 | **무제한** |
| 업종 심층 분석 (F04) | O |
| 상권 비교 (F05) | O |
| 업종 추천 (F07) | O |
| 점포 이력/리스크 (F08) | O |
| 시간대별 히트맵 (F06) | O |
| 매출 시뮬레이션 (F09) | O |
| PDF 리포트 저장 (F10) | O |

## 3. 가격 정책 (안)

| 플랜 | 가격 | 비고 |
|------|------|------|
| Free | 0원 | 기본 리포트 + 일 5회 챗봇 |
| Premium 월간 | 9,900원/월 | 전체 기능 |
| Premium 연간 | 99,000원/년 (월 8,250원) | 17% 할인 |

**가격 근거**:
- 경쟁 서비스(오픈업, 소상공인365)가 무료 → 가격 민감도 높음
- 한 번 창업 의사결정에 수십~수억 투자 → 월 1만원은 낮은 허들
- LLM API 비용 (Claude) 사용자당 월 ~2,000~5,000원 예상 → 마진 확보 가능

## 4. 전환 유도 전략

### 4.1 Soft Paywall

Free 사용자가 Premium 기능에 접근할 때:
```
┌────────────────────────────────────────────┐
│ 🔒 업종 심층 분석은 Premium 기능입니다       │
│                                            │
│ 이 상권에 "카페"를 열면 어떨지              │
│ 경쟁 현황, 예상 매출, 리스크까지            │
│ AI가 심층 분석해드립니다.                   │
│                                            │
│ [Premium 시작하기 — 월 9,900원]             │
│ [7일 무료 체험]                             │
└────────────────────────────────────────────┘
```

### 4.2 전환 트리거 포인트

| 시점 | 유도 방식 |
|------|-----------|
| 기본 리포트 확인 후 | 추천 질문 칩에 Premium 기능 포함 ("카페 분석해줘" → Premium 안내) |
| 일 5회 챗봇 소진 시 | "오늘 질문 횟수를 모두 사용했습니다. Premium으로 무제한 분석하세요" |
| 상권 비교 시도 시 | 미리보기(블러 처리) + 업그레이드 유도 |
| PDF 다운로드 시도 시 | "리포트 저장은 Premium 기능입니다" |

### 4.3 무료 체험

- 가입 후 **7일간 Premium 전체 기능** 제공
- 체험 종료 전 D-3, D-1 알림
- 결제 정보 미등록 시에도 체험 가능 (전환율 vs 진입장벽 트레이드오프)

## 5. 기술 구현

### 5.1 인증

| 항목 | 방식 |
|------|------|
| 인증 방식 | OAuth2 (Google, Kakao) |
| 세션 관리 | JWT (access + refresh token) |
| 미인증 사용자 | Free tier 동일 (세션 기반, 일 5회) |

### 5.2 DB 스키마

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100),
    provider VARCHAR(20) NOT NULL,       -- 'google' | 'kakao'
    provider_id VARCHAR(255) NOT NULL,
    tier VARCHAR(20) DEFAULT 'free',     -- 'free' | 'premium'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    plan VARCHAR(20) NOT NULL,           -- 'monthly' | 'yearly'
    status VARCHAR(20) NOT NULL,         -- 'active' | 'trial' | 'expired' | 'cancelled'
    trial_ends_at TIMESTAMPTZ,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    payment_key VARCHAR(255),            -- Toss Payments 결제 키
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE usage_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(100),             -- 미인증 사용자용
    action VARCHAR(50) NOT NULL,         -- 'chat_query' | 'report_view' | ...
    date DATE DEFAULT CURRENT_DATE,
    count INT DEFAULT 1
);

CREATE INDEX idx_usage_daily ON usage_logs(user_id, action, date);
```

### 5.3 Tier 미들웨어 (`server/middleware/tier_gate.py`)

```python
from fastapi import Request, HTTPException

PREMIUM_FEATURES = {"F04", "F05", "F06", "F07", "F08", "F09", "F10"}
FREE_DAILY_CHAT_LIMIT = 5

async def check_tier(request: Request, feature_id: str):
    """Free/Premium 접근 제어"""
    user = request.state.user  # None이면 미인증

    if feature_id in PREMIUM_FEATURES:
        if not user or user.tier != "premium":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PREMIUM_REQUIRED",
                    "feature": feature_id,
                    "message": "Premium 구독이 필요한 기능입니다"
                }
            )

async def check_chat_limit(request: Request):
    """Free 사용자 일일 챗봇 횟수 제한"""
    user = request.state.user
    if user and user.tier == "premium":
        return  # 무제한

    today_count = await get_daily_chat_count(user or request.state.session_id)
    if today_count >= FREE_DAILY_CHAT_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "DAILY_LIMIT_EXCEEDED",
                "limit": FREE_DAILY_CHAT_LIMIT,
                "message": "오늘 무료 질문 횟수를 모두 사용했습니다"
            }
        )
```

### 5.4 결제 연동

| 항목 | 방식 |
|------|------|
| PG사 | Toss Payments (또는 PortOne) |
| 결제 수단 | 카드, 간편결제 (카카오페이, 네이버페이) |
| 정기결제 | 빌링키 발급 → 월/연 자동 결제 |
| 해지 | 현 결제 주기 끝까지 Premium 유지 후 Free 전환 |

## 6. 수익 시뮬레이션 (참고)

| 지표 | 보수적 | 낙관적 |
|------|--------|--------|
| 월 방문자 (MAU) | 5,000 | 30,000 |
| Free→Premium 전환율 | 2% | 5% |
| Premium 구독자 | 100명 | 1,500명 |
| 월 매출 (9,900원 기준) | 99만원 | 1,485만원 |
| LLM 비용 (사용자당 ~3,000원) | 30만원 | 450만원 |
| 인프라 비용 | 20만원 | 100만원 |
| **월 순이익** | **49만원** | **935만원** |

## 7. 수용 기준

- [ ] 미인증 사용자도 Free tier로 서비스 이용 가능
- [ ] OAuth2 로그인 (Google, Kakao) 동작
- [ ] Free 사용자 일 5회 챗봇 제한이 정확히 동작
- [ ] Premium 기능 접근 시 Soft Paywall UI 표시
- [ ] 7일 무료 체험 → 만료 후 Free 전환
- [ ] Toss Payments 정기결제 동작
- [ ] 해지 시 현 주기 끝까지 Premium 유지

---

*작성일: 2026-03-25*
