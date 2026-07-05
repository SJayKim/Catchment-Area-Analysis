# F05-H3 / F05-H4 회귀 fix — 2026-04-27

> Ring 1 의 F05-compare 다색 하이라이트 store 검증 spec 2건이 Real 모드에서 FAIL. spec 자체의 wait 가 부족.

## 1. Context

E2E ring1 회귀 (2026-04-27) 에서 ring1 38 PASS / 2 FAIL.

| spec | 라인 | 실패 단언 |
|------|-----:|----------|
| F05-H3 비교모드 다색 하이라이트 store 상태 (4dbd598 회귀) | 113 | `expect(lenOk).toBe(true)` |
| F05-H4 한글 조사 처리 (과/를 회귀) | 149 | `expect(ok).toBe(true)` |

**근본 원인**:
- 두 spec 모두 `await sendChatMessage(...) → await page.waitForTimeout(3000) → window.__districtStore.getState()` 패턴.
- `mode: 'Mock'` 메타데이터로 작성됐지만 현 백엔드는 Real(USE_MOCK=false). Real-mode 3-way comparison 은 SSE done 까지 30~60s.
- 3 초 시점엔 `compare` card 이벤트가 아직 도착 안 함 → eventHandlers `case 'card'` 의 `addToCompare` 미실행 → `compareList=[]`.
- Spec 의 PASS/FAIL 은 환경 의존적 (Mock 에선 PASS, Real 에선 FAIL). 4dbd598 의 다색 하이라이트 자체 회귀가 아니라 spec 의 환경 가정이 틀어짐.

**무관한 변경**:
- 오늘(04-27) working tree 의 entity_matching / errors.py / sanitizer 변경은 본 회귀와 무관.
- 컨테이너 베이스라인 04-24 에서 잔존하는 **spec-level** 문제.

## 2. Scope

| 항목 | 변경 파일 | 변경 |
|------|----------|------|
| F05-H3 wait | `frontend/e2e/ring1-features/f05-compare.spec.ts` | `waitForTimeout(3000)` → `waitForFunction(...compareList.length===3, 60000)` |
| F05-H4 wait | 동 | 동일 패턴 (length===2) |
| 헬퍼 (옵션) | `frontend/e2e/helpers/setup.ts` | `waitForCompareList(page, expectedLen, timeout)` 헬퍼 추가 |

비범위:
- 다색 하이라이트 4dbd598 회귀 자체 (실제 회귀 아님 — spec 문제)
- `mode: 'Mock'` 메타데이터 정정 (EvalPacket 메타이고 실행 영향 없음 — 후속)

## 3. Design

### 3.1 헬퍼 추가

```ts
// frontend/e2e/helpers/setup.ts (append)
export async function waitForCompareList(
  page: Page,
  expectedLen: number,
  timeout = 60_000,
): Promise<{ codes: string[]; mode: boolean }> {
  await page.waitForFunction(
    (n) => {
      const w = window as unknown as {
        __districtStore?: { getState: () => unknown };
      };
      const st = w.__districtStore?.getState?.() as
        | { compareList?: { code: string }[]; isCompareMode?: boolean }
        | undefined;
      return (st?.compareList?.length ?? 0) === n && st?.isCompareMode === true;
    },
    expectedLen,
    { timeout },
  );
  return await page.evaluate(() => {
    const w = window as unknown as { __districtStore?: { getState: () => unknown } };
    const st = w.__districtStore?.getState?.() as
      | { compareList?: { code: string }[]; isCompareMode?: boolean }
      | undefined;
    return {
      codes: st?.compareList?.map((d) => d.code) ?? [],
      mode: !!st?.isCompareMode,
    };
  });
}
```

### 3.2 F05-H3 / F05-H4 spec 변경

`waitForTimeout(3000)` 직후의 `page.evaluate(...)` 블록을 `waitForCompareList(page, N, 60_000)` 한 줄로 교체. expect 단언은 동일.

## 4. Checklist

### Pass 1 — 기본 구현

- [ ] (T1) `waitForCompareList` 헬퍼 추가
- [ ] (T2) F05-H3 wait 교체 (length=3)
- [ ] (T3) F05-H4 wait 교체 (length=2)
- [ ] (T4) `npx playwright test ring1-features/f05-compare.spec.ts -g "F05-H3|F05-H4" --reporter=line` PASS

### 재검토

- 엣지: 60s 내에도 SSE 가 카드 발행 못 하면 `waitForFunction` 타임아웃 → FAIL 되지만, 이 경우는 시스템 회귀가 맞으므로 정확한 신호.
- 메모리 교훈:
  - [feedback_check_env_before_test](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_check_env_before_test.md) — Mock vs Real spec 분기 인지
  - [feedback_playwright_sse_capture](../../../.claude/projects/C--Users-cyon1-OneDrive-Desktop-Catchment-Area-Analysis/memory/feedback_playwright_sse_capture.md) — page.route 금지 (해당 spec 은 store 직접 검증이라 무관)

## 5. Scenario

| Ring | Case | 검증 |
|------|------|------|
| Ring 1 | F05-H3 | `compareList.length===3 && isCompareMode===true` (60s 내) |
| Ring 1 | F05-H4 | `compareList.length===2 && isCompareMode===true` (60s 내) |
| Ring 1 | F05-H1/H2/E1 | 회귀 가드 (영향 없어야 함) |

## 6. Pass

- Pass 1 (기본): T1~T4
- Pass 2 (엣지): SSE 30s 내 카드 미도달 시 명확한 timeout 메시지 확인 (시스템 회귀 시그널)

## 7. Validation

- `npx playwright test ring1-features/f05-compare.spec.ts --project=chromium --reporter=line` → 5/5 PASS

## 8. Metadata

- Owner: sjkim
- Created: 2026-04-27
- 관련 Plan: [p0-priority-2026-04-27](../fix/p0-priority-2026-04-27.md), [e2e-spec-hotfix-2026-04-23](e2e-spec-hotfix-2026-04-23.md)
