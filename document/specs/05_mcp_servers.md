# 05. MCP 서버 명세서

> MarketScope AI 데이터 접근 계층 (Data Access Layer)
> 작성일: 2026-03-19

---

> ## ⚡ Phase 1 MVP 기준 — MCP 서버 활성 상태
>
> | MCP 서버 | Phase 1 상태 | Phase 1 핵심 API | 담당 에이전트 |
> |---------|------------|----------------|-------------|
> | **#1 공공데이터** | ✅ **활성** | data.go.kr #15012005 (소상공인 상권정보), 서울 열린데이터광장 생활인구(OA-15379), 서울 추정매출(OA-15572), 서울 지하철 승하차, KOSIS 주민등록인구 | 유동인구 / 매출추정 / 경쟁분석 / 입지분석 |
> | **#2 지도/GIS** | ✅ **활성** | 카카오 로컬 API (지오코딩, 카테고리 검색) | 입지분석 |
> | **#3 부동산** | 🚫 **[Phase 2]** | 한국부동산원, LURIS | 부동산 에이전트 활성 시 |
> | **#4 뉴스/SNS** | 🚫 **[Phase 2]** | ⚠️ 네이버 데이터랩 DB 저장 금지 → 대안 소스 확보 후 | 트렌드 에이전트 활성 시 |
> | **#5 규제/인허가** | 🚫 **[Phase 2]** | ⚠️ localdata.go.kr 2026-04-15 폐기 → data.go.kr로 재설계 | 규제 에이전트 활성 시 |
> | **#6 금융/대출** | 🚫 **[Phase 2]** | 기업마당, K-Startup | 금융 에이전트 활성 시 |
>
> **Phase 1 데이터 스택 (상업적 이용 가능 확인)**:
> - 소상공인 상권정보 (data.go.kr #15012005) — 공공누리 1유형, 경쟁/입지 에이전트 핵심
> - 서울 생활인구 (OA-15379) — 공공누리 1유형, 유동인구 에이전트 핵심
> - 서울 추정매출 (OA-15572) — 공공누리 1유형, 매출추정 에이전트 핵심
> - 서울 지하철 승하차 — 공공누리 1유형, 입지 에이전트 보조
> - KOSIS 주민등록인구 — 공공데이터법 허용, 유동인구 에이전트 보조
> - ❌ **네이버 데이터랩 제외**: 이용약관 저장/DB화 금지 → 상업 SaaS 구조적 위반

---

## 목차

1. [공통 사항](#공통-사항)
2. [MCP Server #1: 공공데이터](#mcp-server-1-공공데이터-public-data)
3. [MCP Server #2: 지도/GIS](#mcp-server-2-지도gis-maps)
4. [MCP Server #3: 부동산](#mcp-server-3-부동산-real-estate)
5. [MCP Server #4: 뉴스/SNS](#mcp-server-4-뉴스sns-news--social)
6. [MCP Server #5: 규제/인허가](#mcp-server-5-규제인허가-regulatory)
7. [MCP Server #6: 금융/대출](#mcp-server-6-금융대출-finance)

---

## 공통 사항

### MCP 서버 구현 패턴

모든 MCP 서버는 `mcp-python-sdk`(v1.x) 기반으로 구현하며, 동일한 프로젝트 구조를 따른다.

```
mcp_servers/
├── public_data/
│   ├── __init__.py
│   ├── server.py          # FastMCP 인스턴스, 도구/리소스 등록
│   ├── tools.py           # @mcp.tool() 데코레이터로 도구 정의
│   ├── resources.py       # @mcp.resource() 데코레이터로 리소스 정의
│   ├── api_client.py      # 외부 API 호출 래퍼 (httpx.AsyncClient)
│   ├── schemas.py         # Pydantic 모델 (요청/응답 스키마)
│   ├── cache.py           # Redis 캐싱 로직
│   └── config.py          # 환경변수, API 키, 설정값
├── maps/
├── real_estate/
├── news_social/
├── regulatory/
├── finance/
├── shared/
│   ├── rate_limiter.py    # 공용 Rate Limiter (Token Bucket)
│   ├── logging.py         # 구조화 로깅 (structlog)
│   ├── errors.py          # 공용 예외 클래스
│   └── redis_client.py    # Redis 연결 풀 싱글턴
└── pyproject.toml
```

#### 서버 기동 패턴

```python
# server.py 공통 패턴
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="public-data-server",
    version="1.0.0",
    description="공공데이터 포털 API 래퍼",
)

# tools.py에서 정의한 도구 임포트 시 자동 등록
import tools  # noqa: F401
import resources  # noqa: F401

if __name__ == "__main__":
    mcp.run(transport="stdio")  # 에이전트와 stdio 통신
```

### 에이전트의 도구 발견 및 호출 흐름

1. **발견 (Discovery)**: 에이전트가 MCP 서버에 `tools/list` 요청을 보내면, 서버는 등록된 모든 도구의 이름, 설명, JSON Schema 파라미터를 반환한다.
2. **호출 (Invocation)**: 에이전트(LLM)가 `tools/call` 요청으로 도구 이름과 인자를 전달하면, 서버가 실행 후 결과를 반환한다.
3. **전송 (Transport)**: 로컬 배포 시 `stdio`, 원격 배포 시 `SSE(Server-Sent Events)` 전송을 사용한다.

```
Agent (LangGraph)
  ↕ JSON-RPC over stdio/SSE
MCP Server (FastMCP)
  ↕ httpx.AsyncClient
External API (data.go.kr, kakao, naver 등)
```

### 인증 및 API 키 관리

| 환경변수 | 용도 | 발급처 | Phase 1 |
|---------|------|--------|---------|
| `DATA_GO_KR_API_KEY` | data.go.kr 전체 API 인증 (소상공인 #15012005 등) | 공공데이터포털 | ✅ 필수 |
| `KOSIS_API_KEY` | 통계청 KOSIS API (주민등록인구 등) | KOSIS | ✅ 필수 |
| `SEOUL_OPEN_DATA_KEY` | 서울 열린데이터광장 (생활인구 OA-15379, 추정매출 OA-15572, 지하철) | 서울열린데이터광장 | ✅ 필수 |
| `KAKAO_REST_API_KEY` | 카카오 로컬 API (지오코딩, 카테고리 검색) | Kakao Developers | ✅ 필수 |
| `NAVER_MAP_CLIENT_ID` | 네이버 지도 API (지도 렌더링) | Naver Cloud Platform | ✅ 필수 |
| `NAVER_MAP_CLIENT_SECRET` | 네이버 지도 API (지도 렌더링) | Naver Cloud Platform | ✅ 필수 |
| `NAVER_CLIENT_ID` | 네이버 검색 API (**데이터랩 제외** — DB 저장 금지로 상업 서비스 불가) | Naver Developers | 🚫 [Phase 2] |
| `NAVER_CLIENT_SECRET` | 네이버 검색 API (**데이터랩 제외** — DB 저장 금지로 상업 서비스 불가) | Naver Developers | 🚫 [Phase 2] |
| `LURIS_API_KEY` | 토지이용규제정보 API | LURIS | 🚫 [Phase 2] |
| `LAW_API_KEY` | 국가법령정보 API | 법제처 | 🚫 [Phase 2] |
| `FRANCHISE_FTC_KEY` | 프랜차이즈 정보공개서 | 공정거래위원회 | 🚫 [Phase 2] |

> ⚠️ **localdata.go.kr 관련**: LocalData 인허가 API 2026-04-15 서비스 종료. 인허가 에이전트는 Phase 2이므로 현재 임팩트 없음. Phase 2 구현 시 반드시 data.go.kr 인허가 API로 재설계 필요.

- 모든 API 키는 `.env` 파일 또는 Kubernetes Secret으로 관리한다.
- `pydantic-settings`의 `BaseSettings`를 사용하여 타입 안전하게 로드한다.
- 키는 절대 로그에 기록하지 않으며, `SecretStr` 타입을 사용한다.

### Rate Limiting 미들웨어

```python
# shared/rate_limiter.py
import asyncio
from dataclasses import dataclass

@dataclass
class RateLimitConfig:
    max_requests: int       # 허용 요청 수
    window_seconds: float   # 윈도우 크기(초)

class TokenBucketRateLimiter:
    """토큰 버킷 알고리즘 기반 Rate Limiter"""
    def __init__(self, config: RateLimitConfig):
        self.max_tokens = config.max_requests
        self.refill_rate = config.max_requests / config.window_seconds
        self.tokens = float(config.max_requests)
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """토큰 획득. 부족 시 대기."""
        async with self._lock:
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.refill_rate
                await asyncio.sleep(wait_time)
            self.tokens -= 1
```

각 MCP 서버별 Rate Limit 설정:

| MCP 서버 | 외부 API | 제한 | 설정값 | Phase 1 |
|----------|---------|------|--------|---------|
| 공공데이터 | data.go.kr (소상공인 #15012005) | 1,000회/일 (활용등록 시 최대 100,000/일) | max_requests=40, window_seconds=3600 | ✅ 활성 |
| 공공데이터 | KOSIS (주민등록인구) | 10,000회/일 | max_requests=400, window_seconds=3600 | ✅ 활성 |
| 공공데이터 | 서울열린데이터 (생활인구·추정매출·지하철) | 1,000회/일 | max_requests=40, window_seconds=3600 | ✅ 활성 |
| 지도/GIS | 카카오 로컬 | 100,000회/일 | max_requests=100, window_seconds=60 | ✅ 활성 |
| 지도/GIS | 네이버 지도 | 300,000회/월 | max_requests=7, window_seconds=60 | ✅ 활성 (렌더링용) |
| 지도/GIS | 카카오모빌리티 | 10,000회/일 | max_requests=400, window_seconds=3600 | ✅ 활성 |
| 부동산 | data.go.kr | 1,000회/일 | max_requests=40, window_seconds=3600 | 🚫 [Phase 2] |
| 뉴스/SNS | 네이버 검색 | 25,000회/일 | max_requests=1000, window_seconds=3600 | 🚫 [Phase 2] |
| 뉴스/SNS | 네이버 데이터랩 | 1,000회/일 | **⚠️ 사용 불가 — DB 저장 이용약관 위반** | ❌ 제외 |
| 규제/인허가 | law.go.kr | 제한 없음 (예의 사용) | max_requests=10, window_seconds=60 | 🚫 [Phase 2] |
| 금융/대출 | bizinfo.go.kr | 1,000회/일 | max_requests=40, window_seconds=3600 | 🚫 [Phase 2] |

### 요청/응답 로깅

모든 MCP 서버는 `structlog`을 사용하여 JSON 형식으로 로깅한다.

```python
# 로그 구조
{
    "timestamp": "2026-03-19T10:30:00.123Z",
    "level": "info",
    "mcp_server": "public-data",
    "tool": "get_floating_population",
    "event": "api_call",
    "external_api": "data.go.kr/15012005",
    "params": {"district_code": "1168010100", "quarter": "2025Q4"},
    "duration_ms": 342,
    "status": "success",
    "cache_hit": false,
    "request_id": "req_abc123"
}
```

- `level=info`: 정상 호출
- `level=warning`: Rate limit 임계치 도달 (80%), 캐시 미스
- `level=error`: API 실패, 타임아웃, 파싱 오류

### 공용 에러 클래스

```python
# shared/errors.py
class MCPToolError(Exception):
    """MCP 도구 실행 중 발생하는 기본 예외"""
    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}

class ExternalAPIError(MCPToolError):
    """외부 API 호출 실패"""
    pass

class RateLimitExceeded(MCPToolError):
    """Rate Limit 초과"""
    pass

class DataNotFoundError(MCPToolError):
    """요청한 데이터 없음"""
    pass

class DataParsingError(MCPToolError):
    """응답 파싱 실패"""
    pass
```

에러 코드 체계:

| 코드 | 의미 | HTTP 매핑 |
|------|------|-----------|
| `API_TIMEOUT` | 외부 API 타임아웃 (10초) | 504 |
| `API_ERROR` | 외부 API 비정상 응답 | 502 |
| `RATE_LIMITED` | Rate Limit 초과 | 429 |
| `NOT_FOUND` | 데이터 없음 | 404 |
| `PARSE_ERROR` | 응답 파싱 실패 | 500 |
| `AUTH_ERROR` | API 키 인증 실패 | 401 |
| `INVALID_PARAM` | 잘못된 파라미터 | 400 |

---

## MCP Server #1: 공공데이터 (Public Data)

### 1.1 서버 프로필

| 항목 | 내용 |
|------|------|
| **서버명** | `public-data-server` |
| **목적** | 상권분석에 필요한 인구, 매출, 점포 등 공공데이터 제공 |
| **래핑 API** | [Phase 1] 소상공인 상권정보 (data.go.kr #15012005), 서울 생활인구 (OA-15379), 서울 추정매출 (OA-15572), 서울 지하철 승하차, KOSIS 주민등록인구 / [Phase 2 추가 예정] 국세청 사업자등록상태조회 |

### 1.2 도구 목록

#### 1.2.1 `get_floating_population`

유동인구 데이터를 시간대/요일/성별/연령별로 조회한다.

```python
@mcp.tool()
async def get_floating_population(
    district_code: str,   # 상권코드 (10자리). 예: "1168010100"
    quarter: str,         # 분기. 형식: "2025Q4"
) -> FloatingPopulationResult:
    """특정 상권의 시간대/요일/성별/연령별 유동인구를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInUpjong`
  - 실제 유동인구 API: `http://apis.data.go.kr/B553077/api/open/sdsc2/baroApi`
  - 서비스명: `소상공인시장진흥공단_상가(상권)정보_유동인구`
  - API ID: `15012005` (상권정보 통합, 유동인구 세부 엔드포인트)
- **메서드**: `GET`
- **인증**: Query Parameter `serviceKey={DATA_GO_KR_API_KEY}` (URL 인코딩된 일반 인증키)
- **요청 파라미터**:
  ```
  serviceKey: str       # 인증키
  divId: str            # 구분ID ("trdarCd": 상권코드)
  key: str              # 상권코드 값
  indsLclsCd: str       # 업종대분류코드 (선택)
  indsMclsCd: str       # 업종중분류코드 (선택)
  indsSclsCd: str       # 업종소분류코드 (선택)
  stdrQuarterCd: str    # 기준분기코드 (예: "20254")
  type: str             # 응답형식 ("json")
  ```
- **응답 파싱**: `response["body"]["items"]["item"]` → 리스트

**반환 스키마**:

```python
class FloatingPopulationResult(BaseModel):
    district_code: str                    # 상권코드
    district_name: str                    # 상권명
    quarter: str                          # 기준분기 "2025Q4"
    total_population: int                 # 총 유동인구 수
    by_time: list[TimeSlotPopulation]     # 시간대별
    by_day: list[DayPopulation]           # 요일별
    by_gender: GenderPopulation           # 성별
    by_age: list[AgeGroupPopulation]      # 연령별
    data_source: str                      # "소상공인진흥공단_상권정보API"
    retrieved_at: datetime                # 조회 시각

class TimeSlotPopulation(BaseModel):
    time_slot: str       # "06-11", "11-14", "14-17", "17-21", "21-24", "00-06"
    population: int      # 해당 시간대 유동인구

class DayPopulation(BaseModel):
    day: str             # "월", "화", "수", "목", "금", "토", "일"
    population: int

class GenderPopulation(BaseModel):
    male: int
    female: int
    male_ratio: float    # 0.0 ~ 1.0
    female_ratio: float

class AgeGroupPopulation(BaseModel):
    age_group: str       # "10대", "20대", "30대", "40대", "50대", "60대이상"
    population: int
    ratio: float         # 0.0 ~ 1.0
```

**데이터 정규화**:
- API 원시 응답의 `nmPopltnCntXxx` 필드들을 `TimeSlotPopulation` 리스트로 변환
  - `MAG_06_11_FLPOP_CO` → time_slot="06-11"
  - `MAG_11_14_FLPOP_CO` → time_slot="11-14"
  - `MAG_14_17_FLPOP_CO` → time_slot="14-17"
  - `MAG_17_21_FLPOP_CO` → time_slot="17-21"
  - `MAG_21_24_FLPOP_CO` → time_slot="21-24"
  - `MAG_24_06_FLPOP_CO` → time_slot="00-06"
- 요일 필드: `MON_FLPOP_CO`, `TUES_FLPOP_CO`, `WED_FLPOP_CO`, `THUR_FLPOP_CO`, `FRI_FLPOP_CO`, `SAT_FLPOP_CO`, `SUN_FLPOP_CO`
- 성별 필드: `ML_FLPOP_CO` (남), `FML_FLPOP_CO` (여)
- 연령 필드: `AGRDE_10_FLPOP_CO`, `AGRDE_20_FLPOP_CO`, ..., `AGRDE_60_ABOVE_FLPOP_CO`
- 모든 인구 수는 `int`로 변환, `None`은 `0`으로 처리

---

#### 1.2.2 `get_estimated_revenue`

업종별 추정매출 데이터를 조회한다.

```python
@mcp.tool()
async def get_estimated_revenue(
    district_code: str,    # 상권코드 (10자리)
    industry_code: str,    # 업종소분류코드 (예: "CS200001" 한식음식점)
    quarter: str,          # 분기 "2025Q4"
) -> EstimatedRevenueResult:
    """특정 상권/업종의 추정매출 데이터를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInUpjong`
  - 매출 세부 엔드포인트: 상권정보 API 내 추정매출 조회
  - API ID: `15012005`
- **메서드**: `GET`
- **인증**: Query Parameter `serviceKey`
- **요청 파라미터**:
  ```
  serviceKey: str
  divId: str            # "trdarCd"
  key: str              # 상권코드
  indsSclsCd: str       # 업종소분류코드
  stdrQuarterCd: str    # 기준분기코드
  type: str             # "json"
  ```

**반환 스키마**:

```python
class EstimatedRevenueResult(BaseModel):
    district_code: str
    district_name: str
    industry_code: str
    industry_name: str
    quarter: str
    total_revenue: int                      # 총 추정매출 (원)
    total_count: int                        # 총 결제건수
    avg_revenue_per_store: int              # 점포당 평균매출
    by_time: list[TimeSlotRevenue]          # 시간대별
    by_day: list[DayRevenue]               # 요일별
    by_gender: GenderRevenue               # 성별
    by_age: list[AgeGroupRevenue]          # 연령별
    weekend_ratio: float                    # 주말매출비율 0.0~1.0
    data_source: str
    retrieved_at: datetime

class TimeSlotRevenue(BaseModel):
    time_slot: str       # "06-11", "11-14", "14-17", "17-21", "21-24", "00-06"
    revenue: int         # 매출액 (원)
    count: int           # 결제건수

class DayRevenue(BaseModel):
    day: str             # "월" ~ "일"
    revenue: int
    count: int

class GenderRevenue(BaseModel):
    male_revenue: int
    female_revenue: int
    male_count: int
    female_count: int

class AgeGroupRevenue(BaseModel):
    age_group: str       # "10대", "20대", "30대", "40대", "50대", "60대이상"
    revenue: int
    count: int
```

**데이터 정규화**:
- 매출 필드: `THSMON_SELNG_AMT` (당월매출), `THSMON_SELNG_CO` (당월건수)
- 시간대: `MAG_06_11_SELNG_AMT`, `MAG_11_14_SELNG_AMT`, ... (6개 슬롯)
- 요일: `MON_SELNG_AMT`, `TUES_SELNG_AMT`, ... (7일)
- 성별: `ML_SELNG_AMT`, `FML_SELNG_AMT`
- 연령: `AGRDE_10_SELNG_AMT`, ..., `AGRDE_60_ABOVE_SELNG_AMT`
- 모든 금액은 `int`(원 단위), 건수는 `int`

---

#### 1.2.3 `get_store_list`

특정 좌표 반경 내 점포(상가업소) 목록을 조회한다.

```python
@mcp.tool()
async def get_store_list(
    lat: float,            # 위도
    lng: float,            # 경도
    radius: int,           # 반경 (미터). 기본값 500, 최대 3000
    industry_code: str | None = None,  # 업종소분류코드 (선택)
) -> StoreListResult:
    """특정 좌표 반경 내 점포(상가업소) 목록을 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInRadius`
- **메서드**: `GET`
- **인증**: Query Parameter `serviceKey`
- **요청 파라미터**:
  ```
  serviceKey: str
  radius: int              # 반경 (미터)
  cx: float                # 경도 (lng)
  cy: float                # 위도 (lat)
  indsSclsCd: str          # 업종소분류코드 (선택)
  pageNo: int              # 페이지 번호
  numOfRows: int           # 페이지당 행 수 (최대 1000)
  type: str                # "json"
  ```
- **페이지네이션**: `pageNo`를 증가시키며 `totalCount`에 도달할 때까지 반복

**반환 스키마**:

```python
class StoreListResult(BaseModel):
    center_lat: float
    center_lng: float
    radius_m: int
    total_count: int
    stores: list[StoreInfo]
    data_source: str
    retrieved_at: datetime

class StoreInfo(BaseModel):
    store_id: str              # 상가업소번호
    store_name: str            # 상호명
    branch_name: str | None    # 지점명
    industry_large: str        # 업종대분류명
    industry_medium: str       # 업종중분류명
    industry_small: str        # 업종소분류명
    industry_code: str         # 업종소분류코드
    address_road: str          # 도로명주소
    address_jibun: str         # 지번주소
    lat: float                 # 위도
    lng: float                 # 경도
    floor: str | None          # 층정보
    distance_m: float | None   # 중심점 대비 거리 (계산값)
```

---

#### 1.2.4 `get_store_count_change`

특정 상권/업종의 분기별 개폐업 추이를 조회한다.

```python
@mcp.tool()
async def get_store_count_change(
    district_code: str,       # 상권코드
    industry_code: str,       # 업종소분류코드
    quarters: list[str],      # 조회 분기 목록 ["2024Q1", "2024Q2", ...]
) -> StoreCountChangeResult:
    """특정 상권/업종의 분기별 개업/폐업/증감 추이를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInUpjong` (상권 내 업종 점포 수 조회)
- 각 분기별로 개별 API 호출 후 비교
- **메서드**: `GET`
- **인증**: Query Parameter `serviceKey`

**반환 스키마**:

```python
class StoreCountChangeResult(BaseModel):
    district_code: str
    district_name: str
    industry_code: str
    industry_name: str
    quarterly_data: list[QuarterlyStoreCount]
    overall_trend: str           # "증가", "감소", "유지"
    net_change: int              # 전체 기간 순증감
    data_source: str
    retrieved_at: datetime

class QuarterlyStoreCount(BaseModel):
    quarter: str                 # "2024Q1"
    total_stores: int            # 총 점포 수
    new_stores: int              # 신규 개업
    closed_stores: int           # 폐업
    net_change: int              # 순증감 (new - closed)
    survival_rate: float | None  # 생존율 (이전 분기 대비)
```

**데이터 정규화**:
- 원시 필드: `STOR_CO` (점포수), `OPBIZ_STOR_CO` (개업점포수), `CLSBIZ_STOR_CO` (폐업점포수)
- `net_change = new_stores - closed_stores`
- `survival_rate = (이전 분기 total - 당분기 closed) / 이전 분기 total`
- `overall_trend`: net_change 합산이 양수면 "증가", 음수면 "감소", 0이면 "유지"

---

#### 1.2.5 `get_resident_population`

특정 지역의 거주(주민등록) 인구 통계를 조회한다.

```python
@mcp.tool()
async def get_resident_population(
    region_code: str,    # 행정동코드 (10자리). 예: "1168010100"
) -> ResidentPopulationResult:
    """특정 행정동의 주민등록 인구(거주인구) 통계를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://kosis.kr/openapi/Param/statisticsParameterData.do`
  - 통계표 ID: `DT_1B040A3` (주민등록인구 행정구역별/성별)
- **메서드**: `GET`
- **인증**: Query Parameter `apiKey={KOSIS_API_KEY}`
- **요청 파라미터**:
  ```
  method: str             # "getList"
  apiKey: str
  itmId: str              # "T2" (총인구수)
  objL1: str              # 행정구역코드
  objL2: str              # 성별코드 ("0" 전체, "1" 남, "2" 여)
  format: str             # "json"
  jsonVD: str             # "Y"
  prdSe: str              # "M" (월간)
  startPrdDe: str         # 시작기간 "202501"
  endPrdDe: str           # 종료기간 "202501"
  orgId: str              # "101" (통계청)
  tblId: str              # "DT_1B040A3"
  ```

**반환 스키마**:

```python
class ResidentPopulationResult(BaseModel):
    region_code: str
    region_name: str
    base_date: str                        # "2025-01" (기준년월)
    total_population: int
    male_population: int
    female_population: int
    total_households: int
    by_age: list[AgeGroupPopulation]      # 연령대별
    population_density: float | None       # 인구밀도 (명/km²)
    data_source: str                       # "통계청_KOSIS"
    retrieved_at: datetime
```

---

#### 1.2.6 `get_worker_population`

특정 지역의 직장인구(종사자) 통계를 조회한다.

```python
@mcp.tool()
async def get_worker_population(
    region_code: str,    # 행정동코드
) -> WorkerPopulationResult:
    """특정 행정동의 직장인구(종사자 수) 통계를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://kosis.kr/openapi/Param/statisticsParameterData.do`
  - 통계표 ID: `DT_1K52C01` (전국사업체조사 종사자수)
- **메서드**: `GET`
- **인증**: Query Parameter `apiKey`

**반환 스키마**:

```python
class WorkerPopulationResult(BaseModel):
    region_code: str
    region_name: str
    base_year: str                        # "2024"
    total_workers: int
    total_businesses: int
    by_industry: list[IndustryWorkers]    # 산업별 종사자
    avg_workers_per_business: float
    data_source: str                       # "통계청_KOSIS_전국사업체조사"
    retrieved_at: datetime

class IndustryWorkers(BaseModel):
    industry_category: str     # 산업대분류명
    industry_code: str         # 산업대분류코드
    worker_count: int
    business_count: int
```

---

#### 1.2.7 `get_seoul_living_population`

서울시 특정 행정동의 생활인구 데이터를 조회한다.

```python
@mcp.tool()
async def get_seoul_living_population(
    dong_code: str,    # 행정동코드 (8자리). 예: "11680101"
    date: str,         # 조회일자 "2025-03-15"
) -> SeoulLivingPopulationResult:
    """서울시 특정 행정동의 시간대별 생활인구를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `http://openapi.seoul.go.kr:8088/{SEOUL_OPEN_DATA_KEY}/json/SPOP_LOCAL_RESD_DONG/{startIndex}/{endIndex}/{date}`
  - 서비스명: `서울시 생활인구 내국인`
- **메서드**: `GET`
- **인증**: URL 경로에 API 키 포함
- **요청 URL 예시**:
  ```
  http://openapi.seoul.go.kr:8088/{KEY}/json/SPOP_LOCAL_RESD_DONG/1/24/20250315
  ```
- **페이지네이션**: `startIndex`, `endIndex`로 범위 지정 (시간대 24개)

**반환 스키마**:

```python
class SeoulLivingPopulationResult(BaseModel):
    dong_code: str
    dong_name: str
    date: str                              # "2025-03-15"
    total_living_population: float         # 총 생활인구 (추정치, 소수점)
    by_time: list[HourlyLivingPopulation]  # 시간대별 (0~23시)
    by_gender: GenderPopulation
    by_age: list[AgeGroupPopulation]
    data_source: str                        # "서울열린데이터광장_생활인구"
    retrieved_at: datetime

class HourlyLivingPopulation(BaseModel):
    hour: int            # 0 ~ 23
    population: float    # 해당 시간대 생활인구 (추정치)
```

**데이터 정규화**:
- 원시 필드: `TOT_LVPOP_CO` (총생활인구), `TMZON_00_LVPOP_CO` ~ `TMZON_23_LVPOP_CO` (시간대별)
- `ML_LVPOP_CO` (남성), `FML_LVPOP_CO` (여성)
- `AGRDE_0_9_LVPOP_CO`, `AGRDE_10_LVPOP_CO`, ..., `AGRDE_70_ABOVE_LVPOP_CO`
- 생활인구는 `float` 타입 (통계적 추정치이므로 소수점 허용)

---

#### 1.2.8 `get_card_sales`

서울시 특정 행정동/업종의 카드매출 통계를 조회한다.

```python
@mcp.tool()
async def get_card_sales(
    dong_code: str,         # 행정동코드 (8자리)
    industry_code: str,     # 업종코드
    quarter: str,           # 분기 "2025Q4"
) -> CardSalesResult:
    """서울시 특정 행정동/업종의 카드매출 통계를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `http://openapi.seoul.go.kr:8088/{SEOUL_OPEN_DATA_KEY}/json/VwsmAdstrdSelngQq/{startIndex}/{endIndex}/{quarter_code}`
  - 서비스명: `서울시 상권분석서비스(행정동별-업종별 매출현황)`
- **메서드**: `GET`
- **인증**: URL 경로에 API 키 포함

**반환 스키마**:

```python
class CardSalesResult(BaseModel):
    dong_code: str
    dong_name: str
    industry_code: str
    industry_name: str
    quarter: str
    total_sales: int                      # 총 카드매출 (원)
    total_count: int                      # 총 결제건수
    avg_sales_per_transaction: int        # 건당 평균매출
    by_day: list[DayRevenue]             # 요일별
    by_time: list[TimeSlotRevenue]       # 시간대별
    by_gender: GenderRevenue
    by_age: list[AgeGroupRevenue]
    data_source: str                      # "서울열린데이터광장_카드매출"
    retrieved_at: datetime
```

### 1.3 리소스 (Static Resources)

```python
@mcp.resource("public-data://industry-codes")
async def get_industry_codes() -> str:
    """소상공인진흥공단 업종분류코드 전체 목록을 반환합니다."""
    # 대분류(8) > 중분류(67) > 소분류(746) 계층 구조
    # 반환 형식: JSON
```

```python
@mcp.resource("public-data://district-codes")
async def get_district_codes() -> str:
    """전국 상권영역 코드 목록을 반환합니다."""
    # 상권유형: 골목상권, 발달상권, 전통시장, 관광특구
```

```python
@mcp.resource("public-data://dong-codes")
async def get_dong_codes() -> str:
    """전국 행정동 코드 목록을 반환합니다."""
```

### 1.4 캐싱 전략

| 도구 | Redis 키 패턴 | TTL | 비고 |
|------|--------------|-----|------|
| `get_floating_population` | `pub:fp:{district_code}:{quarter}` | 7일 | 분기 데이터, 변동 적음 |
| `get_estimated_revenue` | `pub:rev:{district_code}:{industry_code}:{quarter}` | 7일 | 분기 데이터 |
| `get_store_list` | `pub:store:{lat_3d}:{lng_3d}:{radius}:{industry_code}` | 24시간 | 좌표 소수 3자리 반올림 |
| `get_store_count_change` | `pub:scc:{district_code}:{industry_code}:{quarters_hash}` | 7일 | quarters 리스트의 MD5 해시 |
| `get_resident_population` | `pub:rpop:{region_code}` | 30일 | 월간 통계, 변동 적음 |
| `get_worker_population` | `pub:wpop:{region_code}` | 30일 | 연간 통계 |
| `get_seoul_living_population` | `pub:slp:{dong_code}:{date}` | 24시간 | 일별 데이터 |
| `get_card_sales` | `pub:card:{dong_code}:{industry_code}:{quarter}` | 7일 | 분기 데이터 |

**캐싱 구현 패턴**:

```python
# cache.py
import hashlib
import json
from shared.redis_client import redis

async def cached_call(key: str, ttl_seconds: int, fetch_fn):
    """캐시 우선 조회, 미스 시 fetch_fn 실행 후 저장"""
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    result = await fetch_fn()
    await redis.setex(key, ttl_seconds, json.dumps(result, default=str))
    return result
```

### 1.5 에러 처리

| 상황 | 처리 방식 |
|------|----------|
| API 타임아웃 (10초) | 1회 재시도 후 `ExternalAPIError(code="API_TIMEOUT")` 발생 |
| HTTP 4xx/5xx | 상태 코드별 분기: 401→`AUTH_ERROR`, 429→`RATE_LIMITED`, 그 외→`API_ERROR` |
| data.go.kr `resultCode != "00"` | `resultMsg` 파싱하여 `ExternalAPIError` 발생 |
| Rate Limit 초과 | 대기 후 재시도 (최대 3회, 지수 백오프 1s→2s→4s) |
| 데이터 미존재 | `DataNotFoundError(code="NOT_FOUND", message="해당 분기 데이터 없음")` |
| 응답 JSON 파싱 실패 | `DataParsingError(code="PARSE_ERROR")`, 원시 응답 로깅 |

---

## MCP Server #2: 지도/GIS (Maps)

### 2.1 서버 프로필

| 항목 | 내용 |
|------|------|
| **서버명** | `maps-server` |
| **목적** | 지오코딩, 주변 시설 검색, 도보 경로, 교통 접근성 분석 |
| **래핑 API** | 카카오 로컬 API, 네이버 지도 API, 카카오모빌리티 도보경로 API |

### 2.2 도구 목록

#### 2.2.1 `geocode`

주소를 좌표와 행정구역 코드로 변환한다.

```python
@mcp.tool()
async def geocode(
    address: str,   # 검색할 주소. 도로명 또는 지번 주소
) -> GeocodeResult:
    """주소를 위경도 좌표 및 행정구역 코드로 변환합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://dapi.kakao.com/v2/local/search/address.json`
- **메서드**: `GET`
- **인증**: 헤더 `Authorization: KakaoAK {KAKAO_REST_API_KEY}`
- **요청 파라미터**:
  ```
  query: str               # 검색 주소
  analyze_type: str         # "similar" (유사 주소 포함) 또는 "exact"
  page: int                 # 1 (기본값)
  size: int                 # 1 (첫 번째 결과만)
  ```
- **응답 경로**: `response["documents"][0]`

**반환 스키마**:

```python
class GeocodeResult(BaseModel):
    address: str               # 입력 주소
    lat: float                 # 위도 (WGS84)
    lng: float                 # 경도 (WGS84)
    address_road: str | None   # 도로명주소
    address_jibun: str | None  # 지번주소
    district_code: str         # 행정동코드 (10자리)
    dong_code: str             # 행정동코드 (8자리, 서울 생활인구용)
    sido: str                  # 시도명
    sigungu: str               # 시군구명
    dong: str                  # 행정동명
    confidence: str            # "exact", "similar", "none"
    data_source: str           # "카카오_로컬API"
    retrieved_at: datetime
```

**데이터 정규화**:
- 카카오 응답 `address.b_code`(법정동코드) → `district_code`
- 카카오 응답 `address.h_code`(행정동코드) → `dong_code` (앞 8자리)
- `x` → `lng`, `y` → `lat` (카카오는 x=경도, y=위도)
- `address_type`이 `ROAD`이면 `address_road`, `REGION`이면 `address_jibun` 우선 설정

---

#### 2.2.2 `reverse_geocode`

좌표를 주소 및 행정구역 코드로 변환한다.

```python
@mcp.tool()
async def reverse_geocode(
    lat: float,    # 위도
    lng: float,    # 경도
) -> ReverseGeocodeResult:
    """위경도 좌표를 주소 및 행정구역 코드로 변환합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://dapi.kakao.com/v2/local/geo/coord2regioncode.json`
- **메서드**: `GET`
- **인증**: 헤더 `Authorization: KakaoAK {KAKAO_REST_API_KEY}`
- **요청 파라미터**:
  ```
  x: float    # 경도
  y: float    # 위도
  ```
- **응답 경로**: `response["documents"]` (행정동 / 법정동 두 결과)

**반환 스키마**:

```python
class ReverseGeocodeResult(BaseModel):
    lat: float
    lng: float
    address: str               # 전체 주소
    district_code: str         # 행정동코드 (10자리)
    dong_code: str             # 행정동코드 (8자리)
    sido: str
    sigungu: str
    dong: str
    region_type: str           # "H" (행정동) 또는 "B" (법정동)
    data_source: str
    retrieved_at: datetime
```

---

#### 2.2.3 `search_nearby`

특정 좌표 반경 내 카테고리별 POI(장소)를 검색한다.

```python
@mcp.tool()
async def search_nearby(
    lat: float,            # 위도
    lng: float,            # 경도
    radius_m: int,         # 반경 (미터). 최대 20000
    category_code: str,    # 카카오 카테고리 코드 (예: "FD6" 음식점, "CE7" 카페)
) -> NearbySearchResult:
    """특정 좌표 반경 내 카테고리별 장소를 검색합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://dapi.kakao.com/v2/local/search/category.json`
- **메서드**: `GET`
- **인증**: 헤더 `Authorization: KakaoAK {KAKAO_REST_API_KEY}`
- **요청 파라미터**:
  ```
  category_group_code: str   # 카카오 카테고리 코드
  x: float                   # 경도
  y: float                   # 위도
  radius: int                # 반경 (미터)
  sort: str                  # "distance" (거리순)
  page: int                  # 1~45
  size: int                  # 1~15
  ```
- **카카오 카테고리 코드**:
  ```
  MT1: 대형마트        CS2: 편의점        PS3: 어린이집,유치원
  SC4: 학교            AC5: 학원          PK6: 주차장
  OL7: 주유소,충전소    SW8: 지하철역      BK9: 은행
  CT1: 문화시설        AG2: 중개업소       PO3: 공공기관
  AT4: 관광명소        AD5: 숙박          FD6: 음식점
  CE7: 카페            HP8: 병원          PM9: 약국
  ```
- **페이지네이션**: `is_end`가 `false`인 동안 `page` 증가 (최대 45페이지)

**반환 스키마**:

```python
class NearbySearchResult(BaseModel):
    center_lat: float
    center_lng: float
    radius_m: int
    category_code: str
    category_name: str
    total_count: int
    pois: list[POI]
    data_source: str
    retrieved_at: datetime

class POI(BaseModel):
    place_id: str            # 장소 고유 ID
    place_name: str          # 장소명
    category_name: str       # 카테고리명 (계층 구조: "음식점 > 한식")
    category_code: str       # 카테고리 코드
    phone: str | None        # 전화번호
    address_road: str        # 도로명주소
    address_jibun: str       # 지번주소
    lat: float               # 위도
    lng: float               # 경도
    distance_m: int          # 중심점 대비 거리 (미터)
    place_url: str           # 카카오맵 URL
```

---

#### 2.2.4 `search_keyword`

키워드로 장소를 검색한다.

```python
@mcp.tool()
async def search_keyword(
    keyword: str,                   # 검색 키워드
    lat: float | None = None,       # 중심 위도 (선택)
    lng: float | None = None,       # 중심 경도 (선택)
    radius_m: int | None = None,    # 반경 (선택, 최대 20000)
) -> KeywordSearchResult:
    """키워드로 장소를 검색합니다. 좌표 제공 시 해당 위치 중심으로 검색합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://dapi.kakao.com/v2/local/search/keyword.json`
- **메서드**: `GET`
- **인증**: 헤더 `Authorization: KakaoAK {KAKAO_REST_API_KEY}`
- **요청 파라미터**:
  ```
  query: str          # 검색 키워드
  x: float            # 경도 (선택)
  y: float            # 위도 (선택)
  radius: int         # 반경 (선택)
  sort: str           # "accuracy" 또는 "distance"
  page: int
  size: int
  ```

**반환 스키마**:

```python
class KeywordSearchResult(BaseModel):
    keyword: str
    total_count: int
    pois: list[POI]         # POI 스키마는 search_nearby와 동일
    data_source: str
    retrieved_at: datetime
```

---

#### 2.2.5 `get_walking_route`

두 지점 간 도보 경로 정보를 조회한다.

```python
@mcp.tool()
async def get_walking_route(
    origin_lat: float,     # 출발지 위도
    origin_lng: float,     # 출발지 경도
    dest_lat: float,       # 도착지 위도
    dest_lng: float,       # 도착지 경도
) -> WalkingRouteResult:
    """두 지점 간 도보 경로(거리, 소요시간)를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://apis-navi.kakaomobility.com/v1/directions`
  - 카카오모빌리티 도보 길찾기 (대안: `https://apis-navi.kakaomobility.com/v1/future/directions`)
- **메서드**: `GET`
- **인증**: 헤더 `Authorization: KakaoAK {KAKAO_REST_API_KEY}`
- **요청 파라미터**:
  ```
  origin: str          # "경도,위도" (예: "127.0276,37.4979")
  destination: str     # "경도,위도"
  vehicle_type: int    # 7 (도보)
  ```
- **참고**: 카카오모빌리티 도보 API가 비공개인 경우, 네이버 도보 경로 API 대체
  - 네이버 엔드포인트: `https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving` (차량 기준)
  - 도보 전용은 직선 거리 × 1.3 보정 계수로 추정

**반환 스키마**:

```python
class WalkingRouteResult(BaseModel):
    origin_lat: float
    origin_lng: float
    dest_lat: float
    dest_lng: float
    distance_m: int           # 도보 거리 (미터)
    duration_min: float       # 소요 시간 (분). 평균 보행속도 4km/h 기준
    straight_distance_m: int  # 직선 거리 (미터)
    route_exists: bool        # 경로 존재 여부
    data_source: str
    retrieved_at: datetime
```

---

#### 2.2.6 `get_transit_nearby`

특정 좌표 주변의 대중교통(지하철역, 버스정류장) 정보를 조회한다.

```python
@mcp.tool()
async def get_transit_nearby(
    lat: float,         # 위도
    lng: float,         # 경도
    radius_m: int = 500,  # 반경 (미터). 기본값 500
) -> TransitNearbyResult:
    """특정 좌표 주변의 지하철역/버스정류장을 조회합니다."""
```

**외부 API 호출**:
- 지하철역: `https://dapi.kakao.com/v2/local/search/category.json` (category_group_code=`SW8`)
- 버스정류장: `https://dapi.kakao.com/v2/local/search/keyword.json` (query="버스정류장")
- 두 API를 병렬 호출 (`asyncio.gather`)

**반환 스키마**:

```python
class TransitNearbyResult(BaseModel):
    center_lat: float
    center_lng: float
    radius_m: int
    subway_stations: list[SubwayStation]
    bus_stops: list[BusStop]
    nearest_subway_distance_m: int | None
    nearest_bus_distance_m: int | None
    transit_score: float          # 교통 접근성 점수 0~100
    data_source: str
    retrieved_at: datetime

class SubwayStation(BaseModel):
    station_name: str        # 역명
    line_name: str           # 노선명 (예: "2호선", "신분당선")
    lat: float
    lng: float
    distance_m: int          # 중심점 대비 거리

class BusStop(BaseModel):
    stop_name: str           # 정류장명
    stop_id: str | None      # 정류장 ID
    lat: float
    lng: float
    distance_m: int
```

**데이터 정규화**:
- `transit_score` 계산 로직:
  - 지하철 500m 이내: +40점, 1km 이내: +25점, 없음: 0점
  - 버스 300m 이내: +30점 × min(정류장수/3, 1), 500m 이내: +20점
  - 지하철 환승역(2개 이상 노선): 추가 +10점
  - 최대 100점 cap

---

#### 2.2.7 `get_category_pois`

특정 좌표 주변 주요 카테고리(학교, 병원, 마트 등) 시설을 일괄 검색한다.

```python
@mcp.tool()
async def get_category_pois(
    lat: float,          # 위도
    lng: float,          # 경도
    radius_m: int,       # 반경 (미터)
    category: str,       # 카테고리: "학교", "병원", "마트", "편의점", "카페", "음식점", "은행", "약국", "공공기관", "문화시설"
) -> CategoryPOIResult:
    """특정 좌표 주변 지정 카테고리 시설을 검색합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://dapi.kakao.com/v2/local/search/category.json`
- 카테고리 매핑:
  ```python
  CATEGORY_MAP = {
      "학교": "SC4",
      "병원": "HP8",
      "마트": "MT1",
      "편의점": "CS2",
      "카페": "CE7",
      "음식점": "FD6",
      "은행": "BK9",
      "약국": "PM9",
      "공공기관": "PO3",
      "문화시설": "CT1",
  }
  ```

**반환 스키마**:

```python
class CategoryPOIResult(BaseModel):
    center_lat: float
    center_lng: float
    radius_m: int
    category: str
    category_code: str
    total_count: int
    pois: list[POI]
    data_source: str
    retrieved_at: datetime
```

### 2.3 리소스

```python
@mcp.resource("maps://kakao-category-codes")
async def get_kakao_category_codes() -> str:
    """카카오 로컬 API 카테고리 코드 전체 목록을 반환합니다."""

@mcp.resource("maps://category-mapping")
async def get_category_mapping() -> str:
    """한글 카테고리명 → 카카오 카테고리 코드 매핑 테이블을 반환합니다."""
```

### 2.4 캐싱 전략

| 도구 | Redis 키 패턴 | TTL | 비고 |
|------|--------------|-----|------|
| `geocode` | `maps:geo:{address_hash}` | 30일 | 주소→좌표는 거의 변하지 않음 |
| `reverse_geocode` | `maps:rgeo:{lat_5d}:{lng_5d}` | 30일 | 좌표 소수 5자리 |
| `search_nearby` | `maps:nearby:{lat_3d}:{lng_3d}:{radius}:{category}` | 6시간 | 점포 변동 고려 |
| `search_keyword` | `maps:kw:{keyword_hash}:{lat_3d}:{lng_3d}:{radius}` | 6시간 | |
| `get_walking_route` | `maps:walk:{olat_4d}:{olng_4d}:{dlat_4d}:{dlng_4d}` | 7일 | 경로 변동 거의 없음 |
| `get_transit_nearby` | `maps:transit:{lat_3d}:{lng_3d}:{radius}` | 24시간 | |
| `get_category_pois` | `maps:cat:{lat_3d}:{lng_3d}:{radius}:{category}` | 6시간 | |

### 2.5 에러 처리

| 상황 | 처리 방식 |
|------|----------|
| 카카오 API 401 | API 키 만료/오류 → `AUTH_ERROR`, 키 재확인 알림 |
| 카카오 API 429 | 일일 한도 초과 → 네이버 API 폴백 (geocode, search 한정) |
| 주소 검색 결과 없음 | `confidence="none"` 반환, 에러 미발생 |
| 카카오모빌리티 도보 API 미응답 | 직선 거리 × 1.3 보정으로 추정값 반환, `route_exists=false` |

---

## MCP Server #3: 부동산 (Real Estate)

### 3.1 서버 프로필

| 항목 | 내용 |
|------|------|
| **서버명** | `real-estate-server` |
| **목적** | 상업용 부동산 실거래가, 임대료, 건물 정보, 토지이용 조회 |
| **래핑 API** | 국토교통부 실거래가 API, 건축물대장 API, 한국부동산원 임대동향조사 |

### 3.2 도구 목록

#### 3.2.1 `get_commercial_transactions`

상업용 부동산 실거래가 내역을 조회한다.

```python
@mcp.tool()
async def get_commercial_transactions(
    district_code_5: str,   # 법정동 앞 5자리 (시군구코드). 예: "11680"
    year_month: str,        # 조회 년월 "202503"
) -> CommercialTransactionResult:
    """특정 시군구의 상업/업무용 부동산 실거래가 내역을 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `http://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade`
  - 서비스명: `국토교통부_상업업무용 부동산 매매 실거래자료`
  - API ID: `15126463`
- **메서드**: `GET`
- **인증**: Query Parameter `serviceKey`
- **요청 파라미터**:
  ```
  serviceKey: str
  LAWD_CD: str          # 법정동 시군구코드 (5자리)
  DEAL_YMD: str         # 계약 년월 (6자리, "202503")
  pageNo: int
  numOfRows: int        # 최대 1000
  ```

**반환 스키마**:

```python
class CommercialTransactionResult(BaseModel):
    district_code_5: str
    year_month: str
    total_count: int
    transactions: list[Transaction]
    avg_price_per_pyeong: int | None     # 평당 평균가 (원)
    data_source: str                      # "국토교통부_상업용실거래가"
    retrieved_at: datetime

class Transaction(BaseModel):
    deal_date: str               # 거래일 "2025-03-15"
    deal_type: str               # "매매", "전세", "월세"
    property_type: str           # "상가", "오피스텔", "사무실" 등
    address_jibun: str           # 지번주소
    dong: str                    # 법정동
    floor: str | None            # 층
    area_m2: float               # 전용면적 (㎡)
    area_pyeong: float           # 전용면적 (평, 계산값)
    price_total: int             # 거래금액 (만원)
    price_per_m2: int            # ㎡당 가격 (만원)
    price_per_pyeong: int        # 평당 가격 (만원)
    deposit: int | None          # 보증금 (만원, 임대 시)
    monthly_rent: int | None     # 월세 (만원, 월세 시)
    build_year: int | None       # 건축년도
```

**데이터 정규화**:
- 면적 변환: `area_pyeong = area_m2 / 3.306`
- 가격 계산: `price_per_m2 = price_total / area_m2`, `price_per_pyeong = price_total / area_pyeong`
- `deal_date`: 원시 데이터의 `년`, `월`, `일` 필드 조합 → `"YYYY-MM-DD"`
- 거래금액: 원시 데이터의 쉼표 제거 후 `int` 변환

---

#### 3.2.2 `get_commercial_rent_index`

상업용 부동산 임대동향지수를 조회한다.

```python
@mcp.tool()
async def get_commercial_rent_index(
    region: str,       # 지역명 ("서울", "강남구" 등)
    quarter: str,      # 분기 "2025Q4"
) -> RentIndex:
    """상업용 부동산 임대동향지수(임대가격지수, 공실률 등)를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://kosis.kr/openapi/Param/statisticsParameterData.do`
  - 통계표: 한국부동산원 상업용부동산 임대동향조사
  - 조직ID: `408` (한국부동산원)
  - 통계표ID: `DT_408_2006_S0022` (상가 임대가격지수), `DT_408_2006_S0019` (오피스 공실률)
- **메서드**: `GET`
- **인증**: Query Parameter `apiKey`

**반환 스키마**:

```python
class RentIndex(BaseModel):
    region: str
    quarter: str
    retail_rent_index: float             # 상가 임대가격지수 (기준시점=100)
    office_rent_index: float             # 오피스 임대가격지수
    retail_rent_change_rate: float       # 상가 임대가격 변동률 (%)
    office_rent_change_rate: float       # 오피스 임대가격 변동률 (%)
    avg_retail_rent_per_m2: int | None   # 상가 ㎡당 평균 임대료 (원, 가용 시)
    avg_office_rent_per_m2: int | None   # 오피스 ㎡당 평균 임대료 (원, 가용 시)
    data_source: str
    retrieved_at: datetime
```

---

#### 3.2.3 `get_building_register`

건축물대장 정보를 조회한다.

```python
@mcp.tool()
async def get_building_register(
    address: str,    # 건물 주소 (도로명 또는 지번)
) -> BuildingInfo:
    """건축물대장 정보(건물 개요, 용도, 면적, 층수 등)를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `http://apis.data.go.kr/1613000/BldRgstService_v2/getBrTitleInfo`
  - 서비스명: `국토교통부_건축물대장정보 서비스`
  - API ID: `15044713`
- **메서드**: `GET`
- **인증**: Query Parameter `serviceKey`
- **요청 파라미터**:
  ```
  serviceKey: str
  sigunguCd: str       # 시군구코드 (5자리)
  bjdongCd: str        # 법정동코드 (5자리)
  platGbCd: str        # 대지구분코드 ("0": 대지, "1": 산)
  bun: str             # 번 (4자리 zero-padding)
  ji: str              # 지 (4자리 zero-padding)
  numOfRows: int
  pageNo: int
  type: str            # "json"
  ```
- **주소 파싱**: 입력 주소를 먼저 `geocode` 도구로 변환하여 시군구코드, 법정동코드, 번지 추출

**반환 스키마**:

```python
class BuildingInfo(BaseModel):
    address: str                    # 조회 주소
    address_road: str | None
    address_jibun: str | None
    building_name: str | None       # 건물명
    main_use: str                   # 주용도 (예: "제1종근린생활시설")
    etc_use: str | None             # 기타용도
    total_area_m2: float            # 연면적 (㎡)
    building_area_m2: float         # 건축면적 (㎡)
    land_area_m2: float             # 대지면적 (㎡)
    floor_area_ratio: float         # 용적률 (%)
    building_coverage_ratio: float  # 건폐율 (%)
    total_floors_above: int         # 지상 층수
    total_floors_below: int         # 지하 층수
    build_year: int | None          # 사용승인일 기준 년도
    approval_date: str | None       # 사용승인일 "YYYYMMDD"
    structure: str | None           # 구조 (예: "철근콘크리트구조")
    elevator_count: int             # 승강기 수
    parking_count: int              # 주차장 수
    data_source: str                # "국토교통부_건축물대장"
    retrieved_at: datetime
```

---

#### 3.2.4 `get_vacancy_rate`

상업용 부동산 공실률을 조회한다.

```python
@mcp.tool()
async def get_vacancy_rate(
    region: str,       # 지역명 ("서울", "강남구" 등)
    quarter: str,      # 분기 "2025Q4"
) -> VacancyInfo:
    """상업용 부동산(상가/오피스) 공실률을 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://kosis.kr/openapi/Param/statisticsParameterData.do`
  - 조직ID: `408`, 통계표ID: `DT_408_2006_S0019`
- **인증**: Query Parameter `apiKey`

**반환 스키마**:

```python
class VacancyInfo(BaseModel):
    region: str
    quarter: str
    retail_vacancy_rate: float          # 상가 공실률 (%, 예: 8.5)
    office_vacancy_rate: float          # 오피스 공실률 (%)
    retail_vacancy_change: float        # 상가 공실률 변동 (전분기 대비, %p)
    office_vacancy_change: float        # 오피스 공실률 변동 (%p)
    data_source: str
    retrieved_at: datetime
```

---

#### 3.2.5 `get_land_use_plan`

특정 좌표의 토지이용계획(용도지역, 용도지구) 정보를 조회한다.

```python
@mcp.tool()
async def get_land_use_plan(
    lat: float,    # 위도
    lng: float,    # 경도
) -> LandUseInfo:
    """특정 위치의 토지이용계획(용도지역/지구/구역) 정보를 조회합니다."""
```

**외부 API 호출**:
- 1단계: `reverse_geocode(lat, lng)`로 지번주소 확보
- 2단계: 토지이용규제정보서비스 API 호출
- **엔드포인트**: `https://api.luris.go.kr/luris/api/LandUseReg`
  - 또는 data.go.kr 경유: `http://apis.data.go.kr/1611000/nsdi/LandUseService/attr/getLandUseAttr`
- **메서드**: `GET`
- **인증**: Query Parameter `serviceKey` 또는 `authkey={LURIS_API_KEY}`
- **요청 파라미터**:
  ```
  pnu: str              # 19자리 필지고유번호 (시도2+시군구3+읍면동3+리2+대지구분1+본번4+부번4)
  format: str           # "json"
  numOfRows: int
  pageNo: int
  ```

**반환 스키마**:

```python
class LandUseInfo(BaseModel):
    lat: float
    lng: float
    address_jibun: str
    pnu: str                              # 필지고유번호 (19자리)
    land_category: str                    # 지목 ("대", "전", "답" 등)
    land_area_m2: float                   # 필지면적 (㎡)
    zoning_main: str                      # 용도지역 (예: "제2종일반주거지역", "일반상업지역")
    zoning_sub: list[str]                 # 용도지구 (예: ["미관지구", "방화지구"])
    zoning_area: list[str]                # 용도구역 (예: ["개발제한구역"])
    building_coverage_limit: float | None  # 건폐율 상한 (%)
    floor_area_ratio_limit: float | None   # 용적률 상한 (%)
    height_limit: float | None             # 높이제한 (미터)
    restrictions: list[str]                # 기타 규제사항
    data_source: str
    retrieved_at: datetime
```

---

#### 3.2.6 `estimate_premium`

상가 권리금을 추정한다 (내부 계산 로직).

```python
@mcp.tool()
async def estimate_premium(
    district_code: str,       # 상권코드
    industry_code: str,       # 업종소분류코드
    monthly_revenue: int,     # 월 평균매출 (원)
) -> PremiumEstimate:
    """상가 권리금을 업종/매출 기준으로 추정합니다."""
```

**외부 API 호출**: 없음 (내부 로직 + 캐싱된 데이터 활용)
- `get_estimated_revenue`로 해당 상권/업종 평균매출 조회
- `get_commercial_transactions`로 해당 상권 거래 시세 참조

**반환 스키마**:

```python
class PremiumEstimate(BaseModel):
    district_code: str
    district_name: str
    industry_code: str
    industry_name: str
    monthly_revenue: int                   # 입력 월매출
    avg_monthly_revenue_area: int          # 해당 상권 업종 평균 월매출
    estimated_premium_low: int             # 권리금 하한 추정 (원)
    estimated_premium_mid: int             # 권리금 중간 추정 (원)
    estimated_premium_high: int            # 권리금 상한 추정 (원)
    calculation_method: str                # 산출 방식 설명
    factors: PremiumFactors
    disclaimer: str                        # 면책 문구
    data_source: str
    retrieved_at: datetime

class PremiumFactors(BaseModel):
    revenue_multiplier: float              # 매출 배수 (업종별 기본 배수)
    location_factor: float                 # 입지 계수 (0.5~2.0)
    industry_trend_factor: float           # 업종 성장/쇠퇴 계수 (0.7~1.3)
    competition_factor: float              # 경쟁 강도 계수 (0.6~1.2)
```

**산출 로직**:
- `base_premium = monthly_revenue × revenue_multiplier × 12` (연매출 기준)
- `adjusted_premium = base_premium × location_factor × industry_trend_factor × competition_factor`
- `estimated_premium_low = adjusted_premium × 0.7`
- `estimated_premium_mid = adjusted_premium`
- `estimated_premium_high = adjusted_premium × 1.3`
- 업종별 `revenue_multiplier`: 음식점 3~5, 카페 2~3, 편의점 2~4, 미용실 3~5

### 3.3 리소스

```python
@mcp.resource("real-estate://sigungu-codes")
async def get_sigungu_codes() -> str:
    """전국 시군구 코드(5자리) 전체 목록을 반환합니다."""

@mcp.resource("real-estate://zoning-types")
async def get_zoning_types() -> str:
    """용도지역/용도지구/용도구역 유형 코드 및 설명을 반환합니다."""
```

### 3.4 캐싱 전략

| 도구 | Redis 키 패턴 | TTL | 비고 |
|------|--------------|-----|------|
| `get_commercial_transactions` | `re:txn:{district_code_5}:{year_month}` | 7일 | 월별 실거래 데이터 |
| `get_commercial_rent_index` | `re:rent:{region_hash}:{quarter}` | 30일 | 분기 통계 |
| `get_building_register` | `re:bldg:{address_hash}` | 90일 | 건축물대장은 거의 변동 없음 |
| `get_vacancy_rate` | `re:vac:{region_hash}:{quarter}` | 30일 | 분기 통계 |
| `get_land_use_plan` | `re:land:{lat_5d}:{lng_5d}` | 90일 | 용도지역은 거의 변동 없음 |
| `estimate_premium` | `re:prem:{district}:{industry}:{revenue_bucket}` | 24시간 | revenue_bucket=만원 단위 버킷 |

### 3.5 에러 처리

| 상황 | 처리 방식 |
|------|----------|
| 실거래 데이터 미존재 | `transactions=[]`, `total_count=0` 반환 (에러 아님) |
| 건축물대장 미조회 | 주소 파싱 실패 시 `INVALID_PARAM`, 결과 없을 시 `NOT_FOUND` |
| LURIS API 장애 | `DataNotFoundError`, 토지이용 정보 미포함 상태로 반환 |
| 권리금 추정 데이터 부족 | `disclaimer`에 "참고 데이터 부족으로 추정 신뢰도 낮음" 명시 |

---

## MCP Server #4: 뉴스/SNS (News & Social)

### 4.1 서버 프로필

| 항목 | 내용 |
|------|------|
| **서버명** | `news-social-server` |
| **목적** | 상권/업종 관련 뉴스, 블로그, 검색 트렌드, 감성 분석 제공 |
| **래핑 API** | 네이버 검색 API, 네이버 데이터랩 API, Google Trends (pytrends) |

### 4.2 도구 목록

#### 4.2.1 `search_news`

키워드 관련 뉴스 기사를 검색한다.

```python
@mcp.tool()
async def search_news(
    keyword: str,            # 검색 키워드 (예: "강남역 상권", "카페 창업")
    period_days: int = 30,   # 최근 N일 이내
    count: int = 10,         # 최대 결과 수 (최대 100)
) -> NewsSearchResult:
    """키워드 관련 최신 뉴스 기사를 검색합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://openapi.naver.com/v1/search/news.json`
- **메서드**: `GET`
- **인증**: 헤더
  ```
  X-Naver-Client-Id: {NAVER_CLIENT_ID}
  X-Naver-Client-Secret: {NAVER_CLIENT_SECRET}
  ```
- **요청 파라미터**:
  ```
  query: str           # 검색어
  display: int         # 결과 수 (최대 100)
  start: int           # 시작 위치 (1~1000)
  sort: str            # "date" (날짜순) 또는 "sim" (유사도순)
  ```
- **기간 필터**: 네이버 검색 API는 기간 파라미터 미지원 → `pubDate` 파싱 후 클라이언트 측 필터링

**반환 스키마**:

```python
class NewsSearchResult(BaseModel):
    keyword: str
    period_days: int
    total_count: int                    # 검색된 전체 건수
    returned_count: int                 # 반환된 건수
    articles: list[NewsArticle]
    data_source: str                     # "네이버_검색API"
    retrieved_at: datetime

class NewsArticle(BaseModel):
    title: str                  # 기사 제목 (HTML 태그 제거)
    description: str            # 기사 요약 (HTML 태그 제거)
    link: str                   # 기사 원문 URL
    original_link: str          # 언론사 원문 URL
    pub_date: datetime          # 게시일
    source: str | None          # 언론사명 (파싱 가능 시)
```

**데이터 정규화**:
- HTML 태그 제거: `<b>`, `</b>`, `&quot;`, `&amp;` 등 처리
- `pubDate` RFC 822 형식 → `datetime` 변환
- `period_days` 기준으로 오래된 기사 필터링
- 결과를 `pub_date` 기준 최신순 정렬

---

#### 4.2.2 `search_blogs`

키워드/지역 관련 블로그 포스트를 검색한다.

```python
@mcp.tool()
async def search_blogs(
    keyword: str,                    # 검색 키워드
    location: str | None = None,     # 지역명 (선택, 예: "강남역")
    count: int = 10,                 # 최대 결과 수
) -> BlogSearchResult:
    """키워드 관련 블로그 포스트를 검색합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://openapi.naver.com/v1/search/blog.json`
- **메서드**: `GET`
- **인증**: 동일 (X-Naver-Client-Id, X-Naver-Client-Secret)
- **요청 파라미터**:
  ```
  query: str           # location이 있으면 "{location} {keyword}"로 조합
  display: int
  start: int
  sort: str            # "date" 또는 "sim"
  ```

**반환 스키마**:

```python
class BlogSearchResult(BaseModel):
    keyword: str
    location: str | None
    total_count: int
    returned_count: int
    posts: list[BlogPost]
    data_source: str
    retrieved_at: datetime

class BlogPost(BaseModel):
    title: str               # 포스트 제목
    description: str         # 포스트 요약
    link: str                # 포스트 URL
    blogger_name: str        # 블로거 이름
    blogger_link: str        # 블로그 URL
    post_date: str           # 게시일 "YYYYMMDD"
```

---

#### 4.2.3 `get_search_trend`

네이버 데이터랩 검색어 트렌드를 조회한다.

```python
@mcp.tool()
async def get_search_trend(
    keywords: list[str],       # 검색어 목록 (최대 5개)
    period_months: int = 12,   # 최근 N개월
) -> TrendData:
    """네이버 검색어 트렌드(상대적 검색량)를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://openapi.naver.com/v1/datalab/search`
- **메서드**: `POST`
- **인증**: 헤더 X-Naver-Client-Id, X-Naver-Client-Secret
- **요청 본문** (JSON):
  ```json
  {
      "startDate": "2025-03-19",
      "endDate": "2026-03-19",
      "timeUnit": "month",
      "keywordGroups": [
          {"groupName": "카페 창업", "keywords": ["카페 창업", "카페창업"]},
          {"groupName": "음식점 창업", "keywords": ["음식점 창업", "음식점창업"]}
      ]
  }
  ```
- **timeUnit**: `"date"` (일간), `"week"` (주간), `"month"` (월간)

**반환 스키마**:

```python
class TrendData(BaseModel):
    keywords: list[str]
    period_start: str                  # "2025-03-19"
    period_end: str                    # "2026-03-19"
    time_unit: str                     # "month"
    trends: list[KeywordTrend]
    data_source: str                    # "네이버_데이터랩"
    retrieved_at: datetime

class KeywordTrend(BaseModel):
    keyword: str
    data_points: list[TrendPoint]
    avg_ratio: float                   # 기간 평균 비율
    trend_direction: str               # "상승", "하락", "유지"
    peak_period: str                   # 최고점 기간

class TrendPoint(BaseModel):
    period: str         # "2025-03" (월간) 또는 "2025-03-19" (일간)
    ratio: float        # 상대적 검색량 (0~100, 최대치=100)
```

**데이터 정규화**:
- `trend_direction` 결정: 최근 3개월 평균 vs 이전 3개월 평균 비교
  - 10% 이상 증가 → "상승", 10% 이상 감소 → "하락", 그 외 → "유지"
- `peak_period`: `ratio`가 최대인 `period` 값

---

#### 4.2.4 `get_google_trend`

Google Trends 데이터를 조회한다.

```python
@mcp.tool()
async def get_google_trend(
    keywords: list[str],       # 검색어 목록 (최대 5개)
    geo: str = "KR",           # 지역 코드 (기본: 한국)
    period: str = "12m",       # 기간 ("3m", "6m", "12m", "5y")
) -> TrendData:
    """Google Trends 검색어 트렌드를 조회합니다."""
```

**외부 API 호출**:
- **라이브러리**: `pytrends` (`TrendReq`)
- **내부 호출**:
  ```python
  from pytrends.request import TrendReq
  pytrends = TrendReq(hl="ko", tz=540)
  pytrends.build_payload(keywords, cat=0, timeframe="today 12-m", geo=geo)
  df = pytrends.interest_over_time()
  ```
- **Rate Limit**: Google은 비공식 API이므로 요청 간 2초 딜레이 적용
- **인증**: 불필요 (비공식 API)

**반환 스키마**: `TrendData`와 동일 구조 (`data_source: "Google_Trends"`)

---

#### 4.2.5 `analyze_sentiment`

텍스트 목록의 감성(긍정/부정/중립)을 분석한다.

```python
@mcp.tool()
async def analyze_sentiment(
    texts: list[str],    # 분석할 텍스트 목록 (뉴스 제목, 블로그 요약 등)
) -> SentimentResult:
    """텍스트 목록의 감성(긍정/부정/중립)을 분석합니다."""
```

**외부 API 호출**: 없음 (내부 LLM 호출 또는 로컬 모델)
- 방법 1: LLM 기반 (Claude/GPT에 감성 분석 프롬프트)
- 방법 2: 로컬 모델 (`transformers` 라이브러리, `klue/bert-base` 등)
- 기본 구현: LLM 기반 (에이전트 자체 LLM 활용)

**반환 스키마**:

```python
class SentimentResult(BaseModel):
    total_count: int
    positive_count: int
    negative_count: int
    neutral_count: int
    positive_ratio: float            # 0.0~1.0
    negative_ratio: float
    neutral_ratio: float
    overall_sentiment: str           # "긍정", "부정", "중립"
    details: list[TextSentiment]
    data_source: str                  # "internal_llm" 또는 "klue_bert"
    retrieved_at: datetime

class TextSentiment(BaseModel):
    text: str                        # 원문 (최대 200자로 절단)
    sentiment: str                   # "긍정", "부정", "중립"
    confidence: float                # 신뢰도 0.0~1.0
    keywords: list[str]              # 핵심 키워드 (최대 5개)
```

### 4.3 리소스

```python
@mcp.resource("news-social://industry-keywords")
async def get_industry_keywords() -> str:
    """업종별 관련 검색 키워드 매핑 테이블을 반환합니다."""
    # 예: "CS200001" (한식음식점) → ["한식", "한식당", "한정식", "백반"]
```

### 4.4 캐싱 전략

| 도구 | Redis 키 패턴 | TTL | 비고 |
|------|--------------|-----|------|
| `search_news` | `news:search:{keyword_hash}:{period_days}` | 1시간 | 뉴스는 빠르게 갱신 |
| `search_blogs` | `news:blog:{keyword_hash}:{location_hash}` | 3시간 | |
| `get_search_trend` | `news:trend:{keywords_hash}:{period_months}` | 24시간 | 일 단위 변동 |
| `get_google_trend` | `news:gtrend:{keywords_hash}:{geo}:{period}` | 24시간 | |
| `analyze_sentiment` | `news:sent:{texts_hash}` | 7일 | 동일 텍스트는 결과 불변 |

### 4.5 에러 처리

| 상황 | 처리 방식 |
|------|----------|
| 네이버 검색 결과 0건 | `articles=[]` 또는 `posts=[]` 반환, 에러 미발생 |
| 네이버 데이터랩 429 | 지수 백오프 후 재시도 (최대 3회) |
| pytrends 429 (Google 차단) | `TooManyRequestsError` → 10초 대기 후 1회 재시도, 실패 시 빈 결과 반환 |
| 감성 분석 LLM 호출 실패 | 전체 텍스트를 "중립"으로 처리, `confidence=0.0` |
| HTML 태그 파싱 실패 | 원시 텍스트 그대로 반환, 로그 경고 |

---

## MCP Server #5: 규제/인허가 (Regulatory)

### 5.1 서버 프로필

| 항목 | 내용 |
|------|------|
| **서버명** | `regulatory-server` |
| **목적** | 창업 관련 법령, 조례, 용도지역, 인허가 요건, 학교정화구역 조회 |
| **래핑 API** | 국가법령정보센터 API, 자치법규정보시스템, 토지이용규제정보서비스 |

### 5.2 도구 목록

#### 5.2.1 `search_law`

법령 검색을 수행한다.

```python
@mcp.tool()
async def search_law(
    keyword: str,                 # 검색 키워드 (예: "식품위생법", "학교환경위생정화구역")
    law_type: str = "all",        # 법령 유형: "all", "법률", "대통령령", "부령", "행정규칙"
) -> LawSearchResult:
    """키워드로 법령을 검색합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://www.law.go.kr/DRF/lawSearch.do`
- **메서드**: `GET`
- **인증**: Query Parameter `OC={LAW_API_KEY}` (Open API 인증키)
- **요청 파라미터**:
  ```
  OC: str              # 인증키
  target: str          # "law" (법령)
  type: str            # "JSON"
  query: str           # 검색어
  display: int         # 결과 수 (최대 100)
  page: int            # 페이지
  sort: str            # "prdt" (공포일순) 또는 "efdt" (시행일순)
  LicGubun: str        # 법령유형 (선택): "법률", "대통령령", "총리령,부령"
  ```

**반환 스키마**:

```python
class LawSearchResult(BaseModel):
    keyword: str
    law_type: str
    total_count: int
    articles: list[LawArticle]
    data_source: str               # "국가법령정보센터"
    retrieved_at: datetime

class LawArticle(BaseModel):
    law_id: str                    # 법령 ID (MST)
    law_name: str                  # 법령명
    law_type: str                  # "법률", "대통령령", "부령" 등
    proclamation_date: str         # 공포일 "YYYYMMDD"
    enforcement_date: str          # 시행일 "YYYYMMDD"
    proclamation_number: str       # 공포번호
    law_url: str                   # 법령 상세 URL
    is_current: bool               # 현행 여부
```

---

#### 5.2.2 `get_local_ordinance`

지방자치단체 조례를 검색한다.

```python
@mcp.tool()
async def get_local_ordinance(
    region: str,       # 지역명 (예: "서울특별시", "강남구")
    keyword: str,      # 검색 키워드 (예: "식품접객업", "영업시간")
) -> OrdinanceSearchResult:
    """지방자치단체 조례를 검색합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://www.law.go.kr/DRF/lawSearch.do`
  - 자치법규 검색: `target=ordin`
  - 또는 자치법규정보시스템: `https://www.elis.go.kr/openapi/ordin`
- **메서드**: `GET`
- **인증**: Query Parameter `OC={LAW_API_KEY}`
- **요청 파라미터**:
  ```
  OC: str
  target: str          # "ordin" (자치법규)
  type: str            # "JSON"
  query: str           # "{region} {keyword}"
  display: int
  page: int
  ```

**반환 스키마**:

```python
class OrdinanceSearchResult(BaseModel):
    region: str
    keyword: str
    total_count: int
    ordinances: list[Ordinance]
    data_source: str
    retrieved_at: datetime

class Ordinance(BaseModel):
    ordinance_id: str          # 조례 ID
    ordinance_name: str        # 조례명
    region: str                # 자치단체명
    ordinance_type: str        # "조례", "규칙"
    proclamation_date: str     # 공포일
    enforcement_date: str      # 시행일
    ordinance_url: str         # 상세 URL
    is_current: bool
```

---

#### 5.2.3 `get_zoning_info`

특정 좌표의 용도지역 규제 정보를 조회한다.

```python
@mcp.tool()
async def get_zoning_info(
    lat: float,    # 위도
    lng: float,    # 경도
) -> ZoningInfo:
    """특정 위치의 용도지역/지구/구역 및 건축 제한을 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://api.luris.go.kr/luris/api/LandUseReg`
  - 또는 `http://apis.data.go.kr/1611000/nsdi/LandUseService/attr/getLandUseAttr`
- **메서드**: `GET`
- **인증**: Query Parameter `authkey={LURIS_API_KEY}` 또는 `serviceKey`
- **사전 처리**: `reverse_geocode` → PNU(필지고유번호) 생성

**반환 스키마**:

```python
class ZoningInfo(BaseModel):
    lat: float
    lng: float
    address: str
    pnu: str                                # 필지고유번호
    zoning_main: str                        # 용도지역 (예: "일반상업지역")
    zoning_sub: list[str]                   # 용도지구
    zoning_area: list[str]                  # 용도구역
    permitted_uses: list[str]               # 허용 용도 (업종 목록)
    conditional_uses: list[str]             # 조건부 허용 용도
    prohibited_uses: list[str]              # 금지 용도
    building_coverage_limit: float | None   # 건폐율 상한 (%)
    floor_area_ratio_limit: float | None    # 용적률 상한 (%)
    height_limit_m: float | None            # 높이 제한 (미터)
    special_notes: list[str]                # 특이사항
    data_source: str
    retrieved_at: datetime
```

**데이터 정규화**:
- 용도지역별 건폐율/용적률 상한 매핑 (내부 참조 테이블):
  ```
  제1종전용주거지역: 건폐율 50%, 용적률 50~100%
  제2종전용주거지역: 건폐율 50%, 용적률 100~150%
  제1종일반주거지역: 건폐율 60%, 용적률 100~200%
  제2종일반주거지역: 건폐율 60%, 용적률 150~250%
  제3종일반주거지역: 건폐율 50%, 용적률 200~300%
  준주거지역: 건폐율 70%, 용적률 200~500%
  중심상업지역: 건폐율 90%, 용적률 400~1500%
  일반상업지역: 건폐율 80%, 용적률 300~1300%
  근린상업지역: 건폐율 70%, 용적률 200~900%
  유통상업지역: 건폐율 80%, 용적률 200~1100%
  전용공업지역: 건폐율 70%, 용적률 150~300%
  일반공업지역: 건폐율 70%, 용적률 200~350%
  준공업지역: 건폐율 70%, 용적률 200~400%
  ```

---

#### 5.2.4 `get_permit_requirements`

특정 업종의 인허가 요건(필요 서류, 시설 기준, 면적 기준 등)을 조회한다.

```python
@mcp.tool()
async def get_permit_requirements(
    industry_code: str,    # 업종소분류코드 (예: "CS200001" 한식음식점)
) -> PermitRequirementResult:
    """특정 업종의 창업 시 필요한 인허가 요건을 조회합니다."""
```

**외부 API 호출**:
- 법령 검색 API를 통해 관련 법령 조회 후, 내부 매핑 테이블과 결합
- 1단계: 업종코드 → 관련 법령 키워드 매핑 (내부 테이블)
  ```python
  INDUSTRY_LAW_MAP = {
      "CS200001": {"keyword": "식품위생법", "permit": "식품접객업 영업신고"},
      "CS200002": {"keyword": "식품위생법", "permit": "식품접객업 영업신고"},
      "CS300001": {"keyword": "공중위생관리법", "permit": "미용업 신고"},
      # ...
  }
  ```
- 2단계: `search_law` 호출로 최신 법령 내용 확인

**반환 스키마**:

```python
class PermitRequirementResult(BaseModel):
    industry_code: str
    industry_name: str
    requirements: list[PermitRequirement]
    total_estimated_days: int              # 예상 소요일
    total_estimated_cost: int              # 예상 비용 (원)
    related_laws: list[str]                # 관련 법령명
    data_source: str
    retrieved_at: datetime

class PermitRequirement(BaseModel):
    permit_name: str              # 인허가명 (예: "식품접객업 영업신고")
    issuing_agency: str           # 발급기관 (예: "관할 구청 위생과")
    required_documents: list[str] # 필요 서류
    facility_standards: list[str] # 시설 기준
    area_requirement: str | None  # 면적 기준 (예: "조리장 면적 ≥ 영업장 면적의 1/3")
    estimated_days: int           # 처리 예상 소요일
    estimated_cost: int           # 예상 비용 (원)
    notes: list[str]              # 참고사항
```

---

#### 5.2.5 `check_school_zone`

특정 좌표가 학교정화구역(절대정화구역, 상대정화구역) 내에 있는지 확인한다.

```python
@mcp.tool()
async def check_school_zone(
    lat: float,    # 위도
    lng: float,    # 경도
) -> SchoolZoneInfo:
    """특정 위치가 학교정화구역(절대/상대) 내에 있는지 확인합니다."""
```

**외부 API 호출**:
- 1단계: 카카오 로컬 API로 반경 200m 내 학교 검색 (`category_group_code=SC4`)
  - **엔드포인트**: `https://dapi.kakao.com/v2/local/search/category.json`
- 2단계: 각 학교까지의 거리 계산
  - 절대정화구역: 학교 출입문 기준 직선 50m 이내
  - 상대정화구역: 학교 경계선 기준 직선 200m 이내

**반환 스키마**:

```python
class SchoolZoneInfo(BaseModel):
    lat: float
    lng: float
    is_absolute_zone: bool            # 절대정화구역 여부
    is_relative_zone: bool            # 상대정화구역 여부
    nearby_schools: list[NearbySchool]
    restrictions: list[str]           # 제한 업종 목록
    data_source: str
    retrieved_at: datetime

class NearbySchool(BaseModel):
    school_name: str            # 학교명
    school_type: str            # "초등학교", "중학교", "고등학교"
    lat: float
    lng: float
    distance_m: int             # 중심점 대비 거리
    zone_type: str | None       # "절대정화구역", "상대정화구역", None(구역 외)
```

**제한 업종 정보** (학교환경위생정화구역 내):
- **절대정화구역 (50m)**: 모든 유흥업소, 단란주점, 호프/소주방, PC방, 노래연습장, 당구장, 숙박업소, 만화대여점
- **상대정화구역 (200m)**: 위 업종 + 지역 교육환경보호위원회 심의 대상 업종

### 5.3 리소스

```python
@mcp.resource("regulatory://industry-permit-map")
async def get_industry_permit_map() -> str:
    """업종코드별 필요 인허가 매핑 테이블을 반환합니다."""

@mcp.resource("regulatory://school-zone-restrictions")
async def get_school_zone_restrictions() -> str:
    """학교정화구역 내 제한/금지 업종 목록을 반환합니다."""

@mcp.resource("regulatory://zoning-limits")
async def get_zoning_limits() -> str:
    """용도지역별 건폐율/용적률 상한 참조 테이블을 반환합니다."""
```

### 5.4 캐싱 전략

| 도구 | Redis 키 패턴 | TTL | 비고 |
|------|--------------|-----|------|
| `search_law` | `reg:law:{keyword_hash}:{law_type}` | 7일 | 법령 개정 빈도 낮음 |
| `get_local_ordinance` | `reg:ordin:{region_hash}:{keyword_hash}` | 7일 | |
| `get_zoning_info` | `reg:zone:{lat_5d}:{lng_5d}` | 90일 | 용도지역 변동 극히 드묾 |
| `get_permit_requirements` | `reg:permit:{industry_code}` | 30일 | 법령 기반 정적 정보 |
| `check_school_zone` | `reg:school:{lat_4d}:{lng_4d}` | 30일 | 학교 이전은 드묾 |

### 5.5 에러 처리

| 상황 | 처리 방식 |
|------|----------|
| 법령 검색 결과 0건 | `articles=[]` 반환, 에러 미발생 |
| law.go.kr API 장애 | 캐시 데이터 우선 반환, 캐시 미스 시 `ExternalAPIError` |
| LURIS API 미응답 | `get_land_use_plan` (부동산 서버)로 폴백 |
| 학교 검색 실패 | `nearby_schools=[]`, `is_absolute_zone=false`, `is_relative_zone=false` 반환 |
| 업종코드 매핑 없음 | `INVALID_PARAM` 에러, 지원 업종 코드 목록 안내 |

---

## MCP Server #6: 금융/대출 (Finance)

### 6.1 서버 프로필

| 항목 | 내용 |
|------|------|
| **서버명** | `finance-server` |
| **목적** | 창업 대출, 정부 지원사업, 프랜차이즈 정보, 인건비 계산 기초 데이터 제공 |
| **래핑 API** | 기업마당 지원사업 API, K-Startup API, 프랜차이즈 정보공개서 |

### 6.2 도구 목록

#### 6.2.1 `search_startup_loans`

소상공인/창업자 대상 대출 상품을 검색한다.

```python
@mcp.tool()
async def search_startup_loans(
    industry: str,       # 업종 키워드 (예: "음식점", "소매업")
    region: str,         # 지역 (예: "서울", "경기")
) -> LoanSearchResult:
    """소상공인/창업자 대상 대출 상품을 검색합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://www.bizinfo.go.kr/uss/rss/bizInfoRssList.json`
  - 기업마당 지원사업 통합검색 API
  - 또는 `http://apis.data.go.kr/B552735/kisedKstartup/getKStartup` (K-Startup)
- **K-Startup 엔드포인트**: `http://apis.data.go.kr/B552735/kisedKstartup/getKStartup`
  - API ID: `15125364`
- **메서드**: `GET`
- **인증**: Query Parameter `serviceKey={DATA_GO_KR_API_KEY}`
- **요청 파라미터 (K-Startup)**:
  ```
  serviceKey: str
  pageNo: int
  numOfRows: int
  cond[pblancNm::LIKE]: str    # 공고명 검색어
  ```
- **요청 파라미터 (기업마당)**:
  ```
  dataType: str          # "json"
  searchTxt: str         # 검색어
  areaCd: str            # 지역코드
  indCd: str             # 업종코드
  busiType: str          # "financing" (금융지원)
  pageNo: int
  numOfRows: int
  ```

**반환 스키마**:

```python
class LoanSearchResult(BaseModel):
    industry: str
    region: str
    total_count: int
    loans: list[LoanProduct]
    data_source: str                # "기업마당_지원사업 + K-Startup"
    retrieved_at: datetime

class LoanProduct(BaseModel):
    product_id: str              # 지원사업 고유 ID
    product_name: str            # 상품/사업명
    institution: str             # 지원기관 (예: "소상공인시장진흥공단")
    loan_type: str               # "정책자금", "보증", "융자" 등
    target_audience: str         # 대상 (예: "예비창업자, 소상공인")
    max_amount: int | None       # 최대 대출한도 (원)
    interest_rate: str | None    # 금리 정보 (예: "연 2.0%~3.5%")
    repayment_period: str | None # 상환기간 (예: "5년(거치 2년 포함)")
    application_period: str      # 신청기간
    description: str             # 상세 설명
    detail_url: str              # 상세 페이지 URL
    contact: str | None          # 문의처
```

---

#### 6.2.2 `search_government_subsidies`

정부/지자체 지원사업(보조금)을 검색한다.

```python
@mcp.tool()
async def search_government_subsidies(
    industry: str,                    # 업종 키워드
    region: str,                      # 지역
    business_type: str = "창업",      # 사업유형: "창업", "기존사업자", "전체"
) -> SubsidySearchResult:
    """정부/지자체 지원사업(보조금, 컨설팅 등)을 검색합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://www.bizinfo.go.kr/uss/rss/bizInfoRssList.json`
- **메서드**: `GET`
- **요청 파라미터**:
  ```
  dataType: str          # "json"
  searchTxt: str         # 검색어 (industry + 관련 키워드)
  areaCd: str            # 지역코드
  busiType: str          # "all" (전체), "financing" (금융), "technology" (기술) 등
  pageNo: int
  numOfRows: int
  ```

**반환 스키마**:

```python
class SubsidySearchResult(BaseModel):
    industry: str
    region: str
    business_type: str
    total_count: int
    subsidies: list[Subsidy]
    data_source: str                  # "기업마당_지원사업"
    retrieved_at: datetime

class Subsidy(BaseModel):
    subsidy_id: str               # 지원사업 ID
    subsidy_name: str             # 사업명
    institution: str              # 지원기관
    support_type: str             # 지원유형: "금융", "기술", "인력", "수출", "내수", "창업", "경영"
    target_audience: str          # 지원대상
    support_amount: str | None    # 지원규모/금액
    application_period: str       # 신청기간
    description: str              # 상세내용
    detail_url: str               # 상세 페이지 URL
    status: str                   # "접수중", "접수예정", "접수마감"
```

---

#### 6.2.3 `calculate_loan_repayment`

대출 상환 스케줄을 계산한다 (내부 계산, 외부 API 없음).

```python
@mcp.tool()
async def calculate_loan_repayment(
    principal: int,             # 대출 원금 (원)
    annual_rate: float,         # 연이자율 (%, 예: 3.5)
    term_months: int,           # 상환 기간 (월)
) -> RepaymentSchedule:
    """원리금균등 방식 대출 상환 스케줄을 계산합니다."""
```

**반환 스키마**:

```python
class RepaymentSchedule(BaseModel):
    principal: int                          # 대출 원금
    annual_rate: float                      # 연이자율 (%)
    monthly_rate: float                     # 월이자율 (%)
    term_months: int                        # 상환 기간 (월)
    monthly_payment: int                    # 월 납입금 (원)
    total_payment: int                      # 총 납입금 (원)
    total_interest: int                     # 총 이자 (원)
    schedule: list[MonthlyPayment]          # 월별 상환 내역
    data_source: str                        # "internal_calculation"
    retrieved_at: datetime

class MonthlyPayment(BaseModel):
    month: int                # 회차 (1~term_months)
    payment: int              # 납입금 (원)
    principal_part: int       # 원금 상환분 (원)
    interest_part: int        # 이자분 (원)
    remaining_balance: int    # 잔여 원금 (원)
```

**계산 로직** (원리금균등상환):
```python
monthly_rate = annual_rate / 100 / 12
monthly_payment = principal * monthly_rate * (1 + monthly_rate)**term_months / ((1 + monthly_rate)**term_months - 1)
# 각 월:
# interest_part = remaining * monthly_rate
# principal_part = monthly_payment - interest_part
# remaining = remaining - principal_part
```

---

#### 6.2.4 `get_franchise_disclosure`

프랜차이즈 정보공개서 데이터를 조회한다.

```python
@mcp.tool()
async def get_franchise_disclosure(
    brand_name: str,    # 프랜차이즈 브랜드명 (예: "이디야커피", "bbq치킨")
) -> FranchiseInfo:
    """프랜차이즈 정보공개서(가맹비, 매출, 가맹점 수 등)를 조회합니다."""
```

**외부 API 호출**:
- **엔드포인트**: `https://franchise.ftc.go.kr/mnu/00013/program/userRqst/list.do`
  - 프랜차이즈 정보공개서 공개 API (공정거래위원회)
  - 또는 data.go.kr 경유 API
- **메서드**: `GET`
- **인증**: Query Parameter `apiKey={FRANCHISE_FTC_KEY}` (발급 필요)
- **요청 파라미터**:
  ```
  searchKeyword: str     # 브랜드명
  pageIndex: int
  pageUnit: int
  ```

**반환 스키마**:

```python
class FranchiseInfo(BaseModel):
    brand_name: str                        # 브랜드명
    company_name: str                      # 가맹본부명 (법인명)
    representative: str                    # 대표자
    industry_category: str                 # 업종 (예: "커피", "치킨")
    initial_franchise_fee: int | None      # 가맹비 (원)
    education_fee: int | None              # 교육비 (원)
    deposit: int | None                    # 보증금 (원)
    interior_cost_per_pyeong: int | None   # 평당 인테리어 비용 (원)
    other_initial_cost: int | None         # 기타 초기비용 (원)
    total_initial_cost_estimate: int | None # 총 초기투자비용 추정 (원)
    avg_monthly_revenue: int | None        # 가맹점 평균 월매출 (원)
    avg_annual_revenue: int | None         # 가맹점 평균 연매출 (원)
    total_franchise_count: int | None      # 전체 가맹점 수
    new_franchise_count: int | None        # 신규 가맹점 수 (연간)
    closed_franchise_count: int | None     # 폐점 수 (연간)
    contract_period_years: int | None      # 계약 기간 (년)
    renewal_condition: str | None          # 갱신 조건
    territory_protection: bool | None      # 영업지역 보호 여부
    disclosure_year: str                   # 정보공개서 기준 연도
    data_source: str                       # "공정거래위원회_프랜차이즈정보"
    retrieved_at: datetime
```

---

#### 6.2.5 `get_minimum_wage`

연도별 최저임금 정보를 반환한다.

```python
@mcp.tool()
async def get_minimum_wage(
    year: int,    # 조회 연도 (예: 2026)
) -> MinWageInfo:
    """해당 연도의 최저임금 정보를 반환합니다."""
```

**외부 API 호출**: 없음 (내부 데이터 테이블)
- 매년 최저임금위원회 발표 후 수동 업데이트

**반환 스키마**:

```python
class MinWageInfo(BaseModel):
    year: int
    hourly_wage: int               # 시급 (원)
    monthly_wage: int              # 월급 (원, 주 40시간 기준 209시간)
    daily_wage: int                # 일급 (원, 8시간 기준)
    weekly_hours: int              # 기준 주당 근로시간 (40)
    monthly_hours: int             # 기준 월 근로시간 (209)
    change_rate: float             # 전년 대비 인상률 (%)
    effective_date: str            # 시행일 "YYYY-01-01"
    data_source: str               # "최저임금위원회"
    retrieved_at: datetime
```

**내부 데이터**:
```python
MIN_WAGE_TABLE = {
    2024: {"hourly": 9860, "monthly": 2060740},
    2025: {"hourly": 10030, "monthly": 2096270},
    2026: {"hourly": 10280, "monthly": 2148520},  # 예시
}
```

---

#### 6.2.6 `get_insurance_rates`

4대보험 요율 정보를 반환한다.

```python
@mcp.tool()
async def get_insurance_rates(
    year: int,    # 조회 연도
) -> InsuranceRates:
    """해당 연도의 4대보험 요율을 반환합니다."""
```

**외부 API 호출**: 없음 (내부 데이터 테이블)
- 매년 관계부처 발표 후 수동 업데이트

**반환 스키마**:

```python
class InsuranceRates(BaseModel):
    year: int
    national_pension: InsuranceRate          # 국민연금
    health_insurance: InsuranceRate          # 건강보험
    long_term_care: InsuranceRate            # 장기요양보험
    employment_insurance: InsuranceRate      # 고용보험
    industrial_accident: InsuranceRate       # 산재보험 (업종별 상이)
    total_employer_rate: float               # 사업주 총 부담률 (%)
    total_employee_rate: float               # 근로자 총 부담률 (%)
    data_source: str                          # "국민연금공단, 건강보험공단, 근로복지공단"
    retrieved_at: datetime

class InsuranceRate(BaseModel):
    name: str                    # 보험명
    total_rate: float            # 전체 요율 (%)
    employer_rate: float         # 사업주 부담률 (%)
    employee_rate: float         # 근로자 부담률 (%)
    base_description: str        # 산정 기준 설명
    notes: str | None            # 참고사항
```

**내부 데이터 (2025년 기준 예시)**:
```python
INSURANCE_RATES_2025 = {
    "national_pension": {
        "total_rate": 9.0,
        "employer_rate": 4.5,
        "employee_rate": 4.5,
        "base": "기준소득월액 (상한 5,900,000원)",
    },
    "health_insurance": {
        "total_rate": 7.09,
        "employer_rate": 3.545,
        "employee_rate": 3.545,
        "base": "보수월액",
    },
    "long_term_care": {
        "total_rate": 0.9182,  # 건강보험료의 12.95%
        "employer_rate": 0.4591,
        "employee_rate": 0.4591,
        "base": "건강보험료 × 12.95%",
    },
    "employment_insurance": {
        "total_rate": 1.8,  # 실업급여 1.8% (150인 미만)
        "employer_rate": 0.9,
        "employee_rate": 0.9,
        "base": "보수총액 (실업급여 기준, 사업장 규모별 고용안정/직업능력개발 별도)",
    },
    "industrial_accident": {
        "total_rate": 1.47,  # 전 업종 평균
        "employer_rate": 1.47,
        "employee_rate": 0.0,
        "base": "보수총액 (업종별 상이, 음식점업 약 1.2%)",
    },
}
```

### 6.3 리소스

```python
@mcp.resource("finance://minimum-wage-history")
async def get_minimum_wage_history() -> str:
    """연도별 최저임금 변동 이력을 반환합니다 (2015~현재)."""

@mcp.resource("finance://insurance-rates-history")
async def get_insurance_rates_history() -> str:
    """연도별 4대보험 요율 변동 이력을 반환합니다."""

@mcp.resource("finance://bizinfo-area-codes")
async def get_bizinfo_area_codes() -> str:
    """기업마당 지역 코드 매핑 테이블을 반환합니다."""
```

### 6.4 캐싱 전략

| 도구 | Redis 키 패턴 | TTL | 비고 |
|------|--------------|-----|------|
| `search_startup_loans` | `fin:loan:{industry_hash}:{region_hash}` | 6시간 | 지원사업 공고 수시 변동 |
| `search_government_subsidies` | `fin:sub:{industry_hash}:{region_hash}:{biz_type}` | 6시간 | |
| `calculate_loan_repayment` | 캐시 안 함 | - | 순수 계산, 즉시 반환 |
| `get_franchise_disclosure` | `fin:fran:{brand_hash}` | 7일 | 연 1회 공시 |
| `get_minimum_wage` | `fin:minwage:{year}` | 365일 | 연 1회 결정 |
| `get_insurance_rates` | `fin:ins:{year}` | 365일 | 연 1회 결정 |

### 6.5 에러 처리

| 상황 | 처리 방식 |
|------|----------|
| 대출 상품 검색 결과 0건 | `loans=[]` 반환, 에러 미발생 |
| 기업마당 API 장애 | 캐시 데이터 반환, 캐시 미스 시 `ExternalAPIError` |
| 프랜차이즈 브랜드 미조회 | `DataNotFoundError(code="NOT_FOUND", message="해당 브랜드 정보공개서 없음")` |
| 미래 연도 최저임금 조회 | 최신 확정 연도 데이터 반환 + 경고 메시지 |
| 대출 계산 파라미터 이상 | `INVALID_PARAM`: 원금 ≤ 0, 이율 < 0, 기간 ≤ 0 검증 |
| K-Startup API 타임아웃 | 기업마당 API 단독으로 결과 반환, 부분 데이터임을 명시 |

---

## 부록: 전체 도구 요약표

| # | MCP 서버 | 도구명 | 외부 API | 캐시 TTL | Phase 1 | 담당 에이전트 |
|---|---------|--------|---------|----------|---------|-------------|
| 1 | 공공데이터 | `get_floating_population` | data.go.kr #15012005 (소상공인 상권정보) | 7일 | ✅ 활성 | 유동인구 |
| 2 | 공공데이터 | `get_estimated_revenue` | data.go.kr #15012005 → **서울 추정매출 OA-15572** | 7일 | ✅ 활성 | 매출추정 |
| 3 | 공공데이터 | `get_store_list` | data.go.kr #15012005 | 24시간 | ✅ 활성 | 경쟁분석 / 입지 |
| 4 | 공공데이터 | `get_store_count_change` | data.go.kr #15012005 | 7일 | ✅ 활성 | 경쟁분석 |
| 5 | 공공데이터 | `get_resident_population` | KOSIS (행안부 주민등록인구) | 30일 | ✅ 활성 | 유동인구 보완 |
| 6 | 공공데이터 | `get_worker_population` | KOSIS | 30일 | ✅ 활성 | 유동인구 보완 |
| 7 | 공공데이터 | `get_seoul_living_population` | 서울 열린데이터광장 생활인구 (OA-15379) | 24시간 | ✅ 활성 | 유동인구 **핵심** |
| 8 | 공공데이터 | `get_card_sales` | 서울 열린데이터광장 추정매출 (OA-15572) | 7일 | ✅ 활성 | 매출추정 **핵심** |
| 9 | 지도/GIS | `geocode` | 카카오 로컬 | 30일 | ✅ 활성 | 입지 |
| 10 | 지도/GIS | `reverse_geocode` | 카카오 로컬 | 30일 | ✅ 활성 | 입지 |
| 11 | 지도/GIS | `search_nearby` | 카카오 로컬 | 6시간 | ✅ 활성 | 입지 |
| 12 | 지도/GIS | `search_keyword` | 카카오 로컬 | 6시간 | ✅ 활성 | 입지 |
| 13 | 지도/GIS | `get_walking_route` | 카카오모빌리티 | 7일 | ✅ 활성 | 입지 |
| 14 | 지도/GIS | `get_transit_nearby` | 카카오 로컬 (지하철 + 버스) + **서울 지하철 승하차** | 24시간 | ✅ 활성 | 입지 **핵심** |
| 15 | 지도/GIS | `get_category_pois` | 카카오 로컬 | 6시간 | ✅ 활성 | 입지 |
| 16 | 부동산 | `get_commercial_transactions` | data.go.kr #15126463 | 7일 | 🚫 [Phase 2] | 부동산 에이전트 |
| 17 | 부동산 | `get_commercial_rent_index` | KOSIS/한국부동산원 | 30일 | 🚫 [Phase 2] | 부동산 에이전트 |
| 18 | 부동산 | `get_building_register` | data.go.kr #15044713 | 90일 | 🚫 [Phase 2] | 부동산 에이전트 |
| 19 | 부동산 | `get_vacancy_rate` | KOSIS/한국부동산원 | 30일 | 🚫 [Phase 2] | 부동산 에이전트 |
| 20 | 부동산 | `get_land_use_plan` | LURIS | 90일 | 🚫 [Phase 2] | 부동산 에이전트 |
| 21 | 부동산 | `estimate_premium` | 내부 계산 | 24시간 | 🚫 [Phase 2] | 부동산 에이전트 |
| 22 | 뉴스/SNS | `search_news` | 네이버 검색 | 1시간 | 🚫 [Phase 2] | 트렌드 에이전트 |
| 23 | 뉴스/SNS | `search_blogs` | 네이버 검색 | 3시간 | 🚫 [Phase 2] | 트렌드 에이전트 |
| 24 | 뉴스/SNS | `get_search_trend` | ~~네이버 데이터랩~~ **⚠️ 사용 불가** — DB 저장 이용약관 위반, 대안 소스 확보 필요 | - | ❌ 제외 | - |
| 25 | 뉴스/SNS | `get_google_trend` | Google Trends | 24시간 | 🚫 [Phase 2] | 트렌드 에이전트 |
| 26 | 뉴스/SNS | `analyze_sentiment` | 내부 LLM | 7일 | 🚫 [Phase 2] | 트렌드 에이전트 |
| 27 | 규제/인허가 | `search_law` | law.go.kr | 7일 | 🚫 [Phase 2] | 규제 에이전트 |
| 28 | 규제/인허가 | `get_local_ordinance` | law.go.kr/elis.go.kr | 7일 | 🚫 [Phase 2] | 규제 에이전트 |
| 29 | 규제/인허가 | `get_zoning_info` | LURIS | 90일 | 🚫 [Phase 2] | 규제 에이전트 |
| 30 | 규제/인허가 | `get_permit_requirements` | ~~localdata.go.kr~~ **⚠️ 2026-04-15 폐기** → data.go.kr 재설계 필요 | 30일 | 🚫 [Phase 2] | 규제 에이전트 |
| 31 | 규제/인허가 | `check_school_zone` | 카카오 로컬 | 30일 | 🚫 [Phase 2] | 규제 에이전트 |
| 32 | 금융/대출 | `search_startup_loans` | 기업마당/K-Startup | 6시간 | 🚫 [Phase 2] | 금융 에이전트 |
| 33 | 금융/대출 | `search_government_subsidies` | 기업마당 | 6시간 | 🚫 [Phase 2] | 금융 에이전트 |
| 34 | 금융/대출 | `calculate_loan_repayment` | 내부 계산 | 없음 | 🚫 [Phase 2] | 금융 에이전트 |
| 35 | 금융/대출 | `get_franchise_disclosure` | franchise.ftc.go.kr | 7일 | 🚫 [Phase 2] | 금융 에이전트 |
| 36 | 금융/대출 | `get_minimum_wage` | 내부 데이터 | 365일 | 🚫 [Phase 2] | 금융 에이전트 |
| 37 | 금융/대출 | `get_insurance_rates` | 내부 데이터 | 365일 | 🚫 [Phase 2] | 금융 에이전트 |

---

> 본 명세서는 MarketScope AI 시스템의 데이터 접근 계층 전체를 정의한다.
> 각 MCP 서버의 구현 시 이 문서의 도구 시그니처, 반환 스키마, 캐싱 전략을 준수해야 한다.
