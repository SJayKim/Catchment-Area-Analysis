# QuickStart Guide

> 클론 후 5분 안에 서비스 실행하기

---

## 사전 준비

| 항목 | 최소 버전 | 확인 명령 |
|------|-----------|-----------|
| **Docker Desktop** | 24+ | `docker --version` |
| **Node.js** | 18+ | `node --version` |
| **Python** | 3.12+ | `python --version` |
| **Git** | 2.30+ | `git --version` |

### API 키 발급 (필수)

| 키 | 용도 | 발급 |
|----|------|------|
| **Kakao Map JavaScript Key** | 지도 표시 | [developers.kakao.com](https://developers.kakao.com) → 앱 생성 → JavaScript 키 |
| **LLM API Key** (택 1) | AI 챗봇 | Anthropic: [console.anthropic.com](https://console.anthropic.com) / Google: [aistudio.google.com](https://aistudio.google.com/apikey) |

### API 키 발급 (선택)

| 키 | 용도 | 발급 |
|----|------|------|
| 서울 열린데이터 API Key | Full ETL (Path C) | [data.seoul.go.kr](https://data.seoul.go.kr) → 마이페이지 → 인증키 |
| Langfuse Keys | LLM 트레이싱 | [langfuse.com](https://langfuse.com) → 프로젝트 → API Keys |

---

## Step 1. 환경 변수 설정

```bash
# 로컬 개발용 env 파일 생성 (.env=prod, .env.dev=로컬 dev 관례)
cp .env.example .env.dev
```

> ⚠ `docker compose up`(전체 스택) / `--profile dev` 경로는 **`.env.dev` 파일이 반드시 있어야 한다**
> (backend / backend-dev / frontend-dev 서비스가 `env_file: .env.dev` 를 요구 — 없으면 `env file .env.dev not found` 로 기동 실패).
> 호스트에서 직접 uvicorn 을 띄우는 경우에도 `config.py` 가 `.env.dev` 를 우선 로드하고, 없으면 `.env` 로 폴백한다.

`.env.dev` 파일을 열고 아래 값을 입력:

```dotenv
# 필수 — LLM (둘 중 하나)
ANTHROPIC_API_KEY=sk-ant-...        # Anthropic 사용 시
GOOGLE_API_KEY=AI...                # Gemini 사용 시 (기본값)

# 필수 — 지도
NEXT_PUBLIC_KAKAO_MAP_KEY=your_kakao_js_key

# LLM 설정 (기본값: Gemini)
LLM_PROVIDER=gemini                 # "gemini" 또는 "anthropic"
# AGENT_LOOP_VERSION=v2             # 기본값 v2 (모델주도 agentic loop + Trust Kernel) — 레거시 PAE 그래프로 롤백 시 pae
```

> 나머지 값(DATABASE_URL, REDIS_URL 등)은 docker-compose 기본값과 일치하므로 수정 불필요.
>
> 참고: Agent 아키텍처 기본값은 **v2 agentic loop**(`agent_loop_version="v2"`)이며, PAE(Planner-Actor-Evaluator)는
> Mock 모드 폴백 및 `AGENT_LOOP_VERSION=pae` 롤백 스위치용 레거시다. (구 `AGENT_MODE` 설정은 2026-07-05 제거 —
> 관측 필드 `agent_mode` 는 이제 실효 서빙 루프를 자동 보고한다.)

---

## Step 2. 실행 경로 선택

| 경로 | 소요 시간 | 필요 인프라 | 데이터 | 추천 대상 |
|------|-----------|-------------|--------|-----------|
| **Path A** Mock 모드 | ~2분 | 없음 (DB/Redis 불필요) | 5개 샘플 상권 | 빠른 데모, UI/Agent 개발 |
| **Path B** Seed 복원 | ~5분 | Docker (PostGIS + Redis) | 1,650개 실제 상권 | 실데이터 테스트, 일반 개발 |
| **Path C** Full ETL | ~15분 | Docker + 서울 열린데이터 API 키 | 1,650개 최신 상권 | 데이터 최신화, ETL 파이프라인 검증 |

---

### Path A: Mock 모드 (DB 없이 바로 실행)

Docker 없이 Backend + Frontend만 실행합니다. 5개 샘플 상권(강남역, 홍대, 건대, 명동, 서울역)으로 전체 기능을 체험합니다.

```bash
# 1. .env.dev에서 Mock 모드 활성화
#    USE_MOCK=true 로 변경

# 2. Backend 실행
cd server
pip install -e ".[dev]"
uvicorn server.main:app --reload --port 8000

# 3. Frontend 실행 (새 터미널)
cd frontend
npm install
npm run dev
```

`http://localhost:3000` 접속.

---

### Path B: Seed 복원 (추천 -- 실데이터 빠른 세팅)

시드 덤프 파일(`data/seed/marketscope_seed.dump`, 5MB)을 pg_restore로 복원합니다.
서울 열린데이터 API 키 없이도 실제 1,650개 상권 데이터로 실행 가능합니다.

```bash
# 1. .env.dev 확인: USE_MOCK=false

# 2. 자동 세팅 스크립트 (Docker 시작 → 마이그레이션 → 시드 복원 → 검증)
python scripts/setup_db.py --quick

# 3. Backend 실행
cd server
pip install -e ".[dev]"
uvicorn server.main:app --reload --port 8000

# 4. Frontend 실행 (새 터미널)
cd frontend
npm install
npm run dev
```

`http://localhost:3000` 접속 → 서울시 1,650개 실제 상권으로 분석.

**`setup_db.py --quick`이 하는 일:**
1. Docker Desktop 실행 확인
2. `db` (PostGIS) + `redis` 컨테이너 시작
3. PostgreSQL 준비 대기
4. Alembic 마이그레이션 실행
5. `marketscope_seed.dump` → pg_restore
6. 테이블별 행 수 검증 출력

---

### Path C: Full ETL (API에서 직접 수집)

서울 열린데이터 API에서 최신 데이터를 직접 수집합니다.

```bash
# 1. .env.dev에 서울 열린데이터 API 키 입력
#    SEOUL_OPENDATA_API_KEY=your_key
#    USE_MOCK=false

# 2. 전체 ETL 실행
python scripts/setup_db.py --full

# 3. Backend + Frontend 실행 (Path B의 3~4번과 동일)
cd server && uvicorn server.main:app --reload --port 8000
# (새 터미널)
cd frontend && npm run dev
```

---

### 대안: Docker Compose로 전체 서비스 한 번에 실행

Backend와 Frontend도 Docker 컨테이너로 실행하고 싶다면 (**`.env.dev` 필수** — Step 1 참조):

```bash
# frontend 이미지는 빌드 타임에 Kakao 키를 bake — 빌드 전에 호스트 셸에 export 필요
export NEXT_PUBLIC_KAKAO_MAP_KEY=your_kakao_js_key

# 전체 서비스 (db + redis + migrate + seed + backend + frontend + nginx)
docker compose up -d

# 로그 확인
docker compose logs -f backend frontend
```

`http://localhost:3000` 접속. 시드 데이터 자동 복원됨.

**개발 모드** (소스 코드 변경 시 자동 리로드):

```bash
# DB + Redis + Backend(hot-reload) + Frontend(hot-reload)
docker compose up -d db redis
docker compose --profile dev up
```

---

## Step 3. 동작 확인

서비스가 정상 실행되면:

1. `http://localhost:3000` 접속 — 랜딩 페이지 로드, `/app` 진입 시 서울 지도 + 채팅 화면
2. 지도에서 상권 폴리곤 클릭 → 프리뷰 카드(Zero-LLM, F13) 표시 → "AI 분석 보기" 클릭 시 AI 분석 시작
3. 채팅창에 자연어 입력:
   - `"강남역 분석해줘"` → SummaryCard (유동인구 + 매출 + 점포)
   - `"여기서 뭐하면 좋을까?"` → RecommendCard (업종 추천)
   - `"홍대랑 비교해줘"` → CompareCard (상권 비교)
   - `"이 자리 위험해?"` → RiskCard (리스크 분석)

### 헬스 체크

```bash
# Backend 상태 확인
curl http://localhost:8000/health

# DB 연결 확인 (Real 모드)
docker compose exec db psql -U marketscope -c "SELECT count(*) FROM districts;"
```

---

## DB 관리 명령어

```bash
# DB 리셋 (전체 데이터 삭제 후 재생성)
python scripts/setup_db.py --reset

# 리셋 후 시드 다시 복원
python scripts/setup_db.py --quick

# Docker 볼륨까지 완전 초기화
docker compose down -v
docker compose up -d db redis
python scripts/setup_db.py --quick
```

---

## 개발 명령어 요약

```bash
# 린트 / 포맷
npx prettier --write .                        # TypeScript
cd server && ruff check --fix . && ruff format .  # Python

# 테스트
cd frontend && npx playwright test            # E2E 테스트 (Playwright)
cd server && pytest                           # API 테스트

# 로그 확인
docker compose logs -f db                     # PostgreSQL 로그
docker compose logs -f redis                  # Redis 로그
```

---

## 트러블슈팅

### Docker Desktop이 실행 중이 아님
```
Docker daemon is not running. Start Docker Desktop first.
```
→ Docker Desktop 앱 실행 후 다시 시도.

### 포트 충돌 (5432, 6379, 8000, 3000)
```
Error: bind: address already in use
```
→ 해당 포트를 사용하는 프로세스 종료: `netstat -ano | findstr :5432`
→ 또는 `docker compose down`으로 기존 컨테이너 정리 후 재시작.

### Seed 파일이 LFS 포인터인 경우
```
Seed file looks like a Git LFS pointer. Run 'git lfs pull' first.
```
→ `git lfs pull` 실행 후 다시 시도.

### Python 인코딩 오류 (Windows)
```
UnicodeDecodeError: 'cp949' codec can't decode ...
```
→ 환경 변수에 `PYTHONIOENCODING=utf-8` 설정:
```bash
export PYTHONIOENCODING=utf-8   # Git Bash
set PYTHONIOENCODING=utf-8      # CMD
$env:PYTHONIOENCODING="utf-8"   # PowerShell
```

### Kakao Map이 로드되지 않음
→ `.env.dev`에 `NEXT_PUBLIC_KAKAO_MAP_KEY` 값 확인.
→ Docker 로 frontend 를 빌드하는 경우 키는 **빌드 타임 build-arg** 로 들어감 — 빌드 전에 호스트 셸에 `export NEXT_PUBLIC_KAKAO_MAP_KEY=...` 후 `docker compose build frontend` 재실행.
→ Kakao Developers 콘솔에서 **플랫폼 → Web → 사이트 도메인**에 `http://localhost:3000` 등록.

### AI 챗봇이 응답하지 않음
→ `.env.dev`에 LLM API 키 확인 (`ANTHROPIC_API_KEY` 또는 `GOOGLE_API_KEY`).
→ `LLM_PROVIDER`가 설정한 키와 일치하는지 확인 (`gemini` vs `anthropic`).
→ Backend 로그 확인: `docker compose logs -f backend` 또는 터미널 출력.

---

## 프로젝트 구조 참고

```
├── .env.example                   # 환경 변수 템플릿 (.env=prod / .env.dev=로컬 dev 로 복사해 사용)
├── docker-compose.yml             # PostGIS + Redis + Backend + Frontend + Nginx
├── scripts/setup_db.py            # DB 자동 프로비저닝 스크립트
├── data/
│   └── seed/marketscope_seed.dump # 시드 데이터 (pg_restore용) — 리포에 포함된 유일한 데이터 파일
│       # (선택) data/shp/OA-15560.shp, data/csv/OA-15584.csv 는 서울 열린데이터에서
│       # 직접 내려받아 배치하는 파일 — 리포 미포함, setup_db.py 가 존재할 때만 사용
├── server/                        # FastAPI Backend
│   ├── server/main.py            # 앱 진입점
│   ├── server/config.py          # 환경 설정
│   ├── alembic/                  # DB 마이그레이션
│   └── pyproject.toml            # Python 의존성
├── frontend/                      # Next.js Frontend
│   ├── src/                      # React 컴포넌트 & 페이지
│   └── package.json              # Node 의존성
└── docs/                          # 문서
    ├── architecture/             # 시스템 아키텍처
    ├── spec/                     # 기능 스펙
    └── status/                   # 진행 상황
```
