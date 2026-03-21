# 09. 프론트엔드 명세서

## 목차
1. [페이지 구조](#1-페이지-구조)
2. [컴포넌트 아키텍처](#2-컴포넌트-아키텍처)
3. [상태 관리 (Zustand)](#3-상태-관리-zustand)
4. [SSE 통합](#4-sse-통합)
5. [반응형 디자인](#5-반응형-디자인)
6. [UX 플로우](#6-ux-플로우)

---

## 1. 페이지 구조

### 1.1 Next.js App Router 구조

```
src/
├── app/
│   ├── layout.tsx                          # 루트 레이아웃 (글로벌 프로바이더, 폰트)
│   ├── page.tsx                            # / (랜딩 + 검색)
│   ├── loading.tsx                         # 전역 로딩 UI
│   ├── error.tsx                           # 전역 에러 바운더리
│   ├── not-found.tsx                       # 404 페이지
│   │
│   ├── analysis/
│   │   ├── [id]/
│   │   │   ├── page.tsx                    # /analysis/[id] (분석 결과)
│   │   │   ├── loading.tsx                 # 분석 결과 로딩 (스켈레톤)
│   │   │   └── compare/
│   │   │       └── page.tsx                # /analysis/[id]/compare (비교 뷰)
│   │   └── layout.tsx                      # 분석 공통 레이아웃
│   │
│   ├── dashboard/
│   │   ├── page.tsx                        # /dashboard (대시보드)
│   │   └── layout.tsx                      # 대시보드 레이아웃 (사이드바)
│   │
│   ├── chat/
│   │   └── [analysisId]/
│   │       └── page.tsx                    # /chat/[analysisId] (후속 채팅)
│   │
│   └── auth/
│       ├── login/
│       │   └── page.tsx                    # /auth/login
│       ├── register/
│       │   └── page.tsx                    # /auth/register
│       └── callback/
│           └── page.tsx                    # /auth/callback (OAuth 리다이렉트)
│
├── components/
│   ├── map/                                # 지도 컴포넌트
│   ├── charts/                             # 차트 컴포넌트
│   ├── report/                             # 보고서 컴포넌트
│   ├── chat/                               # 채팅 컴포넌트
│   ├── common/                             # 공통 UI 컴포넌트
│   └── layout/                             # 레이아웃 컴포넌트
│
├── hooks/                                  # 커스텀 훅
│   ├── useSSE.ts                           # SSE 연결 훅
│   ├── useAnalysis.ts                      # 분석 데이터 훅
│   ├── useAuth.ts                          # 인증 훅
│   └── useMap.ts                           # 지도 제어 훅
│
├── stores/                                 # Zustand 스토어
│   ├── analysisStore.ts
│   ├── userStore.ts
│   ├── mapStore.ts
│   └── chatStore.ts
│
├── lib/
│   ├── api.ts                              # API 클라이언트 (axios 인스턴스)
│   ├── auth.ts                             # 인증 유틸리티
│   └── constants.ts                        # 상수 정의
│
├── types/                                  # TypeScript 타입 정의
│   ├── analysis.ts
│   ├── chat.ts
│   ├── map.ts
│   └── api.ts
│
└── styles/
    └── globals.css                         # Tailwind CSS + 커스텀 스타일
```

### 1.2 페이지별 상세

#### `/` - 랜딩 + 검색 페이지

| 항목 | 값 |
|------|-----|
| 인증 필요 | 아니오 (미인증 시 검색만 가능, 분석 실행 시 로그인 유도) |
| SSR/CSR | SSG (정적 생성) + CSR (검색 인터랙션) |
| 주요 섹션 | 히어로 배너, 검색 바, 최근 분석 사례, 서비스 소개 |

```typescript
// app/page.tsx
interface HomePageProps {
  // 서버 컴포넌트 - props 없음
}

// 클라이언트 컴포넌트로 분리되는 섹션:
// - SearchBar (검색어 자동완성, 위치 선택)
// - RecentAnalyses (최근 공개 분석 사례)
```

#### `/analysis/[id]` - 분석 결과 페이지

| 항목 | 값 |
|------|-----|
| 인증 필요 | 예 |
| SSR/CSR | SSR (초기 데이터) + CSR (인터랙티브 탐색) |
| 주요 섹션 | 종합 요약, 지도, 에이전트별 결과, 교차 검증 타임라인, 차트 |

```typescript
// app/analysis/[id]/page.tsx
interface AnalysisPageProps {
  params: { id: string };
}

// 서버 측: 분석 결과 데이터 프리페치
// 클라이언트 측: 지도 인터랙션, 차트 렌더링, 탭 전환
```

#### `/analysis/[id]/compare` - 비교 뷰

| 항목 | 값 |
|------|-----|
| 인증 필요 | 예 (Starter 이상) |
| SSR/CSR | CSR (비교 대상 선택 후 동적 로딩) |
| 주요 섹션 | 비교 대상 선택, 나란히 비교 테이블, 비교 차트 |

#### `/dashboard` - 사용자 대시보드

| 항목 | 값 |
|------|-----|
| 인증 필요 | 예 |
| SSR/CSR | SSR (분석 이력) + CSR (필터, 정렬) |
| 주요 섹션 | 사용량 요약, 분석 이력 목록, 즐겨찾기 |

#### `/chat/[analysisId]` - 후속 채팅

| 항목 | 값 |
|------|-----|
| 인증 필요 | 예 |
| SSR/CSR | SSR (채팅 이력) + CSR (실시간 채팅) |
| 주요 섹션 | 분석 요약 사이드바, 채팅 영역, 추천 질문 |

#### `/auth/login`, `/auth/register` - 인증 페이지

| 항목 | 값 |
|------|-----|
| 인증 필요 | 아니오 (이미 로그인 시 리다이렉트) |
| SSR/CSR | CSR |
| 주요 섹션 | 로그인/회원가입 폼, OAuth 버튼 |

---

## 2. 컴포넌트 아키텍처

### 2.1 지도 컴포넌트 (Map Components)

지도 라이브러리: **Kakao Maps SDK** (국내 상권 데이터와 호환성 우선) + Mapbox GL JS (히트맵/커스텀 레이어 필요 시)

---

#### `DistrictMap` - 상권 경계 폴리곤 오버레이

상권 경계를 GeoJSON 폴리곤으로 지도 위에 표시하는 핵심 지도 컴포넌트.

```typescript
interface DistrictMapProps {
  /** 지도 중심 좌표 */
  center: {
    lat: number;
    lng: number;
  };
  /** 초기 줌 레벨 (기본: 15) */
  zoom?: number;
  /** 상권 경계 GeoJSON (Polygon 또는 MultiPolygon) */
  boundaryGeoJson?: GeoJSON.Feature | null;
  /** 경계 폴리곤 스타일 */
  boundaryStyle?: {
    fillColor?: string;       // 기본: "rgba(59, 130, 246, 0.15)"
    strokeColor?: string;     // 기본: "#3B82F6"
    strokeWidth?: number;     // 기본: 2
  };
  /** 분석 반경 (미터) - 반경 원 표시 */
  radiusM?: number;
  /** 지도 클릭 이벤트 */
  onMapClick?: (lat: number, lng: number) => void;
  /** 지도 영역 변경 이벤트 */
  onBoundsChange?: (bounds: MapBounds) => void;
  /** 지도 스타일 */
  mapStyle?: "standard" | "satellite" | "dark";
  /** 하위 레이어 컴포넌트 */
  children?: React.ReactNode;
}

interface MapBounds {
  ne: { lat: number; lng: number };   // 북동 좌표
  sw: { lat: number; lng: number };   // 남서 좌표
}
```

---

#### `CompetitorMarkers` - 경쟁업체 핀

```typescript
interface CompetitorMarkersProps {
  /** 경쟁업체 마커 데이터 */
  competitors: CompetitorMarker[];
  /** 직접 경쟁업체만 표시 여부 */
  showDirectOnly?: boolean;
  /** 마커 클릭 이벤트 */
  onMarkerClick?: (competitor: CompetitorMarker) => void;
  /** 선택된 마커 ID */
  selectedId?: string | null;
  /** 클러스터링 사용 여부 (기본: true, 50개 이상 시 자동) */
  enableClustering?: boolean;
}

interface CompetitorMarker {
  id: string;
  name: string;
  category: string;
  lat: number;
  lng: number;
  rating: number | null;
  reviewCount: number | null;
  isDirectCompetitor: boolean;
}
```

---

#### `HeatmapLayer` - 유동인구/매출 히트맵

```typescript
interface HeatmapLayerProps {
  /** 히트맵 데이터 포인트 */
  data: HeatmapPoint[];
  /** 히트맵 유형 */
  type: "population" | "revenue";
  /** 투명도 (0~1, 기본: 0.6) */
  opacity?: number;
  /** 반경 (픽셀, 기본: 30) */
  radius?: number;
  /** 표시 여부 */
  visible?: boolean;
  /** 색상 그라디언트 */
  gradient?: Record<number, string>;
  /** 강도 범위 */
  intensityRange?: {
    min: number;
    max: number;
  };
}

interface HeatmapPoint {
  lat: number;
  lng: number;
  weight: number;             // 0.0 ~ 1.0 (정규화된 가중치)
}
```

---

#### `POIMarkers` - 주요 시설 마커

```typescript
interface POIMarkersProps {
  /** POI 데이터 목록 */
  pois: POIMarker[];
  /** 표시할 POI 카테고리 필터 */
  visibleCategories?: POICategory[];
  /** 마커 클릭 이벤트 */
  onMarkerClick?: (poi: POIMarker) => void;
  /** 거리 라벨 표시 여부 (기본: false) */
  showDistanceLabel?: boolean;
}

type POICategory =
  | "subway"        // 지하철역
  | "bus_stop"      // 버스 정류장
  | "school"        // 학교
  | "university"    // 대학교
  | "hospital"      // 병원
  | "parking"       // 주차장
  | "park"          // 공원
  | "shopping";     // 대형 쇼핑시설

interface POIMarker {
  id: string;
  name: string;
  type: POICategory;
  lat: number;
  lng: number;
  distanceM: number;          // 분석 중심점으로부터 거리
}
```

---

#### `WalkingCircle` - 도보 5분/10분 반경

```typescript
interface WalkingCircleProps {
  /** 도보 반경 데이터 (실제 도로망 기반 폴리곤) */
  circles: WalkingCircleData[];
  /** 표시 여부 */
  visible?: boolean;
  /** 선택된 반경 (분) - 해당 반경 강조 */
  highlightMinutes?: number | null;
}

interface WalkingCircleData {
  minutes: number;            // 5 또는 10
  polygonGeoJson: GeoJSON.Feature;   // 도보 도달 가능 영역 폴리곤
  style?: {
    fillColor?: string;       // 5분: "rgba(34,197,94,0.1)", 10분: "rgba(251,146,60,0.1)"
    strokeColor?: string;     // 5분: "#22C55E", 10분: "#FB923C"
    strokeWidth?: number;
    strokeDasharray?: string; // 점선 패턴
  };
}
```

---

### 2.2 차트 컴포넌트 (Chart Components)

차트 라이브러리: **Plotly.js** (`react-plotly.js` 래퍼 사용)

모든 차트는 공통 래퍼 `ChartContainer`를 통해 반응형 리사이즈, 로딩 상태, 에러 상태를 처리한다.

```typescript
/** 모든 차트 컴포넌트가 상속하는 공통 Props */
interface BaseChartProps {
  /** 차트 너비 (기본: "100%") */
  width?: number | string;
  /** 차트 높이 (기본: 400) */
  height?: number;
  /** 로딩 상태 */
  loading?: boolean;
  /** 다크 모드 */
  darkMode?: boolean;
  /** 애니메이션 사용 여부 (기본: true) */
  animate?: boolean;
  /** 차트 다운로드 버튼 표시 (기본: false) */
  showDownload?: boolean;
  /** CSS 클래스명 */
  className?: string;
}
```

---

#### `PopulationTimeChart` - 시간대별 유동인구 바 차트

```typescript
interface PopulationTimeChartProps extends BaseChartProps {
  /** 시간대별 유동인구 데이터 */
  hourlyData: HourlyPopulation[];
  /** 피크 시간대 하이라이트 */
  peakHours?: string[];
  /** 비교 데이터 (선택) - 다른 상권 또는 이전 기간 */
  comparisonData?: HourlyPopulation[];
  /** 비교 데이터 라벨 */
  comparisonLabel?: string;
  /** 요일 필터 (선택된 요일만 표시) */
  dayFilter?: ("MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT" | "SUN")[];
}

interface HourlyPopulation {
  hour: string;               // "00", "01", ..., "23"
  count: number;              // 유동인구 수
  label?: string;             // 표시 라벨 (예: "오전 9시")
}
```

---

#### `RevenueTrendChart` - 매출 추이 라인 차트

```typescript
interface RevenueTrendChartProps extends BaseChartProps {
  /** 매출 추이 데이터 */
  trendData: RevenueTrend[];
  /** 동종 업종 평균 비교선 표시 */
  showIndustryAverage?: boolean;
  /** 동종 업종 평균 데이터 */
  industryAverageData?: RevenueTrend[];
  /** 예측 구간 표시 (미래 데이터가 포함된 경우) */
  showForecast?: boolean;
  /** 예측 시작 인덱스 */
  forecastStartIndex?: number;
  /** Y축 단위 */
  yAxisUnit?: "만원" | "억원";
}

interface RevenueTrend {
  period: string;             // "2025-10", "2025-11", ...
  revenue: number;            // 매출액 (만원)
  upperBound?: number;        // 신뢰구간 상한 (예측 시)
  lowerBound?: number;        // 신뢰구간 하한 (예측 시)
}
```

---

#### `CompetitionRadar` - 경쟁 분석 레이더 차트

```typescript
interface CompetitionRadarProps extends BaseChartProps {
  /** 평가 항목별 점수 */
  scores: RadarScore[];
  /** 동종 업종 평균 점수 (비교 표시) */
  averageScores?: RadarScore[];
  /** 최대 점수 (기본: 100) */
  maxScore?: number;
  /** 항목별 가중치 표시 */
  showWeights?: boolean;
}

interface RadarScore {
  category: string;           // "유동인구", "경쟁도", "접근성", "매출", "성장성"
  score: number;              // 0 ~ maxScore
  weight?: number;            // 가중치 (0~1)
  description?: string;       // 툴팁 설명
}
```

---

#### `RiskMatrix` - 리스크 매트릭스 산점도

```typescript
interface RiskMatrixProps extends BaseChartProps {
  /** 리스크 항목 데이터 */
  risks: RiskPoint[];
  /** 리스크 임계값 라인 표시 */
  showThresholds?: boolean;
  /** 마커 클릭 이벤트 */
  onRiskClick?: (risk: RiskPoint) => void;
  /** 영역 라벨 표시 (저위험, 중위험, 고위험, 치명적) */
  showZoneLabels?: boolean;
}

interface RiskPoint {
  id: string;
  name: string;               // "임대료 상승", "경쟁 과열", ...
  probability: number;        // 발생 확률 (0~1) → X축
  impact: number;             // 영향도 (0~1) → Y축
  category: "market" | "financial" | "operational" | "regulatory";
  mitigation?: string;        // 대응 방안
}
```

---

#### `FinancialScenario` - 3시나리오 비교 차트

```typescript
interface FinancialScenarioProps extends BaseChartProps {
  /** 시나리오별 월별 수익 예측 */
  scenarios: {
    optimistic: MonthlyFinancial[];
    base: MonthlyFinancial[];
    pessimistic: MonthlyFinancial[];
  };
  /** 손익분기점 표시 */
  showBreakEven?: boolean;
  /** 손익분기점 (개월) */
  breakEvenMonths?: {
    optimistic: number;
    base: number;
    pessimistic: number;
  };
  /** 초기 투자금 라인 표시 */
  showInitialInvestment?: boolean;
  /** 초기 투자금 (만원) */
  initialInvestment?: number;
  /** 표시 항목 선택 */
  displayMetric?: "revenue" | "profit" | "cumulative_profit" | "cash_flow";
}

interface MonthlyFinancial {
  month: number;              // 1, 2, ..., 36
  revenue: number;            // 월 매출 (만원)
  cost: number;               // 월 비용 (만원)
  profit: number;             // 월 순이익 (만원)
  cumulativeProfit: number;   // 누적 순이익 (만원)
  cashFlow: number;           // 현금 흐름 (만원)
}
```

---

#### `SeasonalPattern` - 월별 매출 패턴

```typescript
interface SeasonalPatternProps extends BaseChartProps {
  /** 월별 매출 계수 (1.0 = 평균) */
  monthlyFactors: MonthlyFactor[];
  /** 동종 업종 평균 패턴 */
  industryPattern?: MonthlyFactor[];
  /** 현재 월 강조 */
  highlightCurrentMonth?: boolean;
  /** 차트 유형 */
  chartType?: "bar" | "line" | "area";
}

interface MonthlyFactor {
  month: string;              // "01", "02", ..., "12"
  factor: number;             // 매출 계수 (예: 1.2 = 평균 대비 20% 높음)
  label?: string;             // "1월", "2월", ...
  note?: string;              // 특이 사항 (예: "성수기", "비수기")
}
```

---

### 2.3 보고서 컴포넌트 (Report Components)

---

#### `ExecutiveSummary` - 핵심 요약 카드

```typescript
interface ExecutiveSummaryProps {
  /** 종합 점수 (0~100) */
  overallScore: number;
  /** 종합 등급 */
  overallGrade: string;
  /** 핵심 메시지 (3~5문장) */
  executiveSummary: string;
  /** 핵심 인사이트 목록 */
  keyInsights: string[];
  /** 추천 의견 */
  recommendation: string;
  /** 추천 방향 */
  recommendationType: "positive" | "caution" | "negative";
  /** 로딩 상태 */
  loading?: boolean;
  /** 분석 깊이 */
  depth: "quick" | "standard" | "deep";
  /** 분석 소요 시간 (초) */
  durationSec?: number;
}
```

**UI 구성:**
- 좌측: 원형 점수 게이지 (0~100, 색상 그라디언트: 빨강→노랑→초록)
- 우측 상단: 등급 뱃지 + 추천 방향 아이콘
- 본문: 핵심 요약 텍스트
- 하단: 인사이트 칩(chip) 목록, 추천 카드

---

#### `AgentResultCard` - 에이전트 분석 결과 카드

```typescript
interface AgentResultCardProps {
  /** 에이전트 이름 */
  agentName: string;
  /** 에이전트 표시 이름 (한국어) */
  displayName: string;
  /** 에이전트 아이콘 */
  icon: React.ReactNode;
  /** 분석 상태 */
  status: "pending" | "running" | "completed" | "failed";
  /** 신뢰도 점수 */
  confidenceScore?: number;
  /** 요약 텍스트 */
  summary?: string;
  /** 핵심 지표 (key-value 쌍) */
  keyMetrics?: Record<string, string | number>;
  /** 상세 결과 (마크다운 또는 구조화된 데이터) */
  detailedResult?: any;
  /** 데이터 출처 */
  sources?: string[];
  /** 실행 시간 (초) */
  durationSec?: number;
  /** 카드 펼침/접힘 상태 */
  defaultExpanded?: boolean;
  /** 펼침/접힘 토글 콜백 */
  onToggleExpand?: (expanded: boolean) => void;
}
```

**UI 구성:**
- 헤더: 아이콘 + 에이전트 이름 + 상태 뱃지 + 신뢰도 바
- 접힌 상태: 요약 + 핵심 지표 3개
- 펼친 상태: 전체 분석 결과 + 차트 + 출처

---

#### `DebateTimeline` - 교차 검증 과정 타임라인

```typescript
interface DebateTimelineProps {
  /** 검증 라운드 데이터 */
  rounds: DebateRound[];
  /** 검증 요약 */
  summary?: string;
  /** 점수 조정 내역 */
  adjustments?: ScoreAdjustment[];
  /** 애니메이션 활성화 (SSE 실시간 진행 시) */
  animated?: boolean;
  /** 현재 진행 중인 라운드 인덱스 (-1 = 완료) */
  activeRoundIndex?: number;
}

interface DebateRound {
  roundNumber: number;
  challenger: string;         // 에이전트 이름
  challengerDisplayName: string;
  target: string;
  targetDisplayName: string;
  challengePoint: string;     // 이의 제기 내용
  response: string;           // 반박 내용
  resolution: string;         // 합의 결과
}

interface ScoreAdjustment {
  metric: string;             // 조정된 지표
  before: number;
  after: number;
  reason: string;             // 조정 사유
}
```

**UI 구성:**
- 수직 타임라인 (왼쪽 에이전트 ↔ 오른쪽 에이전트)
- 각 라운드: 질문 카드 → 응답 카드 → 합의 결과 뱃지
- 실시간 진행 시: 현재 라운드 펄스 애니메이션 + 이전 라운드 페이드인

---

#### `ComparisonTable` - 두 상권 비교 테이블

```typescript
interface ComparisonTableProps {
  /** 분석 A 정보 */
  analysisA: AnalysisSummary;
  /** 분석 B 정보 */
  analysisB: AnalysisSummary;
  /** 비교 항목 목록 */
  rows: ComparisonRow[];
  /** 종합 비교 의견 */
  winnerSummary: string;
  /** 카테고리별 필터 */
  categoryFilter?: string[];
  /** 우승 항목 하이라이트 */
  highlightWinner?: boolean;
}

interface AnalysisSummary {
  requestId: string;
  query: string;
  locationSummary: string;    // "강남구 역삼동"
  overallScore: number;
  overallGrade: string;
}

interface ComparisonRow {
  category: string;           // "유동인구", "경쟁도", ...
  metric: string;             // "일 평균 유동인구"
  valueA: string | number;
  valueB: string | number;
  winner: "a" | "b" | "tie";
  note?: string;
  unit?: string;              // "명", "만원", "%" 등
}
```

---

#### `RecommendationCard` - 추천 사항 카드

```typescript
interface RecommendationCardProps {
  /** 추천 유형 */
  type: "positive" | "caution" | "negative";
  /** 추천 제목 */
  title: string;
  /** 추천 상세 내용 */
  description: string;
  /** 실행 항목 (체크리스트) */
  actionItems?: ActionItem[];
  /** 관련 에이전트 (클릭 시 해당 섹션 이동) */
  relatedAgents?: string[];
}

interface ActionItem {
  text: string;
  priority: "high" | "medium" | "low";
  category: string;           // "입지", "마케팅", "운영", "재무"
}
```

---

### 2.4 채팅 컴포넌트 (Chat Components)

---

#### `ChatPanel` - AI 채팅 패널

```typescript
interface ChatPanelProps {
  /** 관련 분석 ID */
  analysisId: string;
  /** 채팅 메시지 목록 */
  messages: ChatMessage[];
  /** 메시지 전송 핸들러 */
  onSendMessage: (message: string, contextFocus?: string[]) => Promise<void>;
  /** 로딩 상태 (AI 응답 대기 중) */
  isLoading?: boolean;
  /** 추천 질문 목록 */
  suggestedQuestions?: string[];
  /** 분석 결과 참조 가능 에이전트 목록 */
  availableContexts?: { name: string; displayName: string }[];
  /** 패널 위치 */
  position?: "side" | "bottom" | "fullscreen";
  /** 패널 닫기 핸들러 */
  onClose?: () => void;
}

interface ChatMessage {
  messageId: string;
  role: "user" | "assistant";
  content: string;            // 마크다운 형식
  references?: ChatReference[];
  suggestedQuestions?: string[];
  createdAt: string;          // ISO 8601
}

interface ChatReference {
  agentName: string;
  section: string;
  snippet: string;
}
```

---

#### `MessageBubble` - 메시지 버블

```typescript
interface MessageBubbleProps {
  /** 메시지 데이터 */
  message: ChatMessage;
  /** 참조 링크 클릭 핸들러 (분석 결과 해당 섹션으로 이동) */
  onReferenceClick?: (agentName: string, section: string) => void;
  /** 메시지 복사 핸들러 */
  onCopy?: (content: string) => void;
  /** 타이핑 애니메이션 (AI 응답 시) */
  isTyping?: boolean;
}
```

**UI 구성:**
- 사용자 메시지: 우측 정렬, 파란 배경
- AI 메시지: 좌측 정렬, 회색 배경, 마크다운 렌더링
- 참조 구간: 인라인 칩으로 표시, 클릭 시 해당 분석 섹션으로 스크롤
- AI 응답 대기 중: 타이핑 인디케이터 (점 3개 애니메이션)

---

#### `AnalysisProgress` - 분석 진행 상황 표시

```typescript
interface AnalysisProgressProps {
  /** 분석 요청 ID */
  requestId: string;
  /** 전체 에이전트 수 */
  totalAgents: number;
  /** 에이전트별 진행 상황 */
  agentProgress: AgentProgressItem[];
  /** 현재 단계 */
  currentPhase: "queued" | "agents" | "debate" | "synthesis" | "complete" | "error";
  /** 교차 검증 진행 상황 */
  debateProgress?: {
    currentRound: number;
    totalRounds: number;
    currentPair?: { challenger: string; target: string };
  };
  /** 예상 남은 시간 (초) */
  estimatedRemainingSeconds?: number;
  /** 전체 진행률 (0~100) */
  overallProgress: number;
  /** 에러 정보 */
  error?: {
    message: string;
    code: string;
    recoverable: boolean;
  };
}

interface AgentProgressItem {
  agentName: string;
  displayName: string;
  status: "pending" | "running" | "completed" | "failed";
  progressPct?: number;       // 0~100
  currentStep?: string;       // "공공데이터 API 조회 중..."
  durationSec?: number;
  summary?: string;           // 완료 시 요약
}
```

**UI 구성:**
- 수직 스텝 인디케이터 (6개 에이전트 + 교차 검증 + 종합 보고서)
- 각 스텝: 아이콘 + 이름 + 상태 (대기/진행/완료/오류) + 진행바
- 진행 중 스텝: 현재 작업 텍스트 + 스피너 애니메이션
- 완료된 스텝: 체크 아이콘 + 요약 텍스트 (페이드인)
- 하단: 전체 진행바 + 예상 남은 시간

---

## 3. 상태 관리 (Zustand)

### 3.1 스토어 구조 개요

```
stores/
├── analysisStore.ts          # 분석 데이터 + 진행 상황
├── userStore.ts              # 사용자 인증 + 프로필
├── mapStore.ts               # 지도 상태 + 레이어 제어
└── chatStore.ts              # 채팅 메시지 + 세션
```

### 3.2 `analysisStore` - 분석 스토어

```typescript
import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";

interface AnalysisState {
  // === 상태 ===

  /** 현재 활성 분석 결과 */
  currentAnalysis: AnalysisResult | null;

  /** 분석 진행 상황 (SSE 실시간 업데이트) */
  progress: {
    requestId: string | null;
    status: "idle" | "queued" | "processing" | "completed" | "failed";
    overallProgress: number;          // 0~100
    agentProgress: AgentProgressItem[];
    debateProgress: DebateProgress | null;
    currentPhase: AnalysisPhase;
    estimatedRemainingSeconds: number | null;
    error: ProgressError | null;
  };

  /** 분석 이력 목록 */
  history: {
    items: AnalysisHistoryItem[];
    total: number;
    page: number;
    pageSize: number;
    isLoading: boolean;
    filters: HistoryFilters;
  };

  /** 비교 분석 */
  comparison: {
    analysisA: AnalysisSummary | null;
    analysisB: AnalysisSummary | null;
    result: ComparisonResult | null;
    isLoading: boolean;
  };

  // === 액션 ===

  /** 새 분석 요청 */
  createAnalysis: (request: AnalysisCreateRequest) => Promise<string>;

  /** 분석 결과 로드 */
  loadAnalysis: (requestId: string) => Promise<void>;

  /** 에이전트 진행 상황 업데이트 (SSE 이벤트 핸들러) */
  updateAgentProgress: (event: SSEEvent) => void;

  /** 교차 검증 진행 상황 업데이트 */
  updateDebateProgress: (event: SSEEvent) => void;

  /** 분석 완료 처리 */
  handleAnalysisComplete: (event: SSEEvent) => void;

  /** 에러 처리 */
  handleAnalysisError: (event: SSEEvent) => void;

  /** 진행 상태 초기화 */
  resetProgress: () => void;

  /** 이력 로드 */
  loadHistory: (page?: number, filters?: HistoryFilters) => Promise<void>;

  /** 비교 분석 실행 */
  runComparison: (analysisIdA: string, analysisIdB: string) => Promise<void>;

  /** 비교 대상 설정 */
  setComparisonTarget: (slot: "A" | "B", analysis: AnalysisSummary) => void;
}

type AnalysisPhase = "idle" | "queued" | "agents" | "debate" | "synthesis" | "complete" | "error";

interface DebateProgress {
  currentRound: number;
  totalRounds: number;
  rounds: DebateRound[];
}

interface HistoryFilters {
  status?: string;
  industry?: string;
  dateFrom?: string;
  dateTo?: string;
  sortBy: "created_at" | "overall_score";
  sortOrder: "asc" | "desc";
}

interface ProgressError {
  message: string;
  code: string;
  recoverable: boolean;
}

const useAnalysisStore = create<AnalysisState>()(
  devtools(
    immer(
      persist(
        (set, get) => ({
          // 초기 상태
          currentAnalysis: null,
          progress: {
            requestId: null,
            status: "idle",
            overallProgress: 0,
            agentProgress: [],
            debateProgress: null,
            currentPhase: "idle",
            estimatedRemainingSeconds: null,
            error: null,
          },
          history: {
            items: [],
            total: 0,
            page: 1,
            pageSize: 10,
            isLoading: false,
            filters: { sortBy: "created_at", sortOrder: "desc" },
          },
          comparison: {
            analysisA: null,
            analysisB: null,
            result: null,
            isLoading: false,
          },

          // 액션 구현
          createAnalysis: async (request) => {
            const response = await api.post("/analysis", request);
            set((state) => {
              state.progress.requestId = response.data.request_id;
              state.progress.status = "queued";
              state.progress.currentPhase = "queued";
              state.progress.overallProgress = 0;
            });
            return response.data.request_id;
          },

          updateAgentProgress: (event) => {
            set((state) => {
              const { agentProgress } = state.progress;
              const idx = agentProgress.findIndex(
                (a) => a.agentName === event.data.agent_name
              );
              if (event.data.type === "agent_start") {
                if (idx === -1) {
                  agentProgress.push({
                    agentName: event.data.agent_name,
                    displayName: event.data.agent_display_name,
                    status: "running",
                    progressPct: 0,
                  });
                } else {
                  agentProgress[idx].status = "running";
                }
                state.progress.currentPhase = "agents";
                state.progress.status = "processing";
              } else if (event.data.type === "agent_complete") {
                if (idx !== -1) {
                  agentProgress[idx].status = "completed";
                  agentProgress[idx].progressPct = 100;
                  agentProgress[idx].summary = event.data.summary;
                  agentProgress[idx].durationSec = event.data.duration_sec;
                }
              }
              // 전체 진행률 계산
              const completed = agentProgress.filter(
                (a) => a.status === "completed"
              ).length;
              state.progress.overallProgress = Math.round(
                (completed / 6) * 80   // 에이전트 80%, 검증+종합 20%
              );
            });
          },

          // ... 나머지 액션 구현
        }),
        {
          name: "analysis-store",
          partialize: (state) => ({
            // persist 대상: 이력 필터만 저장
            history: { filters: state.history.filters },
          }),
        }
      )
    ),
    { name: "AnalysisStore" }
  )
);
```

### 3.3 `userStore` - 사용자 스토어

```typescript
interface UserState {
  // === 상태 ===

  /** 현재 사용자 정보 */
  user: UserProfile | null;

  /** 인증 상태 */
  isAuthenticated: boolean;

  /** Access Token */
  accessToken: string | null;

  /** 토큰 만료 시각 */
  tokenExpiresAt: number | null;

  /** 로딩 상태 */
  isLoading: boolean;

  // === 액션 ===

  /** 로그인 */
  login: (email: string, password: string) => Promise<void>;

  /** 회원가입 */
  register: (data: RegisterRequest) => Promise<void>;

  /** OAuth 로그인 */
  oauthLogin: (provider: "google" | "kakao") => void;

  /** OAuth 콜백 처리 */
  handleOAuthCallback: (token: string) => Promise<void>;

  /** 토큰 갱신 */
  refreshToken: () => Promise<void>;

  /** 로그아웃 */
  logout: () => Promise<void>;

  /** 프로필 로드 */
  loadProfile: () => Promise<void>;

  /** 환경설정 업데이트 */
  updatePreferences: (prefs: Partial<UserPreferences>) => Promise<void>;

  /** 인증 상태 확인 (앱 초기화 시) */
  checkAuth: () => Promise<void>;
}

interface UserProfile {
  userId: string;
  email: string;
  name: string;
  tier: "free" | "starter" | "pro";
  oauthProvider: string | null;
  analysisCountThisMonth: number;
  analysisLimit: number | null;       // null = 무제한
  preferences: UserPreferences;
  createdAt: string;
}

interface UserPreferences {
  defaultLocation: LocationInput | null;
  defaultIndustry: string | null;
  defaultDepth: "quick" | "standard" | "deep";
  language: "ko" | "en";
  notificationEmail: boolean;
  mapStyle: "standard" | "satellite" | "dark";
}
```

### 3.4 `mapStore` - 지도 스토어

```typescript
interface MapState {
  // === 상태 ===

  /** 지도 중심 좌표 */
  center: { lat: number; lng: number };

  /** 줌 레벨 */
  zoom: number;

  /** 현재 보이는 영역 */
  bounds: MapBounds | null;

  /** 활성 레이어 */
  activeLayers: {
    boundary: boolean;        // 상권 경계
    competitors: boolean;     // 경쟁업체
    heatmap: boolean;         // 히트맵
    poi: boolean;             // POI
    walkingCircle: boolean;   // 도보 반경
  };

  /** 히트맵 모드 */
  heatmapType: "population" | "revenue";

  /** 선택된 마커 */
  selectedMarker: {
    type: "competitor" | "poi";
    id: string;
    data: CompetitorMarker | POIMarker;
  } | null;

  /** POI 카테고리 필터 */
  visiblePOICategories: POICategory[];

  /** 도보 반경 강조 */
  highlightWalkingMinutes: number | null;   // 5 또는 10

  /** 지도 마커 데이터 */
  markerData: MapMarkerSet | null;

  /** 지도 로딩 상태 */
  isLoading: boolean;

  // === 액션 ===

  /** 지도 중심 이동 */
  setCenter: (lat: number, lng: number) => void;

  /** 줌 레벨 변경 */
  setZoom: (zoom: number) => void;

  /** 레이어 토글 */
  toggleLayer: (layer: keyof MapState["activeLayers"]) => void;

  /** 히트맵 타입 변경 */
  setHeatmapType: (type: "population" | "revenue") => void;

  /** 마커 선택 */
  selectMarker: (type: string, id: string) => void;

  /** 마커 선택 해제 */
  clearSelection: () => void;

  /** POI 카테고리 필터 설정 */
  setPOICategories: (categories: POICategory[]) => void;

  /** 마커 데이터 로드 */
  loadMarkers: (analysisId: string) => Promise<void>;

  /** 초기 상태로 리셋 */
  resetMap: () => void;
}
```

### 3.5 `chatStore` - 채팅 스토어

```typescript
interface ChatState {
  // === 상태 ===

  /** 분석별 채팅 세션 */
  sessions: Record<string, ChatSession>;    // key: analysisId

  /** 현재 활성 세션 ID */
  activeSessionId: string | null;

  // === 액션 ===

  /** 메시지 전송 */
  sendMessage: (
    analysisId: string,
    message: string,
    contextFocus?: string[]
  ) => Promise<void>;

  /** 채팅 이력 로드 */
  loadHistory: (analysisId: string) => Promise<void>;

  /** 활성 세션 설정 */
  setActiveSession: (analysisId: string) => void;

  /** 세션 삭제 */
  clearSession: (analysisId: string) => void;
}

interface ChatSession {
  analysisId: string;
  messages: ChatMessage[];
  isLoading: boolean;                 // AI 응답 대기 중
  suggestedQuestions: string[];       // 현재 추천 질문
  hasMore: boolean;                   // 이전 메시지 더 있는지
  page: number;
}
```

---

## 4. SSE 통합

### 4.1 `useSSE` 커스텀 훅

```typescript
import { useEffect, useRef, useCallback } from "react";
import { useAnalysisStore } from "@/stores/analysisStore";

interface UseSSEOptions {
  /** 분석 요청 ID */
  requestId: string;
  /** 연결 활성화 여부 */
  enabled?: boolean;
  /** 재연결 시도 최대 횟수 */
  maxRetries?: number;
  /** 연결 성공 콜백 */
  onConnected?: () => void;
  /** 연결 종료 콜백 */
  onDisconnected?: () => void;
  /** 에러 콜백 */
  onError?: (error: Event) => void;
}

interface UseSSEReturn {
  /** 연결 상태 */
  connectionStatus: "connecting" | "connected" | "disconnected" | "error";
  /** 재시도 횟수 */
  retryCount: number;
  /** 수동 재연결 */
  reconnect: () => void;
  /** 수동 연결 해제 */
  disconnect: () => void;
}

function useSSE({
  requestId,
  enabled = true,
  maxRetries = 10,
  onConnected,
  onDisconnected,
  onError,
}: UseSSEOptions): UseSSEReturn {
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const [connectionStatus, setConnectionStatus] = useState<UseSSEReturn["connectionStatus"]>("disconnected");

  const {
    updateAgentProgress,
    updateDebateProgress,
    handleAnalysisComplete,
    handleAnalysisError,
  } = useAnalysisStore();

  const connect = useCallback(() => {
    if (!requestId || !enabled) return;

    const token = useUserStore.getState().accessToken;
    const url = `${API_BASE_URL}/api/v1/analysis/${requestId}/stream?token=${token}`;

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;
    setConnectionStatus("connecting");

    eventSource.onopen = () => {
      setConnectionStatus("connected");
      retryCountRef.current = 0;
      onConnected?.();
    };

    // 이벤트 핸들러 등록
    const eventHandlers: Record<string, (e: MessageEvent) => void> = {
      analysis_start: (e) => {
        const data = JSON.parse(e.data);
        updateAgentProgress({ type: "analysis_start", data });
      },
      agent_start: (e) => {
        const data = JSON.parse(e.data);
        updateAgentProgress({ type: "agent_start", data });
      },
      agent_progress: (e) => {
        const data = JSON.parse(e.data);
        updateAgentProgress({ type: "agent_progress", data });
      },
      agent_complete: (e) => {
        const data = JSON.parse(e.data);
        updateAgentProgress({ type: "agent_complete", data });
      },
      debate_start: (e) => {
        const data = JSON.parse(e.data);
        updateDebateProgress({ type: "debate_start", data });
      },
      debate_round: (e) => {
        const data = JSON.parse(e.data);
        updateDebateProgress({ type: "debate_round", data });
      },
      synthesis_start: (e) => {
        const data = JSON.parse(e.data);
        updateAgentProgress({ type: "synthesis_start", data });
      },
      complete: (e) => {
        const data = JSON.parse(e.data);
        handleAnalysisComplete({ type: "complete", data });
        eventSource.close();
        setConnectionStatus("disconnected");
      },
      error: (e) => {
        const data = JSON.parse(e.data);
        handleAnalysisError({ type: "error", data });
        if (!data.recoverable) {
          eventSource.close();
          setConnectionStatus("error");
        }
      },
      heartbeat: () => {
        // 연결 유지 확인, 별도 처리 불필요
      },
    };

    Object.entries(eventHandlers).forEach(([event, handler]) => {
      eventSource.addEventListener(event, handler);
    });

    eventSource.onerror = (event) => {
      setConnectionStatus("error");
      onError?.(event);

      // 자동 재연결 (EventSource 기본 동작에 추가 로직)
      if (retryCountRef.current < maxRetries) {
        retryCountRef.current += 1;
        // EventSource는 자동 재연결을 시도하지만,
        // 최대 재시도 횟수 초과 시 수동 종료
      } else {
        eventSource.close();
        setConnectionStatus("disconnected");
        onDisconnected?.();
      }
    };

    return () => {
      eventSource.close();
    };
  }, [requestId, enabled]);

  useEffect(() => {
    const cleanup = connect();
    return () => {
      cleanup?.();
      eventSourceRef.current?.close();
    };
  }, [connect]);

  const reconnect = useCallback(() => {
    eventSourceRef.current?.close();
    retryCountRef.current = 0;
    connect();
  }, [connect]);

  const disconnect = useCallback(() => {
    eventSourceRef.current?.close();
    setConnectionStatus("disconnected");
  }, []);

  return {
    connectionStatus,
    retryCount: retryCountRef.current,
    reconnect,
    disconnect,
  };
}
```

### 4.2 점진적 UI 업데이트 패턴

분석 진행 중 에이전트가 완료될 때마다 UI가 점진적으로 채워지는 방식:

```typescript
// app/analysis/[id]/page.tsx
"use client";

function AnalysisPage({ params }: { params: { id: string } }) {
  const {
    currentAnalysis,
    progress,
    loadAnalysis,
  } = useAnalysisStore();

  const isInProgress = ["queued", "processing"].includes(progress.status);

  // SSE 연결 (분석 진행 중일 때만)
  const { connectionStatus } = useSSE({
    requestId: params.id,
    enabled: isInProgress,
  });

  // 완료된 분석이면 결과 직접 로드
  useEffect(() => {
    if (!isInProgress) {
      loadAnalysis(params.id);
    }
  }, [params.id, isInProgress]);

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* 진행 중: 프로그레스 표시 */}
      {isInProgress && (
        <AnalysisProgress
          requestId={params.id}
          totalAgents={6}
          agentProgress={progress.agentProgress}
          currentPhase={progress.currentPhase}
          debateProgress={progress.debateProgress}
          overallProgress={progress.overallProgress}
          estimatedRemainingSeconds={progress.estimatedRemainingSeconds}
          error={progress.error}
        />
      )}

      {/* 완료된 에이전트 결과는 즉시 표시 (점진적 렌더링) */}
      <div className="flex-1 space-y-4">
        {progress.agentProgress
          .filter((a) => a.status === "completed")
          .map((agent) => (
            <AgentResultCard
              key={agent.agentName}
              agentName={agent.agentName}
              displayName={agent.displayName}
              status={agent.status}
              summary={agent.summary}
              // 에이전트 완료 시 fade-in 애니메이션
              className="animate-in fade-in slide-in-from-bottom-4 duration-500"
            />
          ))}
      </div>

      {/* 완료 후: 전체 보고서 */}
      {progress.status === "completed" && currentAnalysis && (
        <>
          <ExecutiveSummary
            overallScore={currentAnalysis.overall_score!}
            overallGrade={currentAnalysis.overall_grade!}
            executiveSummary={currentAnalysis.executive_summary!}
            keyInsights={currentAnalysis.key_insights!}
            recommendation={currentAnalysis.recommendation!}
          />
          {/* 차트, 지도, 교차 검증 타임라인 등 */}
        </>
      )}
    </div>
  );
}
```

### 4.3 에러 처리 및 재연결

```typescript
// 연결 상태에 따른 UI 표시
function ConnectionStatusBanner({ status, retryCount, onReconnect }: {
  status: UseSSEReturn["connectionStatus"];
  retryCount: number;
  onReconnect: () => void;
}) {
  if (status === "connected") return null;

  const messages = {
    connecting: "서버에 연결 중입니다...",
    disconnected: "연결이 끊어졌습니다.",
    error: `연결 오류가 발생했습니다 (재시도 ${retryCount}/10)`,
  };

  return (
    <div className={cn(
      "fixed top-0 inset-x-0 z-50 p-2 text-center text-sm",
      status === "error" ? "bg-red-100 text-red-800" : "bg-yellow-100 text-yellow-800"
    )}>
      <span>{messages[status]}</span>
      {status !== "connecting" && (
        <button
          onClick={onReconnect}
          className="ml-2 underline font-medium"
        >
          다시 연결
        </button>
      )}
    </div>
  );
}
```

---

## 5. 반응형 디자인

### 5.1 브레이크포인트 정의

Tailwind CSS 기본 브레이크포인트 기반:

| 이름 | 최소 너비 | 대상 기기 |
|------|----------|----------|
| `sm` | 640px | 대형 스마트폰 (가로) |
| `md` | 768px | 태블릿 (세로) |
| `lg` | 1024px | 태블릿 (가로) / 소형 노트북 |
| `xl` | 1280px | 데스크톱 |
| `2xl` | 1536px | 대형 모니터 |

### 5.2 레이아웃 전략

#### 데스크톱 (`lg` 이상) - 좌우 분할

```
┌─────────────────────────────────────────────────┐
│ 헤더 (네비게이션 + 검색 + 사용자 메뉴)              │
├───────────────────────┬─────────────────────────┤
│                       │                         │
│     지도 영역          │    보고서 영역             │
│     (50% 너비)        │    (50% 너비)            │
│                       │                         │
│  ┌─────────────────┐  │  ┌───────────────────┐  │
│  │ DistrictMap     │  │  │ ExecutiveSummary  │  │
│  │ + Layers        │  │  │                   │  │
│  │                 │  │  ├───────────────────┤  │
│  │                 │  │  │ AgentResultCards  │  │
│  │                 │  │  │ (스크롤)           │  │
│  │                 │  │  │                   │  │
│  └─────────────────┘  │  │ Charts            │  │
│  레이어 컨트롤 패널     │  │                   │  │
│                       │  │ DebateTimeline    │  │
│                       │  └───────────────────┘  │
├───────────────────────┴─────────────────────────┤
│ 채팅 패널 (우측 사이드 슬라이드)                     │
└─────────────────────────────────────────────────┘
```

```typescript
// 데스크톱 레이아웃
<div className="hidden lg:flex h-[calc(100vh-64px)]">
  {/* 좌측: 지도 */}
  <div className="w-1/2 relative">
    <DistrictMap {...mapProps}>
      <CompetitorMarkers {...competitorProps} />
      <HeatmapLayer {...heatmapProps} />
      <POIMarkers {...poiProps} />
      <WalkingCircle {...walkingProps} />
    </DistrictMap>
    <MapLayerControls className="absolute bottom-4 left-4" />
  </div>

  {/* 우측: 보고서 (스크롤 가능) */}
  <div className="w-1/2 overflow-y-auto border-l">
    <ExecutiveSummary {...summaryProps} />
    <AgentResults {...agentProps} />
    <ChartSection {...chartProps} />
    <DebateTimeline {...debateProps} />
  </div>

  {/* 채팅 사이드 패널 (토글) */}
  {isChatOpen && (
    <div className="w-96 border-l animate-in slide-in-from-right">
      <ChatPanel {...chatProps} position="side" />
    </div>
  )}
</div>
```

#### 모바일 (`lg` 미만) - 수직 스택 + 바텀시트

```
┌─────────────────────┐
│ 헤더 (햄버거 메뉴)    │
├─────────────────────┤
│                     │
│   지도 영역           │
│   (전체 너비, 40vh)  │
│                     │
├─────────────────────┤
│ ▲ 바텀시트 핸들       │
├─────────────────────┤
│                     │
│  보고서 영역          │
│  (바텀시트, 스와이프) │
│                     │
│  탭: 요약|상세|차트   │
│                     │
│  콘텐츠 (스크롤)      │
│                     │
├─────────────────────┤
│ 채팅 버튼 (FAB)      │
└─────────────────────┘
```

```typescript
// 모바일 레이아웃
<div className="lg:hidden flex flex-col h-[calc(100vh-56px)]">
  {/* 상단: 지도 */}
  <div className="h-[40vh] relative">
    <DistrictMap {...mapProps} zoom={14}>
      {/* 모바일에서는 핵심 레이어만 */}
      <CompetitorMarkers {...competitorProps} />
      <WalkingCircle {...walkingProps} />
    </DistrictMap>
  </div>

  {/* 바텀시트: 보고서 */}
  <BottomSheet
    snapPoints={["20%", "60%", "95%"]}
    defaultSnap="60%"
  >
    {/* 탭 네비게이션 */}
    <TabBar
      tabs={[
        { id: "summary", label: "요약" },
        { id: "detail", label: "상세" },
        { id: "chart", label: "차트" },
      ]}
      activeTab={activeTab}
      onTabChange={setActiveTab}
    />

    {/* 탭별 콘텐츠 */}
    <div className="overflow-y-auto">
      {activeTab === "summary" && <ExecutiveSummary {...summaryProps} />}
      {activeTab === "detail" && <AgentResults {...agentProps} />}
      {activeTab === "chart" && <ChartSection {...chartProps} />}
    </div>
  </BottomSheet>

  {/* 채팅 FAB 버튼 */}
  <button
    onClick={() => setIsChatOpen(true)}
    className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-blue-600 text-white shadow-lg z-40"
  >
    <ChatIcon />
  </button>

  {/* 채팅 전체 화면 모달 (모바일) */}
  {isChatOpen && (
    <ChatPanel {...chatProps} position="fullscreen" onClose={() => setIsChatOpen(false)} />
  )}
</div>
```

### 5.3 `BottomSheet` 컴포넌트

```typescript
interface BottomSheetProps {
  /** 스냅 포인트 (높이 비율 또는 픽셀) */
  snapPoints: string[];
  /** 기본 스냅 포인트 */
  defaultSnap?: string;
  /** 드래그로 닫기 허용 */
  dismissible?: boolean;
  /** 닫기 콜백 */
  onDismiss?: () => void;
  /** 스냅 변경 콜백 */
  onSnapChange?: (snap: string) => void;
  /** 자식 컴포넌트 */
  children: React.ReactNode;
}
```

### 5.4 반응형 차트 처리

```typescript
// 차트 반응형 래퍼
function ResponsiveChart({ children }: { children: React.ReactNode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className="w-full">
      {React.cloneElement(children as React.ReactElement, {
        width: dimensions.width,
        height: dimensions.width < 640 ? 250 : 400,  // 모바일에서 낮은 높이
      })}
    </div>
  );
}
```

---

## 6. UX 플로우

### 6.1 전체 사용자 여정

```
[1. 검색] → [2. 로딩 (실시간 진행)] → [3. 결과 탐색] → [4. 채팅] → [5. 저장/공유]
```

### 6.2 단계별 상세

#### 단계 1: 검색 (`/`)

**진입 조건:** 없음 (누구나 접근 가능)

**사용자 흐름:**
```
1.1  랜딩 페이지 진입
1.2  검색 바에 질의 입력 (예: "강남역 근처 카페 창업")
     → 자동완성 드롭다운: 상권명, 행정동, 주소 제안
1.3  위치 선택 (3가지 방식 중 택 1):
     a) 자동완성에서 상권/주소 선택
     b) 지도에서 직접 클릭
     c) 현재 위치 사용 (Geolocation API)
1.4  업종 선택 (선택 사항)
     → 대분류 → 중분류 → 소분류 계층형 선택기
1.5  분석 깊이 선택: 빠른분석(3분) | 표준분석(7분) | 심층분석(15분)
1.6  "분석 시작" 버튼 클릭
     → 미인증: 로그인 모달 표시 (OAuth 버튼 포함)
     → 인증 완료 후: POST /api/v1/analysis 호출
     → 요율 제한 초과: 업그레이드 안내 모달
```

**핵심 인터랙션:**
- 검색어 입력 시 300ms 디바운스 후 자동완성 API 호출
- 지도와 검색 바 양방향 동기화 (검색 결과 선택 시 지도 이동, 지도 클릭 시 검색 바 업데이트)
- 위치 선택 시 해당 상권 경계 프리뷰 표시

---

#### 단계 2: 로딩 - 실시간 진행 (`/analysis/[id]`)

**진입 조건:** 분석 요청 후 자동 이동

**사용자 흐름:**
```
2.1  분석 진행 페이지 자동 전환
     → SSE 연결 수립
2.2  각 에이전트 진행 상황 실시간 표시
     2.2.1  상권 분석 에이전트 시작 → 진행바 애니메이션
     2.2.2  상권 분석 완료 → 결과 카드 fade-in → 요약 표시
     2.2.3  유동인구 분석 시작 → ...
     (반복)
2.3  완료된 에이전트 결과는 즉시 탐색 가능
     → 카드 클릭으로 상세 확인
     → 완료된 차트 먼저 렌더링
2.4  교차 검증 진행 표시
     → 에이전트 간 토론 과정 타임라인 실시간 표시
2.5  종합 보고서 생성 중 표시
2.6  분석 완료 → 전체 보고서 전환
```

**핵심 인터랙션:**
- 전체 진행바 (상단) + 개별 에이전트 스텝 (수직 타임라인)
- 완료된 에이전트 카드를 클릭하면 해당 상세 결과로 스크롤
- 예상 남은 시간 카운트다운
- 브라우저 탭이 비활성이어도 SSE 유지 (완료 시 브라우저 알림)

**에러 처리:**
- 개별 에이전트 실패: 해당 에이전트 결과 비워두고 나머지 계속 진행
- SSE 연결 끊김: 자동 재연결 + 놓친 이벤트 복구
- 전체 실패: 에러 메시지 + 재시도 버튼

---

#### 단계 3: 결과 탐색 (`/analysis/[id]`)

**진입 조건:** 분석 완료 후 (또는 이력에서 완료된 분석 선택)

**사용자 흐름:**
```
3.1  종합 요약 확인
     → 종합 점수 (게이지), 등급, 핵심 요약, 인사이트 칩
3.2  에이전트별 결과 탐색 (탭 또는 스크롤)
     → 상권 분석: 경계 지도, 점포 현황, 공실률
     → 유동인구: 시간대별 차트, 연령/성별 분포
     → 경쟁 분석: 경쟁업체 목록, 포화도, 레이더 차트
     → 매출 분석: 추이 차트, 계절 패턴, 벤치마크
     → 리스크: 리스크 매트릭스, 대응 전략
     → 재무 시뮬레이션: 3시나리오 차트, 손익분기점
3.3  지도 인터랙션
     → 레이어 전환 (경쟁업체, 히트맵, POI, 도보 반경)
     → 마커 클릭으로 상세 정보 팝업
     → 히트맵 모드 전환 (유동인구/매출)
3.4  교차 검증 과정 확인
     → 타임라인에서 각 라운드의 이의→반박→합의 확인
     → 점수 조정 내역 확인
3.5  비교 분석 진입 (선택)
     → "다른 상권과 비교" 버튼 → /analysis/[id]/compare
```

**핵심 인터랙션:**
- 지도와 보고서 연동: 보고서에서 경쟁업체 클릭 시 지도에서 해당 마커 하이라이트
- 차트 인터랙션: 호버 시 툴팁, 클릭으로 드릴다운
- 스크롤 스파이: 현재 보고 있는 섹션이 사이드 네비게이션에 하이라이트

---

#### 단계 4: 채팅 (`/chat/[analysisId]`)

**진입 조건:** 완료된 분석 결과 페이지에서 채팅 버튼 클릭

**사용자 흐름:**
```
4.1  채팅 패널 열기 (사이드 패널 또는 전체 화면)
4.2  추천 질문 표시 (최대 3개)
     → 클릭으로 바로 질문 전송
4.3  자유 질문 입력
     예: "이 지역 카페 월 예상 매출이 3천만원이라고 했는데, 어떤 근거인가요?"
4.4  AI 응답 수신
     → 마크다운 렌더링 (코드 블록, 테이블, 리스트 등)
     → 분석 결과 참조 구간이 인라인 칩으로 표시
     → 참조 칩 클릭 시 분석 결과 해당 섹션으로 이동
4.5  후속 추천 질문 표시
4.6  대화 지속 또는 패널 닫기
```

**핵심 인터랙션:**
- 컨텍스트 포커스: 특정 에이전트 결과를 참조 범위로 지정 가능
- 타이핑 인디케이터: AI 응답 생성 중 점 3개 애니메이션
- 자동 스크롤: 새 메시지 시 하단으로 자동 스크롤

---

#### 단계 5: 저장/공유

**사용자 흐름:**
```
5.1  분석 결과 저장 (자동: 모든 완료된 분석은 이력에 저장)
5.2  대시보드에서 이력 확인 (/dashboard)
     → 날짜, 업종, 상태별 필터링
     → 점수 또는 날짜 기준 정렬
5.3  공유 기능 (향후 확장)
     → 공유 링크 생성 (읽기 전용)
     → PDF 다운로드
5.4  비교 분석
     → 대시보드에서 두 분석 선택 → 비교 보기
```

### 6.3 상태 전환 다이어그램

```
                    ┌─────────────────┐
                    │   랜딩 페이지     │
                    │   (미인증 가능)   │
                    └────────┬────────┘
                             │ 분석 시작
                             ▼
                    ┌─────────────────┐     ┌──────────┐
                    │   로그인 필요?    │────→│ 로그인    │
                    └────────┬────────┘  예  └────┬─────┘
                          아니오                    │
                             │◄───────────────────┘
                             ▼
                    ┌─────────────────┐
                    │  요율 제한 확인   │
                    └────┬───────┬────┘
                     OK  │       │ 초과
                         ▼       ▼
              ┌──────────────┐  ┌──────────┐
              │  분석 큐잉    │  │ 업그레이드 │
              │  (202 응답)  │  │ 안내 모달  │
              └──────┬───────┘  └──────────┘
                     │
                     ▼
              ┌──────────────┐
              │  SSE 스트림   │
              │  진행 표시    │◄──── 에이전트 완료 시
              │              │      결과 점진적 표시
              └──────┬───────┘
                     │ 완료
                     ▼
              ┌──────────────┐
              │  결과 탐색    │
              │  (지도+보고서) │
              └──┬───┬───┬───┘
                 │   │   │
        ┌────────┘   │   └────────┐
        ▼            ▼            ▼
  ┌──────────┐ ┌──────────┐ ┌──────────┐
  │  채팅    │ │  비교     │ │ 대시보드  │
  │          │ │  분석     │ │ (이력)   │
  └──────────┘ └──────────┘ └──────────┘
```

### 6.4 애니메이션 및 트랜지션 가이드

| 요소 | 애니메이션 | 지속 시간 | 이징 |
|------|-----------|---------|------|
| 에이전트 결과 카드 등장 | fade-in + slide-up | 500ms | ease-out |
| 진행 바 업데이트 | width 트랜지션 | 300ms | ease-in-out |
| 교차 검증 라운드 등장 | fade-in + scale | 400ms | ease-out |
| 지도 레이어 전환 | opacity 트랜지션 | 300ms | linear |
| 바텀시트 스냅 | spring 물리 | 350ms | spring(1, 0.8, 0) |
| 채팅 메시지 등장 | slide-up | 200ms | ease-out |
| 점수 게이지 | count-up + stroke-dashoffset | 1200ms | ease-out |
| 탭 전환 | fade + slide | 200ms | ease-in-out |
| 모달/오버레이 | fade-in + scale(0.95→1) | 200ms | ease-out |
| 스켈레톤 로딩 | shimmer (좌→우) | 1500ms | linear (반복) |

### 6.5 접근성 (A11y) 고려사항

| 항목 | 구현 |
|------|------|
| 키보드 네비게이션 | 모든 인터랙티브 요소 Tab 이동 가능, Enter/Space 활성화 |
| 스크린 리더 | 차트에 `aria-label` 제공, 진행 상태 `aria-live="polite"` |
| 색상 대비 | WCAG AA 이상 (4.5:1 텍스트, 3:1 UI 컴포넌트) |
| 지도 대체 텍스트 | 지도 옆에 텍스트 기반 위치 정보 병행 표시 |
| 모션 감소 | `prefers-reduced-motion` 미디어 쿼리 대응 |
| 폰트 크기 | rem 단위 사용, 브라우저 설정 존중 |
