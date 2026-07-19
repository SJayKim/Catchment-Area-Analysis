# MarketScope AI 상용화 Plan — 1인 창업자 관점

> 작성일: 2026-04-08
> 대상: 코드만 있는 0명 단계의 1인 창업자
> 핵심 질문: "내일부터 무엇을, 어떤 순서로 할 것인가"

---

## Context — 왜 이 plan이 필요한가

MarketScope AI는 기술적으로는 거의 다 만들어진 상태(Phase 1A 100%, Phase 1B ~95%)지만, **상용화 관점에서는 0%**입니다.

| 영역 | 상태 |
|---|---|
| 코드/제품 | Mock E2E + Real Data 거의 완료, 12만+ 행 적재, E2E 28 spec |
| 수익화 (Phase 2) | OAuth/결제/Tier 게이팅 **0%** — 오늘 결제 받을 수 없음 |
| 인프라 | docker-compose만 존재, 배포 환경/CI-CD/모니터링 없음 |
| 백엔드 테스트 | 0개 |
| 고객 | 0명 |
| 마케팅 채널 | 0개 |
| 사업자등록/약관/도메인 | 없음 |
| Real 모드 블로커 | `districts.boundary` NULL (지도 폴리곤 표시 불가), `district_summary` Real DB 분기 미작동 |

> ⚠ 2026-07-16 정정 (문서 정합성 감사): 위 표는 2026-04-08 스냅샷. 현재는 — 백엔드 테스트 `server/tests` **30모듈·수집 247케이스**(최근 실측 2026-07-08 241 passed/6 deselected) · E2E **spec 44파일·test 선언 188개** · CI 5잡(`.github/workflows/ci.yml`) + push 자동배포 파이프라인(`scripts/deploy/auto_deploy.sh`) 운영 · Real 모드 블로커(boundary NULL, `district_summary` 분기) 해소 · `marketscope.robitlabs.co.kr` 프로덕션 라이브. 수익화(Phase 2)·고객·마케팅 축은 여전히 0 으로 유효.

**경쟁 환경** (가장 중요한 진실):
오픈업/소상공인365/우리마을가게/나이스비즈맵 — 경쟁사 4개 모두 무료. 이들은 정부·대기업이 운영하는 "데이터 대시보드"입니다. **데이터로는 절대 이길 수 없으며**, 우리의 단 하나의 무기는 **"데이터를 해석해서 결정을 내려주는 AI 컨설턴트"** 포지셔닝입니다.

이 plan은 (a) 1인 개발자가 흔히 빠지는 함정("기능을 더 만들면 팔린다")을 피하고, (b) 저비용으로 PMF 검증부터 시작하며, (c) 검증된 신호가 보일 때만 다음 단계로 자원을 투입하는 **검증 우선 / 단계적 확장** 로드맵입니다.

---

## 1. 핵심 전략 결정 — 모든 것을 결정하는 7가지

| # | 결정 | 결정 내용 | 근거 |
|---|---|---|---|
| 1 | **포지셔닝** | "당신의 창업 결정을 대신 검증해주는 서울 상권 AI 컨설턴트" | "데이터 대시보드"가 아닌 "결정 지원 AI"로 카테고리 자체를 다르게 잡음 |
| 2 | **한 줄 가치 제안** | "지도에서 찍기만 하세요. 망할지 안 망할지 AI가 알려드립니다." | 고객 언어 ("LangGraph/SSE/PostGIS" 같은 개발자 언어 금지) |
| 3 | **PMF 검증 우선** | Phase 2/3 신규 기능은 결제 의향 확인 후에만 구현 | 베타 결제 의향 0이면 어떤 기능도 무의미 |
| 4 | **가격** | Free 일 5회 / **Premium 9,900원/월** + Founding Member 평생 50% 할인 (첫 100명 한정) | spec 그대로, 단 첫 100명 락인 lever 추가 |
| 5 | **결제 전 단계** | M1~M2는 결제 X 베타 무료 → M3에 Phase 2(OAuth+Toss) 완성 후 결제 OPEN | Phase 2가 0%이므로 어차피 강제됨, 약점을 자연 흐름으로 활용 |
| 6 | **인프라 시작** | Vercel + **Fly.io (nrt)** + **Neon (PostGIS)** + Upstash Redis + Cloudflare | 월 ~25,000원, SSE/LangGraph 호환, vendor lock-in 최소 |
| 7 | **하지 말 것** | F06 히트맵 / F09 시뮬레이션 / F10 PDF 신규 구현 / OAuth 등 모든 유료화 코드 (M2까지), 유료 광고 (M5까지), 모바일 앱 (영원), 채용 (월 매출 500만 전까지) | 1인 창업의 가장 흔한 실패 패턴 회피 |

