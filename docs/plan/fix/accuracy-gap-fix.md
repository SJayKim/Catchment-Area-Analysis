# Accuracy Gap Fix — Edge 엔티티 매핑 + Follow-up 컨텍스트 해석

> Plan 유형: fix
> 작성일: 2026-04-22
> 기준 평가: `docs/status/current-status.md` §프로젝트 완성도 평가 (2026-04-22)
> 선행 조건: 2026-04-22 E2E Consumer-experience 100/100 READY 상태

---

## 1. Context

### 1.1 배경

2026-04-22 E2E + Ops 회귀 Run 에서 code-level 회귀 0, infra 커버리지 100% 를 달성하여 MVP 운영 READY 판정. 같은 시점 3축 완성도 평가에서 **정확성 74/100** 으로 안정성(85) / 효율성(82) 대비 가장 낮게 측정. 2026-04-13 분석 품질 평가에서도 S3(상권비교) 2.6 · S6(시뮬레이션) 6.1 · S7(후속질문) 8.9 로 기준치(9.0) 미달이 이 축에 집중.

정확성 약점은 **6개의 구체적 GAP** 으로 분해됨 (상세: current-status.md §프로젝트 완성도 평가). 본 문서는 GAP 별 원인 / 업계·연구 해결 사례 / MarketScope 적용안 / 통합 로드맵을 담는다.

### 1.2 관련 메모리 (Memory 교훈 반영)

- `feedback_check_env_before_test.md` — USE_MOCK 환경에 따라 district_code 가 달라지므로 fix 는 Mock/Real 양쪽 동시 검증
- `feedback_marketscope_sse_format.md` — 본 Plan 의 rewriter sub-node 는 SSE 이벤트 추가 없이 backend 내부에서만 동작 (SSE 계약 불변)
- `feedback_probe_endpoint_shape_first.md` — Respond 후처리 검증 레이어는 tool_results 의 실제 JSON shape 를 먼저 probe 후 스키마 작성
- `feedback_stale_container_vs_source.md` — 구현 후 E2E 회귀 시 backend 컨테이너 재빌드 강제

### 1.3 GAP 요약

| ID | 카테고리 | 현상 | 체감 빈도 |
|----|---------|------|:--------:|
| A | Entity Linking | `"홍대 vs 성수"` — 2글자 축약어 매칭 누락 → 비교 1개만 | 높음 |
| B | Taxonomy Alias | `"브런치 가게 매출?"` — category_code None → 재질문 1턴 | 중간 |
| C | Query Rewriting | `"홍대 말고 성수로"` — 도치 문장 엔티티 오추출 | 낮음 |
| D | Abstention | Tool 실패 시 LLM 일반 지식으로 메움 ("외식업 폐업률 25%…") | 높음 |
| E | Coreference | `"거기 중에 2030 비율?"` — 지시어 → 특정 카드 매핑 실패 | 높음 |
| F | UX | `"방금 그 비교 PDF"` — 전체 대화 PDF, 선택형 미지원 | 낮음 |

---

## 2. Scope

### 2.1 In Scope

- GAP-A: `_candidate_words` 2글자 허용 + 3-stage candidate ranking + abstain 재질문 카드
- GAP-B: `learned_aliases` 테이블 + LLM fallback + hit_count promote
- GAP-C: Planner 2-pass 의도 재분석 (엔티티 부족 시 LLM re-extract)
- GAP-D: Respond 후처리 검증 레이어 (숫자 Tool attribution 강제)
- GAP-E: pre-Planner coreference rewriter sub-node
- GAP-F: Card 단위 PDF 버튼 (`useReportExport({ messageId })`)

### 2.2 Out of Scope

- LLM 자체 파인튜닝 (비용/운영 부담 과다)
- 음성 입력/다국어 (Phase 2 이후)
- embedding 기반 entity linking (1,650 규모라 `pg_trgm` 충분)
- NLI 앙상블 (HALT-RAG 수준) — 규모상 과함, 정규식 + 필드 체크로 대체

### 2.3 가정

- Real 모드 (USE_MOCK=false) 를 주 대상으로 설계, Mock 은 회귀 보장만
- Gemini flash 호출 (rewrite/alias mining) 은 평균 200ms · ~$0.0002/call 수준 → 캐시/learned_aliases 누적으로 장기적으로는 miss-path 로만 호출
- `state.cards[-1].data` 를 그대로 앵커로 신뢰 — cards 는 이미 검증된 Tool 결과

