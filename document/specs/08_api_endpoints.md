# 08. API 엔드포인트 명세서

## 목차
1. [API 아키텍처](#1-api-아키텍처)
2. [엔드포인트 명세](#2-엔드포인트-명세)
3. [WebSocket / SSE 프로토콜](#3-websocket--sse-프로토콜)
4. [에러 응답 형식](#4-에러-응답-형식)
5. [미들웨어 스택](#5-미들웨어-스택)
6. [Celery 태스크 통합](#6-celery-태스크-통합)

---

## 1. API 아키텍처

### 1.1 FastAPI 앱 구조

```
backend/
├── main.py                    # FastAPI 앱 진입점, 라우터 등록
├── core/
│   ├── config.py              # 환경 변수 및 설정 (pydantic-settings)
│   ├── security.py            # JWT 생성/검증, OAuth2 헬퍼
│   ├── dependencies.py        # Depends() 공통 의존성
│   └── exceptions.py          # 커스텀 예외 클래스
├── middleware/
│   ├── cors.py                # CORS 설정
│   ├── rate_limit.py          # 티어별 요율 제한
│   ├── auth.py                # 인증 미들웨어
│   ├── logging.py             # 요청/응답 로깅 + Langfuse 연동
│   └── error_handler.py       # 전역 예외 핸들러
├── routers/
│   ├── analysis.py            # /api/v1/analysis/*
│   ├── chat.py                # /api/v1/chat/*
│   ├── auth.py                # /api/v1/auth/*
│   ├── user.py                # /api/v1/user/*
│   └── data.py                # /api/v1/districts/*, /api/v1/industries, /api/v1/map/*
├── schemas/
│   ├── analysis.py            # 분석 관련 Pydantic 모델
│   ├── chat.py                # 채팅 관련 모델
│   ├── auth.py                # 인증 관련 모델
│   ├── user.py                # 사용자 관련 모델
│   └── common.py              # 공통 응답 모델, 페이지네이션
├── services/
│   ├── analysis_service.py    # 분석 비즈니스 로직
│   ├── chat_service.py        # 채팅 비즈니스 로직
│   ├── auth_service.py        # 인증/OAuth 로직
│   └── user_service.py        # 사용자 관련 로직
├── tasks/
│   ├── celery_app.py          # Celery 앱 설정
│   ├── analysis_task.py       # 분석 실행 태스크
│   └── callbacks.py           # 태스크 완료 콜백
└── db/
    ├── session.py             # SQLAlchemy async 세션
    ├── models.py              # ORM 모델
    └── repositories/          # 데이터 접근 계층
```

### 1.2 앱 초기화 (`main.py`)

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작: DB 풀, Redis 연결, Langfuse 초기화
    await init_db_pool()
    await init_redis()
    init_langfuse()
    yield
    # 종료: 리소스 정리
    await close_db_pool()
    await close_redis()

app = FastAPI(
    title="MarketScope AI API",
    version="1.0.0",
    description="AI 기반 상권 분석 플랫폼 API",
    lifespan=lifespan,
)

# 미들웨어 등록 (역순으로 실행됨)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(CORSMiddleware, **cors_settings)

# 라우터 등록
app.include_router(auth_router, prefix="/api/v1/auth", tags=["인증"])
app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["분석"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["채팅"])
app.include_router(user_router, prefix="/api/v1/user", tags=["사용자"])
app.include_router(data_router, prefix="/api/v1", tags=["데이터"])
```

### 1.3 인증 시스템

#### JWT 토큰 구조

| 항목 | Access Token | Refresh Token |
|------|-------------|---------------|
| 만료 시간 | 30분 | 7일 |
| 저장 위치 | Authorization 헤더 | HttpOnly 쿠키 |
| 페이로드 | `{ sub, email, tier, exp, iat }` | `{ sub, token_family, exp, iat }` |
| 알고리즘 | RS256 | RS256 |

```python
# JWT 페이로드 스키마
class AccessTokenPayload(BaseModel):
    sub: str                  # user_id (UUID)
    email: str
    tier: Literal["free", "starter", "pro"]
    exp: int                  # Unix timestamp
    iat: int

class RefreshTokenPayload(BaseModel):
    sub: str                  # user_id (UUID)
    token_family: str         # 토큰 재사용 감지용 패밀리 ID
    exp: int
    iat: int
```

#### 토큰 갱신 플로우

```
1. 클라이언트: Access Token 만료 감지 (401 응답)
2. 클라이언트: POST /api/v1/auth/refresh (Refresh Token 쿠키 자동 전송)
3. 서버: Refresh Token 검증 → 새 Access Token + Refresh Token 발급
4. 서버: 기존 Refresh Token 무효화 (Rotation)
5. 클라이언트: 새 Access Token으로 원래 요청 재시도
```

#### OAuth2 제공자

**Google OAuth2:**
```
인증 URL: https://accounts.google.com/o/oauth2/v2/auth
토큰 URL: https://oauth2.googleapis.com/token
스코프: openid, email, profile
콜백 URL: {BASE_URL}/api/v1/auth/callback/google
```

**Kakao OAuth2:**
```
인증 URL: https://kauth.kakao.com/oauth/authorize
토큰 URL: https://kauth.kakao.com/oauth/token
스코프: profile_nickname, account_email
콜백 URL: {BASE_URL}/api/v1/auth/callback/kakao
```

### 1.4 요율 제한 (Rate Limiting)

Redis 기반 슬라이딩 윈도우 카운터를 사용하며, **월간 분석 요청 횟수**를 기준으로 제한한다.

| 티어 | 월간 분석 횟수 | API 호출 제한 (분당) | 동시 분석 수 |
|------|--------------|-------------------|------------|
| Free | 3회 | 30 req/min | 1 |
| Starter | 20회 | 60 req/min | 2 |
| Pro | 무제한 | 120 req/min | 5 |

```python
# Redis 키 패턴
rate_limit_key = f"rate:{user_id}:analysis:monthly:{year}-{month}"
api_rate_key = f"rate:{user_id}:api:minute:{timestamp_minute}"
```

제한 초과 시 응답 헤더:
```
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1712016000    # Unix timestamp (월초 리셋 시각)
Retry-After: 2592000             # 초 단위 (제한 초과 시만)
```

---

## 2. 엔드포인트 명세

### 2.1 분석 엔드포인트 (Analysis)

---

#### `POST /api/v1/analysis` - 새 분석 요청 생성

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |
| 최소 티어 | Free |
| 요율 제한 | 티어별 월간 분석 횟수 차감 |

**Request Body:**
```python
class LocationInput(BaseModel):
    address: Optional[str] = None           # "서울시 강남구 역삼동 123-45"
    lat: Optional[float] = None             # 37.4979
    lng: Optional[float] = None             # 127.0276
    radius_m: Optional[int] = Field(500, ge=100, le=2000)  # 분석 반경 (미터)

    @model_validator(mode="after")
    def check_location(self):
        if not self.address and (self.lat is None or self.lng is None):
            raise ValueError("address 또는 lat/lng 좌표가 필요합니다")
        return self

class AnalysisCreateRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500,
                       description="분석 질의 (예: '강남역 근처 카페 창업 분석')")
    location: Optional[LocationInput] = None
    industry: Optional[str] = Field(None, description="업종 코드 (예: 'Q12041')")
    depth: Literal["quick", "standard", "deep"] = Field(
        "standard",
        description="분석 깊이 - quick: 3분/주요지표, standard: 7분/전체분석, deep: 15분/심층분석"
    )
```

**Response (202 Accepted):**
```python
class AnalysisCreateResponse(BaseModel):
    request_id: str                         # UUID v4
    status: Literal["queued"]
    estimated_duration_sec: int             # quick=180, standard=420, deep=900
    stream_url: str                         # "/api/v1/analysis/{request_id}/stream"
    created_at: datetime

# 예시 응답
{
    "request_id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "status": "queued",
    "estimated_duration_sec": 420,
    "stream_url": "/api/v1/analysis/a1b2c3d4-5678-90ab-cdef-1234567890ab/stream",
    "created_at": "2026-03-19T10:30:00Z"
}
```

---

#### `GET /api/v1/analysis/{request_id}` - 분석 결과 조회

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |
| 최소 티어 | Free |
| 참고 | 본인의 분석만 조회 가능 |

**Path Parameter:**
- `request_id` (str, UUID) - 분석 요청 ID

**Response (200 OK):**
```python
class AgentOutput(BaseModel):
    agent_name: str                         # "commercial_area", "population", ...
    status: Literal["pending", "running", "completed", "failed"]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_sec: Optional[float]
    result: Optional[dict]                  # 에이전트별 분석 결과 (아래 상세)
    confidence_score: Optional[float]       # 0.0 ~ 1.0
    sources: Optional[list[str]]            # 참조한 데이터 출처

class DebateRound(BaseModel):
    round_number: int
    challenger: str                         # 에이전트 이름
    target: str                             # 대상 에이전트 이름
    challenge_point: str                    # 이의 제기 내용
    response: str                           # 반박 내용
    resolution: str                         # 합의 결과
    score_adjustment: Optional[dict]        # 점수 조정 내역

class AnalysisResult(BaseModel):
    request_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    query: str
    location: LocationInput
    industry: Optional[str]
    depth: str

    # 종합 결과
    overall_score: Optional[float]          # 0 ~ 100
    overall_grade: Optional[str]            # "A+", "A", "B+", ...
    executive_summary: Optional[str]        # 3~5문장 핵심 요약
    key_insights: Optional[list[str]]       # 핵심 인사이트 목록
    recommendation: Optional[str]           # 최종 추천 의견

    # 에이전트별 결과
    agent_outputs: list[AgentOutput]

    # 교차 검증 결과
    debate_rounds: Optional[list[DebateRound]]
    debate_summary: Optional[str]

    # 메타데이터
    created_at: datetime
    completed_at: Optional[datetime]
    total_duration_sec: Optional[float]
    token_usage: Optional[dict]             # { prompt_tokens, completion_tokens, total_cost }

# 에이전트별 result 필드 상세 구조

# 1) 상권 분석 에이전트 (commercial_area)
class CommercialAreaResult(BaseModel):
    district_name: str                      # 상권 명칭
    district_type: str                      # "골목상권", "발달상권", "전통시장", "관광특구"
    boundary_geojson: dict                  # 상권 경계 GeoJSON
    total_stores: int                       # 전체 점포 수
    category_breakdown: dict[str, int]      # 업종별 점포 수
    vacancy_rate: float                     # 공실률 (%)
    avg_rent_per_sqm: Optional[float]       # 평당 평균 임대료 (만원)
    nearby_districts: list[dict]            # 인접 상권 정보

# 2) 유동인구 분석 에이전트 (population)
class PopulationResult(BaseModel):
    daily_average: int                      # 일 평균 유동인구
    hourly_distribution: dict[str, int]     # 시간대별 유동인구 { "09": 1200, ... }
    day_of_week: dict[str, int]             # 요일별 { "MON": 15000, ... }
    age_distribution: dict[str, float]      # 연령대별 비율 { "20s": 0.35, ... }
    gender_ratio: dict[str, float]          # 성별 비율 { "male": 0.48, "female": 0.52 }
    trend_6m: list[dict]                    # 최근 6개월 추이
    peak_hours: list[str]                   # 피크 시간대
    residential_vs_floating: dict           # 거주인구 vs 유동인구 비율

# 3) 경쟁 분석 에이전트 (competition)
class CompetitionResult(BaseModel):
    total_competitors: int                  # 동일 업종 경쟁 점포 수
    competitors: list[dict]                 # 상위 경쟁업체 목록 (이름, 위치, 평점, 리뷰 수)
    saturation_index: float                 # 포화도 지수 (0~1, 높을수록 과포화)
    avg_competitor_rating: float            # 경쟁업체 평균 평점
    entry_exit_trend: dict                  # 개폐업 추이 { "openings_6m": 5, "closings_6m": 3 }
    market_share_estimate: float            # 예상 시장 점유율
    differentiation_opportunities: list[str]  # 차별화 기회 포인트

# 4) 매출 분석 에이전트 (revenue)
class RevenueResult(BaseModel):
    estimated_monthly_revenue: int          # 예상 월 매출 (만원)
    revenue_range: dict[str, int]           # { "min": 2000, "max": 5000 }
    seasonal_pattern: dict[str, float]      # 월별 매출 계수 { "01": 0.85, ... }
    avg_transaction_amount: int             # 평균 객단가
    daily_transaction_count: int            # 일 평균 거래 건수
    revenue_trend_6m: list[dict]            # 6개월 매출 추이
    benchmark_comparison: dict              # 동일 업종 평균 대비

# 5) 리스크 분석 에이전트 (risk)
class RiskResult(BaseModel):
    overall_risk_score: float               # 종합 리스크 점수 (0~100)
    risk_factors: list[dict]                # [{ name, score, impact, probability, description }]
    risk_matrix: list[dict]                 # 리스크 매트릭스 데이터 (산점도용)
    mitigations: list[dict]                 # [{ risk, strategy, effectiveness }]
    regulatory_risks: list[str]             # 규제 리스크 항목
    market_cycle_position: str              # "성장기", "성숙기", "쇠퇴기"

# 6) 재무 시뮬레이션 에이전트 (financial)
class FinancialResult(BaseModel):
    scenarios: dict[str, dict]              # { "optimistic": {...}, "base": {...}, "pessimistic": {...} }
    initial_investment: dict                # { 보증금, 인테리어, 장비, 기타 }
    monthly_costs: dict                     # { 임대료, 인건비, 재료비, 공과금, 기타 }
    break_even_months: dict[str, int]       # 시나리오별 손익분기점 (개월)
    roi_1year: dict[str, float]             # 시나리오별 1년 ROI
    roi_3year: dict[str, float]             # 시나리오별 3년 ROI
    cash_flow_projection: list[dict]        # 월별 현금 흐름 예측 (12개월)
```

---

#### `GET /api/v1/analysis/{request_id}/stream` - SSE 진행 상황 스트림

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT, 쿼리 파라미터 `token`으로도 가능) |
| 최소 티어 | Free |
| Content-Type | `text/event-stream` |
| 연결 방식 | Server-Sent Events (SSE) |

상세 프로토콜은 [3. WebSocket / SSE 프로토콜](#3-websocket--sse-프로토콜) 참조.

---

#### `POST /api/v1/analysis/compare` - 두 상권 비교 분석

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |
| 최소 티어 | Starter |
| 요율 제한 | 분석 횟수 2회 차감 |

**Request Body:**
```python
class CompareRequest(BaseModel):
    analysis_id_a: str                      # 첫 번째 분석 ID
    analysis_id_b: str                      # 두 번째 분석 ID
    comparison_focus: Optional[list[str]] = None  # 비교 초점 카테고리
    # ["population", "competition", "revenue", "risk", "financial"]
```

**Response (200 OK):**
```python
class ComparisonResult(BaseModel):
    comparison_id: str
    analysis_a: AnalysisSummary             # 분석 A 요약
    analysis_b: AnalysisSummary             # 분석 B 요약
    comparison_table: list[ComparisonRow]   # 항목별 비교
    winner_summary: str                     # 종합 비교 의견
    pros_cons_a: dict[str, list[str]]       # A의 장단점
    pros_cons_b: dict[str, list[str]]       # B의 장단점

class ComparisonRow(BaseModel):
    category: str                           # "유동인구", "경쟁도", ...
    metric: str                             # "일 평균 유동인구"
    value_a: Any
    value_b: Any
    winner: Literal["a", "b", "tie"]
    note: Optional[str]
```

---

#### `GET /api/v1/analysis/history` - 분석 이력 조회

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |
| 최소 티어 | Free |

**Query Parameters:**
```python
class AnalysisHistoryParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=50)
    status: Optional[Literal["queued", "processing", "completed", "failed"]] = None
    sort_by: Literal["created_at", "overall_score"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"
    industry: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
```

**Response (200 OK):**
```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

class AnalysisHistoryItem(BaseModel):
    request_id: str
    query: str
    location_summary: str                   # "서울 강남구 역삼동"
    industry: Optional[str]
    depth: str
    status: str
    overall_score: Optional[float]
    overall_grade: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

# 응답 타입: PaginatedResponse[AnalysisHistoryItem]
```

---

### 2.2 채팅 엔드포인트 (Chat)

---

#### `POST /api/v1/chat/{analysis_id}` - 후속 질문

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |
| 최소 티어 | Free |
| 참고 | 완료된 분석에 대해서만 채팅 가능 |

**Request Body:**
```python
class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    context_focus: Optional[list[str]] = None  # 참조할 에이전트 결과
    # ["commercial_area", "population", "competition", "revenue", "risk", "financial"]
```

**Response (200 OK):**
```python
class ChatMessageResponse(BaseModel):
    message_id: str
    role: Literal["assistant"]
    content: str                            # 마크다운 형식 응답
    references: list[ChatReference]         # 분석 결과 참조 구간
    suggested_questions: list[str]          # 추천 후속 질문 (최대 3개)
    created_at: datetime

class ChatReference(BaseModel):
    agent_name: str                         # 참조한 에이전트
    section: str                            # 참조한 섹션
    snippet: str                            # 인용 텍스트
```

---

#### `GET /api/v1/chat/{analysis_id}/history` - 채팅 이력 조회

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |
| 최소 티어 | Free |

**Query Parameters:**
- `page` (int, default: 1)
- `page_size` (int, default: 20, max: 50)

**Response (200 OK):**
```python
class ChatHistoryItem(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    references: Optional[list[ChatReference]]
    created_at: datetime

# 응답 타입: PaginatedResponse[ChatHistoryItem]
```

---

### 2.3 인증 엔드포인트 (Auth)

---

#### `POST /api/v1/auth/register` - 회원가입

| 항목 | 값 |
|------|-----|
| 인증 | 불필요 |

**Request Body:**
```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=2, max_length=50)
    agree_terms: bool = Field(..., description="이용약관 동의 (필수)")
    agree_privacy: bool = Field(..., description="개인정보처리방침 동의 (필수)")
    agree_marketing: bool = Field(False, description="마케팅 수신 동의 (선택)")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.match(r"^(?=.*[a-zA-Z])(?=.*\d)(?=.*[!@#$%^&*]).{8,}$", v):
            raise ValueError("비밀번호는 영문, 숫자, 특수문자를 포함해야 합니다")
        return v
```

**Response (201 Created):**
```python
class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"]
    expires_in: int                         # 초 단위 (1800)
    user: UserProfile
    # Refresh Token은 Set-Cookie 헤더로 전달 (HttpOnly, Secure, SameSite=Strict)
```

---

#### `POST /api/v1/auth/login` - 로그인

| 항목 | 값 |
|------|-----|
| 인증 | 불필요 |

**Request Body:**
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

**Response (200 OK):** `AuthResponse` (위와 동일)

---

#### `POST /api/v1/auth/refresh` - 토큰 갱신

| 항목 | 값 |
|------|-----|
| 인증 | Refresh Token (쿠키) |

**Request:** 본문 없음 (Refresh Token은 쿠키에서 자동 전송)

**Response (200 OK):** `AuthResponse` (위와 동일)

---

#### `POST /api/v1/auth/logout` - 로그아웃

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |

**Response (200 OK):**
```json
{ "message": "로그아웃 되었습니다" }
```
Set-Cookie로 Refresh Token 쿠키 삭제. Redis에서 Refresh Token 블랙리스트 등록.

---

#### `GET /api/v1/auth/oauth/{provider}` - OAuth 인증 시작

| 항목 | 값 |
|------|-----|
| 인증 | 불필요 |
| Path Parameter | `provider`: `"google"` 또는 `"kakao"` |

**Response (302 Redirect):** OAuth 제공자의 인증 페이지로 리다이렉트

---

#### `GET /api/v1/auth/callback/{provider}` - OAuth 콜백

| 항목 | 값 |
|------|-----|
| 인증 | 불필요 |
| Path Parameter | `provider`: `"google"` 또는 `"kakao"` |

**Query Parameters:**
- `code` (str) - OAuth 인증 코드
- `state` (str) - CSRF 방지 상태값

**Response (302 Redirect):**
프론트엔드로 리다이렉트 (`{FRONTEND_URL}/auth/callback?token={access_token}`)

---

### 2.4 사용자 엔드포인트 (User)

---

#### `GET /api/v1/user/profile` - 프로필 조회

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |

**Response (200 OK):**
```python
class UserProfile(BaseModel):
    user_id: str
    email: str
    name: str
    tier: Literal["free", "starter", "pro"]
    oauth_provider: Optional[str]           # "google", "kakao", None
    analysis_count_this_month: int
    analysis_limit: Optional[int]           # None = 무제한 (Pro)
    preferences: UserPreferences
    created_at: datetime
```

---

#### `PUT /api/v1/user/preferences` - 환경설정 수정

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |

**Request Body:**
```python
class UserPreferences(BaseModel):
    default_location: Optional[LocationInput] = None    # 기본 분석 위치
    default_industry: Optional[str] = None              # 기본 업종
    default_depth: Literal["quick", "standard", "deep"] = "standard"
    language: Literal["ko", "en"] = "ko"
    notification_email: bool = True                     # 분석 완료 이메일 알림
    map_style: Literal["standard", "satellite", "dark"] = "standard"
```

**Response (200 OK):** 업데이트된 `UserPreferences`

---

### 2.5 데이터 엔드포인트 (Data)

---

#### `GET /api/v1/districts/search` - 상권 검색

| 항목 | 값 |
|------|-----|
| 인증 | 선택 (미인증 시 제한적 결과) |

**Query Parameters:**
```python
class DistrictSearchParams(BaseModel):
    q: str = Field(..., min_length=1, max_length=100)   # 검색어
    type: Optional[Literal["commercial", "administrative"]] = None
    limit: int = Field(10, ge=1, le=50)
```

**Response (200 OK):**
```python
class DistrictSearchResult(BaseModel):
    district_id: str
    name: str                               # "강남역 상권"
    full_address: str                       # "서울특별시 강남구 역삼동"
    type: str                               # "골목상권", "발달상권"
    center_lat: float
    center_lng: float
    store_count: Optional[int]              # 점포 수

# 응답: list[DistrictSearchResult]
```

---

#### `GET /api/v1/industries` - 업종 카테고리 목록

| 항목 | 값 |
|------|-----|
| 인증 | 불필요 |

**Query Parameters:**
- `parent_code` (str, optional) - 상위 업종 코드 (미지정 시 대분류 반환)

**Response (200 OK):**
```python
class IndustryCategory(BaseModel):
    code: str                               # "Q12"
    name: str                               # "음식"
    level: int                              # 1=대분류, 2=중분류, 3=소분류
    children_count: int                     # 하위 업종 수
    parent_code: Optional[str]

# 응답: list[IndustryCategory]
```

---

#### `GET /api/v1/map/markers/{analysis_id}` - 분석 결과 지도 마커

| 항목 | 값 |
|------|-----|
| 인증 | 필수 (JWT) |

**Query Parameters:**
- `layer` (str, optional) - 표시할 레이어 필터: `"competitors"`, `"poi"`, `"boundary"`, `"heatmap"`

**Response (200 OK):**
```python
class MapMarkerSet(BaseModel):
    center: dict[str, float]                # { "lat": 37.4979, "lng": 127.0276 }
    radius_m: int
    boundary_geojson: Optional[dict]        # 상권 경계 폴리곤

    competitors: list[CompetitorMarker]
    pois: list[POIMarker]
    heatmap_data: Optional[HeatmapData]
    walking_circles: list[WalkingCircle]

class CompetitorMarker(BaseModel):
    id: str
    name: str
    category: str
    lat: float
    lng: float
    rating: Optional[float]
    review_count: Optional[int]
    is_direct_competitor: bool              # 직접 경쟁 여부

class POIMarker(BaseModel):
    id: str
    name: str
    type: str                               # "subway", "bus_stop", "school", "hospital", ...
    lat: float
    lng: float
    distance_m: int                         # 중심점으로부터 거리

class HeatmapData(BaseModel):
    type: Literal["population", "revenue"]
    points: list[dict]                      # [{ "lat", "lng", "weight" }, ...]
    max_weight: float
    min_weight: float

class WalkingCircle(BaseModel):
    minutes: int                            # 5 또는 10
    polygon_geojson: dict                   # 도보 반경 폴리곤 (실제 도로 기반)
```

---

## 3. WebSocket / SSE 프로토콜

### 3.1 SSE 진행 상황 스트리밍

분석 진행 상황은 SSE(Server-Sent Events)를 통해 실시간으로 전달한다.
WebSocket 대비 SSE를 선택한 이유: 단방향 서버→클라이언트 통신만 필요하며, 자동 재연결이 내장되어 있고, HTTP/2 환경에서 효율적이다.

**연결:**
```
GET /api/v1/analysis/{request_id}/stream
Authorization: Bearer {access_token}

# 또는 쿼리 파라미터 방식 (EventSource에서 헤더 설정이 불가능한 경우)
GET /api/v1/analysis/{request_id}/stream?token={access_token}
```

**응답 헤더:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

### 3.2 이벤트 타입 및 페이로드

#### `analysis_start` - 분석 시작
```
event: analysis_start
data: {
    "type": "analysis_start",
    "request_id": "a1b2c3d4-...",
    "total_agents": 6,
    "estimated_duration_sec": 420,
    "timestamp": "2026-03-19T10:30:00Z"
}
```

#### `agent_start` - 에이전트 실행 시작
```
event: agent_start
data: {
    "type": "agent_start",
    "agent_name": "commercial_area",
    "agent_display_name": "상권 분석",
    "agent_index": 1,
    "total_agents": 6,
    "timestamp": "2026-03-19T10:30:01Z"
}
```

#### `agent_progress` - 에이전트 진행 상황 (선택적)
```
event: agent_progress
data: {
    "type": "agent_progress",
    "agent_name": "commercial_area",
    "progress_pct": 45,
    "current_step": "공공데이터 API 조회 중...",
    "timestamp": "2026-03-19T10:30:15Z"
}
```

#### `agent_complete` - 에이전트 실행 완료
```
event: agent_complete
data: {
    "type": "agent_complete",
    "agent_name": "commercial_area",
    "agent_display_name": "상권 분석",
    "agent_index": 1,
    "total_agents": 6,
    "duration_sec": 45.2,
    "confidence_score": 0.87,
    "summary": "강남역 상권은 발달상권으로 총 2,340개 점포가 영업 중입니다.",
    "key_metrics": {
        "total_stores": 2340,
        "vacancy_rate": 4.2,
        "district_type": "발달상권"
    },
    "timestamp": "2026-03-19T10:30:46Z"
}
```

#### `debate_start` - 교차 검증 시작
```
event: debate_start
data: {
    "type": "debate_start",
    "total_rounds": 3,
    "participants": ["commercial_area", "population", "competition", "revenue", "risk", "financial"],
    "timestamp": "2026-03-19T10:34:00Z"
}
```

#### `debate_round` - 교차 검증 라운드
```
event: debate_round
data: {
    "type": "debate_round",
    "round_number": 1,
    "challenger": "risk",
    "target": "revenue",
    "challenge_point": "매출 추정 시 최근 임대료 상승 추세가 반영되지 않았습니다.",
    "response": "임대료 상승분을 반영하여 월 예상 비용을 12% 상향 조정합니다.",
    "score_adjustment": { "revenue.estimated_monthly_revenue": -180 },
    "timestamp": "2026-03-19T10:34:30Z"
}
```

#### `synthesis_start` - 종합 보고서 생성 시작
```
event: synthesis_start
data: {
    "type": "synthesis_start",
    "timestamp": "2026-03-19T10:35:00Z"
}
```

#### `complete` - 분석 완료
```
event: complete
data: {
    "type": "complete",
    "request_id": "a1b2c3d4-...",
    "overall_score": 72.5,
    "overall_grade": "B+",
    "executive_summary": "강남역 인근 카페 창업은 높은 유동인구와...",
    "total_duration_sec": 312.5,
    "timestamp": "2026-03-19T10:35:12Z"
}
```

#### `error` - 오류 발생
```
event: error
data: {
    "type": "error",
    "error": "population 에이전트 실행 중 오류가 발생했습니다",
    "code": "AGENT_EXECUTION_FAILED",
    "agent_name": "population",
    "recoverable": true,
    "timestamp": "2026-03-19T10:31:20Z"
}
```

#### `heartbeat` - 연결 유지 (30초 간격)
```
event: heartbeat
data: { "type": "heartbeat", "timestamp": "2026-03-19T10:31:00Z" }
```

### 3.3 재연결 전략

```python
# 서버 측: 각 이벤트에 ID 부여
id: {event_sequence_number}
event: agent_complete
data: {...}

# 클라이언트 재연결 시 Last-Event-ID 헤더로 마지막 수신 ID 전송
# 서버는 해당 ID 이후의 이벤트부터 재전송
```

| 항목 | 값 |
|------|-----|
| 초기 재연결 대기 | 1초 |
| 최대 재연결 대기 | 30초 |
| 백오프 전략 | 지수 백오프 (x2) + 지터 |
| 최대 재시도 | 10회 |
| 서버 측 retry 설정 | `retry: 3000` (3초) |

### 3.4 SSE 서버 구현

```python
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

@router.get("/analysis/{request_id}/stream")
async def stream_analysis_progress(
    request_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    last_event_id: Optional[int] = Header(None, alias="Last-Event-ID"),
):
    analysis = await get_analysis_or_404(request_id, current_user.id)

    async def event_generator():
        redis = get_redis()
        channel = f"analysis:{request_id}:events"
        last_id = last_event_id or 0

        # 놓친 이벤트 재전송 (Redis Stream에서)
        missed_events = await redis.xrange(
            f"analysis:{request_id}:event_log",
            min=str(last_id + 1), max="+"
        )
        for event_id, event_data in missed_events:
            if await request.is_disconnected():
                return
            yield {
                "id": event_id,
                "event": event_data["type"],
                "data": event_data["payload"],
                "retry": 3000,
            }

        # 실시간 이벤트 구독 (Redis Pub/Sub)
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message["type"] == "message":
                    event = json.loads(message["data"])
                    yield {
                        "id": event["sequence"],
                        "event": event["type"],
                        "data": json.dumps(event["data"]),
                        "retry": 3000,
                    }
                    if event["type"] in ("complete", "error"):
                        break
        finally:
            await pubsub.unsubscribe(channel)

    return EventSourceResponse(event_generator())
```

---

## 4. 에러 응답 형식

### 4.1 표준 에러 스키마

모든 에러 응답은 다음 형식을 따른다:

```python
class ErrorResponse(BaseModel):
    error: str                              # 사람이 읽을 수 있는 에러 메시지 (한국어)
    code: str                               # 머신 리더블 에러 코드
    details: Optional[Any] = None           # 추가 정보 (유효성 검사 오류 상세 등)
    request_id: Optional[str] = None        # 요청 추적 ID (Langfuse correlation)
    timestamp: datetime                     # 에러 발생 시각

# 예시
{
    "error": "월간 분석 횟수를 초과했습니다. Starter 플랜으로 업그레이드하세요.",
    "code": "RATE_LIMIT_EXCEEDED",
    "details": {
        "limit": 3,
        "used": 3,
        "reset_at": "2026-04-01T00:00:00Z",
        "upgrade_url": "/pricing"
    },
    "request_id": "req_a1b2c3d4",
    "timestamp": "2026-03-19T10:30:00Z"
}
```

### 4.2 에러 코드 카탈로그

#### 인증 에러 (AUTH_*)

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `AUTH_TOKEN_EXPIRED` | 401 | Access Token이 만료되었습니다 |
| `AUTH_TOKEN_INVALID` | 401 | 유효하지 않은 토큰입니다 |
| `AUTH_REFRESH_TOKEN_EXPIRED` | 401 | Refresh Token이 만료되었습니다. 재로그인이 필요합니다 |
| `AUTH_REFRESH_TOKEN_REUSED` | 401 | Refresh Token 재사용이 감지되었습니다 (보안 위협) |
| `AUTH_CREDENTIALS_INVALID` | 401 | 이메일 또는 비밀번호가 올바르지 않습니다 |
| `AUTH_EMAIL_ALREADY_EXISTS` | 409 | 이미 등록된 이메일입니다 |
| `AUTH_OAUTH_FAILED` | 400 | OAuth 인증에 실패했습니다 |
| `AUTH_FORBIDDEN` | 403 | 해당 리소스에 접근 권한이 없습니다 |

#### 요율 제한 에러 (RATE_*)

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `RATE_LIMIT_EXCEEDED` | 429 | 월간 분석 횟수를 초과했습니다 |
| `RATE_API_LIMIT_EXCEEDED` | 429 | 분당 API 호출 한도를 초과했습니다 |
| `RATE_CONCURRENT_LIMIT` | 429 | 동시 분석 수 한도를 초과했습니다 |

#### 분석 에러 (ANALYSIS_*)

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `ANALYSIS_NOT_FOUND` | 404 | 분석 결과를 찾을 수 없습니다 |
| `ANALYSIS_NOT_READY` | 202 | 분석이 아직 진행 중입니다 |
| `ANALYSIS_FAILED` | 500 | 분석 처리 중 오류가 발생했습니다 |
| `ANALYSIS_TIMEOUT` | 504 | 분석 처리 시간이 초과되었습니다 |
| `ANALYSIS_LOCATION_INVALID` | 400 | 유효하지 않은 위치 정보입니다 |
| `ANALYSIS_INDUSTRY_INVALID` | 400 | 유효하지 않은 업종 코드입니다 |
| `ANALYSIS_AGENT_FAILED` | 500 | 에이전트 실행 중 오류가 발생했습니다 |

#### 유효성 검사 에러 (VALIDATION_*)

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `VALIDATION_ERROR` | 422 | 요청 데이터가 유효하지 않습니다 |
| `VALIDATION_MISSING_FIELD` | 422 | 필수 필드가 누락되었습니다 |
| `VALIDATION_INVALID_FORMAT` | 422 | 잘못된 데이터 형식입니다 |

#### 서버 에러 (SERVER_*)

| 코드 | HTTP 상태 | 설명 |
|------|----------|------|
| `SERVER_INTERNAL_ERROR` | 500 | 서버 내부 오류가 발생했습니다 |
| `SERVER_EXTERNAL_API_ERROR` | 502 | 외부 API 연동 중 오류가 발생했습니다 |
| `SERVER_MAINTENANCE` | 503 | 서비스 점검 중입니다 |

### 4.3 유효성 검사 에러 상세

FastAPI의 RequestValidationError는 다음 형식으로 변환한다:

```json
{
    "error": "요청 데이터가 유효하지 않습니다",
    "code": "VALIDATION_ERROR",
    "details": [
        {
            "field": "query",
            "message": "이 필드는 필수입니다",
            "type": "missing"
        },
        {
            "field": "location.radius_m",
            "message": "값은 100 이상이어야 합니다",
            "type": "greater_than_equal",
            "context": { "ge": 100 }
        }
    ],
    "request_id": "req_x1y2z3",
    "timestamp": "2026-03-19T10:30:00Z"
}
```

---

## 5. 미들웨어 스택

미들웨어는 등록 역순으로 실행된다. 아래는 요청 처리 순서대로 기술한다.

### 5.1 실행 순서

```
요청 수신
  → [1] CORS 미들웨어
  → [2] 요청 로깅 미들웨어 (Langfuse correlation ID 생성)
  → [3] 인증 미들웨어
  → [4] 요율 제한 미들웨어
  → [5] 에러 핸들링 미들웨어
  → 라우터 핸들러
  → [5] 에러 핸들링 미들웨어 (응답)
  → [4] 요율 제한 미들웨어 (헤더 추가)
  → [2] 요청 로깅 미들웨어 (응답 로깅)
  → [1] CORS 미들웨어 (헤더 추가)
응답 전송
```

### 5.2 CORS 미들웨어

```python
from fastapi.middleware.cors import CORSMiddleware

cors_settings = {
    "allow_origins": [
        "http://localhost:3000",            # 로컬 개발
        "https://marketscope.ai",           # 프로덕션
        "https://www.marketscope.ai",
    ],
    "allow_credentials": True,              # 쿠키 전송 허용 (Refresh Token)
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Authorization", "Content-Type", "X-Request-ID"],
    "expose_headers": [
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "X-Request-ID",
    ],
    "max_age": 3600,                        # Preflight 캐시 1시간
}
```

### 5.3 요청/응답 로깅 미들웨어 + Langfuse 연동

```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. 요청 ID 생성 또는 수신
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id

        # 2. Langfuse 트레이스 시작
        trace = langfuse.trace(
            id=request_id,
            name=f"{request.method} {request.url.path}",
            metadata={
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params),
                "user_agent": request.headers.get("User-Agent"),
                "user_id": getattr(request.state, "user_id", None),
            },
        )
        request.state.langfuse_trace = trace

        # 3. 요청 처리
        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        # 4. 응답 로깅
        trace.update(
            output={
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }
        )

        # 5. 응답 헤더에 요청 ID 추가
        response.headers["X-Request-ID"] = request_id

        # 6. 구조화된 로그 출력
        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            user_id=getattr(request.state, "user_id", None),
        )

        return response
```

### 5.4 인증 미들웨어

```python
# 인증이 불필요한 경로 목록
PUBLIC_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/oauth/google",
    "/api/v1/auth/oauth/kakao",
    "/api/v1/auth/callback/google",
    "/api/v1/auth/callback/kakao",
    "/api/v1/industries",
    "/docs",
    "/openapi.json",
    "/health",
}

# 인증 선택적 경로 (인증 시 추가 데이터 제공)
OPTIONAL_AUTH_PATHS = {
    "/api/v1/districts/search",
}

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_PATHS:
            return await call_next(request)

        token = self._extract_token(request)

        if path in OPTIONAL_AUTH_PATHS:
            if token:
                request.state.user = await self._verify_token(token)
            return await call_next(request)

        if not token:
            raise AuthenticationError("AUTH_TOKEN_INVALID")

        user = await self._verify_token(token)
        request.state.user = user
        request.state.user_id = user.id

        return await call_next(request)
```

### 5.5 요율 제한 미들웨어

```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis 슬라이딩 윈도우 기반 요율 제한"""

    TIER_LIMITS = {
        "free":    {"monthly_analysis": 3,  "api_per_minute": 30,  "concurrent": 1},
        "starter": {"monthly_analysis": 20, "api_per_minute": 60,  "concurrent": 2},
        "pro":     {"monthly_analysis": None, "api_per_minute": 120, "concurrent": 5},
    }

    async def dispatch(self, request: Request, call_next):
        user = getattr(request.state, "user", None)
        if not user:
            return await call_next(request)

        tier = user.tier
        limits = self.TIER_LIMITS[tier]

        # 1. 분당 API 호출 제한 확인
        api_ok, api_remaining = await self._check_api_rate(user.id, limits["api_per_minute"])
        if not api_ok:
            raise RateLimitError("RATE_API_LIMIT_EXCEEDED")

        # 2. 분석 엔드포인트인 경우 추가 확인
        if request.url.path == "/api/v1/analysis" and request.method == "POST":
            # 월간 분석 횟수 확인
            if limits["monthly_analysis"] is not None:
                analysis_ok, analysis_remaining = await self._check_monthly_analysis(
                    user.id, limits["monthly_analysis"]
                )
                if not analysis_ok:
                    raise RateLimitError("RATE_LIMIT_EXCEEDED")

            # 동시 분석 수 확인
            concurrent_ok = await self._check_concurrent(user.id, limits["concurrent"])
            if not concurrent_ok:
                raise RateLimitError("RATE_CONCURRENT_LIMIT")

        response = await call_next(request)

        # 응답 헤더에 요율 제한 정보 추가
        if limits["monthly_analysis"] is not None:
            used = await self._get_monthly_usage(user.id)
            response.headers["X-RateLimit-Limit"] = str(limits["monthly_analysis"])
            response.headers["X-RateLimit-Remaining"] = str(max(0, limits["monthly_analysis"] - used))
            response.headers["X-RateLimit-Reset"] = str(self._get_month_reset_timestamp())

        return response
```

### 5.6 에러 핸들링 미들웨어

```python
class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except MarketScopeError as e:
            # 커스텀 비즈니스 예외
            return JSONResponse(
                status_code=e.status_code,
                content=ErrorResponse(
                    error=e.message,
                    code=e.code,
                    details=e.details,
                    request_id=getattr(request.state, "request_id", None),
                    timestamp=datetime.utcnow(),
                ).model_dump(),
            )
        except RequestValidationError as e:
            # Pydantic 유효성 검사 오류
            return JSONResponse(
                status_code=422,
                content=ErrorResponse(
                    error="요청 데이터가 유효하지 않습니다",
                    code="VALIDATION_ERROR",
                    details=self._format_validation_errors(e.errors()),
                    request_id=getattr(request.state, "request_id", None),
                    timestamp=datetime.utcnow(),
                ).model_dump(),
            )
        except Exception as e:
            # 예상치 못한 서버 오류
            logger.exception("Unhandled exception", request_id=getattr(request.state, "request_id", None))

            # Langfuse에 오류 기록
            if hasattr(request.state, "langfuse_trace"):
                request.state.langfuse_trace.update(
                    level="ERROR",
                    status_message=str(e),
                )

            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    error="서버 내부 오류가 발생했습니다",
                    code="SERVER_INTERNAL_ERROR",
                    request_id=getattr(request.state, "request_id", None),
                    timestamp=datetime.utcnow(),
                ).model_dump(),
            )
```

---

## 6. Celery 태스크 통합

### 6.1 아키텍처 개요

```
[FastAPI] → POST /analysis → [Redis Queue] → [Celery Worker] → [Redis Pub/Sub] → [SSE 스트림]
                                                    ↓
                                              [PostgreSQL]
                                              (결과 저장)
```

분석 요청은 Celery 태스크로 비동기 처리된다. FastAPI는 태스크를 큐에 넣고 즉시 202 응답을 반환한다. 클라이언트는 SSE 또는 폴링으로 진행 상황을 확인한다.

### 6.2 Celery 앱 설정

```python
from celery import Celery

celery_app = Celery(
    "marketscope",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
)

celery_app.conf.update(
    # 태스크 설정
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",

    # 큐 설정
    task_routes={
        "tasks.analysis_task.run_analysis": {"queue": "analysis"},
        "tasks.analysis_task.run_quick_analysis": {"queue": "analysis_quick"},
    },

    # 동시 실행 제한 (워커당)
    worker_concurrency=4,
    worker_prefetch_multiplier=1,

    # 결과 만료
    result_expires=86400,                   # 24시간

    # 재시도 설정
    task_acks_late=True,                    # 처리 완료 후 ACK
    task_reject_on_worker_lost=True,        # 워커 비정상 종료 시 재큐
)
```

### 6.3 분석 태스크 정의

```python
from celery import Task
import asyncio

class AnalysisTask(Task):
    """분석 태스크 기본 클래스"""
    autoretry_for = (ExternalAPIError,)     # 외부 API 오류 시 자동 재시도
    retry_kwargs = {"max_retries": 2, "countdown": 10}
    retry_backoff = True
    retry_backoff_max = 60
    retry_jitter = True

    # 태스크 타임아웃 설정
    soft_time_limit = 900                   # 15분 (소프트: SoftTimeLimitExceeded 발생)
    time_limit = 960                        # 16분 (하드: 강제 종료)

@celery_app.task(base=AnalysisTask, bind=True, name="tasks.analysis_task.run_analysis")
def run_analysis(self, request_id: str, user_id: str, params: dict):
    """메인 분석 태스크"""
    try:
        # asyncio 이벤트 루프에서 실행
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            _execute_analysis(self, request_id, user_id, params)
        )
        return result
    except SoftTimeLimitExceeded:
        # 타임아웃 시 부분 결과라도 저장
        loop.run_until_complete(
            _handle_timeout(request_id)
        )
        raise

async def _execute_analysis(task: Task, request_id: str, user_id: str, params: dict):
    """
    Celery 워커에서 LangGraph StateGraph를 실행하고 진행 이벤트를 Redis Pub/Sub으로 발행.

    LangGraph 연동 방식:
    - graph.astream_events()로 노드 실행 이벤트를 스트리밍 수신
    - 각 이벤트를 Redis Pub/Sub channel에 publish → FastAPI SSE 엔드포인트가 클라이언트로 전달
    - LangGraph 체크포인터(InMemorySaver 또는 AsyncPostgresSaver)가 State 영속성 담당
    """
    from app.agents.graph import build_analysis_graph
    from app.agents.state import create_initial_state
    from langgraph.checkpoint.memory import InMemorySaver

    redis = await get_redis()
    channel = f"analysis:{request_id}:events"
    sequence = 0
    task_start_time = time.monotonic()

    async def publish_event(event_type: str, data: dict):
        nonlocal sequence
        sequence += 1
        event = {"type": event_type, "data": data, "sequence": sequence}
        await redis.publish(channel, json.dumps(event, default=str))
        await redis.xadd(
            f"analysis:{request_id}:event_log",
            {"type": event_type, "payload": json.dumps(data, default=str)},
            maxlen=100,
        )

    # 1. 초기 State 생성 (MarketScopeState)
    session_id = request_id          # request_id = session_id 1:1 매핑
    user_input = params["user_input"]
    initial_state = create_initial_state(session_id=session_id, user_input=user_input)

    # 2. DB에 세션 시작 기록
    await db.execute(
        """INSERT INTO analysis_sessions
           (session_id, user_id, user_input, analysis_mode, target_location,
            target_industry, commander_plan, status)
           VALUES ($1, $2, $3, 'pending', '', '', '{}', 'RUNNING')""",
        session_id, user_id, user_input,
    )
    await publish_event("analysis_start", {
        "request_id": request_id,
        "session_id": session_id,
        "total_agents": 4,      # Phase 1: population, competition, revenue, location
        "timestamp": datetime.utcnow().isoformat(),
    })

    # 3. LangGraph 그래프 빌드 및 체크포인터 설정
    checkpointer = InMemorySaver()  # Phase 1: 인메모리 체크포인터 (단일 워커 내 충분)
    # Phase 2: AsyncPostgresSaver로 교체 (멀티 워커, 재시작 복구 지원)
    # from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    # checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)

    graph = build_analysis_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": session_id}}

    # 4. LangGraph 스트리밍 실행
    # astream_events()는 on_chain_start, on_chain_end, on_node_start, on_node_end 등을 emit
    final_state = None
    async for event in graph.astream_events(initial_state, config=config, version="v2"):
        kind = event["event"]
        name = event.get("name", "")

        if kind == "on_chain_start" and name == "commander":
            await publish_event("agent_start", {
                "agent_name": "commander",
                "agent_display_name": "분석 계획 수립",
                "timestamp": datetime.utcnow().isoformat(),
            })

        elif kind == "on_chain_end" and name == "commander":
            plan = event["data"]["output"].get("commander_plan", {})
            await publish_event("agent_complete", {
                "agent_name": "commander",
                "agent_display_name": "분석 계획 수립",
                "analysis_mode": plan.get("analysis_mode"),
                "agents_to_run": plan.get("agents_to_run", []),
                "estimated_duration_sec": plan.get("estimated_duration_seconds"),
                "timestamp": datetime.utcnow().isoformat(),
            })

        elif kind == "on_chain_start" and name in ("population", "competition", "revenue", "location"):
            await publish_event("agent_start", {
                "agent_name": name,
                "agent_display_name": AGENT_DISPLAY_NAMES.get(name, name),
                "timestamp": datetime.utcnow().isoformat(),
            })

        elif kind == "on_chain_end" and name in ("population", "competition", "revenue", "location"):
            result_key = f"{name}_result"
            result = event["data"]["output"].get(result_key, {})
            await publish_event("agent_complete", {
                "agent_name": name,
                "agent_display_name": AGENT_DISPLAY_NAMES.get(name, name),
                "confidence_score": result.get("confidence_score"),
                "summary": result.get("summary"),
                "timestamp": datetime.utcnow().isoformat(),
            })

        elif kind == "on_chain_end" and name == "narrative":
            final_state = event["data"]["output"]
            final_report = final_state.get("final_report", {})
            await publish_event("complete", {
                "request_id": request_id,
                "session_id": session_id,
                "overall_score": final_report.get("overall_score"),
                "verdict": final_report.get("verdict"),
                "one_line_summary": final_report.get("one_line_summary"),
                "total_duration_sec": round(time.monotonic() - task_start_time, 1),
                "timestamp": datetime.utcnow().isoformat(),
            })

    # 5. 최종 State를 DB에 저장 (analysis_sessions 업데이트)
    if final_state:
        await db.execute(
            """UPDATE analysis_sessions SET
               analysis_mode=$1, target_location=$2, target_industry=$3,
               commander_plan=$4,
               population_result=$5, competition_result=$6,
               revenue_result=$7, location_result=$8,
               final_report=$9, overall_score=$10, verdict=$11,
               node_executions=$12, errors=$13,
               processing_time_ms=$14, status='COMPLETED'
               WHERE session_id=$15""",
            final_state.get("commander_plan", {}).get("analysis_mode"),
            final_state.get("commander_plan", {}).get("target_location"),
            final_state.get("commander_plan", {}).get("target_industry"),
            json.dumps(final_state.get("commander_plan", {})),
            json.dumps(final_state.get("population_result")),
            json.dumps(final_state.get("competition_result")),
            json.dumps(final_state.get("revenue_result")),
            json.dumps(final_state.get("location_result")),
            json.dumps(final_state.get("final_report")),
            final_state.get("final_report", {}).get("overall_score"),
            final_state.get("final_report", {}).get("verdict"),
            json.dumps(final_state.get("node_executions", [])),
            json.dumps(final_state.get("errors", [])),
            round((time.monotonic() - task_start_time) * 1000),
            session_id,
        )
    else:
        await db.execute(
            "UPDATE analysis_sessions SET status='FAILED' WHERE session_id=$1",
            session_id,
        )

    # 6. 이벤트 로그 TTL 설정 (24시간 후 자동 삭제)
    await redis.expire(f"analysis:{request_id}:event_log", 86400)

    return {"request_id": request_id, "status": "completed"}


AGENT_DISPLAY_NAMES = {
    "commander": "분석 계획 수립",
    "population": "인구 분석",
    "competition": "경쟁 분석",
    "revenue": "매출 분석",
    "location": "입지 분석",
    "visualization": "시각화 생성",
    "narrative": "리포트 생성",
}
```

#### LangGraph 체크포인터 선택 기준

| 환경 | 체크포인터 | 설명 |
|------|----------|------|
| Phase 1 (단일 워커) | `InMemorySaver` | 구현 단순, 워커 재시작 시 State 손실 (허용 가능) |
| Phase 2 (멀티 워커) | `AsyncPostgresSaver` | 워커 간 State 공유, 재시작 복구 지원 |
| 개발/테스트 | `InMemorySaver` | 기본값 |

#### `build_analysis_graph()` 시그니처 (참고)

```python
# app/agents/graph.py
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver

def build_analysis_graph(checkpointer: BaseCheckpointSaver) -> CompiledGraph:
    """
    Phase 1 LangGraph StateGraph 빌드.

    노드 구성:
      START → commander → [population ‖ competition] → [revenue ‖ location]
            → visualization → narrative → END

    fan-out/fan-in은 LangGraph의 Send API 또는 병렬 엣지로 구현.
    """
    workflow = StateGraph(MarketScopeState)
    workflow.add_node("commander", commander_node)
    workflow.add_node("population", population_node)
    workflow.add_node("competition", competition_node)
    workflow.add_node("revenue", revenue_node)
    workflow.add_node("location", location_node)
    workflow.add_node("visualization", visualization_node)
    workflow.add_node("narrative", narrative_node)

    workflow.add_edge(START, "commander")
    workflow.add_conditional_edges("commander", route_after_commander)
    # Phase 1: population + competition 병렬 (Step 1)
    #          revenue + location 병렬 (Step 2, population/competition 완료 후)
    workflow.add_edge(["population", "competition"], "revenue")
    workflow.add_edge(["population", "competition"], "location")
    workflow.add_edge(["revenue", "location"], "visualization")
    workflow.add_edge("visualization", "narrative")
    workflow.add_edge("narrative", END)

    return workflow.compile(checkpointer=checkpointer)
```

### 6.4 태스크 상태 폴링 vs SSE

| 방식 | 사용 시점 | 장점 | 단점 |
|------|----------|------|------|
| **SSE (권장)** | 분석 실행 중 실시간 진행 표시 | 실시간, 상세 진행률 | 연결 유지 필요 |
| **폴링** | SSE 연결 불가 시 대체 수단 | 간단, 방화벽 친화적 | 지연, 불필요한 요청 |

폴링 방식으로 상태를 확인할 때는 `GET /api/v1/analysis/{request_id}` 엔드포인트의 `status` 필드를 확인한다:

```
queued → processing → completed
                   → failed
```

권장 폴링 간격: 5초 (처음 30초), 이후 10초.

### 6.5 태스크 타임아웃 및 재시도 정책

**[Phase 1] analysis_mode 기준**

| analysis_mode | 소프트 타임아웃 | 하드 타임아웃 | 최대 재시도 |
|--------------|--------------|-------------|-----------|
| quick | 120초 (2분) | 150초 | 1회 |
| basic | 300초 (5분) | 360초 | 2회 |
| comparison | 420초 (7분) | 480초 | 2회 |

**재시도 대상 오류:**
- 외부 API 응답 타임아웃 (`ExternalAPIError`)
- 일시적 네트워크 오류 (`ConnectionError`)
- Redis 연결 오류 (`RedisConnectionError`)

**재시도 불가 오류 (즉시 실패):**
- 유효하지 않은 파라미터 (`ValidationError`)
- 인증 오류 (`AuthenticationError`)
- 데이터 없음 (`DataNotFoundError`)

### 6.6 큐잉 흐름 (API → Celery)

```python
# routers/analysis.py
@router.post("/", status_code=202, response_model=AnalysisCreateResponse)
async def create_analysis(
    request: AnalysisCreateRequest,
    current_user: User = Depends(get_current_user),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
):
    # 1. 요율 제한 확인
    await rate_limiter.check_and_increment(current_user)

    # 2. 위치 정보 정규화 (주소 → 좌표 변환 등)
    location = await normalize_location(request.location)

    # 3. DB에 분석 요청 레코드 생성
    analysis = await create_analysis_record(
        user_id=current_user.id,
        query=request.query,
        location=location,
        industry=request.industry,
        depth=request.depth,
    )

    # 4. 분석 깊이에 따른 예상 소요 시간
    duration_map = {"quick": 180, "standard": 420, "deep": 900}
    estimated_duration = duration_map[request.depth]

    # 5. Celery 태스크 큐잉
    task = run_analysis.apply_async(
        args=[str(analysis.id), str(current_user.id)],
        kwargs={"params": {
            "query": request.query,
            "location": location.model_dump(),
            "industry": request.industry,
            "depth": request.depth,
            "estimated_duration_sec": estimated_duration,
        }},
        task_id=str(analysis.id),           # 분석 ID를 태스크 ID로 사용
        queue="analysis_quick" if request.depth == "quick" else "analysis",
    )

    # 6. 응답 반환
    return AnalysisCreateResponse(
        request_id=str(analysis.id),
        status="queued",
        estimated_duration_sec=estimated_duration,
        stream_url=f"/api/v1/analysis/{analysis.id}/stream",
        created_at=analysis.created_at,
    )
```