---

## 2. Stage 0 — Pre-Launch (M1, 4주)

### 목표
"정말 돈 낼 사람이 있다"는 증거 + 법적 준비 완료.

### Go/No-Go 조건
- 인터뷰 15명+, "유료여도 쓰겠다" 3명+
- 랜딩 페이지 이메일 30개+
- 사업자등록 + 약관 + 도메인 완료
- **No-Go이면 피보팅** (B2B 부동산 / 프랜차이즈 본사 / 프로젝트 동결)

### 해야 할 일

**2.1 고객 발견 인터뷰 15명 (최우선, 1~2주)**
- 대상: 최근 1년 창업 사장 5~7명 + 예비 창업자 5~7명 + 상가 중개사 3~5명
- 모집: 동네 카페 직접 방문, 네이버 카페("아프니까 사장이다", "장사의 신"), 당근 동네생활, 지인 snowball
- **금지 질문**: "이 서비스 쓰실래요?"
- **필수 질문** (Mom Test):
  - "자리 정할 때 가장 어려웠던 게 뭐예요?"
  - "오픈업/소상공인365 써보셨어요? 왜 안 썼어요?"
  - "그 문제 해결에 지금 돈 쓰고 있어요? 얼마나?"
- 산출물: 인터뷰 15건의 공통 페인 패턴 노트

**2.2 랜딩 페이지 + 이메일 수집 (병렬, 3~5일)**
- 도메인: `marketscope.kr` (1.5만원/년)
- 도구: 기존 Next.js 그대로 + Vercel Free + Stibee 무료(250명) 또는 ConvertKit 무료
- 구성: Hero 카피 A/B/C 후보, 1분 데모(Loom 무료 셀카 녹화), 데모 GIF 3개, 베타 신청 폼(이메일 + 업종 + 지역 + "월 9,900원 의향" 3지선다), FAQ 5개
- 트래픽: 본인 SNS, 디스콰이엇 "만들었어요", 긱뉴스, 페이스북 "스타트업 모임"

**2.3 Phase 1B 데모용 최소 코드 수정 (2~3일, 더 만들지 말 것)**
- `server/server/agent/tools/district_summary.py` — Real DB 분기 작동 수정
- `server/server/data/etl/seoul_opendata.py` 또는 fixture — 5개 핵심 상권(강남역/홍대/건대/명동/서울역) polygon GeoJSON 수동 입력 (API 승인 우회)
- `frontend/src/components/chat/cards/{Summary,Compare,Recommend,Risk}Card.tsx` — 다크 테마 통일
- **금지**: F04, F06, F09, F10, OAuth, 결제, Tier 게이팅 — 한 줄도 안 됨

**2.4 사업자등록 + 법적 준비 (1주, 병렬)**
- 홈택스 1인 간이과세자 사업자등록 (30분, 0원)
- 통신판매업 신고 (구청 또는 정부24, 4만원)
- 개인정보 처리방침 (KISA 무료 양식)
- 이용약관 (스타트업 표준 + ChatGPT 초안, 변호사 검토 0~22만원)
- 환불 정책 (전자상거래법: 7일 청약철회, 디지털 콘텐츠 사용 시 제외 명시)
- **Toss Payments 가맹점 신청 즉시 시작** (심사 1~2주, M3에 맞추려면 지금)
- 도메인 + Cloudflare Email Routing (info@marketscope.kr → Gmail, 무료)

**2.5 트래킹 인프라 (1일)**
- GA4 (무료) + Microsoft Clarity (무료, 세션 녹화) — Clarity가 GA보다 PMF 검증에 가치 큼

### 비용
도메인 1.5만 + 통판 신고 4만 + 인터뷰 커피 5~10만 = **약 10만원**

### 시간 분배
코딩 30% / 인터뷰 50% / 마케팅 10% / 법무 10%

---

## 3. Stage 1 — Closed Beta (M2, 4~6주)

### 목표
베타 5~10명이 "실제로 의사결정에 사용", 결제 카드 등록 1~2명, 어떤 카드/Tool이 진짜 가치인지 데이터로 식별.