---

## 3. Design

### 3.1 카테고리 1 — Entity Linking & Fuzzy Place Matching (GAP-A)

#### 3.1.1 업계 사례

- **Google Maps / Kakao Map**: edit distance + 초성 분해 + 별칭 + 사용자 클릭 CTR 가중 합산. Top-k 후보 노출 후 사용자 선택.
- **Babel Street**: 단순 Levenshtein 대신 cross-lingual word embeddings 로 "Samsung / 삼성" 커버. 한국어처럼 divergent 언어에서 효과.
- **Amazon e-commerce**: LLM 기반 candidate generation + learning-to-rank.

#### 3.1.2 연구 접근

- **Entity Linking 3단 파이프라인**: NER → Candidate Generation → Disambiguation ([nlpprogress.com](http://nlpprogress.com/english/entity_linking.html))
- **Disambiguation score** = `w1·string_sim + w2·structural_sim + w3·contextual_sim`
- **BLINK / GENRE**: zero-shot entity linking, cross-encoder scoring

#### 3.1.3 MarketScope 적용안

```
Stage 1 (Candidate): _candidate_words 2글자 허용으로 확장
  → 2글자면 LIKE '홍대%' (prefix-only), 3글자+ 은 contains 허용

Stage 2 (Rank): 후보 N 개에 대해
  score = 0.5 × name_sim (RapidFuzz token_set_ratio)
        + 0.3 × type_priority (발달 > 골목 > 전통 > 관광특구)
        + 0.2 × daily_flpop_zscore

Stage 3 (Abstain): Top1 score < 0.6 또는 (Top1 - Top2) < 0.05
  → "홍대입구역_1 과 홍익대학교_발달상권 중 어디를 보시나요?" 재질문 카드
```

**인프라**: PostgreSQL `pg_trgm` + GiST 인덱스 (1,650 규모에 ms 단위). 임베딩 불필요.

### 3.2 카테고리 2 — Taxonomy / Alias Expansion (GAP-B)

#### 3.2.1 업계 사례

- **Amazon/Shopee**: miss 키워드 → LLM 분류 → `learned_aliases` 테이블 적재 → 다음 사용자는 즉시 hit.
- **Yelp**: "bubble tea / boba / 버블티" 다국어 별칭을 수작업 + 크라우드소싱 누적. 트렌드 키워드는 별도 surface.
- **Spotify**: LLM 이 new cluster 제안 → editor 승인 → taxonomy 반영 (TnT-LLM 패턴).

#### 3.2.2 연구 접근

- **TaxoAdapt / Taxoria / CodeTaxo**: query node 삽입 문제 — LLM 이 (a) 후보 parent 탐색 (b) 정당성 설명 (c) 중복 체크.
- **TELEClass**: class-specific term mining — 기존 노드 + 코퍼스에서 autocatch.
- **TAXMAP**: contextual embedding + 생성 모델 3종 앙상블 + **human validation gate**.

#### 3.2.3 MarketScope 적용안

```python
# services/category_resolver.py (확장)
def resolve(self, message: str) -> str | None:
    # 1. 기존 hit-path (defaults + DB aliases)
    if code := self._exact_lookup(message):
        return code

    # 2. learned_aliases 테이블 (신규 스키마)
    if code := self._learned_lookup(message):
        self._increment_hit(message, code)
        return code

    # 3. miss → LLM fallback (Gemini flash)
    llm_result = await self._llm_classify(
        message,
        known_categories=self._all_codes_with_aliases()
    )
    if llm_result.confidence >= 0.8:
        self._insert_learned_alias(
            alias=message,
            code=llm_result.code,
            confidence=llm_result.confidence,
            source="llm_gemini_flash"
        )
        return llm_result.code

    # 4. confidence 낮음 → 선택지 카드 반환 (None 대신 AbstainSignal)
    return AbstainSignal(options=self._top_k_similar_codes(message, k=3))
```

**신규 테이블** (`003_add_learned_aliases.py` 마이그레이션):
```sql
CREATE TABLE learned_aliases (
  alias TEXT PRIMARY KEY,
  code TEXT NOT NULL REFERENCES category_metadata(code),
  confidence REAL NOT NULL,
  source TEXT NOT NULL,  -- 'llm_gemini_flash' | 'human'
  hit_count INT DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT now(),
  last_used_at TIMESTAMPTZ DEFAULT now()
);
```

**Promote 규칙**: `hit_count ≥ 5` 이면 `category_metadata.aliases` 로 승급 (LLM 재호출 불필요화).

### 3.3 카테고리 3 — Conversational Query Rewriting & Coreference (GAP-C/E)

#### 3.3.1 업계 사례

- **Perplexity / ChatGPT Search**: 모든 follow-up 을 **standalone question** 으로 rewrite 후 retrieval.
- **Google AI Overviews**: CHIQ 스타일 — 히스토리 먼저 "clean context" 로 표준화 후 rewrite.
- **Elasticsearch / Alhena**: **4-parallel rewriter** (coreference / recall / constraint / intent) 병합. 60% follow-up 에 coreference 존재.

#### 3.3.2 연구 접근

- **InfoCQR**: "pronouns resolve, carry implied subjects, preserve intent" 3원칙 프롬프트.
- **CHIQ**: 히스토리를 그대로 주지 않고 "clean context" 로 치환.
- **SEAL**: 2-stage semantic parsing — LLM extract → agentic calibration. PAE 와 구조 동일.

#### 3.3.3 MarketScope 적용안

**Pre-Planner Rewriter Sub-node** 추가 (PAE 그래프 변경):

```
START → [rewriter?] → PLANNER → ACTOR → EVALUATOR → RESPOND → END
         ↑
  coreference 감지 패턴이 message 에 있고
  history 가 존재할 때만 활성화 (lazy gate)
```

**감지 패턴**: `거기|저기|방금|그거|이거|해당|위|동일`
**활성화 조건**: 위 패턴 + `len(history) > 0`

**Sub-node 프롬프트** (Gemini flash, ~200ms):
```
system: "아래 대화 히스토리를 참조해, 마지막 user 메시지를
         독립적으로 이해 가능한 질문으로 재작성하세요.
         규칙:
         - 대명사는 최근 카드의 district/category 로 치환
         - 생략된 주어 복원
         - 원래 의도 보존
         - 도치 문장은 자연스러운 어순으로 정리
         JSON 응답: {rewritten, anchor_district, anchor_category}"
input:  최근 5 turn history + state.cards[-1].data + current_message
output: {rewritten: str, anchor_district: str|null, anchor_category: str|null}
```

Planner 는 `rewritten` 을 새 message 로 받고, `anchor_*` 을 entity 로 우선 주입. 앵커가 명확하면 Planner 의 detect_districts 단계 skip 가능 → 추가 지연 상쇄.

### 3.4 카테고리 4 — Abstention & Grounded Generation (GAP-D)

#### 3.4.1 핵심 인사이트 (Google Research 2025)

**"RAG abstention paradox"**: RAG 를 달면 오히려 abstain 확률이 **낮아진다**. 컨텍스트 존재 자체가 모델 confidence 를 부풀리기 때문. 단순한 프롬프트 규칙 추가만으로는 100% 준수 불가 → **후처리 검증 레이어** 필수.

#### 3.4.2 업계/연구 사례

- **Harvey / Moveworks**: citation 없는 문장은 UI 에서 회색으로 다운톤.
- **ChatGPT Deep Research**: retrieved chunk 0 이면 고정 템플릿 ("관련 자료 없음"), 일반 지식 답변 금지.
- **Bing Copilot**: confidence threshold 미달 시 abstain 문구.
- **HALT-RAG**: NLI 앙상블로 문장과 context 간 entailment 검증 → entail 없으면 재생성.
- **Selective Generation**: retrieval sufficient 분류기 먼저.
- **MEGA-RAG**: multi-evidence fallback.

#### 3.4.3 MarketScope 적용안 (2중 방어)

**Pre-check (respond.py 진입 시)**:
```python
def classify_tool_results(tool_results: list[dict]) -> str:
    """Return 'full' | 'partial' | 'empty'."""
    if not tool_results:
        return "empty"
    critical_fields = {
        "get_floating_population": "total_pop",
        "get_estimated_sales": "monthly_sales",
        "get_store_info": "total_stores",
        # ...
    }
    empties = 0
    for r in tool_results:
        key = critical_fields.get(r["tool"])
        if key and not r["result"].get(key):
            empties += 1
    if empties == len(tool_results):
        return "empty"
    return "partial" if empties > 0 else "full"

# Respond 프롬프트 분기
if status == "empty":
    return "요청하신 데이터를 가져오지 못했습니다. 다른 상권으로 시도해 주세요."
elif status == "partial":
    system_prompt += "\n일부 데이터가 수집되지 않았습니다. 해당 항목은 '데이터 없음' 으로 명시하고, 추정/일반지식 금지."
```

**Prompt 단 — 경량 attribution**:
```
"답변의 각 숫자/구체적 주장마다 괄호로 출처 Tool 명을 표기하세요.
 예: '일 유동인구 745만 (get_floating_population)'.
 출처 Tool 이 없으면 그 문장 자체를 쓰지 마세요."
```

**후처리 정규식 검증** (stream 종료 후 한 번):
```python
# 숫자 + 단위 패턴에 ('xxx_tool)' attribution 필수
UNATTRIBUTED = re.compile(r'\d[\d,\.]*\s*(원|명|%|억|만|건)(?!.*?\([a-z_]+\))')
violations = UNATTRIBUTED.findall(final_text)
if violations:
    log.warning("respond_hallucination_risk", count=len(violations))
    # Optional: 위반 문장 자동 탈락 or disclaimer 추가
```

### 3.5 카테고리 5 — Card-level PDF (GAP-F)

#### 3.5.1 업계 사례

- **Notion AI**: 블록 호버 → "Export this block as PDF".
- **Perplexity**: 각 답변 카드 Share/Export 버튼.
- **Linear / Slack**: 메시지 호버 → "Save as..." (스레드 전체 아님).

#### 3.5.2 MarketScope 적용안

- 전역 PDF 버튼 유지 + 각 Card 우상단에 `⬇ PDF` 버튼 추가
- `useReportExport({ messageId?: string })` 파라미터화
- `messageId` 있으면 해당 카드의 `ReportDocument` 서브셋만 렌더
- 전체 대화 모드는 기존대로 `messageId=undefined`

---

## 4. Checklist

### 4.1 작업 체크리스트 (W1~W4)

**W1 — 고빈도 이슈 선제 처리**
- [ ] GAP-A #1: `_candidate_words` 2글자 prefix 허용 (`repositories/real/districts.py`)
- [ ] GAP-A #2: 3-stage ranking 함수 + `pg_trgm` 인덱스 추가 (신규 마이그레이션 `004_add_pg_trgm.py`)
- [ ] GAP-A #3: Planner 에서 Top1-Top2 ambiguity 감지 시 abstain 카드 반환 경로
- [ ] GAP-D #1: `classify_tool_results` 유틸 (`agent/nodes/respond.py`)
- [ ] GAP-D #2: empty/partial 분기 + attribution 프롬프트 규칙
- [ ] GAP-D #3: 후처리 정규식 검증 + structlog 경고 로깅

**W2 — Coreference / Rewriter**
- [ ] GAP-E #1: coreference 패턴 감지 유틸 (`agent/nodes/rewriter.py` 신규)
- [ ] GAP-E #2: PAE 그래프에 conditional rewriter sub-node 추가 (`agent/graph.py`)
- [ ] GAP-E #3: `anchor_district` / `anchor_category` state 주입
- [ ] GAP-C #1: Planner 2-pass 재분석 — 엔티티 부족 시 LLM re-extract

**W3 — Learned Aliases**
- [ ] GAP-B #1: `learned_aliases` 테이블 마이그레이션 (`005_learned_aliases.py`)
- [ ] GAP-B #2: `CategoryResolver` LLM fallback + INSERT/UPDATE 로직
- [ ] GAP-B #3: `AbstainSignal` 처리 — Actor 에서 선택지 카드 발행
- [ ] GAP-B #4: hit_count ≥ 5 promote 야간 잡 (`scripts/promote_aliases.py`)

**W4 — UX**
- [ ] GAP-F #1: Card 컴포넌트 5종에 PDF 버튼 prop
- [ ] GAP-F #2: `useReportExport({ messageId })` 파라미터화
- [ ] GAP-F #3: `ReportDocument` 가 messageId 기반 서브셋 렌더링 지원

### 4.2 재검토 (Self-Review Gate)

- [ ] **엣지케이스**: Rewriter sub-node 가 원래 standalone 질문에도 작동하면? → 감지 패턴 매칭 안 되면 skip 하여 no-op 보장
- [ ] **엣지케이스**: `learned_aliases` 가 악의적 입력으로 오염되면? → confidence ≥ 0.8 + LLM prompt 에 카테고리 화이트리스트 고정
- [ ] **엣지케이스**: `pg_trgm` 성능 — 1,650 rows 에서 OK 지만 상권 추가 시 인덱스 재생성 필요
- [ ] **메모리 교훈**: `feedback_stale_container_vs_source.md` — 각 W 단계 후 backend 컨테이너 재빌드 강제
- [ ] **메모리 교훈**: `feedback_marketscope_sse_format.md` — Rewriter 추가로 SSE 이벤트 타입 추가 X, 내부 state 만 변경
- [ ] **타 Plan 충돌**: `sales-unit-conversion-fix.md` (완료), `deployment-root-cause-fixes.md` (완료) — 영향 없음
- [ ] **LLM 비용**: Rewriter (조건부) + alias mining (miss-only) → 평균 요청당 +0.3 flash call → 월 예상 증가 < $5 (MVP 규모)

### 4.3 Scenario (E2E Ring Mapping)

| Ring | ID | 시나리오 | 대상 GAP | 기대 |
|------|----|---------|:--------:|------|
| 1 | 1-F05-H5 | "홍대 vs 성수 매출 비교" | A | 2개 상권 detect, CompareCard 렌더 |
| 1 | 1-F05-H6 | "종로 vs 종로3가" ambiguity | A | abstain 카드 (선택지 2개) |
| 1 | 1-F04-H3 | "브런치 가게 차리면 매출?" | B | simulate_revenue 호출, SimulationCard |
| 1 | 1-F04-H4 | "무인카페" 신규 키워드 | B | LLM fallback hit + learned_aliases INSERT |
| 2 | 2-J06 | 비교 후 "거기 중 2030 비율?" | E | rewriter 활성, compareList 참조 |
| 2 | 2-J07 | 요약 후 "치킨집 몇 년 버텨?" | D | get_store_history 호출 또는 abstain |
| 3 | 3-REG-ABSTAIN | Tool 실패 시뮬레이션 | D | 일반 지식 답변 0건 |
| 3 | 3-REG-REWRITER-NOOP | standalone 질문에 rewriter 미발동 | E | 감지 패턴 없으면 skip |

### 4.4 Pass 반복 전략

- **Pass 1 (기본)**: W1 완료 후 GAP-A/D 시나리오만 Ring 1 회귀
- **Pass 2 (엣지)**: W2-W3 완료 후 ambiguity / rewriter-noop / learned_aliases 중복 INSERT 방어
- **Pass 3 (성능)**: LLM 호출 수 측정 (Rewriter + Resolver fallback 총합 / 세션당 평균 < 1.5)
- Fail → `feedback_check_env_before_test.md` 에 따라 Mock/Real 양쪽 재실행

### 4.5 Agent 모델 선택

- **설계**: opus (본 Plan 작성)
- **구현**: sonnet (각 W 단계별)
- **검증**: haiku (정규식/유틸 단위 테스트), opus (rewriter 프롬프트 엔지니어링)

---

## 5. Validation

### 5.1 회귀 검증

- 2026-04-13 분석 품질 스코어 재측정 (S1~S8), S3/S6/S7 이 9.0 이상 목표
- Ring 1/2/3 전수 실행 (`npm test`), Consumer score 100/100 유지
- `docs/qa/runs/accuracy-gap-fix-{date}.md` 런 리포트 작성

### 5.2 정량 KPI

| 지표 | 현재 | 목표 |
|------|-----:|-----:|
| 정확성 종합 점수 | 74 | 85+ |
| S3 (비교) | 2.6 | 9.0+ |
| S6 (시뮬레이션) | 6.1 | 9.0+ |
| S7 (후속질문) | 8.9 | 9.3+ |
| GAP-A 성공률 | ~60% | 95%+ |
| GAP-D 할루시네이션 발생률 | ~15% | <3% |
| 평균 LLM 추가 호출 / session | 0 | < 1.5 |

### 5.3 비용/지연 가드

- Rewriter sub-node: flash 호출 단일, p95 < 500ms
- Learned aliases fallback: flash 호출 단일, miss-only, 누적 후 hit-rate ≥ 80%
- Respond 후처리 정규식: < 10ms, 동기 처리

---

## Metadata

| 항목 | 값 |
|------|-----|
| 작성자 | Claude (Opus 4.7) + 사용자 합의 |
| 작성일 | 2026-04-22 |
| 선행 Plan | `sales-unit-conversion-fix.md` ✅, `deployment-root-cause-fixes.md` ✅ |
| 후행 연계 | Phase 2 — `plan/business/commercialization-plan.md` (Premium 착수 전 선행 권장) |
| 참고 리서치 | 본 Plan §3 업계 사례 + 연구 접근 — Sources 섹션 참조 |

## Sources

**Query Rewriting / Coreference**
- [RAG Query Rewriting: 4 Layers That Fix Multi-Turn Retrieval — Alhena](https://alhena.ai/blog/query-rewriting-before-retrieval-multi-turn-rag/)
- [InfoCQR: Informative Conversational Query Rewriting (arXiv 2310.09716)](https://arxiv.org/html/2310.09716)
- [CHIQ: Contextual History Enhancement for Query Rewriting (arXiv 2406.05013)](https://arxiv.org/html/2406.05013v1)
- [Query rewriting strategies for LLMs & search engines — Elasticsearch](https://www.elastic.co/search-labs/blog/query-rewriting-llm-search-improve)
- [SEAL: Self-Evolving Agentic Learning for Conversational QA (SSRN)](https://papers.ssrn.com/sol3/Delivery.cfm/94ced9f0-a736-4434-9c44-5c95ab93da32-MECA.pdf?abstractid=5800460&mirid=1)
- [Improving LLMs' Learning for Coreference Resolution (arXiv 2509.11466)](https://arxiv.org/abs/2509.11466)

**Entity Linking / Fuzzy Matching**
- [Entity linking — Wikipedia](https://en.wikipedia.org/wiki/Entity_linking)
- [Word Embeddings for Fuzzy Matching of Organization Names — Babel Street](https://www.babelstreet.com/blog/word-embeddings-for-fuzzy-matching-of-organization-names)
- [Neural Entity Linking: A Survey (arXiv 2006.00575)](https://arxiv.org/pdf/2006.00575)
- [A Flexible Deep Learning Approach to Fuzzy String Matching (EMNLP 2020)](https://aclanthology.org/2020.emnlp-demos.9.pdf)

**Abstention / Grounded Generation**
- [Deeper insights into RAG: The role of sufficient context — Google Research](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)
- [HALT-RAG: Hallucination Detection with NLI Ensembles and Abstention (arXiv 2509.07475)](https://arxiv.org/html/2509.07475v1)
- [Hallucination Mitigation for RAG — A Review (MDPI)](https://www.mdpi.com/2227-7390/13/5/856)
- [AI grounding: How agentic RAG will help limit AI hallucinations — Moveworks](https://www.moveworks.com/us/en/resources/blog/improved-ai-grounding-with-agentic-rag)

**Taxonomy Expansion**
- [CodeTaxo: Taxonomy Expansion with Code Language Prompts (arXiv 2408.09070)](https://arxiv.org/html/2408.09070)
- [TaxoAdapt: Aligning LLM-Based Multidimensional Taxonomy (ACL 2025)](https://aclanthology.org/2025.acl-long.1442.pdf)
- [TELEClass: Taxonomy Enrichment and Hierarchical Classification (arXiv 2403.00165)](https://arxiv.org/html/2403.00165v2)
- [TnT-LLM: Text Mining at Scale with Large Language Models (arXiv 2403.12173)](https://arxiv.org/html/2403.12173v1)
- [Taxonomy Expansion through Collaborative LLM Mapping (ACM SAC 2025)](https://dl.acm.org/doi/10.1145/3672608.3707906)
