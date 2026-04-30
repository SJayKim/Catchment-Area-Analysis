/**
 * Ring0-D1 — Route error boundary.
 *
 * 2026-04-30 Plan `ux-sweep-phase-d-a11y` (D.1). 4 boundary 파일이 정상
 * 등록되었는지 + reset 동선이 살아있는지 가벼운 정적 검증.
 *
 * Playwright 환경에서 의도적으로 Next 의 build manifest 를 깨뜨리는 건 risk
 * 가 커서, 빈 상태에서 직접 boundary 컴포넌트가 마운트되었는지 + 키 selector
 * (data-testid) 가 노출되는지 확인한다.
 */
import { test, expect } from '../helpers/setup';

test.describe('Ring0-D1 — Route error/loading boundaries', () => {
  test('global error.tsx 신규 — 컴포넌트 export + reset 시그니처', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const here = process.cwd();
    const target = path.resolve(here, 'src/app/error.tsx');
    const src = fs.readFileSync(target, 'utf8');
    expect(src).toContain("'use client'");
    expect(src).toMatch(/reset:\s*\(\)\s*=>\s*void/);
    expect(src).toContain('data-testid="route-error"');
    expect(src).toContain('data-testid="route-error-reset"');
  });

  test('global loading.tsx 신규 — role=status 표기', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const target = path.resolve(process.cwd(), 'src/app/loading.tsx');
    const src = fs.readFileSync(target, 'utf8');
    expect(src).toContain('data-testid="route-loading"');
    expect(src).toContain('role="status"');
  });

  test('/app error.tsx 신규 — reset + 홈 링크', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const target = path.resolve(process.cwd(), 'src/app/app/error.tsx');
    const src = fs.readFileSync(target, 'utf8');
    expect(src).toContain('data-testid="app-route-error"');
    expect(src).toContain('data-testid="app-route-error-reset"');
    expect(src).toContain('data-testid="app-route-error-home"');
  });

  test('/app loading.tsx 신규 — split-panel skeleton', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const target = path.resolve(process.cwd(), 'src/app/app/loading.tsx');
    const src = fs.readFileSync(target, 'utf8');
    expect(src).toContain('data-testid="app-route-loading"');
    expect(src).toContain('animate-pulse');
    expect(src).toContain('animate-bounce');
  });

  // (Mock-only) 신규 8 — D.1 reset() 무한 throw 시 Next 자체 fallback 의존.
  // boundary 컴포넌트 자체가 reset 호출 후 같은 throw 가 재발생할 때 self-throw
  // 하지 않고 Next 의 default error overlay 가 처리하도록 위임. 정적 회귀:
  //   - reset() 콜백 안에서 setState/throw 가 부재 (boundary 자체 self-throw 없음)
  //   - useEffect 가 console.error 만 수행 (re-throw 부재)
  test('Ring0-D1-RESET-LOOP — boundary self-throw 없음 (정적 invariant)', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const targets = [
      path.resolve(process.cwd(), 'src/app/error.tsx'),
      path.resolve(process.cwd(), 'src/app/app/error.tsx'),
    ];
    for (const t of targets) {
      const src = fs.readFileSync(t, 'utf8');
      // reset() 호출은 inline arrow 한 곳뿐 — chain throw 없음.
      const resetMatches = src.match(/reset\(\)/g) ?? [];
      expect.soft(resetMatches.length, `${t} reset() 호출 1회`).toBe(1);
      // useEffect 안에 throw 가 등장하지 않아야 (boundary 가 재진입 무한 throw
      // 를 만들지 않음).
      expect.soft(/useEffect\([^)]*throw/.test(src), `${t} useEffect throw 없음`).toBe(
        false
      );
      // setState 호출이 useEffect 안에서 재진입 throw 를 만들지 않도록 — 단순
      // console.error 만 수행하는지 확인.
      expect(src).toMatch(/console\.error\(/);
      expect(src).not.toMatch(/throw\s+new\s+Error/);
    }
  });
});