### Go/No-Go 조건
- 베타 10명 중 5명+ 주 2회 이상 자발적 사용
- 결제 카드 등록(가짜 결제 검증) 1~2명
- "이게 없으면 결정 못 했을 것" 발언 3건+
- 가치 핵심 카드 1~2개 명확화 (예: Risk가 압도적)

### 해야 할 일

**3.1 베타 사용자 5~10명 직접 모집 (1~2주)**
- 1순위: M1 인터뷰 20명 중 "써볼게요" 한 사람 → 카톡 직접 초대
- 2순위: 부동산 중개사무소 5곳 직접 방문 (강남/홍대/건대 — Mock 5상권과 일치)
- 조건: 무료 + 인터뷰 응답 의무, 본인 가게/관심 자리 1건 분석, 주 1회 30분 회고

**3.2 베타 환경 — Stage 1 인프라 (3~5일)**

| 컴포넌트 | 선택 | 이유 |
|---|---|---|
| Frontend | **Vercel Hobby** (Free) | Next.js standalone과 1급 호환. **단 SSE는 Vercel rewrite 거치지 않음** (Hobby 10s, Pro 60s 컷이 LLM 응답보다 짧음) — 클라이언트에서 `NEXT_PUBLIC_API_URL`로 backend 직접 호출 |
| Backend | **Fly.io Machines** (region nrt, shared-cpu-1x@512MB, `min_machines_running=1`) | always-on VM, SSE/LangGraph 시간 제한 없음, Dockerfile 그대로 사용. **Railway 대신 1차**: Railway는 idle scale-down으로 LangGraph 초기화 cold start 발생. **Render 대신**: 메모리 512MB 고정이 빠듯 |
| Database | **Neon Free** (PostgreSQL + PostGIS, ap-northeast-1) | PostGIS 공식 지원 (`CREATE EXTENSION postgis`), 0.5GB free, branch 기능, AWS Tokyo. **Supabase 대안**: Supabase Auth 쓸 거면 Supabase 우선 |
| Cache | **Upstash Redis Free** | 서버리스, 10K req/day, region nrt 가능 |
| DNS+WAF | **Cloudflare** ($10/년) | 도메인 + WAF + DDoS + SSL + Bot Fight |
| LLM | Gemini Flash 우선 (90%) + Claude Sonnet fallback | 현재 코드에 둘 다 통합됨, Gemini Flash가 ~10x 저렴 |
| 에러 추적 | **Sentry Free** (5K errors/월) | FastAPI + Next.js 1급 SDK |
| Uptime | UptimeRobot Free + BetterStack Free | `/health` 5분 체크 |
| CI/CD | **GitHub Actions** (Free 2,000 min/월) | backend.yml + frontend.yml + migrations.yml |
| 백업 | Neon 자동 PITR 7일 + 주1회 R2 dump | Free tier 충분 |

**Stage 1 월 비용**:
| 항목 | 원/월 |
|---|---|
| Vercel Hobby | 0 |
| Fly.io 1x shared-cpu-1x@512MB | ~3,500 |
| Fly egress (5GB) | ~1,500 |
| Neon Free / Upstash Free | 0 |
| Cloudflare | ~1,000 |
| Sentry/UptimeRobot/BetterStack Free | 0 |
| LLM (Gemini Flash, 베타 5~10명) | 10,000~20,000 |
| **합계** | **약 16,000~26,000원/월** |

**3.3 "비밀 로그인" — OAuth 만들지 말 것 (1일)**
- 베타 사용자 5~10명에게 고유 URL: `marketscope.kr/?key=BETA_XXXX`
- 백엔드 환경변수 `BETA_KEYS` 화이트리스트 검증 (신규 미들웨어 또는 `server/server/api/deps.py`에 의존성 함수)
- OAuth/JWT/users 테이블 모두 불필요 → 절약한 1주를 인터뷰에 투자

**3.4 PMF 지표 측정 (1주차부터)**
- Microsoft Clarity 세션 녹화 + GA + 백엔드 로그 (chat.py에 JSON Lines 사용량 로그 추가)
- 측정:
  - Activation: 가입 → 첫 분석 완료 비율
  - 사용자당 챗봇 호출/주
  - 가장 오래 머문 카드 (= 가장 가치 있는 기능)
  - 이탈 지점 (Clarity 녹화로 직접 관찰)
- 정성: 주 1회 30분 인터뷰

**3.5 결제 의향 가짜 검증 (4~5주차)**
- 결제 시스템 만들지 말고: 가짜 결제 페이지 → "정식 출시 시 9,900원, 사전 등록 시 첫 3개월 50% 할인" → Toss 빌링키 발급(실제 결제 X)
- **카드 등록한 사람 수가 진짜 PMF 신호** (말 X, 행동 O)

