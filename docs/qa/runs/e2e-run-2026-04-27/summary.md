# E2E Run — 2026-04-27

## 결과 (75 PASS / 2 FAIL / 32 SKIP)

| Ring | Pass | Fail | Skip | 비고 |
|------|-----:|-----:|-----:|------|
| 0 preflight | 1 | 0 | 0 | stack-up 정상 |
| 1 features | 38 | **2** | 4 | F05-H3 / F05-H4 (chromium only) |
| 2 journeys | 10 | 0 | 0 | chromium + mobile-iphone + tablet-ipad |
| 3 negative | 26 | 0 | 28 | tablet/mobile 변형 skip |
| **합계** | **75** | **2** | **32** | |

## FAIL 2건

- `f05-compare.spec.ts:71` **F05-H3 비교모드 다색 하이라이트** — `expect(ok).toBe(true)` 실패. 4dbd598 (04-17) 다색 하이라이트 회귀 검증 spec 자체.
- `f05-compare.spec.ts:118` **F05-H4 한글 조사 처리 (과/를)** — 동일 검증 라인.

두 건 모두 **컨테이너 베이스라인(04-24)** 의 잔존 회귀이며, 오늘 변경분과 무관.

## 오늘 변경분 검증

컨테이너는 2일 전 빌드라 W1 entity_matching market boost / `_XMLTagSanitizer` / `errors.py` 헬퍼는 반영 안 됨. 대신 unit 으로 커버:

- `tests/test_entity_matching.py` 6/6 PASS
- `tests/test_xml_sanitizer.py` 6/6 PASS
- `tests/test_planner_clarification.py` 4/4 PASS

## 다음

- F05-H3/H4 — 별도 회귀로 진단 필요 (04-17 다색 하이라이트 commit 후 store 상태 노출 변경 가능). spec vs 구현 정렬 점검.
- 오늘 변경분 E2E 검증은 backend 재빌드 + 재기동 후 ring1 재실행으로 가능. 현재 unit 커버리지로 충분.
