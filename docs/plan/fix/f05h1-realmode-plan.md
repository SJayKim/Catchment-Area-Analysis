# Plan — F05-H1 Korean Particles Fix + Real Mode E2E Run

> 작성일: 2026-04-07
> 범위: (1) F05-H1 SOFT FAIL 1건 해소 / (2) Real mode 42 시나리오 재실행
> 기준: `docs/qa/e2e-run-2026-04-07.md` (Mock 94/100 READY)

---

## A. F05-H1: Korean particles → multi-district 라우팅 fix

### A.1 현상

| 입력 | 결과 |
|------|------|
| `강남역, 홍대입구 비교해줘` | ✅ PASS — CompareCard 정상 |
| `강남역과 홍대입구를 비교해줘` | ❌ SOFT FAIL — `numCount=1`, CompareCard 미렌더 |

(`F05-H1-2-way/verdict.json`: "DOM only shows the user query and a 'thinking' indicator with no CompareCard, no comparison numbers")

### A.2 근본 원인 (코드 트레이스)

**Step 1 — `chat.py` 자동감지 (`api/routes/chat.py:124`)**:
- `detect_district_by_name(message)` 호출 — message 내 **첫 번째** 매칭 상권만 반환
- "강남역과 홍대입구를 비교해줘" → 강남역과 → 조사 `과` strip → 강남역 → return (홍대입구 못 봄)
- `body.district_code = D3001` 단일 코드만 세팅

**Step 2 — `planner.py` rule classification (`agent/nodes/planner.py:25`)**:
- `intents.yaml`의 `comparison: (비교|vs|대비|차이)` → 매칭 → `(comparison, 0.9)`
- confidence ≥ 0.7 → **LLM classifier 미호출**
- `referenced_districts = [district_code]` = `[D3001]` (1개만)

**Step 3 — comparison-specific 보정 (`planner.py:218`)**:
```python
if intent == "comparison" and len(referenced_districts) < 2 and district_code:
    if district_code not in referenced_districts:
        referenced_districts.insert(0, district_code)
```
- `D3001`이 이미 들어있으므로 no-op → 여전히 1개

**Step 4 — `compare_districts` Tool 호출**:
- `district_codes=[D3001]` 1개로 호출 → 비교 데이터 부족 → CompareCard 안 그려짐

### A.3 왜 comma 형식은 동작하는가?

추측: comma 형식 `"강남역, 홍대입구 비교해줘"`도 `detect_district_by_name`은 첫 번째(강남역)만 찾아 같은 상태가 됨. 그러나 PAE Planner LLM이 호출되는 분기 (e.g. comparison 이외 confidence가 다르게 나오거나, parse 후 LLM가 referenced_districts에 둘을 모두 채워주는 케이스)에 의해 통과한 것으로 보임. 검증 후 fix 검증 단계에서 양쪽 모두 안정적으로 PASS함을 확인한다.

**핵심**: Rule path는 _절대_ 다중 상권을 추출하지 않음 → comma도 가끔 fail 가능. **deterministic한 fix가 필요.**

### A.4 Fix 설계

**원칙**: planner의 hot path에 가벼운 deterministic multi-extraction을 추가. LLM 호출 없음.

**변경 1 — Repository protocol 확장 (`repositories/protocols.py`)**:
```python
class DistrictRepository(Protocol):
    ...
    async def detect_districts_in_message(self, message: str) -> list[dict]: ...
    # returns [{"code": "...", "name": "..."}, ...] (multiple matches, deduped)
```

**변경 2 — Mock impl (`repositories/mock/districts.py`)**:
```python
async def detect_districts_in_message(self, message: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for code, d in DISTRICTS.items():
        if d["name"] in message and code not in seen:
            found.append({"code": code, "name": d["name"]})
            seen.add(code)
    return found
```

**변경 3 — Real impl (`repositories/real/districts.py`)**:
- 기존 `detect_district_by_name`의 word/particles/stopwords 로직 재사용
- 첫 매칭에 return 하지 말고 모두 수집 → list 반환
- Dedupe by district_code
- 최대 5개 cap (어드밴서리 입력 방어)

**변경 4 — Planner 조정 (`agent/nodes/planner.py`)**:
```python
# After rule classification, before LLM fallback:
if intent == "comparison":
    from server.repositories import get_data_access
    multi = await get_data_access().districts.detect_districts_in_message(message)
    if multi:
        codes = [m["code"] for m in multi]
        # Merge with current district_code (priority: explicit message > selected)
        if district_code and district_code not in codes:
            codes.insert(0, district_code)
        referenced_districts = codes[:3]  # max 3 (CompareCard limit)
```

**변경 5 — `intents.yaml` 패턴 보강** (방어적):
- 현재 `(비교|vs|대비|차이)` 그대로 유지 (이미 매칭됨)
- 조사 패턴 보강 불필요 — 위 코드 fix가 본질적 해결

### A.5 검증 기준

| 입력 | 기대 결과 |
|------|----------|
| `강남역과 홍대입구를 비교해줘` | CompareCard 2개 상권, numCount ≥ 3 |
| `강남역, 홍대입구 비교해줘` | (회귀) 동일 PASS |
| `강남역, 홍대, 건대 비교해줘` | (F05-H2 회귀) 3개 상권 모두 |
| `강남역과 홍대 vs 건대 어때` | 3개 (조사+vs 혼합) |

### A.6 Risk