**3.6 차별화 검증 — "AI 응답 품질" 확인**
- 베타 사용자에게 "오픈업 결과 vs MarketScope 결과" 비교 요청
- "왜 이게 더 좋은가요?" 응답 → 마케팅 카피로 활용
- 만약 "차이를 모르겠다" 다수 → AI 응답을 더 단정적/실용적으로 튜닝 ("여기 카페 추천 안 함, 이유 3가지" 같은 강한 어조)

### 시간 분배
코딩 40% / 인터뷰 40% / 마케팅 15% / 운영 5%

---

## 4. Stage 2 — Public Launch (M3~M4, 2~3개월)

### 목표
유료 결제자 누적 10명 → 100명, MRR 10만 → 100만, 채널 1~2개 검증.

### Go/No-Go 조건
- 출시 1개월 결제자 10명+
- 첫 달 churn 30% 이하
- 채널 1개라도 CAC < LTV
- Free → 유료 전환율 1%+

### 해야 할 일

**4.1 Phase 2 인증/결제/Tier (3~4주, 가장 큰 작업 덩어리)**
- OAuth2 Google + 카카오 (NextAuth.js for Google, 카카오는 별도 OAuth 핸들러, 2~3일)
- DB 마이그레이션 4번째 리비전: `users`, `subscriptions`, `usage_logs` (B01 spec 그대로)
- Tier 미들웨어 + Free 일 5회 제한 (Redis 카운터, 1~2일)
- Toss Payments 빌링키 정기결제 + 웹훅 + 알림톡 (5~7일)
- 14일 무료 체험 (카드 등록 X로 진입 장벽 ↓, 1일)
- Soft Paywall UI — **베타에서 검증된 가장 가치 있는 기능을 paywall 뒤로** (1~2일)

**4.2 Stage 1 → Stage 2 코드 변경 (P0)**
- `server/server/api/routes/chat.py:25-31` — `_sessions` dict + `_chat_semaphore=20`을 Redis store로 이관 (horizontal scale 준비)
- `server/server/main.py` — `/ready` endpoint 분리 (DB+Redis 핑), CORS origins 환경변수화, Sentry SDK 주입, slowapi rate limit 미들웨어 (분당 30, IP+사용자 둘 다)
- `server/server/config.py:50` — `cors_origins` 환경변수
- `server/server/services/llm_router.py` (신규) — Gemini → Claude 자동 폴백 + per-user 일일 토큰 cap
- `server/server/agent/graph.py` — Langfuse callback 주입 + Anthropic prompt caching 활성화 (system prompt 30~90% 비용 절감)

**4.3 Stage 2 인프라 변화**

| 컴포넌트 | Stage 1 | Stage 2 |
|---|---|---|
| Backend | Fly 1x 512MB | **Fly 2x shared-cpu-2x@2GB** + autoscale `min=2, max=6` |
| DB | Neon Free | **Neon Launch ($19/월)** always-on, PITR 7d, 10GB |
| Cache | Upstash Free | **Upstash Pay-as-you-go** ($10~30/월) |
| Auth | 없음 | NextAuth + JWT HttpOnly cookie + Google/Kakao OAuth |
| Payment | 없음 | Toss Payments 빌링키 + 웹훅 |
| Rate limiting | 없음 | slowapi + Redis backend |
| Langfuse | 미사용 | Langfuse Cloud Free (50K obs/월) |
| Logs | BetterStack Free | BetterStack Pro $25 (30GB, 30일 retention) |
| CDN | Vercel edge only | + **Cloudflare R2** + Workers cache for `/api/map-data/polygons` |
| Frontend | Vercel Hobby | Vercel Pro $20 |
| Email | 없음 | Resend Free (3K/월, 영수증) + 카카오 알림톡 (Bizm 등 8~12원/건) |

**Stage 2 월 비용**: 약 47만~62만원 (LLM 비용이 가장 큰 변수)
**손익분기**: 유료 50명 도달 시 (50 × 9,900 = 495,000원)

**4.4 Soft Launch — 한국형 채널 1~2개 집중 (1~2주)**
- 1주차: 디스콰이엇 "만들었어요" 정식 런칭 포스트
- 2주차: GeekNews 기술 글 ("Claude + LangGraph로 상권분석 챗봇 만들기")
- 3주차: 네이버 카페 1곳 (운영자 사전 신뢰 쌓기 후 정식 게시)
- **절대 5개 동시 시도 금지**, 각 채널마다 클릭 → 가입 → 결제 깔때기 측정
- 보도자료 발송: 벤처스퀘어, 플래텀, 테크42, 디일렉

