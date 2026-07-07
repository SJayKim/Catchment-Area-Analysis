# QuickStart Guide

> 클론 후 5분 안에 서비스 실행하기

---

## 사전 준비

| 항목 | 최소 버전 | 확인 명령 |
|------|-----------|-----------|
| Docker Desktop | 24+ | `docker --version` |
| Node.js | 18+ | `node --version` |
| Python | 3.12+ | `python --version` |
| Git | 2.30+ | `git --version` |

**필수 키**: Kakao Map JS Key ([developers.kakao.com](https://developers.kakao.com)) + LLM Key — Anthropic ([console.anthropic.com](https://console.anthropic.com)) 또는 Gemini ([aistudio.google.com/apikey](https://aistudio.google.com/apikey))

**선택 키**: 서울 열린데이터 ([data.seoul.go.kr](https://data.seoul.go.kr), Path C 전용) · Langfuse ([langfuse.com](https://langfuse.com), LLM 트레이싱)

---

## Step 1. 환경 변수 설정

```bash
cp .env.example .env.dev   # .env=prod, .env.dev=로컬 dev 관례
```

> ⚠ `.env.dev` 없으면 컨테이너 기동 실패(`env file .env.dev not found`). `config.py` 는 `.env.dev` 우선 로드 → `.env` 폴백.

`.env.dev` 필수 항목:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...        # Anthropic 사용 시
GOOGLE_API_KEY=AI...                # Gemini 사용 시 (기본값)
NEXT_PUBLIC_KAKAO_MAP_KEY=your_kakao_js_key
LLM_PROVIDER=gemini                 # "gemini" 또는 "anthropic"
# AGENT_LOOP_VERSION=v2             # 기본 v2 (Trust Kernel 루프) — 레거시 PAE 롤백 시 pae
```

> DATABASE_URL, REDIS_URL 등 나머지는 docker-compose 기본값과 일치하므로 수정 불필요.

---

## Step 2. 실행 경로 선택

| 경로 | 소요 시간 | 필요 인프라 | 데이터 | 추천 대상 |
|------|-----------|-------------|--------|-----------|
| **Path A** Mock 모드 | ~2분 | 없음 | 5개 샘플 상권 | 빠른 데모, UI/Agent 개발 |
| **Path B** Seed 복원 ★ | ~5분 | Docker | 1,650개 실제 상권 | 실데이터 테스트, 일반 개발 |
| **Path C** Full ETL | ~15분 | Docker + 서울 열린데이터 API | 1,650개 최신 상권 | 데이터 최신화 |

---

### Path A: Mock 모드 (DB 없이 바로 실행)

5개 샘플 상권(강남역·홍대·건대·명동·서울역)으로 전체 기능 체험. DB/Redis 불필요.

```bash
# .env.dev: USE_MOCK=true
cd server && pip install -e ".[dev]"
uvicorn server.main:app --reload --port 8000
# 새 터미널
cd frontend && npm install && npm run dev
```

`http://localhost:3000` 접속.

---

### Path B: Seed 복원 (추천 — 실데이터 빠른 세팅)

시드 덤프(`data/seed/marketscope_seed.dump`, 5MB) pg_restore. 서울 열린데이터 API 키 불필요.

```bash
# .env.dev: USE_MOCK=false
python scripts/setup_db.py --quick   # Docker 시작 → 마이그레이션 → 시드 복원 → 검증
cd server && pip install -e ".[dev]"
uvicorn server.main:app --reload --port 8000
# 새 터미널
cd frontend && npm install && npm run dev
```

`http://localhost:3000` 접속 → 1,650개 실제 상권 분석.

---

### Path C: Full ETL (API에서 직접 수집)

```bash
# .env.dev: SEOUL_OPENDATA_API_KEY=your_key, USE_MOCK=false
python scripts/setup_db.py --full
# Backend + Frontend 실행 — Path B의 마지막 3단계와 동일
```

---

### 대안: Docker Compose로 전체 서비스 한 번에 실행

> ⚠ frontend 이미지는 **빌드 타임에 Kakao 키를 bake** — `docker compose up -d` 전 호스트 셸에 `export NEXT_PUBLIC_KAKAO_MAP_KEY=...` 필수.

```bash
export NEXT_PUBLIC_KAKAO_MAP_KEY=your_kakao_js_key
docker compose up -d                   # db + redis + migrate + seed + backend + frontend + nginx
docker compose logs -f backend frontend
# 개발 모드(소스 자동 리로드): docker compose up -d db redis && docker compose --profile dev up
```

---

## Step 3. 동작 확인

1. `http://localhost:3000` → `/app` 진입 → 지도 상권 클릭 → 프리뷰 카드 → "AI 분석 보기"
2. 채팅창 테스트: `"강남역 분석해줘"` / `"여기서 뭐하면 좋을까?"` / `"홍대랑 비교해줘"`
3. 헬스 체크: `curl http://localhost:8000/health` / `docker compose exec db psql -U marketscope -c "SELECT count(*) FROM districts;"`

---

## DB 관리 명령어

```bash
python scripts/setup_db.py --reset   # 전체 데이터 삭제
python scripts/setup_db.py --quick   # 리셋 후 시드 복원

# 볼륨까지 완전 초기화
docker compose down -v
docker compose up -d db redis
python scripts/setup_db.py --quick
```

---

## 개발 명령어 요약

```bash
npx prettier --write .                            # TS 포맷
cd server && ruff check --fix . && ruff format .  # Python 린트/포맷
cd frontend && npx playwright test                # E2E 테스트
cd server && pytest                               # Backend 테스트
docker compose logs -f db                         # 로그
```

---

## 트러블슈팅

### Docker Desktop이 실행 중이 아님
→ Docker Desktop 앱 실행 후 재시도.

### 포트 충돌 (5432, 6379, 8000, 3000)
→ `netstat -ano | findstr :5432` 로 프로세스 확인 후 종료, 또는 `docker compose down` 후 재시작.

### Seed 파일이 LFS 포인터인 경우
→ `git lfs pull` 실행 후 재시도.

### Python 인코딩 오류 (Windows)
→ `PYTHONIOENCODING=utf-8` 설정: Git Bash `export PYTHONIOENCODING=utf-8` / CMD `set PYTHONIOENCODING=utf-8` / PS `$env:PYTHONIOENCODING="utf-8"`.

### Kakao Map이 로드되지 않음
→ `.env.dev` `NEXT_PUBLIC_KAKAO_MAP_KEY` 확인. Docker 빌드 시 키는 **빌드 타임 build-arg** — `docker compose build frontend` 전 호스트 `export NEXT_PUBLIC_KAKAO_MAP_KEY=...` 필수. Kakao Developers 콘솔 → 플랫폼 → Web → 사이트 도메인에 `http://localhost:3000` 등록.

### AI 챗봇이 응답하지 않음
→ `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` 와 `LLM_PROVIDER` 값 일치 확인. Backend 로그: `docker compose logs -f backend`.

---

## 프로젝트 구조 참고

```
.env.example                    # 환경 변수 템플릿 (.env=prod / .env.dev=로컬 dev 로 복사)
docker-compose.yml              # PostGIS + Redis + Backend + Frontend + Nginx
scripts/setup_db.py             # DB 자동 프로비저닝
data/seed/marketscope_seed.dump # 시드 데이터 (pg_restore용)
server/                         # FastAPI Backend (server/main.py, config.py, alembic/)
frontend/                       # Next.js Frontend (src/, package.json)
docs/                           # architecture/ spec/ status/
```