| Risk | 완화 |
|------|------|
| Real DB ILIKE prefix가 5개 이상 잘못 매칭 | `[:3]` cap |
| Stopwords가 진짜 상권명을 차단 | 기존 stopwords와 동일 set 재사용 |
| Planner에 I/O 추가 → latency | comparison intent만 호출, Mock은 dict iter (μs), Real은 단일 SQL session |

---

## B. Real mode 42 시나리오 E2E run

### B.1 사전 조건

| 항목 | 상태 |
|------|------|
| Docker DB+Redis | 미기동 (현재 호스트에 컨테이너 없음 — `docker ps` 결과 workspace만) |
| Migration 003 (`category_aliases`) | 코드 존재, 미적용 |
| Seed dump (`data/seed/marketscope_seed.dump`) | 존재 (5MB) |
| `.env`: `USE_MOCK=false` | ✅ 이미 false |
| Backend (`uvicorn`) | 미기동 (현재 Mock 모드 8002로 운영 중이었으나 셧다운 가정) |
| Frontend (`next dev`) | 미기동 |

### B.2 실행 단계

**B.2.1 — DB+Redis+migrate+seed 기동**:
```bash
cd C:/Users/cyon1/OneDrive/Desktop/Catchment-Area-Analysis
docker compose up -d db redis
# health check 대기
docker compose run --rm migrate
docker compose run --rm seed
```

**B.2.2 — Migration 003 검증** (`category_metadata.aliases` 컬럼):
```bash
docker compose exec db psql -U marketscope -d marketscope -c "\d category_metadata"
# aliases 컬럼 존재 확인
```

**B.2.3 — Backend (Real mode)**:
- 옵션 A (Docker): `docker compose up -d backend`
- 옵션 B (로컬): `cd server && USE_MOCK=false uvicorn server.main:app --port 8002`
- → 로컬 옵션 B 채택 (기존 8002 포트 사용, 빠른 재기동)

**B.2.4 — Frontend**:
- `cd frontend && npm run dev` (port 3000 또는 3001)

**B.2.5 — E2E run**:
```bash
cd frontend
npx playwright test ring0-preflight ring1-features ring2-journeys ring3-negative \
    --reporter=list --workers=2
```
- Artifacts: `frontend/e2e/artifacts/run-2026-04-07-real/`
- (helpers에서 `RUN_DIR` env로 분리)

### B.3 Real-only 검증 항목

| 항목 | 기대 |
|------|------|
| **P0-1 Migration 003** | `category_metadata.aliases` 컬럼 존재, Backend startup error 없음 |
| **F03 Real (`district_summary`)** | 1,650개 상권 중 임의 1개에 대해 SummaryCard 정상 (유동인구/매출/점포 실데이터) |
| **F05 Compare Real** | 강남역 vs 홍대입구 실 데이터 비교 (Mock D3001~D3005 아닌 실 코드) |
| **F08 Risk Real (`store_history`)** | store_history 테이블이 비어있음 → graceful "데이터 없음" 응답 (크래시 X) |
| **모든 도구 Repository Real path** | 어떤 Tool도 `NotImplementedError`/`AttributeError` 없음 |

### B.4 알려진 Real-only 블로커 (계획상 SKIP/관찰)

1. **store_history 테이블 empty** — F08 Tool은 graceful empty 반환해야 함 (P0/P1 fix 이후 verified, 재확인)
2. **district_summary Real path** — F03가 Real DB로 동작 (Phase 1B 완료 시 검증됨)
3. **detect_district_by_name 실 데이터 정확도** — 1,650개 상권 중 동명이상권 우려, 검증 필요

### B.5 Mock 모드와의 차이점

| 항목 | Mock | Real |
|------|------|------|
| 상권 수 | 5 (D3001~D3005) | 1,650 |
| 폴리곤 | 단순 사각형 | 실제 SHP 변환 |
| 데이터 출처 | JSON 파일 | PostGIS + Redis |
| 응답 latency | <500ms | 1~3s (DB 쿼리) |

### B.6 평가

- 동일한 fresh subagent 평가 프로토콜 (Ring 1은 5 batches, Ring 2/3는 per-scenario)
- Consumer-experience score 재산출
- Mock과의 회귀 비교 (동일 시나리오에서 응답 품질 차이 기록)

---

## C. 산출물

| 파일 | 내용 |
|------|------|
| `docs/plan/fix/f05h1-realmode-plan.md` | (본 문서) |
| `server/server/repositories/protocols.py` | `detect_districts_in_message` 추가 |
| `server/server/repositories/mock/districts.py` | Mock impl |
| `server/server/repositories/real/districts.py` | Real impl |
| `server/server/agent/nodes/planner.py` | comparison multi-extract 호출 |
| `frontend/e2e/artifacts/run-2026-04-07-real/` | 42개 시나리오 artifact |
| `docs/qa/runs/e2e-run-2026-04-07-real.md` | Real mode run 리포트 |
| `docs/status/current-status.md` | 두 작업 결과 반영 |

---

## D. 실행 순서

1. ✏️ Plan 작성 (본 문서) — **DONE**
2. 🛠️ A.4 변경 1~4 코드 수정
3. 🧪 Mock 모드에서 F05-H1/H2 spec 재실행 → PASS 확인
4. 🐳 B.2.1 Docker DB/Redis 기동 + migration + seed
5. 🔄 B.2.3 Backend Real mode 재기동
6. 🌐 B.2.4 Frontend 재기동
7. 🎬 B.2.5 42 시나리오 실행 (Real mode)
8. 📊 결과 평가 + Consumer-experience score
9. 📝 리포트 + status doc 업데이트
10. 🗒️ Memory 업데이트 (필요 시)

---
*작성일: 2026-04-07*