**4.5 콘텐츠 마케팅 SEO 시드 (병렬)**
- 블로그 5~10편 (네이버 블로그 1차 + marketscope.kr/blog 2차):
  - "2026 서울 상권분석 완전 가이드" (Pillar)
  - "오픈업 vs 소상공인365 vs MarketScope 비교"
  - "강남역 상권 분석 2026" (자체 데이터로 자동 생성 + 사람 검수, 글 끝 CTA)
  - "홍대 상권 분석 2026"
  - "성수동 상권 분석 2026"
- SEO 키워드 (네이버 우선): "상권분석 사이트", "강남 상권분석", "카페창업 입지", "AI 상권분석" (선점)
- **핵심 트릭**: 지역별 25개 글을 MarketScope 자체 Tool로 자동 생성 → 30분 다듬기 → 게시 → 글 자체가 제품 데모

**4.6 첫 100명 채널 믹스**
| 채널 | 목표 | 시간 |
|---|---|---|
| 지인 네트워크 (M1 인터뷰 leverage) | 25 | 매우 낮음 |
| 디스콰이엇 + Build in Public | 20 | 중 |
| 네이버 카페 (장기 신뢰 후) | 15 | 매우 높음 |
| 유튜브 "AI 상권탐정" 채널 | 10 | 매우 높음 |
| 인스타 + 스레드 Reels | 10 | 중 |
| 블로그 SEO | 5 | 중 |
| 오프라인 (전단지 + 창업카페 + 부동산 직방문) | 10 | 중 |
| 링크드인 B2B | 5 | 낮음 |
| **합계** | **100** | |

**4.7 Founding Member 100명 캠페인**
- 첫 100명 유료 → "평생 50% 할인 (월 4,950원)" 락인
- 가장 강력한 첫 100명 유인책 (LTV 손실보다 사회적 증거 가치 큼)

### 시간 분배
코딩 50% / 인터뷰 20% / 마케팅 25% / 운영 5%

---

## 5. Stage 3 — Growth (M5~M9, 3~6개월)

### 목표
MRR 100만 → 500만, Churn < 10%, CAC < LTV 명확, Phase 3 기능 가치 검증된 순서로 출시.

### 해야 할 일

**5.1 채널별 CAC 측정 + 더블다운**
- UTM + GA로 채널별 결제 전환율
- 효과 큰 1~2개 채널에 80% 시간 집중, 나머지 버림
- LTV 추정 (₩69,300 with 10% churn, ₩138,600 with 5%) → 유료 광고는 대부분 적자, 오가닉 + B2B만 흑자
- **연간 결제 도입** (79,000원, 34% 할인) → LTV 2~3배 증가

**5.2 Phase 3 기능 — 가치 검증된 순서**
- F09 매출 시뮬레이션: "월매출 OO원 예상" — 가장 강력한 마케팅 hook → 우선
- F10 PDF 리포트: 부동산 중개인 B2B 진입 쐐기 → 두 번째
- F06 히트맵: 시각적 임팩트 크지만 매출 직결 약함 → 세 번째 또는 후순위

**5.3 추천 프로그램 (Refer-a-Friend)**
- 추천인 1개월 무료 + 피추천인 50% 할인
- 카톡 공유 버튼 + 쿠폰 코드 (이메일 X)
- 추천 → 결제 비율 측정

**5.4 제휴 파트너십 (3~5개 도전)**
- 네이버 카페 운영자 정식 후원 (월 10~30만원)
- 부동산 사무소 단체 계약 (B2B 49,000원/3계정) — 강남/홍대/성수 30곳 직방문
- 소상공인진흥공단 컨설턴트 무료 제공 → 입소문
- 정부 사업 응모 (소상공인 디지털 전환, K-스타트업, 서울시 청년창업)

**5.5 가격 A/B 실험 (실데이터 기반)**
| 그룹 | 가격 |
|---|---|
| A | 5,500원 (가격 민감도) |
| B | 9,900원 (control) |
| C | 14,900원 (프리미엄 인식) |
| D | 9,900원 + 7일 체험 (체험 단축) |

측정: 결제 전환율, ARPU, 첫 달 churn, LTV

**5.6 운영 자동화**
- Toss webhook → 자동 가입/해지/만료
- 카카오 알림톡 자동화 (영수증, 만료 D-7/D-1)
- Sentry 에러 → 카톡 봇 즉시 알림
- ETL 자동화: GitHub Actions cron `cron: '0 0 1 1,4,7,10 *'` (`server/data/etl/runner.py`)

### 시간 분배
코딩 30% / 인터뷰 25% / 마케팅 35% / 운영 10%

---

## 6. Stage 4 — Scale (M10+, 6개월+)

### 목표
MRR 500만~1,000만, B2B 고객 5~10개사, 1인 → 1.5인 (외주/파트타임), 지방 또는 카테고리 확장.

### 해야 할 일

**6.1 인프라 — PaaS → AWS Seoul 이전 (트리거: MAU 10K+ 또는 SLA 요구 / B2B 진입)**

| 컴포넌트 | 선택 |
|---|---|
| Container | **AWS ECS Fargate** (k8s 대비 운영 부담 1/5) |
| LB | ALB (HTTP/2 + SSE 호환) |
| DB | **Aurora PostgreSQL Serverless v2** + PostGIS, RDS Proxy |
| Cache | **ElastiCache Redis** cluster |
| Storage | S3 + CloudFront (PDF, GeoJSON) |
| Frontend | Vercel Pro 유지 (또는 ECS+CloudFront 이전) |
| WAF | AWS WAF + Cloudflare 이중 |
| Secret | AWS Secrets Manager |
| Queue | SQS + Celery worker (별도 ECS service) |
| Analytics | BigQuery 또는 ClickHouse on ECS |
| LLM trace | Langfuse self-hosted on ECS |

**Stage 4 월 비용 추정**: 약 330만~500만원 (LLM 75%)
**손익분기**: MAU 50,000명 × 5% 전환 × 9,900원 = MRR 2,475만원

**6.2 마이그레이션 (Stage 2 → Stage 4, 3주 단계화)**
- Week 1: Aurora 프로비저닝, Neon → Aurora `pg_dump|pg_restore`, schema diff 검증
- Week 2: ECS Fargate task definition, staging E2E 검증
- Week 3 D-day: DNS TTL 60s 단축 → Fly read-only → 최종 dump → DNS cutover → 24h 모니터링

**비파괴 보장**: 표준 PostgreSQL+PostGIS+컨테이너만 사용 → 데이터 마이그레이션만 신경

**6.3 B2B 진출 (가장 큰 성장 레버)**
- 부동산 사무소: 49,000원/3계정 (계정당 16,300원, 65% premium)
- 중대형 사무소: 149,000원/10계정 + 전담 매니저
- 프랜차이즈 본사: 협의 (월 200만~), API + 가맹개발팀 5명, 신규 가맹점 입지 분석
- 정부/공공기관: SaaS 라이선스 + 조달청 나라장터 등록

**6.4 첫 채용 우선순위**
1. 콘텐츠 마케터 파트타임 (50~100만원/월)
2. CS 파트타임
3. 풀스택 개발자 (가장 마지막)

**6.5 지방 확장**: 부산 → 대구 → 인천 (서울 ETL 코드 재활용)

### 시간 분배
코딩 20% / 인터뷰 25% / 마케팅 35% / 운영 20%

---

## 7. 6개월 마케팅 캘린더 (M1~M6)

| 월 | 핵심 활동 | KPI 목표 |
|---|---|---|
| **M1** | 인터뷰 15명 + 랜딩 + 사업자등록 + Build in Public 10편 + 유튜브 채널 개설 + 네이버 카페 5개 가입 | 베타 신청 50명, 인터뷰 15명, 유튜브 50구독 |
| **M2** | 베타 100명 access + 첫 NPS + 블로그 5편 + 약관/처리방침 + Toss 심사 완료 | 베타 100명, NPS 30+, 블로그 8편, 유튜브 200구독 |
| **M3** | 결제 OPEN + Founding Member 100명 캠페인 + 보도자료 + 디스콰이엇 정식 런칭 + 네이버 검색광고 일 1만원 실험 | 신규가입 300명, **유료 30명**, MRR 14.8만원, 보도자료 1~2건 |
| **M4** | 추천 프로그램 + B2B 49,000원 플랜 출시 + 가격 A/B 시작 + 부동산 중개사 직방문 (성수/잠실 10곳) | 누적가입 800, **누적유료 100명**, MRR 70만원, 유튜브 1,000구독 |
| **M5** | 블로그 콘텐츠 가속 (주 3편) + 연간 결제 도입(79,000원) + 카페 정식 후원 1곳 + 인플루언서 무료 협찬 | 누적가입 1,600, 누적유료 160명, MRR 120만원, NPS 40+ |
| **M6** | 유료 200명 도전 + 메이저 매체 인터뷰 + B2B 첫 사무소 계약 3곳 + 6개월 회고 + 정부 사업 결과 | 누적가입 2,600, **누적유료 200명** (낙관 300), MRR 200만원 (낙관 500만) |

---

## 8. 즉시 액션 — 내일(M1-W1-D1) 5시간 안에 끝낼 7가지

1. **홈택스 사업자등록** (개인 간이과세) — 30분, 0원
2. **marketscope.kr 도메인 구매** — 10분, 1.5만원
3. **Toss Payments 가맹점 신청** (심사 1~2주 시작) — 1시간
4. **인스타/스레드/X/디스콰이엇/링크드인 5개 계정 + 프로필 통일** — 1시간
5. **첫 디스콰이엇 메이커로그 글 발행**: "0명에서 시작하는 SaaS" — 30분
6. **네이버 카페 5개 가입** (장사의 신, 자영업의 모든것, 카페창업카페, 외식창업이야기, 부동산스터디) + 댓글 5개 — 1시간
7. **지인 창업자 5명 명단 + 첫 1명 인터뷰 요청 카톡** — 30분

---

## 9. 절대 함정 회피 가이드

| 함정 | 대응 |
|---|---|
| "기능을 더 만들면 팔린다" | Phase 2/3 기능은 결제 의향 검증 후에만. PMF 검증에 집중 |
| "디자인 완벽주의" | shadcn/ui 그대로, 디자인 외주 = 함정 |
| "유료 광고로 빠르게 키우자" | LTV/CAC 계산상 오가닉/B2B 외 모두 적자. M5 이후 신중히 |
| "VC 펀딩 받자" | 1인 SaaS는 부트스트래핑이 답. 한국 정부 예비창업패키지 1억만 검토 가치 |
| "직원/외주 빨리 채용" | 매출 500만/월 전 채용 금지. 콘텐츠 외주가 첫 번째 |
| "100% 정확도 추구" | 95% + 면책 명확화. "참고용, 결정 책임은 사용자" |
| "Vercel 함수에 SSE 프록시" | Hobby 10s/Pro 60s 컷이 LLM 응답보다 짧음. 클라이언트 → backend 직접 호출 |
| "Supabase Auth 쓰면서 Neon DB" | Auth 쓸 거면 Supabase, 안 쓸 거면 Neon. 쪼개지 말 것 |

---

## 10. Critical Files (참고/수정 대상)

이 plan을 실행할 때 가장 중요한 파일들 (리포 상대 경로 — 2026-07-04 옛 머신 절대경로에서 교체):

- `server/server/agent/tools/district_summary.py` — **Stage 0 블로커**. Real DB 분기 작동 수정. 수정 안 되면 데모 불가.
- `server/server/data/etl/seoul_opendata.py` — **Stage 0 블로커**. 5개 핵심 상권 boundary 수동 폴리곤 주입 (또는 fixture). 지도 데모 가능 여부 결정.
- `frontend/src/components/chat/cards/` — Summary/Compare/Recommend/Risk Card 4종 다크 테마 일관성. 베타 첫인상의 90%.
- `server/server/api/routes/chat.py` — `_sessions` dict (line 25), `_chat_semaphore=20` (line 31). **Stage 1**: 베타 키 화이트리스트 + 사용량 JSON Lines 로그 추가. **Stage 2**: Redis store 이관 필수.
- `server/server/main.py` — lifespan, CORS, health endpoint. **Stage 2 P0**: `/ready` 분리 + CORS env화 + Sentry + slowapi rate limit.
- `server/server/config.py` — `cors_origins` (line 50) 환경변수화 + LLM provider/timeout. 모든 환경변수의 single source of truth.
- `server/Dockerfile` — multi-stage runner target, **이미 production-ready**, Fly/Render/ECS에 그대로 배포.
- `docker-compose.yml` — Fly/ECS 매핑 reference. release_command/healthcheck 패턴 재사용.
- `frontend/next.config.mjs` — Vercel rewrite 정책. **SSE는 직접 호출로 분리** (Vercel을 통하지 않음).
- `server/alembic/versions/001_initial_schema.py` — PostGIS schema (Neon/Aurora migration reference). Stage 2에서 다음 리비전(users/subscriptions/usage_logs) 추가.
- `docs/spec/B01-business-model.md` — Stage 2 OAuth/Toss/Tier 청사진. 이미 잘 작성되어 있어 Stage 0~1엔 손대지 말 것.
- `data/seed/marketscope_seed.dump` — 5MB binary, 초기 Neon import 자료.

> ⚠ 2026-07-04 정정: 일부 라인 참조는 드리프트됨 — `cors_origins` 는 현행 `config.py:72`, alembic 은 이미 001~005 존재(다음 리비전은 006). Stage 0 블로커 2건은 해소 완료.

---

## 11. Verification — 단계별 성공 검증 방법

### Stage 0 검증 (M1 종료 시)
```
□ 인터뷰 노트 15건 작성됨 (customer-discovery-notes.md)
□ "유료 의향" 답변 3명+ (정량)
□ 랜딩 페이지 이메일 30개+ (Stibee dashboard)
□ 사업자등록증 + 통신판매업 + 처리방침 + 약관 4개 문서 완비
□ marketscope.kr DNS 정상 해결
□ Toss Payments 심사 진행 중 또는 완료
□ Real 모드 데모: 5개 상권 클릭 → 폴리곤 표시 → SummaryCard 정상 렌더링
```

검증 명령:
- `curl https://marketscope.kr/api/health` → 200
- 브라우저에서 강남역 클릭 → SummaryCard 한국어 응답 + 차트
- 인터뷰 노트 grep으로 공통 페인 포인트 2~3개 추출

### Stage 1 검증 (M2 종료 시)
```
□ Fly.io 배포 성공: https://api.marketscope.ai/health → 200
□ Sentry 첫 에러 capture 확인
□ UptimeRobot 5분 체크 정상
□ 베타 사용자 5~10명 active (chat.py 사용량 로그 기준)
□ Clarity 세션 녹화 5건+ 분석 완료
□ 결제 의향 검증: 가짜 결제 페이지에서 카드 등록 1~2명
□ "가장 가치 있는 카드" 정량적으로 1~2개 식별
□ 월 인프라 비용 < 30,000원
```

검증 명령:
- `fly logs -a marketscope-api` → 정상 로그
- Anthropic/Gemini console에서 일 비용 < $1
- PostHog (또는 자체 로그) funnel: 가입 → 첫 분석 → 카드 노출 비율

### Stage 2 검증 (M4 종료 시)
```
□ OAuth (Google + 카카오) 정상 가입
□ Toss 빌링키 정기결제 성공 + 알림톡 수신
□ Tier 게이팅: Free 일 5회 초과 시 차단 + paywall 노출
□ Founding Member 누적 100명 (또는 가까이)
□ MRR 50만원+ (50명 × 9,900 × 0.5 할인)
□ 첫 달 churn < 30%
□ Sentry error rate < 0.5%
□ 채널별 CAC 측정 가능 (UTM + GA)
```

검증 명령:
- DB query: `SELECT COUNT(*) FROM subscriptions WHERE status='active'`
- Toss dashboard MRR 확인
- GA4 funnel: 채널별 가입 → 결제 전환

### Stage 3 검증 (M9 종료 시)
```
□ MRR 500만원+
□ Churn < 10%/월
□ CAC < LTV (LTV ≈ 6만원 가정 시 CAC < 6만원)
□ 채널 1~2개에 80% 집중, ROI 명확
□ B2B 첫 사무소 1~3곳 계약
□ 정부 사업 1건 응모 또는 선정
```

### Stage 4 진입 트리거
```
□ MAU > 10,000 또는
□ B2B 계약 SLA 99.9% 요구 또는
□ 동시 SSE > 200 (Fly autoscale max 6 근접) 또는
□ Neon storage > 8GB / Upstash 비용 폭증
```

---

## 12. 핵심 원칙 (한 줄 요약)

1. **하지 말 것을 정하는 것이 할 것을 정하는 것보다 중요하다.**
2. **코드는 자산이 아니다. 학습된 통찰만이 자산이다.**
3. **10명의 깊은 사용자 > 1만명의 얕은 방문자.**
4. **오픈업은 데이터를 보여준다. MarketScope는 결정을 내려준다.** (모든 마케팅 메시지의 north star)
5. **어떤 Stage에서도 코딩 시간이 60%를 넘으면 위험 신호다.** (개발자가 가장 흔히 빠지는 함정)
